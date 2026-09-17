#!/usr/bin/env python3
"""Do the instructions still describe the project? A worker only knows what AGENT_GUIDE.md, AGENTS.md and its
role file tell it, and those drift behind the tools every day. This checks them mechanically and for free:
paths and tools they cite that no longer exist, tools added or changed lately that nothing tells a worker
about, rules stated in one place and contradicted in another, and whether workers are reading the guide whole.
Printed by tools/daily_review.sh; a finding trips the auditor the way the blocked rate does.

  python3 tools/docs_check.py [--since-days 7] [--json]
"""
import argparse, collections, glob, json, os, re, subprocess, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..")); os.chdir(ROOT)
# every file an agent is told to read: the shared rules, the worker guide, the role and loop texts, the
# handoff sections tickets cite, and the contracts a ticket sends a worker to.
DOCS = sorted(set(["AGENT_GUIDE.md", "AGENTS.md", "HANDOFF.md", "FIXTURE.md", ".pi/coordinator.md"]
                  + glob.glob(".pi/roles/*.md") + glob.glob("docs/HANDOFF_*.md") + glob.glob("docs/*.md")))
# changelogs and records are history, not instructions: an agent is never sent to them
DOCS = [d for d in DOCS if os.path.exists(d) and not d.startswith(("docs/reviews/", "docs/audits/", "docs/proposals/", "docs/benchmarks/", "docs/tickets/", "docs/worklog/"))
        and os.path.basename(d) not in ("config-log.md", "note_audits.md", "measurement-drift.md", "renames.md")]
PATH = re.compile(r"\b((?:tools|docs|src|web|reference)/[A-Za-z0-9_./<>-]+|[A-Z][A-Z_]+\.md)\b")


def sh(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since-days", type=int, default=7); ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    text = {d: open(d).read() for d in DOCS if os.path.exists(d)}
    all_text = "\n".join(text.values())
    index = open("tools/README.md").read() if os.path.exists("tools/README.md") else ""   # the generated index counts as documentation
    findings = []

    # 1. a cited path that does not exist (placeholders such as <ID> are skipped)
    for d, s in text.items():
        for m in sorted({m.group(1) for m in PATH.finditer(s)}):
            if "<" in m or m.endswith("/") or "*" in m: continue
            if not os.path.exists(m.split(":")[0]):
                findings.append("%s cites %s, which does not exist" % (d, m))

    # 2. a tool the WORK uses that no instruction mentions: named by a ticket, or run by a worker, in the window.
    #    (Most of tools/ is infrastructure a worker never touches; listing all of it was noise.)
    tickets = ""
    for f in ("TODO.md", "TODO_ARCHIVE.md"):
        if os.path.exists(f): tickets += open(f).read()
    recent_tickets = sh("git log --since='%d days ago' --format=%%s" % a.since_days)
    used = collections.Counter()
    for f in glob.glob("/tmp/bn-pi/*/session/subagent-artifacts/*worker*_transcript.jsonl"):
        for m in re.finditer(r"tools/([a-z0-9_]+\.(?:py|sh))", open(f, errors="replace").read()):
            used["tools/" + m.group(1)] += 1
    for t in sorted(glob.glob("tools/*.py") + glob.glob("tools/*.sh")):
        base = os.path.basename(t)
        if base in all_text or t in all_text or t in index: continue
        by_ticket = t in tickets or base in tickets
        by_worker = used.get(t, 0) >= 3
        if by_ticket or by_worker:
            why = []
            if by_ticket: why.append("tickets name it")
            if by_worker: why.append("workers ran it %d times" % used[t])
            findings.append("no instruction mentions %s (%s)" % (t, ", ".join(why)))

    # 3. a version string in the instructions that the tool itself has moved past (TRC2 v2 vs v3 style)
    for d, s in text.items():
        for m in re.finditer(r"\b([A-Z]{2,6})\s*v(\d+)\b", s):
            name, ver = m.group(1), int(m.group(2))
            newest = max([int(x) for x in re.findall(r"%s v(\d+)" % name, sh("grep -rho '%s v[0-9]' tools/ src/ || true" % name))] or [ver])
            if newest > ver: findings.append("%s says %s v%d; the code writes v%d" % (d, name, ver, newest))

    # 4. a rule spliced by an earlier edit: a lower-case word followed by a capitalised clause and a colon,
    #    which is what "edit only the files the Never commit on main:" looked like (2026-09-16)
    for d, s in text.items():
        for m in re.finditer(r"[a-z]{3,} ((?:Never|Always|Do not|Only|Every|The) [a-z][^.:\n]{0,60}:)", s):
            findings.append("%s may have a spliced rule near %r" % (d, m.group(0)[:70]))

    if os.path.exists("tools/index.py"):
        r = subprocess.run("python3 tools/index.py --check", shell=True, capture_output=True, text=True)
        if r.returncode != 0: findings.append("tools/README.md is out of date (python3 tools/index.py rewrites it)")

    # 5. are workers reading the guide whole?
    lines = len(open("AGENT_GUIDE.md").read().splitlines()) if os.path.exists("AGENT_GUIDE.md") else 0
    heads = collections.Counter()
    for f in glob.glob("/tmp/bn-pi/*/session/subagent-artifacts/*_transcript.jsonl"):
        for m in re.finditer(r"AGENT_GUIDE\.md[^\"]{0,40}?head -n? ?(\d+)", open(f, errors="replace").read()):
            heads[int(m.group(1))] += 1
    cut = sum(n for k, n in heads.items() if k < lines)
    whole = sum(n for k, n in heads.items() if k >= lines)
    if cut and cut >= whole: findings.append("workers truncate AGENT_GUIDE.md more often than not (%d reads cut short of its %d lines, %d whole)" % (cut, lines, whole))

    print("instructions checked: %s" % ", ".join(text))
    print("AGENT_GUIDE.md is %d lines; reads seen: %s" % (lines, dict(heads) or "none in the artifacts on disk"))
    if findings:
        for f in findings: print("- " + f)
    else:
        print("- nothing stale found")
    print("\nDOCS-TRIGGER: %s" % ("yes" if findings else "no"))


if __name__ == "__main__":
    main()
