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

## R4 step-1 findings (GLM-5, 2026-09-12): the candidate chain is NOT what fires; the teardown is a memory release

All addresses below verified against ROM bytes, not just decomp labels. Frames are relative to
loading `/tmp/emptyfield_start.state` (never-spawn battle, battle age = frame+3); watches are
per-frame snapshots unless noted.

### What does NOT fire (each excluded by watch and/or trace)

- `eStruct2038160.BattleTerminate01` (0x02038161): stays 0x00 through the teardown.
- BC30 jump-offset byte (0x0200BC30): 0x00 the whole battle in BOTH the never-spawn battle and
  the no-op-poke control. `eStruct203F7D8+1` (0x0203F7D9) = 0x02 in BOTH battles from the first
  battle frame, so `sub_8007850`'s `r4==2` gate (loc_80078C6) is common battle-start flow, not
  the differentiator. `eS200BC50` (0x0200bc50) stays all-zero the whole battle.
- `HandlesBattleMainUntilEndOfBattleThenTriggersEnterMap` write-0: `BattleState.Unk_0a`
  (+0x0a) = 1 every frame, battle_main always returns nonzero, the SubsystemIndex=0 store never
  runs. The frequent `--trace-pc` hits at 0x08005368 (lr=0x08007829, r0=1) are the benign
  every-frame path: battle_main (0x08007800) tail-calls into 0x08005360, whose `bl` (encoded
  target 0x08009800 — the decomp's "bl battle_main_8007800" label there is wrong) just re-writes
  SubsystemIndex=0x0c and clears GameState byte1. Note the hit PC is addr+4 because the check
  runs while the second BL halfword executes.
- All five literal `SubsystemIndex=0x10` stores (0x08005f0c, 0x0800598C, 0x080059B0,
  0x08005A4C, 0x08005A74), `warp_setSubsystemIndexTo0x10AndOthers_8005f00` entry (0x08005f00),
  `CutsceneCmd_warp_cmd` (0x08038040) and the generic script byte-writer strb (0x08035F06):
  ZERO trace hits in the teardown frames. Caveat: `--trace-pc` perturbs timing on this title
  (single-stepping past SWI HLE accelerates the game loop inside traced frames; the teardown
  appears ~1 frame early under trace), so these traces are qualitative.

### What actually happens (watch data, never-spawn battle)

- f88-89 (age 91-92): the custom screen opens on schedule (`BattleState.Index_01=8`, +3=1) —
  the chip window itself is healthy.
- f99 (age 102): `CurBattleDataPtr` (GameState+0x1c, 0x02001b9c) is cleared to 0 — the FIRST
  teardown event. The bytes at 0x02001b80 change to `10 11 11` the same frame, but this is
  freed-heap fill, NOT `SubsystemIndex=0x10`: at f100 `BattleStatePtr` (0x020093c8) reads
  `00 11 22 00` and `GameStatePtr` (0x020093ec) reads 0 (0x11/0x22 free-fill patterns), and the
  cutscene state (0x02011c50) is still 0xff (inactive) at f99, populating only at f100.
- f100+: battle dispatch stops (`BattleState` frozen at `04 08 00 01 01 ...`), joypad input is
  inert, rendering continues. R3's "SubsystemIndex goes 12 -> 16" was this fill artifact.
- Control battle (roll's own entry 0x080b4bb8 via the same poke mechanism): no release through
  260+ frames. Its custom screen opens later than age 91 (Index_01 still 0 at age 92), so
  same-age memory diffs mix phase differences.
- BattleSettings entries 0x080b4b88 vs 0x080b4bb8 differ ONLY in the three EnemySetup pointers
  (0x080b5306 emptied vs 0x080b532d real); byte[0]=0 in both; no timer/flag field.

### Interventions tried (all failed to keep the battle alive)

1. Hold GameState[0..3]=(0c,00,00,00) every frame (--cheat 0x02001b80:0x000c + 0x02001b82:0x0000):
   the release still runs; battle frozen after f100; script presses (A@130,Start@140,A@150)
   produce no state change — input inert. 620 frames captured without crash.
2. Hold BattleState+0x12/+0x13 at the control's values (0x02034892:0x0203): release unchanged.
3. Hold CurBattleDataPtr + BattleStatePtr + GameStatePtr (6 halfword cheats): release
   unchanged; dispatch stops anyway.

### Conclusion

The exit decision is upstream of every tested held-RAM point: something inside the battle
(silently, with the custom screen open, ~11 frames after it opens) commits to battle exit and
the release machinery frees CurBattleDataPtr one frame before the toolkit pointers. The release
writes reach GameState+0x1c through indirect dispatch (the only labeled `str` sites are
initNewGameData_8004DF0 and StartBattle, both setters), so the deciding store is still
unidentified. Until it is found, no held RAM value or one-shot poke can deliver R4 step 2
(battle alive 600+ frames with a firing chip), and steps 3a/3b (new states + determinism +
R2 measurement on the never-spawn route) are blocked.

## R5 addendum (2026-09-12, wt/r5-watch) -- watchpoint results

Instrument: `mgba_capture --watch-write addr[:len]` (commit 17dc00f): real libmgba
WATCHPOINT_WRITE shims, byte-granule, verified frame-identical with the flag off and
on the known roll store (asm29.s:10286 -> `at=0x080AA59E lr=0x080AA6F9`).

Release event, live recipe (overworld_net -> script -> pokes 60/70; battle age = capture frame - 79):

- Age 99 (capture frame 178): 0x02001b9c..0x02001bac (CurBattleDataPtr, +ba0/ba4/ba8/bac) all clear
  in ONE frame; 0x02001b80..b98 become freed-heap nibble fill (0x11/0x22 patterns). The battle
  GameState heap block is released at age 99. Screen is frozen (static frame hash) from age ~11 to
  ~68 and resumes changing after the release.
- The writes emit ZERO watchpoint hits while the same watches are live in the same frame (DISPCNT
  store at 0x08001760 fires at 178). Excluded: CPU stores (all widths + STM), DMA (forced DMA3 fill
  fires), SWI RegisterRamReset, CpuSet/CpuFastSet (frame-178 SWI delta has no dest in the block).
  The release write bypasses every path libmgba 0.10.2's shims instrument -- it is an
  emulator-internals question, not a game-code question. R4's "indirect dispatch" is real.
- Caveat for tool users: `--poke-at`/`--cheat` writes are also caught and report the CPU's stale
  r15 as `at` (they run outside the emulator loop between frames).

State-reload hazard: loading /tmp/emptyfield_start.state or /tmp/r4_pre*.state directly and running
past battle age ~68 derails deterministically (PC walks into 0xDE31xxxx, illegal 0x0000b710), on the
old and new binary alike, while live runs stay healthy -- savestate reload is not faithful for this
scenario at depth. State-based probing past age ~68 is unsafe; use live runs.
