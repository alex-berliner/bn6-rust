#!/usr/bin/env python3
"""Canon routine coverage per scenario (T2 coverage ticket).

Runs canon under the covstep profiler (tools/covstep.c -- single-stepped
libmgba, same ROM/state/script/cheat/poke semantics as mgba_capture.c,
validated byte-identical RAM over 120 stepped-vs-runFrame frames) and writes
docs/coverage/<scenario>.md: every routine executed, with call counts and
the first frame it ran, ranked by count, each named by the disassembly's
symbol and file:line -- plus a second table of routines executed in
`battle_full` but not in any existing harness row's scenario (the uncovered
set, i.e. what the porting queue must still cover).

Usage:
  python3 tools/coverage.py mettaur        # the mettaur row's scenario
  python3 tools/coverage.py battle_full    # the full-battle scenario
  python3 tools/coverage.py --union-only   # refresh the harness-row union cache

Scenarios are fixed dicts below (recipe + input script, read from
tools/states.py / tools/harness.py -- never edited here). Histograms are
cached in /tmp/covcache (keyed by full profiler config hash); only the .md
files are committed.

Function map: reference/bn6f labels carrying `thumb_func_end`/`arm_func_end`
(13225 ends on the bn-notes branch) with addresses from their _HHHHHHHH
suffixes. ~8% of ends have no address suffix and cannot be placed without
assembling the disassembly (no prebuilt agbasm binutils here); executed PCs
in those gaps attribute to the preceding resolved symbol, and the top rows
of each table are hand-verified against the disassembly.

Call semantics (calibrated on a 30-frame mettaur capture, 405 entries with
hits -- see PC_ADJ): an executed entry records raw r15 == E (branch-landed,
146 entries) or raw r15 == E+2 (fall-through/next-PC read, 258 entries), so
calls(E) = hits(E) + hits(E+2). Exactly one entry in 405 showed a wider
delta (ARM-mode noise); GBA game code is Thumb throughout the battle path.
"""

import argparse
import bisect
import glob
import hashlib
import json
import os
import pickle
import re
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import harness as H  # read-only: scenario shapes only, never modified

REAL = "/tmp/bn6f_real.gba"
STERILE = "/tmp/bn6f_sterile.gba"
PAUSED = "/tmp/pausedwithcannon.state"
OVERWORLD_NET = "/tmp/overworld_net.state"
REF = "/home/box/Code/bn/reference/bn6f"
COVSTEP_SRC = os.path.join(HERE, "covstep.c")
COVSTEP_BIN = "/tmp/covstep"
CACHE = "/tmp/covcache"
DOCDIR = os.path.join(os.path.dirname(HERE), "docs", "coverage")

#: calls(E) = hist[E] + hist[E+2] (calibration above; GBA battle code Thumb).
PC_ADJ_FALLTHROUGH = 2  # provenance: peeked -- 258/405 entries record E+2, 146/405 record E

#: Flags in Side.extra that only touch the renderer (never executed code),
#: dropped for profiling. --zero is KEPT (it writes emulated RAM every frame).
RENDER_FLAGS = ("--disable-bg", "--disable-obj", "--only-bg",
                "--only-bg-with-obj", "--diff-against")


def _build_covstep():
    if os.path.exists(COVSTEP_BIN):
        return
    subprocess.run(["gcc", COVSTEP_SRC, "-o", COVSTEP_BIN, "-I/usr/include",
                    "-lmgba", "-lm", "-O2"], check=True)


def submodule_commit():
    return subprocess.run(["git", "-C", REF, "rev-parse", "--short", "HEAD"],
                          check=True, capture_output=True, text=True).stdout.strip()


def function_map():
    """{addr: (sym, mode, file, line)}, + stats. Cached in /tmp by commit."""
    os.makedirs(CACHE, exist_ok=True)
    commit = submodule_commit()
    cache = os.path.join(CACHE, "funcmap-%s.pkl" % commit)
    if os.path.exists(cache):
        with open(cache, "rb") as f:
            cached = pickle.load(f)
            if len(cached) == 3:
                return cached
    lab = re.compile(r"^([A-Za-z_][\w]*):")
    endm = re.compile(r"(thumb|arm)_func_end\s+([A-Za-z_][\w]*)")
    suf = re.compile(r"^(?:sub_|.*?_)([0-9A-Fa-f]{7,8})$")
    labels, ends = {}, {}
    nfiles = 0
    for f in sorted(glob.glob(REF + "/asm/*.s") + glob.glob(REF + "/*.s")):
        nfiles += 1
        for i, line in enumerate(open(f, errors="replace"), 1):
            m = lab.match(line)
            if m:
                labels.setdefault(m.group(1), (os.path.basename(f), i))
            m2 = endm.search(line)
            if m2:
                ends[m2.group(2)] = m2.group(1)
    funcs, nosuffix = {}, 0
    for name, mode in ends.items():
        m = suf.match(name)
        if m and name in labels:
            addr = int(m.group(1), 16)
            funcs.setdefault(addr, []).append((name, mode) + labels[name])
        else:
            nosuffix += 1
    # Every address-carrying label (interior loc_/jt_ anchors included) for
    # pinpointing executed code inside ranges whose own entry lacks a suffix.
    anchors = {}
    for name, (f, ln) in labels.items():
        m = suf.match(name)
        if m:
            anchors.setdefault(int(m.group(1), 16), (name, f, ln))
    # primary name per address: prefer a descriptive (non-sub_) symbol
    prim = {}
    for addr, alts in funcs.items():
        alts.sort(key=lambda a: (a[0].startswith("sub_"), a[0]))
        prim[addr] = alts[0] + (tuple(a[0] for a in alts[1:]),)
    stats = dict(commit=commit, files=nfiles, ends=len(ends),
                 resolved=len(prim), nosuffix=nosuffix, anchors=len(anchors))
    with open(cache, "wb") as f:
        pickle.dump((prim, stats, anchors), f)
    return prim, stats, anchors


def scenario_config(name):
    """Full profiler config for a named scenario (read from harness/states)."""
    if name == "mettaur":
        check = next(c for c in H.CHECKS if c.name == "mettaur")
        side = check.canon("isolated")
        count = check.align.canon_ref + check.frames + H.NEGATIVE_MARGIN
        return side_to_config(side, count, note="harness mettaur canon side")
    if name == "battle_full":
        # provenance: derived -- states.py battlestart recipe (walk cycle +
        # one-shot encounter poke at frame 60) then battle play from frame 79
        # (battle frame 0); chip-window timings from states.py chip_ready_empty
        # (slide-in battle-frame 91, pick/OK/confirm +39/+49/+59 from open).
        walk = ",".join("%s@%d" % (("Right", "Down", "Left", "Up")[i % 4], i)
                        for i in range(79))
        play = ("B@90,B@120,A@209,Start@219,A@229,A@280,B@300,B@330,"
                "Left@350,Right@360,Up@370,Down@380,B@400,A@420,B@450")
        return dict(rom=REAL, loadstate=OVERWORLD_NET, loadsave=None,
                    script="%s,%s" % (walk, ",".join(
                        "%s@%d" % (k, int(v) + 79) for k, v in
                        (t.split("@") for t in play.split(",")))),
                    cheats=(), pokes=(),
                    poke_at=("60:0x02001c16:0x2000", "60:0x02001c18:0"),
                    zero=(), count=530,
                    note="states.py battlestart recipe + battle play to frame 530")
    raise SystemExit("unknown scenario %r (want mettaur|battle_full)" % name)


def side_to_config(side, count, note=""):
    # Only side.extra can carry anything beyond the fields below (args() is
    # exactly loadstate/cheats/pokes/script/zero/fixture/extra); anything
    # there that is not a renderer-only flag is unhandled.
    extra, i, ex = [], 0, list(side.extra)
    while i < len(ex):
        if ex[i] in ("--only-bg", "--only-bg-with-obj", "--diff-against"):
            i += 2  # renderer-only flag plus its value
        elif ex[i] in RENDER_FLAGS:
            i += 1  # bare renderer-only flag
        else:
            extra.append(ex[i])
            i += 1
    # side.args() already linearizes loadstate/cheats/pokes/script/zero/extras;
    # re-split into covstep flags (covstep takes the same flag spellings).
    cfg = dict(rom=side.resolved_rom(), loadstate=side.loadstate, loadsave=None,
               script=side.script, cheats=tuple(side.cheats), pokes=tuple(side.pokes),
               poke_at=tuple(side.pokes_at), zero=tuple(side.zero),
               count=count, note=note)
    if side.fixture is not None:
        cfg["cheats"] = cfg["cheats"] + tuple(H.fixture_cheats(side.fixture))
    if side.capture_fn is not None:
        raise SystemExit("capture_fn side cannot be profiled")
    if extra:
        raise SystemExit("unhandled non-render extra flags: %r" % extra)
    return cfg


def harness_union_configs():
    """One profiler config per harness Check's canon capture (read-only)."""
    cfgs = []
    for c in H.CHECKS:
        if c.name == "rollup":
            continue  # run_rollup is a no-crash check, not a Check with canon_ref
        side = c.canon("isolated") if callable(c.canon) else c.canon
        count = c.align.canon_ref + c.frames + H.NEGATIVE_MARGIN
        cfgs.append((c.name, side_to_config(side, count, note="harness %s" % c.name)))
    # run_rollup's side: include it -- it is a real long scenario
    try:
        n, side_desc = H.run_rollup.__doc__ or "", None
    except Exception:
        pass
    return cfgs


def profile(cfg):
    """Run covstep for cfg; return [(raw_pc, count, first_frame)]. Cached."""
    _build_covstep()
    os.makedirs(CACHE, exist_ok=True)
    key = hashlib.sha1(json.dumps(cfg, sort_keys=True, default=str).encode()).hexdigest()[:12]
    out = os.path.join(CACHE, "hist-%s.bin" % key)
    if not os.path.exists(out):
        cmd = [COVSTEP_BIN, cfg["rom"], str(cfg["count"]), "--out", out]
        if cfg.get("loadstate"):
            cmd += ["--loadstate", cfg["loadstate"]]
        if cfg.get("loadsave"):
            cmd += ["--loadsave", cfg["loadsave"]]
        if cfg.get("script"):
            cmd += ["--script", cfg["script"]]
        for c in cfg.get("cheats", ()):
            cmd += ["--cheat", c]
        for p in cfg.get("pokes", ()):
            cmd += ["--poke", p]
        for p in cfg.get("poke_at", ()):
            cmd += ["--poke-at", p]
        for z in cfg.get("zero", ()):
            cmd += ["--zero", z]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    d = open(out, "rb").read()
    magic, nf, ne = struct.unpack("<III", d[:12])
    assert magic == 0x31535643, out
    return [struct.unpack("<III", d[12 + i * 12:24 + i * 12]) for i in range(ne)]


BIOS_END = 0x00004000  # provenance: derived -- GBA BIOS ROM size 16KB


def attribute(hist, funcs, anchors):
    """hist -> ({addr: [calls, instr, first, anchor]}, buckets).

    calls(E) = hits(E) + hits(E+2) (PC_ADJ); first = earliest frame of ANY
    record in the range (the old entry-only version leaked a 10^9 sentinel
    for ranges whose entry was never observed). A range with calls == 0 but
    instr > 0 holds executed code under a suffix-less entry (or a table jump
    into its interior); its hottest interior anchor (a loc_/jt_ label, whose
    address suffix is exact) is attached for display so the porting queue can
    still find the code.
    """
    starts = sorted(funcs)
    anchor_addrs = sorted(anchors)
    hit = {}
    for pc, c, ff in hist:
        hit[pc] = (c, ff)
    entries = set(starts)
    cov = {}
    buckets = {"bios": [0, 0], "iwram-gap": [0, 0], "ewram": [0, 0]}
    for pc, (c, ff) in hit.items():
        if pc < BIOS_END:
            buckets["bios"][0] += c
            continue
        key = pc if pc in entries else pc - PC_ADJ_FALLTHROUGH
        i = bisect.bisect_right(starts, key) - 1
        if i < 0:
            if 0x03000000 <= pc < 0x03008000:
                buckets["iwram-gap"][0] += c
            elif 0x02000000 <= pc < 0x02040000:
                buckets["ewram"][0] += c
            else:
                buckets["bios"][0] += c
            continue
        a = starts[i]
        r = cov.setdefault(a, [0, 0, ff, None, None])
        r[1] += c
        if ff < r[2]:
            r[2] = ff
    for a, r in cov.items():
        r[0] = hit.get(a, (0, 0))[0] + hit.get(a + PC_ADJ_FALLTHROUGH, (0, 0))[0]
        if r[0] == 0 and r[1] > 0:
            # hottest executed PC in the range -> nearest interior anchor
            lo, hi = a, starts[starts.index(a) + 1] if a != starts[-1] else 0x0A000000
            best, bestc = None, -1
            for pc, (c, _ff) in hit.items():
                key = pc if pc in entries else pc - PC_ADJ_FALLTHROUGH
                if a <= key < hi and c > bestc:
                    best, bestc = pc, c
            if best is not None:
                j = bisect.bisect_right(anchor_addrs, best) - 1
                if j >= 0 and anchor_addrs[j] >= a:
                    r[3] = anchor_addrs[j]
    return cov, buckets


def fmt_sym(funcs, addr):
    name, mode, f, ln, aliases = funcs[addr]
    if aliases:
        return "%s (alias %s)" % (name, ", ".join(aliases))
    return name


def display_row(funcs, anchors, a, r):
    calls, instr, ff, anchor = r[0], r[1], r[2], r[3]
    if anchor is not None and anchor in anchors:
        name, f, ln = anchors[anchor]
        return ("`%s` (code in `%s`)" % (name, fmt_sym(funcs, a)), "%s:%d" % (f, ln))
    name, mode, f, ln, _ = funcs[a]
    return "`%s`" % fmt_sym(funcs, a), "%s:%d" % (f, ln)


def ranked_table(cov, funcs, anchors):
    rows = sorted(cov.items(), key=lambda kv: (-kv[1][0], kv[0]))
    lines = ["| rank | calls | instr | first frame | symbol | location |",
             "| ---: | ---: | ---: | ---: | --- | --- |"]
    for rank, (a, r) in enumerate(rows, 1):
        sym, loc = display_row(funcs, anchors, a, r)
        lines.append("| %d | %d | %d | %d | %s | %s |" %
                     (rank, r[0], r[1], r[2], sym, loc))
    return lines, rows


def write_doc(scenario, cfg, cov, buckets, funcs, stats, anchors, union_sets, interp_lines):
    # union_sets = (uncovered_rows, unionsyms); uncovered is ALWAYS
    # battle_full minus the harness union, whichever scenario this doc is for.

    os.makedirs(DOCDIR, exist_ok=True)
    lines, rows = ranked_table(cov, funcs, anchors)
    total_instr = sum(r[1] for _, r in cov.items())
    bio = buckets["bios"][0]
    (uncovered, unionsyms) = union_sets
    md = []
    md.append("# Coverage: `%s`" % scenario)
    md.append("")
    md.append("Profiler: tools/covstep.c (single-stepped libmgba, same drive "
              "semantics as mgba_capture.c; stepped-vs-runFrame RAM identical "
              "over 120 frames) + function map from reference/bn6f@%s "
              "(%d `*_func_end` symbols, %d address-resolved, %d without an "
              "address suffix attributed to the preceding resolved symbol)." %
              (stats["commit"], stats["ends"], stats["resolved"], stats["nosuffix"]))
    md.append("")
    md.append("Scenario: %s" % cfg["note"])
    md.append("`rom=%s loadstate=%s script=%s cheats=%s pokes=%s poke_at=%s frames=%d`" %
              (os.path.basename(cfg["rom"]), os.path.basename(cfg.get("loadstate") or "-"),
               (cfg.get("script") or "-")[:120], cfg.get("cheats", ()),
               cfg.get("pokes", ()), cfg.get("poke_at", ()), cfg["count"]))
    md.append("")
    md.append("Executed: %d routines, %d instructions profiled (BIOS bucket %d, "
              "%.1f%%)." % (len(cov), total_instr, bio, 100.0 * bio / max(total_instr, 1)))
    md.append("")
    md.append("## Interpreters in this ranking (HANDOFF.md porting plan)")
    md.append("")
    md += interp_lines
    md.append("")
    md.append("## All routines executed, ranked by calls")
    md.append("")
    md += lines
    md.append("")
    md.append("## Uncovered set: in `battle_full` but in no harness row's scenario")
    md.append("")
    md.append("%d routines (battle_full's own routines minus the %d-routine "
              "harness-row union)." % (len(uncovered), len(unionsyms)))
    md.append("")
    md.append("| rank | battle_full calls | first frame | symbol | location |")
    md.append("| ---: | ---: | ---: | --- | --- |")
    for rank, (a, r) in enumerate(uncovered, 1):
        sym, loc = display_row(funcs, anchors, a, r)
        md.append("| %d | %d | %d | %s | %s |" % (rank, r[0], r[2], sym, loc))
    md.append("")
    with open(os.path.join(DOCDIR, scenario + ".md"), "w") as f:
        f.write("\n".join(md))
    return rows, uncovered


INTERPRETERS = r"""
- animation bytecode player: TBD (rank/symbol from the table above)
- object dispatcher: TBD
- script VMs: TBD
""".strip().split("\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario", nargs="?", default="battle_full")
    ap.add_argument("--union-only", action="store_true")
    args = ap.parse_args()
    funcs, stats, anchors = function_map()
    # harness-row union (cached histograms; the expensive part runs once)
    union_cfgs = harness_union_configs()
    unionsyms = set()
    for name, cfg in union_cfgs:
        try:
            hist = profile(cfg)
        except SystemExit as e:
            print("union: skip %s (%s)" % (name, e))
            continue
        cov, _ = attribute(hist, funcs, anchors)
        unionsyms |= set(cov)
    print("union: %d rows, %d routines" % (len(union_cfgs), len(unionsyms)))
    if args.union_only:
        return
    cfg = scenario_config(args.scenario)
    hist = profile(cfg)
    cov, buckets = attribute(hist, funcs, anchors)
    bfcfg = scenario_config("battle_full")
    bfhist = hist if args.scenario == "battle_full" else profile(bfcfg)
    bfcov, _ = attribute(bfhist, funcs, anchors)
    uncovered = [(a, bfcov[a]) for a in set(bfcov) - unionsyms]
    uncovered.sort(key=lambda kv: (-kv[1][0], kv[0]))
    rows, _ = write_doc(args.scenario, cfg, cov, buckets, funcs,
                        stats, anchors, (uncovered, unionsyms), INTERPRETERS)
    print("%s: %d routines, %d uncovered; wrote docs/coverage/%s.md" %
          (args.scenario, len(rows), len(uncovered), args.scenario))


if __name__ == "__main__":
    main()
