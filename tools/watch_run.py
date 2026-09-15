#!/usr/bin/env python3
"""A live, readable view of a coordinator run for a human at a terminal (the "view" window of the run's tmux
session): the coordinator's turns from events.jsonl (its text and tool calls, tool results in one line) and
every line of status.log, as they happen. usage: python3 tools/watch_run.py <run dir>   (Ctrl-C to leave)"""
import json, os, subprocess, sys, time

RUN = sys.argv[1]; EV = os.path.join(RUN, "events.jsonl"); ST = os.path.join(RUN, "status.log")
print("run %s  (%s)  -- coordinator turns and status lines; Ctrl-C leaves, the run keeps going\n" % (RUN, open(os.path.join(RUN, "run")).read().strip() if os.path.exists(os.path.join(RUN, "run")) else "?"))


def show(e):
    t = e.get("type"); m = e.get("message") or {}
    if t == "turn_end" and m.get("role") == "assistant":
        stamp = time.strftime("%H:%M:%S", time.localtime((m.get("timestamp") or time.time() * 1000) / 1000))
        text = " ".join(c.get("text", "") for c in m.get("content", []) if c.get("type") == "text").strip()
        if text: print("[%s] coordinator: %s" % (stamp, text[:600].replace("\n", " ")))
        for c in m.get("content", []):
            if c.get("type") == "toolCall":
                args = json.dumps(c.get("arguments"))
                print("[%s]   -> %s %s" % (stamp, c.get("name"), args[:200]))
        if m.get("errorMessage"): print("[%s]   !! %s" % (stamp, str(m["errorMessage"])[:200]))
    elif t == "turn_end" and m.get("role") == "toolResult":
        text = " ".join(c.get("text", "") for c in m.get("content", []) if c.get("type") == "text").strip()
        print("            <- %s: %s" % (m.get("toolName"), text[:160].replace("\n", " | ")))


def main():
    while not os.path.exists(EV): time.sleep(1)
    tail = subprocess.Popen(["tail", "-n", "+1", "-F", EV, ST], stdout=subprocess.PIPE, text=True)
    for line in tail.stdout:
        line = line.rstrip("\n")
        if line.startswith("==> "): continue
        if line.startswith("{"):
            try: show(json.loads(line))
            except ValueError: pass
        elif line.strip(): print("[status] " + line)
        sys.stdout.flush()


if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: pass
