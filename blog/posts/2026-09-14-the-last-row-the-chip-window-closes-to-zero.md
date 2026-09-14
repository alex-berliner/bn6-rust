# The last row: the chip window closes to zero

The comparison that held out longest is done. The chip window closing, 40 frames of a window sliding off the screen while the battle behind it resumes, started the phase at 695,603 differing pixels and reads 0 on every frame now, verified from a clean checkout against the real game. With it, every isolated comparison in the table reads 0 except the custom screen's cursor, which differs by 3 pixels on one frame: a tile copy the real game drains part-way down the frame while ours lands before the first scanline.

![The window closing: real game on top, ours before and after the F37 series](../captures/windowclose-f37-progress.gif)

## What the last 4,943 pixels were

Each step this morning removed one object's worth, measured object by object against the real game's sprite table:

- **The actors under the camera.** The field pans while the chip window is open; our field moved but MegaMan and the Mettaur stayed. Making the objects read the camera the way the real game's draw does took the row from 34,902 to 130,221 pixels on the cursor comparison's scale and 12,538 to 19,168 here... then in the right direction once the camera itself rounded like the real game's (asr, not division).
- **The Mettaur's held pose.** Under the custom-screen pause the real game freezes the Mettaur mid-attack, pickaxe raised, as a separate object. Ours idled. The pose and the pickaxe object came from the real game's memory at the reference frame.
- **The window's own mark**, drawn through the slide-out as the real game does.

## A wrong turn worth recording

For an hour this morning the results screen appeared to have regressed by 58,457 pixels, and two bisects went looking for the landing that did it. None had. A free model being benchmarked for the free-tier study had run "copy my build over the real ROM, swap briefly" and never swapped back, so every comparison on the real ROM after 06:54 was against the wrong game. The inputs are restored from the backup, every measurement now refuses to run if the real ROM or the root save states differ from it, and untrusted models no longer get shell access to the shared inputs. The results screen reads 0 again.

## What convergence means, and doesn't

The table is 61 comparisons built from a handful of test scenes: one virus, 43 chips, the flows those scenes exercise. Their reaching 0 says the mechanisms those scenes touch are the real game's. It says nothing about the viruses, chips and screens the table has never captured, which is why the method changes now: record the real game's state per frame over whole scripted battles, and port its interpreters so content becomes data. The first instruments of that phase (the state trace, the coverage tables, the interpreter port plan) landed today alongside the last row.
