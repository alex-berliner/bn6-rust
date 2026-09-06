#!/usr/bin/env python3
"""Export a trimmed frame-range of a bn6f .spr into a BNSP asset.

usage: spr_export_range.py <file.spr> <out.bin> --anim N --frames A B... </spr>

Keeps a sprite's animation but only the listed frame indexes (0-based within that
animation), so e.g. the cannon barrel can be cut to just its charge frames and
hold on the last one (the caller holds the final frame).
"""
import argparse
import os
import sys
import struct

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spr import Sprite, load_sprite_bytes
from spr_export import build  # reuse the section builder


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--anim", type=int, default=0)
    ap.add_argument("--frames", type=int, nargs="+", required=True,
                    help="frame indexes (within anim) to keep, in order")
    args = ap.parse_args()

    spr = Sprite(load_sprite_bytes(args.input))
    src = spr.frames(args.anim)

    class Trimmed:
        """Present only the chosen frames as a single animation to build()."""
        def frames(self, anim):
            if anim != 0:
                return []
            return [src[i] for i in args.frames]

        def tiles(self, frame):
            return spr.tiles(frame)

        def oam_entries(self, frame):
            return spr.oam_entries(frame)

        def palette(self, frame, index):
            return spr.palette(frame, index)

    trimmed = Trimmed()
    data, counts = build(trimmed, [0])
    with open(args.output, "wb") as f:
        f.write(data)
    g, p, a, fr, o = counts
    print(f"{args.output}: {len(data)} bytes  "
          f"({g} gfx, {p} pal, {a} anim, {fr} frames, {o} oam)")


if __name__ == "__main__":
    main()
