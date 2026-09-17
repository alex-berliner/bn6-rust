# entries.md -- the BattleSettings entry types and how each is fielded (M2)

## The two families and their fetch paths (T65 PASS 1, re-cited)

1240 records over 84 lists, 1076 formation arrays. **Family B** (random encounters): 82 lists in
the off_8020170 tree, fetched by `rollRandomEncounter_80AA4C0` (asm/asm29.s:10133-10325) ->
`selectEncounterTableForMap_80AA5F4` (asm29.s:10337-10457): root word chosen by EVENT_67F/680/681
(asm29.s:10340-10363; flags at eEventFlags 0x02001c88), group/map bytes (asm29.s:10367-10373),
rec[7] gate (asm29.s:10400-10404, JumpTable80AA6B8 asm29.s:10471-10496), element mask
(asm29.s:10405-10408), index = `iCurrFrame mod filtered_count` (asm29.s:10432-10436). **Family A**
(scripted): battleSettingsList0 0x080aee70 / BattleSettingsList1 0x080b0d88 (bn6f.map:28302/28573),
fetched BY INDEX at `idx*0x10` with no bounds check -- `getBattleSettingsFromList0/List1`
(asm/asm00_1.s:16048-16066); callers: chatbox.s:5528-5539 (text-script halfword),
map_script_cutscene.s:5528-5545 (`ReadMapScriptHalfword`), asm28_0.s:314-317 (`[r5,#4]` cutscene
var), asm03_1_1.s:2452-2454 (constant 0), asm33.s:16503-16506 (caller arg, list1),
asm03_0.s:14606-14619 (byte at `byte_203CA50+2*(oBattleState_Unk_1a-1)`, in-battle, list1). None of
the six callers' indexes is overworld-pokable (entries.md census, T131 worklog step 1).

## T131 -- can a family-A record be fielded at all? YES: the roll's OPT path

`rollRandomEncounter_80AA4C0` has a pre-chosen-record branch BEFORE the table walk
(asm29.s:10216-10234): if `oS2001c04_Unk_28` (u32 @0x02001c2c, S2001c04.inc:23) is nonzero AND
`GetPositiveSignedRNG` bit0 == 0 (asm29.s:10220-10222; the routine is `GetRNG`'s step plus a
0x7fffffff mask, asm00_0.s:2631-2646 -- adoption iff bit30 of the seed at the draw is 0) AND
`oS2001c04_OptCurBattleDataPtr` (u32 @0x02001c30, S2001c04.inc:24) is 0x08-prefixed
(asm29.s:10224-10230), the roll executes the store at 0x080AA54A (asm29.s:10233) and adopts the
pointer as the chosen record. **Any 0x08 record -- family A included -- with no root walk, no rec7
gate, no count.** The three levers a poke can set, canon-side:

- ROOT: the four root words are ROM (off_8020170/178/180/188); a 2944-slot ROM walk of all four
  trees (both halves) contains **zero** family-A lists, so the root lever (EVENT flags) cannot
  reach family A. It CAN reach family B alternates (T87).
- INDEX: `iCurrFrame mod count` reaches family-B records only (family A is never in the walk).
- GATE: rec[7] handlers apply only to the family-B walk; all three family-A records named below
  read gate[7]==0.
- **THE FAMILY-A LEVER**: the OPT words 0x02001c2c (nonzero) + 0x02001c30/0x02001c32 (record
  pointer), plus an admission seed for the bit0 gate.

## 0x02001b9c verdict (the T58/T70 vs T76 dispute)

`GameState.CurBattleDataPtr` loc=0x1c (GameState.inc:50) at 0x02001b80 = **0x02001b9c**, and the
same word is `BattleState+0x38` via `oToolkit_BattleStatePtr` (sub_800A714's `strh #0`,
asm00_1.s:16040-16044). Both names address one word. It IS a 0x080axxxx-shape **pointer** (T58/T70
right): measured, the halfword pair reads `a0f80a08` = 0x080af8a0 from frame 60 on
(/tmp/t131_c2/settings.bin). Writers measured by `--watch-write 0x02001b98:8` on the battlestart
route: the roll's OPT store `str r0,[r7,#oGameState_CurBattleDataPtr]` at **0x080AA54A =
asm/asm29.s:10233** (frame 60, old 0x00000000 -> 0x080af8a0, lr=0x080AA539 = the return from
`GetPositiveSignedRNG`); then **StartBattle** re-pins it (0x08005BD4 = asm/asm00_1.s:5428, frame
60, value-preserving); then **copyWords_80014EC** re-copies it (0x080014F4, frame 76,
value-preserving, lr=0x08006C4A). sub_800A714's halfword zero never fired in frames 0..159 (it is
a teardown/init zeroing, not a data format).

## The fielding triple (poke, record, slots) -- rec163 0x080af8a0, measured

State `battlestart_scripted` (tools/states.py) = battlestart_ai4_rank0's route PLUS frame-59 pokes
`0x02001c2c:0x0001`, `0x02001c30:0xf8a0`, `0x02001c32:0x080a`, and admission seed
`0x020013f0:0xd7c1`/`0x020013f2:0x7734` = 0x7734d7c1. The seed is required: the natural frame-60
chain holds exactly 3 draws and the OPT draw's candidate bit reads 1 (reject) at every candidate
position (C1 seed watch + GetPositiveSignedRNG algebra); 0x7734d7c1 makes the roll's ADJACENT draws
(threshold `GetRNG` asm29.s:10204, then OPT `GetPositiveSignedRNG` :10220, no call between)
satisfy `(draw & 0x1f) < 12` (byte_8020C5C[0x85] = 12, CentralArea1 rate 5) and bit0 == 0 for
either draw ordering.

| quad (rec163 formation 0x080b06a3) | slot (built-frame coords) | NameID +0x28 | HP +0x24 | panel +0x12 |
|---|---|---|---|---|
| `11348800` | e1 (0x0203aa88), populate frame **69** | **0x0088** | **0x00fa** = GunnerEnemyStruct2_8112B9C row 3 | **(4,3)** = 0x0304 |
| `11158800` | e2 (0x0203ab60) | **0x0088** | **0x00fa** | **(5,1)** = 0x0105 |
| `11261600` | e3 (0x0203ac38) | **0x0016** (ai4 v3) | **0x00c8** = off_8109150[4] 0x0810ae4c row 3 | **(6,2)** = 0x0206 |

quad[0] `00220000` is the dispatch-0 player spawn (consumes no enemy slot). Byte-equality holds at
populate frame 69 and through the whole 40-frame window (69..108). The first three fields were
never visible to the old 30-byte e-watches (NameID +0x28 sits past row 0x1d); trace.py's e-watches
are now 34 bytes and parse NameID (T131).

## Determinism and negative (measured)

- Determinism: `trace.py record canon battlestart_scripted` twice (/tmp/tr_s1, /tmp/tr_s2) ->
  **0 divergent frames/fields** over all 113 captured frames, hence over the 40-frame window
  69..108, on e1/e2/e3 NameID/HP/panel and the settings word.
- Negative (lever absent = battlestart_ai4_rank0's route, C1): enemy-slot fields (state/action/
  panel/HP) first diverge at **frame 148** overworld coords = built-frame 69 = the populate frame;
  the settings word itself diverges at frame 60 (the lever's own write: 0x080b50e0 vs 0x080af8a0).
- M1: formations line moved `verified 0/1076` -> `verified 1/1076` (the row referenced by
  `rec 0x080af8a0 (battleSettingsList0)` is `recorded (canon)`, scenario `battlestart_scripted`).
- ROM sha256 before = after = `a37c1028adb72082b51e142321fa437967bc54b6f46730a53f6581ad455ad670`
  (no src/ change).

## Unverified

Whether a scripted entry's sequencer arms (attack timing) differ from the roll's -- that is the
port, not this lever: on this route the sequencer stays 0 (T58/T87's stuck-sequencer blocker) and
no attack arms through the captured frames. Also unverified: rec183 0x080af9e0 / rec217 0x080afc00
are fielded by the identical recipe (same lever, different OptCurBattleDataPtr halfwords) -- their
quads are dumped in docs/worklog/T131.md but only rec163 was captured.
