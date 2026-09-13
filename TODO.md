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
### F12. The chip rows' own residues, family by family  *(OPEN -- 2026-09-13, F12a minibomb family done, ticket stays OPEN for seeds)*
**Result.** F12a minibomb family done, ticket stays OPEN for seeds. chip-minibomb 10/10->0/0 (verify_rows PASS 0/0/60/17158, landed a607263); wave/window/opening-isolated/chip-cannon PASS 0; opening integrated 72499/2691 pre-existing identical on baseline; full table: energbom/megenbom -26, iceseed/grasseed 2145->2122, bugbomb 8338->8280, vdoll/suprvulc/buster/chip-use unchanged, except chip-poisseed 2145->2237 (worst 334, +92) owned by seed follow-up. Worker worker-muse (muse-spark-1.3-contributor, 75 turns, $0.068). Verifier verifier-glm (glm-5.3-flash, 18 turns, $0.016): fix code-CONFIRMED, opening pre-existing CONFIRMED, canon OAM order UNCHECKED (probe flag failure), poisseed regression PARTIALLY CONFIRMED (totals attributable, trail colors unchecked). Next: seed family (poisseed/iceseed/grasseed) with its own canon OAM dump.
**Why.** After F5b: SuprVulc 2464 / 177 / 113; the bomb, seed and VDoll rows 10 to 8338; EnergBom and
MegEnBom 19958 / 1871; the chip-family-0x15 rows 14740 to 73481. **Do:** take ONE family per run of
this ticket, smallest residue first (the rows at 10-8338), and bring its rows to 0; mark this ticket
PARTIAL with which family is done and leave it OPEN for the next family, until every chip row is 0.

- F16 DONE -- Oracle coverage: every harness row, not two. Oracle generalized to all 60 comparison rows (tools/oracle.py +138/-41, new tools/f16_slot_probe.py, export block untouched, landed ee6c494)
- F13b DONE -- `card` isolated via fixture rewire (follow-up to F13's verified negative). card 18486->0 via fixture rewire, landed 4b16fd7
- F14b PARTIAL -- `mettaur`: mercy-blink predicate bit 2 -> bit 1 (follow-up to F14's refuted negative). Blink experiment done, partial drop, landed 3e49236
- F15 DONE -- tiles/gauge: the one vblank frame, 208 px at k=7. tiles+gauge isolated 208->0, cursor unmoved 620802, landed 12a130a

### F17. `mettaur` isolated: enemy_anim k=61, the Mettaur's own animation *(OPEN -- 2026-09-13)*
**Why.** F14b landed `3e49236`: `mettaur` 31075->19698 (worst 1566->1245, 70 frames, negative frame 60824 not blind); `src/actor.rs` only, mercy-blink predicate now `(invulnerable>>1)&1`; `mm_timer` 70/70, first oracle divergence `enemy_anim` k=61 (2/70); full table exactly one row differs (improved). The mercy seed/rate and blink predicate are settled and stay untouched -- the remainder is the enemy's animation state, not a third mercy ticket.
**Do, in order.**
1. Start in `tools/worktree.sh f17-mettaur-anim`. Baseline `python3 tools/harness.py --only mettaur` (must read 19698/1245/70, negative 60824 not blind), plus `tools/diffmask.py` region and `tools/oracle.py mettaur` (must read `mm_timer` 70/70, first divergence `enemy_anim` k=61), measured.
2. Localize the `enemy_anim` k=61 frames to the Mettaur's attack element and pixels, find canon's Mettaur animation routine in `reference/bn6f` and cite it, fix `src/` only, measured on the same oracle fields and pixel frames.
3. Re-run `mettaur`, `wave`, `window`, `opening`, `chip-cannon` and the full table -- nothing may get worse, and a row that does is reported with its numbers, measured.
**Rules.** `src/` enemy-animation path only; mercy seed/rate/blink predicate and comments untouched; no allowlist change; no alignment or region change except by measured event (F2's rule); captures one at a time.
**Measure and report.** Row `mettaur` before/after (total/worst/frames) on the identical script and window, oracle `mm_timer` match count and first `enemy_anim` divergent frame before/after, full-table deltas.
**Coordinator:** `verify_rows` on every row the report names; the verifier only for claims beyond harness lines (routine identity, cause); a wrong-guess PARTIAL gets one follow-up; a second miss marks it BLOCKED and moves on.

### F18. `windowclose` isolated: the close event's remaining total *(OPEN -- 2026-09-13)*
**Why.** `windowclose` isolated reads total 695603 (worst 28784) over 40 frames at canon 81+k, rust 8+253+k (`web/captures/windowclose-isolated.txt:1`); the row note (`tools/harness.py:1477`) records the measured event: `--watch 0x020364c0:0x48` shows JumpOffset 0x04->0x08 on the A-press frame with slide counter +0x40 counting 0x0c..0x78 across canon frames 81..90, rust slide calls at capture 261..270 (marker origin 8), event offset 253 where the ten slide frames compare EXACTLY 0 on `--only-bg 3`; a deeper meaningless basin sits near offset 264 (575089 vs 695603) from unshared-battle noise; the post-close BG3 residue at the true alignment is a flat 1402 px of HUD-strip fixture content (canon gauge RESETS empty then refills rows 8..15 while descriptor gauge=1 stays full; hand chip-name rows 148..158 `Cannon 40` vs none).
**Do, in order.**
1. Start in `tools/worktree.sh f18-windowclose`. Baseline `python3 tools/harness.py --only windowclose` (695603/28784/40 at offset 253, negative confirmed not blind), plus `--only-bg 3` ten slide frames at 0 and the post-close BG3 1402 px split by element, measured.
2. Attribute the post-close residue element by element (gauge-reset/refill vs hand chip-name) to fixture content vs `src/`, citing canon's close routine in `reference/bn6f`; fix the fixture/descriptor with `peeked` provenance or `src/`, never the alignment, measured on the same band.
3. Re-run `windowclose`, `wave`, `window`, `opening`, `chip-cannon` and the full table -- nothing may get worse, and a row that does is reported with its numbers, measured.
**Rules.** `src/` or fixture/descriptor per the attribution only; no allowlist change; no alignment or region change except by measured event -- offset 253 stands unless the watch names a new event frame (F2's rule); captures one at a time.
**Measure and report.** Row `windowclose` before/after (total/worst/frames) on the identical script and window, `--only-bg 3` slide-frame totals before/after, post-close BG3 residue by element before/after, full-table deltas.
**Coordinator:** `verify_rows` on every row the report names; the verifier only for claims beyond harness lines (routine identity, fixture-content class); a wrong-guess PARTIAL gets one follow-up; a second miss marks it BLOCKED and moves on.

### F19. `popup` isolated: 107511 px over 80 frames *(OPEN -- 2026-09-13)*
**Why.** `popup` isolated reads total 107511 (worst 1348) over 80 frames at canon 43+k, rust 1(marker)+122+k, canon (sterile) (`web/captures/popup-isolated.txt:1`); canon REAL_START=43 (A pressed at 40), rust marker origin 1 with a 26-frame band holding a unique zero at offset 122; `AUDIT.md` records the attribution as 100% OBJ -- the enemy's HP digits exposed because the popup needs that tile range unzeroed.
**Do, in order.**
1. Start in `tools/worktree.sh f19-popup`. Baseline `python3 tools/harness.py --only popup` (107511/1348/80, negative confirmed not blind), plus `tools/diffmask.py` region (OBJ vs BG split) and `tools/oracle.py` where supported, measured.
2. Localize the residue to frames and the HP-digit/popup element, find canon's routine for that element in `reference/bn6f` and cite it, fix `src/` (or the fixture/descriptor with `peeked` provenance if the residue is the tile-range fixture), measured on the same frames and region.
3. Re-run `popup`, `wave`, `window`, `opening`, `chip-cannon` and the full table -- nothing may get worse, and a row that does is reported with its numbers, measured.
**Rules.** `src/` (or fixture/descriptor when the residue is the fixture) only; no allowlist change; no alignment or region change except by measured event (F2's rule); captures one at a time.
**Measure and report.** Row `popup` before/after (total/worst/frames) on the identical script and window, diffmask region before/after, full-table deltas.
**Coordinator:** `verify_rows` on every row the report names; the verifier only for claims beyond harness lines (routine identity, cause); a wrong-guess PARTIAL gets one follow-up; a second miss marks it BLOCKED and moves on.

**Common to F8-F19 unless the ticket says otherwise.** Baseline the row (harness line plus
`tools/diffmask.py` region, plus `tools/oracle.py` where the row is supported); localize the residue to
frames and an element; find canon's routine for that element in reference/bn6f and cite it; fix src/
(or the fixture/descriptor when the residue is the fixture, with `peeked` provenance); re-run the row,
wave, window, opening, chip-cannon and the full table -- nothing may get worse, and a row that does is
reported with its numbers. No allowlist change; no alignment or region change except by measured event
(F2's rule). **Coordinator:** verify_rows on every row the report names; the verifier only for claims
beyond harness lines; a PARTIAL from a wrong guess about the cause gets one follow-up ticket; if that
also fails, mark the ticket BLOCKED and move on to the next OPEN ticket.

