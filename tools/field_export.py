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
"""

import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from field_dump import load


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "field.bin"
    tiles, tilemap, pal = load()

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
