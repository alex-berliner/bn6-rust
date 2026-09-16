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

### T44. battle_full sequencer first-divergence on T7r scripted fixture *(OPEN -- 2026-09-16)*
**Why.** T7r PARTIAL landed a battle_full fixture with gauge=1 + window_pick OK + scripted A@170 so `self.seq.state` traverses {SEQ_20, SEQ_24, SEQ_00, SEQ_04} (TODO.md:197). docs/SCOPE.md M2 still reads "battle_full diverges on 174/540 sequencer frames". The sequencer-timing objective closed NEGATIVE/BLOCKED four ways (T7s NEGATIVE, T7u BLOCKED, T7y NEGATIVE, T7z BLOCKED); this is a recon pass on the T7r fixture that exists now, not a port.

**New evidence.** T7r PARTIAL landed the scripted A@170 fixture (was a measurement-only branch); T7p DONE drove rng_cadence below 10/540 (RNG residue bounded); T32 DONE + T9l PARTIAL seeded gunner/gauge from measured values; no oracle run has ever been on T7r's branch tip.

**Files.** `tools/trace.py`, `tools/oracle.py`, `tools/diffmask.py`, `tools/verify_rows.py`, `docs/worklog/T44.md`. No `src/` edits.

**Do.**
1. Check out the T7r branch tip into a worktree. **measurement.**
2. Run `python3 tools/oracle.py battle_full --both`; record first divergent field and frame. **measurement.**
3. Run `python3 tools/diffmask.py battle_full --frames 170..200,195..250`; record per-frame px diff and region. **measurement.**
4. Run `python3 tools/verify_rows.py HEAD wave window opening chip-cannon mettaur --expect 0/0/N`; record identical/veto. **measurement.**
5. Write `docs/worklog/T44.md` naming first divergence field+frame, region, and the reference/bn6f routine for that field.

**Rules.** Read-only this ticket; cite reference/bn6f file:line for every measurement; do not reopen T7s/T7u/T7y/T7z; if divergence sits in a closed sub-objective, report NEGATIVE with the new cite and stop.

**Acceptance.** `tools/oracle.py battle_full` names first divergence at frame ≥ 540 (i.e., past end-of-trace) OR names field+frame with a reference/bn6f cite; verify_rows on wave/window/opening/chip-cannon/mettaur identical to HEAD (veto on regression). If divergence is at k<540 in a closed sub-objective, NEGATIVE with the named cite.

**Measure and report.** battle_full · frames · total · worst · region · commit · oracle first divergence field+frame · cite · one line of mechanism · one line of what is unverified.

**Coordinator:** Reject any `src/` edit; require the oracle to run on T7r's branch tip, not main; verify_rows identical is the veto.

**SCOPE:** advances M2.

---

### T45. M5 Gunner row aligned on first attack event *(OPEN -- 2026-09-16)*
**Why.** F40a BLOCKED on `gunner 2105613/38237/130` said the BG3 plateau lever wasn't settled. T9j PARTIAL ported the per-type routine `ForGunner_8113078` (asm32.s:10123-10142, 4-arm state machine sub_8112F70/sub_8112FBA/sub_8113002/ai_8113038) into `src/gunner.rs::gunner_update`. T9l PARTIAL landed as424814d and derived the gunner row's own backdrop seed (gunner 2850534/38237/130 baseline, regressed since to2105613). T32 DONE named the gunner gauge seed. T9k NEGATIVE refused to relocate `Battle::gunner_ctl`/`Battle::impacts` into `GunnerEntry`; alignment must live elsewhere.

**New evidence.** T9l PARTIAL landing424814d settles the backdrop layer of F40a's plateau; T32 DONE settling the gauge seed answers the gauge-driven half of the BG3 plateau question; T9j PARTIAL having the per-type routine in `src/gunner.rs` means the first-attack predicate (sub_8112F70 → sub_8112FBA firing-setup) is local and alignable.

**Files.** `src/gunner.rs`, `src/battle.rs` (read-only), `tools/oracle.py`, `tools/harness.py`, `tools/verify_rows.py`, `docs/worklog/T45.md`.

**Do.**
1. Read `src/gunner.rs::gunner_update` and the 4-arm dispatch cite (asm32.s:9958-10102). **measurement.**
2. Run `python3 tools/oracle.py gunner --field gunner_attack_event` if present; else peek `oAIAttackVars_Unk_00` to find stage-0→4 transition frame. **measurement.**
3. Run `python3 tools/verify_rows.py HEAD gunner --expect0/0/130`; record baseline. **measurement.**
4. Wire the alignment event (stage-0→4 frame, cite asm32.s:9980) into the harness's `GUNNER_ROW` if needed; re-run verify_rows on gunner+mettaur+windowclose+result; report before/after. **measurement.**

**Rules.** Cite asm32.s:9980 for the firing-setup frame; do not move `Battle::gunner_ctl` or `Battle::impacts` (T9k NEGATIVE); no allowlist change.

**Acceptance.** gunner row reads 0/0/130, verify_rows on mettaur/windowclose/result identical to HEAD; OR named mechanism with cite if 0/0 unreachable and the named mechanism drops gunner integrated below 1,500,000.

**Measure and report.** gunner · frames · total · worst · region · commit · first attack frame · cite · one line of mechanism · one line of what is unverified.

**Coordinator:** Reject any `src/battle.rs` refactor (T9k NEGATIVE veto); require the change to be confined to `src/gunner.rs` + harness; verify_rows identical is the veto.

**SCOPE:** advances M5.

---

### T46. M4 chips as data: Bomb family reads AttackPower +0x1a *(OPEN -- 2026-09-16)*
**Why.** T17 DONE drove the sword/blade family from `ChipDataArr`'s own attack bytes (10 chips pixel-verified AS DATA per SCOPE M4). T36 PARTIAL drove Cannon/HiCannon/M-Cannon from AttackPower+0x1a (`branch landed as be6e706`). T38 NEGATIVE tried to rewrite the Cannon family and was NEGATIVE. T34 NEGATIVE tried the Recov/Barrier/Vulcan subfamily tables and was NEGATIVE. The Bomb family (MiniBomb 0x36, EnergBom 0x37, MegEnBom 0x38, FlshBom 0x39, BlkBomb 0x3c, BigBomb 0xca — six rows in `tools/scoreboard.py:59-64`) is unverified-as-data and has not been ported. SCOPE M4 is at 43/411; this port would close 6/411 once the harness row reads 0/0/N.

**New evidence.** T17 DONE set the `AttackFamily`-driven dispatch pattern; T19 DONE made the chip-asset contract loud so a Bomb family port declares its sprite range (`byte_80B8BD4` row cite per `chip_export.py` precedent); T36 PARTIAL landed the AttackPower+0x1a read for Cannon; no Bomb family port has been tried.

**Files.** `src/chips.rs`, `src/inventory.rs`, `data/ChipDataArr.s` (read-only), `tools/inventory.py`, `tools/harness.py`, `tools/verify_rows.py`, `docs/worklog/T46.md`.

**Do.**
1. Read `tools/inventory.py` for the Bomb family's `data/ChipDataArr.s` lines; pick the lowest-id unverified record (0x36 MiniBomb). **measurement.**
2. Run `python3 tools/verify_rows.py HEAD chip-minibomb --expect N/N/N`; record baseline. **measurement.**
3. Replace any `match chip.id` arm for MiniBomb (and the 5 family siblings in one commit) with `chip.attack_power()` + element reads per T17's pattern; cite `data/ChipDataArr.s:<line>` for each record. **measurement.**
4. Re-run verify_rows on chip-minibomb + all sibling rows; record before/after. **measurement.**
5. Update `tools/inventory.py` Bomb family row to `verified` with the cite once the harness reads 0/0.

**Rules.** Cite `data/ChipDataArr.s:line` for every chip record; do not edit allowlist; do not change `tools/inventory.py`'s count line except to mark the family as data-driven; do not widen to Recov/Barrier/Vulcan (T34 NEGATIVE).

**Acceptance.** chip-minibomb + chip-energbom + chip-megenbom + chip-flshbom + chip-blkbomb + chip-bigbomb all read 0/0/N; `tools/inventory.py` Bomb family row marked `verified` with cite; verify_rows on all other chip rows identical to HEAD.

**Measure and report.** chip-minibomb · frames · total · worst · region · commit · first divergent frame · cite · one line of mechanism · one line of what is unverified.

**Coordinator:** Verify each Bomb chip's `data/ChipDataArr.s` record actually has a non-zero AttackPower byte before edit; reject edits to non-Bomb chip families; verify_rows identical on the43 already-verified chip rows is the veto.

**SCOPE:** advances M4.

