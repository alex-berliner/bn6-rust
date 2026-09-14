#!/usr/bin/env python3
"""The MiniMax coding plan's remaining quota, from its own endpoint (GET /v1/coding_plan/remains): a rolling
5-hour window and a weekly window, each reported as a remaining percentage. The weekly window is the binding
one (a ticket cycle costs about 0.7% of the week and 5% of a 5-hour window, measured 2026-09-14), so the plan
is spent evenly: each calendar day may use the weekly remainder at the start of that day divided by the days
left in the week (the day's ALLOWANCE), so the week lasts the week and nothing is left at its reset. Prints
  minimax: remaining P% of the 5h window (resets in M min); weekly W% (resets in D.d days); today used U% of an allowance of A%
and with --min N exits 1 when the 5-hour or weekly percentage is below N OR the day's allowance is spent,
2 when the probe itself failed (never treated as exhausted), 0 otherwise. The key is read from
~/.pi/agent/auth.json (never printed). The day's starting point is kept in /tmp/bn-pi/quota/minimax-<date>.
"""
import datetime, json, os, sys, time, urllib.request


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
    # the day's allowance: the weekly remainder at the day's first probe, divided by the days left then
    os.makedirs("/tmp/bn-pi/quota", exist_ok=True)
    snap = "/tmp/bn-pi/quota/minimax-%s" % datetime.date.today().isoformat()
    if not os.path.exists(snap):
        json.dump({"weekly_at_start": pw, "days_left": max(1.0, dw)}, open(snap, "w"))
    s = json.load(open(snap)); allowance = s["weekly_at_start"] / max(1.0, s["days_left"]); used = s["weekly_at_start"] - pw
    if pw > s["weekly_at_start"]:        # the week reset during the day: start the day over
        json.dump({"weekly_at_start": pw, "days_left": max(1.0, dw)}, open(snap, "w")); allowance, used = pw / max(1.0, dw), 0.0
    print("minimax: remaining %.0f%% of the 5h window (resets in %.0f min); weekly %.0f%% (resets in %.1f days); today used %.1f%% of an allowance of %.1f%%"
          % (p5, m5, pw, dw, used, allowance))
    if need is not None and (min(p5, pw) < need or used >= allowance): sys.exit(1)


if __name__ == "__main__":
    main()
