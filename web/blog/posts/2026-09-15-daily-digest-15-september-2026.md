# Daily digest, 15 September 2026

This project rebuilds the battle engine of Mega Man Battle Network 6, a Game Boy Advance game, as new code in Rust. The rule is exact: a scene played by our version must match a recording of the original game pixel for pixel, frame by frame. Small AI agents do the work in tickets, each a bounded task; a ticket ends finished, half-done, blocked, or as a dead end that taught us something.

In the last 24 hours the agents closed 54 tickets: 10 finished, 19 half-done and kept, 25 blocked or dead ends. Every number below was measured by the automatic comparison against a recording of the original game.

## The opening seconds of a fight

A fight opens with the viruses materialising onto the arena, each on the square its formation gives it, each handed a palette slot that fixes its colours. Compared alone, without the surrounding interface, the opening matches; inside a full fight those same 40 frames showed a reported 72499 differing pixels. Two produced only measurements of how the intro assigns palettes and sheets (F38c, F38d). A third found the defect and was blocked from fixing it: we spawn the viruses down a diagonal, where the original's own data gives squares (5,1), (5,3) and (6,2), so the third virus's 24-pixel error is one row of squares, not the animation bug assumed (F38e). Porting those bytes grew our scene descriptor from 64 bytes to 67, a hand-recorded state file for the chip menu stopped fitting, that menu went from one differing pixel to 26, and it was reverted (F38f). The file is hand-captured and cannot be regenerated (F38g), so the squares were re-encoded inside the old size, reporting 25829 (F38h). The last ticket, meant to hand palette slots out in the original's order, found its premise gone: the opening inside a full fight already matches every pixel of every frame, 25829 does not reproduce, and its stub was dropped (F38i).

## The chip-selection cursor

Between turns the fight pauses and the player picks chips from a menu with a moving cursor; our 170-frame recording sits at one differing pixel, a "tear" that wanders and is tolerated for now. Four attempts failed: a re-measurement after the window's marker changed found nothing moved (F37h); two ran out before porting (F37i, F37k); two ports of the original's queued-transfer drain both made the cursor worse (F37j). The fifth described it at last — 1 pixel at (183,5) on frame 97 alone, not the 3 pixels on two frames earlier tickets were told of, frame 37 having been cleaned up by the opening work — and named the cause: the original's queue lands tiles mid-frame, part-way down the screen, while we write all 36 tiles before the frame starts (F37l).

## The phases of a fight

A fight steps through phases — chip window, countdown, fight, banner, results — which the original drives with a numbered state and handler table; both sides' state is recorded frame by frame and compared. The first pass landed those states without moving a pixel, but its evidence did not reproduce; a re-check kept three disagreements: the enemy on frame 0, MegaMan on frame 179, the generator on frame 271 (T7). Porting the window's states from the original's dispatch table fixed the results recording but left 173 of 540 frames of a full fight disagreeing (T7c); a scenario built to close the window showed the original holding a window state far longer (T7d); neither merged. A later ticket brought all 540 frames into agreement, naming the window-opening and kill-timing groups (T7e); merging the old branch afterwards proved pointless, the fault having been the scenario's setup (T7g).

The countdown is still held by a fitted number: we wait 60 frames because 60 was measured, not because the original says so. One confirmed the window's edges without removing the 60 (T7f); one modelled the real leave condition in comments (T7j); one ported it and lost to the banner's 30-frame countdown, which expires before the banner exists, cutting disagreement only from 273 to 256 of 540 and costing 38 pixels in the chip menu (T7u). MegaMan's per-frame work was gated off while the window is up (T7q), his release-edge block moved after his update as the original's order requires (T7o). Seeding the fight with a full custom gauge and a scripted press made the machine walk the window states, improving MegaMan's frame-179 group from 101 differing action values to 76 (T7r), but opened the window on our frame 125 against the original's 42 — an 83-frame drift with no legal repair, the gauge pause being a hardcoded 60 (T7s).

The generator is compared as a cadence — how often each side draws per frame — since one extra draw desynchronises everything after. Its first divergence was named at frame 271, on 10 of 540 frames (T7n); a call-order move took it to 9, under the bar, leaving the follow-up nothing to do (T7p); the last found it back at 14 after the scripted stalls added frames, the cited debris spawner covering 2 (T7v). Three never reached a port (T7i, T7m, and T7l, which meant to seed the original's hop pose on frame 0 so the spawn fade stops parking the enemy's action at zero); one idea was rejected outright, the original's Mettaur starting in spawn action 0x0A where ours sits at 0x00, which changed nothing (T7h).

## The Gunner virus

The Mettaur, the hard-hat virus that sends a shockwave down a row, was the only enemy our engine could field; the Gunner aims a cursor at MegaMan and fires. Fielding one was the whole problem: the recorded battle always yields three Mettaurs, the formation rolled on frame 60, and our scene descriptor could not say a slot holds something else (T9). The lever proved to be the frame counter: poked once on frame 60, the roll picks a Mettaur-plus-Gunner formation (T9b), and that recipe landed with two bits per slot naming each slot's virus (T9c). The poked fight then refused to go live — nothing writes the phase word on either route in, and the phase moves only from a hand-played paused save (T9d). Two follow-ups poked the blocking values directly, moved the phase machine and still got no live fight (T9e, T9f); a third returned three negatives from the attack's settle window (T9g). Its behaviour was ported from the table the original indexes by enemy type (T9h), then as its real routine — a four-arm machine that aims a cursor, locks it, fires 3 shots 10 frames apart and recovers for 24 — taking the recording from 3859001 differing pixels to 2850534 over 130 frames (T9j). Moving the cursor and impact bookkeeping into the Gunner's own data proved relocation only, and the widened signature broke the Mettaur path, pushing the chip menu to 59 pixels (T9k).

## The results screen, and what a full fight puts behind it

The results screen, the window that slides in with the rank and the reward, carried a tracked residue of 102547 pixels over 40 frames; the ticket sent to decompose it found the screen already matching exactly — trustworthy because a deliberately wrong build run alongside still differs, by 111839 pixels (F21e). Two residues exist only inside a full fight: firing the buster matches exactly on its own, but inside a fight it was tracked near 643698 pixels, measured at 54672, and split into 8862 in the chip-name strip and 45810 in the sliding results window (F35a). Warping between panels was tracked at 363658 and measured at 40628, all of it a six-frame ramp where the original's chip-name slide writes its tiles a frame earlier than ours (F36a); a second decomposition put 40302 of those pixels in the scrolling backdrop, so the two readings disagree about which layer owns it (F36b).

## Sound

Audio is compared like pixels: both sides' mixed output dumped and compared sample for sample. The first ran 200 frames: 642914 samples on the original against 640170 on ours, 99.9884% of compared samples differing, because the two sides play different battle music (T13). Two defects were fixed: our hit sample fired whether or not the shot connected and is now armed only when damage lands, along with a 6.6 ms onset offset (T13b). A second scenario hit a wrong premise: the plan was to gate chip-fire and chip-damage sounds behind the original's conditions, but our code plays neither and the cited routines contain no sound call (T13c). The follow-up dumped the cannon route channel by channel — the original plays a chip-select blip and the chip-fire effect, ours nothing at all (T13d).

## The ROM's own tables, and the two script interpreters

"Done" is counted per item, so the counts came from the ROM's own tables rather than anyone's notes: 411 chips, 63 Program Advances, 32 virus families across 187 ranks, 25 Navis (T10). The enemy roster got its own pass, 452 identity rows read from the type tables: the think side holds 32 entries, not the predicted 96, and its entries are not routines but pointers to per-action handler tables — the shape the Gunner port needed (T12). The game's two small interpreters, for map cutscene scripts and for the chatbox text framing a battle, were ported as jump tables of 71 and 27 opcodes, every unimplemented one a named trap carrying the original's symbol; the chip menu improved from 44 differing pixels to 7 (T8).

## The tooling

Two tickets went to the measuring apparatus. The phase comparison had been reading recordings made before the phase field existed, agreeing on a field that was absent, and its alignment option crashed; fresh recordings and a fixed comparator gave honest numbers — the Mettaur and popup recordings agree across all 70 and 80 frames, a full fight disagreed on 174 of 540 (T7b). Separately, a race in the capture step could grab the Gunner recording's frames at the wrong moment; fixed, that row now reports what it sees (T9i).

## New recordings

![T13d NEGATIVE: cannon-route audio probe — canon fires ch0+ch4 SFX, ours silent. Docs-only commit; no harness change.](../captures/cannon-progress.gif)

![T5 object dispatcher ported: table and dispatch with citations; isolated rows 0, cursor tear 15->1](../captures/cursor-progress.gif)

![opening (integrated), FAILED: per-frame max 2691 px, total 72499 px over 40 frames. Alignment: canon frame 120+k, rust frame 8(marker)+119+k. canon](../captures/opening-integrated.gif)

## Where the whole thing stands

The game is compared against the original in 67 recorded scenes. 60 of them now match pixel for pixel in every frame.
The scenes that still differ: opening (inside a full fight); field (inside a full fight); warp (inside a full fight); chip-use (inside a full fight); gunner (on its own); gunner (inside a full fight); cursor (on its own). Each is a known, measured gap with a ticket behind it.

## What it cost

The agents run on prepaid subscriptions. Charm Hyper:  246.3 of 250 credits (3.7 used today, 1%).
tickets 45, landed 25, pi spend $23.54, $/landed 0.942, NEGATIVE+BLOCKED 16 (36%).
