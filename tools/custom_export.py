"""Export the in-battle chip selection window for the ROM.

usage: python3 custom_export.py <out.bin>

The window is a 15x20 tilemap in palette bank 9 (byte_86E625C,
data/dat38_85.s:2997), drawn on BG3 with char block 2 and shown by sliding
BG3's scroll from 0x78 to 0 at 0xc a frame (sub_8026B04, asm03_0.s:882).
Its tiles are dword_86E1D38, the raw 4bpp block that follows the window's
three palette variants dword_86E1C78 in the same file; nothing names it in
the code because it is uploaded with that block, which is why it took a scan
of every data blob against the map to find. The checkered cells are the
placeholders the game overwrites with chip art and icons at runtime.

Format (little-endian):
  0x00  magic "BNCW"
  0x04  u32 version
  0x08  u32 -> tiles   : u32 byte_len, then tiles (tile 0 blank, then the
                         block, so the map's ids index it directly)
  0x0c  u32 -> map     : u32 w, u32 h, w*h u16 entries
  0x10  u32 -> palette : 3 banks * 32 bytes
"""

import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bnasm import read_symbol

BN6 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "reference", "bn6f")
DAT = os.path.join(BN6, "data", "dat38_85.s")
TILES = 135


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "custom.bin"
    tiles = bytes(32) + read_symbol(DAT, "dword_86E1D38", max_bytes=TILES * 32, through_labels=True)
    tilemap = read_symbol(DAT, "byte_86E625C", max_bytes=15 * 20 * 2, through_labels=True)
    pal = read_symbol(DAT, "dword_86E1C78", max_bytes=96, through_labels=True)
    assert len(tiles) == (TILES + 1) * 32 and len(tilemap) == 600 and len(pal) == 96

    out = bytearray(struct.pack("<4sIIII", b"BNCW", 1, 0, 0, 0))
    off_tiles = len(out)
    out += struct.pack("<I", len(tiles)) + tiles
    while len(out) % 4:
        out.append(0)
    off_map = len(out)
    out += struct.pack("<II", 15, 20) + tilemap
    off_pal = len(out)
    out += pal
    struct.pack_into("<4sIIII", out, 0, b"BNCW", 1, off_tiles, off_map, off_pal)
    with open(out_path, "wb") as f:
        f.write(out)
    print(f"{out_path}: {len(out)} bytes")


if __name__ == "__main__":
    main()
