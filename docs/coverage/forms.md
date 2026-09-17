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
