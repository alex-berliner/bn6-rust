# emotion window -- the navi's face in the battle HUD

Rows: `emotion_syn` (isolated, frames 40, ALIGN_CHIP), plus T122's
`emotion_face_b` (slot 4 through AIData.Unk_36) and `emotion_skip` (canon's
blink countdown byte pinned to 5 -- face gone on BOTH sides; pairing evidence
for the align window, not face coverage -- see below).

## What the rows prove

Canon's face-selection gate is reproduced for THREE states, all via the
landed `assets/emotion.bin` bank and `src/emotion.rs`'s per-face palettes:

- `emotion_syn`: canon with `AIData.Unk_32` poked to 1 (0x020340B2) draws the
  slot-2 face from `off_801CD08[2]` (dword_872DB14) with slot 2's own palette;
  ours (descriptor `emotion=2`, `FACE_INDEX[2] = 0x300`) renders the same 40
  frames byte-exactly (PASS 0/0/40, frame-shift negative not blind, 644).
- `emotion_face_b` (T122): canon with `AIData.Unk_36` poked to 1 (0x020340B6)
  -> enum 5 -> slot 4 (`off_801CD08[4]` = bank +0x600, slot 4's palette, which
  DIFFERS from slot 2's in the ROM); ours (`emotion=4`) reads 0/0/40, negative
  not blind (644). The port's per-face PALETTE upload is under test here, not
  just slot 2's art.
- `emotion_skip` (T122): the blink countdown byte pinned to 5. eStruct2035280+0xf
  (0x0203528F) is NOT the face slot and NOT a "skip" flag: it is the 12-step
  blink countdown owned by sub_801CC94 -- asm00_2.s:27550-27551 loads 0xc into
  it, :27557-27566 decrements it once per frame and reloads at 0, and
  :27567-27574 copies the 0x20-byte blink pattern byte_801CDA4 ->
  byte_30016D0 off bit 1 of that same byte. The face slot lives at +0x10/+0x11
  (asm00_2.s:27341-27342, read back at :27403). The draw gate's `cmp #6` /
  `cmp #5` (asm00_2.s:27648-27652) are therefore two phases of a 12-frame blink
  cycle: canon suppresses the face window about 2 frames per cycle -- that IS
  the blink. The row pins 0x0203528F = 5 (aligned halfword poke
  0x0203528E:0x0500; the other byte of that poke lands on +0xe, the
  beast-out counter -- see the chain section -- which reads 0x03 on this
  route, NOT 0 as T122's comment claimed (T123 measured byte 0x03 flat over
  100 frames); the poke zeroes it mid-window, which T122 measured harmless
  there -- face-ONLY, 694 px/frame), and `drawEmotionWindow_801CDEC` emits NO
  OBJ for countdown 5/6 (asm00_2.s:27647-27652; T108 measured byte=5 -> face
  gone).
  T225 WON THE ROW BACK BY MECHANISM: the port now models the countdown byte
  (`src/emotion.rs`'s `blink_countdown`/`blink_cycles`, gated in `show` exactly
  like canon's drawer at asm00_2.s:27762-27768; the active arm of sub_801CC94 --
  per-frame decrement, wrap-reload of the canon period 0xc -- is transcribed in
  `Emotion::update`; the ARMING path and the bit-1 overlay queue are still
  unported, see unverified) and takes its initial value from descriptor +64
  (`blink_countdown`, the descriptor mirror of canon's at-load poke
  0x0203528e:0x0500). The static "emotion=5 builds no sprites" arm is DELETED:
  slots 5/6 build sprites like every other slot (T123 verified the slot-5
  render pixel-exact). Row reads 0/0/40 and the negative is the ZEROED PORTED
  WRITE (harness `negative_rust`: the same descriptor with blink_countdown 0),
  which must read the slot-5 face -- negative 27760 = 694 px/frame flat in the
  face box, T123's measured profile: the row fails through the ported blink
  arm, not through a frame shift.

**When the countdown arms (T123, read off sub_801CC94 asm00_2.s:27520-27600
and confirmed by a 100-frame watch):** the countdown does NOT free-run. A
period halfword r5[0x38] reloads 0x14 (20) per blink; when it expires and the
state conditions allow (r5[0x15]==0 needs r5[0x1e]!=0; r5[0x15]!=0 needs
r5[0x17]!=0xff), `GetPositiveSignedRNGSecondary & 1 + 1` arms 1 or 2 blinks
(r5[0x1d]), each 12 frames (r5[0xf] = 0xc at :27550-27551, decremented at
:27557-27566, reload at 0 while blinks remain); the 0x20-byte blink overlay
pattern copies while the PRE-decrement countdown has bit 1 set (:27567-27574).
MEASURED on the descriptor route (T123, probe.py watch, emotion_syn recipe,
100 capture frames): the countdown reads 0x00 on EVERY frame -- the blink
never arms, so the 5/6 blanking phases never occur in any compared window
here. Slots 5/6 DO draw on canon whenever the countdown is not in a blink: see the
skip-range note below for the cross state. (T225 landed exactly this: the
static 5/6 arm is deleted, the countdown byte is modeled, and the row is won
back with the zeroed-write negative -- 27760.)

Measured poke effects (T122 step 2, canon 43..82, each poke against the same
recipe with no face poke): both pokes are face-ONLY -- 27760 total = 694
px/frame flat in the face box x0..48/y18..34, 0 px everywhere else.

## The tables (T122, read straight out of the ROM bytes --
## /tmp/bn6f_sterile.gba af13c206…, file offset = addr - 0x08000000)

**`byte_801E6F4` @ 0x0801E6F4** (asm00_2.s:31045) — the emotion ENUM → face
slot table, **6 entries + 2 pad** (the ticket's "23-entry" premise was wrong:
this table is 8 bytes). Indexed with the enum from
`possiblyGetBattleEmotion_8015B64` (asm00_2.s:15122-15174, stride 1, e.g.
asm00_2.s:30970/30997/31033):

| enum | 0 | 1 | 2 | 3 | 4 | 5 | (6, 7 pad) |
| slot | 0 | 2 | 3 | 1 | 5 | 4 | 0, 0 |

- enum 0 = calm; 1 = Unk_32≠0; 2 = Mood==0xff; 3 = Anger≠0; 5 = Unk_36≠0 or
  Mood==0 (check order asm00_2.s:15140-15166).
- **enum 4 → slot 5 is UNREACHABLE**: the routine never returns 4. So no
  AIData poke can land a slot in the skip range through the ENUM table --
  but the transformation table below does reach 5/6 (a cross state's own
  faces), and the draw gate does not block them: see the skip-range note.

**`byte_801E700` @ 0x0801E700** (asm00_2.s:31049) — the TRANSFORMATION → base
face slot table, **25 entries + 3 pad**, indexed by the second return
(oNaviStats_Transformation) of possiblyGetBattleEmotion, consumed by
sub_801E6A8/sub_801E660 (asm00_2.s:30962-31001). This is the 23+-entry table
the ticket was after:

| transformation | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 | 21 | 22 | 23 | 24 | (25..27 pad) |
| base slot | 0 | 5 | 6 | 7 | 8 | 9 | 5 | 6 | 7 | 8 | 9 | 20 | 20 | 15 | 16 | 17 | 18 | 19 | 15 | 16 | 17 | 18 | 19 | 22 | 22 | 0, 0, 0 |

Post-adjustments (asm00_2.s:30975-31001): transformation 1..10 → +5 when
`byte_801E6F4[enum] == 2` (full synchro: cross faces 5..9 become 10..14);
transformation 11/12 → +1 when `byte_801E6F4[enum] == 3` (beast out with
Mood==0xff: the test at asm00_2.s:31022-31025 is on the RESOLVED SLOT value 3,
and slot 3 comes from enum 2 = Mood==0xff, `byte_801E6F4[2] = 3` -- Anger is
enum 3 → `byte_801E6F4[3] = 1`, a different arm). Slot 20 becomes 21.

**Skip range (5/6) entries**: `byte_801E6F4[4] = 5` (unreachable enum, above)
and `byte_801E700[1] = 5`, `[2] = 6` -- reachable via a non-zero
transformation byte, i.e. a cross/beast state. The upload path's `cmp #5`
(asm00_2.s:27390, `bge loc_801CBBE`) only skips the blink *bookkeeping* --
`loc_801CBBE` (asm00_2.s:27404) IS the upload -- so a transformation-resolved
slot 5 (e.g. `byte_801E700[1] = 5`, a cross state) is uploaded and drawn
whenever the blink countdown is not sitting at 5/6. Our `emotion_skip` row
does NOT exercise this path; it pins the blink countdown byte 0x0203528F = 5
instead (an empty box against an empty box).

**The cross state itself (T123, measured -- recipe for the battle-side
ticket):** the battle NaviStats.Transformation byte sits at
`eBattleNaviStats0 + 0x2c` = **0x0203ce2c** for the player (ewram.s:3109,
include/structs/NaviStats.inc:36, read per frame by
possiblyGetBattleEmotion_8015B64 via GetBattleNaviStatsAddr asm00_2.s:10159).
On the emotion_syn recipe NOTHING writes it (100-frame --watch-write: zero
writes), so a load poke `0x0203ce2c:0x0001` survives: the resolved slot
halfword 0x02035290 reads 0x0005 on every frame 38..99 with the countdown
flat 0x00 -- canon draws the slot-5 cross face on all 40 compared frames.
Two measured cautions: (1) do NOT carry the siblings' Unk_32 poke on top --
enum 1 -> byte_801E6F4[1]=2 -> the full-synchro +5 (sub_801E6A8
asm00_2.s:30975-31001) lands slot 0x000a, measured; (2) the cross state
repaints MegaMan himself -- 587 px/frame of non-face delta (x≈50..79,
y≈70..119, flat) that the descriptor route cannot reproduce (it fixes
MegaMan in his calm form), so a cross-state emotion row cannot reach 0 until
the battle-side cross model exists. T123's src/emotion.rs 5/6-arm deletion
was verified to make the face match canon pixel-exactly (the 694 px/frame
face delta vanishes) but is NOT landed: it breaks the frozen emotion_skip
pairing row (0/0/40 -> FAILED 27760/694, same descriptor byte, contradictory
outputs). Full numbers: docs/worklog/T123.md.

**Slot coverage**: `off_801CD08` @ 0x0801CD08 (asm00_2.s:27580-27603), 23
pointer words read from ROM, deltas from dword_872D814:
`[0x0000, 0x0180, 0x0300, 0x0480, 0x0600, 0x0780, 0x0880, 0x0980, 0x0a80,
0x0b80, 0x0c80, 0x0d80, 0x0e80, 0x0f80, 0x1080, 0x0780, 0x0880, 0x0980,
0x0a80, 0x0b80, 0x1700, 0x1700, 0x1800]` — byte-identical to the landed
`src/emotion.rs` FACE_INDEX. Slots 15..19 alias 5..9 and 21 aliases 20 in the
table itself; slots 5/6 DO have distinct art (0x780/0x880) and ARE drawn --
a transformation-resolved slot 5/6 uploads through loc_801CBBE
(asm00_2.s:27404) and reaches the screen except during the ~2-frames-per-
cycle blink phases 5/6 (see the skip-range note above). The landed `assets/emotion.bin` covers all 23
slots (bank 0x1900) and all 23 palettes (0x2e0); per-face palette check from
dword_872F114 + slot*32: slot 4's palette differs from slot 2's, as does
every other slot's.

## The chain (cites)

- Draw gate: `drawEmotionWindow_801CDEC` (asm00_2.s:27646-27676) reads
  eStruct2035280+0xf = 0x0203528F and emits NO OBJ for countdown values 5/6.
  +0xf is the blink countdown (sub_801CC94, asm00_2.s:27550-27574), not the
  face source (that is +0x10/+0x11, asm00_2.s:27341-27342, read back at
  :27403). Both things people have measured here are true at different
  countdown phases: on pass 4's route the poke lands mid-cycle and only
  shifts WHICH ~2 frames per blink cycle are blank ("changes no pixels"),
  while pinned at 5/6 the window blanks ~2 frames per cycle continuously
  (T122 step 2: 694 px/frame face-only).
- Upload: sub_801CB38 (asm00_2.s:27404-27406, `loc_801CBBE`) uploads the
  face every updater frame from off_801CD08; its `cmp #5` at :27390
  (`bge loc_801CBBE`) skips only the blink bookkeeping, not the upload.
- Face source: `sub_801CB38` (asm00_2.s:27332-27464) re-uploads the face
  every updater frame, resolved slot stored to +0x10/+0x11 (:27341-27342),
  slot from `possiblyGetBattleEmotion_8015B64`
  (asm00_2.s:15122-15174): Unk_36!=0 or Mood==0 -> enum 5; Anger!=0 -> enum
  3; Unk_32!=0 -> enum 1; Mood==0xff -> enum 2; else 0.
  `byte_801E6F4` (asm00_2.s:31044) = [0,2,3,1,5,4] maps enum to slot.
- Bank: off_801CD08 (asm00_2.s:27580-27603), 23 entries, per-face palettes
  at dword_872F114 + slot*0x20 (asm00_2.s:27449-27452). Exported verbatim by
  tools/emotion_export.py into assets/emotion.bin (v2, 7160 bytes).

## Why Unk_32 (slot 2) and not Anger (slot 1)

Measured this session (probe.py diff, 90 frames, sterile PAUSED route):

- Anger poke (0x020340B4): face box x0..48/y18..34 differs 694 px/frame AND
  the field panels tint (766 px/frame decaying to 635, y92..150), AND the
  angry face is CONSUMED by the resumed chip's resolution at canon 43
  (reverts to calm mid-window). Not face-only; unusable for a zero row on
  this route.
- Unk_32 poke (0x020340B2): face box 694 px/frame (holds from k=12 through
  the end of the window), 0 pixels everywhere else. Face-only.
- Unk_36 poke (0x020340B6, enum 5 -> slot 4): also face-only, same profile
  -- a spare state if slot 2 is ever needed elsewhere.
- All three faces differ from calm and from each other by the same 694 px:
  the per-emotion faces differ in colour on one silhouette, not in shape.

## Known artefacts outside the row

- Blink: canon's face blinks at canon 2..11 on this route (face box reads 0
  there -- the blink overlay is shared by every face); before canon_ref 43,
  never in the compared window.
- Trace (`emotion_syn_full`): enemy_state_action/enemy_panel_x/enemy_panel_y
  diverge at k=0 (canon's leftover deleted-enemy RAM vs the fixture's
  enemies:0 arena -- the arena must be zero-enemy for the +63 emotion/
  enemy_action disambiguation), and mm_state_action canon=21 vs rust=8
  (canon's chip-cast action code vs our equivalent; pixels identical). All
  other fields (sequencer, mm_anim, mm_panel, mm_timer, enemy_anim,
  rng_cadence) match 40/40.
- `cursor` residue 29/28/170 (veto 1/1/170/186300): pre-existing from pass
  4's port, unchanged by this pass (identical before and after).
- Coverage arithmetic (corrected after the verifier pass): M7 emotion went
  **1/25 → 2/25** with T122 (`emotion_syn` + `emotion_face_b`); T225 won the
  withdrawn `emotion_skip` back by mechanism (the modeled 0x0203528F countdown
  gates the draw; the negative zeroes the ported write and fails at 27760),
  taking M7 emotion to **3/25**.

## Known coupling (pass 6, 2026-09-17): the cursor row reads the binary footprint

The cursor row's compared window contains mid-frame VRAM copy-drain frames
(F3's seam at k=97; the 4->3 cursor-slot transition at k=37) whose pixel
phases follow the ROM's physical layout. Main's binary lands them at (0, 1)
px; every T105 variant re-rolls them: full branch (28, 1), field-only
(19, 19), field removed + gate via enemy_action (56 @ k=7, 6). Measured
per-frame in docs/worklog/T105.md (pass 6). The emotion feature is
pixel-correct (emotion_syn 0/0/40, negative 644); the blocker is the cursor
row's layout calibration, owned by the follow-up recalibration ticket
proposed in the worklog.
