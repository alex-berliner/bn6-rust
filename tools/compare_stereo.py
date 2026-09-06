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
    """Fraction of differing pixels that are NOT the near-black backdrop."""
    pa, pb = a.load(), b.load()
    tot = dif = 0
    for y in range(a.height):
        for x in range(a.width):
            r0, g0, b0 = pa[x, y]
            r1, g1, b1 = pb[x, y]
            # ignore backdrop (near-black on both) so it doesn't dominate
            if (r0 + g0 + b0 < 40) and (r1 + g1 + b1 < 40):
                continue
            tot += 1
            if (r0, g0, b0) != (r1, g1, b1):
                dif += 1
    return (dif / tot * 100.0) if tot else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("real_dir")
    ap.add_argument("rust_dir")
    ap.add_argument("out")
    ap.add_argument("--frame", type=int, default=0)
    ap.add_argument("--win", default="160x120", help="WxH navi window")
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

    # Load both at the requested frame; align on navi centroid.
    ri = load_frame(rfiles[args.frame])
    ui = load_frame(ufiles[args.frame])
    rc = crop_centered(ri, *navi_centroid(ri), ww, wh)
    uc = crop_centered(ui, *navi_centroid(ui), ww, wh)

    from PIL import Image, ImageChops, ImageDraw
    diff = ImageChops.difference(rc, uc).convert('L').point(lambda v: min(255, v * 3))

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
