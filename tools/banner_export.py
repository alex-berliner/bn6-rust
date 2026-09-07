#!/usr/bin/env python3
"""Export the battle BANNER -- "BATTLE START!", "ENEMY DELETED" and the rest.

usage: banner_export.py <bn6f.gba> assets/banner.bin [--sheet out.png]

The banner is the wide ribbon that crosses the middle of the screen. It is not
a picture: it is TEXT in a font of its own, twenty 8x16 cells laid out as five
32x16 objects, and each message is a list of pointers to those cells. Two
arrays of messages live at pt_801EF84 (20 entries) and pt_801EFD4 (27); each
entry points at a record whose first word is (y << 8) | x and whose following
words are glyph pointers, terminated by byte_801FDC0 -- which is itself the
BLANK glyph, so the uploader (sub_801E838, asm00_2.s:31106) simply stops
advancing and keeps writing blanks out to the twentieth cell.

The palette is not the text font's: sub_801E838 sends the sixteen colours at
byte_86F2900 to the palette staging buffer as its last act, so those are the
banner's own and they go in the asset too.

Output format, all little endian:

    0x00  "BNBR"
    0x04  version (1)
    0x08  glyph count
    0x0c  message count
    0x10  offset of the glyph block
    0x14  offset of the message block
    0x18  palette, 16 x u16
    ...   glyphs: `count` x 0x40 bytes, top tile then bottom tile
    ...   messages: `count` x (x u8, y u8, 20 x u16 glyph index)

Needs the real ROM, which is never committed.
"""

import argparse
import struct
import sys

BASE = 0x08000000
#: The two arrays of message records, by the address in their symbol names.
ARRAYS = [(0x0801EF84, 20), (0x0801EFD4, 27)]
#: The blank glyph, which also terminates a record's pointer list.
TERMINATOR = 0x0801FDC0
#: The sixteen colours sub_801E838 stages for the banner.
PALETTE = 0x086F2900
#: Cells across the strip: five 32x16 objects of four cells each.
CELLS = 20
GLYPH_BYTES = 0x40


def word(rom, addr):
    return struct.unpack_from("<I", rom, addr - BASE)[0]


def record(rom, addr):
    """(x, y, [glyph pointer] * CELLS), padded with the blank."""
    header = word(rom, addr)
    x, y = header & 0xFF, (header >> 8) & 0xFF
    glyphs = []
    at = addr + 4
    while len(glyphs) < CELLS:
        pointer = word(rom, at)
        if pointer == TERMINATOR:
            break
        glyphs.append(pointer)
        at += 4
    return x, y, glyphs + [TERMINATOR] * (CELLS - len(glyphs))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rom")
    ap.add_argument("out")
    ap.add_argument("--sheet", help="also render every message to a PNG")
    args = ap.parse_args()
    rom = open(args.rom, "rb").read()
    top = BASE + len(rom) - GLYPH_BYTES

    messages, glyphs = [], []
    index = {}
    for start, count in ARRAYS:
        for i in range(count):
            addr = word(rom, start + i * 4)
            if not BASE <= addr < top:
                continue
            x, y, pointers = record(rom, addr)
            # Two of the array slots are not records at all -- the arrays abut
            # and the boundary entry reads as one -- and they give themselves
            # away by pointing outside the ROM.
            if any(not BASE <= p < top for p in pointers):
                continue
            cells = []
            for p in pointers:
                if p not in index:
                    index[p] = len(glyphs)
                    glyphs.append(rom[p - BASE:p - BASE + GLYPH_BYTES])
                cells.append(index[p])
            messages.append((x, y, cells))

    header = bytearray(0x18 + 32)
    header[0:4] = b"BNBR"
    struct.pack_into("<I", header, 0x04, 1)
    struct.pack_into("<I", header, 0x08, len(glyphs))
    struct.pack_into("<I", header, 0x0C, len(messages))
    glyph_at = len(header)
    struct.pack_into("<I", header, 0x10, glyph_at)
    struct.pack_into("<I", header, 0x14, glyph_at + len(glyphs) * GLYPH_BYTES)
    header[0x18:0x18 + 32] = rom[PALETTE - BASE:PALETTE - BASE + 32]

    body = bytearray()
    for g in glyphs:
        body += g
    for x, y, cells in messages:
        body += struct.pack("<BB", x, y)
        for c in cells:
            body += struct.pack("<H", c)

    open(args.out, "wb").write(bytes(header) + bytes(body))
    print("%s: %d glyphs, %d messages, %d bytes"
          % (args.out, len(glyphs), len(messages), len(header) + len(body)))

    if args.sheet:
        from PIL import Image

        def expand(v):
            r, g, b = v & 31, (v >> 5) & 31, (v >> 10) & 31
            return ((r << 3) | (r >> 2), (g << 3) | (g >> 2), (b << 3) | (b >> 2))

        colours = [expand(struct.unpack_from("<H", header, 0x18 + i * 2)[0]) for i in range(16)]
        sheet = Image.new("RGB", (CELLS * 8, 20 * len(messages)), (0, 0, 0))
        px = sheet.load()
        for n, (x, y, cells) in enumerate(messages):
            for c, gi in enumerate(cells):
                g = glyphs[gi]
                for half in range(2):
                    for row in range(8):
                        for col in range(0, 8, 2):
                            b = g[half * 0x20 + row * 4 + col // 2]
                            px[c * 8 + col, n * 20 + half * 8 + row] = colours[b & 0xF]
                            px[c * 8 + col + 1, n * 20 + half * 8 + row] = colours[b >> 4]
        sheet.resize((CELLS * 16, 40 * len(messages))).save(args.sheet)
        print("sheet -> %s" % args.sheet)
    return 0


if __name__ == "__main__":
    sys.exit(main())
