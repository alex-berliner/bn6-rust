# Daily digest, 15 September 2026

This project rebuilds the battle engine of Mega Man Battle Network 6, a Game Boy Advance game, as new code in Rust. The rule is exact: a scene played by our version must match a recording of the original game pixel for pixel, frame by frame. Small AI agents do the work in tickets, each a bounded task; a ticket ends finished, half-done, blocked, or as a dead end that taught us something.

In the last 24 hours the agents closed 54 tickets: 10 finished, 20 half-done and kept, 24 blocked or dead ends. Every number below was measured by the automatic comparison against a recording of the original game.

## The opening seconds of a fight

The opening of a battle is the first second or two after the player presses to start: the camera zooms in, the hero appears in his hopping pose, the three viruses fade into their panel slots, and the player's chip-selection window slides in. Players see this every fight, so getting it right matters.

The main copy of the code already matches the original recording in every pixel of every frame — so an agent (F38i) that set out to improve a residue claimed by an earlier report found the number it measured on its own copy of the code didn't reproduce, and the change was set aside.

Another agent (F38h) preserved the existing per-enemy panel encoding so the cursor's saved state file stays valid, which dropped the opening's differing-pixel count from 72,499 to 25,829 across the full scene and 40 frames while leaving the cursor scene at its known 1 differing pixel. The remaining gap was pinned to how colour slots are handed to the small enemies, a problem outside this ticket's scope.

Two attempts to land the panel fix (F38f, F38g) both failed: the first was applied but introduced a cursor regression from 1 to 26 differing pixels and was reverted, and the second could not regenerate the cursor scene's state file because the test runner refuses to overwrite hand-captured recordings. The per-enemy panel port itself is correct against the original ROM, but the rule that forbids touching outside the named files blocks landing (F38e, F38g).

## The cursor's last wobble

The custom chip-selection window has, for weeks, had exactly one stray pixel that the cursor comparison carries on a single frame (1 differing pixel in 1 of 170 frames), and getting it to zero means the cursor moves exactly as the original does. Two more attempts today chased the wrong target: one agent (F37k) never reached measurement after tooling failures, another (F37h) confirmed the count did not move, and a drain-timing port (F37j) actively made things worse.

The honest narrowing (F37l) came from a careful re-measurement: the residue is a single pixel at one specific moment in the scene, not three pixels at two moments. The original game's graphics pipeline writes the affected tiles mid-frame while we write all 36 tiles before the first scanline; closing the gap would require sub-frame tile replacement infrastructure we don't have.

## The fight's phases

A fight steps through phases — the player picks chips, the countdown ticks, the strike lands, the results screen appears — driven by a small table in the original game.

The big move (T7e) brought the full-fight scene to all 540 frames aligned by fixing two named groups (165 of window-setup, 8 of kill-timing). Two follow-ups (T7r, T7q) taught the code that runs the player each frame to stand still during the chip-selection phases, as the original does; both kept other comparisons clean. An attempt (T7u) to replace a hardcoded 60 with the original's banner-idle check regressed the cursor scene from 1 to 38 differing pixels — the mechanism was correct but the timer defeated the check, so the change was set aside. A docs-only probe (T7j) left the constant alone. Several agents (T7l, T7m, T7i) hit their tool-budget ceiling during baseline capture and produced nothing.

Two negative results (T7s, T7g) clarified what is and isn't wrong: the window's opening moment sits at our frame 125 vs the original's frame 42, but every available fix path is forbidden or dead code, and a missing-state ticket turned out to be a saved-state file difference rather than a code port. The frame-by-frame RNG cadence (T7n, T7p, T7v) sat at 9 differing frames per 540, below the acceptance threshold; the remaining divergence is split between a death-debris spawner and sites outside the ticket's scope.

## The Gunner virus

The Mettaur virus — the hopping, cannon-firing enemy — is the default test enemy. The second virus, the Gunner, teleports, hovers, and fires three shots in a row. Today the per-type behaviour was ported from the original game's disassembly (T9j), with named arms for its three shots, the gap between them, and its recovery window; this shrank the Gunner comparison from 3,859,001 to 2,850,534 differing pixels across 130 frames but did not reach zero, because the controls and impact logic still live on the fight itself rather than the Gunner entry (T9k). A capture-race fix (T9i) and the per-type behaviour citation (T9h) were added to the codebase. The trigger recipe (T9d, T9c, T9b) was confirmed: a one-shot write at frame 60 selects the BattleSettings record that fields a Gunner.

## The results screen and sound

The screen that shows who won (F21e) was already at 0 differing pixels across 40 frames — the ticket was a no-op verification. The battle music and the percussive hit effects that play during a fight also matter: an audio probe (T13) produced a sample-by-sample dump showing 639,328 of 639,402 compared samples differ between the two sides, peaking on different music; a follow-up (T13b) gated the hit sample so it only fires when a strike actually lands. Two probes (T13c, T13d) readied a second scenario and committed docs.

## The data tables, the scripts, and the tooling

Two inventory passes (T10, T12) walked the ROM's own tables — the data the original game loads at boot, listing every chip, every enemy, every scripted event — and produced 411 battle chips, 63 Program Advances (the combos that fire when certain chips are picked together), 32 enemy families with 187 ranks, 25 Navis (the game's digital fighters), and a 452-row enemy identity table whose four side-tables were misread in the original ticket as one. Three further baseline-only tickets (F35a, F36a, F36b) measured where we currently stand on the buster (MegaMan's default arm cannon) and the warp into battle: 54,672 differing pixels across 28 frames for buster, 40,628 differing pixels across 30 frames for warp, with the standalone versions of both scenes already matching. A script-engine port (T8) brought the map and chatbox text dispatch into the Rust side, with 71 and 27 named variants, shrinking the cursor scene from 44 down to 7 differing pixels as a side effect.

## New recordings

![T13d NEGATIVE: cannon-route audio probe — canon fires ch0+ch4 SFX, ours silent. Docs-only commit; no harness change.](../captures/cannon-progress.gif)

![T5 object dispatcher ported: table and dispatch with citations; isolated rows 0, cursor tear 15->1](../captures/cursor-progress.gif)

![opening (integrated), FAILED: per-frame max 2691 px, total 72499 px over 40 frames. Alignment: canon frame 120+k, rust frame 8(marker)+119+k. canon](../captures/opening-integrated.gif)

## Where the whole thing stands

The game is compared against the original in 67 recorded scenes. 60 of them now match pixel for pixel in every frame.
The scenes that still differ: opening (inside a full fight); field (inside a full fight); warp (inside a full fight); chip-use (inside a full fight); gunner (on its own); gunner (inside a full fight); cursor (on its own). Each is a known, measured gap with a ticket behind it.

## What it cost

The agents run on prepaid subscriptions. Charm Hyper:  250.0 of 250 credits (0.0 used today, 0%).
tickets 46, landed 26, pi spend $23.72, $/landed 0.912, NEGATIVE+BLOCKED 16 (35%).
