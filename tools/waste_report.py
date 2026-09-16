#!/usr/bin/env python3
"""What the day's model usage spent on nothing: the waste the outcome ledger cannot see.

The ledger says a ticket was BLOCKED; it does not say the worker spent 45 minutes and 600,000 tokens first,
that a fifth of its turns died on provider errors, or that it called the same command eleven times in a row.
This reads the artifacts already on disk (each run's subagent-artifacts and the replay sessions) and reports,
per model and per session, the time and tokens that produced nothing, the provider errors, and the loops.
Free: nothing is sent anywhere. tools/daily_review.sh prints it and turns its thresholds into auditor triggers.

  python3 tools/waste_report.py [--since 24] [--json]
"""
import argparse, collections, glob, json, os, re, subprocess, sys, time

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..")); os.chdir(ROOT)
ERRORS = [("rate limit", re.compile(r"429|rate.?limit|too many requests", re.I)),
          ("stream truncated", re.compile(r"Stream ended without finish_reason", re.I)),
          ("connection", re.compile(r"Connection error|RemoteDisconnected|timed? ?out|ECONNRESET", re.I)),
          ("server error", re.compile(r"\b5\d\d\b|Internal server error", re.I)),
          ("out of credit", re.compile(r"out of credits|insufficient balance|billing", re.I))]


def sessions(since_h):
    """(kind, label, model, meta, transcript path) for every child session and replay in the window"""
    cutoff = time.time() - since_h * 3600
    for m in glob.glob("/tmp/bn-pi/*/session/subagent-artifacts/*_meta.json"):
        if os.path.getmtime(m) < cutoff: continue
        try: d = json.load(open(m))
        except (ValueError, OSError): continue
        yield ("child", d.get("agent", "?"), d.get("model", "?"), d, d.get("transcriptPath") or m.replace("_meta.json", "_transcript.jsonl"))
    for ev in glob.glob("/tmp/bn-pi/replay/*/events.jsonl"):
        if os.path.getmtime(ev) < cutoff: continue
        yield ("replay", "replay " + os.path.basename(os.path.dirname(ev)), None, None, ev)


def scan(path):
    """turns, tokens, minutes, error counts and the worst run of identical tool calls in one session file"""
    turns = tokens = 0; first = last = None; errs = collections.Counter(); seen_err = set()
    calls = []; model = None
    try: fh = open(path)
    except OSError: return None
    for line in fh:
        if '"role"' not in line: continue
        try: e = json.loads(line)
        except ValueError: continue
        m = e.get("message") if isinstance(e.get("message"), dict) else e
        if e.get("type") and e.get("type") not in ("turn_end",) and "message" in e: continue   # replay files repeat a message per event
        if m.get("role") != "assistant": continue
        turns += 1; u = m.get("usage") or {}
        tokens += (u.get("input", 0) or 0) + (u.get("output", 0) or 0)
        model = model or m.get("model") or (m.get("provider") and str(m.get("provider")))
        ts = m.get("timestamp") or e.get("timestamp")
        if ts: first = first or ts; last = ts
        em = m.get("errorMessage")
        if isinstance(em, str) and (m.get("id"), em[:80]) not in seen_err:
            seen_err.add((m.get("id"), em[:80]))
            for ename, rx in ERRORS:
                if rx.search(em): errs[ename] += 1; break
            else: errs["other"] += 1
        for c in m.get("content") or []:
            if isinstance(c, dict) and c.get("type") == "toolCall":
                calls.append(json.dumps([c.get("name"), c.get("arguments")], sort_keys=True)[:400])
    worst = run = 1
    for i in range(1, len(calls)):
        run = run + 1 if calls[i] == calls[i - 1] else 1
        worst = max(worst, run)
    mins = ((last - first) / 60000.0) if (first and last and last > first) else 0.0
    return dict(turns=turns, tokens=tokens, minutes=mins, errors=errs, repeat=worst if len(calls) else 0, calls=len(calls), model=model)


def landed_tickets(since_h):
    try:
        rows = json.loads(subprocess.run(["python3", "tools/ticket_ledger.py", "--since", str(since_h), "--json"], capture_output=True, text=True).stdout)
    except ValueError:
        return {}
    out = {}
    for r in rows:
        k = r["model"].split(":")[0]
        o = out.setdefault(k, dict(landed=set(), turns=0, cost=0.0, min=0.0))
        if r.get("landed") and r["ticket"] != "?": o["landed"].add(r["ticket"])
        o["turns"] += r.get("turns", 0); o["cost"] += r.get("cost", 0.0); o["min"] += r.get("min", 0.0)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", type=float, default=24.0); ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    per = collections.defaultdict(lambda: dict(sessions=0, turns=0, tokens=0, minutes=0.0, errors=collections.Counter(), loops=[], long=[]))
    flagged = []
    for kind, label, model, meta, path in sessions(a.since):
        s = scan(path)
        if not s or not s["turns"]: continue
        key = (model or s["model"] or "?").split(":")[0]
        p = per[key]
        p["sessions"] += 1; p["turns"] += s["turns"]; p["tokens"] += s["tokens"]; p["minutes"] += s["minutes"]
        p["errors"] += s["errors"]
        name = (os.path.basename(os.path.dirname(path)) if os.path.basename(path) == "events.jsonl" else os.path.basename(path))[:30]
        if s["repeat"] >= 4: p["loops"].append((name, s["repeat"]))
        if s["minutes"] >= 40: p["long"].append((name, round(s["minutes"])))
        if sum(s["errors"].values()) >= 3: flagged.append("%s %s: %d provider errors in %d turns (%s)" % (label, name, sum(s["errors"].values()), s["turns"], dict(s["errors"])))
        if s["repeat"] >= 6: flagged.append("%s %s: the same tool call %d times in a row" % (label, name, s["repeat"]))
    led = landed_tickets(a.since)
    if a.json: print(json.dumps({k: {**v, "errors": dict(v["errors"])} for k, v in per.items()}, default=str)); return
    print("| model | sessions | turns | tokens | minutes | provider errors | per landed ticket |")
    print("|---|---|---|---|---|---|---|")
    tot_err = tot_turn = 0
    for k, v in sorted(per.items(), key=lambda kv: -kv[1]["turns"]):
        e = sum(v["errors"].values()); tot_err += e; tot_turn += v["turns"]
        l = led.get(k.split("/")[-1], led.get(k, {}))
        n = len(l.get("landed", []) or [])
        per_landed = ("%d turns, %.0f min" % (v["turns"] / n, v["minutes"] / n)) if n else "nothing landed"
        print("| %s | %d | %d | %d | %.0f | %s | %s |" % (k, v["sessions"], v["turns"], v["tokens"], v["minutes"],
              ", ".join("%s %d" % (a, b) for a, b in v["errors"].most_common()) or "none", per_landed))
    rate = (100.0 * tot_err / tot_turn) if tot_turn else 0.0
    print("\nprovider errors per 100 turns: %.1f (%d over %d turns)" % (rate, tot_err, tot_turn))
    loops = [(k, n, r) for k, v in per.items() for n, r in v["loops"]]
    if loops: print("repeated identical tool calls: " + "; ".join("%s %s x%d" % (k.split('/')[-1], n, r) for k, n, r in loops[:6]))
    longs = [(k, n, m) for k, v in per.items() for n, m in v["long"]]
    if longs: print("sessions at or past 40 minutes: " + "; ".join("%s %s %dmin" % (k.split('/')[-1], n, m) for k, n, m in longs[:6]))
    for f in flagged[:8]: print("- " + f)
    print("\nWASTE-TRIGGER: yes" if (rate >= 2.0 or any(r >= 6 for _, _, r in loops)) else "\nWASTE-TRIGGER: no")


if __name__ == "__main__":
    main()
