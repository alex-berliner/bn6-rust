# Scenario `battlestart_gunner` (T9c, corrected by T9d) -- measured, NO harness row

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

## Why the battle never goes live (T9d's measured chain) -- replaces the
## refuted gate-chain narrative

The earlier T9 narrative -- sequencer state 0 gated by `sub_801483C`,
state 4 gated by `sub_801E754` over `dword_20352C0` bit 15 -- was
REFUTED by T9c's verifier: that bit is already clear in the poked
battle, the "sequencer=4 + `0x02036848:4`/`0x02036840:4`" poke makes 4
stick for 338 frames, never writes 8, and produces no damage across 5
button presses. T9d replaced it with watch-write measurements (logs in
`docs/trace/t9d/`, 5 capture runs, 200 frames each):

1. **Nobody writes `dword_203CA70` on EITHER battlestart scenario.**
   `--watch-write 0x0203ca70` on `battlestart` (record 7, the scenario
   T9's ticket wrongly called "working") and on `battlestart_gunner`
   (record 6) logs ZERO hits in 200 frames -- not even state 0's own
   setup stores. The two scenarios are indistinguishable at the
   sequencer; the roll outcome is not the difference. (`docs/trace/t9d/battlestart_watchwrite.log` vs `battlestart_gunner_watchwrite.log`: both
   only show the frozen custom-gauge writes at `0x020352A2` = 0x20,
   `0x0801BE7E` frame 0 and `0x0801DF8E` frame 69.) The only route in the
   repo where the sequencer moves is the hand-played PAUSED root
   (`docs/trace/t9d/live_paused_route.log`: already `0x1C` at load;
   on Start it writes `0x1C -> 8` at frame 11, PC `0x080083F8`, inside
   `sub_80083E4`).
2. **The chain, measured top-down.** The banner task `sub_800801C`
   (`asm/asm00_1.s:10422`, dispatch table `off_8008038` indexed by the
   byte `dword_203CA70` holds) is only ever called from `sub_800938A`
   (`asm/asm00_1.s:13126`, call at `13135`), the `oBattleState.Index_01 = 0x0C` handler of
   the battle-FSM dispatcher `sub_8009158` (`asm/asm00_1.s:12760`, table
   `off_80091BC` entry `0x0C` at `asm00_1.s:12818`). `eBattleState` is at
   `0x02034880` (`ewram.s:2572`), so `Index_01` is byte `0x02034881`.
   Watching `0x02034880:2` on `battlestart_gunner`
   (`docs/trace/t9d/gunner_fsm_index01.log`): `Index_01` 0->4 at frame 0
   (`0x08007974`), 4->8 at frame 66 (`0x08007A04`), the battle re-init
   wipes it, 0->4 at frame 152 (`0x08009270`), 4->8 at frame 153
   (`0x080092E8`) -- then NO write through frame 199. **It parks at
   0x08** (the earlier "the state-0 handler polls every frame" claim was
   wrong; the handler never runs at all).
3. **The branch that never falls through.** State 0x08's handler
   `sub_8009338` (`asm/asm00_1.s:13054`) gates on
   `bl sub_8026A28; cmp r0,#0; beq locret_8009388`
   (`asm/asm00_1.s:13065-13067`). That `beq` is taken every frame, so
   `Index_01` never reaches `0x0C` and `sub_800801C` never dispatches.
4. **Why the gate never opens.** `sub_8026A28` (`asm/asm03_0.s:761`)
   dispatches on `eS20364C0`'s top FSM byte `JumpOffset00`
   (`0x020364C0`, `ewram.s:2676`): state 0 `sub_8026A50` returns 0 (and
   self-advances to 4), state 4 `custMenuMainMaybe_8026A88` always
   returns 0, state 8 `sub_8026A6C` returns `Unk_04` (+4, already 1
   since init -- written by `0x080268F2`, see the chip-window log).
   Watching `0x020364C0:6` (`docs/trace/t9d/gunner_chipwindow.log`):
   the chip-window controller inits at frame 154 (`JumpOffset00` 0->4
   at `0x08026A66`), slides the window in frames 155-164 (`Unk_02` =
   0x78 at `0x08026B36`, the 0x78/0xC countdown, `JumpOffset01` -> 4 at
   `0x08026BE2` on the tenth call) -- then parks in top-state 4 forever.
   The 4->8 write never fires, and its author is not in the identified
   asm: no handler of `custMenuMainMaybe_8026A88` (`asm/asm03_0.s`
   760-1300) stores to `[r5]`.

**What the poked battle is missing (T9d step 3's answer):** neither a
value the roll poke left wrong nor any byte of record 6's setup
`byte_80B5347` -- the record-7 `battlestart` dies identically, so the
stop is upstream of anything the two records distinguish. It is the
chip-window controller's top-state advance `eS20364C0.JumpOffset00`
(0x020364C0) 4 -> 8, the "window ready" signal `sub_8026A28` gates on.
Leading (UNVERIFIED) hypothesis for the signal's source: the
`JumpOffset01 = 0x40` path (`sub_8026CCC` -> `sub_8027548` via
`custMenuMainMaybe`, `asm/asm03_0.s` `loc_8026CE6` branch), which fires
only when `sub_802A220` returns != 0xff -- i.e. when the window has
data (a chip hand) to present; a battle whose hand was never drawn
would park forever. Next ticket's cheap test: `--dump` the chip hand in
both routes, or `--poke-at` `0x020364C0 = 8` (one capture) and watch
`dword_203CA70` and `Index_01` move.

## The open contract question (T9b's, still for the user)

Canon record 6 fields TWO enemies (Mettaur + Gunner). This branch implements
the per-slot `enemy_kind` form (FIXTURE.md +5, two bits per slot) rather
than the hide/zero-the-Mettaur technique; a row that compares only the
Gunner slot would need the other.

## T9g — 700-frame settle and panel-row probe (NEGATIVE on both)

**Result.** no attack event in 700 frames on either route; the row
ticket that follows is **not** writable aligned by a measured event —
the next stop is the AI handshake byte the `is_MegaMan_in_range?`
predicate keys off, not the heartbeat cycle and not the panel row.
Raw logs in `docs/trace/t9g/`.

### Step 1: 700-frame settle (`--poke-at 165:0x020364C0:0x08` in place)

Watched on `battlestart_gunner` from f0 to f699 with the T9e trigger
poke (`eS20364C0.JumpOffset00 = 8`, ewram.s:2676) armed:

- 0x0203ab68:3 (slot1 CurState/CurAction/CurPhase; T1 oracle field
  `enemy_state_action` 0x0203ab68+0x08/+0x09)
- 0x0203ab80:8 (slot1 +0x20 Timer/Timer2, +0x24 HP, +0x26 MaxHP)
- 0x020352a0:4 (custom gauge `eStruct2035280+0x20`, asm00_2.s:29892)
- 0x020352a2:2 (gauge +2)
- 0x0203ca70:4 (`dword_203CA70`, ewram.s:3040)

Movement (raw: `docs/trace/t9g/settle_watch_700.log`):

- f69: slot1 BattleObject materialises with `CurState=0x04 /
  CurAction=0x00 / CurPhase=0x00`, HP 0x003c, MaxHP 0x003c.
- f118: CurPhase → 0x04; Timer at 0x0203ab80 arms at 0x0010.
- f119..149: Timer counts down 0x10 → 0x01; byte-1 of the u32 timer
  alternates 0x02 ↔ 0x01 each frame (HP / MaxHP unchanged).
- f150: CurPhase 0x04 → 0x08.
- f151: CurAction 0x00 → 0x01; CurState 0x04 — **parked** (T9e doc
  writes "CurState=0x01/CurAction=0x04"; measurement here is the byte
  order swapped, the values match).
- f166: `dword_203CA70` 0x00 → 0x04000000 (trigger poke arms; the
  sequencer advances as expected from T9e's proof).
- f167..f699 (533 frames): parked; HP 0x003c / gauge 0x00200000 /
  sequencer 0x04000000 — all unchanged.

Per-virus heartbeat log (every 234th frame, the AI candidate for
"act" per `sub_8112D9C`'s 234-frame cycle, asm32.s:9735; ticket's
"act now" hypothesis):

- f234 — unchanged from f151's parked state (0x040100 at 0x0203ab68,
  0x020000003c003c00 at 0x0203ab80, gauge 0x00200000, sequencer
  0x04000000). **Empty heartbeat table for this fixture.**

### Step 2: panel-row-3 probe (`--cheat 0x0203a9c3:3` + trigger poke)

Same 700-frame watch with MegaMan's PanelY (`BattleObject+0x13`,
ewram.s:2572) cheated to 3 every frame, putting MegaMan and the
Gunner (slot1 PanelY=3) on the same row — the verifier's named
condition for the Gunner's `is_MegaMan_in_range?` predicate.
Raw: `docs/trace/t9g/settle_watch_700_row3.log`.

Identical trajectory to step 1: same f69 spawn, same f118..150
countdown, same f151 parked-state transition, same f166 sequencer
0x00 → 0x04000000, same f167..f699 frozen values. **No attack event
in 700 frames.** The panel-row-3 cheat does NOT unstick the Gunner.

### Step 3: RNG cadence at 0x020013f0 (`ePrimaryRngSeed`, ewram.s:262)

Watched 700 frames, raw: `docs/trace/t9g/rng_watch_700.log`. Unique
seed values per checkpoint (frames where the seed CHANGED from the
previous frame):

| frame | cumulative unique draws |
|---|---|
| f0   | 1   |
| f100 | 100 |
| f300 | 300 |
| f500 | 500 |
| f699 | 637 |

700 frames produced 637 unique seed values — the AI loop IS drawing
the RNG at roughly 1 draw / frame. For comparison, T7i's parallel
measurement on `battle_full` counted **10 / 540** draws (one every
~54 frames). The draw rate is NOT frozen: the loop is calling
`GetRNG`, just not acting on its result.

### What this rules out

Both gates named by T9g's `**Why.**` are empty:

- (a) `sub_8112D9C`'s 234-frame heartbeat — f234 finds no movement.
  The heartbeat table is empty for this fixture. (Two full cycles
  would need f468 + f702; the 700-frame window catches the first one
  and falls one cycle short of the second. Even if the second
  cycle's "act now" fires at f702, the row ticket would have to align
  at f702+, well past this watch's reach.)
- (b) MegaMan's panel row — the row-3 cheat does not unstick.
- (c) The RNG cadence is alive (~1/frame), so the gate is not a
  GetRNG draw count.

The next stop is the AI handshake byte the `is_MegaMan_in_range?`
predicate keys off — a column check, a `MegaMan_Alive` flag, an
`AIAttackVars` field, or a panel-direction check that the panel row
alone does not satisfy. Measuring which sub-condition fails is the
row ticket's first move: it needs that predicate unblocked before it
can land. (The 700-frame watch here also cannot rule out a f702+
event, but two cycles of 234 still leaves no plausible "act now" if
f234 itself is silent.)

### What is unverified

Whether `sub_8112D9C`'s heartbeat (`AIAttackVars.Unk_10` decrementing
from `Unk_0c = 0xEA = 234`, asm32.s:9735-9751) is the heartbeat to
count from at all on this fixture — the engine has an earlier
per-virus heartbeat that may run before the AIAttackVars arm; whether
the row-check chain has a panel-row-independent failure mode that
the cheat alone does not satisfy.
