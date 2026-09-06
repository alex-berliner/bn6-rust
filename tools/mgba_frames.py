#!/usr/bin/env python3
"""Decode raw frames written by tools/mgba_capture.c into PNGs.

Each <name>.rgb is GW*GH 32-bit native GBA pixels, straight from the core's
renderer output buffer (color_t). color_t is unpacked as 4 little-endian bytes;
mGBA's default 32-bit native is 0x00RRGGBB (bytes B,G,R,0). We normalise to
RGB for inspection.

usage: mgba_frames.py <outdir> [--out <pngdir>] [--cols <n>] [--at <i>]
"""
import sys, os, glob, struct
from PIL import Image

GW, GH = 240, 160

def decode(path):
    data = open(path, 'rb').read()
    px = []
    for i in range(0, len(data), 4):
        # mGBA 32-bit native is 0x00RRGGBB (M_COLOR_RED=0xFF, GREEN=0xFF00,
        # BLUE=0xFF0000 -> little-endian memory order R,G,B,x).
        r = data[i]; g = data[i+1]; b = data[i+2]  # a = data[i+3]
        px.append((r, g, b))
    im = Image.new('RGB', (GW, GH))
    im.putdata(px)
    return im

def main():
    args = sys.argv[1:]
    src = args[0]
    dst = None
    if '--out' in args:
        dst = args[args.index('--out') + 1]
    cols = 6
    if '--cols' in args:
        cols = int(args[args.index('--cols') + 1])
    only = None
    if '--at' in args:
        only = int(args[args.index('--at') + 1])

    os.makedirs(dst, exist_ok=True) if dst else None
    files = sorted(glob.glob(os.path.join(src, '*.rgb')))
    if only is not None:
        files = [files[only]]
    for f in files:
        im = decode(f)
        base = os.path.basename(f).replace('.rgb', '')
        if dst:
            im.save(os.path.join(dst, base + '.png'))
        else:
            im.save('/tmp/' + base + '.png')
    print(f"decoded {len(files)} frames")

if __name__ == '__main__':
    main()
