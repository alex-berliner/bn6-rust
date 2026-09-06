//! Runtime reader and animation player for exported bn6f sprite assets.
//!
//! The binary layout is produced by `tools/spr_export.py`; see that file for
//! the format. Multi-byte fields are read byte-wise because the asset is
//! embedded with `include_bytes!` and ARM7TDMI faults on unaligned word loads.

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
pub struct Player {
    assets: Assets,
    anim: usize,
    frame_in_anim: usize,
    ticks_left: u8,
    /// Added to every frame's palette index, as the game's temp attack
    /// objects add byte_80B8BD4's palette byte (HiCannon's barrel is the
    /// Cannon's with palette 1, M-Cannon's with 2).
    palette_add: usize,
    /// Set by `new` and `play`: the frame just loaded is drawn this frame
    /// and its duration counts from the next, as the game's sprites do (an
    /// animation set during an object's update shows its first frame for
    /// the full duration; verified frame-for-frame against the real ROM).
    fresh: bool,
    done: bool,
    /// The palette currently in VRAM and the index it came from. Frames of one
    /// animation almost always share a palette, so this avoids reallocating it
    /// on every frame change.
    palette: Option<(u16, PaletteVramSingle)>,
    /// The flat palettes parts with a palette offset are drawn in, keyed by
    /// the offset. Measured on the real ROM: offset 1 draws every colour as
    /// (247,239,222) (BGR555 0x6fbe; the Vulcan gun's first frame), offset 4
    /// as (239,255,239) (0x77fd; the cannon barrel's silhouette), and offset
    /// 2 leaves the sprite's own colours (the gun's second frame). The banks
    /// those offsets land on in the game's object palette layout were not
    /// identified; the colours were.
    flat: [Option<PaletteVramSingle>; 8],
    /// An all-white palette for the hit flash, allocated on first use. The game
    /// does this by forcing the object's palette bank to 15
    /// (sprite_forceWhitePalette, asm/sprite.s:1141).
    white: Option<PaletteVramSingle>,
    white_on: bool,
    parts: Vec<Part>,
}

impl Player {
    pub fn new(assets: Assets, anim: usize) -> Self {
        let mut p = Self {
            assets,
            anim,
            frame_in_anim: 0,
            ticks_left: 0,
            palette_add: 0,
            fresh: true,
            done: false,
            palette: None,
            flat: Default::default(),
            white: None,
            white_on: false,
            parts: Vec::new(),
        };
        p.load_frame();
        p
    }

    /// Restart on `anim`, even if it is already the current one, so a one-shot
    /// animation can be replayed.
    pub fn play(&mut self, anim: usize) {
        self.anim = anim;
        self.frame_in_anim = 0;
        self.done = false;
        self.fresh = true;
        self.load_frame();
    }

    pub fn anim(&self) -> usize {
        self.anim
    }

    /// Draw with the frame's palette index shifted by `add` from now on.
    pub fn set_palette_add(&mut self, add: usize) {
        self.palette_add = add;
        self.palette = None;
        let ticks = self.ticks_left;
        let fresh = self.fresh;
        self.load_frame();
        self.ticks_left = ticks;
        self.fresh = fresh;
    }

    pub fn parts(&self) -> &[Part] {
        &self.parts
    }

    /// True once a one-shot animation has held its last frame to the end.
    pub fn finished(&self) -> bool {
        self.done
    }

    /// Draw every part solid white, or normally again. Rebuilds the current
    /// frame in place without disturbing its timing.
    pub fn set_white(&mut self, on: bool) {
        if on == self.white_on {
            return;
        }
        self.white_on = on;
        let ticks = self.ticks_left;
        self.load_frame();
        self.ticks_left = ticks;
    }

    /// Advance by one hardware frame, loading the next animation frame when the
    /// current one's duration expires. A one-shot animation holds its last
    /// frame rather than wrapping; the caller decides what to play next.
    pub fn update(&mut self) {
        if self.done {
            return;
        }
        if self.fresh {
            self.fresh = false;
            return;
        }
        self.ticks_left = self.ticks_left.saturating_sub(1);
        if self.ticks_left > 0 {
            return;
        }
        let (first, count) = self.assets.anim(self.anim);
        if self.assets.frame(first + self.frame_in_anim).flags & 0x40 == 0
            && self.frame_in_anim + 1 >= count
        {
            self.done = true;
            return;
        }
        self.frame_in_anim = (self.frame_in_anim + 1) % count;
        self.load_frame();
    }

    fn load_frame(&mut self) {
        let (first, _) = self.assets.anim(self.anim);
        let frame = self.assets.frame(first + self.frame_in_anim);
        let tiles = self.assets.gfx(frame.gfx as usize);
        // The outgoing sprites hold the only other references to the previous
        // palette, so they go first; otherwise its slot is still occupied when
        // a differently-paletted frame tries to allocate.
        self.parts.clear();

        let palette = if self.white_on {
            self.white
                .get_or_insert_with(|| {
                    PaletteVramSingle::try_allocate_new(&Palette16::new([Rgb15::new(0x7fff); 16]))
                        .expect("white palette should fit in vram")
                })
                .clone()
        } else {
            let index = frame.pal + self.palette_add as u16;
            match &self.palette {
                Some((cached, palette)) if *cached == index => palette.clone(),
                _ => {
                    self.palette = None;
                    let palette =
                        PaletteVramSingle::try_allocate_new(&self.assets.palette(index as usize))
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
            let flat_colour = match e.pal_offset {
                1 => Some(0x6fbe),
                4 => Some(0x77fd),
                _ => None,
            };
            let part_palette = match flat_colour {
                Some(colour) if !self.white_on => self.flat[e.pal_offset as usize & 7]
                    .get_or_insert_with(|| {
                        PaletteVramSingle::try_allocate_new(&Palette16::new(
                            [Rgb15::new(colour); 16],
                        ))
                        .expect("flat palette should fit in vram")
                    })
                    .clone(),
                _ => palette.clone(),
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

        self.ticks_left = frame.duration.max(1);
    }
}
