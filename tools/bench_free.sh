#!/usr/bin/env bash
# Screen every tool-capable free model on OpenRouter with the replay benchmark on one archived ticket,
# sequentially (the free tier is 20 requests/min and 1000/day across all free models), a short wall
# clock each (a model that thrashes burns the day's quota in minutes). Appends one line per model to
# docs/benchmarks/free-models-<date>.md. usage: bash tools/bench_free.sh [ticket=F18d] [minutes=5]
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
T="${1:-F18d}"; MIN="${2:-5}"; OUT="docs/benchmarks/free-models-$(date +%Y-%m-%d).md"
SKIP="lyria|content-safety|openrouter/free|cohere/north-mini-code|gemma-4-31b"
MODELS=$(curl -s https://openrouter.ai/api/v1/models | python3 -c "
import json,sys
for m in sorted(json.load(sys.stdin)['data'], key=lambda m: m['id']):
    if m['id'].endswith(':free') and 'tools' in (m.get('supported_parameters') or []): print(m['id'])" | grep -vE "$SKIP")
[ -f "$OUT" ] || printf '# Free models on OpenRouter, replay of %s, %s min each (verdict / turns / minutes / cache hit)\n\n' "$T" "$MIN" > "$OUT"
for m in $MODELS; do
  line=$(python3 tools/replay_bench.py "$T" --model "openrouter/$m" --thinking off --minutes "$MIN" 2>&1 | grep -E "^$T:" | tail -1)
  d=$(ls -td /tmp/bn-pi/replay/*/ | head -1)
  hit=$(python3 - "$d/events.jsonl" <<'PY'
import json, sys
n = inp = cr = 0
for line in open(sys.argv[1]):
    try: e = json.loads(line)
    except ValueError: continue
    m = e.get("message") if isinstance(e, dict) else None
    if isinstance(m, dict) and m.get("role") == "assistant":
        u = m.get("usage") or {}; n += 1; inp += u.get("input", 0); cr += u.get("cacheRead", 0)
print("%d turns, cache %.0f%%" % (n, 100.0 * cr / (cr + inp) if cr + inp else 0))
PY
)
  err=$(grep -oE 'free-models-per-day' "$d/stderr.txt" "$d/events.jsonl" 2>/dev/null | head -1)
  echo "- $m: ${line#$T: } [$hit]${err:+ DAILY QUOTA HIT}" | cut -c1-220 >> "$OUT"
  [ -n "$err" ] && { echo "- (stopped: daily free quota exhausted; rerun tomorrow for the rest)" >> "$OUT"; break; }
done
echo "done $(date +%H:%M)" >> "$OUT"
