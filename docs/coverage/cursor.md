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
