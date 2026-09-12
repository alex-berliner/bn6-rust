# WORKFLOW_AUDIT — is the agent workflow token-optimal for the scoped goal? (2026-09-12)

Scope audited: the cut-down engine (the 43 chips already in the harness, 5 viruses, 2 bosses,
player fidelity, the custom screen for that deck, battle flow, and the infrastructure that
makes those checkable). Estimated at ~110 tickets / ~$750 before this audit.

Workflow audited: HANDOFF.md §8 as practised, plus the pi design in SUBAGENT_FLOWS.md /
PI_WORKFLOW.md and the `.pi/goals` objective, plus the per-role model routing from
MODEL_RESEARCH.md.

Cost model used: per-ticket figures from the session estimate — coordinator ~$2.40 (70% of a
ticket), worker ~$0.75, recon ~$0.07, planner ~$0.05, verifier ~$0.06, measurer/archivist
~$0.03; hard timing rows take 2–4 attempts.

## Findings

| # | Element | Finding | Verdict | Change |
|---|---|---|---|---|
| 1 | The `.pi/goals` objective | Its seven success criteria are all tooling (guide, 7 roles, 7 flows, extension, benchmark, scoreboard); advancing parity rows is explicitly out of scope. The benchmark alone (5 suites × 8 candidate models, one suite running captures) is ~40 ticket-equivalents, roughly $200–300, i.e. a third of the whole scoped engine, to choose between models whose price difference per ticket is cents. | Not token-optimal | Replace the benchmark with usage logging on real tickets (pi's JSON usage is free) and one A/B on the two live tickets. Drop the scoreboard until rows move. Re-scope the goal to the engine. |
| 2 | Long-lived coordinator | 70% of every ticket is the coordinator resending 100–200k of context. The 5-minute check-in loop is a full-context turn every 5 minutes: ~$0.90/hour idle on Opus 5, ~$36 over a 40-hour capture calendar. | Largest single waste | Fresh coordinator session per ticket batch, handing off through HANDOFF.md (which exists for this). Event-driven wakeups on task notifications with a 20–30 minute fallback, not a 5-minute poll. Hard cap the coordinator at ~100k context. |
| 3 | recon → planner → worker chain on every ticket | Three roles each read overlapping context (asm, journal, plan, src). For chip-convergence tickets the mechanism is already implemented and the residue is timing; recon and planner add ~$0.15 and two coordinator turns (~$0.30) for nothing. | Wasteful for most of the scope | Recon only when the oracle does not localise. Planner only for tickets with an unknown mechanism (viruses, bosses, the timing gaps). Chip-convergence tickets go straight to a worker with a templated ticket. |
| 4 | One ticket per harness row | The 43 chips are 7 swords, 6 bombs, 8 recoveries, 4 vulcans, 3 cannons, 3 barriers, 4 seeds, and singletons; they already share one descriptor template and one build. Per-row ticketing re-derives the same family residue up to 8 times. | ~3× waste on chips | Ticket per chip family (~12 tickets), with the family's rows as the acceptance set. |
| 5 | Verifier on every ticket | For a row that reads 0 with a non-blind negative, the harness is the verifier; a model verifier adds a spawn and two coordinator turns and, per the review study, catches little on large diffs anyway. | Conditional value | Verifier only for judgment tickets: allowlist edits, fitted constants, fixture recipes, timing attributions, and anything that changes a canon-side patch. Zero-reading rows merge on the harness line alone, still from a detached tree. |
| 6 | Measurer role | A model that runs `harness.py --only X` and copies the line. The script already prints the line. | Pure overhead | Delete the role. The worker or coordinator runs the script and the output file is the record. |
| 7 | Archivist + the journal | Writing is cheap (~$0.01). Reading is not: TRANSFER.md is ~2,900 lines (~40k tokens) and recon/planner read sections of it every ticket (10–30k). Documentation is a read-side token liability. | Wrong side optimised | Agents read only HANDOFF §0–§4 and the row's own `note`. TRANSFER.md is for humans; AGENTS.md says so explicitly. Per-ticket facts go into the harness row note and the AUDIT closing table, not prose. |
| 8 | AGENTS.md in every child | If it carries HANDOFF + AUDIT (~10k tokens) every spawn pays it; ~5 spawns/ticket ≈ 50k/ticket. Children share a cache only if the prefix is byte-identical and within TTL (Anthropic 5 min, Gemini ~3–5 min). | Small but compounding | Keep AGENTS.md under ~2k tokens and byte-stable; role text after it; nothing volatile (dates, ticket text) before the last stable block. |
| 9 | Attribution by reading (F5 `/bn-attribute`) | The design parallelises attribution (recon ∥ measurer → planner → worker) instead of making it unnecessary. Hard timing rows cost 2–4 attempts because nothing tells the worker which variable diverged on which frame. | Optimises the wrong step | Build the state oracle first (canon RAM watch of RNG/object table/timers vs. an exported Rust state block; harness reports first divergent frame and field). Expected effect: attempts on timing rows from ~3 to ~1.5. |
| 10 | Independent rows in the ticket loop | 40 of 59 rows share the deleted-enemy fixture defect. Ticketing any chip before the fixture chain lands re-derives the 14388 baseline. | Ordering error | One infrastructure ticket (recipes → battlestart → emptyfield → chip_ready_empty → re-point rows) before any chip ticket. |
| 11 | Escalation ladder T2 → T1 → T0 | Each failed rung costs a worker run plus coordinator turns (~$1.25). Starting cheap is only cheaper if the cheap model's success rate on this workload exceeds ~60%; there is no data, and the workload (no_std Rust, hand asm) is where cheap models are weakest. | Likely net-negative | Two rungs: start at the workhorse (Sonnet 5 or Gemini 3.8 Flash), escalate to Sol/Opus 5 after one failure on a timing ticket. |
| 12 | Model routing matrix | Per-ticket effect of any subagent model choice is cents. The one material choice is the coordinator's cache-read rate (Anthropic 0.1×, Fable 5.1 $0.25/M, Opus 5 $0.50/M, Sol $0.20/M if the listed price holds). | Fine, over-engineered | Pick the coordinator by cache price and judgment; keep the rest as MODEL_RESEARCH.md recommends; stop tuning it. |
| 13 | Root-state recipes | Frame-by-frame reading with a frontier model is a few hundred k tokens per state. | Avoidable | RAM-driven walks in Python; a vision model only at branch points; record the input log once. |
| 14 | Worktree + detached verification + full-table run before commit | Token-neutral (scripts), calendar-heavy (15–25 min per full run, captures serialize). | Keep | Full table only at merge to main; per-row runs in worktrees — already the rule. |
| 15 | Design documents | PI_WORKFLOW.md + SUBAGENT_FLOWS.md are ~400 lines to maintain and, if they enter agent context, ~8k tokens per read. | Keep out of agent context | Fold the surviving decisions into HANDOFF §8; do not reference them from AGENTS.md. |

## Revised budget for the scoped goal

| Lever | Before | After |
|---|---|---|
| Coordinator per ticket | $2.40 | ~$1.00 (fresh sessions, event-driven, ≤100k context) |
| Tickets | ~110 | ~70 (family-level chips, no measurer/archivist spawns, fixture chain first) |
| Attempts on timing tickets | ~3 | ~1.5 (oracle) |
| Per ticket, average | ~$6.80 incl. multi-attempt | ~$2.50 |
| Scoped engine | ~$750 | ~$275 (+$100 infrastructure) → **~$375, range $300–700** |

## The minimal loop that the audit supports

1. Infrastructure first, in this order: recipes → fixture chain → oracle → usage logging.
2. Ticket = a family or a system, with its harness rows as the acceptance set, in a worktree.
3. Worker (Sonnet 5 / Gemini 3.8 Flash, xhigh) runs baseline → change → after, using the oracle's first divergent field; recon/planner only when the oracle does not localise.
4. Coordinator (Opus 5 or Sol, fresh session per batch, ≤100k context) merges on the harness line; a verifier (Terra) only for judgment tickets.
5. Facts land in the row note and the AUDIT table; the journal is for humans.
