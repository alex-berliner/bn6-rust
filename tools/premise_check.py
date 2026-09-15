#!/usr/bin/env python3
"""Re-measure the rows an OPEN ticket's **Why.** cites, for free, before a worker spends credits on a premise that
has drifted (F39a, F41 and F21e closed as "premise wrong" on 2026-09-15). A citation looks like
`warp integrated 40628/11744/30`, `opening 72499/2691/40`, `cursor 1/1/170` or `result isolated 0/0/40`; the row is
re-run with the harness, and when its total differs from the cited one a **Premise check.** line is added to the
ticket saying what the row reads now. Runs in the 09:15 roundup. Costs no credits: the harness is local.
  python3 tools/premise_check.py [--dry-run] [--commit]
"""
import datetime, os, re, subprocess, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..")); os.chdir(ROOT)
LINE = re.compile(r"^(?P<row>\S+)\s+(?P<ui>isolated|integrated)\s+(?P<status>\S+).*?total (?P<total>\d+)\s+worst (?P<worst>\d+)\s+frames (?P<frames>\d+)", re.M)


def rows():
    out = {}
    for line in subprocess.run(["python3", "tools/harness.py", "--list"], capture_output=True, text=True).stdout.splitlines():
        m = re.match(r"^(\S+)\s+ui=(\S+)", line)
        if m: out[m.group(1)] = m.group(2)
    return out


def measure(row, ui):
    p = subprocess.run(["python3", "tools/harness.py", "--only", row, "--ui", ui, "--no-gallery"], capture_output=True, text=True)
    for m in LINE.finditer(p.stdout + p.stderr):
        if m.group("row") == row and m.group("ui") == ui: return int(m.group("total")), int(m.group("worst")), int(m.group("frames"))
    return None


def main():
    dry = "--dry-run" in sys.argv; commit = "--commit" in sys.argv
    known = rows(); todo = open("TODO.md").read(); today = datetime.date.today().isoformat(); sha = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    cite = re.compile(r"\b(?P<row>[a-z][a-z0-9-]*)(?:\s+(?P<ui>isolated|integrated))?\s+(?P<t>\d+)/(?P<w>\d+)/(?P<f>\d+)\b")
    changed = []; cache = {}
    for m in re.finditer(r"^### (?P<id>[A-Z]+\d+[a-z]?)\. .*?\*\(OPEN\b.*?\n(?P<body>.*?)(?=^### |\n## |\Z)", todo, re.M | re.S):
        tid, body = m.group("id"), m.group("body")
        why = re.search(r"\*\*Why\.\*\*(.*?)(?=\n\*\*|\Z)", body, re.S); why = why.group(1) if why else ""
        if "**Premise check" in body: continue
        notes = []
        for c in cite.finditer(why):
            row = c.group("row")
            if row not in known: continue
            ui = c.group("ui") or ("integrated" if known[row] == "integrated" else "isolated")
            if (row, ui) not in cache: cache[(row, ui)] = measure(row, ui)
            now = cache[(row, ui)]
            if now and now[0] != int(c.group("t")): notes.append("%s %s now reads %d/%d/%d on main %s; the ticket cites %s/%s/%s" % (row, ui, now[0], now[1], now[2], sha, c.group("t"), c.group("w"), c.group("f")))
        if notes:
            changed.append((tid, notes)); print("%s: %s" % (tid, "; ".join(notes)))
            if not dry:
                add = "\n\n**Premise check (%s).** %s. Re-check the premise before working the ticket." % (today, "; ".join(notes))
                todo = todo.replace(m.group(0), m.group(0).rstrip("\n") + add + "\n", 1)
    if not changed: print("premise_check: every cited number still holds (%d tickets checked)" % len(re.findall(r"^### [A-Z]+\d+[a-z]?\. .*?\*\(OPEN\b", todo, re.M))); return
    if dry: return
    open("TODO.md", "w").write(todo)
    if commit:
        subprocess.run("exec 9>/tmp/bn-land.lock; flock -w 600 9 && git add TODO.md && git commit -q -m 'TODO: premise checks -- %s (tools/premise_check.py)\n\nCo-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>' && git push -q origin main" % ", ".join(t for t, _ in changed), shell=True)


if __name__ == "__main__":
    main()
