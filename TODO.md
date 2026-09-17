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
### T141. The cursor seam class on wt/t138's binary: does ANY pad value put its tear back in class, or is the pad exhausted?  *(NEGATIVE -- 2026-09-17, Pad sweep 11..25 on wt/t138 layout [e671af6]: SEAM_PHASE_PAD_ITERS 13 and 21 both restore cursor to main's exa)*

**Result.** Pad sweep 11..25 on wt/t138 layout (e671af6): SEAM_PHASE_PAD_ITERS 13 and 21 both restore cursor to main's exact line 1/1/170/186279 (pad alive, not exhausted); 15/15 11..25 sweep values measured. But no pad brings the whole guard set into class: field-bg1/2 totals are pad-coupled (4320@11,4800@13,1920@17,6720@19,5040@21,5520@25; main 3600) and field-bg3 is pad-invariant +44 (380263/405169 vs main 380219/405125) - the T135 merge re-rolled the field-bg artifact, so strict full-table-identical bar fails at every pad. Guard rows at pad 21 all identical to main (mettaur 0/0/70/41734, result 0/0/40/111839, super_armor 0/0/70/29640, wave 0/0/90/3840, chip-use 0/0/30/7768, tiles/gauge 0/0/8/12197, window 0/0/16/81056, windowclose 0/0/40/207166, opening 0/0/40/86591, popup 0/0/80/1288). Tear shape: V-curve too-few=tear/too-many=duplicated frames, seam-phase artifact not render divergence. Coordinator verify_rows PASS 15/15 (field-bg FAILED-vs-main lines match report numbers exactly). Branch wt/t138 kept unmerged at e671af6; worktree removed. Next: fix is T118's missing mid-frame-write scanline measurement or a policy call on the field-bg reroll class - both above this ticket.
**Result.** THE SIX-STAMP QUESTION IS ANSWERED WITH NUMBERS: the pad is NOT exhausted. MY OWN verify_rows of main right now (6bd5170): field-bg1 FAILED 3600/3600/40/174345, field-bg2 FAILED 3600/3600/40/3600, field-bg3 FAILED 380219/40/24906-as-worst/405125, cursor FAILED 1/1/170/186279 -- note main's field rows are 3600, NOT the 5280 this session has been quoting, because T135 LANDED (c5cab90, src/actor.rs +28, src/battle.rs +33, assets/megaman.bin 26662 -> 26854 B) and its layout change took the band from 22 rows to 15. THE SWEEP, on wt/t138's tip after merging that main in (so the layout is T138 + T140 + T135, 12 commits, tip e671af6): pad -> cursor total/worst/frames | negative = 13 -> 1/1/170 | 186279, 15 -> 55/49 | 186277, 17 -> 77/56 | 186350, 19 -> 68/67 | 186276, 21 -> 1/1/170 | 186279, 23 -> 321/280 | 186557, 25 (main's) -> 16241/3385/170 | 170163. TWO VALUES (13 and 21) reproduce main's exact line including the negative 186279, the plateau is NOT contiguous, and above them the failure mode changes character -- at 23/25 the tear becomes a DUPLICATED DISPLAY FRAME at every content-change frame (the overshoot arm of T111's V-bottom; the worker proved it frame-exactly: only 5 divergent frames of 170, period 30 = the blink period, rust showing post-blink content for two frames where canon shows it for one), which is why 16241 is not a new render divergence but the same artifact pushed too far. So cursor is absorbable on this layout and the wall is elsewhere. THE ELSEWHERE, and this is why the branch still cannot land: at the in-class pads the field-bg rows are NOT main's. field-bg1/bg2 at pad 21 read 5040/5040 against main's 3600/3600, and they step with the pad across the whole range the worker measured (4320@11, 4800@13, 1920@17, 6720@19, 5040@21, 5520@25 -- never 3600), while field-bg3 reads 380263 at every pad against main's 380219 (+44, pad-invariant, outside the +/-25 drift envelope). No SEAM_PHASE_PAD_ITERS in 11..25 gives cursor-in-class AND a byte-identical field table, so under AGENTS.md's no-surface-worse rule I am NOT landing wt/t138 at pad 21: the row this run bled for (super_armor 0/0/70, negative 29640, unchanged at pad 21) stays parked one step longer, and the ticket the band needs is now written (T142) because the band is the thing holding M3's first live NaviCust rule off main. ROM at the chosen pad: sha256 c5178b3a8fcd7c281e82edc40f661bbf51c9ab731c81be9b117c2233f8426820, 594028 B (+676 vs T140's 593352, -16 vs the pad-25 build of the same merge); fitted 16, derived 438, peeked 146. docs/coverage/cursor.md gained the dated sweep table, the class boundary and the verdict; docs/worklog/T141.md the full log. WHAT WAS NOT PROVEN, and the worker says so: pads below 11 and the even values in between are unmeasured, so an exact 3600 co-fit somewhere outside 11..25 is not strictly excluded -- and the +44 on field-bg3 is unattributed, which T142 must not confuse with the band. child ~$0.5.
**Why.** T140 got M3's super-armor row to **`super_armor` PASS 0/0/70, negative not blind 29640** with the compared window UNCHANGED, deleted a fitted constant on the way (`FLASH_FRAMES = 4` -> fitted 17 -> 16), wrote the `paused_superarmor` scenario into `tools/states.py`, and left every guard row byte-identical to main -- and the branch still cannot land because its binary layout moved the cursor tear from `1/1/170/186279` to **`26/25/170/186276`**. AGENTS.md forbids a landing that makes any surface worse, so I kept wt/t138 (tip 3e50994) unmerged. This is the run's recurring wall and it has now cost six tickets their landing (T119b, T122b, T128, T129, T134, T140), so the question needs an answer rather than another report: `SEAM_PHASE_PAD_ITERS` (`src/main.rs`, documented at `:309-322`, fitted to 17 in T111, re-fitted to 25 in T130 at commit 5ac9227) has been treated as the knob that absorbs layout shifts, but the evidence says it may not be a knob any more -- T132's verifier swept pads 29..35 on wt/t132's layout and got **29/28 at pad 29 with no pad in that range reaching <=1/1**, and T137 measured pad 17 and pad 25 as BYTE-IDENTICAL on all three field-bg rows. Either the pad still works on this layout, in which case wt/t138 lands with a re-fit, or the pad is exhausted, in which case the tear is a genuine render-timing divergence and every src-changing ticket from now on is unlandable until that is fixed -- a fact I need stated with numbers, not inferred from six PARTIAL stamps.

**Files.** `src/main.rs`'s `SEAM_PHASE_PAD_ITERS` VALUE ONLY (this ticket is the ticket that says so -- no other edit in that file, no other constant in it, and the pad doc comment's prose may gain one line recording which value was chosen and why), `docs/coverage/cursor.md` (append a dated section: the sweep table, the class boundary, and the verdict on whether the pad is exhausted), `docs/worklog/T141.md`. **NOT** `tools/harness.py` (any row's frames/align/pairing/negative, including `super_armor`'s, which T140 just set), `tools/states.py`, `src/actor.rs`, `src/battle.rs`, `src/backdrop.rs`, `src/fixture.rs` (wt/t138's port is FROZEN -- you change its pad, not its code), `tools/trace.py`'s judged set, `tools/allowlist.py`, `tools/patch_sterile.py`, canon, `reference/bn6f`, `assets/`.

**Do.** Work in the LIVE worktree `/tmp/bnwt/t138` (tip 3e50994, clean, it holds T138's port + T140's row, scenario and flash removal -- do NOT run `tools/worktree.sh`, and do NOT edit any file step 1 forbids). `git merge main` if it has moved. Commit each measured step on the branch; never merge.
1. Reproduce both endpoints with ONE capture pair each, and confirm your starting point: on your tip `cursor` should read `26/25/170/186276`; if it reads `1/1/170/186279` instead, main moved the layout under you and you re-measure everything else from the new tip. **measurement.**
2. Sweep the pad on this layout: the value in use now, plus at least 6 others bracketing the range that T130/T132 touched (I suggest 17, 21, 25, 27, 29, 33 plus the current value -- state the range you chose and why), one `cursor` isolated run per value, reported as a table of `pad -> total/worst/frames/negative`. This is the whole ticket's deliverable, so do it before anything expensive; each run is 1 capture pair. **measurement.**
3. If some value puts `cursor` at <=1/1/170: re-measure the 12-row guard set on THAT pad (`mettaur`, `result`, `super_armor`, `wave`, `chip-use`, `tiles`, `gauge`, `window`, `windowclose`, `opening`, `popup`, and the three `field-bg` rows as they stand -- `python3 tools/harness.py --list` for real names, `docs/coverage/rows.md` for the ones that never existed) and report whether the row that made this branch interesting still reads 0 there. If yes, the branch is land-ready and say so plainly. **measurement.**
4. If NO value does: write the negative properly -- the sweep table, the minimum total in the range, where the class boundary is, and whether the tear's SHAPE is even the seam artifact any more (does the divergent frame sit at the same capture, does the region move with the pad, is it the whole top band or a cursor sprite). Distinguish "no pad in this range" from "the pad cannot ever fix this" with evidence, because those two conclusions send me to completely different places. **measurement + doc.**
5. Record it in `docs/coverage/cursor.md` and name, in your report, the ROM sha256+size+delta of the pad you end on.

**Rules.** One number changes: `SEAM_PHASE_PAD_ITERS`. Never touch a row definition, never touch the port, never touch wt/t139's or any other branch, never edit canon. No capture beyond the sweep plus step 3's guard table -- budget them, <=14 total, tool budget <=70. Commit `docs/worklog/T141.md` with step 1's endpoints as your FIRST commit (eight workers on this queue have lost their later steps to the budget; your worklog is the deliverable if nothing else lands).

**Acceptance.** Either: a pad value that restores `cursor` to <=1/1/170 on wt/t138's layout with the guard set byte-identical to main's lines and `super_armor` still 0/0/70 -- at which point the whole branch (T138's port + T140's row and scenario + this re-fit) is land-ready and I land it; or a bounded NEGATIVE: a sweep table of >=7 values that shows no pad in the plausible range brings this layout into class, with the tear's shape characterised well enough that I can tell a seam-phase artifact from a real render-timing divergence.

**Measure and report.** rows: `cursor` (the full sweep table), then the 12-row guard set at the chosen pad; frames per row, totals, worsts, negatives, the pad value chosen and its before/after, ROM sha256+size+delta, commits; one line of mechanism; one line unverified.

**Coordinator:** this is the ONLY ticket allowed to edit `src/main.rs`, and only that constant; it lands nothing itself -- I re-run `verify_rows` on the tip and make the merge call. Free tier: the sweep plus the guard table. Verifier only if a pad is found and the landing hinges on the guard table. <=$0.35 expected, <=$0.70 cap. **Unblocks wt/t138's M3 landing, or retires the pad as a solution with numbers.**

---

### T155. M3's hole, second half: the moved object LEAVING the hole — the exit arm canon's flag word also drives  *(BLOCKED -- 2026-09-17, NOT ATTEMPTED - same queue-integrity finding as T157 [grep-checked there, recorded in its stamp]: the h2b ladd)*

**Result.** NOT ATTEMPTED - same queue-integrity finding as T157 (grep-checked there, recorded in its stamp): the h2b ladder's first rungs T152/T153/T154 were never admitted to TODO.md, no h2b scenario exists in tools/states.py, and T155's steps cite those rungs as predecessors. Re-dispatch refused until the ladder's first rung exists as a landed ticket or a new ticket builds it from the ROM.
**Why.** The goal's rule is "every rung must make the previous rung's mechanism do work it previously refused": T152's branch makes the sterile box's item *register a hit*; nothing makes an object that has been moved *leave the hole it fell into*, which is the rung the goal names as "the moved object leaving the hole". The state is already there — `inventory.py`'s panel census records that type 0 is "skipped by every reader; flag word is the only one with bit 0x8000", and `_object_updatePanelParameters` (asm/asm38.s:4213-4219) re-ORs the word every frame, so an exit is a re-evaluation of the same bit under a different mask, not a new event. T130 proved the same shape is portable and landable: `object_panel_setPoison`'s masked template `(Flags & ~0x3f5f) | 0x114` on the type-4 write landed at fe9b8f3 with verify_rows PASS 9/9 — a mask read, not a fitted value. Advances **M3** ("flinch/knockback/drag", "every panel type and effect").

**Files.** `src/field.rs`, `src/actor.rs`, `tools/states.py` (scenario `h2b_hole_exit`), `docs/coverage/panels.md` (append), `docs/worklog/T155.md`. **NOT** `tools/patch_sterile.py`, `src/battle.rs`, `tools/harness.py` row definitions, `reference/bn6f`, `assets/`.

**Do.** Own worktree via `tools/worktree.sh t155`. Commit `docs/worklog/T155.md` with step 1 as your FIRST commit. If T154 has landed, build on it; if not, work on the state *as if* the enter arm exists and say so explicitly in the report — do not re-port the enter arm.
1. Baseline: on today's main, capture `h2b_hole_exit`'s window and record the frame where canon puts the object back on the field and what our side does at that frame (both x/y, both flags words). **measurement.**
2. Find canon's exit arm by walking the same flag word to its *other* reader(s) — the compare that clears or bypasses the hole bit for an object already in the hole; cite `file:line` and the exact mask it tests. If the exit is driven by a *different* field (a timer, an owner flag), name that field and cite it. **doc + measurement.**
3. Port the arm behind the same named `const` mask family step 2 cites — masks only, no per-scene values. **measurement.**
4. Re-run step 1's capture with the port: report the exit frame's object state delta before/after, and the pixel total/worst over the full compared window. Target 0. **measurement.**
5. Guard rows (`chips`, `wave`, `buster`, `field`, `popup`, `cursor`) + `battle_full` trace, verbatim lines. **measurement.**

**Rules.** The exit must be produced by state, not by a scripted frame count — a `EXIT_FRAMES = N` constant with no canon cite is a fitted constant and refuses the ticket. Do not touch the enter arm's code if T154 landed it. Do not compare inside a cropped region. Tool budget <=80, captures <=12.

**Acceptance.** `h2b_hole_exit` at **0 differing pixels on all its frames** with the object's position field matching canon on the exit frame (field named, frame named), `chips` unmoved and `wave`/`buster` at 0; or a bounded NEGATIVE naming the field that actually drives the exit and the routine that must be ported first.

**Measure and report.** row · frames · total · worst · region · commit · one line of mechanism · one line unverified; ROM sha256+size+delta; `cursor`'s line.

**Coordinator:** the free tier is the pair of captures at step 4 (before/after) on the exit frame — I re-run it on the tip. Cross-family verifier required for step 2's citation (it is a memory finding, and T153 is already auditing one of these patch/cite claims). <=$0.35 expected, <=$0.70 cap. **Depends on T154 landing; if T154 came back NEGATIVE, this ticket is not dispatched.**

---

### T156. M4/M3's box pass-through on a b+2 input: the second held-out item, engine-side only  *(BLOCKED -- 2026-09-17, NOT ATTEMPTED - same queue-integrity finding as T157: cites T152/T153/T154 as rungs)*

**Result.** NOT ATTEMPTED - same queue-integrity finding as T157: cites T152/T153/T154 as rungs; none exist in TODO.md; T156 additionally forbids landing while T152 is unmerged and T152 does not exist. Refused until the ladder's first rung lands or a ticket builds it from the ROM.
**Why.** The goal's held-out item is a **b+2 input** — a second box item that was never in any recording — and its rule is "an object that moves into a box's hole passes through". Today's pass is bought: T152's objective exists because the hit on the sterile box's item is registered by an *input patch*, and T153 is auditing exactly what `set_unk_col_desc` patches (obj 382/387) at byte level. So the pass-through rung has to be demonstrated on an item the patch was never tuned for, with the patch out of the loop, or the ladder is one lucky fixture. Two measured facts make this cheap to attempt: the collision descriptor is per-object data (T153's own subject), and T142/T143 showed a *deeper* arm can ride the same dispatch and go from 3463/2296/203 to **0/0/20** on `buster`+`field`+`popup` with no patch change — the mechanism generalises when it is in the engine. Advances **M4** (chip/item objects as data) and **M3** (ownership/area steal, obstacles).

**Files.** `src/objects.rs` (the collision-descriptor read path), `src/battle.rs` (the per-frame collision step), `src/field.rs` (only the hole-bit predicate T154 exported), `tools/states.py` (scenario `h2b_pass_b2`), `docs/coverage/objects.md` (append), `docs/worklog/T156.md`. **NOT** `tools/patch_sterile.py`, `tools/states.py`'s *existing* scenarios (read-only), `assets/`, `reference/bn6f`.

**Do.** Own worktree (`tools/worktree.sh t156`), its own `CARGO_TARGET_DIR`. Commit `docs/worklog/T156.md` with step 1 as your FIRST commit.
1. Build `h2b_pass_b2` **without looking at any existing box recording**: derive the item's descriptor from the ROM's own table, not from a capture; record what canon does with it and what our engine does, patch OFF. Both numbers, both first-divergence frames. **measurement.**
2. Read the pass-through predicate in canon — the compare on the descriptor + the hole bit that lets an object continue instead of stopping — cite `file:line`, and name which of the two masks our build is missing. **doc + measurement.**
3. Port the missing mask into our collision step as data (descriptor field + panel flag), no per-item literals. **measurement.**
4. Re-run step 1's comparison; the pass-through frame's object state and the full-window pixel total must both move to canon's value. Report before/after per frame. **measurement.**
5. Negative fixture: perturb the item's descriptor by one value the ROM never uses and show the row fails (not blind). Then guard rows + `battle_full` trace. **measurement.**

**Rules.** Patch OFF is the only admissible measurement on this ticket; a number that needs `patch_sterile.py` to pass is reported as a failure, not a pass. No allowlist, no boxed diff, no subtracted baseline. If the descriptor's *source* table is not yet exported, that is a legitimate NEGATIVE: name the table and its `file:line`, stop. Tool budget <=80, captures <=14.

**Acceptance.** `h2b_pass_b2` at **0 differing pixels over its whole compared window with no sterile patch applied**, the pass-through frame named, the negative fixture non-zero, `chips` unmoved; or a bounded NEGATIVE with the byte-level reason the descriptor cannot be read engine-side yet (which table, which missing export, which obj slot).

**Measure and report.** row · frames · total · worst · region · commit · one line of mechanism · one line unverified; the ROM sha256+size+delta; `cursor`'s exact line.

**Coordinator:** step 1's patch-off baseline is the ticket's spine and I re-measure it myself; a verifier pass is mandatory here because the claim is "no patch was used" and T153 has already found one such claim soft. Do not land while T152 is unmerged — its `Files.` overlap is `src/objects.rs`. <=$0.40 expected, <=$0.80 cap. **This is the rung that turns T152's pass into an engine pass.**

---

### T157. M3's pushed box: a box that is pushed moves — the push and the hit share one ported arm  *(BLOCKED -- 2026-09-17, NOT ATTEMPTED -- the ticket's premise does not exist on main, and it is a queue-integrity finding, not a work )*

**Result.** NOT ATTEMPTED -- the ticket's premise does not exist on main, and it is a queue-integrity finding, not a work failure. T157's whole cost model is 'cheap because T129 already paid the reconnaissance' and its rungs are 'T152 makes the hit register, T154/T156 make holes behave'; checked all four citations: (a) `grep -cE h2b tools/states.py` = 0, so NO h2b scenario of any kind exists, which means step 1's 'capture h2b_push' has nothing to capture and the step-1 cost is 'invent the scenario, the fixture and canon's box route from scratch'; (b) there is no ticket section for T152, T153 or T154 ANYWHERE -- `grep -nE '^### T15[0-9]\.' TODO.md TODO_ARCHIVE.md` prints only T155, T156, T157, T158, and the 12/8/19 mentions of T152/T153/T154 are all INSIDE those four tickets' own Why paragraphs, i.e. self-referential; (c) the only file in the repo that mentions h2b at all is the untracked judge scratch docs/proposals/20260917-190237.md, which DOES define T154 -- so the judge proposed the ladder's first rung and the admitting coordinator appended only T155-T158, leaving four tickets that each cite a rung that was never admitted, never measured and never landed; (d) docs/coverage/objects.md, which T156 tells its worker to append, does not exist either. The worker's own step-0 message said exactly this ('the h2b ladder has zero landed predecessors on main') and it then ended the session with no commits; nothing was changed, no worktree edits, wt/t157 is at main's a58228e and I am removing its worktree. THE SAME FINDING APPLIES TO T155, T156 AND T158, which cite the same missing rungs -- T156 additionally instructs 'do not land while T152 is unmerged', and T152 does not exist to be merged. I am NOT re-dispatching any of them until either the ladder's first rung lands or someone writes a ticket that builds it from the ROM instead of from a phantom predecessor. For contrast, what this run CAN use is real: T142 is live on the field-bg band, and wt/t138 sits parked at super_armor PASS 0/0/70 with cursor in class at pads 13 and 21, waiting on that band. child ~$0.06, no captures.
**Why.** The ladder's remaining rung is "a box that is pushed moves" and the goal's anti-victory rule is that each rung must make the previous mechanism *refuse less*: T152 makes the hit register, T154/T156 make holes behave, and the push is the one object response that canon drives from the same collision descriptor plus an ownership byte we already carry as a stand-in — SCOPE's M3 row still lists "ownership/area steal" as unmet, T129's Alliance-byte work is PARTIAL and **kept UNMERGED at f28efe3** because its new row did not pass. So the push is where two half-lands meet: the alliance/ownership mask (`src/field.rs:60`, the only reason holes and broken panels are excluded today) and the descriptor. Advances **M3**.

**Files.** `src/field.rs` (the alliance/ownership mask), `src/actor.rs` (the object's response to a hit), `src/objects.rs` (descriptor read), `tools/states.py` (scenario `h2b_push`), `docs/coverage/panels.md` (append), `docs/worklog/T157.md`. **NOT** `src/battle.rs`, `tools/patch_sterile.py`, `tools/harness.py` row definitions, T129's branch (read it, do not cherry-pick it).

**Do.** Own worktree (`tools/worktree.sh t157`). Commit the worklog with step 1 first.
1. Baseline: with the push not yet ported, capture `h2b_push` and record, frame by frame, the first frame where canon's box position changes and what our side does; plus the object's flags word at that frame. **measurement.**
2. Read T129's unmerged alliance work (branch at f28efe3) and report in one paragraph whether its mask is the predicate canon's push arm needs, citing both `file:line`s. If it is not, say so and continue with canon's own predicate. **doc + measurement.**
3. Port the push: displacement from the descriptor and the ownership test, all values from exported data or existing consts. **measurement.**
4. Re-run step 1: box position field and the full-window pixels must both reach canon's values; state the frame count that moved. **measurement.**
5. Guard rows + `battle_full` trace + the negative fixture (same push with an unowned box must be non-zero). **measurement.**

**Rules.** Reuse, never re-derive, T129's mask wording — and if you need to change its semantics, report that instead of editing it. No displacement constant without a cite. Tool budget <=80, captures <=12.

**Acceptance.** `h2b_push` at **0 differing pixels on all frames** with the box's position field diverging on **0 frames** of the window (trace: field, frames, first divergent frame), non-blind negative fixture, `chips`/`wave`/`buster` unmoved; or a bounded NEGATIVE naming which owner-side routine must land first.

**Measure and report.** row · frames · total · worst · region · commit · one line of mechanism · one line unverified · ROM sha256+size+delta · `cursor`'s line.

**Coordinator:** cheap because T129 already paid the reconnaissance; free tier is step 4's before/after pair. If your step-2 paragraph says T129's mask is load-bearing, tell me — that changes which branch I land first. <=$0.35 expected, <=$0.70 cap. **Pairs with T156 but files-disjoint, so it can run alongside it.**

---

### T158. M3's h2b rows become harness rows: promote the ladder to the scoreboard and close the collision routine's coverage  *(OPEN -- 2026-09-29)*

**Why.** Every rung above is measured on a comparison that only exists inside a worktree — the `box2plus` ladder's rows are not in the harness, so the daily review cannot see whether the ladder moved, and a regression in the hole or box path is invisible to the veto that stops other landings. The precedent is T140: the `super_armor` row went from nothing to **PASS 0/0/70, negative not blind 29640** by *writing the scenario into `tools/states.py` and the row into `tools/harness.py`*, and that row is now what gates T138/T141's landing. SCOPE's standard says "done" needs a canon recording, a port with citations, trace parity and pixel parity *per item*, and the item must be on the scoreboard or it is not an item. Advances **M3**, and it is the ticket that lets me keep gating on these rows.

**Files.** `tools/harness.py` (add the `h2b_*` rows and their negatives — no existing row's frames/align/pairing may change), `tools/states.py` (register the scenarios T154–T157 built), `tools/trace.py` (add the hole/push fields to the judged set), `docs/coverage/panels.md` and `docs/coverage/objects.md` (append), `docs/worklog/T158.md`. **NOT** any `src/` file, `reference/bn6f`, `assets/`, `tools/patch_sterile.py`, `tools/allowlist.py`.

**Do.** Own worktree (`tools/worktree.sh t158`). Commit the worklog first. `src/` is READ-ONLY on this ticket: if a row cannot read 0 without a code change, that is a finding, not a reason to edit.
1. `python3 tools/harness.py --list` and record which of the h2b rungs are already rows; for each missing one, add it with the frames of the recording and its own negative fixture. Report the table: row → total/worst/frames/negative. **measurement.**
2. Prove the negatives are not blind: for each new row, run its negative fixture and report the non-zero it produces, plus what you perturbed. A row whose negative reads 0 stays out of the harness and you say so. **measurement.**
3. Add the hole/box fields to `tools/trace.py`'s judged set and re-run `battle_full`; report the field-by-field map (which field, how many of the scene's frames, first divergent frame) and whether these fields diverge on any h2b scenario. **measurement.**
4. Coverage closure for the collision path: for canon's object/collision routine family, list every executed routine in the h2b windows as ported or out-of-scope-with-a-reason, at `file:line`. Report the counts before and after. **doc + measurement.**
5. Full-table regression on main vs your tip: `python3 tools/harness.py` and paste every changed line; the row set must be strictly non-worse. **measurement.**

**Rules.** No src edits, no tolerance, no allowlist, no re-framing of an existing row's window to make it pass; a new row that only passes with a patch applied does not go in — say that instead. Tool budget <=70.

**Acceptance.** The h2b rungs present as harness rows with **non-blind negatives** and their numbers reproducible by `tools/verify_rows.py` from a clean checkout; `battle_full`'s line unchanged or better; and the coverage table showing the collision family's executed routines each ported or scoped out with a reason. If a rung is not yet at 0 because T154/T156/T157 left residue, the row is still added with its real number and named as the gate — that is the deliverable, not a failure.

**Measure and report.** every new row: frames · total · worst · negative; rows changed elsewhere and their before/after; the trace field map; commit; one line of mechanism; one line unverified.

**Coordinator:** docs/tools-only landings go in with `--no-verify` only when `git diff --stat` against base names no `src/`, `vendor/`, `Cargo` or `assets/` path — I check that myself, as I did for T126/T127/T133. This is the cheapest ticket in the batch and the one that makes the other four permanent. <=$0.25 expected, <=$0.50 cap.

### T142. M8's band, decided not described: is the black top of the reveal capture a mid-scan CNT store or a map copy that arrives late?  *(NEGATIVE -- 2026-09-17, Step 1 DECIDED by bytes, not inference: the band is S1 - the renumber frame's BG0CNT store lands mid-scan betw)*

**Result.** Step 1 DECIDED by bytes, not inference: the band is S1 - the renumber frame's BG0CNT store lands mid-scan between scanlines 14/15 (post-flip map at 0x06009800 byte-identical to steady state 113 frames before the flip, so the boundary commit had NO map bytes to copy; pre-flip screenblock 17 all zeros; CNT flips 0x1100->0x1303 exactly at rust frame 121; rows 0..14 black = 3600 px = 15 rows, one frame). Mechanism: commit() waits for vblank, wait_for_vblank early-returns when vblank already passed, the renumber frame's loop overshoots, mGBA composites scanline-wise. Step 3 fix did NOT land: pad sweep 13..41 on main's footprint is a V-bottom at main's own 25 (3600=15 rows), never 0; src/main.rs restored byte-identical to main; branch diff vs main is docs+tooling only. Coordinator verify_rows PASS: field-bg1 3600/3600/40/174345, field-bg2 3600/3600/40/3600, field-bg3 380219/24906/40/405125, cursor 1/1/170/186279 - all MATCH main's lines at 780d8e0. Consequence recorded: wt/t138's cursor co-fits (pads 13/21) are WORSE than main on main's footprint (6480/4320 vs 3600) - pad re-fit cannot land wt/t138; the band needs a mechanism change. Unverified (worker says so): mGBA's scanline compositing model not vendored (scanline-15 landing inferred from capture); BG1/2/3 CNT stores not watched; which loop work causes the ~15-scanline overshoot unmeasured. Next candidate in-scope: hoist RESULT window first-paint (tile alloc + map fill) off the renumber frame in src/battle.rs (show_results-time background paint), needs its own measured pass. Evidence: worklog T142 on wt/t142 (780d8e0 + dedc1da scripts), captures /tmp/t142_*.bin
**Why.** Three tickets have now pointed at three different files for the same residue and each one's measurement refuted the previous one's story: T133 said the layer renumber lands a capture late in `src/battle.rs:4899-4910`; T137 measured the renumber ON TIME and moved the owner to `src/backdrop.rs`'s band-cell first paint; T139 exonerated `src/backdrop.rs`'s tile path and moved it to a mid-scan register write. T139's mechanism then took two hits from its own verifier: the watch capture it rests on covers `0x06004000:16384`, which ENDS AT `0x06007FFF` -- tile char blocks only, so **BG0's map was never observed at all**, and "about scanline 22" is read off the band's own height, i.e. a description, not a measurement. Meanwhile T141 settled the pad question on a neighbouring branch and produced the datum T139 said was impossible: on one layout the band's height MOVES WITH THE PAD (4320@11, 4800@13, 1920@17, 6720@19, 5040@21, 5520@25), while `field-bg3` sits at 380263 at every pad. Main today, after T135 landed, reads `field-bg1` **3600/3600/40** neg 174345 and `field-bg2` **3600/3600/40** neg 3600 -- that is 15 rows, down from the 22 rows T137 and T139 measured, moved by a landing that touched nothing in the field path. The band is pad- and footprint-sensitive and nobody has a model for why, and it is the ONLY thing keeping wt/t138 (M3's super armour, `super_armor` PASS 0/0/70 neg 29640, a fitted constant deleted, a real `tools/states.py` scenario) off main: at the two pads that put `cursor` back to main's exact 1/1/170/186279 the band is worse than main's, so AGENTS.md's no-surface-worse rule refuses the landing. Take the band to 0 and that whole queue of parked branches unblocks.

**Files.** `src/main.rs` **the `SEAM_PHASE_PAD_ITERS` value only** (if your fix makes the band vanish, say which pad you end on and what `cursor` reads there -- T141 has a co-fit on wt/t138 at pad 21 that will conflict with yours and I will resolve it, so REPORT the number, do not try to land both), `src/battle.rs` (the RESULT-window construction that drops the filler: `:4902` `if self.shown.is_none() { self.filler_bg.show(frame); }`, `:4934-4947`, `:4957`), `src/backdrop.rs` (its map writes) **only if step 1 says S2**, `docs/coverage/field_integrated.md`, `docs/worklog/T142.md`. **A recon map for this ticket is at `docs/recon/T142.md`: read it first; every causal link in it is unverified.** **NOT** `tools/harness.py` (no row's frames/align/pairing/negative -- `field-bg1`'s window is `canon_ref=135, rust_offset=113, frames=40` per `harness.py:2196-2221` and it stays), `tools/states.py`, `src/actor.rs`, `src/fixture.rs` (wt/t138 is parked holding all three), `tools/trace.py`'s judged set, `tools/allowlist.py`, `tools/patch_sterile.py`, `docs/coverage/cursor.md` (T141 owns it), canon, `reference/bn6f`, `assets/`.

**Do.** Start your worktree as the ticket says (default: `bash tools/worktree.sh t142`) from main.
1. **Settle S1 vs S2 with ONE pair of captures and no code change.** Run the row's own rust Side with the map window T142's recon corrected to (recon answer 4: `tiled.rs:362-371` puts the maps at `0x06008000..0x0600BFFF`, and this row's BG0CNT goes `0x1100 -> 0x1303`, i.e. screenblock **17 -> 19**, so pre-flip map = `0x06008800`, post-flip map = `0x06009800` -- the verifier's proposed `0x06008000:4096` covers blocks 16-17 and MISSES block 19, which is why nothing was decided last time): `--watch 0x06008000:8192:/tmp/t142_map.bin` AND `--watch 0x04000008:2:/tmp/t142_bg0cnt.bin` AND `--watch 0x04000000:2:/tmp/t142_dispctl.bin` on the same run, `field-bg1`'s rust configuration (`--only-bg 0`, `fixture=FIELD_ZERO`, `script=Start@10`), captures KEPT. Then read, for the capture where the band is black: is the post-flip map at `0x06009800` (window bytes `0x1800..0x1FFF`) ALREADY the final backdrop map, or is it still arriving? **Map complete while the band is black = S1 (a CNT/DISPLAY_CONTROL store landing mid-scan); map arriving in that same frame = S2 (the copy is the thing that spills).** Say which, with the bytes. Cost: 1 capture pair, `--watch` costs no extra capture and cannot perturb the run. **measurement -- this step decides which file the rest of the ticket edits, so do not skip it and do not edit code before it.**
2. **Kill or keep the arithmetic.** recon answer 6's hole: `copy_tiles` is a plain CPU `copy_from_nonoverlapping` of 2048 B per 32x32 map (`screenblock.rs:40-47`) and T118b measured a whole map copy at ~3.3 scanlines, but the band is 15-22 ROWS = ~7-11 KB of visible delay, so one map copy cannot explain it. Name the maps that actually go dirty in the boundary commit and their sizes (`src/field.rs`, `src/backdrop.rs`, `src/hud.rs` -- recon did not read them), and state whether S2's arithmetic is alive or dead. Also CONFIRMED and worth knowing before you reach for it: `tiled.rs:412-416` assigns hardware BG index in `.show()` CALL ORDER, the CNT/HOFS/VOFS stores at `tiled.rs:468-486` all precede `copy_tiles` at `:482-485`, a layer that stops being shown gets **no store at all** and its vacated register is masked only by the single `DISPLAY_CONTROL` write at `:461-466`, and `wait_for_vblank`'s early return is real (`interrupt.rs:417-427`) with the wait as commit's FIRST statement (`display/mod.rs:321`). **measurement + doc.**
3. **The fix, in the file step 1 named.** Bring the band to 0 on `field-bg1`. What is already excluded, do not re-litigate it: T133's value-major scan (widened this band 5280 -> 5760), T133's primed 37-`set_tile` allocation (broke composition to 208205/38400 full screen -- now understood as the dirty gate at `regular_background.rs:457` carrying tiles AND screenblock), any change to a row's compared window, any asset byte, and T139's claim that no pad value moves this band (T141 measured that it does). No fitted constant, nothing chosen from the diffmask. **code change + measurement.**
4. **Re-measure the whole coupling, because that is what unblocks the queue:** `field-bg1`, `field-bg2`, `field-bg3` and `cursor` at YOUR fix's pad AND at 21 AND at 13 (T141's two in-class values), reported as a table. `field-bg2`'s negative EQUALS its positive (3600) by T137's explained one-frame-shifted window landing on byte-equal canon c136, so a 0 there with negative == 3600 is a BLIND zero and you must say so rather than claim the win. `field-bg3`'s +44 against main at constant pad is NOT the band -- if your fix moves it, that is a second finding, report it separately. **measurement.**
5. If `field-bg1` reaches 0 and `cursor` is in class at some pad: name the pad, and state plainly whether wt/t138's parked branch (its tip e671af6 already carries pad 21 + T140's row + T135) would then land clean on top of your fix, or whether it needs a re-merge first. **I land things; you report.**

**Rules.** One capture pair per measurement, <=10 total; no row definition, window, align or negative changes; the band must be reported as ROWS (`total / 240`) every time you state a number, since three tickets have quoted it in px only; commit `docs/worklog/T142.md` with step 1's bytes as your FIRST commit; `src/main.rs` beyond that one constant, and every other branch's files, are out of bounds; end every grep/find/ls/rustc pipeline with `|| true` or `2>/dev/null` (a non-zero bash exit aborts your session and this queue has already lost two workers that way).

**Acceptance.** `field-bg1` isolated **0/0/40** with a S1-or-S2 mechanism named at file:line and step 1's bytes as its evidence, and the coupling table of step 4 -- which also unblocks wt/t138's landing. Or a bounded NEGATIVE with the same two halves: which seam the map bytes decide, and why no in-scope change can remove a band that is pad- and footprint-sensitive by these amounts.

**Measure and report.** rows: `field-bg1`, `field-bg2`, `field-bg3`, `cursor` (+ `mettaur`, `result`, `tiles`, `gauge` for the guard); frames 40/40/40/170; totals, worsts, BOTH negatives, band height in rows for every number; the watch windows' decoded state at the boundary capture; ROM sha256+size+delta; fitted/derived/peeked; commits; one line of mechanism; one line unverified (mGBA's compositing model is not vendored here, so a mid-scan effect is observable in a capture but cannot be traced to a scanline from this tree).

**Coordinator:** owns `src/main.rs`'s pad constant by authorization for this ticket only, and reports the coupling table for wt/t138's landing decision; T141's co-fit at pad 21 on the parked branch will conflict with yours and that is mine to resolve. Free tier: verify_rows on the four rows. Verifier for claims beyond rows: which seam step 1 decided, and step 2's dirty-map accounting. <=$0.50 expected, <=$1.00 cap. **Unblocks M8's last field row and, through it, M3's super armour.**

---

