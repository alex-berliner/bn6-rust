"""Export the battle text font: the glyphs the chip name is drawn from.

usage: python3 text_font_export.py <out.bin>

The real ROM draws a chip's name along the bottom of the battle screen from a
font of two-tile glyphs, top over bottom, one glyph per 64-byte label in
data/dat38_60.s. The font begins at dword_86B7AE0 and the GLYPH INDEX IS THE
GAME'S OWN CHARACTER CODE, so constants/bn6-charmap.tbl indexes it directly:
code 0x0d is C, 0x26 is a, 0x33 is n, and rendering those tiles spells what the
charmap says it should.

Codes 0 through 0xb3 are exported. The first 0x40 are space, the digits, the
two cases and a couple of marks, which is everything a chip name uses; past
that the font runs into kana, and 0xb3 is the ZENNY SYMBOL the RESULT window's
reward line ends with -- matched by taking that line's tiles out of a live
screen and searching all 448 glyphs. The font itself is 448 glyphs of 64
bytes, sixteen rows of four.

A SECOND COPY FOLLOWS with 8 added to every nibble. The game does not blit
these glyphs unchanged: renderTextGfx_8045F8C's copy loop adds a 32-bit colour
word to every glyph word on the way to VRAM (sub_3006C18, asm/asm38.s:2381-94;
the word comes from dword_3006B84, whose entries are 0, 0x44444444, 0x88888888
and 0xCCCCCCCC). The RESULT window's reward line and the chip card's name both
pass colour index 8, so their tiles are these glyphs plus 0x88888888 -- which
is why searching a live screen's tiles for the raw font finds nothing. Checked
against a capture: the "1" and "0" of its "100 z" are glyph 2 and glyph 1 with
8 added to every nibble, byte for byte.

Format (little-endian):
  0x00  magic "BNTF"
  0x04  u32 version
  0x08  u32 -> tiles : u32 byte_len, then glyph 0 upward, two tiles each,
        then the same glyphs again with 8 added to every nibble
"""

import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bnasm import read_symbol

BN6 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "reference", "bn6f")
DAT = os.path.join(BN6, "data", "dat38_60.s")
FONT = "dword_86B7AE0"
GLYPHS = 0xB4
#: The zenny symbol, the last glyph this needs.
ZENNY = 0xB3


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "text_font.bin"
    want = GLYPHS * 64
    tiles = read_symbol(DAT, FONT, max_bytes=want, through_labels=True)
    if len(tiles) != want:
        raise SystemExit(f"{FONT}: expected {want} bytes, got {len(tiles)}")

    shifted = bytes(((b & 15) + 8) | ((((b >> 4) & 15) + 8) << 4) for b in tiles)
    tiles = tiles + shifted

    out = bytearray(struct.pack("<4sII", b"BNTF", 2, 0))
    while len(out) % 4:
        out.append(0)
    off = len(out)
    out += struct.pack("<I", len(tiles)) + tiles
    struct.pack_into("<4sII", out, 0, b"BNTF", 1, off)
    with open(out_path, "wb") as f:
        f.write(out)
    print(f"{out_path}: {len(out)} bytes ({GLYPHS} glyphs, twice)")


if __name__ == "__main__":
    main()
