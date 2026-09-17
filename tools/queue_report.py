#!/usr/bin/env python3
"""Is there enough work for the workers? The ledger counts what got done; nothing counted whether a run had
anything to do. With several providers sharing one queue a coordinator can start, find every open ticket
already claimed, and stop in four turns -- which looks like a healthy short session in every other report.

This reads the queue, the claims, the runs and the launcher log and answers: how many tickets are open and
unclaimed, how they were supplied against how fast they were consumed, which runs starved, and how much
provider time went unused for lack of work. Printed by the daily roundup; a shortfall trips the auditor.

  python3 tools/queue_report.py [--since 24]
"""
import argparse, datetime, glob, json, os, re, subprocess, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..")); os.chdir(ROOT)
CLAIMS = "/tmp/bn-claims"


def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout


def live_runs():
    out = []
    for d in sorted(glob.glob("/tmp/bn-pi/2*")):
        if os.path.exists(os.path.join(d, "exit")): continue
        if subprocess.run(["pgrep", "-f", "session-dir %s/session" % d], capture_output=True).returncode == 0:
            out.append((os.path.basename(d), open(os.path.join(d, "run")).read().strip() if os.path.exists(os.path.join(d, "run")) else "?"))
    return out


def slots():
    """worker slots the scheduled profiles would run"""
    import tomllib
    cfg = tomllib.load(open("providers.toml", "rb")); n = 0
    for run in cfg["schedule"]["runs"]:
        w = cfg["runs"][run]["workers"]
        n += w if isinstance(w, int) else 2
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", type=float, default=24.0)
    a = ap.parse_args()
    listing = sh("python3 tools/next_ticket.py --list 2>/dev/null")
    open_ids = [l.split()[0] for l in listing.splitlines() if len(l.split()) > 1 and l.split()[1] == "OPEN"]
    claimed = set(os.listdir(CLAIMS)) if os.path.isdir(CLAIMS) else set()
    live = {d for d, _ in live_runs()}
    held = set()
    for t in claimed:
        p = os.path.join(CLAIMS, t)
        try: run = open(p).read().strip()
        except OSError: continue
        if os.path.basename(run) in live: held.add(t)
    free = [t for t in open_ids if t not in held]
    n_slots = slots()
    since = "%d hours ago" % int(a.since)
    admitted = len(re.findall(r"[A-Z]+\d+[a-z]?", " ".join(re.findall(r"judge-admitted ([^\n(]*)", sh("git log --since='%s' --format=%%s main" % since)))))
    closed = len(re.findall(r"^TODO [A-Z]+\d+[a-z]? (?:DONE|PARTIAL|BLOCKED|NEGATIVE)", sh("git log --since='%s' --format=%%s main" % since), re.M))
    batches = sh("git log --since='%s' --format=%%s main" % since).count("judge-admitted")

    # runs that started and found nothing: few turns and an early end
    starved = []
    cutoff = datetime.datetime.now().timestamp() - a.since * 3600
    for d in sorted(glob.glob("/tmp/bn-pi/2*")):
        ev = os.path.join(d, "events.jsonl")
        if not os.path.exists(ev) or os.path.getmtime(ev) < cutoff: continue
        turns = 0; last = ""
        for line in open(ev, errors="replace"):
            if '"role":"assistant"' not in line: continue
            try: e = json.loads(line)
            except ValueError: continue
            if e.get("type") != "turn_end": continue
            m = e.get("message") or {}
            turns += 1
            t = " ".join(c.get("text", "") for c in m.get("content", []) if c.get("type") == "text").strip()
            if t: last = t
        if turns and turns <= 8 and re.search(r"no OPEN|claimed|nothing to|queue", last, re.I):
            starved.append((os.path.basename(d), open(os.path.join(d, "run")).read().strip() if os.path.exists(os.path.join(d, "run")) else "?", turns))
    log = sh("tail -400 /tmp/bn-pi/run_day.log")
    idle_ticks = len(re.findall(r"queue empty and the judge is at its daily cap|nothing running", log))

    print("| measure | value |"); print("|---|---|")
    print("| worker slots the schedule would fill | %d |" % n_slots)
    print("| tickets OPEN and unclaimed right now | %d (%s) |" % (len(free), ", ".join(free[:6]) or "none"))
    print("| tickets admitted in the window | %d in %d judge batches |" % (admitted, batches))
    print("| tickets closed in the window | %d |" % closed)
    print("| runs that started and found nothing | %d%s |" % (len(starved), (": " + ", ".join("%s/%s in %d turns" % s for s in starved[:4])) if starved else ""))
    print("| launcher ticks with nothing to run | %d |" % idle_ticks)
    short = (admitted < closed) or (len(free) < n_slots) or bool(starved)
    if short:
        print("\nSupply is behind demand: %d admitted against %d closed, %d unclaimed for %d slots%s."
              % (admitted, closed, len(free), n_slots, ", %d starved starts" % len(starved) if starved else ""))
    print("\nQUEUE-TRIGGER: %s" % ("yes" if short else "no"))


if __name__ == "__main__":
    main()
