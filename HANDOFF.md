# HANDOFF — start here (2026-09-13)

Short on purpose: it is what a fresh session reads before doing anything, and every token of it is
re-sent on every turn of that session. The long version with the history, the incidents, the gotchas
and the numbered sections that tickets and code comments cite as "HANDOFF §N" is
`docs/HANDOFF_2026-09-12.md`. Agents read `AGENT_GUIDE.md` and `AGENTS.md`, not this file.

## 0. What this is

A Rust reimplementation of Mega Man Battle Network 6 Falzar's battle system as a real GBA ROM
(ARM7TDMI, `no_std`, thumbv4t, agb vendored at `vendor/agb`). The standard is per-pixel parity with the
original ROM ("canon"): full 240x160, every compared frame, zero differing pixels, measured by
`tools/harness.py` from headless mGBA captures of both ROMs. A non-zero is a defect with a frame and
region, never a tolerance. No boxes in space or time; no subtracted baselines; every check carries a
negative fixture that must fail; a reported 0 always says what it compares (canon vs ours, or before
vs after -- a merge that changed nothing is not parity).

## 1. Where things stand

- **At 0 differing frames (canon vs ours):** wave, window, opening, cannon, field, banner, warp, card,
  tiles, gauge and 28 of the 43 chip rows -- 38 rows. `python3 tools/harness.py --list` names every
  row; `web/captures/` holds each row's GIF and caption, plus a before/after GIF per landed ticket
  (the gallery page), made at the end of every coordinator run.
- **Open queue (`python3 tools/next_ticket.py --list`):** F18d windowclose (650544), F21d result
  (block-copy the window's tilemap; F21b's slide rework, 190633, waits on it on its kept branch),
  F12 seed feet (247/132/132), F25 Mettaur attack phase (mettaur 19698; tiles/gauge integrated 3865;
  popup's HUD bar), F24 per-scanline backdrop scroll port (cursor 620802; result's backdrop tail),
  F23 naming (battle.rs next). BLOCKED after two misses: F10/F10b buster. Closed tickets:
  `TODO_ARCHIVE.md`. From run 4 the coordinator runs two workers on tickets with disjoint
  `**Files.**` lines (`next_ticket.py --pair`).
- **Order (the user, 2026-09-12):** every existing row to 0 before any new content. Scope after that:
  5 viruses, 2 bosses, player fidelity, the custom screen, battle flow. No Navis, Navi Customizer,
  Program Advances, audio, netbattle.
- **After convergence (agreed 2026-09-13):** switch from behaviour-driven porting to trace- and
  coverage-driven porting before any new content. In order: (1) widen the state oracle into a
  state-trace harness -- record canon's structs per frame over scripted scenarios from power-on and
  diff ours against them, first divergence named automatically, pixels as the gate on the same
  recordings; (2) use the bn6f fork's profiler (master branch: function map + libmgba coverage) to
  list the functions canon executes per scenario; (3) port canon's interpreters first -- the
  animation bytecode player (replacing our own), the object dispatcher, the script VMs -- so chips,
  viruses and maps become data; (4) then port remaining functions in coverage order, cited line by
  line, each verified by the trace. The 5 viruses / 2 bosses come from data after (3), and are its
  first test. Existing rows stay as free regression tests.
- **Continuous improvement protocol (agreed 2026-09-13, to build after the Claude-agent batch lands):**
  a daily review script (machine cron) that joins ticket outcome to role/model/cost and reports cost
  per landed verified ticket, rows at 0, NEGATIVE/BLOCKED rate, no-pair rate and Claude tokens per
  landed ticket into docs/reviews/; a replay benchmark (re-run archived tickets with known answers
  from their base commit) that gates any model switch; and an event-triggered auditor that reads a
  digest and PROPOSES reshapes of roles, loop, AGENTS.md and tools into docs/audits/ with a
  docs/config-log.md changelog, one structural change per cycle, never touching the invariants
  (canon never changes, verify_rows always, no fitted constants, the spend floor).
- **Money:** `python3 tools/or_spend.py` prints the real OpenRouter balance (the lower of the key's
  limit and the account's credit). The user keeps $5 in the account; runs stop at that floor.
  `python3 tools/spend_ledger.py` shows spend per role and model.
- **Public:** repo https://github.com/alex-berliner/bn6-rust (main pushed after merges by the
  coordinator; agents never push); site https://alex-berliner.github.io/bn6-rust/ from the generated
  `gh-pages` branch (`bash tools/publish_site.sh`, refuses any ROM that is not ours); the disassembly
  fork https://github.com/alex-berliner/bn6f branch `bn-notes` (the submodule points there).

## 2. Run a session

1. `bash tools/restore_inputs.sh` if `/tmp/bn6f_real.gba` is missing (the machine wipes /tmp).
2. `python3 tools/or_spend.py --min 5` and `python3 tools/next_ticket.py --list`.
3. Launch the coordinator, detached, with a cap on this run's total spend:
   `BN_PI_CAP=<dollars> bash tools/pi_coordinator.sh "Run the loop. Spend floor 5."`
   It takes the first OPEN ticket, dispatches the worker, verifies (free row check, then the verifier
   only for claims beyond harness lines), lands with `tools/land.sh`, records with
   `tools/ticket_result.py`, and loops; a ticket that misses twice is marked BLOCKED and skipped.
4. Watch it only with `bash tools/pi_watch.sh <run dir>` (ticket-level events) -- do not mirror the
   run turn by turn from a Claude Code session; that session exists for judgment and then closes.
5. When it stops: spot-check a zero yourself (`python3 tools/verify_rows.py HEAD <rows> --expect ...`),
   `python3 tools/archive_tickets.py`, `git push origin main`, `bash tools/publish_site.sh`.

- **Daily review, auditor, replay benchmark (built 2026-09-13):** a user crontab line runs
  `bash tools/daily_review.sh` at 09:15 (ledger, balance, full-table scoreboard, hygiene counts,
  auditor triggers) into `docs/reviews/<date>.md`; `python3 tools/ticket_ledger.py --since H` is the
  outcome x model x cost table; `bash tools/pi_audit.sh` writes a proposal-only audit to
  `docs/audits/`; `python3 tools/replay_bench.py <ID> --model <m>` re-runs an archived ticket from
  its base commit and judges it with verify_rows (`docs/benchmarks/`); every applied reshape goes
  in `docs/config-log.md` with its evidence and the metric it moved.

## 3. Decisions in force

- **Roles and models** (`.pi/agents/*.md`, `.pi/settings.json`, pins in `~/.pi/agent/models.json`):
  worker `z-ai/glm-5.3-flash` high, pinned to Z.AI; recon `deepseek/deepseek-v4.1-flash` medium, pinned
  to DeepSeek (its output is a map, never a finding); verifier and coordinator
  `meta/muse-spark-1.3-contributor` high (the same model as Muse Spark 1.3 at ~1/16 the price; the
  user accepts its data-use terms); escalation `openai/gpt-5.6-sol`, only when an implementation fell
  short, never for a disproven prediction; no model overrides in dispatches; Opus 5 last resort.
  Measured: a GLM ticket costs $0.01-0.37; a verifier pass ~$0.02-0.03 on the contributor tier
  (was $0.37 Muse, $1.02-1.38 Sol).
- **Worker A/B decided (2026-09-13, seven tickets):** Muse contributor workers on F17/F19/F21 cost
  $0.039/$0.035/$0.110 (all landed, verified); GLM workers on F12/F18/F20/F22 cost $0.098/$0.231/
  $0.045/$0.044 (one landed, three precise negatives/localizations). Same quality of report and
  verdicts, Muse about 40% cheaper per ticket at a lower per-turn price. Worker = Muse contributor,
  verifier = GLM-5.3-Flash (cross-family), coordinator = Muse contributor. The A/B roles
  (worker-muse, verifier-glm) are deleted.
- **Superseded note:** Muse Spark 1.3 contributor scores ~48 on the user's chart to
  GLM's 42 and is cheaper on every line ($0.10/$0.20, cache $0.002/M): the coordinator alternates
  `worker-muse` and `worker` on F12's families (verifier `verifier-glm` when the worker was Muse, so
  the checker is a different family) and records model, turns and cost per ticket. Decide from two
  tickets each: if Muse matches or beats GLM on outcome and cost, worker = Muse contributor and
  verifier = GLM for good. Judgment work off the Claude plan: `bash tools/pi_judge.sh` proposes the
  next three tickets to docs/proposals/ for about a cent. `tools/probe.py` (watch/peek/frame/diff in
  one call) replaces the throwaway scripts workers wrote.
- **Verification is two-tier:** `tools/verify_rows.py` reproduces every claimed harness line from a
  clean detached checkout, always, free; the verifier role checks the two or three claims the next
  ticket would build on (memory findings, causes, exclusions, partial/negative outcomes), with a hard
  tool budget. Nothing merges without the free tier passing.
- **Convergence rules:** alignment by measured event, never by the lower score; never widen
  `tools/allowlist.py`; canon never changes, and canon (sterile) only when a ticket explicitly
  authorizes one patch (`tools/patch_sterile.py`, documented); no src/ change outside a ticket that
  allows it; captures one at a time; a row that gets worse is reported, not hidden.
- **Fixtures:** every state is a recipe (`tools/states.py build all` rebuilds everything from the ROM
  and the battery save except `noenemy2`, which is lost); the chip rows compare against
  `afterdissolve_0x0c` with a one-shot AIData poke (F5b) -- the enemy-less battle route (R3-R5) is
  closed. The state oracle (`tools/oracle.py wave|mettaur`) names the first divergent field and frame.
- **pi:** built from source at `/home/box/Code/pi` (branch `local/build-fixes`, `npm link`ed);
  project resources load after `/trust`; `< /dev/null` on every headless run; `~/.pi/agent/models.json`
  turns Opus 5's mid-conversation-effort beta off and caps Opus 5/Sonnet 5 output at 32k; the context
  pruner is on in `agentic-auto` mode. Extensions: `pi-context-prune`, `pi-subagents`, `pi-goal-x`
  (project-local).
- **Two workers in flight (2026-09-13, the user's call at <=5% overhead):** tickets declare a
  `**Files.**` line; `next_ticket.py --pair` returns the first OPEN ticket plus the next OPEN one whose
  files are disjoint; the coordinator runs two workers asynchronously, verifies and lands one at a
  time, and re-runs the free row check on main after a merge when another ticket landed meanwhile
  (revert on mismatch). Measured overhead is that extra free check plus a few hundred tokens of
  coordinator context; the old sequential rule cost half the wall-clock. Every ticket without a
  `**Files.**` line runs alone.
- **Wall time (2026-09-13):** captures are parallel inside a row (rust and canon sides, and the isolated and
  integrated variants together) under a machine-wide 3-slot semaphore in `chip_compare.capture`, so the old
  "never two captures at once" rule is enforced by code instead of by agents; `harness.py --ui isolated`
  runs one variant; `verify_rows.py`/`progress_gif.py` keep persistent target dirs (warm builds); `land.sh`
  reuses a verify_rows PASS on the same commit from the last 30 minutes instead of re-running it.
- **Build profile:** release is fat LTO with debug info, from agb's template; every harness number
  rests on it -- do not flip either setting without rerunning the table.

## 4. Inputs and backups

Never tracked: the real ROM, the battery save, save states. Working copies live in `/tmp`; backups in
`/home/box/bn-backup` and `/media/box/Scyther/bn-backup`, together with a git bundle of the submodule's
`bn-notes` branch (`git -C reference/bn6f bundle create /home/box/bn-backup/bn6f-bn-notes.bundle
bn-notes`; also pushed to the fork). Refresh both when a root state or `bn-notes` changes.

## 5. Map of the documents

`AGENTS.md` rules every agent loads · `AGENT_GUIDE.md` how agents build, measure, align ·
`TODO.md` open tickets, `TODO_ARCHIVE.md` closed ones · `docs/HANDOFF_2026-09-12.md` the long handoff
(§1 inputs, §3 harness, §4 descriptor/marker, §5 capture flags, §6 states, §9 gotchas, §13 the full
decision log) · `AUDIT.md` the 17 rules · `FIXTURE.md` the descriptor contract · `MODEL_RESEARCH.md`
and `WORKFLOW_AUDIT.md` why the routing and workflow are what they are · `docs_recon_teardown.md` the
enemy-less battle investigation · `TRANSFER.md` the long journal (human reading) · `.pi/coordinator.md`
the coordinator's loop · `~/.claude/projects/-home-box-Code-bn/memory/` the user's standing rules.
