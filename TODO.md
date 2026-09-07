# Work that can be handed to a subagent

Each entry is meant to be pasted into a ticket more or less as it stands. Anything
without a way to *measure* whether it worked is not ready to hand out — write the
measurement first.

## Rules for every ticket

- **Give each agent its own `CARGO_TARGET_DIR`** under `/tmp`. `cargo` locks the shared
  target directory and every build overwrites the same `target/.../bn` that
  `tools/gbafix.py` reads, so two agents building at once will silently pack each
  other's ROM. This has already caused two wrong captures.
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

---

## A. Measured residues — small, self-contained, all have a number

### A1. The Mettaur's attack tail — 4 frames, 698 px each
The last five ticks before the virus returns to idle. The real ROM holds three distinct
poses there (2, 2, 1 ticks); this build holds four (1, 1, 2, 1). Everything earlier in
the tail matches exactly: run-length analysis of both sides gives the identical sequence
2,1,1,3,8,4,9,3,2,2,2,2,4,10,6 up to the divergence.

Already ruled out, do not repeat: `SWING.frames` 0x40 → 0x3f. It is well motivated —
`object_exitAttackState` writes CurAnim=0 on the tick Unk_10 reaches zero
(asm31.s:170737), and animation 1's sub-frames in `assets/mettaur.bin` sum to exactly 63
— and it changes nothing, because animation 1's last sub-frame is pixel-identical to the
idle pose. On a wider window it is actively worse. A tick-by-tick simulation of
`Actor`/`Player` predicts (1,2,2), which matches neither side, so something in the
attacking-to-idle handoff is not modelled by either reading. That is where to look.
See `TRANSFER.md` 7ah.

### A2. The chip window's cursor — FIX THE FIXTURE FIRST
"At a delay of two the bracket is one frame early; at three the card is one frame late."
Two things that move on different frames, which is exactly the shape the chip-in-hand
icon turned out to have — the fix there was to decouple them. `CURSOR_DELAY` is in
`src/custom.rs`. See `TRANSFER.md` 7ag.

BUT THE FIXTURE CANNOT SETTLE IT, and that is the first job. The real side is scripted
(Left held six frames at 20, 50, 80, 110, 140) and the rust side is NOT: `demo-cardname`
walks its cursor on a schedule of its own and `check_card` captures it with no script at
all, so the two walks are aligned by a lag that is a compromise across the whole run.
Measured at the best lag (85), 58 of 60 frames match and the two that differ are 3233 px
each — the whole preview card. Tracking when the card's contents change on each side:

    real  106, 112, 114, 122, 130, 138, 142, 146, 154, 162, 170, 178, 186, 194
    rust  106,      114, 122, 130, 138,      146, 154, 162, 170, 178, 186, 194

Every eight frames is something in the card BLINKING, on both sides and in phase. The
real ROM has two changes that are not on that cadence -- 112 and 142, each two frames
after a Left press -- and this build has none, because its own switches happen to land on
cadence frames. So one move looks two frames late and the other four frames early, which
is not a timing rule, it is an artefact of the two sides being driven by different walks.

Make `demo-cardname` take its directions from the pad instead, drive both sides from the
identical script, and the question becomes answerable. Then decouple the bracket from the
card if the numbers say so.

### A3. The shockwave's panel light — 3 frames of 90  *(assigned)*
Single dwell boundaries a frame out. Also open: is "a panel somebody is standing on is
not lit" a real rule, or one capture's coincidence? It is currently modelled as a rule on
the strength of a single observation. See `TRANSFER.md` 7ai.

### A4. Pin the backdrop's scroll phase
`regress.py`'s `tiles` check does not compare a fixed frame — it searches rust frames
340..400 for the one that best matches real frame 43, because the backdrop's scroll phase
is not pinned. That hides a whole class of drift. Work out the phase relationship (the
backdrop scrolls; the question is what it is counting from) and make the check compare a
single frame. Recorded as "unresolvable from one save state", which may just mean a
second save state is needed.

---

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

### B2. Panel damage
`src/field.rs` carries the art for hole, broken, normal, cracked and poison panels and
nothing drives cracked or broken. `object_crackPanel` writes 3 and a broken panel is 1
(object.s:2301, 2198). Find what cracks a panel in the real ROM and drive it. Verify with
a capture of something heavy landing.

### B3. Sound — research ticket, not an implementation one
Nothing in this build makes a sound. Before anyone writes code, find out what it would
take: where the sequences and samples live in the ROM, what the driver is, whether agb
can be given a channel layout that matches, and what the smallest useful first step is
(one sound effect on the buster, most likely). Deliver a plan with citations and a size
estimate, not code.

---

## C. Research tickets — read-only, no build, good to run several at once

### C1. How many frames into a battle does BATTLE START! go up?
Currently placed, not measured: this build raises it the moment the last enemy has
finished materialising. `sub_8008064` (asm00_1.s:10386) is state 1 of the dispatcher
`off_8008038`, driven by `dword_203CA70` through `sub_800801C`. Trace the battle-scene
boot to the first tick of that dispatcher and count. Alternatively find a way to make a
save state at a battle's start, which is the thing the harness has never had.

### C2. The last 8 frames before the RESULT window
The handler that raises the banner arms a countdown of 0x66 = 102 frames
(asm00_1.s:10577-10592) and leaving the state needs both that and the banner reporting
idle. 102 frames from the banner's frame 49 is 151; the window is measured starting at
159. States 6-9 of `off_8008038` (asm00_1.s:10370) were not traced. This build uses the
measured 110; finding the real source would replace a measurement with a derivation.

### C3. The emotion window
`src/emotion.rs` draws it and it never changes state. The real ROM has angry, and full
synchro, and more. Find what drives the state and when, with citations, and whether any
of it is reachable in a one-Mettaur battle.

### C4. Does the chip-name popup's gate match ours?
This build shows the popup for `attack_family == 0x15`, which is right for all 43 chips
in the scoreboard. The real gate is a `ChipData+9` flag bit plus a chip-category check
(`sub_800B892`), read in `object_drawChipName` (object.s:183-239). Work out the exact
predicate and say whether any chip in the game disagrees with the family rule. Cheap, and
it turns a proxy into the real thing.

---

## D. Harness

### D1. Track the Mettaur cycle in `regress.py`
A1's residue lives only in `TRANSFER.md`. Give it a check, with the alignment done the
way 7ah describes (list the frames on which the virus's bounding box changes on each side
and find the lag that lines the two lists up), so a regression in it is caught rather
than remembered.

### D2. Make the harness clean up after itself, everywhere  *(done)*
`regress.py`'s rollup check, `chip_compare.py --clean` (which `scoreboard.py` now always
passes) and `throw_dump.py` all delete their captures. `--clean` is opt-in for
`chip_compare` rather than the default because `--no-build` reuses the previous run's
Rust capture. What is left: the ad-hoc capture directories a person makes by hand, which
is what actually filled the disk.
