# Recon: what ends an enemy-less battle (DeepSeek V4.1 Flash, 2026-09-12, UNVERIFIED where marked)

## 1. Every instruction that writes `SubsystemIndex` = 0x10

Direct, symbol-named stores (`oGameState_SubsystemIndex` == GameState+0, GameState base 0x02001b80):

```
asm00_1.s:5073  sub_800596C            asm00_1.s:5096  sub_8005990
asm00_1.s:5083      mov r1, #0x10      asm00_1.s:5105      mov r1, #0x10
asm00_1.s:5089      strb r0,[r5,#oGameState_SubsystemIndex]   asm00_1.s:5111  strb r0,[r5,...]
asm00_1.s:5191  sub_8005A28            asm00_1.s:5217  sub_8005A50
asm00_1.s:5210      strb r0,[r5,...]   asm00_1.s:5236      strb r0,[r5,...]
asm00_1.s:5931  warp_setSubsystemIndexTo0x10AndOthers_8005f00
asm00_1.s:5938      mov r0,#0x10 ; asm00_1.s:5939 strb r0,[r4,#oGameState_SubsystemIndex]
```
These are the only five literal writes of 0x10 to offset 0 in all of `asm/` (I scanned every `strb rN,[rM]` whose base register was loaded from `oToolkit_GameStatePtr`; the only three such unnamed stores are asm00_1.s:6028 (=0), ow_player.s:2633, map_script_cutscene.s:1123).

Generic writer that can also produce it:
```
map_script_cutscene.s:1114-1126  MapScriptCutsceneCmd_write_gamestate_byte (cmd 0x2a / 0x32)
  ldr r0,[r10,#oToolkit_GameStatePtr]
  bl ReadMapScriptByte        ; byte1 = GameState offset
  add r0,r0,r4
  bl ReadMapScriptByte        ; byte2 = value
  strb r4,[r0]                ; [GameState+byte1] = byte2  -> byte1=0,byte2=0x10 sets it
```
(`MapScriptCutsceneCmd_write_word/hword`, map_script_cutscene.s:1070-1106, write arbitrary memory, so offset 0 too. I found no tracked script using byte1=0.)

## 2. Reachability

The four `sub_80059xx` handlers have exactly one caller — the overworld warp dispatcher:
```
asm00_1.s:4975-4996  sub_80058D0:
  ldr r5,[r5,#oToolkit_GameStatePtr]
  ldrb r0,[r5,#oGameState_SubsystemIndex]
  cmp r0,#4
  bne .doNotCheckWarp          ; only runs in the SubsystemIndex==4 overworld handler
```
It is called from `gamestate_OnMapUpdate_8005268` (asm00_1.s:4358, call at 4394). So those four are **not** reachable from the battle loop (12).

`warp_setSubsystemIndexTo0x10AndOthers_8005f00` has two call sites, both cutscene bytecode:
```
map_script_cutscene.s:5315-5360  CutsceneCmd_warp_cmd_8038040
  ... bl warp_setSubsystemIndexTo0x10AndOthers_8005f00   ; line 5342 (subcmd 0x40)
  ... bl warp_setSubsystemIndexTo0x10AndOthers_8005f00   ; line 5358 (byte1 bit0 clear)
```
Scripts invoking it: `cs_warp_cmd_8038040_2 byte1=0x0 ...` in data/dat21.s:94,210,1614,2454,2575,3024,5227,5848,6302,7191,7309; dat22.s:166..., dat23.s:848....

The eS200BC50 "battle flow" writes nothing to GameState:
```
asm03_1_1.s:7206-7277  dispatch_803C620   ; r7 = eS200BC50, jump table on [r7]
asm03_1_1.s:7385-7400  sub_803C754        ; strb r0,[r7,#oS200BC50_Index00]=0; bl sub_813D9A0(0x32)
asm37_0.s:3729-3746    sub_813D5C8 / test0x200bc50_0x5_813D60C  ; only [eS200BC50+6]/[+5]
```
So eS200BC50 cannot itself set SubsystemIndex; it only feeds `eStruct2038160.BattleTerminate01`.

Living-enemy / enemy-list code (none writes SubsystemIndex):
```
asm00_1.s:8569-8601  SpawnBattleObjectUsingBattleEntityConfig_8007368
  loop_800736C: ldrb r0,[r6] ; and #0xf0 ; cmp #0xf0 ; beq done_8007384 ; ... bx dispatch
  done_8007384:                              ; line 8591
    ldrh r0,[r5,#oBattleState_Unk_04_05]
    strh r0,[r5,#oBattleState_Unk_12_13]     ; enemy/ally alive counts seeded from spawn
    CopyWords AliveBattleActors <- BattleActors (0x20 bytes)
asm00_1.s:15122-15138 battle_isBattleOver  ; reads Unk_12/Unk_13/Unk_0b (patched to ret 0)
asm00_1.s:16043-16067 sub_800A7A6          ; counts OpponentActors with NameID in [r1,r2]
asm00_1.s:15044-15060 relatedToIsBattleOver_800A11C  ; dec Unk_12/13, clears AliveBattleActors slot
asm01.s:487-511 sub_8020140 ; called first thing by battle_main_8007800 (asm00_1.s:9351)
  bl test0x200bc50_0x5_813D60C ; beq ret
  bl eStruct200BC30_getJumpOffset00 ; cmp r0,#0xc ; bne ret
  bl sub_813D66C ; bl dispatch_803C620 ; strb r0,[eStruct2038160+1]  ; BattleTerminate01
```
`sub_8007850` (asm00_1.s:9399, battle Index_00=0) then ends the battle when `eStruct2038160_getBattleTerminate01 != 0` (asm00_1.s:9467-9490) or when BC30 jump-offset has bit 0xc set (`tst r0,#0xc`, asm00_1.s:9466). Neither path stores to GameState; both only move BattleState indices, and the caller `HandlesBattleMainUntilEndOfBattleThenTriggersEnterMap` (asm00_1.s:4473-4483) writes **0**, not 16.

## Candidate mechanism (UNVERIFIED)

With an empty EnemySetup the dispatch loop hits `done_8007384` immediately (asm00_1.s:8591) and seeds `Unk_12_13`/`AliveBattleActors` from a zero enemy count; because `battle_isBattleOver` is patched to 0, the early end instead runs through `sub_8020140` → `eStruct2038160.BattleTerminate01` (asm01.s:487-511) and/or the BC30=0xc branch of `sub_8007850` (asm00_1.s:9466). The battle then exits to `EnterMap`, which starts the map cutscene (`cutscene_8036EFE`, asm00_1.s:4239); a `cs_warp_cmd_8038040_2 byte1=0x0` command in that script calls `warp_setSubsystemIndexTo0x10AndOthers_8005f00` (asm00_1.s:5931) whose `strb` at asm00_1.s:5939 writes 16. I did **not** observe the specific cutscene or prove the empty list causes the early terminate, and I found no "enemy count == 0" test that writes SubsystemIndex; the `~20` figure matches no terminate constant (the nearby 0x14 counters are asm00_1.s:9764-9772 and 11125), so treat the link as unconfirmed.

Smallest intervention (unverified): patch the `strb r0,[r4,#oGameState_SubsystemIndex]` at asm00_1.s:5939 to a no-op (`strb`→`nop`) so that cutscene warp cannot land 16, or hold `GameState[0]` = 0x0C (byte at 0x02001b80) every frame; to keep the battle alive upstream, hold `eStruct2038160.BattleTerminate01` (0x02038161) at 0 / patch `sub_8020140` (asm01.s:487) to return immediately. Which one is honest depends on whether the 12→16 write is the warp script or a direct 0x10 store; that is the unverified part.
