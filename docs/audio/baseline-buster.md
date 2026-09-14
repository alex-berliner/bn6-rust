# audio baseline: the buster scenario (T13, 2026-09-14)

Both sides' post-mix stereo dumped per frame (`mgba_capture --dump-audio`,
post-mix stereo s16 interleaved, one `frame.#####.pcm` per rendered frame)
and compared whole by `tools/audio_probe.py`: every sample, no resampling,
no trimming, no baseline subtraction. Then soloed per channel
(`--audio-channel`) to attribute the residue.

8 capture runs in the original pass, one at a time inside the 3-slot semaphore:

| run | side | audio dir |
|---|---|---|
| 1, 3 | canon ×2 (determinism pair) | `/tmp/aud_t13/aud_canon_v1`, `aud_canon_v2` |
| 2, 4 | ours ×2 (determinism pair) | `/tmp/aud_t13/aud_rust_v1`, `aud_rust_v2` |
| 5 | canon, `--audio-channel 0` | `aud_canon_ch0` |
| 6 | ours, `--audio-channel 0` | `aud_rust_ch0` |
| 7 | ours, `--audio-channel 4` | `aud_rust_ch4` |
| 8 | canon, `--audio-channel 4` | `aud_canon_ch4` |

Run count, stated plainly: the original pass used the ticket's cap of 8. A
revision pass then spent MORE, in two lots. Lot 1, deliberate: run 9, one
no-press canon control (`aud_canon_ch0_ctl` — same state, same enemy cheats,
same script, NO B pokes, `--audio-channel 0`), taken to make the blip onset a
measurement instead of an inference. Lot 2, accidental and disclosed: a
script-import mistake replayed the four full commands of runs 1-4 once more
(same argv, same output dirs), so the grand total is 13 capture runs. The
replayed trees re-verified byte-identical to their first versions, so no
number below changed; the replay bought nothing.

Scenario: the harness `buster` row's, reproduced flag for flag.
canon = `/tmp/bn6f_sterile.gba` from `/tmp/pausedwithcannon.state`,
`--cheat 0x0203ab84:0 --cheat 0x0203ab86:0` (enemy deleted),
`--script "Start@10"`, the 7 BUSTER_AIDATA_POKES (`--poke-at 130..133`:
B pressed+held 130, held 131, released 132, cleared 133). 200 frames.
ours = the plain release build (this worktree's), the 32 `--cheat` writes of
the BUSTER_ZERO fixture descriptor, `--script "B@108,B@109"`. 200 frames.
Neither side is `--ui isolated` (audio is not affected by BG/OBJ and the row's
isolated variant only blanks pixels).

Event clocks (both measured by the row): canon's fire (CurAction 0x11) is
capture frame 132; ours (ORCL action byte 0x08→0x0b) is capture frame 112.
The presses both sit at capture frame 130/108+0 — so a "press+k" pairing is
the honest shared clock, and the two sides' frame filenames are NOT the same
scenario moment (canon 132 pairs with ours 112), which is why the cross-side
tables below are per side, on each side's own fire frame.

mgba's channel id table (stderr, from `core->listAudioChannels`):
0 = PSG Channel 1 (Square/Sweep), 1 = PSG2, 2 = PSG3 (PCM), 3 = PSG4 (Noise),
4 = FIFO Channel A, 5 = FIFO Channel B.

## 1. Baseline, no soloing (200 frames each side)

| | canon | ours |
|---|---|---|
| total interleaved samples (L+R) | 642914 | 640170 |
| rate as mgba settles it (stderr "measured", = samples ÷ 3.348541 s) | 95999.1 Hz | 95589.4 Hz |
| `audioRateChanged` reports (do not trust) | 65536 Hz | 65536 Hz |
| peak \|sample\| | 19452 | 11221 |
| whole-tree RMS | 4746.8 | 734.4 |

Silence-vs-sound is a number: canon's tree is a battle-music mix (RMS 4746.8
over all 200 frames); ours is near-silent except the buster events (RMS 734.4
— the music our side does not play yet dominates the difference).

The 2744-sample tree-length mismatch: frame 0 accounts for 2742 of it (our
frame 0 drains 234 L+R pairs where canon's drains 1605), and the remaining
net 2 samples are the NET of 105 later frames whose per-frame pair counts
differ by small amounts each way (both sides stay within 1605..1618; the
tool's per-frame accounting puts 769 gross skipped L+R pairs on those 105
frames, netting to one pair). A capture-start artifact on our side, not an
audio-path defect — but it is a defect by this ticket's own standard (a
stated length mismatch) and it is reported as one.

## 2. Whole-tree comparison, canon vs ours (the tool, no soloing)

- frame pairing: 200 common frame names; per-frame byte lengths disagree at
  frame 0 (ours 234 vs canon 1605 L+R pairs) — the frame-0 artifact above.
- total samples: canon 642914 vs ours 640170 interleaved s16.
- first differing sample: global interleaved s16 index 2 — frame 0, offset 1,
  channel L; canon=1, ours=0. The two sides' captures disagree from the
  second sample of frame 0, as boot music on one side and silence on the
  other would predict. Nothing here is a parity number: the sides are not
  event-paired frame for frame, and the tool is not asked to pretend they are.
- differing samples: 639328 of 639402 COMPARED (99.9884%); the tool skips
  2140 L+R pairs where per-frame lengths differ (frame 0 alone is 1371 of
  them) and counts all 106 per-frame length defects while listing only the
  first 10 in detail ("... (96 more)"), so the skip is visible rather than
  silently compared at min(na, nb).
- max |Δ|: L 21956 (frame 119, offset 1438), R 19378 (frame 93, offset 1272).

## 3. Negative fixtures (both must read non-zero — they do)

- canon vs canon with channel R shifted +1 sample
  (`audio_probe.py shift ... R 1`): 317813 of 642914 differing, first at
  global index 1 (frame 0, offset 0, R), max |Δ| R 12360. NOT blind.
- canon vs a same-length all-zero tree (`audio_probe.py zero`): 642841 of
  642914 differing, first at global index 2, max |Δ| L 19452. NOT blind.

## 4. Determinism (the precondition for "sample-exact")

- canon run 1 vs run 2: `cmp` over the concatenated trees — byte-identical;
  the tool agrees: 0 differing samples of 642914.
- ours run 1 vs run 2: byte-identical; 0 differing samples of 640170.

Audio is frame-deterministic on BOTH sides. Sample-exact parity stays a
usable standard; no user decision is needed on this precondition.

## 5. Attribution: per-channel, on each side's fire frame

Per-frame RMS of the soloed runs around the fire frame. canon fires at 132,
ours at 112; both presses sit at "capture press frame + 0" (canon poke 130,
ours script 108), so "press+k" below is the shared clock.

canon `--audio-channel 0` (PSG1 Square/Sweep — the battle music and the
blip), and the same run with NO press (`aud_canon_ch0_ctl`) as a control:
the two whole trees subtract sample-exactly — EVERY pre-press frame,
including 12-27 where music alone reaches RMS 4234.6 / peak 8460, reads 0.0
in the difference, so the music cancels exactly and what follows is the
press's own measured consequence:

| frame | RMS of difference | peak of difference | nonzero diff samples |
|---|---|---|---|
| 12..134 (music only, control-subtracted) | 0.0 | 0 | 0 |
| 135 = press+5 (onset, partial frame) | 997.9 | 5381 | 486 of 3210 |
| 136 | 2790.4 | 9179 | 3167 |
| 137 | 2788.9 | 8140 | 3210 |
| 138 | 2670.6 | 6934 | 3212 |
| 140 | 2333.8 | 5723 | 3234 |
| 142 | 2123.3 | 5234 | 3210 |

The blip's own body is frames 135..142: a partial-frame onset at press+5,
peak 9179 at 136, decaying to 2123 by 142 — about 8 frames, beside the
ROM-data reading of a 7-tick gate. Both of those numbers are peaks/RMS of
the SUBTRACTION, not of the channel: the soloed ch0 in 135..142 is a
channel where the blip has REPLACED the music the control subtracts, so
the subtraction's peak there (9179) is not canon's own peak on that frame
(8366) — label accordingly when quoting either. And the decay endpoint is
measured against the ~3000 unattributed post-fire divergence floor the
next paragraph disclaims: by 142 the difference has already decayed INTO
that floor, so "2123" bounds the tail, it does not measure the blip alone. From frame 143 the difference does NOT
go back to zero: it stays near RMS 3000 to the end of the capture. That
sustained part is post-fire divergence between the pressed run and the
control (the fired shot changes state the music and scene read), NOT the
blip, and it is unattributed by this ticket. Without the control, the mix
bump sits at 136..138 and reads as press+6; the control moves the onset to
press+5 and shows the mix reading was a full frame late.

canon `--audio-channel 4` (FIFO A — M4A's sample bus, music only here):
RMS 393..2926 across 129..138 with no isolated onset; the 132→133 rise
(1446→2925) is the music's own dynamics, unattributed (the control run was
soloed on ch0, so it cannot clean this channel's reading).

ours `--audio-channel 0` (PSG1 — our fitted sweep, nothing else on this
channel all run: RMS 0.0 for frames 0..113 and 118..199):

| frame | RMS | peak |
|---|---|---|
| 114 = press+6 | 1090.2 | 4554 |
| 115 | 489.0 | 3465 |
| 116 | 12.0 | 30 |
| 117 | 0.5 | 1 |
| 118.. | 0.0 | 0 |

ours `--audio-channel 4` (FIFO A — the agb mixer, `assets/buster_hit.wav`):
0.0 for frames 0..117 and from 131 on; the event spans frames 118..130 (13
frames, the whole wav body), whose first frame is the one quoted: frame 118
= press+10, RMS 2175.9, peak 11221.

Attribution, measured:

- The fire blip is PSG channel 0 (mgba id 0) on BOTH sides, at slightly
different press latencies: canon's onset is press+5 (partial frame, first
full frame press+6, measured against its own no-press control); ours is
press+6 (full frame; ch0 is silent to the sample in our other 196 frames).
One frame apart, not equal.
- The residue is NOT one channel: ours fires a SECOND sound canon's run does
  not show — the `buster_hit.wav` through the agb mixer (FIFO A, id 4) at
  press+10, peak 11221, on a scenario with no enemy to hit. Canon's own
  `--audio-channel 4` shows no isolated event at press+10 above its music.
  This ticket names the channel, not the routine (the hit path in
  src/battle.rs is the suspect; fixing it is a src ticket this one feeds).
- Canon's blip envelope, now measured against the no-press control (ch0,
  frames 135..142): partial-frame onset at press+5, peak 9179 at 136 (a
  peak of the subtraction on a channel where the blip replaced the music;
  canon's own peak at 136 is 8366), decay to 2123 by 142 — measured
  against the ~3000 unattributed post-fire floor, so it is an upper bound
  on the tail, not a pure-blip figure. About 8 frames beside the ROM
  data's 7-tick gate reading.
  This is a measurement of canon's own PSG channel, not a target;
  src/battle.rs's `BUSTER_BLIP_ENVELOPE` (fitted, initial_volume 6, 2-frame
  software stop) remains what its own tag says it is — now with a
  control-subtracted same-scenario measurement beside it.

## Unverified (named limits of this ticket)

- The envelope MECHANISM on canon's side: the control-subtracted shape
  (partial-frame onset, 8-frame decay, software-like tail) is measured, but
  which M4A mechanism produces it is not settled by this ticket.
- Our ch4 event's 13-frame body (118..130) against the wav's documented
  ~10.7-frame body (1881 samples at 10512 Hz): an open timing question on
  the mixer-rate path, recorded here and NOT chased.
- The sustained post-fire difference on canon's ch0 from frame 143 (RMS
  ~3000 to capture end): post-fire divergence, unattributed.
- Frame determinism holds for THESE runs on THIS box; step 4 is one pair of
  runs per side, not a proof over reboots/loads.

Trees live under `/tmp/aud_t13/` (not committed); the tool and this report
are the ticket's deliverables.
