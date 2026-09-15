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

### T7r. battle_full fixture: scripted L input so self.seq.state traverses {SEQ_20, SEQ_24, SEQ_00, SEQ_04} *(OPEN -- 2026-09-15)*

**Why.** T7q PARTIAL (f80b72f) added the seq.state gate in `Actor::update` / `t1_player_entry` — early-returns `Update::Nothing` when `seq.state in {SEQ_20, SEQ_24, SEQ_00, SEQ_04}` with cites playerObject_update_80EA484 (asm31.s:107147) + sub_8009158 dispatcher (asm00_1.s:12760) + sub_8008452/sub_8008492/sub_800840C/sub_8008064 (asm00_1.s:10441-10514). Counts did NOT move (k=179 group stayed at mm_state_action/mm_anim/mm_timer 101/86/302) because self.seq.state stays at SEQ_08 for all k=0..542 in battle_full — T7g NEGATIVE (2026-09-15) named the root cause: canon's battle_full includes scripted L@40 input that fills the gauge and opens the chip window at frame 42; our battle_full fixture has flags=0x19 with no L input, gauge stays 0, the chip-window-open transition at src/battle.rs:2615-2655 never fires, and self.seq.state never enters the gated set. Without the fixture driving the chip window open, the seq.state gate from T7q PARTIAL is inert and the k=179 group (the largest remaining M2 divergence: 101 + 86 + 302 = 489 divergent frames) stays stuck. M2 acceptance is "battle_full sequencer first divergence none" — fixing the sequencer traversal is the lowest-cost path to the k=179 group's drop.

**Files.** tools/harness.py (battle_full fixture: scripted L@N or chip-fire that fills the gauge, only the segment between battle-init and the chip-window-open branch), tools/states.py (only if the recipe needs the chip-window-open state's setup), tools/trace.py (only if a sequencer-field watch must widen), docs/coverage/battle_full.md (notes), tools/probe.py (only the per-frame sequencer watch if a gated frame needs visualizing)

**Do.**
1. Baseline `tools/trace.py record/diff --align row:battle_full` on HEAD → *report: self.seq.state values for k=0..540 (all SEQ_08 expected, per T7q PARTIAL); k=179 group counts 101/86/302 on mm_state_action/mm_anim/mm_timer; cursor 1/1/170 unchanged.*
2. Read the battle_full fixture in tools/harness.py; identify the segment between battle-init (k=0) and the chip-window-open branch (canon frame 42, k=31 scenario frame); pick the scripted-L mechanism — either a one-shot `--poke-at frame:0x02036xxx:val` for the AIData Held bit or a scripted chip-fire that grows the gauge (cite `sub_800A244` → `sub_800A8F8` → `TestBattleFlag_0x40`, asm00_2.s:???); cross-reference T7g's negative for the gauge=0 mechanism → *report the cited scripted-input mechanism (the named file:line), the proposed frame number for the poke, and the gauge_tick value before/after.*
3. Apply the scripted-input fix in tools/harness.py only (no src/ change); the fix is fixture scripting — never a hardwired SEQ_20 trigger or a fitted state value in src/battle.rs → *report the new scripted-input line(s) with the `// provenance:` tag and the cited file:line.*
4. Re-run the diff with the new capture → *report: self.seq.state sequence over k=0..210 (target: SEQ_08 until k~30, SEQ_20 at k~31..32, SEQ_24 at k~33..132, SEQ_00 at k~133..135, SEQ_04 at k~136..195, SEQ_08 at k~206+); k=179 group counts after (target mm_state_action<101, mm_anim<86, mm_timer<302).*
5. Re-run `tools/verify_rows.py` from a clean detached checkout → *report: 67-row table — every chip row 0/0/30, mettaur 0/0/70, wave 0/0/90, popup 0/0/80, windowclose 0/0/40, result 0/0/40, field 0/0/40, buster 0/0/28, warp 0/0/30, chip-use integrated unchanged; cursor stays ≤1/1/170 (no regression from the scripted-L side effect).*
6. Land with `tools/land.sh` and re-run the free row check on main → *report: 67-row table identical to HEAD except battle_full sequencer counts drop.*

**Rules.** Only the named files; no src/ change; no allowlist change; no new harness row; no alignment change; the fix is fixture scripting (gauge fill → chip window open) — never a fitted state value in src/battle.rs and never a hardwired SEQ_20 trigger; every new literal gets a `// provenance:` tag with the cite; `fitted constants in src/` (HEAD: 19) may not increase; canon never changes; ≤4 capture runs, one at a time inside the 3-slot semaphore.

**Acceptance.** self.seq.state traverses SEQ_20 by k~31 and reaches SEQ_08 by k~207 on battle_full with the cited fixture scripting; mm_state_action/mm_anim/mm_timer counts drop below 101/86/302 at k=179 (T7q PARTIAL's gate fires); cursor stays ≤1/1/170; mettaur 0/0/70; every isolated pixel row reads 0 as it does today; no allowlist change; fitted-constant count unchanged or lower.

**Measure and report.** row: battle_full + cursor + windowclose + mettaur + result + field + wave + popup + the chip rows. frames: 540 battle_full, 170 cursor, 70 mettaur. total: k=179 group counts before/after; self.seq.state sequence over 540 frames; pixel totals per row. worst: any pixel row that moves. region: for the trace, the sequencer state field k=0..540 both sides; for any pixel regression, the diffmask frame and region. commit: tools/harness.py (battle_full fixture scripted-input segment). One line of mechanism (scripted L input or chip-fire fills the gauge at canon frame 42, fires the chip-window-open transition sub_800A244 → sub_800A8F8 → TestBattleFlag_0x40, carries self.seq.state through SEQ_20→SEQ_24→SEQ_00→SEQ_04→SEQ_08 per the sub_800801C/0x8008038 table). One line of what is unverified (whether the k=179 group drops to 0 or stops at a smaller residual — the next ticket decides whether a downstream gate is also needed).

**Coordinator:** dispatch first. Worker muse-spark-1.3-contributor (T7q's child class — sequencer traversal), verifier GLM-5.3-flash cross-family; ≤$0.15 expected, ≤$0.40 cap; verify_rows on the regression set plus the fitted-constant count. Advances **M2** (sequencer coverage; the k=179 group is the largest remaining divergence inside battle_full at 489 divergent frames across 540).

---

### F38e. opening integrated 72499: fix the diagonal spawn cells (src/battle.rs:1907-1908) and the materialize y offset (src/actor.rs:528)  *(BLOCKED -- 2026-09-15, F38e worker found two rule conflicts that prevent landing: [1] spawn-cell fix needs per-enemy panel data per s)*

**Result.** F38e worker found two rule conflicts that prevent landing: (1) spawn-cell fix needs per-enemy panel data per spawnEnemy_80073E2 asm00_1.s:8695, but src/fixture.rs (the only natural location) is outside 'Only the named files' and a hardcoded triple violates 'never a fitted panel triple'; (2) sub_801641A asm00_2.s:16101-16136 does NOT do per-step y motion — it only decrements Timer/Timer2 and calls mosaic+alpha setters. The 24-px position delta for enemy 3 is fully explained by bug 1's wrong panel assignment (panel row 3 vs row 2). Per-enemy panels at ROM 0x080b5354 confirmed as 0x15/0x35/0x26 = (5,1)/(5,3)/(6,2). Baseline opening integrated 72499/2691/40 unchanged. Fitted constants 19 unchanged. No commits landed. Tree clean on wt/f38e at d3d7439. Worker muse-spark-1.3-contributor was the assumed model in the ticket but actual model was MiniMax-M3 per run meta; 86 turns, /bin/bash.29 cost (T7r per-cap; F38e meta not yet written but same role+model). Awaiting user direction: (a) permit src/fixture.rs to add per-enemy panel bytes, OR (b) confirm bug 2 should be de-scoped (no y motion in asm).
**Why.** F38 PARTIAL (07ad4e3, notes only), F38c PARTIAL (c7667a5, 112 insertions, docs only), and F38d PARTIAL (3dafe69, 68 insertions, docs only) all decomposed opening integrated 72499/2691/40 and named the bugs without landing a fix. F38d named two concrete defects with cites: (1) the diagonal spawn at src/battle.rs:1907-1908 places rust enemies at panels (4,1)/(5,2)/(6,3) vs canon's triangle (5,1)/(5,3)/(6,2) — cites spawnEnemy_80073E2 (asm00_1.s:8695); (2) the materialize y offset (rust 88-104 vs canon 112-128 for enemy 3) traces to src/actor.rs:528 because the Appearing state lacks sub_801641A's per-step y motion — cite sub_801641A (asm00_2.s:16101) + APPEAR_STEPS*APPEAR_TICKS_PER_STEP=32 (src/actor.rs:257 matches asm00_2.s:16106-16136). Per-frame attribution (F38c): mid y=30..130 jumps to 2306 at k=33+ (second-enemy-cluster materialize), bot y=130..160 jumps to 384 at k=32+; PAL_OBJ 0-15 vs 0-5 allocation lives in PaletteVramSingle::try_allocate_shared call order at src/spr.rs:701-761. F38e lands the two named bugs (spawn cells + materialize y) — the next-largest pieces after F38d's measurement pass. M2 acceptance is "integrated-row pixel parity"; closing opening integrated removes one of the four large integrated remnants.

**Files.** src/battle.rs (only the spawn-cell loop at :1907-1908 — the diagonal placement), src/actor.rs (only the Appearing state's per-step y motion at :528, with sub_801641A's per-step arithmetic), src/spr.rs (only if the PAL_OBJ call order must be reordered), src/objects.rs (only if the materialize animation spawn frame needs adjustment), tools/probe.py (only if a per-frame OAM watch is needed to localize the spawn-cell fix), docs/coverage/opening_integrated.md (notes)

**Do.**
1. Baseline `tools/harness.py --only opening --ui integrated` on HEAD → *report opening integrated 72499/2691/40 with per-region pixel counts (top 0, mid ~2306 at k=33+, bot ~384 at k=32+, OAM layer-local totals by palette band 0-15), plus the per-enemy spawn-cell positions on both sides (canon (5,1)/(5,3)/(6,2), ours (4,1)/(5,2)/(6,3)).*
2. OAM + position dump both sides at k=10, k=20, k=33, k=39 with `tools/probe.py --oam --pal --pos`; cross-reference panels (5,1)/(5,3)/(6,2) vs (4,1)/(5,2)/(6,3) against spawnEnemy_80073E2 (asm00_1.s:8695) and the materialize y per-step against sub_801641A (asm00_2.s:16101) → *report the per-enemy x/y at the materialized frames on both sides, the per-step y delta from sub_801641A, and the spawned-from-frame for each enemy.*
3. Fix the spawn-cell triangle in src/battle.rs:1907-1908 — change the diagonal placement from (4,1)/(5,2)/(6,3) to (5,1)/(5,3)/(6,2) per spawnEnemy_80073E2; add per-step y motion to the Appearing state in src/actor.rs:528 per sub_801641A's per-step arithmetic (start_y=112, step_y=16 over APPEAR_STEPS=2 × APPEAR_TICKS_PER_STEP=16 frames); cite both files in the same commit → *report the new (x, y, panel) per-enemy on rust, the per-step y trace, and the cites.*
4. Re-run `tools/harness.py --only opening --ui integrated` and `tools/verify_rows.py` from a clean detached checkout → *report opening integrated before/after (target 72499/2691/40 → 0/0/40 with the two named bugs fixed; if not 0, decompose the residual by region and frame, name the next mechanism), cursor stays ≤1/1/170, mettaur 0/0/70, windowclose 0/0/40, result 0/0/40, field 0/0/40, all chip rows 0/0/30, opening isolated 0/0/40 (untouched by this fix).*
5. Land with `tools/land.sh` and re-run the free row check on main → *report: 67-row table identical to HEAD except opening integrated.*

**Rules.** Only the named files; no allowlist change; no new harness row; no alignment change; the fix is a port of canon's spawnEnemy_80073E2 + sub_801641A — never a fitted (x, y) pair or a fitted panel triple; every new literal gets a `// provenance:` tag with the cite; `fitted constants in src/` (HEAD: 19) may not increase; canon never changes; ≤4 capture runs, one at a time inside the 3-slot semaphore.

**Acceptance.** opening integrated reads 0/0/40 with the spawn-cell port cited at spawnEnemy_80073E2 (asm00_1.s:8695) and the materialize y port cited at sub_801641A (asm00_2.s:16101); opening isolated stays 0/0/40; cursor ≤1/1/170; mettaur 0/0/70; windowclose/result/field 0/0/40; all chip rows 0/0/30 (or current); no allowlist change; fitted-constant count unchanged or lower.

**Measure and report.** row: opening + cursor + windowclose + mettaur + result + field + the chip rows. frames: 40 opening, 170 cursor, 70 mettaur. total/worst: opening integrated before/after (72499/2691 → 0/0); per-region pixel counts top/mid/bot; per-enemy spawn position on both sides. region: k=10..39 per-frame y trace on the Appearing state; OAM OBJ layer-local totals; the spawn-cell fan-out at k=20..33. commit: src/battle.rs (spawn cells) + src/actor.rs (materialize y). One line of mechanism (canon spawns the enemy triangle (5,1)/(5,3)/(6,2) from spawnEnemy_80073E2 and materialize steps enemy.y by sub_801641A over APPEAR_STEPS×APPEAR_TICKS_PER_STEP=32 frames). One line of what is unverified (the residual if non-zero — the PAL_OBJ slot-allocation order in src/spr.rs:701-761 is a separate mechanism).

**Coordinator:** dispatch second. Worker muse-spark-1.3-contributor (F38d's child class — spawn cells + materialize y), verifier GLM-5.3-flash cross-family; ≤$0.25 expected, ≤$0.50 cap; verify_rows on the full table. Advances **M2**.

---

### T9j. Gunner as data: port the per-type routine into src/gunner.rs and align the harness row on the Gunner's first attack event *(OPEN -- 2026-09-15)*

**Why.** T9h PARTIAL (a97f07f) landed the cite + GunnerEntry struct + ForGunner_8113078 handler-table (CurActions 0x00..0x0B, asm32.s:10123-10142) + per-state timer arms (SHOTS=3, SHOT_GAP=10, RECOVER_FRAMES=24, asm32.s:9958-10102) + src/objects.rs Style::Gunner dispatch arm from byte_80182C4[3*enemy_idx] (enemy_idx 0x85 → ACTOR_TYPE_VIRUS 0x17 → ForGunner_8113078) + tools/harness.py GUNNER_ROW + symlinked assets/Gunner/gunner.bin + docs/coverage/gunner.md. T9i PARTIAL (019a79d) landed the capture race fix (serial flag + variant_label key in tools/harness.py so rust+canon serialize under 3-slot semaphore when serial=True). After T9i the gunner row reads 3859001/38400/130 with negative 3838543 not blind — root cause is alignment mismatch, not the port: canon frame 0 is state-loading uniform white and rust origin 8 is already battle content, so canon_ref=0 is wrong, and canon's first non-uniform frame is 71 (T9i "alignment is a separate issue"). The port itself is still missing: src/objects.rs's Style::Gunner dispatch arm is registered but the per-type routine in src/gunner.rs is only the struct/cite scaffolding, not a port — the Gunner entity still falls through to the Mettaur routine (current bug). Art provenance is solved: tools/spr_export.py at comp_825BFC4 reproduces assets/gunner.bin byte-for-byte (T9b). M5 acceptance is "per entry: scenario, port, trace, pixels"; closing the Gunner moves M5 from 1/187 to 2/187.

**Files.** src/gunner.rs (the per-type routine ported from ForGunner_8113078, asm32.s:10123-10142, with cited per-state timer arms), src/objects.rs (only the dispatch slot that routes ForGunner into Actor::update, distinct from F38e's spawn cells), src/ai.rs (only if the Gunner's think/act hooks differ from the Mettaur's), tools/harness.py (only the gunner row's alignment — set canon_ref to the Gunner's first attack event frame and rust_base to its matched origin), tools/states.py (only if the scenario needs adjustment for the alignment), assets/Gunner/ (already byte-for-byte from comp_825BFC4 per T9b, no change), docs/coverage/gunner.md (notes)

**Do.**
1. Baseline on HEAD → *report: mettaur 0/0/70 unchanged; gunner row exists (`python3 tools/harness.py --list 2>&1 | grep -c gunner`) and reads 3859001/38400/130 after T9i; T9i regression set (cursor 1/1/170, mettaur 0/0/70, result 0/0/40, wave 0/0/90, popup 0/0/80) all PASS; gunner row is non-zero because the per-type routine falls through to the Mettaur.*
2. Read ForGunner_8113078 (asm32.s:10123-10142) and the per-state handler table; identify the 12 CurActions (0x00..0x0B), the SHOTS=3 / SHOT_GAP=10 / RECOVER_FRAMES=24 timer arms (asm32.s:9958-10102), and the per-state fields oAIAttackVars_Unk_00/Unk_01/Unk_10/Unk_18 from the GunnerEntry struct T9h landed; cite every literal to file:line → *report the per-state routine structure, the timer-arms table cited, and the cite count.*
3. Port the per-type routine into src/gunner.rs as a `fn gunner_update(...)` that mirrors MettaurEntry's structure (state advance + per-tick work + return Update); cite each field to asm32.s:10123-10142 with `// provenance:` tags; verify the dispatch arm in src/objects.rs routes `ForGunner` into `gunner_update` not `mettaur_update` → *report the ported routine's size, the cite count, the dispatch-table entry written, and the dispatch verified by a per-frame actor-type trace.*
4. Realign the gunner row in tools/harness.py: canon_ref = Gunner's first attack event frame (e.g. canon frame 71 from T9i's named "first non-uniform frame", or the first frame Gunner CurAction transitions to 0x03 per ForGunner's CurAction 0x03 = ATTACK chain); rust_base = the matched origin on our side → *report the new canon_ref, rust_base, and the per-frame alignment evidence (both sides' attack-event frames).*
5. Re-run `tools/harness.py --only gunner` and `tools/verify_rows.py` from a clean detached checkout → *report gunner before/after (target 3859001/38400/130 → 0/0/130), the full table identical to HEAD (mettaur 0/0/70, cursor ≤1/1/170, all chip rows 0/0/30, opening 0/0/40, windowclose 0/0/40, buster 0/0/28, chip-use 0/0/30, warp 0/0/30).*
6. Land with `tools/land.sh` and re-run the free row check on main → *report: 67-row table identical to HEAD except gunner 0/0/130.*

**Rules.** Only the named files; no allowlist change; the Gunner port is a port of canon's per-type routine at asm32.s:10123-10142 — never a hand-written re-creation; every new literal gets a `// provenance:` tag with the cite; `fitted constants in src/` (HEAD: 19) may not increase; canon never changes; ≤4 capture runs, one at a time inside the 3-slot semaphore.

**Acceptance.** gunner harness row reads 0/0/130 at the aligned scenario's frame count with the per-type routine cited at ForGunner_8113078 (asm32.s:10123-10142) + byte_80182C4 (asm00_2.s:19965-19974); mettaur stays 0/0/70; cursor stays ≤1/1/170; every other isolated row 0/0; no allowlist change; fitted-constant count unchanged or lower; the Gunner's art is byte-for-byte from assets/Gunner/gunner.bin (already extracted per T9b).

**Measure and report.** row: gunner (new) + mettaur + cursor + the chip rows + opening + windowclose + buster + chip-use + warp. frames: 130 gunner, 70 mettaur, 170 cursor. total/worst: gunner before/after (3859001/38400 → 0/0); per-frame pixel counts. region: per-OAM entries (gunner entities vs Mettaur fixture); per-frame diff regions if non-zero. commit: src/gunner.rs (the per-type routine) + src/objects.rs (the dispatch slot) + tools/harness.py (the alignment). One line of mechanism (ForGunner_8113078's 12 CurActions with cited timer arms mirror MettaurEntry's structure, dispatched at byte_80182C4[3*0x85]; alignment fixed by canon_ref=Gunner first attack event frame 71). One line of what is unverified (the remaining 185 viruses — each family follows the same port shape but with its own identity row, art slot, and routine).

**Coordinator:** dispatch third. Worker muse-spark-1.3-contributor (T9i's child class — Gunner per-type routine + alignment), verifier GLM-5.3-flash cross-family; ≤$0.25 expected, ≤$0.50 cap; verify_rows on the full table. Advances **M5** (viruses; closes the second per-type port after Mettaur).

