# windowclose row -- boot-frame coupling and the pad pin (T231)

Row: `windowclose` (isolated, frames 40, canon_ref 81, script-timed
Start@230/A@260 presses; negative not blind). The row's pass class is set by
the boot-capture marker phase, not by window code.

## The coupling

The harness aligns on `BATTLE_MARKER`'s first "BATT" appearance (never on
power-on frame counts), but the row's presses are script-timed at fixed capture
frames -- so a boot-timing shift that moves the marker's first appearance one
capture frame desyncs the presses from battle time (T220's "Battle-field layout
butterfly", docs/worklog/T220.md: measured marker origin 8 -> 9 under a
Battle-layout shift, whole upper screen of battle frame 0 differs, 63962/3557/40
signature, re-syncing from bf1).

History: the row read 0/0/40/207166 through T220's landing (0033d2d); the
drift to 63962/3557/40/266037 entered main with T216's landing (f440247,
pad 25->21, verified without re-reading windowclose). T230 proved the drift
byte-identical on main and the merged tree and pad-independent at {21,25}.

## The reclaim (T231)

`SEAM_PHASE_PAD_ITERS` (src/main.rs) is the pad the marker phase hangs on.
T231 sweep, post-T216 main a06d14e, windowclose+cursor measured:

| pad | windowclose | cursor |
|-----|-------------|--------|
| 20  | PASS 0/0/40, neg 207166 (the T220 line) | FAILED 1/1/170, neg 186279 |
| 21  | FAIL 63962/3557/40, neg 266037 (main's drift) | FAILED 1/1/170, neg 186279 |
| 22  | PASS 0/0/40, neg 207166 | FAILED 1/1/170, neg 186279 |
| 25  | FAIL 63962/3557/40, neg 266037 (T230) | FAILED 1/1/170, neg 186279 |

Pad 21 is the odd phase out: cursor's seam plateau still spans 20/21/22
(T230's sweep), but windowclose's marker phase at 21 crosses the boot vblank
boundary one frame off. **20 pinned** (T231): inside cursor's plateau AND at
windowclose's zero; 22 is an equally good spare. Full isolated table at 20:
every acceptance row at its target (windowclose 0/0/40/207166, cursor 1/1/170/
186279, emotion_skip 0/0/40/27760, blind_met 0/0/70/60901, mettaur 0/0/70/41734);
the only FAILED rows are the pre-existing known-fail pins (field-bg1/2/3,
buster_charge, gunner, navi-gunner(-ai), cursor), each at its documented line.

Any future code-layout change can re-roll the marker phase; windowclose,
cursor, mettaur are the sentinels (T220's rule).
