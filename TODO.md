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
### F18d. `windowclose` isolated: the k11 gauge-body single-step redraw *(OPEN -- 2026-09-13)*

**Files.** src/battle.rs, src/custom.rs

**Why.** F18c's verified Result: `windowclose` 651885/28430 -> 650544/27555/40 (landed b0ba8a5); BG3 k9/k10 are 0, but k11 carries 1596 (x48-191 y0-15 canon-only): our gauge body lands k12 vs canon's single-step 149B+50B redraw at canon 92 (RGB-proven, mechanism unmodeled). Verifier independently reproduced the k9/k10/k11 relocation and confirmed a -369 px non-BG3 improvement rides along (net full-screen -1341).
**Do, in order.**
1. Start in `tools/worktree.sh f18d-windowclose-k11`. Baseline `python3 tools/harness.py --only windowclose --no-gallery` (must read 650544/27555/40 at offset 253, negative confirmed not blind), plus `--only-bg 3` per-frame k=10/k=11/k=12 totals and bboxes, measured.
2. Model canon's single-step gauge redraw at canon 92 from the row's own capture state (149B+50B regions, palette/tile writes), then land our gauge body one frame earlier in `src/` citing canon's close routine in `reference/bn6f`, measured on k=11/k=12 and the same region.
3. Re-run `windowclose`, `wave`, `window`, `opening`, `chip-cannon` and the full table -- nothing may get worse, and a row that does is reported with its numbers, measured.
**Rules.** `src/` only; no allowlist change; offset 253 stands unless a watch names a new event frame (F2's rule); captures one at a time.
**Measure and report.** Row `windowclose` before/after (total/worst/frames), `--only-bg 3` k=10/k=11/k=12 before/after, full-table deltas.
**Coordinator:** `verify_rows` on every row the report names; the verifier only for claims beyond harness lines (redraw attribution); a wrong-guess PARTIAL gets one follow-up; a second miss marks it BLOCKED and moves on.

- F21b PARTIAL -- `result` isolated: the ~2900 px/frame outside the window -- backdrop tail and one-frame slide lag. result 408337/31895->190633/24647/40 (tilemap-column slide j=-30+2/frame + 16-frame hold + peeked backdrop seed, k=10,12,13 zeroed
- F21c BLOCKED -- `result` field-row pairing: re-justify after the slide rework. field re-pairing blocked on scope decision, nothing landed
### F21d. `result`: write the window's tilemap by block copy, not 576 managed tile writes  *(OPEN -- 2026-09-13)*

**Files.** src/results.rs, src/backdrop.rs, vendor/agb

**Why.** F21c's verified measurement: F21b's slide rework (result 408337 -> 190633 on wt/f21b) regressed
`field` 0 -> 1048 because our per-tick full-map rewrite (576 `set_tile` calls through agb's VRAM
manager, ~0.46 frame per blit) overruns about one frame in three during slide frames 133-159, so our
RESULT mark dwells 2 frames per step where canon's takes 1; skip-cache + blank-init + tile-warming
cut the stalls 10 -> 1 with a remnant at capture 148/149. Canon copies the tilemap as a block
(`CopyBackgroundTiles` in the sub_802BD60 driver chain). This is the engine-timing class of residue:
fix the mechanism, not the content. **Decision (coordinator, 2026-09-13):** direct VRAM block writes
for this window are in scope, including a helper inside vendor/agb if the public API cannot express
it (fix agb, do not work around it -- see the vendor-deps rule).

**Do, in order.**
1. Start with `bash tools/worktree.sh f21d-blockcopy`, then `git merge wt/f21b-result-tail` (the slide rework,
   kept unmerged; F21c's branch was deleted, its findings are in TODO_ARCHIVE.md). Baseline result and field
   there (190633 / 24647 / 40 and 1048 / 177 / 40) plus wave, window, opening, chip-cannon.
2. Replace the per-tile rewrite with one block copy of the prepared tilemap into the window's BG map
   (memcpy or DMA3 into VRAM, sized to the map; if agb's `RegularMap`/VRAM manager owns that memory,
   add a minimal `copy_map_block` (or equivalent) to vendor/agb with a doc comment, and keep the
   manager's bookkeeping consistent). Measure the blit's cost with a per-frame cycle/scanline probe
   (or the marker's frame counter vs canon's) and report frames per step before/after.
3. **Acceptance.** field back to 0/0/40 (negative not blind); result at or below 190633 with the mark
   dwelling 1 frame per step like canon; wave/window/opening/chip-cannon 0; full table nothing worse.
   Land F21b's rework together with this fix; if the copy cannot reach 1 frame/step, report the
   measured cost per blit and stop.

**Rules.** src/results.rs, src/backdrop.rs and vendor/agb only; no allowlist, alignment or fixture
change. **Coordinator:** verify_rows on result, field and the canaries; the verifier on the
"1 frame per step" claim (it must measure it, e.g. with the oracle or a frame-count watch).

### F12. The chip rows' own residues, family by family  *(OPEN -- 2026-09-13, F12e feet theory refuted, no change, ticket stays OPEN)*

**Result.** F12e feet theory refuted, no change, ticket stays OPEN. chip-poisseed 247/43/70/50822, chip-iceseed 132/16/70/52022, chip-grasseed 132/16/70/52022 (verify_rows PASS on HEAD a7ee2ac, negatives not blind); k9-14 feet is NOT a palette-table selection -- bilateral OAM shows identical pos/size/palette family (canon pal 1, ours pal 7, body pixels exact), our shadow ellipse is wider tile art (rust (16,16,16) vs canon black), i.e. asset-content outside src scope; canon cite asm31.s:108961/off_80EB6F8/sub_80CE44E (seeds throw via type-3 object 0x4f, shadow path untraced); corners #2 and reorder #3 unattempted (budget, gated on #1); no commits, branch wt/f12-seed-feet deleted, main untouched at a7ee2ac. Worker worker-muse (muse-spark-1.3-contributor:high, 81 turns, $0.042). No verifier (nothing landed; refutation is measurement, not a claim to build on). Next: scope decision on assets/poisseed.bin shadow tiles, or trace t3_0x4f shadow path, or corners row-order pass.
**Result.** F12d seed sheet order landed, ticket stays OPEN for feet+corners. chip-poisseed 2237/334->247/43, chip-iceseed 2122/334->132/16, chip-grasseed 2122/334->132/16 (verify_rows PASS on 98e30f1, negatives not blind; wave/window/opening/chip-cannon 0, warp identical to HEAD); middle column pushed last (4,6,5) so it sorts above neighbours in overlap zones, gated on poison_pending>0 (seed-only); cover-order feet fix tried then reverted (ice/grass 132->180 worse, palette-content landing core out of scope); landed 002a69c. Worker worker-muse (muse-spark-1.3-contributor:high, 81 turns, $0.102). Verifier verifier-glm: all 5 claims CONFIRMED (push order, seed-only gate, clean tree, opening pre-existing, no experiment residue). Next: feet landing-core palette content (canon core-blue (8,57,123) vs foot-grey) and sheet corner cross-row order, then re-run all three seed rows.
**Result.** F12c seed family localized to OAM overlap order, ticket stays OPEN for the fix. chip-poisseed 2237/334/70/52258, chip-iceseed 2122/334/70/53458, chip-grasseed 2122/334/70/53458 (verify_rows PASS on HEAD f53cda8, negatives not blind); prior 'canon static vs our cycling' claim corrected -- both sides run pod, 1 black gap frame, 3-frame ellipse, 4-frame white, 3-frame green, 3-frame teal, diamonds frame-aligned, canon OAM static (18x 32x32 tile 31 pal 1 prio 2) while tile-31 VRAM content cycles; our VRAM tiles byte-identical to canon tile 31 (0/512), palettes identical, positions/flips identical; only divergence is overlap order in 24px inter-panel zones (zone B: canon R148 over L188, ours L188 over R148 -> 2px green-stripe shift x200-201 vs x198-199) plus 6px x160-161 corner residue and poisseed-only feet cover-order difference (canon shadow OAM11 above navi foot OAM12, ours reversed; canon BLACK vs ours (16,16,16)); no fix landed, no canon routine cited, branch wt/f12-seed2 deleted with no commits, main untouched at f53cda8. Worker worker-muse (muse-spark-1.3-contributor:high, 81 turns, $0.057). No verifier (nothing landed; mechanism unverified). Next: apply middle-column-last sheet push order (panel-148 above neighbors), re-run all three seed rows + wave/window/opening/chip-cannon + full table, then chase feet pois-only via ice/grass shadow-palette dumps.
**Result.** F12b seed family localized, ticket stays OPEN for the fix. chip-poisseed 2237/334/70/52258 (k=52-61 2px stripe x197-202 y70-142 worst 334, plus k=9-14 feet residue 43->1px), chip-iceseed 2122/334/70/53458, chip-grasseed 2122/334/70/53458 (verify_rows PASS on wt/f12-seed 253198b, negatives not blind); canon sheet square-phase is one static image (tile 31 pal 1, OBJ VRAM byte-static) vs our 3-frame cycling, but canon tile-31 matches no poisarea.bin blob and no VRAM candidate (best 103/1024 mismatched) so no fix landed, branch wt/f12-seed kept unmerged, worktree removed. Worker worker (glm-5.3-flash, 78 turns, $0.098). No verifier (nothing landed; mechanism unverified). F12a minibomb 10/10->0/0 landed a607263 earlier. Next: find canon sheet pixels at the x=200 seam (OBJ/BG priority test), localize the feet component, decompose iceseed/grasseed from main.
**Result.** F12a minibomb family done, ticket stays OPEN for seeds. chip-minibomb 10/10->0/0 (verify_rows PASS 0/0/60/17158, landed a607263); wave/window/opening-isolated/chip-cannon PASS 0; opening integrated 72499/2691 pre-existing identical on baseline; full table: energbom/megenbom -26, iceseed/grasseed 2145->2122, bugbomb 8338->8280, vdoll/suprvulc/buster/chip-use unchanged, except chip-poisseed 2145->2237 (worst 334, +92) owned by seed follow-up. Worker worker-muse (muse-spark-1.3-contributor, 75 turns, $0.068). Verifier verifier-glm (glm-5.3-flash, 18 turns, $0.016): fix code-CONFIRMED, opening pre-existing CONFIRMED, canon OAM order UNCHECKED (probe flag failure), poisseed regression PARTIALLY CONFIRMED (totals attributable, trail colors unchecked). Next: seed family (poisseed/iceseed/grasseed) with its own canon OAM dump.
**Files.** src/, assets/, tools/harness.py

**Decision (2026-09-13, human session): assets are in scope when the replacement is canon's own data.** The seed sheet's shadow (F12e: ours is a wider (16,16,16) ellipse baked into the sheet, canon's is black and narrower) is fixed by tracing canon's shadow path (the seeds throw a type-3 object 0x4f via off_80EB6F8/sub_80CE44E; the shadow path is untraced) and reproducing what canon draws -- tiles extracted from the canon ROM, or the shadow drawn as the separate object canon uses. Hand-drawn art that merely looks closer is not in scope.

**Why.** After F5b: SuprVulc 2464 / 177 / 113; the bomb, seed and VDoll rows 10 to 8338; EnergBom and
MegEnBom 19958 / 1871; the chip-family-0x15 rows 14740 to 73481. **Do:** take ONE family per run of
this ticket, smallest residue first (the rows at 10-8338), and bring its rows to 0; mark this ticket
PARTIAL with which family is done and leave it OPEN for the next family, until every chip row is 0.

- F16 DONE -- Oracle coverage: every harness row, not two. Oracle generalized to all 60 comparison rows (tools/oracle.py +138/-41, new tools/f16_slot_probe.py, export block untouched, landed ee6c494)
- F13b DONE -- `card` isolated via fixture rewire (follow-up to F13's verified negative). card 18486->0 via fixture rewire, landed 4b16fd7
- F14b PARTIAL -- `mettaur`: mercy-blink predicate bit 2 -> bit 1 (follow-up to F14's refuted negative). Blink experiment done, partial drop, landed 3e49236
- F15 DONE -- tiles/gauge: the one vblank frame, 208 px at k=7. tiles+gauge isolated 208->0, cursor unmoved 620802, landed 12a130a

### F25. Mettaur attack phase: enter canon's 106-frame attack cycle like canon does *(OPEN -- 2026-09-13)*

**Files.** src/actor.rs, src/ai.rs

**Why.** Three rows wait on the same missing behavior -- our Mettaur idles while canon's attacks. F17's Result: `mettaur` 19698/1245/70/60824 unchanged pixels, oracle `mm_timer` 70/70 with first divergence `enemy_anim` k=61 (2/70); SWING shows IDLE on the 64th executor tick per canon sub_8109DEC (asm31.s:170830-170848, SWING_POSE=0x40-1 derived); mercy seed/rate/blink predicate settled and untouched. F20b's Result: `tiles`/`gauge` integrated 25979/3282->3865/678/8 (negative 15891 not blind), isolated still 0/0/8, via the HUDMATCH descriptor corrected to canon-peeked BattleObject panel positions (MM (2,2) @0x0203a9c2/3, enemy (5,2) @0x0203ab72/3); the residual 3865 is canon's Mettaur mid-attack (CurState/CurAction 0x04/0x0b) against ours idle -- F17's family, not the fixture. F19's Result (TODO_ARCHIVE.md): `popup` 107511/1348/80/108815 -> 60614/1842/80/60806 (-44%, fixture only, landed c2c24e6); subject center band 0, enemy box 51991->6081, HUD bar 55520 unchanged. Canon anchors: both sides run the same 106-frame Mettaur attack cycle (canon attack animations start at canon frames 32, 138; ours at battle frames 95, 201, 307, 413 -- TODO_ARCHIVE.md F2); enemy slots 0x0203aa88/0x0203ab60/0x0203ac38 per AGENT_GUIDE.md, BattleObject offsets per reference/bn6f/include/structs/BattleObject.inc.
**Do, in order.**
1. Start in `tools/worktree.sh f25-mettaur-attack`. Baseline `python3 tools/harness.py --only mettaur,tiles,gauge,popup --no-gallery` (must read mettaur 19698/1245/70 with negative 60824 not blind, tiles/gauge integrated 3865/678/8 with negative 15891 not blind, popup 60614/1842/80), plus `tools/oracle.py mettaur` (must read `mm_timer` 70/70, first `enemy_anim` divergence k=61) and `tools/diffmask.py` region splits (tiles/gauge OBJ cells, popup HUD bar), measured.
2. Drive our Mettaur into canon's attack cycle: find canon's Mettaur attack-timing/animation routine in `reference/bn6f` and cite it, fix `src/` (attack-phase entry, frame-95-equivalent timing, attack animation/CurState-CurAction) only, measured on the same oracle fields (first `enemy_anim` divergence at/past k=61, attack-cycle phase vs canon's 106-frame period) and the same pixel frames and regions.
3. Re-run `mettaur`, `tiles`, `gauge`, `popup`, `wave`, `window`, `opening`, `chip-cannon` and the full table -- nothing may get worse, and a row that does is reported with its numbers, measured.
**Rules.** `src/` enemy-attack path only; mercy seed/rate/blink predicate, HUDMATCH positions, and popup fixture untouched; no allowlist change; no alignment or region change except by measured event (F2's rule).
**Measure and report.** Rows `mettaur`, `tiles`/`gauge` (both variants), `popup` before/after (total/worst/frames) on the identical scripts and windows, oracle `mm_timer` match count and first `enemy_anim` divergent frame before/after, tiles/gauge OBJ-cell and popup HUD-bar splits before/after, full-table deltas. **Acceptance:** `mettaur` 0/0/70 (negative not blind); `tiles`/`gauge` integrated at or below 3865 decomposed by element with frames and regions (0 if the attack phase lines up); `popup` HUD bar 55520 decomposed, enemy-box element toward 0; isolated variants still 0; nothing worse.
**Coordinator:** `verify_rows` on every row the report names; the verifier only for claims beyond harness lines (routine identity, attack-phase attribution); a wrong-guess PARTIAL gets one follow-up; a second miss marks it BLOCKED and moves on.

### F24. `cursor`/`result` backdrop: port canon's per-scanline BG scroll (the BGScrollCB HBlank raster callback) into src/ *(OPEN -- 2026-09-13)*

**Files.** src/backdrop.rs, tools/harness.py

**Why.** F22's Result is a precise refutation: `cursor` 620802/6884/170/728447 unchanged (nothing landed, branch empty, deleted); at event-locked offset 237 (252-8-(22-15), canon RAM 0x020364C7 walk 0x0a->4@21->3@51->2@81->1@111->0@141 per custMenuSomeHandler_8028B74 asm03_0.s:5194, rust 252/282/312/342/372) x<112 = 0 over all 170 frames -- walk, bracket, blink, names, pictures, offered deck already exact; the whole residue is x>=112 unshared mid-battle content (backdrop scroll/art phase, enemy, HP). F22b's Result refuted the fixture-side fix: a load-peeked backdrop seed (entry 15/timer 3/scroll 629/913) scored 1295120 at offset 237, worse than the 779920 there, and was reverted with a clean tree; offset 237 stands (226 is a false minimum, x<112 nonzero there); shift metrology shows coexisting exact translations (116,16)/(52,48) irreconcilable with a single clock offset under 2:1 scroll -- i.e. per-scanline BGScrollCB raster-callback behavior that no uniform scroll phase or seed can reproduce, needing src/ work. The same mechanism is what the result row's backdrop tail needs: F21's Result leaves ~2900 px/frame outside the window (backdrop tail + slide lagging canon by about a frame), and F21b's branch (408337/31895->190633/24647/40 via tilemap-column slide + peeked backdrop seed) was NOT LANDED after the verifier refuted its tail story. Canon anchors: the battle backdrop scrolls under `BGScrollCB_BG1Diagonal3to2Scroll` (reference/bn6f/asm/asm00_0.s:3272-3288) off the counter pair `eBGScrollCBCounters` at 0x02009690/0x02009694, zeroed exactly once at battle init by `sub_8080D90`; battle frame 0 = both counters 0. F22b was Files tools/harness.py and concluded the row needs a src/ raster-callback mechanism, not another seed.
**Do, in order.**
1. Start in `tools/worktree.sh f24-raster-scroll`. Baseline `python3 tools/harness.py --only cursor,result --no-gallery` (must read cursor 620802/6884/170 at offset 237 and result 408337/31895/40 at offset 15, negatives confirmed not blind), plus `tools/diffmask.py` cursor x<112 vs x>=112 split (x<112 = 0) and result inside/outside-window split (outside ~2900 px/frame), measured.
2. Port canon's per-scanline backdrop scroll into `src/backdrop.rs`: find the HBlank raster callback canon installs for the battle backdrop in `reference/bn6f` (the BGScrollCB family off `eBGScrollCBCounters`), cite the routine line-for-line, and drive our BGOFS writes per scanline from the same counters, measured on the cursor x>=112 frames and the result outside-window frames with per-frame totals and bboxes before/after.
3. Re-run `cursor`, `result`, `wave`, `window`, `opening`, `chip-cannon` and the full table -- nothing may get worse, and a row that does is reported with its numbers, measured.
**Rules.** `src/backdrop.rs` mechanism plus harness row-note documentation only; no uniform-scroll seed or single-offset re-fit; no allowlist change; no alignment change except by measured event -- offsets 237 (cursor) and 15 (result) stand unless a watch names a new event frame (F2's rule).
**Acceptance.** `cursor` 0/0/170 (negative not blind) is the target; a landing needs the x>=112 residue reduced by the per-scanline mechanism itself (routine cited), the result outside-window tail reduced on the same alignment, and nothing worse; if the mechanism is ported and cursor still differs, report the per-frame split and stop (one follow-up at most).
**Measure and report.** Rows `cursor` + `result` before/after (total/worst/frames) on the identical scripts and windows, cursor x<112 vs x>=112 split and result inside/outside-window split before/after, canon raster routine cited with file and lines, full-table deltas.
**Coordinator:** `verify_rows` on every row the report names; the verifier only for claims beyond harness lines (routine identity, per-scanline attribution); a wrong-guess PARTIAL gets one follow-up; a second miss marks it BLOCKED and moves on.

### F23. Naming pass: the bare numbers in src/custom.rs and src/battle.rs  *(OPEN -- 2026-09-13, F23 custom.rs naming landed, ticket OPEN for battle.rs)*

**Result.** F23 custom.rs naming landed, ticket OPEN for battle.rs. Bare literals 299->0 (~60 provenance consts, canon/unnamed tags); release .text byte-identical branch-vs-main, .gba 541272B both, cmp-l 49 (0x41669-0x826a6 rodata panic lines); spot verify_rows PASS (window 0, poisseed 247/43); landed fb51444. Worker worker-muse. No verifier (no behavior claims beyond harness lines; .text proof independent). Next: battle.rs (56 bare).
**Files.** src/battle.rs

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

