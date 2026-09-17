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
MODEL="$(python3 tools/roles.py model "${BN_RUN:-${BN_PROVIDER:-$(python3 tools/roles.py first)}}" judge --tail)"
mkdir -p docs/proposals /tmp/bn-pi/judge
STAMP="$(date +%Y%m%d-%H%M%S)"; OUT="docs/proposals/$STAMP.md"; SESS="/tmp/bn-pi/judge/$STAMP"
mkdir -p "$SESS"
CTX="$(python3 tools/next_ticket.py --list 2>/dev/null || true)"
SCOPE="$(sed -n '1,60p' docs/SCOPE.md 2>/dev/null || true)"
BLOCKED="$(grep -E '^- .* BLOCKED -- ' TODO.md TODO_ARCHIVE.md 2>/dev/null | cut -c1-400 || true)"
LEDGER="$(python3 tools/spend_ledger.py 2>/dev/null | tail -8 || true)"
timeout 900 pi -p --approve --no-session --mode json \
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

Propose the next FIVE tickets, in the exact ticket format used in TODO.md, every part present or the ticket is refused by tools/judge_append.py: `### ID. title *(OPEN -- date)*` with a fresh ID, **Why.** with the measured facts, a **Files.** line naming the files the worker may touch, numbered **Do** steps each ending in a measurement, **Rules**, **Acceptance.** (what measured numbers close it) and **Measure and report.**, a **Coordinator:** note, and the docs/SCOPE.md milestone it advances (M1..M11). Keep each ticket under 5000 characters: name the facts and the measurements, do not narrate; every ticket is re-sent to a worker on every turn. Never continue an objective whose last ticket ended NEGATIVE or BLOCKED: that objective is closed until new evidence exists (a recon map or a measurement made after the close, which the ticket must quote under **New evidence.**); pick another item from the ladder instead. Two proposals in a row on one objective is the most you may make in a day. For an engine-core (M2) ticket the acceptance is a trace target (field, frames of the scene, first divergent frame) with verify_rows identical as the veto; for a content ticket it is the item's own scene and trace at 0; interaction rules need a scripted-input scenario (one button log driving both sides). Order them by how much trace or row divergence they remove per dollar, against docs/SCOPE.md's milestones (M2 before content; a virus, chip or Navi is a port under the interpreters, never a re-creation). Read only what you need to write them: the open tickets' text from TODO.md, and grep tools/harness.py or TODO_ARCHIVE.md for a specific fact. Reply with the five tickets only." \
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
EOF
