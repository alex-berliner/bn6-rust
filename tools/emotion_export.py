"""Export the emotion window: the navi's face at the top left of the battle.

usage: python3 emotion_export.py <out.bin>

The real ROM draws it as two objects, not tiles: a 32x16 at (0,18) and a 16x16
at (32,18), both in OBJ palette bank 12, read straight out of the sterile
arena's OAM on a paused battle frame (objects 2 and 3, VRAM tiles 0x3b4 and
0x3bc). That is why it survives the field being stripped and shows in every
chip capture, above the compared window.

Its art is dword_872D814 in data/dat38_86.s, found by taking those twelve
tiles out of OBJ VRAM and searching every assembled label in the disassembly
for their bytes: the first eight tiles are the 32x16 object and the four in
the label after it, dword_872D914, are the 16x16 one, which is exactly how the
two objects split. The bank of faces continues past them at 0x180 bytes each,
one per emotion; only the calm one is exported, which is the one every capture
shows. The palette is dword_872F114 in the same file, matching OBJ bank 12
word for word.

Format (little-endian):
  0x00  magic "BNEM"
  0x04  u32 version
  0x08  u32 -> tiles   : u32 byte_len, then the twelve tiles in VRAM order
  0x0c  u32 -> palette : 16 BGR555 entries
"""

import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bnasm import read_symbol

BN6 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "reference", "bn6f")
DAT = os.path.join(BN6, "data", "dat38_86.s")
TILES = "dword_872D814"
PALETTE = "dword_872F114"
#: The 32x16 object's eight tiles and the 16x16 object's four.
TILE_COUNT = 12


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "emotion.bin"
    want = TILE_COUNT * 32
    tiles = read_symbol(DAT, TILES, max_bytes=want, through_labels=True)
    if len(tiles) != want:
        raise SystemExit(f"{TILES}: expected {want} bytes, got {len(tiles)}")
    palette = read_symbol(DAT, PALETTE, max_bytes=32, through_labels=True)
    if len(palette) != 32:
        raise SystemExit(f"{PALETTE}: expected 32 bytes, got {len(palette)}")

    out = bytearray(struct.pack("<4sIII", b"BNEM", 1, 0, 0))
    while len(out) % 4:
        out.append(0)
    off_tiles = len(out)
    out += struct.pack("<I", len(tiles)) + tiles
    off_pal = len(out)
    out += palette
    struct.pack_into("<4sIII", out, 0, b"BNEM", 1, off_tiles, off_pal)
    with open(out_path, "wb") as f:
        f.write(out)
    print(f"{out_path}: {len(out)} bytes ({TILE_COUNT} tiles)")


if __name__ == "__main__":
    main()
