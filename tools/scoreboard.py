#!/usr/bin/env python3
"""Run every chip comparison and print the scoreboard.

Each comparison is run with --clean: 43 chips leave about 4 GB of raw capture
frames behind otherwise, and this box has run out of swap over exactly that.

usage: python3 scoreboard.py [--only NAME,...] [--out FILE]

Each row is one chip: its demo feature, the frames compared and the mean
pixels per frame chip_compare.py reports. EXACT MEANS ZERO. It used to mean
"equals a floor", because the ENEMY DELETED banner contributed 369 px on one
frame of every comparison and could not be zeroed from the harness -- the
harness writes before each frame and the game uploads the banner during the
frame that shows it. tools/patch_sterile.py now patches the routine that
uploads it (sub_801E838) out of the capture ROM, so there is no floor left to
subtract and a chip is exact when its mean is 0. The same patch file also
removes the chip-name popup (sub_801E95C), which the banner's floor had been
hiding: it costs one frame of every comparison and is what kept AreaGrab,
Invisibl, Barrier, Barr100 and Barr200 off zero. All 43 are at zero as of
2026-09-07: the last two, BugBomb and VDoll, came in when their arcs stopped
being swept and were read out of the running game instead (tools/throw_dump.py,
TRANSFER 7ao).

The frame counts are the length of each attack: too few misses its end, too
many compares a second volley against an idle navi, because the sterile demo
re-fires as soon as the navi is free.
"""

import argparse
import os
import re
import subprocess
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")

#: The flags a chip that shows its name popup needs; see the note by the five
#: of them at the bottom of the list.
POPUP = ["--rust-start", "123", "--hide-enemy", "--no-banner-zero"]

#: feature, chip id in hex, frames, extra flags.
CHIPS = [
    ("demo-cannon", "01", 40, []),
    ("demo-hicannon", "02", 40, []),
    ("demo-mcannon", "03", 40, []),
    ("demo-airshot", "04", 40, []),
    ("demo-vulcan", "05", 60, []),
    ("demo-vulcan2", "06", 70, []),
    ("demo-vulcan3", "07", 80, []),
    ("demo-suprvulc", "08", 113, []),
    ("demo-sword", "47", 40, []),
    ("demo-wideswrd", "48", 40, []),
    ("demo-longswrd", "49", 40, []),
    ("demo-wideblde", "4a", 40, []),
    ("demo-longblde", "4b", 40, []),
    ("demo-fireswrd", "4c", 40, []),
    ("demo-aquaswrd", "4d", 40, []),
    ("demo-elecswrd", "4e", 40, []),
    ("demo-bambswrd", "4f", 40, []),
    ("demo-muramasa", "55", 40, []),
    ("demo-minibomb", "36", 60, []),
    ("demo-energbom", "37", 60, []),
    ("demo-megenbom", "38", 60, []),
    ("demo-flshbom", "39", 48, []),
    ("demo-blkbomb", "3c", 50, []),
    ("demo-bigbomb", "ca", 75, []),
    ("demo-lilbolr", "62", 48, []),
    ("demo-poisseed", "46", 70, []),
    ("demo-iceseed", "45", 70, []),
    ("demo-grasseed", "44", 70, []),
    ("demo-bugbomb", "43", 70, []),
    ("demo-vdoll", "96", 70, []),
    # Recov moves nothing, so the aligner has nothing to lock onto: the
    # sterile demo's auto-fire uses its chip at frame 123.
    ("demo-recovery", "9a", 40, ["--rust-start", "123"]),
    ("demo-recov30", "9b", 40, ["--rust-start", "123"]),
    ("demo-recov50", "9c", 40, ["--rust-start", "123"]),
    ("demo-recov80", "9d", 40, ["--rust-start", "123"]),
    ("demo-recov120", "9e", 40, ["--rust-start", "123"]),
    ("demo-recov150", "9f", 40, ["--rust-start", "123"]),
    ("demo-recov200", "a0", 40, ["--rust-start", "123"]),
    ("demo-recov300", "a1", 40, ["--rust-start", "123"]),
    # The five family-0x15 chips put their NAME up in the middle of the screen
    # while they present, out of the same tiles the ENEMY DELETED banner uses.
    # To see it the banner blanking has to come off, and for that the enemy has
    # to stay alive so no banner is ever asked for -- hence --hide-enemy, which
    # keeps it immortal and blanks its own tiles instead. 80 frames covers the
    # popup's whole life: it goes up on the attack's 18th frame and rolls back
    # up 58 frames later.
    # AreaGrab stops one frame short of its steal: the column it takes is a
    # BACKGROUND change, which --disable-bg hides on the real side and cannot
    # hide on this one, so the frames after the steal compare three drawn
    # panels against nothing. The popup is over by then (it goes up on the
    # attack's 18th frame and is gone after its 76th).
    ("demo-areagrab", "a3", 77, POPUP),
    ("demo-invisibl", "b1", 80, POPUP),
    ("demo-barrier", "b2", 80, POPUP),
    ("demo-barr100", "b3", 80, POPUP),
    ("demo-barr200", "b4", 80, POPUP),
]

MEAN = re.compile(r"^mean ([0-9.]+) px/frame")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated feature names")
    ap.add_argument("--out")
    args = ap.parse_args()
    wanted = set(args.only.split(",")) if args.only else None

    rows = []
    for feature, chip, frames, extra in CHIPS:
        if wanted and feature not in wanted:
            continue
        out = subprocess.run(
            ["python3", os.path.join(ROOT, "tools", "chip_compare.py"),
             chip, feature, "--frames", str(frames), "--clean", *extra],
            cwd=ROOT, capture_output=True, text=True,
        )
        mean = None
        for line in out.stdout.splitlines():
            m = MEAN.match(line)
            if m:
                mean = float(m.group(1))
        floor = 0.0
        rows.append((feature, frames, mean, floor))
        state = "?" if mean is None else ("EXACT" if mean <= 0.05 else "%.1f" % mean)
        print("%-16s %3d frames  mean %-8s %s" % (
            feature, frames, "n/a" if mean is None else "%.1f" % mean, state))
        sys.stdout.flush()

    exact = sum(1 for _, _, m, f in rows if m is not None and m <= f + 0.05)
    print("\n%d of %d exact" % (exact, len(rows)))
    if args.out:
        with open(args.out, "w") as f:
            for feature, frames, mean, floor in rows:
                f.write("%s\t%d\t%s\t%.2f\n" % (feature, frames, mean, floor))


if __name__ == "__main__":
    main()
