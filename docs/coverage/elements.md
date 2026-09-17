# elements — M3's first damage rule: the element/weakness multipliers (T126)

Everything here is read off `/tmp/bn6f_real.gba` (sha256
`a37c1028adb72082b51e142321fa437967bc54b6f46730a53f6581ad455ad670`, 8388608
bytes) and `reference/bn6f` (read-only). Every byte below was dumped with a
Python read of the ROM in this session; every routine claim carries an
assembly file+line cite.

## 1. The two IWRAM multipliers

Both are called from the damage accumulation in `sub_3007218`
(reference/bn6f/asm/asm38.s:3483-3487):

```asm
ldrb r0, [r6,#oCollisionData_PrimaryElement]   // defender (asm38.s:3484)
ldrb r1, [r7,#oCollisionData_PrimaryElement]   // attacker (asm38.s:3485... :3484/:3485 pair)
bl getPrimaryElementWeaknessMultipler_3007432  // :3486
...
ldrb r0, [r6,#oCollisionData_SecondaryElementWeakness] // defender (asm38.s:3490)
ldrb r1, [r7,#oCollisionData_SecondaryElement]         // attacker (asm38.s:3491)
bl getSecondaryElementWeaknessMultipler_30074e2        // :3492
```

The caller starts a hit counter at 1 (`mov r4,#1`, asm38.s:3483), adds each
multiplier's return (`add r4,r4,r0`, :3487 and :3493), adds `sub_30074BA`
(bubble/aura arm) and `applyElecOnBubbleMultipler_30074a2`, stores `r4-1` into
`oCollisionData_DamageMultiplier` (+0x75) and `oCollisionData_ExclamationIndicator`
(+0x74) (asm38.s:3495-3499, :3504-3506), and finally multiplies the raw damage
by the whole sum (`mul r0,r4`, asm38.s:3520). So the multiplier is
**additive per extra hit**: a single weakness makes ×2, a double weakness ×3.

## 2. Primary table — `getPrimaryElementWeaknessMultipler_3007432`

Routine: asm38.s:3533-3540. Index = `defender_element * 5 + attacker_element`
(`mov r2,#5; mul r0,r2; add r0,r0,r1`, asm38.s:3534-3536), one byte per cell,
return value 0 or 1 (added to the hit count above).

Table `byte_3007444`, ROM load address **0x081d7944** (unique 25-byte match in
the ROM; the symbol's VMA is the IWRAM copy 0x03007444, asm38.s:3543-3555,
`.byte` rows quoted verbatim there). Rows = defender element 0..4 (ELEM enum,
constants/constants.inc:72-76: NULL 0, HEAT 1, AQUA 2, ELEC 3, WOOD 4),
columns = attacker element 0..4, cell = extra hit:

| def \ atk | 0 NULL | 1 HEAT | 2 AQUA | 3 ELEC | 4 WOOD |
|-----------|--------|--------|--------|--------|--------|
| 0 NULL    | 0      | 0      | 0      | 0      | 0      |
| 1 HEAT    | 0      | 0      | 1      | 0      | 0      |
| 2 AQUA    | 0      | 0      | 0      | 1      | 0      |
| 3 ELEC    | 0      | 0      | 0      | 0      | 1      |
| 4 WOOD    | 0      | 1      | 0      | 0      | 0      |

ROM bytes, row-major from 0x081d7944:
`00 00 00 00 00 | 00 00 01 00 00 | 00 00 00 01 00 | 00 00 00 00 01 | 00 01 00 00 00`
followed by 3 bytes of `00` padding to the word boundary. The diagonal
cycle reads exactly the BN6 weakness ring: HEAT weak to AQUA, AQUA to ELEC,
ELEC to WOOD, WOOD to HEAT; NULL weak to nothing.

## 3. Secondary table — `getSecondaryElementWeaknessMultipler_30074e2`

Routine: asm38.s:3634-3692 (`r0` documented "weakness bitfield" at :3632).
No data table — a pure rule over two bitfields:

```asm
mov r2, #0
tst r0, r1            // defender_weakness & attacker_element
bne loc_30074F8       // overlap -> candidate hit
cmp r0, #0x80         // special case: weakness exactly 0x80 (sword)
bne loc_30074FE
ldr r0, [r7,#oCollisionData_SelfCollisionTypeFlags]  // attacker's flags (+0x30)
ldr r1, dword_300754C // =0x2000
tst r0, r1
beq loc_30074FE
mov r2, #1            // sword-weak defender hit by a 0x2000-flagged attacker
b loc_30074FE
loc_30074F8:
cmp r0, #0            // a zero weakness bitfield never counts
beq loc_30074FE
mov r2, #1
loc_30074FE:
mov r0, r2
```

Rule: **factor 1 iff `weakness != 0` and `(weakness & attacker) != 0`; or
iff `weakness == 0x80` and the attacker's `SelfCollisionTypeFlags`
(CollisionData +0x30, CollisionData.inc:142) has bit 0x2000 set.** Otherwise 0.

Weakness bit values (flag_enum, constants/constants.inc:79-82):
ELEM_BREAK 0x10, ELEM_WIND 0x20, ELEM_CURSOR 0x40, ELEM_SWORD 0x80. The
attacker's `SecondaryElement` is the high nibble of `BattleObject.Element`
(`sub_8019F8C`: `and r2, 0xf0` stored to +0x19, asm00_2.s:21350-21351; the
same split puts `Element & 0xf` into PrimaryElement, asm00_2.s:21347-21348 and
`object_setupCollisionData` asm00_2.s:21385-21392). The 0x80 special case is
the sword-weakness path; what 0x2000 names in `SelfCollisionTypeFlags` is not
in the .inc (no named bits for that field) — left unnamed here.

## 4. Where the defender's bytes come from

Enemy spawn (asm00_1.s:9240-9249, `sub_80075xx` enemy init):

- `enemy_getStruct2` row (`enemy_getStruct2`, asm00_2.s:684; virus sub-table
  `AIEnemyStruct2Ptrs_8109150`, asm31.s:169536-169630, 32 entries × 4, ai
  index × 4): the row's first halfword is **element<<12 | hp(12 bits)** —
  `lsl r2,r2,#0x14 / lsr r2,r2,#0x14` masks HP to 12 bits into
  `oBattleObject_HP`/`MaxHP`, then `lsr r1,#0xc` stores the top nibble into
  `oBattleObject_Element` (asm00_1.s:9240-9249). So Struct2's `elem_hp`
  halfword is **element + HP packed together**, HP in the low 12 bits —
  settled by the ROM bytes below (all Mettaur/Gunner rows have a zero element
  nibble and 12-bit HP values, and elemental viruses show nonzero nibbles with
  in-range HP).
- `enemy_getStruct1` row (`enemy_getStruct1`, asm00_2.s:646; sub-table
  `AIEnemyStruct1Ptrs_81090D0`, asm31.s:169485-169478, 32 entries; fields
  `.equiv` asm00_2.s:637-644: Element +5, SecondaryElementWeakness +6,
  HasShadow +7): Element is **OR'd** into `oBattleObject_Element`
  (asm00_2.s:17637-17641), SecondaryElementWeakness is stored to the collision
  data's +0x18 (`sub_8019F9E` asm00_2.s:21355-21358).

## 5. The ROM's own element bytes, ai 1 (Mettaur) and ai 0x17 (Gunner)

All 32 `AIEnemyStruct1Ptrs_81090D0` / `AIEnemyStruct2Ptrs_8109150` entries
walked from the ROM (pointers read at 0x081090D0 / 0x08109150, file offsets
0x01090D0 / 0x0109150). Mettaur (ai 0x01) and Gunner (ai 0x17):

| ai | struct1 | Element (+5) | SecondaryElementWeakness (+6) | struct2 row0 | element nibble | HP |
|----|---------|--------------|-------------------------------|--------------|----------------|-----|
| 0x01 Mettaur | 0x08109bd0 | 0x00 | 0x00 | 0x08109bd8 `0x0028` | 0 | 40 |
| 0x17 Gunner  | 0x08112b94 | 0x00 | 0x00 | 0x08112b9c `0x003c` | 0 | 60 |

Neither fixture enemy is weak to anything: both rows read element 0 and
weakness 0. The only nonzero weakness bytes in the whole virus table are
ai 0x19 (`w=0x40` cursor, ROM 0x08113754+6) and ai 0x1a (`w=0x20` wind, ROM
0x081143c8+6); the nonzero element nibbles (Struct2 row 0): ai 0x02 `0x2046`
(aqua, 70 HP), ai 0x05 `0x3064` (elec, 100), ai 0x08 `0x103c` (heat, 60),
ai 0x0b `0x1050` (heat, 80), ai 0x0c `0x1096` (heat, 150), ai 0x0e `0x2050`
(aqua, 80), ai 0x0f `0x203c` (aqua, 60), ai 0x10 `0x10c8` (heat, 200),
ai 0x11 `0x3064` (elec, 100), ai 0x12 `0x3078` (elec, 120), ai 0x14 `0x408c`
(wood, 140), ai 0x15 `0x4064` (wood, 100), ai 0x16 `0x4082` (wood, 130).
The ticket's cited cell — `off_8109150[4]` row 0 at 0x0810ae4c — reads
`0x005a` = element 0, HP 90: HP alone, element zero.

Consequence for M3's fixtures: **no ×≠1 pair is reachable on a green row with
the two fixture enemy kinds we have** (Mettaur, Gunner — `fixture.rs`
`kind_of`, KIND_GUNNER). Step 2/4 of T126 measure the pair with a RAM poke
instead, and the bounded negative in `docs/worklog/T126.md` records why.

## 6. What the attacker's element is

The attacker's collision data PrimaryElement is `BattleObject.Element & 0xf`,
SecondaryElement `Element & 0xf0` (asm00_2.s:21347-21351, :21385-21392). For
chips the record's `ChipElement` is `ChipData +0x6` (ChipData.inc:9; the
asset's record field our `src/chips.rs` `element` reads). The CHIP_ELEM enum
(constants.inc:117-127: FIRE 0, AQUA 1, ELEC 2, WOOD 3, PLUS 4, SWORD 5,
CURSOR 6, OBSTACLE 7, WIND 8, BREAK 9, NONE 0xa) maps onto the ELEM space the
primary table indexes by +1 for the four core elements (FIRE→HEAT 1,
AQUA→AQUA 2, ELEC→ELEC 3, WOOD→WOOD 4, NONE→NULL 0) and onto the secondary
bitfield for the rest (SWORD→0x80, CURSOR→0x40, WIND→0x20, BREAK→0x10).
provenance for the +1 and the bit mapping: derived — the primary table's own
row/column structure (its diagonal is only consistent with the ELEM enum
numbering, §2) plus the secondary flag_enum values; PLUS (4) and OBSTACLE (7)
have no readable row in either table and stay unported.
