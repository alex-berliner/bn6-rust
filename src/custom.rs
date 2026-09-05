//! The chip selection window that opens when the custom gauge fills.
//!
//! The game draws it on BG3 -- char block 2, screen block 31 (sub_801DA24,
//! asm00_2.s:29030) -- from the 15x20 map byte_86E625C in palette bank 9,
//! and slides it in by scrolling from 0x78 to 0 at 0xc a frame, and out the
//! same way (sub_8026B04, sub_8026BF4; asm03_0.s:882, 1026). The tiles are
//! dword_86E1D38, exported with the map by tools/custom_export.py.
//!
//! The map's dynamic regions -- chip name, picture, the slot rows, OK and
//! the stack column -- arrive blank (see tools/custom_export.py); the chip
//! art the game renders into them (sub_8028476, sub_80284E2) and the chip
//! records behind the slots (unk_20365C0) are located but not reproduced
//! yet. The cursor is: it walks the five slots and OK the way the default
//! slot table links them (dword_802A7CC, asm03_0.s:9062: a ring, slot 0
//! through 4 then OK, with no vertical moves while the second row is empty),
//! Start jumps it to OK, and A on OK closes the window
//! (custMenuSomeHandler_8028B74, asm03_0.s:5160-5344). A on a slot does
//! nothing until there are chips to pick.

use agb::display::Priority;
use agb::display::object::{DynamicSprite16, Object, PaletteVramSingle, Size, SpriteVram};
use agb::display::tiled::{
    RegularBackground, RegularBackgroundSize, TileEffect, TileFormat, TileSet, TileSetting,
};
use agb::display::{GraphicsFrame, Palette16, Rgb15};
use agb::input::{Button, ButtonController, Tri};

const MAGIC: &[u8; 4] = b"BNCW";
const MAP_W: usize = 15;
const MAP_H: usize = 20;
const SLIDE_FROM: i32 = 0x78;
const SLIDE_STEP: i32 = 0xc;
/// The window's palette bank; the results windows use 9-11 too, so the
/// bank is set on open and the results' restored on close.
pub const BANK: u8 = 9;

/// The cursor's index for the OK box; 0-4 are the offered slots
/// (S20364C0.inc:14, eS20364C0+7).
const OK: u8 = 0xa;
/// The bracket swaps tile and shrinks a pixel every 8 frames (sub_8028820,
/// asm03_0.s:4807: frame counter >> 3 & 1).
const BLINK_SHIFT: u32 = 3;

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
    [corner(0, 0, 0), corner(0xe, 0, 0x10), corner(0xe, 0xe, 0x30), corner(0, 0xe, 0x20)],
    [corner(1, 1, 0), corner(0xc, 1, 0x10), corner(0xc, 0xc, 0x30), corner(1, 0xc, 0x20)],
];
const OK_BRACKET: [[Corner; 4]; 2] = [
    [corner(1, 2, 0), corner(0x16, 2, 0x10), corner(0x16, 0x14, 0x30), corner(1, 0x14, 0x20)],
    [corner(3, 4, 0), corner(0x14, 4, 0x10), corner(0x14, 0x12, 0x30), corner(3, 0x12, 0x20)],
];

pub struct CustomAssets {
    tiles: TileSet,
    map: &'static [u8],
    palette: &'static [u8],
    cursor_tiles: &'static [u8],
    cursor_palette: Palette16,
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
    /// The two blink phases of the corner tile.
    cursor: [SpriteVram; 2],
    cursor_at: u8,
    /// Counted while the window is open, as eS20364C0+0x40 is.
    frames: u32,
}

impl CustomAssets {
    pub fn new(data: &'static [u8]) -> Self {
        assert_eq!(&data[0..4], MAGIC, "not a BNCW asset");
        let at = |o: usize| u32::from_le_bytes(data[o..o + 4].try_into().unwrap()) as usize;
        let (t, m, p, c) = (at(0x08), at(0x0c), at(0x10), at(0x18));
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
            cursor_tiles: &data[c..c + 64],
            cursor_palette: read_palette(&data[c + 64..c + 96]),
        }
    }

    /// One of the three colour variants, for background bank 9.
    pub fn palette(&self, variant: usize) -> Palette16 {
        read_palette(&self.palette[variant * 32..variant * 32 + 32])
    }

    pub fn open(&self) -> Custom<'_> {
        let mut bg = RegularBackground::new(
            Priority::P0,
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
        let mut custom = Custom {
            bg,
            tiles: &self.tiles,
            map: self.map,
            revealed: 0,
            phase: Phase::Opening { x: SLIDE_FROM },
            cursor,
            cursor_at: 0,
            frames: 0,
        };
        custom.reveal(SLIDE_FROM);
        custom
    }
}

fn read_palette(bytes: &[u8]) -> Palette16 {
    let mut colours = [Rgb15::new(0); 16];
    for (i, slot) in colours.iter_mut().enumerate() {
        *slot = Rgb15::new(u16::from_le_bytes(bytes[i * 2..i * 2 + 2].try_into().unwrap()));
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
            Phase::Open => {
                self.frames += 1;
                self.navigate(input)
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
    /// Left and right follow the slot records' link bytes; with only the
    /// first row offered the links form the ring 0..4, OK. Start moves the
    /// cursor to OK (asm03_0.s:5276), A acts on the slot under the cursor
    /// (asm03_0.s:5344): OK closes the window, a chip slot is not picked yet.
    fn navigate(&mut self, input: &ButtonController) -> Phase {
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
        if input.is_just_pressed(Button::A) && self.cursor_at == OK {
            return Phase::Closing { x: 0 };
        }
        Phase::Open
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
