# Transfer Doc: Battle Captures, the Sterile Arena, and the Cannon Comparison

This is the working knowledge from the "make the Rust `bn` reimplementation match the real
MMBN6F ROM frame-for-frame" effort. It records what was built, the reverse-engineering
insights, the failures, and the open items. Read this first if you are picking this up.

Driving goal (in order of priority as it evolved):
1. Reproduce the real ROM's battle rendering so a **differential mask over the intended same
   frame is a single solid colour** (zero difference). That means the Rust port renders the
   exact same frame as the real game.
2. For the **Cannon chip** specifically, then replicate 10 chips (each verified against the
   real ROM, doing it well not fast).

---

## 1. The capture pipeline (how to get frames from the real ROM)

All of this uses libmgba (mGBA's core library) directly, not the Qt window. The harness is
`tools/mgba_capture.c`, built with:

```sh
gcc tools/mgba_capture.c -o /tmp/mgba_capture -I/usr/include -lmgba -lm
```

`tools/mgba_capture.sh` wraps it (optionally `--build <features>` to compile the Rust ROM
first, and decodes raw `.rgb` frames to `.png`). `--no-decode` leaves raw `.rgb`.

### Harness options
- `<rom> <outdir> <count>` — the base: run `count` frames, write `frame.NNNNN.rgb` to `outdir`.
- `--loadstate <file>` — load a save state before running. **Critical gotcha:** mGBA-qt states
  are `RASTATE` (7-char banner + version byte) followed by the raw `GBASerializedState` at
  **offset 16**. `mCoreLoadStateNamed` reads the raw state from offset 0, so the harness
  detects the `RASTATE` banner and rewrites a temp file with only the raw state. RetroArch
  `.state` files are a different incompatible container — do not use them.
- `--loadsave <file>` — load the battery .srm.
- `--peek 0xADDR` / `--poke 0xADDR:0xVALUE` — read/write 16-bit bus memory.
- `--dump 0xADDR:N:file` — dump N bytes to a file (for struct reverse-engineering).
- `--cheat 0xADDR:0xVALUE` — **re-written every frame** before `runFrame`. This is what lets a
  value survive the game recomputing it... *but see the render-config blocker in §5*.
- `--script "A@60,Start@120"` — tap keys at frame numbers (a one-frame tap = a press).
- `--disable-bg` — the big one, see §5.

`tools/mgba_frames.py` decodes raw `.rgb` → PNG. Channel order for the raw native frames is
`[R][G][B][x]` (0x00RRGGBB little-endian). `.rgb` files are 240*160*4 bytes.

### Known save states
- `/tmp/bn6f_real.gba` — the real ROM (SHA1 `0676ecd4d58a976af3346caebb44b9b6489ad099`,
  exactly the decomp's `bn6f.sha1`). Copyrighted — **never commit**.
- `/tmp/pausedwithcannon.state` — a battle paused with a `Cannon40` queued. This is the save
  state used for all the cannon captures. Reliable: it loads a live battle.
- Also seen: `chipselect.state` (chip-select window).

### The real ROM is stripped to a "sterile arena" via a code patch
`tools/patch_sterile.py` patches `battle_isBattleOver` (ROM `0x0800A18E`) to `mov r0,#0; bx lr`
(always return "not over"), so the battle never concludes. It produces `/tmp/bn6f_sterile.gba`.

---

## 2. Reverse-engineering: battle RAM addresses

These were found by poking the live `pausedwithcannon` battle.

- **Toolkit** (`eToolkit`) is at `0x20093b0` (ewram.s:582). `BattleStatePtr` is at toolkit
  offset `0x18` → the live **BattleState** is at `0x02034880` (heap-allocated per battle).
- **BattleState fields** (from `include/structs/BattleState.inc`): `Unk_0b` at `0x0b`,
  `Unk_12` at `0x12`, `Unk_13` at `0x13`, `BattleField` at `0x06`, `Unk_a0` at `0xa0`.
- **Battle objects** (the linked list of `BattleObject`s):
  - `0x0203a9b0` = **MegaMan** (HP 60/100, panel 0x202 = (2,2), NameID 0x1a0).
  - `0x0203ab60` = **Mettaur** (HP 40/40, panel 0x205 = (5,2), NameID 0x0001).
  - `0x0203aa88` = a second enemy already at HP 0.
- **BattleObject field offsets** (`include/structs/BattleObject.inc`): `CurState@0x8`,
  `CurAction@0x9`, `PanelX@0x12`, `PanelY@0x13`, `HP@0x24`, `MaxHP@0x26`, `NameID@0x28`,
  `Coords.X@0x34`, `Coords.Y@0x38`. `OBJECT_FLAG_VISIBLE = 0x02` at offset 0x0.
  - The **Mettaur's HP** is at `0x0203ab60+0x24 = 0x0203ab84`; `MaxHP` at `0x0203ab86`.
- **Player battle-hand** block at `byte_20349C0` (`0x20349C0`). `hand[0]` = pick count;
  the next chip id is the u16 at `hand[2 + 2*count]` (so with count 0, the chip is at
  `0x20349C2`). Hand stride is `0x50` per alliance (`getBattleHandAddr_8010018`,
  asm00_2.s:2664). Cannon battle id = 1 (`CHIP_CANNON`), HiCannon = 2.

---

## 3. The sterile real battle (enemy removed, no conclusion)

Two interacting goals: remove the Mettaur AND keep the battle live.

- **Deleting the enemy** (`--cheat 0x0203ab84:0` and `0x0203ab86:0` every frame) removes it
  ("ENEMY DELETED" banner) — but the game then advances to the RESULTS window.
- **Immortal enemy** (`--cheat HP=0xffff`) keeps it alive → the battle stays live and
  MegaMan keeps firing, and **no "ENEMY DELETED" banner** triggers (so the Mettaur is still
  on screen, but there's no banner) — at frame 66 of the immortal capture, the frame is
  MegaMan + green cannon barrel + Mettaur (HP 5533) on black.
- **Patching `battle_isBattleOver`** (the code patch) stops the conclusion *when the enemy is
  deleted* (§1), so you can delete the enemy and keep the battle live. The "ENEMY DELETED"
  banner still shows during the cannon fire (it's tied to the enemy deletion event), so the
  banner is still in the frame.

**Net:** to capture a clean "MegaMan + attack on black" with no enemy and no banner you need
BOTH (a) the `battle_isBattleOver` code patch so the fight doesn't end, and (b) a way to remove
the banner/enemy. The banner removal is the open item (§7).

---

## 4. Disabling the field / background — the key trick

The battle field (panels), the background bubbles, and the HUD are **re-loaded by the game
every frame**, so NO write-based approach survives:
- Writing `REG_DISPCNT` (0x04000000) → the game re-writes it to `0x7f60` each frame (peek
  confirms: write 0, read back 0x7f60).
- Clearing the BG palette (0x05000000-0x050001ff) → no effect.
- Zeroing **all** OAM (0x07000000) → the frame is unchanged; the game re-writes OAM.

**The thing that works is disabling the layer on the renderer itself**, which is what mGBA-qt's
layer toggle does. The public `mCore->enableVideoLayer(core, id, enable)` (with the
`GBAVideoLayer` enum: BG0=0..BG3=3, OBJ=4, WIN0=5, WIN1=6, OBJWIN=7) **segfaults for BG1-3 on
libmgba 0.10.x**. So the harness reaches the renderer directly:

```c
struct ARMCore* cpu = (struct ARMCore*) core->cpu;
struct GBA* gba = (struct GBA*) cpu->master;      // &gba->d
gba->video.renderer->disableBG[0..3] = true;
gba->video.renderer->disableOBJ = false;          // keep MegaMan + attack
gba->video.renderer->disableWIN[0] = WIN[1] = true;
```

This is the **`--disable-bg`** option. Result: only the OBJ sprites (MegaMan + attack + enemy +
HUD text sprites) show, on a **black** background. The field/background become black — the
exact precondition for a solid-color diff against the Rust version's plain background.

---

## 5. The Rust sterile arena (`demo-sterile`)

`cargo build --release --features "demo-cannon demo-sterile demo-auto"` → gbafix →
`/tmp/rust_black.gba`.

- Renders **MegaMan alone** (no enemy), **plain black background**, never concludes.
- **`demo()` in `src/battle.rs`:** a `demo-sterile` branch returns `(hand, 2, None)` — **col 2**,
  so MegaMan is at panel (2,2) matching the real save state. **BUG FOUND:** if you build with
  both `demo-cannon` AND `demo-sterile`, `demo-cannon`'s branch (`megaman_col = 3`) ran FIRST and
  shadowed the sterile col 2 (`demo()` is a chain of `if cfg!(feature = ...) return`). That
  placed MegaMan at col 3 (screen x≈100) vs the real's col 2 (x≈61) — a one-panel (40 px)
  offset. The fix moved the `demo-sterile` check to the **top** of `demo()`. This was the
  single biggest improvement to the comparison (field the frames actually align at (0,0)).
- The sterile arena must draw a **plain background** (not `field.background`) so both sides are
  black — revert the earlier change that drew the field in sterile mode.

### Key chip constants / poses (actor.rs / battle.rs)
- `CANNON` attack pose: `anim 8`, `CANNON_FRAMES = 0x1d` (29 frames). The barrel is spawned at
  the start of the pose, shot fires at counter `0xf` (asm31.s:109531), pose exits `0x1d`
  (109554).
- The **barrel** effect: `spr::Player::new(BARREL_CHARGE, 0)` anchored at `(mx + 18, my - 24)`.
  The **+18,-24** was tuned to match the real's arm hold (barrel centre = body centre
  +(+21,-11)); it was `+12,-18` before. Use `BARREL_CHARGE` (frames 1-5 of `byte_82F39C0`, the
  compact green barrel + charge orb, NOT the cyan charged-buster discharge). The shot is
  `Shot::cannon` with `CANNON_ORB` (`byte_82FE704`)
  — the **big yellow-outlined white orb**, animation 0 — NOT the buster bolt.
- The Rust `Cannon`/`HiCannon` chip now uses `Shot::cannon` (big orb). `Shot::cannon` was added
  in `src/shot.rs` (passes anim 0 to `Player::new`); `Shot::new` gained an `anim` parameter.

---

## 6. The comparison toolding

- **`tools/compare_stereo.py`** — navi-aligned REAL|RUST|DIFF side-by-side. Options:
  `--win WxH`, `--navi-center x,y` (pin the crop centre, better than centroid when the field
  confuses detection), `--navi-only` (mask everything except navi/attack colours).
  `is_field()` masks the battle-panel palette (navy/orange/cream) so the field cancels. The
  navi centroid detection is unreliable when the field is present (the panels are saturated
  and pull the centroid) — use `--navi-center` or strip the field first.
- **`tools/diffmask.py`** — the goal tool: renders a differential mask over two frames. Solid
  `--solid` colour (default green) where pixels are identical, `--diff` colour (red) where they
  differ, with `--align dx,dy` to shift the second frame. Prints the % differing. THIS is the
  tool that must go to a single solid colour. Background already goes solid (both black).

---

## 7a. STATUS 2026-09-06: the Cannon is frame-for-frame identical

With the enemy deleted (`--cheat 0x0203ab84:0 --cheat 0x0203ab86:0`), the ENEMY DELETED
banner's tiles blanked each frame (`--zero 0x6016E00:1280`, new harness option; the banner is
OAM objects 0-4, 32x16 each at y=64, tiles 880-919), `--disable-bg`, and the Rust built with
`demo-cannon,demo-sterile,demo-auto`, every frame from the attack's start (real f43 with
A@40; Rust f122 in a 220-frame run) through the recovery differs by **0 pixels** within
x<140 (x>=149 holds the real ROM's dissolving Mettaur remnant). One frame, c6, shows ~370
differing pixels: the banner's tiles re-uploaded that frame before the blanking took --
capture artifact, not the game.

What it took (all in the commit "Match the Cannon frame-for-frame..."):
- The barrel is sprite_82F39C0 **animation 0 in full**, 13 frames spawned at counter 0: five
  blank, three white silhouette (OAM palette offset 4 -> flat 0x77fd, `spr.rs`), the barrel,
  the small then big muzzle orb at counters 14/15, the cyan discharge chevrons 16-22 (these
  ARE part of the cannon; the earlier "not the discharge frames" note was wrong), then the
  plain barrel to the pose's end. Its own OAM offsets carry the recoil; it is anchored once at
  (mx+16, my-24) and does not follow the navi.
- The navi's cannon pose is on screen 0x1e frames (the 0x1d frame only queues the exit), then
  **animation 15 for 3 frames** (arm coming down), then idle.
- Sprite parts are drawn last-to-first (the game's OAM order): the shadow goes under the
  feet (99 px visible, as the real), and attack objects draw before the navi so the barrel
  covers the arm.
- The cannon's shot has no sprite: `Shot::cannon` is hidden; only its hitbox travels.
- The player's HP number is no longer drawn under the navi (the game's is on the HUD layer).
- Timeline (c = frames since attack start): pose frames 33/34/34/35/35 at c0-4, 36 at c5-13,
  37/38/39 at c14/15/16 (body x 43->39->38->37), 40 at c17-29 (x 35); barrel white c5-7,
  green from c8; muzzle orb small c14, big c15; chevrons c16-22; recovery c30-32; idle c33.

## 7d. Backgrounds-on whole-screen match (PARKED by the user, 2026-09-06)

The user's call: the backdrop is not worth the effort, so pixel-parity work stays on the
backgrounds-off setup (`chip_compare.py` defaults to `--disable-bg`; `--bg` is opt-in and left
in place). Everything below is the record of how far it got, for whoever picks it up.


`tools/chip_compare.py <id> demo-field --bg` keeps the real ROM's backgrounds and diffs all
240x160; the Rust side is then built without demo-sterile, and `demo-field` fields the save
state's layout (MegaMan at (2,2), a Mettaur at (5,2)). Every demo-* feature now enables one
umbrella `demo` feature, so the two hand-maintained cfg lists that had already drifted are gone.

Fixed: the field's halves were the opposite colours to the real ROM's -- **the player's half is
the red one** (src/field.rs draw_panel's side index). Whole screen 99.2% -> 59.4% differing.

Measured on an idle frame (real: enemy HP poked to 900 to match ours, no A press; rust:
demo-field):
- backdrop, y < 72: 99.9% differing -- we draw black. Missing: the navy/teal-arc backdrop
  layer, the HP box ("60"), the emotion window, the CUSTOM gauge bar.
- field, y 72-144: 7.4% differing, and all of it is the Mettaur's pose (mid-pickaxe in the
  real capture) -- the panels themselves match.
- bottom, y >= 145: 100% differing -- the backdrop continues below the field and the chip
  name ("Cannon 40") is drawn there.
The backdrop, measured from the real ROM (BG1: BG1CNT 0x1d03 = priority 3, char block 0,
screen block 29 -> map at 0x600E800, tiles from 0x6000000, palette bank 0):
- It is a 32x32-tile (256x256 px) map of a teal-arc motif on navy, ~37 distinct tiles, all in
  palette bank 0. Dumped and rendered from VRAM: scratchpad/bg1_map.png.
- It SCROLLS: 1 px left every 2 frames and 1 px up every 4 frames (measured by best-shift
  matching over frames 41-55 of an idle capture; residual 42-482 px out of 4800, i.e. a rigid
  scroll). In fixed point that is +0x80 HOFS and +0x40 VOFS per frame on an 8.8 accumulator.
- The tiles are in the disassembly at **dword_8617488** (data/dat38_60.s:49372, 4416 bytes =
  138 tiles), found by scanning every data blob and compressed file for a distinctive VRAM
  tile. The blob's order is NOT the VRAM order: the game uploads it in groups (VRAM 3-6 ->
  blob 1-4, 8/13/14/19/20 -> 5/10/11/16/17, 9/10/15/24/29/30 -> 32-37, 11/12/18/21/27/28 ->
  128-133), and the uniform navy tiles collapse onto blob tile 0. So an exporter has to know
  the upload's tile order, or lay the tiles out itself and rewrite the map.
- The 32x32 tilemap was NOT found in any data blob or compressed file, so it is probably built
  at runtime (or stored in a form the scan does not reach). Open.
Next: the backdrop's upload routine and map construction (a Sonnet pass is on it), then the
HUD.

## 7r. The HUD reaches per-pixel parity; FlshBom does too (2026-09-07)

THE BG3 HUD LAYER IS EXACT -- 0 px over the whole strip, real against this build, once the
gauge animation's phases are lined up. Three things were wrong and all three are the kind a
still screenshot hides.

THE EMOTION WINDOW (the navi's face under the HP box) was not drawn at all. The real ROM draws
it as two OBJECTS rather than tiles -- a 32x16 at (0,18) and a 16x16 at (32,18), OBJ palette
bank 12, OAM objects 2 and 3 -- which is why it survives the field being stripped and appears in
every sterile chip capture just above the compared window. Twelve tiles out of OBJ VRAM matched
byte for byte against every assembled label in the disassembly: `dword_872D814` in
data/dat38_86.s, whose own label holds the wide object's eight tiles and whose next label holds
the narrow one's four, exactly how the two objects split; the palette is `dword_872F114` beside
it. The bank continues past them at 0x180 bytes each, one window per emotion, which this build
has no state to choose between. tools/emotion_export.py. The sterile arena's top strip went from
195 px to 0.
BUT: the real ROM DROPS the emotion window the moment the ENEMY DELETED banner shows, so past
the attack's frame 6 the sterile capture has no window and this build still draws one. That is
the same class of artifact as the banner itself -- read the top strip only before frame 6.

THE PLAYER'S HP WAS DRAWN TWICE, in the tile box on BG3 and again in object text below it. A
full battle showed the number twice; the sterile arena showed one where the real capture, its BG
layers stripped, has none. Only the box is the real ROM's.

A FULL CUSTOM GAUGE FLOWS. The body cell steps through four patterns SEVEN frames each, in VRAM
tile order 0x234, 0x235, 0x232, 0x233, and the L-or-R marker alternates cyan (0x236) and orange
(0x23a) every EIGHT. It is a TILEMAP swap, not a palette cycle and not new art: dumping the
bar's tile bytes and BG palette bank 9 frame by frame shows both standing still while the map's
tile ids change. NOT VERIFIED: where the cycle starts; one save state cannot say whether the
phase runs off the battle's frame counter or off the moment the gauge filled.
This is worth generalising -- a HUD element that looks static in a screenshot may be animated,
and the way to tell is to dump the map, the tile art and the palette across frames and see which
of the three moves.

THE CHIP SELECT WINDOW, compared with sprites off on both sides, matches on the window frame,
the pick stack and its frame, the OK box, the CHIP SELECT panel and the code row. Two notes:
- The orange knob above the pick stack and the OK box's bracket are OBJECTS, not tiles. With
  --disable-obj the real ROM's knob is the same dark socket this build draws, and its BG tiles
  match this build's byte for byte, so the socket is right and the disc on top is missing.
- The slot icons carry their selectability in the PALETTE BANK: bank 11 is the bright cream
  icon palette and bank 12 a dimmer copy of it, and in a capture where one chip has been picked
  the slots whose codes no longer fit are the ones in bank 12. This build has `allowed()`
  already and gives every slot bank 11, which is right only before the first pick. Bank 12's
  palette is in neither the window's data nor the chip data, like bank 11's; read it off a live
  menu: 0000 6739 4e73 4231 39ce 2d6a 292a 14a5 5af7 5eb3 0000 0000 0000 0000 0000 0000.
- Cells beyond the offer are hidden by writing the empty-cell tiles in BANK 9, where the frame
  palette renders them as the panel's own background. That is how the real ROM shows eight cells
  where this build shows ten.

FLSHBOM IS EXACT -- 0 px on every frame of the attack. Three defects: the thrown ball still used
the MiniBomb sprite, the arc was a bomb's, and the held ball dragged its sprite's ground shadow
along to the navi's hand. A HELD OBJECT'S SHADOW IS NOT DRAWN -- anchoring it at the navi's
origin instead is not enough, the real ROM's ground mark there is the navi's own and nothing
more. On fitting the arc: fit the WHOLE flight, not its first half. Fitting thirty of the forty
frames gives a curve that is right at the peak and six pixels low at the landing. And fit the
arc THIS BUILD DRAWS: the ball's z carries 0x8c00 of subpixel and its first frame is drawn after
a step, so the naive simulation is a step ahead of the real thing and solving against it puts
the constants in the wrong place.

## 7ab. Whole-screen tile parity, and the limit of one save state (2026-09-07)

0 of 38400 pixels, sprites off, `demo-hudmatch` against /tmp/pausedwithcannon.state: backdrop
with its animation and scroll, HP box, CUSTOM gauge with its flowing bar, twelve panels and the
chip name strip.

HOW TO ALIGN TWO SCREENS. Capture both with `--disable-obj`, then search PAIRS of frames -- not
one frame against a sweep, because the backdrop's animation and its scroll have periods that only
line up occasionally. Sample every eighth pixel over a grid of (real frame, rust frame) first;
the winner is usually exact or nearly so at full resolution. Use an EARLY real frame: by frame
~290 of that capture the navi has been hit and the HP box reads 40, which no fixture reproduces.

WHAT MOVED. The gauge's flow ran a frame ahead of its counter. With the two screens aligned on
the backdrop, every tile matched but the gauge's bar -- 360 px, one 8-pixel band -- and sweeping
that band alone put it at -1 (`BAR_PHASE`).

AND THE LIMIT. Two phases in that screen CANNOT be settled by one save state:
- the gauge's flow phase against the backdrop's. The capture's gauge has been full for an unknown
  time, so nothing fixes their relative phase; -1 is what makes this screen match and the only
  argument for it being a rule is that it is 1 rather than 14.
- the SCROLL's parity. Both sides step the backdrop a pixel every other frame; in this pairing
  they step on opposite frames, so the screen matches on one frame and diverges on the next by
  about 3000 px. Giving the backdrop a one-frame head start fixes the parity and breaks the
  gauge, because they are driven by different counters. Where the real ROM's scroll sat when the
  state was saved is not something the state explains. Do not chase it with a constant; capture a
  battle FROM ITS FIRST FRAME if it ever matters.

## 7ac. A whole frame WITH SPRITES, live virus included (2026-09-07)

0 of 38400 pixels: MegaMan, a Mettaur mid-swing, its shockwave, the emotion window, the
chip-in-hand icon and the enemy's HP readout, all identical to the real ROM. The first comparison
with a live virus rather than an empty arena.

THE FIXTURE. `demo-field` -- MegaMan (2,2), Mettaur (5,2) -- with two additions: a Cannon in hand,
so the icon the chip window leaves over the navi is there, and the Mettaur's HP set to 0xffff,
which is what the capture writes into it every frame to keep it standing. The real side is
`/tmp/mgba_capture /tmp/bn6f_sterile.gba out N --loadstate /tmp/pausedwithcannon.state --cheat
0x0203ab84:0xffff --cheat 0x0203ab86:0xffff --disable-bg --script "Start@10"`; the Rust side is
the same ROM captured with `--disable-bg`. Align by searching rust frames against one real frame.

WHAT THE ENEMY'S HP READOUT GOT WRONG, all three worth knowing:
- it sits LEVEL with its panel's centre, not six pixels below;
- it draws at most FOUR digits -- 0xffff reads 5535, not 65535;
- it goes ABOVE the enemy. With it behind, the Mettaur's helmet ate the outline row above the
  digits: thirteen pixels, the last thing left. Same lesson as LilBolr's HP figure (7aa): the
  game's object text is drawn ahead of the thing it belongs to.

WHAT IT DOES NOT SHOW. Only that frame matches. The virus's next move comes from an RNG this
build does not reproduce, so the frame after is already 765 px apart. The result is that every
OBJECT on the screen is right, not that the fight runs the same.

## 7ad. The navi's warp, frame for frame (2026-09-07)

0 differing pixels over the 66 frames that cover two scripted moves, the warp's seven frames
included. The method is new and worth reusing: SCRIPT THE SAME INPUTS INTO BOTH SIDES and track
one object frame by frame.

HOW TO SET IT UP.
- The sterile arena CANNOT test movement: with its enemy deleted the real ROM stops taking input
  and the navi will not move however long the key is held. Keep the enemy alive instead
  (`--cheat 0x0203ab84:0xffff --cheat 0x0203ab86:0xffff`), and compare only the navi's half until
  the virus's shockwave crosses into it -- about 30 frames in this capture.
- Press the direction on the real side at frame 60, before anything has hit the navi; a navi
  mid-mercy-blink is invisible on half the frames and unreadable.
- Track by COLOUR, not by bounding box: `(0,132,222)` is one of the navi's blues and nothing else
  on that half of the screen has it.

WHAT WAS WRONG, three things:
- the dissolve began a frame too early. `step()` now sets the state and the WARP_OUT animation
  starts on the NEXT update (`WARP_DELAY`), which is what the real ROM does;
- and ran a frame too short: LEAVING_FRAMES 3 -> 4;
- the frame the panel is COMMITTED on is drawn in the sprite's SECOND palette -- a washed-out
  copy of the first, five of whose colours are palette 1 of battleSpriteMegaMan.spr word for word.
  It is NOT the forced white a hit uses, and it could not have been drawn at all: the exporter
  was taking one palette for the navi. `spr_export.py --palettes 1` now gives it two.

## 7ae. The buster (2026-09-07)

Scripting B into both sides the way 7ad scripts a direction found five defects; four are fixed.
30 differing frames and about 15000 px are now 4 frames and 1480.

- FOUR FRAMES OF NOTHING after the button, so BUSTER carries `windup: Some((anim::IDLE, 4))`.
  The chips that reuse this spec inherit it; the chip comparisons align on the first body change,
  so the scoreboard cannot see the difference either way.
- THE POSE IS 17 FRAMES, not 5. The disassembly's "animation 14 for five passes" counts passes of
  the ANIMATION.
- THE SHOT IS A HITSCAN. It never crosses the field: OAM on the firing frame has the flash still
  at the gun and the enemy's HP already down. This build fired a travelling `Shot::buster`; the
  plain buster now strikes the row at once and draws only the flash. The CHARGED shot still
  travels.
- TWO OBJECTS WERE MISSING, both found by dumping OBJ VRAM on the firing frame and searching all
  97 .spr files for those tiles:
  - the BARREL, `byte_82F6ECC.spr` animation 0 -- a 16x8 riding the navi's arm at (+13,-30) from
    his origin, four frames of recoil (durations 1,2,2,3) and then held for the whole pose;
  - the FLASH, `byte_82FE378.spr` -- five frames (2,1,1,2,1) at the FRONT panel's x, 26 px above
    the panel centre.
  A TRAP with both: they are single-part sprites, and the effects list's `no_shadow` flag skips
  part 0. Setting it -- which is right for a HELD object with a shadow part -- draws nothing at
  all.

0 PX over the whole thirty frames of a shot. The last three constants came from ONE measurement
repeated: find the frames on which the navi's BODY changes, on each side, with the barrel and the
flash excluded from the sample box. The real changes on 5, 6, 8, 10 and then holds; this build
was on 6, 7, 9, 11 -- one late throughout, so the windup is 4. The pose then ended a frame early,
so it is 17. Then the flash's own two big frames landed one early, so the strike is the pose's
THIRD frame. One measurement, one constant, re-measure; do not sweep several at once when the
frames themselves can be counted.

## 7af. Holding the buster: the charge (2026-09-07)

0 px over the 32 frames of a hold that the capture's shockwave leaves comparable. Four findings,
and the first one is a behaviour, not a constant.

THE BUSTER FIRES ON THE RELEASE, NOT THE PRESS. Hold B on the real ROM and the navi stands in his
idle, charging, for as long as it is held; he shoots when it is let go. A tap is a press AND a
release, which is why tapping still fires at once -- and why a two-frame press could not tell the
two apart. Every buster constant in 7ae is measured from the RELEASE because of this:
`BUSTER_WINDUP` is 2 and `BUSTER_ARM_DELAY` is 2.

THE CHARGE GLOW WAS THE WRONG SPRITE. The real one is `sprite_83A9190` -- four 32x32 quadrants
around the navi at (-30,-50), (2,-50), (-30,-18), (2,-18). It is in `data/dat38_33.s`, NOT under
data/sprites, so a search of all 97 .spr files finds nothing; `spr.load_sprite_bytes` takes
`file.s:symbol` for exactly this case. This build had a different sprite that drew green dots.

- it rides TWO pixels forward of the panel centre, not eight;
- it starts on the ELEVENTH frame of the hold, not the tenth;
- it is drawn OVER the navi. The real ROM's OAM has its quadrants at entries 4-7 and the navi's
  at 8-10, so its sparks cross his body. Drawn under him they were cut wherever they crossed --
  the last 53 px a frame, and the third time today that the answer was OAM order (7aa, 7ac).

THE FULL CHARGE IS 101 FRAMES of holding B, and its glow is animation 2, drawn in the sprite's
THIRD palette -- a magenta orb at the navi's chest with pink sparks.

HOW TO SEE IT AT ALL. The obvious capture cannot: the save state's Mettaur hammers the navi with a
shockwave at exactly the moment the charge fills and buries him. Press DOWN first. The navi moves
off the virus's row, the wave then travels a row he is no longer on, and the change is in plain
sight. Worth reaching for whenever the capture's own virus is in the way.
A TRAP on the way: this build showed no magenta at all until `spr_export.py --palettes 3` was
used. A frame carrying a palette OFFSET needs those palettes exported, or the offset falls back
to the first and nothing says so.

STILL NOT VERIFIED: the charged shot itself. Releasing at full charge puts the navi back in the
shockwave's way in this capture.

## 7ag. The chip button fires on the release too (2026-09-07)

Same as the buster (7af), same measurement. With a two-frame press of A the real ROM's navi steps
his pose on frames 4, 8, 11 and 17; this build stepped on 2, 6, 9 and 15 -- two early, exactly
the length of the press. `is_just_released` aligns all four and everything after: a Cannon's use
goes from 22277 differing pixels to 256.

CORRECTED: THE CHIP BUTTON IS PRESS-DRIVEN, NOT RELEASE-DRIVEN. Holding A for sixty frames on the
real ROM still fires the chip two frames after the press and drops the icon then; a two-frame
press cannot tell "release" from "press + 2" apart, and reading it as a release was wrong for
every longer hold. Only the BUSTER waits for the button to come up -- verified separately by
holding B for eighty frames, through which the navi stands in his idle and charges.

AND THE D-PAD IS THE SAME TWO FRAMES. The chip window's cursor moves TWO frames after the
direction: held six frames, the real ROM's bracket stays on OK for two and is on the new slot on
the third. 108 of the 110 frames of a two-step walk then match, card and all. Three findings with
the same two frames -- the buster, the chip button, the cursor -- is the strongest hint yet that
the real ROM simply acts on its pad a couple of frames after reading it, rather than each of
these being its own rule. Anyone refactoring that should re-derive 7ae's constants, which absorb
the same two frames in their own way.
NOT RESOLVED: the last frame of a cursor move. At a delay of two the bracket is one frame early;
at three the card is one frame late.

The 256 were the CHIP-IN-HAND ICON on one frame, AND THE EXPLANATION WAS WRONG. It was recorded
as the button's RELEASE arriving late through an input lag, and "nothing in the drawing can drop
an icon before it knows the button is up". The button never comes up. Measured again with A HELD
for five frames:

  icon present   real  through the press's frame + 1, gone from + 2
                 rust  through + 2, gone from + 3
  navi's pose changes  frame + 4 on BOTH sides

So the attack was aligned all along and the real ROM simply takes the chip out of the hand ONE
FRAME BEFORE the use fires. `chip_use_in` reads 1 on that frame, and skipping the icon there takes
the check to zero. The lesson is the older one restated: when a residue is blamed on something
that cannot be fixed, check the blame before accepting it -- the measurement that would have
falsified this one is a five-frame hold, which takes a minute.

## 7ah. Comparing an ENEMY, and the wave that ran a frame late (2026-09-07)

Sixty of the seventy frames of a Mettaur's attack cycle are identical to the real ROM.

HOW TO ALIGN A VIRUS. It acts on an RNG neither side shares, so there is no fixed offset to guess.
Instead, list the frames on which its own BOUNDING BOX changes on each side and look for the lag
that lines the two lists up: real 140, 141, 142, 145, 153, 157, 166 against rust 160, 161, 162,
165, 173, 177, 186 -- a lag of twenty, exact on every boundary. Then compare pixels at that lag.
This is the general way to compare anything the RNG drives.

WHAT IT FOUND: the shockwave ran ONE FRAME BEHIND for its whole flight. Shots are stepped before
the actors, so a shot the enemy spawns during its own update misses that frame's tick -- the same
pre-tick the bombs' effects already do, and `Shot::shockwave` now does it too. Three of the wave's
four differing frames go to zero; the cycle goes from 16 differing frames and 5117 px to 10 and
2430.

WHAT IS LEFT: four frames at the end of the cycle, 698 px each, where the real Mettaur holds its
pickaxe up a frame or two longer than this build.

AND A NEGATIVE RESULT WORTH KEEPING (2026-09-07). The obvious fix is wrong. `object_exitAttackState`
writes CurAnim=0 on the tick Unk_10 is decremented TO zero (asm31.s:170737), so only 63 of the
counter's 64 ticks show the pose -- and animation 1's own sub-frame durations in
`assets/mettaur.bin` sum to exactly 63, which looks like confirmation. Setting `SWING.frames` to
0x3f changes NOTHING: animation 1's last sub-frame (index 15) has OAM data identical to the idle
pose, so shortening the window by a tick swaps one image for a pixel-identical one. Measured on a
wider window it is actively WORSE -- 0 differing frames of 70 becomes 21 and 16961 px -- so it is
not a harmless no-op either.

What the tail actually looks like, from run-length analysis of which captured frames are identical
to their neighbour, done independently on each side: the first fifteen segments of the swing's tail
match EXACTLY (2,1,1,3,8,4,9,3,2,2,2,2,4,10,6). Only the last five ticks before idle diverge --
the real ROM holds three distinct poses there (2,2,1 ticks) and this build four (1,1,2,1). That is
animation 1's last two authored sub-frames plus the attacking-to-idle handoff tick. A tick-by-tick
simulation of `Actor`/`Player` predicts (1,2,2), which is neither, so something in the handoff is
not modelled by either reading. Unresolved.

## 7ai. The shockwave lights the panel it stands on (2026-09-07)

A whole effect this build never drew, and the reason it was never noticed is worth as much as the
effect: THE CHIP CAPTURES RUN WITH THE BACKGROUNDS STRIPPED, and this is a background tile. Turn
`--disable-bg` off and look at a live field now and then; the comparison that finds everything
else cannot see this class of thing at all.

The Mettaur's shockwave paints the panel under it with one of the field's two highlight overlays
-- a solid yellow block -- for all 0x16 frames it dwells there, travelling with it panel by panel.
Two details from the same capture:
- THE LIGHT LINGERS three frames. At every hop the new panel and the old one are lit together for
  exactly three frames.
- A PANEL SOMEBODY IS STANDING ON IS NOT LIT. The wave passes through the navi's own panel with it
  dark and lights the one behind him again on the far side. NOT VERIFIED beyond this one capture:
  it is a single observation, not a rule read out of the disassembly.

VERIFIED: with both sides captured `--disable-obj` (backgrounds only) and aligned on the wave's
own dwell boundaries, 87 of 90 frames of the field's panels are identical, highlight and all. The
three that differ are single dwell boundaries a frame out.

## 7aj. The HP box counts down and flashes (2026-09-07)

Found by a cheap audit worth repeating: list the COLOURS each side shows over a long run and
subtract. Three appeared in the real ROM and never here, and two of them were the HP box's orange.

The player's box was jumping straight to the new number in white. It should count down and flash,
and now does -- a drop of ten goes 5, 4, 1 on both sides.

- THE STEP IS `|difference| / 8 + 4`, not `+ 2` as the code had it. That is what makes the first
  step five rather than three.
- THE FLASH HOLDS 17 FRAMES, of which three are the countdown, so the constant is 15.
- THE FLASH IS NOT A SECOND SET OF DIGITS. The tiles never change: the real ROM swaps four
  entries of the box's palette bank -- 4, 5, 6 and 11 -- to an orange ramp and swaps them back.
  Dumping BG palette RAM on a flashing frame gives the four values directly. Building it as an
  orange digit set instead gets the wrong orange by one palette entry, which is how the mistake
  showed.
- AND THE PALETTE WRITE HAS TO BE HELD BACK A FRAME. A palette lands on the frame it is made and
  the box's tile writes land on the next, so swapping the ramp the moment the counter flashes
  paints the OLD number orange for a frame.

NOT VERIFIED: the heal flash. Nothing in the capture heals the navi, so the same ramp is used for
both.

## 7ak. One command for every check (2026-09-07)

`python3 tools/regress.py` runs all of them: the 43-chip scoreboard, the battle screen's tiles,
a whole frame with sprites, the chip window, the preview card, the RESULT window, the navi's
warp, the buster and a chip use. Each check rebuilds its own ROM, captures both sides, aligns
them the way that fixture is aligned, and prints what it got against what it should get.
`--only name,...` runs a subset; `--list` shows the numbers.

WHY IT EXISTS. The scoreboard covered the chips and everything else was run by hand, one fixture
at a time -- which is exactly how a regression in one survives a session spent on another. Two of
today's changes helped one fixture and cost others, and both were caught only because somebody
remembered to check.

A check's `want` is what it measured when last verified, not zero: `chips` wants 0 now that the
arcs are read rather than fitted (7ao), and `chip-use` wants 256 (the chip-in-hand icon, one
frame). There is a tenth check, `rollup`, which is not a comparison: it runs the full battle
under a long input script and asserts it does not crash (7an).
A check that comes out BETTER says so, and its number should be written down.

AND EXACT NOW MEANS ZERO. The scoreboard's old "floor" -- 369 px of ENEMY DELETED banner on one
frame of every comparison -- is gone: `patch_sterile.py` patches out sub_801E838, the routine
that uploads the banner's text. Removing it exposed five chips that had been passing against the
floor while carrying a real residue: AreaGrab, Invisibl, Barrier, Barr100 and Barr200 each flash
the CHIP'S NAME as eight 8x16 objects at (28,32) for one frame, out of the same OBJ VRAM the
banner uses, and this build draws nothing there. That is the argument for patching a thing out
rather than measuring around it: a floor hides whatever else is under it.

## 7am. The chip-name popup, patched out; 41 of 43 exact (2026-09-07)

Those five are now zero, and the fix was the same move again: find the routine, patch it out.

The popup is `sub_801E95C` (asm/asm00_2.s:31261). It looks the chip up
(`getChip8021DA8`), calls `sub_801EA5A` to pick the local player's buffer and destination
(`byte_203EDA0` -> `0x6016E00`; player two gets `byte_203EFA0` -> `0x6017280`), renders the
name through `renderTextGfx_8045F8C`, and queues the damage digits beside it through
`sub_801EA34` (`0x6017060` / `0x6017160`). Its only caller is `sub_801E8CC`, one entry in the
state table at `off_801E944`, and that caller pushes and pops its own `r0` around the call, so
the return value is discarded and a bare `bx lr` at the entry is safe. `patch_sterile.py` writes
`70 47` at `0x0801E95C`.

WHY IT ONLY EVER COST ONE FRAME. The tiles are uploaded once and the objects then live off VRAM
for the ~58 frames the name is up. The harness zeroes `0x6016E00` before every frame, so every
frame but the upload frame draws transparent -- the same shape of artifact the banner had. For
AreaGrab that frame was the attack's c18, 127 px at x 29..91, y 40..42: the bottom three rows of
eight 8x16 glyphs, the rest of them above the diff window's y=40.

WHY sub_801E838 WAS NOT ENOUGH. It is the banner AND it writes to the same `0x6016E00`, which is
what made it look like one problem. It is not: the banner is five 32x16 objects written in a 5x4
loop up to `0x6017300`, the name is eight 8x16 glyphs written by the text renderer, and they are
two routines that happen to share a tile region.

SCOREBOARD: **41 of 43 exact** after this, every chip at literal 0.0 except BugBomb 1.1 and
VDoll 1.6. Both of those turned out to be one frame of one-pixel rounding on a fitted arc, and
reading the real constants out of the object took them to zero as well (7ao): **43 of 43**.

## 7z. The preview card, all four rows, 0 px (2026-09-07)

The chip window's card is exact for all five of the capture's chips -- five elements, five
codes, five powers -- and the way in was two corrections to a premise.

THE NAME IS NOT PROPORTIONAL. It is the fixed 8x16 battle font `dword_86B7AE0`, the one
`assets/text_font.bin` already carried for the RESULT window, written into the row's eight
cells left to right and padded with the font's blank. The glyph index IS the game's own
character code, so `constants/bn6-charmap.tbl` indexes the font directly, and the tiles are the
COLOUR-ADDED copy: `sub_3006C18` (asm/asm38.s:2381-94) adds a 32-bit word from `dword_3006B84`
(0, 0x44444444, 0x88888888, 0xCCCCCCCC) to every glyph word on the way to VRAM, and this window
passes index 8. The blank it pads with is then flat colour 8 -- which is exactly what
`CARD_INTERIOR_TILE` is, so the row needs no separate background.

THE OTHER THREE ROWS ARE NOT THAT FONT AT ALL. They are three little tables of the window's own,
stored READY-COLOURED so nothing is added on the way to VRAM:
- `dword_86E2E98` -- 28 code letters, 0x40 each: A-Z, then '*' and a blank, ink 0xb. Indexed by
  the same code byte the slot glyphs use.
- `dword_86E411C` -- 10 damage digits, 0x40 each, 0-9 in order, ink 9.
- `dword_86E3598` -- 11 element icons, 0x80 each (16x16), indexed by the chip's element byte,
  0x0a being null.

HOW TO FIND ART YOU CAN SEE ON A LIVE SCREEN. Searching the ROM for the tiles themselves finds
nothing, and neither does searching for their SHAPE tile-aligned: every glyph starts with three
blank rows, so its cell begins twelve bytes before its ink and a 32-byte-aligned scan never
lines up. Search ROW-aligned (every 4 bytes) for the shape -- the ink mask over any one ink
value and any one background value, starting at the first NON-BLANK row -- and all three tables
fall out on the first pass. This is the general trick for anything the game composes at runtime.

AND THE SHARED ICON BANK HAS A PER-ELEMENT TAIL. `dword_86E3B18`, immediately after the icons,
is 11 rows of six BGR555 words: entries 10 through 15 of BG bank 11. Entries 10-12 are the icon
frame's colours, the same every row; 13-15 are the ELEMENT'S OWN, and the game writes them as it
draws the card. Bank 11 had been read off one live menu (7u) -- which happened to be showing a
null-element chip, whose last three are zero -- so AirShot's wind icon came out black in all 64
of its colour-13 pixels and Sword's lost 24. This is the same trap as 7t: one save state cannot
tell you which parts of a palette are per-state.

A PICKED SLOT STILL PREVIEWS ITS CHIP. Walk the real ROM's cursor onto its picked Cannon and the
Cannon card comes up, even though the slot itself shows the empty-cell art. Only OK and a slot
with nothing in it leave the card without a chip.

THE FIXTURE. `demo-custmatch` has the cursor on OK, where the real ROM shows its "sending chip
data" card and CLEARS the name and the row under the picture -- so it cannot see any of this.
`demo-cardname` is the same window with the cursor on the first slot. On the real ROM, hold Left
for six frames from `/tmp/chipselect.state`: a one-frame tap does nothing, the menu wants the key
held. Walking further with `--script` on both sides compares all five cards in one run.
`demo-custmatch` had also stopped opening its window at all -- it fields no enemy, so the
all-enemies-deleted win fired on frame one and held the gauge, and the gauge is what opens the
window.

## 7y. The five bomb chips left, named and half-found (2026-09-07)

The bomb family (attack_family 0x12) has five chips this build does not draw. Their NAMES come
straight out of the ROM -- tools/chip_export.py already parses
data/textscript/TextScriptChipNames0.s, so `chip_names()` gives them without guessing:

  id 67  BugBomb   subfamily 07, power 0
  id 68  GrasSeed  subfamily 0d, power 10, params 2,2, element 3
  id 69  IceSeed   subfamily 09, power 10, params 1,1, element 1
  id 70  PoisSeed  subfamily 0c, power 10, param2 3, element 10
  id 150 VDoll     subfamily 08, power 10, element 7

POISSEED IS BUILT -- 6.9 px/frame over seventy frames against a floor of 5.3, throw, arc, landing
and poison all matching. Three things it taught:
- ITS ARC NEEDED NO FITTING. The plain bomb launch and gravity put the pod on the real ROM's
  pixel at every frame. Try that before reaching for the tracker.
- A SPRITE'S PALETTE CAN BE A SHIFT PLUS AN OAM OFFSET. Every part of both animations carries an
  OAM palette offset of 9, the chip's shift is 3 (its attack_param_2, as BigBomb's 3 picks the
  red bomb), and the live palette is the sprite's index 12. So the offsets count from the SHIFTED
  palette. And the per-offset palettes were cached by the offset alone and never cleared, so the
  pod kept IceSeed's cyan however it was shifted -- set_palette_add and set_offsets_follow_shift
  clear that cache now.
- AN EFFECT'S TIMING HAS TWO KNOBS, and one alone is not enough. The poison sheet spawned when
  the pod lands runs a frame early; spawned a frame later it runs a frame late. It is spawned a
  frame later AND already one tick in, so its first frame shows for exactly one frame -- the real
  ROM's landing frame carries neither pod nor sheet.

ICESEED AND GRASSEED CAME FREE WITH IT and are both EXACT. They are the same pod sprite and the
same nine-panel sheet, told apart by palette:
- THE POD's palette is the chip's attack_param_2 as a shift on top of the OAM offset of 9 every
  part carries -- IceSeed 1, GrasSeed 2, PoisSeed 3, landing on the sprite's palettes 10, 11, 12.
- THE SHEET's DOES NOT FOLLOW IT. Shifting the sheet by the same amount took PoisSeed from 6.9
  px/frame to 178.8. PoisSeed and IceSeed share the sheet sprite's own palette 0; GrasSeed takes
  8. Dump OBJ bank 1 while a sheet is up and compare it against the asset's palettes.
Neither sets its panels: the field asset has no grass or ice art. That is the one thing still
missing from them, and it is invisible in the sterile arena either way.

BUGBOMB AND VDOLL ARE BUILT TOO, so the bomb family is complete at eleven chips. Both THROW AND
STAY: the object stops where it lands and keeps standing, so neither bursts. BugBomb is 35.4
px/frame against a floor of 5.3 and VDoll 10.7.
- BugBomb's ball is the SEEDS' sprite in another animation (4 held, 5 thrown) and flies flatter
  and slower than a bomb.
- VDoll's doll is its own sprite, byte_83262C0.spr, and arcs to the top of the screen and hangs
  there -- its own launch, gravity and a sixty-frame flight. Its HELD object is the seeds' sprite
  again, animation 0. Substituting that alone took it from 233 px/frame to 157 before any arc
  fitting, so CHECK THE HELD OBJECT SEPARATELY: it need not be the thing that is thrown.

POISSEED WAS THE ONE TO BUILD FIRST because its panel art already exists: the field asset carries
HOLE, BROKEN, NORMAL, CRACKED and POISON, and the ROM's panel tilemap has only those five, so
GrasSeed's and IceSeed's panels are art this project does not have at all.

What is already known about PoisSeed, from a sterile capture with chip 0x46 poked in:
- The navi throws a small magenta pod in an arc. In OAM mid-flight it is a 16x16 object at tile
  0x23 in OBJ palette 1, with its ground shadow a 16x8 at tile 0x21 -- the same shadow-as-part-0
  shape the bombs use.
- Those four tiles are byte_82F569C.spr, found by pulling them out of OBJ VRAM and searching all
  97 sprite files. tools/spr_export.py reads it: 10 animations, 25 frames.
- When it lands, a pale green three-by-three grid appears over the ENEMY's half. With the
  backgrounds stripped it still shows, so the poison overlay is drawn with OBJECTS, not by
  swapping panel tiles.
- Its arc can be fitted the way FlshBom's and BlkBomb's were: track the pod by its magenta
  colours, and SWEEP the constants against the capture rather than fitting a parabola to the
  tracked centroid (7x's note on why).

## 7ao. Stop sweeping arcs: read them out of the object (2026-09-07)

`tools/throw_dump.py <chip>` prints a thrown chip's launch constants out of the
running game, and every arc in this port is now the game's own numbers rather
than a fit. The two chips that were still off -- BugBomb 1.1 px/frame and VDoll
1.6 -- went to ZERO on the first try with them. **43 of 43 exact.**

HOW IT WORKS. Dump all 256K of EWRAM once per frame across the flight and look
for a word that advances by the same non-zero step every frame: a thrown thing's
across-speed never changes, so that word is its X. The battle object's layout
follows (sub_80C5C9C, asm31.s:29505, reads XYZ from +0x34 and VX/gravity/VZ from
+0x40), and walking the Z velocity back a frame at a time -- the gravity step is
constant, so this is exact -- reaches the spawn height 0x300000 and gives the
launch velocity and the frame it was thrown on.

WHY SWEEPING COULD NEVER FINISH THE JOB. A launch a little too weak and a pull a
little too soft draw the SAME PIXELS, because the two errors cancel over the
flight; that is the ridge 7aa describes. Every fitted constant in this file was
sitting on one:

| chip     | swept              | actual             |
|----------|--------------------|--------------------|
| BlkBomb  | vz 0x22051 g 0x27C0| vz 0x2236E g 0x2800|
| LilBolr  | vz 0x22280 g 0x27F0| vz 0x2236E g 0x2800|
| BugBomb  | vz 0x25D60 g 0x27C0| vz 0x26062 g 0x2800|
| FlshBom  | vz 0x2BD00 g 0x3000| vz 0x28CCC g 0x3000|
| VDoll    | vx 0x1EEA0 vz 0x31600 g 0x2060 | vx 0x1EEEE vz 0x2F333 g 0x2000 |

Everything on the left drew the right pixels except at a rounding boundary, and
a rounding boundary is exactly where BugBomb's and VDoll's last residues were.

TWO THINGS THE READ-OUT FOUND THAT NO SWEEP COULD.

1. **LilBolr is BlkBomb.** Identical vx, vz and gravity, to the digit. Two
   separate sweeps had found two nearby but different answers and nothing said
   they were the same launcher.
2. **SOME OBJECTS MOVE AND THEN FALL.** A bomb applies the pull and then moves
   (sub_80C5C9C, asm31.s:29536); VDoll's doll (sub_80D47C0 loc_80D4848,
   asm31.s:60530) and FlshBom's ball move and then apply it. That is half a
   step, and it is a pixel wherever the arc is steep. It also explains the note
   7aa left behind about FlshBom's fit having to be "a step behind the naive
   one": 0x2BD00 is 0x28CCC + one gravity step to within 0x34. `Bomb` now
   carries `moves_before_falling` and does it in the right order.

THE FIVE LAUNCHERS, all spawning at Z 0x300000 and X + 4 ahead of the navi:

| launcher | chips                                        | vx      | vz      | g      | timer |
|----------|----------------------------------------------|---------|---------|--------|-------|
| MiniBomb | MiniBomb EnergBom MegEnBom BigBomb, 3 seeds  | 0x2E666 | 0x20666 | 0x2800 | 40    |
| BlkBomb  | BlkBomb LilBolr                              | 0x2C000 | 0x2236E | 0x2800 | 42    |
| BugBomb  | BugBomb                                      | 0x2C000 | 0x26062 | 0x2800 | 42    |
| FlshBom  | FlshBom (moves first)                        | 0x2E666 | 0x28CCC | 0x3000 | 40    |
| VDoll    | VDoll (moves first)                          | 0x1EEEE | 0x2F333 | 0x2000 | 60    |

THE LESSON, and it generalises past arcs: when a constant lives in the game's
memory while you can see its effect, READ IT. A sweep converges on the set of
values that draw what you are looking at, which is bigger than the set of true
values, and the difference shows up later as one frame you cannot explain.

## 7aa. One launcher throws them all (2026-09-07)

Sweeping the three arc constants of the three worst chips landed all three on the SAME across-
speed, and two of them on the same gravity:

| chip     | vx           | vz      | gravity      | before | after | floor |
|----------|--------------|---------|--------------|--------|-------|-------|
| BlkBomb  | 0x2C000      | 0x22051 | 0x27C0       | --     | exact | 7.4   |
| BugBomb  | = BlkBomb's  | 0x25D60 | = BlkBomb's  | 35.4   | 6.4   | 5.3   |
| LilBolr  | = BlkBomb's  | 0x22280 | 0x27F0       | 34.6   | exact | 7.7   |
| VDoll    | 0x1EEA0      | 0x31600 | 0x2060       | 10.7   | 6.9   | 5.3   |

So the thrown things share a launcher and differ mostly in how hard it throws. When a new chip's
arc needs fitting, START from BLKBOMB_VX and BLKBOMB_GRAVITY and sweep vz alone -- that is one
dimension instead of three, and it is where two of these three ended up anyway. VDoll is the
exception, and it is the one that is not a bomb.

HOW TO SWEEP. `tools/chip_compare.py` reports a mean; a shell loop that seds the three constants,
runs it, and restores them at exit does the search in about 25 seconds a point. Do not sweep one
constant at a time to the end: vz and gravity trade off along a RIDGE (a taller throw with a
harder pull looks the same), so step along the ridge, not across it. Every minimum found here was
a plateau several hundred wide; take the middle.

WHAT IS LEFT IS NOT THE ARC. Each of the three now has a handful of pixels on a handful of
frames, and tracking the object's bounding box frame by frame shows the paths agreeing exactly.
- BugBomb: one frame, 80 px, the last frame before it lands -- the ball a pixel right and a pixel
  down of the real one, on that frame alone. The sweep's minimum is a plateau and every point on
  it has the same frame wrong, so this is the model's discretisation, not a constant.
- VDoll: five frames, 109 px, all in x 129-139 as the doll comes back down at the right edge of
  the compare window. Its ground shadow's two frames went away with the shadow's OAM slot, and
  sweeping the across-speed to 0x1EEA0 took the rest of the arc; what is left is the doll's own
  art at the frames where it is half off the box.
- LilBolr: DONE. The last three frames were the boiler's HP FIGURE passing behind the navi's
  head -- the figure is drawn with the thrown object, the thrown object after the actors, so his
  helmet cut the digits: 69 white pixels in the real ROM against 50 in this build. The real ROM's
  OAM puts the figure ahead of the navi. When a residue sits where two objects overlap, count the
  pixels of ONE colour on each side before assuming a position is wrong; the figure's bounding
  box had been identical all along.
- PoisSeed: DONE, and the answer was OAM ORDER. A thrown object's GROUND SHADOW goes BETWEEN the
  navi's body and the navi's OWN shadow: dumping OAM at the throw, MiniBomb's bomb is entry 9,
  the navi's body 10-13, the bomb's shadow 14 and the navi's shadow 15. This build drew the whole
  thrown object after the actors, under all of them. PoisSeed's pod shadow is BLACK in its palette
  and so bites a notch out of the navi's grey shadow where they overlap; IceSeed's and GrasSeed's
  are grey, the same colour as the navi's, which is why only PoisSeed ever showed it.
  MOVING THE WHOLE BOMB ABOVE THE NAVI IS WRONG, and the measurement is worth keeping: PoisSeed
  6.9 -> 6.0 but IceSeed and GrasSeed 5.3 -> 6.0, MiniBomb 6.2 -> 7.0, BlkBomb 7.4 -> 10.1,
  LilBolr 7.7 -> 18.2, FlshBom 7.7 -> 9.9, BigBomb 4.9 -> 5.6. Only the SHADOW moves, and
  `Actor::show_with_underlay` already offers exactly that slot -- it runs the closure immediately
  before the navi's part 0. Every other bomb chip is unchanged and PoisSeed is exact.
Track the bounding box before touching a constant: if it already matches, the arc is right and
the residue is animation or a part, not physics.

## 7x. The RESULT window (2026-09-07)

It had never been compared: demo-results needs a chip press the capture harness cannot land, so
`demo-resultmatch` puts the window up at once with the capture's own readout -- 0:29:33 is 1760
frames, busting level 2 -- against /tmp/noenemy2.state. Three defects, and each is a class:

A POSITION READ FROM THE DISASSEMBLY IN THE WRONG UNITS. "Rests at x = 3" is a tile COLUMN, not a
pixel; the window sat 24 px left and 16 px up of the real one. Aligning the two images by search
gives the offset in one step -- do that before trusting a number lifted from the code.

PALETTE BANKS TAKEN BY SOMETHING ELSE. The window draws in banks 9-11 and the CUSTOM gauge holds
bank 9 all fight, so the window came up in the gauge's greens. It takes its banks back on open
now, as the chip window already did. Any element that shares a bank has to do this.

A MISSING SUB-IMAGE. The coin in the GET DATA box is a 7x6 image -- the same shape as a chip
card's picture -- at dword_8732E54 with palette dword_8733394, both matched byte for byte against
a live results screen's char block. It is kept as its own tileset rather than padded into the
window's blob, which would cost 15 KB of zeroes to reach tile 0x1e8.

THE REWARD TEXT WAS NEVER PROPORTIONAL. "100 z" is the fixed battle font `dword_86B7AE0` with 8
added to every nibble -- `sub_3006C18` (asm/asm38.s:2381-94) adds a colour word from
`dword_3006B84` to every glyph word on the way to VRAM and this window passes index 8, which is
why a search for the raw font finds nothing on screen. The zenny symbol is glyph 0xb3, found by
pulling that line out of VRAM and searching all 448 glyphs. Same path as the chip card's name
(7z).

AND THEN FOUR MORE, of which only one was in the window's own map:
- THE GET DATA READOUT'S BOTTOM EDGE. The stored map has a lit tile there (top pixel row colour
  9) where the live window has ten flat cells, tile 0xc4. The game replaces that run as it draws
  the reward. 80 px, one pixel row -- the last thing inside the window.
- THE CUSTOM GAUGE GOES. Label, bar and end caps, all of it, the moment the window comes up; only
  the HP box stays. `set_gauge` takes a flag for it.
- SO DOES THE EMOTION WINDOW. Same rule as the ENEMY DELETED banner: it belongs to the fight.
- THE BADGE AT THE TOP-LEFT IS NOT PART OF THE WINDOW. It is the chip select screen's
  regular-chip mark hung as OAM entry 0 -- a 16x16 at (37,21), OBJ tile 0x200 in bank 11 -- and
  both the art at that tile and that bank match the chip window's byte for byte. When a window
  has an ornament the map cannot explain, dump OAM.

0 px now across the window, its badge and the HP box. What still differs is the field and
backdrop outside the window, which the fixture does not reproduce. `demo-resultmatch` carries the
capture's 60 HP too, as `demo-hudmatch` does.

## 7aq. The banner is TEXT, and it is now drawn (2026-09-07)

"ENEMY DELETED" is in the build, matched to the real ROM's pixels over all 58 frames of its
roll-out, and so are the other forty-four messages the game keeps.

IT IS NOT A PICTURE. The real ROM has a font of 8x16 cells and a record per message: the first
word is `(y << 8) | x` and the words after it are one glyph pointer per cell, terminated by
`byte_801FDC0` -- which is itself the BLANK glyph, so `sub_801E838` (asm00_2.s:31106) simply stops
advancing its cursor and keeps writing blanks out to the twentieth cell. Twenty cells go up as
five 32x16 objects. Two arrays of records, at `pt_801EF84` (20) and `pt_801EFD4` (27), and two of
those 47 slots are not records at all -- the arrays abut and the boundary entry reads as one,
which shows up as glyph pointers outside the ROM.

`tools/banner_export.py` walks all of that into `assets/banner.bin`: 40 distinct glyphs, 45
messages, 4506 bytes. Its `--sheet` renders every message, which is how the ids were identified --
0 BATTLE START!, 1 ENEMY DELETED, 2 MEGAMAN DELETED, 3 TURN START!, 4 FINAL TURN!, 5 YOU WIN!,
6 YOU LOSE, 7 DRAW!.

THE PALETTE IS NOT THE TEXT FONT'S. `sub_801E838`'s last act is to stage the sixteen colours at
`byte_86F2900`, which are the banner's own yellow-on-blue, and the asset carries them. Rendering
the sheet in the chip-name popup's bank 11 gives a blue-on-black that looks plausible and is
wrong -- worth remembering when a sheet "nearly" looks right.

THE ROLL-OUT IS THE POPUP'S, exactly: the same 58-entry vertical-scale sequence, the same shared
affine matrix, read out of OAM for both. `banner::SCALE` is the one copy and `battle.rs`'s popup
uses it.

VERIFIED: `regress.py`'s `banner` check builds `demo-sterile,demo-banner`, which puts ENEMY
DELETED up on the clock's 100th frame, and compares 58 frames against a capture that forces the
enemy's HP to zero and presses Start at 10, where the real banner runs frames 49..106. 0 px. The
box stops at x=145 because the deleted enemy's remnant dissolves to the right of it for a hundred
frames, and the real ROM for that fixture is built with `patch_sterile.py --keep-banner` -- the
sterile ROM patches the banner OUT, which is what every chip comparison needs and precisely what
this one cannot have.

WHAT IS MEASURED AND WHAT IS PLACED. Measured: the art, the palette, the position, the 58-frame
animation, and that the RESULT window starts sliding 110 frames after the banner goes up (banner
49..106, window 159), which turns `RESULTS_DELAY` from an admitted 30-frame stand-in into a read
number. NOT measured: how long after the last enemy is gone the banner itself goes up. This build
puts it up the moment the fight is over.

## 7as. BATTLE START!, and every check at zero (2026-09-07)

A battle now opens the way the game opens one: the field fades in, the enemy materialises, and
BATTLE START! unrolls over a fight that is already running. The research (7ar) says why it does
not pause: `sub_8008064` (asm00_1.s:10386) raises message 0 and there is no `PauseBattle` call
anywhere in it, and `sub_800801C` is ticked every frame from `sub_800938A` alongside the normal
chip-hand processing. So the banner goes up without touching the intro's own gate.

NOT VERIFIED: how many frames after the intro it goes up. There is no save state at a battle's
start to compare against, and making one means playing the game to a battle. Everything else about
it -- the art, the palette, the position, the 58-frame roll-out -- is the same asset and the same
animation the ENEMY DELETED check already matches at 0 px.

NOT IN A DEMO BUILD, and the reason is worth keeping: every fixture that fields an enemy compares
against a capture taken mid-battle, where no banner is up. `check_chip_use` starts at frame 130
and the banner ends at 126. Four frames is not margin, so `cfg!(feature = "demo")` keeps it out,
the way the chip-in-hand icon is kept out of the sterile arena.

AND EVERY CHECK IS AT ZERO. All twelve, for the first time:

    chips 0 (43 of 43)   tiles 0   field 0   window 0   card 0   result 0
    warp 0   buster 0   chip-use 0   popup 0   banner 0   rollup 0

`chip-use` was the last one, at 256 px, and the note explaining it was wrong (7ag).

## 7ar. Where the banner's numbers come from (2026-09-07)

Traced in the disassembly after the banner was already matched by measurement, which is the right
order: the pixels agreed first, and this says why.

ONE ENTRY POINT. Every banner goes through `sub_801E792` (asm00_2.s:31016), which takes
`messageIndex * 4` -- a byte offset into what is really ONE 47-entry pointer array, since
`pt_801EF84 + 0x50 == pt_801EFD4` -- refuses if a banner is already up (bit 0x8000 of
`eStruct2035280+0x40`, asm00_2.s:31024-31029), latches the record's KIND byte into the state block
`byte_2036840` (31053-31061) and dispatches through `off_801E944` (31258-31265): kinds 0/1/2 to
`sub_801E828`, kind 3 to `sub_801E8CC`, kind 4 to `sub_801E8EA`. There are 34 call sites in three
files.

THE ROLL-OUT IS THREE PHASES, not a table. `sub_801CE28` (asm00_2.s:27587) ticks a phase byte and
a counter in `byte_2036840`, and each phase calls `sub_802FE7A` (asm03_0.s:20115) -- an OAM affine
writer at angle 0, so pure scale -- with `r2 = pd / 4`:
- ROLL-IN, `sub_801CE6C` (27624): `r2 = 0xE0 - counter * 0x20` for counter 1..5, so pd 768, 640,
  512, 384, 256. Five frames.
- HOLD, `sub_801CE92` (27647): only counters 1, 2, 3, 46, 47 and 48 touch the matrix -- 208, 224,
  256 ... 224, 208, 256 -- and counters 4..45 fall straight through without writing, so the matrix
  simply KEEPS 256 for 43 frames. That is why the hold reads as a plateau with a wobble at each
  end: nothing is animating it in between. 48 frames.
- ROLL-OUT, `sub_801CED2` (27688): `r2 = 0x40 + counter * 0x20` for counter 1..5, so 384, 512,
  640, 768, 896, then the affine slot is freed and the objects go. Five frames.
5 + 48 + 5 = 58, which is exactly what the capture shows. The horizontal scale is the constant
`r1 = 0x40` in all three (27633, 27672, 27697).

THE GAP TO THE RESULT WINDOW is armed by the same handler that raises the banner: `sub_80081A4`
(asm00_1.s:10542) sets a countdown at `[r5,#8]` to 0x66 = 102 frames or 0x5e = 94 depending on the
battle mode (10577-10592), and leaving that state needs BOTH the countdown and the banner
reporting idle through `sub_801E754` (asm00_2.s:30973). 102 frames from the banner's frame 49 is
151, against the 159 measured; the remaining 8 frames are in states 6-9 of the same end-of-turn
machine (`off_8008038`, asm00_1.s:10370) or the window's own lead-in, and were not traced. This
build uses the measured 110.

WHICH MESSAGE, BY CALLER: 0 BATTLE START! and 3 TURN START! and 4 FINAL TURN! all come from
`sub_8008064` (asm00_1.s:10386), state 1 of `off_8008038`; 1 ENEMY DELETED is the default in
`sub_80081A4` and 2 MEGAMAN DELETED in `sub_800825A` (10632), each upgraded to 5 YOU WIN! or 6 YOU
LOSE when `sub_800A152()` returns 7. No `PauseBattle` call sits inside `sub_8008064`, so BATTLE
START! does NOT stop the fight.

THE CHIP-NAME POPUP IS A BANNER TOO, in the same machinery: message ids 19 and 20 are kind 3,
which dispatches to `sub_801E8CC` -> `sub_801E95C`, and they are raised by `object_drawChipName`
(object.s:183-239) gated on a `ChipData+9` flag bit and a chip-category check (`sub_800B892`).
So the "attack_family 0x15" rule 7ap uses is a proxy for that gate; it is right for all 43 chips
in the scoreboard, and if a chip is ever added that disagrees, this is where to look.

AND PAUSE FREEZES IT. The pause menu (`sub_802B7A0`, asm03_0.s:10937) raises message 9 or 13, both
kind 2, and kind 2 is exactly what makes `sub_801CE28` stop incrementing its counter at 4
(27590-27603): the banner sits fully extended for as long as the game is paused. Unpausing calls
`sub_801E780`, which forces the counter to 45 and drops it into the hold's tail wobble and the
normal roll-out. Worth knowing if PAUSE is ever implemented -- it is a real menu, with a cursor
box, text from `TextScript86F0300` and its own screen fades.

## 7ap. The chip-name popup, DRAWN rather than patched away (2026-09-07)

Five chips put their NAME up in the middle of the screen while they present, and this build now
draws it, matched over its whole life. `patch_sterile.py` no longer removes it: something the game
shows is something to match.

WHICH CHIPS, and the rule is in the data. `attack_family: 0x15` in `data/ChipDataArr.s`, which
AreaGrab, Invisibl, Barrier, Barr100 and Barr200 carry and nothing else does. Checked the other
way as well, by dumping OAM on the attack's 40th frame for all 43 scoreboard chips: exactly those
five put objects up. Recov looks like it should and does not.

WHAT IT IS, read out of OAM frame by frame (`--dump 0x7000000:1024` at each frame in turn):
- One 8x16 object per letter of the name, all at y=32, in OBJ palette bank 11, at OAM entries 0
  upward so they stand over everything.
- CENTRED on x=60: an eight-letter name runs 28..92 and a seven-letter one 32..88.
- The glyphs are the RAW half of `assets/text_font.bin` -- the asset carries the plain glyphs and
  then a colour-added copy, and this uses the plain ones. Checked byte for byte against the tiles
  the real ROM leaves at 0x6016E00 for every letter of "Barrier".
- OBJ bank 11 is `0000 7ffe 14a5 03e0 7bde 7fbc 7f99 6e6f 61cc 037f 029f 0280 3547 37f6 7bd1
  4108`, the same sixteen colours for all five chips.
- Every object shares ONE AFFINE MATRIX whose only moving part is the vertical scale, and it is
  the same 58-frame sequence for all five: 768, 640, 512, 384, 256, 208, 224, then 256 held for
  43 frames, then 224, 208, 256, 384, 512, 640, 768, 896, gone. Bigger is FLATTER (the matrix maps
  screen back to texture), so it unrolls from a flat line, overshoots into a stretch a fifth
  taller than life, settles, and rolls back up.
- It goes up 21 frames after the button, which is the attack's 18th frame.

HOW TO COMPARE IT, and this is the part that took the thinking. The popup writes the SAME OBJ
tiles the ENEMY DELETED banner does, and every chip comparison blanks those tiles every frame to
keep the banner out. Blanking them hides the popup too. The way through is not to blank at all
and instead to keep the banner from ever being asked for: `--hide-enemy` leaves the enemy alive
and immortal with its own tiles blanked, so nothing is ever deleted and no banner is ever
requested. `chip_compare.py` gained `--no-banner-zero` for that, and `--box x0,y0,x1,y1` to look
at one region rather than the navi's half. The scoreboard runs those five with both flags now, so
the popup is inside the normal comparison, and `regress.py`'s new `popup` check compares the whole
strip (`--box 24,34,100,52`) rather than the bottom half the standard window sees. All five chips:
0.0 px/frame across the popup's whole life.

TWO FIXTURE NOTES. The box stops at y=34 because the real ROM draws its HP box at x<46, y 28..33
and the sterile arena does not. And AreaGrab stops at 77 frames: the column it steals is a
BACKGROUND change, which `--disable-bg` hides on the real side and cannot hide on this one, so the
frames after the steal compare three drawn panels against nothing. The popup is over by then.

## 7an. Sixteen palette banks, spent on far fewer than sixteen palettes (2026-09-07)

THE FULL BATTLE CRASHED and no chip fixture could have caught it. `panicked at src/spr.rs:386:
sprite palette should fit in vram: PaletteFull`, 362 frames into the rollup build (no demo
feature, four enemies, buster fire) -- reproducible from one input script, invisible to every
`demo-*` fixture because each of those puts one or two objects on screen.

THE CAUSE. A GBA has sixteen object palette banks. agb's sprite loader already shares a bank
between objects that want the same colours, but the key it dedupes on is the ADDRESS of a
`&'static Palette16`, so it can only do it for a palette baked into the ROM. Every palette in
this port is read out of an exported sprite file at runtime and handed to
`PaletteVramSingle::try_allocate_new`, whose own doc comment says it "performs no
deduplication". So MegaMan, ProtoMan, Colonel, the Mettaur, the Gunner, each shot and each spark
took a bank of their own, several of them holding the SAME sixteen colours twice, and the
seventeenth request panicked.

THE FIX IS IN agb, not around it. `SpriteLoaderInner` gains a second map,
`dynamic_palettes: HashMap<Palette16, PaletteVramSingle>`, keyed on the colours themselves;
`Palette16` and `Rgb15` gain `PartialEq/Eq/Hash` so they can be that key;
`garbage_collect_palettes` prunes it the same way it prunes the other (drop every entry nothing
else holds, then retry), which keeps it bounded at about sixteen entries; and
`PaletteVramSingle::try_allocate_shared` is the public way in. `spr.rs` calls it in all four
places it used to call `try_allocate_new` -- the frame palette, the OAM-offset palette, the
white hit-flash and StepSwrd's red afterimage. `try_allocate_new` stays for a palette that must
own its bank because something will write over it.

Sharing cannot change a pixel: the colours are identical, only the bank index differs, and
nothing here depends on which bank an object lands in. Four thousand frames of the same fight
now run clean, and every fixture is unchanged.

AND THERE WAS A SECOND ONE, found by running the rollup under a DIFFERENT walk: `custom.rs:404,
cursor palette should fit in vram`, about 1650 frames in. `spr.rs` was not the only caller of
`try_allocate_new` -- `custom.rs` (twice, for the cursor and for the regular-chip mark, which the
real ROM draws out of the same bank 11), `hud.rs`, `emotion.rs` and `battle.rs`'s hand icon all
built their palettes at runtime too. All five now share.

WHAT THIS SAYS ABOUT THE HARNESS. `regress.py` checked nine things and none of them was "the game
runs". A fixture puts one chip on an empty arena; these crashes needed five actors and their
effects, and a chip window that only opens if the navi is still alive when the gauge fills. The
`rollup` check now runs THREE different walks of 2600 frames each, because one walk decides which
enemies the navi meets and how long it survives -- the two crashes came out of two different
walks, and one walk would have found only one of them.

AND THE REBUILD IS PARALLEL NOW. `tools/build_roms.sh` builds 58 ROMs; one after another that is
about a quarter of an hour, which is long enough that the site was routinely stale. They cannot
simply be backgrounded, because cargo locks its target directory and every job writes the same
`target/.../bn` that gbafix then reads. Each worker gets its own `CARGO_TARGET_DIR` under /tmp
instead, handed out round robin so a worker keeps its own incremental artifacts, with `JOBS`
defaulting to half the cores. 2m21s wall for 17m37s of CPU.

## 7w. The scoreboard, and two fixtures worth knowing (2026-09-07)

`tools/scoreboard.py` runs every chip comparison and prints each one's mean against its FLOOR --
the mean the ENEMY DELETED banner's single frame alone puts on a run of that length, 369/N. A
chip is exact when its mean equals its floor. Run it after any change that touches drawing, not
just the chip you were working on: the first run caught the chip-in-hand icon's palette being
allocated for every battle including the sterile arena that never draws it, which left SuprVulc's
volley short of object palette banks and panicking with "sprite palette should fit in vram". A
chip-at-a-time check had missed it because SuprVulc is the only chip long enough to run out.

43 OF 43 EXACT (2026-09-07, latest run, at a floor of zero -- 7am for the floor, 7ao for the
last two). Every chip in the list is at literal 0.0 px/frame. The arcs got there by having their
constants READ OUT OF THE RUNNING GAME (`tools/throw_dump.py`), which is strictly better than the
sweep that preceded it: see 7ao.

TWO FIXTURES, and it matters which:
- `demo-hudmatch` matches the capture's HUD STATE -- 60 HP, full gauge, Cannon in hand -- and
  puts the navi at column 3 with no enemy. It is for TILE comparisons, where the navi's column
  does not matter, and it deliberately never opens the chip window.
- `demo-field` matches the capture's FIELD state -- MegaMan at (2,2), a Mettaur at (5,2) -- which
  is what a whole-screen comparison WITH sprites needs.
- `demo-custmatch` matches the chip window's five offers and its pick.

- `demo-resultmatch` puts the RESULT window up at once with the capture's readout and its 60 HP,
  against /tmp/noenemy2.state (7x). `demo-cardname` is `demo-custmatch` with the cursor on a slot,
  which is the only way to see the preview card (7z).

## 7v. Elements this build was simply missing (2026-09-07)

Three of them turned up in one afternoon, all by looking at a live battle rather than at a chip:
the EMOTION WINDOW (7r), the CHIP IN HAND, and the backdrop's animation (7t). The lesson is that
a chip-by-chip comparison in the sterile arena cannot find anything the sterile arena strips.
Capture a plain battle from a save state, unpaused with `--script Start@10`, and look at it.

THE CHIP IN HAND is a 16x16 object over the navi carrying the front chip's own icon -- the same
art byte_8725894 gives the window's slots, which chips.bin already has. Its OAM entry is (59,52)
with the navi on the middle panel of its row: that panel's centre one left and fifty-six up. Only
its OBJECT palette was new, byte_872CFD4, which is NOT the window's icon bank (a background
palette, differing at two entries).
IT IS NOT DRAWN IN THE STERILE ARENA. The object belongs to the chip window CLOSING, not to the
hand's contents, and the real captures poke a chip straight into the hand slot; drawing one there
costs every chip comparison a flat 256 px. Same class of thing as the emotion window, which the
real ROM drops the moment the ENEMY DELETED banner shows.

## 7u. The chip select window is EXACT (2026-09-07)

0 px against the capture, sprites and all. The route there is the general one and worth copying.

IDENTIFY THE CAPTURE'S OWN STATE FROM ITS PIXELS. Each slot's four icon tiles came out of OBJ/BG
VRAM and were matched against all 411 chips' icons in byte_8725894 (id * 0x80): Vulcan1 D,
AirShot *, Sword S, MiniBomb B, Cannon A. The pick stack's icon matched Cannon too, so the fifth
slot is not empty -- it is PICKED. `demo-custmatch` then offers exactly those five with the
Cannon picked and the cursor on OK, and every difference left is art.

Four defects fell out:
- A PICKED SLOT KEEPS ITS CODE and loses only its icon.
- A SLOT'S CODE IS THE FOLDER ENTRY'S, not the chip's first code. A folder holds copies of a chip
  under different letters; `Offer` carries the entry's code now and the selectability rule uses
  it.
- THE CARD SHOWS A MESSAGE whenever the cursor is not on a previewable chip. "CHIP DATA
  TRANSMISSION / Sending chip data..." is a static 7x6 image at dword_87225B4 -- exactly the
  picture region, text and all -- with palette dword_87257F4. The blob continues with the
  window's other messages ("...DO DATA SHUFFLE!" is next).
- THE PICK STACK'S FRAME IS FOUR TILES: the top two rows have their own pair, the rest alternate
  the first two, the right column mirrored.

Earlier findings that also had to be right: eight slot cells and not ten, with the hidden pair
filled FLAT rather than with the empty icon in another bank; bank 12 as the dimmed icon palette
for chips that cannot join the picks; the regular-chip mark object; and the cursor bracket's
OBJECT palette, which is not the window's background bank.

## 7t. The backdrop is ANIMATED (2026-09-07)

CORRECTS 7m. The backdrop is not a still image that scrolls. Its TILE ART cycles: seven complete
sets of the layer's 37 tiles, eight frames each, a 56-frame loop -- the little magenta digits
inside the rings fading in and out -- while the map's 1024 entries, palette bank 0 and the scroll
all stand still.

HOW TO SEE IT AT ALL: dump BG1's CHAR data frame by frame. Dumping the map or the palette shows
nothing moving, and a whole-frame comparison at one moment is what let 7m call the layer exact.
Any HUD or background element that looks static in a screenshot deserves this test -- dump the
map, the tile art and the palette across frames and see which of the three moves. The CUSTOM
gauge (7r) turned out to be the map; this is the art.

All 7 x 37 tiles matched byte for byte, AT TILE ALIGNMENT, against the blob at dword_8617488 --
searching without the alignment constraint gives false hits inside runs of uniform bytes, which
is how four of them first came back "not in the blob". The asset now records seven rows of 37
blob indices, a 32x32 map of slot indices 0..36 (not indices into a collapsed 32-tile list: two
slots that share art in one step do not in another), and the palette. tools/backdrop_export.py
still needs only the submodule. The swap uses agb's replace_tile, which rewrites the pixels
behind a tile in place -- what the real ROM does, since its map never moves.

RESOLVED, and the two false alarms on the way are worth more than the result.

WHOLE-SCREEN TILE PARITY IS 0 px OF 38400 AGAIN, animation and all. It just needs a long enough
capture: the art loop is 56 frames and the scroll repeats every 128, so the two coincide only
every 896, and the CUSTOM gauge's flow adds its own 112. A hundred-frame search finds nothing and
reads as a regression. Search a thousand frames and pick the pair.

FALSE ALARM ONE: the analysis script expanded RGB555 to 8 bits as `v * 255 // 31`. The emulator
uses `v << 3 | v >> 2`. That is off by one on most values, so every exact comparison against a
rendered model failed and the backdrop looked structurally wrong when it was not -- 18% of
sampled pixels "mismatched" at the correct offset. Use the shift-or expansion.

FALSE ALARM TWO: comparing raw .rgb capture bytes compares the ALPHA byte too, and two frames
that render identically can differ there. Strip every fourth byte, or go through PIL's convert.

A Python renderer built from the map, tiles and palette reproduces either side exactly and will
solve a frame's (art step, scroll x, scroll y) by search -- the real capture's frame 48 is step 0
at (62, 31). Both sides keep y = x/2, so the scroll phases are NOT independent after all.

## 7s. LilBolr, and the digit palette that was never the game's (2026-09-07)

LILBOLR IS DOWN TO 34.6 px/frame from 333.6. Three things.

THE FIGURE UNDER THE BOILER is the summoned LilBoiler's own HP, not the chip's damage: it reads
40 for all three LilBolrs, whose powers are 100, 140 and 180. Drawn as a constant. Its two
digits span sixteen pixels from the projectile's own x, top three pixels below it.

FITTING AN ARC WHOSE SPRITE BOBS. The boiler's animation moves its centroid, so fitting a
parabola to the tracked centroid fights the animation and lands in the wrong place. Take this
build's own centroid MINUS its modelled parabola -- that difference is the bob, and it is
identical on both sides because the sprite is -- then fit parabola + bob against the real
centroid. Seven pixels of total error over thirty-nine frames is the floor of that model, and no
choice of launch, gravity or spawn subpixel beats it.

THE HP DIGITS WERE IN A MADE-UP PALETTE, flat white on near-black. hud.rs said so in a comment
and nothing had ever had a real number to compare against, because the sterile arena deletes the
enemy and no number is drawn. The boiler's 40 is the first. The game's palette is
`dword_86B7AC0` in data/dat38_60.s, the 32 bytes immediately BEFORE the battle text font, and
dumping OBJ palette bank 14 out of a live battle gives those sixteen words back word for word:
the fill is a soft white 0x7bfe and the outline a dark blue 0x28e6. This changes every number
the game draws -- enemy HP, damage figures, the chip card's power.
The general lesson: a stand-in that no measurement has ever touched is not a small thing. Look
for the fixture that would expose it.

## 7q. Per-pixel parity needs a MATCHING FIXTURE (2026-09-07)

Reporting a difference as "live state" is not a measurement. Build a fixture that matches the
capture's state instead, so any difference left is art.

`demo-hudmatch` is that fixture for the battle screen: the navi at 60 HP, a full gauge and a
Cannon in hand, which is what /tmp/pausedwithcannon.state holds. Against it the WHOLE BATTLE
SCREEN diffs to 0 px of 38400 with sprites off -- HUD 0, backdrop 0, field 0, chip name 0.

BUILDING IT IMMEDIATELY FOUND A BUG the state mismatch had hidden: the chip name was read with
`chips.get(id)`, indexing the chip table BY CHIP ID, but the table is in tools/chip_export.py's
own CHIPS order, where index 1 is HiCannon while chip id 1 is Cannon. Every chip name in the game
named the wrong chip, and it looked plausible enough to survive comparison against a capture that
held a different chip. The hand holds Chip values, so the name comes from those now.

FOR THE CHIP MENU the same fixture gets the header to 0 and the HP box to backdrop phase alone.
What is left there is genuinely state: the two builds offer different chips (the card's picture
alone is ~3000 px), and the real ROM draws EIGHT slot cells where this draws ten -- its lower row
shows three empty boxes, not five, so the count follows how many the deck can offer. Matching
that needs a fixture that offers the same chips; identifying them from their icons needs the
record stride in chips.bin, which is not 36 as the exporter's packing suggests.

## 7p. The bomb family, mapped; FlshBom started (2026-09-07)

Every NAMED chip in each implemented family, read straight out of ChipDataArr.s by attack_family
and attack_subfamily, so there is no more guessing about what is left:
- SWORD 0x13: Sword(s0) WideSwrd(s1) LongSwrd(s2) WideBlde(s3) LongBlde(s4) FireSwrd(s12)
  AquaSwrd(s13) ElecSwrd(s14) BambSwrd(s15) StepSwrd(s1, param1=1) Muramasa(s8). ALL ELEVEN ARE
  IMPLEMENTED -- the family is complete. WindRack, VarSwrd, NeoVari, MoonBld, MchnSwrd, ElemSwrd
  and AssnSwrd are sword-NAMED but families 0x3f, 0x53, 0x54, 0x40 and 0x49, not this one.
- CANNON 0x14: Cannon, HiCannon, M-Cannon. Complete.
- VULCAN 0x17: Vulcan1, Vulcan2, Vulcan3, SuprVulc. Complete.
- BOMB 0x12, the only one with room left: MiniBomb(s0) EnergBom(s1) MegEnBom(s1) BlkBomb(s6)
  LilBolr1/2/3(s3) BigBomb(s15) are done; FlshBom1/2/3(s14) is started; BugBomb(s7) GrasSeed(s13)
  IceSeed(s9) PoisSeed(s12) VDoll(s8) are not.

FLSHBOM1/2/3 share subfamily 0xe, so one implementation serves all three (powers 40, 70, 100).
Wired as a bomb variant it is at 138 px/frame. Its held ball is its OWN sprite, sprite_8391E40 in
data/dat38_33.s -- found by pulling the held ball's tiles out of OBJ VRAM and searching the data
blobs, since it is in no sprite file and its yellow is in none of the bomb sprite's thirteen
palettes. That sprite carries its own part offsets, sitting 22 right and 10 down of the bomb
sprite's, so the held object is drawn at the panel origin less that; with it the first five
frames are 51 px. Frames 5-8 are still 589: the held ball's second frame needs its own offset.

## 7o. LilBolr, identified and ready to build (2026-09-07)

LilBolr1/2/3 (98, 99, 100; powers 100, 140, 180) are bomb family, subfamily 3, which routes
through off_80EB6F8[3] = sub_80D7A96 rather than MiniBomb's sub_80C5DBC: a fixed target in front
of the navi rather than the targeted arc. They are now in the chip export.

Captured against the real ROM (`--cheat` the hand to 0x62, enemy immortal): the navi plays the
throw pose, a gold ball arcs up and off the top of the frame with damage numbers popping, and
then a WHITE SPRAY opens on the panels ahead and runs for the rest of the attack. The spray is
the new machinery -- everything before it is the throw this build already has.

ITS PARTS ARE BOTH IDENTIFIED, and neither needs new art of its own:
- THE BLAST is the SAME object MiniBomb's is. sprite_8399578 (data/dat38_33.s) is six frames,
  durations 2 then 4 -- a white flash, an orange blast, then smoke, 22 frames in all -- and its
  art matches the exported bomb_blast asset byte for byte. So the existing blast serves.
- THE THROWN OBJECT is the LilBoiler VIRUS: its tiles are in
  data/sprites/virusBattleSprite_824EAF4.spr. That is why it looks nothing like a bomb.
WHAT IS ACTUALLY NEW is the arc. Wired up as a plain bomb variant, LilBolr's throw pose matches
exactly (frames 0-8 are 0 px) and then the flight differs by 700-1050 px from frame 9 to 41
before returning to 0: the real ball arcs UP and off the top of the frame rather than across.
So the work is the arc and the blast's placement, not the artwork.
The blast covers x 125..204 on screen, about two panels wide, over y 50..128.

IMPLEMENTED to 352 px/frame, from about a thousand. The boiler draws from the virus sprite, the
blast is the shared one, and the arc has its own constants: LILBOLR_VX 0x2C7AE, LILBOLR_VZ
0x2999A, LILBOLR_GRAVITY 0x2800 (the bomb's). Track the kettle by its gold colours
((222,156,49), (173,107,8), (255,206,90)) to compare trajectories -- bounding boxes pick up the
navi and the damage popup and are useless here. On that measure the HORIZONTAL now matches
exactly, frame for frame: 76, 93, 109, 126, 142.
WHAT IS LEFT, and it is not the arc. Searching vz alone made things worse in both directions
(0x18F5C gave 422, 0x1C000 gave 381, against 0x2999A's 352), because the residual is not mostly
position. Two other things: the real kettle carries a FLAME and a purple ring on its lid that
animation 0 does not draw, worth 366 px on frame 19 where the diff is grey-blue and white rather
than gold; and the damage figure that rides beneath it is drawn by no chip here yet.
THAT FIGURE IS IDENTIFIED as an object, but NOT as a meaning. It is two 32x16 OBJECTS at (84,64)
and (116,64) on frame 19, tiles 888 and 896 -- the same OBJ number tiles the enemy HP counter
uses (880 upward, which BANNER_TILES already blanks) -- so it is the number machinery hud.rs
already has, drawn under the projectile and travelling with it, not a new sprite.
WHAT IT IS NOT is this chip's damage. It reads 40 where LilBolr1's attack_power is 100. Since the
thrown object is a VIRUS sprite, the likeliest reading is the summoned LilBoiler's own HP, which
would make this chip a summon rather than a throw -- but the boiler does explode into the shared
bomb blast, which a summon would not. Drawing the chip's power there scores 404 px/frame against
352 for leaving it out, so it stays out until the figure's meaning is settled. SETTLED: LilBolr1, 2 and 3, whose
attack powers are 100, 140 and 180, ALL show 40. A constant figure across the three is not
damage; taken with the thrown object being a virus sprite it is the summoned LilBoiler's own HP,
which viruses have fixed. SO THIS CHIP IS A SUMMON, not a throw, and the blast that already
matches is the boiler's own doing rather than a bomb going off. Modelling it as a bomb gets the
arc and the blast right by coincidence of shape; a faithful version needs a summoned actor with
40 HP that lands and then acts.
The kettle's flame is NOT missing: every one of the virus sprite's animations carries the flame
and the purple ring, and rendering them confirms it. The residual on frame 19 is grey-blue and
white because it is this number, not the lid. The vertical
is still 5-13 px high and drifting, which is worth revisiting only after the sprite is right.

The earlier note read: its sprite is sprite_8399578 (data/dat38_33.s). That took all three searches to find, which is
worth knowing: it is in none of the 97 plain .spr files and none of the 269 compressed ones, and
only turned up in the assembled data blobs. Its objects at one frame are a 32x32 body at (165,90)
with 8x32 pieces either side at (157,92) and (197,92), a 16x32 at (175,88) and 32x16 pieces below
at (169,108) and (165,122) -- so it is composed of several parts, not one sprite.

## 7n. How to investigate this ROM (2026-09-07)

Three habits earned their keep tonight and are worth following before reasoning about tables.

1. VERIFY A NULL RESULT BEFORE BELIEVING IT. `--dump` used to read memory before the frame loop
   ran, so every dump described the save state rather than the frame being looked at. Two dumps
   taken at different frames came back identical, which read as "the palettes never change" when
   it meant "nothing was read", and that went into a commit as a confident claim about an mGBA
   blending bug. When a measurement says identical, not found, or no difference, change something
   that MUST show up and confirm the measurement moves before concluding anything from absence.
2. TO IDENTIFY UNKNOWN ART, SEARCH FOR ITS BYTES. Take the tiles out of OBJ or BG VRAM at a
   chosen frame and search the assembled data files (and the 269 compressed blobs) for that exact
   sequence. This found BlkBomb's thrown sprite among 97 sprite files, EnergBom's animation, the
   HUD's fourth font variant, the CUSTOM gauge's tiles and the chip menu's stack frame. It is
   faster than tracing the tables and it is decisive. Beware only that blank and near-blank tiles
   collide, so match on a distinctive tile and prefer a multi-tile needle.
3. FOR SCROLLED OR ANIMATED CONTENT, COMPARE THE DATA, NOT THE PICTURE. Shifting and wrapping a
   screenshot to undo a scroll reported 2153 differing pixels on two backdrop layers that are
   byte-identical, because the screen is a 240 px window on a 256 px map. Compare tilemaps in
   VRAM instead. Pixels are for forming a hypothesis; the underlying data is for confirming it.

## 7m. Tile parity: the field and the backdrop (2026-09-07)

The capture harness can now isolate layers: `--disable-obj` turns the sprites off and leaves the
BG layers on, and `--only-bg <n>` leaves exactly one BG layer on and everything else off. With
the objects gone a whole-frame diff is a diff of the tilemaps, and one layer at a time says which
layer a difference is in. Both were what made the rest of this measurable.

LAYER ROLES, read off those captures and confirmed against BG0-3CNT (1c08, 1d03, 1e02, 1f09):
BG1 is the backdrop (screen block 29, char base 0, priority 3), BG2 the field (block 30, char
base 0, priority 2), BG3 the HUD and chip name (block 31, char base 2, priority 1). BG0 is empty
in battle. This build now matches that layering: the field moved from priority 3 to 2 with the
backdrop behind it at 3.

THE FIELD IS EXACT -- 0 px over the whole layer. It was short by one tilemap row: the real ROM
draws a front lip below the bottom panel row, five tiles repeating per column (0x28d, 0x28e,
0x28f, 0x28e, 0x28d) in that column's own side palette, 1 on the player's red half and 5 on the
enemy's blue one. That is the six pixels the field stopped short of at y 144..149. Its tiles were
already inside the exported tileset, which covers 498 tiles from TILE_BASE while the lip uses 653
to 655, so this was a tilemap row and no new art. field_export.py emits it as two variants after
the highlights, and Field::draw_lip paints one per column of the bottom row.

THE BACKDROP IS EXACT -- all 1024 cells of its tilemap carry identical tile art and identical
flip and palette bits. It was parked on two obstacles recorded in 7d: the tile blob's order is
not the order the game uploads to VRAM, and the 32x32 map is in no data blob because the game
builds it at runtime. Matching every tile of a live battle's BG1 byte for byte against the blob
resolved both at once -- all 37 distinct map tiles matched, collapsing to 32 blob tiles -- so
tools/backdrop_export.py records the map as indices into the blob and needs only the disassembly,
not the ROM. It scrolls one pixel left every two frames and one pixel up every four, kept in
quarter-pixels; the direction matters and was wrong at first, caught by comparing per-frame steps
rather than absolute positions.
DO NOT compare scrolled screenshots by shifting and wrapping them: the screen is a 240 px window
on a 256 px map, so a wrapped shift does not reconstruct the map and leaves a false residual
(2153 px on a pair that is in fact identical). Compare the tilemaps in VRAM instead.
The sterile arena leaves the backdrop out, for the same reason it draws a plain field: the real
captures strip their BG layers, so both sides must be MegaMan on black. With the backdrop drawn
there, every chip comparison jumped to 15767 px/frame.

BG3 IS NOW MOSTLY DRAWN. The HP box and the CUSTOM gauge are both in tiles, on a layer at
priority 1, and the HUD strip is down from 5409 px to 812 -- what is left there is live state,
not art: the demo sits at 80 HP with a part-filled gauge where the captured battle is at 60 with
a full one.
- THE HP BOX is a left cap, four digit slots filled right-aligned with a blank tile in the
  leading positions, and a right cap. Each digit is two tiles stacked and the set steps by two
  tiles per digit. Its art is a FOURTH variant of the font tools/font_export.py already reads
  three sets of, in the same file: dword_86E1638, whose first 640 bytes are the ten digits,
  verified tile for tile, with the box frame pieces immediately after. tools/hud_tiles_export.py
  emits it. The real ROM draws this in TILES; this build had it as sprites.
- THE GAUGE's art is in the same file under dword_86E489C, loaded at VRAM tile 0x222, so the
  asset index is a constant offset from the VRAM tile. Its layout is not what the tilemap first
  suggests: the top row is the CUSTOM LABEL, white text on a dark filler, and the bar is the
  single row below it -- end cap, six body cells, the four-cell L-or-R marker, six more body
  cells, mirrored end cap, spanning columns 6 to 23. The marker is cyan while the gauge fills and
  orange once it is full, which is the binary swap 7d's research found rather than a proportional
  readout. NOT VERIFIED: the bar's empty body cell, drawn here with the label row's filler. The
  gauge drains only when the custom window opens and that window replaces this whole layer, so a
  draining bar never shows on its own.
- PALETTE BANKS COLLIDE HERE. The gauge's bank is 9, which the results windows also take and
  were assigned after it, and the chip window borrows banks 9-15 while it is up. On the real ROM
  that is safe because the window covers this layer, so the gauge takes bank 9 last, gets it back
  when the window closes, and the layer stands down while the window is up.

THE CHIP NAME IS DRAWN, and with it the last text on the battle screen. The font is at
dword_86B7AE0 in data/dat38_60.s, one glyph per 64-byte label, each glyph two CONSECUTIVE tiles
top over bottom, and THE GLYPH INDEX IS THE GAME'S CHARACTER CODE, so constants/bn6-charmap.tbl
indexes it directly (0x0d renders C, 0x26 a, 0x33 n). tools/text_font_export.py emits codes
0..0x3f. Two traps: searching the blob for a glyph's bytes gives false matches on near-blank
tiles, and the symbol that first turns up in such a search is seven glyphs into the font.
The damage figure after the name is the HUD asset's SECOND digit set, orange, twelve pairs into
that blob, stepping one pair per digit like the white one.
ITS TRIGGER IS THE OPPOSITE of the obvious one: the real ROM names the chip ABOUT to be used,
not the one in flight. On a capture with A at frame 40, the name stands from frame 0 and clears
on frame 42, the frame the chip fires, so it follows the front of the hand.

A TRAP WORTH KNOWING: the backdrop takes BG palette bank 0, which is what the real ROM does and
what makes the backdrop match, but handing it bank 0 in the STERILE arena costs the barrier
bubble its colours -- Barrier goes from 0.8 px/frame to 766, with the bubble not drawn at all.
The field does not use bank 0, which is why taking it is safe in a full battle. So the assignment
is gated on not being sterile. This was found by bisecting the chip scoreboard across the tile
commits, which is worth doing after any change to palette banks: the chip captures and the tile
captures use different builds, and a change that is right for one can be silently wrong for the
other.

WHOLE-SCREEN TILE PARITY, sprites off: 7523 px, from 10134. By band: HUD strip 3610, backdrop
2808, field 147, name strip 958. None of it is missing art -- it is live state (the captured
battle is at 60 HP with a full gauge holding a Cannon; a demo is at 100 with an empty gauge and a
different chip) plus the backdrop's scroll phase, which depends on when the battle started.

FOR THE RECORD, the older note said the chip name was rows 18-19 of BG3, 1224 px. Its glyphs are a font in the ROM at
dword_86B7CA0 (data/dat38_60.s): each character is two tiles stacked, and the game copies glyphs
into VRAM to compose a name, which is why the two n's of "Cannon" are the same glyph at different
VRAM tiles. Searching the blob for a glyph's bytes is NOT a reliable way to index it -- blank and
near-blank tiles collide -- so this needs the game's character-to-glyph table. The damage number
beside the name is easier: it is a second digit set in the HP blob, starting at VRAM 0x1b8 with
the same two-tiles-per-digit step, so "40" is 0x1c0 then 0x1b8, and those pairs are already in
the exported asset.

FOR THE RECORD, the older note said BG3. With sprites off, the whole screen differs by 10134 px: 5409 in the HUD
strip (y 0..40), 1224 in the chip-name strip (y 150..160), 3373 in the backdrop band which is
scroll phase alone, and 128 across the field which is backdrop showing through the gaps between
panels at a different phase. BG3's map has content only in rows 0-1 and 18-19, 37 distinct tiles
in palettes 0, 9 and 13, char base 2 (0x6008000). Rows 0-1 are the HP box in columns 0-5 (frame
tiles 0x1b4-0x1b7, digit tiles around 0x1a0-0x1ad, each cell a two-row pair) and the CUSTOM gauge
from column 6 in palette 9. Rows 18-19 are the chip name. All of it holds live values, so it
needs a tile-based renderer rather than a static export -- exporting the map as captured would
hardcode this state's "60" and "Cannon40". That is the next piece of work.

## 7e. AreaGrab and per-panel ownership (2026-09-06)

field::Panels now carries `enemy_owned` per panel instead of the fixed 1-3 / 4-6 split:
`draw_panel` takes it (so a stolen panel is drawn in the other side's colours), `half(side,
row)` gives a side's live column range, and `other_half(side)` gives the panels a side may not
stand on -- folded into the `blocked` mask at the three movement sites, so the actor no longer
consults the static `field::half`. AreaGrab (a presentation chip, so the fight holds first)
calls `steal_column(occupied)`, which takes the enemy's front-most column a row at a time and
skips any panel someone stands on. Verified in a demo (demo-areagrab): three grabs move the
boundary 3/3 -> 4/2 -> 5/1 -> 6/0 except the Mettaur's own panel, which stays the enemy's.
Not pixel-compared: the effect is on the field layer, which the parity setup disables.

## 7f. Sibling chips (2026-09-06)

The families generalise: **Recov50** (9c demo-recov50 --rust-start 123) diffs to zero with no
code change beyond the amount table (byte_80EC870 = 10,30,50,80,120,150,200,300,1000, indexed
by chip id - Recov10), and Recov80/120 use the same path. **Vulcan2** (06) and **Vulcan3** (07)
scale by shot count: measured on the real ROM the muzzle flashes run every 5 frames from c5 and
each extra shot lengthens the attack by 11 frames (the gun is on screen 35, 46 and 57 frames for
Vulcan1/2/3), so the firing state is `20 + (shots-3)*11` and the gun's life `35 + (shots-3)*11`.
All four now diff to zero -- SuprVulc's ten shots included, whose firing state is 100 frames
and gun 112, measured the same way (its (firing, recovery) is (100, 10), so the gun's life is
just 2 + firing + recovery and no longer needs its own formula). NOTE: keep --frames inside the
attack, since the Rust demo's auto-fire starts the next use as soon as the navi is free while
the real capture presses A once. The last differing frame was not the flash but the NAVI: the real
was still in the firing pose (recoil + muzzle flash) where ours had switched to recovery, so the
firing state was ending early. Measured, the firing pose's last frame is c21/c35/c46 (the pose
starts at c2) and the gun lives 35/46/57 frames, giving (firing, recovery) = (20,13), (34,10),
(45,10) for 3/4/5 shots -- kept as a measured table in `vulcan_timing`, since the state
machine's ticks do not map to frames one-for-one.

## 7g. The elemental swords (2026-09-06)

FireSwrd (76), AquaSwrd (77), ElecSwrd (78) and BambSwrd (79) are family 0x13 subfamilies
0xc-0xf and all diff to zero. What they add over Sword/WideSwrd/LongSwrd:
- Hit shape: byte_80EBA18's first byte per subfamily is 4 for all of them, i.e. the column
  ahead, like WideSwrd; the arc animation (byte_80EBAD8) is 0x16, also WideSwrd's.
- The sword object's row comes from byte_80EBB64[subfamily] (asm31.s:109348): row 3
  (sprite_82EFE48) for the plain swords, rows 0x19/0x1a/0x1b for fire/aqua/elec
  (sprite_83279C0 / sprite_8329D28 / sprite_832C418), and row 0x1c for BambSwrd, which is
  sprite_82EFE48 again with palette 2.
- The ARC takes the element's colour: the strike ORs `(subfamily - 0xb) << 16` into the
  spawn's Param3 (asm31.s:109198-109206), which sub_80E0568 adds to the sprite's palette
  index -- 1 fire, 2 aqua, 3 elec, 4 bamboo. Exporting sprite_830F144 with `--palettes 4` and
  setting the player's palette add reproduces it exactly. Getting this wrong was the whole
  residual: the swords themselves were already pixel-perfect, only the arc was the default
  light blue.

## 7h. The bomb family and the gauge/HP research (2026-09-06)

**BigBomb (202)** and **BlkBomb (60)** are family 0x12 like MiniBomb. What differs:
- The HELD object's row is byte_80EB738's packed halfword per subfamily (asm31.s:108898):
  MiniBomb and BigBomb row 4, BlkBomb row 0x2d, which is the same bomb sprite with palette 4.
- The THROWN object's palette is byte_80C5BA0[Param1]'s fourth byte (asm31.s:29422), Param1
  being the chip's first attack parameter: row 0 -> palette 0 (MiniBomb), row 3 -> palette 3
  (BigBomb, whose parameter is 3) -- the red bomb. BigBomb's held bomb is red too.
- BigBomb's landing is NINE MiniBomb puffs, not a bigger one: the region byte is
  dword_80C5D7C[Param1] (asm31.s:29619) -- 1 for MiniBomb, 0xf for BigBomb -- and 0xf indexes
  the nine-offset list byte_8019951 (asm00_2.s:20987), the landing panel plus its eight
  neighbours, each getting the same effect row 0. (byte_80C5BA0's third byte is the flying
  bomb's hit modifier, not a blast size.) With that, BigBomb is at 22 px/frame mean, down from
  87: the 3x3 blast lines up -- same bounding box and same pixel count on both sides -- and
  what is left is one puff out of phase: the differing pixels are all blast oranges against
  blast oranges (real (239,181,33) where ours is (214,74,33)) in a 16x14 box at the window's
  right edge, i.e. the leftmost puff of the nine is a frame ahead or behind ours. Reversing the
  spawn order does not change it. 22 px/frame, 0.06% of the screen. Open.
- BlkBomb, after two wrong turns, is left arcing like MiniBomb (~256 px/frame). The trail:
  off_80EB6F8[6] = sub_80CD886 (asm31.s:45704), whose object takes sprite_831EA40 animation 0
  from byte_80CD8AC[Param1 * 8] (asm31.s:46200) and, on the reading of sub_80CDA1C /
  sub_80CDAD8, plants itself on a panel three ahead and ticks a 60-frame fuse. Implementing
  exactly that was WRONG on both counts: sprite_831EA40 renders as a numbered canister (a
  count bomb) and the real ROM plainly throws a dark brown ball along MiniBomb's arc, ground
  shadow and all -- so it does arc, and the sprite reading is off somewhere.
  sprite_load's arguments were checked and are as assumed (sprite.s:75-78: r1 list, r2 index),
  so the error is elsewhere -- possibly that subfamily 6 does not reach sub_80CD886 at all for
  the player. With the arc restored several frames diff to zero (c40 among them); what is left
  is the bomb's colour (its brown is in none of sprite_82F569C's twelve palettes) and the
  pose's last frames.

**The custom gauge (research, second pass, confirms the first):** the counter lives at
word_20352A0 (eStruct2035280+0x20), is cleared by ClearCustGauge (asm00_2.s:29826) and raised
0xd a frame by sub_801DFB8 from sub_800855E (asm00_1.s:11099). Its only readers are
sub_800A21C (a binary `cmp r0,#0x4000` ready check) and sub_8010B78 (AI chip-use bucketing).
**No routine turns the counter into a proportional fill.** The gauge cell is an 18x2 tile
region written by CopyBackgroundTiles from word_801ED6C (counting) and word_801EDB4 (ready),
with a three-frame sparkle picked from byte_86E1CD8 (data/dat38_85.s:1795) -- i.e. a binary
state plus an animation, not a bar that grows. Drawing it is background work, which is parked.

**The HP box** is OBJECTS, not a background: digits go to OBJ VRAM 0x06016600 (asm00_2.s:25957)
from three pre-coloured glyph sets (off_801D854/0x880/0x8AC -> dword_86E0AB8.., the same 8x16
cells this project already exports), and byte_203EB50 drives them per frame: on a change the
shown number walks toward the real HP by |delta|/8 + 2 a frame (sub_801C1D0/sub_801C1EA,
asm00_2.s:25916-25949) while a flash timer picks the alternate glyph set. That count-up/down
is worth having as a gameplay detail.

## 7i. HP numbers (2026-09-06)

The HP box is objects, not background (asm00_2.s:25957 DMAs the digits to OBJ VRAM), so it is
drawn: the player's number sits at the top left (x 44, y 12 -- measured; the box frame around
it is background art and is not drawn) and every number now lags the real value the way the
game's does. `hud::Counter` walks the shown number toward the actual by `|difference| / 8 + 2`
a frame and flashes while it catches up (sub_801C168 -> sub_801C1D0 / sub_801C1EA,
asm00_2.s:25853-25949); tools/font_export.py now exports all three pre-coloured digit sets
(dword_86E0AB8 / 86E0D38 / 86E0FB8, off_801D854/880/8AC) and `draw_number_in` picks one.

## 7j. Blade swords and the rest of the Recovs (2026-09-06)

WideBlde (74) and LongBlde (75) are sword subfamilies 3 and 4: the same sword object as the
plain swords, the column and two-panel shapes, and arc rows 0x19/0x1a -- which byte_80E0398
resolves to the arc's animations 0 and 1 in **palette 5** (asm31.s:85787), the white blade.
Both diff to zero. Recov150/200/300 need nothing but their ids (the amount table already had
them); Recov300 diffs to zero.

## 7k. Muramasa, and the arc's palette rows (2026-09-06)

Muramasa (85, sword subfamily 8) diffs to zero: LongSwrd's two-panel shape with the arc in
**animation 1, palette 6** -- byte_80EBAD8[8] = row 0x2d of byte_80E0398. Reading that table
past row 27 needs care: a pointer (off_80E0408 = unk_200150C) sits inline and occupies one
four-byte row, so a naive parse stops there and every later row comes out missing. Rows that
matter so far: 0x16/0x17/0x18 = arc animations 0/1/2 palette 0, 0x19/0x1a = animations 0/1
palette 5 (the blades), 0x25 = animation 3 palette 0 (sword subfamily 9, unused so far),
0x2d = animation 1 palette 6 (Muramasa).

## 7l. StepSwrd (partial, 2026-09-06)

StepSwrd (81) is sword subfamily 1 -- WideSwrd's column shape and arc -- plus a dash: its first
attack parameter is 1, which sends the family's state 0 through sub_8015B00 to reserve a panel
across the boundary and move the navi there (asm31.s:108790-108826). Implemented that way
(`Actor::warp_to`, and back on Recovering), and against the real ROM the DASH PANEL matches
exactly (body box x 123-157 on both) and every frame from the slash's start (c10) is identical.
Looking at the frames rather than the numbers settled it: at c0, c4 and c10 the NAVI IS
IDENTICAL -- pose, position, everything -- and so is the slash. The residual is entirely the
capture: the enemy is deleted for these runs, and because StepSwrd dashes the navi across the
boundary the deleted Mettaur's dissolving remnant (and the screen-wide red flash of its
"DELETED" sequence at c16+) now fall inside the x<140 window, where for every other chip they
sat outside it. So the earlier "the step's ten frames differ" reading was wrong -- what differed
was the enemy, not the navi.
Neither escape works: pressing A later (--a-frame) is refused, the game stops accepting chip use
after the deletion sequence; keeping the enemy alive (--keep-enemy) puts a live, moving Mettaur
in the half the navi dashes into and is worse. Both flags are in chip_compare.py for the next
attempt. StepSwrd is believed correct but is not cleanly measurable with this save state; a
state with no enemy at all, or one whose enemy is off the dash panel, would settle it.

### 7l (corrected twice, same day)

Most of the paragraph above is wrong and is kept only so the dead ends are not walked twice.
FIRST, A HARNESS BUG THAT POISONED THE MIDDLE OF THIS INVESTIGATION: `--dump` (and `--peek`) ran
straight after the save state loaded, BEFORE the frame loop, so every dump was a picture of the
save state and not of the frame being looked at. Two dumps taken at different frames came back
identical, which read as "nothing changed" when it meant "nothing was read". --dump now runs
after the last frame, so `<count> N` dumps memory as it stands once frame N-1 has been drawn.
Anything dumped before that fix should be re-taken. --peek still reads at load time.

What is actually true, measured per frame from the framebuffer:
- The navi's own body colour is on the enemy's front column for the attack's frames 0..23 and at
  home from frame 24. The dash is real and immediate. There is no deletion "flash": what looked
  like one is the afterimage below.
- HOME AFTERIMAGE: the navi's idle silhouette stands on the panel it stepped off, drawn two
  frames on and two off, on frames 1-2, 5-6, 9-10, 13-14 and 17-18. It is drawn with the navi's
  palette masked down to red -- OBJ palette RAM holds a whole bank that is the navi's palette
  entry for entry with green and blue zeroed. This is the GAME, not the capture. (An earlier note
  here called it an mGBA blend artifact; that was the --dump bug talking.)
  Implemented as `step_ghost` with `spr::Player::set_red_only`, and it lands exactly: those ten
  frames and everything else through frame 23 are 0 px.
- DESTINATION AFTERIMAGE: the panel the navi steps TO carries a second red copy, two on and two
  off on frames 8-9, 12-13, 16-17, 20-21, 24-25 and 28-29. It is a separate object, not the navi
  recoloured: on frames 12-13 and 16-17 the panel holds both a red silhouette and the navi's
  ordinary body colour at once. It outlives the step -- the navi is home from frame 24 and the
  red copy is still blinking there at 29. It TRAILS the navi by three frames and is refreshed
  only on the first frame of each blink pair, then held for the second: object for object out of
  OAM, the copy on frames 16 AND 17 has exactly the sizes and positions the navi's four sprites
  had on frame 13, and the copy on frame 12 those of frame 9. Implemented (`step_ghost2`, with a
  four-entry ring of the navi's sprite frames and `spr::Player::frozen_at`).
  It stops taking new frames once the navi goes home and holds the last pose it had on that
  panel: refreshing past the return puts the navi's HOME pose on the far panel and costs 1090 px
  on frames 32-33 instead of 68.
- THE SWORD FOLLOWS THE NAVI. The 16x16 object that appears over the HOME panel at (41,58) from
  frame 24 is the sword's blade tip, not a warp effect -- pulled out of OBJ VRAM with its palette
  and drawn, it is plainly the blade. So an attack object is positioned relative to the navi and
  moves with it, rather than staying where it spawned: when StepSwrd sends the navi home the
  sword goes too. Implemented in the Recovering branch, and it takes frames 24-27 from 152/168
  to 68/0.
- THE AFTERIMAGE COPIES THE SWORD TOO, but only while the sword is still over there. On frames
  20-21 the far panel's blade tip is drawn in the red bank ((24,0,0) and (231,0,0) where the live
  sword is teal and white); adding a red copy of the sword to the afterimage takes those from 206
  to 26 px. From frame 24, when the navi and its sword go home, the far panel's copy is the navi
  alone -- keeping the sword in it costs 173 px a frame instead of 68.
  The afterimage also keeps taking new frames after the return, but only from frames where the
  navi was still on the far panel, so the trail carries each frame's POSITION beside its sprite
  and is followed by position rather than cut off at the return.
- ITS RECOVERY IS A FRAME LONGER than the other swords'. On the attack's frame 29 the real navi
  is still in the recovery pose (917 non-black at home, 178 of them body colour) and idle on 30,
  where Sword, WideSwrd and Muramasa are idle on 29. STEP_SWORD is SWORD with recover+1, and it
  takes frame 29's home panel from 886 px to 84. Sword, WideSwrd and Muramasa are unchanged.
- StepSwrd now scores 23 px/frame over 40 frames, from 340, with 33 of the 40 at exactly 0.
- WHAT IS LEFT: frame 6 is the standing banner artifact (369, unavoidable). The far panel holds a
  flat 68 px on every blink frame from 24 on, which is a SWORD copy the real keeps there after the
  return and this does not draw -- drawing the frame this has costs 173 a frame instead, so the
  frame it should hold is still unknown. Frame 29's home panel keeps 84 px, one frame of pose in
  the hand-off from recovery to idle.

Capture modes, and what each costs:
- A state with no enemy is impossible: the game refuses a chip press once the deletion sequence
  has run. Proved on one continuous run with no save states involved -- A at frame 40 fires, A at
  120, 150, 200 and 260 all do nothing. States saved after the deletion inherit the refusal, and
  one saved at frame 300 is already in the victory fade. `--clean-state` is gone.
- `--hide-enemy` keeps the enemy alive and immortal and blanks its object tiles every frame
  (`--zero 0x60103E0:448`; objects 9, 10 and 14, palette 1, tiles 31..44, decoded from
  `--dump 0x7000000:1024`). Its HP counter comes from tiles the banner blanking already covers.
  It is the only way to capture a chip that needs a target, and it is expensive: the enemy gets
  hit, and the hit puts the navi into FULL SYNCHRO, which rewrites the navi's own palette bank in
  place -- bank 0 stops being the navi's colours. That is what made an earlier reading of "a
  third set of colours" look mysterious. Cannon scores 0 with the enemy deleted and 346 px/frame
  with it hidden. Use it only before the strike lands.
- Clearing the entity's visible flag does NOT work as a poke: the object header's Flags byte is at
  struct offset 0 with OBJECT_FLAG_VISIBLE = 0x02 (ObjectHeader.inc:6-9), the Mettaur's struct
  base is 0x0203AB60 (HP at +0x24 = the known 0x0203AB84; T1 battle objects, stride 0xD8, array
  eT1BattleObjects at 0x0203A9A0, ewram.s:2972, MegaMan at 0x0203A9B0), but cheats are written
  before runFrame and the game re-sets the bit every frame, so it has no effect at all.

## 7c. Scoreboard (2026-09-06, later): five chips at zero, and the timing rules

`tools/chip_compare.py <id> <feature> --frames 40` -> 0 px on every frame (c6 is always the
banner-tile artifact): Cannon (01 demo-cannon), Sword (47 demo-sword), WideSwrd (48
demo-wideswrd), AirShot (04 demo-airshot), Recov10 (9a demo-recovery --rust-start 123).
MiniBomb (36 demo-minibomb, flight in the default window and the landing with --xmax 240),
Vulcan1 (05 demo-vulcan), HiCannon (02 demo-hicannon), M-Cannon (03 demo-mcannon),
Recov50 (9c demo-recov50 --rust-start 123), Vulcan2 (06 demo-vulcan2), Vulcan3 (07 demo-vulcan3),
FireSwrd (4c), AquaSwrd (4d), ElecSwrd (4e), BambSwrd (4f), WideBlde (4a), LongBlde (4b),
Recov80 (9d demo-recov80 --rust-start 123), Recov120 (9e demo-recov120, same),
Recov150 (9f demo-recov150, same), Recov200 (a0 demo-recov200, same), Recov300 (a1 --rust-start 123), SuprVulc (08 demo-suprvulc --frames 113), Muramasa (55), LongSwrd (49 demo-longswrd),
EnergBom (37 demo-energbom --frames 45) and MegEnBom (38 demo-megenbom, same),
BlkBomb (3c demo-blkbomb --frames 45: 12.8 px/frame, 0 on all but three frames -- see 7h),
BigBomb (ca demo-bigbomb --frames 60, and 0 across the whole screen with --xmax 240 from c10 on:
its nine puffs overlap and the draw order was the entire difference -- read out of the real ROM's
OAM on a blast frame, they occupy OAM centre/left/right of the front row, then centre/right/left
of the middle row, then centre/right/left of the back row, lowest index on top), Recov30 (9b
demo-recov30 --rust-start 123), Barrier (b2 demo-barrier: nothing visible on either side for
the first 60 frames -- see below). The chips that "would not fire" when poked were being swapped
for the bug chip 0x185 by the hand validation (someChipHandValidationHappensHere_800B090,
asm00_1.s:17303 -> encryption_testPack_8006e84, asm00_1.s:7809: the library count
byte_20008A0[id] ^ 0x81 must equal its copy byte_2004C20[id]); chip_compare.py now pokes a count
of 1 and a copy of 0x80 for the chip (preserving the neighbouring byte of the halfword).
Invisibl (b1 demo-invisibl --frames 190 --rust-start 123) and Barrier (b2 demo-barrier, same
flags) are matched too, and so are Barr100 (b3 demo-barr100) and Barr200 (b4 demo-barr200) at
`--frames 120 --rust-start 123`: 0.9 px/frame, the same residual Barrier itself has. The three
are one chip -- family 0x15 subfamily 4, off_802CCB4[4] = sub_80E3B50 -- whose first attack
parameter indexes byte_8020B2C (data/dat01.s:189) for the bubble's HP: 1 -> 10, 5 -> 0x64,
7 -> 0xc8. The bubble is the same object in another colour, gold for Barr100 and pink for
Barr200, matched against sprite_832F8C8's thirteen palettes (3 and 6); the asset is now exported
with all of them.
EnergBom and MegEnBom are MiniBomb's family and throw (off_80EB6F8[1] = sub_80C5DBC, the same
function MiniBomb and BigBomb use), powers 40 and 60, on the same bomb sprite but its OTHER pair
of animations: held 2 and thrown 3 where MiniBomb uses 0 and 1, in the sprite's palette 5.
Animation 3 is a five-frame loop at four frames each -- the bomb tumbles in flight, where
MiniBomb's single thrown frame does not. All of that was found without reading a line of
disassembly, by pulling the real bomb's tiles straight out of OBJ VRAM at a chosen frame and
searching the sprite's graphics blobs for those exact bytes; the OAM dump says which object and
which tile, and the blob says which animation. That is the fastest way to identify an unknown
sprite and is worth reaching for first.
BLKBOMB'S THROWN SPRITE IS FOUND (the open item in 7h). It is not the bomb sprite in another
palette: it is byte_831FA84.spr, one animation of one frame in three parts -- a 32x8 ground
shadow and a 16x32 plus an 8x32 making a dark brown ball with a fuse -- and one palette. Found by
taking its tiles out of OBJ VRAM mid-flight and searching all 97 sprite files for those exact
bytes; only that one holds them. Its held bomb was already right (the bomb sprite's animation 0
in palette 4). Its flight is slower: the leading edge covers 70 px over the 27 frames where
MiniBomb's covers 74, so the flight is 42 frames rather than 40 (41 and 43 score 53 and 50
px/frame against 42's 12.8), with its own horizontal and launch speeds, BLKBOMB_VX 0x2C000 and
BLKBOMB_VZ 0x22051. Those were found by search against the real capture, not derived: vx has a
plateau over 0x2C000-0x2C200 at 10.6 px/frame with 0x2BF00 and 0x2C34B both worse, and vz is flat
over 0x22000-0x22200, so the residual is not vertical. What is left is 65 and 45 px on frames 31
and 37, where the bomb crosses the top edge of the diff window at y=40 and the two arcs differ by
about a pixel. Everything else is 0.
WHICH PALETTE AN OAM OFFSET COUNTS FROM IS PER OBJECT, and both halves are measured. HiCannon's
barrel sits in palette 1 and its silhouette frame, offset 4, shows the flat palette 4, ignoring
the shift. Barr100's bubble is Barrier's shifted by 3 and its later frames, offsets 1 and 2, show
the gold set's lighter shades 4 and 5. Forcing either rule on both breaks the other -- HiCannon
goes to 29 px/frame, Barr100 to 273 -- so `spr::Player::set_offsets_follow_shift` picks. Both are family-0x15 "presentation" chips (object_timefreezeBegin,
object_dimScreen, object_drawChipName, effect, undim; object.s:95-287): the battle is frozen
and the effect lands 128 frames after the press for Invisibl and 77 for Barrier -- measured, the
banner's own timing not traced; the screen dim is not drawn yet. Invisibl: FlashingInvisTimer
0x68 and the navi is not drawn while bit 1 of the timer is set (blindVisualHandledHere_8016934,
asm00_2.s:16787). Barrier: type-4 object 7 = sprite_832F8C8 animation 0 (a one-frame dot the
navi covers, then three frames of bubble, four times, looping; its later frames use the
sprite's lighter palettes 1 and 2 through OAM palette offsets), 2 px forward of the origin,
between the navi's shadow and body in OAM order, alive while the barrier has HP.
OAM palette offsets are indices into the sprite's own palette table counted from the frame's
palette (cannon barrel silhouette = its flat palette 4, Vulcan gun flash = its flat palette 1,
bubble = palettes 1/2); an offset past the palettes the asset carries falls back to the frame's
own, which reproduces the gun's second frame. The exporter keeps extra palettes with
--palettes N.
LongSwrd (0x49), HiCannon (0x02), M-Cannon (0x03) and Barrier (0xb2) do not fire when poked
into the real ROM's hand slot (a Sonnet pass found no static ChipData gate; unresolved --
try dumping AIData Unk_44 after the press, or the ChipLockoutTimer, or a release-edge press).

Timing rules that hold for all five (commit "One timing rule for sprites, poses and effects"):
- `spr::Player`: a newly set animation is drawn on its first frame that frame and its
  duration counts from the next (`fresh`). The actor ticks its sprite AFTER its state
  machine, so this holds whether the animation was set by `attack()` before the update or by
  the lead-in -> pose transition inside it.
- `Actor`: a pose (`Attacking`) and a lead-in (`WindingUp`) are on screen for every tick from
  their length down to 1; the exit is the frame after. The transition frame ticks the new
  pose at once (the game sets the animation and its counter in the same tick). `recover_anim:
  None` holds the pose through recovery; `Some(a)` plays `a` (the cannon's animation 15).
- `Battle.effects`: an effect with N frames is drawn for N frames including its spawn frame.
  Type-1 attack objects (barrel, sword) and type-4 effects (arc, heal) need no special case.
- The comparer aligns on the navi's body box, not the whole frame (the deleted Mettaur's
  remnant dissolves at x>=149; HUD objects blink).
Objects per chip: Cannon barrel sprite_82F39C0 anim 0 at (+16,-24); Sword object
sprite_82EFE48 anim 0 at the origin from the slash state's first frame (two lead-in frames),
arc sprite_830F144 anim 2/0/1 at the front panel -16 on pose frame 10; AirShot arm object
sprite_83138C4 anim 0 at (+18,-24), 21-frame pose, instant one-panel hit on frame 6; Recov
heal sprite_830D494 anim 0 at the origin, 14 frames; MiniBomb held bomb sprite_82F569C anim 0 at
the origin until the throw (pose frame 10 of animation 6 held 42 frames), thrown bomb anim 1 as
t3_0x8 with 16.16 physics (from +4/+0x30, vx 0x2e666, vz 0x20666 - 0x2800/frame, 0x28 frames;
the frame's first part is the shadow and stays on the ground; Y and Z truncated separately),
blast sprite_8399578 anim 0 (22 frames) at the landing panel; Vulcan1 arm gun sprite_83195F0
at (+23,-25) with its animation following the attack's states (0: two frames of the first
state, whose first frame is drawn flat cream -- OAM palette offset 1; 1: the 5-frame firing
loop with muzzle flashes from the firing state's first frame; 2: held from the last state),
navi animation 10 for 2, 13 for 20 (it loops every 5 frames on its own), 10 for 13; the three
shots (t3_0x12, every 0xa ticks from the firing state's first frame) load no sprite.
OAM palette offsets measured: 1 = flat (247,239,222), 2 = the sprite's own colours, 4 = flat
(239,255,239).

## 7b. DONE 2026-09-06: the Sword (chip 0x47) is frame-for-frame identical

`tools/chip_compare.py 47 demo-sword --frames 40`: 0 pixels on every frame from the press to
the idle (c6 is the banner-tile artifact, as for the cannon). The comparer aligns on the navi's
BODY box on both sides (the whole-frame "first change" was the deleted Mettaur's dissolving
remnant). What the real ROM does (c = frames from the press's effect, real f43):
- States (sub_80EB776): state 0 and 1 take one frame each -> `windup: Some((0, 2))`; the slash
  state (sub_80EB862) begins at c2: animation 5 (gfx5 x8, gfx6 x2, gfx7 x2, gfx8 held), timer
  0x15, the hit and the arc on the frame it reads 0xc = pose frame 10 (c11); pose on screen 27
  frames (`frames: 0x15 + 2`, `recover: 5` with the pose held: `recover_anim: None`), idle c29.
- The sword object: t1_0x5 (byte_80B8BD4 row 3 = list 0xC index 0 -> **sprite_82EFE48**,
  animation 0: an 8x8 spark above the head for 8 frames, then the blade through the swing
  (frames of 2) and the 16x16 tip held), spawned in the slash state's first frame and DRAWN
  from that frame, riding the navi origin with no arm offset, gone with the attack's exit.
  (Earlier reading "sprite_82F6ECC" was a 5-byte-row indexing slip; 82F6ECC is the hilt-by-navi
  sprite. The blue hilt seen on MegaMan's arm is his own gfx6 art.) Confirmed by OAM dumps at
  f48/f55/f65: the object's parts land exactly where animation 0's OAM offsets put them.
- The arc: type-4 effect (row byte_80EBAD8[sf]=0x18 of byte_80E0398 = list 0xC index 0x14 ->
  **sprite_830F144**, animation 2 for Sword, 0 WideSwrd, 1 LongSwrd), at the front panel's
  coordinates 0x10 up (panel_centre(3,2) - (0,16) exactly), drawn OVER the sword object, first
  frame on screen for its full duration (a strike-spawned effect must not tick on its spawn
  frame: `effects_before_strike` in battle.rs).
- Actor: an attack with a lead-in now ticks its pose on the transition frame (the game sets
  the animation and starts the counter in the same tick), and `recover_anim: None` holds the
  pose; the cannon still diffs to zero after these changes (re-checked).
- Palette bank 1 in the real OAM = the teal sword palette, bank 2 = the light-blue arc.
- Still unresolved: HiCannon/M-Cannon/Barrier do not fire when poked into the hand.

## 7. Where the Cannon comparison stood before that (superseded)

At the intended same frame (real f72 vs Rust f126, both barrel-peak, aligned (0,-2)) the
diffmask is **~9.5% differing**. The background is already **solid green** (identical). The red
regions are:
1. **The MegaMan + barrel sprite pixels** — the dominant residual.
2. The **Mettaur** (real enemy, kept immortal → no banner → still on screen).
3. The **HP number text** (Rust shows "100", real's HP differs).
4. A small **HUD fragment** top-left on the real.

### CORRECTION (2026-09-06): the "lit" palette is Full Synchro, not the Cannon

Re-checked with palette dumps and colour timelines (`--dump 0x05000200:512:...`, note the
byte count is decimal): OBJ bank 0 (MegaMan) is rewritten to a brighter palette from the
frame the shot lands on the *immortal* Mettaur (f63 with A@40) and it **stays lit for the
rest of the capture**; without firing it never changes; and with the enemy **deleted**
(`--cheat 0x0203ab84:0 --cheat 0x0203ab86:0`, sterile patch keeping the fight live) MegaMan
stays dark through the whole cannon. The immortal Mettaur keeps attacking, so every shot is
a counter hit, which puts MegaMan in Full Synchro — the brightened palette. So do NOT
brighten the navi during the Cannon pose; use the enemy-deleted capture as the reference
(`/tmp/fire_nomet`: pose starts f50, barrel f51–72, idle again f73). The section below is
kept for the record but its conclusion is superseded.

### The sprite colour difference — earlier hypothesis (superseded, see above)
The real MegaMan **changes palette between idle and cannon-fire**:
- **Idle (real f45, no cannon):** dark body blue `(8,57,123)`. **My Rust idle is exactly this**
  → my Rust idle renders correctly.
- **Lit (real f66-80, during/after the cannon fires):** bright body blue `(33,74,132)`,
  `(49,82,181)`, `(41,66,115)`, `(82,239,255)`.

So the real game **lights the navi up (switches to a bright "lit" palette) when charging/firing
the cannon** — a `sprite_setPalette` switch (asm31.s:69 etc.). My Rust stays on the dark idle
palette during the cannon pose, which is exactly the shade difference in the diff.

**The fix (open):** brighten MegaMan (apply the lit palette) during the `CANNON` pose for
`CANNON_FRAMES`. The bright palette colours are extracted above. The mechanism in the game is a
palette swap on the firing navi; implementing it in agb is a palette-swap during the pose.

### Other open items
- **Remove the "ENEMY DELETED" banner** (OBJ text tied to the enemy-deletion event) so it doesn't
  pollute the diff — or pick a capture where it's cleared.
- **Match the exact cannon pose frame timings** (the Rust auto-fires continuously; the barrel+
  orb+charge phase must be frame-for-frame with the real).
- The field-strip via `--disable-bg` is the enabler; the sub-pixel sprite placement and the
  palette brighten are the last real fidelity gaps to a solid diff.

---

## 8. Chip ids for the battle-hand poke (`capture_real_chip.sh`)

`tools/capture_real_chip.sh <chipid_hex> <outdir> [count]` loads the sterile-patched ROM + save
state, pokes the hand chip at `0x20349c2`, unpauses and fires. Chip ids (battle-hand):
Cannon=0x01, HiCannon=0x02, AirShot=0x04, Vulcan=0x05, MiniBomb=0x36, Sword=0x47,
WideSword=0x48, LongSword=0x49, Recov10=0x9a, Recov30=0x9b, Invisibl=0xb1, Barrier=0xb2,
AreaGrab=0xa3. (These match the Rust constants: CHIP_SWORD=71, CHIP_CANNON=1, etc.)

---

## 9. Website log

- `tools/serve.py` serves `web/` on port 8123 (LAN `http://192.168.1.101:8123/`), `no-store`.
- `/log.html` — reverse-chronological screenshot/anim log, fetches `web/log/log.json`.
- `tools/log_entry.py <img> <caption> --tag X --out DIR` copies the image into
  `web/log/DIR/<ts>-<name>.<ext>` and appends to `log.json`. It preserves the source extension,
  so GIFs are logged as `.gif` and the `<img>` tag plays them.
- `/gifs.html` — capture gallery via `web/captures/manifest.json`.

---

## 10. Repos and hygiene

- Main Rust repo: `~/Code/bn` (agb, target `thumbv4t-none-eabi`). `git add`/`commit` per
  meaningful change.
- `reference/bn6f` is a git **submodule** of the bn6f decomp. It builds an **identical ROM**, so
  contributions must be comment/symbol/docs only (no code changes, or `make` errors).
  Made: documented `battle_isBattleOver` win/lose flags (asm00_1.s:15005) and the hand-chip
  layout (asm00_2.s:2657). Both comment-only.
- The real ROM and save states are **gitignored** (copyrighted). Never commit them.

---

## 11. Quick reference for the next operator

```sh
# Build the harness
gcc tools/mgba_capture.c -o /tmp/mgba_capture -I/usr/include -lmgba -lm

# Patch the ROM so the battle never concludes -> sterile ROM
python3 tools/patch_sterile.py /tmp/bn6f_real.gba /tmp/bn6f_sterile.gba

# Capture a real cannon in the sterile arena, field stripped, enemy deleted, no banner-ish
/tmp/mgba_capture /tmp/bn6f_sterile.gba /tmp/cap 120 \
  --loadstate /tmp/pausedwithcannon.state \
  --cheat 0x0203ab84:0xffff --cheat 0x0203ab86:0xffff --disable-bg \
  --script "Start@10,A@40,A@70"

# Build + capture the Rust version
cargo build --release --features "demo-cannon,demo-sterile,demo-auto"
python3 tools/gbafix.py target/thumbv4t-none-eabi/release/bn /tmp/rust.gba
tools/mgba_capture.sh /tmp/rust.gba /tmp/rust_out 200 --no-decode

# Diff-mark two intended-same frames
python3 tools/diffmask.py /tmp/cap/frame.00072.rgb /tmp/rust_out/frame.00126.rgb /tmp/dm.png --align 0,-2
```

The single biggest things to remember: (1) the field can only be stripped by disabling the
renderer layer (`--disable-bg`), because the game reloads DISPCNT/BGPAL/OAM every frame; (2)
~~the real MegaMan lights up during the cannon fire~~ -- STALE, and checked: the real navi's
colours do not change through a cannon shot (counted frame by frame over the whole pose, the same
blues throughout), and all three cannons compare at 0.0 px, so whatever that early note saw was
the barrel's own charge glow and not the navi. (3) the
`demo-sterile` branch must come before `demo-cannon` or MegaMan lands on the wrong column.
