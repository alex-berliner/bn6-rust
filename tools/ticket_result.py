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
    m = re.search(r"^### %s\. (.*?)\s*\*\((\w+)[^)]*\)\*\s*$" % re.escape(tid), s, re.M)
    if not m:
        sys.exit("no ticket %s" % tid)
    today = datetime.date.today().isoformat()
    first = re.split(r"(?<=[.;])\s", result, 1)[0][:110].rstrip(".;")
    head = "### %s. %s  *(%s -- %s, %s)*" % (tid, m.group(1), status, today, first)
    nxt = re.search(r"^#{2,3} ", s[m.end():], re.M)
    end = m.end() + (nxt.start() if nxt else len(s) - m.end())
    body = s[m.end():end]
    body = re.sub(r"\n\n\*\*Result\.\*\*.*?(?=\n\n|\Z)", "", body, count=1, flags=re.S)
    body = "\n\n**Result.** " + result + body
    s = s[:m.start()] + head + body + s[end:]
    open(p, "w").write(s)
    print("stamped %s %s" % (tid, status))
    if commit:
        subprocess.run(["git", "-C", ROOT, "add", "-u", "TODO.md"], check=True)
        msg = "TODO %s %s: %s" % (tid, status, first)
        subprocess.run(["git", "-C", ROOT, "commit", "-q", "-m", msg], check=True)
        print("committed: " + msg)


if __name__ == "__main__":
    main()
