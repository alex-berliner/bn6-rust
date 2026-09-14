#!/usr/bin/env bash
# Stop a coordinator run when the day's Charm Hyper credits are gone (the user's rule, 2026-09-14: shut
# down fully; OpenRouter is a reserve, not a fallback). Polls tools/hyper_credits.py every 3 minutes.
# usage: bash tools/hyperwatch.sh <run dir>     (pi_coordinator.sh starts it when BN_HYPER=1)
RUN="${1:?run dir}"; MIN="${BN_HYPER_MIN:-3}"
cd "$(dirname "$0")/.."
while true; do
  sleep 180
  [ -f "$RUN/exit" ] && exit 0
  if ! python3 tools/hyper_credits.py --min "$MIN" >/dev/null 2>&1; then
    echo "$(date +%H:%M) HYPER EXHAUSTED (remaining < $MIN): stopping the run" >> "$RUN/status.log"
    for p in $(ps -eo pid,args | grep "session-dir $RUN/session" | grep -v grep | awk '{print $1}'); do kill "$p" 2>/dev/null; done
    sleep 5
    for p in $(ps -eo pid,args | grep "session-dir $RUN/session" | grep -v grep | awk '{print $1}'); do kill -9 "$p" 2>/dev/null; done
    for p in $(ps -eo pid,args | grep -E 'pi -p .*(worker|verifier|recon)' | grep -v grep | awk '{print $1}'); do kill "$p" 2>/dev/null; done
    echo "hyper exhausted $(date +%H:%M)" > "$RUN/exit"; exit 0
  fi
done
