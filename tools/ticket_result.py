#!/usr/bin/env python3
"""Stamp a ticket's status in TODO.md and add its **Result.** paragraph, then commit TODO.md alone.

usage: python3 tools/ticket_result.py <ID> <STATUS> "<result text>" [--no-commit]
  STATUS: DONE | PARTIAL | BLOCKED | NEGATIVE | OPEN
The status line becomes "*(STATUS -- <today>, <first sentence of result>)*"; the paragraph is inserted
right after the ticket's heading (an existing Result paragraph is replaced).
"""
import datetime, os, re, subprocess, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    tid, status, result = sys.argv[1], sys.argv[2].upper(), sys.argv[3].strip()
    commit = "--no-commit" not in sys.argv
    p = os.path.join(ROOT, "TODO.md")
    s = open(p).read()
    m = re.search(r"^### %s\. (.*?)\s*\*\((\w+)\b.*\)\*\s*$" % re.escape(tid), s, re.M)
    if not m:
        sys.exit("no ticket %s" % tid)
    today = datetime.date.today().isoformat()
    first = re.split(r"(?<=[.;])\s", result, 1)[0][:110].rstrip(".;").replace("(", "[").replace(")", "]")
    head = "### %s. %s  *(%s -- %s, %s)*" % (tid, m.group(1), status, today, first)
    nxt = re.search(r"^#{2,3} ", s[m.end():], re.M)
    end = m.end() + (nxt.start() if nxt else len(s) - m.end())
    body = s[m.end():end]
    body = re.sub(r"\n\n\*\*Result\.\*\*.*?(?=\n\n|\Z)", "", body, count=1, flags=re.S)
    body = "\n\n**Result.** " + result + body
    s = s[:m.start()] + head + body + s[end:]
    open(p, "w").write(s)
    print("stamped %s %s" % (tid, status))
    # the worker's work log (docs/worklog/<ID>.md) lands on main with the stamp, from its branch or its worktree,
    # so what was tried survives even when the branch stays unmerged
    log = os.path.join("docs", "worklog", tid + ".md"); found = None
    for wt in subprocess.run(["git", "-C", ROOT, "worktree", "list", "--porcelain"], capture_output=True, text=True).stdout.splitlines():
        if wt.startswith("worktree ") and os.path.exists(os.path.join(wt[9:], log)) and wt[9:] != ROOT:
            cand = os.path.join(wt[9:], log)
            if found is None or os.path.getmtime(cand) > os.path.getmtime(found): found = cand
    if found is None:
        for b in subprocess.run(["git", "-C", ROOT, "branch", "--list", "wt/*", "--format=%(refname:short)"], capture_output=True, text=True).stdout.split():
            r = subprocess.run(["git", "-C", ROOT, "show", "%s:%s" % (b, log)], capture_output=True, text=True)
            if r.returncode == 0 and r.stdout.strip():
                os.makedirs(os.path.join(ROOT, "docs", "worklog"), exist_ok=True); open(os.path.join(ROOT, log), "w").write(r.stdout); found = "branch " + b; break
    elif found:
        os.makedirs(os.path.join(ROOT, "docs", "worklog"), exist_ok=True)
        if os.path.abspath(found) != os.path.abspath(os.path.join(ROOT, log)):
            open(os.path.join(ROOT, log), "w").write(open(found).read())
    if found: print("work log carried to main from %s" % found)
    if commit:
        subprocess.run(["git", "-C", ROOT, "add", "-u", "TODO.md"], check=True)
        if os.path.exists(os.path.join(ROOT, log)): subprocess.run(["git", "-C", ROOT, "add", log], check=True)
        msg = "TODO %s %s: %s" % (tid, status, first)
        subprocess.run(["git", "-C", ROOT, "commit", "-q", "-m", msg], check=True)
        print("committed: " + msg)


if __name__ == "__main__":
    main()
