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

/// Where the two objects go. Peeked off the real ROM's OAM first, then found
/// hardcoded in canon's own draw routine for HUD element 14, sub_801CDEC
/// (asm00_2.s:27554-27583): it hands sub_802FE28 the packed pairs
/// 0x80004012 / 0xCBB4 and 0x40200012 / 0xCBBC -- y=18 x=0 shape 1 size 2
/// (32x16) tile 0x3b4, and y=18 x=32 shape 0 size 1 (16x16) tile 0x3bc, both
/// palette 12 priority 2, which is exactly what the OAM dump reads back.
const LEFT: (i32, i32) = (0, 18); // provenance: derived -- canon sub_801CDEC's own 0x80004012 (asm00_2.s:27576), confirmed against the sterile arena's OAM
const RIGHT: (i32, i32) = (32, 18); // provenance: derived -- canon sub_801CDEC's own 0x40200012 (asm00_2.s:27580), confirmed against the sterile arena's OAM
/// Tiles in the wide object; the rest belong to the narrow one.
const WIDE_TILES: usize = 8; // provenance: derived -- a 32x16 object is 4x2 8x8 tiles, the exporter's own asset layout

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
        let palette = PaletteVramSingle::try_allocate_shared(&Palette16::new(colours))
            .expect("emotion palette should fit in vram");

        let split = WIDE_TILES * 32;
        Self {
            wide: DynamicSprite16::from_bytes(Size::S32x16, &tiles[..split])
                .to_vram(palette.clone()),
            narrow: DynamicSprite16::from_bytes(Size::S16x16, &tiles[split..]).to_vram(palette),
        }
    }

    /// `x_offset` is canon's own per-frame X displacement for this element:
    /// `sub_801CDEC` does not use the packed OAM words below as they stand,
    /// it adds `eStruct2035280 + 0x12` (0x02035292) shifted into the X field
    /// first -- `ldrb r4, [r5,#0x12]; lsl r4, r4, #0x10; add r0, r0, r4`
    /// (asm00_2.s:27561-27568 and :27570-27572, once per object). That byte
    /// is the chip window's own slide counter, counted from the open
    /// position: measured with `--watch 0x02035290:8` on the real ROM it
    /// reads 0 with no window, steps 0x0c a frame from 0 to 0x78 over the
    /// ten frames of the slide-in (BATTLESTART, canon 187..196), holds 0x78
    /// for as long as the window is up, and steps back 0x0c a frame to 0
    /// over the ten frames of the slide-out (CHIPSELECT + Start@50,A@80,
    /// canon 81..90). So the whole HUD's objects ride 120 px to the right
    /// while the chip window covers the left of the screen -- F26b measured
    /// exactly that displacement on `cursor`, canon x122..165 against our
    /// x2..45, byte-identical content.
    pub fn show(&self, frame: &mut GraphicsFrame, x_offset: i32) {
        for (sprite, at) in [(&self.wide, LEFT), (&self.narrow, RIGHT)] {
            Object::new(sprite.clone())
                .set_priority(Priority::P2)
                .set_pos((at.0 + x_offset, at.1))
                .show(frame);
        }
    }
}
