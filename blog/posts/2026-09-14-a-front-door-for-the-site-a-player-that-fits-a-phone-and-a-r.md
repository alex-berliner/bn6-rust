# A front door for the site, a player that fits a phone, and a ROM that checks its cartridge

The site now opens on a directory instead of the emulator. One entry per page: the player, the learn feed, the blog, the before-and-after gallery, the run log, the ROM download, the repository and the disassembly fork it is built on. Every old address still works.

## The player fits on a phone

The player moved to its own page, and the complaint that drove that was simple: on a phone the on-screen buttons sat far below the game screen, and you could not see both at once. The old page put a paragraph and a header above the emulator and then gave the emulator nearly a full screen of its own, so the touch controls, which the emulator hangs at the bottom of its own box, fell off the bottom of the page.

Now the emulator box is the first thing on the page and it is exactly one screenful. The game screen is scaled to the width of the phone at its own 3:2 shape, and the touch controls the emulator ships with take the room under it. On a 390 by 844 phone, held upright, that works out to a 390 by 260 screen with 584 pixels under it for the buttons. Held sideways, the screen fills the height on the left and the buttons take the strip on the right. The key legend is behind a small "keys" button in the corner, and the rest of the text sits below the emulator, one scroll away.

That is computed from the page's own layout rules, not seen on a device: this machine has no phone. If the buttons still land somewhere odd, that is the next thing to fix.

## The ROM white-screened on a real Game Boy Advance

This morning's download was tried on real hardware, through a Supercard flash cart running the SuperFW firmware, and showed nothing but a white screen. The ROM's header is fine: the logo bytes, the fixed byte and the checksum all match what the console's boot program checks. The cause is in the first instructions our program runs.

A GBA cartridge answers the console at a speed set by a register the game writes at start-up. Manufactured cartridges are fast, so the runtime we build on stores the value 0x4317 there without looking: three wait cycles for the first read of a run and one for each read after it, with prefetching on. The Supercard's memory cannot keep up at that speed. Reads come back wrong, the very next thing the program does is copy its own fast code out of the cartridge, and it copies garbage. The firmware knows this about commercial games and patches their start-up code; it did not know our program.

The fix is to stop guessing. The copy now happens at whatever speed the console booted with, and then a small routine that lives in the console's internal memory, so it is safe from the problem it is testing for, adds up the first 16 kilobytes of the cartridge at the slow speed and again at the fast one. If the two sums agree the fast setting stays; if they differ the cartridge cannot serve it and the boot setting comes back. In the emulator the sums agree and the register reads 0x4317 as before; a test build with the comparison deliberately broken reads the boot value back. Every harness row measures the same as before the change: all the isolated rows at zero, the cursor row's single-frame tear still three pixels.

Whether it boots on the cart is for the next download to tell. The build on the site is the one with the probe.

**Update, later the same day.** The rebuilt ROM still shows a white screen on the cart. The waitstate write was a real hazard but not the whole story, and the probe stays in because it costs nothing. The hardware question is shelved for now at the user's request; the next suspects are written down in HANDOFF.md.
