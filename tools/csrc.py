#!/usr/bin/env python3
"""Show one MMBN6F routine two ways at once: Ghidra's decompiled C and the
hand-made disassembly it came from.

    python3 tools/csrc.py ForMettaur_8109EF4
    python3 tools/csrc.py 8109EF4
    python3 tools/csrc.py virusObject_dispatch_8108F50 --c-only
    python3 tools/csrc.py sub_3005B00 --asm-only

Any spelling that pins down the address works, because every symbol in this
disassembly carries its address as a suffix: the name itself, the name with a
different prefix (``sub_8109EF4`` and ``ForMettaur_8109EF4`` are the same place),
or the bare address with or without ``0x``.  An address in the middle of a
routine resolves to the routine that contains it, so a crash address or a table
label inside a function still lands somewhere useful.

The C comes from decomp/, which tools/ghidra_decompile.sh fills.  The
disassembly comes from reference/bn6f itself and always works, so --asm-only is
useful even before anything has been decompiled.
"""

import bisect
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "ghidra"))
import bnsyms                                                    # noqa: E402

DEFAULT_DECOMP = os.path.join(bnsyms.repo_root(), "decomp")
DEFAULT_CACHE = "/home/box/opt/ghidra-projects/bn6f.work/symbols.tsv"
HEX_SUFFIX = re.compile(r"([0-9A-Fa-f]{6,8})$")
RULE = "=" * 78


def load_index(ref_dir=None):
    """The symbol table, from the TSV the Ghidra run left behind when it is
    current, else rebuilt from reference/bn6f (about a second)."""
    ref_dir = ref_dir or bnsyms.default_ref_dir()
    cache = os.environ.get("BN_SYMBOLS", DEFAULT_CACHE)
    elf = os.path.join(ref_dir, "bn6f.elf")
    if os.path.exists(cache):
        fresh = not os.path.exists(elf) or \
            os.path.getmtime(cache) >= os.path.getmtime(elf)
        if fresh:
            try:
                return bnsyms.read_tsv(cache)
            except Exception:
                pass
    syms, _stats = bnsyms.load(ref_dir)
    return syms


def parse_query(query):
    """(address or None, name or None) for a query string."""
    q = query.strip()
    bare = q[2:] if q[:2].lower() == "0x" else q
    if re.fullmatch(r"[0-9A-Fa-f]{6,8}", bare):
        addr = int(bare, 16)
        if bnsyms.region_of(addr) != "?":
            return addr, None
    m = HEX_SUFFIX.search(q)
    if m:
        addr = int(m.group(1), 16)
        if bnsyms.region_of(addr) != "?":
            return addr, q
    return None, q


def resolve(syms, query):
    """(symbol, enclosing_function, note) or raise LookupError.

    symbol is what the query named; enclosing_function is the function whose C we
    can show, which is the same thing for a function and the containing routine
    for a label inside one.
    """
    addr, name = parse_query(query)

    # `M` rows are the ELF's $a/$t/$d mapping symbols -- machinery for the Ghidra
    # import, not names anybody looks up, and they collide with the real label at
    # the same address.
    syms = [s for s in syms if s.kind in ("F", "D")]

    by_name = {}
    for s in syms:
        by_name.setdefault(s.name, s)
    lower = {}
    for s in syms:
        lower.setdefault(s.name.lower(), s)

    hit = None
    notes = []
    if name and name in by_name:
        hit = by_name[name]
    elif name and name.lower() in lower:
        hit = lower[name.lower()]
        notes.append("matched %s case-insensitively" % hit.name)

    funcs = sorted((s for s in syms if s.kind == "F"), key=lambda s: s.addr)
    func_addrs = [s.addr for s in funcs]

    if hit is None:
        if addr is None:
            raise LookupError(
                "no symbol called %r, and it is not an address either.\n"
                "Give a symbol name, an address (0x08109EF4 / 8109EF4), or any\n"
                "name ending in the address (sub_8109EF4)." % query)
        exact = [s for s in syms if s.addr == addr]
        if exact:
            hit = sorted(exact, key=lambda s: s.kind != "F")[0]
            if name and name != hit.name:
                notes.append("no symbol is called %s; 0x%08X is %s"
                             % (name, addr, hit.name))
        else:
            hit = None

    if hit is None:
        # An address with no symbol of its own: fall through to the enclosing
        # function below.
        target = addr
    else:
        target = hit.addr

    enclosing = None
    i = bisect.bisect_right(func_addrs, target) - 1
    if i >= 0:
        cand = funcs[i]
        end = cand.addr + cand.size if cand.size else cand.addr + 1
        if cand.addr <= target < end or cand.addr == target:
            enclosing = cand

    if hit is None:
        if enclosing is None:
            raise LookupError("0x%08X is not inside any function the disassembly "
                              "declares, and carries no symbol." % addr)
        notes.append("0x%08X has no symbol of its own" % addr)
    elif enclosing is not None and enclosing is not hit and hit.kind != "F":
        notes.append("%s is a label 0x%X into %s -- any C shown is that function's"
                     % (hit.name, hit.addr - enclosing.addr, enclosing.name))
    elif hit.kind != "F" and enclosing is None:
        notes.append("%s is a data label, not a function -- there is no C for it"
                     % hit.name)

    return hit, enclosing, "; ".join(notes)


def read_decomp_index(decomp_dir):
    """addr -> filename, from the index tools/ghidra/BnDecompile.java writes."""
    path = os.path.join(decomp_dir, "index.tsv")
    out = {}
    if not os.path.exists(path):
        return out
    with open(path) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            f = line.rstrip("\n").split("\t")
            if len(f) < 9:
                continue
            # name, status, error
            out[int(f[0], 16)] = (f[1], f[5], f[8])
    return out


def show_c(sym, decomp_dir, out):
    """Print the decompiled C for `sym` (a function). True if anything printed."""
    index = read_decomp_index(decomp_dir)
    entry = index.get(sym.addr)
    candidates = []
    if entry:
        candidates.append(entry[0] + ".c")
        candidates.append("%s.%08X.c" % (entry[0], sym.addr))
    candidates.append(sym.name + ".c")
    candidates.append("%s.%08X.c" % (sym.name, sym.addr))

    for fname in candidates:
        path = os.path.join(decomp_dir, fname)
        if os.path.exists(path):
            out.write("--- C: %s %s\n" % (bnsyms.display_path(path),
                                          "-" * max(0, 68 - len(fname))))
            with open(path) as fh:
                out.write(fh.read().rstrip("\n") + "\n")
            return True

    if entry and entry[1] != "ok":
        out.write("--- C: %s failed to decompile: %s\n" % (sym.name, entry[2]))
        return False
    if not os.path.isdir(decomp_dir) or not os.listdir(decomp_dir):
        out.write("--- C: nothing decompiled yet.  Run:  tools/ghidra_decompile.sh\n")
    else:
        out.write("--- C: no file for %s in %s (Ghidra found no function there)\n"
                  % (sym.name, bnsyms.display_path(decomp_dir)))
    return False


def show_asm(sym, enclosing, out, context=0):
    """Print the disassembly's own lines, with their file:line numbers."""
    src = sym if sym is not None and sym.asm_file else enclosing
    if src is None or not src.asm_file:
        out.write("--- asm: reference/bn6f has no recorded line for this symbol\n")
        return False

    path = os.path.join(bnsyms.repo_root(), src.asm_file)
    if not os.path.exists(path):
        out.write("--- asm: %s is missing (is the submodule checked out?)\n"
                  % src.asm_file)
        return False

    start = src.start_line
    end = src.end_line if src.end_line >= start else 0
    if not end:
        # A label has only its own line; show it plus the enclosing function's
        # tail so the reader sees what the label heads.
        if enclosing is not None and enclosing.end_line > start:
            end = enclosing.end_line
        else:
            end = start + 40
    start = max(1, start - context)
    end = end + context

    with open(path, errors="replace") as fh:
        lines = fh.readlines()
    end = min(end, len(lines))
    label = "%s:%d-%d" % (src.asm_file, start, end)
    out.write("--- asm: %s %s\n" % (label, "-" * max(0, 66 - len(label))))
    width = len(str(end))
    for n in range(start, end + 1):
        out.write("%*d  %s" % (width, n, lines[n - 1].rstrip("\n") + "\n"))
    return True


def main(argv):
    args = [a for a in argv[1:]]
    want_c = want_asm = True
    context = 0
    decomp_dir = os.environ.get("BN_DECOMP_OUT", DEFAULT_DECOMP)
    ref_dir = None
    query = None
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--c-only":
            want_asm = False
        elif a == "--asm-only":
            want_c = False
        elif a in ("-C", "--context") and i + 1 < len(args):
            i += 1
            context = int(args[i])
        elif a == "--decomp" and i + 1 < len(args):
            i += 1
            decomp_dir = args[i]
        elif a == "--ref" and i + 1 < len(args):
            i += 1
            ref_dir = args[i]
        elif a in ("-h", "--help"):
            sys.stdout.write(__doc__)
            return 0
        elif a.startswith("-"):
            sys.stderr.write("csrc: unknown option %s (try --help)\n" % a)
            return 2
        elif query is None:
            query = a
        else:
            sys.stderr.write("csrc: one symbol at a time (got %r and %r)\n"
                             % (query, a))
            return 2
        i += 1

    if query is None:
        sys.stderr.write("usage: csrc.py <symbol-or-address> "
                         "[--c-only|--asm-only] [-C N]\n")
        return 2

    syms = load_index(ref_dir)
    try:
        sym, enclosing, note = resolve(syms, query)
    except LookupError as e:
        sys.stderr.write("csrc: %s\n" % e)
        return 1

    out = sys.stdout
    shown = sym if sym is not None else enclosing
    out.write("%s\n" % RULE)
    out.write("%s @ 0x%08X" % (shown.name, shown.addr))
    if shown.kind == "F":
        out.write("  %s" % shown.mode)
        if shown.size:
            out.write("  %d bytes" % shown.size)
    else:
        out.write("  (data label)")
    out.write("\n")
    if note:
        out.write("note: %s\n" % note)
    out.write("%s\n" % RULE)

    if want_c:
        target = enclosing if (enclosing is not None and shown.kind != "F") else shown
        if target.kind != "F":
            out.write("--- C: %s is not a function; nothing to decompile\n" % target.name)
        else:
            show_c(target, decomp_dir, out)
        if want_asm:
            out.write("\n")
    if want_asm:
        show_asm(sym, enclosing, out, context)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except BrokenPipeError:
        os._exit(0)
