#!/usr/bin/env python3
"""tools/audio_diff.py -- T95: sample-exact diff of two mgba --dump-audio trees.

The M9 comparator: load two per-frame PCM trees dumped by mgba_capture's
--dump-audio (post-mix stereo s16le interleaved; one ``frame.#####.pcm`` per
rendered frame, same numbering as video), compare every sample of every
paired frame, and report the total differing-sample count, the worst single
frame, and the first divergent sample. Mirrors ``tools/probe.py diff``
ergonomics (positional A/B dirs, ``--a-start``/``--b-start``/``--frames``,
per-frame count + total + worst + first-divergent-sample).

The compare is SAMPLE-EXACT. No resampling, no trimming, no alignment window,
no tolerance, no baseline subtraction. Frame pairings are by filename
(``frame.NNNNN.pcm`` on both sides); a missing frame on either side, a
per-frame byte-length mismatch, or a single differing sample is reported as
the defect it is, the same way ``tools/probe.py diff`` reports a single
differing pixel.

Format flags exist so the comparator can also chew non-mgba dumps, but the
DEFAULTS match mgba's output and must continue to match it without a
tolerance. The cited format is the close-NEGATIVE fact (sample width,
channels, rate, ``file:line``); see ``docs/handbook/audio.md`` for the
matrix.

Usage:
  audio_diff.py DIR_A DIR_B [--a-start N] [--b-start N] [--frames N]
                  [--format {s16le,raw}] [--bits {8,16}]
                  [--channels {1,2}] [--rate HZ] [--quiet]

Output (one line per compared frame + a summary), echoing ``probe.py diff``:
  k=A-B  samples=differing-of-compared  first=(global_idx, channel, value_a, value_b)
  total S worst W at k=... over F frames

Exit code: 0 on sample-exact match (every paired frame has zero differing
samples and identical byte lengths), non-zero otherwise. Use ``--quiet`` to
suppress per-frame lines and only print the summary + first divergent sample.
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
            stem = name[6:-4]
            try:
                out[int(stem)] = os.path.join(tree, name)
            except ValueError:
                # frame.ABC.pcm etc -- not from mgba_capture, skip silently
                continue
    return dict(sorted(out.items()))


def frame_bytes(samples_per_frame, bits, channels):
    """Bytes one frame file should hold for the declared format."""
    return samples_per_frame * channels * (bits // 8)


def decode(raw, bits, channels):
    """Decode a raw frame file to a flat list of channel-major-or-interleaved
    samples. Returns (samples_list, samples_per_frame)."""
    if bits == 16:
        # signed 16-bit little-endian
        if len(raw) % 2 != 0:
            raise ValueError("file byte length %d is not a multiple of 2 (16-bit samples)" % len(raw))
        n = len(raw) // 2
        s = struct.unpack("<%dh" % n, raw)
        if channels == 1:
            return list(s), n
        if channels == 2:
            if n % 2 != 0:
                raise ValueError("file byte length %d is not a multiple of 4 (16-bit stereo pair)" % len(raw))
            return list(s), n // 2
        raise ValueError("unsupported channel count %d" % channels)
    if bits == 8:
        if channels == 1:
            # unsigned 8-bit, "raw" convention (0..255, 128 = silence)
            return list(raw), len(raw)
        if channels == 2:
            if len(raw) % 2 != 0:
                raise ValueError("file byte length %d is not a multiple of 2 (8-bit stereo)" % len(raw))
            return list(raw), len(raw) // 2
        raise ValueError("unsupported channel count %d" % channels)
    raise ValueError("unsupported sample width %d bits" % bits)


def diff_pair(sa, sb, npairs_a, npairs_b, channels):
    """Per-frame sample-exact diff. Returns
    (differing_sample_count, first_divergent_sample_or_None, max_abs_delta).

    `first_divergent_sample` is (global_interleaved_index_within_pair, channel,
    value_a, value_b). `max_abs_delta` is max over all differing samples.
    """
    n = min(npairs_a, npairs_b)
    diffs = 0
    first = None
    worst = 0
    for i in range(n):
        for c in range(channels):
            x = sa[i * channels + c]
            y = sb[i * channels + c]
            if x != y:
                diffs += 1
                if first is None:
                    first = (i * channels + c, c, x, y)
                d = x - y
                if d < 0:
                    d = -d
                if d > worst:
                    worst = d
    # any leftover on the longer side counts as a differing sample per leftover
    # (defect, not a silence assumption); reported separately by the caller
    # using the per-frame byte-length mismatch.
    if npairs_a != npairs_b:
        diffs += abs(npairs_a - npairs_b) * channels
    return diffs, first, worst


def parse_args(argv):
    ap = argparse.ArgumentParser(
        description="sample-exact diff of two mgba --dump-audio trees",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("dirA", help="first tree (mgba_capture --dump-audio <dir>)")
    ap.add_argument("dirB", help="second tree")
    ap.add_argument("--a-start", type=int, default=0,
                    help="first frame index on the A side (default 0)")
    ap.add_argument("--b-start", type=int, default=0,
                    help="first frame index on the B side (default 0)")
    ap.add_argument("--frames", type=int, default=None,
                    help="compare at most N frame pairs (default: whole common length)")
    ap.add_argument("--format", choices=["s16le", "raw"], default="s16le",
                    help="sample encoding (default s16le, the mgba --dump-audio format)")
    ap.add_argument("--bits", type=int, choices=[8, 16], default=16,
                    help="sample width in bits (default 16, the mgba --dump-audio format)")
    ap.add_argument("--channels", type=int, choices=[1, 2], default=2,
                    help="channel count (default 2, the mgba --dump-audio format)")
    ap.add_argument("--rate", type=int, default=32768,
                    help="sample rate in Hz, informational only (default 32768, "
                         "the GBA's native PSG rate; mgba's resampled output is "
                         "~96000 measured -- tools/mgba_capture.c:30-48)")
    ap.add_argument("--quiet", action="store_true",
                    help="suppress per-frame lines, print only summary")
    return ap.parse_args(argv)


def main(argv):
    args = parse_args(argv)

    if not os.path.isdir(args.dirA):
        print("audio_diff: %s: not a directory" % args.dirA, file=sys.stderr)
        return 2
    if not os.path.isdir(args.dirB):
        print("audio_diff: %s: not a directory" % args.dirB, file=sys.stderr)
        return 2

    fa = list_frames(args.dirA)
    fb = list_frames(args.dirB)

    if not fa:
        print("audio_diff: %s: no frame.NNNNN.pcm files found" % args.dirA, file=sys.stderr)
        return 2
    if not fb:
        print("audio_diff: %s: no frame.NNNNN.pcm files found" % args.dirB, file=sys.stderr)
        return 2

    keys_a = sorted(fa)
    keys_b = sorted(fb)
    pairs = []
    a = args.a_start
    b = args.b_start
    while a in fa and b in fb:
        pairs.append((a, b))
        a += 1
        b += 1
    if args.frames is not None:
        pairs = pairs[: args.frames]

    # detect one tree running out before the other: a frame-count mismatch is
    # itself a defect ("PASS on truncated dump: sample-count mismatch reported"),
    # not an excuse to stop comparing.
    leftover_a = [k for k in keys_a if k >= args.a_start + len(pairs)]
    leftover_b = [k for k in keys_b if k >= args.b_start + len(pairs)]

    if not pairs:
        print("audio_diff: no paired frames between %s (start=%d) and %s (start=%d)"
              % (args.dirA, args.a_start, args.dirB, args.b_start), file=sys.stderr)
        if leftover_a or leftover_b:
            print("  %s has %d unpaired frame(s) past the common prefix; %s has %d."
                  % (args.dirA, len(leftover_a), args.dirB, len(leftover_b)))
        return 2

    # per-frame byte size the format demands (for clean error messages)
    # we read each file's actual byte length and compare to whatever the format
    # implies for the per-frame sample count (varies frame to frame).
    frames_compared = 0
    total = 0
    worst = (0, -1, None)        # (count, k, first_divergent_tuple)
    first_any = None              # (k, frame_a, frame_b, sample_index, channel, value_a, value_b)
    len_mismatches = []           # list of (k, frame_a, frame_b, bytes_a, bytes_b)
    format_errors = []            # list of (k, error_message)

    for k, (na, nb) in enumerate(pairs):
        try:
            raw_a = open(fa[na], "rb").read()
            raw_b = open(fb[nb], "rb").read()
            sa, npairs_a = decode(raw_a, args.bits, args.channels)
            sb, npairs_b = decode(raw_b, args.bits, args.channels)
        except (ValueError, struct.error) as e:
            format_errors.append((k, na, nb, str(e)))
            continue

        if len(raw_a) != len(raw_b):
            len_mismatches.append((k, na, nb, len(raw_a), len(raw_b)))

        d, first, max_d = diff_pair(sa, sb, npairs_a, npairs_b, args.channels)
        frames_compared += 1
        total += d
        if d > worst[0]:
            worst = (d, k, first)
        if not args.quiet:
            if first is None:
                print("k=%-4d A=%05d B=%05d  0 differing  same-length %d bytes"
                      % (k, na, nb, len(raw_a)))
            else:
                idx, ch, va, vb = first
                print("k=%-4d A=%05d B=%05d  %d differing  first=(pair_idx=%d ch=%d a=%d b=%d, |delta|_max=%d)  len %d/%d"
                      % (k, na, nb, d, idx // args.channels, ch, va, vb, max_d,
                         len(raw_a), len(raw_b)))
        if first_any is None and first is not None:
            idx, ch, va, vb = first
            first_any = (k, na, nb, idx, ch, va, vb)

    # a sample-count mismatch (one tree runs longer than the other) is a defect
    if leftover_a or leftover_b:
        # each leftover frame contributes its whole sample count to the diff
        # total, so the verifier cannot miss a truncation in the numbers.
        for k in leftover_a[:10] + leftover_b[:10]:
            try:
                raw = open(fa[k] if k in fa else fb[k], "rb").read()
                _, npairs = decode(raw, args.bits, args.channels)
                total += npairs * args.channels
            except (ValueError, struct.error):
                total += 0  # format error will be reported separately

    # summary
    if (first_any is None and not len_mismatches and not format_errors
            and not leftover_a and not leftover_b):
        verdict = "PASS"
    else:
        verdict = "FAIL"

    # duration in seconds (informational; rate is not used in the comparison)
    total_pairs = sum(
        decode(open(fa[na], "rb").read(), args.bits, args.channels)[1]
        for na, _ in pairs
        if True
    )
    duration = total_pairs / float(args.rate) if args.rate > 0 else 0.0

    summary = ("total %d differing samples over %d frame pairs "
               "(compared %d total L+R pairs at %d Hz = %.3f s), "
               "worst %d differing samples at k=%d, "
               "first divergent %s"
               % (total, frames_compared, total_pairs, args.rate, duration,
                  worst[0], worst[1],
                  ("none" if first_any is None
                   else "k=%d frame_A=%05d frame_B=%05d sample_idx=%d channel=%d a=%d b=%d"
                       % first_any)))
    print(summary)

    if leftover_a or leftover_b:
        print("SAMPLE-COUNT MISMATCH: %s has %d extra frame(s) past the common prefix "
              "(first %s); %s has %d (first %s)"
              % (args.dirA, len(leftover_a), leftover_a[:5],
                 args.dirB, len(leftover_b), leftover_b[:5]))
    if len_mismatches:
        print("%d per-frame byte-length mismatches (truncated/extended file); first %d:"
              % (len(len_mismatches), min(10, len(len_mismatches))))
        for k, na, nb, la, lb in len_mismatches[:10]:
            print("  k=%d frame_A=%05d frame_B=%05d: %d bytes vs %d bytes (delta %+d)"
                  % (k, na, nb, la, lb, lb - la))
    if format_errors:
        print("%d format/decode errors:" % len(format_errors))
        for k, na, nb, msg in format_errors[:10]:
            print("  k=%d frame_A=%05d frame_B=%05d: %s" % (k, na, nb, msg))

    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
