# Audio comparison (M9)

`tools/audio_diff.py` compares two `mgba_capture --dump-audio <dir>` trees
sample-exactly: every sample of every paired frame is checked, no resampling,
no trimming, no tolerance, no baseline subtraction. It is the audio analogue
of `tools/probe.py diff` (same `--a-start` / `--b-start` / `--frames`
ergonomics, same per-frame-then-summary output) and the close-NEGATIVE fact
for M9 (audio parity + the triggers' trace).

## The canonical mgba format

mgba's audio dump is the comparator's default format and the source of truth
for what `tools/audio_diff.py` must understand without flags:

| field         | value                                                        | cite (tools/mgba_capture.c) |
|---------------|--------------------------------------------------------------|-----------------------------|
| container     | one file per rendered frame, `frame.NNNNN.pcm` in the tree   | line 30-48 (header), line 958 |
| encoding      | signed 16-bit little-endian                                  | line 30-48 ("signed 16-bit interleaved PCM") |
| layout        | interleaved L/R (L,R,L,R,...)                                | line 30-48, 954-955 (`blip_read_samples(left, pcm, avail, 1); blip_read_samples(right, pcm+1, avail, 1)`) |
| channels      | 2 (post-mix stereo bus, PSG + both DirectSound FIFOs)        | line 36-39, 629-630 |
| sample width  | 16 bits                                                      | line 953 (`int16_t pcm[4096*2]`), line 966 (`sizeof(int16_t)*2`) |
| bytes / pair  | 4 (2 channels × 2 bytes)                                     | line 966 |
| per-frame cap | 4096 L+R pairs                                               | line 950 (`if (avail > 4096) avail = 4096`) |
| advertised rate | 65536 Hz (mAVStream.audioRateChanged)                      | line 200-203, 1082-1086 |
| measured rate | ~96000 Hz (the one to believe; resampler drift)              | line 40-48, 1082-1086 |

The `--rate` flag in `audio_diff.py` is **informational only** (it divides the
compared-pair count to print a duration line in the summary). The comparison
itself is sample-exact and does not use rate at all, so the canonical mgba
dump can be compared without a tolerance and without the user supplying a
rate.

The `audio_rate` knob on the emulator side is the GBA's `sampleInterval`
scalar; mgba's blip_t setup resamples the post-mix bus to the rate the host
audio device wants, which is why "advertised" and "measured" differ by a
factor of ~1.46. Use the measured number from the run's own stderr ("audio:
wrote N samples over M frames ... = R Hz measured") when you want a
real-world duration, not the mAVStream report.

## CLI

```
tools/audio_diff.py DIR_A DIR_B
                     [--a-start N] [--b-start N] [--frames N]
                     [--format {s16le,raw}] [--bits {8,16}]
                     [--channels {1,2}] [--rate HZ] [--quiet]
```

| flag | meaning | default | matches mgba? |
|------|---------|---------|---------------|
| `--a-start N` | first frame index on the A side | 0 | n/a |
| `--b-start N` | first frame index on the B side | 0 | n/a |
| `--frames N` | compare at most N frame pairs | whole common prefix | n/a |
| `--format s16le\|raw` | signed 16-bit little-endian, or unsigned 8-bit | `s16le` | yes |
| `--bits 8\|16` | sample width | `16` | yes |
| `--channels 1\|2` | channel count | `2` | yes |
| `--rate HZ` | informational sample rate for the duration line | `32768` (GBA's native PSG rate) | n/a — see rate note above |
| `--quiet` | drop per-frame lines, print only summary + first divergent | off | n/a |

The defaults are mgba's format. Override only when comparing a dump that was
produced by something other than mgba_capture.

## Output shape

Per-frame (one line per paired frame unless `--quiet`):

```
k=K    A=NNNNN B=NNNNN  D differing  first=(pair_idx=I ch=C a=A b=B, |delta|_max=M)  len LA/LB bytes
```

Summary line:

```
total T differing samples over F frame pairs (compared P total L+R pairs at R Hz = S s),
worst W differing samples at k=KW, first divergent (k=K frame_A=A frame_B=B sample_idx=I channel=C a=A b=B)
```

Plus, when applicable:

- `SAMPLE-COUNT MISMATCH: <dirA> has N extra frame(s) past the common prefix (first [...]); <dirB> has N ...`
  (truncated or extended tree: the unpaired tail itself is a defect, not
  "stop comparing at the shorter side").
- `M per-frame byte-length mismatches (truncated/extended file): ...`
  (per-frame pair with different raw byte length, even if the per-frame
  sample counts happen to round-trip).
- `M format/decode errors: ...`
  (file byte length is not a multiple of (channels × bits/8) — wrong encoding
  flag, or a corruption).

## Exit codes

| code | meaning |
|------|---------|
| 0 | sample-exact match over the compared prefix (every paired frame reads 0 differing samples, identical byte lengths, no leftover frames on either side) |
| 1 | any defect (differing sample, per-frame length mismatch, leftover frames, decode error) |
| 2 | misuse (missing dir, no `.pcm` files in either tree, no paired frames with the given start offsets) |

## Negative fixtures (built-in)

The four cases below all pass on the current code; they are what would close
the M9 row's "audio parity" acceptance:

1. **identical** → `total 0 differing samples ... worst 0 differing samples at k=-1, first divergent none`, exit 0
2. **mutated** (one sample in one frame changed by one LSB) → non-zero total, named worst sample (frame, channel, value A, value B, |delta|), exit 1
3. **truncated** (B side stops short of A) → per-frame pairs compared are sample-exact, but a `SAMPLE-COUNT MISMATCH` line reports the leftover frames on A and the exit is non-zero
4. **format mismatch** (one tree written as 8-bit unsigned instead of 16-bit signed) → per-frame byte-length mismatch lines, decode errors, exit 1

## What the tool deliberately does NOT do

- no resampling (the `--rate` flag is metadata; not used to resample either
  side, not used to pick a "closer" match)
- no alignment window (frame N pairs with frame N; cross-frame matching is
  the orchestrator's job, not the comparator's)
- no per-sample tolerance (any nonzero delta is reported, including the
  smallest possible ±1)
- no normalisation or DC removal
- no detection of "the two sides are bit-identical except for a global gain"
  (any such residue is reported as N differing samples, frame by frame, so
  the verifier can see WHERE the residue lives)
