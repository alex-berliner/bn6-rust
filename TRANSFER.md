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
All three now diff to zero. The last differing frame was not the flash but the NAVI: the real
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
  what is left is a small colour/edge residual in its last frames (135-230 px, at the window's
  right edge). Reversing the nine-panel spawn order does not change it. Open.
- BlkBomb is a different object: off_80EB6F8[6] = sub_80CD886 (asm31.s:45704), not
  sub_80C5DBC. It spawns a type-3 family 0x4a object three panels ahead with NO arc: it
  materialises on the panel, plants itself, reserves it and ticks a 60-frame fuse
  (sub_80CDA1C, sub_80CDAD8) with sound 0xc1. That behaviour is implemented. Its ART is NOT:
  the object's `sprite_load(0x80, 0xc, 0x23)` appeared to name sprite_831EA40, but rendering
  that sprite's animations shows a numbered canister (a count bomb), not the dark brown bomb
  the real ROM draws, and the brown is in none of sprite_82F569C's twelve palettes either. So
  the sprite is still unknown and the held bomb's grey palette stands in; BlkBomb sits at
  ~265 px/frame. Open: resolve effect list 0xC index 0x23 properly (check whether
  sprite_load's r2 is an index into a different list for type-3 objects).

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

## 7c. Scoreboard (2026-09-06, later): five chips at zero, and the timing rules

`tools/chip_compare.py <id> <feature> --frames 40` -> 0 px on every frame (c6 is always the
banner-tile artifact): Cannon (01 demo-cannon), Sword (47 demo-sword), WideSwrd (48
demo-wideswrd), AirShot (04 demo-airshot), Recov10 (9a demo-recovery --rust-start 123).
MiniBomb (36 demo-minibomb, flight in the default window and the landing with --xmax 240),
Vulcan1 (05 demo-vulcan), HiCannon (02 demo-hicannon), M-Cannon (03 demo-mcannon),
Recov50 (9c demo-recov50 --rust-start 123), Vulcan2 (06 demo-vulcan2), Vulcan3 (07 demo-vulcan3),
FireSwrd (4c), AquaSwrd (4d), ElecSwrd (4e), BambSwrd (4f), WideBlde (4a), LongBlde (4b),
Recov300 (a1 --rust-start 123), LongSwrd (49 demo-longswrd), Recov30 (9b
demo-recov30 --rust-start 123), Barrier (b2 demo-barrier: nothing visible on either side for
the first 60 frames -- see below). The chips that "would not fire" when poked were being swapped
for the bug chip 0x185 by the hand validation (someChipHandValidationHappensHere_800B090,
asm00_1.s:17303 -> encryption_testPack_8006e84, asm00_1.s:7809: the library count
byte_20008A0[id] ^ 0x81 must equal its copy byte_2004C20[id]); chip_compare.py now pokes a count
of 1 and a copy of 0x80 for the chip (preserving the neighbouring byte of the halfword).
Invisibl (b1 demo-invisibl --frames 190 --rust-start 123) and Barrier (b2 demo-barrier, same
flags) are matched too. Both are family-0x15 "presentation" chips (object_timefreezeBegin,
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
the real MegaMan **lights up during the cannon fire**, which is the sprite-colour gap; (3) the
`demo-sterile` branch must come before `demo-cannon` or MegaMan lands on the wrong column.
