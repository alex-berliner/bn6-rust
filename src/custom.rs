//! The chip selection window that opens when the custom gauge fills.
//!
//! The game draws it on BG3 -- char block 2, screen block 31 (sub_801DA24,
//! asm00_2.s:29030) -- from the 15x20 map byte_86E625C in palette bank 9,
//! and slides it in by scrolling from 0x78 to 0 at 0xc a frame, and out the
//! same way (sub_8026B04, sub_8026BF4; asm03_0.s:882, 1026). The tiles are
//! dword_86E1D38, exported with the map by tools/custom_export.py.
//!
//! The map is a template: at load the game overwrites 27 rectangles with
//! running VRAM tile ids (byte_8027B2C via sub_8027CCC) that the chip
//! renderers then draw into. Those regions come out of the asset blank, with
//! the records, and are drawn here: the offered chips' icons and code
//! letters in the first slot row (sub_80281D4, sub_8028204), the empty icon
//! byte_86E601C where there is no chip (sub_8028310, asm03_0.s:4152), the
//! highlighted chip's card picture in its own palette (sub_80284E2,
//! asm03_0.s:4373: 0x540 bytes of picture and the chip palette into bank
//! 10), the live OK box (sub_8028320, asm03_0.s:4176) and the picks stacked
//! down the right-hand column (sub_80281D4 per row, asm03_0.s:3942). The
//! chip name, element and damage the card also carries are not drawn yet.
//!
//! The icons are bank 11 in the game's patch records, yet chip palettes
//! differ wholesale and nothing in the battle code stages bank 11
//! (unk_3001AC0 has writers only in asm03_2.s, asm33.s and asm36.s), so how
//! five icons share it was not resolved. Each slot gets its own bank here,
//! 11 to 15, holding its chip's palette, which draws every icon as authored.
//!
//! Input follows custMenuSomeHandler_8028B74 (asm03_0.s:5160): the cursor
//! walks the default slot ring (dword_802A7CC, asm03_0.s:9062: slots 0 to 4
//! then OK, no vertical moves while the second row is empty), Start jumps to
//! OK, A on a slot adds it (sub_8028D6C, asm03_0.s:5451: at most five, and
//! only while the pick fits the name-or-code rule of sub_8028E4C), B undoes
//! the last pick (sub_8029032, asm03_0.s:5892), and A on OK closes the window
//! with the picks as the hand (custMenuPressOK_8028D3A, asm03_0.s:5415).

use alloc::vec::Vec;

use agb::display::object::{DynamicSprite16, Object, PaletteVramSingle, Size, SpriteVram};
use agb::display::tiled::{
    RegularBackground, RegularBackgroundSize, TileEffect, TileFormat, TileSet, TileSetting,
};
use agb::display::{Graphics, GraphicsFrame, Palette16, Priority, Rgb15};
use agb::input::{Button, ButtonController, Tri};

use crate::chips::{Chip, PICTURE_TILES, WILDCARD};

const MAGIC: &[u8; 4] = b"BNCW";
const MAP_W: usize = 15;
const MAP_H: usize = 20;
const SLIDE_FROM: i32 = 0x78;
const SLIDE_STEP: i32 = 0xc;
/// The window's palette bank; the results windows use 9-11 too, so the
/// banks are set on open and the results' restored on close.
pub const BANK: u8 = 9;
/// The card picture's bank, holding the highlighted chip's palette.
const PICTURE_BANK: u8 = 10;
/// Slot `i`'s icon draws in bank `SLOT_BANK + i`; see the module comment.
const SLOT_BANK: u8 = 11;
/// Chips offered per window: the base count before Custom parts
/// (sub_802A40C, asm03_0.s:8650).
pub const OFFERED: usize = 5;
/// Picks per window (sub_8028D6C, asm03_0.s:5457).
pub const HAND_SIZE: usize = 5;

/// The cursor's index for the OK box; 0-4 are the offered slots
/// (S20364C0.inc:14, eS20364C0+7).
const OK: u8 = 0xa;
/// The bracket swaps tile and shrinks a pixel every 8 frames (sub_8028820,
/// asm03_0.s:4807: frame counter >> 3 & 1).
const BLINK_SHIFT: u32 = 3;

/// Indices into the asset's patch records, in byte_8027B2C's order.
const REGION_PICTURE: usize = 1;
const fn region_slot_icon(slot: usize) -> usize {
    5 + 2 * slot
}
const fn region_slot_code(slot: usize) -> usize {
    6 + 2 * slot
}
const REGION_OK: usize = 25;
const REGION_STACK: usize = 26;
/// The blank code glyph, dword_86E591C[0x1b] (sub_8028204).
const CODE_NONE: usize = 0x1b;

/// One bracket corner: offset from the cursor origin and its flips, per
/// blink phase. The game's tables (byte_80288B0 for a slot, byte_80288E4
/// for OK; asm03_0.s:4860, 4878) hold four words each of
/// `dy, 0, dx, flags` with 0x10 = horizontal flip, 0x20 = vertical.
struct Corner {
    dx: i32,
    dy: i32,
    hflip: bool,
    vflip: bool,
}

const fn corner(dx: i32, dy: i32, flags: u8) -> Corner {
    Corner {
        dx,
        dy,
        hflip: flags & 0x10 != 0,
        vflip: flags & 0x20 != 0,
    }
}

const SLOT_BRACKET: [[Corner; 4]; 2] = [
    [
        corner(0, 0, 0),
        corner(0xe, 0, 0x10),
        corner(0xe, 0xe, 0x30),
        corner(0, 0xe, 0x20),
    ],
    [
        corner(1, 1, 0),
        corner(0xc, 1, 0x10),
        corner(0xc, 0xc, 0x30),
        corner(1, 0xc, 0x20),
    ],
];
const OK_BRACKET: [[Corner; 4]; 2] = [
    [
        corner(1, 2, 0),
        corner(0x16, 2, 0x10),
        corner(0x16, 0x14, 0x30),
        corner(1, 0x14, 0x20),
    ],
    [
        corner(3, 4, 0),
        corner(0x14, 4, 0x10),
        corner(0x14, 0x12, 0x30),
        corner(3, 0x12, 0x20),
    ],
];

/// A patched rectangle of the map (byte_8027B2C record).
#[derive(Clone, Copy)]
struct Region {
    x: usize,
    y: usize,
    w: usize,
    h: usize,
    bank: u8,
    column_major: bool,
}

pub struct CustomAssets {
    tiles: TileSet,
    map: &'static [u8],
    palette: &'static [u8],
    regions: Vec<Region>,
    cursor_tiles: &'static [u8],
    cursor_palette: Palette16,
    empty_icon: TileSet,
    code_glyphs: TileSet,
    ok_box: TileSet,
}

enum Phase {
    Opening { x: i32 },
    Open,
    Closing { x: i32 },
    Done,
}

/// An offered chip and where it came from in the deck.
#[derive(Clone, Copy)]
pub struct Offer {
    pub chip: Chip,
    pub deck_index: usize,
}

pub struct Custom<'a> {
    assets: &'a CustomAssets,
    bg: RegularBackground,
    /// Columns drawn so far; the rest of the map is left as tile 0.
    revealed: usize,
    phase: Phase,
    /// The two blink phases of the corner tile.
    cursor: [SpriteVram; 2],
    cursor_at: u8,
    /// Counted while the window is open, as eS20364C0+0x40 is.
    frames: u32,
    slots: [Option<Offer>; OFFERED],
    /// Slot indices in pick order (eS20364C0+0x48).
    picks: Vec<usize>,
    pictured: Option<u16>,
}

impl CustomAssets {
    pub fn new(data: &'static [u8]) -> Self {
        assert_eq!(&data[0..4], MAGIC, "not a BNCW asset");
        let at = |o: usize| u32::from_le_bytes(data[o..o + 4].try_into().unwrap()) as usize;
        let (t, m, p, r, c, a) = (at(0x08), at(0x0c), at(0x10), at(0x14), at(0x18), at(0x1c));
        let len = at(t);
        let tiles = &data[t + 4..t + 4 + len];
        let (w, h) = (at(m), at(m + 4));
        assert_eq!((w, h), (MAP_W, MAP_H), "unexpected chip window map size");
        let regions = (0..at(r))
            .map(|i| {
                let e = &data[r + 4 + i * 8..r + 12 + i * 8];
                Region {
                    x: e[0] as usize,
                    y: e[1] as usize,
                    w: e[2] as usize,
                    h: e[3] as usize,
                    bank: e[4],
                    column_major: e[5] == 1,
                }
            })
            .collect();
        let tileset = |bytes: &'static [u8]| {
            assert_eq!(bytes.as_ptr() as usize % 4, 0, "tile data must be word aligned");
            // SAFETY: alignment asserted; the exporter emits whole tiles.
            unsafe { TileSet::new(bytes, TileFormat::FourBpp) }
        };
        Self {
            tiles: tileset(tiles),
            map: &data[m + 8..m + 8 + w * h * 2],
            palette: &data[p..p + 96],
            regions,
            cursor_tiles: &data[c..c + 64],
            cursor_palette: read_palette(&data[c + 64..c + 96]),
            empty_icon: tileset(&data[a..a + 0x80]),
            code_glyphs: tileset(&data[a + 0x80..a + 0x80 + 28 * 0x40]),
            ok_box: tileset(&data[a + 0x80 + 28 * 0x40..a + 0x80 + 28 * 0x40 + 0x100]),
        }
    }

    /// One of the three colour variants, for background bank 9.
    pub fn palette(&self, variant: usize) -> Palette16 {
        read_palette(&self.palette[variant * 32..variant * 32 + 32])
    }

    /// Open the window over the offered chips, at most one per slot.
    pub fn open(&self, offered: &[Offer], gfx: &Graphics) -> Custom<'_> {
        // BG3CNT 0x1f09 while the menu runs: priority 1, under the HUD
        // layer and over the actors (sub_801DA24, asm00_2.s:29038).
        let mut bg = RegularBackground::new(
            Priority::P1,
            RegularBackgroundSize::Background32x32,
            TileFormat::FourBpp,
        );
        bg.set_scroll_pos((SLIDE_FROM, 0));
        let palette = PaletteVramSingle::try_allocate_new(&self.cursor_palette)
            .expect("cursor palette should fit in vram");
        let cursor = [0, 1].map(|i| {
            DynamicSprite16::from_bytes(Size::S8x8, &self.cursor_tiles[i * 32..i * 32 + 32])
                .to_vram(palette.clone())
        });
        let mut slots = [None; OFFERED];
        for (slot, offer) in slots.iter_mut().zip(offered) {
            *slot = Some(*offer);
        }
        let mut custom = Custom {
            assets: self,
            bg,
            revealed: 0,
            phase: Phase::Opening { x: SLIDE_FROM },
            cursor,
            cursor_at: 0,
            frames: 0,
            slots,
            picks: Vec::new(),
            pictured: None,
        };
        gfx.set_background_palette(BANK, &self.palette(0));
        for (i, slot) in custom.slots.iter().enumerate() {
            if let Some(offer) = slot {
                gfx.set_background_palette(SLOT_BANK + i as u8, &read_palette(offer.chip.palette()));
            }
        }
        for slot in 0..OFFERED {
            custom.draw_slot(slot);
        }
        custom.draw_stack();
        custom.fill(REGION_OK, &self.ok_box, None);
        custom.draw_card(gfx);
        custom.reveal(SLIDE_FROM);
        custom
    }
}

fn read_palette(bytes: &[u8]) -> Palette16 {
    let mut colours = [Rgb15::new(0); 16];
    for (i, slot) in colours.iter_mut().enumerate() {
        *slot = Rgb15::new(u16::from_le_bytes(
            bytes[i * 2..i * 2 + 2].try_into().unwrap(),
        ));
    }
    Palette16::new(colours)
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
                u16::from_le_bytes(self.assets.map[i * 2..i * 2 + 2].try_into().unwrap())
            } else {
                0
            };
            // Cells inside the drawn regions are the renderers' and stay put
            // once revealed; the template only fills them when the column
            // first arrives, and they are already blank before that.
            if visible && self.in_region(col, row) {
                continue;
            }
            self.bg.set_tile(
                (col as i32, row as i32),
                &self.assets.tiles,
                TileSetting::new(
                    e & 0x3ff,
                    TileEffect::new(e & 0x400 != 0, e & 0x800 != 0, (e >> 12) as u8),
                ),
            );
        }
    }

    fn in_region(&self, col: usize, row: usize) -> bool {
        self.assets
            .regions
            .iter()
            .any(|r| col >= r.x && col < r.x + r.w && row >= r.y && row < r.y + r.h)
    }

    /// Draw a tileset over a region, tile k at its k-th cell in the
    /// record's order, in the record's bank unless one is given; `None`
    /// tiles blank it.
    fn fill(&mut self, region: usize, tiles: &TileSet, bank: Option<u8>) {
        let r = self.assets.regions[region];
        self.fill_from(r, tiles, 0, bank.unwrap_or(r.bank));
    }

    fn fill_from(&mut self, r: Region, tiles: &TileSet, first: u16, bank: u8) {
        for k in 0..r.w * r.h {
            let (dx, dy) = if r.column_major {
                (k / r.h, k % r.h)
            } else {
                (k % r.w, k / r.w)
            };
            self.bg.set_tile(
                ((r.x + dx) as i32, (r.y + dy) as i32),
                tiles,
                TileSetting::new(first + k as u16, TileEffect::new(false, false, bank)),
            );
        }
    }

    fn blank(&mut self, region: usize) {
        let r = self.assets.regions[region];
        let tiles = &self.assets.tiles;
        for dy in 0..r.h {
            for dx in 0..r.w {
                self.bg.set_tile(
                    ((r.x + dx) as i32, (r.y + dy) as i32),
                    tiles,
                    TileSetting::new(0, TileEffect::new(false, false, r.bank)),
                );
            }
        }
    }

    /// A slot's icon and code letter: the chip's while it is offered and
    /// unpicked, the empty icon and blank glyph otherwise (sub_8028310).
    fn draw_slot(&mut self, slot: usize) {
        let assets = self.assets;
        match self.slots[slot] {
            Some(offer) if !self.picks.contains(&slot) => {
                let icon = offer.chip.icon();
                self.fill(region_slot_icon(slot), &icon, Some(SLOT_BANK + slot as u8));
                let code = offer.chip.codes[0] as usize;
                let r = assets.regions[region_slot_code(slot)];
                self.fill_from(r, &assets.code_glyphs, (code * 2) as u16, r.bank);
            }
            _ => {
                self.fill(region_slot_icon(slot), &assets.empty_icon, None);
                let r = assets.regions[region_slot_code(slot)];
                self.fill_from(r, &assets.code_glyphs, (CODE_NONE * 2) as u16, r.bank);
            }
        }
    }

    /// The picks down the right-hand column, one icon per row, the empty
    /// icon below them (sub_80281D4 per row at open, asm03_0.s:3942).
    fn draw_stack(&mut self) {
        let assets = self.assets;
        let stack = assets.regions[REGION_STACK];
        for row in 0..HAND_SIZE {
            let cell = Region {
                x: stack.x,
                y: stack.y + row * 2,
                w: 2,
                h: 2,
                bank: stack.bank,
                column_major: false,
            };
            match self.picks.get(row).and_then(|&slot| self.slots[slot].map(|o| (slot, o))) {
                Some((slot, offer)) => {
                    let icon = offer.chip.icon();
                    self.fill_from(cell, &icon, 0, SLOT_BANK + slot as u8);
                }
                None => self.fill_from(cell, &assets.empty_icon, 0, stack.bank),
            }
        }
    }

    /// The card shows the chip under the cursor; on OK, or over an empty
    /// or picked slot, it is left as it was (sub_8028476 draws nothing for
    /// the empty slot types, asm03_0.s:4316).
    fn draw_card(&mut self, gfx: &Graphics) {
        let Some(offer) = self.highlighted() else {
            return;
        };
        if self.pictured == Some(offer.chip.id) {
            return;
        }
        self.pictured = Some(offer.chip.id);
        gfx.set_background_palette(PICTURE_BANK, &read_palette(offer.chip.palette()));
        let picture = offer.chip.picture();
        let r = self.assets.regions[REGION_PICTURE];
        debug_assert_eq!((r.w, r.h), PICTURE_TILES);
        self.fill_from(r, &picture, 0, PICTURE_BANK);
    }

    fn highlighted(&self) -> Option<Offer> {
        let slot = self.cursor_at as usize;
        if slot < OFFERED && !self.picks.contains(&slot) {
            self.slots[slot]
        } else {
            None
        }
    }

    /// Whether the chip in `slot` may join the picks so far: any chip
    /// first; then one sharing the picks' single name, or one whose code
    /// agrees with theirs, '*' agreeing with anything (sub_8028E4C,
    /// asm03_0.s:5595; the exact merge of codes across picks is read from
    /// the greying pass and may differ in corners).
    fn allowed(&self, slot: usize) -> bool {
        let Some(offer) = self.slots[slot] else {
            return false;
        };
        if self.picks.is_empty() {
            return true;
        }
        let picked: Vec<Chip> = self
            .picks
            .iter()
            .filter_map(|&s| self.slots[s].map(|o| o.chip))
            .collect();
        let name = picked[0].name();
        if picked.iter().all(|c| c.name() == name) && offer.chip.name() == name {
            return true;
        }
        let mut merged = None;
        for c in &picked {
            let code = c.codes[0];
            if code == WILDCARD {
                continue;
            }
            match merged {
                None => merged = Some(code),
                Some(m) if m == code => {}
                Some(_) => return false,
            }
        }
        let code = offer.chip.codes[0];
        code == WILDCARD || merged.is_none_or(|m| m == code)
    }

    /// Advance a frame. Returns true once the window has slid back out.
    pub fn update(&mut self, input: &ButtonController, gfx: &Graphics) -> bool {
        self.phase = match self.phase {
            Phase::Opening { x } if x > 0 => {
                let x = (x - SLIDE_STEP).max(0);
                self.bg.set_scroll_pos((x, 0));
                self.reveal(x);
                Phase::Opening { x }
            }
            Phase::Opening { .. } => Phase::Open,
            Phase::Open => {
                self.frames += 1;
                self.navigate(input, gfx)
            }
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

    /// One frame of the open window's input (custMenuSomeHandler_8028B74).
    fn navigate(&mut self, input: &ButtonController, gfx: &Graphics) -> Phase {
        match input.just_pressed_x_tri() {
            Tri::Positive => {
                self.cursor_at = match self.cursor_at {
                    4 => OK,
                    OK => 0,
                    i => i + 1,
                }
            }
            Tri::Negative => {
                self.cursor_at = match self.cursor_at {
                    0 => OK,
                    OK => 4,
                    i => i - 1,
                }
            }
            Tri::Zero => {}
        }
        if input.is_just_pressed(Button::Start) {
            self.cursor_at = OK;
        }
        if input.is_just_pressed(Button::A) {
            if self.cursor_at == OK {
                return Phase::Closing { x: 0 };
            }
            let slot = self.cursor_at as usize;
            if self.picks.len() < HAND_SIZE && !self.picks.contains(&slot) && self.allowed(slot)
            {
                self.picks.push(slot);
                self.draw_slot(slot);
                self.draw_stack();
            }
        }
        if input.is_just_pressed(Button::B) {
            if let Some(slot) = self.picks.pop() {
                self.draw_slot(slot);
                self.draw_stack();
            }
        }
        self.draw_card(gfx);
        Phase::Open
    }

    /// The picks in order, for the hand.
    pub fn hand(&self) -> impl Iterator<Item = Offer> + '_ {
        self.picks.iter().filter_map(|&slot| self.slots[slot])
    }

    pub fn show(&self, frame: &mut GraphicsFrame) {
        self.bg.show(frame);
        if !matches!(self.phase, Phase::Open) {
            return;
        }
        // The origin is the slot's position less 3 in each axis
        // (sub_8028894, sub_80288D0, asm03_0.s:4843-4884: a slot sits at
        // (8 + 16 * index, 0x68), OK at (0x58 + 3, 0x70 - 2)).
        let (x, y, bracket) = if self.cursor_at == OK {
            (0x58, 0x6b, &OK_BRACKET)
        } else {
            (8 + 16 * self.cursor_at as i32 - 3, 0x68 - 3, &SLOT_BRACKET)
        };
        let phase = (self.frames >> BLINK_SHIFT) as usize & 1;
        for c in &bracket[phase] {
            Object::new(self.cursor[phase].clone())
                .set_pos((x + c.dx, y + c.dy))
                .set_hflip(c.hflip)
                .set_vflip(c.vflip)
                .show(frame);
        }
    }
}
