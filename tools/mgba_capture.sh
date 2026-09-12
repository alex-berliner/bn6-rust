#!/bin/bash
# Native GBA frame capture for the bn project.
#
# Drives mGBA's core library directly (tools/mgba_capture.c) instead of the
# Qt window, so every frame is the exact 240x160 GBA framebuffer, captured in
# lock-step with the emulator, with no X server or window offsets. Optionally
# builds the ROM first, and decodes the raw frames to PNGs.
#
# usage: mgba_capture.sh [<rom.gba>] <outdir> <count> [--press-A <ticks>] [--build <features...>]
#
#   --build  build the ROM from cargo features before capturing (comma/space
#            list). When set, no <rom.gba> positional is needed. The project
#            has no non-default features any more (AUDIT pair 17 prune
#            ticket retired the last of the demo-* ones) -- pass "" for the
#            plain release build, or a feature a future agent adds.
#   --press-A <ticks>  hold A for <ticks> frames starting ~frame 60
#   --no-decode  leave raw .rgb frames instead of decoding to .png
#
# Requires the mGBA development library, which provides the core headers:
#   Ubuntu: sudo apt-get install libmgba-dev
set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"

ROM=""
OUTDIR=""
COUNT=""
BUILD=""
PRESS_A=""
DECODE=1
POS=()
while [ $# -gt 0 ]; do
  case "$1" in
    --build) BUILD="$2"; shift 2 ;;
    --press-A) PRESS_A="--press-A $2"; shift 2 ;;
    --no-decode) DECODE=0; shift ;;
    --) shift; break ;;
    -*) echo "unknown option $1" >&2; exit 2 ;;
    *) POS+=("$1"); shift ;;
  esac
done

# Positional args: [<rom.gba>] <outdir> <count>. `--build` may supply the ROM,
# so the optional ROM is only the first positional when 3 positionals remain.
if [ ${#POS[@]} -ge 3 ]; then
  ROM="${POS[0]}"; OUTDIR="${POS[1]}"; COUNT="${POS[2]}"
elif [ ${#POS[@]} -eq 2 ]; then
  OUTDIR="${POS[0]}"; COUNT="${POS[1]}"
else
  echo "usage: mgba_capture.sh [<rom.gba>] <outdir> <count> [--build <feat>] [--press-A <ticks>]" >&2
  exit 2
fi

if [ -z "$ROM" ] && [ -z "$BUILD" ]; then
  echo "need a <rom.gba> or --build to supply one" >&2
  exit 2
fi

# Build the ROM if requested.
if [ -n "$BUILD" ]; then
  echo "==> building features: $BUILD"
  ( cd "$ROOT" && cargo build --release --features "$BUILD" )
  # Where cargo actually built, not where we assume: a CARGO_TARGET_DIR set in
  # the environment would otherwise leave this packing a stale ELF from $ROOT.
  TARGET_DIR="$( cd "$ROOT" && cargo metadata --format-version 1 --no-deps \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["target_directory"])' )"
  ROM_SRC="$TARGET_DIR/thumbv4t-none-eabi/release/bn"
  ROM_TMP="$(mktemp --suffix=.gba)"
  python3 "$ROOT/tools/gbafix.py" "$ROM_SRC" "$ROM_TMP"
  ROM="$ROM_TMP"
  echo "==> built $ROM"
fi

# Build the helper if needed.
if [ ! -x /tmp/mgba_capture ] || [ "$HERE/mgba_capture.c" -nt /tmp/mgba_capture ]; then
  echo "==> building mgba_capture"
  gcc "$HERE/mgba_capture.c" -o /tmp/mgba_capture -I/usr/include -lmgba -lm
fi

echo "==> capturing $COUNT frames from $ROM -> $OUTDIR"
mkdir -p "$OUTDIR"
rm -f "$OUTDIR"/frame.*.rgb 2>/dev/null || true
/tmp/mgba_capture "$ROM" "$OUTDIR" "$COUNT" $PRESS_A

if [ "$DECODE" = 1 ]; then
  echo "==> decoding to PNG"
  python3 "$HERE/mgba_frames.py" "$OUTDIR" --out "$OUTDIR/png"
  echo "==> done: $OUTDIR/png/frame.*.png"
else
  echo "==> done: $OUTDIR/frame.*.rgb"
fi
