# AGENT_GUIDE — what a worker needs, in the order it is needed

Your ticket text arrives in your task. Rules are in AGENTS.md. When a ticket cites "HANDOFF §N", read
only that section of docs/HANDOFF_2026-09-12.md. Never read TODO.md, HANDOFF.md or tools/harness.py
whole; grep them.

## The loop
```
bash tools/worktree.sh <name>                     # your own worktree, branch and target dir (it prints them)
export CARGO_TARGET_DIR=/tmp/ct_<name>            # keep ONE target dir: a fat-LTO release build is ~1 min cold, seconds warm
python3 tools/harness.py --only ROW --no-gallery  # the ticket's baseline, BEFORE any edit (--ui isolated for the inner loop)
# ... the change, in the files the ticket allows ...
python3 tools/harness.py --only ROW --no-gallery  # the identical command again
git add <paths> && git commit                     # per landed step, saying what was measured; never `git add -A`, never push
```
Read the result line: `ROW isolated PASS total 0 worst 0 frames 90 | negative: not blind (total 3840)`.
`total` is differing pixels summed over the compared frames, `worst` the worst single frame; PASS only
when every frame reads 0. `FAILED (allowed: ...)` is a ticketed failure: never widen tools/allowlist.py.
`BLIND` means the negative control also read 0, so the row proves nothing. Every number you report must
come from a command you ran in that session.

## What you leave behind
- `docs/worklog/<ID>.md`, written as you go and committed with your other work: what you measured and the
  numbers, every idea you tried and why you dropped it, what you would try next. It lands on main even if
  your branch does not, and the next worker on this objective starts by reading it. A failed ticket with a
  good log is worth more than a silent one.
- A report in the AGENTS.md shape: the harness lines before and after, the citations, and what is unproven.
- Constants tagged `// provenance: derived|peeked|fitted -- <source>` (derived = from ROM data, peeked =
  from the running game, fitted = matched to the picture, mechanism unknown; the harness counts fitted ones).

## Finding things in the original game
- `python3 tools/csrc.py <symbol or address>` prints a decompiled C view of a routine of the original
  followed by the disassembly lines it came from. Use it to see a routine's shape before reading assembly;
  in a measured A/B it halved the assembly reading per solved ticket. It is a MAP: a citation is always an
  assembly file and line, and every number is verified by measurement.
- `docs/recon/<ID>.md`, when it exists, is a map of where your ticket's behaviour lives; read it first, and
  treat every causal claim in it as unverified.
- The disassembly's symbols were renamed from address-only names on 2026-09-15 (321 of them:
  `sub_8109EF4` became `ForMettaur_8109EF4` and so on). `reference/bn6f/docs/renames.md` maps old to new,
  and every new name keeps the address as its suffix, so searching by address always works.
  `reference/bn6f/docs/decomp/*.c` is a different, older decompilation under the old names.
- `reference/bn6f` is improved as we learn (Monday: 321 symbols renamed), but not by you mid-ticket: the gate is a
  rebuild to the ROM's sha1. If you work out what an `Unk_` field or an unnamed routine is, say so in your report
  and work log with the evidence; the morning pass carries it into the disassembly and the decompiled C.
- A comment that cites a fact's provenance points at `docs/provenance.md#<id>` (e.g.
  `#7aw` for the save-state-at-first-frame fact, `#7ao` for the read-arcs-out-of-the-object
  fact); read only that section. The historical journal `TRANSFER.md` stays in place but its
  load-bearing facts are now in `docs/provenance.md`.

## What this project is
A Rust reimplementation of BN6 Falzar's battle system as a real GBA ROM (`no_std`, thumbv4t, vendored agb).
Parity means the original's behaviour reproduced exactly, on three surfaces that each have a zero: pixels
over every compared frame of the full 240x160 screen, the state trace field by field, and audio sample for
sample. A non-zero is a defect with a frame and a place, never a tolerance; no boxes in space or time, no
subtracted baselines, no "inherent" residues, and every check has a negative fixture that must fail. Your
landing may not make any surface worse. Engine-core progress shows in the trace first, with the pixels as
the veto; a chip, a virus or a Navi is done when its own scene reads zero on pixels AND trace.

## How a row works
One plain ROM, told what to be: the harness writes a 64-byte descriptor at `0x02000040` every frame
(`--cheat`), `src/fixture.rs` reads it at startup (enemies, HP, hand, gauge, flags as a `SceneFlags`
type, fire_frame, rng...; contract in FIXTURE.md). The ROM writes a marker "BATT" plus a frame counter at
`0x02000000` every frame and the harness aligns on its first appearance, never on power-on frame counts
(boot length moves with code size). The oracle block sits at `0x02000008` (40 bytes, assembled from one
table in src/battle.rs). A `Check` has `rust`/`canon` Sides (rom, loadstate, script, cheats, pokes, zero,
extra flags), `frames`, an `Align(canon_ref, search, note)`, a `ui` (isolated blanks what the check is not
about, on both sides; integrated leaves everything on), and a negative. Alignment is chosen BY EVENT (a
RAM value that marks the moment on both sides); the search band only confirms a unique minimum, never
pick an offset because it scores lower (F2's rule).

## Inputs (never tracked, never committed)
`/tmp/bn6f_real.gba` canon · `/tmp/bn6f_real.srm` battery save · `/tmp/bn6f_sterile.gba` canon with two
code patches ("canon (sterile)": the battle never concludes, no banner) · `/tmp/bn6f_sterile_emptynet.gba`
· `/tmp/*.state` save states · `/tmp/mgba_capture` the capture tool. If any is missing:
`bash tools/restore_inputs.sh` (`python3 tools/states.py build all` rebuilds every state from recipes).

## Measuring tools
```
python3 tools/oracle.py wave|mettaur              # first divergent STATE field and frame
python3 tools/probe.py watch|peek|frame|diff      # the common measurements, one command instead of a script
python3 tools/verify_rows.py <branch> ROW,ROW --expect ROW=T/W/F/NEG   # reproduce your lines from a clean checkout
python3 tools/trace.py record canon <scenario> --out /tmp/tr_c         # canon's per-frame state
python3 tools/trace.py record rust  <scenario> --out /tmp/tr_r         # ours (TRC2 v3, written only when the trace flag is set)
python3 tools/trace.py diff /tmp/tr_c /tmp/tr_r --align row:<scenario> # first divergent field and frame, then the list
python3 tools/scoreboard.py                       # the whole table at a glance
```
Every tool's one-line purpose is in `tools/README.md` (generated). The extraction and dump tools tickets use most: `tools/spr_export.py` and `tools/spr.py` (sprites), `tools/spr_dump.py`
and `tools/spr_export_range.py` (sheets), `tools/throw_dump.py` (thrown-object arcs), `tools/text_font_export.py`
(glyphs), `tools/chip_export.py` (chip records), `tools/sample_export.py` (audio). `tools/web_rom.sh` and `tools/serve.py` build and serve the
browser ROM; you rarely need either.

`mgba_capture <rom> <outdir> <count>` then: `--loadstate F` · `--loadsave F.srm` · `--script "A@40,Start@10"` ·
`--cheat addr:val16` (every frame) · `--poke addr:val16` (at load) · `--poke-at frame:addr:val16` (once, max 32)
· `--zero addr:len` · `--watch addr:len:file` · `--watch-write addr[:len]` (frame, old->new, instruction) ·
`--dump addr:len:file` · `--peek addr` (at load) · `--only-bg N` · `--disable-obj` · `--disable-bg` ·
`--trace-pc addr --trace-steps N` (perturbs timing). Frames are `frame.#####.rgb`; `tools/mgba_frames.py <dir>
--at i` renders a PNG; `tools/diffmask.py` shows where a diff is.

## Traps that cost a day each
- Forcing the encounter roll's accumulator EVERY frame freezes the generator's draw (orbit trap): use a
  one-shot `--poke-at` and vary held directions.
- Freed-heap fill patterns 0x11/0x22 look like state; a value's MEANING needs evidence, not the value.
- A chip press is refused after an enemy died at reload (the sequencer is left in 0x08): see F5b.
- `--peek` at load reads 0 for objects the intro has not populated; dump from a later frame.
- `land.sh --no-verify` is refused for any branch that changes code, and rightly: a worker used it to land
  a regression on 2026-09-15.
- Never measure from a tree another agent holds. Stage by path. Commit per step. Never push.
- Your captures share three machine-wide slots with everyone else's; a row's own captures already run in
  parallel. (Token discipline is in your role text, and it is not optional.)

## RAM you will meet
GameState 0x02001b80 (SubsystemIndex: 4 map, 8 battle_init, 12 battle main) · CurBattleDataPtr 0x02001b9c ·
RNG seed 0x020013f0 (rotl(seed,1)+1 ^ 0x873ca9e5) · MegaMan 0x0203a9b0 (CurState +8, CurAction +9, timer
+0x20, HP +0x24) · enemies 0x0203aa88 / 0x0203ab60 / 0x0203ac38 · his AIData JoypadPressed 0x020340a4, Held
0x020340a2 (input reaches him only while the sequencer word 0x0203CA70 is in 0x08; in 0x0C a one-shot poke
here delivers a press) · joypad mirror 0x02036822 · scroll counters 0x02009690/94, both 0 at frame 0.