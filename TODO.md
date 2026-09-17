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
### T81. M3: Finish CONFUSED with the star-ring effect object (continue T72 PARTIAL)  *(NEGATIVE -- 2026-09-17, Closed NEGATIVE on wt/t81 @ 8566903 [worklog-only])*

**Result.** Closed NEGATIVE on wt/t81 @ 8566903 (worklog-only). T72 PARTIAL scaffolding claim REFUTED: git log shows commit 462ccda was 'Worklog only, no source edit'; grep src/*.rs for Confused|confused|CONFUSED finds zero Style::Confused variant, zero set_confused function, no per-AIIndex confused stub at src/ai.rs:143-160. T81's ticket premise that T72 added the scaffolding is factually wrong. Per-AIIndex navi confused routine (off_810AA84..off_810AB38, asm31.s:172547-172644) READ but NOT ported: it dispatches on oAIState_DecideState to 3 arms (sub_810AAD0/sub_810AAE6/sub_810AB40), confused-tick is sub_810AC9A (:172857-172881, 4-tick be-confused + 5th-tick act-normally). Mettaur per-AIIndex confused routine is already ported at src/objects.rs:352 (BLIND_OR_CONFUSED constant false) and src/objects.rs:430 (METTAUR_WANDER arm) — but doesn't fire because BLIND_OR_CONFUSED is constant. Navi per-AIIndex confused port requires the T82 prereqs (navi Style/kind, sequencer-stuck, record unknown) that upstream tickets rejected. Tool budget 80 hard-exhausted on the refutation audit + worklog. Branch stays unmerged; wt/t81 removed after stamp. Recommended next ticket: T-CONFUSED-METTAUR (one-byte BLIND_OR_CONFUSED to runtime read + Mettaur-only confused harness row).
**Why.** T72 PARTIAL (2026-09-17, docs/worklog/T72.md, branch wt/t72 on main d3cfa2c) measured CONFUSED end-to-end and ported code, but the row went RED at the star ring: same-route canon-vs-canon floor = **11,436 px / worst 132 / first divergence k=1**, all six clusters the confusion star ring (orbit anchors x=10-219, y=106-122, ~30-frame period). Reader `playerObject_checkDirectionButtons_800FA54` (asm00_2.s:1867-1902) at :1894-1897 tests flags1 0x8000 ALONE then remaps via `byte_800FAA4 {0,2,1,4,3}`. Timer tick `sub_800E730` (asm/object.s:5457-5492): decrement Unk_1e at :5458-5460, signed `bgt` :5461 → re-assert 0x8000 + spawn status-effect object via `sub_80E09EE` → `object_spawnType4(6)` (asm31.s:85839-85855); initial timer **0x12c = 300** (sub_8013EE6, asm00_2.s:11371-11378, off_80141BC). T72 ported flag chain + tick into src/ai.rs + src/objects.rs + src/battle.rs (status-tick only) + new row `confused`; the star-ring sprite object is outside that scope. Milestone **M3** (CONFUSED at zero).

**New evidence.** T72 PARTIAL step 5 refutation precise: 90/90 frames covered by ring, 6 clusters ~127-184 px each, canon-vs-canon floor 11,436. Ring is `object_spawnType4(6)` (kind 6 effect object) drawn from type-4 pool, orbit timing from `sub_80E09EE` (asm31.s:85839-85855), sprite frames + palette from `assets/effects.bin` (or canon-side equivalent). T64's LTO trap (`#[no_mangle]` poke mailbox 0x020002fc + `core::hint::black_box`) carries over. T67's --watch-write lossy warning applies.

**Files.** `src/effects.rs` (NEW — type-4 effect object pool + spawn routine + orbit timing, `// canon: sub_80E09EE asm31.s:85839-85855` cited per arm), `src/objects.rs` (extend for spawn call at timer expiry `object.s:5482-5487`), `src/battle.rs` (status-tick lines only — `confused_tick()` once per frame), `src/spr.rs` (sprite-frame load + palette + tile allocation for type-4 effect kind 6), `tools/harness.py` (existing `confused` row only — no new row, no config change), `docs/coverage/statuses.md`, `docs/worklog/T81.md`. **NOT** tools/allowlist.py, tools/trace.py, tools/inventory.py, src/actor.rs (T69's), src/ai.rs (T72 ported, do not re-edit), src/fixture.rs, tools/states.py (state exists), reference/bn6f.

**Do.**
1. Baseline, no edit: build ROM, sha256; verify_rows HEAD on guard set → expect identical to T72 (wave 0/0/90, window 0/0/16, opening 0/0/40, mettaur 0/0/70, chip-cannon 0/0/40, windowclose 0/0/40, cursor 1/1/170/186279, blind unchanged). **measurement.**
2. Read `sub_80E09EE` and `object_spawnType4(6)` at the cited file:line; name the type-4 spawn parameters, orbit period (~30 frames), sprite frame set, palette/tile allocation. Read assets/effects.bin layout for kind 6. **measurement.**
3. Port the spawn: `src/effects.rs` — `EffectKind6` struct (x, y, anchor_idx, phase) + spawn routine + per-frame update; `src/objects.rs` — when timer expires AND bit is re-asserted, call the spawn with cited coords; `src/spr.rs` — sprite-frame load + tile/palette allocation in PAL_OBJ pool. **code change.**
4. Re-run `confused` row from a clean detached checkout; expect 0/0/90 with negative fixture non-zero (frame shift). Report ring's per-frame positions across k=1..90. **measurement.**
5. verify_rows on 8-row guard set + blind + confused; expect all identical to step 1, confused now 0/0/90. **measurement.**

**Rules.** Ring is data-driven from spawn routine, not fitted sprite pattern. Per-orbit-anchor positions from cited routine's table (asm31.s or shared effect-object table). No allowlist, no patch_sterile, canon never changes, no F47-style scroll broadening. `confused` row config (canon_ref=40, search range(100,111), negative = frame shift) unchanged from T72. ≤5 captures, tool budget ≤80.

**Acceptance.** confused 0/0/90 with non-blind negative (frame-shift negative still non-zero); 8-row guard set identical; SCOPE M3 status-bit count moves **0/69 → 1/69** (CONFUSED verified). Cited `sub_80E09EE` + `object_spawnType4(6)` arms each carry `file:line` provenance tag; ring's 6 anchor coords + 30-frame period reproduced from cited routine, not fitted. NEGATIVE naming ring's per-anchor pixel source (tile slot, palette index) + asm site closes it.

**Measure and report.** rows: confused + 8-row guard set; frames 90 each. Before/after pixel totals, worst, region, 6 anchor coords, orbit period, ROM sha256+size, fitted count, commit; one line of mechanism; one line unverified.

**Coordinator:** owns src/effects.rs (new), src/objects.rs's status-spawn call, src/spr.rs's tile allocation; pair with T80 (tools/states.py + src/custom.rs disjoint). Free tier: verify_rows from clean checkout on 10-row set. Verifier for step 2's cite vs sprite asset match (memory finding ring's PAL_OBJ slot). ≤$0.25 expected, ≤$0.50 cap. Advances **M3**.

---

- T82 NEGATIVE -- M7: Forms recon — TF enum + charge-shot dispatch + emotion window states. Closed NEGATIVE on wt/t82 @ c90a451 (docs-only)

### T83. M3: CONFUSED-Mettaur — flip the const, add a Mettaur-only harness row  *(NEGATIVE -- 2026-09-17, Closed NEGATIVE on wt/t83 @ 4013359 [worklog-only])*

**Result.** Closed NEGATIVE on wt/t83 @ 4013359 (worklog-only). 3 ticket errata: (1) bit pattern wrong -- ticket said 0xc000 (0x4000|0x8000 = IMMOBILIZED|CONFUSED) but asm gate at reference/bn6f/asm/asm31.s:171395-171397 tests 0xa000 (0x2000|0x8000 = OBJECT_FLAGS_BLIND|OBJECT_FLAGS_CONFUSED); include/structs/CollisionData.inc:16-18 confirms BLIND=0x2000, CONFUSED=0x8000; (2) no 'confused' harness row exists -- grep -c 'name="confused"' tools/harness.py = 0, grep -c 'name="blind"' = 0; BLIND row lives on wt/t69 per commit 60e8ad3; T81 NEGATIVE commit 8566903 confirmed tools/harness.py has no confused row; (3) confused scaffolding (set_confused() hook, Style::Confused variant, per-AIIndex confused-stub) lives in src/ai.rs/src/battle.rs/src/fixture.rs which the ticket's 'NOT' list forbids touching -- T81 refuted T72's scaffolding claim. Naming erratum: object_getFlag (asm00_2.s:21627-21632) reads oCollisionData_ObjectFlags1 (+0x3c); no oBattleObject_StatusFlags2 field exists. Recommended unblock: T83a = gate flip only (src/objects.rs:352+430 against 0xa000 mask, no anchor.rs, no harness row); T83b = chip effect + set_confused + Style::Confused + per-AIIndex stub (wider scope). Tool budget 60 hard-exhausted on the audit. Branch stays unmerged; wt/t83 removed after stamp.
**Why.** T81 NEGATIVE proved the per-AIIndex navi confused routine is NOT ported, but the Mettaur per-AIIndex confused routine IS ported at src/objects.rs:352 — gated by `const BLIND_OR_CONFUSED: bool = false;` with the `else if BLIND_OR_CONFUSED` arm at src/objects.rs:430. The single-byte gate is the only thing standing between the port and the per-frame effect. SCOPE M3 status count advances **0/69 → 1/69**.

**New evidence.** T81 NEGATIVE (2026-09-17, wt/t81 @ 8566903, worklog-only): T72's per-AIIndex navi confused (off_810AA84..off_810AB38) is unported; T72's scaffolding claim REFUTED by grep — worklog-only commit 462ccda added no `Style::Confused`. Mettaur per-AIIndex confused routine is ported at src/objects.rs:352 with `BLIND_OR_CONFUSED = false`; the `else if BLIND_OR_CONFUSED` arm at src/objects.rs:430 sets `self.decide = METTAUR_WANDER` but never fires. Navi confuse requires T82 prereqs (navi Style/kind) that T82 NEGATIVE rejected — Mettaur route is the only viable surface. T81's own recommendation: "one-byte BLIND_OR_CONFUSED to runtime read + Mettaur-only confused harness row."

**Files.** `src/objects.rs` (BLIND_OR_CONFUSED → runtime read of bits `0x4000|0x8000` from `oBattleObject_StatusFlags2` at src/objects.rs:352+430; **no other src/ edit**), `tools/anchor.rs` (NEW — exposes the runtime read of the flag-word for harness read-back), `tools/harness.py` (add `confused_mettaur` row against the existing `confused` scenario: canon_ref=40, search range(100,111), negative = frame shift; **no row-config change** to the `confused` row), `docs/coverage/statuses.md`, `docs/worklog/T83.md`. **NOT** tools/allowlist.py, tools/trace.py, tools/inventory.py, src/ai.rs, src/battle.rs, src/fixture.rs, tools/states.py (state exists), reference/bn6f.

**Do.**
1. Baseline, no edit: build ROM, sha256; verify_rows HEAD on 8-row guard set + blind + confused → expect all identical to T81 step 1. **measurement.**
2. Re-read `MettaurEntry` per-AIIndex routine at src/objects.rs:430 + the bit cite at include/structs/CollisionData.inc:16-18; name the `oBattleObject_StatusFlags2` offset the gate would read. **measurement.**
3. Add `tools/anchor.rs` exposing the runtime read; flip `BLIND_OR_CONFUSED` from `false` to a runtime read of the bit (file:line tag). **code change.**
4. Add `confused_mettaur` row in tools/harness.py using the SAME scenario as `confused` but bound onto the Mettaur slot via a battle with one Mettaur and a confused-source chip firing on MegaMan; build ROM; re-run `confused` + `confused_mettaur`. Expect `confused_mettaur` 0/0/90 with non-blind negative (frame shift); `confused` row identical to step 1 (gate still false in non-Mettaur path). **measurement.**
5. verify_rows on the 8-row guard set + blind + confused + confused_mettaur from a clean detached checkout; expect guard set + blind + confused identical, confused_mettaur 0/0/90. **measurement.**

**Rules.** Gate flip must be a runtime read of the named bit, not a fitted `true`. `confused_mettaur` row uses the SAME scenario as `confused` (offset only). No allowlist, no patch_sterile, no src/ change outside src/objects.rs:352+430 + the new anchor. ≤5 captures, tool budget ≤60.

**Acceptance.** `confused_mettaur` 0/0/90 with non-blind negative (frame shift); `confused` row identical to baseline; 8-row guard set + blind identical; SCOPE M3 status-bit count **0/69 → 1/69**. Cited bit at include/structs/CollisionData.inc:16-18 + Mettaur slot arm at src/objects.rs:430 each carry file:line provenance. NEGATIVE naming the ring's per-orbit pixel source closes it.

**Measure and report.** rows: confused_mettaur + confused + 8-row guard set + blind; frames 90 each. Before/after pixel totals, worst, region, ring anchor coords if it fires, ROM sha256+size, fitted count, commit; one line of mechanism; one line unverified.

**Coordinator:** owns src/objects.rs:352+430, tools/anchor.rs (new), tools/harness.py:confused_mettaur row; pair with T85 (disjoint, tools/inventory.py + tools/states.py only). Free tier: verify_rows from clean checkout on 11-row set. ≤$0.25 expected, ≤$0.50 cap. Advances **M3**.

---

### T84. M3: IMMOBILIZED — first status bit, no closure candidates left  *(BLOCKED -- 2026-09-17, Closed BLOCKED on wt/t84 @ 43b6b28 [additive const landed, linker-dropped)*

**Result.** Closed BLOCKED on wt/t84 @ 43b6b28 (additive const landed, linker-dropped; harness row not landed). Per coordinator rule: 2 in a row on M3 (T81 NEGATIVE, T83 NEGATIVE) end PARTIAL/BLOCKED/NEGATIVE — no third M3 ticket should be dispatched. T84 reached the same prereq-conflict pattern: IMMOBILIZED bit-test arm needs src/fixture.rs edits (fixture kind field for immobilized state propagation) which the ticket's NOT list forbids. Worker landed an additive const OBJECT_FLAGS_IMMOBILIZED=0x4000 at src/objects.rs:352 area (linker-dropped, byte-identical ROM); bit mask 0x4000 (lsl #0xe = bit 14) confirmed at asm31.s:171386-171390. Worklog carries the full mechanism read and the recommended split: T84a (gate flip only against 0x4000 mask with src/fixture.rs field added) + T84b (harness row with the fixture bit-set pathway). docs/coverage/statuses.md NOT written (would have implied landing). Branch stays unmerged; wt/t84 removed after stamp. Coordinator will not dispatch further M3 tickets until prereqs (fixture kind field for status bits, Style::Confused/Immobilized variants in src/ai.rs, battlestart sequencer unblock per T9d) are met by upstream tickets.
**Why.** T18 DERIVED-FROM-CODE status table (landed 3f09aa7): 32 of 69 flag bits have a per-bit reader, and SCOPE names three M3 candidates (CONFUSED, BLIND, IMMOBILIZED). CONFUSED: T83 in flight. BLIND: T69 BLOCKED on scope (render gate reshape). **IMMOBILIZED is the only candidate without an open follow-up** — its reader is at asm/asm31.s:171386-171390 (per SCOPE), the bit field is `OBJECT_FLAGS_IMMOBILIZED` (asm/asm00_2.s:23901 lsl r1,r1,#0x14), and there's no recent ticket touching it. M3 status-bit count advances **0/69 → 1/69** (or 2/69 if T83 lands first).

**New evidence.** T81 NEGATIVE (2026-09-17) closed CONFUSED's last follow-up; T69 BLOCKED (still UNMERGED) closes BLIND's narrative; T18 status table (landed 3f09aa7, verifier-re-run corrected) lists IMMOBILIZED's per-bit reader site at asm/asm31.s:171386-171390 outside the off_80209EC table — a directly-written flag2 mask test on the Mettaur/player slot's navi-side routine. The bit field source is at include/structs/CollisionData.inc (`OBJECT_FLAGS_IMMOBILIZED` #0x14 — slide-left-by-0x14 ⇒ mask `0x10` in flag2 stride; flag2 lives at `+0x4` of the same word per the struct), with object_setFlag/clearFlag sites to be enumerated at the Mettaur/player slot.

**Files.** `src/objects.rs` (read+gate path for `OBJECT_FLAGS_IMMOBILIZED` at the per-bit-reader-equivalent site; **no gate addition beyond a single bit-test**), `tools/states.py` (NEW scenario `immobilized_check` — battle with one Mettaur triggered into an immobilize-source condition and a frame window where it must NOT move), `tools/harness.py` (add `immobilized` row: canon_ref=40, negative = Mettaur moves at the held frame; no allowlist), `docs/coverage/statuses.md`, `docs/worklog/T84.md`. **NOT** tools/allowlist.py, tools/trace.py, tools/inventory.py, src/ai.rs, src/battle.rs (only status-tick hook if needed), src/fixture.rs, reference/bn6f.

**Do.**
1. Baseline, no edit: build ROM, sha256; verify_rows HEAD on 8-row guard set + blind + confused → expect all identical to T81 step 1. **measurement.**
2. Walk the per-bit-reader cite at asm/asm31.s:171386-171390; name the gate condition (which action the bit prevents — e.g. decider-store, action-tick). Walk the per-bit-set sites by grep-ing `OBJECT_FLAGS_IMMOBILIZED` references in asm31.s. Report reader site + at least one known setter site with `file:line`. **measurement.**
3. Wire the bit-test in src/objects.rs at the citation site; add `tools/states.py:immobilized_check` scenario that places a fresh-Mettaur into the cited immobilize-source condition. **code change.**
4. Build ROM; run `immobilized` row only; expect 0/0/40 with a non-blind negative (Mettaur moves at the held frame). **measurement.**
5. verify_rows on 8-row guard set + blind + confused + immobilized; expect guard + blind + confused identical, immobilized 0/0/40. **measurement.**

**Rules.** Bit-test MUST be derived from the cited reader site, not a fitted constant. The `immobilized` row's scenario must trigger the cited condition; if no Mettaur-side trigger exists in 40 frames, narrow the assertion to "no positional diff on the held frames". No allowlist, no patch_sterile. ≤5 captures, tool budget ≤60.

**Acceptance.** `immobilized` 0/0/40 with non-blind negative; 8-row guard set + blind + confused identical to step 1; SCOPE M3 status-bit count **0/69 → 1/69** (or 2/69 if T83 lands first). Reader cite at asm/asm31.s:171386-171390 + setter cite at the strongest grep hit both carry `file:line` provenance. NEGATIVE naming which action was gated (vs which action canon held) closes it.

**Measure and report.** rows: immobilized + confused + blind + 8-row guard set; frames 40 each. Before/after pixel totals, worst, region, ROM sha256+size, fitted count, commit; one line of mechanism (which action the bit gates); one line unverified.

**Coordinator:** owns src/objects.rs bit-test + tools/states.py:immobilized_check + tools/harness.py:immobilized row; pair with T85 (disjoint). Free tier: verify_rows from clean checkout on 11-row set. ≤$0.20 expected, ≤$0.40 cap. Advances **M3**.

---

### T85. M4: StepSwrd (id 81) pixel row — close the family-0x13 row gap  *(NEGATIVE -- 2026-09-17, Closed NEGATIVE on wt/t85 @ a1b3253 [branch stays unmerged])*

**Result.** Closed NEGATIVE on wt/t85 @ a1b3253 (branch stays unmerged). chip-stepswrd row FAIL 670/152/40 (negative 26899 non-blind); ticket's 'recovery-pose is fitted, no src/ change required' prediction REFUTED by measurement. +1 at src/battle.rs:439 (STEP_SWORD.recover = SWORD.recover + 1) does not match canon's full-40-frame StepSwrd recovery-pose behaviour. The scoreboard.py/inventory.py/chips.json/SCOPE.md updates are STALE (chip id 81 marked 'verified' but row fails 670/152/40); those updates cannot merge until a src/ change closes the row. 10 family-0x13 rows (chip-sword/wideswrd/longswrd/wideblde/longblde/fireswrd/aquaswrd/elecswrd/bambswrd/muramasa) all PASS 0/0/40 with T17 negatives (6397/7977/8824/7977/8824/8499/8396/7367/7913/8824) -- identical to HEAD. Fitted count 16 (one fewer than HEAD). ROM sha256 byte-identical (584392 B). docs/coverage/step_sword.md + docs/worklog/T85.md carry the full diagnostic probes for the next worker (probe: which record byte changes the +1 outcome; likely AttackSubFamily byte needs a per-step value, not the family-wide 0x01). Branch stays unmerged; wt/t85 removed after stamp.
**Why.** SCOPE: "StepSwrd (81) rides the same record dispatch without a pixel row of its own (tools/inventory.py AS_DATA_FAMILIES={0x13,0x15,0x21})". T17 landed family 0x13 for Sword..BambSwrd (71-79) + Muramasa (85) — 10 rows verified-pixels. StepSwrd's row would be the 11th sword family pixel row at no record-dispatch change (the dispatch already covers its family/subfamily bytes per SCOPE); the only open question is whether its one-frame-longer recovery pose at src/battle.rs:428-431 (`// StepSwrd holds its recovery pose one frame longer than the other swords.`) is record-driven or fitted — both outcomes need pixel verification. SCOPE M4 chip row count advances **43/411 → 44/411**.

**New evidence.** T75 NEGATIVE (docs-only on main): "the record-driven chip families' unprobed ids onto the scoreboard" — StepSwrd offset = `data/ChipDataArr.s:2514`, family/subfamily bytes are within the 0x13 / matching-subfamily envelope so the existing record dispatch CAN route id 81. T57 DONE census (verifier-hyper confirmed 14 record rows; 43 of 411 verified total). T78 DONE pattern shows the port shape — a per-record-byte dispatch with no separate `match id` arm. The src/battle.rs:428-431 doc-comment is the only cited divergence from sibling swords.

**Files.** `tools/states.py` (NEW scenario `stepswrd_select` — chip-select state with id 81 in the picked slot, fire it, compare pixels), `tools/harness.py` (add `chip-stepswrd` row: canon_ref=40, negative = fire-different-chip or no-chip; reuse the chip-cannon fixture base), `docs/coverage/chips.md`, `docs/worklog/T85.md`. **NOT** tools/allowlist.py, tools/trace.py, tools/inventory.py, src/battle.rs (T17 record dispatch already routes id 81; if the recovery-frame offset is fitted and the row red, escalate to a port ticket — do NOT silently port in this scope), src/chips.rs, reference/bn6f.

**Do.**
1. Baseline, no edit: build ROM, sha256; verify_rows HEAD on 8-row guard set + each sword/blade row (sword, longsword, wideswrd, wideblde, longblde, fireswrd, aquaswrd, elecswrd, bambswrd, muramasa) → expect all 0/0/N. **measurement.**
2. Read `data/ChipDataArr.s:2514` (StepSwrd record bytes) and the 10 sibling offsets (Sword..BambSwrd 71-79 + Muramasa 85) to confirm the family-0x13 + matching-subfamily envelope covers id 81 with no `match id { 81 => ... }` arm remaining in src/battle.rs. Re-read src/battle.rs:428-431 to classify the recovery-pose offset as either record-driven or fitted. **measurement.**
3. Add `tools/states.py:stepswrd_select` with chip-id 81 in the picked slot and a fire-cue matched to the sword-family scenario. Add `chip-stepswrd` row in tools/harness.py using the stepswrd_select scenario. **code change.** *If src/battle.rs:428-431 is fitted, do not edit it here — report the fitted constant as the ticket's NEGATIVE outcome.*
4. Build ROM; run `chip-stepswrd` row only; expect 0/0/40 with non-blind negative (different-chip fire). **measurement.**
5. verify_rows on the 8-row guard set + 10 sword/blade rows + chip-stepswrd; expect all identical to step 1, chip-stepswrd 0/0/40. **measurement.**

**Rules.** No src/battle.rs edit unless the recovery-pose offset is proven record-driven — src/battle.rs is owned by T17's family port and may NOT be re-opened for this ticket. No allowlist, no patch_sterile, no src/ change outside tools/. ≤5 captures, tool budget ≤60.

**Acceptance.** `chip-stepswrd` 0/0/40 with non-blind negative; 10 sword/blade rows identical to step 1; 8-row guard set identical; SCOPE M4 chip row count advances **43/411 → 44/411**. Cite `data/ChipDataArr.s:2514` for StepSwrd record bytes + the dispatch path; if src/battle.rs:428-431 is fitted, the ticket closes NEGATIVE with the named constant + cited site rather than landing a row.

**Measure and report.** rows: chip-stepswrd + 10 sword/blade family rows + 8-row guard set; frames 40 each. Before/after pixel totals, worst, region, ROM sha256+size, fitted count, commit; one line of mechanism (record dispatch vs fitted); one line unverified.

**Coordinator:** owns tools/states.py:stepswrd_select + tools/harness.py:chip-stepswrd row; pair with T83 OR T84 (disjoint with both — T83 owns tools/anchor.rs + src/objects.rs + tools/harness.py:confused_mettaur row, T84 owns src/objects.rs + tools/states.py:immobilized_check + tools/harness.py:immobilized row; pair with whichever lands first). Free tier: verify_rows from clean checkout on 19-row set. ≤$0.20 expected, ≤$0.40 cap. Advances **M4**.

### T86. M2 — PA recognition close-out via peeked state  *(NEGATIVE -- 2026-09-17, Closed NEGATIVE on wt/t86 @ 7433aea [worklog + baseline only])*

**Result.** Closed NEGATIVE on wt/t86 @ 7433aea (worklog + baseline only). Tool budget 80 hard-exhausted on step 1 (baseline) + step 2 (recipe stream reverification from /tmp/bn6f_real.gba); no src/custom.rs edit, no tools/harness.py pa_recog row. Baseline measurements: ROM sha256 0d3ea6d3277b0b43eb05d63deb193dcbac59ddd88ce73e6e9f1e9678f89b7a9f 584392B; pa_chipselect_state sha256 f9935ded0c98849646ef905f43216d808b1ab32e55167a7fabc41ca091e8f79f matches T80's on-disk copy; tools/inventory.py PA line 0/63 (correct baseline). Recipe stream reverified this session: PARecipePtrsB=20 dead ptrs at off_802BC60; PARecipePtrsA=43 live ptrs at off_802BCB0 (file offsets 0x2BC60..0x2BD5C+4); 63 records total (33 m=4 id-exact, 30 m=0 ascending-code-with-wildcard); 62 records count=3, A[12] count=4 (FireHit3+AquaNdl3+ElcPuls3+RskyHny3 -> 0x15A); all ingredient words are pure chip ids (code bits 0); result words are PA chip ids 0x140..0x15D (GigaCan1..MstrCros). Steps 3-5 (PA_RECIPES const + walk in src/custom.rs + pa_recog harness row) NOT landed. The blocker remains mgba_capture.c scripted-input (7ag owns it, off-limits); the worklog's plan to use peeked pa_chipselect_state as scripted-input replacement still requires src/custom.rs edits that exceed the remaining budget. Branch stays unmerged; wt/t86 removed after stamp. Recommended next ticket: T86b with budget <=150 for the full implementation.
**Why.** T80 PARTIAL (2026-09-17, branch wt/t80 @ e7738ea) landed only step 3: tools/states.py `State.patches` field + `_apply_state_patches` helper + `pa_chipselect_state` record (base=CHIPSELECT, patches=((0x5DDC0,0x01),)); /tmp/pa_chipselect.state sha256 f9935ded0c98849646ef905f43216d808b1ab32e55167a7fabc41ca091e8f79f. Steps 4-9 NOT landed: step 4 single-key bisect, step 5 `PA_RECIPES` const + walk in src/custom.rs, step 6 `pa_recog` harness row, step 7 F12 pad ladder, step 8 verify_rows, step 9 docs/coverage/pa_recog.md. The blocker is mgba_capture.c scripted-input (7ag owns it, off-limits) — but **steps 5/7/8/9 can land WITHOUT scripted-input** by using the peeked `pa_chipselect_state` on canon side (that state IS the scripted-input replacement). SCOPE M2 "PA recognition" chip-selection rule unmet; M4 program-advances = **0/63**.

**New evidence.** T80 PARTIAL result: 13 named rows verified identical to HEAD (cursor 1/1/170, all 12 others 0/0/N). T71's parser output (docs/worklog/T71.md): 63 recipes from `PARecipePtrsA` 43 ptrs at off_802BCB0 + `PARecipePtrsB` 20 ptrs at off_802BC60 (B dead in this build); record layout `[count u8][matcher u8][result u16 LE][ingredient u16 LE]×count`; m=0 paMatchCodeId / m=4 paMatchExact; 30 m=0 + 33 m=4; 190 ingredient slots over 90 ids; results 0x140..0x15D = GigaCan1, GigaCan2, …, MstrCros. Reader `custMenuPressOK_8028D3A` asm03_0.s:5437 → sub_8029110 :6029 → matchPARecipes_8029520 :6643; result stored at **0x02036660** via sub_802B6F2 :10881.

**Files.** `src/custom.rs` (OK-press branch BEFORE `Phase::Closing` + `PA_RECIPES: [(u8,u8,u16,[u16;4]); 63]` const from T71's parser output + walk that rewrites self.picks to collapsed hand + writes result word to 0x0203FF00), `src/deck.rs` (id/code exposure — already there per T71; no edit), `tools/harness.py` (ONE new row `pa_recog`: canon = REAL + `pa_chipselect_state`, watch 0x020366F2:0xA; rust = plain_rom + descriptor `deck=[1,12,71,54,1]`, `deck_codes=[0,0,18,1,0]`, `window_pick_count=1`, `window_pick_slot=4`, `window_cursor=0xa`, same script, watch 0x0203FF00:0xA; Align on OK-collapse marker; non-blind negative = same route WITHOUT A presses, watch stays ffff, cursor-walk pixels still move), `docs/coverage/pa_recog.md` (NEW), `docs/worklog/T86.md`. **NOT** tools/allowlist.py, tools/trace.py, tools/oracle.py, src/objects.rs, src/ai.rs, src/actor.rs, src/battle.rs, src/fixture.rs, src/chips.rs, src/shot.rs, tools/inventory.py (only re-run for the PA-line update), reference/bn6f.

**Do.**
1. Baseline, no edit: build ROM, sha256 (expect 5b46337a…85ef, 584296 B); `python3 tools/inventory.py` → quote PA line (expect `0 / 63`). **measurement.**
2. Verify pa_chipselect_state sha256 f9935ded… matches T80's on-disk copy; report any diff. **measurement.**
3. Port: `src/custom.rs` — `PA_RECIPES` const table from T71's parser output (cite each record's `byte_802Bxxxx asm03_0.s:114xx`); walk on OK-press branch BEFORE `Phase::Closing`; on match, rewrite `picks` to collapsed hand + write result word to **0x0203FF00** via `core::ptr::write_volatile`. Picked-words view reads `Deck::id/code`, no fitted count. **code change.**
4. tools/harness.py: ONE new row `pa_recog` as in **Files.**; Align on OK-collapse marker. **code change + measurement.**
5. verify_rows on 67-row table + pa_recog from a clean detached checkout; expect guard set identical, pa_recog 0/0/N with non-blind negative. `python3 tools/inventory.py` PA line **0/63 → 63/63**. **measurement.**

**Rules.** Recipe table generated from T71's parser output, no per-PA match (`match result_id` is the rule violation). Picked-words view reads `Deck::id/code`, no fitted count. Watch mirror at 0x0203FF00 rust-only, EWRAM top page. State file patch is `peeked` provenance. Cursor ≤1/1/170/186300. No allowlist, no patch_sterile, canon never changes. ≤8 captures, tool budget ≤80.

**Acceptance.** pa_recog 0/0/N with non-blind negative; PA-result field first divergence **none** in the row's window (OK-collapse frame + value matched); tools/inventory.py PA line **0/63 → 63/63**; verify_rows identical on `wave,window,opening,chip-cannon,mettaur,cursor,windowclose`; both watches (0x020366F2 canon / 0x0203FF00 rust) show the same 5-word sequence at the collapse frame. NEGATIVE naming canon scripted-input failure mode + recipe-table cites closes it.

**Measure and report.** rows: pa_recog + 7-row guard set; frames N/90/16/40/40/70/170/40. Before/after pixel totals, worst, region, recipe count (63), result field's old→new frame, both watches' word sequences, both ROM sha256+size, fitted count, commit; one line of mechanism; one line unverified.

**Coordinator:** owns src/custom.rs + tools/harness.py — pair with T87 (M5 disjoint, src/objects.rs disjoint). Free tier: verify_rows + `python3 tools/inventory.py` re-run. Verifier for step 3's table-driven claim and step 4's descriptor alignment. ≤$0.30 expected, ≤$0.70 cap. Advances **M2**, then **M4**.

---

### T87. M5 — T58 PARTIAL step 5 redo: an AIIndex-4 rank the frame-60 lever can field  *(OPEN)*

**Why.** T58 PARTIAL (2026-09-16, branch wt/t58 tip 0302084) landed steps 1-4 (rank census): 452 identity rows → 257 virus rows → 187 distinct (ai_index, version) pairs; ai 0 = 1 pair, ai 1-31 = exactly 6 pairs each; the ported Mettaur routine rides byte offset 0x04 = ai_index 1, and the live trio NameIDs 0x0001/0x0085/0x2000 are ai 1/7/17 — NOT ai 4. Step 5 NEGATIVE specifically for Mettaur v4/v5: CentralArea1 record list at **0x080b4b78** (data/dat30.s:2463, NOT data/BattleSettings.s), records 12/13 carry record[7]==1 gated by sub_80AA6EC (label at asm29.s:10493, not :10488), so lever alone cannot field them in overworld_net's daytime forest. **T58's NEGATIVE closed Mettaur v4/v5 specifically, NOT every ai_index 4 rank.** 5 other ranks at ai_index 4 exist (one per version v0..v5; the live trio uses v0..v3). M5 is 1/187; SCOPE M5 (one recorded scenario per rank).

**New evidence.** T58 PARTIAL result: lever model reproduced (60:0x0200a210:0x371 reads one tick later → 886 → mod 12 = 10 → record 0x080b4c18, formation Mettaur/Gunner/Mettaur; slots populate at frame 148 with NameID 0x0001/0x0085/0x2000 matching off_8109150 byte-for-byte; 40-frame determinism 0 px across two builds). Verifier CONFIRMED census, lever model, record/formation/HP byte match, 0-px determinism, and both negatives (CentralArea1 record-12/13 gate, no attack arms within 300 frames). The 1076 0xF0-terminated formation arrays (T65) carry rank versions WITHOUT the gate for some ai_index-4 ranks — those ARE fieldable.

**Files.** `tools/states.py` (ONE new `State` recipe `battlestart_ai4_rank<N>` for an N with record[7]==0 — base `/tmp/overworld_net.state` + T58's frame-60 lever at step-2-derived value + any unlock poke if needed), `docs/coverage/mettaur.md` (append the AIIndex-4 rank census + lever values), `docs/worklog/T87.md`. **NOT** src/ (zero changes), tools/harness.py (no row added — recording-only), tools/rom_enemy_tables.py, tools/trace.py, tools/oracle.py, tools/allowlist.py, assets/, reference/ (read-only).

**Do.**
1. `python3 tools/rom_enemy_tables.py` → group the 187 (ai_index, version) pairs by ai_index 4; report the six (ai=4, v=0..5) ranks' identity rows + the first BattleSettings record each one appears in, with each record's record[7] gate byte. **measurement.**
2. For each AIIndex-4 rank whose first record has record[7]==0 (no sub_80AA6EC gate), walk `data/BattleSettings.s` lists (`battleSettingsList0:2`, `BattleSettingsList1:1505`; T65's 1076 0xF0-terminated arrays) and report the record address whose formation names that rank, with bytes read and the lever value the frame-60 must take. **measurement.**
3. Add ONE `State` recipe (base `/tmp/overworld_net.state`, frame-60 lever at step 2's value), build via `python3 tools/states.py build all`. **measurement.**
4. `--watch` it: report chosen BattleSettings pointer, the three populated slots' NameID/version/HP at populating frame, and compare each HP against that version's `off_8109150` `elem_hp` row. **measurement.**
5. Determinism: 40 frames from two independent builds of the new state diff to **0** pixels; report pixel count and both state hashes. **measurement.**
6. Record the frame at which canon's new enemy first arms an attack (trace/peek read-only); quote field and frame as the alignment event for a follow-up port ticket. **measurement.**

**Rules.** Recording-only: no src/ change, no harness row, no allowlist, no patch_sterile, canon never changes. Only a NEW State entry — no existing recipe's rom/base/script/pokes/frames change, no root state touched (inputs guard stays green). The new state must be rebuildable by `tools/states.py build all`. Every claimed byte cites reference/bn6f file:line or the ROM table. ≤5 captures, tool budget ≤60.

**Acceptance.** At least one NEW `State` recipe (`battlestart_ai4_rank<N>`) builds and fields a non-Mettaur-v0..v3 ai_index-4 rank whose off_8109150 elem_hp matches the populating-frame HP byte-for-byte; 40-frame determinism reads **0 px** across two independent builds; alignment event frame named. docs/coverage/mettaur.md carries the AIIndex-4 rank census + lever values. NEGATIVE naming the sub_80AA6EC-gated records that block a specific rank (with record address + gate byte) closes it.

**Measure and report.** rows: 7-row guard set unchanged; frames 40 (recording only); two state hashes, both ROM sha256+size, lever value, AIIndex-4 rank identity row, populated slots NameID/version/HP, off_8109150 elem_hp row, alignment event frame, fitted count, commit; one line of mechanism; one line unverified.

**Coordinator:** owns tools/states.py + docs only — pair with T86 (src/custom.rs + tools/harness.py disjoint). Free tier: `python3 tools/states.py build all` from clean checkout, byte-identity of ROM. ≤$0.05 expected, ≤$0.10 cap. Advances **M5**.

---

### T88. M2 — Land T66's POST_FLINCH_FRAMES shadow replacement from a fresh worktree  *(DONE -- 2026-09-17, Closed RESOLVED-ALREADY on wt/t88-t66-land @ 8b0ce0d [T67 already landed T66's fix; no source change; worklog-only])*

**Result.** Closed RESOLVED-ALREADY on wt/t88-t66-land @ 8b0ce0d (worklog-only; no source change). The literal cherry-pick from `wt/t66` (commits 8495f6c / 9aa7e26 / 13623d0) is irreconcilable with current main: T67 step 3 (c2e1317, 2026-09-16) already deleted `POST_FLINCH_FRAMES` and replaced `post_flinch: u8` with `phase_arm_shadow: u8` at the same lines T66's 8495f6c edits. Cherry-pick produced conflicts in all four T66 files (src/actor.rs, src/battle.rs, docs/coverage/battle_full.md, docs/worklog/T66.md); resolving them requires choosing one model over the other (violating the ticket's "no re-derivation, no re-write" rule). T66's expected ROM sha (ef2ebed1d0cc6617…) is unreachable because T66's tip predates T67/T78/T80/T85. T67 delivers T66's intent strictly more completely (it attributes the 9..0 tail to `playerAI_sub_80F0354` at asm31.s:118977-118978, where T66 left it unattributed; the writer-census hole T66 flagged is closed). Acceptance items T67 already satisfies: POST_FLINCH_FRAMES gone + 248-frame hold rule + writer list in docs/coverage/battle_full.md + 7 guard rows identical (cursor 1/1/170/186279 held) + verify_rows PASS + no diff to Q3.md/ghidra_decompile.sh/BnPrepare.java (clean on main when T88 opened). Branch stays unmerged; wt/t88-t66-land removed after stamp. docs/worklog/T88.md carries the full conflict analysis.

**Why.** T66 PARTIAL (2026-09-16, branch wt/t66 tip 13623d0) met acceptance in full but UNMERGED: `tools/land.sh` refused because main's checkout carried foreign uncommitted edits in three external files (`docs/tickets/Q3.md`, `tools/ghidra_decompile.sh`, `tools/ghidra/BnPrepare.java` — a live human Ghidra session, off-limits to the worker). Diff vs main: `src/actor.rs`, `src/battle.rs`, `docs/coverage/battle_full.md`, `docs/worklog/T66.md` — purely src+docs. WHAT IT DOES: deletes `const POST_FLINCH_FRAMES: u8 = 11; // provenance: fitted` and the 11-frame 9..0 countdown shadow, replaced by `timer_holds_sentinel: bool` + `const TIMER_SENTINEL: u16 = 0xffff` (derived: `playerFlinchAction_80174FE` underflows Timer to 0xFFFF at asm00_2.s:18353-18356, PC 0x08017586 strh; the CurAction 0x08 handler `playerAI_update_80EA734` at asm31.s:107357-107447 contains ZERO oBattleObject_Timer stores, so the sentinel is held until another writer fires; canon holds it 248 frames, k=292..539, T63 store table). ROM sha256 ef2ebed1d0cc6617e6e15c494e0a87fe32011ec16656cc458c5e50cbe321e029. 6 guard rows + cursor all identical to main, verify_rows PASS twice. SCOPE M2 "timer hold" model-quality fix on the player slot.

**New evidence.** T66 PARTIAL result already documented: `mm_timer` on battle_full stays 270/540 because OUR navi is never hit (hp set {60}, mercy {120}, timer {0} over k=0..539) — so the change is observation-vacuous on battle_full and lands as model-quality only; fire-alignment gap (canon fires k=250 from scripted A@260 vs ours AUTO-FIRE k=352 from `fire_frame: 180`) is a separate un-ticketed blocker awaiting a user ruling. T67 DONE (2026-09-17, landed 2d7ce09) confirmed the Timer writer-list methodology. Whether the dirty-checkout gate (docs/tickets/Q3.md / ghidra_decompile.sh / BnPrepare.java) has cleared between T66 and today is unknown; if still present, `tools/land.sh` will refuse again from any worktree that targets main.

**Files.** `src/actor.rs` (the shadow and its export — verbatim from wt/t66), `src/battle.rs` (Timer export path if forced — verbatim from wt/t66), `docs/coverage/battle_full.md` (the 248-frame 0xFFFF hold + writer list — verbatim from wt/t66), `docs/worklog/T88.md` (carry T66's worklog + the disposition note). **NOT** tools/allowlist.py, tools/trace.py, tools/oracle.py, tools/harness.py, tools/states.py, src/objects.rs, src/ai.rs, src/fixture.rs, reference/bn6f; **NOT** docs/tickets/Q3.md, tools/ghidra_decompile.sh, tools/ghidra/BnPrepare.java (T66's three dirty files — human Ghidra session, off-limits).

**Do.**
1. Fresh worktree: `bash tools/worktree.sh t88-t66-land`; from the new branch, `git cherry-pick 8495f6c 9aa7e26 13623d0` from `wt/t66` (T66's three commits, src+docs only). **measurement.**
2. Build ROM, sha256; expect `ef2ebed1d0cc6617e6e15c494e0a87fe32011ec16656cc458c5e50cbe321e029` (T66's tip hash). **measurement.**
3. verify_rows on `wave,window,opening,chip-cannon,mettaur,windowclose,cursor` (7-row guard set); expect all identical to T66's pre-land numbers (cursor 1/1/170/186279, others 0/0/N). tools/inventory.py → M2 line unchanged. **measurement.**
4. `python3 tools/oracle.py battle_full --both` → `mm_timer` divergent count 270/540 (unchanged — no player hit on battle_full) AND `enemy_state_action`/`enemy_anim`/`rng_cadence` unchanged (T66 touched mm_timer only). **measurement.**
5. Land: `bash tools/land.sh t88-t66-land wave,window,opening,chip-cannon,mettaur,windowclose,cursor --expect wave=0/0/90,window=0/0/16,opening=0/0/40,chip-cannon=0/0/40,mettaur=0/0/70,windowclose=0/0/40,cursor=1/1/170`. **landing.**
6. If `tools/land.sh` refuses at step 5 with the same dirty-checkout error T66 hit, **STOP and report** (the gate is unchanged): record the exact error, list the three dirty files, and propose T88a = "Land after dirty files cleared by user" as the follow-up — do NOT touch the dirty files. **disposition.**

**Rules.** Cherry-pick verbatim from wt/t66 — no re-derivation, no re-write. Verify T66's verifier-hyper findings (per-frame decrementors at asm00_2.s:1381/1691/16135/16287/16460/18259/18903 + object.s:143/172/785; writer-list labelled non-exhaustive) carried in. No fitted constant replacement; if the sentinel hold is held, `docs/coverage/battle_full.md` must say so. Cursor ≤1/1/170/186300. No allowlist, no patch_sterile, canon never changes. ≤2 captures, tool budget ≤30.

**Acceptance.** ROM sha256 = ef2ebed1d0cc6617… (verbatim); POST_FLINCH_FRAMES either gone or carries a provenance tag naming a measurement + frame range (T66 produced the former); the 248-frame hold rule stated in `docs/coverage/battle_full.md` with the writer list; 7 guard rows identical to T66's published numbers; cursor 1/1/170/186279 not exceeded; verify_rows PASS. `git diff --stat` after landing touches only the four T88 paths (src/actor.rs, src/battle.rs, docs/coverage/battle_full.md, docs/worklog/T88.md) — no Q3.md / ghidra_decompile.sh / BnPrepare.java diff. NEGATIVE naming a regression in any guard row OR a dirty-file diff OR a successful refusal with the same T66 dirty-checkout error closes it.

**Measure and report.** rows: 7-row guard set; frames 90/16/40/40/70/40/170. Before/after pixel totals (expect identical to T66), mm_timer divergent count (expect 270/540 unchanged), ROM sha256+size, fitted count, disposition note (landed or T66-dirty-gate-still-present), commit; one line of mechanism; one line unverified.

**Coordinator:** owns the cherry-pick and the land; pair with T86 (src/custom.rs + tools/harness.py disjoint — `git cherry-pick` reuses src/, not tools/). Free tier: verify_rows from the fresh worktree. Verifier for step 6's disposition: did the dirty-checkout gate clear between T66 and T88, or did the fresh worktree bypass it? ≤$0.10 expected, ≤$0.20 cap. Advances **M2**.

### T89. M2 — Land T7q's seq.state gate port in src/battle.rs (continued from T7q PARTIAL)  *(NEGATIVE -- 2026-09-17, Closed NEGATIVE [RESOLVED-ALREADY] on wt/t89)*

**Result.** Closed NEGATIVE (RESOLVED-ALREADY) on wt/t89. T7q's seq.state gate IS already on main via commit 8ad8067 (src/objects.rs:74-91 PLAYER_EXECUTOR_GATED_STATE_00/04/20/24 + player_executor_gated; src/objects.rs:186-188 t1_player_entry(...,seq_state) early-return Update::Nothing; src/battle.rs:3524 t1_player_entry(&mut self.megaman, self.seq.state) gate wired; src/battle.rs:3533-3538 T7o's SEQ04 seq-match block relocated). wt/t7q branch absent (git for-each-ref | grep t7q empty). Cherry-pick from non-existent wt/t7q = no-op. mm_timer 270/540, rng_cadence 9/540, cursor 1/1/170 are current main values (T66/T7p already measured). T7p DONE ae54df7, T88 RESOLVED-ALREADY 8b0ce0d, T7r PARTIAL 7358b0d all on main. Disposition: gate already on main via 8ad8067. Recommended next ticket: T89a = 'Measure battle_full sequencer-first-divergence with current main's gate and confirm T66's sequencer-timing gap is the remaining M2 work'. No fresh worktree, no land. Branch stays unmerged; wt/t89 removed after stamp.
**Why.** T7q PARTIAL (2026-09-16, branch wt/t7q unmerged) added the seq.state gate at `src/battle.rs` `Actor::update` (t1_player_entry early-returns `Update::Nothing` when `seq.state in {SEQ_20, SEQ_24, SEQ_00, SEQ_04}`). Branch stayed unmerged because cursor and oracle traces were not re-measured at this stage. M2 sequencer gap (battle_full 174/540 sequencer frames): the k=179 group (MegaMan's per-tick work) is gated by the same set of states canon holds for ~248 frames (T66 PARTIAL → T88 DONE's TIMER_SENTINEL = 0xffff, `playerFlinchAction_80174FE` underflow at asm00_2.s:18353-18356). T7o's release-edge port (SEQ04 seq-match block relocated from src/battle.rs:2533 → :3268 past t1_player_entry) reduced `rng_cadence` 10/540 → 9/540 (T7p DONE). Combining T7q's gate with T7o's relocation is the cited path toward closer-to-zero on battle_full sequencer; landing wt/t7q onto current main is the cheapest measurable M2 step. SCOPE **M2** advance: k=179 group's first divergence on battle_full stays N or later; cursor veto holds.

**Files.** `src/battle.rs` (T7q's gate in `Actor::update` near t1_player_entry; verbatim from wt/t7q; no other src/ edit), `docs/coverage/battle_full.md` (carry T7q's notes + acceptance cite), `docs/worklog/T89.md`. **NOT** tools/allowlist.py, tools/trace.py, tools/oracle.py, tools/harness.py, src/objects.rs, src/ai.rs, src/fixture.rs, src/actor.rs, src/custom.rs, reference/bn6f; **NOT** docs/tickets/Q3.md, tools/ghidra_decompile.sh, tools/ghidra/BnPrepare.java (T66's three dirty files — human Ghidra session, off-limits).

**Do.**
1. `bash tools/worktree.sh t89-t7q-land`; cherry-pick T7q's seq.state gate onto a fresh branch off current main HEAD; build ROM, sha256. **measurement.**
2. Run `python3 tools/oracle.py battle_full --both` on the fresh build; report `enemy_state_action`, `enemy_anim`, `mm_state_action`, `mm_anim`, `mm_timer`, `rng_cadence` divergent counts (expect `mm_timer 270/540` unchanged per T66, `rng_cadence 9/540` unchanged per T7p, k=179 group state fields unchanged at k=179). **measurement.**
3. Run `python3 tools/verify_rows.py HEAD wave,window,opening,chip-cannon,mettaur,windowclose,cursor --expect wave=0/0/90,window=0/0/16,opening=0/0/40,chip-cannon=0/0/40,mettaur=0/0/70,windowclose=0/0/40,cursor=1/1/170`. **measurement.**
4. Land: `bash tools/land.sh t89-t7q-land wave,window,opening,chip-cannon,mettaur,windowclose,cursor --expect ...`. If `tools/land.sh` refuses with the same dirty-checkout error T66 hit, STOP and report. **landing.**
5. `python3 tools/oracle.py battle_full --both` on landed main; expect identical to step 2. **measurement.**

**Rules.** Cherry-pick T7q verbatim — no re-derivation. The seq.state gate set is `{SEQ_20, SEQ_24, SEQ_00, SEQ_04}` per T7q. Cursor veto: ≤1/1/170/186300. No allowlist, no patch_sterile, canon never changes. ≤2 captures, tool budget ≤30.

**Acceptance.** ROM lands cleanly; gate from T7q present in src/battle.rs with file:line tag; cursor 1/1/170/186279 unchanged; oracle battle_full identical to T7o's PARTIAL result; `git diff --stat` touches only `src/battle.rs`, `docs/coverage/battle_full.md`, `docs/worklog/T89.md`. NEGATIVE naming a regression in any guard row OR a dirty-file diff OR a refusal with the same T66 dirty-checkout error closes it.

**Measure and report.** rows: 7-row guard set; frames 90/16/40/40/70/40/170. Before/after pixel totals (expect identical to T66/T7o pre-land numbers), oracle field divergent counts, ROM sha256+size, fitted count, disposition note (landed or refused), commit; one line of mechanism; one line unverified.

**Coordinator:** owns the cherry-pick and the land; pair with T90 (M8 disjoint). Free tier: verify_rows from the fresh worktree. Verifier for step 4's disposition: did the dirty-checkout gate clear between T66 and T89? ≤$0.10 expected, ≤$0.20 cap. Advances **M2**.

---

### T90. M8 — First formation scenario + harness row from T65 census  *(PARTIAL -- 2026-09-17, Landed PARTIAL on wt/t90 @ 98ddac0 [docs-only branch])*

**Result.** Landed PARTIAL on wt/t90 @ 98ddac0 (docs-only branch). Tool budget 80 hard-exhausted on step 1 baseline + T87/T58 byte-exact record census; step 2 (read data/BattleSettings.s) done, steps 3-5 (tools/states.py recipe + harness row + verify_rows on full set) NOT landed. Baseline measurements: T87 ai4 rank0 rec0 = 0x080b4334 bytes 00141500ff003800 e2490000 8d470b08 (rec7=0, gate free); formation ptr 0x080b478d quads 00/22/00/00, 11/14/a3/00, 11/26/13/00, f0/00/00/00 (3 quads, matches T87 byte-for-byte); lever 0x373 (from T58's frame-60 lever 60:0x0200a210:0x371); ROM sha256 a37c1028adb7…0d455ad670 (8 388 608 B). 7 guard rows identical to HEAD (wave/window/opening/chip-cannon/mettaur/windowclose/popup all 0/0/N). Recommended next ticket: T90a = tools/states.py + tools/harness.py + docs/coverage/formations.md with budget ≤150.
**Why.** T65 PASS 3 (landed 79da4ed) closed M1's formations GAP with **1240 records over 84 lists / 1076 0xF0-terminated formation arrays**; all **0/1076** scenarios recorded. T58 PARTIAL (branch wt/t58 tip 0302084) census: **187 distinct (ai_index, version) pairs**; lever model reproduced (60:0x0200a210:0x371 → 886 → mod 12 → record 0x080b4c18, formation Mettaur/Gunner/Mettaur; slots populate at frame 148 with NameID 0x0001/0x0085/0x2000 matching off_8109150 byte-for-byte; **40-frame determinism 0 px across two builds**). T58 step 5 closed for Mettaur v4/v5 (CentralArea1 records 12/13 gated by sub_80AA6EC at asm29.s:10493); T87 OPEN records a non-Mettaur ai_index-4 rank with record[7]==0. **T90 ports one of those 1076 formations to the harness** as the first scenario recording for M8. SCOPE **M8** advance: formations count `0/1076 → 1/1076`.

**Files.** `tools/states.py` (NEW `battlestart_<rank>` recipe using T87's lever value + the cited BattleSettings record; base `/tmp/overworld_net.state` + T58's frame-60 lever at T87-derived value), `tools/harness.py` (NEW row `<rank>_formation`: canon_ref=40, `search range(<T87 lever value>-2, <T87 lever value>+2)`, negative = same route WITHOUT the lever poke), `docs/coverage/formations.md` (NEW — first entry carrying the cited BattleSettings record address + bytes), `docs/worklog/T90.md`. **NOT** tools/allowlist.py, tools/trace.py, tools/oracle.py, tools/inventory.py (only re-run for M8 line update), src/, reference/bn6f.

**Do.**
1. From T87's recipe byte, extract the BattleSettings record address + the chosen `<rank>`'s three-slot formation word (NameID/version/HP triplet) and the record[7] gate byte. **measurement.**
2. Read `data/BattleSettings.s` near the cited address; confirm the record's formation matches T87's byte-for-byte reading and no `match formation_id` arm in src/ exists. **measurement.**
3. Add `tools/states.py:battlestart_<rank>` with base `/tmp/overworld_net.state` + T87's lever value at frame 60 + any required unlock poke; build via `python3 tools/states.py build all`. **measurement.**
4. Add `<rank>_formation` row in tools/harness.py; run it; expect 0/0/40 with non-blind negative (no-lever route produces a different formation). **measurement.**
5. verify_rows on 8-row guard set + `<rank>_formation`; expect guard identical, `<rank>_formation` 0/0/40. **measurement.**

**Rules.** Recording-only at the harness row layer — src/ stays untouched. State file patches are `peeked` provenance. No allowlist, no patch_sterile, canon never changes. The `<rank>` chosen must have record[7]==0 (per T87 + T58). ≤5 captures, tool budget ≤80.

**Acceptance.** `<rank>_formation` 0/0/40 with non-blind negative (frame-shift negative non-zero); 8-row guard set identical; SCOPE M8 formations count `0/1076 → 1/1076`. Cited BattleSettings record address + bytes each carry `file:line` provenance; formation byte-exact vs T58's census + T87's recipe. NEGATIVE naming the gate byte for a blocked rank (with record address) closes it.

**Measure and report.** rows: `<rank>_formation` + 8-row guard set; frames 40 each. Before/after pixel totals, worst, region, lever value, BattleSettings record address, formation triplet, gate byte, ROM sha256+size, fitted count, commit; one line of mechanism; one line unverified.

**Coordinator:** owns tools/states.py + tools/harness.py + docs only; pair with T89 (src/battle.rs disjoint). Free tier: verify_rows + `python3 tools/states.py build all` byte-identity of ROM. Verifier for step 1's formation-bytes vs T87 cite. ≤$0.10 expected, ≤$0.20 cap. Advances **M8**.

---

### T91. M4 — TrnArrw family (ids 24-26) as data, take-1  *(NEGATIVE -- 2026-09-17, Closed NEGATIVE on wt/t91 [worklog only])*

**Result.** Closed NEGATIVE on wt/t91 (worklog only). Ticket's 'family unchanged across 3 ids' premise REFUTED by reading reference/bn6f/data/ChipDataArr.s:747..871: chip 24 TrnArrw1 codes=GMZ? family 0x28 attack_power 40; chip 25 TrnArrw2 codes=MSY? family 0x28 attack_power 50; chip 26 TrnArrw3 codes=BET? family **0x2D** (Muramasa's family) attack_power 60. Chip_element identical (0x01) across all three so it cannot discriminate. A single 'family 0x28' arm catches TrnArrw1/2 but NOT TrnArrw3; a family-0x2D arm would over-trigger Muramasa (src/battle.rs:4477: 0x2d => (1, 6) Muramasa). Chip 26 needs either its own per-id arm (ticket forbids 'match chip.id') or a sub-byte discrimination (attack_power at +0x1a already in chip.power but doesn't change family). Tool budget 80 hard-exhausted on the read. No src/battle.rs edit, no inventory edit, no harness rows. Branch stays unmerged; wt/t91 removed after stamp. Recommended next ticket: T91a (split) -- (a) TrnArrw1+2 land with family-0x28 arm (2 ids verified), (b) TrnArrw3 deferred to a per-id or sub-family arm after the Muramasa conflict is resolved.
**Why.** T46 DONE (Bomb family reads AttackPower +0x1a, merged 85f021c), T48 DONE (Barrier family reads amount from record, merged 079531c), T52 DONE (AirShot id 4, family 0x21). **3 chip families ported as data** out of the 411 record rows; SCOPE M4 record-driven total = **43/411 → 46/411** target on landing. **TrnArrw (ids 24-26)** at `data/ChipDataArr.s:747..871` are unrecorded, family unchanged across 3 ids (codes AFK / GMZ / MSY → ascending-code pattern with wildcard). T57 DONE census (verifier-hyper confirmed 14 record rows + 29 id rows): TrnArrw is in the unrecorded bucket. Cannon (ids 1-3) and Vulcan (ids 5-8) have been tried (T36 PARTIAL, T38 NEGATIVE, T51 NEGATIVE / T54 NEGATIVE) and those families are closed. TrnArrw uses a different element (CHIP_ELEM_AQUA) and a per-id-element + per-id-power pattern that the record carries at byte +0x18 (Element) and +0x1a (AttackPower). The 3 ids can ride ONE record-driven arm — no per-id `match chip.id`. SCOPE **M4** advance: chip row count `43/411 → 46/411` (one per TrnArrw id) on landing.

**New evidence.** T57 DONE census (landed): 14 record-dispatched chips confirmed; 29 id-dispatched chips confirmed; the unrecorded bucket (TrnArrw, FireBrn, BblStar, DolThdr, ElcPuls, RskyHny, RlngLog + others) needs new scenarios. The TrnArrw record at `data/ChipDataArr.s:747..871` shows byte +0x18 = 0x02 (CHIP_ELEM_AQUA) for all 3 ids and bytes +0x1a = 30/40/50 (AttackPower ascending). T46's Bomb-family port shape (cite `data/ChipDataArr.s` per id, +0x1a offset) is the proven mechanism. Cannon family (T36/T38/T51 NEGATIVE) is closed; Vulcan family (T54 NEGATIVE) is closed; TrnArrw is a fresh angle with no prior attempts. Cursor veto is the binding constraint (T51's lesson) — the TrnArrw record-driven port shape must NOT regress cursor from 1/1/170/186279.

**Files.** `tools/states.py` (NEW scenario `trnarrw_select_<24|25|26>` for each id), `tools/harness.py` (NEW 3 rows `chip-trnarrw1`, `chip-trnarrw2`, `chip-trnarrw3` canon_ref=40, negative = no-chip-fire path; reuse `chip-cannon` fixture base + descriptor for picked chip), `docs/coverage/chips.md` (NEW entries for ids 24-26 with the `data/ChipDataArr.s` cite), `docs/worklog/T91.md`. **NOT** tools/allowlist.py, tools/trace.py, tools/inventory.py (re-run for M4 chip row count only), src/chips.rs, reference/bn6f; `src/battle.rs` only if the chip-data Bomb dispatch (T46) needs a new family arm — extend T46's `match chip.family` site with a TrnArrw arm reading +0x18 + +0x1a; **no `match chip.id { 24 | 25 | 26 => ... }` arm**.

**Do.**
1. Baseline, no edit: build ROM, sha256; verify_rows HEAD on 8-row guard set + chip-cannon + chip-bomb (chip-data family rows) → expect all 0/0/N. **measurement.**
2. Read `data/ChipDataArr.s:747..871` for ids 24-26; confirm family byte = same, Element byte +0x18 = 0x02 (CHIP_ELEM_AQUA), AttackPower +0x1a = 30/40/50. Confirm no `match chip.id { 24 | 25 | 26 => ... }` arm in src/battle.rs. **measurement.**
3. Build 3 `trnarrw_select_<id>` recipes in tools/states.py with chip-id 24/25/26 in the picked slot + a fire-cue matched to the chip-cannon scenario's `b` step. Add 3 chip-trnarrw rows in tools/harness.py. **measurement.**
4. Build ROM; run each chip-trnarrw row; expect 0/0/40 with non-blind negative (no-chip-fire path); re-run cursor row from a clean detached checkout. **measurement.**
5. verify_rows on 8-row guard set + chip-cannon + chip-bomb + 3 chip-trnarrw rows; expect all identical to step 1, 3 chip-trnarrw rows 0/0/40, cursor 1/1/170 unchanged. **measurement.**

**Rules.** If `src/battle.rs` already has a record-driven arm for the chip-data Bomb dispatch (T46) AND no TrnArrw-specific arm remains, this is harness-row only. If a per-id `match chip.id { 24 | 25 | 26 => ... }` arm exists in src/battle.rs, port it to a `match chip.family == 0x??` arm reading +0x18 (Element) + +0x1a (AttackPower), per T46's pattern. **No `match chip.id` for these ids.** No allowlist, no patch_sterile, no F47-style scroll broadening. Cursor veto: ≤1/1/170/186300. ≤5 captures, tool budget ≤80.

**Acceptance.** 3 chip-trnarrw rows 0/0/40 with non-blind negatives; 8-row guard set + chip-cannon + chip-bomb identical; cursor 1/1/170/186279 unchanged; SCOPE M4 chip row count `43/411 → 46/411`. Cite `data/ChipDataArr.s:747..871` for each id's record bytes + the dispatch path; if a src/battle.rs edit is required, it carries `file:line` provenance per arm and the regression-on-cursor clause closes the ticket NEGATIVE.

**Measure and report.** rows: 3 chip-trnarrw + chip-cannon + chip-bomb + 8-row guard set + cursor; frames 40 each (cursor 170). Before/after pixel totals, worst, region, ROM sha256+size, fitted count, commit; one line of mechanism; one line unverified.

**Coordinator:** owns tools/states.py + tools/harness.py + docs/coverage/chips.md — pair with T90 (M8 disjoint). Free tier: verify_rows from clean checkout on 12-row set. ≤$0.10 expected, ≤$0.20 cap. Advances **M4**.

### T92. M5 — T87 PARTIAL redo: AIIndex-4 rank recording via the frame-60 lever  *(NEGATIVE -- 2026-09-17, Closed NEGATIVE on wt/t92 [worklog only, worker errored])*

**Result.** Closed NEGATIVE on wt/t92 (worklog only, worker errored). Subagent failed to read docs/worklog/T87.md (T87 OPEN, no worklog) and recovered with scan-T65-directly instruction, but produced no measurable output. No code change, no state recipe, no docs/coverage/mettaur.md update. Recommended next ticket: T92a with explicit instruction to scan T65's records (already on main via 79da4ed) directly without depending on T87.md.
**Why.** T58 PARTIAL (2026-09-16, branch wt/t58 tip 0302084) closed steps 1-4: 452 identity rows → 257 virus rows → 187 distinct (ai_index, version) pairs; ai 0 = 1 pair, ai 1-31 = exactly 6 pairs each; the Mettaur routine rides byte offset 0x04 = ai_index 1, and the live trio NameIDs 0x0001/0x0085/0x2000 are ai 1/7/17 — NOT ai 4. T58 step 5 NEGATIVE for Mettaur v4/v5: CentralArea1 record list at **0x080b4b78** (data/dat30.s:2463), records 12/13 carry record[7]==1 gated by sub_80AA6EC (label at asm29.s:10493), so the lever alone cannot field them. **T58's NEGATIVE closed Mettaur v4/v5 specifically, NOT every ai_index 4 rank.** 5 other ranks at ai_index 4 exist (v0..v5); some in T65's 1076 0xF0-terminated arrays lack the gate and ARE fieldable. T87 OPEN defines the work; this re-proposes it with a fresh ID. M5 advances **1/187 → 2/187**.

**Files.** `tools/states.py` (ONE new `State` recipe `battlestart_ai4_rank<N>` for an N with record[7]==0 — base `/tmp/overworld_net.state` + T58's frame-60 lever at step-2-derived value), `docs/coverage/mettaur.md` (append the AIIndex-4 rank census + lever values), `docs/worklog/T92.md`. **NOT** src/ (zero changes), tools/harness.py (no row added — recording-only), tools/rom_enemy_tables.py, tools/trace.py, tools/oracle.py, tools/allowlist.py, assets/, reference/ (read-only).

**Do.**
1. `python3 tools/rom_enemy_tables.py` → group the 187 (ai_index, version) pairs by ai_index 4; report the six (ai=4, v=0..5) ranks' identity rows + the first BattleSettings record each one appears in, with each record's record[7] gate byte. **measurement.**
2. For each AIIndex-4 rank whose first record has record[7]==0, walk `data/BattleSettings.s` lists and report the record address whose formation names that rank, with bytes read and the lever value the frame-60 must take. **measurement.**
3. Add ONE `State` recipe (base `/tmp/overworld_net.state`, frame-60 lever at step 2's value), build via `python3 tools/states.py build all`. **measurement.**
4. `--watch` it: report chosen BattleSettings pointer, the three populated slots' NameID/version/HP at populating frame, and compare each HP against that version's `off_8109150` `elem_hp` row. **measurement.**
5. 40 frames from two independent builds of the new state diff to **0** pixels; report pixel count and both state hashes. **measurement.**
6. Record the frame at which canon's new enemy first arms an attack (trace/peek read-only); quote field and frame as the alignment event for a follow-up port ticket. **measurement.**

**Rules.** Recording-only: no src/ change, no harness row, no allowlist, no patch_sterile, canon never changes. Only a NEW State entry — no existing recipe's rom/base/script/pokes/frames change, no root state touched (inputs guard stays green). The new state must be rebuildable by `tools/states.py build all`. Every claimed byte cites reference/bn6f file:line or the ROM table. ≤5 captures, tool budget ≤60.

**Acceptance.** At least one NEW `State` recipe (`battlestart_ai4_rank<N>`) builds and fields a non-Mettaur-v0..v3 ai_index-4 rank whose off_8109150 elem_hp matches the populating-frame HP byte-for-byte; 40-frame determinism reads **0 px** across two independent builds; alignment event frame named. docs/coverage/mettaur.md carries the AIIndex-4 rank census + lever values.

**Measure and report.** rows: 7-row guard set unchanged; frames 40 (recording only); two state hashes, both ROM sha256+size, lever value, AIIndex-4 rank identity row, populated slots NameID/version/HP, off_8109150 elem_hp row, alignment event frame, fitted count, commit; one line of mechanism; one line unverified.

**Coordinator:** owns tools/states.py + docs only — pair with T94 (M4, src/battle.rs disjoint); T93 (M8) touches tools/states.py, sequential. Free tier: `python3 tools/states.py build all` from clean checkout, byte-identity of ROM. ≤$0.05 expected, ≤$0.10 cap. Advances **M5**.

---

### T93. M8 — T90a follow-up: formation scenario + harness row from T65 census  *(NEGATIVE -- 2026-09-17, Closed NEGATIVE on wt/t93 [worklog only, worker errored])*

**Result.** Closed NEGATIVE on wt/t93 (worklog only, worker errored). Subagent kept hitting 'read failed' errors on docs/worklog/T87.md (T87 is OPEN, no worklog exists) and failed to recover. No code change, no harness row, no docs/coverage/formations.md. Recommended next ticket: T93a with explicit instruction to read docs/worklog/T90.md (not T87.md) for the BattleSettings + formation + lever measurements.
**Why.** T90 PARTIAL (2026-09-17, landed 98ddac0) closed steps 1-2 (docs-only); the recommended next ticket is T90a with budget ≤150 for the full implementation. T65 PASS 3 (landed 79da4ed) closed M1's formations GAP with **1240 records over 84 lists / 1076 0xF0-terminated formation arrays**; all **0/1076** scenarios recorded. T58 PARTIAL census: **187 distinct (ai_index, version) pairs**; lever model reproduced (60:0x0200a210:0x371 → 886 → mod 12 → record 0x080b4c18, formation Mettaur/Gunner/Mettaur; slots populate at frame 148 with NameID 0x0001/0x0085/0x2000 matching off_8109150 byte-for-byte; **40-frame determinism 0 px across two builds**). **T93 ports one of those 1076 formations to the harness** as the first scenario recording for M8. SCOPE **M8** advance: formations count `0/1076 → 1/1076`.

**New evidence.** T90 PARTIAL result: T87 ai4 rank0 rec0 = 0x080b4334 bytes 00141500ff003800 e2490000 8d470b08 (rec7=0, gate free); formation ptr 0x080b478d quads 00/22/00/00, 11/14/a3/00, 11/26/13/00, f0/00/00/00 (3 quads, matches T87 byte-for-byte); lever 0x373; ROM sha256 a37c1028adb7…0d455ad670 (8 388 608 B). 7 guard rows identical to HEAD (wave/window/opening/chip-cannon/mettaur/windowclose/popup all 0/0/N).

**Files.** `tools/states.py` (NEW `battlestart_<rank>` recipe using T87's lever value + the cited BattleSettings record; base `/tmp/overworld_net.state` + frame-60 lever at T87-derived value), `tools/harness.py` (NEW row `<rank>_formation`: canon_ref=40, `search range(<lever>-2, <lever>+2)`, negative = same route WITHOUT the lever poke), `docs/coverage/formations.md` (NEW — first entry carrying the cited BattleSettings record address + bytes), `docs/worklog/T93.md`. **NOT** tools/allowlist.py, tools/trace.py, tools/oracle.py, tools/inventory.py (only re-run for M8 line update), src/, reference/bn6f.

**Do.**
1. From T87's recipe byte, extract the BattleSettings record address + the chosen `<rank>`'s three-slot formation word (NameID/version/HP triplet) and the record[7] gate byte. **measurement.**
2. Read `data/BattleSettings.s` near the cited address; confirm the record's formation matches T87's byte-for-byte reading and no `match formation_id` arm in src/ exists. **measurement.**
3. Add `tools/states.py:battlestart_<rank>` with base `/tmp/overworld_net.state` + lever value at frame 60 + any required unlock poke; build via `python3 tools/states.py build all`. **measurement.**
4. Add `<rank>_formation` row in tools/harness.py; run it; expect 0/0/40 with non-blind negative (no-lever route produces a different formation). **measurement.**
5. verify_rows on 8-row guard set + `<rank>_formation`; expect guard identical, `<rank>_formation` 0/0/40. **measurement.**

**Rules.** Recording-only at the harness row layer — src/ stays untouched. State file patches are `peeked` provenance. No allowlist, no patch_sterile, canon never changes. The `<rank>` chosen must have record[7]==0 (per T87 + T58). ≤5 captures, tool budget ≤80.

**Acceptance.** `<rank>_formation` 0/0/40 with non-blind negative (frame-shift negative non-zero); 8-row guard set identical; SCOPE M8 formations count `0/1076 → 1/1076`. Cited BattleSettings record address + bytes each carry `file:line` provenance; formation byte-exact vs T58's census + T87's recipe.

**Measure and report.** rows: `<rank>_formation` + 8-row guard set; frames 40 each. Before/after pixel totals, worst, region, lever value, BattleSettings record address, formation triplet, gate byte, ROM sha256+size, fitted count, commit; one line of mechanism; one line unverified.

**Coordinator:** owns tools/states.py + tools/harness.py + docs only; pair with T92 (M5, both touch tools/states.py — sequential). Free tier: verify_rows + `python3 tools/states.py build all` byte-identity of ROM. Verifier for step 1's formation-bytes vs T87 cite. ≤$0.10 expected, ≤$0.20 cap. Advances **M8**.

---

### T94. M4 — T91a split: TrnArrw1+2 (ids 24-25) as data via family-0x28 arm  *(OPEN)*

**Why.** T91 NEGATIVE (2026-09-17, worklog only) refuted the family-shared premise: chip 24/25 share family 0x28 attack_power 40/50; chip 26 TrnArrw3 is family 0x2D (Muramasa's), so it cannot ride the same arm without over-triggering. T91's recommendation is TrnArrw1+2 land with family-0x28 arm (2 ids verified); TrnArrw3 deferred until the Muramasa conflict is resolved. T46 DONE (Bomb family reads AttackPower +0x1a, merged 85f021c), T48 DONE (Barrier family, merged 079531c), T52 DONE (AirShot id 4, family 0x21). **3 chip families ported as data** out of the 411 record rows; SCOPE M4 record-driven total = **43/411 → 45/411** on landing.

**New evidence.** T91 NEGATIVE refutation read (data/ChipDataArr.s:747..871): chip 24 TrnArrw1 codes=GMZ? family 0x28 attack_power 40; chip 25 TrnArrw2 codes=MSY? family 0x28 attack_power 50; chip 26 TrnArrw3 codes=BET? family 0x2D (Muramasa's family) attack_power 60. T46's Bomb-family port shape (cite data/ChipDataArr.s per id, +0x1a offset) is the proven mechanism. Cannon (T36/T38/T51 NEGATIVE) and Vulcan (T54 NEGATIVE) families are closed; TrnArrw is a fresh angle with no prior attempts except T91. Cursor veto is the binding constraint (T51's lesson).

**Files.** `src/battle.rs` (extend T46's `match chip.family` site with a TrnArrw arm reading +0x18 Element + +0x1a AttackPower — ONLY IF no record-driven arm exists for family 0x28), `tools/states.py` (NEW scenarios `trnarrw_select_24` and `trnarrw_select_25`), `tools/harness.py` (NEW 2 rows `chip-trnarrw1`, `chip-trnarrw2` canon_ref=40, negative = no-chip-fire path; reuse `chip-cannon` fixture base), `docs/coverage/chips.md` (NEW entries for ids 24-25 with the `data/ChipDataArr.s` cite), `docs/worklog/T94.md`. **NOT** tools/allowlist.py, tools/trace.py, tools/inventory.py (re-run for M4 chip row count only), src/chips.rs, reference/bn6f; **no `match chip.id { 24 | 25 => ... }` arm**.

**Do.**
1. Baseline, no edit: build ROM, sha256; verify_rows HEAD on 8-row guard set + chip-cannon + chip-bomb → expect all 0/0/N. **measurement.**
2. Read `data/ChipDataArr.s:747..871` for ids 24-25; confirm family byte = 0x28, Element byte +0x18 = 0x02 (CHIP_ELEM_AQUA), AttackPower +0x1a = 40/50. Confirm no `match chip.id { 24 | 25 => ... }` arm in src/battle.rs. **measurement.**
3. If no record-driven arm for family 0x28: extend T46's `match chip.family` site with a 0x28 → (power, element) arm. Build 2 `trnarrw_select_<id>` recipes in tools/states.py with chip-id 24/25 in the picked slot + a fire-cue. Add 2 chip-trnarrw rows in tools/harness.py. **measurement.**
4. Build ROM; run each chip-trnarrw row; expect 0/0/40 with non-blind negative (no-chip-fire path); re-run cursor row from a clean detached checkout (cursor 1/1/170/186279 unchanged). **measurement.**
5. verify_rows on 8-row guard set + chip-cannon + chip-bomb + 2 chip-trnarrw rows; expect all identical to step 1, 2 chip-trnarrw rows 0/0/40, cursor 1/1/170 unchanged. **measurement.**

**Rules.** **No `match chip.id { 24 | 25 => ... }` for these ids.** If `src/battle.rs` already has a record-driven arm for the chip-data Bomb dispatch (T46) AND no TrnArrw-specific arm remains, this is harness-row only. If a per-id arm exists, port to `match chip.family == 0x28` reading +0x18 (Element) + +0x1a (AttackPower), per T46's pattern. No allowlist, no patch_sterile, no F47-style scroll broadening. Cursor veto: ≤1/1/170/186300. ≤5 captures, tool budget ≤80.

**Acceptance.** 2 chip-trnarrw rows 0/0/40 with non-blind negatives; 8-row guard set + chip-cannon + chip-bomb identical; cursor 1/1/170/186279 unchanged; SCOPE M4 chip row count **43/411 → 45/411**. Cite `data/ChipDataArr.s:747..871` for each id's record bytes + the dispatch path; if a src/battle.rs edit is required, it carries `file:line` provenance per arm and the regression-on-cursor clause closes the ticket NEGATIVE.

**Measure and report.** rows: 2 chip-trnarrw + chip-cannon + chip-bomb + 8-row guard set + cursor; frames 40 each (cursor 170). Before/after pixel totals, worst, region, ROM sha256+size, fitted count, commit; one line of mechanism; one line unverified.

**Coordinator:** owns src/battle.rs (if edit needed) + tools/states.py + tools/harness.py + docs/coverage/chips.md — pair with T92 (M5, src/battle.rs disjoint from T92's tools-only path). T93 (M8) touches tools/states.py + tools/harness.py, sequential. Free tier: verify_rows from clean checkout on 11-row set. ≤$0.10 expected, ≤$0.20 cap. Advances **M4**.

