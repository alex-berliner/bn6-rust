# AGENTS.md — rules every pi session and subagent in this repo runs under

Keep this file short and stable: it is loaded into every child's context.

- Read `AGENT_GUIDE.md` for how to build, measure and align. A ticket that cites "HANDOFF §N" means
  that section of `docs/HANDOFF_2026-09-12.md`; read only that section. A comment or a doc that cites a fact's provenance points at `docs/provenance.md#<id>` (e.g. `#7aw` for the save-state-at-first-frame fact, `#7ao` for the read-arcs-out-of-the-object fact); read only that section. The historical journal `TRANSFER.md` stays in place but its load-bearing facts are now in `docs/provenance.md`. Never read TODO.md, HANDOFF.md or tools/harness.py
  whole -- your ticket text is in your task, and grep does the rest.
- Parity means the original's behaviour reproduced exactly, measured on three surfaces, each with a zero:
  pixels over every compared frame of the full screen, the state trace field by field, and audio sample for
  sample. A non-zero on any of them is a defect with a frame and a place, never a tolerance: no boxes, no
  subtracted baselines, no "inherent" residues. A landing may not make any surface worse.
- The harness (`python3 tools/harness.py --only <row>`) is the veto: no landing may make a row worse, and a
  check whose negative fixture also reads 0 is BLIND and proves nothing. For engine-core work the state
  trace (`tools/trace.py`: which field, how many of the scene's frames, the first divergent frame) is the
  progress number, so a ticket that moves the trace with every row unchanged is progress, not a no-op.
- Tickets state what to measure. Baseline first, then the change, then the same script again;
  report both numbers with the frame window. A precise negative result is a good outcome.
- Report in this shape, nothing more: row · frames · total · worst · region · commit · one line
  of mechanism · one line of what is unverified.
- Work only in your own worktree from `tools/worktree.sh <name>`; edit only the files the ticket names;
  stage by path (`git add -u <path>`); never `git add -A`; never push (the coordinator pushes). Never commit
  on main: work happens on your worktree branch, and only `tools/land.sh` merges it, after `verify_rows`
  reproduces your numbers from a clean checkout. `--no-verify` is refused for any branch that changes code.
- `reference/bn6f` is the project's own disassembly and it does get improved (names, struct fields), but never
  by you inside a ticket: its gate is a full rebuild to the ROM's sha1, which is not part of your loop. Read it,
  cite it, and put what you learned in your report or work log; a tooling pass propagates it. Copyrighted inputs (ROMs, save states, saves) are never
  tracked; never `git add -f` anything gitignored.
- Captures are bounded by a machine-wide semaphore (3 slots, `BN_CAPTURE_SLOTS`), so a row's captures
  overlap and two processes cannot overload the box; still run one harness command at a time yourself.
- Name the numbers you touch. A bare literal in a line you edit or cite gets a name: a `const` with a
  `// provenance:` tag when its meaning is known, or the canon symbol in a comment (`// canon:
  oBattleObject_HP`) for an address or offset. Spend at most a couple of commands finding the meaning;
  if it stays unknown, tag it `// unnamed: <what it appears to be>` so a later pass can find it. Never
  rename or move a value you did not need to understand for the ticket.
- Keep `docs/worklog/<ID>.md` as you go and commit it with your work: what you measured and the numbers,
  every idea you tried and why you dropped it, what you would try next. It reaches main even when your
  branch does not, and the next worker on the objective starts by reading it.
- Do the work yourself. A ticket that is bigger than it looked comes back as a report, not as
  a subcontract.
