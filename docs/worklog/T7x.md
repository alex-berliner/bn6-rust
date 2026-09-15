# T7x — battle_full SEQ_04's leave predicate: port isBannerBusy_801E754

## Baseline (step 1)

`tools/trace.py record canon|rust battle_full` on HEAD 75b357b (2 capture runs), then
`tools/trace.py diff /tmp/t7x/canon /tmp/t7x/rust --align row:battle_full`:

- **sequencer DIVERGES 273/540**, not the ticket's predicted 173/540. The ticket's number
  predates T7r's rewrite of the battle_full fixture (gauge=1 + scripted A@170 in
  tools/states.py:595+, which moved our window ~83 frames later than canon's).
- Divergent k-spans (canon frame 11+k <-> rust export k): k=31..32 (canon 0x20, ours 0x08),
  k=33..124 (canon 0x24, ours 0x08), k=133..135 (canon 0x00, ours 0x24), k=136..171
  (canon 0x04, ours 0x24), k=172..173 (canon 0x04, ours 0x00), k=196..233 (canon 0x08,
  ours 0x04), k=305..404 (canon 0x0C, ours 0x08).
- Full spans, canon rows -> k=row-11: 0x1C 0..10, 0x08 11..41, 0x20 42..43, 0x24 44..143,
  0x00 144..146, 0x04 147..206, 0x08 207..315, 0x0C 316..554. Ours: 0x08 0..124, 0x24
  125..171, 0x00 172..173, 0x04 174..233, 0x08 234..404, 0x0C 405..542.
- So the bulk of the divergence is the **window-open offset** (canon opens at k=31, ours at
  k=125 — the scenario's gauge/intro timeline, not SEQ_04) plus window-open duration (canon
  holds 0x24 for 100 frames, ours 47). SEQ_04's own length already matches: 60 exports both.

## Step 2 — the asm reading

- `isBannerBusy_801E754` (reference/bn6f/asm/asm00_2.s:31072-31098 in the re-cut reference
  at nested-repo HEAD 566c504b, the same commit main 3486090 carries): returns
  `(HudElementMask & 0x8000) != 0` — `ldr r1,[r2,#oStruct2035280_HudElementMask]; mov r0,#1;
  lsl r0,r0,#0xf; and r0,r1` — with a type-4/2 refinement that can return 2, never 0 while
  the bit is set.
- **Setter**: `spawnBannerRecord_801E792` (asm00_2.s:31115-31220) — after spawning the record
  it calls `setBattleHudElements_801BECC(1 << 15)` (the `mov r0,#1; lsl r0,r0,#0xf;
  bl setBattleHudElements_801BECC` tail, :31166-31170 region). Called from SEQ_04's handler
  `bannerSeqState04BannerWait_8008064` (asm00_1.s:10469-10570): the first run (byte [r5,#3]==0)
  arms the 0x1e (30) timer at [r5,#8], sets [r5,#3]=4, and calls spawnBannerRecord
  **immediately** — the 0x1e halfword has **no reader anywhere in asm/** (grepped), it is
  write-only; the 0x293 arm (`mov r0,#0xa5; lsl r0,r0,#2; sub r0,#1` -> strh [r5,#0xa]) is the
  win-count variant's timer on the sub_800A97A outcome path. Every run then writes 0x08 only
  once isBannerBusy reads 0 (bl at asm00_1.s:10500-10502, `mov r0,#8; str r0,[r5]` tail).
- **Clearer**: the banner record's own completion — `sub_801CEFA` (asm00_2.s:27770-27779), the
  state-3 handler of the record's state table `off_801CE5C` (dispatched by `sub_801CE28` on
  byte_2036840[0], states 0..3 with per-state counter byte_2036847 counting to 5; 0x2d=45
  armed for record types 4/2 by `sub_801E780`) — calls
  `clearBattleHudElements_801BED6(1 << 15)` (asm00_2.s:25578-25585). **This clear site is a
  ported routine**: our record is `src/banner.rs`'s Banner, whose lifetime is
  `banner::SCALE.len()` = 58 (peeked from OAM, F32b) and whose completion is `update()`
  returning false (src/battle.rs's `if !banner.update() { self.banner = None; }`).
- **Canon's measured mask series** (battle_full trace, hud.bin watch on 0x020352C0 + 0x020352C4,
  both words agree on bit 15): bit15 **set rows 148..205 = k=137..194** (mask 0xC497, hud_live
  base 0x4497), clear from k=195; then the ENEMY DELETED record sets it again **k=306..363**
  (mask 0x8084, teardown base 0x0084). Both records: 58 exports, first set one export after
  the spawning state becomes visible, state's leave one export after the clear.
- Canon's own trace refutes the "banner 289 = window close + 30" reading that
  BATTLE_START_AFTER_WINDOW=30 was peeked from: the record spawns at SEQ_04's first run
  (close+4), bit15 k=137..194, and **no banner strip is visible anywhere in the capture**
  (scanned rows 148..284 for a bright strip at the message's own position x=64..224,
  y=52..68: backdrop brightness only, ~23-30/93 per row vs the 60+ a 240-wide strip gives).
  No harness row shows this banner (every harness row's rust side carries a fixture, and the
  spawn was fixture-guarded; fixture rows never close the window — T7d), so the 30 was never
  pixel-checked by the suite.

Cite note: the ticket cites isBannerBusy_801E754 at asm00_2.s:31071-31097; the re-cut
reference (357da2a rename pass) carries it at 31072-31098 with the same body. The mid-run
steering's "30907-30931, mask[6] >> 12" does not exist in the reference on main (checked
main 3486090 / nested 566c504b: 30907-30931 is sub_801E658/sub_801E660); the file on disk
outranks the steering, so the cite used is 31072-31098.

## The port

- `BANNER_BUSY: u16 = 0x8000` (derived, cite above); mask export becomes
  `(hud_live ? 0x4497 : 0x0084) | (banner record alive ? BANNER_BUSY : 0)`.
- SEQ_04's arm: first run spawns the record (`Banner::new(.., banner::BATTLE_START)`,
  canon's byte-[r5,#3] first-run branch, latched once per battle via `banner_record_ran`);
  leaves to SEQ_08 when `self.banner.is_none()` — the bit test, no frame count.
- Deleted: `SEQ04_FRAMES` (derived 60), `BANNER_FRAMES` (peeked 58) and its assert,
  `BATTLE_START_AFTER_WINDOW` (peeked 30), the `banner_at` countdown field and its arm.
- `opening` (the fight-hold) now excludes the window-close record with `!self.window_closed`:
  canon's 0x04 handler only refreshes AIData (asm00_1.s:10471-10474) and never pauses, and
  battle_full's trace has canon's executor running through its 0x04 (mm fields match ours
  there today, first mm divergence k=269). The pre-existing comment already said the closing
  banner does not hold the fight.

## Results (after)

At the port commit 6143419 (all battle.rs edits; the record spawns VISIBLE at SEQ_04's
first run):

- `tools/trace.py record rust` again + diff: **sequencer 272/540** (was 273). Our SEQ_04
  k=174..232 (59 exports; canon 136..195, 60 — the 1-export shape difference is the
  completion-frame ordering: canon's sequencer step runs before the record update, ours
  after). Our **bit-15 mask series now canon-shaped**: 0x4497 k=0..174, **0xC497
  k=175..232 (58 exports, exactly canon's record length)**, 0x4497 k=233..404, **0x8084
  k=405..461** (the fixture-forced ENEMY DELETED record now carries the bit; canon's own
  ENEMY DELETED: 0x8084 k=306..363, 58 exports), 0x0084 k=462..542.
- cursor isolated 3/3/170 — **unchanged from HEAD** (gate PASS; the known tear, phase rule).
- verify_rows full table (62 rows, in /tmp/bnwt/verify-6143419): 59 PASS 0/0; mettaur
  0/0/70 MATCH; cursor 3/3/170 MATCH; **windowclose FAILED 40038/1900/40 (claimed 0/0/40,
  MISMATCH)** — our side now draws the strip during canon frames 81..120 and canon does
  not; gunner FAILED 2105613/38237/130 — this number is identical in every build I
  measured including before the banner.rs edits, but I never measured gunner on HEAD
  (budget): attribution to the port is UNVERIFIED, treat as suspect.

## The two strip-less repair attempts and why they failed

The windowclose evidence says canon's window-close record runs busy WITHOUT drawing
(battle_full's capture scan: no strip rows 148..284; windowclose's HEAD 0/0 with our side
spawning nothing). Two attempts to keep the record but drop the strip:

1. `Banner::hidden()` — record alive, `show()` skips. windowclose **63962/3557** (WORSE
   than visible) and cursor 16241/3385 (cursor's own walk DOES close the window and reach
   SEQ_04 — T7d's "fixtures hold it open" is wrong for cursor).
2. objectless record (`Vec::new()`, no VRAM upload at all): windowclose **63962/3557 —
   byte-identical to attempt 1** — and cursor 16241/3385. The allocation was never the
   mechanism.
3. NEGATIVE-PROBE: the SEQ_04 spawn disabled, every other port edit intact (constants
   deleted, opening gate, mask export, banner.rs restructure): **windowclose 0/0/40
   RESTORED, cursor 1/1/170** (the tear moved 3->1 with ROM layout — the phase-rule
   phenomenon, cf. the coordinator's ruling that HEAD's 3/3/170 itself moved off 1/1/170
   with the 357da2a ROM re-cut).

So the record's bare EXISTENCE during window-closing rows' compared frames breaks pixels,
through a mechanism not pinned within this ticket's budget. Enumerated and excluded:
`show()` (skips when hidden/empty), the `opening` fight-hold (excluded via
`!window_closed`), the clock gate at :2830 (`paused` is false with the record up: clock
runs), the mask export (export-only, nothing reads it back), VRAM allocation (attempt 2).
What remains, unverified: some reader of banner/record state not in that list, or an
RNG/clock side path the record's lifetime shifts. The intro block (src/battle.rs:2768)
reveals one more thing: our INTRO BATTLE START spawns there ("sub_8008064 raises message
0 ... THE FIGHT IS PAUSED FOR THE WHOLE OF IT") — a THIRD spawn site the port did not
migrate; canon's byte-[r5,#3] latch may tie all three to one record.

## Verdict: NEGATIVE

The bit-test reading is right and the port reproduces canon's mask series exactly, but the
record's existence breaks windowclose + cursor through an unpinned mechanism, so the
constants cannot come out yet. The branch stays at 6143419 (the coherent port, cursor gate
PASS, windowclose refuted by the strip) with this log; the probe state above is the next
worker's starting point: diff a gallery of my broken windowclose build against HEAD's to
find what actually moves (the worst frame's region will name the mechanism), and check
whether gunner's 2105613/38237/130 predates the port (one HEAD run) — if it does not, the
record's existence touches something on non-window rows too, and the mask-export field is
the first suspect to re-verify ("nothing reads it back" was proven for the OLD export;
the bit-15 addition touches a judged-adjacent word).

Numbers for the next worker:
- fitted constants: 19 before, 19 after (neither deleted constant was fitted-tagged; the
  ticket's <=17 target is not reachable by the named edits — SEQ04_FRAMES was derived,
  BANNER_FRAMES and BATTLE_START_AFTER_WINDOW were peeked).
- capture runs used: 8 total — 2 (baseline trace) + 1 (cursor gate) + 2 (re-record) +
  1 (verify_rows' windowclose... verify_rows runs all rows; counted as 1 mandated sweep)
  + 2 (windowclose+cursor re-gates). Discretionary: 0.
- The steering's cite (asm00_2.s:30907-30931, "mask[6] >> 12") does not exist in the
  reference on main (checked main 3486090 / nested 566c504b); the file on disk carries
  isBannerBusy_801E754 at 31072-31098 with the `HudElementMask & 0x8000` body — cite used.
- Unverified: (1) whether the 8 kill-timing frames at k=297..304 shift — untouched by the
  port (the 0x0C edge stays at ours k=405 vs canon 305, the accumulated window offset);
  (2) whether bit 15's clear is the same event that ends opening's ENEMY DELETED banner
  (canon's teardown record: 0x8084 k=306..363, 58 exports — same length, same clear site
  sub_801CEFA, but the teardown spawn route sub_80081A4's own arm was not traced); (3)
  what breaks pixels when the record exists without drawing (the two strip-less attempts).
