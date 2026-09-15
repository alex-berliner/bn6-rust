# gunner — notes

## T9l (2026-09-15): the row's own backdrop seeds, and the residue split

- Seeds derived from canon's own counters at canon_ref=80 (probe.py watch on the row's own
  canon Side): counters −640/−320 (battle frame f=80), anim entry 15/Timer 7 → position 81.
  With offset 25: nx=26, na=28 → scroll_xq=108, scroll_yq=54, art position 54 = entry 11/Timer 2.
  Landed on GUNNER_ROW (peeked tag); the old 5/4/424/724 were FIELD_ROW's.
- gunner 2850534/38237/130 → **2105613/38237/130**. BG1-only 1524416 → **230400** — exactly six
  full-screen frames (k=0..5); BG1 is 0 for k≥6, the backdrop is now exact.
- Layer table after: BG1 230400 · BG3 1426551 · all-BG (--disable-obj) 1949547 · OBJ-only
  (--disable-bg) 636883.
- Remaining residue: k=0..5 full-screen canon fade-in (OBJ mean 93→12); k=6..75 BG3 ~2047/frame
  (two enemy HP boxes y0..15 x100..190 + the gauge bar y152 x12..60, canon's reads full); k≥77
  BG3 plateau 21182/frame — canon's gauge-full pause auto-opens the chip window on BG3 (slide
  ~156, settled 165 — src/battle.rs:1998's documented frame-165 auto-open) and pauses canon's
  battle; OBJ plateau is downstream. NOT the aim cursor: no 3 px/frame walk in the OBJ diff
  bboxes (k=10..40 static y52..119 x59..197; growth from k=45 sits in the shot region).
- The next lever is GUNNER_ROW's `gauge` (fixture maps nonzero → GAUGE_FULL), not the attack
  logic (T9k) and not the cursor (T9l).
