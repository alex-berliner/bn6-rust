#!/usr/bin/env bash
# Stop a coordinator run when its provider's budget is gone: for a subscription provider, when the balance
# drops under providers.toml's stop_below (the user's rule, 2026-09-14: shut down fully, the reserve is not
# a fallback). Polls `tools/roles.py budget <provider> --stop` every 3 minutes; only a real "below"
# (exit 1) counts, twice in a row, never a probe error (exit 2). Pay-as-you-go runs are stopped by the
# run's own cap watcher instead (tools/pi_coordinator.sh).
# usage: bash tools/budget_watch.sh <provider> <run dir>
PROV="${1:?provider}"; RUN="${2:?run dir}"
cd "$(dirname "$0")/.."
strikes=0
while true; do
  sleep 180
  [ -f "$RUN/exit" ] && exit 0
  python3 tools/roles.py budget "$PROV" --stop >/dev/null 2>&1; rc=$?
  [ "$rc" = 1 ] || { strikes=0; continue; }
  strikes=$((strikes + 1)); [ "$strikes" -ge 2 ] || continue
  echo "$(date +%H:%M) $PROV EXHAUSTED: stopping the run" >> "$RUN/status.log"
  for p in $(ps -eo pid,args | grep "session-dir $RUN/session" | grep -v grep | awk '{print $1}'); do kill "$p" 2>/dev/null; done
  sleep 5
  for p in $(ps -eo pid,args | grep "session-dir $RUN/session" | grep -v grep | awk '{print $1}'); do kill -9 "$p" 2>/dev/null; done
  # this run's children carry its provider's role names (worker-<p>, verifier-<p>, recon-<p>)
  for p in $(ps -eo pid,args | grep -E "pi -p .*(worker|verifier|recon)(-$PROV)?\b" | grep -v grep | awk '{print $1}'); do kill "$p" 2>/dev/null; done
  echo "$PROV exhausted $(date +%H:%M)" > "$RUN/exit"; exit 0
done
