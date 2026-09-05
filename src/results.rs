//! The window shown when a battle ends.
//!
//! sub_802C34E (asm/asm03_0.s:12353) puts up the RESULT window after the
//! last enemy is deleted, or the LOSER window when the player is: a 24x18
//! tilemap in palette bank 9 that slides in from x = -30 at two pixels a
//! frame until it rests at x = 3, then waits for A or Start, holds 0x14 more
//! frames and fades the screen out (sub_802C280, asm03_0.s:12234). The clear
//! time is five BCD digits written right to left at row 4, columns 20, 19,
//! 17, 16 and 14 as two-tile-tall glyphs from tile 0xa0, in palette bank
//! 9 + rank (sub_802C4E8, asm03_0.s:12558; byte_802C538).

use agb::display::Priority;
use agb::display::tiled::{
    RegularBackground, RegularBackgroundSize, TileEffect, TileFormat, TileSet, TileSetting,
};
use agb::display::{Palette16, Rgb15};

const MAGIC: &[u8; 4] = b"BNRS";
pub const WIN: usize = 0;
pub const LOSE: usize = 1;

const REST_X: i32 = 3;
const START_X: i32 = -30;
const SLIDE_STEP: i32 = 2;
/// The window is 18 tiles tall on a 20-tile screen; where the game puts it
/// vertically is not read, so it is centred.
const Y: i32 = 8;
const DISMISS_FRAMES: u8 = 0x14;
/// The clear time is capped at 9'59"99 (dword_802C548).
const TIME_CAP: u32 = 0x95999;
const DIGIT_COLS: [usize; 5] = [20, 19, 17, 16, 14];
const FONT_TILE: u16 = 0xa0;

struct Variant {
    tiles: TileSet,
    map: &'static [u8],
}

pub struct Results {
    variants: [Variant; 2],
    palette: &'static [u8],
}

enum Phase {
    Sliding { x: i32 },
    Waiting,
    Dismissing { ticks: u8 },
    Done,
}

/// A window on screen, driving its own slide, wait and dismissal.
pub struct Shown {
    bg: RegularBackground,
    phase: Phase,
}

impl Results {
    pub fn new(data: &'static [u8]) -> Self {
        assert_eq!(&data[0..4], MAGIC, "not a BNRS asset");
        let u32_at = |o: usize| u32::from_le_bytes(data[o..o + 4].try_into().unwrap()) as usize;
        let count = u32_at(0x08);
        assert_eq!(count, 2);
        let pal = u32_at(0x0c);
        let mut o = 0x10;
        let mut variant = || {
            o = (o + 3) & !3;
            let len = u32_at(o);
            let tiles = &data[o + 4..o + 4 + len];
            assert_eq!(tiles.as_ptr() as usize % 4, 0, "tile data must be word aligned");
            o = (o + 4 + len + 3) & !3;
            let (w, h) = (u32_at(o), u32_at(o + 4));
            let map = &data[o + 8..o + 8 + w * h * 2];
            o += 8 + w * h * 2;
            Variant {
                // SAFETY: alignment asserted above; the exporter emits whole
                // 4bpp tiles.
                tiles: unsafe { TileSet::new(tiles, TileFormat::FourBpp) },
                map,
            }
        };
        let a = variant();
        let b = variant();
        Self {
            variants: [a, b],
            palette: &data[pal..pal + 96],
        }
    }

    /// The three palette banks the windows use, for background banks 9-11.
    pub fn palettes(&self) -> [Palette16; 3] {
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

    /// Put up a window. `time` is the clear time in frames and `rank` 0-2 the
    /// busting level colour; both are ignored by the LOSER window.
    pub fn show(&self, variant: usize, time: u32, rank: u8) -> Shown {
        let v = &self.variants[variant];
        let mut bg = RegularBackground::new(
            Priority::P0,
            RegularBackgroundSize::Background32x32,
            TileFormat::FourBpp,
        );
        for i in 0..24 * 18 {
            let e = u16::from_le_bytes(v.map[i * 2..i * 2 + 2].try_into().unwrap());
            bg.set_tile(((i % 24) as i32, (i / 24) as i32), &v.tiles, entry(e));
        }
        if variant == WIN {
            // Minutes, seconds and hundredths as BCD, least significant first.
            let frames = time.min(u32::MAX / 100);
            let hundredths = frames % 60 * 100 / 60;
            let seconds = frames / 60 % 60;
            let minutes = (frames / 3600).min(9);
            let mut bcd = hundredths % 10
                | (hundredths / 10) << 4
                | (seconds % 10) << 8
                | (seconds / 10) << 12
                | minutes << 16;
            bcd = bcd.min(TIME_CAP);
            for col in DIGIT_COLS {
                let d = (bcd & 0xf) as u16;
                let top = FONT_TILE + d * 2;
                let bank = 9 + rank.min(2) as u16;
                for (dy, tile) in [(0, top), (1, top + 1)] {
                    bg.set_tile(
                        (col as i32, 4 + dy),
                        &v.tiles,
                        entry(tile | bank << 12),
                    );
                }
                bcd >>= 4;
            }
        }
        bg.set_scroll_pos((-START_X, -Y));
        Shown {
            bg,
            phase: Phase::Sliding { x: START_X },
        }
    }
}

fn entry(e: u16) -> TileSetting {
    TileSetting::new(
        e & 0x3ff,
        TileEffect::new(e & 0x400 != 0, e & 0x800 != 0, (e >> 12) as u8),
    )
}

impl Shown {
    /// Advance a frame. `confirm` is whether A or Start is down. Returns the
    /// fade amount to apply once dismissal starts, 0-16, or None before it.
    pub fn update(&mut self, confirm: bool) -> Option<u8> {
        self.phase = match self.phase {
            Phase::Sliding { x } if x < REST_X => {
                let x = (x + SLIDE_STEP).min(REST_X);
                self.bg.set_scroll_pos((-x, -Y));
                Phase::Sliding { x }
            }
            Phase::Sliding { .. } => Phase::Waiting,
            Phase::Waiting if confirm => Phase::Dismissing {
                ticks: DISMISS_FRAMES,
            },
            Phase::Waiting => Phase::Waiting,
            Phase::Dismissing { ticks } if ticks > 1 => Phase::Dismissing { ticks: ticks - 1 },
            Phase::Dismissing { .. } => Phase::Done,
            Phase::Done => Phase::Done,
        };
        match self.phase {
            Phase::Done => Some(16),
            _ => None,
        }
    }

    pub fn show(&self, frame: &mut agb::display::GraphicsFrame) {
        self.bg.show(frame);
    }
}
