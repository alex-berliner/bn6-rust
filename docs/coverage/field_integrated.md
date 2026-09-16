# `field` integrated residue — per-layer attribution (F45, 2026-09-16)

Row: `field` integrated = **158935 total / 5606 worst / 40 frames**, negative not blind
<!-- Superseded by ROM version, 2026-09-15 (F48's rule: a non-zero total carries its build identity).
     The figure above was the F45-era reading on built ROM sha256 ab80121e..., and F48 showed it was
     never machine-gated at landing (verify_rows' old matcher could only match the isolated line).
     On today's tree -- ROM 1997be3b..., produced by T17/T19's chip-asset change -- the row reads
     158930 / 5601 / 40, negative 261029, and that value IS machine-gated (verify_rows HEAD
     --expect field=158930/5601/40/261029 -> MATCH (integrated line); a deliberately wrong expect
     returns MISMATCH, so the gate is live). The -23 step is deterministic and explained; the +18
     between F45's 158935 and F46's 158953 is NOT, since both trees build ab80121e -- see
     docs/measurement-drift.md. Cite 158935 only as a historical quote, never as the current row. -->
(261034). Re-measured on this branch before any edit; the row's own entry is unchanged.
`field` isolated = 0/0/40 (neg 1139): the subject is OBJ and OBJ matches, so the residue is a
BG/window/blend story. Fitted constants: **19** (derived 430, peeked 147).

## The boundary

Rust capture **121 = battle 110 = k=5** on the `field` row (rust base 8 + offset 108 = 116;
canon_ref 130). At that capture `self.shown` becomes `Some` and `src/battle.rs:4546-4549`
skips `filler_bg`, so every layer drops one hardware BG (backdrop BG1→BG0, panels BG2→BG1,
HUD BG3→BG2, `shown`→BG3) while canon's own RESULT window has not started (canon ~154).
Captures 118-120 are byte-identical stall frames. Same content therefore pairs:

* **k=0..4 (pre-boundary):** the SAME `--only-bg N` on both sides.
* **k>=5 (post-boundary):** canon `--only-bg N` vs rust `--only-bg N-1`.

The rows: `field-bg1` (canon BG1 backdrop vs rust BG0), `field-bg2` (canon BG2 panels vs
rust BG1), `field-bg3` (canon BG3 HUD vs rust BG2), all `Align(canon_ref=135,
rust_offset=113, search=None)`, frames=40 — the `field` row's event-locked pairing moved
past the 5 pre-boundary frames. Rust capture 121 is **k=0** on the post rows, **k=5** on
`field` itself.

**The N/N-1 compensation is confirmed by collapse, not assumption:** F42's both-sides
`--only-bg 1` mask was 100% saturated on 34 of 40 frames (a black-screen comparison). With
the compensated pairing the same layer's mask peaks at **37.9%** and never saturates; and
`field-bg2` reads **0 differing pixels on 39 of 40 frames** — a wrong pairing (panels vs
backdrop) cannot read byte-identical for 39 straight frames.

## The rule (recon F45 §3, applied before trusting any number)

A per-layer isolation frame whose differing-pixel mask covers more than **X = 75%** of the
240x160 screen (28800 px) is a full-screen render, not a layer mask, and is **rejected**: no
number from it may be quoted. X=75% sits inside the measured gap between usable masks
(28.9% worst pre-boundary) and F42's saturated ones (92.5% at the boundary, 100% after).
The mask is a property of the paired captures (one RGB-only diff per frame
`tools/chip_compare.py`), so per frame there is one coverage number per mask; the per-SIDE
content is fixed by each side's own flag (rust `--only-bg N-1`, canon `--only-bg N`), which
is what makes the two sides the same layer.

**Rejected frames: 0.** No frame in any mask used below reaches 75%.

## Per-frame coverage table

`integ` = the unchanged `field` integrated row (per-k from F42's kept integrated capture,
sums exactly to the row's own 158935/5606/40). Coverage = mask px / 38400. `pre-bg1` =
pre-boundary same-N BG1-only mask from F42's kept `--only-bg 1`-on-both-sides capture
(base 116, canon_ref 130), re-derived offline; its integrated per-k reproduces main's row
exactly, so the rust ROM it captured renders identically to main on these frames.

Pre-boundary (the same-N window, `field` k=0..4 = rust 116..120 <-> canon 130..134).
For reference, F42's own both-sides BG1 mask at k=5 read 35505 (92.5%) — saturated under
the rule, REJECTED, and no number from it is used anywhere below; every mask quoted here
comes from the compensated post rows or the same-N pre-boundary frames, all <=75%:

| field k | integ | pre-bg1 | pre-bg1 % |
|---|---|---|---|
| 0 | 0 | 0 | 0.0 |
| 1 | 0 | 0 | 0.0 |
| 2 | 3566 | 7362 | 19.2 |
| 3 | 5319 | 11117 | 29.0 |
| 4 | 5319 | 11117 | 29.0 |

Post rows (post k = `field` k - 5; post k=1..34 = `field` k=6..39):

| post k | field k | integ | bg1 | bg1 % | bg2 | bg2 % | bg3 | bg3 % |
|---|---|---|---|---|---|---|---|---|
| 0 | 5 | 5606 | 14559 | 37.9 | 4560 | 11.9 | 704 | 1.8 |
| 1 | 6 | 4092 | 8642 | 22.5 | 0 | 0.0 | 0 | 0.0 |
| 2 | 7 | 5515 | 11608 | 30.2 | 0 | 0.0 | 0 | 0.0 |
| 3 | 8 | 4701 | 9923 | 25.8 | 0 | 0.0 | 0 | 0.0 |
| 4 | 9 | 5545 | 11679 | 30.4 | 0 | 0.0 | 0 | 0.0 |
| 5 | 10 | 4911 | 10419 | 27.1 | 0 | 0.0 | 0 | 0.0 |
| 6 | 11 | 5488 | 11665 | 30.4 | 0 | 0.0 | 0 | 0.0 |
| 7 | 12 | 5335 | 11385 | 29.6 | 0 | 0.0 | 0 | 0.0 |
| 8 | 13 | 5075 | 10751 | 28.0 | 0 | 0.0 | 0 | 0.0 |
| 9 | 14 | 3868 | 8263 | 21.5 | 0 | 0.0 | 0 | 0.0 |
| 10 | 15 | 5093 | 10830 | 28.2 | 0 | 0.0 | 0 | 0.0 |
| 11 | 16 | 4342 | 9263 | 24.1 | 0 | 0.0 | 0 | 0.0 |
| 12 | 17 | 5113 | 10900 | 28.4 | 0 | 0.0 | 0 | 0.0 |
| 13 | 18 | 4614 | 9879 | 25.7 | 0 | 0.0 | 0 | 0.0 |
| 14 | 19 | 5002 | 10786 | 28.1 | 0 | 0.0 | 0 | 0.0 |
| 15 | 20 | 4671 | 10057 | 26.2 | 0 | 0.0 | 0 | 0.0 |
| 16 | 21 | 4361 | 9492 | 24.7 | 0 | 0.0 | 0 | 0.0 |
| 17 | 22 | 3358 | 7362 | 19.2 | 0 | 0.0 | 0 | 0.0 |
| 18 | 23 | 4374 | 9536 | 24.8 | 0 | 0.0 | 0 | 0.0 |
| 19 | 24 | 3528 | 7893 | 20.6 | 0 | 0.0 | 1917 | 5.0 |
| 20 | 25 | 4281 | 9570 | 24.9 | 0 | 0.0 | 3837 | 10.0 |
| 21 | 26 | 3292 | 7338 | 19.1 | 0 | 0.0 | 5757 | 15.0 |
| 22 | 27 | 4243 | 9430 | 24.6 | 0 | 0.0 | 7677 | 20.0 |
| 23 | 28 | 3470 | 7822 | 20.4 | 0 | 0.0 | 9696 | 25.2 |
| 24 | 29 | 3977 | 9170 | 23.9 | 0 | 0.0 | 11744 | 30.6 |
| 25 | 30 | 3170 | 6990 | 18.2 | 0 | 0.0 | 13792 | 35.9 |
| 26 | 31 | 3961 | 9141 | 23.8 | 0 | 0.0 | 15840 | 41.2 |
| 27 | 32 | 3384 | 7521 | 19.6 | 0 | 0.0 | 17973 | 46.8 |
| 28 | 33 | 3623 | 9104 | 23.7 | 0 | 0.0 | 20197 | 52.6 |
| 29 | 34 | 2788 | 6810 | 17.7 | 0 | 0.0 | 22421 | 58.4 |
| 30 | 35 | 3149 | 8896 | 23.2 | 0 | 0.0 | 24642 | 64.2 |
| 31 | 36 | 2673 | 7261 | 18.9 | 0 | 0.0 | 24818 | 64.6 |
| 32 | 37 | 2836 | 8543 | 22.2 | 0 | 0.0 | 24906 | 64.9 |
| 33 | 38 | 2465 | 6422 | 16.7 | 0 | 0.0 | 24906 | 64.9 |
| 34 | 39 | 2827 | 8477 | 22.1 | 0 | 0.0 | 24906 | 64.9 |
| 35 | 40..44 | (past field's window) | 6786 | 17.7 | 0 | 0.0 | 24906 | 64.9 |
| 36 | 40..44 | (past field's window) | 8407 | 21.9 | 0 | 0.0 | 24906 | 64.9 |
| 37 | 40..44 | (past field's window) | 7645 | 19.9 | 0 | 0.0 | 24906 | 64.9 |
| 38 | 40..44 | (past field's window) | 9584 | 25.0 | 0 | 0.0 | 24906 | 64.9 |
| 39 | 40..44 | (past field's window) | 7967 | 20.7 | 0 | 0.0 | 24906 | 64.9 |

(Full 40-value count lines for every mask are in docs/worklog/F45.md; the table shows the
shape — every bg1 frame 16.7-37.9%, bg2 zero except the boundary frame, bg3 zero until
canon's RESULT arrives.)


Row totals: `field-bg1` **367776** (worst 14559, neg 402740), `field-bg2` **4560** (worst
4560, neg 4560 — non-blind only via the boundary frame), `field-bg3` **380263** (worst
24906, neg 405169). All negatives non-blind. The HARNESS LINE is the
citable number for each row; the per-frame tables are transcriptions of the kept capture
dirs (/tmp/bn-cd4ee804/, re-diffed with chip_compare.diff_frames this pass, bg3 corrected
from a one-frame shift), and any discrepancy is a transcription bug, not a measurement.

## Attribution — by-index bookkeeping, layer assignment by elimination

* **k=0,1 (0 px):** nothing to attribute.
* **k=2..4 (14204 px) — backdrop, pre-boundary.** The same-N BG1-only mask reads
  7362/11117/11117 (coverage 19.2/29.0/29.0%, all <=75%, none rejected) — MORE than the
  integrated 3566/5319/5319 on each frame: the arena (panels/HUD/OBJ drawn over the
  backdrop) hides part of the backdrop divergence. These are the three byte-identical stall
  frames 118-120.
* **k=5 (5606 px) — the boundary frame itself.** All three layers' masks are usable there
  (backdrop 14559/37.9%, panels 4560/11.9%, HUD 704/1.8%): the frame where the stack
  renumbers, backdrop-dominant. No frame rejected.
* **k=6..39 (139125 px, 87.5% of the row) — assigned to the backdrop by elimination.**
  - panels (`field-bg2`): **0 px on every frame k=1..39** — panels carry nothing.
  - HUD (`field-bg3`): **0 px for k=1..18** — HUD content matches. From k=19 the row diverges
    in an exact 1917 px/frame ramp saturating at 24906 (64.9%): that is canon's own RESULT
    window slide-in starting at canon 154 = k=19, drawn on canon BG3 over the HUD, compared
    against rust's HUD (BG2). It is a z-order/stack difference (canon: RESULT overwrites HUD
    on one tilemap; rust: HUD on BG2, `shown` RESULT on BG3), NOT a HUD content defect — in
    the integrated composite there is no spike at k>=19 (integ stays 2.4-5.6k), i.e. both
    sides render the same RESULT content and the stack difference is invisible in the
    composite.
  - backdrop (`field-bg1`): nonzero on **every** one of the 40 frames, 6422..14559 px
    (coverage 16.7-37.9%, never saturated, zero frames rejected). Its isolated diff exceeds
    the integrated diff on every frame — the arena hides 52-67% of it (1 - integ/bg1
    recomputed from the table; min 52.5%, max 66.8%; pre-boundary 51.6%/52.2%).
  - OBJ: 0/0/40 (`field` isolated, `--disable-bg` blanks all 4 BGs and both WINs, keeps OBJ).
  - So for k=6..39 the only measured carrier of integrated residue is the backdrop.

**Bookkeeping: the k=2..4 / k=5 / k=6..39 split of the row's own 158935 is by frame index
and closes trivially; layers are assigned only by elimination (panels 0 on 39/40 frames,
HUD 0 before canon 154, OBJ 0/0/40), with windows and blend/mosaic unexcluded.** The three
field-bgN rows measure a paired --only-bg composite on the post-boundary N/N-1 pairing, so
their totals (367776/4560/380263) include any systematic difference that pairing itself
introduces and are never summed against, or compared with, the 158935 residue; 14204/5606/
139125 are the field row's own integrated per-frame sums partitioned by k, and the backdrop
attribution of the 139125 is an elimination inference, not a measurement. Rejected frames:
0. Uncovered px: 0.

## What cannot be tested with this tooling (ticket step 5)

* **Windows:** both `--disable-bg` and `--only-bg N` force `disableWIN[0]=disableWIN[1]=true`
  (`tools/mgba_capture.c:396-398` and `:549-550`). No capture on this row has ever had a
  window on, so a window claim cannot come from any isolation mechanism here at all.
* **BLEND (BLDCNT/BLDALPHA/BLDY) and mosaic:** untouched by every capture flag (grep across
  `tools/*.c`, `tools/*.py` is empty), active in both integrated and isolation captures, and
  never isolated. They could in principle carry composite-only residue where every layer
  mask reads equal; I could not test them because no flag renders a blend-off/mosaic-off
  frame, and the capture budget was spent. With every other BG disabled there is nothing
  for blend to blend with, so a blend-only or window-only composite difference is
  structurally invisible to all three masks — which is exactly why windows and
  blend/mosaic stay unexcluded in the bookkeeping above.
* **BG2-only and BG0-only full composites** (F42 never tested them): not captured — the
  6-capture budget went to the three post rows that attribute the 139125 px bulk. Unmeasured.
* **Pre-boundary panels/HUD isolation (same-N rows for k=0..4):** not captured (budget);
  the pre-boundary attribution rests on the backdrop mask alone (usable, 0/0/7362/11117/
  11117) exceeding the integrated diff per frame, which is consistent with backdrop-only
  divergence but does not by itself exclude a small additional contribution on other layers
  hidden by the backdrop overlap. Unverified remainder: <= 14204 px, bounded by k=2..4.

## One line of mechanism

ART-CLOCK PHASE, 3 frames — measured at tile level, F47 (kept dirs `/tmp/bn-f47/`, this
session; the scroll registers are write-only and latch, see below). Canon's resident
backdrop tile set steps at k=5,13,21,29,37 (tiles changed per edge: 36,34,8,5,9 — a
RESIDENT-SLOT count, slots 1..37 whose 32 B changed; the verifier's whole-window hash
counting gives 38,29,34,34 — different counting, same edges; from
`/tmp/bn-f47/canon_tiles.bin`, slots 1..37 watched per frame); ours steps at k=8,16,24,32
(36,34,8,5, same counting — the same schedule sequence; `/tmp/bn-f47/rust_tiles.bin`, slots
512..548). The scroll is NOT the carrier: a <=2 px integer shift zeroes the bg1 mask exactly
on 20/34 frames k=6..39 (base 300946 -> best 39580, dirs `/tmp/bn-f47/{canon,rust}_bg1`).
HEADLINE CAVEAT: the base total and the period-4 best-shift cycle (2,1),(1,1),(2,1),(1,0)
are convention-INDEPENDENT; the 39580 / 20-of-34 percentage is convention-DEPENDENT — these
figures use the overlap-only convention (compare only the (240-|dx|)x(160-|dy|) overlap
after translating canon; shifted-in edge pixels NOT charged, no wrap), while a +-4 run that
CHARGES edge pixels gives 53937 and 0-of-34. Given the two edge sets, the residual after
shift falls — arithmetically, it must — ONLY in [canon_edge, rust_edge): the 2-3 frames
where canon has already stepped and we have not yet (k=6-7, 13-15, 21-23, 29-31, 37-39);
that placement is a CONSEQUENCE of the edges (a prediction that held), not an independent
observation. So F42's "residue is art CONTENT" and the end-sequence attribution are both
wrong, and the live defect is: our art clock's edges fall 3 frames after canon's on an
otherwise identical period-8 schedule. The latency is in the CLOCK, not the upload —
`src/backdrop.rs:255-266` writes the step same-frame (replace_tile + commit, <=1 frame of
pipeline). WHERE in the clock the 3 frames live is UNMEASURED: seed vs free-run cannot be
separated from this fixture, and the earlier pointer to a seed path at
`src/battle.rs:2385-2403` was a miscite (that range is the results-window tail —
`self.results.show(...)`, `blit_slide`, `self.shown = Some(shown)` — plus
`prime_backdrop`'s doc-comment and signature; the seed gate is `prime_backdrop`'s
`match self.fixture` at battle.rs:2416, and it is unreachable under FIELD_ZERO,
tools/harness.py:1564, used by the field/field-bg1 rust side at :2034). The smallest step
that WOULD measure it: one `--peek`/`--watch` of canon's art-step counter (adjacent to
`eBGScrollCBCounters` at 0x02009690) at one known battle-relative frame, showing its step
index runs 3 ahead of ours. Register-level confirmation is structurally unavailable: the
readback is address-agnostic (`--watch` = tools/mgba_capture.c:966-972, `core->busRead8`
per byte after every rendered frame) and returns real per-register values where readable —
in the SAME frame the write-only scroll halfwords 0x04000010..0x1E all read one latch value
(cycling 0xd0fc/0x4211/0x4805/0xfffe, no ramp; rust: constant 0x30b8) while readable
WININ/WINOUT 0x48/0x4A read a genuine 0x3f3f (canon_videoio.bin, the 0x04000000:0x60
watch) — and HOFS/VOFS are write-only, so `--watch` cannot read ANY side's scroll position.
Canon's scroll ramp is instead taken from its own counters (`eBGScrollCBCounters`
0x02009690, `/tmp/bn-f47/canon_scrollcnt.bin`): SLOPE confirmed — 2400 -> 2088 falling
8/frame and 33968 -> 33812 falling 4/frame = 0.5 and 0.25 px/frame after >>4 — while the
absolute 82/41 -> 63/31 endpoints quoted in the F47 worklog table are NOT derivable from
the kept counters (2400>>4 = 150, 33968>>4 = 2123): slope confirmed, offset unexplained.
Ours tracks the ramp within the <=2 px shift dither. (0x040000D0..DE — the inverted premise
F47's ticket was written under — is DMA2/DMA3 territory, DMA2CNT = 0xD0 per
io_reg.h:119-137, and holds no scroll on either side; the scroll block is
0x04000010..0x1E, and its write-only-ness is the latch above.)

What IS established here: the positive controls that validate the N/N-1 pairing are
`field-bg2`'s 0 on 39/40 frames and `field-bg3`'s 0 on post k=1..18; `field-bg1` (never 0,
min 6422) and `field-bg3` post-154 carry no control of their own and may be cited for the
PRESENCE of a difference, never its magnitude.

## One line of what is unverified

That the post-boundary pairing is same-content rests on the collapse (saturation 100% ->
<=37.9%) plus `field-bg2`'s 39 zero frames — the `.show()`-order argument itself is still
inference, and the pre-boundary panels/HUD masks and the BLEND/mosaic channel were never
captured.

## Rows this ticket adds

`field-bg1`, `field-bg2`, `field-bg3` (post-boundary, notes state what each proves). The
existing `field` row is unchanged: this session it reads 158935/5606/40 integrated
(neg 261034) and 0/0/40 isolated (neg 1139). The pre-boundary same-N row (k=0..4,
`Align(canon_ref=130, rust_offset=108, search=None)`, frames=5) was NOT landed: the capture
budget (6) is exactly the three post rows, and its numbers are derived above from F42's kept
`--only-bg 1` capture; a follow-up can land it with the same recipe if verification wants it
harness-run.

## T22 — F47's open (c) ART CONTENT settled: ART FAITHFUL — canon SLOTWISE 37/37 x 7 steps
(slot k = `FRAMES[step][k-1]`; canon BG1 cell ids = asset MAP +1, port's = +512; 0 captures used)

F47's naive `s*37+k` art test failed on LAYOUT, not content. Rebuilt on the ROM's own upload
list — `BattleBackdropGFXAnimScript_807FB98` (dat20.s:148; initial
`gfx_anim_4bit_tile_copy gfx_dest=unk_6000040 num_tiles=0x24` :149, then 29
`gfx_anim_data_ptr` entries :150-178) scheduling `BattleBackdropTiles0-6` (dat20.s:181-225,
36 halfwords each, blob indices into GFXAnimTileBlob_8617488) — on F47's kept tile dumps
(`/tmp/bn-f47/{canon,rust}_tiles.bin`), analysis in `/tmp/bn-t22-backdrop-content/`:

- Transcription: `backdrop_export.py`'s `FRAMES[s]` == `[0] + table` byte-exact, 36/36 slots
  x 7 tables (tables index VRAM slots 2..37; slot 1 = the blank filler the map's empty cells
  point at).
- Canon is SLOTWISE faithful (the headline): canon VRAM slot k (slots 1..37 of the
  0x06000000:0x800 window, slot k at window offset k*32) holds `FRAMES[step][k-1]` — **37/37 at
  ALL 7 steps** (F47's named captures 140/148/156/164/172 → steps 5/6/0/1/2 each 37/37; steps 3
  and 4 attested in the same kept dump at caps 16-27 and 68-83, i.e. OUTSIDE F47's compared
  40-frame window). The slot relation is pinned independently by the map: canon's BG1 cell ids
  are the asset MAP values **+1** (ids 1..37, no 0; id 1 = the blank), the port's are the asset
  MAP values **+512**.
- The port is NOT slotwise faithful: its resident window reads **1/37 at every capture** (only
  the blank tile aligns slotwise) — the port permutes the tile array AND its map, and the two
  cancel. Measured on the COMPOSED render (map composed with the tile array) against the
  asset's composed render: **1024/1024 cells identical for canon at all 7 steps and for the
  port at 6 of 7 sampled steps** (the port's earliest step-0 capture reads 0/1024 until its map
  write lands, ~cap 30 — the tile write runs ahead of the map write in the port's first
  frames). Positions are therefore proven AS DRAWN, which is stronger than a set claim. The
  permutation's provenance ("map-scan first-occurrence order", worklog T22 step 2) is the
  worker's label and was NOT confirmed by the verifier audit — kept as a labelled hypothesis,
  not a result.
- Naive-grid control, reproduced IN MAGNITUDE only (verifier-hyper audit; the exact digits
  depend on the counting convention, so the convention is stated here). Naive convention:
  reading the canon window's first 37 tiles (offsets 0..1152) against the flat asset grid
  `s*37+k` gives best **2/37** (cap 174 `[2,2,1,0,1,0,2]`; cap 39 `[2,2,2,1,1,1,1]`; no step
  reaches 3) — F47's 2-3/37 magnitude. The +1-shifted variant (`s*37+(k-1)`, same 37 window
  positions) reads **36/37** — 36 of 37, because the window's first 32 bytes are not a backdrop
  slot. The corrected alignment — slots 1..37 at offsets 32..1216, canon slot k =
  `FRAMES[step][k-1]` — reads **37/37**. The off-by-one is DEMONSTRATED and stands: identical
  bytes, 37/37 under the corrected alignment versus single digits (2/37) under the naive one,
  independently pinned by the map's +1/+512 cell ids. (This pass's offline check
  `/tmp/bn-t22-backdrop-content/t22_convention_check2.py` reproduces the verifier's vectors
  exactly under the stated conventions; the worklog's original step-3 figures
  `[2,3,2,2,1,2,2]`/`[3,3,2,1,2,1,2]` were convention-muddled and are superseded — no exact
  3/37 digit match is claimed.)

So the ROM holds no tile the asset lacks at any step, on either side, and canon draws them
from the same cells slotwise while the port's permuted array+map composes to the same 1024
cells: `field`'s integrated residue stays timing-only, exactly the F42/F45/F46/F47 circle's
conclusion. No row moved, no src/ edit; built ROM byte-identical to main's (`cmp` = 0 differing
bytes, sha256 1997be3b4e8f463ac328aede2d5a027d7f73fcb8adcab5834592d71a7a419fed).

Forward-blocking limits (stated here so the next ticket hits them with the caveat, not after
it):

- Palette: do NOT extend "37/37 x 7" to the palette — bank 0 rests only on the exporter's
  "read from a live battle" comment; no palette watch exists in the kept dumps.
- Byte→art mapping: still 0/3, still a per-scene compare chain at `asm33.s:4168-4195`; nothing
  here proves byte 0x07 is the field stage's byte.
- The regenerated SCOPE prose carries typed constants (29 entries / 7 tables / 36 halfwords /
  37/37) that nothing re-verifies: if `FRAMES` ever changes, SCOPE keeps asserting 37/37
  forever. "Generated file" here means generator-assembled prose, NOT machine-checked.
- This ticket CLOSES F47's stated open item rather than overturning a landed claim:
  `docs/worklog/F47.md:156-158` and `:262` already disclaimed the naive grid and named exactly
  this recipe (the anim-script upload list) as the way to settle (c). F47's phase headline is
  untouched: it comes from capture-to-capture change counts, which need no asset indexing at
  all.

## T23 — F47's 3-frame art-clock phase located: canon's OWN anim-state record read over the field row's window — VERDICT: SEED

F47 left "WHERE the phase difference lives" open. Read from canon's own anim-state machinery
(one capture run, 2026-09-15; artifacts kept for the auditor in `/tmp/bn-t23-art-clock-phase/` —
`canon_animstates.bin`, `canon_scrollcnt_run1.bin`, `t23_analyze.py`, `t23_align.py`; the four
/tmp canon roots untouched):

- The watch: 175 frames from the `field` row's own canon side (sterile ROM +
  `/tmp/pausedwithcannon.state` + DELETE_ENEMY `0x0203ab84:0 0x0203ab86:0` + script `Start@10`,
  `--disable-bg`), watching ALL of `eGFXAnimStates` `0x020094c0:0x1d0` (19 x 24-byte records,
  // canon: eGFXAnimStates, ewram.s:596) AND `eBGScrollCBCounters` `0x02009690:0x8`. Run
  identity: the scroll-counter stream is **175/175 word-identical** to F47's kept
  `/tmp/bn-f47/canon_scrollcnt.bin` at shift 0 — this run IS F47's capture indexing; every
  number below is directly comparable to F47's tile edges.
- Record 0's six halfwords (only record 0 of 19 changes — it IS the backdrop anim):
  hw0 `0x0001` constant (active flag + anim id, `LoadGFXAnim` 0x8001b1c,
  reference/bn6f/docs/decomp/asm00_0.c:2316-2339); **hw1 = frame countdown** — decremented
  1/frame and reloaded from the entry's hold field by the ticker `ProcessGFXAnims` 0x8001b94
  (asm00_0.c:2359-2394, `*(v0+1) -= 1; if <= 0` reload), observed `0008`→`0001` every frame;
  hw2:hw3 `0x0807fba4` constant = the anim script's LoopAddress (the same base
  `src/backdrop.rs`'s seed doc cites); **hw4:hw5 = entry index** — the current script-entry
  pointer, advanced +8/entry by `ProcessGFXAnims` (`*(v0+2) = v3`; "eight bytes an entry").
- Canon's clock edges MEASURED: the entry pointer advances at captures **139, 147, 155, 163,
  171** — every capture ≡ 3 (mod 8) in 135..174 and nowhere else. The countdown reloads to 8
  at 139..163 and to **4** at **171**: 171 is the supercycle WRAP to entry 0, whose hold is 4
  (pointer back at the script base `0x0807fba4`, printed value `0004`). Full 0..174 scanned:
  ramp-up edges at 3,7,11,15,19 (hold-4 entries), then steady every-8 spacing beginning at
  **27** (first 8-gap 19→27; 27,35,…,171). F47's tile-set edges
  (140,148,156,164,172) are exactly ONE capture later — a CORRECTION to the ticket's
  prediction that the index changes AT 140,148,...: the art CLOCK ticks at **k=4+8m** and the
  resident tile set follows at k=5+8m (pointer→VRAM lands the next capture).
- **The hold-schedule corroboration (strongest evidence here):** the countdown field is
  `ProcessGFXAnims`'s per-entry hold reload (`reference/bn6f/docs/decomp/asm00_0.c:2359-2394`,
  `v2 = *(v0+1) - 1; … *(v0+1) = v3[1]`; `+2` is the advanced pointer), and canon's dump
  matches **our own already-landed table `src/backdrop.rs:90-92` `STEP_HOLD = [4 × 10,
  8 × 19]` entry-for-entry**: capture 0 sits at entry 5 (`0x0807fbcc`) holding 4 through the
  edges at 3,7,11,15, switches to 8 at entry 10 (cap 19), and wraps to entry 0 (`0x0807fba4`,
  hold 4) at cap 171 — a **192-frame supercycle (10×4 + 19×8) reproduced by an independent
  175-frame dump**. Our side already carries the right hold data; the defect is the SEED, not
  the table. This is precisely what **T24** (sibling branch `wt/t24-art-clock-seed`) is now
  testing — it puts our art-clock countdown at canon's measured 4 and judges on the only
  lines containing backdrop pixels (field integrated, field-bg1).
- Paired k=0 numbers (F47's axis, canon 135+k ↔ rust 121+k): canon countdown hw1 at cap 135 =
  `0004`, canon entry = CommandPos `0x0807fc64`; resident step 4 (T22's table). Ours at paired
  k=0 (rust cap 121): resident step 4 (T22) — the STEP INDEX is EQUAL, but the timer phase is
  not: our seed is `FIELD_ZERO art_timer=7` (+1 construction lead = **8 at k=0**,
  tools/harness.py:1564 + src/backdrop.rs:233), so our first tick is at k=8 vs canon's k=4.
  The countdown comparison is invariant to the pairing's 8-frame ambiguity (the row's own
  Align offset 22 pairs rust 121 with canon 143, which reads the same `0004` — the two
  pairings differ by exactly one art period).
- **VERDICT: SEED** — canon's art timer is ALREADY 4 frames ahead of ours at paired k=0
  (countdown 4 vs 8), constant across all five measured edges, with no accumulating frame in
  the window (both timers decrement 1/frame, period 8 both sides). 4 − canon's 1-frame
  pointer→VRAM pipeline = F47's 3-frame tile-edge offset — this RECONCILES F47's in-hand
  number; it is NOT a prediction (F47's 3 was in hand before the equation). The 1 is measured
  as tile edge 140 − clock edge 139 (canon's own clock against canon's own VRAM, across two
  dumps of verified run identity, not fitted to close the gap), and our 8 is corroborated by
  F47's measured rust edge at k=8 — what a timer of 8 at k=0 predicts. A step-index-only
  comparison at k=0
  would have misread FREE-RUN (both show step 4); the countdown phase is the discriminator.
- src/ fix site (named, NOT edited): the seed path `prime_backdrop`'s `match self.fixture`
  (src/battle.rs:2416) → `Backdrop::seed`'s `self.timer = timer + 1` (src/backdrop.rs:231-233),
  fed by `FIELD_ZERO art_entry=10, art_timer=7` (tools/harness.py:1564); the fresh-battle
  default is `timer: STEP_HOLD[0] + 1` (src/backdrop.rs:179). Two corrections to F47's prose:
  the seed gate DOES fire under FIELD_ZERO (art_entry=10 ≠ `FIXTURE_UNSET` 0xFFFF, and
  `prime_backdrop` is called unconditionally at src/main.rs:372) — F47's "unreachable under
  FIELD_ZERO" parenthetical is a miscite, and F47's worklog now carries a `CORRECTED BY T23`
  retraction of it (main commit 3a96422, with the disk proof `harness.py:1564-1565`,
  `battle.rs:1576`/`:2417`, `main.rs:372`, `fixture.rs:132-134`); that refutation of a landed
  claim is the reason T24 exists (main 80246a5). Any timer-phase fix is a one-constant change
  at those lines. The earlier "must first reconcile that the `field` row reads 0/0/40"
  tension is ANSWERED: the passing `field` line is the ISOLATED `--disable-bg` variant, which
  switches off all four BG layers (`tools/mgba_capture.c:386-395`), so the backdrop is not in
  those compared pixels at all; the backdrop lives on `field` integrated and `field-bg1`.

No row added or changed; no src/ edit; built ROM byte-identical to main's (`cmp` = 0 differing
bytes, sha256 1997be3b4e8f463ac328aede2d5a027d7f73fcb8adcab5834592d71a7a419fed); 1 of ≤2
capture runs used.
