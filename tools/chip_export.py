"""Export battle chip data and card art for the ROM.

usage: python3 chip_export.py <out.bin>

Chips are the 411 chip_data_struct records of ChipDataArr_8021DA8
(data/ChipDataArr.s), one per chip id in order (id 0 is MegaBstr, id 1
Cannon). The struct layout is in include/rom_structs/ChipData.inc: codes
u32 at +0 (four code bytes, little endian; 0x00='A' .. 0x19='Z', 0x1a='*',
0xff = no code), chip_element u8 at +6, mb u8 at +8, attack_power u16 at
+0x1a, chip_icon_ptr +0x20, chip_image_ptr +0x24, chip_palette_ptr +0x28.
Chip names come from data/textscript/TextScriptChipNames0.s:
def_text_script TextScriptChipNames0_unkN names chip id N, the string ends
in '@'. The battle chip select (the patched BNCW window) renders the
cards: the selected chip's renderer sub_80284E2 (dispatched by
sub_8028476, asm/asm03_0.s:4316) copies the image [chip+0x24] -- 0x540
bytes, the raw 4bpp 7x6-tile card picture, to VRAM 0x6009560
(asm03_0.s:4399-4404) -- and the chip palette [chip+0x28] (chip_palette_ptr,
32 bytes) to the palette staging slot unk_3001AA0 (asm03_0.s:4405-4409).
The per-slot 16x16 icons are copied by sub_80281D4/sub_80281E4
(asm03_0.s:3931-3969): 0x80 bytes from chip_icon_ptr ([chip+0x20],
asm03_0.s:3922-3925), which for every chip here is byte_8725894 + id*0x80
(data/dat38_86.s:22229); those functions load no palette of their own, so
the icons take their colours from the same per-chip chip_palette_ptr the
card renderer stages (a palette per chip, not one shared icon palette).
Image blocks are one 0x540 block per distinct chip_image_ptr symbol in
data/dat38_86.s; the length below is the byte distance to the next
distinct image symbol (constant 0x540, raw 4bpp -- no LZ77 0x10 header),
which matches the fixed 0x540 transfer in sub_80284E2. Chip families
share an image block (Cannon and HiCannon share byte_86F60F4) but keep
their own palette and icon, so image blobs are stored once.

The 13 chips below are looked up by name in TextScriptChipNames0. The
ROM's display names are at most 8 letters, so three requested names are
aliased to the table's spellings: WideSwd -> WideSwrd (id 72), LongSwd ->
LongSwrd (id 73), Invis -> Invisibl (id 177). ShotGun, CrossGun and
Spreader are not in bn6f's names at all and are skipped (the spreader
family there is Spreadr1..3).

Format (little-endian):
  0x00  magic "BNCH"
  0x04  u32 version (2; v2 appends a behavioural tail, below)
  0x08  u32 chip count, then a table of count * 36-byte records:
          u16 chip id; u8 element (chip_element); u8 mb; u16 attack_power;
          u8[4] codes; char[9] name ('@' stripped, NUL padded);
          u8 reserved; u32 -> icon (0x80 bytes, 16x16 4bpp);
          u32 -> image (image_len bytes, 7x6 8x8-tile 4bpp = 56x48);
          u32 image_len; u32 -> palette (32 bytes, 16 BGR555)
  then the blobs, each 4-aligned after the table; shared image blobs are
  stored once and referenced by several records
  then the v2 behavioural tail, count * 8 bytes appended after the blobs
  (v2 is byte-append-only: every v1 byte, including each record's pointer
  fields, is unchanged; the tail's record stride is 8):
          u8 effect_flags; u8 attack_family; u8 attack_subfamily;
          u8 attack_param_1..4; u8 lockout_frames
          (ChipDataArr_8021DA8 offsets +0x9, +0xb, +0xc, +0x10..+0x13,
          +0x14; include/rom_structs/ChipData.inc)
"""

import os
import re
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bnasm import read_symbol

BN6 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "reference", "bn6f")
DAT = os.path.join(BN6, "data", "dat38_86.s")
ARR = os.path.join(BN6, "data", "ChipDataArr.s")
NAMES = os.path.join(BN6, "data", "textscript", "TextScriptChipNames0.s")

# Requested chips, with the ROM's 8-char display names where they differ.
CHIPS = [
    "Cannon", "HiCannon", "M-Cannon", "AirShot", "Vulcan1", "Sword",
    "WideSwd", "LongSwd", "MiniBomb", "Recov10", "Recov30",
    "Barrier", "AreaGrab", "Invis",
    # Siblings of families that are already matched, to test that the
    # implementations generalise: the Vulcans differ only in shot count
    # (dword_80EBFEC), the Recovs only in the amount (byte_80EC870).
    "Vulcan2", "Vulcan3", "Recov50", "Recov80", "Recov120",
    "FireSwrd", "AquaSwrd", "ElecSwrd", "BambSwrd",
    "BlkBomb", "BigBomb",
    "WideBlde", "LongBlde", "Recov150", "Recov200", "Recov300",
    "SuprVulc", "Muramasa", "StepSwrd",
    "Barr100", "Barr200", "EnergBom", "MegEnBom",
    "LilBolr1", "LilBolr2", "LilBolr3",
    "FlshBom1", "FlshBom2", "FlshBom3",
    "PoisSeed", "IceSeed", "GrasSeed", "BugBomb", "VDoll",
]
# The reachability gates (T116, docs/coverage/chips.md), measured from the
# ROM: an id is folder-reachable when
#   id < 0x19B (411) -- the folder/hand validation's own cap
#     (tooManyGigasMegasAntiCheatHappensHere_800B022, asm/asm00_1.s:17513,
#     dword_800B104 = 0x19b),
#   the record has at least one code -- a folder item is an (id, code) pair
#     and the pack quantity lookup matches the code against the record's
#     four code bytes (getOffsetToQuantityOfChipCodeMaybe_8021c7c,
#     asm/asm03_0.s:305-333); exactly one named id (MegaBstr, id 0) has none,
#   and a display name exists -- TextScriptChipNames0.s carries 238 strings
#     indexed by chip id (ids 0..237); ids 238..410 render no name.
REACHABLE_MAX_ID = 256  # provenance: derived -- TextScriptChipNames0.s holds 256 def_text_script blocks (ids 0..255)


def reachable_ids(chips, names):
    """The folder-reachable chip ids (T116): a def-number-keyed name (so ids
    203..220, which carry no .string, drop out), plus the gates above.
    Returns ids 1..202 + 221..255 -- 220 ids. See the gate block above."""
    out = []
    for cid, c in enumerate(chips):
        if not 0 < cid < REACHABLE_MAX_ID:
            continue
        if cid not in names:  # no name string -> never renders in pack/library
            continue
        if int(c["codes"], 0) == 0xFFFFFFFF:  # no code: can never match a folder item
            continue
        if int(c["library_num"], 0) == 0:  # unnamed placeholder rows
            continue
        out.append(cid)
    return out


ALIASES = {}  # (T116: unused -- the reachable set is derived by id, not by name)
ICON_BASE = 0x8725894  # data/dat38_86.s:22229; sub_80281E4 indexes id*0x80
FIELD = re.compile(r"\s*(\w+):\s*((?:0x[0-9A-Fa-f]+)|(?:[A-Za-z_]\w*)),?")


def chip_data():
    """The 411 ChipDataArr records in order; index i is chip id i."""
    chips = []
    cur = None
    for lineno, line in enumerate(open(ARR), 1):
        if "chip_data_struct [" in line:
            cur = {"line": lineno}
            chips.append(cur)
            continue
        if cur is None:
            continue
        m = FIELD.match(line)
        if m and m.group(1) in (
            "codes", "chip_element", "mb", "attack_power",
            "effect_flags", "attack_family", "attack_subfamily",
            "attack_param_1", "attack_param_2", "attack_param_3",
            "attack_param_4", "lockout_frames", "library_num",
            "chip_icon_ptr", "chip_image_ptr", "chip_palette_ptr",
        ):
            cur[m.group(1)] = m.group(2)
    assert len(chips) == 411, len(chips)
    for c in chips:
        for k in ("codes", "chip_element", "mb", "attack_power",
                  "effect_flags", "attack_family", "attack_subfamily",
                  "attack_param_1", "attack_param_2", "attack_param_3",
                  "attack_param_4", "lockout_frames", "library_num",
                  "chip_icon_ptr", "chip_image_ptr", "chip_palette_ptr"):
            assert k in c, (chips.index(c), k)
    return chips


def chip_names():
    """Chip id -> display name ('@' stripped)."""
    names = {}
    cur = None
    for line in open(NAMES):
        m = re.match(r"\s*def_text_script TextScriptChipNames0_unk(\d+)", line)
        if m:
            cur = int(m.group(1))
            continue
        if cur is None:
            continue
        m = re.search(r'\.string "([^"]*)"', line)
        if m:
            names[cur] = m.group(1)[:-1]
            cur = None
    return names


def chip_name_lines():
    """Chip id -> line of its def_text_script in TextScriptChipNames0.s."""
    out = {}
    for n, line in enumerate(open(NAMES), 1):
        m = re.match(r"\s*def_text_script TextScriptChipNames0_unk(\d+)", line)
        if m:
            out[int(m.group(1))] = n
    return out


def label_offsets(path):
    """Symbol name -> byte offset in the file's data, walking every line."""
    pos = 0
    out = {}
    collecting = None
    for line in open(path):
        m = re.match(r"^([A-Za-z_][A-Za-z_0-9]*)::", line)
        if m:
            out[m.group(1)] = pos
            continue
        m = re.match(r"^\s*\.(byte|hword|short|word|space)\s+(.*)$", line)
        if not m:
            continue
        kind, rest = m.group(1), m.group(2)
        vals = []
        for part in rest.split("//")[0].split(","):
            part = part.strip()
            if part:
                vals.append(int(part, 0))
        if kind == "space":
            pos += vals[0]
        else:
            pos += len(vals) * (1 if kind == "byte" else 2 if kind in ("hword", "short") else 4)
    return out


# Since T116 the export is the REACHABLE SET (ids 1..237, the gates and
# cites in reachable_ids below) instead of a hand list: the three-way census
# (docs/coverage/chips.md) showed the gap list was bounded -- 189 reachable
# ids missing from the old 48-record asset, 5 in-asset ids unverified, 174
# table rows reachable by neither gate.


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "chips.bin"
    chips = chip_data()
    names = chip_names()
    offs = label_offsets(DAT)

    # Every distinct image symbol the ChipData references, positioned in the
    # file; a chip's image length is the gap to the next one.
    image_pos = {}
    for c in chips:
        sym = c["chip_image_ptr"]
        if sym in offs:
            image_pos[sym] = offs[sym]
    order = sorted(image_pos, key=image_pos.get)

    # T116 step 4: the reachable set replaces the hand list.
    wanted = reachable_ids(chips, names)
    nlines = chip_name_lines()

    def resolve(sym):
        """Bytes a symbol names; fall back to an address inside a labelled blob."""
        if sym in offs:
            return read_symbol(DAT, sym, through_labels=True)
        addr = int(sym, 0)
        before = [s for s in offs if int(s, 0) <= addr]
        after = [s for s in offs if int(s, 0) >= addr]
        if not before or not after:
            raise ValueError(f"{sym}: cannot locate in {DAT}")
        if int(before[-1], 0) == addr:
            return read_symbol(DAT, before[-1], through_labels=True)
        start = offs[before[-1]]
        end = min(o for s, o in offs.items() if int(s, 0) >= addr)
        return read_symbol(DAT, before[-1], max_bytes=addr - int(before[-1], 0) + end - addr,
                           through_labels=True)[addr - int(before[-1], 0):]

    recs = []
    for cid in wanted:
        c = chips[cid]
        name = names[cid]
        icon = c["chip_icon_ptr"]
        pal = c["chip_palette_ptr"]
        img = c["chip_image_ptr"]
        # T116: the icon assert is relaxed to "any labelled icon blob": 45
        # reachable ids share icon blobs or use dword_/unk_ icon labels
        # (ElcPuls1-3, the Navi ids 203..237, ...), not byte_8725894 + id*0x80.
        assert icon in offs, (name, cid, icon)
        codes = struct.pack("<I", int(c["codes"], 0))
        icon_blob = resolve(icon)
        pal_blob = resolve(pal)
        img_off = image_pos[img]
        i = order.index(img)
        img_len = image_pos[order[i + 1]] - img_off if i + 1 < len(order) else None
        img_blob = resolve(img) if img_len is None else read_symbol(
            DAT, img, max_bytes=img_len, through_labels=True)
        assert len(icon_blob) >= 0x80 and len(pal_blob) >= 0x20
        assert img_blob[0] != 0x10, f"{name}: image starts with an LZ77 header"
        recs.append(dict(
            id=cid, line=c["line"], name=name[:8], full_name=name, element=int(c["chip_element"], 0), mb=int(c["mb"], 0),
            power=int(c["attack_power"], 0), codes=codes,
            effect_flags=int(c["effect_flags"], 0),
            family=int(c["attack_family"], 0), subfamily=int(c["attack_subfamily"], 0),
            params=[int(c["attack_param_%d" % n], 0) for n in (1, 2, 3, 4)],
            lockout=int(c["lockout_frames"], 0),
            icon=(icon, icon_blob[:0x80]), pal=(pal, pal_blob[:0x20]),
            img=(img, img_blob, img_len)))

    # 36-byte records as in v1 (append-only: the v2 behavioural tail is a
    # separate section after the blobs, so every v1 byte and every stored
    # blob offset is unchanged), then the tail: per record u8 effect_flags,
    # attack_family, attack_subfamily, attack_param_1..4, lockout_frames.
    out = bytearray(struct.pack("<4sII", b"BNCH", 2, len(recs)))
    for r in recs:
        out += (struct.pack("<HBBH4s", r["id"], r["element"], r["mb"], r["power"], r["codes"])
                + r["name"].encode() + b"\0" * (9 - len(r["name"])) + b"\0" + b"\0" * 16)
    blobs = {}
    for i, r in enumerate(recs):
        base = 12 + i * 36
        for kind, slot in (("icon", 20), ("pal", 32)):
            key = (kind, r[kind][0])
            if key not in blobs:
                while len(out) % 4:
                    out.append(0)
                blobs[key] = len(out)
                out += r[kind][1]
            struct.pack_into("<I", out, base + slot, blobs[key])
        key = ("img", r["img"][0])
        if key not in blobs:
            while len(out) % 4:
                out.append(0)
            blobs[key] = len(out)
            out += r["img"][1]
        struct.pack_into("<II", out, base + 24, blobs[key], len(r["img"][1]))

    # The v2 behavioural tail, after every blob: 8 bytes per record in
    # record order.
    for r in recs:
        out += bytes([r["effect_flags"], r["family"], r["subfamily"]]
                     + r["params"] + [r["lockout"]])

    with open(out_path, "wb") as f:
        f.write(out)

    # Report the art findings: every chip image referenced anywhere in the
    # ChipData is a label in data/dat38_86.s, laid out back to back; each
    # block in the export is 0x540 and none starts with an LZ77 0x10 header.
    lengths = {}
    for a, b in zip(order, order[1:]):
        lengths.setdefault(image_pos[b] - image_pos[a], []).append((a, b))
    # Whole-tile blocks: 0x540 for every standard card, but the Navi ids'
    # card art blocks are contiguous multiples of 0x540 (0xA80 x2, 0x1A40 x1
    # -- docs/coverage/chips.md); the record stores the real length and
    # src/chips.rs reads by the stored length, so a bigger blob is data-safe.
    assert all(len(r["img"][1]) % 0x540 == 0 and len(r["img"][1]) > 0 for r in recs)
    print(f"{out_path}: {len(out)} bytes, {len(recs)} chips")
    print(f"image blocks: {len(order)} distinct over all {len(chips)} chips; "
          f"gaps {sorted(lengths)} (outliers: "
          + "; ".join(f"{a}->{b}" for g in lengths for a, b in lengths[g] if g != 0x540)
          + ")")
    for r in recs:
        print(f"  {r['id']:3d} {r['name']:<10} el={r['element']:02x} mb={r['mb']:2d} "
              f"pw={r['power']:3d} codes={' '.join('%02x' % b for b in r['codes'])} "
              f"eff={r['effect_flags']:02x} fam={r['family']:02x} sub={r['subfamily']:02x} "
              f"p={r['params']} lo={r['lockout']} "
              f"icon={r['icon'][0]} img={r['img'][0]}({len(r['img'][1])}) pal={r['pal'][0]}")
    # T116's per-id cite: table line + name string line per exported record
    # (asset index is the record's position in this printed list).
    for i, r in enumerate(recs):
        print(f"  cite id {r['id']}: data/ChipDataArr.s:{r['line']} "
              f"asset idx {i} "
              f"data/textscript/TextScriptChipNames0.s:{nlines[r['id']]}")
    truncated = [(r['id'], r['full_name']) for r in recs if r['full_name'] != r['name']]
    if truncated:
        print("NAMES TRUNCATED to the BNCH char[9] field (the .s line stays the "
              "cite; no src arm dispatches on names): "
              + ", ".join(f"{i} '{n}'" for i, n in truncated))


if __name__ == "__main__":
    main()
