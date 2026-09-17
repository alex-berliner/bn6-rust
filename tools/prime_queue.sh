#!/usr/bin/env bash
# Keep enough work ahead of the workers. Six worker slots share one queue; a coordinator that starts and finds
# every ticket claimed stops in four turns and the launcher waits half an hour. So before the day's runs, and
# whenever the queue is thinner than the slots, ask the judge until there are at least twice as many open
# unclaimed tickets as slots (or until the judge admits nothing, or the cap is reached).
#   bash tools/prime_queue.sh [target]        default target: 2 x the scheduled worker slots
set -uo pipefail
cd "$(dirname "$0")/.."
slots="$(python3 -c "
import tomllib; c = tomllib.load(open('providers.toml','rb'))
print(sum((w if isinstance(w := c['runs'][r]['workers'], int) else 2) for r in c['schedule']['runs']))")"
target="${1:-$((slots * 2))}"
for attempt in 1 2 3 4 5 6; do
  free="$(python3 tools/queue_report.py 2>/dev/null | grep -oE 'unclaimed right now \| [0-9]+' | grep -oE '[0-9]+$')"
  free="${free:-0}"
  [ "$free" -ge "$target" ] && { echo "queue: $free unclaimed for $slots slots, target $target -- enough"; exit 0; }
  f="$(bash tools/pi_judge.sh 2>/dev/null | awk '{print $1}')"
  [ -n "$f" ] || { echo "queue: the judge could not run (no provider with budget)"; exit 0; }
  out="$(python3 tools/judge_append.py "$f")"; echo "queue: $out"
  echo "$out" | grep -q "admitted: \[]" && { echo "queue: the judge admitted nothing; stopping"; break; }
  git push -q origin main 2>/dev/null
done
python3 tools/queue_report.py 2>/dev/null | grep -E 'unclaimed right now|QUEUE-TRIGGER'
