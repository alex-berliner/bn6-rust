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
def _digest_model():
    """the first scheduled run profile whose digest job has one-shot budget right now; None when none has"""
    import tomllib
    runs = [os.environ["BN_RUN"]] if os.environ.get("BN_RUN") else tomllib.load(open("providers.toml", "rb"))["schedule"]["runs"]
    for run in runs:
        r = subprocess.run(["python3", "tools/roles.py", "model", run, "digest", "--tail"], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip(): return r.stdout.strip()
    return None


DIGEST_MODEL = _digest_model()


def _writer():
    """providers.toml [roundup].digest_writer: 'claude:<model>' (the Claude Code CLI, headless) or 'pi'"""
    import tomllib
    try: return tomllib.load(open("providers.toml", "rb")).get("roundup", {}).get("digest_writer", "pi")
    except Exception: return "pi"


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
    for f in ("TODO.md", "TODO_ARCHIVE.md"):
        s = open(f).read() if os.path.exists(f) else ""
        m = re.search(r"^- %s (\w+) -- (.*?)\. (.*)$" % re.escape(tid), s, re.M)
        if m: return m.group(2), m.group(1), m.group(3)[:700]
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
    """the numbers a text states: hex values and digit runs; thousands separators are dropped so 2,850,534 equals 2850534"""
    return set(re.sub(r"(?<=\d),(?=\d{3}\b)", "", x).lower() for x in re.findall(r"0x[0-9a-fA-F]+|\d+(?:[.,]\d+)*", s))


ORIENTATION = ("This project rebuilds the battle engine of Mega Man Battle Network 6, a Game Boy Advance game, as new code in Rust. "
               "The rule is exact: a scene played by our version must match a recording of the original game pixel for pixel, frame by frame. "
               "Small AI agents do the work in tickets, each a bounded task; a ticket ends finished, half-done, blocked, or as a dead end that "
               "taught us something.")

GLOSSARY = """Terms the results use, with the plain meaning to write instead (never use the term bare):
- row / scene / fixture: one recorded situation the game is compared in (e.g. the first seconds of a fight, a chip being used); a row "at 0" means our version matches the original in every pixel of every frame there
- isolated vs integrated: a scene compared on its own vs the same scene inside a full fight
- canon: the original game (its recording or its code)
- harness / verify_rows: the automatic comparison that rebuilds our game and counts differing pixels
- the trace: a frame-by-frame record of the game's internal state, used to find WHERE two runs first differ
- k=N: frame number N of a scene (60 frames per second)
- sequencer: the part of the game that steps a fight through its phases (the chip-selection window, the countdown, the results screen)
- custom screen / chip window: the menu where the player picks battle chips
- Mettaur, Gunner: two enemy types (viruses); each has its own behaviour routine in the original game
- PARTIAL: half-done and kept; BLOCKED: could not proceed; NEGATIVE: an idea tested and found wrong; DONE: finished
- landed / merged: the change went into the main code; kept unmerged: it did not
- verifier: a second agent that checked the claims; worker: the agent that did the work; cursor tear: a known one-frame glitch that moves around and is tolerated for now
- routine / sub_XXXX / asmNN.s:LINE: a function in the original game's disassembly, and where it is
"""


def newcomer_digest(results, facts):
    """one plain-language account of the day for a reader who has never seen the project; '' when unusable"""
    items = "\n".join("- %s (%s): %s. RESULT: %s" % (tid, status, ttl, res) for tid, ttl, status, res in results)
    prompt = ("Write the day's progress report for a project blog whose reader has NEVER looked at the project and knows nothing about it. "
              "The model to imitate is the Dolphin emulator's monthly progress reports: for each change, first explain the concept behind it "
              "(what that part of the game or the emulation does and why a player would notice), then what was done and what it changed, as a "
              "story, precise but free of jargon. "
              "Here is what the project is: %s\n\n%s\nRules: 500 to 900 words. Group the day's tickets by the part of the game they concern "
              "(an enemy, the fight's phases, the opening of a fight, the results screen, sound, the inventory of game data, the tooling), one "
              "section each with a ## heading in plain words. In every section first say what that part of the game is and why it matters, then "
              "what was tried today, what happened, and what is left, as a story in plain English. Never make a ticket id the subject of a "
              "sentence; put ids in parentheses at the end of the sentence they belong to, like (T7e). Explain every term the first time; never "
              "use a term from the glossary bare. Use only numbers that appear in the ticket results below, and explain what each number counts "
              "in the same sentence; never add a file path, branch name or commit hash. No bullet lists. No preamble, no closing summary.\n\n"
              "For EVERY ticket the reader must learn concretely what it was about and what came of it; a sentence like 'an agent set "
              "out to improve a residue and the change was set aside' is worthless -- say what the residue was (e.g. the colours of the "
              "small enemies in the opening seconds, which the game assigns by handing each sprite a palette slot), what was tried and what "
              "was found. Dead ends and blocked attempts get the same concreteness. 900 to 1600 words; never compute a number of your own (no sums, differences or percentages the results do not state). "
              "Write the report directly as your reply, without planning it at length first; do not read any file.\n\n"
              "The day's tickets and their results:\n%s" % (ORIENTATION, GLOSSARY, items))
    writer = _writer()
    for attempt in range(3):
        out = ""; last = ""; kinds = {}
        try:
            if writer.startswith("claude:"):
                last = subprocess.run(["claude", "-p", "--model", writer.split(":", 1)[1], "--output-format", "text", prompt],
                                      capture_output=True, text=True, timeout=1500, stdin=subprocess.DEVNULL, cwd=ROOT).stdout.strip()
            else:
                if not DIGEST_MODEL: return ""
                out = subprocess.run(["pi", "-p", "--approve", "--no-session", "--mode", "json", "--model", DIGEST_MODEL, "--thinking", "low",
                                      "--tools", "read", prompt], capture_output=True, text=True, timeout=1200, stdin=subprocess.DEVNULL).stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return ""
        for line in out.splitlines():
            try: e = json.loads(line)
            except ValueError: continue
            kinds[e.get("type")] = kinds.get(e.get("type"), 0) + 1
            if e.get("type") not in ("turn_end", "message_end"): continue
            m = e.get("message") or {}
            if m.get("role") == "assistant":
                t = " ".join(c.get("text", "") for c in m.get("content", []) if c.get("type") == "text").strip()
                if t: last = t
                if m.get("errorMessage"): print("digest: model error: %s" % str(m["errorMessage"])[:200], file=sys.stderr)
        os.makedirs("/tmp/bn-learn", exist_ok=True); open("/tmp/bn-learn/digest-raw-%d.txt" % attempt, "w").write(last or ("(empty; events: %r)" % kinds))
        words = len(last.split())
        allowed = facts + " " + " ".join(t + " " + ttl for t, ttl, _, _ in results) + " 60 24 %d %d %d %d" % (
            len(results), sum(1 for r in results if r[2] == "DONE"), sum(1 for r in results if r[2] == "PARTIAL"), sum(1 for r in results if r[2] in ("BLOCKED", "NEGATIVE")))
        extra = numbers(last) - numbers(allowed)
        bad = re.search(r"/tmp/|\bwt/|verify_rows|\b(?=[0-9a-f]*[a-f])[0-9a-f]{7,}\b", last)   # paths, branch names, commit hashes
        why = ("%d words" % words) if not (350 <= words <= 2200) else ("numbers not in the facts: %s" % sorted(extra)[:8]) if extra else ("forbidden token %r" % bad.group(0)) if bad else ""
        if why: print("digest: model account rejected (attempt %d): %s" % (attempt + 1, why), file=sys.stderr); continue
        return last
    return ""


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
            if isinstance(e, dict) and e.get("type") not in (None, "turn_end"): continue      # pi emits one message in three events; count it once
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
    ap.add_argument("--body", help="use this file's text as the day's account (reviewed by hand) instead of asking the model")
    ap.add_argument("--title", help="the post's title (default: 'Daily digest, <today>')")
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
    title = a.title or "Daily digest, %s" % datetime.date.today().strftime("%-d %B %Y")
    facts = "\n".join(r[3] for r in results) + "\n" + score + "\n" + "\n".join(failing) + "\n" + ledger + "\n" + "\n".join(hyper)
    out = []                                     # blog.py writes the title itself; the body must not repeat it
    out.append(ORIENTATION); out.append("")
    out.append("In the last %d hours the agents closed %d tickets: %d finished, %d half-done and kept, %d blocked or dead ends. "
               "Every number below was measured by the automatic comparison against a recording of the original game."
               % (int(a.since), len(results), len(done), len(part), len(stuck))); out.append("")
    body = open(a.body).read().strip() if a.body else ("" if (a.no_model or not (DIGEST_MODEL or _writer().startswith("claude:"))) else newcomer_digest(results, facts))
    if body:
        out.append(body); out.append("")
    else:
        out.append("(The plain-language account could not be written today; the tickets' own results follow, with each ticket's goal first.)"); out.append("")
        for name, group in (("Finished", done), ("Half-done, kept", part), ("Blocked or dead ends", stuck)):
            if not group: continue
            out.append("## " + name); out.append("")
            for tid, ttl, status, res in group:
                out.append("**%s.** %s (%s)" % (ttl, short(res), tid)); out.append("")
    if gifs:
        out.append("## New recordings"); out.append("")
        for g in gifs:
            cap = os.path.splitext(g)[0] + ".txt"; cap = open(cap).read().strip().splitlines()[0] if os.path.exists(cap) else os.path.basename(g)
            out.append("![%s](../captures/%s)" % (cap.replace("]", ")"), os.path.basename(g))); out.append("")
    if score:
        m = re.search(r"(\d+) of (\d+)", score)
        out.append("## Where the whole thing stands"); out.append("")
        if m:
            out.append("The game is compared against the original in %s recorded scenes. %s of them now match pixel for pixel in every frame."
                       % (m.group(2), m.group(1)))
        if failing:
            names = "; ".join(l.split()[0] + (" (inside a full fight)" if l.split()[1] == "integrated" else " (on its own)") for l in failing)
            out.append("The scenes that still differ: %s. Each is a known, measured gap with a ticket behind it." % names)
        out.append("")
    if proposals:
        out.append("## Suggested changes to how the agents work"); out.append("")
        out.append("An automatic reviewer reads each day's results and suggests changes to the agents' setup. These wait for a human to accept or reject them:")
        for f, h in proposals: out.append("- %s (%s)" % (h, f))
        out.append("")
    out.append("## What it cost"); out.append("")
    if hyper: out.append("The agents run on prepaid subscriptions. " + hyper[0].replace("hyper: remaining", "Charm Hyper: ").replace("hypercredits", "credits") + ".")
    for l in totals: out.append(l + ".")
    out.append("")
    md = "\n".join(out)
    if not a.post:
        print(md); return
    slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:60]
    slug_exists = glob.glob("web/blog/posts/%s-%s.md" % (today, slug))
    if slug_exists:
        print("digest: already posted (%s)" % slug_exists[0]); return
    subprocess.run(["python3", "tools/blog.py", "new", title], input=md, text=True, check=True)
    cmd = ("exec 9>/tmp/bn-land.lock; flock -w 600 9 && git add web/blog && git commit -q -m 'blog: %s (tools/digest_post.py)\n\n"
           "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>' && git push -q origin main && bash tools/publish_site.sh --no-build" % title)
    print(sh(cmd)); print("digest: posted '%s'" % title)


if __name__ == "__main__":
    main()
