#!/usr/bin/env python3
"""Print real OpenRouter spend (from OpenRouter, not pi's estimate) and exit 1 if what is actually
spendable is below --min dollars. Spendable is the LOWER of the key's remaining limit and the
account's remaining credit (total_credits - total_usage): a key limit above the account balance
does not make money. Reads the key pi stores in ~/.pi/agent/auth.json.

usage: python3 tools/or_spend.py [--min 3.0]
prints: openrouter: used today $X, total $Y, limit L, remaining $R (account $A, key $K)
"""
import argparse, json, os, sys, urllib.request

ap = argparse.ArgumentParser()
ap.add_argument("--min", type=float, default=0.0)
a = ap.parse_args()
auth = json.load(open(os.path.expanduser("~/.pi/agent/auth.json")))["openrouter"]
key = auth if isinstance(auth, str) else (auth.get("key") or auth.get("apiKey"))


def get(path):
    req = urllib.request.Request("https://openrouter.ai/api/v1/" + path, headers={"Authorization": "Bearer " + key})
    return json.load(urllib.request.urlopen(req, timeout=30))["data"]


k = get("key")
acct = None
try:
    c = get("credits")
    acct = float(c["total_credits"]) - float(c["total_usage"])
except Exception:
    pass
key_rem = k.get("limit_remaining")
cands = [x for x in (key_rem, acct) if x is not None]
rem = min(cands) if cands else None
print("openrouter: used today $%.2f, total $%.2f, limit %s, remaining %s (account %s, key %s)" % (
    k.get("usage_daily") or 0, k.get("usage") or 0, k.get("limit"),
    "unlimited" if rem is None else "$%.2f" % rem,
    "?" if acct is None else "$%.2f" % acct, "unlimited" if key_rem is None else "$%.2f" % key_rem))
if rem is not None and rem < a.min:
    print("STOP: spendable $%.2f is below the $%.2f floor" % (rem, a.min))
    sys.exit(1)
