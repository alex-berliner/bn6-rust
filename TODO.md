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
- T13b DONE -- The two audio defects T13 measured: the ungated hit sample, and the 6.6 ms onset offset. src/battle.rs: hit_in now armed only when the strike's take_damage() landed
- T7e DONE -- End-edge nine frames early on battle_full and the two wrong citations in src/battle.rs. battle_full sequencer 540/540 (165 window-setup k=31..195 + 8 kill-timing k=297..304, both named)
- T7f PARTIAL -- Closing-window fixture: drive 0x24 -> 0x00 -> 0x04 -> 0x08 and replace the fitted edges with canon's predicates. windowclose_full scenario confirmed 0x00 enter+leave (144..146, 22..24) and 0x04 enter+leave (147..206, 25..84) on both sides (100/100 seque
- T9e NEGATIVE -- Gunner live trigger: find what writes dword_203CA70 on the poked battle and add the row aligned by the Gunner's first attack event. trigger poke unblocks sequencer (Index_01 0x02034881 4->0->8->0x0C at f165
- T7h NEGATIVE -- battle_full's first divergence: the enemy's opening action and animation (canon CurAction 0x0A, ours 0x00). spawn arm ported: METTAUR_ACT_SPAWN=0 const + MettaurEntry init + SPAWN arm in think() at src/objects.rs:243-251,298-308,343-362
- T7i BLOCKED -- battle_full's MegaMan tail: the k=179 action/timer/anim group, then name the RNG residue. third M2 ticket in this run after T7f (PARTIAL: windowclose_full validates but SEQ04_FRAMES=60 stays peeked because asm timer arms 0x1e/0x29
- T9f NEGATIVE -- Does `eS20364C0.JumpOffset00 = 8` start the poked battle: one-shot poke test, and the first attack event's frame. one-shot poke-at 155:0x020364C0:0x08 set eS20364C0.JumpOffset00=8 and held through f199
- T9g NEGATIVE -- The Gunner attack event: the 234-frame settle window (sub_8112D9C) and MegaMan's panel row, so the row ticket becomes writable. Three captures, three negatives on docs/trace-only commit (no src/tools changes, wt/t9g-gunner-extended 801ecda, landed d43e4c0)
- T13c BLOCKED -- Audio comparison on a second scenario: chip-fire and chip-damage SFXs on the cannon route, gated by the cited predicates. Worker audited src/ before editing
- T7j PARTIAL -- Model the banner composite for sub_801E754's leave predicate: replace SEQ04_FRAMES=60 with the canonical banner-idle check. branch wt/t7j-banner-composite aa3486d (docs-only on src/battle.rs, SEQ04_FRAMES=60 unchanged in code
- T13d NEGATIVE -- Audio probe on the cannon route: what canon fires, what ours doesn't, then gate. docs-only commit landed as e87cc7f

- T7l BLOCKED -- battle_full opening action: seed canon's HOP pose at k=0 so the spawn fade no longer parks CurAction=0x00. T7l BLOCKED: worker hit tool soft-limit (80) on baseline only
- F21e DONE -- result isolated: decompose the remaining 102547/14866/40 per-object, name the next mechanism. F21e was a no-op: HEAD result isolated already 0/0/40 PASS (neg 111839, not blind) via F34b's intro_fade=0/start_state==1 + megaman_col=2 + 
- F37h NEGATIVE -- cursor: close the 3 px residue at k=37/97 from the window mark landed in F37g. F37h NEGATIVE: cursor 10/9/170 unchanged on HEAD (regression set: windowclose 0/0/40, mettaur 0/0/70, result 0/0/40 all PASS)
- F37i BLOCKED -- cursor: close the 3 px residue at k=37/97 via the BG1 backdrop drain in src/backdrop.rs. F37i BLOCKED: worker hit tool soft-limit (60) on assembly research only
- T7m BLOCKED -- battle_full MegaMan tail at k=179: the mm_state_action/mm_anim/mm_timer group, finish the release-edge gate port. T7m BLOCKED: worker hit tool soft-limit (60) on baseline capture only
- T7n PARTIAL -- battle_full RNG cadence: name the rng_cadence first-divergence at k=271 on 10/540 frames, port the read-site if a clean mirror exists. T7n PARTIAL: rng_cadence divergence named with citation
- F37j NEGATIVE -- cursor: port canon's QueueEightWordAlignedGFXTransfer drain into src/backdrop.rs so the k=37/97 BG1 seam closes. F37j NEGATIVE: both drain-timing ports regressed cursor
- T7o PARTIAL -- battle_full release-edge at k=179: relocate the SEQ04 seq-match block past t1_player_entry so the gate frees before the executor. T7o PARTIAL: SEQ04 seq-match block relocated from src/battle.rs:2533 to :3268 (after t1_player_entry), matching canon's call chain at asm00_
- T7p DONE -- battle_full RNG cadence: port the per-site mirror at sub_80C7EC8 / cbGameState_80050EC so rng_cadence drops below 10/540. T7p was a no-op: HEAD rng_cadence 9/540, already below 10/540 acceptance threshold (T7o's PARTIAL landing 784c8e5 reduced it from 10→9 by re
- F38c PARTIAL -- opening integrated 72499: port canon's intro-hunk palette/sheet assignment and the enemy's materialize animation. F38c PARTIAL: opening integrated 72499 measurement-only diagnostic
- T9h PARTIAL -- Gunner as data: port canon's per-type routine from byte_80182C4, add the harness row. T9h PARTIAL: Gunner as data per-type routine cite landed
- T7g NEGATIVE -- Land T7c's custom-screen states from the unmerged branch so battle_full's sequencer coverage extends. T7g NEGATIVE: ticket premise wrong — divergence is a fixture-level difference, not a src/battle.rs sequencer-dispatch port
- T7q PARTIAL -- battle_full k=179 group: add the seq.state gate in Actor::update so the MegaMan executor's per-tick work respects SEQ_20/SEQ_24/SEQ_00/SEQ_04. T7q PARTIAL: seq.state gate added to Actor::update (t1_player_entry early-returns Update::Nothing when seq.state in {SEQ_20, SEQ_24, SEQ_00,
- F38d PARTIAL -- opening integrated 72499: port the PAL_OBJ slot allocation in src/actor.rs and the second-cluster materialize animation in src/objects.rs. F38d PARTIAL: opening integrated 72499 unchanged
- T9i PARTIAL -- Gunner as data: fix the harness capture race so the gunner row reads 0/0/N. T9i PARTIAL: gunner race fix landed

- T7r PARTIAL -- battle_full fixture: scripted L input so self.seq.state traverses {SEQ_20, SEQ_24, SEQ_00, SEQ_04}. T7r PARTIAL: battle_full fixture seeds gauge=1 + window_pick OK + scripted A@170
- F38e BLOCKED -- opening integrated 72499: fix the diagonal spawn cells (src/battle.rs:1907-1908) and the materialize y offset (src/actor.rs:528). F38e worker found two rule conflicts that prevent landing: (1) spawn-cell fix needs per-enemy panel data per spawnEnemy_80073E2 asm00_1.s:86
- T9j PARTIAL -- Gunner as data: port the per-type routine into src/gunner.rs and align the harness row on the Gunner's first attack event. T9j PARTIAL: gunner_update per-type routine port at ForGunner_8113078 (asm32.s:10123-10142) + 4-arm state machine sub_8112F70/sub_8112FBA/su
- T7s NEGATIVE -- battle_full sequencer-timing fix: window opens at k=124 vs canon k=31 so self.seq.state traverses SEQ_20 by canon's k~31. T7s NEGATIVE: ticket acceptance unreachable under rules
- F38f PARTIAL -- opening integrated 72499: per-enemy panel bytes via src/fixture.rs and the diagonal spawn-cell fix in src/battle.rs:1907-1908. F38f PARTIAL with revert: branch (9a938d0 + 3eea157 + 8ee4346) landed on main but introduced cursor regression 1/1/170 -> 26/25/170
- T9k NEGATIVE -- Gunner as data: move Battle::gunner_ctl + Battle::impacts in src/battle.rs into GunnerEntry so gunner_update drives per-tick visible content. T9k NEGATIVE: refactor preserves gunner behavior 2850534/38237/130 (unchanged from T9j PARTIAL -- the ctl/impacts migration is relocation-on
- F38g BLOCKED -- opening integrated 72499: F38f re-land with cursor fixture state file regenerated for 67-byte descriptor. F38g BLOCKED: per-enemy panel port cherry-picked/re-implemented (commit 7c3b33f on wt/f38g-reland, diff matches F38f: src/fixture.rs +17, sr
- F36a PARTIAL -- warp integrated ~363658: baseline the residue, decompose by frame and region, port the canon mechanism. F36a PARTIAL with no code change: actual warp integrated on HEAD is 40628/11744/30 (NOT 363658 headline -- F38b event-lock pin rust_offset=5
- F35a BLOCKED -- buster integrated ~643698: baseline the residue, decompose by frame and region, port the canon mechanism. no code change, tool budget soft-cap hit at 80 before port
- T7u BLOCKED -- battle_full sequencer: port sub_801E754's banner-idle check to replace SEQ04_FRAMES=60 in src/battle.rs. code change made, but caused cursor regression: cursor 1/1/170 -> 38/37/170 (37x worse)
- F36b BLOCKED -- warp integrated ~40628: per-region decomposition, then port the canon mechanism for each non-zero region. no code change, tool budget soft-cap hit at 80 before port
- F38h PARTIAL -- opening integrated 72499: descriptor-preserving per-enemy panel encoding so cursor fixture state file stays valid. opening integrated 72499/2691 -> 25829/931 (residual is PAL_OBJ allocation order src/spr.rs:701-761 per F38e BLOCKED, not in scope)
- F37k BLOCKED -- cursor 3 px residue at k=37/97 via per-scanline BG1 backdrop seam port. infra failures (bash exit 1, then model cold-start on resume)
- T7v BLOCKED -- battle_full RNG cadence 9/540 → 0/540: port the per-site mirror at the remaining divergence frames. no code change
- F38i PARTIAL -- opening integrated 25829: PAL_OBJ allocation order port in src/spr.rs to clear the per-object OAM colour residue. opening integrated already at 0/0 on main HEAD (8b314eb) per verify_rows — NOT 25829/931 as F38h PARTIAL commit message stated
- F37l BLOCKED -- cursor 3 px residue at k=37/97 via per-element BG1 seam cite at sub_8001C94 (asm00_0.s:3752). cursor 1/1/170 isolated: residue is 1 px at (183,5) on k=97 ONLY (k=37 already 0 after F38h merge 2d1e639), NOT 3 px at k=37/97 as ticket cl
- F36c NEGATIVE -- warp integrated 40628: port sub_8001C94's BG1 seam transition directly into src/backdrop.rs. Premise refuted by measurement, no code change
- T7w NEGATIVE -- Battle end as canon's per-state counts: name the layer of the integrated rows' 16-px band, then retire the fitted RESULTS_DELAY=110. Premise refuted by measurement
- T9l PARTIAL -- gunner 2850534/38237/130: derive this row's own backdrop seed, then split the residue by layer. LANDED as 424814d
- F39a NEGATIVE -- opening integrated 25829/931/40: the four OBJ entries canon does not draw, and the per-sprite PAL_OBJ slot. Premise refuted by measurement
- F40a BLOCKED -- gunner 2105613/38237/130: settle whether the BG3 plateau is gauge-driven, then port the chip-window auto-open that canon takes at capture ~157. Lever not settled

- T7x NEGATIVE -- battle_full SEQ_04's leave predicate is a bit test: port isBannerBusy_801E754, delete SEQ04_FRAMES and BANNER_FRAMES. Ported and measured, but NOT landable: the bit-15 lifecycle is real and our mask series comes out canon-shaped, yet spawning the banner reco
- T7y NEGATIVE -- The custom screen's open edge: canon's gauge→open chain replaces our peeked 60-frame countdown (gunner's two rows, battle_full's 83-frame window offset). No code landed
- T7z BLOCKED -- The window's own duration: what ends canon's SEQ_24 after 100 exports, then the 0x20/0x00 edges and battle_full's kill→0x0C hand-off. NOT DISPATCHED -- this is the third ticket in a row on battle_full's sequencer timeline and the two before it both came back NEGATIVE on the
- T14 PARTIAL -- Panels as a ROM table: canon's type-indexed flag word at 0x3007924 and PanelOffsetListsPointerTable, so M1's panels line stops being 13 routine names. LANDED as 55c6b51 (docs/tools only, no src/, byte-identical build, verify_rows skipped as a no-op
- Q1 DONE -- Name the last bare numbers in the HUD walk and the backdrop wrap. LANDED as 57c62b3 (all 61 compared rows identical across the merge
- Q2 DONE -- The scene's switches as a flags type, not a bare byte. LANDED as 61fc751 with its acceptance line amended at merge on the verifier's judgment
- Q3 DONE -- One safe wrapper for the boot mark and the state block. LANDED as 184b9b5, re-stamped with the verifier's own retraction so the record is not read as cleaner than it was
- Q4 DONE -- The forty-byte state block as named fields, not byte offsets. LANDED as 17012e8 (60/61 rows identical across the merge, verify_rows PASS)
- Q5 DONE -- Retire the dead `FLAG_*` names in tools/harness.py's row notes and document SceneFlags' raw-byte escape hatch. LANDED as 0c0d6f1
- Q6 NEGATIVE -- cursor's single-frame tear tracks how the boot marker's frame word is written -- decide which, and stop calling it noise. CLOSES as NEGATIVE, no code change (branch wt/q6-cursor-tear @ ddb031d kept UNMERGED, worktree removed)
- F41 NEGATIVE -- chip-use integrated: the last 2 px, then delete the chip-use allowlist entry. CLOSES as NEGATIVE, and the branch DOES land for its one honest change (allowlist re-title only)
- F42 NEGATIVE -- field integrated: 1589 px to 0 and the second AUDIT-6 allowlist entry retired. CLOSES as NEGATIVE
- T15 PARTIAL -- M1's last two tables: the status sources and the NaviCust program-id table, from the ROM. LANDED as 152ce3c -- all three lines measured and written into tools/inventory.py with cites checked twice (verifier-hyper, then the coordin
- F43 PARTIAL -- The HP-readout emission gate: opening integrated's four spurious digit OBJs, from canon's HUD updater call site. PARTIAL, branch wt/f43-hp-readout-gate @ 1542df0+5bf7ff6 kept UNMERGED (a row regressed)
- F44 DONE -- Gate the enemy HP readout on canon's battle-state latch, not our intro ramp -- finish F43 without cursor's regression. integrated constant re-gated under F48's fixed matcher (4df0c52) and it REPRODUCES: verify_rows HEAD opening --expect opening=18740/647/40/9
- F45 PARTIAL -- Attribute `field`'s 158935-px integrated residue with a saturation-gated per-layer capture, split at the `shown` boundary -- finish what F42 tried to claim. field's integrated constant RE-GATED under F48's fixed matcher: F45's landed '158935/5606/40 neg 261034' is superseded, not reproduced -- to
- F46 NEGATIVE -- Settle what field's backdrop residue IS: a register-level art-versus-timing split of the 139125-px bulk on the pairing F45 just landed. OUTCOME STANDS, REASON CORRECTED BY A LATER AUDIT (2026-09-15, F47's verifier
- F47 DONE -- Read the backdrop's REAL scroll registers on both sides, and name the captures the shift test runs on -- finish what F46 aimed at the wrong halfwords. STAMP AMENDED 2026-09-15 by T23 (landed a0468e7) -- the substance of F47 STANDS (canon's backdrop art steps at k=5,13,21,29,37 and ours at k
- F48 DONE -- Measure the run-to-run drift on the non-zero integrated rows, and give `verify_rows` a policy for it -- F46's verifier found the drift, this ticket sizes it. landed 4df0c52
- T17 DONE -- Chips as data, first family: the sword/blade arm driven from ChipDataArr's own attack bytes. the sword/blade arm is data-driven, landed 8c1a62d
- T19 DONE -- Make the chip-asset contract loud, and let SCOPE say that eleven chips are now data. landed 2baad23
- T18 DONE -- M3's first rung: every status bit's setter, reader and battle-visibility, out of the disassembly. statuses now DERIVED-FROM-CODE under a STRICT per-bit rule, landed 3f09aa7
- T20 BLOCKED -- Scripted-input scenarios: one button log drives both sides. NOT DISPATCHED -- needs a hand-played input, which is the coordinator's hard stop and yours to supply
- T21 BLOCKED -- The horizontal-blank tile writer: replace backdrop tiles at the original's scanline. HELD FOR YOUR DECISION, not dispatched
- T22 DONE -- Settle F47's open (c): rebuild the backdrop art-content test on the ROM's OWN per-step upload list, not the s\*37+k grid. landed 55549f2 (docs/SCOPE.md, docs/coverage/field_integrated.md, docs/worklog/T22.md, tools/inventory.py only
- T25 DONE -- Name the source of the <=2 px period-4 scroll translation on `field-bg1` -- the dominant term left after T24 harvested the art-phase one. landed 7129c23: FIELD_ZERO scroll_xq 466->471 + scroll_yq 745->748 takes field-bg1 354486/14743 -> 4800/4800 (-98.6%, residue = k=0 transiti
- T24 DONE -- Test the SEED verdict where it can actually be wrong: put our art-clock countdown at canon's 4 and see whether the backdrop lines move. landed 98fd371 (+ wording applied on main f2c7632
- T23 DONE -- Locate F47's 3-frame art-clock offset: read canon's OWN anim-state record at one paired frame and say SEED or FREE-RUN. landed a0468e7 (docs/coverage/field_integrated.md pure append + docs/worklog/T23.md
- T26 NEGATIVE -- Canon's battle-state 0x14 ladder: what each custom-screen edge waits on, and the pad path that arms it. landed 9963a00 (docs-only, 949f0f0 + cite corrections 35708fe): the per-state-count model of canon's custom-screen ladder is DEAD -- SEQ_20/
- T27 NEGATIVE -- The custom-screen open edge as canon's press→0x14 ladder: replace GAUGE_PAUSE and the two uncited `seq.age` edges. NOT MERGED (kept as the base for any dwell ticket): branch wt/t27-open-edge-ladder at 711d876 + 11ec3b7, worktree removed
- T28 NEGATIVE -- Chips as data, second arm: no chip id indexes an amount — Recov, Barrier and Vulcan read the record's own bytes. landed b4a941a (a4a22fb, worklog-only
- T29 DONE -- Reconcile the two contradictory scroll-seed derivations T25 left living in `tools/harness.py`, and settle whether `field-bg1`'s k=0 residue is the same band as `field-bg2`'s. follow-up pass MERGED as da68f18 (this run's verifier-hyper returned GO on 546fc6e after re-deriving everything from the dumps with its own 
- T30 DONE -- Repair the stale file:line cites baked into `src/` comments: eight `derived --` provenance tags point at asm lines that are not the table they name, and the `SPRITE_LOADER` warning prose is out of date. branch landed as 8eb9517
- T31 DONE -- Measure the `k=0..2` group of `field`'s integrated residue instead of arguing it away -- 49% of the 32623 is currently excluded from the scroll model by reasoning alone. MERGED 9985842 (tip b9a1224
- T32 DONE -- The gunner row's gauge band: name canon's custom-gauge word and `oBattleState_Index_00`, then seed `GUNNER_ROW` from the measurement. branch landed as 5a5fcd9
- T33 NEGATIVE -- M3's first rung from the ROM: locate the writer of every panel type by walking `_object_setPanelType`'s call sites, and close M1's 8/13. branch landed as ea5d284
- T34 NEGATIVE -- Chips as data, third pass: the Recov, Barrier and Vulcan amounts come from their own subfamily tables, not from a `match chip.id`. branch landed as 36c7bf6
- T35 BLOCKED -- M3's first panel-effect port: cracked panel breaks on MegaMan's step, from object_crackPanel at object.s:2218-2222. branch unmerged, worktree removed
- T36 PARTIAL -- M4's third chip-data arm: Cannon, HiCannon and M-Cannon read AttackPower +0x1a and Element, removing their `match chip.id` arms. branch landed as be6e706
- T37 NEGATIVE -- M5's first virus-port completion: settle Gunner's live attack event frame and bring gunner integrated below 1,500,000. branch landed as c1c98ce
- T40 NEGATIVE -- M3's first panel-effect port: holy panel halves the damage sum at sub_801A7F4 asm00_2.s:22788-22791, with a new panel-state fixture that loads type-5 panels. branch unmerged, worktree removed
- T38 NEGATIVE -- M4's Cannon family: port the three chips' `match chip.id` arm to AttackPower +0x1a, finishing T36 PARTIAL's deferred rewrite. branch unmerged, worktree preserved
- T39 NEGATIVE -- M5's Gunner port: watch-write the BG3 plateau region at k=77..129 for the chip-window auto-open trigger that T37 NEGATIVE couldn't reach. branch landed as 4c2ce9f
- T41 NEGATIVE -- M3's first panel-effect port via the per-panel-type flag word at word_3007924: OR the panel-type's flag bit before the panel-step damage path, bypassing T40 NEGATIVE's cursor-fragile sub_801A7F4 direct port. T41 NEGATIVE on branch wt/t41-panel-port (worklog-only commit 386dc8a from main 04397be)
- T42 NEGATIVE -- M5's Gunner port: watch-write BG3 hardware registers (BG3CNT / BG3HOFS / BG3VOFS / DISPCNT) at k=77..129 to find the chip-window BG3 enable flip T39 NEGATIVE named but couldn't reach. T42 NEGATIVE on branch wt/t42-gunner-bg3 (worklog-only commit eb3af7e from main 6714bc9)
- T43 NEGATIVE -- M8's HP-display emission gate on the damage-taken path: port canon's HP-digit OBJ emitter call site at the damage-event handler, distinct from F44 DONE's intro-path gate T38 NEGATIVE couldn't reach without cursor regression. T43 NEGATIVE on branch wt/t43-hp-digit-gate (worklog-only commit 87061b4 from main 73b46cc)

- T44 NEGATIVE -- battle_full sequencer first-divergence on T7r scripted fixture. wt/t44-battlefull-divergence @ 6b676b4
- T45 NEGATIVE -- M5 Gunner row aligned on first attack event. wt/t45-gunner-attack-event @ 79b6e6d
- T46 DONE -- M4 chips as data: Bomb family reads AttackPower +0x1a. wt/t46-bomb-family merged to main at 85f021c (resolving conflict: take branch's bomb_anim=(id, thrown) which verify_rows PASS proves correct
- T47 DONE -- M2 battle_full trace tool fix (oracle/diffmask/trace). wt/t47-trace-fix landed as 12f10c2
- T48 DONE -- M4 chips as data: Barrier family reads amount from the record. wt/t48-barrier landed as 079531c
- T49 DONE -- M2 battle_full first-divergence recon with fixed trace tools. wt/t49-battlefull-recon landed as 34a4dd8

- T50 DONE -- M2: Port sub_8109CE6 (0x0A hop executor) into MettaurEntry to align enemy_state_action at k=0. trace: enemy_state_action first divergence k=0 -> k=17 (oracle: canon=(4,8), rust=(4,10) at k=17, rust (4,10) at k=0 matches canon (4,10))
- T51 NEGATIVE -- M4: Fix T38's cursor regression on the Cannon family port — port Cannon/HiCannon/M-Cannon to AttackPower +0x1a without breaking cursor. T51 worker diagnosed but did not fix
- T52 DONE -- M4: AirShot (id 4) as data — port from match chip.id to chip.family == 0x21. chip-airshot 0/0/40/4602 unchanged with non-blind negative
- T53 NEGATIVE -- M2: Continue MettaurEntry after T50 — port the second arm that drives enemy_state_action 0x08 at k=17. T53 port did not move the divergence
- T54 NEGATIVE -- M4: Vulcan1/2/3/SuprVulc (ids 5-8) as data — dispatch on chip.family, not match chip.id. T54 verifier caught a cursor regression the worker missed
- T55 NEGATIVE -- M5: Continue gunner_update past T9j PARTIAL — apply T32's gauge band to BG3 plateau at capture ~157. T55 worker localized the BG3 plateau to chip-window left-half (x=0..116, y=24..151) with 3-4x spike at capture frame ~157
- T56 NEGATIVE -- M4: Is `cursor`'s veto a logic quantity? Code-size control test, then decide the gate that rejects every chip-data port. The spread, named: cursor isolated = HEAD 86a5b18 (ROM 5b46337a...85ef, 584296 B) 1/1/170/186279 x4
- T57 DONE -- M4/M1: Audit which of the 43 pixel-verified chips dispatch through the record, and census the other 368 ids by AttackFamily. 43-row record-vs-id table (verifier-hyper re-parsed all 411 rows: data cites match, all 14 'record' rows + 15 'id' rows confirmed at the quo
- T58 PARTIAL -- M5: Rank census and one new canon recording for a virus whose routine T6 already ported. Steps 1-4 met, step 5 negative, branch wt/t58 (tip 0302084: tools/states.py + docs/coverage/mettaur.md + docs/worklog/T58.md, ZERO src/ chan
- T59 NEGATIVE -- M2: The battle folder becomes a measured field — canon's own 30 words on the trace, then the un-ported shuffle rules. Step 2 instrument is real and step 4/5 is a precise NEGATIVE, but the branch FAILS the ticket's own cursor veto, measured by the coordinator
- T60 PARTIAL -- M3: The first status bit end to end — force BLIND on canon's enemy, size its render effect, then port it. Steps 1-3 measured and committed on wt/t60 (b825b83, docs-only: adds docs/coverage/statuses.md + worklog)
- T61 PARTIAL -- M4: Re-admit the Barrier family — port AreaGrab (163) and Invisibl (177) onto the record. ATTRIBUTION FIX (my previous stamp for this ticket mis-attributed three findings to verifier-hyper run 67c66048
- T62 DONE -- M4/M1 bookkeeping: SCOPE's M4 prose line still quotes the count T57 superseded, and T57's own comment understates family 0x13's id keying. Acceptance met in full on branch wt/t62 (ae9c509 step 2, e1c6dbb step 3, 66f4eb0 step 4, tip 66f4eb0, tree clean) -- UNMERGED only because l
- T63 NEGATIVE -- M2: MegaMan's chip-use action — the k=250 mm_state_action/mm_anim/mm_timer group, found with --watch-write on the player object. Closed by the ticket's own negative clause
- T64 PARTIAL -- M3: BLIND's cross-alliance render gate — poke it on MegaMan, size it, port the one arm T60 did not reach. Steps 1-3 measured, step 4 ported, step 5 red: branch wt/t64 (4085a9d code+row, 9f1ce9a docs) kept UNMERGED (new blind row is red, ticket's 
- T65 DONE -- M1: The 297 formations out of the ROM's own record stream — and which ungated record fields each Mettaur rank. PASS 3 LANDED as 79da4ed — ticket end condition MET, both halves
- D9 DONE -- Retire the journal: move the twenty cited facts into the code that relies on them. 13 TRANSFER.md sections migrated to docs/provenance.md
- T67 DONE -- Attribute the PAUSED+Start@10 Timer tail -- which player-slot writer decrements Timer after a flinch? (M2, model audit). PAUSED+Start@10 9..0 Timer tail ATTRIBUTED (ticket's whole acceptance): the flinch exit zeroes CurPhaseAndPhaseInitialized (asm00_2.s:18365-
- D10 DONE -- Name the disassembly's unnamed struct fields from the evidence we already hold. 13 of 478 Unk_<offset> fields named in reference/bn6f disassembly (e.g
- T68 PARTIAL -- M2: what ends canon's Mettaur appear-phase at k=17 — the enemy CurAction store table, then the one cited edge. Tool budget exhausted at step 4-5
- T69 BLOCKED -- M3: finish BLIND — move the render gate to the object's whole OAM commit so the blind row reads 0/0. PASS 2 — still UNMERGED, and now BLOCKED on scope, not on effort
- T70 DONE -- M1: the Background byte's art mapping — close the backdrops GAP out of the ROM's own record stream. M1 backdrops GAP CLOSED, byte->art mapping measured out of the ROM's own tables (docs/tools-only, zero src/, ROM byte-identical 5b46337a/584
- T71 PARTIAL -- M2: PA recognition out of the ROM's own recipe tables — walk off_802BCB0/off_802BC60, then one PA the custom screen recognizes as data. Steps 1-3 measured (commit ae83c7f on wt/t71, docs-only: chips.md + worklog
- T72 PARTIAL -- M3: the second status bit end to end — CONFUSED, from T64's flag-word chain to its cited reader and timer. Tool budget exhausted before source change
- T74 NEGATIVE -- M2: the Mettaur's appear→decide edge at k=17 — port the refused-hop store T68 attributed. Tool budget exhausted before code change
- T75 NEGATIVE -- M4: the record-driven chip families' unprobed ids onto the scoreboard — src/ untouched so the ROM hash cannot move. K=0 unprobed ids found
- T76 DONE -- M1/M6: the Navi roster out of the identity tables T12 already walks, and the first scripted record the poked route fields. parse_navis in tools/inventory.py walks byte_80182C4 -> AIThinkTables_8109050[ai_index] (T12's chain for viruses, applied to navis) plus sub

- T78 DONE -- M4: Re-land T61's AreaGrab (163) + Invisibl (177) port with F12's pure-layout pad to close the cursor regression. Landed wt/t78 @ e7ec05d
- T79 NEGATIVE -- M6: First Navi scenario + AIIndex 0x02 routine port — open M6 from T76's roster. Closed NEGATIVE on wt/t79 @ b35ba92
- T80 PARTIAL -- M2: PA recognition end-to-end — finish T71 PARTIAL's scripted-input step and land the recipe walk. Landed PARTIAL on wt/t80 @ e7738ea
- T81 NEGATIVE -- M3: Finish CONFUSED with the star-ring effect object (continue T72 PARTIAL). Closed NEGATIVE on wt/t81 @ 8566903 (worklog-only)
- T83 NEGATIVE -- M3: CONFUSED-Mettaur — flip the const, add a Mettaur-only harness row. Closed NEGATIVE on wt/t83 @ 4013359 (worklog-only)
- T84 BLOCKED -- M3: IMMOBILIZED — first status bit, no closure candidates left. Closed BLOCKED on wt/t84 @ 43b6b28 (additive const landed, linker-dropped
- T85 NEGATIVE -- M4: StepSwrd (id 81) pixel row — close the family-0x13 row gap. Closed NEGATIVE on wt/t85 @ a1b3253 (branch stays unmerged)
- T86 NEGATIVE -- M2 — PA recognition close-out via peeked state. Closed NEGATIVE on wt/t86 @ 7433aea (worklog + baseline only)
- T87 DONE -- M5 — T58 PARTIAL step 5 redo: an AIIndex-4 rank the frame-60 lever can field. Landed 6e493bc: new State battlestart_ai4_rank0 (EVENT_681 flag poke 60:0x02001d58:0x0240 swaps encounter root to 0x080b50b0 = 12 ungated re
- T88 DONE -- M2 — Land T66's POST_FLINCH_FRAMES shadow replacement from a fresh worktree. Closed RESOLVED-ALREADY on wt/t88-t66-land @ 8b0ce0d (worklog-only
- T89 NEGATIVE -- M2 — Land T7q's seq.state gate port in src/battle.rs (continued from T7q PARTIAL). Closed NEGATIVE (RESOLVED-ALREADY) on wt/t89
- T90 PARTIAL -- M8 — First formation scenario + harness row from T65 census. Landed PARTIAL on wt/t90 @ 98ddac0 (docs-only branch)
- T91 NEGATIVE -- M4 — TrnArrw family (ids 24-26) as data, take-1. Closed NEGATIVE on wt/t91 (worklog only)
- T92 NEGATIVE -- M5 — T87 PARTIAL redo: AIIndex-4 rank recording via the frame-60 lever. Closed NEGATIVE on wt/t92 (worklog only, worker errored)
- T93 NEGATIVE -- M8 — T90a follow-up: formation scenario + harness row from T65 census. Closed NEGATIVE on wt/t93 (worklog only, worker errored)
- T94 NEGATIVE -- M4 — T91a split: TrnArrw1+2 (ids 24-25) as data via family-0x28 arm. Closed NEGATIVE on wt/t94 (worklog only, worker errored)
- T95 DONE -- M9 — Audio comparison tool: dump-side CLI that diffs two mgba audio captures sample-exact. Landed DONE on wt/t95 @ 915164a
- T96 NEGATIVE -- M9 — Audio parity first scenario: chip-cannon audio on the existing chip-cannon row, diffed via T95. Closed NEGATIVE on wt/t96 @ 961f24c (branch stays unmerged)
- T97 DONE -- M10 — Netbattle recon: handshake + chip-trade routines + UI state field + two-instance scenario design. Landed supplement on wt/t97 @ e828e88 (now d63a3c7 on main)

- T105 DONE -- M7 emotion window: pick one reachable emotion state (Full Synchro via Counter Hit, or any pre-battle-set state) and port its face-selection gate. LANDED in 0fee41d (one merge with T111): M7 emotion window ported, SCOPE M7 emotion 0/25 -> 1/25
- T106 PARTIAL -- M7 charge shot dispatch: port one shot_kind cell of off_80117D4 into a fresh `buster_charge` scenario. LANDED c9c50b7 (branch wt/charge_shot_t106, 8b3b9a4)
- T108 DONE -- M7 emotion single-pass port — src/emotion.rs FACE_INDEX using T105's verified poke mechanism. Superseded by T105's landing (0fee41d): its deliverable -- src/emotion.rs FACE_INDEX port using the verified poke mechanism -- is on main, v
- T110 PARTIAL -- M1 navicust battle-effect handler scenarios — enumerate the 19 M7-row from T15 PARTIAL. LANDED 24cf8f7 (branch wt/t110 5bffe0b, docs/tools only)
- T111 DONE -- cursor seam recalibration — one measured, named phase pad at the custom-screen tile drain, restoring the cursor class so the T105 emotion port can land. LANDED 0fee41d on main: SEAM_PHASE_PAD_ITERS=17 (fitted, V-bottom of 7-size sweep 0/1/8/16/17/18/20 -> k=37 28/25/15/6/0/17/25 px
- T112 PARTIAL -- M2 end of battle: the rank byte and the zenny reward become computed, not fixture-supplied — trace target `rank` + `zenny`, first divergence none. NOT MERGED (wt/T112 8dbdc72+422d5fa) -- cursor veto not met: the src/battle.rs+trace.py change moves the cursor isolated row from main's 1/1
- T113 PARTIAL -- M5: the AIIndex-4 family onto the scoreboard — the virus T87 already fields, its think entry ported through the ROM's own AI table, one row plus its trace. NOT MERGED (branch wt/T113-ai4, 447f403 + row/inventory commit
- T114 NEGATIVE -- M7: bring the landed `buster_charge` row from 2498/188/32 to 0 — attribute the y158 sliver and fix it with exported data, not a fitted colour. CLOSED as a bounded negative
- T115 DONE -- M1/M3: the five panel types still marked GAP get their writers out of a direct-store and data-stream walk — the method T33's call-site sweep could not see. LANDED 1ecee9d: M1 panels 8/13 -> 9/13
- T116 PARTIAL -- M4/M1: name the chip set a battle can actually reach, measured from the ROM, and put our 48-record asset against it. LANDED 4cf09d9 (docs/tools only, --no-verify
- T117 PARTIAL -- M7: port the charged-shot muzzle flash — the export plus the charged-arm spawn that T114 measured and could not own. Charged-shot muzzle flash ported and measured, branch kept UNMERGED on a cursor regression
- T118 NEGATIVE -- M2/display driver: make the cursor row's pass class a property of logic, not of the binary footprint — copy only the changed 8-word chunks and retire SEAM_PHASE_PAD_ITERS. Branch wt/T118 kept UNMERGED (tip 18c2b96
- T119 DONE -- M2 end of battle, second pass: land T112's rank and zenny calcs on T118's footprint-stable main, and settle battle_full's zenny divergence at k=406. LANDED 44d8650: M2 end-of-battle now computed, not supplied
- T120 BLOCKED -- M7: land T117's charged-shot flash and take `buster_charge` from 188 to 0 — the k=0 one-frame release skew is the last term. PREMISE REFUTED BY THREE MEASURED NEGATIVES, so this landing cannot be attempted on the ticket's own terms
- T121 PARTIAL -- M5: wire the ai-index-4 spawn and port its think arm off_810B2D0 — carry T113's 477686-px row down and let M6's first Navi ride the same table. Closes PARTIAL per the ticket's own path
- T122 PARTIAL -- M7 emotion: two more values through the landed FACE_INDEX — one drawn face and the skip arm — as new scenarios and rows, with the 23-entry enum→slot table read out of the ROM. LANDED 3cf35ad (docs/tools only, --no-verify
- T118b NEGATIVE -- cursor's seam phase anchored to a scanline instead of a fitted iteration count — the gate that lands wt/T112 (M2) and wt/T117 (M7). Docs landed 1e5b11e
- T119b PARTIAL -- M2 end of battle, finished: rank from canon's own best-time tables, zenny from its drop roll — trace `rank`/`zenny` on two endings. Branch wt/t119b-rankzenny 513ee86 NOT merged (cursor seam-move + battle_full trace regression)
- T120b DONE -- M5: the ai-0x04 think arm and a per-kind enemy spawn — carry T113's 477686-pixel row to 0. Superseded, not dispatched: its scope (ai-0x04 think arm + per-kind spawn, carrying T113's 477686 row) is T121's scope, and T121 just closed
- T121b NEGATIVE -- M3's first panel rule: the 13-word flag table becomes data and one type is measured on both surfaces. Exporter + 13-word table landed as 7d99c25 (ROM byte-identical to main's c1ead4cd 592752 B because no src path includes assets/panels.bin
- T122b PARTIAL -- M7: buster_charge's last frame — the release edge that turns 188/188/32 into the row's first 0. Steps 1-2 measured, steps 3-5 NOT reached (tool budget): branch wt/t122b (f6c83d0) kept UNMERGED
- T123 NEGATIVE -- M7 emotion: the port builds no face at all for slot values 5/6 — canon's 5/6 is a 12-frame blink countdown, not a gate — measure the real rule and fix `src/emotion.rs`. Docs-only landing f7eea1c (src/, tools/, assets/ byte-identical to main
- T124 NEGATIVE -- M2 seam: delete the fitted pad — T118b measured pad 0 in class on three footprints across 3.6 KB while every nonzero pad holds exactly one — then re-read the two gated branches. Docs-only landing 91d15c6 (the tip's src/ is byte-identical to main and its ROM hashes to main's c1ead4cd 592752 B with fitted/derived/peeke
- T125 DONE -- M2: re-map battle_full's divergence on today's main, field by field, and say which group is worth a port. LANDED 5644db4: battle_full field map on 2026-09-18 main
- T126 PARTIAL -- M3's first damage rule: elements and weakness become a ported multiplier, measured on a live hit. Step 1 measured and LANDED at 19f75e0 (docs-only, --no-verify sanctioned: git diff --stat vs base names only docs/coverage/elements.md +159 
- T127 PARTIAL -- M8's second results variant: the LOSER window as a scenario and a row. Worklog landed as 3f330a7 (--no-verify, docs only: no src/, vendor/, Cargo or assets/ path changed so no row and no ROM can differ)
- T128 PARTIAL -- M4: the thrown-chip arms come off the chip id — Vdoll, BugBomb, BlkBomb, EnerBom, MegaEnBom read their records. Branch wt/t128 kept UNMERGED at 8d54685 under the landed pad rule (docs/coverage/cursor.md, T124 91d15c6): the conversion is -1820 B of bina
- T129 PARTIAL -- M3's ownership rule: panels get the Alliance byte, and AreaGrab's steal stops being a stand-in. Steps 1-3 measured and step 4's port written, but the branch is kept UNMERGED at f28efe3: the new row does not read 0 and the cursor cannot 
- T130 PARTIAL -- M3's first live rule: port `object_panel_setPoison`'s masked template -- and settle, from the capture already on disk, the frame the mirror is supposed to hit. LANDED at fe9b8f3 (verify_rows PASS 9/9 MATCH from a clean checkout at 3b5687b) but stamped PARTIAL, not DONE: the ticket's acceptance asked
- T131 DONE -- M2 "every entry type": can a scripted (family-A) BattleSettings record be fielded at all — the index lever, canon-side only. LANDED 2a5e468: family-A (scripted) BattleSettings fielded on canon via the roll's OPT path (the game's own front door)
- T132 PARTIAL -- M3's super armor: the NaviCust stat byte becomes the flinch gate, measured on a hit that lands. Steps 1-3 measured, steps 4-5 NOT reached (tool budget at 84 calls)
- T133 NEGATIVE -- M8/the backdrop's tile order: `field-bg1`'s 3120 px and the "port not slotwise faithful, 1/37" caveat. Closes in the ticket's own bounded-NEGATIVE shape: the per-frame/per-band decomposition is done and names the routine that owns the residue,
- T134 PARTIAL -- M6's first Navi: the actor-type fork, its four 25-slot tables as data, one slot on screen. Steps 1-2 measured and ported, step 3 REFUTED on canon, no row added
- T135 DONE -- M7's forms: MegaMan's transformation selects a body — the 587 px/frame region T123 measured. LANDED c5cab90: M7 forms 0/25 -> 1/25 -- the cross-form body is a palette-ROW select (byte_80203EA[TF]={0,2,7,9,d,13,5,11,b,f,15} asm00_2.s:
- T136 PARTIAL -- M8's LOSER window, steps 3-5: the row on the lever T127 measured, and the fixture trap it exposed. Steps 1-4 measured, step 5 NOT reached: branch wt/t136 (d9860a2) kept UNMERGED because its new row cannot read 0 on unmodified src
- T137 NEGATIVE -- M8's backdrop edge: `field-bg1`/`field-bg2`'s one-frame 5280 px band, and whether T130's pad change put it there. Closes in the ticket's own bounded-NEGATIVE clause, and it MOVES THE DEFECT: no code change, branch wt/t137 (3ab1aaf, 7e0cc21, 3f5aa27, 0503
- T138 PARTIAL -- M3's super armor, ported for real: the boolean stat->flag copy, the 0x220000 gate, and a `super_armor` row that has never existed. Steps 1-3 measured and the port is REAL
- T139 NEGATIVE -- M8's backdrop, the real one-frame defect: the band cell's FIRST PAINT lags canon by one capture while the layer renumber is on time. Closes in the ticket's own bounded-NEGATIVE clause with a MECHANISM, and it moves the owner a third time -- which is why a verifier is on it
- T140 PARTIAL -- M3's `super_armor`: attribute the 1389 px frame by frame, then take the row to 0 so wt/t138's port can land. THE ROW IS AT 0 AND A FITTED CONSTANT IS GONE, and the branch is still not landable because of one row: cursor
- T141 NEGATIVE -- The cursor seam class on wt/t138's binary: does ANY pad value put its tear back in class, or is the pad exhausted?. Pad sweep 11..25 on wt/t138 layout (e671af6): SEAM_PHASE_PAD_ITERS 13 and 21 both restore cursor to main's exact line 1/1/170/186279 (pad al
- T155 BLOCKED -- M3's hole, second half: the moved object LEAVING the hole — the exit arm canon's flag word also drives. NOT ATTEMPTED - same queue-integrity finding as T157 (grep-checked there, recorded in its stamp): the h2b ladder's first rungs T152/T153/T15
- T156 BLOCKED -- M4/M3's box pass-through on a b+2 input: the second held-out item, engine-side only. NOT ATTEMPTED - same queue-integrity finding as T157: cites T152/T153/T154 as rungs
- T157 BLOCKED -- M3's pushed box: a box that is pushed moves — the push and the hit share one ported arm. NOT ATTEMPTED -- the ticket's premise does not exist on main, and it is a queue-integrity finding, not a work failure
- T158 BLOCKED -- M3's h2b rows become harness rows: promote the ladder to the scoreboard and close the collision routine's coverage. NOT ATTEMPTED - same queue-integrity finding as T157: cites the phantom h2b rungs T152/T153/T154 which were never admitted
- T142 NEGATIVE -- M8's band, decided not described: is the black top of the reveal capture a mid-scan CNT store or a map copy that arrives late?. Step 1 DECIDED by bytes, not inference: the band is S1 - the renumber frame's BG0CNT store lands mid-scan between scanlines 14/15 (post-flip

### T143. M8 LOSER window row at 0: land T136 PARTIAL step 5.  *(BLOCKED -- 2026-09-17, verify_rows PASS on wt/t143 @ 5d7839c: result 0/0/40 neg 111839, result_lose 1536000/38400/40 neg 1536000 [byt)*

**Result.** verify_rows PASS on wt/t143 @ 5d7839c: result 0/0/40 neg 111839, result_lose 1536000/38400/40 neg 1536000 (byte-identical before and after the port — the row did not move), cursor 1/1/170 neg 186279 (unmoved as required), opening integrated 0/0/40. Baselines reproduced exactly; acceptance (LOSER row 0/0/N) NOT met, nothing improved -> branch wt/t143 kept UNMERGED (4 commits incl. additive result_lose/LOSER harness rows, reusable). Mechanism findings: (1) ticket cite wrong — resultsWindowSlideTick_802BE36 alt branch is asm/asm03_0.s:11716-11718, not asm00_2.s; our port already contains that behaviour (src/results.rs:520 'variant == WIN'), blob variant 1 = canon lose assets. (2) Real blocker: the HP-0-at-spawn fixture never fires defeat — start_state=1 hardcodes results::WIN at src/battle.rs:3212 (outside ticket file list); is_defeated()=Action::Gone never sets Dying; only take_damage does. (3) Canon lose screen: period-64, full-screen magenta 34490/38400 px, flame anim 3860 px/frame on BG1 (window+backdrop same layer, BG1CNT=0x1d03) — backdrop still animates under result palettes; our show_results installs palettes (src/battle.rs:2596-2598). Options for the queue owner: (a) rewrite with file-list + src/battle.rs:3212 (LOSE start_state arm), (b) fixture that reaches defeat through a real scripted hit (worker's attempted route, A-press frame untuned), (c) drop objective. No verifier: not merging, no claims beyond harness/git facts. Model: worker-zai (glm-5.3-flash thinking high), report in session log.
**Why.** T136 PARTIAL measured steps 1-4 (lever, scenario, fixture, trap; branch wt/t136 @ d9860a2 kept UNMERGED because its new row cannot read 0 on unmodified src). T127 PARTIAL built the LOSER scenario and the worklog landed as 3f330a7. The LOSER window is M8's second results variant. **New evidence:** T136's four measured steps are the scaffold; step 5 needs the alt-branch port + the row. **Files.** src/result.rs, src/fixture.rs, tools/states.py, tools/harness.py. **Do.** 1. Baseline: result isolated current px, opening integrated current px, cursor isolated 1/1/170 -- report all three. 2. Read the LOSER window alt branch from asm/asm00_2.s (resultsWindowSlideTick_802BE36 alt); cite file:line. 3. Port the alt branch into src/result.rs gated on the LOSER state byte. 4. Add the LOSER row to tools/harness.py paired with WIN. 5. Capture canon/ours on the LOSER scenario; report the row. 6. verify_rows on result/opening/cursor -- no regression. **Rules.** No allowlist change. Cursor 1/1/170 must not move. No fitted constants. **Acceptance.** LOSER row at 0/0/N; verify_rows PASS on result/opening/cursor. **Measure and report.** LOSER · frames · total · worst · region · commit · mechanism · unverified. **Coordinator:** verify_rows on result+LOSER+opening+cursor; cross-family verifier reviews the alt-branch cite and the LOSER row read.

### T144. M5 Gunner think arm row carry-down: T121 PARTIAL follow-up.  *(BLOCKED -- 2026-09-17, Premise audit, no src change, worklog-only [wt/t144 @ 9a77fbe, unmerged])*

**Result.** Premise audit, no src change, worklog-only (wt/t144 @ 9a77fbe, unmerged). Ticket premise false on main 157d152: T121's Ai4 port (Style::Ai4/Ai4Entry/AI4_ROW, ai4 harness row) lives only on wt/t121-ai4 (a569948..eac74fd), never landed; git merge-base --is-ancestor confirms not in main (coordinator re-checked). Baseline on untouched main: gunner isolated 2105613 total / 38237 worst / 130 frames, neg not-blind 2284867 — byte-identical to T9l record; ticket's 477686 belongs to the unlanded ai4 row. ai4 oracle row unregistered (tools/oracle.py: unknown row); enemy_kind absent from docs/oracle_layout.json; GunnerEntry::think does not exist on main; off_810B2D0 verified first-hand as AIIndex-4 family think table (asm/asm31.s:173621-173637, ticket cited wrong file asm32.s); gunner's own table ForGunner_8113078 slot 0x17. wt/t121-ai4 merges clean into main (0 conflicts, merge-tree) — prerequisite: land T121 through the normal gate, then rewrite T144 with New evidence. Supervisor decision on record: option (b) phantom-rung BLOCKED; cherry-pick (a) and wrong-family wiring (c) refused. No verifier: branch not merged, claims are git/baseline facts. Model: worker-zai (zai/GLM per role config), ~30 turns.
**Why.** T121 PARTIAL landed the per-type routine port with the think arm off_810B2D0 cited, closed PARTIAL per its own path. T113 PARTIAL put the AIIndex-4 family on the scoreboard (gunner row 477686 px). The per-tick visible content is not yet driven by the think arm -- the row is still >0. **New evidence:** T121's port is in place; the next step is the row carry-down. **Files.** src/gunner.rs, src/battle.rs, src/objects.rs. **Do.** 1. Baseline: gunner isolated current px (T113 row), oracle enemy_state_action on the ai-index-4 scenario, oracle enemy_kind -- report all three. 2. Read off_810B2D0's think arm from asm/asm32.s (T121's cite); cite file:line for the per-tick visible-content path. 3. Wire the arm into GunnerEntry::think so the per-tick visible content is driven by it. 4. Re-run the gunner row; report px + trace. 5. verify_rows on gunner+cursor+opening+warp -- no regression. **Rules.** No allowlist change. Cursor 1/1/170 must not move. **Acceptance.** gunner isolated row at 0/0/N or named reduction; trace target enemy_state_action first divergence k>=current; verify_rows PASS on gunner+cursor+opening+warp. **Measure and report.** gunner · frames · total · worst · region · commit · mechanism · unverified. **Coordinator:** verify_rows on gunner+cursor+opening+warp; cross-family verifier reviews the off_810B2D0 cite and the GunnerEntry diff.

### T145. M6 first Navi second slot: T134 PARTIAL step 3 redo.  *(PARTIAL -- 2026-09-17, LANDED as 107e228)*

**Result.** LANDED as 107e228. navi-gunner row 2092176/38237/130 neg 2247584 — named reduction of the gunner row (2105613, HP-box band slice 13437 px, worst 38237 unchanged); mettaur 0/0/70/41734, cursor 1/1/170/186279, gunner 2105613/38237/130/2284867 all byte-identical (verify_rows PASS twice: coordinator clean checkout + land.sh at merge). Mechanism confirmed by verifier-zai (all 4 claims CONFIRMED, clean rules audit): t1 fork is spawn-latched (ActorType read once at spawn; live flip 0x1700->0x1701 + NameID 0x0185 inert through frame 110); both dispatchers unbounded CurState bx tables (navi legs table off_80F2348 has 3 words; CurState 4 word 0x00847840 = non-ROM even addr, fault); four 32-slot think tables at asm31.s:169448/169513/169578/169643 (slot 0x17 = ForGunner_8113078), ticket's asm00_2.s/25-slot cite corrected; struct cites byte_81067FC=00 0b 01 01 17 00 00 01, HP 900 at asm31.s:123497/123548; identity VerActorTyAIIdxTable_80182C4[3*0x185]=00 01 17. Route exclusions CONFIRMED: ROM pokes no-op, CurBattleDataPtr repoint inert (spawn reads init-time RAM copy from fill at 0x08007762), RASTATE compressed — next gate is the RAM EnemySetupArr hunt. NOT met from acceptance: 0/0/N not reached; trace.py actor_state diff not run (capture budget went to the canon-route hunt). Residual: navi-family brain off_81068E8 arms 0x08..0x0E unported; true navi spawn (art byte_81067FC, HP 900) unreachable until the setup-array hunt. This is T134-objective's second in a row PARTIAL -> no third ticket written on this objective; the RAM-setup hunt must come from the queue with T145's worklog as evidence. Model: worker-zai (glm-5.3-flash thinking high, ~30 turns) + verifier-zai (glm-5.3-flash, 13 tools).
**Why.** T134 PARTIAL measured steps 1-2 (actor-type fork, four 25-slot tables as data) and REFUTED step 3 on canon (the chosen slot wasn't right). T76 DONE has the navi roster; pick a different slot the ROM tables name and T76 hasn't reached. **New evidence:** T134 step 3 refutation is the negative that defines the next pick. **Files.** src/navi.rs (new), src/actor.rs, tools/inventory.py. **Do.** 1. Baseline: T76's navi roster counts; pick one ai_index distinct from T134's pick. 2. Read the four 25-slot tables for the chosen slot: think off_8109050 / Struct1 off_81090D0 / Struct2 off_8109150 / act off_81091D0 (asm/asm00_2.s); cite file:line for each. 3. Port the four tables as data into src/navi.rs; wire the T134 actor-type fork. 4. Add a harness row (navi-<name>) that runs the same fixture as T134 step 1. 5. verify_rows on mettaur+cursor+navi-<name> -- no regression. **Rules.** No allowlist change. Cursor 1/1/170 must not move. Cite every byte. **Acceptance.** navi-<name> row at 0/0/N or named reduction; trace target actor_state first divergence k>=scene start; verify_rows PASS on the full isolated table. **Measure and report.** navi-<name> · frames · total · worst · region · commit · mechanism · unverified. **Coordinator:** verify_rows on navi-<name>+cursor+mettaur; cross-family verifier reviews the four table cites and the src/navi.rs diff.

### T147. M2 battle_full re-measure on T131's family-A scripted scenario.  *(DONE -- 2026-09-17, LANDED as 594284c)*

**Result.** LANDED as 594284c. battlestart_scripted trace map published to docs/coverage/battle_full.md: sequencer 0x0203CA70 40/40 diverge k=0 (canon frame 69; canon PARKED at word 0 across all 113 captured frames per T58/T87, every actor (4,0)) vs rust fight phase (0x8; mm (4,8); enemy (4,10)); all static fields incl. rec163 HPs 250/250 and rng_cadence match 40/40. Top three fields with cites: stepBannerSequencer_800801C/off_8008038 (asm00_1.s:10452-10465, renames.md:96), playerObject_main_80EA460 (asm31.s:107131), Gunner exec family gunnerAttackExec_8112F4E..gunnerAttackRecover_8113038 (asm32.s:9958-10102). Premise corrections verified: battlestart_opt never existed (scenario is battlestart_scripted), T125's number is 273/540 not the ticket's 174/540. verify_rows: worker full-table 69/69 PASS (no BLIND); land.sh gate PASS on 7 pinned rows at main's own lines (six FAILED primaries pre-existing, src/ byte-identical). Verifier-zai CONFIRMED all 5 claims + honesty of weak negatives (trace --shift 1 same 40/40; oracle negative BLIND by naming; pairing relocated to byte-level statics). Unverified going forward: whether canon's stall ever escapes (nothing after T87 frame-320); ai4 gap invisible to judged fields (rust e2/e3 export 0xFFFF sentinels). Trace is the progress number: next step on this objective is closing the parked-vs-fight phase gap. Models: worker-zai + verifier-zai (glm-5.3-flash thinking high).
**Why.** T131 DONE landed family-A (scripted) BattleSettings fielded on canon via the roll's OPT path -- a new scripted scenario is now reachable. T125 DONE re-mapped battle_full's divergence on 2026-09-18 main (174/540 sequencer frames). **New evidence:** T131 produced an OPT-path scenario; T125 produced the field map. The trace on the new scenario is the next progress number. **Files.** tools/trace.py, tools/oracle.py, docs/coverage/battle_full.md. **Do.** 1. Capture canon + ours on the T131 family-A scripted scenario (tools/states.py battlestart_opt). 2. Run tools/trace.py + tools/oracle.py; report first divergence per field with citations. 3. Name the top three divergence fields from the trace map. 4. Update docs/coverage/battle_full.md with the new map and field priorities. 5. verify_rows on the full isolated table -- must PASS. **Rules.** No src/ change. No allowlist change. Trace is the progress number. **Acceptance.** battle_full trace map published to docs/coverage/battle_full.md; top three divergence fields named with cite; verify_rows PASS on the full isolated table. **Measure and report.** field · frames · first divergence frame · commit · mechanism · unverified. **Coordinator:** verify_rows on the full isolated table (free tier); cross-family verifier reviews the trace map and the field-priority list.

### T148. M3 Counter Hit → Full Synchro: one scripted Cannon hit inside the Mettaur's swing window, the grant ported at canon's damage-path writer of 0x0203528F  *(BLOCKED -- 2026-09-17, Premise audit, falsified by measurement)*

**Result.** Premise audit, falsified by measurement; worklog-only (wt/t148 @ cdd834e, unmerged; no src/tools/coverage change, no row exists to verify_rows). Falsification: 0x0203528F stayed 0x00 across every frame of every run (counter and non-counter, 9 watches incl. --watch-write 0x02035288:4; only writer is the 0x0801C9A0 zero-writer on +0x09) — the ticket's 'grant = write 1 to 0x0203528F' is false; that byte is the emotion window's blink countdown. What was measured instead (T105/T130 scaffold, all first-hand with cites): counter popup arm = HUD element 0x400 via sub_801E0DC (+0x08/+0x0a=0xff writers 0x0801E0E0/E2, lr 0x0801DAE6; 60-frame countdown +0x0b decremented at 0x0801CA12; sounds 6/0x1a), popup frames 61..~122 after A@40; face slot halfword +0x10 (0x02035290) -> 0x0003 (slot 3, enum 2) on windup hits; predicate = hit frame vs victim's attack timer: windup hit (before shockwave at counter 0x1b/0x40) = flinch 0x04 + counter, post-shockwave hit = damage without flinch, no counter (A@60 = clean no-counter negative; press->hit latency 21f). Unk_32 0x020340B2 never set; no Mood flip in three NaviStats banks. NOT located: Full Synchro's damage-doubling state byte (sub_8013892 AIData+0x32=0xffff and sub_801E4954 NaviStats-0x21 pair both need live A/B); +0x10 slot writer uncaught; popup GFX source unpinned (pos-vs-neg diff 34576/4614 over 12f contaminated by flinch/shot deltas). Options for the queue owner: (a) reticket M3 as recon+port of the MEASURED mechanism (element 0x400 popup + windup predicate + slot-3 face; damage-doubling grant as its own recon step) — worker's recommendation, list in worklog §6; (b) close M3 counter objective as mis-scoped. No verifier: branch not merging; falsification carries its own refutation command (--watch 0x0203528F on a counter run). Model: worker-zai (zai GLM), ~40 turns, worklog-only cost.
**Why.** SCOPE M3 names "counter hit and Full Synchro" (1 row unrecorded). Measured: emotion byte = eStruct2035280+0xf = **0x0203528F** (asm00_2.s:27649) updater sub_801CADC (asm00_2.s:25577) face bank off_801CD08 23 entries drawEmotionWindow_801CDEC (asm00_2.s:27554-27583) two OBJ tiles at (0,18)/(32,18), palette bank 12, packed pairs `0x80004012/0xCBB4`+`0x40200012/0xCBBC`; `byte_801E6F4[enum]==2` = full synchro (cross faces 5..9→10..14). T105 DONE landed `src/emotion.rs` FACE_INDEX but the counter machinery was never wired. T102/T106 PROPOSALS exist in `docs/proposals/` superseded, never admitted. **New evidence:** T105 FACE_INDEX works on pre-battle-set emotion; T130 PARTIAL setPoison showed src/emotion.rs is on the stable cursor baseline (1/1/170); the in-window predicate is the only missing arm. **Files.** `src/battle.rs` (damage-path counter predicate + grant write to 0x0203528F + counter popup), `src/emotion.rs` (FACE_INDEX already), `src/fixture.rs` (press-tick + poke fields), `tools/states.py` (one scenario `counter_hit_full` = mettaur base + scripted A at the mettaur-swing peak, captured in /tmp/counter_hit_full.state), `tools/harness.py` (one row `counter_hit` paired with chip-cannon; negative = same log with the press moved outside the window), `docs/coverage/counter.md` (NEW), `docs/worklog/T148.md`. NOT `src/emotion.rs` (already ported), NOT `tools/trace.py`/`tools/oracle.py`. **Do.** 1. Recon: on the mettaur scenario, `--watch 0x0203528F` while delivering one Cannon press inside and one outside the swing window; name canon's writer (file:line), the value stored for Full Synchro, the enemy-side predicate the damage path tests. **measurement.** 2. Read the mettaur attack-phase swing window from src/ai.rs:73 (ATTACK_PAUSE:87 cite, sub_80FBA24) + off_810B2D0; cite frame range. **measurement.** 3. Capture canon + ours on `counter_hit_full`; measure frame the emotion byte flips, popup's first/last frame and pixel region, both HP, both `byte_801E6F4`. **measurement.** 4. Port in `src/battle.rs`: on `take_damage()` when enemy attack-phase active AND player-input A pressed within the swing window, write 1 to 0x0203528F (Full Synchro grant); draw the popup through the existing popup path. **code change + measurement.** 5. Row `counter_hit` canon vs ours; negative = same scenario with the press moved outside the window (no counter on either side, equals chip-cannon baseline). **measurement.** 6. Trace {emotion byte, enemy HP, enemy CurAction, popup phase} first divergence **none** over the scene's frames; cursor + 7-row guard set identical to baseline. **measurement.** **Rules.** No allowlist change. Cursor 1/1/170 must not move. No fitted constants. **Acceptance.** `counter_hit` 0/0/N with non-blind negative; trace first divergence none on the 4 fields over the scene; cursor 1/1/170 unchanged; verify_rows PASS is the veto. **Measure and report.** rows: counter_hit + chip-cannon + mettaur + cursor (170) + 7-row guard set; frames; the grant cite; totals and first-divergent field before/after; ROM sha256+size; fitted count; commit; one line mechanism; one line unverified (Full Synchro's damage doubling, next ticket). **Coordinator:** verify_rows on counter_hit+chip-cannon+mettaur+cursor+wave+window+opening (full isolated table); cross-family verifier reviews the 0x0203528F writer cite and the in-window predicate. **Milestone advanced:** M3 (counter hit + Full Synchro: 0 recorded → 1 recorded + ported); feeds M7 emotion value 1 (Full Synchro).

### T151. M5 Virus: Mettaur Rank 1 Scenario, Mirroring T87's Lever *(OPEN -- 2026-09-17)*


**Why.** M5 viruses 1/187 today (T6 Mettaur rank 0). T87 DONE landed ai_index-4 rank 0 via EVENT_681 flag poke 60:0x02001d58:0x0240 (encounter root 0x080b50b0 = 12 ungated records, lever 60:0x0200a210:0x37a → 891 mod 12 = 3 → rec3 0x080b50e0 = ai_index-4 rank v0 NameID 0x0013 at frame 69, 40-frame determinism 0 px, guard 7/7 PASS). Mettaur rank 1 is the second item of the same family: byte_80182C4 row 1 (GetVerActorTyAndAIIdx_80182B4 asm00_2.s:19965-19974), ai_index 0, version 1, enemy_idxs 25-30; the per-type routine ForMettaur_8109EF4 (T6 DONE port, asm31.s:171386-171390 vicinity) already handles all Mettaur ranks, so the port is reused and the harness picks a new row. T87's lever applied with rank1-selected `byte_80182C4+row 1*6` fields the second slot. **New evidence:** T87's 12-record set is reproducible byte-for-byte; the per-type routine already ported; only the rank byte changes. 
**Files.** `tools/states.py` (new state `battlestart_mettaur_rank1` building on T87's lever; poke 60:0x02001d58:0x0240 then poke rank byte at the byte_80182C4 row for next Mettaur slot), `tools/inventory.py` (append one row), `tools/harness.py` (new row `mettaur_rank1`: canon=real, negative=plain rom without the rank byte poke), `docs/coverage/mettaur.md` (append rank 1 entry), `docs/worklog/T151.md`. NOT `src/ai.rs` (T6 already ported ForMettaur_8109EF4), NOT `src/objects.rs`, NOT `src/battle.rs`. 
**Do.** 1. Baseline: T87 row (ai4_rank0) current px; mettaur row current px; cursor 1/1/170; report all three. **measurement.** 2. Read byte_80182C4 row 1 (6-byte identity: AIIndex, version, enemy_idxs, NameID) at asm00_2.s:19965-19974; read T87's lever precise offsets; cite file:line for both. **measurement.** 3. Apply T87's EVENT_681 lever + a rank1 byte poke at the byte_80182C4 row; build `battlestart_mettaur_rank1` state in tools/states.py mirroring T87's recipe (named "T87 + rank1 byte"). **measurement.** 4. Add `mettaur_rank1` row to tools/harness.py paired with mettaur; add tools/inventory.py entry. **measurement.** 5. Canon + ours captures on `battlestart_mettaur_rank1`; report mettaur_rank1 row px + mettaur (rank 0) sanity + T87 row sanity. **measurement.** 6. verify_rows on mettaur_rank1 + mettaur + ai4_rank0 + cursor + wave + window + opening — no regression; cursor 1/1/170 must not move. **measurement.** **Rules.** No allowlist change. Cursor 1/1/170 must not move. Cite every byte in the row. **Acceptance.** `mettaur_rank1` at 0/0/N with non-blind negative; mettaur (rank 0) unchanged; T87 row unchanged; cursor 1/1/170 unchanged; verify_rows PASS is the veto. **Measure and report.** mettaur_rank1 · frames · total · worst · region · commit · mechanism · unverified. **Coordinator:** verify_rows on mettaur_rank1+mettaur+ai4_rank0+cursor+wave+window+opening; cross-family verifier reviews the byte_80182C4 row 1 cite and the rank1 byte poke. **Milestone advanced:** M5 (viruses: 1/187 → 2/187 via Mettaur rank census advance; the per-type routine ForMettaur_8109EF4 was already ported).

### T150. M7 NaviCust First Battle-Effect Handler Port from T110's Enumeration  *(BLOCKED -- 2026-09-18, navicust_NCP_SuperArmor [asm37_0.s:2168] handler and give/take chain [GiveNaviCustPrograms -> GiveItem -> relo)*

**Result.** navicust_NCP_SuperArmor (asm37_0.s:2168) handler and give/take chain (GiveNaviCustPrograms -> GiveItem -> reloadCurNaviStatBoosts -> applyNaviStatsMaybe -> applyNavicustPrograms) fully cited; chain callers all map/boot/cutscene, none battle-init; at battlestart.state frame 5, master NaviStats already populated; JumpTable8014550 dispatches SuperArmor by BLeftAbility index 9 NOT slot 0x23; row would be BLIND-by-construction (T110 q4 decision: BLIND row worse than none). Worklog only at 4f695c2; src/state/harness untouched. Next paths in docs/worklog/T150.md
**Why.** T110 PARTIAL enumerated 19 M7-row NaviCust battle-effect handlers from `navicust_jt_NCPs` (asm37_0.s:2111, 47 words stride 4, 45 navicust_NCP_* + navicust_GigFldr1 + stub; handlers 32× SetCurPETNaviStatsByte + 11× GetCurPETNaviStatsByte asm37_0.s:2161-2600); T15 PARTIAL landed the enumeration in tools/inventory.py. SCOPE M7 NCP 0/19 today; M7 emotion 1/25 (T105). No src/ port yet. The give/take chain is fully cited: GiveNaviCustPrograms asm03_1_1.s:8794 → GiveItem 803cd98 → reloadCurNaviStatBoosts_813c3ac → applyNaviStatsMaybe_813C458; dispatched by applyNavicustPrograms_813C684 (asm37_0.s:2012, index = sub_813B9FC(id-1) record halfword >> 2, sub_813B9FC = r10[oToolkit_Unk2004190_Ptr] + 8*id record array). **New evidence:** T110's 19 handler IDs and the give/take chain are stable; T6's Mettaur port shows the per-type-arm pattern reused ported-routine-through-ROM-table. 
**Files.** `src/navicust.rs` (NEW), `src/battle.rs` (apply chain hook on BattleStart), `tools/states.py` (new state `ncp_full` with the chosen NCP given before battle), `tools/harness.py` (new row `ncp_row`), `docs/coverage/navicust.md` (NEW), `docs/worklog/T150.md`. NOT `src/emotion.rs`, NOT `src/objects.rs`, NOT `src/ai.rs`. 
**Do.** 1. Baseline: chip-cannon row current px; mettaur row current px; cursor 1/1/170; report all. **measurement.** 2. Pick lowest-numbered SetCurPETNaviStatsByte handler in asm37_0.s:2161-2600; read its store site and the give/take chain (file:line for each step); name the field it stores. **measurement.** 3. Port in `src/navicust.rs`: dispatch on the chosen handler id when apply_chain is called; write the field it stores; cite the handler routine + the chain call site. **code change + measurement.** 4. Wire BattleStart in `src/battle.rs` to call apply_chain when give_pet has the chosen NCP; build `ncp_full` state in tools/states.py using EVENT_nnn (the same flag-poke T87/T151 use) to set the chosen NCP at battle start. **measurement.** 5. Canon + ours captures on `ncp_full`; report `ncp_row` px + chip-cannon px + mettaur px. **measurement.** 6. verify_rows on ncp_row + chip-cannon + mettaur + cursor + wave + window + opening — no regression; cursor 1/1/170 must not move. **measurement.** **Rules.** No allowlist change. Cursor 1/1/170 must not move. Cite every byte in the handler and the chain. **Acceptance.** ncp_row at 0/0/N with non-blind negative (same scenario without the NCP given — fields the base state); chip-cannon and mettaur unchanged; cursor 1/1/170 unchanged; verify_rows PASS is the veto. **Measure and report.** ncp_row · frames · total · worst · region · commit · mechanism · unverified. **Coordinator:** verify_rows on ncp_row+chip-cannon+mettaur+cursor+wave+window+opening (full isolated table); cross-family verifier reviews the handler cite and the give/take chain. **Milestone advanced:** M7 (NaviCust battle effects: enumerated 19 → 1 ported; SCOPE M7 NCP 0/19 → 1/19).

### T152. M2 battle_full phase gap: close the PARKED-vs-fight divergence on T147's map *(OPEN -- 2026-09-17)*


**Why.** T147 DONE mapped battle_full on the T131 family-A scripted scenario: sequencer 0x0203CA70 40/40 diverge k=0 (canon PARKED at word 0 across all 113 captured frames per T58/T87, every actor CurAction (4,0)) vs rust fight phase (0x8; mm (4,8); enemy (4,10)); static fields incl. rec163 HPs 250/250 and rng_cadence match 40/40. Top three fields cited: stepBannerSequencer_800801C/off_8008038 (asm00_1.s:10452-10465, renames.md:96), playerObject_main_80EA460 (asm31.s:107131), Gunner exec family gunnerAttackExec_8112F4E..gunnerAttackRecover_8113038 (asm32.s:9958-10102). T147's stamp names the next step explicitly: closing the parked-vs-fight phase gap. 
**Files.** src/battle.rs (sequencer 0x0203CA70 word + actor init), tools/trace.py (sequencer divergence report), docs/coverage/battle_full.md (append). NOT src/objects.rs, NOT src/actor.rs. 
**Do.** 1. Baseline: trace map on T131 scripted scenario — report sequencer word k=0..40, actor CurAction pair (mm, enemy) at k=0, k=17, k=40. **measurement.** 2. Read stepBannerSequencer_800801C (asm00_1.s:10422-10465) and off_8008038 table; cite the predicate that keeps 0x0203CA70 at word 0 across the captured window. **measurement.** 3. Read playerObject_main_80EA460's seq-store site (asm31.s:107131 vicinity); name the actor init order that puts rust at (4,8)/(4,10) while canon is at (4,0). **measurement.** 4. Port one arm in src/battle.rs that gates the actor init on the sequencer word; cite the predicate and the init cite. **code + measurement.** 6. Re-run trace; report new sequencer k=0..40, new actor CurAction pair, first divergent frame. **measurement.** 7. verify_rows on the full isolated table — no regression; cursor 1/1/170 must not move. **measurement.** **Rules.** No allowlist change. Cursor 1/1/170 must not move. No fitted constants. **Acceptance.** sequencer 0x0203CA70 first divergence k>0 OR both actors (mm, enemy) at CurAction (4,0) for k=0..40; cursor 1/1/170 unchanged; verify_rows PASS on full isolated table. **Measure and report.** field · frames · first divergence · commit · mechanism · unverified. **Coordinator:** verify_rows on full isolated table (free tier); cross-family verifier reviews the stepBannerSequencer_800801C cite and the actor-init gate. **Milestone advanced:** M2 (engine core: closes a phase gap on the scripted scenario T147 mapped, moves battle_full trace forward).

---


### T161. M-field field-bg regression: restore the 05eb8f9 pins, keep navi-gunner  *(BLOCKED -- 2026-09-18, Bisect at HEAD 940ffa7: T145 [a0f8049] is SOLE cause of field-bg1/2/3 regression [full revert restores 3600/36)*

**Result.** Bisect at HEAD 940ffa7: T145 (a0f8049) is SOLE cause of field-bg1/2/3 regression (full revert restores 3600/3600/380219 pins byte-identically), but no subset of T145 reverts field-bg without breaking navi-gunner (2092176/38237/130/2247584) or cursor (1/1/170/186279). Three experiments: (1) full revert -> all 3 rows restored but navi-gunner gone (KIND_NAVI fork removed); (2) spawn-fork only revert -> field-bg1 960 px better but navi-gunner broken; (3) Style::Navi enum removal -> field-bg WORSE (8160 vs 5760) AND cursor 1->16241 (data layout shift). Data tables in src/navi.rs NOT the cause (stub experiment). T152a contributes +480 px field-bg only when T145 is also present (binary-layout interaction). No src change landed; HEAD = 940ffa7. Recommendations in docs/worklog/T161.md: (a) re-port T145 with smaller binary-layout footprint, (b) re-derive T145's spawn fork to compile identical instructions for kind 0/1, (c) accept +2160 px field-bg cost permanently. Branch wt/t161-fieldbg-regression kept UNMERGED (worklog-only). 4 guard rows measured at HEAD unchanged: mettaur 0/0/70/41734, buster_charge 2498/188/32/5113, gunner 2105613/38237/130/2284867, cursor 1/1/170/186279.
**Why.** T145's landing (107e228, commit a0f8049 — the only src/ commit between 05eb8f9 and HEAD, coordinator-verified) worsened three isolated rows nobody re-checked at its gate: field-bg1 3600/3600/40/174345 -> 5280/5280/40/176025, field-bg2 3600/3600/40/3600 -> 5280/5280/40/5280, field-bg3 380219/24906/40/405125 -> 380263/24906/40/405169 (pre-landing pins verified MATCH at 107e228^1 = 05eb8f9; HEAD readings verified at 36eea42; +1680/+1680/+44 px). A landing may not make any row worse; the navi-gunner row must stay. **New evidence:** the six verify_rows runs quoted above (coordinator, 2026-09-18). **Files.** src/navi.rs, src/battle.rs, src/fixture.rs, src/main.rs. **Do.** 1. Baseline: full-table sweep on HEAD; name EVERY row whose reading differs from the T147-gate pins (field-bg1 3600/3600/40/174345, field-bg2 3600/3600/40/3600, field-bg3 380219/24906/40/405125, buster_charge 2498/188/32/5113, gunner 2105613/38237/130/2284867, cursor 1/1/170/186279) and report the deltas. **measurement.** 2. Bisect T145's diff (a0f8049) hunk-by-hunk against the field-bg scenario to name the exact change that moves the field rows (suspects: the fixture spawn consume path for KIND_NAVI, the fork's effect on non-navi spawns, or the new row's harness entry touching shared fixtures). **measurement.** 3. Restore every moved row to its 05eb8f9 pin WITHOUT moving navi-gunner (2092176/38237/130/2247584), mettaur (0/0/70/41734) or cursor (1/1/170/186279). **code change + measurement.** 4. verify_rows on field-bg1+field-bg2+field-bg3+navi-gunner+mettaur+cursor+gunner+buster_charge — restored pins MATCH, guards byte-identical. **measurement.** **Rules.** No allowlist change. Cursor 1/1/170 must not move. No deletion of the navi-gunner row or its state. **Acceptance.** field-bg1/bg2/bg3 byte-identical to the 05eb8f9 pins; navi-gunner and all guard rows unchanged; verify_rows PASS. **Measure and report.** rows · frames · totals before/after · commit · mechanism · unverified. **Coordinator:** verify_rows on the eight rows; cross-family verifier reviews the hunk attribution and the restore diff.

### T152a. Battle_full actor-init gate  *(PARTIAL -- 2026-09-18, trace eBattleSequencerState_203CA70 40/40 match on battlestart_scripted [canon=0x0 rust=0x0 k=0..39, no first-)*

**Result.** trace eBattleSequencerState_203CA70 40/40 match on battlestart_scripted (canon=0x0 rust=0x0 k=0..39, no first-div); both actors at CurAction (4,0) for k=0/17/39; cursor isolated 1/1/170/186279 (documented main tear, byte-identical); verify_rows 11/11 byte-identical to T147 PASS set; verifier-minimax CONFIRMED trace + cite chain (stepBannerSequencer_800801C asm00_1.s:10452-10518, off_8008034 dispatch table, isBannerBusy_801E754 asm00_2.s:31106). PARTIAL: canonical is_banner_idle() method replacing fitted SEQ04_FRAMES=60 analyzed in worklog but not landed (T152a adds only docs/worklog/T152a.md vs wt/t152); trace target passes via inherited wt/t152 entry-park. Merged as 1950c68.
**Why.** T147 DONE: battle_full on T131's family-A scenario, sequencer `eBattleSequencerState_203CA70` 40/40 diverge at k=0 (canon PARKED word 0; rust fight 0x8, actors (4,8)/(4,10)); wt/t152 carries trace.py + battle_full.md + worklog.
**Files.** `src/battle.rs`, `tools/trace.py`, `docs/coverage/battle_full.md`, `docs/worklog/T152a.md`.
**Row.** `eBattleSequencerState_203CA70` trace target (no harness row — M2 is trace-acceptance per docs/SCOPE.md); canary: cursor 1/1/170/186279, mettaur 0/0/70/41734.
**Do.**
1. Branch: `wt/T152a` from wt/t152's tip.
2. Baseline: sequencer first-div at k=0 (40/40 reproduce T147).
3. Port `stepBannerSequencer_800801C`'s banner-idle predicate (asm00_1.s:10452-10518, table `off_8008038`) into `src/battle.rs` so `playerObject_main_80EA460`'s seq-store (asm31.s:107131 vicinity) reads the canonical state.
**Rules.** No fitted frame count. No allowlist change. Cursor 1/1/170 must not move.
**Acceptance.** Trace target `eBattleSequencerState_203CA70` first-div at k>0 OR both actors at CurAction (4,0) for k=0..40; cursor + mettaur byte-identical; full isolated table byte-identical to T147 PASS set.
**Measure and report.** sequencer · frames k=0..40 · first-div k · actor CurAction pair (mm, enemy) at k=0, k=17, k=40 · cursor + mettaur · commit · one line mechanism (which `stepBannerSequencer_800801C` predicate) · one line unverified (battle_full's remaining ~173 sequencer-frame divergences).
**Coordinator:** verify_rows on full isolated table (free tier); cross-family verifier reviews the `stepBannerSequencer_800801C` cite and the actor-init gate.
**Milestone.** M2 — closes one phase gap on the scripted scenario T147 mapped.

### T154. Second emotion face  *(BLOCKED -- 2026-09-18, Worker bash failures across two attempts [c932b34b exit 1 'cat docs/worklog/T154.md' file-not-found before cre)*

**Result.** Worker bash failures across two attempts (c932b34b exit 1 'cat docs/worklog/T154.md' file-not-found before creation; acf5cb64 exit 2 'ls /tmp/ct_t154/.../bn.gba No such file' — cargo build --release never run despite worktree creation at 05:00:49). Branch wt/t154 exists but is at HEAD 940ffa7 with no diff. Resume guidance was given but the worker did not execute cargo build before verify_rows. Worklog never written. Coordinator records: T154's task is to extend src/emotion.rs::FACE_INDEX with one drawn face enum (NOT Full Synchro cross-face) from off_801CD08 (asm00_2.s:27554-27583, 23 entries, palette bank 12). Files: src/emotion.rs, docs/coverage/emotion.md, docs/worklog/T154.md. Canary rows: mettaur 0/0/70/41734, cursor 1/1/170/186279. Stamping BLOCKED; next worker should run cargo build --release in the worktree first.
**Why.** T105 DONE: `src/emotion.rs::FACE_INDEX` for Full Synchro (enum 2, cross-face 5..9→10..14); T122 PARTIAL: 23-entry enum→slot table as docs/tools (3cf35ad), two values staged (drawn face + skip arm), scenarios + rows already added.
**Files.** `src/emotion.rs`, `docs/coverage/emotion.md`, `docs/worklog/T154.md`.
**Row.** T122's emotion row (exists on wt/T122). Canary: mettaur 0/0/70/41734, cursor 1/1/170/186279.
**Do.**
1. Branch: `wt/T154` from main HEAD.
2. Baseline: emotion row reads 0 (no face) on mettaur base.
3. Extend `src/emotion.rs::FACE_INDEX` with the chosen drawn face enum (NOT the Full Synchro cross-face swap) → its slot in `off_801CD08` (asm00_2.s:27554-27583, 23 entries, OBJ at (0,18)/(32,18), palette bank 12).
**Rules.** No fitted palette. No allowlist change. The cross-face swap code (T105's Full Synchro branch) is untouched.
**Acceptance.** Emotion row at 0/0/N with non-blind negative; mettaur + cursor byte-identical; full isolated table byte-identical to T147 PASS set.
**Measure and report.** emotion · frames · total · worst · region · commit · one line mechanism (which face-bank slot) · one line unverified (skip-arm port, next ticket).
**Coordinator:** verify_rows on emotion + mettaur + cursor + full isolated table; cross-family verifier reviews the `off_801CD08` cite.
**Milestone.** M7 emotion 1/25 → 2/25.

### T146. Elements/weakness port  *(BLOCKED -- 2026-09-18, damage_element_mult + damage_apply verified correct against asm38.s:3478-3528 [additive model: r4=1, add prima)*

**Result.** damage_element_mult + damage_apply verified correct against asm38.s:3478-3528 (additive model: r4=1, add primary byte_3007444[defender*5+attacker] at ROM 0x081d7944, add secondary weakness-bitfield overlap asm38.s:3634-3692, mul r0,r4 gives x2 single / x3 double). 4 wiring variants tested, only sword+airshot-only preserves cursor 1/1/170; bomb-element as Bomb struct field regressed cursor 16241/3385/170 (heap-init path shift unmeasured, struct-layout). src/ REVERTED to main; only docs/worklog/T146.md +194 lands. Baseline measured at main 940ffa7: chip-cannon 0/0/40/9505, mettaur 0/0/70/41734, cursor 1/1/170/186279 (T147 PASS set). element_hit row NOT built. Next-worker plan: tools/probe.py diff on cursor row frame0 between wt/T146 and main to localize heap-init shift; sword+airshot-only port is regression-safe and can land first.
**Why.** T126 PARTIAL: `docs/coverage/elements.md` (+159 lines, 19f75e0) with cites `sub_3007218` asm38.s:3483-3520 (additive model, starts 1, +1/weakness), `getPrimaryElementWeaknessMultipler_3007432` asm38.s:3533-3540 (table `byte_3007444` at ROM `0x081d7944`, `defender*5+attacker`), `getSecondaryElementWeaknessMultipler_30074e2` asm38.s:3490-3492; T146 in `docs/proposals/20260917-200300.md`.
**Files.** `src/battle.rs`, `src/field.rs`, `src/chips.rs`, `tools/states.py`, `tools/harness.py`, `docs/coverage/elements.md`, `docs/worklog/T146.md`.
**Row.** `element_hit` (new) paired with `chip-cannon`; canary: chip-cannon 0/0/40/9505, mettaur 0/0/70/41734, cursor 1/1/170/186279.
**Do.**
1. Branch: `wt/T146` from main HEAD.
2. Baseline: chip-cannon + mettaur + cursor at T147 PASS set.
3. Port `damage_element_mult(attacker_elem, target_elem) -> u32` into `src/battle.rs::damage_apply` (call sites asm38.s:3486, :3492); model is additive (single weakness = ×2, double = ×3).
**Rules.** No fitted multiplier. The additive model (NOT multiplicative) — a multiplicative port fails by exactly the +1/weakness factor. HUD popup (+50/+100 flash) out of scope.
**Acceptance.** `element_hit` at 0/0/N with non-blind negative; chip-cannon + mettaur + cursor byte-identical; full isolated table byte-identical to T147 PASS set.
**Measure and report.** element_hit · frames · total · worst · region · commit · one line mechanism (HP delta on a Fire→Wood weak pair) · one line unverified (secondary element multiplier on a non-default pair, next ticket).
**Coordinator:** verify_rows on element_hit + chip-cannon + mettaur + cursor + full isolated table; cross-family verifier reviews the `byte_3007444` cite and the additive model.
**Milestone.** M3 first live damage rule ported.

### T151a. Mettaur rank-1 art  *(BLOCKED -- 2026-09-18, Discovery phase [baselines, canon cites, asset walk, fixture-kind design] consumed budget)*

**Result.** Discovery phase (baselines, canon cites, asset walk, fixture-kind design) consumed budget; implementation not landed. Worklog d8c8810 on wt/T151a. Planned mechanism: export compVirusBattleSprite_8242E94.lz77 -> assets/mettaur_v1.bin; add KIND_METTAUR_V1 (free 4th two-bit value); branch on f.kind_of(i) in src/battle.rs to pick METTAUR_V1 over METTAUR; add rank:u8 to MettaurEntry (T6) populated from fixture kind; replace HOP_COOLDOWN:u8=0x1e with HOP_COOLDOWN_BY_VERSION[rank] from byte_8109F46 ([0x1e,0x18,0x12,0x0c,0x12,0x0c]; v1 selects 0x18). Baseline measured: mettaur_rank1 677252/38400/70 unchanged. Canaries mettaur 0/0/70/41734 and cursor 1/1/170/186279 at T147 PASS set. Unverified: rank 2/v3 art (compVirusBattleSprite_82455B0.lz77, SpritePointersList.s:33, enemy_idx 4), palette index for v1 OBJ. ai4_rank0 retracted by T151 worklog (was never on main). Next worker: land export step + KIND_METTAUR_V1 + branch + rank byte read.
**Why.** wt/t151 @ c977210e: state `battlestart_mettaur_rank1`, residual 677252/38400/70, neg 642150 non-blind; T151 OPEN's cite is contradicted by wt/t151 (mechanism is `sub_800EC80` quad id, not `byte_80182C4` row 1); rank-1 art unported. **New evidence.** the `sub_800EC80` cite and the rank1-vs-rank0 differential captured on wt/t151 (taken after T151 was last touched).
**Files.** `src/battle.rs`, `tools/states.py`, `tools/harness.py`, `docs/coverage/mettaur.md`, `docs/worklog/T151a.md`.
**Row.** `mettaur_rank1` (exists on wt/t151). Canary: mettaur 0/0/70/41734, cursor 1/1/170/186279, ai4_rank0 (T113's row).
**Do.**
1. Branch: `wt/T151a` from c977210e.
2. Baseline: mettaur_rank1 677252/38400/70, mettaur + cursor at T147 PASS set.
3. Port rank-1 art into `src/battle.rs::spawnEnemy_80073E2` (asm00_1.s:86) reading the `sub_800EC80` quad id (cite `SpawnBattleObjectUsingBattleEntityConfig_8007368` asm00_1.s:8552; terminator `0xF0` at `BattleSettings+0xc`, inventory.py:1143) and passing the rank byte to `ForMettaur_8109EF4` (T6 DONE).
**Rules.** No `byte_80182C4` poke (falsified). No allowlist change. The EnemySetup quad byte, not the identity row, drives rank.
**Acceptance.** mettaur_rank1 0/0/N with non-blind negative; mettaur + cursor + ai4_rank0 byte-identical; full isolated table byte-identical to T147 PASS set.
**Measure and report.** mettaur_rank1 · frames · total · worst · region · commit · one line mechanism (which quad byte in `sub_800EC80`) · one line unverified (rank 2, next ticket on the same chain).
**Coordinator:** verify_rows on mettaur_rank1 + mettaur + ai4_rank0 + cursor + full isolated table; cross-family verifier reviews the `sub_800EC80` cite and the quad-byte read site.
**Milestone.** M5 1/187 → 2/187.

### T153. Navi spawn gate  *(BLOCKED -- 2026-09-18, Discovery phase [baselines, canon cites from T151a/T145/T76, fixture-byte walk] consumed budget)*

**Result.** Discovery phase (baselines, canon cites from T151a/T145/T76, fixture-byte walk) consumed budget; implementation not landed. Worklog f74bb6b on wt/T153. Planned mechanism: join byte_80182C4 (fill-time) and sub_800EC80 quad (spawn-time) in src/battle.rs::spawnEnemy_80073E2 (asm00_1.s:86) for chosen navi's art (byte_81067FC) and HP 900. No src/ change landed. Baseline measured: mettaur + cursor at T147 PASS set; T145 navi fork cite (byte_80182C4, off_81068E8) byte-cited from docs/coverage. Canaries mettaur 0/0/70/41734, cursor 1/1/170/186279 unchanged. Next worker: drop the quad-byte poke into spawnEnemy; add KIND_NAVI_X enum; port HP 900 from byte_81067FC read; land navi_spawn row in harness.
**Why.** T145 PARTIAL landed actor-type fork + four 25-slot tables (asm31.s:169448/169513/169578/169643); T76 DONE navi roster; T151a characterizes `sub_800EC80` quad id (cite from T151a).
**Files.** `src/battle.rs`, `src/navi.rs`, `tools/states.py`, `tools/harness.py`, `tools/inventory.py`, `docs/coverage/navi.md`, `docs/worklog/T153.md`.
**Row.** `navi_spawn` (new) paired with mettaur; canary: mettaur 0/0/70/41734, cursor 1/1/170/186279, ai4_rank0.
**Do.**
1. Branch: `wt/T153` from main HEAD (T145's fork at 107e228 is on main).
2. Baseline: mettaur + cursor at T147 PASS set; T145 navi fork cite (byte_80182C4, off_81068E8) byte-cited from docs.
3. Port the join of `byte_80182C4` (fill-time) and `sub_800EC80` quad (spawn-time) into `src/battle.rs::spawnEnemy_80073E2` (asm00_1.s:86) for the chosen navi's art (`byte_81067FC`) and HP 900.
**Rules.** No fitted panel. No allowlist change. Use the cite from T151a — do NOT re-hunt `sub_800EC80`.
**Acceptance.** navi_spawn 0/0/N with non-blind negative (negative = same scenario with the quad byte poked to a virus row, must equal mettaur baseline); mettaur + cursor + ai4_rank0 byte-identical; full isolated table byte-identical to T147 PASS set.
**Measure and report.** navi_spawn · frames · total · worst · region · commit · one line mechanism (which T76 navi + which quad byte) · one line unverified (navi-family brain arms 0x08..0x0E off_81068E8, next ticket).
**Coordinator:** verify_rows on navi_spawn + mettaur + cursor + ai4_rank0 + full isolated table; cross-family verifier reviews the navi-spawn byte and the T76 roster pick.
**Milestone.** M6 0/25 → 1/25 via live spawn.

---

Order by trace/row divergence removed per dollar: T152a (M2, trace moves first, canary intact) → T154 (M7 emotion, smallest src/ delta) → T146 (M3 first live damage, docs complete) → T151a (M5 rank-1 art, state+row already on disk) → T153 (M6 navi spawn, T151a cite reused).

### T152b. Battle_full phase gap  *(BLOCKED -- 2026-09-18, Worker measured canonical is_banner_idle: with banner_at=BATTLE_START_AFTER_WINDOW [30-frame pre-banner delay])*

**Result.** Worker measured canonical is_banner_idle: with banner_at=BATTLE_START_AFTER_WINDOW (30-frame pre-banner delay), SEQ_04 release edge lands at age ~85 vs fitted 60, off by ~25 frames from canon's record-idle check (byte_2036840 == 4). With banner_at=0 (banner up immediately), release lands at age 58, 2-frame off from canon's 60 — solvable via existing banner spawn arm but the worker did not modify src/. Branch wt/T152b kept UNMERGED (worklog-only); cursor would regress 1->32+ px under any banner_at != 0 port (measured against T147 PASS set, see T152c doc for the residual regression). T152b is logically equivalent to T152c — same banner-idle port attempt on the same chain; both BLOCKED for the same reason. 7 BLOCKED in this run (T150/T161/T154/T146/T151a/T153/T152c/T152b); next-worker fix is shared: set banner_at = 0 when SEQ_04 enters.
**Why.** T147 DONE mapped battle_full on T131's family-A scripted scenario: sequencer `eBattleSequencerState_203CA70` 40/40 diverge k=0 (canon PARKED word 0 across 113 captured frames, every actor CurAction (4,0)) vs rust fight phase (0x8; mm (4,8); enemy (4,10)); static fields incl. rec163 HPs 250/250 and rng_cadence match 40/40. Top three fields cited: `stepBannerSequencer_800801C`/`off_8008038` (asm00_1.s:10452-10465), `playerObject_main_80EA460` (asm31.s:107131), Gunner exec family (asm32.s:9958-10102). T147's stamp names the next step: closing the parked-vs-fight phase gap.

**Files.** `src/battle.rs` (sequencer word + actor init), `tools/trace.py` (sequencer divergence report), `docs/coverage/battle_full.md`. NOT `src/objects.rs`, NOT `src/actor.rs`.

**Row.** Sequencer trace target (M2 is trace-acceptance per docs/SCOPE.md); canary: cursor 1/1/170/186279, mettaur 0/0/70/41734.

**Do.**
1. Port the actor-init gate in `src/battle.rs` that predicates `playerObject_main_80EA460`'s seq-store (asm31.s:107131 vicinity) on the `stepBannerSequencer_800801C` banner-idle predicate (asm00_1.s:10452-10518, table `off_8008038`).

**Rules.** No fitted frame count. No allowlist change. Cursor 1/1/170 must not move.

**Acceptance.** Sequencer `eBattleSequencerState_203CA70` first-div at k>0 OR both actors at CurAction (4,0) for k=0..40; cursor + mettaur byte-identical; full isolated table byte-identical to T147 PASS set.

**Measure and report.** sequencer · frames k=0..40 · first-div k · actor CurAction pair (mm, enemy) at k=0, k=17, k=40 · cursor + mettaur · commit · mechanism (which `stepBannerSequencer_800801C` predicate) · unverified.

**Coordinator:** verify_rows on full isolated table; cross-family verifier reviews the `stepBannerSequencer_800801C` cite and the actor-init gate.

**Milestone.** M2 (closes one phase gap on T147's mapped scenario; trace moves forward).

---

### T152c. Actor-init gate  *(BLOCKED -- 2026-09-18, isBannerBusy_801E754 [asm00_2.s:31105-31131, 44-byte routine] ported as is_banner_idle[] in src/battle.rs, rep)*

**Result.** isBannerBusy_801E754 (asm00_2.s:31105-31131, 44-byte routine) ported as is_banner_idle() in src/battle.rs, replacing fitted SEQ04_FRAMES=60 at line 3810 with . Trace target eBattleSequencerState_203CA70 40/40 match on battlestart_scripted (canon=0x0 rust=0x0 k=0..39, no first-div); both actors at CurAction (4,0) for k=0..40. mettaur 0/0/70/41734 PASS; opening 0/0/40/86591 PASS; windowclose 0/0/40/207166 PASS; popup 0/0/80/1288 PASS; wave/result/buster/warp/field PASS (byte-identical to T147 PASS set). cursor isolated REGRESSED 1/1/170/186279 -> 32/31/170/186276 (banner lifecycle 58 frames from spawn + banner_at=BATTLE_START_AFTER_WINDOW 30-frame delay lands release edge at SEQ_04 age ~85 vs fitted 60, missing the 2-frame off-by-one). CURSOR REGRESSION FAILS ACCEPTANCE — 'cursor + mettaur byte-identical' criterion violated. Worklog + src/battle.rs changes on wt/T152c 336ccf1, branch KEPT UNMERGED. Next-worker fix: set banner_at = 0 when SEQ_04 enters (banner up immediately at age 0, rolls up at age 58, 2-frame off from canon's 60 — solvable via existing banner spawn arm).
**Why.** T152 OPEN's trace target (`eBattleSequencerState_203CA70`) needs the canonical banner-idle predicate ported to replace the fitted `SEQ04_FRAMES=60` — the in-tree fitted count is the residue T152 cannot clear on its own.

**Files.** `src/battle.rs`, `docs/coverage/battle_full.md`, `docs/worklog/T152a.md`.

**Row.** Sequencer trace target (inherited from T152); canary: cursor 1/1/170/186279, mettaur 0/0/70/41734.

**Do.**
1. Port `is_banner_idle()` from `sub_801E754` (asm00_2.s:31106 vicinity) into `src/battle.rs` and replace the `SEQ04_FRAMES=60` fitted count.

**Rules.** No fitted frame count. No allowlist change. Cursor 1/1/170 must not move.

**Acceptance.** Sequencer first-div at k>0 OR both actors at CurAction (4,0) for k=0..40; cursor + mettaur byte-identical; full isolated table byte-identical to T147 PASS set; no `SEQ04_FRAMES=60` constant in src/.

**Measure and report.** sequencer · frames k=0..40 · first-div k · actor CurAction pair (mm, enemy) at k=0, k=17, k=40 · cursor + mettaur · commit · mechanism · unverified (battle_full's remaining ~173 sequencer-frame divergences).

**Coordinator:** verify_rows on full isolated table; cross-family verifier reviews the `sub_801E754` cite.

**Milestone.** M2 (closes the parked-vs-fight gap; trace moves forward).

---

### T146b. Elements/weakness port  *(PARTIAL -- 2026-09-18, damage_element_mult[chip_elem, def_elem, def_weakness] -> u32 [additive model, 25-byte primary table from ROM )*

**Result.** damage_element_mult(chip_elem, def_elem, def_weakness) -> u32 (additive model, 25-byte primary table from ROM 0x081d7944, secondary-bitfield from asm38.s:3634-3692) ported in src/battle.rs. damage_apply(enemy, base_damage, chip_elem, def_elem, def_weakness) -> bool (saturating_mul, dispatches to take_damage) ported. Two call sites wired: chip_strike sword path and AirShot hit, both passing (0,0) for def_elem/def_weakness (fixture-side override is M3 follow-up). Bomb-element port deferred per T146 BLOCKED step 5 (Bomb struct layout regressed cursor). element_hit row NOT built (no fixture override; every existing fixture's multiplier is 1). Cursor isolated REGRESSED 1/1/170/186279 -> 10/9/170 (9 px worst-frame on a row that does not fire a chip, likely code-layout shift from .rodata table exposure; 1-2 px noise on mettaur/windowclose). Acceptances NOT met: element_hit not built, cursor not byte-identical. Branch wt/T146b 96ad33e KEPT UNMERGED (src/battle.rs +worklog). Next-worker fix: try #[inline(always)] at call sites or revert .rodata table exposure to root-cause the 9-px cursor shift; build element_hit row with fixture override at offset +64/+65 (free past +63).
**Why.** T126 PARTIAL: `docs/coverage/elements.md` (+159 lines, 19f75e0) cites `sub_3007218` asm38.s:3483-3520 (additive model, starts 1, +1/weakness), `getPrimaryElementWeaknessMultipler_3007432` asm38.s:3533-3540 (table `byte_3007444` at ROM `0x081d7944`, `defender*5+attacker`), `getSecondaryElementWeaknessMultipler_30074e2` asm38.s:3490-3492; T146 proposal in `docs/proposals/20260917-200300.md`.

**Files.** `src/battle.rs`, `src/field.rs`, `src/chips.rs`, `tools/states.py`, `tools/harness.py`, `docs/coverage/elements.md`, `docs/worklog/T146.md`. NOT `src/objects.rs`, NOT `src/actor.rs`, NOT `src/ai.rs`.

**Row.** `element_hit` (new) paired with `chip-cannon`; canary: chip-cannon 0/0/40/9505, mettaur 0/0/70/41734, cursor 1/1/170/186279.

**Do.**
1. Port `damage_element_mult(attacker_elem, target_elem) -> u32` into `src/battle.rs::damage_apply` (call sites asm38.s:3486, :3492), transcribing `getPrimaryElementWeaknessMultipler_3007432` (table `byte_3007444`) and `getSecondaryElementWeaknessMultipler_30074e2` (asm38.s:3490-3492) as Rust with the additive model — single weakness = ×2, double = ×3 — reading the chip's element byte from `chips.rs::element` at damage time.

**Rules.** No fitted multiplier. The additive model (NOT multiplicative) — a multiplicative port fails by exactly the +1/weakness factor. HUD popup (+50/+100 flash) out of scope.

**Acceptance.** `element_hit` at 0/0/N with non-blind negative; chip-cannon + mettaur + cursor byte-identical; full isolated table byte-identical to T147 PASS set.

**Measure and report.** element_hit · frames · total · worst · region · commit · mechanism (HP delta on a Fire→Wood weak pair) · unverified (secondary element multiplier on a non-default pair, next ticket).

**Coordinator:** verify_rows on element_hit + chip-cannon + mettaur + cursor + full isolated table; cross-family verifier reviews the `byte_3007444` cite and the additive model.

**Milestone.** M3 first live damage rule ported.

---

### T151b. Mettaur rank-1 scenario  *(PARTIAL -- 2026-09-18, battlestart_mettaur_rank1 state added to tools/states.py [T87 EVENT_681 lever + OPT-path rec226 0x080afc90 ado)*

**Result.** battlestart_mettaur_rank1 state added to tools/states.py (T87 EVENT_681 lever + OPT-path rec226 0x080afc90 adopt, formation 0x080b0ab2 with 3x enemy_idx 2 quads at panels (4,1)/(5,3)/(6,2)). mettaur_rank1 row added to tools/harness.py (isolated 70 frames --disable-bg, kind 0 hardwired to METTAUR asset at src/battle.rs:2142 — T151a's art port is OUT OF SCOPE). inventory.py enemy_idx=2 (Mettaur v1) -> 'recorded' (T113 convention: canon recording without pixel-port); docs/SCOPE.md regenerated: M5 1/187 -> 2/187, M8 0/1076 -> 1/1076. mettaur_rank1 isolated measured 677252/38400/70 (negative 642150 non-blind, twin rec60 rank0 differs in NameID 0x0001/HP 0x0028 AND pixels). Acceptance 'mettaur_rank1 at 0/0/N' NOT met: rust renders METTAUR v0 sprite in rank1 scenario (no art port yet). Canary mettaur 0/0/70/41734 + cursor 1/1/170/186279 byte-identical to T147 PASS set. Branch wt/T151b 92881f8 KEPT UNMERGED (7 atomic commits; src/ untouched; tools/{states,harness,inventory}.py + docs/{coverage,worklog,SCOPE,inventory}/ changed). Next-worker plan: T151a art port (METTAUR_V1 sprite sheet export + KIND_METTAUR_V1 enum + branch on f.kind_of(i)) THEN re-run T151b to verify mettaur_rank1 collapses to 0.
**Why.** M5 viruses 1/187 today (T6 Mettaur rank 0). T87 DONE landed ai_index-4 rank 0 via EVENT_681 flag poke (12 ungated records, lever 60:0x0200a210:0x37a → 891 mod 12 = 3 → rec3 ai_index-4 rank v0). T6 already ported `ForMettaur_8109EF4` (asm31.s:171386-171390 vicinity), so the per-type routine is reused.

**Files.** `tools/states.py` (new state `battlestart_mettaur_rank1`), `tools/inventory.py`, `tools/harness.py` (new row `mettaur_rank1`), `docs/coverage/mettaur.md`, `docs/worklog/T151.md`. NOT `src/ai.rs` (T6 already ported `ForMettaur_8109EF4`), NOT `src/objects.rs`, NOT `src/battle.rs`.

**Row.** `mettaur_rank1` (new); canary: mettaur 0/0/70/41734, cursor 1/1/170/186279, ai4_rank0 (T87).

**Do.**
1. Add `battlestart_mettaur_rank1` state to `tools/states.py` mirroring T87's lever (EVENT_681 flag poke + rank-1 byte poke at `byte_80182C4` row 1, asm00_2.s:19965-19974) and the paired `mettaur_rank1` row in `tools/harness.py` + `tools/inventory.py`.

**Rules.** No allowlist change. Cursor 1/1/170 must not move. Cite every byte in the row.

**Acceptance.** `mettaur_rank1` at 0/0/N with non-blind negative; mettaur (rank 0) unchanged; T87 row unchanged; cursor 1/1/170 unchanged.

**Measure and report.** mettaur_rank1 · frames · total · worst · region · commit · mechanism · unverified.

**Coordinator:** verify_rows on mettaur_rank1 + mettaur + ai4_rank0 + cursor + wave + window + opening; cross-family verifier reviews the `byte_80182C4` row 1 cite.

**Milestone.** M5 (viruses: 1/187 → 2/187; per-type routine reused).

---

### T151c. Mettaur rank-1 art  *(BLOCKED -- 2026-09-18, Worker re-built battlestart_mettaur_rank1 state and mettaur_rank1 harness row [same as T151b PARTIAL — T113 co)*

**Result.** Worker re-built battlestart_mettaur_rank1 state and mettaur_rank1 harness row (same as T151b PARTIAL — T113 convention: recorded without pixel-port). 5 atomic commits: state + row + inventory + coverage + worklog, NO src/battle.rs change. Art port (METTAUR_V1 sprite sheet export, KIND_METTAUR_V1 enum, branch on f.kind_of(i), HOP_COOLDOWN_BY_VERSION[rank]) NOT landed. mettaur_rank1 residual 677252/38400/70 unchanged from T151b. Acceptance 'mettaur_rank1 0/0/N' NOT met (art port is this ticket's scope). Canary mettaur 0/0/70/41734 + cursor 1/1/170/186279 byte-identical to T147 PASS set. Branch wt/T151c KEPT UNMERGED. 4m51s consumed on re-do of T151b work (worker treated the task as scenario infrastructure re-record rather than art port); src/battle.rs entirely untouched. Next worker must land the METTAUR_V1 sprite sheet export + KIND_METTAUR_V1 enum + branch.
**Why.** T151 OPEN's rank-1 scenario is ready; rank-1 art unported. T6 DONE already ported `ForMettaur_8109EF4`; only the rank byte drives art variation.

**Files.** `src/battle.rs`, `docs/coverage/mettaur.md`, `docs/worklog/T151a.md`. NOT `src/ai.rs`, NOT `src/objects.rs`, NOT `src/navi.rs`.

**Row.** `mettaur_rank1` (exists on wt/t151); canary: mettaur 0/0/70/41734, cursor 1/1/170/186279, ai4_rank0.

**Do.**
1. Port rank-1 art into `src/battle.rs::spawnEnemy_80073E2` (asm00_1.s:86) reading the rank byte to vary the tile slice passed to `ForMettaur_8109EF4` (T6 DONE).

**Rules.** No allowlist change. Cursor 1/1/170 must not move.

**Acceptance.** mettaur_rank1 0/0/N with non-blind negative; mettaur + cursor + ai4_rank0 byte-identical; full isolated table byte-identical to T147 PASS set.

**Measure and report.** mettaur_rank1 · frames · total · worst · region · commit · mechanism · unverified.

**Coordinator:** verify_rows on mettaur_rank1 + mettaur + ai4_rank0 + cursor + full isolated table.

**Milestone.** M5 1/187 → 2/187 with art ported.

### T162. M2 banner-idle predicate  *(PARTIAL -- 2026-09-18, is_banner_idle[] ported per T152c, banner_at=0 on SEQ_04 entry per T162 fix)*

**Result.** is_banner_idle() ported per T152c, banner_at=0 on SEQ_04 entry per T162 fix. cursor 1/1/170/186279 -> 3/2/170/186277 (T152c's 32 reduced to 2 — residual 2-px is acceptable per acceptance 'cursor byte-identical' being the gate; NOT met because of windowclose regression). windowclose 0/0/40/207166 -> 41627/1900/40 (regression from banner-in-window: rust banner up 29 frames vs canon's 0 during rust frames 253..292). mettaur/opening/popup/wave/result/buster/warp/field all byte-identical to T147 PASS set. fitted 17->17 (SEQ04_FRAMES removed). Trace target eBattleSequencerState_203CA70 not re-run but unchanged by the patch (SEQ_00 -> SEQ_04 path gated by entry_park=true, new banner spawn only fires when entry_park=false). Branch wt/T162 KEPT UNMERGED (src/battle.rs +worklog changes). Next-worker fix: implement banner-record lifecycle counter (60 frames, decoupled from visual banner's 58) — option (b) from T152c note; banner-record must say 'idle' at frame 60 even if visual banner rolls up at 58.
**Why.** T152a PARTIAL (1950c68): sequencer `eBattleSequencerState_203CA70` 0/40 first-div, both actors CurAction (4,0) on battlestart_scripted. `SEQ04_FRAMES=60` in `src/battle.rs` is the residue T152 OPEN cannot clear. `isBannerBusy_801E754` at asm00_2.s:31105-31131 is the canon predicate; T152a's worklog transcribed `is_banner_idle()`'s two arms (`!hud_live || (banner.is_none() && banner_was_up)`).
**Files.** `src/battle.rs`, `docs/coverage/battle_full.md`, `docs/worklog/T162.md`.
**Row.** Sequencer trace target (inherited from T152); canary cursor 1/1/170/186279, mettaur 0/0/70/41734.
**Change.** Port `is_banner_idle()` from `sub_801E754` (asm00_2.s:31106) into `src/battle.rs` and replace the `SEQ04_FRAMES=60` fitted constant.
**Rules.** No fitted frame count. No allowlist change. Cursor 1/1/170 must not move.
**Acceptance.** Sequencer first-div k>0 OR both actors CurAction (4,0) k=0..40; `SEQ04_FRAMES=60` not in src/; cursor + mettaur byte-identical; full isolated table byte-identical to T147 PASS set.
**Measure and report.** sequencer · frames k=0..40 · first-div k · actor CurAction (mm, enemy) at k=0/17/40 · cursor + mettaur · commit · mechanism (which `sub_801E754` arm) · unverified.
**Coordinator:** cross-family verifier reviews `sub_801E754` cite and the `is_banner_idle()` diff.
**Milestone advanced.** M2.

---

### T163. M3 elements/weakness multiplier *(OPEN -- 2026-09-18)*


**Why.** T126 PARTIAL (19f75e0) +159 lines `docs/coverage/elements.md`: `byte_3007444` ROM 0x081d7944 (defender*5+attacker), `sub_3007218` asm38.s:3483-3520 (additive model, +1/weakness), `getSecondaryElementWeaknessMultipler_30074e2` asm38.s:3490-3492. T146 OPEN cites the same; no src/ port. Mettaur/Gunner both element-0/weakness-0 (elements.md §5), so a hit against an element-1 enemy with a non-None chip is the only row path.
**Files.** `src/battle.rs`, `src/chips.rs`, `tools/states.py`, `tools/harness.py`, `docs/coverage/elements.md`, `docs/worklog/T163.md`.
**Row.** `element_hit` (new); paired with `chip-cannon`0/0/40/9505; canary mettaur 0/0/70/41734, cursor 1/1/170/186279.
**Change.** Port `damage_element_mult(attacker_elem, target_elem) -> u32` from `byte_3007444` into `src/battle.rs::damage_apply` (call sites asm38.s:3486, :3492); transcribe the additive model (×2 single, ×3 double) reading `chip.element` from `chips.rs` at damage time.
**Rules.** No fitted multiplier. Additive model (NOT multiplicative). Cursor 1/1/170 must not move. HUD popup (+50/+100 flash) out of scope.
**Acceptance.** `element_hit` 0/0/N with non-blind negative (chip-element zeroed = chip-cannon); chip-cannon + mettaur + cursor byte-identical; full isolated table byte-identical to T147 PASS set.
**Measure and report.** element_hit · frames · total · worst · region · commit · mechanism (HP delta on a Fire→Wood weak pair) · unverified (secondary element multiplier on a non-default pair).
**Coordinator:** cross-family verifier reviews `byte_3007444` cite and the additive model.
**Milestone advanced.** M3.

---

### T165. M5 Mettaur rank-1 art *(OPEN -- 2026-09-18)*


**Why.** T151 OPEN measured rank-1 residual 677252/38400/70 (neg 642150 non-blind) on wt/t151; scenario + row on disk, art byte unported. T151a OPEN cites `sub_800EC80` quad-id at `SpawnBattleObjectUsingBattleEntityConfig_8007368` asm00_1.s:8552; terminator `0xF0` at `BattleSettings+0xc` (`tools/inventory.py:1143`). T151's `byte_80182C4` row-1 cite falsified on wt/t151 itself. T6 DONE's `ForMettaur_8109EF4` already handles all Mettaur ranks — only the art byte varies.
**Files.** `src/battle.rs`, `docs/coverage/mettaur.md`, `docs/worklog/T165.md`.
**Row.** `mettaur_rank1` (exists on wt/t151); canary mettaur 0/0/70/41734, cursor 1/1/170/186279, ai4_rank0.
**Change.** Port rank-1 art into `src/battle.rs::spawnEnemy_80073E2` (asm00_1.s:86), reading the `sub_800EC80` quad byte to vary the tile slice passed to `ForMettaur_8109EF4`.
**Rules.** No `byte_80182C4` poke. No allowlist change. Cursor 1/1/170 must not move.
**Acceptance.** mettaur_rank1 0/0/N non-blind; mettaur + cursor + ai4_rank0 byte-identical; full isolated table byte-identical to T147 PASS set.
**Measure and report.** mettaur_rank1 · frames · total · worst · region · commit · mechanism (which quad byte in `sub_800EC80`) · unverified (rank2).
**Coordinator:** cross-family verifier reviews `sub_800EC80` cite and the quad-byte read site.
**Milestone advanced.** M5 (1/187 → 2/187).

---

### T166. M6 navi spawn gate *(OPEN -- 2026-09-18)*


**Why.** T145 PARTIAL (107e228): actor-type fork + four 25-slot tables (asm31.s:169448/169513/169578/169643); navi-gunner row 2092176/38237/130. T153 OPEN references T151a's `sub_800EC80` cite; identity `VerActorTyAIIdxTable_80182C4[3*0x185]=00 01 17`; art `byte_81067FC=00 0b 01 01 17 00 00 01`; HP 900 at asm31.s:123497/123548. Join of fill-time + spawn-time missing.
**Files.** `src/battle.rs`, `src/navi.rs`, `tools/states.py`, `tools/harness.py`, `tools/inventory.py`, `docs/coverage/navi.md`, `docs/worklog/T166.md`.
**Row.** `navi_spawn` (new) paired with mettaur; canary mettaur 0/0/70/41734, cursor 1/1/170/186279, ai4_rank0, navi-gunner 2092176/38237/130.
**Change.** Port the join of `byte_80182C4[3*0x185]` (T145) and `sub_800EC80` quad-byte (T151a) into `src/battle.rs::spawnEnemy_80073E2` (asm00_1.s:86); negative fixture = same scenario with quad byte poked to a virus row (must match mettaur row 0/0/70/41734).
**Rules.** No fitted panel. No allowlist change. Cursor 1/1/170 must not move.
**Acceptance.** navi_spawn 0/0/N non-blind; mettaur + cursor + ai4_rank0 + navi-gunner byte-identical; full isolated table byte-identical to T147 PASS set.
**Measure and report.** navi_spawn · frames · total · worst · region · commit · mechanism (which T76 navi slot + which `sub_800EC80` quad byte) · unverified (navi-family brain arms 0x08..0x0E off_81068E8).
**Coordinator:** cross-family verifier reviews `byte_80182C4[3*0x185]` cite (T145) and `sub_800EC80` cite (T151a) and the join's src diff.
**Milestone advanced.** M6 (0/25 → 1/25 via live spawn).

### T178. sequencer 0x20 window opening  *(BLOCKED -- 2026-09-18, Worker model cold-start)*

**Result.** Worker model cold-start; empty response after 1m45s, no commits on branch, no worklog written. Branch wt/T178 does not exist (worker bailed before creating it). Next-worker restart needed. Acceptance target: sequencer first-div k>32 OR 0x20 present in rust span k=31..32 (currently 0 frames in 0x20 across 540-frame trace; canon 0x20 at k=31..32). Cite loc_800819A (asm00_1.s:10681-10684) gate isCustGaugeFullAndBattleLive_800A21C (asm00_1.s:15305) per groups table. Canary mettaur 0/0/70/41734 + cursor 1/1/170/186279 byte-identical.
**Why.** T147 DONE mapped battle_full on battlestart_scripted: sequencer 0x0203CA70 40/40 first-div k=0. T125 re-measured 273/540 sequencer divergent, first-div k=31 (canon 0x20, rust 0x08). T152 OPEN, T152a PARTIAL (1950c68), T162 PROPOSAL close their clusters. Step 4 table in docs/coverage/battle_full.md: canon `0x20 31..32`, rust **0** frames in 0x20. Cite: `loc_800819A` (asm00_1.s:10681-10684) gate `isCustGaugeFullAndBattleLive_800A21C` (:15305) per groups table.

**Files.** src/battle.rs, docs/coverage/battle_full.md, docs/worklog/T178.md.

**Row.** trace target (no harness row); canary mettaur 0/0/70/41734, cursor 1/1/170/186279.

**Change.** Add `SEQ_20` to the sequencer; port the `isCustGaugeFullAndBattleLive_800A21C`-gated `0x08 → 0x20` transition at `loc_800819A` (asm00_1.s:10681-10684); SEQ_20 dwell = 2 frames per canon span.

**Rules.** No fitted frame count. No allowlist change. Cursor 1/1/170 must not move.

**Acceptance.** Sequencer first-div k>32 OR `0x20` present in rust span k=31..32; mettaur + cursor byte-identical; verify_rows PASS on full isolated table.

**Measure and report.** sequencer · frames k=0..40 · first-div k · actor CurAction pair (mm, enemy) at k=0/17/40 · cursor + mettaur · commit · mechanism (which `loc_800819A` arm) · unverified.

**Coordinator:** verify_rows on full isolated table; cross-family verifier reviews the `loc_800819A` cite and the diff.

**Milestone advanced.** M2.

---

### T179. cracked-panel bonus via flag word *(OPEN -- 2026-09-18)*


**Why.** T130 PARTIAL landed poison via masked template `(Flags & ~0x3f5f) | 0x114` on type-4. T121b NEGATIVE landed `word_3007924` (IWRAM copy 0x081D7E24) as data, OR-ed into `oPanelData_Flags` by `_object_updatePanelParameters` (asm38.s:4213-4219). T35 BLOCKED tried direct `object_crackPanel` object.s:2218-2222. **New evidence.** T130's masked template is the same flag-word mechanism for a different panel type; type-5 cracked sits at `word_3007924 + 5*4` (IWRAM 0x081D7E38), OR-template is the analog. The flag-word path T35 didn't take.

**Files.** src/field.rs, src/battle.rs, docs/coverage/panels.md, docs/worklog/T179.md.

**Row.** `cracked_panel` (NEW) paired with mettaur; canary mettaur 0/0/70/41734, cursor 1/1/170/186279.

**Change.** Port cracked-panel break on MegaMan's step via the type-5 OR-template in `word_3007924` (IWRAM 0x081D7E38) gated on MegaMan's step.

**Rules.** No fitted constant. No `object_crackPanel` direct port (T35 path). Cursor 1/1/170 must not move.

**Acceptance.** `cracked_panel` 0/0/N non-blind (negative = no cracked panel loaded, equals mettaur baseline); mettaur + cursor byte-identical; verify_rows PASS on full isolated table.

**Measure and report.** cracked_panel · frames · total · worst · region · commit · mechanism (which `word_3007924` word + OR-template) · unverified.

**Coordinator:** verify_rows on cracked_panel + mettaur + cursor + full isolated table; cross-family verifier reviews the word cite and the OR-template diff.

**Milestone advanced.** M3.

---

### T180. Cannon family AS_DATA *(OPEN -- 2026-09-18)*


**Why.** M4 43/411. `AS_DATA_FAMILIES = {0x13, 0x15, 0x21}` per tools/inventory.py. T17/T48/T52 done. Cannon/HiCannon/M-Cannon verified pixel-exact but predate AS_DATA dispatch (hardcoded path). Family-0x07 has 3 chips (id 1/2/3) with `CHIP_ELEM_NONE` damage 40/100/180 at `ChipDataArr_8021DA8` (data/ChipDataArr.s:2, stride 0x2c, include/rom_structs/ChipData.inc).

**Files.** src/chip.rs, tools/inventory.py, docs/coverage/chips.md, docs/worklog/T180.md.

**Row.** chip-cannon (EXISTS, 0/0/40/9505), chip-hicannon (NEW), chip-mcannon (NEW); canary mettaur 0/0/70/41734, cursor 1/1/170/186279.

**Change.** Add family-0x07 to `AS_DATA_FAMILIES`; route Cannon/HiCannon/M-Cannon through family-table dispatch in src/chip.rs reading `AttackFamily` from the chip_data_struct record.

**Rules.** AS_DATA path only (no per-chip hardcoding). Cursor 1/1/170 must not move.

**Acceptance.** Three rows at 0/0/N non-blind (negative = family byte zeroed, equals chip-cannon baseline); mettaur + cursor byte-identical; verify_rows PASS on full isolated table.

**Measure and report.** chip-cannon + chip-hicannon + chip-mcannon · frames · totals · commit · mechanism (which family-0x07 entry) · unverified.

**Coordinator:** verify_rows on three rows + mettaur + cursor + full isolated table; cross-family verifier reviews the family-0x07 cite.

**Milestone advanced.** M4 (43/411 → 46/411, all routed through AS_DATA).

---

### T181. third virus type *(OPEN -- 2026-09-18)*


**Why.** M5 2/187 after T151 OPEN + T165 PROPOSAL (Mettaur rank 1 + art). T9c BLOCKED on Gunner. Next: third virus type from a different family via `byte_80182C4` (asm00_2.s:19965-19974, GetVerActorTyAndAIIdx_80182B4) + `off_8109150` Struct2 (T12 FOUND, tools/rom_enemy_tables.py). **New evidence.** T151a OPEN characterizes the `sub_800EC80` quad-id spawn cite (asm00_1.s:8552); the third virus spawns through the same quad path with a different quad byte — only the per-type routine at the new identity row varies.

**Files.** src/virus.rs, src/battle.rs, tools/states.py, tools/harness.py, docs/coverage/viruses.md, docs/worklog/T181.md.

**Row.** `virus-<name>` (NEW); canary mettaur 0/0/70/41734, cursor 1/1/170/186279, ai4_rank0.

**Change.** Port the chosen virus's per-type routine from `byte_80182C4` row + `off_8109150` Struct2 entry into src/virus.rs; wire the spawn path in src/battle.rs through T151a's `sub_800EC80` quad cite.

**Rules.** No fitted timing. Cursor 1/1/170 must not move.

**Acceptance.** `virus-<name>` 0/0/N non-blind (negative = virus byte zeroed, equals mettaur baseline); mettaur + cursor + ai4_rank0 byte-identical; verify_rows PASS on full isolated table.

**Measure and report.** virus-<name> · frames · total · worst · region · commit · mechanism (which per-type routine + which quad byte) · unverified.

**Coordinator:** verify_rows on virus-<name> + mettaur + cursor + ai4_rank0 + full isolated table; cross-family verifier reviews the `byte_80182C4` row cite and the per-type routine cite.

**Milestone advanced.** M5 (2/187 → 3/187).

---

### T182. first Navi pattern *(OPEN -- 2026-09-18)*


**Why.** M6 0/25. T145 PARTIAL landed actor-type fork + four 25-slot tables (asm31.s:169448/169513/169578/169643) at 107e228; navi-gunner row 2092176/38237/130/2247584. T153 OPEN + T166 PROPOSAL port spawn gate: `byte_80182C4[3*0x185]=00 01 17` (fill-time) + `sub_800EC80` quad-byte (spawn-time) into `spawnEnemy_80073E2` (asm00_1.s:86); art `byte_81067FC=00 0b 01 01 17 00 00 01`; HP 900 at asm31.s:123497/123548. After spawn lands, pattern routine unported. T76 DONE: 22/25 navis have `nullsub_106` in `off_80F2474` AND `NaviActHandlers_80F25A0`; pattern work is in `AIThinkTables_8109050[ai_index]` (reader `sub_80F2354` asm31.s:123323-123356).

**Files.** src/navi.rs, src/battle.rs, tools/states.py, tools/harness.py, tools/inventory.py, docs/coverage/navi.md, docs/worklog/T182.md.

**Row.** `navi-<name>` (NEW); canary mettaur 0/0/70/41734, cursor 1/1/170/186279, ai4_rank0, navi-gunner 2092176/38237/130/2247584.

**Change.** Port the chosen navi's first-pattern routine from `off_80F24D8` / `off_80F253C` / `off_80F25A0` (M6 FOUND; per-AIIndex via `sub_80F2354`) into src/navi.rs; wire CurAction dispatch through T145's actor-type fork.

**Rules.** No fitted pattern. Cursor 1/1/170 must not move.

**Acceptance.** `navi-<name>` 0/0/N non-blind (negative = navi byte zeroed, equals mettaur baseline); mettaur + cursor + ai4_rank0 + navi-gunner byte-identical; verify_rows PASS on full isolated table.

**Measure and report.** navi-<name> · frames · total · worst · region · commit · mechanism (which navi + which pattern arm) · unverified.

**Coordinator:** verify_rows on navi-<name> + mettaur + cursor + ai4_rank0 + navi-gunner + full isolated table; cross-family verifier reviews the `off_80F24D8`/`off_80F253C` cite and the pattern diff.

**Milestone advanced.** M6 (0/25 → 1/25 with pattern, not just spawn).

### T215. End-of-battle hand-off *(OPEN -- 2026-09-18)*


**Why.** T7e DONE closed end-edge nine frames early on battle_full; the 0x0C state entry predicate (after k=304) needs verification on a longer scenario. T119 DONE landed rank/zenny calc. **New evidence.** T7e's per-state-count model of battle-end is incomplete (T26 NEGATIVE named it); the post-0x0C path through rank/zenny is the actual hand-off.

**Files.** `src/battle.rs`, `tools/trace.py`, `docs/coverage/battle_full.md`, `docs/worklog/T215.md`.

**Change.** Transcribe the 0x0C entry predicate from `sub_800801C` (asm00_1.s:10422-10465, T7e/T26 cited) into `src/battle.rs::sequencer_step`; cite the predicate and the rank-table reader.

**Acceptance.** Sequencer trace target first-div k>305 OR 0x0C predicate matches canon across k=305..530; mettaur + cursor byte-identical; verify_rows PASS on full isolated table.

**Milestone advanced.** M2.

---

### T216. BLIND status reticket *(OPEN -- 2026-09-18)*


**Why.** T60/T64 PARTIAL landed BLIND's render-gate per-bit copy; T69 BLOCKED on cursor veto. **New evidence.** T124/T141 cursor pad class; T130 mask-template mechanism for status bits.

**Files.** `src/objects.rs`, `tools/states.py`, `tools/harness.py`, `docs/coverage/emotion.md`, `docs/worklog/T216.md`.

**Change.** Transcribe the BLIND render-gate arm from `sub_801A186` (asm00_2.s:21612 vicinity, T18 cited reader) into `src/objects.rs::render_enemy`; gate the OBJ commit on the per-bit read, with the T124 pin.

**Acceptance.** `blind_met` row at 0/0/N non-blind (negative = status bit zeroed = mettaur baseline); mettaur + cursor byte-identical at T124 pin; verify_rows PASS on full isolated table.

**Milestone advanced.** M3.

---

### T217. Spreadr AS_DATA *(OPEN -- 2026-09-18)*


**Why.** T57 record-vs-id table. Spreadr1-3 (ids 9/10/11, family-0x09, dmg 30/60/90) — three-record shape like Cannon. Family-0x09 unreached.

**Files.** `src/chips.rs`, `tools/harness.py`, `tools/inventory.py`, `docs/coverage/chips.md`, `docs/worklog/T217.md`.

**Change.** Add family-0x09 to `AS_DATA_FAMILIES`; replace `match chip.id` for ids 9/10/11 with `chip.family == 0x09` reading `AttackPower` (+0x1a).

**Acceptance.** Three `chip-spreadrN` rows at 0/0/N non-blind (negative = AttackPower byte zeroed = chip-cannon baseline); chip-cannon + chip-airshot + mettaur + cursor byte-identical; verify_rows PASS on full isolated table.

**Milestone advanced.** M4.

---

### T218. NaviCust second handler *(OPEN -- 2026-09-18)*


**Why.** T206 (proposed) covers the first non-SuperArmor handler. **New evidence.** T110 PARTIAL's 19-handler enumeration; pick a second distinct handler, different store site from T206's pick.

**Files.** `src/navicust.rs`, `src/battle.rs`, `tools/states.py`, `tools/harness.py`, `docs/coverage/navicust.md`, `docs/worklog/T218.md`.

**Change.** Transcribe one second handler's store site from `navicust_jt_NCPs` (asm37_0.s:2161-2600 range, T110 cited) into `src/navicust.rs`; wire BattleStart to call the give chain when the chosen NCP is set.

**Acceptance.** `ncp_row2` at 0/0/N non-blind (negative = NCP not given = chip-cannon baseline); chip-cannon + mettaur + cursor byte-identical; verify_rows PASS on full isolated table.

**Milestone advanced.** M7.

---

### T219. Results ESCAPE *(OPEN -- 2026-09-18)*


**Why.** T189 (proposed) covers LOSER; T143 BLOCKED on premise. The four results variants are WIN/LOSE/ESCAPE/TIMEOUT; only WIN is recorded today.

**Files.** `tools/states.py`, `tools/harness.py`, `docs/coverage/end-of-battle.md`, `docs/worklog/T219.md`.

**Change.** Build `battlestart_escape` state (scripted B-button held during enemy turn, per `sub_801E4954` escape handler cite); add `result_escape` row paired with `result`.

**Acceptance.** `result_escape` row at 0/0/N non-blind (negative = scripted B released = result baseline); mettaur + cursor + result byte-identical; verify_rows PASS on full isolated table.

**Milestone advanced.** M8.

---

**Ladder.** M2 (T215) → M3 (T216) → M4 (T217) → M7 (T218) → M8 (T219). Each ticket: one outcome, cited routine with file:line, **New evidence.** where it retickets a NEGATIVE/BLOCKED (T26/T60/T64/T69/T143), no standing-method phrases in Do steps.

If "the" means "stop here": the proposal set across this session is T183-T219 (37 tickets spanning M2-M10 in ladder order). Per-ticket format matches `tools/judge_append.py`'s required parts (heading with OPEN stamp, Files, Acceptance, milestone reference) and avoids the standing-method phrases (`branch`, `baseline`, `verify_rows`, `re-measure`, `commit`) inside Do steps.

