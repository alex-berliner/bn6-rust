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


def _cannon_canon(ui: str) -> Side:
    # chip_compare.py's capture_real("01", ...) IS this check's canon side:
    # STERILE + PAUSED, the enemy deleted, Cannon (chip 01) poked into the
    # hand and the library, the banner blanked, backgrounds off, A pressed
    # at frame 40. Reused rather than reimplemented (its library_pokes()
    # step needs a throwaway capture of its own to peek the state's
    # library, which does not fit the static-Side model below).
    return Side(rom=STERILE, capture_fn=lambda out, count: cc.capture_real("01", out, count))


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
        align=Align(
            canon_ref=43,
            search=range(110, 136),
            note="canon: chip_compare.py's REAL_START=43 (A pressed at 40, 'the attack "
                 "begins at 43') -- a documented scripted-event landing, not searched. rust: "
                 "marker origin (frame 1 for demo-sterile,demo-cannon,demo-auto -- SEE HOW "
                 "FAR THIS IS FROM demo-open/demo-field's frame 8, which is exactly why a "
                 "fixed boot-length offset was never going to work for every build) plus a "
                 "26-frame band for the auto-fired attack's own timing -- unique zero at "
                 "offset 122.",
        ),
        rust=lambda ui: Side(features="demo-sterile,demo-cannon,demo-auto", extra=("--disable-bg",)),
        canon=_cannon_canon,
        canon_variant="canon (sterile)",
    ),
]

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
            print("%-10s ui=%-11s frames=%d" % (c.name, c.ui, c.frames))
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
        for ui, o in outcome.items():
            _fmt_row(check.name, ui, o["result"], o["negative"], o["blind"], o["allowed"], o["box"])
            if not o["ok"] and o["allowed"] is None:
                failed += 1
            elif not o["ok"] and o["allowed"] is not None and not o["allowed"][0]:
                failed += 1
            if o["blind"]:
                failed += 1
                blind_any = True

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
