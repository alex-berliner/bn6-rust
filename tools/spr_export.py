"""Export a bn6f `.spr` file to the compact binary asset format the ROM embeds.

usage: python3 spr_export.py <file.spr|.lz77> <out.bin> [--anim N ...]

Graphics blobs are shared between frames in the source data, so they are
deduplicated here rather than emitted per frame.

Format (little-endian, byte-addressed; the reader makes no alignment
assumptions because unaligned word loads are a hazard on ARM7TDMI):

  0x00  magic "BNSP"
  0x04  u32 version
  0x08  u32 -> gfx    : u32 count, count * (u32 data_offset, u32 byte_len)
  0x0c  u32 -> palette: u32 count, count * 32 bytes (16 * u16 BGR555)
  0x10  u32 -> anim   : u32 count, count * (u16 first_frame, u16 frame_count)
  0x14  u32 -> frame  : u32 count, count * FrameRec
  0x18  u32 -> oam    : u32 count, count * OamRec

  FrameRec (10 bytes): u16 gfx, u16 pal, u16 oam_first, u16 oam_count,
                       u8 duration, u8 flags
  OamRec    (6 bytes): u16 tile, i8 x, i8 y, u8 size_shape, u8 flags

`size_shape` is `shape << 2 | size`, which is exactly how agb encodes its
`Size` enum. OamRec flags: bit0 h-flip, bit1 v-flip, bits 4-7 palette offset.
"""

import argparse
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spr import BASE, Sprite, load_sprite_bytes


def build(spr, anims, extra_palettes=0):
    gfx_blobs, gfx_ids = [], {}
    palettes, pal_ids = [], {}
    anim_recs, frame_recs, oam_recs = [], [], []

    for a in anims:
        frames = spr.frames(a)
        anim_recs.append((len(frame_recs), len(frames)))
        for f in frames:
            if f.gfx not in gfx_ids:
                gfx_ids[f.gfx] = len(gfx_blobs)
                gfx_blobs.append(bytes(spr.tiles(f)))
            # Palettes are keyed by blob *and* index; a frame uses index 0 here,
            # runtime palette swaps (hit flash, cross forms) pick others later.
            key = (f.pal, 0)
            if key not in pal_ids:
                pal_ids[key] = len(palettes)
                palettes.append(spr.palette(f, 0))
                # The palette block's length word covers only the first
                # palette, but the game indexes past it: the cannon barrel's
                # byte_80B8BD4 rows add 1 and 2 for HiCannon and M-Cannon.
                # Keep those consecutive after the frame's own so a runtime
                # palette add maps onto the asset's indices.
                for extra in range(1, extra_palettes + 1):
                    palettes.append(spr.palette(f, extra))

            entries = spr.oam_entries(f)
            first = len(oam_recs)
            for e in entries:
                flags = (1 if e.hflip else 0) | (2 if e.vflip else 0) | (e.pal_offset << 4)
                oam_recs.append((e.tile, e.x, e.y, (e.shape << 2) | e.size, flags))
            frame_recs.append(
                (gfx_ids[f.gfx], pal_ids[key], first, len(entries),
                 f.duration or 1, f.flags)
            )

    # Lay out sections. Each section is a u32 count followed by its records;
    # the gfx section additionally carries a data area after its table.
    out = bytearray()
    header = struct.pack("<4sIIIIII", b"BNSP", 1, 0, 0, 0, 0, 0)
    out += header

    def align(b):
        while len(b) % 4:
            b += b"\0"

    off_gfx = len(out)
    out += struct.pack("<I", len(gfx_blobs))
    table_at = len(out)
    out += b"\0" * (8 * len(gfx_blobs))
    data_offsets = []
    for blob in gfx_blobs:
        align(out)
        data_offsets.append((len(out), len(blob)))
        out += blob
    for i, (o, n) in enumerate(data_offsets):
        struct.pack_into("<II", out, table_at + i * 8, o, n)

    align(out)
    off_pal = len(out)
    out += struct.pack("<I", len(palettes))
    for p in palettes:
        out += struct.pack("<16H", *p)

    align(out)
    off_anim = len(out)
    out += struct.pack("<I", len(anim_recs))
    for first, count in anim_recs:
        out += struct.pack("<HH", first, count)

    align(out)
    off_frame = len(out)
    out += struct.pack("<I", len(frame_recs))
    for rec in frame_recs:
        out += struct.pack("<HHHHBB", *rec)

    align(out)
    off_oam = len(out)
    out += struct.pack("<I", len(oam_recs))
    for tile, x, y, size_shape, flags in oam_recs:
        out += struct.pack("<HbbBB", tile, x, y, size_shape, flags)

    struct.pack_into("<4sIIIIII", out, 0, b"BNSP", 1,
                     off_gfx, off_pal, off_anim, off_frame, off_oam)
    return bytes(out), (len(gfx_blobs), len(palettes), len(anim_recs),
                        len(frame_recs), len(oam_recs))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("output")
    ap.add_argument("--anim", type=int, nargs="*", default=None)
    ap.add_argument("--palettes", type=int, default=0,
                    help="extra consecutive palettes to keep after each frame's own")
    args = ap.parse_args()

    spr = Sprite(load_sprite_bytes(args.input))
    anims = args.anim if args.anim else list(range(len(spr.anim_offsets)))
    data, counts = build(spr, anims, args.palettes)
    with open(args.output, "wb") as f:
        f.write(data)
    g, p, a, fr, o = counts
    print(f"{args.output}: {len(data)} bytes  "
          f"({g} gfx blobs, {p} palettes, {a} anims, {fr} frames, {o} oam entries)")


if __name__ == "__main__":
    main()
