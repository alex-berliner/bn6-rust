#!/usr/bin/env python3
"""A full-battle GIF of the current release ROM, played by a fixed "player" script: pick chips in the
chip window, confirm OK, fight with the buster and the chips, reopen the custom screen with L, pick and
confirm again, play to deletion and RESULT. It shows the build as a player would see it; it is not a
parity measurement (the per-row GIFs are). --walk uses the harness's first rollup walk instead.

usage: python3 tools/battle_gif.py [--frames 2400] [--step 2] [--walk] [--out web/captures/full-battle-loop.gif]
"""

TOUR = (["A@200", "A@222", "A@244", "Start@270", "A@292"]
        + ["B@%d" % t for t in range(430, 1100, 14)]
        + ["A@520", "A@640", "A@760", "Up@580", "Down@820"]
        + ["L@1150", "A@1210", "A@1232", "Start@1258", "A@1280"]
        + ["B@%d" % t for t in range(1420, 2100, 14)] + ["A@1500", "A@1620"])
import argparse, os, subprocess, sys
sys.path.insert(0, os.path.dirname(__file__))
import harness as h, chip_compare as cc
from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--frames", type=int, default=2400)
    ap.add_argument("--step", type=int, default=2, help="keep every Nth frame")
    ap.add_argument("--walk", action="store_true", help="use the rollup walk instead of the player tour")
    ap.add_argument("--out", default=os.path.join(ROOT, "web/captures/full-battle-loop.gif"))
    a = ap.parse_args()
    rom = h.plain_rom()
    if a.walk:
        keys, last = h.ROLLUP_WALKS[0], a.frames - 50
        script = [h.held(keys[i % len(keys)], at, 3) for i, at in enumerate(range(60, last, 19))]
        script += [h.held("B", at, 2) for at in range(70, last, 11)]
        script += [h.held("A", at, 2) for at in range(100, last, 37)]
    else:
        script = TOUR
    out = cc.scratch("battle_gif")
    cc.capture(rom, out, a.frames, "--script", ",".join(script))
    frames = [cc.frame(out, i).resize((480, 320), Image.NEAREST) for i in range(0, a.frames, a.step)]
    frames[0].save(a.out, save_all=True, append_images=frames[1:], duration=a.step * 1000 // 60,
                   loop=0, optimize=True)
    subprocess.run(["rm", "-rf", out])
    rev = subprocess.run(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"], capture_output=True,
                         text=True).stdout.strip()
    with open(a.out[:-4] + ".txt", "w") as f:
        f.write("The release ROM played by a fixed player script (tools/battle_gif.py), %d frames at every "
                "%dth: the chip window a battle opens with, a chip picked and OK, 'Sending chip data', "
                "BATTLE START!, the fight against a Mettaur with the buster and FireSwrd, deletion and "
                "RESULT. The faded copy of the chip window that used to stay on the left of the field "
                "after the window closed (TODO F3) is FIXED: vacate() never cleared a single column "
                "(its condition tested a scroll value the slide never reaches), so the whole window "
                "map reappeared on BG3 at scroll 0; it now clears each column on the frame canon does "
                "(sub_8026BF4's cadence, measured on eS20364C0 +0x44), and the harness's new "
                "windowclose row compares the close directly (977410 -> 695603 full screen, the "
                "window's own layer exact over the whole slide). "
                "This is the build as a player sees it, not a parity "
                "measurement; the per-row GIFs are the measurements.\n\ncommit %s" % (a.frames, a.step, rev))
    print("wrote %s (%d frames, %.1f MB)" % (a.out, len(frames), os.path.getsize(a.out) / 1e6))


if __name__ == "__main__":
    main()
