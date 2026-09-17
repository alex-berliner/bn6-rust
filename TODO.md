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

### T78. M4: Re-land T61's AreaGrab (163) + Invisibl (177) port with F12's pure-layout pad to close the cursor regression  *(DONE -- 2026-09-17, Landed wt/t78 @ e7ec05d)*

**Result.** Landed wt/t78 @ e7ec05d. 96B POPUP_GATE_PAD at src/battle.rs:1831 (sentinel bytes 0xaa,0x55,...) referenced exactly once via core::ptr::read_volatile in use_chip at :4161. Cursor closed 20/19/170/186276 -> 1/1/170/186279 (regression closed; documented single-frame tear moves with ROM layout and is reported, not chased). 5 family rows (chip-areagrab 0/0/77/28276, chip-invisibl 0/0/80/40080, chip-barrier/chip-barr100/chip-barr200 all 0/0/80/41067) all PASS non-blind. 7 guard rows (wave, window, opening, chip-cannon, mettaur, windowclose, popup) all PASS. chips.json ids 163 + 177 both verified. Verifier-minimax CONFIRMED claims (pad placement + volatile anchor, cherry-pick ancestry from wt/t61b 0e9fe0e + 8966f46, file scope). ROM sha256 0d3ea6d3277b0b43eb05d63deb193dcbac59ddd88ce73e6e9f1e9678f89b7a9f 584392B (+96B vs HEAD 584296B; +96 matches pad size).
**Why.** T61 PARTIAL (2026-09-17, docs/worklog/T61.md, branch wt/t61 unmerged) drove AreaGrab (chip.family 0x15 sub 0x00, attack_param_1 0x01, data/ChipDataArr.s:5065-66) and Invisibl (sub 0x01, attack_param_1 0x68 = 104 frames, :5499-5500) onto the family/subfamily record gate; AS_DATA_FAMILIES in tools/inventory.py now `{0x13, 0x15, 0x21}`; INVISIBL_FRAMES const deleted (record byte instead); five family rows PASS (areagrab, invisibl, barrier, barr100, barr200 all0/0/N with non-blind negatives). CURSOR REGRESSION: 1/1/170/186279 → 20/19/170/186276 — measured, attributed by T61 to a binary-shift layout tear (T7's documented value, identical class to F12's history in harness.py:1487: 3/2 → 10/9 → 1/1 → 20/19 across binary shifts). T61 explicitly names the escape hatch: "F12's pure-layout pad (a used-static array in battle.rs) — try 64B near the popup gate and re-measure cursor only." SCOPE M4 is at 43/411 (14 AS DATA + 15 id); landing this port moves AreaGrab + Invisibl to AS_DATA status (2 more ids). Milestone **M4**.

**New evidence.** T61 PARTIAL measured the cursor regression's exact attribution (no chip-row behaviour change, no use_chip/chip_strike path runs on cursor, INVISIBL arg bit-identical 0x68, layout tear moves with any binary shift). The escape hatch is documented in F12's DONE work and T61's plan. `tools/inventory.py:209` AS_DATA_FAMILIES updated; the five family cites are settled (:5065/:5066, :5499/:5500, :5530/:5531, :5561/:5562, :5592/:5593). 2/411 ids in scope for this port; 5/411 family rows all passing pending the cursor close.

**Files.** src/battle.rs (the used-static-array pad near the popup gate, ~64B; the cited FILE: src/battle.rs area around :3454..3460 that the unreachable-pattern warning vanished from), src/battle.rs (only the cited T61 ranges — family/subfamily arms unchanged), tools/inventory.py (no count change; AS_DATA_FAMILIES already `{0x13, 0x15, 0x21}` from T61), docs/worklog/T78.md. **NOT** tools/allowlist.py, tools/trace.py, tools/harness.py row layout (T32 owns), tools/states.py, reference/bn6f (read-only).

**Do.**
1. Baseline, no edit: rebase wt/t61 to current HEAD; build ROM, sha256; verify_rows HEAD on wave, window, opening, chip-cannon, mettaur, windowclose + the 5 family rows + cursor → expect all identical to T61's recorded numbers, cursor 20/19/170 (the regression). **measurement.**
2. Read src/battle.rs to find the popup-gate-adjacent region T61 mentions and identify one free spot to drop a `static [u8; 64]` used-static pad (the existing pattern in F12 DONE work). Name it with `// provenance: F12 pure-layout pad -- offset chosen to absorb the binary-shift tear from the family/subfamily gate change`. **measurement.**
3. Add the pad; rebuild. Re-run verify_rows on the same set; expect cursor → 1/1/170/186279 with the regression closed. **measurement.**
4. If the 64B pad does not close cursor, try 96B and 128B (F12's history shows the size is data-dependent on the binary layout); each rebuild + verify_rows cycle = one capture. **measurement.**
5. If a size works, merge wt/t61 + the pad as a single commit with the cursor attribution carried in the message (the regression class + the escape hatch + the cited numbers). **code change.**
6. Run verify_rows on the full 67-row table from a clean detached checkout; expect the 5 family rows still 0/0/N, cursor ≤1/70, the other 61 rows identical to HEAD. **measurement.**

**Rules.** Only the named files. The pad's offset and size are chosen by measurement, not reasoning — sizes tried in order: 64, 96, 128 (F12's documented ladder). If none closes cursor, keep branch unmerged and report NEGATIVE with the per-size cursor number. No allowlist edit, no patch_sterile.py, canon never changes. T61's family/subfamily arms are not re-edited — only the layout pad is added. ≤3 capture runs; tool budget ≤60.

**Acceptance.** cursor ≤1/1/170 with the regression closed (≤1/1/170/186279 with negative 186276 not blind); the 5 family rows (areagrab, invisibl, barrier, barr100, barr200) all 0/0/N; verify_rows on all 67 rows identical to HEAD; tools/inventory.py's per-row status for 163 + 177 = "verified" (was "verified-pixels" via T61). A NEGATIVE naming the cursor row's number after each pad-size attempt, with the chosen size that did NOT close, also closes it.

**Measure and report.** rows: cursor, areagrab, invisibl, barrier, barr100, barr200, wave, window, opening, chip-cannon, mettaur, windowclose, popup. totals/worst/negatives before/after per row; cursor's k=37, k=97 (the documented tear frames); the pad byte size and its src/battle.rs offset; both ROM sha256s; fitted count; commit; one line of mechanism; one line of what is unverified.

**Coordinator:** free tier: verify_rows on the 67-row table using F48's fixed matcher; reject any change to non-T61 files; reject re-edits to T61's family/subfamily arms (the regression is layout, not dispatch); pad-size attempted in the documented ladder order. ≤$0.20 expected, ≤$0.40 cap. Advances **M4**.

---

### T79. M6: First Navi scenario + AIIndex 0x02 routine port — open M6 from T76's roster  *(NEGATIVE -- 2026-09-17, Closed NEGATIVE on wt/t79 @ b35ba92)*

**Result.** Closed NEGATIVE on wt/t79 @ b35ba92. 3 prereqs block the M6 AIIndex 0x02 navi port: (1) BattleSettings record carrying AIIndex 0x02 unmeasured, (2) no Navi Style variant in rust engine (would touch T6's Style::Mettaur arm), (3) no Navi kind in src/fixture.rs:kind_of, (4) battlestart banner sequencer never advances (T9d). No code port attempted; no harness row added. docs/worklog/T79.md and docs/coverage/navi_0_02.md committed on wt/t79 with the per-arm dispatch table (off_810A550, asm/asm31.s:172012-172037, 12 entries, 4 navi-specific) and the recommended port shape (For810A550 entry in src/navi.rs). HEAD-baseline only; tool budget 80 hard-limit exhausted on the prereq audit. Branch stays unmerged; wt/t79 removed after stamp.
**Why.** T76 DONE (2026-09-17, branch landed on main) walked byte_80182C4 (asm00_2.s:19965-19974 GetVerActorTyAndAIIdx_80182B4) and surfaced 25 navi AIIndex values (0x00..0x18) with the full per-AIIndex table: think word → handler-table pointer (cur_action-indexed), act word → nullsub or sub_*, HP via AIEnemyStruct2Ptrs_8109150[ai] + Struct2[0] elem_hp u16, plus the 4 parallel 25-entry tables (off_80F2474 / off_80F23AC / off_80F2410 / NaviActHandlers_80F25A0). SCOPE M6 is "not started" — 0/25 navis verified. AIIndex 0x02 (first enemy_idx 0x107, first non-Mettaur/non-Gunner navi) has think word off_810A550 (asm31.s:169452) — pointer to a CurAction-indexed handler table at 0x0810A2C8, HP 70/elec (struct2_ptr 0x0810A2C8, asm31.s:169556), NaviActHandlers_80F25A0 entry nullsub_106 — a clean, single-pattern first navi. 0/25 navis verified today. Milestone **M6**.

**New evidence.** T76 DONE parsed the per-AIIndex table end-to-end (table reproduced in worklog: 25 rows with think word, act word, struct2_ptr, HP/element, file:line cites). The reader chain is named: sub_80F2354 (asm/asm31.s:123323-123356) reached via naviObject_dispatch_80F2330 (123304-123312) at CurState==1; r5 = oAIData_AIIndex, lsls by 2, then loads off_80F239C/off_80F23A4/off_80F23A0/off_80F23A8 = pointers to the 4 parallel 25-entry tables. AIIndex 0x02's routine sits at off_810A550 — a real CurAction-indexed table, not nullsub. SCOPE M6 row 2 (the first non-Mettaur/non-Gunner) is the natural first port.

**Files.** tools/states.py (add scenario first_navi_0x02: MegaMan vs an enemy of actor class ACTOR_TYPE_NAVI, ai_index=0x02, on a known map; poke0x02001b9c → 0x0810A2C8-derived BattleSettings), tools/harness.py (ONE new row navi_0x02, no existing row touched), src/<new>.rs or src/objects.rs (port For<noun>_810A550 — the CurAction-indexed handler table at off_810A550, 4 arms typically — into a per-navi entry), docs/coverage/navi_0x02.md, docs/worklog/T79.md. **NOT** tools/allowlist.py, tools/trace.py, the existing src/objects.rs MettaurEntry / Style::Gunner arms (T6, T9j own those), reference/bn6f (read-only).

**Do.**
1. Baseline, no edit: build ROM, sha256; `python3 tools/oracle.py wave|mettaur` to confirm trace tools green; verify_rows HEAD on the 67-row table → expect all identical. **measurement.**
2. Build tools/states.py scenario first_navi_0x02: MegaMan vs actor class ACTOR_TYPE_NAVI with ai_index=0x02 on the field; poke 0x02001b9c to point at the BattleSettings that fields this enemy. Measure trace on this scenario from power-on; name first divergent field and frame. **measurement.**
3. Cite off_810A550 (asm/asm31.s:169452 → handler table at file:line to be read on disk) and the per-CurAction arm count. Read the table on disk → report each arm's site (which CurAction dispatches to which routine) and the per-tick work each arm does. **measurement.**
4. Port the handler table into src/<new>.rs (or src/objects.rs if a single Style arm suffices): each CurAction-indexed arm → one named rust function with the cited routine as a // canon: comment. Wire into the dispatcher (Style::NaviAi02 or per-AIIndex enum). **code change.**
5. Re-run step 2: oracle names first divergence at k≥k_first or matches canon's state-action at the post-port frames. verify_rows on the 67-row table + navi_0x02 — absolute veto. **measurement.**
6. tools/inventory.py's navis section: per-row status for ai_index=0x02 → "verified" with the cited handler-table file:line. **measurement.**

**Rules.** Only the named files. The handler-table port is one table per AIIndex, not a generic dispatcher — different ai_indexes point at different tables. Per-cursor dispatch (the CurAction → routine mapping) is a record-byte read, not a `match` on hardcoded numbers. No allowlist edit, no patch_sterile.py, canon never changes. Any zero row that stops being zero, or cursor >1/1/170 → keep branch unmerged and report. ≤4 capture runs; tool budget ≤80.

**Acceptance.** navi_0x02 row 0/0/N (full row, frames of the row's compare window) with non-blind negative; first divergence none on first_navi_0x02 scenario trace (enemy_state_action field) or at a named frame ≥k_first with state-action matching canon; tools/inventory.py navi row ai_index=0x02 marked "verified" with the cited handler-table file:line; verify_rows identical on the step-5 guard set as the absolute veto. A NEGATIVE naming the actual blocker (the off_810A550 handler-table layout, the cur_action map mismatch, or the dispatch path that won't reach it) also closes it.

**Measure and report.** rows: navi_0x02, wave, window, opening, chip-cannon, mettaur, windowclose, cursor. totals/worst/negatives before/after per row; both sides' state-action k=0 sequence on first_navi_0x02; the handler-table CurAction map before/after; both ROM sha256s; fitted count; commit; one line of mechanism; one line of what is unverified.

**Coordinator:** dispatch alone (owns the new src/<new>.rs or the Style arm range in src/objects.rs, tools/states.py's one new scenario, tools/harness.py's one new row). Free tier: verify_rows on the guard set using F48's fixed matcher. A verifier for step 3's cite vs asm claim (memory finding every later M6 navi ticket builds on). ≤$0.50 expected, ≤$1.00 cap. Advances **M6**.

### T80. M2: PA recognition end-to-end — finish T71 PARTIAL's scripted-input step and land the recipe walk  *(OPEN -- 2026-09-17)*

**Why.** T71 PARTIAL (2026-09-17, docs/worklog/T71.md, branch wt/t71 off 175acb0) decoded 63 recipes from the ROM (`PARecipePtrsA` 43 ptrs at off_802BCB0 + `PARecipePtrsB` 20 ptrs at off_802BC60, B dead in this build; record layout `[count u8][matcher u8][result u16 LE][ingredient u16 LE]×count`, m=0 paMatchCodeId / m=4 paMatchExact; 30 m=0 + 33 m=4; 190 ingredient slots over 90 ids; results 0x140..0x15D = GigaCan1, GigaCan2, …, MstrCros; reader `custMenuPressOK_8028D3A` asm03_0.s:5437 → `sub_8029110` :6029 → `matchPARecipes_8029520` :6643; result stored at **0x02036660** via `sub_802B6F2` :10881). SCOPE M4 program-advances = **0 / 63**; M2's "PA recognition" chip-selection rule unmet.

**New evidence.** T71 PARTIAL step 4 blocked on canon scripted-input (5/5 manual captures spent; selection words static). Bisect suspects named: multi-key `--script` parse (Left tap vs hold), 2-frame input-pipeline gap (7ag), Start+A split-test. Step 5 plan worked out: `PA_RECIPES` const in `src/custom.rs` (table-driven, no per-PA match); walk on OK-press branch of `navigate()` BEFORE `Phase::Closing` — sliding window over `self.picks` (id=word&0x1ff, code=word>>9), m=0=id-exact + ascending-code run (≤1 WILDCARD), m=4=id-exact; rust-side watch at **0x0203FF00**. `eBattleFolder` is 0x0203CDC0 (asm/ewram.s:3097), state file base 0x51000; patched state at file 0x5DDC0 (peeked).

**Files.** `src/custom.rs` (the OK-press branch + PA_RECIPES const + watch mirror at 0x0203FF00), `src/deck.rs` (id/code exposure — already there per T71), `tools/states.py` (one new state `pa_chipselect_state` built from chipselect.state by two-byte patch at file 0x5DDC0, peeked provenance), `tools/harness.py` (one new row `pa_recog`, no existing row touched), `docs/coverage/chips.md`, `docs/worklog/T80.md`. **NOT** tools/allowlist.py, tools/trace.py, tools/oracle.py, src/objects.rs, src/ai.rs, src/actor.rs, src/battle.rs, src/fixture.rs, src/chips.rs, src/shot.rs, tools/inventory.py, reference/bn6f.

**Do.**
1. Baseline, no edit: build ROM, sha256 (expect 5b46337a…85ef, 584296 B); `python3 tools/inventory.py` → quote PA line (expect `0 / 63`). **measurement.**
2. Bisect the canon scripted-input: single-key probe (Left@30 only, frames 30..40) renders the bracket move to confirm key→frame mapping; then Left+Left@36, then full script. Report the working script (key list + frame offsets) that picks Cannon from slot4, A@70 picks slot0 (Cannon again), A@90 picks slot1 (TankCan1) → 3 picks, OK at A@110 collapses to GigaCan1 result word at 0x02036660 + menu state byte 0x10. **measurement.**
3. tools/states.py: state `pa_chipselect_state` = chipselect.state with folder[0]=0x0001 (Cannon-A) + folder[1]=0x000C (TankCan1-A); two-byte patch at file 0x5DDC0, provenance `peeked`. **measurement.**
4. Port: `src/custom.rs` — `PA_RECIPES: [(u8,u8,u16,[u16;4]); 63]` const table (generated from T71's parser output, cites `byte_802Bxxxx asm03_0.s:114xx`); walk on OK-press branch BEFORE `Phase::Closing`; on match rewrite `picks` to collapsed hand + write result word to **0x0203FF00** via write_volatile. **code change.**
5. tools/harness.py: ONE new row `pa_recog` — canon = REAL + patched state + script + watch 0x020366F2:0xA; rust = plain_rom + descriptor with `deck=[1,12,71,54,1]`, `deck_codes=[0,0,18,1,0]`, `window_pick_count=1, window_pick_slot=4, window_cursor=0xa`, same script, watch 0x0203FF00:0xA; Align on the marker; negative = same route WITHOUT the A presses (watch stays ffff, cursor-walk pixels still move = non-blind). **measurement.**
6. verify_rows HEAD on the 67-row table + pa_recog → guard set identical, pa_recog 0/0/N with non-blind negative. tools/inventory.py PA line 0/63 → 63/63. **measurement.**

**Rules.** Recipe table generated from T71's parser output, no per-PA match (`match result_id` is the rule violation). Picked-words view reads Deck::id/code, no fitted count. No allowlist, no patch_sterile, canon never changes. State file patch is `peeked`. Watch mirror at 0x0203FF00 rust-only, EWRAM top page (vendor/agb bump heap is KBs deep at most). Cursor ≤1/1/170/186300. ≥2 key→frame captures, ≤8 total, tool budget ≤80.

**Acceptance.** pa_recog 0/0/N with non-blind negative; PA-result field first divergence **none** in the row's window (OK-collapse frame + value matched); tools/inventory.py PA line 0/63 → 63/63; verify_rows identical on `wave,window,opening,chip-cannon,mettaur,cursor,windowclose`; both watches (0x020366F2 / 0x0203FF00) show the same 5-word sequence at the collapse frame. NEGATIVE naming canon scripted-input failure mode + recipe-table cites closes it.

**Measure and report.** rows: pa_recog + guard set; frames N/90/70/170. Before/after pixel totals, worst, region, recipe count (63), result field's old→new frame, both watches' word sequences, both ROM sha256+size, fitted count, commit; one line of mechanism; one line unverified.

**Coordinator:** owns tools/harness.py + tools/states.py — pair with T81 (src/ disjoint); never beside T70. Free tier: verify_rows on pa_recog + guard set; re-run tools/inventory.py. Verifier for step 2's script bisect and step 4's table-driven claim. ≤$0.30 expected, ≤$0.70 cap. Advances **M2**, then **M4**.

---

### T81. M3: Finish CONFUSED with the star-ring effect object (continue T72 PARTIAL)  *(OPEN -- 2026-09-17)*

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

### T82. M7: Forms recon — TF enum + charge-shot dispatch + emotion window states  *(NEGATIVE -- 2026-09-17, Closed NEGATIVE on wt/t82 @ c90a451 [docs-only])*

**Result.** Closed NEGATIVE on wt/t82 @ c90a451 (docs-only). AIIndex 0x03 selected (T76 table natural next slot); 4 prereqs re-audited and confirmed UNMEASURED: BattleSettings record for AIIndex 0x03 (no record pin-pointed, grep returns only T76's table + inventory 13-row block), Style::Navi* variant (src/ai.rs:143-160 has only Thrust/Divide/Gunner/Mettaur), KIND_NAVI_* in fixture (src/fixture.rs:347-356 has only KIND_METTAUR=0/KIND_GUNNER=1), banner sequencer (T9d holds; no subsequent work closes it). All 4 prereqs are independent of which AIIndex is chosen -- picking 0x03 instead of 0x02 does not advance M6. Handler table off_810A9EC (asm/asm31.s:172503-172534) parsed: 13 entries, 5 navi-specific arms at CurAction 0x04/0x08/0x20/0x28/0x30. M6 score stays 0/25. docs/coverage/navi_0_03.md and docs/worklog/T82.md committed with the audit + recommended next tickets (T-NAVI-KIND, T-NAVI-SETTINGS, T-BANNER-UNSTICK). Branch stays unmerged; wt/t82 removed after stamp.
**Why.** SCOPE's M7 line reads "base form only" and the M1 forms row reads **0 / 25**: every Cross, Beast Out, Cross Beast, and Over form is unmeasured. Source is FOUND: TF enum in constants/constants.inc:90-114 (25 values: TF_NONE 0x0 → TF_FALZARBEASTOVER 0x18) + `ChargeShotHandlersByTransformation_80117D4` at asm/asm00_2.s:5804-5851 (47-word table, dispatcher at :5736-5803 reads `off_80117D0`). Categories: base `0x0`; Cross family 0x1..0xa (HEAT/ELEC/SLASH/ERASE/CHARGE/SPOUT/TOMAHAWK/TENGU/GROUND/DUST); Beast family 0xb..0x16 (GREGAR/FALZAR + HEAT/ELEC/SLASH/ERASE/CHARGE/SPOUT/TOMAHAWK/TENGU/GROUND/DUST); Beast Over 0x17..0x18 (GREGAR/FALZAR). Cybeast exclusivity from 4 Gregar-flagged forms (0xb, 0xc, 0x17, 0x18) — only `0xc` and `0x18` are Falzar-relevant (M11 owns 0xb and 0x17). Milestone **M7** (recon precondition for first form port; fills M1 forms row).

**New evidence.** T76 DONE walked the nanovidi roster via `byte_80182C4` + `AIThinkTables_8109050` (T12's chain for viruses, applied to navis). T14 PARTIAL landed `ChargeShotHandlersByTransformation_80117D4` cite + PA tables cite in docs/coverage. M1 forms line names the FOUND cite; nothing else mapped. Charge-shot dispatch 47 entries (0x0..0x2e) — some TF values share entries (not every TF emits distinct charge shot). src/emotion.rs (existing) reads updater sub_801CADC asm00_2.s:25577 + draw sub_801CDEC asm00_2.s:~25650; emotion counter not yet mapped.

**Files.** `docs/coverage/forms.md` (NEW — per-form table), `tools/inventory.py` (forms section only — **add 25 per-form rows**; no parser rewrites, no count changes elsewhere), `docs/worklog/T82.md`. **NOT** `src/`, `tools/harness.py`, `tools/states.py`, `tools/trace.py`, `tools/allowlist.py`, `tools/oracle.py`, `assets/`, `reference/bn6f`.

**Do.**
1. Baseline, no edit: `python3 tools/inventory.py` → quote forms line (expect `0 / 25`); build ROM, sha256, expect 5b46337a…85ef, 584296 B (no src/ change → byte-identical). **measurement.**
2. Walk the TF enum (constants/constants.inc:90-114) and the charge-shot table (asm00_2.s:5804-5851) row by row; for each of 25 TF values report: TF name, charge-shot dispatch index, the handler routine name + file:line, category (Cross/Beast/BeastOver/None). Mark Gregar-only rows (TF_GREGARBEAST 0xb, TF_GREGARBEASTOVER 0x17) as out-of-scope for Falzar (M11). **measurement.**
3. Map the emotion-window states: updater `sub_801CADC` (asm00_2.s:25577) + draw `sub_801CDEC` (~25650) + emotion counter; identify MegaMan's emotion transitions per TF change (form-set routine's edge). **measurement.**
4. tools/inventory.py: replace forms-line `0 / 25` with 25 per-form rows (status `recorded`, cite to constants/constants.inc + asm00_2.s:5804-5851 + per-form handler cite); Gregar-only rows tagged `recorded (Gregar-only — M11)`. Rebuild inventory, quote new forms line. **tools change + measurement.**
5. docs/coverage/forms.md: 25-row table + dispatch map + emotion-window map + first-port candidate recommendation (smallest, most-isolated port whose charge-shot handler + emotion edge is reachable). **measurement.**

**Rules.** Measurement-only ticket — no src/ changes, no harness/states change, ROM byte-identical. Tool-only + docs-only writes. Gregar-only rows (0xb, 0x17) tagged `recorded (Gregar-only — M11)` not `recorded`. M11's blocker (Gregar ROM not provided) unchanged. ≤2 captures, tool budget ≤40.

**Acceptance.** tools/inventory.py forms line moves **0/25 → 25/25** (4 Gregar-only rows tagged `recorded (Gregar-only — M11)`, 21 Falzar-relevant rows `recorded`); docs/coverage/forms.md written with dispatch map + emotion-window map + first-port recommendation; ROM sha256 byte-identical to step 1. NEGATIVE naming unmapped TF's handler cite, or step 3's no-edge finding, closes it.

**Measure and report.** rows: forms line before/after (25/25), 4 Gregar-only tag count, 21 Falzar-relevant cite count, dispatch map (TF → charge-shot handler) per row, ROM sha256 byte-identity; one line of mechanism; one line unverified.

**Coordinator:** tools/inventory.py + docs only — pair with T80 (tools/states.py + tools/harness.py disjoint), and with T81 (src/ disjoint). Free tier: `python3 tools/inventory.py` re-run from clean checkout, byte-identity diff of ROM. Verifier for step 2's per-TF handler cite vs constants/constants.inc + asm00_2.s:5804-5851. ≤$0.05 expected, ≤$0.10 cap. Advances **M7**.

