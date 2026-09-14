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
### F33d. Post-0x0C simulation: act after the countdown starts instead of freezing in `over` *(OPEN -- 2026-09-14)*

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
### F37. `cursor` and `windowclose`: the sprite layer, object by object  *(OPEN -- 2026-09-14)*

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

