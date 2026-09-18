#!/usr/bin/env python3
"""The state oracle (TODO R6/R7): the first divergent FIELD and frame, not
just a pixel count.

One harness row, both sides captured with `--watch`:

  rust  -- the plain fixture ROM. Two watch streams: the battle marker
           (0x02000000:8, for marker-origin alignment -- added by
           `harness.Side.do_capture` exactly as `harness.run` does) and the
           ROM's own state-export block (0x02000008:40, `ORCL`, written by
           src/main.rs every frame from `battle.oracle_snapshot`'s field
           map). Every exported field is already in canon's units and
           encodings; the map with sources lives on `oracle_snapshot`.
  canon -- the row's own canon side, watched at:
           0x020013f0:4   ePrimaryRngSeed (ewram.s:262)
           <mm_base>:30   MegaMan's BattleObject +0x08..+0x26
                          (mm_base 0x0203a9b8 = eT1BattleObject0+8;
                          CurState/CurAction/PanelX/PanelY/Timer/HP per
                          include/structs/BattleObject.inc:40-101)
           <enemy_slot>+8:30 the POPULATED enemy BattleObject +0x08..+0x26.
                          NOT slot 0x0203aa88: for the PAUSED-based rows
                          (wave/mettaur) the live Mettaur is the SECOND
                          T1 slot, 0x0203ab60 -- proven by the ALIVE cheat
                          itself, whose address 0x0203ab84 = 0x0203ab60 +
                          oBattleObject_HP, and by the probe capture (TODO
                          R6 report): 0x0203aa88 reads HP 0x0000 there.
           0x020352a0:2   the custom gauge (eStruct2035280+0x20,
                          sub_801DFB8, asm00_2.s:29892-29907)

Alignment is the row's OWN Align, reused verbatim: `harness.run()` captures
both sides, finds the rust marker origin, and scores every offset in the
row's search band by the full-screen pixel diff -- the same pairing the
row's published number was measured at. Field comparison happens on those
same frames.

THE FIELD CONTRACT (TODO R7): every field R6 requested, classified. PARITY
fields are compared frame by frame and printed in the full table whether
they match or not; INFO-ONLY fields are watched and printed but never
compared, because the two FIXTURES disagree by design (fixture age, the
ALIVE cheat, the descriptor), not because the model is wrong; UNSUPPORTED
fields have no honest equivalent on one side and are printed as such with
the evidence -- none is invented.

  PARITY (compared):
    rng_cadence         canon 0x020013f0 ePrimaryRngSeed (ewram.s:262) vs
                        export +8 (ai::Rng::state()). Compared as EXACTLY
                        one GetRNG step per frame per side (seed = rotl+1 ^
                        0x873ca9e5, asm00_0.s:2610-2622; canon measured 1
                        step/frame over 219 transitions -- ai.rs's module
                        doc; ours by construction in `Battle::update`).
                        Deliberately NOT absolute-value equality: the two
                        fixtures' battles are different AGES, so the
                        streams sit at different orbit points by
                        construction (the absolute values print under
                        rng_abs below; src/ai.rs DEFAULT_SEED's doc).
    mm_state_action     canon 0x0203a9b8 +0x08/+0x09 (eT1BattleObject0+8,
                        include/structs/BattleObject.inc:40-52) vs export
                        +12/13 (Actor::oracle_fields, player action map).
    mm_anim             canon +0x10 (0x0203a9c0) vs export +14 -- identity:
                        our anim indices ARE the sprites' animation-table
                        indices canon's CurAnim byte indexes (R6 probe).
    mm_panel_x/y        canon +0x12/+0x13 (0x0203a9c2/3) vs export +15/16
                        (Actor::panel(), canon's 1-based units).
    mm_timer            canon +0x20 (0x0203a9d0) vs export +18 -- the flinch
                        countdown 0x16..0x00 plus the post-flinch 0xffff,
                        9..0 tail (actor.rs `post_flinch`; fitted, counted
                        off the R6 watch capture). This IS the
                        animation/action timer that drives hit timing on
                        the player side.
    enemy_state_action  canon <slot>+0x08/+0x09 (0x0203ab68) vs export
                        +22/23 (Actor::oracle_fields enemy action map +
                        Ai::oracle_is_wait).
    enemy_anim          canon <slot>+0x10 vs export +24 -- identity.
    enemy_panel_x/y     canon <slot>+0x12/+0x13 vs export +25/26.

  INFO-ONLY (watched, printed, NOT compared -- fixtures disagree by design):
    mm_hp               canon +0x24 (0x0203a9d4) vs export +20: the PAUSED
                        rows' canon side reads the capture's own damaged
                        navi (50/60) while the descriptor says megaman_hp
                        90/100 -- a fixture disagreement, not a model
                        defect.
    enemy_hp            canon <slot>+0x24 (0x0203ab84) vs export +30: the
                        canon side is poked 0xffff by the ALIVE cheat by
                        design.
    gauge               canon 0x020352a0 (eStruct2035280+0x20, sub_801DFB8,
                        asm00_2.s:29892-29907) vs export +32: canon's is
                        full (0x4000) from the old battle; ours ticks from
                        the descriptor's gauge field -- fixture age again.
    rng_abs             the two streams' absolute orbit positions (see
                        rng_cadence; the model claim is the cadence).

  UNSUPPORTED (no honest equivalent; printed as such, never compared,
  never invented -- TODO R7 names both explicitly):
    battle_frame        export +4 only. Canon has NO known battle-frame RAM
                        word (R6 searched for one; the row's Align already
                        IS the frame pairing), so there is nothing to
                        compare against.
    enemy_timer         canon <slot>+0x20 (0x0203ab80) vs export +28. R6's
                        probe measured canon reading a CONSTANT 0x0002 here
                        for the whole window -- the Mettaur's swing/timing
                        countdown lives OUTSIDE the probed +0x00..+0x2f
                        range -- so there is nothing dynamic to model and
                        the export returns 0. The enemy's timing countdown
                        stays unsupported; do not invent an equivalent.

Negative control (AUDIT pair 10, oracle edition, TODO R7's contract): the
SAME field comparison with the canon side shifted one frame later must
CHANGE the nominal result -- the per-field first-divergence table has to
move -- or the oracle is BLIND on that row. "Still diverges somewhere" on
an already-divergent row proves nothing and is reported as BLIND.

Since TODO F16 the oracle runs on ANY harness.py comparison row: it derives
the enemy-slot configuration from the row's own fixture descriptor
(`enemies` field) and a per-row table of verified canon enemy slots. Rows
whose fixture has no enemy (the 49 sterile-arena rows) skip the enemy
fields with an explicit n/a -- never a fake match against a canon side
that still carries a live object from its own state. `rollup` fails
loudly: it is a no-crash walk with no Sides and no Align to reuse.

Usage:
  python3 tools/oracle.py <row>            # any harness.py row but rollup
  python3 tools/oracle.py <row> --shift N  # canon shifted N frames (default 0)
"""

import argparse
import dataclasses
import os
import json
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import chip_compare as cc  # noqa: E402
import harness as H  # noqa: E402
import states as S  # noqa: E402

# --- the field model ---------------------------------------------------------


def rng_step(seed: int) -> int:
    """One GetRNG step (asm00_0.s:2610-2622; ai.rs's own formula):
    seed = rotl(seed, 1) + 1 ^ 0x873ca9e5."""
    return ((((seed << 1) | (seed >> 31)) & 0xFFFFFFFF) + 1) & 0xFFFFFFFF ^ 0x873CA9E5


MM_BASE = 0x0203A9B8  # eT1BattleObject0 + oBattleObject_CurState
GAUGE_ADDR = 0x020352A0  # eStruct2035280 + 0x20
RNG_ADDR = 0x020013F0  # ePrimaryRngSeed
MM_ORACLE_ADDR = 0x02000008  # the rust export block ("ORCL"); docs/oracle_layout.json's block_addr

#: The ORCL block's layout, GENERATED from src/battle.rs's ORACLE_LAYOUT table
#: by tools/oracle_layout.py (Q4): the Rust table is authoritative, this JSON is
#: its committed projection, and harness.py's startup self-check
#: (oracle_layout.self_check) re-parses the Rust table and refuses a stale copy.
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir,
                       "docs", "oracle_layout.json")) as _layout_file:
    ORCL_LAYOUT = json.load(_layout_file)
ORCL_BLOCK_LEN = ORCL_LAYOUT["block_len"]
ORCL_OFFSETS = {f["name"]: f["offset"] for f in ORCL_LAYOUT["fields"]}

#: The canon battle-object table (ewram.s:2972-2992): slot 0 is MegaMan
#: (0x0203a9b0, watched at +0x08), the struct stride is 0xD8
#: (eT1BattleObject1 at 0x203aa88, 2 at 0x203ab60). HP is +0x24 of the
#: struct, which is where the ALIVE cheat pokes.
ENEMY_TABLE = 0x0203A9B0
ENEMY_STRIDE = 0xD8

#: Per-row configuration: the INDEX of the populated enemy slot in the
#: canon table, for every row whose fixture descriptor has enemies > 0.
#: Everything else about a row is its own Check definition (Sides, Align,
#: frames -- reused verbatim). (provenance: peeked -- one canon capture
#: per row watching the whole table, tools/f16_slot_probe.py, read at the
#: row's own canon_ref: every row keeps its enemy in slot 2 (= the PAUSED
#: proof, 0x0203ab60: the ALIVE cheat's own address 0x0203ab84 = base +
#: 2*0xD8 + oBattleObject_HP) except `opening`, whose three enemies sit in
#: slots 1..3 and whose export block is `enemies.first()` (battle.rs
#: oracle_snapshot), so canon's counterpart is the FIRST enemy, slot 1;
#: and `result`, whose slot-2 enemy is already DELETED at canon_ref 21
#: (state 0x08, hp 0x0000) -- the row is about the battle-over sequence,
#: the watch is the honest one, the fields simply read the dead object.
ENEMY_SLOT = {
    "opening": 1,
    "mettaur": 2,
    "tiles": 2,
    "gauge": 2,
    "wave": 2,
    "window": 2,
    "card": 2,
    "cursor": 2,
    # T182: navi-gunner shares the gunner row's slot 2 population
    # (verified via tools/f16_slot_probe.py navi-gunner: first compared
    # canon frame 80 slot2@0x203ab60 state=04 act=00 hp=003c; last compared
    # canon frame 209 slot2@0x203ab60 state=04 act=01 hp=003c).
    "navi-gunner": 2,
    "navi-gunner-ai": 2,
    "windowclose": 2,
    "result": 2,
    # T147: battlestart_scripted scenario (states.TRACE_SCENARIOS, two-sided
    # since this ticket) fields rec163's slots 1..3 (T131 step 3): canon's
    # populated FIRST enemy is e1 = 0x0203aa88 = TABLE SLOT 1 in this file's
    # indexing (slot 0 is MegaMan itself, 0x0203a9b0 -- the `opening` entry
    # is the same shape: three enemies in slots 1..3, export block =
    # enemies.first(), canon counterpart = the FIRST enemy, slot 1). NameID
    # 0x0088 from built-frame 69 (T131 step 3; this ticket's canon capture
    # re-reads it).
    "battlestart_scripted": 1,
    # T47 (2026-09-16): battle_full scenario (states.TRACE_SCENARIOS) is a
    # 540-frame scripted PAUSED battle against a single Mettaur (kind=0),
    # the same enemy family as the mettaur row -- the populated canon slot
    # is the SECOND T1 entry, 0x0203ab60 (ALIVE proof: 0x0203ab84 =
    # 0x0203ab60 + oBattleObject_HP).
    "battle_full": 2,
}

#: fields watched and printed but NEVER compared: the two FIXTURES disagree
#: by design (fixture age, the ALIVE cheat, the descriptor) -- the full
#: contract with addresses and reasons is the module docstring and is
#: printed under FIELD CONTRACT.
INFO_FIELDS = ["mm_hp", "enemy_hp", "gauge", "rng_abs"]

#: fields with NO honest equivalent on one side (TODO R7 names both):
#: printed as unsupported with their evidence, never compared, never
#: invented.
UNSUPPORTED_FIELDS = ["battle_frame", "enemy_timer"]

# --- canon watch-file parsing ------------------------------------------------
# One row per captured frame, appended after every rendered frame.


def canon_fields_mm(row: bytes) -> dict:
    """From a watch of MM_BASE (object +0x08), 30 bytes, BattleObject.inc:
    +0x08 CurState, +0x09 CurAction, +0x10 CurAnim, +0x12/13 PanelX/Y,
    +0x20 Timer, +0x24 HP."""
    return dict(
        state=row[0],
        action=row[1],
        anim=row[8],
        panel_x=row[0x0A],
        panel_y=row[0x0B],
        timer=struct.unpack_from("<H", row, 0x18)[0],
        hp=struct.unpack_from("<H", row, 0x1C)[0],
    )


def canon_fields_enemy(row: bytes) -> dict:
    return canon_fields_mm(row)  # same BattleObject layout


def rust_fields(row: bytes) -> dict:
    """From one 40-byte ORCL block row -- offsets read from
    docs/oracle_layout.json (generated from src/battle.rs's ORACLE_LAYOUT,
    Q4; harness.py's self-check keeps the two in agreement)."""
    return dict(
        state=row[ORCL_OFFSETS["mm_state_action"]],
        action=row[ORCL_OFFSETS["mm_state_action"] + 1],
        anim=row[ORCL_OFFSETS["mm_anim"]],
        panel_x=row[ORCL_OFFSETS["mm_panel_x"]],
        panel_y=row[ORCL_OFFSETS["mm_panel_y"]],
        timer=struct.unpack_from("<H", row, ORCL_OFFSETS["mm_timer"])[0],
        hp=struct.unpack_from("<H", row, ORCL_OFFSETS["mm_hp"])[0],
        enemy_state=row[ORCL_OFFSETS["enemy_state_action"]],
        enemy_action=row[ORCL_OFFSETS["enemy_state_action"] + 1],
        enemy_anim=row[ORCL_OFFSETS["enemy_anim"]],
        enemy_panel_x=row[ORCL_OFFSETS["enemy_panel_x"]],
        enemy_panel_y=row[ORCL_OFFSETS["enemy_panel_y"]],
        enemy_timer=struct.unpack_from("<H", row, ORCL_OFFSETS["enemy_timer"])[0],
        enemy_hp=struct.unpack_from("<H", row, ORCL_OFFSETS["enemy_hp"])[0],
        battle_frame=struct.unpack_from("<I", row, ORCL_OFFSETS["battle_frame"])[0],
        rng=struct.unpack_from("<I", row, ORCL_OFFSETS["rng"])[0],
        gauge=struct.unpack_from("<H", row, ORCL_OFFSETS["gauge"])[0],
    )


def watch_rows(path: str, width: int) -> list:
    data = open(path, "rb").read()
    rows = len(data) // width
    if rows * width != len(data):
        raise SystemExit("%s: %d bytes is not a multiple of %d" % (path, len(data), width))
    return [data[i * width:(i + 1) * width] for i in range(rows)]


# --- the comparison ----------------------------------------------------------

#: (rust accessor, canon accessor) pairs for the COMPARED fields. Canon rows
#: are dicts from canon_fields_mm; rust rows from rust_fields. rng_cadence
#: is handled separately (it needs consecutive frames of both streams).
FIELD_PAIRS = [
    ("mm_state_action", lambda r: (r["state"], r["action"]),
     lambda c: (c["state"], c["action"])),
    ("mm_anim", lambda r: r["anim"], lambda c: c["anim"]),
    ("mm_panel_x", lambda r: r["panel_x"], lambda c: c["panel_x"]),
    ("mm_panel_y", lambda r: r["panel_y"], lambda c: c["panel_y"]),
    ("mm_timer", lambda r: r["timer"], lambda c: c["timer"]),
    ("enemy_state_action", lambda r: (r["enemy_state"], r["enemy_action"]),
     lambda c: (c["state"], c["action"])),
    ("enemy_anim", lambda r: r["enemy_anim"], lambda c: c["anim"]),
    ("enemy_panel_x", lambda r: r["enemy_panel_x"], lambda c: c["panel_x"]),
    ("enemy_panel_y", lambda r: r["enemy_panel_y"], lambda c: c["panel_y"]),
]


def compare(rust_rows: list, canon_mm: list, canon_enemy: list,
            canon_rng: list, offset: int, frames: int,
            has_enemy: bool = True) -> dict:
    """First divergent frame per compared field at `offset` (rust row index
    = offset + k, canon row index = canon_ref + k, already applied by the
    callers slicing the row lists). Fields whose name starts with
    "enemy_" are compared only when the row's fixture has an enemy
    (F16): a sterile-arena row's export block carries the 0xffff
    no-enemy sentinel, and the canon side's own state may still hold a
    live object from its own history -- comparing the two would be a
    fake match or a fake divergence, so they are skipped entirely."""
    pairs = [p for p in FIELD_PAIRS
             if has_enemy or not p[0].startswith("enemy_")]
    out = {}
    for name in [p[0] for p in pairs] + ["rng_cadence"]:
        out[name] = dict(first=None, count=0, canon=None, rust=None,
                         pairs=set())
    prev_rust_rng = prev_canon_rng = None
    for k in range(frames):
        r = rust_fields(rust_rows[offset + k])
        c = canon_fields_mm(canon_mm[k])
        e = canon_fields_enemy(canon_enemy[k]) if has_enemy else c
        for name, rget, cget in pairs:
            cval = cget(e if name.startswith("enemy_") else c)
            rval = rget(r)
            out[name]["pairs"].add((cval, rval))
            if rval != cval:
                f = out[name]
                if f["first"] is None:
                    f["first"] = k
                    f["canon"] = cval
                    f["rust"] = rval
                f["count"] += 1
        # rng cadence: one step per frame, per side, across the whole window.
        crng = struct.unpack("<I", canon_rng[k])[0]
        if prev_rust_rng is not None:
            if r["rng"] != rng_step(prev_rust_rng) or crng != rng_step(prev_canon_rng):
                f = out["rng_cadence"]
                f["pairs"].add(((prev_canon_rng, crng), (prev_rust_rng, r["rng"])))
                if f["first"] is None:
                    f["first"] = k
                    f["canon"] = (prev_canon_rng, crng)
                    f["rust"] = (prev_rust_rng, r["rng"])
                f["count"] += 1
        prev_rust_rng, prev_canon_rng = r["rng"], crng
    return out


def _scenario_check(name: str) -> H.Check:
    """Build a synthetic H.Check from a states.TRACE_SCENARIOS scenario so
    the oracle can run on non-comparison scenarios (T47: battle_full).

    Sides come from the scenario's own spec dict: rust = fixture+script,
    canon = rom+loadstate+cheats+script. Alignment is the scenario's own
    canon_ref/rust_base pairing (the same one tools/trace.py uses). The
    marker on the rust side is the harness's own boot marker -- the
    fixture writes it from BATT onward (src/main.rs's Battle::update), so
    H.run()'s find_marker_origin still gives a usable origin.
    """
    scen = S.TRACE_SCENARIOS[name]

    def rust_factory(_variant: str) -> H.Side:
        spec = dict(scen["rust"])
        fixture = spec.pop("fixture", None)
        return H.Side(rom=H.plain_rom(), fixture=fixture,
                      script=spec.pop("script", None),
                      extra=tuple(spec.pop("extra", ())),
                      **{k: v for k, v in spec.items()
                         if k in ("loadstate", "cheats", "pokes", "pokes_at",
                                  "zero")})

    def canon_factory(_variant: str) -> H.Side:
        spec = dict(scen["canon"])
        return H.Side(**{k: v for k, v in spec.items()
                         if k in ("rom", "loadstate", "script", "cheats",
                                  "pokes", "pokes_at", "zero", "extra",
                                  "features", "fixture")})

    return H.Check(
        name=name, ui="isolated", frames=scen["frames"],
        align=H.Align(canon_ref=scen["canon_ref"], rust_offset=scen["rust_base"],
                      search=None,
                      note="scenario %s alignment from states.TRACE_SCENARIOS"
                           % name),
        rust=rust_factory, canon=canon_factory,
    )


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("row")
    ap.add_argument("--shift", type=int, default=0,
                    help="canon side shifted N frames later (the negative "
                         "control is --shift 1 on the same captures)")
    ap.add_argument("--both", action="store_true",
                    help="accepted for compatibility with the battle_full "
                         "ticket's documented invocation; the oracle on a "
                         "harness row already watches BOTH sides (rust "
                         "ORCL block + canon RNG/MM/enemy/gauge), so this "
                         "flag is a no-op kept to keep tool invocations "
                         "from erroring out (T47, 2026-09-16)")
    args = ap.parse_args()

    if args.row == "rollup":
        raise SystemExit(
            "row 'rollup' is a no-crash walk, not a comparison (harness.py "
            "run_rollup): it has no Sides and no Align to reuse, so there is "
            "nothing for the oracle to watch on a canon side")
    checks = [c for c in H.CHECKS if c.name == args.row]
    if not checks and args.row in H.SCENARIO_ROWS:
        # T47 (2026-09-16): the scenario path is a non-comparison scenario
        # whose Sides and alignment live in states.TRACE_SCENARIOS, not in
        # CHECKS. Build a synthetic Check and route through the same flow.
        checks = [_scenario_check(args.row)]
    if not checks and args.row in S.TRACE_SCENARIOS and all(
            k in S.TRACE_SCENARIOS[args.row] for k in ("canon", "rust")):
        # T147 (2026-09-19): a two-sided TRACE_SCENARIOS entry -- canon+rust
        # side specs both present in states.py -- needs no harness.py
        # SCENARIO_ROWS tuple membership; the same _scenario_check flow
        # applies. One-sided scenarios (T131's battlestart_scripted before
        # T147 added its rust side) stay unroutable: the oracle compares
        # two sides, so there is nothing for it to watch on a one-sided
        # scenario.
        checks = [_scenario_check(args.row)]
    if not checks:
        raise SystemExit(
            "unknown row %r: harness.py --list names the rows, "
            "tools/harness.py SCENARIO_ROWS lists the non-comparison "
            "scenarios (%s); rollup is a no-crash walk, not a comparison"
            % (args.row, ", ".join(H.SCENARIO_ROWS)))
    check = checks[0]
    if check.ui not in ("isolated", "integrated", "both"):
        raise SystemExit("row %s has ui=%r; the oracle runs one variant"
                         % (args.row, check.ui))
    variant = "isolated" if check.ui in ("isolated", "both") else "integrated"

    # F16: enemy presence is a property of the row's own fixture descriptor
    # (which lives on the RUST side; the canon side reproduces the scenario
    # via its own state/pokes and carries no descriptor). A row with no
    # fixture enemy skips the enemy fields with an explicit n/a.
    enemy_count = (check.rust(variant).fixture or {}).get("enemies", 0)
    has_enemy = enemy_count > 0
    if has_enemy and args.row not in ENEMY_SLOT:
        raise SystemExit(
            "row %s's fixture has %d enemies but the oracle has no verified "
            "canon enemy slot for it: run the slot probe (tools/"
            "f16_slot_probe.py -- one canon capture watching the whole "
            "eT1BattleObjects table, ewram.s:2972, read at the row's own "
            "canon_ref), verify the populated slot, and add it to ENEMY_SLOT "
            "with the probe as provenance -- see HANDOFF §3a"
            % (args.row, enemy_count))
    enemy_slot = (ENEMY_TABLE + ENEMY_SLOT[args.row] * ENEMY_STRIDE + 0x08
                  if has_enemy else None)
    # The canon watches ride in `extra`, so `harness.run()`'s own captures
    # carry them -- the alignment machinery is reused verbatim, not copied.
    canon_rng_file = cc.scratch("o_canonrng_%s.bin" % args.row)
    canon_mm_file = cc.scratch("o_canonmm_%s.bin" % args.row)
    canon_enemy_file = cc.scratch("o_canonenemy_%s.bin" % args.row)
    canon_gauge_file = cc.scratch("o_canongauge_%s.bin" % args.row)
    rust_block_file = cc.scratch("o_rustblock_%s.bin" % args.row)
    canon_watch = [
        "--watch", "%#x:4:%s" % (RNG_ADDR, canon_rng_file),
        "--watch", "%#x:30:%s" % (MM_BASE, canon_mm_file),
        "--watch", "%#x:2:%s" % (GAUGE_ADDR, canon_gauge_file),
    ]
    if has_enemy:
        # slot + oBattleObject_CurState (+0x08): same layout as the MM watch
        canon_watch[2:2] = ["--watch", "%#x:30:%s"
                            % (enemy_slot, canon_enemy_file)]
    rust_watch = ["--watch", "%#x:40:%s" % (MM_ORACLE_ADDR, rust_block_file)]

    def sides():
        rust_side = check.rust(variant)
        rust = dataclasses.replace(rust_side,
                                   extra=rust_side.extra + tuple(rust_watch))
        canon_side = check.canon(variant)
        canon = dataclasses.replace(canon_side,
                                    extra=canon_side.extra + tuple(canon_watch))
        return rust, canon

    for path in ((canon_rng_file, canon_mm_file, canon_gauge_file,
                  rust_block_file) + ((canon_enemy_file,) if has_enemy else ())):
        if os.path.exists(path):
            os.unlink(path)

    rust, canon = sides()
    result = H.run(rust, canon, check.frames, check.align)

    rust_rows = watch_rows(rust_block_file, 40)
    canon_mm = watch_rows(canon_mm_file, 30)
    canon_enemy = watch_rows(canon_enemy_file, 30) if has_enemy else []
    canon_rng = watch_rows(canon_rng_file, 4)
    canon_gauge = watch_rows(canon_gauge_file, 2)
    # The displayed table sits at +shift; the negative control needs the
    # nominal table AND the +1 table off the same captures, so keep one
    # frame of slack even at shift 0.
    need = check.frames + max(args.shift, 1)
    for name, rows, width in (("rust block", rust_rows, 40),
                              ("canon mm", canon_mm, 30),
                              ("canon rng", canon_rng, 4),
                              ("canon gauge", canon_gauge, 2)) + (
            (("canon enemy", canon_enemy, 30),) if has_enemy else ()):
        if len(rows) < need:
            raise SystemExit("%s watch has only %d rows (need %d)"
                             % (name, len(rows), need))

    shift = args.shift
    base = check.align.canon_ref + shift
    if base + 1 + check.frames > len(canon_mm):
        raise SystemExit("canon shift %d runs past the capture (%d rows)"
                         % (shift, len(canon_mm)))

    def at(off):
        return compare(rust_rows[result.rust_origin + result.rust_offset:],
                       canon_mm[base + off:], canon_enemy[base + off:],
                       canon_rng[base + off:], 0, check.frames,
                       has_enemy=has_enemy)

    # The displayed (and nominal) table sits at `base` = canon_ref + shift;
    # the control is the same captures at base+1.
    res = at(0)
    nominal = res
    control = at(1)

    first0 = rust_fields(rust_rows[result.rust_origin + result.rust_offset])
    if has_enemy:
        print("enemy fields watched at canon slot %d (%#x, the populated "
              "enemy for this row; fixture enemies=%d)"
              % (ENEMY_SLOT[args.row], enemy_slot, enemy_count))
    else:
        print("fixture enemies=0: enemy fields SKIPPED (n/a) -- the canon "
              "side's own state object is not this row's fixture")
    print("row %s%s: aligned canon frame %d+k <-> rust marker origin %d + "
          "offset %d + k (search %s); pixel total %d worst %d over %d frames"
          % (args.row, " [canon shifted %+d]" % shift if shift else "",
             check.align.canon_ref, result.rust_origin,
             result.rust_offset,
             ("%d..%d" % (check.align.search.start, check.align.search.stop))
             if check.align.search is not None else "fixed",
             result.total, result.worst, check.frames))
    print("compared rust battle frames %d..%d (from the export block's own "
          "counter) vs canon frames %d..%d"
          % (first0["battle_frame"],
             first0["battle_frame"] + check.frames - 1,
             base, base + check.frames - 1))

    diverged = {n: f for n, f in res.items() if f["first"] is not None}
    parity_names = [n for n in [p[0] for p in FIELD_PAIRS]
                    if has_enemy or not n.startswith("enemy_")] + ["rng_cadence"]
    print("")
    print("PARITY FIELDS -- full table, every compared field "
          "(%d compared frames):" % check.frames)
    for name in parity_names:
        f = res[name]
        if f["first"] is None:
            print("  %-20s match           %d/%d frames"
                  % (name, check.frames, check.frames))
        else:
            print("  %-20s DIVERGES         first k=%d (canon %d, rust "
                  "battle frame %d) canon=%s rust=%s; %d/%d frames"
                  % (name, f["first"], base + f["first"],
                     first0["battle_frame"] + f["first"], f["canon"],
                     f["rust"], f["count"], check.frames))
    if diverged:
        fname, ff = sorted(diverged.items(), key=lambda kv: kv[1]["first"])[0]
        print("FIRST DIVERGENCE: %s at k=%d (canon frame %d) canon=%s "
              "rust=%s"
              % (fname, ff["first"], base + ff["first"], ff["canon"],
                 ff["rust"]))
    else:
        print("FIRST DIVERGENCE: none -- every parity field matches on "
              "every one of the %d compared frames" % check.frames)

    # info-only and unsupported fields, first compared frame. The field
    # contract (module docstring) classifies every requested field; here we
    # print each one's actual values so a silent change cannot hide.
    r0 = rust_fields(rust_rows[result.rust_origin + result.rust_offset])
    c0 = canon_fields_mm(canon_mm[base])
    print("")
    print("INFO-ONLY (fixtures disagree by design -- watched, not compared):")
    print("  rng_abs      canon=%08x rust=%08x (different fixture ages; "
          "the model claim is the 1-step cadence above)"
          % (struct.unpack("<I", canon_rng[base])[0], r0["rng"]))
    print("  mm_hp        canon=%d rust=%d (PAUSED's own damaged navi vs "
          "the descriptor's megaman_hp)" % (c0["hp"], r0["hp"]))
    if has_enemy:
        e0 = canon_fields_enemy(canon_enemy[base])
        print("  enemy_hp     canon=%d rust=%d (ALIVE poke vs the kind's "
              "default)" % (e0["hp"], r0["enemy_hp"]))
    else:
        print("  enemy_hp     n/a (fixture enemies=0)")
    print("  gauge        canon=%d rust=%d (old battle's full gauge vs ours "
          "ticking from the descriptor)"
          % (struct.unpack("<H", canon_gauge[base])[0], r0["gauge"]))
    print("UNSUPPORTED (no honest equivalent on one side -- never compared, "
          "never invented; TODO R7):")
    print("  battle_frame rust=%d (canon has NO known battle-frame RAM word "
          "-- R6 searched; the row's Align is the frame pairing)"
          % r0["battle_frame"])
    if has_enemy:
        e0 = canon_fields_enemy(canon_enemy[base])
        print("  enemy_timer  canon=%d rust=%d (canon reads a CONSTANT "
              "0x0002 at slot+0x20 -- R6 probe; the timing countdown lives "
              "outside the probed +0x00..+0x2f, so nothing dynamic to model)"
              % (e0["timer"], r0["enemy_timer"]))
    else:
        print("  enemy_timer  n/a (fixture enemies=0)")

    # the pixel side of the same alignment, for the consistency report
    counts = [cc.diff_frames(result.canon_dir, base + k,
                             result.rust_dir,
                             result.rust_origin + result.rust_offset + k)
              for k in range(check.frames)]
    nz = [k for k, c in enumerate(counts) if c]
    print("")
    print("PIXEL DIFF on this alignment: first non-zero frame %s, total %d, "
          "worst %d"
          % (("k=%d (%d px)" % (nz[0], counts[nz[0]])) if nz else "none",
             sum(counts), max(counts)))

    # negative control (AUDIT pair 10, TODO R7's contract): the SAME
    # captures, canon shifted +1. The verdict is whether the NOMINAL RESULT
    # changed -- the per-field first-divergence table must move -- not
    # merely whether anything diverges: on an already-divergent row, "still
    # diverges somewhere" under a shift proves nothing.
    def table_key(table):
        return tuple((table[n]["first"], table[n]["count"],
                      table[n]["canon"], table[n]["rust"])
                     for n in sorted(table))

    changed = [n for n in sorted(nominal)
               if table_key({n: nominal[n]}) != table_key({n: control[n]})]
    print("")
    if changed:
        print("NEGATIVE CONTROL (canon shifted +1 frame, same captures): "
              "the nominal result CHANGED on %d/%d compared field(s) -- "
              "NOT BLIND" % (len(changed), len(nominal)))
        for n in changed:
            print("  %-20s nominal first=%s count=%d -> shifted first=%s "
                  "count=%d"
                  % (n, nominal[n]["first"], nominal[n]["count"],
                     control[n]["first"], control[n]["count"]))
    else:
        # Not every UNCHANGED verdict means the same thing (F16): if every
        # compared field held ONE (canon, rust) value pair for the whole
        # window, the state has no timing in it at all -- a one-frame shift
        # cannot move any first-divergence, exactly like the harness's own
        # negative="pixel" precedent for `window` (no timing in the picture
        # to get wrong). If some field IS dynamic yet the table still did
        # not move, that is a genuine red flag, not a static window.
        static = [n for n in sorted(nominal)
                  if len(nominal[n]["pairs"]) > 1 and n != "rng_cadence"]
        print("NEGATIVE CONTROL (canon shifted +1 frame, same captures): "
              "the nominal result is UNCHANGED on every compared field -- "
              "BLIND: a one-frame misalignment would go unreported")
        if not static:
            print("  honest-static: every compared field except the "
                  "shift-invariant-by-construction rng_cadence holds "
                  "exactly ONE (canon, rust) value pair across all %d "
                  "frames -- there is no state timing in this window to "
                  "shift (the row's own pixel negative covers its "
                  "alignment)" % check.frames)
        else:
            print("  NOT honest-static: %s change value across the window, "
                  "yet no first-divergence moved -- investigate before "
                  "trusting this row" % ", ".join(static))


if __name__ == "__main__":
    main()
