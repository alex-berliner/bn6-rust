# Methodology audit — problem / solution pairs

Started 2026-09-08. One line each way; the reasoning lives in TRANSFER.md.

| # | Problem | Solution |
|---|---------|----------|
| 1 | Alignment between the real capture and ours is counted in frames from power-on, and our boot length moves with the compiler (fat LTO), so a fixed "real X ↔ ours Y" pairing breaks on unrelated edits. A vblank wait at the end of setup does NOT fix this. | Have the ROM write a **"battle started" marker** to a known RAM address, and have the harness align both captures on that event instead of on a frame number. `mettaur`/`wave` already align on the enemy's own state changes; the marker makes it universal. |
| 2 | Checks isolate layers only coarsely — all backgrounds off or all objects off — so unrelated elements ride together in one number, and we don't know which BG layer the HUD, panels and gauge each live on. | Use `--only-bg <n>` (already in the harness, used zero times) to compare **one BG layer at a time**, and first map which layer each element is on. |
| 3 | `field` cannot compare beyond one frame because the enemy acts on an RNG the two sides don't share — and hiding its sprite is not enough, since its attacks light panels and change the HP counter on the background layers too. | **Standard: arena checks run with zero enemies.** Patch the game so an empty field keeps running (the sterile ROM already does this via `battle_isBattleOver`) and use a no-enemy save state, as the chip fixtures already do. No enemy, no side effects. Enemy behaviour gets its own checks where the enemy is the subject (`mettaur`, `wave`). |
| 4 | `result`'s fixture begins after the window has already arrived (it moves only at frames 0–2), so the check is one still picture. | Generate an **earlier save state** with the harness's `--savestate`, so the slide-in is inside the capture. |
| 5 | Save states are coupled to the fixture they're compared against — remove the Mettaur from a Rust fixture and its canon state must change to match — but the states are opaque files in `/tmp` with no record of how they were made, so a fixture change silently leaves a stale state behind. | Treat states as **built, not kept**: a manifest listing each one as (base ROM, base state, script, cheats, frame count), regenerated with the harness's `--savestate`. Changing a fixture then means editing the manifest and re-running it, and the coupling is written down instead of remembered. |
| 6 | Many checks and every chip capture diff a **box** — the navi's half, a strip, a band — and report zero for it. Everything outside the box is unmeasured: the sterile fixture's HUD prints a bare "100" where canon draws the HP box with MegaMan's face, and a bomb's explosion can be missing from a frame that still scores 0. A box zero is not parity. | **Standard: full-screen, every frame, no exceptions.** One harness, one job: take init data for the Rust side and the canon side, run both, and require zero differing pixels over the whole 240×160 for N frames. Every change goes through it. If a fixture needs UI standardised to make that possible — the HUD, the effects, the enemy count — either **make the element match**, or, when it's irrelevant to the change under test, **remove or blank it on both sides** using the techniques above (zero enemies, a game patch, `--only-bg`, `--zero`). Never shrink the box. Layer isolation (`--only-bg`) is compatible: full screen, one layer at a time. Boxes are not. |
| 7 | The gallery is the user's main instrument for judging whether the work is on track, but it's updated by discretion — after the fact, when something is finished, mostly with successes. So it lags the work and shows the flattering subset. | **The gallery is an output of the harness, not a curated afterthought.** Every harness run that touches a change writes its capture into the gallery automatically: full screen, real beside ours, the measured pixel count in the caption, and the commit it came from. Failures and in-progress states go in too — a red number is more useful for judging direction than a zero. Rule: **if a commit changes what the screen shows, the gallery shows it, before the next commit.** |
| 8 | The ROM dropdown on the site has no timestamps, so there's no way to tell whether a given ROM is recent or a stale build from hours ago. Organisation has been poor. | **Every ROM's label starts with its full date and time of creation** (`2026-09-08 03:14 — Full battle vs one Mettaur`), written by the build script from the moment it packs the ROM, and the list sorts newest first. A ROM without a timestamp does not go in the list. |
| 9 | A chip or animation test run with the UI blanked proves the animation but says nothing about how it composes with the HUD, gauge and banners around it — and one run with everything on can't tell which of the two is at fault when it fails. | **Every non-UI test runs twice.** Once **isolated** — UI elements blanked or removed on both sides, so the number is the animation alone — and once **integrated**, with every UI element active, full screen. Both must read zero. A failure in only the second run localises the fault to composition, not the animation. |
| 10 | Every new check I wrote was wrong on its first run — sampling its own period, missing `--loadstate`, the wrong sign, the wrong window — and each reported a confident number. Nothing proves a check can *fail* before its zero is believed. | **Every check ships with a negative fixture** — a deliberate one-frame offset or a known-different ROM — and the harness runs it too. A check that reads zero on both the real pair and the broken pair is rejected as blind. |
| 11 | The suite's `want` convention lets a known defect pass as "ok" — `audio` at 7303 shows green — so a number can be normalised into passing and a later commit can raise it unnoticed. | **A non-zero is a failure, full stop.** Drop `want`; the harness demands zero. Known defects go in a separate allowlist with a ticket and a date, visible as failures the suite is tolerating, never as passes. |
| 12 | Tuned constants make a check read zero whether they were derived from the game or fitted to the picture, and nothing distinguishes the two. `gauge`'s zero rests on two fitted offsets with no known mechanism. | **Every constant declares its provenance** in source: `derived` (from ROM data, cited), `peeked` (read from the running game), or `fitted` (matched, mechanism unknown). The harness summary counts how many `fitted` constants the current zeros rest on, so a zero standing on a fudge is visible as such. |
| 13 | Captures under memory pressure wrote fewer frames than asked; the harness now refuses a short capture, but the runs still fail and cost time. A global lock would fix it by stopping agents from testing concurrently, which is worse. | **Stream, don't store**: diff each frame against the reference as it leaves the emulator and keep only counts, so a capture no longer writes hundreds of MB to `/tmp`. And **retry a short capture automatically** rather than fail it. Either or both; no lock. |
| 14 | A full suite run is ~40 minutes, most of it 43 separate cargo builds for the chip fixtures — which collides with "every change through the harness". | **One ROM, chip chosen at runtime.** The harness pokes the chip id into a known RAM address before the run and our ROM reads it at startup; the canon side already gets its chip by `--poke`. 43 captures against one build. All run by default; a chip-specific change may iterate on its own isolated + integrated pair, then run the full list before commit. |
| 15 | Tickets have encoded my hypothesis as the task, and agents spent runs chasing it. | **Tickets state what to measure, not what I think the answer is.** Any guess goes on a separate "unverified" line the agent is free to disprove first. |
| 16 | Chip comparisons run against the *sterile* ROM — a patched original with two behaviours removed and the enemy deleted — but captions and checks call it "real ROM". | **Name the canon variant** wherever a modified original is the comparison: "canon (sterile)". |
| 17 | Fixtures are 55+ `demo-*` compile-time feature flags, one build each, existing only to bake a state into a binary. | **Fixtures become data, not features.** One ROM reads a fixture descriptor from RAM at startup — chip in hand, HP, enemy count, gauge state, backdrop phase, which UI elements to blank — poked by the harness. Keep a flag only where the *code* differs. |

## Optimisations

Where the harness work would actually benefit from parallelism, and one thing to do first.

| Where | What |
|-------|------|
| **The diff itself** — do this first | The pixel comparison is pure Python looping over 38,400 pixels per frame. Vectorise it with numpy: likely 50–100× on the comparison step, bigger than any parallelism, and it makes every parallel worker cheaper. |
| The chip scoreboard | 43 independent captures, run serially today. With one build (pair 14) they are embarrassingly parallel, bounded by memory — which stream-not-store (pair 13) makes small. |
| The suite | 18 independent checks, run serially. Same. |
| The audit's extra runs | Isolated + integrated (pair 9) and the negative fixture (pair 10) triple the captures per check, all independent. |
| Lag searches | Each candidate lag's diff is independent. |
| **Where it does not help** | Agent-level edits to the same file. Worktrees made parallel agents safe; they did not make merge conflicts free. Research and measurement fan out cleanly; concurrent edits to `battle.rs` do not. |

## First job after the audit

Bring **all existing work** into the harness framework of pair 6 before anything new: every current check and every chip fixture rewritten as a full-screen, every-frame call into the one harness, aligned on the battle-started marker, with its UI standardised or blanked so the whole 240×160 reads zero.

## Parked

- **Audio** — not ready to work on; dropped for now (2026-09-08). The `audio` check stays in the suite at its recorded number so it cannot silently regress, but no effort goes into it until this is lifted.

## Execution plan (2026-09-08)

Waves are grouped so no two concurrent agents touch the same files. Each agent works in its own worktree.

**Wave 1 — foundations, four agents in parallel**
- `harness-diff` (tools/chip_compare.py, tools/mgba_capture.c): numpy-vectorised diff; `--watch addr:len` per-frame RAM readout; streaming diff mode; automatic retry of a short capture. Pairs 13 + optimisations.
- `marker` (src/ only): the ROM writes a battle-started marker and a battle frame counter to a fixed RAM address every frame. Pair 1.
- `states` (tools/states.py, new): a manifest of every save state as (base ROM, base state, script, cheats, frames), regenerated with `--savestate`; plus an earlier RESULT state. Pairs 4, 5.
- `roms-and-captions` (tools/build_roms.sh, tools/captures_manifest.py, web/): timestamped ROM labels newest-first; captions name the canon variant. Pairs 8, 16.

**Wave 2 — after wave 1 merges**
- `fixtures-as-data` (src/): one ROM reads a fixture descriptor from RAM; the `demo-*` flags go; the sterile HUD stub goes. Pairs 6, 14, 17.
- `harness` (tools/regress.py rewrite): one `run(rust_init, canon_init, frames)`, full screen every frame, aligned on the marker, no `want`, negative fixture per check, provenance count, gallery written as output, isolated + integrated runs. Pairs 6, 7, 9, 10, 11, 12.

**Wave 3** — migrate every existing check and the chip scoreboard into the harness; all must read zero. The "first job after the audit."

**Wave 3 — two agents in parallel (launched 2026-09-08)**
- `migrate-checks` (tools/harness.py, tools/allowlist.py): port every `regress.py` check and the 43-chip scoreboard into the harness table as descriptors; isolated runs must read 0; integrated numbers reported honestly and allowlisted with tickets where they are not yet 0.
- `fixture-gaps` (src/): the FIXTURE.md fields added after wave 2 — offered deck, start-at-results, banner_at — and the HUD standardised so integrated runs can reach zero.

Then a final step: delete the `demo-*` flags and `tools/regress.py` once the harness reads zero through descriptors for everything they covered.

Note from the wave-2 merge: the fixtures-as-data change moved boot timing by one frame, and the two checks still on a HARDCODED lag (`cursor`, `audio`) moved with it — `cursor` 0 -> 602, all of it on one frame of 170, lag still a sharp minimum. Every marker-aligned check was untouched. Pair 1 demonstrated on the day it landed; `regress.py` is left reporting the failure honestly until the port replaces it.

**Wave 3b — driving the isolated numbers to zero (launched 2026-09-08, after both wave-3 branches merged)**
Measured from main at 9d2e623, full screen, isolated: only `opening` and `rollup` read zero. The rest, and the work split:
- `zero-tools` (tools/harness.py, states.py, mgba_capture.c, chip_compare.py, allowlist.py): the 38-chip shared baseline of 14388 (state artifact, unverified) -> a rebuilt state from the manifest; wire `window`/`card`/`result` to the new descriptor fields (they still read 161790/93713/779747); a one-BG-layer-plus-OBJ capture mode for `cursor` (621404), `popup` (107511), `wave` (288491); localise `tiles` 538, `field` 1048, `buster` 3172, `warp` 9198, `chip-use` 9514.
- `zero-src` (src/): custmatch/cardname palette residue at window-open (371/862 px on two frames); `banner` 2248 over 58 frames through banner_at; the untagged files' provenance; the two fitted gauge constants (A8) traced in the disassembly.

**Wave 3c — the last mile to zero (launched 2026-09-08, after wave 3b merged at 9f0b057)**
Every residue is now localised to frame and region; what remains splits cleanly by side.
- `zero-enemy` (tools/, incl. patch_sterile.py): the deleted-enemy artifacts are one root cause behind the chip baseline (14388), `banner` (2248), `popup`'s exposed HP digits and the family-0x15 chips (~105k, all OBJ). Route: a sterile ROM in which the enemy is never spawned, a fresh chip state from the manifest by real inputs, the second attack gate found with a trace mode in mgba_capture if needed. Also `result` through the new `result_elapsed` field (+56) aligned to RESULT_ARRIVAL's slide-in.
- `zero-layers` (src/): put every element on the BG layer canon uses (pair 2 -- `--only-bg N` is only symmetric if the layers match), which also fixes window/card's per-frame constant; implement `result_elapsed`; then the localised ROM-side residues: the navi idle-pose artifact at canon ~164 (field/buster/chip-use), warp 9198, chip-use's impact, tiles 538, wave's panel lighting (BG3 244980), mettaur 42175, the five chip outliers; and the gauge counter's zeroing at battle start.

**Wave 3d — the two follow-ups 3c sized (launched 2026-09-08 at the user's "do both")**
- `bg3-merge` (src/: battle.rs, hudtiles.rs, custom.rs, results.rs, hud.rs, main.rs): HudTiles + Custom + Results on ONE background at canon's BG3 (P1, one tilemap), scroll-compensated; then `--only-bg N` is symmetric on both sides (pair 2) and window/card's per-frame constant should go.
- `mettaur-ai` (src/: ai.rs, actor.rs, field.rs, spr.rs, shot.rs, emotion.rs): the real Mettaur -- a 5-state RNG-gated machine (sub_8109FD6, byte_8109F46) -- seeded from the canon state's RNG through the new `rng` descriptor field (+58); behind `mettaur` 42175 and most of `wave` 288491.
- `fresh-state` (tools/) continues in parallel: the empty-field fixture, and whether a chip fires with no live target.
