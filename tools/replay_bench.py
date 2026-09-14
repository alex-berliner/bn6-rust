#!/usr/bin/env python3
"""Replay benchmark: re-run an archived ticket with a candidate model from the ticket's base commit and
check whether it reaches the archived, verified answer. The cheap way to compare models on THIS
project's work (about $0.05-0.30 a run) instead of trialling them on the live queue.

usage: python3 tools/replay_bench.py <ID> --model openrouter/<vendor>/<model> [--thinking high]
                                    [--role worker] [--minutes 45] [--expect ROW=T/W/F ...] [--keep] [--dry-run]

- the ticket text is the archived section up to its **Result.**; the expectations are the rows the
  Result reports as "row T/W -> T/W/F" or "row T/W/F PASS" (override or add with --expect)
- the base commit is the parent of the commit on main whose subject names the ticket
- the model works in /tmp/bnwt/replay-<ID>-<stamp> on branch wt/replay-<ID>-<stamp> with the role's
  system prompt, headless (stdin closed), then tools/verify_rows.py judges the branch
- writes docs/benchmarks/<ID>-<model>-<stamp>.md; removes the worktree unless --keep
"""
import argparse, datetime, json, os, re, subprocess, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ARROW = re.compile(r"\b([a-z][a-z0-9-]*)\s+(\d+)/(\d+)(?:/(\d+))?(?:/\d+)?\s*(?:->|→)\s*(\d+)/(\d+)/(\d+)")
PASSED = re.compile(r"\b([a-z][a-z0-9-]*)\s+(\d+)/(\d+)/(\d+)\s+PASS")


def sh(cmd, **kw):
    return subprocess.run(cmd, shell=isinstance(cmd, str), capture_output=True, text=True, **kw)


def ticket_section(tid):
    text = ""
    for f in ("TODO.md", "TODO_ARCHIVE.md"):
        p = os.path.join(ROOT, f)
        if os.path.exists(p): text += open(p).read() + "\n"
    m = re.search(r"^### %s\. .*?(?=^### |\Z)" % re.escape(tid), text, re.M | re.S)
    if not m: sys.exit("ticket %s not found in TODO.md/TODO_ARCHIVE.md" % tid)
    sec = m.group(0)
    results = "\n".join(re.findall(r"^\*\*Result\.\*\*.*?(?=\n\n|\Z)", sec, re.M | re.S))
    ticket = re.sub(r"^\*\*(Result|Next pass[^*]*)\.?\*\*.*?(?=\n\n|\Z)", "", sec, flags=re.M | re.S)
    return re.sub(r"\n{3,}", "\n\n", ticket).strip(), results


def expectations(result, extra):
    exp = {}
    for m in ARROW.finditer(result):
        exp.setdefault(m.group(1), (m.group(5), m.group(6), m.group(7)))
    for m in PASSED.finditer(result):
        exp.setdefault(m.group(1), (m.group(2), m.group(3), m.group(4)))
    for e in extra or []:
        row, val = e.split("=", 1); t, w, f = (val.split("/") + ["-", "-"])[:3]; exp[row] = (t, w, f)
    return exp


def base_commit(tid):
    for extra in (["--merges"], []):
        r = sh(["git", "-C", ROOT, "log", "main", "--format=%H %s", "-1", "--grep=^\\(Merge \\)\\?%s\\b" % tid] + extra)
        line = r.stdout.strip().splitlines()[0] if r.stdout.strip() else ""
        if line and not line.split(" ", 1)[1].startswith("TODO"):
            sha = line.split()[0]
            return sh(["git", "-C", ROOT, "rev-parse", sha + "^1"]).stdout.strip(), line
    sys.exit("no commit on main names %s; pass a base with --base" % tid)


def role_prompt(role):
    s = open(os.path.join(ROOT, ".pi", "agents", role + ".md")).read()
    if s.startswith("---"):
        s = s.split("---", 2)[2]
    return s.strip()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ticket"); ap.add_argument("--model", required=True); ap.add_argument("--thinking", default="high")
    ap.add_argument("--role", default="worker"); ap.add_argument("--minutes", type=int, default=45)
    ap.add_argument("--expect", action="append"); ap.add_argument("--base"); ap.add_argument("--keep", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    ticket, result = ticket_section(a.ticket)
    exp = expectations(result, a.expect)
    named = set(re.findall(r"`([a-z][a-z0-9-]*)`", ticket)) | set(re.findall(r"\b([a-z][a-z0-9-]*)\b", ticket.split("\n")[0]))
    exp = {r: v for r, v in exp.items() if r in named or any(r == e.split("=")[0] for e in a.expect or [])}
    if not exp: sys.exit("no expectations for rows the ticket names; pass --expect ROW=T/W/F")
    base, subject = (a.base, "(given)") if a.base else base_commit(a.ticket)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    name = "replay-%s-%s" % (a.ticket, stamp); wt = "/tmp/bnwt/" + name; branch = "wt/" + name
    print("ticket %s: %d chars; base %s (%s); expect %s" % (a.ticket, len(ticket), base[:7], subject[:70], exp))
    if a.dry_run: return
    sh(["git", "-C", ROOT, "worktree", "add", "-b", branch, wt, base])
    sh("rm -rf reference/bn6f && ln -s %s/reference/bn6f reference/bn6f && git update-index --skip-worktree reference/bn6f" % ROOT, cwd=wt)
    rp = "/tmp/bn-pi/replay/%s" % stamp; os.makedirs(rp, exist_ok=True)
    open(rp + "/role.md", "w").write(role_prompt(a.role))
    prompt = ("You are replaying an archived ticket as a benchmark of your model, in a headless session. Your worktree is the "
              "current directory (branch %s); AGENTS.md and AGENT_GUIDE.md apply (read them first; you are already in your "
              "worktree, do not create another). Never push, never touch other directories. Commit on the current branch. "
              "Report the harness line before and after for every row the ticket names.\n\n%s" % (branch, ticket))
    env = dict(os.environ, CARGO_TARGET_DIR="/tmp/ct_replay")
    t0 = datetime.datetime.now()
    with open(rp + "/events.jsonl", "w") as out, open(rp + "/stderr.txt", "w") as err:
        subprocess.run(["timeout", str(a.minutes * 60), "pi", "-p", "--approve", "--no-session", "--mode", "json",
                        "--model", a.model, "--thinking", a.thinking, "--append-system-prompt", rp + "/role.md", prompt],
                       cwd=wt, env=env, stdin=subprocess.DEVNULL, stdout=out, stderr=err)
    minutes = (datetime.datetime.now() - t0).total_seconds() / 60
    cost = turns = 0
    for line in open(rp + "/events.jsonl"):
        try: e = json.loads(line)
        except ValueError: continue
        m = e.get("message") if isinstance(e, dict) else None
        if isinstance(m, dict) and m.get("role") == "assistant":
            turns += 1; cost += ((m.get("usage") or {}).get("cost") or {}).get("total", 0)
    rows = ",".join(exp)
    v = sh(["python3", os.path.join(ROOT, "tools", "verify_rows.py"), branch, rows] +
           sum((["--expect", "%s=%s/%s/%s/-" % (r, t, w, f)] for r, (t, w, f) in exp.items()), []))
    ncommits = sh(["git", "-C", ROOT, "rev-list", "--count", base + ".." + branch]).stdout.strip()
    verdict = "PASS" if "verify_rows: PASS" in v.stdout else "FAIL"
    if ncommits in ("", "0"):
        verdict = "NO-OP (no commits on the branch; rows unchanged prove nothing)"
    lines = "\n".join(l for l in v.stdout.splitlines() if l.startswith("  ") or l.startswith("verify_rows"))
    os.makedirs(os.path.join(ROOT, "docs", "benchmarks"), exist_ok=True)
    short = a.model.split("/")[-1]
    doc = os.path.join(ROOT, "docs", "benchmarks", "%s-%s-%s.md" % (a.ticket, short, stamp))
    open(doc, "w").write("# Replay %s with %s (%s): %s\n\nbase %s (%s)\ncost $%.4f, %d turns, %.0f min, thinking %s, role %s\n\nexpected: %s\n\n```\n%s\n```\n\nsession: %s\n" % (
        a.ticket, a.model, a.thinking, verdict, base[:7], subject, cost, turns, minutes, a.thinking, a.role, exp, lines, rp))
    print("%s: %s  $%.4f  %d turns  %.0f min  -> %s" % (a.ticket, verdict, cost, turns, minutes, doc))
    if not a.keep:
        sh(["git", "-C", ROOT, "worktree", "remove", "--force", wt]); sh(["git", "-C", ROOT, "branch", "-D", branch])


if __name__ == "__main__":
    main()
