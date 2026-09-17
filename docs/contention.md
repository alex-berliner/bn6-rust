# Where agents collide, and what stops them

Several agent runs work on this project at the same time, on one machine, against one copy of the
repository. Each run is a coordinator with a few workers, and at any moment six or so of them are
building, measuring and merging. Almost everything they touch is their own; a short list of things is
shared by all of them, and every shared thing is a place where two agents can get in each other's way.

This is that list. For each one: what it is, what going wrong looks like, and what currently prevents
it. It is written to be read by someone who has not seen the machinery before.

A note on the shape of the problem. The runs do **not** duplicate each other's work — of 102 branches
created so far, exactly one ticket has two, and that one is a benchmark that is meant to run twice.
Claims are honoured. What they collide over is shared *resources*, and the damage is waiting, lost
writes and blocked landings rather than wasted duplicate effort.

---

## 1. The one working copy of the repository

**What it is.** Every run does its actual work in its own git worktree under `/tmp/bnwt/`, but all of
them eventually merge into the single checkout at `/home/box/Code/bn`. The morning roundup writes
there too, and so does a human session.

**How it goes wrong.** A merge needs that checkout to be clean. If any tracked file has uncommitted
edits — a rebuilt site manifest, a half-finished source file — every run's landing is refused at once.
One stray file is a machine-wide outage.

**What stops it.** `tools/land.sh` holds `/tmp/bn-land.lock` while it merges, and before merging it
sorts the dirt into two piles. Files that a tool generated (the site captures, the blog, the tool
index, the review, inventory, benchmark and worklog output) it commits itself and carries on. Anything
else — somebody's unfinished source — it still refuses, and it prints the filenames so the refusal is
actionable.

## 2. The merge itself

**What it is.** Two merges into the same checkout at the same moment would interleave and corrupt it.

**What stops it.** The same `/tmp/bn-land.lock`, taken for the whole landing with a 30-minute wait. A
second landing queues behind the first rather than failing. This is working as intended and is not a
bottleneck — the waits are single digits.

**The failure this used to have.** If the merge hit a conflict, the script died part-way through under
`set -e` and left the shared checkout full of conflict markers, which then tripped the dirty-checkout
refusal for everyone until a human cleaned it up. One branch's bad day became every run's. The merge
is now guarded: on conflict it names the conflicting files, aborts the merge, and leaves the checkout
exactly as it was. The branch and its worktree survive, so the work is rebased and landed later.

## 3. `TODO.md`, the ticket list

**What it is.** One file, in that one shared checkout, holding every ticket and its status. Two
different tools rewrite it constantly: `judge_append.py` when a judge admits new tickets, and
`ticket_result.py` when a coordinator stamps a finished one.

**How it goes wrong.** Both do read-modify-write: read the whole file, change a part, write the whole
file back. If two run at the same second, the second one read a version without the first one's change
and writes it back out. The first change is gone, and both processes report success. A whole admitted
batch of tickets could vanish this way, silently.

**What stops it.** Both now take `/tmp/bn-land.lock` across the read-modify-write and hold it through
the commit. Using the *landing* lock rather than a lock of their own is deliberate: it also stops a
stamp from interleaving with a merge that is rewriting the same file.

This one went unnoticed for a while and got likelier on 2026-09-17, when the daily cap on judge batches
went from 12 to 40 and the judge stopped being pinned to a single provider.

## 4. The measurement harness

**What it is.** The tool that runs the game and compares frames against the original. Its numbers are
the project's entire acceptance standard.

**How it goes wrong.** Frame comparisons are timing sensitive. Two running side by side produce numbers
that are not trustworthy, which is worse than producing none.

**What stops it.** `tools/verify_rows.py` takes `/tmp/bn-verify.lock` exclusively and waits if another
verification holds it, printing that it is waiting. These waits are the single largest source of agent
idling, and they are worth every second: the alternative is measurements nobody can rely on.

## 5. Emulator captures

**What it is.** Screenshotting frames out of the emulator, which several processes do at once — the
harness, a verification, a worker's own probing.

**How it goes wrong.** Too many at once and captures come up short under memory pressure.

**What stops it.** A machine-wide semaphore of three slots (`/tmp/bn-capslot-0..2`, `chip_compare.py`),
plus a count check and retry. Three slots on this box let a row's independent captures overlap without
starving each other. The rule used to be "never two at once" and was relaxed once the count check made
short captures detectable.

## 6. The canon inputs in `/tmp`

**What it is.** The original ROM and its save states, which every measurement compares against.

**How it goes wrong.** A model with shell access can overwrite them. One did, on 2026-09-14. Every
measurement taken afterwards would be against the wrong baseline and would look fine.

**What stops it.** `tools/check_inputs.sh` re-hashes each input against a backup outside `/tmp` and
refuses to measure or land if any byte differs. Note that this is *detective*, not preventive: it
catches a clobber rather than preventing one. The preventive half is the standing rule that untrusted
models get no shell access to shared measurement inputs.

## 7. The ticket queue

**What it is.** Several runs drawing work from one list.

**How it goes wrong.** Two runs pick the same ticket and do the same work twice.

**What stops it.** A claim file per ticket under `/tmp/bn-claims/`, written when a run takes a ticket
and ignored once the owning run is dead, so a crash does not strand work forever. Because an expired
claim could let a second run re-pick a ticket whose branch was still in flight, `next_ticket.py` also
refuses any ticket that still has an unmerged branch of its own. Measured result: no duplicated work.

## 8. Ticket numbers at admission

**What it is.** Two judges, running on different providers minutes apart, proposing the next ticket
number.

**How it went wrong.** They picked the same number, and the duplicate was thrown away — along with the
rest of that proposal. Seven of ten refusals at one point were this.

**What stops it.** A proposed ID that already exists takes the next free suffix instead of being
discarded.

## 9. The disassembly

**What it is.** `reference/bn6f`, a submodule. Because a fresh worktree checks a submodule out empty
and re-cloning it per agent is wasteful, every worktree gets a **symlink to the one copy** in the main
checkout instead.

**How it goes wrong.** That single copy is read by every run. A write to it from anywhere lands in
everybody's. And since it is now editable — names and struct fields may be improved as long as the
rebuilt ROM is byte-identical — a bad rename breaks the build for every run at once.

**What stops it.** Four things, and one gap.

- The symlink is marked `skip-worktree`, so a `git add -A` in a worktree cannot stage it over the
  submodule pointer. Without this, merging such a branch turned the submodule into a symlink pointing
  at itself and deleted the disassembly from the main checkout. That happened once.
- Comment-only notes go through `annotate_asm.py`, which refuses if the submodule is dirty, reverts
  any edit that is not comment-only, and now refuses unless the submodule is on the `bn-notes` branch.
  A submodule checkout is detached by default, and committing on a detached head then pushing the
  branch name pushes the *stale* branch and exits successfully — so the roundup reported success while
  the day's work sat unpushed, reachable only by the superproject pointer. That happened on
  2026-09-17 and is how this check came to exist.
- Renames go through `tools/rename_lane.sh`: it takes the landing lock, refuses unless the submodule is
  clean and on `bn-notes`, applies, rebuilds, checks the ROM's sha1 against canon, and reverts
  everything on any failure. The rebuild takes about three seconds, so there is no reason for an
  ungated rename. Its `--self-test` proves the gate still bites rather than trusting that it does.
- Workers are never given a rename to do. It is not part of a ticket's loop.

**The gap.** Nothing *prevents* a worker from writing through the symlink into the shared copy. Nothing
is told to, and nothing does, but the only thing standing in the way is that no instruction asks for
it. `skip-worktree` stops such a change being committed, not being made.

## 10. A run's worktree directory

**What it is.** Each run works in its own directory under `/tmp/bnwt/`, and `land.sh` removes that
directory after it merges the branch.

**How it goes wrong.** Landing another run's finished branch is legitimate — the commits reach main
either way — but removing its *directory* while that run's coordinator is standing in it takes the
ground out from under it mid-turn. On 2026-09-17 the hyper run removed `/tmp/bnwt/t125-fullmap` while
the zai run owned it. The commits survived; the run did not have a working directory any more.

**What stops it.** Before removing, `land.sh` checks whether any process on the machine has that
directory as its working directory, and if so leaves it alone and records an incident. A directory left
behind costs nothing: `run_day.sh` prunes stale ones every tick.

## 11. Build output directories

**What it is.** Cargo builds from several worktrees at once.

**What stops it.** Each worktree exports its own `CARGO_TARGET_DIR=/tmp/ct_<name>`; without it every
build serialises on one lock. The ROM built in a worktree is byte-identical to the main checkout's,
which is verified, so numbers measured in a worktree are directly comparable.

## 12. Benchmark scratch directories

**What it is.** A replay benchmark re-runs an archived ticket with a candidate model and writes its
events to a directory named by a timestamp.

**How it went wrong.** Two benchmark arms started in the same second, shared one directory, and mixed
their events together. Both reports had to be voided: the verdicts were artifacts rather than results.

**What stops it.** The stamp now carries the model's name and the process id as well as the time, so
two arms cannot collide even when started together.

## 13. Provider budgets

**What it is.** Several runs drawing on the same paid plan.

**How it goes wrong.** One run spends the day's allowance in an hour and the rest sit idle, or the
provider rate-limits everyone.

**What stops it.** A pacer in front of each provider, a per-provider daily allowance computed from what
is left in the week, a one-active-run rule for the provider that requires it, and a credits check
before a run launches.

---

## Still open

- **The shared disassembly copy is writable through the symlink** (section 9). No guard, only the
  absence of an instruction to do it.
- **The main checkout is still the merge target.** The real fix is to give landings their own clean
  checkout, so the working area can be dirty without blocking anyone. That is a larger change to how
  merges happen and is deliberately deferred until the current fixes have been watched for a day.
- **`check_inputs.sh` detects rather than prevents** a clobbered measurement input (section 6).
