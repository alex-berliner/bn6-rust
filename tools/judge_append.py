#!/usr/bin/env python3
"""Admit the judge's proposed tickets into TODO.md without a human, if each passes the template check:
a `### ID. title *(OPEN -- date)*` heading with a fresh ID, a `**Files.**` line, an `**Acceptance.**` (or
`**Measure and report.**`) section, and a reference to a docs/SCOPE.md milestone (M1..M11) or to an OPEN
ticket it follows. Appends the accepted tickets to the T section, commits TODO.md alone, and prints what it
admitted or refused.  usage: python3 tools/judge_append.py <proposal.md>"""
import fcntl, os, re, subprocess, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# TODO.md is one file in one shared checkout, and every run's judge and every run's coordinator do a
# read-modify-write on it. Two at the same second meant the second read a TODO.md without the first's
# tickets and wrote them back out: a whole admitted batch gone, with both processes reporting success.
# This got likelier when the daily batch cap went 12 -> 40 and the judge stopped being pinned to one
# provider (2026-09-17). Held until the process exits, which is after the commit.
_lock = open("/tmp/bn-land.lock", "w"); fcntl.flock(_lock, fcntl.LOCK_EX)
# How a judge opens a ticket is not something any prompt has managed to pin down, and every variant that
# did not match used to cost a whole batch of good tickets. On 2026-09-17 alone: "# T107." instead of
# "### T107." threw away a 3,000-word proposal, and later the same day five complete, well-formed tickets
# (T143-T147, every section present) were discarded because they opened "**T143** -- title" with no hash
# and no OPEN stamp. Patching one variant at a time loses another batch each time, so this accepts the
# family -- any heading level or none, bold or plain, stamp or no stamp -- and normalises it.
#
# Over-matching is safe here: a line that merely mentions a ticket id becomes a candidate, and then the
# template check below refuses it for having no Files line and no acceptance. A false positive costs a
# refusal line in the log; a false negative costs five tickets.
HEAD = re.compile(
    r"^(?:#{1,4}\s*)?\*{0,2}([A-Z]+\d+[a-z]?)\*{0,2}[.:]?\s*(?:--|\u2014|-|\.)?\s+\S.*$", re.M)
p = sys.argv[1]; text = open(p).read()
todo = open(os.path.join(ROOT, "TODO.md")).read(); arch = open(os.path.join(ROOT, "TODO_ARCHIVE.md")).read()
known = set(re.findall(r"^### ([A-Z]+\d+[a-z]?)\. ", todo + arch, re.M)) | set(re.findall(r"^- ([A-Z]+\d+[a-z]?) ", todo, re.M))
# statuses of every ticket, to refuse proposals that continue an objective a NEGATIVE or BLOCKED ticket just closed
STATUS = {}
for m in re.finditer(r"^### ([A-Z]+\d+[a-z]?)\. .*?\*\((\w+)\b", todo + arch, re.M): STATUS[m.group(1)] = m.group(2)
for m in re.finditer(r"^- ([A-Z]+\d+[a-z]?) (\w+) -- ", todo + arch, re.M): STATUS.setdefault(m.group(1), m.group(2))
# a daily cap: the judge minted three chained dead ends an hour overnight on 2026-09-16
today_batches = subprocess.run("git -C %s log --since='%s 00:00' --format=%%s | grep -c judge-admitted" % (ROOT, __import__('datetime').date.today().isoformat()), shell=True, capture_output=True, text=True).stdout.strip()
heads = list(HEAD.finditer(text)); admitted, refused = [], []
for i, m in enumerate(heads):
    body = text[m.start():heads[i + 1].start() if i + 1 < len(heads) else len(text)].rstrip() + "\n\n"
    # A bare label line ("T143 (M8):") above the real ticket also matches the heading family. It is not a
    # ticket and refusing it is just noise in the log, so anything too short to hold a ticket is skipped.
    if len(body.strip()) < 200:
        continue
    tid = m.group(1); why = []
    if tid in known:
        base = re.match(r"([A-Z]+\d+)", tid).group(1)
        for suffix in list("bcdefghijklmnopqrstuvwxyz"):
            if base + suffix not in known and base + suffix not in [t for t, _, _ in admitted]:
                body = body.replace("### %s." % tid, "### %s." % (base + suffix), 1); tid = base + suffix; break
        else: why.append("id exists and no free suffix")
    if "**Files.**" not in body: why.append("no Files line")
    if "**Acceptance.**" not in body and "**Measure and report.**" not in body: why.append("no acceptance")
    if not re.search(r"\bM(1[01]|[1-9])\b", body) and not re.search(r"\b(follows|follow-up to|after) [A-Z]+\d+[a-z]?\b", body): why.append("no milestone or predecessor")
    if len(body) > 9000: why.append("too long (over 9000 characters; the judge is asked for 5000)")
    whytext = re.search(r"\*\*Why\.\*\*(.*?)(?=\n\*\*|\Z)", body, re.S); whytext = whytext.group(1) if whytext else body
    dead = sorted({r for r in re.findall(r"\b([A-Z]+\d+[a-z]?)\b", whytext) if STATUS.get(r) in ("NEGATIVE", "BLOCKED")})
    if dead and "**New evidence.**" not in body: why.append("continues an objective closed by %s; needs a **New evidence.** section (a measurement made after that close, or a recon map)" % ", ".join("%s (%s)" % (r, STATUS[r]) for r in dead))
    if today_batches.isdigit() and int(today_batches) >= 40: why.append("daily cap: %s judge batches already admitted today" % today_batches)
    # Rewrite whatever shape the first line arrived in into the one TODO.md and every reader expect.
    first, _, rest = body.partition("\n")
    stamp = "" if re.search(r"\*\(\w+\b", first) else " *(OPEN -- %s)*" % __import__('datetime').date.today().isoformat()
    titletext = re.sub(r"^(?:#{1,4}\s*)?\*{0,2}[A-Z]+\d+[a-z]?\*{0,2}[.:]?\s*(?:--|\u2014|-|\.)?\s+", "", first).strip()
    titletext = re.sub(r"\s*\*\(\w+\b[^)]*\)\*\s*$", "", titletext)
    # A judge often writes the whole ticket as one paragraph, so the "first line" is the entire ticket.
    # The heading must stay a heading: cut it at the first section marker and push the rest into the body,
    # or TODO.md gets a 1,400-character title and becomes unreadable.
    cut = titletext.find("**")
    if cut > 0:
        titletext, carried = titletext[:cut].strip(), titletext[cut:].strip()
        rest = carried + ("\n" + rest if rest else "")
    body = "### %s. %s%s\n\n%s" % (tid, titletext, stamp, rest)
    (refused if why else admitted).append((tid, why, body))
if admitted:
    # at the END of the T section (older OPEN tickets keep their place in the queue), before the next section
    k = todo.index("## T. Trace-driven porting"); nxt = todo.find("\n## ", k + 1); k = len(todo) if nxt < 0 else nxt + 1
    todo = todo[:k].rstrip("\n") + "\n\n" + "".join(b for _, _, b in admitted) + todo[k:]
    open(os.path.join(ROOT, "TODO.md"), "w").write(todo)
    subprocess.run(["git", "-C", ROOT, "add", "TODO.md"], check=True)
    subprocess.run(["git", "-C", ROOT, "commit", "-q", "-m", "TODO: judge-admitted %s (tools/judge_append.py)\n\nCo-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" % ", ".join(t for t, _, _ in admitted)], check=True)
print("admitted:", [t for t, _, _ in admitted]); print("refused:", [(t, w) for t, w, _ in refused])
# A batch that admits nothing is the loop failing to feed itself, and it is silent otherwise: the judge
# reports success, the file is written, and the queue stays empty. That is how a heading-format bug threw
# away whole proposals for days (2026-09-17).
if not admitted:
    subprocess.run(["bash", os.path.join(ROOT, "tools", "incident.sh"), "judge-discarded",
                    "%s admitted 0 of %d proposed: %s" % (os.path.basename(p), len(refused),
                                                          "; ".join("%s %s" % (t, w) for t, w, _ in refused)[:400])])
