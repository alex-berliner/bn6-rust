#!/usr/bin/env python3
"""T10: inventory of the battle engine out of bn6f's own tables.

Enumerates, each row with the ROM table symbol and file:line cite:
  chips, Program Advances, virus families/ranks, Navi bosses + Cybeasts,
  MegaMan's forms (TF enum + the per-transformation charge-shot table),
  panel effect routines, statuses, encounter formations + BattleSettings
  records, arena backdrops, NaviCust battle-relevant stat slots.

Category states (per the supervisor's T10 decision): FOUND (table symbol,
file:line, stride, count) / DERIVED-FROM-CODE (routine + per-item sites,
count = sites) / GAP (search trail named). A GAP is a result, not a failure.

Writes docs/inventory/<section>.json and regenerates the "## Per-item
tables" section of docs/SCOPE.md (everything above that marker is the
human's prose and is never touched). Prints the summary counts to stdout.

    python3 tools/inventory.py

Read-only on reference/bn6f. Enemy rows come from T12's tool (shelled out
to, never re-derived or edited): `python3 tools/rom_enemy_tables.py`.
"""

import ast
import json
import os
import re
import struct
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# reference/bn6f is a gitlink (mode 160000): in a fresh worktree it is an
# EMPTY directory. Resolve the disassembly root explicitly -- BN6F_REF env
# var, else the repo path -- and fail with instructions instead of a
# FileNotFoundError deep in a parse. The tool never creates the symlink and
# never touches reference/.
REF = os.environ.get("BN6F_REF") or os.path.join(REPO, "reference", "bn6f")
INV = os.path.join(REPO, "docs", "inventory")


def ensure_ref():
    probe = os.path.join(REF, "constants", "constants.inc")
    if not os.path.exists(probe):
        sys.exit(
            f"bn6f disassembly not found at {REF}\n"
            "  reference/bn6f is a gitlink and is EMPTY in a fresh worktree.\n"
            "  Either symlink it from a checkout that has it, e.g.\n"
            f"    ln -s /home/box/Code/bn/reference/bn6f {os.path.join(REPO, 'reference', 'bn6f')}\n"
            "  or point BN6F_REF at the disassembly root:\n"
            "    BN6F_REF=/home/box/Code/bn/reference/bn6f python3 tools/inventory.py")


# fail before the module-level enum/table parsing below touches the fs
ensure_ref()

# canon: data labels use two colons, code/local labels one
LABEL_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):{1,2}\s*(?://.*)?$")
BYTE_RE = re.compile(r"^\s*\.byte\s+(.+)$")
HWORD_RE = re.compile(r"^\s*\.hword\s+(.+)$")
WORD_RE = re.compile(r"^\s*\.word\s+(.+)$")
STRING_RE = re.compile(r"^\s*\.string\s+\"(.*)\"\s*$")
COMMENT_RE = re.compile(r"//.*$")


def read_lines(rel):
    with open(os.path.join(REF, rel), "r", errors="replace") as f:
        return f.readlines()


def strip_comment(ln):
    # strings may contain '@' and text; only // appears as a comment marker
    return re.sub(r"(?<!\")//.*$", "", ln).rstrip()


def parse_values(rest):
    out = []
    for tok in rest.split(","):
        tok = tok.strip()
        if not tok:
            continue
        if re.fullmatch(r"0[xX][0-9a-fA-F]+", tok):
            out.append(("v", int(tok, 16)))
        elif re.fullmatch(r"\d+", tok):
            out.append(("v", int(tok)))
        else:
            out.append(("s", tok))
    return out


def label_bounds(lines, label):
    """(start_idx0, next_label_or_None) for `label` in already-read lines."""
    start = None
    for i, ln in enumerate(lines):
        m = LABEL_RE.match(ln.rstrip("\n"))
        if m and m.group(1) == label:
            start = i
            break
    if start is None:
        return None, None
    for j in range(start + 1, len(lines)):
        m = LABEL_RE.match(lines[j].rstrip("\n"))
        if m:
            return start, j
    return start, len(lines)


def region_bytes(path, label):
    """Linear token stream of a label's region: [('b',v)|('w',v_or_name)|('h',v)]
    plus the 1-based line of each token's row (for cites)."""
    lines = read_lines(path)
    s, e = label_bounds(lines, label)
    if s is None:
        return []
    out = []
    for i in range(s + 1, e):
        raw = lines[i].rstrip("\n")
        ln = strip_comment(raw)
        for rx, tag in ((BYTE_RE, "b"), (HWORD_RE, "h"), (WORD_RE, "w")):
            m = rx.match(ln)
            if m:
                for kind, val in parse_values(m.group(1)):
                    out.append((tag, kind, val, i + 1))
                break
    return out


def find_symbol_line(rel, symbol):
    """First line (1-based) defining `symbol` (data label or thumb_func_start)."""
    for i, ln in enumerate(read_lines(rel), 1):
        if re.match(rf"^{re.escape(symbol)}::?", ln) or \
           f"thumb_func_start {symbol}" in ln:
            return i
    return None


def split_labels(path):
    """All labels of a file: [(name, line1based)]."""
    out = []
    for i, ln in enumerate(read_lines(path), 1):
        m = LABEL_RE.match(ln.rstrip("\n"))
        if m:
            out.append((m.group(1), i))
    return out


# ---------------------------------------------------------------- constants

def parse_enum_consts(rel, prefix):
    """enum NAME // value lines from constants/enums/<rel> or constants/."""
    out = []
    for i, ln in enumerate(read_lines(rel), 1):
        m = re.match(rf"\s*enum ({prefix}\w+)\s*//\s*(0x[0-9a-fA-F]+|\d+)", ln)
        if m:
            out.append({"name": m.group(1), "value": int(m.group(2), 0),
                        "cite": f"constants/{os.path.basename(rel)}:{i}"})
    return out


CHIP_ELEM = parse_enum_consts("constants/constants.inc", "CHIP_ELEM_")
TF_ENUM = parse_enum_consts("constants/constants.inc", "TF_")
NAVI_ENUM = parse_enum_consts("constants/constants.inc", "NAVI_")
ELEM_BY_VAL = {e["value"]: e["name"] for e in CHIP_ELEM}

# class names for the chip LibraryType nibble. Derived, not enum'd: the
# standard block (codes-bearing ids 0x01-0x13F) is 0; the 13-row band 0x02
# matches the Giga count; DarkChips are the contiguous 0x140-0x15D block
# (30 rows, library_type 4); 1 = mega; 3 = secret incl. the id-0 blank.
# provenance: derived -- from ChipDataArr's own arrangement
LIBRARY_TYPE_NAMES = {0: "standard", 1: "mega", 2: "giga", 3: "secret", 4: "dark"}


def decode_codes(u32):
    """Packed code field -> letters. Byte order + alphabet already
    established by our own tools/chip_export.py header (citing
    sub_8028E4C, asm03_0.s:5595): four bytes little-endian, 0x00='A' ..
    0x19='Z', 0x1a='*', 0xff = no code."""
    if u32 == 0xFFFFFFFF:
        return ""
    out = []
    for shift in (0, 8, 16, 24):
        c = (u32 >> shift) & 0xFF
        if c == 0xFF:
            continue
        out.append("*" if c == 0x1A else chr(ord("A") + c))
    return "".join(out)


# ------------------------------------------------------------------- chips

def chip_names():
    """Chip id -> display name, keyed by the def_text_script number
    (TextScriptChipNames0_unkN names chip id N). Corrected in T116: the file
    holds 256 defs (ids 0..255) but only 238 .string entries -- ids
    203..220 carry no string (placeholder rows, e.g. fam 0x14 sharing
    Cannon's image), so the previous order-of-appearance list shifted every
    name from id 203 on (its index 221 was 'ChrgeMan', the real def 221 is
    'Roll'). Index 0 is the 'MegaBstr' placeholder. Ids with no string map
    to "".
    """
    lines = read_lines("data/textscript/TextScriptChipNames0.s")
    by_id = {}
    cur = None
    for ln in lines:
        m = re.match(r"\s*def_text_script TextScriptChipNames0_unk(\d+)", strip_comment(ln))
        if m:
            cur = int(m.group(1))
            continue
        m = STRING_RE.match(strip_comment(ln))
        if m and cur is not None:
            by_id[cur] = m.group(1).split("@")[0]  # the '@' terminator and any padding after it are not the name (id 255 was 'DustMan[EX]@ ' under .rstrip("@"))
            cur = None
    return [by_id.get(i, "") for i in range(max(by_id) + 1)]


def chip_name_lines():
    """Chip id -> line of its def_text_script in TextScriptChipNames0.s
    (the def number IS the chip id; ids without a .string have no entry)."""
    out = {}
    for n, ln in enumerate(read_lines("data/textscript/TextScriptChipNames0.s"), 1):
        m = re.match(r"\s*def_text_script TextScriptChipNames0_unk(\d+)", ln)
        if m:
            out[int(m.group(1))] = n
    return out


def chip_asset_index():
    """Chip id -> record index in assets/chips.bin (BNCH v2: u32 count at 8,
    36-byte records, id u16 at 0 -- tools/chip_export.py's format)."""
    data = open(os.path.join(REPO, "assets", "chips.bin"), "rb").read()
    count = int.from_bytes(data[8:12], "little")
    return {int.from_bytes(data[12 + j * 36:14 + j * 36], "little"): j
            for j in range(count)}


# canon: ChipDataArr_8021DA8's AttackFamily (+0xb) -- the sword/blade family
# the landed T17 arm (src/battle.rs SWORD_FAMILY) dispatches on FROM THE
# RECORD ITSELF, not from ported per-chip code. A pixel-verified chip whose
# record carries one of these families is therefore "as data": its
# behaviour in our build is the ROM's own table row, not hand-ported logic.
# Derived from the ROM table (no per-chip list): ChipDataArr.s's
# attack_family field, intersected with the pixel-scoreboard ids.
# T57 43-row audit (docs/worklog/T57.md): the families whose EVERY
# pixel-verified id's behaviour src/battle.rs dispatches through the
# record, not through a `match chip.id` arm. Per family:
#   0x13 sword/blade -- all ten verified ids (71-79, 85) are consumed at
#     src/battle.rs:4391 (`chip.family == SWORD_FAMILY`, hit shape from
#     SWORD_HIT_SHAPE indexed by the record's AttackSubFamily); the one
#     byte this family still keys by id is the use_chip ENTRY arm
#     src/battle.rs:4144 (`CHIP_SWORD | ... | CHIP_BAMBSWRD`), common to
#     all swords and not behaviour-selecting. Stays in.
#   0x21 AirShot -- id 4 read at src/battle.rs:4128 and :4468, both
#     `chip.family == AIRSHOT_FAMILY`. Stays in.
#   0x15 Barrier family -- RE-ADMITTED (T61): the two id gates T57 found
#     (AreaGrab 163 and Invisibl 177 consumed by `match chip.id`) are gone;
#     every dispatch for the family now keys on the record -- attack_family
#     0x15 (ChipDataArr.s:5065/:5499/:5530/:5561/:5592) AND the record's
#     AttackSubFamily (0x00 AreaGrab :5066, 0x01 Invisibl :5500, 0x04
#     Barriers :5531/:5562/:5593). Invisibl's timer reads the record's
#     AttackParam1 (:5504, 0x68); the barriers' HP/palette already read
#     AttackParam1 via barrier_hp/barrier_palette. The AreaGrab
#     presentation quartet (77/47/4/3) has no record byte and stays
#     fitted/peeked, but it times one behaviour arm -- it does not SELECT
#     between behaviours, and the sword precedent (peeked timing consts
#     under 0x13) keeps that from blocking as-data status. The record
#     table itself carries two further 0x15/0x04 blocks (ids 181/182,
#     ChipDataArr.s:5623/:5654) beyond the 48-record asset; the game only
#     ever sees the asset, whose 0x15 records are exactly
#     {163(0x00), 177(0x01), 178/179/180(0x04)}.
AS_DATA_FAMILIES = {0x13, 0x15, 0x21}  # canon: T57 per-id audit; 0x15 re-admitted by T61; see block comment above


def parse_chips():
    txt = "".join(read_lines("data/ChipDataArr.s"))
    blocks = []
    # split on struct blocks, tracking the line of each block header
    for m in re.finditer(r"chip_data_struct \[(.*?)\]", txt, re.S):
        line = txt[: m.start()].count("\n") + 1
        fields = dict(re.findall(r"(\w+):\s*(0x[0-9a-fA-F]+|\w+),", m.group(1)))
        blocks.append((line, fields))
    names = chip_names()
    verified_ids = set(verified_chip_ids())
    asset_idx = chip_asset_index()
    nlines = chip_name_lines()
    rows = []
    for i, (line, f) in enumerate(blocks):
        codes = int(f["codes"], 16)
        libtype = int(f["library_type"], 16)
        libnum = int(f["library_num"], 16)
        elem = int(f["chip_element"], 16)
        name = names[i] if 0 < i < len(names) else ""
        # T116's reachable gate (cites in docs/coverage/chips.md): id < 0x19B
        # (folder validation, asm/asm00_1.s:17513), >=1 code (the pack matches
        # the item code against the record's code bytes,
        # getOffsetToQuantityOfChipCodeMaybe_8021c7c, asm/asm02.s:305-333),
        # and a name string (TextScriptChipNames0.s; ids 203..220 and 256..410
        # have none). R = 237: ids 1..202 + 221..255.
        reachable = (0 < i < 256 and name != ""
                     and codes != 0xFFFFFFFF and libnum != 0)
        # "verified" (trace + pixel parity AS DATA) beats "verified-pixels"
        # (pixel-verified through our own code): the eleven sword/blade
        # chips crossed over in T19 when the strike started dispatching on
        # the record's AttackFamily through the ROM's own tables.
        status = ("verified" if i in verified_ids
                  and int(f["attack_family"], 16) in AS_DATA_FAMILIES
                  else "verified-pixels" if i in verified_ids
                  else "unrecorded")
        rows.append({
            "id": i,
            "name": name,
            "codes": f"{codes:08x}",
            "codes_decoded": decode_codes(codes),
            "class_raw": libtype,
            "class": LIBRARY_TYPE_NAMES.get(libtype, f"library_type_{libtype}"),
            "element": ELEM_BY_VAL.get(elem, f"elem_{elem:02x}"),
            "damage": int(f["attack_power"], 16),
            "mb": int(f["mb"], 16),
            "cite": (f"data/ChipDataArr.s:{line}"
                     + ("" if not reachable else
                        (f"; asset idx {asset_idx[i]}" if i in asset_idx
                         else "; not in the shipped 48-record asset")
                        + f"; name "
                          f"data/textscript/TextScriptChipNames0.s:{nlines[i]}")),
            "reachable": reachable,
            "status": status,
        })
    return rows


def verified_chip_ids():
    """The 43 chip ids of the pixel-scoreboard rows (tools/scoreboard.py CHIPS:
    ('demo-<name>', '<hex id>', frames, extras))."""
    src = open(os.path.join(REPO, "tools", "scoreboard.py")).read()
    m = re.search(r"^CHIPS = (\[.*?\n\])", src, re.S | re.M)
    # entries may name the POPUP extras constant; a placeholder is fine, we
    # only need (feature, hex id) from each tuple
    literal = re.sub(r"\bPOPUP\b", "None", m.group(1))
    chips = ast.literal_eval(literal)
    assert len(chips) == 43, len(chips)
    return [int(hexid, 16) for _, hexid, _, _ in chips]


# -------------------------------------------------------- Program Advances

PA_FILE = "asm/asm03_0.s"
PA_TABLES = [
    # canon: off_802BCB0 (walked by sub_8029520, asm03_0.s:6631)
    # T14: renamed from off_802BCB0 (renames.md:214)
    {"symbol": "PARecipePtrsA_802BCB0", "line_hint": "PARecipePtrsA_802BCB0:", "list": "recognition list (sub_8029520)"},
    # canon: off_802BC60 -- T14: renamed (renames.md:214)
    {"symbol": "PARecipePtrsB_802BC60", "line_hint": "PARecipePtrsB_802BC60:", "list": "second list"},
]


def parse_program_advances():
    lines = read_lines(PA_FILE)
    rows = []
    for table in PA_TABLES:
        s, e = label_bounds(lines, table["symbol"])
        if s is None:
            continue
        tline = s + 1
        nptr = 0
        words_seen = 0
        terminator = None
        for i in range(s + 1, e):
            m = WORD_RE.match(strip_comment(lines[i]))
            if not m:
                continue
            tok = m.group(1).strip()
            words_seen += 1
            if tok in ("0xFF", "0x0", "NULL"):
                terminator = f".word {tok} ({PA_FILE}:{i + 1})"
                break
            rec_label = tok
            rec = region_bytes(PA_FILE, rec_label)
            vals = [v for t, k, v, _ in rec if t in ("b", "h", "w") and k == "v"]
            if not vals:
                continue
            count, matcher = vals[0], vals[1]
            result = vals[2] | (vals[3] << 8) if len(vals) > 3 else 0
            # record shape: [count][matcher][result u16] then either a
            # (chip,code) pair per ingredient (matcher-4, 10-byte records like
            # byte_802BA60) or a trailing u16 (matcher-0, 6-byte records like
            # byte_802BAE4: [3][0][result][?]). The matcher byte's semantics
            # live in off_80295C0's two routines (sub_80295C8/sub_802961A);
            # only the exact-shape ingredient decode is claimed here.
            ings = None
            if len(vals) == 4 + 2 * count:
                ings = [(vals[4 + 2 * j], vals[5 + 2 * j]) for j in range(count)]
            rl = rec[0][3] if rec else None
            rows.append({
                "list": table["symbol"],
                "count": count,
                "matcher_raw": matcher,
                "result_chip": result,
                "result_name": pa_result_name(result, lines),
                "ingredients": [f"{c:02x}/{code:02x}" for c, code in ings] if ings else [],
                "raw_bytes": " ".join(f"{v:02x}" for v in vals),
                "cite": f"{PA_FILE}:{tline} + {rec_label} {PA_FILE}:{rl}",
                "status": "unrecorded",
            })
            nptr += 1
        table["pointer_words"] = words_seen
        table["records"] = nptr
        table["terminator"] = terminator
    return rows


def pa_result_name(chip_id, lines):
    names = chip_names()
    return names[chip_id] if 0 < chip_id < len(names) else ""


# ----------------------------------------------------------------- viruses

def parse_viruses():
    """Enemy rows come from T12's tool (never re-derived here)."""
    proc = subprocess.run(
        [sys.executable, os.path.join(REPO, "tools", "rom_enemy_tables.py")],
        capture_output=True, text=True, check=True)
    data = json.loads(proc.stdout)
    rows = data["rows"]
    # virus family/rank table: group the identity rows by AIIndex; each
    # identity row (enemy_idx) is a rank, its version byte keys the Struct2
    # row (elem_hp u16 @0x00, first row of a row-per-level struct -- the
    # high nibble is the ELEMENT, not hp: asm00_2.s:683).
    families = {}
    for r in rows:
        if r["actor_type_raw"] != 0:  # ACTOR_TYPE_VIRUS (AIData.inc:6)
            continue
        fam = families.setdefault(r["ai_index"], {
            "ai_index": r["ai_index"],
            "think": r["think"]["symbol"],
            "think_cite": f"{r['think']['file']}:{r['think']['line']}",
            "act": r["act"]["symbol"],
            "act_cite": f"{r['act']['file']}:{r['act']['line']}",
            "ranks": [],
        })
        # a family's ranks are its distinct version bytes (up to 6 per
        # family); the identity table repeats an enemy_idx per spawn entry,
        # so ranks dedupe on version and collect their spawn enemy_idxs
        dup = next((rk for rk in fam["ranks"] if rk["version_byte"] == r["version"]), None)
        if dup is not None:
            dup["spawn_enemy_idxs"].append(r["enemy_idx"])
            continue
        hp = virus_rank_hp(r["ai_index"], r["version"])
        status = "verified" if is_mettaur_row(r) else "unrecorded"
        fam["ranks"].append({
            "spawn_enemy_idxs": [r["enemy_idx"]],
            "enemy_idx": r["enemy_idx"],
            "version_byte": r["version"],
            "elem_hp_row0_raw": f"0x{hp:04x}" if hp is not None else "",
            "hp_low12": (hp & 0xFFF) if hp is not None else None,
            "cite": f"asm/asm00_2.s:19975 byte_80182C4 row {r['enemy_idx']}",
            "status": status,
        })
    out = []
    for ai in sorted(families):
        fam = families[ai]
        fam["ranks"].sort(key=lambda x: x["enemy_idx"])
        out.append(fam)
    return out, data["meta"]


def is_mettaur_row(r):
    # the verified item is THE Mettaur the mettaur scenario records (V1,
    # enemy_idx 1): ported as canon's routine with trace + pixel parity
    # (docs/coverage/mettaur.md, T6). The family's other ranks/versions are
    # not separately recorded.
    return r["ai_index"] == 1 and r["enemy_idx"] == 1


def virus_rank_hp(ai_index, version):
    """u16 at Struct2[ai_index] + 6*version (stride 6, asm00_2.s:678-682).
    Struct2 pointer table off_8109150 (asm/asm31.s:169550)."""
    if not hasattr(virus_rank_hp, "cache"):
        lines = read_lines("asm/asm31.s")
        s, e = label_bounds(lines, "AIEnemyStruct2Ptrs_8109150")  # T14: was off_8109150, renamed (renames.md:244)
        ptrs = []
        for i in range(s + 1, e):
            m = WORD_RE.match(strip_comment(lines[i]))
            if not m:
                continue
            tok = m.group(1).strip()
            if not re.fullmatch(r"[A-Za-z_]\w*", tok):
                break
            ptrs.append(tok)
        cache = {}
        for idx, lbl in enumerate(ptrs):
            vals = [v for t, k, v, _ in region_bytes("asm/asm31.s", lbl) if t == "h" and k == "v"]
            # rows of 3 hwords (elem_hp, unk, elem_damage), stride 6 bytes
            cache[idx] = vals[0::3] if vals else []
        virus_rank_hp.cache = cache
    rows = virus_rank_hp.cache.get(ai_index, [])
    return rows[version] if version < len(rows) else None


# ------------------------------------------------------------------- navis

# T76: the chain T12 already walks for viruses works for navis too. The
# per-AIIndex arm in AIThinkTables_8109050 (asm/asm31.s:169444) is the
# NAVI-side analog of the virus chain: think word is a pointer to a
# CurAction-indexed handler TABLE handed to battle_801B1C4 (asm31.s:169395-
# 169402). NaviIdentity rows (sub_80F2354, asm/asm31.s:123323-123356) also
# reach two extra 25-entry tables off_80F2474 and NaviActHandlers_80F25A0
# -- mostly nullsub_106 (22/25 each). Per-ai routine present only at slots
# 0,5,13 in NaviActHandlers and 5,10,16 in off_80F2474.
NAVI_STRUCT1 = "NaviEnemyStruct1Ptrs_80F24D8"  # asm/asm31.s:123445 (T14: renamed, renames.md:404) — Struct1 ptrs (consumed by enemy_getStruct1, asm00_2.s:669-674)
NAVI_STRUCT2 = "NaviEnemyStruct2Ptrs_80F253C"  # asm/asm31.s:123496 (T14: renamed) — Struct2 ptrs (consumed by enemy_getStruct2, asm00_2.s:713)
NAVI_ACT = "NaviActHandlers_80F25A0"           # asm/asm31.s:123547 (T14: renamed) — per-AIIndex act routine called by sub_80F2354 bx r0
NAVI_PATTERN = "off_80F2474"                   # asm/asm31.s:123420 (unlabeled in disassembly) — second per-AIIndex routine called by sub_80F2354 bx r0
NAVI_COMMON = "off_80F2410"                    # asm/asm31.s:123387 (unlabeled) — first routine called by sub_80F2354 (shared damage routines)
NAVI_ATTACK_TBL = "off_80F23AC"                # asm/asm31.s:123369 (unlabeled) — jump-table arg to ai_eventuallyRunsAIAttack_801AF44 (asm31.s:123346)
NAVI_AI_TABLE = "AIThinkTables_8109050"        # asm/asm31.s:169444 — same 32-entry think/row per-type chain the viruses use (T12)


def parse_navis():
    lines31 = read_lines("asm/asm31.s")
    def words(lines, label):
        s, e = label_bounds(lines, label)
        out = []
        for i in range(s + 1, e):
            m = WORD_RE.match(strip_comment(lines[i]))
            if m:
                tok = m.group(1).strip().rstrip("+1")
                if not re.fullmatch(r"[A-Za-z_]\w*", tok):
                    break
                out.append((tok, i + 1))
        return out
    s1 = words(lines31, NAVI_STRUCT1)
    s2 = words(lines31, NAVI_STRUCT2)
    act = words(lines31, NAVI_ACT)
    pat = words(lines31, NAVI_PATTERN)
    common = words(lines31, NAVI_COMMON)
    atk = words(lines31, NAVI_ATTACK_TBL)
    ai_tbl = words(lines31, NAVI_AI_TABLE)
    n = min(len(s1), len(s2), len(act), len(pat), 25)
    navi_names = {e["value"]: e["name"] for e in NAVI_ENUM}
    rows = []
    for i in range(n):
        hp = navi_row0_hp(s2[i][0])
        ai_tbl_sym = ai_tbl[i][0] if i < len(ai_tbl) else ""
        ai_tbl_cite = f"asm/asm31.s:{ai_tbl[i][1]}" if i < len(ai_tbl) else ""
        is_nullsub_act = act[i][0] == "nullsub_106"
        is_nullsub_pat = pat[i][0] == "nullsub_106"
        # GAP marker when we have no name AND no per-ai routine (the
        # pattern work for these navis is still in the per-AIIndex arm
        # table, but no naming source is located in budget).
        if i not in navi_names and is_nullsub_act and is_nullsub_pat:
            status = "GAP: no NAVI_* enum match + ai_pattern arm and act both nullsub_106 (per-type work in ai_tbl[i] only)"
        elif is_nullsub_act and is_nullsub_pat:
            status = "named-via-NAVI-enum (per-type work in ai_tbl[i]; act/pat nullsub_106)"
        else:
            status = "per-ai routine named"
        rows.append({
            "index": i,
            "navi": navi_names.get(i, f"// unnamed: navi-table index {i}"),
            "ai_index": i,
            "struct1": f"{s1[i][0]} (asm/asm31.s:{s1[i][1]})",
            "struct2": f"{s2[i][0]} (asm/asm31.s:{s2[i][1]})",
            "struct2_row0_raw": f"0x{hp:04x}" if hp is not None else "",
            "act": f"{act[i][0]} (asm/asm31.s:{act[i][1]})",
            "pattern": f"{pat[i][0]} (asm/asm31.s:{pat[i][1]})",
            "ai_arm": f"{ai_tbl_sym} ({ai_tbl_cite})",
            "common": f"{common[i][0]} (asm/asm31.s:{common[i][1]})",
            "attack_tbl": f"{atk[i][0]} (asm/asm31.s:{atk[i][1]})",
            "cite": f"asm/asm31.s:{s1[i][1]},{s2[i][1]},{act[i][1]},{pat[i][1]},{ai_tbl_cite.split(':')[1] if ':' in ai_tbl_cite else ai_tbl_cite}",
            "status": status,
        })
    return rows


def navi_row0_hp(label):
    vals = [v for t, k, v, _ in region_bytes("asm/asm31.s", label) if t == "h" and k == "v"]
    return vals[0] if vals else None


# ------------------------------------------------------------------- forms

def parse_forms():
    # canon: charge-shot dispatch off_80117D4 (asm/asm00_2.s:5789),
    # indexed by the Transformation byte (DeterminePowerAttackChargeTime's
    # TF_GREGARBEAST/TF_FALZARBEASTOVER compare, asm/asm00_2.s:9170-9173).
    # The table is longer than the TF enum (extra indexes up to its end are
    # kept in 'charge_shot_table_extra', unclaimed); the ladder rows are the
    # TF enum values.
    lines = read_lines("asm/asm00_2.s")
    s, e = label_bounds(lines, "ChargeShotHandlersByTransformation_80117D4")  # T14: was off_80117D4, renamed in reference
    charges = {}
    for i in range(s + 1, e):
        m = WORD_RE.match(strip_comment(lines[i]))
        if not m:
            continue
        idx_m = re.search(r"//\s*0x([0-9a-fA-F]+)", lines[i])
        if not idx_m:
            break
        sym = m.group(1).strip().replace("+1", "")
        idx = int(idx_m.group(1), 16)
        charges[idx] = {"symbol": sym, "cite": f"asm/asm00_2.s:{i + 1}"}
    rows = []
    for t in TF_ENUM:
        ch = charges.get(t["value"])
        rows.append({
            "tf_value": f"0x{t['value']:02x}",
            "form": t["name"],
            "form_cite": t["cite"],
            "charge_shot": ch["symbol"] if ch else "// unnamed: no charge-shot entry",
            "charge_cite": ch["cite"] if ch else "",
            "status": "unrecorded",
        })
    tf_max = max(t["value"] for t in TF_ENUM)
    extra = [{"index": f"0x{k:02x}", "charge_shot": v["symbol"], "cite": v["cite"]}
             for k, v in sorted(charges.items()) if k > tf_max]
    return rows, extra


# ------------------------------------------------------------------ panels

# canon: word_3007924 (IWRAM copy, asm/asm38.s:4242-4249). ROM original:
# IWRAMRoutinesROMLocation + 0x1E24 = 0x081D7E24 -- bn6f.map:34342 is the
# IWRAMRoutinesROMLocation line itself (0x081d6000), and word_3007924 is in
# no map line: the address is derived from the copy routine (start.s
# start_copyMemory: 0x081d6000 -> 0x3005B00 len 0x1ed4, so
# 0x3007924 - 0x3005B00 = 0x1E24; byte match
# verified in the ROM at 0x081D7E24). _object_updatePanelParameters reads
# oPanelData_Type, copies it to oPanelData_Animation, lsls it by 2 and ORs the
# word into oPanelData_Flags (asm/asm38.s:4213-4219). 13 words, stride 4,
# one per panel type 0x0..0xC.
PANEL_TYPE_FLAG_WORDS = {
    0x0: "0x18000", 0x1: "0x14000", 0x2: "0x10010", 0x3: "0x10050",
    0x4: "0x10110", 0x5: "0x12010", 0x6: "0x10410", 0x7: "0x10810",
    0x8: "0x11010", 0x9: "0x10210", 0xA: "0x10210", 0xB: "0x10210",
    0xC: "0x10210",
}

# provenance: derived -- meanings from writer/reader names and comments in the
# reference disassembly; rows whose meaning is not named by any site carry
# "unnamed:". Regens: tickPanels_800C380 turns broken(1) -> 2 and
# cracked(3) -> 1 (asm/object.s:1471-1472/1503-1504), so 2 = normal and the
# numbering matches src/field.rs (PANEL_HOLE=0 .. PANEL_POISON=4).
PANEL_TYPE_ROWS = [
    # (type, meaning, writer cite, reader cite)
    (0x0, "hole (skipped by every reader; flag word is the only one with bit 0x8000)",
     "GAP confirmed zero-writer (T33 4-site sweep widened by T115 to the whole field, 42+ sites examined): object_setPanelType (object.s:2601-2611) is a trampoline to _object_setPanelType (asm38.s:4309-4315), so 29 bl sites total (asm38.s:3581/3969/3980/3993 all r2=#2; asm31.s x21, asm32.s x2, asm00_2.s x2 -- constant args only 2/3/4/6/7/0xb/0xc, rest data-fed) + 13 direct strb oPanelData_Type sites (asm38.s:4318 inside the setter + object.s:2220/2235/2272/2287/2323/2357/2371/2405/2419/2455/2469/2505/2519, all store 1/3) + object_panel_setPoison (object.s:2540-2563, literal-offset strb with r2=#4). The setter REFUSES type-0 targets (asm38.s:4316-4317 ldrb/tst r3/beq skip), so 0 is only the init/memset default, never re-written; T115 data walk (byte_80E6D0C/byte_80CE41E/dword_80DE79C/1240 BattleSettings records/1076 formation arrays) found no other 0 producer",
     "asm/asm38.s:4315-4317 (_object_setPanelType tst->skip) + asm/object.s:1426-1428 (tickPanels skip)"),
    (0x1, "broken",
     "asm/object.s:2323 (object_breakPanel); also object_crackPanel 2nd arm asm/object.s:2235; cracked regen asm/object.s:1503-1504",
     "asm/asm00_2.s:11130 (sub_8013CC4 cmp #1) + asm/object.s:1430-1434 (tickPanels regen 0x708)"),
    (0x2, "normal (regen target of broken)",
     "asm/object.s:1471-1472 (tickPanels regen); also asm/asm00_2.s:8300-8301 (sub_8012792 stage chip), asm/asm31.s:38397-38398 (t3_0x31_80C9F78), fire melts type 7 -> 2 asm/asm38.s:3575-3582 (sub_3007460)",
     "asm/object.s:1460 (tickPanels default arm regen)"),
    (0x3, "cracked",
     "asm/object.s:2218-2222 (object_crackPanel 1st arm: Flags = (Flags & ~0x3f0f)+3, Type=3)",
     "asm/object.s:1436-1442 (tickPanels: regen then -> 1)"),
    (0x4, "poison",
     "asm/asm31.s:6146-6147 (sub_80BAE16 local arm)",
     "asm/asm00_2.s:21674-21689 (sub_801A186 ticks oCollisionData_PoisonPanelTimer)"),
    (0x5, "holy",
     "GAP confirmed zero-writer (T115 full walk, same 42+ sites as the 0x0 row: 29 bl sites with constant args only 2/3/4/6/7/0xb/0xc, 13 direct strb sites all 1/3, poison 4) plus every data-fed writer: t4_0x56 whole-field nibbles byte_80E6D0C (asm31.s:99543-99566) hold only {2,3,6,7,8}; t3_0x4f area types byte_80CE41E (asm31.s:47201) {4,7,6}; t3_0xc9 dword_80DE79C (asm31.s:81488) {FF,3,7,6}; t4_0x16 arms (asm31.s:88662-88960) are Param1-fed with constant-3 enemy-half arm and unreferenced spawners; t4_0x1f (asm31.s:89990-90045) type comes from ExtraVars[0], also unreferenced; navi-byte events asm00_2.s:10776-10810 write only {3,4} into the byte sub_8013CC4 (asm00_2.s:11109-11160) replays onto panels; shockwave dispatch asm31.s:31640-31653 {skip,crack,break,variable}. Holy stays a live reader rule (object.s:4831-4833 'cmp r1,#5 // holy panel?' + asm00_2.s:22788-22791 halves the damage sum) with no producer in this ROM's code or data",
     "asm/object.s:4831-4833 (object_calculateFinalDamage1 'cmp r1,#5 // holy panel?') + asm/asm00_2.s:22788-22791 (sub_801A7F4 halves the damage sum)"),
    (0x6, "grass",
     "asm/asm31.s:6168-6169 (sub_80BAE16 local arm) + asm/asm31.s:30843-30844 (cornfiestaRelatedObject_80C6580)",
     "asm/asm38.s:3855-3862 (applyHeatOnGrassDamage_300766c 'cmp r0,#6 // grass')"),
    (0x7, "unnamed: stage terrain melted to normal(2) by fire (sub_3007460); ice candidate",
     "asm/asm31.s:6104-6105 (sub_80BAE16 local arm)",
     "asm/asm38.s:3575-3582 (sub_3007460 cmp #7 -> setPanelType 2); readers asm/asm00_2.s:16573/17376/18848/19321/19552"),
    (0x8, "unnamed: ice candidate; whole-field pattern seeder t4_0x56 (regen like broken, Elec melts to 2)",
     "asm31.s:99515-99529 (sub_80E6CAA in t4_0x56_80E6BDC: base = byte_80E6D0C + Param1*0xc + alliance*0x78, then per panel ldr word / lsr (row-1)*4 / and #0xf -> type = packed 4-bit nibble) + packed pattern table byte_80E6D0C asm31.s:99543-99566 (240 bytes = 2 alliances x 10 Param1 entries x 12 bytes; nibble set {2,3,6,7,8} -- the ONLY producer of 8: Param1 2/3/4 own-side rows, 0x82/0x28 bytes in both alliance halves). Update-handler vtable entry asm00_1.s:2491; spawner sub_80E6C8C asm31.s:99473-99489 is unreferenced in the whole ROM (no bl, no pointer word 0x080E6C8C/D -- byte search) so no live capture (T115 step 3: 0 captures)",
     "asm/object.s:1444-1450 (tickPanels regen 0x258/0x708) + asm/asm38.s:3960-3983 (sub_3007708 cmp #8 + Elec melts to 2)"),
    (0x9, "unnamed: 9..0xC share flag word 0x10210; regen without the 0x708 blink timer",
     "GAP confirmed zero-writer (T115 full walk, same 42+ sites as the 0x5 row). _object_setPanelType itself has special-case arms for 9..0xC (asm38.s:4318-4326, sets oPanelData_Unk_12=0x708), sub_3007708 melts 9..0xC + element 4 to type 2 (asm38.s:3993), but no producer: no constant arg, no direct strb, and none of the data tables (byte_80E6D0C {2,3,6,7,8}, byte_80CE41E {4,7,6}, dword_80DE79C {FF,3,7,6}, navi-byte events {3,4}, 1240 records, 1076 formation arrays) holds a 9",
     "asm/asm38.s:4318-4326 (_object_setPanelType: 9..0xC get Unk_12=0x708) + asm/object.s:1452-1458 + asm/asm00_2.s:21953-21960"),
    (0xA, "unnamed: same regen group as 9",
     "GAP confirmed zero-writer (T115 full walk, same sites as 0x9): the in-code handles (asm38.s:4318-4326 _object_setPanelType Unk_12=0x708, sub_3007708 asm38.s:3993 melt on element 4) confirm the type exists in code, but no constant arg, direct strb, or data-table byte anywhere in the ROM produces 0xA",
     "asm/asm38.s:4318-4326 + asm/object.s:1452-1458 (9..0xC range) + asm/asm38.s:3993 (sub_3007708 melt)"),
    (0xB, "unnamed: stage type written from the hit object's CurState (alliance arm)",
     "asm/asm31.s:27871-27872 (t3_0x0_80C4E58, alliance != 0 arm)",
     "asm/asm38.s:4318-4326 (_object_setPanelType 9..0xC)"),
    (0xC, "unnamed: stage type written from the hit object's CurState (alliance arm)",
     "asm/asm31.s:27855-27856 (t3_0x0_80C4E58, alliance == 0 arm)",
     "asm/asm38.s:4318-4326 (_object_setPanelType 9..0xC)"),
]

# Second type-shaped table, unparsed in the recon. 46 .word entries (stride 4)
# at 0x08019B78 pointing to signed (x,y) byte-pair lists 0x7F-terminated
# (byte_80198E8..byte_8019C7C); readers scale the pairs by the alliance
# direction. Index provenance per reader:
PANEL_OFFSET_LIST_READERS = [
    "asm/asm38.s:3703-3706 (_object_removeCollisionData: idx = oCollisionData_Region)",
    "asm/asm38.s:4010-4013 (sub_300777C: idx = oCollisionData_Region)",
    "asm/asm38.s:4100-4104 (sub_3007828: idx = byte [r0+1] of an effect object)",
    "asm/asm00_2.s:15553-15556 (GetRandomRelativePanelFiltered: idx = r4, caller-supplied 'which list of relative panel offsets')",
    "asm/asm00_2.s:25340 (sub_801BD3C: idx = arg >> 0x17)",
]


def parse_panels():
    rows = []
    for ty, meaning, writer, reader in PANEL_TYPE_ROWS:
        if writer.startswith("GAP"):
            status = "bounded-GAP (T33): walked writer sites, no writer in disassembly"
        elif writer.startswith("unnamed:"):
            status = "unverified: reader-only (no writer cite)"
        else:
            status = "verified"
        rows.append({
            "type": f"0x{ty:X}",
            "meaning": meaning,
            "flag_word": PANEL_TYPE_FLAG_WORDS[ty],
            "writer": writer,
            "reader": reader,
            "status": status,
        })
    return rows


# ---------------------------------------------------------------- statuses

# T18: DERIVED-FROM-CODE. The 69 named bits are walked to their canonical
# sites: every bl object_setFlag1/2 + object_clearFlag(2) + inline
# orr/str-to-flags-field (setters/clearers), every bl object_getFlag(2) +
# direct flags-field load followed by a tst/and/lsr mask test (readers).
# Masks are resolved from `ldr rX, lbl // =0xVAL`, `mov rX, #CONST` (named
# struct_const or .equiv), and the `mov rX, #1; lsl rX, rX, #BITCONST`
# idiom; a multi-bit mask attributes a hit to EVERY named bit it covers
# (e.g. the 0xa000 BLIND|CONFUSED gate in MettaurDecideCheckStatusAndRow).
STATUS_ASM_DIR = "asm"
STATUS_HELPER_SET = {"object_setFlag1": 1, "object_setFlag2": 2}
STATUS_HELPER_CLR = {"object_clearFlag": 1, "object_clearFlag2": 2}
STATUS_HELPER_GET = {"object_getFlag": 1, "object_getFlag2": 2}
STATUS_FIELD_LOADS = {1: "#oCollisionData_ObjectFlags1",
                      2: "#oCollisionData_ObjectFlags2"}


def _status_consts():
    consts = {}
    for rel in ("include/structs/CollisionData.inc",
                "include/structs/BattleObject.inc"):
        for i, ln in enumerate(read_lines(rel), 1):
            m = re.match(r"\s*struct_const (\w+),\s*(0x[0-9a-fA-F]+|\d+)", ln)
            if m:
                consts[m.group(1)] = int(m.group(2), 0)
    for ln in read_lines(f"{STATUS_ASM_DIR}/asm31.s"):
        m = re.match(r"\s*\.equiv (\w+),\s*(0x[0-9a-fA-F]+|\d+)", ln)
        if m and m.group(1) not in consts:
            consts[m.group(1)] = int(m.group(2), 0)
    return consts


def _tok_val(tok, consts):
    if tok in consts:
        return consts[tok]
    try:
        return int(tok, 0)
    except ValueError:
        return None


def _resolve_reg(lines, idx, reg, consts, depth=18):
    """value last assigned to reg before line idx (backward, stops on labels
    and on any bl -- a helper call clobbers the caller-saved argument)"""
    for j in range(idx - 1, max(-1, idx - depth), -1):
        ln = lines[j].strip()
        if re.match(r"\w+:\s*$", ln):
            return None
        if ln.startswith("bl ") or ln.startswith("blx "):
            return None
        m = re.match(rf"ldr\s+{reg},\s*\w+\s*//\s*=(0x[0-9a-fA-F]+|\d+)", ln)
        if m:
            return int(m.group(1), 0)
        m = re.match(rf"movs?w?\s+{reg},\s*#(\w+)", ln)
        if m:
            v = _tok_val(m.group(1), consts)
            if v is None:
                return None
            for k in range(j + 1, idx):
                m2 = re.match(rf"lsls?\s+{reg},\s*{reg},\s*#(\w+)",
                              lines[k].strip())
                if m2:
                    b = _tok_val(m2.group(1), consts)
                    if b is not None:
                        return (1 << b) & 0xFFFFFFFF
            return v
        m = re.match(rf"movs?\s+{reg},\s*(r\d+)", ln)
        if m and m.group(1) != reg:
            v = _resolve_reg(lines, j, m.group(1), consts, depth)
            if v is None:
                return None
            for k in range(j + 1, idx):
                m2 = re.match(rf"lsls?\s+{reg},\s*{reg},\s*#(\w+)",
                              lines[k].strip())
                if m2:
                    b = _tok_val(m2.group(1), consts)
                    if b is not None:
                        return (1 << b) & 0xFFFFFFFF
            return v
    return None


def _resolve_fwd_mask(lines, idx, reg, consts, depth=14):
    """mask held in reg at line idx (resolved backward, incl. mov #1 + lsl;
    stops on labels and on any bl -- a helper call clobbers caller-saved r)"""
    for j in range(idx - 1, max(0, idx - depth), -1):
        ln = lines[j].strip()
        if re.match(r"\w+:\s*$", ln):
            return None
        if ln.startswith("bl ") or ln.startswith("blx "):
            return None
        m = re.match(rf"ldr\s+{reg},\s*\w+\s*//\s*=(0x[0-9a-fA-F]+|\d+)", ln)
        if m:
            return int(m.group(1), 0)
        m = re.match(rf"movs?\s+{reg},\s*#(\w+)", ln)
        if m:
            v = _tok_val(m.group(1), consts)
            if v is None:
                return None
            for k in range(j + 1, idx):
                m2 = re.match(rf"lsls?\s+{reg},\s*{reg},\s*#(\w+)",
                              lines[k].strip())
                if m2:
                    b = _tok_val(m2.group(1), consts)
                    if b is not None:
                        return (1 << b) & 0xFFFFFFFF
            return v
    return None


def _bits_hit(mask, consts):
    """every named 32-bit flag value covered by mask (combined masks count
    for each bit they carry -- LOOSE rule, used only for the 'any-mask
    mention' column/counts; a combined test only proves SOME member
    mattered, so the headline per-bit counts use mask == bit value, see
    parse_statuses)"""
    out = set()
    for n, v in consts.items():
        if (n.startswith("OBJECT_FLAGS_") and not n.endswith("_BIT")
                and not n.startswith("OBJECT_FLAGS_2_UNK")
                and v and (mask & v) == v):
            out.add(n)
        if (n.startswith("OBJECT_FLAGS_2_") and v
                and (mask & v) == v):
            out.add(n)
    return out


def _status_field_sites(consts):
    """walk every asm file: setter/clearer/reader sites per flags field"""
    files = sorted(f for f in os.listdir(os.path.join(REF, STATUS_ASM_DIR))
                   if f.endswith(".s"))
    src = {f: read_lines(f"{STATUS_ASM_DIR}/{f}") for f in files}
    setters = {1: {}, 2: {}}   # bitname -> [("file:line", mask), ...]
    clearers = {1: {}, 2: {}}
    readers = {1: {}, 2: {}}

    def add(d, fld, mask, cite):
        for bit in _bits_hit(mask, consts):
            d[fld].setdefault(bit, []).append((cite, mask))

    for f in files:
        lines = src[f]
        for i, ln in enumerate(lines):
            s = ln.strip()
            for fld in (1, 2):
                fldc = STATUS_FIELD_LOADS[fld]
                # UNSOUND heuristic (T18 correction pass): this fires on ANY
                # ldr/str/ldrh/strh touching the flags field, including a
                # whole-word store / bulk zero, and credits the first orr/bic
                # within +/-5 lines WITHOUT checking that the orr/bic targets
                # the flags register. 4 credits this run came through here;
                # a bulk zero near an unrelated orr must not read as
                # "inflicting a status". Kept flagged, not silently trusted.
                if re.search(rf"(ldr|str|ldrh|strh)\s+\w+,\s*\[\w+,\s*" + fldc,
                             s):
                    for k in range(max(0, i - 5), min(len(lines), i + 6)):
                        s2 = lines[k].strip()
                        mo = re.match(r"orrs?\s+\w+,\s*(r\d+)", s2)
                        mb = re.match(r"bics?\s+\w+,\s*(r\d+)", s2)
                        if not (mo or mb):
                            continue
                        reg = (mo or mb).group(1)
                        v = _resolve_reg(lines, k, reg, consts, 15)
                        if v:
                            add(setters if mo else clearers, fld, v,
                                f"{STATUS_ASM_DIR}/{f}:{i + 1}")
                        break
            m = re.match(r"bl\s+(object_(?:setFlag\d|clearFlag\d?|getFlag\d?))",
                         s)
            if m:
                name = m.group(1)
                cite = f"{STATUS_ASM_DIR}/{f}:{i + 1}"
                if name in STATUS_HELPER_SET:
                    v = _resolve_reg(lines, i, "r0", consts)
                    if v:
                        add(setters, STATUS_HELPER_SET[name], v, cite)
                elif name in STATUS_HELPER_CLR:
                    v = _resolve_reg(lines, i, "r0", consts)
                    if v:
                        add(clearers, STATUS_HELPER_CLR[name], v, cite)
                elif name in STATUS_HELPER_GET:
                    fld = STATUS_HELPER_GET[name]
                    for k in range(i + 1, min(len(lines), i + 14)):
                        s2 = lines[k].strip()
                        if k > i and re.match(r"\w+:", s2):
                            break
                        mt = re.match(r"tsts?\s+r0,\s*(r\d+)", s2)
                        ma = re.match(r"ands?\s+r0,\s*r0,\s*(r\d+)", s2)
                        if mt or ma:
                            reg = (mt or ma).group(1)
                            if reg != "r0":
                                v = _resolve_fwd_mask(lines, k, reg, consts)
                                if v:
                                    add(readers, fld, v, cite)
                            break
                        ml2 = re.match(rf"lsrs?\s+r0,\s*r0,\s*#(\w+)", s2)
                        if ml2:
                            b = _tok_val(ml2.group(1), consts)
                            if b is not None:
                                add(readers, fld, 1 << b, cite)
                            break
                        if re.match(r"str\b", s2) and k > i + 2:
                            break
                continue
            for fld in (1, 2):
                m = re.match(r"(ldr|ldrh)\s+(\w+),\s*\[\w+,\s*"
                             + STATUS_FIELD_LOADS[fld], s)
                if m:
                    reg = m.group(2)
                    for k in range(i + 1, min(len(lines), i + 10)):
                        s2 = lines[k].strip()
                        if re.match(r"str", s2):
                            break
                        mt = re.match(rf"tsts?\s+{reg},\s*(r\d+)", s2)
                        if mt:
                            r2 = mt.group(1)
                            if r2 != reg:
                                v = _resolve_fwd_mask(lines, k, r2, consts)
                                if v:
                                    add(readers, fld, v,
                                        f"{STATUS_ASM_DIR}/{f}:{i + 1}")
                            break
                        ml2 = re.match(rf"lsrs?\s+{reg},\s*{reg},\s*#(\w+)",
                                       s2)
                        if ml2:
                            b = _tok_val(ml2.group(1), consts)
                            if b is not None:
                                add(readers, fld, 1 << b,
                                    f"{STATUS_ASM_DIR}/{f}:{i + 1}")
                            break
    return setters, clearers, readers


def _status_table_families():
    """off_80209EC (data/dat01.s): 6 pointers, families of stride-8 records
    [0] flag2 mask u32, [4] hword, [6] CollisionData timer offset; consumed
    by sub_801A554 (asm/asm00_2.s:22211-22230), index
    (oCollisionData_StatusEffectFinal>>4)-1 + (val&7)<<3."""
    dat = read_lines("data/dat01.s")
    lab = {}
    for i, ln in enumerate(dat):
        m = re.match(r"(\w+)::", ln)
        if m:
            lab[m.group(1)] = i
    start = lab["off_80209EC"]
    ptrs = [re.match(r"\s*\.word (\w+)", l).group(1)
            for l in dat[start + 1:start + 7]]
    fams = []
    for pl in ptrs:
        vals = []
        for l in dat[lab[pl] + 1:]:
            if re.match(r"\w+::", l):
                break
            wm = re.search(r"\.word (0x[0-9a-fA-F]+)", l)
            if wm:
                v = int(wm.group(1), 16)
                vals += [v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF,
                         (v >> 24) & 0xFF]
            else:
                vals += [int(m.group(0), 16)
                         for m in re.finditer(r"0x[0-9a-fA-F]+", l)]
        recs = [(int.from_bytes(bytes(vals[j:j + 4]), "little"),
                 int.from_bytes(bytes(vals[j + 4:j + 6]), "little"),
                 vals[j + 6])
                for j in range(0, len(vals) - 7, 8)]
        fams.append({"label": pl, "records": recs})
    return fams


def parse_statuses():
    consts = _status_consts()
    fams = _status_table_families()
    setters, clearers, readers = _status_field_sites(consts)
    # family -> flag2 mask reached by every record's [+0] word (measured:
    # one mask per family); family n = StatusEffectFinal high nibble n
    fam_masks = {}
    for fi, fam in enumerate(fams, 1):
        masks = sorted({r[0] for r in fam["records"]})
        assert len(masks) == 1, f"family {fi} has mixed masks {masks}"
        fam_masks[fi] = masks[0]
    table_mask_set = set(fam_masks.values())
    # flags2 bits written directly by named code (outside the table path)
    direct_f2 = {v for n, v in consts.items()
                 if n.startswith("OBJECT_FLAGS_2_")
                 and setters[2].get(n)}
    rows = []
    for rel, prefix in (("include/structs/CollisionData.inc", "OBJECT_FLAGS_"),
                        ("include/structs/BattleObject.inc", "DAMAGE_")):
        for i, ln in enumerate(read_lines(rel), 1):
            m = re.match(rf"\s*struct_const ({prefix}\w+),\s*(0x[0-9a-fA-F]+)",
                         ln)
            if not m:
                continue
            name, val = m.group(1), m.group(2)
            v = int(val, 16)
            is_f2 = name.startswith("OBJECT_FLAGS_2_")
            fld = 2 if is_f2 else (1 if name.startswith("OBJECT_FLAGS_")
                                   else 0)
            st = setters[fld].get(name, []) if fld else []
            cl = clearers[fld].get(name, []) if fld else []
            rd = readers[fld].get(name, []) if fld else []
            fams_hit = sorted(fi for fi, fm in fam_masks.items()
                              if fm & v == v and v) if is_f2 else []
            in_table = bool(fams_hit)
            # per-bit (strict, mask == this bit's value) vs any-mask mention
            # (loose): a combined test only proves SOME member mattered
            st_strict = [c for c, m in st if m == v]
            rd_strict = [c for c, m in rd if m == v]
            st_loose = [c for c, m in st if m != v]
            rd_loose = [c for c, m in rd if m != v]

            def site_txt(strict, loose, none_txt, loose_tag):
                if strict:
                    return strict[0] + (f" (+{len(strict) - 1})"
                                        if len(strict) > 1 else "")
                if loose:
                    return f"{loose[0]} ({loose_tag})"
                return none_txt

            setter_txt = site_txt(st_strict, st_loose, "NONE",
                                  "combined-mask only")
            reader_txt = site_txt(rd_strict, rd_loose, "none",
                                  "combined-mask only")
            rows.append({
                "bit": name, "value": val,
                "setter": setter_txt,
                "reader": reader_txt,
                # re-derived from the per-bit rule (T18 correction): not the
                # loose any-mask count
                "battle_visible": "yes" if rd_strict else "no",
                "via_table": (",".join(str(x) for x in fams_hit)
                              if in_table else "-"),
                "cite": f"{rel}:{i}", "status": "unrecorded",
                "_counts": (len(st_strict), len(cl), len(rd_strict)),
                "_loose": (len(st), len(cl), len(rd)),
                "_in_direct_f2": is_f2 and bool(st),
            })
    n_set = sum(1 for r in rows if r["_counts"][0] > 0)
    n_rd = sum(1 for r in rows if r["_counts"][2] > 0)
    n_set_loose = sum(1 for r in rows if r["_loose"][0] > 0)
    n_rd_loose = sum(1 for r in rows if r["_loose"][2] > 0)
    # three SEPARATE partitions (T18 correction: never add across them):
    # RECORDS: table-only + shared-family = 37; MASKS: table-only + overlap
    # = 6; and the directly-written-masks-outside-the-table count is a MASK
    # count, not a record count.
    overlap_masks = table_mask_set & direct_f2
    records_overlap = sum(len(f["records"]) for f in fams
                          if f["records"][0][0] in direct_f2)
    meta = {
        "families": fams,
        "fam_masks": fam_masks,
        "n_bits": len(rows),
        "n_written": n_set,
        "n_written_loose": n_set_loose,
        "n_read": n_rd,
        "n_read_loose": n_rd_loose,
        "n_unread": len(rows) - n_rd,
        "n_written_read": sum(1 for r in rows
                              if r["_counts"][0] > 0 and r["_counts"][2] > 0),
        "table_records": sum(len(f["records"]) for f in fams),
        "table_sizes": [len(f["records"]) for f in fams],
        "table_masks": sorted(hex(m) for m in table_mask_set),
        # set differences, on distinct flag2 masks
        "table_only_masks": sorted(
            hex(m) for m in table_mask_set - direct_f2),
        "direct_only_masks": sorted(
            hex(m) for m in direct_f2 - table_mask_set),
        "table_records_only": sum(len(f["records"]) for f in fams
                                  if f["records"][0][0] not in direct_f2),
        "records_overlap": records_overlap,
        "masks_overlap": sorted(hex(m) for m in overlap_masks),
        "fam_sizes": [len(f["records"]) for f in fams],
    }
    return rows, meta


STATUS_M3_CANDIDATES = [
    # (status, reader cite, inflicting path -- what a chip must write)
    # T18 correction: CONFUSED's reader cite must be a PER-BIT test.
    # asm31.s:171395-171397 was REFUTED (that is the effect body -- the strb
    # of 8 to oAIState_Unk_00 and the strh #0 to +2); the 0xa000 tst lives at
    # asm31.s:171391-171393 and is BLIND|CONFUSED combined, which only proves
    # SOME member mattered. The per-bit CONFUSED reader is asm00_2.s:1894-1897
    # (object_getFlag; mov r1,#1; lsl r1,#0xf; tst = 0x8000 alone).
    ("CONFUSED", "asm/asm00_2.s:1894-1897",
     "StatusEffectFinal 0x2X -> sub_801A554 family 2 -> flag2 0x80 + timer"
     " oCollisionData_Unk_1e -> flags1 0x8000 (tick object.s:5438-5452)"),
    ("BLIND", "asm/asm00_2.s:16861-16863",
     "StatusEffectFinal 0x3X -> family 3 -> flag2 0x20 + BlindTimer"
     " (inflicter measured: asm/asm00_2.s:11366-11368; NOTE the 0x12c=300 is"
     " a SHARED 5-second status duration -- off_80141BC also feeds"
     " oCollisionData_Unk_1e at 11375-11377 and setInvulnerableTime at"
     " 11348/11356 -- not a BLIND-specific constant)"),
    ("IMMOBILIZED", "asm/asm31.s:171386-171390",
     "StatusEffectFinal 0x4X -> family 4 (7 recs) -> flag2 0x40 + timer"
     " oCollisionData_Unk_22 -> flags1 0x4000 (tick object.s:5500-5508)"),
]


# -------------------------------------------------------------- formations

def parse_formations():
    """T65: walk the record streams straight from the ROM, not the .s lines
    (the .s parse desynced on interleaved labels AND never saw the encounter
    tree at all).  Two families:
    - family A (scripted battles): battleSettingsList0 0x080aee70 /
      BattleSettingsList1 0x080b0d88 (canon: bn6f.map:28302/28573), consumed
      by getBattleSettingsFromList0/List1 (asm/asm00_1.s:16046-16062, idx*0x10).
    - family B (random encounters): off_8020170 group tables
      (selectEncounterTableForMap_80AA5F4, asm/asm29.s:10338-10457):
      [0x08020170] = real-world table (21 groups, canon span
      0x08020190..0x080201E4) / [0x08020170+4] = internet table (23 words:
      0x080201E4 + 23*4 = 0x08020240 = pt_8020240, asm/asm01.s:555-580); mapgroup
      >= 0x80 uses the internet table at index group-0x80.  Group slot ->
      map array (16 words); map slot -> record list.  EVENT_67F/680/681 swap
      only the internet table (0x08020178/80/88, asm29.s:10348-10366).
    Records: 16 bytes (include/rom_structs/BattleSettings.inc; Background
    +0x4 proven by asm/asm03_0.s:14591-14593); byte[0]==0xff ends a list
    (T58's self-check); byte[4] Background; byte[7] gate handler index
    (JumpTable80AA6B8, asm29.s:10471); u32@0xc EnemySetupArrPtr ->
    0xF0-terminated 4-byte quads, quad[2] = enemy id (inventory.py:1060).

    T65 PASS 3 -- spawn dispatch and the 0x00 quad id.  Each quad dispatches
    on quad[0]>>4 into off_80073A0 (SpawnBattleObjectUsingBattleEntityConfig_
    8007368, asm/asm00_1.s:8569-8599: test (quad[0]&0xF0)==0xF0 ends the
    array, `lsr r0,#2` then `ldr r1,[table+r0]` = nibble*4 = entry n):
    0=spawnMegaMan_80073CC (asm00_1.s:8635-8648), 1=spawnEnemy_80073E2
    (enemy_idx = quad[2], asm00_1.s:8727), 2=spawnMysteryData_8007424,
    3=spawnRock_8007450, 8=spawnRockCube_80074FA, 9=spawnGuardian_800751C,
    10=spawnMetalCube_800748A.  quad[1] = panel x|y<<4, quad[3] low nibble =
    version.  So the "0x00 quad id" flagged uninterpreted in pass 1+2 is the
    PLAYER-SPAWN slot: 1045/1076 arrays carry quad[2]==0.  Per-array sets of
    the zero-id quads' dispatch nibbles, measured: {0}:991, {0,3}:38,
    {0,10}:12, {3}:2, {0,9}:2 -- i.e. 52 of the 54 arrays with a non-player
    zero-id quad ALSO carry the dispatch-0 (player) zero-id quad and only 2
    ({3}) are exclusively non-player; the non-player nibbles present are 3
    (spawnRock_8007450), 9 (spawnGuardian_800751C) and 10
    (spawnMetalCube_800748A) -- dispatch nibble 2 (spawnMysteryData) never
    appears.  ZERO dispatch-1 (enemy) quads have enemy_idx 0 in the whole
    census, so enemy_idx 0 never spawns from a formation.  PASS 3 residue:
    of the data region 0x080aee70..0x080b81eb, 80 bytes fall outside every
    record-list span (terminator 0xFF + 3-byte align pad = full 4-byte
    slot), 16-word map array, or referenced array (incl. 0xF0): the four
    unreferenced quad runs (52 bytes, residue_pass3.orphan_quad_runs) plus
    28 residual align-pad/sliver bytes (residue_pass3.residual_pad_bytes,
    addresses and byte values emitted) (all merges/addresses recomputed
    here, not assumed)."""
    rom = open(os.path.join(REF, "bn6f.gba"), "rb").read()

    def w(addr):
        return struct.unpack_from("<I", rom, addr - 0x08000000)[0]

    labels = {}
    for line in open(os.path.join(REF, "bn6f.map"), errors="replace"):
        m = re.match(r"\s+0x(0*8[0-9a-f]{7})\s+(\S+)", line)
        if m:
            labels.setdefault(int(m.group(1), 16), m.group(2))
    for m2 in re.finditer(r"(?m)^((?:byte|dword)_[0-9A-Fa-f]+)::", open(
            os.path.join(REF, "data", "BattleSettings.s"), errors="replace").read()):
        # byte_*/dword_* labels live only in data/BattleSettings.s (address
        # embedded in the name), not in bn6f.map -- carry them so family-A
        # formation arrays keep the label names the T50 baseline had.  The
        # file's single dword_ label (dword_80B083B) NAMES a referenced array
        # start whose first quad the old parse labeled separately as
        # byte_80B083F (an interior continuation label at +4 -- that overlap
        # is why the .s parse counted 297 arrays for 296 referenced starts).
        labels.setdefault(int(m2.group(1).split("_")[1], 16), m2.group(1))

    def walk_list(la):
        off = la - 0x08000000
        recs = []
        for i in range(4096):
            if rom[off + i * 0x10] == 0xFF:  # canon: T58 record[0]==0xff
                return recs, "ok"
            recs.append((la + i * 0x10,
                         rom[off + i * 0x10: off + i * 0x10 + 0x10]))
        return recs, "no-terminator"

    def formation_entries(ptr):
        off = ptr - 0x08000000
        ents = []
        for i in range(512):
            q = rom[off + i * 4: off + i * 4 + 4]
            if len(q) != 4 or q[0] == 0xF0:
                return ents, "ok"
            ents.append(q)
        return ents, "no-F0"

    # family A: the two .s labels, read as record streams from the ROM
    FAM_A = [("battleSettingsList0", 0x080AEE70),   # canon: bn6f.map:28302
             ("BattleSettingsList1", 0x080B0D88)]   # canon: bn6f.map:28573
    fam_a = {}
    for name, la in FAM_A:
        recs, term = walk_list(la)
        fam_a[la] = {"name": name, "recs": recs, "term": term}

    # family B: the encounter group tables
    ROOTS = {"default": 0x08020170, "EVENT_67F": 0x08020178,   # canon: asm29.s:10348-10371
             "EVENT_680": 0x08020180, "EVENT_681": 0x08020188}
    REAL_GROUPS = 21      # canon: off_8020190 block 0x08020190..0x080201E4
    INTERNET_GROUPS = 23  # canon: 0x080201E4 + 23*4 = 0x08020240 = pt_8020240 (asm/asm01.s:555-580)
    map_arrs, gas = {}, set()
    for vname, vaddr in ROOTS.items():
        for world, base, n in (("real", w(vaddr), REAL_GROUPS),
                               ("net", w(vaddr + 4), INTERNET_GROUPS)):
            for g in range(n):
                ga = w(base + 4 * g)
                gas.add(ga)
                map_arrs[(vname, world, g)] = [w(ga + 4 * m) for m in range(16)]
    list_addrs, owners, seen = [], {}, set()
    for vname in ROOTS:
        for world in ("real", "net"):
            n = REAL_GROUPS if world == "real" else INTERNET_GROUPS
            for g in range(n):
                for m, la in enumerate(map_arrs[(vname, world, g)]):
                    if la not in seen:
                        seen.add(la)
                        list_addrs.append(la)
                        owners[la] = (vname, world, g, m)
    fam_b = {}
    for la in list_addrs:
        recs, term = walk_list(la)
        fam_b[la] = {"recs": recs, "term": term}

    # formation arrays across BOTH families, with the census records that
    # reference each (PASS 3: every array is named by its referencing records)
    form, mismatches, refs = {}, [], {}

    def add_form(ptr, src):
        if ptr not in form:
            ents, st = formation_entries(ptr)
            form[ptr] = ents
            if st != "ok":
                mismatches.append((f"0x{ptr:08x}", st, src))
        refs.setdefault(ptr, []).append(src)
        return form[ptr]

    for la, L in list(fam_a.items()) + list(fam_b.items()):
        lname = L.get("name", f"0x{la:08x}")
        for ra, r in L["recs"]:
            add_form(struct.unpack_from("<I", r, 0xC)[0], f"rec 0x{ra:08x} ({lname})")
        if L["term"] != "ok":
            mismatches.append((f"0x{la:08x}", L["term"], L.get("name", "encounter list")))

    # PASS-3 residue scan: interval-account the whole data region.  Explained
    # = record lists (the full 4-byte terminator slot: 0xFF + 3-byte align
    # pad), the 16-word map arrays, and every referenced formation array
    # (quads + 0xF0).  What survives is 80 bytes: the four true orphan quad
    # runs (52) and residual align-pad/sliver bytes (28), both emitted.
    spans = [(la, la + 0x10 * len(L["recs"]) + 4)
             for la, L in list(fam_a.items()) + list(fam_b.items())]
    spans += [(ga, ga + 0x40) for ga in gas]
    for ptr, ents in form.items():
        spans.append((ptr, ptr + 4 * len(ents) + 1))
    merged = []
    for a, b in sorted(spans):
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([a, b])
    lo, hi = merged[0][0], max(b for _a, b in merged)
    residue = []
    for i, (a, b) in enumerate(merged):
        gb = merged[i + 1][0] if i + 1 < len(merged) else hi
        ga_ = b
        while ga_ < gb:
            # scan each unexplained byte range for 0xF0-terminated quad runs
            off = ga_ - 0x08000000
            j, ok = 0, True
            while True:
                if ga_ + 4 * j >= gb or j > 64:
                    ok = False
                    break
                if rom[off + 4 * j] >> 4 == 0xF:
                    break
                j += 1
            if not ok or j == 0:
                ga_ += 1
                continue
            end = ga_ + 4 * j
            tgt = struct.pack("<I", ga_)
            word_refs, pos = [], rom.find(tgt)
            while pos != -1:  # unaligned-inclusive: ANY word equal to the address
                if not (ga_ <= 0x08000000 + pos < end):
                    word_refs.append(f"0x{0x08000000 + pos:08x}")
                pos = rom.find(tgt, pos + 1)
            residue.append({
                "addr": f"0x{ga_:08x}", "end": f"0x{end:08x}", "quads": j,
                "bytes": end - ga_ + 1,
                "word_refs_in_rom": word_refs,
                "cite": f"reference/bn6f/bn6f.gba:0x{ga_:08x}..0x{end:08x} (unreferenced by any census record or ROM word)",
            })
            ga_ = end + 1
    # the non-orphan unaccounted bytes: align pads / 1-byte slivers, named
    # (the orphan-run ranges themselves are excluded here, not double-counted)
    orphan_iv = sorted((r["addr"], r["end"]) for r in residue)
    resid_pad = []
    for i, (a, b) in enumerate(merged):
        gb = merged[i + 1][0] if i + 1 < len(merged) else hi
        cur = b
        for oa, oe in orphan_iv:
            oa = int(oa, 16)
            oe = int(oe, 16) + 1  # include the run's 0xF0 terminator byte
            if oe <= cur or oa >= gb:
                continue
            if oa > cur:
                resid_pad.append({
                    "addr": f"0x{cur:08x}", "end": f"0x{oa:08x}", "bytes": oa - cur,
                    "byte_values": rom[cur - 0x08000000:oa - 0x08000000].hex(" "),
                })
            cur = max(cur, oe)
        if gb > cur:
            resid_pad.append({
                "addr": f"0x{cur:08x}", "end": f"0x{gb:08x}", "bytes": gb - cur,
                "byte_values": rom[cur - 0x08000000:gb - 0x08000000].hex(" "),
            })

    lists = {}
    for la, L in fam_a.items():
        lists[L["name"]] = {"records": len(L["recs"]), "term": L["term"],
                            "cite": f"reference/bn6f/bn6f.gba:0x{la:08x} (ROM walk; data/BattleSettings.s)"}
    lists["encounter_tree_off_8020170"] = {
        "lists": len(fam_b), "records": sum(len(L["recs"]) for L in fam_b.values()),
        "term_mismatches": sum(1 for L in fam_b.values() if L["term"] != "ok"),
        "cite": "reference/bn6f/bn6f.gba (ROM walk via asm/asm29.s:10371 off_8020170)",
        # PASS 3 (kept inside this entry so the section's list count stays 84)
        "residue_pass3": {
            "region": f"0x{lo:08x}..0x{hi - 1:08x}",
            "orphan_quad_runs": residue,
            "residual_pad_bytes": resid_pad,
            "note": "outside every span (record lists incl. full 4-byte terminator slot, 16-word map arrays, referenced arrays incl. 0xF0) fall 80 bytes = 52 orphan-run bytes (orphan_quad_runs) + 28 align-pad/sliver bytes (residual_pad_bytes, 0x00/0xff fill); none of the orphan runs is named by any ROM word",
        }}

    form_rows = []
    for ptr, ents in form.items():
        in_a = any(FAM_A[0][1] <= ptr < 0x080B1BBC for _ in [0])
        form_rows.append({
            "formation": labels.get(ptr, f"rom_{ptr:08x}"),
            "entries": len(ents),
            "enemy_ids": [f"{q[2]:02x}" for q in ents],
            "referenced_by": refs.get(ptr, []),
            "cite": f"reference/bn6f/bn6f.gba:0x{ptr:08x}"
                    + (" (within data/BattleSettings.s spans)" if in_a else " (unlabeled encounter-tree array)"),
            "status": "unrecorded",
        })
    form_rows.sort(key=lambda r: r["formation"])
    return lists, form_rows


# --------------------------------------------------------------- backdrops

def parse_backdrops(formation_lists):
    """T65: Background byte (BattleSettings+0x4; meaning proven by
    battleSettings_setBackground asm/asm03_0.s:14591-14593 strb
    r0,[BattleSettings_200AF60+0x4])
    census over EVERY record of BOTH families (see parse_formations for the
    walk) -- previously counted from the .s parse only, which saw the 461
    family-A records but none of the 779 encounter-tree ones.

    T65 PASS 3 closes the byte->art gap: battle init sub_8080DA0
    (asm/asm21.s:15-45, reached from initBattleStructsAndVram_80071D4 at
    asm/asm00_1.s:8435 after the record/ROM pointer lands in
    oBattleState_BattleSettings) reads the byte via sub_8081308
    (asm/asm21.s:469-523, ldrb [BattleSettings+0x4] at :473-475) and indexes
    THREE parallel tables by it: off_8080E34[r*0x10] scroll callbacks + LCD
    flags (asm21.s:79), off_8080F98[r] -> LoadBGAnimData
    (asm/asm03_0.s:21209; BGAnimData {gfx_src LZ77, gfx_dest 0x6000020,
    tilemap_src (+0xc offset), tilemap_dest_offset, palette_src,
    palette_dest 0x03001960, palette_size 0x20}) and off_8081220[r] ->
    LoadGFXAnims (asm21.s:389).  0xff is NOT an unset sentinel: sub_8081308
    turns it into the map default -- real-world 7 (asm21.s:515-516), net
    pt_808139C[group-0x80][map] byte (23-word table asm21.s:548-564),
    weather-puzzle maps (word_8081368, asm21.s:524-530) 0x15 flag-clear else
    0x10.  Explicit values in the census: 0x07/0x08 = the Comps1/Comps2 bg
    art in its two palette variants (id 6 is the RobotControlComp art)."""
    rom = open(os.path.join(REF, "bn6f.gba"), "rb").read()

    def w(addr):
        return struct.unpack_from("<I", rom, addr - 0x08000000)[0]

    def walk_list(la):
        off = la - 0x08000000
        recs = []
        for i in range(4096):
            if rom[off + i * 0x10] == 0xFF:  # canon: T58 record[0]==0xff
                return recs, "ok"
            recs.append(rom[off + i * 0x10: off + i * 0x10 + 0x10])
        return recs, "no-terminator"

    lists = []
    for name, la in (("battleSettingsList0", 0x080AEE70),   # canon: bn6f.map:28302
                     ("BattleSettingsList1", 0x080B0D88)):  # canon: bn6f.map:28573
        recs, _t = walk_list(la)
        lists.extend(recs)
    ROOTS = (("default", 0x08020170), ("EVENT_67F", 0x08020178),   # canon: asm29.s:10348-10371
             ("EVENT_680", 0x08020180), ("EVENT_681", 0x08020188))
    REAL_GROUPS = 21      # canon: off_8020190 block 0x08020190..0x080201E4
    INTERNET_GROUPS = 23  # canon: 0x080201E4 + 23*4 = 0x08020240 = pt_8020240 (asm/asm01.s:555-580)
    seen = set()
    for vname, vaddr in ROOTS:
        for base, n in ((w(vaddr), REAL_GROUPS), (w(vaddr + 4), INTERNET_GROUPS)):
            for g in range(n):
                ga = w(base + 4 * g)
                for m in range(16):
                    la = w(ga + 4 * m)
                    if la in seen:
                        continue
                    seen.add(la)
                    recs, _t = walk_list(la)
                    lists.extend(recs)
    values = {}
    for r in lists:
        values[r[4]] = values.get(r[4], 0) + 1
    BGANIM_TBL = 0x08080F98  # canon: off_8080F98, asm/asm21.s:213

    def art_of(v):
        p = w(BGANIM_TBL + 4 * v)
        if not p:
            return f"unused id (off_8080F98[{v}] = 0)"
        gfx, tmap, pal = w(p), w(p + 8), w(p + 0x10)
        s = (f"BGAnimData 0x{p:08x}: LZ77 tiles 0x{gfx:08x}, tilemap 0x{tmap:08x}, "
             f"palette 0x{pal:08x}")
        if v == 0x07:  # provenance: peeked -- same asset maps/Comps1/loader.s:240-246 (off_806DBD4) loads
            s += " = the Comps1/Comps2 maps' own bg art (palette byte_8616760)"
        if v == 0x08:  # provenance: peeked -- same asset maps/Comps1/loader.s:247-253 (off_806DBF0) loads
            s += " = the Comps1/Comps2 art's alternate-palette variant (same tiles/tilemap, palette byte_8616EC4)"
        return s

    rows = []
    for v, c in sorted(values.items()):
        rows.append({
            "background_byte": f"0x{v:02x}",
            "records_using_it": c,
            "role": "map-default" if v == 0xFF else "explicit-id",
            "art": ("map default, resolved by sub_8081308 asm/asm21.s:469-523: "
                    "real-world lists -> 7 (same art as explicit 0x07); net lists -> "
                    "pt_808139C[group-0x80][map] byte (measured family-B distribution: "
                    "ids 0,1,3,4,5,6,7,8,9,10,11,12,13,14,15,17,18,19,20 and 55 records "
                    "on weather-puzzle maps resolving 0x10-or-0x15)"
                    if v == 0xFF else art_of(v)),
            "cite": "asm/asm21.s:469-523 sub_8081308 ldrb [BattleSettings+0x4] -> off_8080F98[r] LoadBGAnimData (asm/asm03_0.s:21209) via sub_8080DA0 asm/asm21.s:15-45 (from initBattleStructsAndVram_80071D4 asm/asm00_1.s:8435); writer battleSettings_setBackground asm/asm03_0.s:14591-14593; reference/bn6f/bn6f.gba ROM walk"
                    + ("; 0x08 singleton = record 0 of battleSettingsList0 (reference/bn6f/bn6f.gba:0x080aee70)" if v == 0x08 else ""),
            "status": {
                0x07: ("verified (T70 static: same gfx/tilemap wrappers as the poked 0x08 art "
                       "(0x08616598/0x08616634), palette wrapper byte_8616760 -- variant 1, 0x08's is "
                       "byte_8616EC4; records carrying 0x07 are fetched by getBattleSettingsFromList1 "
                       "asm/asm00_1.s:16046-16062, e.g. 0x080b0d88+4 = 0x07 measured)"),
                0x08: ("verified (T70 poke on the battlestart route: [0x02001b9c] pinned 0x080aee70 "
                       "-> [ptr]+0x4 = 0x08; BG1 slot k=5 = tile 3 of the id-8 anim blob 0x08616904, "
                       "16/36 slots hold its tiles = script 0x0807FAC0 (off_8081220[8]) ran)"),
                0xFF: ("verified (T70: resolution branches asm/asm21.s:475-516 -- non-0xff passes "
                       "through (bne :476); 0xff -> net pt_808139C[group-0x80][map] ldrb :489, weather "
                       "override 0x15 :508, real-world 7 :516; battlestart route default = "
                       "pt_808139C[0x10][0] = 9, off_8081220[9] first script = "
                       "BattleBackdropGFXAnimScript_807FB98 = T22's byte-exact default-arena anim)"),
            }[v],
        })
    return rows


# --------------------------------------------------------------- NaviCust

# FOUND (T15, corrected by verifier): a 47-entry NCP battle-effect handler
# table -- navicust_jt_NCPs (asm/asm37_0.s:2111, 47 .word entries at lines
# 2112-2158, stride 4; 47 unique targets = 45 navicust_NCP_* +
# navicust_GigFldr1 + entry 0 = sub_813C808, a push {lr}; pop {pc} no-op
# stub). NOT a program-id table: dispatch keys off sub_813B9FC(id-1), which
# is not a lookup but r10[oToolkit_Unk2004190_Ptr] + 8*id -- an 8-byte-stride
# record array -- and the jump index is that record's halfword >> 2 (low 2
# bits masked off), so several programs can share an entry and entry order is
# a program-list order, not an id space. Handler bodies (asm37_0.s:2161-2600)
# contain 32 bl SetCurPETNaviStatsByte + 11 bl GetCurPETNaviStatsByte (e.g.
# navicust_NCP_SuperArmor -> SetCurPETNaviStatsByte(0, 0x23, 1)); reached
# through the stat-boost reload chain, i.e. adjacent to but NOT the
# enumeration behind the line's 19 NaviStats slots. Give/take chain:
# GiveNaviCustPrograms/TakeNaviCustPrograms
# (asm/asm03_1_1.s:8794/:8814) -> GiveItem 803cd98 (KeyItemsPtr byte array
# indexed directly by program id, no stride) -> reloadCurNaviStatBoosts_813c3ac
# (id 0x71 only) -> applyNaviStatsMaybe_813C458 (asm37_0.s:1796) ->
# applyNavicustPrograms_813C684 -> navicust_jt_NCPs. The rows below are
# the 19 named NaviStats slots those handlers write (a different axis).
NAVICUST_FIELDS = [
    "Attack", "Speed", "Charge", "BButton", "BPwrAtk", "FstBarr",
    "BLeftAbility", "CustomLevel", "MegaLevel", "GigaLevel", "Mood",
    "CustHPBug", "FloatShoes", "AirShoes", "UnderShirt", "SuperArmor",
    "EmotionBug", "ProcessingBug", "SlipRun", "ChipRecovery",
]


# ------------------------------------------------------------------
# T110: per-handler enumeration of navicust_jt_NCPs itself. Every entry
# walked in reference/bn6f/asm/asm37_0.s (labels at the cited lines; the
# jump-table entry for index k sits at asm37_0.s:2112+k). Effect column =
# what the body does: Set(slot,val)/Get-then-Set(slot) with the
# SetCurPETNaviStatsByte slot, or the composed calls it makes.
# `battle_relevant` = the handler writes at least one NaviStats slot that
# appears in the 19-slot DERIVED-FROM-HEADERS list above (the
# include/structs/NaviStats.inc named u8 slots this section counts).
# MEASURED COUNTS (T110): 47 entries = 1 no-op stub + 46 real handlers;
# 24 handlers are battle-relevant over 13 distinct slots
# (0x1 Attack, 0x2 Speed, 0x3 Charge, 0x6 FstBarr, 0x7 BLeftAbility,
# 0xa CustomLevel, 0xb MegaLevel, 0xc GigaLevel, 0x1b FloatShoes,
# 0x1c AirShoes, 0x1d UnderShirt, 0x23 SuperArmor, 0x35 SlipRun);
# 6 of the 19 slots have NO handler writing them (BButton 0x4, BPwrAtk 0x5,
# Mood 0xe, CustHPBug 0x19, EmotionBug 0x24, ProcessingBug 0x31); the
# other 22 handlers write 11 distinct slots NOT in the 19 (0x26, 0x27,
# 0x1e, 0x1f, 0x25 Humor, 0x33, 0x36, 0x5f Poem, 0x60, 0x61, 0xd) plus
# direct-r10 HP writes (0x3e..0x42). The SCOPE
# denominator 19 counts SLOTS, not handlers -- restated counts are in
# docs/coverage/navicust.md; the slot table above is unchanged.
NAVICUST_HANDLER_EFFECTS = [
    ("sub_813C808", 2162, "no-op stub (push {lr}; pop {pc})", "", False),
    ("navicust_NCP_SuperArmor", 2168, "Set(0x23,1)", "SuperArmor", True),
    ("navicust_NCP_Custom1", 2180, "Get(0xa)+1, max 8", "CustomLevel", True),
    ("navicust_NCP_Custom2", 2197, "Get(0xa)+2, max 8", "CustomLevel", True),
    ("navicust_NCP_MegFldr1", 2214, "Get(0xb)+1, max 10", "MegaLevel", True),
    ("navicust_NCP_MegFldr2", 2231, "Get(0xb)+2, max 10", "MegaLevel", True),
    ("navicust_GigFldr1", 2248, "Get(0xc)+1, max 10", "GigaLevel", True),
    ("navicust_NCP_FstBarr", 2265, "Set(6,1)", "FstBarr", True),
    ("navicust_NCP_Shield", 2276, "Set(7,0x3b)", "BLeftAbility", True),
    ("navicust_NCP_Reflect", 2287, "Set(7,0x8b)", "BLeftAbility", True),
    ("navicust_NCP_AntiDmg", 2298, "Set(7,0x3d)", "BLeftAbility", True),
    ("navicust_NCP_FlotShoe", 2309, "Set(0x1b,1)", "FloatShoes", True),
    ("navicust_NCP_AirShoes", 2320, "Set(0x1c,1)", "AirShoes", True),
    ("navicust_NCP_UnderSht", 2331, "Set(0x1d,1)", "UnderShirt", True),
    ("navicust_NCP_ChpShufl", 2342, "Set(0x60,1)", "unnamed 0x60", False),
    ("navicust_NCP_NumbrOpn", 2353, "Set(0x61,1)", "unnamed 0x61", False),
    ("navicust_NCP_SneakRun", 2364, "Set(0x1e,1)", "unnamed 0x1e", False),
    ("navicust_NCP_OilBody", 2375, "Set(0x27,2)", "unnamed 0x27", False),
    ("navicust_NCP_Fish", 2388, "Set(0x27,4)", "unnamed 0x27", False),
    ("navicust_NCP_Battery", 2401, "Set(0x27,8)", "unnamed 0x27", False),
    ("navicust_NCP_Jungle", 2414, "Set(0x27,0x10)", "unnamed 0x27", False),
    ("navicust_NCP_Collect", 2427, "Get(0x26)|2", "unnamed 0x26", False),
    ("navicust_NCP_Millions", 2441, "Set(0x33,1)", "unnamed 0x33", False),
    ("navicust_NCP_Humor", 2452, "Set(0x25,1)", "Humor (not in 19)", False),
    ("navicust_NCP_Poem", 2463, "Set(0x5f,1)", "Poem (not in 19)", False),
    ("navicust_NCP_SlipRunr", 2474, "Set(0x35,1)", "SlipRun", True),
    ("navicust_NCP_AutoHeal", 2485, "Set(0x36,1)", "unnamed 0x36", False),
    ("navicust_NCP_BustPack", 2496, "Get+3 max 4 for slots 1,2,3",
     "Attack+Speed+Charge", True),
    ("navicust_NCP_BodyPack", 2535, "calls SuperArmor+FlotShoe+AirShoes+UnderSht",
     "SuperArmor+FloatShoes+AirShoes+UnderShirt", True),
    ("navicust_NCP_FldrPak1", 2545, "calls MegFldr1+Custom1",
     "MegaLevel+CustomLevel", True),
    ("navicust_NCP_FldrPak2", 2553, "calls MegFldr2+Custom2",
     "MegaLevel+CustomLevel", True),
    ("navicust_NCP_BugStop", 2561, "Set(0x1f,1)", "unnamed 0x1f", False),
    ("navicust_NCP_Rush", 2572, "Get(0xd)|1", "unnamed 0xd", False),
    ("navicust_NCP_Beat", 2588, "Get(0xd)|2", "unnamed 0xd", False),
    ("navicust_NCP_Tango", 2604, "Get(0xd)|4", "unnamed 0xd", False),
    ("navicust_NCP_AttackPlus1", 2620, "Get(1)|4", "Attack", True),
    ("navicust_NCP_SpeedPlus1", 2637, "Get(2)|4", "Speed", True),
    ("navicust_NCP_ChargePlus1", 2654, "Get(3)|4", "Charge", True),
    ("navicust_NCP_AttckMAX", 2671, "Set(1,4)", "Attack", True),
    ("navicust_NCP_SpeedMAX", 2682, "Set(2,4)", "Speed", True),
    ("navicust_NCP_ChargMAX", 2693, "Set(3,4)", "Charge", True),
    ("navicust_NCP_HPPlus50", 2704, "r10 direct +50 max HP", "unnamed HP 0x3e..", False),
    ("navicust_NCP_HPPlus100", 2716, "r10 direct +100 max HP", "unnamed HP 0x3e..", False),
    ("navicust_NCP_HPPlus200", 2728, "r10 direct +200 max HP", "unnamed HP 0x3e..", False),
    ("navicust_NCP_HPPlus300", 2740, "r10 direct +300 max HP", "unnamed HP 0x3e..", False),
    ("navicust_NCP_HPPlus400", 2754, "r10 direct +400 max HP", "unnamed HP 0x3e..", False),
    ("navicust_NCP_HPPlus500", 2768, "r10 direct +500 max HP", "unnamed HP 0x3e..", False),
]


def parse_navicust_handlers():
    rows = []
    for idx, (sym, line, effect, slot, battle) in enumerate(NAVICUST_HANDLER_EFFECTS):
        rows.append({
            "index": idx,
            "handler": sym,
            "cite": f"asm/asm37_0.s:{line} (jt entry {2112 + idx})",
            "effect": effect,
            "slot": slot,
            "battle_relevant": battle,
            "status": "unrecorded",
        })
    return rows


def parse_navicust():
    rows = []
    for i, ln in enumerate(read_lines("include/structs/NaviStats.inc"), 1):
        m = re.match(r"\s*u8 (\w+).*loc=(0x[0-9a-fA-F]+|\d+)", ln)
        if m and m.group(1) in NAVICUST_FIELDS:
            rows.append({
                "slot": m.group(1), "offset": m.group(2),
                "cite": f"include/structs/NaviStats.inc:{i}",
                "status": "unrecorded",
            })
    return rows


# ------------------------------------------------------------------ output

def write_section(name, payload):
    os.makedirs(INV, exist_ok=True)
    path = os.path.join(INV, f"{name}.json")
    with open(path, "w") as f:
        json.dump(payload, f, indent=1)
        f.write("\n")


def md_table(rows, cols):
    head = "| " + " | ".join(c if isinstance(c, str) else c[0] for c in cols) + " |"
    sep = "|" + "|".join("---" for _ in cols) + "|"
    lines = [head, sep]
    for r in rows:
        cells = []
        for c in cols:
            key, cap = (c, 40) if isinstance(c, str) else c
            v = str(r.get(key, ""))
            cells.append(v[:cap])
        lines.append("| " + " | ".join(cells) + " |")
    return lines


def status_summary(rows):
    # virus families carry per-rank statuses
    flat = rows if not (rows and "ranks" in rows[0]) else \
        [r for fam in rows for r in fam["ranks"]]
    total = len(flat)
    # A row counts as verified when it carries a name AND a status other than
    # 'unrecorded' / 'bounded-GAP' / 'unverified' / 'GAP (T..' prefixes.
    bad_prefixes = ("unrecorded", "bounded-GAP", "unverified", "GAP (T")
    def is_verified(r):
        st = r.get("status", "")
        if not st:
            return False
        if any(st.startswith(p) for p in bad_prefixes):
            return False
        return True
    ver = sum(1 for r in flat if is_verified(r))
    return ver, total


# audit/caveat notes emitted into the generated section text (not source
# comments) so a reader of docs/SCOPE.md alone sees them
SECTION_NOTES = {
    "program advances (M4)":
        lambda pa_meta: (
            f"Pointer-word audit: the two tables hold {pa_meta['pointer_words']}"
            f" .word entries = {pa_meta['records']} recipe records + "
            + ("terminator " + "; ".join(pa_meta['terminators'])
               if pa_meta['terminators']
               else "no terminator (the second list runs into the next label)")
            + ", so the denominator 63 counts records, not pointer words."),
    "viruses (M5)":
        lambda meta: (
            "elem_hp caveat: the Struct2 word is `elem_hp u16 @0x00`; its HIGH"
            " nibble is the ELEMENT and the HP is the low 12 bits (the"
            " disassembly's own `.hword 0xXYYY` comment, asm/asm00_2.s:683),"
            " and offset 0 is the FIRST ROW of a row-per-level struct --"
            " Mettaur's rows read 0x0028/0x0050/0x0078/0x00A0. Never read"
            " 0x003C as 'the Gunner's HP constant': it is element 0, hp 60,"
            " row 0 of Gunner's rows."),
    "panels (M3)":
        lambda meta: (
            "T115 field walk (supersedes T33's 4-site sweep): object_setPanelType"
            " (object.s:2601) is a trampoline to _object_setPanelType, so 29 bl"
            " sites (asm31 x21, asm32 x2, asm00_2 x2, asm38 x4) + 13 direct strb"
            " oPanelData_Type sites + 4 data-fed writers (t4_0x56 whole-field"
            " nibble table byte_80E6D0C {2,3,6,7,8}; t3_0x4f area byte_80CE41E"
            " {4,7,6}; t3_0xc9 dword_80DE79C {FF,3,7,6}; navi-byte replay"
            " asm00_2.s:10776-10810 + sub_8013CC4 {3,4}) walked; BattleSettings"
            " records (1240) and formation arrays (1076) carry no panel-type"
            " byte (quad[0] dispatches only the 11 non-panel spawners asm00_1.s:8588-8621),"
            " and T70's byte_203CA50 pairs stages to BACKGROUNDS only. 0x8 is"
            " written by byte_80E6D0C nibbles; 0x0/0x5/0x9/0xA have no producer"),
    "formations (M8)":
        lambda meta: (
            f"T65 ROM-walk audit (supersedes the provisional .s arithmetic):"
            f" every record stream read from reference/bn6f/bn6f.gba itself --"
            f" family A scripted battles (battleSettingsList0 0x080aee70 /"
            f" BattleSettingsList1 0x080b0d88, bn6f.map:28302/28573, consumed by"
            f" getBattleSettingsFromList0/List1 asm/asm00_1.s:16046-16062 at"
            f" index*0x10) = 269+192 = 461 records + 297 0xF0-terminated"
            f" formation arrays (the old .s parse was exactly right HERE), plus"
            f" family B random-encounter tree (off_8020170 group tables," 
            f" selectEncounterTableForMap_80AA5F4 asm/asm29.s:10338-10457: 21"
            f" real-world groups / 23 internet groups (23 words proven by"
            f" 0x080201E4 + 23*4 = 0x08020240 = pt_8020240, asm/asm01.s:555-580),"
            f" group slot -> 16-word map array -> record"
            f" list; EVENT_67F/680/681 swap only the internet table) = 82"
            f" distinct lists, 779 records, 779 formation arrays -- ALL of it"
            f" missed by the .s parse (unlabeled ROM after 0x080b1bbc). Totals"
            f" 84 lists / 1240 records / 1076 formation arrays; every list"
            f" ends on a 0xff record[0] and every EnemySetupArrPtr reaches a"
            f" 0xF0 (mismatches 0). Records are 16 bytes"
            f" (include/rom_structs/BattleSettings.inc; the Background byte"
            f" +0x4 is proven by battleSettings_setBackground"
            f" asm/asm03_0.s:14591-14593 strb r0,[BattleSettings_200AF60+0x4]):"
            f" byte[0]==0xff terminator, byte[4] Background, byte[7] gate"
            f" handler index (JumpTable80AA6B8 asm29.s:10471), u32@0xc"
            f" EnemySetupArrPtr -> 4-byte quads, quad[0]==0xF0 stop, quad[2] ="
            f" enemy id. Formation arrays: 4-byte entries up to the 0xF0 stop"
            f" consumed by SpawnBattleObjectUsingBattleEntityConfig_8007368."),
    "statuses (M3)":
        lambda meta: (
            f"T18 verdict, CORRECTED by verifier-hyper re-run (all numbers are"
            f" generator output; reader/writer rules now strict vs loose, BOTH"
            f" printed): every bl object_setFlag1/2 + object_clearFlag(2) +"
            f" inline orr/str to oCollisionData_ObjectFlags1/2 is a"
            f" setter/clearer; every bl object_getFlag(2) + direct flags-field"
            f" load followed by a tst/and/lsr mask test is a reader. PER-BIT"
            f" reader = a mask EQUAL to the bit's own value; ANY-MASK mention ="
            f" a combined mask that merely carries the bit (a combined test"
            f" only proves SOME member mattered -- e.g. the 0xa000"
            f" BLIND|CONFUSED tst at asm31.s:171391-171393 credits both, the"
            f" 0x220000 tst at asm00_2.s:23375 credits SUPERARMOR). The"
            f" M3-facing reader count is the PER-BIT one: {meta['n_read']}/69"
            f" strict vs {meta['n_read_loose']} loose (loose-only bits:"
            f" FLINCHING, SUPERARMOR, UNK_29, flags2 bits 11/13/20). Written is"
            f" likewise per-bit-store: {meta['n_written']}/69 strict vs"
            f" {meta['n_written_loose']} loose -- FLINCHING's only setter"
            f" credit is the combined 0x400400 orr at asm00_2.s:18308"
            f" (playerFlinchAction_80174FE), so per-bit-store it is unwritten."
            f" The inline orr/str heuristic is UNSOUND and flagged in code: it"
            f" fires on ANY ldr/str/ldrh/strh touching the flags field,"
            f" including a whole-word bulk zero, and credits the first orr/bic"
            f" within +/-5 lines without checking that the orr targets the"
            f" flags register (4 credits this run). DAMAGE_*"
            f" (BattleObject.inc:119-123) have ZERO named sites in asm/ -- they"
            f" are carried in the damage word by the damage pipeline, so all"
            f" five stay header-derived. Table reconciliation, three SEPARATE"
            f" partitions (never added across): RECORDS --"
            f" {meta['table_records_only']} table-only (f4=7 + f2=6 + f5=6 +"
            f" f6=6) + {meta['records_overlap']} shared-family (f1=6 + f3=6) ="
            f" {meta['table_records']}; MASKS --"
            f" {len(meta['table_only_masks'])} table-only"
            f" ({','.join(meta['table_only_masks'])}) +"
            f" {len(meta['masks_overlap'])} overlap"
            f" ({','.join(meta['masks_overlap'])}) = 6; and"
            f" {len(meta['direct_only_masks'])} = the count of DISTINCT"
            f" directly-written flag2 masks OUTSIDE the table"
            f" ({','.join(meta['direct_only_masks'])}) -- a mask count, not a"
            f" record count. Table-mask direct sites measured: 0x8 HAS a direct"
            f" reader (asm00_2.s:17482-17485: object_getFlag2; mov r1,#8; tst;"
            f" bne locret), 0x20 has a direct setter (asm00_2.s:11368) and no"
            f" reader, 0x40/0x80 have neither, 0x10000/0x20000 UNMEASURED for"
            f" direct sites (budget); the observable read for those is on the"
            f" flags1 status bit the object.s per-frame status tick propagates"
            f" (e.g. object.s:5438-5452 clears flags1 0x8000 + flag2 0x80 when"
            f" the Confused timer Unk_1e expires), so battle_visible is judged"
            f" on the flags1 bit and is re-derived from the per-bit rule."
            f" Duration caveat: the 0x12c=300 at asm00_2.s:11364-11368 is a"
            f" SHARED 5-second status constant -- off_80141BC also feeds"
            f" oCollisionData_Unk_1e at 11375-11377 and setInvulnerableTime at"
            f" 11348/11356 -- do NOT fit 300 to BLIND. M3 scenario candidates"
            f" (per-bit reader + table-reachable): "
            + "; ".join(f"{s} reader {r} ({p})" for s, r, p in STATUS_M3_CANDIDATES)
            + ". Chip-id caveat: the fixture hand (FIXTURE.md +13) can carry"
            " any chip id, but the cannon/wave rows' fired chips inflict no"
            " status; which chip id writes which StatusEffectFinal value is"
            " NOT pinned here (the setCollisionStatusEffect callers are the"
            " asm31.s per-attack effect routines) -- that pinning is M4 work."),
    "backdrops (M8)":
        lambda meta: (
            "Sentinel note: Background 0xff on 1047 of 1240 records (T65 ROM walk) is"
            " counted as an UNSET sentinel, not backdrop id 255. What this section"
            " counts after excluding 0xff: 2 set values (0x07 on 192 records, 0x08 on"
            " 1 record); the distinct-value denominator 3 includes the"
            " sentinel row so the sentinel itself stays auditable."
            " T70 measured mapping (closes the T15 GAP): the byte's readers are"
            " battleSettings_setBackground (asm/asm03_0.s:14592 strb"
            " r0,[BattleSettings_200AF60+0x4]; callers asm03_0.s:14617"
            " battleSettings_802D2B2 -- its argument is byte_203CA50[2*(stage-1)+1],"
            " ldrb [r6,#1] :14615, the stage-pair word copied from dword_203F568 by"
            " battle_copyStructsIncludingBattleStats_800b2d8 asm/asm00_1.s:17871-17874 --"
            " and asm33.s:16529 sub_812B768, caller-supplied) and battle init"
            " sub_8080DA0 (asm/asm21.s:17 bl sub_8081308; r ="
            " [r10->BattleState.BattleSettings]+4 ldrb :474, cmp #0xff :475, bne"
            " passthrough :476). The art SELECT is the table load asm/asm21.s:32"
            " ldr r0,[r6,r1] = off_8080F98[r] -> LoadBGAnimData :33, plus :36"
            " off_8081220[r] -> LoadGFXAnims :37; 0xff resolves BEFORE the index: net"
            " pt_808139C[group-0x80][map] ldrb :489, weather override 0x15 :508,"
            " real-world 7 :516. Per byte, the BGAnimData {gfx wrapper"
            " (sz_words,LZ77_off); dest 0x6000020; tilemap wrapper (w,h,LZ77@+0xc);"
            " palette wrapper (data@+4)} decodes as: 0x07 and 0x08 share gfx 0x08616598"
            " (17 tiles, LZ77 at 0x086165b0) and tilemap 0x08616634 (32x32), differing"
            " only in palette (0x08616760 vs 0x08616EC4) = the Comps1/Comps2 map bg art"
            " (the maps' own BGAnimData off_806DBD4/off_806DBF0 -- cited by"
            " reference/bn6f/maps/Comps1/loader.s:224-227 -- reuse the same"
            " gfx/tilemap wrappers; id 6's gfx 0x08610b04 is cited by"
            " reference/bn6f/maps/RobotControlComp/loader.s:133); 0xff on the battlestart"
            " route resolves to id 9 = the default net arena: anim off_8081220[9] first"
            " script = BattleBackdropGFXAnimScript_807FB98 = T22's byte-exact art."
            " Poked fielding (one capture): [0x02001b9c] pinned 0x080aee70 on the"
            " battlestart route (watch: natural 0x080b4be8 at frame 60 only), byte at"
            " [ptr]+0x4 = 0x08, BG1 VRAM slot k=5 (0x060000A0) = tile 3 of the id-8 anim"
            " blob 0x08616904, 16/36 slots holding its tiles -- script 0x0807FAC0"
            " (off_8081220[8]) ran. UNVERIFIED: the palette leg (bank 0 read white at the"
            " dump frame -- the poked scripted record's battle repainted palettes) and no"
            " live poke of 0x07 itself."
            " T22 art-content chain (verified as data, settled F47's open"
            " (c)): BattleBackdropGFXAnimScript_807FB98 (data/dat20.s:148;"
            " initial gfx_anim_4bit_tile_copy gfx_dest=unk_6000040"
            " num_tiles=0x24 at :149, then 29 gfx_anim_data_ptr entries"
            " :150-178, gfx_anim_loop :179) schedules the 7 tile tables"
            " BattleBackdropTiles0-6_807FE40/807FCD8/807FC90/807FD20/"
            " 807FD68/807FDB0/807FDF8 (dat20.s:222/:187/:181/:193/:201/"
            " :208/:216, 36 halfwords each, blob indices into"
            " GFXAnimTileBlob_8617488) copied as 36 tiles to 0x06000040"
            " (VRAM slots 2..37; slot 1 = the blank filler the map's empty"
            " cells point at). tools/backdrop_export.py's FRAMES[s] == [0] +"
            " table byte-exact for all 7 tables (36/36 slots x 7, T22 step"
            " 1). Canon VRAM is SLOTWISE faithful: canon slot k (slots 1..37"
            " of the 0x06000000:0x800 window, slot k at window offset k*32)"
            " holds FRAMES[step][k-1], 37/37 at all 7 steps on the kept F47"
            " tile dumps (named captures 140/148/156/164/172 -> steps"
            " 5/6/0/1/2; steps 3 and 4 attested in the same dump at caps"
            " 16-27 and 68-83, outside F47's compared 40-frame window), and"
            " the relation is pinned by the map: canon's BG1 cell ids are the"
            " asset MAP values +1 (1..37, no 0), the port's are +512. The"
            " port is NOT slotwise faithful (1/37 at every capture -- only"
            " the blank tile aligns): it permutes the tile array AND its map,"
            " and the two cancel -- composed render (map composed with the"
            " tile array) vs the asset's composed render: 1024/1024 cells"
            " identical for canon at all 7 steps and the port at 6 of 7"
            " sampled steps (the port's earliest step-0 capture reads 0/1024"
            " until its map write lands, ~cap 30 -- the tile write runs ahead"
            " of the map write in the port's first frames). The permutation's"
            " provenance ('map-scan first-occurrence order') is the worker's"
            " label, unconfirmed -- hypothesis, not result. Naive-grid control"
            " reproduces F47's figure IN MAGNITUDE only: window tiles 0..1152"
            " vs flat s*37+k gives best 2/37 (cap 174 [2,2,1,0,1,0,2]; cap 39"
            " [2,2,2,1,1,1,1]; no step 3), the +1-shifted variant s*37+(k-1)"
            " reads 36/37 (the window's first 32 bytes are not a backdrop"
            " slot), the corrected slot alignment (offsets 32..1216, slot k ="
            " FRAMES[step][k-1]) reads 37/37 -- counting convention stated so"
            " the next reader gets the same figure. FORWARD-BLOCKING LIMITS:"
            " (i) do not extend 37/37 x 7 to the palette -- bank 0 rests only"
            " on the exporter's 'read from a live battle' comment, no palette"
            " watch in the kept dumps; (ii) byte->art mapping CLOSED by T70"
            " (mapping note above + row statuses; the asm33.s:4168-4195"
            " compare chain is a different, per-scene loader, not this"
            " table); (iii) the typed"
            " constants in this note (29/7/36/37/37) are NOT re-verified by"
            " the generator -- if FRAMES ever changes, SCOPE keeps asserting"
            " 37/37 forever ('generated' here is assembled prose, not"
            " machine-checked); (iv) this CLOSES F47's stated open item"
            " (docs/worklog/F47.md:156-158 and :262 already disclaimed the"
            " naive grid and named this recipe) -- F47's phase headline is"
            " untouched (capture-to-capture change counts, no asset"
            " indexing). T22 steps 2-3 + verifier audit + wording pass,"
            " /tmp/bn-t22-backdrop-content/"),
    "navicust battle effects (M7)":
        lambda meta: (
            "T15 verdict (corrected from 'program-id enumeration'): FOUND --"
            " a 47-entry NCP battle-effect handler table: navicust_jt_NCPs"
            " (asm/asm37_0.s:2111), 47 .word entries (lines 2112-2158),"
            " stride 4; 47 unique targets = 45 navicust_NCP_* +"
            " navicust_GigFldr1 + entry 0 = sub_813C808 (push {lr};"
            " pop {pc} no-op stub). Dispatched by"
            " applyNavicustPrograms_813C684 (asm/asm37_0.s:2012) over the 8"
            " equipped-program slots (byte_2006DD8, cleared/filled in the"
            " same routine); the jump index is sub_813B9FC(id-1) record's"
            " halfword >> 2 (low 2 bits masked off), where sub_813B9FC is NOT"
            " a lookup but r10[oToolkit_Unk2004190_Ptr] + 8*id -- an"
            " 8-byte-stride record array -- so several programs can share an"
            " entry and entry order is a program-list order, not an id space."
            " Handler bodies (asm37_0.s:2161-2600) contain 32 bl"
            " SetCurPETNaviStatsByte + 11 bl GetCurPETNaviStatsByte (e.g."
            " navicust_NCP_SuperArmor -> SetCurPETNaviStatsByte(0, 0x23, 1))"
            " -- the SCOPE line may claim the table for the NCP battle-effect"
            " handler side, NOT for a program-id enumeration; it is adjacent"
            " to but not the enumeration behind this section's 19 NaviStats"
            " slots (a different axis); per-handler battle-relevance is NOT"
            " classified here. Give/take chain walked:"
            " GiveNaviCustPrograms (asm/asm03_1_1.s:8794) -> GiveItem 803cd98"
            " (KeyItemsPtr[program_id], plain byte array, no stride) ->"
            " reloadCurNaviStatBoosts_813c3ac (asm37_0.s:1719, id 0x71 only)"
            " -> applyNaviStatsMaybe_813C458 (asm37_0.s:1796) ->"
            " applyNavicustPrograms_813C684."),
}


def regenerate_scope(sections, pa_meta=None, status_meta=None):
    scope_path = os.path.join(REPO, "docs", "SCOPE.md")
    with open(scope_path) as f:
        old = f.read()
    marker = "## Per-item tables"
    idx = old.index(marker)
    head = old[:idx + len(marker)]
    out = [head, ""]
    out.append(
        "(GENERATED by tools/inventory.py -- T10. Do not hand-edit below this"
        " line; rerun `python3 tools/inventory.py`. Status vocabulary:"
        " `unrecorded` / `recorded` / `ported` / `verified` (trace + pixel"
        " parity as data) / `verified-pixels` (pixel-verified through our own"
        " code, not yet as data). Category states: FOUND = table symbol +"
        " file:line; DERIVED-FROM-CODE = routine + per-item sites; GAP = no"
        " table located, search trail named.)")
    out.append("")
    out.append("| milestone | section | state | verified / total |")
    out.append("|---|---|---|---|")
    for m, (name, state, rows) in sections:
        ver, total = status_summary(rows)
        out.append(f"| {m} | {name} | {state} | {ver} / {total} |")
    out.append("")
    for m, (name, state, rows) in sections:
        cols = COLUMN_SETS.get(name)
        if not cols and name != "viruses (M5)":
            continue
        out.append(f"### {name} ({state})")
        out.append("")
        note = SECTION_NOTES.get(name)
        if note:
            arg = pa_meta if name == "program advances (M4)" else (
                status_meta if name == "statuses (M3)" else None)
            out.append(f"Note: {note(arg)}")
            out.append("")
        if name == "viruses (M5)":
            # one line per family rank (deduped by version byte)
            out.append("| ai_index | family routine | version byte | spawn enemy_idxs | hp (low 12 bits of Struct2 row) | cite | status |")
            out.append("|---|---|---|---|---|---|---|")
            for fam in rows:
                for rk in fam["ranks"]:
                    spawns = ",".join(str(x) for x in rk["spawn_enemy_idxs"])
                    out.append(
                        f"| {fam['ai_index']:#x} | {fam['think']} | "
                        f"{rk['version_byte']} | {spawns} | "
                        f"{rk['elem_hp_row0_raw']} | {rk['cite']} | {rk['status']} |")
        else:
            out.extend(md_table(rows, cols))
        out.append("")
    with open(scope_path, "w") as f:
        f.write("\n".join(out) + "\n")


COLUMN_SETS = {
    "viruses (M5)": [("ai_index", 10), ("family routine", 24), ("cite", 40), "status"],
    "cybeasts (M6)": [("form", 24), ("form_cite", 34), ("sprite_category_cite", 44), "status"],
    "chips (M4)": [("id", 6), ("name", 12), "codes_decoded", "class", "element", ("damage", 8), ("cite", 40), "status"],
    "program advances (M4)": [("list", 12), ("result_name", 10), ("result_chip", 6), ("ingredients", 24), ("cite", 48), "status"],
    "navis + cybeasts (M6)": [("index", 6), ("navi", 24), ("ai_arm", 30), ("pattern", 22), ("act", 22), ("cite", 46), "status"],
    "forms (M7)": [("tf_value", 8), ("form", 22), ("charge_shot", 34), ("charge_cite", 24), "status"],
    "panels (M3)": [("type", 6), ("meaning", 24), ("flag_word", 10), ("writer", 42), ("reader", 44), "status"],
    "statuses (M3)": [("bit", 36), ("value", 12), ("setter", 40), ("reader", 40), ("battle_visible", 14), ("via_table", 10), ("cite", 40), "status"],
    "formations (M8)": [("formation", 14), ("entries", 8), ("enemy_ids", 24), ("cite", 30), "status"],
    "backdrops (M8)": [("background_byte", 12), ("records_using_it", 10), ("cite", 52), "status"],
    "navicust battle effects (M7)": [("slot", 16), ("offset", 10), ("cite", 40), "status"],
}


def main():
    ensure_ref()
    chips = parse_chips()
    pas = parse_program_advances()
    viruses, enemy_meta = parse_viruses()
    navis = parse_navis()
    forms, charge_extra = parse_forms()
    panels = parse_panels()
    statuses, status_meta = parse_statuses()
    lists, form_rows = parse_formations()
    backdrops = parse_backdrops(lists)
    navicust = parse_navicust()
    navicust_handlers = parse_navicust_handlers()

    write_section("chips", {"generator": "tools/inventory.py", "rows": chips})
    write_section("program_advances", {"generator": "tools/inventory.py", "rows": pas})
    write_section("viruses", {"generator": "tools/inventory.py (enemy rows: tools/rom_enemy_tables.py)",
                              "identity_meta": enemy_meta, "rows": viruses})
    write_section("navis", {"generator": "tools/inventory.py", "rows": navis})

    # the Cybeasts as their own rows: the TF enum's beast/over values plus
    # the dedicated sprite categories (canon: constants/enums/
    # sprite_categories.inc:17-18 G_BEAST_0B/F_BEAST_0C)
    sprite_cites = {}
    for i, ln in enumerate(read_lines("constants/enums/sprite_categories.inc"), 1):
        sm = re.match(r"\s*map_enum (\w*BEAST_\w+) //", ln)
        if sm:
            sprite_cites[sm.group(1)] = f"constants/enums/sprite_categories.inc:{i}"
    cybeasts = []
    for t in TF_ENUM:
        if "BEAST" not in t["name"]:
            continue
        cat = t["name"].replace("TF_", "")
        cybeasts.append({
            "form": t["name"],
            "form_cite": t["cite"],
            "sprite_category_cite": sprite_cites.get(cat, ""),
            "status": "unrecorded",
        })
    write_section("cybeasts", {"generator": "tools/inventory.py", "rows": cybeasts})
    write_section("forms", {"generator": "tools/inventory.py", "rows": forms,
                            "charge_shot_table_extra": charge_extra,
                            "charge_shot_table_cite": "asm/asm00_2.s:5789 off_80117D4"})
    write_section("panels", {"generator": "tools/inventory.py", "rows": panels})
    write_section("statuses", {"generator": "tools/inventory.py",
                               "table_meta": {
                                   k: v for k, v in status_meta.items()
                                   if k != "families"},
                               "rows": statuses})
    write_section("formations", {"generator": "tools/inventory.py",
                                 "battle_settings_lists": lists, "rows": form_rows})
    write_section("backdrops", {"generator": "tools/inventory.py", "rows": backdrops})
    write_section("navicust", {"generator": "tools/inventory.py", "rows": navicust})
    # T110: per-handler enumeration as its OWN section JSON -- deliberately
    # NOT folded into the navicust slot rows, so the published SCOPE M1
    # denominator (0/19 slots) is unchanged until the human restates it
    # (measured counts: 24/47 handlers battle-relevant over 13 slots).
    write_section("navicust_handlers", {"generator": "tools/inventory.py",
                                        "rows": navicust_handlers})

    nrec = sum(v["records"] for v in lists.values())
    # computed, not a literal: 2 scripted lists + the encounter tree's lists
    nlists = sum(v.get("lists", 1) for v in lists.values())
    f1w = sum(1 for r in statuses if r['bit'].startswith('OBJECT_FLAGS_')
              and not r['bit'].startswith('OBJECT_FLAGS_2_')
              and r['_counts'][0] > 0)
    f2w = sum(1 for r in statuses if r['bit'].startswith('OBJECT_FLAGS_2_')
              and r['_counts'][0] > 0)
    f1r = sum(1 for r in statuses if r['bit'].startswith('OBJECT_FLAGS_')
              and not r['bit'].startswith('OBJECT_FLAGS_2_')
              and r['_counts'][2] > 0)
    f2r = sum(1 for r in statuses if r['bit'].startswith('OBJECT_FLAGS_2_')
              and r['_counts'][2] > 0)
    sections = [
        ("M1", ("chips (M4)", "FOUND: data/ChipDataArr.s:2 ChipDataArr_8021DA8 (411 x chip_data_struct, stride 0x2c, include/rom_structs/ChipData.inc)", chips)),
        ("M1", ("program advances (M4)", "FOUND: asm/asm03_0.s off_802BCB0 + off_802BC60 recipe-pointer tables (records [count][matcher][result u16][chip,code]*n)", pas)),
        ("M1", ("viruses (M5)", "FOUND via T12: byte_80182C4 identity rows + off_8109150 Struct2 (tools/rom_enemy_tables.py)", viruses)),
        ("M1", ("navis + cybeasts (M6)", "FOUND: asm/asm31.s off_80F24D8/off_80F253C/off_80F25A0", navis)),
        ("M1", ("cybeasts (M6)", "FOUND: TF enum values + dedicated sprite categories (constants/enums/sprite_categories.inc:17-18)", cybeasts)),
        ("M1", ("forms (M7)", "FOUND: constants/constants.inc TF enum + charge-shot dispatch off_80117D4 (asm/asm00_2.s:5789)", forms)),
        ("M1", ("panels (M3)", "FOUND: word_3007924 (IWRAM copy, asm/asm38.s:4242-4249) = IWRAMRoutinesROMLocation+0x1E24 = 0x081D7E24 in ROM (word_3007924 is in no map line; derived from start.s's copy: bn6f.map:34342 IWRAMRoutinesROMLocation = 0x081d6000 -> 0x3005B00 len 0x1ed4, 0x3007924-0x3005B00=0x1E24): 13 words, stride 4, one per panel type 0x0..0xC, OR-ed into oPanelData_Flags by _object_updatePanelParameters (asm/asm38.s:4213-4219)", panels)),
        ("M1", ("statuses (M3)",
                "DERIVED-FROM-CODE (T18, corrected by verifier re-run): per-bit canonical sites"
                f" measured by walking every object_setFlag/clearFlag/getFlag call and inline flags-field orr/str/tst in"
                f" reference/bn6f/asm -- written per-bit-store {status_meta['n_written']}/69"
                f" (flags1 {f1w}/32, flags2 {f2w}/32, DAMAGE 0/5; loose any-mask mention {status_meta['n_written_loose']}/69),"
                f" per-bit readers {status_meta['n_read']}/69 (flags1 {f1r}/32, flags2 {f2r}/32; loose any-mask mention {status_meta['n_read_loose']}/69),"
                f" {status_meta['n_unread']} with no per-bit reader, {status_meta['n_written_read']} both written and read per-bit;"
                f" nearest per-status table off_80209EC (data/dat01.s:155, via sub_801A554 asm/asm00_2.s:22211)"
                f" holds {status_meta['table_records']} records -- RECORDS: {status_meta['table_records_only']} table-only"
                f" (f4=7+f2=6+f5=6+f6=6) + {status_meta['records_overlap']} shared-family (f1=6+f3=6) = 37; MASKS:"
                f" {len(status_meta['table_only_masks'])} table-only ({','.join(status_meta['table_only_masks'])})"
                f" + {len(status_meta['masks_overlap'])} overlap ({','.join(status_meta['masks_overlap'])}) = 6; and"
                f" {len(status_meta['direct_only_masks'])} distinct directly-written flag2 masks OUTSIDE the table"
                f" ({','.join(status_meta['direct_only_masks'])}) -- a mask count, not a record count; table-mask direct sites:"
                f" 0x8 direct reader asm/asm00_2.s:17482-17485, 0x20 direct setter asm/asm00_2.s:11368 / no reader, 0x40/0x80 neither,"
                f" 0x10000/0x20000 unmeasured; M3 candidates (per-bit readers): "
                + " / ".join(f"{s} ({r})" for s, r, _p in STATUS_M3_CANDIDATES),
                statuses)),

        ("M1", ("formations (M8)", f"ROM-WALK (T65): reference/bn6f/bn6f.gba record streams -- off_8020170 encounter tree (asm/asm29.s:10371) + scripted battleSettingsList0 0x080aee70 (bn6f.map:28302) / BattleSettingsList1 0x080b0d88 (bn6f.map:28573, getBattleSettingsFromList0/List1 asm/asm00_1.s:16046-16062), {nrec} records over {nlists} lists (2 scripted + {nlists - 2} encounter-tree), {len(form_rows)} 0xF0-terminated formation arrays (section denominator = {len(form_rows)} arrays, all rows status unrecorded) -- old .s parse held 461 records / 297 arrays and missed the whole encounter tree (779 records, 779 arrays); mismatches 0", form_rows)),
        ("M1", ("backdrops (M8)", "DERIVED-FROM-RECORDS, byte->art CLOSED (T65 pass 3; mapping verified + poked T70): BattleSettings.Background byte values (writer battleSettings_setBackground asm/asm03_0.s:14592; for scripted battles also sourced from byte_203CA50 stage pairs by battleSettings_802D2B2 asm/asm03_0.s:14599); the byte is read at battle init by sub_8081308 (asm/asm21.s:469-523, ldrb [BattleSettings+0x4] :473-475, called from sub_8080DA0 asm/asm21.s:15-45 via initBattleStructsAndVram_80071D4 asm/asm00_1.s:8435) and indexes off_8080F98[r] -> LoadBGAnimData (asm/asm03_0.s:21209) = explicit LZ77 tiles/tilemap/palette pointers: 0x07/0x08 = the Comps1/Comps2 bg art in its two palette variants (id 6 is the RobotControlComp art), 0xff = map default (real 7, net pt_808139C[group-0x80][map] asm/asm21.s:548-564, weather-puzzle maps 0x15/0x10) -- census in rows below; ART CONTENT of the scheduled field anim verified as data T22: BattleBackdropGFXAnimScript_807FB98 dat20.s:148, 29 entries :150-178 -> 7 tile tables dat20.s:181-225 byte-exact vs assets/backdrop.bin FRAMES; canon SLOTWISE 37/37 x 7 steps (slot k = FRAMES[step][k-1]; canon BG1 cell ids = asset MAP +1, port's = asset MAP +512); port permutes tile array AND map, the two cancel (composed render 1024/1024 cells x7 canon, 6/7 port, on kept F47 dumps -- port not slotwise faithful, 1/37; permutation provenance 'map-scan first-occurrence order' unconfirmed hypothesis)", backdrops)),
        ("M1", ("navicust battle effects (M7)", "FOUND (NCP battle-effect handler table): asm/asm37_0.s:2111 navicust_jt_NCPs, 47 words stride 4 (45 navicust_NCP_* + navicust_GigFldr1 + a no-op stub; NOT a program-id enumeration), dispatched by applyNavicustPrograms_813C684 (asm/asm37_0.s:2012, index = sub_813B9FC(id-1) record halfword >> 2, sub_813B9FC = r10[oToolkit_Unk2004190_Ptr] + 8*id record array); handlers 32x SetCurPETNaviStatsByte + 11x GetCurPETNaviStatsByte (asm37_0.s:2161-2600); give/take chain GiveNaviCustPrograms asm/asm03_1_1.s:8794 -> GiveItem 803cd98 -> reloadCurNaviStatBoosts_813c3ac -> applyNaviStatsMaybe_813C458; slot rows below DERIVED-FROM-HEADERS (NaviStats.inc)", navicust)),
    ]
    regenerate_scope(sections, pa_meta={
        "pointer_words": sum(t["pointer_words"] for t in PA_TABLES),
        "records": sum(t["records"] for t in PA_TABLES),
        "terminators": [t["terminator"] for t in PA_TABLES if t["terminator"]],
    }, status_meta=status_meta)

    for m, (name, state, rows) in sections:
        ver, total = status_summary(rows)
        print(f"{name}: {state} -- verified {ver}/{total}")
    rch = [r for r in chips if r["reachable"]]
    ver_r = sum(1 for r in rch if r["status"] != "unrecorded")
    print(f"chips (M4) reachable set: verified {ver_r}/{len(rch)} "
          f"(R={len(rch)}: ids 1..202+221..255, the folder-reachable gate -- "
          f"id<0x19B, >=1 code, a TextScriptChipNames0 name; "
          f"docs/coverage/chips.md)")


if __name__ == "__main__":
    main()
