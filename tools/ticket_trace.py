#!/usr/bin/env python3
"""Everything that happened on one ticket, as one readable timeline: which model played which part, what it
ran, what came back, what it decided, and what reached main. Nothing is recorded for this: it reassembles the
artifacts every run already writes (the coordinator's event log, each child's transcript and report, the run's
status log, and git). Meant for inspecting a ticket after the fact, not for running always.

  python3 tools/ticket_trace.py T19 [--out docs/tickets/T19.md] [--stdout] [--chars 220] [--full]
"""
import argparse, collections, datetime, glob, json, os, re, subprocess, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..")); os.chdir(ROOT)


def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout


def clock(ms):
    try: return datetime.datetime.fromtimestamp((int(ms) or 0) / 1000).strftime("%H:%M:%S")
    except (TypeError, ValueError): return "--:--:--"


def short(s, n):
    s = (s or "").strip()
    return s if len(s) <= n else s[:n] + " …"


def task_of(transcript):
    """the task a child was given (its first non-redacted user record)"""
    if not os.path.exists(transcript): return ""
    for line in open(transcript, errors="replace"):
        try: e = json.loads(line)
        except ValueError: continue
        if e.get("recordType") == "message" and e.get("role") == "user":
            t = (e.get("text") or "").strip()
            if t and "[prompt redacted]" not in t: return t
    return ""


def children_for(tid):
    """every child session that worked this ticket: its report names the ticket most often, or the task it was
    given names it (a verifier is told "Branch wt/q3-..., commit ...", so the report alone misses it)"""
    out = []
    word = re.compile(r"(?<![A-Za-z0-9])%s(?![A-Za-z0-9])" % re.escape(tid), re.I)
    for meta in glob.glob("/tmp/bn-pi/*/session/subagent-artifacts/*_meta.json"):
        rep = meta.replace("_meta.json", "_output.md")
        transcript = meta.replace("_meta.json", "_transcript.jsonl")
        text = open(rep, errors="replace").read() if os.path.exists(rep) else ""
        hits = collections.Counter(re.findall(r"\b([A-Z]{1,2}\d{1,3}[a-z]?)\b", text))
        top = hits.most_common(1)[0][0] if hits else None
        task = task_of(transcript)
        if top != tid and not word.search(task[:4000]): continue
        try: d = json.load(open(meta))
        except ValueError: continue
        out.append(dict(meta=meta, report=rep, transcript=transcript,
                        run=meta.split("/")[3], role=d.get("agent", "child"), model=str(d.get("model", "?")),
                        usage=d.get("usage") or {}, ts=int(d.get("timestamp") or 0)))
    return sorted(out, key=lambda c: c["ts"])


def events_from_transcript(path, actor, chars, rchars, thinking=True):
    """(ts, actor, kind, text) for one child's transcript. pi writes a child's file as records: `tool_start`
    carries the call and a preview of its arguments, `message` carries the assistant's words (inside `message`)
    and each tool result's text, `tool_end` the error flag."""
    out = []
    if not os.path.exists(path): return out
    for line in open(path, errors="replace"):
        try: e = json.loads(line)
        except ValueError: continue
        ts = e.get("ts") or 0
        kind = e.get("recordType")
        if kind == "tool_start":
            # argsPreview is pi's own truncation; argsPayload is the whole call, which is what a reader needs
            args = e.get("argsPayload")
            args = json.dumps(args) if not isinstance(args, str) else args
            if not args or args == "{}": args = e.get("argsPreview") or ""
            out.append((ts, actor, "runs", "%s %s" % (e.get("toolName"), short(args, 10 ** 9))))
        elif kind == "message" and e.get("role") == "assistant":
            m = e.get("message") or {}
            parts = m.get("content") if isinstance(m.get("content"), list) else []
            t = " ".join(c.get("text", "") for c in parts if isinstance(c, dict) and c.get("type") == "text").strip()
            if not t: t = (m.get("text") or "").strip()
            if thinking:
                th = " ".join(c.get("thinking", "") for c in parts if isinstance(c, dict) and c.get("type") in ("thinking", "reasoning")).strip()
                if th: out.append((ts, actor, "thinks", short(th, chars)))
            if t: out.append((ts, actor, "says", short(t, chars)))
            if m.get("errorMessage") or e.get("errorMessage"):
                out.append((ts, actor, "error", short(str(m.get("errorMessage") or e.get("errorMessage")), chars)))
        elif kind == "message" and e.get("role") == "toolResult":
            t = e.get("text") or ""
            out.append((ts, actor, "gets", "%s%s: %s" % (e.get("toolName"), " (error)" if e.get("isError") else "", short(t, rchars))))
        elif kind == "message" and e.get("role") == "user" and (e.get("text") or "").strip() not in ("", "[prompt redacted]"):
            out.append((ts, actor, "is told", short(e.get("text"), chars)))
    return out


def coordinator_events(run, tid, chars, window, thinking=True):
    """the coordinator's own turns that name the ticket, or fall inside its children's window"""
    ev = "/tmp/bn-pi/%s/events.jsonl" % run
    out = []
    if not os.path.exists(ev): return out
    lo, hi = window
    for line in open(ev, errors="replace"):
        if '"role":"assistant"' not in line: continue
        try: e = json.loads(line)
        except ValueError: continue
        if e.get("type") != "turn_end": continue
        m = e.get("message") or {}
        ts = m.get("timestamp") or 0
        blob = json.dumps(m)
        if tid not in blob and not (lo - 120000 <= ts <= hi + 600000): continue
        if thinking:
            th = " ".join(c.get("thinking", "") for c in m.get("content") or [] if c.get("type") in ("thinking", "reasoning")).strip()
            if th: out.append((ts, "coordinator", "thinks", short(th, chars)))
        t = " ".join(c.get("text", "") for c in m.get("content") or [] if c.get("type") == "text").strip()
        if t: out.append((ts, "coordinator", "says", short(t, chars)))
        for c in m.get("content") or []:
            if c.get("type") == "toolCall":
                args = json.dumps(c.get("arguments"))
                if tid in args or c.get("name") == "subagent" or "land.sh" in args or "verify_rows" in args or "ticket_result" in args:
                    out.append((ts, "coordinator", "runs", "%s %s" % (c.get("name"), args)))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ticket"); ap.add_argument("--out"); ap.add_argument("--stdout", action="store_true")
    ap.add_argument("--chars", type=int, default=4000, help="cap on a model's own words and thinking")
    ap.add_argument("--result-chars", type=int, default=800, help="cap on what a tool printed back")
    ap.add_argument("--no-thinking", action="store_true", help="leave the models' thinking out")
    ap.add_argument("--full", action="store_true", help="no caps at all")
    ap.add_argument("--worker-only", action="store_true", help="leave the coordinator's own turns out (the children's story alone)")
    a = ap.parse_args(); tid = a.ticket.upper()
    chars = 10 ** 9 if a.full else a.chars
    rchars = 10 ** 9 if a.full else a.result_chars
    kids = children_for(tid)
    if not kids: sys.exit("no session's report names %s (the artifacts under /tmp/bn-pi are wiped by a reboot)" % tid)
    runs = sorted({c["run"] for c in kids}); window = (min(c["ts"] for c in kids), max(c["ts"] for c in kids))
    timeline = []
    for c in kids:
        actor = "%s (%s)" % (c["role"], c["model"].split("/")[-1])
        timeline += events_from_transcript(c["transcript"], actor, chars, rchars, not a.no_thinking)
    if not a.worker_only:
        for r in runs:
            timeline += coordinator_events(r, tid, chars, window, not a.no_thinking)
    timeline.sort(key=lambda x: (int(x[0]) if str(x[0]).isdigit() else 0))
    # the ticket's own text, its result, and what reached main
    body = ""
    for f in ("TODO.md", "TODO_ARCHIVE.md"):
        if not os.path.exists(f): continue
        m = re.search(r"^### %s\. .*?(?=^### |\n## |\Z)" % re.escape(tid), open(f).read(), re.M | re.S)
        if m: body = m.group(0).strip(); break
    if not body:
        body = sh("python3 tools/next_ticket.py --id %s --results 0 2>/dev/null" % tid) or "(the ticket's text is no longer in TODO.md or the archive)"
    commits = sh("git log --format='%%h %%ad %%s' --date=format:'%%m-%%d %%H:%%M' --grep='\\b%s\\b' main | head -12" % tid)
    status_lines = []
    for r in runs:
        f = "/tmp/bn-pi/%s/status.log" % r
        if os.path.exists(f):
            status_lines += [l for l in open(f, errors="replace").read().splitlines() if tid in l]
    status = "\n".join(status_lines)
    out = ["# %s: everything that happened" % tid, "",
           "Reassembled from the run artifacts by tools/ticket_trace.py; nothing was recorded specially.", ""]
    out += ["## Who worked on it", "", "| when | part | model | turns | tokens | cost (nominal) |", "|---|---|---|---|---|---|"]
    for c in kids:
        u = c["usage"]; tok = (u.get("input", 0) or 0) + (u.get("output", 0) or 0) + (u.get("cacheRead", 0) or 0)
        out.append("| %s | %s | %s | %s | %s | $%.3f |" % (clock(c["ts"]), c["role"], c["model"], u.get("turns", "?"), tok, float(u.get("cost") or 0)))
    if status: out += ["", "## What the run recorded", "", "```", status, "```"]
    if commits.strip(): out += ["", "## What reached main", "", "```", commits.strip(), "```"]
    out += ["", "## The ticket as the worker received it", "", "```", body, "```"]
    out += ["", "## Timeline", ""]
    last_actor = None
    for ts, actor, kind, text in timeline:
        if actor != last_actor: out.append(""); last_actor = actor
        if len(text) > 300 or "\n" in text:
            out.append("- `%s` **%s** %s:" % (clock(ts), actor, kind))
            out.append("")
            out.append("  ```")
            out += ["  " + l for l in text.splitlines()]
            out.append("  ```")
        else:
            out.append("- `%s` **%s** %s: %s" % (clock(ts), actor, kind, text))
    doc = "\n".join(out) + "\n"
    if a.stdout: print(doc); return
    path = a.out or os.path.join("docs", "tickets", "%s.md" % tid)
    os.makedirs(os.path.dirname(path), exist_ok=True); open(path, "w").write(doc)
    print("wrote %s: %d sessions, %d timeline entries, %d KB" % (path, len(kids), len(timeline), len(doc) // 1024))


if __name__ == "__main__":
    main()
