# T9l — gunner 2850534/38237/130: derive this row's own backdrop seed, then split the residue by layer

Branch: `wt/t9l-gunner-seed` · 2026-09-15 · worker-hyper

## Step 1 — baseline (`tools/harness.py --only gunner`, both variants identical, ui="both")

- gunner **isolated 2850534 / 38237 / 130**, integrated **2850534 / 38237 / 130** (HEAD a106d7a).
- offset **25** (search 0..40), rust_origin 8, canon_ref 80.
- five worst frames: k=0 (38237), k=1..3 (38223), k=4 (38169); then ~10-12k/frame k=6..76,
  ramp k=77..86, plateau 31644 from k≈87 to 129.
- negative: **not blind** (2852957).
- fitted constants at HEAD: 19.

## Step 2 — layer split (before seeds)

| config       | total   | worst | offset |
|--------------|---------|-------|--------|
| `--only-bg 1`  | 1524416 | 38400 | 0 |
| `--only-bg 3`  | 1426551 | 38237 | 1 |
| `--disable-obj`| 2770727 | 38237 | 25 |
| `--disable-bg` | 636883  | 38400 | 22 |

BG carries 2770727 of 2850534 (97%). Note the search slides to offset 0/1/22 on the isolated
layers — a phase-shifted periodic fill minimizes wherever, so those offsets are diagnostic only.

## Step 3 — peek of canon's own counters (probe.py watch, REAL + battlestart_gunner.state, the row's own Side)

- eBGScrollCBCounters: frame c reads −8(c+1)/−4(c+1); frozen one capture frame at 67/68
  (a one-frame stall the battle itself takes). At canon_ref=80: **−640/−320 = −8·80/−4·80**,
  so the battle frame **f = 80** (f0 = 1 at capture frame 0, net of the stall).
- eGFXAnimStates[0] at frame 80: entry **15** (CommandPos 0x0807fc1c, LoopAddress 0x0807fba4),
  Timer **7** → schedule position 80+8−7 = **81**.
- Derivation (offset 25, ORIGIN 8): nx = 26, na = 28 →
  scroll_xq = (2·80 − 2·26) mod 1024 = **108** (borrowed 424, Δ −316);
  scroll_yq = (80 − 26) mod 1024 = **54** (borrowed 724, Δ −670);
  art (81 − 28 + 1) mod 192 = **54 = entry 11 / Timer 2** (borrowed 5/4).
  Same inverse maps cursor's position 53 → entry 11/Timer 3, matching CURSOR_ROW.

## Step 4 — seeds landed

GUNNER_ROW `art_entry=11, art_timer=2, scroll_xq=108, scroll_yq=54`, tagged
`provenance: peeked -- canon's own counters at this row's canon_ref`. No new fitted constant (19).

- gunner **2850534 → 2105613** (isolated = integrated), worst still 38237 at k=0, negative not
  blind (2284867).
- per-layer after: `--only-bg 1` **230400** (−1.29M; exactly six full-screen frames k=0..5,
  BG1 reads 0 for k≥6 — the backdrop is exact), `--only-bg 3` **1426551** (unchanged, it is not
  backdrop), `--disable-obj` **1949547**, `--disable-bg` **636883** (unchanged).

## Step 5 — the residue, named to frame / layer / routine

1. **k=0..5, every layer full-screen** — canon fades from bright (canon OBJ mean 93, 77, 60,
   44, 28, 12; rust ~3): a fade tail canon shows at frames 80..85 that the rust side does not
   reproduce. Unidentified.
2. **k=6..75, BG3, ~2047/frame** — (a) the two enemy HP boxes, y0..15, x100..190 (this battle has
   TWO enemies; `mettaur`'s single box is exact, so it is the second box / pair layout, src/hud.rs
   territory); (b) the bottom-left custom gauge bar, y152, x12..60: canon's bar reads FULL from
   k=0 while GUNNER_ROW's borrowed `gauge=0` never fills.
3. **k≥77, BG3, plateau 21182/frame** — canon's gauge-full pause opens the chip window on BG3
   (slide from canon frame ~156; the documented "window comes up on its own at frame 165",
   src/battle.rs:1990-2006) and PAUSES canon's battle. Canon BG3 carries a left-half window
   (x0..117, full height) rust never draws; the OBJ plateau (~5.8k/frame) is downstream of that
   pause. The k=45..76 OBJ growth (dense y90..120, x to 239) precedes the window and sits in the
   shot region — the diff bboxes show NO 3 px/frame aim-cursor walk, so the ticket's cursor
   suspect (sub_8112F70, asm32.s:9958-9973) is NOT what the layers name.
4. Gauge register: 0x020352a0 (eStruct2035280+0x20) reads 0x0000 all 170 frames peeked on canon —
   the full-bar evidence is visual (the bar pixels), not from that address. The state's live gauge
   register is somewhere else (CurBattleDataPtr-relative?).

Dropped idea: porting the aim cursor per the ticket's cite — the split and the bboxes refute it.

## Next ticket's levers (unverified)

- GUNNER_ROW `gauge` — the fixture maps `gauge != 0 → GAUGE_FULL` (binary), so `gauge=1` should
  make our window open on canon's schedule and freeze our battle in step. NOT attempted here
  (gauge is outside this ticket's allowed GUNNER_ROW fields).
- The enemy HP box pair layout (second box) and the k=0..5 fade are independent, smaller.
