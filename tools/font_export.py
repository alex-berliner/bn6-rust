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

The palette follows the glyphs. It is dword_86B7AC0 in data/dat38_60.s, the
32 bytes immediately before the battle text font, and it is the game's own:
dumping OBJ palette bank 14 out of a live battle where a number is on screen
gives those sixteen words back exactly. The glyphs use index 5 for the fill
and 9 for the outline, so the inner white is 0x7bfe and the outline the dark
blue 0x28e6 -- not the flat white on black this build stood in before.

Format (little-endian):
  0x00  magic "BNFT"
  0x04  u32 version
  0x08  u32 glyph count
  0x0c  glyphs, 0x40 bytes each, digit 0 first
        then 16 BGR555 palette entries
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
# The three pre-coloured sets the game switches between: the HP number is
# drawn from off_801D854 normally and from off_801D880 / off_801D8AC while
# it flashes after damage or a heal (asm/asm00_2.s:26131). They differ only
# in the fill colour index (5, 8 and 14) over the same outline.
VARIANTS = ["dword_86E0AB8", "dword_86E0D38", "dword_86E0FB8"]
#: The palette all three draw in, OBJ bank 14 of a live battle.
PALETTE = "dword_86B7AC0"


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "font.bin"
    sets = []
    for symbol in VARIANTS:
        data = read_symbol(DAT, symbol, max_bytes=GLYPHS * GLYPH_BYTES, through_labels=True)
        if len(data) != GLYPHS * GLYPH_BYTES:
            raise SystemExit(f"{symbol}: expected {GLYPHS * GLYPH_BYTES} bytes, got {len(data)}")
        sets.append(data)

    palette = read_symbol(
        os.path.join(BN6, "data", "dat38_60.s"),
        PALETTE,
        max_bytes=32,
        through_labels=True,
    )[:32]
    if len(palette) != 32:
        raise SystemExit(f"{PALETTE}: expected 32 bytes, got {len(palette)}")

    # Glyph n of set v is at index v * GLYPHS + n.
    out = bytearray(struct.pack("<4sII", b"BNFT", 2, GLYPHS * len(sets)))
    for data in sets:
        out += data
    out += palette
    with open(out_path, "wb") as f:
        f.write(out)
    print(f"{out_path}: {len(out)} bytes ({len(sets)} sets of {GLYPHS} glyphs)")


if __name__ == "__main__":
    main()
