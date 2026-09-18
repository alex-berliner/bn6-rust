# Daily digest for 17 September 2026 — 9.0% of the battle engine's running code is ours, +0.2 points since 2026-09-17

This project rebuilds the battle engine of Mega Man Battle Network 6, a Game Boy Advance game, as new code in Rust. The rule is exact: a scene played by our version must match a recording of the original game pixel for pixel, frame by frame. Small AI agents do the work in tickets, each a bounded task; a ticket ends finished, half-done, blocked, or as a dead end that taught us something.

This covers 10:46 on 17 September to 10:46 on 18 September. In that window the agents closed 70 tickets: 11 finished, 27 half-done and kept, 32 blocked or dead ends. Every number below was measured by the automatic comparison against a recording of the original game.

## The one-pixel flicker that decides what lands

Every change is judged by an automatic comparison. It rebuilds our game, plays a recorded situation (we call these scenes; one might be the first seconds of a fight), and counts the pixels that differ from a recording of the original game. One scene, 170 frames of the player moving the cursor in the chip-selection menu, has long carried a tolerated glitch called the cursor tear: exactly 1 pixel differs, in a single frame. The tear comes from the moment our code copies the screen's tile map into video memory. Its timing depends on how the compiled program is laid out, so almost any code change moves it. The project's rule is that no change may make any scene worse, so this one pixel decides the fate of much of the work below.

An earlier fix inserted a tuned delay of 17 empty loop turns, which put the tear back at 1 pixel (T111). Every attempt to make the tear independent of program size has since failed. Copying only the parts of the map that had changed pushed the cursor scene to 16187 differing pixels. It also broke a window-closing scene that had matched perfectly for months (T118). Waiting for a fixed screen line couldn't hit the right moment, because the timing that matters is finer than one line of the display (T118b). Deleting the delay outright gave 31 differing pixels (T124). A sweep of delay values on another version of the code found that 13 and 21 both restore the 1-pixel tear, but the backdrop scenes shift with every value tried (T141).

## The fight's phases and its opening

A fight moves through phases: the chip-selection window, the "battle start" banner, the fighting, and the results screen. The part of the game that steps through them is the sequencer. To find where our version first departs from the original, agents use the trace, a frame-by-frame record of the game's internal state. Re-measured on a full 540-frame fight, the sequencer disagrees in 273 of those frames, and the first disagreement is at frame 31. The cause is that our version never enters phase 0x20, the moment the chip window reopens once the custom gauge fills (T125). A second map, made on a scripted opening, found the sequencer disagreeing from the very first frame (T147). That scripted opening only exists because of an earlier discovery: pointing the original game's own encounter picker at any stored enemy lineup makes it field that lineup (T131).

The banner came next. Our version waits a fixed, hand-tuned 60 frames before starting the fight, while the original checks whether its banner has finished. With the original's check ported, the sequencer matched for all 40 frames of the opening (T152a, kept). Landing the check itself moved the cursor tear to 32 pixels, though (T152c). Measurements showed that showing the banner immediately lands the release 2 frames away from the original's 60 (T152b). A fix built on that brought the cursor scene down to 3 differing pixels. But the window-closing scene went from a perfect match to 41627 differing pixels, because our banner stays up for 29 frames in which the original shows none (T162). The attempt to add phase 0x20 never started: the agent returned an empty answer (T178).

## Viruses

The enemies in these fights are viruses. The best known is the Mettaur, a hard hat that hops and sends out shockwaves. Each type comes in stronger versions. A new scene with three rank-1 Mettaurs was recorded (T151b). It differs by 677252 pixels over 70 frames, because our game still draws the basic Mettaur. The plan is to unpack the stronger version's sprite sheet and read its hop delay from the original's table, where rank 1 waits 0x18 frames instead of 0x1e. One attempt spent its whole budget on research (T151a), one redid the recording by mistake (T151c), and one agent never produced any output (T165).

For a third virus type, the agent chose the family numbered 0x02, after the Mettaur's 0x01 and the Gunner's 0x17. It found that this family's behaviour routine has 4 handlers of its own plus 8 shared ones, then ran out of budget (T181). Work on the family numbered 4 did get its spawn and first handler wired, leaving a scene with 488098 differing pixels. It was kept unmerged because the cursor tear jumped (T121). The ticket that planned the same work was dropped as a duplicate (T120b). The earlier attempt had stopped because the file it needed was outside its allowed scope (T113). A later follow-up found its premise was false, because that wiring had never reached the main code (T144).

## Navis

Navis are the boss characters who fight the way MegaMan does. The first Navi work found where the game branches between Navi and virus behaviour, but it was kept unmerged when the cursor scene went to 23 differing pixels (T134). A second pass landed a scene that fields a Gunner through the Navi branch. It differs by 2092176 pixels, down from the plain Gunner scene's 2105613 (T145). Today the Navi's behaviour tables went in as pure data, together with a second scene. That scene gives exactly the same count as the first, because our Navi code still passes through to the old behaviour (T182). Planning for a real Navi spawn with 900 hit points ran out of budget (T153). A search through the original game's data for any encounter that spawns a Navi found zero. So a Navi fight will need either a patch to the game data or a faked encounter record (T166).

## Battle chips and damage rules

Chips are the attacks a player picks each turn. Cannon, HiCannon and M-Cannon are now chosen by their family byte, 0x14, instead of by hard-coded chip numbers, and all three scenes still match perfectly (T180). The thrown chips, such as BugBomb, were converted the same way and all 12 chip scenes matched, but the cursor scene went to 44 differing pixels (T128). A survey found that a battle can actually reach 237 chip numbers, not 411 (T116).

Elements follow a rock-paper-scissors rule: fire against wood, for example. The multiplier turned out to be additive, so one weakness doubles damage and two triple it (T126). A first port that also changed bombs sent the cursor scene to 16241 differing pixels and was reverted (T146). A port limited to swords and AirShot went to 10 (T146b). A third version, built as a small function the compiler can inline, was merged (T163). No scene shows it yet, because in every existing scene the multiplier is 1.

The battlefield's panels carry types such as poison. The game code that sets panel type 0x8 was found, bringing coverage to 9 of 13 types (T115). The table of 13 panel flag values went in as data, but the scene it called for turned out to compare the wrong code path (T121b). Poison panels now follow the original's own template (T130). The rule deciding which side owns each panel was ported, but the cursor scene went to 38 differing pixels (T129).

Super armor stops MegaMan from flinching when hit. The rule was confirmed in the original, though one claim in the write-up was refuted (T132). A real port brought a new scene to within 1389 differing pixels (T138), and a follow-up got that scene to match perfectly. It stays unmerged anyway, because the cursor scene went to 26 differing pixels (T140). A survey had already listed all 47 upgrade parts that MegaMan can install (T110). The first one, super armor, can't get a meaningful scene for now, because the comparison would be blind to it (T150). The belief that a Counter Hit writes one particular memory byte was false: that byte is the countdown for the face's blink (T148). Four tickets about pushable boxes and holes were refused because the steps they build on were never written (T155, T156, T157, T158).

## MegaMan's face and body

A small window shows MegaMan's emotion, and it changes when he reaches Full Synchro, a charged-up emotional state. The first face was ported and matches (T105). A duplicate of that task was closed (T108). A value once thought to decide the face is in fact a 12-frame blink countdown (T123). The original's face tables were copied out byte-exact (T122). The next face never started, because the agent never built the game (T154).

Transformations now select the right body colours: the original picks a row in the colour palette, and that scene matches (T135). For the charged buster shot, the first scene differed by 2498 pixels (T106). That turned out to be a missing muzzle flash, not the gauge (T114). Porting the flash cut it to 188, but the cursor scene went to 10 (T117). The landing was ruled impossible on its own terms (T120), and the last frame's 188 pixels turned out not to be a timing skew (T122b).

## The results screen

After a win, the game gives a rank and a zenny reward. Both are now computed rather than supplied (T119), after a first version was held up by the cursor scene going to 7 (T112). Porting the original's best-time tables stays unmerged (T119b). For the LOSER screen, setting MegaMan's health to 0 does nothing, because deletion needs the damage path (T127). The screen's timeline was recorded (T136). A port left that scene exactly where it was (T143).

## The backdrop

Two backdrop scenes show a 3600-pixel black band for one frame. It was traced to a display-control write landing between screen lines 14 and 15 (T142), after three narrower theories were ruled out (T133, T137, T139). A related backdrop regression comes entirely from the Navi branch. No partial revert fixes the backdrop without losing the Navi scene or disturbing the cursor (T161).

## New recordings

![T152a PARTIAL: trace eBattleSequencerState_203CA70 40/40 match on battlestart_scripted; entry-park closes sequencer gap via T152 inheritance; cursor kept at documented 1/1/170/186279; canonical is_banner_idle() port left as follow-up](../captures/cursor-progress.gif)

![emotion_syn (isolated), PASS (all zero): per-frame max 0 px, total 0 px over 40 frames. Alignment: canon frame 43+k, rust frame 2(marker)+122+k. canon (sterile)](../captures/emotion_syn-isolated.gif)

![form_cross (isolated), PASS (all zero): per-frame max 0 px, total 0 px over 40 frames. Alignment: canon frame 43+k, rust frame 2(marker)+122+k. canon (sterile)](../captures/form_cross-isolated.gif)

![T163 PARTIAL: damage_element_mult ported (additive model from asm38.s:3478-3520, PRIMARY table from ROM 0x081d7944); inline match arms preserve cursor 1/1/170 and mettaur 0/0/70; element_hit row deferred (no def_elem!=0 fixture yet)](../captures/mettaur-progress.gif)

![result (isolated), PASS (all zero): per-frame max 0 px, total 0 px over 40 frames. Alignment: canon frame 21+k, rust frame 13(marker)+21+k. canon](../captures/result-isolated.gif)

## Where the whole thing stands

The game is compared against the original in 82 recorded scenes. 65 of them now match pixel for pixel in every frame.
The scenes that still differ: opening (inside a full fight); field (inside a full fight); field-bg1 (on its own); field-bg2 (on its own); field-bg3 (on its own); warp (inside a full fight); buster (inside a full fight); buster_charge (on its own); buster_charge (inside a full fight); chip-use (inside a full fight); gunner (on its own); gunner (inside a full fight); navi-gunner (on its own); navi-gunner (inside a full fight); navi-gunner-ai (on its own); navi-gunner-ai (inside a full fight); cursor (on its own). Each is a known, measured gap with a ticket behind it.

## Suggested changes to how the agents work

An automatic reviewer reads each day's results and suggests changes to the agents' setup. These wait for a human to accept or reject them:
- 1. Make the ticket graph machine-checkable — a free gate at admission and in the roundup (new `tools/ticket_graph.py`) (20260918-103759.md)
- 2. Track main's row table in the repo — `tools/pins.py`, so "nothing worse" is machine-checked and a canary costs nothing (20260918-103759.md)
- 3. Pay for discovery at recon price, once, and make the cites reusable — `tools/cite.py` plus a map-before-work rule (20260918-103759.md)

## What it cost

The agents run on prepaid subscriptions. Charm Hyper:  249.3 of 250 credits (0.7 used today, 0%).
tickets 53, landed 31, pi spend $23.01, $/landed 0.742, NEGATIVE+BLOCKED 17 (32%).
