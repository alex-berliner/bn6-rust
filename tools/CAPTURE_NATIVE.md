# Native frame capture (mGBA core)

`mgba_capture.sh` captures the exact GBA framebuffer frame-by-frame by
running the mGBA **core library** headlessly, instead of driving the mGBA Qt
window on a virtual display and screen-scraping it (the old `capture.sh`).

Why this is better:
- Every frame is the real `240x160` GBA framebuffer, straight from the core's
  renderer output buffer — no window offsets, letterboxing, menu bar, or
  X-server scaling to un-map.
- Captures are in lock-step with the emulator: one file per rendered frame,
  deterministic, with no screen-scrape timing races.
- No display server at all (no Xvfb, xdotool, ffmpeg).

## Dependency

The mGBA development library provides the core headers and the shared library
(`libmgba.so`). On Ubuntu:

```
sudo apt-get install libmgba-dev
```

`mgba_capture.sh` will compile `mgba_capture.c` against it on first run.

## Usage

```
tools/mgba_capture.sh [<rom.gba>] <outdir> <count> [--press-A <ticks>] [--build <features...>]
```

- `--build demo-cannon,demo-auto` builds the ROM from cargo features (a
  `,`-separated list) before capturing. When set, no `<rom.gba>` positional is
  needed.
- `--press-A <ticks>` holds the A button for `<ticks>` frames beginning around
  frame 60. The `demo-auto` feature fires on a timer instead, so this is
  optional.
- Raw frames land in `<outdir>/frame.#####.rgb`; `mgba_frames.py` decodes them
  to PNGs in `<outdir>/png/`. Use `--no-decode` to keep only the `.rgb` files.

Examples:

```
# Build the cannon auto-fire ROM and capture 300 frames to find the barrel.
tools/mgba_capture.sh /tmp/cap 300 --build demo-cannon,demo-auto
```

## Files

- `mgba_capture.c` — links `libmgba`, loads the ROM, sets a local framebuffer,
  steps `core->runFrame`, and writes raw 32-bit native pixels per frame. Optional
  `--press-A` drives key input via `core->setKeys`.
- `mgba_frames.py` — decodes raw frames (`240*160*4` bytes, native `0x00RRGGBB`
  little-endian) to RGB PNGs.
- `mgba_capture.sh` — wrapper that builds, captures, and decodes.

## Future work: a sterile single-combatant battle

For clean chip-animation captures against the **real** ROM, the ideal test
environment is MegaMan in battle *by himself*: no enemy virus wandering in and
no win/lose conclusion ending the fight, so a capture run can watch a chip's
full pose and shot without the scene changing or the battle resolving.

The blocker is that the battle ends as soon as the win condition is met
(`battle_isBattleOver`, asm00_1.s:15005) — either all enemies are deleted
(win) or MegaMan is deleted (lose). To keep MegaMan alone and not conclude,
one of these patches is needed (applied via a cheat file to `core->cheatDevice`
+ `mCheatParseFile`, or with the harness's `--poke` writing battle RAM):

1. **Suppress the conclusion**: patch the win/lose check so it never returns
   "over" while this test battle runs (e.g. force the battle-over flag to 0, or
   keep one fake, undeletable enemy present so the all-deleted condition is
   never met).
2. **Hide/immunise the enemy**: keep it in the list so `isBattleOver` sees a
   survivor, but clear its occupancy / mark it non-targetable and non-rendered,
   and zero its AI so it neither moves nor attacks (a "ghost" Mettaur).

The battle-object list and the enemy's HP/occupancy/AI live in the battle RAM
that the decomp labels (`byte_20349C0` hand block, the enemy `BattleObject`s,
and the AI state), so the harness's `--poke`/`--peek` (which read/write 16-bit
bus memory) plus the mGBA cheat device are the two ways to apply it. Once a
sterile battle loads, chip animations can be captured frame-by-frame with no
enemy interference and no auto-conclusion.

## Chip verification workflow (how to land each chip faithfully)

The goal is to replicate a chip so its rendered animation matches the real
MMBN6F ROM frame-for-frame. Do it one chip at a time; verify each before moving
on. Never "it looks close" — the per-pixel diff is the acceptance test.

### 0. Prerequisites (already built)
- `tools/patch_sterile.py` -> `/tmp/bn6f_sterile.gba` (battle_isBattleOver always
  "not over", so the fight never concludes).
- `tools/capture_real_chip.sh <chipid_hex> <outdir> [count]` -> captures the
  real chip's animation in the sterile arena (loads the save state, deletes the
  enemy via `--cheat HP=0`, pokes the hand chip at `0x20349c2`, unpauses, fires).
- `tools/compare_stereo.py <real_dir> <rust_dir> <out>` -> navi-aligned
  REAL|RUST|DIFF with a field-masked %-differ metric.

### 1. Capture the real chip
```
/tmp/capture_real_chip.sh <chipid_hex> /tmp/real_<chip> 200
```
Decode to PNGs, then find the frame where the chip's effect fires and study it:
the projectile size/colour, the barrel/pose, the number of frames. This is the
ground truth. Cross-check the sprite in the disassembly (`byte_82F*` sprites,
`SpritePointersList` indices, the attack family's shot/spawn routine) so the
Rust version uses the *same* asset rather than an approximation.

### 2. Capture the Rust version
```
tools/mgba_capture.sh /tmp/rust_<chip> 200 --build demo-<chip>,demo-sterile,demo-auto
```

### 3. Compare at the matching fire frame
```
python3 tools/compare_stereo.py /tmp/real_<chip> /tmp/rust_<chip>/png /tmp/cmp_<chip>.png \
  --frame <fire_frame> --win 150x110
```
The DIFF panel must be near-empty (only the navi + barrel + projectile show).
Iterate on the Rust until the %-differ is low; a large residual means the
sprite/timing/position is wrong.

### 4. Fix the Rust chip (engine)
- Projectile chips: use the *correct* effect sprite (e.g. Cannon's big orb, not
  the buster bolt); align the barrel to the hand (see the cannon barrel work).
- Slash chips: the crescent illusion (Sword family) — spawn the type-4 illusion
  at the strike.
- Multi-hit chips: match the fan/timing (Vulcan), the arc (MiniBomb), the
  number of columns (WideSword/LongSword).
- Status chips: the heal/shield/invis visuals and durations.

### 5. Log the verified chip
```
tools/log_entry.py /tmp/cmp_<chip>.png "<chip>: real vs rust comparison" --tag <chip> --out compare
```
Then it shows up on /log.html for review.

### Chip id (battle-hand) map for step 1
Cannon=0x01, HiCannon=0x02, AirShot=0x04, Vulcan=0x05, MiniBomb=0x36,
Sword=0x47, WideSword=0x48, LongSword=0x49, Recov10=0x9a, Recov30=0x9b,
Invisibl=0xb1, Barrier=0xb2, AreaGrab=0xa3.
