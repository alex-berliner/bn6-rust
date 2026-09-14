#!/usr/bin/env python3
"""The MiniMax coding plan's remaining quota, from its own endpoint (GET /v1/coding_plan/remains): the plan
meters a rolling 5-hour window and a weekly window, each reported as a remaining percentage. Prints one line
  minimax: remaining P% of the 5h window (resets in M min); weekly W% (resets in D.d days)
and with --min N exits 1 when the smaller of the two percentages is below N, 2 when the probe itself failed
(never treated as exhausted), 0 otherwise. The key is read from ~/.pi/agent/auth.json (never printed).
"""
import json, os, sys, time, urllib.request

def main():
    need = float(sys.argv[sys.argv.index("--min") + 1]) if "--min" in sys.argv else None
    try:
        key = json.load(open(os.path.expanduser("~/.pi/agent/auth.json")))["minimax"]["key"]
        req = urllib.request.Request("https://api.minimax.io/v1/coding_plan/remains", headers={"Authorization": "Bearer " + key})
        j = json.loads(urllib.request.urlopen(req, timeout=60).read().decode())
        g = next(m for m in j["model_remains"] if m.get("model_name") == "general")
        p5, pw = float(g["current_interval_remaining_percent"]), float(g["current_weekly_remaining_percent"])
        m5 = max(0.0, (g["end_time"] / 1000.0 - time.time()) / 60.0); dw = max(0.0, (g["weekly_end_time"] / 1000.0 - time.time()) / 86400.0)
    except Exception as e:
        print("minimax: probe error: %r" % (e,)); sys.exit(2)
    print("minimax: remaining %.0f%% of the 5h window (resets in %.0f min); weekly %.0f%% (resets in %.1f days)" % (p5, m5, pw, dw))
    if need is not None and min(p5, pw) < need: sys.exit(1)

if __name__ == "__main__":
    main()
