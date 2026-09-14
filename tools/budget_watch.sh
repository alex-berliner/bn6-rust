#!/usr/bin/env bash
# Stop a coordinator run when a subscription provider its coordinator or worker sits on is exhausted (under
# providers.toml's stop_below; the user's rule, 2026-09-14: a subscription's day is spent to the end, the
# reserve is not a fallback). Polls `tools/roles.py budget <provider> --stop` for each provider named in
# <run dir>/providers every 3 minutes; only a real "below" (exit 1) counts, twice in a row, never a probe error
# (exit 2). Pay-as-you-go spend is stopped by the run's own cap watcher (tools/pi_coordinator.sh). The cron
# launcher relaunches the run later with its fallback candidates (tools/run_day.sh).
# usage: bash tools/budget_watch.sh <run dir>
RUN="${1:?run dir}"
cd "$(dirname "$0")/.."
NAME="$(cat "$RUN/run" 2>/dev/null)"
SUBS=""
for p in $(cat "$RUN/providers" 2>/dev/null); do
  k="$(python3 -c "import tomllib; print(tomllib.load(open('providers.toml','rb'))['providers']['$p']['kind'])" 2>/dev/null)"
  [ "$k" = subscription ] && SUBS="$SUBS $p"
done
[ -n "$SUBS" ] || exit 0
strikes=0
while true; do
  sleep 180
  [ -f "$RUN/exit" ] && exit 0
  hit=""
  for p in $SUBS; do python3 tools/roles.py budget "$p" --stop >/dev/null 2>&1; [ $? = 1 ] && hit="$p"; done
  [ -n "$hit" ] || { strikes=0; continue; }
  strikes=$((strikes + 1)); [ "$strikes" -ge 2 ] || continue
  echo "$(date +%H:%M) $hit EXHAUSTED: stopping run $NAME" >> "$RUN/status.log"
  # this run only: the coordinator's process group (its children inherit it; timeout(1) gave pi its own group) and
  # run.sh's group. Never by role name: on 2026-09-14 18:51 a name pattern killed another provider's coordinator whose
  # instruction text mentioned "worker".
  for q in $(ps -eo pid,args | grep "session-dir $RUN/session" | grep -v grep | awk '{print $1}'); do kill -TERM -- "-$(ps -o pgid= "$q" | tr -d ' ')" 2>/dev/null; kill -TERM "$q" 2>/dev/null; done
  for q in $(ps -eo pid,args | grep "$RUN/run.sh" | grep -v grep | awk '{print $1}'); do kill -TERM -- "-$(ps -o pgid= "$q" | tr -d ' ')" 2>/dev/null; done
  sleep 5
  for q in $(ps -eo pid,args | grep "session-dir $RUN/session" | grep -v grep | awk '{print $1}'); do kill -9 "$q" 2>/dev/null; done
  echo "$hit exhausted $(date +%H:%M)" > "$RUN/exit"; exit 0
done
