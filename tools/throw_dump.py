#!/usr/bin/env python3
"""Read a thrown chip object's launch constants straight out of the game.

usage: throw_dump.py <chip_id_hex> [--from N] [--to N]
   e.g. throw_dump.py 43        # BugBomb

Every arc in this port used to be SWEPT: step the three constants, run the
comparison, keep what scores best. That works, and it is also how BugBomb
ended up on a launch 1282 too weak and a pull 64 too soft, two errors that
cancel over forty frames and leave one rounding boundary wrong. The game
holds the real numbers in EWRAM while the thing is in the air, so read them.

How it works: dump all 256K of EWRAM once per frame across the flight, then
look for a word that advances by the SAME non-zero step every frame -- that is
the object's X, because the across-speed of a thrown thing never changes. The
battle object's layout follows from it (sub_80C5C9C, asm31.s:29505, loads XYZ
from +0x34 and VX/gravity/VZ from +0x40), so the rest is read off at fixed
offsets. Then walk the Z velocity back a frame at a time -- the gravity step is
constant, so this is exact -- until Z reaches the spawn height, which gives the
launch velocity and the frame it was thrown on.

Prints the numbers to paste into `src/battle.rs`. Needs /tmp/mgba_capture and
the real ROM and state, which are never committed.
"""

import argparse
import os
import struct
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chip_compare as cc  # noqa: E402  (needs the path set first)

EWRAM = 0x02000000
EWRAM_BYTES = 256 * 1024
#: Battle object field offsets, from sub_80C5C9C (asm31.s:29505).
O_TIMER = 0x20
O_X, O_Y, O_Z = 0x34, 0x38, 0x3C
O_VX, O_VY, O_VZ = 0x40, 0x44, 0x48
#: The height every thrown chip object leaves the hand at: the spawn sets Z to
#: the navi's plus 0x300000 and the navi stands at zero.
SPAWN_Z = 0x300000


def dump(chip, frame, path):
    subprocess.run(
        [cc.CAPTURE, cc.STERILE, "/tmp/throw_dump_frames", str(frame),
         "--loadstate", cc.STATE,
         "--cheat", "0x0203ab84:0", "--cheat", "0x0203ab86:0",
         *cc.library_pokes(int(chip, 16)),
         "--cheat", "%s:0x%s" % (cc.HAND_SLOT, chip),
         "--zero", cc.BANNER_TILES, "--disable-bg",
         "--script", "Start@10,A@%d" % cc.REAL_A_FRAME,
         "--dump", "0x%08x:%d:%s" % (EWRAM, EWRAM_BYTES, path)],
        check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def signed(v):
    return v - (1 << 32) if v >= (1 << 31) else v


def word(mem, addr):
    return signed(struct.unpack_from("<I", mem, addr - EWRAM)[0])


def find_object(mems, frames):
    """The address of a field that steps by the same non-zero amount every
    frame, which for a thrown object is its X."""
    hits = []
    for off in range(0, EWRAM_BYTES - 4, 4):
        vals = [signed(struct.unpack_from("<I", mems[f], off)[0]) for f in frames]
        steps = {b - a for a, b in zip(vals, vals[1:])}
        # A whole pixel a frame at least: this rules out counters and clocks.
        if len(steps) == 1 and abs(next(iter(steps))) >= 0x10000:
            hits.append((EWRAM + off, next(iter(steps))))
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("chip")
    ap.add_argument("--from", dest="first", type=int, default=70,
                    help="first frame to sample (default 70, mid-flight for a bomb)")
    ap.add_argument("--to", dest="last", type=int, default=76)
    args = ap.parse_args()

    frames = list(range(args.first, args.last + 1))
    mems = {}
    for f in frames:
        path = "/tmp/throw_ew_%s_%d.bin" % (args.chip, f)
        dump(args.chip, f, path)
        mems[f] = open(path, "rb").read()
    print("sampled frames %d..%d" % (frames[0], frames[-1]))

    hits = find_object(mems, frames)
    if not hits:
        print("no object moving at a constant speed in those frames; try another window")
        return 1
    for addr, step in hits:
        base = addr - O_X
        z = [word(mems[f], base + O_Z) for f in frames]
        vz = [word(mems[f], base + O_VZ) for f in frames]
        pulls = {a - b for a, b in zip(vz, vz[1:])}
        if len(pulls) != 1:
            continue
        gravity = next(iter(pulls))
        if gravity == 0:
            continue  # something moving in a straight line, not thrown
        # Is the position stepped by the velocity of the same frame (the
        # velocity is updated first) or of the one before it?
        first = "velocity" if z[1] - z[0] == vz[1] else "position"
        print("\nobject at 0x%08x (X field 0x%08x)" % (base, addr))
        print("  timer   %s" % " ".join(str(word(mems[f], base + O_TIMER)) for f in frames))
        print("  X       0x%x, step 0x%x" % (word(mems[frames[0]], base + O_X) & 0xFFFFFFFF,
                                             step & 0xFFFFFFFF))
        print("  Y       0x%x" % (word(mems[frames[0]], base + O_Y) & 0xFFFFFFFF))
        print("  Z       %d" % z[0])
        print("  VZ      %d, gravity %d (0x%x) a frame" % (vz[0], gravity, abs(gravity)))
        print("  stepped %s first" % first)

        # Walk back to the spawn, undoing the update in the order it runs.
        # `vv` is the velocity stored on the frame `zz` belongs to, so when
        # `zz` reaches the spawn height `vv` is the launch velocity -- the
        # number to put in the source.
        zz, vv, back = z[0], vz[0], 0
        while zz > 0 and back < 200:
            if zz == SPAWN_Z:
                print("  LAUNCH  %d frames earlier: Z 0x%x, VZ 0x%x, timer %d"
                      % (back, SPAWN_Z, vv & 0xFFFFFFFF,
                         word(mems[frames[0]], base + O_TIMER) + back))
                break
            if first == "velocity":
                zz -= vv
                vv += gravity
            else:
                vv += gravity
                zz -= vv
            back += 1
        else:
            print("  (never passes the 0x%x spawn height going back)" % SPAWN_Z)
    return 0


if __name__ == "__main__":
    sys.exit(main())
