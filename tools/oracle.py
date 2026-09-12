#!/usr/bin/env python3
"""The state oracle (TODO R6): the first divergent FIELD and frame, not
just a pixel count.

One harness row, both sides captured with `--watch`:

  rust  -- the plain fixture ROM. Two watch streams: the battle marker
           (0x02000000:8, for marker-origin alignment -- added by
           `harness.Side.do_capture` exactly as `harness.run` does) and the
           ROM's own state-export block (0x02000080:40, `ORCL`, written by
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

Compared fields (both sides genuinely model them):

  rng_cadence   both streams must advance EXACTLY one GetRNG step per frame
                (seed = rotl+1 ^ 0x873ca9e5, asm00_0.s:2610-2622; canon
                measured 1 step/frame over 219 transitions -- ai.rs's module
                doc; ours by construction in `Battle::update`). Deliberately
                NOT absolute-value equality: the two fixtures' battles are
                different AGES (canon's is a mid-battle save state, ours
                starts at the descriptor), so the two streams sit at
                different points of the orbit by construction. The absolute
                values are printed as info instead; the seeds differ by the
                same design choice (src/ai.rs DEFAULT_SEED's doc).
  mm_state_action, mm_anim, mm_panel_x, mm_panel_y, mm_timer
  enemy_state_action, enemy_anim, enemy_panel_x, enemy_panel_y

Info-only fields (exported/watched but NOT compared, each with the reason):
  battle_frame  rust-only: canon has no known battle-frame RAM word, and
                the row's Align already IS the frame pairing.
  mm_hp         the PAUSED rows' canon side reads 0x003c (the capture's own
                damaged navi) while the descriptor says megaman_hp=100 --
                a fixture disagreement, not a model defect.
  enemy_hp      canon's is poked 0xffff by the ALIVE cheat by design.
  enemy_timer   canon reads a CONSTANT 0x0002 there for the whole probe
                window (the swing countdown lives outside +0x00..+0x2f);
                nothing dynamic to model, the export returns 0.
  gauge         canon's is full (0x4000) from the old battle; ours ticks
                from the descriptor's gauge field -- fixture age again.

Negative control (AUDIT pair 10, oracle edition): the SAME field
comparison with the canon side shifted one frame later must report a
divergence on some compared field, or the oracle is BLIND on that row.

Usage:
  python3 tools/oracle.py <row>            # wave, mettaur
  python3 tools/oracle.py <row> --shift N  # canon shifted N frames (default 0)
"""

import argparse
import dataclasses
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import chip_compare as cc  # noqa: E402
import harness as H  # noqa: E402

# --- the field model ---------------------------------------------------------


def rng_step(seed: int) -> int:
    """One GetRNG step (asm00_0.s:2610-2622; ai.rs's own formula):
    seed = rotl(seed, 1) + 1 ^ 0x873ca9e5."""
    return ((((seed << 1) | (seed >> 31)) & 0xFFFFFFFF) + 1) & 0xFFFFFFFF ^ 0x873CA9E5


MM_BASE = 0x0203A9B8  # eT1BattleObject0 + oBattleObject_CurState
GAUGE_ADDR = 0x020352A0  # eStruct2035280 + 0x20
RNG_ADDR = 0x020013F0  # ePrimaryRngSeed
MM_ORACLE_ADDR = 0x02000008  # the rust export block ("ORCL", 40 bytes)

#: Per-row configuration: the canon address of the POPULATED enemy slot.
#: Everything else is the row's own Check definition.
ROWS = {
    "wave": dict(enemy_slot=0x0203AB60),
    "mettaur": dict(enemy_slot=0x0203AB60),
}

#: fields where the two FIXTURES disagree by design, watched and printed but
#: never compared -- each with its one-line reason (see module doc).
INFO_FIELDS = ["battle_frame", "mm_hp", "enemy_hp", "enemy_timer", "gauge",
               "rng_abs"]

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
    """From one 40-byte ORCL block row -- battle.rs oracle_snapshot's map."""
    return dict(
        state=row[12],
        action=row[13],
        anim=row[14],
        panel_x=row[15],
        panel_y=row[16],
        timer=struct.unpack_from("<H", row, 18)[0],
        hp=struct.unpack_from("<H", row, 20)[0],
        enemy_state=row[22],
        enemy_action=row[23],
        enemy_anim=row[24],
        enemy_panel_x=row[25],
        enemy_panel_y=row[26],
        enemy_timer=struct.unpack_from("<H", row, 28)[0],
        enemy_hp=struct.unpack_from("<H", row, 30)[0],
        battle_frame=struct.unpack_from("<I", row, 4)[0],
        rng=struct.unpack_from("<I", row, 8)[0],
        gauge=struct.unpack_from("<H", row, 32)[0],
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
            canon_rng: list, offset: int, frames: int) -> dict:
    """First divergent frame per compared field at `offset` (rust row index
    = offset + k, canon row index = canon_ref + k, already applied by the
    callers slicing the row lists)."""
    out = {}
    for name in [p[0] for p in FIELD_PAIRS] + ["rng_cadence"]:
        out[name] = dict(first=None, count=0, canon=None, rust=None)
    prev_rust_rng = prev_canon_rng = None
    for k in range(frames):
        r = rust_fields(rust_rows[offset + k])
        c = canon_fields_mm(canon_mm[k])
        e = canon_fields_enemy(canon_enemy[k])
        for name, rget, cget in FIELD_PAIRS:
            cval = cget(e if name.startswith("enemy_") else c)
            rval = rget(r)
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
                if f["first"] is None:
                    f["first"] = k
                    f["canon"] = (prev_canon_rng, crng)
                    f["rust"] = (prev_rust_rng, r["rng"])
                f["count"] += 1
        prev_rust_rng, prev_canon_rng = r["rng"], crng
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("row")
    ap.add_argument("--shift", type=int, default=0,
                    help="canon side shifted N frames later (the negative "
                         "control is --shift 1 on the same captures)")
    args = ap.parse_args()

    if args.row not in ROWS:
        raise SystemExit("no oracle configuration for row %r (have: %s)"
                         % (args.row, ", ".join(sorted(ROWS))))
    cfg = ROWS[args.row]
    check = [c for c in H.CHECKS if c.name == args.row][0]
    if check.ui not in ("isolated", "integrated"):
        raise SystemExit("row %s has ui=%r; the oracle runs one variant"
                         % (args.row, check.ui))
    variant = "isolated" if check.ui in ("isolated", "both") else "integrated"

    enemy_slot = cfg["enemy_slot"]
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
        # slot + oBattleObject_CurState (+0x08): same layout as the MM watch
        "--watch", "%#x:30:%s" % (enemy_slot + 0x08, canon_enemy_file),
        "--watch", "%#x:2:%s" % (GAUGE_ADDR, canon_gauge_file),
    ]
    rust_watch = ["--watch", "%#x:40:%s" % (MM_ORACLE_ADDR, rust_block_file)]

    def sides():
        rust_side = check.rust(variant)
        rust = dataclasses.replace(rust_side,
                                   extra=rust_side.extra + tuple(rust_watch))
        canon_side = check.canon(variant)
        canon = dataclasses.replace(canon_side,
                                    extra=canon_side.extra + tuple(canon_watch))
        return rust, canon

    for path in (canon_rng_file, canon_mm_file, canon_enemy_file,
                 canon_gauge_file, rust_block_file):
        if os.path.exists(path):
            os.unlink(path)

    rust, canon = sides()
    result = H.run(rust, canon, check.frames, check.align)
    print("row %s: aligned canon frame %d+k <-> rust marker origin %d + "
          "offset %d + k (search %s); pixel total %d worst %d over %d frames"
          % (args.row, check.align.canon_ref, result.rust_origin,
             result.rust_offset,
             ("%d..%d" % (check.align.search.start, check.align.search.stop))
             if check.align.search is not None else "fixed",
             result.total, result.worst, check.frames))

    rust_rows = watch_rows(rust_block_file, 40)
    canon_mm = watch_rows(canon_mm_file, 30)
    canon_enemy = watch_rows(canon_enemy_file, 30)
    canon_rng = watch_rows(canon_rng_file, 4)
    canon_gauge = watch_rows(canon_gauge_file, 2)
    need = check.frames + max(args.shift, 0)
    for name, rows, width in (("rust block", rust_rows, 40),
                              ("canon mm", canon_mm, 30),
                              ("canon enemy", canon_enemy, 30),
                              ("canon rng", canon_rng, 4),
                              ("canon gauge", canon_gauge, 2)):
        if len(rows) < need:
            raise SystemExit("%s watch has only %d rows (need %d)"
                             % (name, len(rows), need))

    shift = args.shift
    base = check.align.canon_ref + shift
    if base + check.frames > len(canon_mm):
        raise SystemExit("canon shift %d runs past the capture (%d rows)"
                         % (shift, len(canon_mm)))
    res = compare(rust_rows[result.rust_origin + result.rust_offset:],
                  canon_mm[base:], canon_enemy[base:], canon_rng[base:],
                  0, check.frames)

    first0 = rust_fields(rust_rows[result.rust_origin + result.rust_offset])
    print("compared rust battle frames %d..%d (from the export block's own "
          "counter) vs canon frames %d..%d"
          % (first0["battle_frame"],
             first0["battle_frame"] + check.frames - 1,
             base, base + check.frames - 1))

    diverged = {n: f for n, f in res.items() if f["first"] is not None}
    print("")
    print("COMPARED FIELDS (%s):" % ("FIRST DIVERGENCE" if diverged else "all match"))
    if not diverged:
        print("  every compared field matches canon on every one of the "
              "%d compared frames" % check.frames)
    for name, f in sorted(diverged.items(), key=lambda kv: kv[1]["first"]):
        print("  %-20s first frame k=%d (canon %d, rust battle frame %d) "
              "canon=%s rust=%s; diverged on %d/%d frames"
              % (name, f["first"], base + f["first"],
                 first0["battle_frame"] + f["first"], f["canon"], f["rust"],
                 f["count"], check.frames))

    # info-only fields, first compared frame
    r0 = rust_fields(rust_rows[result.rust_origin + result.rust_offset])
    c0 = canon_fields_mm(canon_mm[base])
    e0 = canon_fields_enemy(canon_enemy[base])
    print("")
    print("INFO-ONLY (fixtures disagree by design -- not compared):")
    print("  battle_frame rust=%d (canon side has no such RAM word)"
          % r0["battle_frame"])
    print("  rng_abs      canon=%08x rust=%08x (different fixture ages; "
          "the model claim is the 1-step cadence above)"
          % (struct.unpack("<I", canon_rng[base])[0], r0["rng"]))
    print("  mm_hp        canon=%d rust=%d (PAUSED's own damaged navi vs "
          "the descriptor's megaman_hp)" % (c0["hp"], r0["hp"]))
    print("  enemy_hp     canon=%d rust=%d (ALIVE poke vs the kind's default)"
          % (e0["hp"], r0["enemy_hp"]))
    print("  enemy_timer  canon=%d rust=%d (canon constant, nothing dynamic "
          "to model)" % (e0["timer"], r0["enemy_timer"]))
    print("  gauge        canon=%d rust=%d (old battle's full gauge vs ours "
          "ticking from the descriptor)"
          % (struct.unpack("<H", canon_gauge[base])[0], r0["gauge"]))

    # the pixel side of the same alignment, for the consistency report
    counts = [cc.diff_frames(result.canon_dir, base + k,
                             result.rust_dir,
                             result.rust_origin + result.rust_offset + k)
              for k in range(check.frames)]
    nz = [k for k, c in enumerate(counts) if c]
    print("")
    print("PIXEL DIFF on this alignment: first non-zero frame %s, total %d, "
          "worst %d"
          % (("k=%d" % nz[0]) if nz else "none", sum(counts), max(counts)))

    # negative control: same captures, canon shifted +1 -- must diverge.
    if shift == 0 and base + 1 + check.frames <= len(canon_mm):
        neg = compare(rust_rows[result.rust_origin + result.rust_offset:],
                      canon_mm[base + 1:], canon_enemy[base + 1:],
                      canon_rng[base + 1:], 0, check.frames)
        fields_moved = sorted(n for n, f in neg.items() if f["first"] is not None)
        print("")
        print("NEGATIVE CONTROL (canon shifted +1 frame, same captures): %s"
              % ("diverges on %d field(s): %s -- NOT BLIND"
                 % (len(fields_moved), ", ".join(fields_moved))
                 if fields_moved else "BLIND -- no compared field moved"))


if __name__ == "__main__":
    main()
