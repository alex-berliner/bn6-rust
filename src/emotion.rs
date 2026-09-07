//! The emotion window: the navi's face in a blue frame at the top left.
//!
//! The real ROM draws it as two OBJECTS rather than tiles, which is why it
//! survives the field being stripped and stands over the backdrop in every
//! capture: a 32x16 at (0,18) and a 16x16 at (32,18), both at priority 2, read
//! out of the sterile arena's OAM (objects 2 and 3, VRAM tiles 0x3b4 and
//! 0x3bc, palette bank 12). Its art and palette are exported by
//! tools/emotion_export.py.
//!
//! Only the calm face is drawn. The ROM's bank continues past it with one
//! window per emotion, which this build has no state to choose between yet.

use agb::display::object::{DynamicSprite16, Object, PaletteVramSingle, Size, SpriteVram};
use agb::display::{GraphicsFrame, Palette16, Priority, Rgb15};

/// Where the two objects go, measured off the real ROM's OAM.
const LEFT: (i32, i32) = (0, 18);
const RIGHT: (i32, i32) = (32, 18);
/// Tiles in the wide object; the rest belong to the narrow one.
const WIDE_TILES: usize = 8;

pub struct Emotion {
    wide: SpriteVram,
    narrow: SpriteVram,
}

impl Emotion {
    pub fn new(data: &'static [u8]) -> Self {
        assert_eq!(&data[0..4], b"BNEM", "not a BNEM asset");
        let at = |o: usize| u32::from_le_bytes(data[o..o + 4].try_into().unwrap()) as usize;
        let (t, p) = (at(0x08), at(0x0c));
        let len = u32::from_le_bytes(data[t..t + 4].try_into().unwrap()) as usize;
        let tiles = &data[t + 4..t + 4 + len];

        let mut colours = [Rgb15::new(0); 16];
        for (i, slot) in colours.iter_mut().enumerate() {
            let o = p + i * 2;
            *slot = Rgb15::new(u16::from_le_bytes(data[o..o + 2].try_into().unwrap()));
        }
        let palette = PaletteVramSingle::try_allocate_new(&Palette16::new(colours))
            .expect("emotion palette should fit in vram");

        let split = WIDE_TILES * 32;
        Self {
            wide: DynamicSprite16::from_bytes(Size::S32x16, &tiles[..split])
                .to_vram(palette.clone()),
            narrow: DynamicSprite16::from_bytes(Size::S16x16, &tiles[split..]).to_vram(palette),
        }
    }

    pub fn show(&self, frame: &mut GraphicsFrame) {
        for (sprite, at) in [(&self.wide, LEFT), (&self.narrow, RIGHT)] {
            Object::new(sprite.clone())
                .set_priority(Priority::P2)
                .set_pos(at)
                .show(frame);
        }
    }
}
