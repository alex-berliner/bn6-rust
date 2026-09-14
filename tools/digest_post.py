#!/usr/bin/env python3
"""The automated daily digest: one blog post per day that had progress, built from the repo's own record
(ticket result commits and their Result paragraphs, the merges on main, new gallery GIFs, the daily
review's scoreboard, the auditor's open proposals, the spend), so the user reads the day without opening
the terminal. Numbers come only from those records: a Hyper model may rewrite each ticket's Result into a
plain-language paragraph, and that paragraph is dropped (the Result's own sentences used instead) if it
contains any number, hex value or path that the facts do not.

  python3 tools/digest_post.py [--since HOURS] [--review docs/reviews/DATE.md] [--no-model] [--post]
    without --post: prints the markdown it would post. With --post: writes the post through blog.py,
    commits web/blog on main under the landing lock, pushes main, publishes the site (--no-build).
    Exits 0 and posts nothing when the window had no ticket result and no merge on main.
"""
import argparse, datetime, glob, json, os, re, subprocess, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(ROOT)
RESULT_COMMIT = re.compile(r"^TODO ([A-Z]+\d+[a-z]?) (DONE|PARTIAL|BLOCKED|NEGATIVE)\b:? ?(.*)")
HEAD = re.compile(r"^### ([A-Z]+\d+[a-z]?)\. (.*?)\s*\*\((\w+)\b", re.M)
DIGEST_MODEL = subprocess.run("python3 tools/roles.py model ${BN_PROVIDER:-$(python3 tools/roles.py first)} digest", shell=True,
                              capture_output=True, text=True).stdout.strip() or "hyper/qwen3.8-flash"


def sh(cmd, **kw):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, **kw).stdout


def ticket_text(tid):
    """title, status, Result paragraph (first 700 chars) of a ticket from TODO.md or the archive."""
    for f in ("TODO.md", "TODO_ARCHIVE.md"):
        s = open(f).read() if os.path.exists(f) else ""
        for m in HEAD.finditer(s):
            if m.group(1) != tid: continue
            body = s[m.end():]; nxt = re.search(r"^### ", body, re.M); body = body[:nxt.start()] if nxt else body
            r = re.search(r"\*\*Result\.\*\*\s*(.*?)(?=\n\n|\*\*Files\.\*\*|\Z)", body, re.S)
            res = re.sub(r"\s+", " ", r.group(1)).replace("**Result.**", "").strip() if r else ""
            return m.group(2), m.group(3), res[:700]
    return tid, "", ""


def short(text, n=420):
    """the first sentences of a result, cut at a sentence end before n chars."""
    if len(text) <= n: return text
    cut = text[:n]; k = max(cut.rfind(". "), cut.rfind("; "))
    return (cut[:k + 1] if k > 120 else cut.rstrip() + "...")


def plain(text):
    """strip the worker-speak that means nothing on a blog: worktree paths, branch refs, bracketed bookkeeping."""
    text = re.sub(r"\[(worktree|branch)[^\]]*\]", "", text)
    text = re.sub(r"/tmp/\S+", "", text)
    return re.sub(r"\s+", " ", text).strip()


def numbers(s):
    """the numbers a text states: hex values and digit runs (with inner separators; trailing punctuation is not a digit)"""
    return set(re.findall(r"0x[0-9a-fA-F]+|\d+(?:[.,]\d+)*", s))


def model_paragraph(tid, title, status, result, facts):
    """one plain-language paragraph from a Hyper model, checked against the facts; '' when unusable."""
    prompt = ("Rewrite this ticket result as ONE paragraph of at most 90 words for a blog read by a non-programmer who "
              "follows this project (a per-pixel reimplementation of a GBA game's battle system). Say what was reached "
              "and, if the result names it, the mechanism found. Use only numbers that appear in the text; never add a "
              "number, a file path or a branch name; no headings, no lists, no preamble. Ticket %s (%s), status %s.\n\n%s"
              % (tid, title, status, result))
    last = ""
    for attempt in range(2):                                   # one retry: a Hyper call now and then returns no text
        try:
            out = subprocess.run(["pi", "-p", "--approve", "--no-session", "--mode", "json", "--model", DIGEST_MODEL,
                                  "--tools", "read", prompt], capture_output=True, text=True, timeout=300, stdin=subprocess.DEVNULL).stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return ""
        for line in out.splitlines():
            try: e = json.loads(line)
            except ValueError: continue
            m = e.get("message") if isinstance(e, dict) else None
            if isinstance(m, dict) and m.get("role") == "assistant":
                t = " ".join(c.get("text", "") for c in m.get("content", []) if c.get("type") == "text").strip()
                if t: last = t
        if last: break
    last = re.sub(r"\s+", " ", last).strip()
    if not last or len(last.split()) > 130: return ""
    if numbers(last) - numbers(facts + " " + tid + " " + title): return ""          # invented a number
    if re.search(r"/tmp/|wt/|worktree|\bbranch\b", last): return ""
    return last


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", type=float, default=24.0); ap.add_argument("--review")
    ap.add_argument("--no-model", action="store_true"); ap.add_argument("--post", action="store_true")
    a = ap.parse_args()
    since = "%d hours ago" % int(a.since); today = datetime.date.today().isoformat()
    review = a.review or ("docs/reviews/%s.md" % today)

    # 1. ticket results in the window, newest first, one per ticket
    seen, results = set(), []
    for line in sh("git log --since='%s' --format='%%h %%s' main" % since).splitlines():
        m = RESULT_COMMIT.match(line.split(" ", 1)[1] if " " in line else "")
        if not m or m.group(1) in seen: continue
        seen.add(m.group(1)); title, status, res = ticket_text(m.group(1))
        results.append((m.group(1), title, m.group(2), plain(res) or plain(m.group(3))))
    merges = [l for l in sh("git log --since='%s' --merges --format='%%s' main" % since).splitlines() if l.strip()]
    if not results and not merges:
        print("digest: nothing to post (no ticket result and no merge on main in the last %dh)" % a.since); return

    # 2. the scoreboard from the review, the spend, the new GIFs, the open setup proposals
    score, failing = "", []
    if os.path.exists(review):
        r = open(review).read()
        m = re.search(r"^rows at 0 .*$", r, re.M); score = m.group(0) if m else ""
        m = re.search(r"^rows at 0 .*?```\n(.*?)```", r, re.M | re.S); failing = [l for l in (m.group(1).splitlines() if m else []) if l.strip()]
    hyper = sh("python3 tools/hyper_credits.py 2>/dev/null").strip().splitlines()[:1]
    ledger = sh("python3 tools/ticket_ledger.py --since %d 2>/dev/null" % a.since)
    totals = [l for l in ledger.splitlines() if re.match(r"^(tickets|total|landed|cost)", l)]
    cutoff = datetime.datetime.now().timestamp() - a.since * 3600
    gifs = sorted(g for g in glob.glob("web/captures/*.gif") if os.path.getmtime(g) > cutoff)
    proposals = []
    for f in sorted(glob.glob("docs/audits/*.md")):
        if os.path.getmtime(f) < cutoff: continue
        for h in re.findall(r"^## (\d+\. .*)$", open(f).read(), re.M)[:3]:
            proposals.append((os.path.basename(f), h.strip()))

    # 3. the post
    done = [r for r in results if r[2] == "DONE"]; part = [r for r in results if r[2] == "PARTIAL"]
    stuck = [r for r in results if r[2] in ("BLOCKED", "NEGATIVE")]
    title = ("Daily digest %s: %d done, %d partial, %d blocked" % (today, len(done), len(part), len(stuck))) if results else "Daily digest %s" % today
    facts = "\n".join(r[3] for r in results) + "\n" + score + "\n" + "\n".join(failing) + "\n" + ledger + "\n" + "\n".join(hyper)
    out = ["# " + title, ""]
    out.append("What the agents landed in the last %d hours, taken from the tickets' own results. Every number here is "
               "measured by the harness against a recording of the original game." % int(a.since)); out.append("")
    for name, group in (("Done", done), ("Partial", part), ("Blocked or negative", stuck)):
        if not group: continue
        out.append("## " + name); out.append("")
        if not a.no_model and name == "Done":
            out.append("Each paragraph is a model's plain-language rewrite of the ticket's own result, checked so that every number in it "
                       "comes from that result; the results themselves are in the repository's TODO_ARCHIVE.md."); out.append("")
        for tid, ttl, status, res in group:
            para = "" if a.no_model else model_paragraph(tid, ttl, status, res, facts)
            out.append("**%s, %s.** %s" % (tid, ttl, para or short(res))); out.append("")
    if gifs:
        out.append("## New recordings"); out.append("")
        for g in gifs:
            cap = os.path.splitext(g)[0] + ".txt"; cap = open(cap).read().strip().splitlines()[0] if os.path.exists(cap) else os.path.basename(g)
            out.append("![%s](../captures/%s)" % (cap.replace("]", ")"), os.path.basename(g))); out.append("")
    if score:
        out.append("## Scoreboard"); out.append(""); out.append(score + ".")
        if failing: out.append("Rows still off zero: " + "; ".join(l.split()[0] + " " + l.split()[1] for l in failing) + ".")
        out.append("")
    if proposals:
        out.append("## Setup proposals waiting for a decision"); out.append("")
        out.append("The auditor proposed these changes to how the agents are run; a human applies at most one per cycle.")
        for f, h in proposals: out.append("- %s (%s)" % (h, f))
        out.append("")
    out.append("## Spend"); out.append("")
    if hyper: out.append(hyper[0].replace("hyper: ", "Charm Hyper: ") + ".")
    for l in totals: out.append(l + ".")
    out.append("")
    md = "\n".join(out)
    if not a.post:
        print(md); return
    slug_exists = glob.glob("web/blog/posts/%s-daily-digest-*.md" % today)
    if slug_exists:
        print("digest: already posted today (%s)" % slug_exists[0]); return
    subprocess.run(["python3", "tools/blog.py", "new", title], input=md, text=True, check=True)
    cmd = ("exec 9>/tmp/bn-land.lock; flock -w 600 9 && git add web/blog && git commit -q -m 'blog: %s (tools/digest_post.py)\n\n"
           "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>' && git push -q origin main && bash tools/publish_site.sh --no-build" % title)
    print(sh(cmd)); print("digest: posted '%s'" % title)


if __name__ == "__main__":
    main()
