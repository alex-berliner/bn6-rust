"""Export the emotion window: the navi's face at the top left of the battle.

usage: python3 emotion_export.py <out.bin>

The real ROM draws it as two objects, not tiles: a 32x16 at (0,18) and a 16x16
at (32,18), both in OBJ palette bank 12, read straight out of the sterile
arena's OAM on a paused battle frame (objects 2 and 3, VRAM tiles 0x3b4 and
0x3bc). That is why it survives the field being stripped and shows in every
chip capture, above the compared window.

T105: the FULL bank now, not just the calm face. The per-emotion pointer table
off_801CD08 (asm00_2.s:27580-27603, 23 words) picks each face's left half; the
upload routine sub_801CB38 (asm00_2.s:27332-27464) queues `table[face]` for
0x100 bytes to VRAM 0x06017680 (asm00_2.s:27408-27416), the SHARED right half
dword_872D914 for 0x80 bytes to 0x06017780 (asm00_2.s:27418-27423), and then a
PER-FACE palette: `lsl r0,r4,#5` over dword_872F114, 0x20 bytes (asm00_2.s:
27449-27452) -- one 16-colour palette per emotion, not one shared. The bank
itself is dword_872D814..dword_872F114 (0x1900 bytes): slots 0..14 at 0x180
strides with 5/6 compressed to 0x100 (the draw gate skips values 5 and 6,
asm00_2.s:27648-27652), values 15..19 aliasing 5..9 and 21 aliasing 20 in the
table itself, the idle-blink right-half frames at +0x1180 (dword_872E994,
uploaded by sub_801CB38's blink branch, unused by this build), and slots
20/22 at the tail. The bank is exported VERBATIM at canon offsets so the
rust side's face offsets are the table's own deltas.

Format (little-endian):
  0x00  magic "BNEM"
  0x04  u32 version = 2
  0x08  u32 -> bank    : u32 byte_len (0x1900), then the bank verbatim at
                          canon offsets from dword_872D814
  0x0c  u32 -> palettes: u32 byte_len (0x2e0 = 23 * 32), then face v's
                          palette at v*32
"""

import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bnasm import read_symbol

#: The asm listing's code-side labels carry ONE colon (`off_801CD08:`), unlike
#: the data files' `sym::` that bnasm.read_symbol matches, so the pointer table
#: is parsed here instead of through read_symbol.
_ASM_LABEL = re.compile(r"^([A-Za-z_][A-Za-z_0-9]*):\s*(?://.*)?$")


def _word_value(text: str) -> int:
    """A .word operand: a number, or a data-label name whose address is its
    suffix (the disassembly's own convention, dword_872D814 et al)."""
    text = text.strip()
    m = re.match(r"^(?:dword|hword|byte|off|unk)_([0-9A-Fa-f]{6,8})$", text)
    if m:
        return int(m.group(1), 16)
    return int(text, 0)


def read_asm_words(path: str, symbol: str, count: int) -> bytes:
    """`count` .word values under a single-colon asm-listing label."""
    out, collecting = bytearray(), False
    with open(path) as f:
        for line in f:
            m = _ASM_LABEL.match(line)
            if m:
                if collecting:
                    break
                collecting = m.group(1) == symbol
                continue
            if not collecting:
                continue
            d = re.match(r"^\s*\.word\s+(.*)$", line)
            if not d:
                continue
            for v in d.group(1).split("//")[0].split(","):
                if v.strip():
                    out += struct.pack("<I", _word_value(v) & 0xFFFFFFFF)
            if len(out) >= count * 4:
                break
    return bytes(out[: count * 4])

BN6 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "reference", "bn6f")
DAT = os.path.join(BN6, "data", "dat38_86.s")
ASM = os.path.join(BN6, "asm", "asm00_2.s")
TABLE = "off_801CD08"      # 23 pointer words, asm00_2.s:27580-27603
BANK = "dword_872D814"     # bank start, data/dat38_86.s:26158
SHARED_RIGHT = "dword_872D914"  # the 16x16 object's four tiles, every face's
PALETTES = "dword_872F114" # 23 per-face palettes, data/dat38_86.s:26556
FACE_COUNT = 23
BANK_LEN = 0x1900          # dword_872D814 .. dword_872F114 (the palettes follow)
PAL_LEN = 0x2E0            # dword_872F114 .. byte_872F3F4 (dat38_86.s:26594)


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "emotion.bin"

    table = read_asm_words(ASM, TABLE, FACE_COUNT)
    if len(table) != FACE_COUNT * 4:
        raise SystemExit(f"{TABLE}: expected {FACE_COUNT * 4} bytes, got {len(table)}")
    ptrs = struct.unpack("<%dI" % FACE_COUNT, table)
    base = ptrs[0]
    for i, p in enumerate(ptrs):
        if not base <= p <= base + BANK_LEN - 0x100:
            raise SystemExit(f"{TABLE}[{i}] = {p:#x}: outside the bank")
    for i in range(1, FACE_COUNT):
        if ptrs[i] == base + 0x100:
            raise SystemExit(f"{TABLE}[{i}] points at the shared right half")
    print("face offsets (off_801CD08[v] - dword_872D814):")
    print("[" + ", ".join(hex(p - base) for p in ptrs) + "]")

    bank = read_symbol(DAT, BANK, max_bytes=BANK_LEN, through_labels=True)
    if len(bank) != BANK_LEN:
        raise SystemExit(f"{BANK}: expected {BANK_LEN:#x} bytes, got {len(bank)}")
    right = read_symbol(DAT, SHARED_RIGHT, max_bytes=0x80, through_labels=True)
    if len(right) != 0x80:
        raise SystemExit(f"{SHARED_RIGHT}: expected 128 bytes, got {len(right)}")
    if bytes(bank[0x100:0x180]) != bytes(right):
        raise SystemExit("bank +0x100 is not dword_872D914's bytes")
    palettes = read_symbol(DAT, PALETTES, max_bytes=PAL_LEN, through_labels=True)
    if len(palettes) != PAL_LEN:
        raise SystemExit(f"{PALETTES}: expected {PAL_LEN:#x} bytes, got {len(palettes)}")

    out = bytearray(struct.pack("<4sIII", b"BNEM", 2, 0, 0))
    off_bank = len(out)
    out += struct.pack("<I", len(bank)) + bank
    off_pal = len(out)
    out += struct.pack("<I", len(palettes)) + palettes
    struct.pack_into("<4sIII", out, 0, b"BNEM", 2, off_bank, off_pal)
    with open(out_path, "wb") as f:
        f.write(out)
    print(f"{out_path}: {len(out)} bytes "
          f"(bank {BANK_LEN:#x}, palettes {PAL_LEN:#x}, {FACE_COUNT} faces)")


if __name__ == "__main__":
    main()
