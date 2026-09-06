#!/usr/bin/env python3
"""Produce a differential mask over frames, showing where two captures differ.

The ultimate goal: two programs (the real ROM and the Rust reimplementation)
render the *same* frame, so the diff mask is a single solid colour (every pixel
identical). This tool renders the mask and reports how far from solid it is.

usage:
  diffmask.py <real.rgb|png> <rust.rgb|png> <out.png> [--align dx,dy] [--solid 0,0,0]

The mask is:
  * solid green  where the pixels are exactly identical,
  * the diff colour (red) where they differ.
"--align" shifts the rust frame by (dx,dy) before comparing, to lock the two
sprites onto the same pixel grid. "--solid" picks the identical colour.
"""
import argparse
import sys
import os
import glob


def decode_raw(path):
    d = open(path, 'rb').read()
    return [(d[i], d[i + 1], d[i + 2]) for i in range(0, len(d), 4)]


def load_frame(path):
    from PIL import Image
    if path.endswith('.rgb'):
        px = decode_raw(path)
        im = Image.new('RGB', (240, 160))
        im.putdata(px)
        return im
    return Image.open(path).convert('RGB')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("real")
    ap.add_argument("rust")
    ap.add_argument("out")
    ap.add_argument("--align", default="0,0", help="shift rust by dx,dy")
    ap.add_argument("--solid", default="0,255,0", help="the identical-colour (r,g,b)")
    ap.add_argument("--diff", default="255,0,0", help="the differing-colour (r,g,b)")
    args = ap.parse_args()

    dx, dy = (int(v) for v in args.align.split(","))
    solid = tuple(int(v) for v in args.solid.split(","))
    difcol = tuple(int(v) for v in args.diff.split(","))

    a = args.real
    b = args.rust
    if os.path.isdir(a) and os.path.isdir(b):
        af = sorted(glob.glob(os.path.join(a, '*.*')))
        bf = sorted(glob.glob(os.path.join(b, '*.*')))
        a = af[0]; b = bf[0]

    ra = load_frame(a)
    rb = load_frame(b)
    pa = ra.load()
    pb = rb.load()
    w = min(ra.width, rb.width)
    h = min(ra.height, rb.height)

    from PIL import Image
    out = Image.new('RGB', (w, h), solid)
    po = out.load()
    nd = 0
    tot = 0
    for y in range(h):
        for x in range(w):
            tot += 1
            bx, by = x - dx, y - dy
            if 0 <= bx < rb.width and 0 <= by < rb.height:
                r0 = pa[x, y][:3]
                r1 = pb[bx, by][:3]
            else:
                r1 = (0, 0, 0)
            if r0 == r1:
                po[x, y] = solid
            else:
                po[x, y] = difcol
                nd += 1
    out.save(args.out)
    print(f"diffmask {a} vs {b} (shift {dx},{dy}): {nd}/{tot} differing "
          f"({100 * nd / max(1, tot):.2f}%) -> {args.out}")


if __name__ == "__main__":
    main()
