#!/bin/bash
# Capture a chip's real animation in the sterile arena.
# usage: capture_real_chip.sh <chipid_hex> <outdir> [count]
CHIP="$1"; OUT="$2"; COUNT="${3:-200}"
mkdir -p "$OUT"; rm -f "$OUT"/*.rgb
# Load sterile-patched ROM + save state, poke the hand chip, unpause + fire A.
/tmp/mgba_capture /tmp/bn6f_sterile.gba "$OUT" "$COUNT" \
  --loadstate /tmp/pausedwithcannon.state \
  --cheat 0x0203ab84:0x0000 --cheat 0x0203ab86:0x0000 \
  --cheat 0x020349c2:$CHIP \
  --script "Start@10,A@60,A@90,A@120" 2>&1 | grep -iE "loaded|fail"
echo "captured $COUNT frames for chip id 0x$CHIP -> $OUT"
