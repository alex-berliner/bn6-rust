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

### T12. The enemy roster out of the ROM's own index tables: every enemy_idx with its think and act entry  *(DONE -- 2026-09-14, LANDED as 1d23394)*

**Result.** LANDED as 1d23394. tools/rom_enemy_tables.py + generated docs/inventory/enemies.{json,md}: 452 identity rows of byte_80182C4 (bound inferred from getBattleArmPositionMaybe_8018810, asm00_2.s:20449; last row idx 0x1C3 v=0x00/PLAYER/AI=0x30, no filler row); the ticket's 0x180 span is FOUR 0x80-byte tables (think off_8109050 32 words / Struct1 ptr off_81090D0 / Struct2 ptr off_8109150 / act off_81091D0, bound off_8109250) -- the ticket's '96 words' prediction was wrong, think is 32. Think words are CurAction-indexed state-HANDLER TABLE pointers (dispatcher passes them as an argument to battle_801B1C4, asm31.s:169395-169402) not routines: 32 distinct handler tables, 2 of which are named For*; act 0/32 named, called via bx r0. Both known-answer checks PASS (idx 0x01..0x04 -> AI 0x01 -> ForMettaur_8109EF4 asm31.s:170982; idx 0x85 -> AI 0x17 -> ForGunner_8113078 asm32.s:10123). HP moved OUT of the gap list: off_8109150 -> elem_hp u16 @0x00 with spot-checks Mettaur 0x0028 and Gunner 0x003C, matching canon's slots in the poked Gunner battle. Cross-check coverage stated honestly: think 32/32, act 11/32 (21 act entries are suffix-less nullsub_* with no address), 0 mismatches where checked; AIIndex<32 holds for non-PLAYER rows only (PLAYER max 0x30, rows 0x1B3..0x1C3 listed as missing from both tables, not dropped). Verifiers (qwen3.8-flash, 2 passes): first REFUTED three claims -- 5 'unresolved' think entries are :: data labels in data/dat31.s:377/1123/1450/1960/2362 (the tool scanned only asm/*.s with a single-colon regex), the three-table structure, and the think-is-a-routine reading -- all fixed in e19f298; second pass CONFIRMED all four re-checks + rules audit + byte-identical regeneration. Rows: canaries identical to HEAD before and after the merge (mettaur 0/0/70/41734, wave 0/0/90/3840); zero captures by this ticket, rollup untouched. Child glm-5.3-flash 61+ turns $0.131 (initial) + fix pass, 2 verifier passes, judge $0.0782 wrote the ticket.
**Files.** tools/rom_enemy_tables.py (new), docs/inventory/enemies.json (new), docs/inventory/enemies.md (new), reference/bn6f (read)

**Why.** M1 (the lowest unmet milestone in docs/SCOPE.md) is gated on T10, and T10 cannot share a shift with T9c because its `**Files.**` line carries `docs/coverage/`. The enemy column set can be built today with zero overlap and zero captures. The ROM's own identity table is already located: `GetVerActorTyAndAIIdx_80182B4 (enemy_idx: u16) -> *const (version: u8, ActorType, ai_index: u8)` returns `&byte_80182C4[3*enemy_idx]` (asm00_2.s:19965-19974; the decompiled twin at docs/decomp/asm00_2.c:14740-14743), and the disassembly's comment on it (asm00_2.s:19963-19964) is a claim about the whole ladder: *"If we change the data here, the virus that ends up spawning will be different. In sprite, AI, attack pattern, HP, etc. Only the name of the original virus remains."* The AIIndex selects `off_8109050` (asm31.s:169420, think) and `off_81091D0` (asm31.s:169615, act) — a 0x180-byte span = **96 words** — and T9b used exactly this to find the Gunner (enemy_idx 0x85 → AIIndex 0x17 → `ForGunner_8113078`, asm31.s:169468, act 0x0810962b) and T6 landed `ForMettaur_8109EF4` (asm31.s:170982, table 170982-171012) whose rows 0x01..0x04 all carry AIIndex 0x01 (asm00_2.s:19980-19983). So the table is machine-readable, its bounds are self-stating, and **two known answers exist to check it against** — which is what makes this a cheap M1 pilot rather than a guess at wikis.

**Do.**
1. Parse `byte_80182C4` in 3-byte rows (version, ActorType, AIIndex) from 0x080182C4 to the next label in asm00_2.s → *report the row count N, the last row's three bytes, and that N ≥ 0x86 (the Gunner's idx must be inside it) with no row landing on a `.balign`/pointer filler.*
2. Parse `off_8109050` and `off_81091D0` to their own next labels → *report both lengths in words (expect 96 for the first, state the second's real value) and assert max(AIIndex used in step 1) < min(both); report any index whose think and act entries disagree in existence, listed, not dropped.*
3. Resolve every entry word to a symbol + `file:line` from the disassembly's labels → *report X of Y think entries resolving to a named `For*_HHHHHHHH` routine and the remainder to `sub_*` or unresolved, and the count of **distinct** routines = the family count M5's queue is ordered by.*
4. Emit `docs/inventory/enemies.json` (one record per enemy_idx, every field carrying `symbol:file:line`) and a generated `docs/inventory/enemies.md` grouped by family, sizes of each family stated → *report the two known-answer checks: idx 0x01..0x04 → AIIndex 0x01 → `ForMettaur_8109EF4`, and idx 0x85 → AIIndex 0x17 → `ForGunner_8113078`, both PASS (a FAIL is this ticket's headline result, not a footnote).*
5. State the boundary honestly → *report which M1 columns these two tables do NOT supply (NameID, HP, sprite pointer, per-version parameter tables, Navi bosses, formations/BattleSettings records) and write them as the named gap list T10 must cover, without chasing them (≤2 greps each for an anchor, then stop).*

**Rules.** No captures at all — this is the one ticket that cannot contend with T9c for a capture slot or a build lock. No edit to `src/*`, `tools/states.py`, `tools/harness.py`, `tools/trace.py`, `tools/mgba_capture.c`, `FIXTURE.md`, `docs/SCOPE.md`, `reference/bn6f` (read-only). `docs/coverage/` stays untouched: no `coverage.py` run, since its writer emits there. `docs/inventory/` is a **new** directory and `enemies.md` is generated by the tool, never hand-typed, so the counts are reproducible by `python3 tools/rom_enemy_tables.py > docs/inventory/enemies.json`. Enum names (`ACTOR_TYPE_VIRUS`) come from `constants/enums/` with a line cite, or the row reports the raw byte. No row without a citation; a row whose bound is inferred from the next label says "bound inferred from <label>".

**Measure and report.** row: none (no harness row exists or changes; report the 59-row rollup untouched). frames: n/a — zero captures. total/worst: N enemy rows, 96/96 word entries parsed, X/Y routines named, family count F. region: `docs/inventory/enemies.{json,md}`. commit: tool + two generated docs. Mechanism: the ROM's own two index tables parsed to their own bounds, checked against the two routines T6/T9b already proved. Unverified: that every family has a distinct routine *per version* (the six per-version parameter tables T9b cited for the Gunner are out of scope here), and that the boss Navis share these tables at all.

**Coordinator:** ~$0.03, no build, no capture — the right thing to run while T9c is mid-capture or LTO-ing. Note before dispatch: T10's `docs/coverage/` entry is marked *(read)*, and a read needs no write permit; if you drop it from T10's `**Files.**` line T10 pairs with T9c outright and this ticket collapses into T10's enemy section (tell that worker `tools/rom_enemy_tables.py` exists and to import it rather than re-derive). If you keep T10 as it stands, land this first and hand it over as the pattern.

---

### T7d. Drive the sequencer's window states with a fixture that closes the window, and put canon's predicates under the edges  *(PARTIAL -- 2026-09-14, Kept UNMERGED at wt/t7d @ 24d9ef7 [8daa88d + 24d9ef7 on a merge of wt/t7c @ 9be540c])*

**Result.** Kept UNMERGED at wt/t7d @ 24d9ef7 (8daa88d + 24d9ef7 on a merge of wt/t7c @ 9be540c). verify_rows on the branch PASSES: 59 rows 0/0 with live negatives, cursor isolated 16/15/170/186275 (the tear: main 26/17, wt/t7c 3/2, here 16/15). WHAT LANDED ON THE BRANCH: (step 1) a new trace scenario states.TRACE_SCENARIOS['windowclose_full'] that opens AND closes the chip window -- CONFIRMED by the verifier re-recording on the current build (it caught that the retained table was from pre-battle.rs-edit 9be540c and re-measured): rust 0x24 0..21, 0x00 22..24 (3), 0x04 25..84 (60), 0x08 85..169; canon 0x24 0..143, 0x00 144..146, 0x04 147..206, 0x08 207..243; trace.py diff --align sequencer=0x0 reads sequencer match 100/100 (canon 144+k <-> rust export 262+k, shift 0), only enemy_state_action (4,11) vs (4,9) and enemy_anim diverge, 33/100, which is F37's frozen executor pose. The canon ranges are byte-identical AS FULL DWORDS to the stored battle_full record (rows 144..206), so the route-independence claim holds and T7c's refutation is answered for the coverage half: 0x00 and 0x04 are now each entered AND LEFT on both sides. (step 2) src/battle.rs: the three fitted edges given named canon-predicate traps plus a genuine latch2 port of canon's [r5+2] byte (cleared by transition the way canon's str r0,[r5] zeroes byte 2, and INDEPENDENTLY EVIDENCED IN CANON'S OWN DATA: row 144 reads byte2=0, rows 145..146 read byte2=4, i.e. the latch is set during 0x00), and both T7c citations fixed (the 0x08->0x20 write is asm00_1.s:10609-10611 with sub_800A244 at 10585; sub_801483C's call sites are 10958 and 11022) -- both CONFIRMED, and no stale 10527-10537/10841 cite survives. SEQ04_FRAMES=60 retagged derived -> peeked with two-record prose, an HONEST tag (both measurements check out); index wart noted: the comment says battle_full k=136..195 while the same record's rows are 147..206 (battle_full's canon_ref 11 offset), two zero-points in one paragraph. sub_8008492 never writes the state word: CONFIRMED (its body writes only [r5,#2] at 11030 and [r5,#4]=6 at 11033-11034). WHY NOT MERGED -- the verifier's claim-2 verdict is MIXED: two of the three traps are still run counts wearing a name, exactly the distinction T7c was refused for. The 0x20 trap is age>=1 and never reads byte_203C974 (which sub_802D6C4 returns, armed by sub_802D6A0, cleared only when both players' entry machines report done, asm03_0.s:15124-15134); the 0x00 state's idle half is age>=1 where canon reads dword_20367F0's done byte; the 0x04 trap is age+1>=SEQ04_FRAMES, a pure frame count, while canon tests sub_801E754 = dword_20352C0 & 0x8000 (asm00_2.s:31012-31020) at asm00_1.s:10500-10502 -- and the rust windowclose_full record already exports a hud_mask field, so a mask-reading predicate looks reachable. NEW CITATION DEFECT of the same class T7c was hit for: the report cites 10508-10512 for the 0x04 test, which covers the 0x08 write, not the bl/cmp/bne at 10500-10502; and the 0x20 and 0x24 cited ranges stop one to two lines short of the writes they name. Also a merge-review regression against the branch this one builds on: cursor 3/2 -> 16/15 and field's allowed row 158953 -> 158979 (both already-failing rows, harness verdict unchanged, reported per the phase rule). UNCHANGED AS CLAIMED, CONFIRMED by fresh capture: battle_full reads 0x08 rows 0..296 then 0x0C 297..542 with gauge 0 on 0 of 540 rows, so its 173 divergent frames are still 165 window-setup + 8 kill-timing; result reads 0x0C on all 40 rows (verifier compared the field directly, not via diff, having removed its worktree first). Rules audit CLEAN: harness.py +17 all-comment, states.py adds only a trace record (no CHECKS row, cannot go blind), trace.py untouched so T7b's missing-field hard failure stands, reference/bn6f untouched, battle.rs step-2 hunks confined to SEQ04_FRAMES/Sequencer/the three traps and three edge arms (the over predicate and DISSOLVE_FRAMES seed changes in main...HEAD come from the T7c merge). NO THIRD TICKET on this objective per the two-in-a-row rule (T7c PARTIAL then T7d PARTIAL); the residual is recorded here: replace the three counts with byte_203C974 / dword_20367F0 / mask 0x8000 reads and fix the three short cites. Child qwen3.8-flash 2 commits; verifier glm-5.3-flash CONFIRMED claims 1,3,4,5 and the rules audit, MIXED on 2.
**Files.** tools/states.py (the scenario that opens and then closes the chip window), src/battle.rs (the four
sequencer edges only), tools/trace.py (only if a field must be watched to see an edge), docs/coverage/
(notes), and the two citation fixes in src/battle.rs's comments

**Why.** follows T7c (PARTIAL, kept unmerged at wt/t7c @ 510b5c6, which carries wt/t7's banner sequencer and
wt/t7b's v3 records and judge fixes -- base your worktree on wt/t7c and merge that branch into yours). T7c
ported the chip-select window's states 0x20/0x24/0x00/0x04 from sub_800801C/off_8008038 and took the
result row's sequencer to 40/40, and the verifier CONFIRMED its divergence arithmetic (on battle_full our
fixture's gauge reads 0 for all 540 frames, so the window never opens: canon's 165 window frames + 8
kill-timing frames = the 173 still divergent, named frame by frame). What it REFUTED is the exoneration of
src/battle.rs: the rows cited as exercising the handlers (mettaur 70/70, popup 80/80) contain no window
states on either side, and the three fixtures that do open the window (window, cursor, card at gauge 16384)
hold it open, so the path measured is 0x08 -> 0x20 (one frame) -> 0x24 (terminal) and **0x00 and 0x04 have
zero measured coverage**; the edges are frame-count fits (age >= 2, SEQ04_FRAMES = 60) where canon tests a
subroutine -- sub_8008452 leaves 0x20 on sub_802D6C4's return, sub_800840C gates 0x00 -> 0x04 on
sub_801483C plus the [r5+2] latch, sub_8008064 writes 0x08 only when sub_801E754's banner-idle check
returns 0 after arming timers 0x1e and 0x293 at entry. So: build the scenario that closes the window and
watch 0x24 -> 0x00 -> 0x04 -> 0x08 happen, then replace each fitted edge with the predicate it stands for
(ports of sub_802D6C4/sub_801483C/sub_801E754 as they already exist or as named traps), keeping the numbers
canon's own record shows for that path. Also fix the two wrong citation line numbers T7c's verifier found
(the 0x08 -> 0x20 write is asm00_1.s:10609-10611, not 10527-10537; the sub_801483C call sites are 10958 in
0x00 and 11022 in 0x24, not 10841).
**Acceptance.** a recorded trace pair on the closing-window scenario in which 0x00 and 0x04 are each entered
and left, with the frame ranges named; battle_full's sequencer either 540/540 unaligned or the remainder
named and shown to be kill-timing setup only; result's sequencer still 40/40; every isolated row 0 with
cursor's tear reported as it moves; the two citations corrected; the SEQ04_FRAMES = 60 tag either promoted
to a ROM-sourced constant or narrowed to what it is (a fit to one record).

### T9c. The Gunner: implement what T9b measured (the frame-60 lever, enemy_kind, the routine, the art, the row)  *(PARTIAL -- 2026-09-14, CORRECTION [re-stamps my earlier entry, which cited verifier findings before the verifier had returned -- the )*

**Result.** CORRECTION (re-stamps my earlier entry, which cited verifier findings before the verifier had returned -- the merge message 1f7efc9's claim that the verifier 'named the real lever 0x02036848 / arm the queue entry' is WRONG; that candidate was in fact tested and REFUTED). LANDED as 1f7efc9 (partial, no gunner row): battlestart_gunner recipe (battlestart pokes + --poke-at 60:0x0200a210:0x371 -> BattleSettings record 6 0x080b4bd8) + per-slot enemy_kind (fixture byte +5, 2 bits/slot, kind 1 = Gunner art/style/default HP). Verifier (qwen3.8-flash, 4 canon captures) verdicts: CLAIM 1 recipe CONFIRMED -- ptr 0x080b4bd8 on all 900 frames, never 0x080b4be8; slot0 0x0203aa88 (ewram.s:2974 eT1BattleObject1) panel 0x0205/NameID 0x0001/HP 0x0028; slot1 0x0203ab60 (:2975) 0x0306/0x0085/0x003c; slot2 empty; MegaMan 0x0203a9b0 (:2973) HP 100; rng low half 0x0f46 (ewram.s:262); --poke-at is a true one-shot (mgba_capture.c:911). Nuance: slots are populated by capture frame 100, '148' was the report's probe frame. CLAIM 2 packing CONFIRMED backward-compatible -- all 5 harness enemy_kind uses pass bare 0 past the isinstance branch, src decode (fixture.rs:262) mirrors the pack; FIXTURE.md text matches code. CLAIM 3a stuckness CONFIRMED -- dword_203CA70 (ewram.s:3040) = 0 for 900 frames with NO logged write, gauge frozen 0x00200000, viruses parked st/act 0x0104 from f151. CLAIM 3b REFUTED -- the branch's proposed fix (sequencer=4 + 0x02036848:4/0x02036840:4 at f160/162) sticks 4 for 338 frames, never writes 8, gauge frozen, MegaMan never leaves (4,1) over 5 A/B presses, no damage: no attack event. The named gate was already open (dword_20352C0 bit 0x8000 clear in the poked battle), so the 4->8->UnpauseBattle causal chain is UNSUPPORTED; docs/coverage/battlestart_gunner.md must be corrected before it is copied forward. Rows: full 60-row table PASS, all isolated rows 0, mettaur 0/0/70/41734 and wave 0/0/90/3840 re-checked on the branch; cursor's single-frame tear moved HEAD 3/3/170/186279 -> branch 13/11/170/186282, which the verifier calls an UNEXPLAINED side effect of this diff, not a pre-existing tear -- reported, not chased, per this phase's rule. OWED: the gunner row+trace (blocked on finding dword_203CA70's write/advance condition, not on any proven impossibility) and the ForGunner_8113078 port. Child glm-5.3-flash 82 turns $0.303; verifier 4 captures.
**Result.** LANDED as 1f7efc9 (partial, no gunner row). Landed: battlestart_gunner recipe (battlestart pokes + --poke-at 60:0x0200a210:0x371 -> BattleSettings record 6 0x080b4bd8) and per-slot enemy_kind (fixture byte +5, 2 bits/slot; kind 1 = Gunner art/style/default HP). Verifier glm-5.3-flash: recipe CONFIRMED (settings ptr 0x080b4bd8 from f60; slot0 Mettaur panel 0x0205/NameID 0x0001/HP 0x28 at 5,2; slot1 NameID 0x0085/HP 0x3c at 6,3; slot2 empty; MegaMan (2,2)/0x64; rng 0x14CA0F46; 18/18 samples), packing CONFIRMED backward-compatible. Full 60-row table identical to HEAD except cursor's tear 13/11/170/186282 (HEAD 3/3/170/186279) -- reported, not chased; mettaur 0/0/70/41734 and wave 0/0/90/3840 both re-checked on the branch. OWED: the gunner row + trace + ForGunner_8113078 port. BLOCKER, now precisely diagnosed by the verifier: the poked battle never goes live -- sequencer 0x0203CA70 stays 0 to frame 2438 because write-mask byte 0x02036848 reads 0 for all 901 frames and NO poke in the recipe writes it, so sub_801483C (@0x080148c4 ldrb r3,[r5]; cmp #4) never releases its 4/8 writes, and the entry is never armed (sub_80141F0's caller @0x0801460e bx r1 = nullsub_57). The branch's gate-chain diagnosis was REFUTED as complete; untried fix = write 0x02036848 to 4 and arm the queue entry. Child glm-5.3-flash 82 turns $0.303; verifier 30+ turns.
**Files.** tools/states.py (the recipe), src/fixture.rs (enemy_kind honoured), src/battle.rs (the fixture's enemy construction by kind), src/objects.rs, src/ai.rs, assets/ (Gunner art extracted from the ROM), tools/harness.py (the new row), FIXTURE.md, docs/coverage/

**Why.** T9b solved T9's blocker with a reproducible lever and wrote no code: the enemy list is built inside
frame 60 by sub_80AA4C0 from the settings pointer, so poking the pointer is useless, but a one-shot poke
of iCurrFrame at frame 60 (--poke-at 60:0x0200a210:0x371, i.e. 0x372 -> 0x371) makes the roll pick
BattleSettings record 6 = 0x080b4bd8 (setup byte_80B5347: 00 22 00 00 | 11 25 01 00 | 11 36 85 00 | F0,
Mettaur + Gunner), verified by a v=0..7 sweep of the resulting pointer. The routine and art provenance
are in T9b's Result. Do T9b's four steps as code: the `battlestart_gunner` recipe with that poke and the
enemy slots confirmed populated; enemy_kind selecting art, style and per-type entry (kind 1 = Gunner;
FIXTURE.md updated); the Gunner's routine under enemy_think/enemy_act with its art byte for byte; one
harness row aligned by its first attack event.
**Acceptance.** the new row 0 (negative not blind); the trace's enemy slot matching canon from spawn through
the second attack on the Gunner scenario; every existing row unchanged; docs/coverage/<scenario>.md.

### T10. Inventory of the battle engine from the ROM's own tables: the completion checklist gets its counts  *(DONE -- 2026-09-14, LANDED as d0e0574 [two passes: 3723b5d + fix 82c31bd])*

**Result.** LANDED as d0e0574 (two passes: 3723b5d + fix 82c31bd). tools/inventory.py + 11 docs/inventory/*.json + the generated '## Per-item tables' section of docs/SCOPE.md; the human's prose above the marker (lines 1-34) is byte-identical (md5 435fde301973de80462fdc16c962d318 both sides; the single deleted line was the human's own placeholder under the marker). Counts: 411 chips / 63 PA records (64 pointer words less off_802BCB0's terminator .word NULL at asm/asm03_0.s:11546, named in generated text and re-read by me) / 32 families + 187 ranks IMPORTED via T12's rom_enemy_tables.py, never re-derived (enemies.json md5 d10e6b028aff010b71b9b07271ed6248 unchanged) / 25 navis / 14 cybeast TF values / 25 TF forms with 148-word charge-shot table off_80117D4 keeping 25 in-range + 123 unclaimed / 13 panels DERIVED-FROM-CODE / 69 status bits DERIVED-FROM-HEADERS / 461 BattleSettings records + 297 formation arrays marked PROVISIONAL with the reader's check spelled out / 3 background values with 0xff on 268/461 stated as an UNSET sentinel / NaviCust program-id table a GAP with its search trail in the doc. elem_hp caveat now in the generated text (high nibble = element, HP = low 12 bits per asm00_2.s:683; offset 0 = row 0 of a row-per-level struct: Mettaur 0x0028/0x0050/0x0078/0x00A0). Backing rows exist for both verified items: Mettaur V1 at SCOPE.md:545 (verified) and exactly 43 verified-pixels chip rows (auditor counted 43). Tool gained BN6F_REF + ensure_ref() for the gitlink trap. Regeneration deterministic: 13/13 artifacts byte-identical on a double run. Auditor (qwen3.8-flash) verdicts: (1) CONFIRMED human prose, (2) CONFIRMED generation byte-identical, (3) import CONFIRMED / caveat REFUTED then fixed, (4) citations: 411 and 25 and 148=25+123 and 25/25/25 CONFIRMED, PA 63 REFUTED-as-stated (64 words) then fixed, 461/297 UNCHECKED and now labelled provisional, (5) gaps CONFIRMED written in the doc with two defects (backdrop 0xff sentinel, a truncated cite cell), (6) Mettaur verified row REFUTED (never emitted) then fixed, rules audit CONFIRMED clean. Zero captures; canaries identical before and after the merge (mettaur 0/0/70/41734, wave 0/0/90/3840). KNOWN POLLUTION handed on: daily_review.sh:37 greps '^\| M[0-9]' from docs/SCOPE.md so the generated per-category rows now print in the milestone block. Child glm-5.3-flash 2 passes; auditor 1 pass.
**Files.** tools/inventory.py (new), docs/SCOPE.md (the counts and per-item checklist), docs/coverage/ (read), reference/bn6f (read)

**Why.** docs/SCOPE.md (written by the human session) is the completion ladder for the whole battle engine;
its items must come from the ROM, not from wikis. Enumerate from reference/bn6f's data tables, each with
the symbol and file:line of the table: every battle chip (id, name, codes, class standard/mega/giga/secret,
element, damage), every Program Advance (recipe and result), every virus family and rank (name id, HP,
element, the per-type entry routine), every Navi boss and the Cybeasts (name id, HP, entry routine), the
player forms present in this ROM (Crosses, Beast Out, Beast Over, Cross Beast) with their charge shots, the
panel types with their effect routines, the statuses, the encounter formation tables and BattleSettings
records, the arena backdrops, and the Navi Customizer programs that alter battle. Write them as
machine-readable tables (docs/SCOPE.md sections generated from tools/inventory.py output, one line per item
with a status column: unrecorded / recorded / ported / verified) so tools/daily_review.sh can count
"verified / total" per milestone.
**Acceptance.** every list produced with its ROM table cited; counts stated; docs/SCOPE.md's per-item tables
regenerated by the tool; the two items already verified (the Mettaur, and the 43 chip rows' pixel rows)
marked at their true status (pixel-verified through our code, not yet "as data").

### T7c. The sequencer's missing states: the custom-screen states our side never reads, and the end edge nine frames early  *(PARTIAL -- 2026-09-14, Kept UNMERGED at wt/t7c @ 510b5c6 [2 commits 3def49e, 510b5c6])*

**Result.** Kept UNMERGED at wt/t7c @ 510b5c6 (2 commits 3def49e, 510b5c6). verify_rows on the branch PASSES (59 rows 0/0 with live negatives, cursor isolated 3/2/170/186277 -- its tear shrank again with the binary), and the result row's sequencer is now 40/40 (canon 0x0C at k=0, was 0/40), but the headline acceptance 'battle_full sequencer 540/540 without re-alignment' is NOT met: 173/540 still divergent. Landed on the branch: src/battle.rs ports the chip-select window's own sequencer states from sub_800801C/off_8008038 -- 0x08 writes 0x20 on the window-open update, 0x20 (sub_8008452) -> 0x24 on its second handler run, 0x24 (sub_8008492) holds while the window is up and leaves on the Done edge, 0x00 (sub_800840C) settles 3 frames, 0x04 (sub_8008064) waits out the banner record (SEQ04_FRAMES = 60) then writes 0x08; the end-sequence test narrowed from state != SEQ_08 to matches!(state, SEQ_0C | SEQ_10); the dissolve seed now carries DISSOLVE_FRAMES (canon blow->0x0C +35, ours measured +34); a fixture with start_state == 1 opens the sequencer at SEQ_0C. tools/harness.py change is comment-only. WHY NOT MERGED -- the verifier split the claim: CONFIRMED that our side never enters the window states on battle_full (fresh 540-frame record reads sequencer {0x08,0x0C} only AND gauge {0} for all 540 frames, so the open-window branch is unreachable) and that the arithmetic closes exactly (canon's stored record: 0x1c 0..10, 0x08 11..41, 0x20 42..43, 0x24 44..143, 0x00 144..146, 0x04 147..206 = 60 frames, 0x08 207..315, 0x0C 316..; 165 window frames + 8 kill-timing frames = 173, and our 0x0C at 297 vs canon k=305 is the +35 seed working). REFUTED the exoneration of src/battle.rs: the mettaur/popup rows the report cited as exercising the handlers contain NO window states at all on either side (canon-met {0x1c,0x8} over 214 rows, canon-pop {0x1c,0x8} over 127, rust 0x08 only), so the 70/70 and 80/80 matches prove only that the port did not break the 0x08 path; three window-opening fixtures (window/cursor/card, gauge 16384 + FLAG_OPEN_WINDOW) drive 0x08 k=8..132, 0x20 for 1 frame, 0x24 to the end and NEVER reach 0x00 or 0x04, so those two arms have zero measured coverage; and the edges are frame-count fits where canon tests a subroutine -- sub_8008452 leaves 0x20 on sub_802D6C4's return (asm00_1.s ~11003-11008), sub_800840C gates on sub_801483C + the [r5+2] latch (10947-10976), sub_8008064 writes 0x08 only when sub_801E754's banner-idle check returns 0 after arming timers 0x1e and 0x293 (10478-10514). Handler identity and table order CONFIRMED (entries 0/1/8/9 = 0x00/0x04/0x20/0x24, str r0,[r5] clears the entry byte, and sub_80080D2 writes #0x20 right after bl PauseBattle on the sub_800A244 path, contradicting the stale header annotation in the same file -- T7c's reading is the right one). Two citation defects to fix on the next pass: battle.rs cites asm00_1.s:10527-10537 for the 0x08->0x20 write (actual 10609-10611; 10527-10537 is the sub_800A152==7 / 0x1c branch) and :10841 for the 0x24 leave (actual sub_801483C call sites 10958 in 0x00 and 11022 in 0x24; 10841 is inside sub_800834A's jump table); and SEQ04_FRAMES = 60 is tagged derived from battle_full's trace alone, which is narrower than its prose claim of the same wait on every route. Second claim CONFIRMED CLEAN: the result row's 0x0C is honoured from the fixture's own start_state (FIXTURE.md +40, src/fixture.rs:333, only RESULT_ROW/RESULTMATCH_ROW set it) and battle_full still opens at 0x08 for 297 frames on the same binary, so it is not a hardwire -- inherited wrinkle named: arrived_at_result() hardcodes the WIN count for any start_state==1 fixture, a losing arrival would read 0x10, no fixture asks today. Battery after: integrated opening 72499 =, warp 40628 =, buster 54672 =, chip-use 275307 =, field 158979 (was 158953, allowed single-frame row, same layout-tear class); nothing else moved. NEXT TICKET per the verifier: a window-CLOSING fixture that actually drives 0x24 -> 0x00 -> 0x04 -> 0x08 (F38/F38b territory plus this branch), because fixture-only is currently unfalsifiable. Child qwen3.8-flash; verifier glm-5.3-flash (23 calls).
**Files.** src/battle.rs (the sequencer states and transitions), src/custom.rs (only where the custom screen enters and leaves), src/results.rs (only the arrival state), tools/trace.py, tools/harness.py (the integrated rows' notes)

**Why.** T7/T7b landed the banner sequencer as canon's state table with fresh trace evidence (docs/trace/t7b/):
on battle_full the sequencer field (dword_203CA70) is divergent on 174 of 540 frames, named frame by frame:
k=31..32 canon 0x20, k=33..132 canon 0x24, k=133..135 0x00, k=136..195 0x04 -- canon's chip-select and
custom-screen states, which our sequencer never enters (ours stays in the fight state while the window is
open); and k=296..304 canon 0x08/0x0C vs ours a step earlier -- our end edge is nine frames early on that
scenario (F32 set the kill-to-0x0C count on the zero-enemy fixtures; the full battle's path differs). Aligned
on the end edge, the two sides match 239/239 to the end. The result row's sequencer reads 0x08 on our side
at k=0 where canon is already 0x0C (F36's structural arrival). Port the missing states from the same table
(sub_800801C / off_8008038 handlers for 0x20, 0x24, 0x00, 0x04: what enters them, what they run each frame,
what leaves them), and find the nine frames on battle_full (watch both sides from the killing blow).
**Acceptance.** battle_full sequencer 540/540 without re-alignment; result's sequencer 0x0C at k=0; the
integrated warp/buster/chip-use rows re-measured (their slide starts on canon's frame now?); every isolated
row 0 (cursor's tear reported); nothing worse.

### T9b. The second virus (Gunner): widen the fixture to field a non-Mettaur, build the canon recipe, port its routine  *(PARTIAL -- 2026-09-14, Measurement pass, zero edits [worktree /tmp/bnwt/t9b-gunner clean at 974f154] -- T9's blocker is SOLVED and re)*

**Result.** Measurement pass, zero edits (worktree /tmp/bnwt/t9b-gunner clean at 974f154) -- T9's blocker is SOLVED and reproducible, the implementation is owed. (1) The frame-60 lever: a pre-frame-60 poke of the settings pointer 0x02001b9c is useless because sub_80AA4C0 stores and builds the enemy list inside frame 60; the working lever is iCurrFrame itself, one-shot --poke-at 60:0x0200a210:0x371 (0x372 -> 0x371, value -1, same mod-12 class as 5), which makes the roll pick BattleSettings record index 6 = 0x080b4bd8 (setup byte_80B5347 = 00 22 00 00 | 11 25 01 00 | 11 36 85 00 | F0). Verified by a v=0..7 sweep reading 0x02001b9c (v=6 -> 0x080b4be8 = record 7, battlestart's natural pick) and a 300-frame slot probe: 0x02001b9c = 0x080b4bd8 from frame 60, slots populate at frame 148 with slot0 panel 0x0205 / NameID 0x0001 / HP 0x0028 (Mettaur) and slot1 panel 0x0306 / NameID 0x0085 / HP 0x003c (the Gunner), slot2 empty. (2) The routine is located: Gunner = enemy_idx 0x85, AIIndex 0x17, think entry ForGunner_8113078, act entry 0x0810962b, CurAction table 0x00-0x0B plus the six per-version parameter tables, from byte_80182C4 / off_8109050[0x17] / off_81091D0[0x17] (asm32.s:10060-10290, asm29.s:10425). (3) ART PROVENANCE NOW PROVEN: tools/spr_export.py at comp_825BFC4 (ROM 0x0825BFC4) reproduces the pre-existing assets/gunner.bin byte-for-byte, 4588 B / 2 gfx blobs / 1 palette / 4 anims / 16 frames / 154 OAM, the same method that reproduces the known-good assets/mettaur.bin -- so T9's 'provenance unknown' is closed: the art IS ROM-derived. (4) NOT OWED-BY-BLOCKER, owed-by-budget: tools/states.py has no battlestart_gunner recipe written (the measured poke set exists only in /tmp/sweep_frame.py and /tmp/slot_probe.py), src/fixture.rs + src/battle.rs enemy_kind selection, the objects.rs/ai.rs port, and the harness row are unstarted. Baseline unchanged: all isolated rows 0, cursor 44/43/170/186276 (pre-existing on the branch's base). THE OPEN QUESTION for the user, which shapes pass three: canon record 6 fields TWO enemies, a Mettaur at (5,2) and the Gunner at (6,3), so a single-kind fixture cannot reproduce it -- the row's canon side needs either the house hide/zero technique to isolate the Gunner or enemy_kind given a per-slot form, and per-slot is a FIXTURE.md contract change. Residual risk named by the worker: the iCurrFrame nudge is only known harmless by construction (same modulo class), not checked against other mod-N readers of the frame counter. Child qwen3.8-flash, 122 turns, $0.180; no verifier (nothing merged, no claim the next step builds on).
**Files.** src/fixture.rs (enemy_kind honoured), src/battle.rs (the fixture's enemy construction: art, style and per-type entry chosen by enemy_kind), src/objects.rs, src/ai.rs, assets/ (Gunner art extracted from the ROM), tools/states.py (the recipe), tools/harness.py (the new row), FIXTURE.md, docs/coverage/

**Why.** T9 measured the two blockers and could not touch them: (1) our fixture ignores enemy_kind
(FIXTURE.md defines kind 0 only; src/battle.rs hardcodes the Mettaur's art and Style::Mettaur), so no
Gunner row can exist; (2) on the canon side the encounter roll must be set BEFORE frame 60 builds the
enemy list: the chosen BattleSettings pointer at 0x02001b9c (GameState+0x1c) goes 0 -> 0x080b4be8 on
frame 60 (= byte_80B5354, the three-Mettaur record the battlestart recipe already forces; 16-byte records;
index 6 = 0x080b4bd8 = byte_80B5347, Mettaur+Gunner 0x85); a poke at frame 61 sticks but the slots stay
empty because the list is built from the rolled pointer inside frame 60. Use the battlestart recipe's own
mechanism (its one-shot roll poke at frame 60 with EnemySetupArr) with index 6's record instead, and
confirm the slots (panel 0x0203aa9a / 0x0203ab72, NameID 0x0203aab0 / 0x0203ab88) are populated.
**Do.** (1) tools/states.py: a `battlestart_gunner` recipe forcing record index 6 at frame 60; confirm the
enemy slots and record the Gunner's per-type routine from the coverage ranking on that scenario;
(2) src/fixture.rs + src/battle.rs: enemy_kind selects art, style and the per-type entry (kind 1 = Gunner),
FIXTURE.md updated; (3) src/objects.rs + src/ai.rs: the Gunner's routine ported under enemy_think/
enemy_act with its art extracted byte for byte; (4) tools/harness.py: one row aligned by the Gunner's first
attack event, negative not blind. **Acceptance.** the new row 0; the trace's enemy slot matching canon from
spawn through the second attack on the Gunner scenario; every existing row unchanged (the Mettaur rows in
particular, kind 0 unchanged); docs/coverage/<scenario>.md.

### T8. Port the script VMs, per section 3 of the plan (map-script and chatbox text-script dispatch)  *(DONE -- 2026-09-14, Landed 752146e [branch wt/t8-script-vms @ cdd976e])*

**Result.** Landed 752146e (branch wt/t8-script-vms @ cdd976e). src/script.rs: MapScriptCommandJumptable ported as 71 variants (canon mov r4,#70 bound, map_script_cutscene.s:1371, leaves the 0x46 arm unreachable), TextScriptBytecodeJumptable as 27 variants indexed byte-0xE5 (chatbox.s:390-472, :545-547), eMapScriptState 0x02011E60, operand sizes from each handler's cursor arithmetic; the map/text opcodes battle_full and result exercise are implemented, everything else a named Trap carrying canon's symbol (first stop: ms_start_cutscene 0x26 at ContinuousMapScriptPtr 0x08072221). Harness (verify_rows, clean checkout, 60 rows): every isolated row 0/0 with non-blind negatives EXCEPT cursor 44/43 -> 7/6, frames 170 and negative total 186276 unchanged; rollup 'all checks pass'. Verifier (hyper/glm-5.3-flash): CONFIRMED the cursor move is binary-layout sensitivity, NOT the VMs executing -- it built the control (if false { step_frame }) in its own worktree and got total 6/6, then re-ran the SAME branch binary and also got 6/6, so VM-on vs VM-off is 0 pixels and within run-to-run wobble (+-1 positive pixel, +-4 negative); CONFIRMED first divergence unchanged (trace.py record rust battle_full 540 frames, diff vs /tmp/tr_c_bf --align row:battle_full -> enemy_state_action k=0 canon frame 11 canon=(4,10) rust=(4,0), mm_state_action not until k=179); CONFIRMED the 27-variant text table and its byte-0xE5 index in the disassembly; rules audit CLEAN (src/battle.rs touched only at the use/mod/field/single step_frame hook, no allowlist widened, no region shrunk, provenance tags present, reference/bn6f untouched). UNCHECKED by the verifier, left as a named gap, not a blocker: the exact mov r4,#70 line in RunContinuousMapScript's dump (script.rs:91-94 quotes a consistent sequence) and the claim that the 0x08072221 stream decodes down to opcode 0x26. Audit line fitted constants 19 (derived 414, peeked 145) vs main's (derived 373, peeked 142). Unverified: which later screen first reaches a Trap. Child qwen3.8-flash, 114 turns, $0.245.
**Files.** src/script.rs (new), src/battle.rs (only where a script is started or stepped), tools/trace.py (progress notes go in this ticket's Result, not the plan file)

**Why.** The third interpreter in docs/coverage/plan-interpreters.md section 3: the map-script VM and the
chatbox text-script VM with their opcode dispatch tables (3.1, 3.2), the lowest-priority of the three
because battle_full barely touches them, but the battle's chip descriptions, the results screen's text and
every later screen run on them. Port the opcode dispatch and the handful of opcodes battle_full and the
result row exercise, in the order 3.3 gives, verified per 3.4.
**Acceptance.** the dispatch tables ported with citations; the opcodes battle_full/result exercise
implemented and the rest stubbed with a named trap; full table identical; the trace's first divergence
unchanged or later; plan notes.

### T9. The second virus as a ported per-type routine, from a real battle recording  *(BLOCKED -- 2026-09-14, Blocked on a file-set widening I cannot grant)*

**Result.** Blocked on a file-set widening I cannot grant. Baseline on the clean tree: 30 rows PASS 0, cursor isolated FAILED 44/43/170/186276 (pre-existing). No Gunner row exists because the fixture cannot field a non-Mettaur: FIXTURE.md defines enemy_kind 0 only and src/battle.rs's fixture enemy construction hardcodes METTAUR art + Style::Mettaur, ignoring enemy_kind; src/battle.rs and src/fixture.rs are not in T9's Files. Measured instead: 0x02001b9c (GameState+0x1c, chosen BattleSettings ptr) goes 0->0x080b4be8 on frame 60 = byte_80B5354 (the 3 Mettaurs battlestart documents), confirming 16-byte records / index 6 = 0x080b4bd8 = byte_80B5347 (Mettaur+Gunner 0x85) and index 10 = 0x080b4c18. Decision-2(b) as handed does NOT work: a poke-at 61:0x02001b9c:0x080b4bd8 sticks (held to 118) and the transition runs 4->8->0xc, but all three enemy slots are empty at battle time (panel 0x0203aa9a/0x0203ab72=0, NameID 0x0203aab0/0x0203ab88=0) because the enemy list is built from the rolled pointer INSIDE frame 60; the frame-60 store order (or a latch at 0x02001c2c) is the next unknown, and the option-(a) roll sweep was never run (wrong capture CLI shape). Art provenance UNVERIFIED: assets/gunner.bin 4588B / cursor.bin 628B / impact.bin 2722B are not verbatim in the ROM, but neither is the known-good assets/mettaur.bin (art is LZ77 in ROM, decompressed in tree), so the only valid check is spr_dump at the Gunner's art address off GunnerEnemyStruct2_8112B9C (asm32.s:9538), not yet located; landing commit c99cece cites AI addresses and HP 0x3c but NO art address, and main.rs:84's GUNNER static is imported by nothing. Ask for the user: widen T9 to src/battle.rs + src/fixture.rs (~6+3 lines in the fixture enemy build at battle.rs ~1807 for a kind->(spr::GUNNER, ai::Style::Gunner) match, ~2 lines in fixture.rs/FIXTURE.md to allow kind<=1); everything downstream stays in the named files.
**Files.** tools/states.py (a recipe for a canon battle that fields the virus; the trace scenario is a states.py recipe, do not edit tools/trace.py), src/objects.rs (the per-type entry), src/ai.rs, assets/ (its art extracted from the ROM), tools/harness.py (a new row and its fixture), docs/coverage/

**Why.** T6 made the Mettaur canon's routine under the ported dispatcher and player; the next virus is
the test that content is now data. Pick the first virus the overworld_net route can field cheaply
(read the fork's enemy tables; the encounter roll's orbit trap is in reference/bn6f's notes: F-series
recipes force the roll at battle frame 60), build the recipe and a scenario, record canon's trace
(the enemy slot's state/action/timers from spawn), locate its per-type routine in the coverage
ranking for that scenario (tools/coverage.py), port it under enemy_think/enemy_act with its art
extracted byte for byte, and add one harness row for it (aligned by its first attack event).
**Acceptance.** the new row 0 (negative not blind); the trace's enemy slot matching canon from spawn
through its second attack; every existing row unchanged; the coverage table for the scenario in
docs/coverage/.

### T6. The Mettaur as canon's per-type routine: replace the hand-written brain with the ported AI entry  *(DONE -- 2026-09-14, Mettaur brain now canon per-type entry MettaurEntry ForMettaur_8109EF4 [objects.rs], hand-written MettaurState)*

**Result.** Mettaur brain now canon per-type entry MettaurEntry ForMettaur_8109EF4 (objects.rs), hand-written MettaurState removed (ai.rs), battle.rs 1 comment line, plan notes S2.6. verify_rows: full isolated table 0 except cursor 44/43 MATCH (same k37+k97 tear, reported not chased); both-rows field/warp/buster/opening 0; negatives not blind. Trace: mettaur 70/70 clean, battle_full first divergence unchanged k=0 (4,10)/(4,0). GLM verifier CONFIRMED claims 1,2,3,5; claim 4 (opening-baseline byte identity) corroborated via opening 0/0/40 + history. Merged c31c8cb; post-merge HEAD verify PASS identical numbers. Worker muse-spark-contrib $0.0899; land.sh reused a same-sha .pass from an earlier partial row set and wrote 'skipped' -- caught, HEAD re-verified, message amended, stale .pass removed.
**Files.** src/ai.rs, src/objects.rs (the per-type entry for the Mettaur), src/actor.rs (only the calls the entry makes), tools/trace.py, docs/coverage/plan-interpreters.md

**Why.** T5 landed the object dispatcher (objects.rs: battle_common_path / enemy_think / enemy_act / the
per-type entries) and T4/T4b the animation player, so an enemy can now be canon's routine rather than
ours. The Mettaur's brain in src/ai.rs is a hand-written state machine tuned to canon's counts (F17, F25,
F28: sub_8109DEC / sub_8109CBC / sub_810A004 and the RunAIAttack chain in the plan's section 2). Port
that chain as the Mettaur's per-type entry: the AI state table, the wait/align/hop/swing/shockwave states
and their counters read from the same fields canon reads (the BattleObject's AI data), driven through
enemy_think / enemy_act, with the hand-written state machine removed behind the same interface.
**Acceptance.** mettaur 0/0/70 (negative not blind), wave 0, tiles/gauge integrated 0, popup 0, cursor and
windowclose unchanged (the pause pose comes from the same routine now); the trace on battle_full and on
mettaur: the enemy slot's CurState/CurAction/timers match canon frame for frame from spawn to the second
attack (first divergence unchanged or later); every other row 0; plan notes.

### T7. The battle end as canon's sequencer table: banner states, teardown, results hand-off  *(PARTIAL -- 2026-09-14, Sequencer states + TRC2 v3 export landed pixel-neutral [verify_rows: isolated all 0 incl mettaur, cursor 10/9 )*

**Result.** Sequencer states + TRC2 v3 export landed pixel-neutral (verify_rows: isolated all 0 incl mettaur, cursor 10/9 tear-smaller, both-rows 0; negatives not blind) but headline trace evidence NOT reproducible: retained rust records are v2, sequencer judge false-greens on missing field, --align sequencer= crashes (StopIteration). GLM verifier CONFIRMED scope (battle.rs/harness-notes/trace only, no allowlist change) + parity divergences (enemy k=0, mm k=179, rng k=271), REFUTED sequencer 239/239 + kill-slide gap as reproducible. Branch wt/t7 @7b984df kept unmerged. Follow-up T7b written.
**Files.** src/battle.rs (the end-sequence hunks), src/banner.rs, src/results.rs, tools/harness.py (the integrated rows' notes), tools/trace.py

**Why.** The five integrated variants (opening 72499, field ~158k, warp 40628, buster 54672, chip-use
275307) wait on one mechanism: canon's banner sequencer is a state table (sub_800801C, asm00_1.s:10422,
dispatch through off_8008038; the 0x0C handler sub_80081A4 :10617 does the HUD teardown; the ENEMY DELETED
banner element runs 49..106; the results driver sub_802BD60 starts the slide at 154 on every zero-enemy
row, F32b/F38 measured) while ours is a hand-written sequence with BANNER_TO_RESULTS and a single `over`
flag, which F33c/F38b showed cannot be made to fit per fixture. Port the sequencer as the state table with
its per-state counts and handlers, the trace's sequencer field (dword_203CA70) as the acceptance: the
state sequence and frames from the killing blow to the results window's first slide equal on both sides.
**Acceptance.** the sequencer trace equal on battle_full and on warp/buster/chip-use integrated; those three
integrated rows 0 or their per-frame remainder against F34's chain; result, popup, banner, field isolated
0; opening integrated re-measured; allowlist entries removed only for rows that read 0; nothing worse.

### T7b. Re-establish the sequencer evidence: fresh v3 traces, loud judge, kill-to-slide gap  *(DONE -- 2026-09-14, Landed 0fb54d4 [branch wt/t7b-sequencer-evidence @ dce93d4, carrying wt/t7's Sequencer states])*

**Result.** Landed 0fb54d4 (branch wt/t7b-sequencer-evidence @ dce93d4, carrying wt/t7's Sequencer states). Judge/align fixes in tools/trace.py only; src/battle.rs untouched by this ticket. Fresh TRC2 v3 records (sequencer field present in all four: r_bf 540f, r_met 70f, r_pop 80f, r_res 40f; canon c_bf/c_met/c_pop/c_res) retained gzipped in docs/trace/t7b/. Re-measured: mettaur sequencer match 70/70 (both sides 0x08 only); popup 80/80 (its mm_state_action k=0 divergence is F30's pre-window act=21, not the sequencer); result 40/40 DIVERGENT first k=0 canon 0x0C vs rust 0x08 (F36's structural arrival now on the sequencer field); battle_full 174/540 divergent named frame by frame (k=31..32 0x20, k=33..132 0x24, k=133..135 0x00, k=136..195 0x04 = canon's chip/custom-screen states our side never reads, k=296..304 0x08/0x0C = our end edge 9 frames early), and aligned on the end edge sequencer=0x0C reads match 239/239 to the end of the recording. Kill->slide measured both sides: canon blow 281 -> 0x0C 316 (+35 dissolve) -> first slide 423 = +107; ours blow 262 -> 0x0C 296 (+34) -> first slide capture 437 = +133 capture frames / +130 battle updates; same +2 post-edge 1596px write and the same 14-tick ramp, so the ~26-frame extra is setup duration (F38/F38b OPEN), not the Sequencer transition -- hence no battle.rs change; T7's asserted '+132' is +133/+130 as measured, and T7's stale harness.py comment still says 132. Verifier (glm-5.3-flash) independently CONFIRMED, from its own detached checkout and raw trc2.bin parses, all three load-bearing claims: (1) the false-green judge now dies naming the missing field on a real v2 record and --align sequencer= raises no StopIteration; (2) 239/239 aligned reproduces and the four records are genuinely v3 (the thing that made T7 unreproducible); (3) kill-to-slide endpoints and the 14-tick ramp reproduce, with the residual risk noted that setup-vs-transition is not decidable from the state word alone (both sides hold 0x0C the whole window) and wants an F38 measurement. Rules audit CLEAN: T7b touched only docs/ and tools/trace.py judge/align/stall code, no allowlist widened, no region shrunk, reference/bn6f untouched, worktree cleaned. POST-MERGE RE-CHECK (T8 752146e landed on main while this worker ran, so the pair was verified apart): verify_rows HEAD 0fb54d4 -- 59 rows PASS 0/0 with live negatives, verify_rows PASS. cursor's single-frame tear moved 44/43 (main before T8) -> 7/6 (T8) -> 10/9 (T7b alone) -> 26/17 on the merged pair, frames 170 and negative ~186287 unchanged, i.e. still the same one-frame layout-sensitive tear the verifier established is binary-layout noise (VM-on vs VM-off = 0 pixels), reported and not chased per this phase's rule. Unverified: the 9-frame end-edge offset was decomposed from two watched fields on separate captures, not one frame-locked pair; canon's 35 vs our 34 dissolve count may be a watched-field convention off-by-one. Child qwen3.8-flash 2 commits + verifier.
**Files.** tools/trace.py (judge + align fixes only), src/battle.rs (only if the re-measurement indicts the Sequencer transition), docs/coverage/plan-interpreters.md (notes)

**Why.** T7 (PARTIAL, branch wt/t7 @ 7b984df kept unmerged) landed the Sequencer states and the TRC2 v3
export pixel-neutral (verify_rows: every isolated row 0 including mettaur, cursor 10/9 tear-smaller,
both-rows 0) but its headline evidence is not reproducible: every retained rust record is TRC2 v2, the new
sequencer judge reports "match" when the rust side lacks the field (false-green), and `--align sequencer=`
crashes with StopIteration (verifier REFUTED the 239/239 + kill-slide gap as reproducible; CONFIRMED scope
and the parity divergences enemy k=0, mm k=179, rng k=271). Base your worktree on wt/t7 (merge it into
your branch; do not merge anything to main), re-record rust v3 traces (battle_full, mettaur, popup,
result) and retain them with the report, fix the judge to fail loudly on a missing/mismatched-side field
and fix the align crash, then re-measure: battle_full sequencer k-ranges, mettaur/popup 70/70 + 80/80,
result 40/40 structural divergence, kill-to-slide gap on both sides (worker asserted canon +107 vs ours
+132: treat as unmeasured until you measure it).
**Acceptance.** fresh v3 rust records retained and named in the report; sequencer trace equal on battle_full
(or k-ranges re-measured with the remainder named frame by frame); judge false-green fixed and align crash
fixed; kill-to-slide gap measured both sides; warp/buster/chip-use disposition unchanged (F34 ramps);
result, popup, banner, field isolated 0; nothing worse.

- T4b DONE -- Port the animation bytecode player, steps 3 and 4 of the plan. T4b steps 3-4 landed 6a2876e (was wt/t4b f86acb6): alt stream, setAnimation/Unk_00, updateSprite gate + variants
- T5 DONE -- Port the object dispatcher, per section 2 of the plan. T5 dispatcher landed 163293b (was wt/t5 e17d8d3): objects.rs battle_common_path/enemy_think/enemy_act/t1_player_entry/t3_entry

**Common to F8-F23 (and their b-tickets) unless the ticket says otherwise.** Baseline the row (harness line plus
`tools/diffmask.py` region, plus `tools/oracle.py` where the row is supported); localize the residue to
frames and an element; find canon's routine for that element in reference/bn6f and cite it; fix src/
(or the fixture/descriptor when the residue is the fixture, with `peeked` provenance); re-run the row,
wave, window, opening, chip-cannon and the full table -- nothing may get worse, and a row that does is
reported with its numbers. No allowlist change; no alignment or region change except by measured event
(F2's rule). **Coordinator:** verify_rows on every row the report names; the verifier only for claims
beyond harness lines; a PARTIAL from a wrong guess about the cause gets one follow-up ticket; if that
also fails, mark the ticket BLOCKED and move on to the next OPEN ticket.

### T13. Audio parity, first measurement: both sides dumped and compared sample-exact  *(DONE -- 2026-09-14, LANDED as 9d52135)*

**Result.** LANDED as 9d52135. tools/audio_probe.py + docs/audio/baseline-buster.md; NO harness row by design (canaries identical to HEAD before and after the merge: mettaur 0/0/70/41734, wave 0/0/90/3840). Baseline numbers: canon 642914 vs ours 640170 interleaved s16 over 200 frames, measured rate 95999.1/95589.4 Hz (both sides' own audioRateChanged 65536 is the not-to-trust number); first cross-side difference at global s16 index 2 (frame 0 offset 1 L, canon=1 ours=0); 639328 of 639402 COMPARED samples differ (99.9884%); max |dL| 21956 @f119/1438, |dR| 19378 @f93/1272 (both sides play different battle music); whole-tree peaks canon 19452 / ours 11221. Frame 0 is short AND silent on our side (234 pairs vs canon 1605, max|sample| 0) -- the audio gap opens as a capture/ramp artifact, not synthesis. Negative fixtures non-blind: shift-by-1 317813, all-zero 642841. Determinism CONFIRMED: 2 identical runs/side byte-identical (md5 047b73848cc35674342bfaae60bd39d8 canon, 84757d1fae2b6dfc80e4680c592d4b60 ours) -- sample-exact needs no precondition decision from the user. MEASURED ATTRIBUTION (needed a 9th capture run, one over the ticket's 8, disclosed; an import mistake also replayed runs 1-4 byte-identically, 13 total): a no-press canon control subtracts sample-exactly at ALL 130 pre-press frames + the 4 poke frames, cancelling the counterexample frames 12-27 (music RMS 4234.6/peak 8460 -> 0.0), and this MOVED the conclusion -- canon's blip onset is frame 135 = press+5 as a PARTIAL frame (486 of 3210 samples), ours 114 = press+6 full frame. QUALIFIER the src ticket must carry (verifier's, mandatory): onset-to-onset distance is ~635 interleaved pairs = 6.6 ms (canon starts 1119/1605 into its frame, ours 149/1605), NOT one frame; a whole-frame shift overshoots by ~10 ms and fails a sample-exact check it should pass. Second ours-only defect, code-level: assets/buster_hit.wav on FIFO A (id 4) at press+10 (frames 118-130, RMS 2175.9 peak 11221 = our whole-tree peak) in a scenario with NO enemy to hit -- src/battle.rs:3235 sets hit_in with no enemy-overlap/HP gate; play_sound occurs once in all of src; ch0 has peak>0 only in 114-117 so the ch4 event cannot be the sweep. Verifiers (qwen3.8-flash, 3 passes over the ticket): pass 1 at f882d8c spent 0 captures and re-measured everything from the surviving /tmp/aud_t13 trees -- CONFIRMED determinism/negatives/rules audit but REFUTED 'entire mismatch is ONE frame' (frame 0 = 2742 of 2744; 105 later frames differ, 769 gross pairs skipped) and the 'ours ch4 0.0 everywhere except frame 118' exclusivity (event spans 118-130), and blocked the canon attribution as not isolated; pass 2 confirmed the tool fix (cmd_compare now lists all 106 defect frames + the compared/skipped pair counts; percentages now against compared samples -- the parent's 99.87% was the same measurement over min(total), so the new denominator is more honest, not a shrunken window); pass 3 CONFIRMED the control-run subtraction and the press+5 onset and called it landable with the 6.6 ms qualifier. Unverified: 13-frame body vs the wav's documented ~10.7-frame body (mixer-rate path), canon's post-143 ~3000 divergence floor (pressed vs control state), determinism beyond one pair of runs per side, and that BUSTER_BLIP_ENVELOPE/_FREQ/_FRAMES are wrong -- this ticket measured, it did not touch src. Child glm-5.3-flash 25+ turns, 13 capture runs; 3 verifier passes.
**Files.** tools/audio_probe.py (new), docs/audio/ (new)

**Why.** M9 is in scope (the user, 2026-09-14 14:00) and docs/SCOPE.md names its first ticket: *"mgba can dump audio; a comparison tool is the first ticket."* The capture side is already done — `mgba_capture.c` has `--dump-audio <dir>` (post-mix stereo s16 interleaved, one `frame.####.pcm` per rendered frame, same numbering as the video) and `--audio-channel <id>` (solo PSG 0-3 / FIFO A-B 4-5, id table printed to stderr) — and nothing in `tools/` compares two PCM trees: `chip_compare.py` and `compare_stereo.py` are pixel-only. There is exactly one place in our ROM that makes a sound today, and it is the weak point M9 exists to close: `src/battle.rs:76-110` ports `SOUND_BUSTER_6A` (id 0x6A, `constants/enums/SoundOffsets.inc:50`, played at the fire phase by `sub_80BCF7A`, asm31.s:10516-10528) as a PSG sweep, and its envelope constant carries `// provenance: fitted -- explicitly "an approximation of the real envelope's shape rather than a reproduction of its mechanism"` (volume set as `15 * 1376/3768 ≈ 6`, note cut by the hardware length counter because M4A runs the envelope in software). That measurement was taken by *subtracting a silent control run* to cancel the battle music — the same subtracted-baseline shape the pixel standard forbids — and no comparison has ever been made between the two sides on one scenario. Two mechanisms also coexist on our side (a PSG sweep in battle.rs and `assets/buster_hit.wav` through the agb mixer in main.rs:103), which per-channel soloing can settle in one capture each.

**Do.**
1. Baseline both sides, no channel soloing: canon and ours, the existing buster scenario, same frame count, `--dump-audio` → *report per side: sample rate as mgba settles it (the stderr table), total samples, peak |sample| and RMS, so silence-vs-sound is a number, not an assumption.*
2. Write `tools/audio_probe.py`: align two PCM trees by frame filename, compare **every** sample, no resampling, no trimming, no baseline subtraction → *report total samples, first differing sample index (and its frame = index ÷ rate), differing-sample count, max |Δ| per channel, and a per-frame RMS pair — full length or a stated length mismatch, which is itself a defect.*
3. Negative fixture, or the tool proves nothing: compare canon against itself with one channel offset by a single sample, and against a same-length all-zero tree → *report both as non-zero totals; a BLIND tool is a failed ticket.*
4. Determinism, the precondition for "sample-exact" as a standard: two identical canon runs → *report `cmp` of the two PCM trees (identical or the first differing byte), and the same for two identical runs of ours.*
5. Attribute the difference: `--audio-channel 0..5` soloed, one run per side, on the frame `SOUND_BUSTER_6A` lands → *report the per-channel first-differing-sample and peak on the fire frame for both sides, so the residue is pinned to a PSG channel or the FIFO mixers rather than "the audio", and state the measured envelope of canon's blip (RMS per frame over its 7-tick gate) against our fitted envelope's.*

**Rules.** No edit to `tools/mgba_capture.c` (shared `/tmp/mgba_capture` rebuild-on-newer-mtime would swap the binary under T9c's captures), `src/*`, `tools/harness.py` (this adds **no row** — an audio result is not a harness verdict yet), `tools/states.py`, `tools/trace.py`, `FIXTURE.md`, `assets/`, `docs/coverage/`. ≤8 capture runs total, one at a time, inside the 3-slot semaphore. No fitted numbers: the tool reports distances, and any envelope shape it prints is labelled as a measurement of one side, not a target for the other. Do not "fix" the silence or the fit — that is a src ticket this one feeds. PCM trees go to `/tmp`, only the report and the tool land.

**Measure and report.** row: none — no harness row is added or changed; report the 59-row rollup unchanged. frames: the buster scenario's compared frame count, both sides. total: differing samples over total samples, and the first differing sample index + frame. worst: max |Δ| and the frame/channel it sits on. region: per-channel, by channel id. commit: `tools/audio_probe.py` + `docs/audio/baseline-buster.md`. Mechanism: both sides' post-mix stereo dumped per frame and compared whole, then soloed by channel to attribute the residue. Unverified: whether the residue is driver timing or envelope mechanism (this ticket names the channel, not the routine), and whether audio is frame-deterministic if step 4 fails.

**Coordinator:** dispatch third. It is the only M9 entry point that needs no src and no harness edit, and it is the ticket that turns an existing `provenance: fitted` constant into a measured one — the cross-cutting invariant "no fitted constants" is already violated in battle.rs's buster envelope and today's harness cannot see it. Costs 4-8 captures, so schedule it when T9c is between rows, never alongside T11 (both are capture-side and only two workers run at once). If step 4 shows non-determinism, stop and report: sample-exact parity would then need a decision from the user, not a tolerance from us.


### T9d. Why the poked Gunner battle never goes live: write-watch the sequencer on the working scenario and name the difference  *(OPEN -- 2026-09-14)*

**Files.** tools/states.py (only if a poke fixes it), docs/coverage/battlestart_gunner.md (corrected), docs/trace/t9d/ (new)

**Why.** T9c landed (`1f7efc9`) the `battlestart_gunner` recipe and per-slot `enemy_kind`, and the verifier CONFIRMED
both: record 6 (`0x080b4bd8`) holds for all 900 frames, slot0 Mettaur panel `0x0205`/NameID `0x0001`/HP `0x0028`,
slot1 NameID `0x0085`/HP `0x003C`, slot2 empty, MegaMan (2,2) HP 100, rng low half `0x0f46`. What it could not do is
produce the row: the banner sequencer `dword_203CA70` (ewram.s:3040) **reads 0 for all 900 frames with no logged
write at all**, the gauge is frozen at `0x00200000`, and the viruses park at state/action `0x0104`. The verifier
REFUTED the causal chain this branch's coverage doc asserts (state 0 gated by `sub_801483C`, state 4 gated by
`sub_801E754` ⇔ `dword_20352C0` bit `0x8000`): that bit is **already clear** in the poked battle, and the proposed
unstick (sequencer=4 plus `0x02036848:4`/`0x02036840:4`) makes 4 stick for 338 frames, never writes 8, and produces
no damage across 5 button presses. So "no attack event is reachable" is NOT established -- what is established is
that nobody has found who writes `dword_203CA70`. The cheap experiment nobody has run is the comparison against a
scenario that DOES go live: the `mettaur` row's canon side is a live battle off `battlestart`, 70 frames, its
negatives non-blind. Same base state, same pokes, one different roll outcome.
**Do.**
1. `--watch-write 0x0203ca70` (and the gauge `0x020352A0`, and `0x02036848`) on the WORKING `battlestart`
   scenario for ~200 frames → *report the writer PC(s) that first put non-zero into the sequencer, the values and
   the frame, and what state the scenario was in when it happened.*
2. The same watch on `battlestart_gunner` for the same frame count → *report the diff: which of those writes is
   absent, and at which PC the chain stops (a write that never fires, or a branch that never taken -- cite the
   instruction line for whichever it is).*
3. Name the one thing the poked battle is missing → *report whether it is a value the roll poke left wrong (then
   add the poke in `tools/states.py`, with the address/width from ewram.s or the ROM label, and re-run 1 capture to
   show the sequencer moving and an attack event happening), or a structural property of state 6's setup bytes
   (`byte_80B5347`: 00 22 00 00 | 11 25 01 00 | 11 36 85 00 | F0), in which case say which byte and cite the ROM
   routine that reads it.*
4. Correct `docs/coverage/battlestart_gunner.md` → *the verifier said its gate-chain narrative must be fixed before
   it is copied forward: replace the `sub_801483C`/`sub_801E754` causal claim with what was actually measured (bit
   already clear, poke sticks 4 for 338 frames, no 8, no damage), and state the finding of step 3 in its place.*

**Rules.** No `src/*`, no `tools/harness.py` (this ticket adds NO row -- the row is the next one if the lever is
found), no `tools/mgba_capture.c`, no `tools/trace.py`, no `FIXTURE.md`, no `assets/`, `reference/bn6f` read-only.
≤5 capture runs. Every address named with its `ewram.s` line or ROM label. A precise negative is the good outcome:
if the sequencer's writer cannot be localized within the budget, report which watch produced which empty log rather
than inventing a gate.
**Acceptance.** `docs/trace/t9d/` holds both watch logs; the coverage doc no longer asserts the refuted chain; and
either `tools/states.py` gains a poke that makes `dword_203CA70` advance (with a capture showing it, plus the frame
of the first attack event, which is what the row will align on), or the report names the exact PC/byte where the
poked battle's chain stops. Either way a follow-up row ticket becomes writable.
### T13b. The two audio defects T13 measured: the ungated hit sample, and the 6.6 ms onset offset  *(OPEN -- 2026-09-14)*

**Files.** src/battle.rs, docs/audio/baseline-buster.md (three wording fixes), docs/coverage/audio-buster.md (new)

**Why.** T13 landed (`9d52135`) the first sample-exact audio comparison and its verifier confirmed, from the trees
on disk and with zero capture runs, two defects that are mechanical facts about our side -- not synthesis guesses:
(a) `src/battle.rs:3235` sets `hit_in = BUSTER_HIT_DELAY` inside `Update::Strike { charged }`'s uncharged arm with
**no enemy-overlap and no HP gate**, so `assets/buster_hit.wav` plays through the agb mixer on FIFO A (channel id 4)
at press+10 (frames 118..130, RMS 2175.9, peak 11221 -- which is our *whole-tree* peak) in a scenario that has no
enemy to hit; canon's run of the same scenario shows no such onset (its frame 140 = 2181.5 sits *below* 136-139 =
2466/2519/2593/2782). It is the only `play_sound` call in all of `src`. (b) the buster blip's onset is **one frame
later than canon's at frame granularity, and the verifier's mandatory qualifier is that the measured onset-to-onset
distance is ~635 interleaved pairs = 6.6 ms, NOT one frame**: canon's first differing sample is pair 1119/1605 into
its frame 135 (press+5, a partial frame -- 486 of 3210 samples, all in L) while ours starts at pair 149/1605 of
frame 114 (press+6, a full frame), so a fix that shifts ours a whole frame earlier **overshoots by ~10 ms and fails
a sample-exact check it should pass**. The frame-level attribution is now measured, not inferred: the no-press canon
control subtracts sample-exactly at all 130 pre-press frames plus the four poke frames, cancelling the frames 12-27
music (RMS 4234.6 / peak 8460 -> difference 0.0).
**Do.**
1. Gate the hit sample the way the ROM gates it → *find canon's own condition for the `SOUND_BUSTER_*` hit sound in
   the disassembly (the fire phase's enemy-overlap/HP test, cited `symbol:file:line`), implement that predicate on
   the `hit_in` write, and re-measure: our channel-4 tree in a zero-enemy fixture must go silent, and with an enemy
   present the event must appear where the predicate says. Report both trees' peaks, not one.*
2. Close the onset offset as a **time** difference, not a frame difference → *report the onset pair index on both
   sides after the change (canon 1119/1605 of its onset frame is the target's phase); state the residual in pairs
   and in ms at the measured 95999.1 / 95589.4 Hz, and do not claim parity at frame granularity alone.*
3. Three wording fixes in `docs/audio/baseline-buster.md`, none of which changes a number: label the 9179 as a
   **peak of the subtraction** on a channel where the blip *replaced* the music (canon's own peak at 136 is 8366);
   note that "decay to 2123 by 142" is measured against the ~3000 unattributed divergence floor the doc already
   disclaims; and change "now reports every mismatched frame" to what the tool does (counts all 106, lists the
   first 10).
4. Leave the frame-0 ramp ALONE but say what it is → *our frame 0 is short (234 pairs vs canon's 1605) AND silent
   (max |sample| 0 over its 234 pairs), which is why the first cross-side difference is global s16 index 2; report
   whether that is our boot-time audio ramp or the capture harness's own priming, with a cite, and stop there.*

**Rules.** No edit to `tools/harness.py` (this adds **no row** -- audio is still not a harness verdict), `tools/mgba_capture.c`, `tools/states.py`, `tools/trace.py`, `FIXTURE.md`, `assets/`, `docs/coverage/` except the new `audio-buster.md`, `reference/bn6f` read-only. ≤8 capture runs, one at a time inside the 3-slot semaphore, and state the count honestly (T13 disclosed 13 runs against an 8 budget; a disclosed overage is fine, a quiet one is not). No fitted numbers: `BUSTER_BLIP_ENVELOPE`/`_FREQ`/`_FRAMES` may only change against a cited ROM value or a measured residue, and the `provenance:` tag must be updated in the same commit. `docs/inventory/enemies.{json,md}` are T12's generated output -- regenerate with its tool, never hand-edit.
**Acceptance.** the full table identical to today -- every named row except the `rollup` line, i.e. the same set `python3 tools/harness.py --list` prints, each isolated row reading 0 (`cursor`'s single-frame tear reported, not chased) -- a `src/` change must not move a pixel; our channel-4 tree silent in the zero-enemy fixture with the predicate cited; the onset residual stated in pairs and ms against the 6.6 ms measurement; `docs/coverage/audio-buster.md` recording what is now parity and what is still residue.
