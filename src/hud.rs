//! The battle digit font and the hardware objects that draw numbers with it.
//!
//! The digits are not a sprite container: they are raw 4bpp tile data acting
//! as a shared font (`dword_86E0AB8`, data/dat38_85.s:1476), which is why they
//! appear in no sprite pointer list. Each glyph is a 0x40-byte 8x16 cell -- two
//! stacked 8x8 tiles -- and so goes into an 8x16 OBJ byte-for-byte, with no
//! reordering (tools/font_export.py).

use agb::display::Priority;
use agb::display::GraphicsFrame;
use agb::display::object::{DynamicSprite16, Object, PaletteVramSingle, Size, SpriteVram};
use agb::display::{Palette16, Rgb15};
use alloc::vec::Vec;

const MAGIC: &[u8; 4] = b"BNFT";
const GLYPH_BYTES: usize = 0x40; // provenance: derived -- dword_86E0AB8's own per-glyph stride, two stacked 8x8 tiles (tools/font_export.py)
const GLYPH_W: i32 = 8; // provenance: derived -- an 8x16 OBJ glyph's own pixel width

/// The digit sets the asset carries: the plain one and the two the game
/// flashes with after damage or a heal.
pub const SETS: usize = 3; // provenance: derived -- the exporter's own asset layout (dword_86E0AB8)
pub const SET_PLAIN: usize = 0;
pub const SET_DAMAGE: usize = 1;
pub const SET_HEAL: usize = 2;

/// Digits the game's object-text HP readout has room for.
const MAX_DIGITS: u32 = 4; // provenance: peeked -- a capture with HP forced to 0xffff reads back "5535", not "65535"

pub struct Hud {
    digits: Vec<SpriteVram>,
}

/// A number on screen that walks toward the value it is meant to show, as
/// the game's HP boxes do: on a change the shown number moves by
/// `|difference| / 8 + 4` a frame and the digits flash in the damage or
/// heal set while a timer runs (sub_801C168, sub_801C1D0, sub_801C1EA;
/// asm00_2.s:25853-25949).
pub struct Counter {
    shown: u16,
    flash: u8,
    set: usize,
}

impl Counter {
    pub fn new(value: u16) -> Self {
        Self {
            shown: value,
            flash: 0,
            set: SET_PLAIN,
        }
    }

    pub fn shown(&self) -> u16 {
        self.shown
    }

    pub fn set(&self) -> usize {
        if self.flash > 0 { self.set } else { SET_PLAIN }
    }

    /// One frame of catching up to `actual`.
    pub fn update(&mut self, actual: u16) {
        self.flash = self.flash.saturating_sub(1);
        if self.shown == actual {
            return;
        }
        // Fifteen, measured: the real ROM's HP box holds its orange ramp for
        // seventeen frames after a ten-point hit, of which three are the
        // countdown itself. provenance: peeked (15, 1) -- measured off a
        // live capture's own flash duration.
        let (set, flash) = if actual < self.shown {
            (SET_DAMAGE, 15)
        } else {
            (SET_HEAL, 1)
        };
        self.set = set;
        self.flash = self.flash.max(flash);
        // Measured on a capture whose navi drops from 60 to 50: the box shows
        // 55, then 51, then 50 -- steps of 5, 4 and 1, which is
        // |difference| / 8 + 4, not + 2. provenance: peeked (8, 4) -- fits
        // that one capture's own step sequence; no disassembly citation.
        let step = self.shown.abs_diff(actual) / 8 + 4;
        self.shown = if actual < self.shown {
            self.shown.saturating_sub(step).max(actual)
        } else {
            (self.shown + step).min(actual)
        };
    }
}

impl Hud {
    pub fn new(data: &'static [u8]) -> Self {
        assert_eq!(&data[0..4], MAGIC, "not a BNFT asset");
        let count = u32::from_le_bytes(data[8..12].try_into().unwrap()) as usize;

        // The glyphs use colour index 5 for the inner fill and 9 for the
        // outline. The palette is the game's own, dword_86B7AC0, which the
        // exporter appends after the glyphs: OBJ bank 14 of a live battle
        // holds those sixteen words exactly. This build stood in flat white
        // on black before, which is a shade off on both.
        let p = 0x0c + count * GLYPH_BYTES;
        let mut colours = [Rgb15::new(0); 16];
        for (i, slot) in colours.iter_mut().enumerate() {
            let o = p + i * 2;
            *slot = Rgb15::new(u16::from_le_bytes(data[o..o + 2].try_into().unwrap()));
        }
        let palette = PaletteVramSingle::try_allocate_shared(&Palette16::new(colours))
            .expect("font palette should fit in vram");

        // Every digit is uploaded once and kept in vram. A number redrawn each
        // frame would otherwise re-upload the same ten glyphs forever.
        let digits = (0..count)
            .map(|i| {
                let o = 0x0c + i * GLYPH_BYTES;
                DynamicSprite16::from_bytes(Size::S8x16, &data[o..o + GLYPH_BYTES])
                    .to_vram(palette.clone())
            })
            .collect();
        Self { digits }
    }

    /// Width in pixels the value will occupy, for centring it on something.
    pub fn width(&self, value: u16) -> i32 {
        let mut digits = 1;
        let mut remaining = value;
        while remaining >= 10 {
            remaining /= 10;
            digits += 1;
        }
        digits * GLYPH_W
    }

    /// Draw `value` right-aligned so its last digit ends at `right_x`, one
    /// 8x16 object per digit. Digits are emitted from the right, so the loop
    /// always runs once and zero draws a lone '0'. The game blank-pads a
    /// fixed-width field; this draws only the digits the number has.
    pub fn draw_number(&self, frame: &mut GraphicsFrame, value: u16, right_x: i32, y: i32) {
        self.draw_number_in(frame, value, right_x, y, SET_PLAIN);
    }

    /// Draw with one of the game's three digit sets.
    pub fn draw_number_in(
        &self,
        frame: &mut GraphicsFrame,
        value: u16,
        right_x: i32,
        y: i32,
        set: usize,
    ) {
        let mut remaining = value;
        let mut x = right_x - GLYPH_W;
        // FOUR DIGITS AND NO MORE. The capture keeps its Mettaur alive by
        // writing 0xffff into its HP, and the readout under it shows 5535,
        // not 65535 -- so the object text has four slots and the rest is
        // dropped.
        let mut left = MAX_DIGITS;
        loop {
            Object::new(self.digits[set * 10 + (remaining % 10) as usize].clone())
                // With the actors, so the chip select window covers them;
                // the game's HP boxes are on its priority-0 HUD layer at
                // the top of the screen, which these placeholders are not.
                .set_priority(Priority::P2)
                .set_pos((x, y))
                .show(frame);
            remaining /= 10;
            left -= 1;
            if remaining == 0 || left == 0 {
                break;
            }
            x -= GLYPH_W;
        }
    }
}
