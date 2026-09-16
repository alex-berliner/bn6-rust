# Note audits

Each row: a `// bn` note in reference/bn6f re-read against its code by a cheap model with the day's last credits (tools/note_audit.py). NO means the note may be wrong: the judge and the humans read this file.

| date | site | verdict | why | nominal $ |
|---|---|---|---|---|
| 2026-09-15 | asm/asm00_0.s:830 | UNSURE | the snippet is a synchronous, mode-gated queue drain (`ProcessGFXTransferQueue` + DMA wait in `memory_80009FC`) but contains neither `applyGFXAnimStepTiles_8001C94` nor `show_step`/`replace_tile`, so the mid-frame timing, 36-tile loop and 1 px residue claims cannot be confirmed from this code. | 0.0068 |
| 2026-09-16 | asm/asm00_0.s:3769 | UNSURE | The snippet shows the per-element jumptable dispatch and an EWRAM write in the loop, but the handler bodies, buffer identity, and frame timing needed to confirm the y=5/k=97 residue attribution and the pre-scanline pre-transform claim are not present in this code. | 0.0080 |
| 2026-09-16 | asm/asm00_1.s:8541 | YES | The code loads `oBattleSettings_EnemySetupArrPtr` from the BattleSettings struct and iterates that array in place (byte-masking/dispatching spawn via `SpawnBattleObjectUsingBattleEntityConfig_8007368`) without any copy to RAM, consistent with the note's ROM-pointer claim. | 0.0011 |
| 2026-09-16 | asm/asm00_1.s:8650 | UNSURE | the note's mechanism depends on spawnEnemy_80073E2's body (its `push {r5,lr}` entry and the trailing `sub_800768C`/`object_spawnType1` call), but the supplied assembly stops at that label, so those claims cannot be checked—only the dispatch-table claim (entry 0x04, type nibble 0x04) is visible, and  | 0.0163 |
