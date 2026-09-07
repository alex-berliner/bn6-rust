"""Export the HUD's tile font and HP-box frame for the ROM.

usage: python3 hud_tiles_export.py <out.bin>

The real ROM draws its HP box on BG3 as TILES, not sprites: each digit is two
tiles stacked, and the set steps by two tiles per digit, so digit six sits
twelve tiles past digit zero. The box itself is a left cap, four digit slots
filled right-aligned with a blank tile in the leading positions, and a right
cap.

The art is a fourth variant of the font the three-set font_export.py already
reads, in the same file: dword_86E1638 holds the ten digits in its first 640
bytes, verified tile for tile against a live battle's BG3, and the box frame
pieces follow immediately after. The palette is BG palette bank 13 of the same
battle.

Format (little-endian):
  0x00  magic "BNHT"
  0x04  u32 version
  0x08  u32 -> tiles  : u32 byte_len, then 4bpp tile data
  0x0c  u32 -> palette: 32 bytes (16 * u16 BGR555)
"""

import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bnasm import read_symbol

BN6 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "reference", "bn6f")
DAT = os.path.join(BN6, "data", "dat38_85.s")
BLOB = "dword_86E1638"
#: Ten digits then the frame pieces, 50 tiles.
BLOB_BYTES = 1600

#: Tile pair index within the blob for each piece, counting in two-tile pairs.
DIGIT_FIRST = 0
BLANK_PAIR = 10
CAP_PAIR = 11

#: BG palette bank 13, read from a live battle.
PALETTE = [0, 32766, 5285, 992, 31710, 32700, 32665, 28271, 25036, 895, 671, 640, 13639, 14326, 31697, 16648]


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "hud_tiles.bin"
    tiles = read_symbol(DAT, BLOB, max_bytes=BLOB_BYTES, through_labels=True)
    if len(tiles) != BLOB_BYTES:
        raise SystemExit(f"{BLOB}: expected {BLOB_BYTES} bytes, got {len(tiles)}")

    out = bytearray(struct.pack("<4sIII", b"BNHT", 1, 0, 0))
    while len(out) % 4:
        out.append(0)
    off_tiles = len(out)
    out += struct.pack("<I", len(tiles)) + tiles
    while len(out) % 4:
        out.append(0)
    off_pal = len(out)
    for c in PALETTE:
        out += struct.pack("<H", c)

    struct.pack_into("<4sIII", out, 0, b"BNHT", 1, off_tiles, off_pal)
    with open(out_path, "wb") as f:
        f.write(out)
    print(f"{out_path}: {len(out)} bytes ({len(tiles) // 32} tiles)")


if __name__ == "__main__":
    main()
