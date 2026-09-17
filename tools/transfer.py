#!/usr/bin/env python3
"""Print one section of TRANSFER.md, the first phase's journal. The tools cite it for the provenance of a
number ("TRANSFER 7aw", "TRANSFER.md section 3"); the file is 2,900 lines and nobody should read it whole,
so this resolves a citation to its own section and nothing else.

  python3 tools/transfer.py 7aw          one section by its id
  python3 tools/transfer.py "section 3"  or by its number
  python3 tools/transfer.py --list       every section id with its heading
  python3 tools/transfer.py --cited      the sections the code actually cites, and from where
"""
import glob, re, subprocess, sys, os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..")); os.chdir(ROOT)
DOC = "TRANSFER.md"


def sections():
    """(id, heading, first line, last line) for every heading in the journal"""
    lines = open(DOC, errors="replace").read().splitlines()
    heads = []
    for i, l in enumerate(lines):
        m = re.match(r"^#{1,4}\s+(?:(\d+[a-z]{0,2})[.)]?\s+)?(.*)$", l)
        if m and l.startswith("#"):
            sid = m.group(1) or re.sub(r"[^a-z0-9]+", "-", m.group(2).lower())[:40]
            heads.append((sid, m.group(2).strip(), i))
    out = []
    for k, (sid, title, i) in enumerate(heads):
        end = heads[k + 1][2] if k + 1 < len(heads) else len(lines)
        out.append((sid, title, i, end))
    return lines, out


def main():
    if not os.path.exists(DOC): sys.exit("%s is not here" % DOC)
    args = [a for a in sys.argv[1:]]
    lines, secs = sections()
    if not args or "--list" in args:
        for sid, title, i, end in secs: print("%-10s %4d-%-4d %s" % (sid, i + 1, end, title[:90]))
        return
    if "--cited" in args:
        hits = subprocess.run("grep -rn 'TRANSFER[ .]' tools/ src/ docs/*.md AGENTS.md AGENT_GUIDE.md 2>/dev/null", shell=True, capture_output=True, text=True).stdout
        cited = {}
        for line in hits.splitlines():
            for m in re.finditer(r"TRANSFER(?:\.md)?\s+(?:section\s+)?(\d+[a-z]{0,2})", line):
                cited.setdefault(m.group(1), []).append(line.split(":")[0])
        for sid in sorted(cited):
            title = next((t for s, t, _, _ in secs if s == sid), "(no such section)")
            print("%-8s %-60s cited by %s" % (sid, title[:60], ", ".join(sorted(set(cited[sid])))))
        return
    want = re.sub(r"^section\s+", "", " ".join(args).strip().lower())
    for sid, title, i, end in secs:
        if sid.lower() == want:
            print("\n".join(lines[i:end])); return
    near = [s for s, _, _, _ in secs if want in s.lower()]
    sys.exit("no section %r in %s%s" % (want, DOC, ("; did you mean %s?" % ", ".join(near[:5])) if near else "; --list shows them all"))


if __name__ == "__main__":
    main()
