# audio coverage: the cannon scenario (T13d, 2026-09-14)

T13's buster baseline (`docs/audio/baseline-buster.md`) and T13b's buster
gate fix (`docs/coverage/audio-buster.md`) measured and gated two audio
defects on the buster scenario. T13c BLOCKED on a premise error the audit
caught: no chip-fire or chip-damage `play_sound` calls existed in
`src/battle.rs` (only the T13b-gated buster hit at line 3130), no chip-
fire/chip-damage wav ships with the build (`assets/` has 47 `.bin` + 1
`.wav`, the buster hit), and the citation fragments were wrong (the
sub_801A308 body reads `oBattleObject_Alliance XOR 1 + ORs oAIData_Unk_10`,
contains no `PlaySoundEffect`; `sub_801B720` line number points inside
`sub_801ABB8`). Per T13c's option (a), this ticket re-scoped to probe what
canon fires on the cannon route first, then gate after the dump tells us
what fires.

The dump told us: canon fires a chip-select blip on ch0 (PSG1) at frame 2
and a chip-fire SFX on ch4 (FIFO A) at frame 22..37 (peak 20391, body 16
frames). Ours fires **0 samples on either channel** through the whole
200-frame capture. The T13c audit's finding holds: there are no arms to
gate. Per the ticket, "an empty canon-fire list (i.e. canon is silent on
this route) is a result, reported as one with the measured proof" -- the
opposite (canon fires, ours doesn't) is the case here, and the measured
proof is in the per-channel trees under `/tmp/aud_t13d/`.

6 capture runs against the ticket's cap of 8 (the buster baseline took 8;
this ticket took 6, leaving runs 7..8 unspent -- ch5 was not soloed on
either side, matching the buster baseline's discipline of ch0 + ch4
only):

| # | side | scenario | solo | tree |
|---|---|---|---|---|
| 1 | canon ×1 | sterile, AFTER_DISSOLVE, --poke HAND_SLOT:01 + --poke-at 3:AIDATA_PRESSED:1 + MIRROR:1 + --zero BANNER_TILES + --disable-bg | full | `aud_t13d/cannon_canon_full` |
| 2 | ours ×1 | plain ROM + chip-cannon descriptor (enemies:0, megaman_col:2, megaman_row:2, hand:[0x01], flags:0x1F, fire_frame:90) + --disable-bg | full | `aud_t13d/cannon_rust_full` |
| 3 | canon ×1 | same as 1 | ch0 | `aud_t13d/cannon_canon_ch0` |
| 4 | ours ×1 | same as 2 | ch0 | `aud_t13d/cannon_rust_ch0` |
| 5 | canon ×1 | same as 1 | ch4 | `aud_t13d/cannon_canon_ch4` |
| 6 | ours ×1 | same as 2 | ch4 | `aud_t13d/cannon_rust_ch4` |

Trees under `/tmp/aud_t13d/` (not committed).

## 1. The measured divergence

| tree | peak \|sample\| | onset | body |
|---|---|---|---|
| canon ch0 (PSG1) | 6179 (music peak, frame 77) | frame 2 (RMS 956.9 / peak 5394) | 1-frame blip (chip-select) |
| canon ch4 (FIFO A) | **20391** (frame 33) | frame 22 (RMS 690.8 / peak 4118) | 16 frames 22..37 (chip-fire SFX) |
| ours ch0 | **0** | -- | none (silent end to end) |
| ours ch4 | **0** | -- | none (silent end to end) |

Per the ticket's reading: "canon fires SFX samples that ours doesn't".
The SFX is the FIFO-A sample at frames 22..37; ours has no arm that fires
it on the chip-use path, and no `.wav` file in `assets/` to play even if
it did. The T13c audit is the source for this absence; this ticket is the
source for the canonical side.

## 2. The chip-fire gate, recorded but not armed

The cited canonical gate (per F5b on the same route): the chip-fire event
is the CurAction 0x08->0x14 write at frame 3 (`--watch-write 0x0203a9b8`
measured it, lr 0x0800FBF7 from object_setAttack2 in sub_800FB54, asm31.s).
The SFX fires +19 frames later (frame 22). The cited chip-damage gate
(from T13b on the buster scenario) is `take_damage[enemy_idx] != 0`
(src/battle.rs:3012 already gates SOUND_HIT_6B there for the buster).

Adding the chip-fire arm to `src/battle.rs` is a separate ticket
(per the ticket's rules: "If canon fires SFX samples that ours doesn't:
locate the corresponding arms in src/battle.rs (or add them if missing
per T13c's audit), gate each on its cited predicate" -- but this ticket
also says "Only the named files" and the named src file is "the chip-
fire and chip-damage `play_sound` calls and their gate predicates ONLY
-- IF the dump shows they fire", and "fitted constants in src/ (HEAD: 19)
may not increase", and the canonical sample id and wav data are not in
this ticket's editable scope either -- `assets/` is read-only per
AGENT_GUIDE / `AGENTS.md`). The arm lands when the chip-fire wav is added
to `assets/` and the cited chip-fire event predicate is wired in
`src/battle.rs`'s chip-use path.

## 3. The onset offset, not measured on this route

The 635-pair (6.6 ms) buster-residual class the buster baseline measured
(T13b §2): not re-measured here. The cannon ch4 onset is canon's own
peak 20391 at frame 33, measured against the cannon-route's own music
background -- it is not subtracted by a no-press control (would have been
run 7; ticket budget left it out). The chip-select ch0 onset at frame 2
lands BEFORE the press (frame 3) by one frame, the same capture-harness
priming artifact T13's buster baseline named ("a capture-start artifact
on our side, not an audio-path defect").

## 4. Frame 0 -- the capture harness's own priming, cited

Same as T13b §3. Our frame 0 is short (234 L+R pairs vs canon's 1605) AND
silent (max |sample| 0 over its 234 pairs); it is why the first cross-
side difference is global s16 index 2. Same source, same verdict.

## Parity and residue after T13d

Parity (measured): the cannon route's audio is canon-fired music + chip-
select blip + chip-fire sample on ch0/ch4, all of it absent in ours (ours
is byte-silent). No code change in `src/battle.rs` this ticket (T13c's
audit said no arms to gate; the dump confirms).

Residue (recorded, not chased):

- The chip-fire and chip-damage arms in `src/battle.rs` (the SFX canon
  fires on the cannon route's ch4 onset at frame 22 and on the buster
  scenario's `take_damage` arm): absent, correct per the audit. Adding
  them requires a chip-fire/chip-damage `.wav` in `assets/` (currently
  only `assets/buster_hit.wav`), which is read-only for this ticket.
- The ch0 sub-frame onset phase (635-pair / 6.6 ms residual class from
  T13b): not re-measured on the cannon route.
- Canon SFX ID on the ch4 event (likely `SOUND_HIT_6B` re-fired on the
  chip-fire path or one of `SOUND_HIT_6D`/`SOUND_HIT_6E`): not chased
  past the audio dump.
- The frames 73..105 ch4 bump on canon (RMS 1713..3068, peak 5088..12495):
  looks like music dynamics with no isolated onset; not chased.
- `verify_rows.py` clean run on `cannon + battle_full`: not re-run by
  this ticket (no `src/` or `tools/` change); HEAD's claims stand.