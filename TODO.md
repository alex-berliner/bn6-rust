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
- **DO THE WORK YOURSELF.** Do not delegate a ticket onward -- not to `ds-worker`,
  `ds-ask` or any other DeepSeek path, and not to a further agent. You are the worker.
  A ticket that turns out to be bigger than it looked comes back as a report saying
  so, not as a subcontract. There is a delegation policy in a global CLAUDE.md that
  says to prefer DeepSeek for volume work; it does NOT apply to this project, where
  the user has asked for Sonnet agents only.

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

CLOSED at 0 -- TRANSFER 7bc. The paragraph that used to stand here said the residue was a
fixture problem with no shared origin and could only ever coincide. That was wrong, and
nobody had read `sub_8028820`. The blink counter is window-relative on both sides (a field
at 0x02036500, asm03_0.s:4801-4804 and 1163-1165); the save state's value is just not zero
(0x647, peeked). Held static and swept, the offset was exactly +1 frame, and the frame was
ours: the slide-in reached `Phase::Open` through a second match arm a frame after the real
ROM advances to state 4 in the call that zeroes the counter (asm03_0.s:1011-1012).


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

WHAT IS LEFT is the wave's FIRST hop, one frame. THE LAYOUT SCARE IS RETIRED (TRANSFER
7bd): the claim that any source edit shifts the Mettaur's timing was tested with a private
target directory and is false. Identical source gives byte-identical ROMs and captures; a
comment, a dead const, a dead function and a dead local inside the strike arm itself all
left the spawn frame at 198. The ROM hash moves only because `assert_eq!` bakes
`panic::Location` line numbers into `.rodata` -- six dead bytes. The likely cause of the
original report was two builds racing the shared target directory. So the first hop can be
chased directly, with no methodology worry attached to it.

### A4. Pin the backdrop's scroll phase  *(done -- see TRANSFER 7av)*
`tiles` compares a fixed frame 392 now, not the best of sixty. The phase counts from battle init
(`eBGScrollCBCounters`, zeroed once by `sub_8080D90`), and the save state is 7891 battle frames in,
so the origin is genuinely unrecoverable from it -- a capture from a battle's real frame 0 would
settle this AND BATTLE START!'s delay (C1) in one go. That save state is now the single most
valuable thing the harness does not have.


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

### B2. Panel damage  *(researched -- ready to implement)*
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

### B3b. The next sound needs a DirectSound sample exporter
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


### D2. Make the harness clean up after itself, everywhere  *(done)*
`regress.py`'s rollup check, `chip_compare.py --clean` (which `scoreboard.py` now always
passes) and `throw_dump.py` all delete their captures. `--clean` is opt-in for
`chip_compare` rather than the default because `--no-build` reuses the previous run's
Rust capture. What is left: the ad-hoc capture directories a person makes by hand, which
is what actually filled the disk.
