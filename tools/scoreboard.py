#!/usr/bin/env python3
"""Run every chip comparison and print the scoreboard.

usage: python3 scoreboard.py [--only NAME,...] [--out FILE]

Each row is one chip: its demo feature, the frames compared and the mean
pixels per frame chip_compare.py reports. Read a lone 369 at frame 6 as zero
-- that is the ENEMY DELETED banner, which shows for exactly one frame and
cannot be moved (chip_compare.py's docstring explains why) -- so the column
"floor" is what the banner alone contributes and a chip is exact when its mean
equals its floor.

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
    ("demo-areagrab", "a3", 40, ["--rust-start", "123"]),
    ("demo-invisibl", "b1", 60, ["--rust-start", "123"]),
    ("demo-barrier", "b2", 60, ["--rust-start", "123"]),
    ("demo-barr100", "b3", 60, ["--rust-start", "123"]),
    ("demo-barr200", "b4", 60, ["--rust-start", "123"]),
]

MEAN = re.compile(r"^mean ([0-9.]+) px/frame")
#: The banner's one frame, and the mean it alone puts on a run of N frames.
BANNER = 369


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
             chip, feature, "--frames", str(frames), *extra],
            cwd=ROOT, capture_output=True, text=True,
        )
        mean = None
        for line in out.stdout.splitlines():
            m = MEAN.match(line)
            if m:
                mean = float(m.group(1))
        floor = BANNER / frames
        rows.append((feature, frames, mean, floor))
        state = "?" if mean is None else ("EXACT" if mean <= floor + 0.05 else "%.1f" % (mean - floor))
        print("%-16s %3d frames  mean %-8s floor %-6.1f %s" % (
            feature, frames, "n/a" if mean is None else "%.1f" % mean, floor, state))
        sys.stdout.flush()

    exact = sum(1 for _, _, m, f in rows if m is not None and m <= f + 0.05)
    print("\n%d of %d exact" % (exact, len(rows)))
    if args.out:
        with open(args.out, "w") as f:
            for feature, frames, mean, floor in rows:
                f.write("%s\t%d\t%s\t%.2f\n" % (feature, frames, mean, floor))


if __name__ == "__main__":
    main()
