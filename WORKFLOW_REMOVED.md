# What this branch removed, and what it kept

This branch is `main` with the agent workflow cut out, so a different orchestrator (LangChain) can be
built over the same project. Everything removed is one `git checkout main -- <path>` away.

## Removed: the workflow

- `.pi/` — coordinator loop and role prompts; `providers.toml` — provider budgets, models, schedule.
- `AGENTS.md`, `AGENT_GUIDE.md`, `HANDOFF.md` — instructions to the agents.
- `TODO.md`, `TODO_ARCHIVE.md` — the ticket queue and its archive. The archive holds every ticket's
  measured Result paragraph; read it from `main` when building the new queue format.
- `tools/`: the coordinator, judge, auditor, ticket admission and stamping, landing, worktrees, the
  daily review and management window, digest and slide writers, provider quota probes and pacers,
  the incident log, benchmarks and replays, spend ledgers.
- `docs/`: audits, proposals, reviews, benchmarks, generated ticket traces, the config log, the
  contention and stages maps.
- `WORKFLOW_AUDIT.md`, `MODEL_RESEARCH.md`, `REPORT_T75.md`.

## Kept: the project

- `src/`, `vendor/`, `assets/`, `Cargo.*`, `build.rs` — the ROM.
- `reference/bn6f` — the disassembly (submodule).
- `tools/`: the measurement harness (`harness.py`, `verify_rows.py`, `chip_compare.py`, the capture
  and compare tools, `check_inputs.sh`/`restore_inputs.sh`), the state trace and oracle, coverage
  and `coverage_percent.py`, the inventory, every exporter, the disassembly tooling
  (`field_names.py`, `apply_renames.py`, `rename_lane.sh`, `ghidra_decompile.sh`, `csrc.py`),
  the site and blog builders.
- `docs/`: `SCOPE.md`, `coverage/`, `inventory/`, `recon/`, `worklog/`, `trace/`, `provenance.md`,
  the porting plan `HANDOFF_2026-09-12.md`.
- `web/` — the site, blog and browser ROM.

## What the new orchestrator must provide

A ticket format and queue; a way to give a worker one ticket in an isolated checkout; the landing
gate (`verify_rows` from a clean checkout before any merge, one merge at a time); ticket authoring
from the scoreboard and `SCOPE.md`; budget awareness per provider. The invariants the old workflow
enforced and this one must too: canon never changes; no fitted constants; a row whose negative
fixture does not fail is BLIND; every constant cites the disassembly or a measurement.
