#!/usr/bin/env python3
"""The OpenCode Go plan has no balance endpoint (2026-09-16): its limits are per model, per 5-hour window and per
month, and the gateway answers an exhausted model with an error. So this probe sends one tiny request to the run's
worker model through the Go gateway and reports open (remaining 1) or exhausted (remaining 0), plus this
machine's own request count for the last five hours from the pacer's log. With --min N: exit 1 when exhausted,
2 when the probe itself failed. The key is read from ~/.pi/agent/auth.json (never printed).
"""
import json, os, re, sys, time, urllib.request, urllib.error, tomllib

def main():
    need = float(sys.argv[sys.argv.index("--min") + 1]) if "--min" in sys.argv else None
    try:
        key = json.load(open(os.path.expanduser("~/.pi/agent/auth.json")))["opencode"]["key"]
        cfg = tomllib.load(open(os.path.join(os.path.dirname(__file__), "..", "providers.toml"), "rb"))
        run = next((r for r, v in cfg["runs"].items() if any(m.startswith("opencode/") for m in v["worker"])), None)
        model = next(m for m in cfg["runs"][run]["worker"] if m.startswith("opencode/")).split("/", 1)[1] if run else "glm-5.3-flash"
        body = json.dumps({"model": model, "messages": [{"role": "user", "content": "Reply with the single word: ok"}], "max_tokens": 5}).encode()
        req = urllib.request.Request("https://opencode.ai/zen/go/v1/chat/completions", data=body, method="POST",
                                     headers={"Authorization": "Bearer " + key, "Content-Type": "application/json", "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) pi-agent", "x-opencode-session": "probe"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r: status = r.status
        except urllib.error.HTTPError as e:
            status = e.code; msg = e.read().decode()[:200]
            if status in (401, 402, 429) or "exhaust" in msg.lower() or "limit" in msg.lower(): status = 429
            elif status >= 500: raise
    except Exception as e:
        print("opencode: probe error: %r" % (e,)); sys.exit(2)
    recent = 0; log = "/tmp/bn-pacer/opencode.log"
    if os.path.exists(log):
        cutoff = time.time() - 5 * 3600
        for line in open(log):
            m = re.match(r"^(\d\d):(\d\d):(\d\d) /", line)
            if m: recent += 1     # the log has no date; count lines (the pacer log is rotated by run_day daily)
    print("opencode: remaining %d (model %s %s); this machine's requests in the log: %d" % (1 if status == 200 else 0, model, "open" if status == 200 else "exhausted (%d)" % status, recent))
    if need is not None and status != 200: sys.exit(1)

if __name__ == "__main__":
    main()
