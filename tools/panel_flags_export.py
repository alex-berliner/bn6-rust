#!/usr/bin/env python3
"""Export the per-panel-type flag words (T121b, step 1).

The table lives at ROM address 0x081D7E24 (`word_3007924`'s ROM source, an
IWRAM copy at 0x3007924 -- word_3007924 is in no map line; the address is
derived from the copy routine instead: reference/bn6f/asm/start.s copies
IWRAMRoutinesROMLocation = 0x081d6000 (bn6f.map:34342) to 0x3005B00,
size 0x1ed4, so 0x3007924 - 0x3005B00 = 0x1e24 and
0x081d6000 + 0x1e24 = 0x081D7E24, inside the copy): 13 words, stride 4,
one per panel type 0x0..0xC,
OR-ed into `oPanelData_Flags` (+0x14) by `_object_updatePanelParameters`
(asm/asm38.s:4213-4219: `lsl r2,r1,#2; ldr r3,[r3,r2]; orr r1,r3`).
The alliance bit is OR'd separately by the same routine
(`ldrb [Alliance]; lsl #5; orr` -- asm38.s:4220-4223), so it is NOT in
these words; the 0x20 "enemy panel" bit of PanelData.inc comes from there.

Bytes come from the ROM file itself: reference/bn6f/bn6f.gba at file offset
0x1D7E24 (== address - 0x08000000); /tmp/bn6f_real.gba is byte-identical
(cmp, 2026-09-18). The asset this writes is the RAW 52 bytes, little-endian,
one u32 per type in type order -- every consumer indexes it by type; no
triple is ever hand-written in src/.

Bit names: include/structs/PanelData.inc names only 0x2 (blocks movement),
0x20 (enemy panel) and the 0x00800000.. support/attack group -- none of
which appear in this table. Each remaining bit is named after the only type
whose table word sets it (derived from the ROM bytes below); the two bits
present in many types keep `unnamed:` comments.
"""

import struct
import sys

ROM_PATHS = ("/tmp/bn6f_real.gba", "reference/bn6f/bn6f.gba")
# canon: word_3007924 -- the table's ROM source address, derived from the copy
# routine (start.s: IWRAMRoutinesROMLocation 0x081d6000 -> 0x3005B00, 0x1ed4;
# 0x3007924 - 0x3005B00 = 0x1e24; 0x081d6000 + 0x1e24 = 0x081D7E24)
TABLE_ADDR = 0x081D7E24
TYPES = 13

# Bits named by the only type whose word sets them. Provenance for each is
# the table word itself (derived -- ROM bytes at TABLE_ADDR + type*4).
NAMED_BITS = {
    0x0040: "CRACKED",   # type 3 word only
    0x0100: "POISON",    # type 4
    0x0200: "UNK_9C",    # types 9..0xC (the setter's Unk_12=0x708 group)
    0x0400: "GRASS",     # type 6
    0x0800: "ICE",       # type 7
    0x1000: "TYPE8",     # type 8 (T115: writer exists, effect unnamed)
    0x2000: "HOLY",      # type 5
    0x4000: "BROKEN",    # type 1
    0x8000: "HOLE",      # type 0
}


def load_table():
    rom = open(ROM_PATHS[0], "rb").read()
    off = TABLE_ADDR - 0x08000000
    return [struct.unpack_from("<I", rom, off + t * 4)[0] for t in range(TYPES)]


def decode(word):
    return [NAMED_BITS[b] if b in NAMED_BITS else "0x%x" % b
            for b in (1 << i for i in range(32)) if word & b]


def main(out_path="assets/panels.bin"):
    words = load_table()
    for t, w in enumerate(words):
        names = decode(w)
        unnamed = [n for n in names if n.startswith("0x")]
        print("type 0x%01X  @0x%08X  word 0x%08X  bits: %s%s"
              % (t, TABLE_ADDR + t * 4, w,
                 ",".join(n for n in names if not n.startswith("0x")) or "-",
                 "  unnamed:%s" % ",".join(unnamed) if unnamed else ""))
    common = words[2] & 0x7FFFFFFF
    for t, w in enumerate(words):
        assert (w & 0x10) == (common & 0x10) or t < 2
    data = b"".join(struct.pack("<I", w) for w in words)
    if out_path:
        open(out_path, "wb").write(data)
        print("wrote %s (%d bytes)" % (out_path, len(data)))


if __name__ == "__main__":
    main(*sys.argv[1:])
