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
