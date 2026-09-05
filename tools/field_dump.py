"""Render the bn6f 6x3 battle field to a PNG.

Geometry and data locations come from the disassembly:
  - `object_getCoordinatesForPanels` (asm/object.s): panels are 40x24 px, with
    X = panelX * 40 - 140 and Y = panelY * 24 - 20 relative to field centre.
  - `sub_800C01C` copies 5x3 tiles per panel; tile column comes from the
    `byte_800C0AA` table and tile row from `3 * row + 6`.
  - `sub_80075CA` (asm/asm00_1.s) loads the tileset from `dword_86DDBA0` and
    queues `dword_86E08F8` (0x100 bytes) into the palette buffer at 0x3001980,
    which is bank 1 onwards -- so that blob supplies BG banks 1..8.
    Banks 1-4 are the red (enemy) side, banks 5-8 the blue (player) side.
"""

import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bnasm import bgr555, decode_tile, lz77_decompress, read_symbol

BN6 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "reference", "bn6f")
DAT = os.path.join(BN6, "data", "dat38_85.s")

TILE_COLS = [-5, 0, 5, 10, 15, 20, 25, 30]
PANEL_TW, PANEL_TH = 5, 3

# sub_80075CA decompresses the tileset to 0x6001460, i.e. VRAM tile 163, so the
# tilemap's tile ids are offset by that much from the start of the blob. The
# lowest id any panel variant uses is exactly 163, which confirms the base.
TILE_BASE = (0x6001460 - 0x6000000) // 32


def load():
    tiles = lz77_decompress(read_symbol(DAT, "dword_86DDBA0", max_bytes=0x4000,
                                        through_labels=True))
    tilemap = read_symbol(DAT, "byte_86DFA98", max_bytes=0x400, through_labels=True)
    # Bank 0 and banks 1..8 come from different blobs, queued separately by
    # sub_80075CA. Assemble them into one 16-bank palette.
    pal = bytearray(32 * 16)
    pal[0:32] = read_symbol(DAT, "dword_86E09F8", max_bytes=0x20, through_labels=True)
    pal[32:32 + 0x100] = read_symbol(DAT, "dword_86E08F8", max_bytes=0x100,
                                     through_labels=True)
    return tiles, tilemap, bytes(pal)


def bank(pal, n):
    base = n * 32
    return [int.from_bytes(pal[base + i * 2: base + i * 2 + 2], "little") for i in range(16)]


def render(field_type=0, scale=3):
    tiles, tilemap, pal = load()
    img = Image.new("RGB", (240, 160), (0, 0, 0))

    for row in range(1, 4):
        for col in range(1, 7):
            side = 0 if col <= 3 else 1
            variant = 6 * field_type + 3 * side + (row - 1)
            entries = tilemap[variant * 32: variant * 32 + 30]
            tile_x = TILE_COLS[col]
            tile_y = 3 * row + 6

            for i in range(PANEL_TW * PANEL_TH):
                e = int.from_bytes(entries[i * 2: i * 2 + 2], "little")
                tid, hflip, vflip, pb = e & 0x3FF, e & 0x400, e & 0x800, e >> 12
                colours = bank(pal, pb)
                px = decode_tile(tiles, tid - TILE_BASE)
                tx = (tile_x + i % PANEL_TW) * 8
                ty = (tile_y + i // PANEL_TW) * 8
                for y in range(8):
                    for x in range(8):
                        v = px[7 - y if vflip else y][7 - x if hflip else x]
                        if v == 0:
                            continue
                        sx, sy = tx + x, ty + y
                        if 0 <= sx < 240 and 0 <= sy < 160:
                            img.putpixel((sx, sy), bgr555(colours[v]))

    return img.resize((240 * scale, 160 * scale), Image.NEAREST)


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "field.png"
    ftype = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    render(ftype).save(out)
    print("wrote", out)
