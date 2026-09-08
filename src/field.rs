//! The 6x3 battle field.
//!
//! Geometry comes from `object_getCoordinatesForPanels` in the disassembly:
//! panels are 40x24 px with `X = panelX * 40 - 140`, `Y = panelY * 24 - 20`
//! relative to the field centre. Resolved against the tile layout that
//! `sub_800C01C` produces, panel centres land on screen at
//! `x = col * 40 - 20`, `y = row * 24 + 60`.

use alloc::vec::Vec;

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
/// enum, but the setters pin the values: `object_breakPanel` writes 1 and
/// `object_crackPanel` writes 3 (asm/object.s:2301, 2198), and a broken panel
/// regenerates to 2 (asm/object.s:1450). The game has further types beyond
/// these -- grass, ice, currents -- but this tilemap only carries five.
pub const PANEL_HOLE: usize = 0;
pub const PANEL_BROKEN: usize = 1;
pub const PANEL_NORMAL: usize = 2;
pub const PANEL_CRACKED: usize = 3;
/// Not driven by anything yet; poison panels damage whoever stands on them.
#[allow(dead_code)]
pub const PANEL_POISON: usize = 4;

/// The two highlight overlays follow the panel variants in the tilemap: a
/// solid block of one tile each, drawn over a panel for a single frame when
/// something asks for a flash (sub_800C0BA, asm/object.s:1121).
const HIGHLIGHT_FIRST: usize = 32;
/// The front lip: one tilemap row of five tiles per panel column, sitting in
/// the row below the bottom panels, in that column's own side palette. The
/// real ROM has it at screen block 30's row 18, and it is the six pixels the
/// field was short of at y 144..149. One variant per side.
const LIP_FIRST: usize = HIGHLIGHT_FIRST + 2;

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
        assert_eq!(
            tiles.as_ptr() as usize % 4,
            0,
            "tile data must be word aligned"
        );

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

    pub fn background(&self, panels: &Panels) -> RegularBackground {
        // The real ROM has the field on BG2 at priority 2 with the backdrop
        // behind it on BG1 at priority 3.
        let mut bg = RegularBackground::new(
            Priority::P2,
            RegularBackgroundSize::Background32x32,
            TileFormat::FourBpp,
        );
        for row in 1..=ROWS {
            for col in 1..=COLS {
                self.draw_panel(
                    &mut bg,
                    col,
                    row,
                    panels.get(col, row),
                    panels.enemy_owned(col, row),
                );
            }
        }
        for col in 1..=COLS {
            self.draw_lip(&mut bg, col, panels.enemy_owned(col, ROWS));
        }
        bg
    }

    /// Paint one of the highlight overlays over a panel.
    pub fn draw_highlight(&self, bg: &mut RegularBackground, col: i32, row: i32, which: usize) {
        self.draw_variant(bg, col, row, HIGHLIGHT_FIRST + which);
    }

    /// Repaint one panel's 5x3 tile block, so a panel that changes state does
    /// not cost a redraw of the whole field.
    pub fn draw_panel(
        &self,
        bg: &mut RegularBackground,
        col: i32,
        row: i32,
        panel_type: usize,
        enemy_owned: bool,
    ) {
        // The two sides share tiles and differ only by palette bank; against
        // the real ROM the player's half is the red one.
        let side = usize::from(enemy_owned);
        self.draw_variant(bg, col, row, 6 * panel_type + 3 * side + (row as usize - 1));
    }

    /// Paint the front lip under one column of the bottom row.
    pub fn draw_lip(&self, bg: &mut RegularBackground, col: i32, enemy_owned: bool) {
        let variant = LIP_FIRST + usize::from(enemy_owned);
        let entries = &self.tilemap[variant * 32..variant * 32 + PANEL_TW * 2];
        let tile_x = TILE_COLS[col as usize];
        let tile_y = 3 * (ROWS + 1) + 6;
        for i in 0..PANEL_TW {
            let e = u16::from_le_bytes(entries[i * 2..i * 2 + 2].try_into().unwrap());
            let setting = TileSetting::new(
                e & 0x3ff,
                TileEffect::new(e & 0x400 != 0, e & 0x800 != 0, (e >> 12) as u8),
            );
            let pos = (tile_x + i as i32, tile_y);
            if pos.0 >= 0 {
                bg.set_tile(pos, &self.tiles, setting);
            }
        }
    }

    fn draw_variant(&self, bg: &mut RegularBackground, col: i32, row: i32, variant: usize) {
        let entries = &self.tilemap[variant * 32..variant * 32 + 30];
        let tile_x = TILE_COLS[col as usize];
        let tile_y = 3 * row + 6;

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

/// How long a broken panel takes to come back, from `sub_800C488`
/// (asm/object.s:1541). The shorter 0x1e0 applies only in battle mode 1.
const REGEN_FRAMES: u16 = 0x258; // provenance: derived -- sub_800C488, asm/object.s:1541
/// Over the last second the panel alternates between drawing itself broken and
/// normal, warning that it is about to return (asm/object.s:1458).
const BLINK_FRAMES: u16 = 60; // provenance: derived -- asm/object.s:1458

const PANEL_COUNT: usize = (COLS * ROWS) as usize;

fn index(col: i32, row: i32) -> usize {
    (row as usize - 1) * COLS as usize + (col as usize - 1)
}

/// State of every panel on the field, indexed by 1-based `(col, row)`.
///
/// `Type` is what the panel is; `Animation` is what gets drawn, and the two
/// differ while a broken panel blinks (PanelData.inc:6, and the per-frame tick
/// in `sub_800C380`, asm/object.s:1404).
pub struct Panels {
    types: [u8; PANEL_COUNT],
    animation: [u8; PANEL_COUNT],
    regen: [u16; PANEL_COUNT],
    occupied_last: u32,
    dirty: u32,
    /// One-shot highlight requests, as PanelData's Unk_01: set for a frame,
    /// drawn, cleared (asm/object.s:2552, 1732). Value is 1 + overlay index.
    flash: [u8; PANEL_COUNT],
    flash_last: [u8; PANEL_COUNT],
    /// Which side each panel belongs to: false the player's, true the
    /// enemy's. Columns 1-3 start the player's and 4-6 the enemy's, and
    /// AreaGrab moves the boundary a column at a time
    /// (sub_80E0754, asm31.s:85444).
    enemy_owned: [bool; PANEL_COUNT],
}

impl Panels {
    pub fn new(fill: usize) -> Self {
        Self {
            types: [fill as u8; PANEL_COUNT],
            animation: [fill as u8; PANEL_COUNT],
            regen: [REGEN_FRAMES; PANEL_COUNT],
            occupied_last: 0,
            dirty: 0,
            flash: [0; PANEL_COUNT],
            flash_last: [0; PANEL_COUNT],
            enemy_owned: core::array::from_fn(|i| i % COLS as usize >= 3),
        }
    }

    /// Whose half this panel is on.
    pub fn enemy_owned(&self, col: i32, row: i32) -> bool {
        self.enemy_owned[index(col, row)]
    }

    /// The columns a side may stand on: the panels it owns, which are always
    /// a contiguous run from its own edge.
    pub fn half(&self, enemy_side: bool, row: i32) -> (i32, i32) {
        let owned = |col| self.enemy_owned(col, row) == enemy_side;
        let mut lo = 1;
        let mut hi = COLS;
        while lo < COLS && !owned(lo) {
            lo += 1;
        }
        while hi > lo && !owned(hi) {
            hi -= 1;
        }
        (lo, hi)
    }

    /// The panels a side may NOT stand on because the other side owns them.
    pub fn other_half(&self, enemy_side: bool) -> u32 {
        let mut mask = 0;
        for row in 1..=ROWS {
            for col in 1..=COLS {
                if self.enemy_owned(col, row) != enemy_side {
                    mask |= panel_bit(col, row);
                }
            }
        }
        mask
    }

    /// Take the enemy's front-most column for the player, a row at a time,
    /// as AreaGrab does; a panel someone is standing on cannot be taken.
    /// Returns the panels that changed hands.
    pub fn steal_column(&mut self, occupied: u32) -> Vec<(i32, i32)> {
        let mut taken = Vec::new();
        for row in 1..=ROWS {
            let (lo, _) = self.half(true, row);
            if lo <= COLS
                && self.enemy_owned(lo, row)
                && lo > 1
                && occupied & panel_bit(lo, row) == 0
            {
                self.enemy_owned[index(lo, row)] = false;
                self.dirty |= panel_bit(lo, row);
                taken.push((lo, row));
            }
        }
        taken
    }

    pub fn get(&self, col: i32, row: i32) -> usize {
        self.types[index(col, row)] as usize
    }

    /// What to draw for this panel, which is not always its type.
    pub fn animation(&self, col: i32, row: i32) -> usize {
        self.animation[index(col, row)] as usize
    }

    pub fn set(&mut self, col: i32, row: i32, panel_type: usize) {
        let i = index(col, row);
        self.types[i] = panel_type as u8;
        self.regen[i] = REGEN_FRAMES;
    }

    /// Crack a panel, or break it outright if it was cracked already, which is
    /// what `object_crackPanel` does on a second hit (asm/object.s:2206).
    pub fn crack(&mut self, col: i32, row: i32) {
        let next = if self.get(col, row) == PANEL_CRACKED {
            PANEL_BROKEN
        } else {
            PANEL_CRACKED
        };
        self.set(col, row, next);
    }

    /// Ask for a panel to draw as highlight overlay `which` this frame only.
    pub fn highlight(&mut self, col: i32, row: i32, which: usize) {
        self.flash[index(col, row)] = 1 + which as u8;
    }

    /// The overlay a panel should draw this frame instead of itself, if any.
    pub fn flashing(&self, col: i32, row: i32) -> Option<usize> {
        match self.flash_last[index(col, row)] {
            0 => None,
            f => Some(f as usize - 1),
        }
    }

    /// Advance one frame. `occupied` is a bitmask of panels a navi is standing
    /// on or has reserved as the target of a warp.
    pub fn update(&mut self, occupied: u32) {
        for i in 0..PANEL_COUNT {
            let bit = 1 << i;
            // A flash lasts the one frame it was asked for; both edges dirty.
            if self.flash[i] != self.flash_last[i] {
                self.flash_last[i] = self.flash[i];
                self.dirty |= bit;
            }
            self.flash[i] = 0;
            let mut anim = self.types[i];
            match self.types[i] as usize {
                PANEL_HOLE => {}
                PANEL_BROKEN => {
                    self.regen[i] = self.regen[i].saturating_sub(1);
                    if self.regen[i] == 0 {
                        self.types[i] = PANEL_NORMAL as u8;
                        self.regen[i] = REGEN_FRAMES;
                        anim = PANEL_NORMAL as u8;
                    } else if self.regen[i] <= BLINK_FRAMES {
                        // Bit 1 of the countdown, so two frames of each.
                        anim = if self.regen[i] & 2 != 0 {
                            PANEL_NORMAL as u8
                        } else {
                            PANEL_BROKEN as u8
                        };
                    }
                }
                // A cracked panel gives way once whoever was standing on it
                // has gone, not when they arrive.
                PANEL_CRACKED => {
                    if self.occupied_last & bit != 0 && occupied & bit == 0 {
                        self.types[i] = PANEL_BROKEN as u8;
                        self.regen[i] = REGEN_FRAMES;
                        anim = PANEL_BROKEN as u8;
                    }
                }
                _ => {}
            }
            if anim != self.animation[i] {
                self.animation[i] = anim;
                self.dirty |= bit;
            }
        }
        self.occupied_last = occupied;
    }

    /// Take the mask of panels whose drawn appearance changed, so only those
    /// repaint. Iterate it with [`panels_in`].
    pub fn take_dirty(&mut self) -> u32 {
        core::mem::take(&mut self.dirty)
    }
}

/// Bit for one panel in an occupancy or dirty mask.
pub fn panel_bit(col: i32, row: i32) -> u32 {
    1 << index(col, row)
}

/// The 1-based `(col, row)` of every panel set in a mask.
pub fn panels_in(mask: u32) -> impl Iterator<Item = (i32, i32)> {
    (0..PANEL_COUNT)
        .filter(move |i| mask & (1 << i) != 0)
        .map(|i| {
            (
                (i % COLS as usize) as i32 + 1,
                (i / COLS as usize) as i32 + 1,
            )
        })
}

pub const COLS: i32 = 6;
pub const ROWS: i32 = 3;

/// Screen position of the centre of a panel, for 1-based `(col, row)`.
pub fn panel_centre(col: i32, row: i32) -> (i32, i32) {
    (col * 40 - 20, row * 24 + 60)
}

/// The half of the field a side owns. Columns 1-3 are the player's, 4-6 the
/// enemy's; a navi cannot leave its own half without a chip that grabs area.
/// The columns a side starts with, before any panel changes hands; live
/// bounds come from `Panels::half`.
pub fn half(enemy_side: bool) -> (i32, i32) {
    if enemy_side { (4, COLS) } else { (1, 3) }
}
