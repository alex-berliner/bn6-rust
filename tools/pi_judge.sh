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

Propose the next THREE tickets, in the exact R/F ticket format used in TODO.md (### ID. title *(OPEN -- date)*, **Why.** with the measured facts, numbered **Do** steps each ending in a measurement, **Rules**, **Measure and report**, a **Coordinator:** note). Order them by how many existing harness rows they bring to 0 per dollar, against docs/SCOPE.md's milestones (M2 before content; a virus, chip or Navi is a port under the interpreters, never a re-creation). Read only what you need to write them: the open tickets' text from TODO.md, and grep tools/harness.py or TODO_ARCHIVE.md for a specific fact. Reply with the three tickets only." \
  > "$SESS/events.jsonl" 2> "$SESS/stderr.txt" < /dev/null || true
python3 - "$SESS/events.jsonl" "$OUT" "$STAMP" "$MODEL" <<'EOF'
import json, sys
last, cost = "", 0.0
for line in open(sys.argv[1]):
    try: e = json.loads(line)
    except ValueError: continue
    m = e.get("message") if isinstance(e, dict) else None
    if isinstance(m, dict) and m.get("role") == "assistant":
        cost += ((m.get("usage") or {}).get("cost") or {}).get("total", 0)
        t = " ".join(c.get("text", "") for c in m.get("content", []) if c.get("type") == "text").strip()
        if t: last = t
open(sys.argv[2], "w").write("# Proposed tickets %s (%s, $%.4f)\n\n%s\n" % (sys.argv[3], sys.argv[4], cost, last or "(no output -- see the session's stderr)"))
print("%s ($%.4f)" % (sys.argv[2], cost))
EOF
