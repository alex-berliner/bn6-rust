//! The emotion window: the navi's face in a blue frame at the top left.
//!
//! The real ROM draws it as two OBJECTS rather than tiles, which is why it
//! survives the field being stripped and stands over the backdrop in every
//! capture: a 32x16 at (0,18) and a 16x16 at (32,18), both at priority 2, read
//! out of the sterile arena's OAM (objects 2 and 3, VRAM tiles 0x3b4 and
//! 0x3bc, palette bank 12). Its art and palette are exported by
//! tools/emotion_export.py.
//!
//! The face is chosen by the emotion value the fixture descriptor carries
//! (offset +63). Canon's chain: the draw gate `drawEmotionWindow_801CDEC`
//! reads eStruct2035280+0xf and skips values 5 and 6 (asm00_2.s:27648-27652),
//! while the face's ART is re-uploaded every updater frame by sub_801CB38
//! (asm00_2.s:27332-27464), which indexes the per-emotion pointer table
//! off_801CD08 (asm00_2.s:27580-27603) with the slot that
//! possiblyGetBattleEmotion_8015B64 computes from live battle data -- anger,
//! mood and the like, mapped through byte_801E6F4 (asm00_2.s:31044). This
//! port takes the already-resolved slot from the descriptor: the harness's
//! canon side reaches slot 2 by poking the player's AIData.Unk_32
//! (0x020340B2, measured face-only over 90 frames -- unlike Anger at
//! 0x020340B4, which also tints the field panels and is consumed by the
//! resumed chip's resolution at canon 43); enum 1 via byte_801E6F4 =
//! face slot 2.

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

/// How many faces the bank holds: off_801CD08 is 23 pointer words
/// (asm00_2.s:27580-27603).
const FACE_SLOTS: usize = 23; // canon: off_801CD08's length, the table the draw gate indexes

/// Face slot -> byte offset of the slot's left half inside the asset's bank:
/// canon's own pointer table off_801CD08 (asm00_2.s:27580-27603), resolved to
/// deltas from dword_872D814. Slots 0..14 sit at 0x180 strides with 5/6
/// compressed to 0x100 (the bank's own layout -- those slots are never
/// uploaded), values 15..19 alias 5..9 and 21 aliases 20 IN THE TABLE, and
/// 22 sits at the tail. tools/emotion_export.py parses the same table out of
/// the disassembly and refuses to export a bank the pointers don't fit, so
/// this constant and the asset cannot drift apart silently.
const FACE_INDEX: [u16; FACE_SLOTS] = [
    0x0000, 0x0180, 0x0300, 0x0480, 0x0600, 0x0780, 0x0880, 0x0980, 0x0a80, 0x0b80, 0x0c80,
    0x0d80, 0x0e80, 0x0f80, 0x1080, 0x0780, 0x0880, 0x0980, 0x0a80, 0x0b80, 0x1700, 0x1700,
    0x1800,
]; // provenance: derived -- canon's off_801CD08 (asm00_2.s:27580-27603), deltas from dword_872D814; cross-checked by tools/emotion_export.py's own parse

/// Canon uploads 0x100 bytes per face's left half (the queued transfer size
/// is off_801CD6C, asm00_2.s:27414-27416) and 0x80 bytes for the SHARED right
/// half dword_872D914 = bank +0x100 (asm00_2.s:27418-27423), which is every
/// face's 16x16 object; slot 0's own copy of those bytes in the bank is where
/// the exporter finds them.
const LEFT_HALF_LEN: usize = 0x100; // canon: off_801CD6C (asm00_2.s:27605), the left-half transfer size
const RIGHT_HALF: (usize, usize) = (0x100, 0x80); // canon: dword_872D914 = dword_872D814+0x100 (asm00_2.s:27418) and off_801CD70's 0x80 (asm00_2.s:27423-27426)

pub struct Emotion {
    wide: Option<SpriteVram>,
    narrow: Option<SpriteVram>,
}

impl Emotion {
    /// `emotion` is the face slot: canon's off_801CD08 index, also the value
    /// its draw gate checks for the 5/6 skip. Values 5 and 6 build no
    /// sprites at all, mirroring canon's `beq locret_801CE14`
    /// (asm00_2.s:27648-27652). Slots >= 23 are unreachable from the game's
    /// own emotion states (byte_801E6F4/byte_801E700 only emit 0..22); canon
    /// has no bound check here -- its pointer load would just run off the
    /// table -- so this port falls back to the calm slot rather than read
    /// past the asset.
    pub fn new(data: &'static [u8], emotion: u8) -> Self {
        assert_eq!(&data[0..4], b"BNEM", "not a BNEM asset");
        let at = |o: usize| u32::from_le_bytes(data[o..o + 4].try_into().unwrap()) as usize;
        assert_eq!(at(0x04), 2, "BNEM asset version, v2 = full bank + per-face palettes");
        let (bank_off, pal_off) = (at(0x08), at(0x0c));
        let bank_len = u32::from_le_bytes(data[bank_off..bank_off + 4].try_into().unwrap()) as usize;
        let bank = &data[bank_off + 4..bank_off + 4 + bank_len];
        let pal_len = u32::from_le_bytes(data[pal_off..pal_off + 4].try_into().unwrap()) as usize;
        let palettes = &data[pal_off + 4..pal_off + 4 + pal_len];

        let slot = usize::from(emotion);
        let face = if slot < FACE_SLOTS {
            FACE_INDEX[slot] as usize
        } else {
            FACE_INDEX[0] as usize
        };

        // Per-face palette: sub_801CB38 queues `lsl r0,r4,#5` bytes from
        // dword_872F114 (asm00_2.s:27449-27452) -- slot * 32, one 16-colour
        // palette per emotion, the anger face's red among them.
        let pal = slot * 32;
        let mut colours = [Rgb15::new(0); 16];
        for (i, c) in colours.iter_mut().enumerate() {
            let o = pal + i * 2;
            *c = Rgb15::new(u16::from_le_bytes(palettes[o..o + 2].try_into().unwrap()));
        }
        let palette = PaletteVramSingle::try_allocate_shared(&Palette16::new(colours))
            .expect("emotion palette should fit in vram");

        let left = &bank[face..face + LEFT_HALF_LEN];
        let right = &bank[RIGHT_HALF.0..RIGHT_HALF.0 + RIGHT_HALF.1];
        let split = WIDE_TILES * 32;
        Self {
            wide: Some(DynamicSprite16::from_bytes(Size::S32x16, &left[..split]).to_vram(palette.clone())),
            narrow: Some(DynamicSprite16::from_bytes(Size::S16x16, right).to_vram(palette)),
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
            if let Some(sprite) = sprite {
                Object::new(sprite.clone())
                    .set_priority(Priority::P2)
                    .set_pos((at.0 + x_offset, at.1))
                    .show(frame);
            }
        }
    }
}
