"""Export the battle text font: the glyphs the chip name is drawn from.

usage: python3 text_font_export.py <out.bin>

The real ROM draws a chip's name along the bottom of the battle screen from a
font of two-tile glyphs, top over bottom, one glyph per 64-byte label in
data/dat38_60.s. The font begins at dword_86B7AE0 and the GLYPH INDEX IS THE
GAME'S OWN CHARACTER CODE, so constants/bn6-charmap.tbl indexes it directly:
code 0x0d is C, 0x26 is a, 0x33 is n, and rendering those tiles spells what the
charmap says it should.

Only codes 0 through 0x3f are exported: space, the digits, the two cases and a
couple of marks, which is everything a chip name uses. Past that the font runs
into kana.

Format (little-endian):
  0x00  magic "BNTF"
  0x04  u32 version
  0x08  u32 -> tiles : u32 byte_len, then glyph 0 upward, two tiles each
"""

import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bnasm import read_symbol

BN6 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "reference", "bn6f")
DAT = os.path.join(BN6, "data", "dat38_60.s")
FONT = "dword_86B7AE0"
GLYPHS = 0x40


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "text_font.bin"
    want = GLYPHS * 64
    tiles = read_symbol(DAT, FONT, max_bytes=want, through_labels=True)
    if len(tiles) != want:
        raise SystemExit(f"{FONT}: expected {want} bytes, got {len(tiles)}")

    out = bytearray(struct.pack("<4sII", b"BNTF", 1, 0))
    while len(out) % 4:
        out.append(0)
    off = len(out)
    out += struct.pack("<I", len(tiles)) + tiles
    struct.pack_into("<4sII", out, 0, b"BNTF", 1, off)
    with open(out_path, "wb") as f:
        f.write(out)
    print(f"{out_path}: {len(out)} bytes ({GLYPHS} glyphs)")


if __name__ == "__main__":
    main()
