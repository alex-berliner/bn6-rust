#!/usr/bin/env python3
"""Reproduce a report's harness lines from a clean detached checkout -- the free, model-less tier of
verification (HANDOFF §13). No agent touches the checkout; it is built with its own target dir and
removed afterwards.

usage:
  python3 tools/verify_rows.py <ref> <row>[,<row>...] [--expect ROW=TOTAL/WORST/FRAMES/NEG ...]
                               [--expect-file FILE] [--keep]

  <ref>          a branch or commit, e.g. wt/r9-shot or HEAD
  --expect       what the report claims for a row: total/worst/frames/negative-total, e.g.
                 wave=0/0/90/3840 ('-' skips a field). Repeatable.
  --expect-file  a file containing harness result lines as printed (e.g. pasted from a report);
                 every line whose first word is a requested row becomes an expectation.

Exit status: 0 when every row ran and every expectation matched; 1 on any mismatch, a BLIND
negative, or a row that failed to run. Rows run one at a time (captures never overlap).
"""
import argparse, os, re, subprocess, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LINE = re.compile(r"^(?P<row>\S+)\s+(?P<ui>isolated|integrated)\s+(?P<status>\S+).*?total (?P<total>\d+)\s+"
                  r"worst (?P<worst>\d+)\s+frames (?P<frames>\d+).*?negative: (?P<neg>not blind|BLIND)"
                  r"(?: \(total (?P<negtotal>\d+)\))?")


def parse(text):
    out = {}
    for line in text.splitlines():
        m = LINE.search(line.strip())
        if m:
            out.setdefault(m["row"], m.groupdict())
    return out


def main():
    if subprocess.run(["bash", os.path.join(ROOT, "tools", "check_inputs.sh")]).returncode != 0:
        sys.exit("verify_rows: inputs changed; refusing to measure")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ref")
    ap.add_argument("rows")
    ap.add_argument("--expect", action="append", default=[])
    ap.add_argument("--expect-file")
    ap.add_argument("--keep", action="store_true", help="leave the checkout in place")
    a = ap.parse_args()
    rows = [r for r in a.rows.split(",") if r]

    expect = {}
    if a.expect_file:
        for row, d in parse(open(a.expect_file).read()).items():
            expect[row] = (d["total"], d["worst"], d["frames"], d["negtotal"] or "-")
    for e in a.expect:
        row, vals = e.split("=", 1)
        expect[row] = tuple(vals.split("/"))

    sha = subprocess.run(["git", "-C", ROOT, "rev-parse", "--short", a.ref], check=True,
                         capture_output=True, text=True).stdout.strip()
    # one persistent target dir: cargo tracks the sources, so the second build of any
    # tree is warm (~20 s) instead of a cold fat-LTO build (~2 min)
    wt, target = "/tmp/bnwt/verify-%s" % sha, "/tmp/ct_verify"
    if not os.path.exists(wt):
        subprocess.run(["git", "-C", ROOT, "worktree", "add", "--detach", wt, sha], check=True,
                       capture_output=True)
        subprocess.run(["rm", "-rf", os.path.join(wt, "reference/bn6f")], check=True)
        os.symlink(os.path.join(ROOT, "reference/bn6f"), os.path.join(wt, "reference/bn6f"))
    env = dict(os.environ, CARGO_TARGET_DIR=target, CARGO_BUILD_JOBS=os.environ.get("CARGO_BUILD_JOBS", "2"))

    ok = True
    print("verify_rows: %s (%s) in %s" % (a.ref, sha, wt))
    for row in rows:
        r = subprocess.run([sys.executable, "tools/harness.py", "--only", row, "--no-gallery"], cwd=wt,
                           env=env, capture_output=True, text=True, stdin=subprocess.DEVNULL)
        got = parse(r.stdout).get(row)
        if not got:
            ok = False
            tail = (r.stdout + r.stderr).strip().splitlines()[-3:]
            print("  %-14s DID NOT RUN (exit %d): %s" % (row, r.returncode, " | ".join(tail)))
            continue
        line = "%s/%s/%s/%s" % (got["total"], got["worst"], got["frames"], got["negtotal"] or "-")
        verdict = "ran"
        if got["neg"] == "BLIND":
            ok, verdict = False, "BLIND NEGATIVE"
        if row in expect:
            want = expect[row]
            have = (got["total"], got["worst"], got["frames"], got["negtotal"] or "-")
            bad = [n for n, w, h in zip(("total", "worst", "frames", "negative"), want, have)
                   if w != "-" and w != h]
            if bad:
                ok, verdict = False, "MISMATCH %s (claimed %s)" % (",".join(bad), "/".join(want))
            elif verdict == "ran":
                verdict = "MATCH"
        print("  %-14s %-8s %-24s %s" % (row, got["status"], line, verdict))

    if not a.keep:
        subprocess.run(["git", "-C", ROOT, "worktree", "remove", "--force", wt], capture_output=True)
    print("verify_rows: %s" % ("PASS" if ok else "FAIL"))
    if ok:
        open("/tmp/land_verify_%s.pass" % sha, "w").write(" ".join(rows) + "\n")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
