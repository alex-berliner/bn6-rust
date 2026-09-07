"""Export the battle backdrop's tileset, tilemap and palette for the ROM.

usage: python3 backdrop_export.py <out.bin>

The backdrop is the layer the real ROM keeps on BG1 at priority 3: a 32x32
tile map of a teal-arc motif on navy that scrolls one pixel left every two
frames and one pixel up every four.

AND IT IS ANIMATED. Its map, its palette and its scroll all stand still while
the TILE ART underneath cycles: seven complete sets of the layer's 37 tiles,
each held for eight frames, a 56-frame loop. Dumping BG1's char data frame by
frame off a live battle shows 36 of the 37 tiles changing across the loop
while the map's 1024 entries and palette bank 0 never move. The little purple
glyphs inside the backdrop's rings are what this animates; a still backdrop
differs from the real ROM by about 280 px a frame.

The tiles live in the disassembly at dword_8617488 (data/dat38_60.s), but the
blob's order is NOT the order the game uploads to VRAM and the 32x32 map is in
no data blob -- the game builds it at runtime. So FRAMES below records, for
each of the seven steps, the blob index of each of the 37 VRAM tiles, matched
byte for byte at tile alignment against the blob; MAP records the layer's
1024 cells as slot indices 0..36; and PALETTE is BG bank 0. None of it needs
the ROM to rebuild the asset -- only the disassembly submodule.

Format (little-endian):
  0x00  magic "BNBD"
  0x04  u32 version
  0x08  u32 -> tiles  : u32 byte_len, then frame 0's 37 tiles, frame 1's, ...
  0x0c  u32 -> map    : 32 * 32 u16 background entries, the slot index
  0x10  u32 -> palette: 32 bytes (16 * u16 BGR555)
  0x14  u32 frames
  0x18  u32 slots
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

#: Blob indices for each animation step, one row of 37 VRAM tiles each.
FRAMES = [
    [0, 0, 1, 2, 3, 4, 0, 5, 32, 33, 8, 134, 10, 11, 34, 14, 14, 135, 16, 17, 136, 14, 14, 35, 21, 22, 137, 24, 36, 37, 27, 0, 28, 29, 30, 31, 0],
    [0, 0, 1, 2, 3, 4, 0, 5, 32, 33, 8, 9, 10, 11, 34, 14, 14, 15, 16, 17, 18, 14, 14, 35, 21, 22, 23, 24, 36, 37, 27, 0, 38, 29, 30, 31, 0],
    [0, 0, 1, 2, 3, 4, 0, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 14, 19, 20, 21, 22, 23, 24, 25, 26, 27, 0, 28, 29, 30, 31, 0],
    [0, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 14, 15, 54, 55, 18, 14, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70],
    [0, 0, 71, 72, 73, 74, 0, 75, 76, 77, 78, 79, 80, 81, 82, 83, 53, 15, 84, 85, 18, 56, 86, 87, 88, 89, 90, 91, 92, 93, 94, 0, 95, 96, 97, 98, 0],
    [0, 39, 99, 100, 101, 102, 44, 103, 104, 105, 106, 107, 108, 109, 34, 110, 83, 111, 112, 113, 114, 115, 116, 35, 117, 118, 119, 120, 121, 122, 123, 65, 124, 125, 126, 127, 70],
    [0, 0, 1, 2, 3, 4, 0, 5, 32, 33, 128, 129, 10, 11, 34, 14, 110, 130, 16, 17, 131, 116, 14, 35, 21, 22, 132, 133, 36, 37, 27, 0, 28, 29, 30, 31, 0],
]


#: How many frames each step is held.
STEP_FRAMES = 8

#: The 32x32 background map, as slot indices 0..36.
MAP = [[0, 0, 0, 0, 0, 0, 0, 0, 0, 19, 20, 21, 22, 23, 24, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 19, 20, 21, 22, 23, 24, 0], [0, 1, 2, 3, 4, 5, 6, 0, 0, 25, 26, 27, 28, 29, 30, 0, 0, 1, 2, 3, 4, 5, 6, 0, 0, 25, 26, 27, 28, 29, 30, 0], [0, 7, 8, 9, 10, 11, 12, 0, 0, 31, 32, 33, 34, 35, 36, 0, 0, 7, 8, 9, 10, 11, 12, 0, 0, 31, 32, 33, 34, 35, 36, 0], [0, 13, 14, 15, 16, 17, 18, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 13, 14, 15, 16, 17, 18, 0, 0, 0, 0, 0, 0, 0, 0, 0], [0, 19, 20, 21, 22, 23, 24, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 19, 20, 21, 22, 23, 24, 0, 0, 0, 0, 0, 0, 0, 0, 0], [0, 25, 26, 27, 28, 29, 30, 0, 0, 1, 2, 3, 4, 5, 6, 0, 0, 25, 26, 27, 28, 29, 30, 0, 0, 1, 2, 3, 4, 5, 6, 0], [0, 31, 32, 33, 34, 35, 36, 0, 0, 7, 8, 9, 10, 11, 12, 0, 0, 31, 32, 33, 34, 35, 36, 0, 0, 7, 8, 9, 10, 11, 12, 0], [0, 0, 0, 0, 0, 0, 0, 0, 0, 13, 14, 15, 16, 17, 18, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 13, 14, 15, 16, 17, 18, 0], [0, 0, 0, 0, 0, 0, 0, 0, 0, 19, 20, 21, 22, 23, 24, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 19, 20, 21, 22, 23, 24, 0], [0, 1, 2, 3, 4, 5, 6, 0, 0, 25, 26, 27, 28, 29, 30, 0, 0, 1, 2, 3, 4, 5, 6, 0, 0, 25, 26, 27, 28, 29, 30, 0], [0, 7, 8, 9, 10, 11, 12, 0, 0, 31, 32, 33, 34, 35, 36, 0, 0, 7, 8, 9, 10, 11, 12, 0, 0, 31, 32, 33, 34, 35, 36, 0], [0, 13, 14, 15, 16, 17, 18, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 13, 14, 15, 16, 17, 18, 0, 0, 0, 0, 0, 0, 0, 0, 0], [0, 19, 20, 21, 22, 23, 24, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 19, 20, 21, 22, 23, 24, 0, 0, 0, 0, 0, 0, 0, 0, 0], [0, 25, 26, 27, 28, 29, 30, 0, 0, 1, 2, 3, 4, 5, 6, 0, 0, 25, 26, 27, 28, 29, 30, 0, 0, 1, 2, 3, 4, 5, 6, 0], [0, 31, 32, 33, 34, 35, 36, 0, 0, 7, 8, 9, 10, 11, 12, 0, 0, 31, 32, 33, 34, 35, 36, 0, 0, 7, 8, 9, 10, 11, 12, 0], [0, 0, 0, 0, 0, 0, 0, 0, 0, 13, 14, 15, 16, 17, 18, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 13, 14, 15, 16, 17, 18, 0], [0, 0, 0, 0, 0, 0, 0, 0, 0, 19, 20, 21, 22, 23, 24, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 19, 20, 21, 22, 23, 24, 0], [0, 1, 2, 3, 4, 5, 6, 0, 0, 25, 26, 27, 28, 29, 30, 0, 0, 1, 2, 3, 4, 5, 6, 0, 0, 25, 26, 27, 28, 29, 30, 0], [0, 7, 8, 9, 10, 11, 12, 0, 0, 31, 32, 33, 34, 35, 36, 0, 0, 7, 8, 9, 10, 11, 12, 0, 0, 31, 32, 33, 34, 35, 36, 0], [0, 13, 14, 15, 16, 17, 18, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 13, 14, 15, 16, 17, 18, 0, 0, 0, 0, 0, 0, 0, 0, 0], [0, 19, 20, 21, 22, 23, 24, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 19, 20, 21, 22, 23, 24, 0, 0, 0, 0, 0, 0, 0, 0, 0], [0, 25, 26, 27, 28, 29, 30, 0, 0, 1, 2, 3, 4, 5, 6, 0, 0, 25, 26, 27, 28, 29, 30, 0, 0, 1, 2, 3, 4, 5, 6, 0], [0, 31, 32, 33, 34, 35, 36, 0, 0, 7, 8, 9, 10, 11, 12, 0, 0, 31, 32, 33, 34, 35, 36, 0, 0, 7, 8, 9, 10, 11, 12, 0], [0, 0, 0, 0, 0, 0, 0, 0, 0, 13, 14, 15, 16, 17, 18, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 13, 14, 15, 16, 17, 18, 0], [0, 0, 0, 0, 0, 0, 0, 0, 0, 19, 20, 21, 22, 23, 24, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 19, 20, 21, 22, 23, 24, 0], [0, 1, 2, 3, 4, 5, 6, 0, 0, 25, 26, 27, 28, 29, 30, 0, 0, 1, 2, 3, 4, 5, 6, 0, 0, 25, 26, 27, 28, 29, 30, 0], [0, 7, 8, 9, 10, 11, 12, 0, 0, 31, 32, 33, 34, 35, 36, 0, 0, 7, 8, 9, 10, 11, 12, 0, 0, 31, 32, 33, 34, 35, 36, 0], [0, 13, 14, 15, 16, 17, 18, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 13, 14, 15, 16, 17, 18, 0, 0, 0, 0, 0, 0, 0, 0, 0], [0, 19, 20, 21, 22, 23, 24, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 19, 20, 21, 22, 23, 24, 0, 0, 0, 0, 0, 0, 0, 0, 0], [0, 25, 26, 27, 28, 29, 30, 0, 0, 1, 2, 3, 4, 5, 6, 0, 0, 25, 26, 27, 28, 29, 30, 0, 0, 1, 2, 3, 4, 5, 6, 0], [0, 31, 32, 33, 34, 35, 36, 0, 0, 7, 8, 9, 10, 11, 12, 0, 0, 31, 32, 33, 34, 35, 36, 0, 0, 7, 8, 9, 10, 11, 12, 0], [0, 0, 0, 0, 0, 0, 0, 0, 0, 13, 14, 15, 16, 17, 18, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 13, 14, 15, 16, 17, 18, 0]]


#: BG palette bank 0, read from a live battle.
PALETTE = [0, 32226, 32131, 28963, 27780, 24580, 19457, 26931, 22671, 17419, 10464, 992, 992, 9249, 10305, 10240]


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "backdrop.bin"
    blob = read_symbol(DAT, BLOB, max_bytes=BLOB_BYTES, through_labels=True)
    slots = len(FRAMES[0])
    assert all(len(f) == slots for f in FRAMES)
    tiles = b"".join(blob[i * 32:(i + 1) * 32] for f in FRAMES for i in f)

    out = bytearray(struct.pack("<4sIIIIII", b"BNBD", 2, 0, 0, 0, 0, 0))

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

    struct.pack_into(
        "<4sIIIIII", out, 0, b"BNBD", 2, off_tiles, off_map, off_pal, len(FRAMES), slots
    )
    with open(out_path, "wb") as f:
        f.write(out)
    print(f"{out_path}: {len(out)} bytes ({len(FRAMES)} steps of {slots} tiles, 32x32 map)")


if __name__ == "__main__":
    main()
