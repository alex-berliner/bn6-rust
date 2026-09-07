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

Keep --frames inside the attack: the real capture presses A once, while the
Rust demo's auto-fire starts the next use as soon as the navi is free, so
frames past the attack's end compare a second volley against an idle navi.
SuprVulc, at 112 frames the longest, needs --frames 113.

Needs /tmp/mgba_capture (tools/mgba_capture.c) and the real ROM/state, which
are never committed (TRANSFER.md).
"""

import argparse
import os
import subprocess
import sys

from PIL import Image, ImageChops

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
CAPTURE = "/tmp/mgba_capture"
STERILE = "/tmp/bn6f_sterile.gba"
STATE = "/tmp/pausedwithcannon.state"
HAND_SLOT = "0x020349c2"
BANNER_TILES = "0x6016E00:1280"
# The A press, and the frame the attack's effect starts. Deleting the enemy
# leaves it dissolving for about a hundred frames with a screen flash at the
# end; a chip that moves the navi toward that remnant (StepSwrd) needs the
# press late enough for it to be gone, hence --a-frame.
REAL_A_FRAME = 40
REAL_START = 43


def load(path):
    return Image.frombytes("RGBA", (240, 160), open(path, "rb").read()).convert("RGB")


def frame(dirname, i):
    return load(os.path.join(dirname, "frame.%05d.rgb" % i))


XMAX = 140
# With --bg the real ROM keeps its field, background and HUD, so the whole
# screen is compared rather than the navi's half.
BACKGROUNDS = False
KEEP_ENEMY = False


def differs(a, b, box=None):
    box = box or ((0, 0, 240, 160) if BACKGROUNDS else (0, 40, XMAX, 160))
    d = ImageChops.difference(a.crop(box), b.crop(box))
    return sum(1 for px in d.getdata() if px != (0, 0, 0))


LIBRARY = 0x020008A0
LIBRARY_COPY = 0x02004C20


def peek16(addr):
    out = subprocess.run(
        [CAPTURE, STERILE, "/tmp/chip_compare_peek", "0", "--loadstate", STATE,
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


def capture_real(chip, out, count):
    subprocess.run(["rm", "-rf", out])
    cmd = [
        CAPTURE, STERILE, out, str(count),
        "--loadstate", STATE,
        # The enemy is deleted so only the navi and its chip are on screen.
        # KEEP_ENEMY makes it immortal instead, for a chip that moves the navi
        # toward where the deleted one would be dissolving (StepSwrd): the
        # remnant and its screen flash would otherwise land in the window.
        *(["--cheat", "0x0203ab84:0xffff", "--cheat", "0x0203ab86:0xffff"]
          if KEEP_ENEMY else
          ["--cheat", "0x0203ab84:0", "--cheat", "0x0203ab86:0"]),
        *library_pokes(int(chip, 16)),
        "--cheat", f"{HAND_SLOT}:0x{chip}",
        "--zero", BANNER_TILES,
        *([] if BACKGROUNDS else ["--disable-bg"]),
        "--script", f"Start@10,A@{REAL_A_FRAME}",
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def build_and_capture_rust(feature, out, count):
    # With backgrounds the Rust side needs its field and HUD, so the sterile
    # arena is left out; the demo feature places the navi itself.
    features = f"{feature},demo-auto" if BACKGROUNDS else f"demo-sterile,{feature},demo-auto"
    subprocess.run(
        ["cargo", "build", "--release", "--features", features],
        cwd=ROOT, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    rom = "/tmp/rust_%s.gba" % feature
    subprocess.run(
        ["python3", os.path.join(ROOT, "tools", "gbafix.py"),
         os.path.join(ROOT, "target", "thumbv4t-none-eabi", "release", "bn"), rom],
        check=True, stdout=subprocess.DEVNULL,
    )
    subprocess.run(["rm", "-rf", out])
    subprocess.run([CAPTURE, rom, out, str(count)], check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


BODY = (8, 57, 123)


def body_box(im):
    pts = [(x, y) for x in range(0, 140) for y in range(40, 160) if im.getpixel((x, y)) == BODY]
    if not pts:
        return None
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    return (min(xs), max(xs), min(ys), max(ys), len(pts))


def first_body_change(dirname, idle_index, from_index, to_index):
    """The first frame whose navi body box differs from the idle's. The whole
    frame cannot be used: the real capture has the deleted Mettaur's remnant
    dissolving on the right and HUD objects blinking, none of which is the
    attack."""
    idle = body_box(frame(dirname, idle_index))
    for i in range(from_index, to_index):
        if body_box(frame(dirname, i)) != idle:
            return i
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("chip")
    ap.add_argument("feature")
    ap.add_argument("--frames", type=int, default=60, help="frames to diff from the start")
    ap.add_argument("--rust-frames", type=int, default=260)
    ap.add_argument("--out", default="/tmp/chip_compare")
    ap.add_argument("--no-build", action="store_true")
    ap.add_argument("--keep-enemy", action="store_true",
                    help="leave the real capture's enemy alive (immortal) instead of deleting it")
    ap.add_argument("--a-frame", type=int, default=40,
                    help="frame the real capture presses A (default 40); raise it to let the deleted enemy finish dissolving")
    ap.add_argument("--bg", action="store_true",
                    help="keep the real ROM's backgrounds and compare the whole screen")
    ap.add_argument("--xmax", type=int, default=140,
                    help="right edge of the diff window (the real capture's deleted Mettaur remnant sits at x>=149 for ~45 frames)")
    ap.add_argument("--rust-start", type=int, default=None,
                    help="the Rust frame of the attack's start, for chips that do not move the navi (demo-auto fires at 122)")
    args = ap.parse_args()
    global XMAX, BACKGROUNDS, KEEP_ENEMY, REAL_A_FRAME, REAL_START
    KEEP_ENEMY = args.keep_enemy
    REAL_A_FRAME = args.a_frame
    REAL_START = REAL_A_FRAME + 3
    BACKGROUNDS = args.bg
    XMAX = 240 if args.bg else args.xmax
    real = os.path.join(args.out, "real_" + args.chip)
    rust = os.path.join(args.out, "rust_" + args.feature)
    os.makedirs(args.out, exist_ok=True)
    capture_real(args.chip, real, REAL_START + args.frames + 5)
    if not args.no_build:
        build_and_capture_rust(args.feature, rust, args.rust_frames)

    # The real attack starts at 43; align on the first frame the navi's body
    # changes on each side (the same number of frames after the start on
    # both, since the lead-in is the game's).
    if args.rust_start is not None:
        real_first = REAL_START
        rust_start = args.rust_start
    else:
        real_first = first_body_change(real, REAL_A_FRAME, REAL_START, REAL_START + 20)
        rust_first = first_body_change(rust, 100, 101, args.rust_frames - args.frames)
        if real_first is None or rust_first is None:
            print("no attack seen: real", real_first, "rust", rust_first)
            sys.exit(1)
        rust_start = rust_first - (real_first - REAL_START)
    print(f"real start {REAL_START} (first change {real_first}); rust start {rust_start}")

    total = 0
    worst = []
    for c in range(args.frames):
        r = frame(real, REAL_START + c)
        u = frame(rust, rust_start + c)
        d = differs(r, u)
        total += d
        worst.append((d, c))
        print("c%02d %5d" % (c, d), end="\n" if c % 6 == 5 else "  ")
    print("\nmean %.1f px/frame; worst %s" % (total / args.frames, sorted(worst)[-5:]))

    # A strip of the frames that differ most, plus the first and last.
    picks = sorted({0, args.frames - 1} | {c for _, c in sorted(worst)[-7:]})
    strip = Image.new("RGB", (100 * len(picks), 70 * 3 + 6), (40, 40, 40))
    for i, c in enumerate(picks):
        r = frame(real, REAL_START + c).crop((30, 50, 130, 120))
        u = frame(rust, rust_start + c).crop((30, 50, 130, 120))
        d = ImageChops.difference(r, u).point(lambda v: 255 if v else 0)
        strip.paste(r, (i * 100, 0))
        strip.paste(u, (i * 100, 73))
        strip.paste(d, (i * 100, 146))
    path = os.path.join(args.out, f"strip_{args.feature}.png")
    strip.resize((strip.width * 2, strip.height * 2), Image.NEAREST).save(path)
    print("frames", picks, "->", path)


if __name__ == "__main__":
    main()
