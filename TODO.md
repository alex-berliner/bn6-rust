# Work that can be handed to a subagent

Each entry is meant to be pasted into a ticket more or less as it stands. Anything
without a way to *measure* whether it worked is not ready to hand out — write the
measurement first.

## Every ticket runs in its own git worktree

    tools/worktree.sh <name>

prints a directory, a branch, and the `CARGO_TARGET_DIR` to export. The agent works THERE and
commits to ITS OWN BRANCH; the coordinator merges back with `git merge --no-ff`. Nothing else
gets an agent's half-finished edits, and nobody has to remember not to build at the wrong moment.

Why this exists: on 2026-09-07 four separate incidents came from agents and coordinator sharing
one checkout. A build taken while a worker held `src/` compiled its half-finished file and
returned a normal-looking number; the same collision later made a build fail outright; and I told
a worker its correct measurement was contamination on the strength of one of those numbers.

What the script handles that a bare `git worktree add` does not:
- `reference/bn6f` is a submodule and a fresh worktree checks it out EMPTY. It is symlinked to
  the main checkout, because it is only ever READ -- disassembly comments are made by the
  coordinator in the main tree, so an agent must not commit inside it. The script marks the
  path `--skip-worktree` so that a stray `git add -A` cannot stage the symlink over the
  gitlink -- doing that once merged a self-referential symlink into main and deleted the
  disassembly from the working tree. Agents should stage by path regardless.
- Each worktree needs its own `CARGO_TARGET_DIR` or the builds serialise on one lock. A build in
  a fresh worktree takes about 30 seconds and produces a BYTE-IDENTICAL ROM to the main tree's --
  verified, three ways, so a number measured in a worktree is directly comparable to one measured
  anywhere else.
- Capture scratch paths are keyed on the checkout path by `chip_compare.scratch()`, so two agents
  cannot overwrite each other's packed ROM between its build and its capture. That needed no
  argument and no convention; it just works out.

An agent that commits on its own branch is also free to commit MIDWAY, which the old "never
commit" rule forbade -- and that rule existed only because everyone shared one tree.

## Rules for every ticket

- **Give each agent its own `CARGO_TARGET_DIR`** under `/tmp` (`tools/worktree.sh` prints one). `cargo` locks the shared
  target directory and every build overwrites the same `target/.../bn` that
  `tools/gbafix.py` reads, so two agents building at once will silently pack each
  other's ROM. This has already caused two wrong captures.
  This rule was itself a trap until 2026-09-07: `regress.py`'s `build()` hardcoded
  `ROOT/target/...`, so setting `CARGO_TARGET_DIR` made cargo build in one place and the
  ROM get packed from a stale ELF in another -- no error, just numbers for a different
  build (`mettaur` 95436 instead of 345). It now asks `cargo metadata` where the target
  directory actually is, so the rule and the harness finally agree. Any OTHER script that
  packs a ROM should be checked for the same assumption before being trusted under a
  private target dir.
- **Baseline first.** The agent must record the number with its own script *before*
  changing anything, and re-run the identical script afterwards, and report both. A
  change nobody can show improves a number is not a fix — see 7ah in `TRANSFER.md`,
  where a well-cited change backed by a disassembly line and the animation data turned
  out to move nothing and to be worse on a wider window.
- **Say which window was measured.** Two agents measuring the same residue in different
  frame windows reached opposite conclusions once. Windows go in the report.
- Only `src/` changes unless the ticket says otherwise. Never `tools/`, `reference/`,
  `assets/` or `Cargo.toml` without a reason in the report.
- A precise negative result is a good outcome and gets written into `TRANSFER.md`. A
  plausible-sounding change that does not move the number is not.
- **DO THE WORK YOURSELF.** Do not delegate a ticket onward to a further agent. You
  are the worker. A ticket that turns out to be bigger than it looked comes back as a
  report saying so, not as a subcontract. (Which model runs which role is decided in
  `.pi/agents/` and HANDOFF §13, not by the worker.)

## Rules for whoever is handing the tickets out

Written after breaking all three of these in one evening.

- **Do not build or measure from the tree while a worker holds `src/`.** Not just "do not edit" --
  a build taken mid-edit compiles whatever state the worker's file is in at that instant and gives
  a number that looks completely normal. This produced a `tiles` reading of 3295 and then one of 0
  within the hour, the second being a build with the worker's fix reverted. Reuse an already-built
  ROM from /tmp, or wait.
- **When a worker's number disagrees with yours, rebuild it yourself before contradicting them.**
  On the strength of the above I told a worker its correct measurement was contamination. It had
  done three from-scratch builds and was right. Its EXPLANATION was wrong (it blamed target-path
  length; three target directories, one deliberately long, give a byte-identical ROM) -- but a
  wrong explanation is not a wrong measurement, and the two must be judged separately.
- **`git add -u <path>` limits to that path.** A commit meant to carry the fix, the harness change
  and two write-ups carried only the submodule bump, and the rest sat unstaged behind a clean-
  looking `git status` line. Check `git show --stat` after committing, not just the exit code.

---

## R. Root states as recipes (HANDOFF §13 step 1)

### R1. Rebuild the fixture chain from power-on  *(DONE -- merged fd282eb, 2026-09-12)*

**Why.** `battlestart.state` was lost with /tmp on 2026-09-08. `overworld_net`, `emptyfield_start`
and `chip_ready_empty` are built from it, and the chip/banner/popup rows cannot move off PAUSED's
deleted-enemy artifacts (the shared 14388 baseline) until `chip_ready_empty` exists again. Every
root state should be a recipe: ROM + battery save + inputs from power-on, rebuildable by
`states.py build`.

**Inputs.** `/tmp/bn6f_real.gba` (real ROM) and `/tmp/bn6f_real.srm` (the battery save, 32 KiB,
sha1 e52de245714a...; backed up in /home/box/bn-backup). `mgba_capture --loadsave <srm>` loads the
save read-only and resets the core, so the capture starts at power-on with that save present
(chat history: it reaches the Capcom logo, then the title). Nothing else from the lost states.

**Known anchors (verified by earlier tickets; read their notes in tools/states.py):**
- SubsystemIndex reads 4 on the map, 8 at battle_init, 12 in the battle main loop
  (`emptyfield_start`'s note gives the address it watched).
- Battle frame 0 = `eBGScrollCBCounters` at 0x02009690 / 0x02009694 both 0 (TRANSFER 7aw).
- The encounter roll's gate: one-shot `--poke-at N:0x02001c16:0x2000` and `N:0x02001c18:0` opens
  exactly one roll at frame N. Forcing it EVERY frame freezes GetRNG's draw (the orbit trap,
  HANDOFF §9) -- use one-shot pokes and vary held directions.
- Overworld position: a live u16 pair at 0x02009f62/0x02009f63 moves 1/frame under held Right
  or Down on the net map ('CentralArea1'); 0x02009f5e moves only under Down.
- `tools/mgba_frames.py <outdir> --at <i>` turns a raw frame into a PNG you can look at.

**Do, in order.**
1. **Power-on to the overworld.** Add a `save=` field to `State` in tools/states.py (passed as
   `--loadsave`), then write a recipe from cold boot with `/tmp/bn6f_real.srm` through the title
   and Continue to controllable overworld play. Decide menu presses from RAM where you can
   (SubsystemIndex, a menu/cursor byte you find in the disassembly) and look at a frame only at
   the branch points. Record which area Continue lands in.
2. **To an encounter-capable net area.** If Continue does not land on the net, walk/jack in by
   script. Stop at a state equivalent in purpose to `overworld_net`: SubsystemIndex 4, on a net
   map that can roll random encounters, position counters responding to held input.
3. **A battle's frame 0.** From (2), open one encounter roll with a one-shot poke (sweep the frame
   if the first choice fails) and build to the frame where the scroll counters read 0/0. This is
   the new `battlestart`. It is a DIFFERENT fixture from the lost one unless it rolls the same
   encounter (three Mettaurs); record which EnemySetupArr entry it rolled, and do not claim
   equivalence you have not measured.
4. **Re-root the chain.** Point `overworld_net`, `emptyfield_start` and `chip_ready_empty` at the
   new states (rebase `emptyfield_start` directly on (2) if that is simpler than going through a
   resolved battle). The downstream recipes' frame numbers WILL change -- re-sweep them and
   re-verify every property their notes document: SubsystemIndex 12 held through the capture, all
   enemy HP 0, scroll counters 0/0 at battle frame 0, the chip window opening on its own, a chip
   in hand, MegaMan idle (CurState/CurAction 4,8) at load of `chip_ready_empty`.
5. **Determinism.** For each new or changed state: build it twice from scratch and capture 40
   frames from each build; the frames must be identical (this is how `result_arrival` was
   verified).
6. `python3 tools/states.py build all` builds every state except `noenemy2` with nothing but the
   ROM and the save. `battlestart` stops being a root.

**Out of scope.** Re-pointing any harness row (next ticket), `src/`, `noenemy2` (its reward roll is
unrecoverable by recipe), patching encounter-table entries (HANDOFF §9: it changes which entry a
roll selects).

**Measure and report.** For each state: its recipe (base, save, script, pokes, frames), every RAM
property you verified with the address and value, the determinism result, and the build time.
Then the report shape in AGENTS.md. A step that fails is reported with exactly what was observed,
not worked around.

### R2. Move the chip rows onto the never-had-an-enemy fixture  *(NEGATIVE -- 2026-09-12, rows not moved)*

**Result.** At the event-pinned alignment (canon CurState leaves 0x0804 at frame 3; shot flight canon
19-28 <-> rust 137-146, identical per-frame cadence) the empty route reads 134535 / 5317 / 40 against
the PAUSED baseline 14388 / 2350 / 40. The residue (diffmask worst frame, canon frame 17) is two of the
three Mettaurs mid-dissolve on the right of the field plus the chip-window strip at top left: the
"empty" state is spawn-and-delete (DELETE_ENEMY_3 from load), the death presentation is deferred while
the chip window is open, and it plays across exactly the frames the chip action occupies. The old
43700-44631 plateau was a false-alignment family with a 49-frame period. Measured and rejected:
per-frame zeroing of BattleObject identity (the ROM freezes), `zero=ENEMY_TILES` (120498), seven
script variants (nothing moves the transient; a chip after the dissolve is refused, HANDOFF §9).
Also found: the rust side's shot fires ~33 frames after marker + fire_frame, not at it. GLM-5.3-Flash
worker, 69 turns, $0.098. The ticket as first written follows.

**Why.** Every chip row compares against canon (sterile) loaded from PAUSED, whose leftover
portrait box and Mettaur corpse cost each row the shared 14388/2350 baseline (see ALIGN_CHIP's
comment in tools/harness.py). R1 rebuilt `/tmp/chip_ready_empty.state` (a battle that never had a
live enemy; MegaMan idle, Vulcan1 in hand; `states.py build all` makes it). tools/harness.py already
has the canon side for it, `_chip_canon_empty()` and `library_pokes_empty()`, NOT wired into any
row: the last attempt (read the "NOT WIRED" comment block) searched alignments and plateaued at
~43700-44631 px from two offsets 49 frames apart -- a false alignment or a real residue, never
settled -- which is worse than 14388, so it was left unwired.

**Do, in order.**
1. **Baseline.** `python3 tools/harness.py --only chip-cannon --no-gallery` (expect 14388 / 2350 / 40,
   negative not blind). Then score `_chip_canon_empty("01")` against `_chip_rust("01")` at the old
   plateau alignment on the NEW state, and record that number too.
2. **Pin the alignment by event, not by search.** On the canon side, watch MegaMan's
   CurState/CurAction (0x0203a9b8; idle reads 0x0804) with `--watch` from load under the row's own
   script, and find the frame it leaves idle for the chip action -- that frame (plus whatever fixed
   lead the chip's first visible frame has) is `canon_ref`, measured and written into the Align
   note. On the rust side, the marker origin plus the descriptor's `fire_frame` gives the matching
   frame; use the existing search band only to CONFIRM a unique minimum there, not to find it.
3. **Localize what is left** at that alignment: per-frame totals, and the region of the differing
   pixels (tools/diffmask.py) -- which sprite, which frames. If the residue comes from the two
   fixtures disagreeing (MegaMan's position, HP, palette, a HUD element, the chip in hand), fix the
   rust DESCRIPTOR or the canon Side's pokes so both sides show the same situation, citing the RAM
   value you matched. If it comes from how src/ draws or times something, stop fixing and report it
   with frame and region -- that is a src/ ticket.
4. **Move the rows.** Only if `chip-cannon` on the empty route reads BELOW 14388 with its negative
   not blind: point the shared chip template at the empty route, run every chip row one at a time,
   and report each row's before and after. A row that gets worse stays on PAUSED, with its numbers
   in the report. Then banner and popup, if they can use the same state.

**Rules.** tools/ only (harness.py, and states.py only if a recipe needs a tweak); no src/; never
widen tools/allowlist.py; every changed row keeps a non-blind negative; captures one at a time.

**Measure and report.** The alignment evidence (the RAM watch frames on both sides), the residue
breakdown with frames and regions, every row's before/after line, and the AGENTS.md report shape.

### R3. A battle that never spawns an enemy  *(PARTIAL -- 2026-09-12, branch wt/r3-empty kept, not merged)*

**Result.** The roll's choice lands in `GameState->CurBattleDataPtr` at `0x02001b9c` (stored at
asm29.s:10286, read by `sub_800531C` asm00_1.s:4455). One-shot pokes `70:0x02001b9c:0x4b88` and
`70:0x02001b9e:0x080b` (the roll writes at frame 60, battle_init reads at 76) retarget the battle to
BattleSettings `0x080b4b88`, whose EnemySetupArrPtr is the emptied entry: no enemy BattleObject ever
populates, SubsystemIndex 12, deterministic over 40 frames. BLOCKED: about 20 battle frames in
(capture frame 99) SubsystemIndex goes 12 -> 16, the battle and game state pointers clear, a cutscene
is populated and input goes inert; a no-op poke of the roll's own entry survives 130+ frames, so the
empty enemy list is the cause. Excluded: BattleTerminate01 (0x02038161, stays 0), dispatch_803C620,
the six warp functions, checkCoordinateTrigger_8031a7a, EVENT_16F1, hand contents. Not merged: the
branch replaces R1's working emptyfield_start/chip_ready_empty recipes with ones that cannot finish.
GLM-5.3-Flash, 193 turns, $0.369. Follow-up recon (DeepSeek V4.1 Flash, $0.068):
`docs_recon_teardown.md`. The ticket as first written follows.

**Why.** R2 showed every "empty" canon state so far spawns an encounter and forces its HP to 0, and
the real ROM then plays the enemies' death presentation across the chip rows' frames. The chip rows
need a canon battle whose encounter has no enemy objects at all. `patch_sterile.py
--empty-net-encounter` already empties one table entry (EnemySetupArr `0x080b5306`) in
`/tmp/bn6f_sterile_emptynet.gba`, but no roll has ever landed on it: HANDOFF §9 records that patching
an entry changes which entry a roll selects, and a sweep of one-shot roll frames never reached it.

**Do, in order.**
1. **Find where the selection lands.** In reference/bn6f, follow the encounter roll
   (`sub_80AA4C0`, its `bl GetRNG` at 0x080AA51E, TRANSFER 7aw) to the RAM location that holds the
   chosen EnemySetupArr pointer (or index) that battle_init reads. Cite file:line.
2. **Make the battle use an empty entry, by the smallest change that is honest about itself.**
   Either (a) a one-shot `--poke-at` of that RAM value, applied after the roll writes it and before
   battle_init reads it, or (b) a code patch added to the emptynet ROM variant only (a new
   patch_sterile.py option, documented like the existing two) that makes the selection return the
   emptied entry. Prefer (a) if a poke window exists; do not change what canon or canon (sterile) are.
3. **Prove it is empty.** At the new battle's frame 0 and 100 frames later: no BattleObject slot for
   an enemy is populated (read the slots; show a frame), SubsystemIndex 12 is held, and a chip picked
   through the window FIRES (the premise that makes the chip rows work -- HANDOFF §9 says a chip fires
   in a battle that never had an enemy).
4. **Rebuild the chain on it:** `emptyfield_start` and `chip_ready_empty` (recipes in tools/states.py,
   no DELETE_ENEMY cheats needed any more), each built twice and 40 frames compared for determinism.
5. **Re-run R2's measurement** on the new `chip_ready_empty`: event-pinned alignment exactly as R2
   did it (its method and numbers are in R2's result above), `chip-cannon` on the empty route vs the
   PAUSED baseline 14388. If it is lower with a non-blind negative, move the chip template and report
   every chip row before/after one at a time; rows that get worse stay on PAUSED.

**Rules.** tools/ only; no src/; reference/bn6f is read-only (report addresses, the coordinator
annotates); never widen the allowlist; captures one at a time.

**Measure and report.** The RAM location and the disassembly lines that prove it, the chosen method
and its window, the emptiness evidence, determinism results, and R2's measurement redone.

### R4. Keep the enemy-less battle alive, then finish R3  *(BLOCKED -- 2026-09-12, branch wt/r4-alive kept)*

**Result.** Step 1 done, and it overturns the recon: none of the five literal `SubsystemIndex=0x10`
stores, the warp entry, `cs_warp_cmd` or the script byte-writer is hit at the teardown frames, and
R3's "12 -> 16" was freed-heap fill (0x11/0x22 patterns), not a mode switch. The never-spawn battle
is healthy through the chip window (opens at battle age ~91, BattleState.Index_01 = 8); at age ~102
the game RELEASES the battle -- CurBattleDataPtr (0x02001b9c) clears one frame before
BattleStatePtr/GameStatePtr -- and dispatch stops. BattleTerminate01 stays 0, BC30 stays 0,
`HandlesBattleMain`'s write-0 never fires. Holding GameState[0..3], the alive counts
(BattleState+0x12/13) or the three pointers does not keep it alive. The deciding store runs through
indirect dispatch and `--trace-pc` perturbs this game's timing, so it is unidentified. Details
appended to docs_recon_teardown.md. GLM-5.3-Flash, 129 turns, $0.228. The ticket as written follows.

**Start from R3's branch:** `bash tools/worktree.sh r4-alive`, then in that worktree
`git merge --ff-only wt/r3-empty`. R3's result above and `docs_recon_teardown.md` are your context.

1. **Confirm the teardown path, do not guess it.** The recon's candidate chain (unverified): battle
   ends through `sub_8007850`'s BC30-jump-offset branch (asm00_1.s:9466) -> EnterMap -> a map cutscene
   whose `cs_warp_cmd_8038040_2 byte1=0x0` calls `warp_setSubsystemIndexTo0x10AndOthers_8005f00`,
   whose `strb` at asm00_1.s:5939 writes 16. Use `mgba_capture --trace-pc <addr> --trace-steps N`
   (HANDOFF §5; bounded steps only) on each link, on R3's retargeted battle, and report which
   addresses are hit on which frame. Find the EARLIEST decision point that differs from a battle with
   enemies (R3's no-op-poke control is the comparison).
2. **Intervene at that earliest point, minimally and visibly.** A held RAM value or a one-shot poke if
   one works; otherwise a new `patch_sterile.py` option applied to the emptynet ROM variant only,
   documented like the existing patches (address, original bytes, new bytes, why). Canon and canon
   (sterile) do not change. Show the battle then stays in SubsystemIndex 12 for 600+ frames with the
   chip window opening on its own and a picked chip FIRING.
3. **Finish R3's steps 4-5:** add the never-spawn chain as NEW state names (keep R1's
   `emptyfield_start`/`chip_ready_empty` working and unchanged -- `states.py build all` must still
   build everything it builds today), determinism twice each, then R2's event-pinned measurement of
   `chip-cannon` on it vs the PAUSED baseline 14388; move the chip template only on a real
   improvement with a non-blind negative, every chip row before/after.

**Rules.** tools/ and docs only; no src/; reference/bn6f read-only; captures one at a time.
Report addresses hit, the intervention with its evidence, and the measurements, in AGENTS.md shape.

### R5. A write watchpoint in the capture tool, then find what releases the empty battle  *(PARTIAL -- 2026-09-12, tool merged, release unattributed)*

**Result.** Step 1 done, verified, committed (17dc00f, plus HANDOFF §5 row). `--watch-write addr[:len]`
arms real libmgba byte-granule WATCHPOINT_WRITEs via `mDebuggerAttach` + `platform->setWatchpoint`
(DEBUGGER_CUSTOM is unbuildable through `mDebuggerCreate` -- returns NULL -- so the tool builds the
`struct mDebugger` and attaches it directly); the entered hook logs frame/addr/old->new and the
writing instruction (`_ARMPCAddress`, r15 minus the ARM/Thumb prefetch offset) plus raw r15 and LR,
then returns -- the emulator never pauses. Verified: known-write anchor hit (roll's
`str r0,[r7,#oGameState_CurBattleDataPtr]`, asm29.s:10286, reports `at=0x080AA59E lr=0x080AA6F9`
frame=60, old=0x00000000 new=0x080B4BB8); new binary vs old binary 0 differing frames (90/90,
emptynet roll recipe); with vs without the flag 0 differing frames (90/90; also 179/179 on a second
recipe); harness `--only wave` with the new binary at /tmp/mgba_capture: PASS total 0 worst 0
frames 90, negative not blind (3840) -- identical to the pre-change baseline line. Tool-side
`--poke-at` writes are caught too but report the CPU's stale r15 as `at` (they run between frames).

Step 2 measured, with a negative at its core. Reconciled frame bases first: R4's "age ~102" and R3's
"capture 99" are the same event -- in the live emptynet recipe (overworld_net base, script, pokes at
60/70; emptyfield_start.state is recipe frame 79 = battle age 0) the release is at **battle age 99 =
capture frame 178**, measured three ways (per-frame value dumps, watchpoint hits, frame hashes).
At 178 the five watched words (0x02001b9c CurBattleDataPtr, ba0, ba4, ba8, bac) clear **in one
frame**, and 0x02001b80..b98 become the freed-heap nibble fill (0x11/0x22 patterns) R4 saw -- the
GameState heap block is released at age 99. But the writes produce **zero watchpoint hits** although
the same watches are live in the same frame (a DISPCNT store at 0x08001760 fires at 178; CPU stores
fire at frames 60/70/76/147; a forced DMA3 fill fires; `--poke-at` fires). Excluded as the writer:
CPU str/strb/strh/stm (all shimmed per mgba 0.10.2 memory-debugger.c), DMA (goes through
`cpu->memory.store32`, proven by experiment), SWI RegisterRamReset (no SWI in the frame-178 delta;
IWRAM body not memset; DISPCNT not forced to 0x0080), CpuSet/CpuFastSet (no dest 0x02001bxx in the
logged frame-178 SWI set; HLE runs real BIOS-stub code through shimmed stores). The CPU stays
healthy (normal per-frame SWI cadence, screen updating). So the release write does not go through
any path libmgba's shims can see -- R4's "indirect dispatch" is real: **no game instruction can be
named for the release with this instrument; the writer is somewhere inside libmgba 0.10.2's
non-store paths** (next step: a libmgba built with a guard on `gba->memory.wram` writes, or bisect
mgba internals). Two further findings recorded in docs_recon_teardown.md: (a) the /tmp pre-states
(emptyfield_start, r4_pre*) DERAIL -- PC walks into 0xDE31xxxx garbage -- when loaded directly and
run past battle age ~68, identically on the old and new binary, while live runs continue healthy:
savestate reload is not faithful for this scenario, so state-based probing past age ~68 is unsafe;
(b) R3/R4's reported teardown ages (20-23) did not reproduce in these live runs (pointer block
intact through age 41 with and without the ALIVE cheats); treat the age-99 event as the only
reproducible release in the merged branch's recipe. Steps 3-4 are therefore blocked on naming the
writer from the emulator side. GLM, one session; /tmp/mgba_capture now runs the r5 binary
(backup: /tmp/mgba_capture.bak_r5). The ticket as written follows.

The empty-battle objective R3-R5 is closed per the 2026-09-12 decision; chip rows stay on the PAUSED baseline.

**Why.** R4 narrowed the enemy-less battle's teardown to one event -- `CurBattleDataPtr` (0x02001b9c)
cleared at battle age ~102 -- but could not see which instruction does it: the store is reached by
indirect dispatch, and `--trace-pc` single-steps, which perturbs this game's timing. A watchpoint
fires at full speed and names the writer directly. It is also the base of the state oracle
(HANDOFF §13 step 3): "which instruction wrote this field, on which frame" is attribution for free.

1. **Tool.** Add `--watch-write addr[:len]` (repeatable) to tools/mgba_capture.c using libmgba
   0.10's debugger (`/usr/include/mgba/debugger/debugger.h`: `mDebuggerCreate`/`mDebuggerAttach`,
   `platform->setWatchpoint` with `WATCHPOINT_WRITE`, an `entered` callback that logs and returns to
   RUNNING, frames driven by `mDebuggerRunFrame` or equivalent). Each hit prints one line: frame,
   address, old -> new, and the writing instruction's address (account for the ARM/Thumb pipeline
   offset in r15; print LR too). Must not change emulation: a capture with a watchpoint set must be
   frame-identical to one without. **Verify on a known write:** the roll's store of the chosen
   BattleSettings to 0x02001b9c (asm29.s:10286 per R3) must report that instruction's ROM address.
   Document the flag in HANDOFF §5's table.
2. **Use it** on R3/R4's never-spawn battle (branch wt/r4-alive has the recipe): watch 0x02001b9c and
   the BattleStatePtr/GameStatePtr words around battle age 90-110; name the clearing instruction,
   then walk the LR chain up to the decision that differs from R3's control battle. Cite
   reference/bn6f file:line for each frame of the chain.
3. **Intervene at that decision,** minimally (held RAM value, one-shot poke, or an emptynet-only
   patch_sterile.py option documented like the others), and show 600+ frames of a live battle with
   the chip window opening on its own and a picked chip firing.
4. **Then R4 step 3** (new state names, R1's chain untouched, determinism twice, R2's event-pinned
   measurement of chip-cannon vs 14388; move the chip template only on a real improvement).

**Start from** `bash tools/worktree.sh r5-watch`, then `git merge wt/r4-alive` in it. **Rules:**
tools/ and docs only; no src/; reference/bn6f read-only; captures one at a time; the capture tool
must still build with `gcc tools/mgba_capture.c -o /tmp/mgba_capture -I/usr/include -lmgba -lm`
and every existing flag must behave as before (run `harness.py --only wave` with the new binary).

### R6. The state oracle: first divergent field, not just a pixel count  *(NEGATIVE -- 2026-09-12, measurements valid; acceptance false, branch not merged)*

**Result.** On `wt/r6-oracle` at `c504eee`, the export was pixel-neutral: `wave` 0/0/90 (negative 3840), `window` 0/0/16 (81056), `mettaur` 30864/1566/70 (45233), and `card` 18486/3081/16 (15405), unchanged from `b600251`. The verifier reproduced every number and CONFIRMED the oracle findings: `mettaur` first diverges at `mm_timer` k=0 on the same frame as its first 959-pixel diff; pixel-clean `wave` nevertheless has real state divergences at enemy animation k=24, MegaMan hit state/timer k=43, and enemy state/action k=64. It therefore FAILed the ticket: wave's required no-divergence claim is false, the requested canon battle-frame/action-timer field set is incomplete, several fields are info-only, the block is before rather than after the descriptor, the complete per-field table is missing, and project-local constants have invalid `provenance: derived` tags. Nothing was merged; `/tmp/bnwt/r6-oracle` was removed and branch `wt/r6-oracle` kept. Worker `openrouter/z-ai/glm-5.3-flash:high`: 146 turns, $0.3061; verifier `openrouter/openai/gpt-5.6-sol:high`: 35 turns, $1.0725. The verifier CONFIRMED that a second state-oracle pass may build on the measured divergences, but not that shot/dwell behavior is ready to change.

**Why.** A harness row says how many pixels differ, not which variable went wrong on which frame, so
every timing residue (MegaMan's hit/dwell timing in `mettaur`, the shot dwell gap, `card`'s cursor)
has cost several attempts of guessing. HANDOFF §13 step 3. The empty-battle objective (R3-R5) is
closed without a fix; the chip rows stay on the PAUSED baseline for now, documented, not hidden.

**Do, in order.**
1. **Pick the field set** (start small; every field needs a canon address AND a rust equivalent):
   the RNG word (0x020013f0, HANDOFF §9); MegaMan's BattleObject -- CurState/CurAction (0x0203a9b8),
   panel X/Y, HP, and the animation/action timer that drives hit and shot timing; the first enemy
   slot's state/action and HP (slot at 0x0203aa88); the custom gauge value; the battle frame counter.
   Take offsets from reference/bn6f/include/structs/BattleObject.inc and cite each.
2. **Rust export.** In src/, write those fields every frame into a fixed EWRAM block right after the
   descriptor (the marker is at 0x02000000, the descriptor at 0x02000040 for 64 bytes; see
   src/main.rs's comments on how BATTLE_MARKER is pinned, and pin the new block the same way),
   converted to CANON's units and encodings (a field map, documented next to the block). This must
   not change pixels: `wave` still PASS 0/90, `window` still PASS 0/16, and every other row you run
   reads the same number as before. Constants get `// provenance:` tags.
3. **tools/oracle.py `<row>`**: capture both sides of a harness row with `--watch` on the canon
   addresses and on the rust block, align with the row's own Align (reuse harness.py's machinery),
   and print the first frame where each field diverges, plus a per-field table. **Negative control**
   (AUDIT pair 10): the same comparison shifted by one frame must report a divergence, or the
   oracle is BLIND on that row.
4. **Acceptance.** `oracle.py wave` reports no divergence on every field both sides model over the
   compared frames. `oracle.py mettaur` reports a first divergent field and frame, and that frame is
   consistent with the first non-zero frame of the row's pixel diff (report both). Document the
   command and the field map in HANDOFF §3.

**Rules.** src/ changes only for the export block (no behaviour change); tools/ and docs; never
widen the allowlist; captures one at a time. **Report** the field map with sources, the before/after
lines of every row run, both oracle outputs with their negative controls, in AGENTS.md shape.

### R7. Land the state oracle on the facts R6 found  *(DONE -- 2026-09-12)*

**Result.** Merged `a9d08b7` as `2b35d4b`. The verifier PASSed all numbered acceptance and CONFIRMED behavior neutrality: `wave` 0/0/90 (negative 3840), `window` 0/0/16 (81056), `mettaur` 30864/1566/70 (45233), and `card` 18486/3081/16 (15405), all unchanged. Independent raw-watch parsing CONFIRMED `mettaur` first diverges at `mm_timer` k=0 with 959 first-frame pixels, while pixel-clean `wave` first diverges at enemy animation k=24, MegaMan state/animation/timer k=43, and enemy state/action k=64. It also CONFIRMED the complete field classifications, populated enemy slot `0x0203ab60`, linker-safe chosen export range `0x02000008..0x0200002f`, honest provenance labels, unsupported-row failures, and shifted-control sensitivity. The worker's two field-specific shifted-control descriptions were REFUTED (the controls changed divergence frames/counts, not RNG or enemy X); those claims are not carried forward. `cargo build --release`, Python compile checks, capture-tool compilation, and `python3 tools/states.py build all` passed. Worker `openrouter/z-ai/glm-5.3-flash:high`: 49 turns, $0.0639; verifier `openrouter/openai/gpt-5.6-sol:high`: 39 turns, $1.2914. Per HANDOFF §13 the next permitted objective is usage logging, not behavior changes.

**Why.** R6's measurements and localization were independently reproduced, but its acceptance asked a
pixel-clean row to have state parity and required canon fields that do not exist. Its implementation
also missed several mechanical requirements. HANDOFF §13 still requires a usable state oracle before
usage logging or behavior tickets. This is the second and last attempt on that objective.

**Do, in order.**
1. Start with `bash tools/worktree.sh r7-oracle`, then cherry-pick R6's implementation commits
   `325581f`, `185f352`, and `c504eee`. Treat R6's measured divergences as tests, not as behavior to
   fix. Audit the diff against this ticket before changing it.
2. Make the field contract honest and complete. For every requested R6 field, cite the canon address
   and Rust source/encoding, or print `unsupported` with the evidence R6 established. A canon battle
   frame and the enemy's timing countdown are unsupported; do not invent equivalents. Distinguish
   parity fields from information-only fields, and print every field in the per-field table even when
   it matches. Keep the verified populated enemy slot `0x0203ab60`; document why `0x0203aa88` is empty
   for these PAUSED fixtures.
3. Keep the behavior-neutral export in a demonstrably free fixed EWRAM block next to the marker. R6
   found that `0x02000080` collides with agb's `SPRITE_LOADER`; use the verified-safe
   `0x02000008` marker padding unless a linker-map proof finds a safer adjacent address. Correct every
   stale address in code and docs. Canon-derived constants need exact ROM/disassembly provenance;
   freely chosen project protocol/layout constants must be labelled as chosen, not falsely
   `provenance: derived`.
4. Make `tools/oracle.py <row>` print the full field table and a first-divergence summary. Its negative
   control must prove sensitivity by changing the nominal result when shifted one frame; merely seeing
   any divergence on an already-divergent nominal row is BLIND. Support `wave` and `mettaur`; fail
   loudly on unsupported rows. Document the command, block layout, comparison contract and unsupported
   fields in HANDOFF §3a.
5. **Acceptance.** Baseline first, then final: `wave` remains 0/0/90 with negative 3840, `window`
   0/0/16 with 81056, `mettaur` 30864/1566/70 with 45233, and `card` 18486/3081/16 with 15405.
   `oracle.py mettaur` reports `mm_timer` k=0 and the same frame's 959-pixel first diff.
   `oracle.py wave` reports pixel total 0 while showing enemy animation k=24, MegaMan hit
   state/timer k=43, and enemy state/action k=64. One-frame shifted controls must measurably alter
   those outputs. If any verified value changes, report it precisely rather than fitting alignment or
   changing behavior.

**Rules.** src/ only for the export block and conversions; no battle/animation/timing behavior change;
tools/ and HANDOFF.md; no canon, state, recipe, allowlist, alignment, region, asset, or Cargo changes;
captures one at a time. **Report** changed paths, the full sourced field map, before/after harness
lines, both complete oracle tables and shifted controls, in AGENTS.md shape.

### R8. Usage logging: primitive profiles for the 43-chip corpus  *(WITHDRAWN -- 2026-09-12, no worker ran)*

Opened by the pi coordinator from HANDOFF §13 step (4), which meant logging TOKEN SPEND per ticket
and role, not instrumenting the game's battle primitives. Withdrawn by the Claude Code coordinator
before any worker ran; the pi coordinator had already stopped itself on its $3 child-spend cap. Spend
accounting comes from pi's session files and `subagent-artifacts/*_meta.json`; a ledger script is a
small coordinator chore, not a ticket.

## F. Convergence: every existing row to 0 differing frames before anything new (user, 2026-09-12)

Tickets run in this order; the coordinator takes the first OPEN one. Queue by leverage, from the
2026-09-12 full table (isolated unless noted): F4 opening 1160 (was 0) -> F5 the chip-row fixture
(28 rows at exactly 14388, 11 more above it) -> F6 tiles/gauge 538 (one capture, two rows) -> field
1048 -> banner 2248 -> buster 3172 -> warp 9198 -> card 18486 -> mettaur 31075 -> F3 (the chip window's
ghost; adds its row) -> popup 107511 -> result 497967 -> cursor 620802 -> the integrated variants.
No new content (viruses, bosses, chips) until the table is at zero. A reported 0 always says what it
compares: canon vs ours, or before vs after.

### F1. MegaMan takes a hit one frame late  *(DONE -- merged d3f25e1, 2026-09-12; mettaur residue moved to F2)*

**Why.** The state oracle (R7, `tools/oracle.py`) localizes the `mettaur` row's 30864 px -- HANDOFF
§10 already says that residue is entirely MegaMan's side -- and shows the same defect hidden on the
pixel-clean `wave` row: canon enters MegaMan's hit state at wave k=43 (state/action (4,3), timer 22,
HP 60 -> 50), our ROM one frame later at k=44 (HP 90 -> 80). On `mettaur` the first divergent field is
`mm_timer` at k=0 (canon 7, rust 0, 7/70 frames), the same frame as the row's first 959 px.

**Do, in order.**
1. **Baseline:** `python3 tools/oracle.py wave` and `python3 tools/oracle.py mettaur` (record both
   tables and negative controls) and the rows wave, window, mettaur, card, field, cannon (record every
   line). This is the before.
2. **The fixture half.** FIELD_ROW in tools/harness.py (the descriptor `wave` and `field` use) gives
   MegaMan 100 HP; canon's state holds 60 before the hit. Peek canon's value, set the descriptor to it
   with a `peeked` provenance note, and show that no pixel row changes (HP is not drawn in `wave`'s
   BG2-only comparison -- prove it rather than assume it).
3. **The timing half.** Find where canon decides a hit lands and enters the flinch on the SAME frame
   (the hit/collision resolution and `object_subtractHP` asm00_2.s:23756, flinch asm00_2.s:18294 --
   src/actor.rs's `take_damage` cites both; use `--watch-write` on MegaMan's CurState/CurAction
   0x0203a9b8 and HP to name the writing instructions and their order within the frame). Compare the
   order of operations in our battle update (src/battle.rs / src/actor.rs): which step runs a frame
   later. Fix the order in src/, citing the asm lines.
4. **Acceptance.** `oracle.py wave`: MegaMan's state/action, anim and timer no longer diverge at k=43
   (report any remaining divergence exactly). `oracle.py mettaur`: `mm_timer`'s divergence count and
   the row's pixel total both fall; report the new first divergent field. wave and window still PASS 0
   with non-blind negatives; card unchanged; every other row reads the same or lower -- a row that gets
   worse is reported with its numbers, not hidden. Negative controls still change the result.

**Rules.** src/ for the timing fix, tools/harness.py for the descriptor value only; no allowlist
change; no alignment or region change; captures one at a time. **Report** the watch-write evidence of
canon's in-frame order, the src/ change with asm citations, both oracle tables before and after, every
row's before/after line, in AGENTS.md shape. **Coordinator:** this ticket changes Rust; if the first
attempt ends PARTIAL, dispatch the second attempt with `model: "openrouter/openai/gpt-5.6-sol"`.

**Result.** PARTIAL; branch `wt/f1-hitlate` is retained unmerged at `fc0065f`. Clean detached
`verify_rows.py` PASS reproduced wave 0/0/90 (negative 3840), window 0/0/16 (81056), mettaur
30864/1566/70 (45233), card 18486/3081/16 (15405), field 1048/177/40 (1225), and cannon
14388/2350/40 (21543). The hop-frame change took wave's MegaMan state/action, animation, panel and
timer oracle mismatches to zero, but mettaur stayed 30864/1566 with `mm_timer` different on 7/70,
so acceptance was not met. The Sol verifier REFUTED the report's commit attribution and claimed canon
operation order (`9276015` is the HP fixture, `fc0065f` the timing fix, and canon writes HP before
flinch state/timer), while supporting the substantive hop-frame fix and unchanged lethal structure;
it REFUTED describing the HP fixture as publication-only/input-neutral because 100 -> 60 changes the
initial emulation state, although the reproduced wave/mettaur pixels were neutral. It CONFIRMED the
blocker: both attack cycles are 106 frames, the permitted 295..324 pairing compares incompatible
120-frame mercy histories, and the equivalent object-phase minimum is offset 203 outside the band.
The generic travelling-shot/lethal paths remain a regression risk; the workers' all-67-rows and
integrated-field assertions were outside the independent row reproduction. Worker 1 used
GLM-5.3-Flash high, 137 turns, $0.240187875; required worker 2 used GPT-5.6-Sol high, 20 turns,
$0.836421800; verifier used GPT-5.6-Sol high, 26 turns, $1.383901000; children total $2.460510675.

### F2. The mettaur row compares the wrong Mettaur attack  *(DONE -- merged 332e658, 2026-09-12)*

**Why.** F1's verified finding: both sides run the same 106-frame Mettaur attack cycle (canon attack
animations start at canon frames 32, 138; ours at battle frames 95, 201, 307, 413). The row's Align
(canon_ref 140, search band 295..325, chosen offset 309) pairs canon's SECOND attack with our THIRD.
Canon's MegaMan is still in the 120-frame mercy from the hit at canon frame 114 (the first attack);
ours took its first hit at battle frame 176 and its third-attack wave falls outside that mercy, so the
two sides are in different situations for the whole window. An equivalent object-phase minimum exists
at offset 203 (second attack <-> second attack), outside the band.

**Result.** DONE and merged as `332e658`; implementation commit `c335e49`. Events
measured from `--watch` captures of the row's own sides: canon attack anims start at
canon frames 32 and 138, MegaMan hit at canon frame 114 (HP 60->50, 120-frame mercy,
next hit 234); rust attack anims at battle frames 95, 201, 307, 413 (capture = battle +
8, marker origin 8), hit at battle 176 (HP 60->50, next 388). Both attack-2s fire
inside the attack-1 mercy, so attack 2 <-> attack 2 is the event pairing; with
canon_ref=140 unchanged, rust attack-2 start (capture 209) gives offset 203. The band
was re-centred to range(193,214) and CONFIRMS a unique V-minimum exactly at 203 (202:
47063, 203: 31075, 204: 37873 over 70 frames). The old offset 309 scored 30864 --
LOWER, and not chosen: it pairs incompatible attack indices (canon attack 2 vs rust
attack 3, different mercy situations). After: 31075 / 1566 / 70, negative not blind
(46554); oracle at the new pairing: mm_timer first divergence k=0 canon=7 rust=6
(the known 1-frame-late hit -- rust's hit capture 184 pairs with canon 113 vs canon's
own 114), 7/70 frames; enemy_anim k=61 1/70; everything else matches 70/70; the
shifted control changes the result (mm_timer 7 -> 0 frames). The residue is MegaMan's
mercy blink phase, 766-px chunks, worst frame k=11 (1566 px), region x 1..77 y 70..113
-- src/ territory, unchanged by this ticket. The row's total moved 30864 -> 31075
(+211): the ticket predicted this may not go down, and the score is not the criterion
-- the pairing is. Clean detached `verify_rows.py` PASS reproduced mettaur
31075/1566/70 with non-blind negative 46554, and `states.py build all` passed. The Sol verifier
CONFIRMED all three claims: offset 203 is attack 2 <-> attack 2 with equivalent 120-frame mercy
history and is derived from events rather than score; old 309 is attack 2 <-> attack 3 with
incompatible histories while 203 is the unique minimum in 193..213; and timer 7/6 is exactly a
one-frame phase residue. It judged acceptance met and safe to merge, but warned that the residue's
source-level cause and direction are unverified, so "late" is not a sound premise for a next fix.
Worker: GLM-5.3-Flash high, 30 turns, $0.019362545; verifier: GPT-5.6-Sol high, 23 turns,
$1.019545900; children total $1.038908445.

**Do, in order.**
1. **Baseline** `harness.py --only mettaur` and `oracle.py mettaur` (30864 / 1566 / 70; first
   divergence mm_timer k=0).
2. **Pair by event, not by score.** Define the pairing from measured state on both sides with
   `--watch`/the oracle block: the same attack index since battle start, AND MegaMan in the same
   mercy/HP situation (canon: hit at frame 114 from attack 1, HP 60 -> 50; ours: hit at 176 from
   attack 1). Derive the rust offset from that pairing; the search band may only be re-centred on it
   to CONFIRM a unique minimum, with the note saying why it is where it is (HANDOFF §3 "Adding a row").
   Report the score at the old offset and at the event-derived one; do not choose by the lower
   number.
3. **Acceptance.** The Align note cites the event evidence; `oracle.py mettaur` at the new pairing
   reports MegaMan's fields, with the first divergent field (if any) and frame; the row's negative is
   not blind and the oracle's shifted control changes the result. Report whatever total results --
   lower, equal or higher -- with the region of what remains.

**Rules.** tools/harness.py (this row's Align only) and docs; no src/; no allowlist change; do not
change any other row. **Report** the event evidence on both sides, old vs new Align and scores, both
oracle tables, in AGENTS.md shape. **Coordinator:** verify_rows plus the Sol verifier on the pairing
claim; this is a judgment about alignment (AUDIT's "no boxes in time"), so the verifier must confirm
the pairing is by event and not by score before any merge. No model escalation on a PARTIAL.

### F4. The opening row reads 1160 px since R1 rebuilt its canon state  *(DONE -- fixture fix landed, isolated 0; the integrated residue filed as A9, 2026-09-12)*

**Why.** `opening isolated` read PASS 0 over 40 frames against the lost `battlestart.state` (HANDOFF
§10). The 2026-09-12 gallery run reads **1160 / 29 / 40** (integrated 73659 / 2720) against R1's
rebuilt state -- same three Mettaurs, different history and RNG. No code change touched the opening;
the canon fixture changed. **Do:** localize the 1160 px (frame, region, which element) with diffmask
and the oracle; decide from measurement whether the row's descriptor, its Align, or our opening
differs from what the rebuilt canon state shows; fix the fixture side if the state is the difference,
or file the src/ defect with its frame and region. No allowlist change.

**Result.** The 1160 was the FIXTURE, not the opening. Localized frame by frame over the row's own
captures: every one of the 40 frames differs by exactly the same static 29 px at x 19..30, y 3..12 --
the HP box's digits. Canon's rebuilt state holds **0x0064 at 0x0203a9d4** (MegaMan object +0x24;
note `--peek` at load reads 0 there because the intro has not populated the object -- read it from a
200-frame capture's `--dump` instead) and draws "100"; the descriptor's `megaman_hp=60` was peeked
from the LOST state (TODO A6) and drew "60". `OPEN_ROW` now carries 100 (peeked), and also carries
the state's own RNG -- ePrimaryRngSeed (0x020013f0) reads **0x14ca0f46** at the rebuilt state's frame
0 (`--peek` at load) -- which `fixture_cheats()` now delivers at descriptor +58 (src/fixture.rs has
read the field since the wave 3d ticket; the harness never wrote it; descriptors without `rng` are
byte-identical, 0 stays "our default seed"). After: `opening isolated` **PASS 0/0/40**, negative not
blind (86591). Integrated moved 73659/2720 -> 72499/2691 and the REST IS NOT FIXTURE -- the rebuilt
state's spawn cells and the enemy HP readout's timing, both filed as **A9** with frames and regions.
The oracle (tools/oracle.py) supports wave/mettaur only and fails loudly on `opening`, so the
localization was done with the row's own captures (harness.run, kept dirs) plus `--dump`/`--peek`
peeks of the canon state instead.

**Coordinator verify (2026-09-12).** `verify_rows.py wt/f4-opening` from a clean detached rebuild:
PASS -- opening 0/0/40/86591 MATCH, wave 0/0/90/3840 MATCH, chip-cannon 14388/2350/40/21543
MATCH, no BLIND negative. No Sol verifier: the merged claim is harness lines plus peeked fixture
provenance, and A9's spawn-cell/RNG hypotheses are explicitly unverified and F5 does not build on
them. Merged as `61e1fdd`; the branch also carried stale reversions of `.pi/coordinator.md` and
`tools/pi_coordinator.sh` (it predated main's spend-cap commit -- out of ticket scope), and the
merge kept main's cap-enforcing versions. Worker GLM-5.3-Flash high, 67 turns, $0.077.

### F5. The chip rows' fixture: fire a chip after the corpse has dissolved  *(PARTIAL -- 2026-09-12; gate commit 28a6104 landed via the F5b merge, branch deleted)*

**Why.** 28 chip rows read exactly 14388 and 11 more read 14388 plus their own residue. The 14388 is
canon's fixture, not our code: from PAUSED, a 528 px portrait box (canon frames 43-48) and the deleted
Mettaur's dissolving corpse (frames 43-52) sit inside every chip row's window (read ALIGN_CHIP's long
comment in tools/harness.py in full first). A state saved after the dissolve clears both, but then the
game refuses every chip press. The previous ticket found the refusal path -- `sub_800938A`
(asm00_1.s:13037) forces CurState back to idle when the banner sequencer `sub_800801C` returns 6 -- yet
patching that compare did not restore firing, and it stopped for lack of a tracer. R5 added one
(`--watch-write`, HANDOFF §5), and `--trace-pc` exists. The empty-battle route (R3-R5) is closed.

**Do, in order.**
1. **Baseline:** `harness.py --only chip-cannon` (14388 / 2350 / 40) and two more chip rows.
2. **Find the real gate.** Build (with tools/states.py, a recipe, no hand-play) a sterile state past
   the full dissolve (portrait and corpse both 0 at load, as the comment's frame-110 state). Press A
   and use `--watch-write` on MegaMan's CurState/CurAction (0x0203a9b0+8/+9) and on the banner
   sequencer's state (`dword_203CA70`) plus `--trace-pc` on `sub_800938A`'s branches, to name the
   instruction and condition that refuses the fire. Compare with a press that fires (from PAUSED before
   the dissolve). Cite reference/bn6f file:line for each step.
3. **Intervene minimally, on the sterile variant only.** This ticket is authorized to add ONE option to
   tools/patch_sterile.py (address, original bytes, new bytes, and why, like the two existing patches)
   that lets a chip fire in this situation, or a one-shot poke if one works. Canon itself never changes.
   Report the intervention prominently: it changes what "canon (sterile)" is for the rows that use it.
4. **Re-point and measure.** Point the chip template at the new state and ROM variant; pin the canon
   alignment by the fire event (MegaMan's CurState leaving idle, as R2 did); run every chip row, one at
   a time, before and after. A row may only move if its negative stays non-blind. Report each row.

**Rules.** tools/ only; no src/; no allowlist change; captures one at a time. **Coordinator:**
verify_rows on every chip row plus the verifier on the gate claim and on the patch being the minimal
one; a PARTIAL from a wrong guess about the gate gets a follow-up ticket, not an escalation.

**Result.** The prescribed route is dead, the gate is found (with corrections), and the next
intervention is named but untested. Baselines: chip-cannon 14388/2350/40 (neg 21543), chip-vulcan
14388/2350/60 (18314), chip-sword 14388/2350/40 (18435) -- region canon frames 43-52, OBJ layer
(portrait box x0-150 y0-30 frames 43-48, corpse x149-196 y70-120 frames 43-52), rust side empty
there. Corrected gate: sequencer 0x08 (`sub_80080D2`) refreshes the TWO alliance players' AIData
via `sub_8012DFC` x2 (not every object); all-dead (`sub_800A152`==1, Unk_3a==0) advances to the
94-frame RESULT countdown 0x0C at ROM 0x0800811C (`mov r0,#0xC; str r0,[r5]`, asm00_1.s:10547-48);
state 0x0C (`sub_80081A4`) never refreshes AIData; `cmp r0,#6` at 0x80093A2 is irrelevant.
The opt-in `--hold-banner` NOP holds 0x08 through frame 129 but freezes corpse+portrait forever,
and the held battle's FSM dispatcher (`sub_8009158`) stops after save/reload; refilling 0x0203ca78
keeps 0x0C and does not restore firing. verify_rows PASS: all three rows MATCH, negatives non-blind.
Sol verifier: gate REFUTE-as-written / core SUPPORTED (scope + stale cites corrected above); patch
CONFIRM (default output byte-identical, exactly 4 bytes change) with one doc defect
(patch_sterile.py:74-76 falsely claims the hold produces a clean firing state); impossibility
REFUTE -- a one-shot poke to MegaMan's AIData pressed field in 0x0C after cleanup was never tested
though F5 allowed it, and that is F5b. Worker GLM-5.3-Flash high, 143 turns, $0.413; Sol verifier
GPT-5.6-Sol high, 14 turns, $0.365 (plus a $0.020 GLM pre-check on the wrong role, superseded).

### F5b. Fire a chip in state 0x0C by delivering the press to MegaMan's AIData directly  *(DONE -- 2026-09-12, merged; 27 chip rows to 0, every other chip row improved, none worse)*

**Why.** F5's verified core: chips fire only while the banner sequencer is in 0x08, because 0x08
(`sub_80080D2`) refreshes the alliance players' AIData from the joypad mirror every frame and 0x0C
(`sub_80081A4`) never does -- firing stops for lack of input delivery, not because of the countdown
(the 0x0203ca78 refill test excludes expiry as the first gate). The Sol verifier REFUTED the
categorical impossibility claim on one ground: nobody has tested a one-shot poke to MegaMan's
AIData pressed field in 0x0C after the cleanup, though F5 allowed a one-shot poke. That test is
this ticket. (Corrected scope: `sub_8012DFC` serves the two alliance players, not every object;
true cites mov/str asm00_1.s:10547-48, `sub_80081A4` 10617, `cmp r0,#6` line 13137.)

**Do, in order.**
1. **Start** with `bash tools/worktree.sh f5b-aidata`, then `git merge --ff-only wt/f5-chipfire`.
   First fix the branch's Sol-recorded doc defects on your branch and commit: patch_sterile.py:74-76
   must say the hold FREEZES the dissolve and kills dispatch (dead end, not a clean firing state),
   and the docstring's line cites/scope corrected as above. Default patch output stays byte-identical
   (prove with cmp, as before).
2. **The untested intervention.** Build (tools/states.py, a recipe, no hand-play) a sterile state past
   the full dissolve (portrait and corpse both 0 at load, sequencer in 0x0C). At a chosen frame apply
a one-shot poke to MegaMan's AIData JoypadPressed (with the A press in the mirror, as a player
   press would be) and use `--watch-write` on CurState/CurAction plus the sequencer word to show the
   fire path (`sub_800FB54` -> `object_setAttack2`, CurAction 0x08->0x14) or the exact refusing
   condition. Cite reference/bn6f file:line for each step, and compare against the A@40 firing press.
3. **If it fires on a clean field:** re-point the chip template at the new state and ROM variant, pin
   the canon alignment by the fire event (MegaMan's CurState leaving idle, R2's method), run every
   chip row one at a time before/after, and move only rows whose negative stays non-blind.
4. **If it refuses:** report exactly what was observed (which instruction/condition fails) -- a precise
   negative, no further intervention, no second patch idea.

**Rules.** tools/ and docs only; no src/; F5 already spent the one authorized sterile-patch change,
so no new patch_sterile.py option -- one-shot poke or held RAM only; canon never changes; no
allowlist change; captures one at a time. **Measure and report** the poke address/frame, the
watch-write fire/refusal trace, every moved row's before/after line, in AGENTS.md shape.
**Coordinator:** verify_rows on every moved row plus the Sol verifier on the fire-after-clean claim;
a second wrong guess ends the 0x0C route (options then, not a third attempt).

**Result.** The Sol-named gap closed with a measured fire. Poke `--poke-at 3:0x020340a4:0x0001`
(AIData JoypadPressed, ptr live from 0x0203aa08) + mirror 0x02036822 on `afterdissolve_0x0c`
(sequencer 0x0C, dissolved field) gives the identical chain as the A@40 control: Unk_44 0->0x4 at
0x0800FFEA, CurAction 0x08->0x14 at 0x0801169A via `sub_800FB54`->`object_setAttack2`, attack ends
frame 37 (minor: the end-frame cite is uncommitted, fire verdict unaffected). 27 chip rows PASS 0/0
(was 14388/2350); suprvulc 2464/177/113; bombs/seeds/vdoll 10-8338; energbom/megenbom 19958/1871;
0x15 rows 14740-73481 -- no row worse, none on PAUSED; wave/opening still 0, cannon 14388.
verify_rows PASS on all 43 moved rows + wave/cannon/opening canaries from a clean rebuild, no BLIND
negatives. Verifier (role default) CONFIRMs fire/scope/method with two recorded flags: the stale
.pi/coordinator.md hunk was dropped at merge (main's verifier-role text kept), and the 5 POPUP rows
now blank canon's popup against rust's drawn one (numbers stand; the popup ticket starts there).
Offset 122 confirmed in the merged-main caption; chip-cannon PASS 0/0/40 on merged main; gallery
GIFs for moved rows stale until the publish step. Worker GLM-5.3-Flash high, 131 turns, $0.219;
verifier Muse-Spark high, 39 turns, $0.403.

### F6. tiles/gauge isolated: 538 px over 8 frames  *(DONE -- 2026-09-12, merged; 208/208/8, residue is only the documented vblank frame)*

**Why.** `tiles` and `gauge` are the same full-screen capture (see `_tiles_gauge()`'s note) and both
read 538 / 208 / 8 isolated. Small, self-contained, two rows at once. **Do:** localize the 538 px with
tools/diffmask.py and the oracle (which frames, which element -- the custom gauge's stripe-flow is the
known TODO A8 candidate); find canon's routine for that element in reference/bn6f; fix src/ with the
citation; re-run tiles, gauge, wave, window and the full table (nothing worse). No allowlist change;
the integrated variants' allowlist entries stay until their own tickets.

**Result.** Landed at the documented residue. `sub_801C4e4` (asm00_2.s:26351-26423, slot 4 of
off_801BF88) draws bar `0x9232+((t div 7)&3)` via SWI Div and marker `byte_801C6C0[t&8]` off one
counter t at 0x02035280, no phase; src/hudtiles.rs runs it verbatim on gauge_tick
(BAR_PHASE/BAR_EXTRA/MARKER_EXTRA deleted, fitted 18->15; MARKER_FRAMES also deleted, derived
145->144). Exclusion proved: old shapes need phase s == 6 (mod 28) and s == 1 (mod 16), no
solution. Fixture seeds gauge_tick=50 from the measured flip (t_used=98+c; seed=(30-428) mod
112). Residue 208 px = HANDOFF-9 vblank frame k=7 only, k=0..6 exactly 0. verify_rows PASS
(tiles/gauge 208/208/8, wave 0/0/90, mettaur 31075 unchanged, negatives non-blind). Verifier
CONFIRMs mechanism/exclusion/seed; flags stale A8 wording left in fixture.rs docs and harness
captions (says defect unresolved -- under-claiming, rides the next caption pass). Full table
re-run: every other row identical to F5b. Worker GLM-5.3-Flash high, 84 turns, $0.117; verifier
Muse-Spark high, 33 turns, $0.421.

### F3. After the chip window closes, a faded copy of it stays on the field  *(DONE -- 2026-09-12, merged; ghost layer exact 0, row 977410->695603, residue is fixture content)*

**Why.** Playing the release ROM from power-on (tools/battle_gif.py's tour: pick FireSwrd, Start to
OK, A), the window slides out after "Sending chip data" and then a faded copy of it -- the window's
panel, chip grid and OK button, in other palettes -- appears on the left of the field at about frame
320 and stays for the whole battle. No harness row covers the window CLOSING: `window`/`card`/`cursor`
stop while it is open, and the integrated rows use flags that skip the opening window entirely.
Unverified: that canon shows nothing there (it should not, but that is the measurement).

**Do, in order.**
1. **Measure it.** Build a row that compares the close: canon from `chipselect.state` (the window open
   mid-battle) pressing through to OK exactly as a player does; our ROM with the descriptor's "open with
   the chip window" flag and the matching presses; align on the close event (a RAM value that marks the
   window leaving, found by --watch/--watch-write on both sides), and compare full screen for the
   frames after it. Negative not blind. Record the number and the region.
2. **Find why our layer keeps the tiles.** Which BG layer and tile/map range hold the ghost after the
   slide-out (dump VRAM/BG control registers at that frame), what canon does to that layer when the
   window leaves (the routine that clears or hides it -- cite reference/bn6f), and what our custom
   window code does instead (src/custom.rs and wherever the window's BG layer is set up).
3. **Fix it in src/,** citing the canon routine, and re-run: the new row, `window`, `card`, `cursor`,
   `wave` (still 0), and the full table (every row the same or better; a row that gets worse is
   reported, not hidden).

**Rules.** src/ for the fix; tools/harness.py for the new row; no allowlist change; captures one at a
time. **Coordinator:** verify_rows plus the verifier on the canon routine claim; a PARTIAL from a wrong
guess about the cause gets a follow-up ticket, not an escalation.

**Result.** The ghost is gone by mechanism, not masking. Old `vacate()` tested a 128-px scroll the
slide never reaches, so no column ever cleared and the whole window map reappeared on BG3 at
scroll 0; new `vacate()` clears leftward per (c+1)*8<=x, matching canon `sub_8026BF4`
(asm03_0.s:1026-1052, blank tile byte_8026C88, set->1 / clear->2 cadence) -- verifier CONFIRMED
against the disassembly and decomp. windowclose 977410/33380 -> 695603/28784 (neg 778748,
non-blind); the window's own layer is exact 0 over all ten slide frames, and the post-close 1402 px
is fixture content (descriptor gauge=1 vs canon's empty/refill; our 'Cannon 40' chip name vs none).
Full table identical to F5b/F6 except cursor 620802->620914 (+112): vacate cannot run there (no OK
press -- premise CONFIRMED), race-noise acceptance plausible with the one-frame localization
UNCHECKED. verify_rows PASS (windowclose/window/cursor/wave/card, all non-blind). Merge carve-outs:
the branch's or_spend.py rewrite and TODO F7-F15 deletion never landed (merge kept main); the gif
caption was reverted as out of scope and the inverted bit-2 comment fixed. Unverified: whether
canon's post-close gauge reset/refill is src/ behaviour or fixture -- the windowclose residue's
next question. Worker GLM-5.3-Flash high, 113 turns, $0.204; verifier Muse-Spark high, 28 turns,
$0.346.

### F7. The legacy `cannon` row still compares against PAUSED: 14388  *(DONE -- 2026-09-12, merged; 0/0/40)*

**Why.** F5b moved all 43 chip rows onto `afterdissolve_0x0c` (27 now 0) but the separate ported
`cannon` row (PORTED_CHECKS, `_cannon_canon`) still uses PAUSED and reads 14388 / 2350 / 40 -- the same
fixture artifact. **Do:** point `cannon` at the same route and Align method F5b used for `chip-cannon`
(or show why it cannot), baseline and after, negative non-blind. tools/harness.py only.

**Result.** Exactly as predicted: `cannon` re-pointed onto F5b's route and Align (`_chip_canon_0c("01")`
+ `ALIGN_CHIP_0C` on `afterdissolve_0x0c`), 14388/2350/40 -> PASS 0/0/40 (neg 9505, non-blind);
`chip-cannon` re-reads unchanged 0/0/40 with the same negative, so the whole 14388 was PAUSED
fixture artifact. verify_rows PASS on both from a clean rebuild. Harness-lines-only claim, no
verifier. Worker GLM-5.3-Flash high, 19 turns, $0.009.

### F8. `field` isolated: 1048 px over 40 frames  *(OPEN -- 2026-09-12)*

### F9. `banner` isolated: 2248 px over 58 frames  *(OPEN -- 2026-09-12)*

### F10. `buster` isolated: 3172 px over 32 frames  *(OPEN -- 2026-09-12)*

### F11. `warp` isolated: 9198 px over 30 frames  *(OPEN -- 2026-09-12)*

**Note.** Its negative control reads 9198 too -- the same as the nominal -- so first check whether the
row's alignment or negative is meaningful before localizing the residue.

### F12. The chip rows' own residues, family by family  *(OPEN -- 2026-09-12)*

**Why.** After F5b: SuprVulc 2464 / 177 / 113; the bomb, seed and VDoll rows 10 to 8338; EnergBom and
MegEnBom 19958 / 1871; the chip-family-0x15 rows 14740 to 73481. **Do:** take ONE family per run of
this ticket, smallest residue first (the rows at 10-8338), and bring its rows to 0; mark this ticket
PARTIAL with which family is done and leave it OPEN for the next family, until every chip row is 0.

### F13. `card` isolated: 18486 px over 16 frames  *(OPEN -- 2026-09-12)*

**Why.** HANDOFF §10 names the chip window's cursor-move timing.

### F14. `mettaur` isolated: 31075 px over 70 frames  *(OPEN -- 2026-09-12)*

**Why.** F2's event pairing left one field: `oracle.py mettaur` first diverges at `mm_timer` k=0
(canon 7, ours 6) -- MegaMan one frame apart inside the 120-frame mercy -- and canon's MegaMan is
blinking where ours is visible (mettaur-progress.gif). Find which side's mercy/blink timing is off by
the frame, from canon's routine (`sub_801A5EE`, asm00_2.s:22252-22296 sets the 120), and fix it.

### F15. tiles/gauge: the one vblank frame, 208 px at k=7  *(OPEN -- 2026-09-12)*

**Why.** F6 left k=0..6 at exactly 0 and 208 px on k=7, the vblank-race residue HANDOFF §9 records.
It is a checkable claim, not a tolerance: find which write lands a frame early or late between the
two binaries (the watchpoint names the writer on both sides) and make ours land where canon's does.
Same ticket: `cursor` went 620802 -> 620914 (+112) at F3's merge although F3's code cannot run in that
row (no OK press) -- the custmatch/cursor VRAM write HANDOFF §9 says lands a frame early between
differently sized binaries. Measure it with --watch-write on both sides; no row may silently move with
code size.

**Common to F8-F15 unless the ticket says otherwise.** Baseline the row (harness line plus
`tools/diffmask.py` region, plus `tools/oracle.py` where the row is supported); localize the residue to
frames and an element; find canon's routine for that element in reference/bn6f and cite it; fix src/
(or the fixture/descriptor when the residue is the fixture, with `peeked` provenance); re-run the row,
wave, window, opening, chip-cannon and the full table -- nothing may get worse, and a row that does is
reported with its numbers. No allowlist change; no alignment or region change except by measured event
(F2's rule). **Coordinator:** verify_rows on every row the report names; the verifier only for claims
beyond harness lines; a PARTIAL from a wrong guess about the cause gets one follow-up ticket; if that
also fails, mark the ticket BLOCKED and move on to the next OPEN ticket.

## A. Measured residues — small, self-contained, all have a number

### A9. The opening's integrated residue: the rebuilt state's spawn cells and the enemy HP readout  *(filed from F4, 2026-09-12)*

`opening integrated` reads **72499 / 2691 / 40** (window canon 120..159 vs rust origin 8 + offset
119) against R1's rebuilt `battlestart.state` after F4's fixture fix (hp + rng delivered). The
whole residue is the three Mettaurs, two mechanisms, both with numbers:

1. **SPAWN CELLS ARE THE OLD STATE'S.** Canon materializes its viruses at **(5,1) from canon frame
   ~118, (5,3) from ~153, (6,2) from ~183** -- measured twice, independently: gold-pixel cells at the
   materialization frames, and the objects' own PanelX/Y at frame 250 (0x0203aa88/0x0203ab60/
   0x0203ac38, +0x12/+0x13 = (5,1),(5,3),(6,2)). The descriptor's diagonal (4,1),(5,2),(6,3) is the
   LOST state's layout; src lays a fixture's enemies out on a fixed +1/+1 diagonal from ONE
   (enemy_col,enemy_row) (src/battle.rs ~1348-1358) and cannot express the new cells. The real
   mechanism is probably spawn cells chosen from primary_rng at battle init -- same encounter, and
   the cells changed between the old and rebuilt states -- but canon's cell-selection routine has
   NOT been found, so that is unverified. Two ways to fix: derive the cells from the (now delivered)
   rng the way canon does, which needs canon's routine in reference/bn6f first; or extend the
   descriptor with per-enemy cells (FIXTURE.md + src/fixture.rs + battle.rs).
2. **THE ENEMY HP READOUT IS ~70 FRAMES EARLY.** Ours draws "40" under each virus the moment it is
   targetable -- already visible on the row's first compared frame (rust 127, mid-materialization;
   the draw loop at src/battle.rs ~3550, "Each enemy's HP sits just under its panel"). Canon shows NO
   readout during the whole opening: scanning 150..400 from the state, its first "40" is at canon
   frame **~196**, with the opening chip window (C1: a battle OPENS with the chip window). Region:
   the digit readouts under the virus panels, x 150..200, y 86..140. src/ territory: gate the
   readout on whatever canon gates it on (probably the same event that opens the window), not on
   targetability.

### A1. The shockwave's departure  *(DONE at 0 -- TRANSFER 7bj)*
460 px to 345 to ZERO. The mechanism was modelled -- a hop spawns a NEW segment and the old
one stops where it is and plays its own animation out -- and the last three frames were the
segment being destroyed too early. `on_last_frame()` was checked BEFORE ticking, so the
fragment spray (`wave.bin` anim 0 frame 4) was never ticked and never shown.
`sprite_getFrameParameters` masks 0x80 out unless the frame's own duration counter has
already reached zero (sprite.s:1182-1198), so the bit means "held for its full duration",
not "reached". Real and ours are now both 2 poses over 5 frames, hash-identical.

THE PER-HOP TABLE IS A DEAD END -- DISPROVED, TRANSFER 7bh. `byte_80C6B00` is 16 rows of 4
bytes indexed by `Param1 * 4` (asm31.s:31411-31416), and `Param1` is INHERITED across a hop:
the respawn goes through `SpawnBattleObjectCommon`, which copies the whole Params word
(asm00_1.s:254). Every hop of one attack reads the same row, and a Version 0 Mettaur is on
row 0 -- dwell 0x16, animation 0 -- from first hop to last. Do not model the table.

THE REAL LEAD is the departing segment's own animation hold. The three frames are real
199-201 against ours 220-222, 115 px each, and they are the fragment spray at the panel just
vacated (`wave.bin` animation 0 frame 4, the one flagged 0x80). The real ROM's spray shows
several distinct sub-poses over that window; ours shows one pose for about two ticks and
then vanishes. So the segment is being destroyed a few ticks too early -- look at
`on_last_frame()` and the departure's destroy sequencing, not at the table.

Two negative results already recorded, do not repeat them: allowing SEVERAL departures to
overlap measures 8725 px over 20 frames; and pre-ticking every new segment's `Player` the
way `Shot::shockwave()` pre-ticks only the first measures the same 8725 and takes `wave` to
3840. One slot, newest wins, and only the first segment is pre-ticked.


### A2. The chip window's cursor  *(done -- TRANSFER 7ag)*
170 frames of a five-step walk, and everything the SCRIPT drives is exact. It was two
one-frame bugs and neither was `CURSOR_DELAY`: the card's palette landed a frame before
its tiles, and the bracket's blink flipped a frame early because `self.frames` is bumped
before anything is drawn. The fixture had to be fixed first -- `demo-cardname` places its
cursor statically and never walks, so a scripted real walk was being compared against a
still picture. `demo-custmatch` starts on OK as the save state does, so both sides run the
same script.

CLOSED at 0 -- TRANSFER 7bc. The paragraph that used to stand here said the residue was a
fixture problem with no shared origin and could only ever coincide. That was wrong, and
nobody had read `sub_8028820`. The blink counter is window-relative on both sides (a field
at 0x02036500, asm03_0.s:4801-4804 and 1163-1165); the save state's value is just not zero
(0x647, peeked). Held static and swept, the offset was exactly +1 frame, and the frame was
ours: the slide-in reached `Phase::Open` through a second match arm a frame after the real
ROM advances to state 4 in the call that zeroes the counter (asm03_0.s:1011-1012).


### A3. The shockwave's panel light  *(DONE at 0 -- TRANSFER 7bk)*
Was 87 of 90. Two of the three were the wave's PARTING light: when the hitbox dwelt its
way off the field this build dropped it immediately, discarding the three-frame linger
`Shot::update` had just armed for the panel it was vacating. The real ROM's segment keeps
re-asserting its old panel's highlight every frame until its own departure animation
finishes -- `object_highlightCurrentCollisionPanels` is called unconditionally from
`sub_80C6C14` (asm31.s:31491) whatever the CurAction is. Fixed in `src/battle.rs`.

AND THE OCCUPANCY RULE WAS NOT A RULE. "A panel somebody is standing on is not lit" was
recorded from one capture and is wrong: there is no occupancy check anywhere in the
render path -- `object_highlightPanel` and the panel-draw loop `sub_800C5E0`
(object.s:2548-2560, 1684-1761) only ever look at panel validity, a blink flag and the
one-shot highlight flag. The real mechanism is in the wave's own update:
`object_clearCollisionRegion` is called only when a hit has just registered
(asm31.s:31480-31485). Confirmed by tracking MegaMan's HP across dumps -- on the SECOND
attack the wave relit his panel normally for about 14 frames while he was still in his
post-hit invincibility, and it went dark only when a hit actually landed. The simple
`taken = navi.panel() == (c, r)` check in `battle.rs` happens to match over the measured
window because that window covers a first hit on a fresh target. Modelling it properly
means modelling mercy invincibility.

WHAT IS LEFT is the wave's FIRST hop, one frame. THE LAYOUT SCARE IS RETIRED (TRANSFER
7bd): the claim that any source edit shifts the Mettaur's timing was tested with a private
target directory and is false. Identical source gives byte-identical ROMs and captures; a
comment, a dead const, a dead function and a dead local inside the strike arm itself all
left the spawn frame at 198. The ROM hash moves only because `assert_eq!` bakes
`panic::Location` line numbers into `.rodata` -- six dead bytes. The likely cause of the
original report was two builds racing the shared target directory. So the first hop can be
chased directly, with no methodology worry attached to it.

### A4. Pin the backdrop's scroll phase  *(REOPENED -- the missing state now exists)*
`tiles` compares a fixed frame 392, not the best of sixty, and that is better than it was. But 392
was SEARCHED FOR, not derived: the phase counts from battle init (`eBGScrollCBCounters`, zeroed
once by `sub_8080D90`) and `pausedwithcannon.state` is 7891 frames in, which nothing here can
reproduce. The entry used to end "a capture from a battle's real frame 0 is the single most
valuable thing the harness does not have".

IT HAS ONE. `/tmp/battlestart.state` peeks as

    battlestart.state       0x02009690 = 0x0000       0x02009694 = 0x0000
    pausedwithcannon.state  0x02009690 = 0xFFFF0968   0x02009694 = 0xFFFF84B4

and -63128/8 = -31564/4 = 7891 exactly, which is the elapsed figure TRANSFER already records. So
the counters fall by 8 and 4 a frame from zero at init, and battlestart.state is at battle frame 0.

WHAT MEASURING IT SHOWED, and why this is not just tidying. Real from battlestart.state against
`demo-open`, backgrounds only, whole screen: the best match against real frame 120 is 1294 px at
rust 127/128, of which the HUD strip is 1102 and the backdrop band 116. Holding that lag and moving
the frame gives 4375, 5352, 1294, 4378, 4005, 5707 for real 100/110/120/130/140/150. A constant
offset plus a static HUD difference would sit near 1294 everywhere. It does not -- so either the
best lag drifts with the frame, or our backdrop advances at a different RATE from the real one,
which would be a parity bug that the swept 392 has been hiding.

### A8. The custom gauge  *(0 -- but by MEASURED constants, not a mechanism)*
`gauge` 446 -> 0. Two offsets, `BAR_EXTRA = 9` and `MARKER_EXTRA = 8` in src/hudtiles.rs.

READ THIS BEFORE TRUSTING THE ZERO. Both numbers were measured, neither was derived, and the
thing they imply is not understood: this build drives the bar and the marker off ONE counter
(`gauge_tick`), and the real ROM evidently does not, because no single phase can satisfy both --
9 mod 28 together with 0 mod 16 has no solution. The offsets make the picture match; they do not
explain why the two clocks are related the way they are. That is still open, and the routine that
draws the flowing bar has still not been found in the disassembly.

Same footing as `BUSTER_HIT_DELAY` in battle.rs, and labelled the same way in the source: the
value that measures right rather than the value that computes right. A zero standing on two
unexplained constants is worth less than a zero standing on a mechanism, and the next person to
touch this should be trying to replace them, not defend them.

### A8 (the diagnosis, kept -- five wrong readings and what settled them)
### A8-old. The custom gauge's BAR CELLS ARE THE WRONG SHAPE
`gauge` 446. Rendering the two HUD strips side by side at the alignment answers it in one look,
after four rounds of me reasoning about timing:

    real   the bar's lit cells are SLANTED parallelograms -- diagonal stripes, "///"
    ours   plain upright rectangles

That is why no phase ever matched. It is the tile ART, not the animation: sweeping our frames over
more than a full 112-frame gauge period against the real frame finds nothing better than 446, and
the alignment frame itself is the best. Everything around it is already right -- the gauge is full
on both sides (peeked: 0x020352A0 reads 0x4000, the cap), the lit bar spans the same 64..183, and
the four-step 7-frame cycle shifting the pattern 2 px a step is confirmed on the real ROM by the
leading edges of its lit runs (66,74,82,90,98 at f41; 64,72,80,88,96 at f42 -- 8 px apart, 2 px
left at a step boundary).

MY OWN WRONG READINGS ALONG THE WAY, all from measuring instead of looking: "the prompt blinks out
of phase" (it does, but that is 194 of the 446, not all of it); "it is an origin problem"; "it is
not a phase problem, the content differs" (right, but I then guessed the wrong content); "the
stripes shift early and stop" -- that last was the DIAGONAL pattern moving through the single row
I was hashing, which is exactly what a slanted cell does.

    HP box 28    bar left 112    marker 194    bar right 112

AND THE TILES ARE NOT WRONG EITHER -- that was my fifth reading and it lasted about ten minutes.
Rendering one body cell across a full cycle on both sides, seven frames apart:

    real   slant   slant'  small-squares  big-square  slant  slant'
    ours   big-square  slant   slant'  small-squares  big-square  slant

The SAME FOUR TILES IN THE SAME ORDER, ours one step behind. Our asset has all four
(indices 57, 58, 59, 60 = VRAM 0x234, 0x235, 0x232, 0x233, exactly what the docstring on
`BAR_CYCLE` already claimed).

WHAT IS VERIFIED, AND NOTHING MORE. The four tiles are right and in the right order; at the
alignment frame the two sides are on different steps of that cycle. Everything else I claimed
about this bar tonight was wrong, six times over, and the last one is worth spelling out because
it is a trap anyone would fall into:

I measured the lit bar's EXTENT with a green-colour test and got 64..183 on the real ROM against
65..182 here, and wrote that up as "our art sits one pixel in at both ends". Reading the actual
pixels instead: at y=14 the real is green at x=64,65,66 with a blue pixel at 67, and ours is green
at 66,67,68,69. Different PATTERNS, not a shifted one. The extents differ because the two sides
are on different cycle steps -- which is the thing already known. An extent computed over a whole
box across differing patterns says nothing about position.

THE TABLE, WHICH SETTLED IT. Hashing one body cell per frame across a full cycle on both sides:

    real  f44..f71 : AAAAA BBBBBBB CCCCCCC DDDDDDD AA
    ours u435..u462: AAAAAAA BBBBBBB CCCCCCC DDDDDDD

Four tiles, seven frames each, on both sides -- and the four HASHES ARE THE SAME on both, so the
art is byte-identical and only the phase differs. (Careful with that table: the letters are
assigned per side, so real's "A" and ours' "A" are NOT the same picture. Matching by hash instead:
the real shows its frame-44 tile on frames 42..48, and we show that same tile on our 442..448.)

TWO NUMBERS, and they are the whole ticket:
  - THE BAR is 9 frames LATE. The alignment maps our frame u to real u-391, so the real's run at
    42..48 should be ours at 433..439 and is ours at 442..448.
  - THE MARKER IS ALREADY ALIGNED, offset 0. Real runs 38..44, ours 429..431, and 429-391 = 38.

That is the surprise, because in this build both come off the SAME counter -- `flow = gauge_tick -
BAR_PHASE`, feeding `(flow / BAR_FRAMES) % 4` for the bar and `(flow / MARKER_FRAMES) % 2` for the
marker. So the two are in the wrong phase RELATIVE TO EACH OTHER, and no single seed or
`BAR_PHASE` can fix both: 9 is not a multiple of the bar's 7-frame step either, so it is not a
rotation of `BAR_CYCLE`.

DO NOT just add 9 somewhere. The mechanism is the question now: find what the real ROM advances
the BAR from, and whether it is the same thing that drives the marker. `SetCustGauge` writes the
gauge VALUE to 0x020352A0 (asm00_2.s:29838); the routine that draws the flowing bar has still not
been found.

SEARCHES THAT DO NOT FIND IT, so nobody repeats them: grepping the asm for the bar's VRAM tile ids
(0x232-0x235) finds nothing -- they are not literals -- and grepping for the gauge art's load base
0x222 finds only `0x2220`, which is an EVENT FLAG base in asm00_1.s:8227 and asm03_2.s:4336, not a
tile. The ids must be built from a base plus an offset, or come out of a table. Try instead:
follow the writers of the BG3 map region the gauge occupies, or set a watchpoint on the map cells
in an emulator and see who writes them.

The marker (194 of the 446) is a separate half-cycle of phase: real is ORANGE at the alignment
frame, ours CYAN, both blinking on the same 16-frame beat with exactly 110 orange pixels lit. Last,
after the two above.

### A7. The backdrop's art animation  *(DONE -- 40 consecutive frames at 0, every frame sampled)*
**`opening` IS NOT 0 AND NEVER WAS.** I wrote that check tonight sampling `range(120, 160, 4)` --
every fourth frame -- and every fourth frame was exactly the set that matched. The backdrop's
scroll moves a pixel every 2 frames across and every 4 down, so a rounding error shows on three
frames in four and hides on the fourth. Sampling a periodic signal on its own period measures
nothing. Measured at the time, at the lag the check used:

    real 120 -> 0    121 -> 2433    122 -> 2433    123 -> 0    124 -> 0

I reported "opening 16788 -> 0" as the evening's headline. It was an artifact of my own sampling.

WHAT THAT UNCOVERED, and it is the good half. The scroll's rounding fix -- ceiling rather than
floor, because the register is `lsr #4` of a FALLING counter -- is CORRECT after all. I had
reverted it twice: once measured at a fixture's stale fixed lag, once "confirmed" by this check.
With it in, and sampling EVERY frame at a searched lag, 34 of 40 frames are exactly 0 where
before three in four were a whole pixel out. The full suite is otherwise untouched: every other
check stays at 0, so the fixture damage I attributed to it earlier really was the `BD_TRACE`
diagnostic.

WHAT IS LEFT, and it is now precise: at lag 6 the failures come in PAIRS EVERY EIGHT FRAMES --
frames 126/127 (156 px), 134/135 (496), 142/143 (2359), 150/151 (2671), 158/159 (2466). Eight
frames is the backdrop's art step in the settled part of its schedule, so with the scroll finally
right the ART now sits one frame off it. The growing magnitude is the art drifting further from
the real ROM's as the run goes on.

FIXED, AND THE FIX IS AN INITIAL CONDITION, NOT A FUDGE. The art needed to start two frames
further back than the real ROM's own clock does: `Backdrop::new` seeds `STEP_HOLD[0] + 1` where the
real ROM reads Timer 3 at the frame its scroll counters read zero. The reason is that this build
creates its backdrop two frames into the battle it is being compared against. Measured rather than
assumed -- that value gives 40 consecutive frames at exactly 0, and one frame either side of it
measures 8102 and 24398.

AND IT UNCOVERED A BUG IN THE SEEDING. `prime()` was assigning the timer, which silently discarded
whatever `seed()` had just set -- so the peeked Timer had never taken effect at all, only the entry
and the scroll counters had. `prime()` now only draws.

`opening` is 0 over 40 CONSECUTIVE frames, every frame sampled, with the lag searched. The backdrop
is exact.
`opening` IS ZERO. The backdrop band is 0 on every sampled frame and so is the HUD. Three parts:
the schedule (below), the scroll's rounding, and MegaMan's HP -- the last 290 px were entirely
the HP box, 29 a frame, because the captured battle's navi is on 60 and `demo-open` started at
100. It now carries the capture's HP as `demo-hudmatch` and `demo-resultmatch` already did.

THE SCROLL ROUNDING, and the trap in measuring it. The register is `lsr #4` of a counter that
FALLS by 8 -- a logical shift of a negative, so a ceiling on the negated value where a plain
divide floors, one pixel apart on ODD frames. Measured at the fixture's FIXED LAG the change
looked catastrophic (290 -> 30304) and was reverted as a negative result. Searching the lag shows
it is identical: 290 at lags 6 and 7, where before it was 290 at 7 and 8. It moves which lag is
right and nothing else. **A fixed alignment constant will report a correct change as a disaster.**
That is the same failure this file records for `tiles`, `mettaur` and `wave`, made a fourth time,
by me, an hour after writing the other three up.

WHAT IS LEFT is `tiles` only. Its window (390..394) predates the corrected period: the art cycle
is 192 frames, so matching art AND scroll needs LCM(192,896) = 2688 rather than 896. A 2790-frame
sweep of `demo-hudmatch` finds its best band score at 68 px, recurring every 384 frames, and never
0 -- while `demo-open` reaches 0 outright. Rendering the 68 shows every arc and ring aligned
pixel-exact and only the glyphs differing, so at those frames we are on a different art STEP, not
looking at a broken asset.

SOLVED. At the derived alignment -- our frame 1798 against the real ROM's frame 44 -- the whole
screen compares at 470 px, and the backdrop band, the field and the bottom strip are all ZERO. The
backdrop is pixel-exact. Every one of the 470 is the HUD's L-or-R prompt blinking out of phase,
which is now A8 above.

The last step of the diagnosis is worth keeping. Our frame 1798 was compared against every real
frame in range, and it matches real 44 EXACTLY while differing from real 43 by 136 px. The fixture
had been comparing against 43. So the "one step's art" theory below was wrong too: nothing was
wrong with the art, the alignment was one frame out.

WHAT WAS RULED OUT ALONG THE WAY, all of it verified rather than assumed: `demo-hudmatch` was instrumented the same way. Its clocks
reach entry 13 / timer 8 -- the real ROM's state at its own capture frame 43 -- on frames 64, 256,
448, 640, every 192 as they should. Combining with the scroll (period 1024 frames) puts the true
alignment at rust 1798, and measuring there gives the best result in the whole capture: full 752,
band 136. Not a search, and not 0.

At rust 1798 our entry is 13, so we are drawing STEP 0, which is `byte_807FE40`. The real ROM at
its frame 43 is on entry 13 as well, so it is drawing the same step. Both sides draw E40 and the
band differs by 136 px. Meanwhile `demo-open`'s compared frames sit early in the schedule, on the
alternating C90/CD8 beats, and reach 0.

So the schedule, the initial condition, the scroll rounding and the step->art mapping are all
verified correct, and what is left is the ART OF ONE STEP. The mapping was checked exhaustively
rather than by eye: parsing the seven tables out of dat20.s and matching them against the
exporter's rows gives a unique hit for every one (FRAMES[0]=E40, [1]=CD8, [2]=C90, [3]=D20,
[4]=D68, [5]=DB0, [6]=DF8), and re-deriving STEP_ORDER from the script under that mapping
reproduces the table in the branch exactly.

NEXT STEP, AND ONE WAY THAT DOES NOT WORK. Diffing raw VRAM at the script's own `gfx_dest`
(0x06000040) between the two builds is USELESS: agb allocates VRAM its own way, so that address
holds unrelated data in this build, and all 1152 bytes differ for a reason that has nothing to do
with the art. (The real side reads `ffffffff` for its first tile at dump time as well, so the
address is not simply "the backdrop's tiles" on that side either.) Do not repeat that.

What is worth doing instead is a pure DATA comparison, no emulator: parse `byte_807FE40`'s 36
indices out of dat20.s, slice those tiles out of the blob at `dword_8617488` (dat38_60.s), and
compare them against step 0's tiles in `assets/backdrop.bin`. If they agree -- and they should,
because `backdrop_export.py` builds the asset from that blob using exactly those indices -- then
THE ART IS NOT THE PROBLEM AND THE MAP IS. Note the script copies 36 tiles while the exporter's
rows carry 37 slots, the extra one at the front; a map that assigns those 37 slots differently
from the real ROM would show up exactly like this: right tiles, wrong places, on some steps and
not others.

The rendering evidence supports the map over the palette: ours draws FEWER glyphs rather than
differently-coloured ones.

MERGED. `opening` 0, `gauge` 446, and every other check still 0 -- seventeen checks, sixteen of
them zero.

What landed: the scripted art schedule, and `Backdrop::seed`, which gives a fixture the phase of
the save state it is compared against instead of starting its clocks at zero. That also brought
`tiles`' alignment back to rust 435 against real 44, so the check captures 438 frames rather than
the 1800 it needed to reach the only unseeded alignment at 1798.

AND THE "FIXTURE REALIGNMENT PROGRAMME" I WROTE HERE WAS MY OWN DEBUG CODE. `chips` 13 off,
`popup` 7366 and `banner` 5162 came from a `BD_TRACE` static I added to instrument the clocks and
forgot to remove -- 5.6 KB and a write every frame. I measured its effects, concluded that a
correct backdrop invalidates every fixture calibrated against the old one, reasoned out why that
followed from the periods, and wrote it up as a programme of work with three options. Removing the
diagnostic took all three checks to 0. The art schedule never touched them.

The reasoning was plausible and the arithmetic about the periods was right; it was attached to a
cause I had introduced myself and not checked for. Before explaining a regression, check what is
in the tree.

MY ORIGINAL FRAMING WAS WRONG. The art clock does NOT have a different origin from the scroll:
`LoadGFXAnims` is called at battle init from `sub_8080DA0`, in the same routine as the scroll's
own zero, back to back (asm00_1.s:8434-8435).

THE REAL MECHANISM: the art is the same scripted GFXAnim engine the overworld uses
(`ProcessGFXAnims`, asm00_0.s:3510-3697), driven by a list of (tile-table, delay) entries in
`eGFXAnimStates` (0x020094c0, GFXAnimState.inc). For this background the script is `off_807FB98`
(data/dat20.s:140-172): TEN 4-frame entries, then NINETEEN 8-frame entries, a 192-frame loop --
not the uniform 8-frames-forever, 56-frame loop this build assumed.

VERIFIED EXACT. Simulating the transcribed schedule against `--dump 0x020094c0:24` peeks of the
real ROM's own `entry`/`Timer`:

    battle frame   1      2      3      5      9        7935
    real         (0,2)  (0,1)  (1,4)  (1,2)  (2,2)    (13,8)
    model        (0,2)  (0,1)  (1,4)  (1,2)  (2,2)    (13,8)

The deep-battle column needed care: `pausedwithcannon` is 7891 frames in and the capture runs 44
frames to reach index 43, so the battle frame is 7935, not 7934. An off-by-one there looks
exactly like a broken model.

WHERE IT STANDS: `opening` 16788 -> 290 (worst frame 29 px, from 2740). But `tiles` 0 -> 282.
That is not a regression in the model, it is a phase move: the art period is now 192 rather than
56, so matching art AND scroll needs LCM(192,896) = 2688 instead of 896, and the check's window
(390..394, capture 395 frames) no longer contains the match. Derived rather than searched, the
match is at rust 2184, and a sweep confirms a sharp minimum there -- 282 px against ~3200 and
~4000 on either side.

WHAT IS LEFT, NARROWED TO A NUMBER: our ART and our SCROLL are THREE FRAMES out of step with
each other. Not the art's schedule, which is exact, and not the scroll, which is pixel-exact --
their relative offset.

Rendering the two sides at rust 2184 shows every arc and ring of the backdrop aligning perfectly
and ONLY the little purple glyphs inside the rings differing, which rules the scroll out by
inspection. Counting glyph-coloured pixels gives the step boundary directly:

    real  (36, 39, 42, 45, 48, 51, 54, 57)  1162 1172 1174 1047 1035 1040  870  884
    ours  (2176, 2179, 2182, ...)           1162 1172 1025 1024 1035  848  843 1208

The two agree for two samples and then ours steps early: the real ROM changes step between its
frames 42 and 45, ours between 2179 and 2182. So at rust 2184 the scroll is exact and the art is
three frames advanced; at 2181 the art would line up and the scroll would not.

WHERE IT IS NOT. Both structures were dumped on the SAME real frames, which settles the
relationship instead of comparing each against its own assumed origin:

    real frame   art entry/Timer   scroll counters   frames since init
    1            0 / 2             -8 / -4           1
    2            0 / 1             -16 / -8          2
    3            1 / 4             -24 / -12         3

So the art's entry 0 counts 4,3,2,1 across scroll-frames -1, 0, 1, 2: THE ART STARTS EXACTLY ONE
FRAME BEFORE THE SCROLL'S ZERO, and `prime()` (entry 0, timer 3 at frame 0) already models that
correctly. The initial condition is right and is not where the three frames are.

WHERE TO LOOK NEXT, then: our own sequencing. `prime()` is called from `Battle::prime_backdrop`
right after `Battle::new`, and `Backdrop::update` advances BOTH clocks -- so the art and the
scroll cannot drift from each other unless `update()` is not being called on every frame the
scroll is supposed to advance, or the backdrop is created some frames before the battle's own
clock starts. Instrument it: have the build report its own `entry`/`timer`/`x_q` per frame (a
poke to a known address the harness can `--dump`, or a debug tile), and compare against the table
above. Do not adjust a constant until that trace exists -- the schedule and the initial condition
are both confirmed exact now, so a constant that fixes the number would be hiding the real cause.

ONE SMALLER THING FOUND ON THE WAY, AND TRIED, AND WRONG. The real scroll register is
`(counter as u32) >> 4` of a counter falling by 8 -- a LOGICAL shift of a negative, so it lands
on -ceil(n/2) where this build's `-(x_q / 4)` gives -floor(n/2), one pixel apart on odd frames.
Checked against the peeks: at frame 1 the counters read -8/-4 and the register is -1/-1, where
this build gives 0/0. The derivation looks airtight.

CHANGING IT TO CEILING MEASURES MUCH WORSE: `opening` 290 -> 30304, `tiles` 1160 with its best
at 390 rather than 391. Reverted. So something in the derivation is wrong -- the register may not
be written straight from that shift, the BG offset may carry another term, or our `x_q` may not
correspond to n the way I assumed. Worth another look with a per-frame trace of BOTH sides'
actual scroll registers, not a third guess.

A plausible change backed by a disassembly line that moves the number the wrong way is exactly
the shape 7ah warns about. Recorded here rather than retried.

DO NOT MERGE THE BRANCH UNTIL THAT IS ANSWERED, because merging as-is turns a `tiles` 0 into a
282, and a 0 that came partly from luck is still worth more than a non-zero nobody has explained.
The backdrop is not just a scrolling picture: parts of it ANIMATE, in steps of about 8 frames.
Counting one of its own colours, magenta (90,0,140), over the whole screen from a battle's
first frame gives a clean staircase on both sides:

    real  934 958 958 959 | 707 725 725 725 725 737 737 737 | 388 x8 | 220 x8 | 0 x8 | 426 ...
    ours  884 884         | 649 673 673 672 672 691 691 691 | 358-377 | 208-220 | 0 x8 | 431 ...

THE TWO CLOCKS DISAGREE WITH EACH OTHER. The SCROLL aligns at lag +7 (our capture starts at
boot, the real one at battle frame 0). The ART ANIMATION aligns at lag **0** -- the staircases
above are absolute capture frames on both sides and they nearly coincide. So relative to our own
battle start, our art animation is running about seven frames early, or is counting from
something other than battle init while the scroll counts from battle init correctly.

That is a real one-clock-per-thing bug of the same family as the three fixed on 2026-09-07, not
the unrecoverable phase that 7bi settled for. It is very likely the whole of the 86 px that the
backdrop band bottoms out at in the `demo-open` fixture, and it is what makes the magenta
elements appear pink in the real strip and absent in ours at the same frame.

WHERE TO LOOK: `src/backdrop.rs` -- what drives the frame it picks for the animated tiles, and
whether that counter is the same `ticks` the scroll uses. On the real side, the scroll is
`BGScrollCB_BG1Diagonal3to2Scroll` (asm00_0.s:3272-3288) off `eBGScrollCBCounters`, zeroed at
battle init; find what advances the ART and whether it shares that origin.
NOTE the amounts differ slightly too (934 against 884 at the same step), so check the count as
well as the timing -- it may be a second, smaller thing.

### A6. The HUD does not match at a battle's opening
Falls out of A4's measurement and deserves its own number. Real from `/tmp/battlestart.state`
against `demo-open`, `--disable-obj`, HUD strip box (0, 0, 240, 24): **1102 px**, and it looks
static rather than drifting, so it is probably content and not timing -- MegaMan's HP, the chip
counts, the enemy names. `demo-open` already fields that capture's own three Mettaurs, so whatever
differs is something the fixture is not setting up.

LOCALISED, AND THEN LOOKED AT, which should have been the first move rather than the third.
Counting differing tiles said "49 tiles, nearly the whole width" and suggested enemy name
plates. Rendering the two strips one above the other answered it in one glance:

    real   HP box reading 60,  and NOTHING else -- no gauge
    ours   HP box reading 100, and a full CUSTOM gauge with its L-or-R prompt

Two separate things, one of them real:

1. **THE CUSTOM GAUGE SHOULD NOT BE DRAWN DURING THE OPENING.**  *(DONE -- gated on a new
   `window_closed` flag; the strip went 1102 px to 85.)* Measured by rendering the real
   ROM's HUD strip at frames 75, 100, 125, 150, 165, 175 and 185 from `/tmp/battlestart.state`:
   **there is no gauge on ANY of them.** Just the HP box, and backdrop everywhere else. By 200
   the chip window is up and the strip is the chip-select screen. Ours draws the gauge, full,
   from the start. A parity gap, not a fixture problem.
   NOTE the gauge and its "L or R" prompt are the real game's own HUD art, not a debug
   affordance -- the only `cfg!(debug_assertions)` in battle.rs is the L/R shortcut at
   battle.rs:1694, which is a different thing. I checked, because "a debug aid leaked into
   release" would have been the tidier answer.
   STILL OPEN: when the gauge DOES first appear. It should be after the first chip window
   closes -- a battle opens with that window (7aw), so there is nothing for a gauge to do before
   it. Confirming that needs a capture where the window actually closes, and a naive `A` press
   does not do it: the cursor starts on a chip, not on OK, so scripted A presses at 230 and 260
   left the window still open at frame 410. Drive the cursor to OK first.
2. MegaMan's HP: the captured battle's navi has 60, `demo-open` starts at 100. Fixture setup.

Lesson worth keeping: a pixel count tells you how much differs and a picture tells you WHAT.
Two rounds of tile arithmetic here produced a wrong guess that one 8-line render replaced.
The existing `tiles` check uses `demo-hudmatch` against `pausedwithcannon` and reads 0, so the HUD
CAN match -- it is this fixture's setup that does not.


### A5. The battle opening  *(done -- TRANSFER 7ba)*
`demo-open` exists and fields the capture's own three Mettaurs. Measured:

    real   white 0..70, field at 71, viruses 113/141/173, window 173
    ours   fade  0..32, field at 32, viruses  59/ 92/125, window 134

SETTLED AND DONE: the white is the battle's -- the save state's scroll counters read zero,
so init has happened, and the screen is white for 71 frames after. The intro now holds full
white for 71 frames in non-demo builds and in `demo-open`; every other demo keeps the old
black ramp, because their frame offsets were calibrated against it and changing it moved
eight checks at once.

DONE. With the lead-in right the rest came with it, and there was never a second problem:

    first virus starts materialising   frame 76 after init, BOTH SIDES
    it settles                         frame 142,          BOTH SIDES
    chip window opens                  129 there, 130 here

The earlier "22 frames early" and "91 against 113" were the wrong lead-in wearing different
hats. A wrong constant early in a sequence makes everything after it look wrong in its own
way, and each of those looks like a separate bug. Fix the earliest and re-measure before
believing any of the others.

A sampling trap worth remembering: a "brightness" measure reads white as FULL brightness, so
a white screen looks like a finished fade. Measure the colour.


## B. Things the game does that this build does not

### B1. The PAUSE menu
Research is done and sits in `TRANSFER.md` 7ar; this is an implementation ticket.
`sub_802B7A0` (asm03_0.s:10937) fades the screen with `SetScreenFade(0x14, 8)`, raises
banner message 9 or 13 depending on a flag at `[r5,#7]`, and both records are KIND 2 —
which is exactly what makes the banner's phase ticker freeze at counter 4, so the ribbon
sits fully extended for as long as the game is paused (asm00_2.s:27590-27603). Unpausing
calls `sub_801E780`, which forces the counter to 45 and drops it into the hold's tail
wobble and the normal roll-out. It is a real menu, not just a banner: a highlighted
background-tile cursor box (`sub_802B8B0`/`sub_802BA24`, tile ids 0xA0AB/0xD0AB), text
from `TextScript86F0300`, sound effects 0x91/0x92 on cursor moves, and
`SetScreenFade(0x10, 8)` on the way out.
The banner half is nearly free — `src/banner.rs` already carries all 45 messages and the
freeze is one condition. Verify against a capture that presses Start mid-battle.

### B2. Panel damage  *(CLOSED, not reachable -- TRANSFER 7bg)*
DO NOT IMPLEMENT THE CHARGE-SHOT CLAIM. It was read to the end and it breaks at its own
citation. `Unk_03` was peeked and is 0 on every frame (0x02034123, MegaMan's slot) -- the
one part that was right -- so the shot really does carry `Param1` = 1. But `Param1` only
chooses the BRANCH: the default branch then overwrites r2 with
`[RelatedObject1Ptr]->CurState` and passes THAT to `object_setPanelType`
(asm31.s:27869-27873). The panel bookkeeping moves at the hit exactly as it should and the
type stays NORMAL. Only `Param1` in {7, 0x15, 0x16} cracks or breaks, and nothing this
build fields produces those. The charge shot joins the NOT REACHABLE list below.

Two harness notes from the attempt, both worth keeping: `--dump`'s byte count is parsed
with `atoi` and silently reads 0 from a `0x`-prefixed string, so it must be DECIMAL; and
holding B for 150 frames does NOT charge the buster on this fixture, because the Mettaur
re-tracks MegaMan's row -- oscillating rows every ~15 frames through both attack windows
and then holding still is what reaches a full undamaged charge.

The rest of the entry stands as the record of a well-cited claim that did not survive.

### B2 (original research, kept for the record)
`src/field.rs` carries the art for all five panel states and nothing drives cracked or
broken. The research says what is reachable and what is not, and the answer is narrower
and more useful than expected.

MEASURED, AND IT DOES NOT HAPPEN (2026-09-07). The claim below is a static read and the
capture refutes it. On the real ROM, from `/tmp/pausedwithcannon.state` with the enemy kept
alive: move MegaMan out of the shockwave's row so the charge is not interrupted, hold B for
150 frames, release. The charged hit lands visibly -- a starburst on the Mettaur -- and the
panel under it DOES NOT CHANGE, through 140 frames afterwards, with backgrounds on and a
400-pixel threshold on that panel's box. An implementation of the claim was written and
reverted unbuilt-upon rather than shipped.

So something in the chain below is wrong, and the most likely link is the one its own author
flagged: `Unk_03`'s value was inferred, not read -- "I could not find anywhere that resets
`Unk_03`". Before anyone tries again, PEEK IT: find `oAIAttackVars_Unk_03` for MegaMan's slot
in the save state and read what is actually there, and read the `Param1` the spawned shot
actually carries, rather than deriving both from the table. The rest of the entry is kept
because the lifecycle and movement findings are probably still good.

THE CLAIM AS ORIGINALLY RESEARCHED, now known not to reproduce: **MegaMan's CHARGE SHOT sets
the panel it hits straight to BROKEN.** The buster and charge shot both spawn the shared type-0 straight-shot object
(`sub_80C4F02`, asm31.s:27760); on a hit it switches on its own `Param1`, and the default
branch calls `object_setPanelType(hit_panel, Param1)` outright (asm31.s:27864-27874), gated
only on the panel being solid. The plain buster's `Param1` is 0x1d (asm31.s:12531), not one
of the five types, so it does nothing visible. The charge shot's comes from
`byte_80EBD34[Unk_03]` = {1,1,1,1,0xC,0xC,0xC,0} (asm31.s:109578-109611), and a base-tier
shot takes index 0 or 1 -- **1 is PANEL_BROKEN**. No cracked stage at all.

ALSO REACHABLE: the seeds stamp an AREA of panels to their terrain directly
(`object_setPanelType` in a loop, asm31.s:47200-47223, effect ids {4,7,6} for
poison/grass/ice at byte_80CE41E), and VDoll sets its landing panel to POISON
unconditionally (asm31.s:60531-60534). Both bypass the crack lifecycle entirely.

NOT REACHABLE, so do not build it: the Mettaur's shockwave CAN crack (`byte_80C6B00`,
asm31.s:31360-31366: `Param1==4` cracks, `==5` poisons) but `Param1` is the virus's Version
tier via an identity table (asm31.s:171288), and the Mettaur this build fields is Version 0
-- confirmed by its 10-damage shockwave. None of MiniBomb, EnergBom, MegEnBom, BigBomb,
BlkBomb, LilBolr, BugBomb or FlshBom contain any crack/break/setPanelType call at all.

THE LIFECYCLE, for whatever is built: broken goes back to normal after **600 frames** (480
if `GetBattleMode()==1`), from `sub_800C488` (object.s:1541-1549), with an alternating
"about to reform" flag over the last 60 (object.s:1458-1467). A broken panel simply REJECTS
movement onto it, like a wall -- the validity gate wants the solid bit 0x10
(`object_isPanelSolid`, object.s:2703; `playerObjectMovingToPanelValidityRelated_800E618`,
object.s:5112) -- rather than dropping anyone through.

TWO THINGS TO CONFIRM EMPIRICALLY BEFORE TRUSTING THEM. Cracked-to-broken is NOT a timer: it
re-arms every frame and instead tests a cached value against mask 0xF800000 (object.s:
1468-1490), whose bits the struct comments call "support object"/"enemy alliance"/"ally
alliance". Whether that means "somebody is standing here" or "this half of the field is
theirs" was NOT established -- and this project has already been burned once by an occupancy
rule that turned out not to exist (TRANSFER 7ai), so measure it. And nothing was found that
handles a panel breaking UNDER someone already standing on it.

VERIFY LIKE THIS: from `/tmp/pausedwithcannon.state`, fire an uncharged buster at the Mettaur
(expect no panel change), then a charge shot (expect its panel to go straight to broken on
the hit frame, no cracked stage), dumping the panel-type bytes before and after. VDoll can be
poked into the hand for the poison case.

### B3c. The `audio` check  *(resolved -- the check was wrong twice, the wiring's 13% was right)*
The suite hears. `check_audio` captures each side twice -- with the press and without -- takes the
residual sample by sample before the RMS (TRANSFER 7ax's method), and compares the two envelopes
over the sample's body. Want 23620, peak residual 4864 real against 4603 here.

IT FIRST DISAGREED WITH THE MEASUREMENT MADE WHEN THE SOUND WAS WIRED UP -- that one had ours 13%
LOUDER, this one had ours 5% QUIETER -- AND THE CHECK WAS THE ONE THAT WAS WRONG. It was not
soloing the FIFOs, so it measured the whole mix, and the buster's PSG FIRE blip has its own
residual in the same frames. That inflated the REAL side's peak from 3609 to 4864 and flipped the
sign. Soloing channels 4 and 5 (the harness's numbering) fixes it: 3609 real against 4603 ours,
ours louder, the same direction the original measurement found.

THE LESSON, and it is the audio version of a sampling error: a control-subtracted envelope only
measures one sound if that sound is the only one on the channels captured.

AND THEN THE MAGNITUDE WAS THE CHECK'S FAULT TOO. I suspected the real side's capture flags, and
measured it: `--zero`, the alive cheats and `--disable-bg` make NO difference at all, the envelope
is byte-identical with and without them. What differed was the WINDOW. Frames 14..29 here are the
same samples the other measurement called +19..+34 -- the two count "the press frame" differently
-- so this check began five frames after the onset and called a mid-decay value the peak.
Widened to 8..31 it reads 4074 real against 4603 ours: the wiring's numbers, to the digit.

SO THE ORIGINAL 13% WAS RIGHT AND BOTH OF MY CORRECTIONS TO IT WERE WRONG.

AND THEN THE 13% ITSELF WAS FIXED, from the ROM data rather than by fitting. The sound's M4A track
opens `0xBC 0x00, 0xBB 0x4B, 0xBD 0x00, 0xBF 0x40, 0xBE 0x70` -- KEYSH, TEMPO, VOICE, PAN, and
then **VOL 0x70 = 112 of M4A's 0..127** (data/dat37.s:41543, byte_81B8308, the track the
SongHeader for SOUND_HIT_6B points at). So the real ROM plays this sample at 112/127 of full and
this build played it at agb's default 1.0. Predicted 4603 * 112/127 = 4060 against the real 4074,
a third of a percent out; measured after the change, 4001 against 4074, within 1.8%.

AND IT WAS ALSO SIX FRAMES LATE. Printing both residual envelopes rather than only their peaks:

    real  96, 2, 855, 3661, 4074, 3756, 3489, 3468, 3609, 3171, ...   onset at press+10
    ours  0 x8, then 3558, 4001, 3102, 3651, ...                      onset at press+16

`BUSTER_HIT_DELAY` was 9, set against a frame accounting that counted "+k" from a different origin
than this check does. On the check's convention -- press+k on both sides, the same one `buster`
uses to compare the visuals at 0 -- it needed to be 4. Swept, and it is a clean minimum rather
than a plateau: 2 -> 25101, 3 -> 17738, **4 -> 11971**, 5 -> 13160, 6 -> 16607, 7 -> 22207.

`audio` 37223 -> 32562 (volume) -> 11971 (timing). WHAT IS LEFT is that THE REAL SOUND IS ABOUT
FIVE TIMES LONGER THAN OURS. Measured out to press+69, the real residual decays smoothly all the
way to zero rather than plateauing, so it is a sound and not control drift:

    press+8   96 2 855 3661 4074 3756 3489 3468 3609 3171 3188 3107 3007 2127
    press+22  1514 1023 673 701 684 668 662 531 417 329 235 199 206 203 187 293
    press+38  150 133 211 105 314 129 86 88 246 326 103 59 129 47 83 52 41 121
    press+56  37 27 13 20 13 27 23 13 0 24 0 0 19 0

Ours is silent from about press+21, which is right for the sample we play: 1881 samples at
10512 Hz is 10.7 frames. So the real ROM's response to a buster hit is NOT just SOUND_HIT_6B.

AND THE TAIL IS NOT A SOUND AT ALL -- IT IS THE METHOD'S NOISE FLOOR. Controlled for directly:
two IDENTICAL runs subtract to exactly 0, so the harness is deterministic; but a press that makes
NO SOUND (Up instead of B) still leaves 100-300 RMS, spiking to 516, because once the navi has
moved the background music mixes differently and the music is on the same FIFOs the check solos.
The "five times longer" tail was the same order as that floor.

The session that wired the sound up suspected exactly this and I argued against it, on the grounds
that the tail decays smoothly to zero rather than plateauing. A smooth decay to zero is what
divergence noise looks like too. The silent-press control is what settles it, and it should have
been the first thing measured -- it costs one capture.

`AUDIO_FRAMES` now stops at +24, where the sample's ~11-frame body has finished, and `audio` reads
7303 rather than 11971.

WHAT WAS RIGHT IN THE OLD ANALYSIS, kept because the reasoning stands on its own: That was the favoured candidate, mine and the sound-wiring session's
both, and the raw samples rule it out. Residual RMS per QUARTER-frame:

    +10 [662, 36, 16, 1578]      <- the sample's onset, mid-frame, sharp
    +11 [2833, 3482, 4193, 3988]
    +21 [2437, 2114, 2033, 1884]
    +23 [1197, 973, 1151, 695]
    +24 [636, 533, 788, 709]     <- the plateau begins, with NO rise
    +28 [741, 655, 629, 616]
    +31 [408, 343, 273, 273]

A second sample starting at +24 would show an onset like +10's -- a quarter-frame jump of several
thousand. There is none anywhere after +10. The tail is one sound decaying, holding around 600-800
for five frames, then decaying again.

SO WHAT IS LEFT: the real ROM's ONE sound lasts about five times longer than the 1881-byte sample
this build exports and plays. Look at the note command in the track rather than the wave: the
track is `0xDB 0x3C 0x7F 0x8C 0xB1 0x00` (data/dat37.s:41543-41544), where 0xDB is one of M4A's
fixed-duration note commands and 0x3C/0x7F are key 60 and velocity 127. Work out that duration and
what the engine does when the note outlasts its sample -- whether the WaveData loops after all
(this build reads type/status 0 as "no loop"), or the engine holds and re-triggers. That is one
number in the ROM and it decides the whole question.

### B3b. The next sound needs a DirectSound sample exporter  *(exporter DONE; wiring left)*
The buster's FIRE is done (PSG channel 1, matched at +7/+8). The buster's HIT is NOT a blip: it
is on FIFO channels A and B and silent on all four PSG channels, so it is a DirectSound SAMPLE
(TRANSFER 7bb). An attempt to fake it on the noise channel measured 27x too loud and was
reverted.

So the next step is an exporter: read a `WaveData` header and its PCM out of `data/dat37.s`
(`SOUND_HIT_6B`'s is already decoded end to end -- `byte_81597A0`, 1881 bytes, 10512 Hz, no
loop), wrap it as a WAV, and play it through agb's existing mixer with `include_wav!`. agb's
mixer takes 8-bit PCM at 10512/18157/32768 Hz, and 10512 is exactly what the game uses.

AND SOLO FIRST, ALWAYS. `--audio-channel`'s table is 0-3 PSG, 4-5 DirectSound; the numbering is
the harness's, not the hardware's, and reading "channel 4" as "the noise generator" is what
produced the reverted attempt.

DONE: `tools/sample_export.py` and `assets/buster_hit.wav`. The header was verified from the
bytes three ways rather than trusted -- 10512.0 Hz exactly, size 1881 agreeing with the
spacing to the next label in dat37.s, and no loop bit under any convention. NOTE that the
disassembly has NO `WaveData.inc`: it is asm-only and never grew C structs for the sound
engine, so the 16-byte layout comes from the stock M4A struct every GBA game shares, cross
checked against this blob. The signed/unsigned step is the one that bites: GBA WaveData is
SIGNED 8-bit and WAV stores 8-bit UNSIGNED, so the exporter adds 128; skipping that makes
hound subtract 128 a second time and turns silence into full negative -- the DC buzz.

WHAT IS LEFT is src/ work and it is structural: `Battle::update` takes `(&input, &gfx)` and
no mixer, so playing a sample means threading a `&mut Mixer` through it, adding
`mixer.frame()` to the per-frame loop, and measuring the hit's own delay the way
`BUSTER_BLIP_DELAY` was measured (7bb puts the FIFO activity at +11..+23, peaking at +16,
which is NOT the fire blip's delay). `include_wav!`'s path is relative to the crate root, so
it is `"assets/buster_hit.wav"` with no `../`.

### B3a. Sound: the harness can hear now  *(the research is done)*
`tools/mgba_capture.c` has `--dump-audio` and `--audio-channel`; see TRANSFER 7au for the two
gotchas (the advertised 65536 Hz is really 96000, and `struct mCore` has a `USE_DEBUGGERS` ABI
trap). The engine is stock Nintendo M4A, agb's mixer sets up the same DMA/FIFO/timer registers,
and nothing in this project competes for them.

The smallest first step is NOT "export a sample": the buster's fire sound is a PSG square/sweep
blip on channel 0, confirmed empirically. agb had no PSG API when this was written -- there is one
now, `vendor/agb/agb/src/sound/psg.rs`, added for that blip -- so a first sound meant either
a small hand-written PSG driver (register pokes on 0x4000060-0x4000075, in the style
`vendor/agb/agb/src/sound/mixer/hw.rs` already uses for DirectSound) or picking a confirmed
DirectSound effect instead -- `SOUND_HIT_6B`'s sample is already decoded end to end: WaveData at
`byte_81597A0`, 1881 bytes, 10512 Hz, no loop.


## C. Research tickets — read-only, no build, good to run several at once

### C1. How many frames into a battle does BATTLE START! go up?  *(answered -- TRANSFER 7aw)*
`/tmp/battlestart.state` exists now. The answer: it does not follow the intro at all, it follows
the FIRST CHIP WINDOW -- thirty frames after that window closes. The build was corrected and lands
within a frame of the real ROM. The same state also showed that a battle OPENS with the chip
window, which this build was getting wrong by 1260 frames.

Still open from the same state: our window opens at 134 against the real 173, because the captured
battle fields three Mettaurs and this one fields one. A fixture with a matching line-up would
settle the intro's length and the screen fade's real frame count in one go.


### C2. The last frames before the RESULT window  *(mostly traced -- TRANSFER 7bf)*
STATES 6-9 ARE A DEAD END: `off_8008038` is the generic banner sequencer for every message
in the game, and 6-9 are a sibling branch entered only when `sub_800A152()` returns 7, a
different outcome. They never run on an enemy kill.

THE COUNTDOWN IS 94, NOT 102. State 3 picks 0x5e or 0x66 on `BATTLE_EFFECT_SHOW_RESULTS`
(asm00_1.s:10580-10592), and the field-encounter `BattleSettings` row has that bit set
(data/BattleSettings.s:6). So the expiry is 49 + 94 = 143, not 151, and the banner's idle
at 106 is not the binding constraint. Dispatch out of state 3 is free.

WHAT IS LEFT is 14 frames, not 8: the reward tally in `sub_8009478` (asm00_1.s:13129),
waiting on two sentinels driven by a fixed 5-step transfer-buffer decrement
(asm01.s:254-258). Settle it by dumping `dword_203F4A0` and `dword_203F5A0` frame by frame
from 143. This build's measured 110 is unaffected either way, so this is derivation for its
own sake and ranks below anything visible.

### C3. The emotion window  *(researched; see TRANSFER 7at)*
Answered: only Calm and Angry are reachable without a Cross or a Navi Customizer bug, and Angry
needs ~120 continuous frames of hitstun or a single 300+ damage hit, which a Mettaur's 10-damage
shockwave will not produce. So this build's single face is very probably correct for the battle it
fields, and implementing Angry is not worth it until there is an enemy that can trigger it. What
IS worth doing cheaply: `tools/emotion_export.py` takes only state 0's tiles and state 0's palette,
and the other 22 states sit right after at a fixed stride -- exporting them is mechanical.


### C4. Does the chip-name popup's gate match ours?  *(answered -- TRANSFER 7be)*
KEEP THE PROXY. `object_drawChipName` gates on nothing about the chip: `sub_800B892` is a
per-alliance announcer-slot sync byte (object.s:934-939) and `ChipData+9` bit 1 only adds a
damage number beside the name (object.s:210-217). Which chips get a popup is decided by
which OBJECT the chip spawns -- 16 phase tables in the ROM, all of the same shape. 84 of
411 chips carry family 0x15 and they group into exactly those tiers.

WHAT IS LEFT, and only when a trap chip is implemented: those 84 split by `ChipData+9`
bit 1 into "no number" and "number" (Mine, TimeBom, AirRaid, Guardian, AntiDmg, ElemTrap,
...). `NamePopup` draws letters only, so the first trap chip needs one exported bit per
chip and a number in the popup.

---

## D. Harness

### D1. Track the residues in `regress.py`  *(done)*
`mettaur` (345) and `wave` (960) both have checks, alignment done the 7ah way, wants
measured rather than copied. A `cursor` check was added too. Fifteen checks now.


### D5. A short capture used to pass for a real result  *(fixed)*
`capture()` ran mGBA and never checked it wrote the frames it asked for. Under load it
sometimes does not, and a short capture does not announce itself: the frames that exist
compare normally, and the missing ones either raise a FileNotFoundError deep inside a check
or are never asked for at all -- which means a truncated capture can produce a WRONG NUMBER
rather than an error.

Twice on 2026-09-07, a full suite run alongside other heavy work reported failures that did
not reproduce on a quiet re-run: `chips` 10 of 43 off, and `opening` erroring on a missing
frame 148. Both were this. FIXED: `capture()` counts the `.rgb` files and refuses to continue
if the count is short, naming the directory and telling you to re-run it alone.

WHAT IS STILL TRUE AND MATTERS: the suite is not trustworthy while the box is busy. That is
now loud instead of silent, but it is still the case, and the two spurious runs cost more
attention tonight than the bug they pretended to find.

### D4. FIVE CHECKS COMPARED A SINGLE FRAME  *(three widened; two cannot be, for different reasons)*
`tiles`, `field`, `window`, `card` and `result` each match ONE frame and report 0. A single
frame can be right while its neighbours are wrong, and at least one of them demonstrably is.

Measured on `field`, which searches rust 190..240 for the best match against real frame 90:
the winner is exact (rust 212, 0 px), and holding that same lag the next twenty frames read

    0  765 1243 1371 1371 1596 1236 1340 1215 1215 986 582 622 364 364 364 364 838 800 800

Part of that is legitimate -- the Mettaur acts on an RNG the two sides do not share, which is
exactly why `mettaur` and `wave` search for a lag around a specific attack instead of trusting
a fixed one. But "one frame in fifty matched exactly" is a weaker claim than `field 0` sounds,
and nobody looking at the suite would know the difference.

DONE, WITH TWO EXCEPTIONS THAT ARE THE INTERESTING PART.

`window` and `card` are now sixteen frames each with a searched lag, and `window` CAUGHT
SOMETHING: a single frame could not tell lag 181 from lag 182, both being exact at frame 59, so
the check had been sitting on the wrong alignment. Over sixteen frames 181 measures 184 px -- the
bracket's blink toggling one frame out, 92 px a toggle, twice -- and 182 measures 0. Nothing could
have seen that from one frame.

`tiles` is a window now too (390..394 originally, 433..437 today) but for a different reason -- to
absorb boot drift -- and it still compares ONE frame's worth of picture.

`result` CANNOT be strengthened this way, and the check now says so in its own comment. Measured:
over real frames 24..39 the compared region does not change at all, every consecutive difference
is 0. Sixteen frames of a still picture is one frame. Strengthening it needs a window covering the
RESULT screen ARRIVING -- the slide-in, the badge appearing -- and that needs a real capture from
before the window opens, which this fixture's save state does not provide.

`field` cannot either, for the opposite reason: it is too dynamic. Holding its best lag, the next
twenty frames run 765, 1243, 1371, 1596, ... because the Mettaur acts on an RNG the two sides do
not share. It needs an alignment like `mettaur`'s, or a window that ends before the enemy's first
independent decision.

### D3. `--dump`'s byte count silently reads 0 from hex  *(fixed)*
`tools/mgba_capture.c`'s `--dump addr:bytes:file` parses the middle field with `atoi`,
which returns 0 for `0x1c0` and dumps an empty file with no error. The address beside it
uses `strtoul(..., 0)` and does accept hex, so the two halves of the same argument disagree
about their base -- which is exactly the sort of thing that costs an hour. Found during B2.
FIXED: the count uses `strtoul` base 0 as well, and a non-positive count now prints what it
rejected and exits 1 rather than writing an empty file and reporting success. Verified both
ways round -- `0x10` and `16` both dump 16 bytes, and `zero` is refused.

### D2. Make the harness clean up after itself, everywhere  *(done)*
`regress.py`'s rollup check, `chip_compare.py --clean` (which `scoreboard.py` now always
passes) and `throw_dump.py` all delete their captures. `--clean` is opt-in for
`chip_compare` rather than the default because `--no-build` reuses the previous run's
Rust capture. What is left: the ad-hoc capture directories a person makes by hand, which
is what actually filled the disk.
