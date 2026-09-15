# Coverage: `gunner`

T9h (2026-09-15). The Gunner scenario port -- the next M5 enemy after the
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

The dispatch cite lives in src/objects.rs (Style::Gunner arm) and in
src/gunner.rs (GunnerEntry doc + struct, the T9h extension to the existing
file -- the per-type routine cite + the per-state timer arms + the
materialize/animation state slots).

## ForGunner_8113078 handler table (asm32.s:10123-10142)

| index | routine                                       | what canon runs        |
|-------|-----------------------------------------------|------------------------|
| 0x00  | RunSpawnAnimationMaybe_8016380+1              | spawn animation        |
| 0x04  | sub_80165B8+1                                 | spawn arming           |
| 0x08  | sub_80165C2+1                                 | idle (freezes if dead) |
| 0x0C  | sub_80166AE+1                                 | hit reaction           |
| 0x10  | sub_81130E4+1                                 | materialize arm 1      |
| 0x14  | sub_81130F0+1                                 | materialize arm 2      |
| 0x18  | sub_81130FC+1                                 | materialize arm 3      |
| 0x1C  | sub_8113108+1                                 | materialize arm 4      |
| 0x20  | sub_8113124+1                                 | AI tick arm            |
| 0x24  | genericAI_exitAttackStateAfterDelay_81097BA+1| wait/recover           |
| 0x28  | sub_8112F4E+1                                 | ATTACK (cursor+impact) |
| 0x2C  | sub_8112D9C+1                                 | guard/cleanup          |

## Per-state timer arms (cite asm/object.s for the per-state read)

| state | timer arm                       | source                          |
|-------|---------------------------------|---------------------------------|
| 0x0A  | SHOTS = 3 (asm32.s:9958-10102)  | sub_8112F4E / sub_8113002 / ai_8113038 |
| 0x0A  | SHOT_GAP = 10                   | sub_8113002 (asm32.s:10066-10070)|
| 0x0A  | RECOVER_FRAMES = 24             | ai_8113038 (asm32.s:10087-10117) |
| 0x04  | spawn wait (sprite_getFrameParameters bit 0x80) | sub_8112F70 |

The Gunner controller in src/gunner.rs (`Gunner::update`) IS the CurAction
0x0A arm -- the cursor + impact driver that fires three panel-anchored
shots 10 frames apart, then recovers for 24 frames. The other CurActions
share `Actor::update` / `Ai::update` the same way `MettaurEntry` does for
the Mettaur's CurActions.

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
  GUNNER_ROW, same family as FIELD_ROW) against the canon side's frame 0
  (the battlestart_gunner state sits at battle frame 0). One full
  materialize + cursor walk + 3 shots + recover cycle, with margin.
- **ui**: both (integrated), the M5 baseline shape.

## What is unverified

Whether the gunner harness row's M5 baseline is the existing M5 1/187
baseline or a freshly measured one -- the next M5 ticket decides. M5 was
1/187 (Mettaur done) at T9c PARTIAL (aa3486d, docs-only); the gunner
row's reading (this ticket) is the next M5 advancement question.