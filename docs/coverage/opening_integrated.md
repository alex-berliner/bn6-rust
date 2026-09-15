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
