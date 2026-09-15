#!/usr/bin/env python3
"""Print the first OPEN ticket in TODO.md -- and only that -- so agents read ~1k tokens instead of the
whole 33k-token file. Adds the Result paragraphs of earlier tickets on the same objective (F5 for F5b),
and the section's shared procedure paragraph if one follows the tickets.

usage: python3 tools/next_ticket.py [--id F12] [--results N] [--list]
  --id       print that ticket instead of the first OPEN one
  --results  also print the Result paragraphs of the N tickets before it in the section (default 1)
  --list     one line per ticket: id, status, title
"""
import argparse, fcntl, os, re, subprocess, sys

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


def pair_for_all(chosen, others):
    """the first of `others` whose **Files.** overlap none of the already chosen tickets'"""
    fas = [files_of(c["body"]) for c in chosen]
    if not all(fas):
        return None
    for o in others:
        fb = files_of(o["body"])
        if fb and all(not overlap(fa, fb) for fa in fas):
            return o
    return None


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

CLAIMS = "/tmp/bn-claims"


def run_alive(run):
    """a run dir's coordinator is alive: no exit file and a pi process on its session dir"""
    if not run or not os.path.isdir(run) or os.path.exists(os.path.join(run, "exit")):
        return False
    return subprocess.run(["pgrep", "-f", "session-dir %s/session" % run], capture_output=True).returncode == 0


def claimed_by_other(tid, me):
    """the ticket is claimed by another run that is still alive (a dead run's claims expire)"""
    p = os.path.join(CLAIMS, tid)
    if not os.path.exists(p):
        return False
    run = open(p).read().strip()
    if run == me:
        return False
    if run_alive(run):
        return True
    os.remove(p); return False


def claim(tids, me):
    os.makedirs(CLAIMS, exist_ok=True)
    for tid in tids:
        open(os.path.join(CLAIMS, tid), "w").write(me)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--id"); ap.add_argument("--results", type=int, default=1); ap.add_argument("--list", action="store_true")
    ap.add_argument("--pair", nargs="?", const=2, type=int, default=0, help="print up to N OPEN tickets whose **Files.** overlap none of the earlier ones (N in flight; default 2)")
    ap.add_argument("--claim", nargs="?", const="", default=None, metavar="RUN",
                    help="mark the printed OPEN tickets as this run's (the run dir; default from $BN_PI_STATUS) and skip tickets another live run has claimed")
    a = ap.parse_args()
    me = None
    if a.claim is not None:
        me = a.claim or os.path.dirname(os.environ.get("BN_PI_STATUS", "")) or "manual"
        os.makedirs(CLAIMS, exist_ok=True)
        lock = open(os.path.join(CLAIMS, ".lock"), "w"); fcntl.flock(lock, fcntl.LOCK_EX)
    text = open(os.path.join(ROOT, "TODO.md")).read()
    ts = tickets(text)
    if me is not None:
        for t in ts:
            if t["status"] == "OPEN" and claimed_by_other(t["id"], me):
                t["status"] = "CLAIMED"          # another live run's; invisible to this one
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
        chosen = [t]
        for _ in range(max(a.pair, 2) - 1):
            partner = pair_for_all(chosen, [x for x in ts if x["status"] == "OPEN" and x not in chosen])
            if not partner:
                break
            chosen.append(partner)
        if me is not None:
            claim([c["id"] for c in chosen], me)
        print(t["body"])
        for c in chosen[1:]:
            print("=== PAIR (disjoint files; may run concurrently) ===\n"); print(c["body"])
        if len(chosen) < 2:
            print("=== NO PAIR ===")
        return
    base = re.match(r"[A-Z]+\d+", t["id"]).group(0)
    if me is not None and t["status"] == "OPEN":
        claim([t["id"]], me)
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
    # the work logs of this objective (docs/worklog/<base>*.md): what earlier workers tried, newest first, two at most
    import glob as _glob
    logs = sorted((f for f in _glob.glob(os.path.join(ROOT, "docs", "worklog", base + "*.md"))), key=os.path.getmtime, reverse=True)
    own = os.path.join(ROOT, "docs", "worklog", t["id"] + ".md")
    for f in ([own] if os.path.exists(own) and own not in logs[:2] else []) + logs[:2]:
        body_log = open(f).read().strip()
        if body_log:
            print("--- work log %s (what was tried before; read it first)\n%s\n" % (os.path.basename(f), body_log[:3500] + (" [...]" if len(body_log) > 3500 else "")))
    # shared procedure paragraph anywhere in the ticket's section
    sec_start = text.rfind("\n## ", 0, t["start"])
    sec_next = re.search(r"^## ", text[t["end"]:], re.M)
    section = text[sec_start:(t["end"] + sec_next.start()) if sec_next else len(text)]
    m = re.search(r"^\*\*Common to .*?(?=\n\n|\Z)", section, re.M | re.S)
    if m and m.group(0) not in t["body"]:
        print("--- shared procedure\n" + m.group(0))


if __name__ == "__main__":
    main()
