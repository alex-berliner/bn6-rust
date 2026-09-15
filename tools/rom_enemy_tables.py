#!/usr/bin/env python3
"""T12: enemy roster out of the ROM's own index tables (bn6f).

Parses, from the ROM itself, bounded by next-label bounds taken from the
disassembly:
  - byte_80182C4  3-byte rows (version, ActorType, AIIndex), one per enemy_idx
    (asm00_2.s, GetVerActorTyAndAIIdx_80182B4)
  - off_8109050   AIIndex -> think routine (asm31.s)
  - off_81091D0   AIIndex -> act routine   (asm31.s)

Every table word is cross-checked against the disassembly's own `.word`
expression for that slot, and resolved to a symbol + file:line cite.

Writes docs/inventory/enemies.md (generated, never hand-typed) and prints the
per-enemy_idx JSON to stdout:
    python3 tools/rom_enemy_tables.py > docs/inventory/enemies.json

Human-readable report lines go to stderr. No captures, no src/ edits.
"""

import hashlib
import json
import os
import re
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASM = os.path.join(REPO, "reference", "bn6f", "asm")
ASM00_2 = os.path.join(ASM, "asm00_2.s")
ASM31 = os.path.join(ASM, "asm31.s")
DATA = os.path.join(REPO, "reference", "bn6f", "data")
ROM_PATH = os.environ.get("BN_ROM", "/tmp/bn6f_real.gba")

# canon: byte_80182C4 (GetVerActorTyAndAIIdx_80182B4, asm00_2.s:19965-19974)
IDENT_ADDR = 0x080182C4
# canon: off_8109050 (think dispatch, asm31.s:169420)
THINK_ADDR = 0x08109050
# canon: off_81091D0 (act dispatch, asm31.s:169615)
ACT_ADDR = 0x081091D0
# canon: off_8109150 (per-AIIndex Struct2 pointer table, asm31.s:169550;
# Struct2 = {elem_hp u16, unk_02 u8, unk_flags u8, elem_damage u16},
# asm00_2.s:677-681)
STRUCT2_ADDR = 0x08109150
ROM_BASE = 0x08000000  # canon: GBA ROM window

# labels: code labels use one colon ("ForMettaur_8109EF4:"), data labels in
# data/*.s use two ("off_810C6F0::")
LABEL_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):{1,2}\s*(?://.*)?$")
BYTE_ROW_RE = re.compile(r"^\s*\.byte\b")
WORD_ROW_RE = re.compile(r"^\s*\.word\b")
# a table entry: `.word Name` or `.word Name+1` (thumb), optional trailing comment
WORD_EXPR_RE = re.compile(r"^\s*\.word\s+([A-Za-z_][A-Za-z0-9_]*)(\+1)?\s*(?://.*)?$")
CONST_RE = re.compile(r"struct_const\s+(ACTOR_TYPE_\w+),\s*(0x[0-9a-fA-F]+|\d+)")
# label suffixes are bare addresses with leading zeros dropped:
# ForMettaur_8109EF4 = 0x08109EF4
ADDR_SUFFIX_RE = re.compile(r"_([0-9A-Fa-f]{6,8})$")


def read_lines(path):
    with open(path, "r", errors="replace") as f:
        return f.readlines()


def find_table_lines(lines, first_label):
    """Return (start_line_1based, next_label_name, next_line_1based)."""
    start = None
    for i, ln in enumerate(lines, 1):
        m = LABEL_RE.match(ln.rstrip("\n"))
        if m and m.group(1) == first_label:
            start = i
            break
    if start is None:
        sys.exit(f"label {first_label} not found")
    for i in range(start + 1, len(lines) + 1):
        m = LABEL_RE.match(lines[i - 1].rstrip("\n"))
        if m:
            return start, m.group(1), i
    sys.exit(f"no next label after {first_label}")


def count_row_lines(lines, start, end):
    n = 0
    for ln in lines[start - 1 : end - 1]:
        if BYTE_ROW_RE.match(ln) or WORD_ROW_RE.match(ln):
            n += 1
    return n


def parse_word_exprs(lines, start, end):
    """The disassembly's own `.word Name[+1]` expressions, in slot order."""
    exprs = []
    for ln in lines[start - 1 : end - 1]:
        m = WORD_EXPR_RE.match(ln)
        if m:
            exprs.append((m.group(1), m.group(2) == "+1"))
        elif WORD_ROW_RE.match(ln):
            exprs.append((None, None))  # a .word we cannot name
    return exprs


def build_label_maps():
    """(name -> (rel_file, line), addr -> (name, rel_file, line)) over every
    label in asm/*.s and data/*.s (data labels use the '::' form)."""
    names, addrs = {}, {}
    for d in (ASM, DATA):
        for fname in sorted(os.listdir(d)):
            if not fname.endswith(".s"):
                continue
            for lineno, ln in enumerate(read_lines(os.path.join(d, fname)), 1):
                m = LABEL_RE.match(ln.rstrip("\n"))
                if not m:
                    continue
                name = m.group(1)
                rel = f"asm/{fname}" if d is ASM else f"data/{fname}"
                names.setdefault(name, (rel, lineno))
                ma = ADDR_SUFFIX_RE.search(name)
                if ma:
                    addr = int(ma.group(1).rjust(8, "0"), 16)
                    addrs.setdefault(addr, (name, rel, lineno))
    return names, addrs


def classify(name):
    if name is None:
        return "unresolved"
    if name.startswith("For"):
        return "named"
    if name.startswith(("sub_", "nullsub_")):
        return "routine_unnamed"
    return "data_or_other"


def resolve_table(addr, exprs, rom, names, addrs, table_file):
    """Resolve each slot: symbol + file:line cite, cross-checked with the ROM
    word where the label carries an address suffix (suffix-less labels like
    nullsub_13 have no address to check against)."""
    base = addr - ROM_BASE
    res, mismatches = [], []
    n_checked = 0
    for i, (name, thumb) in enumerate(exprs):
        word = int.from_bytes(rom[base + 4 * i : base + 4 * i + 4], "little")
        entry = {"index": i, "rom_word": f"0x{word:08X}", "thumb_bit": word & 1}
        if name is not None and name in names:
            f, line = names[name]
            entry.update({"symbol": name, "file": f, "line": line})
        else:
            # fall back to resolving the raw word against every labeled address
            hit = addrs.get(word & ~1)
            if hit:
                entry.update({"symbol": hit[0], "file": hit[1], "line": hit[2]})
            else:
                entry.update({"symbol": None, "file": None, "line": None})
        entry["kind"] = classify(entry["symbol"])
        # cross-check: ROM word must equal the symbol's address (+ thumb bit)
        expect_addr = None
        if name:
            ma = ADDR_SUFFIX_RE.search(name)
            if ma:
                expect_addr = int(ma.group(1).rjust(8, "0"), 16)
        elif entry["symbol"]:
            ma = ADDR_SUFFIX_RE.search(entry["symbol"])
            if ma:
                expect_addr = int(ma.group(1).rjust(8, "0"), 16)
        if expect_addr is not None:
            n_checked += 1
            if (word & ~1) != expect_addr:
                mismatches.append(
                    {"slot": i, "rom_word": f"0x{word:08X}",
                     "expected": f"0x{expect_addr:08X}", "symbol": name or entry["symbol"]})
        res.append(entry)
    return res, mismatches, n_checked


def main():
    rom = open(ROM_PATH, "rb").read()

    def say(msg):
        print(msg, file=sys.stderr)

    # ActorType enum names: reference/bn6f/include/structs/AIData.inc:6-8
    enums, enum_cite = {}, None
    inc = os.path.join(REPO, "reference", "bn6f", "include", "structs", "AIData.inc")
    for lineno, ln in enumerate(read_lines(inc), 1):
        m = CONST_RE.search(ln)
        if m:
            enums[int(m.group(2), 0)] = m.group(1)
            if enum_cite is None:
                enum_cite = lineno
    actor_type_cite = f"include/structs/AIData.inc:{enum_cite}-{enum_cite + 2}"

    # --- step 1: identity rows, bound inferred from next label in asm00_2.s ---
    l00 = read_lines(ASM00_2)
    s, next_label, e = find_table_lines(l00, "VerActorTyAIIdxTable_80182C4")  # T14: was byte_80182C4, renamed in reference (renames.md:241)
    n_ident = count_row_lines(l00, s, e)
    ident_off = IDENT_ADDR - ROM_BASE
    ident_bytes = rom[ident_off : ident_off + 3 * n_ident]
    rows = []
    for i in range(n_ident):
        ver, aty, aidx = ident_bytes[3 * i], ident_bytes[3 * i + 1], ident_bytes[3 * i + 2]
        rows.append({"enemy_idx": i, "version": ver,
                     "actor_type_raw": aty, "actor_type": enums.get(aty, f"0x{aty:02X}"),
                     "ai_index": aidx})
    last = rows[-1]
    say(f"identity rows: N={n_ident} (0x{n_ident:X}) from byte_80182C4 "
        f"(bound inferred from {next_label}, asm00_2.s:{e}); last row = "
        f"version 0x{last['version']:02X}, ActorType 0x{last['actor_type_raw']:02X} "
        f"({last['actor_type']}), AIIndex 0x{last['ai_index']:02X}")
    say(f"N >= 0x86 (Gunner idx inside): {n_ident >= 0x86}")
    filler = [r["enemy_idx"] for r in rows if r["actor_type_raw"] > max(enums)]
    say(f"rows landing on filler/balign (ActorType byte not an ACTOR_TYPE enum): "
        f"{filler or 'none'}")

    # --- step 2: think and act dispatch tables ---
    # Ticket predicted off_8109050 -> off_81091D0 = 0x180 bytes = 96 words, but
    # that span holds THREE parallel 0x80-byte tables: off_8109050 (think),
    # off_81090D0 (per-AIIndex Struct1 pointers, enemy_getStruct1,
    # asm00_2.s:669-674) and off_8109150 (per-AIIndex Struct2 pointers,
    # enemy_getStruct2, asm00_2.s:713). The act table off_81091D0 starts
    # exactly at the span's end and runs 0x80 bytes to off_8109250.
    # Semantics (asm31.s:169395-169402): the THINK word is NOT called -- it is
    # passed as an argument to battle_801B1C4 (jump-table store); each think
    # entry is a CurAction-indexed state-handler TABLE pointer
    # ("// indexed by CurAction * 4", asm31.s:170981-170984). The ACT word IS
    # called (mov lr,pc; bx r0).
    l31 = read_lines(ASM31)
    s_t, next_t, e_t = find_table_lines(l31, "AIThinkTables_8109050")  # T14: was off_8109050, renamed (renames.md:242)
    n_think = count_row_lines(l31, s_t, e_t)
    s_s1, next_s1, e_s1 = find_table_lines(l31, "AIEnemyStruct1Ptrs_81090D0")  # T14: was off_81090D0, renamed (renames.md:243)
    n_struct1 = count_row_lines(l31, s_s1, e_s1)
    s_s2, next_s2, e_s2 = find_table_lines(l31, "AIEnemyStruct2Ptrs_8109150")  # T14: was off_8109150, renamed (renames.md:244)
    n_struct2 = count_row_lines(l31, s_s2, e_s2)
    s_a, next_a, e_a = find_table_lines(l31, "AIActHandlers_81091D0")  # T14: was off_81091D0, renamed (renames.md:245)
    n_act = count_row_lines(l31, s_a, e_a)
    say(f"think  off_8109050: {n_think} words (bound inferred from {next_t}, asm31.s:{e_t})")
    say(f"struct1 off_81090D0: {n_struct1} words (bound inferred from {next_s1}, asm31.s:{e_s1})")
    say(f"struct2 off_8109150: {n_struct2} words (bound inferred from {next_s2}, asm31.s:{e_s2})")
    say(f"act    off_81091D0: {n_act} words (bound inferred from {next_a}, asm31.s:{e_a})")

    names, addrs = build_label_maps()
    think_exprs = parse_word_exprs(l31, s_t, e_t)
    act_exprs = parse_word_exprs(l31, s_a, e_a)
    think_res, think_mm, think_checked = resolve_table(THINK_ADDR, think_exprs, rom, names, addrs, "asm31.s")
    act_res, act_mm, act_checked = resolve_table(ACT_ADDR, act_exprs, rom, names, addrs, "asm31.s")
    for mm in think_mm + act_mm:
        say(f"ROM/DISASM MISMATCH: {mm}")
    say(f"ROM/disasm cross-check coverage: think {think_checked}/{n_think}, "
        f"act {act_checked}/{n_act} (suffix-less labels like nullsub_13 have "
        f"no address to check against)")

    # --- step 3: resolution counts ---
    def count_kinds(res):
        k = {"named": 0, "routine_unnamed": 0, "data_or_other": 0, "unresolved": 0}
        for r in res:
            k[r["kind"]] += 1
        return k
    kt, ka = count_kinds(think_res), count_kinds(act_res)
    say(f"think entries (CurAction-indexed handler-TABLE pointers, not called): "
        f"{kt['named']} named For*_HHHHHHHH, {kt['routine_unnamed']} sub_*/nullsub_*, "
        f"{kt['data_or_other']} data/other labels, {kt['unresolved']} unresolved (of {n_think})")
    say(f"act entries (the callable per-AIIndex routine, mov lr,pc; bx r0): "
        f"{ka['named']} named For*_HHHHHHHH, {ka['routine_unnamed']} sub_*/nullsub_*, "
        f"{ka['data_or_other']} data/other labels, {ka['unresolved']} unresolved (of {n_act})")

    # attach think/act per row
    for r in rows:
        ai = r["ai_index"]
        r["think"] = think_res[ai] if ai < n_think else None
        r["act"] = act_res[ai] if ai < n_act else None

    used_think_syms = sorted({r["think"]["symbol"] for r in rows
                              if r["think"] and r["think"]["symbol"]})
    say(f"distinct think handler-table pointers referenced by used AIIndexes "
        f"(family count) ({len(used_think_syms)})")

    # existence agreement between the two tables
    used_ai = {r["ai_index"] for r in rows}
    no_think = sorted(a for a in used_ai if a >= n_think)
    no_act = sorted(a for a in used_ai if a >= n_act)
    disagree = sorted((set(no_think) | set(no_act)) - (set(no_think) & set(no_act)))
    # max(AIIndex) per actor type: the bare max over ALL rows is 0x30, which
    # exceeds the 32-word tables; the bound holds for non-PLAYER rows
    max_ai_by_type = {}
    for r in rows:
        t = r["actor_type"]
        max_ai_by_type[t] = max(max_ai_by_type.get(t, -1), r["ai_index"])
    say("max AIIndex by ActorType: "
        + ", ".join(f"{t}=0x{a:02X}" for t, a in sorted(max_ai_by_type.items()))
        + f"; max(AIIndex) < {n_think} (both table sizes) holds for "
          "non-PLAYER rows only")
    if no_think or no_act:
        rows_with = lambda a: sorted(f"0x{r['enemy_idx']:X}" for r in rows if r["ai_index"] == a)
        if no_think:
            say(f"MISSING think entry for AIIndex {['0x%02X' % a for a in no_think]} "
                f"(rows {sum((rows_with(a) for a in no_think), [])}) -- listed, not dropped")
        if no_act:
            say(f"MISSING act entry for AIIndex {['0x%02X' % a for a in no_act]} "
                f"(rows {sum((rows_with(a) for a in no_act), [])}) -- listed, not dropped")
        if disagree:
            say(f"DISAGREEMENT (exists in one table, not the other): "
                f"{['0x%02X' % a for a in disagree]}")

    # --- step 4: known-answer checks ---
    checks = [
        {"check": "idx 0x01..0x04 -> AIIndex 0x01 -> ForMettaur_8109EF4",
         "pass": all(rows[i]["ai_index"] == 0x01
                     and rows[i]["think"] and rows[i]["think"]["symbol"] == "ForMettaur_8109EF4"
                     for i in range(0x01, 0x05)),
         "cite": "asm/asm31.s:170982 (T6)"},
        {"check": "idx 0x85 -> AIIndex 0x17 -> ForGunner_8113078",
         "pass": rows[0x85]["ai_index"] == 0x17
                 and rows[0x85]["think"] and rows[0x85]["think"]["symbol"] == "ForGunner_8113078",
         "cite": (f"{rows[0x85]['think']['file']}:{rows[0x85]['think']['line']} (definition; "
                  f"table slot asm31.s:169468) (T9b)")},
    ]
    for c in checks:
        say(f"known-answer check: {c['check']}: {'PASS' if c['pass'] else 'FAIL'}")

    # --- step 5: named gap list (what M1's remaining columns need) ---
    # HP is NOT a gap: it is reachable through off_8109150 (Struct2 pointer
    # table), struct {elem_hp u16 @0, unk_02 u8, unk_flags u8, elem_damage u16}
    # (asm00_2.s:677-681). Spot-check two families against known HPs.
    struct2_exprs = parse_word_exprs(l31, s_s2, e_s2)
    struct2_res, struct2_mm, struct2_checked = resolve_table(
        STRUCT2_ADDR, struct2_exprs, rom, names, addrs, "asm31.s")
    def elem_hp(slot):
        p = int(struct2_res[slot]["rom_word"], 16) & ~1
        return int.from_bytes(rom[p - ROM_BASE : p - ROM_BASE + 2], "little")
    hp_spots = [
        {"family": "Mettaur", "ai_index": 0x01,
         "struct2_symbol": struct2_res[1]["symbol"],
         "struct2_cite": f"{struct2_res[1]['file']}:{struct2_res[1]['line']}",
         "elem_hp": f"0x{elem_hp(1):04X}", "expected": "0x28",
         "pass": elem_hp(1) == 0x28},
        {"family": "Gunner", "ai_index": 0x17,
         "struct2_symbol": struct2_res[0x17]["symbol"],
         "struct2_cite": f"{struct2_res[0x17]['file']}:{struct2_res[0x17]['line']}",
         "elem_hp": f"0x{elem_hp(0x17):04X}", "expected": "0x3C",
         "pass": elem_hp(0x17) == 0x3C},
    ]
    for h in hp_spots:
        say(f"HP spot-check: {h['family']} Struct2 elem_hp={h['elem_hp']} "
            f"(expected {h['expected']}): {'PASS' if h['pass'] else 'FAIL'}")
    gaps = [
        "NameID per enemy_idx (enemy name table not supplied by these index tables)",
        "sprite pointer per enemy_idx",
        "per-version parameter tables (the six per-version tables T9b cited for the Gunner)",
        "Navi bosses (whether boss Navis share these tables at all is unverified)",
        "formations / BattleSettings records (which enemy_idx set a battle spawns)",
    ]

    out = {
        "meta": {
            "generator": "tools/rom_enemy_tables.py",
            "rom": os.path.basename(ROM_PATH),
            "rom_sha1": hashlib.sha1(rom).hexdigest(),
            "regenerate": "python3 tools/rom_enemy_tables.py > docs/inventory/enemies.json",
            "identity_table": {
                "symbol": "byte_80182C4", "address": f"0x{IDENT_ADDR:08X}",
                "row_bytes": 3, "rows": n_ident,
                "bound": f"bound inferred from {next_label} (asm00_2.s:{e})",
                "accessor": "GetVerActorTyAndAIIdx_80182B4 (asm/asm00_2.s:19965-19974)",
                "actor_type_enum_cite": actor_type_cite,
            },
            "think_table": {
                "symbol": "off_8109050", "address": f"0x{THINK_ADDR:08X}", "words": n_think,
                "bound": f"bound inferred from {next_t} (asm31.s:{e_t})",
                "cite": "asm/asm31.s:169420",
                "semantics": ("NOT a called routine: the word is passed as an argument to "
                              "battle_801B1C4 (jump-table store, asm31.s:169395-169402); each "
                              "entry is a CurAction-indexed state-handler TABLE pointer "
                              "('// indexed by CurAction * 4', asm31.s:170981-170984 and "
                              "asm32.s:10122-10125)"),
                "note": ("ticket predicted 96 words for off_8109050->off_81091D0 (0x180 bytes); "
                         "the real span holds THREE parallel 0x80-byte tables: off_8109050 "
                         "think, off_81090D0 per-AIIndex Struct1 pointers (enemy_getStruct1, "
                         "asm00_2.s:669-674), off_8109150 per-AIIndex Struct2 pointers "
                         "(enemy_getStruct2, asm00_2.s:713). The act table off_81091D0 starts "
                         "exactly at the span's end"),
            },
            "struct1_table": {
                "symbol": "off_81090D0", "address": "0x081090D0", "words": n_struct1,
                "bound": f"bound inferred from {next_s1} (asm31.s:{e_s1})",
                "cite": "asm/asm31.s:169485, selected for virus by enemy_getStruct1 (asm00_2.s:669-674)",
            },
            "struct2_table": {
                "symbol": "off_8109150", "address": f"0x{STRUCT2_ADDR:08X}", "words": n_struct2,
                "bound": f"bound inferred from {next_s2} (asm31.s:{e_s2})",
                "cite": "asm/asm31.s:169550, selected for virus by enemy_getStruct2 (asm00_2.s:713)",
                "struct": "{elem_hp: u16 @0x00, unk_02: u8 @0x02, unk_flags: u8 @0x03, elem_damage: u16 @0x04} (asm00_2.s:677-681)",
            },
            "act_table": {
                "symbol": "off_81091D0", "address": f"0x{ACT_ADDR:08X}", "words": n_act,
                "bound": f"bound inferred from {next_a} (asm31.s:{e_a})",
                "cite": "asm/asm31.s:169615",
            },
            "counts": {
                "identity_rows": n_ident,
                "think_words": n_think,
                "act_words": n_act,
                "think_handler_table_named_For": kt["named"],
                "think_handler_table_sub_nullsub": kt["routine_unnamed"],
                "think_handler_table_other_label": kt["data_or_other"],
                "think_unresolved": kt["unresolved"],
                "act_named_routines": ka["named"],
                "act_routine_unnamed": ka["routine_unnamed"],
                "act_data_or_other": ka["data_or_other"], "act_unresolved": ka["unresolved"],
                "think_handler_table_count": len(used_think_syms),
            },
            "rom_disasm_crosscheck": {
                "think_checked": f"{think_checked}/{n_think}",
                "act_checked": f"{act_checked}/{n_act}",
                "note": ("only entries whose label carries an address suffix can be checked; "
                         "suffix-less labels (nullsub_13) have no address to check against"),
            },
            "max_ai_index_by_actor_type": {
                t: f"0x{a:02X}" for t, a in sorted(max_ai_by_type.items())
            },
            "hp_pointer": {
                "table": "off_8109150 (per-AIIndex Struct2 pointers)",
                "field": "elem_hp u16 @0x00",
                "cite": "asm/asm31.s:169550; struct layout asm00_2.s:677-681",
                "spot_checks": hp_spots,
            },
            "known_answer_checks": checks,
            "rom_disasm_mismatches": think_mm + act_mm,
            "ai_index_without_think_entry": [f"0x{a:02X}" for a in no_think],
            "ai_index_without_act_entry": [f"0x{a:02X}" for a in no_act],
            "ai_index_think_act_existence_disagreement": [f"0x{a:02X}" for a in disagree],
            "not_supplied_by_these_tables": gaps,
        },
        "rows": rows,
    }
    json.dump(out, sys.stdout, indent=1)
    sys.stdout.write("\n")

    # --- generate docs/inventory/enemies.md ---
    fam_of = {}
    for r in rows:
        sym = r["think"]["symbol"] if r["think"] and r["think"]["symbol"] else "(no think entry)"
        fam_of.setdefault(sym, []).append(r)
    inv = os.path.join(REPO, "docs", "inventory")
    os.makedirs(inv, exist_ok=True)
    with open(os.path.join(inv, "enemies.md"), "w") as f:
        f.write("# Enemy roster (generated by tools/rom_enemy_tables.py — do not hand-edit)\n\n")
        f.write("Regenerate: `python3 tools/rom_enemy_tables.py > docs/inventory/enemies.json`\n\n")
        f.write(f"- identity rows: {n_ident} (byte_80182C4, bound inferred from "
                f"{next_label}, asm00_2.s:{e})\n")
        f.write(f"- think words: {n_think} (off_8109050, bound inferred from {next_t}, "
                f"asm31.s:{e_t}); act words: {n_act} (off_81091D0, bound inferred from "
                f"{next_a}, asm31.s:{e_a})\n")
        f.write(f"- between them: Struct1 ptrs off_81090D0 ({n_struct1} words, "
                f"asm31.s:169485) and Struct2 ptrs off_8109150 ({n_struct2} words, "
                f"asm31.s:169550) — the ticket's 0x180 span is think+Struct1+Struct2; "
                f"act starts exactly at its end\n")
        f.write("- think entries are CurAction-indexed state-handler TABLE pointers "
                "(passed to battle_801B1C4 as a jump table, asm31.s:169395-169402; "
                "'// indexed by CurAction * 4', asm31.s:170981-170984) — NOT called "
                "routines; act words ARE called (mov lr,pc; bx r0)\n")
        f.write(f"- think handler-table pointers named `For*_HHHHHHHH`: {kt['named']}/{n_think}; "
                f"distinct think handler tables over used AIIndexes (family count): "
                f"{len(used_think_syms)}; act routines named `For*`: {ka['named']}/{n_act}\n")
        f.write(f"- ROM/disasm cross-check coverage: think {think_checked}/{n_think}, "
                f"act {act_checked}/{n_act} (suffix-less labels like nullsub_13 have no "
                f"address to check against)\n")
        for h in hp_spots:
            f.write(f"- HP pointer: off_8109150 Struct2 elem_hp (asm31.s:169550, layout "
                    f"asm00_2.s:677-681); spot-check {h['family']} "
                    f"elem_hp={h['elem_hp']} vs expected {h['expected']}: "
                    f"**{'PASS' if h['pass'] else 'FAIL'}**\n")
        for c in checks:
            f.write(f"- known-answer: {c['check']}: "
                    f"**{'PASS' if c['pass'] else 'FAIL'}** ({c['cite']})\n")
        if no_think or no_act:
            f.write(f"- AIIndex with no think entry ({n_think}-word table): "
                    f"{', '.join('0x%02X' % a for a in no_think) or 'none'}\n")
            f.write(f"- AIIndex with no act entry ({n_act}-word table): "
                    f"{', '.join('0x%02X' % a for a in no_act) or 'none'}\n")
        f.write("\n## Not supplied by these tables (T10 gap list)\n\n")
        f.write("- NOT a gap — HP per enemy_idx: reachable via off_8109150 Struct2 pointer "
                "table (asm31.s:169550), struct {elem_hp u16 @0, unk_02 u8, unk_flags u8, "
                "elem_damage u16 @4} (asm00_2.s:677-681)\n")
        for g in gaps:
            f.write(f"- {g}\n")
        f.write("\n## Families (grouped by think handler-table pointer; cites are "
                "think file:line; think entries are CurAction-indexed handler tables, "
                "not called routines)\n\n")
        for sym in sorted(fam_of, key=lambda s_: (s_ == "(no think entry)", s_)):
            members = fam_of[sym]
            first = members[0]
            cite = (f"{first['think']['file']}:{first['think']['line']}"
                    if first["think"] and first["think"]["file"] else "-")
            f.write(f"### {sym} — {len(members)} enemy_idx (think cite {cite})\n\n")
            f.write("| enemy_idx | version | ActorType | AIIndex | act |\n|---|---|---|---|---|\n")
            for r in members:
                act = r["act"]
                f.write(f"| 0x{r['enemy_idx']:X} | {r['version']} | {r['actor_type']} | "
                        f"0x{r['ai_index']:02X} | {act['symbol'] if act else '(none)'} |\n")
            f.write("\n")

    if not all(c["pass"] for c in checks):
        say("KNOWN-ANSWER CHECK FAILED -- this is the ticket's headline result, not a footnote")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
