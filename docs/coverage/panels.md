# Panel type writers — per-type site walk (T115, 2026-09-18)

Measurement ticket: zero `src/` edits, canon observed read-only, ROM sha256 unchanged.
Method = T18's field walk applied to `oPanelData_Type` + T65/T70's data streams.

## The dispatch machinery (what T33's 4-site sweep missed)

- `object_setPanelType` (asm/object.s:2601-2611) is a **trampoline**
  (`ldr r4, =_object_setPanelType+1; bx r4`) to `_object_setPanelType`
  (asm/asm38.s:4309-4315). One routine, **29 `bl` sites**: asm38.s ×4 (T33's sweep),
  asm31.s ×21, asm32.s ×2, asm00_2.s ×2. (An earlier T115 draft counted 36: the grep
  had also matched 7 `bl object_setPanelTypeBlink` sites — asm31.s:88706/88759/88827/
  88892/88909/90014/90042 — which stage `oPanelData_Unk_08` via
  `object_setPanelTypeBlink` (object.s:2651-2663) and never write `Type`.)
- The setter **refuses type-0 targets**: `ldrb r3,[r0,#oPanelData_Type]; tst; beq skip`
  (asm38.s:4316-4317). Types 9..0xC additionally get `Unk_12=0x708` (asm38.s:4318-4326).
- Companion `object_setPanelTypeBlink` (object.s:2651-2663) stages the intended type
  into `oPanelData_Unk_08` (+`Unk_0d=1`), used by the blink-then-set gimmick families.
- Direct stores to `oPanelData_Type` exist **only** at 13 sites: asm38.s:4318 (setter)
  + object.s:2220/2235/2272/2287/2323/2357/2371/2405/2419/2455/2469/2505/2519 (all 1/3)
  + object_panel_setPoison literal-offset store (object.s:2540-2563, type 4).
  The flag-mask (`0x3f0f`) write forms exist only inside the crackPanel family
  (object.s:2215-2484). No hidden inline writer anywhere in `reference/bn6f/asm`.

## Per-type writer table

| type | verdict | sites (file:line) → dispatch condition → value source |
|---|---|---|
| 0x0 hole | **zero-writer** (init-only) | setter protect asm38.s:4316-4317 makes 0 unwritable by any helper; 29 bl sites + 13 strb sites + 4 data tables + 1240 records + 1076 arrays produce no 0. Default-zero from battle-init memset. |
| 0x1 broken | verified (T33) | object.s:2323 breakPanel; crackPanel 2nd arm object.s:2235; regen object.s:1503-1504 |
| 0x2 normal | verified (T33) | object.s:1471-1472 regen; asm00_2.s:8306 (sub_8012792 #2); asm31.s:38397-38398; fire melt asm38.s:3575-3582 |
| 0x3 cracked | verified (T33) | object.s:2218-2222 crackPanel 1st arm; also t4_0x16 enemy-half arm asm31.s:88780-88781 (`mov r2,#3`); navi event 0xf5 asm00_2.s:10805-10810 |
| 0x4 poison | verified (T33) | asm31.s:6146-6147 (sub_80BAE16); navi events 0xfe/0xfa/0xf9 asm00_2.s:10776-10800 (byte12=4) replayed by sub_8013CC4 |
| 0x5 holy | **zero-writer** | no constant arg (29 sites), no strb site, no table byte (byte_80E6D0C {2,3,6,7,8}; byte_80CE41E {4,7,6}; dword_80DE79C {FF,3,7,6}; navi events {3,4}), no record/array byte. Reader rule lives: object.s:4831-4833 + asm00_2.s:22788-22791. |
| 0x6 grass | verified (T33) | asm31.s:6168-6169 (sub_80BAE16); :30843-30844 cornfiesta; byte_80CE41E[2]=6 via sub_80CE424; dword_80DE79C[3]=6 |
| 0x7 ice candidate | verified (T33) | asm31.s:6104-6105 (sub_80BAE16); byte_80CE41E[1]=7; dword_80DE79C[2]=7 |
| **0x8** | **WRITER FOUND (T115)** | asm31.s:99515-99529 `sub_80E6CAA` (in t4_0x56_80E6BDC): base = `byte_80E6D0C + Param1*0xc + alliance*0x78`; per panel `ldr word / lsr (row-1)*4 / and #0xf` → type = **packed 4-bit nibble**; table `byte_80E6D0C` asm31.s:99543-99566 = 240 bytes (2 alliances × 10 Param1 entries × 12), nibble set {2,3,6,7,8} — 8 in Param1 2/3/4 own-side rows and 0x82/0x28 bytes in both halves. Update-handler vtable asm00_1.s:2491. Spawner sub_80E6C8C asm31.s:99473-99489 is **unreferenced in the whole ROM** (no `bl`, no pointer word 0x080E6C8C/D — byte search) → no live capture. |
| 0x9 | **zero-writer** | setter special-cases 9..0xC (asm38.s:4318-4326) and sub_3007708 melts them (asm38.s:3993), but no constant/strb/table/record byte equals 9 anywhere walked. |
| 0xA | **zero-writer** | same walk as 0x9; no producer. |
| 0xB | verified (T33) | asm31.s:27871-27872 (t3_0x0_80C4E58, alliance≠0 arm) |
| 0xC | verified (T33) | asm31.s:27855-27856 (t3_0x0_80C4E58, alliance==0 arm) |

### Variable-type sites fully walked (step 1 additions over T33)

- t3_0x0_80C4E58 default arm asm31.s:27879-27896: type = `RelatedObject1Ptr->CurState`,
  skip 0xFF; disassembly comment records the real-ROM measurement (buster/charge shot:
  panel type stays NORMAL 140 frames). Gates: Param1 0x22→0xC / 0x24→0xB arms above.
- t3_0xc9_80DE404 → sub_80DE768 asm31.s:81479-81488: `type = dword_80DE79C[Param1]`,
  0xFF = skip. Table bytes: FF,03,07,06.
- t3_0x4f_80CE24C → sub_80CE3C4 asm31.s:47194-47218 → sub_80CE424 (area setter over a
  `PanelOffsetListsPointerTable` 0x7F-terminated pair list): `type = byte_80CE41E[Param1]`.
- t4_0x16_80E1E4C asm31.s:88662-88960: 4 arms dispatched by `off_80E1E60[Param2]`;
  blink phase stages Param1 into Unk_08 over the field, final phase sets Param1 (whole
  field), enemy half only → constant 3, two more Param1 arms (sub_80E1F32/80E1FB6).
- t4_0x1f_80E28A8 asm31.s:89990-90045: list of `(alliance<<4|panel)` bytes in
  ExtraVars, type = `ExtraVars[0]`.
- applyShockwavePanelEffect_80C6CFC asm31.s:31640-31653: 0xFF skip / 3 crack /
  1 break / else setPanelType(r2).
- sub_8013CC4 asm00_2.s:11109-11160: NaviStats byte 0x12 → panel type (skip if
  current 0/1; 1→break, 3→crack, else direct), gated by byte 0x13 chance. Byte 0x12
  writers: asm00_2.s:10776-10810 (events 0xfe/0xfa/0xf9 → 4; 0xf5 → 3) — only {3,4}.
- Remaining constant sites: asm31.s:30844/39065/65798 (#6), :60577 (#4), :65592 (#7),
  :88781 (#3), asm00_2.s:8306 (#2), asm32.s:3241 (#2, sub_810F3F8).

## Data-stream walk (step 2)

- **1240 BattleSettings records** (16 bytes, include/rom_structs/BattleSettings.inc):
  family A scripted (0x080aee70: 269 + 0x080b0d88: 192 = 461), family B encounter tree
  (off_8020170 → 44 groups → 82 lists / 779 records). Byte census (T115 family-A scan
  corrected by the verifier's family-B re-census): byte[0] Battlefield — family A
  251×0 + scattered ids up to 236, family B also carries many ids (verifier census:
  e.g. 189×23, 21×14); byte[4] Background — family A {7:192, 8:1, 255:268}, family B
  all 255 — **known-answer check passes** (reproduces T65's backdrop census: Comps
  art 0x07/0x08, 0xff = map default); byte[6] SidesModifier — family A {0:7, 56:454},
  family B {56:779}. No record field flows to any panel writer (byte[4] = background,
  byte[6] = sides modifier, byte[0] Battlefield has no panel-type reader).
- **1076 formation arrays**: quad[0]&0xFC dispatch ∈ {0,0x10,0x20,0x30,0x80,0x90,0xA0}
  → only the 11 spawners of `SpawnBattleObjectUsingBattleEntityConfig_8007368`
  (asm00_1.s:8588-8621: MegaMan/enemy/mystery data/rocks/cubes/guardian). asm00_1.s
  contains **zero** panel-type store sites → arrays structurally cannot write panels.
  quad[2] enemy ids all ≤ 0xE3, quad[3] ∈ {0,1}.
- **T70 stage pairs `byte_203CA50`**: both ROM references (asm03_0.s:14639 pool used by
  `battleSettings_802D2B2`; asm00_1.s:18213 pool) feed the stage→**background** pairing
  only. Ruled out for panels.
- The actual panel-type ROM data is the four tables above; every value they contain is
  in {FF,2,3,4,6,7,8} — the 8 verified types are predicted (2,3,4,6,7 from data;
  1,B,C from code arms; 0 from init), and 5/9/A appear in none.

## Step 3 — live captures

**0 captures taken (budget ≤3).** The one newly proven writer feeds a GAP row (0x8),
but its spawner `sub_80E6C8C` is unreferenced anywhere in the ROM, so no scenario in
the harness reaches it; the other four types have no firing writer to watch by the
finding itself. Canon-side observation only; no row semantics changed.

## Unverified / next

- The *effects* of panel types (movement block, regen timings, holy damage halving)
  still need scenarios + src — next ticket, not this one.
- What spawns t4_0x56 / t4_0x16 / t4_0x1f in a real battle (the wrappers are
  unreferenced; likely a computed dispatch or data-driven spawn path outside the
  labeled disassembly).

## T121b (2026-09-18) — the 13 words verified from ROM bytes; the poison writer measured live

- **Export**: `tools/panel_flags_export.py` → `assets/panels.bin` (52 raw bytes, one LE u32 per
  type 0x0..0xC) from the ROM file at offset 0x1D7E24 (`reference/bn6f/bn6f.gba`;
  `/tmp/bn6f_real.gba` cmp-identical). The words match `PANEL_TYPE_FLAG_WORDS` above
  (independent read, no row changed).
- **Bit names**: none of the table's bits is named by `PanelData.inc` (it names only 0x2,
  0x20 and the 0x00800000.. group — none in the table). Each of 0x40 cracked / 0x100 poison /
  0x2000 holy / 0x400 grass / 0x800 ice / 0x1000 type-8 / 0x4000 broken / 0x8000 hole is set by
  exactly one type's word and is named after it; 0x10 (every type but hole/broken) and 0x10000
  (all 13) stay unnamed; 0x200 marks exactly the 9..0xC group the setter gives
  `Unk_12=0x708` (asm38.s:4318-4326).
- **Table corroboration, NOT a live rule**: `object_crackPanel`'s flags rewrite
  `Flags = (Flags & ~0x3f0f) + 3` (asm/object.s:2215-2218) clears exactly the table's per-type
  low bits (0-3, 8-13); normal's word 0x10010 has no bit inside that mask, so crack = OR 0x40 →
  0x10050 = the type-3 word exactly.
- **Live measurement** (canon, chip-poisseed route, `--watch 0x02039C00:0x320`, 260 frames;
  raw capture preserved at `/tmp/t121b_wide.txt` and re-parsed by T130 2026-09-18 — the file
  DOES carry values, see docs/worklog/T130.md step 0): canon frame 52 the seed object appears
  over its target panel (that panel's flags gain the 0x80000000 ally-attack bit); frame 53
  `object_panel_setPoison` (object.s:2540-2563) runs on **NINE panels — cols 4-6 × rows 1-3,
  the enemy half 3x3** (T121b's original "six, rows 1-2" missed the back row; re-parsed from
  the preserved capture): flags 0x00010032 → 0x00010134, which is setPoison's own
  masked template `(Flags & ~0x3f5f) | 0x114` measured byte-for-byte, with `Type` 02→04 and
  `Animation` 02→04 (its two `strb #4` stores, :2552-2554). The area is the seed
  gimmick's writer table `byte_80E2588` (asm31.s:89651-89667: 3 entries × 0x18, crack /
  break / poison writers at entry+0x14, **Param1 picks the entry** (`Param1*0x18`,
  sub_80E25F0 asm31.s:89683-89711) while **CurState picks the routine** (off_80E25E4,
  t4_0x1e_80E25D0 asm31.s:89665-89681)); the per-entry `0x10` bytes are check words fed to
  `object_checkPanelParameters` (object.s:2688-2713) by the collector sub_80E269A
  (asm31.s:89775-89810) — an unrelated 0x10 to setPoison's own immediate `#0x10` guard
  against the panel's Flags (:2544-2546).
- **Writer map for M3's first rule**: the live poison route does NOT go through the setter path
  (`_object_setPanelType` → `_object_updatePanelParameters`, the table-OR path): setPoison
  writes its own template 0x114 = the table's 0x110 + an unnamed 0x4 bit it sets itself, and the
  mask clears 0x2 (blocks movement) while OR-ing 0x100. The table's type-4 word and the live
  writer's template differ only in that 0x4. **Guard polarity (corrected by T130):**
  `tst r1,#0x10; beq` branches to the return-0 tail when the bit is CLEAR (object.s:2544-2546),
  so a panel is poisoned only when `Flags & 0x10` IS SET — normal panels carry it
  (0x00010032/0x00010012), the hole (0x18000) and broken (0x14000) words do not: poison cannot
  land on a hole or broken panel. Same guard shape across the crack/break family
  (object.s:2215-2563). Aside: `Unk_12` measured 0x0708 on fresh NORMAL
  panels (frame-0 dump) — the 9..0xC setter arm is not that value's only writer; tickPanels'
  regen writes it too (asm/object.s:1430-1434).
- **Bounded NEGATIVE (row not built)**: a `panel_poison` fixture row needs a type change driven
  at a chosen frame. The fixture descriptor has no panel-type field (+62/+63 are contested
  overlays), `src/fixture.rs`/`src/battle.rs` are outside the ticket's files, and the only
  in-scope reception path would be a bespoke poke-box/watch static pair in `src/field.rs` — a
  new test-only input channel with no precedent — plus a new negative kind (a one-sided no-poke
  comparison; `negative_counts` only shifts frames/pixels). Rejected by the coordinator
  2026-09-18: the row would fixture code the ticket excludes. Note a live type change IS
  reachable (above), so no live-change GAP is claimed — the gap is the fixture/harness plumbing.
