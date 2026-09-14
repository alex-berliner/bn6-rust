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

- T12 DONE -- The enemy roster out of the ROM's own index tables: every enemy_idx with its think and act entry. LANDED as 1d23394
- T7d PARTIAL -- Drive the sequencer's window states with a fixture that closes the window, and put canon's predicates under the edges. Kept UNMERGED at wt/t7d @ 24d9ef7 (8daa88d + 24d9ef7 on a merge of wt/t7c @ 9be540c)
- T9c PARTIAL -- The Gunner: implement what T9b measured (the frame-60 lever, enemy_kind, the routine, the art, the row). CORRECTION (re-stamps my earlier entry, which cited verifier findings before the verifier had returned -- the merge message 1f7efc9's claim 
- T10 DONE -- Inventory of the battle engine from the ROM's own tables: the completion checklist gets its counts. LANDED as d0e0574 (two passes: 3723b5d + fix 82c31bd)
- T7c PARTIAL -- The sequencer's missing states: the custom-screen states our side never reads, and the end edge nine frames early. Kept UNMERGED at wt/t7c @ 510b5c6 (2 commits 3def49e, 510b5c6)
- T9b PARTIAL -- The second virus (Gunner): widen the fixture to field a non-Mettaur, build the canon recipe, port its routine. Measurement pass, zero edits (worktree /tmp/bnwt/t9b-gunner clean at 974f154) -- T9's blocker is SOLVED and reproducible, the implementation
- T8 DONE -- Port the script VMs, per section 3 of the plan (map-script and chatbox text-script dispatch). Landed 752146e (branch wt/t8-script-vms @ cdd976e)
- T9 BLOCKED -- The second virus as a ported per-type routine, from a real battle recording. Blocked on a file-set widening I cannot grant
- T6 DONE -- The Mettaur as canon's per-type routine: replace the hand-written brain with the ported AI entry. Mettaur brain now canon per-type entry MettaurEntry ForMettaur_8109EF4 (objects.rs), hand-written MettaurState removed (ai.rs), battle.rs 1 
- T7 PARTIAL -- The battle end as canon's sequencer table: banner states, teardown, results hand-off. Sequencer states + TRC2 v3 export landed pixel-neutral (verify_rows: isolated all 0 incl mettaur, cursor 10/9 tear-smaller, both-rows 0
- T7b DONE -- Re-establish the sequencer evidence: fresh v3 traces, loud judge, kill-to-slide gap. Landed 0fb54d4 (branch wt/t7b-sequencer-evidence @ dce93d4, carrying wt/t7's Sequencer states)

**Common to F8-F23 (and their b-tickets) unless the ticket says otherwise.** Baseline the row (harness line plus
`tools/diffmask.py` region, plus `tools/oracle.py` where the row is supported); localize the residue to
frames and an element; find canon's routine for that element in reference/bn6f and cite it; fix src/
(or the fixture/descriptor when the residue is the fixture, with `peeked` provenance); re-run the row,
wave, window, opening, chip-cannon and the full table -- nothing may get worse, and a row that does is
reported with its numbers. No allowlist change; no alignment or region change except by measured event
(F2's rule). **Coordinator:** verify_rows on every row the report names; the verifier only for claims
beyond harness lines; a PARTIAL from a wrong guess about the cause gets one follow-up ticket; if that
also fails, mark the ticket BLOCKED and move on to the next OPEN ticket.

- T13 DONE -- Audio parity, first measurement: both sides dumped and compared sample-exact. LANDED as 9d52135
- T9d DONE -- Why the poked Gunner battle never goes live: write-watch the sequencer on the working scenario and name the difference. no writer for dword_203CA70 on either battlestart route (200f watch-write, both empty)
### T13b. The two audio defects T13 measured: the ungated hit sample, and the 6.6 ms onset offset  *(DONE -- 2026-09-14, src/battle.rs: hit_in now armed only when the strike's take_damage[] landed)*

**Result.** src/battle.rs: hit_in now armed only when the strike's take_damage() landed; zero-enemy ch4 tree peak 0 (0 nonzero of 640170 samples), enemy-present peak 11273 at frames 118..130 (was 11221 pre-fix whole-tree peak); onset residual 635 pairs = 6.62ms canon / 6.64ms ours (NOT one frame; a frame shift overshoots 10.1ms); frame 0 234-pair silence = harness priming (mgba_capture.c:631-641,947-967). Full table: only cursor isolated 13->10 (the reported tear) and field integrated allowed 158934->158993 moved; all other isolated rows 0. verifier-hyper CONFIRMS claims 2-5, refines 1 (SOUND_HIT_6B has 5 ROM sites; our gate is stronger than cited on unreachable barrier/mercy axes) -- corrections in 3963c8b. 12 capture runs vs an 8 cap, disclosed. landed 8456a2c, re-verified on HEAD
**Files.** src/battle.rs, docs/audio/baseline-buster.md (three wording fixes), docs/coverage/audio-buster.md (new)

**Why.** T13 landed (`9d52135`) the first sample-exact audio comparison and its verifier confirmed, from the trees
on disk and with zero capture runs, two defects that are mechanical facts about our side -- not synthesis guesses:
(a) `src/battle.rs:3235` sets `hit_in = BUSTER_HIT_DELAY` inside `Update::Strike { charged }`'s uncharged arm with
**no enemy-overlap and no HP gate**, so `assets/buster_hit.wav` plays through the agb mixer on FIFO A (channel id 4)
at press+10 (frames 118..130, RMS 2175.9, peak 11221 -- which is our *whole-tree* peak) in a scenario that has no
enemy to hit; canon's run of the same scenario shows no such onset (its frame 140 = 2181.5 sits *below* 136-139 =
2466/2519/2593/2782). It is the only `play_sound` call in all of `src`. (b) the buster blip's onset is **one frame
later than canon's at frame granularity, and the verifier's mandatory qualifier is that the measured onset-to-onset
distance is ~635 interleaved pairs = 6.6 ms, NOT one frame**: canon's first differing sample is pair 1119/1605 into
its frame 135 (press+5, a partial frame -- 486 of 3210 samples, all in L) while ours starts at pair 149/1605 of
frame 114 (press+6, a full frame), so a fix that shifts ours a whole frame earlier **overshoots by ~10 ms and fails
a sample-exact check it should pass**. The frame-level attribution is now measured, not inferred: the no-press canon
control subtracts sample-exactly at all 130 pre-press frames plus the four poke frames, cancelling the frames 12-27
music (RMS 4234.6 / peak 8460 -> difference 0.0).
**Do.**
1. Gate the hit sample the way the ROM gates it → *find canon's own condition for the `SOUND_BUSTER_*` hit sound in
   the disassembly (the fire phase's enemy-overlap/HP test, cited `symbol:file:line`), implement that predicate on
   the `hit_in` write, and re-measure: our channel-4 tree in a zero-enemy fixture must go silent, and with an enemy
   present the event must appear where the predicate says. Report both trees' peaks, not one.*
2. Close the onset offset as a **time** difference, not a frame difference → *report the onset pair index on both
   sides after the change (canon 1119/1605 of its onset frame is the target's phase); state the residual in pairs
   and in ms at the measured 95999.1 / 95589.4 Hz, and do not claim parity at frame granularity alone.*
3. Three wording fixes in `docs/audio/baseline-buster.md`, none of which changes a number: label the 9179 as a
   **peak of the subtraction** on a channel where the blip *replaced* the music (canon's own peak at 136 is 8366);
   note that "decay to 2123 by 142" is measured against the ~3000 unattributed divergence floor the doc already
   disclaims; and change "now reports every mismatched frame" to what the tool does (counts all 106, lists the
   first 10).
4. Leave the frame-0 ramp ALONE but say what it is → *our frame 0 is short (234 pairs vs canon's 1605) AND silent
   (max |sample| 0 over its 234 pairs), which is why the first cross-side difference is global s16 index 2; report
   whether that is our boot-time audio ramp or the capture harness's own priming, with a cite, and stop there.*

**Rules.** No edit to `tools/harness.py` (this adds **no row** -- audio is still not a harness verdict), `tools/mgba_capture.c`, `tools/states.py`, `tools/trace.py`, `FIXTURE.md`, `assets/`, `docs/coverage/` except the new `audio-buster.md`, `reference/bn6f` read-only. ≤8 capture runs, one at a time inside the 3-slot semaphore, and state the count honestly (T13 disclosed 13 runs against an 8 budget; a disclosed overage is fine, a quiet one is not). No fitted numbers: `BUSTER_BLIP_ENVELOPE`/`_FREQ`/`_FRAMES` may only change against a cited ROM value or a measured residue, and the `provenance:` tag must be updated in the same commit. `docs/inventory/enemies.{json,md}` are T12's generated output -- regenerate with its tool, never hand-edit.
**Acceptance.** the full table identical to today -- every named row except the `rollup` line, i.e. the same set `python3 tools/harness.py --list` prints, each isolated row reading 0 (`cursor`'s single-frame tear reported, not chased) -- a `src/` change must not move a pixel; our channel-4 tree silent in the zero-enemy fixture with the predicate cited; the onset residual stated in pairs and ms against the 6.6 ms measurement; `docs/coverage/audio-buster.md` recording what is now parity and what is still residue.

### T7e. End-edge nine frames early on battle_full and the two wrong citations in src/battle.rs  *(DONE -- 2026-09-14, battle_full sequencer 540/540 [165 window-setup k=31..195 + 8 kill-timing k=297..304, both named])*

**Result.** battle_full sequencer 540/540 (165 window-setup k=31..195 + 8 kill-timing k=297..304, both named); +35 dissolve seed moves rust 0x0C k=296->297, delta 9->8; two citation defects corrected (asm00_1.s:10527-10537->:10609-10611 and :10841->:10958/:11022); verify_rows PASS all rows; verifier-minimax CONFIRMED all 4 claims; landed as 1b7187b; cursor tear 3/2/170/186277->10/9/170/186276
**Files.** src/battle.rs (the sequencer end-edge and the two citation comments only), tools/trace.py (only if a watch field must be added), tools/harness.py (the integrated rows' notes only)

**Why.** T7c kept UNMERGED at wt/t7c @ 510b5c6 because battle_full's sequencer is divergent on 173 of 540 frames — 165 window frames + 8 kill-timing frames (canon's stored record: 0x1c 0..10, 0x08 11..41, 0x20 42..43, 0x24 44..143, 0x00 144..146, 0x04 147..206 = 60 frames, 0x08 207..315, 0x0C 316..); our 0x0C at k=297 vs canon k=305 is the +35 dissolve seed not yet applied to battle_full's path (F32 set the kill-to-0x0C count on zero-enemy fixtures, the full battle's path differs); and two citation defects: src/battle.rs cites asm00_1.s:10527-10537 for the 0x08->0x20 write (actual 10609-10611; 10527-10537 is the sub_800A152==7 / 0x1c branch) and :10841 for the 0x24 leave (actual sub_801483C call sites 10958 in 0x00 and 11022 in 0x24; 10841 is inside sub_800834A's jump table). Closes the M2 sequencer acceptance at 540/540 unaligned, which is the gate this phase carries.

**Do.**
1. Watch canon's and ours' sequencer (dword_203CA70, ewram.s:3040) on battle_full from the killing blow to k=400 with tools/probe.py → *report the exact frame each side enters 0x08 after the dissolve and 0x0C at the end (two integers per side; report the delta).*
2. Apply the +35 dissolve seed to battle_full's path (F32's zero-enemy seed sits at +34 on this scenario; the +1 is canon's own banner-record wait per sub_801E754's banner-idle check, asm00_1.s:10478-10514, with timer arms 0x1e and 0x293) and re-measure the same trace → *report the new delta and the new battle_full sequencer k-count.*
3. Fix the two citation defects in src/battle.rs to the actual line ranges (asm00_1.s:10609-10611 and :10958/:11022) and re-run `tools/verify_rows.py` from a clean detached checkout → *report the table identical to HEAD except cursor's tear (the binary may move it from the 3/2/170/186277 T7c left it at).*

**Rules.** Only src/battle.rs (the end-edge + the two comment cites), tools/trace.py only if a watch field must be added, tools/harness.py notes only; no allowlist change; no new harness row; canon never changes; any fitted constant that changes gets a `// provenance:` tag update in the same commit. ≤8 capture runs total, one at a time inside the 3-slot semaphore.

**Acceptance.** battle_full sequencer 540/540 unaligned (or the remainder named and shown to be kill-timing setup only); result's sequencer still 0x0C at k=0; every isolated row 0 with cursor's tear reported as it moves; the two citations corrected; SEQ04_FRAMES = 60 either promoted to a ROM-sourced constant or narrowed to its actual basis.

**Coordinator:** dispatch first. M2 sequencer is the lowest unmet milestone and T7c's branch already carries the four window states (verifier-confirmed); this is the work that closes the 540/540 sequencer acceptance. Worker muse-spark-1.3-contributor (T7c's child class), verifier GLM-5.3-flash cross-family; ≤$0.15 expected, ≤$0.40 cap; verify_rows on every row named.

---

### T7f. Closing-window fixture: drive 0x24 -> 0x00 -> 0x04 -> 0x08 and replace the fitted edges with canon's predicates  *(PARTIAL -- 2026-09-14, windowclose_full scenario confirmed 0x00 enter+leave [144..146, 22..24] and 0x04 enter+leave [147..206, 25..84)*

**Result.** windowclose_full scenario confirmed 0x00 enter+leave (144..146, 22..24) and 0x04 enter+leave (147..206, 25..84) on both sides (100/100 sequencer frame match on re-record); edges named in code as sub_8008452/sub_800840C/sub_8008064 with timer arms 0x1e/0x293 in comments; SEQ04_FRAMES=60 stays peeked because the asm timer arms are display parameters not countdown timers and the canonical leave predicate (sub_801E754 banner-idle check against HUD bit 0x8000) needs banner composite not modelled; verify_rows did not get a clean run before budget; worktree clean (no diff to land); no fitted frame-count constants survive on strict-provenance reading
**Files.** tools/states.py (the scenario that opens AND closes the chip window), src/battle.rs (the four sequencer edges only), tools/trace.py (only if a field must be watched to see an edge), docs/coverage/ (notes)

**Why.** T7c's verifier REFUTED the exoneration of src/battle.rs: three window-opening fixtures (window/cursor/card, gauge 16384 + FLAG_OPEN_WINDOW) drive 0x08 k=8..132, 0x20 for 1 frame, 0x24 to the end and NEVER reach 0x00 or 0x04, so those two arms have zero measured coverage and the fitted frame counts are unfalsifiable. T7d built the closing-window scenario `states.TRACE_SCENARIOS['windowclose_full']` (kept UNMERGED at wt/t7d @ 24d9ef7 on a merge of wt/t7c @ 9be540c) and re-recorded on the current build to confirm the window opens AND closes. What's owed: put canon's predicates under each of the four edges — sub_8008452 leaves 0x20 on sub_802D6C4's return (asm00_1.s ~11003-11008), sub_800840C gates 0x00 -> 0x04 on sub_801483C + the [r5+2] latch (10947-10976), sub_8008064 writes 0x08 only when sub_801E754's banner-idle check returns 0 after arming timers 0x1e and 0x293 (10478-10514) — and confirm 0x00 / 0x04 actually enter and leave.

**Do.**
1. Re-record `tools/states.py`'s `windowclose_full` scenario on the current build (verify it's the v3 record per T7b's `require_seq`) and read the sequencer field across the scenario → *report the exact frame ranges for 0x24, 0x00, 0x04, 0x08 (four integers per side; confirm 0x00 entered AND left, 0x04 entered AND left).*
2. Replace each fitted edge in src/battle.rs with the canonical predicate: 0x20 leave uses sub_802D6C4's return; 0x00 -> 0x04 transition uses sub_801483C's ldrb/cmp plus the [r5+2] latch; 0x04 -> 0x08 transition uses sub_801E754's banner-idle check (with timer arms 0x1e and 0x293) → *name each ported line with `file:line` and report no fitted frame-count constant survives.*
3. Re-run `tools/verify_rows.py` from a clean detached checkout → *report the table identical to T7e's result (battle_full sequencer 540/540, every isolated row 0, cursor's tear reported as it moves from the T7e value).*

**Rules.** Only the named files; no allowlist change; no harness row added; no fitted frame-count constants survive (each replaced with the canonical predicate that names it); citations updated in the same commit; ≤8 capture runs total, one at a time inside the 3-slot semaphore.

**Acceptance.** windowclose_full scenario records 0x00 entered and left and 0x04 entered and left, with frame ranges named (both sides); battle_full's sequencer remains 540/540 unaligned (T7e's fix); result's sequencer still 0x0C at k=0; every isolated row 0 with cursor's tear reported; the four sequencer edges named with the predicate each stands for (no fitted frame counts).

**Coordinator:** dispatch second (depends on T7e). Once T7e lands, the worker merges wt/t7c into a fresh worktree (`bash tools/worktree.sh t7f-closing-window; git merge --ff-only wt/t7c`) and continues from T7d's branch. Worker muse-spark-1.3-contributor (T7d's child class), verifier GLM-5.3-flash cross-family; ≤$0.15 expected, ≤$0.40 cap; verify_rows on every row named.

---

### T9e. Gunner live trigger: find what writes dword_203CA70 on the poked battle and add the row aligned by the Gunner's first attack event  *(NEGATIVE -- 2026-09-14, trigger poke unblocks sequencer [Index_01 0x02034881 4->0->8->0x0C at f165)*

**Result.** trigger poke unblocks sequencer (Index_01 0x02034881 4->0->8->0x0C at f165; dword_203CA70 0->0x04 at f166); measured previously T9d wrote frame-60 poke overwrote by controller init at f154; correct frame is ~f165 after chip-window controller parks at state 4; BUT slot1's BattleObject (0x0203ab68 Gunner) sits at CurState=0x01/CurAction=0x04 (post-spawn idle) at every frame f154..f400 with HP 0x003c; gunner does NOT reach attack event in 400 frames with sequencer unblocked; no commit (no attack event to align new row on); follow-up needed: longer settle window (sub_8112D9C's 234-frame cycle) and row-check chain needs MegaMan on panel row 3
**Files.** tools/states.py (only if a poke fixes the trigger), src/fixture.rs (enemy_kind honoured — kind 1 = Gunner), src/battle.rs (the fixture's enemy construction by kind), src/objects.rs (the per-type entry), src/ai.rs (ForGunner_8113078 under enemy_think/enemy_act), assets/ (Gunner art extracted at comp_825BFC4, asm32.s:9538), tools/probe.py + tools/trace.py (the watch-write runs), tools/harness.py (the new row aligned by the Gunner's first attack event), FIXTURE.md, docs/coverage/battlestart_gunner.md (corrected, with the measured trigger)

**Why.** T9c landed 1f7efc9 (partial, no gunner row): `battlestart_gunner` recipe (battlestart pokes + `--poke-at 60:0x0200a210:0x371` -> BattleSettings record 6 = 0x080b4bd8, setup byte_80B5347 = 00 22 00 00 | 11 25 01 00 | 11 36 85 00 | F0, Mettaur + Gunner 0x85) and per-slot `enemy_kind` (fixture byte +5, 2 bits/slot) are in and verifier-confirmed. The blocker is now precisely diagnosed: `dword_203CA70` (ewram.s:3040) stays 0 to frame 2438 because write-mask byte 0x02036848 reads 0 for all 901 frames and NO poke in the recipe writes it, so `sub_801483C` (@0x080148c4 `ldrb r3,[r5]; cmp #4`) never releases its 4/8 writes and the entry is never armed (`sub_80141F0`'s caller @0x0801460e `bx r1` = nullsub_57). The branch's gate-chain diagnosis was REFUTED — the `sub_801483C->4` -> `sub_80141F0->bx r1` chain is unsupported. T9b's measurement pass already proved the art reproduces assets/gunner.bin byte-for-byte at comp_825BFC4 (4588 B / 2 gfx blobs / 1 palette / 4 anims / 16 frames / 154 OAM). Closes M5 (the second virus as data under the ported interpreters — T6 already landed the Mettaur's per-type entry).

**Do.**
1. Write-watch 0x0203CA70 and 0x02036848 on the `battlestart_gunner` scenario from f0 to f300 with `tools/probe.py --watch-write` → *report every writer (PC + instruction + byte value) on each side; state whether the trigger is in the recipe (a poke is missing) or in the engine (a path canon reaches but our poked scenario does not).*
2. Reproduce the live trigger with a one-shot poke if it is a missing poke (e.g., 0x02036848 = 4 at the frame the original 8/4 write happens), or with a fixture tweak if it is a missing path → *confirm the sequencer reaches 0x08 by f80, the Gunner's first attack event fires, and the slot's CurState/CurAction/timers match canon's own run on the same scenario (T9b's slot probe: slot1 panel 0x0306 / NameID 0x0085 / HP 0x003c at 6,3).*
3. Port the `ForGunner_8113078` routine (`off_8109050[0x17]` / `off_81091D0[0x17]`, asm32.s:10060-10290; CurAction table 0x00-0x0B plus the six per-version parameter tables from byte_80182C4) under enemy_think/enemy_act, wire assets/gunner.bin at the kind-1 art, add one harness row aligned by the Gunner's first attack event → *report row = 0/0 with negative not blind (kind 1 fixture, no Mettaur in slot0).*

**Rules.** Only the named files; tools/harness.py for the new row only; assets/ for art extracted byte-for-byte at comp_825BFC4 (T9b's measurement); docs/coverage/battlestart_gunner.md corrected before this ticket copies it forward; no allowlist change; canon never changes; the kind-1 fixture must be backward-compatible (every existing row unchanged, the Mettaur rows in particular, kind 0 unchanged); ≤8 capture runs total, one at a time inside the 3-slot semaphore.

**Acceptance.** gunner row 0/0 with negative not blind (kind 1 fixture, slot1 = Gunner, slot0 = Mettaur); the trace on the Gunner scenario shows the slot's CurState/CurAction/timers matching canon from spawn through the second attack; every existing isolated row unchanged (mettaur 0/0/70/41734 in particular; cursor's tear reported as it moves); docs/coverage/battlestart_gunner.md corrected with the measured trigger.

**Coordinator:** dispatch third. M2 sequencer is the priority; this is the M5 content-under-interpreters ticket whose measurement pass T9b already paid for. Worker muse-spark-1.3-contributor (T6's child class — the Mettaur port was a T6 ticket), verifier GLM-5.3-flash cross-family; ≤$0.30 expected, ≤$0.60 cap; verify_rows on every row named (especially mettaur, wave, cursor).

### T7h. battle_full's first divergence: the enemy's opening action and animation (canon CurAction 0x0A, ours 0x00)  *(OPEN -- 2026-09-14, follows T7g, advances M2 and M5)*

**Files.** src/objects.rs (the per-type entry and the enemy's exported CurState/CurAction), src/actor.rs (the 0x0A/0x0B executors' entry condition), src/battle.rs (only where the enemy is created for a fixture), tools/trace.py (only if a field must be watched), docs/coverage/battle_full.md (notes)

**Why.** M2's acceptance is "battle_full trace: first divergence none", and `docs/trace/t7b/battle_full.diff.txt` names the head of that list precisely: `FIRST DIVERGENCE: enemy_state_action at k=0 (canon frame 11) canon=(4, 10) rust=(4, 0)`, divergent on **344/540** frames, with `enemy_anim` diverging from k=21 (canon frame 32, canon=1 rust=0) on **409/540** frames. Both T5 and T6 re-measured and left it untouched (plan-interpreters §2.5: "trace first divergences unchanged with identical counts"; §2.6: "trace battle_full first divergence UNCHANGED (enemy_state_action k=0 canon=(4,10) rust=(4,0), counts 101/86/302/344/409/10 over 540)"), and the mettaur scenario cannot see it — T6 logged that "the enemy is BattlePaused-frozen through the compared window so the entry never runs there". So this is the one M2 gate item whose mechanism has never been measured. The vocabulary is already ported: src/ai.rs:21 says "0x0A is the HOP" executor, src/objects.rs:192 puts the 0x0A/0x0B executors in `Actor` (hop = 6 frames + `byte_8109F46[0]` cooldown, actor.rs:54-55 HOP_FRAMES/HOP_COOLDOWN, both `derived`), and canon's per-type entry's first arm is the spawn (`ForMettaur_8109EF4`'s CurAction 0x00 → `RunSpawnAnimationMaybe_8016380`, asm00_2.s:16009; the spawn pause is a flat 0x1e wait in CurAction 9, src/objects.rs:247-252). Ours reports 0x00 where canon reports 0x0A from the first recorded frame: either canon's spawn arm has already handed CurAction to the 0x0A executor before our window's k=0, or our enemy is created in a state the entry never arms.

**Do.**
1. Baseline the trace with no edit (`tools/trace.py record/diff --align row:battle_full`) and watch the enemy slot from before k=0 (`0x0203ab68/69`, plus `+0x20`) on both sides with `tools/probe.py` → *report, for the first 40 frames, canon's and ours' (CurState, CurAction, timer, anim) per frame: the frame canon's CurAction becomes 0x0A, the frame ours becomes anything at all, and the last frame at which the two agree (expected 0).*
2. Find canon's writer of that opening CurAction and port the arm that runs it — `RunSpawnAnimationMaybe_8016380` (asm00_2.s:16009) through `ForMettaur_8109EF4` (asm31.s:170982) — under the already-landed `enemy_think`/`enemy_act` entries rather than as a new hand-written pose → *report the citation `file:line` per arm actually ported and the trace's new first divergence (field + k + canon/rust values).*
3. Re-run the same diff and the mettaur/wave/popup traces on the same scenario set → *report the enemy_state_action and enemy_anim frame counts (baseline 344/540 and 409/540), the new first divergence, and mettaur 70/70 unchanged.*
4. Re-run `tools/verify_rows.py` from a clean detached checkout → *report the 67-row table identical to HEAD except where the report says, with every chip row and the mettaur row still 0/0 and cursor's tear reported (HEAD 1/1/170).*

**Rules.** Only the named files; no new harness row and no change to tools/harness.py, tools/states.py, FIXTURE.md or the descriptor contract; no allowlist change of any kind; no alignment change except by measured event; the fix is a port under the interpreters (T5/T6's `enemy_think`/`enemy_act`/`MettaurEntry`) — no new hand-written pose and no per-scenario branch; every new literal in an edited line gets a `// provenance:` tag or the canon symbol; `fitted constants in src/` (HEAD: 19) may not increase; canon never changes; ≤6 capture runs, one at a time inside the 3-slot semaphore.

**Measure and report.** row: battle_full, mettaur, popup, wave, cursor, result (trace rows plus the pixel rows this touches). frames: 540 for battle_full, 70 mettaur, 170 cursor. total/worst: per pixel row before and after. region: for the trace, the (CurState, CurAction) pairs frame by frame for k=0..39 both sides; for any pixel regression, the diffmask region and frame. commit: src/objects.rs + src/actor.rs. One line of mechanism; one line of what is unverified (canon's Navi-side spawn arm, if only the virus arm was measured).

**Acceptance.** the `battle_full` first divergence is no longer `enemy_state_action` at k=0 — the pair is equal at k=0 on both sides, with the ported arms cited — and the two counts move off their baselines (344/540 and 409/540) by a measured amount, reported whatever it is; mettaur's trace stays divergence-free on 70/70; every isolated pixel row reads 0 as it does today (43 chips included), cursor's tear reported; `fitted constants` not increased.

**Coordinator:** dispatch second: files are disjoint from T7g's except src/battle.rs, so it runs alone after T7g lands, never alongside it. Worker muse-spark-1.3-contributor (T6's child class — this is the continuation of the Mettaur as data), verifier GLM-5.3-flash cross-family; ≤$0.15 expected, ≤$0.40 cap; verify_rows on mettaur, wave, popup, cursor and the chip rows.

---

### T7i. battle_full's MegaMan tail: the k=179 action/timer/anim group, then name the RNG residue  *(OPEN -- 2026-09-14, follows T7h, advances M2)*

**Files.** src/battle.rs (MegaMan's update path and the RNG step), src/actor.rs (his action/timer/anim fields), src/custom.rs (only if the divergence's cause is the chip window's hand-back), tools/trace.py (only if a field must be watched), docs/coverage/battle_full.md (notes)

**Why.** With T7g's sequencer arms and T7h's opening action done, `docs/trace/t7b/battle_full.diff.txt` leaves exactly one mechanism family before M2's "first divergence none" can be claimed: three fields that all break on the same frame — `mm_state_action` first k=179 (canon frame 190) canon=(4, 8) rust=(4, 3) on **101/540** frames, `mm_anim` first k=179 canon=0 rust=1 on **86/540**, `mm_timer` first k=179 canon=0 rust=22 on **302/540** — i.e. our MegaMan sits in an action with 22 frames of timer left where canon's is back in (4,8) with the timer at 0, and holds it for 302 of the scenario's 540 frames. That is an un-freed gate on his own executor, and it is the same field set the oracle already tracks (`mm_state_action` 0x0203a9b8+0x08/+0x09, `mm_timer` +0x20, AGENT_GUIDE's plan-interpreters §2.4). The one remaining field after it is `rng_cadence`, diverging first at k=271 (canon frame 282) on **10/540** frames — M2's own "RNG parity in battle" bullet — so this ticket's last step measures it and either closes it or states the draw-count difference; nothing is inherited silently. T5/T6 both re-reported the group's counts (101/86/302) unchanged, so no ticket has ever attributed it.

**Do.**
1. Baseline the group with no edit and read the window around it: `tools/probe.py` on MegaMan's BattleObject `0x0203a9b8:+0x08..+0x26` for k=170..200 on both sides, plus the scenario's scripted input → *report, per side, the frame the action pair becomes (4,8), the CurAction each side is holding at k=179 (canon 8 / ours 3), the timer's countdown on our side frame by frame (baseline: 22 at k=179), and the input event or release edge each side is waiting on.*
2. Find canon's release of that action (his per-frame path: `playerObject_update_80EA484` asm31.s:107150 / `playerObject_main_80EA460` asm31.s:107131 / `playerAI_update_80EA734` asm31.s:107351 — cite the exact line that clears the timer or arms the next action) and port that predicate where our side currently counts frames → *report the citation and the trace's three counts after (baseline 101/86/302 over 540) with the new first divergence's field and k.*
3. Measure the RNG cadence on the same recording: count `GetRNG` steps per side from k=250 to k=300 at 0x020013f0 → *report the two sides' cumulative draw counts at k=271 and the first frame they differ; if the gap is an extra or missing draw, name the caller from the coverage table's rank (e.g. `sub_801A308` asm00_2.s:21830, first frame 436 class) or state the count difference as the remainder.*
4. Re-run `tools/verify_rows.py` and the four trace scenarios from a clean detached checkout → *report the table against HEAD (61 of 67 rows at 0, cursor's tear reported) and the mettaur/popup/result traces unchanged or better.*

**Rules.** Only the named files; no new harness row; tools/harness.py untouched; no allowlist change; no alignment or descriptor change except by measured event; the fix is a predicate read from canon's object, never a countdown matched to the picture — a fitted constant that changes gets its `// provenance:` tag updated in the same commit; `fitted constants in src/` (HEAD: 19) may not increase; the 43 chip rows, wave, window, windowclose, result, mettaur and popup must not move; canon never changes; ≤8 capture runs, one at a time inside the 3-slot semaphore.

**Measure and report.** row: battle_full, mettaur, popup, result, cursor and the chip rows. frames: 540 (battle_full), 70 mettaur, 80 popup, 40 result, 170 cursor. total: the three field counts (baseline 101/86/302 over 540) and `rng_cadence` (baseline 10/540) before and after. worst: any pixel row that moves. region: the k=170..200 action/timer table both sides, and for a pixel regression the diffmask frame and region. commit: src/battle.rs + src/actor.rs. One line of mechanism; one line of what is unverified.

**Acceptance.** `battle_full`'s `mm_state_action`/`mm_anim`/`mm_timer` counts are all below their 101/86/302 baselines with the k=179 group closed by a cited predicate (the release edge named in `file:line`), the residual first divergence on the scenario named as one field + one k + both sides' values — and if it is `rng_cadence`, its two cumulative draw counts at k=271 reported; every isolated pixel row still 0 with cursor's 1/1/170 tear reported as it moves; `fitted constants` not increased.

**Coordinator:** dispatch third, after T7h (same files, same scenario; it must not be paired with T7g or T7h). No existing harness row is expected to close here — the dollar buys M2's trace gate and, if the k=179 gate is the one HANDOFF blames for the integrated variants' 3-frame drift, T7g's numbers get restated rather than widened. Worker muse-spark-1.3-contributor, verifier GLM-5.3-flash cross-family; ≤$0.20 expected, ≤$0.50 cap; verify_rows on every row named.


### T9f. Does `eS20364C0.JumpOffset00 = 8` start the poked battle: one-shot poke test, and the first attack event's frame  *(NEGATIVE -- 2026-09-14, one-shot poke-at 155:0x020364C0:0x08 set eS20364C0.JumpOffset00=8 and held through f199)*

**Result.** one-shot poke-at 155:0x020364C0:0x08 set eS20364C0.JumpOffset00=8 and held through f199; Index_01 0x02034880 watch 4->8 at f153 then NOTHING through f199 (no Index_01=0x0C); sequencer LSB stayed 0 (f156 hits at 0x0203CA70 byte0 ARM C-touch and 0x0203CA73 byte3 4 at 0x0800841E inside sub_800840C are incidental, byte 0 is the state per docs/trace/t9d/live_paused_route.log 0x1C->8 at 0x080083F8); 0x020364C4..0x020364C5 watch shows ONLY f154 init burst then nothing -- state-4 handler custMenuMainMaybe_8026A88 never re-enters; T9d's state-8 fall-through hypothesis REFUTED; no first-attack-event frame exists to align on with JumpOffset00=8; next stop is upstream of JumpOffset00 in whatever fires sub_8026840 and decides whether JumpOffset01=0x40 path returns; docs/trace/t9f/ logs committed on wt/t9f-poke-test @ 303f3fc; no src/* or tools/* touched; not merged (docs-only trace ticket); meta doc battlestart_gunner.md corrected
**Files.** tools/states.py (only if the poke belongs in the `battlestart_gunner` recipe), docs/trace/t9f/ (new), docs/coverage/battlestart_gunner.md (the measured result)

**Why.** T9d landed (`73d50fd`) with all three of its claims CONFIRMED by the verifier and its premise refuted in the process: `dword_203CA70` (`ewram.s:3040`) has NO writer at all on either battlestart route -- `--watch-write` logs 0 hits in 200 frames on `battlestart` (record 7) and on `battlestart_gunner` (record 6), so the 3-Mettaur scenario T9's ticket called "working" is dead the same way, and the roll outcome is not the difference. The only route in the repo where the sequencer moves is the hand-played PAUSED root, where it is already `0x1C` at load and writes `0x1C -> 8` at frame 11 from PC `0x080083F8` (`sub_80083E4`) on the Start unpause; `mettaur`'s live canon rides THAT route (`tools/harness.py:958`, `STERILE + PAUSED + ALIVE + script "Start@10"`), not `battlestart`, so no currently-0 row's premise was broken. The stop is localized: `eBattleState.Index_01` (`0x02034881`, `ewram.s:2572`) parks at `0x08` from frame 153, because state 0x08's handler `sub_8009338` (`asm/asm00_1.s:13054`) ends in `bl sub_8026A28; cmp r0,#0; beq locret_8009388` (`asm/asm00_1.s:13065-13067`), and the `beq` is taken every frame -- so `Index_01` never reaches the `0x0C` handler `sub_800938A` (`13126`, the single caller of the banner task `sub_800801C` at `13135`), and nobody writes the sequencer. `sub_8026A28` (`asm/asm03_0.s:761`) dispatches on `eS20364C0.JumpOffset00` (`0x020364C0`, `ewram.s:2676`) through `off_8026A3C` (`asm03_0.s:776-781`): state 0 `sub_8026A50` returns 0 and self-advances to 4, state 4 `custMenuMainMaybe_8026A88` never stores at `[r5]` (the verifier checked every [r5]-relative store in `asm03_0.s` 813-1300 -- they target `#1`, `#2`, `JumpOffset01`, `#0x38`, `#0x40`, `#0x44`, never offset 0), and state 8 `sub_8026A6C` returns `Unk_04` (+4), which the gunner log shows already written to 1 at frame 154 by `0x080268F2`. The verifier derived the consequence: with `JumpOffset00 = 8` the gate's `beq` falls through and `Index_01` is written `0xC` -- exactly the missing step in `docs/trace/t9d/gunner_fsm_index01.log`. That has never been executed. This ticket executes it. It adds NO row and touches no `src/`: it buys the one number a row ticket needs (the frame of the first attack event to align on), or a precise negative naming what still blocks.

**Do.**
1. One-shot `--poke-at` `0x020364C0 = 8` (u32, `eS20364C0.JumpOffset00`) on `battlestart_gunner`, with `--watch-write` on `0x0203CA70` (sequencer) and `0x02034881` (`Index_01`) for 200 frames → *report whether either moves, which values, at which frames, and from which writer PCs; an empty log is a result, reported as one.*
2. If the sequencer moves: hold the poke at load instead of one-shot (the recipe's own poke list) and re-run the same watch for 200 frames → *report the frame of the FIRST attack event, defined as the first frame an enemy's HP drops or the gauge (`0x020352A0`, `0x020352A2`) changes from the frozen `0x00200000`, with the values on both sides -- this is the number the row ticket will align on. Report whether the two viruses still park at state/action `0x0104`.*
3. If it does not move, name the next stop instead of inventing a gate → *report which of the two watches produced an empty log, and run one further watch on the byte the hypothesised author writes (`0x020364C4:2`, the chip-window controller's `Unk_04`/`JumpOffset01` pair) to say whether state 4 is even re-entering; then stop.*
4. Write the result into `docs/coverage/battlestart_gunner.md` (replacing the UNVERIFIED hypothesis sentence with what was measured) and drop the raw logs in `docs/trace/t9f/` → *report the doc's new finding section and the log file list.*

**Rules.** No `src/*`, no `tools/harness.py` (this ticket adds NO row), no `tools/mgba_capture.c`, no `tools/trace.py`, no `tools/probe.py`, no `FIXTURE.md`, no `assets/`, no other `docs/coverage/`; `reference/bn6f` read-only. `tools/states.py` may gain the poke ONLY if step 2 shows it makes the sequencer advance, and the poke line carries its address/width with the `eS20364C0` symbol and `ewram.s:2676`. ≤4 capture runs. Every address named with its `ewram.s` line or ROM label. If the recipe changes, `python3 tools/states.py build all` must still build what it builds today, and report that.

**Acceptance.** `docs/trace/t9f/` holds the watch logs; `docs/coverage/battlestart_gunner.md` states the measured outcome with the numbers; and EITHER the sequencer advanced and the report gives the first attack event's frame plus the values (which makes the `gunner` row ticket writable, aligned by that event), OR the poke produced no movement and the report names which watch was empty and what that rules out. A precise negative closes this ticket.

**Measure and report.** row: none (trace ticket) · frames: 200 per route · total/worst/region: n/a, no pixel comparison; the numbers are the sequencer/Index_01 values with their writer PCs and the attack event's frame · commit: `tools/states.py` only if step 2 passes · one line of mechanism · one line of what is unverified (whether state 8's handler is reached by the real chip-hand path or only by the poke).
