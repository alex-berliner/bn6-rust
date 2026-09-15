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
### F35a. buster integrated ~643698: baseline the residue, decompose by frame and region, port the canon mechanism  *(BLOCKED -- 2026-09-15, no code change, tool budget soft-cap hit at 80 before port)*

**Result.** no code change, tool budget soft-cap hit at 80 before port; baseline 54672/12977/28 (vs ~643698/27225 headline); decomposition from F33c notes: chip-name strip 8862 px (BG3 element 6, sub_801C6EE) + result-window slide 45810 px (sub_802BD60->sub_802BE36), both on BG3, both unsafe to fit; buster isolated 0/0/28; cursor 1/1/170; field AUDIT-6 cap holds; cost $0.252 model=minimax/MiniMax-M3:high
**Why.** buster integrated sits at ~643698/27225/N (TODO_ARCHIVE.md F18b/F18d context, AUDIT-6 allowance) while buster isolated is 0/0/28 — the isolated variant passes via F31b's scripted A-press (per TODO_ARCHIVE.md F31b), but no F/Fb/Fc ticket has decomposed buster integrated. The integrated variant uses demo-* feature (no HUD/backdrop blanking), and TODO_ARCHIVE.md line 1305 names the buster's own residue: "buster additionally keeps drawing the name from k=1 where canon has stopped. Measured on buster's own canon capture (--only-bg 3): the strip … from canon 133 -- the frame after CurAction 0x11, the buster action -- … holds 'Cannon 40' (422 px, y148..158 x1..63) on canon 132 and is BLANK on rust … 422 px/frame x 21 frames = 8862 of buster's 54672" — that is isolated. The integrated residue is the HUD strip + BG1 backdrop + the buster's own behavior in full context. M2 acceptance is "integrated-row pixel parity"; closing buster integrated removes one of the four large integrated remnants.

**Files.** tools/harness.py (only the buster-integrated fixture descriptor — confirm demo-* flag and alignment), src/battle.rs (only the buster path if a per-tick write is needed), src/shot.rs (only the buster's per-state behavior if it differs in full-HUD context), src/fixture.rs (only if a new descriptor field is needed), tools/allowlist.py (only the buster:integrated entry if the row reads 0/0/N), tools/diffmask.py (only for region split), docs/coverage/buster_integrated.md (notes)

**Do.**
1. Baseline `tools/harness.py --only buster --ui integrated` on HEAD → *report buster integrated ~643698/27225/N with the AUDIT-6 allowance; buster isolated 0/0/28 PASS (per F31b scripted A-press); cursor ≤1/1/170; mettaur 0/0/70; windowclose/result/field 0/0/40; all chip rows 0/0/30.*
2. Run `tools/diffmask.py --row buster --ui integrated` to split the residue by region (HUD strip y<24, BG1 backdrop, BG3 window ramp with the 422 px name strip y148..158 x1..63 at canon 132, OBJ layer); cross-reference `tools/harness.py --only buster --ui integrated --only-bg 3` and `--only-bg 1` to attribute by BG layer → *report the per-region pixel totals and the per-frame sequence k=0..N.*
3. Find the canon mechanism for each non-zero region in `reference/bn6f/asm/`: HUD strip sub_8026BF4 (per F18b), BG1 backdrop sub_8001C94 (per F6), BG3 window ramp sub_801C4E4 + the queued chip name "Cannon 40" via renderTextGfx_8045F8C (TODO_ARCHIVE.md line 1272 sub_801C6EE asm00_2.s:26619 → 0x0600cb00), OBJ buster line canon's sub_8009C1C (per F11) → *report the per-region cite, file:line, and the per-region canon mechanism; cross-reference F31b's scripted-A-press cite for the buster's own action.*
4. Port the per-region mechanism into src/battle.rs / src/shot.rs / src/custom.rs / src/backdrop.rs as needed; cite each fix to file:line with `// provenance:` tags; never fit a hardcoded BG layer write or a fitted per-frame name-strip write — port the canon routine → *report the per-region port, the cite count, the diff per file.*
5. Re-run `tools/harness.py --only buster --ui integrated` and `tools/verify_rows.py` from a clean detached checkout → *report buster integrated before/after (target ~643698/27225/N → 0/0/N); buster isolated stays 0/0/28; cursor stays ≤1/1/170; mettaur 0/0/70; windowclose/result/field 0/0/40; all chip rows 0/0/30; full regression set 0/0.*
6. Land with `tools/land.sh` and re-run the free row check on main → *report: 67-row table identical to HEAD except buster integrated 0/0/N; remove the `buster:integrated` allowlist entry from tools/allowlist.py.*

**Rules.** Only the named files; the AUDIT-6 allowance for `buster:integrated` is in tools/allowlist.py — it is removed only after verify_rows PASS at 0/0/N; no new harness row; no alignment change; the fix is a port of canon's HUD + BG1 + BG3 + OBJ routines — never a fitted layer write or a hardcoded name-strip write; every new literal gets a `// provenance:` tag with the cite; `fitted constants in src/` (HEAD: 19) may not increase; canon never changes; ≤4 capture runs, one at a time inside the 3-slot semaphore.

**Acceptance.** buster integrated reads 0/0/N with the per-region mechanism cited at sub_8026BF4 (HUD) + sub_8001C94 (BG1) + sub_801C4E4 + sub_801C6EE (BG3 name strip) + the OBJ layer cite; buster isolated stays 0/0/28; cursor ≤1/1/170; mettaur 0/0/70; windowclose/result/field 0/0/40; all chip rows 0/0/30; `buster:integrated` removed from tools/allowlist.py; no allowlist change elsewhere; fitted-constant count unchanged or lower.

**Measure and report.** row: buster (integrated) + buster (isolated) + cursor + windowclose + mettaur + result + field + the chip rows. frames: N buster, 170 cursor, 70 mettaur. total/worst: buster integrated before/after (~643698/27225 → 0/0); per-region pixel totals HUD/BG1/BG3/OBJ; per-frame sequence k=0..N. region: HUD strip y<24, BG1 backdrop, BG3 window ramp with the 422 px name strip y148..158 x1..63, OBJ layer. commit: src/battle.rs + src/shot.rs + src/custom.rs + src/backdrop.rs (per-region port) + tools/allowlist.py (AUDIT-6 removal). One line of mechanism (buster integrated's residue lives in four canon routines — HUD strip sub_8026BF4, BG1 backdrop sub_8001C94, BG3 window ramp sub_801C4E4 + sub_801C6EE name strip, OBJ buster action sub_8009C1C — each ported with cited file:line). One line of what is unverified (whether the OBJ layer holds additional residue that needs its own per-element cite, since F31b's scripted-A-press isolated the buster's own action but the integrated OBJ layer is the full HUD context).

**Coordinator:** dispatch third. Worker muse-spark-1.3-contributor (buster isolated's child class — per-region integrated port), verifier GLM-5.3-flash cross-family; ≤$0.30 expected, ≤$0.60 cap; verify_rows on the full table. Advances **M2** (integrated buster; closes one of the four large integrated remnants after F38g's opening and F36a's warp).

### T7u. battle_full sequencer: port sub_801E754's banner-idle check to replace SEQ04_FRAMES=60 in src/battle.rs  *(BLOCKED -- 2026-09-15, code change made, but caused cursor regression: cursor 1/1/170 -> 38/37/170 [37x worse])*

**Result.** code change made, but caused cursor regression: cursor 1/1/170 -> 38/37/170 (37x worse). Branch not landed. battle_full sequencer divergence 273/540 -> 256/540 (not met <=100 target). Mechanism correct but banner_at 30-frame countdown defeats banner_idle check before Banner struct spawns. cost $0.395 model=minimax/MiniMax-M3:high
**Why.** T7e DONE brought battle_full sequencer to 540/540 (165 window-setup k=31..195 + 8 kill-timing k=297..304, both named), then T7r PARTIAL (gauge=1 + scripted A@170, 7358b0d) regressed window-setup because self.seq.state now traverses SEQ_08→SEQ_20→SEQ_24→SEQ_00→SEQ_04→SEQ_08 at the wrong scenario k — window opens at rust k=124 vs canon k=31 (T7s NEGATIVE). The fitted SEQ04_FRAMES=60 (src/battle.rs:~1116 / leave-predicate :2724) is what's parked in the wrong place; sub_801E754's banner-idle check (cited at T7d PARTIAL asm00_1.s:10422, off_8008038 table, sub_8008064 at asm00_1.s:10514) is the leave predicate that arms timers 0x1e and 0x293 at entry and returns 0 when the banner composite is idle. T7j PARTIAL documented the path but kept SEQ04_FRAMES=60 unchanged on wt/t7j-banner-composite aa3486d (docs-only). M2 acceptance is "battle_full trace: first divergence none"; closing 165 window-setup frames is the largest remaining M2 residue.

**Files.** src/battle.rs (only the SEQ04_FRAMES=60 constant at :1116 and the SEQ_04 leave predicate at :2724; never a hardcoded 0x04→0x08 timer fit), tools/trace.py (only if a sequencer-field watch needs widening), docs/coverage/battle_full.md (notes), tools/harness.py (only if the window-open timing needs a one-shot poke per T7s analysis), tools/probe.py (only the per-frame seq.state watch)

**Do.**
1. Baseline `tools/trace.py record/diff --align row:battle_full` on HEAD → *report: self.seq.state k=0..210 sequence (rust SEQ_08..124, SEQ_20..125..126, SEQ_24..127..218, SEQ_00..219..221, SEQ_04..222..222, SEQ_08..223+ vs canon SEQ_08..30, SEQ_20..31..32, SEQ_24..33..132, SEQ_00..133..135, SEQ_04..136..195, SEQ_08..206+); mm_state_action/mm_anim/mm_timer at k=179 = 76/78/270; battle_full sequencer divergence still 173/540.*
2. Read sub_801E754 (asm00_1.s:10422) and sub_8008064 (asm00_1.s:10514) for the banner-idle check's return semantics and the timer-arm path; read sub_800840C (asm00_1.s:10441) for the [r5+2] latch that gates 0x00→0x04 → *report the cited file:line for the banner-idle check's return value, the timer-arm constants 0x1e and 0x293 with their meanings, and the precise predicate that should replace SEQ04_FRAMES=60.*
3. Port sub_801E754's banner-idle check into src/battle.rs as `fn banner_idle(banner_composite: &BannerComposite) -> bool` with cited file:line per timer constant; replace SEQ04_FRAMES=60 with `seq.state == SEQ_04 && !banner_idle(...)` in the leave predicate at :2724; tag every constant with `// provenance:<file:line>` (0x1e = sub_8008064 timer-arm, 0x293 = sub_8008064 timer-arm2) → *report the new function body, the cite count, the diff at src/battle.rs:1116 and :2724, fitted-constant count delta (HEAD: 19).*
4. Re-run `tools/trace.py record/diff --align row:battle_full` → *report: self.seq.state k=0..210 sequence (target: SEQ_20 at canon k=31 on rust; SEQ_04 leaves at the canonical idle check not at frame 60); battle_full sequencer divergence count (target ≤100/540 from 173/540); cursor stays ≤1/1/170.*
5. Re-run `tools/verify_rows.py` from a clean detached checkout → *report: 67-row table — every chip row 0/0/30, mettaur 0/0/70, wave 0/0/90, popup 0/0/80, windowclose 0/0/40, result 0/0/40, field 0/0/40, buster 0/0/28, warp 0/0/30; opening integrated stays 72499/2691; warp integrated stays 40628/11744/30; buster integrated stays 54672/12977/28; cursor stays ≤1/1/170.*
6. Land with `tools/land.sh` and re-run the free row check on main → *report: 67-row table identical to HEAD except battle_full sequencer divergence count drops; SEQ04_FRAMES=60 removed from src/battle.rs; no allowlist change.*

**Rules.** Only the named files; no new harness row; no alignment change; the fix is porting sub_801E754's banner-idle check (cite asm00_1.s:10422) — never a fitted timer constant and never a hardcoded frame count; every new literal gets a `// provenance:` tag with the asm file:line; `fitted constants in src/` (HEAD: 19) must not increase (and should drop by 1 with SEQ04_FRAMES=60 removed); canon never changes; ≤6 capture runs, one at a time inside the 3-slot semaphore; tool budget ≤100 (more than the 60 that blocked T7m / 80 that blocked F35a, so the port phase has budget).

**Acceptance.** battle_full sequencer divergence ≤100/540 (from 173/540); SEQ04_FRAMES=60 removed from src/battle.rs; sub_801E754 banner-idle check cited at asm00_1.s:10422 + sub_8008064 at asm00_1.s:10514 in src/battle.rs comments; fitted-constant count drops by 1; cursor stays ≤1/1/170; mettaur 0/0/70; every isolated pixel row reads 0; no allowlist change.

**Measure and report.** row: battle_full + cursor + windowclose + mettaur + result + field + wave + popup + the chip rows. frames: 540 battle_full, 170 cursor, 70 mettaur. total/worst: battle_full sequencer before/after (173/540 → ≤100/540); per-region divergence k=31..195 window-setup vs k=297..304 kill-timing. region: window-setup 165 frames at k=31..195 in self.seq.state field. commit: src/battle.rs (banner_idle fn + leave-predicate swap). One line of mechanism (sub_801E754's banner-idle check at asm00_1.s:10422 is the SEQ_04 leave predicate; arming timers 0x1e and 0x293 is the entry path, sub_8008064 asm00_1.s:10514 writes 0x08 only when the check returns 0). One line of what is unverified (whether the 8 kill-timing frames at k=297..304 also shift once window-setup aligns, since T7e's done-state was measured against the fitted frame count).

**Coordinator:** dispatch first. Worker muse-spark-1.3-contributor (T7d/T7f's child class — sequencer-edge port), verifier GLM-5.3-flash cross-family; ≤$0.30 expected, ≤$0.60 cap; tool budget ≤100; verify_rows on the regression set plus the fitted-constant count. Advances **M2** (sequencer coverage; 165 window-setup frames is the largest remaining M2 residue).

---

### F36b. warp integrated ~40628: per-region decomposition, then port the canon mechanism for each non-zero region  *(BLOCKED -- 2026-09-15, no code change, tool budget soft-cap hit at 80 before port)*

**Result.** no code change, tool budget soft-cap hit at 80 before port; decomposition finding: 99.2% BG1 backdrop (40302 px, y=24..143), HUD 326 px, BG3/OBJ clean — same class as field integrated 158935/5606 and buster integrated 45810/27225 BG1 phase (sub_8001C94 / BGScrollCB_BG1Diagonal3to2Scroll src/backdrop.rs:5,29); warp isolated 0/0/30; cursor 1/1/170; mettaur/wc/result 0/0; cost $0.288 model=minimax/MiniMax-M3:high
**Why.** F36a PARTIAL gave the actual warp integrated baseline: 40628/11744/30 (NOT 363658 headline — F38b event-lock pin rust_offset=5 changed the count). Warp isolated is 0/0/30 PASS per F11 DONE. The integrated variant leaves the HUD strip + BG1 backdrop + OBJ warp line on, where F11 isolated only the OBJ warp line (sub_8009C1C cite). M2 acceptance is "integrated-row pixel parity"; closing warp integrated is one of the four large integrated remnants alongside opening 72499/2691 and buster 54672/12977/28. F36a did no code change — only baseline + decomposition from F33c notes. Warp's baseline is the smallest of the four (40628 vs 54672 vs 72499).

**Files.** tools/harness.py (only the warp-integrated fixture descriptor — confirm demo-* flag and alignment), src/battle.rs (only the warp path if a per-tick write is needed), src/objects.rs (only the warp's per-state behavior in full-HUD context), src/fixture.rs (only if a new descriptor field is needed), tools/allowlist.py (only the warp:integrated entry if the row reads 0/0/30), tools/diffmask.py (only for region split), docs/coverage/warp_integrated.md (notes)

**Do.**
1. Baseline `tools/harness.py --only warp --ui integrated` on HEAD → *report: warp integrated 40628/11744/30 (F36a PARTIAL value); warp isolated 0/0/30 PASS (F11); cursor ≤1/1/170; mettaur 0/0/70; windowclose/result/field 0/0/40; all chip rows 0/0/30.*
2. Run `tools/diffmask.py --row warp --ui integrated` to split the residue by region (HUD strip y<24, BG1 backdrop, BG3 window ramp, OBJ warp line); cross-reference `tools/harness.py --only warp --ui integrated --only-bg 1` and `--only-bg 3` and `--disable-obj` to attribute by layer → *report the per-region pixel totals and the per-frame sequence k=0..N.*
3. Find the canon mechanism for each non-zero region in `reference/bn6f/asm/`: HUD strip sub_8026BF4 (per F18b cite), BG1 backdrop sub_8001C94 (per F6 cite), BG3 window ramp sub_801C4E4 (per F35a cite), OBJ warp line sub_8009C1C (per F11 cite) → *report the per-region cite, file:line, and the per-region canon mechanism; cross-reference F11's OBJ cite for the warp's own action.*
4. Port the per-region mechanism into src/battle.rs / src/objects.rs / src/custom.rs / src/backdrop.rs as needed; cite each fix to file:line with `// provenance:` tags; never fit a hardcoded BG layer write or a hardcoded frame count — port the canon routine → *report the per-region port, the cite count, the diff per file.*
5. Re-run `tools/harness.py --only warp --ui integrated` and `tools/verify_rows.py` from a clean detached checkout → *report: warp integrated before/after (40628/11744/30 → 0/0/30); warp isolated stays 0/0/30; cursor stays ≤1/1/170; mettaur 0/0/70; windowclose/result/field 0/0/40; all chip rows 0/0/30; full regression set 0/0.*
6. Land with `tools/land.sh` and re-run the free row check on main → *report: 67-row table identical to HEAD except warp integrated 0/0/30; remove the `warp:integrated` allowlist entry from tools/allowlist.py.*

**Rules.** Only the named files; the AUDIT-6 allowance for `warp:integrated` is in tools/allowlist.py — it is removed only after verify_rows PASS at 0/0/30; no new harness row; no alignment change; the fix is a port of canon's HUD + BG1 + BG3 + OBJ routines — never a fitted layer write or a hardcoded frame count; every new literal gets a `// provenance:` tag with the cite; `fitted constants in src/` (HEAD: 19) may not increase; canon never changes; ≤4 capture runs, one at a time inside the 3-slot semaphore; tool budget ≤100 to keep the port phase from blocking (F35a hit 80 before port).

**Acceptance.** warp integrated reads 0/0/30 with the per-region mechanism cited at sub_8026BF4 (HUD) + sub_8001C94 (BG1) + sub_801C4E4 (BG3) + sub_8009C1C (OBJ); warp isolated stays 0/0/30; cursor ≤1/1/170; mettaur 0/0/70; windowclose/result/field 0/0/40; all chip rows 0/0/30; `warp:integrated` removed from tools/allowlist.py; no allowlist change elsewhere; fitted-constant count unchanged or lower.

**Measure and report.** row: warp (integrated) + warp (isolated) + cursor + windowclose + mettaur + result + field + the chip rows. frames: 30 warp, 170 cursor, 70 mettaur. total/worst: warp integrated before/after (40628/11744/30 → 0/0/30); per-region pixel totals HUD/BG1/BG3/OBJ; per-frame sequence k=0..N. region: HUD strip y<24, BG1 backdrop, BG3 window ramp, OBJ warp line. commit: src/battle.rs + src/objects.rs + src/custom.rs + src/backdrop.rs (per-region port) + tools/allowlist.py (AUDIT-6 removal). One line of mechanism (warp integrated's residue lives in four canon routines — HUD strip sub_8026BF4, BG1 backdrop sub_8001C94, BG3 window ramp sub_801C4E4, OBJ warp line sub_8009C1C — each ported with cited file:line). One line of what is unverified (whether the OBJ layer holds additional residue that needs its own per-element cite, since F11's isolated OBJ cite was for the warp action only and the integrated OBJ layer is the full HUD context).

**Coordinator:** dispatch second. Worker muse-spark-1.3-contributor (F11's child class — per-region integrated port), verifier GLM-5.3-flash cross-family; ≤$0.30 expected, ≤$0.60 cap; tool budget ≤100; verify_rows on the full table. Advances **M2** (integrated warp; closes one of the four large integrated remnants after F36a).

---

### F38h. opening integrated 72499: descriptor-preserving per-enemy panel encoding so cursor fixture state file stays valid  *(PARTIAL -- 2026-09-15, opening integrated 72499/2691 -> 25829/931 [residual is PAL_OBJ allocation order src/spr.rs:701-761 per F38e B)*

**Result.** opening integrated 72499/2691 -> 25829/931 (residual is PAL_OBJ allocation order src/spr.rs:701-761 per F38e BLOCKED, not in scope). cursor 1/1/170 (≤1/1/170 acceptance, MATCH). all other rows PASS MATCH. cost $0.580 model=minimax/MiniMax-M3:high
**Why.** F38g BLOCKED: /tmp/chipselect.state is hand-captured RASTATE root the harness refuses to overwrite, so F38f's 64→67-byte descriptor change (FIXTURE_SIZE +17, TRACE_OFFSET +4) couldn't be paired with a cursor state regen — F38f PARTIAL with revert (commit 63cb569, cursor regressed 1/1/170 → 26/25/170). F38e BLOCKED: spawn-cell fix needs per-enemy panel data per spawnEnemy_80073E2 (asm00_1.s:8695), but src/fixture.rs (the natural location) is outside F38e's allowed files, and a hardcoded triple violates "never a fitted panel triple"; sub_801641A (asm00_2.s:16101-16136) does NOT do per-step y motion — only Timer/Timer2 + mosaic+alpha setters. The per-enemy panel triple (5,1)/(5,3)/(6,2) per F38f's port is correct canon data. Encoding fits into unused descriptor offsets 56-62 within the 64-byte descriptor: panel_col[3] at +56, panel_row[3] at +59, panel_override_mask u8 at +62. Cursor state file's offsets 56-62 = 0 (unused when captured) → mask=0 → no override → existing cursor behavior preserved; opening state file rebuilt with mask=0x07 + panels=[5,1,5,3,6,2]. M2 acceptance is "integrated-row pixel parity"; opening integrated is the largest of the four large integrated remnants.

**Files.** src/fixture.rs (read panel data + mask at offsets 56-62; default mask=0 = no override), src/battle.rs (only the spawn-cell path at :1907-1908, read override panel if mask bit set), tools/harness.py (only the descriptor encoding at offsets 56-62), tools/states.py (only the opening scenario's rebuild to set mask=0x07 + panels; chipselect unchanged), FIXTURE.md (add the new fields), docs/coverage/opening_integrated.md (notes)

**Do.**
1. Baseline `tools/harness.py --only opening --ui integrated` on HEAD → *report: opening integrated 72499/2691/40; cursor ≤1/1/170; mettaur 0/0/70; windowclose/result/field 0/0/40; all chip rows 0/0/30.*
2. Read spawnEnemy_80073E2 (asm00_1.s:8695) for the per-enemy panel triple's role and the relationship to src/battle.rs:1907-1908 → *report: file:line, the per-slot panel-override path, the existing default rule (diagonal across slots 0/1/2).*
3. Add `panel_col[3]` + `panel_row[3]` + `panel_override_mask` at offsets 56-62 in tools/harness.py descriptor encoding; update FIXTURE.md → *report: the new offsets, chipselect auto-populated values (mask=0 = no override, behavior unchanged), diff at tools/harness.py + FIXTURE.md.*
4. Add src/fixture.rs read at offsets 56-62 with default mask=0; src/battle.rs:1907-1908 reads `fixture.panel_override_mask & (1<<i)` and uses panel_col[i]/panel_row[i] for enemy slot i if set → *report: new read code, spawn-cell diff, fitted-constant count delta (HEAD: 19).*
5. Rebuild tools/states.py opening scenario (mask=0x07, panel_col=[5,5,6], panel_row=[1,3,2]); re-run `tools/harness.py --only opening --ui integrated` → *report: opening integrated before/after (72499/2691 → 0/0 or strictly less); cursor stays ≤1/1/170; mettaur 0/0/70; windowclose/result/field 0/0/40; all chip rows 0/0/30.*
6. Re-run `tools/verify_rows.py` → *report: 67-row table — every chip row 0/0/30, mettaur 0/0/70, wave 0/0/90, popup 0/0/80, windowclose 0/0/40, result 0/0/40, field 0/0/40, buster 0/0/28, warp 0/0/30; opening integrated 0/0/40 or strictly less; warp integrated stays 40628/11744/30; buster integrated stays 54672/12977/28; cursor stays ≤1/1/170.*
7. Land → *report: 67-row table identical to HEAD except opening integrated drops; remove `opening:integrated` allowlist entry from tools/allowlist.py.*

**Rules.** Only the named files; FIXTURE_SIZE stays 64 (no descriptor size change, cursor fixture state file structurally compatible); override is opt-in via mask bit (cursor state file's 0/0/0 mask=0 = no override = preserved behavior); no new harness row; no alignment change; the spawn-cell diff is a port of spawnEnemy_80073E2 (cite asm00_1.s:8695); the panel triple is data from canon (per-scenario, not hardcoded in src/), so it is "derived" not "fitted"; every new literal gets `// provenance:`; `fitted constants in src/` (HEAD: 19) may not increase; canon never changes; ≤4 capture runs, one at a time inside the 3-slot semaphore; tool budget ≤100.

**Acceptance.** opening integrated reads 0/0/40 (or strictly less than 72499/2691) with spawnEnemy_80073E2 cited at asm00_1.s:8695 in src/battle.rs comments; panel_override_mask=0x07 + panel_col=[5,5,6] + panel_row=[1,3,2] in tools/states.py opening scenario; cursor stays ≤1/1/170 (chipselect state file unchanged, mask=0 = no override); mettaur 0/0/70; windowclose/result/field 0/0/40; all chip rows 0/0/30; `opening:integrated` removed from tools/allowlist.py; no allowlist change elsewhere; fitted-constant count unchanged or lower.

**Measure and report.** row: opening (integrated) + cursor + windowclose + mettaur + result + field + the chip rows. frames: 40 opening, 170 cursor. total/worst: opening integrated before/after (72499/2691 → 0/0); per-region top/mid/bot pixel counts; per-enemy spawn position on both sides. region: per-enemy (col, row) at materialized frames on both sides; per-frame OAM trace k=10..39; the spawn-cell fan-out at k=20..33. commit: src/fixture.rs + src/battle.rs + tools/harness.py + tools/states.py + FIXTURE.md. One line of mechanism (canon spawns the enemies at the per-enemy panel triple (5,1)/(5,3)/(6,2) read from spawnEnemy_80073E2 asm00_1.s:8695; the descriptor's panel_override_mask=0x07 makes the change additive — chipselect state file's 0/0/0 mask=0 keeps cursor behavior unchanged while the opening scenario sets mask=0x07 with explicit panels). One line of unverified (whether the materialize y offset from F38e BLOCKED also drops after the spawn cells land — sub_801641A asm00_2.s:16101-16136 may not do per-step y motion, so the y delta may have a separate cause that needs its own ticket).

**Coordinator:** dispatch first. Worker muse-spark-1.3-contributor (F38f/F38g's child class — descriptor-preserving port), verifier GLM-5.3-flash cross-family; ≤$0.30 expected, ≤$0.60 cap; tool budget ≤100; verify_rows on the full table. Advances **M2** (integrated opening; the largest remaining integrated row at 72499/2691/40).

---

### F37k. cursor 3 px residue at k=37/97 via per-scanline BG1 backdrop seam port  *(BLOCKED -- 2026-09-15, infra failures [bash exit 1, then model cold-start on resume])*

**Result.** infra failures (bash exit 1, then model cold-start on resume); worker explored tools/harness.py and src/ but never reached baseline measurement; no commits, no progress; cost $0.125 model=minimax/MiniMax-M3:high
**Why.** F37i BLOCKED (BG1 backdrop drain in src/backdrop.rs; tool budget 60 before port) and F37j NEGATIVE (port canon's QueueEightWordAlignedGFXTransfer drain into src/backdrop.rs; both drain-timing ports regressed cursor) on the 3 px residue at k=37/97 (cursor 1/1/170 — the last unfixed pixel on the cursor row). The 60-frame periodicity (k=37, k=97 differ by 60) matches Battle::tick % 60 in canon's BGScrollCB_BG1Diagonal3to2Scroll (sub_8001C94, per F6 cite in tools/harness.py:1708). The 3 px is the seam tile transition at the BG1 drain scanline (around y=143 per F36a's warp decomposition at 40302 px y=24..143). A per-scanline port from sub_8001C94's BG1 seam handler into src/backdrop.rs respects the 60-frame cycle without the drain-timing regression F37j hit. M2 acceptance is "integrated-row pixel parity"; closing the cursor row at 0/0/170 removes one of the four small cursor residues (the 3 px is the last).

**Files.** src/backdrop.rs (only the BG1 seam transition path), src/battle.rs (only if the BG1 seam is reached from a per-tick battle path), tools/harness.py (only if a new BG1 phase probe is needed), tools/diffmask.py (only for region split at the seam), docs/coverage/cursor.md (notes)

**Do.**
1. Baseline `tools/harness.py --only cursor --ui isolated` on HEAD → *report: cursor 1/1/170 (3 px residue at k=37/97); windowclose 0/0/40; mettaur 0/0/70; result/field 0/0/40; all chip rows 0/0/30.*
2. Run `tools/diffmask.py --row cursor --ui isolated --frame 37` and `--frame 97` → *report: per-frame pixel locations of the 3 px residue (likely BG1 backdrop seam, scanline y~143 per F36a).*
3. Read sub_8001C94 (BGScrollCB_BG1Diagonal3to2Scroll, asm00_1.s) for the BG1 seam transition's per-scanline timing and the 60-frame cycle → *report: file:line for the seam transition, the 60-frame cycle's source (likely modulo a backdrop phase counter), the per-scanline write path.*
4. Port sub_8001C94's seam transition into src/backdrop.rs as `fn bg1_seam_transition(bg_phase: u32) -> u8` with cited file:line → *report: new fn body, cite count, diff at src/backdrop.rs, fitted-constant count delta (HEAD: 19).*
5. Re-run `tools/harness.py --only cursor --ui isolated` → *report: cursor before/after (1/1/170 → 0/0/170); windowclose stays 0/0/40; mettaur stays 0/0/70; result/field stays 0/0/40; all chip rows stay 0/0/30.*
6. Re-run `tools/verify_rows.py` → *report: 67-row table — every chip row 0/0/30, mettaur 0/0/70, wave 0/0/90, popup 0/0/80, windowclose 0/0/40, result 0/0/40, field 0/0/40, buster 0/0/28, warp 0/0/30; cursor 0/0/170; opening integrated stays 72499/2691/40; warp integrated stays 40628/11744/30; buster integrated stays 54672/12977/28.*
7. Land → *report: 67-row table identical to HEAD except cursor 0/0/170.*

**Rules.** Only the named files; no new harness row; no alignment change; the fix ports sub_8001C94's BG1 seam transition (cite asm00_1.s) — never a fitted seam tile value; every new literal gets `// provenance:`; `fitted constants in src/` (HEAD: 19) may not increase; canon never changes; ≤4 capture runs, one at a time inside the 3-slot semaphore; tool budget ≤100.

**Acceptance.** cursor reads 0/0/170 (from 1/1/170); sub_8001C94 cited at asm00_1.s:line in src/backdrop.rs comments; windowclose stays 0/0/40; mettaur stays 0/0/70; result/field stays 0/0/40; all chip rows stay 0/0/30; no allowlist change.

**Measure and report.** row: cursor + windowclose + mettaur + result + field + the chip rows. frames: 170 cursor, 70 mettaur, 40 others. total/worst: cursor before/after (1/1/170 → 0/0/170); per-frame pixel location of the 3 px residue at k=37 and k=97. region: BG1 backdrop seam, scanline y~143. commit: src/backdrop.rs (+ fn). One line of mechanism (sub_8001C94's BG1 seam transition runs once per 60 frames on the BGScrollCB_BG1Diagonal3to2Scroll path; the 3 px at k=37/97 is the seam tile transition's per-scanline write that needs the canonical phase). One line of unverified (whether the seam transition has additional per-element residues that need their own cite, since F37i/F37j both tried BG1-side approaches and neither landed — a third path's failure mode is unknown).

**Coordinator:** dispatch second. Worker muse-spark-1.3-contributor (F37i/F37j's child class — per-scanline BG1 seam port), verifier GLM-5.3-flash cross-family; ≤$0.20 expected, ≤$0.50 cap; tool budget ≤100; verify_rows on the regression set. Advances **M2** (cursor row at 0/0/170).

---

### T7v. battle_full RNG cadence 9/540 → 0/540: port the per-site mirror at the remaining divergence frames  *(BLOCKED -- 2026-09-15, no code change)*

**Result.** no code change; cited mechanism (sub_80C7EC8 death-debris spawner) insufficient alone. baseline shifted to 14/540 [T7r PARTIAL chip-window stalls added 9 frames]. Per-site mirror would close 2/14 [k=282/283], other 12 are sites outside cited scope [rust-side stalls + other per-site draws]. cost $0.281 model=minimax/MiniMax-M3:high
**Why.** T7n PARTIAL named the rng_cadence first-divergence at k=271 on 10/540 frames (cite sub_80C7EC8 / cbGameState_80050EC). T7p DONE was a no-op (HEAD rng_cadence 9/540, already below the ≤10/540 acceptance threshold per T7p's landing 784c8e5). The remaining 9 frames are at known positions per T7n's divergence list. M2 acceptance is "battle_full trace: first divergence none" — pushing 9/540 → 0/540 fully clears the M2 trace metric. The per-site mirror at sub_80C7EC8 ticks once per frame and cbGameState_80050EC is the per-site reader; both are cited in T7n PARTIAL.

**Files.** src/rng.rs (only the per-site mirror at the named sites), src/battle.rs (only if the read-site is reached from a per-tick battle path), tools/trace.py (only if rng_cadence watch needs widening), docs/coverage/battle_full.md (notes)

**Do.**
1. Baseline `tools/trace.py record/diff --align row:battle_full` on HEAD → *report: 9/540 rng_cadence divergence frames with k-values; oracle's first divergent field; mm_state_action/mm_anim/mm_timer values at each divergent frame; battle_full sequencer 9/540 (from HEAD per T7p).*
2. Read sub_80C7EC8 (in disasm) and cbGameState_80050EC for the rng_cadence mirror's per-tick read site and the call chain → *report: file:line for each, the cited routine that touches rng_cadence, the per-tick call site.*
3. Port the per-site mirror into src/rng.rs as `fn tick_rng_cadence(state: &mut BattleState)` with cited file:line → *report: new fn body, cite count, diff at src/rng.rs, fitted-constant count delta (HEAD: 19).*
4. Re-run `tools/trace.py record/diff --align row:battle_full` → *report: rng_cadence divergence before/after (target 0/540); battle_full sequencer 0/540; cursor stays ≤1/1/170.*
5. Re-run `tools/verify_rows.py` → *report: 67-row table — every chip row 0/0/30, mettaur 0/0/70, wave 0/0/90, popup 0/0/80, windowclose 0/0/40, result 0/0/40, field 0/0/40, buster 0/0/28, warp 0/0/30; opening integrated stays 72499/2691/40; warp integrated stays 40628/11744/30; buster integrated stays 54672/12977/28; cursor stays ≤1/1/170.*
6. Land → *report: 67-row table identical to HEAD except battle_full sequencer 0/540.*

**Rules.** Only the named files; no new harness row; no alignment change; the fix ports the per-site mirror (cite file:line) — never a fitted cadence value; every new literal gets `// provenance:`; `fitted constants in src/` (HEAD: 19) may not increase; canon never changes; ≤4 capture runs, one at a time inside the 3-slot semaphore; tool budget ≤100.

**Acceptance.** battle_full sequencer 0/540 (from 9/540); rng_cadence divergence 0/540 (from 9/540); sub_80C7EC8 + cbGameState_80050EC cited at asm file:line in src/rng.rs comments; cursor stays ≤1/1/170; mettaur 0/0/70; every isolated pixel row reads 0; no allowlist change.

**Measure and report.** row: battle_full + cursor + windowclose + mettaur + result + field + wave + popup + the chip rows. frames: 540 battle_full, 170 cursor. total: rng_cadence 9/540 → 0/540; battle_full sequencer 9/540 → 0/540; per-frame divergence list with k-values. region: rng_cadence field at k=271+ frames. commit: src/rng.rs (+ fn). One line of mechanism (rng_cadence mirror at sub_80C7EC8 ticks once per frame; cbGameState_80050EC is the per-site reader; the 9 remaining frames are at the named k-positions and need the per-site write ported into src/rng.rs). One line of unverified (whether the closed cadence frames also fix the mm_state_action/mm_anim/mm_timer residue at k=179, since T7m BLOCKED on that group and T7q PARTIAL added a seq.state gate that may not fully resolve it).

**Coordinator:** dispatch third. Worker muse-spark-1.3-contributor (T7n/T7p's child class — per-site rng mirror), verifier GLM-5.3-flash cross-family; ≤$0.20 expected, ≤$0.50 cap; tool budget ≤100; verify_rows on the regression set. Advances **M2** (battle_full sequencer 0/540).

### F38i. opening integrated 25829: PAL_OBJ allocation order port in src/spr.rs to clear the per-object OAM colour residue  *(PARTIAL -- 2026-09-15, opening integrated already at 0/0 on main HEAD [8b314eb] per verify_rows — NOT 25829/931 as F38h PARTIAL commi)*

**Result.** opening integrated already at 0/0 on main HEAD (8b314eb) per verify_rows — NOT 25829/931 as F38h PARTIAL commit message stated; worker's measurement of 25829/931 on branch does not reproduce (verify_rows at b337528 reports 0/0/40). Worker added 48-line dead-code stub fn pal_obj_allocate(src/spr.rs:691) per own admission; cite corrected to sub_8002818 (sprite.s:254-303) instead of ticket's wrong sub_801C6EE — actual canon mechanism pins PAL_OBJ slot to pal_offset directly which agb's try_allocate_shared cannot replicate without fitted slot (forbidden). All attempts to wire in regressed other rows. Branch kept unmerged: report's numbers did not reproduce (worker's 25829/931 vs actual 0/0); fitted count 19 unchanged; no allowlist change.
**Why.** F38h PARTIAL (2026-09-15) dropped opening integrated 72499/2691 → 25829/931 by porting the per-enemy panel triple (5,1)/(5,3)/(6,2) from spawnEnemy_80073E2 (asm00_1.s:8695) with mask=0x07 in the 64-byte descriptor. F38e BLOCKED named the residual: PAL_OBJ allocation order src/spr.rs:701-761 — outgoing sprites hold the only other references to the previous palette, so they go first (`self.parts.clear()` precedes `try_allocate_shared`), and at OAM load the per-sprite `e.pal_offset` is decoded against the SHIFTED palette (Barr100's bubble, offset 3 → gold shades 4/5) versus the FRAME palette (HiCannon's offset 4 still reads flat 4). On opening integrated's 0x86-prefix materialization, our OAM's per-sprite palette reads back in the wrong slot, giving 25829 px of BG1 backdrop seam + per-object OAM colour over the per-enemy rows. sub_801C6EE (asm00_2.s:26619, renderTextGfx_8045F8C caller) is the canon per-sprite palette source. M2 acceptance is "integrated-row pixel parity"; the per-enemy cell fix F38h landed passes the spawn-position row, leaving PAL_OBJ as the named next mechanism.

**Files.** src/spr.rs (only the PAL_OBJ allocation block at :701-761 and the per-sprite `offsets_follow_shift` decode around :720-740), src/actor.rs (only if a per-sprite palette source is read at materialization), src/battle.rs (only if the materialize y offset from F38e BLOCKED overlaps with PAL_OBJ allocation), tools/diffmask.py (only for region split PAL_OBJ vs BG1), docs/coverage/opening_integrated.md (notes)

**Do.**
1. Baseline `tools/harness.py --only opening --ui integrated` on HEAD → *report: opening integrated 25829/931/40 (F38h PARTIAL value); cursor ≤1/1/170; mettaur 0/0/70; windowclose/result/field 0/0/40; all chip rows 0/0/30.*
2. Run `tools/diffmask.py --row opening --ui integrated` to split the 25829 px into PAL_OBJ allocation (~per-object OAM colour) vs BG1 backdrop seam (~per-scanline backdrop) → *report: per-region pixel totals; per-frame sequence k=0..39 split by region; confirm 25829 = PAL_OBJ + BG1 with file:line.*
3. Read src/spr.rs:701-761 and `offsets_follow_shift` decode (around :720-740); cross-reference sub_801C6EE (asm00_2.s:26619) for the per-sprite palette source → *report: the current PAL_OBJ allocation rule, the per-sprite offset decode, the cited canon route; whether the per-sprite offset follows the SHIFT or FRAME palette on the opening materialization.*
4. Port sub_801C6EE's per-sprite palette source into src/spr.rs:701-761 as `fn pal_obj_allocate(frame: &SpriteFrame, sprite_index: usize) -> PaletteVramSingle` with cited file:line per literal; never fit a hardcoded palette slot for any sprite; tag every literal with `// provenance:<file:line>` → *report: new fn body, cite count, diff at src/spr.rs:701-761, fitted-constant count delta (HEAD: 19).*
5. Re-run `tools/harness.py --only opening --ui integrated` → *report: opening integrated before/after (25829/931 → 0/0 or strictly less); cursor stays ≤1/1/170; mettaur 0/0/70; windowclose/result/field 0/0/40; all chip rows 0/0/30.*
6. Re-run `tools/verify_rows.py` from a clean detached checkout → *report: 67-row table — every chip row 0/0/30, mettaur 0/0/70, wave 0/0/90, popup 0/0/80, windowclose 0/0/40, result 0/0/40, field 0/0/40, buster 0/0/28, warp 0/0/30; opening integrated 0/0/40 or strictly less; warp integrated stays 40628/11744/30; buster integrated stays 54672/12977/28; cursor stays ≤1/1/170.*
7. Land with `tools/land.sh` and re-run the free row check on main → *report: 67-row table identical to HEAD except opening integrated drops; remove `opening:integrated` allowlist entry from tools/allowlist.py.*

**Rules.** Only the named files; no new harness row; no alignment change; the PAL_OBJ allocation diff is a port of sub_801C6EE (cite asm00_2.s:26619) and the per-sprite palette source from `offsets_follow_shift` — never a fitted palette slot or a hardcoded OAM colour; every new literal gets `// provenance:`; `fitted constants in src/` (HEAD: 19) may not increase; canon never changes; ≤4 capture runs, one at a time inside the 3-slot semaphore; tool budget ≤100.

**Acceptance.** opening integrated reads 0/0/40 (or strictly less than 25829/931) with sub_801C6EE cited at asm00_2.s:26619 + the per-sprite `offsets_follow_shift` decode in src/spr.rs comments; cursor stays ≤1/1/170; mettaur 0/0/70; windowclose/result/field 0/0/40; all chip rows 0/0/30; `opening:integrated` removed from tools/allowlist.py; no allowlist change elsewhere; fitted-constant count unchanged or lower.

**Measure and report.** row: opening (integrated) + cursor + windowclose + mettaur + result + field + the chip rows. frames: 40 opening, 170 cursor. total/worst: opening integrated before/after (25829/931 → 0/0 or strictly less); per-region PAL_OBJ/BG1 pixel counts; per-frame OAM colour trace k=10..39. region: per-sprite OAM colour at materialized frames on both sides; the PAL_OBJ allocation slot at materialize. commit: src/spr.rs (+ fn) + src/actor.rs (if materialization). One line of mechanism (canon allocates PAL_OBJ at sub_801C6EE asm00_2.s:26619 with the outgoing sprites' palette slots freed before the incoming per-sprite decode, and the per-sprite offset follows the SHIFT vs FRAME palette via `offsets_follow_shift`; src/spr.rs:701-761 currently clears `self.parts` first but reads `e.pal_offset` against `frame.pal` not `frame.pal + palette_add`, leaving SHIFT-following sprites on the wrong palette slot). One line of unverified (whether the materialize y offset from F38e BLOCKED also drops after PAL_OBJ lands — sub_801641A asm00_2.s:16101-16136 may not do per-step y motion, so the y delta may have a separate cause that needs its own ticket; F38h PARTIAL's 25829/931 was attributed to PAL_OBJ per F38e BLOCKED, but the y offset is independent).

**Coordinator:** dispatch first. Worker muse-spark-1.3-contributor (F38h/F38e's child class — PAL_OBJ allocation port), verifier GLM-5.3-flash cross-family; ≤$0.30 expected, ≤$0.60 cap; tool budget ≤100; verify_rows on the full table. Advances **M2** (integrated opening 25829 → 0).

---

### F37l. cursor 3 px residue at k=37/97 via per-element BG1 seam cite at sub_8001C94 (asm00_0.s:3752)  *(BLOCKED -- 2026-09-15, cursor 1/1/170 isolated: residue is 1 px at [183,5] on k=97 ONLY [k=37 already 0 after F38h merge 2d1e639], NO)*

**Result.** cursor 1/1/170 isolated: residue is 1 px at (183,5) on k=97 ONLY (k=37 already 0 after F38h merge 2d1e639), NOT 3 px at k=37/97 as ticket claimed; region at scanline y=5, NOT y=143. sub_8001C94 per-element handlers do per-tile byte transforms into an EWRAM buffer; our BNBD stores all 7 GFXAnim steps pre-transformed so the data port is a no-op; the residue's actual mechanism is canon's ProcessGFXTransferQueue (asm00_0.s:832) LANDS THE TILES MID-FRAME while our show_step's replace_tile loop writes all 36 tiles before scanline 0. Closing requires sub-frame tile replacement infra (HBlank callback / mid-scanline drain queue / scanline-keyed apply) that does not exist and is out of scope. Branch wt/f37l-bg1-seam has notes-only commit (no src/ changes), HEAD 7a93fbf. Fitted-constant count unchanged at 19.
**Why.** F37i BLOCKED tried the BG1 backdrop drain in src/backdrop.rs (tool budget 60 before port), F37j NEGATIVE tried two drain-timing ports of canon's QueueEightWordAlignedGFXTransfer into src/backdrop.rs and both regressed cursor, F37k BLOCKED on infra failure (no code change, $0.125). The 3 px residue at k=37/97 (cursor 1/1/170) is the last unfixed pixel on the cursor row, with a 60-frame periodicity (k=97 - k=37 = 60) that matches `Battle::tick % 60` — canon's BGScrollCB_BG1Diagonal3to2Scroll (sub_8001C94, asm00_0.s:3752) ticks the GFXAnim seam transition on a 60-frame cadence per `eGFXAnimStates[0].Timer` decrement. A different approach: per-element cite of sub_8001C94's seam write at the specific scanline the residue falls in (around y=143 per F36a's warp decomposition at 40302 px y=24..143), porting only the per-element write path with its cited `// provenance:` tag — never the QueueEightWordAlignedGFXTransfer drain path that F37j regressed on. M2 acceptance is "isolated-row pixel parity"; closing cursor at 0/0/170 removes one of the four small cursor residues.

**Files.** src/backdrop.rs (only the per-element seam write at the y~143 scanline, never the QueueEightWordAlignedGFXTransfer drain path that F37j regressed on), tools/diffmask.py (only for region confirmation at y~143), docs/coverage/cursor.md (notes)

**Do.**
1. Baseline `tools/harness.py --only cursor --ui isolated` on HEAD → *report: cursor 1/1/170 (3 px residue at k=37/97); windowclose 0/0/40; mettaur 0/0/70; result/field 0/0/40; all chip rows 0/0/30.*
2. Run `tools/diffmask.py --row cursor --ui isolated --frame 37` and `--frame 97` → *report: per-frame pixel locations of the 3 px residue (BG1 backdrop seam at scanline y~143, the seam tile transition at sub_8001C94's per-step write).*
3. Read sub_8001C94 (asm00_0.s:3752) for the per-element seam write at the y~143 scanline; read the 60-frame `Timer` decrement path → *report: file:line for the per-element seam write, the 60-frame cycle's source (likely modulo a backdrop phase counter), the per-element write path's exact register/variable.*
4. Port sub_8001C94's per-element seam write into src/backdrop.rs as `fn bg1_seam_per_element_write(slot: &mut GFXAnimSlot, scanline: u32) -> u8` with cited file:line → *report: new fn body, cite count, diff at src/backdrop.rs, fitted-constant count delta (HEAD: 19).*
5. Re-run `tools/harness.py --only cursor --ui isolated` → *report: cursor before/after (1/1/170 → 0/0/170); windowclose stays 0/0/40; mettaur stays 0/0/70; result/field stays 0/0/40; all chip rows stay 0/0/30.*
6. Re-run `tools/verify_rows.py` from a clean detached checkout → *report: 67-row table — every chip row 0/0/30, mettaur 0/0/70, wave 0/0/90, popup 0/0/80, windowclose 0/0/40, result 0/0/40, field 0/0/40, buster 0/0/28, warp 0/0/30; cursor 0/0/170; opening integrated stays 25829/931/40 (F38h PARTIAL value, expected to drop via F38i); warp integrated stays 40628/11744/30; buster integrated stays 54672/12977/28.*
7. Land with `tools/land.sh` and re-run the free row check on main → *report: 67-row table identical to HEAD except cursor 0/0/170.*

**Rules.** Only the named files; no new harness row; no alignment change; the per-element seam write ports sub_8001C94 (cite asm00_0.s:3752) — never a fitted seam tile value, never the QueueEightWordAlignedGFXTransfer drain path that F37j regressed on; every new literal gets `// provenance:`; `fitted constants in src/` (HEAD: 19) may not increase; canon never changes; ≤4 capture runs, one at a time inside the 3-slot semaphore; tool budget ≤100.

**Acceptance.** cursor reads 0/0/170 (from 1/1/170); sub_8001C94 cited at asm00_0.s:3752 in src/backdrop.rs comments; windowclose stays 0/0/40; mettaur stays 0/0/70; result/field stays 0/0/40; all chip rows stay 0/0/30; no allowlist change.

**Measure and report.** row: cursor + windowclose + mettaur + result + field + the chip rows. frames: 170 cursor, 70 mettaur, 40 others. total/worst: cursor before/after (1/1/170 → 0/0/170); per-frame pixel location of the 3 px residue at k=37 and k=97. region: BG1 backdrop seam at scanline y~143. commit: src/backdrop.rs (+ fn). One line of mechanism (sub_8001C94 at asm00_0.s:3752 is the GFXAnim seam transition that writes a per-element tile on a 60-frame cadence; the 3 px at k=37/97 is the seam tile transition's per-scanline write that needs the canonical per-element path, not the QueueEightWordAlignedGFXTransfer drain F37j tried). One line of unverified (whether the seam transition has additional per-element residues at other y positions that need their own cite, since F37i/F37j both tried BG1-side approaches and neither landed — a per-element port's failure mode is unknown).

**Coordinator:** dispatch second. Worker muse-spark-1.3-contributor (F37i/F37j's child class — per-element BG1 seam cite), verifier GLM-5.3-flash cross-family; ≤$0.20 expected, ≤$0.50 cap; tool budget ≤100; verify_rows on the regression set. Advances **M2** (cursor row at 0/0/170).

---

### F36c. warp integrated 40628: port sub_8001C94's BG1 seam transition directly into src/backdrop.rs  *(NEGATIVE -- 2026-09-15, Premise refuted by measurement, no code change)*

**Result.** Premise refuted by measurement, no code change. warp integrated 40628/11744/30 unchanged; per-frame k=0..23 all 0, k=24..29 = 1917/3837/5757/7677/9696/11744; the diff is ONE new 16-px column per frame from the left edge (k=24 x=0..15 -> k=29 x=0..95), uniform on every scanline y=24..143, each column staying wrong; region split HUD 326 / BG1 40302 / BG3 0 reproduces F36a. Three refutations: (1) not art-step timing -- canon's k=23 glyph step matches ours; (2) not scroll phase (F36b's guess) -- dx,dy +/-32 shift search optimal at (0,0), and not a frame lag (rust k=29 vs canon 27/28/30 = 10390/12151/13792); (3) it is content, not phase -- canon's strip is bright light-blue/white appearing at k=24 and persisting (bright px 1749 -> ~6300) while we show the plain navy backdrop: we never draw it. sub_8001C94 (asm00_0.s:3752-3814, read directly) is the per-element glyph tile assembler + ONE queued QueueEightWordAlignedGFXTransfer (asm00_0.s:3807-3811): it writes char-block art, never the BG1 map, so porting it as gfx_anim_seam_transition cannot move the number. verify_rows on wt/f36c-warp-seam (17b3db1, docs-only diff): warp 0/0/30/8440 PASS, mettaur 0/0/70/41734 PASS. Child worker-hyper glm-5.3-flash:high, 88 turns, $0.134. warp:integrated allowlist entry left in place (no 0/0/30). Unverified: which canon routine performs the per-frame one-column BG1 write during the warp slide-in (canon 154..159), and whether the 326 HUD px falls to it.
**Why.** F36a PARTIAL gave the warp integrated decomposition: 99.2% BG1 backdrop (40302 px, y=24..143), HUD 326 px, BG3/OBJ clean — same class as field integrated 158935/5606 and buster integrated 45810/27225 BG1 phase. F36b BLOCKED tried to port the four canon mechanisms (HUD strip sub_8026BF4, BG1 backdrop sub_8001C94, BG3 window ramp sub_801C4E4, OBJ warp line sub_8009C1C) in one pass and hit tool-budget soft-cap 80 before any code change. The 40302 px is a single mechanism — sub_8001C94 (BGScrollCB_BG1Diagonal3to2Scroll's GFXAnim handler at asm00_0.s:3752) — so a focused port of just that routine into src/backdrop.rs's existing GFXAnim path drops warp integrated to 0/0/30 without the multi-region scope F36b attempted. src/backdrop.rs already references sub_8001C94 in its module docs (`sub_8001C94`, asm00_0.s:3752 — TODO A7 mechanism) and has a per-slot `eGFXAnimStates` countdown that `ProcessGFXAnims` decrements; the seam transition is the per-scanline write `sub_8001C94` makes when the slot hits its step. M2 acceptance is "integrated-row pixel parity"; closing warp integrated is one of the four large integrated remnants.

**Files.** src/backdrop.rs (only the GFXAnim seam transition path, around the STEP_ORDER/STEP_HOLD schedule — TODO A7 module docs already cite sub_8001C94), tools/diffmask.py (only for region confirmation that the BG1 residue is in y=24..143), docs/coverage/warp_integrated.md (notes)

**Do.**
1. Baseline `tools/harness.py --only warp --ui integrated` on HEAD → *report: warp integrated 40628/11744/30 (F36a PARTIAL value); warp isolated 0/0/30 PASS (F11); cursor ≤1/1/170; mettaur 0/0/70; windowclose/result/field 0/0/40; all chip rows 0/0/30.*
2. Run `tools/diffmask.py --row warp --ui integrated` to confirm the 40302 px is concentrated in y=24..143 and to split by per-scanline seam → *report: per-scanline pixel totals at the BG1 seam scanlines; per-frame sequence k=0..29 split by region.*
3. Read sub_8001C94 (asm00_0.s:3752) for the per-slot `Timer` decrement path and the per-step tile copy; cross-reference src/backdrop.rs's STEP_ORDER/STEP_HOLD (around TODO A7 module docs) → *report: file:line for the seam transition routine, the per-step tile copy, the per-scanline write path; the gap between canon's seam transition and our current per-step path.*
4. Port sub_8001C94's seam transition into src/backdrop.rs as `fn gfx_anim_seam_transition(slot: &mut GFXAnimSlot)` with cited file:line → *report: new fn body, cite count, diff at src/backdrop.rs, fitted-constant count delta (HEAD: 19).*
5. Re-run `tools/harness.py --only warp --ui integrated` → *report: warp integrated before/after (40628/11744/30 → 0/0/30); warp isolated stays 0/0/30; cursor stays ≤1/1/170; mettaur 0/0/70; windowclose/result/field 0/0/40; all chip rows 0/0/30.*
6. Re-run `tools/verify_rows.py` from a clean detached checkout → *report: 67-row table — every chip row 0/0/30, mettaur 0/0/70, wave 0/0/90, popup 0/0/80, windowclose 0/0/40, result 0/0/40, field 0/0/40, buster 0/0/28, warp 0/0/30; opening integrated stays 25829/931/40 (F38h PARTIAL value, expected to drop via F38i); warp integrated 0/0/30; buster integrated stays 54672/12977/28; cursor stays ≤1/1/170.*
7. Land with `tools/land.sh` and re-run the free row check on main → *report: 67-row table identical to HEAD except warp integrated 0/0/30; remove `warp:integrated` allowlist entry from tools/allowlist.py.*

**Rules.** Only the named files; the AUDIT-6 allowance for `warp:integrated` is in tools/allowlist.py — it is removed only after verify_rows PASS at 0/0/30; no new harness row; no alignment change; the seam transition ports sub_8001C94 (cite asm00_0.s:3752) — never a fitted per-step tile value or a hardcoded frame count; every new literal gets `// provenance:`; `fitted constants in src/` (HEAD: 19) may not increase; canon never changes; ≤4 capture runs, one at a time inside the 3-slot semaphore; tool budget ≤100 (F36b hit 80 on assembly research only — a focused port is in budget).

**Acceptance.** warp integrated reads 0/0/30 with sub_8001C94 cited at asm00_0.s:3752 in src/backdrop.rs comments; warp isolated stays 0/0/30; cursor ≤1/1/170; mettaur 0/0/70; windowclose/result/field 0/0/40; all chip rows 0/0/30; `warp:integrated` removed from tools/allowlist.py; no allowlist change elsewhere; fitted-constant count unchanged or lower.

**Measure and report.** row: warp (integrated) + warp (isolated) + cursor + windowclose + mettaur + result + field + the chip rows. frames: 30 warp, 170 cursor, 70 mettaur. total/worst: warp integrated before/after (40628/11744/30 → 0/0/30); per-scanline pixel totals at the BG1 seam scanlines (y=24..143); per-frame sequence k=0..29. region: BG1 backdrop seam y=24..143. commit: src/backdrop.rs (+ fn). One line of mechanism (sub_8001C94 at asm00_0.s:3752 is the GFXAnim seam transition that runs once per slot's Timer decrement; the 40302 px warp residue is the per-step tile copy's per-scanline write that needs the canonical per-step timing). One line of unverified (whether the 326 HUD-strip px and any BG3/OBJ residue on warp integrated need separate tickets — F36b's decomposition named them as HUD 326 px and BG3/OBJ clean, so this ticket focuses only on the BG1 phase and a HUD-strip follow-up may be needed if the 326 px persists).

**Coordinator:** dispatch third. Worker muse-spark-1.3-contributor (F36a/F36b's child class — focused GFXAnim seam port), verifier GLM-5.3-flash cross-family; ≤$0.30 expected, ≤$0.60 cap; tool budget ≤100; verify_rows on the full table. Advances **M2** (integrated warp 40628 → 0).

### T7w. Battle end as canon's per-state counts: name the layer of the integrated rows' 16-px band, then retire the fitted RESULTS_DELAY=110  *(NEGATIVE -- 2026-09-15, Premise refuted by measurement)*

**Result.** Premise refuted by measurement; no code change; RESULTS_DELAY kept, no AUDIT-6 key deleted, fitted count 19 unchanged. Baseline HEAD integrated: field 158926/5597/40, warp 40628/11744/30, chip-use 275307/18091/30, buster 54672/12977/28. Step-2 layer four-tuple (full/BG3-only/BG1-only/OBJ-off): field 158926/54556/842344/159187, warp 40628/40628/0/40628, chip-use 275307/44306/443520/250417 -- the 16-px band is on BG3 (window layer), NOT BG1 as F36c's geometric y=24..143 attribution guessed; with only BG1 on, warp reads 0. Band region x=0..15, y=24..143 at its first frame; per-frame band growth warp 1917->11744 (+1920/f), chip-use 2090->12797 (+2090/f), field +176/f (field's slide content already in sync). Step 3 watches: canon sequencer 0x0203ca70 edge 0x08->0x0C at capture 47 with first tick at edge+107 on every row; ours (field) 0x0C from capture 8, tick at entry+132 and already in sync under the fitted 110; warp and chip-use never leave 0x08 -- no edge, no slide, so no canon state count can gate those two rows in this fixture. Spans needed to land the band 132/75/118 vs canon 107 -- inconsistent and non-canon, which is the ticket's own NEGATIVE rule. Steps 4-6 not run by design: a port would regress field (canon span ticks at capture 115 vs aligned 140; T7 measured the 94+16 factoring at field +12 and reverted) and leave warp/chip-use byte-identical. Child worker-hyper 88 turns. Unverified: the dispatch producing the 13-frame hand-off->first-tick gap (asm00_1.s:10758 -> :13329) has no named counter; the field-regression counterfactual is predicted from the entry-time mapping plus T7's +12, not re-measured. NO THIRD TICKET on this objective per the two-in-a-row rule; the next question for a future run is what draws the BG3 one-column-per-frame window band during the warp/chip-use window.
**Why.** Three of the seven failing rows are the zero-enemy integrated variants, all carried by AUDIT-6 in tools/allowlist.py: field integrated 158935/5606/40, warp integrated 40628/11744/30, chip-use integrated 2xxxx/<=28000/30 (step 1 reports the exact pair). F36c measured warp frame by frame: k=0..23 all 0, then k=24..29 = 1917/3837/5757/7677/9696/11744 — one new 16-px column per frame from the left edge, bright light-blue/white, persisting, where ours shows the plain navy backdrop; it refuted art-step timing, scroll phase (dx/dy +/-32 optimal at 0,0) and frame lag, and refuted sub_8001C94 (asm00_0.s:3752-3814 writes char-block art, never the BG1 map). 16 px/frame is exactly results::SLIDE_STEP (src/results.rs:63, sub_802BE36's +2 columns, asm03_0.s:11670), and buster integrated is no longer on the failing list (60 of 67 at 0), so one mechanism — when the results window's show is reached in battle context — gates three rows and three allowlist keys. Ours is a fit: `const RESULTS_DELAY: u16 = 110; // provenance: fitted` (src/battle.rs:1197; countdown :1513/:2007, read at :2851-2880). src/battle.rs:1152-1158 records why the last attempt failed: the 94-count + 16-frame composite gave the same show frame by construction but regressed field +12 on one frame, and moving the teardown/banner to the update after regressed +4. battle_full's sequencer baseline is 273/540 (T7u).

**Files.** src/battle.rs (only Sequencer and the `over` path: RESULTS_DELAY :1197, results_delay :1513/:2007, the show block :2851-2880), src/results.rs (only the driver entry point), src/banner.rs (only if the teardown belongs on the update after), tools/allowlist.py (only deleting AUDIT-6 keys), tools/harness.py (only capture `extra` flags used for the step-2 split and the row notes — no canon_ref/search/descriptor/flag change), docs/coverage/integrated_end.md (new)

**Do.**
1. Baseline `tools/harness.py --only field --ui integrated`, same for warp and chip-use, plus buster → *report: total/worst/frames per row (HEAD expected 158935/5606/40, 40628/11744/30, 2xxxx/<=28000/30) and buster integrated's value.*
2. Split the residue by layer on each row's failing k range, both sides with identical flags, the way `field`'s BG2-only variant does: `--only-bg 3`, then `--only-bg 1`, then `--disable-obj` → *report: per-row per-layer totals; name which layer carries the 16-px band.*
3. `tools/probe.py --watch` the sequencer word dword_203CA70 (// canon: dword_203CA70) on each row's own canon capture for the 12 frames around the band's first frame, and the same on ours → *report: both sides' 0x08->0x0C edge frame, the state at the band's first frame, and the slide's first frame counted from that edge, per row.*
4. Port canon's per-state counts behind Sequencer's arms — the end count, the setup hold, the hand-off, the driver start — cited at sub_800801C (asm00_1.s:10422, table off_8008038), sub_80081A4 (asm00_1.s:10617), sub_802BD60 (asm03_0.s:11549), sub_802BE36 (asm03_0.s:11666); delete RESULTS_DELAY. If step 2 puts the band on BG1, or step 3 shows our edge already equal, report NEGATIVE with those numbers and change no code → *report: the constant gone, cites added, fitted-constant count before/after (HEAD: 19).*
5. Re-run step 1's rows on the same windows → *report: per row total/worst/frames before/after and the band frames' per-frame totals.*
6. Delete each AUDIT-6 key whose row reads 0/0, then `tools/verify_rows.py` from a clean detached checkout → *report: the 67-row table (chip rows 0/0/30, mettaur 0/0/70, cursor <=1/1/170, result/windowclose 0/0/40) and battle_full sequencer vs 273/540.*

**Rules.** Only the named files. No new harness row; no alignment or descriptor change (F38f's descriptor growth cost a cursor regression). Every frame count comes from step 3's reading plus an asm cite — RESULTS_DELAY is deleted, never re-tuned, and a value that only holds at one row's window is a NEGATIVE, not a fix. Every new literal gets `// provenance:` with file:line or the canon symbol. Fitted-constant count (HEAD: 19) must not rise. tools/allowlist.py only loses keys. Canon never changes; <=6 capture runs, one at a time inside the 3-slot semaphore; tool budget <=100 — if the port will not fit, come back with the step 2/3 numbers.

**Acceptance.** field, warp and chip-use integrated each read 0/0/their frame count with negatives non-blind, their three AUDIT-6 keys gone (buster's too if it reads 0); RESULTS_DELAY absent from src/battle.rs and the fitted count <=18; the two sides' 0x08->0x0C edge and slide-start frames equal per row; no regression on cursor/mettaur/result/windowclose/the 43 chip rows; battle_full sequencer <=273/540.

**Measure and report.** rows: field, warp, chip-use, buster (integrated), cursor, mettaur, result, windowclose, the chip rows. frames: 40/30/30/28/170/70/40/40/30. total/worst: before/after per row, the four-tuple of layer totals from step 2, per-frame totals of the band frames. region: the band's x-range at its first frame and the layer it lives on. commit. one line of mechanism (which canon state count owns the show frame). one line of what is unverified.

**Coordinator:** dispatch first — the biggest payoff in the queue (three rows, three allowlist keys, one fitted constant), and steps 1-3 are decisive even as a NEGATIVE. Worker = the run profile's resolved worker (this class: F36c $0.134, T7u $0.395); verifier = the other family, on the step-3 frame readings and the sub_80081A4/sub_802BD60 cites. <=$0.45 expected, <=$0.90 cap, tool budget <=100, verify_rows on the full table plus the allowlist count. Advances **M2** (integrated pixel parity, the sequencer's end states, and the no-allowlist invariant).

---

### T9l. gunner 2850534/38237/130: derive this row's own backdrop seed, then split the residue by layer  *(PARTIAL -- 2026-09-15, LANDED as 424814d)*

**Result.** LANDED as 424814d. GUNNER_ROW's four backdrop seeds are now this row's own, derived from canon's counters at its canon_ref (art_entry 5->11, art_timer 4->2, scroll_xq 424->108, scroll_yq 724->54; f=80 from eBGScrollCBCounters -640/-320, schedule position 81 from eGFXAnimStates[0] entry 15/Timer 7, nx=26/na=28 at ORIGIN 8 + offset 25); the row reads gunner 2850534/38237/130 -> 2105613/38237/130 on BOTH variants with the negative non-blind at 2284867, and the BG1-only layer went 1524416 -> 230400 = exactly six full-screen frames k=0..5, i.e. the backdrop is now pixel-exact for k>=6. Layer four-tuple after: full 2105613 / BG3-only 1426551 / BG1-only 230400 / OBJ-off 1949547, so BG3 (the window layer) now carries most of the residue. Residue named to frame and layer: (1) k=0..5 all layers -- canon fades from bright (OBJ mean 93,77,60,44,28,12) where rust is dark, a fade tail this row starts ~10 frames later than the doc's white-0..70 claim; (2) k=6..75 BG3 ~2047/frame -- the two enemy HP boxes (y0..15, x100..190, two enemies vs mettaur's one) and the bottom-left custom gauge bar (y152, x12..60) where canon's bar reads full from k=0 and GUNNER_ROW's borrowed gauge=0 never fills; (3) k>=77 BG3 plateau 21182/frame -- canon's gauge-full pause auto-opens the chip window on BG3 (slide from canon frame ~156, the frame-165 auto-open at src/battle.rs:1998) so BG3 carries a left-half window (x0..117) rust never draws, with the OBJ ~5.8k/frame plateau downstream of that pause. Ticket step 5 (the aim cursor sub_8112F70 walk) was REFUTED by the split -- no 3 px/frame walk appears in the OBJ diff bboxes -- so it was not ported. Rules: only tools/harness.py + docs changed; no alignment/canon_ref/frames/poke/enemy change; fitted constants 19 unchanged; cursor 1/1/170, mettaur 0/0/70, windowclose 0/0/40, opening 0/0/40, chip-cannon 0/0/40 all unchanged, verify_rows PASS. verifier-hyper CONFIRMED the derivation arithmetic step by step against src/backdrop.rs's STEP_ORDER/STEP_HOLD and against reference/bn6f/data/dat20.s:140-172 (S(11)=48, hold 8, cycle 192), plus the rules audit. Caveats it names: the comment's 'derived from canon's counters' is over-broad by one input -- offset 25 is diff-scored from search=range(0,40) on the OLD seeds, the same convention cursor (237) and windowclose (253) use; the -640/-320 and entry15/Timer7 readings are attested only by docs/worklog/T9l.md (a new capture would be needed to re-read them); LoopAddress 0x0807fba4 is not a label in reference/ (equals off_807FB98+12); eBGScrollCBCounters' visual period is 896 frames, not the 1024 the harness mods by (harmless at f=80, bites past canon_ref ~400); src/battle.rs:1998 vs worklog's :1990-2006 is one imprecise cite. Child worker-hyper glm-5.3-flash:high.
**Why.** The gunner row is the largest residue on the table and it is two rows for one mechanism: ui="both" makes isolated and integrated the same capture, both 2850534/38237/130 (docs/reviews/2026-09-15 scoreboard) — 57% of every compared pixel, worst frame 38237 of 38400, i.e. a whole-screen mismatch, not a sprite detail. T9j ported the per-type routine (ForGunner_8113078, asm32.s:10123-10142) and took 3859001 -> 2850534; T9k's Battle::gunner_ctl/impacts move was NEGATIVE (2850534 unchanged, cursor regressed 1/1/170 -> 59/58/170), so the residue is not the attack logic. The prime suspect is the layer that fills the screen: GUNNER_ROW's four backdrop seeds are FIELD_ROW's — `art_entry=5, art_timer=4, scroll_xq=424, scroll_yq=724` (tools/harness.py:1665-1670), whose own comment says "the backdrop's phase matches `mettaur` at the same battle frame" — while this row's canon side starts at canon_ref=80 and runs 130 frames. The documented derivation (tools/harness.py:1740-1770: nx = ORIGIN+offset-7, na = ORIGIN+offset-5, scroll_xq = (2*(f0+canon_ref) - 2*nx) mod 1024, scroll_yq = (f0+canon_ref - nx) mod 1024, art = (canon position at canon_ref - na + 1) mod 192) has never been run for this row; F34 DERIVED the cursor and windowclose seeds that way and their BG1 went 2214975 -> 2/2 and 877602 -> 0/0.

**Files.** tools/harness.py (only GUNNER_ROW's art_entry/art_timer/scroll_xq/scroll_yq and the gunner Check's Align note), src/gunner.rs (only the timing the split names), src/battle.rs (only the gunner cursor/impact path T9k touched), src/objects.rs (only the Style::Gunner arm), tools/probe.py (peek/read only), docs/coverage/gunner.md (notes)

**Do.**
1. Baseline `tools/harness.py --only gunner` → *report: isolated and integrated total/worst/frames (HEAD 2850534/38237/130) and the per-frame totals k=0..129 with the five worst frames named.*
2. Layer split on that same capture, both sides identical: `--only-bg 1`, `--only-bg 3`, `--disable-obj`, `--disable-bg` → *report: four totals; name which layer carries the 2.85M.*
3. Peek canon's own counters at this row's canon_ref on the gunner capture — eBGScrollCBCounters and eGFXAnimStates[0] (// canon: eBGScrollCBCounters, eGFXAnimStates) — and apply the derivation above → *report: f0, nx, na, the derived scroll_xq/scroll_yq/art_entry/art_timer, and the delta from each borrowed FIELD_ROW value.*
4. Set GUNNER_ROW's four seeds to the derived values, each tagged `provenance: peeked -- canon's own counters at this row's canon_ref`, and re-run the row and the split → *report: gunner before/after and the per-layer totals after.*
5. If a non-backdrop residue remains, port the mechanism the layer names, from the cite for that arm (the aim cursor sub_8112F70 / off_8112F60 dispatch, asm32.s:9958-9973; the 3 px/frame walk), and re-run → *report: gunner before/after, the first differing frame and its region.*
6. `tools/verify_rows.py` from a clean detached checkout → *report: the 67-row table — chip rows 0/0/30, mettaur 0/0/70, cursor <=1/1/170, opening/warp/field/chip-use unchanged — and gunner's negative fixture still non-blind.*

**Rules.** Only the named files. Seeds come from canon's counters through the arithmetic already documented in tools/harness.py, never from sweeping `search` or the offset band for the lowest total — a total that falls without a counter behind it is a fit and is reported as one. No new row; no change to canon_ref/search/frames (T9j's alignment stands), to enemy_kind/enemy_hp, or to any pokes. T9k's ctl/impacts relocation is not re-attempted: step 2 decides whether the residue is even OBJ. Fitted-constant count (HEAD: 19) must not rise; every new literal tagged. Canon never changes; <=5 capture runs, one at a time; tool budget <=100.

**Acceptance.** gunner isolated and integrated read 0/0/130 with a non-blind negative; or the layer table plus the derived seeds land and the remaining residue is named to frame, layer and routine cite. GUNNER_ROW's four seeds carry the peeked provenance; cursor <=1/1/170; mettaur 0/0/70; the 43 chip rows 0/0/30; no allowlist change; fitted constants <=19.

**Measure and report.** rows: gunner (both variants), cursor, mettaur, the chip rows, the four integrated rows. frames: 130 gunner, 170 cursor, 70 mettaur. total/worst: before/after at each step, plus the per-layer four-tuple before/after. region: the layer step 2 names, its y-band and the worst frame's x-range. commit. one line of mechanism. one line of what is unverified.

**Coordinator:** dispatch second — two rows for the price of one measurement. Worker = the run profile's resolved worker (T9j's class ran $0.165-0.988; T9k's NEGATIVE $0.768, and this ticket asks for fewer captures); verifier = the other family, on the derived seeds. <=$0.35 expected, <=$0.70 cap, tool budget <=100. Advances **M5** (the Gunner as a ported per-type routine, this row is its gate) and **M2**'s every-entry-type clause.

---

### F39a. opening integrated 25829/931/40: the four OBJ entries canon does not draw, and the per-sprite PAL_OBJ slot  *(OPEN -- 2026-09-15)*

**Why.** opening integrated is the only failing row with no allowlist cover: 25829/931/40 at the 2026-09-15 scoreboard (commit 1f81767), after F38h's per-enemy panel bytes took it from 72499/2691 and made all three spawn cells equal canon's (5,1)/(5,3)/(6,2) (docs/coverage/opening_integrated.md, F38f/F38h sections). Two residues are already written down in that document's OAM tables: (a) we draw OBJ entries canon does not — pairs at y=84 x=132/140 and y=108 x=172/180 carrying tiles 0 and 8; canon 12 OBJs at k=0 vs our 14, canon 15 at k=32 vs our 19 — and (b) palette slots: canon's per-role OAM palette indices are 2 (HUD/navi) and 6 (enemy) while ours read 2 (HUD), 10 (navi), 14 (enemy), with PAL_OBJ slots 0-5 populated against canon's 0-15 and our pal[0] holding what canon keeps at pal[14]. The allocation sites are src/spr.rs:699-763 (`PaletteVramSingle::try_allocate_shared`, order-dependent). F38i (PARTIAL, kept, not on main) corrected canon's cite to sub_8002818 (sprite.s:254-303) and left a 48-line dead-code stub `fn pal_obj_allocate` on its branch; it also claimed the row reads 0/0 at 8b314eb while the scoreboard reads 25829/931 at 1f81767 — step 1 settles that conflict before any code is written.

**Files.** src/spr.rs (only the PAL_OBJ allocation block :699-763 and the `offset_palettes` decode at :759), src/actor.rs (only the materialize/spawn sprite emission that draws the extra pair), src/objects.rs (only if the pair comes out of a dispatch arm), tools/diffmask.py (measurement only), docs/coverage/opening_integrated.md (notes)

**Do.**
1. Settle the value: `tools/verify_rows.py HEAD opening --expect opening:integrated=F` and `tools/harness.py --only opening --ui integrated` from a clean checkout → *report: both numbers, the commit each was taken at, and which is HEAD's truth.*
2. `tools/probe.py --oam --pal` on both sides at k=0, 20, 32, 39 → *report: OBJ count per side per frame, and per entry x/y/tile/palette index; list the entries with no canon counterpart.*
3. Name which of our paths emits those entries (both pairs sit at one enemy cluster's y and carry tiles 0 and 8) against canon's materialize sub_801641A (asm00_2.s:16101-16136) and object_spawnType1 (asm00_1.s:299-316) → *report: our emitting file:line and canon's cited reason nothing is drawn there at that frame.*
4. Port canon's PAL_OBJ slot choice per sub_8002818 (sprite.s:254-303), and remove F38i's stub if it is on the tree → *report: the diff, the cites, the fitted-constant count (HEAD: 19), and confirmation no dead code is committed.*
5. Re-run the row → *report: opening integrated before/after (target 0/0/40) and the per-frame totals for k=32..39.*
6. `tools/verify_rows.py` from a clean detached checkout → *report: the 67-row table — cursor <=1/1/170, mettaur 0/0/70, chip rows 0/0/30, warp/field/chip-use integrated unchanged — and opening's negative still non-blind.*

**Rules.** Only the named files. No palette index is written per sprite to make a frame match (that is a fitted constant and an AUDIT violation), and no OAM entry is suppressed by a frame-count gate — both must fall out of the ported routines. No new harness row, no descriptor/align/flag change (F38f's descriptor growth cost a cursor regression; FIXTURE_SIZE stays 67 as F38h landed it). Fitted-constant count (HEAD: 19) must not rise. Nothing from a kept branch lands except code this ticket writes and measures. Canon never changes; <=4 capture runs, one at a time inside the 3-slot semaphore; tool budget <=100.

**Acceptance.** opening integrated reads 0/0/40 from a clean detached checkout with its negative non-blind; OBJ counts equal canon's at k=0 and k=32 (12 and 15); the per-role palette indices equal canon's at k=39 (2 HUD/navi, 6 enemy); cursor <=1/1/170; mettaur 0/0/70; the 43 chip rows 0/0/30; warp/field/chip-use integrated unchanged; no allowlist change; no dead code in the commit; fitted constants <=19.

**Measure and report.** rows: opening (integrated and isolated), cursor, mettaur, result, windowclose, the chip rows. frames: 40 opening, 170 cursor, 70 mettaur, 40 result/windowclose, 30 chips. total/worst: before/after per row; the per-frame totals at k=32..39; OBJ counts per side at k=0/20/32/39. region: the x=203..214 cluster and the two spurious pairs. commit. one line of mechanism. one line of what is unverified.

**Coordinator:** dispatch third — one row, but the attribution is already tabulated in docs/coverage/opening_integrated.md, so the measurement cost is prepaid; if step 1 shows the row is already 0/0 it closes for a few cents. Worker = the run profile's resolved worker (F38h's class $0.580; F38i's $1.084 with a longer Do list than this); verifier = the other family, on the OAM and palette readings. <=$0.30 expected, <=$0.60 cap, tool budget <=100. Advances **M2** (integrated opening parity) and **M8**'s per-object palette/OAM order.

