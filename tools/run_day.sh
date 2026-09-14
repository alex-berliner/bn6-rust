#!/usr/bin/env bash
# The launcher, run by cron every 30 minutes. Reads providers.toml's schedule: for each active provider in
# order, if it has no run going and its budget allows a start, launch one (tools/pi_coordinator.sh with
# BN_PROVIDER); a subscription provider under its start threshold gets its tail (tools/tail.sh: one judge
# pass and recon maps until the balance is gone). Serial schedule: at most one run in total; parallel:
# one per provider. Also the recovery duties: restore the /tmp inputs after a reboot, prune old checkouts.
# usage: bash tools/run_day.sh          (idempotent; safe by hand)
cd "$(dirname "$0")/.."
bash tools/check_inputs.sh >/dev/null 2>&1 || bash tools/restore_inputs.sh >/dev/null 2>&1   # a reboot empties /tmp
find /tmp/bnwt -maxdepth 1 -name "verify-*" -mtime +1 -exec git worktree remove --force {} \; 2>/dev/null; git worktree prune
find /tmp -maxdepth 1 -name "ct_verify*" -mtime +2 -exec rm -rf {} + 2>/dev/null
python3 tools/roles.py check >/dev/null || { python3 tools/roles.py check; exit 1; }
eval "$(python3 tools/roles.py schedule)"
running=0
for prov in $ACTIVE; do
  # a run of this provider is active when a live coordinator's run dir names it
  active=0
  for d in $(ls -d /tmp/bn-pi/2* 2>/dev/null); do
    [ -f "$d/provider" ] && [ "$(cat "$d/provider")" = "$prov" ] && [ ! -f "$d/exit" ] && pgrep -f "session-dir $d/session" >/dev/null && active=1
  done
  # runs started before the provider file existed count as the first active provider's
  [ "$active" = 0 ] && [ "$prov" = "${ACTIVE%% *}" ] && pgrep -f 'pi -p --approve --session-dir /tmp/bn-pi' >/dev/null && active=1
  if [ "$active" = 1 ]; then echo "$prov: a run is active"; running=$((running + 1)); [ "$PARALLEL" = 1 ] && continue || break; fi
  python3 tools/roles.py budget "$prov" --start >/dev/null 2>&1; rc=$?
  if [ "$rc" = 0 ]; then
    BN_PROVIDER="$prov" bash tools/pi_coordinator.sh > /tmp/bn-pi/last_run_dir 2>&1
    echo "$prov: started $(cat /tmp/bn-pi/last_run_dir)"; running=$((running + 1))
    [ "$PARALLEL" = 1 ] && continue || break
  elif [ "$rc" = 1 ]; then
    tail=$(python3 -c "import tomllib; print(int(tomllib.load(open('providers.toml','rb'))['providers']['$prov'].get('tail', False)))")
    if [ "$tail" = 1 ]; then echo "$prov: under its start threshold; running the tail"; bash tools/tail.sh "$prov"; fi
    echo "$prov: no budget to start"
  else
    echo "$prov: budget probe failed; not starting"
  fi
done
[ "$running" = 0 ] && echo "nothing running"
exit 0
