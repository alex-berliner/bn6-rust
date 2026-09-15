# How an enemy thinks: the scripting engine under every virus

An enemy in Mega Man Battle Network 6 does not behave like a character. It behaves like a row in a table.

Battles in this Game Boy Advance game happen on a grid of eighteen floor panels, six across and three deep, MegaMan on the left half and the enemies on the right. The best known enemy is the Mettaur: a small thing in a yellow hard hat that hops between rows, ducks under its helmet, and swings a pick to send a shockwave down the floor at you. This post is about what that Mettaur is to the original's code, and what it took to run the original's own version of it inside ours.

## An enemy is a row in a table

The original keeps one table of live battle objects — MegaMan, every enemy, every shot in flight, every puff of dust. Sixty times a second the **object dispatcher** walks that table and hands each live object to the routine for its kind.

Which routine an enemy gets is chosen by data. Every enemy the game can spawn has a three-byte row in the cartridge's read-only memory: its **version** (viruses come in ranked versions, weaker to stronger), its kind (virus, Navi or player — the game's words for a common enemy, a named one, and MegaMan), and an **AI index** saying which brain it uses. There are 452 such rows.

The AI index picks one word out of a table of 32, and that word is not a routine: it points to a second table, indexed by what the enemy is doing right now. The Mettaur's has thirteen entries, for actions `0x00` to `0x0C` — hexadecimal, the base-16 notation the original's tables use, so `0x0C` is twelve. The first eight are spawn-and-idle plumbing every enemy shares; the rest are its own decision loop, a plain wait, the hop, the swing, and a guard it never performs.

## Think, then act

![The dispatcher walks the table of live objects, the enemy's row picks its routine, think and act run, and the animation player makes the poses](img/enemy-frame.svg)

One enemy's frame, end to end. Green is the original game's own code now running in our version; grey is still ours.

Each frame, an enemy runs in two halves. The **think** half runs its brain's handler for whatever action it is in the middle of. The **act** half is the tail every battle object shares: collisions, damage, death bookkeeping, and the driver that keeps an attack's animation moving.

That split explains a shape running through the whole engine: the decision loop only gets a turn when nothing else is using the enemy's single action slot. Issue a hop and it goes quiet until the hop hands the slot back. The Mettaur's behaviour is not a script of moves but a machine asked, when it is free, what to do next.

## The Mettaur's five states

That machine is a five-entry jump table.

**Check the row** is the entrance. The first time it runs for a new Mettaur it arms a wait and leaves. The value written is `0x1e`, thirty — but the waiter subtracts first and exits only once the count has gone below zero, so the pause is thirty-one frames, not thirty. That off-by-one was measured against the real cartridge, and it is the difference between matching and not. Afterwards the state compares the Mettaur's row with MegaMan's: equal goes to the attack, different issues a hop one panel toward him.

**Hop and wait** only watches. The hop takes six frames — three reserving the destination panel and spawning a puff of dust, three committing to it — then arms a cooldown from a per-version table (30, 24, 18, 12, 18, 12 frames) and reports back. Accepted, the loop returns to checking the row; refused because something was in the way, it attacks instead.

**Choose the attack** reads the shockwave's damage from another per-version table (10, 30, 50, 70, 50, 100) and sets the swing. The swing holds its pose for a 64-frame countdown, spawns the first shockwave segment when that countdown reads `0x1b` — twenty-seven — then hands over to a separate 40-frame recovery. That recovery was missing from our hand-written version, which let our Mettaur attack at twice the real cadence.

**Wander** is the only place this brain touches randomness; **guard** it cannot reach at all. Wander needs the enemy blind or confused: a random-direction hop, then a roll — take the bottom four bits of a random number, 0 to 15, and below 2 attacks now, otherwise idle 50 frames. Guard sits behind an equipped-ability check a first-version Mettaur fails. Both are ported anyway rather than deleted: a deleted branch is one somebody has to rediscover.

![The five decision states: check the row, hop and wait, choose the attack, and the two behind a status effect](img/mettaur-states.svg)

The same machine as a picture: green states run in every fight, the grey ones only behind a condition nothing here can cause yet.

![The Mettaur's attack cycle, original on the left and our build on the right](../captures/mettaur-attack-compare.gif)

The whole 70-frame attack cycle, original left and ours right, at zero differing pixels a frame — an older recording, aligned by the frames on which the enemy's outline changes.

## The Gunner is a different shape

A Gunner is a stationary cannon virus, and its decision is far simpler: it attacks only when an opponent stands somewhere ahead of it in its own row. The complicated part is the attack, a four-step machine on one entry of the action table — aim, lock, fire, recover.

Aim spawns a lock-on cursor on the Gunner's panel and sends it forward. The cursor moves three pixels a frame and re-checks the panel beneath it every panel's worth of travel, thirteen frames. Find nobody and it runs off the field, abandoning the attack; find the player and it locks for 24 frames and hands that panel back. Fire drops three shots on that panel, ten frames apart, each warning for ten frames with the panel blinking under it. Recover holds 24 frames, and the Gunner is idle again — a pure function of where you stand, with no randomness anywhere.

## From an action to pictures

Nothing above draws anything. An action becomes pictures through the **animation player**, a small interpreter: every sprite's animation is a list of commands, each saying which picture, how many frames to hold it, and a couple of flag bits. Binding finds the list; every frame the player counts the current command's timer down and at zero moves to the next. One flag bit marks the last command, another whether to loop or hold the final picture. A routine switches an object to a new animation by writing an animation number, and a gate decides whether the count runs this frame at all — skipped during a time stop, rebound after a switch.

The detail that bites: the original subtracts one, stores, and compares against zero on the full register, so a timer reading zero still has one more frame to run. Read it the obvious way and every pose comes out a frame short.

## One number, shared

The whole battle draws from a single 32-bit number. Its step: rotate the bits left by one, add one, exclusive-or with the fixed constant `0x873ca9e5`. A second generator with the same formula and its own state shuffles the deck of battle chips you draw from; the two never touch.

Both sides of a comparison start from the same seed, and every draw advances it. Draw once more than the original does, or once fewer, and every later number differs: the two fights agree up to that frame and are unrelated after it.

Watching that number in memory over 220 frames of a recorded battle, all 219 transitions matched the formula bit for bit — and it advanced exactly one step a frame, never two, which is how we know the Mettaur's wander roll never fires in the fights we compare.

## Most of the roster is data

Four tables of 32 entries sit back to back in the ROM, all indexed by that AI index: the think tables, two tables of per-family constants (one holding each enemy's HP and element), and the act routines. The 452 identity rows in front of them map every spawnable enemy onto one of the 32 brains plus a version. The Mettaur's brain covers 82 of those rows, the Gunner's 12. Counted as things to build — a family crossed with its versions — that is 187 virus ranks, of which one is finished.

Porting the next one: find its AI index, follow it to its action table, read the handlers, write them out with citations, and let the recording say whether it is right. No new dispatcher, no new animation player, no new generator.

The limit is naming. Only two of the 32 think tables are identified, the Mettaur's and the Gunner's. The other thirty are mapped to an index and to the enemy ids that use them, but not to a virus you could point at on screen.

## Where this stands

The Mettaur is done in the sense this project means by done: the original's routine, run by the original's dispatcher, posed by the original's animation player, matching the cartridge at zero differing pixels over its recorded attack cycle, with a state trace of a scripted battle agreeing on its state and action across all 70 frames.

The Gunner's routine is ported — the four-step attack machine, the shot count and gap and recovery, the per-state fields in the original's own layout — but its scene does not match yet, and most of what is left is not the enemy.

![The Gunner's scene, the original on top and our build below](../captures/gunner-progress.gif)

The Gunner's scene over 130 frames, original on top and ours below. Correcting the four scroll seeds for this arena's backdrop took the difference from 2,850,534 pixels to 2,105,613 and made the backdrop pixel-exact from the sixth frame on — a reminder that an enemy's row is never only about the enemy.
