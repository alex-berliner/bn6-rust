# Configuration changelog -- every reshape of the agent setup, with the evidence and the metric it was meant to move

The auditor (tools/pi_audit.sh) proposes entries; a human session applies them and records the result here.
One structural change per cycle. Invariants that never change: canon never changes; verify_rows before
every landing; no fitted constants; the $5 spend floor.

| date | change | evidence | metric expected to move | outcome |
|---|---|---|---|---|
| 2026-09-12 | coordination moved from a Claude session to a pi coordinator (muse contributor) with roles worker/verifier/recon | $3-8 per row on the Claude plan; coordinator context re-sent per turn | cost per landed ticket | $0.01-0.30 per ticket (runs 1-4) |
| 2026-09-12 | verify_rows (free clean-checkout reproduction) before any landing; model verifier only for claims beyond harness lines | verifier re-running harness rows cost more than the worker | verifier cost per ticket | verifier $0.005-0.03 |
| 2026-09-13 | next_ticket.py / land.sh / ticket_result.py / archive_tickets.py replace coordinator turns | coordinator spent ~15 turns per landing on the same steps | coordinator cost per ticket | coordinator < $0.02 per ticket |
| 2026-09-13 | two-worker loop: `**Files.**` lines + `next_ticket.py --pair` | user: parallelize if overhead <= 5% | wall time per ticket, pi spend unchanged | run 4: pairs landed with no conflicts, spend per ticket unchanged |
| 2026-09-13 | loop text: an instruction's ticket list is a hint, never a limit; commits from outside the run are never a stop reason | runs 2 and 3 stopped early (F-list treated as the queue; my commits on main read as a collision) | runs end only when no OPEN ticket is left | run 4 ran through |
| 2026-09-13 | multi-pass tickets are stamped OPEN, never PARTIAL/DONE | F12 closed three times by its worker's stamp | re-open commits by the human | F12 stayed OPEN after the rule |
| 2026-09-13 | AGENTS.md: never commit on main | F20b's worker committed straight to main | main commits by workers | none since |
| 2026-09-13 | land.sh takes a machine-wide lock | Claude agents landing alongside the pi coordinator | corrupted merges | none |
| 2026-09-13 | status CLAUDE for tickets held by Claude agents (pi's queue skips non-OPEN) | the user's Claude quota window; two coordinators over one queue | duplicate dispatch | none |
| 2026-09-14 | tools/check_inputs.sh: verify_rows and land.sh refuse to run when /tmp's real or sterile ROM or the two root save states differ from the backup; restore_inputs copies before checking | a free model under the replay benchmark ran `cp /tmp/after.gba /tmp/bn6f_real.gba` at 06:54 ("swap briefly") and never restored it; the results-screen row then read 58457 and a bisect chased a phantom regression for an hour | measurements against a changed canon: none possible | guard in place; the deferred free-model replays stopped (untrusted models get no further shell access to the shared inputs) |
| 2026-09-14 | verifier dispatched only when the branch merges AND the report claims something verify_rows cannot check; no verifier on harness-only DONEs or on non-landed outcomes without a quoted forward claim and its re-check (auditor proposal docs/audits/20260914-093549.md, item 1) | the ledger showed ~25 verifier dispatches in 24h, most on harness-only F12 namings and on kept/blocked branches | verifier dispatches and verifier $ per landed ticket (from ~25/day, ~$0.30/day) | applied 2026-09-14 09:50, takes effect from run 8; to be read off tomorrow's review |
| 2026-09-14 | Charm Hyper subscription (250 credits/day) in the loop: verifier and recon on Hyper's GLM 5.3 Flash / DeepSeek 4.1 Flash, a worker-hyper role on Qwen 3.8 Flash, the coordinator on Hyper Qwen (BN_COORD_MODEL), three workers in flight (next_ticket --pair 3; roles worker, worker-hyper, worker-hyper) | the user bought a month and wants every daily credit used; the free-tier benchmark was rate-limited before it could judge the models | credits used per day (target 250), cost per landed ticket on OpenRouter (Muse workers only now), pass rate of Hyper workers from the ledger and the replay table | applied run 8 (10:33); the subscription benchmark chain runs in parallel |
| 2026-09-14 | Hyper-only operation: all roles on Hyper, the run stops when the day's credits are gone (hyperwatch), each day's run starts by cron 10:35 (hyper_day.sh); OpenRouter is a reserve | the user: "fully shut down when we run out of credits for the day; OpenRouter spend is reserve, not fallback" | OpenRouter spend per day (target 0), credits used per day (target 250), landed tickets per day | applied run 9 (11:0x) |
| 2026-09-14 | worker-hyper = Hyper GLM 5.3 Flash; verifier = Hyper Qwen 3.8 Flash (cross-family) | replay benchmark under the subscription: GLM passes F18d ($0.33, 16 min) and F25c ($0.42, 13 min); Qwen passes both slower ($0.42/37 min, $0.62/53 min); MiniMax passes both dearer ($1.34, $0.73); Kimi fails F25c; DeepSeek no commit (docs/benchmarks/hyper-2026-09-14-deferred.md) | credits per landed ticket (target <= 9, i.e. $0.45), landed tickets per day | applied 13:20, effective from the next dispatch |

## 2026-09-14 17:00 -- the loop runs without the human session (five gaps closed)

Agreed with the user ("sounds good") after the question whether the setup can run unattended for months.
One structural change per cycle was suspended for this batch because each item is a new mechanism, not a
reshape of a working one:

1. **Ticket supply.** When `next_ticket.py` prints "no OPEN ticket" the coordinator runs `tools/pi_judge.sh`
   (against docs/SCOPE.md) and `tools/judge_append.py`, which admits a proposed ticket only if it has a fresh
   ID, a `**Files.**` line, an acceptance section and a milestone or predecessor reference; the loop
   continues from step 1 when anything was admitted.
2. **Verified partials land.** A branch whose verify_rows PASS shows improvement and nothing worse, with any
   claim beyond harness lines confirmed, lands and is stamped PARTIAL; kept-unmerged is reserved for a
   regression, a refuted claim or numbers that did not reproduce (.pi/coordinator.md).
3. **Watchdog.** `tools/hyper_day.sh` runs from cron every 30 minutes: restores the /tmp inputs from
   /home/box/bn-backup after a reboot, prunes verify checkouts older than a day, and starts the all-Hyper
   run when none is active and at least 100 credits remain (hyperwatch still stops it at exhaustion).
4. **Daily digest.** `tools/digest_post.py`, run at the end of `tools/daily_review.sh` (cron 09:15): one blog
   post per day that had a ticket result or a merge, built from the record (result commits, Result
   paragraphs, new GIFs, the review's scoreboard, spend). A Hyper model may rewrite a Result into one plain
   paragraph; the paragraph is dropped if it contains a number, hex value or path the facts do not.
5. **Auditor proposals in the digest.** The digest lists the headings of any audit proposal from the last
   24 hours under "Setup proposals waiting for a decision"; applying one stays a human decision.

Rule kept: `tools/land.sh` is still the only path to main for agents; the digest commits web/blog under the
landing lock and pushes main and gh-pages itself.

## 2026-09-14 17:30 -- providers.toml: the provider map (the user's request)

The user wants to swap subscription services without rewriting the directions, and to run several providers
serially in a day or in parallel. One config file now maps provider -> role -> model and holds the schedule;
the agent files are generated from role templates (.pi/roles/) by tools/roles.py; pi_coordinator.sh takes
BN_PROVIDER and derives the coordinator model, the instruction (which names the roles per provider), the cap
and the watcher from the map; run_day.sh replaces hyper_day.sh (cron every 30 min), budget_watch.sh replaces
hyperwatch.sh, tail.sh replaces hyper_tail.sh; next_ticket.py --claim keeps two parallel runs off the same
ticket; verify_rows.py takes a machine-wide lock. The judge, auditor and digest read their model from the map.
tools/bench_provider.py replays a fixed F-ticket set with a provider's worker and tables it against the Muse
originals and every other provider's replays, with credits measured by balance delta and priced at the
subscription's rate. No model changed in this reshape; the loop text changed only in how roles are named.

## 2026-09-14 18:00 -- run profiles: joint orchestration across providers (the user's point)

The user: joint orchestration is not a bad idea "if for instance hyper has a good coordinator and minimax
doesnt. just requires some more coordination to make sure both are being used to the max". So the unit in
providers.toml is now a run profile with candidate lists per job from any provider, resolved by budget at each
launch; a run stops when the provider of its coordinator or worker is exhausted and the cron relaunches it
on its fallbacks. Both subscriptions drain: the shared-coordinator run keeps going on its own coordinator
once hyper is spent, and hyper's own run keeps going while hyper has credits. The rendered agent files did not
change for today's run.

## 2026-09-14 19:35 -- two subscriptions in parallel (the MiniMax verdict)

MiniMax's $22 plan was put through its paces: M3 as worker passed 3 of 4 replays at Muse's and GLM's pace
(F25c failed after 366 turns); as coordinator it ran a full cycle correctly on the third launch (T7e landed
1b7187b with verify_rows PASS on every row and its own M2.7 verifier confirming four claims), the first two
launches ending on a judgment call (handed back when the only open tickets were claimed) and on a watcher
bug (hyper's exhaustion killed it by a role-name pattern). The plan refuses bursts long before its windows are
used (error 2062), so pi talks to it through tools/api_pacer.py at 20 requests a minute with retries; and its
weekly window is the binding budget (about 0.7% of the week per ticket cycle against 5% of a 5-hour window),
so tools/minimax_quota.py enforces a daily allowance (weekly remainder at the day's start divided by the days
left) and the run stops for the day when it is spent. Decision: schedule.runs = ["hyper", "minimax"], parallel;
each run self-sufficient; the joint sketch (hyper coordinating minimax's workers) stays a comment -- it is not
needed and would add a fourth hyper session, which trips hyper's hourly limit. Benchmarks are queued ahead of a
provider's run, never beside it.

## 2026-09-15 11:00 -- readable output by Opus; work logs; tmux; the day's other changes

The user rejected the first automated digest ("completely incomprehensible") and set the standard for every
human-readable thing here: understandable by someone who has never looked at the project, the Dolphin emulator's
progress reports as the model, and asked for an Opus 5 writer instead of the worker-class models. So: the digest
and the learn slides are written by Opus 5 through the Claude Code CLI (providers.toml [roundup]); the worker-class
models keep the engine work. Also today: per-ticket work logs (docs/worklog, carried to main on every stamp, shown
to the next worker), runs and benchmarks in tmux with a live view, comment-only assembly notes every morning,
land.sh --no-verify refused for code, the coordinator resuming after an early stop, judge tickets up to 9000
chars, MiniMax's daily allowance and pacer, and both subscriptions scheduled in parallel.
