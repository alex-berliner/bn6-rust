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
]

BY_NAME = {s.name: s for s in STATES}


def run_capture(state, out_dir, count, extra=()):
    cmd = [CAPTURE, state.rom, out_dir, str(count)]
    if state.base:
        cmd += ["--loadstate", state.base]
    for c in state.cheats:
        cmd += ["--cheat", c]
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
            build(s.name)
        return
    build(args.name)


if __name__ == "__main__":
    sys.exit(main())
