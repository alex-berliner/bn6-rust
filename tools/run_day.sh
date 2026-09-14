#!/usr/bin/env bash
# The launcher, run by cron every 30 minutes. Reads providers.toml's schedule: for each run profile in order,
# if none of its runs is going and its coordinator and worker resolve to a model with budget, launch it
# (tools/pi_coordinator.sh with BN_RUN; the jobs resolve again at every launch, so a run whose coordinator
# sat on an exhausted provider comes back on its fallback). Serial schedule: at most one run in total;
# parallel: one per profile. A subscription provider under its start threshold gets its tail (tools/tail.sh:
# one judge pass and recon maps until the balance is gone). Also the recovery duties: restore the /tmp
# inputs after a reboot, prune old checkouts. usage: bash tools/run_day.sh   (idempotent; safe by hand)
cd "$(dirname "$0")/.."
bash tools/check_inputs.sh >/dev/null 2>&1 || bash tools/restore_inputs.sh >/dev/null 2>&1   # a reboot empties /tmp
find /tmp/bnwt -maxdepth 1 -name "verify-*" -mtime +1 -exec git worktree remove --force {} \; 2>/dev/null; git worktree prune
find /tmp -maxdepth 1 -name "ct_verify*" -mtime +2 -exec rm -rf {} + 2>/dev/null
python3 tools/roles.py check >/dev/null || { python3 tools/roles.py check; exit 1; }
eval "$(python3 tools/roles.py schedule)"
running=0; tailed=""
for name in $RUNS; do
  active=0
  for d in $(ls -d /tmp/bn-pi/2* 2>/dev/null); do
    [ -f "$d/run" ] && [ "$(cat "$d/run")" = "$name" ] && [ ! -f "$d/exit" ] && pgrep -f "session-dir $d/session" >/dev/null && active=1
  done
  # a run started before run dirs carried a name counts as the first profile's
  [ "$active" = 0 ] && [ "$name" = "${RUNS%% *}" ] && for d in $(ls -d /tmp/bn-pi/2* 2>/dev/null); do
    [ ! -f "$d/run" ] && [ ! -f "$d/exit" ] && pgrep -f "session-dir $d/session" >/dev/null && active=1; done
  if [ "$active" = 1 ]; then echo "$name: a run is active"; running=$((running + 1)); [ "$PARALLEL" = 1 ] && continue || break; fi
  # a queued benchmark on one of this profile's providers goes first, alone on that provider (Hyper's hourly rate
  # limit, 2026-09-14: a run plus a benchmark voided three replays and starved the run's own workers)
  provs="$(python3 tools/roles.py providers "$name" 2>/dev/null)"
  locked=""; for p in $provs; do [ -f "/tmp/bn-bench/$p.lock" ] && kill -0 "$(cut -d' ' -f1 "/tmp/bn-bench/$p.lock")" 2>/dev/null && locked="$p"; done
  if [ -n "$locked" ]; then echo "$name: a benchmark holds $locked; no run this tick"; [ "$PARALLEL" = 1 ] && continue || break; fi
  if [ -s /tmp/bn-bench/queue ]; then
    q="$(head -1 /tmp/bn-bench/queue)"; qrun="${q%% *}"; rest="${q#* }"; qt="${rest%% *}"; qm="${rest#* }"
    qprov="$(python3 tools/roles.py providers "$qrun" 2>/dev/null)"
    if [ -n "$qprov" ] && python3 tools/roles.py budget "${qprov%% *}" --start >/dev/null 2>&1; then
      sed -i '1d' /tmp/bn-bench/queue
      margs=""; [ "$qm" != "-" ] && margs="--model $qm"
      setsid nohup python3 tools/bench_provider.py run "$qrun" --tickets "$qt" $margs > "/tmp/bn-bench/$qrun-$(date +%H%M).log" 2>&1 < /dev/null &
      echo "$name: started the queued benchmark ($qrun: $qt); no run this tick"; sleep 3
      [ "$PARALLEL" = 1 ] && continue || break
    fi
  fi
  if python3 tools/roles.py resolve "$name" > /tmp/bn-pi/resolve_$name.txt 2>&1; then
    BN_RUN="$name" bash tools/pi_coordinator.sh > /tmp/bn-pi/last_run_dir 2>&1 && { echo "$name: started $(cat /tmp/bn-pi/last_run_dir)"; running=$((running + 1)); }
    [ "$PARALLEL" = 1 ] && continue || break
  fi
  echo "$name: cannot start ($(grep -c 'no candidate' /tmp/bn-pi/resolve_$name.txt) job(s) without budget)"
  # the tail: every subscription provider this profile names that is under start_above but above stop_below
  for p in $(python3 -c "
import tomllib; c = tomllib.load(open('providers.toml','rb'))
print(' '.join(sorted({m.split('/')[0] for role in ('coordinator','worker','verifier','recon','judge','auditor','digest') for m in c['runs']['$name'][role]
                       if c['providers'][m.split('/')[0]]['kind'] == 'subscription' and c['providers'][m.split('/')[0]].get('tail')})))"); do
    case " $tailed " in *" $p "*) continue;; esac
    python3 tools/roles.py budget "$p" --start >/dev/null 2>&1; [ $? = 1 ] || continue
    python3 tools/roles.py budget "$p" --stop >/dev/null 2>&1 || continue
    echo "$p: under its start threshold; running the tail through run $name"; tailed="$tailed $p"
    bash tools/tail.sh "$name"
  done
done
[ "$running" = 0 ] && echo "nothing running"
exit 0
