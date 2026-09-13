#!/usr/bin/env python3
"""Move closed tickets out of TODO.md into TODO_ARCHIVE.md, leaving a one-line index entry each, so
TODO.md stays small (agents and the coordinator read it through tools/next_ticket.py, and every token
of closed history was being re-sent). Idempotent: run it whenever tickets close.

- In the ticket sections (R, F, ...): every ticket whose status is not OPEN is moved in full and
  replaced by `- <ID> <STATUS> -- <title>. <first sentence of its Result>`.
- Whole sections named with --archive-sections (default: A B C D, the pre-convergence tickets) are
  moved verbatim.

usage: python3 tools/archive_tickets.py [--archive-sections A B C D] [--dry-run]
"""
import argparse, datetime, os, re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
HEAD = re.compile(r"^### ([A-Z]+\d+[a-z]?)\. (.*?)\s*\*\((\w+)[^)]*\)\*\s*$", re.M)
SEC = re.compile(r"^## ([A-Z])\. ", re.M)


def first_sentence(body):
    m = re.search(r"\*\*Result\.\*\*\s*(.*?)(?<=[.;])\s", body, re.S)
    return (m.group(1).strip()[:140] if m else "").rstrip(".;")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--archive-sections", nargs="*", default=["A", "B", "C", "D"])
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    todo = os.path.join(ROOT, "TODO.md"); arch = os.path.join(ROOT, "TODO_ARCHIVE.md")
    s = open(todo).read()
    moved = []

    # 1. whole sections
    secs = list(SEC.finditer(s))
    keep, cut = [], []
    for i, m in enumerate(secs):
        end = secs[i + 1].start() if i + 1 < len(secs) else len(s)
        if m.group(1) in a.archive_sections:
            cut.append(s[m.start():end]); moved.append("section %s" % m.group(1))
    for c in cut:
        s = s.replace(c, "", 1)

    # 2. closed tickets in the remaining text
    out, pos = [], 0
    heads = list(HEAD.finditer(s))
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(s)
        nsec = re.search(r"^## ", s[m.end():end], re.M)
        if nsec:
            end = m.end() + nsec.start()
        # keep the section's trailing shared paragraph with the section, not the ticket
        body = s[m.start():end]
        common = re.search(r"^\*\*Common to .*?(?=\n\n|\Z)", body, re.M | re.S)
        tail = ""
        if common:
            tail = body[common.start():]; body = body[:common.start()]
        if m.group(3) != "OPEN":
            out.append(s[pos:m.start()])
            out.append("- %s %s -- %s. %s\n" % (m.group(1), m.group(3), m.group(2), first_sentence(body)))
            if tail:
                out.append("\n" + tail)
            cut.append(body); moved.append(m.group(1))
            pos = end
    out.append(s[pos:])
    new = "".join(out)
    new = re.sub(r"\n{3,}", "\n\n", new)

    if not moved:
        print("nothing to archive"); return
    stamp = "\n\n---\n\n# archived %s\n\n" % datetime.date.today().isoformat()
    if a.dry_run:
        print("would move:", ", ".join(moved)); print("TODO.md %d -> %d bytes" % (len(s), len(new))); return
    header = "" if os.path.exists(arch) else ("# TODO_ARCHIVE -- closed tickets, moved verbatim by tools/archive_tickets.py\n"
                                              "Open tickets live in TODO.md; `python3 tools/next_ticket.py --list` indexes them.\n")
    with open(arch, "a") as f:
        f.write(header + stamp + "\n\n".join(c.rstrip() + "\n" for c in cut))
    open(todo, "w").write(new)
    print("moved %d item(s) to TODO_ARCHIVE.md; TODO.md %d -> %d bytes" % (len(moved), len(s), len(new)))


if __name__ == "__main__":
    main()
