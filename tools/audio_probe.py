#!/usr/bin/env python3
"""tools/audio_probe.py -- T13: sample-exact comparison of two per-frame PCM
trees dumped by mgba_capture's --dump-audio (post-mix stereo s16
interleaved, one frame.####.pcm per rendered frame, same numbering as the
video).

No resampling, no trimming, no baseline subtraction, no alignment window:
frames are paired by filename, every sample of every pair is compared, and
a length mismatch (per frame or whole-tree) is reported as the defect it
is. Also does the negative fixtures (a one-sample channel shift and an
all-zero tree) so the comparison is provably not blind.

Usage:
  audio_probe.py compare DIR_A DIR_B [--label-a A] [--label-b B]
                  [--frames N] [--rms-from F] [--rms-to F]
  audio_probe.py summary DIR [--label L] [--frames N] [--rms-from F] [--rms-to F]
  audio_probe.py shift DIR_IN DIR_OUT CHANNEL 1
                  -- offset one channel of every frame by N samples (negative
                  = earlier); tail wraps out of the frame (a per-frame file has
                  no past to borrow), which is itself reported.
  audio_probe.py zero DIR_IN DIR_OUT
                  -- same-length all-silence copy of a tree.

`compare` prints, in order: the frame-pairing verdict (full length, or the
first frame where either side is missing or the per-frame byte lengths
disagree), total samples per side, the first differing sample (its global
interleaved index, its frame and offset in that frame, both values), the
differing-sample count, and max |delta| per channel. --frames limits the
compared prefix (default: the whole common length).
"""

import argparse
import os
import struct
import sys


def list_frames(tree):
    """{frame_number: path} for a --dump-audio tree."""
    out = {}
    for name in os.listdir(tree):
        if name.startswith("frame.") and name.endswith(".pcm"):
            out[int(name[6:-4])] = os.path.join(tree, name)
    return dict(sorted(out.items()))


def load(path):
    with open(path, "rb") as f:
        raw = f.read()
    n = len(raw) // 4  # stereo s16 interleaved: 4 bytes per L+R pair
    return struct.unpack("<%dh" % (n * 2), raw[: n * 4]), n


def rms(samples):
    if not samples:
        return 0.0
    acc = sum(s * s for s in samples)
    return (acc / len(samples)) ** 0.5


def peak(samples):
    return max((abs(s) for s in samples), default=0)


def summarize_tree(tree, label):
    frames = list_frames(tree)
    total_pairs = 0
    pk = 0
    all_s = []
    per_frame = {}
    for num, path in frames.items():
        s, npairs = load(path)
        per_frame[num] = (rms(s), peak(s), npairs)
        total_pairs += npairs
        all_s.extend(s)
    print("tree %s: %d frames, %d interleaved samples (%d frames x L+R), "
          "peak |sample| %d, RMS %.1f"
          % (label, len(frames), total_pairs * 2, total_pairs, peak(all_s),
             rms(all_s)))
    varying = sorted({n for _, _, n in per_frame.values()})
    print("  samples(L+R pairs) per frame: %s" %
          ("%d..%d (varies)" % (varying[0], varying[-1])
           if len(varying) > 1 else str(varying[0])))
    return frames, per_frame


def print_rms_table(a_info, b_info, lo, hi):
    print("frame, rms_a, peak_a, rms_b, peak_b, pairs")
    for num in sorted(set(a_info) & set(b_info)):
        if num < lo or num > hi:
            continue
        ra, pa, na = a_info[num]
        rb, pb, nb = b_info[num]
        print("%d, %.1f, %d, %.1f, %d, %d/%d" % (num, ra, pa, rb, pb, na, nb))
    return 0


def cmd_summary(args):
    frames, info = summarize_tree(args.tree, args.label or args.tree)
    if args.rms_from is not None:
        print_rms_table(info, info, args.rms_from, args.rms_to or 10**9)
    return 0


def cmd_compare(args):
    fa = list_frames(args.tree_a)
    fb = list_frames(args.tree_b)
    only_a = sorted(set(fa) - set(fb))
    only_b = sorted(set(fb) - set(fa))
    if only_a or only_b:
        print("FRAME DEFECT: %d frames only in %s (first %s), %d only in %s (first %s)"
              % (len(only_a), args.label_a, only_a[:3],
                 len(only_b), args.label_b, only_b[:3]))
    common = sorted(set(fa) & set(fb))
    if not common:
        print("no common frames -- nothing to compare")
        return 1
    if args.frames is not None:
        common = common[: args.frames]

    total_a = total_b = 0
    diffs = 0
    max_dl = max_dr = 0
    max_dl_at = max_dr_at = None
    first = None
    len_defect = None
    info_a, info_b = {}, {}
    global_index = 0
    for num in common:
        sa, na = load(fa[num])
        sb, nb = load(fb[num])
        info_a[num] = (rms(sa), peak(sa), na)
        info_b[num] = (rms(sb), peak(sb), nb)
        total_a += na
        total_b += nb
        if na != nb and len_defect is None:
            len_defect = (num, na, nb)
        n = min(na, nb)
        base = global_index
        for i in range(n):
            x, y = sa[2 * i], sb[2 * i]
            if x != y:
                diffs += 1
                if first is None:
                    first = (num, i, "L", x, y, base + 2 * i)
                d = abs(x - y)
                if d > max_dl:
                    max_dl, max_dl_at = d, (num, i)
            x, y = sa[2 * i + 1], sb[2 * i + 1]
            if x != y:
                diffs += 1
                if first is None:
                    first = (num, i, "R", x, y, base + 2 * i + 1)
                d = abs(x - y)
                if d > max_dr:
                    max_dr, max_dr_at = d, (num, i)
        global_index += 2 * n

    print("compared %d frame pairs (%s vs %s)" % (len(common), args.label_a, args.label_b))
    print("total interleaved samples: %s %d, %s %d%s"
          % (args.label_a, total_a * 2, args.label_b, total_b * 2,
             "" if total_a == total_b else "  <-- LENGTH MISMATCH"))
    if len_defect:
        print("per-frame length defect at frame %d: %s %d L+R pairs vs %s %d"
              % (len_defect[0], args.label_a, len_defect[1], args.label_b, len_defect[2]))
    if first is None:
        print("SAMPLE-EXACT: 0 differing samples")
    else:
        num, i, ch, x, y, frames_before = first
        print("first differing sample: global interleaved s16 index %d, "
              "frame %d offset %d channel %s, %s=%d %s=%d "
              % (first[5], num, i, ch, args.label_a, x, args.label_b, y))
    print("differing samples: %d of %d (%.4f%%)"
          % (diffs, min(total_a, total_b) * 2,
             100.0 * diffs / (min(total_a, total_b) * 2) if min(total_a, total_b) else 0.0))
    print("max |delta|: L %d at %s, R %d at %s"
          % (max_dl, "frame %d offset %d" % max_dl_at if max_dl_at else "-",
             max_dr, "frame %d offset %d" % max_dr_at if max_dr_at else "-"))
    if args.rms_from is not None:
        print_rms_table(info_a, info_b, args.rms_from, args.rms_to or 10**9)
    return 0 if diffs == 0 and not len_defect else 1


def cmd_shift(args):
    frames = list_frames(args.tree_in)
    os.makedirs(args.tree_out, exist_ok=True)
    for num, path in frames.items():
        s, npairs = load(path)
        out = [0] * (npairs * 2)
        ch = 0 if args.channel == "L" else 1
        for i in range(npairs):
            out[2 * i] = s[2 * i]
            out[2 * i + 1] = s[2 * i + 1]
        for i in range(npairs):
            j = i + args.shift
            if 0 <= j < npairs:
                out[2 * i + ch] = s[2 * j + ch]
        with open(os.path.join(args.tree_out, "frame.%04d.pcm" % num), "wb") as f:
            f.write(struct.pack("<%dh" % len(out), *out))
    print("wrote %d frames to %s (channel %s shifted by %+d samples, wrapped tail zeroed)"
          % (len(frames), args.tree_out, args.channel, args.shift))
    return 0


def cmd_zero(args):
    frames = list_frames(args.tree_in)
    os.makedirs(args.tree_out, exist_ok=True)
    for num, path in frames.items():
        s, npairs = load(path)
        with open(os.path.join(args.tree_out, "frame.%04d.pcm" % num), "wb") as f:
            f.write(struct.pack("<%dh" % (npairs * 2), *([0] * (npairs * 2))))
    print("wrote %d all-zero frames to %s (same per-frame lengths)"
          % (len(frames), args.tree_out))
    return 0


def main(argv):
    p = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("compare", help="sample-exact diff of two trees")
    c.add_argument("tree_a"); c.add_argument("tree_b")
    c.add_argument("--label-a", default="A"); c.add_argument("--label-b", default="B")
    c.add_argument("--frames", type=int, default=None)
    c.add_argument("--rms-from", type=int, default=None)
    c.add_argument("--rms-to", type=int, default=None)
    c.set_defaults(fn=cmd_compare)

    s = sub.add_parser("summary", help="per-side baseline numbers")
    s.add_argument("tree"); s.add_argument("--label", default=None)
    s.add_argument("--frames", type=int, default=None)
    s.add_argument("--rms-from", type=int, default=None)
    s.add_argument("--rms-to", type=int, default=None)
    s.set_defaults(fn=cmd_summary)

    h = sub.add_parser("shift", help="negative fixture: shift one channel")
    h.add_argument("tree_in"); h.add_argument("tree_out")
    h.add_argument("channel", choices=["L", "R"]); h.add_argument("shift", type=int)
    h.set_defaults(fn=cmd_shift)

    z = sub.add_parser("zero", help="negative fixture: same-length silence")
    z.add_argument("tree_in"); z.add_argument("tree_out")
    z.set_defaults(fn=cmd_zero)

    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
