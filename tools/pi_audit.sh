#!/usr/bin/env bash
# The auditor (agreed 2026-09-13): a one-shot, read-only pi session that reads a DIGEST (the latest
# daily review, the open tickets, the last Results, the config files and the config changelog) and
# PROPOSES reshapes of the agent setup -- roles, loop text, AGENTS.md, ticket format, tools -- into
# docs/audits/<stamp>.md. It never edits anything; a human session applies at most one structural
# change per cycle and records it in docs/config-log.md. Cost: about a cent (muse contributor).
#
# usage: bash tools/pi_audit.sh [review file]      -> prints the proposal file path
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
# The auditor is the only thing that proposes new operating rules, so it failing to start is itself the
# most important incident there is -- and it used to be one line in the review that nobody read. It has
# produced two audits ever, both on 2026-09-14, because this pick kept failing on budget (2026-09-17).
MODEL="${BN_MODEL:-$(python3 tools/roles.py pick auditor --tail 2>/dev/null || true)}"
if [ -z "$MODEL" ]; then
  bash tools/incident.sh auditor-blocked "no scheduled run has an auditor model with budget; no audit written"
  echo "pi_audit: no auditor model has budget; recorded as an incident" >&2; exit 1
fi
REVIEW="${1:-$(ls -t docs/reviews/*.md 2>/dev/null | head -1)}"
STAMP="$(date +%Y%m%d-%H%M%S)"; OUT="docs/audits/$STAMP.md"; SESS="/tmp/bn-pi/audit/$STAMP"; mkdir -p docs/audits "$SESS"
DIGEST="$(
  echo "=== latest review ($REVIEW) ==="; sed -n '1,80p' "$REVIEW" 2>/dev/null
  echo; echo "=== open tickets ==="; python3 tools/next_ticket.py --list 2>/dev/null | head -20
  echo; echo "=== last 12 Results (first 300 chars each) ==="
  grep -hE '^\*\*Result\.\*\*' TODO.md TODO_ARCHIVE.md | tail -12 | cut -c1-300
  echo; echo "=== config changelog ==="; cat docs/config-log.md
  echo; echo "=== operational incidents in the last 24h (tools/incident.sh; the machinery failing, not the game work) ==="
  python3 - <<'INC'
import json, collections, datetime, os
p = "/tmp/bn-incidents.jsonl"
if not os.path.exists(p):
    print("(no incident log on this machine yet)")
else:
    cut = datetime.datetime.now().astimezone() - datetime.timedelta(hours=24)
    kinds, samples = collections.Counter(), {}
    for line in open(p, errors="replace"):
        try: e = json.loads(line)
        except ValueError: continue
        try:
            if datetime.datetime.fromisoformat(e["t"]) < cut: continue
        except Exception: pass
        kinds[e.get("kind", "?")] += 1
        samples.setdefault(e.get("kind", "?"), e.get("msg", ""))
    if not kinds: print("(none in 24h)")
    for k, n in kinds.most_common():
        print("%-18s %3d   e.g. %s" % (k, n, str(samples[k])[:160]))
INC
)"
timeout 900 pi -p --approve --no-session --mode json \
  --model "$MODEL" --thinking high --tools read,grep,find,ls \
  "You are the auditor for /home/box/Code/bn, a per-pixel reimplementation of a GBA game's battle system driven by tickets that agents work in a coordinator loop. You have read-only tools; you change nothing. Your job is to look at how the work is going and propose reshapes of the AGENT SETUP (not the game code): the role files in .pi/agents/*.md, the loop in .pi/coordinator.md, the rules in AGENTS.md and AGENT_GUIDE.md, the ticket format in TODO.md, the model routing, and the tools in tools/ that agents keep re-doing by hand. Read those files. Invariants you never touch: canon never changes, verify_rows runs before every landing, no fitted constants, the spend floor.

Digest:
$DIGEST

The incident list is the machinery failing at itself -- a landing refused, a merge that conflicted and left the shared checkout broken, a judge batch that admitted nothing, the disassembly refused because it was on a detached head, an auditor that could not start. These are NOT ticket outcomes and will not appear in the Results. Treat a repeated incident kind as a first-class finding: propose the rule or the guard that would stop it recurring, exactly as you would for a cost problem. If one kind dominates, that is your first item.

Write a proposal with AT MOST THREE items, ordered by expected effect on cost per landed ticket. Each item: (1) the observed pattern, with the ticket IDs or numbers from the digest as evidence; (2) the exact change as a unified diff against the file it touches, or a spec for a new tool with its usage line; (3) the metric it should move and how the next review would show it; (4) the risk. If the evidence does not support a change, say 'no change' for that slot. Also list any repeated manual work you see in the Results that a script should replace. Reply with the proposal only." \
  > "$SESS/events.jsonl" 2> "$SESS/stderr.txt" < /dev/null || true
python3 - "$SESS/events.jsonl" "$OUT" "$STAMP" "$REVIEW" <<'PY'
import json, sys
last, cost = "", 0.0
for line in open(sys.argv[1]):
    try: e = json.loads(line)
    except ValueError: continue
    m = e.get("message") if isinstance(e, dict) else None
    if isinstance(e, dict) and e.get("type") not in (None, "turn_end"): continue      # pi emits one message in three events; count it once
    if isinstance(m, dict) and m.get("role") == "assistant":
        cost += ((m.get("usage") or {}).get("cost") or {}).get("total", 0)
        t = " ".join(c.get("text", "") for c in m.get("content", []) if c.get("type") == "text").strip()
        if t: last = t
open(sys.argv[2], "w").write("# Audit %s ($MODEL, $%.4f, from %s)\n\nProposal only: a human session applies at most one structural change and records it in docs/config-log.md.\n\n%s\n" % (sys.argv[3], cost, sys.argv[4], last or "(no output -- see the session's stderr)"))
print("%s ($%.4f)" % (sys.argv[2], cost))
PY
