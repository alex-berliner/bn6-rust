#!/usr/bin/env python3
"""Produce a differential mask over frames, showing where two captures differ.

The ultimate goal: two programs (the real ROM and the Rust reimplementation)
render the *same* frame, so the diff mask is a single solid colour (every pixel
identical). This tool renders the mask and reports how far from solid it is.

usage:
  diffmask.py <real.rgb|png> <rust.rgb|png> <out.png> [--align dx,dy] [--solid 0,0,0]
                                                   [--frames START..END[,START..END,...]]

The mask is:
  * solid green  where the pixels are exactly identical,
  * the diff colour (red) where they differ.
"--align" shifts the rust frame by (dx,dy) before comparing, to lock the two
sprites onto the same pixel grid. "--solid" picks the identical colour.
"--frames" restricts the comparison to one or more inclusive frame ranges
(0-based, capture index within the directory); without it, only the first
sorted frame is compared. Multiple ranges are comma-separated. Each range
writes a separate <out_prefix>.png when --frames is given.
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


def parse_frames(spec):
    """Parse "START..END[,START..END,...]" into [(s, e), ...] inclusive."""
    if not spec:
        return []
    out = []
    for tok in spec.split(","):
        if ".." not in tok:
            raise SystemExit("--frames token %r: want START..END" % tok)
        s, e = tok.split("..", 1)
        s, e = int(s), int(e)
        if s < 0 or e < s:
            raise SystemExit("--frames token %r: START..END with START>=0 and END>=START" % tok)
        out.append((s, e))
    return out


def diff_one(ra, rb, dx, dy, solid, difcol):
    pa = ra.load()
    pb = rb.load()
    w = min(ra.width, rb.width)
    h = min(ra.height, rb.height)
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
    return out, nd, tot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("real")
    ap.add_argument("rust")
    ap.add_argument("out")
    ap.add_argument("--align", default="0,0", help="shift rust by dx,dy")
    ap.add_argument("--solid", default="0,255,0", help="the identical-colour (r,g,b)")
    ap.add_argument("--diff", default="255,0,0", help="the differing-colour (r,g,b)")
    ap.add_argument("--frames", default="",
                    help="inclusive frame ranges, comma-separated (e.g. "
                         "'170..200,195..250'); when given, requires real/rust "
                         "to be directories and writes one PNG per range")
    args = ap.parse_args()

    from PIL import Image  # loaded here so --help doesn't need PIL

    dx, dy = (int(v) for v in args.align.split(","))
    solid = tuple(int(v) for v in args.solid.split(","))
    difcol = tuple(int(v) for v in args.diff.split(","))

    ranges = parse_frames(args.frames)
    if ranges:
        if not (os.path.isdir(args.real) and os.path.isdir(args.rust)):
            raise SystemExit("--frames requires real and rust to be directories")
        af = sorted(glob.glob(os.path.join(args.real, '*.*')))
        bf = sorted(glob.glob(os.path.join(args.rust, '*.*')))
        if not af or not bf:
            raise SystemExit("--frames: empty directory (%s or %s)" %
                             (args.real, args.rust))
        base, ext = os.path.splitext(args.out)
        if ext == "":
            base, ext = args.out, ".png"
        total_nd = 0
        total_tot = 0
        per_range = []
        for (s, e) in ranges:
            worst = -1
            worst_k = None
            for k in range(s, e + 1):
                if k >= len(af) or k >= len(bf):
                    raise SystemExit(
                        "--frames %d..%d: out of range (real has %d, rust has %d)" %
                        (s, e, len(af), len(bf)))
                ra = load_frame(af[k])
                rb = load_frame(bf[k])
                img, nd, tot = diff_one(ra, rb, dx, dy, solid, difcol)
                total_nd += nd
                total_tot += tot
                if nd > worst:
                    worst, worst_k = nd, k
                if k == s:
                    out_path = "%s_%d_%d%s" % (base, s, e, ext)
                    img.save(out_path)
                    first_nd = nd
            per_range.append((s, e, first_nd, worst, worst_k))
            print(f"diffmask range {s}..{e}: first frame k={s} {first_nd}/{tot} differing "
                  f"({100 * first_nd / max(1, tot):.2f}%); worst k={worst_k} {worst}/{tot} "
                  f"({100 * worst / max(1, tot):.2f}%) -> {out_path}")
        print(f"diffmask TOTAL over {len(ranges)} range(s): {total_nd}/{total_tot} differing "
              f"({100 * total_nd / max(1, total_tot):.2f}%)")
    else:
        a = args.real
        b = args.rust
        if os.path.isdir(a) and os.path.isdir(b):
            af = sorted(glob.glob(os.path.join(a, '*.*')))
            bf = sorted(glob.glob(os.path.join(b, '*.*')))
            if not af or not bf:
                raise SystemExit("diffmask: empty directory (%s or %s)" % (a, b))
            a = af[0]; b = bf[0]
        ra = load_frame(a)
        rb = load_frame(b)
        img, nd, tot = diff_one(ra, rb, dx, dy, solid, difcol)
        img.save(args.out)
        print(f"diffmask {a} vs {b} (shift {dx},{dy}): {nd}/{tot} differing "
              f"({100 * nd / max(1, tot):.2f}%) -> {args.out}")


if __name__ == "__main__":
    main()
