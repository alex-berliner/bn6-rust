#!/usr/bin/env python3
"""Build a side-by-side GIF of one chip, real ROM against this build.

usage: python3 gif_compare.py <chip_id_hex> <demo-feature> <out.gif> [--frames N]

Runs the same two captures chip_compare.py does and lays them side by side,
the real ROM left and this build right, with a one-pixel divider. The two are
aligned the way chip_compare aligns them: the real attack starts at REAL_START
and the sterile demo's auto-fire at frame 123.

Needs /tmp/mgba_capture and the real ROM, which are never committed.
"""

import argparse
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chip_compare as cc

#: The GBA runs at just under 60 frames a second; GIF delays are centiseconds,
#: so every frame at 2cs is about half speed, which reads better than real time.
DELAY_CS = 2
SCALE = 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("chip")
    ap.add_argument("feature")
    ap.add_argument("out")
    ap.add_argument("--frames", type=int, default=60)
    ap.add_argument("--rust-start", type=int, default=123)
    ap.add_argument("--no-build", action="store_true")
    args = ap.parse_args()

    real = "/tmp/gif_real_" + args.chip
    rust = "/tmp/gif_rust_" + args.feature
    cc.capture_real(args.chip, real, cc.REAL_START + args.frames + 5)
    if not args.no_build:
        cc.build_and_capture_rust(args.feature, rust, args.rust_start + args.frames + 5)

    w, h = 240, 160
    frames = []
    for i in range(args.frames):
        a = cc.frame(real, cc.REAL_START + i)
        b = cc.frame(rust, args.rust_start + i)
        sheet = Image.new("RGB", (w * 2 + 2, h), (60, 60, 60))
        sheet.paste(a, (0, 0))
        sheet.paste(b, (w + 2, 0))
        frames.append(sheet.resize((sheet.width * SCALE, h * SCALE), Image.NEAREST))

    frames[0].save(
        args.out,
        save_all=True,
        append_images=frames[1:],
        duration=DELAY_CS * 10,
        loop=0,
        optimize=True,
    )
    print(f"{args.out}: {len(frames)} frames, {os.path.getsize(args.out)} bytes")


if __name__ == "__main__":
    main()
