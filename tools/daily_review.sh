#!/usr/bin/env bash
# The daily cost-per-progress review (agreed 2026-09-13): joins ticket outcome to model and cost,
# re-measures the scoreboard, computes the metrics, evaluates the auditor's triggers, and writes
# docs/reviews/<date>.md. Meant for a machine cron (see the crontab line in HANDOFF); it changes
# nothing but that file and, when triggered, runs tools/pi_audit.sh (a cent, read-only) whose
# proposal a human session applies. Model switches are never made here: they need the replay
# benchmark (tools/replay_bench.py) and the pre-agreed rule in docs/config-log.md.
#
# usage: bash tools/daily_review.sh [--no-table] [--audit] [--since HOURS]
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
SINCE=24; TABLE=1; AUDIT=0
while [ $# -gt 0 ]; do case "$1" in --no-table) TABLE=0;; --audit) AUDIT=1;; --since) SINCE="$2"; shift;; esac; shift; done
STAMP="$(date +%Y-%m-%d)"; OUT="docs/reviews/$STAMP.md"; TMP=/tmp/bn-review; mkdir -p "$TMP" docs/reviews
{
  echo "# Daily review $STAMP ($(date +%H:%M), last ${SINCE}h)"
  echo
  echo "## Spend and outcomes (tools/ticket_ledger.py --since $SINCE)"
  echo '```'
  python3 tools/ticket_ledger.py --since "$SINCE" 2>&1
  echo '```'
  echo
  echo "## Balance"
  echo '```'; python3 tools/or_spend.py 2>&1 | head -2; python3 tools/hyper_credits.py 2>&1 | head -1; echo '```'
  echo "Provider schedule (providers.toml): $(python3 tools/roles.py schedule | tr '\n' ' ')"
  echo "Subscription rule: the day's balance is spent to the end (tools/budget_watch.sh stops the run, tools/tail.sh spends the rest)."
  echo
  if [ "$TABLE" = 1 ]; then
    echo "## Scoreboard (python3 tools/harness.py --no-gallery, this checkout at $(git rev-parse --short HEAD))"
    python3 tools/harness.py --no-gallery > "$TMP/table.txt" 2>&1
    PASS=$(grep -cE '^\S+\s+(isolated|integrated)\s+PASS' "$TMP/table.txt"); ALL=$(grep -cE '^\S+\s+(isolated|integrated)\s+(PASS|FAILED|ALLOWED|BLIND)' "$TMP/table.txt")
    echo; echo "rows at 0 (canon vs ours): $PASS of $ALL rows/variants"; echo
    echo '```'; grep -E '^\S+\s+(isolated|integrated)\s+(FAILED|ALLOWED)' "$TMP/table.txt" | sed -E 's/\s+/ /g' | cut -c1-110; echo '```'
    echo
  fi
  echo "## Milestones (docs/SCOPE.md)"
  echo '```'; grep -E '^\| M[0-9]' docs/SCOPE.md | cut -c1-200; echo '```'
  echo
  echo "## Hygiene"
  echo "- fitted constants in src/: $(grep -rc 'provenance: fitted' src/ | awk -F: '{s+=$2} END {print s+0}')"
  echo "- unnamed values tagged // unnamed in src/: $(grep -rc '// unnamed' src/ | awk -F: '{s+=$2} END {print s+0}')"
  NOPAIR=0; for f in $(find /tmp/bn-pi -maxdepth 1 -mindepth 1 -type d -newermt "-${SINCE} hours" 2>/dev/null); do
    n=$(grep -o 'NO PAIR' "$f"/session/*.jsonl 2>/dev/null | wc -l); NOPAIR=$((NOPAIR + n)); done
  echo "- coordinator dispatches with no pair available (last ${SINCE}h): $NOPAIR"
  echo "- allowlist entries: $(grep -cE '^\s+"[a-z-]+(:integrated|:isolated)?":' tools/allowlist.py)"
  echo
  echo "## Replay benchmarks (docs/benchmarks/, newest first)"
  echo '```'; for f in $(ls -t docs/benchmarks/*.md 2>/dev/null | head -12); do head -1 "$f" | sed 's/^# //'; grep -oE 'cost \$[0-9.]+, [0-9]+ turns, [0-9]+ min' "$f" | head -1; done; echo '```'
  echo
  echo "## Switch rule (docs/config-log.md)"
  echo "A role's model changes only if, over at least 10 tickets, its cost per landed ticket is twice an alternative's on the replay benchmark (tools/replay_bench.py), and never on one day's numbers."
  echo
  echo "## Auditor triggers"
  NEGRATE=$(python3 tools/ticket_ledger.py --since "$SINCE" 2>/dev/null | grep -oE 'NEGATIVE\+BLOCKED [0-9]+ \([0-9]+%\)' | grep -oE '[0-9]+%' | tr -d '%'); NEGRATE=${NEGRATE:-0}
  NT=$(python3 tools/ticket_ledger.py --since "$SINCE" 2>/dev/null | grep -oE '^tickets [0-9]+' | grep -oE '[0-9]+'); NT=${NT:-0}
  PHASE="$(cat docs/PHASE 2>/dev/null || echo convergence)"; LASTPHASE="$(cat "$TMP/last_phase" 2>/dev/null || echo convergence)"
  TRIG=""
  [ "$NT" -ge 8 ] && [ "$NEGRATE" -ge 30 ] && TRIG="$TRIG negative-or-blocked rate ${NEGRATE}% over $NT tickets;"
  [ "$PHASE" != "$LASTPHASE" ] && TRIG="$TRIG phase changed $LASTPHASE -> $PHASE;"
  [ "$AUDIT" = 1 ] && TRIG="$TRIG forced;"
  echo "$PHASE" > "$TMP/last_phase"
  echo "- phase: $PHASE; negative-or-blocked rate: ${NEGRATE}% over $NT tickets; no-pair dispatches: $NOPAIR"
  if [ -n "$TRIG" ]; then
    echo "- TRIGGERED:$TRIG"; echo
    echo "## Auditor"
    bash tools/pi_audit.sh "$OUT" 2>&1 | tail -3
  else
    echo "- not triggered"
  fi
} > "$OUT.tmp" 2>&1
mv "$OUT.tmp" "$OUT"; echo "$OUT"
# the disassembly's renamed symbols reach this repo's citations once, on a morning with no run active (2026-09-15)
[ -f docs/renames-applied ] || { python3 tools/apply_renames.py --if-idle --commit 2>&1 | tail -3 | grep -q committed && date > docs/renames-applied && git add docs/renames-applied && git commit -q -m 'citations: renames applied marker' && git push -q origin main; }
# open tickets whose cited numbers drifted get a premise-check line before a worker spends credits on them (2026-09-15)
python3 tools/premise_check.py --commit 2>&1 | tail -4
# the automated digest post (agreed 2026-09-14): one blog post per day that had a ticket result or a merge,
# built from the record the review just read, with the auditor's open proposals summarized in it
python3 tools/digest_post.py --since "$SINCE" --review "$OUT" --post 2>&1 | tail -2
# the learn feed grows every morning (the user, 2026-09-15): slides on existing code and on the last day's code
python3 tools/learn_slides.py --existing 6 --recent 6 --since "$SINCE" --post 2>&1 | tail -16
# the day's findings go back into the disassembly as comment-only notes on bn-notes (the user, 2026-09-15)
python3 tools/annotate_asm.py --since "$SINCE" --post 2>&1 | tail -8

