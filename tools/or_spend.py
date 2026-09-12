#!/usr/bin/env python3
"""Print the OpenRouter key's real spend (from OpenRouter, not pi's estimate) and exit 1 if the
remaining limit is below --min dollars. Reads the key pi stores in ~/.pi/agent/auth.json.

usage: python3 tools/or_spend.py [--min 3.0]
"""
import argparse, json, os, sys, urllib.request

ap = argparse.ArgumentParser()
ap.add_argument("--min", type=float, default=0.0)
a = ap.parse_args()
auth = json.load(open(os.path.expanduser("~/.pi/agent/auth.json")))["openrouter"]
key = auth if isinstance(auth, str) else (auth.get("key") or auth.get("apiKey"))
req = urllib.request.Request("https://openrouter.ai/api/v1/key", headers={"Authorization": "Bearer " + key})
d = json.load(urllib.request.urlopen(req, timeout=30))["data"]
rem = d.get("limit_remaining")
print("openrouter: used today $%.2f, total $%.2f, limit %s, remaining %s" % (
    d.get("usage_daily") or 0, d.get("usage") or 0, d.get("limit"),
    "unlimited" if rem is None else "$%.2f" % rem))
if rem is not None and rem < a.min:
    print("STOP: remaining $%.2f is below the $%.2f floor" % (rem, a.min))
    sys.exit(1)
