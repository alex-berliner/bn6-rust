#!/usr/bin/env bash
# Print ONLY ticket-level events from a coordinator run, one line each, and exit when the run ends:
# merged / DONE / BLOCKED / NEGATIVE / PARTIAL / STOP / CAP / exit, plus a stall notice after 25 quiet
# minutes. Meant for a Monitor that wakes a Claude Code session only when something is decided --
# not on every step (each wake re-sends that session's whole context).
#
# usage: bash tools/pi_watch.sh <run dir>      (the dir tools/pi_coordinator.sh printed)
RUN="${1:?run dir}"
until [ -d "$RUN/session" ]; do sleep 5; done
seen=0; stalled=0
while true; do
  if [ -f "$RUN/status.log" ]; then
    n=$(wc -l < "$RUN/status.log")
    if [ "$n" -gt "$seen" ]; then
      tail -n $((n-seen)) "$RUN/status.log" | grep -E --line-buffered -i "merged|DONE|BLOCKED|NEGATIVE|PARTIAL|STOP|CAP HIT" || true
      seen=$n
    fi
  fi
  if [ -f "$RUN/exit" ]; then echo "run ended: $(cat "$RUN/exit")"; break; fi
  last=$(find "$RUN" -type f -printf '%T@\n' | sort -n | tail -1 | cut -d. -f1); age=$(( $(date +%s) - ${last:-0} ))
  if [ "$age" -gt 1500 ] && [ "$stalled" -eq 0 ]; then echo "STALL: nothing written for ${age}s"; stalled=1; fi
  [ "$age" -lt 120 ] && stalled=0
  sleep 60
done
