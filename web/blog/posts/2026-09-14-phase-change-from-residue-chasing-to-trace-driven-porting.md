# Phase change: from residue chasing to trace-driven porting

The rule for the first phase was simple: every existing row at 0 differing frames before any new content. As of today that gate is met for every isolated row but one 8-pixel timing residue, and the whole-screen variants of five rows wait on one thing, the end sequence entering the results screen on canon's frame, which four passes showed has to be ported as one state machine rather than fitted per row.

So the method changes. Building a second virus the way the Mettaur was built would repeat the residue chasing that cost this phase its first two days. Instead:

- **A state-trace harness** (T1): record canon's battle state per frame over whole scripted battles, replay ours on the same inputs, and name the first divergent field and frame automatically, with pixels as the gate on the same recording.
- **Coverage from the disassembly fork's profiler** (T2): the routines canon actually executes per scenario, ranked, so the porting queue comes from what runs.
- **Interpreters before content**: canon's animation bytecode player, object dispatcher and script VMs, each verified by trace. After that, chips, viruses and maps are data from the ROM, and the five viruses and two bosses in scope are the first test of it.

## The workflow that got here

Tickets are written by judgment and worked by a cheap coordinator running two workers in separate worktrees; every branch is reproduced from a clean checkout before it merges, and a model verifier is used only for claims the script cannot check. Landed tickets have cost about $0.17 each on the cheap tier; a one-day burst of stronger agents on the hardest rows landed twelve tickets and found most of the mechanisms in the previous post. A daily review now records cost per landed ticket, the scoreboard and cache health, an auditor proposes changes to the setup when the failure pattern or the phase changes, and a replay benchmark re-runs archived tickets on candidate models before any role changes model (two free models were tried today; neither could hold a task).
