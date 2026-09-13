#!/usr/bin/env python3
"""Compare one chip's animation between the real ROM and the Rust build,
frame for frame, in the sterile arena.

usage: chip_compare.py <chip_id_hex> <demo-feature> [--frames N] [--out DIR]
   e.g. chip_compare.py 47 demo-sword

Real side: /tmp/bn6f_sterile.gba from /tmp/pausedwithcannon.state, the enemy
deleted, the ENEMY DELETED banner's tiles blanked, backgrounds off, the hand's
first chip poked to the id, A pressed at frame 40 (the attack begins at 43).
Rust side: a --release build with demo-sterile, the given chip demo feature
and demo-auto, which fires the hand on its own. The attack starts are
aligned on the first frame that differs from the idle, and every frame from
the start is diffed within x<140 (the real ROM keeps the deleted Mettaur's
remnant at x>=149). A strip of real/rust/diff crops is written for looking.

Chips that do not move the navi (Recov) give the aligner nothing to go on:
pass --rust-start 123, the frame the sterile demo's auto-fire uses its chip.

A chip that needs a live target (StepSwrd steps to the enemy's column) has
nothing to work with once the enemy is deleted, so it gets --hide-enemy: the
enemy stays alive and immortal and its tiles are blanked every frame. That is
not a better default -- a live enemy is hit, and its sparks, damage numbers
and the navi's Full Synchro all land in the diff -- Cannon scores 0 with the
enemy deleted and 346 px/frame with it hidden, and the hit puts the navi into
Full Synchro, which rewrites its palette bank in place and quietly changes
every colour you are trying to compare. Use it only where the chip cannot work
without a target, and only before the strike lands.

Every comparison carries one unavoidable artifact: the ENEMY DELETED banner
is drawn 39 frames after the Start press and its tiles are written after the
per-frame blanking pass, so it shows for exactly one frame -- a 369 px band at
y 70..74, always the attack's frame 6. It cannot be moved: the banner lands at
Start+39, the game refuses a chip press later than about Start+38 (A at 48
with Start at 10 does nothing at all), so the banner is always just inside the
attack. Read a lone 369 at c06 as zero.

Keep --frames inside the attack: the real capture presses A once, while the
Rust demo's auto-fire starts the next use as soon as the navi is free, so
frames past the attack's end compare a second volley against an idle navi.
SuprVulc, at 112 frames the longest, needs --frames 113.

Needs /tmp/mgba_capture (tools/mgba_capture.c) and the real ROM/state, which
are never committed (TRANSFER.md).
"""

import hashlib
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageChops

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
CAPTURE = "/tmp/mgba_capture"
STERILE = "/tmp/bn6f_sterile.gba"
STATE = "/tmp/pausedwithcannon.state"
HAND_SLOT = "0x020349c2"
BANNER_TILES = "0x6016E00:1280"
# The Mettaur's object tiles, blanked every frame to leave the arena as empty
# as deleting the enemy does while the enemy stays alive and targetable. The
# game refuses a chip press once the deletion sequence has run (--a-frame and a
# post-deletion save state both hit the refusal), so this is the only way to
# capture a chip that needs something to aim at. Its HP counter is drawn from
# tiles the banner blanking already covers. Found by decoding OAM (objects 9,
# 10 and 14, palette 1, tiles 31..44) from `--dump 0x7000000:1024`.
ENEMY_TILES = "0x60103E0:448"
# The A press, and the frame the attack's effect starts. Deleting the enemy
# leaves it dissolving on the right for about a hundred frames, which is why
# the diff window stops at x<140; --a-frame exists to press later than that,
# but the game refuses a chip once the deletion sequence has finished, so it
# does not actually work.
REAL_A_FRAME = 40


def load(path):
    return Image.frombytes("RGBA", (240, 160), open(path, "rb").read()).convert("RGB")


def frame(dirname, i):
    return load(os.path.join(dirname, "frame.%05d.rgb" % i))


def frame_path(dirname, i):
    return os.path.join(dirname, "frame.%05d.rgb" % i)


def load_array(path):
    """A raw frame.#####.rgb file as a (160, 240, 3) uint8 array.

    mgba_capture.c writes each pixel as 4 bytes, R,G,B,x (mgba_frames.py's
    decode() comment; the 4th byte is mGBA's unused high byte of its 32-bit
    native colour, not real alpha). Reshape straight into rows x cols x
    channel and drop that 4th byte -- no PIL round trip, which is most of
    what made the old per-pixel comparison slow (Image.frombytes + a Python
    loop over 38,400 pixel tuples)."""
    raw = np.fromfile(path, dtype=np.uint8)
    return raw.reshape(160, 240, 4)[:, :, :3]


def frame_array(dirname, i):
    return load_array(frame_path(dirname, i))


def _count_diff(a, b):
    """Count of pixels where the (h, w, 3) uint8 arrays `a` and `b` differ in
    any channel. Written as an explicit 3-way OR of per-channel not-equal
    masks rather than `np.any(a != b, axis=-1)` -- both give the same
    answer, but np.any's generic reduction over a length-3 trailing axis
    takes its own generic path and measured ~8x slower than just OR-ing the
    three (h, w) boolean planes together directly, on frames this size."""
    d = a != b
    return int(np.count_nonzero(d[..., 0] | d[..., 1] | d[..., 2]))


def diff_frames(dir_a, fa, dir_b, fb, box=None):
    """Count of differing pixels between frame `fa` of `dir_a` and frame `fb`
    of `dir_b`, optionally restricted to a (x0, y0, x1, y1) box -- the
    vectorised replacement for the pure-Python "sum(1 for ... if p[x,y] !=
    q[x,y])" loop that used to back every diff in the project (AUDIT pair 13
    / Optimisations table: "vectorise the pixel diff with numpy... likely
    50-100x, bigger than any parallelism"). See load_array() for the file
    format; comparison is RGB only, matching the old convert("RGB") drop of
    the 4th byte."""
    a = frame_array(dir_a, fa)
    b = frame_array(dir_b, fb)
    if box is not None:
        x0, y0, x1, y1 = box
        a = a[y0:y1, x0:x1]
        b = b[y0:y1, x0:x1]
    return _count_diff(a, b)


XMAX = 140
# With --bg the real ROM keeps its field, background and HUD, so the whole
# screen is compared rather than the navi's half.
BACKGROUNDS = False


#: An explicit diff window, for a fixture that wants one region rather than the
#: navi's half: --box 24,30,100,50 is the chip-name popup and nothing else.
BOX = None


def differs(a, b, box=None):
    """Differing-pixel count between two already-loaded PIL images (as
    frame() returns), vectorised with numpy. Kept for the strip/alignment
    code below that already has Images in hand from frame(); new code with
    a directory and a frame number should call diff_frames() instead and
    skip the PIL conversion entirely -- that is where the real speedup is."""
    box = box or BOX or ((0, 0, 240, 160) if BACKGROUNDS else (0, 40, XMAX, 160))
    x0, y0, x1, y1 = box
    pa = np.asarray(a)[y0:y1, x0:x1]
    pb = np.asarray(b)[y0:y1, x0:x1]
    return _count_diff(pa, pb)


LIBRARY = 0x020008A0
LIBRARY_COPY = 0x02004C20


def peek16(addr):
    out = subprocess.run(
        [CAPTURE, STERILE, scratch("chip_compare_peek"), "0", "--loadstate", STATE,
         "--peek", "0x%08x" % addr],
        capture_output=True, text=True,
    )
    for line in (out.stdout + out.stderr).splitlines():
        if line.startswith("peek"):
            return int(line.split("=")[1], 16)
    raise RuntimeError("peek failed")


def library_pokes(chip_id):
    """The hand validation (someChipHandValidationHappensHere_800B090,
    asm00_1.s:17303) swaps any chip the library does not hold for the bug
    chip 0x185: encryption_testPack_8006e84 wants byte_20008A0[id] ^ 0x81 ==
    byte_2004C20[id]. The state's library lacks HiCannon, LongSwrd and
    Barrier, so give the chip a count of 1 and its copy 0x80, keeping the
    neighbouring byte of the halfword the harness writes."""
    pokes = []
    for base, value in ((LIBRARY, 1), (LIBRARY_COPY, 1 ^ 0x81)):
        addr = base + chip_id
        half = addr & ~1
        old = peek16(half)
        new = (old & 0xff00) | value if addr == half else (old & 0x00ff) | (value << 8)
        pokes += ["--poke", "0x%08x:0x%04x" % (half, new)]
    return pokes


def _frames_written(out, diff_file):
    """How much output a capture actually produced: .rgb files in `out`
    normally, or -- in streaming mode, where none of those exist -- the
    number of per-frame records already appended to `diff_file` (its size
    in u32s; see capture()'s docstring and mgba_capture.c's --diff-against)."""
    if diff_file:
        return os.path.getsize(diff_file) // 4 if os.path.exists(diff_file) else 0
    return len([f for f in os.listdir(out) if f.endswith(".rgb")])


#: How many emulator captures may run at once on this machine, across every
#: process (harness, verify_rows, a worker's own probes): a machine-wide
#: semaphore of flock'd slot files. The rule used to be "never two at once"
#: because captures came up short under memory pressure; the count check and
#: retry in capture() catch that, and 3 slots on a 12-core, 15 GB box leave
#: plenty of headroom while letting a row's independent captures overlap.
CAPTURE_SLOTS = int(os.environ.get("BN_CAPTURE_SLOTS", "3"))


class capture_slot:
    """Context manager: hold one of CAPTURE_SLOTS machine-wide slots."""
    def __enter__(self):
        import fcntl, time
        while True:
            for i in range(CAPTURE_SLOTS):
                f = open("/tmp/bn-capslot-%d" % i, "w")
                try:
                    fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    self.f = f
                    return self
                except OSError:
                    f.close()
            time.sleep(0.25)

    def __exit__(self, *exc):
        import fcntl
        fcntl.flock(self.f, fcntl.LOCK_UN)
        self.f.close()


def capture(rom, out, count, *args, retries=2):
    """Run mgba_capture and make sure it actually produced `count` frames of
    output before trusting it, re-running up to `retries` times on a short
    capture instead of failing outright.

    AUDIT pair 13: captures under memory pressure used to write fewer frames
    than asked, silently -- the frames that exist compare normally and the
    ones that don't either raise deep in a check or never get asked for.
    regress.py's own capture() (which this is meant to replace, see its
    docstring there) catches the short count but only to raise; a machine
    that was briefly busy gets a wasted run instead of a working one. This
    gives it a couple of quiet retries first and only raises if it is still
    short after all of them.

    Works for both capture styles: a normal run writes frame.#####.rgb into
    `out`, and streaming mode (`--diff-against <dir>:<lag>:<file>` somewhere
    in `args`, see mgba_capture.c) writes none of those -- it appends one
    differing-pixel count per rendered frame to <file> instead, so short is
    judged by how many of those records exist rather than by listing `out`.
    """
    diff_file = None
    for i, a in enumerate(args):
        if a == "--diff-against" and i + 1 < len(args):
            diff_file = args[i + 1].rsplit(":", 1)[-1]

    got = -1
    for attempt in range(retries + 1):
        subprocess.run(["rm", "-rf", out], check=True)
        if diff_file:
            subprocess.run(["rm", "-f", diff_file], check=True)
        with capture_slot():
            subprocess.run([CAPTURE, rom, out, str(count), *args], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        got = _frames_written(out, diff_file)
        if got == count:
            return
        if attempt < retries:
            print("capture wrote %d of %d frames to %s -- retrying (%d/%d)" %
                  (got, count, diff_file or out, attempt + 1, retries), file=sys.stderr)
    raise SystemExit(
        "capture wrote %d of %d frames to %s -- the box was probably busy; "
        "re-run it alone before believing any number from this run" %
        (got, count, diff_file or out))


def scratch(name=""):
    """A /tmp working directory unique to THIS checkout of the project.

    Every capture and packed ROM used to go to a fixed path -- /tmp/rg_field.gba,
    /tmp/rust_demo-cannon.gba, /tmp/chip_compare -- which is fine for one person
    and wrong the moment two agents run a check at once: the second overwrites
    the first's ROM between its build and its capture, and the number that comes
    out looks perfectly normal. Keying the directory on the checkout's real path
    means a git worktree gets its own, automatically, with nothing to remember.
    """
    key = hashlib.sha1(os.path.realpath(ROOT).encode()).hexdigest()[:8]
    d = "/tmp/bn-%s" % key
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, name) if name else d


_TARGET_DIR = None


def target_dir():
    """Where cargo ACTUALLY puts the build, asked of cargo rather than assumed.

    This was a hardcoded `ROOT/target` and that made the project's own advice
    dangerous: every agent is told to set `CARGO_TARGET_DIR` so two builds
    cannot race, `cargo build` honours it, and the ROM was then packed from
    `ROOT/target` anyway -- so a private target directory meant measuring
    whatever stale ELF happened to be sitting in the repo, with no error and a
    plausible-looking number. `cargo metadata` knows the answer however it was
    set, environment or config.toml alike.
    """
    global _TARGET_DIR
    if _TARGET_DIR is None:
        out = subprocess.run(["cargo", "metadata", "--format-version", "1", "--no-deps"],
                             cwd=ROOT, check=True, capture_output=True, text=True).stdout
        _TARGET_DIR = json.loads(out)["target_directory"]
    return _TARGET_DIR


