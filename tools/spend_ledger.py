#!/usr/bin/env python3
"""Where the OpenRouter money went: turns, cost and cache reads per role and model, from pi's session
files (HANDOFF §13 step 4, "usage logging"). Reads every run under /tmp/bn-pi and any extra session
dirs given.

usage: python3 tools/spend_ledger.py [extra session dir ...] [--by-run]
"""
import collections, glob, json, os, sys


def scan(path, role, tot):
    for line in open(path):
        try:
            e = json.loads(line)
        except ValueError:
            continue
        m = e.get("message") if isinstance(e, dict) else None
        if isinstance(m, dict) and m.get("role") == "assistant":
            u = m.get("usage") or {}
            k = (role, (m.get("model") or "?").split("/")[-1])
            t = tot[k]
            t[0] += 1
            t[1] += (u.get("cost") or {}).get("total", 0)
            t[2] += u.get("cacheRead", 0)
            t[3] += u.get("input", 0)
            t[4] += u.get("output", 0)


def ledger(dirs):
    tot = collections.defaultdict(lambda: [0, 0.0, 0, 0, 0])
    for d in dirs:
        for f in glob.glob(os.path.join(d, "*.jsonl")):
            scan(f, "coordinator", tot)
        for f in glob.glob(os.path.join(d, "subagent-artifacts", "*_transcript.jsonl")):
            scan(f, os.path.basename(f).split("_")[-3], tot)
    return tot


def show(title, tot):
    print("== " + title)
    print("%-14s %-22s %5s %8s %9s %8s %7s" % ("role", "model", "turns", "cost", "cacheRd k", "input k", "out k"))
    for (role, model), (n, c, cr, i, o) in sorted(tot.items(), key=lambda kv: -kv[1][1]):
        print("%-14s %-22s %5d %8.3f %9d %8d %7d" % (role, model, n, c, cr // 1000, i // 1000, o // 1000))
    print("total $%.2f" % sum(v[1] for v in tot.values()))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    runs = sorted(glob.glob("/tmp/bn-pi/*/session")) + args
    if "--by-run" in sys.argv:
        for r in runs:
            show(r, ledger([r]))
    else:
        show("all runs (%d)" % len(runs), ledger(runs))


if __name__ == "__main__":
    main()
