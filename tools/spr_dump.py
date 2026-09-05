"""Render frames from a bn6f .spr file to a PNG contact sheet.

usage: python3 spr_dump.py <file.spr|.lz77> <out.png> [--anim N] [--pal N] [--scale N]
"""

import argparse
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spr import Sprite, load_sprite_bytes, render_frame


def sheet(spr, anims, pal_index, scale, cell_bg=(24, 24, 32)):
    rendered = []
    for a in anims:
        for f in spr.frames(a):
            px = render_frame(spr, f, pal_index)
            rendered.append((a, f, px))

    if not rendered:
        raise SystemExit("no frames")

    xs = [p[0] for _, _, px in rendered for p in px]
    ys = [p[1] for _, _, px in rendered for p in px]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    cw, ch = maxx - minx + 1, maxy - miny + 1

    cols = min(8, len(rendered))
    rows = (len(rendered) + cols - 1) // cols
    img = Image.new("RGB", (cols * (cw + 2), rows * (ch + 2)), cell_bg)

    for i, (_, _, px) in enumerate(rendered):
        ox = (i % cols) * (cw + 2) + 1 - minx
        oy = (i // cols) * (ch + 2) + 1 - miny
        for (x, y), c in px.items():
            img.putpixel((ox + x, oy + y), c)

    if scale != 1:
        img = img.resize((img.width * scale, img.height * scale), Image.NEAREST)
    return img, len(rendered)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spr")
    ap.add_argument("out")
    ap.add_argument("--anim", type=int, default=None)
    ap.add_argument("--pal", type=int, default=0)
    ap.add_argument("--scale", type=int, default=3)
    args = ap.parse_args()

    spr = Sprite(load_sprite_bytes(args.spr))
    anims = [args.anim] if args.anim is not None else range(len(spr.anim_offsets))
    img, n = sheet(spr, anims, args.pal, args.scale)
    img.save(args.out)
    print(f"{n} frames -> {args.out} ({img.width}x{img.height})")


if __name__ == "__main__":
    main()
