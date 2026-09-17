# buster_charge residue: the gauge strip is not on this screen (T114, 2026-09-18)

**Measured verdict:** the `buster_charge` isolated row (2498/188/32, negative 5113) renders
**only OBJ** — both sides run `--disable-bg` (tools/mgba_capture.c:380-397 sets
`disableBG[0..3]`), and the CUSTOM gauge is BG3 (`hud_bg`). Zero differing pixels at y≥140 in
all 32 compared frames; the earlier y158/dither attribution belongs to no measurement of this
row/alignment. No `hudtiles.rs` constant can move this row.

## Where the 2498 actually is

| residue | frames | region | owner |
|---|---|---|---|
| steady ~92 px/frame | k=6..30 (canon 136..160) | 16×8 patch at (73..87, 79..85) | canon draws a 16×8 flash OBJ, raw (72..74, 78), pri 2, pal 2 (pal 1 for its first frame), tiles 0x20/0x21 and 0x27/0x28 with frame-varying art; **our side spawns no such object** — our charged arm (`src/battle.rs:3576`, `Update::Strike { charged }`) pushes the bolt and skips every fx spawn |
| k=0 transient 188 px | k=0 only | navi sprite area (y58..121, x33..94) | the row's documented one-frame release skew (canon writes CurAction 0x10 ON frame 130, our export block one frame late) — harness buster_charge note, T106 |

Everything else matches pixel-identically, including both bolts (32×16 at (91,75) from canon
139) and all navi part OBJs. The missing art is not in `assets/buster_fx.bin`; it must be
exported from canon OBJ VRAM (tiles 0x20/0x21/0x27/0x28 + their OBJ palette entries), and the
spawn ported into the charged arm of `src/battle.rs` — both outside T114's file list.

## Seed sweep (bounded negative)

`gauge`/`gauge_tick` descriptor seeds, same canon capture and alignment (offset 207):

| seed | total | worst |
|---|---|---|
| baseline | 2498 | 188 |
| gauge=1 (not-full strip) | 2498 | 188 |
| gauge_tick=58 | 2498 | 188 |

The strip is phase-invariant here because it never renders. `BAR`'s `fitted -- NOT VERIFIED`
tag stays: nothing on this row can verify it (see docs/worklog/T114.md).
