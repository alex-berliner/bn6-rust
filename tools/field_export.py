"""Export the bn6f battle field tileset, tilemap and palette for the ROM.

usage: python3 field_export.py <out.bin>

Format (little-endian):
  0x00  magic "BNFD"
  0x04  u32 version
  0x08  u32 -> tiles   : u32 byte_len, then 4bpp tile data (4-byte aligned)
  0x0c  u32 -> tilemap : u32 variant_count, then variant_count * 32 bytes
  0x10  u32 -> palette : 16 banks * 32 bytes (BGR555)

Each tilemap variant is 15 GBA background entries (5x3 tiles for one panel)
plus padding. Variant index is `6 * panel_type + 3 * side + (row - 1)`.

After the panel variants come the two highlight overlays that sub_800C0BA
draws for a one-shot panel flash (dword_86E0458 and dword_86E0478,
asm/object.s:1154): each is a solid block of one tile in bank 4, with no
side or row variants. They are variants HIGHLIGHT_FIRST and +1.
"""

import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bnasm import read_symbol
from field_dump import DAT, TILE_BASE, load

HIGHLIGHT_FIRST = 32
# The two variants after the highlights: the front lip the real ROM draws in
# the tilemap row below the bottom panel row, one per side. Read straight off
# the live BG2 tilemap (screen block 30, row 18): five entries repeating tiles
# 0x28d, 0x28e, 0x28f, 0x28e, 0x28d, in palette 1 on the player's red half and
# palette 5 on the enemy's blue one, the same banks the panels use. Those tile
# ids fall inside the exported tileset already, which covers 498 tiles from
# TILE_BASE, so this adds a tilemap row and no new graphics.
LIP_FIRST = HIGHLIGHT_FIRST + 2
LIP_TILES = (0x28D, 0x28E, 0x28F, 0x28E, 0x28D)
LIP_PALETTES = (1, 5)


def rebase(tilemap):
    """Rewrite tile ids to index the tileset blob directly.

    The game's ids are VRAM tile numbers and the blob is loaded at TILE_BASE,
    so the ROM would otherwise have to know that offset to draw a panel.
    Variants past the five real panel types hold junk ids below the base;
    they are pointed at tile 0 rather than wrapping negative.
    """
    out = bytearray(tilemap)
    for i in range(0, len(out) - 1, 2):
        e = int.from_bytes(out[i:i + 2], "little")
        tid = e & 0x3FF
        tid = tid - TILE_BASE if tid >= TILE_BASE else 0
        out[i:i + 2] = ((e & ~0x3FF) | tid).to_bytes(2, "little")
    return bytes(out)


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "field.bin"
    tiles, tilemap, pal = load()
    assert len(tilemap) // 32 == HIGHLIGHT_FIRST, len(tilemap)
    for sym in ("dword_86E0458", "dword_86E0478"):
        tilemap += read_symbol(DAT, sym, max_bytes=32, through_labels=True)
    assert len(tilemap) // 32 == LIP_FIRST, len(tilemap)
    for bank in LIP_PALETTES:
        row = b"".join(struct.pack("<H", t | (bank << 12)) for t in LIP_TILES)
        tilemap += row + bytes(32 - len(row))
    tilemap = rebase(tilemap)

    out = bytearray(struct.pack("<4sIIII", b"BNFD", 1, 0, 0, 0))

    def align():
        while len(out) % 4:
            out.append(0)

    align()
    off_tiles = len(out)
    out += struct.pack("<I", len(tiles))
    out += tiles

    align()
    off_map = len(out)
    out += struct.pack("<I", len(tilemap) // 32)
    out += tilemap

    align()
    off_pal = len(out)
    out += pal

    struct.pack_into("<4sIIII", out, 0, b"BNFD", 1, off_tiles, off_map, off_pal)
    with open(out_path, "wb") as f:
        f.write(out)
    print(f"{out_path}: {len(out)} bytes "
          f"({len(tiles)//32} tiles, {len(tilemap)//32} variants)")


if __name__ == "__main__":
    main()
