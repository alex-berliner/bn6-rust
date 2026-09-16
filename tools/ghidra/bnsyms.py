#!/usr/bin/env python3
"""Index the hand-made bn6f disassembly (reference/bn6f) into a symbol table.

Nothing in a raw GBA image tells a disassembler where the functions are or
whether they are Thumb or ARM, so the disassembly submodule is the authority for
both.  This module collects that authority into one TSV for the Ghidra scripts
and for ``tools/csrc.py``.

Where the addresses come from
-----------------------------
``reference/bn6f/bn6f.elf``, the submodule's build output, when present.  It is
complete (about 216k symbols, file-local ones included) and exact, and it can be
*verified*: the ROM it produced, ``reference/bn6f/bn6f.gba``, is byte-identical
to the real cartridge image, so every address in it is the real address.  In an
ARM ELF a Thumb function carries bit 0 set in ``st_value``, and the ``$a``/``$t``
mapping symbols delimit the ARM and Thumb stretches of each code section -- both
are exactly what Ghidra's ``TMode`` context register needs.

Fallback, when the submodule has not been built (``--no-elf``, or no .elf file):
``bn6f.map`` for global addresses, plus the address each name carries as a
7-hex-digit suffix (``sub_801FE00``, ``ForMettaur_8109EF4``), a convention
``docs/renames.md`` deliberately preserves.  That path reaches fewer symbols and
is reported as degraded.

Where the Thumb/ARM markers and the file:line come from
-------------------------------------------------------
``*.s``, always -- the ELF has no line information.  ``include/macros/function.inc``
defines the markers:

    thumb_func_start NAME   -- global Thumb function, NAME: on the next line
    thumb_local_start       -- file-local Thumb function, name is the next label
    arm_func_start NAME     -- global ARM function
    arm_local_start         -- file-local ARM function
    thumb_func_end NAME     -- closes either kind, and is what gives both kinds
                               their ELF `function` type

Locals outnumber globals 4:1 and are absent from the linker map, so a map-only
index would miss most of the game's code.

Output (``--out``) is a TSV:

    kind  name  addr  mode  size  asm_file  start_line  end_line

    kind  F = function, D = label/data, M = ARM/Thumb mapping range
    mode  thumb | arm for F and M, data for a `$d` M row, - for D
    size  ELF st_size, or 0 when unknown

``--out-mem`` writes the GBA memory map the Ghidra pre-script builds:

    kind  name  addr  size  src  perms

    ROM   a split of the loaded cartridge image (already has the bytes)
    COPY  an initialised block filled from ROM address `src` -- this is how the
          iwram_text overlay, which the cartridge stores at 0x081D6000 but the
          game runs at 0x03005B00, becomes decompilable
    BSS   an uninitialised block (the hardware regions)
"""

import bisect
import os
import re
import struct
import sys

# GBA address space.  Used to reject implausible name-derived addresses and to
# classify symbols for the summary.
REGIONS = (
    (0x00000000, 0x00004000, "bios"),
    (0x02000000, 0x02040000, "ewram"),
    (0x03000000, 0x03008000, "iwram"),
    (0x04000000, 0x04000400, "io"),
    (0x05000000, 0x05000400, "palette"),
    (0x06000000, 0x06018000, "vram"),
    (0x07000000, 0x07000400, "oam"),
    (0x08000000, 0x08800000, "rom"),
)

IDENT = r"[A-Za-z_][A-Za-z0-9_.$]*"
# `                0x08062938                byte_8062938`
MAP_SYM = re.compile(r"^\s+0x([0-9a-fA-F]{8})\s+(%s)\s*$" % IDENT)
FUNC_START = re.compile(r"^\s*(thumb|arm)_func_start\s+(%s)" % IDENT)
LOCAL_START = re.compile(r"^\s*(thumb|arm)_local_start\b")
FUNC_END = re.compile(r"^\s*(thumb|arm)_func_end\s+(%s)" % IDENT)
LABEL = re.compile(r"^(%s):" % IDENT)
NAME_ADDR = re.compile(r"_0?([0-9A-Fa-f]{7})$")

STT_NOTYPE, STT_OBJECT, STT_FUNC, STT_SECTION, STT_FILE = 0, 1, 2, 3, 4


def repo_root():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", ".."))


def default_ref_dir():
    return os.path.join(repo_root(), "reference", "bn6f")


def display_path(path):
    """Repo-relative when the file is inside the repo, else absolute."""
    path = os.path.abspath(path)
    root = repo_root() + os.sep
    return path[len(root):] if path.startswith(root) else path


def region_of(addr):
    for lo, hi, name in REGIONS:
        if lo <= addr < hi:
            return name
    return "?"


def addr_from_name(name):
    """0x08109EF4 out of ForMettaur_8109EF4, or None when the suffix is not a
    plausible GBA address."""
    m = NAME_ADDR.search(name)
    if not m:
        return None
    addr = int(m.group(1), 16)
    return addr if region_of(addr) != "?" else None


# --------------------------------------------------------------------------
# ELF32 little-endian symbol table, read directly so no binutils is required.
# --------------------------------------------------------------------------

SHN_UNDEF, SHN_LORESERVE = 0, 0xFF00


def read_elf_symbols(path):
    """(name, value, size, sym_type, bind) for every symbol defined in a real
    section.  SHN_ABS symbols are skipped: this disassembly has some 62k of them
    and they are `.equ` constants -- struct field offsets, I/O register numbers --
    not addresses, so importing them as labels would be wrong."""
    with open(path, "rb") as fh:
        data = fh.read()
    if data[:4] != b"\x7fELF" or data[4] != 1 or data[5] != 1:
        raise ValueError("%s is not a little-endian ELF32 file" % path)

    e_shoff, = struct.unpack_from("<I", data, 0x20)
    e_shentsize, e_shnum = struct.unpack_from("<HH", data, 0x2E)

    sections = []
    for i in range(e_shnum):
        off = e_shoff + i * e_shentsize
        # sh_name sh_type sh_flags sh_addr sh_offset sh_size sh_link sh_info
        # sh_addralign sh_entsize
        fields = struct.unpack_from("<10I", data, off)
        sections.append(fields)

    out = []
    for sh_name, sh_type, _f, _a, sh_offset, sh_size, sh_link, _i, _al, sh_entsize in sections:
        if sh_type != 2 or sh_entsize < 16:          # SHT_SYMTAB
            continue
        str_off = sections[sh_link][4]
        str_size = sections[sh_link][5]
        strtab = data[str_off:str_off + str_size]
        for j in range(sh_size // sh_entsize):
            so = sh_offset + j * sh_entsize
            st_name, st_value, st_size, st_info, _other, st_shndx = \
                struct.unpack_from("<IIIBBH", data, so)
            if st_name == 0:
                continue
            if st_shndx == SHN_UNDEF or st_shndx >= SHN_LORESERVE:
                continue
            end = strtab.find(b"\0", st_name)
            name = strtab[st_name:end].decode("ascii", "replace")
            out.append((name, st_value, st_size, st_info & 0xF, st_info >> 4))
    return out


# --------------------------------------------------------------------------
# The .s sources: function markers and their file:line.
# --------------------------------------------------------------------------

def asm_sources(ref_dir):
    """Every .s file that can carry symbols.

    Markers are not confined to asm/: data/dat2x.s carries a few functions and
    each maps/<Area>/loader.s carries that area's loaders.  ref_dir/tools is the
    submodule's own build tooling and holds no game source.
    """
    out = []
    for root, dirs, files in os.walk(ref_dir):
        dirs[:] = [d for d in dirs if d not in (".git", "tools", "bin", "build")]
        for fname in sorted(files):
            if fname.endswith(".s"):
                out.append(os.path.join(root, fname))
    out.sort()
    return out


def parse_asm(ref_dir):
    """Scan every .s file.

    Returns (funcs, labels):
      funcs[name]  = (mode, file, start_line, end_line)
      labels[name] = (file, line)
    """
    funcs = {}
    labels = {}

    for full in asm_sources(ref_dir):
        rel = display_path(full)
        pending_mode = None     # set by *_local_start, consumed by the next label
        pending_line = 0
        expect_label = None     # the NAME: line right after *_func_start NAME
        open_name = None
        open_mode = None
        open_line = 0
        lineno = 0

        def close(name, mode, start, end):
            # A name repeated across files keeps its first definition; the
            # disassembly has none, but stay deterministic if it ever does.
            if name not in funcs:
                funcs[name] = (mode, rel, start, end)

        with open(full, "r", errors="replace") as fh:
            for lineno, line in enumerate(fh, 1):
                m = FUNC_START.match(line)
                if m:
                    if open_name is not None:
                        close(open_name, open_mode, open_line, lineno - 1)
                    open_mode, open_name, open_line = m.group(1), m.group(2), lineno
                    expect_label = m.group(2)
                    pending_mode = None
                    continue

                m = LOCAL_START.match(line)
                if m:
                    if open_name is not None:
                        close(open_name, open_mode, open_line, lineno - 1)
                        open_name = None
                    pending_mode, pending_line = m.group(1), lineno
                    expect_label = None
                    continue

                m = FUNC_END.match(line)
                if m:
                    if open_name is not None:
                        close(open_name, open_mode, open_line, lineno)
                        open_name = None
                    expect_label = None
                    continue

                m = LABEL.match(line)
                if m:
                    name = m.group(1)
                    if expect_label is not None:
                        expect_label = None          # declaration of a global func
                    elif pending_mode is not None:
                        open_mode, open_name, open_line = pending_mode, name, pending_line
                        pending_mode = None
                    elif name not in labels:
                        labels[name] = (rel, lineno)

            if open_name is not None:
                close(open_name, open_mode, open_line, lineno)

    return funcs, labels


def parse_map(ref_dir):
    """name -> addr, from bn6f.map.  Empty when the map has not been built."""
    path = os.path.join(ref_dir, "bn6f.map")
    out = {}
    if not os.path.exists(path):
        return out, path
    with open(path, "r", errors="replace") as fh:
        for line in fh:
            m = MAP_SYM.match(line)
            if m:
                # A symbol can be listed twice (definition + archive member) at
                # the same address, so last wins.
                out[m.group(2)] = int(m.group(1), 16)
    return out, path


class Symbol(object):
    __slots__ = ("name", "addr", "kind", "mode", "size",
                 "asm_file", "start_line", "end_line")

    def __init__(self, name, addr, kind, mode, size, asm_file, start_line, end_line):
        self.name = name
        self.addr = addr
        self.kind = kind
        self.mode = mode
        self.size = size
        self.asm_file = asm_file
        self.start_line = start_line
        self.end_line = end_line

    @property
    def region(self):
        return region_of(self.addr)

    def __repr__(self):
        return "<%s %s @%08X>" % (self.kind, self.name, self.addr)


def verify_build(ref_dir, rom_path=None):
    """Is reference/bn6f's own built ROM byte-identical to `rom_path`?

    Returns (verdict, detail).  verdict is True/False/None (could not check).
    """
    built = os.path.join(ref_dir, "bn6f.gba")
    if not os.path.exists(built):
        return None, "reference/bn6f/bn6f.gba not built"
    if not rom_path or not os.path.exists(rom_path):
        return None, "no ROM given to compare against"
    import hashlib

    def sha1(p):
        h = hashlib.sha1()
        with open(p, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()

    a, b = sha1(built), sha1(rom_path)
    if a == b:
        return True, "bn6f.gba == %s (sha1 %s)" % (os.path.basename(rom_path), a)
    return False, "bn6f.gba sha1 %s != %s sha1 %s" % (a, os.path.basename(rom_path), b)


def load(ref_dir=None, use_elf=True, rom_path=None):
    """Return (symbols, stats).  symbols is address-sorted, functions first at
    any shared address."""
    ref_dir = ref_dir or default_ref_dir()
    elf_path = os.path.join(ref_dir, "bn6f.elf")
    funcs, labels = parse_asm(ref_dir)

    stats = {
        "source": None,
        "elf_path": elf_path,
        "func_markers": len(funcs),
        "asm_labels": len(labels),
        "thumb": 0,
        "arm": 0,
        "mapping": 0,
        "mode_conflicts": [],
        "no_marker_funcs": 0,
        "unplaced_funcs": [],
        "unplaced_labels": 0,
        "unplaced_label_names": [],
        "addr_conflicts": [],
        "regions": {},
        "verified": None,
        "verify_detail": "",
    }
    stats["verified"], stats["verify_detail"] = verify_build(ref_dir, rom_path)

    syms = []

    if use_elf and os.path.exists(elf_path):
        stats["source"] = "elf"
        for name, value, size, styp, _bind in read_elf_symbols(elf_path):
            if styp in (STT_SECTION, STT_FILE):
                continue
            if name.startswith("$"):
                # ARM mapping symbols: $a ARM code, $t Thumb code, $d data.
                base = name.split(".")[0]
                mode = {"$a": "arm", "$t": "thumb", "$d": "data"}.get(base)
                if mode and region_of(value & ~1) != "?":
                    syms.append(Symbol(base, value & ~1, "M", mode, 0, "", 0, 0))
                    stats["mapping"] += 1
                continue
            if styp == STT_FUNC:
                addr = value & ~1
                mode = "thumb" if (value & 1) else "arm"
                if region_of(addr) == "?":
                    stats["unplaced_funcs"].append(name)
                    continue
                marker = funcs.get(name)
                if marker is None:
                    stats["no_marker_funcs"] += 1
                    rel, s_line, e_line = "", 0, 0
                else:
                    if marker[0] != mode:
                        stats["mode_conflicts"].append((name, mode, marker[0]))
                    rel, s_line, e_line = marker[1], marker[2], marker[3]
                syms.append(Symbol(name, addr, "F", mode, size, rel, s_line, e_line))
                stats["thumb" if mode == "thumb" else "arm"] += 1
            else:
                addr = value
                if region_of(addr) == "?":
                    continue                       # .debug_* and friends
                rel, lineno = labels.get(name, ("", 0))
                syms.append(Symbol(name, addr, "D", "-", size, rel, lineno, 0))
    else:
        # Degraded path: no build output, so addresses come from the map plus the
        # address suffix every name carries.
        stats["source"] = "map+names" if use_elf else "map+names (--no-elf)"
        mapsyms, _map_path = parse_map(ref_dir)
        stats["map_symbols"] = len(mapsyms)

        def place(name):
            map_addr = mapsyms.get(name)
            name_addr = addr_from_name(name)
            if map_addr is not None:
                if name_addr is not None and name_addr != map_addr:
                    stats["addr_conflicts"].append((name, map_addr, name_addr))
                return map_addr
            return name_addr

        claimed = set()
        for name in sorted(funcs):
            mode, rel, s_line, e_line = funcs[name]
            addr = place(name)
            if addr is None:
                stats["unplaced_funcs"].append(name)
                continue
            syms.append(Symbol(name, addr, "F", mode, 0, rel, s_line, e_line))
            claimed.add(name)
            stats["thumb" if mode == "thumb" else "arm"] += 1
        for name in sorted(labels):
            if name in claimed:
                continue
            addr = place(name)
            if addr is None:
                stats["unplaced_labels"] += 1
                if len(stats["unplaced_label_names"]) < 20:
                    stats["unplaced_label_names"].append(name)
                continue
            rel, lineno = labels[name]
            syms.append(Symbol(name, addr, "D", "-", 0, rel, lineno, 0))
            claimed.add(name)
        for name in sorted(mapsyms):
            if name not in claimed:
                syms.append(Symbol(name, mapsyms[name], "D", "-", 0, "", 0, 0))

    for s in syms:
        if s.kind == "M":
            continue
        slot = stats["regions"].setdefault(s.region, [0, 0])
        slot[0 if s.kind == "F" else 1] += 1

    syms.sort(key=lambda s: (s.addr, {"M": 0, "F": 1, "D": 2}[s.kind], s.name))
    stats["sized_by_neighbour"] = fill_missing_sizes(syms)
    return syms, stats


def fill_missing_sizes(syms):
    """Give the handful of functions with st_size 0 an extent: up to the next
    function.

    `thumb_func_end NAME` sets `.size NAME, . - NAME`, so a function only lacks a
    size when its end marker is missing.  The next *function* is the bound, not
    the next symbol of any kind -- a function's own internal `loc_`/`off_` labels
    would otherwise cut it off after a few instructions.  The estimate can
    overshoot into trailing data, which is harmless: every consumer intersects it
    with the ELF's `$t`/`$a` code ranges.
    """
    addrs = sorted(s.addr for s in syms if s.kind == "F")
    n = 0
    for s in syms:
        if s.kind != "F" or s.size:
            continue
        j = bisect.bisect_right(addrs, s.addr)
        if j < len(addrs) and addrs[j] > s.addr:
            s.size = addrs[j] - s.addr
            n += 1
    return n


# --------------------------------------------------------------------------
# Memory map
# --------------------------------------------------------------------------

PT_LOAD = 1
PF_X = 1

ROM_BASE = 0x08000000

# GBA hardware regions.  Sizes are the console's, not the game's, so they are
# stated here rather than derived: EWRAM 256 KiB, IWRAM 32 KiB, I/O registers,
# BG/OBJ palette RAM, VRAM 96 KiB, OAM.
HW_BLOCKS = (
    ("EWRAM",   0x02000000, 0x00040000, "rw-"),
    ("IWRAM",   0x03000000, 0x00008000, "rw-"),
    ("IO",      0x04000000, 0x00000400, "rw-"),
    ("PALETTE", 0x05000000, 0x00000400, "rw-"),
    ("VRAM",    0x06000000, 0x00018000, "rw-"),
    ("OAM",     0x07000000, 0x00000400, "rw-"),
)


def read_elf_segments(path):
    """PT_LOAD segments as (vaddr, paddr, filesz, memsz, flags)."""
    with open(path, "rb") as fh:
        data = fh.read()
    e_phoff, = struct.unpack_from("<I", data, 0x1C)
    e_phentsize, e_phnum = struct.unpack_from("<HH", data, 0x2A)
    out = []
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        p_type, _o, p_vaddr, p_paddr, p_filesz, p_memsz, p_flags, _al = \
            struct.unpack_from("<8I", data, off)
        if p_type == PT_LOAD and p_memsz:
            out.append((p_vaddr, p_paddr, p_filesz, p_memsz, p_flags))
    return out


def memory_map(ref_dir=None, rom_size=None):
    """Blocks for the Ghidra pre-script, as (kind, name, addr, size, src, perms).

    The cartridge image is one block from the loader; it gets split so that only
    the linker's executable range is marked executable, which keeps Ghidra's
    analysers out of the 6 MiB of sprite and map data.  Boundaries come from the
    ELF's PT_LOAD headers, never from constants.
    """
    ref_dir = ref_dir or default_ref_dir()
    elf_path = os.path.join(ref_dir, "bn6f.elf")
    rom_size = rom_size or 0x00800000

    exec_ranges = []     # (rom_addr, size) executable where the cartridge holds it
    copies = []          # (name, vaddr, size, src_rom_addr)
    if os.path.exists(elf_path):
        for vaddr, paddr, filesz, _memsz, flags in read_elf_segments(elf_path):
            if not filesz:
                continue                       # NOBITS (bss); HW_BLOCKS covers it
            if paddr < ROM_BASE:
                continue                       # not stored in the cartridge
            if vaddr != paddr:
                # Overlay: stored at paddr, runs at vaddr.
                copies.append(("IWRAM_CODE" if region_of(vaddr) == "iwram"
                               else "OVERLAY_%08X" % vaddr,
                               vaddr, filesz, paddr))
                exec_ranges.append((paddr, filesz, False))
            elif flags & PF_X:
                exec_ranges.append((paddr, filesz, True))

    # Split the cartridge image at every executable boundary.
    bounds = set([ROM_BASE, ROM_BASE + rom_size])
    for addr, size, _x in exec_ranges:
        bounds.add(addr)
        bounds.add(addr + size)
    bounds = sorted(b for b in bounds if ROM_BASE <= b <= ROM_BASE + rom_size)

    rows = []
    for lo, hi in zip(bounds, bounds[1:]):
        if hi <= lo:
            continue
        execish = any(a <= lo < a + s and x for a, s, x in exec_ranges)
        stored = any(a <= lo < a + s and not x for a, s, x in exec_ranges)
        if execish:
            name, perms = "ROM_TEXT_%08X" % lo, "r-x"
        elif stored:
            name, perms = "ROM_OVERLAY_IMAGE_%08X" % lo, "r--"
        else:
            name, perms = "ROM_DATA_%08X" % lo, "r--"
        rows.append(("ROM", name, lo, hi - lo, None, perms))

    for name, vaddr, size, src in copies:
        rows.append(("COPY", name, vaddr, size, src, "r-x"))

    # Hardware regions, minus anything a COPY block already occupies (Ghidra
    # blocks may not overlap), so IWRAM becomes two bss blocks around the code.
    for name, addr, size, perms in HW_BLOCKS:
        holes = sorted((v, v + sz) for _n, v, sz, _s in copies
                       if addr < v + sz and v < addr + size)
        cur = addr
        part = 0
        for lo, hi in holes:
            if lo > cur:
                rows.append(("BSS", "%s%s" % (name, "" if part == 0 else "_%d" % part),
                             cur, lo - cur, None, perms))
                part += 1
            cur = max(cur, hi)
        if cur < addr + size:
            rows.append(("BSS", "%s%s" % (name, "" if part == 0 else "_%d" % part),
                         cur, addr + size - cur, None, perms))

    rows.sort(key=lambda r: (r[0] != "ROM", r[2]))
    return rows


def write_memmap(rows, out_path):
    tmp = out_path + ".tmp"
    with open(tmp, "w") as fh:
        fh.write("# kind\tname\taddr\tsize\tsrc\tperms\n")
        for kind, name, addr, size, src, perms in rows:
            fh.write("%s\t%s\t%08X\t%08X\t%s\t%s\n"
                     % (kind, name, addr, size,
                        "-" if src is None else "%08X" % src, perms))
    os.replace(tmp, out_path)


def write_tsv(syms, out_path):
    tmp = out_path + ".tmp"
    with open(tmp, "w") as fh:
        fh.write("# kind\tname\taddr\tmode\tsize\tasm_file\tstart_line\tend_line\n")
        for s in syms:
            fh.write("%s\t%s\t%08X\t%s\t%d\t%s\t%d\t%d\n" % (
                s.kind, s.name, s.addr, s.mode, s.size, s.asm_file,
                s.start_line, s.end_line))
    os.replace(tmp, out_path)


def read_tsv(path):
    """Inverse of write_tsv, for consumers that want the cached index."""
    syms = []
    with open(path, "r") as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if len(f) != 8:
                continue
            syms.append(Symbol(f[1], int(f[2], 16), f[0], f[3], int(f[4]),
                               f[5], int(f[6]), int(f[7])))
    return syms


def report(syms, stats, out=sys.stderr):
    n_f = sum(1 for s in syms if s.kind == "F")
    n_m = sum(1 for s in syms if s.kind == "M")
    w = out.write
    w("bnsyms: source %s\n" % stats["source"])
    if stats["verified"] is True:
        w("bnsyms: VERIFIED %s\n" % stats["verify_detail"])
    elif stats["verified"] is False:
        w("bnsyms: WARNING addresses unverified -- %s\n" % stats["verify_detail"])
    else:
        w("bnsyms: note: could not verify the build (%s)\n" % stats["verify_detail"])
    w("bnsyms: %d functions (%d thumb / %d arm), %d labels, %d ARM/Thumb ranges\n"
      % (n_f, stats["thumb"], stats["arm"], len(syms) - n_f - n_m, n_m))
    w("bnsyms: *.s gave %d func markers and %d labels\n"
      % (stats["func_markers"], stats["asm_labels"]))
    for region in sorted(stats["regions"]):
        f, d = stats["regions"][region]
        w("bnsyms:   %-8s %6d func %6d label\n" % (region, f, d))
    if stats.get("sized_by_neighbour"):
        w("bnsyms: %d functions had no ELF size; extent taken to the next symbol\n"
          % stats["sized_by_neighbour"])
    if stats["no_marker_funcs"]:
        w("bnsyms: %d ELF functions with no *.s marker (no file:line for those)\n"
          % stats["no_marker_funcs"])
    if stats["mode_conflicts"]:
        w("bnsyms: WARNING %d thumb/arm disagreements between ELF and markers: %s\n"
          % (len(stats["mode_conflicts"]),
             ", ".join("%s elf=%s asm=%s" % c for c in stats["mode_conflicts"][:5])))
    if stats["addr_conflicts"]:
        w("bnsyms: %d names whose hex suffix is not their own address (map wins): %s\n"
          % (len(stats["addr_conflicts"]),
             ", ".join(c[0] for c in stats["addr_conflicts"][:5])))
    if stats["unplaced_funcs"]:
        w("bnsyms: %d functions with no address, skipped: %s\n"
          % (len(stats["unplaced_funcs"]), ", ".join(stats["unplaced_funcs"][:10])))
    if stats["unplaced_labels"]:
        w("bnsyms: %d labels with no address, skipped: %s\n"
          % (stats["unplaced_labels"], ", ".join(stats["unplaced_label_names"][:10])))


def main(argv):
    ref_dir = default_ref_dir()
    out_path = None
    mem_path = None
    rom_path = None
    use_elf = True
    args = list(argv[1:])
    while args:
        a = args.pop(0)
        if a == "--out" and args:
            out_path = args.pop(0)
        elif a == "--ref" and args:
            ref_dir = args.pop(0)
        elif a == "--rom" and args:
            rom_path = args.pop(0)
        elif a == "--out-mem" and args:
            mem_path = args.pop(0)
        elif a == "--no-elf":
            use_elf = False
        else:
            sys.stderr.write(
                "usage: bnsyms.py [--ref DIR] [--rom ROM] [--no-elf] "
                "[--out TSV] [--out-mem TSV]\n")
            return 2

    syms, stats = load(ref_dir, use_elf=use_elf, rom_path=rom_path)
    if not syms:
        sys.stderr.write("bnsyms: no symbols found under %s\n" % ref_dir)
        return 1
    if out_path:
        write_tsv(syms, out_path)
    report(syms, stats)
    if out_path:
        sys.stderr.write("bnsyms: wrote %s\n" % out_path)
    if mem_path:
        rom_size = os.path.getsize(rom_path) if rom_path else None
        rows = memory_map(ref_dir, rom_size)
        write_memmap(rows, mem_path)
        sys.stderr.write("bnsyms: memory map (%d blocks):\n" % len(rows))
        for kind, name, addr, size, src, perms in rows:
            sys.stderr.write("bnsyms:   %-5s %-24s %08X + %08X %s%s\n"
                             % (kind, name, addr, size, perms,
                                "" if src is None else "  <- ROM %08X" % src))
        sys.stderr.write("bnsyms: wrote %s\n" % mem_path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
