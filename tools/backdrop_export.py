"""Export the battle backdrop's tileset, tilemap and palette for the ROM.

usage: python3 backdrop_export.py <out.bin>

The backdrop is the layer the real ROM keeps on BG1 at priority 3: a 32x32
tile map of a teal-arc motif on navy that scrolls one pixel left every two
frames and one pixel up every four.

Its tiles live in the disassembly at dword_8617488 (data/dat38_60.s), 138
tiles, but the blob's order is NOT the order the game uploads to VRAM and the
32x32 map is not in any data blob -- the game builds it at runtime. So the map
below is recorded here as indices into TILES, which are indices into the blob,
recovered by matching every tile of a live battle's BG1 byte for byte against
the blob: all 37 distinct map tiles matched, collapsing to 32 blob tiles. The
palette is BG palette bank 0 of the same battle. Neither needs the ROM to
rebuild the asset -- only the disassembly submodule.

Format (little-endian):
  0x00  magic "BNBD"
  0x04  u32 version
  0x08  u32 -> tiles  : u32 byte_len, then 4bpp tile data
  0x0c  u32 -> map    : 32 * 32 u16 background entries
  0x10  u32 -> palette: 32 bytes (16 * u16 BGR555)
"""

import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bnasm import read_symbol

BN6 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "reference", "bn6f")
DAT = os.path.join(BN6, "data", "dat38_60.s")
BLOB = "dword_8617488"
BLOB_BYTES = 4416

#: Indices into the blob, in the order this asset lays them out.
TILES = [0, 17, 131, 116, 14, 35, 21, 1, 2, 3, 4, 22, 132, 133, 36, 37, 27, 5, 32, 33, 128, 129, 10, 28, 29, 30, 31, 11, 34, 110, 130, 16]

#: The 32x32 background map, as indices into TILES.
MAP = [[0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 3, 4, 5, 6, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 3, 4, 5, 6, 0], [0, 0, 7, 8, 9, 10, 0, 0, 0, 11, 12, 13, 14, 15, 16, 0, 0, 0, 7, 8, 9, 10, 0, 0, 0, 11, 12, 13, 14, 15, 16, 0], [0, 17, 18, 19, 20, 21, 22, 0, 0, 0, 23, 24, 25, 26, 0, 0, 0, 17, 18, 19, 20, 21, 22, 0, 0, 0, 23, 24, 25, 26, 0, 0], [0, 27, 28, 4, 29, 30, 31, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 27, 28, 4, 29, 30, 31, 0, 0, 0, 0, 0, 0, 0, 0, 0], [0, 1, 2, 3, 4, 5, 6, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 3, 4, 5, 6, 0, 0, 0, 0, 0, 0, 0, 0, 0], [0, 11, 12, 13, 14, 15, 16, 0, 0, 0, 7, 8, 9, 10, 0, 0, 0, 11, 12, 13, 14, 15, 16, 0, 0, 0, 7, 8, 9, 10, 0, 0], [0, 0, 23, 24, 25, 26, 0, 0, 0, 17, 18, 19, 20, 21, 22, 0, 0, 0, 23, 24, 25, 26, 0, 0, 0, 17, 18, 19, 20, 21, 22, 0], [0, 0, 0, 0, 0, 0, 0, 0, 0, 27, 28, 4, 29, 30, 31, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 27, 28, 4, 29, 30, 31, 0], [0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 3, 4, 5, 6, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 3, 4, 5, 6, 0], [0, 0, 7, 8, 9, 10, 0, 0, 0, 11, 12, 13, 14, 15, 16, 0, 0, 0, 7, 8, 9, 10, 0, 0, 0, 11, 12, 13, 14, 15, 16, 0], [0, 17, 18, 19, 20, 21, 22, 0, 0, 0, 23, 24, 25, 26, 0, 0, 0, 17, 18, 19, 20, 21, 22, 0, 0, 0, 23, 24, 25, 26, 0, 0], [0, 27, 28, 4, 29, 30, 31, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 27, 28, 4, 29, 30, 31, 0, 0, 0, 0, 0, 0, 0, 0, 0], [0, 1, 2, 3, 4, 5, 6, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 3, 4, 5, 6, 0, 0, 0, 0, 0, 0, 0, 0, 0], [0, 11, 12, 13, 14, 15, 16, 0, 0, 0, 7, 8, 9, 10, 0, 0, 0, 11, 12, 13, 14, 15, 16, 0, 0, 0, 7, 8, 9, 10, 0, 0], [0, 0, 23, 24, 25, 26, 0, 0, 0, 17, 18, 19, 20, 21, 22, 0, 0, 0, 23, 24, 25, 26, 0, 0, 0, 17, 18, 19, 20, 21, 22, 0], [0, 0, 0, 0, 0, 0, 0, 0, 0, 27, 28, 4, 29, 30, 31, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 27, 28, 4, 29, 30, 31, 0], [0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 3, 4, 5, 6, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 3, 4, 5, 6, 0], [0, 0, 7, 8, 9, 10, 0, 0, 0, 11, 12, 13, 14, 15, 16, 0, 0, 0, 7, 8, 9, 10, 0, 0, 0, 11, 12, 13, 14, 15, 16, 0], [0, 17, 18, 19, 20, 21, 22, 0, 0, 0, 23, 24, 25, 26, 0, 0, 0, 17, 18, 19, 20, 21, 22, 0, 0, 0, 23, 24, 25, 26, 0, 0], [0, 27, 28, 4, 29, 30, 31, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 27, 28, 4, 29, 30, 31, 0, 0, 0, 0, 0, 0, 0, 0, 0], [0, 1, 2, 3, 4, 5, 6, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 3, 4, 5, 6, 0, 0, 0, 0, 0, 0, 0, 0, 0], [0, 11, 12, 13, 14, 15, 16, 0, 0, 0, 7, 8, 9, 10, 0, 0, 0, 11, 12, 13, 14, 15, 16, 0, 0, 0, 7, 8, 9, 10, 0, 0], [0, 0, 23, 24, 25, 26, 0, 0, 0, 17, 18, 19, 20, 21, 22, 0, 0, 0, 23, 24, 25, 26, 0, 0, 0, 17, 18, 19, 20, 21, 22, 0], [0, 0, 0, 0, 0, 0, 0, 0, 0, 27, 28, 4, 29, 30, 31, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 27, 28, 4, 29, 30, 31, 0], [0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 3, 4, 5, 6, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 3, 4, 5, 6, 0], [0, 0, 7, 8, 9, 10, 0, 0, 0, 11, 12, 13, 14, 15, 16, 0, 0, 0, 7, 8, 9, 10, 0, 0, 0, 11, 12, 13, 14, 15, 16, 0], [0, 17, 18, 19, 20, 21, 22, 0, 0, 0, 23, 24, 25, 26, 0, 0, 0, 17, 18, 19, 20, 21, 22, 0, 0, 0, 23, 24, 25, 26, 0, 0], [0, 27, 28, 4, 29, 30, 31, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 27, 28, 4, 29, 30, 31, 0, 0, 0, 0, 0, 0, 0, 0, 0], [0, 1, 2, 3, 4, 5, 6, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 3, 4, 5, 6, 0, 0, 0, 0, 0, 0, 0, 0, 0], [0, 11, 12, 13, 14, 15, 16, 0, 0, 0, 7, 8, 9, 10, 0, 0, 0, 11, 12, 13, 14, 15, 16, 0, 0, 0, 7, 8, 9, 10, 0, 0], [0, 0, 23, 24, 25, 26, 0, 0, 0, 17, 18, 19, 20, 21, 22, 0, 0, 0, 23, 24, 25, 26, 0, 0, 0, 17, 18, 19, 20, 21, 22, 0], [0, 0, 0, 0, 0, 0, 0, 0, 0, 27, 28, 4, 29, 30, 31, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 27, 28, 4, 29, 30, 31, 0]]

#: BG palette bank 0, read from a live battle.
PALETTE = [0, 32226, 32131, 28963, 27780, 24580, 19457, 26931, 22671, 17419, 10464, 992, 992, 9249, 10305, 10240]


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "backdrop.bin"
    blob = read_symbol(DAT, BLOB, max_bytes=BLOB_BYTES, through_labels=True)
    tiles = b"".join(blob[i * 32:(i + 1) * 32] for i in TILES)

    out = bytearray(struct.pack("<4sIIII", b"BNBD", 1, 0, 0, 0))

    def align():
        while len(out) % 4:
            out.append(0)

    align()
    off_tiles = len(out)
    out += struct.pack("<I", len(tiles)) + tiles

    align()
    off_map = len(out)
    for row in MAP:
        for t in row:
            out += struct.pack("<H", t)

    align()
    off_pal = len(out)
    for c in PALETTE:
        out += struct.pack("<H", c)

    struct.pack_into("<4sIIII", out, 0, b"BNBD", 1, off_tiles, off_map, off_pal)
    with open(out_path, "wb") as f:
        f.write(out)
    print(f"{out_path}: {len(out)} bytes ({len(TILES)} tiles, 32x32 map)")


if __name__ == "__main__":
    main()
