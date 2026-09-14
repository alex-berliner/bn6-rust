# The Mettaur runs on the original's routine

The first piece of content to become the original game's code rather than our re-creation of it: the Mettaur. Its brain in our build was a hand-written state machine (wait, line up with MegaMan, hop, swing, launch the shockwave) tuned over several tickets to match the original's counts frame by frame. Today that state machine is gone. The Mettaur is now the original's own per-type routine, ported from the disassembly and run by the object dispatcher landed yesterday, reading its timers from the same fields the original reads.

The comparison table did not move: every isolated row still reads 0, the Mettaur's own row included, and the state trace of a full scripted battle shows the enemy's state and action matching the original on all 70 frames of the Mettaur scenario. The landing cost nine cents on the cheap tier.

Why it matters more than the row: the Mettaur was the one enemy we had, and every one of its behaviours had been a separate investigation. The next virus does not get that treatment. It gets its routine ported the same way, under the same dispatcher and the same animation player, and the trace says whether it is right. That is the shape the rest of the content takes: five viruses and two bosses in scope, each a port, not a project.

Next: the battle's end sequence as the original's state table, which is what the five whole-screen comparisons have been waiting on.
