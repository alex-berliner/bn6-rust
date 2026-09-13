#!/usr/bin/env python3
"""Print the first OPEN ticket in TODO.md -- and only that -- so agents read ~1k tokens instead of the
whole 33k-token file. Adds the Result paragraphs of earlier tickets on the same objective (F5 for F5b),
and the section's shared procedure paragraph if one follows the tickets.

usage: python3 tools/next_ticket.py [--id F12] [--results N] [--list]
  --id       print that ticket instead of the first OPEN one
  --results  also print the Result paragraphs of the N tickets before it in the section (default 1)
  --list     one line per ticket: id, status, title
"""
import argparse, os, re, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
HEAD = re.compile(r"^### ([A-Z]+\d+[a-z]?)\. (.*?)\s*\*\((\w+)\b.*\)\*\s*$", re.M)


def tickets(text):
    heads = list(HEAD.finditer(text))
    out = []
    for i, m in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(text)
        # a section heading ("## ") ends a ticket too
        sec = re.search(r"^## ", text[m.end():end], re.M)
        if sec:
            end = m.end() + sec.start()
        out.append({"id": m.group(1), "title": m.group(2), "status": m.group(3),
                    "start": m.start(), "end": end, "body": text[m.start():end].rstrip() + "\n"})
    return out


def files_of(body):
    m = re.search(r"^\*\*Files\.\*\*\s*(.+?)$", body, re.M)
    if not m:
        return None
    return [f.strip().rstrip(".") for f in re.split(r"[,;]\s*", m.group(1)) if f.strip()]


def overlap(a, b):
    for x in a:
        for y in b:
            if x == y or x.startswith(y.rstrip("/") + "/") or y.startswith(x.rstrip("/") + "/"):
                return True
    return False


def pair_for(first, others):
    fa = files_of(first["body"])
    if not fa:
        return None
    for o in others:
        fb = files_of(o["body"])
        if fb and not overlap(fa, fb):
            return o
    return None


def result_para(body):
    m = re.search(r"^\*\*Result\.\*\*.*?(?=\n\n|\Z)", body, re.M | re.S)
    return m.group(0) if m else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--id"); ap.add_argument("--results", type=int, default=1); ap.add_argument("--list", action="store_true")
    ap.add_argument("--pair", action="store_true", help="also print the next OPEN ticket whose **Files.** do not overlap the first's")
    a = ap.parse_args()
    text = open(os.path.join(ROOT, "TODO.md")).read()
    ts = tickets(text)
    if a.list:
        for t in ts:
            print("%-5s %-9s %s" % (t["id"], t["status"], t["title"]))
        return
    if a.id:
        pick = [t for t in ts if t["id"] == a.id]
    else:
        pick = [t for t in ts if t["status"] == "OPEN"]
    if not pick:
        sys.exit("no OPEN ticket" if not a.id else "no ticket %s" % a.id)
    t = pick[0]
    idx = ts.index(t)
    if a.pair:
        partner = pair_for(t, [x for x in ts if x["status"] == "OPEN" and x is not t])
        if partner:
            print(t["body"]); print("=== PAIR (disjoint files; may run concurrently) ===\n"); print(partner["body"])
        else:
            print(t["body"]); print("=== NO PAIR ===")
        return
    base = re.match(r"[A-Z]+\d+", t["id"]).group(0)
    print(t["body"])
    shown = 0
    for prev in reversed(ts[:idx]):
        same = re.match(r"[A-Z]+\d+", prev["id"]).group(0) == base
        if same or shown < a.results:
            r = result_para(prev["body"])
            if r:
                print("--- %s (%s): %s\n%s\n" % (prev["id"], prev["status"], prev["title"], r))
                if not same:
                    shown += 1
        if shown >= a.results and not same:
            break
    # shared procedure paragraph anywhere in the ticket's section
    sec_start = text.rfind("\n## ", 0, t["start"])
    sec_next = re.search(r"^## ", text[t["end"]:], re.M)
    section = text[sec_start:(t["end"] + sec_next.start()) if sec_next else len(text)]
    m = re.search(r"^\*\*Common to .*?(?=\n\n|\Z)", section, re.M | re.S)
    if m and m.group(0) not in t["body"]:
        print("--- shared procedure\n" + m.group(0))


if __name__ == "__main__":
    main()
