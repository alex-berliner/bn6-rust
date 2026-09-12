# SUBAGENT_FLOWS — pi agent design for the bn replica

**This file is an approval gate.** Task 4 (the subagent extension) does not start
until the user approves this design. Everything here is proposed, not yet law;
`AUDIT.md` and `TODO.md` remain the rules of the work itself.

Read `PI_WORKFLOW.md` §0 first for the verified facts this builds on.

---

## 1. The mechanism, concretely

Pi has **no built-in sub-agents** (`README.md`: *"No sub-agents."*). We adopt the
mechanism pi ships as its own example, vendored project-local and adapted:

```
.pi/
  agents/                  one markdown file per role (YAML frontmatter + prompt)
    recon.md
    planner.md
    worker.md
    measurer.md
    verifier.md
    archivist.md
    benchmarker.md
  extensions/subagent/
    index.ts               the `subagent` tool (spawns child pi processes)
    agents.ts              agent discovery (user + project dirs)
  prompts/                 named flows, invoked as /bn-*
    bn-recon.md
    bn-implement.md
    bn-verify.md
    bn-sweep.md
    bn-attribute.md
    bn-bench.md
    bn-close.md
  settings.json            default model/thinking, project defaults (trusted only)
AGENTS.md                  the repo operating rules, loaded by every session and child
```

How a role actually runs, verified in `examples/extensions/subagent/index.ts`:

```
pi --mode json -p --no-session \
   --model <role.model> --thinking <dispatch or role level> \
   --tools read,grep,find,ls[,bash,...] \
   --append-system-prompt <tmp file with the role body> \
   "Task: <task text>"
```

- Each child is a **separate process with an isolated context window**. It never
  sees the parent transcript; it gets the task text plus the role prompt. That is
  the point: the main thread stays a coordinator, and recon hands back compressed
  context instead of making the coordinator read the disassembly.
- Modes: **single** `{agent, task}`, **parallel** `{tasks:[…]}` (max 8 tasks,
  4 concurrent), **chain** `{chain:[…]}` with `{previous}`.
- A role with no `model:` inherits the dispatcher's model and thinking level.
- Project agents/extensions load **only when the folder is trusted**. In an
  untrusted clone the tools are absent, not silently broken.

**Security note.** `.pi/agents` and `.pi/extensions` are repo-controlled prompts
and code. Enabling project scope means this repo can instruct a model to run
commands. That is acceptable here because the repo is the user's own; the
extension keeps pi's default of user-scope agents and requires
`agentScope: "both"` explicitly.

---

## 2. Division of labour — what is *not* delegated

The repo has already paid for these rules in wrong numbers (`TODO.md`, incident
notes in `HANDOFF.md` §9). The agent design encodes them rather than re-learning:

1. **The coordinator owns judgment.** Merges, attribution reasoning, deciding
   that a number is real, editing `reference/bn6f`, and the final verification
   stay in the main thread. The coordinator does not do volume reading or long
   capture runs — those are delegated.
2. **One level of delegation only.** A `worker` never spawns its own subagents
   (TODO: *"DO THE WORK YOURSELF… a ticket that turns out to be bigger than it
   looked comes back as a report saying so, not as a subcontract."*). Enforced by
   giving `worker` no `subagent` tool.
3. **One writer, one worktree, non-overlapping files.** `tools/worktree.sh <name>`
   is the only way a writer gets a tree. `reference/bn6f` stays read-only to
   agents.
4. **Read-only work may parallelise; edits may not.** Recon and disassembly
   sweeps fan out. Two agents editing `src/battle.rs` never run at once.
5. **Captures serialise.** One `measurer` at a time runs harness rows; it streams
   or cleans up (AUDIT pair 13). No parallel captures on this box.
6. **A number is verified from a tree no agent holds.** The `verifier` runs from
   a detached worktree of the branch, never from the worker's live tree.

---

## 3. Roles

Tier names are defined in §4. "Writes" says what the role may change.

| Role | Purpose | Tier | Tools | Thinking | Writes | Worktree |
|---|---|---|---|---|---|---|
| `recon` | Locate routines/data in `reference/bn6f`, read `src/`, return file:line + the actual code + candidate mechanism. Never edits. | T2 fast | read, grep, find, ls, bash | low | nothing | no |
| `planner` | Turn a ticket's measurement + recon into a concrete plan: baseline command, exact change points, after-command, expected observable, risks. Never edits. | T0/T1 | read, grep, find, ls | high | nothing | no |
| `worker` | Implement one ticket in one worktree. Baseline first, change, re-run identical script, report both numbers, commit per landed step. | T1 | all default (no `subagent`) | high | `src/` (+ ticket-allowed paths) | **yes** |
| `measurer` | Run harness rows / captures / sweeps and report raw `total`/`worst`/frames/window. The only role that runs captures; strict serial. | T2 | read, grep, bash | low | nothing (may write `/tmp` scratch) | no |
| `verifier` | Independently reproduce a worker's number from a tree no agent holds; run the relevant rows; audit the diff against the 17 rules; report pass/fail + residue with frame/region. | T0 | read, grep, find, ls, bash | high | nothing | detached |
| `archivist` | Mechanical doc work: TRANSFER.md entry, TODO/AUDIT table updates, provenance tags, gallery/manifest regeneration. | T2 | read, grep, edit, bash | low | docs + `// provenance:` lines only | no |
| `benchmarker` | Run the model/subagent benchmark suite, tally usage/cost, write the report. | T1/T2 | read, grep, bash | medium | `tools/bench_results/` | no |

Rules that hold for every role: `AGENTS.md` is loaded, so `AUDIT.md`'s rules and
the "stage by path, never `git add -A`" rule apply without restating them.

**Why `verifier` is separate from `worker`.** The repo already has the scar:
measuring from a tree an agent holds gave wrong numbers three times, and once
made the coordinator tell a correct agent it was wrong (`HANDOFF.md` §9).
Verification is a different tier and a different tree, on purpose.

---

## 4. Model routing

One provider is configured — OpenRouter (375 models, `models-store.json`;
`auth.json` has `openrouter`). Mixed tiers are therefore available with no new
account. Concrete default ids exist and are named here so the matrix is testable;
the **benchmark (§7), not this table, is the authority** on which model belongs
in which tier.

| Tier | Intent | Candidate defaults (OpenRouter ids) |
|---|---|---|
| **T0 — frontier** | Reasoning under uncertainty: attribution, plans where a wrong guess costs a 25-minute suite run, independent verification, merge resolution. | `anthropic/claude-opus-4.6`, `openai/gpt-5.1`, `google/gemini-3.1-pro-preview` |
| **T1 — workhorse** | Standard implementation and review: capable, cheaper than T0, good tool use. | `anthropic/claude-sonnet-4.6`, `moonshotai/kimi-k2.6`, `openai/gpt-5.1-codex` |
| **T2 — fast/cheap** | Mechanical, high-volume, low-judgment: recon, measurement, archival, sweeps. | `anthropic/claude-haiku-4.5`, `google/gemini-2.5-flash`, `deepseek/deepseek-v3.2`, `z-ai/glm-4.6` |
| **T3 — local (optional)** | Offline/zero-marginal-cost: recon over a checked-out disassembly, archival drafts. Not configured yet; needs an Ollama/vLLM provider entry in `models.json`. | — (unset) |

Default assignment (to be confirmed by the bench):

| Role | Model | Thinking |
|---|---|---|
| `recon` | T2 (`claude-haiku-4.5`) | low |
| `planner` | T0 (`claude-opus-4.6`) | high |
| `worker` | T1 (`claude-sonnet-4.6`) | high |
| `measurer` | T2 (`gemini-2.5-flash`) | low |
| `verifier` | T0 (`gpt-5.1`) | high |
| `archivist` | T2 (`claude-haiku-4.5`) | low |
| `benchmarker` | T1 (`kimi-k2.6`) | medium |

**This supersedes `~/.claude/projects/-home-box-Code-bn/memory/feedback_sonnet_workers.md`**
("Sonnet workers, not DeepSeek"). The user asked for mixed tiers; DeepSeek is
now a *candidate T2*, only allowed into `recon`/`measurer`/`archivist`, never a
`worker` or `verifier`, and only if the bench shows it earns its place. The
design keeps the memory file's intent (quality on the main thread and on edits)
while making the cheap tier explicit and measured.

Switching models per task is one flag; pi's `/model` and `/thinking` can override
for a session, and a role's `model:` frontmatter overrides everything for that role.

---

## 5. Flows

Each flow is a `.pi/prompts/*.md` template. `{previous}` is the chain handoff.

### F1 `/bn-recon <question>` — compressed context
- **single** `recon`, or **parallel** `recon ×N` when the question spans domains
  (disassembly / data tables / `src/`).
- Returns: exact `file:line` ranges, the code, dependencies, "start here".
- No edits. Safe to fan out.

### F2 `/bn-implement <ticket>` — the ticket loop
```
recon ──► planner ──► worker        (chain)
                         │
                         ▼
                 coordinator merges
                         │
                         ▼
                    verifier        (separate, from a clean tree)
```
- `planner` must emit: baseline command + current number, change points,
  after command, expected observable, the frame window to report, risks.
- `worker` runs baseline → change → after, commits on `wt/<name>`, reports both
  numbers with frame/window. A precise negative result is an accepted outcome.
- Coordinator verifies from a tree no agent holds, then
  `git merge --no-ff`, `worktree remove`, `branch -d`, `rm -rf /tmp/ct_*`.

### F3 `/bn-verify <branch|row>` — independent check
- **single** `verifier` in a detached worktree.
- Re-runs the relevant harness rows, compares against the worker's claimed
  numbers, checks the diff against the 17 rules, returns PASS/FAIL + residue.
- The verifier is allowed to say "the number is right, the explanation is wrong"
  — `TODO.md` insists those are judged separately.

### F4 `/bn-sweep <question>` — read-only broad search
- **parallel** `recon × up to 8` partitioned by file domain, each returning
  `file:line` evidence. Coordinator joins. No captures, no edits.

### F5 `/bn-attribute <residue>` — the core debugging flow
```
        ┌─ recon (disassembly: what routine drives this?)  ─┐
parallel┤                                                    ├─► planner ─► worker
        └─ measurer (what frame/region does the harness see?)┘
```
- The two sides are independent and both cheap; run them in parallel.
- `planner` synthesises the mechanism, names the exact change, and states the
  falsifier ("if X is the cause, changing Y must move the row to Z").
- `worker` tests the falsifier before writing the fix. A disproven hypothesis is
  a result and goes to TRANSFER.md.

### F6 `/bn-bench [suite]` — model benchmark
- **single** `benchmarker`, which itself runs child `pi` processes across the
  candidate models (see §7). Serial when the tasks capture; parallel when they
  are read-only.

### F7 `/bn-close <ticket>` — land the paper trail
```
verifier ──► archivist   (chain)
```
- `verifier` confirms the number; `archivist` writes the TRANSFER entry, flips
  the TODO/AUDIT status, adds `// provenance:` tags for any constant touched,
  and regenerates the gallery/manifest. Docs only.

---

## 6. Coordination loop

- One ticket in flight per `worker`; one worktree each.
- A **5-minute check-in** (`/loop 5m` or cron): list live agents, verify/merge
  finished branches, prod any agent silent >15 min with no commit, report a few
  lines. This is `HANDOFF.md` §8's existing loop, now fed by the subagent tool's
  live status.
- **Never measure from a tree an agent holds.** If a number disagrees, rebuild
  it yourself before contradicting the agent.
- Every child's usage line (`turns ↑in ↓out $cost ctx:…`) is captured; the
  coordinator's run log is the raw material for the benchmark's cost column.
- Merge protocol is unchanged: verify → `git merge --no-ff wt/<name>` →
  `worktree remove --force` → `branch -d` → `rm -rf /tmp/ct_<name>`. Never push.
- If a commit changes what the screen shows, the gallery is updated before the
  next commit (AUDIT pair 7); the `archivist` owns this in F7.

---

## 7. Benchmark design (what validates the routing)

Purpose: answer *"which model/tier belongs in which role, per dollar, on **this**
workload"* — disassembly attribution, measurement honesty, and parity
implementation — not generic coding.

**Task suite** (each task declares its pass condition before it runs; AUDIT pair 15):

| Suite | Task | Objective grade | Notes |
|---|---|---|---|
| B1 `attribute` | Given a residue + frame numbers, name the routine that drives it. | `file:line` matches a known-correct answer (exact / same routine / wrong). | ground truth from `TRANSFER.md`; no captures |
| B2 `measure` | Run an assigned harness row and report `total`/`worst`/frames/window. | report equals harness ground truth; "boxed" or omitted-window answers fail (AUDIT pair 6/15). | cheap rows only |
| B3 `implement` | Fix a known-authored defect on a scratch branch (a reverted historical fix, e.g. the A1 departure sequence). | the row's number improves to its recorded 0 and no other row regresses. | the only capture-running suite; strict serial |
| B4 `plan` | Plan a real open ticket from recon context. | rubric judge: names baseline number, exact change point, falsifier, window. | rubric, because a plan has no single number |
| B5 `archive` | Write a TRANSFER entry + provenance tags for a given diff. | rubric judge: measurement stated, hypothesis marked unverified, provenance correct. | mechanical |

**Scoring.** Per run: pass/fail per task, `turns`, input/output/cache tokens,
`$cost`, wall-clock. Headline metric:

> **feature-replication-per-dollar = (verified task passes) / $cost**

with wall-clock as the tiebreak. Only `verifier`-confirmed passes count toward
the numerator, so a model cannot win by claiming a result. A task that "passes"
while breaking another row is counted as zero.

**Negative control (mandatory, AUDIT pair 10).** Every suite ships a deliberately
wrong configuration (a model given a misleading prompt, or a known-bad plan) that
must score below the real runs. A benchmark whose broken control ties the real
runs is BLIND and is rejected, not reported.

**Rubric judge.** Only for B4/B5, and only while it demonstrably tracks
objective outcomes better than objective-only grading — the user's condition.
The judge model must not be one of the candidates under test in the same run.

**Candidate set** for the first run: one model per tier per role-type
(`claude-opus-4.6`, `gpt-5.1`, `claude-sonnet-4.6`, `kimi-k2.6`,
`claude-haiku-4.5`, `gemini-2.5-flash`, `deepseek-v3.2`, `glm-4.6`), so the
matrix's claims are tested rather than asserted.

**Progress scoreboard** (separate from the bench): one page reconciling
`harness.py --list` (59 checks + rollup) against the last gallery captions
(`web/captures/<name>-<ui>.txt`, which already carry `total`/`worst`/PASS and the
commit), `allowlist.ALLOWLIST` (tolerated defects), `provenance_counts()`
(fitted/derived/peeked), and TODO ticket statuses. It reads; it never runs
captures or edits the harness.

---

## 8. Failure modes the design must survive

| Mode | Guard |
|---|---|
| Untrusted clone | Project agents/extensions don't load; `AGENTS.md` still gives the rules; nothing executes. |
| Runaway/looping child | `MAX_CONCURRENCY` cap, abort propagates to children, coordinator's 5-min loop prods silent agents. |
| Two workers on one file | One worktree per worker; non-overlapping files by ticket; coordinator refuses overlapping tickets. |
| Agent commits in `reference/bn6f` | Worktree symlinks it and marks it `--skip-worktree`; role prompts say read-only; coordinator owns disassembly comments. |
| Agent claims a number it didn't measure | `verifier` from a tree no agent holds; stage-by-path; the benchmark only counts verified passes. |
| Cheap model drifts in a judgment role | Escalation ladder: T2 → T1 → T0 on explicit triggers (two failed baseline-after runs; a verifier disagreement; two failed attributions). |
| Prompt-cache thrash | Stable prefixes (`AGENTS.md`, ticket text) and `showCacheMissNotices` to see misses; recon returns compact context. |
| `/tmp` exhaustion | Captures stream or clean up (AUDIT pair 13); scoreboard/bench never accumulate raw frames. |

---

## 9. What approval unlocks

On approval, task 4 builds the extension and tasks 3/5/6/7 build the rest. If any
part of this is wrong, the cheap moment to change it is now, before the artifacts
exist. Open questions worth answering in review:

1. Tier→model defaults in §4 — accept, or pin different ids?
2. `agentScope: "both"` (project agents enabled) — accept for this repo?
3. The B3 `implement` suite reverts historical fixes on scratch branches to make
   ground truth — acceptable use of this repo's history?
4. T3 local tier — configure an Ollama provider now, or leave it unset?
