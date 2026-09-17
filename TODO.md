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
### T62. M4/M1 bookkeeping: SCOPE's M4 prose line still quotes the count T57 superseded, and T57's own comment understates family 0x13's id keying  *(DONE -- 2026-09-16, Acceptance met in full on branch wt/t62 [ae9c509 step 2, e1c6dbb step 3, 66f4eb0 step 4, tip 66f4eb0, tree cle)*

**Result.** Acceptance met in full on branch wt/t62 (ae9c509 step 2, e1c6dbb step 3, 66f4eb0 step 4, tip 66f4eb0, tree clean) -- UNMERGED only because land.sh refuses while main's checkout carries the human's own uncommitted edits (docs/tickets/Q3.md, tools/ghidra_decompile.sh, tools/ghidra/BnPrepare.java, a live Ghidra session I must not touch). MY OWN free-tier checks, not the worker's: `git diff --name-only main wt/t62` = exactly the four named files (docs/SCOPE.md, docs/worklog/T57.md, docs/worklog/T62.md, tools/inventory.py); `git diff --name-only $(git merge-base main wt/t62) wt/t62 -- src assets Cargo.toml Cargo.lock build.rs *.ld` is EMPTY, so the ROM is main's by construction and the worker additionally measured 5b46337aa27da9ca881f2321fe1e210f54717285b4dfa5256c1680bac4b985ef equal before and after through the gbafix path; `git diff --numstat main wt/t62 -- docs/SCOPE.md` = 1 insertion / 1 deletion (the prose line only, no generated line moved); and re-running `python3 tools/inventory.py` inside the worktree leaves the tree CLEAN, i.e. the generator agrees with what is committed. CITES RE-CHECKED BY ME ON MAIN: src/battle.rs:3288 is `let (asset, palette) = match self.chip_in_use.map(|c| c.id) {` with the four sword arms through :3292, :4144 is the CHIP_SWORD|CHIP_WIDESWRD|... entry arm, :4391 is `if chip.family == SWORD_FAMILY {`, and tools/inventory.py:1184 is the `ver = sum(...)` status counter -- so the three corrected slips and both family-0x13 id keys are real lines, not remembered ones. WHAT CHANGED: docs/SCOPE.md:21 (human prose above the GENERATED marker) now reads the counts the tool prints at that moment -- 11 as-data / 32 verified-pixels / 411 rows, AS_DATA_FAMILIES={0x13,0x21} -- replacing the stale 14 and the stale {0x13,0x15,0x21}, with the reason 0x15 was demoted stated from src/battle.rs:3430/:3434; the inventory.py block comment now names BOTH id keys inside family 0x13 (the :4144 entry arm and the :3288-3294 sprite/palette match) and why the family still qualifies (entry arm common to all swords, sprite/palette cosmetic-per-id, behaviour record-dispatched at :4391) -- the literal itself untouched, as the ticket froze it; T57's three cite slips corrected in place with dated notes. No verifier dispatched: the ticket's own coordinator rule waives it unless step 3 changes a family's qualification, and step 3 confirmed 0x13 stays in rather than moving any number. UNVERIFIED, carried forward: the "cosmetic-per-id" reading of :3288-3294 is an arm-level code read, not a pixel A/B -- T61's owner should keep that in mind -- and this prose will need re-syncing the day wt/t61b lands, because that branch re-adds 0x15 and moves the count 11 -> 16.
**Why.** T57 (DONE, landed 954ed81) shrank `tools/inventory.py:228` to `AS_DATA_FAMILIES = {0x13, 0x21}`, and its verifier-hyper run (35 tool calls, all 411 rows re-parsed) confirmed the generated side now reads **11 `verified` / 32 `verified-pixels` / 368 `unrecorded`** -- but `docs/SCOPE.md:21` is human prose ABOVE the `GENERATED` marker at :36, so `inventory.py` never rewrites it and it still says "**14** chips pixel-verified AS DATA ... (tools/inventory.py AS_DATA_FAMILIES={0x13,0x15,0x21})". Every M4 ticket quotes that line, so main currently carries two different answers to "how many chips are data". The same verifier REFUTED one clause of the new comment at tools/inventory.py:210-215 ("the one byte this family still keys by id is the use_chip ENTRY arm src/battle.rs:4144"): `src/battle.rs:3288-3294` picks the sword's SPRITE and PALETTE by `match self.chip_in_use.map(|c| c.id)` with four `CHIP_FIRESWRD|CHIP_AQUASWRD|CHIP_ELECSWRD|CHIP_BAMBSWRD` arms -- a second, behaviour-visible id key inside family 0x13, exactly the kind of asymmetry that dropped 0x15. Three cite slips in the same artifacts need the same pass (:4266 is `spr::Player::new`, the `chip.id - CHIP_CANNON` byte is :4269; `ener:` is :4578 not :4596-4604; the status counter is tools/inventory.py:1184 not :1165). Milestone **M4** (and M1's chips line): this ticket changes no number, only the text that quotes them.

**New evidence.** verifier-hyper on wt/t57 ca569b1 (independent rebuild: ROM `5b46337aa27da9ca881f2321fe1e210f54717285b4dfa5256c1680bac4b985ef`, byte-identical to HEAD; `git diff --quiet 86a5b18 -- src/` clean; the 11/32/368 split recomputed from the rule, not read from the file). Its two named leftovers are this ticket. T56 (NEGATIVE, stamped) is why the ROM sha must be quoted here: a −900 B tree moved `cursor` by 5 px at k=97, so any accidental src touch is visible.

**Note for the worker (added 2026-09-17, after this ticket was written).** T61's re-run branch `wt/t61b` re-adds `0x15` and takes the generated count from 11 to 16, but it is KEPT UNMERGED right now because `cursor` reads 20/19 there (the ticket's own veto), so main's generated numbers have not moved. Re-read `python3 tools/inventory.py` at the moment you work and write the prose from what it prints then, not from either number quoted above.

**Files.** docs/SCOPE.md (**only** the human prose at :21, never the generated part), tools/inventory.py
 (**only** the `AS_DATA_FAMILIES` block comment at :200-227 -- the set literal itself must not change), docs/worklog/T57.md (its cite slips, corrected in place with a dated note), docs/worklog/T62.md. **NOT** src/ (zero changes), tools/inventory.py's `AS_DATA_FAMILIES` literal, tools/harness.py, tools/verify_rows.py, tools/states.py, tools/allowlist.py, assets/, reference/ (read-only).

**Do.** 1. Baseline, no edit: `python3 tools/inventory.py` then read the generated chips line (SCOPE.md:40 `| 43 / 411 |`) and the `verified` / `verified-pixels` / `unrecorded` counts from docs/inventory/chips.json; `sha256sum` the built ROM; quote `docs/SCOPE.md:21` verbatim. **measurement.** 2. Rewrite `docs/SCOPE.md:21` so its as-data number and its `AS_DATA_FAMILIES={...}` list are **read from step 1's generated output**, never hard-coded from memory, and state the reason the family rule does not cover the rest in one clause with the src cite that shows it; leave the milestone text and every other prose line byte-identical. **docs change.** 3. Fix the inventory comment: name BOTH id keys inside family 0x13 (:4144's entry arm and :3288-3294's sprite/palette `match`) and say explicitly why the family still qualifies (the entry arm is common to all swords and the sprite/palette key is cosmetic-per-id, so the *behaviour* is record-dispatched) -- or, if step 2 of that argument fails on the code, say the family does not qualify and name it as T61's blocker; do NOT edit the literal either way. **tools change (comment only).** 4. Correct the three cite slips in docs/worklog/T57.md and tools/inventory.py against disk, each with a dated `corrected by T62` note rather than a silent edit. **docs change.** 5. Rebuild: ROM sha256 must equal step 1's byte-for-byte, `git diff --name-only` must list only the four named files, and `python3 tools/inventory.py` must leave the generated part of SCOPE.md unchanged (`git diff --stat docs/SCOPE.md` = the prose line only). **measurement.**

**Rules.** The `AS_DATA_FAMILIES` literal is frozen: adding 0x15 back is **T61's** job (it owns src/battle.rs), not this one's; if this ticket's step-3 argument says 0x13 no longer qualifies, the fix is a named blocker, not an edit. Zero src/ changes -- quote both ROM sha256s (T56's rule). No row, fixture, allowlist, state or scope-order change; SCOPE's milestone list and §3 order are untouched. Every cite re-checked against disk before it is written. ≤1 capture, tool budget ≤30.

**Acceptance.** `docs/SCOPE.md:21` agrees with the generated table it sits above (the same as-data count, the same family set, with the reading of that number shown); the family-0x13 comment names both id keys or names the family's disqualification; the three cite slips are corrected with dated notes; ROM sha256 identical before/after; `git diff --name-only` = the four named files. A NEGATIVE closing it = the prose and generated parts cannot be made to agree without editing the literal (i.e. T61 must land first) -- report that, change nothing.

**Measure and report.** rows: none (no ROM change). The ROM sha256 (before = after), the generated 11/32/368-or-current split, SCOPE.md:21 before/after verbatim, the two family-0x13 id-key sites as read from disk, the corrected cites with their disk line numbers, `git diff --stat`; commit; one line of mechanism; one line of what is unverified.

**Coordinator:** dispatch when `tools/inventory.py` and `docs/SCOPE.md` are free -- it textually overlaps T61 (which owns that literal and src/battle.rs) and must not run beside it. Free tier: no row moves (ROM byte-identical is the gate); run `python3 tools/inventory.py` yourself and diff the generated part. No verifier unless the step-3 argument changes a family's qualification, in which case the claims are the two src cites. ≤$0.10 expected, ≤$0.20 cap. Keeps **M4**/M1 quoting honest.

---

### T63. M2: MegaMan's chip-use action — the k=250 mm_state_action/mm_anim/mm_timer group, found with --watch-write on the player object  *(NEGATIVE -- 2026-09-16, Closed by the ticket's own negative clause)*

**Result.** Closed by the ticket's own negative clause; no src/ touched (branch wt/t63: 56679e5 worklog, b8ae780 negative close + one cite fix; docs only, so no row could move -- the verifier confirmed the diff names only docs/worklog/T63.md and docs/coverage/battle_full.md). Pass-1 wording in full is in the previous version of this paragraph (git log -p TODO.md); in outline: the baseline reproduced the ticket exactly (mm_state_action 76/540 first k=250, mm_anim 78/540 first k=251, mm_timer 270/540 first k=269, 13-field total 1370) with the 7-row guard set identical and cursor at its known 1/1/170/186279, and the 67-store table (canon --watch-write on 0x0203a9b8:2 / 0x0203a9c0:1 / 0x0203a9d0:2, first store at capture frame 261 = k=250) is in docs/worklog/T63.md. VERDICT: verifier-hyper 87d802ec (qwen3.8-flash) CONFIRMS the blocker by a stronger route than the report used. Our side fires at k=352 because that is AUTO-FIRE (fight-open about k=172 plus fire_frame 180 at tools/states.py:635, re-seeded by src/battle.rs:3178, flags 0x19 bit3 = src/fixture.rs:71) while the rust scenario script is only A@170 (tools/states.py:643), which just closes the window; canon's script is A@260 (tools/states.py:603) -- press 260, store 261, k=250. Our navi is NEVER hit (hp set {60}, mercy {120}, timer {0} over k=0..539), and swapping 0x0b to 0x14 at k=352 fixes nothing because canon reads 0x08 at k=352..384. So porting the 0x14 arm cannot move k=250, cannot drop mm_timer below 270, cannot move 1370. Also CONFIRMED: the ticket's canon=(4,0x20) was a hex misread of the oracle's DECIMAL print (tools/oracle.py:536; the byte is 0x14); the chain useChipFromHand_800FB54 (asm00_2.s:2006) -> bl at 0x0800FBF2 -> the SHARED tail strb r0,[r5,#oBattleObject_CurAction] at asm00_2.s:5611 = PC 0x0801169A; CurAnim=8 one frame later at PC 0x0800F2BE and NOTHING to Timer (first A9D0 store is frame 280); and k=269 is the Mettaur's wave hitting MegaMan (hp 60->50, mercy 0->119, action 3, anim 1, timer 22 on one frame) into playerFlinchAction_80174FE (asm00_2.s:18300-18378 exactly). THREE CITE CORRECTIONS to fold in before any of these lines is pasted into a code comment: the bl object_setAttack0 is asm00_2.s:23656 (not 23653); the flinch jump-table entry is asm31.s:107216 (not 107195); that guard tests mask 0x2, not bit 4. Two names stay UNCHECKED on checked PCs: 0x0800F2BE as object_setAnimation, and which of the three bl object_setAttack2 lines (2067/2088/2152) sits at 0x0800FBF2. Dropped from the record: the report's +3-dropped-frames aside is an indexing artifact (k = capture frame - 11, canon_ref 11 in tr_c/meta.json), not a capture defect. NEW DEFECT the verifier measured and the report missed: canon holds Timer at 0xFFFF for 248 frames (k=292..539, a genuine hold -- no A9D0 store after frame 303) while src/actor.rs:429 carries const POST_FLINCH_FRAMES: u8 = 11 marked provenance: fitted and :727-735 exports a 9..0-then-0 shadow. Fixing it is free and independent of the alignment gap, but the shadow is SHARED by rows that pass today, so the follow-up (T66, written from this verdict) must re-check wave/window/opening/chip-cannon/mettaur/windowclose. The fire-alignment gap itself needs a user ruling -- the row rules forbid retuning fire_frame -- so it is deliberately NOT ticketed.
**Result.** Closed by the ticket's own negative clause; no src/ touched (branch wt/t63: 56679e5 worklog, b8ae780 negative close + a cite fix; docs only, so no row could move -- verifier confirmed docs/coverage/battle_full.md
docs/worklog/T63.md names only docs/worklog/T63.md and docs/coverage/battle_full.md). Full pass-1 wording is in the previous version of this paragraph (git log -p TODO.md), kept here in outline: baseline reproduced the ticket exactly (mm_state_action 76/540 first k=250, mm_anim 78/540 first k=251, mm_timer 270/540 first k=269, 13-field total 1370) with the 7-row guard set identical and cursor at its known 1/1/170/186279; the 67-store table (canon --watch-write on 0x0203a9b8:2/0x0203a9c0:1/0x0203a9d0:2, first store at capture frame 261 = k=250) is in docs/worklog/T63.md. VERDICT -- verifier-hyper (87d802ec, qwen3.8-flash) CONFIRMS the blocker by a stronger route than the report used: our side fires at k=352 because that is AUTO-FIRE (fight-open ~k=172 + fire_frame 180, tools/states.py:635, re-seeded by src/battle.rs:3178, flags 0x19 bit3 = src/fixture.rs:71) and the rust scenario script is only  (tools/states.py:643) which just closes the window, while canon's script is  (tools/states.py:603) -- press 260, store 261, k=250; our navi is NEVER hit (hp set {60}, mercy {120}, timer {0} over k=0..539), and a 0x0b->0x14 swap at k=352 fixes nothing because canon reads 0x08 at k=352..384. So porting the 0x14 arm cannot move k=250, cannot drop mm_timer below 270, cannot move 1370. CONFIRMED too: the ticket's  was a hex misread of the oracle's DECIMAL print (tools/oracle.py:536; the byte is 0x14), the chain useChipFromHand_800FB54 (asm00_2.s:2006) -> bl at 0x0800FBF2 -> the SHARED tail  at asm00_2.s:5611 = PC 0x0801169A (writing CurAnim=8 one frame later at PC 0x0800F2BE and NOTHING to Timer -- first A9D0 store is frame 280), and that the k=269 change is the Mettaur's wave hitting MegaMan (hp 60->50, mercy 0->119, action 3, anim 1, timer 22 on the same frame) into playerFlinchAction_80174FE (asm00_2.s:18300-18378 exactly). THREE CITE CORRECTIONS that must be folded in before any of these lines is pasted into a code comment:  is asm00_2.s:23656 (not 23653); the flinch jump-table entry is asm31.s:107216 (not 107195); the flag2 guard there tests mask 0x2, not 'bit 4'. Two names stay UNCHECKED on checked PCs: 0x0800F2BE as , and which of the three  lines (2067/2088/2152) is at 0x0800FBF2. Also dropped from the record: the report's '+3 dropped frames' aside is an indexing convention artifact (k = capture frame - 11, canon_ref 11 in tr_c/meta.json), not a capture defect. NEW DEFECT the verifier measured and the report missed: canon holds Timer 0xFFFF for 248 frames (k=292..539, a genuine hold -- no A9D0 store after frame 303), while src/actor.rs:429 carries  and :727-735 exports the shadow 9..0 then 0 -- written it is free and independent of the alignment gap, but it is SHARED by rows that pass today, so the follow-up must re-check wave/window/opening/chip-cannon/mettaur/windowclose; that ticket is T66. The fire-alignment gap itself needs a user ruling (the row rules forbid retuning fire_frame), so it is NOT ticketed.
**Result.** Ticket closed by its own negative clause: the k=250 group is blocked upstream of the player action model, so no src/ was touched (branch wt/t63, commits 56679e5 worklog + b8ae780 the negative close and a cite fix, docs only). Step 1 baseline reproduced the ticket exactly (tools/oracle.py battle_full --both: mm_state_action first k=250 canon=(4,20) rust=(4,8) 76/540; mm_anim k=251 canon=8 rust=0 78/540; mm_timer k=269 canon=22 rust=0 270/540; 13-field total 1370) with the guard set identical (wave 0/0/90/3840, window 0/0/16/81056, opening 0/0/40/86591, chip-cannon 0/0/40/9505, mettaur 0/0/70/41734, cursor 1/1/170/186279, windowclose 0/0/40/207166), canon ROM a37c1028... 8,388,608 B. Step 2's store table (67 stores, NONE before frame 261... note k numbering: the first action store is at k=250 in the oracle's frame index) is in docs/worklog/T63.md: k=250 0x0203a9b9 0x08->0x14 PC 0x0801169A lr 0x0800FBF7; k=251 0x0203a9c0 0->8 PC 0x0800F2BE; k=269 0x0203a9b9 0x14->0x03 PC 0x0801169A lr 0x0801B11F, 0x0203a9c0 8->1 PC 0x08017556, 0x0203a9d0 0->0x17->0x16 PC 0x0801757C/86; k=270..291 0x0203a9d0 -1/frame PC 0x08017586 lr 0x0801BA10; k=292 0x0203a9d0 ->0xFFFF, 0x0203a9c0 1->0, 0x0203a9b9 0x03->0x08; k>=293 idle-anim refresh PC 0x080EA79C (playerAI_update_80EA734). THREE PREMISE CORRECTIONS, all from disk: (1) the ticket's 'canon=(4,0x20)' is a hex misread of the oracle's DECIMAL print -- canon's k=250 CurAction is 0x14 (=20 decimal), written by useChipFromHand_800FB54 (reference/bn6f/asm/asm00_2.s:2006) through bl object_setAttack2 at 0x0800FBF2 into the shared tail strb at 0x0801169A (asm00_2.s:5611), which writes CurAnim=8 one frame later and NOTHING to Timer; (2) the k=269 change is not the chip action ending -- it is the Mettaur's wave hitting MegaMan (HP 60->50, mercy 119), so ai_eventuallyRunsAIAttack_801AF44 (bl object_setAttack0 at 0x0801B11A, asm00_2.s:23653) writes the flinch action 0x03 whose handler playerFlinchAction_80174FE (asm00_2.s:18300) runs the anim-1/Timer-0x17 countdown; (3) docs/coverage/battle_full.md's playerObject_update_80EA484 cite was 107150, the label is at asm31.s:107156 -- fixed on the branch. THE BLOCKING MODEL GAP: rust fires the chip at k=352 (fixture auto-fire fire_frame=180 counted from fight-open ~172; the script's A@170 only closes the window) while canon fires at k=250, and rust's player is never hit at all (hp 60, mercy 120 through k=539), so the already-ported flinch model never triggers -- porting the 0x14 arm cannot move mm_state_action past k=250, cannot drop mm_timer below 270, and a 0x0b->0x14 swap inside rust's own episode leaves every frame divergent (canon reads 0x08 there). Bonus contradiction for the follow-up: canon holds Timer=0xFFFF from k=292 to k=539, which the fitted 10-frame post_flinch shadow in src/actor.rs (derived from the older PAUSED capture) does not represent. Captures used 3 of 6; the outside-modified docs/tickets/Q3.md in the main checkout was never touched. Not yet independently verified -- a verifier-hyper is being dispatched on the writer attribution and the fire-frame/hp gap because the next M2 ticket depends on them.
**Why.** battle_full's trace after T50 (landed 21fde8f) reads, per docs/worklog/T50.md/T53.md: `mm_state_action` 76/540 first k=250 canon=(4,0x20) rust=(4,0x08); `mm_anim` 78/540 first k=251 canon=8 rust=0; `mm_timer` 270/540 first k=269 canon=22 rust=0 — 424 of the 1370 divergent field-frames, all three fields of the **player's** BattleObject, inside the same 20 frames. Our port never advances MegaMan's CurAction/CurAnim/Timer for the chip-use action. The two earlier attempts at this group, T7i and T7m, were BLOCKED on the tool soft-limit before any port, and ran on the pre-T47 trace tools. Milestone **M2**.

**New evidence.** (1) T47 (12f10c2) and T49 (34a4dd8, DONE) fixed tools/trace.py and oracle.py and re-mapped the group: T49's "would try next" names the chip-execute chain (CurAction-4 handler `sub_80C5D84`, asm31.s:29664, cited at src/battle.rs:1464). (2) tools/mgba_capture.c:72-84 `--watch-write` (R5, landed 17dc00f) prints frame + store PC + LR and is frame-identical; harness.py:687-689 already used it on **this byte**: `--watch-write 0x0203a9b8` showed CurAction 0x08→0x14 at frame 3 from PC 0x0801169A (lr 0x0800FBF7). Nobody has watched the player's action word across canon's k=200..300.

**Files.** src/actor.rs (the player Action model, its CurState/CurAnim/Timer fields, the oracle export), src/battle.rs (**only** the per-tick call site that advances the player actor — never `trace_snapshot`, never the presentation block at :3427-3462, never deck), docs/coverage/battle_full.md, docs/worklog/T63.md. **NOT** tools/harness.py, tools/trace.py, tools/oracle.py, tools/states.py, tools/inventory.py, tools/allowlist.py; reference/bn6f read-only.

**Do.** 1. Baseline, no edit: `python3 tools/oracle.py battle_full --both` → expect the three fields' first frames/counts above and the 1370 total; `python3 tools/verify_rows.py HEAD wave,window,opening,chip-cannon,mettaur,cursor,windowclose --expect …`; ROM sha256 **and byte size**. **measurement.**
2. Canon store trace: one canon capture of battle_full with `--watch-write 0x0203a9b8:2 --watch-write 0x0203a9c0:1 --watch-write 0x0203a9d0:2` (CurState/CurAction +0x8, CurAnim +0x10, Timer +0x20 off base 0x0203a9b0, tools/trace.py:5-8) → report every store in k=200..300 with frame, old→new, PC, LR. **measurement.**
3. Map each store PC to source (PC−0x08000000, label lookup in reference/bn6f) and read the routine: name the arm that writes CurAction=0x20, what it writes to CurAnim and Timer, and what ends the action; cross-check the enclosing chain against `playerObject_update_80EA484` (asm31.s:107150, docs/coverage/battle_full.md rank 257 — re-check the line on disk). **measurement.**
4. Port that arm into the player action model with those cites as comments; any value step 2/3 cannot site is reported, not written. **code change.**
5. Re-run step 1: mm_state_action's first divergence later than k=250, mm_timer's count below 270, the field-frame total below 1370, guard rows identical, fitted ≤19. **measurement.**

**Rules.** No fitted constant (AGENTS.md); no row/fixture/allowlist change; canon never changes; cursor ≤1/1/170/186279, windowclose 0/0/40 and every zero row identical are the absolute veto; quote ROM sha256 **and** size (T56: a code-layout shift moved cursor 5-28 px). ≤6 captures, tool budget ≤90.

**Acceptance.** Trace target on battle_full, frames 540, field `mm_state_action`: first divergent frame later than **k=250**, `mm_timer` count < 270, 13-field total < 1370, the store PC(s) from step 2 cited in the src diff, fitted ≤19, verify_rows identical on the step-1 guard set as the veto. A NEGATIVE naming every writer of the player's action byte in k=200..300 and the model gap that blocks the arm also closes it.

**Measure and report.** rows: battle_full (oracle), wave, window, opening, chip-cannon, mettaur, cursor, windowclose; frames 540/90/16/40/40/70/170/40. Before/after per-field first frame and count, the 1370 total, the store table (frame/old→new/PC/LR), both ROM sha256s+sizes, fitted count; commit; one line of mechanism; one line of what is unverified.

**Coordinator:** dispatch alone (owns src/actor.rs + one named battle.rs call site). Free tier: verify_rows on the guard set with F48's matcher. A verifier for step 3's PC→routine attribution — every later mm_* ticket builds on it. ≤$0.40 expected, ≤$0.80 cap. Advances **M2**.

---

### T64. M3: BLIND's cross-alliance render gate — poke it on MegaMan, size it, port the one arm T60 did not reach  *(OPEN -- 2026-09-17)*

**Why.** M3 reads "not started" and the cheapest rung is BLIND (ObjectFlags1 0x2000): T60 (PARTIAL, b825b83) read the gate and found that an **enemy-side** poke exercises neither side — `blindVisualHandledHere_8016934` (asm00_2.s:16821-16886) clears `OBJECT_FLAG_VISIBLE` on an object only when `battle_findPlayer(alliance^1)` — the object's **opposing player** — carries 0x2000 (:16861-16869, T18's reader cite). T60's 262,824 px over 240 frames came instead from the AI wander gate (`MettaurDecideCheckStatusAndRow_810A004`, asm31.s:171395), which is **out of this ticket**: a player-side BLIND poke exercises the render arm alone. We already ported the sibling arm in the same routine — `INVIS_HIDE_BIT` at src/actor.rs:420-421 with the `invisible` field at :374-376 — so the hide mechanism exists and only the cross-alliance predicate is missing. Milestone **M3**.

**New evidence.** T60's measured poke recipe (`40:<flags1>:0x2000` **and** `40:<BlindTimer>:0xffff` — the tick clears the bit; a load-time poke is overwritten by CollisionData init ~frame 31) and its address derivation method: the enemy's CollisionDataPtr at base+0x54 = 0x0203abb4 read 0x02038640, ObjectFlags1 = +0x3c (include/structs/CollisionData.inc:145), BlindTimer = +0x20 (:134). For MegaMan, T1's mercy anchor says [0x0203a9b0+0x54]+0x24 = 0x02038514 → ptr 0x020384f0, so the predicted poke targets are **ObjectFlags1 0x0203852c / BlindTimer 0x02038510** — to be confirmed, not assumed.

**Files.** src/actor.rs (the flags word as named consts + the draw gate's `show` path), src/battle.rs (**only** the call site that hands the opposing player's flags to the enemy's draw gate), tools/harness.py (**ONE** new row; no existing row's frames/align/negative/region touched), docs/coverage/statuses.md (new), docs/worklog/T64.md. **NOT** tools/states.py, tools/inventory.py, tools/trace.py, tools/oracle.py, tools/allowlist.py, src/objects.rs (T63's neighbour); reference/bn6f read-only.

**Do.** 1. Baseline: `python3 tools/verify_rows.py HEAD wave,window,opening,chip-cannon,mettaur,cursor,windowclose --expect …`, ROM sha256+size; read `[0x0203a9b0+0x54]` out of the existing canon mmbase watch stream and report the ptr, +0x3c and +0x20 addresses against the prediction above. **measurement.**
2. Canon effect size, no src change: two canon captures of the mettaur row's scene, poked vs unpoked with T60's recipe at step 1's addresses, diffed with `tools/diffmask.py` over 90 frames → px total, first frame, region. **If 0 px: close NEGATIVE naming which test rejects the subject (the 0x100 early-out at :16831-16834, the alliance test at :16852, or the AIData ActorType==2 path at :16862+).** **measurement.**
3. Read asm00_2.s:16821-16886 from disk: report the three arms (0x100 out; 0x202/FlashingInvisTimer — ours at src/actor.rs:420-421, whose cite "16787" is stale, re-derive it; and the 0x2000 cross-alliance clear), which categories reach each, and who clears BLIND and on what tick. **measurement.**
4. Port: BLIND as a named const with its CollisionData.inc:134/145 offsets, plus the cross-alliance arm in the draw gate fed by the opposing player's flags; the bit reaches our side by a row poke at the address **our** port exposes, named from the built ROM's symbol table and never chosen to fit the picture; add the ONE row aligned on the poked frame (the measured event) with a frame-shift negative. **code change.**
5. Re-run: new row 0/0 with a non-blind negative; **our** poked-vs-unpoked total equal to canon's step-2 total over the same window (report both); guard rows identical. **measurement.**

**Rules.** Canon never changes: a poke is the established fixture (F5b's AIData poke), never a patch and never a timer tuned to the picture. No new root state, no allowlist edit, no second status bit in this ticket. Any zero row that stops being zero, or cursor above 1/1/170/186279, or windowclose above 0 → branch unmerged, reported. fitted ≤19. ≤6 captures, tool budget ≤80.

**Acceptance.** Step 2's canon px with frames+region (or the NEGATIVE that closes it); the new row 0/0 with a non-blind negative; ours-vs-canon equal poked-vs-unpoked totals; BLIND/BlindTimer/ObjectFlags1 as named consts with their CollisionData.inc lines; the stale INVIS_HIDE_BIT cite corrected; verify_rows identical on the guard set as the absolute veto. Report explicitly that SCOPE's **statuses 0/69 does not move** (that line is generated from T18's walk) — what moves is M3 from "not started" to a measured scenario.

**Measure and report.** rows: blind (new), wave, window, opening, chip-cannon, mettaur, cursor, windowclose; frames the row's + 90/16/40/40/70/170/40. Before/after totals/worst/negatives, both ROM sha256s+sizes, step 2's px/region, both poked addresses and values, fitted count; commit; one line of mechanism; one line of what is unverified.

**Coordinator:** dispatch alone (owns src/actor.rs + tools/harness.py; disjoint from T63 except battle.rs, so never run beside it). Free tier: verify_rows on the guard set plus the new row. A verifier for step 2's px claim and step 3's arm split — every later status ticket copies this route. ≤$0.30 expected, ≤$0.60 cap. Advances **M3**.

---

### T65. M1: The 297 formations out of the ROM's own record stream — and which ungated record fields each Mettaur rank  *(OPEN -- 2026-09-16, Pass 1 done, verifier-confirmed, ready to land -- blocked only by the dirty main checkout [docs/tickets/Q3.md,)*

**Result.** Pass 1 done, verifier-confirmed, ready to land -- blocked only by the dirty main checkout (docs/tickets/Q3.md, not mine to touch). Branch wt/t65 tip 256b8a5 (ad675cb steps 1-3, d82e3fb steps 4-5, dec03d1 the seven verifier fixes, 256b8a5 the cite erratum I owed it); diff vs merge-base is six files -- tools/inventory.py, docs/inventory/formations.json, docs/inventory/backdrops.json, docs/SCOPE.md (generated), docs/coverage/formations.md, docs/worklog/T65.md -- and ZERO src/, so no row can move and the ROM is main's byte-for-byte (5b46337aa27da9ca881f2321fe1e210f54717285b4dfa5256c1680bac4b985ef, 584296 B; the generator walks ROM bytes, it does not rebuild them -- and note cargo build --release emits only the ELF, the .gba comes from tools/gbafix.py, so a bare "cargo build" hash claim is not attributable). CENSUS, independently reproduced by verifier-hyper c4d03425 (qwen3.8-flash) straight from reference/bn6f/bn6f.gba with no repo tooling: the old .s parse got 461 records / 297 arrays / 2 lists; the ROM walk gets 1240 records over 84 lists (2 scripted family A + 82 encounter-tree family B), 1076 distinct 0xF0-terminated formation arrays, 0 terminator mismatches. Chain: off_8020170 (reference/bn6f/asm/asm29.s:10371) -> group table ([+0] real-world, [+4] internet, 23 groups proven twice over: 0x080201E4 + 23*4 = 0x08020240 = pt_80240 at asm/asm01.s:555-580 AND .equiv INTERNET_NUM_GROUPS, 23 at reference/bn6f/constants/enums/GameAreas.inc:10) -> map array -> 16-byte records, record[0]==0xff terminator; formation quads are 0xF0-terminated with the enemy id at quad[2]. EVENT_67F/680/681 swap only the internet table (0x08020178/80/88) and add no new lists, so 82+2 is complete reachability. KNOWN ANSWERS reproduced byte-for-byte: CentralArea1 list 0x080b4b78, raw length 14, filtered (rec7==0) count 12, rec6=0x080b4bd8, rec10=0x080b4c18, gated rec12=0x080b4c38 / rec13=0x080b4c48 -- and the modulus is the FILTERED count: 882%12=6, 886%12=10, 894%12=6 all match T58's three verified rolls, while mod 14 contradicts two of them. Backdrop byte (BattleSettings +0x4, include/rom_structs/BattleSettings.inc:10, corroborated by battleSettings_setBackground strb at asm/asm03_0.s:14591-14593) over all 1240 records: 0xff 1047, 0x07 192, 0x08 1 (the singleton is battleSettingsList0 record 0 at 0x080aee70). STEP 5: 88 ungated records naming enemy_idx 2..6 over 24 lists; per family, family B has ZERO ungated 4/5/6 (5 and 6 appear only as the gated CentralArea1 rec12/rec13, 4 never), family A HAS 15 (0x080af430/0x080af480/0x080af4e0 name 4) but is index-fetched, so no roll lever exists there -- all 88 rows re-checked by the verifier for record address, rec7==0, lever = position among that list's ungated records, lever < filtered count. VERIFIER FIXES APPLIED: the generated SCOPE line printed "1240 records over 3 lists" because nlists was len() of a dict that aggregates family B into one bucket (tools/inventory.py:1613-1614, the same commit's note already said 84) -- now computed, prints 84; the q column is documented as a 0-based quad index; family-A byte_ labels are carried into formations.json (296 labeled / 780 rom_XXXXXXXX); the 1045/1076 arrays containing a 0x00 quad id are flagged as uninterpreted; the step-5 NEGATIVE is per-family not global. ERRATUM I MUST RECORD: I told the worker the BattleSettings.inc and GameAreas.inc cites were dead on the verifier's say-so -- both files EXIST and both cites were correct; the verifier had searched a fresh worktree whose reference/bn6f submodule is empty. 256b8a5 reframes item 2 as added corroboration and names both paths and lines. Consequence for this run: any claim that a reference/bn6f cite does not exist must be re-checked in /home/box/Code/bn/reference/bn6f before it is acted on. OPEN remains because the ticket's own end condition (all 1076 arrays identified, and the 0x07/0x08 backdrop bytes mapped to art) is not met; the next pass is M5 work that consumes this table.
**Result.** Pass 1 measured and committed on wt/t65 (ad675cb steps 1-3, d82e3fb steps 4-5, tip now under fixup by resume-run 6c135753); src/ untouched (git diff --name-only -- src is empty), tool re-run by the coordinator exits 0, docs/SCOPE.md's human prose at :21 untouched. The census is real: 1240 records over 84 lists, 1076 distinct 0xF0-terminated formation arrays, 0 terminator mismatches, where the old .s parse held 461 records / 297 arrays over 2 family-A lists and missed family B entirely (779 records / 779 arrays, unlabeled ROM after 0x080b1bbc). Pointer chain: off_8020170 (reference/bn6f/asm/asm29.s:10371, swapped by EVENT_67F/680/681 at 0x08020178/80/88) -> group table (21 real / 23 internet words) -> [table+group*4] -> [arr+map*4] -> 16-byte records to record[0]==0xff. T58's four known answers reproduce byte-for-byte (CentralArea1 list 0x080b4b78 = 14 records, raw 14 / filtered 12, gated at 12,13; rec6 0x080b4bd8, rec10 0x080b4c18 with formation 0x080b5387, rec12 0x080b4c38, rec13 0x080b4c48). verifier-hyper (c4d03425) CONFIRMS all of that and adds: the modulus is the FILTERED count (882%12=6->rec6, 886%12=10->rec10, 894%12=6->rec6, where mod 14 gives 0/4/12 and contradicts two verified picks); the walk covers everything reachable (the three internet tables add 0 new lists, 82 family-B + 2 family-A = 84); the backdrop histogram 0xff:1047 / 0x07:192 / 0x08:1 sums to 1240 with the singleton at 0x080aee70; and it re-checked all 88 step-5 rows. Seven REFUTED / fix-before-merge items, all dispatched back to the worker: (1) tools/inventory.py:1236 prints 'over 3 lists' as a literal though :1234 computes 84, and the note keeps the stale T32 .s-parse framing; (2) two cites name files that do not exist -- BattleSettings.inc and GameAreas.inc:10 -- the +0x4 Background byte is proven instead by asm/asm03_0.s:14591-14593 battleSettings_setBackground; (3) the step-5 NEGATIVE is per-family not global: family A's battleSettingsList0 has 15 ungated records naming enemy_idx 4/5/6 (0x080af430, 0x080af480, 0x080af4e0 name 4) while family B, the only roll-levered family, has none; (4) the (q,id) table convention is undocumented so a reader sees 9 false mismatches per 88; (5) formations.json now names 1076/1076 arrays rom_*, contradicting formations.md:14's label-or-address claim -- every family-A array lost its byte_ label vs the T50 baseline; (6) zero-id quads (rom_080aff44 enemy_ids ['00','7f']) are uninterpreted and unnamed as a gap; (7) the ROM hash 5b46337a... cannot be attributed to , which emits no .gba (only ELF ade9310b...), so the build command must be quoted as the build_roms.sh/gbafix path that produced it. Landing still blocked independently by the dirty main checkout (docs/tickets/Q3.md, not mine to commit or revert).
**Why.** M1's formations line is "FOUND: data/BattleSettings.s battleSettingsList0:2 / BattleSettingsList1:1505, 461 records, 297 0xF0-terminated formation arrays | **0/297**", and tools/inventory.py:1208-1212 admits the number is "provisional, this tool's own arithmetic, not independently divided out". T58 tried the same .s-line parse and **desynced on 299 formation labels**; only its ROM-side walk (list pointer `off_8020170` → group 0x90 / map 0 → 0x080b4b78, self-verified by `record[0]==0xff`) held. Without that table the next M5 recording is a guess: the ported Mettaur routine (ai_index 1) covers **6/187 pairs** (enemy_idx 1-6, HP rows 0x28/0x50/0x78/0xA0/0x78/0xB4 per docs/worklog/T58.md) and the one list read names the other five ranks only in rec12 0x080b4c38 (enemy_idx 5) and rec13 0x080b4c48 (enemy_idx 6), both gated by `record[7]==1` → `sub_80AA6EC`. Milestone **M1**, unblocking **M5**.

**New evidence.** T58 (PARTIAL, 0302084) measured the roll model and closed it three ways: filter (`record[7]` handler, then element mask & 0x1f), weight 1 per passing record, pick candidate `(iCurrFrame mod count)`, the roll reading iCurrFrame **one tick after** the frame-60 poke — verified by 0x371→rec6, 0x375→rec10, 0x37D→rec6 (a count of 14 would have picked rec12). That makes "which record fields rank R in map M, and with what lever value" a computable question, and gives this ticket its known-answer checks.

**Files.** tools/inventory.py (**only** `parse_formations`/`parse_backdrops` and their notes — the `AS_DATA_FAMILIES` literal is frozen, its comment is T62's), docs/coverage/formations.md (new), docs/inventory/ (generated), docs/SCOPE.md (regenerated only), docs/worklog/T65.md. **NOT** src/ (zero changes), tools/harness.py, tools/states.py, tools/rom_enemy_tables.py, tools/trace.py, tools/oracle.py, tools/allowlist.py, assets/; reference/bn6f read-only.

**Do.** 1. Baseline: `python3 tools/inventory.py`, quote the formations and backdrops lines and the generated row counts; build the ROM and quote its sha256 (src/ untouched). **measurement.**
2. ROM walk of every list: from the group-list table, each list's 16-byte records to its 0xff terminator; per record report address, list id (group/map), formation label, its enemy_idx entries (0xF0-terminated quads, byte [2] as at inventory.py:1060), `record[7]`, and the Background byte (BattleSettings.inc:8, +0x4). Report the per-list record count and the terminator mismatches. **measurement.**
3. Known answers: reproduce rec6 0x080b4bd8 and rec10 0x080b4c18 in CentralArea1's list 0x080b4b78, the list's 14 records, and rec12/rec13's `record[7]==1`; every mismatch named by record address. **measurement.**
4. Replace the provisional note with the ROM-derived counts and report how many records and how many formation arrays the old .s parse missed; regenerate the backdrops section (Background byte → records using it) from the same walk. **tools change.**
5. Answer the M5 question from the table: every ungated (`record[7]==0`) record naming enemy_idx 2..6, with its list, index and the `iCurrFrame mod count` lever value that fields it, written into docs/coverage/formations.md; re-build and re-quote the ROM sha256. **measurement.**

**Rules.** Zero src/ changes — a byte-identical ROM is the gate (T56: a −900 B tree moved cursor 5 px). No new state, row, fixture or allowlist change; no states.py edit (T58's recipe stays as it is). Every cite re-checked against disk; the count may go **down** if the ROM says so. ≤1 capture, tool budget ≤40.

**Acceptance.** A per-list record table with the ROM-derived counts (old vs new quoted, mismatch count 0 or named); the four known answers from step 3 reproduced byte-for-byte; ≥1 ungated record naming enemy_idx 2..6 with the lever value that fields it, or a NEGATIVE stating that none of the lists read this way has one, with the list count covered; ROM sha256 identical before/after; `git diff --name-only` = the named files.

**Measure and report.** rows: none (no ROM change). The ROM sha256 (before = after), record/array counts before/after, per-list record counts, the step-3 known-answer table, the ungated rank-bearing records with lever values, `git diff --stat`; commit; one line of mechanism (which pointer chain the walk followed); one line of what is unverified (no scenario, no port, no row).

**Coordinator:** dispatch when tools/inventory.py and docs/SCOPE.md are free — it overlaps **T62** (OPEN, owns that comment and SCOPE's prose) and must not run beside it; then run it beside T63 or T64 (files disjoint). Free tier: none to land; run `python3 tools/inventory.py` yourself and diff the generated part. A verifier for step 3's known answers and step 5's ungated list, since the next M5 recording buys them. ≤$0.15 expected, ≤$0.30 cap. Advances **M1**, unblocks **M5**.

### D9. Retire the journal: move the twenty cited facts into the code that relies on them  *(OPEN -- 2026-09-16)*
**Why.** `TRANSFER.md` is 2,897 lines of the first phase's journal that no agent may read whole, yet twenty-odd comments in `tools/` and `src/` cite it for the provenance of a number ("eBGScrollCBCounters read 0/0, TRANSFER.md 7aw"; "what makes the battle conclude, TRANSFER.md section 3"). `python3 tools/transfer.py --cited` lists every cited section, which file cites it, and one heading each; one citation (`TRANSFER.md 1270`, in tools/allowlist.py) names a section that does not exist. A citation a worker cannot cheaply resolve costs turns, and a dangling one is worse. Milestone M2 (the tooling the engine core is measured with): no engine change.
**Files.** docs/provenance.md (new), tools/allowlist.py, tools/harness.py, tools/states.py, tools/patch_sterile.py, tools/scoreboard.py, tools/chip_compare.py, src/*.rs (comment lines only), AGENTS.md and AGENT_GUIDE.md (the rule, once the citations are gone).
**Do.** 1. `python3 tools/transfer.py --cited` for the list; for each, read that section with `tools/transfer.py <id>` and write the fact it carries, in two or three sentences with its measurement, into `docs/provenance.md` under a heading that keeps the old id as an anchor (`## 7aw — a save state at a battle's first frame`). 2. Repoint every citation at `docs/provenance.md#<id>`. 3. Resolve the dangling `TRANSFER.md 1270` citation: find what allowlist.py's gauge-stripe entry actually rests on, or mark it unproven. 4. Leave TRANSFER.md in place, untouched, with a line at the top saying the load-bearing facts now live in docs/provenance.md.
**Rules.** Comments and docs only: no behaviour change, and the .gba may differ only by panic-line bytes. Do not delete or edit TRANSFER.md's body.
**Acceptance.** `grep -rn 'TRANSFER' tools/ src/ | grep -v transfer.py` returns nothing but the new pointer; `python3 tools/docs_check.py` reports no dangling citation; verify_rows PASS on mettaur, field, opening, cursor identical to HEAD.
**Measure and report.** The harness lines before and after, the count of citations moved, and the answer to the dangling one.
**Coordinator:** a docs ticket; no verifier needed when verify_rows is identical.


### T66. Replace the fitted POST_FLINCH_FRAMES shadow with the measured Timer hold (M2, model quality)  *(PARTIAL -- 2026-09-16, Acceptance met in full, but UNMERGED: land.sh refuses while main's checkout carries foreign uncommitted edits,)*

**Result.** Acceptance met in full, but UNMERGED: land.sh refuses while main's checkout carries foreign uncommitted edits, and by now that is three files (docs/tickets/Q3.md, tools/ghidra_decompile.sh, tools/ghidra/BnPrepare.java) -- a live human Ghidra session in this checkout, which I must not touch, stash or commit. Branch wt/t66 tip 13623d0 (8495f6c the change, 9aa7e26 worklog, 13623d0 the verifier-requested cite fixes, comment-only: `git diff 9aa7e26..13623d0 -- src/` has zero non-comment lines). Diff vs main: src/actor.rs, src/battle.rs, docs/coverage/battle_full.md, docs/worklog/T66.md. WHAT IT DID: deleted `const POST_FLINCH_FRAMES: u8 = 11; // provenance: fitted` and the 11-frame 9..0 countdown shadow, replaced by `timer_holds_sentinel: bool` + `const TIMER_SENTINEL: u16 = 0xffff` (derived: playerFlinchAction_80174FE underflows Timer to 0xFFFF at asm00_2.s:18353-18356, PC 0x08017586 strh, and the CurAction 0x08 handler playerAI_update_80EA734 at asm31.s:107357-107447 contains ZERO oBattleObject_Timer stores, so the sentinel is held until another writer fires; canon holds it 248 frames, k=292..539, T63 store table). ROM sha256 now ef2ebed1d0cc6617e6e15c494e0a87fe32011ec16656cc458c5e50cbe321e029 (code changed, so it differs from main's 5b46337a...; measured with the gbafix path, not bare cargo build). MEASURED (my own free-tier re-runs, twice, not the worker's): wave 0/0/90/3840, window 0/0/16/81056, opening 0/0/40/86591, chip-cannon 0/0/40/9505, mettaur 0/0/70/41734, windowclose 0/0/40/207166 all MATCH, cursor 1/1/170/186279 identical to main -- the known single-frame tear, reported not chased, inside the ticket's 1/1 and total<=186300 veto; verify_rows verdict PASS at both 9aa7e26 and 13623d0. VERDICT: verifier-hyper 54b8a0d9 (qwen3.8-flash) says MERGE, no blockers, and independently re-derived the disassembly shape; it REFUTED four things in the first pass, all fixed on the branch -- asm00_2.s:17875/17977 store the SPAWNED t1 effect object's Timer, not the player slot (player-slot lines are 17877/17979); the "no Timer here" range was short (widened to 18358-18366, the phase write); the four-writer list was NOT exhaustive (now labelled non-exhaustive with the per-frame decrementors asm00_2.s:1381/1691/16135/16287/16460/18259/18903 and object.s:143/172/785 named, and the note that if any is reachable on the player slot the sentinel counts down instead of holding); and the worklog's reason for "no row moved" was false ("their players never flinch" -- the mettaur row at tools/harness.py:1045 says MegaMan is hit mid-attack-1 on BOTH sides, ours at battle frame 177, and src/actor.rs:622 is the hit path). The true reason, now recorded: harness rows compare pixel diffs only (verify_rows parses total/worst/frames/negative) and oracle RAM fields like mm_timer are in no row's compared region -- so six identical rows are VACUOUS evidence for this field, not proof of harmlessness. mm_timer on battle_full stays 270/540 (first k=269, canon 22 rust 0) because our navi is never hit there. STILL OPEN, ticketed as T67: the 9..0 tail the deleted constant was fitted to is unattributed -- whatever wrote it is by definition a player-slot Timer writer missing from the census -- so the open-ended hold is provisional on battle_full's store table; and the fire-event alignment (canon k=250 from a scripted A@260 vs our AUTO-FIRE at k=352) stays un-ticketed pending a user ruling, because the row rules forbid retuning fire_frame.
**Why.** `src/actor.rs:429` carries `const POST_FLINCH_FRAMES: u8 = 11;` tagged
`// provenance: fitted -- read off the PAUSED+Start@10 watch capture`, and the export at
`src/actor.rs:727-735` emits `0xffff` on the first idle frame, then a 9..0 countdown, then 0 (the
`measured 137..147` comment sits at `src/actor.rs:660`). T63's verifier (87d802ec, verdict in the
T63 Result) measured what canon actually does in `battle_full`: the flinch handler
`playerFlinchAction_80174FE` (`reference/bn6f/asm/asm00_2.s:18300-18378`) writes Timer `0x17` at
k=269 (PC `0x0801757C`, same-frame decrement `0x08017586`), and at k=292 (capture frame 303) writes
`0x00 -> 0xFFFFFFFF` (PC `0x08017598`, with `CurAnim 1 -> 0` and `CurAction 0x03 -> 0x08` in the same
tail) and then **holds 0xFFFF for 248 frames to k=539** -- a real hold, since no store to
`0x0203a9d0` occurs after frame 303 in the 67-store table. An 11-frame fitted shadow cannot represent
that. This is the only M2-side defect T63 proved that is fixable without touching a fixture or a
fire-frame, both of which the row rules forbid and which need a user ruling.

**Do.** Read `docs/worklog/T63.md` first (store table, all numbers).
1. Re-derive the post-flinch Timer behaviour from the ROM, not from the fitted constant: after the
   countdown reaches 0, Timer stays at the `0xFFFF` sentinel until some *other* writer touches it.
   Find the writers in the disassembly (`grep -n "oBattleObject_Timer" reference/bn6f/asm/*.s` and
   the flinch tail above) and state which ones can end the hold; if none can, the hold is open-ended
   and the model must say so.
2. Change `src/actor.rs` so the exported `mm_timer`/`Timer` value follows that rule. If the old shadow
   is still needed to keep a passing row passing, keep it behind a named constant whose provenance tag
   cites a measurement (file:line + frame range), never `fitted`, and say which row forced it.
3. Baseline first, same script twice: `python3 tools/oracle.py battle_full --both` before and after,
   and the guard set `python3 tools/verify_rows.py wt/t66 wave,window,opening,chip-cannon,mettaur,windowclose,cursor
   --expect ...`. The shadow is shared by rows that pass today, so this is the risk of the ticket, not
   step 1.
4. Note honestly what this ticket can and cannot move: on `battle_full` OUR navi is never hit (hp set
   {60}, mercy {120}, timer {0} over k=0..539), so `mm_timer`'s 270 divergent frames are NOT expected
   to move here; the fire-alignment gap (canon fires at k=250 from a scripted `A@260`, we fire at
   k=352 from AUTO-FIRE with `fire_frame: 180`) is a separate, un-ticketed blocker awaiting a ruling.

**Files.** `src/actor.rs` (the shadow and its export), `docs/coverage/battle_full.md` (record the
248-frame 0xFFFF hold and the writer list), `docs/worklog/T66.md`. `src/battle.rs` only if the Timer
export path forces it; no fixture, no `tools/states.py`, no `tools/harness.py` row config.

**Rules.** Do not change any fixture, script, `fire_frame`, compared region or comparison start; do not
widen `tools/allowlist.py`; `reference/bn6f` is read-only. A fresh worktree has an EMPTY
`reference/bn6f` submodule -- read the disassembly from `/home/box/Code/bn/reference/bn6f` (or export
`BN6F_REF` to it) or you will "refute" live cites. `cargo build --release` emits no `.gba`; the ROM
comes from `python3 tools/gbafix.py $CARGO_TARGET_DIR/thumbv4t-none-eabi/release/bn <out>.gba`, so
quote that if you report a hash. Report in the AGENTS.md shape (row, frames, total, worst, region,
commit, one line of mechanism, one line of what is unverified).

**Acceptance.** `POST_FLINCH_FRAMES` is either gone or carries a provenance tag naming a measurement
and a frame range; the hold rule is stated in `docs/coverage/battle_full.md` with the ROM writers that
can end it; every named guard row is identical or better, and any row that moves is reported with its
numbers (a row that gets worse means keep the branch unmerged and report). `cursor` measures 1 frame
and 1 px of total <= 186300 (it moves with ROM layout: report, do not chase; > 1/1 or total > 186300
with the same ROM sha256 as main's `5b46337aa27da9ca881f2321fe1e210f54717285b4dfa5256c1680bac4b985ef`
means unmerged). If the change turns out to be unobservable anywhere today, that is a valid outcome --
report it as a model-quality change with the rows unchanged, and name the trace that would show it once
the hit lands.

### T67. Attribute the PAUSED+Start@10 Timer tail -- which player-slot writer decrements Timer after a flinch? (M2, model audit)  *(OPEN)*

**Why.** T66 deleted `const POST_FLINCH_FRAMES: u8 = 11; // provenance: fitted` and replaced the
9..0 countdown shadow with an open-ended `TIMER_SENTINEL` hold (`src/actor.rs`, branch wt/t66). Its
verifier (54b8a0d9, verdict in the T66 Result) CONFIRMED the derivation -- the underflow store is
`asm00_2.s:18356-18358` at PC `0x08017586`, the flinch exit tail writes no Timer, and the
CurAction 0x08 handler `playerAI_update_80EA734` (`asm31.s:107357-107447`) has ZERO
`oBattleObject_Timer` stores -- but left one item open, quoted here because it is the whole ticket:
**"the old PAUSED+Start@10 9..0 tail is still unattributed -- the deleted fitted constant's
observation is explained away rather than explained; whichever writer produced it is by definition a
player-slot Timer writer missing from the census."** So either that older capture's 9..0 tail was a
different field/offset read, a different object, or a real player-slot Timer writer that T66's hold
model does not represent. All three are answerable from ROM text plus ONE watch capture; no row is
expected to move (rows compare pixels, and `mm_timer` is in no row's compared region --
`tools/verify_rows.py`'s row regex carries total/worst/frames/negative only).

**Do.**
1. Reproduce the reading the deleted constant was fitted to. The provenance tag named a
   `PAUSED+Start@10 watch capture` -- find that scenario: `grep -rn "PAUSED\|Start@" tools/states.py`
   (read the section that defines it, not the whole file) and re-run its canon side with
   `--watch-write 0x0203a9d0:2` on the player object, long enough to cover the post-flinch frames.
   Report the frame window and the values. If it cannot be reproduced, that IS the result: record it
   and the fitted tag was fitting a phantom.
2. Census the candidates: `grep -n "oBattleObject_Timer" reference/bn6f/asm/*.s` (T66's verifier
   counted `[r5]` Timer stores in asm00_2.s at 1381, 1674, 1691, 16135, 16142, 16250, 16287, 16454,
   16460, 18259, 18262, 18274, 18812, 18888, 18903 plus `object.s:143/172/785` incrementors, ~1807
   store sites tree-wide, and `oBattleObject_Timer` is a UNION member so a `+0x20` store is not the
   same field -- that distinction is what refuted T66's first writer list, keep it). For each store
   that can reach the PLAYER slot, name the routine, the register base and what event reaches it.
   Then answer: does any of them run per-frame after the flinch exit? That is the only shape that can
   produce a 9..0 tail.
3. Decide the model. If a real per-frame player-slot decrementor exists, T66's hold is wrong for that
   window: the fix goes in `src/actor.rs` ONLY if the census names a reachable writer, in which case
   model the writer (countdown length from the disassembly, never a fitted count) and re-run
   step 1's capture to show the trace matches. If none is reachable, the hold stands and
   `docs/coverage/battle_full.md` plus the `TIMER_SENTINEL` provenance tag must say so explicitly --
   "open-ended hold, provisional on battle_full's 248-frame store table; the PAUSED+Start@10 tail is
   attributed to <finding>" -- with the unattributed-forever case written as a negative, not left as a
   loose end.

**Files.** `docs/coverage/battle_full.md`, `docs/worklog/T67.md`, `src/actor.rs` (only if step 3 finds
a reachable writer), `src/battle.rs` (comment lines only, if they repeat a cite you correct). No
fixture, no `tools/states.py`, no `tools/harness.py` row config, no allowlist change.

**Rules.** `reference/bn6f` is read-only, and a FRESH worktree has an EMPTY `reference/bn6f` submodule
(gitlink) -- read the disassembly from `/home/box/Code/bn/reference/bn6f` or export `BN6F_REF` to it,
otherwise you will "refute" live cites (this has now burned two verifier rounds this run).
`cargo build --release` emits no `.gba`: the hashed ROM is
`python3 tools/gbafix.py $CARGO_TARGET_DIR/thumbv4t-none-eabi/release/bn <out>.gba`, so quote that if
you report a hash. Work only in your own worktree; do not touch main's checkout, which carries a
foreign uncommitted edit to `docs/tickets/Q3.md`. Never rename or move a value you did not need to
understand. Report in the AGENTS.md shape (row, frames, total, worst, region, commit, one line of
mechanism, one line of what is unverified).

**Acceptance.** The 9..0 tail is either attributed to a named ROM writer with its reachability argued
from the disassembly, or closed as unattributable with the reproduction attempt's frame window and
values -- one or the other, not "still open". If `src/actor.rs` changed, the guard set
`wave,window,opening,chip-cannon,mettaur,windowclose,cursor` is identical or better at the new tip and
`mm_timer` on battle_full is reported before/after from `python3 tools/oracle.py battle_full --both`;
if only docs changed, say so and give `git diff --name-only` to prove no src/. `cursor` measures 1
frame and 1 px of total <= 186300 (it moves with ROM layout: report, do not chase; > 1/1 or total >
186300 on the same ROM sha256 as main's `5b46337aa27da9ca881f2321fe1e210f54717285b4dfa5256c1680bac4b985ef`
means unmerged). A precise negative is a good outcome here: T66 merges either way, and this ticket
only tightens what its provenance tag is allowed to claim.
