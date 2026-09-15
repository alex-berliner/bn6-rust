# Two of the three interpreters are in

An interpreter here means a small engine inside the game that reads instructions from the game's data and carries them out, the way a music player reads a score. The port plan named three of them that sit under everything in the original game's battle code: the animation player, the object dispatcher, and the script VMs. The first two landed today, in four tickets, each verified by the full comparison table staying identical and by the state trace of a full scripted battle diverging no earlier than before.

![One battle frame: the clock ticks, the object dispatcher walks the table of live objects and calls each one's routine (enemy, MegaMan, shots and effects), the animation player steps every sprite's animation script, and the sprites are drawn](img/interpreters-frame.svg)

What happens sixty times a second: the two pieces that landed are the green boxes, the original game's own code now running in our version; the grey boxes were still ours when this was written.

- **The animation player**, all four steps: binding a sprite's animation tables from the ROM data; the per-frame update with the original's countdown, consume, loop-or-hold semantics; the alternate stream and the way a caller switches an object to a new animation; and the update gate with its rebind protocol and its time-stop variants. Our hand-written player is gone behind the same interface.
- **The object dispatcher**: the original keeps a table of live objects and, each frame, walks it and sends every object to the entry routine for its type; enemies go through a think step and an act step. That table and that walk are ported (objects.rs), with our actors, shots and effects as the per-type entries for now.

![The animation player in four steps: bind the sprite's script from the game's data; every frame count the timer down, take the next step at zero, loop or hold at the end; a routine can switch to a new animation; a gate skips the count during a time stop and rebinds after a switch](img/animation-player.svg)

The animation player, step by step. Each sprite's script is a list of pictures with a timer each; the player counts the timer down and moves to the next picture at zero.

Why this order matters: the last phase spent most of its effort on lifecycle differences (an object updating a frame late, a pose held one frame short) that were symptoms of not having these two pieces. From here, an enemy or a chip is the original's routine running under the original's dispatcher and player, not a re-creation of what it looks like.

Next: the Mettaur becomes the original's per-type routine instead of our state machine, then the battle's end sequence becomes the original's state table, which is what the five whole-screen comparisons have been waiting for.
