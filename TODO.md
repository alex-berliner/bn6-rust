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
### F18d. `windowclose` isolated: the k11 gauge-body single-step redraw  *(DONE -- 2026-09-13, windowclose 650544/27555/40->648948/27391/40 [BG3 k11 1596->0, x48-191 y0-15])*

**Result.** windowclose 650544/27555/40->648948/27391/40 (BG3 k11 1596->0, x48-191 y0-15); wave/window/chip-cannon 0; opening isolated 0 (integrated 72499 pre-existing on base); verifier CONFIRMED all 3 claims (149B+50B single-step canon redraw, 1-frame agb lag mechanism, close_blank arms only on close); landed bb8e8f0; worker muse-spark-1.3-contributor 83 turns $0.106, verifier GLM
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
### F21d. `result`: write the window's tilemap by block copy, not 576 managed tile writes  *(DONE -- 2026-09-13, result 408337/31895->102547/14866/40 [neg 195579 not blind], field 1048/177->0/0/40)*

**Result.** result 408337/31895->102547/14866/40 (neg 195579 not blind), field 1048/177->0/0/40; 17 blits in 17 consecutive frames (1/step, was 2/step +0.47 overrun); wave/window/opening/chip-cannon 0; field-int 358420->305263 better; verifier CONFIRMED all 3 claims (OAM trace 1f/step, refcount audit, scope); landed 90dd655; worker muse-spark-1.3-contributor 77 turns $0.069, verifier GLM
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

### F12. The chip rows' own residues, family by family -- multi-pass, stays OPEN until every chip row is 0  *(OPEN -- 2026-09-13, suprvulc family: 2464/177/113->0/0/113 PASS [neg 28047] via canon-data muzzle-fire replica [tile512+pal11 byte)*

**Result.** suprvulc family: 2464/177/113->0/0/113 PASS (neg 28047) via canon-data muzzle-fire replica (tile512+pal11 bytes verified) chip-gated to SuprVulc (gate cec8c48 fixes verifier-refuted guarantee); vulcans/seeds/bugbomb/minibomb/wave 0, cursor 272341 (total/worst better than HEAD 272362); verifier CONFIRMED asset+trajectory+scope; landed 7b551ad HEAD re-check MATCH; worker muse-spark + gate-micro 22 turns $0.008, verifier GLM
**Result.** suprvulc: still 2464/177/113, no fix (budget stop, no edits); verifier CONFIRMED all 3 exclusions (T4 const 0x40000000 f0-134; gun slot static state4 to c115 + linkage confirmed, siblings static; volley 0xa-tick + 10 shots + FAN bytes match ours -- citation offset: mov/strh at ~109977); ball is LIVE object (shadow writes to c125), driver still unknown (spawn_t1_0x5 spawns nothing); next: tile-streaming lead 0x02034b80/c86-89 or replication fix; worker muse-spark 80 turns $0.032, verifier GLM
**Result.** suprvulc pass: LOCALIZED not fixed (tool-budget stop, no edits, branch clean removed): residue = one 16x16 canon fireball (obj0 tile512 pal11) k99-112, parks x=37 from capture 107; canon 10 T3 shots/11f period vs ours stagger 10; hypothesis sub_80EBF6E last-shot beat / muzzle-fire / T4-pool UNVERIFIED; no verifier (no claims); worker muse-spark 76 turns $0.026
**Result.** vdoll family: chip-vdoll 628/564->0/0/70 PASS (neg 36375); rest_snaps+rest_z(0)+rest_poisons+LANDING_LAG=1 (sub_80D47C0/loc_80D481E); bugbomb/seeds/minibomb/guards 0, cursor 620802; verifier CONFIRMED all 3 (routine, decrement-before-branch, scope) + rules clean; landed c622a81 HEAD re-check MATCH; worker muse-spark 57 turns $0.032, verifier GLM
**Result.** bugbomb family: chip-bugbomb 8280/414->0/0/70 PASS (neg 23486); vdoll 628 unchanged (BugBomb-only gate); cursor 620802 unchanged; seeds/minibomb/guards 0; verifier CONFIRMED sub_80D9E94 snap (Z=0xa<<16), VDoll path identical, blast out-of-row, rules clean (8280-decomposition unchecked); landed 26372d1 HEAD re-check MATCH; next: vdoll 628; worker muse-spark 58 turns $0.027, verifier GLM
**Result.** feet per-family push order: poisseed 115/43->0/0/70 PASS (neg 50708), ice/grass/minibomb 0; cursor +112 drift GONE (620802, F22 value, HEAD re-check MATCH); bugbomb 8280/vdoll 628 unchanged; verifier CONFIRMED scope+cursor-numbers+rules-clean, OAM mechanism UNCHECKED (gap, uncontradicted, 0px/70f); landed e257338; worker muse-spark 90 turns $0.042, verifier GLM
**Result.** corners row-order pass: poisseed 247/43->115/43 (k9-14 feet only), iceseed/grasseed 132/16->0/0/70 PASS (negs 50722/51922 not blind); wave/window/opening/chip-cannon/minibomb 0; verifier CONFIRMED feet cover-order reversal (tiles/pal/geometry byte-identical), CONFIRMED 18-obj row-grouping (9-obj unchecked), CONFIRMED minibomb-conflict (bomb OAM5 shadow OAM9/10 below navi); feet fix not attempted (per-family reorder vs minibomb 0); landed 54abe87; worker muse-spark-1.3-contributor +resume, verifier GLM
**Result.** F12e feet theory refuted, no change, ticket stays OPEN. chip-poisseed 247/43/70/50822, chip-iceseed 132/16/70/52022, chip-grasseed 132/16/70/52022 (verify_rows PASS on HEAD a7ee2ac, negatives not blind); k9-14 feet is NOT a palette-table selection -- bilateral OAM shows identical pos/size/palette family (canon pal 1, ours pal 7, body pixels exact), our shadow ellipse is wider tile art (rust (16,16,16) vs canon black), i.e. asset-content outside src scope; canon cite asm31.s:108961/off_80EB6F8/sub_80CE44E (seeds throw via type-3 object 0x4f, shadow path untraced); corners #2 and reorder #3 unattempted (budget, gated on #1); no commits, branch wt/f12-seed-feet deleted, main untouched at a7ee2ac. Worker worker-muse (muse-spark-1.3-contributor:high, 81 turns, $0.042). No verifier (nothing landed; refutation is measurement, not a claim to build on). Next: scope decision on assets/poisseed.bin shadow tiles, or trace t3_0x4f shadow path, or corners row-order pass.
**Result.** F12d seed sheet order landed, ticket stays OPEN for feet+corners. chip-poisseed 2237/334->247/43, chip-iceseed 2122/334->132/16, chip-grasseed 2122/334->132/16 (verify_rows PASS on 98e30f1, negatives not blind; wave/window/opening/chip-cannon 0, warp identical to HEAD); middle column pushed last (4,6,5) so it sorts above neighbours in overlap zones, gated on poison_pending>0 (seed-only); cover-order feet fix tried then reverted (ice/grass 132->180 worse, palette-content landing core out of scope); landed 002a69c. Worker worker-muse (muse-spark-1.3-contributor:high, 81 turns, $0.102). Verifier verifier-glm: all 5 claims CONFIRMED (push order, seed-only gate, clean tree, opening pre-existing, no experiment residue). Next: feet landing-core palette content (canon core-blue (8,57,123) vs foot-grey) and sheet corner cross-row order, then re-run all three seed rows.
**Result.** F12c seed family localized to OAM overlap order, ticket stays OPEN for the fix. chip-poisseed 2237/334/70/52258, chip-iceseed 2122/334/70/53458, chip-grasseed 2122/334/70/53458 (verify_rows PASS on HEAD f53cda8, negatives not blind); prior 'canon static vs our cycling' claim corrected -- both sides run pod, 1 black gap frame, 3-frame ellipse, 4-frame white, 3-frame green, 3-frame teal, diamonds frame-aligned, canon OAM static (18x 32x32 tile 31 pal 1 prio 2) while tile-31 VRAM content cycles; our VRAM tiles byte-identical to canon tile 31 (0/512), palettes identical, positions/flips identical; only divergence is overlap order in 24px inter-panel zones (zone B: canon R148 over L188, ours L188 over R148 -> 2px green-stripe shift x200-201 vs x198-199) plus 6px x160-161 corner residue and poisseed-only feet cover-order difference (canon shadow OAM11 above navi foot OAM12, ours reversed; canon BLACK vs ours (16,16,16)); no fix landed, no canon routine cited, branch wt/f12-seed2 deleted with no commits, main untouched at f53cda8. Worker worker-muse (muse-spark-1.3-contributor:high, 81 turns, $0.057). No verifier (nothing landed; mechanism unverified). Next: apply middle-column-last sheet push order (panel-148 above neighbors), re-run all three seed rows + wave/window/opening/chip-cannon + full table, then chase feet pois-only via ice/grass shadow-palette dumps.
**Result.** F12b seed family localized, ticket stays OPEN for the fix. chip-poisseed 2237/334/70/52258 (k=52-61 2px stripe x197-202 y70-142 worst 334, plus k=9-14 feet residue 43->1px), chip-iceseed 2122/334/70/53458, chip-grasseed 2122/334/70/53458 (verify_rows PASS on wt/f12-seed 253198b, negatives not blind); canon sheet square-phase is one static image (tile 31 pal 1, OBJ VRAM byte-static) vs our 3-frame cycling, but canon tile-31 matches no poisarea.bin blob and no VRAM candidate (best 103/1024 mismatched) so no fix landed, branch wt/f12-seed kept unmerged, worktree removed. Worker worker (glm-5.3-flash, 78 turns, $0.098). No verifier (nothing landed; mechanism unverified). F12a minibomb 10/10->0/0 landed a607263 earlier. Next: find canon sheet pixels at the x=200 seam (OBJ/BG priority test), localize the feet component, decompose iceseed/grasseed from main.
**Result.** F12a minibomb family done, ticket stays OPEN for seeds. chip-minibomb 10/10->0/0 (verify_rows PASS 0/0/60/17158, landed a607263); wave/window/opening-isolated/chip-cannon PASS 0; opening integrated 72499/2691 pre-existing identical on baseline; full table: energbom/megenbom -26, iceseed/grasseed 2145->2122, bugbomb 8338->8280, vdoll/suprvulc/buster/chip-use unchanged, except chip-poisseed 2145->2237 (worst 334, +92) owned by seed follow-up. Worker worker-muse (muse-spark-1.3-contributor, 75 turns, $0.068). Verifier verifier-glm (glm-5.3-flash, 18 turns, $0.016): fix code-CONFIRMED, opening pre-existing CONFIRMED, canon OAM order UNCHECKED (probe flag failure), poisseed regression PARTIALLY CONFIRMED (totals attributable, trail colors unchecked). Next: seed family (poisseed/iceseed/grasseed) with its own canon OAM dump.
**Files.** src/battle.rs, assets/, tools/harness.py

**Next pass (human session, 2026-09-13 19:20).** Stamp this ticket OPEN after every family (PARTIAL/DONE close it and the human has had to re-open it twice); it ends when every chip row reads 0. Seeds are done (poisseed/iceseed/grasseed 0). Next families in order of size: bugbomb 8280, vdoll 628, then every other chip row the full table shows non-zero, one family per pass, with wave/window/opening/chip-cannon and minibomb/poisseed/iceseed/grasseed as canaries at 0.

**Decision (2026-09-13, human session): assets are in scope when the replacement is canon's own data.** The seed sheet's shadow (F12e: ours is a wider (16,16,16) ellipse baked into the sheet, canon's is black and narrower) is fixed by tracing canon's shadow path (the seeds throw a type-3 object 0x4f via off_80EB6F8/sub_80CE44E; the shadow path is untraced) and reproducing what canon draws -- tiles extracted from the canon ROM, or the shadow drawn as the separate object canon uses. Hand-drawn art that merely looks closer is not in scope.

**Why.** After F5b: SuprVulc 2464 / 177 / 113; the bomb, seed and VDoll rows 10 to 8338; EnergBom and
MegEnBom 19958 / 1871; the chip-family-0x15 rows 14740 to 73481. **Do:** take ONE family per run of
this ticket, smallest residue first (the rows at 10-8338), and bring its rows to 0; mark this ticket
PARTIAL with which family is done and leave it OPEN for the next family, until every chip row is 0.

- F16 DONE -- Oracle coverage: every harness row, not two. Oracle generalized to all 60 comparison rows (tools/oracle.py +138/-41, new tools/f16_slot_probe.py, export block untouched, landed ee6c494)
- F13b DONE -- `card` isolated via fixture rewire (follow-up to F13's verified negative). card 18486->0 via fixture rewire, landed 4b16fd7
- F14b PARTIAL -- `mettaur`: mercy-blink predicate bit 2 -> bit 1 (follow-up to F14's refuted negative). Blink experiment done, partial drop, landed 3e49236
- F15 DONE -- tiles/gauge: the one vblank frame, 208 px at k=7. tiles+gauge isolated 208->0, cursor unmoved 620802, landed 12a130a

### F25. Mettaur attack phase: enter canon's 106-frame attack cycle like canon does  *(PARTIAL -- 2026-09-13, mettaur 19698/1245/70 unchanged [neg 60824 not blind])*

**Result.** mettaur 19698/1245/70 unchanged (neg 60824 not blind); tiles/gauge iso 0, int 3865/678/8 (neg 15891); popup 60614/1842/80; mm_timer 70/70, enemy_anim k=61 1/70; verifier: routine identity CONFIRMED, attack path matches canon CONFIRMED (period 106, pose 63, strike entry+38), residual = uniform +1 phase offset CONFIRMED-measured, intro-gate attribution UNCHECKED, wave 44v45 UNCHECKED; branch wt/f25-mettaur-attack c7a5ce7 kept unmerged; worker muse-spark-1.3-contributor 86 turns $0.161, verifier GLM
**Files.** src/actor.rs, src/ai.rs

**Why.** Three rows wait on the same missing behavior -- our Mettaur idles while canon's attacks. F17's Result: `mettaur` 19698/1245/70/60824 unchanged pixels, oracle `mm_timer` 70/70 with first divergence `enemy_anim` k=61 (2/70); SWING shows IDLE on the 64th executor tick per canon sub_8109DEC (asm31.s:170830-170848, SWING_POSE=0x40-1 derived); mercy seed/rate/blink predicate settled and untouched. F20b's Result: `tiles`/`gauge` integrated 25979/3282->3865/678/8 (negative 15891 not blind), isolated still 0/0/8, via the HUDMATCH descriptor corrected to canon-peeked BattleObject panel positions (MM (2,2) @0x0203a9c2/3, enemy (5,2) @0x0203ab72/3); the residual 3865 is canon's Mettaur mid-attack (CurState/CurAction 0x04/0x0b) against ours idle -- F17's family, not the fixture. F19's Result (TODO_ARCHIVE.md): `popup` 107511/1348/80/108815 -> 60614/1842/80/60806 (-44%, fixture only, landed c2c24e6); subject center band 0, enemy box 51991->6081, HUD bar 55520 unchanged. Canon anchors: both sides run the same 106-frame Mettaur attack cycle (canon attack animations start at canon frames 32, 138; ours at battle frames 95, 201, 307, 413 -- TODO_ARCHIVE.md F2); enemy slots 0x0203aa88/0x0203ab60/0x0203ac38 per AGENT_GUIDE.md, BattleObject offsets per reference/bn6f/include/structs/BattleObject.inc.
**Do, in order.**
1. Start in `tools/worktree.sh f25-mettaur-attack`. Baseline `python3 tools/harness.py --only mettaur,tiles,gauge,popup --no-gallery` (must read mettaur 19698/1245/70 with negative 60824 not blind, tiles/gauge integrated 3865/678/8 with negative 15891 not blind, popup 60614/1842/80), plus `tools/oracle.py mettaur` (must read `mm_timer` 70/70, first `enemy_anim` divergence k=61) and `tools/diffmask.py` region splits (tiles/gauge OBJ cells, popup HUD bar), measured.
2. Drive our Mettaur into canon's attack cycle: find canon's Mettaur attack-timing/animation routine in `reference/bn6f` and cite it, fix `src/` (attack-phase entry, frame-95-equivalent timing, attack animation/CurState-CurAction) only, measured on the same oracle fields (first `enemy_anim` divergence at/past k=61, attack-cycle phase vs canon's 106-frame period) and the same pixel frames and regions.
3. Re-run `mettaur`, `tiles`, `gauge`, `popup`, `wave`, `window`, `opening`, `chip-cannon` and the full table -- nothing may get worse, and a row that does is reported with its numbers, measured.
**Rules.** `src/` enemy-attack path only; mercy seed/rate/blink predicate, HUDMATCH positions, and popup fixture untouched; no allowlist change; no alignment or region change except by measured event (F2's rule).
**Measure and report.** Rows `mettaur`, `tiles`/`gauge` (both variants), `popup` before/after (total/worst/frames) on the identical scripts and windows, oracle `mm_timer` match count and first `enemy_anim` divergent frame before/after, tiles/gauge OBJ-cell and popup HUD-bar splits before/after, full-table deltas. **Acceptance:** `mettaur` 0/0/70 (negative not blind); `tiles`/`gauge` integrated at or below 3865 decomposed by element with frames and regions (0 if the attack phase lines up); `popup` HUD bar 55520 decomposed, enemy-box element toward 0; isolated variants still 0; nothing worse.
**Coordinator:** `verify_rows` on every row the report names; the verifier only for claims beyond harness lines (routine identity, attack-phase attribution); a wrong-guess PARTIAL gets one follow-up; a second miss marks it BLOCKED and moves on.

### F25b. Mettaur +1 attack-phase offset: attribute it, fix only inside the attack path  *(BLOCKED -- 2026-09-13, attack path pixel-perfect at true phase [offset 204: enemy 0px, MegaMan 30864])*

**Result.** attack path pixel-perfect at true phase (offset 204: enemy 0px, MegaMan 30864); entries canon 31/137/243 vs rust 95/201/307 = exact diff 64 all three (intro-gate hypothesis REFUTED); wave flight 44 vs canon 45 confirmed (shot.rs, out of scope) gives hit diff 63 vs enemy 64 -- incommensurate phases, no in-scope fix; offset 203 unique sharp minimum (19698); verify_rows PASS all MATCH on e708b3b; no verifier (nothing builds on it); second miss, objective BLOCKED; worker muse-spark
**Files.** src/actor.rs, src/ai.rs

**Why.** F25's verified Result (PARTIAL, branch wt/f25-mettaur-attack c7a5ce7 kept unmerged): attack entry now canon-shaped (act 0x0b/anim 0 one frame, pose 63, strike entry+38, period 106; routine identity sub_8109DEC/sub_8109E4A + Decide sub_810A126 CONFIRMED by verifier) but mettaur 19698/1245/70 unchanged, enemy_anim still diverges k=61 (canon 201=0, rust=1). Verifier measured the residual as a uniform +1 attack-phase offset present from the very first attack (canon entries at 31/137, ours shifted +1 throughout). UNCHECKED: whether the +1 comes from the intro-gate (attack-1 has no canon counterpart) or from wave flight 44 vs canon 45 (src/shot.rs pixel claim unverified), and the mm_timer counterfactual.
**Do, in order.**
1. Start with `bash tools/worktree.sh f25b-phase`, then `git merge wt/f25-mettaur-attack` (the verified attack-entry rework, kept unmerged). Baseline mettaur, tiles, gauge, popup there (19698/1245/70, tiles/gauge integrated 3865/678/8, popup 60614/1842/80) plus oracle mm_timer 70/70, enemy_anim k=61.
2. Attribute the +1 phase: trace where our first attack entry's +1 vs canon 31 comes from (intro-gating in ai.rs/actor.rs vs wave-flight timing), measuring entry frames on both sides with watches on this row's own captures. Fix it only if the cause is inside src/actor.rs, src/ai.rs; wave timing (src/shot.rs) may be measured with existing tools but NOT edited. If the cause is the intro/fixture with no canon counterpart, report the measurement and stop (precise negative).
3. Re-run `mettaur`, `tiles`, `gauge`, `popup`, `wave`, `window`, `opening`, `chip-cannon` and the full table -- nothing may get worse, and a row that does is reported with its numbers, measured.
**Rules.** src/actor.rs, src/ai.rs only; no shot.rs/fixture/allowlist/alignment change; no region change except by measured event (F2's rule); captures one at a time.
**Measure and report.** First-entry frames both sides before/after, enemy_anim first-divergence before/after, wave-flight frames both sides (measured, not edited), rows before/after, full-table deltas. **Acceptance:** `mettaur` toward 0 via the phase fix landing inside the attack path; if the +1 is intro/fixture-side, a measured attribution with the entry-frame traces and STOP (a second miss marks the objective BLOCKED).
**Coordinator:** `verify_rows` on every row the report names; the verifier on the phase-attribution claim (it must confirm the +1 source); a second miss marks it BLOCKED and moves on.

### F24. `cursor`/`result` backdrop: port canon's per-scanline BG scroll (the BGScrollCB HBlank raster callback) into src/  *(NEGATIVE -- 2026-09-13, premise refuted: canon battle HBlank scroll callback is nullsub_38 no-op [22/22 backdrop types, verifier CONFI)*

**Result.** premise refuted: canon battle HBlank scroll callback is nullsub_38 no-op (22/22 backdrop types, verifier CONFIRMED in disassembly); sole scroll is per-frame Diagonal3to2 (-0.5/-0.25 px/f) already implemented in backdrop.rs (verifier CONFIRMED); zero edits, tree clean; cursor HEAD 620914@226 / 780032@237 (x<112=112 single frame), result 102547@21; FOUND: F12 landing 54abe87 moved cursor 620802->620914 (+112 one frame, verifier bisected, F18d/F21d exonerated) -- owned by next cursor ticket; worker muse-spark 44 turns $0.018, verifier GLM
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

### F25c. `mettaur`: the shockwave's flight is 44 frames, canon's is 45 -- the one frame between the enemy's phase and MegaMan's *(PARTIAL -- 2026-09-13, mettaur 19698/1245->4265/800/70 [neg 45788 not blind], oracle 10/10 fields 70/70 FIRST-DIVERGENCE-none)*
**Result.** mettaur 19698/1245->4265/800/70 (neg 45788 not blind), oracle 10/10 fields 70/70 FIRST-DIVERGENCE-none; verifier CONFIRMED canon citation (sub_80C6B64 present-at-init asm31.s:31461-31496, HP113->114, flight 45) and fix (hop_pending latch, wave 0/buster 3172/cannon 0, no fitted const) and residual distribution (exact 8 frames k=0,1,6,11,17,22,63,68, enemy_anim clean); partial gaps: T3 Timer-field mapping inferred, inbox=0 box-unchecked; acceptance 0 unmet -> branch wt/f25c-wave-flight 6b28e9b KEPT unmerged; third consecutive non-DONE on mettaur objective -> no follow-up per two-in-a-row rule; worker + verifier GLM Landed on main by the human session as a verified partial (land.sh, verify_rows on mettaur and six canaries); the 8-frame spray residue is F25d.
**Files.** src/shot.rs, src/ai.rs, tools/harness.py

**Why.** F25b measured, and verify_rows reproduced, that our Mettaur's attack path is pixel-perfect at
its true phase: at offset 204 the enemy differs by 0 px over the whole row while MegaMan reads 30864;
at the row's offset 203 MegaMan pairs and the enemy is one frame off (19698, the unique sharp
minimum). Attack entries are canon 31/137/243 vs ours 95/201/307, exactly 64 apart all three times,
so the intro-gate story is refuted. The one frame is the shockwave: ours reaches MegaMan 44 frames
after launch, canon's 45 (F25b confirmed it in src/shot.rs and declared it out of that ticket's
files). That is not a block, it is the fix. shot.rs already notes that shots are stepped before the
actors ("PRE-TICKED", src/shot.rs:145-147), which is the kind of ordering that costs one frame.

**Do, in order.**
1. Start in `tools/worktree.sh f25c-wave-flight`. Baseline mettaur (19698/1245/70 at offset 203,
   negative 60824 not blind) and wave, window, opening, chip-cannon, field, result, plus tiles/gauge
   integrated (3865) and popup (60614).
2. Measure canon's shockwave frame by frame from the Mettaur's launch to the hit: the wave object's
   slot, x position and timer per frame (probe.py watch on both sides, same launch frame), and the
   frame MegaMan's HP drops and his mercy counter starts. Do the same on ours. Name the frame where
   the two diverge (spawn delay, hop cadence, hit-check order) and cite canon's routine for that step.
3. Make ours identical there (src/shot.rs, or src/ai.rs if it is the launch), with a provenance
   comment. Then re-align the mettaur row only by the measured event (the enemy's attack entry and
   MegaMan's hit now at the same offset), never by score.
4. **Acceptance.** mettaur 0/0/70 (negative not blind) at one offset for both the enemy and MegaMan;
   wave, window, opening, chip-cannon, field, result 0 or unchanged; tiles/gauge integrated and popup
   re-measured and reported (they wait on the same phase); full table nothing worse. If the wave row
   moves, its per-frame split is the report.

**Rules.** src/shot.rs, src/ai.rs and the mettaur row's Align note only; no allowlist change; no fitted
constant (the 45 must come from canon's routine, cited). **Coordinator:** verify_rows on every row
named; the verifier on the canon citation and the "same offset for both" claim; one follow-up at most.

### F25d. `mettaur`: the departure spray on 8 frames, 4265 px, content not timing  *(DONE -- 2026-09-13, mettaur 4265/800/70 -> 0/0/70 [neg 41734 not blind], oracle 10/10 fields 70/70)*

**Result.** mettaur 4265/800/70 -> 0/0/70 (neg 41734 not blind), oracle 10/10 fields 70/70; cause: hop-spawned shockwave segments were created with the sprite's fresh flag set and skipped their first update, so every animation-frame change and despawn on them ran one frame late (the eight residue frames k=0,1,6,11,17,22,63,68 were exactly those changes; tiles and palette bytes byte-identical at phase-aligned pairs); fix: one self.player.update() after the spawn in Shot::update per canon t3_0x16_80C6B40 (asm31.s:31413-31420, state 0 sub_80C6B64 loads the sprite then falls through to object_updateSprite the same frame); wave/window/opening/chip-cannon/result unchanged, field isolated 0, field integrated 305258->305263 (+5 px on one scanline y=0 of one frame, ROM-layout timing sensitivity, ticketed as F30); landed by the human session via land.sh (verify_rows PASS on 7 rows); Claude Opus agent, 73 tool calls, 16 min.
**Files.** src/shot.rs, src/spr.rs, assets/

**Assigned to a Claude agent (2026-09-13 20:20, the user's Claude quota window).** pi's loop skips any status but OPEN.

**Why.** F25c fixed the one-frame hit (shockwave flight 44 -> 45 per canon sub_80C6B64) and landed on
main as a verified partial: mettaur 19698/1245 -> 4265/800 at offset 203, the oracle's ten state
fields match 70/70, and the residue sits on exactly eight frames (k=0,1,6,11,17,22,63,68), all outside
the enemy box, at the same post-hit phase on both sides. So the shockwave's departure spray around
MegaMan differs in content, not timing (F25c's verified reading). That is the last thing between the
mettaur row and 0.

**Do, in order.**
1. Start in `tools/worktree.sh f25d-spray`. Baseline mettaur 4265/800/70 (negative 45788 not blind).
2. On those eight frames dump both sides' OAM for the spray objects (tile index, palette, position,
   size, flip) and the tile bytes they point at, and say which differs: the art (asset), the palette,
   or the sequence (which sprite on which frame). Cite canon's animation script for the spray (the
   shockwave object's own anim, the family around sub_80C6B64), with file and lines.
3. Fix it at the source: art extracted from the canon ROM into assets/, or the sequence in src/,
   with a provenance comment. Never hand-drawn art.
4. **Acceptance.** mettaur 0/0/70 (negative not blind); wave, window, opening, chip-cannon, field,
   result 0 or unchanged; tiles/gauge integrated and popup re-measured and reported; nothing worse.

**Rules.** No alignment or allowlist change; src/shot.rs, src/spr.rs and assets/ only.
**Coordinator:** verify_rows on every row named; the verifier on the canon citation; one follow-up.

### F27. `popup`: the OBJ-layer element canon draws over the enemy and ours does not (55520 px)  *(CLAUDE -- 2026-09-13)*

**Files.** src/hud.rs, src/hudtiles.rs, assets/ (new files only), tools/harness.py (the popup row's note only)

**Why.** popup 60614/1842/80 (negative 60806 not blind). F19 left it at: subject band 0, enemy box 6081,
and 55520 px in the region it called the HUD bar that is canon-only OBJ (capturing both sides with
`--disable-obj` removes it). F20 showed the integrated tiles/gauge OBJ residue was object positions;
this one is an object we do not draw at all. Identify it by OAM first: canon's object slot, tiles,
palette, position and visibility per frame over the 80 frames, and the routine that spawns and
drives it (cite file:line). Then implement it in ours from canon's data: tiles extracted from the
canon ROM into assets/, timing and position from the routine, never hand-drawn or fitted.
**Acceptance.** the popup row's HUD-bar region 0 on all 80 frames and the popup total reported
(enemy box 6081 may remain, it is F28's); wave, window, opening, chip-cannon, field, tiles, gauge 0;
full table nothing worse.

### F28. Mettaur: its first attack starts 64 frames after canon's, relative to battle start  *(PARTIAL -- 2026-09-13, premise refuted as a defect, two real frames fixed, landed)*

**Result.** premise refuted as a defect, two real frames fixed, landed. The 64 = 34 + 30: canon's pausedwithcannon.state resumes a Mettaur already spawned and mid-hop (slot 0x0203ab60, not 0x0203aa88 which is empty; CurAction 0x0a frames 0-27, 0x08 28-30, 0x0b from 31) while ours runs from init (0x00 to battle 61, 0x09 from 62, 0x0b at 95): 34 frames of scene difference plus canon's one-time 30-frame post-spawn wait an already-spawned Mettaur never runs; a constant the alignment absorbs. Real defects: sub_8109CBC (asm31.s:170665-170672) exits its wait when the subtract goes negative so an arming of 0x1e is 31 frames (ours 30), and sub_810A004's Param4 branch (asm31.s:171296-171305) spends its own frame arming the wait (ours was born inside it); fixed in src/ai.rs (param4 its own field, born in RowCheck, the waiter owns its last frame); our entries now battle 97/203/309. Alignment by event: mettaur offset 203 -> 205 (V 204/206 = 46297/37873 identical shape), wave 345 -> 347 (346/348 = 4800/3840); on the branch mettaur 4265/800/70 (pre-F25d base), wave 0/0/90, tiles/gauge integrated unchanged 3865/678/8 (neg 15891), isolated 0/0/8, popup unchanged, field integrated +5 (305258->305263, worst same, enemies:0 row). Why tiles/gauge integrated cannot be 0 yet: HUDMATCH clears FLAG_OPEN_WINDOW and src/battle.rs:2107-2110 re-arms gauge_pause every frame with the gauge full while only the open-window branch decrements it, so our battle freezes from battle 62 and the Mettaur never leaves CurAction 0x09; the whole 3865 is its idle sprite vs canon's swing (bbox (164,68)-(204,111), every other pixel 0); the one-line fix alone makes the row worse (16130) because by battle 427 our MegaMan has taken two shockwave hits (HP 60->50 at 177, ->40 at 389) and blinks while canon's holds 60 unhit: the fixture must seed MegaMan's HP/mercy like it seeds the backdrop and gauge (F28b). popup's rust side has no enemy at all (enemies:0) while canon's is deleted and dissolving: the enemy-box residual is 7 frames k=0..6, not the tiles/gauge phase. Claude Opus agent, 101 tool calls, 32 min, 247k tokens.
**Files.** src/ai.rs, src/fixture.rs, tools/harness.py (the mettaur/tiles/gauge Align only, by measured event)

**Why.** F25b measured the attack entries: canon at battle frames 31/137/243, ours at 95/201/307,
the same 106-frame period on both sides and exactly 64 later on ours all three times. The mettaur
row hides it by pairing attack indices (offset 203); the gauge-aligned integrated rows do not:
tiles/gauge integrated 3865/678/8 (negative 15891 not blind) is canon's Mettaur mid-attack
(CurState/CurAction 0x04/0x0b) against ours idle, and it is part of popup's enemy box (6081) and of
windowclose's remainder. Find where the 64 comes from by measurement, not by guess: canon's Mettaur
AI timer from battle init (enemy slot 0x0203aa88, its AI data and timer fields; the routine that
seeds the first attack delay; whether the intro banner gates it) against ours, on the same battle
frame numbering; or a fixture difference in when our battle starts relative to the gauge. Fix at the
source with the citation.
**Acceptance.** tiles/gauge integrated 0/0/8 (negative not blind); mettaur at or below 4265 on its
event-locked alignment (if the event moves, re-sweep the band and report the new unique minimum
and the event that names it); popup's enemy box reported; wave, window, opening, chip-cannon, field
0; full table nothing worse.

### F29. `windowclose`: decompose the remaining 648948 by layer and frame, fix what lives in the window  *(PARTIAL -- 2026-09-13, windowclose 648948/27391/40 -> 407778/11879/40 [neg 534875 not blind], landed)*

**Result.** windowclose 648948/27391/40 -> 407778/11879/40 (neg 534875 not blind), landed; cursor exactly 620802/6884/170 unchanged though it shares CUSTMATCH_ROW; full table otherwise identical, field integrated -5. Decomposition at offset 253: BG0 0, BG3 0 (F18-F18d), BG2 field 266412/18864 on k=1..19 = canon's 15-px camera pan driven from inside the window's slide routine (sub_8026BF4 adds dword_8026CC8=0x18000 to Camera+0x34 per slide-out call, asm03_0.s:1099-1104, constant :1141-1142, slide-in subtracts :964-969) with an arithmetic shift (floor), ours ten frames late with ceil -> fixed in src/battle.rs (pan on the slide calls via Custom::is_closing(), div_euclid floor; FIELD_SLIDE/FIELD_SLIDE_STEP now derived = 10 x 0x18000), BG2 0 on all 40 frames; OBJ 97644 = MegaMan's panel (CUSTMATCH_ROW megaman_col/row 3,2 -> 2,3 per canon's BattleObject PanelX/Y +0x12/+0x13, -36620) + the Mettaur's phase (14228, flat 205/frame from k=10) + HP boxes on k<10; BG1 backdrop 877602 = a constant (20,10) px scroll-phase translation on all 40 frames because the fixture seeds no backdrop phase (F26b: per-row seed from canon's counters 0xffff9ad8/0xffffcd6c and GFX entry 25 at canon frame 81; a shared seed takes cursor to 1222398) plus the odd-frame lsr-vs-floor rounding backdrop.rs:278-283 predicts. Trap recorded: -x.div_euclid(2) parses as -(x.div_euclid(2)) and reproduces the old rounding on odd frames. Remaining 407778 = BG1 phase + Mettaur phase. Claude Opus agent, 103 tool calls, 33 min, 414k tokens.
**Files.** src/custom.rs, src/hudtiles.rs, src/field.rs, tools/harness.py (the windowclose row's note only)

**Why.** windowclose 648948/27391/40 after F18-F18d fixed the close transients; the slide (k0-9) is
0 and the rest is the forty frames as the battle resumes behind the closing window, which nobody has
decomposed. Capture both sides per layer (`--only-bg N`, `--disable-obj`, identical on both sides)
and produce a per-frame table layer x px x bbox; name the mechanism for each non-zero layer with a
canon citation: the Mettaur's phase (F28's 64 frames), the backdrop's scroll and art phase, the HUD,
the window's own tiles and scroll. Fix what lives in your files; for causes in files other workers
hold (src/backdrop.rs, src/actor.rs, src/battle.rs, src/shot.rs, src/ai.rs) report the exact change
as a proposal with the measurement behind it.
**Acceptance.** the decomposition table with citations; every fix verified on windowclose plus
wave, window, opening, chip-cannon, field; full table nothing worse.

### F31. `buster`: 3172 px over 32 frames, blocked twice, a fresh measurement  *(PARTIAL -- 2026-09-13, the row is vacuous: canon's OAM over the window holds four idle-MegaMan objects plus, from canon frame 164, th)*

**Result.** the row is vacuous: canon's OAM over the window holds four idle-MegaMan objects plus, from canon frame 164, the battle-result mark (16x16 tile 0x200 pal 11 prio 0 sliding to (37,21)): 163 + 17x177 = 3172 = the whole row, on k=14..31; canon's scripted B at 150/151 never fires (CurState/CurAction/CurAnim/HP 04/08/00/60 and the sequencer 0x0400000c constant over canon 145..186, F10's 0x0C delivery wall re-measured) and our ZERO_ENEMY fixture never resolves so we never draw the mark; the alignment 122 is the first of an 8-wide plateau (122..129 all 3172; 90..105 all 13959; the event-locked offset 100 reads 13959/794/32); our buster pose (rust 111..129) lies entirely outside the compared window 130..161. Landed: canon's t3_0x0_80C4E58 (asm31.s:27690-27697, off_80C4E70 :27703, sub_80C4E7C sprite_load :27725-27727) shows a shot's first animation frame on its spawn frame, ours ran a frame late (fresh player's first update eaten, src/spr.rs:336-343): the pre-tick now lives once in Shot::new (removed from shockwave(), behaviour-neutral for every current row; full table byte-identical both ways, field integrated -5). The plain buster builds no Shot at all (Update::Strike charged:false is a hitscan). Measured against a canon side that fires (Start@10,B@30,B@31 in the 0x08 window): pose 25 frames = 5 fire ticks (sub_80EB450 asm31.s:108680-108691) + byte_80209CC[Rapid*6+min(free panels,5)] (sub_800FAF6 asm00_2.s:1944-1990, dat01.s:146) = 5+0x14 vs ours 19; barrel at pose+0 vs ours +2 (BUSTER_ARM_DELAY); muzzle at pose+1 vs +4 and our FX double-ticked on its spawn frame (battle.rs:2623 fx.update() plus the effects loop); both objects live until object_exitAttackState (sub_80EB502 asm31.s:108712-108722) vs our fixed 18/7 frames. Next: F31b re-cuts the row around a canon side that fires and lands those four. Claude Opus agent, 69 tool calls, 20 min, 195k tokens.
**Files.** src/shot.rs, tools/harness.py (the buster row's note only)

**Why.** buster isolated reads 3172 px over 32 frames and has been BLOCKED since F10/F10b (two
misses: read both Results in TODO_ARCHIVE.md before anything else, and F1's, which changed the hit
frame in shot.rs). F25d just showed the shape of these residues on the mettaur row: not art, not
timing constants, but one object updating a frame late because our object lifecycle differs from
canon's dispatcher (spawn-frame update). Measure the buster the same way: both sides' OAM for the
shot and MegaMan per frame over the 32 frames, the tile bytes at phase-aligned pairs, the frame the
shot spawns, moves and despawns, and the frame the enemy reacts (HP at 0x0203aa88+0x24, state +8/+9);
cite canon's buster object routine and MegaMan's shooting state in reference/bn6f (file:line).
**Acceptance.** buster 0/0/32 (negative not blind) with no alignment change except by a measured
event; wave, window, opening, chip-cannon, field, mettaur 0; full table nothing worse. src/actor.rs
is held by other workers: a change needed there is reported as an exact proposal, not made.

### F30. `field` integrated: a one-scanline write lands on either side of a VBlank boundary depending on ROM layout  *(PARTIAL -- 2026-09-13, layout race 10585px [[8,10585]] -> 0 over 200 frames across ROM layouts [worker])*

**Result.** layout race 10585px [(8,10585)] -> 0 over 200 frames across ROM layouts (worker); verifier CONFIRMED root cause sources (Blend::commit BLDCNT/BLDY, agb early-return wait, canon main.s frame-sync + ProcessGFXTransferQueue) and fix faithful (54 lines, no-op on fitting frames); combination: field/wave/window/opening/chip-cannon/result/mettaur0/popup5094/windowclose407778/buster3172 preserved, cursor 620802->620914 (+112); verifier: one-frame scanline-band diff CONFIRMED, x<112-locality REFUTED, spin-only-cause YES, better-vs-canon UNMEASURED; branch wt/f30-scanline c64b68a KEPT unmerged; worker muse-spark 97 turns $0.078, verifier GLM
**Files.** src/main.rs, src/field.rs

**Why.** F25d measured that two builds differing only in ROM layout (545824 vs 553900 bytes, a
one-statement change elsewhere) differ on field's own rust side at capture 121 by 39 px, all on
scanline y=0, x 67..237, and at the boot frame; field isolated stays 0 but field integrated moved
305258 -> 305263. A write that reaches VRAM or a register during that scanline's draw is sensitive
to CPU time before VBlank: that is an engine-timing bug of ours (canon's driver copies during
VBlank), not a canon difference, and it will bite every integrated row. Find the write (watch VRAM
and the BG registers with mgba_capture --watch-write on that frame), move it under VBlank the way
canon's driver sequences it (cite), and show the two builds' captures identical on every frame.
**Acceptance.** field's rust side byte-identical between two ROM layouts (pad the ROM to prove it)
on all 170 captured frames; field isolated 0; field integrated not worse; wave, window, opening,
chip-cannon 0.

### F30b. VBlank re-sync spin: is cursor frame 0 better or worse, and gate the spin accordingly  *(BLOCKED -- 2026-09-13, spin proven no-op on cursor [6 reps 620802 bit-identical, F30 +112 = layout jitter])*

**Result.** spin proven no-op on cursor (6 reps 620802 bit-identical, F30 +112 = layout jitter); gate KEEP ungated; layout race NOT 0: with spin 6704px@capture8 (frame-121 fixed 85->0, battle-frame-0 remains; masked-VBlank hypothesis UNCONFIRMED, new-mechanism work out of scope); field-int +12 = layout jitter (spin on/off bit-identical 3x); verify_rows PASS 10/10 MATCH on e858b42; no verifier (no follow-up per two-in-a-row: F30 PARTIAL->F30b); branches kept unmerged; worker muse-spark
**Files.** src/main.rs

**Why.** F30's verified Result (PARTIAL, branch wt/f30-scanline c64b68a kept unmerged): the layout race is fixed (10585px -> 0 over 200 frames across ROM layouts; root cause and fix-faithfulness both verifier-CONFIRMED), but the combination moves cursor 620802 -> 620914 (+112). The verifier measured the diff as ONE compared frame (frame 0), a full-width scanline band at y~=40 -- the artifact class the spin targets -- and confirmed the 54-line spin is the only code delta, but better-vs-canon was UNMEASURED (one run per side; emulator nondeterminism not excluded) and the x<112-locality story was REFUTED.
**Do, in order.**
1. Start with `bash tools/worktree.sh f30b-spin-gate`, then `git merge wt/f30-scanline` (the verified fix, kept unmerged). Baseline cursor (620802/6884/170/728447 on main) and field isolated/integrated there.
2. Measure cursor frame 0 against CANON with and without the spin (same-index rust-vs-canon diff on frame 0, repeated runs for nondeterminism): if the spin makes frame 0 better-or-equal vs canon, say so with numbers and keep it; if worse, gate the spin (e.g. only where a layout-divergence is possible, or fix the overrun source on cursor's frame 0) and re-measure.
3. Re-run cursor, field, wave, window, opening, chip-cannon, result, mettaur, popup, windowclose -- nothing worse than main; re-prove the layout-race 0-over-200-frames with the gate in place.
**Rules.** src/main.rs only; no allowlist/alignment/fixture change; no fitted constant; captures one at a time.
**Measure and report.** Cursor frame-0 vs canon with/without spin (repeated), gate decision with numbers, layout-race proof, rows before/after, full-table deltas. **Acceptance:** layout race still 0 AND cursor at or below 620802 with the spin in place; else a measured better-vs-worse verdict and STOP.
**Coordinator:** `verify_rows` on every row the report names; the verifier on the better-vs-worse claim (it must measure it).

### F27b. Emotion window: show it on canon's rule (HUD element mask bit 14, from HUD init to HUD teardown), not "while an enemy is alive"  *(DONE -- 2026-09-13, popup 60614/1842/80 -> 5094/1148/80 [neg 5286 not blind], the x2-45 y18-33 emotion-window box 0 on all 80 fram)*

**Result.** popup 60614/1842/80 -> 5094/1148/80 (neg 5286 not blind), the x2-45 y18-33 emotion-window box 0 on all 80 frames; the residual 5094 is the Mettaur's dissolve (F28). Canon's rule implemented: the emotion window is battle-HUD element 14 (mask dword_20352C0, sub_801BEE0 asm00_2.s:25540-25563, draw sub_801CDEC :27554-27583), cleared with elements 0/1/4/10 by sub_80081A4 -> sub_801BED6(0xE4C53) (asm00_1.s:10617-10621) on the frame the banner sequencer enters the RESULT countdown 0x0C, measured on the real ROM with --watch-write (frame 47 seq 0x0C, frame 48 mask 0x4497->0x0084 at lr 0x080081B9); canon holds the window through the enemy's death and its 47-frame dissolve, ours dropped it at the death. src/battle.rs: hud_live set at HUD init, cleared where over fires (same event in this build), draw gate hud_live && no popup && no fade; src/fixture.rs FLAG_HUD_LIVE bit 6 (peeked) because popup and the 43 chip rows share one zero-enemy descriptor while their canon captures sit on opposite sides of the teardown (popup mask 0x4497 on all 125 frames, afterdissolve 0x8084 on all 47), so only the descriptor can say which; src/emotion.rs LEFT/RIGHT provenance derived from sub_801CDEC. cannon/chip-cannon/chip-invisibl/mettaur/opening/tiles/gauge/field/wave/window/card/banner/cursor/windowclose/result unchanged. Remaining: our end sequence fires over at the last enemy's defeat where canon reaches the RESULT countdown 47 frames later after the dissolve (F32); the teardown models element 14 only. Claude Opus agent, 98 tool calls, 27 min, 380k tokens.
**Files.** src/battle.rs (the emotion-window gate and the teardown only; pi's F12 worker edits other parts of battle.rs), src/emotion.rs, src/fixture.rs (only if a fixture rule must change), tools/harness.py (the popup row only)

**Why.** F27 identified popup's 55520 px: two OBJs at (0,18) 32x16 tile 0x3b4 and (32,18) 16x16 tile
0x3bc, palette 12, priority 2, on all 125 canon frames -- the emotion window, which src/emotion.rs
already draws from assets/emotion.bin with byte-identical tiles and palette. Canon draws it while
bit 14 of the battle-HUD element mask (dword_20352C0, dispatched by sub_801BEE0 asm00_2.s:25540-25563,
draw sub_801CDEC asm00_2.s:27554-27583) is set: 0x4497 on every popup frame (the enemy goes
ALIVE -> DELETE_ENEMY and the window stays), 0x8084 on every frame of the afterdissolve route (HUD
torn down, RESULT countdown). Ours drops it the frame the last enemy is defeated (battle.rs:3682's
`fighting` predicate), which is wrong in a real battle too. F27 measured a fixture-flag workaround
(popup 60614 -> 5094, box 0/80, cannon 0, chip rows unchanged, field integrated +5) and did not land
it because the mechanism is the gate itself.
**Do.** Find when canon clears bit 14 (the caller of sub_802A0F8's hide, asm03_0.s:8317-8333, on the
transition into the RESULT countdown) and measure that frame on a canon capture where the last enemy
dies (the result fixture); make ours hide the window at the same event, and show it from HUD init.
If the zero-enemy popup fixture then tears down at once, fix the fixture's semantics (an empty
enemy list is not a victory; canon never has one) rather than adding a flag; the flag from F27's
proposal is the fallback only if the fixture cannot express canon's situation otherwise.
**Acceptance.** popup at or below 5094 with the x2-45 y18-33 box 0 on all 80 frames (the rest is
F28's Mettaur dissolve); cannon 0 and every chip row unchanged (their canon mask has bit 14 clear, so
ours hides at the same frame -- measure the hide frame on both sides on one chip row); result,
field, wave, window, opening unchanged or 0; nothing worse.

### F26. `cursor`: decompose the x>=112 residue by layer and name each layer's mechanism  *(PARTIAL -- 2026-09-13, layer table delivered: BG0/BG2/BG3 0, BG1 scroll rates match [verifier CONFIRMED counters+zeroing+rate], BG1 a)*

**Result.** layer table delivered: BG0/BG2/BG3 0, BG1 scroll rates match (verifier CONFIRMED counters+zeroing+rate), BG1 art citations CONFIRMED; verifier FLAGS OBJ arithmetic (689572>620802 total, must be redefined) and marks UNCHECKED: 2-frame art lead, Mettaur kind-byte/variant, portrait box-x, MegaMan panel; no src change, tree clean; worker muse-spark 38 turns $0.021, verifier GLM
**Files.** src/backdrop.rs, src/actor.rs, tools/diffmask.py, tools/probe.py

**Why.** F24 refuted the raster theory: canon's battle HBlank scroll callback is a no-op (nullsub_38 for
all 22 backdrop types, verifier confirmed in the disassembly) and the per-frame diagonal 3:2 scroll is
already in backdrop.rs. So F22b's two "coexisting translations" (116,16) and (52,48) are two different
things on two layers, not one mechanism. cursor reads 620914/.../170 at offset 237 (F12's landing
54abe87 added +112 on one frame; F18d/F21d exonerated); x<112 is 0 on every frame (walk, bracket,
blink, names, pictures, deck exact). Everything left is x>=112: the battle behind the custom window
(backdrop, panels, Mettaur, HP). Nobody has measured which layer carries what.

**Do, in order.**
1. Baseline cursor at offset 237. Capture both sides with each layer alone (`--only-bg N` and
   `--disable-obj`, identical on both sides) and diff per layer per frame: report which layers carry
   the residue and each one's per-frame shape (px, bbox, first differing frame).
2. For each non-zero layer, find its mechanism by measurement, not by fit: for the backdrop BG, the
   scroll (canon's counters at 0x02009690/0x02009694 vs our scroll state, per frame) and the art
   phase (which tile set is uploaded on which frame, the step counter); for OBJ, the Mettaur's
   CurState/CurAction and animation frame vs ours (F25/F25b's one-frame phase) and the HP/HUD
   objects; for the panel BG, the tilemap content. Name the first differing frame and field per
   layer and cite canon's routine.
3. If a layer's cause is a small fix in src/ with a canon citation, make it and measure; otherwise
   stop with the decomposition. **Acceptance.** a table layer x (px, first differing frame, mechanism
   with canon routine); the +112 one-frame change from 54abe87 attributed to its object and push
   order; any src/ change verified on cursor, wave, window, opening, chip-cannon, result and field
   with nothing worse.

**Rules.** No alignment change except by measured event (offset 237 stands until a watch names a new
event frame); no allowlist change; no seed or scroll refit. **Coordinator:** verify_rows on every
row named; the verifier only if src/ changes or a canon routine is cited.

### F28b. tiles/gauge integrated to 0: unfreeze the HUDMATCH battle and seed MegaMan's mid-battle state; then popup's dissolving enemy  *(DONE -- 2026-09-13, tiles/gauge integrated 3865/678/8 -> 0/0/8 [neg 12843 not blind], isolated 0/0/8 unchanged)*

**Result.** tiles/gauge integrated 3865/678/8 -> 0/0/8 (neg 12843 not blind), isolated 0/0/8 unchanged; popup 5094/1148/80 -> 0/0/80 (neg 1288 not blind); mettaur 0/0/70, wave/window/card/banner/opening-iso/cannon/warp-iso/field-iso 0 unchanged, field integrated 305263->305251 (worst same, F30), everything else byte-identical; full table rollup PASS. (1) src/battle.rs: gauge_pause re-armed only when open_window_allowed(): canon's fight state opens every frame with UnpauseBattle (sub_800855E asm00_1.s:11125/11132) and pauses only by leaving for the custom screen (sub_800A21C :15203-15218 paired with PauseBattle and state 0x14 at :11188-11195); HUDMATCH (window flag clear) froze its whole battle from the gauge filling. (2) Canon's MegaMan at frames 42..48: HP 0x3c, Timer 0, FlashingInvisTimer (CollisionDataPtr 0x020384f0 +0x24) 0; seeding cannot survive 427 frames of our own battle (two shockwave hits by then), so the HUDMATCH descriptor's phases were translated 318 frames earlier = 3 x 106 (enemy phase preserved): art_entry 5->23, art_timer 4->6 by 318 STEP_ORDER/STEP_HOLD ticks, scroll_xq 424->36, scroll_yq 724->18 (mod 1024), gauge_tick 50->32 by the mod-112 identity, Align band 415..440 -> 97..122, offset 109; left/right halves, HUD strip, both boxes all 0. (3) popup: the corpse draws from tiles up to 0x048, above F9's 768-byte blank -- ENEMY_DISSOLVE_FIRST_PHASE 0x60106E0:576 (5094->2858); the dissolve's transfer queue entries sit in slot 3 (0x0200B4F4 size word) at canon 44/45/48, not F9's slot 41 (a no-op on this row): three one-shot pokes (2858->0); banner 0/0/58 unchanged. Remaining: allowlist AUDIT-6 tiles/gauge entry now dead (removed by the human session after landing). Claude Opus agent, 62 tool calls, 20 min, 346k tokens.
**Files.** src/battle.rs (the gauge_pause re-arm hunk at ~2107 only), src/fixture.rs, tools/harness.py (the HUDMATCH and popup descriptors and notes)

**Why.** F28 measured why tiles/gauge integrated sit at 3865/678/8: HUDMATCH clears FLAG_OPEN_WINDOW and
battle.rs re-arms gauge_pause every frame once the gauge is full, so the rust battle freezes from battle 62
and the Mettaur never leaves its wait; the whole residue is its idle sprite against canon's swing. The
one-line fix (`if self.gauge == GAUGE_FULL && self.open_window_allowed() { self.gauge_pause = GAUGE_PAUSE }`)
alone makes the row worse (16130) because by battle 427 our MegaMan has taken two shockwave hits and is in
mercy while canon's holds HP 60 unhit through frame 51: the fixture has to carry canon's mid-battle MegaMan
(HP, mercy counter, position) the way it already carries the backdrop phase (scroll_xq/scroll_yq) and the
gauge (gauge_tick). Measured with the throwaway unfreeze: the Mettaur's box reads exactly 0 on all 8 frames
at the row's pinned offset 427 after F28's two frames.
**Do.** (1) The gauge_pause fix, cited (canon's custom gauge does not pause a battle whose window cannot
open). (2) A fixture field (peeked provenance) for MegaMan's HP and mercy state, read from canon's
BattleObject at 0x0203a9b0 (+0x24 HP, the mercy counter field) at the row's reference frame, applied at
battle init; HUDMATCH's descriptor carries canon's values. (3) Measure tiles/gauge integrated per half
(left/MegaMan, right/Mettaur). (4) Then popup: its rust side has no enemy (enemies:0) while canon's Mettaur
is deleted and dissolving for k=0..6 (5094 px after F27b); give the fixture the dissolving enemy at
canon's phase (state DELETE, HP 0, dissolve counter peeked) or show why F19's blanking should cover it.
**Acceptance.** tiles and gauge integrated 0/0/8 (negatives not blind) with the isolated variants still 0;
popup 0/0/80 or its residual attributed per frame; mettaur, wave, window, opening, chip-cannon, field 0 or
unchanged; the field integrated +5 re-measured; nothing worse.

### F31b. `buster`: re-cut the row around a canon side that fires, then land the four measured buster defects  *(DONE -- 2026-09-13, buster re-cut and closed: old row [canon idle, 3172 flat over an 8-wide plateau] replaced by one where both si)*

**Result.** buster re-cut and closed: old row (canon idle, 3172 flat over an 8-wide plateau) replaced by one where both sides fire; the press is poked into canon's AIData like F11's warp (the plain buster fires on the RELEASE: JoypadPressed 0x0002, Held, then Released -> CurAction 0x08 -> 0x11; Held alone does nothing for 24 frames; idle Held word 0xfc00), canon_ref = the watched CurAction write 0x11 at canon 132 (0x0203a9b9), anim 0x0e 133..157, barrel in OAM from 134, muzzle 135, both gone 159; 28 frames; band range(96,113) unique minimum 0 at offset 103 (2911 at 102 and 104). Pre-fix 4936/617/28 (neg 6869) -> 0/0/28 (neg 3167 not blind): (1) 4936->736 pose length derived = 5 fire ticks (sub_80EB450 asm31.s:108680-108691) + byte_80209CC[Rapid*6 + min(free panels ahead,5)] (sub_800FAAC/sub_800FAF6 asm00_2.s:1903-1990, dat01.s:146-149), measured at three columns (29/25/21 frames at col 1/2/3, three exact predictions, Rapid row 0), Actor::buster_spec computes it from the navi's column; (2) 736->0 barrel and muzzle live exactly as long as the pose (oAIData_Unk_68 / oBattleObject_RelatedObject1Ptr cleared by sub_80EB502 with object_exitAttackState, asm31.s:108712-108722), BUSTER_ARM_FRAMES/BUSTER_FX_FRAMES gone; (3)(4) strike_at 3->2 (muzzle and damage on the fire phase's second tick, asm31.s:108632-108676) and the extra fx.update() at spawn removed: pixel-neutral here because the two errors cancelled on blank muzzle cells. buster integrated 643698/27225/32 -> 248260/17668/28 (allowed). Full table 48 PASS, every failing row equal to main. Open, pixel-invisible: canon's CurAction 0x11 lands on k=0 while our ORCL export flips to 0x0b on k=1 though both draw the windup on k=0..1 (F36). Claude Opus agent, 32 tool calls, 20 min, 299k tokens.
**Files.** tools/harness.py (the buster row, its fixture and Align), tools/states.py (a recipe if one is needed), src/actor.rs (the BUSTER pose constants only), src/battle.rs (the buster hunks only: fx.update() at ~2623, BUSTER_ARM_DELAY, BUSTER_ARM_FRAMES/BUSTER_FX_FRAMES)

**Why.** F31 showed the buster row measures nothing about the buster: canon's press never fires in it and the
3172 is the result mark; its offset is a plateau tie-break, not an event. Canon fires when the press lands
in the 0x08 window (Start@10,B@30,B@31 on the STERILE+PAUSED+DELETE side: action 0x11 at f33, anim 0x0e
f34..f58, barrel f35, muzzle f36, both gone f60). A row is honest only if both sides fire: cut the canon
side there, lock canon_ref to the measured press event (the action write, watched), align by the same
event on our side (rust press frame), and re-sweep the band for a unique minimum. Then land the four
measured defects (pose length 25 = 5 + byte_80209CC lookup, derived; barrel on tick 0; the FX ticked once
on its spawn frame; barrel and muzzle until object_exitAttackState) with citations, measuring each alone.
**Acceptance.** a new buster row that compares two firing busters (state watches on both sides show the
attack state on the same offset), negative not blind, alignment by event; buster as low as the four fixes
take it; buster integrated re-measured; wave, window, opening, chip-cannon, field, mettaur, popup 0 or
unchanged; every chip row unchanged (they share the fixture path); nothing worse. The old 3172 alignment is
not to be "fixed" by giving our side the result mark: a row that draws nothing on either side proves nothing.

### F33. The integrated variants (field 305263, warp, buster, chip-use): decompose by HUD element with canon's element mask, fix in hud.rs/hudtiles.rs  *(PARTIAL -- 2026-09-13, field integrated 305263/10061/40 -> 304103/10032/40, warp integrated 363658 -> 362788, buster integrated 64369)*

**Result.** field integrated 305263/10061/40 -> 304103/10032/40, warp integrated 363658 -> 362788, buster integrated 643698 -> 642770, chip-use integrated 644119 -> 643191 (all allowed rows; -29 px/frame: ZERO_ENEMY said megaman_hp=100 while every canon side holds 0x3c at 0x0203a9d4, element 2 the HP box); cursor 620802 -> 502822 on the branch and 154367/914/170 on main after F26b (the emotion window's OAM x takes the chip window's slide counter eStruct2035280+0x12 = SLIDE_FROM - x, added by sub_801CDEC asm00_2.s:27561-27572; Custom::hud_obj_x() -> Emotion::show; -117980 exactly as predicted); windowclose 648948 -> 642133 on the branch, 27819/1938/40 on main. Per-element table for field integrated from canon's dispatcher tables (update sub_801BEE0 asm00_2.s:25540-25563 / off_801BF04, draw sub_801BF64 :25564-25599 / off_801BF88; masks on every compared frame 0x0084 update / 0x00c5 draw: elements 2 and 7 updated, 0/2/6/7 drawn, gauge/icon/emotion torn down at canon 48): element 2 HP box 29 px/frame fixed; element 6 chip name + damage (sub_801C6EE :26619) 422 px/frame on field/warp/buster still drawn by canon and not by ours because ours ties the name to the hand with the icon (element 1, torn down) -- measured proposal: ZERO_ENEMY hand=[1] plus battle.rs:3743 filter '&& self.hud_live' gives field 287204 / warp 350128 / buster 629266, neither half alone; gauge_up should also require hud_live (element 4, unmeasured); and 86% of the four rows' residue is the BG1 backdrop phase: ZERO_ENEMY seeds none (canon 130: x -64176 / y -32088 -> x_q 684, y_q 854 by backdrop.rs's arithmetic, art phase to walk back) -- F33b. Landed 870e3ef; post-merge cursor 154367, windowclose 27819, popup/buster/tiles 0. Claude Opus agent, 103 tool calls, 35 min, 255k tokens.
**Files.** src/hud.rs, src/hudtiles.rs, src/emotion.rs, tools/harness.py (the integrated rows' notes only), tools/allowlist.py entries removed only when a row reads 0

**Why.** Four integrated (full-HUD) variants are allowlisted since AUDIT-6 ("HUD vs a zero-enemy arena, not
compared before"): field 305263/10061/40, warp, buster, chip-use, each in the hundreds of thousands. F27b
found the HUD is driven in canon by a per-element enable mask (dword_20352C0; elements 0, 1, 4, 10 and 14
are torn down together at the RESULT countdown by sub_80081A4, asm00_1.s:10617-10621; the dispatcher
sub_801BEE0 asm00_2.s:25540-25563 with an updater and a draw per element, e.g. element 14 = emotion window
sub_801CADC/sub_801CDEC) and that our build models only element 14 of it. Decompose field integrated by
element: capture both sides, split the residue by HUD region (the HP box, the custom gauge, the emotion
window, the hand icon, the enemy HP objects, the chip name/icon) and by layer, name each element's canon
draw routine from the dispatcher table and its enable bit, and compare our drawing of it frame by frame.
**Do.** Fix element by element in your files with citations; measure each; then re-check warp, buster and
chip-use integrated (same HUD) and report their deltas. **Acceptance.** a per-element table for field
integrated with canon routines; field integrated as low as the elements you fixed take it, the isolated
variants and wave/window/opening/chip-cannon/popup/tiles/gauge untouched at their values; an allowlist entry
removed only for a row that reads 0; nothing worse.

### F32. End sequence: `over` fires at the last enemy's defeat, canon enters the RESULT countdown 47 frames later, after the dissolve  *(OPEN -- 2026-09-13)*

**Files.** src/battle.rs (the end sequence only), src/banner.rs

**Why.** F27b measured on the real ROM (PAUSED, enemy HP forced 0, Start@10): the banner sequencer enters
the RESULT countdown 0x0C at frame 47 and the HUD teardown fires at 48, while the enemy's death is at
frame 0 and its dissolve fills the 47 frames between; ours fires `over` (banner + RESULT) at the defeat
itself. No row measures that offset today because the result row is aligned by event on the results
screen, but it is a battle-flow defect that every later row through the end of a battle will hit.
**Do.** Watch canon's sequencer (dword_203CA70) and the enemy's state from the killing hit to 0x0C on the
result fixture's route, cite the routine that counts the dissolve and the one that enters 0x0C, and make
ours enter the end sequence on the same event with the same count. **Acceptance.** the frame of 0x0C
after the killing hit equal on both sides (watch on both), result 102547 or better on its event-locked
alignment, banner/popup/wave/window/opening/chip-cannon unchanged or 0.

### F34. `result` 102547: decompose by layer and frame; the window's inside (904), the slide lag, the backdrop tail *(CLAUDE -- 2026-09-13)*
**Files.** src/results.rs, tools/harness.py (the result row's note and its descriptor's backdrop seed fields only)

**Why.** result reads 102547/14866/40 (negative 195579 not blind) after F21 (reward reveal chain) and F21d
(block-copied tilemap, one blit per frame, F21b's slide). F21 left "inside the window 904 on the plateau,
outside ~2900/frame backdrop tail + slide lag"; nobody has decomposed the 102547 since F21d. Per-layer and
per-frame first: the window's BG, the backdrop BG1 (its scroll phase is a per-row seed derived from canon's
counters at the row's canon_ref -- F26b is deriving that mechanism for the CUSTMATCH rows; if its
derivation lands first, apply it here, otherwise derive this row's seed the same way and cite it), OBJ.
Then the window itself: canon's driver chain sub_802BD60 -> sub_802BE36 -> sub_802C044/sub_802C0A4 (F21),
its slide timing and tile content frame by frame against ours.
**Acceptance.** a layer x frame table with canon citations; result as low as the mechanisms you fix take it
(each fix measured alone); field, wave, window, opening, chip-cannon, popup 0 or unchanged; nothing worse.

### F33b. The ZERO_ENEMY rows' backdrop seed and the two HUD gates: field/warp/buster/chip-use integrated toward 0 *(CLAUDE -- 2026-09-13)*
**Files.** tools/harness.py (the ZERO_ENEMY descriptor and the four integrated rows' notes), src/battle.rs (the two HUD gates only: the chip-name filter at ~3743 and gauge_up), src/hud.rs, src/hudtiles.rs

**Why.** F33's per-element decomposition: 86% of field integrated's 304103 (and of warp/buster/chip-use
integrated) is the BG1 backdrop phase, because ZERO_ENEMY seeds no backdrop phase while its canon side is
thousands of frames into pausedwithcannon; canon's counters at canon 130 read x -64176 / y -32088
(-8f/-4f from battle init, F26b) and at 150 x -64336 / y -32168, so by backdrop.rs's arithmetic x_q=684,
y_q=854 at canon 130 with the art phase to walk back the same way; the seed is per row (each row's
canon_ref differs) and our pipeline lags are the ones F26b measured (scroll R-7, art R-5). The rest of the
HUD: element 6 (chip name + damage, sub_801C6EE asm00_2.s:26619) is drawn by canon on every compared frame
and not by ours because we tie the name to the hand together with the icon (element 1, torn down at 48):
measured, ZERO_ENEMY hand=[1] plus `.filter(|_| self.chip_use_in != 1 && self.hud_live)` at battle.rs:3743
gives field 304103 -> 287204, warp 362788 -> 350128, buster 642770 -> 629266 (422 px/frame), and neither
half alone (the descriptor half alone regresses warp/buster isolated); gauge_up should also require
hud_live (element 4). chip-use additionally keeps the name after the chip is used (canon reads
dword_20352C8), ~444 px/frame.
**Do.** (1) Derive and set each of the four rows' backdrop seed (art_entry/art_timer/scroll_xq/scroll_yq)
from canon's counters and GFX state at that row's canon_ref, citing the derivation; measure BG1 alone
per row. (2) The two gates with citations, with the hand descriptor, measured together; check windowclose
and cursor (both enemies=0 rows) do not regress. (3) chip-use's name after use. **Acceptance.** BG1 0 on
all frames of the four rows; each row's remaining residue decomposed by element and layer; the isolated
variants, cursor, windowclose, popup, buster, tiles, gauge, wave, window, opening, chip-cannon unchanged
or better; an allowlist entry removed only for a row that reads 0; nothing worse.

### F26b. `cursor` layer table: repair the OBJ arithmetic and check the four UNCHECKED attributions  *(PARTIAL -- 2026-09-13, cursor 620802/6884/170 -> 272341/1603/170 [neg 458619 not blind] at the event offset 237 [the unseeded band's )*

**Result.** cursor 620802/6884/170 -> 272341/1603/170 (neg 458619 not blind) at the event offset 237 (the unseeded band's minimum had sat at 226, 11 frames off the event, with 237 reading 779920); windowclose 407778 -> 34707/2652/40 (neg 221819 not blind) at 253; BG1 alone 0 on all 40 windowclose frames and 2 px on 1 of 170 cursor frames. Derivation: BGScrollCB_BG1Diagonal3to2Scroll (asm00_0.s:3287-3303) writes (counter-8)>>4 and (counter-4)>>4 to BG1HOFS/VOFS, counters zeroed at battle init (sub_8080D90/DA0 asm00_1.s:8434-8435) so they hold -8f/-4f at battle frame f (watched: CHIPSELECT sits at battle frame 3156); canon's phase in our units x_q=2f mod 1024, y_q=f mod 1024; art from eGFXAnimStates[0] (0x020094c0) entry=(CommandPos-LoopAddress)/8 and Timer, 192/cycle; our pipeline lags measured once on windowclose (a capture frame R shows the scroll of tick R-7 and the art of tick R-5) and predicted cursor with no tuning (2214975 -> 2). Seeds: CURSOR_ROW art 11/3 scroll 746/885, WINDOWCLOSE_ROW 17/1 846/935; CUSTMATCH_ROW untouched (window/card 0). The odd-frame lsr-vs-floor note retired with a proof (lsr #4 of -8f = -ceil(f/2) = -((x_q+3)/4)), comment-only, .text/.rodata byte-identical to main. Layer table repaired (layer-local vs attributed): cursor 272341 = OBJ 272340 + BG1 1; windowclose 34707 = OBJ only. F26's UNCHECKED: (a) '2-frame art lead' refuted (an unseeded clock), (b) no Kind field exists (enemy NameID 1 constant), (c) the y18..33 HUD block is a pure 120 px x displacement: ours x2..45, canon x122..165, identical content, 117980 px-frames of cursor (the emotion window's custom-screen position; F33), (d) MegaMan panel (2,3) confirmed, landed by F29. Remaining: cursor's 1 px at k=97 is sub-frame (canon's tile copy is queued by QueueEightWordAlignedGFXTransfer/sub_8001C94 asm00_0.s:3752 and drained part-way down the frame, ours lands before scanline 0) and the 2-frame relative skew of our scroll and art clocks is absorbed per row by seeds rather than fixed in src (F35); the rest is OBJ (cursor: HUD block 117980 + y107..159 154360; windowclose 34707). Claude Opus agent, 92 tool calls, 32 min, 207k tokens. Post-merge on main with F28b's gauge_pause change (landed in between): cursor reads 272378/1639/170 (+37 px, sprite layer), windowclose 34707 unchanged; the interaction belongs to the cursor sprite-layer follow-up.
**Files.** src/backdrop.rs, src/actor.rs, tools/diffmask.py, tools/probe.py

**Assigned to a Claude agent (2026-09-13 21:00) together with the backdrop-phase findings of F29.** F29 measured on windowclose (fixture CUSTMATCH_ROW, shared with cursor): the backdrop layer BG1 is a constant (20,10) px translation on all 40 frames (scroll rates SCROLL_X_Q=2/SCROLL_Y_Q=1 per frame are right; 40 frames of the phase gap is exactly (20,10)) because the fixture seeds no backdrop phase (art_entry etc. 0xFFFF, a fresh Backdrop::new at x_q=y_q=0) while /tmp/chipselect.state is thousands of frames into a battle. Canon at windowclose's reference frame 81: eBGScrollCBCounters (ewram.s:619, 0x02009690/0x02009694) = 0xffff9ad8 / 0xffffcd6c; eGFXAnimStates[0] (ewram.s:596, 0x020094c0) LoopAddress 0x0807fba4, CommandPos 0x0807fc6c = entry 25, first halfwords 0x0001 0x0002. An empirical seed scroll_xq=80/scroll_yq=40 took BG1 877602 -> 228662 and windowclose 648948 -> 392992, but the same seed takes cursor 620802 -> 1222398: cursor pairs rust 237 with canon 15 where windowclose pairs 253 with 81, so the seed must be derived per row from canon's counters at that row's own canon_ref, never shared. After the seed, BG1's residual alternates +1 px on odd multiples of 3 (k=3,9,15,...) and 0 on even multiples of 6: the lsr-of-a-falling-counter vs floor-divide difference src/backdrop.rs:278-283 already documents as untested; this row measures odd frames. Acceptance for this pass: BG1 0 on all 40 windowclose frames and on cursor's 170 frames, both with seeds derived from canon's counters (cite the derivation), cursor and windowclose totals reported per layer, wave/window/opening/chip-cannon/field/result 0 or unchanged.

**Why.** F26's verified Result (PARTIAL): BG0/BG2/BG3 clean and BG1 scroll rates match (both verifier-CONFIRMED), but the verifier FLAGGED the OBJ-layer arithmetic (OBJ-total 689572 exceeds the full-frame 620802, so as stated it must count occluded/overdrawn pixels -- the table must say which) and marked four attributions UNCHECKED: (a) BG1 art phase ours-leads-by-2 (canon entry 17->18 at k=4 vs ours at k=2; citations LoadGFXAnim/ProcessGFXAnims/sub_8001C94/schedule off_807FB98 CONFIRMED, entry-size-8 and the lead itself not measured); (b) chipselect's enemy is a Mettaur variant other than kind 0 (04/0b stability not re-measured; no oBattleObject_Kind field found -- variant may ride NameID); (c) enemy-HP portrait content byte-identical 871px with box-x canon 122-165 vs ours 2-45; (d) MegaMan at canon panel (2,3) vs fixture (3,2). No F-next may build on the table until the arithmetic closes.
**Do, in order.**
1. Start in `bash tools/worktree.sh f26b-layers2`. Baseline cursor at offset 237 (620802/6884/170/728447, negative not blind).
2. Redefine the OBJ-layer measurement so the arithmetic closes (visible-composite diff pixels vs layer-local diffs, stated per layer), re-measure the per-layer totals at offset 237, and check (a)-(d) with watches on this row's own captures (GFXAnim state at 0x020094C0 both sides; enemy CurState/CurAction + NameID/variant field; portrait bbox both sides; MegaMan panel both sides).
3. Fix in src/ only what has a canon citation and a measured before/after on cursor; otherwise stop with the repaired table. Re-run cursor, wave, window, opening, chip-cannon, result, field -- nothing worse.
**Rules.** Same files as F26; no alignment/allowlist/seed/scroll change except by measured event; captures one at a time.
**Measure and report.** Repaired layer table (definition stated, arithmetic closed), (a)-(d) confirmed or refuted each with the watch traces, rows before/after, full-table deltas. **Acceptance:** the table adds up and every attribution the next cursor ticket needs is measured, not inferred.
**Coordinator:** `verify_rows` on every row the report names; the verifier on the repaired table and any canon citation.

### F35. Backdrop engine timing: tile copies drained mid-frame like canon's queue, and one clock for scroll and art  *(OPEN -- 2026-09-13)*

**Files.** src/backdrop.rs, src/main.rs

**Why.** F26b measured two engine-timing facts on the backdrop. (1) Canon queues its backdrop tile copy
(QueueEightWordAlignedGFXTransfer, sub_8001C94, asm00_0.s:3752) and the queue drains part-way down the
frame, so on the frame of an art step canon shows the previous step in rows 0..5 and the new one below;
ours lands before scanline 0. Visible as 2 px on cursor's frame k=97 (the same texel twice, 128 apart).
(2) Our scroll register is written by commit() and the art by replace_tile() inside update(), so a
capture frame R shows the scroll of tick R-7 and the art of tick R-5: a 2-frame relative skew between two
clocks that canon does not have (one counter pair, one queue). The per-row seeds in the harness absorb
it today; the mechanism should not need absorbing.
**Do.** Watch canon's queue drain (the transfer's VRAM write frame and scanline via --watch-write on the
tile region) and ours; make ours copy at the same point of the frame canon's queue does (cite the queue
flush routine and its place in the frame loop), and drive scroll and art from one tick so both lead by the
same amount; then re-derive the CURSOR_ROW/WINDOWCLOSE_ROW seeds by F26b's derivation with the new single
lead and show BG1 0 on all cursor and windowclose frames. **Acceptance.** cursor's BG1-only diff 0 on all 170
frames; windowclose BG1 0 on all 40; wave, window, card, opening, chip-cannon, field, result, tiles, gauge
0 or unchanged; nothing worse.

### F36. The oracle export block trails or leads the frame it describes by one frame (buster's attack-state entry)  *(OPEN -- 2026-09-13)*

**Files.** src/main.rs, tools/oracle.py

**Why.** F31b's re-cut buster row reads 0 px, but on its lock canon's CurAction becomes 0x11 on k=0 while
our ORCL export's CurAction byte flips to 0x0b on k=1, though both sides draw the windup on k=0..1 and the
pose from k=2. Either our attack state is entered a frame late (and its first frame draws the same pixels as
idle), or the export block is written a frame away from the frame it describes (it is written between
battle.update() and gfx.frame()). Every oracle comparison inherits that ambiguity.
**Do.** Watch the ORCL block against a state whose drawing is unambiguous on the same frame (a warp or a
flinch: the pixel changes on the frame the state changes on canon), on both sides, and say which side of the
pair is off; fix it (the export's placement in the frame loop, or the state entry), cite canon's order of
state update vs draw (the object dispatcher then object_updateSprite), and show the oracle's first
divergence unchanged or improved on mettaur, buster, warp and card. **Acceptance.** the export's fields
describe the frame captured (shown on two rows with a state change), no pixel row changes.

### F23. Naming pass: the bare numbers in src/custom.rs and src/battle.rs  *(OPEN -- 2026-09-13, battle.rs naming: 110 bare lines/38 values->0/0 [~60 consts])*

**Result.** battle.rs naming: 110 bare lines/38 values->0/0 (~60 consts); release .text md5-identical, .gba same size 553172B cmp-l 29 rodata panic-tables only; full table all 60 rows ran non-blind + rollup PASS (3x2600f); buster 3172 pre-existing; landed 67f2a7d; ticket OPEN for actor.rs; worker muse-spark 92 turns $0.052, no verifier
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

