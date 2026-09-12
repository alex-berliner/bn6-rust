# PI_WORKFLOW — the pi-native way to build this replica

**Status:** draft. `SUBAGENT_FLOWS.md` is the approval artifact for the agent flow
and model routing; this file is the standing guide that the flow, the artifacts
and the benchmark tools are built against. Nothing here overrides `AUDIT.md`.

This document is bn-specific on purpose. The parity target, the harness, the
worktree protocol and `AUDIT.md`'s 17 rules are the reason the workflow looks
the way it does; the shape is not portable to a project that does not measure
per-pixel parity.

---

## 0. Research baseline

Two inputs: what this repo already does, and what pi can actually express.
Everything below was verified by reading the file named, not from memory.

### 0.1 The repo's existing process

| Source | What it fixes as law | Lines worth naming |
|---|---|---|
| `AUDIT.md` | 17 problem/solution pairs: no boxes in space or time; no subtracted baselines or "inherent" residues; every check must be able to fail (negative fixture, no BLIND rows); tickets state a measurement, not a hypothesis; a non-zero is a failure, full stop; gallery is a harness output; provenance tags on every constant. | the pair table, and the Optimisations table (numpy diff first, then parallelise) |
| `HANDOFF.md` §8 | Agents run **one agent, one worktree, non-overlapping files**; `tools/worktree.sh <name>` prints dir/branch/`CARGO_TARGET_DIR`; verify from a tree no agent holds, then `git merge --no-ff`; never push; annotations in `reference/bn6f` are comments/labels only, on local branch `bn-notes`. | §8, §9 gotchas |
| `TODO.md` | Ticket rules: one worktree each; **baseline first**, same script before and after, report both; say which frame window was measured; `src/` only unless the ticket says otherwise; a precise negative result is a good outcome; **do the work yourself** (no onward delegation). Coordinator rules: don't build/measure from a tree a worker holds; rebuild a disagreeing number before contradicting it; `git add -u <path>` limits scope. | "Every ticket runs in its own git worktree", "Rules for every ticket", "Rules for whoever is handing the tickets out" |
| `FIXTURE.md` | The 64-byte descriptor at `0x02000040` and the "BATT" marker at `0x02000000`. One ROM, told what to be; align on the marker, never a power-on frame. | whole file |
| `tools/harness.py` | The one gate. 59 comparison checks (43 chip + 16 others) plus a `rollup` no-crash walk; `--list` enumerates them, `--only` runs a subset. Runs isolated + integrated, a negative fixture per check, full-screen every frame. Also owns `provenance_counts()` (`fitted`/`derived`/`peeked`) and `CHECKS`. | `main()`, `provenance_counts()`, `CHECKS` |
| `tools/allowlist.py` | Ticketed known defects; still print as `FAILED (allowed: ...)`, never pass. Format `{key: (max_px, "TICKET-ID", "DATE")}`. | `ALLOWLIST` |
| `tools/scoreboard.py` | Chip-only scoreboard; 43 rows, mean px per frame, zero is exact. | header docstring |
| `tools/chip_compare.py` | The library: `capture()`, `diff_frames()` (numpy), `frame_array()`, `scratch()` (keyed on checkout path), `peek16()`, `capture_real()`. | the harness reuses this |
| `tools/worktree.sh` | Isolated worktree; symlinks `reference/bn6f` and marks it `--skip-worktree` so a stray `git add -A` cannot stage the gitlink. | whole script |

**Current state (from `AUDIT.md` / `HANDOFF.md` §10):** passing at 0 — `opening`
(isolated), `wave`, `window`, `rollup`; 19 fitted / 145 derived / 112 peeked;
every other row has a number and a cause in `AUDIT.md`. The standing instruction
in `~/.claude/projects/-home-box-Code-bn/memory/` is *Sonnet workers, high
effort, keep the main thread for coordination* — the routing matrix in
`SUBAGENT_FLOWS.md` replaces that with explicit tiers, so it needs the user's
approval before it becomes the rule.

### 0.2 What pi 0.85.1 can express

Verified against the installed package at
`/home/box/.nvm/versions/node/v24.15.0/lib/node_modules/@earendil-works/pi-coding-agent/`.

| Capability | Where it lives | What it means here |
|---|---|---|
| Context file | `AGENTS.md` / `CLAUDE.md`, global + parent dirs + cwd, concatenated (`README.md` §Context Files) | The repo's operating rules reach every session and every subagent without being pasted. |
| Sub-agents | **not built in** (`README.md`: "No sub-agents"); the example extension `examples/extensions/subagent/` implements them | A project-local extension can spawn `pi` children with isolated context, per-role model/tools/thinking. |
| Agent definition | markdown + YAML frontmatter: `name`, `description`, `tools`, `model`; `~/.pi/agent/agents/*.md`, `.pi/agents/*.md` (project needs `agentScope` + trust) | One file per role. Omitted `model` inherits the dispatcher's model/thinking. |
| Subagent invocation | `pi --mode json -p --no-session --model … --thinking … --tools …`, spawn per child (`index.ts:300-345`) | Model routing is a CLI flag; it is real and inspectable. |
| Modes | single `{agent, task}`; parallel `{tasks:[…]}` (max 8 tasks, 4 concurrent); chain `{chain:[…]}` with `{previous}` | Maps onto this repo's real split: read-only recon fans out; edits stay serial. |
| Prompt templates | `.pi/prompts/*.md`, invoked `/name`, `$1`/`$@`, `{previous}` in chains | Encodes the ticket workflow as `/bn-implement`, `/bn-recon`, `/bn-verify`. |
| Skills | `.pi/skills/**/SKILL.md`, on-demand, `/skill:name` | Home for the harness/measurement runbook so it is not in every context. |
| Extensions | `.pi/extensions/`, project-local, loaded only after trust | The subagent tool, and any guardrails. |
| Settings | `~/.pi/agent/settings.json`, `.pi/settings.json` | `defaultModel`, `modelThinkingLevels`, per-project defaults. Currently `openrouter` / `moonshotai/kimi-k2.6`. |
| Model access | `~/.pi/agent/models-store.json`: one provider, `openrouter`, 375 models; `auth.json` has `openrouter` | Mixed-tier routing is available on one provider; no new account needed. |
| Trust | project `.pi` resources load only when the folder is trusted; `-a`/`--approve` overrides one run; `defaultProjectTrust` in global settings | A fresh clone must run non-interactively with `--approve` or be trusted, or agents/skills/prompts/extensions silently do not load. |
| Goals | `npm:pi-goal-x` (installed) | Task trees + evidence contracts already in use; the scoreboard complements it. |

### 0.3 Gaps this goal closes

1. **No encoded workflow.** `HANDOFF.md` §8 is prose for a *Claude Code* Agent
   tool and `~/.claude/...` memory. Pi has a different mechanism (markdown
   agents, `.pi/agents`, `.pi/prompts`, project extension); none of it exists yet.
2. **No per-role model routing.** The repo says "Sonnet workers, not DeepSeek"
   in an external memory file; pi's default is one model for everything. There is
   no matrix saying which tier + thinking level each role gets, and no way to
   measure whether that choice is right.
3. **No model benchmark.** Nothing answers "is model A better per dollar than
   model B on *this* workload", where the workload is disassembly reading,
   measurement, and parity attribution — not generic coding.
4. **No progress roll-up.** `harness.py --list` names rows; `AUDIT.md` holds the
   closing state; `allowlist.py` holds tolerated failures; `provenance_counts()`
   holds the fitted/derived/peeked split. Nothing puts them on one current page.

### 0.4 Non-negotiable constraints for whatever gets built

- `AUDIT.md`'s 17 rules are unchanged and bind the new tooling. In particular a
  benchmark that scores a model must still be able to fail (negative control),
  must not subtract a baseline, and must not compare a box.
- No new `demo-*` cargo features. Copyrighted inputs stay in `/tmp` and
  gitignored; never `git add -f`, never `git add -A`, never push.
- Captures are memory-heavy and serialise; a benchmark that runs captures must
  stream (`chip_compare`'s `--diff-against`) or run one at a time.
- Project-local pi resources require trust; anything shipped must be inert in an
  untrusted clone.
