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

### T105. M7 emotion window: pick one reachable emotion state (Full Synchro via Counter Hit, or any pre-battle-set state) and port its face-selection gate  *(OPEN -- 2026-09-17, Pass 6 [branch wt/t105-emotion e0c35c9, NOT merged]: BLOCKED within the ticket file list, by measurement)*

**Result.** Pass 6 (branch wt/t105-emotion e0c35c9, NOT merged): BLOCKED within the ticket file list, by measurement. Calibration valid: pure main on the worker tree reads cursor 1/1/170 (single 1px frame k=97, marker origin 8/offset 237) = coordinator's HEAD numbers. Bisect table (each step rebuild + cursor): S1a main+fixture.rs emotion field only = 38/19/170; S1 = S1a + main emotion.rs/asset = 38/19 (tools exonerated); B0 full branch afa348a = 29/28/170 (main's k=97 1px tear intact, NEW 28px damage at k=37, x49..238/y1..7 index-consistent recolor slivers, canon-rust pairing +-1 frame checked at 4698/2502px); S2 fixture byte-identical to main (field deleted) + battle.rs gate reads enemy_action at enemies==0 (the +63 disambiguation FIXED, byte-identical fixture) = 62/56/170 with the seam moved to NEW frame k=7 (56px). Mechanism named: the cursor window's mid-frame VRAM copy-drain seam frames (k=97 = F3 documented sub-frame seam, k=37 = 4->3 slot transition, k=7) re-roll pixel phases with ANY binary-footprint change (code addresses, struct size, asset placement); the 1/1 class is a layout-calibrated coincidence (F26b already saw 2/2<->1/1 across trees). All three ticket candidates measured dead (asset layout subsumed; +63 read exonerated by S2; tools exonerated by S1a==S1, OR-write byte-identity). emotion_syn stays PASS 0/0/40/644 on the branch (recipe unchanged). Final ROM afa348a 592404B sha256 f488955c. verify_rows from clean checkout (coordinator, e0c35c9): all 10 rows MATCH (guard set + popup PASS, emotion_syn PASS 0/0/40/644, cursor FAILED 29/28/170/186277 reproducing). Only remaining knob = a measured seam-phase pad at the custom-screen tile drain (battle.rs/cust.rs/main.rs -- outside this ticket's file list); re-rolling binaries to land seams in class rejected as a landmine. Follow-up ticket text in docs/worklog/T105.md pass 6. M7 stays 0/25 on main; emotion port complete and verified on branch, blocked from landing only by the cursor row's phase calibration.
**Result.** Pass 5 (branch wt/t105-p5 cb34c79, NOT merged -- cursor regressed): emotion_syn now PASS 0/0/40/644 with non-blind negative (row v3 = popup recipe verbatim + canon poke 0x020340b2:0x0001 [Unk_32, enum 1 -> byte_801E6F4 slot 2] + rust descriptor emotion=2). Pass-4 failure explained by measurement: (1) canon fires the resumed cast at ref 43 regardless of the dropped A press; (2) Anger is CONSUMED by that cast, reverting to calm exactly at align ref 43; (3) Anger also tints field panels (766->635 px, y92..150) -- Unk_32 (and spare Unk_36/slot 4) are face-only: 694 px in box x0..48/y18..34, 0 elsewhere, holds past 43. FACE_INDEX renders slot 2 byte-exactly; only a comment changed in src; ROM 592404B sha256 39a40d49; fitted 16 / derived 434 / peeked 146. verify_rows from clean checkout (coordinator-confirmed): opening 0/0/40/86591, mettaur 0/0/70/41734, cannon 0/0/40/9505, buster 0/0/28/3167, chip-use 0/0/30/7768, wave 0/0/90/3840, windowclose 0/0/40/207166, popup 0/0/80/1288, emotion_syn 0/0/40/644 -- all MATCH/PASS; cursor FAILED 29/28/170/186277. CURSOR REGRESSION CONFIRMED vs main: HEAD (c15c570) reads 1/1/170/186279 this session (fresh captures), branch reads 29/28/170/186277 deterministic (3x) -- not capture jitter (negative totals jitter only ~2), not the layout-tear class (29 frames). Landing vetoed: a surface got worse. Cursor 'jitter' question closed: pass 2's 186279 negative was a wrong claim. Trace item unsatisfiable as written: trace block carries neither the emotion byte nor OBJ tiles; emotion_syn_full's 4 diverging fields are constant fixture-shape (enemies:0 arena vs canon leftover deleted-enemy RAM needed by battle.rs +63 disambiguation -- out of ticket scope; mm_state_action 21 vs 8 pixel-identical). NEXT PASS (blocker first): bisect cursor regression on wt/t105-p5 -- candidates (a) emotion.bin 1408->7160B ROM/RAM layout shift, (b) fixture descriptor emotion field at +63, (c) row/scenario change; restore cursor to 1/1/170 class, then land (acceptance then fully met except the trace item, which should be re-worded to the pixel row + a named watch, not chase battle.rs). M7 emotion window 0/25 -> 1/25 on the branch only.
**Result.** Pass 4: recon corrected by measurement -- 0x0203528F is only the draw gate (poking it changes no pixels); face identity is re-uploaded every frame by sub_801CB38 from possiblyGetBattleEmotion_8015B64: Anger!=0 (AIData+0x34, 0x020340B4) -> enum 3 -> face slot 1 via byte_801E6F4; each face has its own palette. Landed on branch wt/t105-emotion (2e1e608+e5ab898, NOT merged): exporter v2 (full 23-face bank 0x1900 + 23 palettes at canon offsets), src/emotion.rs port (FACE_INDEX[23], skip 5/6, per-slot palette), descriptor emotion at +63 gated on enemies==0, emotion_syn row + emotion_syn_full scenario, assets/emotion.bin 7160B. verify_rows (clean checkout, e5ab898): opening 0/0/40/86591, mettaur 0/0/70/41734, cannon 0/0/40/9505, buster 0/0/28/3167, chip-use 0/0/30/7768, wave 0/0/90/3840, windowclose 0/0/40/207166, popup 0/0/80/1288 -- all PASS (calm face byte-exact through the new port); emotion_syn FAILED 106001/3161/40/109779 (deterministic, ~4x one face, not merely wrong art); cursor FAILED 29/28/170 (veto 1/1/170 not met; negative total measured 186277 vs claimed 186279). Acceptance not met, cursor surface worse -> branch kept unmerged, worktree removed. Next pass (worklog has ordered plan): probe.py diff canon-poke vs canon-calm in x0-48/y18-34 attributes everything; then face-box vs asset-decoded slot-1 art; check cursor negative jitter. M7 stays 0/25.
**Result.** Poke mechanism discovered: --poke at 0x0203528F:0x01 does NOT set the byte (poke rounds to half-word 0x0203528E so the high byte lands at 0x0203528F and gets masked). Workaround verified: --poke 0x0203528E:0x0100 (16-bit half-word where high byte=1, low byte=0) sets byte 0x0203528F to 0x01 cleanly. LZ77/BitUnPack of eStruct2035280 is per-init only (BIOS CpuSet at PC 0x00000240, 18 word-aligned writes covering 0x02035280..0x020352BC, all at frame 0) -- so the poke persists through the 40-frame compare window. Plain ROM sha256 0d3ea6d3 584392 bytes; 7-row guard set isolated PASS; cursor 1/1/170/186279 within veto. Steps 3-5 not done -- tool budget (120) exhausted after baseline + poke mechanism confirmation. M7 emotion window stays 0/25 (no row added, no src/emotion.rs change). Branch wt/t105-emotion at bb5c01a (worklog-only). verify_rows PASS at HEAD reproduces the guard set + cursor. Multi-pass stays OPEN; next pass needs (a) emotion_syn_full State with --poke 0x0203528E:0x0100 (16-bit half-word), (b) emotion_syn Check row, (c) emotion_export.py extended to 23 face slots (0x1B30 bytes), (d) assets/emotion.bin extended, (e) src/emotion.rs port with FACE_INDEX honoring skip values 5/6.
**Result.** Baseline measured on canon: plain ROM (sha256 0d3ea6d3, 584392 bytes); 7-row guard set isolated PASS (opening 0/0/40, mettaur 0/0/70, cannon 0/0/40, buster 0/0/28, chip-use 0/0/30, wave 0/0/90, windowclose 0/0/40); cursor 1/1/170/186279 within the ≤1/1/170/186300 veto; --watch 0x0203528F reads 0x00 across 40 frames from battlestart.state on canon (calm baseline confirmed). Steps 3-5 not done -- tool budget (80) exhausted at step 2. M7 emotion window stays 0/25 (no row added, no src/emotion.rs change). Branch wt/t105-emotion 812f438 worklog-only; verify_rows PASS reproduces the guard set + cursor. Multi-pass stays OPEN; next pass needs tools/states.py emotion_syn_full scenario, tools/harness.py emotion_syn row, tools/emotion_export.py extended to 23 face slots (0x1B30 bytes), assets/emotion.bin extended, src/emotion.rs port with FACE_INDEX honoring skip values 5/6.
**Result.** Worker recon only (worklog-only commit). Emotion byte 0x0203528F, face bank off_801CD08 (23 entries), draw routine drawEmotionWindow_801CDEC, value 1 chosen for test. Budget exhausted before baseline/capture. Worklog already on main from prior run (8c792c1 was an empty add). M7 emotion window stays 0/25 (no progress on row yet, no row added).
**Result.** Recon only, from disassembly (worker-zai via prior run, unstamped until now): emotion byte = eStruct2035280+0xf = 0x0203528F (asm00_2.s:27649); draw routine drawEmotionWindow_801CDEC skips face when val==5||6; face bank off_801CD08 = 23-entry table, stride 0x180, shared 0x80-byte right half dword_872D914; vals 15..19 alias 5..9. No code change, no capture, NOTHING verified by pixels. Follow-ups named in docs/worklog/T105.md: baseline capture with --watch on 0x0203528F, descriptor-buffer 64->66 or overlay decision, emotion_export.py full 23-face bank (0x1B30 bytes), src/emotion.rs port with FACE_INDEX, honor skip values 5/6. Branch wt/t105-emotion kept worklog only; not merged.
**Why.** src/emotion.rs:11 explicitly says **"Only the calm face is drawn. The ROM's bank continues past it with one window per emotion, which this build has no state to choose between yet."** The draw routine is `sub_801CDEC` (asm00_2.s:27554-27583, HUD element 14) handing `sub_802FE28` packed pairs `0x80004012 / 0xCBB4` and `0x40200012 / 0xCBBC` — two OBJ tiles, palette bank 12, priority 2, positions `(0,18)` and `(32,18)`; the art+palette export is `tools/emotion_export.py` writing `assets/emotion.bin` (BNEM header at +0x00..+0x0c, face data at offset named by header). SCOPE M7 emotion reads 0/25 (the form row is 0/25 separately; emotion is its own sub-row in M7 prose). The emotion value byte lives near the navi's stat block (cite-able through `GetCurPETNaviStatsByte` callers in asm37_0.s). **No ticket has ported a non-calm face** (grep TODO/TODO_ARCHIVE for "emotion" returns only the T102 prose cite and existing row notes). T102 (proposed) targets the counter-hit grant; this ticket is the render gate's complement: a +1NCP-style poke to the emotion byte is enough to flip the face in a scenario with no hand-played input (the poke is the fixture, canon never changes — F5b's rule).

**Files.** `src/emotion.rs` (the face-selection gate, choose face index from emotion value; one const table per reachable state), `assets/emotion.bin` (verify face offsets per emotion value; no redraw, only re-layout), `src/fixture.rs` (descriptor emotion field), `tools/states.py` (ONE scenario `emotion_syn_full` = `battlestart.state` + poke `60:<emotion_addr>:0xNN` + scripted none), `tools/harness.py` (ONE row `emotion_syn`: canon_ref=40, negative = same scenario WITHOUT poke), `docs/coverage/emotion.md` (NEW), `docs/worklog/T105.md`. **NOT** src/battle.rs, src/objects.rs, src/ai.rs, src/chips.rs, tools/trace.py, tools/oracle.py, tools/allowlist.py, tools/inventory.py, tools/mgba_capture.c, reference/bn6f.

**Do.**
1. **Recon:** read the BNEM header at `assets/emotion.bin` + every face's offset/width/height (currently 1 face, calm); cite each face's data start; find the emotion-state byte (cite file:line — likely one of the NCP-settable stats or a separate byte near the navi struct); confirm the emotion byte's reachable value list from canon's NCP set or from sub_801CADC (asm00_2.s:25577 updater). **measurement.**
2. Baseline, no edit: build ROM, sha256 + size; verify_rows 7-row guard set + cursor → 0/0/N ×6, cursor 1/1/170; capture the existing chip-cannon scenario, read OBJ tiles at (0,18) and (32,18) — both sides should be the calm face. **measurement.**
3. Add `emotion_syn_full` + the `emotion_syn` row (canon = REAL + emotion poke; rust = plain_rom; negative = same scenario WITHOUT poke → both sides stay calm, pixels match step 2). **code change + measurement.**
4. Port the face-selection gate in src/emotion.rs: read emotion-state byte (peeked address), index into a `const FACE_INDEX: [u8; N]` table keyed by emotion value; rebuild, sha256. **code change + measurement.**
5. Re-run: `emotion_syn` 0/0/40 with non-blind negative (no poke → calm face, both sides match step 2; poke → non-calm face, both sides render it); trace `emotion_syn_full`: the emotion byte AND the OBJ tile at (0,18)/(32,18) first divergence **none** over the row's frames; guard set + cursor identical to step 2. **measurement.**

**Rules.** Art from canon bytes, not redrawn (the BNEM export is already data). The FACE_INDEX table is cited from canon's per-emotion draw site. State/descriptor poke carries `peeked` provenance. Cursor veto ≤1/1/170/186300. No allowlist, no patch_sterile, canon never changes. ≤6 captures, tool budget ≤80.

**Acceptance.** `emotion_syn` 0/0/40 with non-blind negative; OBJ tiles at (0,18)/(32,18) match between canon and rust; trace `emotion_syn_full`: emotion byte + OBJ tile first divergence **none** over the scene's frames; 7-row guard set + cursor identical to step 2; verify_rows PASS is the veto. NEGATIVE naming canon's measured no-face-change behavior (frames + bytes + cite) closes it.

**Measure and report.** rows: emotion_syn + 7-row guard set; frames 40 each (cursor 170). Emotion byte cite + face offset per value, before/after pixel totals, OBJ tile counts at the emotion positions both sides, ROM sha256+size, fitted count, commit; one line of mechanism; one line unverified (the other ~24 emotion states, by value).

**Coordinator:** owns src/emotion.rs + asset layout + the row; runs alone (owns tools/states.py + tools/harness.py). Free tier: verify_rows from a clean checkout on the 8-row set; verifier for step 1's BNEM header + emotion-byte cites. ≤$0.20 expected, ≤$0.40 cap.

**Milestone advanced:** M7 (emotion window 0/25 → 1/25 first port).

---

### T106. M7 charge shot dispatch: port one shot_kind cell of off_80117D4 into a fresh `buster_charge` scenario  *(PARTIAL -- 2026-09-17, LANDED c9c50b7 [branch wt/charge_shot_t106, 8b3b9a4])*

**Result.** LANDED c9c50b7 (branch wt/charge_shot_t106, 8b3b9a4). buster_charge row+state added; row reads isolated FAILED 2498/188/32 (neg 5113, not blind) = 22px/frame dithered sliver on y158 (canon multicolor (12,24,8)/(16,5,29) vs our red-only) + k0 transient; k1-k5 read 0. 8-row guard set byte-identical to baseline (cursor 1/1/170/186279); ROM 0d3ea6d3 584392 = main-identical (charge_shot.rs undeclared by design: declaring a behaviourally-identical call moved cursor 1->10px, so code-addition timing wobble is the blocker for wiring). verify_rows PASS from clean checkout on 9 rows. verifier-hyper: CONFIRMED sub_8011818/sub_80118A4/off_81333B0 are not symbols (0x8011818=cell 0x11, 0x80118A4=cell 0x34 in the 148-cell ChargeShotHandlersByTransformation_80117D4 at asm00_2.s:5809-5957), CONFIRMED AIData loc 0x1b=0x0203409b counted by sub_8012EBC (9085-9155, count-up 9129-9140), CONFIRMED attribute 0x94/shot object 0x23c, REFUTED the Cannon damage formula (canon = 0x1e + 0x14*min(getBusterDamage(),5), not buster+0x14*min(buster,5); getBusterDamage_801265A at asm00_2.s:7933 is NaviIndex+stats[1]+byte_80126A4+tf table with emotion override, NOT Attack+1) and corrected the 'caps at 100' claim (cap is per-(BPwrAtk,tf) from powerAttackChargeTimes_8020404 via off_8012FC4; static read 180 at index 10; 100 is save-specific watched). Worker corrected the file in 8b3b9a4: CANNON arm returns None with // unported: needs getBusterDamage_801265A. Cells 0x06..0x0D named. Models: worker-hyper hyper/glm-5.3-flash 151t $0.455 + correction pass; verifier-hyper hyper/qwen3.8-flash 19t $0.128. Next: port getBusterDamage_801265A (owned by nobody), then the y158 dither, then declare the module behind a T111-style phase pad.
**Why.** SCOPE M7 prose lists "charge shots" with the M7 row at 0/25. T15 PARTIAL (LANDED 152ce3c) finds the charge-shot dispatch table off_80117D4 (asm/asm00_2.s:5789, 8 entries 0x06..0x0D by shot_kind) and the per-shot arm sub_8011818 (asm00_2.s:5801). Charge shots are reproducible from a F5b-pattern scripted input: HOLD A from f0 of the per-attack action state, NO window. The existing buster row uses TAP-A; a fresh `buster_charge` scenario builds on `afterdissolve_0x0c` with HOLD-A scripted. shot_kind=0x06 (Cannon) is the simplest cell — same Cannon attack power, only the held pose and palette differ. Success unblocks the other 7 shot_kinds. **No prior ticket on charge shots** (grep TODO/TODO_ARCHIVE for `charge_shot` returns nothing — T105 prose cites emotion only).

**Files.** `src/charge_shot.rs` (NEW: per-shot_kind dispatch; CANNON case; const table from off_80117D4 with `// provenance: off_80117D4 asm00_2.s:5789`), `src/battle.rs` (wire HOLD-A observation into t1_player_entry so the per-attack state sees the hold timer), `tools/states.py` (ONE scenario `buster_charge` = `afterdissolve_0x0c` + scripted HOLD-A@chip_pick + L@open), `tools/harness.py` (ONE row `buster_charge`: canon=HOLD scripted, negative=TAP-A@chip_pick → matches the existing buster row TAP-A trace), `docs/coverage/forms.md` (NEW), `docs/worklog/T106.md`. **NOT** src/chips.rs, src/objects.rs, src/ai.rs, src/emotion.rs, src/fixture.rs, tools/trace.py, tools/oracle.py, tools/allowlist.py, tools/inventory.py, tools/mgba_capture.c, reference/bn6f.

**Do.**
1. **Recon:** cite every cell of off_80117D4 (asm00_2.s:5789) with its shot_kind; cite the per-shot OBP/palette table (off_81333B0 stride 0x10) with `// unnamed: <hold-pose palette table>` if the symbol is not in bn6f; cite sub_80118A4 (asm00_2.s:5837) palette-swap; cite the hold-timer counter file:line. **measurement.**
2. Baseline, no edit: build ROM, sha256 + size; verify_rows 8-row guard set (opening/mettaur/cannon/buster/chip-use/wave/windowclose/cursor) PASS; capture `buster_charge` TAP-scripted → first 32 frames match the existing buster row pixel-for-pixel (negative confirms scenario = TAP). **measurement.**
3. Add `buster_charge` scenario with HOLD scripted + the `buster_charge` row (canon=HOLD, negative=TAP). **code change + measurement.**
4. Port one charge-shot cell: src/charge_shot.rs `ChargeShot::update(shot_kind=0x06, hold_timer)` arm; src/battle.rs invokes from t1_player_entry when hold_A ≥ 24 frames. Rebuild, sha256+size. **code change + measurement.**
5. Re-run: `buster_charge` 0/0/32 with non-blind negative; OAM byte at the shot position first divergence **none**; 8-row guard set + cursor identical to step 2; verify_rows PASS is the veto. **measurement.**

**Rules.** Art from canon bytes, not redrawn. One const table per shot_kind, cited. Scripted HOLD carries `peeked` provenance. Cursor veto ≤1/1/170/186300. No allowlist, no patch_sterile, canon never changes. ≤6 captures, tool budget ≤80.

**Acceptance.** `buster_charge` 0/0/32 with non-blind negative; OAM byte at shot position first divergence **none**; 8-row guard set + cursor identical to step 2; verify_rows PASS is the veto. NEGATIVE naming canon's measured no-charge behavior (frames + bytes + cite) closes it.

**Measure and report.** rows: buster_charge + 8-row guard set; frames 32 each. Charge-shot cite + OBP/palette per shot_kind, before/after pixel totals, OAM byte trace, ROM sha256+size, fitted count, commit; one line of mechanism; one line unverified (the other 7 shot_kinds).

**Coordinator:** owns src/charge_shot.rs + the row; runs alone (owns tools/states.py + tools/harness.py). Free tier: verify_rows from a clean checkout on the 9-row set; verifier for step 1's off_80117D4 + off_81333B0 cites. ≤$0.20 expected, ≤$0.40 cap.

**Milestone advanced:** M7 (forms charge-shot 0/25 → 1/25 first port).

---

### T108. M7 emotion single-pass port — src/emotion.rs FACE_INDEX using T105's verified poke mechanism  *(NEGATIVE -- 2026-09-17, NOT MERGED [branch wt/t108-emotion, 91ba403+8a4d371, worktree kept for the exporter])*

**Result.** NOT MERGED (branch wt/t108-emotion, 91ba403+8a4d371, worktree kept for the exporter). The ticket's mechanism is refuted by measurement on its own route: --poke-at 60:0x0203528E:0x0100 lands byte 0x0203528F=0x01 and holds to f95+, yet CANON's screen changes 0 px over 120 frames (full-frame and face-box vs calm); poking 0x0500 (byte=5) makes the face vanish (694 px/frame in x0..48/y18..34 from f60). So 0x0203528F is drawEmotionWindow_801CDEC's skip/flash GATE (cmp 5/6 asm00_2.s:27648-27652, flash timer sub_801CC94 :27551/27560/27566), not the face index; the index comes from the live chain sub_801CB38 -> sub_801E6A8 -> possiblyGetBattleEmotion_8015B54 via byte_801E6F4 (asm00_2.s:31045). 'poke -> value-1-face both sides' is therefore unsatisfiable; steps 3-5 were not built on a dead mechanism. Landed on branch: tools/emotion_export.py v2 + assets/emotion.bin full bank dword_872D814..dword_872F114 (0x1900) + 23 per-face palettes (0x2E0) = 7156 B (the ticket's 0x1B30 does not reproduce; its off_801CD08 cite :25567 is stale, real 27580-27602). NEW TRAP for the next pass: v2 asset with the v1 reader const-folds agb's sprite assert (dynamic.rs:264) and LTO deletes Battle::update/draw -> ROM 217 KB smaller that never reaches a battle; asset and reader must land in one commit. Baseline reproduced exactly: ROM 0d3ea6d3 584392; guard set 0/0/N x7 + popup 0/0/80 (1288); cursor 1/1/170/186279; fitted 16. Model worker-hyper hyper/glm-5.3-flash, ~$0.4. Recommendation (from the worker, adopted): re-ticket M7 emotion from T105 passes 4-6 (AIData-poke row shape, wt/t105-p5 has it at 0/0/40) and the T111 cursor seam pad, not from T105 pass-1 recon.
**Why.** T105 PARTIAL on wt/t105-emotion (bb5c01a, worklog-only) discovered the poke mechanism: `--poke 0x0203528E:0x0100` (16-bit half-word) sets byte 0x0203528F to 0x01 cleanly — the 8-bit `--poke` rounds to half-word 0x0203528E so the high byte lands at 0x0203528F and gets masked. T105 also mapped: BNEM header at assets/emotion.bin +0x00..+0x0c, face data at header-named offset; face bank off_801CD08 (reference/bn6f/asm/asm00_2.s:25567, 23 entries, stride 0x180, shared 0x80-byte right half dword_872D914); draw routine drawEmotionWindow_801CDEC (asm00_2.s:27554-27583) skips face when val==5||6; LZ77/BitUnPack of eStruct2035280 is per-init only (BIOS CpuSet at PC 0x00000240, 18 word-aligned writes at frame 0) so the poke persists through 40-frame windows. SCOPE M7 emotion reads 0/25. Multi-pass stays OPEN per T105. **New evidence:** T105 PARTIAL delivered a non-blind baseline (plain ROM sha256 0d3ea6d3, 584392 B; 7-row guard set isolated PASS; cursor 1/1/170/186279 within veto; --watch on 0x0203528F reads 0x00 for 40 frames on canon).

**Files.** `src/emotion.rs` (FACE_INDEX `[u8; 24]` table keyed by emotion value 0..23 with skip-5/6 mapping; draw call emits one of 23 face slots), `assets/emotion.bin` (extend from 1 to 23 face slots, total 0x1B30 bytes), `tools/emotion_export.py` (extend to 23 slots, header 0x00..+0x0c unchanged), `tools/states.py` (ONE scenario `emotion_syn_full` = `battlestart.state` + `--poke 0x0203528E:0x0100` at f60), `tools/harness.py` (ONE row `emotion_syn`: canon=HOLD-poke, negative=no-poke→calm-both-sides), `docs/coverage/emotion.md` (NEW), `docs/worklog/T108.md`. **NOT** src/battle.rs, src/objects.rs, src/ai.rs, src/chips.rs, src/fixture.rs, tools/trace.py, tools/oracle.py, tools/allowlist.py, tools/inventory.py, tools/mgba_capture.c, reference/bn6f.

**Do.**
1. **Recon:** extend tools/emotion_export.py to dump all 23 face slots (assets/emotion.bin to 0x1B30 bytes); cite each face's data start against off_801CD08 offsets; document shared right-half dword_872D914 and drawEmotionWindow_801CDEC's skip-5/6 path. **measurement.**
2. Baseline, no edit: build ROM, sha256+size; verify_rows 8-row guard set + cursor → 0/0/N ×7, cursor 1/1/170/186279; capture `emotion_syn_full` no-poke → both sides render calm face at OBJ (0,18) and (32,18). **measurement.**
3. Add `emotion_syn_full` scenario + `emotion_syn` row (canon=poke-0x0100-at-f60, negative=no-poke→calm-both-sides match step 2). **code change + measurement.**
4. Port src/emotion.rs: read byte 0x0203528F (peeked, `// provenance: T105 worklog`); `const FACE_INDEX: [u8; 24]` table with skip-5/6 mapping from drawEmotionWindow_801CDEC; rebuild, sha256+size. **code change + measurement.**
5. Re-run: `emotion_syn` 0/0/40 with non-blind negative; trace `emotion_syn_full`: emotion byte + OBJ tile at (0,18)/(32,18) first divergence **none** over the row's frames; 8-row guard set + cursor identical to step 2; verify_rows PASS is the veto. **measurement.**

**Rules.** Art from canon bytes, not redrawn (BNEM export is data). FACE_INDEX table cited from off_801CD08 with `// provenance: off_801CD08 asm00_2.s:25567`. State/descriptor poke carries `peeked` provenance. Cursor veto ≤1/1/170/186300. No allowlist, no patch_sterile, canon never changes. ≤6 captures, tool budget ≤80.

**Acceptance.** `emotion_syn` 0/0/40 with non-blind negative (no-poke→calm-both-sides; poke→value-1-face-both-sides); OBJ tiles at (0,18)/(32,18) match between canon and rust; trace `emotion_syn_full`: emotion byte + OBJ tile first divergence **none** over the scene's 40 frames; 8-row guard set + cursor identical to step 2; verify_rows PASS is the veto. NEGATIVE naming canon's measured no-face-change behavior (frames + bytes + cite) closes it.

**Measure and report.** rows: emotion_syn + 8-row guard set + cursor; frames 40 each (cursor 170). Emotion byte cite + face offset per value, before/after pixel totals, OBJ tile counts at the emotion positions both sides, ROM sha256+size, fitted count, commit; one line of mechanism; one line unverified (the other ~22 emotion values, not value 1).

**Coordinator:** owns src/emotion.rs + asset layout + the row; runs alone (owns tools/states.py + tools/harness.py + tools/emotion_export.py). Free tier: verify_rows from a clean checkout on the 9-row set; verifier for step 1's BNEM header + face-bank cites. ≤$0.20 expected, ≤$0.40 cap.

**Milestone advanced:** M7 (emotion window 0/25 → 1/25 first port).

---

### T110. M1 navicust battle-effect handler scenarios — enumerate the 19 M7-row from T15 PARTIAL  *(PARTIAL -- 2026-09-17, LANDED 24cf8f7 [branch wt/t110 5bffe0b, docs/tools only])*

**Result.** LANDED 24cf8f7 (branch wt/t110 5bffe0b, docs/tools only). No M1 row added: every candidate row on the ticket's route is BLIND by construction. Deliverable 1 landed: docs/inventory/navicust_handlers.json = all 47 navicust_jt_NCPs entries (asm37_0.s:2112-2158) with index->handler->body line->effect->NaviStats slot->battle_relevant, generated by new tools/inventory.py parse_navicust_handlers(). Counts (verifier re-derived independently): 1 no-op stub (sub_813C808 at 2162) + 46 handlers; 24 distinct slots written = 13 battle-relevant {0x1 Attack,0x2 Speed,0x3 Charge,0x6 FstBarr,0x7 BLeftAbility,0xa CustomLevel,0xb MegaLevel,0xc GigaLevel,0x1b FloatShoes,0x1c AirShoes,0x1d UnderShirt,0x23 SuperArmor,0x35 SlipRun} + 11 off-denominator {0xd,0x1e,0x1f,0x25,0x26,0x27,0x33,0x36,0x5f,0x60,0x61}; 6 of SCOPE's 19 slots have NO handler (0x4 BButton,0x5 BPwrAtk,0xe Mood,0x19 CustHPBug,0x24 EmotionBug,0x31 ProcessingBug); HPPlus50-500 bypass SetCurPETNaviStatsByte with direct r10 writes (2704/2716/2728/2740/2754/2768). Route refutation (worker 6 captures + verifier re-measured on its own captures): at battlestart.state NaviStatsPtr=toolkit 0x020093b0+0x74 -> record 0x020047cc, dispatch input 0x02004190 (halfword[0]=0 for every record), and --poke 0x020047d2:0x0001 (the FstBarr byte, = what navicust_NCP_FstBarr writes) vs no-poke reads total 0 worst 0 over 40 frames; verifier's stronger control: --watch-write 0x020047cc:0x10 = ZERO write events across the whole 40-frame window, and reloadCurNaviStatBoosts has 28 bl sites, all boot/navicust-exit/cutscene (plus one .word in jt_8043B00 at asm/chatbox.s:8641), none reachable inside the battle window. So the handler chain never runs in battle: an M1 navicust row needs a pre-battle state or the consumer side (0x0203F4AC copies), not a map-record poke. verify_rows 9 rows unchanged (guard 0/0/N, cursor 1/1/170/186279, buster_charge 2498/188/32). Human decisions left open: SCOPE M1's 0/19 denominator is a slot count from inventory.py's u8-only regex (hides u16 ChipRecovery and the named u16 MaxBaseHP/CurHP/HP at 0x3e/0x40/0x42), and the consumer-side row shape needs sign-off. Models: worker-hyper hyper/glm-5.3-flash 94t; verifier-hyper hyper/qwen3.8-flash ~30t.
**Why.** SCOPE M1 navicust reads 0/19: the FOUND table at asm/asm37_0.s:2111 (navicust_jt_NCPs, 47 words stride 4: 45 navicust_NCP_* + navicust_GigFldr1 + a no-op stub) is identified by T15 PARTIAL (LANDED 152ce3c) as the per-program handler dispatch (NOT a program-id enumeration — the index comes from sub_813B9FC(id-1) record halfword >> 2, asm37_0.s:2012). Of the 47 handlers, T15 PARTIAL distinguishes 32x SetCurPETNaviStatsByte + 11x GetCurPETNaviStatsByte + 3 misc (the no-op stub, GigFldr1, and one tracker), of which 19 affect battle (the M7 line). Without per-handler scenarios the M1 row stays 0/19 forever. T15 PARTIAL landed only docs; no scenario file exists. **New evidence:** T15 PARTIAL enumerated the 47 handlers with cites; T15's verifier-hyper re-run cross-checked the dispatch (sub_813B9FC); tools/states.py supports per-state poke + scripted input. The cheapest first scenario is the no-op stub (one capture, no edit to handlers needed; only the row needs adding).

**Files.** `tools/states.py` (NEW scenarios: `navicust_noop_full` = `battlestart.state` + `--poke 0x0203XXXX:0x0001` per handler index; one row per handler, 19 rows total over 2 batches to fit the budget), `tools/harness.py` (NEW 19-row block `navicust_handlers`: canon=HOLD, rust=plain_rom, all 19 reading a single NAVICUST handler byte; negative = same scenario WITHOUT poke → bytes match step 2 baseline), `tools/inventory.py` (extend parse_navicust to enumerate the 19 battle-effect handlers, cite per-handler site in asm37_0.s:2111-2600), `docs/coverage/navicust.md` (NEW), `docs/worklog/T110.md`. **NOT** src/battle.rs, src/objects.rs, src/chips.rs, src/fixture.rs, src/emotion.rs, src/charge_shot.rs, tools/trace.py, tools/oracle.py, tools/allowlist.py, tools/mgba_capture.c, reference/bn6f.

**Do.**
1. **Recon:** list the 19 battle-effect handlers (T15 PARTIAL table — 32 SetCurPETNaviStatsByte + 11 GetCurPETNaviStatsByte → filter by which NAVI stat slots affect battle: HP, Atk, Spd, Charge, etc. via include/rom_structs/NaviStats.inc). Cite per-handler: `// canon: navicust_NCP_<name>` line in asm37_0.s:2111-2600. **measurement.**
2. Baseline, no edit: build ROM, sha256+size; verify_rows 8-row guard set + cursor → 0/0/N ×7, cursor 1/1/170; capture `navicust_noop_full` no-poke → both sides' NAVI stats byte-for-byte equal (control scenario). **measurement.**
3. Add `navicust_noop_full` scenario + 1 row (`navicust_noop`: canon=poke-stub-byte, negative=no-poke→matches step 2 baseline) — first M1 row. **code change + measurement.**
4. Add the remaining 18 scenarios + 18 rows in 2 batches (9 each, ≤6 captures per ticket × 3 ticket cycle); each scenario pokes one handler's NAVI stat byte; each row canon=HOLD, rust=plain_rom, negative=no-poke. **code change + measurement.**
5. Re-run: 19 navicust rows 0/0/N with non-blind negative; SCOPE M1 navicust row 0/19 → 19/19; 8-row guard set + cursor identical to step 2; verify_rows PASS is the veto. **measurement.**

**Rules.** Scenarios are poke-driven, no hand-played input (T20 BLOCKED's hard stop is preserved). Each poke carries `peeked` provenance. NAVI stat slot indexes cited from include/rom_structs/NaviStats.inc. Cursor veto ≤1/1/170/186300. No allowlist, no patch_sterile, canon never changes. ≤6 captures per ticket × 3 ticket cycle, tool budget ≤80 per cycle.

**Acceptance.** 19 navicust rows 0/0/N with non-blind negative; SCOPE M1 navicust row 0/19 → 19/19; tools/inventory.py parse_navicust enumerates the 19 battle-effect handlers with per-handler cites; 8-row guard set + cursor identical to step 2; verify_rows PASS is the veto. NEGATIVE naming canon's measured no-stat-change behavior (frames + bytes + cite) closes it.

**Measure and report.** rows: 19 navicust + 8-row guard set + cursor; frames per row 40 (cursor 170). Per-handler cite + NAVI stat slot, before/after pixel totals, stat-byte trace, ROM sha256+size, fitted count, commit; one line of mechanism; one line unverified (the 28 handlers that DON'T affect battle, listed as out-of-scope).

**Coordinator:** owns tools/states.py + tools/harness.py + tools/inventory.py + the rows; runs alone. Free tier: verify_rows from a clean checkout on the 9-row set per cycle; verifier for step 1's 19-handler cite list. ≤$0.60 expected over 3 cycles, ≤$1.20 cap.

**Milestone advanced:** M1 (navicust battle-effects 0/19 → 19/19 first enumerated).

---

### T111. cursor seam recalibration — one measured, named phase pad at the custom-screen tile drain, restoring the cursor class so the T105 emotion port can land *(OPEN -- 2026-09-17)*

**Result.** T105 pass 6 bisected the cursor regression on the T105 branch (wt/t105-emotion e0c35c9, port verified there: emotion_syn PASS 0/0/40/644, guard set + popup all 0/0/N) to the binary footprint itself: pure main = 1/1/170 (single 1px frame k=97; origin 8, offset 237); main + fixture.rs emotion field alone = 38/19/170; full branch = 29/28/170 (NEW 28px damage at k=37, x49..238/y1..7, main's k=97 tear intact; canon<->rust pairing +-1 frame checked at 4698/2502px); fixture byte-identical to main + battle.rs gate reading enemy_action at enemies==0 (the +63 disambiguation FIXED) = 62/56/170 with the seam moved to NEW frame k=7 (56px). Tools exonerated (S1a==S1; OR-write byte-identity). Mechanism: the cursor window's mid-frame VRAM copy-drain seam frames (k=97 = F3's documented sub-frame seam; k=37 = the 4->3 slot transition; k=7) re-roll pixel phases with ANY binary-footprint change, and the row's 1/1 class is a layout-calibrated coincidence (F26b already saw 2/2<->1/1 across trees). Full step table and per-frame detail: docs/worklog/T105.md pass 6. No fix exists inside T105's file list; this ticket owns the one measured knob.

**Files.** `src/battle.rs` (the custom-screen tile-drain replace/queue path: ONE measured, named phase pad), `src/cust.rs`, `src/main.rs` (only if the drain lives there), `docs/coverage/cursor.md` (NEW: coupling note -- row class vs binary footprint, the k-frame table), `docs/worklog/T111.md`. Branch starts from `wt/t105-emotion` (merge it: it carries the verified T105 port; one landing lands both).
**NOT** tools/harness.py (row semantics frozen: same canon side, same negative, same compare), tools/states.py, tools/oracle.py, tools/allowlist.py, tools/trace.py, reference/bn6f, canon or canon (sterile).

**Do.**
1. **Recon:** locate the tile-drain path (battle.rs replace/queue), cite file:line for where the pad goes; rebuild the merged tree; reproduce branch cursor 29/28/170 (k=37 28px + k=97 1px) and, on pure main in the same tree, 1/1/170 (k=97 1px) -- environment calibration. **measurement.**
2. Add the pad as one named constant (`// unnamed: seam-phase pad, sized by measurement` until its meaning is known; size in cycles or iterations, whichever the drain speaks) and sweep sizes: each size = rebuild + cursor row only; table of size -> cursor total/worst/seam frame; stop at the first size hitting the target shape (k=37: 0 px, k=97: 1 px). ≤8 pad sizes, ≤2 captures each. **code change + measurement.**
3. Full re-run on the padded T105 tree: 7-row guard set + popup + emotion_syn (must hold 0/0/40/644 with its non-blind negative) + cursor ≤1-class; ROM sha256+size. **measurement.**
4. If NO size in the sweep reaches ≤1-class: STOP, report the size table as a measured NEGATIVE with the best shape reached, and name the next knob (do not widen the sweep silently).

**Rules.** The pad is timing-only: no behaviour change (the rows are the proof -- every row stays at its branch value). Canon never changes; the row's canon side, negative and compare stay byte-identical. No allowlist, no patch_sterile. The pad constant carries provenance per AGENTS.md. Cursor target: total ≤1, worst ≤1, frames 170; the tear's frame may move with layout -- reported, not chased. ≤10 captures, tool budget ≤80.

**Acceptance.** cursor ≤1-class on the padded T105 branch with the pad sized and named; emotion_syn 0/0/40/644 and guard set + popup all 0/0/N from a clean checkout; verify_rows PASS is the veto; the coordinator then lands T111+T105 in ONE merge. A NEGATIVE (bounded sweep, size table, best shape, named next knob) closes it BLOCKED.

**Measure and report.** size sweep table (size -> cursor total/worst/seam frame k), final 10-row set, ROM sha256+size, fitted count, commit; one line of mechanism (why the chosen size lands the seams); one line unverified (whether the class holds across future merges -- that is every later landing's check, not this ticket's).

**Coordinator:** owns src/battle.rs (drain path) + the pad; runs alone. Free tier: verify_rows from a clean checkout on the 10-row set; verifier at landing for the pad-is-timing-only claim. ≤$0.25 expected, ≤$0.50 cap.

**Milestone advanced:** unblocks M7 landing (T105 emotion port 0/25 -> 1/25).

---

### T112. M2 end of battle: the rank byte and the zenny reward become computed, not fixture-supplied — trace target `rank` + `zenny`, first divergence none  *(PARTIAL -- 2026-09-17, NOT MERGED [wt/T112 8dbdc72+422d5fa] -- cursor veto not met: the src/battle.rs+trace.py change moves the curso)*

**Result.** NOT MERGED (wt/T112 8dbdc72+422d5fa) -- cursor veto not met: the src/battle.rs+trace.py change moves the cursor isolated row from main's 1/1/170 to 7/6/170 (neg 186276); F12 pure-layout pad ladder re-measured 64->13/12, 96->10/9, 128->7/6, 144->88/56 and no pad size restored <=1/1, so the branch waits on T111's seam recalibration (same root cause: any binary-footprint change re-phases the tile-drain seam). result isolated stayed 0/0/40 (neg 111839) and the other 6 guard rows are byte-identical. WHAT IT FOUND (traced, not pixel-judged): canon's rank byte is eS20364C0+0x0e (0x020364CE), written by sub_802C97E (asm03_0.s:13232-13257, --watch-write frame 13) through the record check sub_802CA1E (13260-13286) against best-time tables unk_20018C0/unk_2000260; the source is the battle-stats record 0x0203F4A4 (+1 level, +4 clear-time word, +8 reward halfword) latched by sub_801FF18 (asm01.s:49-60: time 0xFFFFFFFF->0x6E0=1760 at frame 10, level word->0x01010200 frame 11), copied to results slot 0x02035260 by sub_800B444 (asm00_1.s:17986-17991, frame 12), then into the window struct by showResultWindow_802C34E (asm03_0.s:12441-12455). Watched per frame: rank 0, level 2, reward 0xFFFF->0x4064 (=0x4000|100), time 1760. Ported fn battle_rank + fn battle_zenny with the missing inputs NAMED (no ai_index/enemy_idx on our Actor, best-time tables unported -> canon's own 0xFF branch gives rank 0; the zenny drop-roll sub_802C8FA->sub_80AA8E0/sub_80AAC8C unported, RESULTMATCH_ZENNY fallback). TRACE: result 40 frames rank match 40/40, zenny match 40/40, FIRST DIVERGENCE none; second scenario battle_full (540 frames) rank 540/540, zenny diverges first k=406 canon=100 rust=0 (113/540) and the report attributes it to window-up export-counter stall (F33d), both sides' stored value 100 once the window is up. ROM sha256 8aa6d9722faf3b1b, fitted 16 unchanged, derived 435 (+2), 6/6 captures. Model worker-hyper hyper/glm-5.3-flash 110t. NEXT: rebase on T111's pad, then re-run step 5; reward ITEMS (chips/PAs) still out of scope; exported busting level reads 8 vs canon 2 on battle_full (INFO, unjudged).
**Why.** SCOPE M2 lists "end of battle with rank and rewards" and no part of it is computed in our build: `src/battle.rs:2452` calls `self.results.show(kind, time, level, 0, zenny)` with a literal `0` for rank, and the money comes from the descriptor (`src/fixture.rs:243-244` `result_zenny` at +44, consumed at `src/battle.rs:3067` through `f.result_zenny`). The display is real and cited (`src/results.rs:104-105` `RANK_MAX: u8 = 2`, `:527` `TIME_BANK + rank.min(RANK_MAX)` recolors the time digits, `:191` "level 0xb is the S rank", reward chain `sub_802C34E->sub_802BE36->sub_802C044` 42 tiles, cooldown `sub_802C0A4`, driver `sub_802BD60`, `asm03_0.s:11959/:12558/:13017-13029`) — but the number that selects it has never been ported, so every results variant we can reach is pinned to one rank and one payout. Canon stores its own rank/zenny words in RAM, which makes this a trace question with a zero.

**Files.** `src/battle.rs` (the two calcs + the call site at :2452/:3067; the oracle/trace export of the two values), `src/results.rs` (signature only if rank stops being a parameter literal), `tools/trace.py` (two new canon watches + the pair), `docs/coverage/end-of-battle.md` (NEW), `docs/worklog/T112.md`. **NOT** tools/harness.py (row semantics frozen), tools/states.py, tools/oracle.py, tools/allowlist.py, assets/, reference/bn6f (read-only), canon.

**Do.**
1. Find canon's storage: walk the results setup ahead of `sub_802BD60` in `asm03_0.s` and name the addresses holding the rank byte, the zenny halfword and the level byte; confirm with one canon-side capture on the `result` route (`--watch` at those addresses, 40 frames) and report the values per frame. **measurement.**
2. Baseline ours: print our current rank (literal 0) and zenny (descriptor +44) against canon's watched values from step 1 — the divergence stated as field, value, frames. **measurement.**
3. Port the calcs: locate the routine that writes those words (the battle-stats reader), port it cited into `src/battle.rs` (`fn battle_rank`, `fn battle_zenny`, each `// provenance:` tagged per site), feed them at :2452/:3067 only when the descriptor carries `FIXTURE_UNSET` (`src/battle.rs:1611`) so every existing row keeps its fixture path. **code change + measurement.**
4. Add the two pairs to `tools/trace.py` and re-run: `rank` and `zenny` over the `result` scenario's 40 frames, first divergent frame **none**; then on a second ending scenario you can reach (report which) and state its first divergence. **measurement.**
5. Re-run the 8-row guard set + `result` + `cursor`; if the cursor class moves with the binary, the sanctioned absorber is the F12 pure-layout pad (`src/battle.rs:1819-1831`) — restore ≤1/1/170 by pad size and report the tear's frame, do not chase it. **measurement.**

**Rules.** No fitted rank/zenny values: every term of both calcs carries a disassembly cite or stays unported and is named. Fixture-supplied values remain legal only where a row already compares against them. No allowlist, no patch_sterile, canon never changes. ≤6 captures, tool budget ≤80.

**Acceptance.** Trace target: `rank` byte and `zenny` halfword, 40 frames of the `result` scenario, first divergence **none**, with both values produced by ported cited routines (not the descriptor); byte-equality with canon's stored words on at least one further ending scenario, or that scenario's first divergent frame and field named. `result` isolated 0/0/40 unchanged, 8-row guard set + cursor identical to step 2, verify_rows PASS from a clean checkout as the veto. NEGATIVE naming canon's stored addresses and the missing input stat closes it.

**Measure and report.** rows: result + 8-row guard set; frames 40 (cursor 170). Canon's rank/zenny/level addresses with cites, the watched values, our before/after values, the two calcs' cite lists, trace first-divergence before/after, pixel totals unchanged, ROM sha256+size, fitted count, commit; one line of mechanism; one line unverified (the reward *items* — chips/PAs granted — are not in this ticket's two words).

**Coordinator:** owns src/ + trace.py; runs alone (pairs with nothing that touches src/battle.rs). Free tier: verify_rows on the 9-row set; verifier for step 1's addresses and step 3's cites. ≤$0.30 expected, ≤$0.60 cap. **Advances M2.**

---

### T113. M5: the AIIndex-4 family onto the scoreboard — the virus T87 already fields, its think entry ported through the ROM's own AI table, one row plus its trace *(OPEN -- 2026-09-18)*

**Why.** SCOPE M5 is one virus deep (Mettaur) of 187 (ai_index, version) pairs, and T58's census (PARTIAL, 0302084) says why the next one is nearly free: ai 1-31 carry exactly 6 ranks each, the identity rows come from `byte_80182C4` via `GetVerActorTyAndAIIdx_80182B4` (`asm/asm00_2.s:19965-19974`) and the behaviour from `AIThinkTables_8109050[ai_index]` (T76's chain), so a family needs a port once per ai_index, not per rank. T87 (LANDED 6e493bc) already put a non-Mettaur virus on screen and proved it: the EVENT_681 flag poke `60:0x02001d58:0x0240` swaps the encounter root to `0x080b50b0` (12 ungated records), lever `60:0x0200a210:0x37a` → 891 mod 12 = 3 → rec3 `0x080b50e0`, fields **ai_index-4 rank v0, NameID 0x0013 at frame 69, slot1 HP 0x5a byte-matching `off_8109150[4]` elem_hp** (`0x0810ae4c`, stride 6), 40-frame determinism 0 px on two builds, guard 7 rows identical. `docs/inventory/enemies.md:196-207` shows that ai 0x04 covers `0x13..0x18` (virus) **and `0x113..0x118` (the same AI as a Navi)**, act `nullsub_13`, think table `off_810B2D0` (`asm/asm31.s:173608`) — one port, and M6's first Navi rides it.

**New evidence.** T87's landed state is the measurement this ticket needs and it postdates every earlier attempt: no `src/` change and no harness row has been made for ai 0x04 since, and the two stamps that closed the ai-4 recording line carry no worklog at all (`docs/worklog/` holds T90, T91, T95 — not T92, not T93), i.e. they are error records, not measurements.

**Files.** `src/ai.rs` (the ai_index-4 think arm, cited to `off_810B2D0`/`AIThinkTables_8109050`, no hand-written behaviour), `src/actor.rs` (the enemy's art entry if the sprite category is missing), `tools/harness.py` (ONE new row `ai4`: canon = T87's `battlestart_ai4_rank0` route, rust = plain_rom, negative = the same route WITHOUT the `0x02001d58` poke so a different formation is fielded), `tools/inventory.py` (recognise the ai-4 rank row by its identity-row bytes, not by an id list), `docs/coverage/ai4.md` (NEW), `docs/worklog/T113.md`. **NOT** `src/battle.rs` (if the spawn needs a new entry kind, stop and name it as the follow-up), tools/states.py (T87's state is the fixture), tools/trace.py, tools/oracle.py, tools/allowlist.py, reference/bn6f, canon.

**Do.**
1. Report what our build already does for ai 0x04: the arm table in `src/ai.rs` keyed by `AIThinkTables_8109050[ai_index]`, and whether index 4 is ported, absent or silently shared with Mettaur (ai 1). **measurement.**
2. Add the `ai4` row and run it unmodified by src: total, worst, frames, region — the divergence this ticket exists to remove — plus the negative's total (must be non-zero) and the row's determinism. **code change + measurement.**
3. Port the think arm cited from `off_810B2D0` (`asm/asm31.s:173608`) and the identity/Struct2 bytes (`00 00 04` at `byte_80182C4+3*0x13`, elem_hp 0x005a); rebuild, ROM sha256+size. **code change + measurement.**
4. Re-run the row: report the residue per frame and per region before/after, and the trace fields that own what is left (`enemy_state_action`, `enemy_anim`, `enemy_hp`: first divergent frame each). **measurement.**
5. Guard set + `cursor` against step 2's baseline; if the cursor class moved with the binary, the F12 pure-layout pad (`src/battle.rs:1819`) is the sanctioned absorber and is *reported*, not chased. **measurement.**

**Rules.** A virus is a port under the interpreters, never a re-creation: each arm cites a ROM address or stays unported and is named. Poke provenance `peeked`. No allowlist, no patch_sterile, canon never changes. ≤6 captures, tool budget ≤80.

**Acceptance.** `ai4` 0/0/40 with a non-blind negative, `enemy_state_action`/`enemy_anim` first divergence **none** over the row's frames, 8-row guard set + cursor unchanged, verify_rows PASS from a clean checkout as the veto — then M1 viruses 1/187 → 2/187 with the new row keyed on the identity-row bytes. If the residue is not 0, the ticket closes only with the residue attributed frame-by-frame and region-by-region and the first divergent trace field named; the count does not move.

**Measure and report.** rows: ai4 + 8-row guard set; frames 40. Before/after totals, worst, region, the negative's total, the ai-4 arm's cites, the identity/Struct2 bytes checked, first divergent frame per field, ROM sha256+size, fitted count, commit; one line of mechanism; one line unverified (the other five ai-4 ranks and the `0x113..0x118` Navi rows that share the think table).

**Coordinator:** owns harness.py + inventory.py + ai.rs; runs alone (no pair while T112 holds src/battle.rs). Free tier: verify_rows on the 9-row set; verifier for step 1's arm audit and step 3's cites. ≤$0.35 expected, ≤$0.70 cap. **Advances M5 (M1 viruses line).**

---

### T114. M7: bring the landed `buster_charge` row from 2498/188/32 to 0 — attribute the y158 sliver and fix it with exported data, not a fitted colour *(OPEN -- 2026-09-18)*

**Why.** T106 (PARTIAL, LANDED c9c50b7) put the charge-shot dispatch on the board with its cells named (`ChargeShotHandlersByTransformation_80117D4`, `asm00_2.s:5809-5957`; verifier-corrected: `0x8011818` is cell 0x11, `0x80118A4` cell 0x34, damage `0x1e + 0x14*min(getBusterDamage(),5)` with `getBusterDamage_801265A` still unported) and its row `buster_charge` (`tools/harness.py:2377`) reads **isolated FAILED 2498/188/32, negative 5113, not blind**. The shape is already narrowed by that pass: a ~22 px/frame dithered sliver on y158 — canon multicolour (12,24,8)/(16,5,29) against our red-only — plus a k=0 transient, with k1..k5 at 0. y158 is the CUSTOM gauge strip (`src/hudtiles.rs`: `GAUGE_BANK` :144, `BAR` :135 still tagged `fitted -- NOT VERIFIED`, `INTERIOR` :161 `peeked`, `BAR_CYCLE`/`gauge_palette` :231-245, `set_gauge` :301), whose canon flow routine `sub_801C4E4` (`asm00_2.s:26351-26423`) reads the gauge word `eStruct2035280+0x20` (`word_20352A0`) against its 0x4000 cap. The fixture already carries two named knobs for that strip's phase — `gauge` (descriptor +32) and `gauge_tick` (+28, `src/fixture.rs:203-218`) — so the first question is phase or mechanism, and it is answerable without touching src.

**Files.** `src/hudtiles.rs` (the gauge's not-full/dither arm and its palette, each cited), `tools/hud_tiles_export.py` (carry the measured palette entries/tiles from canon's bytes), `assets/` (the regenerated hud-tile blob only), `tools/states.py` (the scenario's descriptor seeds if step 2 names one), `docs/coverage/charge-gauge.md` (NEW), `docs/worklog/T114.md`. **NOT** `src/battle.rs`, `src/charge_shot.rs` (stays undeclared until T111's pad exists), `tools/harness.py` (row, canon side and negative frozen), tools/trace.py, tools/oracle.py, tools/allowlist.py, reference/bn6f, canon.

**Do.**
1. At the diverging frames, dump both sides' y158 BG map cell, tile index and palette index, name which gauge element owns those 22 px (bar body / end caps / CUSTOM label / marker text) and which 16-colour slots canon writes — cite the ROM bytes and the writing arm of `sub_801C4E4`. **measurement.**
2. Test phase without mechanism: sweep the scenario's `gauge_tick` and `gauge` seeds (the two descriptor knobs), table of seed → row total/worst. If a seed reaches 0 the residue is fixture phase and gets a provenance comment; if none does, it is a mechanism. ≤2 captures. **measurement.**
3. Fix by data or by the cited arm: extend the exporter with the measured palette/tile bytes (never a redrawn colour, never a fitted triple), and port the named `sub_801C4E4` branch for the case step 1 found; retire `BAR`'s `fitted -- NOT VERIFIED` tag with a cite or leave the tag and say so. Rebuild, ROM sha256+size. **code change + measurement.**
4. Re-run: `buster_charge` 0/0/32 with its negative still non-zero, and `buster` (the TAP row) identical to baseline. **measurement.**
5. 8-row guard set + `cursor`; any cursor class move from the footprint change is absorbed with the F12 pure-layout pad (`src/battle.rs:1819`) and reported, not chased. **measurement.**

**Rules.** Art and palette from canon bytes only. No fitted colour and no new fitted const: the hygiene count must not rise. Row semantics, canon side and negative byte-identical. No allowlist, no patch_sterile, canon never changes. ≤6 captures, tool budget ≤80.

**Acceptance.** `buster_charge` isolated 0/0/32 with non-blind negative (baseline 5113), `buster` 0/0/28 unchanged, 8-row guard set + cursor identical to step 2's baseline, verify_rows PASS from a clean checkout as the veto. A bounded NEGATIVE closes it too: the seed→residue table of step 2 plus the per-frame/per-region attribution of the surviving residue and the cite of the mechanism still unported.

**Measure and report.** rows: buster_charge, buster + 8-row guard set; frames 32/28/40 (cursor 170). Before/after totals and worst, the y158 cell/tile/palette table both sides, the seed sweep, palette slot cites, ROM sha256+size, fitted count before/after, commit; one line of mechanism; one line unverified (the other seven shot_kinds and the module's declaration, which waits on T111).

**Coordinator:** owns hudtiles + the exporter + the scenario seed; pairable with T112 or T113 (disjoint files). Free tier: verify_rows on the 9-row set; verifier for step 1's palette/element identification. ≤$0.25 expected, ≤$0.50 cap. **Advances M7.**

---

### T115. M1/M3: the five panel types still marked GAP get their writers out of a direct-store and data-stream walk — the method T33's call-site sweep could not see *(OPEN -- 2026-09-18)*

**Why.** M3's foundation is 13 panel types, and M1 reads 8/13. The table is found and cited: `word_3007924` (IWRAM copy of `0x081D7E24`, `bn6f.map:34342`, copied by `start.s:57-63`), 13 words stride 4, one per type 0x0..0xC, OR-ed into `oPanelData_Flags` by `_object_updatePanelParameters` (`asm/asm38.s:4213-4219`), setter `_object_setPanelType` (`asm/asm38.s:4315-4326`). What is missing is the *writer* for five of them — 0x0 hole, 0x5 holy, 0x8, 0x9, 0xA — so their rows print `bounded-GAP` and count zero (`tools/inventory.py:646-651` gives a row `verified` the moment its writer cite is a site, not a GAP), and no status/panel behaviour can be traced until the type is known to be reachable at all.

**New evidence.** Two landed things postdate the earlier call-site sweep. (1) The method precedent: T18 (DONE, 3f09aa7) found the status bits only because it walked **inline field stores** — "every object_setFlag/clearFlag/getFlag call **and inline flags-field orr/str/tst**" — a class a call-site sweep structurally misses; the same routine that writes 0xB/0xC from an object's CurState (`t3_0x0_80C4E58`, `asm/asm31.s:27855-27872`) and the stage writer `sub_80BAE16` (`asm/asm31.s:6104-6170`, types 4/6/7) both have un-walked arms. (2) T65 (DONE, PASS 3 landed 79da4ed) delivered the record stream nobody had: **1240 records over 84 lists / 1076 0xF0-terminated formation arrays**, referrer-checked with 0 mismatches, plus T70's stage-pair table `byte_203CA50` (`asm/asm21.s:548-564`) — the data side where a stage or encounter would seed panels, which no writer sweep examined.

**Files.** `tools/inventory.py` (`PANEL_TYPE_ROWS` writer cites + `SECTION_NOTES` line for panels), `docs/coverage/panels.md` (NEW: per type, the sites walked and the ruled-out addresses), `docs/inventory/panels.md` if the generator wants it, `docs/worklog/T115.md`. **NOT** any `src/` file (the ROM hash must not move), tools/harness.py, tools/states.py, tools/trace.py, tools/oracle.py, tools/allowlist.py, reference/bn6f (read-only), canon.

**Do.**
1. Walk the *field*, not the helper: every store to the panel type byte/word (direct `strb`/`str` and the inline orr/bic forms, T18's method) plus every constant argument at `_object_setPanelType` sites, and every arm of `sub_80BAE16` and `t3_0x0_80C4E58`; report a per-type table 0x0/0x5/0x8/0x9/0xA → sites (file:line), dispatch condition, and the count of sites examined. **measurement.**
2. Walk the data: T65's 1076 arrays/1240 records and T70's stage pairs — do any bytes seed panel types? Report the table with its stride and the known-answer check (the 8 verified types must be predicted where they already appear), or the rule-out with the bytes examined. **measurement.**
3. For each writer found, prove it live on canon only: one `--watch` capture per type, max 2, on the scenario where it should fire, reporting the flip frame and value. **measurement.**
4. Re-cite `tools/inventory.py` and re-run `python3 tools/inventory.py`: M1 panels 8/13 → N/13; every surviving GAP row states its site count and the addresses ruled out. Confirm the ROM sha256 is unchanged (zero src). **measurement.**

**Rules.** Zero `src/` edits and zero rebuild; the product is cites and the regenerated table. No capture of ours is compared — this is canon-side observation, so no row semantics change. Every emitted cite carries file:line or the row stays bounded-GAP. No allowlist, no patch_sterile, canon never changes. ≤3 captures, tool budget ≤70.

**Acceptance.** `python3 tools/inventory.py` prints M1 panels at N/13 with N>8, each converted row carrying a writer cite **and** (where step 3 could observe it) the flip frame and value; and the ROM sha256 before = after (no rebuild). A NEGATIVE closes it if all five stay GAPs, with the per-type table of every site and data byte examined.

**Measure and report.** rows: none (no harness change); frames: the watch captures only. Panels 8/13 → N/13, the per-type site table, the data-stream verdict, the ROM sha256 before/after identical, capture count, fitted count unchanged, commit; one line of mechanism (which routine sets which type); one line unverified (the panel *effects* — those need scenarios and src, and are the next ticket).

**Coordinator:** docs/tools-only, so it pairs with T112 or T114; runs next to anything. Free tier: nothing to reproduce (no row moves); verifier for step 1's cites and step 3's watches. ≤$0.15 expected, ≤$0.35 cap. **Advances M1 and M3.**

---

### T116. M4/M1: name the chip set a battle can actually reach, measured from the ROM, and put our 48-record asset against it *(OPEN -- 2026-09-18)*

**Why.** M4 reads "every standard chip, mega, giga, secret; Program Advances" and M1's chips line is 43/411 — a denominator nobody can plan against, because our build's chips come from a hand-sized asset: `assets/chips.bin`, a BNCH v2 blob of **48 records** exported by `tools/chip_export.py` from `data/ChipDataArr.s` (`ChipDataArr_8021DA8`, 411 records, stride 0x2c, `include/rom_structs/ChipData.inc`), with `src/chips.rs:66-70` asserting the version before locating the tail. So "368 chips to go" may be 5, or 368, and the queue order is currently a guess. The pieces to settle it are landed and cheap to combine: T57 (DONE, 954ed81) audited all 43 pixel-verified ids against the record, `AS_DATA_FAMILIES = {0x13, 0x15, 0x21}` (`tools/inventory.py:237`); T61 (PARTIAL) verified the asset's 0x15 records are exactly {163(0x00),177(0x01),178/179/180(0x04)} while the table holds 84; T76 (DONE) walks the identity→AI chain for enemies and shows the same enumeration pattern works in `tools/inventory.py`.

**New evidence.** The reachability census is now on disk as a measurement, not a guess: T75's landing report (`REPORT_T75.md`) tabulated table-vs-asset-vs-name per family — 0x13: 17 ids in table / 11 in asset / 11 named; 0x15: 84 / 5 / 38 named; 0x21: 1 / 1 / 1 — and recorded that `TextScriptChipNames0.s` carries only 238 names (ids 0..237) while six 0x13 ids (286/339/370/374/376/410) have neither a name nor an asset record. That is the shape of the answer; it has never been produced for all 411 ids, and no ticket has ever asked what the game can reach.

**Files.** `tools/chip_export.py` (the record set it exports, plus a printed per-id cite), `tools/inventory.py` (a second chips count on the reachable set, keeping the 411 line), `src/chips.rs` (bounds/version/assertion only if the asset grows), `docs/coverage/chips.md` (NEW: the reachable set and how it was derived), `docs/worklog/T116.md`. **NOT** `src/battle.rs` (no dispatch changes here), tools/harness.py, tools/states.py, tools/trace.py, tools/oracle.py, tools/allowlist.py, reference/bn6f (read-only), canon.

**Do.**
1. Cite canon's own reader of `ChipDataArr_8021DA8`: the routine(s) that index it by chip id at chip use and at the custom-screen draw, the index math and the stride; verify two ids live on canon by `--dump` of the record at the computed address. **measurement.**
2. Derive the reachable id set from the ROM and the battery save (never tracked, read only): the ids the game can put in a folder and use in battle, with each id's name from `TextScriptChipNames0.s`; report the count and the list. **measurement.**
3. Produce the three-way table over all 411 rows: in-asset / reachable / verified-on-the-scoreboard, and the gap list (reachable but not in the asset; in the asset but unverified; in neither). Report the counts that M4's queue should be. **measurement.**
4. If the gap list is bounded: extend `tools/chip_export.py` to export the reachable set, rebuild, and run the full chip class of rows plus the 8-row guard set — every row must read exactly its baseline value with the bigger asset. Report the ROM sha256+size before/after. **code change + measurement.**
5. If the asset grows and the cursor class moves: report it as the footprint coupling it is (T111's knob), do not chase the tear, and leave the asset change unmerged. **measurement.**

**Rules.** `src/battle.rs` untouched so no dispatch changes ride along. No allowlist, no patch_sterile, canon never changes, names/descriptions come from the ROM's own strings, and every generated row carries file:line. ≤6 captures, tool budget ≤70.

**Acceptance.** `tools/inventory.py` prints the chips line as `verified / 411` **and** `verified / R` with R the measured reachable count, each reachable id carrying its cite (ChipDataArr line + asset index + name string line); the gap list produced; and either the asset extended to the reachable set with all 43 chip rows and the 8-row guard set byte-identical to baseline (verify_rows PASS as the veto), or a NEGATIVE naming why the extension is unsafe, id by id.

**Measure and report.** rows: the 43 chip rows + 8-row guard set, frames as today per row (cursor 170). Reachable count R, the three-way table, the gap lists, asset record count 48 → M, row totals unchanged before/after, ROM sha256+size, fitted count, commit; one line of mechanism (which table the game indexes to build the chip list); one line unverified (the behaviour of each newly-exported chip — export is not parity).

**Coordinator:** docs/tools + chips.rs only, pairable with T113; runs alone if step 4 grows the asset. Free tier: verify_rows on the 9-row set; verifier for steps 1-2's cites and the reachable-set derivation. ≤$0.20 expected, ≤$0.45 cap. **Advances M4 and M1.**

