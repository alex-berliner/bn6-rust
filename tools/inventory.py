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
    """Ordered .string entries of TextScriptChipNames0.s (index = chip id,
    index 0 is the 'MegaBstr' placeholder)."""
    lines = read_lines("data/textscript/TextScriptChipNames0.s")
    names = []
    for ln in lines:
        m = STRING_RE.match(strip_comment(ln))
        if m:
            names.append(m.group(1).rstrip("@"))
    return names


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
    rows = []
    for i, (line, f) in enumerate(blocks):
        codes = int(f["codes"], 16)
        libtype = int(f["library_type"], 16)
        elem = int(f["chip_element"], 16)
        name = names[i] if 0 < i < len(names) else ""
        status = ("verified-pixels" if i in verified_ids
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
            "cite": f"data/ChipDataArr.s:{line}",
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
    {"symbol": "off_802BCB0", "line_hint": "off_802BCB0:", "list": "recognition list (sub_8029520)"},
    # canon: off_802BC60
    {"symbol": "off_802BC60", "line_hint": "off_802BC60:", "list": "second list"},
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
        s, e = label_bounds(lines, "off_8109150")
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

NAVI_STRUCT1 = "off_80F24D8"  # asm/asm31.s:123439
NAVI_STRUCT2 = "off_80F253C"  # asm/asm31.s:123490
NAVI_ACT = "off_80F25A0"      # asm/asm31.s:123540


def parse_navis():
    lines = read_lines("asm/asm31.s")
    def words(label):
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
    s1, s2, act = words(NAVI_STRUCT1), words(NAVI_STRUCT2), words(NAVI_ACT)
    n = min(len(s1), len(s2), len(act))
    navi_names = {e["value"]: e["name"] for e in NAVI_ENUM}
    rows = []
    for i in range(n):
        hp = navi_row0_hp(s2[i][0])
        rows.append({
            "index": i,
            "navi": navi_names.get(i, f"// unnamed: navi-table index {i}"),
            "struct1": f"{s1[i][0]} (asm/asm31.s:{s1[i][1]})",
            "struct2": f"{s2[i][0]} (asm/asm31.s:{s2[i][1]})",
            "act": f"{act[i][0]} (asm/asm31.s:{act[i][1]})",
            "struct2_row0_raw": f"0x{hp:04x}" if hp is not None else "",
            "cite": f"asm/asm31.s:{s1[i][1]},{s2[i][1]},{act[i][1]}",
            "status": "unrecorded",
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
    s, e = label_bounds(lines, "off_80117D4")
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

# DERIVED-FROM-CODE: the ROM's panel mutations are named object_* routines
# (asm/object.s); the code has no type->routine table (recon T10 §6).
PANEL_ROUTINES = [
    "panel_800BFC4", "object_getPanelParameters", "object_crackPanel",
    "object_breakPanel", "object_breakPanelLoud", "object_panel_setPoison",
    "object_highlightPanel", "object_setPanelType", "object_setPanelAlliance",
    "object_setPanelAllianceTimerLong", "object_setPanelAllianceTimerShort",
    "object_setPanelTypeBlink", "object_checkPanelParameters",
]


def parse_panels():
    rows = []
    for sym in PANEL_ROUTINES:
        ln = find_symbol_line("asm/object.s", sym)
        rows.append({
            "routine": sym,
            "cite": f"asm/object.s:{ln}" if ln else "// unnamed: line not resolved",
            "status": "unrecorded",
        })
    return rows


# ---------------------------------------------------------------- statuses

# DERIVED-FROM-HEADERS: the status bits are the named struct_const bits of
# CollisionData.inc / BattleObject.inc (ROM struct headers, not wiki).
def parse_statuses():
    rows = []
    for rel, prefix in (("include/structs/CollisionData.inc", "OBJECT_FLAGS_"),
                        ("include/structs/BattleObject.inc", "DAMAGE_")):
        for i, ln in enumerate(read_lines(rel), 1):
            m = re.match(rf"\s*struct_const ({prefix}\w+),\s*(0x[0-9a-fA-F]+)", ln)
            if m:
                rows.append({
                    "bit": m.group(1), "value": m.group(2),
                    "cite": f"{rel}:{i}", "status": "unrecorded",
                })
    return rows


# -------------------------------------------------------------- formations

def parse_formations():
    lines = read_lines("data/BattleSettings.s")
    labels = split_labels("data/BattleSettings.s")
    lists = {}
    for name, ln in labels:
        m = re.match(r"battleSettingsList(\d*)", name, re.I)
        if m:
            s, e = label_bounds(lines, name)
            # records: 12 .byte values + 1 .word pointer; list ends at .word 0xFF
            nrec, ptrs = 0, []
            for i in range(s + 1, e):
                wm = WORD_RE.match(strip_comment(lines[i]))
                if wm:
                    tok = wm.group(1).strip()
                    if tok in ("0xFF", "0x0"):
                        break
                    nrec += 1
                    ptrs.append(tok)
            lists[name] = {"records": nrec, "cite": f"data/BattleSettings.s:{ln}"}
    # formation arrays: every byte_* label in this file = 0xF0-terminated
    # 4-byte enemy-setup entries, consumed by
    # SpawnBattleObjectUsingBattleEntityConfig_8007368 (BattleSettings.inc)
    form_rows = []
    for name, ln in labels:
        if not name.startswith("byte_80"):
            continue
        toks = [t for t in region_bytes("data/BattleSettings.s", name) if t[0] == "b" and t[1] == "v"]
        vals = [t[2] for t in toks]
        entries = []
        for j in range(0, len(vals) - 3, 4):
            quad = vals[j:j + 4]
            if quad[0] == 0xF0:
                break
            entries.append(quad)
        form_rows.append({
            "formation": name,
            "entries": len(entries),
            "enemy_ids": [f"{q[2]:02x}" for q in entries],
            "cite": f"data/BattleSettings.s:{ln}",
            "status": "unrecorded",
            # audit note: 4-byte entries, 0xF0-terminated (see the section
            # note emitted by regenerate_scope)
        })
    return lists, form_rows


# --------------------------------------------------------------- backdrops

def parse_backdrops(formation_lists):
    """DERIVED-FROM-RECORDS: no backdrop table is named in the disassembly;
    what the ROM itself supplies is the Background byte (BattleSettings+0x4,
    include/rom_structs/BattleSettings.inc:8) consumed by
    battleSettings_setBackground (asm/asm03_0.s:14556) and loaded by
    CopyBackgroundTiles (asm/asm00_0.s:3096). The distinct values the
    encounter records actually use are countable from BattleSettings.s."""
    # robust pass: walk each list's token stream, records = 16 bytes
    lines = read_lines("data/BattleSettings.s")
    values = {}
    for lname in formation_lists:
        s, e = label_bounds(lines, lname)
        pos = 0
        for i in range(s + 1, e):
            ln = strip_comment(lines[i])
            wm = WORD_RE.match(ln)
            bm = BYTE_RE.match(ln)
            if wm:
                if wm.group(1).strip() in ("0xFF", "0x0"):
                    break
                pos += 4
                continue
            if bm:
                for v in [v for k, v in parse_values(bm.group(1)) if k == "v"]:
                    if pos % 16 == 4:
                        values[v] = values.get(v, 0) + 1
                    pos += 1
    rows = [{
        "background_byte": f"0x{v:02x}",
        "records_using_it": c,
        # 0xff is the UNSET sentinel on the majority of records, not a
        # backdrop id (see the section note emitted by regenerate_scope)
        "role": "unset-sentinel" if v == 0xFF else "set-value",
        "cite": "data/BattleSettings.s (BattleSettings.Background, +0x4)",
        "status": "unrecorded",
    } for v, c in sorted(values.items())]
    return rows


# --------------------------------------------------------------- NaviCust

# DERIVED-FROM-HEADERS: GiveNaviCustPrograms/TakeNaviCustPrograms
# (asm/asm03_1_1.s:8794/:8814) install into the NaviStats block; the
# battle-relevant slots are the named struct offsets of NaviStats.inc.
# No program->effect table exists in the disassembly (search trail:
# 'NaviCust' in data/, asm/, constants/enums/ -- only text scripts and the
# give/take pair). A GAP for the program-id enumeration; the slots are the
# ROM-named inventory.
NAVICUST_FIELDS = [
    "Attack", "Speed", "Charge", "BButton", "BPwrAtk", "FstBarr",
    "BLeftAbility", "CustomLevel", "MegaLevel", "GigaLevel", "Mood",
    "CustHPBug", "FloatShoes", "AirShoes", "UnderShirt", "SuperArmor",
    "EmotionBug", "ProcessingBug", "SlipRun", "ChipRecovery",
]


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
    ver = sum(1 for r in flat if r.get("status", "").startswith("verified"))
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
    "formations (M8)":
        lambda meta: (
            "Audit note (provisional, this tool's own arithmetic, not"
            " independently divided out): record count = number of .word"
            " pointers before the terminator per list, assuming the 0x10-byte"
            " record stride of include/rom_structs/BattleSettings.inc (Size"
            " 0x10, getBattleSettingsFromList0 x0x10 indexing); check by"
            " stride x count vs each list's byte span. Formation arrays: 4-byte"
            " entries up to the 0xF0 stop consumed by"
            " SpawnBattleObjectUsingBattleEntityConfig_8007368."),
    "backdrops (M8)":
        lambda meta: (
            "Sentinel note: Background 0xff on 268 of 461 records is counted as"
            " an UNSET sentinel, not backdrop id 255. What this section counts"
            " after excluding 0xff: 2 set values (0x07 on 192 records, 0x08 on"
            " 1 record); the distinct-value denominator 3 includes the"
            " sentinel row so the sentinel itself stays auditable."),
}


def regenerate_scope(sections, pa_meta=None):
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
            arg = pa_meta if name == "program advances (M4)" else None
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
    "navis + cybeasts (M6)": [("index", 6), ("navi", 24), ("struct2_row0_raw", 8), ("act", 22), ("cite", 46), "status"],
    "forms (M7)": [("tf_value", 8), ("form", 22), ("charge_shot", 34), ("charge_cite", 24), "status"],
    "panels (M3)": [("routine", 36), ("cite", 24), "status"],
    "statuses (M3)": [("bit", 36), ("value", 12), ("cite", 40), "status"],
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
    statuses = parse_statuses()
    lists, form_rows = parse_formations()
    backdrops = parse_backdrops(lists)
    navicust = parse_navicust()

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
    write_section("statuses", {"generator": "tools/inventory.py", "rows": statuses})
    write_section("formations", {"generator": "tools/inventory.py",
                                 "battle_settings_lists": lists, "rows": form_rows})
    write_section("backdrops", {"generator": "tools/inventory.py", "rows": backdrops})
    write_section("navicust", {"generator": "tools/inventory.py", "rows": navicust})

    nrec = sum(v["records"] for v in lists.values())
    sections = [
        ("M1", ("chips (M4)", "FOUND: data/ChipDataArr.s:2 ChipDataArr_8021DA8 (411 x chip_data_struct, stride 0x2c, include/rom_structs/ChipData.inc)", chips)),
        ("M1", ("program advances (M4)", "FOUND: asm/asm03_0.s off_802BCB0 + off_802BC60 recipe-pointer tables (records [count][matcher][result u16][chip,code]*n)", pas)),
        ("M1", ("viruses (M5)", "FOUND via T12: byte_80182C4 identity rows + off_8109150 Struct2 (tools/rom_enemy_tables.py)", viruses)),
        ("M1", ("navis + cybeasts (M6)", "FOUND: asm/asm31.s off_80F24D8/off_80F253C/off_80F25A0", navis)),
        ("M1", ("cybeasts (M6)", "FOUND: TF enum values + dedicated sprite categories (constants/enums/sprite_categories.inc:17-18)", cybeasts)),
        ("M1", ("forms (M7)", "FOUND: constants/constants.inc TF enum + charge-shot dispatch off_80117D4 (asm/asm00_2.s:5789)", forms)),
        ("M1", ("panels (M3)", "DERIVED-FROM-CODE: asm/object.s routines; no type->routine table located", panels)),
        ("M1", ("statuses (M3)", "DERIVED-FROM-HEADERS: CollisionData.inc / BattleObject.inc named bits", statuses)),
        ("M1", ("formations (M8)", f"FOUND: data/BattleSettings.s battleSettingsList0:2 / BattleSettingsList1:1505, {nrec} records, {len(form_rows)} 0xF0-terminated formation arrays", form_rows)),
        ("M1", ("backdrops (M8)", "DERIVED-FROM-RECORDS: BattleSettings.Background byte values (no backdrop table named; search trail: 'backdrop', 'arena' in data/, asm/)", backdrops)),
        ("M1", ("navicust battle effects (M7)", "GAP (program-id table) + DERIVED-FROM-HEADERS (NaviStats slots): search trail 'NaviCust' in data/, asm/, constants/enums/", navicust)),
    ]
    regenerate_scope(sections, pa_meta={
        "pointer_words": sum(t["pointer_words"] for t in PA_TABLES),
        "records": sum(t["records"] for t in PA_TABLES),
        "terminators": [t["terminator"] for t in PA_TABLES if t["terminator"]],
    })

    for m, (name, state, rows) in sections:
        ver, total = status_summary(rows)
        print(f"{name}: {state} -- verified {ver}/{total}")


if __name__ == "__main__":
    main()
