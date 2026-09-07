//! The HP box the real ROM draws on BG3, in tiles rather than sprites.
//!
//! Each digit is two tiles stacked and the set steps by two tiles per digit,
//! so digit six is twelve tiles past digit zero. The box is a left cap, four
//! digit slots filled right-aligned with a blank tile in the leading
//! positions, and a right cap, all in one palette bank. Read off a live
//! battle's BG3 map, whose top row is cap, blank, blank, six, zero, cap for an
//! HP of 60.

use agb::display::tiled::{
    RegularBackground, RegularBackgroundSize, TileEffect, TileFormat, TileSet, TileSetting,
};
use agb::display::{GraphicsFrame, Palette16, Priority, Rgb15};

/// Two-tile pairs within the asset: ten digits, then the blank slot and the
/// cap.
const BLANK_PAIR: u16 = 10;
const CAP_PAIR: u16 = 11;
/// Digit slots between the two caps.
const SLOTS: u32 = 4;
/// The palette bank the box draws in. The field uses 0-8 and the results
/// windows 9-11, so this one is free and is the real ROM's own choice.
pub const BANK: u8 = 13;

pub struct HudTiles {
    bg: RegularBackground,
    tiles: TileSet,
    palette: Palette16,
    shown: Option<u16>,
}

impl HudTiles {
    pub fn new(data: &'static [u8]) -> Self {
        assert_eq!(&data[0..4], b"BNHT", "not a BNHT asset");
        let at = |o: usize| u32::from_le_bytes(data[o..o + 4].try_into().unwrap()) as usize;
        let (t, p) = (at(0x08), at(0x0c));

        let len = u32::from_le_bytes(data[t..t + 4].try_into().unwrap()) as usize;
        let tiles = &data[t + 4..t + 4 + len];
        assert_eq!(
            tiles.as_ptr() as usize % 4,
            0,
            "tile data must be word aligned"
        );

        let mut colours = [Rgb15::new(0); 16];
        for (i, slot) in colours.iter_mut().enumerate() {
            let o = p + i * 2;
            *slot = Rgb15::new(u16::from_le_bytes(data[o..o + 2].try_into().unwrap()));
        }

        Self {
            bg: RegularBackground::new(
                Priority::P1,
                RegularBackgroundSize::Background32x32,
                TileFormat::FourBpp,
            ),
            // SAFETY: alignment asserted above, and the length is a whole
            // number of 4bpp tiles by construction of the exporter.
            tiles: unsafe { TileSet::new(tiles, TileFormat::FourBpp) },
            palette: Palette16::new(colours),
            shown: None,
        }
    }

    pub fn palette(&self) -> Palette16 {
        self.palette.clone()
    }

    /// Repaint the box when the number changes. The digits are laid out
    /// right-aligned, with the leading slots blank rather than zeroed.
    pub fn set_hp(&mut self, hp: u16) {
        if self.shown == Some(hp) {
            return;
        }
        self.shown = Some(hp);
        self.cell(0, CAP_PAIR);
        self.cell(1 + SLOTS, CAP_PAIR);
        let mut left = hp;
        for slot in (0..SLOTS).rev() {
            let pair = if left == 0 && slot + 1 != SLOTS {
                BLANK_PAIR
            } else {
                (left % 10) as u16
            };
            left /= 10;
            self.cell(1 + slot, pair);
        }
    }

    /// Paint one two-tile column of the box.
    fn cell(&mut self, col: u32, pair: u16) {
        for half in 0..2u16 {
            self.bg.set_tile(
                (col as i32, half as i32),
                &self.tiles,
                TileSetting::new(pair * 2 + half, TileEffect::new(false, false, BANK)),
            );
        }
    }

    pub fn show(&self, frame: &mut GraphicsFrame) {
        self.bg.show(frame);
    }
}
