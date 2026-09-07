"""Export the in-battle chip selection window for the ROM.

usage: python3 custom_export.py <out.bin>

The window is a 15x20 tilemap in palette bank 9 (byte_86E625C,
data/dat38_85.s:2997), drawn on BG3 with char block 2 and shown by sliding
BG3's scroll from 0x78 to 0 at 0xc a frame (sub_8026B04, asm03_0.s:882).
Its tiles are dword_86E1D38, the raw 4bpp block that follows the window's
three palette variants dword_86E1C78 in the same file; nothing names it in
the code because it is uploaded with that block, which is why it took a scan
of every data blob against the map to find. The checkered cells in the
source map are the areas the game patches straight after copying it in
(sub_8026840, asm03_0.s:576-590): the 6-byte records byte_8027B2C
(x, y, w, h, palette bank, column-major flag; asm03_0.s:3108) are applied
by sub_8027CCC (asm03_0.s:3204), which fills each rectangle with running
VRAM tile ids from 0x9b -- the chip name, picture, element/damage row, the
two rows of five slots with their code letters, OK and the right-hand
column -- that the chip renderers draw into at runtime. Here those cells
are exported as the blank tile in the record's bank, and the records are
kept so the ROM can draw into the same regions.

Format (little-endian):
  0x00  magic "BNCW"
  0x04  u32 version (2)
  0x08  u32 -> tiles   : u32 byte_len, then tiles (tile 0 blank, then the
                         block, so the map's ids index it directly)
  0x0c  u32 -> map     : u32 w, u32 h, w*h u16 entries (patched)
  0x10  u32 -> palette : 3 banks * 32 bytes, then the shared icon bank
  0x14  u32 -> regions : u32 count, then count * 8 bytes:
                         x, y, w, h, bank, column_major, u16 first VRAM
                         tile id the game assigns (0x9b onwards)
  0x18  u32 -> cursor  : 2 8x8 4bpp tiles, then a 32-byte palette
  0x1c  u32 -> slot art: empty icon (0x80: 4 tiles, 16x16), 28 code
                         glyphs (0x40 each: 2 tiles, 8x16; 0x1b blank),
                         the interactive OK box (0x100: 8 tiles, 4x2), then
                         the pick stack's two frame tiles (0x40)

The cursor is four 8x8 objects, one corner tile flipped into each corner,
blinking between its two tiles every 8 frames (sub_8028820, asm03_0.s:4791;
attribute word 0xb764 = tile 0x364, palette 11). The window's upload list
off_802A744 (asm03_0.s:9024) copies the two tiles dword_86E55BC to OBJ VRAM
0x6016C80 -- tile 0x364. The palette it stages, byte_86E587C to 0x3001A80,
is background bank 9 (the palette master is palette_3001960, bank N at
+N*0x20), so the source of object bank 11 was not found; byte_86E587C's
first bank draws the bracket in the game's yellow and is used for it.

The slots' art when nothing is picked: the empty icon byte_86E601C goes
into every slot and stack cell (sub_8028310, asm03_0.s:4152; sub_80281D4
with id 0x1ff, asm03_0.s:3942), a slot's code letter comes from
dword_86E591C + code * 0x40 with 0x1b for none (sub_8028204), and the OK
box region gets byte_86E79CC + 0x300 while the box is live (sub_8028320,
asm03_0.s:4176).
"""

import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bnasm import read_symbol

BN6 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "reference", "bn6f")
DAT = os.path.join(BN6, "data", "dat38_85.s")
ASM = os.path.join(BN6, "asm", "asm03_0.s")
TILES = 135
FIRST_DYNAMIC = 0x9B


def patch_records():
    """The byte_8027B2C records up to their 0xff terminator."""
    lines = open(ASM).read().split("\n")
    start = next(i for i, l in enumerate(lines) if l.startswith("byte_8027B2C:"))
    data = []
    for line in lines[start:]:
        m = re.match(r"\s*\.byte (.*)", line)
        if m:
            data += [int(v, 0) for v in m.group(1).split(",")]
        elif data and not line.endswith(":"):
            break
    records = []
    while data[len(records) * 6] != 0xFF:
        records.append(tuple(data[len(records) * 6 : len(records) * 6 + 6]))
    return records


def apply_patches(tilemap, records):
    """Overwrite each record's rectangle the way sub_8027CCC does, returning
    the patched map and the first VRAM tile id each record was given."""
    tilemap = bytearray(tilemap)
    firsts = []
    tile = FIRST_DYNAMIC
    for x, y, w, h, bank, column_major in records:
        firsts.append(tile)
        step = h if column_major == 1 else 1
        for row in range(h):
            for col in range(w):
                # The game writes tile + col*step (+row for column-major);
                # those ids are VRAM tiles the ROM does not have, so the cell
                # is exported blank in the record's bank.
                struct.pack_into("<H", tilemap, ((y + row) * 15 + x + col) * 2, bank << 12)
        tile += w * h
    return bytes(tilemap), firsts


#: BG palette bank 11 of a live menu: the shared icon and meter palette.
SHARED_ICON_PALETTE = [0, 32767, 27483, 22198, 16944, 13739, 10538, 5285, 17277, 24243, 22198, 5285, 15823, 0, 0, 0]
#: BG palette bank 12 of the same menu: the DIMMED copy the real ROM gives a
#: slot whose chip cannot join the picks made so far. It is not a computed dim
#: of bank 11 -- white drops 19% per channel where the next entry drops 27% --
#: so like bank 11 it is read off a live menu rather than found in the data.
DIM_ICON_PALETTE = [0, 26425, 20083, 16945, 14798, 11626, 10538, 5285, 23287, 24243, 0, 0, 0, 0, 0, 0]


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "custom.bin"
    tiles = bytes(32) + read_symbol(DAT, "dword_86E1D38", max_bytes=TILES * 32, through_labels=True)
    tilemap = read_symbol(DAT, "byte_86E625C", max_bytes=15 * 20 * 2, through_labels=True)
    pal = read_symbol(DAT, "dword_86E1C78", max_bytes=96, through_labels=True)
    assert len(tiles) == (TILES + 1) * 32 and len(tilemap) == 600 and len(pal) == 96
    records = patch_records()
    tilemap, firsts = apply_patches(tilemap, records)
    cursor = read_symbol(DAT, "dword_86E55BC", max_bytes=64, through_labels=True)
    cursor_pal = read_symbol(DAT, "byte_86E587C", max_bytes=32, through_labels=True)
    # The cursor's own OBJECT palette, which is not the same thing: byte_86E587C
    # is the window's BACKGROUND bank 9 word for word, and the bracket sprites
    # draw from OBJ bank 11 instead, where their corners are orange rather than
    # the yellow bank 9 gives them. Read off a live menu's OBJ palette and
    # matched back to this symbol.
    cursor_obj_pal = read_symbol(DAT, "byte_86E56FC", max_bytes=32, through_labels=True)[:32]
    # The regular-chip mark: the gold ring with a red disc above the pick
    # stack, a 16x16 object the real ROM draws inside a 32x32 OAM entry at
    # (87,-4), so the ring itself lands at (95,4). Its four tiles are the four
    # non-blank ones of that entry and they are contiguous here.
    regular_mark = read_symbol(
        os.path.join(BN6, "data", "dat38_86.s"),
        "byte_86F5834",
        max_bytes=128,
        through_labels=True,
    )
    assert len(cursor) == 64 and len(cursor_pal) == 32
    assert len(cursor_obj_pal) == 32 and len(regular_mark) == 128
    empty = read_symbol(DAT, "byte_86E601C", max_bytes=0x80, through_labels=True)
    codes = read_symbol(DAT, "dword_86E591C", max_bytes=28 * 0x40, through_labels=True)
    ok = read_symbol(DAT, "byte_86E79CC", max_bytes=0x400, through_labels=True)[0x300:0x400]
    # The two tiles that frame the pick stack, alternating down the columns
    # either side of it. The window's stored map does not carry them -- the
    # game patches those cells in when it opens -- and they are not in the
    # window's own tile block; byte_86E2E18 is a separate block the game
    # uploads at VRAM tile 0x89, and it begins with exactly these two.
    stack_frame = read_symbol(DAT, "byte_86E2E18", max_bytes=64, through_labels=True)
    assert len(empty) == 0x80 and len(codes) == 28 * 0x40 and len(ok) == 0x100
    assert len(stack_frame) == 64

    out = bytearray(struct.pack("<4sIIIIIII", b"BNCW", 2, 0, 0, 0, 0, 0, 0))
    off_tiles = len(out)
    out += struct.pack("<I", len(tiles)) + tiles
    while len(out) % 4:
        out.append(0)
    off_map = len(out)
    out += struct.pack("<II", 15, 20) + tilemap
    off_pal = len(out)
    out += pal
    # A FOURTH bank after the three variants: the one palette every chip icon
    # and the vertical meter draw in. The real ROM keeps it in BG bank 11 and
    # draws every icon from it, so its icons are greyscale rather than each
    # chip's own colours -- read off a live menu, since it is in neither this
    # window's data nor the chip data.
    for c in SHARED_ICON_PALETTE + DIM_ICON_PALETTE:
        out += struct.pack("<H", c)
    off_regions = len(out)
    out += struct.pack("<I", len(records))
    for record, first in zip(records, firsts):
        out += struct.pack("<6BH", *record, first)
    while len(out) % 4:
        out.append(0)
    off_cursor = len(out)
    out += cursor + cursor_pal + cursor_obj_pal
    off_slot_art = len(out)
    out += empty + codes + ok + stack_frame + regular_mark
    struct.pack_into(
        "<4sIIIIIII",
        out,
        0,
        b"BNCW",
        2,
        off_tiles,
        off_map,
        off_pal,
        off_regions,
        off_cursor,
        off_slot_art,
    )
    with open(out_path, "wb") as f:
        f.write(out)
    print(f"{out_path}: {len(out)} bytes")


if __name__ == "__main__":
    main()
