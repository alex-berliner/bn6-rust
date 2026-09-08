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
    buf[5] = descriptor.get("enemy_kind", 0)
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


def run(rust: Side, canon: Side, frames: int, align: Align) -> Result:
    """Capture both sides, align them, and return the full 240x160
    differing-pixel count for `frames` consecutive frames -- AUDIT pair 6:
    one harness, one job, no boxes.
    """
    key = hashlib.sha1(repr((rust, canon, frames, align)).encode()).hexdigest()[:10]
    rust_dir = cc.scratch("h_rust_%s" % key)
    canon_dir = cc.scratch("h_canon_%s" % key)
    watch_file = cc.scratch("h_watch_%s.bin" % key)

    upper = max(align.search) if align.search is not None else align.rust_offset
    rust_count = MARKER_MARGIN + upper + frames
    canon_count = align.canon_ref + frames + NEGATIVE_MARGIN

    rust.do_capture(rust_dir, rust_count, watch_file=watch_file)
    canon.do_capture(canon_dir, canon_count)

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


def negative_counts(result: Result, frames: int, delta: int = 1) -> List[int]:
    """AUDIT pair 10: the SAME captures and the SAME alignment this check
    just found, with the canon side shifted by `delta` frames -- not
    re-searched, on purpose. Re-running the search could find a different
    offset that also reads 0 on a periodic fixture, which would prove
    nothing; reusing the found offset and only moving the canon reference is
    what actually tests whether the check can fail.
    """
    return [cc.diff_frames(result.canon_dir, result.canon_ref + delta + k,
                           result.rust_dir, result.rust_origin + result.rust_offset + k)
            for k in range(frames)]


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


def _cannon_canon(ui: str) -> Side:
    # Cannon (chip 01) is just the chip family's own row now -- see
    # _chip_canon()'s comment for what changed and why.
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


def _chip_rust(chip_hex: str) -> Callable[[str], Side]:
    desc = {
        "enemies": 0, "megaman_hp": 100, "megaman_col": 2, "megaman_row": 2,
        "hand": [int(chip_hex, 16)], "hand_count": 1, "gauge": 0,
        "flags": 0x1F, "fire_frame": 90,
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


def _chip_checks() -> List[Check]:
    import scoreboard
    out: List[Check] = []
    for feature, chip_hex, frames, extra in scoreboard.CHIPS:
        name = "chip-" + feature[len("demo-"):]
        hide_enemy = "--hide-enemy" in extra
        banner_zero = "--no-banner-zero" not in extra
        out.append(Check(
            name=name,
            ui="isolated",
            frames=frames,
            align=ALIGN_CHIP,
            rust=_chip_rust(chip_hex),
            canon=_chip_canon(chip_hex, hide_enemy=hide_enemy, banner_zero=banner_zero),
            canon_variant="canon (sterile)",
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
                 "rust: find_marker_origin() gives frame 8 for demo-open; a 21-wide band "
                 "around it finds a UNIQUE zero at offset 119 (partial band shown in the "
                 "report), the residual sub-frame timing the marker alone does not pin.",
        ),
        rust=lambda ui: Side(features="demo-open",
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
            search=range(145, 161),
            note="canon: STERILE+PAUSED+ALIVE, Start@10 -- a scripted press with no clock "
                 "shared with rust's cold boot, so canon_ref=140 is the same documented fixed "
                 "point regress.py's check_mettaur used (its own frame-140 window start), not "
                 "searched. rust: marker origin (frame 8 for demo-field) plus a 16-frame band "
                 "for the Mettaur's own attack-cycle timing -- unique zero at offset 153, i.e. "
                 "rust frame 161, EXACTLY regress.py's old lag-21 answer (140+21 == 8+153).",
        ),
        rust=lambda ui: Side(features="demo-field", extra=("--disable-bg",)),
        canon=lambda ui: Side(rom=STERILE, loadstate=PAUSED, cheats=ALIVE, script="Start@10",
                              extra=("--disable-bg",)),
        canon_variant="canon (sterile)",
    ),
    Check(
        name="cannon",
        ui="isolated",
        frames=40,
        align=ALIGN_CHIP,
        rust=lambda ui: Side(features="demo-sterile,demo-cannon,demo-auto", extra=("--disable-bg",)),
        canon=_cannon_canon,
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
HUDMATCH = dict(enemies=1, enemy_kind=0, enemy_col=5, enemy_row=3, megaman_hp=60,
                megaman_col=3, megaman_row=2, hand=[1], hand_count=1, gauge=1,
                flags=0x10, art_entry=5, art_timer=4, scroll_xq=424, scroll_yq=724)
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
            search=range(415, 440),
            note="canon: regress.py's TILES_REAL_FRAME=44, fixed (PAUSED+Start@10 is a "
                 "documented scripted landing, not searched). rust: marker origin 8 "
                 "(demo-hudmatch's own family) plus a 25-frame band around regress.py's old "
                 "center (435-8=427) -- %s. NOT boxed: regress.py split this same capture "
                 "into `tiles` (y>=24, backgrounds) and `gauge` (y<24, HUD strip) precisely "
                 "because the HUD strip carries a KNOWN, unresolved defect (TODO A8, the "
                 "gauge's stripe animation) that would otherwise contaminate a background-only "
                 "reading -- full screen (pair 6) can no longer keep them apart by cropping, so "
                 "both rows now read the SAME whole-screen number and the HUD defect is "
                 "reported (and allowlisted, not hidden) on both." % subject_note,
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
ZERO_ENEMY = dict(enemies=0, megaman_hp=100, megaman_col=2, megaman_row=2,
                  hand=[], hand_count=0, gauge=0, flags=0x11)
ZERO_ENEMY_ORIGIN = 8

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
DELETE_ENEMY = ("0x0203ab84:0", "0x0203ab86:0")


def _zero_enemy_canon(script: str) -> Callable[[str], Side]:
    def make(ui: str) -> Side:
        return Side(rom=STERILE, loadstate=PAUSED, cheats=DELETE_ENEMY,
                    script=script,
                    extra=() if ui == "integrated" else ("--disable-bg",))
    return make


def _zero_enemy_rust(script: Optional[str] = None) -> Callable[[str], Side]:
    def make(ui: str) -> Side:
        return Side(rom=plain_rom(), fixture=ZERO_ENEMY, script=script,
                    extra=() if ui == "integrated" else ("--disable-bg",))
    return make


def held(key: str, first: int, n: int) -> str:
    """A key script that holds `key` for `n` frames from `first` --
    regress.py's own helper (unchanged; regress.py itself is not edited)."""
    return ",".join("%s@%d" % (key, first + j) for j in range(n))


#: demo-field's row, fixture.rs's table -- VERIFIED BYTE-IDENTICAL there.
#: enemy_hp: 0xFFFF here is not "use the default" (see fixture_cheats()'s
#: comment on that sentinel mismatch) -- it is the LITERAL value
#: demo-field's own Rust source bakes in (FIELDMATCH_HP) and what the real
#: capture's `--cheat 0x0203ab84/86:0xffff` (ALIVE, below) pins the real
#: Mettaur's HP to: a huge number that is never going to reach 0, not a
#: sentinel. Marker origin 8 (measured live), same family as demo-open.
FIELD_ROW = dict(enemies=1, enemy_kind=0, enemy_col=5, enemy_row=2, megaman_hp=100,
                 megaman_col=2, megaman_row=2, hand=[1], hand_count=1, gauge=0,
                 flags=0x11, art_entry=5, art_timer=4, scroll_xq=424, scroll_yq=724,
                 enemy_hp=0xFFFF)
FIELD_ORIGIN = 8

#: demo-custmatch's row (demo-cardname is a feature alias, not a different
#: descriptor -- fixture.rs's table). The offered deck is NOT expressible
#: now read by src/fixture.rs (see its own table's "WAVE 3 ADDITIONS" and
#: "WAVE 3 VERIFICATION" comments -- 371/862px residual on 2 of 200 frames,
#: in the card-picture region, not from the deck/window fields themselves;
#: zero-src's own ticket). window_cursor=0xa (OK) matches demo-custmatch's
#: own capture. Marker origin 8 (measured live).
CUSTMATCH_ROW = dict(enemies=1, enemy_kind=0, enemy_col=5, enemy_row=3, megaman_hp=100,
                     megaman_col=3, megaman_row=2, hand=[], hand_count=0, gauge=1,
                     flags=0x11,
                     deck_count=5, deck=[5, 4, 71, 54, 1],
                     deck_codes=[3, 0xFF, 18, 0xFF, 0xFF],
                     window_pick_count=1, window_pick_slot=4, window_cursor=0xa)
CUSTMATCH_ORIGIN = 8

#: demo-cardname's row -- IDENTICAL to CUSTMATCH_ROW in every column except
#: window_cursor (0 = cursor on the first slot, showing the card's NAME
#: rather than the OK confirmation message -- fixture.rs's own table
#: comment; `card` below is demo-cardname's check, `window` is
#: demo-custmatch's).
CARDNAME_ROW = dict(CUSTMATCH_ROW, window_cursor=0)

#: `window`/`card` isolated variants: CUSTMATCH_ROW/CARDNAME_ROW with
#: FLAG_BLANK_HUD|FLAG_BLANK_BACKDROP added on top of their own
#: FLAG_OPEN_WINDOW|FLAG_SKIP_INTRO (0x11 | 0x06 = 0x17), so nothing but
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
RESULT_ROW = dict(RESULTMATCH_ROW, result_elapsed=0)

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
                 "40-frame stretch cannot tell a 1-frame canon shift from no shift at all).",
        ),
        rust=_zero_enemy_rust("Start@10"),
        canon=_zero_enemy_canon("Start@10"),
        canon_variant="canon (sterile)",
    ),
    Check(
        name="warp",
        ui="both",
        frames=30,
        align=Align(
            canon_ref=130,
            search=range(30, 70),
            note="canon: Right/Down/Left/Up held 3 frames each starting real 130 (past the "
                 "DELETE dissolve, see `field`'s note; regress.py's old real 60/80/100/120 "
                 "shifted by the same +70 the dissolve wait needs), canon_ref=130 = the first "
                 "press. rust: the SAME held-key SHAPE at battle-relative frames 50/70/90/110 "
                 "(marker origin 8 + those, no dissolve to wait out on this side -- it never "
                 "had an enemy) instead of regress.py's old cold-boot guesses (130/150/170/190, "
                 "tuned to a boot length that moves); a 40-wide search band around the first "
                 "press covers plausible input-lag between a resumed real battle and a fresh "
                 "fixture one. Full-screen pixel diff (pair 6) replaces regress.py's own coarse "
                 "blue-pixel position tracking -- strictly more rigorous, not a relaxation.",
        ),
        rust=_zero_enemy_rust(",".join([held("Right", 8 + 50, 3), held("Down", 8 + 70, 3),
                                        held("Left", 8 + 90, 3), held("Up", 8 + 110, 3)])),
        canon=_zero_enemy_canon(",".join(["Start@10", held("Right", 130, 3), held("Down", 150, 3),
                                          held("Left", 170, 3), held("Up", 190, 3)])),
        canon_variant="canon (sterile)",
    ),
    Check(
        name="buster",
        ui="both",
        frames=32,
        align=Align(
            canon_ref=150,
            search=range(90, 130),
            note="canon: regress.py's check_buster's press (STERILE+PAUSED+DELETE, "
                 "Start@10,B@150,B@151) shifted from the old real 60/61 to past the DELETE "
                 "dissolve (see `field`'s note) -- canon_ref=150 = the press. rust: B held at "
                 "battle-frame 100/101 (marker origin 8 + 100/101), not the first tried "
                 "(origin+22) -- verified live that a press that early is BEFORE the navi is "
                 "free to act at all (the diff at that offset was the SAME idle-pose-settling "
                 "transition `field` has, not a shot); battle-frame 100 is well past it, in the "
                 "same order as fire_frame's own 90-frame gap (battle.rs's AUTO_FIRE_GAP).",
        ),
        rust=_zero_enemy_rust(held("B", 8 + 100, 2)),
        canon=_zero_enemy_canon("Start@10," + held("B", 150, 2)),
        canon_variant="canon (sterile)",
    ),
    Check(
        name="chip-use",
        ui="both",
        frames=32,
        align=Align(
            canon_ref=150,
            search=range(90, 130),
            note="Same shape as `buster`, A instead of B: canon Start@10,A@150,A@151 (past the "
                 "DELETE dissolve; PAUSED's own queued Cannon, see ZERO_ENEMY_WITH_HAND, is "
                 "what A actually uses), rust A held at marker origin 8 + 100/101, hand=[1] "
                 "(Cannon, matching PAUSED) -- ZERO_ENEMY's own empty hand would make an A "
                 "press use nothing at all, which is what the first attempt at this check did.",
        ),
        rust=lambda ui: Side(rom=plain_rom(), fixture=ZERO_ENEMY_WITH_HAND,
                             script=held("A", 8 + 100, 2),
                             extra=() if ui == "integrated" else ("--disable-bg",)),
        canon=_zero_enemy_canon("Start@10," + held("A", 150, 2)),
        canon_variant="canon (sterile)",
    ),
    Check(
        name="wave",
        ui="isolated",
        frames=90,
        align=Align(
            canon_ref=71,
            search=range(178, 202),
            note="Enemy IS the subject (AUDIT pair 3: mettaur and wave get their own checks "
                 "rather than a zero-enemy arena). canon: STERILE+PAUSED+ALIVE, Start@10, "
                 "--disable-obj (panel lighting is BG, not sprites) -- canon_ref=71 unchanged "
                 "from regress.py's check_wave (the shockwave's first visible hop). rust: "
                 "FIELD_ROW through the descriptor (not the demo-field FEATURE `mettaur` above "
                 "still uses -- this is the wave 3 cutover) -- marker origin 8 plus a band "
                 "around regress.py's old compared rust frame (start=71 PLUS lag[120,132] = "
                 "191..203, 183..195 once origin is subtracted).",
        ),
        rust=lambda ui: Side(rom=plain_rom(), fixture=FIELD_ROW, extra=("--disable-obj",)),
        canon=lambda ui: Side(rom=STERILE, loadstate=PAUSED, cheats=ALIVE, script="Start@10",
                              extra=("--disable-obj",)),
        canon_variant="canon (sterile)",
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
                 "= the window's own layer, not the whole screen: canon --only-bg 3 (measured "
                 "live, this ticket -- BG3 is the chip-select window itself; BG1 is a flat fill, "
                 "BG2 the field panels underneath), which also turns OBJ/WIN off "
                 "(tools/mgba_capture.c's own --only-bg behaviour); rust gets FLAG_BLANK_HUD | "
                 "FLAG_BLANK_BACKDROP added on top of CUSTMATCH_ROW's own flags so nothing but "
                 "the window renders there either -- ISOLATED_CUSTMATCH_ROW, not a --only-bg on "
                 "the rust side (its window may not live on the same BG index; matching by "
                 "content, not by layer number). canon: REAL+CHIPSELECT unchanged otherwise. "
                 "rust: marker origin 8 plus a band around regress.py's old compared rust frame "
                 "(its own start=55 PLUS lag[174,190] = 229..245, 221..237 once origin is "
                 "subtracted).",
        ),
        rust=lambda ui: Side(rom=plain_rom(), fixture=ISOLATED_CUSTMATCH_ROW),
        canon=lambda ui: Side(rom=REAL, loadstate=CHIPSELECT, extra=("--only-bg", "3")),
        canon_variant="canon",
    ),
    Check(
        name="card",
        ui="isolated",
        frames=16,
        align=Align(
            canon_ref=144,
            search=range(205, 240),
            note="Same wiring as `window` (deck fields land, --only-bg 3 isolates the window "
                 "layer on canon, ISOLATED_CARDNAME_ROW blanks HUD/backdrop on rust). canon: "
                 "REAL+CHIPSELECT, the SAME 5-press-Left script as `cursor` below. rust: "
                 "ISOLATED_CARDNAME_ROW (window_cursor=0, the one byte that distinguishes "
                 "demo-cardname from demo-custmatch) with the same script -- marker origin 8 "
                 "plus a band around regress.py's old compared rust frame (start=144 PLUS "
                 "lag[74,96] = 218..240, 210..232 once origin is subtracted).",
        ),
        rust=lambda ui: Side(rom=plain_rom(), fixture=ISOLATED_CARDNAME_ROW, script=_CURSOR_WALK_REAL),
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
                 "box removed, full screen, all 170 frames.",
        ),
        rust=lambda ui: Side(features="demo-custmatch", script=_CURSOR_WALK_RUST),
        canon=lambda ui: Side(rom=REAL, loadstate=CHIPSELECT, script=_CURSOR_WALK_REAL),
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
                 "src/fixture.rs reads it as of the 'zero-layers' merge (landed on main after "
                 "this row was first written) -- but CHECKED, NOT LIVE (this ticket's "
                 "fresh-state half): the full-table number (497967/31882) is IDENTICAL before "
                 "and after that merge, which is what sent this back for verification rather "
                 "than trusted. CONFIRMED the descriptor write itself is correct: "
                 "Side(fixture=dict(RESULT_ROW, result_elapsed=21)).args() ends in '--cheat "
                 "0x02000078:0x0015' -- FIXTURE_ADDR+56, value 21, exactly right. CONFIRMED, by "
                 "sweeping result_elapsed over {0,10,21,30} on the SAME plain_rom() build (no "
                 "canon side, no alignment involved) and diffing all 40 frames of each pair "
                 "pixel-for-pixel: EVERY pair reads 0 -- result_elapsed=0 and result_elapsed=30 "
                 "render byte-identical output over the whole capture. So this is not an "
                 "alignment/canon_ref problem (that could only ever explain which canon frame "
                 "is compared, never make two DIFFERENT rust-side values render the same "
                 "picture) -- the field is being read into the fixture struct but not yet "
                 "consumed anywhere that affects a rendered frame. pending_src stays (restored "
                 "-- an earlier pass through this file dropped it on the untested assumption "
                 "that 'src reads it' meant 'src uses it'; it does not). RESULT_ROW carries "
                 "result_elapsed=0 (FIXTURE.md: 'the slide-in starts on the first battle "
                 "frame'). canon_ref moved from wave 3b's 0 to 21 regardless -- states.py's own "
                 "measurement that RESULT_ARRIVAL's slide-in runs canon frames 21..32, so THIS "
                 "row compares against canon's slide-in itself once the rust side actually "
                 "produces one. search=range(0,60) is still UNVERIFIED and unnarrowed. Wave 3b's "
                 "own note: start_state=1 alone (no result_elapsed) produces a period-~8 'press "
                 "to continue' blink, not a slide-in, so the row is BLIND to the slide-in phase "
                 "until result_elapsed is both read AND applied. NEXT STEP (src/, not tools/): "
                 "find where src/fixture.rs's Fixture::result_elapsed is stored and confirm "
                 "whether the RESULT-window timer/state machine ever reads that field back.",
        ),
        rust=lambda ui: Side(rom=plain_rom(), fixture=RESULT_ROW),
        canon=lambda ui: Side(rom=REAL, loadstate=RESULT_ARRIVAL),
        canon_variant="canon",
        pending_src="result_elapsed (+56) -- src/fixture.rs reads the field (verified: the "
                    "descriptor cheat pokes the right address/value) but nothing downstream "
                    "consumes it yet -- verified by sweep, 0 px difference across a full "
                    "40-frame capture between result_elapsed=0 and =30 on the SAME rust build "
                    "(AUDIT wave 3c fresh-state ticket).",
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
                 "rust_start=132 (132-1=131).",
        ),
        rust=lambda ui: Side(rom=plain_rom(), fixture=BANNER_ROW, extra=("--disable-bg",)),
        canon=lambda ui: Side(rom="/tmp/bn6f_banner.gba", loadstate=PAUSED,
                              cheats=("0x0203ab84:0", "0x0203ab86:0"), script="Start@10",
                              extra=("--disable-bg",)),
        canon_variant="canon (banner-patched, sterile otherwise)",
    ),
    Check(
        name="popup",
        ui="isolated",
        frames=80,
        align=ALIGN_CHIP,
        rust=_chip_rust("b1"),
        canon=_chip_canon("b1", hide_enemy=True, banner_zero=False),
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


def run_check(check: Check, *, gallery: bool = True) -> Dict[str, dict]:
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
    out = {}
    for ui in variants:
        rust_side = check.rust(ui)
        canon_side = check.canon(ui)
        result = run(rust_side, canon_side, check.frames, check.align)
        neg = negative_counts(result, check.frames)
        blind = all(c == 0 for c in neg)
        allowed = _allowed(check.name, ui, result.worst)
        box = _old_box_figure(check, result)
        gif_path = write_gallery(check, ui, result) if gallery else None
        subprocess.run(["rm", "-rf", result.rust_dir, result.canon_dir], check=True)
        out[ui] = {
            "result": result, "negative": neg, "blind": blind,
            "ok": result.ok, "allowed": allowed, "gif": gif_path, "box": box,
        }
    return out


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
    args = ap.parse_args()

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
            outcome = run_check(check, gallery=not args.no_gallery)
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
