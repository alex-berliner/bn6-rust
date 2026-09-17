# End of battle (SCOPE M2): the results window's numbers

What is computed in our build after T112, and what is still supplied.

## The window's three numbers and where canon keeps them

Canon latches a per-battle stats record at 0x0203F4A4 (+1 busting level, +4 clear
time, +8 reward halfword) via the battle-transcript transfer sub_801FF18
(asm01.s:49-60), copies it to the results slot 0x02035260 (+variant*0xc) with
sub_800B444 (asm00_1.s:17986-17991), and showResultWindow_802C34E copies the slot
into the window struct eS20364C0 (asm03_0.s:12441-12455): level -> +8, reward ->
+0x14, time -> +0x1c. The rank byte is eS+0xe, written by sub_802C97E
(asm03_0.s:13232-13257, the clear-time record check against the best-time tables
unk_20018C0/unk_2000260) and consumed by drawResultClearTime_802C4E8's bank select
(asm03_0.s:12563-12565) through resultWindowSlideTick_802BE36 (asm03_0.s:11721).

## Ours (src/battle.rs)

- **rank** — `Battle::battle_rank`: sub_802CA1E + sub_802C97E's structure, every
  branch cited. The record branches are UNPORTED (named in the fn): the enemy model
  carries no canon ai_index and the build keeps no best-time tables, so the scan
  lands on canon's own no-record-slot branch, rank 0. Fed to `results.show` at the
  show site; exported in TRC2 +60.
- **zenny** — `Battle::battle_zenny`: the sub_802C54C decode (asm03_0.s:12782-12812)
  of `reward_word`. The ROLL that fills the word (sub_802C8FA's sub_80AA8E0 /
  sub_80AAC8C drop-table walk, asm03_0.s:13213-13223 / asm29.s:10830, 11354) is
  UNPORTED (named in the fn), so the word stays 0xFFFF and callers take their named
  fallbacks: the fixture site only when the descriptor's +44 is FIXTURE_UNSET, the
  real-play site via RESULTMATCH_ZENNY (peeked 100). Exported in TRC2 +62.
- **level** — still the fixture's +41 on fixture rows and `results::busting_level`
  on the real-play path; exported in TRC2 +61 as INFO.

## Measured (T112)

- result scenario, 40 frames: rank 40/40, zenny 40/40, FIRST DIVERGENCE none
  (tools/trace.py, TRC2 v4, `results` watch eS20364C0:0x20).
- battle_full, 540 frames: rank 540/540; zenny's only divergence is the window-up
  timing (both sides' stored value is 100 — canon's real roll and our peeked
  fallback agree).
- Pixels: result 0/0/40 and the 8-row guard set byte-identical to HEAD; cursor
  7/6/170 (F12 pad ladder re-measured 64/96/128/144 = 13/10/7/88, kept 128; the
  pre-T112 baseline was 1/1/170 — the tear did not fully restore, named not chased).

## Not computed yet (the follow-ups)

1. canon ai_index/enemy_idx in the enemy model (unlocks battle_rank's record
   branches; needs the best-time tables too).
2. the reward roll (drop tables) — unlocks the real zenny and the reward items
   (chips/PAs), which are outside the two traced words.
3. our busting_level vs canon's latched level byte (battle_full: ours 8, canon 2).
