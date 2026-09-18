#!/usr/bin/env bash
# One-shot "judge" session on the cheap tier: reads the short HANDOFF, the open ticket list, the
# BLOCKED results and the spend ledger, and proposes the next tickets in the R/F format to a file the
# user skims. It changes nothing (read-only tools, told not to edit). Moves ticket authoring off the
# Claude plan: a run costs about a cent.
#
# usage: bash tools/pi_judge.sh ["extra instruction"]     -> prints the proposal file path
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
# One model is not enough. A judge session that produces no ticket text is not rare and it is not one
# bug: on 2026-09-17, hyper/qwen3.8-flash ran 33 turns of file reading into the hard timeout, while
# minimax/MiniMax-M3 emitted a single 105-character thought ("Let me prune context and then check the
# latest open tickets") and stopped, with stopReason "stop" and no text block at all. Both left the
# queue empty and both looked like a successful run in every log. 9 of 37 sessions that day.
# So: try the candidates in turn, stop at the first that actually writes tickets, and bound the spend
# at two attempts -- a judge run is about nine cents and an empty queue idles six workers.
CANDIDATES="${BN_MODEL:-$(for r in $(python3 tools/roles.py schedule 2>/dev/null | sed -n 's/^RUNS="\(.*\)"/\1/p'); do
  python3 tools/roles.py model "$r" judge --tail 2>/dev/null || true
done | awk '!seen[$0]++' | head -2)}"
[ -n "$CANDIDATES" ] || CANDIDATES="$(python3 tools/roles.py pick judge --tail)"
mkdir -p docs/proposals /tmp/bn-pi/judge
STAMP="$(date +%Y%m%d-%H%M%S)"; OUT="docs/proposals/$STAMP.md"; SESS="/tmp/bn-pi/judge/$STAMP"
mkdir -p "$SESS"
CTX="$(python3 tools/next_ticket.py --list 2>/dev/null || true)"
SCOPE="$(sed -n '1,60p' docs/SCOPE.md 2>/dev/null || true)"
BLOCKED="$(grep -E '^- .* BLOCKED -- ' TODO.md TODO_ARCHIVE.md 2>/dev/null | cut -c1-400 || true)"
LEDGER="$(python3 tools/spend_ledger.py 2>/dev/null | tail -8 || true)"
for MODEL in $CANDIDATES; do
SESS="/tmp/bn-pi/judge/$STAMP-$(echo "$MODEL" | tr "/." "--")"; mkdir -p "$SESS"
echo "judge attempt: $MODEL"
timeout 1500 pi -p --approve --no-session --mode json \
  --model "$MODEL" --thinking high --tools read,grep,find,ls \
  "You are the judge for /home/box/Code/bn. Read HANDOFF.md (short) and AGENTS.md. Do not edit or run anything; you have read-only tools. ${1:-}

The completion ladder (docs/SCOPE.md; propose only tickets that advance an unmet milestone, lowest-numbered first unless a later one unblocks it):
$SCOPE

Open tickets:
$CTX

Blocked results:
$BLOCKED

Spend so far:
$LEDGER

Propose the next FIVE tickets, in the exact ticket format used in TODO.md, every part present or the ticket is refused by tools/judge_append.py: `### ID. title *(OPEN -- date)*` with a fresh ID, **Why.** with the measured facts, a **Files.** line naming the files the worker may touch, AT MOST THREE numbered **Do** steps each ending in a measurement, **Rules**, **Acceptance.** (what measured numbers close it) and **Measure and report.**, a **Coordinator:** note, and the docs/SCOPE.md milestone it advances (M1..M11). Keep each ticket under 5000 characters: name the facts and the measurements, do not narrate; every ticket is re-sent to a worker on every turn. THREE STEPS IS A HARD LIMIT and it is about the worker's budget, not about writing style. A step is not one action: "baseline the row" is three captures and three comparisons, and a measured worker spends 15 to 25 tool calls on a single step against a soft budget of 80 for the whole ticket. A six-step ticket therefore cannot be finished in one session -- the worker reaches step three, commits what it has and stamps PARTIAL, and the rest needs a follow-up ticket on a fresh branch. 27 of 83 unmerged branches on 2026-09-17 were exactly that. So scope each ticket to ONE measurable outcome a worker can reach in one sitting, and put the next outcome in the next ticket rather than in step four. Never continue an objective whose last ticket ended NEGATIVE or BLOCKED: that objective is closed until new evidence exists (a recon map or a measurement made after the close, which the ticket must quote under **New evidence.**); pick another item from the ladder instead. Two proposals in a row on one objective is the most you may make in a day. For an engine-core (M2) ticket the acceptance is a trace target (field, frames of the scene, first divergent frame) with verify_rows identical as the veto; for a content ticket it is the item's own scene and trace at 0; interaction rules need a scripted-input scenario (one button log driving both sides). Order them by how much trace or row divergence they remove per dollar, against docs/SCOPE.md's milestones (M2 before content; a virus, chip or Navi is a port under the interpreters, never a re-creation). Read only what you need to write them: the open tickets' text from TODO.md, and grep tools/harness.py or TODO_ARCHIVE.md for a specific fact. You are on a clock: the session is killed at 25 minutes and anything not yet written is lost, which happened to 9 of 37 judge runs on 2026-09-17 -- each one spent about nine cents reading files and produced nothing. Spend at most half your time reading. If you are not finished by then, write the tickets you do have, fewer than five if necessary: three usable tickets beat five that never get written. Reply with the tickets only." \
  > "$SESS/events.jsonl" 2> "$SESS/stderr.txt" < /dev/null || true
python3 - "$SESS/events.jsonl" "$OUT" "$STAMP" "$MODEL" <<'EOF'
import json, sys
last, cost = "", 0.0
for line in open(sys.argv[1]):
    try: e = json.loads(line)
    except ValueError: continue
    m = e.get("message") if isinstance(e, dict) else None
    if isinstance(e, dict) and e.get("type") not in (None, "turn_end"): continue      # pi emits one message in three events; count it once
    if isinstance(m, dict) and m.get("role") == "assistant":
        cost += ((m.get("usage") or {}).get("cost") or {}).get("total", 0)
        t = " ".join(c.get("text", "") for c in m.get("content", []) if c.get("type") == "text").strip()
        if t: last = t
open(sys.argv[2], "w").write("# Proposed tickets %s (%s, $%.4f)\n\n%s\n" % (sys.argv[3], sys.argv[4], cost, last or "(no output -- see the session's stderr)"))
print("%s ($%.4f)" % (sys.argv[2], cost))
print("EMPTY" if not last else "OK")
EOF
if ! grep -q "no output -- see the session" "$OUT" 2>/dev/null; then break; fi
echo "judge: $MODEL wrote no tickets; trying the next candidate" >&2
bash tools/incident.sh judge-empty "$MODEL produced no ticket text ($(wc -c < "$SESS/events.jsonl") bytes of events); trying the next candidate"
done

# Only now, with every candidate spent, is the batch actually lost. The kind is judge-empty rather than
# judge-timeout because the two known causes are not both timeouts and naming one of them would send
# the next reader down the wrong path.
if grep -q "no output -- see the session" "$OUT" 2>/dev/null; then
  bash tools/incident.sh judge-empty "$OUT: no candidate wrote ticket text; the batch is lost and the queue is unchanged"
fi
