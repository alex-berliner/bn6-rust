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
### F17. `mettaur` isolated: enemy_anim k=61, the Mettaur's own animation  *(DONE -- 2026-09-13, mettaur 19698/1245/70/60824 unchanged pixels, oracle enemy_anim 2/70->1/70 (first k=61, mm_timer 70/70))*

**Result.** mettaur 19698/1245/70/60824 unchanged pixels, oracle enemy_anim 2/70->1/70 (first k=61, mm_timer 70/70); SWING shows IDLE on 64th executor tick per canon sub_8109DEC (asm31.s:170830-170848, SWING_POSE=0x40-1 derived), six chip literals pose:None behavior-neutral; wave/window/chip-cannon/opening-isolated PASS 0, opening integrated 72499 pre-existing (verify_rows PASS, landed 5ef3a6d). Worker worker-muse (muse-spark-1.3-contributor:high, 81 turns, $0.0385). Verifier verifier-glm (glm-5.3-flash:high, 25 turns, $0.0129): routine semantics, neutrality, 0px idle all CONFIRMED by independent oracle+capture measurement. Unverified/next: 1-frame relative-phase skew (MegaMan-side, out of scope) is the follow-up.
**Why.** F14b landed `3e49236`: `mettaur` 31075->19698 (worst 1566->1245, 70 frames, negative frame 60824 not blind); `src/actor.rs` only, mercy-blink predicate now `(invulnerable>>1)&1`; `mm_timer` 70/70, first oracle divergence `enemy_anim` k=61 (2/70); full table exactly one row differs (improved). The mercy seed/rate and blink predicate are settled and stay untouched -- the remainder is the enemy's animation state, not a third mercy ticket.
**Do, in order.**
1. Start in `tools/worktree.sh f17-mettaur-anim`. Baseline `python3 tools/harness.py --only mettaur` (must read 19698/1245/70, negative 60824 not blind), plus `tools/diffmask.py` region and `tools/oracle.py mettaur` (must read `mm_timer` 70/70, first divergence `enemy_anim` k=61), measured.
2. Localize the `enemy_anim` k=61 frames to the Mettaur's attack element and pixels, find canon's Mettaur animation routine in `reference/bn6f` and cite it, fix `src/` only, measured on the same oracle fields and pixel frames.
3. Re-run `mettaur`, `wave`, `window`, `opening`, `chip-cannon` and the full table -- nothing may get worse, and a row that does is reported with its numbers, measured.
**Rules.** `src/` enemy-animation path only; mercy seed/rate/blink predicate and comments untouched; no allowlist change; no alignment or region change except by measured event (F2's rule); captures one at a time.
**Measure and report.** Row `mettaur` before/after (total/worst/frames) on the identical script and window, oracle `mm_timer` match count and first `enemy_anim` divergent frame before/after, full-table deltas.
**Coordinator:** `verify_rows` on every row the report names; the verifier only for claims beyond harness lines (routine identity, cause); a wrong-guess PARTIAL gets one follow-up; a second miss marks it BLOCKED and moves on.

- F18 PARTIAL -- `windowclose` isolated: the close event's remaining total. windowclose 695603/28784/40/778748 -> 666451/28784/40/749690
### F20b. `tiles`/`gauge` integrated: match the fixture's sprite positions to canon's state  *(DONE -- 2026-09-13, tiles/gauge integrated 25979/3282->3865/678/8 (negative 15891 not blind), isolated still 0/0/8)*

**Result.** tiles/gauge integrated 25979/3282->3865/678/8 (negative 15891 not blind), isolated still 0/0/8. HUDMATCH descriptor in tools/harness.py corrected to canon-peeked BattleObject panel positions (MM col 3->2, enemy row 3->2; canon (2,2) @0x0203a9c2/3, enemy (5,2) @0x0203ab72/3); residual 3865 is canon Mettaur mid-attack vs ours idle (F17 family); wave/window/opening/chip-cannon 0, warp-integrated exceed pre-existing (stash-identical); AUDIT-6 stays. Committed 2b913aa directly on main (worker skipped worktree; single-file descriptor change, verified post-hoc). Worker worker-muse. Verifier verifier-glm: all 4 claims CONFIRMED (diff scope, offsets, HUDMATCH scope, residual sourced; caveat ours-side action byte 0x04/0x00 on tiles vs 0x04/0x09 from F17 context).
**Why.** F20's verified decomposition: the HUD strip (y<24) reads 0 on all 8 frames and `--disable-obj`
reads 0/0/8, so the whole 25979 px is sprites -- our fixture puts MegaMan at column 3 where canon's
save state holds (2,2), and the enemy one row off canon's, so both navis and the enemy's HP readout sit
in the wrong cells (canon: MegaMan (2,2), enemy (5,2)). F20's worker tried the corrected positions as
a throwaway patch: 25979 -> 3865 (worst 678), and the remaining 3865 is canon's Mettaur mid-attack
(CurState/CurAction 0x04/0x0b) against ours idle -- the enemy AI phase, F17's family, not this ticket.
Fixture, not src/. **Do:** peek canon's positions from the row's own state
(MegaMan's and the enemy's PanelX/PanelY in their BattleObjects, cite the offsets), set the row's
descriptor (`HUDMATCH` in tools/harness.py) to them with `peeked` provenance, run tiles and gauge
(both variants), wave, window, opening, chip-cannon and the full table. **Acceptance:** tiles/gauge
integrated reads about 3865 or lower with a non-blind negative (0 if the Mettaur's attack phase also
lines up), the residual reported by element with frames and regions; isolated still 0; nothing worse. **Rules:** tools/harness.py descriptor only; no allowlist
change (the AUDIT-6 entry stays until the row reads 0, then it is removed, never widened).
**Coordinator:** verify_rows; no verifier unless a claim goes beyond harness lines.

### F21. `result` isolated: 497967 px over 40, its canon side is result_arrival  *(PARTIAL -- 2026-09-13, result 497967/31882/40/476424 -> 408337/31895/40/383600 (-89630))*

**Result.** result 497967/31882/40/476424 -> 408337/31895/40/383600 (-89630); WIN reward drawn on first confirm not at show per canon chain sub_802C34E->sub_802BE36->sub_802C044 (42 tiles 0x2a) ->sub_802C0A4 (30f cooldown 0x1e), driver sub_802BD60; phases Waiting->Revealing42->Cooldown30->RewardWait->Dismissing, LOSE unchanged; plateau inside 3734->904, outside ~2900 backdrop tail + slide lag remain. wave/window/chip-cannon/opening-isolated 0; field-integrated delta is RNG noise (no Shown on that path); full table no other deltas (verify_rows PASS, landed 8bcd73c). Worker worker-muse (muse-spark-1.3-contributor:high, 94 turns, $0.1096). Verifier verifier-glm (glm-5.3-flash:high, 15 turns, $0.0079): all 4 claims CONFIRMED (minor per-function line-attribution slip, values genuine). Next: seed RESULT_ROW art/scroll from peeked RESULT_ARRIVAL RAM (~2900 outside plateau), then slide-phase lag.
**Why.** `result` isolated reads total 497967 (worst 31882) over 40 frames at canon 21+k, rust 10(marker)+15+k (`web/captures/result-isolated.txt:1`, canon REAL+RESULT_ARRIVAL); rust is RESULT_ROW (RESULTMATCH_ROW + result_elapsed=0, `tools/harness.py:1148`); the row note (`tools/harness.py:1529-1535`) records the sweep: result_elapsed 0..40 at fixed offset bottoms at elapsed=14 (522212) but the joint minimum with the row's own search=range(0,60) is elapsed=0 at offset 15 (497967, every other sample 504-505k) -- result_elapsed is not the knob; localized shape is full-screen frame 0 (bbox x0-239,y0-159, 31882) decaying (30846, 29995, ... 17395 by k=10) to a flat ~6600-6900 px plateau from k=16 that never reaches 0; the reward-content theory is disproven (decoded frames: DeleteTime 0:29:33 = exactly 1760, Busting LV. 2, 100z, no chip -- RESULT_ROW's result_frames=1760/level=2/zenny=100 and megaman_hp=60 already match, peeked HP 0x3c/MaxHP 0x64); gauge=1 ruled out (identical 497967/31882); what is left is the pre-arrival battle tail, named lead eBGScrollCBCounters 0x02009690/0x02009694 reading 0x0530/0x8298 at RESULT_ARRIVAL frame 0.
**Do, in order.**
1. Start in `tools/worktree.sh f21-result`. Baseline `python3 tools/harness.py --only result` (497967/31882/40 at offset 15, negative confirmed not blind), plus `tools/diffmask.py` region (early full-screen frames vs k=16+ plateau split) on the same window, measured.
2. Localize the residue to the pre-arrival tail element (backdrop phase vs slide-in/result-window content), find canon's result routine in `reference/bn6f` and cite it, fix `src/` (or the fixture/descriptor with `peeked` provenance if the residue is the tail state), never the alignment, measured on the same frames and region.
3. Re-run `result`, `wave`, `window`, `opening`, `chip-cannon` and the full table -- nothing may get worse, and a row that does is reported with its numbers, measured.
**Rules.** `src/` (or fixture/descriptor when the residue is the tail state) only; no allowlist change; no alignment or region change except by measured event (F2's rule); result_elapsed=0 and the reward fields stay untouched unless the measurement names them; captures one at a time.
**Measure and report.** Row `result` before/after (total/worst/frames) on the identical script and window, per-frame decay/plateau split before/after, full-table deltas.
**Coordinator:** `verify_rows` on every row the report names; the verifier only for claims beyond harness lines (routine identity, tail-state attribution); a wrong-guess PARTIAL gets one follow-up; a second miss marks it BLOCKED and moves on.

### F22. `cursor` isolated: 620802 px over 170 frames  *(NEGATIVE -- 2026-09-13, cursor 620802/6884/170/728447 unchanged (nothing landed, branch empty, deleted))*

**Result.** cursor 620802/6884/170/728447 unchanged (nothing landed, branch empty, deleted); precise refutation: at event-locked offset 237 (252-8-(22-15), canon RAM 0x020364C7 walk 0x0a->4@21->3@51->2@81->1@111->0@141 per custMenuSomeHandler_8028B74 asm03_0.s:5194, rust 252/282/312/342/372) x<112 = 0 over all 170 frames — walk, bracket, blink, names, pictures, offered deck already exact; residue 779920 all x>=112 is unshared mid-battle backdrop/enemy/HP (CUSTMATCH art/scroll 0xFFFF fresh Backdrop, F13-scoped out). Re-pin probe 779920/5181/170 documented NOT applied per coordinator decision B (worse headline, no fix; belongs in follow-up owning the row definition). wave/window/chip-cannon/opening-isolated 0 (verify_rows PASS). Worker worker (glm-5.3-flash:high, 44 turns, $0.0442). Verifier verifier (muse-spark-1.3-contributor:high, 9 turns, $0.0048): routine bytes, Align arithmetic, fixture scoping, empty diff all CONFIRMED (pixel splits not re-measured, static scope). Next: follow-up ticket for event-locked re-pin + x>=112 backdrop fixture fields.
**Why.** `cursor` isolated reads total 620802 (worst 6884) over 170 frames at canon 15+k, rust 8(marker)+226+k (`web/captures/cursor-isolated.txt:1`, canon REAL+CHIPSELECT); rust builds from CUSTMATCH_ROW with the 5-press Left walk (`tools/harness.py:1162-1163`, `_CURSOR_WALK_RUST` presses 250+30k vs `_CURSOR_WALK_REAL` 20+30k) after F13b re-pinned the walk to rust's late window opening; `AUDIT.md` records the attribution as BG3 119680 + OBJ 671892 (the bracket and portrait icons); F15 left `cursor` unmoved at 620802 while fixing the shared vblank frame, so the remainder is the cursor-walk/icons residue, not the tile-write race.
**Do, in order.**
1. Start in `tools/worktree.sh f22-cursor`. Baseline `python3 tools/harness.py --only cursor` (620802/6884/170, negative confirmed not blind), plus `tools/diffmask.py` region (BG3 vs OBJ split, bracket/portrait localization) and per-press transition frames (canon RAM 21/51/81/111/141 pixels +1, rust pixel 252/282/312/342/372), measured.
2. Localize the residue to cursor-slot frames vs bracket/portrait-icon pixels, find canon's cursor/icon routine in `reference/bn6f` and cite it, fix `src/` (or the fixture/descriptor with `peeked` provenance if the residue is the offered-deck fixture), measured on the same transitions and region.
3. Re-run `cursor`, `wave`, `window`, `opening`, `chip-cannon` and the full table -- nothing may get worse, and a row that does is reported with its numbers, measured.
**Rules.** `src/` (or fixture/descriptor when the residue is the fixture) only; no allowlist change; no alignment or region change except by measured event (F2's rule); captures one at a time.
**Measure and report.** Row `cursor` before/after (total/worst/frames) on the identical script and window, diffmask BG3/OBJ split before/after, transition-frame alignment before/after, full-table deltas.
**Coordinator:** `verify_rows` on every row the report names; the verifier only for claims beyond harness lines (routine identity, cause); a wrong-guess PARTIAL gets one follow-up; a second miss marks it BLOCKED and moves on.

### F22b. `cursor` isolated: match the x>=112 unshared mid-battle content on the fixture side  *(NEGATIVE -- 2026-09-13, cursor fixture backdrop-seed probe refuted, nothing landed)*

**Result.** cursor fixture backdrop-seed probe refuted, nothing landed. 620802/6884/170 unchanged (verify_rows PASS on HEAD, negative not blind); load-peeked seed (entry 15/timer 3/scroll 629/913) scored 1295120 at offset 237 (worse than 779920 there), reverted with clean tree; offset 237 stands (226 is false minimum, x<112 nonzero there); shift metrology shows coexisting exact translations (116,16)/(52,48) irreconcilable with single clock offset under 2:1 scroll, i.e. BGScrollCB raster-callback behavior needing src/ work; branch deleted, main clean. Worker worker-muse (78 turns, $0.102). Verifier verifier-glm: session internally consistent, all measurements run as described, negative correct; nits: 44% figure unmeasured in transcript, reverted comment's peeked counters really live-register-derived (moot). Next: follow-up owning the row definition (src/ raster-callback mechanism) or re-pin decision.
**Files.** tools/harness.py

**Why.** F22's Result is a precise refutation: `cursor` 620802/6884/170/728447 unchanged (nothing landed, branch empty, deleted); at event-locked offset 237 (252-8-(22-15), canon RAM 0x020364C7 walk 0x0a->4@21->3@51->2@81->1@111->0@141 per custMenuSomeHandler_8028B74 asm03_0.s:5194, rust 252/282/312/342/372) x<112 = 0 over all 170 frames -- walk, bracket, blink, names, pictures, offered deck already exact; the whole 620802 residue is x>=112 unshared mid-battle content (backdrop scroll/art phase, enemy, HP) between the CUSTMATCH fixture (art/scroll 0xFFFF fresh Backdrop) and canon's chipselect state. The re-pin probe 779920/5181/170 was documented NOT applied per coordinator decision B (worse headline, no fix; belongs in the follow-up owning the row definition). F15 left `cursor` unmoved at 620802 while fixing the shared vblank frame, so this is fixture content, not src/.
**Do, in order.**
1. Start in `tools/worktree.sh f22b-cursor-fixture`. Baseline `python3 tools/harness.py --only cursor` (must read 620802/6884/170, negative confirmed not blind), plus `tools/diffmask.py` x<112 vs x>=112 split confirming x<112 = 0 over all 170 frames at the event-locked alignment, measured.
2. Match the x>=112 content on the fixture side only: peek the backdrop art/scroll phase, enemy and HP state from canon's chipselect capture state with `peeked` provenance into the CUSTMATCH descriptor, or blank the same element on BOTH sides, never one; keep the event-locked alignment (offset 237 unless a `--watch 0x020364c0:0x48` event names a new frame per F2's rule), measured on the same 170 frames and x>=112 region.
3. Re-run `cursor`, `wave`, `window`, `opening`, `chip-cannon` and the full table -- nothing may get worse, and a row that does is reported with its numbers, measured.
**Rules.** Fixture/descriptor with `peeked` provenance (or symmetric blanking on both sides) only; no src/ change unless the measurement names a cursor element; no allowlist change; no alignment change except by measured event; captures one at a time.
**Measure and report.** Row `cursor` before/after (total/worst/frames) on the identical script and window, x<112 vs x>=112 split before/after, full-table deltas.
**Coordinator:** `verify_rows` on every row the report names; the verifier only for claims beyond harness lines (fixture-content class, peeked offsets); a wrong-guess PARTIAL gets one follow-up; a second miss marks it BLOCKED and moves on.


### F18b. `windowclose` isolated: the k=11 transient and the slide residue outside the window layer  *(PARTIAL -- 2026-09-13, windowclose 666451/28784/40->651885/28430/40 [k=11 BG3 transient 2447->0)*

**Result.** windowclose 666451/28784/40->651885/28430/40 (k=11 BG3 transient 2447->0; relocated to k=9 1898 + k=10 1408, net -14566). Same-call Done at x==SLIDE_FROM in src/custom.rs per canon sub_8026BF4 (asm03_0.s:1037, flip 1119-1125); guards wave/window/opening/chip-cannon 0, opening integrated 72499 pre-existing; field-integrated 358291->358162 (worst same, in cap). Landed f5e5380. Worker worker-muse. Verifier verifier-glm: all 4 claims CONFIRMED (asm cite line-for-line, relocation consistent, field delta measured both sides, clean single-commit tree). Remaining: relocated k=9/k=10 close-frame blank/redraw needs canon-91 scroll/map evidence (F18c).
**Files.** src/custom.rs, tools/harness.py

**Why.** F18's Result: `windowclose` 695603/28784/40/778748 -> 666451/28784/40/749690; post-close flat band k=12..39 1402->0 (gauge 980 not-full fill 0x9222 all 16 cells per sub_801C4E4 loc_801C534 + name 422 blanked per sub_8026BF4->sub_8029D80 w=7/h=2 tile 0); slide k=0..9 still 0 on `--only-bg 3`; k=11 transient 2447 unchanged (close-sequencing off-by-one, follow-up). The remaining residue is the close sequencing plus whatever the slide frames carry outside the window layer -- offset 253 stands (JumpOffset 0x04->0x08 on the A-press frame, slide counter +0x40 counting 0x0c..0x78 across canon frames 81..90, rust slide calls at capture 261..270).
**Do, in order.**
1. Start in `tools/worktree.sh f18b-windowclose-k11`. Baseline `python3 tools/harness.py --only windowclose` (must read 666451/28784/40 at offset 253, negative confirmed not blind), plus `--only-bg 3` slide-frame totals (k=0..9 at 0, k=11 at 2447) and per-frame k=11 bbox, measured.
2. Localize the k=11 transient to the close-sequencing off-by-one and the slide frames' residue outside the window layer, find canon's close routine in `reference/bn6f` and cite it, fix `src/` only, measured on k=11 and the same slide frames/region.
3. Re-run `windowclose`, `wave`, `window`, `opening`, `chip-cannon` and the full table -- nothing may get worse, and a row that does is reported with its numbers, measured.
**Rules.** `src/` only; no allowlist change; no alignment or region change except by measured event -- offset 253 stands unless the watch names a new event frame (F2's rule); captures one at a time.
**Measure and report.** Row `windowclose` before/after (total/worst/frames) on the identical script and window, `--only-bg 3` slide-frame totals and k=11 transient before/after, full-table deltas.
**Coordinator:** `verify_rows` on every row the report names; the verifier only for claims beyond harness lines (routine identity, sequencing cause); a wrong-guess PARTIAL gets one follow-up; a second miss marks it BLOCKED and moves on.


### F21b. `result` isolated: the ~2900 px/frame outside the window -- backdrop tail and one-frame slide lag *(OPEN -- 2026-09-13)*

**Files.** src/results.rs, src/backdrop.rs

**Why.** F21's Result: `result` 497967/31882/40/476424 -> 408337/31895/40/383600 (-89630); WIN reward drawn on first confirm not at show per canon chain sub_802C34E->sub_802BE36->sub_802C044 (42 tiles 0x2a)->sub_802C0A4 (30f cooldown 0x1e), driver sub_802BD60; phases Waiting->Revealing42->Cooldown30->RewardWait->Dismissing, LOSE unchanged; plateau inside 3734->904, outside ~2900 px/frame backdrop tail + slide lagging canon by about a frame remain. Reward fields (result_frames=1760/level=2/zenny=100, megaman_hp=60) already match; result_elapsed=0 stays untouched. What is left is pre-arrival battle tail state plus the slide phase landing late.
**Do, in order.**
1. Start in `tools/worktree.sh f21b-result-tail`. Baseline `python3 tools/harness.py --only result` (must read 408337/31895/40 at offset 15, negative confirmed not blind), plus `tools/diffmask.py` inside-vs-outside-window split (inside plateau ~904, outside ~2900/frame) and `tools/oracle.py result` where supported, measured.
2. Measure with the oracle and `--watch-write` which write lands late (backdrop art/scroll tail vs slide-phase write), seed RESULT_ROW art/scroll from peeked RESULT_ARRIVAL RAM, then fix `src/` citing canon's driver sub_802BD60 chain (sub_802C34E->sub_802BE36->sub_802C044->sub_802C0A4), measured on the same outside-window frames and region.
3. Re-run `result`, `wave`, `window`, `opening`, `chip-cannon` and the full table -- nothing may get worse, and a row that does is reported with its numbers, measured.
**Rules.** `src/` (or fixture/descriptor with `peeked` provenance when the residue is the tail state) only; no allowlist change; no alignment or region change except by measured event (F2's rule); result_elapsed=0 and the reward fields stay untouched unless the measurement names them; captures one at a time.
**Measure and report.** Row `result` before/after (total/worst/frames) on the identical script and window, inside/outside-window split before/after, oracle/watch-write writer and frame before/after, full-table deltas.
**Coordinator:** `verify_rows` on every row the report names; the verifier only for claims beyond harness lines (routine identity, tail-state attribution); a wrong-guess PARTIAL gets one follow-up; a second miss marks it BLOCKED and moves on.

### F12. The chip rows' own residues, family by family  *(OPEN -- 2026-09-13, F12e feet theory refuted, no change, ticket stays OPEN)*

**Result.** F12e feet theory refuted, no change, ticket stays OPEN. chip-poisseed 247/43/70/50822, chip-iceseed 132/16/70/52022, chip-grasseed 132/16/70/52022 (verify_rows PASS on HEAD a7ee2ac, negatives not blind); k9-14 feet is NOT a palette-table selection -- bilateral OAM shows identical pos/size/palette family (canon pal 1, ours pal 7, body pixels exact), our shadow ellipse is wider tile art (rust (16,16,16) vs canon black), i.e. asset-content outside src scope; canon cite asm31.s:108961/off_80EB6F8/sub_80CE44E (seeds throw via type-3 object 0x4f, shadow path untraced); corners #2 and reorder #3 unattempted (budget, gated on #1); no commits, branch wt/f12-seed-feet deleted, main untouched at a7ee2ac. Worker worker-muse (muse-spark-1.3-contributor:high, 81 turns, $0.042). No verifier (nothing landed; refutation is measurement, not a claim to build on). Next: scope decision on assets/poisseed.bin shadow tiles, or trace t3_0x4f shadow path, or corners row-order pass.
**Result.** F12d seed sheet order landed, ticket stays OPEN for feet+corners. chip-poisseed 2237/334->247/43, chip-iceseed 2122/334->132/16, chip-grasseed 2122/334->132/16 (verify_rows PASS on 98e30f1, negatives not blind; wave/window/opening/chip-cannon 0, warp identical to HEAD); middle column pushed last (4,6,5) so it sorts above neighbours in overlap zones, gated on poison_pending>0 (seed-only); cover-order feet fix tried then reverted (ice/grass 132->180 worse, palette-content landing core out of scope); landed 002a69c. Worker worker-muse (muse-spark-1.3-contributor:high, 81 turns, $0.102). Verifier verifier-glm: all 5 claims CONFIRMED (push order, seed-only gate, clean tree, opening pre-existing, no experiment residue). Next: feet landing-core palette content (canon core-blue (8,57,123) vs foot-grey) and sheet corner cross-row order, then re-run all three seed rows.
**Result.** F12c seed family localized to OAM overlap order, ticket stays OPEN for the fix. chip-poisseed 2237/334/70/52258, chip-iceseed 2122/334/70/53458, chip-grasseed 2122/334/70/53458 (verify_rows PASS on HEAD f53cda8, negatives not blind); prior 'canon static vs our cycling' claim corrected -- both sides run pod, 1 black gap frame, 3-frame ellipse, 4-frame white, 3-frame green, 3-frame teal, diamonds frame-aligned, canon OAM static (18x 32x32 tile 31 pal 1 prio 2) while tile-31 VRAM content cycles; our VRAM tiles byte-identical to canon tile 31 (0/512), palettes identical, positions/flips identical; only divergence is overlap order in 24px inter-panel zones (zone B: canon R148 over L188, ours L188 over R148 -> 2px green-stripe shift x200-201 vs x198-199) plus 6px x160-161 corner residue and poisseed-only feet cover-order difference (canon shadow OAM11 above navi foot OAM12, ours reversed; canon BLACK vs ours (16,16,16)); no fix landed, no canon routine cited, branch wt/f12-seed2 deleted with no commits, main untouched at f53cda8. Worker worker-muse (muse-spark-1.3-contributor:high, 81 turns, $0.057). No verifier (nothing landed; mechanism unverified). Next: apply middle-column-last sheet push order (panel-148 above neighbors), re-run all three seed rows + wave/window/opening/chip-cannon + full table, then chase feet pois-only via ice/grass shadow-palette dumps.
**Result.** F12b seed family localized, ticket stays OPEN for the fix. chip-poisseed 2237/334/70/52258 (k=52-61 2px stripe x197-202 y70-142 worst 334, plus k=9-14 feet residue 43->1px), chip-iceseed 2122/334/70/53458, chip-grasseed 2122/334/70/53458 (verify_rows PASS on wt/f12-seed 253198b, negatives not blind); canon sheet square-phase is one static image (tile 31 pal 1, OBJ VRAM byte-static) vs our 3-frame cycling, but canon tile-31 matches no poisarea.bin blob and no VRAM candidate (best 103/1024 mismatched) so no fix landed, branch wt/f12-seed kept unmerged, worktree removed. Worker worker (glm-5.3-flash, 78 turns, $0.098). No verifier (nothing landed; mechanism unverified). F12a minibomb 10/10->0/0 landed a607263 earlier. Next: find canon sheet pixels at the x=200 seam (OBJ/BG priority test), localize the feet component, decompose iceseed/grasseed from main.
**Result.** F12a minibomb family done, ticket stays OPEN for seeds. chip-minibomb 10/10->0/0 (verify_rows PASS 0/0/60/17158, landed a607263); wave/window/opening-isolated/chip-cannon PASS 0; opening integrated 72499/2691 pre-existing identical on baseline; full table: energbom/megenbom -26, iceseed/grasseed 2145->2122, bugbomb 8338->8280, vdoll/suprvulc/buster/chip-use unchanged, except chip-poisseed 2145->2237 (worst 334, +92) owned by seed follow-up. Worker worker-muse (muse-spark-1.3-contributor, 75 turns, $0.068). Verifier verifier-glm (glm-5.3-flash, 18 turns, $0.016): fix code-CONFIRMED, opening pre-existing CONFIRMED, canon OAM order UNCHECKED (probe flag failure), poisseed regression PARTIALLY CONFIRMED (totals attributable, trail colors unchecked). Next: seed family (poisseed/iceseed/grasseed) with its own canon OAM dump.
**Files.** src/, tools/harness.py

**Why.** After F5b: SuprVulc 2464 / 177 / 113; the bomb, seed and VDoll rows 10 to 8338; EnergBom and
MegEnBom 19958 / 1871; the chip-family-0x15 rows 14740 to 73481. **Do:** take ONE family per run of
this ticket, smallest residue first (the rows at 10-8338), and bring its rows to 0; mark this ticket
PARTIAL with which family is done and leave it OPEN for the next family, until every chip row is 0.

- F16 DONE -- Oracle coverage: every harness row, not two. Oracle generalized to all 60 comparison rows (tools/oracle.py +138/-41, new tools/f16_slot_probe.py, export block untouched, landed ee6c494)
- F13b DONE -- `card` isolated via fixture rewire (follow-up to F13's verified negative). card 18486->0 via fixture rewire, landed 4b16fd7
- F14b PARTIAL -- `mettaur`: mercy-blink predicate bit 2 -> bit 1 (follow-up to F14's refuted negative). Blink experiment done, partial drop, landed 3e49236
- F15 DONE -- tiles/gauge: the one vblank frame, 208 px at k=7. tiles+gauge isolated 208->0, cursor unmoved 620802, landed 12a130a

### F23. Naming pass: the bare numbers in src/custom.rs and src/battle.rs  *(OPEN -- 2026-09-13, lowest priority: run after F22)*

**Files.** src/custom.rs

**Why.** The user: "the code has a lot of unnamed values and magic numbers". Counted 2026-09-13: 524
non-trivial numeric literals in src/, 325 outside any `const`/`static`; custom.rs 110 bare, battle.rs
56, actor.rs 29, results.rs 29. A name with a provenance tag is documentation the next ticket reads for
free; a bare 0x1F is a mystery every time.

**Do, in order.** One file per pass, custom.rs first. For each bare literal: identify it (the canon
symbol, struct offset or register it corresponds to, via reference/bn6f's include/structs and the
routine the surrounding code cites) and lift it into a named `const` with a `// provenance:` tag, or
annotate it `// canon: <symbol>`; spend at most a few commands per number, and tag the rest
`// unnamed: <what it appears to be>`. No behaviour change of any kind. **Acceptance:** the full table
reads identical line for line (verify_rows on every row), the release .gba differs from the baseline
only by panic line numbers (same size; `cmp -l` count reported), and the file's bare-literal count
(the script in the ticket's Result) drops by at least half. Mark the ticket OPEN again for the next file.

**Rules.** src/ only, the named file only; no allowlist, alignment or fixture change. **Coordinator:**
verify_rows on the full table; no verifier (no claims beyond harness lines).

**Common to F8-F23 (and their b-tickets) unless the ticket says otherwise.** Baseline the row (harness line plus
`tools/diffmask.py` region, plus `tools/oracle.py` where the row is supported); localize the residue to
frames and an element; find canon's routine for that element in reference/bn6f and cite it; fix src/
(or the fixture/descriptor when the residue is the fixture, with `peeked` provenance); re-run the row,
wave, window, opening, chip-cannon and the full table -- nothing may get worse, and a row that does is
reported with its numbers. No allowlist change; no alignment or region change except by measured event
(F2's rule). **Coordinator:** verify_rows on every row the report names; the verifier only for claims
beyond harness lines; a PARTIAL from a wrong guess about the cause gets one follow-up ticket; if that
also fails, mark the ticket BLOCKED and move on to the next OPEN ticket.

