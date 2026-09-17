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
### T70. M1: the Background byte's art mapping — close the backdrops GAP out of the ROM's own record stream  *(DONE -- 2026-09-17, M1 backdrops GAP CLOSED, byte->art mapping measured out of the ROM's own tables [docs/tools-only, zero src/, R)*

**Result.** M1 backdrops GAP CLOSED, byte->art mapping measured out of the ROM's own tables (docs/tools-only, zero src/, ROM byte-identical 5b46337a/584296 B before=after). Reader chain: BattleSettings.Background (+0x4) ldrb at asm21.s:473-475 in sub_8081308; 0xff pre-resolved to map default via pt_808139C[group-0x80][map] (:489/:548-564; weather 0x15; real-world 7); art selected as a TABLE INDEX by sub_8080DA0: off_8080F98[r] (asm21.s:32) -> LoadBGAnimData (asm03_0.s:21209), off_8081220[r] (:36) -> LoadGFXAnims (:37) — never arithmetic. Art: 0x07/0x08 = Comps1/Comps2 bg art, two palette variants (gfx wrapper 0x08616598 = 17 tiles, tilemap 0x08616634 = 32x32, palettes 0x08616760/0x08616EC4; maps' off_806DBD4/off_806DBF0 reuse the same wrappers, maps/Comps1/loader.s:224-227; id 6 = RobotControlComp art :133); 0xff -> pt row group 0x90 = id 9 -> BattleBackdropGFXAnimScript_807FB98 = T22's byte-exact default arena. Live poke: [0x02001b9c] pinned 0x080aee70, +0x4 = 0x08 measured, BG1 k=5 tiles = tile 3 of id-8 blob 0x08616904; 0x07 record @0x080b0d88 (+4=0x07, getBattleSettingsFromList1 asm00_1.s:16046-16062, reachable from asm03_0.s:14612 + asm33.s:16516). Formations: 1045 0x00-quad arrays = dispatch-0 player-spawn slot (spawnMegaMan_80073CC), all 1076 interpreted; inventory backdrops 0/3 -> 3/3, formations 0/1076 (no scenario rows by design). LANDED as c757497 (guard set verify_rows PASS at merged tip, all MATCH, cursor 1/1/170/186279 known tear). Verifier-zai (zai/glm-5.3-flash:high) CONFIRMED all 4 claims: selecting instruction (register chain intact, 12-entry tables, entry 3 unused), art identity (headers 544 B = 17x32, 2048 B = 32x32x2, two-palette variant diff, id-6 art distinct), fielding static bytes (0x080aee74=08, 0x080b0d8c=07), doc consistency (1045 consistent, regeneration byte-identical). Labeling nit from verifier: 5b46337a is the port-build hash, not reference/bn6f/bn6f.gba (a37c1028, 8 MB) — worker's figure was our ROM as the ticket intended. Unverified: palette leg of the 0x08 poke (bank 0 white at dump frame — scripted battle repaints palettes; id7-vs-id8 rests on static tables) and no live poke of 0x07 (both in worklog/T70.md). M8 scheduling unblocked. worker-zai 1 commit 8d21689.
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

- T73 NEGATIVE -- M4: close one whole chip family onto the record — grow AS_DATA_FAMILIES from T57's census, delete that arm's `match chip.id`. Family 0x20 (Recov, 9 ids 154-161+288) is the largest family with every id's behaviour = record byte (RECOV_HP[chip.subfamily])

### T74. M2: the Mettaur's appear→decide edge at k=17 — port the refused-hop store T68 attributed  *(OPEN -- 2026-09-17)*

**Why.** battle_full's first divergence is one store, and T68 caught it. `python3 tools/oracle.py battle_full --both` on main: `enemy_state_action` DIVERGES first **k=17** (canon frame 28) canon=(4,8) rust=(4,10), **458/540**; `enemy_anim` first k=21, **474/540**; mm\_\* first k=250/251/269; rng_cadence 14/540; the 13-field sum is **1370** (T68 step 1, reproducing T49). T68's `--watch 0x0203ab69:1` ground truth over those 540 frames: canon's enemy CurAction is 0x0a for k=0..16, **0x08 at k=17..19**, 0x0b at k=20 (T50's attack edge), 0x02 at k=270, 0x08 at k=303. The k=17 write is PC **0x08011756** — `mov r0,#8; strb r0,[r5,#oBattleObject_CurAction]` in `sub_801171C`'s `loc_8011754` tail (asm/asm00_2.s:5688-5727) — reached from `MettaurHopExec_8109CE6` (asm/asm31.s:170689) through `object_exitAttackState` (0x08011714) on the `object_canMove` refusal that clears `oAIAttackVars_Unk_1a`, the byte our MettaurEntry already carries as `hop_done` (src/objects.rs:254-256, :436-460). We keep hopping; canon stops. Milestone **M2**.

**New evidence.** T68 (PARTIAL, budget exhausted at step 4) landed the store table and the PC; T50 (DONE) proved this file's arms move the field (k=0→k=17); T67 (DONE) landed the attribution method and its trap — `--watch-write` is lossy (14 of ~35 writes), so PCs come from watch-write and values from `--watch` bins.

**Files.** `src/objects.rs` (MettaurEntry's hop/refuse arms); `src/actor.rs` **only** the Action→CurAction mapping in `oracle_fields` (:695-764) if the refused edge needs one; `docs/coverage/battle_full.md`, `docs/coverage/mettaur.md`, `docs/worklog/T74.md`. **NOT** `src/battle.rs`/`src/ai.rs` (T72's), no `tools/` (no new row, fixture or state), no allowlist; `reference/bn6f` read-only.

**Do.** 1. Baseline, no edit: `python3 tools/oracle.py battle_full --both` → quote enemy_state_action/enemy_anim first-k and counts plus the 13-field sum (expect k=17/458, k=21/474, 1370); `python3 tools/gbafix.py $CARGO_TARGET_DIR/thumbv4t-none-eabi/release/bn /tmp/t74.gba` → sha256+size. **measurement.**
2. Read the three cited routines in `/home/box/Code/bn/reference/bn6f`; report the instruction chain from the refused hop to the 0x08 store, and the counter that ends the hop phase (asm/asm31.s:170689-170746, T49's 6-frame motion + `byte_8109F46[0]` cooldown): its init value and decrement site, each at file:line. **measurement.**
3. Canon+rust pair on battle_full's own recipe, `--watch 0x0203ab69:1` (canon) vs the state export (rust) over k=0..40: report both byte series and the lag table (matched frames at lag 0..20) — the table T68 could not compute. ≥300/540 at one lag ⇒ phase offset; else single edge. **measurement.**
4. Port: the refusal path stores CurAction=8 (canon's `sub_801171C` tail semantics) instead of re-arming the hop; counter/mask as named consts with `// provenance:` cites. **code change.**
5. Re-run step 1's oracle and step 3's series, then `python3 tools/verify_rows.py HEAD wave,window,opening,chip-cannon,mettaur,windowclose,cursor --expect cursor=1/1/170/186279`. **measurement.**

**Rules.** No fitted frame counts: if 17 frames is not what the cited counter produces, report NEGATIVE rather than gating on k. `--watch` bins are ground truth, never a lossy WP log. The T56/T73 trap: any code-shape change can move `cursor`; if it reads worse than 1/1/170 the branch stays unmerged with every number reported. No row/fixture/allowlist change, canon never changes. Fresh worktree's `reference/bn6f` is empty. ≤3 captures, tool budget ≤60, one harness command at a time.

**Acceptance.** Engine-core, so a trace target: `enemy_state_action` first divergence at **k≥18** and its count **< 458/540**, 13-field sum **< 1370** (before/after quoted); `enemy_anim` first divergence not earlier than k=21; verify_rows identical on wave,window,opening,chip-cannon,mettaur,windowclose and cursor ≤1/1/170/186279±1px on T56's layout. Pixels are not gated here (battle_full's 10,827,099/35,308/540 is backdrop-dominated, T49). A NEGATIVE landing steps 1-3 (both series, the lag table, the instruction chain) and naming the next lever closes it.

**Measure and report.** row battle_full · frames 540 · both fields' first-k and counts before/after · worst · the diffmask region over k=17..20 · commit · one line of mechanism · one line of what is unverified. Plus the lag table's best lag and matched count, cursor's line, both ROM sha256+size, fitted count (0 or listed).

**Coordinator:** shares `src/objects.rs` with T72 — dispatch **before** T72 or after its verdict; file-disjoint from T70/T71, so it may pair with either. Free tier: verify_rows the guard set from a clean checkout. Verifier for step 2's instruction chain and step 4's "no fitted counter". ≤$0.15 expected, ≤$0.35 cap. Advances **M2**.

---

### T75. M4: the record-driven chip families' unprobed ids onto the scoreboard — src/ untouched so the ROM hash cannot move  *(OPEN -- 2026-09-17)*

**Why.** M1/M4's chips line is **43 / 411**, and that line *is* `tools/scoreboard.py`'s `CHIPS` list (43 entries; `tools/inventory.py:verified_chip_ids()` asserts 43). Each entry is only `(feature-name, chip-hex-id, frames, extras)`: the id gets poked into the hand slot on F5b's `afterdissolve_0x0c` route and the press delivered to AIData, so a new row costs **no src/ change and no ROM change** — the code-size veto cannot fire. T57's census shows the unprobed pool inside the three record-driven families (`AS_DATA_FAMILIES = {0x13,0x15,0x21}`): family **0x15 = 84 ids, 5 rows** (163,177,178,179,180); family **0x13 = 17 ids, 10 rows**, with StepSwrd(81) already riding the dispatch without a row; family 0x21 = AirShot's. Those ids already dispatch on `chip.family/subfamily/power`, so every one that renders as canon does is a verified item bought with captures alone. Milestone **M4**, moving M1's count.

**New evidence.** T57 (DONE) landed the per-family census with each family's record dispatch site (`AIAttackJumptable[0x15] = sub_80EBD9C`, asm/asm31.s:107672; readers asm31.s:107962-107968); T46/T48/T52 (DONE) landed the Bomb/Barrier/AirShot arms on the record bytes; T61 (PARTIAL) re-admitted AreaGrab(163)/Invisibl(177). None of the three added a row.

**Files.** `tools/scoreboard.py` (new entries only; no existing entry's hex/frames/extras touched), `tools/inventory.py` **only** `verified_chip_ids()` and its assert, `docs/coverage/chips.md` (new), `docs/SCOPE.md` (regenerated only), `docs/worklog/T75.md`. **NOT** `src/`, **NOT** `tools/harness.py`/`tools/states.py` (T71's), not `parse_backdrops`/`parse_formations`/`AS_DATA_FAMILIES` (T70's/T62's), no allowlist.

**Do.** 1. Baseline: `python3 tools/inventory.py` → quote the chips line (expect `43 / 411`); `python3 tools/gbafix.py …/bn /tmp/t75.gba` → sha256+size. **measurement.**
2. From `data/ChipDataArr.s` (+0xb attack_family, +0xc subfamily, +0x1a power) enumerate every id with family ∈ {0x13,0x15,0x21} lacking a CHIPS row, and cross each against the src/ table its arm indexes (SWORD_HIT_SHAPE rows, the barrier subfamily-0x04 arm, the airshot arm): id, name, fam/sub, power, and the src line that would run. **measurement.**
3. Activity gate then probe: one canon capture of the same state at `afterdissolve_0x0c` **without** the press pokes (`/tmp/mgba_capture` directly, no tools/ edit) as the empty-hand baseline; then for ≤6 candidates add the entry and run `python3 tools/harness.py --only chip-<name>` — report total/worst/frames, blind or not, and canon-poked-vs-empty-hand Δ (keep only ≥64 px of real activity). **measurement.**
4. Trace per kept row: `python3 tools/oracle.py chip-<name> --both` → first divergence and count on the compared fields (if the tool refuses the row, quote its error and compare the state-export block directly). Drop any row whose trace diverges inside its window. **measurement.**
5. Re-run `python3 tools/inventory.py` + SCOPE: chips line must read `(43+K) / 411` with K = kept rows, assert matching. **tools change + measurement.**
6. Re-run step 1's two commands and the guard set `wave,window,opening,chip-cannon,mettaur,cursor,windowclose`. **measurement.**

**Rules.** Zero src/ edits — the identical ROM hash is the gate. Never keep a row that is not 0/0 with a non-blind negative; never touch an existing row's config to make a new one pass. No new state, arena or allowlist. No inferred coverage: an id whose table row exists but was not captured is reported unprobed, not counted. Fresh worktree's `reference/bn6f` is empty → read `/home/box/Code/bn/reference/bn6f`. ≤30 captures, tool budget ≤60, one harness command at a time.

**Acceptance.** Content ticket: K ≥ 1 new chip rows, each **0/0/N** pixels with a non-blind negative, **no divergence** in the oracle's compared fields inside its own window, and ≥64 px of canon-side activity vs the empty-hand capture; the chips line 43 → 43+K (before/after quoted); ROM sha256 identical to step 1's; verify_rows identical on the guard set with cursor ≤1/1/170/186279. A NEGATIVE landing step 2's full candidate table and step 3's per-id numbers, naming each rejected id's missing shape, closes it.

**Measure and report.** the K new rows + guard set · frames per row (40..113) · total · worst · region · the empty-hand Δ per candidate · commit · one line of mechanism · one line of what is unverified.

**Coordinator:** owns `verified_chip_ids()` in tools/inventory.py only — never beside T70's next pass (same file, both regenerate docs/SCOPE.md). Owns no src/, so it pairs with T74. Free tier: verify_rows the new rows + guard set, re-run inventory yourself. Verifier for step 2's "our arm really runs this id" cross-check and step 3's activity gate (the vacuous-pass risk). ≤$0.30 expected, ≤$0.60 cap. Advances **M4**, then **M1**.

---

### T76. M1/M6: the Navi roster out of the identity tables T12 already walks, and the first scripted record the poked route fields  *(OPEN -- 2026-09-17)*

**Why.** M6 reads "not started" and M1's navis + cybeasts line is **0 / 25** with state FOUND — but the found table is the wrong one. The generated rows (docs/SCOPE.md:732ff) print `act = nullsub_106` for **22 of 25** indexes, `// unnamed: navi-table i…` for **13**, and a struct2 value for exactly one (0x0708, index 11), so no Navi has a pattern routine named. The chain that *does* name per-type routines is already walked for viruses: T12's `byte_80182C4` identity rows (452 = 257 virus + **159 navi** + 36 player, T58 step 1) → `AIThinkTables_8109050` at `ai_index*4` (asm/asm31.s:169395-169401) → the per-type entry (Mettaur's `ForMettaur_8109EF4`, asm/asm31.s:170982, handler table :171011-171031). Running it over the navi rows is what makes M6 writable at all. Milestone **M1**, unblocking **M6**.

**New evidence.** T65 (DONE, 79da4ed) landed the record stream — 84 lists, 1240 records, 1076 formation arrays, 0 terminator mismatches — and separated the two fetch paths: family B (roll-levered) and **family A, the 461 scripted records fetched by index** through `getBattleSettingsFromList0/List1` (asm/asm00_1.s:16046-16062, index*0x10) which the roll cannot reach; T58 (PARTIAL) measured that the chosen BattleSettings pointer sits in `0x02001b9c` from frame 0 of the poked route. Together: a scripted boss battle is deliverable by poke, with no hand-played input (which is what stopped T20).

**Files.** `tools/rom_enemy_tables.py` (extend with the navi walk), `tools/inventory.py` **only** `parse_navis` and its `SECTION_NOTES` entry, `docs/coverage/navis.md` (new), `docs/SCOPE.md` (regenerated only), `docs/worklog/T76.md`. **NOT** `src/`, **NOT** `tools/states.py`/`tools/harness.py` (T71's), not `parse_formations`/`parse_backdrops`/`AS_DATA_FAMILIES` (T70's/T62's), no allowlist; `reference/bn6f` read-only.

**Do.** 1. Baseline, no edit: `python3 tools/inventory.py` → quote the navis + cybeasts line and count the `nullsub_106`/`unnamed` cells in the generated table; gbafix sha256+size (src/ untouched). **measurement.**
2. Walk all 159 navi identity rows: enemy_idx, NameID, HP row, ai_index; then each distinct ai_index's arm in `AIThinkTables_8109050` and its per-type entry at file:line. Report how many navis share an arm with a virus and how many own one. **measurement.**
3. Say what `off_80F24D8`/`off_80F253C`/`off_80F25A0` really are: record stride, the reader that indexes them, and why 22 act slots are `nullsub_106` (cite the reader line that never calls them); name the 13 unnamed indexes from the ROM's own evidence (identity rows, sprite categories, name strings). **measurement.**
4. Join to T65's stream: for every id step 2 classes as a navi, list the family-A records naming it (list addr, record addr, quad slot, the index `getBattleSettingsFromList0/List1` takes), grouped per Navi; report how many of the 25 indexes have ≥1 record. **measurement.**
5. One canon capture (≤2): poke `0x02001b9c` to one of step 4's records on the existing battlestart route and report the chosen pointer, each populated slot's (NameID, HP) from a `--watch` value bin, and whether the object's think entry is the one step 2 predicted — or the named reason none is fieldable. **measurement.**
6. Rewrite `parse_navis` on the measured chain, regenerate SCOPE, re-run step 1: the navis line moved, the ROM hash unchanged. **tools change + measurement.**

**Rules.** Zero src/ — the byte-identical ROM is the gate. No new state file, no harness row, no allowlist. No guessed patterns: a Navi whose routine is not located stays a GAP with its search trail, and the count may go down if the ROM says so. `--watch` bins are ground truth; `--watch-write` is lossy (T67). Fresh worktree's `reference/bn6f` is empty → read `/home/box/Code/bn/reference/bn6f`. ≤2 captures, tool budget ≤50.

**Acceptance.** The generated M1 navis + cybeasts line moves off **0 / 25**: each of the 25 indexes carries a named Navi, its ai_index and think/act entries at file:line, or an explicit GAP row with the trail; the `nullsub_106` count reported before/after; ≥1 family-A record address naming a navi-range enemy id with the index that fetches it, plus step 5's (pointer, slot NameID/HP) reads or the stated reason none is fieldable; ROM sha256 identical before/after. A NEGATIVE landing steps 2-4's tables and showing the navi rows do not go through `AIThinkTables` closes it and names the real pattern source.

**Measure and report.** rows: none (no ROM change) · the navis line before/after and the nullsub/unnamed counts · step 2's arm table size · step 4's records per Navi · step 5's pointer + slot pairs · `git diff --stat` · commit · one line of mechanism · one line of what is unverified (no port, no scenario, no row).

**Coordinator:** tools+docs only, no src/, so it may pair with T74; never beside T70's next pass (same file, both regenerate docs/SCOPE.md) or T71 (tools/states.py). Free tier: run `python3 tools/inventory.py` yourself and diff the generated navis section. Verifier for step 2's arm identification and step 5's slot identity — every M6 ticket buys both. ≤$0.12 expected, ≤$0.25 cap. Advances **M1**, unblocks **M6**.

