"""Export the battle HP digit font for the ROM.

usage: python3 font_export.py <out.bin>

The digits are not a sprite container: they are raw 4bpp tile data acting as a
shared font, which is why they appear in no sprite pointer list. Each glyph is
0x40 bytes -- an 8x16 cell, stored as sixteen 4-byte rows, which is exactly two
stacked 8x8 tiles and so can be handed to an OBJ unchanged.

Three variants exist at 0x280 apart (dword_86E0AB8/86E0D38/86E0FB8,
data/dat38_85.s:1476). They share outline colour 9 and differ only in their
inner colour (5, 8 and 14), which is how the game tints the number. Only the
first is exported until something needs the others.

Format (little-endian):
  0x00  magic "BNFT"
  0x04  u32 version
  0x08  u32 glyph count
  0x0c  glyphs, 0x40 bytes each, digit 0 first
"""

import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bnasm import read_symbol

BN6 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "reference", "bn6f")
DAT = os.path.join(BN6, "data", "dat38_85.s")

GLYPHS = 10
GLYPH_BYTES = 0x40


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "font.bin"
    data = read_symbol(DAT, "dword_86E0AB8", max_bytes=GLYPHS * GLYPH_BYTES,
                       through_labels=True)
    if len(data) != GLYPHS * GLYPH_BYTES:
        raise SystemExit(f"expected {GLYPHS * GLYPH_BYTES} bytes, got {len(data)}")

    out = bytearray(struct.pack("<4sII", b"BNFT", 1, GLYPHS))
    out += data
    with open(out_path, "wb") as f:
        f.write(out)
    print(f"{out_path}: {len(out)} bytes ({GLYPHS} glyphs)")


if __name__ == "__main__":
    main()
