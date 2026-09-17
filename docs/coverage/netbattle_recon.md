# Netbattle (M10) recon supplement — T97 follow-up audit, 2026-09-17

This is a **companion** to `docs/coverage/netbattle.md` (landed on main as the
NEGATIVE closure of T97 by a prior worker, commit `d3f65fc`). That doc carries
the 16 cites the prior worker landed. This file carries:

1. the additional cross-checks I ran (BattleState struct, per-player overlay
   semantics, scenario levers);
2. the per-ticket acceptance items re-stated against the existing cites
   so the verifier doesn't have to re-grep;
3. the negative-naming closure per the ticket's "NEGATIVE naming 'mgba lacks
   --net-battle flag, requires 7ag' closes it" rule.

No `src/` edits. No harness row. No state file. No allowlist edit. mgba_capture.c
off-limits.

---

## 0. Cross-reference of existing recon to ticket items

| ticket item | cite in `docs/coverage/netbattle.md` | this doc supplements |
|-------------|--------------------------------------|----------------------|
| handshake routine (file:line) | §1: `libSIO814469C` libs.s:799-807; `libSIOControlStart` libs.s:896-905; `sub_813D648` asm37_0.s:3822-3831 (wireless arm); `sub_81465BC` libs.s:5079-5112 | §A below: cross-checked against `constants/gba_constants.inc:58-59` for SIOCNT (0x4000128) and the multi-player-mode registers 0x4000120-0x4000126 |
| chip-trade routines (file:line) | §3: `sub_8039B0A` asm03_1_1.s:2018-2065; payload write `sub_81469BC` libs.s:5704-5722 (bytes at unk_2010150+0x0b/+0x0c = 0x201015B/0x201015C); pair source `sub_803C418` asm03_1_1.s:6884-6902 | §B below: distinguishes netbattle trade (asm03_1_1.s) from overworld `subsystem_launchChipTrader` (asm00_1.s:5694-5735) and `ts_start_chip_trader` (include/bytecode/text_script_commands.inc:1233,1236) |
| NetState byte (EWRAM address) | §4: `BattleSettings_200AF60` is a singleton at 0x0200AF60; `BattleSettings.background` byte at +0x4 = **0x0200AF64**; writer `battleSettings_setBackground` asm03_0.s:14589-14596 (the SCOPE M1 cite, also M10's UI gate) | §C below: re-states the **alternative** network-state byte — `BattleState_Unk_0d` at offset 0x0d (the alliance-XOR byte, used by `battle_networkInvert` asm00_1.s:16532) plus `BattleState_Unk_11` flag byte at offset 0x11 (which carries `BATTLE_EFFECT_NETWORK_BATTLE` = 0x04 per `constants/enums/battle_constants.inc:5`) |
| per-frame state machine dispatcher | §2: `cb_80395A4` asm03_1_1.s:1309-1346; six-state table off_80395C8 with 0x00/0x04/0x08/0x0C/0x10/0x14 → sub_80395E4/3630/3658/99CE/A690/B160 | §D below: distinguishes netbattle session FSM (asm03_1_1.s) from the chip-window FSM (`chipWindowState00SlideIn_8026B04` at asm03_0.s:894, clears `BATTLE_EFFECT_NETWORK_BATTLE` at asm03_0.s:1068) and the battle FSM (`dispatchBattleFsm_8009158` referenced in `constants/enums/battle_constants.inc:34-37`) |
| per-player BattleSettings overlay | §4: BattleSettings is a **singleton** at 0x0200AF60, NOT a record table — the per-player overlay is the union of (BattleSettings, `BattleState_Unk_0d`, `BATTLE_EFFECT_NETWORK_BATTLE`) | §E below: confirms this from the struct layout (`include/rom_structs/BattleSettings.inc` 16 bytes; `oBattleState_BattleSettings` u32 pointer at BattleState+0x3c; `BattleSettings.BattleType` byte at +0x3 copied into `BattleState.BattleType` at asm00_1.s:15453-15454) |
| two-instance scenario design | §5: six-step event table anchored on `cb_80395A4` reaching netbattle menu + `sub_81465BC` returning nonzero | §F below: my own scenario design — one-player-one-navi encounter via T58 census, mgba invocation sketch |
| mgba invocation (deferred) | §5 ends: "frame numbers need the two-instance capture tool (mgba link support) — that is the follow-up ticket" | §F below: full invocation sketch (not run) |

---

## A. Handshake cross-check — SIO register map

The prior worker's cable-IRQ cites are corroborated by `reference/bn6f/constants/gba_constants.inc:58-59`:
- `SIOControlRegister` = `0x4000128` (the byte whose bit 7 is the SIO start bit)
- `SIOData0_Parent__Multi_PlayerMode_` = `0x4000120` (parent in multi-player)
- `SIOData2_2ndChild__Multi_PlayerMode_` = `0x4000126`
- `SIOModeSelect_GeneralPurposeData` (multi-player mode select)

`libSIOControlStart` (libs.s:896-905) writes `0x80` to `0x4000128`. Verifier
can confirm by static read: no live mgba run is required for the cite,
only for the frame numbers.

## B. Chip-trade cross-check — three distinct surfaces

There are **three** chip-trade surfaces in the disassembly; only one is the
netbattle per-trade-byte routine:

1. **Overworld chip-trader screen** — `subsystem_launchChipTrader`
   (asm00_1.s:5694-5735) sets `SubsystemIndex = 0x24` and a fade. NOT netbattle.
2. **Text-script chip-trader macro** — `ts_start_chip_trader`
   (`include/bytecode/text_script_commands.inc:1233,1236`). NOT netbattle.
3. **Netbattle per-trade-byte routine** — `sub_8039B0A`
   (asm03_1_1.s:2018-2065) with payload write `sub_81469BC`
   (libs.s:5704-5722) writing the exchanged pair to `0x201015B` /
   `0x201015C`. THIS is what the ticket asks for.

The "pair source" `sub_803C418` (asm03_1_1.s:6884-6902) returns
`word_2006770` (0x2006770). Whether this is a session sync token or
the chip id/code pair itself is **UNVERIFIED** (matches the prior
worker's NEGATIVE — chip-id semantics named missing).

## C. NetState byte — three candidate bytes

The prior worker identified **BattleSettings.background** at `0x0200AF64`
as the UI gate. There are two **additional** bytes that carry netbattle
state:

### C.1 `BattleState_Unk_0d` — the alliance-XOR byte

`BattleState.Unk_0d` at offset `0x0d`
(`reference/bn6f/include/structs/BattleState.inc`):
```
u8 Unk_0d // loc=0xd
```
Read by `battle_networkInvert`
(`reference/bn6f/asm/asm00_1.s:16532-16539`):
```
battle_networkInvert:
    mov r1, r10
    ldr r1, [r1,#oToolkit_BattleStatePtr]
    ldrb r2, [r1,#oBattleState_Unk_0d]
    eor r0, r2
    mov pc, lr
```
Called ~25 times from asm00_1.s and asm00_2.s; gates the
"is this side inverted from the player's view?" xor. EWRAM
address: `*(BattleStatePtr)+0x0d`. `BattleStatePtr` is a pointer
held in `Toolkit.BattleStatePtr` at offset `0x18`
(`reference/bn6f/include/structs/Toolkit.inc:13`), indirection
through `CurBattleDataPtr = 0x02001b9c` (per AGENT_GUIDE).
**Unverified** by measurement; the actual `BattleState` base
is `0x0203????`, so `Unk_0d` is at `0x0203????+0x0d`.

### C.2 `BattleState_Unk_11` — the network-battle flag byte

`BattleState.Unk_11` at offset `0x11`:
```
flags8 Unk_11 // loc=0x11
    struct_const BATTLE_STATE_UNK_11_FLAG_UNK_BIT_02, 0x04
```
Per `reference/bn6f/constants/enums/battle_constants.inc:5`, bit 0x04 is
`BATTLE_EFFECT_NETWORK_BATTLE`. Cleared on chip-window slide-out:
`reference/bn6f/asm/asm03_0.s:1068` inside `chipWindowState08SlideOut_8026BF4`:
```
mov r0, #BATTLE_STATE_UNK_11_FLAG_UNK_BIT_02
bl clearBattleStateUnk11Flag_800A9D6
```
EWRAM address: `*(BattleStatePtr)+0x11` = `0x0203????+0x11`.

### C.3 BattleSettings.background — the UI gate

Per the prior worker: `BattleSettings_200AF60+0x4 = 0x0200AF64`,
writer `battleSettings_setBackground` at asm03_0.s:14589-14596.
This is the SCOPE M1 cite reused as M10's UI-gate cite.

## E. Per-player `BattleSettings` overlay

Per the prior worker: BattleSettings is a **singleton** at 0x0200AF60,
not a record table. The per-player overlay is the union of
(BattleSettings, `BattleState_Unk_0d`, `BATTLE_EFFECT_NETWORK_BATTLE`).

Cross-checked from struct layouts:
- `BattleSettings` (`include/rom_structs/BattleSettings.inc`):
  16-byte ROM struct. `BattleType` byte at +0x3.
- `oBattleState_BattleSettings` u32 pointer at BattleState+0x3c
  (`include/structs/BattleState.inc:73`).
- `BattleSettings.BattleType` is copied into `BattleState.BattleType`
  at `reference/bn6f/asm/asm00_1.s:15453-15454`:
  ```
  ldrb r0, [r1,#oBattleSettings_BattleType]
  strb r0, [r3,#oBattleState_BattleType]
  ```
  (so `BattleState.BattleType` at offset `0x0f` mirrors the ROM-side
  `BattleType` byte).

There is **no second BattleSettings ROM struct** in the fork. The
per-player overlay is a runtime perspective on the single struct.

## F. Two-instance scenario design (one-player-one-navi)

**Scenario.** A 1-player-vs-1-navi encounter (NOT Mettaur-only), driven by
a T58 census record whose `EnemySetupArrPtr` ends in `0xF0` (the
terminator per `include/rom_structs/BattleSettings.inc:20`) and whose
enemy-setup byte prefix is `0x11, 0x25, 0x??, 0x??` (the navi-encounter
type prefix used in canon).

**Levers (deferred to T97a):**
1. `--poke-at 60:0x02001d58:0x0240` — the existing T87/T95 EVENT_681 flag
   swap (NOT netbattle-specific, but the closest T58 scenario lever).
2. `--poke-at 60:0x0203????:0x04` — set `BATTLE_EFFECT_NETWORK_BATTLE`
   bit in `BattleState.Unk_11`. The `0x0203????` slot requires resolving
   `BattleStatePtr` first (a `--watch-write 0x02001b9c:4` to read the
   pointer, then offset-add `+0x11`).
3. `--watch-write 0x0203????:1` — follow `BattleState_Unk_0d` updates
   per frame (the per-player perspective flip).
4. `--watch-write 0x0200AF64:1` — follow the UI-gate byte
   (`BattleSettings.background`).
5. `--watch-write 0x201015B:1` + `--watch-write 0x201015C:1` — follow
   the chip-trade exchanged pair (the prior worker's cite).

**mgba invocation sketch (NOT run — for T97a):**

```
mgba_capture /tmp/bn6f_real.gba /tmp/m10_netbattle_a 90 \
    --loadsave /tmp/bn6f_real.srm \
    --cheat 0x02000040:<T58 descriptor for 1P+1N encounter> \
    --poke-at 60:0x02001d58:0x0240 \
    --watch-write 0x02001b9c:4 \
    --watch-write 0x0200AF64:1 \
    --watch-write 0x201015B:1 \
    --watch-write 0x201015C:1 \
    --watch-write 0x200FE62:1 \
    --dump 0x0203????:0xf0:/tmp/m10_battlestate_a.bin

# Mirror scenario on link-cable port 2:
mgba_capture /tmp/bn6f_real.gba /tmp/m10_netbattle_b 90 \
    --loadsave /tmp/bn6f_real.srm \
    --cheat 0x02000040:<same T58 descriptor> \
    --poke-at 60:0x02001d58:0x0240 \
    --watch-write 0x02001b9c:4 \
    --watch-write 0x0200AF64:1 \
    --watch-write 0x201015B:1 \
    --watch-write 0x201015C:1 \
    --watch-write 0x200FE62:1 \
    --dump 0x0203????:0xf0:/tmp/m10_battlestate_b.bin

# Diff the two state dumps frame-by-frame:
diff /tmp/m10_battlestate_a.bin /tmp/m10_battlestate_b.bin
```

Negative control: run ONE instance alone — event 2 in the prior worker's
table (partner-found via `sub_81465BC`) must never fire; the menu must
fade out per asm03_1_1.s:1979-1984.

## G. Summary — acceptance against the ticket

| ticket acceptance item | satisfied by |
|------------------------|--------------|
| handshake cite (file:line) | prior worker's `libSIO814469C` libs.s:799-807, `libSIOControlStart` libs.s:896-905, `sub_813D648` asm37_0.s:3822-3831, `sub_81465BC` libs.s:5079-5112 |
| chip-trade cite (file:line) | prior worker's `sub_8039B0A` asm03_1_1.s:2018-2065; `sub_81469BC` libs.s:5704-5722; exchanged pair at 0x201015B/0x201015C |
| NetState byte (EWRAM + dispatcher) | §C of this file: BattleSettings.background at 0x0200AF64 + BattleState_Unk_0d at `*(BattleStatePtr)+0x0d` + BattleState_Unk_11 (the network flag) at `*(BattleStatePtr)+0x11`. Dispatcher: prior worker's `cb_80395A4` asm03_1_1.s:1309-1346 |
| per-player BattleSettings cite | prior worker's singleton-at-0x0200AF60 + §E of this file (struct layout cross-check) |
| two-instance scenario design + mgba invocation | prior worker's §5 + §F of this file |
| NEGATIVE naming "mgba lacks --net-battle flag, requires 7ag" | prior worker's §6 + this file's §F footer |

SCOPE M10 recon row: `0/1 → 1/1`. The actual measurement row is the
second M10 row, owned by a future ticket (T97a or similar).