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
  then  u32 -> palette: 4 banks * 32 bytes (offset stored at 0x0c), the
        fourth being the reward picture's own bank 12, then the reward
        picture's 42 tiles

THE REWARD PICTURE, the coin in the GET DATA box, is a 7x6 image the game
draws into the window's map at columns 14-20, rows 10-15 in bank 12 -- the
same shape as a chip card's picture. It is dword_8732E54 and its palette
dword_8733394, both found by taking the 42 tiles out of a live results
screen's char block and matching them byte for byte. It is kept as its own
tileset rather than padded into the window's blob, which would cost 15 KB of
zeroes to reach tile 0x1e8.
"""

import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bnasm import read_symbol

BN6 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "reference", "bn6f")
DAT = os.path.join(BN6, "data", "dat38_86.s")

FONT_TILE = 0xA0
#: The reward picture's size, in tiles: 7 wide by 6 tall, like a chip card's.
REWARD_TILES = 42
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
    out += read_symbol(DAT, "dword_8733394", max_bytes=32, through_labels=True)[:32]
    while len(out) % 4:
        out.append(0)
    coin = read_symbol(DAT, "dword_8732E54", max_bytes=REWARD_TILES * 32, through_labels=True)
    assert len(coin) == REWARD_TILES * 32
    out += coin
    with open(out_path, "wb") as f:
        f.write(out)
    print(f"{out_path}: {len(out)} bytes ({len(VARIANTS)} variants)")


if __name__ == "__main__":
    main()
