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
### F12. The chip rows' own residues, family by family -- multi-pass, stays OPEN until every chip row is 0  *(DONE -- 2026-09-14, every chip row reads 0: the last two were areagrab [orb draw order + burst palette walk, ad653c0] and chip-use)*

**Result.** every chip row reads 0: the last two were areagrab (orb draw order + burst palette walk, ad653c0) and chip-use, re-cut F31b-style so canon fires its Cannon via an AIData A-tap poke (1a3ca80; the old row was vacuous), 9514/1185/32 -> 0/0/30 (neg 7768 not blind). 43 of 43 chip rows at 0; the multi-pass ticket's end condition is met (closed by the human session, 2026-09-14 03:30).
**Result.** chip-use re-cut landed 1a3ca80: chip-use isolated 9514/1185/32->0/0/30 (neg 7768 not blind); old scripted A@150 refused in 0x0C (verifier CONFIRMED vacuity), AIData A-tap poke@130 fires canon Cannon (CurAction 0x08->0x14 CONFIRMED), both fire at offset 101; window stops pre-result-mark (buster stop); OPEN stays: canon 4f tail, 1f watch ambiguity, canon-side k=12 RNG slip (pixel-invisible); areagrab 0 held; HEAD re-check MATCH; worker branch TODO-stamp dropped by coordinator; worker muse-spark, verifier GLM
**Result.** areagrab remainder landed ad653c0: chip-areagrab 1278/684/77->0/0/77 (neg 28276 not blind); wave/window/opening/chip-cannon/minibomb/3xseeds 0 held; chip-use 9514/1185/32 held for next pass; field-integrated +2 layout-jitter (verifier CONFIRMED dead-path); verifier ACCEPT with caveat (canon OAM y-descending order cited-not-reproduced, asm31.s:30497 anchor confirmed); HEAD re-check MATCH; worker muse-spark, verifier GLM
**Result.** areagrab orbs: 25644->1278/684/77 (byte-proof extraction 67e3f4e2, 36c3a22 KEPT: acceptance 0 unmet); verifier CONFIRMED asset bytes + Z<=0 landing + held-art/burst-next in disassembly + scope/rules clean (palette/spawn-k consistent-unchecked; k=76 burst-bank unchecked but arithmetically forced); residual = burst bank + dim shading (dim undrawn, out of scope); stale fitted tag on AREAGRAB_PRESENTATION=77 noted for follow-up; cursor -15; worker muse-spark 83 turns $0.055, verifier GLM Landed on main by the human session at 68535fb as a verified partial (land.sh, verify_rows on chip-areagrab 1278/684/77 plus five canaries); the burst bank and dim shading stay with F12.
**Result.** areagrab orbs measured-STOP (assets rule in brief): orb chain sub_80E07E0->t4_0x3->sub_80C6548->t3_0xf sprite_830E44C, 8 OBJs 4x16x32 pairs falling 8px/f, 1752px worst matched exactly; art in NO current asset (poisarea sheet differs) -> no asset added per brief; NOTE standing Decision ALLOWS canon-extracted assets (vulcan/energbom precedent) so next pass may extract; no edits, tree clean; worker muse-spark
**Result.** barrier bubble: 3x52560->0/0/80 PASS (neg 41067) via BARRIER_PRESENTATION 77->45 (attack+46, peeked); areagrab held 25644 (split 77 fitted, value-preserving); verifier CONFIRMED entry/bubble/gate/pattern + cursor -28 jitter (0x14-vs-0x15 wording flag; fitted count 18); landed 5e681a1 HEAD re-check MATCH; worker muse-spark 57 turns $0.027, verifier GLM
**Result.** popup-gate family: areagrab -17723 (25644), barriers converge 52560 (-15k..-21k), popup 0; HUMAN-IMPLEMENTED (Alex Berliner aff9a31 direct on branch, worker verified byte-identical to own patch); verifier CONFIRMED pattern+popup-free residue+jitter-LAND; cursor 154404 (+13 layout); landed 6081948 HEAD re-check MATCH; worker muse verification-only, verifier GLM
**Result.** verifier on next4 claims: popup-arms ungated CONFIRMED (battle.rs:3594/3603, same FLAG_HUD_LIVE pattern ready); chip-use refusal + offset-129-vs-100 + bubble +46 UNCHECKED (verifier hit budget pre-captures, left exact re-measure commands); offset-129-vs-100 flagged important (AGENT_GUIDE event-alignment); rules clean
**Result.** family-0x15 localized, no landing (budget stop, no edits): areagrab 43367 (popup strip + missing steal orbs), barrier 67921/barr100 71816/barr200 73481 (ungated popup + bubble +46 vs +79); chip-use 9514 NOT chip-content (press refused: seq 0x0c, JoypadPressed 0, ambient flame; offset-129-vs-100 caution) left for owner; baselines verify-locked; next: gate BARRIER/AREAGRAB arms on FLAG_HUD_LIVE; worker muse-spark
**Result.** energbom family: 2x19932->0/0/60 PASS (neg 22207) via Param1==2 t3_0x11 ring (sprite_83B2494 canon bytes); canaries+mettaur/popup/buster/result 0/held; cursor +12 layout-class (verifier: fresh-build reproduced, no executable path, pad-band precedent); verifier CONFIRMED routing chain + asset bytes + rules clean (live-Param1 + 53/54 frames unchecked, mitigated by 0/0 parity); landed 2e19e83 HEAD re-check MATCH; worker muse-spark, verifier GLM
**Result.** invisibl family: 14740->0/0/80 PASS (neg 40080 pixel), popup 0 intact; cursor 154361 on landing (below HEAD 154386; +22 jitter claim documented via pad probe -28); verifier CONFIRMED gate claims earlier; landed 25fc380 HEAD re-check MATCH; worker muse-spark 32 turns $0.01
**Result.** invisibl fix validated, KEPT for cursor +28: chip-invisibl 14740->0/0/80 (neg 40080 pixel), popup 0 intact; verifier CONFIRMED sub_801E95C citation, sterile-zero vs PAUSED-presence (re-measured), FLAG_HUD_LIVE 0x4497/0x8084 disambiguator (nuance: upper-half field varies, live-bit holds), harness pixel-negative legitimate (window precedent); cursor +28 numbers CONFIRMED, 31px signature UNCHECKED; branch wt/f12-next2 6388e2b KEPT unmerged; worker muse-spark, verifier GLM
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

- F25 PARTIAL -- Mettaur attack phase: enter canon's 106-frame attack cycle like canon does. mettaur 19698/1245/70 unchanged (neg 60824 not blind)
- F25b BLOCKED -- Mettaur +1 attack-phase offset: attribute it, fix only inside the attack path. attack path pixel-perfect at true phase (offset 204: enemy 0px, MegaMan 30864)
- F24 NEGATIVE -- `cursor`/`result` backdrop: port canon's per-scanline BG scroll (the BGScrollCB HBlank raster callback) into src/. premise refuted: canon battle HBlank scroll callback is nullsub_38 no-op (22/22 backdrop types, verifier CONFIRMED in disassembly)
- F25c PARTIAL -- `mettaur`: the shockwave's flight is 44 frames, canon's is 45 -- the one frame between the enemy's phase and MegaMan's. mettaur 19698/1245->4265/800/70 (neg 45788 not blind), oracle 10/10 fields 70/70 FIRST-DIVERGENCE-none
- F25d DONE -- `mettaur`: the departure spray on 8 frames, 4265 px, content not timing. mettaur 4265/800/70 -> 0/0/70 (neg 41734 not blind), oracle 10/10 fields 70/70
- F27 CLAUDE -- `popup`: the OBJ-layer element canon draws over the enemy and ours does not (55520 px). 
- F28 PARTIAL -- Mettaur: its first attack starts 64 frames after canon's, relative to battle start. premise refuted as a defect, two real frames fixed, landed
- F29 PARTIAL -- `windowclose`: decompose the remaining 648948 by layer and frame, fix what lives in the window. windowclose 648948/27391/40 -> 407778/11879/40 (neg 534875 not blind), landed
- F31 PARTIAL -- `buster`: 3172 px over 32 frames, blocked twice, a fresh measurement. the row is vacuous: canon's OAM over the window holds four idle-MegaMan objects plus, from canon frame 164, the battle-result mark (16x16 ti
- F30 PARTIAL -- `field` integrated: a one-scanline write lands on either side of a VBlank boundary depending on ROM layout. layout race 10585px [(8,10585)] -> 0 over 200 frames across ROM layouts (worker)
- F30b BLOCKED -- VBlank re-sync spin: is cursor frame 0 better or worse, and gate the spin accordingly. spin proven no-op on cursor (6 reps 620802 bit-identical, F30 +112 = layout jitter)
- F27b DONE -- Emotion window: show it on canon's rule (HUD element mask bit 14, from HUD init to HUD teardown), not "while an enemy is alive". popup 60614/1842/80 -> 5094/1148/80 (neg 5286 not blind), the x2-45 y18-33 emotion-window box 0 on all 80 frames
- F26 PARTIAL -- `cursor`: decompose the x>=112 residue by layer and name each layer's mechanism. layer table delivered: BG0/BG2/BG3 0, BG1 scroll rates match (verifier CONFIRMED counters+zeroing+rate), BG1 art citations CONFIRMED
- F28b DONE -- tiles/gauge integrated to 0: unfreeze the HUDMATCH battle and seed MegaMan's mid-battle state; then popup's dissolving enemy. tiles/gauge integrated 3865/678/8 -> 0/0/8 (neg 12843 not blind), isolated 0/0/8 unchanged
- F31b DONE -- `buster`: re-cut the row around a canon side that fires, then land the four measured buster defects. buster re-cut and closed: old row (canon idle, 3172 flat over an 8-wide plateau) replaced by one where both sides fire
- F33 PARTIAL -- The integrated variants (field 305263, warp, buster, chip-use): decompose by HUD element with canon's element mask, fix in hud.rs/hudtiles.rs. field integrated 305263/10061/40 -> 304103/10032/40, warp integrated 363658 -> 362788, buster integrated 643698 -> 642770, chip-use integrat
- F34b DONE -- `result` to 0: no intro fade when the fixture starts on the results screen, MegaMan's panel, no enemy. result 93183/14866/40->0/0/40 PASS (neg 111839): intro_fade=0 on start_state==1 (7316) + megaman_col 2 (3330) + enemies 0 (3986)
- F32 DONE -- End sequence: `over` fires at the last enemy's defeat, canon enters the RESULT countdown 47 frames later, after the dissolve. over 35 updates after killing blow (was 92): death->0x0C 35/35 both canon routes (47 = 12 pre-resume + 35)
- F34 PARTIAL -- `result` 102547: decompose by layer and frame; the window's inside (904), the slide lag, the backdrop tail. result 102547/14866/40 -> 93183/14866/40 (neg 192263 not blind), landed: canon's PRESS-A-BUTTON prompt run in src/results.rs (sub_802C810 se
- F33b PARTIAL -- The ZERO_ENEMY rows' backdrop seed and the two HUD gates: field/warp/buster/chip-use integrated toward 0. field integrated 304103/10032/40 -> 158938/5609/40 (neg 261037), warp integrated 362788 -> 40628/11744/30 (neg 129960, now inside its cap), 
- F26b PARTIAL -- `cursor` layer table: repair the OBJ arithmetic and check the four UNCHECKED attributions. cursor 620802/6884/170 -> 272341/1603/170 (neg 458619 not blind) at the event offset 237 (the unseeded band's minimum had sat at 226, 11 fra
- F33c NEGATIVE -- The integrated rows after F32: let the zero-enemy fixtures resolve where canon's battle resolves. resolve-flag hypothesis refuted with structure (warp 40628->83175 tried+reverted
### F33d. Post-0x0C simulation: act after the countdown starts instead of freezing in `over`  *(PARTIAL -- 2026-09-14, verifier verdict: canon citations CONFIRMED [sub_800801C:10422, off_8008038 table, sub_80081A4:10617, 0x0C@0x0)*

**Result.** verifier verdict: canon citations CONFIRMED (sub_800801C:10422, off_8008038 table, sub_80081A4:10617, 0x0C@0x0800811E, sub_8012DFC:8977 not called from 0x0C handler, sub_801BED6 teardown, sub_802BD60:11549); scope/rules CONFIRMED (src/battle.rs only); watch-trace frame values + stall attribution UNCHECKED (worker assertions, disassembly-consistent); branch KEPT unmerged; verifier GLM Human session measured the kept branch from a clean checkout and landed it (208c158) as a cited behaviour change with no pixel effect: all nine isolated canaries 0; integrated warp 40628 / buster 54672 / opening 72499 / field 159061 (+123 jitter) unchanged, and chip-use integrated reads 275307 on both sides of the merge -- its drop from 567780 came from F12's chip-use re-cut (1a3ca80), not from this branch. The warp/buster ramps and chip-use's 275307 stay open for the next integrated ticket.
**Result.** post-0x0C split ported but no reduction: warp 40628/11744/30, buster 54672/12977/28, chip-use 275307/18091/30 all identical to baseline; field 158954->159061 (+107 k=5 show-frame only, mechanism unexplained, deterministic); isolated warp/buster/chip-use/field all 0; opening/cursor/windowclose byte-identical; stall attributed (synchronous show_results ~4-frame CPU, battle 109 never presented) but not reduced; k=0..23/0/0..3 pre-ramps 0 held; branch wt/f33d 7cd1f5c KEPT unmerged (acceptance unmet: stall not reduced, field +107); worker muse-spark
**Files.** src/battle.rs, src/banner.rs

**Why.** F32 landed canon's count (dissolve routine at ROM 0x08016676 counts 35 live updates from the killing blow to 0x0C; battle main 0x0800A09F calls sub_80081A4 whose 0x0800811E writes 0x0C to dword_203CA70). F33c re-measured all four integrated rows on main (tools/harness.py:1260-1308): dword_203CA70 reads 0x1c at canon 0..10, 0x08 from 11, 0x0C at 47 on every row's own canon capture (probe.py watch 0x0203ca70:4), and per-k at the event-locked offsets warp off 51 k=0..23 all 0 then k=24..29 = 1917,3837,5757,7677,9696,11744 (canon 154..159 slide-in, total 40628), buster off 103 k=0 0 / k=1..21 422 (name strip) / k=22..27 2458..12977 (45810 of 54672), chip-use off 100 k=0..3 0 then ramp to 25328/frame (567780), field off 108 k=0..1 0 then ~4757/frame (158930). The resolve-flag hypothesis was tried on warp and reverted (83175 integrated vs 40628, 44767 isolated vs 0) because it is structural, not tuning: our `paused` includes `over` (battle.rs), so the scripted subjects never fire, and our ENEMY DELETED banner (banner.rs SCALE, 58 frames, OBJ) parks its tail over k=0..9. Every canon side acts AFTER 0x0C (warp warps at canon 132/152 with the 706/458/395/458/706 signature; buster CurAction 0x08->0x11 at canon 132; chip-use A@150 fires via Unk_44 0->0x4 at 0x0800FFEA then CurAction 0x08->0x14 at 0x0801169A) -- canon keeps simulating inputs/objects/HUD/RESULT after the countdown starts while we freeze them. Field's own stall is decomposed but untraced: captures 118,119,120 byte-identical (117->118, 118->119, 119->120 all full=0), flipping the every-other-frame scroll rhythm from lag 14 pre-stall to lag 11 post-stall (canon never freezes past isolated singles), region sums top=33496 mid=22633 bot=25306 rest=100128 = 158930, k=24..37 slides coincide with matching content (F21/F34 chain holds), coinciding with results_delay 3,2,1 (show at battle 110 = capture 121) with the freezing mechanism untraced (tools/harness.py:1287-1304).

**Do, in order.**
1. Trace canon's per-frame work after 0x0C on one integrated row's own canon capture (warp), citing reference/bn6f file:line for each: the banner-sequencer dispatch sub_800801C (asm00_1.s:10422, table off_8008038) and the 0x0C handler sub_80081A4 (asm00_1.s:10617-10621, 0x0C write at 0x0800811E, teardown/mask init at 0x080081CA); input refresh sub_8012DFC (asm00_2.s:8977, asm00_1.s:10519-10522 -- runs from 0x08, never from 0x0C) vs what 0x0C does run (playerObject_update_80EA484 asm31.s:107160, sub_8012FC8 tail asm00_2.s:9520, object_setAttack2 0x0801169A); HUD mask dword_20352C0 updates (sub_801C168/sub_801C202/sub_801C6EE, sub_801BED6 teardown 0x4497->0x0084 at 0x0801BEDC lr 0x080081B9, banner re-set bit 15 via sub_801BECC); RESULT driver chain sub_802BD60 (asm03_0.s:11549) -> sub_802BE36 -> sub_802C044/sub_802C0A4 incl. CopyBackgroundTiles (asm03_0.s:11575). Measured by --watch 0x0203ca70:4 + 0x020340a2:2/0x020340a4:2 + 0x0203a9b8:4 + 0x020352C0:4 on canon's capture, naming which of the four classes runs each frame after canon 47.
2. Watch ours on the same frames (same four addresses via probe.py on the rust side) and port only the split: `over` stops gating inputs/objects/HUD/RESULT (banner tail confined to its 58-frame OBJ life, no k=0..9 park; scripted warp/buster/chip presses fire past battle 47), while the RESULT countdown/slide keeps F32's count and F21/F34's driver chain. Measured by per-k full-screen shapes on warp integrated at off 51 before/after (k=0..23 must stay 0, k=24..29 ramp is the target).
3. Attribute field's 118-120 stall on the same pass: --watch-write the writer that freezes updates while results_delay reads 3,2,1 (battle.rs results_delay/results_mark/shown/filler_bg hunk), name it with its canon counterpart from step 1 or mark it untraced. Measured by region sums (top/mid/bot/rest) and lag numbers at off 108 before/after.

**Rules.** Only the files in **Files.**; no alignment/allowlist/seed/scroll/hand change except by the watches above; offsets stay event-locked by mark/press (warp 51, buster 103, chip-use 100, field 108), never by score.

**Measure and report.** Warp/buster/chip-use/field integrated before/after (total/worst/frames) on the identical event-locked windows with per-k shapes, the four-address watch traces both sides naming which post-0x0C class was ported, field stall region/lag table before/after, full-table deltas. **Acceptance.** Warp/buster/chip-use integrated as low as the acting-after-0x0C port takes them (k=0..23 / k=0 / k=0..3 pre-ramp frames 0; ramp only where canon's slide has no rust counterpart yet, F21/F34's chain); field stall attributed and reduced, slides still coinciding; the four isolated variants and every 0 row unchanged; allowlist entries removed only for rows that read 0; nothing worse.

**Coordinator:** `verify_rows` on warp/buster/chip-use/field integrated plus warp/buster/chip-use/field isolated and every row the report names; the verifier on the sub_80081A4 / sub_8012DFC / sub_802BD60-chain citations and the watch traces.

- F35 PARTIAL -- Backdrop engine timing: tile copies drained mid-frame like canon's queue, and one clock for scroll and art. mechanism mapped+cited, fix reverted honestly (scanline-6 wait: BG1 62->184/0->571 -- copy smear)
- F35b BLOCKED -- Backdrop step copy: one block copy inside ~1 scanline, then place it at the drain scanline. fast copy 11->1 scanline works as mechanism but fixed placement fails both ways (vblank copy leaves 88, scanline-6 leaves 3007) -- canon usu
- F36 DONE -- The oracle export block trails or leads the frame it describes by one frame (buster's attack-state entry). export placement verified frame-accurate (post-commit test strictly worse, reverted)
### F37. `cursor` and `windowclose`: the sprite layer, object by object  *(PARTIAL -- 2026-09-14, per-object tables landed 1bee9d8 [notes only, descriptors untouched]: cursor 154361/909/170 [camera-pan +15Y +)*

**Result.** per-object tables landed 1bee9d8 (notes only, descriptors untouched): cursor 154361/909/170 (camera-pan +15Y + Mettaur pose 4,11-vs-4,8), windowclose 27819/1938/40 (hand-icon 256 + pose 205, k0 bracket 104); 8 canaries 0; no in-scope fix exists (ai.rs freeze no-op, hud/emotion no pan path); follow-up needs battle.rs+fixture.rs scope; HEAD re-check MATCH; worker muse-spark
**Files.** src/ai.rs, src/hud.rs, src/emotion.rs, tools/harness.py (the cursor and windowclose rows' notes and CUSTMATCH_ROW/CURSOR_ROW/WINDOWCLOSE_ROW descriptor fields)

**Why.** Both rows have every BG layer at 0 (F26b, F29, F33) and everything left is OBJ: cursor ~154k
over 170 frames (F26b's partition: after F33 fixed the emotion window's x, the remainder is the y107..159
band, ~154360 px-frames) and windowclose 27819 over 40 frames (F29: the Mettaur's phase, flat ~205
px/frame from k=10, plus the HP boxes / hand icon on k<10). Nobody has split either by object with
canon's OAM. Decompose per object on both sides (OAM dumps per frame: MegaMan, the Mettaur, the HUD
objects, the emotion window), name each object's first differing frame and its mechanism with a canon
citation: the Mettaur's state during a custom screen (canon pauses the battle; what does its object do,
sub_8109DEC family) against ours, the HUD element mask on these rows (F27b/F33's dispatcher tables), the
descriptor's enemy fields (F28/F28b's peeked mid-battle state) for the Mettaur's phase at the row's
canon_ref. Fix what has a citation and a measured delta; seed through the descriptor only what canon's
RAM at canon_ref says (peeked provenance).
**Acceptance.** a per-object table for both rows; cursor and windowclose as low as the fixes take them,
each fix measured alone; window, card, wave, opening, chip-cannon, mettaur, popup, result 0; nothing worse.

### F37b. `cursor` and `windowclose` to 0: the camera pan while the chip window is open, the Mettaur's held pose, the hand icon and bracket  *(PARTIAL -- 2026-09-14, pan+pose+icon landed a6bf21c: cursor 154361/909/170->130221/767/170, windowclose 27819/1938/40->19168/1878/40 )*

**Result.** pan+pose+icon landed a6bf21c: cursor 154361/909/170->130221/767/170, windowclose 27819/1938/40->19168/1878/40 (neg 316499/214890 not blind); 9 canaries 0; verifier CONFIRMED pan/pose/icon mechanisms + scope (mask values/remainder split consistent-unchecked); remainders: actor object-Y pan (~765/f), custom.rs k0 bracket 104, pose frame (prime reverted); HEAD re-check MATCH; worker muse-spark, verifier GLM
**Files.** src/battle.rs (the camera pan / custom-screen state hunks only), src/fixture.rs (peeked enemy-state fields), tools/harness.py (CUSTMATCH_ROW / CURSOR_ROW / WINDOWCLOSE_ROW descriptor fields and the two rows' notes)

**Why.** F37's per-object tables (landed as notes, 1bee9d8): cursor 154361/909/170 is (a) the field and
its objects sitting 15 px higher on canon while the chip window is open -- the same camera pan F29 ported
for the close (sub_8026BF4 adds 0x18000 = 1.5 px to Camera+0x34 on each of the ten slide-out calls,
asm03_0.s:1099-1104; the slide-in subtracts it, :964-969), so a row that starts with the window open must
start with the camera at the panned position -- and (b) the Mettaur's pose: canon holds CurState/CurAction
4/11 (its attack pose, frozen under the custom-screen pause) where ours idles at 4/8; windowclose
27819/1938/40 is the hand icon (256 px/frame), the same held pose (205 px/frame from k=10) and the k=0
bracket (104). F37 found no fix inside ai.rs/hud.rs/emotion.rs (the freeze is a no-op there, no pan path),
so this is the battle.rs + fixture.rs follow-up it asked for.
**Do.** (1) The pan: make the camera's position follow the window's state on open as it does on close
(the slide-in routine's per-call subtract, cited), and check a row that opens the window (window, card,
cursor from CHIPSELECT) sits 15 px up on both sides on every open frame, measured per layer. (2) The
pose: seed the enemy's CurState/CurAction/animation frame from canon's RAM at the row's canon_ref through
the descriptor (peeked, F28b's pattern for MegaMan), applied at battle init, so the frozen Mettaur holds
the same pose; measure its box alone. (3) The hand icon and the k=0 bracket on windowclose against canon's
HUD element mask on that capture (F27b/F33's dispatcher tables). Each change measured alone.
**Acceptance.** cursor 0/0/170 and windowclose 0/0/40 (negatives not blind), or their per-object remainder;
window, card, wave, opening, chip-cannon, mettaur, popup, result, field 0; nothing worse.

### F37f. `windowclose` k=0..9: the 162 px marcher on the slide frames (custom.rs)  *(OPEN -- 2026-09-14)*

**Files.** src/custom.rs, tools/harness.py (the windowclose row's note)

**Why.** F37e's camera-dy floor (landed) leaves windowclose at 1458/162/40: exactly 162 px on each of nine
slide frames, the same shape marching with the slide -- a window-layer element (custom.rs) drawn one step
off during the slide-out. Identify it by OAM/tilemap on both sides on k=0..9 (which object or tile row,
its x per frame vs the slide position), find canon's draw for it in the slide routine's per-call work
(sub_8026BF4, asm03_0.s:1037-1125) and make ours draw it at the same step.
**Acceptance.** windowclose 0/0/40 (negative not blind); cursor 20 or better; window, card, wave, opening,
chip-cannon, mettaur, popup, result, field 0; nothing worse.

## T. Trace-driven porting (phase "porting", 2026-09-14; the plan in HANDOFF §1)

**Common to the T tickets.** The harness rows stay as free regression tests (every landing runs verify_rows on
wave, window, mettaur, popup, buster, result, field and the row a ticket names). Acceptance in this phase is
stated as state parity: "first divergence at frame N or later on scenario S", with pixels as the gate on the
same recording. Canon never changes; provenance rules as before; cite reference/bn6f file:line.

### T1. The state-trace harness: record canon's battle state per frame, replay ours, name the first divergence  *(PARTIAL -- 2026-09-14, trace harness works, KEPT unmerged [branch wt/t1-trace 147bb0a+1ee6705]: record/diff on battle_full+3 rows, ca)*

**Result.** trace harness works, KEPT unmerged (branch wt/t1-trace 147bb0a+1ee6705): record/diff on battle_full+3 rows, calibration agrees with oracle, negative live; BLOCKERS: per-frame export stores move field 158950/5621->158983/5654 (verifier control CONFIRMED: disabling store restores baseline exactly) -- needs conditional/zero-cost-when-off export; scope: actor.rs/backdrop.rs/battle.rs sites necessary per verifier (ticket file-list under-scoped, follow-up must name them); rng k=271 + RESULT dismissal unconfirmed per report; worker muse-spark, verifier GLM
**Files.** tools/trace.py (new), tools/states.py (scenario recipes), tools/mgba_capture.c (only if --watch needs a per-frame multi-field form), src/main.rs and src/fixture.rs (the oracle export block, widened and versioned), AGENT_GUIDE.md (the trace commands)

**Why.** The oracle (tools/oracle.py) compares a 40-byte export block per frame on one row; the next phase needs the
same over whole scripted battles. Field set, both sides, per frame: MegaMan's BattleObject (0x0203a9b0: CurState +8,
CurAction +9, HP +0x24, panel +0x12/+0x13, Timer +0x20, the mercy counter via CollisionDataPtr +0x54 -> +0x24),
the three enemy slots (0x0203aa88/0x0203ab60/0x0203ac38, same fields), the banner sequencer (0x0203CA70), the
battle-HUD element mask (0x020352C0 update and draw words), the custom gauge, the camera (Camera+0x34, find the
base from sub_8026BF4's use, asm03_0.s:1099), the backdrop counters (0x02009690/94) and GFX anim state
(0x020094c0), the RNG seed (0x020013f0). Ours exports the same fields through the ORCL block (0x02000008 today;
widen to a versioned block in a region measured free -- 0x02000080 collides with agb's sprite loader, R6).
**Do.** (1) `tools/trace.py record <side> <scenario> --out DIR`: runs the scenario's recipe and input script on
one side and writes a per-frame table of the field set (canon via mgba_capture --watch, ours via the export
block); (2) `tools/trace.py diff canon.dir rust.dir --align <event>`: aligns on a measured event (the sequencer's
BATTLE START state, or a row's Align) and prints the first divergent field and frame, then the divergence list;
(3) scenarios in tools/states.py: `battle_full` (from BATTLE START, a fixed input script: open the custom
screen, pick Cannon, fire, take the Mettaur's shockwave, win, dismiss RESULT) on both sides, plus the existing
rows' scenarios; (4) calibration: on mettaur, popup and result the trace's first divergence must agree with
tools/oracle.py's (or explain the difference); (5) the negative control: a one-frame shift of the canon trace
must produce a divergence at frame 0. **Acceptance.** the two commands work on `battle_full` and three rows with
the calibration and the negative shown; AGENT_GUIDE.md documents them in ten lines.

### T1b. Land the trace harness with a zero-cost export: the stores only when tracing is on  *(OPEN -- 2026-09-14)*

**Files.** src/main.rs, src/fixture.rs, src/actor.rs, src/backdrop.rs, src/battle.rs (the export sites only), tools/trace.py, tools/states.py, AGENT_GUIDE.md

**Why.** T1's harness works and is kept on wt/t1-trace (147bb0a: the versioned TRC2 64-byte export block at
0x02000080, linker-placed; 1ee6705: record/diff, scenarios, docs; calibration agrees with the oracle on three
rows, the negative control is live). It could not land because the per-frame export stores move field
integrated 158950 -> 158983 (the verifier's control confirmed: disabling the stores restores the baseline
exactly): extra work per frame shifts a mid-frame write, the class F30 measured. The pixel rows must run
with the export off and byte-identical to main; only trace recordings turn it on.
**Do.** Start with `bash tools/worktree.sh t1b-trace-land` then `git merge wt/t1-trace`. Gate every export
store on one flag read once per frame (a fixture descriptor bit, provenance peeked, or a marker byte the
trace recorder pokes at load): when off, no store executes on any path; when on, the block is written every
frame. Prove it: with the flag off, the release .gba's behaviour is byte-identical to main on the full table
(every row, both variants, identical lines; field integrated 158950 back); with the flag on, `tools/trace.py
record rust battle_full` and the three calibration rows reproduce T1's results, and the negative control
still fires. Confirm the two items T1 left unconfirmed (the RNG field at k=271, the RESULT dismissal in
battle_full). **Acceptance.** full table identical to main with the flag off; T1's record/diff/calibration/
negative with the flag on; AGENT_GUIDE.md's ten lines on the trace commands.

### T2. Coverage: which canon routines each scenario executes, ranked  *(OPEN -- 2026-09-14)*

**Files.** tools/coverage.py (new), docs/coverage/ (new), tools/states.py (read)

**Why.** The porting queue must come from what canon runs, not from guesses. The bn6f fork's master branch
carries a profiler (a function map plus libmgba coverage) -- the submodule at reference/bn6f points at the
bn-notes branch; clone the fork's master into /tmp (never change the submodule) and use its tooling.
**Do.** `tools/coverage.py <scenario>`: run canon on the scenario's recipe and input script under the profiler,
and write docs/coverage/<scenario>.md: every routine executed, with call counts and the first frame it ran,
ranked by count, each named by the disassembly's symbol and file:line; a second table of routines executed
in `battle_full` but not in any existing harness row's scenario (the uncovered set). **Acceptance.** the two
tables for `battle_full` and for the mettaur row's scenario; the interpreters named in HANDOFF §1 (animation
bytecode player, object dispatcher, script VMs) located in the ranking with their symbols.

### F37e. `windowclose` k=0..9: the objects and camera during the ten slide-out frames  *(PARTIAL -- 2026-09-14, cam_dy floor-fix KEPT unmerged [branch wt/f37e 06fa98d]: windowclose 4943/1116/40->1458/162/40 [enemy+MegaMan )*

**Result.** cam_dy floor-fix KEPT unmerged (branch wt/f37e 06fa98d): windowclose 4943/1116/40->1458/162/40 (enemy+MegaMan gone, 162x9 marcher for custom.rs); cursor 8->20 REGRESSION (deterministic, k37/k97 race, blocks landing); verifier CONFIRMED no-skew watch + asr floor mechanism + scope/no-op; marcher ID + race-flip attribution unchecked-consistent; worker muse-spark, verifier GLM Human decision (2026-09-14 06:30): landed anyway -- the camera-dy floor is canon's mechanism (asr) and takes windowclose 4943 -> 1458; the cursor 8 -> 20 is the F35 sub-frame race flipping on the same two frames (k=37/97), a class already blocked on its own ticket (archived), recorded there; the 162x9 marcher is F37f.
**Files.** src/battle.rs (the camera pan on the slide calls and the objects' offset from it), src/actor.rs (object Y under the camera), tools/harness.py (the windowclose row's note)

**Why.** F37d landed the Mettaur's pickaxe prime: cursor 34902 -> 8/6/170 (two micro frames, k=37/97, the
sub-frame queue-drain class F35 mapped) and windowclose 12538 -> 4943/1116/40 with k=10..39 all 0. The whole
4943 is on the ten slide-out frames k=0..9: F29 drives the field's camera pan from the slide calls (1.5 px
per call, floor) and F37c made the objects follow the camera once the window is open, but during the slide
itself the objects and the camera are one step apart on some frames (which side leads is what to measure).
Watch canon's Camera+0x34 and MegaMan's OAM Y per frame across the slide (asm03_0.s:1099-1104 and the
object draw's camera subtract), the same on ours, and make the objects read the camera value canon's draw
reads on that frame (before or after the slide call's add).
**Acceptance.** windowclose 0/0/40 (negative not blind); cursor 8 or better; window, card, wave, opening,
chip-cannon, mettaur, popup, result, field 0; nothing worse.

### F32b. The end sequence as canon's sequencer states, from the killing blow to the results window's first slide frame  *(PARTIAL -- 2026-09-14, end-sequence watched per row, landed 8e44d2e [comments+assert only, zero behavior change]: 0x0C@47/teardown@48)*

**Result.** end-sequence watched per row, landed 8e44d2e (comments+assert only, zero behavior change): 0x0C@47/teardown@48/banner 49..106/slide 154..168 all rows; banner+2 costs field +4 (verifier independently reproduced 158950->158954); one schedule cannot serve warp-72 vs buster-122 (field score-locked); slide-px values + 12px path untraced per report; HEAD re-check PASS; worker muse-spark, verifier GLM
**Files.** src/battle.rs (the end-sequence state machine: over, BANNER_TO_RESULTS, the results hand-off), src/banner.rs, src/results.rs, tools/harness.py (the integrated rows' notes and the ZERO_ENEMY flags)

**Why.** F38b measured why the resolve flag cannot work with our end sequence as it is: with the flag, our
`over` fires at capture 8 and our results window shows near capture 110, while canon's slide starts at
k=24..29 on warp/buster/chip-use; one constant (BANNER_TO_RESULTS, also field's) cannot sit at both, and the
banner tail leaks into the isolated rows (warp 0 -> 5123, buster 0 -> 2286, chip-use 0 -> 4026, all reverted).
F32 landed only the first count (35 updates from the killing blow to 0x0C). Canon's end is a sequence of
sequencer states with their own counts: 0x0C at 47 (F27b's watch), the HUD teardown at 48, the ENEMY
DELETED banner up 49..106 (sub_801E792 asm00_2.s:31055-31112), then the results window's driver
(sub_802BD60 chain, F21/F34). Measure the whole sequence on canon per row (dword_203CA70 transitions, the
banner element's mask bit, the window driver's first state frame) on the result_arrival route and on the
three zero-enemy rows, and port the counts as canon's state machine, replacing BANNER_TO_RESULTS; field's
fixture (which already resolves) must land on the same frames it does today.
**Acceptance.** the frame of the results window's first slide equal on both sides on all four rows (watched);
warp, buster, chip-use integrated 0 or their per-frame remainder against F34's chain; field integrated
unchanged or better; every isolated row and result 0; nothing worse. Human decision (2026-09-14 05:20): a
third ticket on this objective is allowed because F38b's finding is a measured mechanism, not a guess.

### F37d. The Mettaur's pickaxe object during the held attack pose (cursor 34902, windowclose 12538)  *(PARTIAL -- 2026-09-14, pickaxe prime landed 91f766e: cursor 34902/232/170->8/6/170 [k37/k97 micro], windowclose 12538/1200/40->4943/1)*

**Result.** pickaxe prime landed 91f766e: cursor 34902/232/170->8/6/170 (k37/k97 micro), windowclose 12538/1200/40->4943/1116/40 (k10-39 all 0; k0-9 slide residue for camera owner); no new art (mettaur.bin had frame); verifier: freeze-holds-prime + battle.rs-only-trigger CONFIRMED, 7..14-invariance REFUTED (7->7px vs 9->8px), Unk_02=4 unlocated; HEAD re-check PASS (windowclose neg fixture-noise 212849/205769); mettaur+9 canaries 0; worker muse-spark, verifier GLM
**Files.** src/ai.rs, src/spr.rs, src/actor.rs (only if the object attaches through the actor), assets/ (art extracted from the canon ROM only), tools/harness.py (the two rows' notes)

**Why.** F37c landed the camera pan for the objects and the k=0 bracket: cursor 130221 -> 34902/232/170,
windowclose 19168 -> 12538/1200/40, and refuted the pose-frame theory (canon's Unk_02 = 0 is our frame 0).
Its verified remainder is one object at ~205 px/frame: canon's Mettaur holds its attack pose under the
custom-screen pause with its pickaxe drawn as a separate object, and ours draws no pickaxe (34902 over 170
frames and 12538 over 40 are that object plus little else). Find the object in canon: its spawn from the
Mettaur's attack routine (the sub_8109DEC family / the swing state that F17 and F25 cited), its object type
and sprite (OAM dump on the row's canon capture: tile, palette, size, position relative to the Mettaur),
and its lifetime under the pause; extract its art byte for byte from the ROM if ours lacks it, and spawn
it from the same state with the same offset, cited.
**Acceptance.** cursor 0/0/170 and windowclose 0/0/40 (negatives not blind) or the per-object remainder;
mettaur (the row where the pickaxe swings live) 0 unchanged; window, card, wave, opening, chip-cannon,
popup, result, field 0; nothing worse.

### F38b. The integrated rows' results window: resolve the zero-enemy battle where canon does, now that `over` no longer freezes  *(NEGATIVE -- 2026-09-14, resolve-flag retry refuted post-F33d, notes landed 66a6a3c [zero pixel effect]: warp 40628->45751 [isolated 0-)*

**Result.** resolve-flag retry refuted post-F33d, notes landed 66a6a3c (zero pixel effect): warp 40628->45751 (isolated 0->5123 banner tail), buster 54672->81083 (isolated 0->2286), chip-use 275307->269172 (isolated 0->4026), all reverted; our over@capture-8/show~110 cannot sit at canon k=24..29 with one BANNER_TO_RESULTS (untouched for field); sequencer 0x0C@47 re-watched; allowlist kept; HEAD result re-check MATCH; no third ticket on this objective (F38 PARTIAL + F38b NEGATIVE); worker muse-spark
**Files.** tools/harness.py (ZERO_ENEMY's flags and the warp/buster/chip-use integrated rows' Align notes), src/battle.rs (the end-sequence / results hand-off hunk only), src/results.rs

**Why.** F38's decomposition (07ad4e3): warp integrated 40628, buster 54672 and chip-use 275307 are canon's
RESULT window sliding in with no counterpart on our side, because the zero-enemy fixture never resolves.
F33c had tried FLAG_RESOLVE_OVER and measured it worse (warp 40628 -> 83175) because our `over` state then
froze inputs and parked the banner tail; F33d removed that freeze (inputs and objects keep running after
the countdown, canon's 0x0C handler cited). So the flag may now do what it should: retry it on the rows
whose canon side resolves (the sequencer reaches 0x0C at canon 47 on all four; the RESULT slide starts at
canon 154 on warp), lock our slide's first frame to the same sequencer event (dword_203CA70 -> 0x0C, then
the window driver's first state, watched on both sides), and compare the window's slide frame by frame
against F34's driver chain (sub_802BD60 -> sub_802BE36 at 16 px/frame). chip-use's honest lock is 101
(remainder 281885 there). field integrated 158949 keeps its stall attribution (F33b/F33c/F38).
**Acceptance.** warp, buster, chip-use integrated 0 (negatives not blind) or their per-frame remainder with
both sides' sequencer and window-state traces; every isolated row and result unchanged at 0; an
allowlist entry removed only for a row that reads 0; nothing worse.

### F37c. `cursor` and `windowclose` remainders: the objects' Y under the camera pan, the k=0 bracket, the pose frame  *(PARTIAL -- 2026-09-14, object-Y pan + k0 bracket landed 2ecb799: cursor 130221/767/170->34902/232/170, windowclose 19168/1878/40->125)*

**Result.** object-Y pan + k0 bracket landed 2ecb799: cursor 130221/767/170->34902/232/170, windowclose 19168/1878/40->12538/1200/40; pose-frame refuted (canon Unk_02=0 = our frame 0); remainder = missing pickaxe object ~205/f needs spawn/variant ticket; verifier CONFIRMED pan/bracket/refutation + rules clean; HEAD 11-row re-verify PASS (windowclose neg 50px fixture variance); 9 canaries 0; worker muse-spark, verifier GLM
**Files.** src/actor.rs (object Y under the camera pan), src/custom.rs (the k=0 bracket), src/ai.rs (the held pose's frame)

**Why.** F37b landed the camera pan on open, the Mettaur's held pose and the hand icon: cursor 154361 ->
130221/767/170, windowclose 27819 -> 19168/1878/40 (negatives 316499/214890 not blind). Its verified
remainder, per object: the actors' sprite Y does not follow the panned camera (~765 px/frame on cursor:
canon offsets every object by the camera's Y, our field pans but the objects stay), the chip window's
bracket on windowclose's k=0 (104 px, custom.rs), and the held pose's animation frame (F37b's priming
attempt was reverted; canon's frozen Mettaur shows a specific frame of pose 4/11 -- read it from its
BattleObject's animation fields at canon_ref and cite the object's own frame selection).
**Do.** Each measured alone on both rows with a per-object split; the object-Y pan cited from the camera
routine F29/F37b used (Camera+0x34, sub_8026BF4 / the slide-in at asm03_0.s:964-969) and canon's object
draw offset (the OAM Y written from the object's Y minus the camera's), seeds only from canon's RAM at
canon_ref (peeked).
**Acceptance.** cursor 0/0/170 and windowclose 0/0/40 (negatives not blind) or the per-object remainder;
window, card, wave, opening, chip-cannon, mettaur, popup, result, field 0; nothing worse.

### F38. The integrated rows after F33d: the results window's slide on warp/buster/chip-use, and opening integrated decomposed  *(PARTIAL -- 2026-09-14, decomposition landed 07ad4e3 [notes+comment only, zero pixel effect]: warp 40628/buster 54672/chip-use 275307 )*

**Result.** decomposition landed 07ad4e3 (notes+comment only, zero pixel effect): warp 40628/buster 54672/chip-use 275307 = canon RESULT slide w/o rust counterpart; opening 72499 decomposed; field 158949 stall kept; verifier CONFIRMED warp traces/pins, scope, chip-use lock numbers (honest lock-101 remainder 281885); UNPROVEN per verifier: exact OAM census counts, show-frame region numbers, buster/chip-use traces, BG1 mechanism; HEAD result re-check MATCH; worker muse-spark, verifier GLM
**Files.** src/results.rs, src/battle.rs (the end-sequence and results hand-off hunks only), tools/harness.py (the integrated rows' notes and descriptor fields)

**Why.** With every BG layer 0 until the ramp (F33b) and inputs/objects running after the countdown (F33d),
warp integrated 40628 (from k=24), buster 54672 (name 8862 on k=1..21 + ramp from k=22) and chip-use 275307
are canon's RESULT window sliding in on frames where ours has none or a different one; F34/F34b took the
result row itself to 0 with canon's driver chain (sub_802BD60 -> sub_802BE36 slide 16 px/frame -> the
handover -> sub_802BF0C wait), so the window's content is right and what differs is WHEN and FROM WHICH
state it starts on these rows: measure the sequencer (dword_203CA70) and the window driver's state on both
sides per frame from the countdown to the first slide frame, and make ours enter the results screen at
canon's frame from the zero-enemy end sequence. opening integrated 72499/2691/40 has never been decomposed:
do it per layer and region first. field integrated 159061 keeps F33b/F33c's stall attribution.
**Acceptance.** warp, buster, chip-use integrated 0 or their per-frame remainder with the sequencer traces;
opening integrated decomposed with citations; every isolated row and the result row unchanged at 0;
allowlist entries removed only for rows that read 0; nothing worse.

### F23. Naming pass: the bare numbers in src/custom.rs and src/battle.rs  *(DONE -- 2026-09-14, results.rs naming landed b1bac4e: 81 bare->0 [46 provenance consts])*

**Result.** results.rs naming landed b1bac4e: 81 bare->0 (46 provenance consts); .text md5-identical a215f109, .gba 569764B cmp 14 panic-line bytes only; full table identical except tag rollup (derived 303->349, peeked 140->141); custom.rs/battle.rs/actor.rs/results.rs all 0 -- naming passes complete; HEAD re-check MATCH; worker muse-spark; no verifier per ticket
**Result.** actor.rs naming landed ffe8bac: 39 bare->0 (9 provenance consts); .gba byte-identical to new main (md5 dc4892e88034319179d867a5ec623b4c, 569764B, cmp 0; worker baseline 569796B superseded by human F33d landing 208c158); full table unchanged; HEAD re-check MATCH; ticket OPEN for results.rs; worker muse-spark; no verifier per ticket
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

