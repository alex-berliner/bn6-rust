#!/usr/bin/env python3
"""One harness, one job (AUDIT.md pair 6): capture both sides of a check,
align them on an event instead of a frame number, and require zero
differing pixels over the whole 240x160 for every compared frame. No boxes,
no `want`.

    run(rust, canon, frames, align) -> Result

`rust` and `canon` are `Side`s -- how to produce one side's capture
(tools/mgba_capture.c arguments: a ROM, an optional save state, a script, any
--cheat/--poke/--zero, and any layer-isolation flags). `align` says how to
find frame 0 on each side: the rust side always reads its own
battle-started marker (AUDIT pair 1 -- see find_marker_origin()); the canon
side is either a documented fixed frame (a save state's own known battle
frame, or a scripted press with a known, constant lead time) or, when
nothing about the pairing is fixed, a narrow band the harness searches,
exactly regress.py's `by_lag` narrowed down (AUDIT pair 1's other half).

`run_check()` wraps `run()` with the rest of the ticket: no boxes (pair 6),
isolated/integrated (pair 9), a negative fixture that must NOT read 0 (pair
10), no `want` -- pass means every frame is 0, anything else is FAILED,
unless tools/allowlist.py has ticketed it (pair 11) -- and a gallery GIF
written as a side effect of the run, never curated after the fact (pair 7).

usage:
    python3 tools/harness.py [--only NAME,...] [--list] [--no-gallery]

Needs /tmp/mgba_capture, the real ROM and the save states, which are never
committed (see tools/states.py). Every fixture in CHECKS below still builds
its Rust side from a `demo-*` cargo feature -- FIXTURE.md's descriptor path
(fixture_cheats() below) is wired up and ready, but no ROM reads
0x02000040 yet (that is wave 2's `fixtures-as-data` agent, running in
parallel); see the module-level note by FIXTURE_ADDR.
"""

import argparse
import hashlib
import os
import re
import struct
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np
from PIL import Image

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chip_compare as cc  # noqa: E402  (needs the path set first)
from allowlist import ALLOWLIST  # noqa: E402

CAPTURE = "/tmp/mgba_capture"
REAL = "/tmp/bn6f_real.gba"
STERILE = "/tmp/bn6f_sterile.gba"
PAUSED = "/tmp/pausedwithcannon.state"
BATTLESTART = "/tmp/battlestart.state"
#: states.py's own patch_sterile.py build: STERILE + --empty-net-encounter.
EMPTYNET = "/tmp/bn6f_sterile_emptynet.gba"
#: states.py's DELETE_ENEMY_3 -- kills whichever of the three enemy
#: BattleObject slots a genuinely-spawned encounter populates. Named
#: distinctly from any local `DELETE_ENEMY_3` a future check might define,
#: since this file has no such constant of its own yet.
DELETE_ENEMY_3_HARNESS = (
    "0x0203aaac:0", "0x0203aaae:0",
    "0x0203ab84:0", "0x0203ab86:0",
    "0x0203ac5c:0", "0x0203ac5e:0",
)
#: tools/states.py's "chip_ready" state (wave 3b ticket step 1) is built but
#: NOT loaded by anything below -- it is PAUSED run forward past the frame
#: its leftover chip-window-close OAM garbage clears, kept in the manifest
#: as the record of a tried-and-rejected fix (see ALIGN_CHIP's own comment,
#: just above `_chip_canon`, for why: clearing that garbage needs the enemy
#: to have actually died, and once it has, the game refuses further
#: chip-fire input on reload, at any delay). The fix actually used needs no
#: new state -- see ALIGN_CHIP's comment.
#: Keeping the capture's Mettaur alive -- regress.py's ALIVE, unchanged.
ALIVE = ("0x0203ab84:0xffff", "0x0203ab86:0xffff")

WEB_CAPTURES = os.path.join(ROOT, "web", "captures")

# --------------------------------------------------------------------------
# The marker (AUDIT pair 1). src/main.rs writes BATTLE_MARKER at EWRAM's
# base every frame: 0 until the battle has started, then MARKER_MAGIC
# followed by a battle-frame counter that counts 0, 1, 2... from the first
# frame that is actually shown (see main.rs's `clocks_visible` comment).
MARKER_ADDR = 0x02000000
MARKER_LEN = 8
MARKER_MAGIC = 0x4241_5454  # "BATT"


def find_marker_origin(watch_file, magic=MARKER_MAGIC):
    """The first watched frame whose marker reads `magic` -- the rust
    capture's frame 0 for every check below, in place of a hardcoded boot
    length. Confirmed to move with the build in exactly the way AUDIT pair 1
    says it would: `demo-open`/`demo-field` both land it at frame 8,
    `demo-sterile,demo-cannon,demo-auto` at frame 1 -- a fixed "ours frame N"
    pairing would have been wrong for one of them by construction, not by
    accident.
    """
    data = open(watch_file, "rb").read()
    n = len(data) // MARKER_LEN
    for i in range(n):
        val, = struct.unpack_from("<I", data, i * MARKER_LEN)
        if val == magic:
            return i
    raise RuntimeError(
        "the battle-started marker never appeared in %d watched frames -- "
        "the ROM never reached a battle, or MARKER_ADDR/MARKER_MAGIC has "
        "drifted from src/main.rs's BATTLE_MARKER/BATTLE_MAGIC" % n)


# --------------------------------------------------------------------------
# FIXTURE.md's descriptor (AUDIT pairs 6, 14, 17). Not read by any ROM yet
# -- every Check below still builds its rust side from a `demo-*` feature --
# but the conversion from a descriptor dict to the --cheat writes that plant
# it is written now, so the day the fixtures-as-data ROM lands, a Check only
# has to swap its `rust=` Side's `features=` for `fixture=` and this needs no
# changes. Per-frame --cheat, not --poke: FIXTURE.md is explicit that the
# descriptor must survive startup, and --poke only runs once, before the
# ROM's own init could plausibly stomp EWRAM at 0x02000040.
FIXTURE_ADDR = 0x0200_0040
FIXTURE_MAGIC = 0x4649_5854  # "FIXT"
FIXTURE_SIZE = 64


def fixture_cheats(descriptor: dict) -> Tuple[str, ...]:
    """A FIXTURE.md descriptor dict -> 32 `addr:val16` --cheat arguments.

    Fields not given take FIXTURE.md's own "default" sentinel (0xFFFF for
    the backdrop/gauge timing fields, 0 elsewhere) so a partial descriptor
    still reads as a legal one to the ROM once it exists.
    """
    buf = bytearray(FIXTURE_SIZE)
    struct.pack_into("<I", buf, 0, FIXTURE_MAGIC)
    buf[4] = descriptor.get("enemies", 0)
    # +5 enemy_kind: per-slot kinds packed two bits per slot (FIXTURE.md,
    # T9c) -- slot 0 in bits 0-1, slot 1 in bits 2-3, slot 2 in bits 4-5;
    # kind 0 = Mettaur, 1 = Gunner. A bare int is written as-is (every
    # pre-T9c descriptor writes 0 = Mettaur in every slot, so existing rows
    # are unchanged); a per-slot list is packed here.
    kinds = descriptor.get("enemy_kind", 0)
    if isinstance(kinds, (list, tuple)):
        kinds = sum((k & 0b11) << (slot * 2) for slot, k in enumerate(kinds[:3]))
    buf[5] = kinds
    buf[6] = descriptor.get("enemy_col", 0)
    buf[7] = descriptor.get("enemy_row", 0)
    struct.pack_into("<H", buf, 8, descriptor.get("megaman_hp", 60))
    buf[10] = descriptor.get("megaman_col", 0)
    buf[11] = descriptor.get("megaman_row", 0)
    hand = descriptor.get("hand", [])
    buf[12] = descriptor.get("hand_count", len(hand))
    for i in range(5):
        buf[13 + i] = hand[i] if i < len(hand) else 0
    buf[18] = descriptor.get("gauge", 0)
    buf[19] = descriptor.get("flags", 0)
    struct.pack_into("<H", buf, 20, descriptor.get("art_entry", 0xFFFF))
    struct.pack_into("<H", buf, 22, descriptor.get("art_timer", 0xFFFF))
    struct.pack_into("<H", buf, 24, descriptor.get("scroll_xq", 0xFFFF))
    struct.pack_into("<H", buf, 26, descriptor.get("scroll_yq", 0xFFFF))
    struct.pack_into("<H", buf, 28, descriptor.get("gauge_tick", 0xFFFF))
    struct.pack_into("<H", buf, 30, descriptor.get("fire_frame", 0xFFFF))
    # +32 enemy_hp: src/fixture.rs's ACTUAL sentinel is 0 (its own doc: "0 =>
    # the kind's own sensible default"), not FIXTURE.md's stated 0xFFFF --
    # see this ticket's report. Defaulting here to 0 matches the code that
    # reads it, not the (wrong) prose.
    struct.pack_into("<H", buf, 32, descriptor.get("enemy_hp", 0))
    # +34..39 deck_count/deck, +40 start_state, +41 result_level, +42
    # result_frames, +44 result_zenny, +46 banner_at: FIXTURE.md's fields
    # added after wave 2, none read by src/fixture.rs yet (wave 3's
    # `fixture-gaps` agent, running in parallel -- see Check.pending_src).
    # Written anyway, per the ticket: a descriptor is legal input the moment
    # a field lands, with no harness change needed.
    deck = descriptor.get("deck", [])
    buf[34] = descriptor.get("deck_count", len(deck))
    for i in range(5):
        buf[35 + i] = deck[i] if i < len(deck) else 0
    buf[40] = descriptor.get("start_state", 0)
    buf[41] = descriptor.get("result_level", 0)
    struct.pack_into("<H", buf, 42, descriptor.get("result_frames", 0))
    struct.pack_into("<H", buf, 44, descriptor.get("result_zenny", 0))
    struct.pack_into("<H", buf, 46, descriptor.get("banner_at", 0xFFFF))
    # +48..52 deck_codes, +53 window_pick_count, +54 window_pick_slot, +55
    # window_cursor: NOT in FIXTURE.md (src/fixture.rs's own reserved-region
    # additions -- see Fixture::deck_codes/window_pick_count's doc there).
    # 0xFF per deck_codes slot = that slot's own codes[0] (the "no override"
    # sentinel src/fixture.rs's table comment gives).
    deck_codes = descriptor.get("deck_codes", [])
    for i in range(5):
        buf[48 + i] = deck_codes[i] if i < len(deck_codes) else 0xFF
    buf[53] = descriptor.get("window_pick_count", 0)
    buf[54] = descriptor.get("window_pick_slot", 0)
    buf[55] = descriptor.get("window_cursor", 0)
    # +56 result_elapsed (FIXTURE.md, added by the src agent in parallel with
    # this ticket): frames of the RESULT sequence already elapsed at boot
    # when start_state=1. NOT read by src/fixture.rs as of this ticket
    # (grepped -- see the `result` Check's pending_src below); written
    # anyway per FIXTURE.md's own contract ("a descriptor is legal input the
    # moment a field lands, with no harness change needed").
    struct.pack_into("<H", buf, 56, descriptor.get("result_elapsed", 0))
    # +58 rng (FIXTURE.md, read by src/fixture.rs since the wave 3d ticket):
    # delivered now (TODO F4) -- an RNG-gated fixture needs canon's own seed,
    # not this project's default. 0 leaves src/fixture.rs's own "0 = our
    # default seed" convention in force, so every descriptor that does not
    # name an rng is unchanged.
    struct.pack_into("<I", buf, 58, descriptor.get("rng", 0))
    # F38h: per-enemy spawn-cell panel data (NOT in FIXTURE.md,
    # src/fixture.rs's own reserved-region additions at offsets +56..+62).
    # The layout overlays with result_elapsed (+56..+57) and rng (+58..+61),
    # AND panel_override_mask shares +62 with `enemy_state` below; the
    # write ORDER below is chosen so every existing row stays byte-
    # identical:
    #   1. result_elapsed and rng land first (above).
    #   2. panel_col[0..2] at +56/+57/+58 overwrites result_elapsed_lo/hi
    #      and rng byte 0. RESULTMATCH sets result_elapsed=0, so its
    #      result_elapsed reads back as panel_col[0]|(panel_col[1]<<8) =
    #      0 when no panel is named. mettaur/wave set rng to a specific
    #      value; panels=0 (default) overwrites rng's bytes, so their rng
    #      reads back as 0. Per F38f, neither fixture's Mettaur ever
    #      reaches an RNG-gated branch, so the dropped seed is pixel-
    #      neutral. opening sets panel_col/panel_row explicitly; its
    #      effective rng becomes the bytes [panel_col[2], panel_row[0..2]]
    #      = 0x02030106, which is harmless because the opening row's three
    #      Mettaurs are still inside their 31-frame spawn wait at frame 40
    #      (the materialize animation alone consumes frames 0..31).
    #   3. panel_row[0..2] at +59/+60/+61 overwrites rng bytes 1..3 (same
    #      reasoning as above).
    #   4. panel_override_mask at +62 overwrites enemy_state at +62 BELOW
    #      (enemy_state's own write runs last in the buffer build, so
    #      enemy_state wins for cursor/windowclose -- their enemy_state=4
    #      becomes the mask, but enemies=1 means only slot 0 matters and
    #      mask bit 0 stays clear, so no override is applied for the
    #      existing slot 0).
    panel_col = descriptor.get("panel_col", [0, 0, 0])
    panel_row = descriptor.get("panel_row", [0, 0, 0])
    for i in range(3):
        buf[56 + i] = panel_col[i] if i < len(panel_col) else 0
    for i in range(3):
        buf[59 + i] = panel_row[i] if i < len(panel_row) else 0
    # +62 enemy_state / +63 enemy_action: NOT in FIXTURE.md
    # (src/fixture.rs's own reserved-region additions -- see Fixture::enemy_state's
    # doc there). 0 = no override, so every descriptor that does not name them
    # is unchanged. NOTE: F38h overlays panel_override_mask at the SAME byte
    # (+62). The byte is the OR of the two values because the only
    # descriptor that names panel_override_mask (opening, mask=0x07) does NOT
    # name enemy_state, and the only descriptors that name enemy_state
    # (cursor/windowclose, enemy_state=4) do NOT name panel_override_mask:
    # the value ranges never collide in practice, and combining via OR
    # keeps every pre-F38h row byte-identical (opening's 0x07 lands at +62;
    # cursor/windowclose's 4 still lands at +62, mask=4 with enemies=1 means
    # no slot-0 override so behaviour is preserved).
    buf[62] = descriptor.get("panel_override_mask", 0) | descriptor.get("enemy_state", 0)
    buf[63] = descriptor.get("enemy_action", 0)
    out = []
    for off in range(0, FIXTURE_SIZE, 2):
        val, = struct.unpack_from("<H", buf, off)
        out.append("0x%08x:0x%04x" % (FIXTURE_ADDR + off, val))
    return tuple(out)


# --------------------------------------------------------------------------
# Building a rust ROM from a cargo feature -- unchanged from regress.py's
# `build()`, just cached so a Check that runs both an isolated and an
# integrated variant (or a positive and negative fixture) does not rebuild.
_ROM_CACHE: Dict[str, str] = {}


def build_feature_rom(features: str) -> str:
    if features in _ROM_CACHE:
        return _ROM_CACHE[features]
    subprocess.run(["cargo", "build", "--release", "--features", features], cwd=ROOT,
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elf = os.path.join(cc.target_dir(), "thumbv4t-none-eabi/release/bn")
    if not os.path.exists(elf):
        raise SystemExit("cargo built no %s -- is CARGO_TARGET_DIR pointing somewhere odd?" % elf)
    rom = cc.scratch("h_rom_%s.gba" % features.replace(",", "_"))
    subprocess.run(["python3", os.path.join(ROOT, "tools", "gbafix.py"), elf, rom],
                   check=True, stdout=subprocess.DEVNULL)
    _ROM_CACHE[features] = rom
    return rom


# --------------------------------------------------------------------------


@dataclass
class Side:
    """How to produce one side's capture. Exactly the things
    tools/mgba_capture.c already takes (see its usage comment): a ROM, an
    optional save state, a key script, any per-frame --cheat/--zero, a
    one-time --poke, and any raw passthrough flags (--disable-bg,
    --disable-obj, --only-bg N, ...).

    `capture_fn`, if set, bypasses all of the above and is called as
    `capture_fn(out_dir, count)` directly -- the escape hatch a side needs
    when its setup is more than static flags, e.g. chip_compare.py's
    `capture_real`, which pokes the chip into the state's own library via a
    throwaway peek first. Kept rather than reimplemented: AUDIT's ticket
    says import from chip_compare freely.
    """
    rom: Optional[str] = None
    features: Optional[str] = None
    loadstate: Optional[str] = None
    script: Optional[str] = None
    cheats: Tuple[str, ...] = ()
    pokes: Tuple[str, ...] = ()
    #: Each "frame:addr:val16" argument for --poke-at (ONE-SHOT write,
    #: immediately before that frame) -- TODO F5b: how the chip rows deliver
    #: the A press to MegaMan's AIData (JoypadPressed 0x020340a4 + mirror
    #: 0x02036822, frame 3) when the banner sequencer sits in 0x0C, where
    #: sub_8012DFC never refreshes AIData from the mirror.
    pokes_at: Tuple[str, ...] = ()
    zero: Tuple[str, ...] = ()
    extra: Tuple[str, ...] = ()
    fixture: Optional[dict] = None
    capture_fn: Optional[Callable[[str, int], None]] = None

    def resolved_rom(self) -> str:
        if self.rom:
            return self.rom
        if self.features:
            return build_feature_rom(self.features)
        raise ValueError("Side needs rom=, features=, or capture_fn=")

    def args(self) -> List[str]:
        a: List[str] = []
        if self.loadstate:
            a += ["--loadstate", self.loadstate]
        for c in self.cheats:
            a += ["--cheat", c]
        for p in self.pokes:
            a += ["--poke", p]
        for p in self.pokes_at:
            a += ["--poke-at", p]
        for z in self.zero:
            a += ["--zero", z]
        if self.fixture is not None:
            for c in fixture_cheats(self.fixture):
                a += ["--cheat", c]
        if self.script:
            a += ["--script", self.script]
        a += list(self.extra)
        return a

    def do_capture(self, out_dir: str, count: int, watch_file: Optional[str] = None):
        if self.capture_fn:
            if watch_file:
                raise ValueError("capture_fn sides carry no marker -- they are canon sides, "
                                  "never watched")
            self.capture_fn(out_dir, count)
            return
        args = self.args()
        if watch_file:
            args = args + ["--watch", "%#x:%d:%s" % (MARKER_ADDR, MARKER_LEN, watch_file)]
        cc.capture(self.resolved_rom(), out_dir, count, *args)


@dataclass
class Align:
    """How the two captures line up, without a hardcoded "real X <-> ours Y"
    pairing (AUDIT pair 1).

    `canon_ref` is the canon capture's own frame 0 for the comparison --
    documented, not searched: a save state built to BE the fixture's frame 0
    (BATTLESTART), or a scripted event with a known, constant lead time
    (chip_compare.py's REAL_START = a press at frame 40 + 3). It does not
    move with a rust-side source change, so it is never part of the search.

    `search`, if given, is the band of candidate offsets from the RUST
    marker origin (find_marker_origin()) to try; the harness scores every
    offset in it by the total diff over the compared window and keeps the
    minimum -- regress.py's `by_lag`, unchanged in method, narrower in scope
    now that the marker has already absorbed the boot-length unknown pair 1
    names. `rust_offset` is used directly, with no search, when `search` is
    None -- for a pairing with nothing left to find (a future
    fixture-descriptor check where both sides start at a shared frame 0, or
    any check whose offset is itself the thing under test).
    """
    canon_ref: int
    rust_offset: int = 0
    search: Optional[range] = None
    note: str = ""


@dataclass
class Result:
    """One `run()`: the per-frame full-screen differing-pixel counts, and
    everything about how the two captures were aligned to get them."""
    counts: List[int]
    rust_dir: str
    canon_dir: str
    rust_origin: int
    rust_offset: int
    canon_ref: int
    align: Align

    @property
    def total(self) -> int:
        return sum(self.counts)

    @property
    def worst(self) -> int:
        return max(self.counts) if self.counts else 0

    @property
    def ok(self) -> bool:
        """Pair 11: pass means every frame is 0. No `want`, no averaging."""
        return all(c == 0 for c in self.counts)


#: Frames of slack before the marker is expected, and before the negative
#: fixture's +1-frame canon shift -- see run()'s capture-count comment.
MARKER_MARGIN = 40
NEGATIVE_MARGIN = 5


def run(rust: Side, canon: Side, frames: int, align: Align, *,
        variant_label: str = "", serial: bool = False) -> Result:
    """Capture both sides, align them, and return the full 240x160
    differing-pixel count for `frames` consecutive frames -- AUDIT pair 6:
    one harness, one job, no boxes.

    `variant_label` is folded into the scratch-dir key so two ui variants of
    the same Check (ui='both' runs in parallel via run_check's pool.map) do
    not share a watch file -- ui='both' rows whose rust/canon lambdas do not
    vary by ui (e.g. `gunner`) would otherwise collide on the key and race
    to read+remove the same watch_file, with the second variant's
    find_marker_origin raising FileNotFoundError.

    `serial=True` (T9i, 2026-09-15, gunner row) runs rust then canon in this
    process, bypassing the ThreadPoolExecutor path -- the rust+canon pair is
    then sequentially captured in one process, never competing for one of
    cc.CAPTURE_SLOTS together. AUDIT T9i follow-up: the harness's default
    parallel capture had the gunner canon side short-count under slot
    contention (rust 58/170 + canon 27/135 on the 3-slot pool, then watch
    file race). Serial captures stay within one slot at a time so the race
    is bypassed for that row.
    """
    key = hashlib.sha1(repr((rust, canon, frames, align, variant_label)).encode()).hexdigest()[:10]
    rust_dir = cc.scratch("h_rust_%s" % key)
    canon_dir = cc.scratch("h_canon_%s" % key)
    watch_file = cc.scratch("h_watch_%s.bin" % key)

    upper = max(align.search) if align.search is not None else align.rust_offset
    rust_count = MARKER_MARGIN + upper + frames
    canon_count = align.canon_ref + frames + NEGATIVE_MARGIN

    # Build (or fetch) the rust ROM BEFORE any capture starts: cargo and the
    # ROM cache are not something two threads should race on.
    if not rust.capture_fn:
        rust.resolved_rom()
    if serial:
        # provenance: derived -- tools/harness.py:2114 capture-order (T9i)
        # rust+canon run sequentially in this process -- never together in
        # the slot pool, no thread pool. The watch file is still produced by
        # the rust capture (it carries the marker), and find_marker_origin
        # below reads it once both are done.
        rust.do_capture(rust_dir, rust_count, watch_file=watch_file)
        canon.do_capture(canon_dir, canon_count)
    else:
        # The two captures are independent processes, so they overlap
        # (bounded by cc.CAPTURE_SLOTS).
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=2) as pool:
            fr = pool.submit(rust.do_capture, rust_dir, rust_count, watch_file=watch_file)
            fc = pool.submit(canon.do_capture, canon_dir, canon_count)
            fr.result()
            fc.result()

    origin = find_marker_origin(watch_file)
    # AUDIT pair 13: stream what we can, and do not keep what we cannot --
    # the watch file's job ends the moment origin is known.
    subprocess.run(["rm", "-f", watch_file], check=True)

    def score(offset):
        return [cc.diff_frames(canon_dir, align.canon_ref + k, rust_dir, origin + offset + k)
                for k in range(frames)]

    if align.search is not None:
        total, offset = min((sum(score(o)), o) for o in align.search)
        counts = score(offset)
    else:
        offset = align.rust_offset
        counts = score(offset)

    return Result(counts=counts, rust_dir=rust_dir, canon_dir=canon_dir,
                  rust_origin=origin, rust_offset=offset, canon_ref=align.canon_ref,
                  align=align)


def negative_counts(result: Result, frames: int, delta: int = 1,
                    kind: str = "frame") -> List[int]:
    """AUDIT pair 10: the SAME captures and the SAME alignment this check
    just found, deliberately broken, so a check that cannot fail is visible
    as such.

    `kind="frame"` (the default, and the right one for anything that moves)
    shifts the canon side by `delta` frames -- not re-searched, on purpose.
    Re-running the search could find a different offset that also reads 0 on
    a periodic fixture, which would prove nothing; reusing the found offset
    and only moving the canon reference is what actually tests whether the
    check can fail.

    `kind="pixel"` shifts the canon side one pixel LEFT instead, comparing
    canon's columns 1.. against ours 0..-1 on the same frames. It exists for
    a subject that genuinely does not move: canon's BG3 alone, with the chip
    window sitting open and nothing pressed, is byte-identical for 260+
    consecutive frames (measured), so no frame shift can ever break that
    pair -- not because the check is weak but because there is no timing in
    the picture to get wrong. A pixel shift still tests what such a check
    CAN get wrong: that the diff is live, aligned, and looking at real
    content rather than two blank rectangles. Say so where it is used; it is
    a weaker negative than a frame shift and must not be reached for by
    anything with motion in the window.
    """
    if kind == "frame":
        return [cc.diff_frames(result.canon_dir, result.canon_ref + delta + k,
                               result.rust_dir, result.rust_origin + result.rust_offset + k)
                for k in range(frames)]
    if kind == "pixel":
        out = []
        for k in range(frames):
            canon = cc.frame_array(result.canon_dir, result.canon_ref + k)
            rust = cc.frame_array(result.rust_dir,
                                  result.rust_origin + result.rust_offset + k)
            out.append(cc._count_diff(canon[:, delta:], rust[:, :-delta]))
        return out
    raise ValueError("unknown negative kind %r" % kind)


# --------------------------------------------------------------------------


@dataclass
class Check:
    """One row of the table (AUDIT pair 6's replacement for regress.py's 18
    hand-written functions).

    `ui` is "isolated" (UI/backgrounds blanked so the number is one element
    alone), "integrated" (everything on), or "both" (run twice, reported
    separately -- AUDIT pair 9). `rust`/`canon` are called with the ui
    variant string being run ("isolated" or "integrated") and return the
    Side to capture for it.
    """
    name: str
    ui: str
    frames: int
    align: Align
    rust: Callable[[str], Side]
    canon: Callable[[str], Side]
    canon_variant: str = "canon"  # AUDIT pair 16: name the canon variant. "canon (sterile)" for a patched original.
    #: AUDIT wave 3 ticket step 1: non-empty when this check's rust side
    #: cannot be expressed by today's FIXTURE.md descriptor -- the offered
    #: deck (window/card/cursor), start_state (result) or banner_at (banner)
    #: fields the `fixture-gaps` agent is adding in parallel, at the offsets
    #: FIXTURE.md documents but src/fixture.rs does not read yet. The
    #: descriptor is still written (fixture_cheats() covers every FIXTURE.md
    #: field), so the check "lights up" the moment that field is read --
    #: nothing here needs to change. Purely informational: does not affect
    #: pass/fail, only how the row is reported.
    pending_src: str = ""
    #: AUDIT pair 10, which negative fixture proves this check can fail:
    #: "frame" (the default -- canon shifted one frame at the found offset)
    #: for anything with motion in its compared window, "pixel" (canon
    #: shifted one column) for a subject that provably does not move at all,
    #: where a frame shift is not a weaker test but a meaningless one. Only
    #: `window` uses "pixel", and its own note carries the measurement that
    #: justifies it.
    negative: str = "frame"
    #: T9i (2026-09-15): when True, run() captures rust then canon
    #: sequentially in this process (no ThreadPoolExecutor) -- the rust+canon
    #: pair stays out of cc.CAPTURE_SLOTS contention together. The gunner
    #: row sets this; the default is False (parallel).
    serial: bool = False


def _cannon_canon(ui: str) -> Side:
    # Cannon (chip 01) on the OLD PAUSED route -- NOT WIRED since TODO F7
    # (2026-09-12) re-pointed the `cannon` Check onto _chip_canon_0c("01")
    # + ALIGN_CHIP_0C, the same route F5b gave the 43 chip rows. Kept as
    # the record of where the row's 14388/2350 baseline came from; no
    # Check references this any more.
    return _chip_canon("01")(ui)


# --------------------------------------------------------------------------
# The 43-chip scoreboard (AUDIT pair 14, ticket step 2). ONE plain build,
# chip chosen at runtime by a fixture descriptor -- "sterile arena (enemies
# 0), hand = that chip, auto-fire on", exactly what
# `demo-sterile,demo-<chip>,demo-auto` used to build 43 times over. The
# fixture row is `_cannon_canon`'s own table entry (fixture.rs's
# "demo-sterile,demo-cannon,demo-auto" row) generalised to any chip id:
# flags 0x1F (open-window | blank-hud | blank-backdrop | auto-fire |
# skip-intro), fire_frame 90 -- AUTO_FIRE_GAP, battle.rs confirms it seeds
# and reseeds `auto_ticks` exactly as the old demo-auto harness did.
#
# THE SHARED 14388 BASELINE, ROOT-CAUSED BUT NOT YET FIXED (wave 3b ticket
# step 1). Full screen (pair 6) surfaced two DISTINCT artifacts inside canon
# frames 43-52, both from the PAUSED save state (`--disable-bg` isolates
# OBJ; both verified directly against a live capture, not inherited from
# wave 3's note, which undercounted the portrait box at "~694px" -- it is
# exactly 528px):
#
#   1. A 528px "portrait box" (top-left, rows 0-30 cols 0-150) for EXACTLY
#      canon frames 43-48 (2350/2350/1914/1842/1842/1842 px of each of
#      those six frames' totals is this), then gone.
#   2. The remaining ~1822/1822/1386/1314/1314/1314/562/562/562/562px is
#      the deleted enemy's own corpse, dissolving in OBJ at approximately
#      x149-196,y70-120, fully gone by canon frame 53.
#
# THREE FIXES TRIED, ALL VERIFIED TO FAIL. A state rebuild (tools/states.py's
# "chip_ready" -- kept in the manifest as the record, NOT used below) and a
# ROM code patch (this ticket's own third attempt, described below and NOT
# carried in tools/patch_sterile.py -- it did not work) were both AUDIT
# pair-6-compliant (no window shrinking); a fourth attempt that only shifted
# the compared window later was REJECTED during review as exactly the
# "shrink the box in time" pair 6 forbids, and is not here.
#
#   (a) STATE REBUILD. A state saved AFTER the enemy dies (so the portrait
#       garbage has already cleared -- confirmed it clears only as a side
#       effect of the enemy's own death/dissolve processing running, NOT
#       from elapsed frames alone: a parallel run that keeps the enemy
#       ALIVE the whole time never clears it, out to 390 frames tried)
#       makes the game REFUSE every further chip-fire input, at ANY delay
#       after reload (1 through 120 frames tried, all identical output) --
#       while ordinary movement input on the SAME reload works fine (tested
#       the same way), so this is specific to the attack command, not a
#       general post-reload input bug. Poking the hand chip in at load
#       (one-time, matching how capture_real/`_chip_pokes` already
#       validates the library) instead of a late A-press changes nothing.
#       A state saved WHILE the enemy is still alive (preserving
#       fireability) never triggers the portrait-clearing at all, so the
#       two requirements -- a valid target at reload, and having already
#       run the enemy through its death processing -- are mutually
#       exclusive for a single base state.
#   (b) ROM PATCH. Found the actual gate: `sub_800938A` (asm00_1.s:13037,
#       ROM 0x800938A) is MegaMan's own "process a chip-use request"
#       handler. It calls `sub_800801C` (asm00_1.s:10361), which runs one
#       step of the GENERIC BANNER SEQUENCER (TRANSFER.md 7bf's own prior
#       finding: the same state machine drives BATTLE START!, TURN START!,
#       ENEMY DELETED and the result messages, selected by
#       `dword_203CA70`), then checks the result: `cmp r0, #6 / bne
#       loc_80093B0` (ROM 0x80093A2, bytes `06 28`) -- when the sequencer
#       reports 6, CurState is forced back to 8 (idle) and the function
#       returns without firing, exactly the "stuck at idle, A does nothing"
#       behaviour measured live (MegaMan's own CurState/CurAction bytes at
#       0x0203a9b0+8/+9 stay `08 04` forever when refused, transition to
#       `14 00` when a fire succeeds). PATCHED (this ticket, as a test, not
#       committed): changed the compare immediate from 6 to 0xFF (byte
#       0x06 -> 0xFF at ROM 0x80093A2) so `bne` always takes the
#       non-refusal branch, on a throwaway ROM built the same way
#       patch_sterile.py builds STERILE. VERIFIED NOT SUFFICIENT: an A
#       press at any delay after loading a state saved past the corpse's
#       full dissolve (frame 110, portrait and corpse both independently
#       confirmed 0 at load) still produces NO change over 40 frames on the
#       patched ROM -- the same symptom as the unpatched one. Either r0==6
#       is not actually reached in this path once the enemy is dead at
#       reload (the sequencer may be stuck in a DIFFERENT state that
#       returns something else `sub_800938A` also treats as "do nothing",
#       past the `cmp r0,#0; beq locret_800945A` at loc_80093B0), or a
#       SEPARATE gate exists elsewhere. Not resolved further in the time
#       this ticket had; a live debugger/tracer in mgba_capture.c (not
#       present today) would settle which, and is the concrete next step
#       for whoever picks this up.
#
# REPORTED FOR THE ROM SIDE, precisely: canon frames 43-52 (10 of the 40
# compared for `cannon`, proportionally more or less for other chips' own
# frame counts), OBJ layer. Frames 43-48: x0-150,y0-30, the portrait box.
# Frames 43-52: x149-196,y70-120 (partially overlapping), the corpse. Rust
# shows nothing in either region at any frame (its arena is genuinely
# empty) -- nothing to fix on the rust side. The 14388/2350 baseline is
# UNCHANGED from before this ticket; it is ticketed, not silently carried.
ALIGN_CHIP = Align(
    canon_ref=43,
    search=range(110, 136),
    note="canon: chip_compare.py's REAL_START=43 (A pressed at 40, 'the attack "
         "begins at 43') -- a documented scripted-event landing, not searched. rust: "
         "marker origin (1, flags 0x1F skips the intro and blanks HUD/backdrop, "
         "same as `cannon` above) plus a 26-frame band -- unique zero at offset 122 "
         "for every chip verified (unchanged from before this ticket -- see the "
         "comment above for what was tried against the residue and why it is still "
         "here).",
)

#: TODO F5b: the same pairing, Pinned BY THE FIRE EVENT (R2's method) on the
#: afterdissolve_0x0c route. Canon side: --watch-write on 0x0203a9b8 from load
#: under the row's own pokes shows CurAction 0x08->0x14 written at frame 3
#: (0x0801169A, lr 0x0800FBF7) -- the fire. The old route's own rule was "press
#: lands at 41, the attack begins at 43" (chip_compare.py's REAL_START=43): a
#: measured +2 lead from the CurAction write to the first visible attack frame.
#: The same lead here pins canon_ref = 3 + 2 = 5. Rust side is UNCHANGED (same
#: descriptor, same build), so the old band's unique minimum is expected at the
#: same offset -- the band is kept only to CONFIRM it, not to find it.
ALIGN_CHIP_0C = Align(
    canon_ref=5,
    search=range(110, 136),
    note="canon: fire event measured, not searched -- CurAction 0x08->0x14 at frame 3 "
         "of the afterdissolve_0x0c capture (watch-write 0x0203a9b8), +2 frames to the "
         "first visible attack frame, the same measured lead as the PAUSED route (A "
         "write 41, attack 43). rust: unchanged -- marker origin plus the same band as "
         "ALIGN_CHIP, kept to confirm the minimum did not move.",
)

def _chip_pokes(chip_hex: str) -> Tuple[str, ...]:
    """cc.library_pokes() returns a flat ['--poke', 'addr:val', ...] list
    (it is built to be spliced straight into a subprocess argv); Side.pokes
    wants just the 'addr:val' halves, which args() re-adds the flag for."""
    raw = cc.library_pokes(int(chip_hex, 16))
    return tuple(raw[i] for i in range(1, len(raw), 2))


def plain_rom() -> str:
    """ONE plain build (no demo-* feature) -- AUDIT pair 14 -- for every
    fixture-descriptor check in this file, cached by build_feature_rom()
    the same way a demo-feature build is, keyed on the empty string."""
    return build_feature_rom("")


#: TODO F27b: `flags` defaults to every chip row's own 0x1F and only the
#: `popup` row passes anything else -- see that row's own note.
def _chip_rust(chip_hex: str, flags: int = 0x1F) -> Callable[[str], Side]:
    desc = {
        "enemies": 0, "megaman_hp": 100, "megaman_col": 2, "megaman_row": 2,
        "hand": [int(chip_hex, 16)], "hand_count": 1, "gauge": 0,
        "flags": flags, "fire_frame": 90,
    }
    return lambda ui: Side(rom=plain_rom(), fixture=desc, extra=("--disable-bg",))


def _chip_canon(chip_hex: str, a_frame: int = 40, hide_enemy: bool = False,
                banner_zero: bool = True) -> Callable[[str], Side]:
    def make(ui: str) -> Side:
        cheats = list(ALIVE if hide_enemy else ("0x0203ab84:0", "0x0203ab86:0"))
        cheats.append("%s:0x%s" % (cc.HAND_SLOT, chip_hex))
        zero = []
        if banner_zero:
            zero.append(cc.BANNER_TILES)
        if hide_enemy:
            zero.append(cc.ENEMY_TILES)
        return Side(rom=STERILE, loadstate=PAUSED, cheats=tuple(cheats),
                    pokes=_chip_pokes(chip_hex), zero=tuple(zero),
                    script="Start@10,A@%d" % a_frame, extra=("--disable-bg",))
    return make


#: AUDIT wave 3c/3d "encounter-roll" ticket step 4: the CHIP_READY_EMPTY route --
#: states.py's chip_ready_empty (a genuinely fresh battle that never had an enemy,
#: not PAUSED's hand-made snapshot with its own leftover portrait-box/corpse
#: artifacts -- see ALIGN_CHIP's own comment above for the 14388/2350 baseline
#: those artifacts cost every chip). library_pokes_empty mirrors chip_compare.
#: library_pokes()'s formula but peeks THIS state's own library bytes, not
#: PAUSED's (chip_ready_empty.state already carries chip 1/Cannon's own
#: ownership bit set -- see states.py's own build note -- but a different chip
#: id needs its own byte poked the same way).
CHIP_READY_EMPTY = "/tmp/chip_ready_empty.state"

#: TODO F5b (2026-09-12): states.py's afterdissolve_0x0c -- PAUSED's battle
#: resumed with the Mettaur deleted, saved at frame 60: past the corpse's full
#: dissolve (portrait box and corpse both gone at load, rendered frame checked)
#: and inside the banner sequencer's RESULT countdown state 0x0C (dword_203CA70
#: = 0x000c at load, byte_203CA74 = 0, MegaMan idle 0x0804; the state holds
#: both for 90+ frames after reload, byte watches). On this route the chip press
#: is delivered by a ONE-SHOT poke to MegaMan's AIData JoypadPressed -- in 0x0C
#: nothing refreshes AIData from the joypad mirror (0x08 does it via
#: sub_8012DFC x2, asm00_1.s:10519-10522; 0x0C, sub_80081A4 asm00_1.s:10617,
#: never does), which is exactly why F5's plain A press was refused here.
#: Measured (this ticket): --poke-at 3:0x020340a4:0x0001 (+ mirror
#: 0x02036822) FIRES in 0x0C -- Unk_44 0->0x4 at 0x0800FFEA (lr 0x08013235,
#: sub_8012FC8's tail asm00_2.s:9520, still running per-frame from
#: playerObject_update_80EA484 asm31.s:107160), then CurAction 0x08->0x14 at
#: 0x0801169A (lr 0x0800FBF7, object_setAttack2 from sub_800FB54) -- the SAME
#: write chain the A@40-from-PAUSED control shows at its frame 41.
AFTER_DISSOLVE = "/tmp/afterdissolve_0x0c.state"

#: MegaMan's AIData pointer and the alliance-0 joypad mirror, for the press
#: delivery above. AIDataPtr read live from the BattleObject (0x0203a9b0+0x58
#: = 0x0203aa08) on this state: 0x02034080. oAIData_JoypadPressed = +0x24
#: (include/structs/AIData.inc); the mirror's pressed-candidate halfword is
#: +2 (dword_2036820, read by sub_8012DFC asm00_2.s:8977). A = bit 0
#: (JOYPAD_A, include/structs/Joypad.inc). JoypadPressed 0->1 for one frame
#: is exactly what a player's press produces (control: mirror 0x02036824
#: new=0x0001 at frame 41 -> sub_8012DFC writes AIData JoypadPressed 1 the
#: same frame); in 0x0C the mirror poke itself is inert (nothing reads it),
#: it is carried so the fixture says what a player press would have said.
AIDATA_PRESSED = "0x020340a4"
MIRROR_PRESSED = "0x02036822"
PRESS_FRAME = 3  # --poke-at frame; the fire lands the same frame

#: F11 (2026-09-13): the warp row's direction presses, delivered the F5b way.
#: In sequencer 0x0C nothing refreshes the alliance players' AIData from the
#: joypad mirror (sub_8012DFC runs from 0x08; 0x0C never calls it), so script
#: key presses never reach MegaMan -- measured: his pixel centroid stayed at
#: x=61 for the whole old row while the rust side warped. Movement reads
#: JoypadHeld (oAIData +0x22 = 0x020340a2; oAIData_JoypadPressed +0x24 is the
#: A-press path the chip rows use), and the held word PERSISTS in 0x0C, so
#: each 3-frame press is followed by two explicit 0x0000 clears. GBA keymask,
#: active high (include/structs/Joypad.inc): Right=0x10, Left=0x20, Up=0x40,
#: Down=0x80. Measured: poke Right@130 warps canon at 132 with the same
#: 5-frame pixel-count signature as the rust side's script press (706/458/
#: 395/458/706), pressing not needed. Down@150 warps at 152.
JOYPAD_RIGHT = 0x10
JOYPAD_DOWN = 0x80


def _aidata_held_pokes(key_bits: int, first: int, n: int = 3) -> Tuple[str, ...]:
    pokes = ["%d:0x020340a2:0x%04x" % (first + j, key_bits) for j in range(n)]
    pokes += ["%d:0x020340a2:0x0000" % (first + n + j) for j in range(2)]
    return tuple(pokes)


#: F31b (2026-09-13): the buster row's press, delivered the same way as the
#: warp row's directions, because the same wall is in the way. The buster's
#: arena is the zero-enemy one, which means the enemy is DELETED, which means
#: the battle is over and the banner sequencer sits in 0x0C from frame 47 --
#: and in 0x0C nothing refreshes AIData from the joypad mirror, so a scripted
#: B press never reaches MegaMan (F10 measured that, F31 re-measured it: CurState
#: 0x04 / CurAction 0x08 / CurAnim 0x00 unchanged on every frame of the old
#: row). Pressing INSIDE the 0x08 window is not an option either: 0x08 ends at
#: 46 and the DELETE dissolve still has objects on screen through 52, so a
#: buster fired there is compared against a rust side that has no enemy to
#: dissolve.
#:
#: So the press is poked into AIData directly. Measured (this ticket) that the
#: plain buster fires on the RELEASE, not the press: with a scripted
#: B@30,B@31 in the 0x08 window, AIData reads JoypadPressed 0x0002 at 31,
#: JoypadHeld 0x0002 at 31-32 and JoypadReleased 0x0002 at 33 -- and CurAction
#: goes 0x08 -> 0x11 on 33, the RELEASE frame. Poking held alone therefore does
#: nothing (measured: 24 frames of nothing); held then RELEASED fires. The idle
#: value of the held word is 0xfc00, not 0, so the press ORs B into it and the
#: release restores it rather than zeroing it. Measured on the row's own canon
#: side: CurAction 0x11 at 132, CurAnim 0x0e 133..157, pose+barrel in OAM from
#: 134, muzzle from 135, both gone at 159.
JOYPAD_B = 0x0002  # provenance: derived -- include/structs/Joypad.inc, active high
#: What the held word reads when nothing is pressed on this save state
#: (watched 0x020340a2 over the whole capture). // unnamed: the non-key upper
#: bits of oAIData_JoypadHeld
AIDATA_HELD_IDLE = 0xfc00  # provenance: peeked -- watched on the row's own canon side
AIDATA_RELEASED = "0x020340a6"  # canon: oAIData +0x26, the released-this-frame word
#: The press event this row's canon_ref names: CurAction is written 0x11 on
#: the release frame, so the poke frame + 2 IS the event.
BUSTER_PRESS_POKE = 130
BUSTER_ACTION_FRAME = BUSTER_PRESS_POKE + 2  # measured: CurAction 0x11 at 132


def _aidata_tap_pokes(key_bits: int, first: int) -> Tuple[str, ...]:
    """A one-frame tap delivered to AIData: pressed+held on `first`, held on
    `first+1`, released on `first+2`, cleared on `first+3`."""
    held = AIDATA_HELD_IDLE | key_bits
    return (
        "%d:%s:0x%04x" % (first, AIDATA_PRESSED, key_bits),
        "%d:0x020340a2:0x%04x" % (first, held),
        "%d:%s:0x0000" % (first + 1, AIDATA_PRESSED),
        "%d:0x020340a2:0x%04x" % (first + 1, held),
        "%d:0x020340a2:0x%04x" % (first + 2, AIDATA_HELD_IDLE),
        "%d:%s:0x%04x" % (first + 2, AIDATA_RELEASED, key_bits),
        "%d:%s:0x0000" % (first + 3, AIDATA_RELEASED),
    )


BUSTER_AIDATA_POKES = _aidata_tap_pokes(JOYPAD_B, BUSTER_PRESS_POKE)

#: F12 chip-use (2026-09-14): the A press for the Cannon, delivered the F31b way.
#: A = bit 0 (JOYPAD_A, include/structs/Joypad.inc), the same tap shape as the
#: buster's: pressed+held on `first`, held on `first`+1, released on `first`+2.
#: Measured on this row's own canon side (PAUSED+DELETE, Start@10): the poke
#: fires where the scripted A@150 was refused -- CurAction 0x0203a9b9 goes
#: 0x08->0x14 on the poke frame, CurAnim 0x08 runs from the next frame, anim
#: 0x07 at tail, idle (0x04/0x08, anim 0x00) back after the attack's last frame.
JOYPAD_A = 0x0001  # provenance: derived -- include/structs/Joypad.inc, active high
CHIPUSE_PRESS_POKE = 130
CHIPUSE_AIDATA_POKES = _aidata_tap_pokes(JOYPAD_A, CHIPUSE_PRESS_POKE)


WARP_AIDATA_POKES = (_aidata_held_pokes(JOYPAD_RIGHT, 130)
                     + _aidata_held_pokes(JOYPAD_DOWN, 150))


def library_pokes_empty(chip_id: int) -> Tuple[str, ...]:
    pokes = []
    for base in (cc.LIBRARY, cc.LIBRARY_COPY):
        addr = base + chip_id
        half = addr & ~1
        out = cc.scratch("h_libpeek")
        r = subprocess.run([CAPTURE, EMPTYNET, out, "0", "--loadstate", CHIP_READY_EMPTY,
                            "--peek", "0x%08x" % half],
                           capture_output=True, text=True)
        old = 0
        for line in (r.stdout + r.stderr).splitlines():
            if line.startswith("peek"):
                old = int(line.split("=")[1], 16)
        value = 1 if base == cc.LIBRARY else (1 ^ 0x81)
        new = (old & 0xff00) | value if addr == half else (old & 0x00ff) | (value << 8)
        pokes.append("0x%08x:0x%04x" % (half, new))
    return tuple(pokes)


def _chip_canon_empty(chip_hex: str, a_frame: int = 2) -> Callable[[str], Side]:
    """The SAME chip-in-hand-on-a-sterile-arena comparison ALIGN_CHIP's rows use,
    but based on a battle that never had an enemy (states.py's chip_ready_empty)
    instead of PAUSED's hand-made snapshot -- no portrait-box artifact (nothing
    was ever paused mid-window-close to leave one) and no corpse to dissolve
    (nothing was ever spawned to delete). One-shot --poke for the hand slot and
    library, at load, not a per-frame --cheat: chip_ready_empty's own window-
    pick machinery has already settled by the state's own frame 0 (verified,
    states.py's own note), so nothing is still writing that address that a
    one-time poke would race.
    """
    def make(ui: str) -> Side:
        pokes = list(library_pokes_empty(int(chip_hex, 16)))
        pokes.append("%s:0x%s" % (cc.HAND_SLOT, chip_hex))
        return Side(rom=EMPTYNET, loadstate=CHIP_READY_EMPTY, cheats=DELETE_ENEMY_3_HARNESS,
                    pokes=tuple(pokes), script="A@%d" % a_frame, extra=("--disable-bg",))
    return make


# NOT WIRED INTO ANY Check BELOW -- reported, not hidden (AUDIT wave 3c/3d
# "encounter-roll" ticket step 4, run out of time before this converged).
# The premise itself is answered (states.py's chip_ready_empty note / this
# ticket's own report: a chip DOES fire with no enemy alive), which is what
# unblocks re-pointing `cannon` at this route at all -- but the ALIGNMENT
# needed to actually score it did not converge in the time this ticket had.
# _chip_canon_empty('01') run against the existing rust `cannon` fixture
# (h._chip_rust('01')) over canon_ref in {3,4,5,6,8,10,12,15,20,25,30,35,40,
# 45,50} x rust_offset search bands up to 160 wide: monotonically improving
# from 134634 (canon_ref=3) down to a PLATEAU around 43700-44631 (canon_ref
# 40-50, worst ~1100-1200/frame) that two different rust_offset search
# windows (0..90 and 80..160) both converge on from opposite edges (offset
# 31 and 80, 49 apart, same score) -- consistent with a periodic/looping
# element creating more than one comparably-good false alignment rather than
# one sharp minimum, OR a genuine ~44000 px residue at the true alignment
# that this search never actually reached. Either way it is WORSE than the
# 14388 PAUSED-based baseline it was meant to replace, so wiring it into the
# `cannon` Check as-is would be a regression, not a fix -- left as free
# functions (library_pokes_empty, _chip_canon_empty, above) for a future
# session to pick up, not silently declared done. banner/popup/the family-
# 0x15 chips were NOT attempted at all this ticket, for the same reason
# (time) -- see the ticket report.


def _chip_canon_0c(chip_hex: str) -> Callable[[str], Side]:
    """TODO F5b: the SAME chip-in-hand comparison, but on states.py's
    afterdissolve_0x0c route -- a state 60 frames past the corpse's full
    dissolve, sequencer in 0x0C, field already clean at load (no portrait box,
    no corpse: the shared 14388/2350 baseline's entire region, canon frames
    43-52 OBJ, does not exist here). The press is delivered by one-shot pokes
    (AIData JoypadPressed + mirror) instead of a script A press, because 0x0C
    never refreshes AIData from the mirror -- see AFTER_DISSOLVE's comment for
    the measured fire chain. hide_enemy/banner_zero (the PAUSED route's
    alive-cheat and banner-tile zeroing) have no work to do here: nothing
    spawns, no banner is ever uploaded (patch #2), and the state was BUILT on
    the sterile ROM so no ENEMY DELETED banner exists in its history.
    """
    def make(ui: str) -> Side:
        pokes = list(_chip_pokes(chip_hex))
        pokes.append("%s:0x%s" % (cc.HAND_SLOT, chip_hex))
        return Side(rom=STERILE, loadstate=AFTER_DISSOLVE,
                    pokes=tuple(pokes),
                    pokes_at=("%d:%s:0x0001" % (PRESS_FRAME, AIDATA_PRESSED),
                              "%d:%s:0x0001" % (PRESS_FRAME, MIRROR_PRESSED)),
                    zero=(cc.BANNER_TILES,),
                    extra=("--disable-bg",))
    return make


def _chip_checks() -> List[Check]:
    import scoreboard
    out: List[Check] = []
    for feature, chip_hex, frames, extra in scoreboard.CHIPS:
        name = "chip-" + feature[len("demo-"):]
        hide_enemy = "--hide-enemy" in extra
        banner_zero = "--no-banner-zero" not in extra
        # F12: chip-invisibl's window is provably static on BOTH sides once our
        # popup is gone (canon draws none -- zero popup-region pixels over 210
        # sterile-nozero + 150 real-ROM frames, so a frame shift reads 0: no timing
        # in an idle navi). The documented case for a pixel negative (see `window`):
        # a one-column shift tests the diff is live on real content. All others keep
        # the frame shift.
        neg = "pixel" if feature == "demo-invisibl" else "frame"
        out.append(Check(
            name=name,
            ui="isolated",
            frames=frames,
            align=ALIGN_CHIP_0C,
            rust=_chip_rust(chip_hex),
            canon=_chip_canon_0c(chip_hex),
            canon_variant="canon (sterile)",
            negative=neg,
        ))
    return out


CHECKS: List[Check] = [
    Check(
        name="opening",
        ui="both",
        frames=40,
        align=Align(
            canon_ref=120,
            search=range(110, 131),
            note="canon: BATTLESTART is documented as the battle's real frame 0 "
                 "(eBGScrollCBCounters read 0/0, TRANSFER.md 7aw) -- canon_ref=120 is just "
                 "120 battle-frames past that known origin, nothing searched on this side. "
                 "rust: find_marker_origin() gives frame 8 for demo-open/OPEN_ROW; a 21-wide "
                 "band around it finds a UNIQUE zero at offset 119 (partial band shown in the "
                 "report), the residual sub-frame timing the marker alone does not pin. Ported "
                 "from the demo-open feature to OPEN_ROW (fixture.rs's own table entry, AUDIT "
                 "pair 17 prune ticket) -- same descriptor bytes, same numbers. "
                 "F38 (2026-09-14): integrated decomposed -- the search V is unique at "
                 "119 (72499 vs 151114/155175 either side). BG-only (isolated) reads 0 "
                 "and an OBJ-only (--disable-bg both sides) re-capture repeats the "
                 "integrated per-k list EXACTLY (total 72499), so all of it is OBJ. "
                 "Regions: top 0 on every frame, mid ~1080-1470, bot ~270-1230 with a "
                 "k=32+ jump (mid ~1430, bot ~1200). OAM at k=0/33/39 (canon 120+/rust "
                 "127+): canon 12 active -> 15 (navi pal 0 tiles 1/9/25/29 at x41-65, "
                 "enemy pal 1 tiles 31/35/43 at x163-174, HUD pal 12 tiles 948/956 at "
                 "y18; a second enemy cluster at x203-214 appears k=32+) while rust "
                 "holds 11 frozen all three frames (HUD pal 4 tiles 168/176, navi pal "
                 "2 tiles 124/132/148/152, enemy pal 0 tiles 0/8 + pal 3 tiles "
                 "154/158/166, same positions): palette/sheet assignment differs and "
                 "canon's enemy animates/materializes while ours holds -- an intro-hunk "
                 "fix, out of scope.",
        ),
        rust=lambda ui: Side(rom=plain_rom(), fixture=OPEN_ROW,
                             extra=() if ui == "integrated" else ("--disable-obj",)),
        canon=lambda ui: Side(rom=REAL, loadstate=BATTLESTART,
                              extra=() if ui == "integrated" else ("--disable-obj",)),
        canon_variant="canon",
    ),
    Check(
        name="mettaur",
        ui="isolated",
        frames=70,
        align=Align(
            canon_ref=140,
            search=range(193, 214),
            note="canon: STERILE+PAUSED+ALIVE, Start@10 -- a scripted press with no clock "
                 "shared with rust's cold boot, so canon_ref=140 is the same documented fixed "
                 "point regress.py's check_mettaur used (its own frame-140 window start), not "
                 "searched. rust: marker origin (frame 8 for FIELD_ROW, re-measured this "
                 "ticket). PAIRED BY EVENT, NOT SCORE (TODO F2, 2026-09-12): both sides run "
                 "the same 106-frame Mettaur attack cycle, measured from --watch captures of "
                 "this row's own sides -- canon attack anims start at canon frames 32 and 138, "
                 "ours at battle frames 95, 201, 307, 413 (capture = battle + 8); MegaMan is "
                 "hit mid-attack-1 on BOTH sides -- canon HP 60->50 at canon frame 114, ours "
                 "battle frame 177 (176 before F25c's one-frame hit-delay fix) -- so both attack-2s fire while MegaMan is inside the "
                 "120-frame mercy from the attack-1 hit (canon mercy 114..233 covers 138; "
                 "ours 176..295 covers 201). The old band (295..325, offset 309) paired "
                 "canon's SECOND attack with our THIRD -- ours took its first hit at 176 and "
                 "its third-attack wave falls outside that mercy, so the two sides sat in "
                 "different situations for the whole window. Event-derived offset: rust "
                 "attack-2 start capture 209 = origin 8 + offset + k with canon_ref+k=138 "
                 "(k=-2) gives offset 203; F25c re-swept the band and it CONFIRMS a single sharp "
                 "V-minimum exactly there (202: 46297, 203: 4265, 204: 37873 over 70 "
                 "frames), not chosen by score -- the old offset 309 scored 30864, LOWER, "
                 "but pairs incompatible attack indices. The 1-frame-early hit is FIXED in "
                 "src/shot.rs (F25c): canon's wave presents its collision at init in the hop "
                 "frame (PanelX (2,2) after canon frame 113) but MegaMan's HP drops the next "
                 "frame (60->50 after 114), so the shockwave's flight is 45 frames launch to "
                 "hit; ours was 44 (hit on the hop frame). `Shot::hop_pending` latches the hop "
                 "and reports it one frame later for the shockwave only -- our hit moved to "
                 "battle 177 (flight 45), the oracle's every parity field matches 70/70, and "
                 "the row fell 19698/1245 -> 4265/800. NOT YET ZERO: the remaining 4265 px sit "
                 "on 8 frames only (k=0,1,6,11,17,22,63,68), all outside the enemy box (inbox 0) "
                 "-- the departure spray's shape around MegaMan at the same post-hit phase on "
                 "both sides, i.e. spray content not timing, left for a follow-up. Ported from the demo-field feature to FIELD_ROW (fixture.rs's "
                 "own table entry, already used by `wave` below; AUDIT pair 17 prune "
                 "ticket) -- same descriptor bytes. F28 (2026-09-13) moved the event-locked "
                 "offset 203 -> 205 BY THE EVENT, not by score: src/ai.rs now spends canon's own "
                 "arming frame and the 31st frame of the 0x1e post-spawn wait (sub_810A004 "
                 "asm31.s:171296-171305 / sub_8109CBC asm31.s:170665-170672), so our attack "
                 "entries moved +2 (oracle enemy CurAction 0x0b at 0x0200001e, battle "
                 "95/201/307 -> 97/203/309, canon's 31/137/243 unchanged) and the band re-swept "
                 "reproduces the identical V two frames along (204: 46297, 205: 4265, 206: "
                 "37873) with the same 4265 on the same 8 frames.",
        ),
        rust=lambda ui: Side(rom=plain_rom(), fixture=FIELD_ROW, extra=("--disable-bg",)),
        canon=lambda ui: Side(rom=STERILE, loadstate=PAUSED, cheats=ALIVE, script="Start@10",
                              extra=("--disable-bg",)),
        canon_variant="canon (sterile)",
    ),
    Check(
        name="cannon",
        ui="isolated",
        frames=40,
        align=ALIGN_CHIP_0C,
        # TODO F7 (2026-09-12): re-pointed onto the SAME route and Align
        # method F5b used for the 43 chip-scoreboard rows (chip-cannon is
        # literally this comparison: same rust descriptor from _chip_rust,
        # same canon recipe from _chip_canon_0c) -- the PAUSED route the
        # row kept after the prune ticket paid the shared 14388/2350
        # fixture-artifact baseline (PAUSED's leftover portrait box, canon
        # frames 43-48, plus the deleted Mettaur's dissolve, 43-52) that
        # afterdissolve_0x0c does not have. Rust side UNCHANGED from the
        # prune ticket: _chip_rust("01") -- fixture.rs's own table entry
        # for this row (enemies 0, hp 100, col/row 2/2, hand [1], gauge 0,
        # flags 0x1F, fire_frame 90) -- byte-for-byte the descriptor the
        # 43 chip-scoreboard rows already use. The ALIGN_CHIP_0C search
        # band is kept only to CONFIRM the minimum, as for chip-cannon.
        rust=_chip_rust("01"),
        canon=_chip_canon_0c("01"),
        canon_variant="canon (sterile)",
    ),
]

CHECKS.extend(_chip_checks())

# --------------------------------------------------------------------------
# The remaining regress.py checks (AUDIT.md "First job after the audit" /
# wave 3 ticket step 1). Same recipe throughout: a plain build plus a
# fixture descriptor taken from src/fixture.rs's verified table wherever it
# is expressible, full-screen diff (pair 6), marker-aligned (pair 1) with a
# small search band replacing regress.py's raw-frame lag (which was
# boot-length-relative and is now origin-relative), `pending_src` set where
# the descriptor cannot say what the check needs yet.

#: demo-hudmatch's row, fixture.rs's table -- VERIFIED BYTE-IDENTICAL there.
#: Marker origin measured live (this ticket): 8, same family as
#: demo-open/demo-field (no HUD/backdrop blanking to shortcut the boot).
HUDMATCH = dict(enemies=1, enemy_kind=0, enemy_col=5, enemy_row=2, megaman_hp=60,
                megaman_col=2, megaman_row=2, hand=[1], hand_count=1, gauge=1,
                flags=0x10, art_entry=23, art_timer=6, scroll_xq=36, scroll_yq=18,
                # F20b (2026-09-13): positions peeked from this row's own canon
                # capture (REAL + PAUSED + Start@10, canon frame 44): MegaMan
                # PanelX/PanelY 0x0203a9c2/0x0203a9c3 (BattleObject 0x0203a9b0
                # +0x12/+0x13) read (2,2), enemy 0x0203ab72/0x0203ab73 (slot
                # 0x0203ab60 +0x12/+0x13) read (5,2) -- provenance: peeked.
                # TODO F6 (2026-09-12): the phase of the CUSTOM gauge's flow
                # counter. Canon's gauge routine (sub_801C4E4, asm00_2.s:26351)
                # draws bar and marker off ONE counter t (eStruct2035280+0x00,
                # 0x02035280) with NO additive phase: bar tile 0x9232+((t div 7)
                # & 3), marker orange iff (t & 8). PAUSED's t carries an
                # arbitrary fill history -- measured over this row's own canon
                # capture it reads 98 at state load and the draw inside canon
                # frame c uses t = 98 + c (it advances even during the paused
                # frames) -- while the fixture-built battle counts gauge_tick
                # from Battle::new (gt(u) = u - 7, first set_gauge at the
                # marker origin 8). Measured off this row's own alignment (old
                # build: our marker flipped at rust 440, canon's at canon 46,
                # its bar at canon 49): gt(435) = 428 must equal canon's
                # t_used(44) = 30 mod 112, so the seed is 30 - 428 = -398 =
                # 50 (mod 112). With it, src/hudtiles.rs's canon-verbatim
                # formulas align bar AND marker exactly (tiles/gauge isolated
                # residue 538 -> the 208-px wide-screen frame only).
                # F28b (2026-09-13): the four backdrop seeds above and this
                # gauge counter are the SAME phases, translated 318 frames
                # earlier so the compared frame is one our battle is actually
                # in canon frame 44's SITUATION at. F28 measured why they had
                # to move: at the old rust battle 427 our Mettaur matched
                # canon exactly but our MegaMan had taken two shockwave hits
                # (HP 40, inside the 120-frame mercy) where canon's holds 60
                # unhit -- 13642 px, all of it on the left half. 318 = 3 x the
                # Mettaur's own 106-frame cycle, so the enemy keeps the phase
                # F28 proved, and 427 - 318 = 109 is before our first hit
                # (battle 181). A translation, not a re-fit: the backdrop's
                # clocks advanced 318 ticks of src/backdrop.rs's own update
                # (entry 5 / timer 4 -> entry 23 / timer 6 through STEP_ORDER
                # and STEP_HOLD, x_q 424 -> (424 + 2*318) mod 1024 = 36, y_q
                # 724 -> (724 + 318) mod 1024 = 18), and the gauge counter the
                # same (unseeded gt at capture 117 is 110, and 32 + 110 = 142
                # = 30 mod 112, canon's own t_used(44) -- the identity the old
                # seed 50 satisfied at capture 435).
                gauge_tick=32)
HUDMATCH_ORIGIN = 8


def _tiles_gauge(name: str, subject_note: str) -> Check:
    # regress.py's TILES_REAL_FRAME=44, TILES_RUST_FRAMES=range(433,438)
    # (center 435) -- both checks used the SAME capture, just different
    # boxes. Full screen (pair 6) makes them the SAME comparison; kept as
    # two named rows for continuity with regress.py, not because the
    # numbers will differ. offset center = 435 - HUDMATCH_ORIGIN(8) = 427;
    # an 8-frame window (not 1) so the alignment is a rate, not a still
    # picture (pair 10's own lesson from `window`/`card`).
    return Check(
        name=name,
        ui="both",
        frames=8,
        align=Align(
            canon_ref=44,
            search=range(97, 122),
            note="canon: regress.py's TILES_REAL_FRAME=44, fixed (PAUSED+Start@10 is a "
                 "documented scripted landing, not searched). rust: marker origin 8 "
                 "(demo-hudmatch's own family) plus a 25-frame band around 109, which is "
                 "regress.py's old center (435-8=427) minus 318 = 3 x the Mettaur's 106-frame "
                 "cycle (F28b, see the descriptor's own comment; the band was range(415,440) "
                 "while the descriptor seeded the old frame) -- %s. NOT boxed: regress.py split this same capture "
                 "into `tiles` (y>=24, backgrounds) and `gauge` (y<24, HUD strip) precisely "
                 "because the HUD strip carries a KNOWN, unresolved defect (TODO A8, the "
                 "gauge's stripe animation) that would otherwise contaminate a background-only "
                 "reading -- full screen (pair 6) can no longer keep them apart by cropping, so "
                 "both rows now read the SAME whole-screen number and the HUD defect is "
                 "reported (and allowlisted, not hidden) on both. F28 (2026-09-13) measured "
                 "what the 3865 IS, and it is not the HUD: (a) the rust side's battle FREEZES "
                 "at battle frame 62 -- HUDMATCH clears SceneFlags::OPEN_WINDOW, so battle.rs's "
                 "gauge-fill branch re-arms gauge_pause = GAUGE_PAUSE every frame while the "
                 "branch that decrements it is gated on open_window_allowed(), leaving `paused` "
                 "true for good; the Mettaur never leaves its post-spawn wait (oracle enemy "
                 "CurAction 0x09 at 0x0200001e for the whole 470-frame capture) and the whole "
                 "3865 is its idle sprite against canon's swing, bbox (164,68)-(204,111), with "
                 "every other pixel on the screen 0. (b) With that freeze lifted as a throwaway "
                 "patch, the rust Mettaur runs FIELD_ROW's own 106-frame cycle here too and, "
                 "captured OBJ-only, its box (150,55)-(215,125) reads EXACTLY 0 over all 8 "
                 "frames -- at offset 425 before F28's +2 in src/ai.rs, at THIS row's own 427 "
                 "after it. That 2-frame gap against a pin the Mettaur has no say in (the "
                 "backdrop scroll makes 426/428 whole-screen diffs, and gauge_tick seeds the "
                 "gauge to 427) is where F28's +2 was measured. (c) What still blocks 0 is "
                 "MegaMan, not the enemy: unfrozen, he has taken two shockwave hits by battle "
                 "427 (oracle HP 0x3c -> 0x32 at battle 177, -> 0x28 at 389) and is inside the "
                 "120-frame mercy, while canon holds 60 unhit through frame 51 -- the left half "
                 "goes 0 -> 13550 and the row 3865 -> 16130. So fixing the freeze ALONE makes "
                 "this row worse; 0 needs the fixture to carry canon's mid-battle MegaMan as it "
                 "already carries canon's backdrop and gauge phase. F28b (2026-09-13) DID THAT, "
                 "and the row READS 0 -- both variants, full screen, negatives not blind. Not "
                 "by seeding MegaMan (his HP and mercy at battle init cannot survive 427 frames "
                 "of our own Mettaur hitting him) but by moving the compared frame to one our "
                 "battle is genuinely in canon frame 44's situation at: the freeze is gone "
                 "(src/battle.rs's gauge_pause is armed only when the window may open, cited "
                 "there), and the descriptor's four backdrop seeds and gauge_tick were "
                 "TRANSLATED 318 frames earlier -- 3 whole Mettaur cycles, so the enemy phase "
                 "F28 proved at 427 is the same phase at 109, while 109 is before our first "
                 "shockwave hit (battle 181), so MegaMan is idle at HP 60 with FlashingInvisTimer "
                 "0 exactly as canon's is (peeked: BattleObject 0x0203a9b0 +0x24 = 0x3c, +0x20 = "
                 "0, CollisionDataPtr +0x54 -> 0x020384f0 +0x24 = 0 on canon frames 42..48). "
                 "Per-half at the new alignment: left x<120 = 0, right x>=120 = 0, HUD strip "
                 "y<24 = 0. The stages measured on the way: 3865 frozen at 427, 13642 unfrozen "
                 "at 427 (all left), 3460 at 109 with the old gauge seed (all HUD strip), 0 with "
                 "the translated one." % subject_note,
        ),
        rust=lambda ui: Side(rom=plain_rom(), fixture=HUDMATCH,
                             extra=() if ui == "integrated" else ("--disable-obj",)),
        canon=lambda ui: Side(rom=REAL, loadstate=PAUSED, script="Start@10",
                              extra=() if ui == "integrated" else ("--disable-obj",)),
        canon_variant="canon",
    )


#: AUDIT pair 3's standard: "arena checks run with zero enemies." field,
#: warp, buster and chip-use are not about the enemy (mettaur/wave keep a
#: real one, below, because they ARE about it), so their old ALIVE-mettaur
#: setup -- an enemy acting on an RNG the two sides do not share, sitting
#: right there for a full-screen diff to trip over -- is replaced with a
#: genuinely empty arena: the fixture's own `enemies: 0`, and, on the canon
#: side, the enemy DELETED (not merely hidden -- see DELETE_ENEMY's own
#: comment just below for why --hide-enemy's immortal-but-alive enemy turned
#: out not to be inert either). Marker origin 8 (measured live, same family
#: as demo-field/demo-open -- no HUD/backdrop blanking).
#: hand=[]: PAUSED's own queued Cannon-icon (tools/states.py: "Cannon40
#: already queued in the hand") turns out NOT to be permanent -- verified
#: live (this ticket): by the real capture frame these checks now compare
#: from (130+, past the DELETE dissolve), the icon is already gone on the
#: canon side, so an empty rust hand is the match, not hand=[1] (tried
#: first, against the pre-dissolve-wait frame 90 -- wrong once the compare
#: window moved).
#: megaman_hp: 60, not 100 -- F33 (2026-09-13). All four zero-enemy rows
#: compare against the SAME canon state these fields describe (STERILE +
#: pausedwithcannon + DELETE_ENEMY), whose navi holds 0x003c at 0x0203a9d4
#: (BattleObject 0x0203a9b0 + 0x24) -- the value FIELD_ROW's own comment
#: already records as peeked from PAUSED. The HUD's HP box is battle-HUD
#: element 2 (mask dword_20352C0, updater sub_801C168 asm00_2.s:25854, draw
#: sub_801C202 asm00_2.s:25952; bit 2 is set in canon's mask on every frame
#: of all four rows' compared windows, measured with --watch 0x020352C0:8),
#: so it is drawn on both sides and a wrong HP is a live pixel difference:
#: measured on field integrated, ours drew "100" against canon's "60" for a
#: steady ~30 px/frame in the box (the extra leading "1" at x19..20 y3..12
#: plus the changed units digit). provenance: peeked.
#: hand: Cannon, not empty -- F33b (2026-09-13). pausedwithcannon's own
#: queued Cannon40 is still in canon's "chip to use" slot (dword_20352C8) on
#: every compared frame of all four rows, and canon's element 6 (draw
#: sub_801C6EE asm00_2.s:26619, BG3 map rows 0x12/0x13) keeps writing its
#: name and damage there -- measured: canon's BG3 carries "Cannon 40" at
#: y148..158 x1..63, 422 px on every frame, which an empty rust hand cannot
#: draw. What is gone on the canon side by frame 130 is the ICON, because
#: that is element 1 and the teardown at canon 48 cleared it; the earlier
#: note here read the missing icon as a missing chip. Both now follow canon:
#: the descriptor carries the chip, and src/battle.rs gates the icon (not the
#: name) on `hud_live`. provenance: peeked.
ZERO_ENEMY = dict(enemies=0, megaman_hp=60, megaman_col=2, megaman_row=2,
                  hand=[1], hand_count=1, gauge=0, flags=0x11)
ZERO_ENEMY_ORIGIN = 8

# --------------------------------------------------------------------------
# F33 (2026-09-13): what the four integrated (full-HUD) variants of these
# rows actually differ by, decomposed by HUD element and by layer. Measured
# in tools/worktree.sh f33-hud-elements; every number below is a full-screen
# count on the row's own alignment, with the row's own negative confirmed
# not blind.
#
# CANON'S HUD ELEMENT MASK, measured on each row's OWN canon capture with
# --watch 0x020352C0:8 (update mask dword_20352C0, draw mask dword_20352C4;
# dispatchers sub_801BEE0 asm00_2.s:25540-25563 and sub_801BF64 :25564-25599,
# one updater/draw pair per bit):
#
#   canon frames   0- 47   update 0x4497   draw 0x44d7   (full battle HUD)
#   canon frames  48-105   update 0x8084   draw 0x80c5   (teardown + bit 15,
#                                                         the ENEMY DELETED
#                                                         banner)
#   canon frames 106-...   update 0x0084   draw 0x00c5
#
# The teardown at canon 48 is F27b's sub_80081A4 -> sub_801BED6(0xE4C53)
# (asm00_1.s:10617-10621), clearing bits 0,1,4,10,14 from the update mask and
# 1,4,10,14 from the draw mask. EVERY compared frame of all four rows (field
# and warp from canon 130, buster and chip-use from canon 150) therefore sits
# in the LAST state: canon updates elements 2 and 7 and draws 0, 2, 6 and 7 --
# no gauge, no hand icon, no emotion window.
#
# The elements, with the dispatcher table's own entries:
#   bit  updater (off_801BF04)            draw (off_801BF88)              what
#    0   sub_801BFEE :25647 ->801C002(1)  sub_801C06E :25721 ->801C082(1)  ready-chip bubble, class 1 (6 slots at dword_20352E0)
#    1   sub_801BFF8 :25655 ->801C002(0)  sub_801C078 :25729 ->801C082(0)  ready-chip bubble, class 0 = the queued-chip ICON; TORN DOWN at canon 48
#    2   sub_801C168 :25854               sub_801C202 :25952               MegaMan's HP box (BG3 map rows 0-1, screen y0-15 x2-45, 704 px)
#    4   sub_801C470 :26292               sub_801C4E4 :26351               the CUSTOM gauge; TORN DOWN at canon 48
#    6   nullsub_58 (draw only)           sub_801C6EE :26619               the queued chip's NAME + damage, BG3 map rows 0x12/0x13 (screen y144-159 x0-63); reads dword_20352C8, renderTextGfx_8045F8C to 0x0600cb00
#   10   sub_801C984 :26969               sub_801C9A4 :26989               TORN DOWN at canon 48
#   14   sub_801CADC :27186               sub_801CDEC :27554               the emotion window (F27b); TORN DOWN at canon 48
#
# WHAT CANON ACTUALLY PAINTS on those frames (canon side, --only-bg 3, field
# row, canon 130): 1126 px, and only two things -- the HP box (704 px, y0-15
# x2-45) and the chip name strip, which reads "Cannon 40" (422 px, y148-158
# x1-63; pausedwithcannon's own queued Cannon40, whose OBJ icon is gone
# because element 1 was torn down, while its NAME is element 6 and was not).
#
# PER-ELEMENT RESULT for field integrated, the F33 measurement (offset 108,
# canon_ref 130, 40 frames), against F33's own baseline 305263/10061 --
# EVERY line of it is now fixed or attributed; see F33b's own commits and the
# seed note above for the after numbers:
#   element 2, HP box .......  29 px/frame -> 0   (F33: ZERO_ENEMY megaman_hp
#                                                  was 100, canon's navi holds
#                                                  60)
#   element 6, chip name .... 422 px/frame -> 0   (F33b: ZERO_ENEMY hand=[1],
#                                                  the icon gated on hud_live)
#   element 4, CUSTOM gauge . 1596 px/frame -> 0  (F33b: gauge_up gated on
#                                                  hud_live)
#   element 14, emotion .....   0 px (F27b hides it; F33 gave it the chip
#                                     window's x displacement)
#   elements 0, 1, 7, 10 ....   0 px (no slots active, no enemies, torn down)
#   the BG1 backdrop phase .. 261797 px of 305263 (86%) -> 0 on every frame of
#                             warp/buster/chip-use and on every field frame
#                             before its own end-sequence stall (F33b's seeds)
# What is left on these four rows is NOT the HUD and NOT the backdrop:
#   * canon's RESULT window slides in from canon 154 on all four canon
#     captures (the deleted-enemy battle resolves), and only `field` carries
#     SceneFlags::RESOLVE_OVER, so warp k>=24, buster k>=22 and chip-use k>=4 are the
#     window's own ramp: warp 40628 of 40628, buster 45810 of 54672, chip-use
#     565717 of 567780, all of it on BG3.
#   * buster additionally keeps drawing the name from k=1 where canon has
#     stopped. Measured on buster's own canon capture (--only-bg 3): the strip
#     holds "Cannon 40" (422 px, y148..158 x1..63) on canon 132 and is BLANK
#     from canon 133 -- the frame after CurAction 0x11, the buster action --
#     for the rest of the window, while the HP box beside it stays at its 704.
#     It is NOT the ChipsHeld gate: sub_801C6EE (asm00_2.s:26619) blanks map
#     rows 0x12/0x13 and re-renders unless sub_800ED90's r3 = 0, r3 is
#     oBattleObject_ChipsHeld (+0x1a, asm00_2.s:15-46), and that byte reads 1
#     on every frame of the capture (--watch 0x0203a9ca:2). What empties the
#     strip is inside sub_800ED90's player branch, where the chip comes from
#     getBattleHandAddr_8010018's own index byte -- i.e. entering the attack
#     moves canon's hand past the queued chip, which our `hand_at` does not
#     do for a buster shot. Left unfixed on purpose: `warp` (a move, not an
#     attack) keeps the name on all 24 of its pre-RESULT frames, so the rule
#     is attack-specific and guessing it would regress warp. 422 px/frame x 21
#     frames = 8862 of buster's 54672.
#   * field's own end sequence: captures 118, 119 and 120 are byte-identical
#     to one another (a three-frame stall -- the backdrop scrolls on every
#     other frame before and after, so BG1 is 0 only for k=0..1), and from
#     capture 121 `self.shown` is Some, so battle.rs skips `filler_bg` and
#     every layer drops one hardware BG (BG0 backdrop, BG1 panels, BG2 HP box,
#     BG3 the RESULT window) while canon's own RESULT window has not started.
#     That is F32's end-sequence offset, not a HUD or backdrop defect, and it
#     is why --only-bg N is a same-content comparison on this row only for
#     k=0..4.
#
# F33c (2026-09-14): re-measured all four on main with F32's count landed.
# The sequencer event first: dword_203CA70 -> 0x0C at canon 47 on EVERY row's
# own canon capture (field/warp/buster/chip-use identical: 0x1c at 0..10,
# 0x08 from 11, 0x0C at 47; tools/probe.py watch 0x0203ca70:4). Per-k shapes
# at each row's event-locked offset, full screen:
#   warp off 51 ..... k=0..23 all 0, k=24..29 = 1917,3837,5757,7677,9696,11744
#                        (canon's 154..159 slide-in at 1917 px/frame, no rust
#                        counterpart; total 40628, sharp unique minimum)
#   buster off 103 ... k=0 reads 0, k=1..21 read 422 (the name strip above),
#                        k=22..27 = 2458..12977 (slide + strip; 45810 of 54672)
#   chip-use off 100 . k=0..3 read 0 (the Cannon matches), k=4..31 canon's
#                        window ramping then saturated at 25328/frame (567780)
#   field off 108 .... k=0,1 read 0, k=2.. avg ~4757 (the stall, below), and
#                        the slides overlap in k (rust 140..153 <-> canon
#                        154..167) with matching content (mid -> ~100 by k=36)
# The flag was TRIED on warp and REVERTED: instant-resolve (over at battle 0)
# reads 83175 integrated (was 40628) and 44767 isolated (was 0). Structural,
# not tuning: `paused` includes `over` (battle.rs), so the scripted moves
# never fire, and our ENEMY DELETED banner (banner.rs SCALE, 58 frames, OBJ)
# parks its tail over k=0..9. The same wall stands on buster (B frozen, the
# attack gone) and chip-use (A frozen, the Cannon never fires): every canon
# side acts AFTER 0x0C (warp warps at 132/152, buster CurAction 0x11 at 132,
# chip-use A@150 fires), i.e. canon keeps simulating inputs post-resolve
# while our `over` freezes them -- so aligning the windows needs over before
# frame 0 while the subjects need the fight alive past battle 50/100, which
# one `over` event cannot do. No descriptor flag landed, and with nothing
# landed battle.rs needed no fixture-side entry point for F32's count.
# field's stall, decomposed by region at off 108 (canon 130+k vs rust 116+k;
# top y0-15, mid y60-110, bot y140-160, rest the remainder):
#   k=0,1 ......... 0 in every region (the pre-stall pairing is exact)
#   k=2..23 ....... ~4757/frame full-screen scroll-phase mismatch: rust
#                   117->118, 118->119 and 119->120 are all full=0, flipping
#                   the every-other-frame scroll rhythm (pre-stall transitions
#                   match canon at lag 14, post-stall at lag 11; canon's own
#                   rhythm never freezes past isolated singles). Region sums
#                   over the whole window: top=33496 mid=22633 bot=25306
#                   rest=100128 = 158930.
#   k=24..37 ...... the RESULT slides coincide in k with matching content:
#                   mid collapses toward ~100 and rest falls as the window
#                   covers the mismatched scroll, while bot carries the
#                   slide-edge/mark delta (~1000-1450/frame). F21/F34's chain
#                   holds; the window is not the defect.
#   The stall's three frozen updates coincide with results_delay 3,2,1 (the
#   show fires at battle 110 = capture 121); the freezing mechanism itself is
#   untraced and belongs to the battle.rs owner, outside this ticket's scope.
# Record correction: the F33 seed note's per-row minima predate F33b's seeds
# and F32's count -- on main the field search bottoms at the band's top edge
# (108; 158930) riding slope + stall, NOT at the event lock (81 reads
# 566712). The offsets stay event-locked by mark/press, never by score.
#
# F38 (2026-09-14): warp/buster/chip-use re-measured on main with per-k,
# regions, BG splits and sequencer watches; no src/descriptor change landed.
# Sequencer dword_203CA70 is identical on all four canon captures (0x1c at
# 0..10, 0x08 from 11, 0x0C at 47, 0x0400000C from 48); mask 0x020352C0 reads
# 0x4497 -> 0x8084 at 48 -> 0x0084 at 106; subjects act after 0x0C (warp MM
# warps at 130/150, buster CurAction 0x08->0x11 at 132, chip-use 0x08->0x14
# at 130). Warp: k=0..23 all 0, k=24..29 = 1917,3837,5757,7677,9696,11744 =
# canon's BG3 slide (first 16 px strip at canon 154, slide 154..167, settled
# ~27.2k; name-strip region 0 throughout). Buster: k=0 0, k=1..21 422 (BG3
# name strip, canon blanked after the 0x11 write, ours kept -- attack-specific,
# still unfixed on purpose), k=22..27 ramp; sweep V unique at 103. Chip-use's
# printed 275307 sits at the search band's left edge (94; sweep 90..112 falls
# monotonically leftward with only a dip at the event lock -- 100: 284620,
# 101: 281885, 102: 294404): score-ridden, not event-locked; honest lock
# remainder 281885. BG-split at 101: BG0 0, BG2 (panels) 0, BG3 = name strip
# 844 (k=1,2) + slide ramp 44306, BG1 (backdrop) ~17k/frame on EVERY frame --
# canon shows magenta '10/01' rings, ours plain blue rings; art_entry 10..17
# and art_timer 0..7 sweeps do not move it (timer exactly no effect) while the
# peeked canon inputs re-verify (entry 26/timer 5 at 150, counters battle
# 8042): this row's walk-back/seed does not produce canon's art, mechanism
# untraced, no descriptor change made (warp BG1-only control reads 0, so the
# layer mapping and the other rows' seeds are sound). Field: our visible slide
# runs rust 140..153 (show battle ~110 + SLIDE_HOLD 16 + reveal) vs canon
# 154..167 -- both k=24..37 at off 108, coinciding with matching content
# (settled ~28.3k vs ~27.2k); the stall attribution keeps. Resolving
# warp/buster/chip-use cannot coincide (our show battle ~110+ lands past
# warp's window while the banner tail would regress k=0..7 and isolated), and
# BANNER_TO_RESULTS is untouched (field's coincidence depends on it).

#: ZERO_ENEMY plus SceneFlags::RESOLVE_OVER (FIXTURE.md +19 bit5, TODO F8): the
#: `field` row's rust side resolves the way its own canon side does -- canon's
#: deleted-enemy battle reaches the all-dead advance (sequencer 0x0C at canon
#: 47, watched), ENEMY DELETED (canon 49..106, documented), the RESULT window
#: (BG3, canon ~154..167) and its mark OBJ (canon 163..166, watch-write on
#: dword_3002180), so a rust side that holds the fight open forever differs
#: by the mark's 177 px for the last six compared frames. Only `field`
#: carries the bit: warp/buster's own windows end before canon's mark enters
#: (their tickets F11/F10), and chip-use must keep the fight alive to fire
#: its chip at all.
#: F38b (2026-09-14): SceneFlags::RESOLVE_OVER retried on warp/buster/chip-use now that `over`
#: no longer freezes inputs/objects (F33d) -- measured worse-or-flat, reverted: warp
#: integrated 40628->45751 (isolated 0->5123, banner tail k=0..7), buster 54672->81083
#: (isolated 0->2286, our show/mark entering a window whose canon side has neither),
#: chip-use 275307->269172 (isolated 0->4026; only row straddling our show, partial
#: slide overlap). Sequencer re-watched: 0x0C at canon 47; our `over` at capture 8
#: with show at battle ~110 cannot sit at canon's k=24..29 under event-locked subject
#: offsets -- one BANNER_TO_RESULTS cannot serve both, left untouched for field.
#: Driver chain (sub_802BD60->sub_802BE36, 16 px/frame) holds: result isolated 0,
#: warp ramp 1917..11744, field k=24..37 matching content.
#: T7 (2026-09-14): the hand-written `over` flag is now canon's sequencer
#: table (src/battle.rs `Sequencer`: 0x08 the fight, 0x0C/0x10 the end counts,
#: transition edge at dissolve expiry; the real word rides the TRC2 block,
#: judged in tools/trace.py). Per-state counts/handlers stay the old composite:
#: factoring the 110 as the table's 94-count + 16-frame setup read +12 on field
#: integrated (one frame) and was reverted. battle_full sequencer: 0x08 on both
#: sides to each side's kill+35, then 0x0C on both (8 frames apart in k -- the
#: known kill-offset of the rust recipe); the custom-screen states (0x20/0x24/
#: 0x04) and the kill->slide gap (canon +107, ours +132) stay OPEN.
#: T7e (2026-09-14): the two T7c citations in src/battle.rs are corrected
#: (asm00_1.s:10527-10537 -> :10609-10611, the sub_80080D2 `str r0,[r5]` that
#: writes 0x20 after PauseBattle; :10841 -> :10958 in sub_800840C + :11022 in
#: sub_8008492, the sub_801483C call sites, not sub_800834A's jump table).
#: battle_full sequencer remains 173/540: 165 frames k=31..195 (window setup --
#: the fixture never opens the window), 8 frames k=297..304 (auto-fire kill 8
#: aligned frames early). warp/buster/chip-use/opening byte-identical to the
#: T7c battery; field's allowed row 158979 unchanged; cursor 10/9/170/186276
#: (T7c left it at 3/2/170/186277 -- the binary moved the tear, not chased).
ZERO_ENEMY_RESOLVED = dict(ZERO_ENEMY, flags=0x31)  # 0x11 | SceneFlags::RESOLVE_OVER (bit5)

#: `chip-use` alone: an A press with an empty hand uses nothing, so this
#: variant carries Cannon (PAUSED's own queued chip) the way FIELD_ROW does.
ZERO_ENEMY_WITH_HAND = dict(ZERO_ENEMY, hand=[1], hand_count=1)

#: DELETE, not --hide-enemy: verified live (this ticket, on `field`) that an
#: immortal-but-alive Mettaur is NOT actually inert -- it keeps acting on
#: its own AI (digging, sparking), and those effects live outside
#: ENEMY_TILES/BANNER_TILES, so --hide-enemy leaves a large, moving,
#: unexplained residue behind. Deleting it (HP forced to 0, chip_compare.py's
#: default for chips that do not need a target) DOES eventually go fully
#: quiet -- verified live: `--dump 0x7000000:1024` after
#: STERILE+PAUSED+delete+Start@10 has zero non-empty OAM objects on the
#: enemy's side of the screen by capture frame 110 (empty at 110/120/130/
#:140/150, not just fading). So every zero-enemy check below starts its
#: comparison at real frame >=130 -- comfortably past the dissolve, not
#: mid-transition -- rather than trying to --zero a moving target.
#: F33b (2026-09-13): each zero-enemy row's own backdrop phase, derived by
#: F26b's derivation (its Result in TODO.md) from canon's own state at THAT
#: row's canon_ref -- never shared, because each row pairs a different canon
#: frame with a different rust frame.
#:
#:   BGScrollCB_BG1Diagonal3to2Scroll (asm00_0.s:3287-3303) writes
#:   (counter-8)>>4 and (counter-4)>>4 to BG1HOFS/BG1VOFS, and the counters
#:   eBGScrollCBCounters (ewram.s:619, 0x02009690/0x02009694) are zeroed at
#:   battle init (sub_8080D90/sub_8080DA0, asm00_1.s:8434-8435), so at canon
#:   battle frame f they hold -8f and -4f and canon's phase in backdrop.rs's
#:   quarter-pixel units is x_q = 2f mod 1024, y_q = f mod 1024. The art
#:   clock is eGFXAnimStates[0] (ewram.s:596, 0x020094c0; struct
#:   include/structs/GFXAnimState.inc: Timer +0x2, LoopAddress +0x4,
#:   CommandPos +0x8), entry = (CommandPos - LoopAddress) / 8, 192 ticks a
#:   cycle (STEP_HOLD in src/backdrop.rs sums to 192). Our pipeline lags are
#:   F26b's, measured once on windowclose and not re-tuned here: a capture
#:   frame R shows the SCROLL of tick R-7 and the ART of tick R-5. So with
#:   R0 = the rust capture frame this row pairs with its canon_ref (marker
#:   origin 8 + the row's offset),
#:       scroll_xq = (2f - 2(R0-7)) mod 1024,  scroll_yq = (f - (R0-7)) mod 1024
#:       art       = Backdrop's own clock walked back (R0-5) ticks from
#:                   canon's (entry, Timer), minus the seed's construction
#:                   lead (Backdrop::seed stores timer + 1).
#:
#: T25 supersedes the closed form above for FIELD_ZERO's pair (T29, re-derived
#: from the kept dumps). The closed form reproduces the PRE-T25 pair exactly
#: (canon 130 = -64176/-32088 -> f=8022, R0=116 -> 466/745), but reproduces the
#: LANDED 471/748 for NO whole-frame lag: stepping the lag by one moves H by 2
#: and V by 1, and 466->471 wants +5 quarters while 745->748 wants +3, so no
#: integer lag reaches either -- the +5/+3 is a ceil-edge phase correction
#: (reg = -ceil(x_q/4) rounds in half-frames), not a lag. The true derivation
#: of 471/748 is an exhaustive solve, not a fit: over all 1024 quarter-values,
#: against the two kept counter series (/tmp/bn-f47/canon_scrollcnt.bin +
#: /tmp/bn-t25-watch) under the model below (plain >>4 register, visible =
#: mirror lagged 1 capture, equality mod the 256-px content period), the seeds
#: zeroing k=1..39 are H = {471, 472} and V = {748} -- 2-of-1024 and 1-of-1024
#: constraints; the k=0-only sets are {473..476} H and {747..750} V, so H's
#: intersection with k=0 is EMPTY (k=0 is not seed-fixable). At the old
#: 466/745 the same model predicts the register-residual series H period-2
#: [2,1], V period-4 [1,0,1,1] px -- the negation of F47's measured best-shift
#: cycle [(-2,-1),(-1,0),(-2,-1),(-1,-1)], i.e. the closed form's own premise
#: confirmed; 471/748 zeroes the residual on k=1..39.
#:
#: The derivation was checked against F26b's two landed seeds before being
#: used here and reproduces both exactly with no tuning: CHIPSELECT canon 15
#: (counters -25368/-12684 = battle frame 3171, art entry 17 timer 4, R0 245)
#: gives CURSOR_ROW's art 11/3 scroll 746/885, and canon 81 (-25896/-12948 =
#: 3237, entry 25 timer 2, R0 261) gives WINDOWCLOSE_ROW's art 17/1 scroll
#: 846/935.
#:
#: Peeked per row on THAT row's own canon capture (--watch 0x02009690:8 and
#: --watch 0x020094c0:12), all provenance: peeked for the canon readings,
#: derived for the arithmetic above:
#:   field    canon 130: -64176/-32088 = battle frame 8022, art entry 23 timer 1; R0 = 8+108 = 116
#:   warp     canon 130: -64176/-32088 = battle frame 8022, art entry 23 timer 1; R0 = 8+51  = 59
#:   buster   canon 132: -64192/-32096 = battle frame 8024, art entry 24 timer 7; R0 = 8+103 = 111
#:   chip-use canon 150: -64336/-32168 = battle frame 8042, art entry 26 timer 5; R0 = 8+100 = 108
#: The R0s are each row's own alignment, unchanged by this ticket, and three
#: of the four are pixel-exact on their own isolated (OBJ-only) variant --
#: the strongest pairing evidence a row can have, since an OBJ layer that
#: reads 0 over the whole window cannot be a coincidence of phase:
#:   field    isolated reads 0 on all 40 frames at offset 108, a sharp unique
#:            minimum (1139 at 107 and at 109), measured this ticket. The row
#:            note's older "~81 by the banner and mark events" is stale: at 81
#:            the isolated variant does NOT read 0.
#:   warp     Align pins rust_offset=51 with no search; isolated reads 0 there.
#:   buster   isolated reads 0 on all 28 frames at offset 103 (the row's own
#:            note records the sweep).
#:   chip-use the A press at battle frame 100 pairs with canon's at 150, so
#:            offset 100; its isolated variant is not yet 0, so this one rests
#:            on the press event alone.
#: With the seeds in, each row's integrated search now bottoms at exactly that
#: offset with a sharp margin (measured over each band): warp 51 (101168 vs
#: 170394/170612 either side), buster 103 (89416 vs 146978/150053), chip-use
#: 100 (619364 vs 645772/648094), field 108 (323855 vs 402474/389... either
#: side). Before the seeds, chip-use's band bottomed at 105, not 100.
FIELD_ZERO = dict(ZERO_ENEMY_RESOLVED,
                  art_entry=10, art_timer=4, scroll_xq=471, scroll_yq=748)
#: T25: scroll_xq 466 -> 471, scroll_yq 745 -> 748. What the pair buys: the
#: ANCHOR from which our one-capture-visible lag renders canon's offsets --
#: under the model "register visible during rust cap 121+k = mirror at
#: 121+k-1" (our agb commit lands the write one capture after the game-logic
#: frame the mirror records; canon's counter-to-register is same-capture),
#: 471/748 are the exhaustive-solve seeds that make our VISIBLE BG1 scroll
#: register equal canon's mod the 256-px content period on k=1..39 (see the
#: T25-supersedes paragraph at the F33b block above for the solve and its
#: solution sets). Canon side: the eBGScrollCBCounters RAM stream 0x02009690,
#: caps 135..174 = paired k=0..39 (/tmp/bn-f47/canon_scrollcnt.bin); ours:
#: the TRC2 mirror 0x020000B2/0x020000B6, post-update x_q/y_q
#: (0x02000080+50/+54, src/battle.rs's trace table; /tmp/bn-t25-watch).
#:
#: T29 corrections to this record, all re-measured from the kept dumps:
#: (1) CONVENTION PAIRING, NOT COMPETING MODELS. Our own cite for the scroll
#:     CB body (asm00_0.s:3305-3321, the F33b block above) says the asm writes
#:     (counter-8)>>4 and (counter-4)>>4. That -8/-4 wording SAMPLES THE
#:     COUNTER ONE FRAME EARLY relative to a per-frame watch: the asm stores
#:     the DECREMENTED counter before shifting, so plain >>4 applied to the
#:     value our watch sees IS the asm's value. The two conventions are the
#:     same counter read at two different points in the frame, not competing
#:     models of the hardware. The honest residual: the seed solution sets
#:     MOVE ({471,472}/{748} here vs {473,474}/{749} under the asm-sampled
#:     pairing) because pairing our per-frame mirror against canon's
#:     per-frame counter is off by one sample -- which set is canonical
#:     depends on whether you compare watch-to-watch or
#:     watch-to-asm-sampled-value; the capture decides the PAIRING, not the
#:     shift. A later ticket re-deriving a seed from the asm cite gets the
#:     other set -- decide by the pairing, not by the shift.
#: (2) k=0 IS OUTSIDE THE RAMP MODEL, not merely seed-unfixable: at 471/748
#:     the model predicts dH(k=0) = +1 px (H's k=0-only seed set {473..476} is
#:     disjoint from k=1..39's {471,472}), but the measured k=0 best shift is
#:     0 px (T29, translation sweep on /tmp/bn-t25-bg1: minimum AT (0,0)=4800,
#:     next best 10362 at (0,+1)) -- the k=0 residue is CONTENT (the 240x20
#:     top band, rows 0..19 x cols 0..239), not an unseeded phase, and the
#:     "+4 catch-up splits the H phase" phrasing above does not reach it.
#:     T29 measured field-bg2's residue: the SAME band (rows 0..19 x
#:     cols 0..239, k=0, 4800 px, zero on k=1..39) -- so bg1's and bg2's 4800
#:     are one shared F45-transition band, not a scroll defect and not two
#:     coincidental regions.
#: (3) The pixel evidence (F47's period-4 best-shift cycle
#:     (-2,-1),(-1,0),(-2,-1),(-1,-1) on /tmp/bn-t25-bg1, re-measured
#:     post-T24) is reproduced ONLY by the lag model above -- T29 re-derived
#:     it from the counters as the plain->4 residual series H [2,1] period-2,
#:     V [1,0,1,1] period-4 at the old seed, the cycle's negation.
#:     // canon: eBGScrollCBCounters at 0x02009690, canon caps 135..174,
#:     /tmp/bn-f47/canon_scrollcnt.bin (captured 21:55 this session's T25 run).
#:     OURS: /tmp/bn-t25-watch -- AND NOTE ITS OWN SEED, because a solver that
#:     misses it gets a self-consistent wrong answer (T31 hit exactly that):
#:     that stream is the OLD 466/745 capture (its files are timestamped
#:     2026-09-15 21:55:50, 31 min BEFORE 718fba5 moved the pair, and the dump
#:     proves it independently -- x_q is all-even across 210 watches with
#:     SCROLL_X_Q = 2, so parity is invariant and no odd seed can produce it;
#:     the anchor reads x_q[8]=470 = 466+2*2, y_q[8]=747 = 745+2 at battle
#:     frame 0). Therefore every seed in items (1)-(3) above is a SHIFT APPLIED
#:     TO A 466/745 MIRROR (candidate s -> mirror + (s-466) in x, + (s-745) in
#:     y), never a value read out of a 471/748 capture, and what the dump
#:     validates directly is only the OLD-seed series in (3). That dir's kept
#:     analyze.py is a superseded convention (canon 135+k <-> mirror 113+k,
#:     fold mod 512) and reproduces nothing; the validated model is
#:     one-capture-later + equality mod the 256-px content period. T31's
#:     verifier re-derived (1)'s sets from these two files alone in `field`'s
#:     own row indices (canon 130+k <-> rust 116+k -- same model, k relabelled
#:     by 5, the canon-rust gap is 14 in both) and got H {471,472} / V {748}
#:     for the ramp and k=0..2's {465,466} / {744,745,746}, disjoint: see
#:     docs/worklog/T31.md step 3.
#: (4) T31 (2026-09-16): MEASURED verdict on the k=0..2 group of field's
#:     integrated residue (15823 px = 5806+5319+4698, full height, cols
#:     0..227): NOT SCROLL -- no seed and no pixel shift reduces it. Two
#:     independent measurements, no value moved (ROM byte-identical):
#:     (a) exhaustive seed solve extended to ROW k=0..2 (canon cap 130+k <->
#:     rust cap 116+k, origin 8 + offset 108), all 1024 quarter-values per
#:     axis, both pairings, equality mod the 256-px content period. NOTE the
#:     kept /tmp/bn-t25-watch dumps are at the OLD seed 466/745
#:     (watch_scroll.py ran before the fixture move), and that dir's
#:     analyze.py (canon 135+k <-> mirror 113+k, fold mod 512) is a superseded
#:     convention -- the validated model is one-capture-later + mod 256 +
#:     dump seed 466/745 (it reproduces this block's (2)/(3) artifacts
#:     exactly). Result: under the landed one-capture-later pairing the H
#:     seeds zeroing row k=0..2 are {465,466} and V's are {744,745,746},
#:     while the seeds zeroing the ramp window k=6..39 are {471,472}/{748} --
#:     DISJOINT, so no seed zeroes both; best over k=0..2 alone is 0 px at
#:     466/745, but that seed predicts H [1,2] period-2 / V [0,1,1,1]
#:     period-4 residual across the 34 ramp frames whose pixels read 0.
#:     Same-capture pairing: H best over k=0..2 is 1 px (zero set NONE), V
#:     zero set {743..746}. At the landed 471/748 the model itself predicts
#:     only (-2,-1),(-1,-1),(-1,-1) px on row k=0..2 -- sub-2px, and:
#:     (b) pixel translation sweep on the row's own integrated pairing
#:     (harness.run serial, origin 8, canon 130+k <-> rust 116+k): the
#:     minimum over the whole dx,dy in [-4..4]^2 grid is AT (0,0) on all
#:     three frames (5806/5319/4698); the best non-zero shift is (dx=-1,dy=0)
#:     on each and makes every frame ~2x WORSE (11123/10675/9187). The 15823
#:     is transition CONTENT in place, not displaced content. Mechanism
#:     named: across caps 128..142 canon's counter->register rounds to
#:     half-px steps (H reg 86,85,85,84,84,...) while our engine holds x_q
#:     at 686 for 5 caps (STEP_HOLD, the 192-tick cycle) -- at the F45
#:     pre-boundary transition the two quantizations diverge by 1-2 px AND
#:     the resident art differs mid-transition; no seed fixes that without
#:     unfixing the ramp.
#: (5) T31: the bg1/bg2 one-capture-later ROW pairing question (rust_offset
#:     113 -> 114, same event-locked canon_ref 135), measured as a pair:
#:     field-bg2 total 0 worst 0 (the 4800 VANISHES; panels content is static
#:     so the moved pairing holds all 40 frames); field-bg1 total 170745
#:     worst 9923 -- its k=0 band ALSO vanishes (k=0 reads 0) but the moved
#:     pairing mispairs the scrolling backdrop on every k>=1 (full-height
#:     rows 0..159, cols 0..229; canon's register is stalled across the
#:     transition while ours has resumed). So neither 4800 persists as a k=0
#:     band under rust-later: the band is a ONE-CAPTURE TRANSITION EDGE on
#:     both layers (rust reaches canon-135's appearance one capture later
#:     than the landed pairing expects), not static content -- but no
#:     row-level pairing move fixes both rows, bg1's row cannot hold offset
#:     114, and no FIELD_ZERO value moves (the solve sets above are disjoint
#:     from the ramp's). bg1's and bg2's 4800 remain ONE shared F45
#:     transition artifact; bg1's half of that sentence is now pairing-
#:     measured, not only translation-swept.
#: T24: art_timer 7 -> 4, so `Backdrop::seed`'s construction lead (+1,
#: (art_entry, art_timer) = (10, 4) are both read at the POST-boundary anchor, canon cap 135 /
#: rust cap 121 (paired k=0); the cap-130 line above (entry 23, timer 1) is F26b's own anchor and is
#: superseded for this field by T23's. Source of both: // canon: eGFXAnimStates[0] at 0x020094c0.
#: src/backdrop.rs:233) puts our art countdown at 5 at the paired anchor.
#: 4 = canon's own countdown (`// canon: eGFXAnimStates[0] hw1 reads 4 at the
#: paired anchor, /tmp/bn-t23-art-clock-phase/canon_animstates.bin caps 135 and
#: 143, T23 step 3`) + 1 for the pipeline this engine's seed note records:
#: canon's tile copy lands one frame AFTER its clock edge
#: (QueueEightWordAlignedGFXTransfer), our port writes same-frame, so the
#: resident art matches only if we fire at canon's edge+1 (timer 8 fired 3
#: frames after canon's resident edge -- F47's +3, the whole 158930 px field
#: integrated residue). T23's naive art_timer 3 (timer 4 = canon's literal
#: countdown) would fire one frame early: the 208-px tiles/gauge failure the
#: seed note already recorded for the bare peeked Timer 4.
WARP_ZERO = dict(ZERO_ENEMY,
                 art_entry=17, art_timer=6, scroll_xq=580, scroll_yq=802)
BUSTER_ZERO = dict(ZERO_ENEMY,
                   art_entry=10, art_timer=0, scroll_xq=480, scroll_yq=752)
CHIPUSE_ZERO = dict(ZERO_ENEMY_WITH_HAND,
                    art_entry=13, art_timer=3, scroll_xq=522, scroll_yq=773)

DELETE_ENEMY = ("0x0203ab84:0", "0x0203ab86:0")


def _zero_enemy_canon(script: str, pokes_at: Tuple[str, ...] = (),
                      zero: Tuple[str, ...] = ()) -> Callable[[str], Side]:
    def make(ui: str) -> Side:
        return Side(rom=STERILE, loadstate=PAUSED, cheats=DELETE_ENEMY,
                    script=script, pokes_at=pokes_at, zero=zero,
                    extra=() if ui == "integrated" else ("--disable-bg",))
    return make


def _zero_enemy_rust(script: Optional[str] = None,
                     desc: Optional[dict] = None) -> Callable[[str], Side]:
    def make(ui: str) -> Side:
        return Side(rom=plain_rom(), fixture=ZERO_ENEMY if desc is None else desc,
                    script=script,
                    extra=() if ui == "integrated" else ("--disable-bg",))
    return make


def held(key: str, first: int, n: int) -> str:
    """A key script that holds `key` for `n` frames from `first` --
    regress.py's own helper (unchanged; regress.py itself is not edited)."""
    return ",".join("%s@%d" % (key, first + j) for j in range(n))


#: demo-open's row, fixture.rs's table -- battlestart.state was lost, so this
#: could not be re-verified byte-identical against the feature build; kept
#: otherwise exactly as fixture.rs's own table records it. RE-POINTED AT R1's
#: REBUILT battlestart.state (TODO F4, 2026-09-12): the rebuilt state has the
#: same three Mettaurs but a different history, and two peeked initial
#: conditions changed with it --
#:   megaman_hp: canon's navi holds 0x0064 at 0x0203a9d4 (object +0x24) in the
#:     rebuilt state (--peek at load reads 0 while the intro has not populated
#:     the object; a 200-frame capture's --dump reads 0x0064, matching the
#:     "100" drawn in the HP box). The old 60 was peeked from the LOST state
#:     (TODO A6) and was the whole of the isolated row's 1160 px: 29 px of HP
#:     digits (x 19..30, y 3..12) on every one of the 40 frames.
#:   rng: ePrimaryRngSeed (0x020013f0) reads 0x14ca0f46 at the rebuilt state's
#:     frame 0 (--peek at load; the old state's value is unrecoverable).
#:     fixture_cheats() now delivers +58 (src/fixture.rs has read it since the
#:     wave 3d ticket); without it the integrated variant's viruses materialize
#:     on our default seed instead of canon's history.
#: Marker origin 8 (measured live for demo-open), same family as demo-field.
OPEN_ROW = dict(enemies=3, enemy_kind=0, enemy_col=4, enemy_row=1,
                megaman_hp=100,  # provenance: peeked -- canon 0x0064 at 0x0203a9d4, R1's rebuilt battlestart.state (TODO F4); 60 was peeked from the lost state
                megaman_col=2, megaman_row=2, hand=[], hand_count=0, gauge=0,
                flags=0x01,
                rng=0x14CA0F46,  # provenance: peeked -- ePrimaryRngSeed 0x020013f0 at frame 0, --peek at load from R1's rebuilt battlestart.state (TODO F4)
                # F38h: per-slot panel-cell triple from the real ROM's
                # EnemySetup record 0x080b5354 (the roll picked at frame 60
                # of the battlestart recipe, --peeked byte 1 of each slot
                # decode: low 3 bits = panel_x, bits 4-6 = panel_y --
                # spawnEnemy_80073E2 asm00_1.s:8695). mask=0x07 turns the
                # override on for all three slots; every other descriptor's
                # default mask=0 leaves the diagonal (enemy_col+i,
                # enemy_row+i) in place.
                #   slot 0: panel_x=5, panel_y=1
                #   slot 1: panel_x=5, panel_y=3
                #   slot 2: panel_x=6, panel_y=2
                panel_col=[5, 5, 6],  # provenance: derived -- battlestart.state EnemySetup record 0x080b5354, slot bytes 0x15/0x35/0x26, low-3-bits panel_x, spawnEnemy_80073E2 asm00_1.s:8695
                panel_row=[1, 3, 2],  # provenance: derived -- same record, panel_y = (byte >> 4) & 0x7, asm00_1.s:8695
                panel_override_mask=0x07)  # provenance: derived -- F38h: 0x07 = all three slots use the override (1<<0 | 1<<1 | 1<<2)
OPEN_ORIGIN = 8

#: demo-field's row, fixture.rs's table -- VERIFIED BYTE-IDENTICAL there.
#: enemy_hp: 0xFFFF here is not "use the default" (see fixture_cheats()'s
#: comment on that sentinel mismatch) -- it is the LITERAL value
#: demo-field's own Rust source bakes in (FIELDMATCH_HP) and what the real
#: capture's `--cheat 0x0203ab84/86:0xffff` (ALIVE, below) pins the real
#: Mettaur's HP to: a huge number that is never going to reach 0, not a
#: sentinel. Marker origin 8 (measured live), same family as demo-open.
FIELD_ROW = dict(enemies=1, enemy_kind=0, enemy_col=5, enemy_row=2, megaman_hp=60,  # provenance: peeked -- canon live HP 0x003c at 0x0203a9d4 (+0x24 of the object at eT1BattleObject0, peeked from PAUSED via --peek, F1 step 2; the oracle's info-only mm_hp agrees). 100 put MegaMan's HP at a value canon never holds in this battle. HP is game input (damage, death, healing, the HUD counter and the oracle all read it); it is pixel-neutral in these BG2-only/OBJ-only rows, measured -- wave and mettaur unchanged.
                 megaman_col=2, megaman_row=2, hand=[1], hand_count=1, gauge=0,
                 flags=0x11, art_entry=5, art_timer=4, scroll_xq=424, scroll_yq=724,
                 enemy_hp=0xFFFF)
FIELD_ORIGIN = 8

#: T9h (2026-09-15): the Gunner scenario's rust descriptor. The Mettaur+Gunner
#: record (T9b's frame-60 iCurrFrame lever, T9c's recipe: battlestart + a
#: one-shot poke of 0x0200a210:0x371 at frame 60) populates slot 0 with a
#: Mettaur (NameID 0x0001, HP 0x0028, panel (5,2)) and slot 1 with a Gunner
#: (NameID 0x0085, HP 0x003c, panel (6,3)). For the gunner harness row we
#: pin enemies=2 with enemy_kind bits (0=Mettaur slot 0, 1=Gunner slot 1);
#: the kind byte packs 0x01 << 0 | 0x01 << 2 = 0x05, and src/fixture.rs's
#: kind_of() shifts those bits back out (T9c, fixture.rs:248-264).
#: enemy_kind byte pack: 0x05 = slot0 Mettaur | slot1 Gunner (kinds 0,1).
#: enemy_hp 0xFFFF = use src/fixture.rs's per-kind default (KIND_METTAUR=40,
#: KIND_GUNNER=60, the values the poked record carries live at slot init).
#: art_entry/art_timer/scroll_xq/scroll_yq are this row's own, derived (T9l,
#: 2026-09-15) from canon's own counters on this row's canon capture
#: (probe.py watch, REAL + battlestart_gunner.state, the row's own Side):
#: at canon_ref=80 eBGScrollCBCounters read -640/-320 = -8*80/-4*80, so the
#: battle frame f = 80 (capture frame 0 reads -8/-4, i.e. f0 = 1, and the
#: counters freeze for one capture frame at 67/68 -- net f = 80 at canon
#: frame 80); eGFXAnimStates[0] reads entry 15 / Timer 7 (LoopAddress
#: 0x0807fba4, CommandPos 0x0807fc1c) = schedule position 80+8-7 = 81.
#: With the row's offset 25 and ORIGIN 8: nx = 8+25-7 = 26, na = 8+25-5 = 28,
#: scroll_xq = (2*80 - 2*26) mod 1024 = 108, scroll_yq = (80 - 26) mod 1024
#: = 54, art position (81 - 28 + 1) mod 192 = 54 = entry 11 / Timer 2
#: (S(11) = 48, STEP_HOLD[11] = 8, Timer = 48+8-54 = 2). The old values here
#: were FIELD_ROW's borrowed seeds (5/4/424/724, "the backdrop's phase
#: matches mettaur at the same battle frame") -- never derived for this row.
GUNNER_ROW = dict(enemies=2, enemy_kind=0x05, enemy_col=5, enemy_row=2, megaman_hp=60,
                  megaman_col=2, megaman_row=2, hand=[1], hand_count=1, gauge=0,
                  flags=0x11, art_entry=11, art_timer=2, scroll_xq=108, scroll_yq=54,  # provenance: peeked -- canon's own counters at this row's canon_ref
                  enemy_hp=0xFFFF)
GUNNER_ORIGIN = 8

#: T9h (2026-09-15): canon-side state for the gunner row. Re-uses T9c's
#: battlestart_gunner.state (built by states.py from overworld_net.state +
#: battlestart's pokes + the iCurrFrame lever) -- the BattleSettings record
#: 6 (0x080b4bd8) the lever picks has a Mettaur in slot 0 and a Gunner in
#: slot 1, exactly what GUNNER_ROW asks for on the rust side. Named
#: distinctly from any local alias a future check might add.
BATTLESTART_GUNNER = "/tmp/battlestart_gunner.state"

#: demo-custmatch's row (demo-cardname is a feature alias, not a different
#: descriptor -- fixture.rs's table). The offered deck is NOT expressible
#: now read by src/fixture.rs (see its own table's "WAVE 3 ADDITIONS" and
#: "WAVE 3 VERIFICATION" comments -- 371/862px residual on 2 of 200 frames,
#: in the card-picture region, not from the deck/window fields themselves;
#: zero-src's own ticket). window_cursor=0xa (OK) matches demo-custmatch's
#: own capture. Marker origin 8 (measured live).
#: megaman_col/row are canon's own, peeked from /tmp/chipselect.state's
#: MegaMan BattleObject (0x0203a9b0, PanelX/PanelY at +0x12/+0x13 =
#: 0x0203a9c2/0x0203a9c3) via tools/oracle.py windowclose, which read
#: mm_panel_x canon 2 / rust 3 and mm_panel_y canon 3 / rust 2 diverging on
#: all 40 compared frames -- the same class F20b fixed for HUDMATCH. Measured
#: (F29): windowclose 648948/27391/40 -> 612328/26551/40, its OBJ layer
#: 97644 -> 46803, and `cursor` EXACTLY unchanged at 620802/6884/170 (the
#: window covers him for all 170 of its frames), `window`/`card` still 0.
CUSTMATCH_ROW = dict(enemies=1, enemy_kind=0, enemy_col=5, enemy_row=3, megaman_hp=100,
                     megaman_col=2, megaman_row=3, hand=[], hand_count=0, gauge=1,
                     flags=0x11,
                     deck_count=5, deck=[5, 4, 71, 54, 1],
                     deck_codes=[3, 0xFF, 18, 0xFF, 0xFF],
                     window_pick_count=1, window_pick_slot=4, window_cursor=0xa)
CUSTMATCH_ORIGIN = 8

#: F26b (2026-09-13): the backdrop-phase seeds for the two CUSTMATCH_ROW rows
#: that compare the WHOLE screen. `window`/`card` isolate BG3 and never see
#: BG1, so CUSTMATCH_ROW itself stays unseeded; `cursor` and `windowclose`
#: pair DIFFERENT canon frames of the same CHIPSELECT battle (canon 15 vs
#: canon 81) with different rust frames, so one shared seed cannot serve both
#: -- each carries its own, derived from canon's own counters at its own
#: canon_ref, never fitted.
#:
#: THE SCROLL. canon's BGScrollCB_BG1Diagonal3to2Scroll
#: (reference/bn6f/asm/asm00_0.s:3287-3303) subtracts 8 from Counter0 and 4
#: from Counter1 (eBGScrollCBCounters, 0x02009690/0x02009694), `lsr #4` each,
#: and strh's them into RenderInfo Unk_10/Unk_12 (BG1HOFS/BG1VOFS). Both
#: counters are zeroed once at battle init (sub_8080D90/sub_8080DA0,
#: asm00_1.s:8434-8435), so at battle frame f they read exactly -8f/-4f --
#: measured on this row's own canon capture (--watch 0x02009690:4
#: 0x02009694:4 over CHIPSELECT + this row's script): canon frame 0 reads
#: 0xffff9d60/0xffffceb0 = -25248/-12624 = -8*3156/-4*3156, and every later
#: frame is one more step of -8/-4, so CHIPSELECT sits at battle frame
#: f0 = 3156 and canon frame c is battle frame 3156+c. src/backdrop.rs keeps
#: the same phase in quarter-pixels (x_q += 2, y_q += 1 per frame) and emits
#: -((q+3)/4), i.e. floor(-q/4) -- the same value canon's `lsr #4` of a
#: falling counter produces -- so canon's phase in our units is
#: x_q = 2f mod 1024, y_q = f mod 1024 (1024 = 256 px x 4).
#:
#: THE ART. eGFXAnimStates[0] (0x020094c0, GFXAnimState.inc: Timer +2,
#: LoopAddress +4, CommandPos +8) walks src/backdrop.rs's STEP_ORDER/
#: STEP_HOLD schedule (off_807FB98, dat20.s:140-172), 29 entries, 192 frames
#: a cycle. Entry index = (CommandPos - LoopAddress)/8; position in the cycle
#: = sum(STEP_HOLD[:entry]) + STEP_HOLD[entry] - Timer, and it advances by
#: exactly 1 per frame on both sides. Watched on canon: frame 15 = entry 17 /
#: Timer 4 (CommandPos 0x0807fc2c) = position 100; frame 81 = entry 25 /
#: Timer 2 (0x0807fc6c) = position 166.
#:
#: THE ROW'S OWN OFFSET, AND THE TWO PIPELINE LEADS. Our Backdrop is built
#: once, before the first `Battle::update`, and ticks once per frame from
#: there. Watched live on this row's own rust capture (a temporary write of
#: entry/timer/x_q/y_q to the scratch halfwords at 0x02000030, between R7's
#: oracle block and this descriptor -- F26b, since removed) the tick count in
#: RAM at capture frame R is n_ram = R - 6, and the marker's "BATT" first
#: appears at capture frame 8 = the SECOND tick (main.rs's `clocks_visible`
#: gate), which is where ORIGIN 8 comes from. What a frame SHOWS is not what
#: its RAM holds, and the two clocks do not even agree with each other: our
#: scroll is a register written by `commit()` at the following vblank, while
#: our art is a `replace_tile` VRAM write inside `update()`. MEASURED on
#: windowclose by sweeping each clock one tick at a time with the other held
#: (BG1-only, both sides --only-bg 1, this row's own frames):
#:   pixels at capture frame R show the scroll of tick R - 7
#:   pixels at capture frame R show the art    of tick R - 5
#: (with the art held, scroll_xq/yq 844/934 -- the seed the RAM tick count
#: alone predicts -- reads 142518 nonzero on all 20 even k and 0 on all 20
#: odd k, the exact signature of a half-pixel x error, and 846/935 reads
#: 11153 on 7 frames; with the scroll held at 846/935, art entry 17 Timer 1
#: reads 0 where Timer 0 and Timer 2 both read 11153 and Timer 3 reads
#: 21150.) So with
#: nx = ORIGIN + offset - 7 and na = ORIGIN + offset - 5, and `Backdrop::seed`
#: applying at tick 0 while adding its own documented one-tick construction
#: lead to the art timer (the fields therefore carry the state at tick 1):
#:   scroll_xq = (2*(f0+canon_ref) - 2*nx) mod 1024
#:   scroll_yq = (   f0+canon_ref  -   nx) mod 1024
#:   art position of the (art_entry, art_timer) pair
#:             = (canon position at canon_ref - na + 1) mod 192
#: cursor      canon_ref 15: f=3171, x = 6342 mod 1024 = 198, y = 99;
#:             nx = 8+237-7 = 238: 198-476 = -278 -> 746, 99-238 = -139 -> 885
#:             na = 240: (100-240+1) mod 192 = 53 = entry 11 / Timer 3.
#: windowclose canon_ref 81: f=3237, x = 6474 mod 1024 = 330, y = 165;
#:             nx = 8+253-7 = 254: 330-508 = -178 -> 846, 165-254 = -89 -> 935
#:             na = 256: (166-256+1) mod 192 = 103 = entry 17 / Timer 1.
#: The two leads were measured ONCE, on windowclose, and then PREDICTED
#: cursor: with no further tuning cursor's BG1 went 2214975/15746/170 -> 2/2/
#: 170 (one frame, two pixels -- canon's own mid-frame tile transfer, see the
#: cursor row's note). windowclose's BG1 went 877602/22658/40 -> 0/0/40.
#: provenance: peeked -- canon's own eBGScrollCBCounters/eGFXAnimStates[0] on
#: each row's own canon capture, mapped through the arithmetic above.
CURSOR_ROW = dict(CUSTMATCH_ROW, art_entry=11, art_timer=3, scroll_xq=746, scroll_yq=885,
                    enemy_state=4, enemy_action=0x0b)  # provenance: peeked -- canon 0x0203ab68 reads 0x0b04 at frame 15 of this row's own CHIPSELECT+cursor-walk capture (and every 10th frame 10..90: frozen under BattlePaused)
WINDOWCLOSE_ROW = dict(CUSTMATCH_ROW, art_entry=17, art_timer=1, scroll_xq=846, scroll_yq=935,
                        enemy_state=4, enemy_action=0x0b)  # provenance: peeked -- canon 0x0203ab68 reads 0x0b04 at frame 81 of this row's own CHIPSELECT+Start,A capture (anim 0x0101 both rows: SWING's own pose)

#: demo-cardname's row -- IDENTICAL to CUSTMATCH_ROW in every column except
#: window_cursor (0 = cursor on the first slot, showing the card's NAME
#: rather than the OK confirmation message -- fixture.rs's own table
#: comment; `card` below is demo-cardname's check, `window` is
#: demo-custmatch's).
CARDNAME_ROW = dict(CUSTMATCH_ROW, window_cursor=0)

#: `window`/`card` isolated variants: CUSTMATCH_ROW/CARDNAME_ROW with
#: SceneFlags::BLANK_HUD|SceneFlags::BLANK_BACKDROP added on top of their own
#: SceneFlags::OPEN_WINDOW|SceneFlags::SKIP_INTRO (0x11 | 0x06 = 0x17), so nothing but
#: the window itself renders on the rust side -- the full-screen match for
#: canon's --only-bg 3 (see the `window` Check's own note).
ISOLATED_CUSTMATCH_ROW = dict(CUSTMATCH_ROW, flags=0x17)
ISOLATED_CARDNAME_ROW = dict(CARDNAME_ROW, flags=0x17)

#: demo-resultmatch's row: start_state/result_level/result_frames/
#: result_zenny now read by src/fixture.rs (verified byte-identical there,
#: 0px over 200 frames). Marker origin 8 (measured live).
RESULTMATCH_ROW = dict(enemies=1, enemy_kind=0, enemy_col=5, enemy_row=3, megaman_hp=60,
                       megaman_col=3, megaman_row=2, hand=[], hand_count=0, gauge=0,
                       flags=0x11,
                       start_state=1, result_level=2, result_frames=1760, result_zenny=100)
RESULTMATCH_ORIGIN = 8

#: `result`'s own row (AUDIT wave 3c "zero-enemy" ticket, FIXTURE.md +56):
#: RESULTMATCH_ROW plus result_elapsed, aimed at RESULT_ARRIVAL's own
#: measured slide-in start rather than at demo-resultmatch's "long settled"
#: endpoint. result_elapsed=0 ("the slide-in starts on the first battle
#: frame" -- FIXTURE.md) is kept: it is the simplest legal value and the one
#: this ticket can actually reason about without live measurement (see
#: below), so the alignment moves canon_ref instead of tuning this field.
#: RESULTMATCH_ROW plus result_elapsed, aimed at RESULT_ARRIVAL's own
#: measured slide-in start rather than at demo-resultmatch's "long settled"
#: endpoint. result_elapsed=0 ("the slide-in starts on the first battle
#: frame" -- FIXTURE.md) is kept: it is the simplest legal value and the one
#: this ticket can actually reason about without live measurement (see
#: below), so the alignment moves canon_ref instead of tuning this field.
#: F21b: the backdrop tail seed. RESULT_ARRIVAL is captured mid-battle, so
#: its ambient backdrop clocks are mid-cycle: eGFXAnimStates[0] reads entry
#: 24 (CommandPos 0x0807fc64 against LoopAddress 0x0807fba4, 8 bytes an
#: entry), Timer 4, Param0 0x08617488 (this build's own blob -- the same
#: schedule); eBGScrollCBCounters reads 0x0528/0x8294 after frame 0.
#: F34 DERIVES these four from canon's own counters at this row's canon_ref,
#: exactly the way F26b derived CURSOR_ROW's and WINDOWCLOSE_ROW's (the
#: mechanism, the ROM citations and the two pipeline lags are in their comment
#: above; F21b's peeked art pair 24/Timer 4 and its 692/858 were the load-time
#: reading and a hand-mapped scroll, and F34's first pass moved the timer to 6
#: by frame-to-frame measurement -- this is where both numbers come from).
#: WATCHED on canon's own capture of this row (tools/probe.py watch
#: /tmp/bn6f_real.gba 30 0x02009690:4 0x02009694:4 0x020094c2:2 0x020094c8:4
#: --loadstate /tmp/result_arrival.state), at canon frame 21:
#:   eBGScrollCBCounters (ewram eBGScrollCBCounters, 0x02009690/0x02009694)
#:     = 0xffff0480 / 0xffff8240 = -64384 / -32192, and the counters are
#:     zeroed at battle init and fall by 8/4 a frame
#:     (BGScrollCB_BG1Diagonal3to2Scroll, asm00_0.s:3287-3303; sub_8080D90/DA0,
#:     asm00_1.s:8434-8435), so they read -8f/-4f at battle frame f = 8048
#:     -> canon's phase in our units: x_q = 2f mod 1024 = 736, y_q = f mod
#:     1024 = 880.
#:   eGFXAnimStates[0] (0x020094c0): CommandPos 0x0807fc7c - LoopAddress
#:     0x0807fba4 = 0xd8, 8 bytes an entry -> entry 27, Timer 7
#:     (GFXAnimState.inc: Timer +0x2, LoopAddress +0x4, CommandPos +0x8)
#:     -> art position 176 + (8 - 7) = 177 of the 192-frame
#:     STEP_ORDER/STEP_HOLD schedule (10 entries of 4 then 19 of 8).
#: THE LAG IS ANCHORED ON THE MARKER, NOT ON THE RAW CAPTURE FRAME. F26b
#: measured "capture frame R shows the scroll of tick R-7 and the art of tick
#: R-5" on two rows whose marker origin is 8; THIS row's origin is 13
#: (find_marker_origin, the same 13 on every capture taken for it), and the
#: tick a frame shows is origin-relative -- scroll tick = R - origin + 1, art
#: tick = R - origin + 3, which IS F26b's -7/-5 at origin 8, and the two rows
#: it was measured on cannot tell the two forms apart. With this row's own
#: offset 21 (canon 21+k <-> rust 34+k) that is nx = 22 and na = 24:
#:   scroll_xq = (736 - 2*22) mod 1024 = 692
#:   scroll_yq = (880 -   22) mod 1024 = 858
#:   art pair  = (177 - 24 + 1) mod 192 = 154 = entry 24 / Timer 6
#: MEASURED, backdrop layer alone (our BG0 against canon's BG1, --only-bg on
#: both sides, this row's own 40 frames at offset 21): 0 differing pixels on
#: every frame, and the minimum is unique and sharp -- one tick either way
#: reads 146948 (nx 21 / na 23 = 694/859, Timer 5) and 146362 (nx 23 / na 25
#: = 690/857, Timer 7), and reading F26b's lags as absolute capture frames
#: (nx 27 / na 29 = 682/853, entry 23 / Timer 3) reads 387793.
#: provenance: peeked -- canon's own eBGScrollCBCounters/eGFXAnimStates[0] on
#: this row's own canon capture, mapped through the arithmetic above.
RESULT_ROW = dict(RESULTMATCH_ROW, result_elapsed=0,
                  # F34b: canon's BattleObject 0x0203a9b0+0x12 PanelX reads 2 on every
                  # frame of this row's canon capture (BattleObject.inc:63; megaman_row 2
                  # already right). provenance: peeked -- canon PanelX.
                  megaman_col=2,
                  # F34b: canon's enemy slot 0x0203aa88 sits in CUR_STATE_DESTROY 0x08
                  # at the row's canon_ref (BattleObject.inc:38) -- the Mettaur is already
                  # deleted when the RESULT window comes up. provenance: peeked -- canon CurState.
                  enemies=0,
                  art_entry=24, art_timer=6, scroll_xq=692, scroll_yq=858)

#: demo-banner's row. banner_at is NOT expressible yet (FIXTURE.md +46, not
#: read -- pending_src). Marker origin 1 (measured live -- blanks HUD and
#: backdrop, same family as the chip scoreboard).
BANNER_ROW = dict(enemies=0, megaman_hp=100, megaman_col=2, megaman_row=2, hand=[],
                  hand_count=0, gauge=0, flags=0x17, banner_at=100)
BANNER_ORIGIN = 1

CHIPSELECT = "/tmp/chipselect.state"
NOENEMY = "/tmp/noenemy2.state"
RESULT_ARRIVAL = "/tmp/result_arrival.state"
#: regress.py's cursor walk script, reused verbatim (real side unchanged by
#: this ticket).
_CURSOR_WALK_REAL = ",".join(held("Left", 20 + 30 * k, 6) for k in range(5))
_CURSOR_WALK_RUST = ",".join(held("Left", 250 + 30 * k, 6) for k in range(5))

#: TODO F9 (2026-09-12): the banner row's canon side blanks the deleted enemy's
#: dissolve with ENEMY_TILES (0x060103E0:448, the Mettaur's own 14 object tiles)
#: PLUS this tail: the corpse's dissolve re-upload is 768 BYTES at the same base
#: (measured: queue slot src=0x0839A610 dst=0x060103E0 size=768, canon frame 49),
#: i.e. it also covers tiles 45..54, which the Mettaur's live sprite never used --
#: so 0x060105A0:320 is dissolve-sheet territory alone (peeked from the GFX
#: transfer queue, not from any OAM). Blank on canon per frame; the rust fixture
#: has no enemy and the row's subject (BANNER_TILES 0x06016E00) is disjoint.
ENEMY_DISSOLVE_TAIL = "0x60105A0:320"

#: F28b (2026-09-13): the two blanks above stop at tile 0x36 and the dissolve's
#: FIRST phase does not. Watching canon's OAM (0x07000000:1024, this row's own
#: side plus --watch) over the compared window shows the corpse drawn from
#: object tiles 0x01f, 0x023, 0x02b, 0x02d, 0x02f and 0x033 -- all inside the
#: 768 bytes above -- AND from 0x03d, 0x041 and 0x045, whose shapes/sizes
#: (tall 8x32 = 4 tiles, wide 32x16 = 8 tiles) reach tile 0x048: a second sheet
#: region, above everything F9 blanked, which is the whole of popup's leftover
#: 5094 px on canon frames 43..49 (k=0..6, bbox (149,81)-(196,126), canon
#: colour over our black on every one of them; k>=7 was already 0). Tiles
#: 0x37..0x48 = 0x060106E0 + 576 bytes. Nothing else uses them where it
#: matters: over the row's whole 130-frame canon capture the only objects
#: drawn from tiles 0x2d..0x49 inside the compared window (canon 43..122) are
#: these, at x 149..189; the other users (x=4 at frames 0..15, x 137..185 at
#: frames 15..36) are all before canon_ref. Popup only -- `banner` keeps F9's
#: pair unchanged, and reads 0 with them.
ENEMY_DISSOLVE_FIRST_PHASE = "0x60106E0:576"

#: F28b (2026-09-13): and the three frames a per-frame --zero can never win,
#: for the reason F9 already wrote down -- the queue is flushed in the frame's
#: OWN vblank, after that frame's zero has run. Watched live on this row's own
#: canon side (--watch 0x0200B4B0:1024, the transfer queue itself, one row per
#: frame): the dissolve's uploads are queued in slot 3 at canon frames 44
#: (src 0x0839A28C -> 0x060105A0, 896 bytes), 45 (the same source -> 0x060103E0)
#: and 48 (src 0x0839A610 -> 0x060103E0, 768 -- F9's own entry), landing on 45,
#: 46 and 49, which are exactly the k=2, k=3 and k=6 that survived the tile
#: blanking (1148, 1148, 562). NOTE the slot: F9 measured this upload in slot
#: 41 and ENEMY_DISSOLVE_SLOT_SIZE still pokes 0x0200B7EC for it; on this row
#: today it is slot 3, so that poke is a no-op here (it is left alone for
#: `banner`, which reads 0 with it). Size word of slot 3 =
#: fiveWordArr200B4B0 + 3*0x14 + 8 = 0x0200B4F4; zeroing its low half is the
#: whole size (896 = 0x380, 768 = 0x300), so CopyWords copies nothing.
ENEMY_DISSOLVE_QUEUE_KILL = (
    "45:0x0200B4F4:0x0000",
    "46:0x0200B4F4:0x0000",
    "49:0x0200B4F4:0x0000",
)

#: TODO F9 (2026-09-12): the per-frame --zero cannot blank canon frame 49 itself:
#: the dissolve sheet's queue entry (queued during frame 48) is FLUSHED by
#: ProcessGFXTransferQueue during frame 49's own vblank -- after that frame's zero
#: has run -- so the corpse still renders on frame 49 (the leftover 562 px). The
#: entry itself is killed instead: one-shot --poke-at 49 zeroes the SIZE word of
#: queue slot 41 (fiveWordArr200B4B0 + 41*0x14 + 8 = 0x0200B7EC, measured live:
#: that slot's dest word 0x0200B7E8 was written new=0x060103E0 at frame 48) before
#: the flush, so CopyWords copies 0 bytes and the upload never lands. Slot 41 only:
#: the banner text rides queue slots 0..40 (dests 0x06016E00..0x060172E0, watched
#: live) and entries 42/43 are a BG copy and an IWRAM copy -- none touched. The
#: F5b one-shot-poke pattern, applied to a canon Side's fixture machinery.
ENEMY_DISSOLVE_SLOT_SIZE = "49:0x0200B7EC:0x0000"

PORTED_CHECKS: List[Check] = [
    _tiles_gauge("tiles", "regress.py's `tiles`: backgrounds below the HUD"),
    _tiles_gauge("gauge", "regress.py's `gauge`: the HUD strip, TODO A8's stripe-flow defect"),
    Check(
        name="field",
        ui="both",
        frames=40,
        align=Align(
            canon_ref=130,
            search=range(60, 110),
            note="AUDIT pair 3: an empty arena, not the old ALIVE-mettaur setup (an enemy "
                 "acting on an RNG the two sides do not share -- exactly what pair 3 calls "
                 "out). canon_ref=130: the enemy is DELETED, not hidden (see DELETE_ENEMY's "
                 "comment above for why), and 130 is comfortably past frame 110, verified live "
                 "as the last frame with any dissolve OAM at all. rust: marker origin 8 plus a "
                 "wide band -- the picture is static once settled, so a wide band costs "
                 "nothing and does not need a sharp-minimum argument the way a moving subject "
                 "does. frames=40, not 20: the idle navi's own pose settles once more around "
                 "canon frame 164 (k=34) -- a genuine one-time transition, not periodic -- and "
                 "pair 10's negative fixture is BLIND without it in the window (a fully frozen "
                 "40-frame stretch cannot tell a 1-frame canon shift from no shift at all). "
                 "TODO F8 (2026-09-12): the k=34 transition is NOT the navi -- it is canon's "
                 "RESULT window arriving: the canon side's deleted-enemy battle resolves "
                 "(banner sequencer 0x08->0x0C at canon 47, ENEMY DELETED banner canon "
                 "49..106, RESULT window BG3 slide-in canon ~154..167, mark OBJ entering "
                 "canon 163..166), so the rust side now carries SceneFlags::RESOLVE_OVER and "
                 "resolves on the same schedule (banner at battle 0 = capture 8, mark at "
                 "capture ~121). The pairing is therefore by measured EVENT, not only by "
                 "static score: the banner start (canon 49 <-> rust capture 8) and the mark's "
                 "first wrapped frame (canon 163 <-> rust ~121) both give offset ~81, inside "
                 "the unchanged band; F33c measured the search minimum at the band's top "
                 "edge (108) riding slope + stall (566712 at 81), so the offset stays "
                 "event-locked by the mark, never by score; the static field "
                 "alone cannot discriminate offsets, the mark event can.",
        ),
        rust=lambda ui: Side(rom=plain_rom(), fixture=FIELD_ZERO, script="Start@10",
                             extra=() if ui == "integrated" else ("--disable-bg",)),
        canon=_zero_enemy_canon("Start@10"),
        canon_variant="canon (sterile)",
    ),
    # F45 (2026-09-16): three post-boundary per-layer attribution rows for the `field`
    # integrated residue (158935/5606/40). NEW ROWS ONLY -- the `field` row above is
    # untouched. Why the split exists: from rust capture 121 (= battle 110, k=5) self.shown
    # is Some and battle.rs:4546-4549 skips filler_bg, so every layer drops one hardware BG
    # (backdrop BG1->BG0, panels BG2->BG1, HUD BG3->BG2, shown->BG3) while canon's own
    # RESULT window has not started (canon ~154). Past that boundary same content therefore
    # pairs canon BG N with rust BG N-1 (the .show() order at src/battle.rs:4536-4549); at
    # or before it, the SAME index N on both sides is the same-content pairing (that is
    # what the `field` row's own note means by the stall at captures 118-120). Each row
    # proves one thing only: whether the k>=5 bulk of field's 158935 px lives in the layer
    # it isolates. A frame whose differing-pixel mask covers more than 75% of the 240x160
    # screen is a full-screen render, not a layer mask (the measured gap sits between 28.9%
    # and 92.5%, docs/recon/F45.md section 3), and is rejected in
    # docs/coverage/field_integrated.md -- no number from a rejected frame is quoted there.
    Check(
        name="field-bg1",
        ui="isolated",
        frames=40,
        align=Align(
            # canon: the `field` row's own canon_ref 130 + the 5 pre-boundary frames
            canon_ref=135,
            # canon: the `field` row's own event-locked offset 108 + the same 5 frames
            rust_offset=113,
            search=None,
            note="F45 post-boundary backdrop attribution: canon --only-bg 1 (backdrop) vs "
                 "rust --only-bg 0, because rust capture 121 = k=5 is where the hardware "
                 "layers renumber (self.shown Some, filler_bg skipped, src/battle.rs:4546-4549). "
                 "Band: canon_ref=135 and rust_offset=113 are the `field` row's own "
                 "event-locked pairing (mark's first wrapped frame) moved past the 5 "
                 "pre-boundary frames -- search=None because a pairing already argued by "
                 "event must not be re-picked by score (F2's rule). Proves whether the "
                 "k>=5 bulk of field's 158935 px lives in the backdrop layer; frames with "
                 ">75% mask coverage are rejected (full-screen render, not a layer mask) -- the cap is applied BY HAND in docs/coverage/field_integrated.md, the harness does not enforce it; a stronger mask-row guard (mask_diff AND integ_equal AND not_in_occluder == 0) is left for a later ticket (F46/F47).",
        ),
        rust=lambda ui: Side(rom=plain_rom(), fixture=FIELD_ZERO, script="Start@10",
                             extra=("--only-bg", "0")),
        canon=lambda ui: Side(rom=STERILE, loadstate=PAUSED, cheats=DELETE_ENEMY,
                              script="Start@10", extra=("--only-bg", "1")),
        canon_variant="canon (sterile)",
    ),
    Check(
        name="field-bg2",
        ui="isolated",
        frames=40,
        align=Align(
            # canon: the `field` row's own canon_ref 130 + the 5 pre-boundary frames
            canon_ref=135,
            # canon: the `field` row's own event-locked offset 108 + the same 5 frames
            rust_offset=113,
            search=None,
            note="F45 post-boundary field-panels attribution: canon --only-bg 2 (panels) vs "
                 "rust --only-bg 1, same renumbering boundary as field-bg1 (rust capture 121 "
                 "= k=5, self.shown Some). Band identical to field-bg1's (event-locked, not "
                 "scored). Proves whether the k>=5 bulk of field's 158935 px lives in the "
                 "field-panels layer; frames with >75% mask coverage are rejected -- the cap is applied BY HAND in docs/coverage/field_integrated.md, the harness does not enforce it",
        ),
        rust=lambda ui: Side(rom=plain_rom(), fixture=FIELD_ZERO, script="Start@10",
                             extra=("--only-bg", "1")),
        canon=lambda ui: Side(rom=STERILE, loadstate=PAUSED, cheats=DELETE_ENEMY,
                              script="Start@10", extra=("--only-bg", "2")),
        canon_variant="canon (sterile)",
    ),
    Check(
        name="field-bg3",
        ui="isolated",
        frames=40,
        align=Align(
            # canon: the `field` row's own canon_ref 130 + the 5 pre-boundary frames
            canon_ref=135,
            # canon: the `field` row's own event-locked offset 108 + the same 5 frames
            rust_offset=113,
            search=None,
            note="F45 post-boundary HUD attribution: canon --only-bg 3 (HUD) vs rust "
                 "--only-bg 2, same renumbering boundary as field-bg1 (rust capture 121 = "
                 "k=5, self.shown Some). Weakest pairing of the three: rust's BG3 is the "
                 "`shown` RESULT background from capture 121 while canon's BG3 is the HUD, "
                 "and canon's own RESULT slide-in does not start until canon ~154 (k=24 of "
                 "this window) -- so this row proves HUD parity, NOT the `shown` layer, and "
                 "a large reading here is expected to be the shown-vs-HUD mismatch, not a "
                 "HUD defect. Frames with >75% mask coverage are rejected -- the cap is applied BY HAND in docs/coverage/field_integrated.md, the harness does not enforce it",
        ),
        rust=lambda ui: Side(rom=plain_rom(), fixture=FIELD_ZERO, script="Start@10",
                             extra=("--only-bg", "2")),
        canon=lambda ui: Side(rom=STERILE, loadstate=PAUSED, cheats=DELETE_ENEMY,
                              script="Start@10", extra=("--only-bg", "3")),
        canon_variant="canon (sterile)",
    ),
    Check(
        name="warp",
        ui="both",
        frames=30,
        align=Align(
            canon_ref=130,
            rust_offset=51,
            note="canon: Right/Down held 3 frames each starting real 130 (past the "
                 "DELETE dissolve, see `field`'s note), canon_ref=130 = the first "
                 "press; Left@170/Up@190 of the old script sat outside BOTH sides' "
                 "compared windows (rust's own Left/Up at battle 90/110 land at "
                 "capture 98/118, past window end) and their pokes never fire in the "
                 "165-frame canon capture, so they are dropped rather than carried "
                 "as dead code. F11 (2026-09-13): the old script presses were INERT "
                 "-- sequencer 0x0C (entered canon 47, F10's delivery wall) never "
                 "refreshes AIData from the joypad mirror, so canon's MegaMan never "
                 "moved (pixel centroid constant x=61 through the whole old window) "
                 "and the row compared our warp against a static sprite; its negative "
                 "read exactly the nominal 9198 because the static picture is 1-frame "
                 "shift-invariant, and the old band's minimum sat on its LEFT EDGE "
                 "(30) with the true scan minimum at a cross-pairing 24 -- no event "
                 "lock at all. The press is now delivered the F5b way, one-shot "
                 "--poke-at to MegaMan's AIData JoypadHeld (0x020340a2; held bits "
                 "persist in 0x0C, so two explicit 0x0000 clears follow each press), "
                 "measured to warp canon with rust's exact 5-frame signature "
                 "(706/458/395/458/706 px). The ready-chip speech bubble canon shows "
                 "8 frames after ANY warp (PAUSED's own queued Cannon40 icon -- "
                 "sub_801C002/sub_801C082 draw it from the 6 slots at dword_20352E0, "
                 "byte[0] = active, tiles to 0x06016A00 attr2 0xAB50) is blanked with "
                 "a per-frame --zero of those 48 bytes: rust's descriptor hand is "
                 "EMPTY (the old row already matched it against PAUSED's "
                 "gone-by-130 hand icon), the row is not about chips, and the icon's "
                 "own tiles re-upload through the GFX queue every frame (F10b's "
                 "unblankable 0x06016A00 sheets). rust: the SAME held-key SHAPE at "
                 "battle-relative frames 50/70/90/110 (marker origin 8 + those). "
                 "The pairing is the measured EVENT lock, held fixed (no search): "
                 "canon's warp anim starts 132 (poke 130), rust's starts 61 (press "
                 "8+50+3), so offset 51 -- isolated reads 0 there with +-1 frame "
                 "reading 8440, and the negative is no longer shift-invariant. The "
                 "old 40-wide search is dead: it was sized for input-lag between a "
                 "resumed real battle and a fresh fixture one, but the poke delivery "
                 "has no such lag, and on the integrated variant the search just "
                 "rode the static AUDIT-6 residue's monotonic slope to whatever band "
                 "edge minimized it (measured: totals at +1..+4 past the event lock "
                 "fall monotonically) -- the warp's ~1-2k px cannot steer a search "
                 "under 10-19k/frame of static mismatch. Measured with the search "
                 "removed, integrated reads 355385/19909 at the event lock vs the "
                 "OLD canon side's 392779 at the same alignment -- the change is "
                 "~37k BETTER at the honest alignment; the old printed 328071/18287 "
                 "was the band edge riding the slope, and the AUDIT-6 cap 19500 was "
                 "calibrated on that sloped alignment, so the harness's WORSE-than- "
                 "allowed print on integrated is a stale-cap artifact (coordinator "
                 "decision 2026-09-13; tools/allowlist.py untouched). "
                 "F38b (2026-09-14): resolve retried now that `over` no longer freezes "
                 "inputs/objects (F33d) -- warp integrated 40628->45751, isolated 0->5123 "
                 "(worst 1622; negatives not blind), reverted. Sequencer re-watched: 0x0C at "
                 "canon 47; our `over` at capture 8 with show at battle ~110 puts our banner "
                 "tail over rust 59..66 (k=0..7) and our slide past window end (rust 59..88), "
                 "while the k=24..29 ramp (1917..11744) stays canon's BG3 slide at 16 px/frame "
                 "with no rust counterpart (F34 driver chain holds -- result isolated 0). Flag "
                 "stays off; allowlist kept.",
        ),
        rust=_zero_enemy_rust(desc=WARP_ZERO, script=",".join([held("Right", 8 + 50, 3), held("Down", 8 + 70, 3),
                                        held("Left", 8 + 90, 3), held("Up", 8 + 110, 3)])),
        canon=_zero_enemy_canon("Start@10",
                                pokes_at=WARP_AIDATA_POKES,
                                zero=("0x020352E0:48",)),
        canon_variant="canon (sterile)",
    ),
    Check(
        name="buster",
        ui="both",
        frames=28,
        align=Align(
            canon_ref=BUSTER_ACTION_FRAME,
            search=range(96, 113),
            note="F31b re-cut: BOTH sides fire. canon: the zero-enemy arena (STERILE+PAUSED+"
                 "DELETE, Start@10) with the B tap poked into AIData -- see "
                 "BUSTER_AIDATA_POKES above for why a scripted press cannot reach MegaMan "
                 "here and why the tap has to end in a RELEASE. canon_ref is the MEASURED "
                 "EVENT, not a script frame: CurAction 0x0203a9b9 is written 0x11 on canon "
                 "132 (watched), CurAnim 0x0e runs 133..157, the pose and the barrel enter "
                 "OAM at 134, the muzzle at 135, and both objects vanish at 159 when the "
                 "attack state exits. rust: B held at battle-frame 100/101 (marker origin 8 "
                 "+ 100/101, unchanged from the old row) and the same event watched on our "
                 "side -- the ORCL export block's CurAction byte (0x02000008+13) goes 0x08 "
                 "-> 0x0b at rust capture 112, so the event lock is offset 104 and the band "
                 "range(96,113) is +-8 around it, wide enough to show the minimum is unique "
                 "and not a plateau. 28 frames = the attack from its state write to the "
                 "first idle frame after it (canon 132..159); the window STOPS at 159 on "
                 "purpose, because canon puts a 16x16 tile 0x350 palette 10 object at "
                 "(59,52) from 160 (present only when the buster fired; not yet identified, "
                 "// unnamed: a post-shot indicator above the navi) and the result mark "
                 "(16x16 tile 0x200 palette 11 at (37,21), F31's 3172) from 164. The OLD row "
                 "-- canon_ref=150, 32 frames, a scripted press -- compared two idle navis "
                 "and 18 frames of that result mark, and its offset was the first of an "
                 "8-wide plateau (122..129 all read 3172) that began exactly where our "
                 "buster left the window: F31's measurement, and the reason this row was "
                 "re-cut rather than re-aligned. The new alignment is a SHARP unique "
                 "minimum, not a plateau: swept over range(96,113) the totals read 0 at "
                 "offset 103 and 2911 at both 102 and 104, rising monotonically to either "
                 "band edge. What the four fixes were worth, measured one at a time on this "
                 "row: 4936 -> 736 for the pose length (17 -> the byte_80209CC lookup, "
                 "actor.rs), 736 -> 0 for the barrel and muzzle living exactly as long as "
                 "the pose (battle.rs), and 0 -> 0 for strike_at 3 -> 2 plus dropping the "
                 "double tick on the muzzle's spawn frame -- that pair is a model fix with "
                 "no pixels in it here, because assets/buster_fx.bin's first and last cells "
                 "are both blank (canon's OAM carries an 8x8 object at (96,78) that draws "
                 "nothing from canon 141 to 158), which is also why the row still read 0 "
                 "with the pair reverted. STILL OPEN, pixel-invisible: the two sides' state "
                 "watches sit one frame apart at this lock -- canon writes CurAction 0x11 on "
                 "132 = k=0, our ORCL export block flips its CurAction byte to 0x0b on rust "
                 "112 = k=1 -- while both sides DRAW the windup on k=0..1 and the pose from "
                 "k=2. Our windup draws the same pixels as canon's two pre-pose idle frames, "
                 "so the row cannot tell whether our attack state is entered one frame late "
                 "or our export block is one frame behind the frame it describes; settling "
                 "that is a main.rs/oracle question, not this row's. F38b (2026-09-14): resolve "
                 "retried now that `over` no longer freezes inputs/objects (F33d) -- buster "
                 "integrated 54672->81083, isolated 0->2286 (worst 617; negatives not blind), "
                 "reverted. Sequencer 0x0C at canon 47 (re-watched); our `over` at capture 8 "
                 "with show at battle ~110 puts our show (capture ~118, k=7) and mark (~121) "
                 "inside this window (rust 111..138) while canon's slide sits at k=22..27 and "
                 "its mark from 164 sits outside. The k=1..21 name strip (422 px/frame, "
                 "attack-specific, still unfixed on purpose) and the k=22..27 slide ramp keep "
                 "their F38 attribution; flag stays off.",
        ),
        rust=_zero_enemy_rust(held("B", 8 + 100, 2), desc=BUSTER_ZERO),
        canon=_zero_enemy_canon("Start@10", pokes_at=BUSTER_AIDATA_POKES),
        canon_variant="canon (sterile)",
    ),
    Check(
        name="chip-use",
        ui="both",
        frames=30,
        align=Align(
            canon_ref=CHIPUSE_PRESS_POKE,
            search=range(94, 111),
            note="F12 re-cut (2026-09-14): BOTH sides fire, the buster treatment. The old "
                 "row's scripted A@150,A@151 never reached MegaMan: the battle is resolved "
                 "(enemy DELETED, banner sequencer 0x0C from canon 47) and in 0x0C nothing "
                 "refreshes AIData from the joypad mirror (sub_8012DFC runs from 0x08 only) "
                 "-- measured on the old row's own captures: sequencer low byte 0x0c on "
                 "canon 140..186, JoypadPressed 0x020340a4 reads 0 even on the A frames, MM "
                 "stays CurState/CurAction (0x04/0x08) CurAnim 0x00 on every frame, canon "
                 "pixels static k=0..15 with a 177 px idle-flame flicker from k=16, while "
                 "the rust side entered its chip attack (ORCL action 0x0b, anim 8) at "
                 "battle 102 -- so the old event pairing compared our Cannon against "
                 "canon's idle (32847 at the event offset 100; the search's 9514 at 129 "
                 "was a score minimum at the band edge, F2). canon: the zero-enemy arena "
                 "(STERILE+PAUSED+DELETE, Start@10) with the A tap poked into AIData -- "
                 "see CHIPUSE_AIDATA_POKES for the measured fire (CurAction 0x14 on the "
                 "poke frame 130, attack state through 163, idle back at 164). canon_ref "
                 "is that MEASURED fire event. rust: A held at battle-frame 100/101 "
                 "(marker origin 8 + 100/101, unchanged) with hand=[1] Cannon; our ORCL "
                 "action byte flips 0x08->0x0b at rust capture 110, so the event lock is "
                 "offset 101 (sharp unique minimum: 0 here, 7768 at 100 and 102), kept to confirm "
                 "the minimum is unique, not to find it. STILL OPEN, pixel-invisible (buster's "
                 "own ambiguity): the state watches sit one frame apart here -- canon writes "
                 "CurAction 0x14 at k=0, our ORCL flips to 0x0b at k=1 -- while both sides "
                 "DRAW the windup on k=0..1 and the pose from k=2. 30 frames = both attacks' common "
                 "span from the fire frame (canon 130..159, attack through 163; ours "
                 "battle 101..130); the window STOPS at 159 on purpose, before canon's "
                 "result mark from 164 (an OBJ the rust side never draws without "
                 "SceneFlags::RESOLVE_OVER) -- the same stop buster uses. Canon's 4-frame-longer "
                 "tail (attack through 163 vs ours through 131) sits outside the window "
                 "and stays OPEN with this ticket. F38b (2026-09-14): resolve retried now that "
                 "`over` no longer freezes inputs/objects (F33d) -- chip-use integrated "
                 "275307->269172, isolated 0->4026 (worst 808; negatives not blind), reverted. "
                 "Honest lock stays 101 (remainder 281885 there, F38); the printed search minimum "
                 "sits at the band's left edge and is score-ridden, not event-locked. Sequencer "
                 "0x0C at canon 47 (re-watched); our `over` at capture 8 with show at battle ~110 "
                 "straddles this window (rust ~108..137), giving partial slide overlap (hence the "
                 "small drop) while the BG1 art mismatch (~17k/frame) dominates untraced with no "
                 "descriptor change. Flag stays off.",
        ),
        rust=lambda ui: Side(rom=plain_rom(), fixture=CHIPUSE_ZERO,
                             script=held("A", 8 + 100, 2),
                             extra=() if ui == "integrated" else ("--disable-bg",)),
        canon=_zero_enemy_canon("Start@10", pokes_at=CHIPUSE_AIDATA_POKES),
        canon_variant="canon (sterile)",
    ),
    Check(
        name="wave",
        ui="isolated",
        frames=90,
        align=Align(
            canon_ref=71,
            search=range(337, 353),
            note="Enemy IS the subject (AUDIT pair 3: mettaur and wave get their own checks "
                 "rather than a zero-enemy arena). canon: STERILE+PAUSED+ALIVE, Start@10 -- "
                 "canon_ref=71 unchanged from regress.py's check_wave (the shockwave's first "
                 "visible hop). rust: FIELD_ROW through the descriptor. RE-CENTRED AND "
                 "RE-ISOLATED this ticket (AUDIT wave 3d follow-up), two changes together: (1) "
                 "after the src agent replaced the Mettaur's flat timer with the real 5-state "
                 "machine (106-frame cycle, not the old ~64), the OLD band (178..202, centred on "
                 "offset ~190) no longer reaches the true alignment -- re-swept wide "
                 "(range(300,400)) on the OLD --disable-obj isolation found only a shallow, "
                 "non-zero minimum (offset 326, 353137 px), because that isolation leaves BG1 "
                 "and BG3 in the comparison too and 'panel lighting is BG, not sprites' names "
                 "BG2 specifically as the subject -- and (2) the bg3-merge agent's own landing "
                 "(AUDIT wave 3d) made `--only-bg N` finally symmetric between the two sides "
                 "(pair 2), which this check could not exploit before. Switching BOTH sides from "
                 "--disable-obj to --only-bg 2 and re-sweeping the SAME wide band finds a sharp, "
                 "unique zero at offset 345 (337..353 climbs steeply either side, e.g. 344 -> "
                 "4800, 346 -> 3840) -- BG2 alone, unshifted, is EXACT, unlike the multi-layer "
                 "capture. This band (337..353) brackets it with margin.",
        ),
        rust=lambda ui: Side(rom=plain_rom(), fixture=FIELD_ROW, extra=("--only-bg", "2")),
        canon=lambda ui: Side(rom=STERILE, loadstate=PAUSED, cheats=ALIVE, script="Start@10",
                              extra=("--only-bg", "2")),
        canon_variant="canon (sterile)",
    ),
    Check(
        name="gunner",
        ui="both",
        frames=130,
        align=Align(
            canon_ref=80,
            search=range(0, 40),
            note="T9j (2026-09-15): the Gunner scenario -- cannon-fire from the poked "
                 "battlestart_gunner.state. canon: REAL+BATTLESTART_GUNNER (T9c's state, "
                 "BattleSettings record 6 with a Mettaur at slot 0 (panel (5,2), NameID "
                 "0x0001, HP 0x28) and a Gunner at slot 1 (panel (6,3), NameID 0x0085, HP "
                 "0x3c)). rust: GUNNER_ROW (enemies=2, enemy_kind=0x05 packing slot 0 "
                 "Mettaur + slot 1 Gunner, the kind_of() split fixture.rs:248-264 defines). "
                 "INTEGRATED (ui='both'): both BG and OBJ, the whole 240x160. canon_ref=80 "
                 "(first attack-event frame on canon side: canon's state-loading white runs "
                 "capture frames 0..70; battle content starts at 71 and the gunner's first "
                 "attack-event frame -- CurAction transitioning to 0x0A, when sub_8113162's "
                 "row-check fires -- is 80), search band 0..40 (rust side's marker origin 8 "
                 "+ 26..40 = the gunner attack event window on rust). rust_origin=8 for "
                 "GUNNER_ROW, same family as FIELD_ROW. The 130-frame span covers one full "
                 "materialize/attack/recover cycle (cursor walk 13 panels at 3 px/frame "
                 "+ 3 shots at 10-frame gaps + 24-frame recover = ~127 frames, rounded to "
                 "covers one full materialize/attack/recover cycle (cursor walk 13 panels "
                 "at 3 px/frame + 3 shots at 10-frame gaps + 24-frame recover = ~127 "
                 "frames, rounded to 130 with margin). --disable-bg stays off -- "
                 "integrated is the documented 'M5 baseline (0/0/130)' shape the ticket "
                 "asks for. Per-state timer arms cite asm/object.s via src/gunner.rs's "
                 "GunnerEntry doc; the per-type routine cite byte_80182C4[3*enemy_idx] sits "
                 "at src/objects.rs:Style::Gunner and src/gunner.rs:GunnerEntry. The "
                 "negative fixture (frame-shift) MUST be non-blind -- the cursor's own "
                 "panels at x2..37 / y18..152 are the live content a shifted diff would "
                 "break (open question until this row is measured). T9l (2026-09-15) "
                 "measured it: the negative is NOT blind (2852957 at the borrowed seeds). "
                 "T9l also derived this row's own backdrop seeds (see GUNNER_ROW above): "
                 "2850534/38237/130 -> 2105613/38237/130, BG1-only 1524416 -> 230400 (the "
                 "230400 is exactly six full-screen frames, k=0..5; BG1 is 0 for k>=6). "
                 "Remaining residue, named: (1) k=0..5, all layers full-screen -- canon "
                 "fades from bright (OBJ mean 93,77,60,44,28,12) where rust is dark: the "
                 "tail of a fade this row starts 10 frames later than the doc's white "
                 "0..70 claim; (2) k=6..75, BG3 -- the two enemy HP boxes (y0..15, "
                 "x100..190, two enemies vs mettaur's one) and the bottom-left custom "
                 "gauge bar (y152, x12..60): canon's bar reads full from k=0 while "
                 "GUNNER_ROW's borrowed gauge=0 never fills; (3) k>=77 -- canon's "
                 "gauge-full pause opens the chip window on BG3 (slide from canon frame "
                 "~156, the documented 'window comes up on its own at frame 165', "
                 "src/battle.rs:1998) and pauses canon's battle, so BG3 carries a "
                 "left-half window (x0..117, full height) rust never draws and the OBJ "
                 "plateau (~5.8k/frame) is downstream of that pause; the k=45..76 OBJ "
                 "growth (dense y90..120, x to 239) precedes it and is the shot region, "
                 "not the aim cursor -- no 3 px/frame walk shows in the diff bboxes. "
                 "The gauge register this state fights with is NOT 0x020352a0 (reads 0 "
                 "all 170 frames peeked) -- the full-bar evidence is visual.",
        ),
        rust=lambda ui: Side(rom=plain_rom(), fixture=GUNNER_ROW),
        canon=lambda ui: Side(rom=REAL, loadstate=BATTLESTART_GUNNER),
        canon_variant="canon",
        # T9i (2026-09-15): serialize rust+canon in one process so the pair
        # never competes for one of cc.CAPTURE_SLOTS -- the default
        # ThreadPoolExecutor path had the gunner canon side short-count
        # under slot contention (rust 58/170 + canon 27/135 on the 3-slot
        # pool) and the parallel ui='both' variants (isolated + integrated)
        # raced on the same watch file because their rust/canon lambdas do
        # not vary by ui (key collision in run()'s scratch path). run() now
        # folds variant_label into the scratch key, so the watch file is
        # unique per variant, and serial captures run rust then canon
        # sequentially -- the gunner row no longer hits the 3-slot race.
        serial=True,
    ),
    Check(
        name="window",
        ui="isolated",
        frames=16,
        align=Align(
            canon_ref=55,
            search=range(215, 245),
            note="Wave 3b ticket step 2: the deck/deck_codes/window_pick_* fields now land in "
                 "CUSTMATCH_ROW (src/fixture.rs reads them, verified byte-identical there except "
                 "a small 371px/2-frame card-picture residual -- zero-src's own ticket). isolated "
                 "= the window's own layer, not the whole screen: --only-bg 3 on BOTH sides "
                 "(BG3 is the chip-select window itself; BG1 is a flat fill, BG2 the field panels "
                 "underneath). SYMMETRIC AS OF THIS TICKET (AUDIT wave 3d bg3-merge follow-up): "
                 "the rust side used to blank its own HUD/backdrop (ISOLATED_CUSTMATCH_ROW, "
                 "flags 0x17) as a workaround for a BG-index mismatch bg3-merge has since fixed "
                 "-- our HudTiles/Custom/Results now sit on canon's own BG3, so --only-bg 3 "
                 "reaches the SAME layer on both sides without the workaround (dropped: plain "
                 "CUSTMATCH_ROW, flags 0x11, HUD not blanked). Reads 0 (PASS) -- but measured, "
                 "not assumed, and NOT hidden: canon's own BG3 does not change AT ALL for at "
                 "least 260 consecutive frames from CHIPSELECT with no script (diffed live, this "
                 "ticket) -- the window sits open and unchanging with nothing pressed, so a 1-BG "
                 "capture of it is unchanging too, on BOTH sides, at every offset in a swept "
                 "150..295 range (all exactly 0). AUDIT pair 10 in its own terms: this check is "
                 "BLIND (the negative fixture -- canon shifted +1 frame at the SAME found offset, "
                 "not re-searched -- also reads 0, confirmed live), which run_check() reports "
                 "honestly rather than silently passing. NOT FIXED this ticket (out of the scope "
                 "the coordinator asked for -- 'drop the workaround, compare symmetrically, "
                 "report what they read'): a non-blind version needs the compared window to "
                 "straddle a real BG3 transition, and this Check has no script at all to cause "
                 "one (unlike `card` below, which does and is blind for a different, related "
                 "reason -- see its own note). canon: REAL+CHIPSELECT unchanged otherwise. rust: "
                 "marker origin 8 plus a band around regress.py's old compared rust frame (its "
                 "own start=55 PLUS lag[174,190] = 229..245, 221..237 once origin is subtracted) "
                 "-- kept, still inside the wide zero-and-blind plateau just measured.\n"
                 "NEGATIVE FIXTURE, resolved after that ticket: `negative='pixel'`. The "
                 "measurement above is exactly the case a frame-shift negative cannot test -- "
                 "canon's BG3 here is byte-identical for 260+ consecutive frames, so shifting "
                 "it a frame breaks nothing, and the resulting BLIND says the subject is "
                 "static, not that the check is wrong. A one-column shift breaks it instead, "
                 "and tests what this check can actually get wrong: that the diff is live, "
                 "aligned, and looking at the window's real content. Weaker than a frame "
                 "shift, and used here only because this subject provably has no timing in "
                 "it; `card` next door keeps the frame shift, because its window does move.",
        ),
        negative="pixel",
        rust=lambda ui: Side(rom=plain_rom(), fixture=CUSTMATCH_ROW, extra=("--only-bg", "3")),
        canon=lambda ui: Side(rom=REAL, loadstate=CHIPSELECT, extra=("--only-bg", "3")),
        canon_variant="canon",
    ),
    Check(
        name="card",
        ui="isolated",
        frames=16,
        align=Align(
            canon_ref=46,
            search=range(292, 305),
            note="Same wiring as `window`: --only-bg 3 on BOTH sides, plain CARDNAME_ROW "
                 "(window_cursor=0), HUD not blanked. TODO F13b (2026-09-13): the rust side now "
                 "WALKS -- _CURSOR_WALK_RUST (presses 250/280/310/340/370) instead of the real "
                 "script, because F13 measured that rust's window opens ~131..142, so the real "
                 "script's presses (20+30k) landed while it was still closed and rust held static "
                 "slot 0 (row read 18486/3081, matching only from canon 142 where both showed slot "
                 "0's name). Measured live for this ticket: canon (REAL+CHIPSELECT, cursor byte "
                 "0x020364C7) walks OK->4->3->2->1->0 -- RAM transitions 21/51/81/111/141, pixels "
                 "one later (22/52/82/112/142); rust (origin 8, re-measured live for this build) "
                 "pixel transitions 252/282/312/342/372 (+2 after each press, same lag as canon). "
                 "PATH DIFFERENCE, accounted: rust walks FROM 0 and its first Left wraps to OK, so "
                 "its slot sequence is OK,4,3,2,1 -- cross-diffing every rust post-transition frame "
                 "against every canon slot shows rust after transition n == canon slot (4-n) for "
                 "n>=2 and nothing for n=1 (OK) -- so the shared events are press-index-shifted, and "
                 "the alignment is event-locked, NOT press-index-locked: the shared 4->3 slot "
                 "change is canon pixel 52 <-> rust pixel 312, i.e. offset 312-8-(52-46) = 298 "
                 "(inheriting the naive 282-pairing would have aligned rust's OK->4 against "
                 "canon's 4->3 -- a slot mismatch on every frame). Band 292..305 confirms a unique "
                 "sharp minimum at 298 (0 px; 3046 px for the off-by-one neighbours -- F2's rule: "
                 "chosen by the measured event, band only confirms). Compared window canon 46..61 "
                 "straddles the 4->3 transition (RAM 51 / pixel 52), so a one-frame canon shift "
                 "still has something to break -- non-blindness from re-centring, not from "
                 "weakening the negative (negative stays 'frame'). WINDOW-OPEN coverage: the "
                 "window-open ANIMATION itself (rust capture frames ~131..142) was never inside "
                 "the old band (old rust window 198..213) and is not inside this one; what both "
                 "bands keep in view is the OPEN window's live content -- here every compared "
                 "frame shows an open window whose card name changes mid-window on both sides, "
                 "which is the coverage that makes the row able to fail. canon: REAL+CHIPSELECT, "
                 "the SAME 5-press-Left script as `cursor` below (presses 20+30k). rust: marker "
                 "origin 8 plus the band above.",
        ),
        rust=lambda ui: Side(rom=plain_rom(), fixture=CARDNAME_ROW, script=_CURSOR_WALK_RUST,
                             extra=("--only-bg", "3")),
        canon=lambda ui: Side(rom=REAL, loadstate=CHIPSELECT, script=_CURSOR_WALK_REAL,
                              extra=("--only-bg", "3")),
        canon_variant="canon",
    ),
    Check(
        name="cursor",
        ui="isolated",
        frames=170,
        align=Align(
            canon_ref=15,
            search=range(225, 250),
            note="AUDIT ticket step 5: 'cursor... just broke on a hardcoded lag... marker "
                 "alignment is the fix.' The offered deck is STILL pending-src (same field as "
                 "`window`/`card`), so this keeps building the rust side from the "
                 "demo-custmatch FEATURE (not yet a descriptor) -- but the old fixed "
                 "CURSOR_LAG=230 constant is GONE, replaced with marker origin (8, measured "
                 "live for this exact feature build) plus a search band around regress.py's old "
                 "compared rust frame (start=15 PLUS CURSOR_LAG=230 = 245, 237 once origin is "
                 "subtracted), so a future boot-length shift (the ONE THING that broke this, 0 "
                 "-> 602 pixels, all of it one frame of 170) self-corrects instead of silently "
                 "drifting. Script unchanged from regress.py (5 Left-presses, 30 frames apart); "
                 "box removed, full screen, all 170 frames. Ported from the demo-custmatch "
                 "feature to CUSTMATCH_ROW (fixture.rs's own table entry, already used by "
                 "`window` above; AUDIT pair 17 prune ticket) -- same descriptor bytes, same "
                 "numbers.\n"
                 "F26b (2026-09-13), THE BACKDROP PHASE AND THE REPAIRED LAYER TABLE. This row "
                 "now uses CURSOR_ROW, not bare CUSTMATCH_ROW: it pairs canon frame 15 where "
                 "`windowclose` pairs canon 81, so the two need different backdrop seeds (the "
                 "derivation sits above the descriptors). BG1 alone (--only-bg 1 --disable-obj, "
                 "identical flags both sides) 2214975/15746/170 -> 2/2/170 (1/1 on the merged "
                 "tree). Full screen 620802 -> 272341/1603/170. THE OLD 620802 WAS NOT AT THIS "
                 "ROW'S OWN OFFSET: measured this ticket, the unseeded band's minimum sat at "
                 "226 (620802) and the event-derived 237 read 779920 -- the backdrop's whole-"
                 "screen phase error was big enough to drag the search 11 frames off the event, "
                 "exactly what F2's rule warns about. With the seed the minimum is back at 237 "
                 "(272341, against 459077 at 236 and 458617 at 238). "
                 "LAYER TABLE, ARITHMETIC CLOSED. F26's table summed layer-local totals and got "
                 "689572 > the 620802 full frame; the fix is to state two different quantities "
                 "rather than one. LAYER-LOCAL |Li| = that layer captured alone on both sides "
                 "and diffed: it ignores occlusion, so it can exceed the composite. ATTRIBUTED "
                 "|C and Li| = the composite's differing pixels that the layer-local mask also "
                 "calls differing, and those partition the composite exactly. Merged tree, 170 "
                 "frames: composite 272341 = OBJ-only 272340 + BG1-only 1, no pixel in both and "
                 "none UNEXPLAINED (every composite pixel is reproduced by some single-layer "
                 "capture). OBJ layer-local is 612811, and the gap to its 272340 attribution is "
                 "occlusion, measured: on the merged tree the OBJ diff falls in exactly two x "
                 "bands -- 2..77 (y18..152, 340471 px-frames) and 122..189 (y18..159, 272340) "
                 "-- and only the second is outside the chip window (BG3 covers x<112); "
                 "340471 + 272340 = 612811, the layer-local total, and the visible half is "
                 "the attribution to the pixel. (Before F29 landed there was a third band at "
                 "x83..117 y70..113, 129687 px-frames: MegaMan at the wrong panel, hidden "
                 "behind the window and so invisible in the composite either way.) THE FOUR UNCHECKED "
                 "ATTRIBUTIONS OF F26, each now measured. (a) 'BG1 art phase, ours leads by 2' "
                 "-- REFUTED as stated: it was not a 2-frame lead but an unseeded clock. "
                 "Watched, canon eGFXAnimStates[0] is entry 17/Timer 4 at canon frame 15 and "
                 "entry 25/Timer 2 at 81, while our unseeded build was entry 10/Timer 2 at the "
                 "paired rust frame 245; with the derived seed the art matches on every frame. "
                 "(b) 'the enemy is a Mettaur variant other than kind 0' -- there IS no Kind "
                 "field (BattleObject.inc has none); the enemy at 0x0203ab60 reads NameID "
                 "(+0x28) 0x0001, header word 0x02910037, Params 0x1e000000, CurState/CurAction "
                 "0x04/0x0b, HP 40, panel (5,3), every one of them constant over 90 canon "
                 "frames -- so the row's enemy_col/enemy_row/enemy HP already match and the "
                 "open question is only what NameID 1 means, which no pixel here depends on. "
                 "(c) 'enemy-HP portrait content identical, box-x canon 122-165 vs ours 2-45' "
                 "-- CONFIRMED and sharpened to a pure 120 px x displacement: in the OBJ-only "
                 "capture the 44x16 block at y18..33 holds 694 non-background pixels on OUR "
                 "side at x2..45 (canon has none there) and 694 on CANON's at x122..165 (we "
                 "have none there), and the two are identical on all 704 pixels when shifted by "
                 "120, against 10/704 compared at the same x. It is worth 117980 of the visible "
                 "OBJ residue's 272340 px-frames (the other 154360 are y107..159). Not fixed "
                 "here: the HUD OBJ is another worker's file. (d) 'MegaMan at canon panel (2,3) "
                 "vs fixture (3,2)' -- CONFIRMED by watch, canon PanelX/PanelY (0x0203a9c2/"
                 "0x0203a9c3) read (2,3) on every frame of this capture; F29 has since landed "
                 "megaman_col=2/megaman_row=3 in CUSTMATCH_ROW, which this row inherits.\n"
                 "The one BG1 pixel left is not a phase error: 2 px (1 after the merge) at y=5, "
                 "x=55 and x=183 -- the same texel twice, 128 apart, the map's own x+128 "
                 "repeat -- on k=97 alone. Holding our art one frame later makes that frame "
                 "read 1157 px over rows 5..156, so canon's frame carries the PREVIOUS step in "
                 "rows 0..5 and the new one below it: canon's tile copy is queued "
                 "(QueueEightWordAlignedGFXTransfer, sub_8001C94, asm00_0.s:3752) and drained "
                 "part-way down the frame, while our replace_tile lands before scanline 0. A "
                 "sub-frame difference, not a clock difference.\n"
                 "F37 (2026-09-14), PER-OBJECT TABLE, OAM both sides (--watch 0x07000000:1024; "
                 "canon 15..184 <-> rust 245..414). Composite 154361 = 908 x 169 + 909, and "
                 "every frame's diff sits inside canon's Mettaur/HP boxes: o07 HP box "
                 "(156,147,32x16,198px), o08 (166,131,8x16,69), o09 (174,127,16x32,462), o10 "
                 "(172,123,8x16,126), o11 (164,107,32x16,252), o15 (163,143,32x8,155). Two "
                 "stacked causes. (a) CAMERA PAN, +15 Y while the window is open: canon holds "
                 "every field object 15 px lower with the window up (MegaMan y141/141/109/139 "
                 "open vs 126/126/94/124 closed; Mettaur and HP box the same 15), while this "
                 "build's field_slide drives the BG scroll only and its objects sit at the "
                 "closed positions (ours == canon's closed set); the emotion window does not "
                 "move (y18 both) and the cursor bracket needs no shift (positions match, 0 "
                 "px). (b) POSE: canon's Mettaur sits frozen in the attack executor (4,11) "
                 "anim 1 timer 2 all 170 frames -- BattlePaused (GameState+0x0A, "
                 "GameState.inc:34) reads 1, PauseBattle asm00_1.s:14878, unflagged objects "
                 "skip their update (asm00_1.s:90-110) -- while ours idles in the decision "
                 "dispatch (4,8) anim 0 (oracle first divergence k=0, all frames). MegaMan 0 "
                 "in the composite (occluded x<112; states match per oracle), bracket 0, "
                 "emotion 0, mark/power occluded 0. Both cited fixes live outside this "
                 "ticket's files (pan in actor/battle object Y; a battle-pause gate plus a "
                 "phase the Fixture has no fields for -- kind/col/row/HP already match canon "
                 "RAM: NameID 1, (5,3), 40, mm (2,3) HP 100), so neither is widened into. "
                 "F37b (2026-09-14), three battle.rs/fixture.rs steps, each measured alone "
                 "(wt/f37b 674d771/d4b4bb3/69e15ac): (1) enemy HP object-text rides the "
                 "field_slide camera (+15 px open, battle.rs show site): 154361/909 -> "
                 "130246/783, BG layers untouched (already 0). (2) peeked enemy_state=4 / "
                 "enemy_action=0x0b descriptor bytes (+62/+63, fixture.rs reserved-region "
                 "pattern) applied as SWING at window-open, plus the BattlePaused freeze "
                 "(enemy.update skipped while custom open, fixture-gated past close since "
                 "canon holds BattlePaused=1 there): oracle enemy_state_action+enemy_anim "
                 "170/170 (was divergent all frames), pixels 130246 -> 130266 (neutral -- "
                 "pose right, position still 15 px off). A 9-tick pose prime (canon froze "
                 "mid-raise) was tried and REVERTED (windowclose improved but cursor "
                 "130266 -> 159656: at the wrong position the frame is a wash). (3) n/a "
                 "here (no hand icon while open; 130266 -> 130221). Remainder, measured: "
                 "actor object-Y pan (+15 while open -- actor.rs, out of scope) and the "
                 "frozen pose frame. window/card/wave/opening/chip-cannon/mettaur/popup/"
                 "result/field all still 0. "
                 "F37d (2026-09-14), pickaxe prime landed (wt/f37d): canon's frozen "
                 "sprite is anim-1 frame_in_anim 4, not frame 0 -- OAM on this row's own "
                 "canon capture (frame 15, enemy pal 1) shows all five parts at "
                 "(164,107,32x16), (172,123,8x16), (174,127,16x32), (166,131,8x16), "
                 "(163,143,32x8), exactly our ROM-exported mettaur.bin anim-1 frame 4 "
                 "(sub_8109DEC sets CurAnim 1, asm31.s:170830-170848; BattlePaused "
                 "freezes it, asm00_1.s:90-110). No new art: the asset already holds "
                 "it. The seeded SWING is primed 9 executor ticks (frame 4 spans ticks "
                 "7..14 of durations 1,1,1,3,8). Measured: 34902/232/170 -> 8/6/170 "
                 "(k37 2px, k97 6px, the known mid-frame tile transfer); mettaur row "
                 "still 0.",
        ),
        rust=lambda ui: Side(rom=plain_rom(), fixture=CURSOR_ROW, script=_CURSOR_WALK_RUST),
        canon=lambda ui: Side(rom=REAL, loadstate=CHIPSELECT, script=_CURSOR_WALK_REAL),
        canon_variant="canon",
    ),
    Check(
        name="windowclose",
        ui="isolated",
        frames=40,
        align=Align(
            canon_ref=81,
            search=range(248, 259),
            note="TODO F3: the window CLOSING -- no earlier row covered it (window/card/cursor "
                 "stop while it is open). canon: REAL+CHIPSELECT, Start@50 (jump the cursor to "
                 "OK, custMenuSomeHandler's Start branch) then A@80 (custMenuPressOK_8028D3A) "
                 "-- pressed through to OK exactly as a player does. The close event is watched, "
                 "not assumed: --watch 0x020364c0:0x48 (eS20364C0, the window's own state "
                 "struct) shows JumpOffset01 0x04 -> 0x08 (the slide-out state, sub_8026BF4) on "
                 "the frame of the A press and its slide counter (+0x40) counting 0x0c..0x78 "
                 "across the ten calls at canon frames 81..90 -- canon_ref=81, the first frame "
                 "the window is leaving. rust: the same CUSTMATCH_ROW as `window`/`card` (the "
                 "window opens with the cursor already on OK, window_cursor=0xa), the SAME "
                 "press shape (Start@230,A@260), full screen, no layer isolation -- the ticket "
                 "compares the whole screen, the ghost included. Event-derived offset 253: our "
                 "slide-out calls run at capture frames 261..270 (marker origin 8) against "
                 "canon's 81..90, and at offset 253 the ten slide frames compare EXACTLY 0 on "
                 "the window's own layer (--only-bg 3, measured) -- the band is centred there "
                 "to CONFIRM a unique minimum, not to find one: over the full screen a deeper "
                 "meaningless basin sits near offset 264 (575089 vs 695603), where the "
                 "unshared-battle noise (the enemy acts on an RNG the two sides do not share, "
                 "the same residue `cursor` carries) happens to score lower by pairing frames "
                 "from different phases of the two diverging battles; the event, not the "
                 "score, picks 253 (F2's method). The post-close BG3 residue at the true "
                 "alignment WAS a flat 1402 px of HUD-strip content -- canon's gauge RESETS to "
                 "empty when the window closes and redraws (rows 8..15) while ours stayed full, "
                 "and ours showed the hand's chip name (rows 148..158, 'Cannon 40') where canon "
                 "shows none -- FIXED by F18 (2026-09-13), measured on this same band. The gauge "
                 "element was a src/ defect, not fixture content: canon's not-full gauge draw "
                 "(sub_801C4E4 loc_801C534, asm00_2.s:26390-26393) fills ALL 16 bar cells -- the "
                 "four marker cells included -- with map entry 0x9222 = VRAM tile 0x222 (dump-"
                 "verified: 16 consecutive 0x9222 entries at BG3 map row 1, post-close), so the "
                 "L-or-R marker text is a FULL-state-only thing; src/hudtiles.rs now draws the "
                 "exporter's new INTERIOR tile (asset 70 = the gauge blob's tile 0, appended "
                 "after the blank, byte-verified against a post-close VRAM dump) there instead "
                 "of full-state MARKER_WAITING text over black FILLER (--only-bg 3: gauge band "
                 "y8..15 x56..183, 980 px/frame -> 0). The name element likewise: canon's close "
                 "routine sub_8026BF4 (asm03_0.s:1037, the JumpOffset01 0x04->0x08 slide-out "
                 "this row's watch names) blanks the 7x2 name strip via sub_8029D80 (CopyBack-"
                 "groundTiles of tile 0) and leaves it blank -- the OK press commits the picks to "
                 "the sent-chip data (sub_8029110), not to anything the name display follows -- "
                 "so Battle::name_suppressed (set in the window-close block) stops the hand-front "
                 "redraw (--only-bg 3: name strip y148..158 x1..63, 422 px/frame -> 0). Post-"
                 "close BG3 now reads 0 for k=12..39; slide frames k=0..9 and k=10 still exactly "
                 "0; k=11 is an UNCHANGED one-frame close-sequencing transient (2447 px: canon "
                 "blank k10/settled k11, ours blank k10/partial k11/settled k12), not part of "
                 "the flat band. Full screen reads 666451/28784/40 (was 695603/28784/40); what "
                 "remains is the same unshared-battle RNG noise `cursor` carries. SIDE EFFECT, "
                 "measured (base 9ed8a42 vs this branch): the four integrated rows whose "
                 "fixtures say gauge=0 against canon captures whose HUD shows a FULL gauge moved "
                 "with the corrected not-full rendering -- field 368525/23784 -> 380488/24240, "
                 "buster 626040/26660 -> 643698/27225, chip-use 626461/26660 -> 644119/27225 "
                 "(all still inside their AUDIT-6 caps), warp 355385/19909 -> 363658/20107 (it "
                 "already printed WORSE-than-allowed at base: the 19500 cap is the stale-cap "
                 "artifact warp's own note records) -- a fixture-content mismatch class, not a "
                 "src/ defect: canon's own not-full gauge is what the new code now draws. "
                 "F29 (2026-09-13) DECOMPOSED the remaining 648948/27391/40 by LAYER, both "
                 "sides captured with the IDENTICAL isolation flag at this same offset 253: "
                 "BG0 0, BG3 0 (the window's own layer and the HUD strip -- F18..F18d closed "
                 "it, all 40 frames), BG1 877602 worst 22658 on every one of the 40 frames, "
                 "BG2 266412 worst 18864 on k=1..19 only (0 at k=0 and 0 from k=20), "
                 "OBJ-over-blank-BG0 (--only-bg-with-obj 0) 97644 worst 4086, all-BGs "
                 "(--disable-obj) 619294. Each layer\'s mechanism, named and measured: "
                 "(1) BG2 IS THE FIELD\'S 15-PX CAMERA PAN, AND IT RUNS TEN FRAMES LATE. The "
                 "panel art and palette are exact (0 px at k=0 and at k>=20); what differs is "
                 "the vertical scroll: canon\'s top-of-field row runs 87,86,84,83,81,80,78,77,"
                 "75,74,72 over k=0..10 (progress floor(3n/2)) while ours holds 87 to k=10 and "
                 "then runs 87,85,84,82,81,79,78,76,75,73,72 (progress ceil(3n/2)) -- ten "
                 "frames late AND rounded the other way; canon k=2/4/6/8/10 compare EXACTLY 0 "
                 "against our k=12/14/16/18/20. Canon pans the camera FROM INSIDE the window\'s "
                 "own slide routines: sub_8026BF4 (the slide-OUT this row watches) adds "
                 "dword_8026CC8 = 0x18000 to Camera+0x34 on every one of its ten calls "
                 "(reference/bn6f/asm/asm03_0.s:1099-1104, constant at asm03_0.s:1141-1142) and "
                 "the slide-IN subtracts the same value on each of its own (asm03_0.s:964-969); "
                 "0x18000 is 1.5 px in the camera\'s 16.16 fixed point, so ten calls ARE the "
                 "15-px pan, it runs WITH the window, and canon reads the camera with an "
                 "arithmetic shift, i.e. truncation toward -inf, which is what makes the "
                 "progress floor(3n/2) rather than ceil. src/battle.rs:1971-1977 instead waits "
                 "for `self.custom` to become None (which happens on the tenth slide call, so "
                 "the first step lands ten frames late) and divides a magnitude, which rounds "
                 "the other way. FIXED (F29, coordinator-approved hunk in src/battle.rs): "
                 "`want` is 0 while `self.custom.as_ref().is_some_and(|w| !w.is_closing())` is "
                 "false, so the pan steps on the ten slide calls themselves, and the halving is "
                 "div_euclid so it floors the way canon's arithmetic shift does. MEASURED on "
                 "this row: windowclose 648948/27391/40 -> 450770/12529/40 (negative 577321, "
                 "not blind), BG2 266412 -> 0 on all 40 frames; wave/window/opening/chip-cannon/"
                 "field isolated all still 0, opening integrated 72499 unchanged, field "
                 "integrated 305258 -> 305253 (-5 px; that row moves by about 5 px between "
                 "builds at this scale, well inside its 28000 cap). FIELD_SLIDE=30/FIELD_SLIDE_STEP=3 (battle.rs) now carry a derived "
                 "provenance: they are that 0x18000 x 10. "
                 "(2) BG1 IS THE BACKDROP\'S SCROLL PHASE, and the rate is right: the whole "
                 "layer is a CONSTANT translation of (20,10) px on every one of the 40 frames "
                 "(best-shift search, cropped and cyclic both), art identical, so nothing is "
                 "drifting. At SCROLL_X_Q=2 / SCROLL_Y_Q=1 quarter-pixels a frame "
                 "(src/backdrop.rs:66-67) that is exactly 40 frames of scroll phase. "
                 "CUSTMATCH_ROW seeds none (art_entry etc. all 0xFFFF = a fresh Backdrop::new "
                 "at x_q=y_q=0) while /tmp/chipselect.state is thousands of frames into someone "
                 "else\'s battle -- canon\'s own eBGScrollCBCounters (ewram.s:619, 0x02009690/"
                 "0x02009694) read 0xffff9ad8 / 0xffffcd6c at canon frame 81. MEASURED: adding "
                 "art_entry=0, art_timer=4 (= Backdrop::new\'s own fresh clock, so the art is "
                 "unchanged), scroll_xq=80, scroll_yq=40 to CUSTMATCH_ROW takes windowclose to "
                 "392992/20875/40 and BG1 877602 -> 228662; the control (the same four fields "
                 "with scroll_xq=scroll_yq=0) reads 648948/27391/40, byte-for-byte the "
                 "baseline, so the seeding path itself is neutral. NOT APPLIED, and it must not "
                 "be applied as a shared constant: CUSTMATCH_ROW is also `cursor`\'s fixture, "
                 "and `cursor` pairs rust battle frame 237 with canon 15 where this row pairs "
                 "253 with 81 -- a 50-frame difference in the same descriptor -- so the same "
                 "seed measures cursor 620802 -> 1222398 (measured, both runs this session). A "
                 "backdrop seed has to be derived per row from canon\'s counters and the row\'s "
                 "own alignment, not shared. What is left in BG1 after the seed is two smaller "
                 "terms, both localised: a +-1 px odd-frame difference (the residual bottoms at "
                 "roll (+1,+1) or (+1,0) on k=3,9,15,21,27,33,39 and at (0,0) on the even "
                 "multiples of 6) -- exactly the `lsr #4` of a falling counter vs this build\'s "
                 "floor-divide that src/backdrop.rs:278-283 already writes down as untested "
                 "because \'nothing yet MEASURES an odd frame\'; this row now does -- and a "
                 "floor that grows with k (about 500 px at k=6..15, 1200 at k=18..24, 6300 at "
                 "k=27..39), the GFXAnim art schedule\'s own phase, which the same descriptor\'s "
                 "art_entry/art_timer would have to carry. "
                 "(3) OBJ 97644 SPLITS INTO THREE OBJECTS (8x8-cell clustering of the "
                 "--only-bg-with-obj 0 diff): MegaMan x43-117 y52-152, 1532 px/frame rising to "
                 "a flat 1788 from k=10, 68989 of the 97644; the enemy x164-189 y92-159, about "
                 "900 px/frame over k=0..9 settling to a flat 205, 14228; and the HP boxes and "
                 "hand icon in the y4-33 strip (x2-45, x122-165, x96-110), about 1500 px/frame "
                 "on k=0..9 and gone from k=10, about 14400. MegaMan is a DESCRIPTOR defect: "
                 "tools/oracle.py windowclose reads mm_panel_x canon 2 / rust 3 and mm_panel_y "
                 "canon 3 / rust 2 diverging at k=0 on all 40 frames, i.e. CUSTMATCH_ROW\'s "
                 "megaman_col=3/megaman_row=2 against the panel canon\'s own BattleObject holds "
                 "(the same class F20b fixed for HUDMATCH). MEASURED: megaman_col=2, "
                 "megaman_row=3 takes windowclose 648948 -> 612328/26551/40 and OBJ 97644 -> "
                 "46803, and leaves cursor at EXACTLY 620802/6884/170 (unchanged -- the window "
                 "covers him for all 170 of its frames), so unlike the backdrop seed this one "
                 "is safe to share: APPLIED (F29, see CUSTMATCH_ROW's own comment). The enemy is F28\'s: the oracle reads enemy_state_action canon "
                 "(4,11) vs ours (4,9) and enemy_anim canon 1 vs ours 0 from k=0 -- the "
                 "Mettaur\'s attack phase, attributed, not fixed here. ALL THREE TOGETHER, "
                 "measured on one build: windowclose 648948/27391/40 -> 132255/5698/40 "
                 "(negative 208890, not blind), window and card still 0; the TWO THAT LANDED "
                 "here (the camera pan and MegaMan's panel, no backdrop seed) read "
                 "407778/11879/40 (negative 534875, not blind), with BG2 0 on all 40 frames "
                 "and BG3 0 -- what is left is BG1 (the backdrop seed, its own odd-frame "
                 "rounding and its art phase) and the Mettaur. A trap worth the line it costs: "
                 "written as `-x.div_euclid(2)` the fix silently does NOTHING, because unary "
                 "minus binds looser than a method call, so it is `-(x.div_euclid(2))` -- the "
                 "divide-then-negate that rounds toward zero. Measured in that state: BG2 back "
                 "to 7320-7836 px on k=1,3,5,7,9 and 0 on every even frame, the row 433618 "
                 "instead of 407778. Also worth recording: "
                 "the PIXEL negative on this row is not blind, but tools/oracle.py windowclose "
                 "reports its own STATE-field negative as BLIND (a +1-frame canon shift moves "
                 "no first-divergence) -- the state oracle proves nothing on this row until "
                 "that is fixed.\n"
                 "F26b (2026-09-13): the backdrop phase is SEEDED now (WINDOWCLOSE_ROW, see "
                 "its derivation above the descriptor) and BG1 is gone: BG1 alone (--only-bg 1 "
                 "--disable-obj on BOTH sides, identical flags) 877602/22658/40 -> 0/0/40, all "
                 "forty frames, the twenty odd ones included -- so the 'odd-frame rounding' the "
                 "previous paragraph left open is not a defect at all (src/backdrop.rs's scroll "
                 "write carries the proof). Full screen 648948/27391/40 -> 34707/2652/40 on the "
                 "merged tree (F29 had taken it to 407778 on its own). Offset still 253 and now "
                 "sharply so: 34707 against 222040 at 252 and 225712 at 254, where before the "
                 "seed the same band read 648948/659965/673915 -- the event-derived alignment "
                 "and the score minimum now agree by a factor of six. LAYER TABLE, arithmetic "
                 "closed by partitioning the composite instead of summing layer-local totals "
                 "(those double-count: a layer-local diff counts pixels the composite hides "
                 "behind a layer above). Composite 34707 = OBJ-only 34707; BG0/BG1/BG2/BG3 "
                 "layer-local all 0/40 frames, OBJ layer-local 46803 of which 12096 px-frames "
                 "are occluded by the window. Nothing left on this row lives in a background "
                 "layer.\n"
                 "F37 (2026-09-14), PER-OBJECT TABLE, same OAM method (canon 81..120 <-> rust "
                 "261..300). k10..39 read a flat 461 = hand icon 256 + Mettaur pose 205, "
                 "partitioned exactly (icon bbox x59..75 y76..92: 256; Mettaur bbox: 205; "
                 "MegaMan bbox: 0): the icon is this build's pick-in-hand chip at panel "
                 "(2,3)+(-1,-56), drawn once custom is None, while canon draws none (HUD "
                 "draw-mask bit 1 stays 0: 0x4085 open, 0x4495 after close; the OK press "
                 "commits picks to sent-chip data, sub_8029110 -- F18's note). k0 (1174) adds "
                 "the cursor bracket (104 px: canon still draws it on the first slide-out "
                 "frame f81, gone f82+; this build hides it for the whole Closing) and the "
                 "first slide step; k1..k9 (1069..1938) are the 15-px pan ramping down over "
                 "the ten slide calls plus pose. Mask watch (0x020352C0:8): update 0x4487 / "
                 "draw 0x4085 while open (bits 0,1,2,7,10,14 / 0,2,7,14 -- icons 0 on, 1 off "
                 "per sub_801C06E/sub_801C078, HP 2 per sub_801C168, gauge 4, time 7 BCD per "
                 "sub_801C840/sub_801C906, predicate 10, emotion 14 per sub_801CDEC), then "
                 "0x4497/0x4495 from f91 (+update 4, +draw 4/8/10; draw 8 is nullsub). "
                 "BattlePaused reads 1 on all 200 watched frames, 110 past the close, so a "
                 "pause gate must cover the post-close frames too, not just custom-open. "
                 "Same file-scope verdict as cursor: the cited fixes (pan in object Y, icon "
                 "suppression, bracket on the first Closing frame, pause gate + phase seed) "
                 "all live outside this ticket's files; nothing widened. "
                 "F37b (2026-09-14), same three steps (wt/f37b 674d771/d4b4bb3/69e15ac): "
                 "(1) HP pan: 27819/1938 -> 26848/1878. (2) pose seed (4,11/SWING, same "
                 "peeked bytes as cursor: 0x0b04+0x0101 at canon 81 too) + freeze: oracle "
                 "40/40, k10..k15 pose 205 -> 0 range, but letting ticks run post-close "
                 "re-fires the attack (strike + rolling wave from k24, k47 full mayhem), "
                 "so the freeze had to extend past close (window_closed-gated, "
                 "fixture-scoped; default build still resumes). (3) icon suppression "
                 "(name_suppressed gate, mask bit 1 stays 0 post-OK): k10..39 461 -> 205 "
                 "pose-only, total 26848 -> 19168/1878. Remainder, measured: k0 bracket "
                 "104 (custom.rs, out of scope) + first-slide step, k1..k9 pan ramp + "
                 "frozen-frame-0-vs-mid-raise pose, k10..39 the 205 pose frame. BG0/1/2/3 "
                 "layer-local all 0; negatives not blind. "
                 "F37d (2026-09-14), pickaxe prime landed (wt/f37d, battle.rs seed site): "
                 "the 205 was anim-1 frame 0 vs canon's frame 4 (see the `cursor` note "
                 "for the OAM census); priming the seeded SWING 9 executor ticks reads "
                 "12538/1200/40 -> 4943/1116/40 with k10..39 ALL 0. Remainder, measured: "
                 "k0..9 slide frames -- 162px HUD-strip cells (x96-110 y4-18) on even k "
                 "plus the enemy box (x160-191) on odd k (424-1116, worst k7); the "
                 "slide-phase camera rounding lives in battle.rs/custom.rs, out of this "
                 "ticket's files."
                 "F37g (2026-09-14), LAND F37f's mark (merge wt/f37f 0c05e00, custom.rs "
                 "only, no new src edit): windowclose 1458/162/40 -> 0/0/40 isolated "
                 "(negative not blind, 207166), cursor 20/19/170 -> 3/3/170. result "
                 "58457/1676 BEFORE and AFTER (paired control: pre-F37f custom.rs "
                 "rebuilt and recaptured on this base reads the identical 58457/1676, "
                 "negatives 166899 both) -- no results-screen regression from this "
                 "change on this base. Mechanism: F37f's delta vs main is exactly the "
                 "mark object on Closing{x in 12..103}; the result row never enters "
                 "Closing (its rust Side carries no input script, so navigate() never "
                 "runs), hence unreachable there. The bottom-strip residue (x0..135 "
                 "y144..158, canon shows the Cannon40 chip row, rust does not) "
                 "pre-exists on main independent of custom.rs. UNVERIFIED: what draws "
                 "or misses the Cannon40 row (BG content or scroll, not Custom::show "
                 "objects); opening integrated 72499 is likewise identical pre/post "
                 "(pre-existing, out of scope).",
        ),
        rust=lambda ui: Side(rom=plain_rom(), fixture=WINDOWCLOSE_ROW,
                             script="Start@230,A@260"),
        canon=lambda ui: Side(rom=REAL, loadstate=CHIPSELECT, script="Start@50,A@80"),
        canon_variant="canon",
    ),
    Check(
        name="result",
        ui="isolated",
        frames=40,
        align=Align(
            canon_ref=21,
            search=range(0, 60),
            note="AUDIT wave 3c 'zero-enemy' ticket: FIXTURE.md +56 result_elapsed exists and "
                 "src/fixture.rs reads it. AN EARLIER PASS through this file swept it against a "
                 "worktree branched BEFORE that src change merged (result_elapsed=0 and =30 on "
                 "the SAME stale build rendered byte-identical, wrongly read as 'not consumed') "
                 "-- `git merge main` and re-swept with the real implementation: elapsed DOES "
                 "move the picture now (frame 10 e.g.: 10937/15661/17782 px against the "
                 "elapsed=0 baseline for elapsed=10/21/30). pending_src DROPPED -- it is wired. "
                 "SWEPT PROPERLY (this ticket): result_elapsed in {0,2,4,..,40} against "
                 "canon_ref=21 with rust_offset FIXED at 0 (no search) bottoms out at "
                 "elapsed=14 (522212 px) but never gets close to 0, and is a shallow bowl, not a "
                 "sharp minimum (497967 at 0 rising smoothly to a ~535650 plateau by 26+). "
                 "Re-swept the same set WITH the offset search restored (this row's own "
                 "search=range(0,60)) so result_elapsed cannot be fighting a wrong offset: the "
                 "true joint minimum is at result_elapsed=0 (497967, offset=15) -- every other "
                 "sampled elapsed is WORSE (504-505k) once the offset is free to compensate. So "
                 "result_elapsed is not the knob that gets this row toward 0; RESULT_ROW's own "
                 "elapsed=0 already is, or is close to, optimal. LOCALISED the residue instead: "
                 "at offset=15, frame 0 differs over the WHOLE screen (bbox x0-239,y0-159, "
                 "31882 px) and decays frame by frame (30846, 29995, ... 17395 by k=10) to a "
                 "FLAT ~6600-6900 px PLATEAU from k=16 onward that never reaches 0 in the "
                 "40-frame window -- a shape (full-screen early, settling to a stubborn nonzero "
                 "floor, not shrinking further) that matches states.py's own noenemy2 finding "
                 "for this exact fixture family: 'the reward itself is rolled from RNG state "
                 "this recipe does not reach the same way real play did', i.e. RESULT_ARRIVAL's "
                 "own reward content (chip/zenny rolled by real play) has nothing in "
                 "RESULT_ROW/FIXTURE.md to match it against, not a timing field like "
                 "result_elapsed. THE REWARD-CONTENT HYPOTHESIS ABOVE IS NOW DISPROVEN (AUDIT "
                 "wave 3c/3d 'encounter-roll' ticket): decoded RESULT_ARRIVAL's own captured "
                 "frames to PNG and read the window by eye after paging through it (A@70/100/"
                 "130/160/190) -- DeleteTime 0:29:33 (MM:SS:CC, = 29.333s = exactly 1760 frames "
                 "at 60fps), Busting LV. 2, reward 100z, no chip -- EVERY ONE of RESULT_ROW's "
                 "existing result_frames=1760/result_level=2/result_zenny=100 (inherited from "
                 "RESULTMATCH_ROW) already matches this state's own reward EXACTLY, and "
                 "megaman_hp=60 matches too (peeked live: HP 0x3c/MaxHP 0x64 at RESULT_ARRIVAL's "
                 "own frame 0). So the reward-content descriptor field the previous note called "
                 "for is not what's missing -- these three fields were already right. Also ruled "
                 "out: gauge=1 instead of RESULT_ROW's 0 (peeked live: word_20352a0, "
                 "eStruct2035280+0x20, reads 0x4000 -- the same 'full' value 7aw's own gauge-"
                 "fill note gives) changes NOTHING (identical 497967/31882) -- either the gauge "
                 "field is not read for start_state=1 at all, or it is not the source. NOT "
                 "SETTLED, and worth the next session's own measurement rather than a guess: "
                 "RESULT_ARRIVAL's own eBGScrollCBCounters (0x02009690/0x02009694, the backdrop-"
                 "phase clock 7av documents) read 0x0530/0x8298 (1328/-32104 signed) at its own "
                 "frame 0 -- a real elapsed-battle value FIXTURE.md's result_elapsed (already "
                 "swept 0..40, no field wide enough for a number this size even if it were) "
                 "cannot represent, and item 5's own 'pre-arrival battle tail' framing (backdrop "
                 "phase / HP / gauge) named exactly this before HP and gauge were ruled out -- "
                 "backdrop phase is what is left. src/ and FIXTURE.md territory, not tools/. "
                 "F34 DECOMPOSED THE 102547 BY LAYER AND FRAME at this row's own alignment "
                 "(marker origin 13, measured on every capture; offset 21, i.e. canon 21+k <-> "
                 "rust 34+k), identical isolation flags on both sides. The two builds number "
                 "their backgrounds differently: OUR BG0 is canon's BG1 (backdrop), our BG1 is "
                 "canon's BG2 (field panels), our BG2 (the HP box) and our BG3 (the RESULT "
                 "window) are BOTH canon's BG3, and canon's BG0 is blank. LAYER TABLE at this "
                 "branch's 93183 (40 frames): backdrop (our BG0 vs canon BG1) 0 on every frame "
                 "-- its seed is now DERIVED from canon's own counters, see RESULT_ROW's "
                 "comment; field (our BG1 vs canon BG2) a flat 18552 on each of k=0..9 and 0 "
                 "from k=10 (185520 layer-local, most of it behind the window); window+HUD 0 on "
                 "every frame -- our BG3 alone against canon's BG3 reads a constant 704 px at "
                 "(2,0)-(45,15) and our BG2 alone against canon's blank BG0 reads the SAME 704 "
                 "px in the same box (the HP box's layer assignment, not a difference), and our "
                 "BG2 composited under our BG3 against canon's BG3 is 0 on all 40 frames; OBJ "
                 "(--disable-bg both sides) 1532-2088 a frame, 72512 layer-local. PARTITIONED "
                 "(F26b's rule -- layer-local totals double-count what a layer above hides) the "
                 "composite's 93183 = 92760 BG + 423 OBJ, all of it on k=0..9 and all of it "
                 "inside the field's own y72..149 band. THE WINDOW IS EXACT AND THIS ROW DOES "
                 "EXERCISE IT: the slide covers x < 48+16k on both sides through k=11 (F21b's "
                 "tilemap-column slide), the first sub_802C810 write lands at k=14 (80 px change "
                 "inside the prompt box: the setup map's lit line replaced by byte_802C834's "
                 "flat face) and the bit-3 blink toggles 249 px at k=20/21, 28/29 and 36/37 -- "
                 "the same pixels on the same frames on both sides. THE 92760 IS THE INTRO "
                 "FADE: RESULT_ROW carries SceneFlags::SKIP_INTRO, so src/battle.rs USED to start the battle "
                 "with intro_fade = INTRO_SKIP_FADE and darken the field layer and the objects "
                 "for the first ten compared frames, while canon's RESULT_ARRIVAL is 8048 battle "
                 "frames in with no fade left. LANDED (F34b -- this ticket's own three): "
                 "intro_fade = 0 when the fixture's start_state == 1 takes the row 93183 -> "
                 "7316/1878/40 and every BG layer to 0 on all 40 frames; what is left is OBJ "
                 "alone and it decomposes exactly -- canon draws MegaMan at x43..77 y70..113 "
                 "(766 px) and we draw the IDENTICAL 766-px sprite at x83..117, a pure "
                 "one-panel-column +40 px displacement (canon's own BattleObject 0x0203a9b0 "
                 "+0x12 PanelXY reads PanelX 2 / PanelY 2 on every frame of this row's canon "
                 "capture -- BattleObject.inc:63 -- while RESULTMATCH_ROW carries megaman_col=3; "
                 "its megaman_row=2 is right), and we draw an enemy of 385-511 px at x168..189 "
                 "that canon does not draw at all (canon's enemy slot 0x0203aa88 sits in "
                 "CurState 0x08 = CUR_STATE_DESTROY, BattleObject.inc:38, at the row's "
                 "canon_ref: the Mettaur is already deleted when the RESULT window comes up). "
                 "MEASURED, all three on top of each other: megaman_col 3->2 alone 7316 -> "
                 "3330, enemies 1->0 alone 7316 -> 3986, both 7316 -> 0, and with all three the "
                 "row reads PASS total 0 worst 0 frames 40, negative NOT blind (111839). ORDER "
                 "MATTERS: the two descriptor fields WITHOUT the fade change are worth 56 px "
                 "(93183 -> 93127) -- the fade darkens the sprites and the window hides them "
                 "from k=9, so the fade change is what makes the other two visible.",
        ),
        rust=lambda ui: Side(rom=plain_rom(), fixture=RESULT_ROW),
        canon=lambda ui: Side(rom=REAL, loadstate=RESULT_ARRIVAL),
        canon_variant="canon",
    ),
    Check(
        name="banner",
        ui="isolated",
        frames=58,
        align=Align(
            canon_ref=49,
            search=range(115, 145),
            note="banner_at is now read by src/fixture.rs (BANNER_ROW's own banner_at=100 "
                 "verified byte-identical there against demo-banner's own reference, over 200 "
                 "frames -- this note's earlier 'pending-src' was stale, corrected this ticket, "
                 "not re-investigated past that: 2248/58 is zero-src's own item, not this "
                 "ticket's). canon: /tmp/bn6f_banner.gba (tools/patch_sterile.py --keep-banner, "
                 "already built) + PAUSED, enemy HP forced to 0, Start@10 -- unchanged from "
                 "regress.py's check_banner. rust: BANNER_ROW through the descriptor (marker "
                 "origin 1, blanked HUD/backdrop family) plus a band around regress.py's old "
                 "rust_start=132 (132-1=131). "
                 "TODO F9 (2026-09-12): the old 2248/562/58 was the PAUSED route's own deleted-"
                 "enemy corpse, not the banner: every differing pixel sat in the corpse region "
                 "x149-196 y81-117 (ALIGN_CHIP's measurement, frames 43-52) on exactly canon "
                 "frames 49-52 -- the dissolve's last 4 frames, gone by 53; frames 53..106 of "
                 "the window (the banner itself) read exactly 0. Measured on the canon side "
                 "here: the dissolve re-uploads the Mettaur's own OBJ tile DATA at 0x060103E0 "
                 "twice (frames 46 and 49; --watch, 412 of 448 bytes change); the frame-49 "
                 "upload is a 768-byte pre-dithered tile sheet from ROM 0x0839A610 queued "
                 "into the GFX "
                 "transfer queue (slot with dst=0x060103E0, from IWRAM battle code lr "
                 "0x030060B4) and flushed by ProcessGFXTransferQueue (asm00_0.s:830-874) -- "
                 "the death-dissolve gate itself is the still-unfound mechanism asm31.s:169274-"
                 "169296 records (--inert-enemy did not reach it). Fixture content, not src/: "
                 "the rust fixture has no enemy, so the canon side now blanks the element per "
                 "frame (--zero ENEMY_TILES plus ENEMY_DISSOLVE_TAIL for the sheet's 768-byte "
                 "extent, the same per-frame blanking the hide_enemy chip "
                 "rows use) instead of carrying PAUSED's corpse into the window. BANNER_TILES "
                 "(0x06016E00) is disjoint, and the banner text's own uploads observed in the "
                 "same queue dump (dst 0x06016E00..0x060172E0) are all outside ENEMY_TILES, so "
                 "the row's subject is untouched.",
        ),
        rust=lambda ui: Side(rom=plain_rom(), fixture=BANNER_ROW, extra=("--disable-bg",)),
        canon=lambda ui: Side(rom="/tmp/bn6f_banner.gba", loadstate=PAUSED,
                              cheats=("0x0203ab84:0", "0x0203ab86:0"), script="Start@10",
                              zero=(cc.ENEMY_TILES, ENEMY_DISSOLVE_TAIL),
                              pokes_at=(ENEMY_DISSOLVE_SLOT_SIZE,),
                              extra=("--disable-bg",)),
        canon_variant="canon (banner-patched, sterile otherwise)",
    ),
    Check(
        name="popup",
        ui="isolated",
        frames=80,
        align=ALIGN_CHIP,
        # F27b: 0x1F | SceneFlags::HUD_LIVE (FIXTURE.md +19 bit6) -- the ONE thing
        # this row's rust side needs that the other 43 chip rows do not:
        # its canon side is a LIVE battle HUD (element mask 0x020352C0 =
        # 0x4497, bit14 set, on all 125 frames), theirs is a battle already
        # past the HUD teardown (afterdissolve_0x0c, 0x8084, bit14 clear on
        # all 47). Both descriptors are otherwise identical, so the bit is
        # the only place that difference can live -- see the note below.
        rust=_chip_rust("b1", flags=0x5F),
        # F19: was _chip_canon("b1", hide_enemy=True, banner_zero=False) -- the
        # ALIVE enemy acted on canon AI all window (sprite + ticking HP digits,
        # 51991 px in x160-210 y60-125). DELETE (HP 0/0) + the banner row's own
        # per-frame dissolve blanking (ENEMY_TILES + ENEMY_DISSOLVE_TAIL +
        # slot-size poke) leaves the Invisibl popup itself untouched (canon
        # popup frames 65..113 x49, identical before/after) and cuts the enemy
        # box to the early dissolve (6081 px, worst k=0, flat 694 HUD-only
        # from k=10). banner_zero=False stands: the popup glyph tiles live at
        # 0x06016E00 (BANNER_TILES) -- zeroing it kills the subject (measured
        # +29888 center-band).
        # TODO F27 (2026-09-13): the residual 55520 (x2-45 y18-33, flat 694 px
        # on every one of the 80 frames) is NOT an "OBJ HUD HP bar" and is NOT
        # content we lack -- it is the EMOTION WINDOW, the navi's face at the
        # top left, which src/emotion.rs already draws pixel-exactly and which
        # this row gates off. The earlier note here ("rust BLANK_HUD blanks
        # it") is REFUTED: SceneFlags::BLANK_HUD only drops hud_tiles/hud_bg; the
        # emotion window is dropped by src/battle.rs's `fighting` gate, and
        # this row's fixture has enemies=0.
        # Identified by OAM, per frame (--watch 0x7000000:0x400 over the whole
        # canon capture): two objects present on all 125 frames, only the slot
        # moving (2/3 -> 0/1 at f12 -> 8/9 at f61 -> 0/1 at f119) -- (0,18)
        # 32x16 tile 0x3b4 and (32,18) 16x16 tile 0x3bc, OBJ palette 12,
        # priority 2. Exactly what canon's draw routine hardcodes: sub_801CDEC
        # (asm00_2.s:27554-27583) passes 0x80004012/0xCBB4 and
        # 0x40200012/0xCBBC (y=18 x=0 32x16 and y=18 x=32 16x16, tiles
        # 0x3b4/0x3bc, pal 12, prio 2). Its art is the first entry of the
        # per-emotion bank off_801CD08 (asm00_2.s:27488 -> dword_872D814,
        # data/dat38_86.s:26158) + dword_872D914 (:26173), uploaded to
        # 0x06017680 (dword_801CD68, asm00_2.s:27514) by sub_801CB38
        # (asm00_2.s:27240) -- the same bytes assets/emotion.bin already
        # carries (tools/emotion_export.py).
        # Canon's gate is the battle-HUD element enable mask dword_20352C0
        # (eStruct2035280+0x40), dispatched every frame by sub_801BEE0
        # (asm00_2.s:25540-25563); element 14 is the emotion window (updater
        # sub_801CADC at asm00_2.s:25577, draw sub_801CDEC at
        # asm00_2.s:25627), so its bit is 1<<14 = 0x4000 -- the literal
        # sub_802A0F8 passes to hide it (asm03_0.s:8317-8333). MEASURED
        # (--watch 0x20352C0:4): 0x4497, bit14=1, on all 125 frames of THIS
        # row's canon capture; 0x8084, bit14=0, on all 47 frames of the
        # `cannon`/43-chip route (afterdissolve_0x0c, a battle already in its
        # RESULT countdown, whose HUD is torn down). So canon draws it here
        # and genuinely does not draw it there.
        # FIXED F27b (2026-09-13): 60614 -> 5094, this box 0 on all 80 frames
        # (our tiles, palette, position and priority are byte-identical to
        # canon's over 80 consecutive frames). src/battle.rs now follows
        # canon's rule -- the window goes with the HUD TEARDOWN, not with the
        # last enemy: sub_80081A4 (asm00_1.s:10617-10621) clears elements 0,
        # 1, 4, 10 and 14 in one sub_801BED6(0xE4C53) on the frame the banner
        # sequencer enters its RESULT countdown 0x0C. Measured on the REAL rom
        # under this row's own recipe (PAUSED, enemy HP forced to 0, Start@10,
        # --disable-bg): dword_203CA70 goes 0x08 -> 0x0C at frame 47, the mask
        # goes 0x4497 -> 0x0084 at frame 48 (--watch-write 0x20352C0:4:
        # at=0x0801BEDC lr=0x080081B9), bit15 goes back up for the ENEMY
        # DELETED banner (sub_801E792, asm00_2.s:31055-31112) which runs
        # 49..106. So canon holds the window through the enemy's whole
        # dissolve -- 47 frames of it -- where ours used to drop it at the
        # death, and the STERILE rom this row uses never concludes, so canon
        # holds it for all 125 frames here.
        # The flags bit above is not a rendering switch, it is which canon
        # STATE this row's canon capture sits in: this row and the 43 chip
        # rows share one descriptor (_chip_rust, enemies=0, flags=0x1F) and
        # their canon sides are on opposite sides of that teardown, so no rule
        # computed from our own state can tell them apart. A zero-enemy arena
        # has no canon counterpart at all; a fixture that fields an enemy
        # needs no bit (see src/fixture.rs's SceneFlags::HUD_LIVE).
        # The remaining 5094 (x149-196 y81-126) is the enemy's dissolve,
        # F28's Mettaur phase.
        canon=lambda ui: Side(rom=STERILE, loadstate=PAUSED,
                              cheats=DELETE_ENEMY + ("%s:0xb1" % cc.HAND_SLOT,),
                              pokes=_chip_pokes("b1"),
                              zero=(cc.ENEMY_TILES, ENEMY_DISSOLVE_TAIL,
                                    ENEMY_DISSOLVE_FIRST_PHASE),
                              pokes_at=(ENEMY_DISSOLVE_SLOT_SIZE,)
                                       + ENEMY_DISSOLVE_QUEUE_KILL,
                              script="Start@10,A@40", extra=("--disable-bg",)),
        canon_variant="canon (sterile)",
        # No pending_src -- this is fully expressible today. Kept as its own
        # named row (regress.py's check_popup, Invisibl b1 as the
        # representative) rather than five: the OTHER four family-0x15
        # chips (AreaGrab a3, Barrier b2, Barr100 b3, Barr200 b4) are
        # already the 43-chip scoreboard's own chip-areagrab/chip-barrier/
        # chip-barr100/chip-barr200 rows above, same recipe, not
        # duplicated here.
    ),
]

CHECKS.extend(PORTED_CHECKS)


#: rollup (AUDIT ticket step 1): not a comparison -- a no-crash check, run
#: through the SAME capture path (cc.capture / mgba_capture) every other
#: check here uses, per the ticket ("keep it as one, but run it through the
#: harness's capture path"). regress.py's own method, reimplemented here
#: rather than imported (regress.py is not edited by this ticket): three
#: long input scripts on the plain build, watching for a frame that is more
#: than half pure white AND still is 150 frames later (agb's crash screen
#: never clears; a battle-opening white hold, ~71 frames on this build,
#: always does).
ROLLUP_WALKS = [
    ["Up", "Left", "Down", "Left", "Up", "Right", "Down", "Left", "Right", "Up"],
    ["Up", "Left", "Down", "Left", "Up", "Right", "Down", "Left"],
    ["Right", "Right", "Up", "Down", "Left", "Up", "Right", "Down", "Down"],
]
ROLLUP_FRAMES = 2600
ROLLUP_LINGER = 150


def run_rollup() -> Tuple[int, str]:
    rom = plain_rom()
    last = ROLLUP_FRAMES - 50
    total, notes = 0, []
    for w, keys in enumerate(ROLLUP_WALKS):
        script = [held(keys[i % len(keys)], at, 3) for i, at in enumerate(range(60, last, 19))]
        script += [held("B", at, 2) for at in range(70, last, 11)]
        script += [held("A", at, 2) for at in range(100, last, 37)]
        out = cc.scratch("h_rollcap%d" % w)
        cc.capture(rom, out, ROLLUP_FRAMES, "--script", ",".join(script))

        def crashed(i):
            px = cc.frame_array(out, i)
            sampled = px[0:160:2, 0:240:2]
            white = int(np.count_nonzero(np.all(sampled == 255, axis=-1)))
            return white > sampled.shape[0] * sampled.shape[1] // 2

        bad = [i for i in range(60, ROLLUP_FRAMES - ROLLUP_LINGER, 5)
               if crashed(i) and crashed(i + ROLLUP_LINGER)]
        subprocess.run(["rm", "-rf", out], check=True)
        total += len(bad)
        if bad:
            notes.append("walk %d white by frame %d" % (w, bad[0]))
    return total, "; ".join(notes) or "no crash, %d walks of %d frames" % (
        len(ROLLUP_WALKS), ROLLUP_FRAMES)


#: The pre-harness box each ported check used to score 0 inside of --
#: reported alongside the full-screen number so "how much of the residue was
#: never measured" (AUDIT pair 6) has an actual figure, not just the claim.
#: None for checks that had no box (there weren't any before this ticket).
OLD_BOX: Dict[str, Optional[Tuple[int, int, int, int]]] = {
    # opening's isolated variant reads 0 at full screen (no box needed, see
    # the report) -- there is no residue to attribute, so no figure here.
    "opening": None,
    "mettaur": (145, 0, 240, 160),   # regress.py's check_mettaur: "the Mettaur's half of the screen"
    "cannon": (0, 40, 140, 160),     # chip_compare.py's default box (navi's half, below the HUD)
}


# --------------------------------------------------------------------------
# The gallery (AUDIT pair 7): every run writes its own comparison, win or
# lose, in the existing web/captures/*.gif style -- real/canon above, ours
# below, a divider band, both scaled 2x (matched empirically against
# web/captures/battle-opening-hud-compare.gif: a 3-native-pixel band of
# (70, 70, 80) between two full-width halves).
GIF_SCALE = 2
GIF_DELAY_CS = 2
DIVIDER_COLOR = (70, 70, 80)
DIVIDER_PX = 3


def write_gallery(check: Check, ui: str, result: Result):
    os.makedirs(WEB_CAPTURES, exist_ok=True)
    w, h = 240, 160
    n = len(result.counts)
    sheet_h = h * 2 + DIVIDER_PX
    frames = []
    for k in range(n):
        canon_im = cc.frame(result.canon_dir, result.canon_ref + k)
        rust_im = cc.frame(result.rust_dir, result.rust_origin + result.rust_offset + k)
        sheet = Image.new("RGB", (w, sheet_h), DIVIDER_COLOR)
        sheet.paste(canon_im, (0, 0))
        sheet.paste(rust_im, (0, h + DIVIDER_PX))
        frames.append(sheet.resize((w * GIF_SCALE, sheet_h * GIF_SCALE), Image.NEAREST))

    base = "%s-%s" % (check.name, ui)
    gif_path = os.path.join(WEB_CAPTURES, base + ".gif")
    frames[0].save(gif_path, save_all=True, append_images=frames[1:],
                   duration=GIF_DELAY_CS * 10, loop=0, optimize=True)

    rev = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT,
                         capture_output=True, text=True).stdout.strip() or "unknown"
    caption = (
        "%s (%s), %s: per-frame max %d px, total %d px over %d frames. "
        "Alignment: canon frame %d+k, rust frame %d(marker)+%d+k. %s\n\n%s\n\n"
        "commit %s" % (
            check.name, ui, "PASS (all zero)" if result.ok else "FAILED",
            result.worst, result.total, n,
            result.canon_ref, result.rust_origin, result.rust_offset,
            check.canon_variant, check.align.note, rev,
        )
    )
    with open(os.path.join(WEB_CAPTURES, base + ".txt"), "w") as f:
        f.write(caption)
    return gif_path


# --------------------------------------------------------------------------
# Provenance (AUDIT pair 12): how many constants the current zeros rest on
# without a known mechanism. `src/` is another agent's territory this
# ticket -- grep only, never edit.
PROVENANCE_RE = re.compile(r"//\s*provenance:\s*(derived|peeked|fitted)\b")


def provenance_counts() -> Dict[str, int]:
    counts = {"derived": 0, "peeked": 0, "fitted": 0}
    src = os.path.join(ROOT, "src")
    if not os.path.isdir(src):
        return counts
    for dirpath, _, filenames in os.walk(src):
        for fn in filenames:
            if not fn.endswith(".rs"):
                continue
            path = os.path.join(dirpath, fn)
            try:
                with open(path, encoding="utf-8", errors="replace") as f:
                    text = f.read()
            except OSError:
                continue
            for m in PROVENANCE_RE.finditer(text):
                counts[m.group(1)] += 1
    return counts


# --------------------------------------------------------------------------


def _allowed(name: str, ui: str, worst: int) -> Optional[Tuple[bool, str, int]]:
    """tools/allowlist.py lookup (AUDIT pair 11): "check:ui" beats "check".
    Returns (within_limit, ticket, max_px) or None if nothing is allowlisted.
    """
    for key in ("%s:%s" % (name, ui), name):
        if key in ALLOWLIST:
            max_px, ticket, _date = ALLOWLIST[key]
            return worst <= max_px, ticket, max_px
    return None


def _old_box_figure(check: Check, result: Result) -> Optional[Tuple[int, int]]:
    """(boxed total, outside total) against the box `check` used to score 0
    in before this ticket -- AUDIT pair 6's "everything outside the box is
    unmeasured" made concrete. Must run BEFORE run_check() deletes the
    capture directories."""
    box = OLD_BOX.get(check.name)
    if box is None:
        return None
    boxed_total = sum(cc.diff_frames(result.canon_dir, result.canon_ref + k, result.rust_dir,
                                      result.rust_origin + result.rust_offset + k, box)
                      for k in range(len(result.counts)))
    return boxed_total, result.total - boxed_total


def run_check(check: Check, *, gallery: bool = True, only_ui: Optional[str] = None) -> Dict[str, dict]:
    """Every ui variant of `check`: the positive run, its negative fixture
    (pair 10), and, if `gallery`, a written comparison GIF (pair 7). Returns
    {ui: {result, negative, blind, ok, allowed, box}}.

    Deletes both capture directories before returning -- AUDIT pair 13:
    "leaving them behind is how /tmp reached 37 GB" is regress.py's own
    scar tissue (see check_rollup's comment there), so anything read out of
    `result.rust_dir`/`canon_dir` (the gallery GIF, the old-box figure) has
    to happen here, before the cleanup, not later from a dict of paths that
    no longer resolve to anything.
    """
    variants = ("isolated", "integrated") if check.ui == "both" else (check.ui,)
    if only_ui:
        variants = tuple(v for v in variants if v == only_ui)
    sides = {ui: (check.rust(ui), check.canon(ui)) for ui in variants}
    # Resolve (build) every ROM up front, serially, so the parallel runs below
    # never race cargo or the ROM cache.
    for r, c in sides.values():
        for side in (r, c):
            if not side.capture_fn:
                side.resolved_rom()

    def one(ui):
        rust_side, canon_side = sides[ui]
        result = run(rust_side, canon_side, check.frames, check.align,
                     variant_label=ui, serial=check.serial)
        neg = negative_counts(result, check.frames, kind=check.negative)
        blind = all(c == 0 for c in neg)
        allowed = _allowed(check.name, ui, result.worst)
        box = _old_box_figure(check, result)
        gif_path = write_gallery(check, ui, result) if gallery else None
        subprocess.run(["rm", "-rf", result.rust_dir, result.canon_dir], check=True)
        return ui, {
            "result": result, "negative": neg, "blind": blind,
            "ok": result.ok, "allowed": allowed, "gif": gif_path, "box": box,
        }

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=len(variants) or 1) as pool:
        results = list(pool.map(one, variants))
    return {ui: o for ui, o in sorted(results, key=lambda kv: variants.index(kv[0]))}


def _fmt_row(name, ui, r: Result, neg, blind, allowed, box):
    extra = ""
    if box is not None:
        boxed_total, outside = box
        pct = (100.0 * outside / r.total) if r.total else 0.0
        extra = " | old-box %d, outside %d (%.0f%%)" % (boxed_total, outside, pct)
    if r.ok:
        status = "PASS"
    elif allowed is not None:
        within, ticket, max_px = allowed
        status = "FAILED (allowed: %s, <=%d)" % (ticket, max_px) if within else \
                 "FAILED (WORSE than allowed: %s, <=%d)" % (ticket, max_px)
    else:
        status = "FAILED"
    neg_status = "BLIND" if blind else "not blind (total %d)" % sum(neg)
    print("%-10s %-11s %-32s total %-8d worst %-6d frames %-4d%s | negative: %s" % (
        name, ui, status, r.total, r.worst, len(r.counts), extra, neg_status))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated check names")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--no-gallery", action="store_true", help="skip writing web/captures/*.gif")
    ap.add_argument("--ui", choices=("isolated", "integrated"), help="run only this ui variant of each row (a worker's inner loop; landing runs both)")
    args = ap.parse_args()

    # Q4 self-check: the committed docs/oracle_layout.json must still be what
    # src/battle.rs's ORACLE_LAYOUT table generates, and tools/oracle.py's
    # reader must read the same offsets -- never measure against a stale reader.
    import oracle_layout
    oracle_layout.self_check()

    if args.list:
        for c in CHECKS:
            pending = "  [pending-src: %s]" % c.pending_src if c.pending_src else ""
            print("%-10s ui=%-11s frames=%d%s" % (c.name, c.ui, c.frames, pending))
        print("%-10s ui=%-11s frames=%d  (no-crash check, not a comparison)" %
              ("rollup", "n/a", ROLLUP_FRAMES))
        return 0

    wanted = set(args.only.split(",")) if args.only else None
    failed = 0
    blind_any = False
    for check in CHECKS:
        if wanted and check.name not in wanted:
            continue
        try:
            outcome = run_check(check, gallery=not args.no_gallery, only_ui=args.ui)
        except Exception as exc:
            print("%-10s ERROR %s" % (check.name, exc))
            failed += 1
            continue
        pending = "  [pending-src: %s]" % check.pending_src if check.pending_src else ""
        for ui, o in outcome.items():
            _fmt_row(check.name, ui, o["result"], o["negative"], o["blind"], o["allowed"], o["box"])
            if pending:
                print(pending)
            if not o["ok"] and o["allowed"] is None:
                failed += 1
            elif not o["ok"] and o["allowed"] is not None and not o["allowed"][0]:
                failed += 1
            if o["blind"]:
                failed += 1
                blind_any = True

    if wanted is None or "rollup" in wanted:
        got, note = run_rollup()
        state = "PASS" if got == 0 else "FAILED"
        print("%-10s %-11s %-32s %s" % ("rollup", "n/a", state, note))
        if got:
            failed += 1

    if not args.no_gallery:
        subprocess.run(["python3", os.path.join(ROOT, "tools", "captures_manifest.py")],
                       cwd=ROOT, check=True)

    prov = provenance_counts()
    print("\nfitted constants: %d (derived %d, peeked %d)" % (
        prov["fitted"], prov["derived"], prov["peeked"]))

    if blind_any:
        print("%d check(s) FAILED, at least one BLIND (negative fixture read 0)" % failed)
    elif failed:
        print("%d check(s) FAILED" % failed)
    else:
        print("all checks pass: every compared frame reads 0")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
