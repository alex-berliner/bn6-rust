# emotion window -- the navi's face in the battle HUD

Row: `emotion_syn` (isolated, frames 40, ALIGN_CHIP).

## What the row proves

Canon's face-selection gate is reproduced for face slot 2: canon with the
player's `AIData.Unk_32` poked to 1 (0x020340B2 = base 0x02034080) draws the
slot-2 face from `off_801CD08[2]` (dword_872DB14) with slot 2's own palette
every frame, and our port -- `src/emotion.rs`, descriptor `emotion` at +63,
`FACE_INDEX[2] = 0x300` -- renders the same 40 frames byte-exactly
(PASS 0/0/40, frame-shift negative not blind, 644).

## The chain (cites)

- Draw gate: `drawEmotionWindow_801CDEC` (asm00_2.s:27646-27676) reads
  eStruct2035280+0xf = 0x0203528F only to SKIP values 5/6; it is not the
  face source (poking it changes no pixels -- pass 4).
- Face source: `sub_801CB38` (asm00_2.s:27332-27464) re-uploads the face
  every updater frame, slot from `possiblyGetBattleEmotion_8015B64`
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
