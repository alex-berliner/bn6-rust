#!/bin/bash
# Drive the ROM in mGBA on a virtual display and capture PNGs, so changes can
# be checked without a monitor.
#
#   tools/capture.sh shot  <rom> <out.png> [keys...]
#   tools/capture.sh burst <rom> <outdir> <count> [keys...]
#
# `keys` are xdotool key names sent once the emulator is up, in order, with a
# short settle between each. mGBA's defaults map the GBA buttons to
# A=x, B=z, L=a, R=s, Start=Return, Select=BackSpace, d-pad=arrow keys.
#
#   tools/capture.sh shot target/thumbv4t-none-eabi/debug/bn /tmp/a.png z Right
#
# Requires xvfb, xdotool, ffmpeg and mgba-qt. Note that `xdotool key --window`
# does not reach mGBA; the window has to be activated first, which is why this
# script exists rather than a one-liner.
set -u

MODE="${1:?usage: capture.sh shot|burst ...}"
ROM="${2:?rom path}"
DEST="${3:?output}"
shift 3

COUNT=1
if [ "$MODE" = burst ]; then
    COUNT="${1:?burst needs a count}"
    shift
fi

# A display number unlikely to collide with a real session or a parallel run.
DISP=":$((80 + RANDOM % 15))"
export DISPLAY="$DISP"

Xvfb "$DISP" -screen 0 320x260x24 >/dev/null 2>&1 &
XVFB=$!
cleanup() {
    kill "${MGBA:-}" 2>/dev/null
    kill "$XVFB" 2>/dev/null
    wait "${MGBA:-}" 2>/dev/null
    wait "$XVFB" 2>/dev/null
}
trap cleanup EXIT
sleep 1

mgba-qt "$ROM" >/dev/null 2>&1 &
MGBA=$!
sleep 5

WID=$(xdotool search --name mGBA | tail -1)
xdotool windowactivate --sync "$WID" 2>/dev/null

for key in "$@"; do
    xdotool keydown "$key"
    sleep 0.05
    xdotool keyup "$key"
    sleep 0.5
done

grab() {
    xwd -root -display "$DISP" -silent > "$1.xwd" 2>/dev/null
    ffmpeg -y -loglevel error -i "$1.xwd" "$1" 2>/dev/null
    rm -f "$1.xwd"
}

if [ "$MODE" = shot ]; then
    grab "$DEST"
    echo "wrote $DEST"
else
    mkdir -p "$DEST"
    for i in $(seq -w 1 "$COUNT"); do
        grab "$DEST/f$i.png"
    done
    echo "wrote $COUNT frames to $DEST"
fi
