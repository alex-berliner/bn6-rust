//! The wide ribbon that crosses the middle of the screen: "BATTLE START!",
//! "ENEMY DELETED", "MEGAMAN DELETED" and forty-two more.
//!
//! It is not a picture. The real ROM keeps a font of 8x16 cells and a record
//! per message -- `(y << 8) | x`, then a pointer per cell, terminated by the
//! blank glyph -- and uploads twenty cells as five 32x16 objects
//! (sub_801E838, asm00_2.s:31106). `tools/banner_export.py` walks those
//! records out of the ROM into `assets/banner.bin`; see it for the format.
//!
//! The whole strip is one affine object animation shared with the chip-name
//! popup: the vertical scale unrolls it from a flat line, overshoots into a
//! stretch, holds, and rolls it back up. Read out of the real ROM's OAM frame
//! by frame for both, and it is the same sequence.

use agb::display::object::{
    AffineMatrixObject, AffineMode, DynamicSprite16, ObjectAffine, PaletteVramSingle, Size,
    SpriteVram,
};
use agb::display::{AffineMatrix, GraphicsFrame, Palette16, Priority, Rgb15};
use agb::fixnum::Num;
use alloc::vec::Vec;

const MAGIC: &[u8; 4] = b"BNBR";
/// Cells across the strip: five 32x16 objects of four 8x16 cells each.
const CELLS: usize = 20;
const OBJECTS: usize = 5;
const GLYPH_BYTES: usize = 0x40;
/// Bytes of one 32x16 object: eight 4bpp tiles.
const OBJECT_BYTES: usize = 8 * 32;

/// The vertical scale of the shared affine matrix, in the 8.8 OAM stores, one
/// entry per frame of the 58 the banner is up. BIGGER IS FLATTER, because the
/// matrix maps the screen back to the texture: 0x100 is life size, 896 is a
/// sixth of the height and 208 is a fifth taller than life.
pub const SCALE: [u16; 58] = [
    768, 640, 512, 384, 256, 208, 224, // unrolling, with an overshoot
    256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256,
    256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256,
    256, 256, 256, 256, 256, 256, 256, 256, 256, 256, 256,
    256, 256, 256, 256, 256, 256, 256, 256, 256, 256, // held
    224, 208, 256, 384, 512, 640, 768, 896, // rolling back up
];

/// Message ids, in the order `banner_export.py` writes them, which is the
/// order of the game's own two arrays.
pub const BATTLE_START: usize = 0;
pub const ENEMY_DELETED: usize = 1;
pub const MEGAMAN_DELETED: usize = 2;

/// The exported font and message records, read in place out of the asset.
#[derive(Clone, Copy)]
pub struct Assets {
    data: &'static [u8],
    glyphs: usize,
    messages: usize,
    count: usize,
}

impl Assets {
    pub fn new(data: &'static [u8]) -> Self {
        assert_eq!(&data[0..4], MAGIC, "not a BNBR asset");
        let at = |o: usize| u32::from_le_bytes(data[o..o + 4].try_into().unwrap()) as usize;
        Self {
            data,
            glyphs: at(0x10),
            messages: at(0x14),
            count: at(0x0c),
        }
    }

    pub fn palette(&self) -> Palette16 {
        let mut colours = [Rgb15::new(0); 16];
        for (i, slot) in colours.iter_mut().enumerate() {
            let o = 0x18 + i * 2;
            *slot = Rgb15::new(u16::from_le_bytes(self.data[o..o + 2].try_into().unwrap()));
        }
        Palette16::new(colours)
    }

    /// `(x, y, [glyph index; CELLS])` for a message.
    fn message(&self, id: usize) -> (i32, i32, [usize; CELLS]) {
        assert!(id < self.count);
        let r = self.messages + id * (2 + CELLS * 2);
        let mut cells = [0usize; CELLS];
        for (i, cell) in cells.iter_mut().enumerate() {
            let o = r + 2 + i * 2;
            *cell = u16::from_le_bytes(self.data[o..o + 2].try_into().unwrap()) as usize;
        }
        (self.data[r] as i32, self.data[r + 1] as i32, cells)
    }

    fn glyph(&self, index: usize) -> &'static [u8] {
        let o = self.glyphs + index * GLYPH_BYTES;
        &self.data[o..o + GLYPH_BYTES]
    }
}

/// A banner on screen: its five objects, where they go and how far in it is.
pub struct Banner {
    objects: Vec<SpriteVram>,
    x: i32,
    y: i32,
    t: usize,
}

impl Banner {
    pub fn new(assets: Assets, id: usize) -> Self {
        let (x, y, cells) = assets.message(id);
        let palette = PaletteVramSingle::try_allocate_shared(&assets.palette())
            .expect("banner palette should fit in vram");
        // One 32x16 object per four cells. In the GBA's 1D mapping that is
        // four tiles of top halves and then four of bottom halves, which is
        // exactly the order the real ROM's uploader writes them in: the top
        // at its cursor, the bottom 0x80 further on, the cursor stepping 0x20
        // a cell (asm00_2.s:31112).
        let objects = (0..OBJECTS)
            .map(|o| {
                let mut tiles = [0u8; OBJECT_BYTES];
                for c in 0..4 {
                    let glyph = assets.glyph(cells[o * 4 + c]);
                    tiles[c * 32..c * 32 + 32].copy_from_slice(&glyph[..32]);
                    tiles[128 + c * 32..128 + c * 32 + 32].copy_from_slice(&glyph[32..]);
                }
                DynamicSprite16::from_bytes(Size::S32x16, &tiles).to_vram(palette.clone())
            })
            .collect();
        Self { objects, x, y, t: 0 }
    }

    /// Advance a frame; false once the banner has rolled up and gone.
    pub fn update(&mut self) -> bool {
        self.t += 1;
        self.t < SCALE.len()
    }

    pub fn show(&self, frame: &mut GraphicsFrame) {
        let Some(&scale) = SCALE.get(self.t) else {
            return;
        };
        let matrix = AffineMatrixObject::new(AffineMatrix::<Num<i32, 8>> {
            a: Num::from_raw(0x100),
            b: Num::from_raw(0),
            c: Num::from_raw(0),
            d: Num::from_raw(scale as i32),
            x: Num::from_raw(0),
            y: Num::from_raw(0),
        });
        for (i, object) in self.objects.iter().enumerate() {
            ObjectAffine::new(object.clone(), matrix.clone(), AffineMode::Affine)
                .set_priority(Priority::P0)
                .set_pos((self.x + i as i32 * 32, self.y))
                .show(frame);
        }
    }
}
