#!/usr/bin/env python3
"""Run EVERY parity check this project has, in one command.

usage: python3 regress.py [--only NAME,...] [--list]

The chip scoreboard covers 43 chip animations; everything else -- the battle
screen's tiles, a whole frame with sprites, the chip window, the preview card,
the RESULT window, the navi's warp, the buster, a chip use -- was being run by
hand, one fixture at a time, which is how a regression in one of them survives
a session spent on another. Each check below rebuilds its own ROM, captures
both sides, aligns them the way that fixture is aligned, and prints the number
the fixture is judged on against the number it should be.

The last check is not a comparison at all: it runs the full battle under a long
input script and asserts it does not crash, which is the one thing a fixture
with two objects on an empty arena can never tell you.

A check's `want` is the measured truth as of the last time it was verified,
not an aspiration: several are non-zero because that residue is understood and
recorded in TRANSFER.md. The exit status is non-zero if any check comes out
WORSE than its `want`; a check that comes out better prints BETTER and the
number should be written down here.

Needs /tmp/mgba_capture, the real ROM and the save states, which are never
committed. tools/patch_sterile.py must have been run:

    python3 tools/patch_sterile.py /tmp/bn6f_real.gba /tmp/bn6f_sterile.gba
"""

import argparse
import os
import subprocess
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chip_compare as cc  # noqa: E402  (needs the path set first)

CAPTURE = "/tmp/mgba_capture"
REAL = "/tmp/bn6f_real.gba"
STERILE = "/tmp/bn6f_sterile.gba"
PAUSED = "/tmp/pausedwithcannon.state"
CHIPSELECT = "/tmp/chipselect.state"
NOENEMY = "/tmp/noenemy2.state"
#: Keeping the capture's Mettaur alive, which most fixtures want.
ALIVE = ["--cheat", "0x0203ab84:0xffff", "--cheat", "0x0203ab86:0xffff"]


def capture(rom, out, count, *args):
    subprocess.run(["rm", "-rf", out], check=True)
    subprocess.run([CAPTURE, rom, out, str(count), *args],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def build(features, rom):
    subprocess.run(["cargo", "build", "--release", "--features", features], cwd=ROOT,
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(["python3", os.path.join(ROOT, "tools", "gbafix.py"),
                    os.path.join(ROOT, "target/thumbv4t-none-eabi/release/bn"), rom],
                   check=True, stdout=subprocess.DEVNULL)


def diff(a, fa, b, fb, box):
    x0, y0, x1, y1 = box
    p, q = cc.frame(a, fa).load(), cc.frame(b, fb).load()
    return sum(1 for y in range(y0, y1) for x in range(x0, x1) if p[x, y] != q[x, y])


def best(a, fa, b, frames, box):
    """The smallest difference over a window of candidate rust frames."""
    return min(diff(a, fa, b, f, box) for f in frames)


def held(key, first, n):
    """A key script that holds `key` for `n` frames from `first`."""
    return ",".join("%s@%d" % (key, first + j) for j in range(n))


# --------------------------------------------------------------------------


def check_chips():
    out = subprocess.run(["python3", os.path.join(ROOT, "tools", "scoreboard.py")],
                         cwd=ROOT, capture_output=True, text=True)
    line = [l for l in out.stdout.splitlines() if l.endswith("exact")][-1]
    exact, total = int(line.split()[0]), int(line.split()[2])
    bad = [l.split()[0] for l in out.stdout.splitlines() if l and "EXACT" not in l and l[0] == "d"]
    return total - exact, "%d of %d exact, off: %s" % (exact, total, " ".join(bad))


def check_tiles():
    build("demo-hudmatch", "/tmp/rg_hud.gba")
    capture(REAL, "/tmp/rg_tr", 60, "--loadstate", PAUSED, "--script", "Start@10", "--disable-obj")
    capture("/tmp/rg_hud.gba", "/tmp/rg_tu", 400, "--disable-obj")
    return best("/tmp/rg_tr", 43, "/tmp/rg_tu", range(340, 400), (0, 0, 240, 160)), "whole screen"


def check_field():
    build("demo-field", "/tmp/rg_field.gba")
    capture(STERILE, "/tmp/rg_fr", 100, "--loadstate", PAUSED, *ALIVE,
            "--disable-bg", "--script", "Start@10")
    capture("/tmp/rg_field.gba", "/tmp/rg_fu", 400, "--disable-bg")
    return best("/tmp/rg_fr", 90, "/tmp/rg_fu", range(190, 240), (0, 0, 240, 160)), "whole screen"


def check_window():
    build("demo-custmatch", "/tmp/rg_cm.gba")
    capture(REAL, "/tmp/rg_wr", 60, "--loadstate", CHIPSELECT)
    capture("/tmp/rg_cm.gba", "/tmp/rg_wu", 260)
    return best("/tmp/rg_wr", 59, "/tmp/rg_wu", range(236, 252), (0, 0, 112, 160)), "window only"


def check_card():
    build("demo-cardname", "/tmp/rg_cn.gba")
    capture(REAL, "/tmp/rg_kr", 160, "--loadstate", CHIPSELECT,
            "--script", ",".join(held("Left", 20 + 30 * k, 6) for k in range(5)))
    capture("/tmp/rg_cn.gba", "/tmp/rg_ku", 260)
    return best("/tmp/rg_kr", 159, "/tmp/rg_ku", range(238, 250), (0, 0, 112, 160)), "card + window"


def check_result():
    build("demo-resultmatch", "/tmp/rg_res.gba")
    capture(REAL, "/tmp/rg_rr", 40, "--loadstate", NOENEMY)
    capture("/tmp/rg_res.gba", "/tmp/rg_ru", 200)
    return best("/tmp/rg_rr", 39, "/tmp/rg_ru", range(150, 175), (26, 24, 215, 155)), "window + badge"


def check_warp():
    build("demo-field", "/tmp/rg_field.gba")
    capture(STERILE, "/tmp/rg_mr", 120, "--loadstate", PAUSED, *ALIVE,
            "--zero", "0x6016E00:1280", "--disable-bg",
            "--script", "Start@10," + ",".join(
                held(k, at, 3) for k, at in (("Right", 60), ("Down", 80), ("Left", 100), ("Up", 120))))
    capture("/tmp/rg_field.gba", "/tmp/rg_mu", 300, "--disable-bg",
            "--script", ",".join(
                held(k, at, 3) for k, at in (("Right", 130), ("Down", 150), ("Left", 170), ("Up", 190))))
    blue = (0, 132, 222)

    def navi(d, f):
        px = cc.frame(d, f).load()
        pts = [(x, y) for y in range(50, 150) for x in range(240) if px[x, y] == blue]
        return (min(p[0] for p in pts), min(p[1] for p in pts)) if pts else None

    same = sum(1 for k in range(30) if navi("/tmp/rg_mr", 60 + k) == navi("/tmp/rg_mu", 130 + k))
    return 30 - same, "%d of 30 navi positions" % same


def check_buster():
    build("demo-field", "/tmp/rg_field.gba")
    capture(STERILE, "/tmp/rg_br", 100, "--loadstate", PAUSED, *ALIVE,
            "--zero", "0x6016E00:1280", "--disable-bg", "--script", "Start@10,B@60,B@61")
    capture("/tmp/rg_field.gba", "/tmp/rg_bu", 200, "--disable-bg", "--script", "B@130,B@131")
    return sum(diff("/tmp/rg_br", 60 + k, "/tmp/rg_bu", 130 + k, (0, 50, 120, 150))
               for k in range(32)), "navi half, 32 frames"


#: Direction cycles for the rollup check. ONE script is not enough: the walk
#: it produces decides which enemies the navi meets and how long it survives,
#: and the two crashes this check exists for came out of two different walks
#: -- one 362 frames into a fight, the other at a chip window that only opens
#: if the navi is still alive when the gauge fills, some 1650 frames in.
ROLLUP_WALKS = [
    ["Up", "Left", "Down", "Left", "Up", "Right", "Down", "Left", "Right", "Up"],
    ["Up", "Left", "Down", "Left", "Up", "Right", "Down", "Left"],
    ["Right", "Right", "Up", "Down", "Left", "Up", "Right", "Down", "Down"],
]
ROLLUP_FRAMES = 2600


#: The five family-0x15 chips and the box the popup lives in. The scoreboard
#: already runs these chips, but its window starts at y=40 and the popup runs
#: y=32..48, so it only ever sees the bottom half. This box takes the whole
#: strip bar its top two rows, which the real ROM's HP box overlaps at x<46.
POPUP_CHIPS = [("demo-areagrab", "a3"), ("demo-invisibl", "b1"), ("demo-barrier", "b2"),
               ("demo-barr100", "b3"), ("demo-barr200", "b4")]
POPUP_BOX = "24,34,100,52"


def check_popup():
    """The chip-name popup, over its whole life, for every chip that has one."""
    total, notes = 0, []
    for feature, chip in POPUP_CHIPS:
        out = subprocess.run(
            ["python3", os.path.join(ROOT, "tools", "chip_compare.py"), chip, feature,
             "--frames", "77", "--rust-start", "123", "--hide-enemy", "--no-banner-zero",
             "--box", POPUP_BOX],
            cwd=ROOT, capture_output=True, text=True)
        line = [l for l in out.stdout.splitlines() if l.startswith("mean ")]
        if not line:
            notes.append("%s FAILED" % feature)
            total += 1
            continue
        mean = float(line[0].split()[1])
        if mean:
            notes.append("%s %.1f" % (feature, mean))
        total += int(mean * 77)
    return total, "; ".join(notes) or "%d chips, whole popup" % len(POPUP_CHIPS)


def check_banner():
    """The ENEMY DELETED banner: art, palette, position and roll-out.

    The real side is the sterile arena's own save state with the enemy's HP
    forced to zero and Start pressed at frame 10, which puts the banner up on
    frames 49..106; `demo-banner` puts this build's up on its clock's 100th
    frame, which is capture frame 132. The box stops at x=145 because the
    deleted enemy's remnant dissolves to the right of it for a hundred frames.
    """
    build("demo-sterile,demo-banner", "/tmp/rg_ban.gba")
    # The sterile ROM has the banner patched OUT, which is what every chip
    # comparison needs and exactly what this one cannot have.
    subprocess.run(["python3", os.path.join(ROOT, "tools", "patch_sterile.py"),
                    REAL, "/tmp/bn6f_banner.gba", "--keep-banner"],
                   check=True, stdout=subprocess.DEVNULL)
    capture("/tmp/bn6f_banner.gba", "/tmp/rg_banr", 120, "--loadstate", PAUSED,
            "--cheat", "0x0203ab84:0", "--cheat", "0x0203ab86:0",
            "--disable-bg", "--script", "Start@10")
    capture("/tmp/rg_ban.gba", "/tmp/rg_banu", 220)
    box = (40, 56, 145, 88)
    return (sum(diff("/tmp/rg_banr", 49 + k, "/tmp/rg_banu", 132 + k, box) for k in range(58)),
            "58 frames of the banner")


def check_rollup():
    """The full battle, under several long input scripts, must not crash.

    Every other check here puts one or two objects on an empty arena, which is
    why none of them caught the game running out of object palette banks 362
    frames into a real fight (7an). agb's crash screen is a white page, and a
    battle frame never is, so counting frames that are more than half pure
    white finds it without knowing what the panic said.
    """
    build("default", "/tmp/rg_roll.gba")
    last = ROLLUP_FRAMES - 50
    total, notes = 0, []
    for w, keys in enumerate(ROLLUP_WALKS):
        script = [held(keys[i % len(keys)], at, 3) for i, at in enumerate(range(60, last, 19))]
        script += [held("B", at, 2) for at in range(70, last, 11)]
        script += [held("A", at, 2) for at in range(100, last, 37)]
        out = "/tmp/rg_rollcap%d" % w
        capture("/tmp/rg_roll.gba", out, ROLLUP_FRAMES, "--script", ",".join(script))

        def crashed(i):
            px = cc.frame(out, i).load()
            sampled = [(x, y) for y in range(0, 160, 2) for x in range(0, 240, 2)]
            white = sum(1 for x, y in sampled if px[x, y] == (255, 255, 255))
            return white > len(sampled) // 2
        # From 60: the first frames are the boot white before anything is drawn.
        bad = [i for i in range(60, ROLLUP_FRAMES, 5) if crashed(i)]
        # Three walks of 2600 frames is about 1.2 GB of raw captures. Leaving
        # them behind is how /tmp reached 37 GB and the box ran out of swap.
        subprocess.run(["rm", "-rf", out], check=True)
        total += len(bad)
        if bad:
            notes.append("walk %d white by frame %d" % (w, bad[0]))
    return total, "; ".join(notes) or "no crash, %d walks of %d frames" % (
        len(ROLLUP_WALKS), ROLLUP_FRAMES)


def check_chip_use():
    build("demo-field", "/tmp/rg_field.gba")
    capture(STERILE, "/tmp/rg_ar", 100, "--loadstate", PAUSED, *ALIVE,
            "--zero", "0x6016E00:1280", "--disable-bg", "--script", "Start@10,A@60,A@61")
    capture("/tmp/rg_field.gba", "/tmp/rg_au", 200, "--disable-bg", "--script", "A@130,A@131")
    return sum(diff("/tmp/rg_ar", 60 + k, "/tmp/rg_au", 130 + k, (0, 50, 120, 150))
               for k in range(32)), "navi half, 32 frames"


def check_mettaur():
    """The Mettaur virus's 70-frame attack cycle (TRANSFER.md 7ah).

    The virus acts on an RNG neither side shares, so there is no fixed frame
    offset the way `field`/`warp`/`buster` have. Instead: list the frames on
    which the Mettaur's own bounding box (it lives at x>=145, clear of the
    navi) changes on each side, and find the lag that lines the two lists up
    -- of the 17 boundary frames in the real side's attack cluster, 16 land
    on an exact rust boundary at a lag of 21. (7ah measured 20; a rebuild
    today puts every boundary one frame later on both this check and `wave`
    below, which move on a shared mechanism -- see the note in the report.)
    Once aligned, 70 consecutive frames of the cycle are diffed over the
    Mettaur's half of the screen.
    """
    build("demo-field", "/tmp/rg_field.gba")
    capture(STERILE, "/tmp/rg_mtr", 215, "--loadstate", PAUSED, *ALIVE,
            "--disable-bg", "--script", "Start@10")
    capture("/tmp/rg_field.gba", "/tmp/rg_mtu", 235, "--disable-bg")
    lag, start, box = 21, 140, (145, 0, 240, 160)
    diffs = [diff("/tmp/rg_mtr", start + k, "/tmp/rg_mtu", start + lag + k, box)
             for k in range(70)]
    subprocess.run(["rm", "-rf", "/tmp/rg_mtr", "/tmp/rg_mtu"], check=True)
    bad = sum(1 for d in diffs if d)
    return sum(diffs), "%d of 70 frames differ, lag %d" % (bad, lag)


def check_wave():
    """The shockwave's panel light, one hop and its three-frame linger (TRANSFER.md 7ai).

    Both sides captured `--disable-obj` (backgrounds only, so the field's
    panels and their one-shot yellow highlight, (255,255,66), are what's
    compared -- no sprites). The wave hops panel to panel on its own
    schedule with no shared frame offset, so alignment tracks the SET of lit
    panel centres per frame, lists the frames where that set changes on each
    side, and finds the lag that lines up the boundaries around the real
    side's first visible hop (frame 71, confirmed here) -- 126, at last
    measurement. (7ai measured 125; see the note on `mettaur` above, this
    check moved by the same one frame.) A 90-frame window anchored there
    catches the hop and its linger.
    """
    build("demo-field", "/tmp/rg_field.gba")
    capture(STERILE, "/tmp/rg_wvr", 165, "--loadstate", PAUSED, *ALIVE,
            "--disable-obj", "--script", "Start@10")
    capture("/tmp/rg_field.gba", "/tmp/rg_wvu", 290, "--disable-obj")
    lag, start, box = 126, 71, (0, 72, 240, 144)
    diffs = [diff("/tmp/rg_wvr", start + k, "/tmp/rg_wvu", start + lag + k, box)
             for k in range(90)]
    subprocess.run(["rm", "-rf", "/tmp/rg_wvr", "/tmp/rg_wvu"], check=True)
    bad = sum(1 for d in diffs if d)
    return sum(diffs), "%d of 90 frames identical, lag %d" % (90 - bad, lag)


#: name -> (function, the number it produced when last verified). A non-zero
#: `want` is a residue that is understood; TRANSFER.md says why for each.
CHECKS = [
    ("chips", check_chips, 0),        # all 43
    ("tiles", check_tiles, 0),
    ("field", check_field, 0),
    ("window", check_window, 0),
    ("card", check_card, 0),
    ("result", check_result, 0),
    ("warp", check_warp, 0),
    ("buster", check_buster, 0),
    ("chip-use", check_chip_use, 0),
    ("mettaur", check_mettaur, 460),    # attack tail, 4 of 70 frames, 7ah
    ("wave", check_wave, 960),          # panel light, first hop, 1 of 90 frames, 7ai
    ("popup", check_popup, 0),          # the chip-name popup, whole box, five chips
    ("banner", check_banner, 0),        # ENEMY DELETED, all 58 frames
    ("rollup", check_rollup, 0),        # the full battle must survive a long script
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated check names")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
    if args.list:
        for name, _, want in CHECKS:
            print("%-10s want %d" % (name, want))
        return 0
    wanted = set(args.only.split(",")) if args.only else None

    worse = 0
    for name, fn, want in CHECKS:
        if wanted and name not in wanted:
            continue
        try:
            got, note = fn()
        except Exception as exc:  # a missing ROM or state is a setup problem
            print("%-10s ERROR %s" % (name, exc))
            worse += 1
            continue
        state = "ok" if got == want else ("BETTER" if got < want else "WORSE")
        if got > want:
            worse += 1
        print("%-10s %-8s got %-8d want %-8d %s" % (name, state, got, want, note))
        sys.stdout.flush()
    print("\n%s" % ("all checks at or better than their recorded numbers"
                    if not worse else "%d check(s) WORSE" % worse))
    return 1 if worse else 0


if __name__ == "__main__":
    sys.exit(main())
