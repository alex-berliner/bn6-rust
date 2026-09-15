#!/usr/bin/env python3
"""Spend the day's last credits on checking our own notes: for a few `// bn ...` notes in the disassembly, one
tiny model request each (the note plus the surrounding code, no tools) asks whether the note still holds.
Verdicts go to docs/note_audits.md (YES / NO / UNSURE with one sentence); a NO is something for the next
judge or human to look at. Meant for the band under the run's stop threshold (3 credits) and above 1, where
nothing larger can start: tools/run_day.sh calls it there; --force runs it at any balance.
  python3 tools/note_audit.py [--max 3] [--force] [--dry-run]
"""
import argparse, datetime, glob, json, os, re, subprocess, sys, tomllib

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..")); os.chdir(ROOT)
SUB = "reference/bn6f"; LOG = "docs/note_audits.md"


def notes():
    """(file, line, text) for every `// bn` note block in the disassembly, in file order"""
    out = []
    for f in sorted(glob.glob(SUB + "/asm/*.s") + glob.glob(SUB + "/data/*.s")):
        lines = open(f, errors="replace").read().splitlines(); i = 0
        while i < len(lines):
            if re.match(r"^\s*//\s*bn\b", lines[i]):
                j = i; block = []
                while j < len(lines) and re.match(r"^\s*//", lines[j]): block.append(lines[j].strip()); j += 1
                out.append((f, i + 1, "\n".join(block), lines[max(0, i - 40):min(len(lines), j + 40)])); i = j
            else: i += 1
    return out


def audited():
    s = open(LOG).read() if os.path.exists(LOG) else ""
    return set(re.findall(r"^\| \S+ \| (\S+:\d+) \|", s, re.M))


def model():
    cfg = tomllib.load(open("providers.toml", "rb")); run = cfg["schedule"]["runs"][0]
    return cfg["runs"][run]["recon"][0]


def ask(m, note, ctx):
    prompt = ("A note left in a GBA disassembly by a reimplementation project, and the assembly around it. Read the code and say whether the "
              "note's claims about THIS code still hold. Reply with exactly one line: YES, NO or UNSURE, a colon, and one sentence saying why "
              "(for NO: what the code shows instead).\n\nNOTE:\n%s\n\nCODE (the note sits in the middle):\n%s" % (note, "\n".join(ctx)))
    p = subprocess.run(["pi", "-p", "--approve", "--no-session", "--mode", "json", "--model", m, "--thinking", "low", "--tools", "", prompt],
                       capture_output=True, text=True, timeout=300, stdin=subprocess.DEVNULL)
    last, cost = "", 0.0
    for line in p.stdout.splitlines():
        try: e = json.loads(line)
        except ValueError: continue
        if e.get("type") != "turn_end": continue
        msg = e.get("message") or {}
        if msg.get("role") == "assistant":
            cost += ((msg.get("usage") or {}).get("cost") or {}).get("total", 0) or 0
            t = " ".join(c.get("text", "") for c in msg.get("content", []) if c.get("type") == "text").strip()
            if t: last = t
    m2 = re.match(r"\s*(YES|NO|UNSURE)\s*[:.-]?\s*(.*)", last, re.S | re.I)
    return (m2.group(1).upper(), re.sub(r"\s+", " ", m2.group(2)).strip()[:300]) if m2 else ("UNSURE", ("no parseable reply: " + last[:120]) if last else "empty reply"), cost


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max", type=int, default=3); ap.add_argument("--force", action="store_true"); ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if not a.force:
        r = subprocess.run("python3 tools/hyper_credits.py", shell=True, capture_output=True, text=True).stdout
        m = re.search(r"remaining ([0-9.]+)", r); bal = float(m.group(1)) if m else None
        if bal is None or not (1.0 <= bal < 3.0): print("note_audit: balance %s is not in the 1..3 band; nothing to do" % bal); return
    done = audited(); todo = [n for n in notes() if "%s:%d" % (n[0].replace(SUB + "/", ""), n[1]) not in done]
    print("note_audit: %d notes, %d not yet audited" % (len(todo) + len(done), len(todo)))
    if a.dry_run or not todo: return
    mdl = model(); today = datetime.date.today().isoformat(); rows = []
    for f, line, text, ctx in todo[:a.max]:
        site = "%s:%d" % (f.replace(SUB + "/", ""), line)
        (verdict, why), cost = ask(mdl, text, ctx); rows.append((today, site, verdict, why, cost)); print("  %s %s: %s ($%.4f)" % (verdict, site, why[:100], cost))
        if not a.force:
            r = subprocess.run("python3 tools/hyper_credits.py --min 1", shell=True, capture_output=True); 
            if r.returncode == 1: print("note_audit: balance under 1; stopping"); break
    if not os.path.exists(LOG):
        open(LOG, "w").write("# Note audits\n\nEach row: a `// bn` note in reference/bn6f re-read against its code by a cheap model with the day's last credits (tools/note_audit.py). NO means the note may be wrong: the judge and the humans read this file.\n\n| date | site | verdict | why | nominal $ |\n|---|---|---|---|---|\n")
    with open(LOG, "a") as fh:
        for d, site, v, why, c in rows: fh.write("| %s | %s | %s | %s | %.4f |\n" % (d, site, v, why.replace("|", "/"), c))
    subprocess.run("exec 9>/tmp/bn-land.lock; flock -w 600 9 && git add %s && git commit -q -m 'note audits: %d notes checked (%s)\n\nCo-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>' && git push -q origin main" % (LOG, len(rows), ", ".join(v for _, _, v, _, _ in rows)), shell=True)


if __name__ == "__main__":
    main()
