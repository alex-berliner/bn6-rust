#!/usr/bin/env python3
"""Admit the judge's proposed tickets into TODO.md without a human, if each passes the template check:
a `### ID. title *(OPEN -- date)*` heading with a fresh ID, a `**Files.**` line, an `**Acceptance.**` (or
`**Measure and report.**`) section, and a reference to a docs/SCOPE.md milestone (M1..M11) or to an OPEN
ticket it follows. Appends the accepted tickets to the T section, commits TODO.md alone, and prints what it
admitted or refused.  usage: python3 tools/judge_append.py <proposal.md>"""
import os, re, subprocess, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
HEAD = re.compile(r"^### ([A-Z]+\d+[a-z]?)\. .*\*\((OPEN)\b.*\)\*\s*$", re.M)
p = sys.argv[1]; text = open(p).read()
todo = open(os.path.join(ROOT, "TODO.md")).read(); arch = open(os.path.join(ROOT, "TODO_ARCHIVE.md")).read()
known = set(re.findall(r"^### ([A-Z]+\d+[a-z]?)\. ", todo + arch, re.M)) | set(re.findall(r"^- ([A-Z]+\d+[a-z]?) ", todo, re.M))
heads = list(HEAD.finditer(text)); admitted, refused = [], []
for i, m in enumerate(heads):
    body = text[m.start():heads[i + 1].start() if i + 1 < len(heads) else len(text)].rstrip() + "\n\n"
    tid = m.group(1); why = []
    if tid in known: why.append("id exists")
    if "**Files.**" not in body: why.append("no Files line")
    if "**Acceptance.**" not in body and "**Measure and report.**" not in body: why.append("no acceptance")
    if not re.search(r"\bM(1[01]|[1-9])\b", body) and not re.search(r"\b(follows|follow-up to|after) [A-Z]+\d+[a-z]?\b", body): why.append("no milestone or predecessor")
    if len(body) > 6000: why.append("too long")
    (refused if why else admitted).append((tid, why, body))
if admitted:
    # at the END of the T section (older OPEN tickets keep their place in the queue), before the next section
    k = todo.index("## T. Trace-driven porting"); nxt = todo.find("\n## ", k + 1); k = len(todo) if nxt < 0 else nxt + 1
    todo = todo[:k].rstrip("\n") + "\n\n" + "".join(b for _, _, b in admitted) + todo[k:]
    open(os.path.join(ROOT, "TODO.md"), "w").write(todo)
    subprocess.run(["git", "-C", ROOT, "add", "TODO.md"], check=True)
    subprocess.run(["git", "-C", ROOT, "commit", "-q", "-m", "TODO: judge-admitted %s (tools/judge_append.py)\n\nCo-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" % ", ".join(t for t, _, _ in admitted)], check=True)
print("admitted:", [t for t, _, _ in admitted]); print("refused:", [(t, w) for t, w, _ in refused])
