#!/usr/bin/env python3
"""Reproduce a report's harness lines from a clean detached checkout -- the free, model-less tier of
verification (HANDOFF §13). No agent touches the checkout; it is built with its own target dir and
removed afterwards.

usage:
  python3 tools/verify_rows.py <ref> <row>[,<row>...] [--expect ROW=TOTAL/WORST/FRAMES/NEG ...]
                               [--expect-file FILE] [--keep] [--with-main [REF]]

  <ref>          a branch or commit, e.g. wt/r9-shot or HEAD
  --expect       what the report claims for a row: total/worst/frames/negative-total, e.g.
                 wave=0/0/90/3840 ('-' skips a field). Repeatable.
  --expect-file  a file containing harness result lines as printed (e.g. pasted from a report);
                 every line whose first word is a requested row becomes an expectation.
  --with-main    also measure REF (default: main) in THIS invocation and enable the same-session
                 drift band (DRIFT_ENVELOPE below; docs/measurement-drift.md): an --expect on a
                 SEARCHED row whose expected total is NOT 0, that matches no harness line exactly
                 but sits within the row's envelope of the same-session main measurement while the
                 branch itself also sits within the envelope of main, reports
                 "MATCH (drift-band, main=X exp=Y)" instead of FAIL. A zero-total expectation is
                 never widened; a branch-vs-main gap beyond the envelope still FAILs.
                 DIAGNOSTIC-ONLY: land.sh does not pass this flag and must never; see
                 docs/measurement-drift.md §5 for the degenerate same-tree case.
  --selftest     offline probes of _try_drift_band with synthetic harness lines -- no captures,
                 no harness import; prints each probe so a reader can see the band can fail.

Exit status: 0 when every row ran and every expectation matched (exactly or drift-banded); 1 on
any mismatch, a BLIND negative, or a row that failed to run. Rows run one at a time (captures
never overlap).
"""
import argparse, os, re, subprocess, sys, fcntl

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LINE = re.compile(r"^(?P<row>\S+)\s+(?P<ui>isolated|integrated)\s+(?P<status>\S+).*?total (?P<total>\d+)\s+"
                  r"worst (?P<worst>\d+)\s+frames (?P<frames>\d+).*?negative: (?P<neg>not blind|BLIND)"
                  r"(?: \(total (?P<negtotal>\d+)\))?")

#: Same-session drift band per row, in differing PIXELS, applied to every numeric field an
#: --expect pins (total / worst / negative-total); frames must be equal exactly. A row absent
#: from this table has envelope 0 = no banding (strict). See docs/measurement-drift.md for the
#: full measurement; the short version: F48 (ed9c9c1) measured the same-commit run-to-run spread
#: as ZERO on field/opening/gunner/mettaur (4 runs, 2 sessions; field-bg2's kept capture dirs
#: byte-identical run-vs-run on all 40 frames, both sides), so the band covers the skew of a
#: constant recorded in an EARLIER session against a DIFFERENT input version (ROM tree or /tmp
#: canon inputs) -- the only kind of drift ever observed on these rows -- and never a live
#: branch-vs-main difference, which still FAILs past the envelope.
DRIFT_ENVELOPE = {
    # provenance: peeked -- NOT one measured delta: the max of FOUR recorded field-integrated
    # totals across input versions -- 158928 (coordinator/main; reproduced by NO run ever),
    # 158935 (F45 landed @1c49bc5, ROM ab80121e...; likewise never re-measured, see §6 of the
    # doc), 158953 (F46's session AND F48's re-run on those same bytes), 158930 (F48 x4 on
    # ed9c9c1's ROM 1997be3b..., the T17/T19 chip work -- a real tree-side -23, one frame,
    # deterministic x4). Max recorded spread 158953 - 158928 = 25, of which only the 23 px
    # between ab80121e and 1997be3b is reproduced; the outer 2 px exist only to cover 158928.
    # CONSEQUENCE: a real tree-side regression of up to 25 px on `field` bands through when
    # branch == main; anything larger fails and forces the constant to be re-recorded. The
    # same-commit measured spread is 0. Rows with search=None (field-bg1/2/3) are excluded by
    # the searched-row guard in main(), not by this table.
    "field": 25,
}


def parse(text):
    """{row: {'primary': first line's fields, 'lines': [every ui line's fields]}}"""
    out = {}
    for line in text.splitlines():
        m = LINE.search(line.strip())
        if m:
            d = out.setdefault(m["row"], {"lines": []})
            d["lines"].append(m.groupdict())
            d.setdefault("primary", m.groupdict())
    return out


def _fields(l):
    return (l["total"], l["worst"], l["frames"], l["negtotal"] or "-")


def _searched_rows(wt):
    """{row: its Align.search is a range} read from THIS measured tree's harness, so the band
    only ever applies to rows whose rust alignment is genuinely re-searched (a search=None row
    has a pinned pairing and nothing for capture skew to hide behind). Read-only import."""
    try:
        sys.path.insert(0, os.path.join(wt, "tools"))
        import harness  # noqa: F401  (definitions only; harness.main() is import-guarded)
        return {c.name: (c.align.search is not None)
                for c in list(harness.CHECKS) + list(harness.PORTED_CHECKS)}
    except Exception as exc:  # a tree that cannot be imported is not bandable: stay strict
        print("verify_rows: could not read %s's harness rows (%s); drift band disabled" % (wt, exc))
        return {}


def _try_drift_band(want, got_lines, main_lines, env):
    """The same-session rule (docs/measurement-drift.md §4). want: the --expect tuple;
    got_lines: this branch's harness lines; main_lines: the same-session main measurement's.
    Returns main's total (str) if the band fires, else None."""
    if env <= 0 or want[0] in ("-", "0"):
        return None  # nothing to band, or a ZERO row: its failure is a real signal, never widen
    for bl in got_lines:
        for ml in main_lines:
            if bl["ui"] != ml["ui"] or bl["neg"] == "BLIND" or ml["neg"] == "BLIND":
                continue
            okall = True
            for name, w, b, m in zip(("total", "worst", "frames", "negative"),
                                     want, _fields(bl), _fields(ml)):
                if w == "-":
                    continue
                if name == "frames":
                    if w != b or b != m:  # frames is a config constant: no capture skew possible
                        okall = False
                elif abs(int(w) - int(m)) > env or abs(int(b) - int(m)) > env:
                    okall = False
                if not okall:
                    break
            if okall:
                return ml["total"]
    return None


def _selftest():
    """Offline probes of _try_drift_band with synthetic harness lines -- no captures, no
    harness import, no worktree. Every probe prints its result so a reader can see the
    relaxation CAN fail; exit 1 if any probe fails. AGENTS.md's blind-fixture rule applies
    to tooling: a band that cannot fail is not a policy. Probe 9 pins the exit path: the
    band returning None is exactly the condition under which main() prints MISMATCH and
    exits 1 (demonstrated live in F48 step 5: field=999999/0/40/0 -> FAIL, exit 1)."""
    ml = {"row": "field", "ui": "integrated", "status": "PASS", "total": "158930",
          "worst": "5601", "frames": "40", "neg": "not blind", "negtotal": "261029"}
    bl = dict(ml)                                   # same-session main == branch here
    blind = dict(ml, neg="BLIND", negtotal=None)
    big = dict(ml, total="159930")                 # branch 1000 px off main
    env = DRIFT_ENVELOPE["field"]
    ok = True

    def probe(name, want, got, main, e, expect_val):
        nonlocal ok
        val = _try_drift_band(want, got, main, e)
        good = val == expect_val
        ok = ok and good
        print("  selftest %-40s -> %s %s"
              % (name, val if val is not None else "None (band blocked)", "ok" if good else "PROBE FAILED"))

    probe("zero-total expect never widened", ("0", "0", "40", "1139"), [bl], [ml], env, None)
    probe("frames off-by-one blocks", (ml["total"], ml["worst"], "41", ml["negtotal"]),
          [bl], [ml], env, None)
    probe("BLIND branch side blocks", (ml["total"], ml["worst"], "40", ml["negtotal"]),
          [blind], [ml], env, None)
    probe("BLIND main side blocks", (ml["total"], ml["worst"], "40", ml["negtotal"]),
          [bl], [blind], env, None)
    probe("envelope 0 / unlisted row: strict", (ml["total"], ml["worst"], "40", ml["negtotal"]),
          [bl], [ml], 0, None)
    probe("branch 1000 off main blocks", (big["total"], big["worst"], "40", big["negtotal"]),
          [big], [ml], env, None)
    probe("exp 26 off main blocks", ("158956", "5601", "40", "261029"), [bl], [ml], env, None)
    probe("exp 25 off main fires (inclusive)", ("158955", "5601", "40", "261029"),
          [bl], [ml], env, ml["total"])
    anchor = _try_drift_band(("158953", "5624", "40", "261052"), [bl], [ml], env)
    good = anchor == ml["total"]
    ok = ok and good
    print("  selftest %-40s -> MATCH (drift-band, main=%s exp=158953) %s"
          % ("same-session main anchor", anchor, "ok" if good else "PROBE FAILED"))
    last = _try_drift_band(("999999", "0", "40", "0"), [bl], [ml], env)
    good = last is None
    ok = ok and good
    print("  selftest %-40s -> MISMATCH total,negative, exit 1 %s"
          % ("field=999999/0/40/0 still FAILs", "ok" if good else "PROBE FAILED"))
    print("verify_rows selftest: %s" % ("PASS" if ok else "FAIL"))
    sys.exit(0 if ok else 1)


def _measure(sha, rows, wt, target):
    """Run each row once, one at a time, in the detached checkout `wt` at `sha`.
    Returns {row: parse-dict}; a row that did not run gets {'error': ...}."""
    if not os.path.exists(wt):
        subprocess.run(["git", "-C", ROOT, "worktree", "add", "--detach", wt, sha], check=True,
                       capture_output=True)
        subprocess.run(["rm", "-rf", os.path.join(wt, "reference/bn6f")], check=True)
        os.symlink(os.path.join(ROOT, "reference/bn6f"), os.path.join(wt, "reference/bn6f"))
    res = {}
    for row in rows:
        r = subprocess.run([sys.executable, "tools/harness.py", "--only", row, "--no-gallery"],
                           cwd=wt,
                           env=dict(os.environ, CARGO_TARGET_DIR=target,
                                    CARGO_BUILD_JOBS=os.environ.get("CARGO_BUILD_JOBS", "2")),
                           capture_output=True, text=True, stdin=subprocess.DEVNULL)
        got = parse(r.stdout).get(row)
        if not got:
            tail = (r.stdout + r.stderr).strip().splitlines()[-3:]
            res[row] = {"error": "DID NOT RUN (exit %d): %s" % (r.returncode, " | ".join(tail))}
        else:
            res[row] = got
    return res


def main():
    if subprocess.run(["bash", os.path.join(ROOT, "tools", "check_inputs.sh")]).returncode != 0:
        sys.exit("verify_rows: inputs changed; refusing to measure")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ref", nargs="?", help="a branch or commit, e.g. wt/r9-shot or HEAD "
                                            "(unused by --selftest)")
    ap.add_argument("rows", nargs="?", help="comma-separated row names (unused by --selftest)")
    ap.add_argument("--expect", action="append", default=[])
    ap.add_argument("--expect-file")
    ap.add_argument("--selftest", action="store_true",
                    help="offline probes of the drift band (no captures, no harness import)")
    ap.add_argument("--keep", action="store_true", help="leave the checkout in place")
    ap.add_argument("--with-main", dest="with_main", nargs="?", const="main", default=None,
                    metavar="REF", help="also measure REF (default main) same-session and enable "
                                        "the drift band (docs/measurement-drift.md)")
    a = ap.parse_args()
    if a.selftest:
        _selftest()
    if not a.ref or not a.rows:
        ap.error("ref and rows are required unless --selftest")
    rows = [r for r in a.rows.split(",") if r]

    expect = {}
    if a.expect_file:
        for row, d in parse(open(a.expect_file).read()).items():
            expect[row] = _fields(d["primary"])
    for e in a.expect:
        row, vals = e.split("=", 1)
        expect[row] = tuple(vals.split("/"))

    def rev(ref):
        return subprocess.run(["git", "-C", ROOT, "rev-parse", "--short", ref], check=True,
                              capture_output=True, text=True).stdout.strip()

    sha = rev(a.ref)
    main_sha = rev(a.with_main) if a.with_main else None
    # one persistent target dir: cargo tracks the sources, so the second build of any
    # tree is warm (~20 s) instead of a cold fat-LTO build (~2 min)
    wt, target = "/tmp/bnwt/verify-%s" % sha, "/tmp/ct_verify"
    # verifications share the target dir and the capture semaphore: one at a time, machine-wide
    lock = open("/tmp/bn-verify.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("verify_rows: waiting for another verification to finish"); fcntl.flock(lock, fcntl.LOCK_EX)

    ok = True
    print("verify_rows: %s (%s) in %s" % (a.ref, sha, wt))
    results = _measure(sha, rows, wt, target)
    main_results = None
    main_wt = wt
    if a.with_main:
        if main_sha == sha:
            main_results = results  # same tree: the band degenerates to exp-vs-branch
        else:
            main_wt = "/tmp/bnwt/verify-%s" % main_sha
            print("verify_rows: with-main %s (%s) in %s" % (a.with_main, main_sha, main_wt))
            main_results = _measure(main_sha, rows, main_wt, target)
        searched = _searched_rows(wt)
        print("verify_rows: drift envelope (same-session band, searched rows only): %s"
              % (", ".join("%s=%d" % (r, e) for r, e in sorted(DRIFT_ENVELOPE.items())) or "none"))
        strict = [r for r in rows if r not in DRIFT_ENVELOPE
                  and expect.get(r, ("-",))[0] not in ("-", "0")]
        if strict:
            print("verify_rows: no envelope for %s -- those expects stay exact (strict)" % ",".join(strict))

    for row in rows:
        got = results.get(row, {})
        if "error" in got:
            ok = False
            print("  %-14s %s" % (row, got["error"]))
            continue
        primary = got["primary"]
        line = "%s/%s/%s/%s" % _fields(primary)
        verdict = "ran"
        if primary["neg"] == "BLIND":
            ok, verdict = False, "BLIND NEGATIVE"
        if row in expect:
            want = expect[row]
            # an expectation may quote ANY of the row's harness lines: the integrated line every
            # report quotes for a ui=both row could never be gated before (F43's worklog shows
            # opening=18740/647/40/98649 MISMATCHing against the isolated 0/0/40/86591)
            matched = next((l for l in got["lines"]
                            if not [n for n, w, h in zip(("total", "worst", "frames", "negative"),
                                                         want, _fields(l)) if w != "-" and w != h]),
                           None)
            if matched is not None:
                if matched["neg"] == "BLIND":
                    ok, verdict = False, "BLIND NEGATIVE"
                elif verdict == "ran":
                    verdict = "MATCH" if matched is primary else "MATCH (%s line)" % matched["ui"]
            else:
                bad = [n for n, w, h in zip(("total", "worst", "frames", "negative"),
                                            want, _fields(primary)) if w != "-" and w != h]
                banded = None
                mres = (main_results or {}).get(row, {})
                if mres and "error" not in mres:
                    env = DRIFT_ENVELOPE.get(row, 0)
                    if env > 0 and searched.get(row, False):
                        banded = _try_drift_band(want, got["lines"], mres["lines"], env)
                if banded is not None:
                    # drift-band, NOT a widened pass: the branch matches same-session main within
                    # the envelope AND the expect is within the envelope of same-session main
                    verdict = "MATCH (drift-band, main=%s exp=%s)" % (banded, want[0])
                else:
                    ok = False
                    verdict = "MISMATCH %s (claimed %s)" % (",".join(bad), "/".join(want))
        print("  %-14s %-8s %-24s %s" % (row, primary["status"], line, verdict))

    if not a.keep:
        for w in {wt, main_wt}:
            subprocess.run(["git", "-C", ROOT, "worktree", "remove", "--force", w], capture_output=True)
    print("verify_rows: %s" % ("PASS" if ok else "FAIL"))
    if ok:
        open("/tmp/land_verify_%s.pass" % sha, "w").write(" ".join(rows) + "\n")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
