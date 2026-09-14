#!/usr/bin/env bash
# Start, stop or show the pacing proxy for a provider whose providers.toml block has a [providers.X.pacer]
# table (port, upstream, rpm, concurrency). pi's models.json points that provider's baseUrl at the pacer.
# usage: bash tools/pacer.sh start|stop|status <provider>     (run_day.sh and pi_coordinator.sh call start)
cmd="${1:?start|stop|status}"; prov="${2:?provider}"
cd "$(dirname "$0")/.."
eval "$(python3 -c "
import tomllib; p = tomllib.load(open('providers.toml','rb'))['providers']['$prov'].get('pacer')
print('PORT=%s UPSTREAM=%s RPM=%s CONC=%s' % ((p['port'], p['upstream'], p.get('rpm', 20), p.get('concurrency', 2)) if p else ('', '', '', '')))")"
[ -n "$PORT" ] || { echo "$prov has no pacer in providers.toml"; exit 0; }
pat="api_pacer.py --provider $prov "
pid="$(ps -eo pid,args | grep -F "$pat" | grep -vE 'grep|pacer.sh' | awk '{print $1}' | head -1)"
case "$cmd" in
  status) [ -n "$pid" ] && echo "$prov pacer up (pid $pid, port $PORT)" || echo "$prov pacer down";;
  stop) [ -n "$pid" ] && kill "$pid" && echo "stopped $pid" || echo "not running";;
  start) [ -n "$pid" ] && { echo "$prov pacer already up (pid $pid)"; exit 0; }
         mkdir -p /tmp/bn-pacer
         setsid nohup python3 tools/api_pacer.py --provider "$prov" --port "$PORT" --upstream "$UPSTREAM" --rpm "$RPM" --concurrency "$CONC" --log "/tmp/bn-pacer/$prov.log" >/dev/null 2>&1 < /dev/null &
         sleep 1; bash "$0" status "$prov";;
esac
