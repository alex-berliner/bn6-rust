# Every chip row reads zero

The multi-pass ticket that carried the 43 chip rows, F12, closed today with every one of them at 0 differing pixels against the real ROM, over every compared frame. Two days ago 28 were.

## What it took

- **The seed chips** (PoisSeed, IceSeed, GrasSeed): canon pushes the seed sheet's middle column last so it sorts above its neighbours in overlap zones; then the feet needed a per-family push order because the fix that helped seeds broke MiniBomb.
- **BugBomb and VDoll**: canon snaps the thrown object to its rest position at a fixed height, with a poison tick and a one-frame landing lag we lacked.
- **SuprVulc**: the muzzle-fire object rebuilt from canon's data, gated to that chip only.
- **Invisibl, the three Barriers and AreaGrab**: their popups were tied to whether an enemy was alive, where canon ties them to the battle HUD being live; AreaGrab's orbs then needed their art extracted byte for byte from the ROM, a draw order, and a palette walk on the burst.
- **Chip-use**, the last one, turned out to measure nothing: canon's scripted press never fired in a zero-enemy arena, so the row was re-cut to deliver the press into canon's input data, and then it read 0 on all 30 frames.

Each landing was reproduced from a clean checkout before merging, and each chip row has a shifted negative fixture that must keep failing, so a zero is never a blind comparison.

## Cost

The eleven F12 passes cost $1.13 of worker and verifier time on the cheap tier, about a dime a chip family. The whole run that finished the series spent $0.17 per landed ticket.

Two of the families, before and after; the rest are in the [gallery](../gifs.html) under their F12 names.

![PoisSeed across the seed-sheet fix](../captures/chip-poisseed-f12d-progress.gif)

![AreaGrab across the orbs pass](../captures/chip-areagrab-f12-progress.gif)
