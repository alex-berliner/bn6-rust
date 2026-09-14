# audio baseline: the buster scenario (T13, 2026-09-14)

Both sides' post-mix stereo dumped per frame (`mgba_capture --dump-audio`,
post-mix stereo s16 interleaved, one `frame.#####.pcm` per rendered frame)
and compared whole by `tools/audio_probe.py`: every sample, no resampling,
no trimming, no baseline subtraction. Then soloed per channel
(`--audio-channel`) to attribute the residue.

8 capture runs total, one at a time inside the 3-slot semaphore (budget 8/8):

| run | side | audio dir |
|---|---|---|
| 1, 3 | canon ×2 (determinism pair) | `/tmp/aud_t13/aud_canon_v1`, `aud_canon_v2` |
| 2, 4 | ours ×2 (determinism pair) | `/tmp/aud_t13/aud_rust_v1`, `aud_rust_v2` |
| 5 | canon, `--audio-channel 0` | `aud_canon_ch0` |
| 6 | ours, `--audio-channel 0` | `aud_rust_ch0` |
| 7 | ours, `--audio-channel 4` | `aud_rust_ch4` |
| 8 | canon, `--audio-channel 4` | `aud_canon_ch4` |

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

The 2744-sample tree-length mismatch is ONE frame: our frame 0 drains 234
L+R pairs where canon's drains 1605 (every later frame is 1605..1618 on both
sides). A capture-start artifact on our side, not an audio-path defect —
but it is a defect by this ticket's own standard (a stated length mismatch)
and it is reported as one.

## 2. Whole-tree comparison, canon vs ours (the tool, no soloing)

- frame pairing: 200 common frame names; per-frame byte lengths disagree at
  frame 0 (ours 234 vs canon 1605 L+R pairs) — the frame-0 artifact above.
- total samples: canon 642914 vs ours 640170 interleaved s16.
- first differing sample: global interleaved s16 index 2 — frame 0, offset 1,
  channel L; canon=1, ours=0. The two sides' captures disagree from the
  second sample of frame 0, as boot music on one side and silence on the
  other would predict. Nothing here is a parity number: the sides are not
  event-paired frame for frame, and the tool is not asked to pretend they are.
- differing samples: 639328 of 640170 (99.87%).
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

canon `--audio-channel 0` (PSG1 Square/Sweep — the battle music and the blip):

| frame | RMS | peak |
|---|---|---|
| 129..135 (music alone) | 1368..1632 | 4159..4344 |
| 136 = press+6 | 2285.5 | 8366 |
| 137 | 2129.1 | 6745 |
| 138 | 1967.5 | 5463 |

canon `--audio-channel 4` (FIFO A — M4A's sample bus, music only here):
RMS 393..2926 across 129..138 with no isolated onset; the 132→133 rise
(1446→2925) is the music's own dynamics, unattributed (no no-press control
was captured — the 8-run budget went to the pairs above).

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
0.0 everywhere except frame 118 = press+10, RMS 2175.9, peak 11221.

Attribution, measured:

- BOTH sides' fire blip is PSG channel 0 (mgba id 0), and both land on
  press+6 — the fire-phase-relative latencies differ (canon fire+4, ours
  fire+2) because the fire phase itself sits at different press offsets.
- The residue is NOT one channel: ours fires a SECOND sound canon's run does
  not show — the `buster_hit.wav` through the agb mixer (FIFO A, id 4) at
  press+10, peak 11221, on a scenario with no enemy to hit. Canon's own
  `--audio-channel 4` shows no isolated event at press+10 above its music.
  This ticket names the channel, not the routine (the hit path in
  src/battle.rs is the suspect; fixing it is a src ticket this one feeds).
- Canon's blip envelope over its 7-tick gate (its ch0 frames 136..142, the
  gate the ROM data reads as 7 tempo ticks) is NOT separable here: the blip
  sits under 1368..1632 RMS of music, and the 8-run budget bought no
  no-press control to subtract. What IS measured: canon's ch0 peak rises
  4163→8366 at 136 and decays 6745/5463 on 137/138, and the whole-tree RMS
  bump spans at most frames 136..138. This is a measurement of canon's ch0
  MIX on those frames, not a clean envelope and not a target; src/battle.rs's
  `BUSTER_BLIP_ENVELOPE` (fitted, initial_volume 6, 2-frame software stop)
  remains what its own tag says it is — now with a same-scenario measurement
  beside it instead of only the old control-subtracted one.

## Unverified (named limits of this ticket)

- Whether the residue is driver timing or envelope mechanism: the blips'
  press-relative onsets agree (press+6 both sides) but the blips' shapes were
  never isolated from canon's music.
- Frame determinism holds for THESE runs on THIS box; step 4 is one pair of
  runs per side, not a proof over reboots/loads.

Trees live under `/tmp/aud_t13/` (not committed); the tool and this report
are the ticket's deliverables.
