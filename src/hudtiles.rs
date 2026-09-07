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
/// The CUSTOM gauge, in the same asset after the HP tiles. Its art is loaded
/// at VRAM tile 0x222 on the real ROM, so the asset index of VRAM tile t is
/// GAUGE_FIRST + (t - 0x22b). The bar is one tile row: an end cap, six body
/// cells, the four-cell L-or-R marker, six more body cells and a mirrored end
/// cap, with the CUSTOM label on the row above it.
const GAUGE_FIRST: u16 = 50;
const CAP_TOP: u16 = GAUGE_FIRST;
const CAP_BOTTOM: u16 = GAUGE_FIRST + 1;
const FILLER: u16 = GAUGE_FIRST + 2;
const CUSTOM_TEXT: u16 = GAUGE_FIRST + 3;
const BAR: u16 = GAUGE_FIRST + 7;
/// The marker is cyan while the gauge is filling and orange once it is full,
/// which is the swap the gauge shows instead of any proportional readout.
const MARKER_WAITING: u16 = GAUGE_FIRST + 11;
const MARKER_READY: u16 = GAUGE_FIRST + 15;
/// Columns the gauge spans, and how many of them carry bar body.
const GAUGE_COL: u32 = 6;
const GAUGE_CELLS: u32 = 18;
const BAR_CELLS: u32 = 12;
/// The palette bank the gauge draws in on the real ROM.
pub const GAUGE_BANK: u8 = 9;
/// A blank tile the exporter appends, for clearing cells: tile 0 of this asset
/// is the top half of digit zero and cannot serve as one.
const BLANK_TILE: u16 = 69;

/// The palette bank the box draws in. The field uses 0-8 and the results
/// windows 9-11, so this one is free and is the real ROM's own choice.
pub const BANK: u8 = 13;

pub struct HudTiles {
    bg: RegularBackground,
    tiles: TileSet,
    palette: Palette16,
    gauge_palette: Palette16,
    shown: Option<u16>,
    gauge_shown: Option<u32>,
    /// Whether the chip menu is up. The real ROM keeps the HP box on screen
    /// then but redraws it fifteen tile columns over, beside the window and
    /// above the field, and drops the gauge, whose place the window takes.
    menu: bool,
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
        let mut gauge = [Rgb15::new(0); 16];
        for (i, (slot, g)) in colours.iter_mut().zip(gauge.iter_mut()).enumerate() {
            let o = p + i * 2;
            *slot = Rgb15::new(u16::from_le_bytes(data[o..o + 2].try_into().unwrap()));
            *g = Rgb15::new(u16::from_le_bytes(data[o + 32..o + 34].try_into().unwrap()));
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
            gauge_palette: Palette16::new(gauge),
            shown: None,
            gauge_shown: None,
            menu: false,
        }
    }

    pub fn palette(&self) -> Palette16 {
        self.palette.clone()
    }

    pub fn gauge_palette(&self) -> Palette16 {
        self.gauge_palette.clone()
    }

    /// Repaint the CUSTOM label and the bar. `filled` is the gauge's value
    /// over its full value; the marker turns from cyan to orange at one.
    /// NOTE: only the full bar is verified against the real ROM, because the
    /// gauge drains only when the custom window opens and that window
    /// replaces this whole layer, so a draining bar never shows on its own.
    /// The empty body cell is drawn with the label row's filler tile, which is
    /// a guess.
    pub fn set_gauge(&mut self, filled: u16, full: u16) {
        if self.menu {
            return;
        }
        let lit = (u32::from(filled) * BAR_CELLS / u32::from(full.max(1))).min(BAR_CELLS);
        if self.gauge_shown == Some(lit) {
            return;
        }
        self.gauge_shown = Some(lit);
        let ready = lit >= BAR_CELLS;
        let mut body = 0;
        for i in 0..GAUGE_CELLS {
            let col = GAUGE_COL + i;
            let last = i + 1 == GAUGE_CELLS;
            let (top, bottom) = if i == 0 || last {
                (CAP_TOP, CAP_BOTTOM)
            } else if (7..11).contains(&i) {
                let m = if ready { MARKER_READY } else { MARKER_WAITING };
                (CUSTOM_TEXT + (i as u16 - 7), m + (i as u16 - 7))
            } else {
                let cell = if body < lit { BAR } else { FILLER };
                body += 1;
                (FILLER, cell)
            };
            self.gauge_cell(col, 0, top, last);
            self.gauge_cell(col, 1, bottom, last);
        }
    }

    fn gauge_cell(&mut self, col: u32, row: i32, tile: u16, hflip: bool) {
        self.bg.set_tile(
            (col as i32, row),
            &self.tiles,
            TileSetting::new(tile, TileEffect::new(hflip, false, GAUGE_BANK)),
        );
    }

    /// Move the box aside for the chip menu, or bring it back.
    pub fn set_menu(&mut self, menu: bool) {
        if self.menu == menu {
            return;
        }
        self.menu = menu;
        self.shown = None;
        self.gauge_shown = None;
        for col in 0..32 {
            for row in 0..2 {
                self.bg.set_tile(
                    (col, row),
                    &self.tiles,
                    TileSetting::new(BLANK_TILE, TileEffect::new(false, false, BANK)),
                );
            }
        }
    }

    /// Where the HP box starts, in tile columns.
    fn hp_col(&self) -> u32 {
        if self.menu {
            15
        } else {
            0
        }
    }

    /// Repaint the box when the number changes. The digits are laid out
    /// right-aligned, with the leading slots blank rather than zeroed.
    pub fn set_hp(&mut self, hp: u16) {
        if self.shown == Some(hp) {
            return;
        }
        self.shown = Some(hp);
        let base = self.hp_col();
        self.cell(base, CAP_PAIR);
        self.cell(base + 1 + SLOTS, CAP_PAIR);
        let mut left = hp;
        for slot in (0..SLOTS).rev() {
            let pair = if left == 0 && slot + 1 != SLOTS {
                BLANK_PAIR
            } else {
                (left % 10) as u16
            };
            left /= 10;
            self.cell(base + 1 + slot, pair);
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
