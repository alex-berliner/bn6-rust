#!/usr/bin/env python3
"""Ticket outcome joined to who did it and what it cost -- the table the daily review reads.

For every child session under /tmp/bn-pi/<run>/session/subagent-artifacts (pi workers, verifiers,
recon) it takes role, model, turns, cost, tool calls and minutes from the *_meta.json, the ticket ID
from the child's report (*_output.md; the prompt is redacted in the artifacts), the status from the
TODO.md / TODO_ARCHIVE.md stamp, and whether the run's status.log says the branch was merged. Claude
agents (no pi session) are read from the ticket's Result line, which the human session writes as
"Claude <model> agent, N tool calls, M min, K tokens".

usage: python3 tools/ticket_ledger.py [--since HOURS] [--json]
"""
import argparse, collections, datetime, glob, json, os, re, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
HEAD = re.compile(r"^### ([A-Z]+\d+[a-z]?)\. .*?\*\((\w+)\b", re.M)
INDEX = re.compile(r"^- ([A-Z]+\d+[a-z]?) (\w+) -- ", re.M)
RESULT = re.compile(r"^### ([A-Z]+\d+[a-z]?)\. .*?^\*\*Result\.\*\*(.*?)(?=^### |\Z)", re.M | re.S)
CLAUDE = re.compile(r"Claude (\w+) agent, (\d+) tool calls(?:, (\d+) min)?(?:, ([\d.]+)k tokens)?")
STATUS_LINE = re.compile(r"^(\d\d:\d\d) ([A-Z]+\d+[a-z]?) (\S+) (\S+)")


def tickets_text():
    out = ""
    for f in ("TODO.md", "TODO_ARCHIVE.md"):
        p = os.path.join(ROOT, f)
        if os.path.exists(p):
            out += open(p).read() + "\n"
    return out


def statuses(text):
    st = {}
    for m in HEAD.finditer(text):
        st.setdefault(m.group(1), m.group(2))
    for m in INDEX.finditer(text):
        st.setdefault(m.group(1), m.group(2))
    return st


def landed_ids():
    """Tickets with a commit on main whose subject names them (merge or direct): the ground truth."""
    import subprocess
    subj = subprocess.run(["git", "-C", ROOT, "log", "--format=%s", "main"], capture_output=True, text=True).stdout
    out = set()
    for line in subj.splitlines():
        m = re.match(r"^(?:Merge )?([A-Z]+\d+[a-z]?)\b(?!.*\bTODO\b)", line)
        if m and not line.startswith("TODO"):
            out.add(m.group(1))
    return out


def ticket_from_output(path, known):
    if not os.path.exists(path):
        return "?"
    text = open(path).read()
    hits = collections.Counter(t for t in re.findall(r"\b([A-Z]{1,2}\d{1,3}[a-z]?)\b", text) if t in known)
    return hits.most_common(1)[0][0] if hits else "?"


def children(since_ts, known):
    rows = []
    for meta in glob.glob("/tmp/bn-pi/*/session/subagent-artifacts/*_meta.json"):
        try:
            d = json.load(open(meta))
        except ValueError:
            continue
        ts = int(d.get("timestamp") or 0) / 1000
        if ts < since_ts:
            continue
        u = d.get("usage") or {}
        if isinstance(u, str):
            try: u = json.loads(u.replace("'", '"'))
            except ValueError: u = {}
        rows.append({
            "run": meta.split("/")[3], "when": datetime.datetime.fromtimestamp(ts).strftime("%m-%d %H:%M"),
            "ticket": ticket_from_output(meta.replace("_meta.json", "_output.md"), known),
            "role": d.get("agent", "?"), "model": str(d.get("model", "?")).split("/")[-1],
            "turns": int(u.get("turns") or 0), "cost": float(u.get("cost") or 0),
            "tools": int(d.get("toolCount") or 0), "min": int(d.get("durationMs") or 0) / 60000.0, "ts": ts})
    return sorted(rows, key=lambda r: r["ts"])


def claude_agents(text, since_ts):
    rows = []
    for m in RESULT.finditer(text):
        for c in CLAUDE.finditer(m.group(2)):
            rows.append({"run": "claude", "when": "", "ticket": m.group(1), "role": "claude-agent",
                         "model": c.group(1).lower(), "turns": 0, "cost": 0.0, "tools": int(c.group(2)),
                         "min": float(c.group(3) or 0), "ts": 0, "ktokens": float(c.group(4) or 0)})
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", type=float, default=24.0, help="hours (default 24; 0 = everything)")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    since_ts = 0 if a.since == 0 else datetime.datetime.now().timestamp() - a.since * 3600
    text = tickets_text(); st = statuses(text); landed = landed_ids()
    rows = children(since_ts, set(st)) + (claude_agents(text, since_ts) if a.since == 0 else [])
    for r in rows:
        if r["ticket"] == "?" and r["run"] != "claude":
            end = datetime.datetime.fromtimestamp(r["ts"] + r["min"] * 60).strftime("%H:%M")
            for line in open("/tmp/bn-pi/%s/status.log" % r["run"]) if os.path.exists("/tmp/bn-pi/%s/status.log" % r["run"]) else []:
                m = STATUS_LINE.match(line)
                if m and m.group(1) >= end:
                    r["ticket"] = m.group(2); break
    for r in rows:
        r["status"] = st.get(r["ticket"], "?")
        r["landed"] = r["ticket"] in landed
    if a.json:
        print(json.dumps(rows, indent=1)); return
    print("%-11s %-6s %-8s %-6s %-12s %-24s %5s %7s %5s %5s" % ("when", "ticket", "status", "landed", "role", "model", "turns", "cost", "tools", "min"))
    for r in rows:
        print("%-11s %-6s %-8s %-6s %-12s %-24s %5d %7.3f %5d %5.0f" % (r["when"], r["ticket"], r["status"], "yes" if r["landed"] else "", r["role"], r["model"][:24], r["turns"], r["cost"], r["tools"], r["min"]))
    per = collections.defaultdict(lambda: {"cost": 0.0, "landed": False, "status": "?", "roles": set()})
    for r in rows:
        p = per[r["ticket"]]; p["cost"] += r["cost"]; p["landed"] |= r["landed"]; p["status"] = r["status"]; p["roles"].add(r["role"])
    n = len(per); nl = sum(1 for p in per.values() if p["landed"]); tot = sum(p["cost"] for p in per.values())
    neg = sum(1 for p in per.values() if p["status"] in ("NEGATIVE", "BLOCKED"))
    print("\ntickets %d, landed %d, pi spend $%.2f, $/landed %s, NEGATIVE+BLOCKED %d (%.0f%%)" % (
        n, nl, tot, ("%.3f" % (tot / nl)) if nl else "-", neg, 100.0 * neg / n if n else 0))
    for t, p in sorted(per.items(), key=lambda kv: -kv[1]["cost"])[:8]:
        print("  %-6s %-8s %s $%.3f %s" % (t, p["status"], "landed" if p["landed"] else "kept  ", p["cost"], "+".join(sorted(p["roles"]))))


if __name__ == "__main__":
    main()
