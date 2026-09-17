# Daily digest for 16 September 2026

This project rebuilds the battle engine of Mega Man Battle Network 6, a Game Boy Advance game, as new code in Rust. The rule is exact: a scene played by our version must match a recording of the original game pixel for pixel, frame by frame. Small AI agents do the work in tickets, each a bounded task; a ticket ends finished, half-done, blocked, or as a dead end that taught us something.

This covers 06:01 on 16 September to 06:01 on 17 September. In that window the agents closed 49 tickets: 15 finished, 10 half-done and kept, 24 blocked or dead ends. Every number below was measured by the automatic comparison against a recording of the original game.

## The small hard-hat enemy's first moves

The Mettaur is the first enemy most players fight: a small virus in a hard hat that hops to a new square, waits, and swings a pickaxe that sends a shockwave along the floor. The original game runs it through a behaviour routine, a function that decides each frame whether it moves, waits or attacks. If our copy decides one frame late, the Mettaur moves out of step with the original, and a player would feel that.

To find these slips we use the trace, a frame-by-frame record of each run's internal values that shows where two runs first differ. An earlier port of the hop routine moved that first difference from the opening frame to frame 17 (at 60 frames per second), and cut the count of mismatched internal values across the fight's phases from 1387 to 1370 (T50). A second attempt added the next branch of the decision code, but that branch never ran, because our Mettaur was still stuck in its "appearing" state at that point (T53). The next agent found what happens at frame 17 in the original: the Mettaur tries a hop, is refused, and the game writes action code 0x08 where ours writes 0x10 (T68). The agent after that found the two lines in our code that cause this: a "busy" check that stops the Mettaur too early, and a fixed value that labels "appearing" wrongly. It ran out of its tool budget before changing either (T74).

Enemies also come in stronger versions, or ranks. A count of the game's enemy tables found 187 distinct pairs of behaviour and rank, six for most behaviours. It also showed that the Mettaur we had recorded doesn't use the behaviour slot the ticket assumed (T58). One follow-up agent crashed while trying to read notes that didn't exist (T92). A second one succeeded: by changing one story flag and one value at frame 60, it made the game load an encounter with a rank-0 enemy of behaviour 4 at frame 69. That enemy's health, 0x5a, matches the game's table exactly, and two builds gave identical 40-frame runs with 0 differing pixels. The seven reference scenes that every change must leave alone were unchanged (T87).

The Gunner, a second enemy type, has a patch of wrong pixels in the left half of the chip window. The difference jumps about frame 157. The fix needs a meter value that our comparison tool cuts down to a single byte, and changing that tool was outside the ticket's limits (T55).

## MegaMan's own timing

The hero has countdowns too: how long he stays stunned after a hit, and when his controls come back. One of those countdowns used to be an 11-frame guess. The measured version was finished but couldn't be merged, because someone's unsaved work was sitting in the main copy of the code (T66). A later agent traced where the countdown really comes from: when the stun ends, a handler sets a timer to 10 and counts it down one step at a time (T67). That work had already replaced the guess, so trying to merge the older version only produced conflicts and was closed as already solved (T88). A gate on the fight-phase value was found to be merged already, too (T89). Before that, an agent looked for the moment MegaMan uses a chip about frame 250 and found 67 places where his state is written. None of them gave a fix (T63). An attempt to record the shuffled battle folder broke the chip-window cursor scene: 29 differing pixels where the original has only 1 (T59).

## Program Advances

Choosing three matching chips in the chip window, where the player picks attacks for the next turn, can combine them into one powerful attack called a Program Advance. The game's own recipe tables list 63 of them. 33 need exact chip matches and 30 need chips with codes in a row (T71). The saved starting point for testing this was added, a copy of the chip window that differs by one byte (T80). A later attempt ran out of its tool budget while checking the tables again and changed nothing (T86).

## Chips read from data

The game has 411 battle chips, and each one's behaviour comes from its data record. Our copy often picks a chip's behaviour by its ID number. That works, but it isn't how the original does it. An audit of the 43 chips that already match pixel for pixel found that only 11 read their record (T57). AirShot was switched over cleanly (T52). Vulcan and Recov each looked correct but changed the chip-window cursor scene. That scene has a known one-frame, one-pixel flicker (the cursor tear) that shifts when the program's layout moves: to 6 pixels with Vulcan (T54) and to 7 with Recov (T73). A test that added 256 unused bytes to the program showed that code size alone doesn't move the flicker (T56). The cursor break in the Cannon attempt was traced to an undone Barrier change (T51).

AreaGrab and Invisibl were first ported and checked (T61). They were then merged with a 96-byte block of padding that brought the cursor scene back from 20 differing pixels to 1, while five related chip scenes still matched (T78). A notes fix was ready but couldn't be merged for the same unsaved-work reason (T62). Among 84 untested chips, only StepSwrd qualified (T75). Its scene then showed 670 differing pixels, so the guess that no code change was needed was wrong (T85). The TrnArrw arrows looked like one group, but reading the data showed TrnArrw3 belongs to Muramasa's group (T91). The agent sent to port the other two arrows crashed twice (T94).

## Status effects

Some attacks blind, confuse or freeze a target. Forcing blindness on the enemy in the original gave 262,824 differing pixels over 240 frames, starting at frame 139 (T60). Blinding the player instead hides the Mettaur completely: 72,194 pixels over 90 frames (T64). Our version of that scene still didn't match, and moving the check changed the cursor flicker, so after two tries the work is on hold (T69). For confusion, the flag bit was found along with the code that reads and sets it (T72). A follow-up found that setup code the ticket expected didn't exist. It read the routine that keeps an enemy confused for four ticks and lets it act normally on the fifth (T81). Another follow-up found that the ticket had the wrong bit pattern and named a test scene that doesn't exist (T83). For being frozen in place, the flag's name was added, but the rest needed files the ticket didn't allow it to change (T84).

## Navis

Navis are the game's boss characters. All 25 slots in their table are now listed, 12 of them named (T76). Porting the first two Navis stopped on the same four missing pieces: the fight record that starts them, an enemy type for them in our code, an entry in our test setup, and the introduction banner, which never moves on (T79, T82).

## The game's data

Formations are the enemy layouts for each encounter. All 1076 were matched to the 1240 records that use them, with 52 leftover bytes identified (T65). The byte that picks each fight's background art was traced to the game's lookup tables (T70). Building the first formation scene used up its budget after the measurements (T90). A follow-up agent kept trying to read a file that didn't exist (T93). In the game's disassembly, the original game's code turned back into readable text, 13 of 478 unnamed fields got names, updating 6,328 places where they appear, and the rebuilt game stayed identical (D10). The project's old journal was split up, and 33 references now point to where each fact is recorded (D9). For netbattles, the two-player link fights, a 209-line research note lists two candidate state bytes and separates the chip-trade code used in fights from the unrelated trader in the overworld (T97).

## Sound

The goal also covers sound. A new tool compares two sound recordings one sample at a time. It passed all 4 checks and confirmed the recordings are 16-bit stereo, with an advertised rate of 65536 samples per second and a measured rate of about 96000 (T95). The first real sound comparison used a value it never received, so none of the 7 scenes ran and nothing was measured (T96).

## New recordings

![T57 audited which verified AS DATA chips really share a record's bytes: family 0x15 (Barrier et al.) was dispatching on chip id for AreaGrab/Invisibl while its three barriers were already record-driven, so tools/inventory.py's AS_DATA_FAMILIES dropped 0x15 (14 -> 11 verified-as-data chips). Canon keys chip behaviour off the ChipDataArr record (family/subfamily/params); the ROM and every pixel row are byte-identical before and after -- this landing changed the classification, not the picture.](../captures/chip-cannon-progress.gif)

![cursor (isolated), FAILED: per-frame max 1 px, total 1 px over 170 frames. Alignment: canon frame 15+k, rust frame 8(marker)+237+k. canon](../captures/cursor-isolated.gif)

![T87: the ai_index-4 virus rank previously unreachable by T58's frame-60 lever is now fielded - canon EVENT_681 flag poke swaps the encounter root to a 12-record ungated list and lever 0x37a picks rec3; slots populate at frame 69 with HP byte-matching off_8109150[4); recording-only, all guard rows identical](../captures/mettaur-progress.gif)

## Where the whole thing stands

The game is compared against the original in 72 recorded scenes. 61 of them now match pixel for pixel in every frame.
The scenes that still differ: opening (inside a full fight); field (inside a full fight); field-bg1 (on its own); field-bg2 (on its own); field-bg3 (on its own); warp (inside a full fight); buster (inside a full fight); chip-use (inside a full fight); gunner (on its own); gunner (inside a full fight); cursor (on its own). Each is a known, measured gap with a ticket behind it.

## What it cost

The agents run on prepaid subscriptions. Charm Hyper:  0.6 of 250 credits (249.4 used today, 100%).
tickets 44, landed 23, pi spend $16.64, $/landed 0.723, NEGATIVE+BLOCKED 17 (39%).
