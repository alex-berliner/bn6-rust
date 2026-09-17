# cursor row -- seam-phase coupling (T111)

Row: `cursor` (isolated, frames 170, canon_ref 15, align search 225..250,
`--only-bg 3` on both sides). Row semantics frozen: same canon side, same
negative, same compare -- T111 changes none of them.

## The coupling: row class vs binary footprint

The cursor row's pass class (main: total 1 / worst 1 / 170) is NOT a stable
property of the game logic -- it is a layout-calibrated coincidence. agb's
`GraphicsFrame::commit` waits for vblank and then copies the WHOLE screenblock
into VRAM (`vendor/agb/agb/src/display/tiled/screenblock.rs:42`, `copy_tiles`
over `size.num_tiles()`), which always spills past vblank into the first
visible scanlines. On frames where tile contents change mid-copy, the cut
shows as stale-vs-new pixels at a phase (scanline/column of the cut) that is a
pure timing function of the binary's footprint: code addresses, loop code
alignment in ROM, struct sizes. T105 pass 6 bisected it: ANY feature-sized
delta re-rolls the phase (observed shapes (28,1), (19,19), (56@k7,6) across
footprint variants, all deterministic in their binary).

The cursor row's five cursor moves (rust frames 252/282/312/342/372 = k=7/37/
67/97/127: OK->4, 4->3, 3->2, 2->1, 1->0, CURSOR_DELAY=2) each run
`Custom::draw_card`'s card-replace burst, whose shadow writes land in
commit's copy; k=37 (the 4->3 transition) and k=97 (the 2->1 transition) are
the frames where the seam shows. k=97 carries main's own historical 1 px tear
(the "documented sub-frame seam" F3 saw).

## The pad (T111)

`SEAM_PHASE_PAD_ITERS` in src/main.rs: a busy-wait (`nop` loop) inside a
VBlank interrupt handler registered in `main`. interrupt_handler.s runs
`__RUST_INTERRUPT_HANDLER` (user closures included) before returning to the
BIOS's VBlankIntrWait, and commit's copies start after that return -- so each
iteration delays the copy START by ~5-8 cycles (~1.5 px of scanline),
every frame, identically. It reads and writes nothing; the rows are the
proof that it is timing-only.

Sized on the cursor row (2 captures per size, k table from the same captures):

| pad iters | total/worst | k=37 px | k=97 px |
|-----------|-------------|---------|---------|
| 0 (branch) | 29/28 | 28 | 1 |
| 1 | 26/25 | 25 | 1 |
| 8 | 16/15 | 15 | 1 |
| 16 | 7/6 | 6 | 1 |
| **17** | **1/1** | **0** | **1** |
| 18 | 18/17 | 17 | 1 |
| 20 | 26/25 | 25 | 1 |

V-bottom at 17: 17 iterations (~90-140 cycles) re-phases the copy cut onto
canon's on the k=37 frame, restoring the (0,1) shape -- k=37: 0 px, k=97:
1 px, i.e. main's own tear exactly, total <=1 / worst <=1.

## What every later landing must check

Any merge that moves code can re-roll the seam phases and move cursor off the
<=1 class. That is the landing's own check, not this ticket's: after any
landing, run the cursor row and compare against the class (total <=1, worst
<=1, frames 170; the tear's frame may move with layout). If it re-rolls,
T111's sweep protocol (one named const, V-table, ~6 sizes) re-fits the pad on
one ticket-sized loop.

## The anchor attempt (T118b, 2026-09-19) — bounded NEGATIVE

T118's census (its worklog: whole copy ~= 4.1k cycles ~= 3.3 scanlines, never
overruns the 68-line vblank budget) moved the model from "copy spills into
visible scanlines" to "phase-alignment coincidence". T118b measured the phase
response directly. Alignment for all numbers below: canon 15+k <-> rust
origin(8)+237+k; the cut on every measured out-of-class pair lives at
scanlines 0..4, x~217..238 (top-right corner), deepening by scanlines as the
phase moves off canon's.

### Footprint x pad (T111's knob, re-measured on today's main)

| footprint | ROM B | pad 0 | pad 13 | pad 17 | pad 21 |
|-----------|-------|-------|--------|--------|--------|
| main | 592536..592604 | 0/1 | — | 0/1 | — |
| +1132 B static | 595056..595140 | 0/1 | 0/1 | **17/6** | **25/3** |
| −1132 B asset | 591408..591492 | 0/1 | **19/1** | **40/1** | **55/1** |

(k37/k97 px; k7 = 0 everywhere. 1 pad iteration ~= 6.5 cycles ~= 1.6 px of cut
phase; one scanline = 1232 cycles ~= 190 iterations.)

So: NO fitted iteration count serves all footprints (T117's sweep failure is
explained — the pad itself pushes a re-rolled footprint out of class), but the
UNPADDED copy start was in class on all three footprints (3.6 KB span) on the
day of measurement. That unpadded in-class band is a layout coincidence, not a
mechanism — see below.

### Anchor to REG_VCOUNT (the ticket's step 3): measured NEGATIVE

`SEAM_ANCHOR_LY` spin in the VBlank closure (commit 8da06fb on wt/t118b,
reverted): the closure spins on the scanline count (0x04000006) so commit's
copy starts at a scanline. Measured (k37/k97):

| anchor layout variant | ROM B | cursor |
|------------------------|-------|--------|
| LY=160 spin (no trim) | 592564 | **31/19** |
| LY=160 + 1..4 nop trim | 592564..592580 | 31/19, 31/29, 31/29, 22/1 |
| LY=161 spin (one full scanline delay) | 592564 | **37/21** |

One full scanline of delay does NOT re-phase the cut into class: the phase
that sets the seam lives BELOW scanline granularity, so a scanline anchor
cannot see it, and the spin's own 28 bytes of code re-roll the phase on
main's own footprint (0/1 -> 31/19). The sub-scanline residue would need a
per-binary fitted trim — exactly the knob this ticket retires — and its
response is chaotic: the pad-0 layout is in-class across +-2.5 KB of asset
delta while a 28-byte code delta breaks it.

### Verdict

The <=1/1/170 class is a layout coincidence at sub-scanline granularity. What
still sets the phase: the code size/alignment of everything between the
VBlank interrupt entry and commit's copy (closure body, IRQ return path,
commit preamble). No footprint-stable knob was found: not the fitted pad (per
footprint), not an LY anchor, not LY+trim. The pad (fitted 17) stays on main;
any landing that moves code must re-run the cursor row (the existing rule at
the top of this file). A footprint-stable fix needs the copy placed at
canon's phase by construction (content/timing), not re-fitted after the fact.
