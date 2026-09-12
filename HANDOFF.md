# HANDOFF — how to run this repo without the chat that built it

Written for an agent. Every command is meant to be pasted. Where a line explains *why*, it is
because someone already made that mistake. Rules live in `AUDIT.md`; this file is how to act on them.

## 0. Read this first

- This is a Rust reimplementation of Mega Man Battle Network 6's battle system as a **real GBA
  ROM** (ARM7TDMI, `no_std`, `thumbv4t-none-eabi`, agb vendored at `vendor/agb`). Not a desktop port.
- The standard is **per-pixel parity with the original ROM**: full 240×160, every frame, zero
  differing pixels. A non-zero is a defect with a number on it, never a tolerance.
- Four rules that bite (the rest are `AUDIT.md`'s 17 problem/solution pairs):
  1. **No boxes**, in space or time. Never shrink the compared region or start the comparison later
     to skip an artifact. Blank an element on *both* sides or make it match.
  2. **No subtracted baselines, no "inherent" residues.** A leftover difference is a checkable claim
     about the real ROM; find what drives it in `reference/bn6f` before writing "cannot match".
  3. **Every check must be able to fail.** The harness runs a negative fixture per check; a check
     that reads 0 on the broken pair is BLIND and is rejected, not passed.
  4. **Tickets state what to measure, not the hypothesis.** A guess goes on an "unverified" line.

## 1. Files you must have, and must never commit

Copyrighted inputs are **never tracked**: they are gitignored everywhere they could land, and the
working copies the tools read live in `/tmp`. Local copies elsewhere are fine and wanted (the site's
`web/real-bn6f.gba` is why the ROM survived the 2026-09-08 wipe); committing one is the violation.

| path | what | regenerable? |
|---|---|---|
| `/tmp/bn6f_real.gba` | the original ROM (BN6 Falzar, "canon") | **NO — the one irreplaceable input** |
| `/tmp/pausedwithcannon.state` | root state: live battle, Cannon queued, paused | **NO** (hand-played) |
| `/tmp/chipselect.state` | root state: chip window open mid-battle | **NO** (hand-played) |
| `/tmp/battlestart.state` | root state: a battle's frame 0, three Mettaurs | **NO** (its recipe's base is lost) |
| `/tmp/noenemy2.state` | root state: RESULT window, the real reward roll | **NO** (recipe gives a different reward) |
| `/tmp/bn6f_sterile.gba` | canon with 2 code patches ("canon (sterile)") | yes: `patch_sterile.py` |
| `/tmp/bn6f_sterile_emptynet.gba` | sterile + the empty-encounter data patch | yes: `states.py build` makes it |
| every other `/tmp/*.state` | built states | yes: `states.py build <name>` |
| `/tmp/mgba_capture` | the capture binary | yes: §2 |

**`/tmp` is not durable.** The irreplaceable inputs are backed up in `/home/box/bn-backup` and on
`/media/box/Scyther/bn-backup`, together with a git bundle of the submodule's `bn-notes` branch (the
only copy of our disassembly annotations; it has no remote). `bash tools/restore_inputs.sh` restores
the working set. Refresh both backups whenever a root state or `bn-notes` changes
(`git -C reference/bn6f bundle create /home/box/bn-backup/bn6f-bn-notes.bundle bn-notes`).

Gitignored on purpose (`.gitignore`): `web/roms/`, `web/bn6-rust.gba`, `web/build.txt`,
`web/real-bn6f.gba`, `web/*.state`, `web/*.sav`, `target/`. Never `git add -f` any of them.

## 2. From clone to a passing row

```sh
# toolchain: nightly is pinned by rust-toolchain.toml (rust-src, clippy, rustfmt); .cargo/config.toml
# sets build-std and the thumbv4t target. Python 3 with numpy and Pillow. libmgba-dev for the capture tool.
sudo apt-get install libmgba-dev            # Ubuntu; provides <mgba/core/core.h> and libmgba.so
git submodule update --init reference/bn6f  # the disassembly; see §8 for the local bn-notes branch

# the capture tool (tools/mgba_capture.sh does the same on first run)
gcc tools/mgba_capture.c -o /tmp/mgba_capture -I/usr/include -lmgba -lm

# the sterile ROM (2 patches by default: battle_isBattleOver -> 0, banner upload -> return)
python3 tools/patch_sterile.py /tmp/bn6f_real.gba /tmp/bn6f_sterile.gba

# every built state, from the manifest
python3 tools/states.py list
python3 tools/states.py build all

# the first row. Builds the plain ROM itself (cargo build --release, ~30 s cold), captures both
# sides, aligns on the marker, and must print "opening isolated PASS total 0".
python3 tools/harness.py --only opening --no-gallery
```

A plain ROM by hand, if you need one: `cargo build --release && python3 tools/gbafix.py
target/thumbv4t-none-eabi/release/bn /tmp/bn.gba`. The release profile is `lto = "fat"`; boot length
moves with code size, which is why nothing aligns on frame numbers from power-on (§4).

## 3. The harness — `tools/harness.py`

One job (`AUDIT` pair 6): capture both sides, align on an event, require zero over the whole screen
for every compared frame.

```sh
python3 tools/harness.py --list                   # every row: name, ui, frames, pending notes
python3 tools/harness.py --only NAME[,NAME...]    # run rows; writes web/captures/<row>-<ui>.gif + .txt
python3 tools/harness.py --only NAME --no-gallery # same, no gallery output
python3 tools/harness.py                          # the whole table (~15-25 min)
```

Reading a result line:

```
wave   isolated  PASS    total 0      worst 0     frames 90  | negative: not blind (total 3840)
card   isolated  FAILED  total 18486  worst 3081  frames 16  | negative: not blind (total 15405)
tiles  integrated FAILED (allowed: AUDIT-6: ..., <=3600) total 26495 worst 3468 ...
```

- `total` = differing pixels summed over the compared frames; `worst` = the worst single frame.
- `PASS` only when every frame is 0. `FAILED (allowed: ...)` means `tools/allowlist.py` has ticketed
  it as a tolerated failure — it is still a failure. Never widen an allowlist entry to make a build pass.
- `negative:` is pair 10. `not blind (total N)` means the deliberately broken pair differed by N;
  `BLIND` means it did not and the row proves nothing. The suite currently has no BLIND rows; keep it so.
- The summary prints `fitted constants: N (derived D, peeked P)` from `// provenance:` tags in `src/`
  (pair 12). A zero standing on a `fitted` constant is visible as such.

What a row is (`Check` in `harness.py`): `rust` and `canon` are functions of the ui variant returning a
`Side` (ROM, optional `loadstate`, `script`, `cheats`, `pokes`, `zero`, extra capture flags); `frames`;
`align` is an `Align(canon_ref, search, note)` — the canon side's frame 0 is a documented fixed frame or
a searched band, the rust side always reads its own marker (§4); `ui` is `isolated`, `integrated` or
`both` (pair 9: an isolated run blanks what the check is not about, on both sides; integrated runs
everything on); `negative` is `"frame"` (default) or `"pixel"` (only for a subject that provably never
moves — see `window`'s note); `canon_variant` names which original is compared ("canon" or "canon
(sterile)"). The 43 chip rows share one descriptor template and one build (pair 14).

Layer isolation is symmetric since the BG3 merge: our backdrop/field/HUD+window sit on hardware BG1/2/3
exactly as canon's do (BG0 is a blank filler), so `--only-bg N` on both sides compares the same layer.

Adding a row: copy the nearest existing `Check`, set `canon_ref` from a measurement (a `--watch` on the
state's own counters, or a peeked frame), keep the search band narrow and say in `note` why it is where
it is, run it, and confirm `negative: not blind`. Then run the whole table before committing.

The library underneath is `tools/chip_compare.py`: `capture()` (retries a short capture),
`diff_frames()` (numpy, full frame or box), `frame_array()`, `scratch()` (a `/tmp/bn-<hash>` dir keyed
on the checkout path, so worktrees never collide), `peek16()`, `library_pokes()`, `capture_real()`.

## 4. The descriptor and the marker (`FIXTURE.md`)

One plain ROM, told what to be. The harness writes 64 bytes at **`0x02000040`** every frame
(`--cheat`), the ROM reads them once at startup (`src/fixture.rs::read()`). Magic `0x46495854` "FIXT";
absent → the normal full battle. `FIXTURE.md` is the contract; every field it lists is read.

Fields, by offset: `+4 enemies`, `+5 enemy_kind`, `+6/7 enemy col/row`, `+8 megaman_hp u16`,
`+10/11 megaman col/row`, `+12 hand_count`, `+13 hand[5]`, `+18 gauge`, `+19 flags` (bit0 open with the
chip window, bit1 blank HUD, bit2 blank backdrop, bit3 auto-fire, bit4 skip intro), `+20..+27
art_entry / art_timer / scroll_xq / scroll_yq u16` (0xFFFF = default), `+28 gauge_tick`, `+30
fire_frame`, `+32 enemy_hp` (0 = the kind's default), `+34 deck_count`, `+35 deck[5]`, `+40
start_state` (1 = at the RESULT window), `+41 result_level`, `+42 result_frames`, `+44 result_zenny`,
`+46 banner_at`, `+48 deck_codes[5]`, `+53 window_pick_count`, `+54 window_pick_slot`, `+55
window_cursor`, `+56 result_elapsed`, `+58 rng u32` (the game's RNG state at frame 0, peeked from the
canon state). `harness.py::fixture_cheats(desc)` turns a dict into the `--cheat` list;
`src/fixture.rs` has a table of the old `demo-*` fixtures as descriptor bytes.

The **marker**: the ROM writes `0x42415454` "BATT" + a battle-frame counter at **`0x02000000`** every
frame (`src/main.rs`, section `.ewram.marker`). The harness finds the first frame it appears
(`--watch 0x02000000:8`) and aligns on that, never on a frame count from power-on — boot length shifts
with code size, and the first `commit()` can be invisible (agb skips a vblank wait if one already
passed). A check on a hardcoded lag broke the day an unrelated edit moved boot by one frame.

`demo-*` cargo features still exist and still build (`tools/regress.py` and `tools/build_roms.sh` use
them). They are legacy: they get deleted, with `regress.py`, once the harness reads zero through
descriptors for everything they covered. Do not add new ones.

## 5. `mgba_capture` reference

`/tmp/mgba_capture <rom.gba> <outdir> <count> [flags]` runs libmgba headlessly and writes
`<outdir>/frame.#####.rgb` (240×160×4 raw). Frame index is 0-based from load.

| flag | what |
|---|---|
| `--loadstate <file>` | start from a save state (mGBA-qt "RASTATE" banner handled) |
| `--script "Key@frame,..."` | press keys on frames (`Start@10,A@40`) |
| `--cheat addr:val16` | write a 16-bit value **every frame** (how the descriptor is delivered) |
| `--poke addr:val16` | write once, at load, before frame 0 (library ownership bits) |
| `--poke-at frame:addr:val16` | write once, immediately before that frame (max 32). One-shot conditions mid-run |
| `--zero addr:len` | zero a range (tile ranges: banner, enemy) |
| `--watch addr:len:file` | append `len` bytes at `addr` after **every** frame (marker, counters, RNG) |
| `--dump addr:len:file` | read a range once at the end |
| `--peek addr` | print a 16-bit value at load |
| `--savestate <file>` | save at the end (how `states.py build` works) |
| `--only-bg N` | one BG layer on, OBJ and windows off |
| `--only-bg-with-obj N` | one BG layer on, OBJ left alone (a sprite against one layer) |
| `--disable-obj` / `--disable-bg` | sprites off / all BG off |
| `--diff-against dir:lag:file` | stream: diff each frame against `dir` at `lag`, write u32 counts, no frames |
| `--trace-pc addr` (+`--trace-steps N`) | single-step the first N instructions of every frame, print regs on a PC hit. Diagnostic only; unbounded stepping corrupts the BIOS HLE |
| `--audio-channel id`, `--dump-audio dir` | audio (out of scope, §13). The advertised rate is wrong; the printed measured rate is right |
| `--press-A ticks` | legacy: hold A from frame 60 |

## 6. States — `tools/states.py`

Pair 5: a state is a *recipe* (base ROM, base state, script, cheats, pokes, poke_at, frames), not a
file. `list` shows the manifest with each entry's verification note; `build <name>` regenerates it into
`/tmp` with `--savestate`; `build all` does the buildable ones. Roots refuse to build.

| name | root | for |
|---|---|---|
| `paused`, `chipselect`, `battlestart`, `noenemy2` | yes | the hand-played bases (§1) |
| `result_arrival` | no | RESULT slide-in inside the capture (frames 21–31) |
| `overworld_net` | no | the first overworld state: battlestart resolved to the net area |
| `emptyfield_start` | no | a battle that spawned a real encounter and deleted it before frame 0 |
| `chip_ready_empty` | no | from that, the chip window picked and closed by real inputs; a chip fires |
| `chip_ready` | no | a rejected attempt, kept as the record; nothing loads it |

Changing a fixture's comparison parameters means editing the recipe and rebuilding, never keeping a
stale file. A state saved mid-battle has the enemy baked into RAM — no ROM patch removes it afterwards.

## 7. The site — `web/`

- `bash tools/build_roms.sh` — every demo ROM into `web/roms/` in parallel, plus `web/roms/manifest.json`.
  Each label starts with its build timestamp and the list sorts newest first (pair 8); an unstamped ROM is
  dropped. Run after any merge that changes what a listed ROM shows.
- `python3 tools/captures_manifest.py` — `web/captures/manifest.json` from `web/captures/*.gif` (+ `.txt`
  caption), newest first by git add-date. The harness writes the GIFs; commit them (pair 7: a commit that
  changes the screen updates the gallery before the next commit — failures included).
- `bash tools/web_rom.sh` — the dev-profile ROM to `web/bn6-rust.gba` for the page.
- `python3 tools/serve.py [port]` — serves `web/` (default 8123); `index.html` is the ROM dropdown
  (EmulatorJS, needs internet for its core), `gifs.html` the gallery.

## 8. Operating procedure — agents, worktrees, merging

- Delegate through pi's `subagent` tool to the roles in `.pi/agents/` (worker always; verifier and recon
  only when §13 says so). Keep the coordinator for judgment; push disassembly reads, sweeps and long
  runs out. Model per role is in `.pi/agents/*.md` and `MODEL_RESEARCH.md`.
- **One agent, one worktree, non-overlapping files.** `bash tools/worktree.sh <name>` prints
  `/tmp/bnwt/<name>`, branch `wt/<name>`, and `CARGO_TARGET_DIR=/tmp/ct_<name>` to export. It symlinks
  `reference/bn6f` and marks it `--skip-worktree`. Agents stage by path, never `git add -A`, commit per
  landed step, and report numbers with frame/region.
- **Verify before merging, from a tree no agent holds** (its worktree once the agent is done, or a
  detached `git worktree add --detach` of the branch): build + the relevant rows.
  Then from the main checkout: `git merge --no-ff wt/<name>` · `git worktree remove --force
  /tmp/bnwt/<name>` · `git branch -d wt/<name>` · `rm -rf /tmp/ct_<name>`.
- Commit every verified step. **Never push.** Commit messages say what was measured.
- If a commit changes what the screen shows: run the harness (or the affected rows) and commit the
  gallery; rebuild the site ROMs if a listed ROM changed.
- **`reference/bn6f` annotations:** comments and labels only, never instructions or data — the
  disassembly must keep assembling byte-identical. Our commits live on the submodule's local branch
  `bn-notes` (not on the upstream remote — back it up). An agent commits on `wt/<name>` there (branched
  from `bn-notes`), checks `bn-notes` back out afterwards because the checkout is shared; the coordinator
  merges into `bn-notes`, then `git add reference/bn6f && git commit` in the superproject.
- Wake on task notifications (`bg_wait`), with a 20–30 minute fallback check-in, not a 5-minute poll:
  every coordinator turn re-sends its whole context (§13, `WORKFLOW_AUDIT.md` finding 2).
- When an agent's number disagrees with yours, rebuild and check the tree before contradicting it.

## 9. Gotchas, each with the incident behind it

- **Boot length moves with code size** (fat LTO, sub-frame setup crossing vblank). Align on the marker;
  a hardcoded lag broke on an unrelated edit (`cursor` 0 → 602).
- **The RNG orbit trap** (TRANSFER 7aw): `GetRNG` is `seed = rotl(seed,1)+1 ^ 0x873ca9e5` at
  `0x020013f0`. Identical input every frame — or an accumulator *forced every frame* — walks one orbit
  and a roll's outcome is fixed at load. Vary input; use `--poke-at` for one-shot conditions.
- **Patching an encounter-table entry changes which entry a roll selects.** Find-it-then-patch-it does
  not work; spawn a real encounter and delete it instead (`emptyfield_start`).
- **`--never-spawn` crashes a fresh spawn** (boot logo 9–13 frames in) and is a no-op on every
  existing state. Off by default. `--inert-enemy` freezes the enemy but it keeps drawing and swallows
  the chip press. Both kept as documented dead ends.
- **A static subject makes a frame-shift negative BLIND.** `window`'s canon BG3 is byte-identical for
  260+ frames; it uses the pixel-shift negative. `card` was blind because its `canon_ref` sat past the
  last cursor transition; re-centring it exposed a real 18486.
- **`--only-bg` was asymmetric until the BG3 merge** (our layers were on different indices). Per-layer
  numbers from before `6df916a` are not comparable.
- **Two vblank-race residues**: one 96-byte VRAM write one frame early between two differently sized
  binaries (custmatch 371 px), and one wide-screen frame in `tiles` (208 px). Not fixed; don't chase blind.
- **Short captures under memory pressure** read as regressions; `capture()` counts frames and retries.
  Don't run many captures in parallel on a small machine. `/tmp` grows (49 GB seen); `rm -rf /tmp/ct_*`
  is safe, the ROM and states are not.
- **`pkill -f <pattern>` matches its own shell** (exit 144). Kill by PID.
- **Codium's rust-analyzer** respawns and eats RAM; close the window, not just the process.
- **`git add -u <path>` limits the commit to that path**; a `git add -A` in a worktree once turned the
  submodule into a self-referential symlink.
- **Measuring from a tree an agent holds** gave wrong numbers three times and once made the coordinator
  tell a correct agent it was wrong.
- **A chip fires with no enemy** in a battle that never had one; it is refused only after an enemy
  *died* at reload. The zero-enemy standard holds.

## 10. Where the numbers stand (2026-09-08) and what is next

Passing at 0: `opening` (isolated), `wave` (90 frames, BG2 both sides), `window` (16 frames, BG3 both
sides), `rollup` (no crash). 19 fitted / 145 derived / 112 peeked. `AUDIT.md`'s closing table lists every
other row's number and cause. Two root causes carry most of it: **every canon state's enemy was deleted,
not never-spawned** (chip baseline 14388 ×38, `banner` 2248, `popup` ~107k, `field`/`buster`'s orb), and
**MegaMan's own hit/dwell timing** (`shot.rs`'s deferred per-hop dwell; `mettaur`'s 30864 is entirely his
side — the enemy region is 0/70).

Next, in the order §13 fixes: (1) the battlestart recipe, then the fixture chain, then re-point
chips/`banner`/`popup` at `chip_ready_empty`; (2) the state oracle; (3) the `shot.rs` dwell gap and
`card`'s cursor-move timing, oracle-first; (4) delete `demo-*` and `regress.py` once everything they
covered reads zero through descriptors. `tools/regress.py` (the old boxed suite) still runs
(`--only a,b`); its enemy checks read non-zero since the real Mettaur cadence landed — expected.

## 11. Map of the other documents

- `AUDIT.md` — the 17 rules, the optimisations, every wave's split and the closing state. Read first.
- `FIXTURE.md` — the descriptor contract. `TODO.md` — ticket format, the per-ticket rules, old tickets.
- `TRANSFER.md` — the long journal. Worth reading: 7aw (encounters and the RNG trap, battle frame 0),
  7av (backdrop scroll phase), 7bf (the RESULT countdown), 7bn (states manifest), 7bi/7bl (backdrop
  period), 7bg (panel damage — closed). §11's "quick reference" is superseded by this file.
- `tools/CAPTURE_NATIVE.md` — why the capture is headless libmgba.
- `MODEL_RESEARCH.md` — the OpenRouter model survey behind the per-role picks. `WORKFLOW_AUDIT.md` —
  the workflow measured against the scoped goal in tokens per completed row. `AGENTS.md` — the rules
  every pi child loads; `.pi/agents/` — the roles; `.pi/settings.json` — coordinator model and packages.
- `~/.claude/projects/-home-box-Code-bn/memory/` — the user's standing instructions (subagent
  delegation, worker hygiene, no inherent residues, annotate bn6f, vendor deps).
- `reference/bn6f` — the disassembly, with our comments at every address this project has touched.

## 12. Glossary

**canon** the untouched original ROM · **canon (sterile)** the patched original (battle never concludes,
no banner), the comparison for chip rows · **isolated / integrated** the check's subject alone, with UI
blanked on both sides / everything on · **marker origin** the capture frame where "BATT" first appears
on our side · **canon_ref** the canon capture frame that is frame 0 of the comparison · **descriptor**
the 64 bytes at `0x02000040` · **root state** hand-played, irreplaceable · **built state** regenerable
from its recipe · **derived / peeked / fitted** a constant read from ROM data / read from the running
game / matched to the picture with the mechanism unknown · **negative fixture** the deliberately broken
pair each check must fail on · **BLIND** a check whose negative also reads 0 · **residue** the non-zero
a check reports, always with a frame and region.

## 13. Decisions of 2026-09-12 (supersede §8/§10 where they differ)

Made after the model research (`MODEL_RESEARCH.md`) and the workflow audit (`WORKFLOW_AUDIT.md`).

- **Scope.** The 43 chips already in the harness, 5 viruses, 2 bosses, player fidelity, the custom
  screen for that deck, and battle flow. Out: other chips, Navis, Navi Customizer, Program Advances,
  netbattle, audio.
- **Order.** (1) root-state recipes (ROM + `.srm` + input log from power-on, RAM-driven walk, a vision
  model only at branch points) → (2) the fixture chain `battlestart → overworld_net → emptyfield_start
  → chip_ready_empty`, then re-point the chip/banner/popup rows → (3) the state oracle (canon RAM watch
  of the RNG word, MegaMan position/timers, enemy state vs. a state block the Rust ROM exports next to
  the marker; the harness reports the first divergent frame and field) → (4) usage logging → tickets.
- **Tickets are families or systems**, not rows: the 43 chips are ~8 families with their rows as the
  acceptance set. Nothing on a chip before step (2) lands.
- **Roles.** `worker` (always), `verifier` (only for judgment tickets: allowlist edits, fitted constants,
  fixture recipes, canon-side patches), `recon` (only when the oracle does not localise). No measurer
  (the harness prints the line), no archivist (facts go in the row note and AUDIT's table), no
  benchmark, no scoreboard. Role files: `.pi/agents/`. Rules every child loads: `AGENTS.md`.
- **Models** (OpenRouter ids; `.pi/settings.json`): coordinator `anthropic/claude-opus-5` high (chosen by
  cache-read price and the verified caching path in pi); planning/merge judgment `openai/gpt-5.6-sol`;
  worker `anthropic/claude-sonnet-5` xhigh, with `google/gemini-3.8-flash` A/B'd on the shot-dwell and
  card-cursor tickets; verifier `openai/gpt-5.6-terra`; recon and the frame walker
  `google/gemini-3.8-flash`. Fallback recon `deepseek/deepseek-v4-pro` — any open-weight model is used
  through OpenRouter's `:exacto` variant (provider pinned for tool-call quality); closed models unpinned.
  Escalate a failed timing ticket once, to Sol or Opus 5. No caveman mode. The "no DeepSeek" rule is
  gone (memory updated).
- **Coordinator hygiene.** Fresh session per ticket batch, rebuilt from `harness.py --list`, the
  allowlist and `git log`, not from a chat. Context under ~100k. Event-driven wakeups with a 20–30 min
  fallback, not a 5-minute poll. Agents read HANDOFF §0–§4 and the row note only; `TRANSFER.md` is for
  humans.
- **pi.** Project resources load only after `/trust` is run once in this folder (or
  `defaultProjectTrust: "always"` in `~/.pi/agent/settings.json`). The subagent extension, when built,
  needs `agentScope: "both"`. `.pi/goals/` is session state and gitignored (its paused goal still carries the old
  tooling objective; close or rewrite it with `/goal` in pi). `PI_WORKFLOW.md` and
  `SUBAGENT_FLOWS.md` were removed in the cleanup; they are in history at `5ad59b6`.
- **Inputs.** `/tmp` was wiped again (2026-09-12). `bash tools/restore_inputs.sh` restores everything
  regenerable from `/home/box/bn-backup` (copy on `/media/box/Scyther/bn-backup`). Still lost:
  `battlestart.state`, `noenemy2.state` — the recipe work in step (1) replaces battlestart; noenemy2's
  reward roll is unrecoverable by recipe, so the `result` row moves to `result_arrival` and a rebuilt
  RESULT fixture is declared a different fixture, not a restoration. `states.py build all` now skips a
  chain whose base is missing instead of aborting.
- **pi is built from source.** Clone at `/home/box/Code/pi`, branch `local/build-fixes` (one local commit:
  the missing `FinishReason.TOO_MANY_TOOL_CALLS` case that broke `packages/ai` at upstream
  `71dca87`). `npm link` from `packages/coding-agent` points the global `pi` at
  `/home/box/Code/pi/packages/coding-agent/dist/bundle/cli.js`; `pi --version` reads 0.85.1 and a `-p`
  smoke test through OpenRouter passed. To update: `git -C /home/box/Code/pi pull --rebase origin
  main && npm -C /home/box/Code/pi run build` — no relink needed. `npm run build` is what the repo's
  own AGENTS.md says not to run unasked; here the user asked.
- **Extensions (project-local, `.pi/settings.json` `packages`; installed under `.pi/npm/`, gitignored).**
  Survey verdicts are in the session that made them; the adopted set: **`pi-context-prune`** (strips
  finished tool results from what is re-sent, recoverable through `context_tree_query` — the direct fix
  for the coordinator's re-sent-context cost) and **`pi-subagents`** (nicobailon; maintained, 3.5k
  stars; child runs return truncated artifacts, `bg_wait` instead of polling; reads `.pi/agents/**/*.md`,
  project definitions override its builtin `worker`/`reviewer`/`scout`). This **replaces the custom
  subagent extension** SUBAGENT_FLOWS.md gated on approval; nothing custom gets built. Both load: a
  `-p --approve` run lists `context_tree_query`, `subagent`, `bg_wait`, `subagent_supervisor`. `pi-goal-x`
  stays for now; measure its per-turn overlay cost and drop it if it is not terse. Rejected:
  `pi-worktrees` (auto `git add -u` and `git reset --hard` on its own schedule — conflicts with the
  worker-hygiene rule), per-turn LLM routers and free-tier racers (spend tokens every turn to maybe
  save some, and add nondeterminism). To try later: `pi-background-tasks` for serial captures,
  `pi-review` (official) for the verifier's diff step, `@xamfoo/pi-openrouter-pin` if provider hopping
  ever shows up — verify each README first; the store is unmoderated and churning.
