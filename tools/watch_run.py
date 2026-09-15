#!/usr/bin/env python3
"""A live, readable view of a coordinator run for a human at a terminal (the "view" window of the run's tmux
session): the coordinator's turns from events.jsonl (its text and tool calls, tool results in one line), every
worker's, verifier's and recon's turns from their transcripts under session/subagent-artifacts (pi writes them
as they go), and every line of status.log. Each line is tagged with who it came from.
usage: python3 tools/watch_run.py <run dir>   (Ctrl-C leaves; the run keeps going)"""
import glob, json, os, subprocess, sys, threading, time

RUN = sys.argv[1]; EV = os.path.join(RUN, "events.jsonl"); ST = os.path.join(RUN, "status.log")
ART = os.path.join(RUN, "session", "subagent-artifacts")
lock = threading.Lock()


def out(s):
    with lock:
        print(s); sys.stdout.flush()


def stamp(ms=None):
    return time.strftime("%H:%M:%S", time.localtime((ms or time.time() * 1000) / 1000))


def show_message(who, m):
    """an assistant or toolResult message object, printed compactly"""
    if m.get("role") == "assistant":
        t = " ".join(c.get("text", "") for c in m.get("content", []) if c.get("type") == "text").strip()
        if t: out("[%s] %s: %s" % (stamp(m.get("timestamp")), who, t[:500].replace("\n", " ")))
        for c in m.get("content", []):
            if c.get("type") == "toolCall":
                out("[%s] %s   -> %s %s" % (stamp(m.get("timestamp")), who, c.get("name"), json.dumps(c.get("arguments"))[:180]))
        if m.get("errorMessage"): out("[%s] %s   !! %s" % (stamp(m.get("timestamp")), who, str(m["errorMessage"])[:200]))
    elif m.get("role") == "toolResult":
        c = m.get("content")
        t = " ".join(x.get("text", "") for x in c if isinstance(x, dict) and x.get("type") == "text").strip() if isinstance(c, list) else (c if isinstance(c, str) else "")
        if t or m.get("isError"):      # children's transcripts record calls but not outputs (content null): print those only when there is something
            out("           %s <- %s%s: %s" % (who, m.get("toolName"), " (error)" if m.get("isError") else "", t[:140].replace("\n", " | ")))


def tail_lines(path):
    """yield lines appended to a file, forever"""
    with open(path) as f:
        while True:
            line = f.readline()
            if line: yield line
            else: time.sleep(1)


def follow_coordinator():
    while not os.path.exists(EV): time.sleep(1)
    for line in tail_lines(EV):
        if not line.startswith("{"): continue
        try: e = json.loads(line)
        except ValueError: continue
        if e.get("type") == "turn_end" and isinstance(e.get("message"), dict): show_message("coordinator", e["message"])


def follow_status():
    while not os.path.exists(ST): time.sleep(1)
    for line in tail_lines(ST):
        if line.strip(): out("[status] " + line.rstrip())


def follow_transcript(path):
    name = os.path.basename(path); role = name.split("_")[1] if "_" in name else "child"
    who = "%s#%s" % (role, name[:4])
    for line in tail_lines(path):
        try: e = json.loads(line)
        except ValueError: continue
        if isinstance(e, dict) and e.get("role") in ("assistant", "toolResult"): show_message(who, e)


def scan_children():
    seen = set()
    while True:
        for p in glob.glob(os.path.join(ART, "*_transcript.jsonl")):
            if p not in seen:
                seen.add(p); out("[%s] child started: %s" % (stamp(), os.path.basename(p)))
                threading.Thread(target=follow_transcript, args=(p,), daemon=True).start()
        time.sleep(5)


def main():
    out("run %s (%s): coordinator, children and status lines as they happen; Ctrl-C leaves, the run keeps going\n"
        % (RUN, open(os.path.join(RUN, "run")).read().strip() if os.path.exists(os.path.join(RUN, "run")) else "?"))
    for fn in (follow_coordinator, follow_status, scan_children):
        threading.Thread(target=fn, daemon=True).start()
    while True: time.sleep(3600)


if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: pass
