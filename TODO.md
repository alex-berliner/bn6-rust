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
### T64. M3: BLIND's cross-alliance render gate — poke it on MegaMan, size it, port the one arm T60 did not reach  *(PARTIAL -- 2026-09-16, Steps 1-3 measured, step 4 ported, step 5 red: branch wt/t64 [4085a9d code+row, 9f1ce9a docs] kept UNMERGED [n)*

**Result.** Steps 1-3 measured, step 4 ported, step 5 red: branch wt/t64 (4085a9d code+row, 9f1ce9a docs) kept UNMERGED (new blind row is red, ticket's own veto). Canon poke addresses confirmed: [0x0203aa04]=0x020384f0 -> ObjectFlags1 0x0203852c, BlindTimer 0x02038510 (ticket prediction confirmed). Canon effect: player-side BLIND poke (frame 40) hides the Mettaur whole: 72,194 px over 90 frames, first div k=1 (capture 41), region her sprite box (x151-202,y68-120); wave still flies = render arm alone. Arms re-read: 0x100 out :16831-16834; 0x202 blink via FlashingInvisTimer :16839-16841 (stale cite 16787 fixed); 0x2000 cross-alliance clear :16846-16870 (battle_findPlayer(alliance^1), object_getFlag = CollisionDataPtr+0x3c); BLIND cleared by tick in sub_800E730 (object.s:5511-5526). Port: OBJECT_FLAGS_BLIND / COLLISIONDATA_BLIND_TIMER / COLLISIONDATA_OBJECT_FLAGS1 consts, BLIND_POKE_MAILBOX no_mangle .bss 0x020002fc (nm), arm in Actor::show fed from battle.rs enemy loop ~:5180, new blind row (canon_ref 40, band 26-39, 90 frames) + frame-shift negative. Ours poked-vs-unpoked = 37,906 px vs canon 72,194 over same window, same first frame 41: residual ~308-396 px inside her box = a second draw contributor canon's header-flag clear suppresses; port hides ~half, not all. verify_rows on 9f1ce9a reproduces report exactly: blind FAILED 69987/1940/90/70487, wave/window/opening/chip-cannon/metpaur/windowclose all 0/0, cursor 1/1/170/186279 known tear, no BLIND negative. ROMs: canon a37c1028 (8,388,608 B) vs ours 9fe6a964 (582,976 B). SCOPE statuses 0/69 unmoved (T18 walk); M3: not-started -> measured scenario with a half-working ported render gate. No verifier dispatched (branch not merged). Next route: worklog/T64.md section 5 (find the second draw contributor; likely header-flag suppression path not yet modelled). Model worker-zai.
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

### T65. M1: The 297 formations out of the ROM's own record stream — and which ungated record fields each Mettaur rank  *(DONE -- 2026-09-17, PASS 3 LANDED as 79da4ed — ticket end condition MET, both halves)*

**Result.** PASS 3 LANDED as 79da4ed — ticket end condition MET, both halves. (1) ACCOUNTING: all 1076 formation arrays named by their referencing records (1240 referrer entries over 1240 records); verifier-hyper f6bd017f re-implemented the walk independently and found 0 referrer mismatches and 0 length mismatches, and proved the residue scan live (positive control: word refs for 0x80b083b at 0x80afa2c). Residue named by the tool: 52 bytes in four orphan 0xF0-terminated quad runs (0x080b199b..0x080b19ac, 0x080b1b57..0x080b1b78, panel-coords+id nibbles, no census record and no aligned/unaligned ROM word reference) + 28 align-pad bytes (8 three-byte pads, 4 one-byte slivers, all addressed). The 297th .s label explained: byte_80B083F is an interior +4 continuation label of the array starting 0x080b083b, referenced by record 0x080afa20 — 297 labels vs 296 referenced starts. (2) BACKDROP->ART: BattleSettings+0x4 read by sub_8081308 (asm21.s:469-523, ldrb :473-475), reached from sub_8080DA0 (asm21.s:15-45 via initBattleStructsAndVram_80071D4 asm00_1.s:8435); id indexes three parallel tables off_8080E34[id*0x10] scroll/LCD, off_8080F98[id] -> LoadBGAnimData (asm03_0.s:21209), off_8081220[id] -> LoadGFXAnims. 0x07 (192 records, all BattleSettingsList1) -> off_8081098 tiles 0x08616598 / tilemap 0x08616634 / palette 0x08616760 = the Comps1/Comps2 map art (maps/Comps1/loader.s:240-246, Comps2 :215-227); 0x08 (the single battleSettingsList0 rec 0 at 0x080aee70) -> off_80810B4, same tiles+tilemap, palette 0x08616EC4; 0xff (1047) = map default (real-world -> 7 at asm21.s:515-516, net per-map pt_808139C :548-572, weather-puzzle override 0x15 :502-509). Art identity proven at ROM-address level from each map loader-s own record, not pixel-compared (VRAM dst/len differ: 0x6008020/0x1800 map vs 0x6000020/0x800 battle). BONUS: 0x00 quad id is the dispatch-0 player-spawn slot (quad[0]>>4 -> off_80073A0, asm00_1.s:8568-8631; 0=spawnMegaMan_80073CC reads only alliance+panel, 1=spawnEnemy_80073E2 reads quad[2]); of the 1045 arrays with a zero id, 991 have them only in dispatch-0 and 54 also elsewhere (per-array sets {0}:991 {0,3}:38 {0,10}:12 {3}:2 {0,9}:2; nibble 2 never appears), and ZERO of 2546 dispatch-1 quads carries id 0 — enemy_idx 0 never spawns from a formation. GATES: zero src/ (6 files, all named), ROM sha256 5b46337aa27da9ca881f2321fe1e210f54717285b4dfa5256c1680bac4b985ef unchanged (cargo build --release + tools/gbafix.py), tools/inventory.py regenerates formations.json/backdrops.json/SCOPE.md to themselves, verify_rows guard set identical pre and post (wave/window/opening/chip-cannon/mettaur/windowclose 0/0, cursor 1/1/170/186279 known single-frame tear). VERIFIER: f6bd017f CONFIRMED claims 1, 3, 4 and the key half of 2; REFUTED the 54-array parenthetical (claimed exclusivity of non-player quads, and that mystery-data quads were involved) and two internal inconsistencies (28 pad bytes called accounted; docstring region 0x080aff44..0x080b81e3 vs emitted 0x080aee70..0x080b81eb) plus cite line drift — all four fixed at 86ecc36 and re-measured by the worker before the merge. KNOWN GAP, not a T65 regression: tools/inventory.py shells out to tools/rom_enemy_tables.py which hardcodes REPO/reference/bn6f, so the tool crashes in a fresh worktree whose submodule is empty (BN6F_REF is not enough). UNVERIFIED: per-battle scripted overrides of the Background byte (byte_203CA50 / event word through battleSettings_setBackground) were not measured; the art identity is structural. Models: worker-hyper hyper/glm-5.3-flash:high, verifier-hyper hyper/qwen3.8-flash:high. M1 formations line is now closed; M5 can buy rank recordings off this table.
**Result.** Pass 1+2 LANDED as f2ca1e2 (verify_rows guard set 7/7 identical pre/post from clean checkout; ROM byte-identical 5b46337a, zero src/; verifier-hyper c4d03425 CONFIRMED all claims, 7 fix items applied at dec03d1+256b8a5). Census on main: 1240 records / 84 lists / 1076 arrays / 0 mismatches; step-5 per-family NEGATIVE (family B zero ungated idx4/5/6; family A 15 but index-fetched). Ticket stays OPEN: end condition (all 1076 arrays identified, 0x07/0x08 backdrop bytes mapped to art) unmet; next pass is M5 work consuming this table. Note: reference/bn6f cites must be re-checked in the primary checkout, not a fresh worktree (submodule empty there).
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

### D9. Retire the journal: move the twenty cited facts into the code that relies on them  *(DONE -- 2026-09-17, 13 TRANSFER.md sections migrated to docs/provenance.md)*

**Result.** 13 TRANSFER.md sections migrated to docs/provenance.md; 33 citations across 16 files repointed at #<id>; dangling TRANSFER.md 1270 = line range within section 7bl (lines 1272-1275, gauge-stripe flow defect). harness identical pre/post (mettaur 0/0/70/41734, field 0/0/40/1139, opening 0/0/40/86591, cursor 1/1/170/186279); docs_check no new finding; TRANSFER.md body untouched. verify_rows PASS reproduced from clean checkout on wt/d9-provenance=b939e28; landed as ee7dca2. Verifier not needed (docs-only, rows identical to HEAD). Worker-minimax model MiniMax-M3, child cost: see subagent meta.
**Why.** `TRANSFER.md` is 2,897 lines of the first phase's journal that no agent may read whole, yet twenty-odd comments in `tools/` and `src/` cite it for the provenance of a number ("eBGScrollCBCounters read 0/0, TRANSFER.md 7aw"; "what makes the battle conclude, TRANSFER.md section 3"). `python3 tools/transfer.py --cited` lists every cited section, which file cites it, and one heading each; one citation (`TRANSFER.md 1270`, in tools/allowlist.py) names a section that does not exist. A citation a worker cannot cheaply resolve costs turns, and a dangling one is worse. Milestone M2 (the tooling the engine core is measured with): no engine change.
**Files.** docs/provenance.md (new), tools/allowlist.py, tools/harness.py, tools/states.py, tools/patch_sterile.py, tools/scoreboard.py, tools/chip_compare.py, src/*.rs (comment lines only), AGENTS.md and AGENT_GUIDE.md (the rule, once the citations are gone).
**Do.** 1. `python3 tools/transfer.py --cited` for the list; for each, read that section with `tools/transfer.py <id>` and write the fact it carries, in two or three sentences with its measurement, into `docs/provenance.md` under a heading that keeps the old id as an anchor (`## 7aw — a save state at a battle's first frame`). 2. Repoint every citation at `docs/provenance.md#<id>`. 3. Resolve the dangling `TRANSFER.md 1270` citation: find what allowlist.py's gauge-stripe entry actually rests on, or mark it unproven. 4. Leave TRANSFER.md in place, untouched, with a line at the top saying the load-bearing facts now live in docs/provenance.md.
**Rules.** Comments and docs only: no behaviour change, and the .gba may differ only by panic-line bytes. Do not delete or edit TRANSFER.md's body.
**Acceptance.** `grep -rn 'TRANSFER' tools/ src/ | grep -v transfer.py` returns nothing but the new pointer; `python3 tools/docs_check.py` reports no dangling citation; verify_rows PASS on mettaur, field, opening, cursor identical to HEAD.
**Measure and report.** The harness lines before and after, the count of citations moved, and the answer to the dangling one.
**Coordinator:** a docs ticket; no verifier needed when verify_rows is identical.

- T66 PARTIAL -- Replace the fitted POST_FLINCH_FRAMES shadow with the measured Timer hold (M2, model quality). Acceptance met in full, but UNMERGED: land.sh refuses while main's checkout carries foreign uncommitted edits, and by now that is three file
### T67. Attribute the PAUSED+Start@10 Timer tail -- which player-slot writer decrements Timer after a flinch? (M2, model audit)  *(DONE -- 2026-09-17, PAUSED+Start@10 9..0 Timer tail ATTRIBUTED [ticket's whole acceptance]: the flinch exit zeroes CurPhaseAndPhas)*

**Result.** PAUSED+Start@10 9..0 Timer tail ATTRIBUTED (ticket's whole acceptance): the flinch exit zeroes CurPhaseAndPhaseInitialized (asm00_2.s:18365-18366), the next playerAI_update dispatch through JumpTable80EA7B0 (asm31.s:107419+, all 25 slots playerAI_sub_80F0354+1) arms the phase handler which stores Timer=0xa (asm31.s:118977-118978) and decrements per dispatch (:118985-118987, store PC 0x080F03A4) until CurPhase=4 (store at :118991) — T66's census missed it by attributing every asm31 Timer store to non-player objects. Tail reproduces on the PAUSED route canon side: +0x20 = 0x16..0x00 frames 114..136, 0xffff underflow 137, 9..0 frames 138..147. Step 2b NEGATIVE: battle_full canon does NOT fire the tail — sentinel holds 0xffff canon frames 303..339+, gate unidentified, recorded explicitly in docs/coverage/battle_full.md with candidate early-outs (AIData+0x44 &0x8600/&0x80000, asm31.s:107357-107447). Model: fitted POST_FLINCH_FRAMES=11 replaced by derived PHASE_ARM_FRAMES=10+SENTINEL_FRAMES=1+TIMER_SENTINEL (provenance: derived, cites checked); exports unchanged. LANDED as 2d7ce09: verify_rows PASS reproduced from clean checkout (wave/window/opening/chip-cannon/metpaur/windowclose 0/0, cursor 1/1/170/186279 known tear, ROM byte-identical to main 5b46337a); mm_timer battle_full 270/540 and mettaur 70/70 unchanged. Verifier-zai (zai/glm-5.3-flash:high, mission 748df7a5) CONFIRMED all 3 claims; one cite imprecision (completion store is 118991 not 118989-118990, semantics right) and the live watch capture re-run left UNCHECKED (budget; static chain exact). Unverified: which gate blocks phase init in battle_full; f139+ lr=0x0801E011 anomaly; --watch-write lossiness (all in worklog/T67.md). Workers: worker-zai (zai/glm-5.3-flash:high), 4 commits.
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

### D10. Name the disassembly's unnamed struct fields from the evidence we already hold  *(DONE -- 2026-09-17, 13 of 478 Unk_<offset> fields named in reference/bn6f disassembly [e.g)*

**Result.** 13 of 478 Unk_<offset> fields named in reference/bn6f disassembly (e.g. oAIData_Unk_68->BusterBarrelPtr from battle.rs:157, oAIState_Unk_00->DecideState from objects.rs:243, oObjectSprite_Unk_00->CurAnim from spr.rs:427, oChatbox_Unk_05->CbStackDepth from script.rs:1225). 6,328 use sites renamed; 465 left Unk_ (no sentence in evidence). ROM rebuilds to sha1 0676ecd4d58a976af3346caebb44b9b6489ad099 (identical, baseline and after). reference/bn6f submodule bumped to 4ca08bf6; 2,081 .c files in decomp/ now show 7,490 named field references. verify_rows PASS on 8 rows (mettaur 0/0/70/41734, field 0/0/40/1139, opening 0/0/40/86591, cursor 1/1/170/186279, wave 0/0/90/3840, window 0/0/16/81056, chip-cannon 0/0/40/9505, windowclose 0/0/40/207166); docs_check unchanged. Verifier not needed (sha1 gate). Worker-minimax cost /bin/bash.4363.
**Why.** The disassembly declares 1,058 struct fields and 479 are still `Unk_<offset>`. Our own work already knows what a number of them are: source comments and `// bn` notes name `oAIData_Unk_68`, `oAIData_Unk_54`, `oBattleObject_Unk_*` and others in passing, and 34 source comments reference one unnamed field alone. Those names never reach `reference/bn6f/include/structs/*.inc`, so the disassembly, and the decompiled C generated from its types (`tools/csrc.py`, 47,460 named field accesses today), keep calling them `Unk_54` and every later reader re-derives them. The user (2026-09-17) lifted the read-only rule: the disassembly may be improved as long as it still builds the identical ROM. Milestone M2 (the tooling the engine core is read with).
**Files.** tools/field_names.py (new), reference/bn6f/include/structs/*.inc, reference/bn6f/include/rom_structs/*.inc, reference/bn6f/asm/*.s and data/*.s (only the `o<Struct>_Unk_*` uses a rename moves), reference/bn6f/docs/renames.md, docs/worklog/D10.md.
**Do.** 1. Collect the evidence: grep `src/*.rs`, `reference/bn6f/asm/*.s` `// bn` notes, `docs/coverage/*.md` and `docs/recon/*.md` for text that states what an `Unk_` field is, and emit a table of (struct, offset, proposed name, the sentence that says so, where it came from). 2. Propose a name only where a sentence states the role outright; hedged or inferred ones stay unnamed and are listed. 3. Apply each rename across the whole disassembly (definition and every use), keeping the offset comment, and append the old-to-new pair to docs/renames.md with its evidence. 4. Rebuild: `make -j$(nproc)` in reference/bn6f must produce bn6f.gba with sha1 0676ecd4d58a976af3346caebb44b9b6489ad099. A mismatch or an assembler error reverts the whole pass. 5. Re-apply the types so the C follows: `bash tools/retype_if_stale.sh --force`, and report the change in named field accesses.
**Rules.** No behaviour change anywhere: the ROM is byte-identical or the pass is void. Never invent a name; a field whose role is guessed stays `Unk_`. Do not touch this repo's src/.
**Acceptance.** The ROM rebuilds to its sha1; every renamed field's uses moved with it (no `Unk_` left dangling for a renamed offset); docs/renames.md lists each with evidence; the decompiled C shows the new names; `python3 tools/docs_check.py` still clean.
**Measure and report.** How many fields were named of the 479, how many were left for lack of evidence, the sha1 before and after, and the named-field-access count in decomp/ before and after.
**Coordinator:** a tooling ticket; the sha1 build is the gate, so no verifier pass is needed when it matches.

### T68. M2: what ends canon's Mettaur appear-phase at k=17 — the enemy CurAction store table, then the one cited edge  *(OPEN -- 2026-09-17)*

**Why.** battle_full's trace is 1370 divergent field-frames (T63 step 1a, oracle on 56679e5: mm_state_action 76/540 first k=250, mm_anim 78/540 k=251, mm_timer 270/540 k=269, **enemy_state_action 458/540 first k=17, enemy_anim 474/540 first k=21**, rng_cadence 14/540). Both enemy fields — 932 of those 1370 — start at the same place: at k=0 both sides read action 0x10, canon writes 0x08 at k=17 and ours holds 0x10. The ported decide routine cannot own that edge: `docs/coverage/battle_full.md` ranks 328/329 (`sub_8109FD6`, `sub_810A004`) first execute at **frame 437**, and rank 464 `sub_8109CE6` (T50's 0x0A hop executor) runs 69 times from **frame 438**. So the k=17 store belongs to the appear/spawn path, which no ticket has ever read from canon's own write log. Milestone **M2**.

**New evidence.** T53 (NEGATIVE) ported the second *decide* arm and it never fired because "rust's mettaur sits in Action::Appearing" — the appear phase is the un-ported part, not the decide part. T67 (DONE, landed 2d7ce09) landed the method this ticket needs and the trap: `--watch-write` is LOSSY (14 of ~35 writes logged), so attribution comes from the write PCs while the *values* come from `--watch` bins; and T63 (NEGATIVE) proved the same store-table technique on the player object (`0x0203a9b8/:b9/:c0/:d0`, `-o "WP frame="` to grep past glued log lines). Neither measurement was ever taken on the enemy object.

**Files.** src/objects.rs (MettaurEntry think/spawn arms), src/ai.rs, docs/coverage/battle_full.md, docs/worklog/T68.md. **NOT** src/actor.rs or tools/harness.py (T64's), **NOT** tools/states.py or src/fixture.rs (no fixture change: battle_full's script and pokes stay as landed), no allowlist, reference/bn6f read-only.

**Do.** 1. Baseline, no edit: `python3 tools/oracle.py battle_full --both` → all 13 fields' first divergence + counts (expect the T63 table above) and the 13-field sum; ROM sha256 via `python3 tools/gbafix.py $CARGO_TARGET_DIR/thumbv4t-none-eabi/release/bn <out>.gba`. **measurement.**
2. One canon capture of battle_full's own route, 540 frames, `--watch-write` on the enemy object's CurState/CurAction u16 **and** a `--watch` value bin beside it; derive the enemy base first by reading `[base+0x54]` (CollisionDataPtr) as T64 did on this scene's family — report the address you used. Report every store: frame, old→new, PC, LR, k=frame−11, over k=0..120. **measurement.**
3. Name the k=17 writer: `python3 tools/csrc.py <PC>` + the asm `file:line`; state the predicate that ends the appear phase and what writes 0x08, with its bit/flag reads. If the store is not from the 0x0A/0x10 family, say who it is. **measurement.**
4. Classify the 458: cross-correlate the two enemy_state_action series over the 540 exported frames at every lag 0..60 (trace.py's exported table.json holds the decimals) → best lag + its match count. ≥300/540 at one lag ⇒ a single phase offset, name its size. **measurement.**
5. Port that one edge (the cited predicate, never a frame count) into the MettaurEntry spawn arm; re-run step 1 and the guard set. **code change + measurement.**

**Rules.** No fitted counts and no re-alignment to the lower score; first divergence may not move earlier than k=17. `reference/bn6f` from `/home/box/Code/bn/reference/bn6f` (a fresh worktree's submodule is empty — T65's erratum). ≤5 captures, tool budget ≤80, one harness command at a time.

**Acceptance.** Trace target: field `enemy_state_action` as exported by tools/oracle.py on battle_full, frames 540, **divergent count 458 → ≤330** and `enemy_anim` 474 → ≤340, first divergence still ≥ k=17; the k=17 store PC named with its routine cite; the lag table reported either way; verify_rows on `wave,window,opening,chip-cannon,mettaur,cursor,windowclose` identical as the absolute veto (cursor 1/1/170/186279, total ≤186300). A NEGATIVE that carries the full k=0..120 store table, the lag table, and the named next lever (with a match rate below 300/540 at every lag, "not a phase offset" is the result) closes it.

**Measure and report.** row: battle_full (trace) + the guard rows; frames 540/70/170. Before/after per field (enemy_state_action, enemy_anim, sum 1370), the store table, the lag table, both ROM sha256+size, fitted count; commit; one line of mechanism; one line of what is unverified.

**Coordinator:** dispatch alone or beside T69 (files disjoint). Free tier: verify_rows + re-run oracle.py yourself for the two numbers. Verifier for step 3's attribution and step 4's lag claim — the next two M2 tickets are chosen by them. ≤$0.25 expected, ≤$0.55 cap. Advances **M2**.

---

### T69. M3: finish BLIND — move the render gate to the object's whole OAM commit so the blind row reads 0/0  *(OPEN -- 2026-09-17)*

**Why.** T64 (PARTIAL, branch `wt/t64`, tip 9f1ce9a, kept unmerged) measured canon's cross-alliance BLIND arm and ported it, and left one number: canon's player-side poke (`40:0x0203852c:0x2000` + `40:0x02038510:0xffff`) hides the Mettaur **whole** — 72,194 px over 90 frames, first divergence k=1 (capture 41), region her box x151-202 y68-120 — while our poked-vs-unpoked is 37,906 px: our gate hides ~52%, residual 308-396 px/frame inside her own box. Mechanism named in its worklog: canon's arm clears `OBJECT_FLAG_VISIBLE` on the **header** and the sprite layer drops the entire object, whereas our early-out is inside `Actor::show` and skips only `show_with_underlay`, so a second commit path survives. M3 is still "not started" in docs/SCOPE.md; this is the shortest path to its first pixel-parity rule. Milestone **M3**.

**New evidence.** T64's own measurements, made after T60's close: the two poke addresses confirmed live (`[0x0203a9b0+0x54]` = 0x020384f0 → ObjectFlags1 0x0203852c, BlindTimer 0x02038510), the arm split (0x100 early-out asm00_2.s:16831-16834; the 0x202 blink at :16839-16841, which corrects our stale INVIS cite; the 0x2000 cross-alliance clear at :16846-16870; arm D measured pixel-neutral and omitted), and the LTO trap (`#[no_mangle] BLIND_POKE_MAILBOX` at 0x020002fc must be read through `core::hint::black_box` or fat LTO folds the gate to 0).

**Files.** src/actor.rs, src/battle.rs (the enemy draw/commit path only), tools/harness.py (**only** the blind row's mailbox literal), docs/coverage/statuses.md, docs/worklog/T69.md. **NOT** src/objects.rs or src/ai.rs (T68's), no AI change, no `tools/states.py`, no allowlist, reference/bn6f read-only.

**Do.** 1. `bash tools/worktree.sh t69`, merge `wt/t64`'s tip 9f1ce9a into your branch, rebuild, `nm` the mailbox and correct the literal if it moved. verify_rows on the guard set **plus** `blind`: expect blind FAILED 69987/1940/90/70487 and the guard rows exactly as published. **measurement.**
2. Name the survivors: our poked vs unpoked captures of the blind row's window, diffed with `tools/diffmask.py` over the 90 frames (total, worst, per-frame box), and list every place our draw commits an OBJ entry for one enemy per frame (shadow, underlay, the enemy loop in battle.rs). Say which ones the current gate does not reach. **measurement.**
3. Confirm the canon shape: at capture 41 vs 45 on the poked side, report how many of her OAM entries remain (T64's box, x151-202) — the claim to match is zero. **measurement.**
4. Port: lift the gate to the per-object commit site so a cleared visible flag suppresses **every** entry for that object, citing canon's own header-flag test in the object/sprite path (find the read of the header bit that skips the commit; asm00_2.s:16846-16870 only *clears* it). Keep the consts named (CollisionData.inc:16/:134/:145). **code change.**
5. Re-run: `blind` 0/0/90 with the frame-shift negative non-zero; ours poked-vs-unpoked vs canon's 72,194 over the same window, both totals; guard set. **measurement.**

**Rules.** Canon never changes; the poke is the fixture (F5b's route), never a patch and never a timer tuned to the picture. No second status bit, no widening of any existing row's frames/align/region/negative, no allowlist edit. Any guard row that stops reading 0, or cursor > 1/1/170/186279 on the same ROM layout, ⇒ unmerged. ≤6 captures, tool budget ≤70.

**Acceptance.** `blind` = 0/0/90 with a non-blind negative; our poked-vs-unpoked total **equal to 72,194** over the same 90 frames (report both numbers and the sha256+size of both ROMs); the gate sited at a named commit path with its cite, OBJECT_FLAGS_BLIND/BlindTimer/ObjectFlags1 named; the stale INVIS_HIDE_BIT cite corrected in the diff; verify_rows identical on `wave,window,opening,chip-cannon,mettaur,cursor,windowclose`. Report that SCOPE's statuses 0/69 does not move (that line is T18's walk): M3 moves from "not started" to one rule at pixel parity.

**Measure and report.** rows: blind, wave, window, opening, chip-cannon, mettaur, cursor, windowclose; frames 90/90/16/40/40/70/170/40. Before/after totals, worst and negatives, the two poked addresses and values, step 2's survivor list, step 3's entry counts, fitted count; commit; one line of mechanism; one line of what is unverified.

**Coordinator:** may run beside T68 (files disjoint); never beside anything owning src/actor.rs or tools/harness.py. Free tier: verify_rows on the guard set + blind from a clean checkout. A verifier for step 2's "which commit paths survive" and step 4's cite — every later status ticket copies this route. ≤$0.20 expected, ≤$0.45 cap. Advances **M3**.

---

### T70. M1: the Background byte's art mapping — close the backdrops GAP out of the ROM's own record stream  *(OPEN -- 2026-09-17)*

**Why.** docs/SCOPE.md's M1 backdrops line reads `0 / 3` with the byte→art mapping a **GAP** ("no table or arithmetic offset found, trail in note"), and T65's landed census (pass 1+2, f2ca1e2) put the last number on it: over all 1240 BattleSettings records the Background byte (`include/rom_structs/BattleSettings.inc:10`, +0x4; writer `battleSettings_setBackground` asm/asm03_0.s:14591-14593) reads 0xff ×1047, **0x07 ×192, 0x08 ×1** (the singleton at 0x080aee70). M8 has one arena and cannot schedule a second until the byte names its art: T58 already proved the poked route fields a record (`0x02001b9c` = the chosen BattleSettings pointer from frame 0), so a distinct byte value is a reachable second arena with no new hand-played input. Also still open on T65: 1045 of its 1076 formation arrays contain a 0x00 quad id and are uninterpreted. Milestone **M1**, unblocking **M8**.

**New evidence.** T65's ROM walk, landed after that GAP was written: the 84-list / 1240-record census with 0 terminator mismatches, the per-list addresses, and the Background histogram; plus T22's result that the backdrop's *art content* is already data (`BattleBackdropGFXAnimScript_807FB98` dat20.s:148, 29 entries → 7 tile tables dat20.s:181-225, byte-exact against assets/backdrop.bin). What is missing is only the byte→script/map/palette link.

**Files.** tools/inventory.py (**only** `parse_backdrops`/`parse_formations` and their notes — `AS_DATA_FAMILIES` and its comment are frozen, T62's), docs/coverage/formations.md, docs/coverage/backdrops.md (new), docs/inventory/ (generated), docs/SCOPE.md (regenerated only), docs/worklog/T70.md. **NOT** src/, tools/harness.py, tools/states.py, tools/trace.py, tools/oracle.py, tools/allowlist.py, assets/; reference/bn6f read-only.

**Do.** 1. Baseline: `python3 tools/inventory.py`, quote the formations and backdrops lines; build and quote the ROM sha256+size from the gbafix path (src/ untouched). **measurement.**
2. Walk the byte's consumers: every read of the stage-pair word `byte_203CA50` and of `battleSettings_setBackground`'s argument in asm/asm03_0.s (T65's note names :14592/:14599), and report per reader what it does with 0xff vs 0x07 vs 0x08 — table index, arithmetic, or a branch. Give the `file:line` of the instruction that selects the art. **measurement.**
3. Name the art: for each of the three byte values, the tile/map/palette blobs it reaches, matched against T22's byte-exact tables and assets/backdrop.bin; say which backdrop each is in words (the default arena, and the two overrides). **measurement.**
4. One canon capture (≤1, budget's point: no second): load the `battlestart` route and poke the chosen record to one that carries a non-0xff byte (T65's list gives addresses), read the byte at `[0x02001b9c]+0x4` and the backdrop's BG1 tile base at k=5, report both sides' values. Skip with a stated reason if no reachable record with a non-0xff byte exists on that route. **measurement.**
5. Replace the GAP text with the measured mapping in `parse_backdrops`, regenerate SCOPE, and report the formations gap's new size: how many of the 1076 arrays are now interpreted and what the 0x00 quad id means (or does not). **tools change.**
6. Re-run step 1's two commands: the generator's lines and the ROM hash. **measurement.**

**Rules.** Zero src/ changes — a byte-identical ROM is the gate (T56: a −900 B tree moved cursor 5 px). No new state, row, fixture or allowlist change; no states.py edit. Every reference/bn6f cite re-checked in `/home/box/Code/bn/reference/bn6f` (a fresh worktree's submodule is empty — T65's erratum). The count may go down if the ROM says so; no inferred mapping — a byte whose art is only *guessed* stays a GAP with the trail rewritten. Tool budget ≤40.

**Acceptance.** ROM sha256 identical before and after and `git diff --name-only` = the named files; the generated M1 backdrops line moves from `0 / 3` with the selecting instruction cited at `file:line` for each of the three byte values, **or** a NEGATIVE that names every reader walked and says in one line why the byte cannot select art; ≥1 record address per distinct non-0xff byte with the poked route that fields it (step 4's two values reported or the reason it is unreachable); the 0x00-quad count stated against T65's 1045.

**Measure and report.** rows: none (no ROM change). The ROM sha256 (before = after) and build command, the backdrops and formations lines before/after, the per-byte reader table, step 4's two reads, `git diff --stat`; commit; one line of mechanism (which pointer chain the mapping followed); one line of what is unverified (no scenario, no port, no row).

**Coordinator:** dispatch when tools/inventory.py and docs/SCOPE.md are free — it owns both, so never beside T65's next pass or any ticket naming inventory.py; disjoint from T68/T69 so it may pair with either. Free tier: run `python3 tools/inventory.py` yourself and diff the generated part. A verifier for step 2's selecting-instruction claim and step 3's blob identity, since every arena row after this one buys them. ≤$0.12 expected, ≤$0.25 cap. Advances **M1**, unblocks **M8**.

### T71. M2: PA recognition out of the ROM's own recipe tables — walk off_802BCB0/off_802BC60, then one PA the custom screen recognizes as data  *(OPEN -- 2026-09-17)*

**Why.** docs/SCOPE.md's M2 line names "chip selection rules (codes, Regular, Tag, **PA recognition**, folder draw/reshuffle)", and M4's last row — Program Advances — reads **0 / 63**: nothing in our engine touches a PA. The source is FOUND (M1's program-advances line): `asm/asm03_0.s off_802BCB0 + off_802BC60` recipe-pointer tables, records laid out `[count][matcher][result u16][chip,code]*n`. So canon's recognition rule is data and ours is absent; the 63 recipes have never been read. Milestone **M2** (chip selection rules), unblocks **M4**'s PA row.

**New evidence.** T58 (PARTIAL) proved the poked route fields a chosen record from frame 0 (`0x02001b9c` = the BattleSettings pointer), so fixture-side data can be delivered without new content. T7r (PARTIAL, landed) put scripted L/A input into battle_full's fixture — a custom-screen sequence can be driven without a hand-played log, so T20's blocker does not bind here. F5b (DONE) is the working chip-window press route. T65 (DONE) landed the record-stream walking method (1240 records, 0 terminator mismatches).

**Files.** `src/custom.rs` (the recognition walk), `src/deck.rs` (the folder's chip+code view it reads), `tools/states.py` + `tools/harness.py` (**one new row `pa_recog` only** — no existing row's frames/align/region/negative touched), `docs/coverage/chips.md`, `docs/worklog/T71.md`. **NOT** `src/objects.rs`/`src/ai.rs` (T68's), **NOT** `src/actor.rs` or `src/battle.rs`'s draw path (T69's), **NOT** `tools/inventory.py` (T70's), no `src/fixture.rs`, no allowlist; `reference/bn6f` read-only.

**Do.** 1. Baseline, no edit: `python3 tools/inventory.py` → quote the program-advances line verbatim (expect `0 / 63`, state FOUND); build and quote the ROM sha256+size from `python3 tools/gbafix.py $CARGO_TARGET_DIR/thumbv4t-none-eabi/release/bn <out>.gba`. **measurement.**
2. Decode the recipe stream from the ROM itself: walk both pointers with the cited record layout and emit the full table (recipes found, each row's count, matcher byte, result chip u16, and its (chip,code) pairs), plus how many of ChipDataArr's 411 ids appear in ≥1 recipe. State the two pointer arrays' entry counts and whether they are 802BC60-then-802BCB0 or parallel. **measurement.**
3. Name canon's reader: grep both symbols across `reference/bn6f/asm/*.s`, and for the site that runs at the custom screen report its predicate in words (what it compares the folder's chip ids/codes against, the order it stops in) and the **store** of the recognized result — struct field, offset, `file:line`. **measurement.**
4. Make one PA reachable on a fixture: poke the folder to one recipe's (chip,code) set (states.py, `peeked` provenance), drive the window open with T7r-style scripted input on the F5b route, capture canon, and report the frame the result field changes, its old→new value from the state trace, and the same on our side. **measurement.**
5. Port the walk into `src/custom.rs` so it reads the recipe records (runtime table or generated per-record const table with cites — no per-PA `match`), add the `pa_recog` row plus a negative fixture that must fail, and re-run the row's trace and pixels. **code change + measurement.**
6. Re-run step 1's two commands. **measurement.**

**Rules.** Table-driven or it does not land; no fitted frame counts, no re-alignment to the lower score, no allowlist entry, canon never changes (the poke is the fixture, F5b's rule). Do not touch the folder *draw/reshuffle* rules — T59 closed that. Fresh worktrees have an EMPTY `reference/bn6f` submodule: read it from `/home/box/Code/bn/reference/bn6f` (T65's erratum). ≤5 captures, tool budget ≤80, one harness command at a time.

**Acceptance.** Trace target on the new `pa_recog` scenario: the PA-result field's first divergence **none inside the row's window** (report the window in frames) and pixels **0/0/N** with a non-blind negative; `python3 tools/inventory.py`'s program-advances line moves off `0 / 63` by exactly the number of recipes the runtime now consumes from the table (before/after lines quoted); guard set `wave,window,opening,chip-cannon,mettaur,windowclose` identical and `cursor` ≤1/1/170/186300 (T56's named spread: HEAD 86a5b18 = 1/1/170/186279, ROM sha256 5b46337aa27da9ca881f2321fe1e210f54717285b4dfa5256c1680bac4b985ef, 584296 B). A NEGATIVE that lands step 2's complete recipe table and step 3's reader with `file:line`, and says which predicate is unreachable on a poked fixture, closes it and makes the execution ticket writable.

**Measure and report.** rows: pa_recog (new) + the guard set; frames N/90/70/170. Before/after pixel totals, worst, region, the recipe count from step 2, the result field's old→new frame, both ROM sha256+size, fitted count, commit; one line of mechanism; one line of what is unverified.

**Coordinator:** dispatch alone — it owns `tools/harness.py` and `tools/states.py`, so never beside T69 (harness.py) and not beside T70's next pass if that touches states. Free tier: verify_rows on the new row plus the guard set from a clean checkout, and re-run `tools/inventory.py` yourself. Verifier for step 2's parse and step 3's reader identification — every later PA ticket buys them. ≤$0.30 expected, ≤$0.70 cap. Advances **M2**, then **M4**.

---

### T72. M3: the second status bit end to end — CONFUSED, from T64's flag-word chain to its cited reader and timer  *(OPEN -- 2026-09-17)*

**Why.** SCOPE's M3 still reads "not started" and the statuses line is **0 / 69**. T18's corrected per-bit census measured the whole status surface — per-bit stores 39/69 (flags1 26/32, flags2 13/32, DAMAGE 0/5), per-bit readers 37/69 — and named the only three bits with a per-bit reader as the M3 candidates: **CONFUSED `asm/asm00_2.s:1894-1897`**, BLIND `asm/asm00_2.s:16861-16863`, IMMOBILIZED `asm/asm31.s:171386-171390`. BLIND is T60/T64/T69's bit; CONFUSED is the next one, with a reader already located and no ticket against it. Milestone **M3**.

**New evidence.** T60 (PARTIAL) and T64 (PARTIAL, tip 9f1ce9a) made this measurable after my earlier attempt had no address: the scene's object flag words are derived, not guessed — `[0x0203a9b0+0x54]` (CollisionDataPtr) = `0x020384f0` → `ObjectFlags1 0x0203852c`, `BlindTimer 0x02038510`, poked as `40:<addr>:<mask>` on the F5b route; the arm split is `0x100` early-out `asm00_2.s:16831-16834`, `0x202` blink `:16839-16841`, `0x2000` cross-alliance clear `:16846-16870`; and T64's LTO trap — a `#[no_mangle]` poke mailbox (0x020002fc) must be read through `core::hint::black_box` or fat LTO folds the gate to 0. T67 (DONE, 2d7ce09) landed the write-attribution method and its trap: `--watch-write` is **lossy** (14 of ~35 writes), so PCs come from watch-write and values from `--watch` bins.

**Files.** `src/ai.rs`, `src/objects.rs` (the confused arm + timer tick), `src/battle.rs` (**status-tick lines only**), `tools/states.py` + `tools/harness.py` (**one new row `confused` only**), `docs/coverage/statuses.md`, `docs/worklog/T72.md`. **NOT** `src/actor.rs` (T69's), **NOT** `tools/inventory.py` (T70's), no `src/fixture.rs`, no allowlist, no existing row's config; `reference/bn6f` read-only.

**Do.** 1. Baseline, no edit: read `asm/asm00_2.s:1894-1897` in `/home/box/Code/bn/reference/bn6f` and name the struct, the field and the exact bit mask CONFUSED's reader tests; then grep that mask's symbol tree-wide and report the writer/reader site counts (this is the same per-bit walk T18 counted 39/69 and 37/69 against). **measurement.**
2. Find it live on the blind row's route: derive the enemy object's flag words by T64's `[obj+0x54]` chain (report the addresses you used), poke CONFUSED, capture 90 frames of canon, and report the flag word + timer word per frame plus the pixel effect sized with `tools/diffmask.py` (total, worst, box, first divergent k). **measurement.**
3. Name the mechanism: which routine the cited reader sits in, what the confused arm changes (movement direction, action choice, animation), and the timer's **writer and initial length** from the disassembly — report the `file:line` for each, never a fitted count. Classify how many of the row's frames the effect covers. **measurement.**
4. Port: the reader's arm into the enemy AI and the timer tick, with the mask and timer named as consts carrying `// provenance:` cites (canon: the flags field and the routine); keep the `black_box` mailbox shape T64 proved necessary. **code change.**
5. Re-run: the new `confused` row at 0/0/90 with its negative fixture non-zero; then the guard set. **measurement.**

**Rules.** One status bit per ticket. The poke is the fixture, never a canon patch, and no timer value tuned to the picture; no second bit, no row widening, no allowlist edit. Any guard row that stops reading 0, or `cursor` > 1/1/170/186279-±1px on the same ROM layout as T56's measurement, ⇒ unmerged. Fresh worktree's `reference/bn6f` is empty — read `/home/box/Code/bn/reference/bn6f`. ≤5 captures, tool budget ≤70, one harness command at a time.

**Acceptance.** Content ticket, so: the item's own scene at zero — `confused` = **0/0/90** with a non-blind negative; the state trace on that scenario shows **no divergence** in the fields CONFUSED moves (report which: state_action/anim/timer) within the window; the bit's mask, its reader, its writer and its timer length each carried a `file:line`; verify_rows identical on `wave,window,opening,chip-cannon,mettaur,cursor,windowclose,blind`. Report explicitly that SCOPE's statuses `0 / 69` line does not move (that count is T18's walk) — M3 moves from "not started" to a **second** rule at pixel parity. A NEGATIVE that lands step 1's site census and step 2's per-frame values, and names why the reader's arm is pixel-invisible on this route, closes it.

**Measure and report.** rows: confused, blind, wave, window, opening, chip-cannon, mettaur, cursor, windowclose; frames 90/90/90/16/40/40/70/170/40. Before/after totals, worst, region, the poked addresses and values, the timer's cited length, fitted count, commit; one line of mechanism; one line of what is unverified.

**Coordinator:** owns `src/ai.rs`/`src/objects.rs` with T68 and `tools/harness.py` with T69/T71 — dispatch **after** T68's verdict, and build this branch on top of `wt/t69`'s tip once BLIND lands (its flag chain is this ticket's premise). Free tier: verify_rows on the new row + guard set. Verifier for step 1's bit identity and step 3's timer source — later status bits copy both. ≤$0.20 expected, ≤$0.45 cap. Advances **M3**.

---

### T73. M4: close one whole chip family onto the record — grow AS_DATA_FAMILIES from T57's census, delete that arm's `match chip.id`  *(OPEN -- 2026-09-17)*

**Why.** M1's chips line is **43 / 411** and M4's data status is exactly three arms: family **0x13** (Sword…BambSwrd, Muramasa, T17), family **0x15** subfamily **0x04** (Barrier, Barr100, Barr200, T48) and **0x21** (AirShot id 4, T52) — `AS_DATA_FAMILIES = {0x13, 0x15, 0x21}` in `tools/inventory.py`, keyed to `ChipDataArr_8021DA8` (`data/ChipDataArr.s:2`, 411 × `chip_data_struct`, stride **0x2c**, `include/rom_structs/ChipData.inc`), with `AttackPower` at **+0x1a**. 29 further chips are pixel-verified only *through our own code*, and T57's landed census holds the 43-row record-vs-id table **plus the AttackFamily census of the other 368 ids** — so the next family to convert is already named by measurement, not by guesswork. Milestone **M4**, moving **M1**.

**New evidence.** T56 (NEGATIVE) settled the veto that rejected three earlier attempts: `cursor`'s movement is a **code-size** artifact — HEAD 86a5b18 (ROM sha256 5b46337a…85ef, 584296 B) measures 1/1/170/**186279** — so a ≤1px/1-frame cursor move is noise and the size must be reported. T46 (DONE, 85f021c) and T48 (DONE, 079531c) proved a family can be converted end to end after a NEGATIVE on a *different* family, and T61 (PARTIAL) put AreaGrab (163) and Invisibl (177) onto the Barrier record. So the objective is not closed; only the Cannon (T38/T51/T54) and Recov/Barrier-amount (T28/T34) premises failed.

**Files.** `src/chips.rs`, `src/shot.rs` (the converted arm only), `tools/inventory.py` (**`AS_DATA_FAMILIES` and its provenance comment only** — no parser rewrites, that is T70's file region), `docs/SCOPE.md` (regenerated only), `docs/coverage/chips.md`, `docs/worklog/T73.md`. **NOT** `src/actor.rs`, `src/ai.rs`, `src/objects.rs`, `src/custom.rs`, `src/deck.rs`, `tools/harness.py`, `tools/states.py`, `tools/trace.py`, `tools/oracle.py`, `tools/allowlist.py`, `assets/`; `reference/bn6f` read-only.

**Do.** 1. Baseline: `python3 tools/inventory.py` → quote the chips line and the verified id list; `python3 tools/harness.py --only <each row of the candidate family>` → each row's total/worst/frames; build and quote ROM sha256 **and size**. **measurement.**
2. Pick the target from T57's census, not from taste: report the families (id count, subfamily spread) among the still-`match chip.id` ids, and choose the largest family whose every id is explained by record bytes the interpreters already carry (power +0x1a, element, AttackFamily/SubFamily, amount). For each id in it, write the sentence "id N's behaviour = record bytes …" or exclude it with the byte it needs that the record does not hold. **measurement.**
3. Port the chosen arm to read the record for every id in it, deleting that arm's `match chip.id` sites (report the count deleted), and keep any residue in a named const with a `// provenance:` cite. Rebuild; quote ROM sha256 **and size** again. **code change + measurement.**
4. Re-run step 1's rows one by one: every converted id's row still **0/0** with its negative fixture non-zero, and its trace (where the row is traced) with no divergence inside the window. **measurement.**
5. Add the family to `AS_DATA_FAMILIES` with the cite for why *every* id in it now reads the record, regenerate `python3 tools/inventory.py`, and quote the chips line before/after. **tools change + measurement.**
6. Guard set: `wave,window,opening,chip-cannon,mettaur,cursor,windowclose` plus every other `chip-*` row. **measurement.**

**Rules.** A family joins `AS_DATA_FAMILIES` only when *all* its ids are record-driven — a partial family is a false claim, keep it out of the set and say so. No fitted constants, no allowlist, no row widening, no states/harness config change. `cursor` may move ≤1 frame/≤1 px; anything above 1/1/170/186300, or a guard row off zero, ⇒ unmerged, and the ROM **size** delta is part of that report (T56). Fresh worktree's submodule is empty — read `/home/box/Code/bn/reference/bn6f`. ≤4 captures, tool budget ≤60.

**Acceptance.** Content ticket: each converted chip's own scene and trace at **0** — every id in the chosen family reads 0/0 on its own `chip-*` row with a non-zero negative, and the family's whole `match chip.id` arm is gone (report `grep -c` before/after on the arm). `python3 tools/inventory.py`'s chips line moves from `43 / 411` to `43+N / 411` where N = the ids in the family (report N and the id list), and the guard set is identical. If step 2 finds **no** family whose every id is record-explainable, that census — per-id, byte by byte, with the blocking byte named — is the result and closes the ticket as a precise negative.

**Measure and report.** rows: the family's own `chip-*` rows + the guard set; frames per row as published. Before/after row totals and worst, N ids converted, `match chip.id` sites deleted, ROM sha256+size before/after, the inventory chips line before/after, fitted count, commit; one line of mechanism; one line of what is unverified.

**Coordinator:** pairs with T68 or T69 (files disjoint from both); never beside T70 — both touch `tools/inventory.py`. Free tier: verify_rows on every converted row plus the guard set, and re-run `tools/inventory.py` yourself. Verifier only for step 2's per-id byte claims, since that table picks the next two families. ≤$0.15 expected, ≤$0.35 cap. Advances **M4**/**M1**.

