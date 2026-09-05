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

Controls: d-pad warps between panels, B fires the buster (hold and release
for a charged shot) as in the game, where A is the chip button; Select
cracks the panel underfoot as a test aid.

## What is implemented

- The battle intro: the field revealed out of black, then the enemy navis
  materialising one at a time through mosaic and alpha, before control opens.
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
- Viruses: the Mettaur hops a row at a time to the player's row and sends
  its shockwave rolling down it; the Gunner's cursor walks the row until it
  finds the player, locks, and a volley of panel-anchored shots follows, each
  with its blinking warning. All at the game's HP, timings and damage.
- First-pass enemy AI: ProtoMan lines up with the player, warps to the
  facing panel and thrusts; Colonel slashes a telegraphed shape around the
  centre of the player's side, or brings his sword down on the front
  column. The attacks and their timings are the game's; ProtoMan's pacing is
  the average of the game's counter, Colonel's a placeholder.

- The results: after the last deletion the RESULT window slides in with the
  clear time and the busting level in the game's digit font -- time base,
  hits taken and moves, from the game's own scoring -- or the LOSER window
  when the player is deleted; A or Start holds 0x14 frames and fades the
  screen.
- The custom gauge, as the game's counter: 0xd a frame, full at 0x4000, then
  the pause that precedes chip selection. The bar itself is not drawn: two
  passes over the disassembly found no display code that reads the value,
  so rather than invent a fill it stays invisible until that is understood.
- The chip selection window, opening after that pause: its tilemap
  (byte_86E625C, bank 9) and tiles (dword_86E1D38, found by rendering every
  data blob against the map after six targeted searches missed it: nothing
  names it, it is uploaded as part of the palette block it follows) are in
  assets/custom.bin; it slides in from the left at 0xc a frame, revealing
  its columns as they arrive and blanking them as they leave the way the
  game copies them from its staging buffer, holds the fight while it is up,
  and slides out on A over OK, clearing the gauge. The map is the game's
  template with its 27 dynamic rectangles (byte_8027B2C: chip name,
  picture, element row, two rows of five slots, OK, the stack column)
  patched blank as the game does before drawing into them. The cursor is
  the game's four-corner bracket (dword_86E55BC) at its slot and OK
  origins, blinking every 8 frames, walking the default slot ring with
  Start jumping to OK. The slots hold the first five of a thirty-chip
  deck shuffled by the game's secondary RNG (deck.rs), each with its icon
  and code letter; the card shows the highlighted chip's picture in its
  own palette; A adds a chip if it fits the name-or-code rule, B undoes,
  and A on OK takes the picks out of the deck as the hand. Chip records,
  icons, pictures and palettes for thirteen chips are in assets/chips.bin
  (tools/chip_export.py). Not yet: the chip name, element and damage on
  the card, and using the hand in the fight.

Where a value is not yet taken from the disassembly -- Colonel's pacing,
some effect timings -- the code says so at the point of use.

Not started: sound. The game's effects go through Nintendo's m4a driver
(PlaySoundEffect queues m4a_SongNumStart; sound_MusicTable in data/dat37.s
maps an id to a song header with a voice table and a track stream). The
buster and deletion sounds are short sequences on synthesised voices, the
hit and Gunner impact are PCM samples with a 16-byte header; playing them
faithfully means a small m4a sequencer over agb's DMG channels and mixer.

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
