#!/usr/bin/env python3
"""Apply the disassembly's symbol renames (reference/bn6f/docs/renames.md, `old -> new` lines) to this repo's own
citations: comments in src/, the docs, the tools' notes, TODO.md and TODO_ARCHIVE.md. Whole-word replacement only,
never inside reference/ or web/. Meant to run once after a rename pass and only when no pi run is active (a
worker's branch would otherwise conflict on comment lines): tools/daily_review.sh calls it with --if-idle.
  python3 tools/apply_renames.py [--dry-run] [--if-idle] [--commit]
"""
import os, re, subprocess, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..")); os.chdir(ROOT)
MAP = "reference/bn6f/docs/renames.md"
SKIP = ("reference/", "web/", "target/", ".git/", "vendor/", "docs/benchmarks/", "docs/proposals/")


def pairs():
    out = []
    for line in open(MAP):
        m = (re.match(r"^\|\s*`?([A-Za-z_][A-Za-z0-9_.]*)`?\s*\|\s*`?([A-Za-z_][A-Za-z0-9_.]*)`?\s*\|", line)      # a table row: | old | new | evidence |
             or re.search(r"`?([A-Za-z_][A-Za-z0-9_.]*)`?\s*->\s*`?([A-Za-z_][A-Za-z0-9_.]*)`?", line))               # or `old -> new`
        if m and m.group(1) != m.group(2) and m.group(1) not in ("old", "Old") and re.search(r"[0-9A-Fa-f]{5,}", m.group(1)):
            out.append((m.group(1), m.group(2)))
    return list(dict.fromkeys(out))


def main():
    dry = "--dry-run" in sys.argv
    if "--if-idle" in sys.argv and subprocess.run("pgrep -f 'pi -p --approve --session-dir /tmp/bn-pi' >/dev/null", shell=True).returncode == 0:
        print("apply_renames: a pi run is active; not now"); return
    ps = pairs()
    if not ps: print("apply_renames: no renames found in", MAP); return
    pat = re.compile(r"(?<![A-Za-z0-9_])(" + "|".join(re.escape(o) for o, _ in sorted(ps, key=lambda p: -len(p[0]))) + r")(?![A-Za-z0-9_])")
    repl = dict(ps); changed = {}
    for dp, dn, fn in os.walk(ROOT):
        rel = os.path.relpath(dp, ROOT) + "/"
        dn[:] = [d for d in dn if not (rel + d + "/").lstrip("./").startswith(SKIP) and d not in (".git", "target", "vendor")]
        for f in fn:
            p = os.path.join(dp, f); r = os.path.relpath(p, ROOT)
            if r.startswith(SKIP) or not f.endswith((".rs", ".md", ".py", ".sh", ".toml", ".txt", ".c", ".h")): continue
            try: s = open(p).read()
            except (UnicodeDecodeError, OSError): continue
            n, s2 = 0, pat.sub(lambda m: (repl[m.group(1)], None)[0], s)
            n = len(pat.findall(s))
            if n and s2 != s:
                changed[r] = n
                if not dry: open(p, "w").write(s2)
    print("apply_renames: %d renames; %d files, %d citations%s" % (len(ps), len(changed), sum(changed.values()), " (dry run)" if dry else ""))
    for r, n in sorted(changed.items(), key=lambda x: -x[1])[:12]: print("  %5d  %s" % (n, r))
    if changed and not dry and "--commit" in sys.argv:
        subprocess.run("exec 9>/tmp/bn-land.lock; flock -w 600 9 && git add -u && git commit -q -m 'citations: the disassembly'\"'\"'s renamed symbols applied to this repo (tools/apply_renames.py from reference/bn6f/docs/renames.md)\n\nCo-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>' && git push -q origin main && echo committed", shell=True)


if __name__ == "__main__":
    main()
