//! The chip selection window that opens when the custom gauge fills.
//!
//! The game draws it on BG3 -- char block 2, screen block 31 (sub_801DA24,
//! asm00_2.s:29030) -- from the 15x20 map byte_86E625C in palette bank 9,
//! and slides it in by scrolling from 0x78 to 0 at 0xc a frame, and out the
//! same way (sub_8026B04, sub_8026BF4; asm03_0.s:882, 1026). The tiles are
//! dword_86E1D38, exported with the map by tools/custom_export.py.
//!
//! Only the window and its slide are built. The cursor over the five slots
//! and OK, the chip records behind the slots and the chip art the game
//! draws into the placeholder cells are located (custMenuSomeHandler_8028B74,
//! unk_20365C0, byte_8725894) but not yet reproduced, so for now the window
//! opens, waits, and closes on A or Start as pressing OK does.

use agb::display::Priority;
use agb::display::tiled::{
    RegularBackground, RegularBackgroundSize, TileEffect, TileFormat, TileSet, TileSetting,
};
use agb::display::{GraphicsFrame, Palette16, Rgb15};
use agb::input::{Button, ButtonController};

const MAGIC: &[u8; 4] = b"BNCW";
const MAP_W: usize = 15;
const MAP_H: usize = 20;
const SLIDE_FROM: i32 = 0x78;
const SLIDE_STEP: i32 = 0xc;
/// The window's palette bank; the results windows use 9-11 too, so the
/// bank is set on open and the results' restored on close.
pub const BANK: u8 = 9;

pub struct CustomAssets {
    tiles: TileSet,
    map: &'static [u8],
    palette: &'static [u8],
}

enum Phase {
    Opening { x: i32 },
    Open,
    Closing { x: i32 },
    Done,
}

pub struct Custom<'a> {
    bg: RegularBackground,
    tiles: &'a TileSet,
    map: &'a [u8],
    /// Columns drawn so far; the rest of the map is left as tile 0.
    revealed: usize,
    phase: Phase,
}

impl CustomAssets {
    pub fn new(data: &'static [u8]) -> Self {
        assert_eq!(&data[0..4], MAGIC, "not a BNCW asset");
        let at = |o: usize| u32::from_le_bytes(data[o..o + 4].try_into().unwrap()) as usize;
        let (t, m, p) = (at(0x08), at(0x0c), at(0x10));
        let len = at(t);
        let tiles = &data[t + 4..t + 4 + len];
        assert_eq!(tiles.as_ptr() as usize % 4, 0, "tile data must be word aligned");
        let (w, h) = (at(m), at(m + 4));
        assert_eq!((w, h), (MAP_W, MAP_H), "unexpected chip window map size");
        Self {
            // SAFETY: alignment asserted above; the exporter emits whole tiles.
            tiles: unsafe { TileSet::new(tiles, TileFormat::FourBpp) },
            map: &data[m + 8..m + 8 + w * h * 2],
            palette: &data[p..p + 96],
        }
    }

    /// One of the three colour variants, for background bank 9.
    pub fn palette(&self, variant: usize) -> Palette16 {
        let mut colours = [Rgb15::new(0); 16];
        for (i, slot) in colours.iter_mut().enumerate() {
            let o = variant * 32 + i * 2;
            *slot = Rgb15::new(u16::from_le_bytes(
                self.palette[o..o + 2].try_into().unwrap(),
            ));
        }
        Palette16::new(colours)
    }

    pub fn open(&self) -> Custom<'_> {
        let mut bg = RegularBackground::new(
            Priority::P0,
            RegularBackgroundSize::Background32x32,
            TileFormat::FourBpp,
        );
        bg.set_scroll_pos((SLIDE_FROM, 0));
        let mut custom = Custom {
            bg,
            tiles: &self.tiles,
            map: self.map,
            revealed: 0,
            phase: Phase::Opening { x: SLIDE_FROM },
        };
        custom.reveal(SLIDE_FROM);
        custom
    }
}

impl Custom<'_> {
    /// Columns still off the left edge at scroll `x` are left blank and
    /// drawn as the slide brings them on, the way the game copies them in
    /// from its staging buffer (sub_8026B04); on a 32-tile-wide layer a
    /// column more than two tiles past the edge would otherwise wrap round
    /// and show at the right of the screen.
    fn reveal(&mut self, x: i32) {
        while self.revealed < MAP_W && (self.revealed as i32) * 8 + 16 >= x {
            self.set_column(self.revealed, true);
            self.revealed += 1;
        }
    }

    /// The slide-out clears the columns the window has vacated with the
    /// blank tile (byte_8026C88; sub_8026BF4).
    fn vacate(&mut self, x: i32) {
        while self.revealed > 0 && ((self.revealed - 1) as i32) * 8 + 16 < x {
            self.revealed -= 1;
            self.set_column(self.revealed, false);
        }
    }

    fn set_column(&mut self, col: usize, visible: bool) {
        for row in 0..MAP_H {
            let i = row * MAP_W + col;
            let e = if visible {
                u16::from_le_bytes(self.map[i * 2..i * 2 + 2].try_into().unwrap())
            } else {
                0
            };
            self.bg.set_tile(
                (col as i32, row as i32),
                self.tiles,
                TileSetting::new(
                    e & 0x3ff,
                    TileEffect::new(e & 0x400 != 0, e & 0x800 != 0, (e >> 12) as u8),
                ),
            );
        }
    }

    /// Advance a frame. Returns true once the window has slid back out.
    pub fn update(&mut self, input: &ButtonController) -> bool {
        self.phase = match self.phase {
            Phase::Opening { x } if x > 0 => {
                let x = (x - SLIDE_STEP).max(0);
                self.bg.set_scroll_pos((x, 0));
                self.reveal(x);
                Phase::Opening { x }
            }
            Phase::Opening { .. } => Phase::Open,
            // Start jumps the cursor to OK and A confirms it
            // (custMenuSomeHandler_8028B74, asm03_0.s:5160, 5276); with no
            // cursor yet, either closes the window.
            Phase::Open
                if input.is_just_pressed(Button::A) || input.is_just_pressed(Button::Start) =>
            {
                Phase::Closing { x: 0 }
            }
            Phase::Open => Phase::Open,
            Phase::Closing { x } if x < SLIDE_FROM => {
                let x = (x + SLIDE_STEP).min(SLIDE_FROM);
                self.bg.set_scroll_pos((x, 0));
                self.vacate(x);
                Phase::Closing { x }
            }
            Phase::Closing { .. } => Phase::Done,
            Phase::Done => Phase::Done,
        };
        matches!(self.phase, Phase::Done)
    }

    pub fn show(&self, frame: &mut GraphicsFrame) {
        self.bg.show(frame);
    }
}
