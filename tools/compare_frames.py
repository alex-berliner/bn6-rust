#!/usr/bin/env python3
"""Per-pixel compare a real-ROM frame against the Rust port's frame.

Both captures come from the sterile arena (MegaMan alone on a plain
background, no enemy, no field tiles) so they align on the same scene. This
renders side-by-side, a difference heatmap, and reports how many pixels differ.

usage:
  compare_frames.py <real.png|rgb> <rust.png|rgb> <out.png> [--crop X0 Y0 X1 Y1]
  compare_frames.py <realdir> <rustdir> <out> [--frame N]  (match by frame index)

For a .rgb (native capture) input, the frame is decoded from raw
240x160 GBA pixels. PNG inputs are used as-is. A --crop restricts the compare
to the navi/barrel region so the field letterboxing does not dominate.
"""
import argparse
import os
import sys
import glob


def decode_raw(path):
    d = open(path, 'rb').read()
    px = [(d[i], d[i + 1], d[i + 2]) for i in range(0, len(d), 4)]
    from PIL import Image
    im = Image.new('RGB', (240, 160))
    im.putdata(px)
    return im


def load(path):
    if path.endswith('.rgb'):
        return decode_raw(path)
    from PIL import Image
    return Image.open(path).convert('RGB')


def diff_pixel_count(a, b, box):
    ax, ay = a.load(), b.load()
    x0, y0, x1, y1 = box
    n = 0
    for y in range(y0, y1):
        for x in range(x0, x1):
            if ax[x, y] != ay[x, y]:
                n += 1
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("real")
    ap.add_argument("rust")
    ap.add_argument("out")
    ap.add_argument("--frame", type=int, default=None,
                    help="frame index to use when real/rust are directories")
    ap.add_argument("--crop", type=int, nargs=4, default=None,
                    help="X0 Y0 X1 Y1 region of interest")
    args = ap.parse_args()

    a = args.real
    b = args.rust
    if os.path.isdir(a) and os.path.isdir(b):
        af = sorted(glob.glob(os.path.join(a, '*.rgb'))) + sorted(glob.glob(os.path.join(a, '*.png')))
        bf = sorted(glob.glob(os.path.join(b, '*.rgb'))) + sorted(glob.glob(os.path.join(b, '*.png')))
        if args.frame is None:
            print("need --frame when comparing directories")
            return 2
        a = af[args.frame] if args.frame < len(af) else None
        b = bf[args.frame] if args.frame < len(bf) else None
        if not a or not b:
            print("frame %d missing" % args.frame)
            return 2

    from PIL import Image, ImageChops, ImageDraw
    ra = load(a)
    rb = load(b)
    box = args.crop or (0, 0, ra.width, ra.height)
    # Difference heatmap (amplified).
    diff = ImageChops.difference(ra, rb).convert('L').point(lambda v: min(255, v * 3))
    n = diff_pixel_count(ra.convert('RGB'), rb.convert('RGB'), box)
    total = (box[2] - box[0]) * (box[3] - box[1])

    # Compose: real | rust | diff.
    sw, sh = ra.width, ra.height
    canvas = Image.new('RGB', (sw * 3 + 8, sh), (20, 20, 28))
    canvas.paste(ra, (0, 0))
    canvas.paste(rb, (sw + 4, 0))
    canvas.paste(diff.convert('RGB'), (sw * 2 + 8, 0))
    d = ImageDraw.Draw(canvas)
    d.text((2, 2), "REAL", fill=(120, 255, 120))
    d.text((sw + 6, 2), "RUST", fill=(255, 200, 120))
    d.text((sw * 2 + 10, 2), "DIFF", fill=(255, 120, 120))
    canvas.save(args.out)
    print(f"compare: {a} vs {b}")
    print(f"  crop {box}: {n}/{total} pixels differ ({100 * n / max(1,total):.1f}%)")
    print(f"  wrote {args.out} ({canvas.width}x{canvas.height})")


if __name__ == "__main__":
    main()
