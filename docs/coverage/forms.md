# Forms coverage (M7: charge shots)

Status after T106 (one of 25): the charged buster's **Cannon cell** (shot_kind
`oAIData_BPwrAtk` = 0x06) is ported (`src/charge_shot.rs`) and exercised by the
`buster_charge` row; the other 24 cells of
`ChargeShotHandlersByTransformation_80117D4` (reference/bn6f/asm/asm00_2.s:5809,
0x94 cells) are unported — `ChargeShot::update` returns `None` for them.

| shot_kind (BPwrAtk) | cell | behaviour | status |
|---|---|---|---|
| 0x06 | `sub_8011BA2` (asm00_2.s:6173) | Cannon charge shot: damage = buster + 0x14·min(buster,5), attribute 0x94, shot object 0x23c | ported, `buster_charge` row |
| 0x00 | `megamanChargeShotBPwrAtk_init_8011A26` | shared plain init | not ported |
| 0x01 | `busterBugChargeShotDamageCalcHappensHere_8011A7E` | the NORMAL charged buster ((Atk+1)·10) | not ported (our engine hardcodes its damage) |
| 0x02..0x05, 0x07..0x0D | see asm00_2.s:5810-5823 | — | not ported |

The row: canon side = afterdissolve_0x0c state, buster button held by a
per-frame AIData cheat, shot kind poked to 0x06 one frame before the release
poke; rust side = the same dispatch through `src/charge_shot.rs`. The ticket's
"hold ≥ 24 frames arms the dispatch" did not match measurement — see
docs/worklog/T106.md: canon's counter caps at 100 (watched) and the charged
attack only follows a full charge.

## The cross-form body (T135, 2026-09-18): the body is a RECOLOUR, not a new set

M7's body-selection line. The transformation byte is the player's
`oNaviStats_Transformation` = `eBattleNaviStats0` 0x0203ce00 (ewram.s:3109)
+ 0x2c (include/structs/NaviStats.inc) = **0x0203ce2c**; T123 measured zero
mid-battle writers on the descriptor route, so a load poke holds.

**Measured A/B** (90-frame watch pair, PAUSED route, `--disable-bg`, poke
0x0203ce2c:1 vs unpoked): the OAM is **byte-identical on every frame** — same
objects, tiles, positions; MegaMan's body is OAM objects 6..9 (x41..81,
y70..118, OBJ bank 0, priority 2) — and **OBJ bank 0 swaps from palette row 0
to row 2 of the SAME battleSpriteMegaMan blob at the first frame after the
poke** (bank 12 = the face palette, slot 2 vs slot 5). Canon-vs-canon over the
align window: 1281 px/frame = 694 (face) + 587 (body recolour), T123's split
reproduced exactly.

**Canon's switch** (all asm00_2.s unless noted):
- `sub_801002C` :2724-2800 — the palette selector. For the player
  (ActorType 2, NaviIndex 0): AIData flag 0x48 & 0x200 -> 1; TF = stats+0x2c;
  **cross values (TF not 0/0xb/0xc) -> palette row `byte_80203EA[TF]`**
  (:2776-2779); TF 0 -> Mood(+0xe)==0xff ? 4 : 0, plus stats[+0x10]*5+0x12
  when TF==0; TF 0xb/0xc -> 0; other navis via `sub_800FD0A`.
- `byte_80203EA` @0x080203EA (ROM bytes, read this ticket): TF 0..0xa ->
  `0,2,7,9,d,13,5,11,b,f,15` (indices >0xa read 0x00 — never reached: only
  cross values index it).
- `sub_80100EC` :2789-2804 — applies it: TF 0x17/0x18 -> `sub_8016A38`
  (the BeastOver special path), else `sub_801002C` + `sprite_setPalette`.
- Applied at battle init: `playerObject_init_80172F0` :18109-18110 (which also
  WRITES the byte at init: stats+0x2c := stats[+0x17], :18088-18096). Applied
  on real activations by the transformation script opcode (asm31.s:107177).
- Sprite-SET selector: `sub_800FC9E` :2201-2215 + `byte_800FCBC` @0x0800FCBC
  (25 entries): MegaMan's category = table[TF] — **TF 0..0xa ALL map onto
  category 0** (battleSpriteMegaMan: the crosses share the base body art),
  0xb->0xB / 0xc->0xC (the beast bodies), 0xd..0x16 -> 1..0xA (the
  battleSprite*Cross blobs are the CROSS-BEAST bodies), 0x17/0x18 -> 0xB/0xC.
  List 0 = battleSpritePtrs (data/SpritePointersList.s:13-27).
- Per-frame staging: `stageObjPalette_8002818` (sprite.s:254-302) re-stages
  row `[sprite+4]+[sprite+5]` of the frame's own palette blob into
  iObjPaletteMirror_3001550 every frame. The battleSpriteMegaMan blob carries
  **43 palette rows** — the cross rows are RESIDENT in the base set.

**Port** (T135): `src/battle.rs cross_form_palette_row` (byte_80203EA, 11
entries) reads the transformation byte once at battle build (canon reads it at
init; our route's only writer is the load poke) and hands it to
`src/actor.rs set_form_palette_row` -> `spr::Player::set_palette_add`
(the pre-existing per-frame palette-add hook; the warp pale-expiry now
restores the form row instead of 0). `assets/megaman.bin` re-exported with
`tools/spr_export.py --palettes 21` (canon bytes; row 21 byte-verified against
the ROM blob) so palette_add reaches every row byte_80203EA names. Fitted
constants stay 17.

**Row**: `form_cross` = emotion_syn's route + `0x0203ce2c:0x0001` on both
sides + the face emptied on BOTH sides (canon: the emotion_skip halfword pin
`0x0203528e:0x0500` — the draw gate blanks 5/6, asm00_2.s:27648-27652; ours:
descriptor emotion=5, the landed 5/6 arm). The face-slot rule byte_801E700
itself is NOT under test here; no landed emotion row moved. **PASS 0/0/40**,
negative not blind (644). Pre-change the row reads FAILED 23480 worst 587 =
exactly the body region — the bounded negative: without the poke both sides
show the base form.

**Art residency (step 1, no capture)**: of the 25 TF values, TF_NONE + all
ten crosses (0x1..0xa) need **no new body bytes** — same resident sprite set,
palette rows resident in its 43-row blob, face slots resident in
assets/emotion.bin (byte_801E700: crosses -> slots 5..9, +5 full-synchro).
TF_HEATCROSS (0x1) is the form this ticket ports. The twelve
beast/cross-beast values (0xb..0x16) need their own sprite sets
(battleSprite_8233728/823B768, battleSprite*Cross blobs — not resident), the
two overs (0x17/0x18) additionally sub_8016A38's palette path and the
F_BEAST_WINGS/FEATHER overlays.

**Unverified**: what writes 0x0203ce2c in a real cross activation
(battle-side, M4/M7's PA/cross item — no scenario); the exact per-frame
instruction re-deriving the palette row from the live byte (a watch-write on
the sprite struct's palette byte at 0x0203aa44 showed ZERO writes — the row
is re-derived elsewhere, unpinned); the 24 unported forms' own scenarios.
