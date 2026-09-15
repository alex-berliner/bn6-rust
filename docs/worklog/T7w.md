# T7w — battle end as canon's per-state counts (NEGATIVE — measured, no code change)

Ticket: name the layer of the integrated rows' 16-px band, then retire the fitted
RESULTS_DELAY=110. Branch `wt/t7w-end-counts`, HEAD 1163616. **Outcome: NEGATIVE.**
Step 2/3 numbers below refute the ticket's mechanism premise ("one mechanism — when the
results window's show is reached in battle context — gates three rows"); per the ticket's own
rule ("a value that only holds at one row's window is a NEGATIVE, not a fix") no code was
changed, RESULTS_DELAY stays, AUDIT-6 keys stay.

## Step 1 — baseline (`--only <row> --ui integrated --no-gallery`, HEAD)

| row | total | worst | frames | negative |
|---|---|---|---|---|
| field | 158926 | 5597 | 40 | not blind (261025) |
| warp | 40628 | 11744 | 30 | not blind (129960) |
| buster | 54672 | 12977 | 28 | not blind (130248) |
| chip-use | 275307 | 18091 | 30 | not blind (283978) |

fitted constants: 19 (derived 429, peeked 145). Note: the ticket expected buster "no longer on
the failing list" — it still reads 54672/12977 (T7e/F38b numbers), so its AUDIT-6 key stays.

## Step 2 — layer split (both sides identical flags, in-memory extra swap, harness untouched)

Driver: `docs/worklog/t7w_step2_split.py` (wraps the rows' Side.extra; no harness.py edit).

| row | --only-bg 3 | --only-bg 1 | --disable-obj | full |
|---|---|---|---|---|
| field | 54556 / worst 2501 (flat 1126 k=5..23, rises ~176/frame k=24..32, flat 2501, decays to 2316) | 842344 (flat ~20k — NOT layer-symmetric: our backdrop is on BG0, canon's on BG1, harness.py:1854) | 159187 / 5605 | 158926 |
| warp | 40628 / 11744 — byte-identical to full: 0 through k=23, then 1917/3837/5757/7677/9696/11744 | 0 | 40628 (identical) | 40628 |
| chip-use | 44306 / 12797 — 0 through k=23, then 2090/4186/6282/8378/10573/12797 | 443520 (flat ~15k) | 250417 / 17695 (band still present) | 275307 |

**The band lives on BG3** on all three rows (warp's BG3-only counts are pixel-identical to the
full row; BG1 and OBJ carry none of it). Not BG1 → the NEGATIVE branch "band on BG1" does not
fire; this is the report the ticket asked for anyway. Band region at its first frame (warp k=24,
the only row whose k=24 diff is pure band): **x 0..15, y 24..143** — one 16-px column, full
window height, left edge (F36c's reading confirmed by diff mask on the step-3 captures:
1917 px = 16×120).

## Step 3 — sequencer watches (canon 0x0203ca70:4, ours TRC2 0x02000080+42 = 0x020000aa:2)

Driver: `docs/worklog/t7w_step3_watch.py`. The rust side needs FLAG_TRACE (0x80) set in the
fixture for the TRC2 block to be written at all (T1b: picture unchanged, only the 64 stores);
without it the watch reads 00 everywhere (first attempt did exactly that — see "Dropped
attempts"). Canon side flags untouched.

Canon (all three rows, identical sterile+DELETE+Start@10 config): 0x1c→0x08 at capture 11,
**0x08→0x0C at capture 47**; at the band's first frame (canon 154 = k=24) state = **0x0C**;
first slide tick at canon 154 → **107 frames after the edge** (matches F34's slide 154..167 and
the asm chain: sub_80081A4's 94-count → GameState+0x14 hand-off → sub_80094B6 → sub_802BD60 →
sub_802BE36's +2 columns).

Ours (rust watch, full capture scanned for transitions):

- field: `00→0C at capture 8` (RESOLVE_OVER resolves on battle frame 0; no 0x08 frame is ever
  exported), 0x0C at the band frame (rust 140). Our slide runs rust 140..153 = entry+132, in
  sync with canon's aligned 154..167 — the fitted RESULTS_DELAY=110 (+ the show path's internal
  lag) lands it there.
- warp: `00→08 at capture 8`, then **0x08 for the whole 121-frame capture** — the end sequence
  is never entered. At the band frame (rust 83) we are in the fight state while canon is 107
  frames into 0x0C.
- chip-use: same — `00→08 at capture 8`, 0x08 through all 180 frames; band frame rust 126.

Why ours never enters 0x0C on warp/chip-use: the `decided` gate (src/battle.rs:2512-2520)
requires FLAG_RESOLVE_OVER or a non-empty enemy list; WARP_ZERO/CHIPUSE_ZERO/BUSTER_ZERO are
plain ZERO_ENEMY (flags 0x11, harness.py:1564-1572) and enemies=0, so `dissolve_in` is never
armed and the sequencer stays in SEQ_08 forever. Fixing that needs a descriptor flag change —
forbidden by this ticket ("no descriptor change").

## Step 4 — verdict (no code changed)

The ticket's two NEGATIVE triggers (band on BG1 / our edge already equal) do not literally fire,
but the measurements refute the premise harder than either:

1. **warp, chip-use**: our sequencer never reaches the show in the compared window — the gate is
   upstream (fixture resolve flag), not a count. No per-state count can put a band at rust
   83..88 / 126..131. Canon's own edge maps to rust −24 (warp) / 19 (chip-use); our battle does
   not exist until capture 8. Even a RESOLVE_OVER fixture would need entry→tick spans of 75 and
   118 (canon: 107) — non-canon and mutually inconsistent.
2. **field**: our slide is already in sync with canon's under the fitted 110. Canon's true span
   (entry→first tick = 107, = 94 count + 13 hand-off→driver-start) would put our first tick at
   capture 115 instead of the aligned 140 — a 25-frame-early band and a field regression of
   ~2×27k px (ours slides alone k≈0..13, canon slides alone k=24..37). The 25 frames are exactly
   the fixture-history compression: canon's enemy dies at ~12 and dissolves 35 (0x0C at 47), our
   RESOLVE_OVER compresses that to 0x0C at 8 (25 aligned frames early). The fitted 110 exists to
   absorb it; no canon count equals the required 132. T7 (2026-09-14) already ported the 94+16
   factoring with the show frame preserved by construction and measured field +12 on one frame
   (capture 121, y14-30 band), reverted; moving the teardown/banner to the update after read +4,
   also reverted (src/battle.rs:1152-1158).

So: RESULTS_DELAY is a fit that holds only at field's window — the ticket's own definition of a
NEGATIVE — and its retirement cannot be paid for by canon's counts on any of the three rows.
Deleting it would regress field and leave warp/chip-use byte-identical. No code changed; no
AUDIT-6 key deleted (no row reads 0); fitted count stays 19.

## Dropped attempts

- First step-3 run without FLAG_TRACE: rust watch read 00 on every frame (the TRC2 block is only
  written when the descriptor's trace bit is set). Re-ran with flags|0x80 on the rust fixture
  in memory only.
- Considering a battle.rs change to arm `dissolve_in` for RESOLVE_OVER with canon's real
  kill+dissolve history (would move our 0x0C from 8 to ~43 and make the 94-count land the show
  correctly): rejected — it re-times field's banner/mark events that currently match, and the
  entry-time skew is a fixture property; the ticket forbids descriptor changes and widening.

## Capture accounting

Canon never changed. All captures went through harness.run()'s slot-pooled path (3-slot
semaphore); the step-3 watches were `--watch` flags added in memory to the rows' own side
configs. Canon-side capture runs total 19 (step 1: 4, step 2: 9, step 3: 3+3 with and without
FLAG_TRACE) — the ticket's "<=6 capture runs" budget is unreadable against its own steps 1/2/3/5
(each harness row is two captures); I read it as a cap on hand-run one-off probe captures (used:
0). No canon input was modified.

## What the next worker should try

- The real blocker for warp/chip-use/buster is the `decided` gate + fixture flags, not the show
  count. A ticket that allows `flags=0x31` on WARP_ZERO/CHIPUSE_ZERO/BUSTER_ZERO (descriptor
  change) plus a re-derived alignment could make the end sequence reachable; the span mismatch
  (needs 75/118/132 vs canon's 107) would then be an entry-time question per row.
- battle_full (real kill route) is where canon's 94+13 counts should actually pay: its 0x0C
  entries differ by only 8 frames (kill offset), so the port would move the sequencer trace
  273/540 down while field's fixture-locked alignment holds the fitted 110. A ticket splitting
  "fixture-locked rows keep the composite; live-battle rows take canon's counts" is the honest
  follow-up.
- The 13-frame hand-off→driver-start gap has no named counter in the asm (it emerges from the
  battle-state dispatch between the GameState+0x14 write, asm00_1.s:10753-10758, and
  sub_80094B6's entry latch, asm00_1.s:13329-13350); anyone porting it needs that measurement,
  not a constant.
