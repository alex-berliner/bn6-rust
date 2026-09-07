"""Export the palette for the chip-in-hand icon.

usage: python3 hand_icon_export.py <out.bin>

The real ROM hangs a 16x16 object over the navi showing the icon of the chip
at the front of its hand: read out of a live battle's OAM it is at (59,52)
with the navi on the middle panel of its own row, OBJ palette 10, and its four
tiles are byte for byte the chip's own icon from byte_8725894 -- the same art
the chip window's slots use, which chips.bin already carries.

Only the palette is new. It is byte_872CFD4 in data/dat38_86.s and it is NOT
the window's icon bank: that one is a background palette and differs at two
entries (0x6b5b against 0x675b, and 0x5eb3 against 0x0842, the frame's dark
edge).

Format (little-endian):
  0x00  magic "BNHI"
  0x04  u32 version
  0x08  16 BGR555 entries
"""

import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bnasm import read_symbol

BN6 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "reference", "bn6f")
DAT = os.path.join(BN6, "data", "dat38_86.s")
PALETTE = "byte_872CFD4"


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "hand_icon.bin"
    palette = read_symbol(DAT, PALETTE, max_bytes=32, through_labels=True)[:32]
    if len(palette) != 32:
        raise SystemExit(f"{PALETTE}: expected 32 bytes, got {len(palette)}")
    out = struct.pack("<4sI", b"BNHI", 1) + palette
    with open(out_path, "wb") as f:
        f.write(out)
    print(f"{out_path}: {len(out)} bytes")


if __name__ == "__main__":
    main()
