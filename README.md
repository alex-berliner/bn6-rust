# bn

A reimplementation of Mega Man Battle Network 6's battle system as a real
Game Boy Advance ROM, in Rust on the [agb](https://github.com/agbrs/agb)
crate. Data and behaviour come from the
[bn6f disassembly](https://github.com/dism-exe/bn6f), checked out as a
submodule under `reference/`, rather than from memory of the games: sprites,
tiles, palettes and fonts are extracted from it, and each mechanic is written
against the routine that implements it, with the `file:line` cited in the code.

## Building

Needs a nightly toolchain (`rust-toolchain.toml` pins it), and mGBA to run.

    cargo build                                  # target/thumbv4t-none-eabi/debug/bn
    cargo run                                    # launches mgba-qt

Controls: d-pad warps between panels, A fires the buster (hold and release
for a charged shot), B cracks the panel underfoot.

## What is implemented

- The 6x3 field, with per-panel state: panels crack, give way when whoever
  stood on them leaves, and regenerate after 600 frames with a warning blink.
- Navis from the game's own sprite containers, plain and LZ77-compressed,
  composed from their OAM lists and driven by their animation tables.
- Movement as the game's warp: a 3/5/4-frame state machine that commits the
  panel at the midpoint of the dissolve.
- The buster and charge shot, with the game's damage formulas, a travelling
  shot that hops one panel every two frames, flinching, HP drawn with the
  game's digit font, a hit flash with a post-hit mercy window, and deletion:
  the death pose flashing white under the game's own effect until the navi
  is gone.
- First-pass enemy AI: ProtoMan lines up with the player, warps to the
  facing panel and thrusts; Colonel slashes a telegraphed shape around the
  centre of the player's side, or brings his sword down on the front
  column. The attacks and their timings are the game's; ProtoMan's pacing is
  the average of the game's counter, Colonel's a placeholder.

- The custom gauge, as the game's counter: 0xd a frame, full at 0x4000, then
  the pause that precedes chip selection. The bar itself is not drawn: two
  passes over the disassembly found no display code that reads the value,
  so rather than invent a fill it stays invisible until that is understood.

Where a value is not yet taken from the disassembly -- enemy HP, Colonel's
pacing, some effect timings -- the code says so at the point of use.

## Asset pipeline

`tools/` holds the extractors. All of them read straight from the submodule
and write into `assets/`, which is committed so the ROM builds without them.

    python3 tools/spr_export.py reference/bn6f/data/sprites/battleSpriteMegaMan.spr assets/megaman.bin
    python3 tools/field_export.py assets/field.bin
    python3 tools/font_export.py assets/font.bin
    python3 tools/spr_dump.py <sprite> out.png [--anim N]     # contact sheet, for looking

`tools/spr.py` documents the sprite container format, which was reverse
engineered for this; `tools/bnasm.py` reads data out of the `.s` files and
decompresses GBA LZ77.

## Checking it without a screen

    tools/capture.sh shot  <rom> out.png [keys...]
    tools/capture.sh burst <rom> outdir <count> [keys...]

Boots the ROM under Xvfb, sends key presses and writes PNGs. Two things
learned the hard way: mGBA ignores `xdotool key --window`, so the window has
to be activated first; and a tight capture loop starves the emulator, so put
a small sleep between grabs and look at the frames rather than trusting a
pixel-count metric.

## Layout

    src/main.rs    battle loop and input
    src/actor.rs   a navi: movement, attack, flinch, HP, as one action slot
    src/ai.rs      enemy behaviour
    src/shot.rs    the buster's travelling hitbox
    src/field.rs   the field background and per-panel state
    src/hud.rs     HP numbers
    src/spr.rs     sprite asset reader and animation player
    vendor/agb     agb, vendored so engine-level additions can be made in
                   place; so far a Mosaic control and Object::set_mosaic
