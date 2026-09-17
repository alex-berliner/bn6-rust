#!/usr/bin/env python3
"""Carry the day's findings into the disassembly (reference/bn6f, branch bn-notes) as comment-only notes, the
way the September 6-8 notes were written by hand: for every ticket result recorded in the last N hours that
cites a line of the assembly, a model adds a `// bn <ticket> (<date>): ...` note at the cited site saying what
was found and where it lives in this repo's source; then a mechanical check keeps only comment lines added to
*.s files (anything else is reverted), the submodule commits on bn-notes and pushes to the fork, and the
main repo records the new submodule commit. Part of the roundup. Comments only: naming (a struct field that stops being Unk_, a routine that gets its
role in its name) is a separate pass gated by a rebuild to the ROM's sha1, since 2026-09-17 when the
disassembly stopped being read-only. usage:
  python3 tools/annotate_asm.py [--since 24] [--model provider/model] [--dry-run] [--post]
"""
import argparse, json, os, re, subprocess, sys, datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.chdir(ROOT)
SUB = "reference/bn6f"
CITE = re.compile(r"\b((?:asm|dat)[0-9_]+\.s):(\d+)(?:-(\d+))?")
RESULT_COMMIT = re.compile(r"^TODO ([A-Z]+\d+[a-z]?) (DONE|PARTIAL|BLOCKED|NEGATIVE)\b")


def sh(cmd, **kw):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, **kw).stdout


def results(since):
    """(ticket, status, result text) for the tickets stamped in the window, from TODO.md and the archive"""
    ids = []
    for line in sh("git log --since='%d hours ago' --format='%%s' main" % since).splitlines():
        m = RESULT_COMMIT.match(line)
        if m and m.group(1) not in [i for i, _ in ids]: ids.append((m.group(1), m.group(2)))
    text = open("TODO.md").read() + "\n" + (open("TODO_ARCHIVE.md").read() if os.path.exists("TODO_ARCHIVE.md") else "")
    out = []
    for tid, st in ids:
        m = re.search(r"^### %s\. (.*?)\*\(.*?^\*\*Result\.\*\*\s*(.*?)(?=\n\n|\*\*Files\.\*\*|\Z)" % re.escape(tid), text, re.M | re.S)
        res = re.sub(r"\s+", " ", m.group(2)).strip() if m else ""
        if not res:
            m2 = re.search(r"^- %s \w+ -- (.*)$" % re.escape(tid), text, re.M); res = m2.group(1) if m2 else ""
        cites = sorted({(c.group(1), int(c.group(2))) for c in CITE.finditer(res)})
        if cites: out.append((tid, st, res[:1200], cites))
    return out


def pick_model(explicit):
    if explicit: return explicit
    import tomllib
    for run in tomllib.load(open("providers.toml", "rb"))["schedule"]["runs"]:
        r = subprocess.run(["python3", "tools/roles.py", "model", run, "digest", "--tail"], capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip(): return r.stdout.strip()
    return None


def comment_only_diff():
    """Keep each changed file whose diff adds only // comment lines and removes nothing; revert every other file.
    True if anything was kept."""
    kept = []
    for line in sh("git -C %s diff --numstat" % SUB).splitlines():
        add, rem, f = line.split("\t")
        ok = f.endswith(".s") and rem == "0" and int(add) > 0
        if ok:
            for l in sh("git -C %s diff -- %s" % (SUB, f)).splitlines():
                if l.startswith("+++") or l.startswith("---"): continue
                if l.startswith("-") or (l.startswith("+") and not re.match(r"^\+\s*//", l) and l.strip() != "+"): ok = False; break
        if ok: kept.append(f)
        else: print("annotate_asm: reverting %s (not comment-only: +%s -%s)" % (f, add, rem)); sh("git -C %s checkout -- %s" % (SUB, f))
    return bool(kept)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", type=int, default=24); ap.add_argument("--model"); ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--post", action="store_true")
    a = ap.parse_args()
    def incident(kind, msg):
        subprocess.run(["bash", os.path.join(os.path.dirname(os.path.abspath(__file__)), "incident.sh"), kind, msg])
    if sh("git -C %s status --porcelain" % SUB).strip():
        incident("asm-refused", "submodule has uncommitted changes")
        sys.exit("annotate_asm: the submodule has uncommitted changes; refusing")
    # A submodule checkout is detached by default. Committing there and then pushing `fork bn-notes`
    # pushes the STALE local branch and silently succeeds, leaving the new commit reachable only by the
    # superproject pointer -- unpushed, one `git gc` from gone. That happened on 2026-09-17 (92705e0d).
    if sh("git -C %s rev-parse --abbrev-ref HEAD" % SUB).strip() != "bn-notes":
        incident("asm-refused", "submodule not on bn-notes (detached?) -- notes would be orphaned")
        sys.exit("annotate_asm: the submodule is not on bn-notes (detached or another branch); refusing -- "
                 "run: git -C %s checkout bn-notes" % SUB)
    found = results(a.since)
    if not found: print("annotate_asm: no ticket result with an assembly citation in the last %dh" % a.since); return
    model = pick_model(a.model)
    if not model: print("annotate_asm: no model with budget for a one-shot session"); return
    today = datetime.date.today().isoformat()
    brief = "\n\n".join("TICKET %s (%s). Result: %s\nCited: %s" % (t, st, res, ", ".join("%s:%d" % c for c in cites)) for t, st, res, cites in found)
    prompt = ("You add comment-only notes to a GBA disassembly at reference/bn6f (files reference/bn6f/asm/*.s and reference/bn6f/data/*.s), "
              "recording what a reimplementation project found, in the style of the existing `// bn ...` notes (grep one: `grep -rn '// bn' "
              "reference/bn6f/asm | head`). For each ticket below, open each cited file at the cited line, read enough context to name the "
              "routine, and insert, directly above the cited line (or above the first line of a cited range), a comment block of 2 to 6 lines "
              "beginning `// bn %s (%s):` that says in plain words what was found there and which file in this repo's src/ now carries it. "
              "Rules: insert comment lines only, using the edit tool; never change, move or delete any existing line; never touch a file that "
              "is not cited; one note per cited site; no ticket bookkeeping talk (no 'landed', 'verifier', 'branch'); cite by symbol and line. "
              "When done, reply with one line per note: file:line and the ticket. \n\n%s" % ("<TICKET>", today, brief))
    if a.dry_run: print("would annotate:\n" + "\n".join("  %s %s -> %s" % (t, st, ", ".join("%s:%d" % c for c in cites)) for t, st, _, cites in found)); print("model:", model); return
    p = subprocess.run(["pi", "-p", "--approve", "--no-session", "--mode", "json", "--model", model, "--thinking", "medium",
                        "--tools", "read,grep,find,ls,edit", prompt], capture_output=True, text=True, timeout=1800, stdin=subprocess.DEVNULL)
    if not comment_only_diff():
        print("annotate_asm: nothing comment-only to keep"); sh("git -C %s checkout -- ." % SUB); return
    print(sh("git -C %s diff --stat" % SUB))
    if not a.post: return
    ids = ", ".join(t for t, _, _, _ in found)
    msg = "Notes for %s: what the reimplementation found at the cited sites (comment-only, %s)\n\nCo-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" % (ids, today)
    print(sh("cd %s && git add -A asm data && git commit -q -m %s && git push -q fork bn-notes && git rev-parse --short HEAD" % (SUB, json.dumps(msg))))
    print(sh("exec 9>/tmp/bn-land.lock; flock -w 600 9 && git add %s && git commit -q -m %s && git push -q origin main && echo 'superproject pointer updated'"
             % (SUB, json.dumps("reference/bn6f: notes for %s (tools/annotate_asm.py)\n\nCo-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>" % ids))))


if __name__ == "__main__":
    main()
