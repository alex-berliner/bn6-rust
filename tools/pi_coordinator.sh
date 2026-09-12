#!/usr/bin/env bash
# Launch a detached pi coordinator session (GPT-5.6 Sol) that runs TODO.md tickets through the
# worker/verifier roles until a stop condition (.pi/coordinator.md). Detached so a host memory guard
# cannot kill it; stdin closed because pi -p waits on an open stdin (HANDOFF §13 quirk b).
#
# usage: bash tools/pi_coordinator.sh ["extra instruction for this session"]
# prints the run directory; watch <dir>/status.log, <dir>/exit, and the session file in <dir>/session.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
RUN="/tmp/bn-pi/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$RUN/session"
MSG="${1:-Run the loop in your instructions, starting at step 1.}"
cat > "$RUN/run.sh" <<INNER
#!/usr/bin/env bash
cd "$ROOT"
export BN_PI_STATUS="$RUN/status.log"
timeout 43200 pi -p --approve --session-dir "$RUN/session" --mode json \
  --model openrouter/openai/gpt-5.6-sol --thinking high \
  --append-system-prompt "$ROOT/.pi/coordinator.md" "\$(cat "$RUN/instruction.txt")" \
  > "$RUN/events.jsonl" 2> "$RUN/stderr.txt" < /dev/null
echo "exit \$?" > "$RUN/exit"
INNER
printf '%s\n' "$MSG" > "$RUN/instruction.txt"
chmod +x "$RUN/run.sh"
setsid nohup "$RUN/run.sh" > /dev/null 2>&1 < /dev/null &
echo "$RUN"
