# Daily digest for 15 September 2026

This project rebuilds the battle engine of Mega Man Battle Network 6, a Game Boy Advance game, as new code in Rust. The rule is exact: a scene played by our version must match a recording of the original game pixel for pixel, frame by frame. Small AI agents do the work in tickets, each a bounded task; a ticket ends finished, half-done, blocked, or as a dead end that taught us something.

This covers 10:50 on 15 September to 03:45 on 16 September. In that window the agents closed 48 tickets: 23 finished, 4 half-done and kept, 21 blocked or dead ends. Every number below was measured by the automatic comparison against a recording of the original game.

## Following one whole fight, frame by frame

Most of our comparisons look at a short slice of battle. The hardest test is a whole fight, where our version and the original game receive the same button presses for 540 frames (nine seconds, since the game draws 60 frames per second). When a scene like that goes wrong, counting differing pixels only tells you that something broke. To find where it broke, we use a trace, which is a frame-by-frame record of the game's internal values, such as what each character is doing and its timers. The first frame where the two traces disagree points at the code to fix.

Yesterday's attempt at this never got started, because the tools were broken. The comparison tool rejected the whole-fight scene by name, the tool that maps where pixels differ could not pick out single frames, and the trace reader crashed on a memory address (T44). Today all three were fixed. To make sure the repaired comparison was not blind, it was run with one recording shifted by a single frame, and 6 of the 10 values it watches moved (T47). The same run showed Mega Man's action, animation and timer disagreeing on 76, 78 and 270 frames. The game's random-number generator first falls out of step at frame 124.

A follow-up ticket then named the first difference: it comes on the scene's very first frame, which is frame 11 of the original's recording. The Mettaur is a small hard-hatted virus (a basic enemy). Each enemy carries a number saying which action it is performing. In the original, the Mettaur's number is 10, the routine that carries out its hop. In ours it is 0, meaning "hidden." Everything afterwards follows from that one byte: 10,827,099 differing pixels across the 540 frames, with 35,308 on the worst frame. The obvious next job is to port that hop routine. Along the way, a one-line breakage in the difference-mapping tool, left by the earlier repair, was also fixed (T49).

## Gunner, the enemy whose battle never starts

Gunner is a virus that aims a crosshair and fires. Its scene is far from matching: 2,105,613 differing pixels over 130 frames. Earlier, the value that fills the custom gauge was named. That gauge is the bar that fills before you can pick new chips, and our setup now carries the original's full value of 0x4000. All 12 scenes stayed unchanged (T32).

The goal of getting Gunner below 1,500,000 pixels failed for a real reason. Our recording of the original is lined up against ours by choosing an anchor frame. The anchor was tried at 78, 80, 33 and 151, and 80 was already the best. Watching the original's memory showed that Gunner's action number never reaches 10, its attack, in 300 frames: the recorded battle never goes live. The layer that draws the chip menu also appears at frame 6 in ours but frame 77 in the original. That 71-frame gap is wider than the 40 frames the alignment searches (T37).

Two attempts to find what switches that layer on came back empty. The first watched writes to that region of memory (T39). The second watched the hardware registers that control the layer between frames 77 and 129 (T42). A last idea was to align the recordings on Gunner's first attack. It turned out the alignment already does that, and the change of attack stage happens inside the attack routine itself, so there was nothing to adjust (T45).

## Battle chips read from the game's own data

Battle chips are the attacks a player picks: swords, cannons, bombs, barriers. The original game keeps each chip as a record in a table, holding its power, its family and a subfamily number. Our code used to special-case chips one by one, which was correct but not faithful to how the game works. The project goal is to read the record instead.

The sword family went first: eleven chips now driven by their records (T17). A follow-up made a mismatched data file stop with a clear error instead of silently misreading (T19). Heal, Barrier and Vulcan were next, and the attempt showed that their records do not hold the amount at all. Every Recov chip lists power 0, and each Barrier carries 1, 5 or 7, which are row numbers into a separate hit-point table (T28). The three Barriers also share subfamily 4, so that number cannot pick their row (T34).

Cannon, HiCannon and M-Cannon were checked byte by byte against the table, and their powers of 40, 100 and 180 matched. The agent then ran out of its 60-step budget before editing any code (T36). A second agent made the edit, but the cursor scene got worse, so the change was kept unmerged (T38).

Today two families landed. For bombs, the chip's power now comes from its record. Before the merge, the two Energy Bomb scenes were failing by 6,895 pixels. Afterwards, all six bomb scenes match in every pixel, and 18 other chip scenes were unchanged (T46). For barriers, the row number 1, 5 or 7 now selects 10, 100 or 200 hit points and a teal, gold or pink shield. All three barrier scenes match over their 80 frames, 40 other chip scenes are identical, and the count of chips read from data rose from 10 to 13 (T48).

## The battle floor's panels

A battle is fought on a grid of panels, and panels can be cracked, broken, or holy (holy panels halve damage). A table of 13 flag words was found, one per panel type, but the project's count of panel types it has accounted for did not move (T14). Searching for code that sets each panel type found only broken and cracked being written. Five types have no writer at all, which suggests the real list is 8 types, not 13 (T33).

A port of "a cracked panel breaks when you step off it" could not be tested. The machine lacks the ARM toolchain needed to build a game image (T35). A holy-panel port found that the ticket had cited the wrong routine: the right one handles barrier breaking and is called from 6 places. No recorded fight ever stands on a holy panel, so no scene could measure the change (T40). A second approach, setting the panel type's flag bit before damage is applied, also closed as a dead end with only its notes kept (T41).

## Opening the chip menu

The sequencer is the part of the game that steps a fight through its phases, such as the chip-selection menu (the "custom screen") and its countdown. Our menu opens on a 60-frame countdown we measured rather than derived. Replacing it with the original's chain of events failed: the trigger was not in the memory being watched, and our menu phase starts around frame 124 against the original's frame 31. Across the fight, 273 of the 540 frames differ in the sequencer's state (T7y). A third ticket on this was held back under a rule that pauses after repeated dead ends (T7z).

Reading the original closely then overturned the model behind all these attempts. Its phases do not count frames. They wait for "still busy" flags to clear. The spans of 2, 100, 3 and 60 frames we had observed are simply how long on-screen banners live. The phase position was also stored one byte away from where we had been watching (T26). A port built on that corrected picture was sound and removed the 60-frame constant, but it broke another scene, so it is kept unmerged as a starting point (T27). Driving both games from one scripted button log is blocked until a person plays that scenario by hand (T20).

## The enemy's HP numbers

Enemy HP digits in our opening scene appeared too early: four extra digit sprites. A fix gated them on the original's condition and cut the full-fight version of the opening scene from 25,829 differing pixels to 18,740. But it pushed the cursor scene from 1 differing pixel to 54, so it stayed unmerged (F43). Gating on the original's battle-state switch instead kept the gain without that regression (F44). The same idea for digits updating when the enemy takes damage came back a dead end (T43).

## The scrolling backdrop

Behind every battle is an animated, slowly scrolling background. Two supposed small residues turned out to be misread: the chip-use scene inside a full fight differs by 275,307 pixels, not 2 (F41), and the field scene by 158,935, not 1,589 (F42). That figure was re-measured at 158,930 and is now checked automatically (F45). Reading the scroll registers directly proved impossible, because the emulator cannot read them back (F46).

The backdrop art turned out to step every 8 frames in both games, but at frames 5, 13, 21, 29 and 37 in the original against 8, 16, 24 and 32 in ours (F47). Our seven animation steps are the game's own tile lists, unchanged (T22). The original starts its animation timer at 4 where we start at 8 (T23). Setting ours to 4 cut the field scene from 158,930 to 155,048 pixels (T24). Correcting the scroll starting position then took one backdrop layer from 354,486 to 4,800 and the field scene from 155,048 to 32,623, a 79% drop (T25). The remaining 4,800 on that layer sits in the top 20 pixel rows at the first frame, identical on two layers (T29). The frames 0 to 2 part of what remains, 15,823 pixels, was measured and shown not to be scroll (T31).

## Cataloguing the game's data

Status effects are the conditions a character can be under, such as flinching or super armor. Of 69 status flags, 39 have code that sets them and 37 have code that reads them (T18). A table of 47 NaviCust program entries was found (NaviCust is the system that adds abilities to Mega Man), though the project's counts did not change (T15).

## Tools and tidiness

Several tickets left behavior untouched. They named bare numbers (Q1), turned a byte of scene switches into a named type (Q2), reduced the code's unchecked memory access from four blocks to one (Q3), described a 40-byte state record by field names (Q4), removed 13 dead names (Q5) and corrected 11 stale references in comments (T30).

A suspected run-to-run drift in the comparisons does not exist. Five scenes captured twice gave identical pixels (F48). The cursor scene's lone differing pixel is also real rather than noise: it sits at the same spot in frame 97 on every run (Q6). Fixing that pixel would mean redrawing background tiles mid-frame, and that ticket is waiting on a decision (T21).

## New recordings

![T48 DONE: Barrier family reads AttackParam1 from data/ChipDataArr.s:5521/5552/5583. Dispatch on family=0x15, subfamily=0x04. chip-barrier/barr100/barr200 all PASS 0/0/80/41067.](../captures/chip-barrier-progress.gif)

![T46 DONE: Bomb family reads attack_power() + element from data/ChipDataArr.s:1646/1336/1367/1398/1708/6265. Before: chip-energbom/chip-megenbom FAILED 6895/146. After: all 6 PASS 0/0/N.](../captures/chip-minibomb-progress.gif)

## Where the whole thing stands

The game is compared against the original in 67 recorded scenes. 60 of them now match pixel for pixel in every frame.
The scenes that still differ: opening (inside a full fight); field (inside a full fight); warp (inside a full fight); chip-use (inside a full fight); gunner (on its own); gunner (inside a full fight); cursor (on its own). Each is a known, measured gap with a ticket behind it.

## What it cost

The agents run on prepaid subscriptions. Charm Hyper:  0.7 of 250 credits (249.3 used today, 100%).
tickets 18, landed 13, pi spend $6.71, $/landed 0.516, NEGATIVE+BLOCKED 8 (44%).
