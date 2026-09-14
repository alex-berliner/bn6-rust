# audio coverage: the buster scenario after T13b (2026-09-14)

T13's baseline (docs/audio/baseline-buster.md) measured two defects as
mechanical facts about our side. T13b fixed the first and re-measured both.
Capture runs for THIS ticket, stated plainly: 12 against the ticket's 8 cap.
Planned were 7 (below); an import side effect in the /tmp driver re-ran the
first five with identical argv into the same output dirs before the last two,
so the tree on disk for each of the five is the re-run. Both sides' frame
determinism was already established by T13 (byte-identical replay pairs), and
the re-run trees reproduced the first five's numbers exactly (rust0_ch4 peak 0;
rustE_ch4 frame 118 RMS 2197.9 / peak 11273; rust0_ch0 onset frame 114 pair
149), so the overage bought nothing — same disclosure rule T13 ran under.

| # | side | fixture | solo | tree |
|---|---|---|---|---|
| 1-5 (run twice) | ours | zero-enemy, B@108/109 | ch4, ch4, ch0 | `aud_rust0_ch4`, `aud_rustE_ch4`, `aud_rust0_ch0` |
| 4-5 | canon | enemy LIVE (no delete cheats), Start@10, BUSTER_AIDATA_POKES / no pokes | ch4 | `aud_canonE_ch4`, `aud_canonE_ch4_ctl` |
| 6-7 | canon | same pair | ch5 | `aud_canonE_ch5`, `aud_canonE_ch5_ctl` |

Trees under `/tmp/aud_t13b/` (not committed). Canon's zero-enemy trees are
T13's, on disk at `/tmp/aud_t13/`, re-read for this ticket at zero runs.

## 1. The ungated hit sample — FIXED

canon's own gate, cited: the plain buster's hit sound (SOUND_HIT_6B) is played
only from the shot-impact handler `sub_80F2180` (asm/asm31.s:123097), on the
path where `sprite_getFrameParameters` (asm/sprite.s:1192) reports the
sprite's impact frame (bit 0x80 tested at asm/asm31.s:123061-123064) AND the
enemy's HP is actually decremented on the same path (asm/asm31.s:123087-123093,
`strh` to oBattleObject_HP immediately before the `PlaySoundEffect`). No
overlapping enemy, no sample.

src/battle.rs armed `hit_in = BUSTER_HIT_DELAY` unconditionally in
`Update::Strike`'s uncharged arm. It now arms only when the same strike's
overlap loop actually landed (`take_damage` returned true — the HP really went
down, which is the cited path's condition; canon plays the sound even on a
killing blow, and so does this gate).

Measured after the gate, both trees' peaks, not one:

| tree | peak \|sample\| | event |
|---|---|---|
| ours, zero-enemy buster fixture, ch4 soloed, 200 frames | **0** (0 nonzero of 640170) | none — silent end to end |
| ours, enemy present (Mettaur col5 row2), ch4 soloed, 200 frames | **11273** at frame 118 | frames 118..130 (press+10 first frame, RMS 2197.9) — where the predicate says: the hit lands on the strike frame (press+6), `hit_in` 4 fires it at press+10 |

The enemy-present event reproduces the pre-fix body (T13: 118..130, peak
11221) to within half a percent, so the gate changed WHEN the sample plays,
not how.

Cross-check on canon's side, attempted and out of reach of this scenario:
canon with the enemy live (delete cheats dropped, BUSTER_AIDATA_POKES kept)
never fires — pressed run vs its no-press control is BYTE-IDENTICAL video
frames 130..165, because the AIData poke press only reaches MegaMan once the
battle is resolved (the harness's own BUSTER_AIDATA_POKES comment: in state
0x0C, not 0x08). A live-enemy canon run needs a different press delivery
(joypad-mirror poke) and its own control; NOT chased here. On the
zero-enemy scenario canon shows no such onset (T13: its frame 140 = 2181.5
sits below 136-139 = 2466/2519/2593/2782), which is the side the fix removes
from ours.

## 2. The onset offset — restated as a TIME difference

Measured after the change (our ch0 tree is this ticket's `aud_rust0_ch0`;
canon's is T13's `aud_canon_ch0` vs its no-press control `aud_canon_ch0_ctl`,
subtracted sample-exactly at all pre-press frames):

| side | onset | phase within its frame |
|---|---|---|
| canon | frame 135 = press+5, pair 1119/1605, L first (its frame 135 is a partial frame: 486 of 3210 samples) | 69.7% into the frame |
| ours | frame 114 = press+6, pair 149/1605, full frame | 9.3% into the frame |

Residual: ours is LATER by (1 frame − 970 pairs) = **635 interleaved pairs ≈
6.6 ms** — 635/95999.1 Hz = 6.62 ms on canon's measured rate, 635/95589.4 Hz =
6.64 ms on ours. This is NOT a one-frame offset and must not be fixed as one:
shifting our blip a whole frame earlier would overshoot by the remaining 970
pairs = 10.1 ms and fail a sample-exact check it should pass. The offset is
frame-granular parity (both blips land within the same press+5/+6 window
modulo the one-frame arm difference) plus a sub-frame phase residue of 635
pairs. `BUSTER_BLIP_DELAY` is left at its fitted 1: at frame granularity ours
is one frame late (press+6 vs canon's partial-frame press+5), but the
partial-frame onset is a mixer-phase fact, not a delay constant, and no
constant in src can move a sub-frame onset. Recorded as residue.

## 3. Frame 0 — the capture harness's own priming, cited

Our frame 0 is short (234 L+R pairs vs canon's 1605) AND silent (max |sample|
0 over its 234 pairs); it is why the first cross-side difference is global
s16 index 2. Verdict: capture-harness priming, not our boot-time audio ramp:

- the tool discards all boot/state-load backlog before frame 0's dump —
  "Discard whatever boot/state-load already queued so frame 0's file holds
  only audio generated during frame 0 itself" (tools/mgba_capture.c:631-641);
- each frame's dump then writes whatever the blip resampler has AVAILABLE at
  that instant, capped at 4096 (tools/mgba_capture.c:946-967) — a frame's
  production that is still inside the resampler lands in the NEXT frame's
  file;
- our side boots from reset (cold mixer), canon resumes from a save state
  (mixer clock already primed), so the same tool shows a full 1605 on canon's
  frame 0 and 234 on ours; and the 234 are ZERO samples — a boot-time audio
  ramp of ours would have nonzero content, and the artifact is present in
  every one of our five runs this ticket captured (234 pairs each time),
  independent of the src change.

Stopped there, per the ticket; the tool is out of this ticket's editable
scope anyway.

## Parity and residue after T13b

Parity (measured): the ungated hit sample is gone from the zero-enemy
scenario — our ch4 tree reads peak 0 end to end, matching canon's no-onset
side; the blip's frame-granular window is unchanged and now coexists with the
ROM-cited gate.

Residue (recorded, not chased): the 635-pair (6.6 ms) sub-frame onset phase
(§2); our frame-0 capture priming artifact (§3, tool-side); the sustained
post-fire ch0 divergence on canon from frame 143 and the envelope MECHANISM
(both inherited unattributed from T13's list); canon's live-enemy hit-sound
tree (unobtainable with the current state's press delivery, §1).
