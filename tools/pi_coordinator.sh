#!/usr/bin/env bash
# Launch a detached pi coordinator session that runs TODO.md tickets through a provider's roles until a
# stop condition (.pi/coordinator.md). Detached so a host memory guard cannot kill it; stdin closed
# because pi -p waits on an open stdin (HANDOFF §13 quirk b).
#
# usage: [BN_PROVIDER=hyper] [BN_PI_CAP=5] [BN_COORD_MODEL=...] bash tools/pi_coordinator.sh ["instruction for this session"]
#   BN_PROVIDER: a provider from providers.toml (default: the first active one). Sets the coordinator model
#   from its roles, the instruction from `roles.py instruction` when none is given, the OpenRouter cap from
#   cap_per_run_usd for a pay-as-you-go provider, and starts tools/budget_watch.sh for a subscription one.
#   BN_PI_CAP: hard cap in dollars on the run's TOTAL real OpenRouter spend (coordinator + children),
#   enforced by a watcher that reads tools/or_spend.py every minute and stops the run when usage passes
#   the starting total plus the cap. Default: the provider's cap_per_run_usd, else 5.
# prints the run directory; watch <dir>/status.log, <dir>/exit, and the session file in <dir>/session.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PROV="${BN_PROVIDER:-$(python3 "$ROOT/tools/roles.py" first)}"
KIND="$(python3 -c "import tomllib; print(tomllib.load(open('$ROOT/providers.toml','rb'))['providers']['$PROV']['kind'])")"
COORD="${BN_COORD_MODEL:-$(python3 "$ROOT/tools/roles.py" model "$PROV" coordinator)}"
python3 "$ROOT/tools/roles.py" render >/dev/null   # the agent files follow providers.toml
RUN="/tmp/bn-pi/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$RUN/session"; echo "$PROV" > "$RUN/provider"
MSG="${1:-$(python3 "$ROOT/tools/roles.py" instruction "$PROV")}"
cat > "$RUN/run.sh" <<INNER
#!/usr/bin/env bash
cd "$ROOT"
export BN_PI_STATUS="$RUN/status.log"
timeout 43200 pi -p --approve --session-dir "$RUN/session" --mode json \
  --model "$COORD" --thinking high \
  --append-system-prompt "$ROOT/.pi/coordinator.md" "\$(cat "$RUN/instruction.txt")" \
  > "$RUN/events.jsonl" 2> "$RUN/stderr.txt" < /dev/null
echo "exit \$?" > "$RUN/exit"
INNER
CAP="${BN_PI_CAP:-$(python3 -c "import tomllib; print(tomllib.load(open('$ROOT/providers.toml','rb'))['providers']['$PROV'].get('cap_per_run_usd', 5))")}"
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
# a subscription provider's run stops when its balance is gone (tools/budget_watch.sh); BN_HYPER=1 is the old spelling
[ "$KIND" = subscription ] || [ "${BN_HYPER:-0}" = 1 ] && (setsid nohup bash "$ROOT/tools/budget_watch.sh" "$PROV" "$RUN" >/dev/null 2>&1 &)
echo "$RUN"
