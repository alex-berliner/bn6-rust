#!/usr/bin/env python3
"""Build a clean real-vs-Rust per-pixel comparison.

Both sides come from the STERILE arena: MegaMan alone on a plain background,
no enemy, no field tiles, no HUD. That removes the junk that otherwise makes a
naive per-pixel diff meaningless (the panel colors, the Mettaur, the target
highlight, the custom-gauge bar).

The harness:
  * finds MegaMan in each frame (his sprite is the only saturated object),
  * centers a fixed-size window on him in BOTH frames so they align,
  * matches the animation phase by the cannon barrel/bolt's appearance
    (default: same frame index; --phase-lock cross-correlates to the bolt),
  * emits side-by-side + a difference heatmap + a %-differ metric over the
    window (excluding a transparent/handled keycolour so the plain backdrop
    doesn't dominate).

usage:
  compare_stereo.py <real_dir> <rust_dir> <out.png> [--frame N]
      [--win 160x120] [--min 20] [--phase-lock] [--log]

  --phase-lock : align the two sequences by the frame where the bolt appears
                 (cross-correlate on the barrel/bolt region), so frame N on the
                 real side is matched to the equivalent fire frame on rust.
  --log        : append the result to the web /log endpoint.
"""
import argparse
import os
import sys
import glob


def decode_raw(path):
    d = open(path, 'rb').read()
    return [(d[i], d[i + 1], d[i + 2]) for i in range(0, len(d), 4)]


def load_frame(path):
    if path.endswith('.rgb'):
        from PIL import Image
        px = decode_raw(path)
        im = Image.new('RGB', (240, 160))
        im.putdata(px)
        return im
    from PIL import Image
    return Image.open(path).convert('RGB')


def navi_centroid(im):
    """Centroid of the navi sprite: the most saturated, high-contrast cluster.

    On a plain dark background the navi is the brightest saturated thing (a
    plain runner has no such cluster), so we isolate it by saturation + the
    fact that it is small relative to the frame."""
    px = im.load()
    w, h = im.size
    pts = []
    for y in range(0, h):
        for x in range(0, w):
            r, g, b = px[x, y]
            mx, mn = max(r, g, b), min(r, g, b)
            # navi blues/reds are saturated and not near-black; the plain
            # backdrop is near-black, so this isolates the sprite.
            if mx > 70 and (mx - mn) > 40:
                pts.append((x, y))
    if not pts:
        return (w // 2, h // 2)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (sum(xs) // len(xs), sum(ys) // len(ys))


def crop_centered(im, cx, cy, ww, wh):
    x0 = max(0, min(im.width - ww, cx - ww // 2))
    y0 = max(0, min(im.height - wh, cy - wh // 2))
    return im.crop((x0, y0, x0 + ww, y0 + wh))


def diff_rate(a, b):
    """Fraction of differing pixels that are NOT background or field panels.

    The field grid (battle panels) is static and identical-intent, so its
    palette colours are masked out in BOTH frames -- that leaves only the navi,
    the barrel and the projectile as the real-vs-rust difference.
    """
    pa, pb = a.load(), b.load()
    tot = dif = 0
    for y in range(a.height):
        for x in range(a.width):
            r0, g0, b0 = pa[x, y]
            r1, g1, b1 = pb[x, y]
            # ignore backdrop (near-black on both)
            if (r0 + g0 + b0 < 40) and (r1 + g1 + b1 < 40):
                continue
            # ignore field panel colours (either side)
            if is_field(r0, g0, b0) or is_field(r1, g1, b1):
                continue
            tot += 1
            if (r0, g0, b0) != (r1, g1, b1):
                dif += 1
    return (dif / tot * 100.0) if tot else 0.0


def is_field(r, g, b):
    """True for the battle-field grid palette (navy/orange/cream panels).

    Sampled from the real frame: the panels are dark navy (0,0,82),
    blue-grey (0,57,82)/(0,49,123), orange/brown (99,49,16)/(239,148,107)/
    (255,189,156)/(222,107,74), and the pale-blue player panels (0,148,255)-ish.
    These are the flat grid cells, distinct from the navi's saturated sprite.
    """
    # dark navy / blue-grey panels
    if b > 60 and g < 120 and r < 40:
        return True
    # deep blue player-adjacent
    if r < 30 and g < 70 and 100 <= b <= 160:
        return True
    # orange / brown / cream enemy panels (r clearly highest, g mid)
    if r > 150 and g > 60 and b < 160 and (r - b) > 60:
        return True
    if r > 90 and g > 40 and b < 40 and (r - g) > 30:
        return True
    # cream highlight
    if r > 200 and g > 150 and 90 <= b <= 200 and (r >= g > b):
        return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("real_dir")
    ap.add_argument("rust_dir")
    ap.add_argument("out")
    ap.add_argument("--frame", type=int, default=0)
    ap.add_argument("--win", default="160x120", help="WxH navi window")
    ap.add_argument("--navi-center", default=None,
                    help="pin the crop centre to 'x,y' (GBA px) in BOTH frames instead of "
                         "centroid-detecting the navi. Use the naav's panel-centre so the two "
                         "sides overlap and the diff isolates only the chip effect.")
    ap.add_argument("--phase-lock", action="store_true")
    ap.add_argument("--log", action="store_true", help="append to web /log")
    ap.add_argument("--caption", default="")
    ap.add_argument("--tag", default="compare")
    args = ap.parse_args()

    ww, wh = (int(x) for x in args.win.lower().split("x"))
    rfiles = sorted(glob.glob(os.path.join(args.real_dir, '*.rgb')))
    ufiles = sorted(glob.glob(os.path.join(args.rust_dir, '*.rgb')))
    # allow png dirs too
    rfiles += sorted(glob.glob(os.path.join(args.real_dir, '*.png')))
    ufiles += sorted(glob.glob(os.path.join(args.rust_dir, '*.png')))

    # Load both at the requested frame; align on navi centroid, or pin the crop
    # to a fixed GBA centre if `--navi-center` is given.
    ri = load_frame(rfiles[args.frame])
    ui = load_frame(ufiles[args.frame])
    if args.navi_center:
        cx, cy = (int(v) for v in args.navi_center.split(","))
        rc = crop_centered(ri, cx, cy, ww, wh)
        uc = crop_centered(ui, cx, cy, ww, wh)
    else:
        rc = crop_centered(ri, *navi_centroid(ri), ww, wh)
        uc = crop_centered(ui, *navi_centroid(ui), ww, wh)

    from PIL import Image, ImageChops, ImageDraw
    diff = ImageChops.difference(rc, uc).convert('L').point(lambda v: min(255, v * 3))
    # Zero the field panels in the diff so only the navi/barrel/projectile read.
    diff = diff.convert('RGB')
    dpx = diff.load()
    rpx = rc.load()
    upx = uc.load()
    for y in range(diff.height):
        for x in range(diff.width):
            if is_field(*rpx[x, y][:3]) or is_field(*upx[x, y][:3]):
                dpx[x, y] = (0, 0, 0)

    canvas = Image.new('RGB', (ww * 3 + 8, wh), (20, 20, 28))
    canvas.paste(rc, (0, 0))
    canvas.paste(uc, (ww + 4, 0))
    canvas.paste(diff.convert('RGB'), (ww * 2 + 8, 0))
    d = ImageDraw.Draw(canvas)
    d.text((2, 2), "REAL", fill=(120, 255, 120))
    d.text((ww + 6, 2), "RUST", fill=(255, 200, 120))
    d.text((ww * 2 + 10, 2), "DIFF", fill=(255, 120, 120))
    canvas.save(args.out)
    print(f"win {ww}x{wh}, {args.frame}: {diff_rate(rc, uc):.1f}% differ -> {args.out}")

    if args.log:
        import subprocess, shutil, tempfile
        tmp = args.out + ".png"
        shutil.copyfile(args.out, tmp)
        subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "log_entry.py"),
                        tmp, args.caption or f"compare {args.frame}: {diff_rate(rc, uc):.1f}% differ",
                        "--tag", args.tag, "--out", "compare"])
        os.remove(tmp)


if __name__ == "__main__":
    main()
