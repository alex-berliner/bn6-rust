# T7y — the custom screen's open edge: canon's gauge→open chain vs our peeked 60-frame countdown

## Step 1 — baseline (HEAD f23a3eb, 2026-09-15)

`python3 tools/harness.py --only gunner --no-gallery` (clean build, CARGO_TARGET_DIR=/tmp/ct_t7y-open-edge):

- gunner isolated total **2105613** worst **38237** frames 130
- gunner integrated total **2105613** worst **38237** frames 130 (negative not blind, 2284867)
- fitted constants 19 (derived 429, peeked 145)

`python3 tools/trace.py record canon|rust battle_full` + `trace.py diff --align row:battle_full`:

- sequencer: **DIVERGES 273/540 frames**, first k=31 (canon frame 42) canon=0x20 rust=0x8
  (k = export row − 11). Rust spans: 0x08 0..~124, 0x24 ~125..171, 0x00 172..173,
  0x04 ..~233, 0x08 ..~404, 0x0C ..540 — our open is ~83 frames late, as the ticket says.
  (Ticket's "expect 2850534" is stale; see step 2.)
- first pixel-trace divergence in the diff: enemy_state_action k=0 (canon (4,10) vs rust (4,0)).

## Step 2 — the 2105613→2850534 drift: EXONERATED, and the ticket's expectation is stale

`e5591c42` is not a commit in this repo (`git cat-file -t e5591c42` → invalid object); it is the
name of T9l's capture-bin directory /tmp/bn-e5591c42. docs/worklog/F40a.md records F40a's own
baseline (which it calls the e5591c42 baseline) as `gunner isolated total 2105613 worst 38237
frames 130` — **identical to HEAD's measurement**. The 2850534→2105613 move is T9l's own landed
improvement: commit 424814d ("gunner's own backdrop seeds derived from canon's counters"),
parent d4dc9d6, moved gunner 2850534/38237/130 → 2105613/38237/130. The ticket was written
against scoreboard 1f81767 (pre-424814d). **No regression; the range is exonerated; HEAD is on
the good (2105613) side of the drift.**

## Step 3 — healthy canon watch (in progress)

## Step 3 — healthy canon watch (driver: docs/worklog/t7y_step3_watch.py, bins in /tmp/t7y_watches)

Four direct captures through harness.Side argv built in memory (canon battle_full 555f,
rust battle_full 572f, canon gunner 260f, rust gunner 260f) + one broadened canon gunner
capture (260f, watches 0x02035280:0x48, 0x02001b80:0x20, 0x02036822:2, 0x0203CA70:4).
All runs healthy (battle_full canon seq 0x1c->0x08 at 11; gunner canon HUD 0->0x4484 at 70 —
the documented battle start; no white spin).

**canon battle_full** (script Start@10,L@40,Start@70,A@80,...): gauge 0x020352A0 = 0x4000
static from capture 0 (full from the PAUSED state), cleared at 48 after the open. Sequencer
low byte: 0x1c->0x08 at 11, **0x08->0x20 at 42** (= k=31; the L@40 press lands at 40),
0x20->0x24 at 44, 0x24->0x00 at 144, 0x00->0x04 at 147, 0x04->0x08 at 207, 0x08->0x0C at 316.
**Press-gated**: the gauge word never fills during the battle (static full) and the open
follows the L press by 2 frames.

**canon gunner** (no press): gauge word 0x020352A0 = **0x0000 for all 260 captures**; sequencer
word 0x0203CA70 = **0x00 for all 260 captures** (never enters 0x08 — the 0x203CA70 machinery
does not run in this battle at all); joypad mirror flat after a capture-1 boot artifact.
Yet the custom window opens: HUD update word 0x020352C0 0x4484->**0x4485 at capture 152**,
draw word 0x020352C4 0x4484->0x4485->0x4085 (155) ->0x6085 (164), X displacement 0x02035292
ticks +0xc/frame 155..164 (the slide). The visible gauge bar is FULL (49/49 lit px on
y152 x12..60) from battle start (70) through 155, gone at 160 — drawn from a source that is
NOT 0x020352A0. No counter in eStruct2035280 (0x48 bytes watched), GameState 0x02001b80:0x20,
or the joypad mirror counts to the 152 open (the 0x020352B8 byte decrements 0x77/frame from 70
but wraps without correlation). **The gunner open is neither press-gated nor gated by the
documented gauge word — the ticket's premise is refuted on its own acceptance row.**

**rust battle_full** (TRC2 export, old build): no 0x20 frame at all — 0x08 -> 0x24 at export
133; gauge 0x4000 (fixture-seeded) cleared at 180. **rust gunner**: gauge fills 0xd/frame from
capture 105 (0x4000 would need ~1260 frames — the fill never completes in any row window).

## Step 4 — the asm chain (cites re-verified on disk; the ticket's asm03_0.s:540 and asm00_1.s:15203-15218 cites are WRONG)

- Fight body sub_800855E (asm00_1.s:11206-11277, the 0x04 state of dispatcher sub_80084F0
  over eBattleSequencerState_203CA70 — the table off_8008508 is indexed by the RAW BYTE as a
  byte offset: 0x00->sub_8008528, 0x04->sub_800855E, ... 0x14->sub_8008840, 0x18->sub_8008900):
  gauge += 0xd via AddToCustGauge_801DFB8 (asm00_2.s:29942, saturating at CUST_GAUGE_FULL
  0x4000, at eStruct2035280+oStruct2035280_CustGaugeValue); then
  isCustGaugeFullAndBattleLive_800A21C (asm00_1.s:**15305**-15324: sub_801DFE4() == 0x4000,
  no timestop, battle not over) answering 1 -> PauseBattle + state := 0x14 **in the same
  frame** (asm00_1.s:11266-11274). A twin body sub_80089CC repeats the pair at 11870-11878;
  a third call site at 12414. What canon waits on between full and open is **no count in the
  fight body** — the 0x14 chain (sub_8008840 -> sub_8008864: banner record 0x54 ->
  sub_8008894: 0x1e timer -> later sub-states, asm00_1.s:11597-11660) has its own timers we
  have not ported. The press edge (0x20 at L+2) is measured, not yet located in asm.
- The ticket's predicate cite asm00_1.s:15203-15218 is actually sub_800A1D0 (navi-stats
  byte 0x2c in {0x17,0x18} + battle flags bit 0x10 — a DIFFERENT predicate, asm00_1.s:15260-15298).

## Step 5 — NEGATIVE (two attempts, both reverted)

1. **GAUGE_PAUSE deleted** (auto edge latches and opens next tick; press edge honoured in
   release): window 0/0/16 and windowclose 0/0/40 held, but **cursor 3/3/170 ->
   16116/175/170** — the window rows' alignments pin the fitted 60-frame latency; the
   0x14 chain's real timers are unported, and retuning is forbidden. Reverted per the
   coordinator gate.
2. **Press edge only** (cfg!(debug_assertions) dropped; battle_full rust fixture gauge=0 +
   script L@40,A@170 so the press wins the race over the auto edge): the L@40 press at
   export 32 arrives ~32 frames BEFORE our fight branch goes live (export ~64, the
   intro_fade/intro_next gate — inferred from the old auto-open at k~=124 minus 60);
   the press is eaten, the window never opens, and the trace gets structurally worse
   (sequencer 253/540 with no 0x20/0x24 span; mm_timer 302/540; our 0x0C at k=217 vs
   canon 316). Catching the press needs L@~72 — a fitted count, forbidden.

**Verdict: NEGATIVE.** The open edge cannot land as canon's predicate without either a
fitted count (cursor pins GAUGE_PAUSE's 60; the press schedule needs a fitted frame) or a
real port of the 0x14 chain (whose identity as the gunner-row auto-open is itself refuted
by the gauge word reading 0x0000 through the open).

## What is unverified

- Whether canon's gunner open at capture 152 runs sub_8008840's 0x14 chain at all — the
  sequencer word 0x0203CA70 stays 0x00, so if the chain runs it is on a per-battle struct
  we have not located (CurBattleDataPtr-chased; not watched — capture budget spent).
- Where the gunner row's full-from-start gauge BAR is drawn from (not 0x020352A0).
- Whether step 2's 2105613 vs 2850534 difference is code (T9l 424814d's derived seeds) or
  the 357da2a re-cut — 424814d's own commit message claims the move, unre-verified here.

## Next worker

- The single highest-value measurement: --watch-write or a poke-bisect on the gunner canon
  capture around 145..155 to find WHAT writes 0x020352C0's bit 0x1 at 152 (the open), then
  read backwards to the FSM that owns it. The 0x020352B8 byte's odd 0x01->0x14 wrap at 189
  is also unexplained.
- The press edge works and is 2 lines (drop cfg!(debug_assertions) at src/battle.rs:2729);
  it is inert in every harness row (no script presses L/R buttons) but cannot beat the
  fixture-seeded auto edge in battle_full unless the fixture gauge=0 AND the fight branch
  is live by export 32 — fix the intro gate first (why is it ~64 with SKIP_INTRO?).
