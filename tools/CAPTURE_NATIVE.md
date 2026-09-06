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
