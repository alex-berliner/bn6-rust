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

- R1 DONE -- Rebuild the fixture chain from power-on. 
- R2 NEGATIVE -- Move the chip rows onto the never-had-an-enemy fixture. At the event-pinned alignment (canon CurState leaves 0x0804 at frame 3
- R3 PARTIAL -- A battle that never spawns an enemy. The roll's choice lands in `GameState->CurBattleDataPtr` at `0x02001b9c` (stored at
asm29.s:10286, read by `sub_800531C` asm00_1.s:4455)
- R4 BLOCKED -- Keep the enemy-less battle alive, then finish R3. Step 1 done, and it overturns the recon: none of the five literal `SubsystemIndex=0x10`
stores, the warp entry, `cs_warp_cmd` or the script 
- R5 PARTIAL -- A write watchpoint in the capture tool, then find what releases the empty battle. Step 1 done, verified, committed (17dc00f, plus HANDOFF §5 row)
- R6 NEGATIVE -- The state oracle: first divergent field, not just a pixel count. On `wt/r6-oracle` at `c504eee`, the export was pixel-neutral: `wave` 0/0/90 (negative 3840), `window` 0/0/16 (81056), `mettaur` 30864/1566/7
- R7 DONE -- Land the state oracle on the facts R6 found. Merged `a9d08b7` as `2b35d4b`
- R8 WITHDRAWN -- Usage logging: primitive profiles for the 43-chip corpus. 
## F. Convergence: every existing row to 0 differing frames before anything new (user, 2026-09-12)

Tickets run in this order; the coordinator takes the first OPEN one. Queue by leverage, from the
2026-09-12 full table (isolated unless noted): F4 opening 1160 (was 0) -> F5 the chip-row fixture
(28 rows at exactly 14388, 11 more above it) -> F6 tiles/gauge 538 (one capture, two rows) -> field
1048 -> banner 2248 -> buster 3172 -> warp 9198 -> card 18486 -> mettaur 31075 -> F3 (the chip window's
ghost; adds its row) -> popup 107511 -> result 497967 -> cursor 620802 -> the integrated variants.
No new content (viruses, bosses, chips) until the table is at zero. A reported 0 always says what it
compares: canon vs ours, or before vs after.

- F1 DONE -- MegaMan takes a hit one frame late. PARTIAL
- F2 DONE -- The mettaur row compares the wrong Mettaur attack. DONE and merged as `332e658`
- F4 DONE -- The opening row reads 1160 px since R1 rebuilt its canon state. The 1160 was the FIXTURE, not the opening
- F5 PARTIAL -- The chip rows' fixture: fire a chip after the corpse has dissolved. The prescribed route is dead, the gate is found (with corrections), and the next
intervention is named but untested
- F5b DONE -- Fire a chip in state 0x0C by delivering the press to MegaMan's AIData directly. The Sol-named gap closed with a measured fire
- F6 DONE -- tiles/gauge isolated: 538 px over 8 frames. Landed at the documented residue
- F3 DONE -- After the chip window closes, a faded copy of it stays on the field. The ghost is gone by mechanism, not masking
- F7 DONE -- The legacy `cannon` row still compares against PAUSED: 14388. Exactly as predicted: `cannon` re-pointed onto F5b's route and Align (`_chip_canon_0c("01")`
+ `ALIGN_CHIP_0C` on `afterdissolve_0x0c`), 143
- F8 DONE -- `field` isolated: 1048 px over 40 frames. DONE
- F9 DONE -- `banner` isolated: 2248 px over 58 frames. DONE
- F10 BLOCKED -- `buster` isolated: 3172 px over 32 frames. BLOCKED after the second miss, moving on
- F10b BLOCKED -- `buster`: fire in the 0x08 window with the miss-pose fix, or close the row. 
- F11 DONE -- `warp` isolated: 9198 px over 30 frames. DONE
- F17 DONE -- `mettaur` isolated: enemy_anim k=61, the Mettaur's own animation. mettaur 19698/1245/70/60824 unchanged pixels, oracle enemy_anim 2/70->1/70 (first k=61, mm_timer 70/70)
- F20b DONE -- `tiles`/`gauge` integrated: match the fixture's sprite positions to canon's state. tiles/gauge integrated 25979/3282->3865/678/8 (negative 15891 not blind), isolated still 0/0/8
- F21 PARTIAL -- `result` isolated: 497967 px over 40, its canon side is result_arrival. result 497967/31882/40/476424 -> 408337/31895/40/383600 (-89630)
- F22 NEGATIVE -- `cursor` isolated: 620802 px over 170 frames. cursor 620802/6884/170/728447 unchanged (nothing landed, branch empty, deleted)
- F22b NEGATIVE -- `cursor` isolated: match the x>=112 unshared mid-battle content on the fixture side. cursor fixture backdrop-seed probe refuted, nothing landed
- F18b PARTIAL -- `windowclose` isolated: the k=11 transient and the slide residue outside the window layer. windowclose 666451/28784/40->651885/28430/40 (k=11 BG3 transient 2447->0
- F18c PARTIAL -- `windowclose` isolated: the relocated k=9/k=10 close-frame blank/redraw. windowclose 651885/28430->650544/27555/40 (BG3 k9 1898->0, k10 1408->0, k11 0->1596
- F18d DONE -- `windowclose` isolated: the k11 gauge-body single-step redraw. windowclose 650544/27555/40->648948/27391/40 (BG3 k11 1596->0, x48-191 y0-15)
- F21d DONE -- `result`: write the window's tilemap by block copy, not 576 managed tile writes. result 408337/31895->102547/14866/40 (neg 195579 not blind), field 1048/177->0/0/40
- F12 DONE -- The chip rows' own residues, family by family -- multi-pass, stays OPEN until every chip row is 0. every chip row reads 0: the last two were areagrab (orb draw order + burst palette walk, ad653c0) and chip-use, re-cut F31b-style so canon f
- F33d PARTIAL -- Post-0x0C simulation: act after the countdown starts instead of freezing in `over`. verifier verdict: canon citations CONFIRMED (sub_800801C:10422, off_8008038 table, sub_80081A4:10617, 0x0C@0x0800811E, sub_8012DFC:8977 not 
- F37 PARTIAL -- `cursor` and `windowclose`: the sprite layer, object by object. per-object tables landed 1bee9d8 (notes only, descriptors untouched): cursor 154361/909/170 (camera-pan +15Y + Mettaur pose 4,11-vs-4,8), wi
- F37b PARTIAL -- `cursor` and `windowclose` to 0: the camera pan while the chip window is open, the Mettaur's held pose, the hand icon and bracket. pan+pose+icon landed a6bf21c: cursor 154361/909/170->130221/767/170, windowclose 27819/1938/40->19168/1878/40 (neg 316499/214890 not blind)
- F37f PARTIAL -- `windowclose` k=0..9: the 162 px marcher on the slide frames (custom.rs). mark-during-Closing KEPT unmerged (branch wt/f37f 0c05e00, custom.rs only): windowclose 1458/162/40->0/0/40, cursor 20->3/3/170
## T. Trace-driven porting (phase "porting", 2026-09-14; the plan in HANDOFF §1)

**Common to the T tickets.** The harness rows stay as free regression tests (every landing runs verify_rows on
wave, window, mettaur, popup, buster, result, field and the row a ticket names). Acceptance in this phase is
stated as state parity: "first divergence at frame N or later on scenario S", with pixels as the gate on the
same recording. Canon never changes; provenance rules as before; cite reference/bn6f file:line.

### T9b. The second virus (Gunner): widen the fixture to field a non-Mettaur, build the canon recipe, port its routine  *(OPEN -- 2026-09-14)*

**Files.** src/fixture.rs (enemy_kind honoured), src/battle.rs (the fixture's enemy construction: art, style and per-type entry chosen by enemy_kind), src/objects.rs, src/ai.rs, assets/ (Gunner art extracted from the ROM), tools/states.py (the recipe), tools/harness.py (the new row), FIXTURE.md, docs/coverage/

**Why.** T9 measured the two blockers and could not touch them: (1) our fixture ignores enemy_kind
(FIXTURE.md defines kind 0 only; src/battle.rs hardcodes the Mettaur's art and Style::Mettaur), so no
Gunner row can exist; (2) on the canon side the encounter roll must be set BEFORE frame 60 builds the
enemy list: the chosen BattleSettings pointer at 0x02001b9c (GameState+0x1c) goes 0 -> 0x080b4be8 on
frame 60 (= byte_80B5354, the three-Mettaur record the battlestart recipe already forces; 16-byte records;
index 6 = 0x080b4bd8 = byte_80B5347, Mettaur+Gunner 0x85); a poke at frame 61 sticks but the slots stay
empty because the list is built from the rolled pointer inside frame 60. Use the battlestart recipe's own
mechanism (its one-shot roll poke at frame 60 with EnemySetupArr) with index 6's record instead, and
confirm the slots (panel 0x0203aa9a / 0x0203ab72, NameID 0x0203aab0 / 0x0203ab88) are populated.
**Do.** (1) tools/states.py: a `battlestart_gunner` recipe forcing record index 6 at frame 60; confirm the
enemy slots and record the Gunner's per-type routine from the coverage ranking on that scenario;
(2) src/fixture.rs + src/battle.rs: enemy_kind selects art, style and the per-type entry (kind 1 = Gunner),
FIXTURE.md updated; (3) src/objects.rs + src/ai.rs: the Gunner's routine ported under enemy_think/
enemy_act with its art extracted byte for byte; (4) tools/harness.py: one row aligned by the Gunner's first
attack event, negative not blind. **Acceptance.** the new row 0; the trace's enemy slot matching canon from
spawn through the second attack on the Gunner scenario; every existing row unchanged (the Mettaur rows in
particular, kind 0 unchanged); docs/coverage/<scenario>.md.

### T8. Port the script VMs, per section 3 of the plan (map-script and chatbox text-script dispatch)  *(DONE -- 2026-09-14, Landed 752146e [branch wt/t8-script-vms @ cdd976e])*

**Result.** Landed 752146e (branch wt/t8-script-vms @ cdd976e). src/script.rs: MapScriptCommandJumptable ported as 71 variants (canon mov r4,#70 bound, map_script_cutscene.s:1371, leaves the 0x46 arm unreachable), TextScriptBytecodeJumptable as 27 variants indexed byte-0xE5 (chatbox.s:390-472, :545-547), eMapScriptState 0x02011E60, operand sizes from each handler's cursor arithmetic; the map/text opcodes battle_full and result exercise are implemented, everything else a named Trap carrying canon's symbol (first stop: ms_start_cutscene 0x26 at ContinuousMapScriptPtr 0x08072221). Harness (verify_rows, clean checkout, 60 rows): every isolated row 0/0 with non-blind negatives EXCEPT cursor 44/43 -> 7/6, frames 170 and negative total 186276 unchanged; rollup 'all checks pass'. Verifier (hyper/glm-5.3-flash): CONFIRMED the cursor move is binary-layout sensitivity, NOT the VMs executing -- it built the control (if false { step_frame }) in its own worktree and got total 6/6, then re-ran the SAME branch binary and also got 6/6, so VM-on vs VM-off is 0 pixels and within run-to-run wobble (+-1 positive pixel, +-4 negative); CONFIRMED first divergence unchanged (trace.py record rust battle_full 540 frames, diff vs /tmp/tr_c_bf --align row:battle_full -> enemy_state_action k=0 canon frame 11 canon=(4,10) rust=(4,0), mm_state_action not until k=179); CONFIRMED the 27-variant text table and its byte-0xE5 index in the disassembly; rules audit CLEAN (src/battle.rs touched only at the use/mod/field/single step_frame hook, no allowlist widened, no region shrunk, provenance tags present, reference/bn6f untouched). UNCHECKED by the verifier, left as a named gap, not a blocker: the exact mov r4,#70 line in RunContinuousMapScript's dump (script.rs:91-94 quotes a consistent sequence) and the claim that the 0x08072221 stream decodes down to opcode 0x26. Audit line fitted constants 19 (derived 414, peeked 145) vs main's (derived 373, peeked 142). Unverified: which later screen first reaches a Trap. Child qwen3.8-flash, 114 turns, $0.245.
**Files.** src/script.rs (new), src/battle.rs (only where a script is started or stepped), tools/trace.py (progress notes go in this ticket's Result, not the plan file)

**Why.** The third interpreter in docs/coverage/plan-interpreters.md section 3: the map-script VM and the
chatbox text-script VM with their opcode dispatch tables (3.1, 3.2), the lowest-priority of the three
because battle_full barely touches them, but the battle's chip descriptions, the results screen's text and
every later screen run on them. Port the opcode dispatch and the handful of opcodes battle_full and the
result row exercise, in the order 3.3 gives, verified per 3.4.
**Acceptance.** the dispatch tables ported with citations; the opcodes battle_full/result exercise
implemented and the rest stubbed with a named trap; full table identical; the trace's first divergence
unchanged or later; plan notes.

### T9. The second virus as a ported per-type routine, from a real battle recording  *(BLOCKED -- 2026-09-14, Blocked on a file-set widening I cannot grant)*

**Result.** Blocked on a file-set widening I cannot grant. Baseline on the clean tree: 30 rows PASS 0, cursor isolated FAILED 44/43/170/186276 (pre-existing). No Gunner row exists because the fixture cannot field a non-Mettaur: FIXTURE.md defines enemy_kind 0 only and src/battle.rs's fixture enemy construction hardcodes METTAUR art + Style::Mettaur, ignoring enemy_kind; src/battle.rs and src/fixture.rs are not in T9's Files. Measured instead: 0x02001b9c (GameState+0x1c, chosen BattleSettings ptr) goes 0->0x080b4be8 on frame 60 = byte_80B5354 (the 3 Mettaurs battlestart documents), confirming 16-byte records / index 6 = 0x080b4bd8 = byte_80B5347 (Mettaur+Gunner 0x85) and index 10 = 0x080b4c18. Decision-2(b) as handed does NOT work: a poke-at 61:0x02001b9c:0x080b4bd8 sticks (held to 118) and the transition runs 4->8->0xc, but all three enemy slots are empty at battle time (panel 0x0203aa9a/0x0203ab72=0, NameID 0x0203aab0/0x0203ab88=0) because the enemy list is built from the rolled pointer INSIDE frame 60; the frame-60 store order (or a latch at 0x02001c2c) is the next unknown, and the option-(a) roll sweep was never run (wrong capture CLI shape). Art provenance UNVERIFIED: assets/gunner.bin 4588B / cursor.bin 628B / impact.bin 2722B are not verbatim in the ROM, but neither is the known-good assets/mettaur.bin (art is LZ77 in ROM, decompressed in tree), so the only valid check is spr_dump at the Gunner's art address off GunnerEnemyStruct2_8112B9C (asm32.s:9538), not yet located; landing commit c99cece cites AI addresses and HP 0x3c but NO art address, and main.rs:84's GUNNER static is imported by nothing. Ask for the user: widen T9 to src/battle.rs + src/fixture.rs (~6+3 lines in the fixture enemy build at battle.rs ~1807 for a kind->(spr::GUNNER, ai::Style::Gunner) match, ~2 lines in fixture.rs/FIXTURE.md to allow kind<=1); everything downstream stays in the named files.
**Files.** tools/states.py (a recipe for a canon battle that fields the virus; the trace scenario is a states.py recipe, do not edit tools/trace.py), src/objects.rs (the per-type entry), src/ai.rs, assets/ (its art extracted from the ROM), tools/harness.py (a new row and its fixture), docs/coverage/

**Why.** T6 made the Mettaur canon's routine under the ported dispatcher and player; the next virus is
the test that content is now data. Pick the first virus the overworld_net route can field cheaply
(read the fork's enemy tables; the encounter roll's orbit trap is in reference/bn6f's notes: F-series
recipes force the roll at battle frame 60), build the recipe and a scenario, record canon's trace
(the enemy slot's state/action/timers from spawn), locate its per-type routine in the coverage
ranking for that scenario (tools/coverage.py), port it under enemy_think/enemy_act with its art
extracted byte for byte, and add one harness row for it (aligned by its first attack event).
**Acceptance.** the new row 0 (negative not blind); the trace's enemy slot matching canon from spawn
through its second attack; every existing row unchanged; the coverage table for the scenario in
docs/coverage/.

### T6. The Mettaur as canon's per-type routine: replace the hand-written brain with the ported AI entry  *(DONE -- 2026-09-14, Mettaur brain now canon per-type entry MettaurEntry ForMettaur_8109EF4 [objects.rs], hand-written MettaurState)*

**Result.** Mettaur brain now canon per-type entry MettaurEntry ForMettaur_8109EF4 (objects.rs), hand-written MettaurState removed (ai.rs), battle.rs 1 comment line, plan notes S2.6. verify_rows: full isolated table 0 except cursor 44/43 MATCH (same k37+k97 tear, reported not chased); both-rows field/warp/buster/opening 0; negatives not blind. Trace: mettaur 70/70 clean, battle_full first divergence unchanged k=0 (4,10)/(4,0). GLM verifier CONFIRMED claims 1,2,3,5; claim 4 (opening-baseline byte identity) corroborated via opening 0/0/40 + history. Merged c31c8cb; post-merge HEAD verify PASS identical numbers. Worker muse-spark-contrib $0.0899; land.sh reused a same-sha .pass from an earlier partial row set and wrote 'skipped' -- caught, HEAD re-verified, message amended, stale .pass removed.
**Files.** src/ai.rs, src/objects.rs (the per-type entry for the Mettaur), src/actor.rs (only the calls the entry makes), tools/trace.py, docs/coverage/plan-interpreters.md

**Why.** T5 landed the object dispatcher (objects.rs: battle_common_path / enemy_think / enemy_act / the
per-type entries) and T4/T4b the animation player, so an enemy can now be canon's routine rather than
ours. The Mettaur's brain in src/ai.rs is a hand-written state machine tuned to canon's counts (F17, F25,
F28: sub_8109DEC / sub_8109CBC / sub_810A004 and the RunAIAttack chain in the plan's section 2). Port
that chain as the Mettaur's per-type entry: the AI state table, the wait/align/hop/swing/shockwave states
and their counters read from the same fields canon reads (the BattleObject's AI data), driven through
enemy_think / enemy_act, with the hand-written state machine removed behind the same interface.
**Acceptance.** mettaur 0/0/70 (negative not blind), wave 0, tiles/gauge integrated 0, popup 0, cursor and
windowclose unchanged (the pause pose comes from the same routine now); the trace on battle_full and on
mettaur: the enemy slot's CurState/CurAction/timers match canon frame for frame from spawn to the second
attack (first divergence unchanged or later); every other row 0; plan notes.

### T7. The battle end as canon's sequencer table: banner states, teardown, results hand-off  *(PARTIAL -- 2026-09-14, Sequencer states + TRC2 v3 export landed pixel-neutral [verify_rows: isolated all 0 incl mettaur, cursor 10/9 )*

**Result.** Sequencer states + TRC2 v3 export landed pixel-neutral (verify_rows: isolated all 0 incl mettaur, cursor 10/9 tear-smaller, both-rows 0; negatives not blind) but headline trace evidence NOT reproducible: retained rust records are v2, sequencer judge false-greens on missing field, --align sequencer= crashes (StopIteration). GLM verifier CONFIRMED scope (battle.rs/harness-notes/trace only, no allowlist change) + parity divergences (enemy k=0, mm k=179, rng k=271), REFUTED sequencer 239/239 + kill-slide gap as reproducible. Branch wt/t7 @7b984df kept unmerged. Follow-up T7b written.
**Files.** src/battle.rs (the end-sequence hunks), src/banner.rs, src/results.rs, tools/harness.py (the integrated rows' notes), tools/trace.py

**Why.** The five integrated variants (opening 72499, field ~158k, warp 40628, buster 54672, chip-use
275307) wait on one mechanism: canon's banner sequencer is a state table (sub_800801C, asm00_1.s:10422,
dispatch through off_8008038; the 0x0C handler sub_80081A4 :10617 does the HUD teardown; the ENEMY DELETED
banner element runs 49..106; the results driver sub_802BD60 starts the slide at 154 on every zero-enemy
row, F32b/F38 measured) while ours is a hand-written sequence with BANNER_TO_RESULTS and a single `over`
flag, which F33c/F38b showed cannot be made to fit per fixture. Port the sequencer as the state table with
its per-state counts and handlers, the trace's sequencer field (dword_203CA70) as the acceptance: the
state sequence and frames from the killing blow to the results window's first slide equal on both sides.
**Acceptance.** the sequencer trace equal on battle_full and on warp/buster/chip-use integrated; those three
integrated rows 0 or their per-frame remainder against F34's chain; result, popup, banner, field isolated
0; opening integrated re-measured; allowlist entries removed only for rows that read 0; nothing worse.

### T7b. Re-establish the sequencer evidence: fresh v3 traces, loud judge, kill-to-slide gap  *(OPEN -- 2026-09-14)*

**Files.** tools/trace.py (judge + align fixes only), src/battle.rs (only if the re-measurement indicts the Sequencer transition), docs/coverage/plan-interpreters.md (notes)

**Why.** T7 (PARTIAL, branch wt/t7 @ 7b984df kept unmerged) landed the Sequencer states and the TRC2 v3
export pixel-neutral (verify_rows: every isolated row 0 including mettaur, cursor 10/9 tear-smaller,
both-rows 0) but its headline evidence is not reproducible: every retained rust record is TRC2 v2, the new
sequencer judge reports "match" when the rust side lacks the field (false-green), and `--align sequencer=`
crashes with StopIteration (verifier REFUTED the 239/239 + kill-slide gap as reproducible; CONFIRMED scope
and the parity divergences enemy k=0, mm k=179, rng k=271). Base your worktree on wt/t7 (merge it into
your branch; do not merge anything to main), re-record rust v3 traces (battle_full, mettaur, popup,
result) and retain them with the report, fix the judge to fail loudly on a missing/mismatched-side field
and fix the align crash, then re-measure: battle_full sequencer k-ranges, mettaur/popup 70/70 + 80/80,
result 40/40 structural divergence, kill-to-slide gap on both sides (worker asserted canon +107 vs ours
+132: treat as unmeasured until you measure it).
**Acceptance.** fresh v3 rust records retained and named in the report; sequencer trace equal on battle_full
(or k-ranges re-measured with the remainder named frame by frame); judge false-green fixed and align crash
fixed; kill-to-slide gap measured both sides; warp/buster/chip-use disposition unchanged (F34 ramps);
result, popup, banner, field isolated 0; nothing worse.

- T4b DONE -- Port the animation bytecode player, steps 3 and 4 of the plan. T4b steps 3-4 landed 6a2876e (was wt/t4b f86acb6): alt stream, setAnimation/Unk_00, updateSprite gate + variants
- T5 DONE -- Port the object dispatcher, per section 2 of the plan. T5 dispatcher landed 163293b (was wt/t5 e17d8d3): objects.rs battle_common_path/enemy_think/enemy_act/t1_player_entry/t3_entry

**Common to F8-F23 (and their b-tickets) unless the ticket says otherwise.** Baseline the row (harness line plus
`tools/diffmask.py` region, plus `tools/oracle.py` where the row is supported); localize the residue to
frames and an element; find canon's routine for that element in reference/bn6f and cite it; fix src/
(or the fixture/descriptor when the residue is the fixture, with `peeked` provenance); re-run the row,
wave, window, opening, chip-cannon and the full table -- nothing may get worse, and a row that does is
reported with its numbers. No allowlist change; no alignment or region change except by measured event
(F2's rule). **Coordinator:** verify_rows on every row the report names; the verifier only for claims
beyond harness lines; a PARTIAL from a wrong guess about the cause gets one follow-up ticket; if that
also fails, mark the ticket BLOCKED and move on to the next OPEN ticket.

