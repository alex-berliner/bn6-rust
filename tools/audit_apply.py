#!/usr/bin/env python3
"""Apply the auditor's low-risk proposals without a human.

usage: python3 tools/audit_apply.py [audit.md] [--dry-run]

The auditor (tools/pi_audit.sh) proposes reshapes of the agent setup as unified diffs. Until now every
one of them waited for a human session, which meant most waited forever: two audits have ever been
written and neither was applied the same day. This applies the subset that cannot break anything, and
leaves the rest as a proposal.

"Low risk" is defined narrowly and mechanically, not by judgement:

  1. The diff touches ONLY instruction text -- .pi/coordinator.md, .pi/roles/*.md, AGENTS.md,
     AGENT_GUIDE.md. These are prompts. A bad prompt makes an agent work badly for one cycle and the
     next review shows it. Anything under tools/, src/, providers.toml, the harness or the ticket
     files is refused: those can silently corrupt measurements or spend money, and a measurement
     nobody can trust is worse than no change at all.
  2. It does not delete an invariant. A removed line naming verify_rows, canon, the spend floor or
     fitted constants refuses the whole item, whatever else it does.
  3. It is small: at most MAX_LINES changed lines, so a review can read it in the log.
  4. It applies cleanly (`git apply --check`). No fuzz, no manual resolution.
  5. At most ONE item is applied per cycle, keeping the existing "one structural change per cycle"
     rule that the config log is built around.

Everything applied is committed and appended to docs/config-log.md with the audit it came from, so the
next review can attribute a metric change to it. Everything refused is recorded as an incident, which
is what gets it in front of a human.
"""
import os, re, subprocess, sys, datetime

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ALLOWED = (".pi/coordinator.md", "AGENTS.md", "AGENT_GUIDE.md")
# .pi/roles/*.md is the SOURCE; .pi/agents/*.md is generated from it by tools/roles.py render and is
# overwritten on the next render. The first version of this allowed the generated files and refused the
# source, so the auditor's first real proposal against the worker role was refused (2026-09-18).
ALLOWED_GLOB = re.compile(r"^\.pi/roles/[A-Za-z0-9_.-]+\.md$")
# A removed line mentioning any of these is a removed invariant: refuse the item outright.
INVARIANT = re.compile(r"verify_rows|canon never changes|spend floor|fitted constant|check_inputs", re.I)
MAX_LINES = 60


def incident(kind, msg):
    subprocess.run(["bash", os.path.join(ROOT, "tools", "incident.sh"), kind, msg])


def blocks(text):
    """Every fenced diff block, in order."""
    return re.findall(r"```(?:diff|patch)\n(.*?)```", text, re.S)


def files_of(diff):
    """Paths the diff claims to touch, from its +++ headers."""
    out = []
    for m in re.finditer(r"^\+\+\+ (?:b/)?(\S+)", diff, re.M):
        out.append(m.group(1))
    return out


def judge(diff):
    """(ok, reason). Mechanical, in the order a refusal is cheapest to explain."""
    fs = files_of(diff)
    if not fs:
        return False, "no +++ header: not a well-formed unified diff, cannot be applied unattended"
    for f in fs:
        if f not in ALLOWED and not ALLOWED_GLOB.match(f):
            return False, "touches %s, which is not instruction text" % f
    changed = [l for l in diff.splitlines() if (l.startswith("+") or l.startswith("-"))
               and not l.startswith(("+++", "---"))]
    if len(changed) > MAX_LINES:
        return False, "%d changed lines, over the %d-line cap for an unattended change" % (len(changed), MAX_LINES)
    for l in changed:
        if l.startswith("-") and INVARIANT.search(l):
            return False, "removes a line naming an invariant: %s" % l.strip()[:120]
    r = subprocess.run(["git", "-C", ROOT, "apply", "--check", "-"], input=diff, text=True, capture_output=True)
    if r.returncode != 0:
        return False, "does not apply cleanly: %s" % (r.stderr.strip().splitlines() or [""])[0][:160]
    return True, "%d changed lines in %s" % (len(changed), ", ".join(fs))


def title_before(text, diff):
    """The nearest '## <n>. <title>' heading above this diff, for the log line."""
    i = text.find(diff)
    heads = re.findall(r"^##+ (.+)$", text[:i], re.M)
    return heads[-1].strip() if heads else "(untitled item)"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry-run" in sys.argv
    audits = sorted([f for f in os.listdir(os.path.join(ROOT, "docs/audits")) if f.endswith(".md")]) \
        if os.path.isdir(os.path.join(ROOT, "docs/audits")) else []
    path = args[0] if args else (os.path.join(ROOT, "docs/audits", audits[-1]) if audits else None)
    if not path or not os.path.exists(path):
        print("audit_apply: no audit to read"); return 0
    text = open(path).read()
    items = blocks(text)
    if not items:
        print("audit_apply: %s has no diff blocks; nothing is mechanically applicable" % os.path.basename(path))
        incident("audit-unapplied", "%s: proposal has no unified diffs, needs a human" % os.path.basename(path))
        return 0

    applied = None
    for d in items:
        ok, why = judge(d)
        name = title_before(text, d)
        if not ok:
            print("SKIP  %s -- %s" % (name[:70], why))
            incident("audit-unapplied", "%s: %s -- %s" % (os.path.basename(path), name[:80], why))
            continue
        print("APPLY %s -- %s" % (name[:70], why))
        if dry:
            applied = (name, why); break
        r = subprocess.run(["git", "-C", ROOT, "apply", "-"], input=d, text=True, capture_output=True)
        if r.returncode != 0:
            incident("audit-unapplied", "%s: %s -- apply failed after check passed: %s"
                     % (os.path.basename(path), name[:80], r.stderr.strip()[:160]))
            continue
        applied = (name, why); break

    if not applied:
        print("audit_apply: nothing was applicable this cycle"); return 0
    if dry:
        print("audit_apply: --dry-run, not applying"); return 0

    name, why = applied
    today = datetime.date.today().isoformat()
    log = os.path.join(ROOT, "docs/config-log.md")
    row = "| %s | %s | auditor %s (applied automatically: %s) | see the audit item | pending the next review |\n" \
          % (today, name.replace("|", "/")[:120], os.path.basename(path), why.replace("|", "/")[:100])
    with open(log, "a") as fp:
        fp.write(row)
    subprocess.run(["git", "-C", ROOT, "add", "-u", "docs/config-log.md"] + files_of(blocks(text)[0]), check=False)
    subprocess.run(["git", "-C", ROOT, "add", "docs/config-log.md"], check=False)
    msg = ("config: apply the auditor's own proposal -- %s\n\n"
           "From %s, applied by tools/audit_apply.py without a human because it changes only\n"
           "instruction text (%s). Items touching tools, sources or the harness are never applied\n"
           "this way; they stay proposals and are recorded as incidents so they reach a person.\n\n"
           "Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>\n") % (name[:100], os.path.basename(path), why)
    subprocess.run(["git", "-C", ROOT, "commit", "-q", "-m", msg], check=False)
    # a change to a role source is only live once the agent files are regenerated from it
    subprocess.run(["python3", os.path.join(ROOT, "tools", "roles.py"), "render"], capture_output=True)
    subprocess.run(["git", "-C", ROOT, "add", ".pi/agents"], check=False)
    subprocess.run(["git", "-C", ROOT, "commit", "-q", "-m", "agents: re-rendered after an auditor change to a role source"], check=False)
    print("applied and committed: %s" % name[:100])
    return 0


if __name__ == "__main__":
    sys.exit(main())
