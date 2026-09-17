# docs/provenance.md — the facts the code cites

The previous journal `TRANSFER.md` (2,897 lines) is now read-only. Every load-bearing fact
a comment, doc, or tool once cited as `TRANSFER.md <id>` lives here, under its old id as a
heading anchor. New work adds a section, not a journal entry.

The cited ids, with the tools and source files that once pointed at them:

| id    | provenance summary                                                      | cited by |
|-------|-------------------------------------------------------------------------|----------|
| 1     | the capture pipeline (libmgba build, mgba_capture.sh)                   | tools/states.py |
| 2     | battle RAM addresses (BattleState, BattleObject)                        | tools/states.py |
| 3     | the sterile real battle (delete-enemy + immortal + battle_isBattleOver patch) | AGENTS.md, AGENT_GUIDE.md, tools/states.py |
| 7ab   | tile parity; two phases cannot be settled by one save state             | src/fixture.rs, src/hudtiles.rs |
| 7aj   | HP box counts down and flashes                                          | src/custom.rs |
| 7ao   | read arcs out of the object (not sweep)                                 | tools/scoreboard.py |
| 7av   | backdrop's scroll phase pinned (eBGScrollCBCounters)                   | tools/states.py |
| 7aw   | save state at a battle's first frame; the RNG orbit trap                | AGENTS.md, AGENT_GUIDE.md, tools/harness.py, tools/mgba_capture.c, tools/patch_sterile.py, tools/states.py |
| 7b    | the Sword chip 0x47, frame-for-frame                                    | src/actor.rs, src/battle.rs |
| 7ba   | a battle's first 200 frames; white intro, not black fade                | src/main.rs, tools/states.py |
| 7bb   | buster HIT is a sample (FIFO channels 4&5), not a blip                  | src/battle.rs, src/main.rs |
| 7bf   | pre-RESULT countdown is 94, not 102; generic banner sequencer           | tools/harness.py |
| 7bj   | departing segment: a wave's final frame is held for its full authored duration | src/main.rs |
| 7bl   | custom gauge (TODO A8) stripe-flow animation, 470 px on tiles/gauge     | tools/allowlist.py (was the dangling "1270") |

## 1 — the capture pipeline

The capture tool is `tools/mgba_capture.c`, built with `gcc tools/mgba_capture.c -o
/tmp/mgba_capture -I/usr/include -lmgba -lm` and wrapped by `tools/mgba_capture.sh`
(optionally `--build <features>` to compile the Rust ROM first). It uses libmgba directly
(not the Qt window) and writes raw `.rgb` frames; `--no-decode` leaves them raw. The build
line is the load-bearing fact.

## 2 — battle RAM addresses (MegaMan + Mettaur + BattleObject offsets)

The toolkit lives at `0x020093b0` (ewram.s:582); `BattleStatePtr = toolkit+0x18` so the
live **BattleState** is at `0x02034880` (heap-allocated per battle). Battle objects:
**MegaMan** at `0x0203a9b0` (HP 60/100, panel (2,2), NameID 0x1a0), **Mettaur** at
`0x0203ab60` (HP 40/40, panel (5,2), NameID 0x0001). The **BattleObject** layout has
`CurState@0x8`, `CurAction@0x9`, `PanelX@0x12`, `PanelY@0x13`, `HP@0x24`, `MaxHP@0x26`,
`NameID@0x28`. The Mettaur's HP is `0x0203ab60+0x24 = 0x0203ab84`, MaxHP `0x0203ab86`.
Found by live-poking `pausedwithcannon` (2026-09-07).

## 3 — the sterile real battle (delete-enemy + immortal + battle_isBattleOver patch)

Three interacting tricks hold a battle open against a deleted Mettaur: (a) `--cheat
0x0203ab84:0` and `0x0203ab86:0` every frame deletes the enemy, but the game then
advances to RESULTS, so (b) the `battle_isBattleOver` code patch stops the conclusion
when the enemy is deleted, and (c) immortal HP (`--cheat HP=0xffff`) keeps the Mettaur
on screen without the "ENEMY DELETED" banner. The banner is tied to the deletion event
and still shows during a cannon fire.

## 7ab — whole-screen tile parity and the limit of one save state

0 of 38,400 pixels differ, sprites off, `demo-hudmatch` against
`/tmp/pausedwithcannon.state`: backdrop with its animation and scroll, HP box, CUSTOM
gauge with its flowing bar, twelve panels and the chip name strip. The gauge's bar ran
one frame ahead of its counter (sweeping the 8-pixel band alone put it at lag -1,
`BAR_PHASE`). **Two phases in that screen cannot be settled by one save state:** the
gauge's flow phase against the backdrop's (the capture's gauge has been full for an
unknown time), and the scroll parity (both sides step the backdrop a pixel every other
frame, on opposite frames, so a one-frame head start fixes the parity and breaks the
gauge, driven by different counters).

## 7aj — HP box counts down and flashes (orange)

The player's HP box should count down and flash orange on a hit; the old code jumped
straight to the new number in white. Measurement: a drop of ten goes 5, 4, 1 on both
sides. The **step is `|difference| / 8 + 4`** (so the first step is five, not three), and
the **flash hold is 15 frames** of which three are the countdown. The flash is NOT a
second set of digits: the real ROM swaps four entries of the box's palette bank (4, 5,
6 and 11) to an orange ramp and back. A palette write has to be held back a frame
because the box's tile writes land on the next frame.

## 7ao — read arcs out of the object, not sweep

`tools/throw_dump.py <chip>` walks a thrown object's `VX/gravity/VZ` fields out of
running EWRAM (sub_80C5C9C, asm31.s:29505; reads XYZ from +0x34 and VX/gravity/VZ from
+0x40), and the 43 fitted bomb constants became the game's own numbers rather than
fits: **43 of 43 exact.** Five launchers, all spawning at Z `0x300000`, X + 4 ahead of
the navi:

| launcher | chips                                        | vx      | vz      | g      | timer | moves_before_falling |
|----------|----------------------------------------------|---------|---------|--------|-------|----------------------|
| MiniBomb | MiniBomb, EnergBom, MegEnBom, BigBomb (3 seeds) | 0x2E666 | 0x20666 | 0x2800 | 40    | no |
| BlkBomb  | BlkBomb, LilBolr                              | 0x2C000 | 0x2236E | 0x2800 | 42    | no |
| BugBomb  | BugBomb                                      | 0x2C000 | 0x26062 | 0x2800 | 42    | no |
| FlshBom  | FlshBom                                      | 0x2E666 | 0x28CCC | 0x3000 | 40    | yes |
| VDoll    | VDoll                                        | 0x1EEEE | 0x2F333 | 0x2000 | 60    | yes |

The lesson: a sweep converges on the set of values that draw what you are looking at,
which is bigger than the set of true values — and reading the value out of RAM finds it.

## 7av — the backdrop's scroll phase

The backdrop scrolls under a counter pair `eBGScrollCBCounters` at `0x02009690` /
`0x02009694` (EWRAM), decremented by 8 and 4 a frame in `BGScrollCB_BG1Diagonal3to2Scroll`
(asm00_0.s:2165). Both are zeroed exactly once, at battle init, in `sub_8080D90`
(asm21.s:2, called from `initBattleStructsAndVram_80071D4`), so the phase is simply
"frames since this battle started". A save state grabbed mid-battle peeks at -63128
and -31564 — 7891 frames already elapsed — and nothing in the state or the build
reproduces that number.

## 7aw — save state at a battle's first frame; the RNG orbit trap

The encounter-roll accumulator is `eStruct2001c04.Unk_12` at `0x02001c16`
(S2001c04.inc:14), incremented by the player's per-frame movement in `sub_809D348`
(ow_player.s:341-346). `sub_80AA4C0` (asm29.s:10100) rolls when `Unk_12 - Unk_14 >= 0x40`.
The very first battle frame is found by `eBGScrollCBCounters`: they hold stale values
through frame 18 of the walk, read `0x0000/0x0000` at frame 19, and `-8/-4` at frame 20
— frame 19 is the tick `sub_8080D90` zeroes them. The state is written there.

**The RNG orbit trap.** Forcing the roll every frame (`--cheat 0x02001c16:2000
--cheat 0x02001c18:0`) while HOLDING ONE DIRECTION for 200 frames produces ZERO
encounters. Identical input every frame makes the rotate-based RNG
(`seed = rotl(seed,1)+1 ^ 0x873ca9e5` at `0x020013f0`) advance by the same stride, so
the low five bits walk a correlated subsequence. Varying the held direction (cycled
Right/Down/Left/Up one per frame) broke it and a battle came within twenty frames.

## 7b — the Sword (chip 0x47), frame-for-frame

`tools/chip_compare.py 47 demo-sword --frames 40`: 0 pixels on every frame from the
press to the idle (the c6 banner-tile artifact is the same one as for the cannon).
States (sub_80EB776): state 0 and 1 take one frame each → `windup: Some((0, 2))`; the
slash state (sub_80EB862) begins at c2 with animation 5 (gfx5 x8, gfx6 x2, gfx7 x2,
gfx8 held), timer 0x15, the hit and the arc on the frame it reads 0xc = pose frame 10
(c11); pose on screen 27 frames (`frames: 0x15 + 2`, `recover: 5` with the pose held:
`recover_anim: None`), idle c29. The sword object is `byte_80B8BD4` row 3 list 0xC
index 0 → `sprite_82EFE48`, animation 0, riding the navi origin with no arm offset,
gone with the attack's exit. The arc is a type-4 effect (`byte_80EBAD8[sf]=0x18` of
`byte_80E0398` = list 0xC index 0x14 → `sprite_830F144`, animation 2 for Sword, 0
WideSwrd, 1 LongSwrd), at the front panel's coordinates 0x10 up, drawn OVER the sword
object from its first frame (`effects_before_strike` in battle.rs).

## 7ba — battle's first 200 frames; white intro, not black fade

`demo-open` fields the battle-start capture's own line-up (three Mettaurs at (4,1),
(5,2) and (6,3), navi on column 2). On `/tmp/battlestart.state`:

- frames 0..70: PLAIN WHITE, the whole screen
- frame 71: the field appears, whole, with the navi already on it
- frame 113: the first virus materialises
- frame 141: the second (+28)
- frame 173: the third (+32), and the chip window opens

The white is a HOLD then a RAMP (frames 71..86: 92, 85, 77, 70, 62, 56, 48, settling at
42). The two wrong measurements: "brightness" reads a white screen as FULL (it
reported the field at full brightness from frame 0 — wrong), and counting only PURE
(255,255,255) pixels reads a 90%-white screen as 0% white (missed the ramp entirely —
also wrong). The fix both times: measure a continuous quantity, not a predicate.
`SCREEN_FADE_FRAMES = 71 + 14`, full-white hold then ramp off.

## 7bb — the buster's HIT is a sample (FIFO channels 4&5), not a blip

Soloing all six channels and subtracting a control run with no shot — channel 0 (PSG
square 1) has the FIRE blip at +7/+8, channels 1, 2, 3 have nothing above 120 (no PSG
involvement at all), and channels 4 and 5 (FIFO A and B) carry the HIT at +11 through
+23, **peaking 2102 at +16**. Both FIFOs together, and nothing on the PSG, means the
hit is a DirectSound sample at byte_81597A0 (dat37.s), 1881 samples at 10512 Hz, no
loop, exported by `tools/sample_export.py`. The mixer frequency must match exactly.

The harness's `--audio-channel` table is NOT the hardware's: channel 4 is DIRECTSOUND
A, not the PSG's noise channel. Read the table the tool prints.

## 7bf — pre-RESULT countdown is 94, not 102; states 6-9 are a dead end

`off_8008038` (asm00_1.s:10370-10380) is the GENERIC BANNER SEQUENCER, reused for
BATTLE START!, TURN START!, ENEMY DELETED, MEGAMAN DELETED and the result messages,
selected by writing pre-multiplied byte offsets into `dword_203CA70`. State 3
(`sub_80081A4`, asm00_1.s:10542) picks between `mov r4,#0x5e` (94) with `SONG_WINNER_0`
and `mov r4,#0x66` (102) with `SONG_WINNER_1` on `BATTLE_EFFECT_SHOW_RESULTS`, bit 0x2
of `GetBattleEffects()` (asm00_1.s:10580-10592). The one field-encounter row of
`BattleSettings` (data/BattleSettings.s:6) has that bit SET, so a field battle counts
**94**, not 102. The dispatch out of state 3 costs no frame (asm00_1.s:13089-13104);
N = 14 frames of the reward tally in `sub_8009478` (asm00_1.s:13129) waits on two
completion sentinels.

States 6-9 (`sub_800834A`/`sub_80083E4`/`sub_8008452`/`sub_8008492`,
asm00_1.s:10753/10842/10898/10930) are a sibling branch entered only when
`sub_800A152()` returns 7 — a different battle outcome. They never run on the
enemy-kill path.

## 7bj — the departing segment: a wave's final frame must be held

`Shot::update` had to drop the departing segment the instant `on_last_frame()` went
true, before ticking it. So `wave.bin` animation 0 frame 4 (the fragment spray at the
panel just vacated) was never ticked and never shown. Measured on the spray's own
box, both sides at lag 21: real shows pose A 2 frames, then pose B 3 frames, gone on
the 6th (2 poses, 5 frames); ours, before, showed pose A 2 frames, gone immediately
(1 pose, 2 frames); ours, after, matched the real (2 poses, 5 frames), and the after
row was hash-identical to the real one, not merely the same pixel count.

Why: `sprite_getFrameParameters` (sprite.s:1182-1198) BIC's bits 0x80 and 0x40 out of
the flags it returns unless `Unk_01` (the frame's own remaining duration counter) has
already reached zero. Polling for 0x80 doesn't tell you "the last frame has been
reached" — it tells you "the last frame has been reached AND has already been held
for its full authored duration". Anything that destroys an object on first sight of
the bit drops that object's final frame entirely. `object_updateSprite` also runs
unconditionally every tick whatever the CurAction is (asm31.s:31409), so a departed
segment keeps animating exactly like a live one.

## 7bl — custom gauge stripe-flow animation (TODO A8), 470 px on tiles/gauge

The custom gauge's stripe-flow animation is not yet modelled. Measurement on
`tiles/gauge` integrated: **470 px**, all of it the flowing bar and its L-or-R marker.
It is not a fill — the lit-pixel count cycles through the same four values throughout.
It is not a phase — no offset in its 112-frame period helps. The four-state flow this
build models is right for the settled state; what is missing is that early on the
stripes SHIFT position as well as cycling, and something stops that around frame 98 of
the capture.

(Was cited as `TRANSFER.md 1270` in `tools/allowlist.py` — a line number in section
7bl, not a section id; section 7bl is the home of this fact.)
