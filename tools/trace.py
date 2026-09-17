#!/usr/bin/env python3
"""The state trace (T1): record canon's battle state per frame, replay ours,
name the first divergence.

Field set (both sides, per frame): MegaMan's BattleObject (0x0203a9b0:
CurState +8, CurAction +9, HP +0x24, panel +0x12/+0x13, Timer +0x20, the
mercy counter via CollisionDataPtr +0x54 -> +0x24), the three enemy slots
(0x0203aa88/0x0203ab60/0x0203ac38, same fields), the banner sequencer
(0x0203CA70), the battle-HUD element mask (0x020352C0 update and draw
words), the custom gauge (0x020352A0), the camera (Camera Y +0x34 =
0x020099B4, X +0x30 alongside), the backdrop counters (0x02009690/94) and
GFX anim state (0x020094c0), the RNG seed (0x020013f0). Canon's side is
read by `--watch`; ours comes out of the versioned TRC2 export block
(0x02000080, 64 bytes, src/battle.rs `trace_snapshot`).

usage:
    python3 tools/trace.py record <canon|rust> <scenario> --out DIR
    python3 tools/trace.py diff <canon.dir> <rust.dir> --align <event> [--shift N]

<event> is `row:<scenario>` (the scenario's own stored canon_ref/rust_base
pairing -- the same frames oracle.py compares), `sequencer[=0x08]` (first
frame each side's banner word reads the value), or `frame` (capture frame
0 on both sides). --shift N moves the canon side N frames later (the
negative control is --shift 1).

Calibration (T1): on mettaur, popup and result the parity table below is
oracle.py's own FIELD_PAIRS + rng_cadence, compared on oracle's own frames,
so the first divergence agrees with the oracle by construction -- and the
runs below verify it instead of asserting it. Everything else in the field
set is INFO (recorded, printed, never judged): fixtures disagree by design
(HP, gauge, rng_abs), our model has no counterpart (GFX word), or the
mechanisms differ (camera, backdrop phase). The banner sequencer (T7) is
judged separately below: canon's watched word low half against our exported
state byte (both 0x08 in battle, 0x0C/0x10 past the end count). A record that
carries no sequencer field on either side is a HARD failure, never a match, and
divergence is reported as contiguous k-ranges (T7b: T7's judge skipped frames
whose rust row lacked the field, so every retained TRC2 v2 record read
"match 540/540", and `--align sequencer=` died with StopIteration).
"""

import argparse
import dataclasses
import json
import os
import struct
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness as H  # noqa: E402
import oracle as O  # noqa: E402
import states as S  # noqa: E402

CAPTURE = "/tmp/mgba_capture"
MARKER_ADDR = 0x02000000
ORCL_ADDR = O.MM_ORACLE_ADDR  # the rust export block ("ORCL"); oracle.py reads the address from docs/oracle_layout.json (Q4) -- already an int (oracle.py:60), int(x, 0) only takes strings
ORCL_LEN = O.ORCL_BLOCK_LEN            # from docs/oracle_layout.json, generated from src/battle.rs's ORACLE_LAYOUT (Q4)
TRC2_ADDR = 0x02000080
TRC2_LEN = 64
TRC2_MAGIC = 0x54524332
TRC2_VERSION = 4  # T112: +60 rank, +61 level, +62 zenny (src/battle.rs trace_snapshot's table)

#: Canon watch set: name -> (addr, len). 14 watches (mgba_capture takes 16).
CANON_WATCHES = {
    "rng": (0x020013F0, 4),
    "mm": (0x0203A9B8, 30),
    "e1": (0x0203AA90, 30),
    "e2": (0x0203AB68, 30),
    "e3": (0x0203AC40, 30),
    "banner": (0x0203CA70, 4),
    "hud": (0x020352C0, 8),
    "gauge": (0x020352A0, 2),
    "camera": (0x020099B0, 8),
    "backdrop": (0x02009690, 8),
    "gfx": (0x020094C0, 8),
    "mmbase": (0x0203A9B0, 0x60),
    # T112: the RESULT window's own struct (showResultWindow_802C34E fills it
    # from the results slot 0x02035260: level -> +8, reward halfword -> +0x14,
    # time -> +0x1c; the rank byte at +0xe is sub_802C97E's store,
    # asm03_0.s:13256). One watch covers rank byte (0xe), level byte (8) and
    # the zenny halfword (0x14) for the T112 pair.
    "results": (0x020364C0, 0x20),
}
#: Mercy is a pointer chase ([0x0203a9b0+0x54]+0x24 -- T1 probe: 0x02038514
#: reads 119 on the mettaur hit frame, then counts down), so its address is
#: per-scenario (states.TRACE_SCENARIOS) and verified at record time against
#: the mmbase stream -- never assumed.


def decode_result_reward(word: int) -> int:
    """sub_802C54C (asm03_0.s:12782-12812), the T112 zenny halfword decode:
    0xFFFF = no reward; bits 15-14 clear = a CHIP reward (id = word >> 9,
    count = word & 0x1FF) -- not this pair's number, 0 here; bits 15-14 set =
    the amount in word & 0x3FFF (0x4064 -> 100, watched on RESULT_ARRIVAL)."""
    if word == 0xFFFF or word >> 14 == 0:
        return 0
    return word & 0x3FFF


def parse_canon_frame(streams: dict, mercy_addr: int, i: int) -> dict:
    """One frame's field dict from the canon watch streams (row index i)."""
    g = lambda name: streams[name][i]  # noqa: E731
    es = g("results")
    reward = struct.unpack_from("<H", es, 0x14)[0]
    mm = O.canon_fields_mm(g("mm"))
    e1 = O.canon_fields_mm(g("e1"))
    e2 = O.canon_fields_mm(g("e2"))
    e3 = O.canon_fields_mm(g("e3"))
    hud0, hud1 = struct.unpack_from("<II", g("hud"))
    camx, camy = struct.unpack("<ii", g("camera"))
    bd0, bd1 = struct.unpack("<II", g("backdrop"))
    ptr = struct.unpack_from("<I", streams["mmbase"][i], 0x54)[0]
    if ptr != 0 and ptr + 0x24 != mercy_addr:
        raise SystemExit(
            "mercy pointer moved: scenario says %#x, frame %d reads ptr %#x "
            "(re-resolve tools/trace.py's recipe, not the table)" % (mercy_addr, i, ptr))
    return dict(
        rng=struct.unpack("<I", g("rng"))[0],
        mm_state_action=(mm["state"], mm["action"]),
        mm_anim=mm["anim"], mm_panel_x=mm["panel_x"], mm_panel_y=mm["panel_y"],
        mm_timer=mm["timer"], mm_hp=mm["hp"],
        mercy=struct.unpack("<H", streams["mercy"][i])[0] if ptr != 0 else 0,
        e1_state_action=(e1["state"], e1["action"]),
        e1_anim=e1["anim"], e1_panel_x=e1["panel_x"], e1_panel_y=e1["panel_y"],
        e1_timer=e1["timer"], e1_hp=e1["hp"],
        e2_state_action=(e2["state"], e2["action"]),
        e2_anim=e2["anim"], e2_panel_x=e2["panel_x"], e2_panel_y=e2["panel_y"],
        e2_timer=e2["timer"], e2_hp=e2["hp"],
        e3_state_action=(e3["state"], e3["action"]),
        e3_anim=e3["anim"], e3_panel_x=e3["panel_x"], e3_panel_y=e3["panel_y"],
        e3_timer=e3["timer"], e3_hp=e3["hp"],
        banner=struct.unpack("<I", g("banner"))[0],
        hud_update=hud0, hud_draw=hud1,
        gauge=struct.unpack("<H", g("gauge"))[0],
        camera_x=camx, camera_y=camy,
        backdrop0=bd0, backdrop1=bd1,
        gfx=g("gfx").hex(),
        # T112: the results-window words. rank = eS20364C0+0xe (sub_802C97E's
        # store, asm03_0.s:13256); zenny = the +0x14 reward halfword decoded
        # by sub_802C54C (asm03_0.s:12782-12812); the raw halfword and the
        # level byte (eS+8, drawResultLevel_802C6EC) ride as info.
        rank=es[0x0E], results_level=es[8],
        zenny=decode_result_reward(reward), results_reward_raw=reward,
    )


def parse_trc2_row(row: bytes) -> dict:
    """One frame's field dict from a 64-byte TRC2 export row."""
    if struct.unpack_from("<I", row, 0)[0] != TRC2_MAGIC:
        raise SystemExit("TRC2 magic missing -- stale ROM? (want %#x)" % TRC2_MAGIC)
    if struct.unpack_from("<H", row, 4)[0] != TRC2_VERSION:
        raise SystemExit("TRC2 version mismatch -- rebuild the ROM (want %d)" % TRC2_VERSION)
    u16 = lambda o: struct.unpack_from("<H", row, o)[0]  # noqa: E731
    u32 = lambda o: struct.unpack_from("<I", row, o)[0]  # noqa: E731
    i32 = lambda o: struct.unpack_from("<i", row, o)[0]  # noqa: E731
    return dict(
        frame=u32(8), rng=u32(12),
        mm_state_action=(row[16], row[17]) if False else (u16(16) & 0xFF, (u16(16) >> 8) & 0xFF),
        mm_anim=row[18], mm_panel_x=row[19], mm_panel_y=row[20],
        mercy=row[21], mm_timer=u16(22), mm_hp=u16(24),
        e1_state_action=(u16(26) & 0xFF, (u16(26) >> 8) & 0xFF),
        e1_anim=row[28], e1_panel_x=row[29], e1_panel_y=row[30],
        e1_timer=u16(32), e1_hp=u16(34),
        e2_state_action=u16(36), e3_state_action=u16(38),
        gauge=u16(40), sequencer=u16(42), hud_mask=u16(44),
        backdrop_entry=u16(46), backdrop_timer=u16(48),
        backdrop_xq=u32(50), backdrop_yq=u32(54),
        field_slide=u16(58),
        # T112: the results-window words (rank byte, level byte, zenny amount
        # halfword) at +60/+61/+62 -- src/battle.rs trace_snapshot's table.
        rank=row[60], results_level=row[61], zenny=u16(62),
    )


#: Parity fields (name -> (rust getter, canon getter)): oracle.py's own
#: FIELD_PAIRS verbatim, so the trace's first divergence IS the oracle's on
#: the same frames. rng_cadence is compared separately, same rule as oracle.
PARITY = O.FIELD_PAIRS
#: Canon enemy-slot index per scenario for the E1 parity fields (oracle's
#: ENEMY_SLOT, restricted to what the trace records).
E1_SLOT = {"mettaur": "e2", "popup": None, "result": None, "battle_full": "e2"}

#: Info fields: recorded and printed, never judged.
INFO_RUST = ["mercy", "mm_hp", "e1_hp", "gauge", "rng",
             "sequencer", "hud_mask", "backdrop_entry", "backdrop_timer",
             "backdrop_xq", "backdrop_yq", "field_slide", "results_level"]
INFO_CANON = ["mercy", "mm_hp", "e1_hp", "gauge", "rng",
              "banner", "hud_update", "hud_draw",
              "backdrop0", "backdrop1", "camera_x", "camera_y", "gfx",
              "results_level", "results_reward_raw"]

#: T112: the results-window pair, judged with the PARITY fields (same loop,
#: same report shape): the rank byte and the decoded zenny amount, ours from
#: the TRC2 +60/+62 export (the values fed to results.show), canon's from the
#: eS20364C0 watch (+0xe byte, +0x14 halfword through decode_result_reward).
T112_PAIRS = ("rank", "zenny")


def rows_of(path: str, width: int) -> list:
    data = open(path, "rb").read()
    if len(data) % width:
        raise SystemExit("%s: %d bytes is not a multiple of %d" % (path, len(data), width))
    return [data[i * width:(i + 1) * width] for i in range(len(data) // width)]


#: The rust-side trace-enable bit (T1b): src/fixture.rs FLAG_TRACE, bit 7
#: of the descriptor's flags byte. Recordings OR it into the rust fixture
#: so the ROM writes the TRC2 block every frame; pixel rows leave it clear
#: and run byte-identical to a build without the export (field integrated
#: back at 158950). Per-frame --cheat delivery, like every other flag, so
#: it survives boot -- never a one-shot --poke.
TRACE_FLAG = 0x80


def with_trace(side: H.Side) -> H.Side:
    """The same side with the trace export switched on (recordings only)."""
    if side.fixture is not None:
        fixture = dict(side.fixture)
        fixture["flags"] = fixture.get("flags", 0) | TRACE_FLAG
        return dataclasses.replace(side, fixture=fixture)
    # No descriptor on this side: plant just the flags word (descriptor
    # +18: low byte gauge, high byte flags) -- trace_enabled reads the raw
    # byte with no magic check, so this still switches the export on.
    return dataclasses.replace(
        side, cheats=tuple(side.cheats) + ("0x02000052:0x8000",))


def scenario_side(scen: dict, side: str) -> H.Side:
    if "harness_row" in scen:
        checks = [c for c in H.CHECKS if c.name == scen["harness_row"]]
        assert checks, scen
        got = (checks[0].canon if side == "canon" else checks[0].rust)("isolated")
        return with_trace(got) if side == "rust" else got
    spec = dict(scen[side])
    if side == "rust":
        return with_trace(H.Side(rom=H.plain_rom(), fixture=spec.pop("fixture"),
                      script=spec.pop("script", None),
                      extra=tuple(spec.pop("extra", ())), **spec))
    return H.Side(**spec)


def cmd_record(args) -> None:
    scen = S.TRACE_SCENARIOS.get(args.scenario)
    if scen is None:
        raise SystemExit("unknown scenario %r (states.TRACE_SCENARIOS: %s)"
                         % (args.scenario, sorted(S.TRACE_SCENARIOS)))
    side = scenario_side(scen, args.side)
    os.makedirs(args.out, exist_ok=True)
    if args.side == "canon":
        # The compared window starts at canon_ref: capture through its end.
        count = scen["canon_ref"] + scen["frames"] + 4
    else:
        # The compared window is export-counter selected below: capture
        # through its end whatever the marker origin is.
        count = scen["rust_base"] + scen["frames"] + 32
    cmd = [CAPTURE, side.resolved_rom(), args.out, str(count)] + side.args()
    if args.side == "canon":
        for name, (addr, ln) in CANON_WATCHES.items():
            cmd += ["--watch", "%#x:%d:%s" % (addr, ln, os.path.join(args.out, name + ".bin"))]
        mercy_addr = scen["mercy_addr"]
        cmd += ["--watch", "%#x:2:%s" % (mercy_addr, os.path.join(args.out, "mercy.bin"))]
    else:
        cmd += ["--watch", "%#x:%d:%s" % (ORCL_ADDR, ORCL_LEN, os.path.join(args.out, "orcl.bin"))]
        cmd += ["--watch", "%#x:%d:%s" % (TRC2_ADDR, TRC2_LEN, os.path.join(args.out, "trc2.bin"))]
        cmd += ["--watch", "%#x:8:%s" % (MARKER_ADDR, os.path.join(args.out, "marker.bin"))]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit("capture failed: %s" % r.stderr[-2000:])
    if args.side == "canon":
        streams = {n: rows_of(os.path.join(args.out, n + ".bin"), ln)
                   for n, (_, ln) in CANON_WATCHES.items()}
        streams["mercy"] = rows_of(os.path.join(args.out, "mercy.bin"), 2)
        table = [parse_canon_frame(streams, scen["mercy_addr"], i) for i in range(count)]
    else:
        trc2 = rows_of(os.path.join(args.out, "trc2.bin"), TRC2_LEN)
        parsed = []
        for row in trc2:
            if row[:4] != TRC2_MAGIC.to_bytes(4, "little"):
                continue  # pre-battle rows: the block reads zero until the first update
            parsed.append(parse_trc2_row(row))
        r0, nframes = scen["rust_base"], scen["frames"]
        table = [fr for fr in parsed if r0 <= fr["frame"] < r0 + nframes]
        if len(table) < nframes:
            raise SystemExit("short table: %d < %d (counters %s..%s)"
                             % (len(table), nframes,
                                parsed[0]["frame"] if parsed else "-",
                                parsed[-1]["frame"] if parsed else "-"))
    # JSON-ify tuples.
    def conv(v):
        return list(v) if isinstance(v, tuple) else v
    with open(os.path.join(args.out, "table.json"), "w") as f:
        json.dump([{k: conv(v) for k, v in fr.items()} for fr in table], f)
    with open(os.path.join(args.out, "meta.json"), "w") as f:
        json.dump(dict(scenario=args.scenario, side=args.side, frames=scen["frames"],
                       canon_ref=scen.get("canon_ref"), rust_base=scen.get("rust_base"),
                       mercy_addr=scen.get("mercy_addr")), f, indent=1)
    print("recorded %s %s: %d frames -> %s" % (args.side, args.scenario, scen["frames"], args.out))


def load_table(d: str) -> tuple:
    with open(os.path.join(d, "meta.json")) as f:
        meta = json.load(f)
    with open(os.path.join(d, "table.json")) as f:
        table = json.load(f)
    return meta, table


#: The sequencer field's own name on each side (T7b). Canon's is the watched
#: dword_203CA70 (`banner`); ours is the TRC2 v3 export's `sequencer` (offset
#: 42, the word's low half -- src/battle.rs `trace_snapshot`).
SEQ_CANON_KEY = "banner"
SEQ_RUST_KEY = "sequencer"
#: `--align sequencer` with no value: the fight state, canon's own first one
#: (states.TRACE_SCENARIOS battle_full canon_ref 11 is `the first sequencer
#: 0x08`, T1 probe).
SEQ_DEFAULT = 0x08
#: The mask both sides are compared under: the state is the watched word's LOW
#: HALF (byte 1 reads 0 on every recorded frame of every scenario here, and the
#: TRC2 export is a u16), so canon's 0x0400000C and our 0x0C are the same state.
SEQ_MASK = 0xFFFF


def require_seq(table: list, side: str, d: str, key: str) -> None:
    """Fail loudly when a record cannot judge the sequencer at all (T7b).

    T7's judge read the rust side with `.get(SEQ_RUST_KEY)` and skipped the
    frame whenever the key was absent, so a TRC2 v2 record -- every record
    retained before this ticket -- printed `sequencer match N/N frames` for
    every frame. A missing field is a broken measurement, not a match: name
    the side, the directory, the key and what that side does carry."""
    if not table:
        raise SystemExit("%s side (%s): empty table -- re-record "
                         "(python3 tools/trace.py record %s <scenario> --out %s)"
                         % (side, d, side, d))
    have = sorted(table[0].keys())
    missing = [i for i, fr in enumerate(table) if key not in fr]
    if len(missing) == len(table):
        raise SystemExit(
            "%s side (%s) has no %r field in any of its %d rows -- the "
            "sequencer cannot be judged, and this tool will not report a "
            "match for a field that is not there. Re-record it against the "
            "TRC2 v3 export (tools/trace.py record %s <scenario> --out %s); "
            "that record's rows carry: %s"
            % (side, d, key, len(table), side, d, ", ".join(have)))
    if missing:
        raise SystemExit(
            "%s side (%s): %d of %d rows have no %r field (first at index %d) "
            "-- a half-written record cannot judge the sequencer; re-record it"
            % (side, d, len(missing), len(table), key, missing[0]))


def first_event(table: list, pred, side: str, d: str, val: int,
                key: str = None) -> int:
    """The first row index (or its export frame, with key=) matching pred, or
    a loud failure naming the values the side actually read.

    T7 used bare next(...), so `--align sequencer=0x10` on a win run raised
    StopIteration out of argparse and looked like a crash rather than the
    ordinary "that event never happened in this recording"."""
    for i, fr in enumerate(table):
        if pred(fr):
            return fr[key] if key else i
    seen = sorted({(int(fr.get(SEQ_CANON_KEY) if key is None
                     else fr.get(SEQ_RUST_KEY)) or 0) & SEQ_MASK
                   for fr in table if (fr.get(SEQ_CANON_KEY) if key is None
                                       else fr.get(SEQ_RUST_KEY)) is not None})
    raise SystemExit(
        "--align sequencer=%#x: the %s side (%s) never reads %#x -- its %d "
        "recorded rows read %s. Align on a state that happens, or re-record."
        % (val, side, d, val, len(table),
           ", ".join(hex(v & SEQ_MASK) for v in seen)))


def divergent_runs(pairs: list) -> list:
    """Group [(k, canon, rust), ...] into contiguous runs of the same value
    pair: [(k0, k1, canon, rust), ...]. The report names the remainder by
    k-range, which is what 'k-ranges with the remainder named' asks for."""
    runs = []
    for k, cval, rval in pairs:
        if runs and runs[-1][1] == k - 1 and runs[-1][2] == cval and runs[-1][3] == rval:
            runs[-1][1] = k
        else:
            runs.append([k, k, cval, rval])
    return runs


def cmd_diff(args) -> None:
    cmeta, ctab = load_table(args.canon_dir)
    rmeta, rtab = load_table(args.rust_dir)
    scen = S.TRACE_SCENARIOS.get(cmeta["scenario"], S.TRACE_SCENARIOS.get(rmeta["scenario"], {}))
    align = args.align
    if align.startswith("row:"):
        name = align.split(":", 1)[1]
        sc = S.TRACE_SCENARIOS[name]
        c0, r0 = sc["canon_ref"] + args.shift, sc["rust_base"]
        frames = sc["frames"]
        how = "row %s: canon frame %d+k <-> rust export frame %d+k" % (name, c0, r0)
    elif align.startswith("sequencer"):
        val = int(align.split("=", 1)[1], 0) if "=" in align else SEQ_DEFAULT
        # T7b: the sequencer is an alignment EVENT, so it has to exist on both
        # sides; require_seq names the record that cannot serve, and
        # first_event names the values a side did read. Both replace T7's bare
        # next() (StopIteration) and its `.get()` (false-green judge).
        require_seq(ctab, "canon", args.canon_dir, SEQ_CANON_KEY)
        require_seq(rtab, "rust", args.rust_dir, SEQ_RUST_KEY)
        c0 = first_event(ctab, lambda fr: (fr[SEQ_CANON_KEY] & SEQ_MASK) == val,
                         "canon", args.canon_dir, val) + args.shift
        # T7: the rust side exports the sequencer word's low half (TRC2 v3),
        # so both sides align on the event itself -- e.g. =0x0C pairs the two
        # end counts whatever each side's killing-blow frame is.
        r0 = first_event(rtab, lambda fr: (fr[SEQ_RUST_KEY] & SEQ_MASK) == val,
                         "rust", args.rust_dir, val, key="frame")
        frames = min(len(ctab) - c0,
                     sum(1 for fr in rtab if fr.get("frame", -1) >= r0))
        how = "sequencer %#x: canon frame %d+k <-> rust export frame %d+k" % (val, c0, r0)
    elif align == "frame":
        c0, r0 = 0 + args.shift, 0
        frames = min(len(ctab) - c0, len(rtab))
        how = "frame: canon capture %d+k <-> rust capture %d+k" % (c0, r0)
    else:
        raise SystemExit("unknown --align %r (row:<scenario> | frame)" % align)
    # Rust rows are keyed by capture index; rust_base is an export-frame
    # counter, so find the capture row whose TRC2 frame == rust_base.
    if not (r0 <= max(fr.get("frame", -1) for fr in rtab)):
        raise SystemExit("the rust side (%s) has no row at export frame %d "
                         "(its counters run %d..%d) -- re-record or align on "
                         "a frame inside the recording"
                         % (args.rust_dir, r0,
                            min(fr.get("frame", 0) for fr in rtab), r0))
    rbase = next(i for i, fr in enumerate(rtab) if fr.get("frame", i) == r0)
    # T7b pairing: the window is defined by EXPORT COUNTER, not row index. Our
    # counter stalls (the synchronous show_results CPU stall F33d attributed:
    # battle_full's record repeats counter 405 on 4 consecutive capture rows),
    # so an index walk `rtab[rbase + k]` silently slides every later canon
    # frame onto a rust frame that is up to N ahead. Pair by counter and say
    # loudly how many stalls the window contains.
    # T7b: the pairing stays the capture-index walk T1..T7 used -- row i of the
    # rust record is capture frame i, which is what the PIXEL timeline is, and
    # changing it silently would move every later divergence. But our export
    # counter stalls (battle_full repeats counter 405 on 4 capture rows and then
    # skips 406: the synchronous show_results CPU stall F33d attributed), so say
    # loudly, before any number is read, that after the stall the counter and the
    # index differ by N -- otherwise `first k=428` is read as a battle-frame
    # delta when it is 4 capture frames of our own stall.
    seen = {}
    repeats = 0
    jumps = 0
    for i, fr in enumerate(rtab[rbase:rbase + frames], start=rbase):
        c = fr.get("frame")
        if c in seen:
            repeats += 1
        else:
            if i > rbase and c != r0 + (i - rbase):
                jumps += 1
            seen[c] = i
    if repeats or jumps:
        last = rtab[rbase + frames - 1].get("frame")
        print("NOTE: the rust export counter is not one-per-row in this window "
              "(%d repeated row(s), %d jumped row(s) -- the synchronous show_results "
              "CPU stall F33d attributed). Rows are paired by CAPTURE INDEX (the pixel "
              "timeline), so the last compared row's counter is %d where a stall-free "
              "clock would read %d: the %d-frame drift is OURS, not a canon divergence"
              % (repeats, jumps, last, r0 + frames - 1, (r0 + frames - 1) - last))
    frames = min(frames, len(ctab) - c0, len(rtab) - rbase)
    # The sequencer is judged on every align, so require it here too (T7b):
    # row-mode diffs used to print `match` off a v2 record that had no field.
    require_seq(ctab, "canon", args.canon_dir, SEQ_CANON_KEY)
    require_seq(rtab, "rust", args.rust_dir, SEQ_RUST_KEY)
    e1slot = E1_SLOT.get(cmeta["scenario"], "e2")
    has_enemy = e1slot is not None
    out = {}
    for name, _, _ in PARITY:
        if name.startswith("enemy_") and not has_enemy:
            continue
        out[name] = dict(first=None, count=0, canon=None, rust=None)
    for name in T112_PAIRS:  # T112: the results-window pair, judged like PARITY
        out[name] = dict(first=None, count=0, canon=None, rust=None)
    out["rng_cadence"] = dict(first=None, count=0, canon=None, rust=None)
    prev_rrng = prev_crng = None
    for k in range(frames):
        c, r = ctab[c0 + k], rtab[rbase + k]
        rmm = dict(state=r["mm_state_action"][0], action=r["mm_state_action"][1],
                   anim=r["mm_anim"], panel_x=r["mm_panel_x"],
                   panel_y=r["mm_panel_y"], timer=r["mm_timer"])
        cmm = dict(state=c["mm_state_action"][0], action=c["mm_state_action"][1],
                   anim=c["mm_anim"], panel_x=c["mm_panel_x"],
                   panel_y=c["mm_panel_y"], timer=c["mm_timer"])
        ex = e1slot or "e1"
        rE = dict(enemy_state=r["e1_state_action"][0], enemy_action=r["e1_state_action"][1],
                  enemy_anim=r["e1_anim"], enemy_panel_x=r["e1_panel_x"],
                  enemy_panel_y=r["e1_panel_y"])
        cE = dict(state=c[ex + "_state_action"][0], action=c[ex + "_state_action"][1],
                  anim=c[ex + "_anim"], panel_x=c[ex + "_panel_x"],
                  panel_y=c[ex + "_panel_y"])
        for name, rget, cget in PARITY:
            if name.startswith("enemy_") and not has_enemy:
                continue
            if name.startswith("enemy_"):
                rval, cval = rget(rE), cget(cE)
            else:
                rval, cval = rget(rmm), cget(cmm)
            rval = tuple(rval) if isinstance(rval, list) else rval
            cval = tuple(cval) if isinstance(cval, list) else cval
            if rval != cval:
                f = out[name]
                if f["first"] is None:
                    f["first"], f["canon"], f["rust"] = k, cval, rval
                f["count"] += 1
        # T112: the results-window pair -- plain exported/watched fields, same
        # divergence tail as the PARITY loop above.
        for name in T112_PAIRS:
            rval, cval = r[name], c[name]
            if rval != cval:
                f = out[name]
                if f["first"] is None:
                    f["first"], f["canon"], f["rust"] = k, cval, rval
                f["count"] += 1
        crng = c["rng"]
        if prev_rrng is not None:
            if r["rng"] != O.rng_step(prev_rrng) or crng != O.rng_step(prev_crng):
                f = out["rng_cadence"]
                if f["first"] is None:
                    f["first"] = k
                    f["canon"], f["rust"] = (prev_crng, crng), (prev_rrng, r["rng"])
                f["count"] += 1
        prev_rrng, prev_crng = r["rng"], crng
    print("trace diff %s vs %s -- %s, %d compared frames (shift %d)"
          % (args.canon_dir, args.rust_dir, how, frames, args.shift))
    # T7 acceptance field: the sequencer word's low half on both sides.
    # Judged and printed like a parity field, but NOT folded into FIRST
    # DIVERGENCE below, which stays parity-defined (oracle.py FIELD_PAIRS).
    seq = dict(first=None, count=0, canon=None, rust=None)
    seq_runs = []
    for k in range(frames):
        cval = ctab[c0 + k][SEQ_CANON_KEY] & SEQ_MASK
        rval = rtab[rbase + k][SEQ_RUST_KEY] & SEQ_MASK
        if rval != cval:
            if seq["first"] is None:
                seq["first"], seq["canon"], seq["rust"] = k, hex(cval), hex(rval)
            seq["count"] += 1
            seq_runs.append((k, cval, rval))
    if seq["first"] is None:
        print("  %-18s match          %d/%d frames" % ("sequencer", frames, frames))
    else:
        print("  %-18s DIVERGES       first k=%d (canon frame %d) canon=%s rust=%s; %d/%d frames"
              % ("sequencer", seq["first"], c0 + seq["first"],
                 seq["canon"], seq["rust"], seq["count"], frames))
        # The remainder, named frame by frame as contiguous k-ranges: which
        # canon state is on screen while ours says something else.
        for k0, k1, cval, rval in divergent_runs(seq_runs):
            print("  %-18s   k=%-4d..%-4d (canon frame %d..%d) canon=%s rust=%s  %d frames"
                  % ("", k0, k1, c0 + k0, c0 + k1,
                     hex(cval), hex(rval), k1 - k0 + 1))
    for name in [p[0] for p in PARITY if not (p[0].startswith("enemy_") and not has_enemy)] + list(T112_PAIRS) + ["rng_cadence"]:
        f = out[name]
        if f["first"] is None:
            print("  %-18s match          %d/%d frames" % (name, frames, frames))
        else:
            print("  %-18s DIVERGES       first k=%d (canon frame %d) canon=%s rust=%s; %d/%d frames"
                  % (name, f["first"], c0 + f["first"], f["canon"], f["rust"], f["count"], frames))
    firsts = [(f["first"], n) for n, f in out.items() if f["first"] is not None]
    if not firsts:
        print("FIRST DIVERGENCE: none -- every parity field matches on every one of the %d compared frames" % frames)
    else:
        firsts.sort()
        k, n = firsts[0]
        print("FIRST DIVERGENCE: %s at k=%d (canon frame %d) canon=%s rust=%s"
              % (n, k, c0 + k, out[n]["canon"], out[n]["rust"]))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("record")
    p.add_argument("side", choices=["canon", "rust"])
    p.add_argument("scenario")
    p.add_argument("--out", required=True)
    p.set_defaults(fn=cmd_record)
    p = sub.add_parser("diff")
    p.add_argument("canon_dir")
    p.add_argument("rust_dir")
    p.add_argument("--align", required=True)
    p.add_argument("--shift", type=int, default=0)
    p.set_defaults(fn=cmd_diff)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
