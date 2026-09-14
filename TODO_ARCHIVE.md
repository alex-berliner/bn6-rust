# TODO_ARCHIVE -- closed tickets, moved verbatim by tools/archive_tickets.py
Open tickets live in TODO.md; `python3 tools/next_ticket.py --list` indexes them.


---

# archived 2026-09-13

## A. Measured residues — small, self-contained, all have a number

### A9. The opening's integrated residue: the rebuilt state's spawn cells and the enemy HP readout  *(filed from F4, 2026-09-12)*

`opening integrated` reads **72499 / 2691 / 40** (window canon 120..159 vs rust origin 8 + offset
119) against R1's rebuilt `battlestart.state` after F4's fixture fix (hp + rng delivered). The
whole residue is the three Mettaurs, two mechanisms, both with numbers:

1. **SPAWN CELLS ARE THE OLD STATE'S.** Canon materializes its viruses at **(5,1) from canon frame
   ~118, (5,3) from ~153, (6,2) from ~183** -- measured twice, independently: gold-pixel cells at the
   materialization frames, and the objects' own PanelX/Y at frame 250 (0x0203aa88/0x0203ab60/
   0x0203ac38, +0x12/+0x13 = (5,1),(5,3),(6,2)). The descriptor's diagonal (4,1),(5,2),(6,3) is the
   LOST state's layout; src lays a fixture's enemies out on a fixed +1/+1 diagonal from ONE
   (enemy_col,enemy_row) (src/battle.rs ~1348-1358) and cannot express the new cells. The real
   mechanism is probably spawn cells chosen from primary_rng at battle init -- same encounter, and
   the cells changed between the old and rebuilt states -- but canon's cell-selection routine has
   NOT been found, so that is unverified. Two ways to fix: derive the cells from the (now delivered)
   rng the way canon does, which needs canon's routine in reference/bn6f first; or extend the
   descriptor with per-enemy cells (FIXTURE.md + src/fixture.rs + battle.rs).
2. **THE ENEMY HP READOUT IS ~70 FRAMES EARLY.** Ours draws "40" under each virus the moment it is
   targetable -- already visible on the row's first compared frame (rust 127, mid-materialization;
   the draw loop at src/battle.rs ~3550, "Each enemy's HP sits just under its panel"). Canon shows NO
   readout during the whole opening: scanning 150..400 from the state, its first "40" is at canon
   frame **~196**, with the opening chip window (C1: a battle OPENS with the chip window). Region:
   the digit readouts under the virus panels, x 150..200, y 86..140. src/ territory: gate the
   readout on whatever canon gates it on (probably the same event that opens the window), not on
   targetability.

### A1. The shockwave's departure  *(DONE at 0 -- TRANSFER 7bj)*
460 px to 345 to ZERO. The mechanism was modelled -- a hop spawns a NEW segment and the old
one stops where it is and plays its own animation out -- and the last three frames were the
segment being destroyed too early. `on_last_frame()` was checked BEFORE ticking, so the
fragment spray (`wave.bin` anim 0 frame 4) was never ticked and never shown.
`sprite_getFrameParameters` masks 0x80 out unless the frame's own duration counter has
already reached zero (sprite.s:1182-1198), so the bit means "held for its full duration",
not "reached". Real and ours are now both 2 poses over 5 frames, hash-identical.

THE PER-HOP TABLE IS A DEAD END -- DISPROVED, TRANSFER 7bh. `byte_80C6B00` is 16 rows of 4
bytes indexed by `Param1 * 4` (asm31.s:31411-31416), and `Param1` is INHERITED across a hop:
the respawn goes through `SpawnBattleObjectCommon`, which copies the whole Params word
(asm00_1.s:254). Every hop of one attack reads the same row, and a Version 0 Mettaur is on
row 0 -- dwell 0x16, animation 0 -- from first hop to last. Do not model the table.

THE REAL LEAD is the departing segment's own animation hold. The three frames are real
199-201 against ours 220-222, 115 px each, and they are the fragment spray at the panel just
vacated (`wave.bin` animation 0 frame 4, the one flagged 0x80). The real ROM's spray shows
several distinct sub-poses over that window; ours shows one pose for about two ticks and
then vanishes. So the segment is being destroyed a few ticks too early -- look at
`on_last_frame()` and the departure's destroy sequencing, not at the table.

Two negative results already recorded, do not repeat them: allowing SEVERAL departures to
overlap measures 8725 px over 20 frames; and pre-ticking every new segment's `Player` the
way `Shot::shockwave()` pre-ticks only the first measures the same 8725 and takes `wave` to
3840. One slot, newest wins, and only the first segment is pre-ticked.


### A2. The chip window's cursor  *(done -- TRANSFER 7ag)*
170 frames of a five-step walk, and everything the SCRIPT drives is exact. It was two
one-frame bugs and neither was `CURSOR_DELAY`: the card's palette landed a frame before
its tiles, and the bracket's blink flipped a frame early because `self.frames` is bumped
before anything is drawn. The fixture had to be fixed first -- `demo-cardname` places its
cursor statically and never walks, so a scripted real walk was being compared against a
still picture. `demo-custmatch` starts on OK as the save state does, so both sides run the
same script.

CLOSED at 0 -- TRANSFER 7bc. The paragraph that used to stand here said the residue was a
fixture problem with no shared origin and could only ever coincide. That was wrong, and
nobody had read `sub_8028820`. The blink counter is window-relative on both sides (a field
at 0x02036500, asm03_0.s:4801-4804 and 1163-1165); the save state's value is just not zero
(0x647, peeked). Held static and swept, the offset was exactly +1 frame, and the frame was
ours: the slide-in reached `Phase::Open` through a second match arm a frame after the real
ROM advances to state 4 in the call that zeroes the counter (asm03_0.s:1011-1012).


### A3. The shockwave's panel light  *(DONE at 0 -- TRANSFER 7bk)*
Was 87 of 90. Two of the three were the wave's PARTING light: when the hitbox dwelt its
way off the field this build dropped it immediately, discarding the three-frame linger
`Shot::update` had just armed for the panel it was vacating. The real ROM's segment keeps
re-asserting its old panel's highlight every frame until its own departure animation
finishes -- `object_highlightCurrentCollisionPanels` is called unconditionally from
`sub_80C6C14` (asm31.s:31491) whatever the CurAction is. Fixed in `src/battle.rs`.

AND THE OCCUPANCY RULE WAS NOT A RULE. "A panel somebody is standing on is not lit" was
recorded from one capture and is wrong: there is no occupancy check anywhere in the
render path -- `object_highlightPanel` and the panel-draw loop `sub_800C5E0`
(object.s:2548-2560, 1684-1761) only ever look at panel validity, a blink flag and the
one-shot highlight flag. The real mechanism is in the wave's own update:
`object_clearCollisionRegion` is called only when a hit has just registered
(asm31.s:31480-31485). Confirmed by tracking MegaMan's HP across dumps -- on the SECOND
attack the wave relit his panel normally for about 14 frames while he was still in his
post-hit invincibility, and it went dark only when a hit actually landed. The simple
`taken = navi.panel() == (c, r)` check in `battle.rs` happens to match over the measured
window because that window covers a first hit on a fresh target. Modelling it properly
means modelling mercy invincibility.

WHAT IS LEFT is the wave's FIRST hop, one frame. THE LAYOUT SCARE IS RETIRED (TRANSFER
7bd): the claim that any source edit shifts the Mettaur's timing was tested with a private
target directory and is false. Identical source gives byte-identical ROMs and captures; a
comment, a dead const, a dead function and a dead local inside the strike arm itself all
left the spawn frame at 198. The ROM hash moves only because `assert_eq!` bakes
`panic::Location` line numbers into `.rodata` -- six dead bytes. The likely cause of the
original report was two builds racing the shared target directory. So the first hop can be
chased directly, with no methodology worry attached to it.

### A4. Pin the backdrop's scroll phase  *(REOPENED -- the missing state now exists)*
`tiles` compares a fixed frame 392, not the best of sixty, and that is better than it was. But 392
was SEARCHED FOR, not derived: the phase counts from battle init (`eBGScrollCBCounters`, zeroed
once by `sub_8080D90`) and `pausedwithcannon.state` is 7891 frames in, which nothing here can
reproduce. The entry used to end "a capture from a battle's real frame 0 is the single most
valuable thing the harness does not have".

IT HAS ONE. `/tmp/battlestart.state` peeks as

    battlestart.state       0x02009690 = 0x0000       0x02009694 = 0x0000
    pausedwithcannon.state  0x02009690 = 0xFFFF0968   0x02009694 = 0xFFFF84B4

and -63128/8 = -31564/4 = 7891 exactly, which is the elapsed figure TRANSFER already records. So
the counters fall by 8 and 4 a frame from zero at init, and battlestart.state is at battle frame 0.

WHAT MEASURING IT SHOWED, and why this is not just tidying. Real from battlestart.state against
`demo-open`, backgrounds only, whole screen: the best match against real frame 120 is 1294 px at
rust 127/128, of which the HUD strip is 1102 and the backdrop band 116. Holding that lag and moving
the frame gives 4375, 5352, 1294, 4378, 4005, 5707 for real 100/110/120/130/140/150. A constant
offset plus a static HUD difference would sit near 1294 everywhere. It does not -- so either the
best lag drifts with the frame, or our backdrop advances at a different RATE from the real one,
which would be a parity bug that the swept 392 has been hiding.

### A8. The custom gauge  *(0 -- but by MEASURED constants, not a mechanism)*
`gauge` 446 -> 0. Two offsets, `BAR_EXTRA = 9` and `MARKER_EXTRA = 8` in src/hudtiles.rs.

READ THIS BEFORE TRUSTING THE ZERO. Both numbers were measured, neither was derived, and the
thing they imply is not understood: this build drives the bar and the marker off ONE counter
(`gauge_tick`), and the real ROM evidently does not, because no single phase can satisfy both --
9 mod 28 together with 0 mod 16 has no solution. The offsets make the picture match; they do not
explain why the two clocks are related the way they are. That is still open, and the routine that
draws the flowing bar has still not been found in the disassembly.

Same footing as `BUSTER_HIT_DELAY` in battle.rs, and labelled the same way in the source: the
value that measures right rather than the value that computes right. A zero standing on two
unexplained constants is worth less than a zero standing on a mechanism, and the next person to
touch this should be trying to replace them, not defend them.

### A8 (the diagnosis, kept -- five wrong readings and what settled them)
### A8-old. The custom gauge's BAR CELLS ARE THE WRONG SHAPE
`gauge` 446. Rendering the two HUD strips side by side at the alignment answers it in one look,
after four rounds of me reasoning about timing:

    real   the bar's lit cells are SLANTED parallelograms -- diagonal stripes, "///"
    ours   plain upright rectangles

That is why no phase ever matched. It is the tile ART, not the animation: sweeping our frames over
more than a full 112-frame gauge period against the real frame finds nothing better than 446, and
the alignment frame itself is the best. Everything around it is already right -- the gauge is full
on both sides (peeked: 0x020352A0 reads 0x4000, the cap), the lit bar spans the same 64..183, and
the four-step 7-frame cycle shifting the pattern 2 px a step is confirmed on the real ROM by the
leading edges of its lit runs (66,74,82,90,98 at f41; 64,72,80,88,96 at f42 -- 8 px apart, 2 px
left at a step boundary).

MY OWN WRONG READINGS ALONG THE WAY, all from measuring instead of looking: "the prompt blinks out
of phase" (it does, but that is 194 of the 446, not all of it); "it is an origin problem"; "it is
not a phase problem, the content differs" (right, but I then guessed the wrong content); "the
stripes shift early and stop" -- that last was the DIAGONAL pattern moving through the single row
I was hashing, which is exactly what a slanted cell does.

    HP box 28    bar left 112    marker 194    bar right 112

AND THE TILES ARE NOT WRONG EITHER -- that was my fifth reading and it lasted about ten minutes.
Rendering one body cell across a full cycle on both sides, seven frames apart:

    real   slant   slant'  small-squares  big-square  slant  slant'
    ours   big-square  slant   slant'  small-squares  big-square  slant

The SAME FOUR TILES IN THE SAME ORDER, ours one step behind. Our asset has all four
(indices 57, 58, 59, 60 = VRAM 0x234, 0x235, 0x232, 0x233, exactly what the docstring on
`BAR_CYCLE` already claimed).

WHAT IS VERIFIED, AND NOTHING MORE. The four tiles are right and in the right order; at the
alignment frame the two sides are on different steps of that cycle. Everything else I claimed
about this bar tonight was wrong, six times over, and the last one is worth spelling out because
it is a trap anyone would fall into:

I measured the lit bar's EXTENT with a green-colour test and got 64..183 on the real ROM against
65..182 here, and wrote that up as "our art sits one pixel in at both ends". Reading the actual
pixels instead: at y=14 the real is green at x=64,65,66 with a blue pixel at 67, and ours is green
at 66,67,68,69. Different PATTERNS, not a shifted one. The extents differ because the two sides
are on different cycle steps -- which is the thing already known. An extent computed over a whole
box across differing patterns says nothing about position.

THE TABLE, WHICH SETTLED IT. Hashing one body cell per frame across a full cycle on both sides:

    real  f44..f71 : AAAAA BBBBBBB CCCCCCC DDDDDDD AA
    ours u435..u462: AAAAAAA BBBBBBB CCCCCCC DDDDDDD

Four tiles, seven frames each, on both sides -- and the four HASHES ARE THE SAME on both, so the
art is byte-identical and only the phase differs. (Careful with that table: the letters are
assigned per side, so real's "A" and ours' "A" are NOT the same picture. Matching by hash instead:
the real shows its frame-44 tile on frames 42..48, and we show that same tile on our 442..448.)

TWO NUMBERS, and they are the whole ticket:
  - THE BAR is 9 frames LATE. The alignment maps our frame u to real u-391, so the real's run at
    42..48 should be ours at 433..439 and is ours at 442..448.
  - THE MARKER IS ALREADY ALIGNED, offset 0. Real runs 38..44, ours 429..431, and 429-391 = 38.

That is the surprise, because in this build both come off the SAME counter -- `flow = gauge_tick -
BAR_PHASE`, feeding `(flow / BAR_FRAMES) % 4` for the bar and `(flow / MARKER_FRAMES) % 2` for the
marker. So the two are in the wrong phase RELATIVE TO EACH OTHER, and no single seed or
`BAR_PHASE` can fix both: 9 is not a multiple of the bar's 7-frame step either, so it is not a
rotation of `BAR_CYCLE`.

DO NOT just add 9 somewhere. The mechanism is the question now: find what the real ROM advances
the BAR from, and whether it is the same thing that drives the marker. `SetCustGauge` writes the
gauge VALUE to 0x020352A0 (asm00_2.s:29838); the routine that draws the flowing bar has still not
been found.

SEARCHES THAT DO NOT FIND IT, so nobody repeats them: grepping the asm for the bar's VRAM tile ids
(0x232-0x235) finds nothing -- they are not literals -- and grepping for the gauge art's load base
0x222 finds only `0x2220`, which is an EVENT FLAG base in asm00_1.s:8227 and asm03_2.s:4336, not a
tile. The ids must be built from a base plus an offset, or come out of a table. Try instead:
follow the writers of the BG3 map region the gauge occupies, or set a watchpoint on the map cells
in an emulator and see who writes them.

The marker (194 of the 446) is a separate half-cycle of phase: real is ORANGE at the alignment
frame, ours CYAN, both blinking on the same 16-frame beat with exactly 110 orange pixels lit. Last,
after the two above.

### A7. The backdrop's art animation  *(DONE -- 40 consecutive frames at 0, every frame sampled)*
**`opening` IS NOT 0 AND NEVER WAS.** I wrote that check tonight sampling `range(120, 160, 4)` --
every fourth frame -- and every fourth frame was exactly the set that matched. The backdrop's
scroll moves a pixel every 2 frames across and every 4 down, so a rounding error shows on three
frames in four and hides on the fourth. Sampling a periodic signal on its own period measures
nothing. Measured at the time, at the lag the check used:

    real 120 -> 0    121 -> 2433    122 -> 2433    123 -> 0    124 -> 0

I reported "opening 16788 -> 0" as the evening's headline. It was an artifact of my own sampling.

WHAT THAT UNCOVERED, and it is the good half. The scroll's rounding fix -- ceiling rather than
floor, because the register is `lsr #4` of a FALLING counter -- is CORRECT after all. I had
reverted it twice: once measured at a fixture's stale fixed lag, once "confirmed" by this check.
With it in, and sampling EVERY frame at a searched lag, 34 of 40 frames are exactly 0 where
before three in four were a whole pixel out. The full suite is otherwise untouched: every other
check stays at 0, so the fixture damage I attributed to it earlier really was the `BD_TRACE`
diagnostic.

WHAT IS LEFT, and it is now precise: at lag 6 the failures come in PAIRS EVERY EIGHT FRAMES --
frames 126/127 (156 px), 134/135 (496), 142/143 (2359), 150/151 (2671), 158/159 (2466). Eight
frames is the backdrop's art step in the settled part of its schedule, so with the scroll finally
right the ART now sits one frame off it. The growing magnitude is the art drifting further from
the real ROM's as the run goes on.

FIXED, AND THE FIX IS AN INITIAL CONDITION, NOT A FUDGE. The art needed to start two frames
further back than the real ROM's own clock does: `Backdrop::new` seeds `STEP_HOLD[0] + 1` where the
real ROM reads Timer 3 at the frame its scroll counters read zero. The reason is that this build
creates its backdrop two frames into the battle it is being compared against. Measured rather than
assumed -- that value gives 40 consecutive frames at exactly 0, and one frame either side of it
measures 8102 and 24398.

AND IT UNCOVERED A BUG IN THE SEEDING. `prime()` was assigning the timer, which silently discarded
whatever `seed()` had just set -- so the peeked Timer had never taken effect at all, only the entry
and the scroll counters had. `prime()` now only draws.

`opening` is 0 over 40 CONSECUTIVE frames, every frame sampled, with the lag searched. The backdrop
is exact.
`opening` IS ZERO. The backdrop band is 0 on every sampled frame and so is the HUD. Three parts:
the schedule (below), the scroll's rounding, and MegaMan's HP -- the last 290 px were entirely
the HP box, 29 a frame, because the captured battle's navi is on 60 and `demo-open` started at
100. It now carries the capture's HP as `demo-hudmatch` and `demo-resultmatch` already did.

THE SCROLL ROUNDING, and the trap in measuring it. The register is `lsr #4` of a counter that
FALLS by 8 -- a logical shift of a negative, so a ceiling on the negated value where a plain
divide floors, one pixel apart on ODD frames. Measured at the fixture's FIXED LAG the change
looked catastrophic (290 -> 30304) and was reverted as a negative result. Searching the lag shows
it is identical: 290 at lags 6 and 7, where before it was 290 at 7 and 8. It moves which lag is
right and nothing else. **A fixed alignment constant will report a correct change as a disaster.**
That is the same failure this file records for `tiles`, `mettaur` and `wave`, made a fourth time,
by me, an hour after writing the other three up.

WHAT IS LEFT is `tiles` only. Its window (390..394) predates the corrected period: the art cycle
is 192 frames, so matching art AND scroll needs LCM(192,896) = 2688 rather than 896. A 2790-frame
sweep of `demo-hudmatch` finds its best band score at 68 px, recurring every 384 frames, and never
0 -- while `demo-open` reaches 0 outright. Rendering the 68 shows every arc and ring aligned
pixel-exact and only the glyphs differing, so at those frames we are on a different art STEP, not
looking at a broken asset.

SOLVED. At the derived alignment -- our frame 1798 against the real ROM's frame 44 -- the whole
screen compares at 470 px, and the backdrop band, the field and the bottom strip are all ZERO. The
backdrop is pixel-exact. Every one of the 470 is the HUD's L-or-R prompt blinking out of phase,
which is now A8 above.

The last step of the diagnosis is worth keeping. Our frame 1798 was compared against every real
frame in range, and it matches real 44 EXACTLY while differing from real 43 by 136 px. The fixture
had been comparing against 43. So the "one step's art" theory below was wrong too: nothing was
wrong with the art, the alignment was one frame out.

WHAT WAS RULED OUT ALONG THE WAY, all of it verified rather than assumed: `demo-hudmatch` was instrumented the same way. Its clocks
reach entry 13 / timer 8 -- the real ROM's state at its own capture frame 43 -- on frames 64, 256,
448, 640, every 192 as they should. Combining with the scroll (period 1024 frames) puts the true
alignment at rust 1798, and measuring there gives the best result in the whole capture: full 752,
band 136. Not a search, and not 0.

At rust 1798 our entry is 13, so we are drawing STEP 0, which is `byte_807FE40`. The real ROM at
its frame 43 is on entry 13 as well, so it is drawing the same step. Both sides draw E40 and the
band differs by 136 px. Meanwhile `demo-open`'s compared frames sit early in the schedule, on the
alternating C90/CD8 beats, and reach 0.

So the schedule, the initial condition, the scroll rounding and the step->art mapping are all
verified correct, and what is left is the ART OF ONE STEP. The mapping was checked exhaustively
rather than by eye: parsing the seven tables out of dat20.s and matching them against the
exporter's rows gives a unique hit for every one (FRAMES[0]=E40, [1]=CD8, [2]=C90, [3]=D20,
[4]=D68, [5]=DB0, [6]=DF8), and re-deriving STEP_ORDER from the script under that mapping
reproduces the table in the branch exactly.

NEXT STEP, AND ONE WAY THAT DOES NOT WORK. Diffing raw VRAM at the script's own `gfx_dest`
(0x06000040) between the two builds is USELESS: agb allocates VRAM its own way, so that address
holds unrelated data in this build, and all 1152 bytes differ for a reason that has nothing to do
with the art. (The real side reads `ffffffff` for its first tile at dump time as well, so the
address is not simply "the backdrop's tiles" on that side either.) Do not repeat that.

What is worth doing instead is a pure DATA comparison, no emulator: parse `byte_807FE40`'s 36
indices out of dat20.s, slice those tiles out of the blob at `dword_8617488` (dat38_60.s), and
compare them against step 0's tiles in `assets/backdrop.bin`. If they agree -- and they should,
because `backdrop_export.py` builds the asset from that blob using exactly those indices -- then
THE ART IS NOT THE PROBLEM AND THE MAP IS. Note the script copies 36 tiles while the exporter's
rows carry 37 slots, the extra one at the front; a map that assigns those 37 slots differently
from the real ROM would show up exactly like this: right tiles, wrong places, on some steps and
not others.

The rendering evidence supports the map over the palette: ours draws FEWER glyphs rather than
differently-coloured ones.

MERGED. `opening` 0, `gauge` 446, and every other check still 0 -- seventeen checks, sixteen of
them zero.

What landed: the scripted art schedule, and `Backdrop::seed`, which gives a fixture the phase of
the save state it is compared against instead of starting its clocks at zero. That also brought
`tiles`' alignment back to rust 435 against real 44, so the check captures 438 frames rather than
the 1800 it needed to reach the only unseeded alignment at 1798.

AND THE "FIXTURE REALIGNMENT PROGRAMME" I WROTE HERE WAS MY OWN DEBUG CODE. `chips` 13 off,
`popup` 7366 and `banner` 5162 came from a `BD_TRACE` static I added to instrument the clocks and
forgot to remove -- 5.6 KB and a write every frame. I measured its effects, concluded that a
correct backdrop invalidates every fixture calibrated against the old one, reasoned out why that
followed from the periods, and wrote it up as a programme of work with three options. Removing the
diagnostic took all three checks to 0. The art schedule never touched them.

The reasoning was plausible and the arithmetic about the periods was right; it was attached to a
cause I had introduced myself and not checked for. Before explaining a regression, check what is
in the tree.

MY ORIGINAL FRAMING WAS WRONG. The art clock does NOT have a different origin from the scroll:
`LoadGFXAnims` is called at battle init from `sub_8080DA0`, in the same routine as the scroll's
own zero, back to back (asm00_1.s:8434-8435).

THE REAL MECHANISM: the art is the same scripted GFXAnim engine the overworld uses
(`ProcessGFXAnims`, asm00_0.s:3510-3697), driven by a list of (tile-table, delay) entries in
`eGFXAnimStates` (0x020094c0, GFXAnimState.inc). For this background the script is `off_807FB98`
(data/dat20.s:140-172): TEN 4-frame entries, then NINETEEN 8-frame entries, a 192-frame loop --
not the uniform 8-frames-forever, 56-frame loop this build assumed.

VERIFIED EXACT. Simulating the transcribed schedule against `--dump 0x020094c0:24` peeks of the
real ROM's own `entry`/`Timer`:

    battle frame   1      2      3      5      9        7935
    real         (0,2)  (0,1)  (1,4)  (1,2)  (2,2)    (13,8)
    model        (0,2)  (0,1)  (1,4)  (1,2)  (2,2)    (13,8)

The deep-battle column needed care: `pausedwithcannon` is 7891 frames in and the capture runs 44
frames to reach index 43, so the battle frame is 7935, not 7934. An off-by-one there looks
exactly like a broken model.

WHERE IT STANDS: `opening` 16788 -> 290 (worst frame 29 px, from 2740). But `tiles` 0 -> 282.
That is not a regression in the model, it is a phase move: the art period is now 192 rather than
56, so matching art AND scroll needs LCM(192,896) = 2688 instead of 896, and the check's window
(390..394, capture 395 frames) no longer contains the match. Derived rather than searched, the
match is at rust 2184, and a sweep confirms a sharp minimum there -- 282 px against ~3200 and
~4000 on either side.

WHAT IS LEFT, NARROWED TO A NUMBER: our ART and our SCROLL are THREE FRAMES out of step with
each other. Not the art's schedule, which is exact, and not the scroll, which is pixel-exact --
their relative offset.

Rendering the two sides at rust 2184 shows every arc and ring of the backdrop aligning perfectly
and ONLY the little purple glyphs inside the rings differing, which rules the scroll out by
inspection. Counting glyph-coloured pixels gives the step boundary directly:

    real  (36, 39, 42, 45, 48, 51, 54, 57)  1162 1172 1174 1047 1035 1040  870  884
    ours  (2176, 2179, 2182, ...)           1162 1172 1025 1024 1035  848  843 1208

The two agree for two samples and then ours steps early: the real ROM changes step between its
frames 42 and 45, ours between 2179 and 2182. So at rust 2184 the scroll is exact and the art is
three frames advanced; at 2181 the art would line up and the scroll would not.

WHERE IT IS NOT. Both structures were dumped on the SAME real frames, which settles the
relationship instead of comparing each against its own assumed origin:

    real frame   art entry/Timer   scroll counters   frames since init
    1            0 / 2             -8 / -4           1
    2            0 / 1             -16 / -8          2
    3            1 / 4             -24 / -12         3

So the art's entry 0 counts 4,3,2,1 across scroll-frames -1, 0, 1, 2: THE ART STARTS EXACTLY ONE
FRAME BEFORE THE SCROLL'S ZERO, and `prime()` (entry 0, timer 3 at frame 0) already models that
correctly. The initial condition is right and is not where the three frames are.

WHERE TO LOOK NEXT, then: our own sequencing. `prime()` is called from `Battle::prime_backdrop`
right after `Battle::new`, and `Backdrop::update` advances BOTH clocks -- so the art and the
scroll cannot drift from each other unless `update()` is not being called on every frame the
scroll is supposed to advance, or the backdrop is created some frames before the battle's own
clock starts. Instrument it: have the build report its own `entry`/`timer`/`x_q` per frame (a
poke to a known address the harness can `--dump`, or a debug tile), and compare against the table
above. Do not adjust a constant until that trace exists -- the schedule and the initial condition
are both confirmed exact now, so a constant that fixes the number would be hiding the real cause.

ONE SMALLER THING FOUND ON THE WAY, AND TRIED, AND WRONG. The real scroll register is
`(counter as u32) >> 4` of a counter falling by 8 -- a LOGICAL shift of a negative, so it lands
on -ceil(n/2) where this build's `-(x_q / 4)` gives -floor(n/2), one pixel apart on odd frames.
Checked against the peeks: at frame 1 the counters read -8/-4 and the register is -1/-1, where
this build gives 0/0. The derivation looks airtight.

CHANGING IT TO CEILING MEASURES MUCH WORSE: `opening` 290 -> 30304, `tiles` 1160 with its best
at 390 rather than 391. Reverted. So something in the derivation is wrong -- the register may not
be written straight from that shift, the BG offset may carry another term, or our `x_q` may not
correspond to n the way I assumed. Worth another look with a per-frame trace of BOTH sides'
actual scroll registers, not a third guess.

A plausible change backed by a disassembly line that moves the number the wrong way is exactly
the shape 7ah warns about. Recorded here rather than retried.

DO NOT MERGE THE BRANCH UNTIL THAT IS ANSWERED, because merging as-is turns a `tiles` 0 into a
282, and a 0 that came partly from luck is still worth more than a non-zero nobody has explained.
The backdrop is not just a scrolling picture: parts of it ANIMATE, in steps of about 8 frames.
Counting one of its own colours, magenta (90,0,140), over the whole screen from a battle's
first frame gives a clean staircase on both sides:

    real  934 958 958 959 | 707 725 725 725 725 737 737 737 | 388 x8 | 220 x8 | 0 x8 | 426 ...
    ours  884 884         | 649 673 673 672 672 691 691 691 | 358-377 | 208-220 | 0 x8 | 431 ...

THE TWO CLOCKS DISAGREE WITH EACH OTHER. The SCROLL aligns at lag +7 (our capture starts at
boot, the real one at battle frame 0). The ART ANIMATION aligns at lag **0** -- the staircases
above are absolute capture frames on both sides and they nearly coincide. So relative to our own
battle start, our art animation is running about seven frames early, or is counting from
something other than battle init while the scroll counts from battle init correctly.

That is a real one-clock-per-thing bug of the same family as the three fixed on 2026-09-07, not
the unrecoverable phase that 7bi settled for. It is very likely the whole of the 86 px that the
backdrop band bottoms out at in the `demo-open` fixture, and it is what makes the magenta
elements appear pink in the real strip and absent in ours at the same frame.

WHERE TO LOOK: `src/backdrop.rs` -- what drives the frame it picks for the animated tiles, and
whether that counter is the same `ticks` the scroll uses. On the real side, the scroll is
`BGScrollCB_BG1Diagonal3to2Scroll` (asm00_0.s:3272-3288) off `eBGScrollCBCounters`, zeroed at
battle init; find what advances the ART and whether it shares that origin.
NOTE the amounts differ slightly too (934 against 884 at the same step), so check the count as
well as the timing -- it may be a second, smaller thing.

### A6. The HUD does not match at a battle's opening
Falls out of A4's measurement and deserves its own number. Real from `/tmp/battlestart.state`
against `demo-open`, `--disable-obj`, HUD strip box (0, 0, 240, 24): **1102 px**, and it looks
static rather than drifting, so it is probably content and not timing -- MegaMan's HP, the chip
counts, the enemy names. `demo-open` already fields that capture's own three Mettaurs, so whatever
differs is something the fixture is not setting up.

LOCALISED, AND THEN LOOKED AT, which should have been the first move rather than the third.
Counting differing tiles said "49 tiles, nearly the whole width" and suggested enemy name
plates. Rendering the two strips one above the other answered it in one glance:

    real   HP box reading 60,  and NOTHING else -- no gauge
    ours   HP box reading 100, and a full CUSTOM gauge with its L-or-R prompt

Two separate things, one of them real:

1. **THE CUSTOM GAUGE SHOULD NOT BE DRAWN DURING THE OPENING.**  *(DONE -- gated on a new
   `window_closed` flag; the strip went 1102 px to 85.)* Measured by rendering the real
   ROM's HUD strip at frames 75, 100, 125, 150, 165, 175 and 185 from `/tmp/battlestart.state`:
   **there is no gauge on ANY of them.** Just the HP box, and backdrop everywhere else. By 200
   the chip window is up and the strip is the chip-select screen. Ours draws the gauge, full,
   from the start. A parity gap, not a fixture problem.
   NOTE the gauge and its "L or R" prompt are the real game's own HUD art, not a debug
   affordance -- the only `cfg!(debug_assertions)` in battle.rs is the L/R shortcut at
   battle.rs:1694, which is a different thing. I checked, because "a debug aid leaked into
   release" would have been the tidier answer.
   STILL OPEN: when the gauge DOES first appear. It should be after the first chip window
   closes -- a battle opens with that window (7aw), so there is nothing for a gauge to do before
   it. Confirming that needs a capture where the window actually closes, and a naive `A` press
   does not do it: the cursor starts on a chip, not on OK, so scripted A presses at 230 and 260
   left the window still open at frame 410. Drive the cursor to OK first.
2. MegaMan's HP: the captured battle's navi has 60, `demo-open` starts at 100. Fixture setup.

Lesson worth keeping: a pixel count tells you how much differs and a picture tells you WHAT.
Two rounds of tile arithmetic here produced a wrong guess that one 8-line render replaced.
The existing `tiles` check uses `demo-hudmatch` against `pausedwithcannon` and reads 0, so the HUD
CAN match -- it is this fixture's setup that does not.


### A5. The battle opening  *(done -- TRANSFER 7ba)*
`demo-open` exists and fields the capture's own three Mettaurs. Measured:

    real   white 0..70, field at 71, viruses 113/141/173, window 173
    ours   fade  0..32, field at 32, viruses  59/ 92/125, window 134

SETTLED AND DONE: the white is the battle's -- the save state's scroll counters read zero,
so init has happened, and the screen is white for 71 frames after. The intro now holds full
white for 71 frames in non-demo builds and in `demo-open`; every other demo keeps the old
black ramp, because their frame offsets were calibrated against it and changing it moved
eight checks at once.

DONE. With the lead-in right the rest came with it, and there was never a second problem:

    first virus starts materialising   frame 76 after init, BOTH SIDES
    it settles                         frame 142,          BOTH SIDES
    chip window opens                  129 there, 130 here

The earlier "22 frames early" and "91 against 113" were the wrong lead-in wearing different
hats. A wrong constant early in a sequence makes everything after it look wrong in its own
way, and each of those looks like a separate bug. Fix the earliest and re-measure before
believing any of the others.

A sampling trap worth remembering: a "brightness" measure reads white as FULL brightness, so
a white screen looks like a finished fade. Measure the colour.


## B. Things the game does that this build does not

### B1. The PAUSE menu
Research is done and sits in `TRANSFER.md` 7ar; this is an implementation ticket.
`sub_802B7A0` (asm03_0.s:10937) fades the screen with `SetScreenFade(0x14, 8)`, raises
banner message 9 or 13 depending on a flag at `[r5,#7]`, and both records are KIND 2 —
which is exactly what makes the banner's phase ticker freeze at counter 4, so the ribbon
sits fully extended for as long as the game is paused (asm00_2.s:27590-27603). Unpausing
calls `sub_801E780`, which forces the counter to 45 and drops it into the hold's tail
wobble and the normal roll-out. It is a real menu, not just a banner: a highlighted
background-tile cursor box (`sub_802B8B0`/`sub_802BA24`, tile ids 0xA0AB/0xD0AB), text
from `TextScript86F0300`, sound effects 0x91/0x92 on cursor moves, and
`SetScreenFade(0x10, 8)` on the way out.
The banner half is nearly free — `src/banner.rs` already carries all 45 messages and the
freeze is one condition. Verify against a capture that presses Start mid-battle.

### B2. Panel damage  *(CLOSED, not reachable -- TRANSFER 7bg)*
DO NOT IMPLEMENT THE CHARGE-SHOT CLAIM. It was read to the end and it breaks at its own
citation. `Unk_03` was peeked and is 0 on every frame (0x02034123, MegaMan's slot) -- the
one part that was right -- so the shot really does carry `Param1` = 1. But `Param1` only
chooses the BRANCH: the default branch then overwrites r2 with
`[RelatedObject1Ptr]->CurState` and passes THAT to `object_setPanelType`
(asm31.s:27869-27873). The panel bookkeeping moves at the hit exactly as it should and the
type stays NORMAL. Only `Param1` in {7, 0x15, 0x16} cracks or breaks, and nothing this
build fields produces those. The charge shot joins the NOT REACHABLE list below.

Two harness notes from the attempt, both worth keeping: `--dump`'s byte count is parsed
with `atoi` and silently reads 0 from a `0x`-prefixed string, so it must be DECIMAL; and
holding B for 150 frames does NOT charge the buster on this fixture, because the Mettaur
re-tracks MegaMan's row -- oscillating rows every ~15 frames through both attack windows
and then holding still is what reaches a full undamaged charge.

The rest of the entry stands as the record of a well-cited claim that did not survive.

### B2 (original research, kept for the record)
`src/field.rs` carries the art for all five panel states and nothing drives cracked or
broken. The research says what is reachable and what is not, and the answer is narrower
and more useful than expected.

MEASURED, AND IT DOES NOT HAPPEN (2026-09-07). The claim below is a static read and the
capture refutes it. On the real ROM, from `/tmp/pausedwithcannon.state` with the enemy kept
alive: move MegaMan out of the shockwave's row so the charge is not interrupted, hold B for
150 frames, release. The charged hit lands visibly -- a starburst on the Mettaur -- and the
panel under it DOES NOT CHANGE, through 140 frames afterwards, with backgrounds on and a
400-pixel threshold on that panel's box. An implementation of the claim was written and
reverted unbuilt-upon rather than shipped.

So something in the chain below is wrong, and the most likely link is the one its own author
flagged: `Unk_03`'s value was inferred, not read -- "I could not find anywhere that resets
`Unk_03`". Before anyone tries again, PEEK IT: find `oAIAttackVars_Unk_03` for MegaMan's slot
in the save state and read what is actually there, and read the `Param1` the spawned shot
actually carries, rather than deriving both from the table. The rest of the entry is kept
because the lifecycle and movement findings are probably still good.

THE CLAIM AS ORIGINALLY RESEARCHED, now known not to reproduce: **MegaMan's CHARGE SHOT sets
the panel it hits straight to BROKEN.** The buster and charge shot both spawn the shared type-0 straight-shot object
(`sub_80C4F02`, asm31.s:27760); on a hit it switches on its own `Param1`, and the default
branch calls `object_setPanelType(hit_panel, Param1)` outright (asm31.s:27864-27874), gated
only on the panel being solid. The plain buster's `Param1` is 0x1d (asm31.s:12531), not one
of the five types, so it does nothing visible. The charge shot's comes from
`byte_80EBD34[Unk_03]` = {1,1,1,1,0xC,0xC,0xC,0} (asm31.s:109578-109611), and a base-tier
shot takes index 0 or 1 -- **1 is PANEL_BROKEN**. No cracked stage at all.

ALSO REACHABLE: the seeds stamp an AREA of panels to their terrain directly
(`object_setPanelType` in a loop, asm31.s:47200-47223, effect ids {4,7,6} for
poison/grass/ice at byte_80CE41E), and VDoll sets its landing panel to POISON
unconditionally (asm31.s:60531-60534). Both bypass the crack lifecycle entirely.

NOT REACHABLE, so do not build it: the Mettaur's shockwave CAN crack (`byte_80C6B00`,
asm31.s:31360-31366: `Param1==4` cracks, `==5` poisons) but `Param1` is the virus's Version
tier via an identity table (asm31.s:171288), and the Mettaur this build fields is Version 0
-- confirmed by its 10-damage shockwave. None of MiniBomb, EnergBom, MegEnBom, BigBomb,
BlkBomb, LilBolr, BugBomb or FlshBom contain any crack/break/setPanelType call at all.

THE LIFECYCLE, for whatever is built: broken goes back to normal after **600 frames** (480
if `GetBattleMode()==1`), from `sub_800C488` (object.s:1541-1549), with an alternating
"about to reform" flag over the last 60 (object.s:1458-1467). A broken panel simply REJECTS
movement onto it, like a wall -- the validity gate wants the solid bit 0x10
(`object_isPanelSolid`, object.s:2703; `playerObjectMovingToPanelValidityRelated_800E618`,
object.s:5112) -- rather than dropping anyone through.

TWO THINGS TO CONFIRM EMPIRICALLY BEFORE TRUSTING THEM. Cracked-to-broken is NOT a timer: it
re-arms every frame and instead tests a cached value against mask 0xF800000 (object.s:
1468-1490), whose bits the struct comments call "support object"/"enemy alliance"/"ally
alliance". Whether that means "somebody is standing here" or "this half of the field is
theirs" was NOT established -- and this project has already been burned once by an occupancy
rule that turned out not to exist (TRANSFER 7ai), so measure it. And nothing was found that
handles a panel breaking UNDER someone already standing on it.

VERIFY LIKE THIS: from `/tmp/pausedwithcannon.state`, fire an uncharged buster at the Mettaur
(expect no panel change), then a charge shot (expect its panel to go straight to broken on
the hit frame, no cracked stage), dumping the panel-type bytes before and after. VDoll can be
poked into the hand for the poison case.

### B3c. The `audio` check  *(resolved -- the check was wrong twice, the wiring's 13% was right)*
The suite hears. `check_audio` captures each side twice -- with the press and without -- takes the
residual sample by sample before the RMS (TRANSFER 7ax's method), and compares the two envelopes
over the sample's body. Want 23620, peak residual 4864 real against 4603 here.

IT FIRST DISAGREED WITH THE MEASUREMENT MADE WHEN THE SOUND WAS WIRED UP -- that one had ours 13%
LOUDER, this one had ours 5% QUIETER -- AND THE CHECK WAS THE ONE THAT WAS WRONG. It was not
soloing the FIFOs, so it measured the whole mix, and the buster's PSG FIRE blip has its own
residual in the same frames. That inflated the REAL side's peak from 3609 to 4864 and flipped the
sign. Soloing channels 4 and 5 (the harness's numbering) fixes it: 3609 real against 4603 ours,
ours louder, the same direction the original measurement found.

THE LESSON, and it is the audio version of a sampling error: a control-subtracted envelope only
measures one sound if that sound is the only one on the channels captured.

AND THEN THE MAGNITUDE WAS THE CHECK'S FAULT TOO. I suspected the real side's capture flags, and
measured it: `--zero`, the alive cheats and `--disable-bg` make NO difference at all, the envelope
is byte-identical with and without them. What differed was the WINDOW. Frames 14..29 here are the
same samples the other measurement called +19..+34 -- the two count "the press frame" differently
-- so this check began five frames after the onset and called a mid-decay value the peak.
Widened to 8..31 it reads 4074 real against 4603 ours: the wiring's numbers, to the digit.

SO THE ORIGINAL 13% WAS RIGHT AND BOTH OF MY CORRECTIONS TO IT WERE WRONG.

AND THEN THE 13% ITSELF WAS FIXED, from the ROM data rather than by fitting. The sound's M4A track
opens `0xBC 0x00, 0xBB 0x4B, 0xBD 0x00, 0xBF 0x40, 0xBE 0x70` -- KEYSH, TEMPO, VOICE, PAN, and
then **VOL 0x70 = 112 of M4A's 0..127** (data/dat37.s:41543, byte_81B8308, the track the
SongHeader for SOUND_HIT_6B points at). So the real ROM plays this sample at 112/127 of full and
this build played it at agb's default 1.0. Predicted 4603 * 112/127 = 4060 against the real 4074,
a third of a percent out; measured after the change, 4001 against 4074, within 1.8%.

AND IT WAS ALSO SIX FRAMES LATE. Printing both residual envelopes rather than only their peaks:

    real  96, 2, 855, 3661, 4074, 3756, 3489, 3468, 3609, 3171, ...   onset at press+10
    ours  0 x8, then 3558, 4001, 3102, 3651, ...                      onset at press+16

`BUSTER_HIT_DELAY` was 9, set against a frame accounting that counted "+k" from a different origin
than this check does. On the check's convention -- press+k on both sides, the same one `buster`
uses to compare the visuals at 0 -- it needed to be 4. Swept, and it is a clean minimum rather
than a plateau: 2 -> 25101, 3 -> 17738, **4 -> 11971**, 5 -> 13160, 6 -> 16607, 7 -> 22207.

`audio` 37223 -> 32562 (volume) -> 11971 (timing). WHAT IS LEFT is that THE REAL SOUND IS ABOUT
FIVE TIMES LONGER THAN OURS. Measured out to press+69, the real residual decays smoothly all the
way to zero rather than plateauing, so it is a sound and not control drift:

    press+8   96 2 855 3661 4074 3756 3489 3468 3609 3171 3188 3107 3007 2127
    press+22  1514 1023 673 701 684 668 662 531 417 329 235 199 206 203 187 293
    press+38  150 133 211 105 314 129 86 88 246 326 103 59 129 47 83 52 41 121
    press+56  37 27 13 20 13 27 23 13 0 24 0 0 19 0

Ours is silent from about press+21, which is right for the sample we play: 1881 samples at
10512 Hz is 10.7 frames. So the real ROM's response to a buster hit is NOT just SOUND_HIT_6B.

AND THE TAIL IS NOT A SOUND AT ALL -- IT IS THE METHOD'S NOISE FLOOR. Controlled for directly:
two IDENTICAL runs subtract to exactly 0, so the harness is deterministic; but a press that makes
NO SOUND (Up instead of B) still leaves 100-300 RMS, spiking to 516, because once the navi has
moved the background music mixes differently and the music is on the same FIFOs the check solos.
The "five times longer" tail was the same order as that floor.

The session that wired the sound up suspected exactly this and I argued against it, on the grounds
that the tail decays smoothly to zero rather than plateauing. A smooth decay to zero is what
divergence noise looks like too. The silent-press control is what settles it, and it should have
been the first thing measured -- it costs one capture.

`AUDIO_FRAMES` now stops at +24, where the sample's ~11-frame body has finished, and `audio` reads
7303 rather than 11971.

WHAT WAS RIGHT IN THE OLD ANALYSIS, kept because the reasoning stands on its own: That was the favoured candidate, mine and the sound-wiring session's
both, and the raw samples rule it out. Residual RMS per QUARTER-frame:

    +10 [662, 36, 16, 1578]      <- the sample's onset, mid-frame, sharp
    +11 [2833, 3482, 4193, 3988]
    +21 [2437, 2114, 2033, 1884]
    +23 [1197, 973, 1151, 695]
    +24 [636, 533, 788, 709]     <- the plateau begins, with NO rise
    +28 [741, 655, 629, 616]
    +31 [408, 343, 273, 273]

A second sample starting at +24 would show an onset like +10's -- a quarter-frame jump of several
thousand. There is none anywhere after +10. The tail is one sound decaying, holding around 600-800
for five frames, then decaying again.

SO WHAT IS LEFT: the real ROM's ONE sound lasts about five times longer than the 1881-byte sample
this build exports and plays. Look at the note command in the track rather than the wave: the
track is `0xDB 0x3C 0x7F 0x8C 0xB1 0x00` (data/dat37.s:41543-41544), where 0xDB is one of M4A's
fixed-duration note commands and 0x3C/0x7F are key 60 and velocity 127. Work out that duration and
what the engine does when the note outlasts its sample -- whether the WaveData loops after all
(this build reads type/status 0 as "no loop"), or the engine holds and re-triggers. That is one
number in the ROM and it decides the whole question.

### B3b. The next sound needs a DirectSound sample exporter  *(exporter DONE; wiring left)*
The buster's FIRE is done (PSG channel 1, matched at +7/+8). The buster's HIT is NOT a blip: it
is on FIFO channels A and B and silent on all four PSG channels, so it is a DirectSound SAMPLE
(TRANSFER 7bb). An attempt to fake it on the noise channel measured 27x too loud and was
reverted.

So the next step is an exporter: read a `WaveData` header and its PCM out of `data/dat37.s`
(`SOUND_HIT_6B`'s is already decoded end to end -- `byte_81597A0`, 1881 bytes, 10512 Hz, no
loop), wrap it as a WAV, and play it through agb's existing mixer with `include_wav!`. agb's
mixer takes 8-bit PCM at 10512/18157/32768 Hz, and 10512 is exactly what the game uses.

AND SOLO FIRST, ALWAYS. `--audio-channel`'s table is 0-3 PSG, 4-5 DirectSound; the numbering is
the harness's, not the hardware's, and reading "channel 4" as "the noise generator" is what
produced the reverted attempt.

DONE: `tools/sample_export.py` and `assets/buster_hit.wav`. The header was verified from the
bytes three ways rather than trusted -- 10512.0 Hz exactly, size 1881 agreeing with the
spacing to the next label in dat37.s, and no loop bit under any convention. NOTE that the
disassembly has NO `WaveData.inc`: it is asm-only and never grew C structs for the sound
engine, so the 16-byte layout comes from the stock M4A struct every GBA game shares, cross
checked against this blob. The signed/unsigned step is the one that bites: GBA WaveData is
SIGNED 8-bit and WAV stores 8-bit UNSIGNED, so the exporter adds 128; skipping that makes
hound subtract 128 a second time and turns silence into full negative -- the DC buzz.

WHAT IS LEFT is src/ work and it is structural: `Battle::update` takes `(&input, &gfx)` and
no mixer, so playing a sample means threading a `&mut Mixer` through it, adding
`mixer.frame()` to the per-frame loop, and measuring the hit's own delay the way
`BUSTER_BLIP_DELAY` was measured (7bb puts the FIFO activity at +11..+23, peaking at +16,
which is NOT the fire blip's delay). `include_wav!`'s path is relative to the crate root, so
it is `"assets/buster_hit.wav"` with no `../`.

### B3a. Sound: the harness can hear now  *(the research is done)*
`tools/mgba_capture.c` has `--dump-audio` and `--audio-channel`; see TRANSFER 7au for the two
gotchas (the advertised 65536 Hz is really 96000, and `struct mCore` has a `USE_DEBUGGERS` ABI
trap). The engine is stock Nintendo M4A, agb's mixer sets up the same DMA/FIFO/timer registers,
and nothing in this project competes for them.

The smallest first step is NOT "export a sample": the buster's fire sound is a PSG square/sweep
blip on channel 0, confirmed empirically. agb had no PSG API when this was written -- there is one
now, `vendor/agb/agb/src/sound/psg.rs`, added for that blip -- so a first sound meant either
a small hand-written PSG driver (register pokes on 0x4000060-0x4000075, in the style
`vendor/agb/agb/src/sound/mixer/hw.rs` already uses for DirectSound) or picking a confirmed
DirectSound effect instead -- `SOUND_HIT_6B`'s sample is already decoded end to end: WaveData at
`byte_81597A0`, 1881 bytes, 10512 Hz, no loop.


## C. Research tickets — read-only, no build, good to run several at once

### C1. How many frames into a battle does BATTLE START! go up?  *(answered -- TRANSFER 7aw)*
`/tmp/battlestart.state` exists now. The answer: it does not follow the intro at all, it follows
the FIRST CHIP WINDOW -- thirty frames after that window closes. The build was corrected and lands
within a frame of the real ROM. The same state also showed that a battle OPENS with the chip
window, which this build was getting wrong by 1260 frames.

Still open from the same state: our window opens at 134 against the real 173, because the captured
battle fields three Mettaurs and this one fields one. A fixture with a matching line-up would
settle the intro's length and the screen fade's real frame count in one go.


### C2. The last frames before the RESULT window  *(mostly traced -- TRANSFER 7bf)*
STATES 6-9 ARE A DEAD END: `off_8008038` is the generic banner sequencer for every message
in the game, and 6-9 are a sibling branch entered only when `sub_800A152()` returns 7, a
different outcome. They never run on an enemy kill.

THE COUNTDOWN IS 94, NOT 102. State 3 picks 0x5e or 0x66 on `BATTLE_EFFECT_SHOW_RESULTS`
(asm00_1.s:10580-10592), and the field-encounter `BattleSettings` row has that bit set
(data/BattleSettings.s:6). So the expiry is 49 + 94 = 143, not 151, and the banner's idle
at 106 is not the binding constraint. Dispatch out of state 3 is free.

WHAT IS LEFT is 14 frames, not 8: the reward tally in `sub_8009478` (asm00_1.s:13129),
waiting on two sentinels driven by a fixed 5-step transfer-buffer decrement
(asm01.s:254-258). Settle it by dumping `dword_203F4A0` and `dword_203F5A0` frame by frame
from 143. This build's measured 110 is unaffected either way, so this is derivation for its
own sake and ranks below anything visible.

### C3. The emotion window  *(researched; see TRANSFER 7at)*
Answered: only Calm and Angry are reachable without a Cross or a Navi Customizer bug, and Angry
needs ~120 continuous frames of hitstun or a single 300+ damage hit, which a Mettaur's 10-damage
shockwave will not produce. So this build's single face is very probably correct for the battle it
fields, and implementing Angry is not worth it until there is an enemy that can trigger it. What
IS worth doing cheaply: `tools/emotion_export.py` takes only state 0's tiles and state 0's palette,
and the other 22 states sit right after at a fixed stride -- exporting them is mechanical.


### C4. Does the chip-name popup's gate match ours?  *(answered -- TRANSFER 7be)*
KEEP THE PROXY. `object_drawChipName` gates on nothing about the chip: `sub_800B892` is a
per-alliance announcer-slot sync byte (object.s:934-939) and `ChipData+9` bit 1 only adds a
damage number beside the name (object.s:210-217). Which chips get a popup is decided by
which OBJECT the chip spawns -- 16 phase tables in the ROM, all of the same shape. 84 of
411 chips carry family 0x15 and they group into exactly those tiers.

WHAT IS LEFT, and only when a trap chip is implemented: those 84 split by `ChipData+9`
bit 1 into "no number" and "number" (Mine, TimeBom, AirRaid, Guardian, AntiDmg, ElemTrap,
...). `NamePopup` draws letters only, so the first trap chip needs one exported bit per
chip and a number in the popup.

---


## D. Harness

### D1. Track the residues in `regress.py`  *(done)*
`mettaur` (345) and `wave` (960) both have checks, alignment done the 7ah way, wants
measured rather than copied. A `cursor` check was added too. Fifteen checks now.


### D5. A short capture used to pass for a real result  *(fixed)*
`capture()` ran mGBA and never checked it wrote the frames it asked for. Under load it
sometimes does not, and a short capture does not announce itself: the frames that exist
compare normally, and the missing ones either raise a FileNotFoundError deep inside a check
or are never asked for at all -- which means a truncated capture can produce a WRONG NUMBER
rather than an error.

Twice on 2026-09-07, a full suite run alongside other heavy work reported failures that did
not reproduce on a quiet re-run: `chips` 10 of 43 off, and `opening` erroring on a missing
frame 148. Both were this. FIXED: `capture()` counts the `.rgb` files and refuses to continue
if the count is short, naming the directory and telling you to re-run it alone.

WHAT IS STILL TRUE AND MATTERS: the suite is not trustworthy while the box is busy. That is
now loud instead of silent, but it is still the case, and the two spurious runs cost more
attention tonight than the bug they pretended to find.

### D4. FIVE CHECKS COMPARED A SINGLE FRAME  *(three widened; two cannot be, for different reasons)*
`tiles`, `field`, `window`, `card` and `result` each match ONE frame and report 0. A single
frame can be right while its neighbours are wrong, and at least one of them demonstrably is.

Measured on `field`, which searches rust 190..240 for the best match against real frame 90:
the winner is exact (rust 212, 0 px), and holding that same lag the next twenty frames read

    0  765 1243 1371 1371 1596 1236 1340 1215 1215 986 582 622 364 364 364 364 838 800 800

Part of that is legitimate -- the Mettaur acts on an RNG the two sides do not share, which is
exactly why `mettaur` and `wave` search for a lag around a specific attack instead of trusting
a fixed one. But "one frame in fifty matched exactly" is a weaker claim than `field 0` sounds,
and nobody looking at the suite would know the difference.

DONE, WITH TWO EXCEPTIONS THAT ARE THE INTERESTING PART.

`window` and `card` are now sixteen frames each with a searched lag, and `window` CAUGHT
SOMETHING: a single frame could not tell lag 181 from lag 182, both being exact at frame 59, so
the check had been sitting on the wrong alignment. Over sixteen frames 181 measures 184 px -- the
bracket's blink toggling one frame out, 92 px a toggle, twice -- and 182 measures 0. Nothing could
have seen that from one frame.

`tiles` is a window now too (390..394 originally, 433..437 today) but for a different reason -- to
absorb boot drift -- and it still compares ONE frame's worth of picture.

`result` CANNOT be strengthened this way, and the check now says so in its own comment. Measured:
over real frames 24..39 the compared region does not change at all, every consecutive difference
is 0. Sixteen frames of a still picture is one frame. Strengthening it needs a window covering the
RESULT screen ARRIVING -- the slide-in, the badge appearing -- and that needs a real capture from
before the window opens, which this fixture's save state does not provide.

`field` cannot either, for the opposite reason: it is too dynamic. Holding its best lag, the next
twenty frames run 765, 1243, 1371, 1596, ... because the Mettaur acts on an RNG the two sides do
not share. It needs an alignment like `mettaur`'s, or a window that ends before the enemy's first
independent decision.

### D3. `--dump`'s byte count silently reads 0 from hex  *(fixed)*
`tools/mgba_capture.c`'s `--dump addr:bytes:file` parses the middle field with `atoi`,
which returns 0 for `0x1c0` and dumps an empty file with no error. The address beside it
uses `strtoul(..., 0)` and does accept hex, so the two halves of the same argument disagree
about their base -- which is exactly the sort of thing that costs an hour. Found during B2.
FIXED: the count uses `strtoul` base 0 as well, and a non-positive count now prints what it
rejected and exits 1 rather than writing an empty file and reporting success. Verified both
ways round -- `0x10` and `16` both dump 16 bytes, and `zero` is refused.

### D2. Make the harness clean up after itself, everywhere  *(done)*
`regress.py`'s rollup check, `chip_compare.py --clean` (which `scoreboard.py` now always
passes) and `throw_dump.py` all delete their captures. `--clean` is opt-in for
`chip_compare` rather than the default because `--no-build` reuses the previous run's
Rust capture. What is left: the ad-hoc capture directories a person makes by hand, which
is what actually filled the disk.


### R1. Rebuild the fixture chain from power-on  *(DONE -- merged fd282eb, 2026-09-12)*

**Why.** `battlestart.state` was lost with /tmp on 2026-09-08. `overworld_net`, `emptyfield_start`
and `chip_ready_empty` are built from it, and the chip/banner/popup rows cannot move off PAUSED's
deleted-enemy artifacts (the shared 14388 baseline) until `chip_ready_empty` exists again. Every
root state should be a recipe: ROM + battery save + inputs from power-on, rebuildable by
`states.py build`.

**Inputs.** `/tmp/bn6f_real.gba` (real ROM) and `/tmp/bn6f_real.srm` (the battery save, 32 KiB,
sha1 e52de245714a...; backed up in /home/box/bn-backup). `mgba_capture --loadsave <srm>` loads the
save read-only and resets the core, so the capture starts at power-on with that save present
(chat history: it reaches the Capcom logo, then the title). Nothing else from the lost states.

**Known anchors (verified by earlier tickets; read their notes in tools/states.py):**
- SubsystemIndex reads 4 on the map, 8 at battle_init, 12 in the battle main loop
  (`emptyfield_start`'s note gives the address it watched).
- Battle frame 0 = `eBGScrollCBCounters` at 0x02009690 / 0x02009694 both 0 (TRANSFER 7aw).
- The encounter roll's gate: one-shot `--poke-at N:0x02001c16:0x2000` and `N:0x02001c18:0` opens
  exactly one roll at frame N. Forcing it EVERY frame freezes GetRNG's draw (the orbit trap,
  HANDOFF §9) -- use one-shot pokes and vary held directions.
- Overworld position: a live u16 pair at 0x02009f62/0x02009f63 moves 1/frame under held Right
  or Down on the net map ('CentralArea1'); 0x02009f5e moves only under Down.
- `tools/mgba_frames.py <outdir> --at <i>` turns a raw frame into a PNG you can look at.

**Do, in order.**
1. **Power-on to the overworld.** Add a `save=` field to `State` in tools/states.py (passed as
   `--loadsave`), then write a recipe from cold boot with `/tmp/bn6f_real.srm` through the title
   and Continue to controllable overworld play. Decide menu presses from RAM where you can
   (SubsystemIndex, a menu/cursor byte you find in the disassembly) and look at a frame only at
   the branch points. Record which area Continue lands in.
2. **To an encounter-capable net area.** If Continue does not land on the net, walk/jack in by
   script. Stop at a state equivalent in purpose to `overworld_net`: SubsystemIndex 4, on a net
   map that can roll random encounters, position counters responding to held input.
3. **A battle's frame 0.** From (2), open one encounter roll with a one-shot poke (sweep the frame
   if the first choice fails) and build to the frame where the scroll counters read 0/0. This is
   the new `battlestart`. It is a DIFFERENT fixture from the lost one unless it rolls the same
   encounter (three Mettaurs); record which EnemySetupArr entry it rolled, and do not claim
   equivalence you have not measured.
4. **Re-root the chain.** Point `overworld_net`, `emptyfield_start` and `chip_ready_empty` at the
   new states (rebase `emptyfield_start` directly on (2) if that is simpler than going through a
   resolved battle). The downstream recipes' frame numbers WILL change -- re-sweep them and
   re-verify every property their notes document: SubsystemIndex 12 held through the capture, all
   enemy HP 0, scroll counters 0/0 at battle frame 0, the chip window opening on its own, a chip
   in hand, MegaMan idle (CurState/CurAction 4,8) at load of `chip_ready_empty`.
5. **Determinism.** For each new or changed state: build it twice from scratch and capture 40
   frames from each build; the frames must be identical (this is how `result_arrival` was
   verified).
6. `python3 tools/states.py build all` builds every state except `noenemy2` with nothing but the
   ROM and the save. `battlestart` stops being a root.

**Out of scope.** Re-pointing any harness row (next ticket), `src/`, `noenemy2` (its reward roll is
unrecoverable by recipe), patching encounter-table entries (HANDOFF §9: it changes which entry a
roll selects).

**Measure and report.** For each state: its recipe (base, save, script, pokes, frames), every RAM
property you verified with the address and value, the determinism result, and the build time.
Then the report shape in AGENTS.md. A step that fails is reported with exactly what was observed,
not worked around.


### R2. Move the chip rows onto the never-had-an-enemy fixture  *(NEGATIVE -- 2026-09-12, rows not moved)*

**Result.** At the event-pinned alignment (canon CurState leaves 0x0804 at frame 3; shot flight canon
19-28 <-> rust 137-146, identical per-frame cadence) the empty route reads 134535 / 5317 / 40 against
the PAUSED baseline 14388 / 2350 / 40. The residue (diffmask worst frame, canon frame 17) is two of the
three Mettaurs mid-dissolve on the right of the field plus the chip-window strip at top left: the
"empty" state is spawn-and-delete (DELETE_ENEMY_3 from load), the death presentation is deferred while
the chip window is open, and it plays across exactly the frames the chip action occupies. The old
43700-44631 plateau was a false-alignment family with a 49-frame period. Measured and rejected:
per-frame zeroing of BattleObject identity (the ROM freezes), `zero=ENEMY_TILES` (120498), seven
script variants (nothing moves the transient; a chip after the dissolve is refused, HANDOFF §9).
Also found: the rust side's shot fires ~33 frames after marker + fire_frame, not at it. GLM-5.3-Flash
worker, 69 turns, $0.098. The ticket as first written follows.

**Why.** Every chip row compares against canon (sterile) loaded from PAUSED, whose leftover
portrait box and Mettaur corpse cost each row the shared 14388/2350 baseline (see ALIGN_CHIP's
comment in tools/harness.py). R1 rebuilt `/tmp/chip_ready_empty.state` (a battle that never had a
live enemy; MegaMan idle, Vulcan1 in hand; `states.py build all` makes it). tools/harness.py already
has the canon side for it, `_chip_canon_empty()` and `library_pokes_empty()`, NOT wired into any
row: the last attempt (read the "NOT WIRED" comment block) searched alignments and plateaued at
~43700-44631 px from two offsets 49 frames apart -- a false alignment or a real residue, never
settled -- which is worse than 14388, so it was left unwired.

**Do, in order.**
1. **Baseline.** `python3 tools/harness.py --only chip-cannon --no-gallery` (expect 14388 / 2350 / 40,
   negative not blind). Then score `_chip_canon_empty("01")` against `_chip_rust("01")` at the old
   plateau alignment on the NEW state, and record that number too.
2. **Pin the alignment by event, not by search.** On the canon side, watch MegaMan's
   CurState/CurAction (0x0203a9b8; idle reads 0x0804) with `--watch` from load under the row's own
   script, and find the frame it leaves idle for the chip action -- that frame (plus whatever fixed
   lead the chip's first visible frame has) is `canon_ref`, measured and written into the Align
   note. On the rust side, the marker origin plus the descriptor's `fire_frame` gives the matching
   frame; use the existing search band only to CONFIRM a unique minimum there, not to find it.
3. **Localize what is left** at that alignment: per-frame totals, and the region of the differing
   pixels (tools/diffmask.py) -- which sprite, which frames. If the residue comes from the two
   fixtures disagreeing (MegaMan's position, HP, palette, a HUD element, the chip in hand), fix the
   rust DESCRIPTOR or the canon Side's pokes so both sides show the same situation, citing the RAM
   value you matched. If it comes from how src/ draws or times something, stop fixing and report it
   with frame and region -- that is a src/ ticket.
4. **Move the rows.** Only if `chip-cannon` on the empty route reads BELOW 14388 with its negative
   not blind: point the shared chip template at the empty route, run every chip row one at a time,
   and report each row's before and after. A row that gets worse stays on PAUSED, with its numbers
   in the report. Then banner and popup, if they can use the same state.

**Rules.** tools/ only (harness.py, and states.py only if a recipe needs a tweak); no src/; never
widen tools/allowlist.py; every changed row keeps a non-blind negative; captures one at a time.

**Measure and report.** The alignment evidence (the RAM watch frames on both sides), the residue
breakdown with frames and regions, every row's before/after line, and the AGENTS.md report shape.


### R3. A battle that never spawns an enemy  *(PARTIAL -- 2026-09-12, branch wt/r3-empty kept, not merged)*

**Result.** The roll's choice lands in `GameState->CurBattleDataPtr` at `0x02001b9c` (stored at
asm29.s:10286, read by `sub_800531C` asm00_1.s:4455). One-shot pokes `70:0x02001b9c:0x4b88` and
`70:0x02001b9e:0x080b` (the roll writes at frame 60, battle_init reads at 76) retarget the battle to
BattleSettings `0x080b4b88`, whose EnemySetupArrPtr is the emptied entry: no enemy BattleObject ever
populates, SubsystemIndex 12, deterministic over 40 frames. BLOCKED: about 20 battle frames in
(capture frame 99) SubsystemIndex goes 12 -> 16, the battle and game state pointers clear, a cutscene
is populated and input goes inert; a no-op poke of the roll's own entry survives 130+ frames, so the
empty enemy list is the cause. Excluded: BattleTerminate01 (0x02038161, stays 0), dispatch_803C620,
the six warp functions, checkCoordinateTrigger_8031a7a, EVENT_16F1, hand contents. Not merged: the
branch replaces R1's working emptyfield_start/chip_ready_empty recipes with ones that cannot finish.
GLM-5.3-Flash, 193 turns, $0.369. Follow-up recon (DeepSeek V4.1 Flash, $0.068):
`docs_recon_teardown.md`. The ticket as first written follows.

**Why.** R2 showed every "empty" canon state so far spawns an encounter and forces its HP to 0, and
the real ROM then plays the enemies' death presentation across the chip rows' frames. The chip rows
need a canon battle whose encounter has no enemy objects at all. `patch_sterile.py
--empty-net-encounter` already empties one table entry (EnemySetupArr `0x080b5306`) in
`/tmp/bn6f_sterile_emptynet.gba`, but no roll has ever landed on it: HANDOFF §9 records that patching
an entry changes which entry a roll selects, and a sweep of one-shot roll frames never reached it.

**Do, in order.**
1. **Find where the selection lands.** In reference/bn6f, follow the encounter roll
   (`sub_80AA4C0`, its `bl GetRNG` at 0x080AA51E, TRANSFER 7aw) to the RAM location that holds the
   chosen EnemySetupArr pointer (or index) that battle_init reads. Cite file:line.
2. **Make the battle use an empty entry, by the smallest change that is honest about itself.**
   Either (a) a one-shot `--poke-at` of that RAM value, applied after the roll writes it and before
   battle_init reads it, or (b) a code patch added to the emptynet ROM variant only (a new
   patch_sterile.py option, documented like the existing two) that makes the selection return the
   emptied entry. Prefer (a) if a poke window exists; do not change what canon or canon (sterile) are.
3. **Prove it is empty.** At the new battle's frame 0 and 100 frames later: no BattleObject slot for
   an enemy is populated (read the slots; show a frame), SubsystemIndex 12 is held, and a chip picked
   through the window FIRES (the premise that makes the chip rows work -- HANDOFF §9 says a chip fires
   in a battle that never had an enemy).
4. **Rebuild the chain on it:** `emptyfield_start` and `chip_ready_empty` (recipes in tools/states.py,
   no DELETE_ENEMY cheats needed any more), each built twice and 40 frames compared for determinism.
5. **Re-run R2's measurement** on the new `chip_ready_empty`: event-pinned alignment exactly as R2
   did it (its method and numbers are in R2's result above), `chip-cannon` on the empty route vs the
   PAUSED baseline 14388. If it is lower with a non-blind negative, move the chip template and report
   every chip row before/after one at a time; rows that get worse stay on PAUSED.

**Rules.** tools/ only; no src/; reference/bn6f is read-only (report addresses, the coordinator
annotates); never widen the allowlist; captures one at a time.

**Measure and report.** The RAM location and the disassembly lines that prove it, the chosen method
and its window, the emptiness evidence, determinism results, and R2's measurement redone.


### R4. Keep the enemy-less battle alive, then finish R3  *(BLOCKED -- 2026-09-12, branch wt/r4-alive kept)*

**Result.** Step 1 done, and it overturns the recon: none of the five literal `SubsystemIndex=0x10`
stores, the warp entry, `cs_warp_cmd` or the script byte-writer is hit at the teardown frames, and
R3's "12 -> 16" was freed-heap fill (0x11/0x22 patterns), not a mode switch. The never-spawn battle
is healthy through the chip window (opens at battle age ~91, BattleState.Index_01 = 8); at age ~102
the game RELEASES the battle -- CurBattleDataPtr (0x02001b9c) clears one frame before
BattleStatePtr/GameStatePtr -- and dispatch stops. BattleTerminate01 stays 0, BC30 stays 0,
`HandlesBattleMain`'s write-0 never fires. Holding GameState[0..3], the alive counts
(BattleState+0x12/13) or the three pointers does not keep it alive. The deciding store runs through
indirect dispatch and `--trace-pc` perturbs this game's timing, so it is unidentified. Details
appended to docs_recon_teardown.md. GLM-5.3-Flash, 129 turns, $0.228. The ticket as written follows.

**Start from R3's branch:** `bash tools/worktree.sh r4-alive`, then in that worktree
`git merge --ff-only wt/r3-empty`. R3's result above and `docs_recon_teardown.md` are your context.

1. **Confirm the teardown path, do not guess it.** The recon's candidate chain (unverified): battle
   ends through `sub_8007850`'s BC30-jump-offset branch (asm00_1.s:9466) -> EnterMap -> a map cutscene
   whose `cs_warp_cmd_8038040_2 byte1=0x0` calls `warp_setSubsystemIndexTo0x10AndOthers_8005f00`,
   whose `strb` at asm00_1.s:5939 writes 16. Use `mgba_capture --trace-pc <addr> --trace-steps N`
   (HANDOFF §5; bounded steps only) on each link, on R3's retargeted battle, and report which
   addresses are hit on which frame. Find the EARLIEST decision point that differs from a battle with
   enemies (R3's no-op-poke control is the comparison).
2. **Intervene at that earliest point, minimally and visibly.** A held RAM value or a one-shot poke if
   one works; otherwise a new `patch_sterile.py` option applied to the emptynet ROM variant only,
   documented like the existing patches (address, original bytes, new bytes, why). Canon and canon
   (sterile) do not change. Show the battle then stays in SubsystemIndex 12 for 600+ frames with the
   chip window opening on its own and a picked chip FIRING.
3. **Finish R3's steps 4-5:** add the never-spawn chain as NEW state names (keep R1's
   `emptyfield_start`/`chip_ready_empty` working and unchanged -- `states.py build all` must still
   build everything it builds today), determinism twice each, then R2's event-pinned measurement of
   `chip-cannon` on it vs the PAUSED baseline 14388; move the chip template only on a real
   improvement with a non-blind negative, every chip row before/after.

**Rules.** tools/ and docs only; no src/; reference/bn6f read-only; captures one at a time.
Report addresses hit, the intervention with its evidence, and the measurements, in AGENTS.md shape.


### R5. A write watchpoint in the capture tool, then find what releases the empty battle  *(PARTIAL -- 2026-09-12, tool merged, release unattributed)*

**Result.** Step 1 done, verified, committed (17dc00f, plus HANDOFF §5 row). `--watch-write addr[:len]`
arms real libmgba byte-granule WATCHPOINT_WRITEs via `mDebuggerAttach` + `platform->setWatchpoint`
(DEBUGGER_CUSTOM is unbuildable through `mDebuggerCreate` -- returns NULL -- so the tool builds the
`struct mDebugger` and attaches it directly); the entered hook logs frame/addr/old->new and the
writing instruction (`_ARMPCAddress`, r15 minus the ARM/Thumb prefetch offset) plus raw r15 and LR,
then returns -- the emulator never pauses. Verified: known-write anchor hit (roll's
`str r0,[r7,#oGameState_CurBattleDataPtr]`, asm29.s:10286, reports `at=0x080AA59E lr=0x080AA6F9`
frame=60, old=0x00000000 new=0x080B4BB8); new binary vs old binary 0 differing frames (90/90,
emptynet roll recipe); with vs without the flag 0 differing frames (90/90; also 179/179 on a second
recipe); harness `--only wave` with the new binary at /tmp/mgba_capture: PASS total 0 worst 0
frames 90, negative not blind (3840) -- identical to the pre-change baseline line. Tool-side
`--poke-at` writes are caught too but report the CPU's stale r15 as `at` (they run between frames).

Step 2 measured, with a negative at its core. Reconciled frame bases first: R4's "age ~102" and R3's
"capture 99" are the same event -- in the live emptynet recipe (overworld_net base, script, pokes at
60/70; emptyfield_start.state is recipe frame 79 = battle age 0) the release is at **battle age 99 =
capture frame 178**, measured three ways (per-frame value dumps, watchpoint hits, frame hashes).
At 178 the five watched words (0x02001b9c CurBattleDataPtr, ba0, ba4, ba8, bac) clear **in one
frame**, and 0x02001b80..b98 become the freed-heap nibble fill (0x11/0x22 patterns) R4 saw -- the
GameState heap block is released at age 99. But the writes produce **zero watchpoint hits** although
the same watches are live in the same frame (a DISPCNT store at 0x08001760 fires at 178; CPU stores
fire at frames 60/70/76/147; a forced DMA3 fill fires; `--poke-at` fires). Excluded as the writer:
CPU str/strb/strh/stm (all shimmed per mgba 0.10.2 memory-debugger.c), DMA (goes through
`cpu->memory.store32`, proven by experiment), SWI RegisterRamReset (no SWI in the frame-178 delta;
IWRAM body not memset; DISPCNT not forced to 0x0080), CpuSet/CpuFastSet (no dest 0x02001bxx in the
logged frame-178 SWI set; HLE runs real BIOS-stub code through shimmed stores). The CPU stays
healthy (normal per-frame SWI cadence, screen updating). So the release write does not go through
any path libmgba's shims can see -- R4's "indirect dispatch" is real: **no game instruction can be
named for the release with this instrument; the writer is somewhere inside libmgba 0.10.2's
non-store paths** (next step: a libmgba built with a guard on `gba->memory.wram` writes, or bisect
mgba internals). Two further findings recorded in docs_recon_teardown.md: (a) the /tmp pre-states
(emptyfield_start, r4_pre*) DERAIL -- PC walks into 0xDE31xxxx garbage -- when loaded directly and
run past battle age ~68, identically on the old and new binary, while live runs continue healthy:
savestate reload is not faithful for this scenario, so state-based probing past age ~68 is unsafe;
(b) R3/R4's reported teardown ages (20-23) did not reproduce in these live runs (pointer block
intact through age 41 with and without the ALIVE cheats); treat the age-99 event as the only
reproducible release in the merged branch's recipe. Steps 3-4 are therefore blocked on naming the
writer from the emulator side. GLM, one session; /tmp/mgba_capture now runs the r5 binary
(backup: /tmp/mgba_capture.bak_r5). The ticket as written follows.

The empty-battle objective R3-R5 is closed per the 2026-09-12 decision; chip rows stay on the PAUSED baseline.

**Why.** R4 narrowed the enemy-less battle's teardown to one event -- `CurBattleDataPtr` (0x02001b9c)
cleared at battle age ~102 -- but could not see which instruction does it: the store is reached by
indirect dispatch, and `--trace-pc` single-steps, which perturbs this game's timing. A watchpoint
fires at full speed and names the writer directly. It is also the base of the state oracle
(HANDOFF §13 step 3): "which instruction wrote this field, on which frame" is attribution for free.

1. **Tool.** Add `--watch-write addr[:len]` (repeatable) to tools/mgba_capture.c using libmgba
   0.10's debugger (`/usr/include/mgba/debugger/debugger.h`: `mDebuggerCreate`/`mDebuggerAttach`,
   `platform->setWatchpoint` with `WATCHPOINT_WRITE`, an `entered` callback that logs and returns to
   RUNNING, frames driven by `mDebuggerRunFrame` or equivalent). Each hit prints one line: frame,
   address, old -> new, and the writing instruction's address (account for the ARM/Thumb pipeline
   offset in r15; print LR too). Must not change emulation: a capture with a watchpoint set must be
   frame-identical to one without. **Verify on a known write:** the roll's store of the chosen
   BattleSettings to 0x02001b9c (asm29.s:10286 per R3) must report that instruction's ROM address.
   Document the flag in HANDOFF §5's table.
2. **Use it** on R3/R4's never-spawn battle (branch wt/r4-alive has the recipe): watch 0x02001b9c and
   the BattleStatePtr/GameStatePtr words around battle age 90-110; name the clearing instruction,
   then walk the LR chain up to the decision that differs from R3's control battle. Cite
   reference/bn6f file:line for each frame of the chain.
3. **Intervene at that decision,** minimally (held RAM value, one-shot poke, or an emptynet-only
   patch_sterile.py option documented like the others), and show 600+ frames of a live battle with
   the chip window opening on its own and a picked chip firing.
4. **Then R4 step 3** (new state names, R1's chain untouched, determinism twice, R2's event-pinned
   measurement of chip-cannon vs 14388; move the chip template only on a real improvement).

**Start from** `bash tools/worktree.sh r5-watch`, then `git merge wt/r4-alive` in it. **Rules:**
tools/ and docs only; no src/; reference/bn6f read-only; captures one at a time; the capture tool
must still build with `gcc tools/mgba_capture.c -o /tmp/mgba_capture -I/usr/include -lmgba -lm`
and every existing flag must behave as before (run `harness.py --only wave` with the new binary).


### R6. The state oracle: first divergent field, not just a pixel count  *(NEGATIVE -- 2026-09-12, measurements valid; acceptance false, branch not merged)*

**Result.** On `wt/r6-oracle` at `c504eee`, the export was pixel-neutral: `wave` 0/0/90 (negative 3840), `window` 0/0/16 (81056), `mettaur` 30864/1566/70 (45233), and `card` 18486/3081/16 (15405), unchanged from `b600251`. The verifier reproduced every number and CONFIRMED the oracle findings: `mettaur` first diverges at `mm_timer` k=0 on the same frame as its first 959-pixel diff; pixel-clean `wave` nevertheless has real state divergences at enemy animation k=24, MegaMan hit state/timer k=43, and enemy state/action k=64. It therefore FAILed the ticket: wave's required no-divergence claim is false, the requested canon battle-frame/action-timer field set is incomplete, several fields are info-only, the block is before rather than after the descriptor, the complete per-field table is missing, and project-local constants have invalid `provenance: derived` tags. Nothing was merged; `/tmp/bnwt/r6-oracle` was removed and branch `wt/r6-oracle` kept. Worker `openrouter/z-ai/glm-5.3-flash:high`: 146 turns, $0.3061; verifier `openrouter/openai/gpt-5.6-sol:high`: 35 turns, $1.0725. The verifier CONFIRMED that a second state-oracle pass may build on the measured divergences, but not that shot/dwell behavior is ready to change.

**Why.** A harness row says how many pixels differ, not which variable went wrong on which frame, so
every timing residue (MegaMan's hit/dwell timing in `mettaur`, the shot dwell gap, `card`'s cursor)
has cost several attempts of guessing. HANDOFF §13 step 3. The empty-battle objective (R3-R5) is
closed without a fix; the chip rows stay on the PAUSED baseline for now, documented, not hidden.

**Do, in order.**
1. **Pick the field set** (start small; every field needs a canon address AND a rust equivalent):
   the RNG word (0x020013f0, HANDOFF §9); MegaMan's BattleObject -- CurState/CurAction (0x0203a9b8),
   panel X/Y, HP, and the animation/action timer that drives hit and shot timing; the first enemy
   slot's state/action and HP (slot at 0x0203aa88); the custom gauge value; the battle frame counter.
   Take offsets from reference/bn6f/include/structs/BattleObject.inc and cite each.
2. **Rust export.** In src/, write those fields every frame into a fixed EWRAM block right after the
   descriptor (the marker is at 0x02000000, the descriptor at 0x02000040 for 64 bytes; see
   src/main.rs's comments on how BATTLE_MARKER is pinned, and pin the new block the same way),
   converted to CANON's units and encodings (a field map, documented next to the block). This must
   not change pixels: `wave` still PASS 0/90, `window` still PASS 0/16, and every other row you run
   reads the same number as before. Constants get `// provenance:` tags.
3. **tools/oracle.py `<row>`**: capture both sides of a harness row with `--watch` on the canon
   addresses and on the rust block, align with the row's own Align (reuse harness.py's machinery),
   and print the first frame where each field diverges, plus a per-field table. **Negative control**
   (AUDIT pair 10): the same comparison shifted by one frame must report a divergence, or the
   oracle is BLIND on that row.
4. **Acceptance.** `oracle.py wave` reports no divergence on every field both sides model over the
   compared frames. `oracle.py mettaur` reports a first divergent field and frame, and that frame is
   consistent with the first non-zero frame of the row's pixel diff (report both). Document the
   command and the field map in HANDOFF §3.

**Rules.** src/ changes only for the export block (no behaviour change); tools/ and docs; never
widen the allowlist; captures one at a time. **Report** the field map with sources, the before/after
lines of every row run, both oracle outputs with their negative controls, in AGENTS.md shape.


### R7. Land the state oracle on the facts R6 found  *(DONE -- 2026-09-12)*

**Result.** Merged `a9d08b7` as `2b35d4b`. The verifier PASSed all numbered acceptance and CONFIRMED behavior neutrality: `wave` 0/0/90 (negative 3840), `window` 0/0/16 (81056), `mettaur` 30864/1566/70 (45233), and `card` 18486/3081/16 (15405), all unchanged. Independent raw-watch parsing CONFIRMED `mettaur` first diverges at `mm_timer` k=0 with 959 first-frame pixels, while pixel-clean `wave` first diverges at enemy animation k=24, MegaMan state/animation/timer k=43, and enemy state/action k=64. It also CONFIRMED the complete field classifications, populated enemy slot `0x0203ab60`, linker-safe chosen export range `0x02000008..0x0200002f`, honest provenance labels, unsupported-row failures, and shifted-control sensitivity. The worker's two field-specific shifted-control descriptions were REFUTED (the controls changed divergence frames/counts, not RNG or enemy X); those claims are not carried forward. `cargo build --release`, Python compile checks, capture-tool compilation, and `python3 tools/states.py build all` passed. Worker `openrouter/z-ai/glm-5.3-flash:high`: 49 turns, $0.0639; verifier `openrouter/openai/gpt-5.6-sol:high`: 39 turns, $1.2914. Per HANDOFF §13 the next permitted objective is usage logging, not behavior changes.

**Why.** R6's measurements and localization were independently reproduced, but its acceptance asked a
pixel-clean row to have state parity and required canon fields that do not exist. Its implementation
also missed several mechanical requirements. HANDOFF §13 still requires a usable state oracle before
usage logging or behavior tickets. This is the second and last attempt on that objective.

**Do, in order.**
1. Start with `bash tools/worktree.sh r7-oracle`, then cherry-pick R6's implementation commits
   `325581f`, `185f352`, and `c504eee`. Treat R6's measured divergences as tests, not as behavior to
   fix. Audit the diff against this ticket before changing it.
2. Make the field contract honest and complete. For every requested R6 field, cite the canon address
   and Rust source/encoding, or print `unsupported` with the evidence R6 established. A canon battle
   frame and the enemy's timing countdown are unsupported; do not invent equivalents. Distinguish
   parity fields from information-only fields, and print every field in the per-field table even when
   it matches. Keep the verified populated enemy slot `0x0203ab60`; document why `0x0203aa88` is empty
   for these PAUSED fixtures.
3. Keep the behavior-neutral export in a demonstrably free fixed EWRAM block next to the marker. R6
   found that `0x02000080` collides with agb's `SPRITE_LOADER`; use the verified-safe
   `0x02000008` marker padding unless a linker-map proof finds a safer adjacent address. Correct every
   stale address in code and docs. Canon-derived constants need exact ROM/disassembly provenance;
   freely chosen project protocol/layout constants must be labelled as chosen, not falsely
   `provenance: derived`.
4. Make `tools/oracle.py <row>` print the full field table and a first-divergence summary. Its negative
   control must prove sensitivity by changing the nominal result when shifted one frame; merely seeing
   any divergence on an already-divergent nominal row is BLIND. Support `wave` and `mettaur`; fail
   loudly on unsupported rows. Document the command, block layout, comparison contract and unsupported
   fields in HANDOFF §3a.
5. **Acceptance.** Baseline first, then final: `wave` remains 0/0/90 with negative 3840, `window`
   0/0/16 with 81056, `mettaur` 30864/1566/70 with 45233, and `card` 18486/3081/16 with 15405.
   `oracle.py mettaur` reports `mm_timer` k=0 and the same frame's 959-pixel first diff.
   `oracle.py wave` reports pixel total 0 while showing enemy animation k=24, MegaMan hit
   state/timer k=43, and enemy state/action k=64. One-frame shifted controls must measurably alter
   those outputs. If any verified value changes, report it precisely rather than fitting alignment or
   changing behavior.

**Rules.** src/ only for the export block and conversions; no battle/animation/timing behavior change;
tools/ and HANDOFF.md; no canon, state, recipe, allowlist, alignment, region, asset, or Cargo changes;
captures one at a time. **Report** changed paths, the full sourced field map, before/after harness
lines, both complete oracle tables and shifted controls, in AGENTS.md shape.


### R8. Usage logging: primitive profiles for the 43-chip corpus  *(WITHDRAWN -- 2026-09-12, no worker ran)*

Opened by the pi coordinator from HANDOFF §13 step (4), which meant logging TOKEN SPEND per ticket
and role, not instrumenting the game's battle primitives. Withdrawn by the Claude Code coordinator
before any worker ran; the pi coordinator had already stopped itself on its $3 child-spend cap. Spend
accounting comes from pi's session files and `subagent-artifacts/*_meta.json`; a ledger script is a
small coordinator chore, not a ticket.


### F1. MegaMan takes a hit one frame late  *(DONE -- merged d3f25e1, 2026-09-12; mettaur residue moved to F2)*

**Why.** The state oracle (R7, `tools/oracle.py`) localizes the `mettaur` row's 30864 px -- HANDOFF
§10 already says that residue is entirely MegaMan's side -- and shows the same defect hidden on the
pixel-clean `wave` row: canon enters MegaMan's hit state at wave k=43 (state/action (4,3), timer 22,
HP 60 -> 50), our ROM one frame later at k=44 (HP 90 -> 80). On `mettaur` the first divergent field is
`mm_timer` at k=0 (canon 7, rust 0, 7/70 frames), the same frame as the row's first 959 px.

**Do, in order.**
1. **Baseline:** `python3 tools/oracle.py wave` and `python3 tools/oracle.py mettaur` (record both
   tables and negative controls) and the rows wave, window, mettaur, card, field, cannon (record every
   line). This is the before.
2. **The fixture half.** FIELD_ROW in tools/harness.py (the descriptor `wave` and `field` use) gives
   MegaMan 100 HP; canon's state holds 60 before the hit. Peek canon's value, set the descriptor to it
   with a `peeked` provenance note, and show that no pixel row changes (HP is not drawn in `wave`'s
   BG2-only comparison -- prove it rather than assume it).
3. **The timing half.** Find where canon decides a hit lands and enters the flinch on the SAME frame
   (the hit/collision resolution and `object_subtractHP` asm00_2.s:23756, flinch asm00_2.s:18294 --
   src/actor.rs's `take_damage` cites both; use `--watch-write` on MegaMan's CurState/CurAction
   0x0203a9b8 and HP to name the writing instructions and their order within the frame). Compare the
   order of operations in our battle update (src/battle.rs / src/actor.rs): which step runs a frame
   later. Fix the order in src/, citing the asm lines.
4. **Acceptance.** `oracle.py wave`: MegaMan's state/action, anim and timer no longer diverge at k=43
   (report any remaining divergence exactly). `oracle.py mettaur`: `mm_timer`'s divergence count and
   the row's pixel total both fall; report the new first divergent field. wave and window still PASS 0
   with non-blind negatives; card unchanged; every other row reads the same or lower -- a row that gets
   worse is reported with its numbers, not hidden. Negative controls still change the result.

**Rules.** src/ for the timing fix, tools/harness.py for the descriptor value only; no allowlist
change; no alignment or region change; captures one at a time. **Report** the watch-write evidence of
canon's in-frame order, the src/ change with asm citations, both oracle tables before and after, every
row's before/after line, in AGENTS.md shape. **Coordinator:** this ticket changes Rust; if the first
attempt ends PARTIAL, dispatch the second attempt with `model: "openrouter/openai/gpt-5.6-sol"`.

**Result.** PARTIAL; branch `wt/f1-hitlate` is retained unmerged at `fc0065f`. Clean detached
`verify_rows.py` PASS reproduced wave 0/0/90 (negative 3840), window 0/0/16 (81056), mettaur
30864/1566/70 (45233), card 18486/3081/16 (15405), field 1048/177/40 (1225), and cannon
14388/2350/40 (21543). The hop-frame change took wave's MegaMan state/action, animation, panel and
timer oracle mismatches to zero, but mettaur stayed 30864/1566 with `mm_timer` different on 7/70,
so acceptance was not met. The Sol verifier REFUTED the report's commit attribution and claimed canon
operation order (`9276015` is the HP fixture, `fc0065f` the timing fix, and canon writes HP before
flinch state/timer), while supporting the substantive hop-frame fix and unchanged lethal structure;
it REFUTED describing the HP fixture as publication-only/input-neutral because 100 -> 60 changes the
initial emulation state, although the reproduced wave/mettaur pixels were neutral. It CONFIRMED the
blocker: both attack cycles are 106 frames, the permitted 295..324 pairing compares incompatible
120-frame mercy histories, and the equivalent object-phase minimum is offset 203 outside the band.
The generic travelling-shot/lethal paths remain a regression risk; the workers' all-67-rows and
integrated-field assertions were outside the independent row reproduction. Worker 1 used
GLM-5.3-Flash high, 137 turns, $0.240187875; required worker 2 used GPT-5.6-Sol high, 20 turns,
$0.836421800; verifier used GPT-5.6-Sol high, 26 turns, $1.383901000; children total $2.460510675.


### F2. The mettaur row compares the wrong Mettaur attack  *(DONE -- merged 332e658, 2026-09-12)*

**Why.** F1's verified finding: both sides run the same 106-frame Mettaur attack cycle (canon attack
animations start at canon frames 32, 138; ours at battle frames 95, 201, 307, 413). The row's Align
(canon_ref 140, search band 295..325, chosen offset 309) pairs canon's SECOND attack with our THIRD.
Canon's MegaMan is still in the 120-frame mercy from the hit at canon frame 114 (the first attack);
ours took its first hit at battle frame 176 and its third-attack wave falls outside that mercy, so the
two sides are in different situations for the whole window. An equivalent object-phase minimum exists
at offset 203 (second attack <-> second attack), outside the band.

**Result.** DONE and merged as `332e658`; implementation commit `c335e49`. Events
measured from `--watch` captures of the row's own sides: canon attack anims start at
canon frames 32 and 138, MegaMan hit at canon frame 114 (HP 60->50, 120-frame mercy,
next hit 234); rust attack anims at battle frames 95, 201, 307, 413 (capture = battle +
8, marker origin 8), hit at battle 176 (HP 60->50, next 388). Both attack-2s fire
inside the attack-1 mercy, so attack 2 <-> attack 2 is the event pairing; with
canon_ref=140 unchanged, rust attack-2 start (capture 209) gives offset 203. The band
was re-centred to range(193,214) and CONFIRMS a unique V-minimum exactly at 203 (202:
47063, 203: 31075, 204: 37873 over 70 frames). The old offset 309 scored 30864 --
LOWER, and not chosen: it pairs incompatible attack indices (canon attack 2 vs rust
attack 3, different mercy situations). After: 31075 / 1566 / 70, negative not blind
(46554); oracle at the new pairing: mm_timer first divergence k=0 canon=7 rust=6
(the known 1-frame-late hit -- rust's hit capture 184 pairs with canon 113 vs canon's
own 114), 7/70 frames; enemy_anim k=61 1/70; everything else matches 70/70; the
shifted control changes the result (mm_timer 7 -> 0 frames). The residue is MegaMan's
mercy blink phase, 766-px chunks, worst frame k=11 (1566 px), region x 1..77 y 70..113
-- src/ territory, unchanged by this ticket. The row's total moved 30864 -> 31075
(+211): the ticket predicted this may not go down, and the score is not the criterion
-- the pairing is. Clean detached `verify_rows.py` PASS reproduced mettaur
31075/1566/70 with non-blind negative 46554, and `states.py build all` passed. The Sol verifier
CONFIRMED all three claims: offset 203 is attack 2 <-> attack 2 with equivalent 120-frame mercy
history and is derived from events rather than score; old 309 is attack 2 <-> attack 3 with
incompatible histories while 203 is the unique minimum in 193..213; and timer 7/6 is exactly a
one-frame phase residue. It judged acceptance met and safe to merge, but warned that the residue's
source-level cause and direction are unverified, so "late" is not a sound premise for a next fix.
Worker: GLM-5.3-Flash high, 30 turns, $0.019362545; verifier: GPT-5.6-Sol high, 23 turns,
$1.019545900; children total $1.038908445.

**Do, in order.**
1. **Baseline** `harness.py --only mettaur` and `oracle.py mettaur` (30864 / 1566 / 70; first
   divergence mm_timer k=0).
2. **Pair by event, not by score.** Define the pairing from measured state on both sides with
   `--watch`/the oracle block: the same attack index since battle start, AND MegaMan in the same
   mercy/HP situation (canon: hit at frame 114 from attack 1, HP 60 -> 50; ours: hit at 176 from
   attack 1). Derive the rust offset from that pairing; the search band may only be re-centred on it
   to CONFIRM a unique minimum, with the note saying why it is where it is (HANDOFF §3 "Adding a row").
   Report the score at the old offset and at the event-derived one; do not choose by the lower
   number.
3. **Acceptance.** The Align note cites the event evidence; `oracle.py mettaur` at the new pairing
   reports MegaMan's fields, with the first divergent field (if any) and frame; the row's negative is
   not blind and the oracle's shifted control changes the result. Report whatever total results --
   lower, equal or higher -- with the region of what remains.

**Rules.** tools/harness.py (this row's Align only) and docs; no src/; no allowlist change; do not
change any other row. **Report** the event evidence on both sides, old vs new Align and scores, both
oracle tables, in AGENTS.md shape. **Coordinator:** verify_rows plus the Sol verifier on the pairing
claim; this is a judgment about alignment (AUDIT's "no boxes in time"), so the verifier must confirm
the pairing is by event and not by score before any merge. No model escalation on a PARTIAL.


### F4. The opening row reads 1160 px since R1 rebuilt its canon state  *(DONE -- fixture fix landed, isolated 0; the integrated residue filed as A9, 2026-09-12)*

**Why.** `opening isolated` read PASS 0 over 40 frames against the lost `battlestart.state` (HANDOFF
§10). The 2026-09-12 gallery run reads **1160 / 29 / 40** (integrated 73659 / 2720) against R1's
rebuilt state -- same three Mettaurs, different history and RNG. No code change touched the opening;
the canon fixture changed. **Do:** localize the 1160 px (frame, region, which element) with diffmask
and the oracle; decide from measurement whether the row's descriptor, its Align, or our opening
differs from what the rebuilt canon state shows; fix the fixture side if the state is the difference,
or file the src/ defect with its frame and region. No allowlist change.

**Result.** The 1160 was the FIXTURE, not the opening. Localized frame by frame over the row's own
captures: every one of the 40 frames differs by exactly the same static 29 px at x 19..30, y 3..12 --
the HP box's digits. Canon's rebuilt state holds **0x0064 at 0x0203a9d4** (MegaMan object +0x24;
note `--peek` at load reads 0 there because the intro has not populated the object -- read it from a
200-frame capture's `--dump` instead) and draws "100"; the descriptor's `megaman_hp=60` was peeked
from the LOST state (TODO A6) and drew "60". `OPEN_ROW` now carries 100 (peeked), and also carries
the state's own RNG -- ePrimaryRngSeed (0x020013f0) reads **0x14ca0f46** at the rebuilt state's frame
0 (`--peek` at load) -- which `fixture_cheats()` now delivers at descriptor +58 (src/fixture.rs has
read the field since the wave 3d ticket; the harness never wrote it; descriptors without `rng` are
byte-identical, 0 stays "our default seed"). After: `opening isolated` **PASS 0/0/40**, negative not
blind (86591). Integrated moved 73659/2720 -> 72499/2691 and the REST IS NOT FIXTURE -- the rebuilt
state's spawn cells and the enemy HP readout's timing, both filed as **A9** with frames and regions.
The oracle (tools/oracle.py) supports wave/mettaur only and fails loudly on `opening`, so the
localization was done with the row's own captures (harness.run, kept dirs) plus `--dump`/`--peek`
peeks of the canon state instead.

**Coordinator verify (2026-09-12).** `verify_rows.py wt/f4-opening` from a clean detached rebuild:
PASS -- opening 0/0/40/86591 MATCH, wave 0/0/90/3840 MATCH, chip-cannon 14388/2350/40/21543
MATCH, no BLIND negative. No Sol verifier: the merged claim is harness lines plus peeked fixture
provenance, and A9's spawn-cell/RNG hypotheses are explicitly unverified and F5 does not build on
them. Merged as `61e1fdd`; the branch also carried stale reversions of `.pi/coordinator.md` and
`tools/pi_coordinator.sh` (it predated main's spend-cap commit -- out of ticket scope), and the
merge kept main's cap-enforcing versions. Worker GLM-5.3-Flash high, 67 turns, $0.077.


### F5. The chip rows' fixture: fire a chip after the corpse has dissolved  *(PARTIAL -- 2026-09-12; gate commit 28a6104 landed via the F5b merge, branch deleted)*

**Why.** 28 chip rows read exactly 14388 and 11 more read 14388 plus their own residue. The 14388 is
canon's fixture, not our code: from PAUSED, a 528 px portrait box (canon frames 43-48) and the deleted
Mettaur's dissolving corpse (frames 43-52) sit inside every chip row's window (read ALIGN_CHIP's long
comment in tools/harness.py in full first). A state saved after the dissolve clears both, but then the
game refuses every chip press. The previous ticket found the refusal path -- `sub_800938A`
(asm00_1.s:13037) forces CurState back to idle when the banner sequencer `sub_800801C` returns 6 -- yet
patching that compare did not restore firing, and it stopped for lack of a tracer. R5 added one
(`--watch-write`, HANDOFF §5), and `--trace-pc` exists. The empty-battle route (R3-R5) is closed.

**Do, in order.**
1. **Baseline:** `harness.py --only chip-cannon` (14388 / 2350 / 40) and two more chip rows.
2. **Find the real gate.** Build (with tools/states.py, a recipe, no hand-play) a sterile state past
   the full dissolve (portrait and corpse both 0 at load, as the comment's frame-110 state). Press A
   and use `--watch-write` on MegaMan's CurState/CurAction (0x0203a9b0+8/+9) and on the banner
   sequencer's state (`dword_203CA70`) plus `--trace-pc` on `sub_800938A`'s branches, to name the
   instruction and condition that refuses the fire. Compare with a press that fires (from PAUSED before
   the dissolve). Cite reference/bn6f file:line for each step.
3. **Intervene minimally, on the sterile variant only.** This ticket is authorized to add ONE option to
   tools/patch_sterile.py (address, original bytes, new bytes, and why, like the two existing patches)
   that lets a chip fire in this situation, or a one-shot poke if one works. Canon itself never changes.
   Report the intervention prominently: it changes what "canon (sterile)" is for the rows that use it.
4. **Re-point and measure.** Point the chip template at the new state and ROM variant; pin the canon
   alignment by the fire event (MegaMan's CurState leaving idle, as R2 did); run every chip row, one at
   a time, before and after. A row may only move if its negative stays non-blind. Report each row.

**Rules.** tools/ only; no src/; no allowlist change; captures one at a time. **Coordinator:**
verify_rows on every chip row plus the verifier on the gate claim and on the patch being the minimal
one; a PARTIAL from a wrong guess about the gate gets a follow-up ticket, not an escalation.

**Result.** The prescribed route is dead, the gate is found (with corrections), and the next
intervention is named but untested. Baselines: chip-cannon 14388/2350/40 (neg 21543), chip-vulcan
14388/2350/60 (18314), chip-sword 14388/2350/40 (18435) -- region canon frames 43-52, OBJ layer
(portrait box x0-150 y0-30 frames 43-48, corpse x149-196 y70-120 frames 43-52), rust side empty
there. Corrected gate: sequencer 0x08 (`sub_80080D2`) refreshes the TWO alliance players' AIData
via `sub_8012DFC` x2 (not every object); all-dead (`sub_800A152`==1, Unk_3a==0) advances to the
94-frame RESULT countdown 0x0C at ROM 0x0800811C (`mov r0,#0xC; str r0,[r5]`, asm00_1.s:10547-48);
state 0x0C (`sub_80081A4`) never refreshes AIData; `cmp r0,#6` at 0x80093A2 is irrelevant.
The opt-in `--hold-banner` NOP holds 0x08 through frame 129 but freezes corpse+portrait forever,
and the held battle's FSM dispatcher (`sub_8009158`) stops after save/reload; refilling 0x0203ca78
keeps 0x0C and does not restore firing. verify_rows PASS: all three rows MATCH, negatives non-blind.
Sol verifier: gate REFUTE-as-written / core SUPPORTED (scope + stale cites corrected above); patch
CONFIRM (default output byte-identical, exactly 4 bytes change) with one doc defect
(patch_sterile.py:74-76 falsely claims the hold produces a clean firing state); impossibility
REFUTE -- a one-shot poke to MegaMan's AIData pressed field in 0x0C after cleanup was never tested
though F5 allowed it, and that is F5b. Worker GLM-5.3-Flash high, 143 turns, $0.413; Sol verifier
GPT-5.6-Sol high, 14 turns, $0.365 (plus a $0.020 GLM pre-check on the wrong role, superseded).


### F5b. Fire a chip in state 0x0C by delivering the press to MegaMan's AIData directly  *(DONE -- 2026-09-12, merged; 27 chip rows to 0, every other chip row improved, none worse)*

**Why.** F5's verified core: chips fire only while the banner sequencer is in 0x08, because 0x08
(`sub_80080D2`) refreshes the alliance players' AIData from the joypad mirror every frame and 0x0C
(`sub_80081A4`) never does -- firing stops for lack of input delivery, not because of the countdown
(the 0x0203ca78 refill test excludes expiry as the first gate). The Sol verifier REFUTED the
categorical impossibility claim on one ground: nobody has tested a one-shot poke to MegaMan's
AIData pressed field in 0x0C after the cleanup, though F5 allowed a one-shot poke. That test is
this ticket. (Corrected scope: `sub_8012DFC` serves the two alliance players, not every object;
true cites mov/str asm00_1.s:10547-48, `sub_80081A4` 10617, `cmp r0,#6` line 13137.)

**Do, in order.**
1. **Start** with `bash tools/worktree.sh f5b-aidata`, then `git merge --ff-only wt/f5-chipfire`.
   First fix the branch's Sol-recorded doc defects on your branch and commit: patch_sterile.py:74-76
   must say the hold FREEZES the dissolve and kills dispatch (dead end, not a clean firing state),
   and the docstring's line cites/scope corrected as above. Default patch output stays byte-identical
   (prove with cmp, as before).
2. **The untested intervention.** Build (tools/states.py, a recipe, no hand-play) a sterile state past
   the full dissolve (portrait and corpse both 0 at load, sequencer in 0x0C). At a chosen frame apply
a one-shot poke to MegaMan's AIData JoypadPressed (with the A press in the mirror, as a player
   press would be) and use `--watch-write` on CurState/CurAction plus the sequencer word to show the
   fire path (`sub_800FB54` -> `object_setAttack2`, CurAction 0x08->0x14) or the exact refusing
   condition. Cite reference/bn6f file:line for each step, and compare against the A@40 firing press.
3. **If it fires on a clean field:** re-point the chip template at the new state and ROM variant, pin
   the canon alignment by the fire event (MegaMan's CurState leaving idle, R2's method), run every
   chip row one at a time before/after, and move only rows whose negative stays non-blind.
4. **If it refuses:** report exactly what was observed (which instruction/condition fails) -- a precise
   negative, no further intervention, no second patch idea.

**Rules.** tools/ and docs only; no src/; F5 already spent the one authorized sterile-patch change,
so no new patch_sterile.py option -- one-shot poke or held RAM only; canon never changes; no
allowlist change; captures one at a time. **Measure and report** the poke address/frame, the
watch-write fire/refusal trace, every moved row's before/after line, in AGENTS.md shape.
**Coordinator:** verify_rows on every moved row plus the Sol verifier on the fire-after-clean claim;
a second wrong guess ends the 0x0C route (options then, not a third attempt).

**Result.** The Sol-named gap closed with a measured fire. Poke `--poke-at 3:0x020340a4:0x0001`
(AIData JoypadPressed, ptr live from 0x0203aa08) + mirror 0x02036822 on `afterdissolve_0x0c`
(sequencer 0x0C, dissolved field) gives the identical chain as the A@40 control: Unk_44 0->0x4 at
0x0800FFEA, CurAction 0x08->0x14 at 0x0801169A via `sub_800FB54`->`object_setAttack2`, attack ends
frame 37 (minor: the end-frame cite is uncommitted, fire verdict unaffected). 27 chip rows PASS 0/0
(was 14388/2350); suprvulc 2464/177/113; bombs/seeds/vdoll 10-8338; energbom/megenbom 19958/1871;
0x15 rows 14740-73481 -- no row worse, none on PAUSED; wave/opening still 0, cannon 14388.
verify_rows PASS on all 43 moved rows + wave/cannon/opening canaries from a clean rebuild, no BLIND
negatives. Verifier (role default) CONFIRMs fire/scope/method with two recorded flags: the stale
.pi/coordinator.md hunk was dropped at merge (main's verifier-role text kept), and the 5 POPUP rows
now blank canon's popup against rust's drawn one (numbers stand; the popup ticket starts there).
Offset 122 confirmed in the merged-main caption; chip-cannon PASS 0/0/40 on merged main; gallery
GIFs for moved rows stale until the publish step. Worker GLM-5.3-Flash high, 131 turns, $0.219;
verifier Muse-Spark high, 39 turns, $0.403.


### F6. tiles/gauge isolated: 538 px over 8 frames  *(DONE -- 2026-09-12, merged; 208/208/8, residue is only the documented vblank frame)*

**Why.** `tiles` and `gauge` are the same full-screen capture (see `_tiles_gauge()`'s note) and both
read 538 / 208 / 8 isolated. Small, self-contained, two rows at once. **Do:** localize the 538 px with
tools/diffmask.py and the oracle (which frames, which element -- the custom gauge's stripe-flow is the
known TODO A8 candidate); find canon's routine for that element in reference/bn6f; fix src/ with the
citation; re-run tiles, gauge, wave, window and the full table (nothing worse). No allowlist change;
the integrated variants' allowlist entries stay until their own tickets.

**Result.** Landed at the documented residue. `sub_801C4e4` (asm00_2.s:26351-26423, slot 4 of
off_801BF88) draws bar `0x9232+((t div 7)&3)` via SWI Div and marker `byte_801C6C0[t&8]` off one
counter t at 0x02035280, no phase; src/hudtiles.rs runs it verbatim on gauge_tick
(BAR_PHASE/BAR_EXTRA/MARKER_EXTRA deleted, fitted 18->15; MARKER_FRAMES also deleted, derived
145->144). Exclusion proved: old shapes need phase s == 6 (mod 28) and s == 1 (mod 16), no
solution. Fixture seeds gauge_tick=50 from the measured flip (t_used=98+c; seed=(30-428) mod
112). Residue 208 px = HANDOFF-9 vblank frame k=7 only, k=0..6 exactly 0. verify_rows PASS
(tiles/gauge 208/208/8, wave 0/0/90, mettaur 31075 unchanged, negatives non-blind). Verifier
CONFIRMs mechanism/exclusion/seed; flags stale A8 wording left in fixture.rs docs and harness
captions (says defect unresolved -- under-claiming, rides the next caption pass). Full table
re-run: every other row identical to F5b. Worker GLM-5.3-Flash high, 84 turns, $0.117; verifier
Muse-Spark high, 33 turns, $0.421.


### F3. After the chip window closes, a faded copy of it stays on the field  *(DONE -- 2026-09-12, merged; ghost layer exact 0, row 977410->695603, residue is fixture content)*

**Why.** Playing the release ROM from power-on (tools/battle_gif.py's tour: pick FireSwrd, Start to
OK, A), the window slides out after "Sending chip data" and then a faded copy of it -- the window's
panel, chip grid and OK button, in other palettes -- appears on the left of the field at about frame
320 and stays for the whole battle. No harness row covers the window CLOSING: `window`/`card`/`cursor`
stop while it is open, and the integrated rows use flags that skip the opening window entirely.
Unverified: that canon shows nothing there (it should not, but that is the measurement).

**Do, in order.**
1. **Measure it.** Build a row that compares the close: canon from `chipselect.state` (the window open
   mid-battle) pressing through to OK exactly as a player does; our ROM with the descriptor's "open with
   the chip window" flag and the matching presses; align on the close event (a RAM value that marks the
   window leaving, found by --watch/--watch-write on both sides), and compare full screen for the
   frames after it. Negative not blind. Record the number and the region.
2. **Find why our layer keeps the tiles.** Which BG layer and tile/map range hold the ghost after the
   slide-out (dump VRAM/BG control registers at that frame), what canon does to that layer when the
   window leaves (the routine that clears or hides it -- cite reference/bn6f), and what our custom
   window code does instead (src/custom.rs and wherever the window's BG layer is set up).
3. **Fix it in src/,** citing the canon routine, and re-run: the new row, `window`, `card`, `cursor`,
   `wave` (still 0), and the full table (every row the same or better; a row that gets worse is
   reported, not hidden).

**Rules.** src/ for the fix; tools/harness.py for the new row; no allowlist change; captures one at a
time. **Coordinator:** verify_rows plus the verifier on the canon routine claim; a PARTIAL from a wrong
guess about the cause gets a follow-up ticket, not an escalation.

**Result.** The ghost is gone by mechanism, not masking. Old `vacate()` tested a 128-px scroll the
slide never reaches, so no column ever cleared and the whole window map reappeared on BG3 at
scroll 0; new `vacate()` clears leftward per (c+1)*8<=x, matching canon `sub_8026BF4`
(asm03_0.s:1026-1052, blank tile byte_8026C88, set->1 / clear->2 cadence) -- verifier CONFIRMED
against the disassembly and decomp. windowclose 977410/33380 -> 695603/28784 (neg 778748,
non-blind); the window's own layer is exact 0 over all ten slide frames, and the post-close 1402 px
is fixture content (descriptor gauge=1 vs canon's empty/refill; our 'Cannon 40' chip name vs none).
Full table identical to F5b/F6 except cursor 620802->620914 (+112): vacate cannot run there (no OK
press -- premise CONFIRMED), race-noise acceptance plausible with the one-frame localization
UNCHECKED. verify_rows PASS (windowclose/window/cursor/wave/card, all non-blind). Merge carve-outs:
the branch's or_spend.py rewrite and TODO F7-F15 deletion never landed (merge kept main); the gif
caption was reverted as out of scope and the inverted bit-2 comment fixed. Unverified: whether
canon's post-close gauge reset/refill is src/ behaviour or fixture -- the windowclose residue's
next question. Worker GLM-5.3-Flash high, 113 turns, $0.204; verifier Muse-Spark high, 28 turns,
$0.346.


### F7. The legacy `cannon` row still compares against PAUSED: 14388  *(DONE -- 2026-09-12, merged; 0/0/40)*

**Why.** F5b moved all 43 chip rows onto `afterdissolve_0x0c` (27 now 0) but the separate ported
`cannon` row (PORTED_CHECKS, `_cannon_canon`) still uses PAUSED and reads 14388 / 2350 / 40 -- the same
fixture artifact. **Do:** point `cannon` at the same route and Align method F5b used for `chip-cannon`
(or show why it cannot), baseline and after, negative non-blind. tools/harness.py only.

**Result.** Exactly as predicted: `cannon` re-pointed onto F5b's route and Align (`_chip_canon_0c("01")`
+ `ALIGN_CHIP_0C` on `afterdissolve_0x0c`), 14388/2350/40 -> PASS 0/0/40 (neg 9505, non-blind);
`chip-cannon` re-reads unchanged 0/0/40 with the same negative, so the whole 14388 was PAUSED
fixture artifact. verify_rows PASS on both from a clean rebuild. Harness-lines-only claim, no
verifier. Worker GLM-5.3-Flash high, 19 turns, $0.009.


### F8. `field` isolated: 1048 px over 40 frames  *(DONE -- merged 8a03b3f, 2026-09-13; field 1048->0/0/40, integrated improved)*

**Result.** DONE. field isolated 1048/177/40 -> PASS 0/0/40 (negative 1139, not blind); field integrated 397357/26479 -> 368525/23784 (allowed AUDIT-6, improved). Mechanism: the residue was canon's own deleted-enemy battle resolving -- sequencer 0x08->0x0C at canon frame 47, ENEMY DELETED banner 49..106, RESULT window slide-in ~154, mark OBJ (16x16 tile 0x200 pal 11) entering wrapped x=509 at 163 then 13/29/37; our zero-enemy fixture held the fight open forever by design. Fix: FIXTURE.md bit5 FLAG_RESOLVE_OVER carried only on the field descriptor, battle.rs over-gate honors it, results.rs mark entry animation (hidden 4 frames, 509/13/29/37). Align offset 60->80 by measured event (banner canon 49 <-> rust capture 8; mark canon 163 <-> rust 121), unique sharp minimum (0 vs 1139 at +-1) in unchanged band range(60,110). verify_rows PASS (field/wave/window/opening/chip-cannon/cannon). Verifier CONFIRMED all three claims (canon routine sub_802CA5C/sub_8009FF8 lines, flag scope, event pairing). Worker GLM-5.3-Flash high, 141 turns, $0.257; verifier Muse-Spark high, 59 turns, $1.089; children total $1.346.


### F9. `banner` isolated: 2248 px over 58 frames  *(DONE -- merged 597875e, 2026-09-13; banner 2248->0/0/58)*

**Result.** DONE. banner isolated 2248/562/58 -> PASS 0/0/58 (negative 7275, not blind); every other row identical (wave/window/opening/chip-cannon/cannon/field re-verified, full table unchanged). The residue was the PAUSED fixture's own deleted-enemy corpse, not the banner: all 2248 px at x149-196 y81-117 on canon frames 49-52 (the dissolve's last 4 frames); frames 53..106 already 0. Fix in tools/harness.py only (no src/): the banner canon Side blanks ENEMY_TILES + ENEMY_DISSOLVE_TAIL per frame and one-shot pokes the corpse GFX-queue entry's size word (slot 41 = 0x0200B7EC) to 0 before frame 49's flush (ProcessGFXTransferQueue asm00_0.s:830-874; 768-byte pre-dithered sheet from ROM 0x0839A610). No allowlist, alignment or region change. verify_rows PASS on all 7 rows. Harness-lines-only fixture fix, no verifier. Worker GLM-5.3-Flash high, 116 turns, $0.136.


### F10. `buster` isolated: 3172 px over 32 frames  *(BLOCKED -- 2026-09-13; two misses, branch wt/f10b-buster kept unmerged)*

**Result.** BLOCKED after the second miss, moving on. F10b fired the buster for real in the 0x08 window (row no longer vacuous; MegaMan body region 0 px all 32 frames) but the row reads 65386/2714/32 (negative 67166, not blind) -- 100% PAUSED-route fixture baggage (pause ribbon, corpse dissolve, BATTLE START ribbon), measured unblankable with allowed tools (every-frame sheets re-uploaded through the GFX queue; per-frame --zero re-landed by the same-vblank flush; per-frame size-word cheats overwritten by the same-vblank enqueue, cheat-run 74406 = no change; F9's kill only worked on a frame-before enqueue). Blanking would need a ROM patch of the sheet-enqueuer -- outside the file rules. Along the way the real pose mechanism was found and corrected on the branch (NOT merged): shoot length is a 5-frame fire phase (sub_80EB450) plus a hold from byte_80209CC[tier*6 + free panels ahead] (sub_800FAAC return via sub_80EB502), 25f miss vs 17f hit -- F10's sub_800F8CE Timer story is dead (MM +0x20 reads 0 throughout). verify_rows PASS (buster 65386 MATCH + 6 canaries at 0). No verifier: F11 does not build on these claims; the branch keeps the note + src fix for any future ROM-patch-authorized ticket. Worker GLM-5.3-Flash high, 144 turns, $0.333.

**Result.** BLOCKED-as-reported, treated as first miss: buster unchanged 3172/177/32 (negative 3349, not blind; verify_rows MATCH). The 3172 is canon's own resolving battle (RESULT mark via sub_802CA5C, F8's mechanism) and the row is vacuous -- canon's scripted B press is inert in sequencer 0x0C (0x08 from frame 11, 0x0C from 47 through 199; MegaMan idle all 200 frames). Verifier CONFIRMED the 0x0C delivery wall (chip-path positive control works, so the method is valid) and the every-frame GFX-queue re-uploads beating per-frame --zero (banner sheets at 0x06016A00+, 40/40 frames; corpse dst occasional 46/49). Verifier CORRECTED one label ("number right, explanation wrong"): the shoot is CurAction 0x11 carrying CurAnim 0x0e, not CurAction 0x0e -- the follow-up must watch anim (+0x10). Verifier left UNCHECKED: sub_800F8CE's buster-specific caller link, and the pinning-kills-arm link (pinning delivery doesn't stick under every-frame re-enqueue). Worker GLM-5.3-Flash high, 129 turns, $0.343; verifier Muse-Spark high, 66 turns, $0.867.


### F10b. `buster`: fire in the 0x08 window with the miss-pose fix, or close the row  *(BLOCKED -- 2026-09-13; second miss, see F10 result; branch wt/f10b-buster kept unmerged)*

**Why.** F10's verified findings: (a) the buster FIRES in sequencer 0x08 (B@30 control: action 0x11 f33..58) and pairs event-for-event with canon at a constant delta (canon_ref = press+4, offset ~= 105, band range(90,120) already measured); (b) a real src defect underneath -- canon's shoot holds 25 frames on a miss (anim 0x0e f34..58) vs 17 on a hit (f154..170), ours is hard-coded 17 (actor.rs BUSTER frames); fixing it alone REGRESSES the current row, so it must land together with the re-timing; (c) the 0x08 window carries fixture baggage (banner sheets re-uploaded every frame, corpse dst on 46/49) that beat per-frame --zero. Label correction: watch CurAnim (+0x10) for 0x0e, not CurAction (+0x09).

**Do, in order.**
1. **Start** with `bash tools/worktree.sh f10b-buster`, then in that worktree `git merge --ff-only wt/f10-buster` (kept branch with the row-note findings).
2. **Baseline** `harness.py --only buster` (3172/177/32, neg 3349).
3. **One bounded attempt:** move the row's fire into the 0x08 window (B@30-style press), re-time by the measured event pairing (canon_ref = press+4, band range(90,120) to CONFIRM the unique minimum, F2's rule), blank the baggage (F9's kill-the-upload pattern -- but the verifier found STERILE stubs the banner-text upload, so the every-frame sheets at 0x06016A00+ are a different path; measure which upload path feeds the compared frames before choosing the blank), and land the src miss-pose fix (extend the held pose on a whiffed hitscan, citing sub_800F8CE asm00_2.s:1649-1685 -- but first trace the actual buster caller, since the sub_800F8CE link is UNCHECKED and MM +0x20 Timer reads 0 through the shoot).
4. **Acceptance:** buster reads 0 with non-blind negative, wave/window/opening/chip-cannon/field unchanged, full table nothing worse. If the baggage proves unblankable or the caller trace contradicts the Timer story, report the precise negative with the frames -- no second patch idea, no wider change.

**Rules.** src/ for the miss-pose fix, tools/harness.py for this row only; no allowlist change; no region change except by measured event. **Coordinator:** verify_rows plus the verifier on the caller-trace claim; a second miss marks F10 BLOCKED and moves on to F11.


### F11. `warp` isolated: 9198 px over 30 frames  *(DONE -- merged 389578d, 2026-09-13; warp 9198->0/0/30)*

**Result.** DONE. warp isolated 9198/1577/30 -> PASS 0/0/30 (negative 8440, not blind, no longer shift-invariant); 6 canaries re-verified at 0. The Note's suspicion confirmed: canon's script presses were inert (sequencer 0x0C never refreshes AIData; canon centroid fixed x=61 while rust warped), so 9198 was our warp vs a static sprite, the negative equaled the nominal, and the old minimum was a band-edge artifact. Fix in tools/harness.py only (no src/): canon presses via one-shot pokes to AIData JoypadHeld 0x020340a2 (canon warps with rust's exact 5-frame 706/458/395/458/706 signature), ready-chip bubble blanked with per-frame --zero 0x020352E0:48 (sub_801C002/082, 6 slots at dword_20352E0), alignment pinned to the warp event (offset 51, canon 132 <-> rust 61, +-1 reads 8440). Integrated, decided option (a): old printed 328071/18287 was slope-gamed; at the honest lock old 392779 -> new 355385/19909 (~37k better) but prints WORSE vs the stale AUDIT-6 cap 19500 -- allowlist untouched, documented in the row note. verify_rows PASS on all 7 rows. No verifier (F12 does not build on these claims). Worker GLM-5.3-Flash high, 109 turns, $0.183.

**Note.** Its negative control reads 9198 too -- the same as the nominal -- so first check whether the
row's alignment or negative is meaningful before localizing the residue.


---

# archived 2026-09-13

### F16. Oracle coverage: every harness row, not two  *(DONE -- 2026-09-13, Oracle generalized to all 60 comparison rows (tools/oracle.py +138/-41, new tools/f16_slot_probe.py, export bl)*

**Result.** Oracle generalized to all 60 comparison rows (tools/oracle.py +138/-41, new tools/f16_slot_probe.py, export block untouched, landed ee6c494). Sweep 60/60 exit 0; card field k=0/pixel k=0 consistent, mettaur k=0/k=0 consistent, tiles field k=0 vs pixel k=7 (fixture disagreement, reported); only banner of 37 pixel-0 rows state-clean (36 show pixel-invisible src divergences); negatives 48/60 NOT BLIND, 11 honest-static, chip-use BLIND-dynamic flagged. verify_rows PASS six rows unchanged. Worker worker (glm-5.3-flash, 69 turns, $0.085). Verifier verifier (muse-spark-1.3-contributor, 22 turns, $0.009): all samples CONFIRMED (residues, n/a, loud fails, banner/cannon/chip-sword, blind split legitimate), ENEMY_SLOT probe + full censuses UNCHECKED (plausible, not refuted), no rule blockers. Deviations from ticket predictions are data findings, not tool defects; residuals (tiles fixture, chip-use BLIND, 0x14 citation) are src/fixture territory. Note: HANDOFF 3a oracle-coverage sentence now stale, needs docs pass.
**Why.** `tools/oracle.py` names the first divergent state field and frame, which is what turns a
three-attempt ticket into a one-attempt ticket, but it supports only `wave` and `mettaur`. Attribution
is where the money goes (R3-R5, F10: two to four attempts each). Cost reducer for every ticket after it.

**Do, in order.**
1. Generalize `oracle.py <row>` to any row in `harness.py --list`: reuse the row's own Sides and Align
   (as it does for wave/mettaur), watch the same field set on both sides, print the full table, the
   first divergence, the pixel diff's first non-zero frame on the same alignment, and the one-frame-shift
   negative. Rows whose fixture has no enemy skip the enemy fields with an explicit `n/a`, never a fake
   match. Fail loudly on a row whose alignment cannot be reproduced.
2. Extend the export block only if a row needs a field the block lacks (document the layout change in
   HANDOFF §3a of the long handoff and keep the block behavior-neutral: wave/window/opening/cannon/field
   still 0).
3. **Acceptance:** `oracle.py` runs on every row; on three rows with a known residue (card, mettaur,
   tiles) the first divergent field's frame is consistent with the row's first non-zero pixel frame
   (report both); on three rows at 0 the compared fields show no divergence over the window; every
   negative control changes the result; verify_rows on the six rows unchanged.

**Rules.** tools/ and the export block in src/ only; no behavior change; captures one at a time.
**Coordinator:** verify_rows plus the verifier on the "consistent with the pixel diff" claims.

### F13. `card` isolated: 18486 px over 16 frames  *(NEGATIVE -- 2026-09-13, Precise negative, src ruled out by measurement (no edits, branch empty))*

**Result.** Precise negative, src ruled out by measurement (no edits, branch empty). card stays 18486/3081/16 (verify_rows PASS, negative 15405 not blind); 18486 = 6x3081 k0-5 card-region x<128 + 10x0 k6-15; residue is highlighted-card slot 1 vs 0, slot 0 already exact. Canon custMenuSomeHandler_8028B74 (asm03_0.s:5194; cursor byte 0x020364C7 0a->4->3->2->1->0 at RAM 21/51/81/111/141, pixels P+2). Rust static: CARDNAME_ROW window_cursor=0, presses 20-145 land while window closed (opens ~131-141), no just_pressed edge. Our walk already P+2 with canon magnitudes; CURSOR_DELAY=2 correct. Worker worker-muse (muse-spark-1.3-contributor, 57 turns, $0.023). Verifier verifier-glm (glm-5.3-flash, 18 turns, $0.009): walk claim CONFIRMED empirically (RAM walk reproduced), static/oracle-reasoning structurally CONFIRMED, magnitudes/band sub-values UNCHECKED, fixture-rewire recipe actionable with 3 gaps (negative re-verify, window-open coverage, band arithmetic). Follow-up F13b written for the fixture rewire.
**Why.** HANDOFF §10 names the chip window's cursor-move timing.


### F13b. `card` isolated via fixture rewire (follow-up to F13's verified negative)  *(DONE -- 2026-09-13, card 18486->0 via fixture rewire, landed 4b16fd7)*

**Result.** card 18486->0 via fixture rewire, landed 4b16fd7. Rust _CURSOR_WALK_REAL->_CURSOR_WALK_RUST, Align canon_ref 136->46 search 292..305, offset 298 event-locked on shared 4->3 (canon pixel 52 <-> rust pixel 312); band sweep unique min (0 vs 3046 off-by-one). card PASS 0/0/16, negative frame 3046 not blind; wave/window/opening-isolated/chip-cannon PASS 0; full table matches F12a record (only card moved); CURSOR_DELAY split did not surface. Worker worker (glm-5.3-flash, 38 turns, $0.029). Verifier verifier (muse-spark-1.3-contributor, 32 turns, $0.008): CONFIRMED all with independent re-measurement (canon RAM walk, rust origin 8, band sweep, cross-diff path, negative teeth, rules CLEAN). Residuals: rust walk has no RAM trace; window-open animation uncovered by any card band; bracket-vs-card 1-frame split still open in src.
**Result.** card 18486->0 via fixture rewire, landed 4b16fd7. Rust _CURSOR_WALK_REAL->_CURSOR_WALK_RUST, Align canon_ref 136->46 search 292..305, offset 298 event-locked on shared 4->3 (canon pixel 52 <-> rust pixel 312); band sweep unique min (0 vs 3046 off-by-one). card PASS 0/0/16, negative frame 3046 not blind; wave/window/opening-isolated/chip-cannon PASS 0; full table matches F12a record (only card moved); CURSOR_DELAY split did not surface. Worker worker (glm-5.3-flash, 88 msgs, cost from ledger). Verifier verifier (muse-spark): CONFIRMED all -- canon RAM walk, rust origin 8 + pixel transitions, band sweep, cross-diff path, negative teeth, rules CLEAN. Residuals: rust walk has no RAM trace (pixel-identity provenance); window-open animation uncovered by any card band; bracket-vs-card 1-frame split still open in src.
**Why.** F13 (NEGATIVE, verified) ruled out src: canon walks OK->0 at RAM 21/51/81/111/141
(`custMenuSomeHandler_8028B74`, asm03_0.s:5194; cursor byte `0x020364C7`) while rust holds static
slot 0 (presses 20-145 land while the window is closed, opens ~131-141); our walk is already P+2
with canon-identical magnitudes. The residue is the fixture: rust never walks. Rewire the fixture to
walk and compare transition-vs-transition.

**Do, in order.**
1. Baseline card (harness line + `diffmask.py` region + `oracle.py`): must read 18486/3081/16,
   negative not blind (15405).
2. Rewire the card rust script `_CURSOR_WALK_REAL` -> `_CURSOR_WALK_RUST` (presses
   250/280/310/340/370), re-centred on the shared 4->3 transition (canon RAM 51 / pixel 52):
   `canon_ref=46` (band 46..61). Re-derive the rust band from a rust capture (marker origin 8,
   regress lag) -- do NOT inherit an unverified ~276/~282. Account for canon-walks-from-OK vs
   rust-walks-from-0 path difference.
3. Say where the window-open frames stay checked: the old band kept the 142 window-open transition
   in view; the new band must not let the row pass trivially -- keep window-open coverage or move it
   to an explicit second comparison.
4. Re-run card, wave, window, opening, chip-cannon and the full table -- nothing may get worse, and a
   row that does is reported with its numbers. Re-run the frame-shift negative and confirm still
   not-blind (from re-centring, not by weakening the negative).
5. Report: row · frames · total · worst · region · commit · one line of mechanism · one line of what
   is unverified. Watch-out (report, don't widen): the bracket-vs-card 1-frame split in the
   `CURSOR_DELAY` comment may surface once the walk works.

**Rules.** Fixture/descriptor + row note only (`peeked` provenance for the band); no src/, no
allowlist change, no region shrink except by the measured 52-transition event (F2's rule); captures
one at a time.

### F14. `mettaur` isolated: 31075 px over 70 frames  *(PARTIAL -- 2026-09-13, Wrong-guess PARTIAL, no edits (branch empty))*

**Result.** Wrong-guess PARTIAL, no edits (branch empty). mettaur stays 31075/1566/70 (verify_rows PASS, negative 46554 not blind). Worker ruled out mercy/blink (seed 120 / first-observable 119 / -1/frame reproduced; blamed attack latency 82v81 on wave). Verifier CONFIRMED seed/rate/numbers but REFUTED the canon blink formula: lsr #2 carry is bit 1, so canon hides iff (timer>>1)&1 (repo Invisibl comment src/actor.rs:977-979 agrees); ours uses bit 2 -- predicates diverge half the mercy window, consistent with the row signature (k=0 404px flip at timer 93, diffs all 70 frames inside mercy 93->24). Worker worker-muse (muse-spark-1.3-contributor, 64 turns, $0.026). Verifier verifier-glm (glm-5.3-flash, 24 turns, $0.017). Follow-up F14b (corrected-predicate blink experiment) written; wave-timing premise on hold.
**Why.** F2's event pairing left one field: `oracle.py mettaur` first diverges at `mm_timer` k=0
(canon 7, ours 6) -- MegaMan one frame apart inside the 120-frame mercy -- and canon's MegaMan is
blinking where ours is visible (mettaur-progress.gif). Find which side's mercy/blink timing is off by
the frame, from canon's routine (`sub_801A5EE`, asm00_2.s:22252-22296 sets the 120), and fix it.


### F14b. `mettaur`: mercy-blink predicate bit 2 -> bit 1 (follow-up to F14's refuted negative)  *(PARTIAL -- 2026-09-13, Blink experiment done, partial drop, landed 3e49236)*

**Result.** Blink experiment done, partial drop, landed 3e49236. mettaur 31075->19698 (worst 1566->1245, 70 frames, negative frame 60824 not blind); src/actor.rs only (5+/4-, predicate (invulnerable>>1)&1, comment cites lsr-carry + routine); mm_timer 70/70, first divergence enemy_anim k=61 (2/70); full table exactly one row differs (improved). Worker worker (glm-5.3-flash, 36 turns, $0.020). Verifier verifier (muse-spark-1.3-contributor, 10 turns, $0.005): diff+rules CONFIRMED, partial-drop honest CONFIRMED, oracle/table values UNCHECKED by design (no re-runs); puzzles noted: render-only edit vs mm_timer state-field match unexplained, k=0 404-vs-509px conflict in worker texts. No F14c: two PARTIALs in a row on mettaur (F14, F14b), residuals (flash magnitude, enemy_anim k=61, wave latency) stay open for later tickets.
**Result.** Blink experiment done, partial drop, landed 3e49236. mettaur 31075->19698 (worst 1566->1245, 70 frames, negative frame 60824 not blind); src/actor.rs only (5+/4-, predicate (invulnerable>>1)&1, comment cites lsr-carry + routine); mm_timer 70/70, first divergence enemy_anim k=61 (2/70); full table exactly one row differs (improved). Worker worker (glm-5.3-flash, 36 turns, $0.020). Verifier verifier (muse-spark-1.3-contributor, turns/cost from ledger): diff+rules CONFIRMED, partial-drop honest CONFIRMED, oracle/table values UNCHECKED by design (no re-runs); puzzles noted: render-only edit vs mm_timer state-field match unexplained, k=0 404-vs-509px conflict in worker texts. No F14c: two PARTIALs in a row on mettaur (F14, F14b), residuals (flash magnitude, enemy_anim k=61, wave latency) stay open for later tickets.
**Why.** F14's worker matched mercy seed/rate (120, first-observable 119, -1/frame, CONFIRMED) but
misread the canon blink formula; verifier REFUTED it: `lsr #2; bcc` (asm00_2.s:16795-16806) tests the
carry, which is bit 1, so canon hides iff (timer>>1)&1 (2-on/2-off, period 4) -- the repo's own
Invisibl comment (src/actor.rs:977-979) agrees, while the mercy comment (:963-967) repeats the bit-2
error. Ours hides iff (invulnerable/4)%2==1 (bit 2, src/actor.rs:970). The predicates diverge on half
the mercy-window frames; the row signature is consistent (k=0 404px flip at canon 140/timer 93, small
diffs all 70 frames inside mercy 93->24). The wave-timing premise stays on hold until this experiment
runs (stop rule: refuted claim).

**Do, in order.**
1. Baseline mettaur (harness line + `diffmask.py` region + `oracle.py`): must read 31075/1566/70,
   negative not blind (46554).
2. Change the mercy blink predicate to bit-1 (`(invulnerable>>1)&1`-equivalent), fixing the
   :963-967 comment; leave seed/rate (120, -1/frame) and the Invisibl path untouched. Cite
   `blindVisualHandledHere_8016934` + ARM carry semantics in the commit note.
3. Re-run mettaur, wave, window, opening, chip-cannon and the full table -- nothing may get worse,
   and a row that does is reported with its numbers. If 31075 drops only partially, report the
   remaining frames (wave-latency / enemy_anim k=61 / flash-magnitude residuals stay open).
4. Report: row · frames · total · worst · region · commit · one line of mechanism · one line of what
   is unverified.

**Rules.** src/ blink predicate + comments only; no allowlist change, no alignment or region change;
captures one at a time.


### F15. tiles/gauge: the one vblank frame, 208 px at k=7  *(DONE -- 2026-09-13, tiles+gauge isolated 208->0, cursor unmoved 620802, landed 12a130a)*

**Result.** tiles+gauge isolated 208->0, cursor unmoved 620802, landed 12a130a. Backdrop::seed +1 construction lead (src/backdrop.rs 12+/1-, derived; mirrors new() STEP_HOLD[0]+1); one-frame-early art step fixed (canon uploads 36/44/52 p8 vs ours 434/442; rust442==canon52). Canon ProcessGFXAnims (:3596) countdown match, sub_8001C94 (:3752) queue-vs-sync confirmed. Cursor watch-write both sides: canon writer BIOS-HLE 0x2F4 p8 (+p4 band near moves), rust vram_manager PCs; F3 +112 did not recur. Integrated tiles/gauge 26165->25979 same bucket; full table byte-identical except tiles/gauge improved (mettaur delta is F14b in main). verify_rows PASS 7 rows. Worker worker-muse (muse-spark-1.3-contributor, 86 turns, $0.121). Verifier verifier-glm (glm-5.3-flash, 20 turns, $0.018): root-cause/citations/scope/cursor/integrated CONFIRMED (rust period-16 + shift-test + gauge-t sub-details unchecked/descriptive-only), rules CLEAN. Note: coordinator restored README Website section (dd4b137, byte-exact, disclosed) accidentally deleted in worker commit.
**Why.** F6 left k=0..6 at exactly 0 and 208 px on k=7, the vblank-race residue HANDOFF §9 records.
It is a checkable claim, not a tolerance: find which write lands a frame early or late between the
two binaries (the watchpoint names the writer on both sides) and make ours land where canon's does.
Same ticket: `cursor` went 620802 -> 620914 (+112) at F3's merge although F3's code cannot run in that
row (no OK press) -- the custmatch/cursor VRAM write HANDOFF §9 says lands a frame early between
differently sized binaries. Measure it with --watch-write on both sides; no row may silently move with
code size.


---

# archived 2026-09-13

### F18. `windowclose` isolated: the close event's remaining total  *(PARTIAL -- 2026-09-13, windowclose 695603/28784/40/778748 -> 666451/28784/40/749690)*

**Result.** windowclose 695603/28784/40/778748 -> 666451/28784/40/749690; post-close flat band k=12..39 1402->0 (gauge 980 not-full fill 0x9222 all 16 cells per sub_801C4E4 loc_801C534 + name 422 blanked per sub_8026BF4->sub_8029D80 w=7/h=2 tile 0); slide k=0..9 still 0; k=11 transient 2447 unchanged (close-sequencing off-by-one, follow-up). Isolated wave/window/chip-cannon/opening PASS 0; integrated field 380488/24240 + buster 643698/27225 + chip-use 644119/27225 allowed (AUDIT-6), warp 363658/20107 WORSE but already WORSE at base 355385/19909 (stale cap, verified). Landed 40385da (land.sh reused 2-row PASS; coordinator reproduced all 9 isolated + 4 integrated lines with MATCH this session). Worker worker (glm-5.3-flash:high, 102 turns, $0.2305). Verifier verifier (muse-spark-1.3-contributor:high, 22 turns, $0.0042): routine/diff claims CONFIRMED in code, live-dump halves UNCHECKED (not refuted), pixel band corroborates. Next: k=11 sequencing; gauge=0 descriptors belong to rows owning field/buster/chip-use/warp.
**Why.** `windowclose` isolated reads total 695603 (worst 28784) over 40 frames at canon 81+k, rust 8+253+k (`web/captures/windowclose-isolated.txt:1`); the row note (`tools/harness.py:1477`) records the measured event: `--watch 0x020364c0:0x48` shows JumpOffset 0x04->0x08 on the A-press frame with slide counter +0x40 counting 0x0c..0x78 across canon frames 81..90, rust slide calls at capture 261..270 (marker origin 8), event offset 253 where the ten slide frames compare EXACTLY 0 on `--only-bg 3`; a deeper meaningless basin sits near offset 264 (575089 vs 695603) from unshared-battle noise; the post-close BG3 residue at the true alignment is a flat 1402 px of HUD-strip fixture content (canon gauge RESETS empty then refills rows 8..15 while descriptor gauge=1 stays full; hand chip-name rows 148..158 `Cannon 40` vs none).
**Do, in order.**
1. Start in `tools/worktree.sh f18-windowclose`. Baseline `python3 tools/harness.py --only windowclose` (695603/28784/40 at offset 253, negative confirmed not blind), plus `--only-bg 3` ten slide frames at 0 and the post-close BG3 1402 px split by element, measured.
2. Attribute the post-close residue element by element (gauge-reset/refill vs hand chip-name) to fixture content vs `src/`, citing canon's close routine in `reference/bn6f`; fix the fixture/descriptor with `peeked` provenance or `src/`, never the alignment, measured on the same band.
3. Re-run `windowclose`, `wave`, `window`, `opening`, `chip-cannon` and the full table -- nothing may get worse, and a row that does is reported with its numbers, measured.
**Rules.** `src/` or fixture/descriptor per the attribution only; no allowlist change; no alignment or region change except by measured event -- offset 253 stands unless the watch names a new event frame (F2's rule); captures one at a time.
**Measure and report.** Row `windowclose` before/after (total/worst/frames) on the identical script and window, `--only-bg 3` slide-frame totals before/after, post-close BG3 residue by element before/after, full-table deltas.
**Coordinator:** `verify_rows` on every row the report names; the verifier only for claims beyond harness lines (routine identity, fixture-content class); a wrong-guess PARTIAL gets one follow-up; a second miss marks it BLOCKED and moves on.

### F19. `popup` isolated: 107511 px over 80 frames  *(PARTIAL -- 2026-09-13, popup 107511/1348/80/108815 -> 60614/1842/80/60806 (-44%, fixture only, landed c2c24e6))*

**Result.** popup 107511/1348/80/108815 -> 60614/1842/80/60806 (-44%, fixture only, landed c2c24e6); canon ALIVE->DELETE_ENEMY (HP 0/0) + banner dissolve blanking; subject center band 0, enemy box 51991->6081, HUD bar 55520 unchanged; wave/window/chip-cannon/opening-isolated PASS 0, full table no other deltas (verify_rows PASS). Worker worker-muse (muse-spark-1.3-contributor:high, 66 turns, $0.0351). Verifier verifier-glm (glm-5.3-flash:high, 28 turns, $0.0162): sub_801EA34 citation + fixture class + F20 scoping all CONFIRMED; residual-bbox/Rust-HUD sub-values UNCHECKED (stale scratch captures, not refuted). Next: residual 55520 canon-only OBJ HUD HP bar is F20 OBJ-HUD work.
**Why.** `popup` isolated reads total 107511 (worst 1348) over 80 frames at canon 43+k, rust 1(marker)+122+k, canon (sterile) (`web/captures/popup-isolated.txt:1`); canon REAL_START=43 (A pressed at 40), rust marker origin 1 with a 26-frame band holding a unique zero at offset 122; `AUDIT.md` records the attribution as 100% OBJ -- the enemy's HP digits exposed because the popup needs that tile range unzeroed.
**Do, in order.**
1. Start in `tools/worktree.sh f19-popup`. Baseline `python3 tools/harness.py --only popup` (107511/1348/80, negative confirmed not blind), plus `tools/diffmask.py` region (OBJ vs BG split) and `tools/oracle.py` where supported, measured.
2. Localize the residue to frames and the HP-digit/popup element, find canon's routine for that element in `reference/bn6f` and cite it, fix `src/` (or the fixture/descriptor with `peeked` provenance if the residue is the tile-range fixture), measured on the same frames and region.
3. Re-run `popup`, `wave`, `window`, `opening`, `chip-cannon` and the full table -- nothing may get worse, and a row that does is reported with its numbers, measured.
**Rules.** `src/` (or fixture/descriptor when the residue is the fixture) only; no allowlist change; no alignment or region change except by measured event (F2's rule); captures one at a time.
**Measure and report.** Row `popup` before/after (total/worst/frames) on the identical script and window, diffmask region before/after, full-table deltas.
**Coordinator:** `verify_rows` on every row the report names; the verifier only for claims beyond harness lines (routine identity, cause); a wrong-guess PARTIAL gets one follow-up; a second miss marks it BLOCKED and moves on.

### F20. `tiles`/`gauge` integrated: the full-HUD variant, one element at a time  *(PARTIAL -- 2026-09-13, tiles/gauge integrated 25979/3282/8/37337 unchanged (allowed AUDIT-6 <=3600))*

**Result.** tiles/gauge integrated 25979/3282/8/37337 unchanged (allowed AUDIT-6 <=3600); isolated 0/0/8/12197; precise negative decomposition, nothing landed (branch empty, deleted). HUD strip y<24 = 0 all frames (gauge stripe-flow, HP, hand icon already matched); --disable-obj reads 0/0/8 so residue is all OBJ: navi +40px col (fixture megaman_col=3 vs canon RAM (2,2)), enemy +24px row (fixture enemy_row=3 vs canon (5,2)); monkeypatch-only 25979->3865 worst 678; remaining 3865 = canon Mettaur mid-attack (CurState/CurAction 0x04/0x0b) vs ours idle (F17-family). wave/window/chip-cannon/opening-isolated PASS 0, opening integrated 72499 unchanged (verify_rows PASS + coordinator integrated runs MATCH). Worker worker (glm-5.3-flash:high, 48 turns, $0.0447). Verifier verifier (muse-spark-1.3-contributor:high, 5 turns, $0.0031): fixture defaults, 40px/24px arithmetic, empty diff, scoping all CONFIRMED. Supervisor DENIED fixture edit + AI work (out of ticket Rules). Follow-ups: HUDMATCH spawn ticket (moves field/warp/buster) + enemy-AI attack-state ticket.
**Why.** The integrated start is `tiles`/`gauge`: their isolated variants are at 0 (F15: tiles+gauge isolated 208->0, landed 12a130a) and their integrated residue is the smallest of the full-HUD rows (field 368525, warp 355385, buster 626040, tiles/gauge 26495, opening 72499). One capture is two rows (`tools/harness.py:956` `_tiles_gauge`: same full-screen capture, canon REAL+PAUSED Start@10 frame 44, rust HUDMATCH marker origin 8 + offset 427, 8 frames; `tools/allowlist.py:47-48` tiles:integrated/gauge:integrated capped 3600 AUDIT-6 for the gauge stripe-flow + sprites) -- one fix brings two rows to 0, the highest rows-per-dollar on the table, within HANDOFF §3 (convergence first, no new content).
**Do, in order.**
1. Start in `tools/worktree.sh f20-tiles-gauge-integrated`. Baseline `python3 tools/harness.py --only tiles,gauge` plus `--ui isolated` and `--ui integrated` separately (isolated must read 0/0/8, integrated ~26495/total over 8 at canon 44+k / rust 8+427+k, negative confirmed not blind), plus `tools/diffmask.py` region split (HUD strip y<24 vs backgrounds vs OBJ) on the integrated capture, measured.
2. Match the HUD elements one at a time, in this order, each as its own measured step: (a) gauge stripe-flow/bar+marker phase (canon's sub_801C4E4 counter vs HUDMATCH gauge_tick=50), (b) HP box/digits, (c) sprites the integrated variant turns back on (navi, enemy, hand icon), citing each element's canon routine in `reference/bn6f`, fixing `src/` only, measured per element on the same integrated frames and region.
3. Re-run `tiles`, `gauge`, `wave`, `window`, `opening`, `chip-cannon` and the full table -- nothing may get worse, and a row that does is reported with its numbers, measured.
**Rules.** `src/` HUD/sprite path only; isolated alignment, fixture, and descriptor untouched; no allowlist change -- the `tiles:integrated`/`gauge:integrated` entries stay as-is until the row reads 0; no alignment or region change except by measured event (F2's rule); captures one at a time.
**Measure and report.** Rows `tiles`+`gauge` integrated before/after (total/worst/frames) on the identical script and window, isolated lines before/after to prove no regression, diffmask region by element before/after each step, full-table deltas.
**Coordinator:** `verify_rows` on every row the report names; the verifier only for claims beyond harness lines (routine identity, element attribution); a wrong-guess PARTIAL gets one follow-up; a second miss marks it BLOCKED and moves on.


---

# archived 2026-09-13

### F17. `mettaur` isolated: enemy_anim k=61, the Mettaur's own animation  *(DONE -- 2026-09-13, mettaur 19698/1245/70/60824 unchanged pixels, oracle enemy_anim 2/70->1/70 (first k=61, mm_timer 70/70))*

**Result.** mettaur 19698/1245/70/60824 unchanged pixels, oracle enemy_anim 2/70->1/70 (first k=61, mm_timer 70/70); SWING shows IDLE on 64th executor tick per canon sub_8109DEC (asm31.s:170830-170848, SWING_POSE=0x40-1 derived), six chip literals pose:None behavior-neutral; wave/window/chip-cannon/opening-isolated PASS 0, opening integrated 72499 pre-existing (verify_rows PASS, landed 5ef3a6d). Worker worker-muse (muse-spark-1.3-contributor:high, 81 turns, $0.0385). Verifier verifier-glm (glm-5.3-flash:high, 25 turns, $0.0129): routine semantics, neutrality, 0px idle all CONFIRMED by independent oracle+capture measurement. Unverified/next: 1-frame relative-phase skew (MegaMan-side, out of scope) is the follow-up.
**Why.** F14b landed `3e49236`: `mettaur` 31075->19698 (worst 1566->1245, 70 frames, negative frame 60824 not blind); `src/actor.rs` only, mercy-blink predicate now `(invulnerable>>1)&1`; `mm_timer` 70/70, first oracle divergence `enemy_anim` k=61 (2/70); full table exactly one row differs (improved). The mercy seed/rate and blink predicate are settled and stay untouched -- the remainder is the enemy's animation state, not a third mercy ticket.
**Do, in order.**
1. Start in `tools/worktree.sh f17-mettaur-anim`. Baseline `python3 tools/harness.py --only mettaur` (must read 19698/1245/70, negative 60824 not blind), plus `tools/diffmask.py` region and `tools/oracle.py mettaur` (must read `mm_timer` 70/70, first divergence `enemy_anim` k=61), measured.
2. Localize the `enemy_anim` k=61 frames to the Mettaur's attack element and pixels, find canon's Mettaur animation routine in `reference/bn6f` and cite it, fix `src/` only, measured on the same oracle fields and pixel frames.
3. Re-run `mettaur`, `wave`, `window`, `opening`, `chip-cannon` and the full table -- nothing may get worse, and a row that does is reported with its numbers, measured.
**Rules.** `src/` enemy-animation path only; mercy seed/rate/blink predicate and comments untouched; no allowlist change; no alignment or region change except by measured event (F2's rule); captures one at a time.
**Measure and report.** Row `mettaur` before/after (total/worst/frames) on the identical script and window, oracle `mm_timer` match count and first `enemy_anim` divergent frame before/after, full-table deltas.
**Coordinator:** `verify_rows` on every row the report names; the verifier only for claims beyond harness lines (routine identity, cause); a wrong-guess PARTIAL gets one follow-up; a second miss marks it BLOCKED and moves on.

- F18 PARTIAL -- `windowclose` isolated: the close event's remaining total. windowclose 695603/28784/40/778748 -> 666451/28784/40/749690


### F20b. `tiles`/`gauge` integrated: match the fixture's sprite positions to canon's state  *(DONE -- 2026-09-13, tiles/gauge integrated 25979/3282->3865/678/8 (negative 15891 not blind), isolated still 0/0/8)*

**Result.** tiles/gauge integrated 25979/3282->3865/678/8 (negative 15891 not blind), isolated still 0/0/8. HUDMATCH descriptor in tools/harness.py corrected to canon-peeked BattleObject panel positions (MM col 3->2, enemy row 3->2; canon (2,2) @0x0203a9c2/3, enemy (5,2) @0x0203ab72/3); residual 3865 is canon Mettaur mid-attack vs ours idle (F17 family); wave/window/opening/chip-cannon 0, warp-integrated exceed pre-existing (stash-identical); AUDIT-6 stays. Committed 2b913aa directly on main (worker skipped worktree; single-file descriptor change, verified post-hoc). Worker worker-muse. Verifier verifier-glm: all 4 claims CONFIRMED (diff scope, offsets, HUDMATCH scope, residual sourced; caveat ours-side action byte 0x04/0x00 on tiles vs 0x04/0x09 from F17 context).
**Why.** F20's verified decomposition: the HUD strip (y<24) reads 0 on all 8 frames and `--disable-obj`
reads 0/0/8, so the whole 25979 px is sprites -- our fixture puts MegaMan at column 3 where canon's
save state holds (2,2), and the enemy one row off canon's, so both navis and the enemy's HP readout sit
in the wrong cells (canon: MegaMan (2,2), enemy (5,2)). F20's worker tried the corrected positions as
a throwaway patch: 25979 -> 3865 (worst 678), and the remaining 3865 is canon's Mettaur mid-attack
(CurState/CurAction 0x04/0x0b) against ours idle -- the enemy AI phase, F17's family, not this ticket.
Fixture, not src/. **Do:** peek canon's positions from the row's own state
(MegaMan's and the enemy's PanelX/PanelY in their BattleObjects, cite the offsets), set the row's
descriptor (`HUDMATCH` in tools/harness.py) to them with `peeked` provenance, run tiles and gauge
(both variants), wave, window, opening, chip-cannon and the full table. **Acceptance:** tiles/gauge
integrated reads about 3865 or lower with a non-blind negative (0 if the Mettaur's attack phase also
lines up), the residual reported by element with frames and regions; isolated still 0; nothing worse. **Rules:** tools/harness.py descriptor only; no allowlist
change (the AUDIT-6 entry stays until the row reads 0, then it is removed, never widened).
**Coordinator:** verify_rows; no verifier unless a claim goes beyond harness lines.


### F21. `result` isolated: 497967 px over 40, its canon side is result_arrival  *(PARTIAL -- 2026-09-13, result 497967/31882/40/476424 -> 408337/31895/40/383600 (-89630))*

**Result.** result 497967/31882/40/476424 -> 408337/31895/40/383600 (-89630); WIN reward drawn on first confirm not at show per canon chain sub_802C34E->sub_802BE36->sub_802C044 (42 tiles 0x2a) ->sub_802C0A4 (30f cooldown 0x1e), driver sub_802BD60; phases Waiting->Revealing42->Cooldown30->RewardWait->Dismissing, LOSE unchanged; plateau inside 3734->904, outside ~2900 backdrop tail + slide lag remain. wave/window/chip-cannon/opening-isolated 0; field-integrated delta is RNG noise (no Shown on that path); full table no other deltas (verify_rows PASS, landed 8bcd73c). Worker worker-muse (muse-spark-1.3-contributor:high, 94 turns, $0.1096). Verifier verifier-glm (glm-5.3-flash:high, 15 turns, $0.0079): all 4 claims CONFIRMED (minor per-function line-attribution slip, values genuine). Next: seed RESULT_ROW art/scroll from peeked RESULT_ARRIVAL RAM (~2900 outside plateau), then slide-phase lag.
**Why.** `result` isolated reads total 497967 (worst 31882) over 40 frames at canon 21+k, rust 10(marker)+15+k (`web/captures/result-isolated.txt:1`, canon REAL+RESULT_ARRIVAL); rust is RESULT_ROW (RESULTMATCH_ROW + result_elapsed=0, `tools/harness.py:1148`); the row note (`tools/harness.py:1529-1535`) records the sweep: result_elapsed 0..40 at fixed offset bottoms at elapsed=14 (522212) but the joint minimum with the row's own search=range(0,60) is elapsed=0 at offset 15 (497967, every other sample 504-505k) -- result_elapsed is not the knob; localized shape is full-screen frame 0 (bbox x0-239,y0-159, 31882) decaying (30846, 29995, ... 17395 by k=10) to a flat ~6600-6900 px plateau from k=16 that never reaches 0; the reward-content theory is disproven (decoded frames: DeleteTime 0:29:33 = exactly 1760, Busting LV. 2, 100z, no chip -- RESULT_ROW's result_frames=1760/level=2/zenny=100 and megaman_hp=60 already match, peeked HP 0x3c/MaxHP 0x64); gauge=1 ruled out (identical 497967/31882); what is left is the pre-arrival battle tail, named lead eBGScrollCBCounters 0x02009690/0x02009694 reading 0x0530/0x8298 at RESULT_ARRIVAL frame 0.
**Do, in order.**
1. Start in `tools/worktree.sh f21-result`. Baseline `python3 tools/harness.py --only result` (497967/31882/40 at offset 15, negative confirmed not blind), plus `tools/diffmask.py` region (early full-screen frames vs k=16+ plateau split) on the same window, measured.
2. Localize the residue to the pre-arrival tail element (backdrop phase vs slide-in/result-window content), find canon's result routine in `reference/bn6f` and cite it, fix `src/` (or the fixture/descriptor with `peeked` provenance if the residue is the tail state), never the alignment, measured on the same frames and region.
3. Re-run `result`, `wave`, `window`, `opening`, `chip-cannon` and the full table -- nothing may get worse, and a row that does is reported with its numbers, measured.
**Rules.** `src/` (or fixture/descriptor when the residue is the tail state) only; no allowlist change; no alignment or region change except by measured event (F2's rule); result_elapsed=0 and the reward fields stay untouched unless the measurement names them; captures one at a time.
**Measure and report.** Row `result` before/after (total/worst/frames) on the identical script and window, per-frame decay/plateau split before/after, full-table deltas.
**Coordinator:** `verify_rows` on every row the report names; the verifier only for claims beyond harness lines (routine identity, tail-state attribution); a wrong-guess PARTIAL gets one follow-up; a second miss marks it BLOCKED and moves on.


### F22. `cursor` isolated: 620802 px over 170 frames  *(NEGATIVE -- 2026-09-13, cursor 620802/6884/170/728447 unchanged (nothing landed, branch empty, deleted))*

**Result.** cursor 620802/6884/170/728447 unchanged (nothing landed, branch empty, deleted); precise refutation: at event-locked offset 237 (252-8-(22-15), canon RAM 0x020364C7 walk 0x0a->4@21->3@51->2@81->1@111->0@141 per custMenuSomeHandler_8028B74 asm03_0.s:5194, rust 252/282/312/342/372) x<112 = 0 over all 170 frames — walk, bracket, blink, names, pictures, offered deck already exact; residue 779920 all x>=112 is unshared mid-battle backdrop/enemy/HP (CUSTMATCH art/scroll 0xFFFF fresh Backdrop, F13-scoped out). Re-pin probe 779920/5181/170 documented NOT applied per coordinator decision B (worse headline, no fix; belongs in follow-up owning the row definition). wave/window/chip-cannon/opening-isolated 0 (verify_rows PASS). Worker worker (glm-5.3-flash:high, 44 turns, $0.0442). Verifier verifier (muse-spark-1.3-contributor:high, 9 turns, $0.0048): routine bytes, Align arithmetic, fixture scoping, empty diff all CONFIRMED (pixel splits not re-measured, static scope). Next: follow-up ticket for event-locked re-pin + x>=112 backdrop fixture fields.
**Why.** `cursor` isolated reads total 620802 (worst 6884) over 170 frames at canon 15+k, rust 8(marker)+226+k (`web/captures/cursor-isolated.txt:1`, canon REAL+CHIPSELECT); rust builds from CUSTMATCH_ROW with the 5-press Left walk (`tools/harness.py:1162-1163`, `_CURSOR_WALK_RUST` presses 250+30k vs `_CURSOR_WALK_REAL` 20+30k) after F13b re-pinned the walk to rust's late window opening; `AUDIT.md` records the attribution as BG3 119680 + OBJ 671892 (the bracket and portrait icons); F15 left `cursor` unmoved at 620802 while fixing the shared vblank frame, so the remainder is the cursor-walk/icons residue, not the tile-write race.
**Do, in order.**
1. Start in `tools/worktree.sh f22-cursor`. Baseline `python3 tools/harness.py --only cursor` (620802/6884/170, negative confirmed not blind), plus `tools/diffmask.py` region (BG3 vs OBJ split, bracket/portrait localization) and per-press transition frames (canon RAM 21/51/81/111/141 pixels +1, rust pixel 252/282/312/342/372), measured.
2. Localize the residue to cursor-slot frames vs bracket/portrait-icon pixels, find canon's cursor/icon routine in `reference/bn6f` and cite it, fix `src/` (or the fixture/descriptor with `peeked` provenance if the residue is the offered-deck fixture), measured on the same transitions and region.
3. Re-run `cursor`, `wave`, `window`, `opening`, `chip-cannon` and the full table -- nothing may get worse, and a row that does is reported with its numbers, measured.
**Rules.** `src/` (or fixture/descriptor when the residue is the fixture) only; no allowlist change; no alignment or region change except by measured event (F2's rule); captures one at a time.
**Measure and report.** Row `cursor` before/after (total/worst/frames) on the identical script and window, diffmask BG3/OBJ split before/after, transition-frame alignment before/after, full-table deltas.
**Coordinator:** `verify_rows` on every row the report names; the verifier only for claims beyond harness lines (routine identity, cause); a wrong-guess PARTIAL gets one follow-up; a second miss marks it BLOCKED and moves on.


### F22b. `cursor` isolated: match the x>=112 unshared mid-battle content on the fixture side  *(NEGATIVE -- 2026-09-13, cursor fixture backdrop-seed probe refuted, nothing landed)*

**Result.** cursor fixture backdrop-seed probe refuted, nothing landed. 620802/6884/170 unchanged (verify_rows PASS on HEAD, negative not blind); load-peeked seed (entry 15/timer 3/scroll 629/913) scored 1295120 at offset 237 (worse than 779920 there), reverted with clean tree; offset 237 stands (226 is false minimum, x<112 nonzero there); shift metrology shows coexisting exact translations (116,16)/(52,48) irreconcilable with single clock offset under 2:1 scroll, i.e. BGScrollCB raster-callback behavior needing src/ work; branch deleted, main clean. Worker worker-muse (78 turns, $0.102). Verifier verifier-glm: session internally consistent, all measurements run as described, negative correct; nits: 44% figure unmeasured in transcript, reverted comment's peeked counters really live-register-derived (moot). Next: follow-up owning the row definition (src/ raster-callback mechanism) or re-pin decision.
**Files.** tools/harness.py

**Why.** F22's Result is a precise refutation: `cursor` 620802/6884/170/728447 unchanged (nothing landed, branch empty, deleted); at event-locked offset 237 (252-8-(22-15), canon RAM 0x020364C7 walk 0x0a->4@21->3@51->2@81->1@111->0@141 per custMenuSomeHandler_8028B74 asm03_0.s:5194, rust 252/282/312/342/372) x<112 = 0 over all 170 frames -- walk, bracket, blink, names, pictures, offered deck already exact; the whole 620802 residue is x>=112 unshared mid-battle content (backdrop scroll/art phase, enemy, HP) between the CUSTMATCH fixture (art/scroll 0xFFFF fresh Backdrop) and canon's chipselect state. The re-pin probe 779920/5181/170 was documented NOT applied per coordinator decision B (worse headline, no fix; belongs in the follow-up owning the row definition). F15 left `cursor` unmoved at 620802 while fixing the shared vblank frame, so this is fixture content, not src/.
**Do, in order.**
1. Start in `tools/worktree.sh f22b-cursor-fixture`. Baseline `python3 tools/harness.py --only cursor` (must read 620802/6884/170, negative confirmed not blind), plus `tools/diffmask.py` x<112 vs x>=112 split confirming x<112 = 0 over all 170 frames at the event-locked alignment, measured.
2. Match the x>=112 content on the fixture side only: peek the backdrop art/scroll phase, enemy and HP state from canon's chipselect capture state with `peeked` provenance into the CUSTMATCH descriptor, or blank the same element on BOTH sides, never one; keep the event-locked alignment (offset 237 unless a `--watch 0x020364c0:0x48` event names a new frame per F2's rule), measured on the same 170 frames and x>=112 region.
3. Re-run `cursor`, `wave`, `window`, `opening`, `chip-cannon` and the full table -- nothing may get worse, and a row that does is reported with its numbers, measured.
**Rules.** Fixture/descriptor with `peeked` provenance (or symmetric blanking on both sides) only; no src/ change unless the measurement names a cursor element; no allowlist change; no alignment change except by measured event; captures one at a time.
**Measure and report.** Row `cursor` before/after (total/worst/frames) on the identical script and window, x<112 vs x>=112 split before/after, full-table deltas.
**Coordinator:** `verify_rows` on every row the report names; the verifier only for claims beyond harness lines (fixture-content class, peeked offsets); a wrong-guess PARTIAL gets one follow-up; a second miss marks it BLOCKED and moves on.


### F18b. `windowclose` isolated: the k=11 transient and the slide residue outside the window layer  *(PARTIAL -- 2026-09-13, windowclose 666451/28784/40->651885/28430/40 [k=11 BG3 transient 2447->0)*

**Result.** windowclose 666451/28784/40->651885/28430/40 (k=11 BG3 transient 2447->0; relocated to k=9 1898 + k=10 1408, net -14566). Same-call Done at x==SLIDE_FROM in src/custom.rs per canon sub_8026BF4 (asm03_0.s:1037, flip 1119-1125); guards wave/window/opening/chip-cannon 0, opening integrated 72499 pre-existing; field-integrated 358291->358162 (worst same, in cap). Landed f5e5380. Worker worker-muse. Verifier verifier-glm: all 4 claims CONFIRMED (asm cite line-for-line, relocation consistent, field delta measured both sides, clean single-commit tree). Remaining: relocated k=9/k=10 close-frame blank/redraw needs canon-91 scroll/map evidence (F18c).
**Files.** src/custom.rs, tools/harness.py

**Why.** F18's Result: `windowclose` 695603/28784/40/778748 -> 666451/28784/40/749690; post-close flat band k=12..39 1402->0 (gauge 980 not-full fill 0x9222 all 16 cells per sub_801C4E4 loc_801C534 + name 422 blanked per sub_8026BF4->sub_8029D80 w=7/h=2 tile 0); slide k=0..9 still 0 on `--only-bg 3`; k=11 transient 2447 unchanged (close-sequencing off-by-one, follow-up). The remaining residue is the close sequencing plus whatever the slide frames carry outside the window layer -- offset 253 stands (JumpOffset 0x04->0x08 on the A-press frame, slide counter +0x40 counting 0x0c..0x78 across canon frames 81..90, rust slide calls at capture 261..270).
**Do, in order.**
1. Start in `tools/worktree.sh f18b-windowclose-k11`. Baseline `python3 tools/harness.py --only windowclose` (must read 666451/28784/40 at offset 253, negative confirmed not blind), plus `--only-bg 3` slide-frame totals (k=0..9 at 0, k=11 at 2447) and per-frame k=11 bbox, measured.
2. Localize the k=11 transient to the close-sequencing off-by-one and the slide frames' residue outside the window layer, find canon's close routine in `reference/bn6f` and cite it, fix `src/` only, measured on k=11 and the same slide frames/region.
3. Re-run `windowclose`, `wave`, `window`, `opening`, `chip-cannon` and the full table -- nothing may get worse, and a row that does is reported with its numbers, measured.
**Rules.** `src/` only; no allowlist change; no alignment or region change except by measured event -- offset 253 stands unless the watch names a new event frame (F2's rule); captures one at a time.
**Measure and report.** Row `windowclose` before/after (total/worst/frames) on the identical script and window, `--only-bg 3` slide-frame totals and k=11 transient before/after, full-table deltas.
**Coordinator:** `verify_rows` on every row the report names; the verifier only for claims beyond harness lines (routine identity, sequencing cause); a wrong-guess PARTIAL gets one follow-up; a second miss marks it BLOCKED and moves on.


### F18c. `windowclose` isolated: the relocated k=9/k=10 close-frame blank/redraw  *(PARTIAL -- 2026-09-13, windowclose 651885/28430->650544/27555/40 [BG3 k9 1898->0, k10 1408->0, k11 0->1596)*

**Result.** windowclose 651885/28430->650544/27555/40 (BG3 k9 1898->0, k10 1408->0, k11 0->1596; net -1341). Deferred scroll-reset/redraw one frame in src/battle.rs (close_redraw_pending, gauge gated so blank stays blank) per RenderInfo+0x18 watch (0x78@90->0@91) and 80B blanking at canon 91; guards 0, field-int 358162->357495 (in cap). Landed b0ba8a5. Worker worker-muse. Verifier verifier-glm: all 4 CONFIRMED with independent reproduction (parent 651885, branch 650544, BG3 profiles exact). Remaining: k11 1596 gauge-body single-step redraw (F18d).
**Files.** src/custom.rs

**Why.** F18b's verified Result: `windowclose` 666451/28784/40 -> 651885/28430/40 (landed f5e5380); the k=11 BG3 transient (2447) is 0, but relocated to k=9 1898 (x0-11 y0-159, close-frame scroll-0-blank) + k=10 1408 (x2-165 y0-15, pre-redraw HUD) vs canon's 0x78-slide then blank-91. Verifier CONFIRMED the relocation is exactly what a one-frame-earlier Done predicts. What is missing is canon-91 scroll/map evidence and a deferred scroll-reset/redraw design, deliberately not widened into F18b.
**Do, in order.**
1. Start in `tools/worktree.sh f18c-windowclose-k9k10`. Baseline `python3 tools/harness.py --only windowclose --no-gallery` (must read 651885/28430/40 at offset 253, negative confirmed not blind), plus `--only-bg 3` per-frame k=9/k=10/k=11 totals and bboxes, measured.
2. Peek canon's scroll/map state at the blank-91 frame and the 0x78-slide frames from the row's own capture state, then design the deferred scroll-reset/redraw in `src/custom.rs` citing canon's close routine in `reference/bn6f`, measured on k=9/k=10 and the same region.
3. Re-run `windowclose`, `wave`, `window`, `opening`, `chip-cannon` and the full table -- nothing may get worse, and a row that does is reported with its numbers, measured.
**Rules.** `src/` only; no allowlist change; offset 253 stands unless a watch names a new event frame (F2's rule); captures one at a time.
**Measure and report.** Row `windowclose` before/after (total/worst/frames) on the identical script and window, `--only-bg 3` k=9/k=10/k=11 before/after, full-table deltas.
**Coordinator:** `verify_rows` on every row the report names; the verifier only for claims beyond harness lines (routine identity, scroll/map attribution); a wrong-guess PARTIAL gets one follow-up; a second miss marks it BLOCKED and moves on.


### F21b. `result` isolated: the ~2900 px/frame outside the window -- backdrop tail and one-frame slide lag  *(PARTIAL -- 2026-09-13, result 408337/31895->190633/24647/40 [tilemap-column slide j=-30+2/frame + 16-frame hold + peeked backdrop see)*

**Result.** result 408337/31895->190633/24647/40 (tilemap-column slide j=-30+2/frame + 16-frame hold + peeked backdrop seed, k=10,12,13 zeroed; verify_rows PASS, negatives not blind) NOT LANDED: field isolated 0->1048 regression unexplained -- verifier CONFIRMED slide mechanism vs canon driver chain (0xe2 store, +2-col clamp, CopyBackgroundTiles) and offset 31=15+16 arithmetic, but REFUTED the HP-settle-tail story (slide hold + mark re-timing execute inside field compared frames; mark-entry pairing broken); branch wt/f21b-result-tail kept unmerged at 9aa72e9, worktree removed. Worker worker-muse. Verifier verifier-glm: NOT safe to land as-is; also flagged stale asm03_0.s:13225 citation (comment-only). Next: locate field residue per-frame/bbox, re-justify field event pairing (F21c).
**Files.** src/results.rs, src/backdrop.rs

**Why.** F21's Result: `result` 497967/31882/40/476424 -> 408337/31895/40/383600 (-89630); WIN reward drawn on first confirm not at show per canon chain sub_802C34E->sub_802BE36->sub_802C044 (42 tiles 0x2a)->sub_802C0A4 (30f cooldown 0x1e), driver sub_802BD60; phases Waiting->Revealing42->Cooldown30->RewardWait->Dismissing, LOSE unchanged; plateau inside 3734->904, outside ~2900 px/frame backdrop tail + slide lagging canon by about a frame remain. Reward fields (result_frames=1760/level=2/zenny=100, megaman_hp=60) already match; result_elapsed=0 stays untouched. What is left is pre-arrival battle tail state plus the slide phase landing late.
**Do, in order.**
1. Start in `tools/worktree.sh f21b-result-tail`. Baseline `python3 tools/harness.py --only result` (must read 408337/31895/40 at offset 15, negative confirmed not blind), plus `tools/diffmask.py` inside-vs-outside-window split (inside plateau ~904, outside ~2900/frame) and `tools/oracle.py result` where supported, measured.
2. Measure with the oracle and `--watch-write` which write lands late (backdrop art/scroll tail vs slide-phase write), seed RESULT_ROW art/scroll from peeked RESULT_ARRIVAL RAM, then fix `src/` citing canon's driver sub_802BD60 chain (sub_802C34E->sub_802BE36->sub_802C044->sub_802C0A4), measured on the same outside-window frames and region.
3. Re-run `result`, `wave`, `window`, `opening`, `chip-cannon` and the full table -- nothing may get worse, and a row that does is reported with its numbers, measured.
**Rules.** `src/` (or fixture/descriptor with `peeked` provenance when the residue is the tail state) only; no allowlist change; no alignment or region change except by measured event (F2's rule); result_elapsed=0 and the reward fields stay untouched unless the measurement names them; captures one at a time.
**Measure and report.** Row `result` before/after (total/worst/frames) on the identical script and window, inside/outside-window split before/after, oracle/watch-write writer and frame before/after, full-table deltas.
**Coordinator:** `verify_rows` on every row the report names; the verifier only for claims beyond harness lines (routine identity, tail-state attribution); a wrong-guess PARTIAL gets one follow-up; a second miss marks it BLOCKED and moves on.


### F21c. `result` field-row pairing: re-justify after the slide rework  *(BLOCKED -- 2026-09-13, field re-pairing blocked on scope decision, nothing landed)*

**Result.** field re-pairing blocked on scope decision, nothing landed. result 190633 + field 1048/177 reproduced on wt/f21c-field-pairing (=9aa72e9); residue is mark-entry steps k=34-39 (163+177x5=1048); root cause measured as CPU overrun not content: per-tick full-map rewrite (576 set_tile -> VRAM-manager HashMap churn, 0.46 frame/blit, stalls ~1-in-3 through slide frames 133-159) so our mark dwells 2 frames/step vs canon 1/frame -- no offset pairs them; skip-cache+blank-init+tile-warming cut stalls 10->1 but remnant at capture 148/149 (public-API floor still over), all reverted; clean fix needs vendor raw-map API (out of scope) or uncertain base cuts; also verified sub_802CA5C true line 13325 not 13225 (citations still stale, comment-only). Branch deleted, wt/f21b-result-tail kept unmerged, main at 408337 (verify_rows PASS). Worker worker-muse (revived after first attempt failed). No verifier (nothing landed; overrun is measurement for the scope call). No third ticket per two-in-a-row rule -- next is the scope decision itself.
**Files.** src/results.rs, tools/harness.py

**Why.** F21b's verified Result: `result` 408337/31895 -> 190633/24647/40 on branch wt/f21b-result-tail (kept unmerged at 9aa72e9) via tilemap-column slide (START_X=-240, SLIDE_STEP=16, SLIDE_HOLD=16) plus peeked backdrop seed; verifier CONFIRMED the mechanism against the canon driver chain but REFUTED the field-regression story -- the 16-frame hold and re-timed mark execute inside the field row's compared frames (field ZERO_ENEMY_RESOLVED has no result_elapsed key, hold applies; mark entry steps no longer pair with canon's 163..166), so field isolated 0 -> 1048/177 is mark/slide re-timing, not an HP tail. Also flagged: stale asm03_0.s:13225 citation for sub_802CA5C (comment-only) and the offset 31=15+16 justification living only in results.rs, not the harness note.
**Do, in order.**
1. Start in `tools/worktree.sh f21c-field-pairing` from branch wt/f21b-result-tail (continue that work, do not start from main). Baseline `python3 tools/harness.py --only result,field --no-gallery` (must read result 190633/24647/40 and field isolated 1048/177, negatives not blind), plus per-frame/bbox location of the field residue, measured.
2. Re-justify the field row's event-derived pairing against the new mark timeline (or re-time the mark so the field row pairs at 0 again), fix the 13225 citation, document the offset-31 justification in the RESULT_ROW harness note per F2's rule, measured on the field row and the result row.
3. Re-run `result`, `field`, `wave`, `window`, `opening`, `chip-cannon` and the full table -- nothing may get worse; field isolated must read 0 again before this lands with F21b's result improvement.
**Rules.** src/ + harness-note documentation only; no allowlist change; no region change; captures one at a time.
**Measure and report.** Rows `result` + `field` before/after (total/worst/frames), field residue bbox before/after, full-table deltas.
**Coordinator:** `verify_rows` on every row the report names; the verifier only for claims beyond harness lines (pairing attribution); a wrong-guess PARTIAL gets one follow-up; a second miss marks it BLOCKED and moves on.


---

# archived 2026-09-14

### F18d. `windowclose` isolated: the k11 gauge-body single-step redraw  *(DONE -- 2026-09-13, windowclose 650544/27555/40->648948/27391/40 [BG3 k11 1596->0, x48-191 y0-15])*

**Result.** windowclose 650544/27555/40->648948/27391/40 (BG3 k11 1596->0, x48-191 y0-15); wave/window/chip-cannon 0; opening isolated 0 (integrated 72499 pre-existing on base); verifier CONFIRMED all 3 claims (149B+50B single-step canon redraw, 1-frame agb lag mechanism, close_blank arms only on close); landed bb8e8f0; worker muse-spark-1.3-contributor 83 turns $0.106, verifier GLM
**Files.** src/battle.rs, src/custom.rs

**Why.** F18c's verified Result: `windowclose` 651885/28430 -> 650544/27555/40 (landed b0ba8a5); BG3 k9/k10 are 0, but k11 carries 1596 (x48-191 y0-15 canon-only): our gauge body lands k12 vs canon's single-step 149B+50B redraw at canon 92 (RGB-proven, mechanism unmodeled). Verifier independently reproduced the k9/k10/k11 relocation and confirmed a -369 px non-BG3 improvement rides along (net full-screen -1341).
**Do, in order.**
1. Start in `tools/worktree.sh f18d-windowclose-k11`. Baseline `python3 tools/harness.py --only windowclose --no-gallery` (must read 650544/27555/40 at offset 253, negative confirmed not blind), plus `--only-bg 3` per-frame k=10/k=11/k=12 totals and bboxes, measured.
2. Model canon's single-step gauge redraw at canon 92 from the row's own capture state (149B+50B regions, palette/tile writes), then land our gauge body one frame earlier in `src/` citing canon's close routine in `reference/bn6f`, measured on k=11/k=12 and the same region.
3. Re-run `windowclose`, `wave`, `window`, `opening`, `chip-cannon` and the full table -- nothing may get worse, and a row that does is reported with its numbers, measured.
**Rules.** `src/` only; no allowlist change; offset 253 stands unless a watch names a new event frame (F2's rule); captures one at a time.
**Measure and report.** Row `windowclose` before/after (total/worst/frames), `--only-bg 3` k=10/k=11/k=12 before/after, full-table deltas.
**Coordinator:** `verify_rows` on every row the report names; the verifier only for claims beyond harness lines (redraw attribution); a wrong-guess PARTIAL gets one follow-up; a second miss marks it BLOCKED and moves on.

- F21b PARTIAL -- `result` isolated: the ~2900 px/frame outside the window -- backdrop tail and one-frame slide lag. result 408337/31895->190633/24647/40 (tilemap-column slide j=-30+2/frame + 16-frame hold + peeked backdrop seed, k=10,12,13 zeroed
- F21c BLOCKED -- `result` field-row pairing: re-justify after the slide rework. field re-pairing blocked on scope decision, nothing landed


### F21d. `result`: write the window's tilemap by block copy, not 576 managed tile writes  *(DONE -- 2026-09-13, result 408337/31895->102547/14866/40 [neg 195579 not blind], field 1048/177->0/0/40)*

**Result.** result 408337/31895->102547/14866/40 (neg 195579 not blind), field 1048/177->0/0/40; 17 blits in 17 consecutive frames (1/step, was 2/step +0.47 overrun); wave/window/opening/chip-cannon 0; field-int 358420->305263 better; verifier CONFIRMED all 3 claims (OAM trace 1f/step, refcount audit, scope); landed 90dd655; worker muse-spark-1.3-contributor 77 turns $0.069, verifier GLM
**Files.** src/results.rs, src/backdrop.rs, vendor/agb

**Why.** F21c's verified measurement: F21b's slide rework (result 408337 -> 190633 on wt/f21b) regressed
`field` 0 -> 1048 because our per-tick full-map rewrite (576 `set_tile` calls through agb's VRAM
manager, ~0.46 frame per blit) overruns about one frame in three during slide frames 133-159, so our
RESULT mark dwells 2 frames per step where canon's takes 1; skip-cache + blank-init + tile-warming
cut the stalls 10 -> 1 with a remnant at capture 148/149. Canon copies the tilemap as a block
(`CopyBackgroundTiles` in the sub_802BD60 driver chain). This is the engine-timing class of residue:
fix the mechanism, not the content. **Decision (coordinator, 2026-09-13):** direct VRAM block writes
for this window are in scope, including a helper inside vendor/agb if the public API cannot express
it (fix agb, do not work around it -- see the vendor-deps rule).

**Do, in order.**
1. Start with `bash tools/worktree.sh f21d-blockcopy`, then `git merge wt/f21b-result-tail` (the slide rework,
   kept unmerged; F21c's branch was deleted, its findings are in TODO_ARCHIVE.md). Baseline result and field
   there (190633 / 24647 / 40 and 1048 / 177 / 40) plus wave, window, opening, chip-cannon.
2. Replace the per-tile rewrite with one block copy of the prepared tilemap into the window's BG map
   (memcpy or DMA3 into VRAM, sized to the map; if agb's `RegularMap`/VRAM manager owns that memory,
   add a minimal `copy_map_block` (or equivalent) to vendor/agb with a doc comment, and keep the
   manager's bookkeeping consistent). Measure the blit's cost with a per-frame cycle/scanline probe
   (or the marker's frame counter vs canon's) and report frames per step before/after.
3. **Acceptance.** field back to 0/0/40 (negative not blind); result at or below 190633 with the mark
   dwelling 1 frame per step like canon; wave/window/opening/chip-cannon 0; full table nothing worse.
   Land F21b's rework together with this fix; if the copy cannot reach 1 frame/step, report the
   measured cost per blit and stop.

**Rules.** src/results.rs, src/backdrop.rs and vendor/agb only; no allowlist, alignment or fixture
change. **Coordinator:** verify_rows on result, field and the canaries; the verifier on the
"1 frame per step" claim (it must measure it, e.g. with the oracle or a frame-count watch).


### F25. Mettaur attack phase: enter canon's 106-frame attack cycle like canon does  *(PARTIAL -- 2026-09-13, mettaur 19698/1245/70 unchanged [neg 60824 not blind])*

**Result.** mettaur 19698/1245/70 unchanged (neg 60824 not blind); tiles/gauge iso 0, int 3865/678/8 (neg 15891); popup 60614/1842/80; mm_timer 70/70, enemy_anim k=61 1/70; verifier: routine identity CONFIRMED, attack path matches canon CONFIRMED (period 106, pose 63, strike entry+38), residual = uniform +1 phase offset CONFIRMED-measured, intro-gate attribution UNCHECKED, wave 44v45 UNCHECKED; branch wt/f25-mettaur-attack c7a5ce7 kept unmerged; worker muse-spark-1.3-contributor 86 turns $0.161, verifier GLM
**Files.** src/actor.rs, src/ai.rs

**Why.** Three rows wait on the same missing behavior -- our Mettaur idles while canon's attacks. F17's Result: `mettaur` 19698/1245/70/60824 unchanged pixels, oracle `mm_timer` 70/70 with first divergence `enemy_anim` k=61 (2/70); SWING shows IDLE on the 64th executor tick per canon sub_8109DEC (asm31.s:170830-170848, SWING_POSE=0x40-1 derived); mercy seed/rate/blink predicate settled and untouched. F20b's Result: `tiles`/`gauge` integrated 25979/3282->3865/678/8 (negative 15891 not blind), isolated still 0/0/8, via the HUDMATCH descriptor corrected to canon-peeked BattleObject panel positions (MM (2,2) @0x0203a9c2/3, enemy (5,2) @0x0203ab72/3); the residual 3865 is canon's Mettaur mid-attack (CurState/CurAction 0x04/0x0b) against ours idle -- F17's family, not the fixture. F19's Result (TODO_ARCHIVE.md): `popup` 107511/1348/80/108815 -> 60614/1842/80/60806 (-44%, fixture only, landed c2c24e6); subject center band 0, enemy box 51991->6081, HUD bar 55520 unchanged. Canon anchors: both sides run the same 106-frame Mettaur attack cycle (canon attack animations start at canon frames 32, 138; ours at battle frames 95, 201, 307, 413 -- TODO_ARCHIVE.md F2); enemy slots 0x0203aa88/0x0203ab60/0x0203ac38 per AGENT_GUIDE.md, BattleObject offsets per reference/bn6f/include/structs/BattleObject.inc.
**Do, in order.**
1. Start in `tools/worktree.sh f25-mettaur-attack`. Baseline `python3 tools/harness.py --only mettaur,tiles,gauge,popup --no-gallery` (must read mettaur 19698/1245/70 with negative 60824 not blind, tiles/gauge integrated 3865/678/8 with negative 15891 not blind, popup 60614/1842/80), plus `tools/oracle.py mettaur` (must read `mm_timer` 70/70, first `enemy_anim` divergence k=61) and `tools/diffmask.py` region splits (tiles/gauge OBJ cells, popup HUD bar), measured.
2. Drive our Mettaur into canon's attack cycle: find canon's Mettaur attack-timing/animation routine in `reference/bn6f` and cite it, fix `src/` (attack-phase entry, frame-95-equivalent timing, attack animation/CurState-CurAction) only, measured on the same oracle fields (first `enemy_anim` divergence at/past k=61, attack-cycle phase vs canon's 106-frame period) and the same pixel frames and regions.
3. Re-run `mettaur`, `tiles`, `gauge`, `popup`, `wave`, `window`, `opening`, `chip-cannon` and the full table -- nothing may get worse, and a row that does is reported with its numbers, measured.
**Rules.** `src/` enemy-attack path only; mercy seed/rate/blink predicate, HUDMATCH positions, and popup fixture untouched; no allowlist change; no alignment or region change except by measured event (F2's rule).
**Measure and report.** Rows `mettaur`, `tiles`/`gauge` (both variants), `popup` before/after (total/worst/frames) on the identical scripts and windows, oracle `mm_timer` match count and first `enemy_anim` divergent frame before/after, tiles/gauge OBJ-cell and popup HUD-bar splits before/after, full-table deltas. **Acceptance:** `mettaur` 0/0/70 (negative not blind); `tiles`/`gauge` integrated at or below 3865 decomposed by element with frames and regions (0 if the attack phase lines up); `popup` HUD bar 55520 decomposed, enemy-box element toward 0; isolated variants still 0; nothing worse.
**Coordinator:** `verify_rows` on every row the report names; the verifier only for claims beyond harness lines (routine identity, attack-phase attribution); a wrong-guess PARTIAL gets one follow-up; a second miss marks it BLOCKED and moves on.


### F25b. Mettaur +1 attack-phase offset: attribute it, fix only inside the attack path  *(BLOCKED -- 2026-09-13, attack path pixel-perfect at true phase [offset 204: enemy 0px, MegaMan 30864])*

**Result.** attack path pixel-perfect at true phase (offset 204: enemy 0px, MegaMan 30864); entries canon 31/137/243 vs rust 95/201/307 = exact diff 64 all three (intro-gate hypothesis REFUTED); wave flight 44 vs canon 45 confirmed (shot.rs, out of scope) gives hit diff 63 vs enemy 64 -- incommensurate phases, no in-scope fix; offset 203 unique sharp minimum (19698); verify_rows PASS all MATCH on e708b3b; no verifier (nothing builds on it); second miss, objective BLOCKED; worker muse-spark
**Files.** src/actor.rs, src/ai.rs

**Why.** F25's verified Result (PARTIAL, branch wt/f25-mettaur-attack c7a5ce7 kept unmerged): attack entry now canon-shaped (act 0x0b/anim 0 one frame, pose 63, strike entry+38, period 106; routine identity sub_8109DEC/sub_8109E4A + Decide sub_810A126 CONFIRMED by verifier) but mettaur 19698/1245/70 unchanged, enemy_anim still diverges k=61 (canon 201=0, rust=1). Verifier measured the residual as a uniform +1 attack-phase offset present from the very first attack (canon entries at 31/137, ours shifted +1 throughout). UNCHECKED: whether the +1 comes from the intro-gate (attack-1 has no canon counterpart) or from wave flight 44 vs canon 45 (src/shot.rs pixel claim unverified), and the mm_timer counterfactual.
**Do, in order.**
1. Start with `bash tools/worktree.sh f25b-phase`, then `git merge wt/f25-mettaur-attack` (the verified attack-entry rework, kept unmerged). Baseline mettaur, tiles, gauge, popup there (19698/1245/70, tiles/gauge integrated 3865/678/8, popup 60614/1842/80) plus oracle mm_timer 70/70, enemy_anim k=61.
2. Attribute the +1 phase: trace where our first attack entry's +1 vs canon 31 comes from (intro-gating in ai.rs/actor.rs vs wave-flight timing), measuring entry frames on both sides with watches on this row's own captures. Fix it only if the cause is inside src/actor.rs, src/ai.rs; wave timing (src/shot.rs) may be measured with existing tools but NOT edited. If the cause is the intro/fixture with no canon counterpart, report the measurement and stop (precise negative).
3. Re-run `mettaur`, `tiles`, `gauge`, `popup`, `wave`, `window`, `opening`, `chip-cannon` and the full table -- nothing may get worse, and a row that does is reported with its numbers, measured.
**Rules.** src/actor.rs, src/ai.rs only; no shot.rs/fixture/allowlist/alignment change; no region change except by measured event (F2's rule); captures one at a time.
**Measure and report.** First-entry frames both sides before/after, enemy_anim first-divergence before/after, wave-flight frames both sides (measured, not edited), rows before/after, full-table deltas. **Acceptance:** `mettaur` toward 0 via the phase fix landing inside the attack path; if the +1 is intro/fixture-side, a measured attribution with the entry-frame traces and STOP (a second miss marks the objective BLOCKED).
**Coordinator:** `verify_rows` on every row the report names; the verifier on the phase-attribution claim (it must confirm the +1 source); a second miss marks it BLOCKED and moves on.


### F24. `cursor`/`result` backdrop: port canon's per-scanline BG scroll (the BGScrollCB HBlank raster callback) into src/  *(NEGATIVE -- 2026-09-13, premise refuted: canon battle HBlank scroll callback is nullsub_38 no-op [22/22 backdrop types, verifier CONFI)*

**Result.** premise refuted: canon battle HBlank scroll callback is nullsub_38 no-op (22/22 backdrop types, verifier CONFIRMED in disassembly); sole scroll is per-frame Diagonal3to2 (-0.5/-0.25 px/f) already implemented in backdrop.rs (verifier CONFIRMED); zero edits, tree clean; cursor HEAD 620914@226 / 780032@237 (x<112=112 single frame), result 102547@21; FOUND: F12 landing 54abe87 moved cursor 620802->620914 (+112 one frame, verifier bisected, F18d/F21d exonerated) -- owned by next cursor ticket; worker muse-spark 44 turns $0.018, verifier GLM
**Files.** src/backdrop.rs, tools/harness.py

**Why.** F22's Result is a precise refutation: `cursor` 620802/6884/170/728447 unchanged (nothing landed, branch empty, deleted); at event-locked offset 237 (252-8-(22-15), canon RAM 0x020364C7 walk 0x0a->4@21->3@51->2@81->1@111->0@141 per custMenuSomeHandler_8028B74 asm03_0.s:5194, rust 252/282/312/342/372) x<112 = 0 over all 170 frames -- walk, bracket, blink, names, pictures, offered deck already exact; the whole residue is x>=112 unshared mid-battle content (backdrop scroll/art phase, enemy, HP). F22b's Result refuted the fixture-side fix: a load-peeked backdrop seed (entry 15/timer 3/scroll 629/913) scored 1295120 at offset 237, worse than the 779920 there, and was reverted with a clean tree; offset 237 stands (226 is a false minimum, x<112 nonzero there); shift metrology shows coexisting exact translations (116,16)/(52,48) irreconcilable with a single clock offset under 2:1 scroll -- i.e. per-scanline BGScrollCB raster-callback behavior that no uniform scroll phase or seed can reproduce, needing src/ work. The same mechanism is what the result row's backdrop tail needs: F21's Result leaves ~2900 px/frame outside the window (backdrop tail + slide lagging canon by about a frame), and F21b's branch (408337/31895->190633/24647/40 via tilemap-column slide + peeked backdrop seed) was NOT LANDED after the verifier refuted its tail story. Canon anchors: the battle backdrop scrolls under `BGScrollCB_BG1Diagonal3to2Scroll` (reference/bn6f/asm/asm00_0.s:3272-3288) off the counter pair `eBGScrollCBCounters` at 0x02009690/0x02009694, zeroed exactly once at battle init by `sub_8080D90`; battle frame 0 = both counters 0. F22b was Files tools/harness.py and concluded the row needs a src/ raster-callback mechanism, not another seed.
**Do, in order.**
1. Start in `tools/worktree.sh f24-raster-scroll`. Baseline `python3 tools/harness.py --only cursor,result --no-gallery` (must read cursor 620802/6884/170 at offset 237 and result 408337/31895/40 at offset 15, negatives confirmed not blind), plus `tools/diffmask.py` cursor x<112 vs x>=112 split (x<112 = 0) and result inside/outside-window split (outside ~2900 px/frame), measured.
2. Port canon's per-scanline backdrop scroll into `src/backdrop.rs`: find the HBlank raster callback canon installs for the battle backdrop in `reference/bn6f` (the BGScrollCB family off `eBGScrollCBCounters`), cite the routine line-for-line, and drive our BGOFS writes per scanline from the same counters, measured on the cursor x>=112 frames and the result outside-window frames with per-frame totals and bboxes before/after.
3. Re-run `cursor`, `result`, `wave`, `window`, `opening`, `chip-cannon` and the full table -- nothing may get worse, and a row that does is reported with its numbers, measured.
**Rules.** `src/backdrop.rs` mechanism plus harness row-note documentation only; no uniform-scroll seed or single-offset re-fit; no allowlist change; no alignment change except by measured event -- offsets 237 (cursor) and 15 (result) stand unless a watch names a new event frame (F2's rule).
**Acceptance.** `cursor` 0/0/170 (negative not blind) is the target; a landing needs the x>=112 residue reduced by the per-scanline mechanism itself (routine cited), the result outside-window tail reduced on the same alignment, and nothing worse; if the mechanism is ported and cursor still differs, report the per-frame split and stop (one follow-up at most).
**Measure and report.** Rows `cursor` + `result` before/after (total/worst/frames) on the identical scripts and windows, cursor x<112 vs x>=112 split and result inside/outside-window split before/after, canon raster routine cited with file and lines, full-table deltas.
**Coordinator:** `verify_rows` on every row the report names; the verifier only for claims beyond harness lines (routine identity, per-scanline attribution); a wrong-guess PARTIAL gets one follow-up; a second miss marks it BLOCKED and moves on.


### F25c. `mettaur`: the shockwave's flight is 44 frames, canon's is 45 -- the one frame between the enemy's phase and MegaMan's *(PARTIAL -- 2026-09-13, mettaur 19698/1245->4265/800/70 [neg 45788 not blind], oracle 10/10 fields 70/70 FIRST-DIVERGENCE-none)*
**Result.** mettaur 19698/1245->4265/800/70 (neg 45788 not blind), oracle 10/10 fields 70/70 FIRST-DIVERGENCE-none; verifier CONFIRMED canon citation (sub_80C6B64 present-at-init asm31.s:31461-31496, HP113->114, flight 45) and fix (hop_pending latch, wave 0/buster 3172/cannon 0, no fitted const) and residual distribution (exact 8 frames k=0,1,6,11,17,22,63,68, enemy_anim clean); partial gaps: T3 Timer-field mapping inferred, inbox=0 box-unchecked; acceptance 0 unmet -> branch wt/f25c-wave-flight 6b28e9b KEPT unmerged; third consecutive non-DONE on mettaur objective -> no follow-up per two-in-a-row rule; worker + verifier GLM Landed on main by the human session as a verified partial (land.sh, verify_rows on mettaur and six canaries); the 8-frame spray residue is F25d.
**Files.** src/shot.rs, src/ai.rs, tools/harness.py

**Why.** F25b measured, and verify_rows reproduced, that our Mettaur's attack path is pixel-perfect at
its true phase: at offset 204 the enemy differs by 0 px over the whole row while MegaMan reads 30864;
at the row's offset 203 MegaMan pairs and the enemy is one frame off (19698, the unique sharp
minimum). Attack entries are canon 31/137/243 vs ours 95/201/307, exactly 64 apart all three times,
so the intro-gate story is refuted. The one frame is the shockwave: ours reaches MegaMan 44 frames
after launch, canon's 45 (F25b confirmed it in src/shot.rs and declared it out of that ticket's
files). That is not a block, it is the fix. shot.rs already notes that shots are stepped before the
actors ("PRE-TICKED", src/shot.rs:145-147), which is the kind of ordering that costs one frame.

**Do, in order.**
1. Start in `tools/worktree.sh f25c-wave-flight`. Baseline mettaur (19698/1245/70 at offset 203,
   negative 60824 not blind) and wave, window, opening, chip-cannon, field, result, plus tiles/gauge
   integrated (3865) and popup (60614).
2. Measure canon's shockwave frame by frame from the Mettaur's launch to the hit: the wave object's
   slot, x position and timer per frame (probe.py watch on both sides, same launch frame), and the
   frame MegaMan's HP drops and his mercy counter starts. Do the same on ours. Name the frame where
   the two diverge (spawn delay, hop cadence, hit-check order) and cite canon's routine for that step.
3. Make ours identical there (src/shot.rs, or src/ai.rs if it is the launch), with a provenance
   comment. Then re-align the mettaur row only by the measured event (the enemy's attack entry and
   MegaMan's hit now at the same offset), never by score.
4. **Acceptance.** mettaur 0/0/70 (negative not blind) at one offset for both the enemy and MegaMan;
   wave, window, opening, chip-cannon, field, result 0 or unchanged; tiles/gauge integrated and popup
   re-measured and reported (they wait on the same phase); full table nothing worse. If the wave row
   moves, its per-frame split is the report.

**Rules.** src/shot.rs, src/ai.rs and the mettaur row's Align note only; no allowlist change; no fitted
constant (the 45 must come from canon's routine, cited). **Coordinator:** verify_rows on every row
named; the verifier on the canon citation and the "same offset for both" claim; one follow-up at most.


### F25d. `mettaur`: the departure spray on 8 frames, 4265 px, content not timing  *(DONE -- 2026-09-13, mettaur 4265/800/70 -> 0/0/70 [neg 41734 not blind], oracle 10/10 fields 70/70)*

**Result.** mettaur 4265/800/70 -> 0/0/70 (neg 41734 not blind), oracle 10/10 fields 70/70; cause: hop-spawned shockwave segments were created with the sprite's fresh flag set and skipped their first update, so every animation-frame change and despawn on them ran one frame late (the eight residue frames k=0,1,6,11,17,22,63,68 were exactly those changes; tiles and palette bytes byte-identical at phase-aligned pairs); fix: one self.player.update() after the spawn in Shot::update per canon t3_0x16_80C6B40 (asm31.s:31413-31420, state 0 sub_80C6B64 loads the sprite then falls through to object_updateSprite the same frame); wave/window/opening/chip-cannon/result unchanged, field isolated 0, field integrated 305258->305263 (+5 px on one scanline y=0 of one frame, ROM-layout timing sensitivity, ticketed as F30); landed by the human session via land.sh (verify_rows PASS on 7 rows); Claude Opus agent, 73 tool calls, 16 min.
**Files.** src/shot.rs, src/spr.rs, assets/

**Assigned to a Claude agent (2026-09-13 20:20, the user's Claude quota window).** pi's loop skips any status but OPEN.

**Why.** F25c fixed the one-frame hit (shockwave flight 44 -> 45 per canon sub_80C6B64) and landed on
main as a verified partial: mettaur 19698/1245 -> 4265/800 at offset 203, the oracle's ten state
fields match 70/70, and the residue sits on exactly eight frames (k=0,1,6,11,17,22,63,68), all outside
the enemy box, at the same post-hit phase on both sides. So the shockwave's departure spray around
MegaMan differs in content, not timing (F25c's verified reading). That is the last thing between the
mettaur row and 0.

**Do, in order.**
1. Start in `tools/worktree.sh f25d-spray`. Baseline mettaur 4265/800/70 (negative 45788 not blind).
2. On those eight frames dump both sides' OAM for the spray objects (tile index, palette, position,
   size, flip) and the tile bytes they point at, and say which differs: the art (asset), the palette,
   or the sequence (which sprite on which frame). Cite canon's animation script for the spray (the
   shockwave object's own anim, the family around sub_80C6B64), with file and lines.
3. Fix it at the source: art extracted from the canon ROM into assets/, or the sequence in src/,
   with a provenance comment. Never hand-drawn art.
4. **Acceptance.** mettaur 0/0/70 (negative not blind); wave, window, opening, chip-cannon, field,
   result 0 or unchanged; tiles/gauge integrated and popup re-measured and reported; nothing worse.

**Rules.** No alignment or allowlist change; src/shot.rs, src/spr.rs and assets/ only.
**Coordinator:** verify_rows on every row named; the verifier on the canon citation; one follow-up.


### F27. `popup`: the OBJ-layer element canon draws over the enemy and ours does not (55520 px)  *(CLAUDE -- 2026-09-13)*

**Files.** src/hud.rs, src/hudtiles.rs, assets/ (new files only), tools/harness.py (the popup row's note only)

**Why.** popup 60614/1842/80 (negative 60806 not blind). F19 left it at: subject band 0, enemy box 6081,
and 55520 px in the region it called the HUD bar that is canon-only OBJ (capturing both sides with
`--disable-obj` removes it). F20 showed the integrated tiles/gauge OBJ residue was object positions;
this one is an object we do not draw at all. Identify it by OAM first: canon's object slot, tiles,
palette, position and visibility per frame over the 80 frames, and the routine that spawns and
drives it (cite file:line). Then implement it in ours from canon's data: tiles extracted from the
canon ROM into assets/, timing and position from the routine, never hand-drawn or fitted.
**Acceptance.** the popup row's HUD-bar region 0 on all 80 frames and the popup total reported
(enemy box 6081 may remain, it is F28's); wave, window, opening, chip-cannon, field, tiles, gauge 0;
full table nothing worse.


### F28. Mettaur: its first attack starts 64 frames after canon's, relative to battle start  *(PARTIAL -- 2026-09-13, premise refuted as a defect, two real frames fixed, landed)*

**Result.** premise refuted as a defect, two real frames fixed, landed. The 64 = 34 + 30: canon's pausedwithcannon.state resumes a Mettaur already spawned and mid-hop (slot 0x0203ab60, not 0x0203aa88 which is empty; CurAction 0x0a frames 0-27, 0x08 28-30, 0x0b from 31) while ours runs from init (0x00 to battle 61, 0x09 from 62, 0x0b at 95): 34 frames of scene difference plus canon's one-time 30-frame post-spawn wait an already-spawned Mettaur never runs; a constant the alignment absorbs. Real defects: sub_8109CBC (asm31.s:170665-170672) exits its wait when the subtract goes negative so an arming of 0x1e is 31 frames (ours 30), and sub_810A004's Param4 branch (asm31.s:171296-171305) spends its own frame arming the wait (ours was born inside it); fixed in src/ai.rs (param4 its own field, born in RowCheck, the waiter owns its last frame); our entries now battle 97/203/309. Alignment by event: mettaur offset 203 -> 205 (V 204/206 = 46297/37873 identical shape), wave 345 -> 347 (346/348 = 4800/3840); on the branch mettaur 4265/800/70 (pre-F25d base), wave 0/0/90, tiles/gauge integrated unchanged 3865/678/8 (neg 15891), isolated 0/0/8, popup unchanged, field integrated +5 (305258->305263, worst same, enemies:0 row). Why tiles/gauge integrated cannot be 0 yet: HUDMATCH clears FLAG_OPEN_WINDOW and src/battle.rs:2107-2110 re-arms gauge_pause every frame with the gauge full while only the open-window branch decrements it, so our battle freezes from battle 62 and the Mettaur never leaves CurAction 0x09; the whole 3865 is its idle sprite vs canon's swing (bbox (164,68)-(204,111), every other pixel 0); the one-line fix alone makes the row worse (16130) because by battle 427 our MegaMan has taken two shockwave hits (HP 60->50 at 177, ->40 at 389) and blinks while canon's holds 60 unhit: the fixture must seed MegaMan's HP/mercy like it seeds the backdrop and gauge (F28b). popup's rust side has no enemy at all (enemies:0) while canon's is deleted and dissolving: the enemy-box residual is 7 frames k=0..6, not the tiles/gauge phase. Claude Opus agent, 101 tool calls, 32 min, 247k tokens.
**Files.** src/ai.rs, src/fixture.rs, tools/harness.py (the mettaur/tiles/gauge Align only, by measured event)

**Why.** F25b measured the attack entries: canon at battle frames 31/137/243, ours at 95/201/307,
the same 106-frame period on both sides and exactly 64 later on ours all three times. The mettaur
row hides it by pairing attack indices (offset 203); the gauge-aligned integrated rows do not:
tiles/gauge integrated 3865/678/8 (negative 15891 not blind) is canon's Mettaur mid-attack
(CurState/CurAction 0x04/0x0b) against ours idle, and it is part of popup's enemy box (6081) and of
windowclose's remainder. Find where the 64 comes from by measurement, not by guess: canon's Mettaur
AI timer from battle init (enemy slot 0x0203aa88, its AI data and timer fields; the routine that
seeds the first attack delay; whether the intro banner gates it) against ours, on the same battle
frame numbering; or a fixture difference in when our battle starts relative to the gauge. Fix at the
source with the citation.
**Acceptance.** tiles/gauge integrated 0/0/8 (negative not blind); mettaur at or below 4265 on its
event-locked alignment (if the event moves, re-sweep the band and report the new unique minimum
and the event that names it); popup's enemy box reported; wave, window, opening, chip-cannon, field
0; full table nothing worse.


### F29. `windowclose`: decompose the remaining 648948 by layer and frame, fix what lives in the window  *(PARTIAL -- 2026-09-13, windowclose 648948/27391/40 -> 407778/11879/40 [neg 534875 not blind], landed)*

**Result.** windowclose 648948/27391/40 -> 407778/11879/40 (neg 534875 not blind), landed; cursor exactly 620802/6884/170 unchanged though it shares CUSTMATCH_ROW; full table otherwise identical, field integrated -5. Decomposition at offset 253: BG0 0, BG3 0 (F18-F18d), BG2 field 266412/18864 on k=1..19 = canon's 15-px camera pan driven from inside the window's slide routine (sub_8026BF4 adds dword_8026CC8=0x18000 to Camera+0x34 per slide-out call, asm03_0.s:1099-1104, constant :1141-1142, slide-in subtracts :964-969) with an arithmetic shift (floor), ours ten frames late with ceil -> fixed in src/battle.rs (pan on the slide calls via Custom::is_closing(), div_euclid floor; FIELD_SLIDE/FIELD_SLIDE_STEP now derived = 10 x 0x18000), BG2 0 on all 40 frames; OBJ 97644 = MegaMan's panel (CUSTMATCH_ROW megaman_col/row 3,2 -> 2,3 per canon's BattleObject PanelX/Y +0x12/+0x13, -36620) + the Mettaur's phase (14228, flat 205/frame from k=10) + HP boxes on k<10; BG1 backdrop 877602 = a constant (20,10) px scroll-phase translation on all 40 frames because the fixture seeds no backdrop phase (F26b: per-row seed from canon's counters 0xffff9ad8/0xffffcd6c and GFX entry 25 at canon frame 81; a shared seed takes cursor to 1222398) plus the odd-frame lsr-vs-floor rounding backdrop.rs:278-283 predicts. Trap recorded: -x.div_euclid(2) parses as -(x.div_euclid(2)) and reproduces the old rounding on odd frames. Remaining 407778 = BG1 phase + Mettaur phase. Claude Opus agent, 103 tool calls, 33 min, 414k tokens.
**Files.** src/custom.rs, src/hudtiles.rs, src/field.rs, tools/harness.py (the windowclose row's note only)

**Why.** windowclose 648948/27391/40 after F18-F18d fixed the close transients; the slide (k0-9) is
0 and the rest is the forty frames as the battle resumes behind the closing window, which nobody has
decomposed. Capture both sides per layer (`--only-bg N`, `--disable-obj`, identical on both sides)
and produce a per-frame table layer x px x bbox; name the mechanism for each non-zero layer with a
canon citation: the Mettaur's phase (F28's 64 frames), the backdrop's scroll and art phase, the HUD,
the window's own tiles and scroll. Fix what lives in your files; for causes in files other workers
hold (src/backdrop.rs, src/actor.rs, src/battle.rs, src/shot.rs, src/ai.rs) report the exact change
as a proposal with the measurement behind it.
**Acceptance.** the decomposition table with citations; every fix verified on windowclose plus
wave, window, opening, chip-cannon, field; full table nothing worse.


### F31. `buster`: 3172 px over 32 frames, blocked twice, a fresh measurement  *(PARTIAL -- 2026-09-13, the row is vacuous: canon's OAM over the window holds four idle-MegaMan objects plus, from canon frame 164, th)*

**Result.** the row is vacuous: canon's OAM over the window holds four idle-MegaMan objects plus, from canon frame 164, the battle-result mark (16x16 tile 0x200 pal 11 prio 0 sliding to (37,21)): 163 + 17x177 = 3172 = the whole row, on k=14..31; canon's scripted B at 150/151 never fires (CurState/CurAction/CurAnim/HP 04/08/00/60 and the sequencer 0x0400000c constant over canon 145..186, F10's 0x0C delivery wall re-measured) and our ZERO_ENEMY fixture never resolves so we never draw the mark; the alignment 122 is the first of an 8-wide plateau (122..129 all 3172; 90..105 all 13959; the event-locked offset 100 reads 13959/794/32); our buster pose (rust 111..129) lies entirely outside the compared window 130..161. Landed: canon's t3_0x0_80C4E58 (asm31.s:27690-27697, off_80C4E70 :27703, sub_80C4E7C sprite_load :27725-27727) shows a shot's first animation frame on its spawn frame, ours ran a frame late (fresh player's first update eaten, src/spr.rs:336-343): the pre-tick now lives once in Shot::new (removed from shockwave(), behaviour-neutral for every current row; full table byte-identical both ways, field integrated -5). The plain buster builds no Shot at all (Update::Strike charged:false is a hitscan). Measured against a canon side that fires (Start@10,B@30,B@31 in the 0x08 window): pose 25 frames = 5 fire ticks (sub_80EB450 asm31.s:108680-108691) + byte_80209CC[Rapid*6+min(free panels,5)] (sub_800FAF6 asm00_2.s:1944-1990, dat01.s:146) = 5+0x14 vs ours 19; barrel at pose+0 vs ours +2 (BUSTER_ARM_DELAY); muzzle at pose+1 vs +4 and our FX double-ticked on its spawn frame (battle.rs:2623 fx.update() plus the effects loop); both objects live until object_exitAttackState (sub_80EB502 asm31.s:108712-108722) vs our fixed 18/7 frames. Next: F31b re-cuts the row around a canon side that fires and lands those four. Claude Opus agent, 69 tool calls, 20 min, 195k tokens.
**Files.** src/shot.rs, tools/harness.py (the buster row's note only)

**Why.** buster isolated reads 3172 px over 32 frames and has been BLOCKED since F10/F10b (two
misses: read both Results in TODO_ARCHIVE.md before anything else, and F1's, which changed the hit
frame in shot.rs). F25d just showed the shape of these residues on the mettaur row: not art, not
timing constants, but one object updating a frame late because our object lifecycle differs from
canon's dispatcher (spawn-frame update). Measure the buster the same way: both sides' OAM for the
shot and MegaMan per frame over the 32 frames, the tile bytes at phase-aligned pairs, the frame the
shot spawns, moves and despawns, and the frame the enemy reacts (HP at 0x0203aa88+0x24, state +8/+9);
cite canon's buster object routine and MegaMan's shooting state in reference/bn6f (file:line).
**Acceptance.** buster 0/0/32 (negative not blind) with no alignment change except by a measured
event; wave, window, opening, chip-cannon, field, mettaur 0; full table nothing worse. src/actor.rs
is held by other workers: a change needed there is reported as an exact proposal, not made.


### F30. `field` integrated: a one-scanline write lands on either side of a VBlank boundary depending on ROM layout  *(PARTIAL -- 2026-09-13, layout race 10585px [[8,10585]] -> 0 over 200 frames across ROM layouts [worker])*

**Result.** layout race 10585px [(8,10585)] -> 0 over 200 frames across ROM layouts (worker); verifier CONFIRMED root cause sources (Blend::commit BLDCNT/BLDY, agb early-return wait, canon main.s frame-sync + ProcessGFXTransferQueue) and fix faithful (54 lines, no-op on fitting frames); combination: field/wave/window/opening/chip-cannon/result/mettaur0/popup5094/windowclose407778/buster3172 preserved, cursor 620802->620914 (+112); verifier: one-frame scanline-band diff CONFIRMED, x<112-locality REFUTED, spin-only-cause YES, better-vs-canon UNMEASURED; branch wt/f30-scanline c64b68a KEPT unmerged; worker muse-spark 97 turns $0.078, verifier GLM
**Files.** src/main.rs, src/field.rs

**Why.** F25d measured that two builds differing only in ROM layout (545824 vs 553900 bytes, a
one-statement change elsewhere) differ on field's own rust side at capture 121 by 39 px, all on
scanline y=0, x 67..237, and at the boot frame; field isolated stays 0 but field integrated moved
305258 -> 305263. A write that reaches VRAM or a register during that scanline's draw is sensitive
to CPU time before VBlank: that is an engine-timing bug of ours (canon's driver copies during
VBlank), not a canon difference, and it will bite every integrated row. Find the write (watch VRAM
and the BG registers with mgba_capture --watch-write on that frame), move it under VBlank the way
canon's driver sequences it (cite), and show the two builds' captures identical on every frame.
**Acceptance.** field's rust side byte-identical between two ROM layouts (pad the ROM to prove it)
on all 170 captured frames; field isolated 0; field integrated not worse; wave, window, opening,
chip-cannon 0.


### F30b. VBlank re-sync spin: is cursor frame 0 better or worse, and gate the spin accordingly  *(BLOCKED -- 2026-09-13, spin proven no-op on cursor [6 reps 620802 bit-identical, F30 +112 = layout jitter])*

**Result.** spin proven no-op on cursor (6 reps 620802 bit-identical, F30 +112 = layout jitter); gate KEEP ungated; layout race NOT 0: with spin 6704px@capture8 (frame-121 fixed 85->0, battle-frame-0 remains; masked-VBlank hypothesis UNCONFIRMED, new-mechanism work out of scope); field-int +12 = layout jitter (spin on/off bit-identical 3x); verify_rows PASS 10/10 MATCH on e858b42; no verifier (no follow-up per two-in-a-row: F30 PARTIAL->F30b); branches kept unmerged; worker muse-spark
**Files.** src/main.rs

**Why.** F30's verified Result (PARTIAL, branch wt/f30-scanline c64b68a kept unmerged): the layout race is fixed (10585px -> 0 over 200 frames across ROM layouts; root cause and fix-faithfulness both verifier-CONFIRMED), but the combination moves cursor 620802 -> 620914 (+112). The verifier measured the diff as ONE compared frame (frame 0), a full-width scanline band at y~=40 -- the artifact class the spin targets -- and confirmed the 54-line spin is the only code delta, but better-vs-canon was UNMEASURED (one run per side; emulator nondeterminism not excluded) and the x<112-locality story was REFUTED.
**Do, in order.**
1. Start with `bash tools/worktree.sh f30b-spin-gate`, then `git merge wt/f30-scanline` (the verified fix, kept unmerged). Baseline cursor (620802/6884/170/728447 on main) and field isolated/integrated there.
2. Measure cursor frame 0 against CANON with and without the spin (same-index rust-vs-canon diff on frame 0, repeated runs for nondeterminism): if the spin makes frame 0 better-or-equal vs canon, say so with numbers and keep it; if worse, gate the spin (e.g. only where a layout-divergence is possible, or fix the overrun source on cursor's frame 0) and re-measure.
3. Re-run cursor, field, wave, window, opening, chip-cannon, result, mettaur, popup, windowclose -- nothing worse than main; re-prove the layout-race 0-over-200-frames with the gate in place.
**Rules.** src/main.rs only; no allowlist/alignment/fixture change; no fitted constant; captures one at a time.
**Measure and report.** Cursor frame-0 vs canon with/without spin (repeated), gate decision with numbers, layout-race proof, rows before/after, full-table deltas. **Acceptance:** layout race still 0 AND cursor at or below 620802 with the spin in place; else a measured better-vs-worse verdict and STOP.
**Coordinator:** `verify_rows` on every row the report names; the verifier on the better-vs-worse claim (it must measure it).


### F27b. Emotion window: show it on canon's rule (HUD element mask bit 14, from HUD init to HUD teardown), not "while an enemy is alive"  *(DONE -- 2026-09-13, popup 60614/1842/80 -> 5094/1148/80 [neg 5286 not blind], the x2-45 y18-33 emotion-window box 0 on all 80 fram)*

**Result.** popup 60614/1842/80 -> 5094/1148/80 (neg 5286 not blind), the x2-45 y18-33 emotion-window box 0 on all 80 frames; the residual 5094 is the Mettaur's dissolve (F28). Canon's rule implemented: the emotion window is battle-HUD element 14 (mask dword_20352C0, sub_801BEE0 asm00_2.s:25540-25563, draw sub_801CDEC :27554-27583), cleared with elements 0/1/4/10 by sub_80081A4 -> sub_801BED6(0xE4C53) (asm00_1.s:10617-10621) on the frame the banner sequencer enters the RESULT countdown 0x0C, measured on the real ROM with --watch-write (frame 47 seq 0x0C, frame 48 mask 0x4497->0x0084 at lr 0x080081B9); canon holds the window through the enemy's death and its 47-frame dissolve, ours dropped it at the death. src/battle.rs: hud_live set at HUD init, cleared where over fires (same event in this build), draw gate hud_live && no popup && no fade; src/fixture.rs FLAG_HUD_LIVE bit 6 (peeked) because popup and the 43 chip rows share one zero-enemy descriptor while their canon captures sit on opposite sides of the teardown (popup mask 0x4497 on all 125 frames, afterdissolve 0x8084 on all 47), so only the descriptor can say which; src/emotion.rs LEFT/RIGHT provenance derived from sub_801CDEC. cannon/chip-cannon/chip-invisibl/mettaur/opening/tiles/gauge/field/wave/window/card/banner/cursor/windowclose/result unchanged. Remaining: our end sequence fires over at the last enemy's defeat where canon reaches the RESULT countdown 47 frames later after the dissolve (F32); the teardown models element 14 only. Claude Opus agent, 98 tool calls, 27 min, 380k tokens.
**Files.** src/battle.rs (the emotion-window gate and the teardown only; pi's F12 worker edits other parts of battle.rs), src/emotion.rs, src/fixture.rs (only if a fixture rule must change), tools/harness.py (the popup row only)

**Why.** F27 identified popup's 55520 px: two OBJs at (0,18) 32x16 tile 0x3b4 and (32,18) 16x16 tile
0x3bc, palette 12, priority 2, on all 125 canon frames -- the emotion window, which src/emotion.rs
already draws from assets/emotion.bin with byte-identical tiles and palette. Canon draws it while
bit 14 of the battle-HUD element mask (dword_20352C0, dispatched by sub_801BEE0 asm00_2.s:25540-25563,
draw sub_801CDEC asm00_2.s:27554-27583) is set: 0x4497 on every popup frame (the enemy goes
ALIVE -> DELETE_ENEMY and the window stays), 0x8084 on every frame of the afterdissolve route (HUD
torn down, RESULT countdown). Ours drops it the frame the last enemy is defeated (battle.rs:3682's
`fighting` predicate), which is wrong in a real battle too. F27 measured a fixture-flag workaround
(popup 60614 -> 5094, box 0/80, cannon 0, chip rows unchanged, field integrated +5) and did not land
it because the mechanism is the gate itself.
**Do.** Find when canon clears bit 14 (the caller of sub_802A0F8's hide, asm03_0.s:8317-8333, on the
transition into the RESULT countdown) and measure that frame on a canon capture where the last enemy
dies (the result fixture); make ours hide the window at the same event, and show it from HUD init.
If the zero-enemy popup fixture then tears down at once, fix the fixture's semantics (an empty
enemy list is not a victory; canon never has one) rather than adding a flag; the flag from F27's
proposal is the fallback only if the fixture cannot express canon's situation otherwise.
**Acceptance.** popup at or below 5094 with the x2-45 y18-33 box 0 on all 80 frames (the rest is
F28's Mettaur dissolve); cannon 0 and every chip row unchanged (their canon mask has bit 14 clear, so
ours hides at the same frame -- measure the hide frame on both sides on one chip row); result,
field, wave, window, opening unchanged or 0; nothing worse.


### F26. `cursor`: decompose the x>=112 residue by layer and name each layer's mechanism  *(PARTIAL -- 2026-09-13, layer table delivered: BG0/BG2/BG3 0, BG1 scroll rates match [verifier CONFIRMED counters+zeroing+rate], BG1 a)*

**Result.** layer table delivered: BG0/BG2/BG3 0, BG1 scroll rates match (verifier CONFIRMED counters+zeroing+rate), BG1 art citations CONFIRMED; verifier FLAGS OBJ arithmetic (689572>620802 total, must be redefined) and marks UNCHECKED: 2-frame art lead, Mettaur kind-byte/variant, portrait box-x, MegaMan panel; no src change, tree clean; worker muse-spark 38 turns $0.021, verifier GLM
**Files.** src/backdrop.rs, src/actor.rs, tools/diffmask.py, tools/probe.py

**Why.** F24 refuted the raster theory: canon's battle HBlank scroll callback is a no-op (nullsub_38 for
all 22 backdrop types, verifier confirmed in the disassembly) and the per-frame diagonal 3:2 scroll is
already in backdrop.rs. So F22b's two "coexisting translations" (116,16) and (52,48) are two different
things on two layers, not one mechanism. cursor reads 620914/.../170 at offset 237 (F12's landing
54abe87 added +112 on one frame; F18d/F21d exonerated); x<112 is 0 on every frame (walk, bracket,
blink, names, pictures, deck exact). Everything left is x>=112: the battle behind the custom window
(backdrop, panels, Mettaur, HP). Nobody has measured which layer carries what.

**Do, in order.**
1. Baseline cursor at offset 237. Capture both sides with each layer alone (`--only-bg N` and
   `--disable-obj`, identical on both sides) and diff per layer per frame: report which layers carry
   the residue and each one's per-frame shape (px, bbox, first differing frame).
2. For each non-zero layer, find its mechanism by measurement, not by fit: for the backdrop BG, the
   scroll (canon's counters at 0x02009690/0x02009694 vs our scroll state, per frame) and the art
   phase (which tile set is uploaded on which frame, the step counter); for OBJ, the Mettaur's
   CurState/CurAction and animation frame vs ours (F25/F25b's one-frame phase) and the HP/HUD
   objects; for the panel BG, the tilemap content. Name the first differing frame and field per
   layer and cite canon's routine.
3. If a layer's cause is a small fix in src/ with a canon citation, make it and measure; otherwise
   stop with the decomposition. **Acceptance.** a table layer x (px, first differing frame, mechanism
   with canon routine); the +112 one-frame change from 54abe87 attributed to its object and push
   order; any src/ change verified on cursor, wave, window, opening, chip-cannon, result and field
   with nothing worse.

**Rules.** No alignment change except by measured event (offset 237 stands until a watch names a new
event frame); no allowlist change; no seed or scroll refit. **Coordinator:** verify_rows on every
row named; the verifier only if src/ changes or a canon routine is cited.


### F28b. tiles/gauge integrated to 0: unfreeze the HUDMATCH battle and seed MegaMan's mid-battle state; then popup's dissolving enemy  *(DONE -- 2026-09-13, tiles/gauge integrated 3865/678/8 -> 0/0/8 [neg 12843 not blind], isolated 0/0/8 unchanged)*

**Result.** tiles/gauge integrated 3865/678/8 -> 0/0/8 (neg 12843 not blind), isolated 0/0/8 unchanged; popup 5094/1148/80 -> 0/0/80 (neg 1288 not blind); mettaur 0/0/70, wave/window/card/banner/opening-iso/cannon/warp-iso/field-iso 0 unchanged, field integrated 305263->305251 (worst same, F30), everything else byte-identical; full table rollup PASS. (1) src/battle.rs: gauge_pause re-armed only when open_window_allowed(): canon's fight state opens every frame with UnpauseBattle (sub_800855E asm00_1.s:11125/11132) and pauses only by leaving for the custom screen (sub_800A21C :15203-15218 paired with PauseBattle and state 0x14 at :11188-11195); HUDMATCH (window flag clear) froze its whole battle from the gauge filling. (2) Canon's MegaMan at frames 42..48: HP 0x3c, Timer 0, FlashingInvisTimer (CollisionDataPtr 0x020384f0 +0x24) 0; seeding cannot survive 427 frames of our own battle (two shockwave hits by then), so the HUDMATCH descriptor's phases were translated 318 frames earlier = 3 x 106 (enemy phase preserved): art_entry 5->23, art_timer 4->6 by 318 STEP_ORDER/STEP_HOLD ticks, scroll_xq 424->36, scroll_yq 724->18 (mod 1024), gauge_tick 50->32 by the mod-112 identity, Align band 415..440 -> 97..122, offset 109; left/right halves, HUD strip, both boxes all 0. (3) popup: the corpse draws from tiles up to 0x048, above F9's 768-byte blank -- ENEMY_DISSOLVE_FIRST_PHASE 0x60106E0:576 (5094->2858); the dissolve's transfer queue entries sit in slot 3 (0x0200B4F4 size word) at canon 44/45/48, not F9's slot 41 (a no-op on this row): three one-shot pokes (2858->0); banner 0/0/58 unchanged. Remaining: allowlist AUDIT-6 tiles/gauge entry now dead (removed by the human session after landing). Claude Opus agent, 62 tool calls, 20 min, 346k tokens.
**Files.** src/battle.rs (the gauge_pause re-arm hunk at ~2107 only), src/fixture.rs, tools/harness.py (the HUDMATCH and popup descriptors and notes)

**Why.** F28 measured why tiles/gauge integrated sit at 3865/678/8: HUDMATCH clears FLAG_OPEN_WINDOW and
battle.rs re-arms gauge_pause every frame once the gauge is full, so the rust battle freezes from battle 62
and the Mettaur never leaves its wait; the whole residue is its idle sprite against canon's swing. The
one-line fix (`if self.gauge == GAUGE_FULL && self.open_window_allowed() { self.gauge_pause = GAUGE_PAUSE }`)
alone makes the row worse (16130) because by battle 427 our MegaMan has taken two shockwave hits and is in
mercy while canon's holds HP 60 unhit through frame 51: the fixture has to carry canon's mid-battle MegaMan
(HP, mercy counter, position) the way it already carries the backdrop phase (scroll_xq/scroll_yq) and the
gauge (gauge_tick). Measured with the throwaway unfreeze: the Mettaur's box reads exactly 0 on all 8 frames
at the row's pinned offset 427 after F28's two frames.
**Do.** (1) The gauge_pause fix, cited (canon's custom gauge does not pause a battle whose window cannot
open). (2) A fixture field (peeked provenance) for MegaMan's HP and mercy state, read from canon's
BattleObject at 0x0203a9b0 (+0x24 HP, the mercy counter field) at the row's reference frame, applied at
battle init; HUDMATCH's descriptor carries canon's values. (3) Measure tiles/gauge integrated per half
(left/MegaMan, right/Mettaur). (4) Then popup: its rust side has no enemy (enemies:0) while canon's Mettaur
is deleted and dissolving for k=0..6 (5094 px after F27b); give the fixture the dissolving enemy at
canon's phase (state DELETE, HP 0, dissolve counter peeked) or show why F19's blanking should cover it.
**Acceptance.** tiles and gauge integrated 0/0/8 (negatives not blind) with the isolated variants still 0;
popup 0/0/80 or its residual attributed per frame; mettaur, wave, window, opening, chip-cannon, field 0 or
unchanged; the field integrated +5 re-measured; nothing worse.


### F31b. `buster`: re-cut the row around a canon side that fires, then land the four measured buster defects  *(DONE -- 2026-09-13, buster re-cut and closed: old row [canon idle, 3172 flat over an 8-wide plateau] replaced by one where both si)*

**Result.** buster re-cut and closed: old row (canon idle, 3172 flat over an 8-wide plateau) replaced by one where both sides fire; the press is poked into canon's AIData like F11's warp (the plain buster fires on the RELEASE: JoypadPressed 0x0002, Held, then Released -> CurAction 0x08 -> 0x11; Held alone does nothing for 24 frames; idle Held word 0xfc00), canon_ref = the watched CurAction write 0x11 at canon 132 (0x0203a9b9), anim 0x0e 133..157, barrel in OAM from 134, muzzle 135, both gone 159; 28 frames; band range(96,113) unique minimum 0 at offset 103 (2911 at 102 and 104). Pre-fix 4936/617/28 (neg 6869) -> 0/0/28 (neg 3167 not blind): (1) 4936->736 pose length derived = 5 fire ticks (sub_80EB450 asm31.s:108680-108691) + byte_80209CC[Rapid*6 + min(free panels ahead,5)] (sub_800FAAC/sub_800FAF6 asm00_2.s:1903-1990, dat01.s:146-149), measured at three columns (29/25/21 frames at col 1/2/3, three exact predictions, Rapid row 0), Actor::buster_spec computes it from the navi's column; (2) 736->0 barrel and muzzle live exactly as long as the pose (oAIData_Unk_68 / oBattleObject_RelatedObject1Ptr cleared by sub_80EB502 with object_exitAttackState, asm31.s:108712-108722), BUSTER_ARM_FRAMES/BUSTER_FX_FRAMES gone; (3)(4) strike_at 3->2 (muzzle and damage on the fire phase's second tick, asm31.s:108632-108676) and the extra fx.update() at spawn removed: pixel-neutral here because the two errors cancelled on blank muzzle cells. buster integrated 643698/27225/32 -> 248260/17668/28 (allowed). Full table 48 PASS, every failing row equal to main. Open, pixel-invisible: canon's CurAction 0x11 lands on k=0 while our ORCL export flips to 0x0b on k=1 though both draw the windup on k=0..1 (F36). Claude Opus agent, 32 tool calls, 20 min, 299k tokens.
**Files.** tools/harness.py (the buster row, its fixture and Align), tools/states.py (a recipe if one is needed), src/actor.rs (the BUSTER pose constants only), src/battle.rs (the buster hunks only: fx.update() at ~2623, BUSTER_ARM_DELAY, BUSTER_ARM_FRAMES/BUSTER_FX_FRAMES)

**Why.** F31 showed the buster row measures nothing about the buster: canon's press never fires in it and the
3172 is the result mark; its offset is a plateau tie-break, not an event. Canon fires when the press lands
in the 0x08 window (Start@10,B@30,B@31 on the STERILE+PAUSED+DELETE side: action 0x11 at f33, anim 0x0e
f34..f58, barrel f35, muzzle f36, both gone f60). A row is honest only if both sides fire: cut the canon
side there, lock canon_ref to the measured press event (the action write, watched), align by the same
event on our side (rust press frame), and re-sweep the band for a unique minimum. Then land the four
measured defects (pose length 25 = 5 + byte_80209CC lookup, derived; barrel on tick 0; the FX ticked once
on its spawn frame; barrel and muzzle until object_exitAttackState) with citations, measuring each alone.
**Acceptance.** a new buster row that compares two firing busters (state watches on both sides show the
attack state on the same offset), negative not blind, alignment by event; buster as low as the four fixes
take it; buster integrated re-measured; wave, window, opening, chip-cannon, field, mettaur, popup 0 or
unchanged; every chip row unchanged (they share the fixture path); nothing worse. The old 3172 alignment is
not to be "fixed" by giving our side the result mark: a row that draws nothing on either side proves nothing.


### F33. The integrated variants (field 305263, warp, buster, chip-use): decompose by HUD element with canon's element mask, fix in hud.rs/hudtiles.rs  *(PARTIAL -- 2026-09-13, field integrated 305263/10061/40 -> 304103/10032/40, warp integrated 363658 -> 362788, buster integrated 64369)*

**Result.** field integrated 305263/10061/40 -> 304103/10032/40, warp integrated 363658 -> 362788, buster integrated 643698 -> 642770, chip-use integrated 644119 -> 643191 (all allowed rows; -29 px/frame: ZERO_ENEMY said megaman_hp=100 while every canon side holds 0x3c at 0x0203a9d4, element 2 the HP box); cursor 620802 -> 502822 on the branch and 154367/914/170 on main after F26b (the emotion window's OAM x takes the chip window's slide counter eStruct2035280+0x12 = SLIDE_FROM - x, added by sub_801CDEC asm00_2.s:27561-27572; Custom::hud_obj_x() -> Emotion::show; -117980 exactly as predicted); windowclose 648948 -> 642133 on the branch, 27819/1938/40 on main. Per-element table for field integrated from canon's dispatcher tables (update sub_801BEE0 asm00_2.s:25540-25563 / off_801BF04, draw sub_801BF64 :25564-25599 / off_801BF88; masks on every compared frame 0x0084 update / 0x00c5 draw: elements 2 and 7 updated, 0/2/6/7 drawn, gauge/icon/emotion torn down at canon 48): element 2 HP box 29 px/frame fixed; element 6 chip name + damage (sub_801C6EE :26619) 422 px/frame on field/warp/buster still drawn by canon and not by ours because ours ties the name to the hand with the icon (element 1, torn down) -- measured proposal: ZERO_ENEMY hand=[1] plus battle.rs:3743 filter '&& self.hud_live' gives field 287204 / warp 350128 / buster 629266, neither half alone; gauge_up should also require hud_live (element 4, unmeasured); and 86% of the four rows' residue is the BG1 backdrop phase: ZERO_ENEMY seeds none (canon 130: x -64176 / y -32088 -> x_q 684, y_q 854 by backdrop.rs's arithmetic, art phase to walk back) -- F33b. Landed 870e3ef; post-merge cursor 154367, windowclose 27819, popup/buster/tiles 0. Claude Opus agent, 103 tool calls, 35 min, 255k tokens.
**Files.** src/hud.rs, src/hudtiles.rs, src/emotion.rs, tools/harness.py (the integrated rows' notes only), tools/allowlist.py entries removed only when a row reads 0

**Why.** Four integrated (full-HUD) variants are allowlisted since AUDIT-6 ("HUD vs a zero-enemy arena, not
compared before"): field 305263/10061/40, warp, buster, chip-use, each in the hundreds of thousands. F27b
found the HUD is driven in canon by a per-element enable mask (dword_20352C0; elements 0, 1, 4, 10 and 14
are torn down together at the RESULT countdown by sub_80081A4, asm00_1.s:10617-10621; the dispatcher
sub_801BEE0 asm00_2.s:25540-25563 with an updater and a draw per element, e.g. element 14 = emotion window
sub_801CADC/sub_801CDEC) and that our build models only element 14 of it. Decompose field integrated by
element: capture both sides, split the residue by HUD region (the HP box, the custom gauge, the emotion
window, the hand icon, the enemy HP objects, the chip name/icon) and by layer, name each element's canon
draw routine from the dispatcher table and its enable bit, and compare our drawing of it frame by frame.
**Do.** Fix element by element in your files with citations; measure each; then re-check warp, buster and
chip-use integrated (same HUD) and report their deltas. **Acceptance.** a per-element table for field
integrated with canon routines; field integrated as low as the elements you fixed take it, the isolated
variants and wave/window/opening/chip-cannon/popup/tiles/gauge untouched at their values; an allowlist entry
removed only for a row that reads 0; nothing worse.


### F34b. `result` to 0: no intro fade when the fixture starts on the results screen, MegaMan's panel, no enemy  *(DONE -- 2026-09-14, result 93183/14866/40->0/0/40 PASS [neg 111839]: intro_fade=0 on start_state==1 [7316] + megaman_col 2 [3330] )*

**Result.** result 93183/14866/40->0/0/40 PASS (neg 111839): intro_fade=0 on start_state==1 (7316) + megaman_col 2 (3330) + enemies 0 (3986); canaries all 0, windowclose/chip-use unchanged, cursor +18 layout-churn (verifier: branch unreachable for cursor row, 16+2 decomposition); verifier CONFIRMED fade arithmetic + peek citations + rules clean (live peeks unchecked, corroborated by 0); landed 92a01a9 HEAD re-check MATCH; worker muse-spark, verifier GLM
**Files.** src/battle.rs (the intro_fade line at ~1632 only), tools/harness.py (RESULT_ROW / RESULTMATCH_ROW descriptor fields and the result row's note)

**Why.** F34 measured the result row's remaining 93183/14866/40 to 0 with three changes applied together
(each alone measured too): (1) `src/battle.rs:1632`: `intro_fade = 0` when the fixture's `start_state == 1`
-- canon's RESULT_ARRIVAL state is 8048 battle frames in and has no fade left, while FLAG_SKIP_INTRO's
INTRO_SKIP_FADE darkens our field and objects for the first ten compared frames: 93183 -> 7316/1878/40 with
every BG layer 0 on all 40 frames (cite the intro fade's canon counterpart and why it is over by then);
(2) RESULT_ROW `megaman_col` 3 -> 2: canon's BattleObject 0x0203a9b0+0x12 PanelX reads 2 on every frame
(BattleObject.inc:63; megaman_row 2 is already right): 7316 -> 3330; (3) RESULT_ROW `enemies` 1 -> 0: canon's
enemy slot 0x0203aa88 sits in CUR_STATE_DESTROY 0x08 at the row's canon_ref (BattleObject.inc:38), so we draw
385-511 px canon does not: 7316 -> 3986. All three: `result isolated PASS 0/0/40, negative 111839 not blind`.
The descriptor fields without the fade are worth only 56 px, so land the three together.
**Do.** Start in `bash tools/worktree.sh f34b-result-zero`; baseline result 93183/14866/40; apply the three
with the citations above (provenance peeked for the two descriptor fields, the fade rule as a comment on
the canon state); measure each alone and all together. **Acceptance.** result 0/0/40 (negative not blind);
field, wave, window, opening, chip-cannon, popup, mettaur, buster 0; cursor/windowclose and the integrated
rows unchanged or better; nothing worse. **Coordinator:** verify_rows on result and the canaries; the
verifier only on the fade citation.


### F32. End sequence: `over` fires at the last enemy's defeat, canon enters the RESULT countdown 47 frames later, after the dissolve  *(DONE -- 2026-09-13, over 35 updates after killing blow [was 92]: death->0x0C 35/35 both canon routes [47 = 12 pre-resume + 35])*

**Result.** over 35 updates after killing blow (was 92): death->0x0C 35/35 both canon routes (47 = 12 pre-resume + 35); result 93183 held (F34 value), guards/banner/popup/field/mettaur 0, cursor 154361; verifier CONFIRMED 35-count + all routine PCs + residuals-out-of-row (rust OAM 155/120 unchecked); landed d6102bb HEAD re-check MATCH; worker muse-spark 78 turns $0.064, verifier GLM
**Files.** src/battle.rs (the end sequence only), src/banner.rs

**Why.** F27b measured on the real ROM (PAUSED, enemy HP forced 0, Start@10): the banner sequencer enters
the RESULT countdown 0x0C at frame 47 and the HUD teardown fires at 48, while the enemy's death is at
frame 0 and its dissolve fills the 47 frames between; ours fires `over` (banner + RESULT) at the defeat
itself. No row measures that offset today because the result row is aligned by event on the results
screen, but it is a battle-flow defect that every later row through the end of a battle will hit.
**Do.** Watch canon's sequencer (dword_203CA70) and the enemy's state from the killing hit to 0x0C on the
result fixture's route, cite the routine that counts the dissolve and the one that enters 0x0C, and make
ours enter the end sequence on the same event with the same count. **Acceptance.** the frame of 0x0C
after the killing hit equal on both sides (watch on both), result 102547 or better on its event-locked
alignment, banner/popup/wave/window/opening/chip-cannon unchanged or 0.


### F34. `result` 102547: decompose by layer and frame; the window's inside (904), the slide lag, the backdrop tail  *(PARTIAL -- 2026-09-13, result 102547/14866/40 -> 93183/14866/40 [neg 192263 not blind], landed: canon's PRESS-A-BUTTON prompt run in )*

**Result.** result 102547/14866/40 -> 93183/14866/40 (neg 192263 not blind), landed: canon's PRESS-A-BUTTON prompt run in src/results.rs (sub_802C810 setup + the bit-3 blink of sub_802BF0C on eToolkit CurFramePtr 0x0200a210 = 0x22ef at canon 0, +1/frame; toggles at k=21/29/37 on both sides, first write at k=14 on both) took window+HUD 4819 -> 0, and RESULT_ROW's backdrop seed derived from canon's RAM at canon 21 of result_arrival.state (counters 0xffff0480/0xffff8240 = battle frame 8048; eGFXAnimStates[0] entry 27/Timer 7) took the backdrop 18982 -> 0. Layer table at origin 13 / offset 21: backdrop 0/40, window 0/40 (our BG2 HP box composited under BG3 vs canon BG3 = 0; the 704 px per layer is layer assignment only), field 18552/frame on k=0..9 then 0, OBJ 423 attributed; composite 93183 = 92760 BG (field, k=0..9) + 423 OBJ. New finding: the pipeline lags are marker-anchored, scroll tick = R - origin + 1 and art tick = R - origin + 3 (F26b/F33b's R-7/R-5 are the origin-8 case; this origin-13 row separates them: 692/858 + entry 24/Timer 6 gives backdrop 0/40 with a unique sharp minimum, the absolute reading 387793). Not exercised here: the reward reveal chain (sub_802C044/sub_802C0A4, no confirm press in the window). The whole remainder is measured to 0: intro_fade = 0 when the fixture's start_state == 1 (canon's arrival has no fade; FLAG_SKIP_INTRO's INTRO_SKIP_FADE darkens our first ten frames) 93183 -> 7316 with every BG layer 0/40; RESULT_ROW megaman_col 3 -> 2 (canon PanelX 2 at 0x0203a9c2) 7316 -> 3330; RESULT_ROW enemies 1 -> 0 (canon's enemy slot in CUR_STATE_DESTROY 0x08 at 0x0203aa90) 7316 -> 3986; all three: result PASS 0/0/40, negative 111839 not blind; descriptor fields without the fade only 56 px (F34b, pi). Full table 52 PASS, rollup PASS, nothing worse (cursor 154383 vs 154386 jitter). Claude Opus agents, 124 + ~40 tool calls, 28 + 30 min, 228k + ~150k tokens (the first agent was cut off by the session limit and had committed its work).
**Files.** src/results.rs, tools/harness.py (the result row's note and its descriptor's backdrop seed fields only)

**Why.** result reads 102547/14866/40 (negative 195579 not blind) after F21 (reward reveal chain) and F21d
(block-copied tilemap, one blit per frame, F21b's slide). F21 left "inside the window 904 on the plateau,
outside ~2900/frame backdrop tail + slide lag"; nobody has decomposed the 102547 since F21d. Per-layer and
per-frame first: the window's BG, the backdrop BG1 (its scroll phase is a per-row seed derived from canon's
counters at the row's canon_ref -- F26b is deriving that mechanism for the CUSTMATCH rows; if its
derivation lands first, apply it here, otherwise derive this row's seed the same way and cite it), OBJ.
Then the window itself: canon's driver chain sub_802BD60 -> sub_802BE36 -> sub_802C044/sub_802C0A4 (F21),
its slide timing and tile content frame by frame against ours.
**Acceptance.** a layer x frame table with canon citations; result as low as the mechanisms you fix take it
(each fix measured alone); field, wave, window, opening, chip-cannon, popup 0 or unchanged; nothing worse.


### F33b. The ZERO_ENEMY rows' backdrop seed and the two HUD gates: field/warp/buster/chip-use integrated toward 0  *(PARTIAL -- 2026-09-13, field integrated 304103/10032/40 -> 158938/5609/40 [neg 261037], warp integrated 362788 -> 40628/11744/30 [neg)*

**Result.** field integrated 304103/10032/40 -> 158938/5609/40 (neg 261037), warp integrated 362788 -> 40628/11744/30 (neg 129960, now inside its cap), buster integrated 247448 -> 54672/12977/28 (neg 130248), chip-use integrated 643191 -> 567780/25328/32 (neg 624928); isolated variants 0/0/0/9514 unchanged; windowclose 27819, popup 0, cursor 154367 -> 154386 (+19 build jitter, gates are no-ops there), seven failing chip rows byte-identical (control run with main's battle.rs); full table 52 PASS / 12 FAILED, nothing worse. (1) Backdrop seeds derived per row by F26b's derivation from canon's RAM at each canon_ref (counters -8f/-4f: field/warp canon 130 = battle frame 8022, buster 132, chip-use 150; eGFXAnimStates entry/timer; lags R-7/R-5 untouched): field 10/7 466/745, warp 17/6 580/802, buster 10/0 480/752, chip-use 13/3 522/773 -- the same code reproduces the landed CURSOR_ROW and WINDOWCLOSE_ROW seeds untuned; --only-bg 0/1/2 read 0 on every frame of warp/buster/chip-use and on field until its own end-sequence stall (k=1/k=4); each row's band now bottoms at its own event alignment (51/103/100/108; chip-use had bottomed at 105 before the seed; field's 108 measured, its note corrected). (2) HUD gates: canon's mask 0x0084/0x00c5 on every compared frame; gauge (element 4) and hand icon (element 1) now require hud_live, ZERO_ENEMY hand=[1] so the name (element 6) draws: 1596 + 422 px/frame on BG3. (3) chip-use's name is already right; buster's name is the opposite of the guess: canon stops drawing it at canon 133 inside sub_800ED90's player branch (asm00_2.s:15-46) while ChipsHeld stays 1, left unfixed because warp keeps its name (attack-specific rule, untraced). Remaining on all four: canon's deleted-enemy battle resolves at canon 154 and its RESULT window slides in while only field carries FLAG_RESOLVE_OVER (F32); buster's held name 8862; field's 3-frame stall and layer drop from capture 121. Landed 381cb8a. Claude Opus agent, 47 tool calls, 16 min, 356k tokens.
**Files.** tools/harness.py (the ZERO_ENEMY descriptor and the four integrated rows' notes), src/battle.rs (the two HUD gates only: the chip-name filter at ~3743 and gauge_up), src/hud.rs, src/hudtiles.rs

**Why.** F33's per-element decomposition: 86% of field integrated's 304103 (and of warp/buster/chip-use
integrated) is the BG1 backdrop phase, because ZERO_ENEMY seeds no backdrop phase while its canon side is
thousands of frames into pausedwithcannon; canon's counters at canon 130 read x -64176 / y -32088
(-8f/-4f from battle init, F26b) and at 150 x -64336 / y -32168, so by backdrop.rs's arithmetic x_q=684,
y_q=854 at canon 130 with the art phase to walk back the same way; the seed is per row (each row's
canon_ref differs) and our pipeline lags are the ones F26b measured (scroll R-7, art R-5). The rest of the
HUD: element 6 (chip name + damage, sub_801C6EE asm00_2.s:26619) is drawn by canon on every compared frame
and not by ours because we tie the name to the hand together with the icon (element 1, torn down at 48):
measured, ZERO_ENEMY hand=[1] plus `.filter(|_| self.chip_use_in != 1 && self.hud_live)` at battle.rs:3743
gives field 304103 -> 287204, warp 362788 -> 350128, buster 642770 -> 629266 (422 px/frame), and neither
half alone (the descriptor half alone regresses warp/buster isolated); gauge_up should also require
hud_live (element 4). chip-use additionally keeps the name after the chip is used (canon reads
dword_20352C8), ~444 px/frame.
**Do.** (1) Derive and set each of the four rows' backdrop seed (art_entry/art_timer/scroll_xq/scroll_yq)
from canon's counters and GFX state at that row's canon_ref, citing the derivation; measure BG1 alone
per row. (2) The two gates with citations, with the hand descriptor, measured together; check windowclose
and cursor (both enemies=0 rows) do not regress. (3) chip-use's name after use. **Acceptance.** BG1 0 on
all frames of the four rows; each row's remaining residue decomposed by element and layer; the isolated
variants, cursor, windowclose, popup, buster, tiles, gauge, wave, window, opening, chip-cannon unchanged
or better; an allowlist entry removed only for a row that reads 0; nothing worse.


### F26b. `cursor` layer table: repair the OBJ arithmetic and check the four UNCHECKED attributions  *(PARTIAL -- 2026-09-13, cursor 620802/6884/170 -> 272341/1603/170 [neg 458619 not blind] at the event offset 237 [the unseeded band's )*

**Result.** cursor 620802/6884/170 -> 272341/1603/170 (neg 458619 not blind) at the event offset 237 (the unseeded band's minimum had sat at 226, 11 frames off the event, with 237 reading 779920); windowclose 407778 -> 34707/2652/40 (neg 221819 not blind) at 253; BG1 alone 0 on all 40 windowclose frames and 2 px on 1 of 170 cursor frames. Derivation: BGScrollCB_BG1Diagonal3to2Scroll (asm00_0.s:3287-3303) writes (counter-8)>>4 and (counter-4)>>4 to BG1HOFS/VOFS, counters zeroed at battle init (sub_8080D90/DA0 asm00_1.s:8434-8435) so they hold -8f/-4f at battle frame f (watched: CHIPSELECT sits at battle frame 3156); canon's phase in our units x_q=2f mod 1024, y_q=f mod 1024; art from eGFXAnimStates[0] (0x020094c0) entry=(CommandPos-LoopAddress)/8 and Timer, 192/cycle; our pipeline lags measured once on windowclose (a capture frame R shows the scroll of tick R-7 and the art of tick R-5) and predicted cursor with no tuning (2214975 -> 2). Seeds: CURSOR_ROW art 11/3 scroll 746/885, WINDOWCLOSE_ROW 17/1 846/935; CUSTMATCH_ROW untouched (window/card 0). The odd-frame lsr-vs-floor note retired with a proof (lsr #4 of -8f = -ceil(f/2) = -((x_q+3)/4)), comment-only, .text/.rodata byte-identical to main. Layer table repaired (layer-local vs attributed): cursor 272341 = OBJ 272340 + BG1 1; windowclose 34707 = OBJ only. F26's UNCHECKED: (a) '2-frame art lead' refuted (an unseeded clock), (b) no Kind field exists (enemy NameID 1 constant), (c) the y18..33 HUD block is a pure 120 px x displacement: ours x2..45, canon x122..165, identical content, 117980 px-frames of cursor (the emotion window's custom-screen position; F33), (d) MegaMan panel (2,3) confirmed, landed by F29. Remaining: cursor's 1 px at k=97 is sub-frame (canon's tile copy is queued by QueueEightWordAlignedGFXTransfer/sub_8001C94 asm00_0.s:3752 and drained part-way down the frame, ours lands before scanline 0) and the 2-frame relative skew of our scroll and art clocks is absorbed per row by seeds rather than fixed in src (F35); the rest is OBJ (cursor: HUD block 117980 + y107..159 154360; windowclose 34707). Claude Opus agent, 92 tool calls, 32 min, 207k tokens. Post-merge on main with F28b's gauge_pause change (landed in between): cursor reads 272378/1639/170 (+37 px, sprite layer), windowclose 34707 unchanged; the interaction belongs to the cursor sprite-layer follow-up.
**Files.** src/backdrop.rs, src/actor.rs, tools/diffmask.py, tools/probe.py

**Assigned to a Claude agent (2026-09-13 21:00) together with the backdrop-phase findings of F29.** F29 measured on windowclose (fixture CUSTMATCH_ROW, shared with cursor): the backdrop layer BG1 is a constant (20,10) px translation on all 40 frames (scroll rates SCROLL_X_Q=2/SCROLL_Y_Q=1 per frame are right; 40 frames of the phase gap is exactly (20,10)) because the fixture seeds no backdrop phase (art_entry etc. 0xFFFF, a fresh Backdrop::new at x_q=y_q=0) while /tmp/chipselect.state is thousands of frames into a battle. Canon at windowclose's reference frame 81: eBGScrollCBCounters (ewram.s:619, 0x02009690/0x02009694) = 0xffff9ad8 / 0xffffcd6c; eGFXAnimStates[0] (ewram.s:596, 0x020094c0) LoopAddress 0x0807fba4, CommandPos 0x0807fc6c = entry 25, first halfwords 0x0001 0x0002. An empirical seed scroll_xq=80/scroll_yq=40 took BG1 877602 -> 228662 and windowclose 648948 -> 392992, but the same seed takes cursor 620802 -> 1222398: cursor pairs rust 237 with canon 15 where windowclose pairs 253 with 81, so the seed must be derived per row from canon's counters at that row's own canon_ref, never shared. After the seed, BG1's residual alternates +1 px on odd multiples of 3 (k=3,9,15,...) and 0 on even multiples of 6: the lsr-of-a-falling-counter vs floor-divide difference src/backdrop.rs:278-283 already documents as untested; this row measures odd frames. Acceptance for this pass: BG1 0 on all 40 windowclose frames and on cursor's 170 frames, both with seeds derived from canon's counters (cite the derivation), cursor and windowclose totals reported per layer, wave/window/opening/chip-cannon/field/result 0 or unchanged.

**Why.** F26's verified Result (PARTIAL): BG0/BG2/BG3 clean and BG1 scroll rates match (both verifier-CONFIRMED), but the verifier FLAGGED the OBJ-layer arithmetic (OBJ-total 689572 exceeds the full-frame 620802, so as stated it must count occluded/overdrawn pixels -- the table must say which) and marked four attributions UNCHECKED: (a) BG1 art phase ours-leads-by-2 (canon entry 17->18 at k=4 vs ours at k=2; citations LoadGFXAnim/ProcessGFXAnims/sub_8001C94/schedule off_807FB98 CONFIRMED, entry-size-8 and the lead itself not measured); (b) chipselect's enemy is a Mettaur variant other than kind 0 (04/0b stability not re-measured; no oBattleObject_Kind field found -- variant may ride NameID); (c) enemy-HP portrait content byte-identical 871px with box-x canon 122-165 vs ours 2-45; (d) MegaMan at canon panel (2,3) vs fixture (3,2). No F-next may build on the table until the arithmetic closes.
**Do, in order.**
1. Start in `bash tools/worktree.sh f26b-layers2`. Baseline cursor at offset 237 (620802/6884/170/728447, negative not blind).
2. Redefine the OBJ-layer measurement so the arithmetic closes (visible-composite diff pixels vs layer-local diffs, stated per layer), re-measure the per-layer totals at offset 237, and check (a)-(d) with watches on this row's own captures (GFXAnim state at 0x020094C0 both sides; enemy CurState/CurAction + NameID/variant field; portrait bbox both sides; MegaMan panel both sides).
3. Fix in src/ only what has a canon citation and a measured before/after on cursor; otherwise stop with the repaired table. Re-run cursor, wave, window, opening, chip-cannon, result, field -- nothing worse.
**Rules.** Same files as F26; no alignment/allowlist/seed/scroll change except by measured event; captures one at a time.
**Measure and report.** Repaired layer table (definition stated, arithmetic closed), (a)-(d) confirmed or refuted each with the watch traces, rows before/after, full-table deltas. **Acceptance:** the table adds up and every attribution the next cursor ticket needs is measured, not inferred.
**Coordinator:** `verify_rows` on every row the report names; the verifier on the repaired table and any canon citation.


### F33c. The integrated rows after F32: let the zero-enemy fixtures resolve where canon's battle resolves  *(NEGATIVE -- 2026-09-14, resolve-flag hypothesis refuted with structure [warp 40628->83175 tried+reverted)*

**Result.** resolve-flag hypothesis refuted with structure (warp 40628->83175 tried+reverted; paused includes over freezes inputs; banner tail parks k=0..9; canon acts post-0x0C); 0x0C@47 uniform x4 rows; field stall decomposed (lag-14->lag-11, results_delay coincidence, mechanism untraced); notes-only commit landed 2f49e18; no verifier (nothing landed behavioral; findings recorded for next integrated ticket); worker muse-spark 63 turns $0.049
**Files.** tools/harness.py (the ZERO_ENEMY descriptor flags and the integrated rows' Align notes), src/battle.rs (the end-sequence hunk only, if F32's count needs a fixture-side entry point)

**Why.** F33b left warp integrated 40628, buster 54672, chip-use 567780 and field 158938 with every BG layer
0 until canon's RESULT window slides in (warp from k=24, buster k=22, chip-use k=4): canon's deleted-enemy
battle resolves at canon 154 while only field's fixture carries FLAG_RESOLVE_OVER. F32 has now landed
canon's count (over 35 updates after the killing blow; death -> 0x0C at 47 = 12 pre-resume + 35). Re-measure
the four rows on main first: if the ramp now differs only by when our side resolves, give the zero-enemy
descriptors the resolve flag with the sequencer's event frame peeked from each row's canon capture
(dword_203CA70 -> 0x0C), and lock the ramp by that event, never by score. field's own stall (captures 118-120
byte-identical, then the filler BG dropped from 121) is measured on the same pass.
**Acceptance.** warp, buster, chip-use integrated as low as the ramp takes them (0 if the window's content
matches, F21/F34's chain); field integrated decomposed with its stall attributed; the isolated variants and
every 0 row unchanged; allowlist entries removed only for rows that read 0; nothing worse.


### F35. Backdrop engine timing: tile copies drained mid-frame like canon's queue, and one clock for scroll and art  *(PARTIAL -- 2026-09-14, mechanism mapped+cited, fix reverted honestly [scanline-6 wait: BG1 62->184/0->571 -- copy smear])*

**Result.** mechanism mapped+cited, fix reverted honestly (scanline-6 wait: BG1 62->184/0->571 -- copy smear); verifier CONFIRMED tear ~scanline 0-6 (not 48), CpuFastSet 0x480B/8f live, queue chain (citation fixes: :663 not :653, table-indirect dispatch); unchecked: 1157px magnitude, k-indexing, 37-call span, FastSet src addr; seeds untouched, tree clean; worker muse-spark 80 turns $0.111, verifier GLM
**Files.** src/backdrop.rs, src/main.rs

**Why.** F26b measured two engine-timing facts on the backdrop. (1) Canon queues its backdrop tile copy
(QueueEightWordAlignedGFXTransfer, sub_8001C94, asm00_0.s:3752) and the queue drains part-way down the
frame, so on the frame of an art step canon shows the previous step in rows 0..5 and the new one below;
ours lands before scanline 0. Visible as 2 px on cursor's frame k=97 (the same texel twice, 128 apart).
(2) Our scroll register is written by commit() and the art by replace_tile() inside update(), so a
capture frame R shows the scroll of tick R-7 and the art of tick R-5: a 2-frame relative skew between two
clocks that canon does not have (one counter pair, one queue). The per-row seeds in the harness absorb
it today; the mechanism should not need absorbing.
**Do.** Watch canon's queue drain (the transfer's VRAM write frame and scanline via --watch-write on the
tile region) and ours; make ours copy at the same point of the frame canon's queue does (cite the queue
flush routine and its place in the frame loop), and drive scroll and art from one tick so both lead by the
same amount; then re-derive the CURSOR_ROW/WINDOWCLOSE_ROW seeds by F26b's derivation with the new single
lead and show BG1 0 on all cursor and windowclose frames. **Acceptance.** cursor's BG1-only diff 0 on all 170
frames; windowclose BG1 0 on all 40; wave, window, card, opening, chip-cannon, field, result, tiles, gauge
0 or unchanged; nothing worse. F34 (result, marker origin 13) found the lags are marker-anchored, not absolute: scroll tick = R - origin + 1, art tick = R - origin + 3 (F26b/F33b's R-7/R-5 are the origin-8 case); use that form.


### F35b. Backdrop step copy: one block copy inside ~1 scanline, then place it at the drain scanline  *(BLOCKED -- 2026-09-14, fast copy 11->1 scanline works as mechanism but fixed placement fails both ways [vblank copy leaves 88, scanli)*

**Result.** fast copy 11->1 scanline works as mechanism but fixed placement fails both ways (vblank copy leaves 88, scanline-6 leaves 3007) -- canon usually-vblank + occasional slips, no fixed wait matches both; reverted clean, no commits, seeds untouched; slips-deterministic-in-supercycle hypothesis recorded NEEDS EVIDENCE (no F35c per two-in-a-row: F35 PARTIAL->F35b); span claim first-party only; worker muse-spark 87 turns $0.044
**Result.** fast copy 11->1 scanline works as mechanism but fixed placement fails both ways (vblank: 88 left; scanline-6: 3007 left) -- canon drains usually-vblank + occasional slips, no fixed wait matches both; reverted clean, no commits, seeds untouched; slips-deterministic-in-supercycle hypothesis recorded for later (needs evidence); second consecutive non-DONE on backdrop objective -> no F35c per two-in-a-row; worker muse-spark
**Files.** src/backdrop.rs, vendor/agb

**Why.** F35's verified Result (PARTIAL, no commits): canon drains one BIOS CpuFastSet of 0x480 B into 0x06000040 every 8 frames mid-frame near scanline 0-6 (verifier CONFIRMED live: addr/size/period; queue chain main.s:17 -> ProcessGFXTransferQueue asm00_0.s:830 -> CopyByEightWords/SWI_CpuFastSet asm00_0.s:663; table-indirect dispatch via ProcessGFXAnims); ours does sequential per-slot replace_tile calls inside update() which span several scanlines, so a same-position wait smears partial-new rows (measured 62->184 / 0->571, reverted). Verifier corrections to carry: citation is :663 not :653; dispatch is table-indirect; tear sits scanline 0-6 (not 48); unchecked -- step magnitude, k-indexing, our loop span, FastSet src addr.
**Do, in order.**
1. Start in `bash tools/worktree.sh f35b-fastcopy`. Baseline cursor BG1-only (62 @237) + windowclose BG1 (0 @253) + canaries.
2. Replace the per-slot step copy with one block copy sized to the step (memcpy/DMA or a minimal vendor/agb helper with doc comment -- F21d precedent; keep the manager's bookkeeping consistent) and measure its scanline span (must complete inside ~1 scanline); then place its completion at canon's drain scanline and re-measure BG1 diffs.
3. Re-derive CURSOR_ROW/WINDOWCLOSE_ROW seeds with the single lead (marker-anchored form) and report the derivation values WITHOUT editing harness; re-run canaries + full table.
**Rules.** src/backdrop.rs + vendor/agb only; no harness/fixture/allowlist change; no fitted constant; captures one at a time.
**Measure and report.** Copy span before/after (scanlines), BG1 diffs before/after both rows, seed derivation values, rows before/after, full-table deltas. **Acceptance:** cursor BG1-only 0/170, windowclose BG1-only 0/40, canaries 0-or-unchanged; else measured span numbers and STOP.
**Coordinator:** `verify_rows` on every row the report names; the verifier on the copy-span claim (it must measure sub-frame completion).


### F36. The oracle export block trails or leads the frame it describes by one frame (buster's attack-state entry)  *(DONE -- 2026-09-14, export placement verified frame-accurate [post-commit test strictly worse, reverted])*

**Result.** export placement verified frame-accurate (post-commit test strictly worse, reverted); canon contract state-leads-pixels-by-1; buster 1f-late entry + warp 0x10-mapping are state-side (battle/actor owners); comment-only +9 main.rs; verifier CONFIRMED all 3 + rules clean; landed 464e275; worker muse-spark 61 turns $0.038, verifier GLM
**Files.** src/main.rs, tools/oracle.py

**Why.** F31b's re-cut buster row reads 0 px, but on its lock canon's CurAction becomes 0x11 on k=0 while
our ORCL export's CurAction byte flips to 0x0b on k=1, though both sides draw the windup on k=0..1 and the
pose from k=2. Either our attack state is entered a frame late (and its first frame draws the same pixels as
idle), or the export block is written a frame away from the frame it describes (it is written between
battle.update() and gfx.frame()). Every oracle comparison inherits that ambiguity.
**Do.** Watch the ORCL block against a state whose drawing is unambiguous on the same frame (a warp or a
flinch: the pixel changes on the frame the state changes on canon), on both sides, and say which side of the
pair is off; fix it (the export's placement in the frame loop, or the state entry), cite canon's order of
state update vs draw (the object dispatcher then object_updateSprite), and show the oracle's first
divergence unchanged or improved on mettaur, buster, warp and card. **Acceptance.** the export's fields
describe the frame captured (shown on two rows with a state change), no pixel row changes.
