# Scenario `battlestart_gunner` (T9c) -- measured, NO harness row

The canon recipe exists (`tools/states.py` `battlestart_gunner`, T9b's
frame-60 iCurrFrame lever) and the fixture can field its enemies
(`enemy_kind` packed per slot, kind 1 = Gunner), but **no harness row is
landed for it**: the canon side of this battle never reaches an attack
(measured, below), so the ticket's "aligned by its first attack event" has
no event to align by. This file records the measurements so the next ticket
does not re-derive them.

## What reproduces (verified 2026-09-14, this ticket)

- Lever: `--poke-at 60:0x0200a210:0x371` (iCurrFrame 0x372 -> 0x371) on the
  `battlestart` recipe's own roll pokes makes the chosen BattleSettings
  pointer `0x02001b9c` read `0x080b4bd8` (record 6) from frame 60 on --
  never `0x080b4be8` (record 7, the natural 3-Mettaur pick).
- Slots populate at capture frame 148 (= frame 69 from the saved state):
  slot0 Mettaur panel (5,2) HP 0x28 (object `0x0203aa88`), slot1 Gunner
  NameID 0x85 panel (6,3) HP 0x3c (`0x0203ab60`), slot2 empty. MegaMan
  (2,2) HP 0x64. `ePrimaryRngSeed` at state load: `0x14ca0f46` (the same
  value the `opening` row's descriptor carries -- the pre-battle history is
  identical). `eBGScrollCBCounters` read 0/0 at load: the state IS battle
  frame 0.

## Why the battle never goes live (the blocker, all measured)

Through 900 frames from the state: banner sequencer `dword_203CA70` stays
0; both viruses sit in state/action 0x0104 (spawned, idle) from frame 151;
no movement, no MegaMan input, no damage. The same stuckness T1 measured
for the 3-Mettaur `battlestart` -- it is the roll-poke route's, not record
6's. Pokes that do NOT unstick it (all tried): sequencer `0x0203CA70` = 8
or 0x18 (the value sticks, the FSM never advances); custom gauge
`0x020352A0` = 0x4000 (reverts after ~54 frames). No natural-encounter
route exists either: direction cycling without the roll pokes never leaves
the map (SubsystemIndex stays 4).

## The disassembly answer (who writes the sequencer, what gates it)

Read-only pass on `reference/bn6f` (the bounded hunt):

1. `sub_800840C` (sequencer state 0's handler, `asm/asm00_1.s:10947`)
   writes the FIRST `4` into `dword_203CA70` (`str r0,[r5]` at
   `loc_8008438`) -- gated by the banner-queue engine `sub_801483C`
   (`asm/asm00_2.s:12741`, queues at `dword_20367F0`, sources copied from
   `byte_203F558`/`byte_203F658` by `sub_80147E4`) returning 0.
2. State 4's handler `sub_8008064` (`asm/asm00_1.s:10465`) writes the `8`
   (`loc_80080AE` tail) -- gated by `sub_801E754` (`asm/asm00_2.s:31012`)
   returning 0, which happens exactly when the battle-HUD element mask
   `dword_20352C0` bit 15 is CLEAR (mask & 0x8000 == 0).
3. State 8's handler `sub_80080D2` calls `UnpauseBattle`: the battle is
   live (this is F5b's known state 0x08).

In the poked battle the battle FSM (`eBattleState.Index_01`) does reach the
dispatcher (`sub_8009158` runs from frame ~153), so the state-0 handler
polls every frame -- it is the banner-queue engine that never completes.
What fills `byte_203F558`/`byte_203F658` on a NATURAL encounter (the
map-side handover the forced roll may skip) was not pinned within the
hunt's budget. **Untested poke candidate** for a future pass: sequencer
`0x0203CA70` = 4 plus HUD mask `0x020352C0` bit 15 cleared, which enters
state 4 with its own gate already open and lets `sub_80080D2`'s entry run
naturally. Forcing 8 directly was tried and does not work (see above).

## The open contract question (T9b's, still for the user)

Canon record 6 fields TWO enemies (Mettaur + Gunner). This branch implements
the per-slot `enemy_kind` form (FIXTURE.md +5, two bits per slot) rather
than the hide/zero-the-Mettaur technique; a row that compares only the
Gunner slot would need the other.
