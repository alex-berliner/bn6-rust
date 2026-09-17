# emotion window -- the navi's face in the battle HUD

Rows: `emotion_syn` (isolated, frames 40, ALIGN_CHIP), plus T122's
`emotion_face_b` (slot 4 through AIData.Unk_36) and `emotion_skip` (the draw
gate's own byte poked to 5 -- face gone on BOTH sides).

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
- `emotion_skip` (T122): the skip arm -- NO enum can land a skip slot (see the
  table below: enum 4 -> slot 5 is unreachable from
  `possiblyGetBattleEmotion_8015B64`'s arms 5/3/1/2/0), so canon is poked
  straight on the gate's own byte, eStruct2035280+0xf = 0x0203528F = 5
  (aligned halfword poke 0x0203528E:0x0500; nothing writes that byte on this
  route -- its only writers are the blink updater sub_801CC94,
  asm00_2.s:27551-27566, and T105's pass-4 watch read 0x00 for 80 frames),
  and `drawEmotionWindow_801CDEC` emits NO OBJ for 5/6 (asm00_2.s:27647-27652;
  T108 measured byte=5 -> face gone). Ours (descriptor `emotion=5`) builds no
  sprites for slots 5/6. Row reads 0/0/40, negative not blind (644): BOTH
  worlds show an empty face box over all 40 frames.

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
  AIData poke can land a slot in the skip range through this table.

**`byte_801E700` @ 0x0801E700** (asm00_2.s:31049) — the TRANSFORMATION → base
face slot table, **25 entries + 3 pad**, indexed by the second return
(oNaviStats_Transformation) of possiblyGetBattleEmotion, consumed by
sub_801E6A8/sub_801E660 (asm00_2.s:30962-31001). This is the 23+-entry table
the ticket was after:

| transformation | 0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 | 11 | 12 | 13 | 14 | 15 | 16 | 17 | 18 | 19 | 20 | 21 | 22 | 23 | 24 | (25..27 pad) |
| base slot | 0 | 5 | 6 | 7 | 8 | 9 | 5 | 6 | 7 | 8 | 9 | 20 | 20 | 15 | 16 | 17 | 18 | 19 | 15 | 16 | 17 | 18 | 19 | 22 | 22 | 0, 0, 0 |

Post-adjustments (asm00_2.s:30975-31001): transformation 1..10 → +5 when
`byte_801E6F4[enum] == 2` (full synchro: cross faces 5..9 become 10..14);
transformation 11/12 → +1 when `byte_801E6F4[enum] == 3` (angry beast out:
slot 20 becomes 21).

**Skip range (5/6) entries**: `byte_801E6F4[4] = 5` (unreachable enum, above)
and `byte_801E700[1] = 5`, `[2] = 6` (reachable only via a non-zero
transformation byte, i.e. a cross/beast state, not a poke on this route). In
the compared window the skip range is reached only by poking the gate's own
byte 0x0203528F — which is what `emotion_skip` does.

**Slot coverage**: `off_801CD08` @ 0x0801CD08 (asm00_2.s:27580-27603), 23
pointer words read from ROM, deltas from dword_872D814:
`[0x0000, 0x0180, 0x0300, 0x0480, 0x0600, 0x0780, 0x0880, 0x0980, 0x0a80,
0x0b80, 0x0c80, 0x0d80, 0x0e80, 0x0f80, 0x1080, 0x0780, 0x0880, 0x0980,
0x0a80, 0x0b80, 0x1700, 0x1700, 0x1800]` — byte-identical to the landed
`src/emotion.rs` FACE_INDEX. Slots 15..19 alias 5..9 and 21 aliases 20 in the
table itself; slots 5/6 DO have distinct art (0x780/0x880) but the draw gate
never lets them on screen. The landed `assets/emotion.bin` covers all 23
slots (bank 0x1900) and all 23 palettes (0x2e0); per-face palette check from
dword_872F114 + slot*32: slot 4's palette differs from slot 2's, as does
every other slot's.

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
