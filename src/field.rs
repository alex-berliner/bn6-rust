//! The 6x3 battle field.
//!
//! Geometry comes from `object_getCoordinatesForPanels` in the disassembly:
//! panels are 40x24 px with `X = panelX * 40 - 140`, `Y = panelY * 24 - 20`
//! relative to the field centre. Resolved against the tile layout that
//! `sub_800C01C` produces, panel centres land on screen at
//! `x = col * 40 - 20`, `y = row * 24 + 60`.

use agb::display::Priority;
use agb::display::tiled::{
    RegularBackground, RegularBackgroundSize, TileEffect, TileFormat, TileSet, TileSetting,
};
use agb::display::{Palette16, Rgb15};

/// Tile column for each panel column, indexed by the 1-based column.
const TILE_COLS: [i32; 8] = [-5, 0, 5, 10, 15, 20, 25, 30];

const PANEL_TW: usize = 5;
const PANEL_TH: usize = 3;

/// Panel types, in the order the tilemap stores them. The disassembly has no
/// enum for these; the names come from what each variant actually draws.
pub const PANEL_HOLE: usize = 0;
pub const PANEL_BROKEN: usize = 1;
pub const PANEL_NORMAL: usize = 2;
pub const PANEL_CRACKED: usize = 3;
pub const PANEL_POISON: usize = 4;

pub struct Field {
    tiles: TileSet,
    tilemap: &'static [u8],
    palette: &'static [u8],
}

impl Field {
    pub fn new(data: &'static [u8]) -> Self {
        assert_eq!(&data[0..4], b"BNFD", "not a BNFD asset");
        let at = |o: usize| u32::from_le_bytes(data[o..o + 4].try_into().unwrap()) as usize;
        let (t, m, p) = (at(0x08), at(0x0c), at(0x10));

        let tiles_len = u32::from_le_bytes(data[t..t + 4].try_into().unwrap()) as usize;
        let tiles = &data[t + 4..t + 4 + tiles_len];
        assert_eq!(tiles.as_ptr() as usize % 4, 0, "tile data must be word aligned");

        let variants = u32::from_le_bytes(data[m..m + 4].try_into().unwrap()) as usize;

        Self {
            // SAFETY: alignment asserted above, and the length is a whole
            // number of 4bpp tiles by construction of the exporter.
            tiles: unsafe { TileSet::new(tiles, TileFormat::FourBpp) },
            tilemap: &data[m + 4..m + 4 + variants * 32],
            palette: &data[p..p + 32 * 16],
        }
    }

    /// The field's 16 background palette banks.
    pub fn palettes(&self) -> [Palette16; 16] {
        core::array::from_fn(|bank| {
            let mut colours = [Rgb15::new(0); 16];
            for (i, slot) in colours.iter_mut().enumerate() {
                let o = bank * 32 + i * 2;
                *slot = Rgb15::new(u16::from_le_bytes(
                    self.palette[o..o + 2].try_into().unwrap(),
                ));
            }
            Palette16::new(colours)
        })
    }

    pub fn background(&self, panel_type: usize) -> RegularBackground {
        let mut bg = RegularBackground::new(
            Priority::P3,
            RegularBackgroundSize::Background32x32,
            TileFormat::FourBpp,
        );

        for row in 1..=3usize {
            for col in 1..=6usize {
                // Columns 1-3 are the player's blue half, 4-6 the enemy's red.
                let side = if col <= 3 { 1 } else { 0 };
                let variant = 6 * panel_type + 3 * side + (row - 1);
                let entries = &self.tilemap[variant * 32..variant * 32 + 30];
                let tile_x = TILE_COLS[col];
                let tile_y = 3 * row as i32 + 6;

                for i in 0..PANEL_TW * PANEL_TH {
                    let e = u16::from_le_bytes(entries[i * 2..i * 2 + 2].try_into().unwrap());
                    let setting = TileSetting::new(
                        e & 0x3ff,
                        TileEffect::new(e & 0x400 != 0, e & 0x800 != 0, (e >> 12) as u8),
                    );
                    let pos = (
                        tile_x + (i % PANEL_TW) as i32,
                        tile_y + (i / PANEL_TW) as i32,
                    );
                    if pos.0 >= 0 {
                        bg.set_tile(pos, &self.tiles, setting);
                    }
                }
            }
        }

        bg
    }
}

/// Screen position of the centre of a panel, for 1-based `(col, row)`.
pub fn panel_centre(col: i32, row: i32) -> (i32, i32) {
    (col * 40 - 20, row * 24 + 60)
}
