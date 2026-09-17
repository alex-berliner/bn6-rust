# Netbattle recon (M10) — T97, 2026-09-17

Recon-only. No src/ change, no capture, no harness row: `reference/bn6f` (read-only) is the
evidence base. The two-instance capture path (`mgba_capture.c`) does not exist yet, so every
frame number below is defined as an EVENT + watch address to align on, not a measured frame —
measuring them is exactly the follow-up ticket.

## 1. Link handshake (SIO/Cable driver + wireless handshake)

The serial stack is split: a cable/SIO driver in `reference/bn6f/asm/libs.s` and a Wireless
Adapter ("rfu") stack, also in libs.s. Both are installed at boot.

- Boot hookup: `reference/bn6f/asm/start.s:222` (`ldr r1, off_8000298 // =sub_3005E2C+1`,
  pool entry at start.s:230) calls the IRQ installer at startup (`docs/decomp/start.c:100`).
- IRQ installer `sub_3005E2C` (`reference/bn6f/asm/asm38.s:358-391`): installs interrupt
  0x18 (serial) → `libSIO814469C+1` (asm38.s:374) and interrupt 0x1c → `sub_81446AC+1`
  (asm38.s:377), with IME backed up/disabled around the install.
- Serial IRQ `libSIO814469C` (`reference/bn6f/asm/libs.s:799-807`): stops/reloads timer 3
  (libs.s:802) then `bl libSIOControlStart` (libs.s:803).
- `libSIOControlStart` (`reference/bn6f/asm/libs.s:896-905`): sets the SIO start bit
  (0x80) in SIOControlRegister (0x4000128) — this is the SIO transfer arm.
- Mode setup for multi-player cable: `reference/bn6f/asm/libs.s:84-110` writes
  `SIOModeSelect_GeneralPurposeData` / `SIOControlRegister` /
  `SIOData0_Parent__Multi_PlayerMode_` / `SIOData2_2ndChild__Multi_PlayerMode_`
  (registers 0x4000120-0x4000126; `constants/gba_constants.inc:58-59`).
- Wireless handshake poll `sub_813D648` (`reference/bn6f/asm/asm37_0.s:3822-3831`):
  `bl rfu_REQBN_softReset_and_checkID` (asm37_0.s:3827), returns true iff the result is 1 —
  i.e. the wireless adapter answered the soft-reset/ID check. This is the routine whose
  success ARMS the netbattle session flow.
- Wireless API init `sub_81465BC` (`reference/bn6f/asm/libs.s:5079-5112`):
  `rfu_initializeAPI` (libs.s:5087) + `rfu_setTimerInterrupt`; returns nonzero while the
  RFU session is alive. Session counters inited by `sub_8146588`
  (`reference/bn6f/asm/libs.s:5049-5077`: byte_200FE80=0, byte_2010160=0x20,
  byte_200FFE4=1, byte_2010164=1, word_200FE50=0xf0).

Entry condition (cable): IRQ-driven from boot — the driver runs whenever the game writes
the start bit via `libSIOControlStart`. Entry condition (wireless): the netbattle menu state
machine polls `sub_813D648` (adapter present?) then `sub_81465BC` (partner connected?).

## 2. Netbattle session state machine (drives handshake + chip trade)

- Dispatcher `cb_80395A4` (`reference/bn6f/asm/asm03_1_1.s:1309-1346`): runs on struct
  `eS200A290`, dispatches on the index byte at +0x00 through table `off_80395C8` with six
  states: 0x00→sub_80395E4, 0x04→sub_8039630, 0x08→sub_8039658, 0x0C→sub_80399CE,
  0x10→sub_803A690, 0x14→sub_803B160 (asm03_1_1.s:1337-1343). Inner steps sub-dispatch on
  a second byte at +0x01.
- Handshake steps: `sub_8039AB8` polls `sub_81465BC` (bl at asm03_1_1.s:1977); nonzero =
  connected → inner state 8, zero = fade out (asm03_1_1.s:1976-1996). `sub_8039AE4` polls
  `sub_813D648` (bl at asm03_1_1.s:2020); zero = no adapter → fade, nonzero → proceed
  (asm03_1_1.s:1999-2022).

## 3. Chip-trade step and the exchanged data fields

- `sub_8039B0A` (`reference/bn6f/asm/asm03_1_1.s:2018-2065`) is the exchange step:
  session init `sub_8146588` (bl asm03_1_1.s:2021), NI send setup `sub_814695C`
  (bl 2024), value fetch `sub_803C418` (bl 2025), payload write `sub_81469BC`
  (bl 2030), liveness poll `sub_81465BC` (bl 2031).
- `sub_814695C` (`reference/bn6f/asm/libs.s:5644-5681`): arms an 8-byte NI send ring at
  unk_200FE60 and sets the send-pending flag byte_200FE62.
- **Payload write site** `sub_81469BC` (`reference/bn6f/asm/libs.s:5704-5722`): appends a
  16-bit value to the NI send struct `unk_2010150` — low byte → `byte_201015B`
  (+0x0b, libs.s:5713), high byte → `byte_201015C` (+0x0c, libs.s:5715). This
  (+0x0b/+0x0c of 0x2010150) is the exchanged pair's field.
- Pair source `sub_803C418` (`reference/bn6f/asm/asm03_1_1.s:6884-6902`): returns u16
  `word_2006770` (0x2006770), seeded from GetRNG by `sub_803C40C`
  (asm03_1_1.s:6878-6883). **Unproven:** whether this RNG-seeded u16 is itself the traded
  chip id/code pair or a session sync token; the chip-selection UI step that would place a
  chip id/code into the payload was not located within budget. See worklog NEGATIVE.

## 4. Netbattle UI state field

- Struct: `BattleSettings_200AF60` — a singleton at 0x0200AF60, not a table
  (getter `getBattleSettings_200AF60`, `reference/bn6f/asm/asm03_0.s:14538-14542`).
- Field: `BattleSettings.background`, byte at **BattleSettings+0x4** = 0x0200AF64.
- Writer: `battleSettings_setBackground` (`reference/bn6f/asm/asm03_0.s:14589-14596`),
  `strb r0,[r1,#0x4] // BattleSettings.background` at asm03_0.s:14594 (the SCOPE M1 cite).
- Visible callers: asm03_0.s:14617 (battleSettings_802D2B2) and asm33.s:16529
  (map-script battle init, near the initBattleStructsAndVram_80071D4 call at
  asm33.s:16406). **NEGATIVE (named):** no netbattle-named symbol exists anywhere in the
  fork (word-boundary grep for netbattle|versus|trade over asm/ finds only the in-battle
  ChipTrader, asm00_1.s:5694 and asm03_2.s:6901); the caller that arms +0x4 with the
  netbattle value — i.e. which canon event (entering the link battle from the session
  machine) performs the write — is the missing cite. Follow-up: break on 0x0200AF64
  writes during a two-instance capture and cite the writer.

## 5. Two-instance scenario design (event-anchored; frames TBD by capture)

Alignment events and watches for the first two-instance rows (both sides run the same ROM;
parent/child roles decided by the wireless handshake):

| # | moment | event / watch | cite |
|---|--------|---------------|------|
| 0 | boot (pre-frame-0) | IRQ install happens at startup, before any frame | start.s:222; asm38.s:358-391 |
| 1 | handshake arm | netbattle menu state reached: `cb_80395A4` dispatches; `sub_813D648` returns 1 | asm03_1_1.s:1309-1346; asm37_0.s:3827 |
| 2 | partner found | `sub_81465BC` nonzero → inner state 8 on eS200A290+1 | asm03_1_1.s:1977; libs.s:5087 |
| 3 | **SIO-init frame** (handshake completion) | first frame `libSIOControlStart` sets 0x80 in SIOCNT — watch 0x4000128 bit 7 on both instances | libs.s:896-905 |
| 4 | **chip-trade window** | frames where `sub_8039B0A` runs: watch 0x201015B/0x201015C (payload pair) change, and send flag 0x200FE62 | asm03_1_1.s:2018-2065; libs.s:5713,5715 |
| 5 | battle handover (UI armed) | write to BattleSettings+0x4 (0x0200AF64) ≠ 0 — netbattle UI/backdrop gated on it | asm03_0.s:14594 |
| 6 | battle start | battle_init subsystem (GameState 0x02001b80 → 8) reached with the netbattle background value set | asm33.s:16405-16406; asm03_0.s:14538-14542 |

Proposed row shape: record both instances with independent `--watch 0x4000128:2` /
`--watch-write 0x201015B` / `--watch-write 0x200AF64`, align each side on its own first
SIOCNT-start-bit frame (event 3), compare frames [3-10] (handshake tail), [4-window]
(trade), and [5..battle] (UI arm) across instances. Trace fields: 0x201015B/C (pair),
0x200FE62 (send flag), 0x0200AF64 (UI gate). Negative: run one instance alone — event 2
must never fire (`sub_81465BC` stays 0 → fade path asm03_1_1.s:1979-1984).

## 6. Summary

Handshake: cable IRQs installed at boot (start.s:222 → asm38.s:358-391 → libs.s:799-807
→ libs.s:896-905 SIOCNT start bit); wireless handshake `sub_813D648` (asm37_0.s:3827,
rfu softReset+checkID) polled by session machine `cb_80395A4` (asm03_1_1.s:1309).
Chip trade: `sub_8039B0A` (asm03_1_1.s:2018-2065) writes the exchanged 16-bit pair to
unk_2010150+0x0b/+0x0c (libs.s:5713-5715). UI state field: BattleSettings.background at
BattleSettings_200AF60+0x4 = 0x0200AF64, writer asm03_0.s:14594. Scenario: table above;
frame numbers need the two-instance capture tool (mgba link support) — that is the
follow-up ticket.
