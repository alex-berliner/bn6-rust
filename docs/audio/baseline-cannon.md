# audio baseline: the cannon scenario (T13d, 2026-09-14)

Both sides' post-mix stereo dumped per frame (`mgba_capture --dump-audio`,
post-mix stereo s16 interleaved, one `frame.#####.pcm` per rendered frame)
and compared whole by `tools/audio_probe.py`: every sample, no resampling,
no trimming, no baseline subtraction. Then soloed per channel
(`--audio-channel`) to attribute the residue. Same procedure as T13's buster
baseline (`docs/audio/baseline-buster.md`).

6 capture runs against the ticket's cap of 8 (1..6 below; runs 7..8
deliberately not spent, the ch0/ch4 solos already answered the residue
question):

| run | side | solo | tree |
|---|---|---|---|
| 1 | canon ×1 | full | `/tmp/aud_t13d/cannon_canon_full` |
| 2 | ours ×1 | full | `/tmp/aud_t13d/cannon_rust_full` |
| 3 | canon ×1 | `--audio-channel 0` | `/tmp/aud_t13d/cannon_canon_ch0` |
| 4 | ours ×1 | `--audio-channel 0` | `/tmp/aud_t13d/cannon_rust_ch0` |
| 5 | canon ×1 | `--audio-channel 4` | `/tmp/aud_t13d/cannon_canon_ch4` |
| 6 | ours ×1 | `--audio-channel 4` | `/tmp/aud_t13d/cannon_rust_ch4` |

mgba's channel id table (stderr, from `core->listAudioChannels`):
0 = PSG Channel 1 (Square/Sweep), 1 = PSG2, 2 = PSG3 (PCM), 3 = PSG4 (Noise),
4 = FIFO Channel A, 5 = FIFO Channel B. (The ticket's "four audio channels
(ch0/1/2/3, FIFO A; ch4/5/6/7, FIFO B" reads a typo for the standard 4 PSG +
2 FIFO = 6 channels per mgba_capture.c:46-58; ch5 was not soloed in this
pass and shows below the music floor in T13's buster data.)

Scenario: the harness `cannon` row's, reproduced flag for flag. The ticket
cites `_chip_canon_0c("01")` (harness.py:868), so the canon side is the
sterile ROM + AFTER_DISSOLVE state + library_pokes("01") + HAND_SLOT:0x01 +
`--poke-at 3:0x020340a4:0x0001` + `--poke-at 3:0x02036822:0x0001` +
`--zero 0x6016E00:1280` (BANNER_TILES) + `--disable-bg`; the ours side is
the plain release build + the chip-cannon descriptor (`enemies:0,
megaman_hp:100, megaman_col:2, megaman_row:2, hand:[0x01], hand_count:1,
gauge:0, flags:0x1F, fire_frame:90`) + `--disable-bg`. 200 frames. No
script (the fire event lands at frame 3 of the capture, the first visible
attack frame at frame 5 -- the +2 lead from CurAction write 0x08->0x14 to
the first visible attack frame measured by F5b on the same route).

## 1. Whole-tree, no soloing (200 frames)

| | canon | ours |
|---|---|---|
| total interleaved samples (L+R) | 642914 | 640170 |
| rate as mgba settles it (stderr "measured", = samples ÷ 3.348541 s) | 95999.1 Hz | 95589.4 Hz |
| `audioRateChanged` reports (do not trust) | 65536 Hz | 65536 Hz |
| peak \|sample\| | 27323 | **0** |
| whole-tree RMS | 4559.5 | **0.0** |

Ours is **byte-silent end-to-end**: 0 nonzero samples in 640170 interleaved
s16 (every pcm frame, every channel). Canon is the same battle-music mix
the buster baseline saw (RMS 4559.5 vs T13's 4746.8 on buster -- same
scenario, different chip, same music, slightly different dynamics). The
peak 27323 lands at frame 33 -- inside the ch4 event window -- see §3.

## 2. Whole-tree comparison, canon vs ours (the tool, no soloing)

- frame pairing: 200 common frame names; per-frame byte lengths disagree at
  84 frames (the same capture-harness priming artifact T13's buster pass
  measured: frame 0 ours 234 vs canon 1605 L+R pairs, plus the same per-
  frame ±1 pair jitter on the rest). Same source, same report (T13 §1).
- total samples: canon 642914 vs ours 640170 interleaved s16.
- first differing sample: global interleaved s16 index 2 -- frame 0, offset
  1, channel L; canon=2, ours=0. The two sides' captures disagree from the
  second sample of frame 0, as battle music on one side and silence on the
  other predicts.
- differing samples: 639510 of 639552 COMPARED (99.9934%); the tool skips
  1990 L+R pairs where per-frame lengths differ (frame 0 alone is 1371 of
  them) and counts all 84 per-frame length defects while listing only the
  first 10 in detail ("... (74 more)").
- max |Δ|: L 19317 (frame 64, offset 1263), R 27323 (frame 33, offset 1272).
  Frame 33 is the ch4 peak (§3) -- the largest single-sample gap is exactly
  the one the SFX event causes.

## 3. Per-channel attribution

### canon `--audio-channel 0` (PSG1, Square/Sweep)

Two distinct features: (a) the chip-select blip at frame 2, the same shape
T13 saw on the buster scenario's ch0 (frame 2 RMS 956.9 / peak 5394, single
frame's worth of burst before music settles in); (b) sustained battle
music across frames 3..200 with RMS ~1600 and peak ~4200 (no isolated
envelope shape, no second onset).

| frame | RMS | peak |
|---|---|---|
| 0..1 | 0.0 | 0 |
| **2** = press-1 | **956.9** | **5394** |
| 3..21 | 1595..1641 | 4161..4250 |
| 22..60 | 1503..1694 | 4144..5366 |
| 61..76 | 722..1779 | 2360..6179 |
| 77..200 | 1453..1868 | 4144..6179 |

The chip-select blip onset (frame 2) lands BEFORE the press (frame 3) by
one frame: the capture-harness priming on a save-state-loaded mixer primes
the blip in the same way T13's buster baseline saw it. Same shape, same
offset, same artifact (T13 §3 -- "a capture-start artifact on our side, not
an audio-path defect"); the same control would measure the partial-frame
onset phase as for buster, but the ticket only asks for the per-channel
peaks and onset, not the control.

### canon `--audio-channel 4` (FIFO A, sample bus)

The cannon-fire event sits here. Frames 0..21 are music only (RMS ~100..1854,
peaks ~415..4826), then a big isolated SFX event spans frames 22..37 (RMS
2534..6582, peak up to **20391 at frame 33**), then music tails back to a
floor (RMS 481..3016 frames 38..72), then a second quieter SFX-like feature
frames 73..105 (RMS 1713..3068, peak 5088..12495 -- sustained music with
slight bumps; no isolated onset inside this window).

| frame | RMS | peak |
|---|---|---|
| 0..2 | 104..136 | 412..416 |
| 3..21 | 184..1854 | 876..4826 (music only) |
| **22** | **690.8** | **4118** (first frame of SFX event) |
| **23** | **3996.3** | **13246** |
| **24** | **4511.6** | **14111** |
| 25..37 | 2534..6582 | 8936..20391 (frame 33 = peak 20391) |
| 38..60 | 1522..3016 | 3831..11571 |
| 61..72 | 350..1827 | 1492..4786 |
| 73..105 | 1713..3068 | 5088..12495 |
| 106..199 | 116..1859 | 614..6079 |

Press at frame 3 + first visible attack frame at frame 5 + SFX onset at
frame 22 = **press+19**. The event body is 16 frames long (22..37), about
the same body length the buster scenario's ours-side ch4 hit-sample
showed (13 frames), which suggests a FIFO-A sample of comparable duration
on both scenarios. The frame-33 peak of 20391 is canon's own peak
(unsubtracted; no no-press control was taken on this route), so the value
is canon's own channel reading at its highest-energy sample.

What canon's SFX ID is on this path: not chased in this ticket (the
gate-arm work in §4 below happens in the ROM data, not the audio dump).
The candidate samples are `SOUND_HIT_6B` (0x6B, the hit-flash / HP-decrement
sound the buster scenario uses on FIFO A; same sample, different trigger
-- see SOUND_HIT_6B's byte_81597A0 sample at dat37.s) and the chip-fire
sample at `sub_8008900` (asm00_1.s:11637) and its sibling
`sub_8008D18` (asm00_1.s:12184), which both `PlaySoundEffect` with id
**0x9F** (a SOUND_UNK_9F, not in the named half of SoundOffsets.inc).
Both call sites are inside the chip-select/chip-use state-machine, not
the chip-fire impact path. The chip-damage sample (enemy takes HP off the
fire) is one of `SOUND_HIT_6D` (0x6D) or `SOUND_HIT_6E` (0x6E) per the
T13c audit's identification. Confirmed against the ROM data; not loaded
into ours.

### ours `--audio-channel 0` and `--audio-channel 4`

**Both silent.** 0 nonzero samples of 640170 interleaved s16 on ch0; 0 on
ch4. Confirms the T13c audit's finding: there are no `play_sound` arms
for chip-fire or chip-damage in `src/battle.rs` (the only `play_sound`
call in the file is the T13b-gated buster hit at line 3130), and no
chip‑fire/chip‑damage wav ships with the build (`assets/` has 47 `.bin`
files and 1 `.wav`, the buster hit). On the cannon route ours fires zero
samples on both channels through the full 200-frame capture.

## 4. Where the chips should land, documented but not armed

Per T13c's audit (still OPEN: `play_sound` arms for chip-fire and
chip-damage don't exist in `src/battle.rs`, and the chip-fire/chip-damage
wav files don't exist in `assets/`):

- chip-fire (the launch sound canon fires on FIFO A at press+19, peak
  20391): add a `mixer.play_sound(channel)` arm in `src/battle.rs`'s
  chip-use path, gated on the sequencer's chip-fire event (the same
  CurAction 0x08->0x14 write F5b watches for, on the chip arm). Add the
  chip-fire wav to `assets/`. Not done in this ticket; the audio
  measurement is the deliverable, not the src change.
- chip-damage (a `SOUND_HIT_6D` or `SOUND_HIT_6E` play canon fires when
  `take_damage[enemy_idx] != 0`; on this zero-enemy route there is no
  enemy to damage, so canon's chip-damage arm does not fire in this
  measurement -- only the chip-fire arm fires, the one in §3 above).

If/when the chip-fire arm lands, the cited gate is the chip-use path's
chip-fire event (F5b's measured write chain, plus the same `+2` lead the
harness pins); the cited chip-damage gate is the same `take_damage` arm
T13b added for the buster (src/battle.rs:3012), with the existing
hit-sample already gated there for the buster's SOUND_HIT_6B.

## Unverified (named limits of this ticket)

- The canon SFX ID on the ch4 event at frames 22..37: not chased into the
  ROM data (only the FIFO-A envelope shape and timing). The candidate is
  `SOUND_HIT_6B` re-fired on the chip-fire path, or a chip-specific
  sample id (the chip-fire sites in asm00_1.s call 0x9F, not 0x6B; the
  cannon-impact sample is one of 0x6D/0x6E, not verified here).
- The 6.6 ms sub-frame onset phase the buster baseline measured: not
  re-measured on this route; no no-press canon control was taken (would
  have been run 7; ticket budget left it out, canon's own peak 20391 at
  frame 33 is reported unsubtracted).
- The frames 73..105 ch4 bump: looks like music dynamics with no
  isolated onset inside it; not chased.
- Frame determinism: the ticket does not require it, but the buster
  baseline's two-run pairs (run 1 vs run 2 byte-identical on both sides)
  gives every reason to believe cannon's trees are frame-deterministic
  too; not measured here.

Trees live under `/tmp/aud_t13d/` (not committed); the tool and this
report are the ticket's deliverables.