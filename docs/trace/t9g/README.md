# T9g trace logs — `battlestart_gunner` 700-frame settle and panel-row probe

Three captures on `/tmp/bn6f_real.gba` from `/tmp/battlestart_gunner.state`
(T9c's recipe) with the T9e trigger poke `--poke-at 165:0x020364C0:0x08`
(`eS20364C0.JumpOffset00`, ewram.s:2676; the only frame after the
chip-window controller parks in state 4 where the write is not
overwritten by controller init at f154):

| File | Frames | Pokes / cheats | Address set watched |
|---|---|---|---|
| `settle_watch_700.log` | 700 | `--poke-at 165:0x020364C0:0x08` | `0x0203ab68:3` (slot1 CurState/CurAction/CurPhase) · `0x0203ab80:8` (slot1 +0x20 timer + +0x24 HP + +0x26 MaxHP) · `0x020352a0:4` (custom gauge) · `0x020352a2:2` (custom gauge +2) · `0x0203ca70:4` (`dword_203CA70`, ewram.s:3040) |
| `settle_watch_700_row3.log` | 700 | `--poke-at 165:0x020364C0:0x08` + `--cheat 0x0203a9c3:3` (MegaMan PanelY → row 3 every frame) | same as above |
| `rng_watch_700.log` | 700 | `--poke-at 165:0x020364C0:0x08` | `0x020013f0:4` (`ePrimaryRngSeed`, ewram.s:262) |

All three captures ran with the T9e trigger poke (the same one T9e used
to unblock `dword_203CA70`/`Index_01`); the row-3 cheat forces MegaMan's
panel-row byte (`BattleObject+0x13`, ewram.s:2572) to 3 every frame, on
top of the trigger poke.

## Per-frame movement, settle_watch_700.log (T9g step 1)

First movement summary (run `python3 /tmp/analyze_watch.py`):

- f69: slot1 BattleObject materialises at 0x0203ab68 with CurState=0x04
  (`CUR_STATE_UPDATE`), CurAction=0x00, CurPhase=0x00; `0x0203ab84` HP
  = 0x003c (60), MaxHP = 0x003c; timers zero.
- f118: CurPhase 0x00 → 0x04; `0x0203ab80` (Timer) arms at 0x0010.
- f119..149: Timer counts down `0x10 → 0x01`, alternating with byte-1
  swaps `0x02` ↔ `0x01` (the high byte of the u32 timer at 0x0203ab80
  is a separate counter being toggled alongside; HP/MaxHP unchanged).
- f150: CurPhase 0x04 → 0x08 (CUR_PHASE_HIDE or analogous — not the
  234-frame heartbeat).
- f151: CurAction 0x00 → 0x01; CurState 0x04 (UPDATE) — **the parked
  state** the T9e doc references (T9e's text writes "CurState=0x01/
  CurAction=0x04"; measured here is CurState=0x04 / CurAction=0x01 —
  the swap is the T9e doc's order, the measurement is what the engine
  actually stores).
- f151..f699: parked unchanged — 549 frames of CurState=0x04 /
  CurAction=0x01 / CurPhase=0x00; HP 0x003c, MaxHP 0x003c unchanged;
  Timer 0x0000 (the 0x01/0x02 byte wobble above has stopped).
- f166: `0x0203ca70` 0x00000000 → 0x04000000 (the trigger poke at f165
  fires; sequencer reaches the `0x04` chip-window-waiting state from
  `0x00`).
- f167..f699: `0x0203ca70` stays 0x04000000 (sequencer parked).
- f0..f699: `0x020352a0` stays 0x00200000, `0x020352a2` stays 0x0020 —
  gauge never moves.

**Per-virus heartbeat log (every 234th frame)**: the only candidate in
the 0..699 window is **f234**, where the watch values are unchanged
from f151's parked state: `0x0203ab68:3 = 0x040100`,
`0x0203ab80:8 = 0x020000003c003c00`, gauge `0x00200000`/`0x0020`,
sequencer `0x04000000`. **Empty heartbeat table**: the AI candidate
for "act" at the 234-frame mark does not fire on this fixture.

## Per-frame movement, settle_watch_700_row3.log (T9g step 2)

Identical trajectory through f151 (`CurAction 0x00 → 0x01`, parked at
0x040100); identical f166 sequencer transition `0x00 → 0x04000000`;
HP unchanged at 0x003c; gauge unchanged. The `0x0203a9c3:3` cheat
forces MegaMan's PanelY to row 3 (his own row) every frame, putting
MegaMan and the Gunner on the same row — the verifier's named
condition for the Gunner's `is_MegaMan_in_range?` predicate. **No
attack event in 700 frames; Gunner still parked at 0x040100 with HP
0x003c.**

## Per-frame movement, rng_watch_700.log (T9g step 3)

The RNG seed at 0x020013f0 changes value on **637 of the 700 frames**
(63 frames where the seed holds — those line up with vblank/idle
frames where the engine does not draw). Cumulative unique-value
counts at the checkpoints named by the ticket:

| frame | unique RNG values seen |
|---|---|
| f0   | 1   |
| f100 | 100 |
| f300 | 300 |
| f500 | 500 |
| f700 | out-of-range — first frame = 0; f699 carries the last sample |
| f699 | 637 (the total at frame 699) |

For comparison, T7i's parallel measurement on `battle_full` counted
**10 / 540** RNG draws (one every ~54 frames). On this fixture the
draw rate is roughly **1 / frame** — the AI loop IS pulling RNG, not
frozen. The gate is therefore upstream of `sub_8112D9C`'s 234-frame
cycle: the Gunner is being asked, repeatedly, "is MegaMan in range?
act now?", and the answer coming back is "no, stay parked".

## Result (one line of mechanism, one line of unverified)

**Mechanism.** The `battlestart_gunner` fixture, even with the T9e
trigger poke applied at f165 (`eS20364C0.JumpOffset00 = 8`,
ewram.s:2676) AND MegaMan's PanelY cheated to row 3 every frame,
fails to fire a Gunner attack event in 700 frames. The Gunner's
BattleObject at `0x0203ab68` parks at `CurState=0x04 / CurAction=0x01 /
CurPhase=0x00` (T9e's parked state, byte-order swapped in the doc)
from f151 onward, with HP 0x003c unchanged, gauge 0x00200000
unchanged, sequencer parked at 0x04000000 from f166. The 234-frame
AI heartbeat candidate at f234 finds no movement.

**Next stop.** With both (a) the 234-frame settle window and (b) the
panel-row-3 condition both producing no movement, and (c) the RNG
showing ~1 draw/frame (637 / 700, vs T7i's 10 / 540), the gate is
neither time nor RNG nor the row-check chain: it is the
`is_MegaMan_in_range?` predicate returning false on a row whose
CheatY=3 cheat has the wrong semantics, OR an AI handshake byte that
the row-3 condition does not satisfy (e.g. a panel-column check, or a
`MegaMan_Alive` flag, or an AIAttackVars field that the panel row
alone does not unstick). Verifier-confirmed the panel row 3 is the
condition to satisfy; measuring which sub-condition inside the
predicate actually fails is the row ticket's first move (it needs the
panel row settled before it can land).

What is **unverified**: (i) whether the Gunner ever attacks
MegaMan at all on this fixture's panel layout (column 6 vs MegaMan's
column 2 — the row check is necessary but not necessarily
sufficient), and (ii) whether `sub_8112D9C`'s heartbeat (`AIAttackVars.
Unk_10` decrementing from `Unk_0c = 0xEA = 234`, asm32.s:9735) is the
right heartbeat to count from at all, vs some earlier per-virus
heartbeat. The 234-frame log entry being empty does NOT prove the
cycle is irrelevant — only that it does not fire on this fixture with
the current row.