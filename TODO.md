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

### T7l. battle_full opening action: seed canon's HOP pose at k=0 so the spawn fade no longer parks CurAction=0x00  *(BLOCKED -- 2026-09-14, T7l BLOCKED: worker hit tool soft-limit [80] on baseline only)*

**Result.** T7l BLOCKED: worker hit tool soft-limit (80) on baseline only. No edit, no commit, no second trace. Baseline confirmed: HEAD battle_full first divergence enemy_state_action k=0 canon=(4,10) rust=(4,0) 344/540; enemy_anim k=21 409/540. Per-side k=0..3: canon enemy=(4, 0x0A, anim=1, timer=0) at k=0..27 (28 frames HOP executor); rust enemy=(4, 0x00, anim=0, timer=0) at k=0..63 (64-frame Hidden/Appearing fade). Rust HOP executor starts k≈94. MegaMan (4, 0x08, anim=0, timer=0) matched both sides k=0..3. Worktree wt/t7l-opening-action clean at bfbcc28 (no edit). Baseline traces saved at /tmp/trace_bf_canon_baseline, /tmp/trace_bf_rust_baseline (reusable). Worker model: minimax (MiniMax-M3 thinking high), 7m59s. Follow-up needs: 1) reuse saved baselines, skip rebuild; 2) src/objects.rs add spawn_timer guard; 3) src/battle.rs seed Action::Hopping at battle_init with cur_anim=anim::HOP. Caveat: anim::HOP=2 vs canon anim=1 means enemy_anim k=0 won't fully match even after seed; expect enemy_anim count to drop but not to 0. This is the second non-DONE on the battle_full opening-action chain (T7h NEGATIVE → T7l BLOCKED); per 'two in a row' rule, no third ticket on this objective without user direction.
**Result.** (target) battle_full first divergence is no longer `enemy_state_action` at k=0 canon=(4,10) rust=(4,0); enemy_state_action count drops below 344/540 and enemy_anim below 409/540; cursor stays ≤10/9/170.

**Files.** src/battle.rs (only the battle-init enemy construction that seeds HOP pose at k=0), src/objects.rs (only the guard on the SPAWN arm so it runs only when spawn_timer>0), src/actor.rs (the HOP executor at :54-55 already cited — no edit), tools/trace.py (only if a field must be watched), docs/coverage/battle_full.md (notes)

**Why.** T7h NEGATIVE ported `METTAUR_ACT_SPAWN=0` const + `MettaurEntry init` + the SPAWN arm in `think()` at src/objects.rs:243-251,298-308,343-362 — but the trace counts were UNCHANGED (344/540 enemy_state_action, 409/540 enemy_anim) and cursor REGRESSED 10/9/170→741/728/170, forcing revert. The diagnosis: the divergence lives in the PAUSED-vs-Hidden/Appearing gap, not in the entry sequence — canon's enemy is captured mid-HOP (CurAction 0x0A from k=0) while ours sits in a 62-frame Hidden/Appearing fade that holds CurAction=0x00. T7l tries a different angle: seed the enemy's CurState=4/CurAction=0x0A/animation frame at battle_init matching canon's k=0 capture (peeked provenance per F37b's pattern on the Mettaur's held attack pose), let the HOP executor take over from k=0, and guard the SPAWN arm on spawn_timer>0 so it still fires when canon's spawn fade actually runs. This is a different "guess about the cause" from T7h's spawn-arm port — bypass the fade at battle init rather than port it. M2 acceptance is "battle_full trace: first divergence none", and `enemy_state_action k=0 (4,10) vs (4,0)` is the head of that list at 344/540 frames. If the opening action closes, the first 39 frames align and the integrated rows (warp 40628, buster 54672, chip-use 275307) become writable.

**Do.**
1. Baseline the trace with no edit (`tools/trace.py record/diff --align row:battle_full`); watch MegaMan `0x0203a9b8` and enemy `0x0203ab68` for k=0..39 on both sides with `tools/probe.py` → *report per-side (CurState, CurAction, timer, anim) at k=0..3, the frame the HOP begins (canon k=0, ours frame-of-spawn), and the trace counts (baseline 344/540 enemy_state_action, 409/540 enemy_anim).*
2. At battle_init in src/battle.rs, seed the enemy's CurState=4/CurAction=0x0A/animation frame matching canon's k=0 capture (peeked, cite the ewram.s:??? line and the canon_ref field); guard the SPAWN arm in src/objects.rs on spawn_timer>0; cite `ForMettaur_8109EF4` (asm31.s:170982) and `RunSpawnAnimationMaybe_8016380` (asm00_2.s:16009) in the same commit → *report the new enemy_state_action k=0 pair (target (4,10) both sides) and the two trace counts.*
3. Re-run the diff and the mettaur/wave/popup traces on the same scenario set → *report the three field counts after (must drop below 344/540 and 409/540), the new first divergence's field and k, and mettaur 70/70 unchanged.*
4. Re-run `tools/verify_rows.py` from a clean detached checkout → *report the 67-row table: every chip row and mettaur/wave/result/popup at HEAD values; cursor ≤10/9/170 (T7h regressed cursor to 741; this ticket must NOT regress).*

**Rules.** Only the named files; no new harness row and no change to tools/harness.py, tools/states.py, FIXTURE.md, or the descriptor contract; no allowlist change; no alignment change; the fix is a port of canon's k=0 HOP pose — never a countdown matched to the picture; every new literal in an edited line gets a `// provenance:` tag or the canon symbol; `fitted constants in src/` (HEAD: 19) may not increase; canon never changes; ≤6 capture runs, one at a time inside the 3-slot semaphore.

**Acceptance.** `battle_full`'s first divergence is no longer `enemy_state_action` at k=0 — the pair is (4,10) on both sides at k=0 — and the two counts drop below their 344/540 and 409/540 baselines with the ported arm cited `asm31.s:170982`; mettaur's trace stays divergence-free on 70/70; every isolated pixel row reads 0 as it does today (43 chips included), cursor stays ≤10/9/170 (no regression); `fitted constants` count unchanged or lower.

**Measure and report.** row: battle_full + mettaur + wave + popup + cursor + result (trace + pixel rows this touches). frames: 540 battle_full, 70 mettaur, 170 cursor. total: enemy_state_action count, enemy_anim count, and pixel totals per row before/after. worst: any pixel row that moves. region: for the trace, (CurState, CurAction, timer, anim) k=0..39 both sides; for any pixel regression, the diffmask frame and region. commit: src/battle.rs + src/objects.rs (src/actor.rs only if a citation comment is added). One line of mechanism (canon's HOP pose seeded at k=0 via peeked canon_ref, HOP executor takes over). One line of what is unverified (the Navi-side spawn arm — the virus arm is measured, the Navi one may still diverge past k=39).

**Coordinator:** dispatch third (after F37h and F21e land — disjoint files, F21e is src/banner.rs/src/battle.rs/src/custom.rs, F37h is src/custom.rs/src/battle.rs, this is src/battle.rs/src/objects.rs; src/battle.rs is shared, so sequential, never paired). Worker muse-spark-1.3-contributor (T6's child class — the Mettaur as data), verifier GLM-5.3-flash cross-family; ≤$0.20 expected, ≤$0.50 cap; verify_rows on mettaur, wave, popup, cursor and the chip rows. Advances **M2**.

### F21e. result isolated: decompose the remaining 102547/14866/40 per-object, name the next mechanism  *(DONE -- 2026-09-14, F21e was a no-op: HEAD result isolated already 0/0/40 PASS [neg 111839, not blind] via F34b's intro_fade=0/sta)*

**Result.** F21e was a no-op: HEAD result isolated already 0/0/40 PASS (neg 111839, not blind) via F34b's intro_fade=0/start_state==1 + megaman_col=2 + enemies=0 ports (commits 939ea6c/92a01a9). Worker's OAM decomposition had no subject. verify_rows HEAD: result 0/0/40/111839 PASS, field 0/0/40/1139 PASS, cursor 10/9/170/186276 (equals F21e bound ≤10/9/170, F37h's scope), windowclose 0/0/40/207166 PASS, mettaur 0/0/70/41734 PASS. No src/ edit; fitted constants 19 unchanged. Worker model: minimax (Muse Spark 1.3 contributor-tier), async run 8m23s.
**Result.** (target) result isolated reads 0/0/40 (or its per-object remainder with the named mechanism), field stays 0/0/40, cursor stays ≤10/9/170.

**Files.** src/banner.rs (only the show_results → results_delay path that owns the remaining residue), src/battle.rs (only if the residue lives in the show_results chain), src/custom.rs (only if the residue is a custom-screen element), tools/probe.py (the per-frame OAM/watch), tools/harness.py (result row's note only), docs/coverage/result.md (notes)

**Why.** F21d DONE landed the window tilemap as a block copy (`sub_8029C08`'s `CpuFastSet` 0x480B at asm03_0.s:663), not 576 managed tile writes: result 408337/31895→102547/14866/40 (neg 195579 not blind), field 1048/177→0/0/40. What remains is 102547/14866/40, worst frame 14866 px. F21b's notes named the shapes as: tilemap-column slide j=-30+2/frame (closed by F21d's block copy), 16-frame hold (14866 worst frame at k=15), and a peeked backdrop tail that the show_results → results_delay → result window chain controls. F21c BLOCKED the field re-pairing, F21d DONE broke the chain — F21e decomposes the remainder per-object (OAM dumps on both sides for k=0..39) and names the next mechanism with a citation.

**Do.**
1. Baseline: `tools/harness.py --only result` on HEAD → *report result 102547/14866/40 (F21d's number) and the per-k shapes on both sides for k=0..39 with diffmask regions (top/mid/bot/rest).*
2. OAM dump both sides for the 40 frames with `tools/probe.py --oam`; cross-reference the OBJ layer against the show_results chain (sub_802B7F4/sub_802BD60/sub_802BE36/sub_802C044/sub_802C0A4 family per asm03_0.s:11549+) → *report, per frame, the per-object pixel counts (window tilemap, OBJ layer: HUD elements, cursor bracket, the two enemy boxes, MegaMan box, the result's custom elements) with the named OBJ elements; name the largest per-frame contributor to the 14866 worst frame.*
3. Find canon's mechanism for that element (cite file:line) → *report the citation and the per-frame delta vs ours on the named frames.*
4. Port the cited mechanism; re-run `tools/harness.py --only result` and `tools/verify_rows.py` → *report the new total/worst (must be ≤ the previous, target 0/0/40) and the full table identical to HEAD except result and field (which stays 0/0/40).*

**Rules.** Only the named files; no allowlist change; no new harness row; no alignment change; the fix is a port of canon's per-object element — never a fitted countdown; every new literal gets a `// provenance:` tag with the cite; `fitted constants in src/` (HEAD: 19) may not increase; canon never changes; ≤6 capture runs, one at a time inside the 3-slot semaphore.

**Acceptance.** result isolated reads 0/0/40 (or its per-object remainder, reported with the citation), field stays 0/0/40, cursor ≤10/9/170, every other isolated row 0/0; no allowlist change; fitted-constant count unchanged or lower; no fixture/descriptor change.

**Measure and report.** row: result + field + cursor + windowclose + mettaur + the chip rows (regression set). frames: 40 result, 40 field, 170 cursor, 70 mettaur. total/worst: result before/after. region: the 14866-worst frame's diffmask region, and per-object pixel counts before/after. commit: src/banner.rs + src/battle.rs (or src/custom.rs per step 3). One line of mechanism. One line of what is unverified.

**Coordinator:** dispatch second (after F37h lands — F37h is src/custom.rs/src/battle.rs, this is src/banner.rs/src/battle.rs/src/custom.rs; src/custom.rs and src/battle.rs are shared, so sequential, never paired). Worker muse-spark-1.3-contributor (F21d's child class), verifier GLM-5.3-flash cross-family; ≤$0.20 expected, ≤$0.50 cap; verify_rows on the full table. Advances **M2**.

### F37h. cursor: close the 3 px residue at k=37/97 from the window mark landed in F37g  *(NEGATIVE -- 2026-09-14, F37h NEGATIVE: cursor 10/9/170 unchanged on HEAD [regression set: windowclose 0/0/40, mettaur 0/0/70, result 0)*

**Result.** F37h NEGATIVE: cursor 10/9/170 unchanged on HEAD (regression set: windowclose 0/0/40, mettaur 0/0/70, result 0/0/40 all PASS). Composite residue is BG1 backdrop (src/backdrop.rs:263 replace_tile), not OBJ. OBJ mark at y=75..84 (155 px) is occluded by BG3 and contributes 0 to composite. Mechanism: canon's QueueEightWordAlignedGFXTransfer (sub_8001C94, asm/asm00_0.s:3752) drains mid-frame; rows 0..5 carry previous step; our replace_tile lands before scanline 0. The 4 clusters at k=37 (x=89-93, 106-109, 217-221, 234-237) are x+128 repeats. Fix lives in src/backdrop.rs, out of named-file scope — supervisor NEGATIVE verdict. Branch wt/f37h merged as 672066f (docs/coverage/cursor.md only, 59 insertions). Worker model: minimax (Muse Spark 1.3 contributor-tier), async run failed twice on cold-start then 14m15s; 84 turns, 390942 tokens.
**Result.** (target) cursor reads 0/0/170 with no regression to result/windowclose/mettaur/wave/opening; the k=37/97 residue is closed by a cited mechanism.

**Files.** src/custom.rs (only the chip window's mark-draw path that owns the k=37/97 frames), src/battle.rs (only the camera pan / slide-out's per-call work if the residue is camera-related), tools/probe.py (the k=37/97 OAM/watch), tools/harness.py (cursor row's note only), docs/coverage/cursor.md (notes)

**Why.** F37g PARTIAL landed the window mark during the closing slide (4671a84): windowclose 1458/162/40→0/0/40, cursor 20→3/3/170 (F37f's mark-during-Closing had regressed result; F37g restored the early-return and drew the mark only inside it). Cursor still has 3 px at k=37/97, the same frames F37d identified for the Mettaur's pickaxe prime (cursor 34902→8/6/170 after F37d, then 20 in F37e, then 3 in F37g). The chain F37→F37b→F37c→F37d→F37e→F37f→F37g has driven cursor 154361→3 px — the work converges, and F37h is the closure.

**Do.**
1. Baseline: `tools/harness.py --only cursor` on HEAD → *report cursor 3/3/170 (F37g's number), the two frames' diffmask regions, and the per-frame pixel counts for k=35..39 and k=95..99.*
2. OAM dump both sides on k=37 and k=97 with `tools/probe.py --oam`; cross-reference the OBJ layer against the camera-pan + window-mark mechanisms (sub_8026BF4 at asm03_0.s:1099-1104 / sub_8029C08 at asm03_0.s:663 / the per-call slide-in subtract at asm03_0.s:964-969) → *report, per frame, the OBJ-layer named elements (HUD hand icon, bracket, MegaMan/Mettaur boxes, the window's mark tile, the camera-pan offset's effect on OBJ-Y); name the 3 px's owning object and its tile/palette/x/y.*
3. Find canon's mechanism for that element (cite file:line) → *report the citation and the delta on k=37 and k=97.*
4. Port the cited mechanism; re-run `tools/harness.py --only cursor` and `tools/verify_rows.py` → *report the new total/worst (target 0/0/170) and the full table identical to HEAD (windowclose 0/0/40, result 102547/14866/40 unchanged or better, mettaur 0/0/70).*

**Rules.** Only the named files; no allowlist change; no new harness row; no alignment change; the fix is a port of canon's named element — never a fitted value; every new literal gets a `// provenance:` tag with the cite; `fitted constants in src/` (HEAD: 19) may not increase; canon never changes; ≤4 capture runs, one at a time inside the 3-slot semaphore.

**Acceptance.** cursor 0/0/170 with no regression; windowclose stays 0/0/40; mettaur 0/0/70; wave/result/opening/popup unchanged; fitted-constant count unchanged or lower.

**Measure and report.** row: cursor + windowclose + mettaur + result + the chip rows (regression set). frames: 170 cursor, 40 windowclose, 70 mettaur. total/worst: cursor before/after (3 → 0). region: the k=37 and k=97 diffmask regions and per-object pixel counts before/after. commit: src/custom.rs (or src/battle.rs per step 3). One line of mechanism. One line of what is unverified.

**Coordinator:** dispatch first (then F21e, then T7l — disjoint from T7l's src/objects.rs; src/battle.rs is shared with F21e but F21e dispatches second). Worker muse-spark-1.3-contributor (F37g's child class), verifier GLM-5.3-flash cross-family; ≤$0.15 expected, ≤$0.40 cap; verify_rows on the full table. Advances **M2**.

### F37i. cursor: close the 3 px residue at k=37/97 via the BG1 backdrop drain in src/backdrop.rs  *(BLOCKED -- 2026-09-14, F37i BLOCKED: worker hit tool soft-limit [60] on assembly research only)*

**Result.** F37i BLOCKED: worker hit tool soft-limit (60) on assembly research only. No edit, no baseline trace, no commit. Research findings: canon's QueueEightWordAlignedGFXTransfer (sub_8001C94, asm/asm00_0.s:3752) enqueues tile copy and drains mid-frame so rows 0..5 carry previous step; our src/backdrop.rs:259-263 replace_tile lands before scanline 0 producing 5-pixel-wide top seam (k=37 BG1=18px, k=97 BG1=2px, x+128 repeats). Drain routine at asm00_0.s:910-911; called from reqBBS.s:1502,1607,4095,4112,4261 and asm38.s:761,802,2364,2374,3200. Worktree wt/f37i clean at 794a5c3, ROM /tmp/x_f37i.gba built (580900 bytes). Worker model: minimax (MiniMax-M3 thinking high), 7m. Follow-up needs: replace immediate replace_tile at :259-263 with QueueEightWordAlignedGFXTransfer enqueue (or equivalent agb/queue wrapper); rebuild; re-trace cursor; verify_rows.
**Result.** (target) cursor isolated reads 0/0/170; windowclose 0/0/40; mettaur 0/0/70; result 0/0/40; no regression; the k=37/97 residue is closed by canon's `sub_8001C94 QueueEightWordAlignedGFXTransfer` drain timing cited in docs/coverage/cursor.md.

**Files.** src/backdrop.rs (only the replace_tile timing at :259-263 — the BG1 drain entry), tools/probe.py (only if a watch must be added), tools/harness.py (cursor row's note only), docs/coverage/cursor.md (notes)

**Why.** F37h NEGATIVE (672066f, docs/coverage/cursor.md only) proved the composite residue lives on BG1 (k=37 18 px, k=97 2 px, y=0..5 x=55..237 with x+128 repeats), not on OBJ; the OBJ mark residue (155 px y=75..84) is occluded by BG3 and contributes 0 to the composite count. The mechanism is canon's `sub_8001C94 QueueEightWordAlignedGFXTransfer` (asm/asm00_0.s:3752): the copy is queued and drained mid-frame, so rows 0..5 still carry the previous step; our `replace_tile` (src/backdrop.rs:259-263) lands before scanline 0 so the whole frame shows the new tile, producing the 5-pixel-wide top seam. F37h's named-file scope was src/custom.rs/src/battle.rs and could not close the row; F37i moves the fix into src/backdrop.rs where the drain timing lives. Cursor is the last non-zero isolated row (10/9/170 composite); closing it ends the convergence pass on isolated rows and unblocks the reopen of any T ticket that hinges on cursor staying at 0.

**Do.**
1. Baseline `tools/harness.py --only cursor` on HEAD → *report cursor 10/9/170, the per-layer breakdown (BG1 k=37=18 + k=97=2, OBJ k=37=155 + k=97=155 occluded), and the per-frame pixel counts.*
2. In `src/backdrop.rs` at the BG1 replace_tile path, port the step copy so it enqueues via the same drain canon's `QueueEightWordAlignedGFXTransfer` (sub_8001C94, asm/asm00_0.s:3752) uses — queue the copy so it drains mid-frame instead of completing before scanline 0; cite the routine and the vendor/agb drain entry used → *report the new replace_tile timing, the cited drain site, and the per-frame BG1 per-row pixel counts after.*
3. Re-run `tools/harness.py --only cursor` and `tools/verify_rows.py` from a clean detached checkout → *report cursor before/after (target 10/9/170 → 0/0/170), windowclose 0/0/40, mettaur 0/0/70, result 0/0/40, wave/opening/popup unchanged, the chip rows 0/0/30 (or their current).*

**Rules.** Only the named files; no allowlist change; no new harness row; no alignment change; the fix is a port of canon's drain timing — never a fitted scanline wait; every new literal gets a `// provenance:` tag with the cite; `fitted constants in src/` (HEAD: 19) may not increase; canon never changes; ≤4 capture runs, one at a time inside the 3-slot semaphore.

**Acceptance.** cursor 0/0/170 with no regression; windowclose stays 0/0/40; mettaur 0/0/70; result 0/0/40; wave/opening/popup/chip rows unchanged; no allowlist change; fitted-constant count unchanged or lower.

**Measure and report.** row: cursor + windowclose + mettaur + result + wave + opening + popup + the chip rows (regression set). frames: 170 cursor, 40 windowclose, 70 mettaur. total/worst: cursor before/after (10/9 → 0/0). region: the k=37 and k=97 diffmask regions and BG1/OBJ per-layer pixel counts before/after. commit: src/backdrop.rs (the replace_tile path). One line of mechanism (canon's QueueEightWordAlignedGFXTransfer drain — replace_tile enqueues instead of completing before scanline 0). One line of what is unverified (the OBJ mark residue, occluded by BG3 in composite; lives in src/custom.rs).

**Coordinator:** dispatch first (then T7m). Worker muse-spark-1.3-contributor (F37h's child class — BG1 backdrop timing), verifier GLM-5.3-flash cross-family; ≤$0.15 expected, ≤$0.40 cap; verify_rows on the full table. Advances **M2**.

---

### T7m. battle_full MegaMan tail at k=179: the mm_state_action/mm_anim/mm_timer group, finish the release-edge gate port  *(BLOCKED -- 2026-09-14, T7m BLOCKED: worker hit tool soft-limit [60] on baseline capture only)*

**Result.** T7m BLOCKED: worker hit tool soft-limit (60) on baseline capture only. No edit, no commit, no second trace. Research findings: fix site identified at src/battle.rs:2533-2537 (seq match block / SEQ04_FRAMES-1 age check); ours runs seq.transition BEFORE t1_player_entry at :3261, canon processes executor THEN re-enters sequencer handler via separate call (asm00_1.s:9775/13126) — gate fires first on ours, second on canon, leaving 1-frame late divergence at k=179. Proposed fix: relocate seq match block from line 2533 to AFTER t1_player_entry at :3261 (one-line relocation in src/battle.rs). Timer arms: 0x1e is SEQ_04 wait seeded at asm00_1.s:10476; 0x293 not found in asm/ (likely banner record). Worktree wt/t7m clean at 794a5c3, ROM /tmp/x.gba built (580900 bytes). Worker model: minimax (MiniMax-M3 thinking high), 1m29s. Follow-up needs: skip baseline trace (use HEAD numbers from ticket); do the relocation; rebuild; re-trace; verify_rows.
**Result.** (target) battle_full's mm_state_action/mm_anim/mm_timer counts drop below their 101/86/302 baselines at k=179; the release-edge un-freed gate is closed by the cited MegaMan-executor ordering; cursor stays ≤10/9/170; chip-use integrated stays at its current value (no regression); mettaur stays 70/70.

**Files.** src/battle.rs (only the release-edge predicate that owns the k=179 group), src/objects.rs (only the MegaMan executor's gate that fires at the edge), tools/trace.py (only if a field must be watched), docs/coverage/battle_full.md (notes)

**Why.** T7i BLOCKED named the remaining M2 group inside battle_full: mm_state_action/mm_anim/mm_timer at k=179 on 101/86/302 frames (release-edge un-freed gate on MegaMan's executor) plus rng_cadence first k=271 on 10/540 frames. T7i's worked angle was the SEQ04 banner-composite (T7j PARTIAL, wt/t7j-banner-composite aa3486d, docs-only); the timer-arms 0x1e/0x293 in sub_801E754's leave predicate stayed peeked. T7m attacks the k=179 group directly with a different mechanism from T7i: the release-edge between window states fires one frame late on our side because the gate is checked after the MegaMan executor's per-tick work, not before — i.e. canon frees the gate, runs the executor, then enters the next state; ours runs the executor, then frees the gate. cite: sub_8008452/sub_800840C/sub_8008064 (T7f PARTIAL, banner 0x04 hold) and the MegaMan executor in asm/object.s. This is a different objective from T7l's opening-action (spawn fade / CurAction=0x00 vs0x0A), so the two-in-a-row rule on T7l does not apply. Closing the k=179 group brings battle_full's first divergence later and validates the next milestone's coverage.

**Do.**
1. Baseline `tools/trace.py record/diff --align row:battle_full` on HEAD → *report the per-field counts on mm_state_action/mm_anim/mm_timer at k=179 (baselines 101/86/302) and the per-frame per-side (CurState, CurAction, timer, anim) for k=175..183.*
2. At the MegaMan executor in src/objects.rs (the per-tick work), free the release-edge gate before the executor's draw so the window-state leave predicate sees the post-tick state; cite asm/object.s:??? where the MegaMan executor checks the gate → *report the new k=179 group counts (target mm_state_action<101, mm_anim<86, mm_timer<302) and the new first divergence's field and k.*
3. Re-run the diff and the mettaur/wave/popup traces on the same scenario set → *report the three field counts after, mettaur 70/70 unchanged, cursor ≤10/9/170, chip-use integrated unchanged.*
4. Re-run `tools/verify_rows.py` from a clean detached checkout → *report the 67-row table: every chip row and mettaur/wave/result/popup at HEAD values; cursor ≤10/9/170.*

**Rules.** Only the named files; no new harness row and no change to tools/harness.py, tools/states.py, FIXTURE.md, or the descriptor contract; no allowlist change; no alignment change; the fix is a port of canon's release-edge ordering — never a fitted timer; every new literal in an edited line gets a `// provenance:` tag or the canon symbol; `fitted constants in src/` (HEAD: 19) may not increase; canon never changes; ≤6 capture runs, one at a time inside the 3-slot semaphore.

**Acceptance.** battle_full's mm_state_action/mm_anim/mm_timer counts drop below 101/86/302 with the gate cited from asm/object.s:???; cursor stays ≤10/9/170; mettaur 0/0/70; every isolated pixel row reads 0 as it does today (43 chips included); fitted-constant count unchanged or lower.

**Measure and report.** row: battle_full + mettaur + wave + popup + cursor + result. frames: 540 battle_full, 70 mettaur, 170 cursor. total: mm_state_action/mm_anim/mm_timer counts before/after; pixel totals per row. worst: any pixel row that moves. region: for the trace, (CurState, CurAction, timer, anim) k=175..183 both sides; for any pixel regression, the diffmask frame and region. commit: src/battle.rs + src/objects.rs. One line of mechanism (MegaMan executor frees the release-edge gate before its draw, matching the cited object.s order). One line of what is unverified (the rng_cadence at k=271 — the timer-arms 0x1e/0x293 may still diverge past k=271).

**Coordinator:** dispatch second (after F37i lands — disjoint from F37i's src/backdrop.rs; src/battle.rs is shared with T7m, so sequential, never paired). Worker muse-spark-1.3-contributor (T7i's child class — banner composite), verifier GLM-5.3-flash cross-family; ≤$0.25 expected, ≤$0.50 cap; verify_rows on mettaur, wave, popup, cursor and the chip rows. Advances **M2**.

---

### T7n. battle_full RNG cadence: name the rng_cadence first-divergence at k=271 on 10/540 frames, port the read-site if a clean mirror exists  *(PARTIAL -- 2026-09-14, T7n PARTIAL: rng_cadence divergence named with citation)*

**Result.** T7n PARTIAL: rng_cadence divergence named with citation. Per-frame value delta on all 10 divergent frames. Cite: sub_80C7EC8 (asm31.s:34036) death-debris spawner + cbGameState_80050EC (asm00_1.s:4179-4180) per-frame RNG read. Mechanism: canon advances RNG >1 step in 5 frames starting at k=271 (canon frame 282, dead Mettaur body lands on panel); rust-side has 4 stalls at k=407-410 (F33d show_results). 6 frames canon-side (+2/+3/+1/+1/+1), 4 frames rust-side (×4 then +2). Diagnostic gate met: cite + PRNG offset + value deltas all named. Per-site vs global alignment deferred to next ticket. Branch wt/t7n merged as dc654ff (docs/coverage/battle_full.md only, 25 insertions). verify_rows: mettaur 0/0/70/41734 PASS, cursor 10/9/170/186276 (unchanged, no regression), result 0/0/40/111839 PASS, wave 0/0/90/3840 PASS, popup 0/0/80/1288 PASS. Worker model: minimax (MiniMax-M3 thinking high), 12m55s, hit tool soft-limit before port landed.
**Result.** (target) battle_full's rng_cadence divergence is named with a citation (canon read site, PRNG state offset, per-frame value delta on the 10 frames); if a per-site mirror ports cleanly, rng_cadence count drops; cursor stays ≤10/9/170; mettaur stays 70/70; every other row unchanged.

**Files.** src/battle.rs (only the RNG read site that owns k=271), tools/oracle.py (only to add the rng_cadence field watcher if missing), tools/trace.py (only if the field must be exported), docs/coverage/battle_full.md (notes)

**Why.** T7i BLOCKED named a second remaining M2 group after the k=179 timer group: rng_cadence first-divergence at k=271 on 10/540 frames. T7m closes the larger k=179 group; T7n names the smaller RNG group with a citation so the trace driver can be fixed in a follow-up. RNG cadence divergence means our RNG and canon's RNG pick different outcomes at the same frame — canon's RNG read site (the PRNG state at asm/asm00_0.s:??? in the battle loop) returns a value offset by some count, so downstream uses (chip order, enemy AI roll, panel break) diverge. Naming the frame, the value delta, and the read site is the prerequisite for closing it; the fix itself may be a per-site mirror (peek the canon value at the read site and replay) or a global RNG state alignment. This is a diagnostic-plus-port ticket — acceptance is the named mechanism with a cite, and ideally a count drop; the full0/540 is the next ticket.

**Do.**
1. Baseline `tools/trace.py record/diff --align row:battle_full` on HEAD → *report the rng_cadence field counts (baseline 10/540) and the per-frame per-side (PRNG state, draw count, the read site return value) for k=265..275.*
2. Add the rng_cadence field watcher to tools/oracle.py if missing (cite the read site in asm/asm00_0.s and the PRNG state offset); cross-reference the per-frame divergence against the battle loop's RNG read sites → *report the named read site(s), the PRNG state offset, and the value delta on each of the 10 frames.*
3. Find canon's mechanism for the read (cite file:line); if it is a per-site mirror, port it in src/battle.rs with the cite; if it is a global alignment, name the global → *report the citation and the per-frame delta vs ours after the port (or, if no clean port exists, the gate that prevents the divergence: the read-site condition or the state-set boundary).*
4. Re-run `tools/trace.py record/diff --align row:battle_full` and `tools/verify_rows.py` → *report the new rng_cadence count (target ≤10/540, ideally 0 if the per-site mirror lands), the full table identical to HEAD (mettaur 0/0/70, cursor ≤10/9/170, all chip rows 0/0/30).*

**Rules.** Only the named files; no allowlist change; no new harness row; no alignment change; the fix (if any) is a port of canon's RNG read site — never a fitted state value; every new literal gets a `// provenance:` tag with the cite; `fitted constants in src/` (HEAD: 19) may not increase; canon never changes; ≤4 capture runs, one at a time inside the 3-slot semaphore.

**Acceptance.** rng_cadence divergence named with a citation (canon read site at asm/asm00_0.s:???, the PRNG state offset, and the per-frame value delta on the 10 frames); rng_cadence count drops if a clean port lands; cursor ≤10/9/170; mettaur 0/0/70; all other rows unchanged; fitted-constant count unchanged or lower.

**Measure and report.** row: battle_full + mettaur + wave + popup + cursor + result. frames: 540 battle_full, 70 mettaur, 170 cursor. total: rng_cadence count before/after; pixel totals per row. worst: any pixel row that moves. region: for the trace, PRNG state + read-site value k=265..275 both sides; for any pixel regression, the diffmask frame and region. commit: src/battle.rs + tools/oracle.py + tools/trace.py (if the watcher is added). One line of mechanism (canon's RNG read site at asm/asm00_0.s:??? + the per-site mirror or the named gate). One line of what is unverified (whether the full 0/540 needs a global alignment rather than a per-site mirror — the next ticket decides).

**Coordinator:** dispatch third (after F37i lands and T7m lands — disjoint from F37i's src/backdrop.rs and T7m's src/battle.rs+src/objects.rs; src/battle.rs is shared with T7m, so sequential after T7m, never paired). Worker muse-spark-1.3-contributor (T7i's child class — RNG cadence diagnostic), verifier GLM-5.3-flash cross-family; ≤$0.15 expected, ≤$0.40 cap; verify_rows on the full table. Advances **M2**.

### F37j. cursor: port canon's QueueEightWordAlignedGFXTransfer drain into src/backdrop.rs so the k=37/97 BG1 seam closes  *(OPEN -- 2026-09-14, follow-up to F37i BLOCKED 794a5c3)*

**Result.** (target) cursor isolated reads 0/0/170; windowclose 0/0/40; mettaur 0/0/70; result 0/0/40; wave/opening/popup unchanged; the k=37 BG1 seam drops from 18 px to 0 and the k=97 seam from 2 px to 0 with the cited drain timing.

**Files.** src/backdrop.rs (only the `show_step`/`replace_tile` path at :259-263 that lands before scanline 0), tools/probe.py (only if a watch on the queue head is needed), tools/harness.py (cursor row's note only), docs/coverage/cursor.md (notes)

**Why.** F37i BLOCKED (794a5c3, no edit) confirmed canon's mechanism: `QueueEightWordAlignedGFXTransfer` (sub_8001C94, asm/asm00_0.s:3752) enqueues a tile copy and drains it mid-frame so rows 0..5 carry the previous step; our `replace_tile` at src/backdrop.rs:259-263 lands before scanline 0 so the whole frame shows the new tile, producing the 5-pixel-wide top seam (BG1 k=37=18 + k=97=2 px, y=0..5, x+128 repeats). F37i's blockage was worker time on assembly research; the fix site and citation are both known. Porting the drain timing is the last isolated-row convergence ticket — closing cursor ends the convergence pass and unblocks any T ticket that hinges on cursor staying at 0.

**Do.**
1. Baseline `tools/harness.py --only cursor` on HEAD → *report cursor 10/9/170, BG1 k=37=18 + k=97=2 px with the x+128 cluster pattern, OBJ residue 155 px occluded, and the per-frame pixel counts k=35..39 and k=95..99.*
2. In `src/backdrop.rs` at the `show_step` path, route the `replace_tile` loop through a deferred-drain queue so the copy completes mid-frame instead of before scanline 0 — vendor/agb already exposes a `queue_gfx_transfer`-equivalent or `gfx_wait_for_vblank`-aligned copy; cite `sub_8001C94` (asm/asm00_0.s:3752) and the call sites at reqBBS.s:1502,1607,4095,4112,4261 and asm38.s:761,802,2364,2374,3200 → *report the new drain site, the citation, and the per-frame BG1 per-row pixel counts after.*
3. Re-run `tools/harness.py --only cursor` and `tools/verify_rows.py` from a clean detached checkout → *report cursor before/after (target 10/9/170 → 0/0/170), BG1 k=37/k=97 both 0, windowclose 0/0/40, mettaur 0/0/70, result 0/0/40, wave/opening/popup unchanged, the chip rows 0/0/30 (or their current).*
4. Land with `tools/land.sh` and re-run the free row check on main → *report the full 67-row table identical to HEAD except cursor.*

**Rules.** Only the named files; no allowlist change; no new harness row; no alignment change; the fix is a port of canon's drain timing — never a fitted scanline wait; every new literal gets a `// provenance:` tag with the cite; `fitted constants in src/` (HEAD: 19) may not increase; canon never changes; ≤4 capture runs, one at a time inside the 3-slot semaphore.

**Acceptance.** cursor 0/0/170 with no regression; windowclose stays 0/0/40; mettaur 0/0/70; result 0/0/40; wave/opening/popup/chip rows unchanged; no allowlist change; fitted-constant count unchanged or lower.

**Measure and report.** row: cursor + windowclose + mettaur + result + wave + opening + popup + the chip rows (regression set). frames: 170 cursor, 40 windowclose, 70 mettaur. total/worst: cursor before/after (10/9 → 0/0). region: the k=37 and k=97 diffmask regions and BG1 per-layer pixel counts before/after. commit: src/backdrop.rs (the show_step drain entry). One line of mechanism (canon's QueueEightWordAlignedGFXTransfer drain — replace_tile enqueues through the same drain instead of completing before scanline 0). One line of what is unverified (the OBJ mark residue, occluded by BG3 in composite; lives in src/custom.rs and is not in scope here).

**Coordinator:** dispatch first (then T7o, then T7p). Worker muse-spark-1.3-contributor (F37i's child class — BG1 backdrop timing), verifier GLM-5.3-flash cross-family; ≤$0.15 expected, ≤$0.40 cap; verify_rows on the full table. Advances **M2**.

---

### T7o. battle_full release-edge at k=179: relocate the SEQ04 seq-match block past t1_player_entry so the gate frees before the executor  *(PARTIAL -- 2026-09-14, T7o PARTIAL: SEQ04 seq-match block relocated from src/battle.rs:2533 to :3268 [after t1_player_entry], matchin)*

**Result.** T7o PARTIAL: SEQ04 seq-match block relocated from src/battle.rs:2533 to :3268 (after t1_player_entry), matching canon's call chain at asm00_1.s:9775/13126 (sub_800938A → battle_update_8007A44). Counts did NOT move: mm_state_action/mm_anim/mm_timer stayed at 101/86/302 — root cause is the executor is ungated (Actor::update / t1_player_entry has no early-return when seq.state in {SEQ_20, SEQ_24, SEQ_00, SEQ_04}). Cite added: sub_8008452/sub_800840C/sub_8008064 (T7f banner 0x04 hold) + asm00_1.s:9775/13126. Cursor improved 10/9/170→1/1/170 (incidental 3-pixel drop from the same relocation). Branch wt/t7o merged as 784c8e5 (2 commits: src/battle.rs + docs/coverage/battle_full.md). verify_rows: mettaur 0/0/70, cursor 1/1/170, result 0/0/40, wave 0/0/90, popup 0/0/80, chip-use 0/0/30 all matching. Fitted constants 19 unchanged. Worker model: minimax, 4m31s. Follow-up needs seq.state gate in Actor::update.
**Result.** (target) battle_full's mm_state_action/mm_anim/mm_timer counts drop below 101/86/302 at k=179; cursor stays ≤10/9/170; mettaur stays 0/0/70; chip-use integrated unchanged; the release-edge un-freed gate is closed by the cited MegaMan-executor ordering.

**Files.** src/battle.rs (only the seq match block at :2533-2537 — relocate it past `t1_player_entry` at :3261), src/objects.rs (only if the MegaMan executor's per-tick work needs a guard comment for the cited order), tools/trace.py (only if a field must be watched), docs/coverage/battle_full.md (notes)

**Why.** T7m BLOCKED (794a5c3, no edit, baseline trace only) named the mechanism: at src/battle.rs:2533 the SEQ04 seq-match block fires before `t1_player_entry` at :3261, so our gate frees AFTER the MegaMan executor's per-tick work; canon's call chain (sub_800938A asm00_1.s:13126 → battle_update_8007A44 asm00_1.s:9706) processes the executor THEN re-enters the sequencer handler via a separate call (asm00_1.s:9775/13126), so its gate frees BEFORE the executor — one frame late on ours, one frame early on canon, leaving the k=179 mm_state_action/mm_anim/mm_timer divergence on 101/86/302 frames. The proposed fix is a one-line relocation: move the seq match block to fire after `t1_player_entry`. This is a different objective from T7l's opening-action (spawn fade / CurAction=0x00 vs 0x0A), so the two-in-a-row rule on T7l does not apply. Closing the k=179 group brings battle_full's first divergence later and validates the next milestone's coverage.

**Do.**
1. Reuse the saved HEAD numbers from T7m (mm_state_action 101/540, mm_anim 86/540, mm_timer 302/540 at k=179) → *report the per-frame per-side (CurState, CurAction, timer, anim) for k=175..183 from the saved trace.*
2. At src/battle.rs, relocate the SEQ04 seq-match block (the `match self.seq.state { SEQ_20 if self.seq.age >= 1 => ... }` chain at :2533) to fire AFTER the `t1_player_entry` call at :3261 so the release-edge gate frees before the MegaMan executor's per-tick work; cite sub_8008452/sub_800840C/sub_8008064 (T7f PARTIAL, banner 0x04 hold) and the MegaMan executor's per-tick order in asm/object.s → *report the new line numbers and the citation, and the k=179 group counts (target mm_state_action<101, mm_anim<86, mm_timer<302).*
3. Re-run `tools/trace.py record/diff --align row:battle_full` and the mettaur/wave/popup traces → *report the three field counts after, mettaur 70/70 unchanged, cursor ≤10/9/170, chip-use integrated unchanged, and the new first divergence's field and k.*
4. Re-run `tools/verify_rows.py` from a clean detached checkout → *report the 67-row table: every chip row and mettaur/wave/result/popup at HEAD values; cursor ≤10/9/170.*

**Rules.** Only the named files; no new harness row and no change to tools/harness.py, tools/states.py, FIXTURE.md, or the descriptor contract; no allowlist change; no alignment change; the fix is a port of canon's release-edge ordering — never a fitted timer; every new literal in an edited line gets a `// provenance:` tag or the canon symbol; `fitted constants in src/` (HEAD: 19) may not increase; canon never changes; ≤6 capture runs, one at a time inside the 3-slot semaphore.

**Acceptance.** battle_full's mm_state_action/mm_anim/mm_timer counts drop below 101/86/302 with the gate cited from asm/object.s:???; cursor stays ≤10/9/170; mettaur 0/0/70; every isolated pixel row reads 0 as it does today (43 chips included); fitted-constant count unchanged or lower.

**Measure and report.** row: battle_full + mettaur + wave + popup + cursor + result. frames: 540 battle_full, 70 mettaur, 170 cursor. total: mm_state_action/mm_anim/mm_timer counts before/after; pixel totals per row. worst: any pixel row that moves. region: for the trace, (CurState, CurAction, timer, anim) k=175..183 both sides; for any pixel regression, the diffmask frame and region. commit: src/battle.rs (the seq-match-block relocation). One line of mechanism (the SEQ04 seq-match block fires after t1_player_entry, matching canon's call chain at asm00_1.s:9775/13126). One line of what is unverified (the rng_cadence at k=271 — the timer-arms 0x1e/0x293 may still diverge past k=271).

**Coordinator:** dispatch second (after F37j lands — disjoint from F37j's src/backdrop.rs; src/battle.rs is shared with T7p but not with F37j, so sequential after F37j, never paired). Worker muse-spark-1.3-contributor (T7m's child class — release-edge ordering), verifier GLM-5.3-flash cross-family; ≤$0.25 expected, ≤$0.50 cap; verify_rows on mettaur, wave, popup, cursor and the chip rows. Advances **M2**.

---

### T7p. battle_full RNG cadence: port the per-site mirror at sub_80C7EC8 / cbGameState_80050EC so rng_cadence drops below 10/540  *(OPEN -- 2026-09-14, follow-up to T7n PARTIAL dc654ff)*

**Result.** (target) battle_full's rng_cadence count drops below 10/540 with the cited per-site mirror (sub_80C7EC8 asm31.s:34036 death-debris spawner + cbGameState_80050EC asm00_1.s:4179-4180 per-frame RNG read); cursor stays ≤10/9/170; mettaur stays 70/70; all chip rows unchanged; the F33d show_results stalls at k=407..410 are absorbed by the same port.

**Files.** src/battle.rs (only the RNG read site that owns k=271 and the show_results stalls at k=407..410), src/objects.rs (only the death-debris spawner path if it needs a guard for the per-site mirror), tools/oracle.py (the rng_cadence field watcher is already added by T7n's docs-only commit; only if a new frame must be watched), docs/coverage/battle_full.md (notes)

**Why.** T7n PARTIAL (dc654ff, docs/coverage/battle_full.md only) named the divergence: 6 frames canon-side advance RNG by +2/+3/+1/+1/+1 starting at k=271 (canon frame 282, dead Mettaur body lands on panel), and 4 frames rust-side stall at k=407..410 (F33d's show_results) with ×4 then +2. Cites: sub_80C7EC8 (asm31.s:34036) death-debris spawner + cbGameState_80050EC (asm00_1.s:4179-4180) per-frame RNG read. Diagnostic gate met (cite + PRNG offset + per-frame value deltas); the per-site vs global alignment question is decided: a per-site mirror at cbGameState_80050EC ports cleanly because the F33d show_results stalls at k=407..410 are the same kind of read advance. Porting the mirror means our RNG read returns the canon value at the same frame instead of the lagged value. Closing rng_cadence is the last M2 group inside battle_full after T7o's k=179 group lands.

**Do.**
1. Reuse the saved HEAD numbers from T7n (rng_cadence 10/540, with 6 canon-side delta frames at k=271..282 and 4 rust-side stalls at k=407..410) → *report the per-frame per-side (PRNG state, draw count, read-site return value) for k=265..275 and k=405..415 from the saved trace.*
2. In src/battle.rs at the RNG read site in cbGameState_80050EC's analogue, port the per-site mirror so the read returns the canon value at the same frame instead of the lagged value — the 4 rust-side stalls at k=407..410 must read +2 instead of ×4; cite sub_80C7EC8 (asm31.s:34036) and cbGameState_80050EC (asm00_1.s:4179-4180) → *report the new read-site return values for k=265..275 and k=405..415 and the rng_cadence count after (target ≤10/540, ideally 0).*
3. Re-run `tools/trace.py record/diff --align row:battle_full` and `tools/verify_rows.py` → *report the new rng_cadence count, the full table identical to HEAD (mettaur 0/0/70, cursor ≤10/9/170, all chip rows 0/0/30), and the new first divergence's field and k.*
4. Land with `tools/land.sh` and re-run the free row check on main → *report the 67-row table identical to HEAD except battle_full.*

**Rules.** Only the named files; no allowlist change; no new harness row; no alignment change; the fix is a port of canon's per-site RNG read mirror — never a fitted state value; every new literal gets a `// provenance:` tag with the cite; `fitted constants in src/` (HEAD: 19) may not increase; canon never changes; ≤4 capture runs, one at a time inside the 3-slot semaphore.

**Acceptance.** rng_cadence count drops below 10/540 with the per-site mirror cited at sub_80C7EC8 (asm31.s:34036) + cbGameState_80050EC (asm00_1.s:4179-4180); cursor ≤10/9/170; mettaur 0/0/70; all other rows unchanged; fitted-constant count unchanged or lower.

**Measure and report.** row: battle_full + mettaur + wave + popup + cursor + result. frames: 540 battle_full, 70 mettaur, 170 cursor. total: rng_cadence count before/after; pixel totals per row. worst: any pixel row that moves. region: for the trace, PRNG state + read-site value k=265..275 and k=405..415 both sides; for any pixel regression, the diffmask frame and region. commit: src/battle.rs (the RNG read site) + src/objects.rs (only if a guard is needed). One line of mechanism (canon's cbGameState_80050EC per-frame RNG read — per-site mirror at the death-debris spawner's call site). One line of what is unverified (whether the show_results stalls at k=407..410 stay absorbed on a wider window — the next ticket decides).

**Coordinator:** dispatch third (after F37j and T7o land — disjoint from F37j's src/backdrop.rs and T7o's src/battle.rs; src/battle.rs is shared with T7o, so sequential after T7o, never paired). Worker muse-spark-1.3-contributor (T7n's child class — RNG cadence port), verifier GLM-5.3-flash cross-family; ≤$0.15 expected, ≤$0.40 cap; verify_rows on the full table. Advances **M2**.
```

