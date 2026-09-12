#!/usr/bin/env python3
"""The save-state manifest (AUDIT.md pair 5): every /tmp state this project
loads, written down as (base ROM, base state, script, cheats, frame count)
instead of kept as an opaque file nobody can explain.

usage:
    python3 tools/states.py list
    python3 tools/states.py build <name>
    python3 tools/states.py build all

Before this file, four states existed in /tmp with no record of how they
were made: PAUSED, CHIPSELECT, NOENEMY and BATTLESTART (the ones
tools/regress.py and tools/chip_compare.py load). "Regenerate what can be
regenerated" first needs to know which ones actually CAN be -- and that
turns out to be a question with a physical answer, not a guess:

    mGBA-qt's own interactive "save state" feature writes a file that starts
    with a "RASTATE" banner followed by the raw serialized core state (see
    the --loadstate comment in tools/mgba_capture.c, which exists ONLY to
    convert that banner away -- nothing this project writes ever produces
    one). `pausedwithcannon.state` and `chipselect.state` both start with
    that banner. They were made by hand, live, in the emulator; there is no
    script that reproduces "the state a person reached by playing", only the
    playing itself, and that is gone. They are ROOTS.

    `noenemy2.state` and `battlestart.state` both start with a PNG signature
    (`\\x89PNG`, an IHDR for a 240x160 image) -- which is exactly what
    mCoreSaveStateNamed(..., SAVESTATE_ALL) writes, SAVESTATE_ALL including
    SAVESTATE_SCREENSHOT, and exactly what tools/mgba_capture.c's own
    `--savestate` flag asks for. Both were built by THIS project's harness,
    not hand-played -- which makes them candidates to write down and
    regenerate, and the two came out differently once tried:

      - NOENEMY has a working base to start from (PAUSED) and a documented
        trigger (delete the enemy's HP, TRANSFER.md section 3 / 7bf). The
        recipe below reproduces the RESULT window's arrival at the same
        place, frame for frame, but NOT the reward panel's content, and NOT
        how soon the "press to continue" prompt starts blinking afterward
        -- both depend on exactly which reward the kill rolls, which this
        recipe (an instant HP-zero from a memory cheat) does not drive the
        same way real play did. Measured, not hidden: see BUILT_NOENEMY's
        docstring below for the numbers. Left as `root=True` regardless of
        being harness-made, because `build` overwriting the live fixture
        with a state carrying a DIFFERENT reward is exactly the silent drift
        this manifest exists to prevent -- flip it once the reward-content
        divergence is understood well enough to either fix the recipe or
        accept the new content on purpose.
      - BATTLESTART's own documented recipe (TRANSFER.md 7aw) starts from an
        overworld save, walking toward a random encounter with the roll
        forced every frame. There is no overworld save file in /tmp, none
        was ever recorded, and reaching one from a cold boot means scripting
        a title screen, a name entry and an intro this project has never
        driven. Nothing here is runnable, so despite being harness-made in
        the same sense as NOENEMY, it stays a ROOT until that input exists.

    PAUSED and CHIPSELECT are true roots: `build` refuses them outright.
    NOENEMY and BATTLESTART are marked `root=True` too, for the reasons
    above, but each carries a `recipe` a future session can flip on once its
    own caveat is resolved -- the manifest writes the coupling down instead
    of it living only in whoever's memory ran the original capture.

RESULT_ARRIVAL is the one new state this ticket adds (AUDIT pair 4): the
existing NOENEMY fixture starts after the RESULT window has already slid
in (it is static from its own frame 2 onward), so `result` in regress.py
can only ever compare one still picture. RESULT_ARRIVAL is captured early
enough that the window's whole slide-in happens inside a 40-frame capture
from it. It is `root=False` and IS built by this file, into /tmp, on
request.

Needs /tmp/mgba_capture and the real ROM, which are never committed
(TRANSFER.md). Every state this writes goes to /tmp -- never into the repo.
"""

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Optional, Tuple

CAPTURE = "/tmp/mgba_capture"
REAL = "/tmp/bn6f_real.gba"
STERILE = "/tmp/bn6f_sterile.gba"

PAUSED = "/tmp/pausedwithcannon.state"
BATTLESTART = "/tmp/battlestart.state"


@dataclass
class State:
    name: str
    path: str
    root: bool
    description: str
    #: The recipe, present even for a root this project COULD in principle
    #: rebuild (NOENEMY) so the coupling is on paper -- absent (None) only
    #: where there is genuinely nothing to run (PAUSED, CHIPSELECT,
    #: BATTLESTART).
    rom: Optional[str] = None
    base: Optional[str] = None          # another state's --loadstate, or None for a cold boot
    script: Optional[str] = None        # tools/mgba_capture.c's "--script" syntax
    cheats: Tuple[str, ...] = field(default_factory=tuple)  # each "--cheat" argument
    #: Each "frame:addr:val" argument for tools/mgba_capture.c's --poke-at
    #: (AUDIT wave 3c "encounter-roll" ticket): a ONE-SHOT write, unlike
    #: `cheats` above (re-applied every frame). For a condition that must
    #: fire on exactly one named frame -- see "emptyfield_start"'s own use.
    poke_at: Tuple[str, ...] = field(default_factory=tuple)
    #: Each "addr:val16" argument for mgba_capture's --poke (one-time, at
    #: load, before frame 0) -- chip_compare.py's own library-ownership
    #: technique (library_pokes()), used by "chip_ready_empty" below.
    pokes: Tuple[str, ...] = field(default_factory=tuple)
    #: Frames to run before --savestate fires. NOTE THE OFF-BY-ONE THAT
    #: ISN'T ONE: mgba_capture's loop runs frame indices 0..frames-1 and
    #: writes the state AFTER the last of them, so the state is poised to
    #: compute frame `frames` next -- loading it and capturing K frames of
    #: your own gives you frame indices `frames`..`frames+K-1` in the
    #: original run's numbering. Verified empirically (see the ticket
    #: report): a state built with frames=20 reproduces, frame for frame,
    #: an uninterrupted run's frames 20 onward.
    frames: Optional[int] = None
    note: str = ""


#: Deleting the enemy's HP/MaxHP fields keeps them at 0 every frame, which is
#: what makes the battle conclude (TRANSFER.md section 3, and the same pair
#: check_banner in regress.py pokes). The addresses are BattleObject+0x24/26
#: for the Mettaur at 0x0203ab60 (TRANSFER.md section 2).
DELETE_ENEMY = ("0x0203ab84:0", "0x0203ab86:0")

#: BATTLESTART's own battle (fresh-state ticket) fields THREE Mettaurs, not
#: PAUSED's one, in three more BattleObject slots -- found live, not by
#: extrapolating the 0xd8 stride from section 2's two known addresses:
#: `--dump 0x0203a9b0:0x500` at battlestart.state+200 frames (all three
#: materialised, TRANSFER 7ba's frames 113/141/173) shows MegaMan at
#: 0x0203a9b0 (panel 2,2, unchanged from section 2) and three enemy
#: BattleObjects, each NameID 0x0001 (Mettaur), HP 40/40, at 0x0203aa88
#: (panel 4,1), 0x0203ab60 (panel 5,2 -- the same address PAUSED's own
#: single Mettaur happens to live at, coincidentally the same allocator
#: slot, not the same battle), and 0x0203ac38 (panel 6,3) -- the third
#: enemy, exactly the 0xd8 stride section 2 already documented, confirmed
#: rather than assumed. HP/MaxHP at each base+0x24/+0x26 as section 2 gives.
DELETE_ENEMY_3 = (
    "0x0203aaac:0", "0x0203aaae:0",  # first Mettaur  (panel 4,1)
    "0x0203ab84:0", "0x0203ab86:0",  # second Mettaur (panel 5,2)
    "0x0203ac5c:0", "0x0203ac5e:0",  # third Mettaur  (panel 6,3)
)

STATES = [
    State(
        name="paused",
        path=PAUSED,
        root=True,
        description="A live battle, Cannon40 already queued in the hand, "
                     "paused (Start resumes it). The base of nearly every "
                     "other fixture (tools/chip_compare.py's STATE, "
                     "regress.py's ALIVE/PAUSED). RASTATE format -- made by "
                     "hand in mGBA-qt. Its own backdrop-scroll counters read "
                     "7891 frames already elapsed (TRANSFER.md 7av) with "
                     "nothing in the state or this project explaining that "
                     "number, which is the other half of why it cannot be "
                     "replayed from a cold boot: the number is not just "
                     "unrecorded, the process that produced it is gone.",
    ),
    State(
        name="chipselect",
        path="/tmp/chipselect.state",
        root=True,
        description="The chip-select window, open, mid-battle. Used by "
                     "regress.py's check_window/check_card/check_cursor. "
                     "RASTATE format -- made by hand in mGBA-qt, same as "
                     "PAUSED.",
    ),
    State(
        name="battlestart",
        path="/tmp/battlestart.state",
        root=True,
        description="A battle's real frame 0 -- eBGScrollCBCounters read "
                     "0/0, TRANSFER.md 7aw. Used by regress.py's "
                     "check_opening. PNG-chunked format (mCoreSaveStateNamed "
                     "with SAVESTATE_ALL) -- built by this project's own "
                     "harness at some point, NOT hand-made, but its "
                     "documented recipe (7aw: an overworld save, walked "
                     "toward a random encounter with the roll forced every "
                     "frame and the held direction varied so the RNG does "
                     "not walk one correlated orbit) needs an overworld save "
                     "file that is not in /tmp and was never written down. "
                     "Nothing here is runnable without first scripting a "
                     "title screen, a name entry and an intro from a cold "
                     "ROM -- which is real work this ticket did not do -- so "
                     "this stays root until that exists.",
    ),
    State(
        name="overworld_net",
        path="/tmp/overworld_net.state",
        root=False,
        rom=REAL,
        base=BATTLESTART,
        script="Start@200,A@210,A@400,A@430,A@460,A@490,A@520,A@550,A@580,"
               "A@610,A@640,A@670,A@700,A@730,A@760",
        cheats=DELETE_ENEMY_3,
        frames=800,
        description="The overworld net area a battle's own encounter came "
                     "from, reached by letting BATTLESTART's battle actually "
                     "resolve on the REAL (unpatched) ROM -- AUDIT wave 3c "
                     "'fresh-state' ticket step 1, the base the sterile "
                     "empty-field walk (emptyfield_start) loads. All three "
                     "Mettaurs are held at HP 0 the whole run (DELETE_ENEMY_3 "
                     "-- see its own comment for how the three addresses "
                     "were found), which is enough for battle_isBattleOver "
                     "(unpatched here) to conclude the fight on its own.",
        note="VERIFIED (this ticket). Script, frame by frame against "
             "battlestart.state's own timeline: the chip window is open by "
             "frame ~150 (matches TRANSFER 7aw); Start@200 moves the cursor "
             "to OK, A@210 confirms an empty hand and closes it; BATTLE "
             "START! around frame 300; ENEMY DELETED/GET around 400 (all "
             "three HP-zeroed enemies resolve as one kill, not three "
             "separate deletions -- not investigated further, not needed "
             "for this recipe); the RESULT window's two pages (DeleteTime/"
             "Busting LV, then GET DATA showing a chip, then a zenny page) "
             "come up around 500-730 and the trailing A@430..A@730 (30-frame "
             "spacing -- tighter spacing just re-picks the chip window's "
             "cursor before Start closes it, per TRANSFER 7aw) page through "
             "them; a black transition runs ~735-775; the net area "
             "('CentralArea1') is up, lit and static by frame ~778, and "
             "frame 800 (this state) matches it with no further script "
             "needed. MOVEMENT VERIFIED, not by the handover's own named "
             "bytes (0x02009f5c/0x02009f60 from OverworldPlayerObject.inc, "
             "which do not move here either -- consistent with the "
             "handover's own finding that those .inc offsets are not to be "
             "trusted unverified): `--watch 0x02009f40:0x50:file` over 80 "
             "held frames of Right, and separately of Down, from this state "
             "finds a live pair at 0x02009f62/0x02009f63 (a little-endian "
             "u16, wrapping, incrementing by exactly 1/frame under EITHER "
             "held direction -- consistent with this map's isometric "
             "projection, where screen-Right and screen-Down both move the "
             "underlying grid position) and a second axis-specific pair at "
             "0x02009f5e (paired with 0x02009f6a) that only moves under "
             "Down, not Right. Whatever their exact X/Y semantics, both "
             "pairs respond to held input exactly as a position counter "
             "should, which is the acceptance test this step asked for.",
    ),
    State(
        name="noenemy2",
        path="/tmp/noenemy2.state",
        # See the module docstring: harness-made (PNG format) so a recipe
        # below IS runnable, but flipping this to False makes `build`
        # silently replace the fixture's reward content -- not done here.
        root=True,
        rom=REAL,
        base=PAUSED,
        script="Start@10",
        cheats=DELETE_ENEMY,
        frames=172,
        description="A battle already resolved into the RESULT window "
                     "(regress.py's check_result; the real side of "
                     "tools/chip_compare's method extended past a chip). "
                     "PNG-chunked -- harness-made, not hand-made.",
        note="ATTEMPTED AND VERIFIED NOT EQUIVALENT (this ticket). Recipe: "
             "load PAUSED on the REAL rom (not sterile -- sterile patches "
             "battle_isBattleOver to never conclude, which is exactly what "
             "reaching RESULT needs to NOT happen), force both enemy HP "
             "fields to 0 every frame, press Start at frame 10 to resume, "
             "run 172 frames, --savestate. Capturing 60 frames from the "
             "result and diffing full-screen against 60 frames of the real "
             "noenemy2.state (tools/chip_compare.py's frame()+differs()) "
             "gives 238053 px total, ~3200-4700 px/frame, ALL of it in the "
             "reward panel (y 96..158 on frame 0, 4406 px there alone) -- "
             "the window chrome above y=96 is bit-for-bit identical. The "
             "reward itself is rolled from RNG state this recipe does not "
             "reach the same way real play did, so an instant HP=0 kill "
             "gets a different prize. A second, structural difference: the "
             "real noenemy2.state is static for at least 60 frames (no "
             "interactive prompt yet), while this recipe's own timeline "
             "starts blinking a 'press to continue' cursor by its frame 5 "
             "(every 8 frames after) -- the reward flow the real capture is "
             "in the middle of is evidently longer (more pages, e.g. a chip "
             "AND zenny rather than one). No frame count fixes this: it is "
             "the same one script's timeline, so every choice of `frames` "
             "either sits inside the slide-in (frames<167) or the blink "
             "(frames>=172-ish forever after, period 8). Reported, not "
             "hidden, per the ticket.",
    ),
    State(
        name="result_arrival",
        path="/tmp/result_arrival.state",
        root=False,
        rom=REAL,
        base=PAUSED,
        script="Start@10",
        cheats=DELETE_ENEMY,
        frames=135,
        description="AUDIT pair 4: NOENEMY starts after the RESULT window "
                     "has already arrived (static from its own frame 2 "
                     "onward), so `result` can only ever compare one still "
                     "picture. This state is captured 32 frames earlier in "
                     "the same timeline as NOENEMY's recipe above -- frame "
                     "135 rather than 172 -- so the window's entire slide-in "
                     "(measured at frames 21..32 of a 40-frame capture from "
                     "it, see below) happens INSIDE a 40-frame capture "
                     "instead of before it.",
        note="VERIFIED (this ticket). Two independent builds of this exact "
             "recipe differ in 16 incidental bytes of the state file itself "
             "(a small metadata chunk, not the 240x160 core state) but "
             "render 40 identical frames when captured -- the recipe is "
             "deterministic where it matters. Capturing 40 frames from the "
             "built state and diffing consecutive frames over the window "
             "region (26,24,215,155): frames 2..20 move (the tail of the "
             "battle settling -- expected, this is BEFORE arrival), frames "
             "21..32 are the slide-in itself (2983..7803 px moving each "
             "frame), frame 35 has an 80px residual settle, and the rest "
             "read 0. The arrival is inside the window and not at frame 0, "
             "which is what pair 4 asked for.",
    ),
    State(
        name="chip_ready",
        path="/tmp/chip_ready.state",
        root=False,
        rom=STERILE,
        base=PAUSED,
        script="Start@10",
        cheats=(),
        frames=50,
        description="Wave 3b ticket step 1, KEPT AS THE RECORD OF A TRIED "
                     "AND REJECTED FIX -- NOT LOADED BY ANYTHING IN "
                     "tools/harness.py. PAUSED's own hand-made snapshot "
                     "leaves a ~528px OAM 'portrait box' (objects 0-1, tiles "
                     "948-959, palette 12, top-left) sitting in VRAM from "
                     "whatever the chip window was doing when the state was "
                     "captured by hand -- present at every chip/cannon "
                     "capture's canon frames 43-48. This state is PAUSED "
                     "run forward through real input (Start@10 only, enemy "
                     "left alive) to frame 50, then saved -- the attempt "
                     "was to reach a clean, reloadable base past the "
                     "garbage. See the note for why it does not actually "
                     "do that.",
        note="VERIFIED, in TWO ROUNDS, that this does not work (this "
             "ticket). ROUND 1: the portrait garbage turns out to clear "
             "only as a side effect of the enemy's OWN death/dissolve "
             "processing running -- a parallel run that keeps the enemy "
             "alive the whole time never clears it (out to 390 frames "
             "tried), so an EARLIER build of this state also deleted the "
             "enemy (matching the downstream recipe's timing) to make the "
             "garbage clear. That broke chip-firing entirely: pressing A "
             "at ANY delta (1 through 120 frames) after loading a state "
             "where the enemy is already dead produces IDENTICAL output "
             "regardless of timing -- the input is silently ignored "
             "(ordinary movement input, tested the same way, DOES work "
             "after the same reload, so this is specific to the attack "
             "command). ROUND 2 (this build, cheats=() -- the enemy is "
             "left alive during the build, matching PAUSED's own "
             "property): fireability is preserved, but the portrait "
             "garbage then NEVER clears (verified live: still present, "
             "unchanged, at frame 0 of a reload built this way) -- the "
             "two requirements are mutually exclusive for a single base "
             "state; there is no `frames=` value that gets both. Chasing "
             "the actual ROM-code gate for the chip-fire refusal (traced "
             "to `sub_800938A`/`sub_800801C` in asm00_1.s, see "
             "tools/harness.py's own comment by ALIGN_CHIP) did not "
             "resolve it either: patching the compare that gate uses did "
             "not restore firing after a save/reload past the dissolve. "
             "tools/harness.py's chip/cannon rows load PAUSED directly, "
             "unchanged, with the ORIGINAL 'Start@10,A@40' script -- the "
             "14388/2350 shared baseline this state was meant to fix is "
             "reported honestly, not silently carried by a state that "
             "looks like a fix but is not one.",
    ),
    State(
        name="emptyfield_start",
        path="/tmp/emptyfield_start.state",
        root=False,
        rom="/tmp/bn6f_sterile_emptynet.gba",  # STERILE_BASE + --empty-net-encounter (patch_sterile.py)
        base="/tmp/overworld_net.state",
        script=",".join("%s@%d" % (("Right", "Down", "Left", "Up")[i % 4], i)
                         for i in range(160)),  # cycled one per frame, TRANSFER 7aw's own shape
        poke_at=("100:0x02001c16:0x2000", "100:0x02001c18:0"),  # ONE roll attempt, at frame 100
        cheats=DELETE_ENEMY_3,  # kill whichever slot(s) spawn, every frame from load
        frames=119,
        description="AUDIT wave 3c/3d 'fresh-state'/'encounter-roll' ticket, ROUTE CHANGED THIS "
                     "SESSION from patching the encounter table to the technique every other "
                     "zero-enemy check in this harness already uses (AUDIT pair 3): let a real "
                     "encounter spawn, then DELETE it (force HP=0 every frame). See the note for "
                     "why the encounter-table patch route (this entry's previous recipe) turned "
                     "out to be unreliable even once the RNG-freeze root cause (below) was fixed.",
        note="THE ROLL'S OWN FREEZE, ROOT-CAUSED (this session): --trace-pc on sub_80AA4C0's own "
             "`bl GetRNG` (ROM 0x080AA51E) and its masked-value/threshold compare (completing by "
             "0x080AA52A) shows that the OLD recipe -- 0x02001c16/0x02001c18 forced EVERY frame "
             "from load -- leaves GetRNG's masked draw effectively frozen: nothing on this code "
             "path perturbs it between one frame's draw and the next when the accumulator itself "
             "is pinned open every frame, so the roll's outcome is fixed at load (TRANSFER 7aw's "
             "held-direction orbit trap, walked through the accumulator instead of input). "
             "mgba_capture.c gained --poke-at frame:addr:value (a ONE-SHOT write, applied "
             "immediately before the named frame instead of every frame) as the fix: real "
             "per-frame play runs untouched up to the poke, so sweeping the frame samples "
             "GetRNG's actual state each time instead of repeating frame 0's fixed draw. "
             "VERIFIED: sweeping N in 1-frame steps flips between roll success and failure and "
             "lands on many distinct nearby EnemySetupArr addresses (0x080b52f9, 5313, 5320, "
             "532d, 5347, 5354, 5365, 5376, 5387, 5398 all seen, N=80..230) -- genuine variation, "
             "not a frozen repeat. "
             ""
             "WHY THE ENCOUNTER-TABLE PATCH ROUTE WAS ABANDONED, not merely left unfinished: a "
             "controlled A/B test (this session) proved that PATCHING a naturally-reached entry "
             "makes THE SAME recipe that found it reach a DIFFERENT entry instead. N=100 with "
             "block=1 deterministically selects EnemySetupArr=0x080b52f9 (re-run twice, "
             "byte-identical) on the ROM with only 0x080b5306 patched; after ALSO patching "
             "0x080b52f9's own entry (byte at +4, ROM 0x080b52fd, 0x11->0xf0, the exact same "
             "patch shape as 0x080b530a), the IDENTICAL N=100 recipe selects 0x080b5398 instead "
             "-- proof that whatever selects an entry for a given roll is sensitive to an "
             "entry's own encoded content/length, not just to table position, so 'find it on an "
             "unpatched ROM, then patch it, then walk the same recipe again' is not a sound "
             "method for ANY entry this way (not just 0x080b5306) -- once an entry is emptied it "
             "stops being reachable by the walk that found it. A wide re-search for 0x080b5306 "
             "itself (one-shot poke N=0..700 in 1-frame steps, block=1) never landed on it "
             "either. patch_sterile.py's --empty-net-encounter patch (0x080b530a) is UNCHANGED "
             "and still correct as a description of that one table entry; it is simply not "
             "used by this recipe any more. "
             ""
             "THIS RECIPE, VERIFIED END TO END (this session): from overworld_net.state, cycle "
             "Right/Down/Left/Up one per frame (TRANSFER 7aw's own shape), one-shot-poke the "
             "roll's gate open at frame 100 only -- reliably (re-run twice) reaches "
             "EnemySetupArr=0x080b52f9 (MegaMan + 2 Mettaur, HP 40/40 each at BattleObject slots "
             "0x0203aa88/0x0203ab60), held at HP 0 the whole run by DELETE_ENEMY_3 (harmless on "
             "the never-populated third slot). SubsystemIndex: 4 (map) through frame 99, 8 "
             "(battle_init trigger) at 100, 12 (battle main) from 116 onward, UNCHANGED through "
             "the rest of a 320-frame capture -- no crash, no reversion. eBGScrollCBCounters "
             "(0x02009690/0x02009694) read 0/0 at capture frame 118 (battle's own frame 0, "
             "TRANSFER 7aw) -- confirmed by reloading a state built at frames=119: --peek both "
             "addresses immediately after load, before running anything, reads 0x0000/0x0000. "
             "MegaMan HP/MaxHP 60/100, all three enemy slots 0/0 at capture frame 199 (81 real "
             "frames into the battle) -- OAM at that frame decodes to 12 non-hidden entries (the "
             "y=240/x=0/tile=0 rest are the standard GBA 'unused slot' sentinel), all consistent "
             "with MegaMan's own multi-tile sprite, none matching a live enemy (which the HP "
             "dump already rules out structurally, the same proof states.py's own noenemy2 entry "
             "uses).",
    ),
    State(
        name="chip_ready_empty",
        path="/tmp/chip_ready_empty.state",
        root=False,
        rom="/tmp/bn6f_sterile_emptynet.gba",
        base="/tmp/emptyfield_start.state",
        description="AUDIT wave 3c/3d ticket step 3: emptyfield_start with a chip picked "
                     "through the chip window (which opens on its own) and in hand, ready to "
                     "test whether a chip fires with no enemy alive at all -- see the note for "
                     "the answer (yes) and which chip actually ended up in hand (Vulcan1, not "
                     "Cannon).",
        # The chip window opens ON ITS OWN partway through this battle too (TRANSFER 7aw), just
        # not at 7aw's own battle-frame 165 -- measured THIS session by scanning --only-bg 3
        # content frame by frame: blank through ~90, a slide-in at 100, settled (37765 px, flat)
        # from 110 onward, still open with nothing pressed. A@130 picks whatever the window
        # offers in its default cursor slot (measured: chip id 5, Vulcan1 -- see the note for why
        # this is NOT Cannon despite the library poke below, and why that is not chased further),
        # Start@140 moves the cursor to OK (TRANSFER 7aw: "Pressing A alone picks chips and
        # leaves the window open"), A@150 confirms and closes it.
        script="A@130,Start@140,A@150",
        cheats=DELETE_ENEMY_3,
        # chip_compare.capture_real's own technique (tools/chip_compare.py's library_pokes()),
        # values computed by hand against THIS state's own library bytes (peeked live: 0xfd9d at
        # 0x020008a0, 0x7c62 at 0x02004c20) rather than reused from chip_compare's own
        # peek16() -- that function reads PAUSED's library, a different save's data, not this
        # one's. Kept as plain --poke tuples rather than calling library_pokes() itself, since
        # that function's own peek16() reads PAUSED's library, not this state's.
        pokes=("0x020008a0:0x019d", "0x02004c20:0x8062"),
        frames=280,  # 230 to the window's close + 50 margin -- see the note for why
        note="VERIFIED END TO END (this ticket). BG3 content (--only-bg 3, sampled every 10 "
             "frames): blank through 90, 704px at 90 (slide-in starting), 36913 at 100, settled "
             "flat at 37765 from 110 through at least 590 -- the window opens ~100-110 battle-"
             "frames in for this recipe (not 165, which was measured for a DIFFERENT, 3-Mettaur "
             "battle/state) and stays open indefinitely with nothing pressed, exactly as 7aw "
             "describes. THE LIBRARY POKE DID NOT FORCE CANNON: applied "
             "(0x020008a0:0x019d, 0x02004c20:0x8062 -- chip_compare.library_pokes()'s own "
             "formula, marking chip id 1/Cannon owned) before the window opens, then A@130 "
             "picked whatever sits in the window's default cursor slot regardless -- watched "
             "HAND_SLOT (0x020349c2) settle at chip id 5 (Vulcan1, already in this project's own "
             "43-chip scoreboard as demo-vulcan) at capture frame 212, not 1. A second attempt "
             "(4 Left-presses at 130/140/150/160 before picking, hoping to reach a different "
             "slot) landed on the SAME chip 5 -- NOT CHASED FURTHER given the time this ticket "
             "had: the offered set is very likely drawn from this save's own equipped folder, "
             "not from the ownership 'library' library_pokes() edits (which only affects hand-"
             "VALIDATION post-pick, per that function's own docstring), so forcing a SPECIFIC "
             "offered chip likely needs either finding the folder/deck's own RAM address or "
             "poking a per-slot offer buffer neither this session nor TRANSFER.md's existing "
             "notes have located. Chip 5 (Vulcan1) served the premise test just as well -- see "
             "the ticket report. MegaMan CurState/CurAction (0x0203a9b0+8/+9) settle at (4,8) -- "
             "the ticket's own documented idle baseline -- 48 frames after the window closes; "
             "this state is built at frames=280 (230 to close + 50 margin) so IT ALREADY shows "
             "(4,8) at load, verified by --peek immediately after loading with no frames run.",
    ),
]

BY_NAME = {s.name: s for s in STATES}


def run_capture(state, out_dir, count, extra=()):
    cmd = [CAPTURE, state.rom, out_dir, str(count)]
    if state.base:
        cmd += ["--loadstate", state.base]
    for c in state.cheats:
        cmd += ["--cheat", c]
    for p in state.pokes:
        cmd += ["--poke", p]
    for p in state.poke_at:
        cmd += ["--poke-at", p]
    if state.script:
        cmd += ["--script", state.script]
    cmd += list(extra)
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def build(name):
    state = BY_NAME.get(name)
    if state is None:
        raise SystemExit("no such state %r -- see `states.py list`" % name)
    if state.root:
        raise SystemExit(
            "%s (%s) is a ROOT state -- refusing to overwrite it.\n%s"
            % (state.name, state.path, state.description))
    if not state.rom or state.frames is None:
        raise SystemExit("%s has no runnable recipe" % state.name)
    if not os.path.exists(CAPTURE):
        raise SystemExit("%s not found -- build it first (see TRANSFER.md section 1)" % CAPTURE)
    scratch = "/tmp/states_py_scratch_%s" % state.name
    run_capture(state, scratch, state.frames, extra=["--savestate", state.path])
    subprocess.run(["rm", "-rf", scratch], check=True)
    print("built %s -> %s" % (state.name, state.path))


def list_states():
    print("%-14s %-6s %-32s %-14s %-7s %s" % ("name", "root", "path", "base", "frames", "description"))
    for s in STATES:
        base = os.path.basename(s.base) if s.base else "(cold boot)" if s.rom else "-"
        frames = str(s.frames) if s.frames is not None else "-"
        print("%-14s %-6s %-32s %-14s %-7s %s" % (
            s.name, "yes" if s.root else "no", s.path, base, frames, s.description.split(".")[0] + "."))
        if s.note:
            print("               %s" % s.note)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    b = sub.add_parser("build")
    b.add_argument("name", help="a state's name, or 'all'")
    args = ap.parse_args()

    if args.cmd == "list":
        list_states()
        return
    if args.name == "all":
        for s in STATES:
            if s.root:
                print("skip %-14s ROOT (%s)" % (s.name, s.path))
                continue
            if s.base and not os.path.exists(s.base):
                # a chain rooted at a lost root state (battlestart died with /tmp on 2026-09-08);
                # skip it and keep building the rest instead of aborting the whole run
                print("skip %-14s base missing (%s)" % (s.name, s.base))
                continue
            build(s.name)
        return
    build(args.name)


if __name__ == "__main__":
    sys.exit(main())
