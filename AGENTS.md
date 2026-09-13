# AGENTS.md — rules every pi session and subagent in this repo runs under

Keep this file short and stable: it is loaded into every child's context.

- Read `AGENT_GUIDE.md` for how to build, measure and align. A ticket that cites "HANDOFF §N" means
  that section of `docs/HANDOFF_2026-09-12.md`; read only that section. Never `TRANSFER.md` (a journal). Never read TODO.md, HANDOFF.md or tools/harness.py
  whole -- your ticket text is in your task, and grep does the rest.
- The standard is per-pixel parity with the real ROM: zero differing pixels over the full
  screen for every compared frame. A non-zero is a defect with a frame and region, never a
  tolerance. No boxes, no subtracted baselines, no "inherent" residues.
- The harness (`python3 tools/harness.py --only <row>`) is the only pass/fail. A check whose
  negative fixture also reads 0 is BLIND and proves nothing.
- Tickets state what to measure. Baseline first, then the change, then the same script again;
  report both numbers with the frame window. A precise negative result is a good outcome.
- Report in this shape, nothing more: row · frames · total · worst · region · commit · one line
  of mechanism · one line of what is unverified.
- Work only in your own worktree from `tools/worktree.sh <name>`; edit only the files the
  ticket names; stage by path (`git add -u <path>`); never `git add -A`; never push (the coordinator pushes).
- `reference/bn6f` is read-only for agents. Copyrighted inputs (ROMs, save states, saves) are never
  tracked; never `git add -f` anything gitignored.
- Captures are bounded by a machine-wide semaphore (3 slots, `BN_CAPTURE_SLOTS`), so a row's captures
  overlap and two processes cannot overload the box; still run one harness command at a time yourself.
- Do the work yourself. A ticket that is bigger than it looked comes back as a report, not as
  a subcontract.
