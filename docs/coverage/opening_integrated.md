# Opening integrated — F38c measurement

## Baseline (HEAD)

```
opening    isolated    PASS                             total 0        worst 0      frames 40   | negative: not blind (total 86591)
opening    integrated  FAILED                           total 72499    worst 2691   frames 40   | negative: not blind (total 155601)
fitted constants: 19 (derived 424, peeked 145)
```

## Per-frame pixel breakdown (script `/tmp/measure_opening.py`)

```
k     total  top    mid    bot    x203-214
 0    1431      0   1431      0      0
 1    1719      0   1467    252      0
...
31    1702      0   1590    112      0
32    2118      0   1642    476     16
33    2691      0   2306    385     79
34    2691      0   2306    385     79
35    2440      0   2088    352     41
36    2440      0   2088    352     41
37    2610      0   2226    384     92
38    2610      0   2226    384     92
39    2635      0   2279    356     25
```

- **top (y=0..30)**: 0 throughout
- **mid (y=30..130)**: ~1400 baseline, +700 jump at k=33/34+ (1642→2306)
- **bot (y=130..160)**: ~200 baseline, jumps to ~400 at k=32+
- **x=203..214 cluster**: 0 for k=0..31, then 16/79/79/41/41/92/92/25 at k=32..39

## Per-frame OAM attribution (script `/tmp/dump_oam.py`, watch OAM 0x07000000 + PAL_OBJ 0x05000200)

### CANON at k=0 (canon_frame 120) — 12 OBJs, all OAM palette field bits 10-11 = 2

| y | x | shape/size | tile | role |
|---|---|------------|------|------|
| 18 | 0 | 1/2 | 948 | HUD |
| 18 | 32 | 0/1 | 956 | HUD |
| 70 | 49 | 0/2 | 9 | navi |
| 100 | 42 | 1/2 | 1 | navi |
| 102 | 41 | 0/1 | 25 | navi |
| 102 | 65 | 1/0 | 29 | navi |
| 64 | 174 | 2/2 | 35 | enemy (foot) |
| 68 | 166 | 2/0 | 43 | enemy (body) |
| 80 | 163 | 1/1 | 31 | enemy (head) |
| 112 | 174 | 2/2 | 35 | enemy (foot) |
| 116 | 166 | 2/0 | 43 | enemy (body) |
| 128 | 163 | 1/1 | 31 | enemy (head) |

### CANON at k=32 (canon_frame 152) — 15 OBJs, ADD 3 entries:

| y | x | shape/size | tile | role |
|---|---|------------|------|------|
| 88 | 214 | 2/2 | 35 | **second enemy (foot)** |
| 92 | 206 | 2/0 | 43 | **second enemy (body)** |
| 104 | 203 | 1/1 | 31 | **second enemy (head)** |

The second enemy cluster is a copy of the first enemy's tile triplet at x=203/206/214 (offset +40 from first cluster's x=163/166/174). Same tiles, same OAM palette field (bits 10-11 = 2).

### RUST at k=0 (rust_frame 127) — 14 OBJs

| y | x | shape/size | tile | role |
|---|---|------------|------|------|
| 18 | 0 | 1/2 | 196 | HUD (tile shift -752) |
| 18 | 32 | 0/1 | 204 | HUD (tile shift -752) |
| 70 | 49 | 0/2 | 132 | navi (tile shift +123) |
| 100 | 42 | 1/2 | 124 | navi (tile shift +123) |
| 102 | 41 | 0/1 | 148 | navi (tile shift +123) |
| 102 | 65 | 1/0 | 152 | navi (tile shift +123) |
| 64 | 134 | 2/2 | 158 | enemy (tile shift +123) |
| 68 | 126 | 2/0 | 166 | enemy (tile shift +123) |
| 80 | 123 | 1/1 | 154 | enemy (tile shift +123) |
| 84 | 132 | 2/0 | 0 | **spurious** (not in canon) |
| 84 | 140 | 2/0 | 8 | **spurious** (not in canon) |
| 88 | 174 | 2/2 | 172 | enemy (tile shift +123) |
| 92 | 166 | 2/0 | 180 | enemy (tile shift +123) |
| 104 | 163 | 1/1 | 168 | enemy (tile shift +123) |

### RUST at k=32 (rust_frame 159) — 19 OBJs, ADD 5 entries:

| y | x | shape/size | tile | role |
|---|---|------------|------|------|
| 108 | 172 | 2/0 | 8 | **spurious extra** (no match) |
| 108 | 180 | 2/0 | 0 | **spurious extra** (no match) |
| 116 | 206 | 2/0 | 194 | second enemy? (tile +151, not 43) |
| 112 | 214 | 2/2 | 186 | second enemy? (tile +151, not 35) |
| 128 | 203 | 1/1 | 182 | second enemy? (tile +151, not 31) |

RUST has the second enemy cluster materialize at k=32 but with WRONG tiles (+151 shift vs the +123 shift used by the first cluster), WRONG x (the body is at x=206 same as canon, but head at x=203 — shifted to y=128 instead of y=104), and an extra "spurious" pair at x=172/180 y=108 that has no analog in canon.

### PAL_OBJ fingerprints at k=0

**CANON** (canon_frame 120): palettes 0-10, 12, 14, 15 all populated (pal[0..6] distinct content; pal[7..9] full 16 colors of 0x0240; pal[10] 9 colors; pal[12] 15 colors; pal[14]/[15] 15 colors).

**RUST** (rust_frame 127): palettes 0-5 populated; palettes 6-15 ALL ZERO. The data is also shifted — our pal[0] matches canon pal[14], our pal[2] matches canon pal[0], our pal[4] matches canon pal[12]. This means **palette slot allocation** differs: our sprites are claiming slots 0-5 while canon claims 0-15 (and the per-sprite palette data ends up at the wrong slot index for us).

## Mechanism notes

- The PAL_OBJ fingerprint mismatch shows this is fundamentally a palette-slot allocation/load order problem, not a per-sprite palette index problem. Both sides write `frame.pal + palette_add` into PAL_OBJ at a slot determined by agb's `PaletteVramSingle::try_allocate_shared`, but the slot allocation order diverges.
- The second enemy cluster materialize at k=32 is a port-missing: canon uses the same `tile + offset` arithmetic for both clusters, but our port only materializes the first cluster. The tiles at x=203..214 y=88..104 should be a copy of the first cluster's tile triplet with a +40 x-offset.
- `sub_8112D9C` (asm32.s:9735) is a state dispatcher for oAIAttackVars_Unk_00 — NOT the materialize. The actual materialize for the intro hunk is in `asm00_1.s` (the per-element introduction routine); the second enemy cluster likely runs through `object_spawnType1` (asm00_1.s:299-316) at a 32-tick offset.

## Outstanding work

The PAL_OBJ slot-0-5 vs 0-15 divergence and the missing second-cluster materialize are the two named defects. The fix needs to:
1. Trace which sprite claims PAL_OBJ slot N and reorder the load order so each sprite maps to the same slot canon does (port the order from asm00_1.s's per-element introduction routine).
2. Port the second enemy cluster materialize — the second cluster's tiles are the first cluster's tiles with the panel x-offset applied; the materialize path is shared with the first cluster's setup at k=0 but triggered on a 32-tick delay.

This measurement is sufficient for the next F38c dispatch to drive the port.

## F38d re-measurement (2026-09-15)

Re-ran `tools/harness.py --only opening --ui integrated` on HEAD: 72499/2691/40 (unchanged from F38c).
Re-ran `tools/probe.py --oam --pal` via `/tmp/dump_oam.py` for k=0..39 on both sides — F38c data confirmed.

### Per-frame OAM totals (this re-measurement)

| k | canon OBJs | rust OBJs | rust-canon |
|---|------------|-----------|------------|
| 0  | 12 | 14 | +2 (spurious at y=84) |
| 1  | 12 | 14 | +2 (spurious at y=84) |
| 32 | 15 | 19 | +4 (spurious at y=84, y=108) |
| 33 | 15 | 19 | +4 |
| 39 | 15 | 19 | +4 |

### PAL_OBJ 4-bit palette field on every OAM entry at k=39

| side | HUD | navi | enemy | spurious |
|------|-----|------|-------|----------|
| canon | 2 | 2 | 6 | n/a |
| rust  | 2 | 10 | 14 | 2 |

The OAM palette field (attr2 bits 10-11) is the SAME (0b2 = bit-1 set) on every visible OAM
entry on both sides; the 4-bit `pal` field (bits 10-13 of attr2, when extended) differs:
canon uses palette indices 2 (navi/HUD) + 6 (enemy) + 0 (no entry), rust uses 2 (HUD), 10
(navi), 14 (enemy), 2 (spurious).

### Position summary (k=39)

| role | canon | rust | diff |
|------|-------|------|------|
| navi       | x=41-65, y=70-102 | x=41-65, y=70-102 | match |
| enemy 1    | x=163-174, y=64-80 | x=123-134, y=64-80 | rust -40px x |
| enemy 2    | x=163-174, y=112-128 | x=163-174, y=88-104 | rust y -24px |
| enemy 3 (k=32+) | x=203-214, y=88-104 | x=203-214, y=112-128 | rust y +24px |
| spurious   | n/a | y=84 (x=132/140), y=108 (x=172/180) | 4 extra |

So the rust second cluster materializes at y=88-104 (rust: front-row panel 5), while canon's
second cluster is at y=112-128 (panel 5 row 3). And rust's third cluster at y=112-128
matches what canon drew for its SECOND cluster. Rust's first cluster is at x=123-134 (panel 4
from rust's diagonal `(enemy_col+i, enemy_row+i)` spawn), canon's first cluster is at x=163-174
(panel 5). Two distinct position bugs.

## F38d port attempt: NOT LANDED

The two cited mechanisms need deep changes that did not land within budget:

1. **PAL_OBJ slot-allocation order** in `src/actor.rs`: the slot index for each sprite is
   picked by `PaletteVramSingle::try_allocate_shared` (src/spr.rs:701-761) in call order. The
   order canon uses is dictated by the per-element introduction routine in
   `reference/bn6f/asm/asm00_1.s:8695` (`spawnEnemy_80073E2`) and the materialize animation
   `reference/bn6f/asm/asm00_2.s:16101` (`sub_801641A`, called from the `off_80163A8`
   jumptable at `:16046`). A speculative re-order in src/actor.rs / src/spr.rs could
   collapse the +123 / +151 tile shifts but would be a fitted palette index, not a port.

2. **Second-cluster materialize at k=32+** in `src/objects.rs`: the per-element materialize
   is `sub_801641A` (asm00_2.s:16101). The 32-tick duration comes from `APPEAR_STEPS *
   APPEAR_TICKS_PER_STEP = 16 * 2 = 32` (`src/actor.rs:257`) which matches
   `sub_801641A`'s outer/inner counter (asm00_2.s:16106-16136). The second enemy DOES
   materialize in rust at the right offset (rust k=32 adds 5 OBJs), but the
   panel position and tile VRAM offset differ from canon.

The "fitted constants in src/" count stayed at 19; no new fitted constants were introduced.
No canonical ROM data was modified. No allowlist change was made.

What is unverified (the end-sequence integration rows — warp/buster/chip-use — they need the
end-sequence state machine ticket, not this one).
