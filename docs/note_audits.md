# Note audits

Each row: a `// bn` note in reference/bn6f re-read against its code by a cheap model with the day's last credits (tools/note_audit.py). NO means the note may be wrong: the judge and the humans read this file.

| date | site | verdict | why | nominal $ |
|---|---|---|---|---|
| 2026-09-15 | asm/asm00_0.s:830 | UNSURE | the snippet is a synchronous, mode-gated queue drain (`ProcessGFXTransferQueue` + DMA wait in `memory_80009FC`) but contains neither `applyGFXAnimStepTiles_8001C94` nor `show_step`/`replace_tile`, so the mid-frame timing, 36-tile loop and 1 px residue claims cannot be confirmed from this code. | 0.0068 |
