# End of battle (SCOPE M2): the results window's numbers

What is computed in our build after T112, and what is still supplied.

## The window's three numbers and where canon keeps them

Canon latches a per-battle stats record at 0x0203F4A4 (+1 busting level, +4 clear
time, +8 reward halfword) via the battle-transcript transfer sub_801FF18
(asm01.s:170), copies it to the results slot 0x02035260 (+variant*0xc) with
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
- **zenny** — `Battle::battle_zenny`: the sub_802C54C decode (asm03_0.s:12691;
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

## T219 (2026-09-18, NEGATIVE): there is no ESCAPE result window in this title

T219 asked for a `result_escape` row. Measured anatomy (all numbers from
captures run this session; worklog docs/worklog/T219.md has the commands):

**Kind byte.** showResultWindow_802C34E (asm03_0.s:12353) indexes everything by
the window kind at BattleState+0x0d (oBattleState_Unk_0d, BattleState.inc;
BattleStatePtr = [eToolkit+0x18] (Toolkit.inc loc 0x18, eToolkit 0x020093b0,
bn6f.map:2611) = 0x02034880 -- dumped). Three art pairs exist, kind 0/1/2:
GFX off_802C3FC (asm03_0.s:12500) = byte_872F3F4/0xE60, byte_8730254/0xF00,
dword_8731154/0xCA0; maps off_802C434 (asm03_0.s:12540) = dword_8731DF4 /
dword_8732154 / dword_87324B4, copied to unk_2034B30 (0x02034b30).

**Who writes the kind.** Exactly one writer: sub_80079A8 (asm00_1.s:9657-9660)
-- 0 when GetBattleEffects()&8 == 0, else sub_803DD60() (asm03_1_1.s:9413-9436)
which returns only 0 or 1. Unk_0d therefore only ever holds 0/1 in play (0
verified live: --watch 0x0203488d over a full result_arrival capture and a full
PAUSED->WIN recipe, both flat 0; --watch-write armed over the whole 200-frame
recipe saw ZERO stores -- the byte is 0-initialized and only ever stored 0).

**kind -> what draws (measured, poke experiment).** Poking the kind halfword
0x0203488c:0x0200 at frame 20 of the PAUSED->WIN recipe (Start@10 + DELETE_ENEMY;
odd-address 16-bit pokes silently fail, so the aligned halfword with Unk_0c=0
preserved) routes the ending into the ESCAPE flow:
- frames 140-158 cutscene motion, 158-171 static DIM (mean brightness 30.0 ->
  5.5, nonzero px 64984 -> 19082), 171-183 undim/transition, then a static full
  screen from frame 183 to 300 (brightness 23.9, 76800 nonzero).
- NO result window: no slide-in anywhere in frames 140-190, and the map at
  0x02034b30 dumped from the end-state differs from ALL THREE canon maps by
  >=860/864 bytes (the method is sound: the WIN timeline's same dump matches
  kind0 dword_8731DF4 within 20 bytes -- digits/blink drawn in after the copy).
- End state: BattleType (BattleState+0xf) 0x06 vs the WIN timeline's 0x00;
  GameState 0x02001b80 = 0 (the battle subsystem was exited). No write to
  Unk_0d during the whole flow (watch-write: 0 stores).

So: **kind 0 = the WIN/RESULT window, kind 1 = the LOSER window (art never
exported, see below), kind 2 = escape -- which ends the battle with NO window
at all** (dim, cutscene, fade back to the map). The escape-cutscene OBJECT is
the type-4 id-0x3b object (t4_0x3b_80E4910, asm31.s:94495-94507; action table
sub_80E4930 asm31.s:94509-94516: object_dimScreen / object_drawChipName /
sub_80E4954 asm31.s:94519-94557 the escape handler / object_undimScreen),
spawned only from attack-effect table off_802CCB4 entry 0x1a (asm03_0.s:13738)
-- dispatched for player chips by sub_8017AB4 (asm00_2.s:19056) and for enemy
AI by sub_80EBD9C (asm31.s:109719): an enemy-flee route, not a player input.
The ticket's own mechanism claim ("scripted B held during enemy turn", cite
"sub_801E4954") measured FALSE: battlestart.state + B held frames 300-800,
900-frame capture, MegaMan CurAction (0x0203a9b9) only ever 0x00 -> 0x01 at
frame 183, never the handler's 0x0c. (Cite correction: sub_801E4954 does not
exist; the handler is sub_80E4954.)

**Exporter warning (T189's to fix, recorded not changed).**
tools/results_export.py packs TWO variants and labels kind-2 art (dword_8731154
+ dword_87324B4) "LOSE" -- canon kind-1 art (byte_8730254, 0xF00 bytes, map
dword_8732154) was NEVER exported. If kind 2 draws no window, our "LOSE"
variant is the third window's art (or an unused one), and the true LOSER art is
unported. src/results.rs was NOT touched here.

**TIMEOUT.** Out of T219's scope by decision. Three arts exist in the tables;
whether a fourth variant exists at all is UNVERIFIED (canon shows three arts,
two windows + the flee flow).
