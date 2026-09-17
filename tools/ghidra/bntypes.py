#!/usr/bin/env python3
"""Turn the reference/bn6f disassembly's own struct definitions into C that
Ghidra can parse, and into the evidence tables that say where those types
belong in the cartridge.

The disassembly does not declare its types in C.  It declares them as GNU-as
macros under `include/structs/*.inc` and `include/rom_structs/*.inc`, e.g.

        .macro ai_data_struct, label:req, struct_entry=..., ...
        enum8 ActorType   // loc=0x0
        u8 AIIndex        // loc=0x1
        ...
        struct_org 0xa0
        u8_arr AttackVars, 0x50 // loc=0xa0
        .endm

        def_struct_offsets ai_data_struct, oAIData

and the build then *assembles* those macros to produce one absolute symbol per
field (`oAIData_AIIndex = 1`).  That assembly step is the only thing that knows
the real layout -- unions, `struct_org`, nested sub-structs and `.space` make
the text alone ambiguous -- so this script runs it:

  1. assemble a throwaway file that includes only the struct macros, and read
     every `o<Struct>_<Field>` absolute symbol out of the object file.  Those
     offsets are ground truth, produced by the same assembler the ROM is built
     with.
  2. parse the same .inc text for the things the symbol table cannot carry:
     field order, declared width, which fields are alternate names for the same
     bytes (unions), and which fields are nested structs.
  3. emit one C struct per `def_struct_offsets` label, with the true offsets,
     explicit padding, and a manifest recording which .inc line each came from,
     then compile the result with `_Static_assert` on every offset and every
     size so a transcription slip fails here instead of quietly renaming half a
     routine's fields.

Three more evidence passes read the disassembly rather than the includes:

  * pointer and sub-struct types -- `ldr r4,[r5,#oBattleObject_AIDataPtr]`
    followed by `ldrb r0,[r4,#oAIData_ActorType]` can only mean that field is
    an `AIData *`; `add r7,#oAIData_AttackVars` followed by
    `[r7,#oAIAttackVars_Unk_30]` can only mean that field is an AIAttackVars.
    Both symbols in each pair were written by the disassembly, so neither end
    of the inference is invented here.
  * global instances -- `ewram.s` and friends instantiate the structs by name
    (`t1_battle_object_struct eT1BattleObject0`), `data/ChipDataArr.s` repeats
    a rom-struct literal 411 times, and `bn6f.map` gives every one of them an
    address.  That is what types 0x0203a9b0 as a BattleObject and 0x08021da8 as
    ChipData[411] without anyone guessing.
  * register parameters -- the game passes the current object in r5 and the AI
    attack variables in r7, registers no ARM calling convention describes.  The
    disassembly proves it per function, three ways: operand syntax
    (`ldrb r0, [r5,#oBattleObject_CurState]` can only mean r5 is a
    BattleObject*, and only counts while the function has not written r5
    itself), hand-written signature comments
    (`sub_8033A80: // (self: * S2011E30 $r5) -> ()`), and call-through -- a
    routine that calls one of those without setting r5 must be supplying its
    own.  Contradictions between them are dropped and reported, never averaged.

Nothing is written inside reference/bn6f; the submodule is read-only here.

    tools/ghidra/bntypes.py --ref reference/bn6f --out-dir <workdir>

writes, into <workdir>:
    bn_types.h        C declarations for every struct
    bn_types.tsv      manifest: struct -> .inc, every field, every alias
    bn_globals.tsv    global label -> struct type -> address
    bn_protos.tsv     function -> register -> pointer type, with its evidence
"""

import argparse
import collections
import os
import re
import subprocess
import sys
import tempfile

# ---------------------------------------------------------------------------
# The assembler's own type vocabulary (include/macros/struct.inc), as widths.
# u0 is a zero-width marker: `u0 Size` names the end of a struct, `u0 AIState`
# names a nested one.  u8_arr carries its length as a second argument.
# ---------------------------------------------------------------------------
PRIMITIVES = {
    "u0": (0, None),
    "u8": (1, "u8"),
    "u16": (2, "u16"),
    "u32": (4, "u32"),
    "s8": (1, "s8"),
    "s16": (2, "s16"),
    "s32": (4, "s32"),
    "ptr": (4, "ptr"),
    "bool": (1, "bool8"),
    "bool8": (1, "bool8"),
    "enum8": (1, "u8"),
    "enum16": (2, "u16"),
    "enum32": (4, "u32"),
    "flags8": (1, "u8"),
    "flags16": (2, "u16"),
    "flags32": (4, "u32"),
    "u8_arr": (None, "u8[]"),
}

CTYPE = {
    "u8": "u8",
    "u16": "u16",
    "u32": "u32",
    "s8": "s8",
    "s16": "s16",
    "s32": "s32",
    "bool8": "u8",
    "ptr": "void *",
}

MACRO_RE = re.compile(r"^\s*\.macro\s+([A-Za-z_][\w]*)\s*,?\s*(.*)$")
ENDM_RE = re.compile(r"^\s*\.endm\b")
DEFOFF_RE = re.compile(
    r"^\s*def_(?:rom_)?struct_offsets\s+([A-Za-z_]\w*)\s*,\s*([A-Za-z_]\w*)")
# BattleObject.inc does not go through def_struct_offsets: it calls the macro
# directly in offset mode, once per object flavour, because each flavour has a
# different `extra_vars_size`.  Those four calls define oBattleObject,
# oT1BattleObject, oT3BattleObject and oT4BattleObject.
DIRECTOFF_RE = re.compile(
    r"^\s*([A-Za-z_]\w*_struct)\s+([A-Za-z_]\w*)\s*,\s*offset_struct_entry\b"
    r"\s*(?:,\s*[A-Za-z_]\w*)?\s*(?:,\s*(\S+?))?\s*$")
EQUIV_RE = re.compile(r"^\s*\.equiv\s+(o[A-Za-z_]\w*)\s*,\s*(0x[0-9a-fA-F]+|\d+)")


def strip_comment(line):
    """Return (code, comment) for one .inc line, honouring // and /* */."""
    comment = ""
    i = line.find("//")
    if i >= 0:
        code, comment = line[:i], line[i + 2:].strip()
    else:
        code = line
    j = code.find("/*")
    if j >= 0:
        code = code[:j]
    return code.rstrip(), comment


# ---------------------------------------------------------------------------
# 1. Ground-truth offsets, straight out of the assembler
# ---------------------------------------------------------------------------

def assemble_offsets(ref, keep_dir=None):
    """Assemble the struct macro includes and return {symbol: offset}.

    `def_struct_offsets` runs each struct macro in `.struct` mode, which turns
    every field into an absolute symbol holding its byte offset.  Assembling is
    therefore the authoritative way to resolve unions, `struct_org` and nested
    sub-structs; no reimplementation of GNU as's macro expansion can be trusted
    against it.
    """
    src = "\n".join([
        '\t.include "include/macros/enum.inc"',
        '\t.include "include/macros/label.inc"',
        '\t.include "include/macros/struct.inc"',
        '\t.include "include/macros/rom_struct.inc"',
        '\t.include "include/macros/ewram_structs.inc"',
        '\t.include "include/macros/rom_structs.inc"',
        "",
    ])
    tmp = keep_dir or tempfile.mkdtemp(prefix="bntypes")
    asm = os.path.join(tmp, "bntypes_probe.s")
    obj = os.path.join(tmp, "bntypes_probe.o")
    with open(asm, "w") as f:
        f.write(src)
    for exe in ("arm-none-eabi-as", "arm-none-eabi-nm"):
        if not any(os.access(os.path.join(p, exe), os.X_OK)
                   for p in os.environ.get("PATH", "").split(os.pathsep)):
            sys.exit("bntypes: %s not found; the struct offsets can only be "
                     "obtained by assembling the disassembly's own macros" % exe)
    r = subprocess.run(
        ["arm-none-eabi-as", "-mcpu=arm7tdmi", "-I", ".", "-I", "include",
         asm, "-o", obj],
        cwd=ref, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit("bntypes: assembling the struct macros failed:\n" + r.stderr)
    out = subprocess.run(["arm-none-eabi-nm", "-t", "x", obj],
                         capture_output=True, text=True, check=True).stdout
    offsets = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[1].lower() == "a":
            offsets[parts[2]] = int(parts[0], 16)
    return offsets


# ---------------------------------------------------------------------------
# 2. The .inc text: order, width, nesting, unions
# ---------------------------------------------------------------------------

class Item(object):
    __slots__ = ("kind", "name", "arg", "line", "comment", "prev_comment")

    def __init__(self, kind, name, arg=None, line=0, comment="", prev_comment=""):
        self.kind = kind          # field | call | union | nextu | endu | const
        self.name = name
        self.arg = arg
        self.line = line
        self.comment = comment
        self.prev_comment = prev_comment


class Macro(object):
    def __init__(self, name, params, path, line):
        self.name = name
        self.params = params      # ordered [(name, default)]
        self.path = path
        self.line = line
        self.items = []
        self.is_rom = False
        self.alias_of = None      # a one-line wrapper: JoypadFlags -> enum16
        self.type_note = ""       # the `// type: struct AIData` comment


def parse_params(text):
    params = []
    for raw in text.split(","):
        raw = raw.strip()
        if not raw:
            continue
        raw = raw.replace(":req", "")
        if "=" in raw:
            k, v = raw.split("=", 1)
            params.append((k.strip(), v.strip()))
        else:
            params.append((raw, ""))
    return params


def parse_incs(ref):
    """Read every struct .inc into Macro objects plus the def_*_offsets list."""
    macros = {}
    defs = []            # (macro_name, label, path, line, is_rom)
    equivs = []          # (symbol, path, line, comment)
    roots = [os.path.join("include", "structs"),
             os.path.join("include", "rom_structs")]
    files = [os.path.join("include", "macros", "ewram_structs.inc")]
    for root in roots:
        d = os.path.join(ref, root)
        for fn in sorted(os.listdir(d)):
            if fn.endswith(".inc"):
                files.append(os.path.join(root, fn))

    for rel in files:
        path = os.path.join(ref, rel)
        if not os.path.isfile(path):
            continue
        with open(path, errors="replace") as f:
            lines = f.readlines()
        cur = None
        prev_comment = ""
        in_block_comment = False
        for n, raw in enumerate(lines, 1):
            if in_block_comment:
                if "*/" in raw:
                    in_block_comment = False
                continue
            if "/*" in raw and "*/" not in raw:
                in_block_comment = True
                continue
            code, comment = strip_comment(raw)
            body = code.strip()

            m = MACRO_RE.match(code)
            if m and cur is None:
                cur = Macro(m.group(1), parse_params(m.group(2)), rel, n)
                cur.type_note = comment
                prev_comment = ""
                continue
            if cur is not None and ENDM_RE.match(code):
                macros[cur.name] = cur
                cur = None
                prev_comment = ""
                continue

            if cur is None:
                m = DEFOFF_RE.match(code)
                if m:
                    defs.append((m.group(1), m.group(2), rel, n, {}))
                    continue
                m = DIRECTOFF_RE.match(code)
                if m:
                    extra = {}
                    if m.group(3):
                        extra["extra_vars_size"] = m.group(3)
                    defs.append((m.group(1), m.group(2), rel, n, extra))
                    continue
                m = EQUIV_RE.match(code)
                if m:
                    equivs.append((m.group(1), rel, n, comment))
                continue

            if not body:
                if comment:
                    prev_comment = comment
                continue

            head = body.split()[0]
            rest = body[len(head):].strip()

            if head == "\\struct_entry":
                # ewram_structs.inc writes some structs without the u8/u16/u32
                # wrappers, invoking the entry macro directly with an explicit
                # byte size: `\struct_entry \label\()_Unk_04, 2`.
                args = [a.strip() for a in rest.split(",")] if rest else []
                if args:
                    cur.items.append(Item("raw", args[0],
                                          args[1] if len(args) > 1 else "0",
                                          n, comment, prev_comment))
                prev_comment = ""
                continue

            if head in ("union", "nextu", "endu"):
                cur.items.append(Item(head, None, line=n))
            elif head == "struct_const":
                parts = [p.strip() for p in rest.split(",")]
                if len(parts) >= 2:
                    cur.items.append(Item("const", parts[0], parts[1], n, comment))
            elif head == "init_rom_struct":
                cur.is_rom = True
            elif head in PRIMITIVES or head.endswith("_struct") or head in macros \
                    or re.match(r"^[A-Za-z_]\w*$", head):
                args = [a.strip() for a in rest.split(",")] if rest else []
                args = [a for a in args if a != ""]
                if head in PRIMITIVES:
                    if not args:
                        continue
                    cur.items.append(Item("field", args[0].lstrip("\\"),
                                          args[1] if len(args) > 1 else None,
                                          n, comment, prev_comment))
                elif head.endswith("_struct"):
                    cur.items.append(Item("call", head, args, n, comment))
                else:
                    # A locally defined one-line wrapper type
                    # (`JoypadFlags Held`, `TextScriptArchivePtr TextScriptPtr`).
                    if args:
                        cur.items.append(Item("typed", head, args, n, comment,
                                              prev_comment))
            prev_comment = comment if comment else ""

    # A wrapper macro's width is its own first typed line.
    for mac in macros.values():
        if len(mac.params) == 1 and mac.items:
            first = next((i for i in mac.items if i.kind == "field"), None)
            if first is not None and all(
                    i.kind in ("field", "const") for i in mac.items):
                for line_item in mac.items:
                    if line_item.kind == "field":
                        break
                src_line = None
                with open(os.path.join(ref, mac.path), errors="replace") as f:
                    src_line = f.readlines()[first.line - 1]
                kind = src_line.split()[0]
                if kind in PRIMITIVES:
                    mac.alias_of = kind
    return macros, defs, equivs


# ---------------------------------------------------------------------------
# 3. Expansion: macro + label -> ordered, offset-resolved field list
# ---------------------------------------------------------------------------

class Field(object):
    def __init__(self, name, sym, offset, size, base, order, note=""):
        self.name = name
        self.sym = sym
        self.offset = offset
        self.size = size
        self.base = base          # u8/u16/.../ptr, or a struct C name
        self.order = order
        self.note = note
        self.array = 0            # element count when base is u8 and size > 1
        self.alias_of = None


class Struct(object):
    def __init__(self, cname, label, macro, path, line):
        self.cname = cname
        self.label = label
        self.macro = macro
        self.path = path
        self.line = line
        self.fields = []
        self.aliases = []
        self.size = 0
        self.note = ""


def cname_for(label):
    return label[1:] if label.startswith("o") and len(label) > 1 else label


def bind_args(macro, args):
    """Positional and keyword binding of a macro invocation's arguments."""
    values = {name: default for name, default in macro.params}
    pos = [p for p in macro.params]
    idx = 0
    for a in args:
        if "=" in a and re.match(r"^[A-Za-z_]\w*\s*=", a):
            k, v = a.split("=", 1)
            values[k.strip()] = v.strip()
        else:
            if idx < len(pos):
                values[pos[idx][0]] = a
            idx += 1
    return values


def substitute(text, values):
    """Expand \\label, \\()-concatenation and \\arg in a macro argument.

    `\\()` is GNU as's empty-string separator: `\\label\\()_SpriteData` means the
    argument `label` followed by the literal `_SpriteData`.  It has to terminate
    the parameter name before substitution, or the whole of `label_SpriteData`
    reads as one parameter and expands to nothing.
    """
    text = text.replace("\\()", "\x00")
    def repl(m):
        return str(values.get(m.group(1), ""))
    text = re.sub(r"\\([A-Za-z_]\w*)", repl, text)
    return text.replace("\x00", "").strip()


class Builder(object):
    def __init__(self, macros, offsets, def_labels=(), embedded=None,
                 declared_type=None):
        self.macros = macros
        self.offsets = offsets
        self.def_labels = set(def_labels)
        self.embedded = embedded or {}
        # (inc path, line) -> the type keyword that line declares, so expansion
        # never has to infer a width.
        self._decl_cache = declared_type or {}
        self.macro_to_label = {}      # object_sprite_struct -> oObjectSprite
        self.structs = {}             # label -> Struct
        self.missing = []
        self.order = 0

    def struct_size(self, label):
        """The struct's own length in bytes.

        `_End` is preferred over `_Size`: on the four battle-object flavours
        they differ, because `_Size` counts the 16-byte linked-list header that
        the allocator puts *before* the address every pointer to the object
        holds (bn6f.map: eT1BattleObject0_LinkedList_Prev is at
        eT1BattleObject0 - 0x10).  `_End` is the body, which is what a
        `BattleObject *` addresses.
        """
        for suffix in ("_End", "_Size"):
            if label + suffix in self.offsets:
                return self.offsets[label + suffix]
        return None

    def build(self, macro_name, label, path, line, extra=None):
        macro = self.macros[macro_name]
        st = Struct(cname_for(label), label, macro_name, path, line)
        st.note = macro.type_note
        self.order = 0
        # \label inside the macro body means this struct's own label; without
        # binding it every nested sub-struct would resolve to a bare "_Field".
        values = {name: default for name, default in macro.params}
        if macro.params:
            values[macro.params[0][0]] = label
        values.update(extra or {})
        self.expand(macro, label, values, st, depth=0)
        size = self.struct_size(label)
        if size is None:
            size = max((f.offset + max(f.size, 1) for f in st.fields), default=0)
            st.note = (st.note + " size inferred from last field").strip()
        st.size = size
        self.resolve_overlaps(st)
        return st

    def expand(self, macro, prefix, values, st, depth):
        if depth > 6:
            return
        for item in macro.items:
            if item.kind == "field":
                self.add_field(macro, item, prefix, values, st)
            elif item.kind == "raw":
                # This form spells the whole symbol, `\label\()_Unk_04`, not
                # just the field name the u8/u16/u32 wrappers take.
                name = substitute(item.name, values)
                if name.startswith(prefix + "_"):
                    name = name[len(prefix) + 1:]
                size = parse_int(substitute(item.arg or "0", values))
                kind = {1: "u8", 2: "u16", 4: "u32"}.get(size, "u8[]")
                self.emit(st, prefix, name, size, kind,
                          (item.prev_comment or item.comment or "").strip())
            elif item.kind == "typed":
                wrapper = self.macros.get(item.name)
                base = wrapper.alias_of if wrapper else None
                if base is None:
                    continue
                name = substitute(item.arg[0], values).lstrip("\\")
                size, kind = PRIMITIVES[base]
                note = wrapper.type_note if wrapper else ""
                self.emit(st, prefix, name, size, kind, note)
            elif item.kind == "call":
                self.expand_call(item, prefix, values, st, depth)

    def add_field(self, macro, item, prefix, values, st):
        name = substitute(item.name, values)
        if not name:
            return
        # The declared type keyword, looked up by the item's source position --
        # `_decl_cache` is filled from the .inc lines before any struct is built.
        decl = self._decl_cache.get((macro.path, item.line), "u8")
        size, kind = PRIMITIVES[decl]
        if decl == "u8_arr":
            raw = substitute(item.arg or "0", values)
            size = parse_int(raw)
        note = (item.prev_comment or item.comment or "").strip()
        self.emit(st, prefix, name, size, kind, note, decl)

    def emit(self, st, prefix, name, size, kind, note, decl=None):
        sym = prefix + "_" + name
        if sym not in self.offsets:
            self.missing.append(sym)
            return
        size = size if size is not None else 0
        if decl == "u0" and "o" + name in self.def_labels:
            # `u0 AIState // loc=0x80` is how the includes mark a nested struct
            # they did not want to re-declare.  The name is the struct's own
            # name, and it is only taken as one when its length fits the space
            # the parent leaves for it.
            inner = self.struct_size("o" + name)
            if inner:
                size, kind = inner, name
                note = (note + " u0 marker naming struct " + name).strip()
        elif decl == "u8_arr":
            proof = self.embedded.get((prefix, name)) or \
                self.embedded.get((self.canon_label(st), name))
            if proof and self.struct_size(proof[0]) == size:
                kind = cname_for(proof[0])
                note = "%s -- %d accesses through `add rN, #%s_%s` prove it" \
                    % (note, proof[1], self.canon_label(st), name)
        self.order += 1
        f = Field(name, sym, self.offsets[sym], size, kind, self.order, note)
        st.fields.append(f)

    def canon_label(self, st):
        """The label the asm writes this struct's field offsets with.

        All four battle-object flavours are indexed by `oBattleObject_*` in the
        code, so evidence gathered against the canonical label applies to each.
        """
        return self.macro_to_label.get(st.macro, st.label)

    def expand_call(self, item, prefix, values, st, depth):
        callee = self.macros.get(item.name)
        if callee is None:
            return
        args = [substitute(a, values) for a in item.arg]
        label = args[0] if args else prefix
        sub_values = bind_args(callee, args)
        if label == prefix:
            # `object_header_struct \label` -- the sub-struct's fields belong
            # directly to the parent, at the parent's own offsets.
            self.expand(callee, prefix, sub_values, st, depth + 1)
            return
        # A named sub-object: emit it as one field of the sub-struct's type.
        canon = self.macro_to_label.get(item.name)
        member = label[len(prefix) + 1:] if label.startswith(prefix + "_") else label
        # The sub-struct's `_Size`/`_End` symbols are written in the *parent's*
        # coordinate system (oBattleObject_SpriteData_Size == 0x9c, the offset
        # one past its last byte), so its length has to come from its own
        # canonical definition.
        size = self.struct_size(canon) if canon else None
        start = self.first_offset(callee, label, sub_values, depth)
        if size is None and start is not None:
            end = self.struct_size(label)
            size = (end - start) if end is not None else None
        if start is None or canon is None or size is None:
            self.expand(callee, label, sub_values, st, depth + 1)
            return
        self.order += 1
        f = Field(member, label, start, size, cname_for(canon), self.order,
                  "sub-struct " + item.name)
        st.fields.append(f)

    def first_offset(self, callee, label, values, depth):
        """The lowest offset any field of this sub-struct resolves to."""
        probe = Struct("probe", label, "", "", 0)
        save = self.order
        self.expand(callee, label, values, probe, depth + 1)
        self.order = save
        if not probe.fields:
            return None
        return min(f.offset for f in probe.fields)

    def resolve_overlaps(self, st):
        """Unions: keep the finest-grained naming, record the rest as aliases.

        Fields are ordered by offset then by width, so where several names
        describe the same bytes (`CurState`/`CurState_CurAction`/
        `CurStateActionPhaseAndPhaseInitialized` all start at 0x8) the narrowest
        wins and the wider ones become documented aliases.  That maximises the
        number of distinct byte ranges the decompiler can name.
        """
        # Scalars before sub-structs at the same offset.  A sub-struct that
        # lands on top of the parent's own fields is not a member of it: the
        # battle objects' `LinkedList` block resolves to offset 0 because the
        # macro re-bases the origin for it, but in memory the allocator puts
        # that header *before* the address every BattleObject* holds
        # (bn6f.map: eT1BattleObject0_LinkedList_Prev == eT1BattleObject0 - 0x10).
        # Losing the overlap test demotes it to an alias, which is right.
        ordered = sorted(
            [f for f in st.fields if f.size > 0],
            key=lambda f: (f.offset, 1 if f.note.startswith("sub-struct") else 0,
                           f.size, f.order))
        kept = []
        occupied = []
        for f in ordered:
            lo, hi = f.offset, f.offset + f.size
            if hi > st.size and st.size:
                f.alias_of = "beyond struct size"
                st.aliases.append(f)
                continue
            clash = next((k for k in occupied
                          if not (hi <= k.offset or lo >= k.offset + k.size)),
                         None)
            if clash is not None:
                f.alias_of = ("%s (separate block, re-based origin)" % clash.name
                              if f.note.startswith("sub-struct") else clash.name)
                st.aliases.append(f)
                continue
            kept.append(f)
            occupied.append(f)
        # Zero-width markers (`u0 Size`, `u0 End`) name a boundary, not a
        # field, and were already filtered out of `ordered` above.
        st.fields = kept


def parse_int(text):
    text = text.strip()
    if not text:
        return 0
    try:
        return int(text, 0)
    except ValueError:
        return 0


# ---------------------------------------------------------------------------
# Pointer targets: what a `ptr` field actually points at, proved by the asm
# ---------------------------------------------------------------------------

LOAD_RE = re.compile(
    r"^\s*ldr\s+(r\d+)\s*,\s*\[(r\d+)\s*,\s*#?(o[A-Za-z]\w*?)_(\w+)\]")
USE_RE = re.compile(r"\[(r\d+)\s*,\s*#?(o[A-Za-z]\w*?)_(\w+)\]")
WRITE_RE = re.compile(r"^\s*(?:ldr|ldrb|ldrh|ldrsb|ldrsh|mov|movs|add|adds|sub|"
                      r"subs|lsl|lsr|asr|and|orr|eor|neg|mul|mvn|bic)\s+(r\d+)\s*,")
CALL_RE = re.compile(r"^\s*(?:bl|blx)\b")


def read_function_extents(symbols_tsv, ref):
    """[(name, abspath, start_line, end_line)] for every declared function.

    tools/ghidra/bnsyms.py already worked out where each of the 13,646
    functions begins and ends in the `.s` files -- including the ~10.6k that are
    `thumb_local_start` bodies with no name of their own on the marker line.
    Re-deriving that here would be a second, worse copy of it.
    """
    out = []
    with open(symbols_tsv, errors="replace") as f:
        for line in f:
            if line.startswith("#"):
                continue
            col = line.rstrip("\n").split("\t")
            if len(col) < 8 or col[0] != "F" or not col[5]:
                continue
            path = col[5]
            if not os.path.isabs(path):
                # symbols.tsv records paths relative to the repo root, as
                # `reference/bn6f/asm/asm31.s`.
                tail = path.split("reference/bn6f/", 1)[-1]
                path = os.path.join(ref, tail)
            try:
                start, end = int(col[6]), int(col[7])
            except ValueError:
                continue
            if start and end and os.path.isfile(path):
                out.append((col[1], path, start, end))
    return out


_LINE_CACHE = {}


def file_lines(path):
    if path not in _LINE_CACHE:
        with open(path, errors="replace") as f:
            _LINE_CACHE[path] = f.readlines()
    return _LINE_CACHE[path]


ADDR_OF_RE = re.compile(
    r"^\s*add\s+(r\d+)\s*,\s*(?:r\d+\s*,\s*)?#?(o[A-Za-z]\w*?)_(\w+)\s*$")


def scan_pointer_targets(funcs, struct_labels):
    """Vote on `<Struct>.<Field>` -> pointed-at struct from real code.

    The pattern is unambiguous in this game's Thumb:

        ldr r4, [r5,#oBattleObject_AIDataPtr]
        ldrb r0, [r4,#oAIData_ActorType]

    The second line can only be read one way: whatever `oBattleObject_AIDataPtr`
    holds is an `AIData *`.  Votes are collected function by function (the held
    register is forgotten at every function boundary, at every reassignment of
    that register, and for r0-r3 at every call) and a target is accepted only
    when nothing votes against it.
    """
    votes = collections.defaultdict(collections.Counter)
    inner = collections.defaultdict(collections.Counter)
    for name, path, start, end in funcs:
        lines = file_lines(path)
        held = {}
        at = {}
        for raw in lines[start - 1:end]:
            code = strip_comment(raw)[0]
            if not code.strip():
                continue
            for reg, label, field in USE_RE.findall(code):
                src = held.get(reg)
                if src and label in struct_labels:
                    votes[src][label] += 1
                src = at.get(reg)
                if src and label in struct_labels:
                    inner[src][label] += 1
            if CALL_RE.match(code):
                for r in ("r0", "r1", "r2", "r3", "r12", "lr"):
                    held.pop(r, None)
                    at.pop(r, None)
            m = LOAD_RE.match(code)
            if m:
                dst, _, label, field = m.groups()
                held[dst] = (label, field)
                at.pop(dst, None)
                continue
            # `add r7, #oAIData_AttackVars` steps a pointer to a field that is
            # itself a struct; whatever offsets the next access uses name its
            # type.  The disassembly wrote both symbols, so neither end of this
            # inference is invented here.
            m = ADDR_OF_RE.match(code)
            if m and m.group(2) in struct_labels:
                at[m.group(1)] = (m.group(2), m.group(3))
                held.pop(m.group(1), None)
                continue
            w = WRITE_RE.match(code)
            if w:
                held.pop(w.group(1), None)
                at.pop(w.group(1), None)
    out = {}
    for (label, field), counter in votes.items():
        best = pick_struct(counter)
        total = sum(counter.values())
        if best is not None and total >= 2:
            out[(label, field)] = (best, total)
    embedded = {}
    for (label, field), counter in inner.items():
        best = pick_struct(counter)
        total = sum(counter.values())
        if best is not None and total >= 2:
            embedded[(label, field)] = (best, total)
    return out, embedded


# ---------------------------------------------------------------------------
# Global instances: `ewram.s` says what lives where, `bn6f.map` says at what
# ---------------------------------------------------------------------------

INSTANCE_RE = re.compile(r"^\s*([a-zA-Z_]\w*_struct)\s+([A-Za-z_]\w*)\s*(?://.*)?$")
MAP_RE = re.compile(r"^\s+(0x[0-9a-f]{8,16})\s+([A-Za-z_]\w*)\s*$")


ROM_ARRAY_LABEL_RE = re.compile(r"^([A-Za-z_]\w*)::")
ROM_ARRAY_ENTRY_RE = re.compile(r"^\s*([a-zA-Z_]\w*_struct)\s*(?:\[|$)")


def scan_rom_struct_arrays(ref, macro_to_label, rom_macros):
    """ROM tables written as repeated struct literals, e.g. data/ChipDataArr.s:

        ChipDataArr_8021DA8::
            chip_data_struct [ codes: 0xFFFFFFFF, ... ]
            chip_data_struct [ ... ]            x411

    That is an array of ChipData at the label, and the label's address is in
    bn6f.map like any other.
    """
    out = []
    files = ["rom.s"]
    datadir = os.path.join(ref, "data")
    if os.path.isdir(datadir):
        files += [os.path.join("data", fn) for fn in sorted(os.listdir(datadir))
                  if fn.endswith(".s")]
    for rel in files:
        path = os.path.join(ref, rel)
        if not os.path.isfile(path):
            continue
        label = None
        label_line = 0
        macro = None
        count = 0
        with open(path, errors="replace") as f:
            for n, raw in enumerate(f, 1):
                m = ROM_ARRAY_LABEL_RE.match(raw)
                if m:
                    if macro and count:
                        out.append((label, macro, count, "%s:%d" % (rel, label_line)))
                    label, label_line, macro, count = m.group(1), n, None, 0
                    continue
                m = ROM_ARRAY_ENTRY_RE.match(raw)
                if m and m.group(1) in rom_macros and label:
                    if macro in (None, m.group(1)):
                        macro, count = m.group(1), count + 1
        if macro and count:
            out.append((label, macro, count, "%s:%d" % (rel, label_line)))
    return [(lab, macro_to_label.get(mac), n, where)
            for lab, mac, n, where in out if macro_to_label.get(mac)]


def scan_globals(ref, macro_to_label):
    addrs = {}
    mapfile = os.path.join(ref, "bn6f.map")
    if os.path.isfile(mapfile):
        with open(mapfile, errors="replace") as f:
            for raw in f:
                m = MAP_RE.match(raw)
                if m:
                    addrs.setdefault(m.group(2), int(m.group(1), 16))
    out = []
    for rel in ("ewram.s", "iwram.s", "iwram_data.s", "vram.s", "data.s", "rom.s"):
        path = os.path.join(ref, rel)
        if not os.path.isfile(path):
            continue
        with open(path, errors="replace") as f:
            for n, raw in enumerate(f, 1):
                m = INSTANCE_RE.match(raw)
                if not m:
                    continue
                macro, label = m.group(1), m.group(2)
                canon = macro_to_label.get(macro)
                if canon is None:
                    continue
                addr = addrs.get(label)
                if addr is None:
                    continue
                out.append((label, cname_for(canon), addr, 1, "%s:%d" % (rel, n)))
    return out, addrs


# ---------------------------------------------------------------------------
# Register parameters: which function takes what in which callee-saved register
# ---------------------------------------------------------------------------

FUNC_START_RE = re.compile(r"^\s*(?:thumb|arm)_func_start\s+(\w+)")
FUNC_END_RE = re.compile(r"^\s*(?:thumb|arm)_func_end\s+(\w+)")
LOCAL_LABEL_RE = re.compile(r"^([A-Za-z_]\w*):")
SIG_RE = re.compile(r"^([A-Za-z_]\w*):\s*//\s*\((.*?)\)\s*->")
JUMPTAB_SIG_RE = re.compile(
    r"^\s*\.word\s+([A-Za-z_]\w*)\s*\+\s*1\s*//\s*\((.*?)\)\s*->")
SIG_ARG_RE = re.compile(
    r"(?:\*\s*(?:const\s+|mut\s+)?)([A-Za-z_]\w*)\s*\$?(r\d+)|"
    r"\*(?:const |mut )?\s*([A-Za-z_]\w*)\s*@(r\d+)")
# Callee-saved registers: the ones no ARM convention passes arguments in, and
# so exactly the ones that surface as `unaff_rN` in the decompiler's output.
CALLEE_SAVED = ("r4", "r5", "r6", "r7", "r8", "r9", "r10", "r11")
# Anything that puts a new value in a register.  `push` does not; `pop` and the
# load-multiples do.
POP_RE = re.compile(r"^\s*(?:pop|ldm[a-z]*)\b[^{]*\{([^}]*)\}")


def scan_register_params(funcs, struct_labels, struct_cnames):
    """Per function, which callee-saved register holds a pointer to which struct.

    Two independent sources, kept separate so the report can say which one
    carried a given function:

      operand   the function's own instructions index a register by a struct's
                field offsets (`[r5,#oBattleObject_CurAction]`).  A wrong struct
                name there would not assemble, so this is as strong as the build.
      comment   a hand-written signature on the function's label or on the
                jump-table entry that reaches it
                (`// (self: * S2011E30 $r5) -> ()`).

    A function is given a register parameter where the two agree or where only
    one of them speaks.  Where they disagree it is skipped and reported: one of
    the two is wrong and this script cannot tell which.
    """
    by_func = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))
    comments = collections.defaultdict(dict)
    for name, path, start, end in funcs:
        # A register only counts as a parameter while the function has not yet
        # written it.  MettaurDecide_8109FD6 indexes r6 by oAIState offsets, but
        # it built r6 itself two instructions earlier (`mov r6,#0x80; add r6,r6,r4`)
        # -- r6 is a local there, and r5, read on the first instruction and never
        # written, is the parameter.  This is the same condition that makes the
        # decompiler say `unaff_rN` in the first place.
        written = set()
        for raw in file_lines(path)[start - 1:end]:
            m = SIG_RE.match(raw)
            if m:
                for a, r, a2, r2 in SIG_ARG_RE.findall(m.group(2)):
                    cn, reg = (a or a2), (r or r2)
                    if reg in CALLEE_SAVED and cn in struct_cnames:
                        comments[m.group(1)][reg] = cn
            code = strip_comment(raw)[0]
            for reg, label, field in USE_RE.findall(code):
                if reg in CALLEE_SAVED and label in struct_labels \
                        and reg not in written:
                    by_func[name][reg][label] += 1
            w = WRITE_RE.match(code)
            if w:
                written.add(w.group(1))
            p = POP_RE.match(code)
            if p:
                for reg in p.group(1).split(","):
                    written.add(reg.strip())

    # Jump-table entries annotate the handler they point at, which is often the
    # only place a handler's signature is written down.
    known = {f[0] for f in funcs}
    seen_files = sorted({f[1] for f in funcs})
    for path in seen_files:
        for raw in file_lines(path):
            m = JUMPTAB_SIG_RE.match(raw)
            if m and m.group(1) in known:
                for a, r, a2, r2 in SIG_ARG_RE.findall(m.group(2)):
                    cn, reg = (a or a2), (r or r2)
                    if reg in CALLEE_SAVED and cn in struct_cnames:
                        comments[m.group(1)].setdefault(reg, cn)

    rows = []
    conflicts = []
    names = set(by_func) | set(comments)
    for func in sorted(names):
        regs = set(by_func.get(func, {})) | set(comments.get(func, {}))
        for reg in sorted(regs):
            counter = by_func.get(func, {}).get(reg)
            operand = None
            if counter:
                operand = pick_struct(counter)
                if operand is None:
                    conflicts.append((func, reg, "operand",
                                      ",".join("%s=%d" % kv for kv in
                                               counter.most_common())))
                    continue
            comment = comments.get(func, {}).get(reg)
            if operand and comment:
                if cname_for(operand) != comment:
                    conflicts.append((func, reg, "operand-vs-comment",
                                      "%s vs %s" % (cname_for(operand), comment)))
                    continue
                src, cname, n = "operand+comment", comment, sum(counter.values())
            elif operand:
                src, cname, n = "operand", cname_for(operand), sum(counter.values())
            else:
                src, cname, n = "comment", comment, 0
            rows.append((func, reg, cname, src, n))

    direct = collections.defaultdict(dict)
    for func, reg, cname, _src, _n in rows:
        direct[func][reg] = cname
    added, more = propagate_register_params(funcs, direct)
    for (func, reg), (cname, via) in sorted(added.items()):
        rows.append((func, reg, cname, "callthrough:" + via, 0))
    conflicts.extend(more)
    rows.sort(key=lambda r: (r[0], r[1]))
    return rows, conflicts


BL_RE = re.compile(r"^\s*bl\s+([A-Za-z_]\w*)\s*$")


def propagate_register_params(funcs, direct, max_rounds=12):
    """Carry a register parameter back to the callers that must be supplying it.

    If `MettaurAttackExec_8109DD2` needs a BattleObject in r5, then every
    routine that calls it without first writing r5 is handing over its own r5 --
    so that caller takes one too.  r4-r11 survive a call by definition, so the
    only thing that can break the chain is the caller writing the register
    itself, which is checked at each call site.

    This is what reaches the routines that never touch a field themselves: a
    dispatcher that only does `bl`, or a wrapper that forwards.  Without it half
    the call graph keeps saying `unaff_r5` while its callees say `self`.

    Two types can meet on one register.  Where one of them is ObjectHeader the
    answer is the other, because ObjectHeader is literally the first four bytes
    of every object struct and a helper that only reads `Flags` is still being
    handed the whole object.  Where they are genuinely different structs the
    register is dropped for that function and the disagreement reported: one of
    the two call paths is not what it looks like, and guessing between them
    would put a wrong field name in the C.
    """
    known = {func: dict(regs) for func, regs in direct.items()}
    from_direct = {(f, r) for f, regs in direct.items() for r in regs}
    poisoned = set()
    calls = {}
    for name, path, start, end in funcs:
        written = set()
        sites = []
        for raw in file_lines(path)[start - 1:end]:
            code = strip_comment(raw)[0]
            m = BL_RE.match(code)
            if m:
                sites.append((m.group(1), frozenset(
                    r for r in CALLEE_SAVED if r not in written)))
                continue
            w = WRITE_RE.match(code)
            if w:
                written.add(w.group(1))
            pm = POP_RE.match(code)
            if pm:
                for reg in pm.group(1).split(","):
                    written.add(reg.strip())
        if sites:
            calls[name] = sites

    added = {}
    conflicts = set()
    for _round in range(max_rounds):
        changed = 0
        for caller, sites in calls.items():
            for callee, live in sites:
                for reg, cname in known.get(callee, {}).items():
                    if reg not in live or (caller, reg) in poisoned:
                        continue
                    have = known.get(caller, {}).get(reg)
                    if have == cname:
                        continue
                    if have is None:
                        known.setdefault(caller, {})[reg] = cname
                        added[(caller, reg)] = (cname, callee)
                        changed += 1
                        continue
                    if "ObjectHeader" in (have, cname):
                        if have == "ObjectHeader" and (caller, reg) not in from_direct:
                            known[caller][reg] = cname
                            added[(caller, reg)] = (cname, callee)
                            changed += 1
                        continue
                    if (caller, reg) in from_direct:
                        conflicts.add((caller, reg, "callthrough-vs-operand",
                                       "%s (own) vs %s (via %s)"
                                       % (have, cname, callee)))
                        continue
                    conflicts.add((caller, reg, "callthrough",
                                   "%s vs %s (via %s)" % (have, cname, callee)))
                    poisoned.add((caller, reg))
                    known[caller].pop(reg, None)
                    added.pop((caller, reg), None)
                    changed += 1
        if not changed:
            break
    for key in list(added):
        if key in poisoned:
            added.pop(key)
    return added, sorted(conflicts)


# ObjectHeader is the first four bytes of every object struct, so a function
# that indexes r5 by both `oObjectHeader_*` and `oBattleObject_*` is reading one
# object, not two.  The larger type subsumes the header.
SUBSUMED = {"oObjectHeader"}


def pick_struct(counter):
    labels = set(counter)
    real = labels - SUBSUMED
    if len(real) == 1:
        return real.pop()
    if not real and labels:
        return labels.pop()
    return None


# ---------------------------------------------------------------------------
# Emit
# ---------------------------------------------------------------------------

PREAMBLE = """/* Generated by tools/ghidra/bntypes.py from reference/bn6f -- do not edit.
 *
 * Every struct below is a transcription of a GNU-as macro in
 * reference/bn6f/include/structs or include/rom_structs.  Field offsets are not
 * re-derived here: they are the absolute symbols the disassembly's own
 * assembler emits for that macro, so a field at 0x58 here is at 0x58 in the
 * cartridge.  Padding is explicit and named for the byte it starts at.
 *
 * Union members are flattened: where several names describe the same bytes the
 * narrowest naming is kept and the wider ones are listed as `alias` comments,
 * which is what makes the decompiler able to name the most distinct fields.
 */

typedef unsigned char u8;
typedef signed char s8;
typedef unsigned short u16;
typedef signed short s16;
typedef unsigned int u32;
typedef signed int s32;
"""


def topo_order(order):
    """Define a struct before any struct that embeds it by value.

    Pointers are fine with a forward declaration; a by-value member is not, and
    Ghidra's C parser is as strict about that as a compiler.
    """
    by_name = {st.cname: st for st in order}
    out, state = [], {}

    def visit(st):
        mark = state.get(st.cname)
        if mark == 2:
            return
        if mark == 1:                       # a cycle cannot happen by value
            return
        state[st.cname] = 1
        for f in st.fields:
            dep = by_name.get(f.base)
            if dep is not None and dep is not st:
                visit(dep)
        state[st.cname] = 2
        out.append(st)

    for st in order:
        visit(st)
    return out


def padding(offset, size):
    """Filler for a stretch the .inc leaves unnamed, in the widest aligned unit.

    Granularity matters to the decompiler, not just to the eye: a four-byte
    store into a `u8 _pad[32]` comes out as four separate byte assignments,
    while the same store into a `u32 _pad[8]` stays one.  So pad in words where
    the offset and the length allow it, halfwords where they allow that, bytes
    otherwise.
    """
    for width, ctype in ((4, "u32"), (2, "u16")):
        if offset % width == 0 and size % width == 0:
            n = size // width
            return "%s _pad_%02x[%d];" % (ctype, offset, n) if n > 1 \
                else "%s _pad_%02x;" % (ctype, offset)
    return "u8 _pad_%02x[%d];" % (offset, size) if size > 1 \
        else "u8 _pad_%02x;" % offset


def emit_header(order, ptr_targets, path):
    lines = [PREAMBLE, ""]
    lines.append("/* forward declarations: the structs point at each other */")
    for st in order:
        lines.append("struct %s;" % st.cname)
    lines.append("")
    for st in order:
        lines.append("/* %s -- %s:%d, macro %s, %d bytes%s */"
                     % (st.cname, st.path, st.line, st.macro, st.size,
                        (", " + st.note) if st.note else ""))
        lines.append("struct %s {" % st.cname)
        pos = 0
        for f in st.fields:
            if f.offset > pos:
                lines.append("    " + padding(pos, f.offset - pos))
                pos = f.offset
            elif f.offset < pos:
                continue
            lines.append("    %s" % declare(st, f, ptr_targets))
            pos = f.offset + f.size
        if st.size > pos:
            lines.append("    " + padding(pos, st.size - pos))
        lines.append("};")
        for a in sorted(st.aliases, key=lambda x: (x.offset, x.name)):
            lines.append("/* alias: %s.%s at 0x%x (%d bytes) names the same "
                         "bytes as %s */" % (st.cname, a.name, a.offset, a.size,
                                             a.alias_of))
        lines.append("")
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")


def declare(st, f, ptr_targets):
    comment = "  /* 0x%02x */" % f.offset
    if f.base in ("u8", "u16", "u32", "s8", "s16", "s32", "bool8"):
        width = {"u8": 1, "s8": 1, "bool8": 1, "u16": 2, "s16": 2,
                 "u32": 4, "s32": 4}[f.base]
        ctype = CTYPE[f.base]
        if f.size > width:
            if f.size % width:
                return "u8 %s[%d];%s" % (f.name, f.size, comment)
            return "%s %s[%d];%s" % (ctype, f.name, f.size // width, comment)
        return "%s %s;%s" % (ctype, f.name, comment)
    if f.base == "ptr":
        target = ptr_targets.get((st.label, f.name)) \
            or ptr_targets.get((st.macro, f.name))
        if target:
            return "struct %s *%s;%s /* %d loads prove the target type */" \
                % (target[0], f.name, comment, target[1])
        return "void *%s;%s" % (f.name, comment)
    if f.base == "u8[]":
        return "u8 %s[%d];%s" % (f.name, max(f.size, 1), comment)
    # A nested struct.
    return "struct %s %s;%s" % (f.base, f.name, comment)


def emit_manifest(order, path, missing, notes):
    with open(path, "w") as f:
        f.write("# generated by tools/ghidra/bntypes.py -- the struct catalogue\n")
        f.write("# STRUCT\tcname\tinc_file:line\tmacro\tlabel\tsize\tfields\taliases\n")
        f.write("# FIELD\tcname\tfield\toffset\tsize\tbase\n")
        f.write("# ALIAS\tcname\tfield\toffset\tsize\tbase\tsame_bytes_as\n")
        for st in order:
            f.write("STRUCT\t%s\t%s:%d\t%s\t%s\t0x%x\t%d\t%d\n"
                    % (st.cname, st.path, st.line, st.macro, st.label, st.size,
                       len(st.fields), len(st.aliases)))
        for st in order:
            for x in st.fields:
                f.write("FIELD\t%s\t%s\t0x%x\t%d\t%s\n"
                        % (st.cname, x.name, x.offset, x.size, x.base))
            for x in st.aliases:
                f.write("ALIAS\t%s\t%s\t0x%x\t%d\t%s\t%s\n"
                        % (st.cname, x.name, x.offset, x.size, x.base,
                           x.alias_of))
        for sym in sorted(set(missing)):
            f.write("UNRESOLVED\t%s\n" % sym)
        for note in notes:
            f.write("UNMODELLED\t%s\n" % note)


def verify_layout(order, header_path, workdir):
    """Compile the header against the offsets it claims.

    Every field and every struct size is asserted with `_Static_assert`, so a
    transcription that drifts by one byte fails here rather than silently
    misnaming half a routine's C.  The compile targets the same ABI as the
    cartridge (arm-none-eabi, 4-byte alignment), because that is the alignment
    the layout has to survive.
    """
    src = ["#include <stddef.h>", '#include "%s"' % os.path.basename(header_path)]
    n = 0
    for st in order:
        src.append('_Static_assert(sizeof(struct %s) == %d, "size %s");'
                   % (st.cname, st.size, st.cname))
        n += 1
        for f in st.fields:
            src.append('_Static_assert(offsetof(struct %s, %s) == %d, "%s.%s");'
                       % (st.cname, f.name, f.offset, st.cname, f.name))
            n += 1
    path = os.path.join(workdir, "bn_types_check.c")
    with open(path, "w") as fh:
        fh.write("\n".join(src) + "\n")
    r = subprocess.run(
        ["arm-none-eabi-gcc", "-std=c11", "-fsyntax-only", "-I", workdir, path],
        capture_output=True, text=True)
    return n, r.returncode, r.stderr


# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ref", required=True, help="reference/bn6f checkout")
    ap.add_argument("--out-dir", required=True, help="where to write the tables")
    ap.add_argument("--symbols", required=True,
                    help="symbols.tsv from tools/ghidra/bnsyms.py -- it carries "
                         "the file:line extent of every function, including the "
                         "10.6k thumb_local_start bodies")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    ref = os.path.abspath(args.ref)
    out = os.path.abspath(args.out_dir)
    os.makedirs(out, exist_ok=True)

    def say(*a):
        if not args.quiet:
            print("bntypes:", *a)

    offsets = assemble_offsets(ref, out)
    say("assembled the struct macros: %d field offsets" % len(offsets))

    macros, defs, equivs = parse_incs(ref)
    say("parsed %d macros and %d struct definitions from the .inc files"
        % (len(macros), len(defs)))

    # Re-read the declared type keyword for every field item, keyed by source
    # position, so expansion knows a width without guessing.
    decl_by_pos = {}
    for mac in macros.values():
        path = os.path.join(ref, mac.path)
        with open(path, errors="replace") as f:
            lines = f.readlines()
        for item in mac.items:
            if item.kind == "field":
                code = strip_comment(lines[item.line - 1])[0].strip()
                decl_by_pos[(mac.path, item.line)] = code.split()[0]

    funcs = read_function_extents(os.path.abspath(args.symbols), ref)
    say("%d functions with a known extent in the .s files" % len(funcs))

    def_labels = {label for _m, label, _p, _l, _e in defs}
    ptr_targets_raw, embedded_raw = scan_pointer_targets(funcs, def_labels)
    say("%d pointer fields and %d embedded sub-structs have their type proved "
        "by the asm" % (len(ptr_targets_raw), len(embedded_raw)))

    builder = Builder(macros, offsets, def_labels, embedded_raw, decl_by_pos)
    for macro_name, label, path, line, extra in defs:
        builder.macro_to_label.setdefault(macro_name, label)
    # ewram.s instantiates the battle objects through one-line wrappers
    # (`t1_battle_object_struct` -> `battle_object_struct \label, ..., 0x2c`).
    # Follow the wrapper to the flavour it names, or those 96 instances would
    # have no type.
    for mac in macros.values():
        calls = [i for i in mac.items if i.kind == "call"]
        if len(calls) != 1 or mac.name in builder.macro_to_label:
            continue
        callee = calls[0]
        tail = [a for a in callee.arg[1:] if "struct_entry" not in a
                and "struct_start_address" not in a]
        for m2, label2, _p, _l, extra2 in defs:
            if m2 != callee.name:
                continue
            want = list(extra2.values())
            if [x.strip() for x in tail] == [x.strip() for x in want]:
                builder.macro_to_label[mac.name] = label2
                break

    order = []
    unmodelled = []
    for macro_name, label, path, line, extra in defs:
        if macro_name not in macros:
            say("WARNING no macro %s for %s" % (macro_name, label))
            continue
        st = builder.build(macro_name, label, path, line, extra)
        if not st.fields:
            # Either nothing includes the .inc, so the build never assembles it
            # and there are no offsets to be had, or the macro is written in a
            # form this converter does not read.  Say which rather than emit a
            # struct whose layout came from nowhere.
            has_syms = any(k.startswith(label + "_") for k in offsets)
            unmodelled.append(
                "%s\t%s:%d\t%s" % (label, path, line,
                    "assembled, but no field of it was recognised in the macro"
                    if has_syms else
                    "no assembled offsets -- nothing in the build includes " + path))
            continue
        builder.structs[label] = st
        order.append(st)
    say("built %d structs, %d fields, %d union aliases"
        % (len(order), sum(len(s.fields) for s in order),
           sum(len(s.aliases) for s in order)))
    if builder.missing:
        say("%d field symbols had no assembled offset (listed in the manifest)"
            % len(set(builder.missing)))

    struct_labels = set(builder.structs)
    struct_cnames = {s.cname for s in order}

    ptr_targets = {}
    for (label, field), (target, n) in ptr_targets_raw.items():
        if target not in builder.structs:
            continue
        if label in builder.structs:
            ptr_targets[(label, field)] = (cname_for(target), n)
            ptr_targets.setdefault((builder.structs[label].macro, field),
                                   (cname_for(target), n))

    order = topo_order(order)
    emit_header(order, ptr_targets, os.path.join(out, "bn_types.h"))

    # .equiv-only layouts have no macro, so they are reported rather than
    # modelled: saying so is better than inventing a struct for them.
    equiv_groups = collections.Counter()
    for sym, rel, line, comment in equivs:
        equiv_groups["%s (%s:%d)" % (sym, rel, line)] += 1
    emit_manifest(order, os.path.join(out, "bn_types.tsv"),
                  builder.missing, unmodelled + sorted(equiv_groups))

    checks, rc, err = verify_layout(order, os.path.join(out, "bn_types.h"), out)
    if rc != 0:
        say("LAYOUT CHECK FAILED -- the emitted C does not match the offsets "
            "the assembler produced:")
        say(err.strip()[:4000])
        sys.exit(1)
    say("layout check: %d offset and size assertions hold when the header is "
        "compiled for arm-none-eabi" % checks)

    globals_, addrs = scan_globals(ref, builder.macro_to_label)
    rom_macros = {m.name for m in macros.values() if m.is_rom}
    for label, canon, count, where in scan_rom_struct_arrays(
            ref, builder.macro_to_label, rom_macros):
        addr = addrs.get(label)
        if addr is not None and canon in builder.structs:
            globals_.append((label, cname_for(canon), addr, count, where))
    with open(os.path.join(out, "bn_globals.tsv"), "w") as f:
        f.write("# label\tstruct\taddress\tcount\tdeclared_at\n")
        for label, cname, addr, count, where in globals_:
            f.write("%s\t%s\t%08x\t%d\t%s\n" % (label, cname, addr, count, where))
    say("%d global struct instances located by name and address (%d of them "
        "arrays)" % (len(globals_), sum(1 for g in globals_ if g[3] > 1)))

    rows, conflicts = scan_register_params(funcs, struct_labels, struct_cnames)
    with open(os.path.join(out, "bn_protos.tsv"), "w") as f:
        f.write("# function\tregister\tstruct\tevidence\trefs\n")
        for func, reg, cname, src, n in rows:
            f.write("%s\t%s\t%s\t%s\t%d\n" % (func, reg, cname, src, n))
        for func, reg, why, detail in conflicts:
            f.write("# CONFLICT\t%s\t%s\t%s\t%s\n" % (func, reg, why, detail))
    per_reg = collections.Counter(r[1] for r in rows)
    say("%d register parameters over %d functions: %s"
        % (len(rows), len({r[0] for r in rows}),
           ", ".join("%s=%d" % kv for kv in sorted(per_reg.items()))))
    if conflicts:
        say("%d register/function pairs skipped as contradictory "
            "(listed in bn_protos.tsv)" % len(conflicts))
    say("wrote bn_types.h, bn_types.tsv, bn_globals.tsv, bn_protos.tsv to " + out)


if __name__ == "__main__":
    main()
