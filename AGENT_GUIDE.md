# AGENT_GUIDE — the 2k-token extract of docs/HANDOFF_2026-09-12.md that a worker actually needs

HANDOFF.md is the short session-start document; the long one with the history, incidents and the
"HANDOFF §N" sections tickets cite is docs/HANDOFF_2026-09-12.md. Read THIS, then only the section a
ticket names. Rules are in AGENTS.md; your ticket text comes from `tools/next_ticket.py`.

## What this is
A Rust reimplementation of BN6 Falzar's battle system as a real GBA ROM (`no_std`, thumbv4t, vendored
agb). Standard: per-pixel parity with the original ROM ("canon"), full 240x160, every compared frame,
zero differing pixels. A non-zero is a defect with a frame and region. No boxes in space or time, no
subtracted baselines, no "inherent" residues. Every check has a negative fixture that must fail.

## Inputs (never tracked, never committed)
`/tmp/bn6f_real.gba` canon · `/tmp/bn6f_real.srm` battery save · `/tmp/bn6f_sterile.gba` canon with
2 code patches ("canon (sterile)": battle never concludes, no banner) · `/tmp/bn6f_sterile_emptynet.gba`
· `/tmp/*.state` save states · `/tmp/mgba_capture` the capture tool. If any is missing:
`bash tools/restore_inputs.sh` (roots from /home/box/bn-backup, everything else rebuilt; `python3
tools/states.py build all` rebuilds every state from recipes).

## Build and measure
```
export CARGO_TARGET_DIR=/tmp/ct_<name>            # your worktree's own target dir (tools/worktree.sh prints it)
cargo build --release && python3 tools/gbafix.py target/thumbv4t-none-eabi/release/bn /tmp/x.gba
python3 tools/harness.py --list                  # every row
python3 tools/harness.py --only ROW --no-gallery # one row (add --ui isolated for a fast inner loop; landing runs both)
python3 tools/oracle.py wave|mettaur             # first divergent STATE field and frame (R7)
python3 tools/verify_rows.py <branch> ROW,ROW --expect ROW=T/W/F/NEG   # reproduce claimed lines, clean checkout
```
Result line: `ROW isolated PASS total 0 worst 0 frames 90 | negative: not blind (total 3840)`.
`total` = differing pixels summed over compared frames, `worst` = worst frame; PASS only when every
frame is 0; `FAILED (allowed: ...)` is a ticketed failure, never widen tools/allowlist.py; `BLIND`
means the negative also read 0 and the row proves nothing. `fitted constants: N` counts `// provenance:
fitted` tags in src/ (tag every constant: derived = from ROM data, peeked = from the running game,
fitted = matched to the picture, mechanism unknown).

## How a row works
One plain ROM, told what to be: the harness writes a 64-byte descriptor at `0x02000040` every frame
(`--cheat`), `src/fixture.rs` reads it at startup (enemies, HP, hand, gauge, flags, fire_frame, rng...;
contract in FIXTURE.md). The ROM writes a marker "BATT" + frame counter at `0x02000000` every frame;
the harness aligns on its first appearance, never on power-on frame counts (boot length moves with code
size). R7's oracle block sits at `0x02000008` (40 bytes). A `Check` has `rust`/`canon` Sides (rom,
loadstate, script, cheats, pokes, zero, extra flags), `frames`, an `Align(canon_ref, search, note)`, a
`ui` (isolated blanks what the check is not about, on both sides; integrated leaves everything on), a
negative ("frame" shift, or "pixel" for a static subject). Alignment is chosen BY EVENT (a RAM value
that marks the moment on both sides), and the search band only confirms a unique minimum -- never pick
an offset because it scores lower (F2's rule).

## mgba_capture flags
`<rom> <outdir> <count>` then: `--loadstate F` · `--loadsave F.srm` · `--script "A@40,Start@10"` ·
`--cheat addr:val16` (every frame) · `--poke addr:val16` (once at load) · `--poke-at frame:addr:val16`
(once, before that frame; max 32) · `--zero addr:len` · `--watch addr:len:file` (append after every
frame) · `--watch-write addr[:len]` (log every write: frame, old->new, writing instruction; R5) ·
`--dump addr:len:file` · `--peek addr` (at load; an object the intro has not populated reads 0) ·
`--only-bg N` · `--disable-obj` · `--disable-bg` · `--trace-pc addr --trace-steps N` (perturbs
timing; bounded use only). Frames are `frame.#####.rgb`; `tools/mgba_frames.py <dir> --at i` renders a
PNG; `tools/diffmask.py` shows where a diff is.

## RAM you will meet
GameState 0x02001b80 (SubsystemIndex byte: 4 map, 8 battle_init, 12 battle main) · CurBattleDataPtr
0x02001b9c · RNG seed 0x020013f0 (GetRNG: seed = rotl(seed,1)+1 ^ 0x873ca9e5) · MegaMan's
BattleObject 0x0203a9b0 (CurState/CurAction +8/+9, HP +0x24, timer +0x20) · enemy slots
0x0203aa88 / 0x0203ab60 / 0x0203ac38 · MegaMan's AIData JoypadPressed 0x020340a4 / Held
0x020340a2 (input reaches him only while the banner sequencer dword_203CA70 is in state 0x08; in 0x0C a
one-shot poke here delivers a press -- F5b/F11) · joypad mirror 0x02036822 · scroll counters
0x02009690/94 read 0/0 at a battle's frame 0.

## Traps that cost a day each
- Forcing the encounter roll's accumulator EVERY frame freezes GetRNG's draw (orbit trap): use one-shot
  `--poke-at` and vary held directions. Patching an encounter-table entry changes which entry a roll
  selects.
- Freed-heap fill patterns 0x11/0x22 look like state; a value's MEANING needs evidence, not just the value.
- A chip press is refused after an enemy died at reload (banner sequencer left 0x08): see F5b.
- `--peek` at load reads 0 for objects the intro has not populated; dump from a later frame.
- Never measure from a tree another agent holds; never `git add -A`; stage by path; commit per landed
  step with what was measured; never push.
- Re-read a file rather than trust a prune summary when exact text or numbers matter. Batch shell work
  into one command or a script per stretch: every turn re-sends your whole context.
- Wall time: a row's captures run in parallel (3 machine-wide slots); a fat-LTO release build is the slow
  step (~1 min cold, seconds warm), so keep one target dir and do not `cargo clean`.
