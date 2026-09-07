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

### A1. The shockwave's DEPARTURE — 4 frames, 115 px each  (was "the Mettaur's tail")
RENAMED, because the diagnosis was wrong. Splitting the `mettaur` check's window by region:
the virus's own body is 0 px over all 70 frames -- its animation is exact -- and the entire
460 px sits to its LEFT, on frames 198-201 of the standard alignment.

What it is: the real ROM leaves a thinning spray of blue fragments arcing above the panel
the shockwave has just hopped off, for about six frames. This build shows it for two and
then nothing. That fits `TRANSFER.md` 7ai's finding that
`object_highlightCurrentCollisionPanels` keeps being called from `sub_80C6C14` until the
SEGMENT'S OWN DEPARTURE ANIMATION finishes (`sprite_getFrameParameters` bit 0x80,
`sub_80C6CBA`, asm31.s:31552-31567) -- so a hop is not one sprite moving: the old segment
stays and plays out while the new one appears, and this build moves a single sprite and
draws nothing behind it.

The job: find the departure animation in `t3_0x16_80C6B40` (asm31.s:31354) and its sprite,
and make `Shot::shockwave` leave one behind at each hop. `src/shot.rs` already tracks
`left_panel`/`left_ticks` for the panel light, which is the same event.

Already ruled out, do not repeat: `SWING.frames` 0x40 -> 0x3f. Well motivated --
`object_exitAttackState` writes CurAnim=0 on the tick Unk_10 reaches zero (asm31.s:170737),
and animation 1's sub-frames in `assets/mettaur.bin` sum to exactly 63 -- and it changes
nothing, because animation 1's last sub-frame is pixel-identical to the idle pose. On a
wider window it is worse. The pickaxe was never involved.

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

### A3. The shockwave's panel light — 89 of 90, one frame left
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

WHAT IS LEFT is the wave's FIRST hop, one frame, and one claim to check before trusting
it. The agent reported that ANY source edit -- including in code that never runs before
the wave spawns -- shifts the Mettaur's whole attack timing by whole frames uniformly,
identical source always reproducing identical frames, which it read as binary-layout
sensitivity in boot or vblank sync rather than RNG. That would be a serious problem for
every RNG-driven comparison, so it deserves independent confirmation: it sits awkwardly
beside the fact that `field`, `warp`, `buster` and `chip-use` all compare at FIXED frame
numbers and have stayed at zero across dozens of builds today. Confirm or refute it
first; if it is real it is a bigger ticket than this one.

### A4. Pin the backdrop's scroll phase  *(done -- see TRANSFER 7av)*
`tiles` compares a fixed frame 392 now, not the best of sixty. The phase counts from battle init
(`eBGScrollCBCounters`, zeroed once by `sub_8080D90`), and the save state is 7891 battle frames in,
so the origin is genuinely unrecoverable from it -- a capture from a battle's real frame 0 would
settle this AND BATTLE START!'s delay (C1) in one go. That save state is now the single most
valuable thing the harness does not have.

### A4-old. Pin the backdrop's scroll phase
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

### B3a. Sound: the harness can hear now  *(the research is done)*
`tools/mgba_capture.c` has `--dump-audio` and `--audio-channel`; see TRANSFER 7au for the two
gotchas (the advertised 65536 Hz is really 96000, and `struct mCore` has a `USE_DEBUGGERS` ABI
trap). The engine is stock Nintendo M4A, agb's mixer sets up the same DMA/FIFO/timer registers,
and nothing in this project competes for them.

The smallest first step is NOT "export a sample": the buster's fire sound is a PSG square/sweep
blip on channel 0, confirmed empirically. agb has no PSG API at all, so a first sound means either
a small hand-written PSG driver (register pokes on 0x4000060-0x4000075, in the style
`vendor/agb/agb/src/sound/mixer/hw.rs` already uses for DirectSound) or picking a confirmed
DirectSound effect instead -- `SOUND_HIT_6B`'s sample is already decoded end to end: WaveData at
`byte_81597A0`, 1881 bytes, 10512 Hz, no loop.

### B3-old. Sound — research ticket, not an implementation one
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

### C3. The emotion window  *(researched; see TRANSFER 7at)*
Answered: only Calm and Angry are reachable without a Cross or a Navi Customizer bug, and Angry
needs ~120 continuous frames of hitstun or a single 300+ damage hit, which a Mettaur's 10-damage
shockwave will not produce. So this build's single face is very probably correct for the battle it
fields, and implementing Angry is not worth it until there is an enemy that can trigger it. What
IS worth doing cheaply: `tools/emotion_export.py` takes only state 0's tiles and state 0's palette,
and the other 22 states sit right after at a fixed stride -- exporting them is mechanical.

### C3-old. The emotion window
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
