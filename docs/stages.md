# The day, in stages

This project runs itself. A cron job wakes every half hour and starts agent runs; another wakes once a
day and does the managerial work — measuring how yesterday went, deciding what to change, writing the
tickets, publishing the blog. Until 2026-09-17 those two things simply overlapped, and the managerial
jobs kept losing, because they run at the start of a cycle when six workers have already spent most of
the day's provider budget. The auditor — the one job whose entire purpose is to notice the workflow
going wrong and propose a fix — produced two reports in four days, and the rest of the time died on
"no candidate for auditor has budget now".

So the day is now staged. Work does not start until management has finished.

## The stages

| # | Stage | When | Spends model budget | What runs | If it fails |
|---|---|---|---|---|---|
| 0 | **Restore** | every 30-min tick | no | `check_inputs.sh` and `restore_inputs.sh` (a reboot empties `/tmp`), stale worktree prune, `roles.py check`, `retype_if_stale.sh` | the tick stops; nothing else runs |
| 1 | **Measure** | once a day, window opens | no | `daily_review.sh`: the scoreboard re-measured, cost per landed ticket, waste, ticket supply against demand, **operational incidents**, and the auditor's triggers | review is written with what it has |
| 2 | **Decide** | after 1 | yes, cheap tier | `pi_audit.sh` proposes agent-setup changes; `audit_apply.py` applies the low-risk subset; `premise_check.py`; `prime_queue.sh` fills the ticket queue to twice the worker slots | recorded as an incident |
| 3 | **Publish** | after 2 | yes, writer tier | `digest_post.py` (the daily blog), `learn_slides.py`, `annotate_asm.py` (findings back into the disassembly), `apply_renames.py`, `publish_site.sh` (fresh ROM on the site) | recorded as an incident |
| — | **gate** | end of 3 | — | the window writes `/tmp/bn-pi/mgmt-done-<date>` | see below |
| 4 | **Work** | every 30-min tick, once the gate is open | yes, the bulk | `run_day.sh` starts a coordinator per provider; each dispatches workers, verifiers and recon against claimed tickets | the tick reports and waits for the next |
| 5 | **Land** | continuous, inside stage 4 | no | `verify_rows.py` from a clean checkout, then `land.sh`: lock, merge, remove worktree, delete branch | refusal recorded as an incident; the branch survives |

## The gate

`run_day.sh` will not start a worker run between the management window opening and the window
reporting itself finished. Two settings control it, both overridable by environment variable:

- `BN_MGMT_OPEN` (default `0600`) — when the window opens.
- `BN_MGMT_DEADLINE` (default `0900`) — when work proceeds regardless.

If the marker has not appeared by the deadline, work starts anyway and an incident is recorded. A
broken roundup should cost one management window, never the whole day.

Outside that window — overnight, and all afternoon — ticks behave exactly as before.

## What the auditor may now change by itself

The auditor writes proposals as unified diffs. `tools/audit_apply.py` applies at most one per cycle,
and only if every one of these holds:

1. **It touches instruction text only** — `.pi/coordinator.md`, `.pi/agents/*.md`, `AGENTS.md`,
   `AGENT_GUIDE.md`. These are prompts: a bad one makes an agent work badly for a cycle and the next
   review shows it. Anything under `tools/`, `src/`, the harness or `providers.toml` is refused,
   because those can silently corrupt a measurement or spend money, and a measurement nobody can
   trust is worse than no change at all.
2. **It does not delete an invariant.** A removed line naming `verify_rows`, canon, the spend floor,
   fitted constants or `check_inputs` refuses the whole item, whatever else it does.
3. **It is small** — at most 60 changed lines.
4. **It applies cleanly** — `git apply --check`, no fuzz.
5. **One item per cycle**, which is the rule `docs/config-log.md` was already built around.

Everything applied is committed and logged in `docs/config-log.md` against the audit it came from, so
the next review can attribute a metric change to it. Everything refused becomes an incident, which is
what puts it in front of a person.

## Incidents

Stages 2 through 5 record their failures with `tools/incident.sh`, one JSON line each to
`/tmp/bn-incidents.jsonl`. Stage 1 reads them back, prints them in the review, and triggers the
auditor if there are any. This is the loop's only way of seeing its own machinery break: none of these
failures produce a ticket result, so before this existed every one of them had to be found by a human
reading terminal panes.

Kinds recorded today: `land-refused`, `land-conflict`, `verify-failed`, `lock-timeout`,
`rename-reverted`, `asm-refused`, `judge-discarded`, `auditor-blocked`, `audit-unapplied`,
`mgmt-window-missed`.

## The open question: when the window should be

The window is at 06:00 because that is when the blog post wants to exist. It is not where the budget
wants it. The main provider's credits reset at about 10:35, so a 06:00 management window spends
whatever last night's runs left behind — which on most days is very little, and is the direct cause of
the auditor starving. Moving the window to just after the reset would fix the budget problem and move
the morning blog post to mid-morning. See `docs/contention.md` for the resources these stages share.
