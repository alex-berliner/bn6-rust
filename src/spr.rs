//! Runtime reader and animation player for exported bn6f sprite assets.
//!
//! The binary layout is produced by `tools/spr_export.py`; see that file for
//! the format. Multi-byte fields are read byte-wise because the asset is
//! embedded with `include_bytes!` and ARM7TDMI faults on unaligned word loads.

use agb::display::object::{DynamicSprite16, PaletteVramSingle, Size, SpriteVram};
use agb::display::{Palette16, Rgb15};
use alloc::vec::Vec;

const MAGIC: &[u8; 4] = b"BNSP";

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
}

pub struct Oam {
    pub tile: u16,
    pub x: i8,
    pub y: i8,
    pub size: Size,
    pub hflip: bool,
    pub vflip: bool,
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

    pub fn anim_count(&self) -> usize {
        self.u32_at(self.anim) as usize
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
    pub hflip: bool,
    pub vflip: bool,
}

/// Plays one animation, rebuilding VRAM sprites only when the frame changes.
pub struct Player {
    assets: Assets,
    anim: usize,
    frame_in_anim: usize,
    ticks_left: u8,
    parts: Vec<Part>,
}

impl Player {
    pub fn new(assets: Assets, anim: usize) -> Self {
        let mut p = Self {
            assets,
            anim,
            frame_in_anim: 0,
            ticks_left: 0,
            parts: Vec::new(),
        };
        p.load_frame();
        p
    }

    pub fn set_anim(&mut self, anim: usize) {
        if anim != self.anim {
            self.anim = anim;
            self.frame_in_anim = 0;
            self.load_frame();
        }
    }

    pub fn anim_count(&self) -> usize {
        self.assets.anim_count()
    }

    pub fn parts(&self) -> &[Part] {
        &self.parts
    }

    /// Advance by one hardware frame, loading the next animation frame when the
    /// current one's duration expires.
    pub fn update(&mut self) {
        self.ticks_left = self.ticks_left.saturating_sub(1);
        if self.ticks_left == 0 {
            let (_, count) = self.assets.anim(self.anim);
            self.frame_in_anim = (self.frame_in_anim + 1) % count;
            self.load_frame();
        }
    }

    fn load_frame(&mut self) {
        let (first, _) = self.assets.anim(self.anim);
        let frame = self.assets.frame(first + self.frame_in_anim);
        let tiles = self.assets.gfx(frame.gfx as usize);
        let palette = PaletteVramSingle::try_allocate_new(&self.assets.palette(frame.pal as usize))
            .expect("sprite palette should fit in vram");

        self.parts.clear();
        for i in 0..frame.oam_count as usize {
            let e = self.assets.oam(frame.oam_first as usize + i);
            let (w, h) = e.size.to_tiles_width_height();
            let start = e.tile as usize * 32;
            let len = w * h * 32;
            let sprite = DynamicSprite16::from_bytes(e.size, &tiles[start..start + len])
                .to_vram(palette.clone());
            self.parts.push(Part {
                sprite,
                x: e.x as i32,
                y: e.y as i32,
                hflip: e.hflip,
                vflip: e.vflip,
            });
        }

        self.ticks_left = frame.duration.max(1);
    }
}
