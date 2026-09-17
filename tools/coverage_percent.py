#!/usr/bin/env python3
"""How much of the battle engine's CODE have we reimplemented?

usage: python3 tools/coverage_percent.py [--scenario battle_full] [--all] [--missing 20] [--json]

The feature scoreboard in docs/SCOPE.md answers "how many things are done" -- 26 of 1,873 items. That
is a fair question but a cruel denominator: it counts 1,076 enemy formations and 411 chips as equals,
and it is blind to the engine underneath them, which is most of the actual work. It also grows as the
project discovers more of the game, so finishing work can make the number fall.

This asks the other question. tools/coverage.py runs the real ROM under a single-stepping profiler and
records every routine the game actually executes in a scenario, with how many instructions each one
burned. That is a denominator the game itself defines: not what we imagine the engine contains, but
what it demonstrably runs. Against it we count the routines this port cites in src/*.rs.

Two numbers come out, and the second is the honest one:

  by routine       -- what fraction of the executed routines we have touched. Democratic, and wrong:
                      a routine called twice counts the same as the object dispatcher.
  by instruction   -- what fraction of the executed INSTRUCTIONS belong to routines we have ported.
                      This is the number that answers "how much of the running game is ours".

What it does NOT prove: a citation means a routine was read and reimplemented, not that the
reimplementation is faithful. Pixel and trace parity are what prove faithfulness, and they live in the
harness rows. Read this as "how much of the engine have we engaged with", with the feature scoreboard
as the stricter "how much is actually finished".

The library bucket (libs.s: memcpy, division, the decompressors) is reported separately. It executes
constantly and is real code, but reimplementing the C library is not reimplementing the battle engine,
and leaving it in the denominator would permanently depress the number for no reason.
"""
import argparse, glob, json, os, re, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# Two row shapes. The plain one is a resolved routine. The second, "`anchor` (code in `owner`)", is an
# interior label the profiler could not place -- about 8% of the disassembly's function ends carry no
# address suffix -- and its instructions belong to the named owner. Those 61 rows hold 25 million of
# battle_full's 38 million engine instructions, so dropping them (as a first version of this script did)
# understates everything by more than half.
ROW = re.compile(
    r"^\|\s*\d+\s*\|\s*([\d,]+)\s*\|\s*([\d,]+)\s*\|\s*\d+\s*\|\s*"
    r"`([^`]+)`(?:\s*\(code in `([^`]+)`\))?\s*\|\s*([^|]+?)\s*\|\s*$", re.M)
HEAD = "## All routines executed, ranked by calls"
NEXT = re.compile(r"^## ", re.M)
LIB = re.compile(r"^(libs|bios)\.s:")
# The profiler places an executed PC by walking back to the nearest symbol that carries an address, and
# about 8% of the disassembly's function ends do not. Everything before the first resolved symbol
# therefore lands on the ROM entry point. In battle_full that bucket is 22.4 million instructions --
# 56% of the profile -- and it is not a routine anyone can port. Counting it as unported would report
# "3.5% done" when the honest statement is "we cannot attribute over half of what ran". It is set aside
# and reported on its own line, and shrinking it is a job for the function map, not the porting queue.
UNATTRIBUTED = {"start_80002a8"}


def executed(path):
    """{symbol: (calls, instr, location)} from one coverage report's main table."""
    txt = open(path, errors="replace").read()
    i = txt.find(HEAD)
    if i < 0:
        return {}
    m = NEXT.search(txt, i + len(HEAD))
    body = txt[i:m.start() if m else len(txt)]
    out = {}
    for calls, instr, sym, owner, loc in ROW.findall(body):
        c, n = int(calls.replace(",", "")), int(instr.replace(",", ""))
        key = owner or sym                   # interior anchors count towards the routine that owns them
        if key in out:
            c += out[key][0]; n += out[key][1]
        out[key] = (c, n, loc.strip())
    return out


def cited():
    """Every disassembly symbol named anywhere in our Rust sources."""
    pat = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*_[0-9A-Fa-f]{4,8}\b")
    got = set()
    for f in glob.glob(os.path.join(ROOT, "src", "**", "*.rs"), recursive=True):
        got |= set(pat.findall(open(f, errors="replace").read()))
    return {s.lower() for s in got}          # the disassembly is inconsistent about hex case


def report(name, ex, ours, missing_n, as_json=False):
    lib = {s: v for s, v in ex.items() if LIB.match(v[2])}
    una = {s: v for s, v in ex.items() if s.lower() in UNATTRIBUTED}
    eng = {s: v for s, v in ex.items() if not LIB.match(v[2]) and s.lower() not in UNATTRIBUTED}
    done = {s: v for s, v in eng.items() if s.lower() in ours}
    r_tot, r_done = len(eng), len(done)
    i_tot = sum(v[1] for v in eng.values()); i_done = sum(v[1] for v in done.values())
    i_lib = sum(v[1] for v in lib.values())
    res = {
        "scenario": name,
        "routines_executed": r_tot, "routines_ported": r_done,
        "routines_pct": round(100.0 * r_done / r_tot, 2) if r_tot else 0.0,
        "instructions_executed": i_tot, "instructions_ported": i_done,
        "instructions_pct": round(100.0 * i_done / i_tot, 2) if i_tot else 0.0,
        "library_routines": len(lib), "library_instructions": i_lib,
        "unattributed_instructions": sum(v[1] for v in una.values()),
    }
    if as_json:
        return res
    print("== %s" % name)
    print("   engine routines executed : %6d, ported %5d  -> %5.1f%% by routine"
          % (r_tot, r_done, res["routines_pct"]))
    print("   engine instructions      : %10d, ported %10d -> %5.1f%% BY INSTRUCTION"
          % (i_tot, i_done, res["instructions_pct"]))
    i_una = res["unattributed_instructions"]; whole = i_tot + i_lib + i_una
    print("   library/BIOS set aside   : %6d routines, %10d instructions (%4.1f%% of all executed)"
          % (len(lib), i_lib, 100.0 * i_lib / whole if whole else 0))
    print("   UNATTRIBUTED set aside   : %6d bucket,   %10d instructions (%4.1f%% of all executed)"
          % (len(una), i_una, 100.0 * i_una / whole if whole else 0))
    if missing_n:
        gap = sorted((v[1], s, v[2]) for s, v in eng.items() if s.lower() not in ours)[::-1][:missing_n]
        if gap:
            print("   the %d biggest unported routines, by instructions burned:" % len(gap))
            for n, s, loc in gap:
                print("     %10d  %-34s %s" % (n, s, loc))
    print()
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default="battle_full")
    ap.add_argument("--all", action="store_true", help="every scenario in docs/coverage, plus their union")
    ap.add_argument("--missing", type=int, default=10, help="list the N heaviest unported routines")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    ours = cited()
    files = sorted(glob.glob(os.path.join(ROOT, "docs/coverage/*.md"))) if a.all else \
        [os.path.join(ROOT, "docs/coverage/%s.md" % a.scenario)]
    out, union = [], {}
    for f in files:
        if not os.path.exists(f):
            sys.exit("no coverage report at %s -- run: python3 tools/coverage.py %s" % (f, a.scenario))
        ex = executed(f)
        if not ex:
            continue
        for s, v in ex.items():
            c, n, loc = v
            if s in union:
                union[s] = (union[s][0] + c, max(union[s][1], n), loc)   # instr: the deepest run, not a sum
            else:
                union[s] = v
        out.append(report(os.path.basename(f)[:-3], ex, ours, 0 if a.all else a.missing, a.json))
    if a.all and union:
        out.append(report("UNION of every recorded scenario", union, ours, a.missing, a.json))
    if a.json:
        print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
