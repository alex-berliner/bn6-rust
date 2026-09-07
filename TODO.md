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

### A1. The shockwave's departure — 3 frames left of 4  *(mostly done -- TRANSFER 7ah)*
460 px to 345. The mechanism is modelled: a hop spawns a NEW segment and the old one stops
where it is and plays its own animation out until its authored last frame comes round.

What is left is very probably a hop LATE in the attack, where the real ROM is on a different
row of `byte_80C6B00` (asm31.s:31361-31366) with a shorter dwell and a different animation,
while `Shot::shockwave` uses row 0's dwell of 0x16 for every hop -- its own doc comment
already calls that "its first version". Modelling the per-hop table is the job. A negative
result on the way there: allowing SEVERAL departures to overlap measures 8725 px over 20
frames, far worse, because the real ROM's late hops are too short-lived to leave that many
fragments. One slot, newest wins.


### A2. The chip window's cursor  *(done -- TRANSFER 7ag)*
170 frames of a five-step walk, and everything the SCRIPT drives is exact. It was two
one-frame bugs and neither was `CURSOR_DELAY`: the card's palette landed a frame before
its tiles, and the bracket's blink flipped a frame early because `self.frames` is bumped
before anything is drawn. The fixture had to be fixed first -- `demo-cardname` places its
cursor statically and never walks, so a scripted real walk was being compared against a
still picture. `demo-custmatch` starts on OK as the save state does, so both sides run the
same script.

STILL OPEN, and it is a fixture problem not a build one: the check's `want` is 3152, which
is entirely the bracket's blink one frame out. That blink counts from the window's own
opening and the two sides have no shared origin for it. It read 0 for a while and then did
not, after a change that cannot affect this fixture's logic. Anchoring it needs something
both sides share -- most likely a battle-relative counter rather than a window-relative
one. Check what `sub_8028820` (asm03_0.s:4807) actually reads its frame counter FROM.


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


### A5. A battle-opening fixture with three viruses
`/tmp/battlestart.state` is a battle's first frame, and the chip window opens at 173 there
against 134 here -- but the captured battle materialises THREE Mettaurs one at a time and
this build fields one, so the two are not comparable. A demo feature that fields three
Mettaurs on the capture's own panels would make the whole opening comparable: the screen
fade's real length (this build stands in "two frames a step", and only the 0x10 divisor is
confirmed), the materialise sequence, and the window's opening frame. It would also give
the `cursor` check's blink a battle-relative origin to be anchored to (A2).

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

### B2. Panel damage  *(researched -- ready to implement)*
`src/field.rs` carries the art for all five panel states and nothing drives cracked or
broken. The research says what is reachable and what is not, and the answer is narrower
and more useful than expected.

REACHABLE, and the one to build: **MegaMan's CHARGE SHOT sets the panel it hits straight to
BROKEN.** The buster and charge shot both spawn the shared type-0 straight-shot object
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


## C. Research tickets — read-only, no build, good to run several at once

### C1. How many frames into a battle does BATTLE START! go up?  *(answered -- TRANSFER 7aw)*
`/tmp/battlestart.state` exists now. The answer: it does not follow the intro at all, it follows
the FIRST CHIP WINDOW -- thirty frames after that window closes. The build was corrected and lands
within a frame of the real ROM. The same state also showed that a battle OPENS with the chip
window, which this build was getting wrong by 1260 frames.

Still open from the same state: our window opens at 134 against the real 173, because the captured
battle fields three Mettaurs and this one fields one. A fixture with a matching line-up would
settle the intro's length and the screen fade's real frame count in one go.


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


### C4. Does the chip-name popup's gate match ours?
This build shows the popup for `attack_family == 0x15`, which is right for all 43 chips
in the scoreboard. The real gate is a `ChipData+9` flag bit plus a chip-category check
(`sub_800B892`), read in `object_drawChipName` (object.s:183-239). Work out the exact
predicate and say whether any chip in the game disagrees with the family rule. Cheap, and
it turns a proxy into the real thing.

---

## D. Harness

### D1. Track the residues in `regress.py`  *(done)*
`mettaur` (345) and `wave` (960) both have checks, alignment done the 7ah way, wants
measured rather than copied. A `cursor` check was added too. Fifteen checks now.


### D2. Make the harness clean up after itself, everywhere  *(done)*
`regress.py`'s rollup check, `chip_compare.py --clean` (which `scoreboard.py` now always
passes) and `throw_dump.py` all delete their captures. `--clean` is opt-in for
`chip_compare` rather than the default because `--no-build` reuses the previous run's
Rust capture. What is left: the ad-hoc capture directories a person makes by hand, which
is what actually filled the disk.
