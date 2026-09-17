# T75 — NEGATIVE LANDING (per ticket escape hatch)

**Step 1 baseline (no edit):**
- `python3 tools/inventory.py`: `chips (M4): FOUND: data/ChipDataArr.s:2 ChipDataArr_8021DA8 (411 x chip_data_struct, stride 0x2c, include/rom_structs/ChipData.inc) -- verified 43/411`
- ROM: `python3 tools/gbafix.py … /tmp/t75.gba` → sha256 `5b46337aa27da9ca881f2321fe1e210f54717285b4dfa5256c1680bac4b985ef`, size `584296` bytes (identical to T57/T61/T63/T68/T74).

**Step 2 — candidate enumeration (ChipDataArr.s ∩ TextScriptChipNames0.s ∩ assets/chips.bin):**

| family | ids in table | ids in asset | ids with name | unprobed with name AND in asset |
|---|---|---|---|---|
| 0x13 SWORD_FAMILY | 17 | 11 | 11 | **1 (StepSwrd 81)** |
| 0x15 BARRIER_FAMILY | 84 | 5 | 38 of the 79 unprobed | **0** (none of the 38 named ids are in chips.bin; src-arm dispatches on sub=0x04 only) |
| 0x21 AIRSHOT_FAMILY | 1 | 1 | 1 | 0 (AirShot already rowed) |

**Reject reasons per id (the "missing shape" gate):**
- Family 0x13: 6 ids (286/339/370/374/376/410) — no name string (TextScriptChipNames0.s only carries ids 0..237) AND not in chips.bin. StepSwrd (81) IS in asset AND has name.
- Family 0x15: 38 named ids (104-106 AirRaid1-3, 110-115 BurnSqr/Sensor, 129-153 Wind/Fan/Snake/SumnBlk/NumbrBl/Meteors/Magnum/CircGun/RockCube/TimeBom1/Mine/Fanfare/Discord/Timpani/Silence/Guardian/Anubis/Otenko, 162-173 PanlGrab/GrabBnsh/GrabRvng/PnlRetrn/Geddon/HolyPanl/Snctuary/ComingRd/GoingRd/SloGauge/FstGauge, 176 BugFix, 181-182 BblWrap/LifeAur [sub=0x04, would select, BUT not in chips.bin], 186-201 various) — NONE in chips.bin. src-arm dispatches only on subfamily 0x04, so even if any were in the asset the only ids that would fire are 181/182, and those are absent from the 48-record asset.
- Family 0x21: AirShot (4) already rowed.

**Verdict**: ONE id is viable — StepSwrd (id 81, family 0x13, sub 0x01, in chips.bin record 32). Step 3-5 deferred to a follow-up ticket (worklog T75.md "What is unverified" section enumerates the next worker's procedure).

**Step 5 — inventory.py**: not run; K = 0, chips line stays `43 / 411`.

**Step 6 — guard set**: not run; no row added, no src/ edit, ROM hash unchanged by definition.

**Files touched**: `docs/worklog/T75.md` (new, 215 lines).

**Commit**: `1f2b7bb` on `wt/t75-unprobed`.

**One line of mechanism**: Of the 84 unprobed ids in the three record-driven families, only StepSwrd (id 81) has a name AND is in the 48-record asset AND dispatches on a subfamily src/battle.rs selects on; the other 83 are gated by one of: no name string (TextScriptChipNames0.s has 238 entries), not in assets/chips.bin (asset carries 48 of 411), or subfamily ≠ 0x04 (the src barrier arm's subfamily gate, T48).

**One line of what is unverified**: Step 3-5 for chip-stepswrd (add the scoreboard row, run the activity gate and oracle trace, keep only if 0/0/N with non-blind negative ≥64 px canon activity vs an empty-hand afterdissolve_0x0c capture, then regenerate docs/SCOPE.md and re-run the guard set).
