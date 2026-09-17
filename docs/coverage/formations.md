# formations (T65) -- the record streams as the ROM's own pointers walk them

Census of every BattleSettings record stream reachable from the ROM's own pointer tables
(reference/bn6f/bn6f.gba; probe scripts /tmp/t65_walk.py, /tmp/t65_census.py; generator tools/inventory.py).

## Pointer chains

- Family A (scripted battles): battleSettingsList0 @0x080aee70, BattleSettingsList1 @0x080b0d88 (bn6f.map:28302/28573), consumed by getBattleSettingsFromList0/List1 (asm/asm00_1.s:16046-16062, index*0x10). 269+192 = 461 records, 297 formation arrays (the old .s parse's numbers, confirmed).

- Family B (random encounters): off_8020170 group tables (selectEncounterTableForMap_80AA5F4, asm/asm29.s:10338-10457): [0x08020170] = real-world table (21 groups, off_8020190 block) / [+4] = internet table (23 words, proven by 0x080201E4 + 23*4 = 0x08020240 = pt_8020240, asm/asm01.s:555-580); mapgroup >= 0x80 indexes the internet table at group-0x80. Group slot -> map array (16 words) -> record list. EVENT_67F/680/681 swap only the internet table (0x08020178/80/88). 82 distinct lists, 779 records, 779 formation arrays -- ALL missed by the old .s parse.

- Totals: 84 lists (2 scripted + 82 encounter), 1240 records, 1076 distinct 0xF0-terminated formation arrays; 0 terminator mismatches (every list ends on record[0]==0xff, every EnemySetupArrPtr reaches a 0xF0).

- Record = 16 bytes (include/rom_structs/BattleSettings.inc): byte[0]==0xff list terminator, byte[4] Background (meaning proven by battleSettings_setBackground asm/asm03_0.s:14591-14593, strb r0,[BattleSettings_200AF60+0x4]), byte[7] gate handler index (JumpTable80AA6B8, asm29.s:10471), u32@0xc EnemySetupArrPtr -> 4-byte quads, quad[0]==0xF0 stop, quad[2] = enemy id. Formation = byte_ label (family A, labels carried from data/BattleSettings.s) or rom_XXXXXXXX (family B, unlabeled in ROM).


## Known answers (CentralArea1, list 0x080b4b78, mapgroup 0x90 map 0, 14 records)

| rec | addr | rec7 | formation | enemy ids (quad[2]) |
|---|---|---|---|---|
| rec0 | 080b4b78 | 0 | 0x080b52f9 | 00,01,01 |
| rec1 | 080b4b88 | 0 | 0x080b5306 | 00,01,01 |
| rec2 | 080b4b98 | 0 | 0x080b5313 | 00,01,01 |
| rec3 | 080b4ba8 | 0 | 0x080b5320 | 00,01,01 |
| rec4 | 080b4bb8 | 0 | 0x080b532d | 00,01,01 |
| rec5 | 080b4bc8 | 0 | 0x080b533a | 00,01,01 |
| rec6 | 080b4bd8 | 0 | 0x080b5347 | 00,01,85 |
| rec7 | 080b4be8 | 0 | 0x080b5354 | 00,01,01,01 |
| rec8 | 080b4bf8 | 0 | 0x080b5365 | 00,01,01,01 |
| rec9 | 080b4c08 | 0 | 0x080b5376 | 00,01,01,01 |
| rec10 | 080b4c18 | 0 | 0x080b5387 | 00,01,85,01 |
| rec11 | 080b4c28 | 0 | 0x080b5398 | 00,01,01,01,0c |
| rec12 | 080b4c38 | 1 | 0x080b53ad | 00,01,01,05 |
| rec13 | 080b4c48 | 1 | 0x080b53be | 00,01,01,06 |

rec6 = 0x080b4bd8 (ids 00,01,85) and rec10 = 0x080b4c18 (ids 00,01,85,01, formation 0x080b5387 = T58's byte_80B5387) are ungated; rec12 0x080b4c38 (id 05) and rec13 0x080b4c48 (id 06) carry rec7==1 -> sub_80AA6EC (asm29.s:10488, EVENT_1D8 + progress gate) -- all four byte-for-byte as T58 recorded.

Roll arithmetic re-derived: the mod count is the FILTERED count (12 rec7==0 records here, not 14): poke+1 882 mod 12 = 6 (rec6), 886 mod 12 = 10 (rec10), 894 mod 12 = 6, and 894 mod 14 = 12 = T58's 'count of 14 would have picked rec12'.


## M5 answer: ungated (rec7==0) records naming enemy_idx 2..6

**Lever values exist only for family B** (the random-encounter lists the roll actually reads via selectEncounterTableForMap_80AA5F4). Family A is fetched by index (getBattleSettingsFromList0/List1, idx*0x10) -- there is no iCurrFrame roll in family A, so its records below are listed without lever semantics.

**Lever** = position of the record among its list's rec7==0 records = the value v such that `iCurrFrame mod (filtered count) == v` picks it (T58 model: the roll reads iCurrFrame one tick after the frame-60 poke; element-mask test of sub_80AA824 assumed passing under the 0x1f fallback select arg; other JumpTable80AA6B8 handlers passing would shift the count).

### Notation legend (read before auditing rows)

- Columns: **list** = encounter-list ROM address; **mapgroup/map** = owner slot in the group tables (mapgroup shown as 0x80+g for internet groups); **rec** = 0-based record index within the list; **addr** = record address; **lever** = filtered position (see above); **enemy_idx(qN)** = quad N of the record's formation array, 0-based over the 4-byte EnemySetup entries, whose byte[2] is the named enemy id; **formation** = array address.

- `(q0, id)`-style pairs are (quad index, enemy id byte[2]) -- NOT raw ROM quad dumps; a record naming the same id in several slots prints one pair per slot. Version nibbles (quad[3]>>4) read 0 throughout this census and are not shown.

### Family B (roll-levered): 88 ungated records over 24 distinct lists

enemy_idx 2 (92 slots) and 3 (42 slots) only.

**NEGATIVE, scoped to family B: zero family-B records are ungated AND name enemy_idx 4, 5 or 6.** In family B, ids 5 and 6 appear exactly once each and both behind the rec7==1 gate (CentralArea1 rec12 0x080b4c38 / rec13 0x080b4c48); id 4 never appears in family B at all. This is a PER-FAMILY statement: family A (scripted, index-fetched) DOES hold ungated records naming 4/5/6 -- 15 records with rec7==0 (e.g. 0x080af430, 0x080af480, 0x080af4e0 name enemy_idx 4) -- but none of them is reachable through the encounter roll.

| list | mapgroup/map | rec | addr | lever | enemy_idx (quad slot) | formation |
|---|---|---|---|---|---|---|
| 0x080b2408 | 0x02/0 | rec1 | 0x080b2418 | 1 | 2(q2) | 0x080b26de |
| 0x080b2408 | 0x02/0 | rec3 | 0x080b2438 | 3 | 2(q1) | 0x080b2700 |
| 0x080b2408 | 0x02/0 | rec5 | 0x080b2458 | 5 | 2(q2) | 0x080b2722 |
| 0x080b2408 | 0x02/0 | rec6 | 0x080b2468 | 6 | 2(q1) 2(q3) | 0x080b272f |
| 0x080b2408 | 0x02/0 | rec11 | 0x080b24b8 | 11 | 2(q3) | 0x080b278c |
| 0x080b24ec | 0x02/1 | rec3 | 0x080b251c | 3 | 2(q2) | 0x080b27fa |
| 0x080b24ec | 0x02/1 | rec6 | 0x080b254c | 6 | 2(q1) 2(q2) | 0x080b2821 |
| 0x080b24ec | 0x02/1 | rec9 | 0x080b257c | 9 | 2(q3) | 0x080b2854 |
| 0x080b24ec | 0x02/1 | rec10 | 0x080b258c | 10 | 2(q1) 2(q3) | 0x080b286d |
| 0x080b24ec | 0x02/1 | rec11 | 0x080b259c | 11 | 2(q1) 2(q2) 2(q3) | 0x080b287e |
| 0x080b25f0 | 0x02/2 | rec2 | 0x080b2610 | 2 | 2(q1) | 0x080b28f1 |
| 0x080b25f0 | 0x02/2 | rec3 | 0x080b2620 | 3 | 2(q2) 2(q3) | 0x080b28fe |
| 0x080b25f0 | 0x02/2 | rec8 | 0x080b2670 | 8 | 2(q2) | 0x080b2957 |
| 0x080b25f0 | 0x02/2 | rec11 | 0x080b26a0 | 11 | 2(q3) | 0x080b2992 |
| 0x080b2f1c | 0x05/0 | rec4 | 0x080b2f5c | 4 | 3(q1) | 0x080b3321 |
| 0x080b2f1c | 0x05/0 | rec8 | 0x080b2f9c | 8 | 3(q1) | 0x080b3361 |
| 0x080b2f1c | 0x05/0 | rec11 | 0x080b2fcc | 11 | 3(q1) 3(q2) | 0x080b3394 |
| 0x080b2fe0 | 0x05/1 | rec3 | 0x080b3010 | 3 | 2(q2) | 0x080b33d8 |
| 0x080b2fe0 | 0x05/1 | rec6 | 0x080b3040 | 6 | 3(q1) 3(q2) | 0x080b33ff |
| 0x080b2fe0 | 0x05/1 | rec9 | 0x080b3070 | 9 | 3(q3) | 0x080b3432 |
| 0x080b2fe0 | 0x05/1 | rec10 | 0x080b3080 | 10 | 3(q1) | 0x080b344b |
| 0x080b2fe0 | 0x05/1 | rec11 | 0x080b3090 | 11 | 3(q1) | 0x080b345c |
| 0x080b31a8 | 0x05/3 | rec7 | 0x080b3218 | 7 | 3(q3) | 0x080b35d8 |
| 0x080b31a8 | 0x05/3 | rec11 | 0x080b3258 | 11 | 3(q1) 3(q3) | 0x080b3624 |
| 0x080b3740 | 0x08/1 | rec1 | 0x080b3750 | 1 | 3(q2) 3(q3) | 0x080b3892 |
| 0x080b3740 | 0x08/1 | rec2 | 0x080b3760 | 2 | 3(q1) 3(q2) | 0x080b38a3 |
| 0x080b3b8c | 0x0c/7 | rec0 | 0x080b3b8c | 0 | 2(q2) | 0x080b3f95 |
| 0x080b3b8c | 0x0c/7 | rec1 | 0x080b3b9c | 1 | 2(q2) | 0x080b3fa2 |
| 0x080b3b8c | 0x0c/7 | rec3 | 0x080b3bbc | 3 | 2(q1) 2(q3) | 0x080b3fbc |
| 0x080b3ce0 | 0x0c/12 | rec0 | 0x080b3ce0 | 0 | 2(q1) | 0x080b40c1 |
| 0x080b3ce0 | 0x0c/12 | rec2 | 0x080b3d00 | 2 | 2(q2) | 0x080b40e3 |
| 0x080b4268 | 0x0d/1 | rec0 | 0x080b4268 | 0 | 2(q1) 2(q2) | 0x080b46d9 |
| 0x080b4268 | 0x0d/1 | rec1 | 0x080b4278 | 1 | 2(q1) 2(q2) | 0x080b46e6 |
| 0x080b4268 | 0x0d/1 | rec2 | 0x080b4288 | 2 | 2(q1) 2(q2) 2(q3) | 0x080b46f3 |
| 0x080b4268 | 0x0d/1 | rec3 | 0x080b4298 | 3 | 2(q1) 2(q3) | 0x080b4704 |
| 0x080b4598 | 0x0d/13 | rec0 | 0x080b4598 | 0 | 2(q1) 2(q2) 2(q3) | 0x080b49c1 |
| 0x080b4598 | 0x0d/13 | rec1 | 0x080b45a8 | 1 | 2(q1) 2(q2) 2(q3) | 0x080b49d2 |
| 0x080b4598 | 0x0d/13 | rec2 | 0x080b45b8 | 2 | 2(q1) 2(q2) 2(q3) | 0x080b49e3 |
| 0x080b4598 | 0x0d/13 | rec3 | 0x080b45c8 | 3 | 2(q1) 2(q2) 2(q3) | 0x080b49f4 |
| 0x080b45dc | 0x0d/14 | rec0 | 0x080b45dc | 0 | 2(q1) | 0x080b4a05 |
| 0x080b45dc | 0x0d/14 | rec1 | 0x080b45ec | 1 | 2(q1) 2(q2) 2(q3) | 0x080b4a16 |
| 0x080b45dc | 0x0d/14 | rec2 | 0x080b45fc | 2 | 2(q1) 2(q2) | 0x080b4a27 |
| 0x080b45dc | 0x0d/14 | rec3 | 0x080b460c | 3 | 2(q1) | 0x080b4a34 |
| 0x080b45dc | 0x0d/14 | rec4 | 0x080b461c | 4 | 2(q1) 2(q2) 2(q3) | 0x080b4a41 |
| 0x080b45dc | 0x0d/14 | rec5 | 0x080b462c | 5 | 2(q1) 2(q2) | 0x080b4a52 |
| 0x080b45dc | 0x0d/14 | rec6 | 0x080b463c | 6 | 2(q1) 2(q3) | 0x080b4a5f |
| 0x080b45dc | 0x0d/14 | rec7 | 0x080b464c | 7 | 2(q1) | 0x080b4a70 |
| 0x080b4660 | 0x0d/15 | rec1 | 0x080b4670 | 1 | 2(q2) | 0x080b4a8a |
| 0x080b4660 | 0x0d/15 | rec3 | 0x080b4690 | 3 | 2(q1) 2(q2) | 0x080b4aa4 |
| 0x080b5c64 | 0x11/2 | rec2 | 0x080b5c84 | 2 | 2(q1) | 0x080b60bc |
| 0x080b5c64 | 0x11/2 | rec4 | 0x080b5ca4 | 4 | 2(q1) 2(q2) | 0x080b60d6 |
| 0x080b5c64 | 0x11/2 | rec8 | 0x080b5ce4 | 8 | 2(q1) | 0x080b6116 |
| 0x080b5c64 | 0x11/2 | rec9 | 0x080b5cf4 | 9 | 2(q2) 2(q3) | 0x080b6127 |
| 0x080b5c64 | 0x11/2 | rec11 | 0x080b5d14 | 11 | 2(q1) | 0x080b614d |
| 0x080b5d48 | 0x11/3 | rec0 | 0x080b5d48 | 0 | 2(q1) | 0x080b6184 |
| 0x080b5d48 | 0x11/3 | rec3 | 0x080b5d78 | 3 | 2(q2) | 0x080b61ab |
| 0x080b5dcc | 0x11/4 | rec0 | 0x080b5dcc | 0 | 2(q1) | 0x080b6200 |
| 0x080b5dcc | 0x11/4 | rec3 | 0x080b5dfc | 3 | 2(q2) | 0x080b6227 |
| 0x080b6338 | 0x12/0 | rec1 | 0x080b6348 | 1 | 2(q1) 2(q3) | 0x080b64fe |
| 0x080b6338 | 0x12/0 | rec4 | 0x080b6378 | 4 | 2(q1) | 0x080b6529 |
| 0x080b6338 | 0x12/0 | rec7 | 0x080b63a8 | 7 | 2(q1) 2(q2) | 0x080b6554 |
| 0x080b6338 | 0x12/0 | rec8 | 0x080b63b8 | 8 | 2(q1) | 0x080b6565 |
| 0x080b6338 | 0x12/0 | rec10 | 0x080b63d8 | 10 | 2(q3) | 0x080b6583 |
| 0x080b63fc | 0x12/1 | rec4 | 0x080b643c | 4 | 2(q1) 2(q2) | 0x080b65e9 |
| 0x080b63fc | 0x12/1 | rec7 | 0x080b646c | 7 | 2(q3) | 0x080b6624 |
| 0x080b63fc | 0x12/1 | rec10 | 0x080b649c | 10 | 2(q2) 2(q3) | 0x080b665b |
| 0x080b66e8 | 0x13/0 | rec2 | 0x080b6708 | 2 | 3(q1) 3(q3) | 0x080b69ab |
| 0x080b66e8 | 0x13/0 | rec3 | 0x080b6718 | 3 | 3(q2) | 0x080b69bc |
| 0x080b66e8 | 0x13/0 | rec4 | 0x080b6728 | 4 | 3(q1) | 0x080b69c9 |
| 0x080b66e8 | 0x13/0 | rec6 | 0x080b6748 | 6 | 3(q2) | 0x080b69e7 |
| 0x080b66e8 | 0x13/0 | rec7 | 0x080b6758 | 7 | 3(q1) 3(q2) | 0x080b69f4 |
| 0x080b66e8 | 0x13/0 | rec9 | 0x080b6778 | 9 | 3(q2) | 0x080b6a16 |
| 0x080b683c | 0x13/1 | rec3 | 0x080b686c | 3 | 3(q1) | 0x080b6b05 |
| 0x080b683c | 0x13/1 | rec8 | 0x080b68bc | 8 | 3(q2) 3(q3) | 0x080b6b4e |
| 0x080b72f8 | 0x15/1 | rec0 | 0x080b72f8 | 0 | 2(q1) | 0x080b76cb |
| 0x080b72f8 | 0x15/1 | rec3 | 0x080b7328 | 3 | 2(q1) | 0x080b76fe |
| 0x080b72f8 | 0x15/1 | rec13 | 0x080b73c8 | 13 | 2(q1) | 0x080b779c |
| 0x080b73fc | 0x15/2 | rec0 | 0x080b73fc | 0 | 3(q1) | 0x080b77cb |
| 0x080b73fc | 0x15/2 | rec2 | 0x080b741c | 2 | 3(q1) | 0x080b77e9 |
| 0x080b73fc | 0x15/2 | rec3 | 0x080b742c | 3 | 3(q1) | 0x080b77fa |
| 0x080b73fc | 0x15/2 | rec4 | 0x080b743c | 4 | 3(q1) 3(q2) | 0x080b7807 |
| 0x080b73fc | 0x15/2 | rec5 | 0x080b744c | 5 | 3(q2) | 0x080b7818 |
| 0x080b73fc | 0x15/2 | rec7 | 0x080b746c | 7 | 3(q1) | 0x080b7836 |
| 0x080b7b14 | 0x16/1 | rec9 | 0x080b7ba4 | 9 | 3(q1) | 0x080b7fa3 |
| 0x080b7b14 | 0x16/1 | rec10 | 0x080b7bb4 | 10 | 3(q2) | 0x080b7fb4 |
| 0x080b7b14 | 0x16/1 | rec13 | 0x080b7be4 | 13 | 3(q1) 3(q2) | 0x080b7fe3 |
| 0x080b7ce8 | 0x16/2 | rec0 | 0x080b7ce8 | 0 | 3(q1) 3(q3) | 0x080b80e7 |
| 0x080b7ce8 | 0x16/2 | rec6 | 0x080b7d48 | 6 | 3(q1) 3(q3) | 0x080b8145 |

### Family A (scripted, index-fetched -- no roll lever): 50 records name enemy_idx 2..6

All rec7==0; enemy_idx 2 in 26 slots, 3 in 45, 4 in 25; the 15 records naming 4/5/6 are the only family-A occurrences of those ranks. Fetched by getBattleSettingsFromList0/List1(battleSettingsIdx), so fielding them is an index question, not a lever question.


## Caveats

- **Zero-id gap:** 1045 of the 1076 formation arrays contain a quad with byte[2]==0x00 (e.g. rom_080aff44 = ['00','7f'], and every CentralArea1 record's first quad). Nobody has interpreted id 0x00 from a table or reader in this census; it is consistent with the player/MegaMan slot T9c observed (slot data shows 0x00 slots beside NameID 0x0001 Mettaur), but treat 0x00 as UNVERIFIED, not an enemy_idx.

- Lever values assume only rec7==0 records pass; if an event sets a gate handler (entries 2..11 of JumpTable80AA6B8) the filtered count grows and every subsequent lever shifts.

- Element-mask pass rate per select arg (0x40 / 0x20 / PET byte / 0x1f fallback) is inferred from T58's three verified (poke, record) pairs, not traced.

