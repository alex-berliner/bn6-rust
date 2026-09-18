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
        trigger (delete the enemy's HP, docs/provenance.md#3 / #7bf). The
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
      - BATTLESTART's recipe was rebuilt from power-on (ticket R1): cold boot
        with the battery save (/tmp/bn6f_real.srm) scripts the title screen
        and Continue into CentralArea1 (overworld_net), then a one-shot poke
        at frame 60 triggers an encounter roll (3 Mettaurs) reaching battle
        frame 0 (eBGScrollCBCounters 0/0) at frame 79. battlestart is no
        longer a root.

    PAUSED and CHIPSELECT are true roots: `build` refuses them outright.
    NOENEMY is marked `root=True` too, for the reasons above, but carries
    a `recipe` a future session can flip on once its caveat is resolved.
    BATTLESTART is now a built state (`root=False`).

RESULT_ARRIVAL is the one new state this ticket adds (AUDIT pair 4): the
existing NOENEMY fixture starts after the RESULT window has already slid
in (it is static from its own frame 2 onward), so `result` in regress.py
can only ever compare one still picture. RESULT_ARRIVAL is captured early
enough that the window's whole slide-in happens inside a 40-frame capture
from it. It is `root=False` and IS built by this file, into /tmp, on
request.

Needs /tmp/mgba_capture and the real ROM, which are never committed
(docs/provenance.md). Every state this writes goes to /tmp -- never into the repo.
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
SRM = "/tmp/bn6f_real.srm"

PAUSED = "/tmp/pausedwithcannon.state"
BATTLESTART = "/tmp/battlestart.state"
CHIPSELECT = "/tmp/chipselect.state"


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
    save: Optional[str] = None          # battery save (.srm) for --loadsave from cold boot
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
    #: Each (file_offset, byte_value) pair to apply to `state.path` byte-wise
    #: BEFORE any mgba_capture run -- a cheap "state built from another state
    #: by patching N bytes" recipe, used by "pa_chipselect_state" (one byte
    #: patched from /tmp/chipselect.state at file offset 0x5DDC0 to swap the
    #: hand-slot-0 chip, T71's recipe).
    patches: Tuple[Tuple[int, int], ...] = field(default_factory=tuple)
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
#: what makes the battle conclude (docs/provenance.md#3, and the same pair
#: check_banner in regress.py pokes). The addresses are BattleObject+0x24/26
#: for the Mettaur at 0x0203ab60 (docs/provenance.md#2).
DELETE_ENEMY = ("0x0203ab84:0", "0x0203ab86:0")

#: BATTLESTART's own battle (fresh-state ticket) fields THREE Mettaurs, not
#: PAUSED's one, in three more BattleObject slots -- found live, not by
#: extrapolating the 0xd8 stride from section 2's two known addresses:
#: `--dump 0x0203a9b0:0x500` at battlestart.state+200 frames (all three
#: materialised, docs/provenance.md#7ba's frames 113/141/173) shows MegaMan at
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
                     "7891 frames already elapsed (docs/provenance.md#7av) with "
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
        name="overworld_net",
        path="/tmp/overworld_net.state",
        root=False,
        rom=REAL,
        base=None,
        save=SRM,
        script="Start@700,A@800",
        frames=900,
        description="The overworld net area reached from cold boot with the "
                     "battery save (/tmp/bn6f_real.srm) through the title "
                     "screen and Continue into CentralArea1.",
        note="VERIFIED (ticket R1). Cold boot with /tmp/bn6f_real.srm loads "
             "through Capcom logo (frames 0-210) and title screen (press "
             "Start appears ~650); Start@700 opens Continue menu (defaulting "
             "to Continue when save is present); A@800 confirms Continue. "
             "Black transition completes by frame 835 and CentralArea1 net "
             "map is loaded and controllable. SubsystemIndex (at 0x02001b80) "
             "settles at 4 on the map from frame 835 through 900+ (verified: "
             "peek 0x02001b80 reads 0x0004). Controllable overworld play "
             "verified by position counters responding to held directional "
             "input: u16 at 0x02009f62/0x02009f63 increments 1/frame under "
             "held Right or Down; u16 at 0x02009f5e increments under Down. "
             "Build time: ~0.78s. Determinism: 40 frames from two independent "
             "builds diff to 0 pixels.",
    ),
    State(
        name="battlestart",
        path="/tmp/battlestart.state",
        root=False,
        rom=REAL,
        base="/tmp/overworld_net.state",
        script=",".join("%s@%d" % (("Right", "Down", "Left", "Up")[i % 4], i)
                         for i in range(79)),
        poke_at=("60:0x02001c16:0x2000", "60:0x02001c18:0"),
        frames=79,
        description="A battle's real frame 0 -- eBGScrollCBCounters read "
                     "0/0, docs/provenance.md#7aw. Used by harness.py's "
                     "check_opening. Rebuilt by recipe from overworld_net.",
        note="VERIFIED (ticket R1). From overworld_net.state, cycle 4 directions "
             "one per frame; one-shot poke the encounter roll open at frame 60 "
             "only. Battle init triggers at frame 60 (SubsystemIndex 8); battle "
             "main loop begins at frame 76 (SubsystemIndex 12). eBGScrollCBCounters "
             "(0x02009690/0x02009694) read 0x0000/0x0000 at frame 79 (verified by "
             "--peek immediately at reload). Rolled EnemySetupArr entry at "
             "0x080b5354 (3 Mettaurs at panels (5,1), (5,3), (6,2)). Live RAM "
             "BattleObjects confirmed at 0x0203aa88, 0x0203ab60, 0x0203ac38, each "
             "NameID 0x0001 (Mettaur), HP 40/40. Build time: ~0.13s. Determinism: "
             "40 frames from two builds diff to 0 pixels.",
    ),
    State(
        name="battlestart_gunner",
        path="/tmp/battlestart_gunner.state",
        root=False,
        rom=REAL,
        base="/tmp/overworld_net.state",
        script=",".join("%s@%d" % (("Right", "Down", "Left", "Up")[i % 4], i)
                         for i in range(79)),
        # battlestart's own roll-open pokes PLUS T9b's frame-60 lever: a
        # one-shot write of iCurrFrame (0x0200a210) 0x372 -> 0x371 makes the
        # frame-60 encounter roll pick BattleSettings record 6 = 0x080b4bd8
        # (setup byte_80B5347) instead of record 7 (0x080b4be8, the 3
        # Mettaurs battlestart rolls naturally).
        poke_at=("60:0x02001c16:0x2000", "60:0x02001c18:0",
                 "60:0x0200a210:0x371"),
        frames=79,
        description="A battle's real frame 0 whose encounter roll picked the "
                     "Mettaur+Gunner record (T9b's frame-60 iCurrFrame lever). "
                     "Base for the harness's gunner row.",
        note="VERIFIED (ticket T9c). Recipe = battlestart's own plus the "
             "iCurrFrame lever above; both re-measured on the built state's own "
             "recipe run with --watch: chosen BattleSettings ptr 0x02001b9c reads "
             "0x080b4bd8 from capture frame 60 on (never 0x080b4be8), and the "
             "enemy BattleObject slots populate at capture frame 148 -- slot0 "
             "panel (5,2) / NameID 0x0001 / HP 0x0028 (Mettaur, object at "
             "0x0203aa88: panel +0x12 = 0x0205, NameID +0x28 = 0x0001, HP +0x24 "
             "= 0x0028) and slot1 panel (6,3) / NameID 0x0085 / HP 0x003c (the "
             "Gunner, object at 0x0203ab60), slot2 stays empty. Build time: "
             "~0.15s.",
    ),
    State(
        name="battlestart_ai4_rank0",
        path="/tmp/battlestart_ai4_rank0.state",
        root=False,
        rom=REAL,
        base="/tmp/overworld_net.state",
        script=",".join("%s@%d" % (("Right", "Down", "Left", "Up")[i % 4], i)
                         for i in range(79)),
        # battlestart_gunner's roll-open pokes, then T87's unlock + lever.
        # Unlock: a ONE-SHOT frame-60 write of the event-flag byte
        # 0x02001d58 (canon: eEventFlags + 0xd0, bn6f.map:253; flag N lives
        # at eEventFlags+(N>>3) bit 0x80>>(N&7), asm/asm03_0.s:18558-18577)
        # sets EVENT_681 (1665 -> byte+0xd0 bit 0x40) and keeps the
        # neighbour byte (events 1672..1679, reads 0x02) intact. Overworld
        # MapGroup/MapNumber stay EXACTLY as overworld_net has them:
        # selectEncounterTableForMap_80AA5F4 swaps the whole internet
        # group-table root on EVENT_681 (asm/asm29.s:10362-10371, root
        # 0x08020188), and its (net group 0x10, map 0) slot -- map 0 =
        # CentralArea1's own map number, UNTOUCHED -- is encounter list
        # 0x080b50b0 (12 records, ALL rec7==0) instead of CentralArea1's
        # 0x080b4b78 (which names NO ai_index-4 rank). Writing the map
        # bytes instead (0x02001b84, oGameState_MapId) WEDGED the
        # overworld: iCurrFrame froze, rollRandomEncounter_80AA4C0 was
        # never entered again (its Unk_14 step accumulator 0x02001c18
        # stayed 0) and no battle ever started -- the flag flip touches
        # only the roll's own table pick. The iCurrFrame lever (canon:
        # iCurrFrame, 0x0200a210; the roll reads it one tick after the
        # poke, T58 model) 0x37a makes the roll read 0x37b = 891,
        # 891 mod 12 = 3 -> record 0x080b50e0 (formation 0x080b580a,
        # enemy ids 00/85/13 = ai_index-4 rank v0, enemy_idx 0x13).
        poke_at=("60:0x02001c16:0x2000", "60:0x02001c18:0",
                 "60:0x02001d58:0x0240", "60:0x0200a210:0x37a"),
        frames=79,
        description="A battle's real frame 0 whose encounter roll picked "
                    "record 0x080b50e0 (CentralArea1's net area read through "
                    "EVENT_681's table swap: list 0x080b50b0 rec3) naming the "
                    "ai_index-4 rank v0 (enemy_idx 0x13; T87).",
        note="VERIFIED (ticket T87). Recipe = battlestart_gunner's base/script/"
             "roll-open pokes PLUS the frame-60 EVENT_681 flag set "
             "(0x02001d58:0x0240; eEventFlags=0x02001c88, flag 1665 -> byte +0xd0 "
             "bit 0x40, neighbour byte 0x02 preserved) and the iCurrFrame lever "
             "0x37a (read 0x37b=891, 891 mod 12 = 3 -> rec3 0x080b50e0 of list "
             "0x080b50b0, whose 12 records are ALL rec7==0). --watch on the built "
             "state: chosen BattleSettings ptr 0x02001b9c reads 0x080b50e0 from "
             "frame 0; slots populate at capture frame 69 (= frame 148 from "
             "overworld_net, T9c's offset) -- slot0 NameID 0x0085 (Gunner) / HP "
             "0x003c (0x0203aab0/aaac), slot1 NameID 0x0013 (ai_index-4 rank v0, "
             "enemy_idx 0x13) / HP 0x005a (0x0203ab88/ab84), byte-equal to "
             "off_8109150[4] = 0x0810ae4c Struct2 row-0 elem_hp 0x005a (6-byte "
             "rows; stride verified on ai 1 = 0x28/0x50/0x78/0xA0/0x78/0xB4 and "
             "ai 0x17 row 0 = 0x3c); slot2 NameID/HP stay 0 (the id-00 quad spawns "
             "a shell, ai 0's act = nullsub_13). CurState_CurAction 0x0203aa90/"
             "0x0203ab68: 0x0004 at 69 -> 0x0104 at 151, never an action >= 0x20 "
             "through 330 frames; sequencer 0x0203CA70 = 0 at frame 320 (T58's "
             "stuck-sequencer blocker). Determinism: 40 frames from two "
             "independent builds diff to 0 pixels (worst 0); state hashes "
             "10cdd201.../f70f298d... differ byte-wise (serialized screenshot), "
             "pixels identical. Build time: ~0.2s.",
    ),
    State(
        name="battlestart_scripted",
        path="/tmp/battlestart_scripted.state",
        root=False,
        rom=REAL,
        base="/tmp/overworld_net.state",
        script=",".join("%s@%d" % (("Right", "Down", "Left", "Up")[i % 4], i)
                         for i in range(79)),
        # battlestart_ai4_rank0's four pokes PLUS T131's OPT-path lever
        # (asm/asm29.s:10216-10234): three one-shot frame-59 halfword writes
        # arming the roll's pre-chosen-record path -- oS2001c04_Unk_28 word
        # 0x02001c2c := 0x0001 (tst r1,r1 nonzero; high half already 0 RAM),
        # oS2001c04_OptCurBattleDataPtr 0x02001c30/0x02001c32 := 0x080af8a0
        # (battleSettingsList0 rec163 = 0x080aee70 + 163*0x10,
        # getBattleSettingsFromList0 asm/asm00_1.s:16048-16056). With Unk_28
        # set and GetPositiveSignedRNG bit0==0 the roll does
        # str OptCurBattleDataPtr -> GameState.CurBattleDataPtr 0x02001b9c
        # (asm29.s:10233): the family-A record is adopted with no root walk,
        # no rec7 gate, no count -- "fielded at all" for the scripted entry
        # type. The frame-60 EVENT_681 + iCurrFrame levers stay in BOTH arms
        # (they only feed the table path the OPT branch skips) so the sole
        # delta vs the battlestart_ai4_rank0 negative arm is the OPT lever.
        poke_at=("60:0x02001c16:0x2000", "60:0x02001c18:0",
                 "60:0x02001d58:0x0240", "60:0x0200a210:0x37a",
                 "59:0x02001c2c:0x0001", "59:0x02001c30:0xf8a0",
                 "59:0x02001c32:0x080a",
                 "59:0x020013f0:0xd7c1", "59:0x020013f2:0x7734"),
        # The seed halfwords are the admission half of the lever: the roll's
        # OPT branch also needs GetPositiveSignedRNG bit0==0 (asm29.s:10220-
        # 10222). Measured on the negative arm's own seed watch (T131 C1):
        # frame 60 holds exactly 3 draws and the natural chain's candidate
        # bits at the OPT position all read 1 (reject), so the seed at frame
        # 59 is set to 0x7734d7c1 -- for which the roll's ADJACENT draws
        # (threshold GetRNG asm29.s:10204 then OPT GetPositiveSignedRNG
        # :10220, no call between) satisfy (draw&0x1f)<12 (the CentralArea1
        # rate-5 threshold byte_8020C5C[0x85]=12) and bit0==0 (adopt) for
        # either draw ordering.
        frames=79,
        description="A battle's real frame 0 whose encounter roll adopted "
                    "family-A record rec163 0x080af8a0 (battleSettingsList0: "
                    "enemy_idx 0x16 = ai_index-4 rank v3 + two Gunner v3; "
                    "T131).",
        note="Recipe mechanism (T131): see the poke_at comment; measurements "
             "and the byte-equality check live in docs/worklog/T131.md and "
             "docs/coverage/entries.md. Negative arm = battlestart_ai4_rank0 "
             "(identical route, OPT words absent). Build time: ~0.2s.",
    ),
    State(
        name="emptyfield_start",
        path="/tmp/emptyfield_start.state",
        root=False,
        rom="/tmp/bn6f_sterile_emptynet.gba",  # STERILE_BASE + --empty-net-encounter (patch_sterile.py)
        base="/tmp/overworld_net.state",
        script=",".join("%s@%d" % (("Right", "Down", "Left", "Up")[i % 4], i)
                         for i in range(79)),  # cycled one per frame, docs/provenance.md#7aw's own shape
        poke_at=("60:0x02001c16:0x2000", "60:0x02001c18:0"),  # ONE roll attempt, at frame 60
        cheats=DELETE_ENEMY_3,  # kill whichever slot(s) spawn, every frame from load
        frames=79,
        description="A battle that spawned a real encounter and deleted it before frame 0 "
                     "(all 3 Mettaurs held at HP 0). Base for chip_ready_empty.",
        note="VERIFIED (ticket R1). Re-swept for the new power-on overworld_net base: "
             "from overworld_net.state, cycle Right/Down/Left/Up one per frame; one-shot "
             "poke at frame 60 opens encounter roll. Battle init triggers at frame 60 "
             "(SubsystemIndex 8); battle main loop at frame 76 (SubsystemIndex 12); "
             "SubsystemIndex 12 held throughout. eBGScrollCBCounters (0x02009690/0x02009694) "
             "read 0x0000/0x0000 at frame 79 (battle frame 0, docs/provenance.md#7aw) -- verified "
             "by --peek immediately at reload. All three enemy HP fields held at 0 "
             "throughout by DELETE_ENEMY_3 (peeks at 0x0203aaac, 0x0203ab84, 0x0203ac5c "
             "all read 0x0000). Build time: ~0.12s. Determinism: 40 frames from two builds "
             "diff to 0 pixels.",
    ),
    State(
        name="chip_ready_empty",
        path="/tmp/chip_ready_empty.state",
        root=False,
        rom="/tmp/bn6f_sterile_emptynet.gba",
        base="/tmp/emptyfield_start.state",
        script="A@130,Start@140,A@150",
        cheats=DELETE_ENEMY_3,
        pokes=("0x020008a0:0x019d", "0x02004c20:0x8062"),
        frames=280,
        description="AUDIT wave 3c/3d ticket step 3: emptyfield_start with a chip picked "
                     "through the chip window (which opens on its own) and in hand, ready to "
                     "test whether a chip fires with no enemy alive at all.",
        note="VERIFIED (ticket R1). From emptyfield_start.state, chip window opens on its "
             "own: BG3 content (--only-bg 3) starts slide-in at frame 91, reaches full 21230 px "
             "at frame 110, settles flat with nothing pressed. A@130 picks default cursor slot "
             "(chip id 5, Vulcan1); Start@140 moves cursor to OK; A@150 confirms and closes "
             "window (closed by frame 165, BG3 settles at 2300 px HUD background). Hand slot 1 "
             "(0x020349c2) carries chip id 5 (peek reads 0x0005). MegaMan CurState/CurAction "
             "(at 0x0203a9b8) transitions to (4, 8) idle at frame 278. State built at frames=280 "
             "shows (4, 8) at reload (verified by peek 0x0203a9b8 reading 0x0804). SubsystemIndex "
             "12 held throughout all 280+ frames. All three enemy HP held at 0. Build time: "
             "~0.32s. Determinism: 40 frames from two builds diff to 0 pixels.",
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
        description="ROOT AND LOST (2026-09-08) -- the recipe below is kept as the "
                     "record of a rebuild that is NOT equivalent (different reward "
                     "roll; see note). A battle already resolved into the RESULT window "
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
        name="buster_charge",
        path="/tmp/buster_charge.state",
        root=False,
        rom=STERILE,
        base=PAUSED,
        script="Start@10",
        cheats=DELETE_ENEMY,
        frames=60,
        description="T106: the charged-buster route -- the afterdissolve_0x0c state "
                    "under another name (SAME recipe: PAUSED resumed, Mettaur held at "
                    "HP 0, saved 60 frames in, banner sequencer in 0x0C). The ticket's "
                    "'scripted HOLD-A' is NOT in the recipe because it cannot be: in "
                    "0x0C nothing refreshes the alliance players' AIData from the "
                    "joypad mirror (F31b's measured wall), so a scripted hold never "
                    "reaches the pwrAtk handler. The hold is delivered per-capture "
                    "instead -- a per-frame --cheat on oAIData_JoypadHeld (0x020340a2 "
                    "= idle 0xfc00 | B) counts oAIData_PwrAtkCurChargeTime up from "
                    "the state's own frame 0, and the release (released word "
                    "0x020340a6) plus the shot kind (oAIData_BPwrAtk 0x02034087 = 0x06) "
                    "are one-shot pokes the frame before -- see the buster_charge row "
                    "in tools/harness.py.",
        note="RECIPE-IDENTICAL to afterdissolve_0x0c by design (same base/script/"
             "cheats/frames): the charge row's canon side needs exactly that scene, "
             "and the hold cannot be baked into the state (the 0x0C AIData wall "
             "above). Measured on this recipe's canon captures (T106): held from "
             "capture frame 0, the charge counter (0x0203409b, watched) reads 1 at "
             "frame 0 and caps at 100 from frame 99; a released-word poke at frame "
             "130 is the frame CurAction 0x0203a9b9 is written 0x10 (the charged "
             "attack, 130..159, back to 0x08 at 160).",
    ),
    State(
        name="afterdissolve_0x0c",
        path="/tmp/afterdissolve_0x0c.state",
        root=False,
        rom=STERILE,
        base=PAUSED,
        script="Start@10",
        cheats=DELETE_ENEMY,
        frames=60,
        description="TODO F5b step 2: PAUSED's battle resumed (Start@10) with the "
                    "Mettaur held at HP 0 (DELETE_ENEMY), saved 60 frames in -- past "
                    "the corpse's full dissolve (portrait box and corpse both 0, they "
                    "end at capture-relative 43-52 in the chip rows) and inside the "
                    "banner sequencer's RESULT countdown state 0x0C (dword_203CA70, "
                    "entered 36 frames after the enemy's death per F5, countdown 94 "
                    "frames, so 60 leaves ~80 frames of runway). The state where a chip press is "
                    "refused because NOTHING refreshes the alliance players' AIData "
                    "from the joypad mirror (0x08 does it via sub_8012DFC x2, 0x0C "
                    "never does) -- the base for the one-shot AIData JoypadPressed poke "
                    "test.",
        note="VERIFIED (this ticket). Peek at load: dword_203CA70 (0x0203ca70) reads "
             "0x000c (sequencer in the countdown state; byte 3 carries 0x04 from "
             "sub_80081A4's own init at 0x080081CA), byte_203CA74 reads 0 (countdown "
             "not expired), MegaMan CurState/CurAction (0x0203a9b8) reads 0x0804 "
             "(idle). Portrait box and corpse both gone at load (rendered frame 0 "
             "inspected; they end at capture-relative 43-52 and 60 > 52). Reloaded, "
             "the state holds sequencer 0x0C and idle for 90+ straight frames (byte "
             "watches on 0x0203ca70/0x0203a9b8, no change). MegaMan's AIDataPtr at "
             "0x0203aa08 reads 0x02034080 -- JoypadHeld 0x020340a2, JoypadPressed "
             "0x020340a4, Unk_44 0x020340c4; alliance-0 joypad mirror at 0x02036820 "
             "(pressed candidate halfword 0x02036822, sub_8012DFC asm00_2.s:8977). "
             "Determinism: 40 frames from two independent builds diff to 0 pixels. "
             "The F5b poke test on this state FIRES: --poke-at 3:0x020340a4:0x0001 "
             "(+ mirror 0x02036822) writes CurAction 0x08->0x14 at 0x0801169A "
             "(lr 0x0800FBF7, object_setAttack2 from sub_800FB54) the same frame, "
             "identical to the A@40-from-PAUSED control's fire chain.",
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
        name="pa_chipselect_state",
        path="/tmp/pa_chipselect.state",
        root=False,
        base=CHIPSELECT,
        patches=((0x5DDC0, 0x01),),  # provenance: derived -- T71's one-byte patch over /tmp/chipselect.state, swaps deck-slot-0 high byte 0x05 -> 0x01 so the window's first offer is Cannon-A (chip id 1, code A) instead of the original chip id 5. Verified byte-by-byte vs the source: this is the ONLY differing byte. The state file's EWRAM (file base 0x51000) is preserved verbatim from /tmp/chipselect.state, so the state byte at 0x020366F2 + 0x02036660 (selection/hand buffers) is canonical (chipselect.state itself was made by hand at a real BattleSettings + eBattleFolder read).
        description="T80 step 3: chipselect.state with hand-slot-0's high byte patched from 0x05 to 0x01 -- "
                     "the smallest patch that turns the offered-window's first row into Cannon-A while "
                     "leaving the rest of the deck (slots 1..4) and the live EWRAM untouched. Built by "
                     "copying /tmp/chipselect.state (the canonical chip-select menu root) + 1 byte; no "
                     "mgba_capture invocation (frames=None default). Used by harness.py's pa_recog row "
                     "(the new PA-recognition harness row) as its base state on BOTH sides -- canon with "
                     "the same /tmp/pa_chipselect.state, rust with the same + the T80 walk in src/custom.rs.",
        note="VERIFIED (T80): the only differing byte vs /tmp/chipselect.state is at file offset 0x5DDC0 "
             "(0x05 -> 0x01), reconfirmed by byte-by-byte diff. The RASTATE header + every other EWRAM "
             "byte matches /tmp/chipselect.state byte-for-byte, so the chipselect menu root's canonical "
             "0x020366F2 selection-byte stream and 0x02036660 hand-buffer are preserved.",
    ),
]

BY_NAME = {s.name: s for s in STATES}


def run_capture(state, out_dir, count, extra=()):
    cmd = [CAPTURE, state.rom, out_dir, str(count)]
    if state.base:
        cmd += ["--loadstate", state.base]
    if state.save:
        cmd += ["--loadsave", state.save]
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


def _apply_state_patches(state):
    """Copy `state.base` to `state.path` and apply `state.patches`
    byte-wise. Raises if either is missing or if a patch offset is
    out of range for the source. The base file's other contents are
    preserved verbatim, so a one-byte patch on a RASTATE keeps every
    mGBA header byte unchanged (T80)."""
    if not state.base or not state.patches:
        return False
    if not os.path.exists(state.base):
        raise SystemExit("%s source missing -- restore it first" % state.base)
    with open(state.base, "rb") as f:
        data = bytearray(f.read())
    for off, byte in state.patches:
        if off < 0 or off >= len(data):
            raise SystemExit("patch offset 0x%x outside source state (len 0x%x)"
                             % (off, len(data)))
        data[off] = byte & 0xff
    with open(state.path, "wb") as f:
        f.write(bytes(data))
    return True


def build(name):
    state = BY_NAME.get(name)
    if state is None:
        raise SystemExit("no such state %r -- see `states.py list`" % name)
    if state.root:
        raise SystemExit(
            "%s (%s) is a ROOT state -- refusing to overwrite it.\n%s"
            % (state.name, state.path, state.description))
    if _apply_state_patches(state):
        # A "copy + N-byte patch" recipe (T80 pa_chipselect_state): no ROM,
        # no script, no capture run -- the source state file IS the input.
        print("built %s -> %s (patches from %s)" % (state.name, state.path, state.base))
        return
    if not state.rom or state.frames is None:
        raise SystemExit("%s has no runnable recipe" % state.name)
    if not os.path.exists(CAPTURE):
        raise SystemExit("%s not found -- build it first (see docs/provenance.md#1)" % CAPTURE)
    if state.save and not os.path.exists(state.save):
        raise SystemExit("%s not found -- restore it first (see tools/restore_inputs.sh)" % state.save)
    scratch = "/tmp/states_py_scratch_%s" % state.name
    run_capture(state, scratch, state.frames, extra=["--savestate", state.path])
    subprocess.run(["rm", "-rf", scratch], check=True)
    print("built %s -> %s" % (state.name, state.path))


def list_states():
    print("%-14s %-6s %-32s %-14s %-7s %s" % ("name", "root", "path", "base", "frames", "description"))
    for s in STATES:
        base = os.path.basename(s.base) if s.base else "(save)" if s.save else "(cold boot)" if s.rom else "-"
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

#: The state-trace scenarios (T1, tools/trace.py): each maps a scenario name
#: to how to record it on both sides plus the alignment pairing. Row
#: scenarios reuse harness.py's own Sides verbatim (same ROM, state, script,
#: cheats) and the pairing oracle.py compares (canon_ref + rust_base, both
#: measured there, not here). battle_full is the whole arc from battle start
#: on both sides: resume, open the custom screen, pick/confirm Cannon, fire,
#: take the Mettaur's shockwave, win, dismiss RESULT.
#:
#: WHY battle_full starts from PAUSED, not BATTLESTART (measured 2026-09-14,
#: T1): a fresh BATTLESTART battle never fills the custom gauge (word
#: 0x020352A0 reads 0 for 800 frames, HUD mask never reaches the live
#: 0x4497, banner sequencer stays 0) with or without input, so the custom
#: screen cannot open there on canon; PAUSED is a live battle with a full
#: gauge (0x4000). "From BATTLE START" is the sequencer's own event: both
#: sides align on entering battle (canon sequencer 0x1c->0x08 at capture 11,
#: rust export-frame counter 0). Canon recipe (REAL rom -- STERILE never
#: concludes, so no win there): Start@10 resumes; L@40 opens custom (~48);
#: Start@70 goes to OK and A@80 confirms WITHOUT picking, so the hand keeps
#: its Cannon (A@70 picks Vulcan out of slot 0 -- measured); A@260 fires
#: after the close (~207); Cannon kills the 40HP Mettaur at 281 while its
#: shockwave lands at 280; sequencer enters 0x0C at 316 (DISSOLVE 35);
#: RESULT prompt blinks from ~417; A@440/A@470 dismisses. Rust recipe: a
#: 1-Mettaur fixture (killable default 40HP) with Cannon in hand and
#: FLAG_AUTO_FIRE at fire_frame 180, killing at table frame 262 -- 8 frames
#: off canon's ref-relative 270, the closest of the swept 90/180.
TRACE_SCENARIOS = {
    "mettaur": {
        "harness_row": "mettaur",
        "canon_ref": 140,  # provenance: peeked -- oracle.py mettaur's own compared canon frames 140..209
        "rust_base": 205,  # provenance: peeked -- oracle.py mettaur's own compared rust export frames 205..274
        "frames": 70,
        "mercy_addr": 0x02038514,  # provenance: peeked -- [0x0203a9b0+0x54]+0x24 on the PAUSED battle, T1 probe (119 on the hit frame)
    },
    "popup": {
        "harness_row": "popup",
        "canon_ref": 43,  # provenance: peeked -- oracle.py popup's own compared canon frames 43..122
        "rust_base": 122,  # provenance: peeked -- oracle.py popup's own compared rust export frame base 122
        "frames": 80,
        "mercy_addr": 0x02038514,  # provenance: peeked -- same PAUSED battle as mettaur, T1 probe
    },
    "result": {
        "harness_row": "result",
        "canon_ref": 21,  # provenance: peeked -- oracle.py result's own compared canon frames 21..60
        "rust_base": 21,  # provenance: peeked -- oracle.py result's own compared rust export frame base 21
        "frames": 40,
        "mercy_addr": 0x02038514,  # provenance: peeked -- same PAUSED battle family (RESULT_ARRIVAL), T1 probe
    },
    "battle_full": {
        "frames": 540,
        "canon_ref": 11,  # provenance: peeked -- first sequencer 0x08 on the recipe's own capture (0x1c->0x08 at 11), T1 probe
        "rust_base": 0,  # provenance: peeked -- rust export-frame counter at its battle start (counter = capture - 8, T1 probe)
        "mercy_addr": 0x02038514,  # provenance: peeked -- same PAUSED battle, T1 probe
        "canon": {
            "rom": REAL,
            "loadstate": PAUSED,
            "cheats": ("0x020349c2:0x01",),
            "script": "Start@10,L@40,Start@70,A@80,A@260,A@440,A@470",
        },
        "rust": {
            "fixture": {
                "enemies": 1, "enemy_kind": 0, "enemy_col": 5, "enemy_row": 2,
                "megaman_hp": 60, "megaman_col": 2, "megaman_row": 2,
                "hand": [1], "hand_count": 1,
                # T7r (2026-09-15): set gauge non-zero so Battle::new seeds the
                # gauge to GAUGE_FULL (src/battle.rs:1975 -- `f.gauge != 0 ?
                # GAUGE_FULL : 0`). The gauge-fill branch (src/battle.rs:2724)
                # then arms gauge_pause = GAUGE_PAUSE (60 frames) once intro
                # finishes; the countdown (src/battle.rs:2615-2655) opens the
                # chip window at frame ~124 (rust side), transitions
                # SEQ_08 -> SEQ_20 -> SEQ_24 -> SEQ_00 -> SEQ_04, and trips
                # T7q's seq.state gate in t1_player_entry (src/objects.rs:184)
                # so the k=179 group divergence drops. The "scripted-L"
                # cited in the ticket text is canon's PAUSED-state side
                # effect (sub_800A21C asm00_1.s:15203-15218): a full gauge
                # alone triggers the window opening; the L press itself is a
                # no-op in canon's fight state.
                "gauge": 1,
                "flags": 0x19,
                # T7r: also pre-pick the cannon and place the cursor on the OK
                # button (custom::OK = 0xa, src/custom.rs:106) so the scripted
                # A press below closes the window on its first try -- matches
                # canon's L@40 -> Start@70 -> A@80 progression (canon recipe
                # above). Without window_cursor=OK the A press would add
                # whatever slot cursor_at starts on, never close.
                "deck_count": 5, "deck": [5, 4, 71, 54, 1],
                "deck_codes": [3, 0xFF, 18, 0xFF, 0xFF],
                "window_pick_count": 1, "window_pick_slot": 4, "window_cursor": 0xa,
                "fire_frame": 180, "enemy_hp": 0,
            },
            # T7r: scripted A press at frame 170 (after the window opens at
            # ~k=124; window_pick_count pre-selects Cannon and OK is already
            # cursor_at so A closes the window immediately, src/custom.rs:
            # 1201-1210). Window close -> SEQ_00 (settle) -> SEQ_04 (banner
            # wait) -> SEQ_08 (fight) per the seq.match block at
            # src/battle.rs:3270-3277 (sub_800840C/sub_8008064 edges).
            "script": "A@170",
        },
    },
    # T105: the emotion row's own trace scenario -- rides the emotion_syn
    # Check's sides via harness_row (trace.py resolves it), so the state
    # fields over the row's window prove the Anger poke disturbs nothing
    # outside the face. The emotion byte itself (0x020340B4, the poked
    # AIData.Anger) and the face OBJ tiles are NOT in trace.py's fixed
    # CANON_WATCHES set -- they are measured with probe.py watch on both
    # sides, reported in docs/worklog/T105.md.
    "emotion_syn_full": {
        "harness_row": "emotion_syn",
        "canon_ref": 43,  # provenance: derived -- ALIGN_CHIP's own canon_ref, the row's pairing
        "rust_base": 122,  # provenance: derived -- ALIGN_CHIP's unique-zero offset, the popup scenario's own peeked base (same recipe family)
        "frames": 40,
        "mercy_addr": 0x02038514,  # provenance: peeked -- same PAUSED battle as mettaur/popup, T1 probe
    },
    # T122: the two new emotion rows' trace scenarios -- same shape as
    # emotion_syn_full (they ride the row's own sides via harness_row), so
    # the state fields over each new window can be diffed without touching
    # trace.py. The canon pokes differ per row (Unk_36 0x020340B6 for the
    # slot-4 face; the gate byte 0x0203528F for the skip arm) -- both live
    # outside trace.py's fixed CANON_WATCHES, measured per row in
    # docs/worklog/T122.md.
    "emotion_face_b_full": {
        "harness_row": "emotion_face_b",
        "canon_ref": 43,  # provenance: derived -- ALIGN_CHIP's own canon_ref, the row's pairing
        "rust_base": 122,  # provenance: derived -- ALIGN_CHIP's unique-zero offset, same recipe family as emotion_syn
        "frames": 40,
        "mercy_addr": 0x02038514,  # provenance: peeked -- same PAUSED battle as mettaur/popup, T1 probe
    },
    "emotion_skip_full": {
        "harness_row": "emotion_skip",
        "canon_ref": 43,  # provenance: derived -- ALIGN_CHIP's own canon_ref, the row's pairing
        "rust_base": 122,  # provenance: derived -- ALIGN_CHIP's unique-zero offset, same recipe family as emotion_syn
        "frames": 40,
        "mercy_addr": 0x02038514,  # provenance: peeked -- same PAUSED battle as mettaur/popup, T1 probe
    },
    # T135: the cross-body row's trace scenario -- same shape as the emotion
    # trio (it rides the row's own sides via harness_row). The poked byte
    # (0x0203ce2c, oNaviStats_Transformation) and the body palette bank are
    # outside trace.py's fixed CANON_WATCHES -- measured with probe.py watch
    # in docs/worklog/T135.md (OAM byte-identical, OBJ bank 0 row 0 -> row 2).
    "form_cross_full": {
        "harness_row": "form_cross",
        "canon_ref": 43,  # provenance: derived -- ALIGN_CHIP's own canon_ref, the row's pairing
        "rust_base": 122,  # provenance: derived -- ALIGN_CHIP's unique-zero offset, same recipe family as emotion_syn
        "frames": 40,
        "mercy_addr": 0x02038514,  # provenance: peeked -- same PAUSED battle as mettaur/popup, T1 probe
    },
    # T131: the scripted-entry (family-A) scenario. Canon side rides the
    # battlestart_scripted state (battlestart_ai4_rank0's route + the roll's
    # OPT-path pokes, asm/asm29.s:10216-10234). The settings word (0x02001b9c,
    # canon: oGameState_CurBattleDataPtr / BattleState+0x38, the chosen
    # BattleSettings record pointer) rides the scenario's own extra watch so
    # the 16-watch capture budget (CANON_WATCHES 15 + mercy) stays intact;
    # trace.py merges extra_watches into the same --watch mechanism.
    "battlestart_scripted": {
        "frames": 40,
        "canon_ref": 69,  # provenance: peeked -- populate frame on the ai4_rank0 route's own capture (T87; re-checked on T131's)
        "rust_base": 0,  # provenance: peeked -- rust export-frame counter at its battle start, the same contract as battle_full's (counter = capture - 8, T1 probe)
        "mercy_addr": 0x02038514,  # provenance: peeked -- same battle-object family as mettaur/popup, T1 probe
        "extra_watches": {"settings": (0x02001b9c, 4)},
        "drop_watches": ("panel_type", "panel_flags"),  # T130's raw-bin-only watches (never parsed); dropped here so 13 + mercy + settings <= 16
        "canon": {
            "rom": REAL,
            "loadstate": "/tmp/battlestart_scripted.state",
        },
        # T147: the rust side -- rec163's own slots as the descriptor names
        # them. T131 step 3 measured the fielded record (re-read on this
        # ticket's canon capture at built-frame 69): e1 NameID 0x0088 panel
        # (4,3) HP 0x00fa, e2 0x0088 (5,1) 0x00fa, e3 0x0016 (6,2) 0x00c8;
        # MegaMan (2,2) HP 100. The port's kind table has 0=Mettaur,
        # 1=Gunner (src/fixture.rs kind_of) and no ai4 family, so slot 2
        # fields a Gunner where canon fields ai4 0x16 -- that name/HP delta
        # is exactly what this scenario's map is supposed to surface, not a
        # fixture bug. enemy_hp names the FIRST enemy only (FIXTURE.md +32),
        # so e2/e3 ride the kind default -- HP is not a judged field here.
        "rust": {
            "fixture": {
                "enemies": 3,
                "enemy_kind": 0x15,  # provenance: derived -- packed 2 bits/slot (src/fixture.rs), slots 0/1/2 = kind 1 (Gunner); ai4 (0x16) has no kind value in the port
                "panel_col": [4, 5, 6],  # provenance: peeked -- rec163 formation 0x080b06a3 quads (T131 step 3; canon e-watches, built-frame 69, this ticket's capture)
                "panel_row": [3, 1, 2],  # provenance: peeked -- same quads
                "panel_override_mask": 0x07,  # provenance: derived -- F38h: all three slots take the override (the opening row's own mask)
                "megaman_hp": 100,  # provenance: peeked -- canon mm_hp 100 at built-frame 69 (this ticket's canon capture)
                "megaman_col": 2, "megaman_row": 2,  # provenance: peeked -- canon mm_panel (2,2) at built-frame 69
                "hand": [1], "hand_count": 1,
                # From here down: battle_full's standing fixture contract
                # (T7r) verbatim -- gauge=1 arms the custom-window chain at
                # frame ~124, outside this scenario's 40-frame entry window.
                "gauge": 1,
                "flags": 0x19,
                "deck_count": 5, "deck": [5, 4, 71, 54, 1],
                "deck_codes": [3, 0xFF, 18, 0xFF, 0xFF],
                "window_pick_count": 1, "window_pick_slot": 4, "window_cursor": 0xa,
                "fire_frame": 180, "enemy_hp": 250,  # provenance: peeked -- canon e1_hp 0x00fa (GunnerEnemyStruct2_8112B9C row 3, T131 step 3); FIRST enemy only (FIXTURE.md +32)
            },
            "script": "A@170",
        },
    },
}
