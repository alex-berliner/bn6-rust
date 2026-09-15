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

### T7u. battle_full sequencer: port sub_801E754's banner-idle check to replace SEQ04_FRAMES=60 in src/battle.rs  *(OPEN -- 2026-09-15)*

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

### F36b. warp integrated ~40628: per-region decomposition, then port the canon mechanism for each non-zero region  *(OPEN -- 2026-09-15)*

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

