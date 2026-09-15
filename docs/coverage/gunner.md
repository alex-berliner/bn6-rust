# Coverage: `gunner`

T9j (2026-09-15). The Gunner scenario port -- the next M5 enemy after the
Mettaur, fired against canon's `ForGunner_8113078` per-type routine
(reference/bn6f/asm/asm32.s:10123).

## Per-type routine dispatch

The interpreter reads `byte_80182C4[3*enemy_idx]` via
`GetVerActorTyAndAIIdx_80182B4` (reference/bn6f/asm/asm00_2.s:19965-19974)
and routes the (Version, ActorType, AIIndex) triple to the right handler
table. For the Gunner (enemy_idx 0x85, the NameID the poked
battlestart_gunner.state slot 1 populates with) the row is
`(0, ACTOR_TYPE_VIRUS, 0x17)` -- AIIndex 0x17 selects the
CurAction-indexed handler table `ForGunner_8113078` at asm32.s:10123.

The dispatch cite lives in src/objects.rs (Style::Gunner arm) and the
port in src/gunner.rs (`gunner::gunner_update`, the T9j extension; the
T9h cite + struct + handler table sit alongside it).

## ForGunner_8113078 handler table (asm32.s:10123-10142)

| CurAction | routine                                       | arm           |
|-----------|-----------------------------------------------|---------------|
| 0x00      | RunSpawnAnimationMaybe_8016380+1              | spawn anim    |
| 0x04      | sub_80165B8+1                                 | spawn arming  |
| 0x08      | sub_80165C2+1                                 | idle          |
| 0x0C      | sub_81166AE+1                                 | hit reaction  |
| 0x10-0x1C | sub_81130E4/0F0/0FC/108+1                     | materialize   |
| 0x20      | sub_8113124+1                                 | AI tick       |
| 0x24      | genericAI_exitAttackStateAfterDelay_81097BA+1| wait/recover  |
| 0x28 (0x0A)| sub_8112F4E+1                                | ATTACK        |
| 0x2C      | sub_8112D9C+1                                 | guard/cleanup |

## Per-state timer arms (cite asm/object.s for the per-state read)

| state | timer arm                       | source                          |
|-------|---------------------------------|---------------------------------|
| 0x0A  | SHOTS = 3 (asm32.s:9958-10102)  | sub_8112F4E / sub_8113002 / ai_8113038 |
| 0x0A  | SHOT_GAP = 10                   | sub_8113002 (asm32.s:10066-10070)|
| 0x0A  | RECOVER_FRAMES = 24             | ai_8113038 (asm32.s:10087-10117) |
| 0x04  | spawn wait (sprite_getFrameParameters bit 0x80) | sub_8112F70 |

The CurAction 0x0A arm (the ATTACK the gunner actually fires) is itself
a 4-arm state machine dispatched through `off_8112F60[oAIAttackVars_Unk_00]`
(asm32.s:9958-9973): 0=sub_8112F70 (aim cursor), 4=sub_8112FBA (cursor
locked, fire setup), 8=sub_8113002 (firing 3 shots 10 frames apart), and
12=ai_8113038 (recover 24 frames).

The Gunner controller in src/gunner.rs (`Gunner::update`) is the
CurAction 0x0A arm driver -- the cursor + impact machine that fires
three panel-anchored shots 10 frames apart, then recovers for 24
frames. `gunner::gunner_update` is the per-type routine port of
`sub_8112F4E`'s 4-arm dispatch via `oAIAttackVars_Unk_00`, mirroring
`MettaurEntry::think`'s shape (state advance + per-tick work + return
Update); the function is the port of canon's per-type routine, not a
hand-written re-creation.

## Scenario (T9h harness row)

- **canon side**: `rom=bn6f_real.gba loadstate=battlestart_gunner.state`
  (T9c's state: BattleSettings record 6 = 0x080b4bd8, Mettaur at slot 0
  panel (5,2) NameID 0x0001 HP 0x28, Gunner at slot 1 panel (6,3) NameID
  0x0085 HP 0x3c).
- **rust side**: `GUNNER_ROW` (tools/harness.py, T9h descriptor -- the
  Mettaur+Gunner pair packed as enemy_kind=0x05 = 0b0000_0101: slot 0
  kind 0 Mettaur, slot 1 kind 1 Gunner; the bit-pair split src/fixture.rs
  reads via `kind_of()`).
- **frames**: 130. The row pairs the rust side's marker origin (8 for
  GUNNER_ROW) against the canon side's first attack-event frame
  (canon_ref=80, swept from 0..130 in T9j: canon's state-loading white
  runs capture frames 0..70 and the first attack-event frame on the
  canon side -- where the gunner's CurAction transitions to 0x0A via
  `sub_8113162`'s row-check -- sits at 80; search band 0..40 picks the
  rust side's matching frame within rust_origin + offset = 8 + 26..40).
  One full materialize + cursor walk + 3 shots + recover cycle, with
  margin.
- **ui**: both (integrated), the M5 baseline shape.

## Per-type routine port (T9j)

The `gunner::gunner_update` function in src/gunner.rs ports canon's
`ForGunner_8113078` (asm32.s:10123-10142) CurAction 0x0A arm
(`sub_8112F4E`, asm32.s:9958-10102). The function mirrors
`MettaurEntry::think`'s shape -- `(me, target, blocked, rng) -> Update`
(state advance + per-tick work + return Update) -- and is wired into
the dispatch arm `objects::enemy_think` `Style::Gunner` (the same call
site `Style::Mettaur` uses for `MettaurEntry::think`). The actual
cursor / impacts / pose work lives on `Battle::gunner_ctl` and
`Battle::impacts` (battle.rs's existing path) -- moving those would
widen the change past the files this ticket allows.

## What is unverified

The harness row reads 2850534/38237/130 at canon_ref=80 + search
0..40, NOT 0/0/130. The diff is dominated by content the rust side is
not yet matching (cursor travel timing and the per-state pose changes
battle.rs owns); the per-type routine port lays the citation groundwork
but does not change visible behavior. A subsequent ticket will move
cursor + impacts into GunnerEntry (and refactor battle.rs's special
path into `gunner_update`) so the visible state aligns.
