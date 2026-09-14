#!/usr/bin/env python3
"""Charm Hyper credits: one tiny request, prints the remaining hypercredits and today's use against the
subscription's 250/day (the user's rule from 2026-09-14: spend all of it every day).
usage: python3 tools/hyper_credits.py [--min N]   (exit 1 when remaining < N)"""
import json, os, sys, urllib.request
key = open(os.path.expanduser("~/.charmhyper_key")).read().strip()
req = urllib.request.Request("https://hyper.charm.land/v1/chat/completions", data=json.dumps({"model": "qwen3.8-flash", "messages": [{"role": "user", "content": "ok"}], "max_tokens": 1}).encode(), headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
d = json.load(urllib.request.urlopen(req, timeout=60))
rem = (d.get("usage", {}).get("remaining") or {}).get("hypercredits")
print("hyper: remaining %.1f of 250 hypercredits (%.1f used today, %.0f%%)" % (rem, 250 - rem, 100 * (250 - rem) / 250) if rem is not None else "hyper: %s" % d)
if "--min" in sys.argv and rem is not None and rem < float(sys.argv[sys.argv.index("--min") + 1]): sys.exit(1)
