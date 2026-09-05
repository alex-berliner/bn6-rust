//! The battle digit font and the hardware objects that draw numbers with it.
//!
//! The digits are not a sprite container: they are raw 4bpp tile data acting
//! as a shared font (`dword_86E0AB8`, data/dat38_85.s:1476), which is why they
//! appear in no sprite pointer list. Each glyph is a 0x40-byte 8x16 cell -- two
//! stacked 8x8 tiles -- and so goes into an 8x16 OBJ byte-for-byte, with no
//! reordering (tools/font_export.py).

use agb::display::GraphicsFrame;
use agb::display::object::{DynamicSprite16, Object, PaletteVramSingle, Size, SpriteVram};
use agb::display::{Palette16, Rgb, Rgb15};
use alloc::vec::Vec;

const MAGIC: &[u8; 4] = b"BNFT";
const GLYPH_BYTES: usize = 0x40;
const GLYPH_W: i32 = 8;

pub struct Hud {
    digits: Vec<SpriteVram>,
}

impl Hud {
    pub fn new(data: &'static [u8]) -> Self {
        assert_eq!(&data[0..4], MAGIC, "not a BNFT asset");
        let count = u32::from_le_bytes(data[8..12].try_into().unwrap()) as usize;

        // The glyphs use colour index 5 for the inner fill and 9 for the
        // outline. The palette bank the game keeps them in is not identified
        // yet, so this is a local stand-in -- not the game's palette.
        let mut colours = [Rgb15::new(0); 16];
        colours[5] = Rgb15::WHITE;
        colours[9] = Rgb::new(16, 16, 16).to_rgb15();
        let palette = PaletteVramSingle::try_allocate_new(&Palette16::new(colours))
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
        let mut remaining = value;
        let mut x = right_x - GLYPH_W;
        loop {
            Object::new(self.digits[(remaining % 10) as usize].clone())
                .set_pos((x, y))
                .show(frame);
            remaining /= 10;
            if remaining == 0 {
                break;
            }
            x -= GLYPH_W;
        }
    }
}
