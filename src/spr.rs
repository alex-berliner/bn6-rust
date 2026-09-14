//! Runtime reader and animation player for exported bn6f sprite assets.
//!
//! The binary layout is produced by `tools/spr_export.py`; see that file for
//! the format. Multi-byte fields are read byte-wise because the asset is
//! embedded with `include_bytes!` and ARM7TDMI faults on unaligned word loads.
//!
//! `Player` is a port of the ROM animation bytecode player, steps 1-4 of
//! docs/coverage/plan-interpreters.md §1.4: the bind path
//! (`_sprite_loadAnimationData`, reference/bn6f/asm/asm38.s:1667-1721,
//! normal and `Unk_03 & 0x80` alt arms), the tick with its `Unk_05` output
//! (`_sprite_update`, reference/bn6f/asm/asm38.s:1722-1793, both stream
//! arms), the `sprite_setAnimation` / `CurAnim` -> `Unk_00` write path
//! (reference/bn6f/asm/sprite.s:1120-1137), and the `object_updateSprite`
//! gate with its `CurAnim` / `CurAnimCopy` rebind protocol plus the
//! timestop / `sub_801BC24` / `UpdateBattleObjectSprite` variants
//! (reference/bn6f/asm/asm00_2.s:25045-25190). The BNSP asset carries the same
//! tables flattened at export time: one command stream per animation, each
//! command a (frame-select, duration, flags) triple. The exporter
//! pre-resolved the frame-select (`cmd[0]`, which the ROM scales by 4 to
//! index the pointer table at `[Unk_1c+0xC]`, asm38.s:1779-1788) into the
//! frame's own (gfx, pal, OAM range); `duration` is the ROM command byte 1
//! (loaded into `Unk_01` by the bind, decremented by the tick at
//! asm38.s:1725-1729) and `flags` the ROM command byte 2 (loaded into
//! `Unk_02`, tested for end-of-stream at asm38.s:1737-1738 and loop at
//! asm38.s:1770). `Unk_05` (emitted by the bind at asm38.s:1717 and by the
//! tick at asm38.s:1790) is the selected OAM list's first entry byte 4
//! shifted right 4 -- that entry's palette bank, which `sub_8002818` adds
//! to the base palette when drawing the frame
//! (reference/bn6f/asm/sprite.s:254-302).

use agb::display::object::{DynamicSprite16, PaletteVramSingle, Size, SpriteVram};
use agb::display::{Palette16, Rgb15};
use alloc::vec::Vec;

const MAGIC: &[u8; 4] = b"BNSP";

#[derive(Clone, Copy)]
pub struct Assets {
    data: &'static [u8],
    gfx: usize,
    pal: usize,
    anim: usize,
    frame: usize,
    oam: usize,
}

pub struct Frame {
    pub gfx: u16,
    pub pal: u16,
    pub oam_first: u16,
    pub oam_count: u16,
    pub duration: u8,
    /// 0x80 marks the last frame, 0x40 that the animation restarts after it.
    /// Most animations are one-shot and are re-triggered by game logic.
    pub flags: u8,
}

pub struct Oam {
    pub tile: u16,
    pub x: i8,
    pub y: i8,
    pub size: Size,
    pub hflip: bool,
    pub vflip: bool,
    /// Bits 4-7 of the OAM record's flags: a palette bank offset added to the
    /// sprite's own. Only seen on the cannon barrel's silhouette frame
    /// (sprite_82F39C0 animation 0 frame 1, offset 4), which the real ROM
    /// draws in a flat light colour; see `Player::load_frame`.
    pub pal_offset: u8,
}

impl Assets {
    pub fn new(data: &'static [u8]) -> Self {
        assert_eq!(&data[0..4], MAGIC, "not a BNSP asset");
        let at = |o: usize| u32::from_le_bytes(data[o..o + 4].try_into().unwrap()) as usize;
        Self {
            data,
            gfx: at(0x08),
            pal: at(0x0c),
            anim: at(0x10),
            frame: at(0x14),
            oam: at(0x18),
        }
    }

    fn u16_at(&self, o: usize) -> u16 {
        u16::from_le_bytes(self.data[o..o + 2].try_into().unwrap())
    }

    fn u32_at(&self, o: usize) -> u32 {
        u32::from_le_bytes(self.data[o..o + 4].try_into().unwrap())
    }

    /// `(first frame index, frame count)` for an animation.
    pub fn anim(&self, i: usize) -> (usize, usize) {
        let o = self.anim + 4 + i * 4;
        (self.u16_at(o) as usize, self.u16_at(o + 2) as usize)
    }

    pub fn frame(&self, i: usize) -> Frame {
        let o = self.frame + 4 + i * 10;
        Frame {
            gfx: self.u16_at(o),
            pal: self.u16_at(o + 2),
            oam_first: self.u16_at(o + 4),
            oam_count: self.u16_at(o + 6),
            duration: self.data[o + 8],
            flags: self.data[o + 9],
        }
    }

    pub fn oam(&self, i: usize) -> Oam {
        let o = self.oam + 4 + i * 6;
        let flags = self.data[o + 5];
        Oam {
            tile: self.u16_at(o),
            x: self.data[o + 2] as i8,
            y: self.data[o + 3] as i8,
            size: size_from_bits(self.data[o + 4]),
            hflip: flags & 1 != 0,
            vflip: flags & 2 != 0,
            pal_offset: flags >> 4,
        }
    }

    pub fn gfx(&self, i: usize) -> &'static [u8] {
        let o = self.gfx + 4 + i * 8;
        let start = self.u32_at(o) as usize;
        let len = self.u32_at(o + 4) as usize;
        &self.data[start..start + len]
    }

    pub fn palette_count(&self) -> usize {
        self.u32_at(self.pal) as usize
    }

    pub fn palette(&self, i: usize) -> Palette16 {
        let o = self.pal + 4 + i * 32;
        let mut colours = [Rgb15::new(0); 16];
        for (c, slot) in colours.iter_mut().enumerate() {
            *slot = Rgb15::new(self.u16_at(o + c * 2));
        }
        Palette16::new(colours)
    }
}

/// agb's `Size` discriminant is `shape << 2 | size`, matching the bn6f encoding.
fn size_from_bits(bits: u8) -> Size {
    match bits {
        0b00_00 => Size::S8x8,
        0b00_01 => Size::S16x16,
        0b00_10 => Size::S32x32,
        0b00_11 => Size::S64x64,
        0b01_00 => Size::S16x8,
        0b01_01 => Size::S32x8,
        0b01_10 => Size::S32x16,
        0b01_11 => Size::S64x32,
        0b10_00 => Size::S8x16,
        0b10_01 => Size::S8x32,
        0b10_10 => Size::S16x32,
        0b10_11 => Size::S32x64,
        _ => Size::S8x8,
    }
}

/// One hardware object making up a composed frame.
pub struct Part {
    pub sprite: SpriteVram,
    pub x: i32,
    pub y: i32,
    /// Pixel width; the caller mirrors offsets about the actor origin, which
    /// needs the part's own extent, not just its offset.
    pub width: i32,
    pub hflip: bool,
    pub vflip: bool,
}

/// Plays one animation, rebuilding VRAM sprites only when the frame changes.
/// The colour a forced-white sprite is drawn in. NOT 0x7fff: that renders
/// (255,255,255) and the real ROM shows that colour NOWHERE -- three
/// captures, 476 frames between them, including the Cannon's and the Sword's
/// flashes, contain not one pure-white pixel. Every white in the game is
/// (247,255,255), which is 0x7ffe.
/// NOT VERIFIED directly: the one flash available to compare is the navi
/// being hit, and the Mettaur's wave covers him whenever that happens.
const WHITE: u16 = 0x7ffe; // provenance: peeked -- measured across three captures/476 frames (see the doc comment above); the exact flash use-case itself is flagged NOT VERIFIED there

/// End-of-stream bit of a command's flags byte (ROM command byte 2,
/// `Unk_02`): `_sprite_update` tests it at asm38.s:1737-1738 and, when set,
/// either loops or holds the last frame instead of advancing to the next
/// command. Every shipped asset sets it exactly on each animation's last
/// frame (scanned all assets/*.bin: no mid-stream use, no missing last).
const CMD_END: u8 = 0x80; // provenance: derived -- `_sprite_update`'s `tst r0, r2` with r2 = 0x80, reference/bn6f/asm/asm38.s:1737-1738
/// Loop bit: with `CMD_END` set, the stream restarts through
/// `_sprite_loadAnimationData` (asm38.s:1770-1776) instead of holding.
const CMD_LOOP: u8 = 0x40; // provenance: derived -- `_sprite_update`'s `tst r0, r2` with r2 = 0x40, reference/bn6f/asm/asm38.s:1770
/// Bit 7 of the sprite flags (`Unk_03`): selects the alternate command
/// stream. Both cores test it the same way (`ldrb Unk_03; and 0x80; bne`):
/// the bind at asm38.s:1668-1672, the tick at asm38.s:1730-1733.
const ALT_STREAM_BIT: u8 = 0x80; // provenance: derived -- the bind's stream-select test, reference/bn6f/asm/asm38.s:1668-1672
/// Command durations are 1-based on both sides: the exporter already writes
/// `f.duration or 1` (tools/spr_export.py:69), so the max only guards
/// hand-built assets.
const MIN_DURATION: u8 = 1; // provenance: derived -- tools/spr_export.py:69 writes `f.duration or 1`
/// `OBJECT_FLAG_ACTIVE`: `object_updateSprite` returns early unless the
/// object's header flags carry it (asm00_2.s:25050-25053), and
/// `UpdateBattleObjectSprite` skips the sprite when it is clear
/// (asm00_2.s:25147-25151).
const FLAG_ACTIVE: u8 = 0x01; // provenance: derived -- OBJECT_FLAG_ACTIVE, reference/bn6f/include/structs/ObjectHeader.inc:8
/// `OBJECT_FLAG_STOP_SPRITE_UPDATE`: checked next by both gates
/// (asm00_2.s:25054-25057 and :25152-25156).
const FLAG_STOP_SPRITE_UPDATE: u8 = 0x08; // provenance: derived -- OBJECT_FLAG_STOP_SPRITE_UPDATE, reference/bn6f/include/structs/ObjectHeader.inc:11
/// `OBJECT_FLAG_UPDATE_DURING_TIMESTOP`: when set, the timestop gate is
/// skipped (asm00_2.s:25058-25066 and :25157-25166).
const FLAG_UPDATE_DURING_TIMESTOP: u8 = 0x10; // provenance: derived -- OBJECT_FLAG_UPDATE_DURING_TIMESTOP, reference/bn6f/include/structs/ObjectHeader.inc:12

/// Gate inputs for `update_battle_object_sprite`: the BattleObject header
/// flags plus the battle state the `UpdateBattleObjectSprite` dispatch
/// reads (asm00_2.s:25144-25169). `prevent_anim` folds the two-part check
/// (CollisionDataPtr non-null AND `PreventAnim` set); the flags byte passes
/// its bits straight through.
#[derive(Clone, Copy)]
pub struct SpriteGate {
    /// The object's header flags byte (ACTIVE / STOP_SPRITE_UPDATE /
    /// UPDATE_DURING_TIMESTOP in the low nibble).
    pub flags: u8,
    /// `battle_isTimeStop()`.
    pub timestop: bool,
    /// Collision-gated anim hold (CollisionDataPtr + PreventAnim).
    pub prevent_anim: bool,
}

impl SpriteGate {
    /// The gate our battle objects always present: active, never
    /// STOP_SPRITE_UPDATE, no timestop on our rows, no collision-gated anim
    /// holds -- so the gate always reaches the rebind-then-tick core. The
    /// value below is ACTIVE (`flags`) with every skip condition clear.
    pub fn battle_object() -> Self {
        Self {
            flags: FLAG_ACTIVE,
            timestop: false,
            prevent_anim: false,
        }
    }
}

pub struct Player {
    assets: Assets,
    /// `Unk_00`: the bound animation index, written by `sprite_setAnimation`
    /// (reference/bn6f/asm/sprite.s:1130) and consumed by the bind.
    anim: usize,
    /// Flattened `Unk_20`: index of the current command in the animation's
    /// stream. The ROM steps it by one 3-byte command (`add r1, #3`,
    /// asm38.s:1740); ours steps by one flattened frame.
    frame_in_anim: usize,
    /// `Unk_01`: remaining ticks on the current command. The bind loads it
    /// from command byte 1 (`_sprite_loadAnimationData`, asm38.s:1667-1719);
    /// the tick decrements it and consumes commands while it goes negative
    /// (asm38.s:1725-1729).
    countdown: u8,
    /// `Unk_02`: the current command's flags byte (command byte 2).
    cmd_flags: u8,
    /// `Unk_03`: sprite flags (see `ALT_STREAM_BIT`). `sprite_load` stores
    /// the sprite category here (reference/bn6f/asm/sprite.s:86) and
    /// `sprite_initialize` clears it (sprite.s:101); nothing in src/ sets
    /// any bit (see `set_alt`), so the alt arms below never fire on our
    /// rows -- they are ported against the flattened tables, where both
    /// arms coincide (see `bind`).
    unk03: u8,
    /// `Unk_05`: the emitted frame key -- the selected OAM list's first
    /// entry byte 4 shifted right 4, i.e. that entry's palette bank. The
    /// bind emits it (asm38.s:1717) and the tick re-emits it (asm38.s:1790).
    /// Our renderer resolves palettes per frame/OAM entry in `load_frame`,
    /// so this is stored for the trace tooling rather than consumed here.
    unk05: u8,
    /// Added to every frame's palette index, as the game's temp attack
    /// objects add byte_80B8BD4's palette byte (HiCannon's barrel is the
    /// Cannon's with palette 1, M-Cannon's with 2).
    palette_add: usize,
    /// The hold state. The ROM keeps no latch: at end-of-stream without loop
    /// it parks `Unk_01 = 1` (asm38.s:1772-1774) and re-consumes the end
    /// marker every other tick, holding the last frame. Re-consuming is
    /// display-identical to stopping, so the port latches here instead and
    /// the game logic polls it through `finished()`.
    done: bool,
    /// The palette currently in VRAM and the index it came from. Frames of one
    /// animation almost always share a palette, so this avoids reallocating it
    /// on every frame change.
    palette: Option<(u16, PaletteVramSingle)>,
    /// Palettes in VRAM for parts drawn with an OAM palette offset, keyed
    /// by the palette index they resolve to. The offset indexes the
    /// sprite's own palette table past the frame's palette: the cannon
    /// barrel's silhouette is its flat palette 4, the Vulcan gun's first
    /// frame its flat palette 1, the barrier bubble's later frames its
    /// lighter palettes 1 and 2 -- all confirmed against the real ROM. An
    /// offset past the palettes the asset carries falls back to the frame's
    /// own (the gun's second frame, offset 2, shows its own colours on the
    /// real ROM; the asset is exported with one extra palette so it does).
    offset_palettes: [Option<PaletteVramSingle>; 8],
    /// An all-white palette for the hit flash, allocated on first use. The game
    /// does this by forcing the object's palette bank to 15
    /// (sprite_forceWhitePalette, asm/sprite.s:1141).
    white: Option<PaletteVramSingle>,
    white_on: bool,
    /// The current palette with green and blue masked off, allocated on first
    /// use and keyed by the index it came from. StepSwrd's afterimage is drawn
    /// this way: the real ROM loads a whole palette bank that is the navi's
    /// with only the red component kept, entry for entry (read out of OBJ
    /// palette RAM on the frame it is drawn).
    red: Option<(u16, PaletteVramSingle)>,
    red_on: bool,
    /// Whether an OAM palette offset counts from the shifted palette or the
    /// frame's own; see `load_frame`.
    offsets_follow_shift: bool,
    parts: Vec<Part>,
}

impl Player {
    pub fn new(assets: Assets, anim: usize) -> Self {
        let mut p = Self {
            assets,
            anim,
            frame_in_anim: 0,
            countdown: 0,
            cmd_flags: 0,
            unk03: 0,
            unk05: 0,
            palette_add: 0,
            done: false,
            palette: None,
            offset_palettes: Default::default(),
            white: None,
            white_on: false,
            red: None,
            red_on: false,
            offsets_follow_shift: false,
            parts: Vec::new(),
        };
        p.bind(anim);
        p.load_frame();
        p
    }

    /// Bind `anim`: the port of `_sprite_loadAnimationData`
    /// (reference/bn6f/asm/asm38.s:1667-1721). The normal path
    /// (`Unk_03 & 0x80 == 0`, asm38.s:1673-1688) indexes the dword table at
    /// `[Unk_18]` by `Unk_00 * 4`, follows `+8` to the frame list and takes
    /// its first entry as `Unk_20`, loading `Unk_01`/`Unk_02` from command
    /// bytes 1/2 (asm38.s:1684-1688). The alt path (`Unk_03 & 0x80`,
    /// asm38.s:1689-1716) indexes `[Unk_18]` by `Unk_00 * 4` directly into
    /// `Unk_1c`, then `+8` and the first entry into `Unk_20`, loading
    /// `Unk_01`/`Unk_02` from `[Unk_1c+0x10]`/`[Unk_1c+0x12]`
    /// (asm38.s:1712-1716). The exporter flattens both layouts into one
    /// per-animation command stream (plan §1.2), so both arms land on the
    /// stream's first command here (see `load_command`); `Unk_05` is emitted
    /// in `load_frame` (asm38.s:1717-1721). Like the ROM bind, this does not
    /// tick: the countdown covers the bind frame, and the next `update` --
    /// whether it runs later this frame (`object_updateSprite` rebinds then
    /// ticks, asm00_2.s:25060-25083) or next frame -- decrements it first.
    fn bind(&mut self, anim: usize) {
        if self.unk03 & ALT_STREAM_BIT != 0 {
            // Alt arm (asm38.s:1689-1716): `Unk_1c = [Unk_18 + Unk_00 * 4]`
            // (ROM-relative), durations from the entry's `+0x10`/`+0x12` --
            // the same (duration, flags) pair the flattened frame carries.
        } else {
            // Normal arm (asm38.s:1673-1688): `Unk_1c = [Unk_18]`,
            // `Unk_20 = first entry past +8`, durations from command
            // bytes 1/2 -- the same flattened pair.
        }
        self.set_animation(anim);
        self.frame_in_anim = 0;
        let (first, _) = self.assets.anim(anim);
        self.load_command(first);
        self.done = false;
    }

    /// Load the countdown (`Unk_01`) and flags (`Unk_02`) from one flattened
    /// command: the normal bind reads command bytes 1/2 at `Unk_20`
    /// (asm38.s:1684-1688), the alt bind reads `[Unk_1c+0x10]`/`[Unk_1c+0x12]`
    /// (asm38.s:1712-1716).
    fn load_command(&mut self, index: usize) {
        let cmd = self.assets.frame(index);
        self.countdown = cmd.duration.max(MIN_DURATION);
        self.cmd_flags = cmd.flags;
    }

    /// Advance one command in the current stream. The normal stream steps
    /// `Unk_20 += 3` (asm38.s:1740) and reloads `Unk_01`/`Unk_02` from the
    /// new command's bytes 1/2 (asm38.s:1742-1745); the alt stream steps
    /// `Unk_1c += 0x14` (asm38.s:1754-1755), re-resolves `Unk_20` through
    /// `[Unk_18] + [Unk_1c+8]` (asm38.s:1756-1760) and reloads from
    /// `[Unk_1c+0x10]`/`[Unk_1c+0x12]` (asm38.s:1761-1765). The arm is
    /// selected by `Unk_03 & 0x80` (asm38.s:1730-1733); flattened, both
    /// advance one frame and reload (duration, flags) from it.
    fn step_stream(&mut self, first: usize) {
        if self.unk03 & ALT_STREAM_BIT != 0 {
            // Alt advance (asm38.s:1747-1766): stride 0x14 over the entry
            // array plus the re-resolve -- absorbed by the flattening.
        } else {
            // Normal advance (asm38.s:1740-1746): stride 3 over commands.
        }
        self.frame_in_anim += 1;
        self.load_command(first + self.frame_in_anim);
    }

    /// Select-and-bind `anim`: the `CurAnim` write pushed through
    /// `sprite_setAnimation`'s `Unk_00` store (sprite.s:1131), rebound at
    /// once when it differs from the bound animation -- the direct-bind path
    /// the spawn/init code takes (`bl sprite_loadAnimationData`, plan §1.3).
    /// Re-selecting the bound animation rewrites `Unk_00` and does NOT
    /// restart the stream: canon only rebinds on a `CurAnim != CurAnimCopy`
    /// edge (asm00_2.s:25077-25081), so a same-animation replay keeps the
    /// current frame and countdown. `Actor::select` (the AI-side `CurAnim`
    /// write) and the battle.rs one-shot selections all flow through here.
    pub fn play(&mut self, anim: usize) {
        if self.anim == anim {
            // Rebind edge not taken (`beq` past setAnimation+bind): the
            // stream keeps ticking; `Unk_00` already reads `anim`.
            return;
        }
        self.bind(anim);
        self.load_frame();
    }

    /// Write the pending animation index (`Unk_00`): the port of
    /// `sprite_setAnimation` (reference/bn6f/asm/sprite.s:1131 -- `strb r0,
    /// [r3,#oObjectSprite_Unk_00]` after the header-offset shift). Its twin
    /// `sprite_setAnimationAlt` (sprite.s:1120) is instruction-identical
    /// (same shift, same store); only the callers differ. This does not
    /// rebind: the per-frame gate (`rebind_if_changed`) picks the write up.
    pub fn set_animation(&mut self, anim: usize) {
        self.anim = anim;
    }

    /// Set the alternate-stream flag (`Unk_03 & 0x80`, see `ALT_STREAM_BIT`).
    /// Nothing in src/ calls this (default off, as `sprite_initialize`
    /// leaves it, sprite.s:101); it exists so the ported alt arms have
    /// their ROM-side input.
    pub fn set_alt(&mut self, alt: bool) {
        if alt {
            self.unk03 |= ALT_STREAM_BIT;
        } else {
            self.unk03 &= !ALT_STREAM_BIT;
        }
    }

    /// The `CurAnim` vs `CurAnimCopy` rebind protocol shared by every
    /// per-frame sprite gate (`object_updateSprite` asm00_2.s:25077-25083,
    /// `object_updateSpriteTimestop` asm00_2.s:25096-25105, `sub_801BC24`
    /// asm00_2.s:25128-25141, `UpdateBattleObjectSprite` asm00_2.s:25170-25180):
    /// when the AI-side `CurAnim` differs from its copy, write it through
    /// `sprite_setAnimation` (sprite.s:1131, inside `bind`), rebind with
    /// `sprite_loadAnimationData` (inside `bind`), and advance the copy.
    /// Returns true when it rebound.
    pub fn rebind_if_changed(&mut self, cur_anim: usize, cur_anim_copy: &mut usize) -> bool {
        if *cur_anim_copy == cur_anim {
            return false;
        }
        self.bind(cur_anim);
        self.load_frame();
        *cur_anim_copy = cur_anim;
        true
    }

    /// `object_updateSprite` (asm00_2.s:25045-25083) minus its gates: the
    /// rebind protocol above, then `sprite_update`. The gates -- pause
    /// (:25046-25048), ACTIVE (:25050-25053), STOP_SPRITE_UPDATE (:25054-25057),
    /// timestop unless UPDATE_DURING_TIMESTOP (:25058-25066), and the
    /// CollisionDataPtr/PreventAnim check (:25067-25076) -- all pass for our
    /// battle objects; see `SpriteGate::battle_object`.
    pub fn update_sprite(&mut self, cur_anim: usize, cur_anim_copy: &mut usize) {
        self.rebind_if_changed(cur_anim, cur_anim_copy);
        self.update();
    }

    /// `object_updateSpriteTimestop` (asm00_2.s:25084-25109): the same core
    /// without the timestop gate (it runs during timestop). No caller in
    /// src/ models timestop yet, so this shares the body; kept as the cited
    /// variant for the port that does.
    pub fn update_sprite_timestop(&mut self, cur_anim: usize, cur_anim_copy: &mut usize) {
        self.rebind_if_changed(cur_anim, cur_anim_copy);
        self.update();
    }

    /// `sub_801BC24` (asm00_2.s:25110-25143): the rebind-only variant -- on
    /// a changed animation it rebinds and returns WITHOUT ticking
    /// (:25128-25141, then `pop {pc}`); only the unchanged path ticks
    /// (:25142 `bl sprite_update`). Same gates as `object_updateSprite`.
    pub fn update_sprite_rebind_only(&mut self, cur_anim: usize, cur_anim_copy: &mut usize) {
        if !self.rebind_if_changed(cur_anim, cur_anim_copy) {
            self.update();
        }
    }

    /// `UpdateBattleObjectSprite` (asm00_2.s:25144-25190): the flag-checked
    /// wrapper battle objects actually go through (plan §1.3). Unlike
    /// `object_updateSprite` it checks no pause flag: ACTIVE clear
    /// (:25147-25151) or STOP_SPRITE_UPDATE set (:25152-25156) skips the
    /// sprite; without UPDATE_DURING_TIMESTOP (:25157-25166) timestop skips
    /// it too; then the CollisionDataPtr/PreventAnim check (:25167-25169)
    /// before the shared rebind-then-tick core (:25170-25182).
    pub fn update_battle_object_sprite(
        &mut self,
        gate: SpriteGate,
        cur_anim: usize,
        cur_anim_copy: &mut usize,
    ) {
        if gate.flags & FLAG_ACTIVE == 0 {
            return;
        }
        if gate.flags & FLAG_STOP_SPRITE_UPDATE != 0 {
            return;
        }
        if gate.flags & FLAG_UPDATE_DURING_TIMESTOP == 0 && gate.timestop {
            return;
        }
        if gate.prevent_anim {
            return;
        }
        self.update_sprite(cur_anim, cur_anim_copy);
    }

    /// The bound animation index (`Unk_00`, written by `set_animation` and
    /// consumed by the bind). After the per-frame gate it is also what the
    /// stream shows; mid-frame (between an AI-side select and the gate) it
    /// is the selection, like canon's `Unk_00`.
    pub fn anim(&self) -> usize {
        self.anim
    }

    /// Draw with the frame's palette index shifted by `add` from now on.
    pub fn set_palette_add(&mut self, add: usize) {
        self.palette_add = add;
        self.palette = None;
        // The per-offset palettes are cached by the OAM offset alone, so they
        // have to go too: a shift changes which palette an offset lands on.
        // Without this a sprite whose first frame already carries an offset
        // keeps the palette it was built with -- PoisSeed's pod, whose every
        // part carries offset 9, stayed IceSeed's cyan however it was shifted.
        self.offset_palettes = Default::default();
        self.load_frame();
    }

    pub fn parts(&self) -> &[Part] {
        &self.parts
    }

    /// True once a one-shot animation has held its last frame to the end.
    pub fn finished(&self) -> bool {
        self.done
    }

    /// True while the currently-displayed frame is the one whose own data
    /// carries the 0x80 "last frame" flag -- for a looping animation (0x40
    /// also set) this goes true once every loop, for as many ticks as that
    /// frame's duration lasts, rather than latching like `finished`. This is
    /// `sprite_getFrameParameters`'s bit 0x80 (asm/sprite.s:1182-1198),
    /// which the Mettaur shockwave segment's departure state polls every
    /// frame to know when to vanish (`sub_80C6CBA`, asm31.s:31552-31567): it
    /// does not count down a fixed timer, it waits for its own animation to
    /// come back around to this frame.
    pub fn on_last_frame(&self) -> bool {
        self.cmd_flags & CMD_END != 0
    }

    /// The emitted frame key (`Unk_05`): the current frame's OAM list's
    /// first entry byte 4 shifted right 4, i.e. its palette bank. Stored
    /// for the trace tooling; the renderer resolves palettes itself.
    pub fn unk05(&self) -> u8 {
        self.unk05
    }

    /// Draw every part solid white, or normally again. Rebuilds the current
    /// frame in place without disturbing its timing.
    pub fn set_white(&mut self, on: bool) {
        if on == self.white_on {
            return;
        }
        self.white_on = on;
        self.load_frame();
    }

    /// Which animation this player is on, and how far into it. With
    /// `frozen_at` this is enough to rebuild the same still frame later.
    pub fn frame_key(&self) -> (usize, usize) {
        (self.anim, self.frame_in_anim)
    }

    /// Count OAM palette offsets from the shifted palette rather than the
    /// frame's own. Set before the palette shift; see `load_frame`.
    pub fn set_offsets_follow_shift(&mut self, on: bool) {
        self.offsets_follow_shift = on;
        self.offset_palettes = Default::default();
    }

    /// A still player holding one named frame of one animation.
    pub fn frozen_at(assets: Assets, anim: usize, frame_in_anim: usize) -> Self {
        let mut p = Self::new(assets, anim);
        p.frame_in_anim = frame_in_anim;
        // Keep the command state consistent with the frozen frame, as the
        // bind would have left it had the stream run there: `on_last_frame`
        // and `unk05` read the current command, not frame 0's.
        let (first, _) = p.assets.anim(anim);
        let cmd = p.assets.frame(first + frame_in_anim);
        p.countdown = cmd.duration.max(1);
        p.cmd_flags = cmd.flags;
        p.done = true;
        p.load_frame();
        p
    }

    /// Draw every part with green and blue masked off, or normally again.
    pub fn set_red_only(&mut self, on: bool) {
        if on == self.red_on {
            return;
        }
        self.red_on = on;
        self.load_frame();
    }

    /// Advance by one hardware frame: the port of `_sprite_update`
    /// (reference/bn6f/asm/asm38.s:1722-1793), both stream arms selected by
    /// `Unk_03 & 0x80` (asm38.s:1730-1733; the alt arm at :1747-1766, the
    /// normal arm at :1734-1746 -- see `step_stream` for why they coincide
    /// here). Decrement the countdown; while it goes negative, consume
    /// commands: at end-of-stream loop through a rebind or hold the last
    /// frame, else step to the next command and reload. Every exit re-emits
    /// `Unk_05` (asm38.s:1790, in `load_frame`). A one-shot holds its last
    /// frame rather than wrapping; the caller decides what to play next.
    pub fn update(&mut self) {
        if self.done {
            return;
        }
        // Decrement-then-compare (asm38.s:1725-1729: `ldrb r0, [Unk_01]` /
        // `sub r0, #1` / `strb` / `cmp r0, #0` / `bge` to the emit tail): the
        // compare is on the full register, so 0 goes to -1 and consumes
        // while anything else keeps displaying the current command --
        // including durations above 127 (vulcan_fireball holds a frame for
        // 255 ticks), which a signed-byte view of the countdown would
        // misread as negative.
        loop {
            if self.countdown == 0 {
                // Countdown ran out: the register went negative, so consume
                // the current command (below). Its flags live in `cmd_flags`
                // as the ROM keeps them in `Unk_02` (asm38.s:1735-1738:
                // `ldrb r0, [r1,#2]` then `tst r0, 0x80`).
                self.countdown = 0xFF; // canon: the `strb` of r0 = -1 at asm38.s:1727; reloaded below before it can tick
            } else {
                self.countdown -= 1;
                return;
            }
            let (first, count) = self.assets.anim(self.anim);
            if self.cmd_flags & CMD_END == 0 && self.frame_in_anim + 1 < count {
                // Next command, then keep consuming (both arms branch back
                // to the decrement: normal asm38.s:1746, alt asm38.s:1766).
                self.step_stream(first);
                self.load_frame();
                continue;
            }
            if self.cmd_flags & CMD_LOOP != 0 {
                // Loop: restart through the bind (asm38.s:1776:
                // `bl _sprite_loadAnimationData`), then keep consuming
                // (asm38.s:1777 branches back to the decrement).
                self.bind(self.anim);
                self.load_frame();
                continue;
            }
            // Hold: park the countdown at 1 (asm38.s:1772-1774: `mov r4, #1`
            // then `strb`) and fall through to the decrement above, which
            // takes it to 0 and re-emits the last frame; the next tick
            // re-consumes this same end marker. Latch `done` for the game
            // logic polling `finished()` instead of re-consuming forever:
            // display-identical.
            self.countdown = 1; // canon: `_sprite_update` parks Unk_01 = 1, asm38.s:1772-1774
            self.done = true;
        }
    }

    fn load_frame(&mut self) {
        let (first, _) = self.assets.anim(self.anim);
        let frame = self.assets.frame(first + self.frame_in_anim);
        // Emit `Unk_05` (bind tail asm38.s:1717, tick tail asm38.s:1790):
        // the selected OAM list's first entry byte 4 shifted right 4.
        // The asset stores that nibble as the entry's `pal_offset`
        // (`tools/spr_export.py` packs `pal_offset << 4`; `sub_8002818`
        // draws the frame with palette `Unk_04 + Unk_05`).
        self.unk05 = if frame.oam_count == 0 {
            0
        } else {
            self.assets.oam(frame.oam_first as usize).pal_offset
        };
        let tiles = self.assets.gfx(frame.gfx as usize);
        // The outgoing sprites hold the only other references to the previous
        // palette, so they go first; otherwise its slot is still occupied when
        // a differently-paletted frame tries to allocate.
        self.parts.clear();

        let palette = if self.white_on {
            self.white
                .get_or_insert_with(|| {
                    PaletteVramSingle::try_allocate_shared(&Palette16::new([Rgb15::new(WHITE); 16]))
                        .expect("white palette should fit in vram")
                })
                .clone()
        } else if self.red_on {
            let index = frame.pal + self.palette_add as u16;
            match &self.red {
                Some((cached, palette)) if *cached == index => palette.clone(),
                _ => {
                    self.red = None;
                    let src = self.assets.palette(index as usize);
                    let mut colours = [Rgb15::new(0); 16];
                    for (i, c) in colours.iter_mut().enumerate() {
                        *c = Rgb15::new(src.colour(i).0 & 0x001f);
                    }
                    let palette = PaletteVramSingle::try_allocate_shared(&Palette16::new(colours))
                        .expect("red-only palette should fit in vram");
                    self.red = Some((index, palette.clone()));
                    palette
                }
            }
        } else {
            let index = frame.pal + self.palette_add as u16;
            match &self.palette {
                Some((cached, palette)) if *cached == index => palette.clone(),
                _ => {
                    self.palette = None;
                    let palette =
                        PaletteVramSingle::try_allocate_shared(&self.assets.palette(index as usize))
                            .expect("sprite palette should fit in vram");
                    self.palette = Some((index, palette.clone()));
                    palette
                }
            }
        };

        for i in 0..frame.oam_count as usize {
            let e = self.assets.oam(frame.oam_first as usize + i);
            let (w, h) = e.size.to_tiles_width_height();
            let start = e.tile as usize * 32;
            let len = w * h * 32;
            // Which palette an OAM offset counts from is not the same for
            // every object, and both halves of this are measured. HiCannon's
            // barrel sits in palette 1 and its silhouette frame, offset 4,
            // still shows the flat palette 4 -- so by default the offset
            // counts from the FRAME's palette and ignores the shift. Barr100's
            // bubble is Barrier's shifted by 3, and its later frames, which
            // carry offsets 1 and 2, show the gold set's lighter shades 4 and
            // 5 rather than the teal 1 and 2 -- so it counts from the SHIFTED
            // palette. `offsets_follow_shift` picks which.
            let offset_index = frame.pal as usize
                + if self.offsets_follow_shift { self.palette_add } else { 0 }
                + e.pal_offset as usize;
            let part_palette = if e.pal_offset != 0
                && !self.white_on
                && !self.red_on
                && offset_index < self.assets.palette_count()
            {
                self.offset_palettes[e.pal_offset as usize & 7]
                    .get_or_insert_with(|| {
                        PaletteVramSingle::try_allocate_shared(&self.assets.palette(offset_index))
                            .expect("offset palette should fit in vram")
                    })
                    .clone()
            } else {
                palette.clone()
            };
            let sprite = DynamicSprite16::from_bytes(e.size, &tiles[start..start + len])
                .to_vram(part_palette);
            self.parts.push(Part {
                sprite,
                x: e.x as i32,
                y: e.y as i32,
                width: (w * 8) as i32,
                hflip: e.hflip,
                vflip: e.vflip,
            });
        }
        // Timing stays in `bind`/`update`: rebuilding the frame's VRAM
        // (palette swaps, stills) must not disturb the countdown.
    }
}
