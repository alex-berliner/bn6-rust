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
# Every worktree gets its own cargo target dir, and nothing removed them once the worktree was gone:
# 169 orphans holding 73 GB had collected by 2026-09-17, on a disk that was 83% full. They are pure
# build output -- rebuildable in about 30 seconds -- so an orphan older than six hours goes. The
# six-hour floor keeps a dir a live build or verification is still writing to.
for _d in /tmp/ct_*; do
  [ -d "$_d" ] || continue
  _n="${_d#/tmp/ct_}"
  [ -d "/tmp/bnwt/$_n" ] && continue
  [ -n "$(find "$_d" -maxdepth 0 -mmin -360 2>/dev/null)" ] && continue
  rm -rf "$_d"
done
# Some tickets pointed CARGO_TARGET_DIR at a path under /tmp/bnwt instead of /tmp/ct_*, so build output
# collected among the worktrees where nothing was looking for it: 16 such directories, 7.2 GB, on
# 2026-09-17. A cargo target dir is unmistakable -- it carries CACHEDIR.TAG and no Cargo.toml -- so the
# test is exact rather than name-based, and a real checkout can never match it.
for _d in /tmp/bnwt/*/; do
  _d="${_d%/}"
  [ -f "$_d/CACHEDIR.TAG" ] || continue
  [ -f "$_d/Cargo.toml" ] && continue
  [ -n "$(find "$_d" -maxdepth 0 -mmin -360 2>/dev/null)" ] && continue
  git worktree list --porcelain 2>/dev/null | grep -qx "worktree $_d" && continue   # the script has already cd'd to the repo root
  rm -rf "$_d"
done
python3 tools/roles.py check >/dev/null || { python3 tools/roles.py check; exit 1; }
bash tools/retype_if_stale.sh        # the decompiled C follows the disassembly's types within half an hour
# --- the stage gate: management before work ------------------------------------------------------
# Managerial jobs (the review, the auditor, the judge, the digest, the slides, the disassembly notes,
# the site) all spend the same provider budget the workers do, and they run at the START of a cycle
# when they have the least of it left: six workers had already been running all night. That is how the
# auditor came to have no model with budget on 2026-09-17, which is why it had produced two audits in
# four days. From that date the day is staged: no worker run starts between the management window
# opening and the window reporting itself finished.
#
# MGMT_OPEN is when the window opens (the review's cron slot). MGMT_DEADLINE is when work proceeds
# anyway, so a broken roundup costs one window rather than the whole day; that case is an incident.
MGMT_OPEN="${BN_MGMT_OPEN:-1036}"; MGMT_DEADLINE="${BN_MGMT_DEADLINE:-1330}"
NOW="$(date +%H%M)"; MARK="/tmp/bn-pi/mgmt-done-$(date +%F)"
if [ ! -f "$MARK" ] && [ "$((10#$NOW))" -ge "$((10#$MGMT_OPEN))" ]; then
  if [ "$((10#$NOW))" -lt "$((10#$MGMT_DEADLINE))" ]; then
    echo "stage gate: the management window is open and has not finished; no worker run this tick"; exit 0
  fi
  bash tools/incident.sh mgmt-window-missed "no $MARK by $NOW; starting workers anyway"
  echo "stage gate: management never reported finished by $MGMT_DEADLINE; proceeding and recording it"
fi

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
    q="$(head -1 /tmp/bn-bench/queue)"; set -- $q; qrun="$1"; qt="$2"; qm="${3:--}"; qv="${4:--}"; qx="${5:--}"
    qprov="$(python3 tools/roles.py providers "$qrun" 2>/dev/null)"
    # the queued benchmark's OWN provider must be free: this loop runs once per scheduled profile, and on
    # 2026-09-16 the minimax iteration launched a hyper-queued benchmark beside the hyper one already running
    qbusy=""; for p in $qprov; do [ -f "/tmp/bn-bench/$p.lock" ] && kill -0 "$(cut -d' ' -f1 "/tmp/bn-bench/$p.lock")" 2>/dev/null && qbusy="$p"; done
    if [ -n "$qbusy" ]; then echo "queued benchmark waits: $qbusy is busy"
    elif [ -n "$qprov" ] && python3 tools/roles.py budget "${qprov%% *}" --start >/dev/null 2>&1; then
      sed -i '1d' /tmp/bn-bench/queue
      margs=""; [ "$qm" != "-" ] && margs="--model $qm"; [ "$qv" != "-" ] && margs="$margs --variant $qv"; [ "$qx" != "-" ] && margs="$margs --role-extra $qx"
      blog="/tmp/bn-bench/$qrun-$(date +%H%M).log"
      if command -v tmux >/dev/null 2>&1; then tmux new-session -d -s "bn-bench-$qrun-$(date +%H%M)" -c "$PWD" "python3 tools/bench_provider.py run '$qrun' --tickets '$qt' $margs 2>&1 | tee '$blog'"
      else setsid nohup python3 tools/bench_provider.py run "$qrun" --tickets "$qt" $margs > "$blog" 2>&1 < /dev/null & fi
      echo "$name: started the queued benchmark ($qrun: $qt); no run this tick"; sleep 3
      [ "$PARALLEL" = 1 ] && continue || break
    fi
  fi
  # an empty queue that the judge cannot refill (its daily cap) is not worth a run: each launch would spend a judge call and stop
  if ! python3 tools/next_ticket.py --list 2>/dev/null | grep -qE '^\S+\s+OPEN\b'; then
    batches="$(git log --since="$(date +%F) 00:00" --format=%s | grep -c judge-admitted)"
    if [ "${batches:-0}" -ge 40 ]; then echo "$name: queue empty and the judge is at its daily cap; no run this tick"; continue; fi
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
# the last credits of a subscription with a daily balance (under the run's stop threshold, above 1) check our own notes
for p in hyper; do
  bal="$(python3 tools/hyper_credits.py 2>/dev/null | grep -oE 'remaining [0-9.]+' | awk '{print $2}')"
  [ -n "$bal" ] && python3 -c "import sys; sys.exit(0 if 1.0 <= float('$bal') < 3.0 else 1)" && python3 tools/note_audit.py --max 3 2>&1 | tail -4
done
[ "$running" = 0 ] && echo "nothing running"
exit 0
