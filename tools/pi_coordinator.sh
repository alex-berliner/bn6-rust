#!/usr/bin/env bash
# Launch a detached pi coordinator session that runs TODO.md tickets through a provider's roles until a
# stop condition (.pi/coordinator.md). Detached so a host memory guard cannot kill it; stdin closed
# because pi -p waits on an open stdin (HANDOFF §13 quirk b).
#
# usage: [BN_RUN=hyper] [BN_PI_CAP=5] [BN_COORD_MODEL=...] bash tools/pi_coordinator.sh ["instruction for this session"]
#   BN_RUN: a run profile from providers.toml (default: the first scheduled one). Its jobs resolve to the first
#   candidate model whose provider has budget (tools/roles.py resolve); that sets the coordinator model, the
#   instruction when none is given, the OpenRouter cap from any pay-as-you-go provider involved, and starts
#   tools/budget_watch.sh over the subscription providers the coordinator and worker sit on.
#   BN_PI_CAP: hard cap in dollars on the run's TOTAL real OpenRouter spend (coordinator + children),
#   enforced by a watcher that reads tools/or_spend.py every minute and stops the run when usage passes
#   the starting total plus the cap. Default: the provider's cap_per_run_usd, else 5.
# prints the run directory; watch <dir>/status.log, <dir>/exit, and the session file in <dir>/session.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NAME="${BN_RUN:-${BN_PROVIDER:-$(python3 "$ROOT/tools/roles.py" first)}}"
python3 "$ROOT/tools/roles.py" resolve "$NAME" >/dev/null || { echo "run $NAME: no candidate for its coordinator or worker has budget" >&2; exit 1; }
COORD="${BN_COORD_MODEL:-$(python3 "$ROOT/tools/roles.py" model "$NAME" coordinator)}"
PROVS="$(python3 "$ROOT/tools/roles.py" providers "$NAME")"
python3 "$ROOT/tools/roles.py" render "$NAME" >/dev/null   # the agent files follow providers.toml and today's budgets
RUN="/tmp/bn-pi/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$RUN/session"; echo "$NAME" > "$RUN/run"; echo "$PROVS" > "$RUN/providers"
python3 "$ROOT/tools/roles.py" resolve "$NAME" > "$RUN/roles.txt"
MSG="${1:-$(python3 "$ROOT/tools/roles.py" instruction "$NAME")}"
cat > "$RUN/run.sh" <<INNER
#!/usr/bin/env bash
# The coordinator session, resumed up to 6 times when it ends by itself while work remains (a model now and then
# ends its turn mid-loop -- Qwen at 16:27 and M3 at 18:10 on 2026-09-14 -- and waiting for the next cron tick
# cost half an hour each time). A watcher's exit file ends the run for good.
cd "$ROOT"
export BN_PI_STATUS="$RUN/status.log"
for i in 1 2 3 4 5 6 7; do
  sess="$RUN/session"; [ "\$i" -gt 1 ] && sess="$RUN/session-\$i"
  note=""; [ "\$i" -gt 1 ] && note="

You are resuming run $RUN (session \$i): the previous coordinator session ended its turn early. Continue the loop from step 1; branches and worktrees left by that session are in flight, not strays -- verify and land or record them first."
  timeout 43200 pi -p --approve --session-dir "\$sess" --mode json \
    --model "$COORD" --thinking high \
    --append-system-prompt "$ROOT/.pi/coordinator.md" "\$(cat "$RUN/instruction.txt")\$note" \
    >> "$RUN/events.jsonl" 2>> "$RUN/stderr.txt" < /dev/null
  rc=\$?
  [ -f "$RUN/exit" ] && exit 0                                   # a watcher ended the run
  [ "\$rc" = 0 ] || break                                         # a crash or a timeout: stop and let the cron relaunch
  python3 tools/next_ticket.py --list 2>/dev/null | grep -qE '^\S+\s+OPEN\b' || { f="\$(bash tools/pi_judge.sh 2>/dev/null | awk '{print \$1}')"; [ -n "\$f" ] && python3 tools/judge_append.py "\$f" | grep -q "admitted: \[[A-Z]" || break; }
  echo "\$(date +%H:%M) coordinator session \$i ended early with work left; resuming" >> "$RUN/status.log"
done
echo "exit \$rc" > "$RUN/exit"
INNER
CAP="${BN_PI_CAP:-$(python3 -c "
import tomllib; c = tomllib.load(open('$ROOT/providers.toml','rb'))['providers']
print(max([c[p].get('cap_per_run_usd', 5) for p in '$PROVS'.split() if c[p]['kind'] == 'payg'] or [5]))")}"
START="$(python3 "$ROOT/tools/or_spend.py" | sed -n 's/.*total \$\([0-9.]*\).*/\1/p')"
printf '%s\n\nThis run has a hard cap of $%s of total real spend (coordinator and children together),\nenforced outside you; plan to finish or stop well before it.\n' "$MSG" "$CAP" > "$RUN/instruction.txt"
cat > "$RUN/capwatch.sh" <<CAPW
#!/usr/bin/env bash
LIMIT=\$(python3 -c "print(float('$START') + float('$CAP'))")
while [ ! -f "$RUN/exit" ]; do
  used=\$(python3 "$ROOT/tools/or_spend.py" 2>/dev/null | sed -n 's/.*total \\\$\([0-9.]*\).*/\1/p')
  if [ -n "\$used" ] && python3 -c "import sys; sys.exit(0 if float('\$used') >= \$LIMIT else 1)"; then
    echo "\$(date +%H:%M) CAP HIT: total \$used >= \$LIMIT" >> "$RUN/status.log"
    # timeout(1) puts pi in its own process group, so kill pi by its session dir as well as run.sh's group
    for p in \$(pgrep -f "$RUN/session"); do kill -TERM \$p 2>/dev/null; done
    for p in \$(pgrep -f "$RUN/run.sh"); do kill -TERM -- -\$(ps -o pgid= \$p | tr -d ' ') 2>/dev/null; done
    echo "exit cap" > "$RUN/exit"; break
  fi
  sleep 60
done
CAPW
chmod +x "$RUN/capwatch.sh"
chmod +x "$RUN/run.sh"
setsid nohup "$RUN/run.sh" > /dev/null 2>&1 < /dev/null &
setsid nohup "$RUN/capwatch.sh" > /dev/null 2>&1 < /dev/null &
# the run stops when a subscription provider its coordinator or worker sits on is exhausted (tools/budget_watch.sh)
(setsid nohup bash "$ROOT/tools/budget_watch.sh" "$RUN" >/dev/null 2>&1 &)
echo "$RUN"
