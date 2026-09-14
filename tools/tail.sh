#!/usr/bin/env bash
# A subscription's last credits. A run needs about a ticket's worth (start_above in providers.toml) to reach
# a landing before the watcher stops it at stop_below, so under that tools/run_day.sh starts no run; this
# spends what is left on single-shot sessions that need no landing: one judge pass per day (tomorrow's
# tickets, admitted by tools/judge_append.py), then a recon map (docs/recon/<ID>.md, which the coordinator
# hands to the worker) for every OPEN ticket that lacks one, until no candidate is above stop_below. The
# judge and recon models resolve from the run profile at the --tail level. usage: bash tools/tail.sh <run>
NAME="${1:?run profile}"
set -uo pipefail
cd "$(dirname "$0")/.."
mkdir -p docs/recon /tmp/bn-pi/tail
MODEL="$(python3 tools/roles.py model "$NAME" recon --tail 2>/dev/null)" || { echo "tail: no recon candidate of run $NAME has budget; nothing to spend"; exit 0; }
PROV="${MODEL%%/*}"
mark="/tmp/bn-pi/tail/judge_${NAME}_$(date +%F)"
if [ ! -f "$mark" ]; then
  touch "$mark"
  f="$(BN_RUN="$NAME" bash tools/pi_judge.sh 2>/dev/null | awk '{print $1}')"
  [ -n "$f" ] && python3 tools/judge_append.py "$f" && git push -q origin main 2>/dev/null
fi
ROLE="$(awk 'BEGIN{n=0} /^---$/{n++; next} n>=2' .pi/roles/recon.md)"
for t in $(python3 tools/next_ticket.py --list 2>/dev/null | awk '$2=="OPEN"{print $1}'); do
  [ -f "docs/recon/$t.md" ] && continue
  python3 tools/roles.py budget "$PROV" --stop >/dev/null 2>&1 || { echo "tail: $PROV balance gone"; exit 0; }
  Q="$(python3 tools/next_ticket.py --id "$t" --results 0 2>/dev/null | head -c 7000)"
  [ -n "$Q" ] || continue
  S="/tmp/bn-pi/tail/$t-$(date +%H%M%S)"; mkdir -p "$S"
  timeout 1500 pi -p --approve --no-session --mode json --model "$MODEL" --thinking medium \
    --tools read,grep,find,ls,bash \
    "$ROLE

The question: for the ticket below, map where in reference/bn6f and src/ the behaviour it names lives, with the code, the RAM it touches, and the cheapest runtime check for each causal link. Do not edit anything and do not run captures; reading and grep only.

$Q" > "$S/events.jsonl" 2> "$S/stderr.txt" < /dev/null
  python3 - "$S/events.jsonl" "docs/recon/$t.md" "$t" "$MODEL" <<'PY'
import json, sys
last, cost = "", 0.0
for line in open(sys.argv[1]):
    try: e = json.loads(line)
    except ValueError: continue
    m = e.get("message") if isinstance(e, dict) else None
    if isinstance(m, dict) and m.get("role") == "assistant":
        cost += ((m.get("usage") or {}).get("cost") or {}).get("total", 0) or 0
        t = " ".join(c.get("text", "") for c in m.get("content", []) if c.get("type") == "text").strip()
        if t: last = t
if len(last) < 200: sys.exit(1)
open(sys.argv[2], "w").write("# Recon map for %s (%s, $%.4f nominal; every causal link unverified)\n\n%s\n" % (sys.argv[3], sys.argv[4], cost, last))
print("recon %s: %d chars, $%.4f" % (sys.argv[3], len(last), cost))
PY
  if [ -f "docs/recon/$t.md" ]; then
    ( exec 9>/tmp/bn-land.lock; flock -w 600 9 && git add "docs/recon/$t.md" && git commit -q -m "recon map for $t (tools/tail.sh, end-of-day $PROV credits)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" && git push -q origin main ) 2>/dev/null
  fi
done
echo "tail: every OPEN ticket has a recon map; $(python3 tools/roles.py budget "$PROV" --stop 2>/dev/null | tail -1)"
