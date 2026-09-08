#!/usr/bin/env python3
"""Run EVERY parity check this project has, in one command.

usage: python3 regress.py [--only NAME,...] [--list]

The chip scoreboard covers 43 chip animations; everything else -- the battle
screen's tiles, a whole frame with sprites, the chip window, the preview card,
the RESULT window, the navi's warp, the buster, a chip use -- was being run by
hand, one fixture at a time, which is how a regression in one of them survives
a session spent on another. Each check below rebuilds its own ROM, captures
both sides, aligns them the way that fixture is aligned, and prints the number
the fixture is judged on against the number it should be.

The last check is not a comparison at all: it runs the full battle under a long
input script and asserts it does not crash, which is the one thing a fixture
with two objects on an empty arena can never tell you.

A check's `want` is the measured truth as of the last time it was verified,
not an aspiration: several are non-zero because that residue is understood and
recorded in TRANSFER.md. The exit status is non-zero if any check comes out
WORSE than its `want`; a check that comes out better prints BETTER and the
number should be written down here.

Needs /tmp/mgba_capture, the real ROM and the save states, which are never
committed. tools/patch_sterile.py must have been run:

    python3 tools/patch_sterile.py /tmp/bn6f_real.gba /tmp/bn6f_sterile.gba
"""

import argparse
import os
import subprocess
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chip_compare as cc  # noqa: E402  (needs the path set first)

CAPTURE = "/tmp/mgba_capture"
REAL = "/tmp/bn6f_real.gba"
STERILE = "/tmp/bn6f_sterile.gba"
PAUSED = "/tmp/pausedwithcannon.state"
CHIPSELECT = "/tmp/chipselect.state"
NOENEMY = "/tmp/noenemy2.state"
#: A save state at a battle's FIRST frame -- its scroll counters read 0/0.
BATTLESTART = "/tmp/battlestart.state"
#: Keeping the capture's Mettaur alive, which most fixtures want.
ALIVE = ["--cheat", "0x0203ab84:0xffff", "--cheat", "0x0203ab86:0xffff"]


def capture(rom, out, count, *args):
    subprocess.run(["rm", "-rf", out], check=True)
    subprocess.run([CAPTURE, rom, out, str(count), *args],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # AND CHECK IT ACTUALLY WROTE THEM. A short capture does not announce
    # itself: the frames that exist compare normally and the ones that do not
    # either raise a FileNotFoundError deep in a check or, worse, never get
    # asked for. Twice on 2026-09-07 a suite run under load reported checks
    # WORSE -- once `chips` 10 of 43 off, once `opening` missing frame 148 --
    # and neither reproduced on a quiet re-run. A count is cheap; a day spent
    # chasing a regression that was a truncated capture is not.
    got = len([f for f in os.listdir(out) if f.endswith(".rgb")])
    if got != count:
        raise SystemExit(
            "capture wrote %d of %d frames to %s -- the box was probably busy; "
            "re-run it alone before believing any number from this run" % (got, count, out))


def build(features, rom):
    subprocess.run(["cargo", "build", "--release", "--features", features], cwd=ROOT,
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    # cc.target_dir() asks cargo where it actually built, rather than assuming
    # ROOT/target -- see its docstring; a private CARGO_TARGET_DIR used to make
    # this pack a stale ELF and report numbers for a different build entirely.
    elf = os.path.join(cc.target_dir(), "thumbv4t-none-eabi/release/bn")
    if not os.path.exists(elf):
        raise SystemExit("cargo built no %s -- is CARGO_TARGET_DIR pointing somewhere odd?" % elf)
    subprocess.run(["python3", os.path.join(ROOT, "tools", "gbafix.py"), elf, rom],
                   check=True, stdout=subprocess.DEVNULL)


def diff(a, fa, b, fb, box):
    x0, y0, x1, y1 = box
    p, q = cc.frame(a, fa).load(), cc.frame(b, fb).load()
    return sum(1 for y in range(y0, y1) for x in range(x0, x1) if p[x, y] != q[x, y])


def best(a, fa, b, frames, box):
    """The smallest difference over a window of candidate rust frames."""
    return min(diff(a, fa, b, f, box) for f in frames)


def held(key, first, n):
    """A key script that holds `key` for `n` frames from `first`."""
    return ",".join("%s@%d" % (key, first + j) for j in range(n))


# --------------------------------------------------------------------------


def check_chips():
    out = subprocess.run(["python3", os.path.join(ROOT, "tools", "scoreboard.py")],
                         cwd=ROOT, capture_output=True, text=True)
    line = [l for l in out.stdout.splitlines() if l.endswith("exact")][-1]
    exact, total = int(line.split()[0]), int(line.split()[2])
    bad = [l.split()[0] for l in out.stdout.splitlines() if l and "EXACT" not in l and l[0] == "d"]
    return total - exact, "%d of %d exact, off: %s" % (exact, total, " ".join(bad))


#: The backdrop (BG1) scrolls under a per-frame counter pair, eBGScrollCBCounters
#: (0x02009690/0x02009694 in EWRAM, decremented 8 and 4 a frame -- see
#: BGScrollCB_BG1Diagonal3to2Scroll, reference/bn6f/asm/asm00_0.s:3272-3288) that is
#: zeroed only once, at battle init (sub_8080D90, asm21.s:2, called from
#: initBattleStructsAndVram_80071D4, asm00_1.s ~5147). So the phase is "frames since
#: this battle started" -- exactly what this build already counts from (backdrop.rs's
#: `ticks`) -- but PAUSED is a save state grabbed mid-battle, and pausing does not
#: reset or expose the counter: peeking it at load (`--peek 0x02009690/0x02009694`)
#: reads -63128/-31564, i.e. 7891 real frames already elapsed before the save, a
#: number nothing else in the state or in this build can reproduce.
#: /tmp/battlestart.state DOES read 0/0, so a known origin now exists -- but anchoring
#: this check on it does not produce an exact match anywhere in its usable window
#: (TRANSFER 7bi); the best the backdrop band alone reaches there is 86 px. This
#: fixture stays.
#: What IS available: both sides are deterministic replays (fixed scripts, no live
#: input), so a rust frame that reproduces the real ROM's phase does so every run.
#: Measured once by sweeping the old 340..400 window: 392 is the only exact hit --
#: 391 already differs by 110 px and 393 by 3295 (VOFS ticks over on a 4-frame
#: cadence), so it is not a coincidental near-match. Pinning it turns this from "does
#: some frame in a 60-frame window match" into "does frame 392 match", which a real
#: phase or rate regression will fail, and a coincidental one in the old range would
#: not have.
#: AND 392 IS NO LONGER A LONE COINCIDENCE. The backdrop's visual period is 896
#: frames -- not the 1024 the register modulus suggests, because the motif repeats
#: within the map at x+128 -- and `diff(real 43, rust 392 + k*896)` is 0 for k = 0..8,
#: out to rust frame 7560. Zero drift over 7168 elapsed frames also says our scroll
#: RATE matches the real ROM's exactly, which is the thing a single matching frame
#: could never have shown on its own.
#: THE ALIGNMENT IS DERIVED NOW, NOT SWEPT, and the check no longer covers the
#: HUD. Both changes come from 7bl.
#: The frame: the fixture now SEEDS its backdrop with the save state's own
#: phase (Backdrop::seed, src/backdrop.rs), so the two sides share an origin
#: and the match comes back close to boot instead of 1798 frames in -- rust
#: 435 against real 44, exact. Before the seed the only alignment was where the
#: art's 192-frame cycle and the scroll's 1024-frame one came back together,
#: every LCM = 3072 frames, which made this check capture 1800 frames to find
#: one. A five-frame window absorbs the boot-length drift fat LTO gives any
#: source change.
#: Real frame 44, not 43: our frame matches 44 to the pixel and differs from 43
#: by 136. The old comparison against 43 was a frame out and nobody could see
#: it while a wrong art model was cancelling the error.
#: The BOX excludes the HUD strip, and that is not a softening. The old check
#: compared the whole screen at one frame and read 0 for weeks while hiding a
#: wrong art schedule, a scroll rounding error AND an unmodelled gauge
#: animation -- three defects that happened to cancel there. The gauge is a
#: separate, named, still-open defect (TODO A8) and has its own check below, so
#: nothing is hidden by the split: this one says the BACKGROUNDS are exact and
#: `gauge` says the HUD is not.
TILES_REAL_FRAME = 44
TILES_RUST_FRAMES = range(433, 438)
TILES_BOX = (0, 24, 240, 160)


def check_tiles():
    """Backgrounds, whole screen below the HUD, at a derived alignment."""
    build("demo-hudmatch", cc.scratch("rg_hud.gba"))
    capture(REAL, cc.scratch("rg_tr"), 60, "--loadstate", PAUSED, "--script", "Start@10",
            "--disable-obj")
    capture(cc.scratch("rg_hud.gba"), cc.scratch("rg_tu"), max(TILES_RUST_FRAMES) + 1,
            "--disable-obj")
    scores = [(diff(cc.scratch("rg_tr"), TILES_REAL_FRAME, cc.scratch("rg_tu"), f, TILES_BOX), f)
              for f in TILES_RUST_FRAMES]
    got, at = min(scores)
    return got, "backgrounds below the HUD, best of %d..%d (at %d)" % (
        min(TILES_RUST_FRAMES), max(TILES_RUST_FRAMES), at)


#: The HUD at the same alignment, which is where the gauge's unmodelled flow
#: lives. TODO A8: the bar is full throughout and its four-state cycle is right,
#: but early on its stripes SHIFT position as well as cycling and this build
#: does not do that. 470 is a defect with a number, not a tolerance.
def check_gauge():
    """The HUD strip at `tiles`' alignment -- the gauge's flow (TODO A8)."""
    build("demo-hudmatch", cc.scratch("rg_hud.gba"))
    capture(REAL, cc.scratch("rg_gr"), 60, "--loadstate", PAUSED, "--script", "Start@10",
            "--disable-obj")
    capture(cc.scratch("rg_hud.gba"), cc.scratch("rg_gu"), max(TILES_RUST_FRAMES) + 1,
            "--disable-obj")
    scores = [(diff(cc.scratch("rg_gr"), TILES_REAL_FRAME, cc.scratch("rg_gu"), f,
                    (0, 0, 240, 24)), f) for f in TILES_RUST_FRAMES]
    got, at = min(scores)
    subprocess.run(["rm", "-rf", cc.scratch("rg_gr"), cc.scratch("rg_gu")], check=True)
    return got, "HUD strip at frame %d" % at


def check_field():
    build("demo-field", cc.scratch("rg_field.gba"))
    capture(STERILE, cc.scratch("rg_fr"), 100, "--loadstate", PAUSED, *ALIVE,
            "--disable-bg", "--script", "Start@10")
    capture(cc.scratch("rg_field.gba"), cc.scratch("rg_fu"), 400, "--disable-bg")
    return best(cc.scratch("rg_fr"), 90, cc.scratch("rg_fu"), range(190, 240), (0, 0, 240, 160)), "whole screen"


#: SIXTEEN FRAMES, NOT ONE (TODO D4). This compared a single frame and read 0,
#: and a single frame could not tell lag 181 from lag 182 -- both are exact at
#: frame 59. Over sixteen consecutive frames 181 is 184 px (the bracket's blink
#: toggling one frame out, 92 px a toggle, twice) and 182 is 0. The check was
#: quietly on the wrong alignment and nothing could see it.
#: The lag is searched rather than fixed, for the reason recorded on `mettaur`
#: and `wave`: this fixture's rust side boots from reset while its real side
#: loads a save state, so the offset moves with any source change.
WINDOW_FRAMES = 16
WINDOW_LAGS = range(174, 190)


def check_window():
    build("demo-custmatch", cc.scratch("rg_cm.gba"))
    capture(REAL, cc.scratch("rg_wr"), 60 + WINDOW_FRAMES, "--loadstate", CHIPSELECT)
    capture(cc.scratch("rg_cm.gba"), cc.scratch("rg_wu"), 60 + max(WINDOW_LAGS) + WINDOW_FRAMES)

    def score(lag):
        return [diff(cc.scratch("rg_wr"), 55 + k, cc.scratch("rg_wu"), 55 + lag + k,
                     (0, 0, 112, 160)) for k in range(WINDOW_FRAMES)]

    total, lag = by_lag(WINDOW_LAGS, score)
    return total, "%d frames of the window, lag %d" % (WINDOW_FRAMES, lag)


#: Sixteen frames rather than one, and a searched lag -- same reasons as
#: `check_window` above (TODO D4). The window is the sixteen frames ending at
#: real 159, which is where the fifth card has settled.
CARD_FRAMES = 16
CARD_LAGS = range(74, 96)


def check_card():
    build("demo-cardname", cc.scratch("rg_cn.gba"))
    capture(REAL, cc.scratch("rg_kr"), 160, "--loadstate", CHIPSELECT,
            "--script", ",".join(held("Left", 20 + 30 * k, 6) for k in range(5)))
    capture(cc.scratch("rg_cn.gba"), cc.scratch("rg_ku"), 160 + max(CARD_LAGS) + 1)

    def score(lag):
        return [diff(cc.scratch("rg_kr"), 159 - CARD_FRAMES + 1 + k, cc.scratch("rg_ku"),
                     159 - CARD_FRAMES + 1 + lag + k, (0, 0, 112, 160))
                for k in range(CARD_FRAMES)]

    total, lag = by_lag(CARD_LAGS, score)
    return total, "%d frames of the card, lag %d" % (CARD_FRAMES, lag)


#: The cursor walk: five Left presses, six frames each, thirty apart. The real
#: side comes from the chip-select save state, where the window is already open
#: with the cursor on OK; `demo-custmatch` is that same state, so both sides can
#: be driven by the SAME script and compared frame for frame -- which
#: `check_card` cannot do, because `demo-cardname` places its cursor statically
#: and never walks at all.
CURSOR_PRESS = 250
CURSOR_LAG = 230
#: This wanted 3152 for a long time, all of it THE BRACKET'S BLINK being one
#: frame out, and the entry here used to say the two sides had no shared origin
#: for it and could only ever coincide. That was wrong, and it was wrong in the
#: way this project keeps being wrong: a real mechanism was written off as
#: unknowable before anybody read it.
#: The blink is `(counter >> 3) & 1` off a counter at 0x02036500 that state 4 of
#: the window's own state machine increments once a frame (asm03_0.s:4801-4804,
#: 1163-1165). It is window-relative on BOTH sides, so an origin does exist --
#: the save state's value is simply not zero. Peeked, it is 0x647; measured off
#: the toggles, the real side's drawn counter at capture frame f is 1606 + f.
#: With both sides static the phase offset came out at exactly +1 frame, and the
#: cause was ours, not the fixture's: the slide-in fell through to a separate
#: match arm to reach `Phase::Open`, spending a frame the real ROM does not
#: (asm03_0.s:1011-1012 advances to state 4 in the same call that zeroes the
#: counter). Invisible in every other check, because the window looks the same
#: during that frame -- only the blink counts from it. Fixed in src/custom.rs.
#: The want is 0. Anything else is a real regression.


def check_cursor():
    """Every frame of a five-step cursor walk, both sides on one script."""
    build("demo-custmatch", cc.scratch("rg_cw.gba"))
    capture(REAL, cc.scratch("rg_wr2"), 200, "--loadstate", CHIPSELECT,
            "--script", ",".join(held("Left", 20 + 30 * k, 6) for k in range(5)))
    capture(cc.scratch("rg_cw.gba"), cc.scratch("rg_wu2"), 420, "--script",
            ",".join(held("Left", CURSOR_PRESS + 30 * k, 6) for k in range(5)))
    total = sum(diff(cc.scratch("rg_wr2"), 15 + k, cc.scratch("rg_wu2"), 15 + CURSOR_LAG + k, (0, 0, 112, 160))
                for k in range(170))
    subprocess.run(["rm", "-rf", cc.scratch("rg_wr2"), cc.scratch("rg_wu2")], check=True)
    return total, "170 frames of a five-step walk"


#: THE BATTLE'S OPENING, and it exists because the suite was flattering itself.
#: Every other check compares a fixture built for it; nothing compared the thing
#: a player actually sees first. `demo-open` fields the same three Mettaurs as
#: /tmp/battlestart.state and had NO check at all, so an 85-px HUD difference and
#: a backdrop that drifts to 2700 px sat outside the suite entirely while it
#: reported fifteen zeros.
#: The box is the HUD strip and the backdrop band, stopping short of the field:
#: the three viruses materialise on their own schedule and diverge above real
#: frame 190, which is a separate question from this one.
#: THE WANT IS NOT ZERO AND THAT IS NOT ACCEPTABLE, it is just honest. It is
#: TODO A7: the backdrop animates as well as scrolls, and our two clocks are
#: locked to each other while the real ROM's are not -- the scroll aligns at lag
#: 7 and the art at lag 0. Drive this to 0; do not adjust the want to suit a
#: build.
#: EVERY FRAME, AND A SEARCHED LAG. This check first sampled `range(120, 160, 4)`
#: and read 0 -- and every 4th frame was exactly the set that matched, because
#: the backdrop's scroll moves a pixel every 2 frames across and every 4 down,
#: so a rounding error shows on 3 frames in 4 and hides on the fourth. Measured
#: at the time: 120 -> 0, 121 -> 2433, 122 -> 2433, 123 -> 0, 124 -> 0. A check
#: I wrote myself, reporting zero while the picture was a pixel out most of the
#: time. Sampling a periodic signal on its own period measures nothing.
OPENING_LAGS = range(3, 12)
OPENING_BOX = (0, 0, 240, 60)


def check_opening():
    """The first 40 frames after a battle's field appears, HUD and backdrop."""
    build("demo-open", cc.scratch("rg_open.gba"))
    capture(REAL, cc.scratch("rg_opr"), 200, "--loadstate", BATTLESTART, "--disable-obj")
    capture(cc.scratch("rg_open.gba"), cc.scratch("rg_opu"), 210, "--disable-obj")
    frames = range(120, 160)

    def score(lag):
        return [diff(cc.scratch("rg_opr"), f, cc.scratch("rg_opu"), f + lag, OPENING_BOX)
                for f in frames]

    total, lag = by_lag(OPENING_LAGS, score)
    worst = max(score(lag))
    subprocess.run(["rm", "-rf", cc.scratch("rg_opr"), cc.scratch("rg_opu")], check=True)
    return total, "%d frames of the opening, lag %d, worst %d px" % (len(frames), lag, worst)


#: Sixteen frames rather than one, and a searched lag (TODO D4) -- BUT THIS ONE
#: IS STILL EFFECTIVELY A SINGLE FRAME AND SHOULD NOT BE READ AS MORE.
#: Measured: over real frames 24..39 the compared region does not change at all,
#: every consecutive difference is 0. So the sixteen frames are the same picture
#: sixteen times and the lag search has nothing to bite on -- it reports the
#: bottom of whatever range it is given, which is why widening the range moved
#: the reported lag from 105 to 95 without changing the result.
#: What would actually strengthen this: a window covering the RESULT screen
#: ARRIVING -- its slide-in and the badge appearing -- rather than sixteen
#: frames after everything has settled. That needs the real side captured from
#: before the window opens, which this fixture's save state does not give.
RESULT_FRAMES = 16
RESULT_LAGS = range(95, 140)


def check_result():
    build("demo-resultmatch", cc.scratch("rg_res.gba"))
    capture(REAL, cc.scratch("rg_rr"), 40, "--loadstate", NOENEMY)
    capture(cc.scratch("rg_res.gba"), cc.scratch("rg_ru"), 40 + max(RESULT_LAGS) + 1)

    def score(lag):
        return [diff(cc.scratch("rg_rr"), 39 - RESULT_FRAMES + 1 + k, cc.scratch("rg_ru"),
                     39 - RESULT_FRAMES + 1 + lag + k, (26, 24, 215, 155))
                for k in range(RESULT_FRAMES)]

    total, lag = by_lag(RESULT_LAGS, score)
    return total, "%d frames of the window and badge, lag %d" % (RESULT_FRAMES, lag)


def check_warp():
    build("demo-field", cc.scratch("rg_field.gba"))
    capture(STERILE, cc.scratch("rg_mr"), 120, "--loadstate", PAUSED, *ALIVE,
            "--zero", "0x6016E00:1280", "--disable-bg",
            "--script", "Start@10," + ",".join(
                held(k, at, 3) for k, at in (("Right", 60), ("Down", 80), ("Left", 100), ("Up", 120))))
    capture(cc.scratch("rg_field.gba"), cc.scratch("rg_mu"), 300, "--disable-bg",
            "--script", ",".join(
                held(k, at, 3) for k, at in (("Right", 130), ("Down", 150), ("Left", 170), ("Up", 190))))
    blue = (0, 132, 222)

    def navi(d, f):
        px = cc.frame(d, f).load()
        pts = [(x, y) for y in range(50, 150) for x in range(240) if px[x, y] == blue]
        return (min(p[0] for p in pts), min(p[1] for p in pts)) if pts else None

    same = sum(1 for k in range(30) if navi(cc.scratch("rg_mr"), 60 + k) == navi(cc.scratch("rg_mu"), 130 + k))
    return 30 - same, "%d of 30 navi positions" % same


#: THE SUITE HEARS NOTHING WITHOUT THIS. Two sounds are implemented -- the
#: buster's PSG fire blip and its DirectSound hit sample -- and until now
#: nothing measured either, so the hit's known 13% loudness error sat outside
#: every check exactly the way `demo-open` once did.
#: The method is TRANSFER 7ax's: the battle's own noise never stops, so each
#: side is captured TWICE, once with the press and once without, and the
#: residual is taken sample by sample before the RMS. Frames are counted from
#: the press, and the score is the summed absolute difference between the two
#: sides' residual envelopes over the sample's body.
#: The want is 37223 and that is a DEFECT WITH A NUMBER, not a tolerance. Peak
#: residual RMS is 4074 on the real ROM against 4603 here -- our hit is about
#: 13% loud, which is exactly what the session that wired the sound up
#: measured (4074 against 4605).
#: THIS CHECK WAS WRONG TWICE BEFORE IT AGREED WITH THAT, and both ways are
#: worth keeping because both look like results:
#:   1. Not soloing the FIFOs measured the whole mix, and the buster's PSG FIRE
#:      blip has its own residual in the same frames. That inflated the REAL
#:      peak to 4864 and made our hit look 5% QUIET -- the wrong SIGN.
#:   2. Then the window, frames 14..29, turned out to be the same samples the
#:      other measurement called +19..+34: it began five frames after the onset
#:      and reported a mid-decay value as the peak, 3609 instead of 4074 -- the
#:      wrong MAGNITUDE.
#: A control-subtracted envelope measures one sound only if that sound is alone
#: on the captured channels, and only if the window contains its onset.
#: The window has to CONTAIN the onset, and the first version did not. Its
#: frames 14..29 turned out to be the same samples the wiring measurement called
#: +19..+34 -- an offset in what "the press frame" means between the two -- so
#: it started five frames after the rise and reported a mid-decay value as the
#: peak. Widened to cover the whole event on both sides: the sample's body is
#: about 11 frames (1881 samples at 10512 Hz) and this holds 24.
AUDIO_FRAMES = range(8, 32)


def _envelope(rom, press, extra, *args):
    """Per-frame residual RMS after `press`, control-subtracted.

    `args` carries whatever the side needs to be IN a battle at all -- the
    real ROM wants its save state and the cheats that keep the enemy alive.
    Leaving them out captures a ROM that never reaches a fight, whose envelope
    is a flat zero and looks like a missing sound rather than a broken setup.
    """
    import math
    import struct
    out = []
    for tag, script in (("hit", "%s,B@%d,B@%d" % (extra, press, press + 1)),
                        ("ctl", extra)):
        d = cc.scratch("rg_aud_" + tag)
        subprocess.run(["rm", "-rf", d], check=True)
        subprocess.run([CAPTURE, rom, cc.scratch("rg_aud_frames"), str(press + 40),
                        *args, "--disable-bg", "--script", script.strip(","),
                        # SOLO THE FIFOs. The hit is a DirectSound sample and
                        # lives on channels 4 and 5 (the harness's numbering,
                        # 0-3 being the PSG). Without this the mix also carries
                        # the buster's PSG FIRE blip, whose own residual lands
                        # in the same frames and moves the measured peak.
                        "--audio-channel", "4", "--audio-channel", "5",
                        "--dump-audio", d],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        out.append(d)
    hit, ctl = out
    env = []
    for k in AUDIO_FRAMES:
        f = press + k
        a = open(os.path.join(hit, "frame.%05d.pcm" % f), "rb").read()
        b = open(os.path.join(ctl, "frame.%05d.pcm" % f), "rb").read()
        n = min(len(a), len(b)) // 2
        va = struct.unpack("<%dh" % n, a[:n * 2])
        vb = struct.unpack("<%dh" % n, b[:n * 2])
        env.append(math.sqrt(sum((x - y) ** 2 for x, y in zip(va, vb)) / max(n, 1)))
    for d in (hit, ctl, cc.scratch("rg_aud_frames")):
        subprocess.run(["rm", "-rf", d], check=True)
    return env


def check_audio():
    """The buster's hit, real against ours, as a residual envelope."""
    build("demo-field", cc.scratch("rg_field.gba"))
    real = _envelope(STERILE, 60, "Start@10", "--loadstate", PAUSED, *ALIVE,
                     "--zero", "0x6016E00:1280")
    ours = _envelope(cc.scratch("rg_field.gba"), 130, "")
    total = int(sum(abs(a - b) for a, b in zip(real, ours)))
    peak_r, peak_o = int(max(real)), int(max(ours))
    return total, "%d frames after the hit, peak real %d vs ours %d" % (
        len(real), peak_r, peak_o)


def check_buster():
    build("demo-field", cc.scratch("rg_field.gba"))
    capture(STERILE, cc.scratch("rg_br"), 100, "--loadstate", PAUSED, *ALIVE,
            "--zero", "0x6016E00:1280", "--disable-bg", "--script", "Start@10,B@60,B@61")
    capture(cc.scratch("rg_field.gba"), cc.scratch("rg_bu"), 200, "--disable-bg", "--script", "B@130,B@131")
    return sum(diff(cc.scratch("rg_br"), 60 + k, cc.scratch("rg_bu"), 130 + k, (0, 50, 120, 150))
               for k in range(32)), "navi half, 32 frames"


#: Direction cycles for the rollup check. ONE script is not enough: the walk
#: it produces decides which enemies the navi meets and how long it survives,
#: and the two crashes this check exists for came out of two different walks
#: -- one 362 frames into a fight, the other at a chip window that only opens
#: if the navi is still alive when the gauge fills, some 1650 frames in.
ROLLUP_WALKS = [
    ["Up", "Left", "Down", "Left", "Up", "Right", "Down", "Left", "Right", "Up"],
    ["Up", "Left", "Down", "Left", "Up", "Right", "Down", "Left"],
    ["Right", "Right", "Up", "Down", "Left", "Up", "Right", "Down", "Down"],
]
ROLLUP_FRAMES = 2600


#: The five family-0x15 chips and the box the popup lives in. The scoreboard
#: already runs these chips, but its window starts at y=40 and the popup runs
#: y=32..48, so it only ever sees the bottom half. This box takes the whole
#: strip bar its top two rows, which the real ROM's HP box overlaps at x<46.
POPUP_CHIPS = [("demo-areagrab", "a3"), ("demo-invisibl", "b1"), ("demo-barrier", "b2"),
               ("demo-barr100", "b3"), ("demo-barr200", "b4")]
POPUP_BOX = "24,34,100,52"


def check_popup():
    """The chip-name popup, over its whole life, for every chip that has one."""
    total, notes = 0, []
    for feature, chip in POPUP_CHIPS:
        out = subprocess.run(
            ["python3", os.path.join(ROOT, "tools", "chip_compare.py"), chip, feature,
             "--frames", "77", "--rust-start", "123", "--hide-enemy", "--no-banner-zero",
             "--box", POPUP_BOX],
            cwd=ROOT, capture_output=True, text=True)
        line = [l for l in out.stdout.splitlines() if l.startswith("mean ")]
        if not line:
            notes.append("%s FAILED" % feature)
            total += 1
            continue
        mean = float(line[0].split()[1])
        if mean:
            notes.append("%s %.1f" % (feature, mean))
        total += int(mean * 77)
    return total, "; ".join(notes) or "%d chips, whole popup" % len(POPUP_CHIPS)


def check_banner():
    """The ENEMY DELETED banner: art, palette, position and roll-out.

    The real side is the sterile arena's own save state with the enemy's HP
    forced to zero and Start pressed at frame 10, which puts the banner up on
    frames 49..106; `demo-banner` puts this build's up on its clock's 100th
    frame, which is capture frame 132. The box stops at x=145 because the
    deleted enemy's remnant dissolves to the right of it for a hundred frames.
    """
    build("demo-sterile,demo-banner", cc.scratch("rg_ban.gba"))
    # The sterile ROM has the banner patched OUT, which is what every chip
    # comparison needs and exactly what this one cannot have.
    subprocess.run(["python3", os.path.join(ROOT, "tools", "patch_sterile.py"),
                    REAL, "/tmp/bn6f_banner.gba", "--keep-banner"],
                   check=True, stdout=subprocess.DEVNULL)
    capture("/tmp/bn6f_banner.gba", cc.scratch("rg_banr"), 120, "--loadstate", PAUSED,
            "--cheat", "0x0203ab84:0", "--cheat", "0x0203ab86:0",
            "--disable-bg", "--script", "Start@10")
    capture(cc.scratch("rg_ban.gba"), cc.scratch("rg_banu"), 220)
    box = (40, 56, 145, 88)
    return (sum(diff(cc.scratch("rg_banr"), 49 + k, cc.scratch("rg_banu"), 132 + k, box) for k in range(58)),
            "58 frames of the banner")


def check_rollup():
    """The full battle, under several long input scripts, must not crash.

    Every other check here puts one or two objects on an empty arena, which is
    why none of them caught the game running out of object palette banks 362
    frames into a real fight (7an). agb's crash screen is a white page, and a
    battle frame never is, so counting frames that are more than half pure
    white finds it without knowing what the panic said.
    """
    build("default", cc.scratch("rg_roll.gba"))
    last = ROLLUP_FRAMES - 50
    total, notes = 0, []
    for w, keys in enumerate(ROLLUP_WALKS):
        script = [held(keys[i % len(keys)], at, 3) for i, at in enumerate(range(60, last, 19))]
        script += [held("B", at, 2) for at in range(70, last, 11)]
        script += [held("A", at, 2) for at in range(100, last, 37)]
        out = cc.scratch("rg_rollcap%d" % w)
        capture(cc.scratch("rg_roll.gba"), out, ROLLUP_FRAMES, "--script", ",".join(script))

        def crashed(i):
            px = cc.frame(out, i).load()
            sampled = [(x, y) for y in range(0, 160, 2) for x in range(0, 240, 2)]
            white = sum(1 for x, y in sampled if px[x, y] == (255, 255, 255))
            return white > len(sampled) // 2
        # A WHITE PAGE IS NOT ENOUGH ANY MORE. agb's crash screen is white, and
        # so is the first 71 frames of every battle this build opens (TRANSFER
        # 7ba) -- and the rollup loops battles, so it shows several. What tells
        # them apart is that a crash NEVER CLEARS: the screen is still white
        # 150 frames later, where an intro is long gone. So a frame only counts
        # if it is white and so is the one 150 frames after it.
        LINGER = 150
        bad = [i for i in range(60, ROLLUP_FRAMES - LINGER, 5)
               if crashed(i) and crashed(i + LINGER)]
        # Three walks of 2600 frames is about 1.2 GB of raw captures. Leaving
        # them behind is how /tmp reached 37 GB and the box ran out of swap.
        subprocess.run(["rm", "-rf", out], check=True)
        total += len(bad)
        if bad:
            notes.append("walk %d white by frame %d" % (w, bad[0]))
    return total, "; ".join(notes) or "no crash, %d walks of %d frames" % (
        len(ROLLUP_WALKS), ROLLUP_FRAMES)


def check_chip_use():
    build("demo-field", cc.scratch("rg_field.gba"))
    capture(STERILE, cc.scratch("rg_ar"), 100, "--loadstate", PAUSED, *ALIVE,
            "--zero", "0x6016E00:1280", "--disable-bg", "--script", "Start@10,A@60,A@61")
    capture(cc.scratch("rg_field.gba"), cc.scratch("rg_au"), 200, "--disable-bg", "--script", "A@130,A@131")
    return sum(diff(cc.scratch("rg_ar"), 60 + k, cc.scratch("rg_au"), 130 + k, (0, 50, 120, 150))
               for k in range(32)), "navi half, 32 frames"


#: WHY THESE TWO SEARCH FOR THEIR LAG INSTEAD OF HARDCODING IT.
#: Both capture their RUST side unscripted, straight from power-on reset, while
#: the real side is anchored by a save state and a scripted Start. That makes
#: the offset between them boot-relative -- and boot length is not invariant
#: under a source change, because fat LTO re-inlines globally (TRANSFER 7bj:
#: two builds differing only in `Shot::update` first diverge at frame SEVEN).
#: A hardcoded lag therefore fails for a reason that has nothing to do with the
#: thing being measured, and it has done exactly that twice: `tiles` was widened
#: into a window for the same reason, and these two both moved by one frame on
#: the same build, which is one shift and not two coincidences.
#: Searching a narrow band gives up nothing, because the minimum is a SHARP
#: point, not a plateau. Measured with the wave fix in: `mettaur` is 0 at lag 20
#: with 8485 at 19 and 8380 at 21; `wave` is 0 at lag 125 with 4800 at 124 and
#: 3840 at 126. A real logic regression produces no zero anywhere in the band.
METTAUR_LAGS = range(15, 27)
WAVE_LAGS = range(120, 132)


def by_lag(lags, score):
    """The best (total, lag) over a band of candidate alignments."""
    return min((sum(score(lag)), lag) for lag in lags)


def check_mettaur():
    """The Mettaur virus's 70-frame attack cycle (TRANSFER.md 7ah).

    The virus acts on an RNG neither side shares, so there is no fixed frame
    offset the way `field`/`warp`/`buster` have. Instead: list the frames on
    which the Mettaur's own bounding box (it lives at x>=145, clear of the
    navi) changes on each side, and find the lag that lines the two lists up
    -- of the 17 boundary frames in the real side's attack cluster, 16 land
    on an exact rust boundary at a lag of 21. (7ah measured 20; a rebuild
    today puts every boundary one frame later on both this check and `wave`
    below, which move on a shared mechanism -- see the note in the report.)
    Once aligned, 70 consecutive frames of the cycle are diffed over the
    Mettaur's half of the screen.
    """
    build("demo-field", cc.scratch("rg_field.gba"))
    capture(STERILE, cc.scratch("rg_mtr"), 215, "--loadstate", PAUSED, *ALIVE,
            "--disable-bg", "--script", "Start@10")
    # Enough frames for the WHOLE lag band, not just one lag:
    # start 140 + max(METTAUR_LAGS) + 70 frames of window.
    capture(cc.scratch("rg_field.gba"), cc.scratch("rg_mtu"),
            140 + max(METTAUR_LAGS) + 70, "--disable-bg")
    start, box = 140, (145, 0, 240, 160)

    def score(lag):
        return [diff(cc.scratch("rg_mtr"), start + k, cc.scratch("rg_mtu"), start + lag + k, box)
                for k in range(70)]

    total, lag = by_lag(METTAUR_LAGS, score)
    bad = sum(1 for d in score(lag) if d)
    subprocess.run(["rm", "-rf", cc.scratch("rg_mtr"), cc.scratch("rg_mtu")], check=True)
    return total, "%d of 70 frames differ, lag %d" % (bad, lag)


def check_wave():
    """The shockwave's panel light, one hop and its three-frame linger (TRANSFER.md 7ai).

    Both sides captured `--disable-obj` (backgrounds only, so the field's
    panels and their one-shot yellow highlight, (255,255,66), are what's
    compared -- no sprites). The wave hops panel to panel on its own
    schedule with no shared frame offset, so alignment tracks the SET of lit
    panel centres per frame, lists the frames where that set changes on each
    side, and finds the lag that lines up the boundaries around the real
    side's first visible hop (frame 71, confirmed here) -- 126, at last
    measurement. (7ai measured 125; see the note on `mettaur` above, this
    check moved by the same one frame.) A 90-frame window anchored there
    catches the hop and its linger.
    """
    build("demo-field", cc.scratch("rg_field.gba"))
    capture(STERILE, cc.scratch("rg_wvr"), 165, "--loadstate", PAUSED, *ALIVE,
            "--disable-obj", "--script", "Start@10")
    # start 71 + max(WAVE_LAGS) + 90 frames of window.
    capture(cc.scratch("rg_field.gba"), cc.scratch("rg_wvu"),
            71 + max(WAVE_LAGS) + 90, "--disable-obj")
    start, box = 71, (0, 72, 240, 144)

    def score(lag):
        return [diff(cc.scratch("rg_wvr"), start + k, cc.scratch("rg_wvu"), start + lag + k, box)
                for k in range(90)]

    total, lag = by_lag(WAVE_LAGS, score)
    bad = sum(1 for d in score(lag) if d)
    subprocess.run(["rm", "-rf", cc.scratch("rg_wvr"), cc.scratch("rg_wvu")], check=True)
    return total, "%d of 90 frames identical, lag %d" % (90 - bad, lag)


#: name -> (function, the number it produced when last verified). A non-zero
#: `want` is a residue that is understood; TRANSFER.md says why for each.
CHECKS = [
    ("chips", check_chips, 0),        # all 43
    ("tiles", check_tiles, 0),
    ("gauge", check_gauge, 0),
    ("field", check_field, 0),
    ("window", check_window, 0),
    ("card", check_card, 0),
    ("cursor", check_cursor, 0),
    ("opening", check_opening, 0),
    ("result", check_result, 0),
    ("warp", check_warp, 0),
    ("audio", check_audio, 37223),  # the hit's envelope; drive to 0, do not raise
    ("buster", check_buster, 0),
    ("chip-use", check_chip_use, 0),
    ("mettaur", check_mettaur, 0),
    ("wave", check_wave, 0),
    ("popup", check_popup, 0),          # the chip-name popup, whole box, five chips
    ("banner", check_banner, 0),        # ENEMY DELETED, all 58 frames
    ("rollup", check_rollup, 0),        # the full battle must survive a long script
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated check names")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
    if args.list:
        for name, _, want in CHECKS:
            print("%-10s want %d" % (name, want))
        return 0
    wanted = set(args.only.split(",")) if args.only else None

    worse = 0
    for name, fn, want in CHECKS:
        if wanted and name not in wanted:
            continue
        try:
            got, note = fn()
        except Exception as exc:  # a missing ROM or state is a setup problem
            print("%-10s ERROR %s" % (name, exc))
            worse += 1
            continue
        state = "ok" if got == want else ("BETTER" if got < want else "WORSE")
        if got > want:
            worse += 1
        print("%-10s %-8s got %-8d want %-8d %s" % (name, state, got, want, note))
        sys.stdout.flush()
    print("\n%s" % ("all checks at or better than their recorded numbers"
                    if not worse else "%d check(s) WORSE" % worse))
    return 1 if worse else 0


if __name__ == "__main__":
    sys.exit(main())
