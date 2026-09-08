# Work that can be handed to a subagent

Each entry is meant to be pasted into a ticket more or less as it stands. Anything
without a way to *measure* whether it worked is not ready to hand out — write the
measurement first.

## Every ticket runs in its own git worktree

    tools/worktree.sh <name>

prints a directory, a branch, and the `CARGO_TARGET_DIR` to export. The agent works THERE and
commits to ITS OWN BRANCH; the coordinator merges back with `git merge --no-ff`. Nothing else
gets an agent's half-finished edits, and nobody has to remember not to build at the wrong moment.

Why this exists: on 2026-09-07 four separate incidents came from agents and coordinator sharing
one checkout. A build taken while a worker held `src/` compiled its half-finished file and
returned a normal-looking number; the same collision later made a build fail outright; and I told
a worker its correct measurement was contamination on the strength of one of those numbers.

What the script handles that a bare `git worktree add` does not:
- `reference/bn6f` is a submodule and a fresh worktree checks it out EMPTY. It is symlinked to
  the main checkout, because it is only ever READ -- disassembly comments are made by the
  coordinator in the main tree, so an agent must not commit inside it. The script marks the
  path `--skip-worktree` so that a stray `git add -A` cannot stage the symlink over the
  gitlink -- doing that once merged a self-referential symlink into main and deleted the
  disassembly from the working tree. Agents should stage by path regardless.
- Each worktree needs its own `CARGO_TARGET_DIR` or the builds serialise on one lock. A build in
  a fresh worktree takes about 30 seconds and produces a BYTE-IDENTICAL ROM to the main tree's --
  verified, three ways, so a number measured in a worktree is directly comparable to one measured
  anywhere else.
- Capture scratch paths are keyed on the checkout path by `chip_compare.scratch()`, so two agents
  cannot overwrite each other's packed ROM between its build and its capture. That needed no
  argument and no convention; it just works out.

An agent that commits on its own branch is also free to commit MIDWAY, which the old "never
commit" rule forbade -- and that rule existed only because everyone shared one tree.

## Rules for every ticket

- **Give each agent its own `CARGO_TARGET_DIR`** under `/tmp` (`tools/worktree.sh` prints one). `cargo` locks the shared
  target directory and every build overwrites the same `target/.../bn` that
  `tools/gbafix.py` reads, so two agents building at once will silently pack each
  other's ROM. This has already caused two wrong captures.
  This rule was itself a trap until 2026-09-07: `regress.py`'s `build()` hardcoded
  `ROOT/target/...`, so setting `CARGO_TARGET_DIR` made cargo build in one place and the
  ROM get packed from a stale ELF in another -- no error, just numbers for a different
  build (`mettaur` 95436 instead of 345). It now asks `cargo metadata` where the target
  directory actually is, so the rule and the harness finally agree. Any OTHER script that
  packs a ROM should be checked for the same assumption before being trusted under a
  private target dir.
- **Baseline first.** The agent must record the number with its own script *before*
  changing anything, and re-run the identical script afterwards, and report both. A
  change nobody can show improves a number is not a fix — see 7ah in `TRANSFER.md`,
  where a well-cited change backed by a disassembly line and the animation data turned
  out to move nothing and to be worse on a wider window.
- **Say which window was measured.** Two agents measuring the same residue in different
  frame windows reached opposite conclusions once. Windows go in the report.
- Only `src/` changes unless the ticket says otherwise. Never `tools/`, `reference/`,
  `assets/` or `Cargo.toml` without a reason in the report.
- A precise negative result is a good outcome and gets written into `TRANSFER.md`. A
  plausible-sounding change that does not move the number is not.
- **DO THE WORK YOURSELF.** Do not delegate a ticket onward -- not to `ds-worker`,
  `ds-ask` or any other DeepSeek path, and not to a further agent. You are the worker.
  A ticket that turns out to be bigger than it looked comes back as a report saying
  so, not as a subcontract. There is a delegation policy in a global CLAUDE.md that
  says to prefer DeepSeek for volume work; it does NOT apply to this project, where
  the user has asked for Sonnet agents only.

## Rules for whoever is handing the tickets out

Written after breaking all three of these in one evening.

- **Do not build or measure from the tree while a worker holds `src/`.** Not just "do not edit" --
  a build taken mid-edit compiles whatever state the worker's file is in at that instant and gives
  a number that looks completely normal. This produced a `tiles` reading of 3295 and then one of 0
  within the hour, the second being a build with the worker's fix reverted. Reuse an already-built
  ROM from /tmp, or wait.
- **When a worker's number disagrees with yours, rebuild it yourself before contradicting them.**
  On the strength of the above I told a worker its correct measurement was contamination. It had
  done three from-scratch builds and was right. Its EXPLANATION was wrong (it blamed target-path
  length; three target directories, one deliberately long, give a byte-identical ROM) -- but a
  wrong explanation is not a wrong measurement, and the two must be judged separately.
- **`git add -u <path>` limits to that path.** A commit meant to carry the fix, the harness change
  and two write-ups carried only the submodule bump, and the rest sat unstaged behind a clean-
  looking `git status` line. Check `git show --stat` after committing, not just the exit code.

---

## A. Measured residues — small, self-contained, all have a number

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

### B3c. The `audio` check  *(the contradiction is resolved; a magnitude question is left)*
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

WHAT IS LEFT is a magnitude question, not a sign one. Ours is 4603 against 3609, about 27% loud,
where the wiring measured 4605 against 4074, about 13%. The two agree on OUR peak almost exactly
(4603 vs 4605) and differ on the REAL one (3609 vs 4074), so the remaining difference is in how
the real side is captured -- this check passes `--zero 0x6016E00:1280` and the cheats that keep
the enemy alive, and that measurement may not have. Settle that, then drive the number down.

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
