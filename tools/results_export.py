"""Export the battle results windows for the ROM.

usage: python3 results_export.py <out.bin>

sub_802C34E (asm/asm03_0.s:12353) shows one of these after a battle: a raw
tileset queued to char block 2 from tile 1, a 24x18 tilemap in palette bank 9,
a three-bank palette for banks 9-11 (the clear-time digits recolour by rank),
and a digit font placed at tile 0xa0 (data/dat38_86.s; table off_802C3FC).

Variant 0 is the RESULT window, variant 1 the LOSER window. Each variant's
tile blob is laid out so the map's ids index it directly: tile 0 blank, the
tileset from 1, and for the win window the font from 0xa0.

Format (little-endian):
  0x00  magic "BNRS"
  0x04  u32 version
  0x08  u32 variant count, then per variant:
          u32 tiles_len, tiles (4-aligned); u32 w, u32 h, w*h u16 map
  then  u32 -> palette: 3 banks * 32 bytes (offset stored at 0x0c)
"""

import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bnasm import read_symbol

BN6 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "reference", "bn6f")
DAT = os.path.join(BN6, "data", "dat38_86.s")

FONT_TILE = 0xA0
VARIANTS = [
    ("byte_872F3F4", 0xE60, "dword_8731DF4", True),
    ("dword_8731154", 0xCA0, "dword_87324B4", False),
]


def blob(tileset, with_font):
    out = bytearray(32) + tileset
    if with_font:
        out += bytes(FONT_TILE * 32 - len(out))
        out += read_symbol(DAT, "dword_8732874", max_bytes=0x5E0, through_labels=True)
    return bytes(out)


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "results.bin"
    out = bytearray(struct.pack("<4sIII", b"BNRS", 1, len(VARIANTS), 0))
    for tiles_sym, size, map_sym, with_font in VARIANTS:
        tiles = blob(read_symbol(DAT, tiles_sym, max_bytes=size, through_labels=True), with_font)
        while len(out) % 4:
            out.append(0)
        out += struct.pack("<I", len(tiles)) + tiles
        while len(out) % 4:
            out.append(0)
        tilemap = read_symbol(DAT, map_sym, max_bytes=24 * 18 * 2, through_labels=True)
        out += struct.pack("<II", 24, 18) + tilemap
    while len(out) % 4:
        out.append(0)
    struct.pack_into("<I", out, 0x0C, len(out))
    out += read_symbol(DAT, "dword_8732814", max_bytes=96, through_labels=True)
    with open(out_path, "wb") as f:
        f.write(out)
    print(f"{out_path}: {len(out)} bytes ({len(VARIANTS)} variants)")


if __name__ == "__main__":
    main()
