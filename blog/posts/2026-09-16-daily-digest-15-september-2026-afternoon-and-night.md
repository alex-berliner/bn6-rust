# Daily digest, 15 September 2026, afternoon and night

This project rebuilds the battle engine of Mega Man Battle Network 6, a Game Boy Advance game, as new code in Rust. The rule is exact: a scene played by our version must match a recording of the original game pixel for pixel, frame by frame. Small AI agents do the work in tickets, each a bounded task; a ticket ends finished, half-done, blocked, or as a dead end that taught us something.

In the last 17 hours the agents closed 51 tickets: 23 finished, 5 half-done and kept, 23 blocked or dead ends. Every number below was measured by the automatic comparison against a recording of the original game.

(The plain-language account could not be written today; the tickets' own results follow, with each ticket's goal first.)

## Finished

**M2 battle_full first-divergence recon with fixed trace tools.** wt/t49-battlefull-recon landed as 34a4dd8. Recon: oracle.py battle_full --both names first divergence = enemy_state_action at k=0 (canon frame 11) canon=(4,10) rust=(4,0). Cite reference/bn6f/asm/asm31.s:170689 (sub_8109CE6, 0x0A hop executor) + asm31.s:170982 (ForMettaur_8109EF4). Mechanism: CurAction byte divergence - canon 0x0A, rust 0x00. 10,827,099 px diff / 35,308 worst at k=0 / 540 frames. (T49)

**M4 chips as data: Barrier family reads amount from the record.** wt/t48-barrier landed as 079531c. chip-barrier + chip-barr100 + chip-barr200 all PASS 0/0/80/41067. Dispatch on chip.family==0x15 && chip.subfamily==0x04 with HP/palette indexed by chip.params[0] (1/5/7 -> 10/100/200 HP and teal/gold/pink). Cite data/ChipDataArr.s:5521/5552/5583. 40 other chip rows identical (vulcans, swords, bombs, cannon, etc). SCOPE.md M4 line 10 -> 13 chips AS DATA. (T48)

**M2 battle_full trace tool fix (oracle/diffmask/trace).** wt/t47-trace-fix landed as 12f10c2. Tools-only fix: oracle.py --both + battle_full via SCENARIO_ROWS; diffmask.py --frames; trace.py ORCL_ADDR fix. First divergence = enemy_state_action at k=0 (canon frame 11) canon=(4,10) rust=(4,0); mm_state_action/mm_anim/mm_timer residual 76/78/270 reproduces T7r PARTIAL; rng_cadence first divergence at k=124. Oracle NOT BLIND (6/10 fields move on +1 shift). (T47)

**M4 chips as data: Bomb family reads AttackPower +0x1a.** wt/t46-bomb-family merged to main at 85f021c (resolving conflict: take branch's bomb_anim=(id, thrown) which verify_rows PASS proves correct). Before merge: chip-energbom/chip-megenbom FAILED 6895/146 on main 486dad8 (element-driven bomb_anim caused regression); after merge: all 6 Bomb chip rows PASS 0/0/{60,60,60,48,50,75}/{17158,22207,22207,17490,18173,72679}. (T46)

**Repair the stale file:line cites baked into `src/` comments: eight `derived --` provenance tags point at asm lines that are not the table they name, and the `SPRITE_LOADER` warning prose is out of date.** branch landed as 8eb9517. worker-minimax (M3:high, 30 turns, /bin/bash.21) did comment-only repair: 11 stale // provenance: derived cites rewritten (RECOV_HP asm31.s:111044->RecovHealBySubfamily_80EC870 at asm31.s:111132, BarrierHpByType data/dat01.s:189->194, VULCAN_SHOTS asm31.s:109878-109892->VulcanShotsBySubfamily_80EBFEC at asm31.s:110022), 5 SPRITE_LOADER prose sites updated to current nm evidence (BATTLE_MARKE... (T30)

**Measure the `k=0..2` group of `field`'s integrated residue instead of arguing it away -- 49% of the 32623 is currently excluded from the scroll model by reasoning alone.** MERGED 9985842 (tip b9a1224; diff vs merge-base is docs/worklog/T31.md + tools/harness.py only, 0 non-comment lines, FIELD_ZERO still 471/748, no src/, no row/frames/region/allowlist change, ROM unchanged by construction since harness.py is not compiled in). Acceptance met on both arms. (T31)

**The gunner row's gauge band: name canon's custom-gauge word and `oBattleState_Index_00`, then seed `GUNNER_ROW` from the measurement.** branch landed as 5a5fcd9. worker-minimax (M3:high, /bin/bash.42 cost) added GUNNER_ROW descriptor (gauge=0x4000, name+gate=isCustGaugeFullAndBattleLive_800A21C) at tools/harness.py:1759 with asm00_1.s:15305 cite; one-line & 0xFF mask on fixture_cheats gauge write at :156 so descriptor can carry asm-world 0x4000 (sub_801DFE4 at :15311-15313) and round-trip to same u8 byte as prior gauge=0. (T32)

**Reconcile the two contradictory scroll-seed derivations T25 left living in `tools/harness.py`, and settle whether `field-bg1`'s k=0 residue is the same band as `field-bg2`'s.** follow-up pass MERGED as da68f18 (this run's verifier-hyper returned GO on 546fc6e after re-deriving everything from the dumps with its own loops -- mirror 0x020000B2/B6 confirmed from src/battle.rs's trace_snapshot b[50]/b[54] + main.rs:275 TRACE_OFFSET=128 + nm's 02000000 D BATTLE_MARKER; all four seed solution sets reproduced; (T29)

**Name the source of the <=2 px period-4 scroll translation on `field-bg1` -- the dominant term left after T24 harvested the art-phase one.** landed 7129c23: FIELD_ZERO scroll_xq 466->471 + scroll_yq 745->748 takes field-bg1 354486/14743 -> 4800/4800 (-98.6%, residue = k=0 transition frame only) and field integrated 155048/5545 -> 32623/5806 (-79%, neg 173631 non-blind); witnesses bg2 4800 / bg3 380263 unchanged, field isolated 0/0/40/1139, ROM byte-identical (1997be3b) so zero cross-build ambiguity; (T25)

**Test the SEED verdict where it can actually be wrong: put our art-clock countdown at canon's 4 and see whether the backdrop lines move.** landed 98fd371 (+ wording applied on main f2c7632; diff was ONLY tools/harness.py's FIELD_ZERO art_timer 7->4 and its // canon: citation block, plus docs/worklog/T24.md -- no src/, no assets, no capture tool, no probe, no verify_rows, no allowlist, no coverage doc, no SCOPE/inventory, no row, no Align/frames/region/PORTED_CHECKS/negative edit, reference/bn6f read-only). (T24)

**Read the backdrop's REAL scroll registers on both sides, and name the captures the shift test runs on -- finish what F46 aimed at the wrong halfwords.** STAMP AMENDED 2026-09-15 by T23 (landed a0468e7) -- the substance of F47 STANDS (canon's backdrop art steps at k=5,13,21,29,37 and ours at k=8,16,24,32 on the same period-8 schedule, a 3-frame phase offset, edges CONFIRMED by independent hashing; scroll is not the carrier; the register map is scroll 0x04000010..0x0400001E and write-only readback is structurally unavailable through mgba's busRead8 path; (F47)

**Locate F47's 3-frame art-clock offset: read canon's OWN anim-state record at one paired frame and say SEED or FREE-RUN.** landed a0468e7 (docs/coverage/field_integrated.md pure append + docs/worklog/T23.md; ONE capture run, 2 of 3 budget, rest reused from F47's kept dumps). (T23)

**Settle F47's open (c): rebuild the backdrop art-content test on the ROM's OWN per-step upload list, not the s\*37+k grid.** landed 55549f2 (docs/SCOPE.md, docs/coverage/field_integrated.md, docs/worklog/T22.md, tools/inventory.py only; zero captures used of a 3 budget, everything derived from F47's kept dumps). (T22)

**Gate the enemy HP readout on canon's battle-state latch, not our intro ramp -- finish F43 without cursor's regression.** integrated constant re-gated under F48's fixed matcher (4df0c52) and it REPRODUCES: verify_rows HEAD opening --expect opening=18740/647/40/98649 -> 'MATCH (integrated line)', and the same call with a deliberately wrong expect (1/2/3/4) returns MISMATCH total,worst,frames,negative, so the gate is live and not rubber-stamping. (F44)

**Measure the run-to-run drift on the non-zero integrated rows, and give `verify_rows` a policy for it -- F46's verifier found the drift, this ticket sizes it.** landed 4df0c52. The 'run-to-run drift' that F46's audit blamed on vblank sampling does not exist: same-ROM captures are pixel-deterministic on the five rows measured (verifier-hyper byte-compared two real kept re-captures -- rust 193 + canon 180 files, 0 differing, aggregate md5s equal -- and proved they are not dir-reuse: cc.capture() rm -rf's per attempt at tools/chip_compare.py:233, run_check deletes both dirs at... (F48)

**Make the chip-asset contract loud, and let SCOPE say that eleven chips are now data.** landed 2baad23. Chips::new now enforces the exporter's version u32 (src/chips.rs:66-70, from_le_bytes matching chip_export.py:238's '<4sII') BEFORE locating the tail, so a v1 asset panics by name instead of silently reading blob bytes as behaviour; both silent match defaults replaced by named panics with all 11 ROM arc rows and shape 1 spelled out; (T19)

**Chips as data, first family: the sword/blade arm driven from ChipDataArr's own attack bytes.** the sword/blade arm is data-driven, landed 8c1a62d. chip_strike's CHIP_* id count 35 -> 24 with all ELEVEN sword/blade ids gone (Sword, WideSwrd, LongSwrd, WideBlde, LongBlde, FireSwrd, AquaSwrd, ElecSwrd, Bambswrd, Muramasa, StepSwrd -- the eleven the parity table covers; re-derived with the printed command on git show 2478ff1:src/battle.rs, so the verifier's 33 was its own awk end-boundary); (T17)

**M3's first rung: every status bit's setter, reader and battle-visibility, out of the disassembly.** statuses now DERIVED-FROM-CODE under a STRICT per-bit rule, landed 3f09aa7. Generator-scanned (verifier-hyper re-ran the shipped scanner in memory and reproduced every count): written 39/69 per-bit (flags1 26/32, flags2 13/32, DAMAGE 0/5) vs 40 loose -- the single loose-only credit is OBJECT_FLAGS_FLINCHING from combined =0x400400 at asm00_2.s:18308 in playerFlinchAction_80174FE; (T18)

**Retire the dead `FLAG_*` names in tools/harness.py's row notes and document SceneFlags' raw-byte escape hatch.** LANDED as 0c0d6f1. All 13 dead FLAG_* names in tools/harness.py's row notes rewritten to SceneFlags::<NAME> (grep -c 'FLAG_[A-Z_]' now 0 on main; every one had an exact newtype counterpart, so no NEGATIVE was needed), and both SceneFlags From impls in src/fixture.rs now say in prose what the raw-byte door is for (the harness's poke/cheat descriptor path) and what it is not for (call-site bit tests). (Q5)

**One safe wrapper for the boot mark and the state block.** LANDED as 184b9b5, re-stamped with the verifier's own retraction so the record is not read as cleaner than it was. What changed: one private BattleMarker type owns every raw access to BATTLE_MARKER in src/main.rs -- unsafe blocks 4 -> 1 (grep -c unsafe 6 -> 3 lines, two being edition-2024 #[unsafe(no_mangle)] / #[unsafe(link_section=".ewram.marker")] attributes, not blocks); (Q3)

**The forty-byte state block as named fields, not byte offsets.** LANDED as 17012e8 (60/61 rows identical across the merge, verify_rows PASS). The 40-byte oracle block is now built from one Rust ORACLE_LAYOUT: [(&str,usize,usize); (Q4)

**The scene's switches as a flags type, not a bare byte.** LANDED as 61fc751 with its acceptance line amended at merge on the verifier's judgment. fixture.rs's eight FLAG_* u8 consts -> `pub struct SceneFlags(u8)` with associated consts and const fn accessors; 14 `.flag(` sites map 1:1 onto 14 accessor sites in battle.rs/main.rs; all 61 compared rows identical HEAD<->branch (verify_rows PASS; cursor 1/1/170/186279 both sides, gunner 2105613/38237/130/2284867 both sides). (Q2)

**Name the last bare numbers in the HUD walk and the backdrop wrap.** LANDED as 57c62b3 (all 61 compared rows identical across the merge; verify_rows PASS). src/hud.rs's HP walk `abs_diff / 8 + 4` -> HP_WALK_DIVISOR / HP_WALK_MIN_STEP kept `provenance: peeked`: canon has no such walk -- GetMaxAndCurHPForCurPETNavi_80010D4 (asm/asm00_0.s:1963-1980) is a pure accessor, asm00_1.s:12860/16301/16994 read oBattleObject_HP without stepping a display, and the chain near asm00_2.s:29913 is the... (Q1)

## Half-done, kept

**M4's third chip-data arm: Cannon, HiCannon and M-Cannon read AttackPower +0x1a and Element, removing their `match chip.id` arms.** branch landed as be6e706. worker-minimax (M3:high, 60 turns, /bin/bash.21) ran chip_export.py v2 + cross-checked against reference/bn6f/data/ChipDataArr.s:33-126 byte-by-byte -- Cannon 0x0028=40 (matches chip.power), HiCannon 0x0064=100, M-Cannon 0x00B4=180; all three Element 0x0A=CHIP_ELEM_NONE (matches default). ZERO unexplained mismatches. (T36)

**Attribute `field`'s 158935-px integrated residue with a saturation-gated per-layer capture, split at the `shown` boundary -- finish what F42 tried to claim.** field's integrated constant RE-GATED under F48's fixed matcher: F45's landed '158935/5606/40 neg 261034' is superseded, not reproduced -- today's tree reads field integrated 158930/5601/40 neg 261029 and that value is now MACHINE-GATED (verify_rows HEAD --expect field=158930/5601/40/261029 -> MATCH (integrated line); wrong expect -> MISMATCH). (F45)

**The HP-readout emission gate: opening integrated's four spurious digit OBJs, from canon's HUD updater call site.** PARTIAL, branch wt/f43-hp-readout-gate @ 1542df0+5bf7ff6 kept UNMERGED (a row regressed). The gain is real and coordinator-measured in the branch's own worktree: opening integrated 25829/931/40 (neg 105749) -> 18740/647/40 (neg 98649, still non-blind), opening isolated stays 0/0/40 (neg 86591), gunner 2105613 -> 2094676/38237/130 (same mechanism, canon-aligned, its own intro digits), mettaur 0/0/70, result 0/0/40, wi... (F43)

**M1's last two tables: the status sources and the NaviCust program-id table, from the ROM.** LANDED as 152ce3c -- all three lines measured and written into tools/inventory.py with cites checked twice (verifier-hyper, then the coordinator re-grepping each corrected cite on disk), but the M1 counts do NOT move: docs/SCOPE.md still reads 0/69, 0/19, 0/3, so the ladder's rung stays unmet and only the evidence behind each line changed. (T15)

**Panels as a ROM table: canon's type-indexed flag word at 0x3007924 and PanelOffsetListsPointerTable, so M1's panels line stops being 13 routine names.** LANDED as 55c6b51 (docs/tools only, no src/, byte-identical build, verify_rows skipped as a no-op; the diff was checked empty against src/, tools/harness.py, tools/states.py, tools/allowlist.py and the reference/bn6f gitlink is identical on both sides). (T14)

## Blocked or dead ends

**M5 Gunner row aligned on first attack event.** wt/t45-gunner-attack-event @ 79b6e6d; worklog-only on docs/worklog/T45.md; no src/gunner.rs edit (T9k NEGATIVE veto on Battle::gunner_ctl/impacts). Baseline reproduce: gunner HEAD 2105613/38237/130/2284867 MISMATCH (fitted 19 unchanged); verify_rows mettaur/windowclose/result PASS 0/0/70/41734, 0/0/40/207166, 0/0/40/111839 (veto identical to HEAD). (T45)

**battle_full sequencer first-divergence on T7r scripted fixture.** wt/t44-battlefull-divergence @ 6b676b4; worklog-only on docs/worklog/T44.md; verify_rows HEAD wave,window,opening,chip-cannon,mettaur PASS 0/0/{90,16,40,40,70}/{3840,81056,86591,9505,41734} MATCH (isolated line). oracle.py rejects battle_full (unknown row: harness.py --list whitelist); oracle.py --both unknown flag. diffmask.py has no --frames flag (tools/diffmask.py:54-62); no battle_full capture set. (T44)

**M8's HP-display emission gate on the damage-taken path: port canon's HP-digit OBJ emitter call site at the damage-event handler, distinct from F44 DONE's intro-path gate T38 NEGATIVE couldn't reach without cursor regression.** T43 NEGATIVE on branch wt/t43-hp-digit-gate (worklog-only commit 87061b4 from main 73b46cc) (T43)

**M5's Gunner port: watch-write BG3 hardware registers (BG3CNT / BG3HOFS / BG3VOFS / DISPCNT) at k=77..129 to find the chip-window BG3 enable flip T39 NEGATIVE named but couldn't reach.** T42 NEGATIVE on branch wt/t42-gunner-bg3 (worklog-only commit eb3af7e from main 6714bc9) (T42)

**M3's first panel-effect port via the per-panel-type flag word at word_3007924: OR the panel-type's flag bit before the panel-step damage path, bypassing T40 NEGATIVE's cursor-fragile sub_801A7F4 direct port.** T41 NEGATIVE on branch wt/t41-panel-port (worklog-only commit 386dc8a from main 04397be) (T41)

**M5's Gunner port: watch-write the BG3 plateau region at k=77..129 for the chip-window auto-open trigger that T37 NEGATIVE couldn't reach.** branch landed as 4c2ce9f (T39)

**M4's Cannon family: port the three chips' `match chip.id` arm to AttackPower +0x1a, finishing T36 PARTIAL's deferred rewrite.** branch unmerged, worktree preserved. worker-minimax (M3:high, /bin/bash.49 -- over the /bin/bash.40 cap by /bin/bash.09) completed the Cannon family port: CANNON_FAMILY=0x14 const added, both use_chip and chip_strike arms converted from match chip.id to early-return if chip.family==0x14, barrel palette (chip.id - CHIP_CANNON) replaced with chip.subfamily, 3 CHIP_CANNON/HICANNON/MCANNON constants deleted, AS_DATA_FAMI... (T38)

**M3's first panel-effect port: holy panel halves the damage sum at sub_801A7F4 asm00_2.s:22788-22791, with a new panel-state fixture that loads type-5 panels.** branch unmerged, worktree removed. worker-minimax (M3:high, 112 turns, /bin/bash.35) created src/panel.rs with PanelType enum (8 variants Hole=0..Ice=7) + halve_if_holy(damage, panel_type) helper; wired into two damage-sum call sites in src/battle.rs:3199/3204; mod panel; in src/main.rs. Build green; ROM ELF sha256 unchanged. (T40)

**M5's first virus-port completion: settle Gunner's live attack event frame and bring gunner integrated below 1,500,000.** branch landed as c1c98ce. worker-minimax (M3:high, /bin/bash.57) ran sensitivity sweep canon_ref in {78,80,33,151} with locked search=range(0,40) -- baseline 2105613 (canon_ref=80) is local minimum. Watch probe of battlestart_gunner.state shows CurAction at 0x0203ab69 never reaches 0x0A in 300 frames; AIAttackVars_Unk_00 at 0x02034320 stays 0x00 throughout. (T37)

**M3's first panel-effect port: cracked panel breaks on MegaMan's step, from object_crackPanel at object.s:2218-2222.** branch unmerged, worktree removed. worker-minimax attempts: 1st cold-start (/bin/bash.05), 2nd cold-start (/bin/bash.05), 3rd ran and reached cargo build + gbafix but gbafix.py:33 failed calling arm-none-eabi-objcopy -- the GNU ARM toolchain is not installed on this box. T35 cannot produce a ROM that verify_rows can check until arm-none-eabi-objcopy is installed. (T35)

**Chips as data, third pass: the Recov, Barrier and Vulcan amounts come from their own subfamily tables, not from a `match chip.id`.** branch landed as 36c7bf6. worker-minimax (M3:high, 21 turns, /bin/bash.23) ran chip_export.py v2 BEFORE editing -- Recov subfamily 0..7 maps to 10..300 HP correctly (matches RecovHealBySubfamily_80EC870 at asm31.s:111132); Vulcan subfamily 0..3 maps to 3/4/5/10 shots correctly (matches byte 0xA050403 at asm31.s:110022); (T34)

**M3's first rung from the ROM: locate the writer of every panel type by walking `_object_setPanelType`'s call sites, and close M1's 8/13.** branch landed as ea5d284. worker-minimax (M3:high, 22 turns, /bin/bash.13) walked _object_setPanelType (4 call sites all load r2=#2) and inline strb oPanelData_Type (13 sites all type 1 broken or type 3 cracked) -- no writers found for types 0x0/0x5/0x8/0x9/0xA in reference/bn6f/asm. (T33)

**Chips as data, second arm: no chip id indexes an amount — Recov, Barrier and Vulcan read the record's own bytes.** landed b4a941a (a4a22fb, worklog-only; docs/worklog/T28.md is the record, ROM 1997be3b unchanged by construction, no src/ or assets/ byte moved so every number in the report is main's own). (T28)

**The custom-screen open edge as canon's press→0x14 ladder: replace GAUGE_PAUSE and the two uncited `seq.age` edges.** NOT MERGED (kept as the base for any dwell ticket): branch wt/t27-open-edge-ladder at 711d876 + 11ec3b7, worktree removed. (T27)

**Canon's battle-state 0x14 ladder: what each custom-screen edge waits on, and the pad path that arms it.** landed 9963a00 (docs-only, 949f0f0 + cite corrections 35708fe): the per-state-count model of canon's custom-screen ladder is DEAD -- SEQ_20/24/00/04 wait on busy-flag polls (sub_802D6C4 :11076-11081, sub_801483C+[r5,#2] latch :11095/:11031-11041, isBannerBusy_801E754 :10565-10567) with every timer in the SHARED driver slot [r5,#8]=0x0203CA78, so the observed spans 2/100/3/60 are banner-record lifetimes, never ages; (T26)

**The horizontal-blank tile writer: replace backdrop tiles at the original's scanline.** HELD FOR YOUR DECISION, not dispatched. T21's job is to eliminate the cursor row's single-frame seam by writing backdrop tiles from the HBlank handler at the scanline canon's graphics-transfer drain lands on -- i.e. (T21)

**Scripted-input scenarios: one button log drives both sides.** NOT DISPATCHED -- needs a hand-played input, which is the coordinator's hard stop and yours to supply. The blocker is step 2 as written: 'Record one scenario by hand in canon: open the window, move the cursor across two codes, pick two chips, confirm; (T20)

**Settle what field's backdrop residue IS: a register-level art-versus-timing split of the 139125-px bulk on the pairing F45 just landed.** OUTCOME STANDS, REASON CORRECTED BY A LATER AUDIT (2026-09-15, F47's verifier; see docs/worklog/F46.md's CORRECTED section for the full evidence). NOT LANDED; branch wt/f46-backdrop-registers @ 5e2499a kept unmerged, worktree removed. (F46)

**field integrated: 1589 px to 0 and the second AUDIT-6 allowlist entry retired.** CLOSES as NEGATIVE; branch wt/f42-field-integrated @ 0a4d840 kept UNMERGED (its only content is docs/worklog/F42.md, which this stamp carries to main; merging the branch would revert T15's landed tools/inventory.py + docs/SCOPE.md, since it branched before 152ce3c). (F42)

**chip-use integrated: the last 2 px, then delete the chip-use allowlist entry.** CLOSES as NEGATIVE, and the branch DOES land for its one honest change (allowlist re-title only). The ticket's premise was a misread, CONFIRMED: chip-use integrated measures 275307/18091/30 (negative 283978 non-blind), never 'total 2' -- so there were no 2 px to name and the entry cannot be deleted at a measured 0; isolated stays 0/0/30 with negative 7768 (verify_rows PASS on wt/f41-chip-use-2px @ 233adfe). (F41)

**cursor's single-frame tear tracks how the boot marker's frame word is written -- decide which, and stop calling it noise.** CLOSES as NEGATIVE, no code change (branch wt/q6-cursor-tear @ ddb031d kept UNMERGED, worktree removed). Step 1's five-run spread on one unchanged commit (35e6efa) is ZERO: cursor 1/1/170, negative 186279, region checksum 5a772d64782bcae2 -- one pixel at (183,5), k=97, canon frame 112 -- five runs, plus five more plain runs before instrumentation, and the coordinator's own verify_rows on main HEAD after Q5's landing... (Q6)

**The window's own duration: what ends canon's SEQ_24 after 100 exports, then the 0x20/0x00 edges and battle_full's kill→0x0C hand-off.** NOT DISPATCHED -- this is the third ticket in a row on battle_full's sequencer timeline and the two before it both came back NEGATIVE on the same underlying reason, so the run's streak rule applies (T7x: SEQ_04's leave ported bit-exactly, and the banner record's bare existence then broke windowclose 0/0/40 -> 40038/1900/40 and cursor 3/3/170 -> 16241/3385 through an unpinned mechanism; (T7z)

**The custom screen's open edge: canon's gauge→open chain replaces our peeked 60-frame countdown (gunner's two rows, battle_full's 83-frame window offset).** No code landed; branch wt/t7y-open-edge @ 6ea64ce kept UNMERGED, worktree removed. The ticket's lever does not exist in the watched bytes. Step 1 baseline corrects the ticket: HEAD's gunner is 2105613/38237/130 (the quoted 2850534/38237/130 was pre-T9l) and sequencer divergence is 273/540 with first divergence k=31 (canon 0x20 vs our 0x08). (T7y)

## New recordings

![T48 DONE: Barrier family reads AttackParam1 from data/ChipDataArr.s:5521/5552/5583. Dispatch on family=0x15, subfamily=0x04. chip-barrier/barr100/barr200 all PASS 0/0/80/41067.](../captures/chip-barrier-progress.gif)

![T46 DONE: Bomb family reads attack_power() + element from data/ChipDataArr.s:1646/1336/1367/1398/1708/6265. Before: chip-energbom/chip-megenbom FAILED 6895/146. After: all 6 PASS 0/0/N.](../captures/chip-minibomb-progress.gif)

## Where the whole thing stands

The game is compared against the original in 67 recorded scenes. 60 of them now match pixel for pixel in every frame.
The scenes that still differ: opening (inside a full fight); field (inside a full fight); warp (inside a full fight); chip-use (inside a full fight); gunner (on its own); gunner (inside a full fight); cursor (on its own). Each is a known, measured gap with a ticket behind it.

## What it cost

The agents run on prepaid subscriptions. Charm Hyper:  0.7 of 250 credits (249.3 used today, 100%).
tickets 21, landed 16, pi spend $7.26, $/landed 0.454, NEGATIVE+BLOCKED 8 (38%).
