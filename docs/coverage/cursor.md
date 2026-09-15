# Cursor row — coverage notes

## State at F37h (2026-09-14, branch wt/f37h)

Cursor isolated row: total 10 / worst 9 over 170 frames (FAILED).
The two non-zero frames:
- k=37 (canon 52, rust 282): 9 px
- k=97 (canon 112, rust 342): 1 px

(The ticket predicted 3/3/170 from F37g; the live measurement is
10/9/170. 0fb54d4 T7b also reported "60 isolated rows 0 except
cursor 10/9/170", so the current state matches T7b's reading.
F37g's archived 3/3/170 was either momentary or measured under
slightly different conditions.)

## Attribution (composite 10 px)

BG-only diff == composite diff at these two frames: every differing
pixel sits on BG1 (backdrop), NOT on OBJ. Per-layer captures
(--disable-obj, --only-bg 1/2/3):

| layer  | k=37 px | k=97 px | location                   |
|--------|---------|---------|----------------------------|
| BG1    |   18    |    2    | y=0..5, x=55..237 (x+128 repeats) |
| BG2    |    0    |    0    | --                          |
| BG3    |    0    |    0    | --                          |
| OBJ    |  155    |  155    | y=75..84, x=56..71 — HIDDEN by BG3 in composite |

The OBJ residue (155 px chip-window mark, rust has it, canon does
not) is occluded by BG3 in the composite and does not contribute
to the harness count. The composite 9 + 1 px residue IS BG1.

## Mechanism (per F37's own analysis)

The BG1 residue matches F37d's documented "sub-frame tile transfer"
residue at the same k=37 / k=97 frames: canon's QueueEightWordAlignedGFXTransfer
(sub_8001C94, asm/asm00_0.s:3752) queues the copy and drains it
mid-frame, so rows 0..5 still carry the previous step; our
backdrop.rs's `replace_tile` (src/backdrop.rs:263) lands before
scanline 0, so the whole frame shows the new tile. The seam is the
5-pixel-wide top-edge of a tile, and the four clusters at k=37
are the x+128 repeats of one tile (89-93, 106-109, 217-221, 234-237).

cite: src/backdrop.rs:230, src/backdrop.rs:259-263 (the replace_tile
call). canon: sub_8001C94, asm/asm00_0.s:3752.

## Scope conflict

The fix lives in src/backdrop.rs (the replace_tile call timing).
The ticket names src/custom.rs and src/battle.rs as the only
modifiable src files. The OBJ mark residue (155 px, hidden by BG3)
lives in src/custom.rs but does not affect the composite count.

This is a scope conflict — the ticket's premise (OAM/window-mark
residue) does not match the actual residue (BG1 backdrop phase).
Worker cannot close the k=37 / k=97 composite residue within the
named-files scope.

Escalated to supervisor.
