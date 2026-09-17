#!/usr/bin/env bash
# Record one operational failure, so the loop can see its own machinery breaking.
#
#   bash tools/incident.sh <kind> "<what happened>"
#   kinds: land-refused land-conflict verify-failed rename-reverted asm-refused judge-discarded
#          auditor-blocked starved-run lock-timeout
#
# Why this exists. Every failure in this workflow used to be printed to a tmux pane and then lost.
# The daily review measured TICKET outcomes -- what the agents achieved on the game -- and the auditor
# that proposes new operating rules was fed only those outcomes. So a whole class of problem was
# invisible to the loop by construction: a landing refused because the shared checkout was dirty, a
# merge that conflicted and left the tree broken, a judge batch discarded on a formatting technicality,
# the disassembly committed to a detached head, an auditor that could not start for lack of budget.
# None of those produce a ticket Result, so none of them ever reached the auditor, and every one of
# them had to be found by hand (2026-09-17). This is the missing input.
#
# Written to /tmp rather than the repo on purpose: an incident file inside the checkout would itself
# be an uncommitted file blocking every landing, which is one of the failures it is meant to record.
# The roundup rolls the day's incidents into the review, which is committed.
LOG=/tmp/bn-incidents.jsonl
kind="${1:?usage: incident.sh <kind> <message>}"; shift
msg="$*"
printf '{"t":"%s","kind":"%s","run":"%s","cwd":"%s","msg":%s}\n' \
  "$(date -Is)" "$kind" "${BN_RUN:-${TMUX_PANE:-unknown}}" "$PWD" \
  "$(python3 -c 'import json,sys; print(json.dumps(sys.argv[1]))' "$msg")" >> "$LOG" 2>/dev/null || true
