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
/// The level readout sits at row 6, columns 16-20, its digits right-aligned;
/// level 0xb is the S rank, one glyph at tiles 0xb6/0xb7 in bank 10
/// (sub_802C6EC, asm03_0.s:12830-12888).
const LEVEL_ROW: i32 = 6;
const LEVEL_COL: i32 = 16;
const S_TILE: u16 = 0xb6;
pub const LEVEL_S: u8 = 0xb;

/// What went into the busting level, from the game's per-alliance counters
/// (byte_203EAE0; sub_800AC20, asm00_1.s:16678-17055).
pub struct Tally {
    /// Clear time in frames.
    pub time: u32,
    /// Times the player was hit: counter 3.
    pub hits_taken: u8,
    /// Times the player moved: counter 4, bumped as each move begins
    /// (asm31.s:108088).
    pub moves: u8,
}

/// The busting level for a solo battle, 1 to 11 where 11 is S. Time gives a
/// base of 6/5/4/3 at or under 5.00, 12.00 and 36.00 seconds (off_800ADDC,
/// byte_800AE00); being hit x times adds 1 - x, or -3 from four hits; moving
/// at most twice adds one. The game also credits multiple deletions, counter
/// hits and a counter 0xb that stays zero here -- none of which this battle
/// can produce yet -- so those terms are left out rather than scored as free
/// points.
pub fn busting_level(t: &Tally) -> u8 {
    let seconds = t.time / 60;
    let base: i32 = if seconds < 5 {
        6
    } else if seconds < 12 {
        5
    } else if seconds < 36 {
        4
    } else {
        3
    };
    let hit = match t.hits_taken {
        x if x < 4 => 1 - x as i32,
        _ => -3,
    };
    let moved = if t.moves <= 2 { 1 } else { 0 };
    (base + hit + moved).clamp(1, LEVEL_S as i32) as u8
}

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
    /// The screen fade the game runs on dismissal (sub_802C280 ends with a
    /// SetScreenFade of 0x10 steps); one step a frame stands in for its
    /// cadence, which was not read.
    Fading { step: u8 },
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

    /// Put up a window. `time` is the clear time in frames, `level` the
    /// busting level and `rank` 0-2 the time's record colour; the LOSER window
    /// ignores all three.
    pub fn show(&self, variant: usize, time: u32, level: u8, rank: u8) -> Shown {
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
            // The level: S as its one glyph, else decimal digits right-aligned
            // to the readout's last column.
            let mut col = LEVEL_COL + 4;
            if level >= LEVEL_S {
                for (dy, tile) in [(0, S_TILE), (1, S_TILE + 1)] {
                    bg.set_tile((col, LEVEL_ROW + dy), &v.tiles, entry(tile | 10 << 12));
                }
            } else {
                let mut n = level.max(1);
                loop {
                    let top = FONT_TILE + (n % 10) as u16 * 2;
                    for (dy, tile) in [(0, top), (1, top + 1)] {
                        bg.set_tile((col, LEVEL_ROW + dy), &v.tiles, entry(tile | 9 << 12));
                    }
                    n /= 10;
                    if n == 0 {
                        break;
                    }
                    col -= 1;
                }
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
    /// screen fade to apply, 1-16, once the window is being dismissed, and
    /// None before then; 16 means the screen is fully black.
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
            Phase::Dismissing { .. } => Phase::Fading { step: 1 },
            Phase::Fading { step } if step < 16 => Phase::Fading { step: step + 1 },
            Phase::Fading { .. } => Phase::Done,
            Phase::Done => Phase::Done,
        };
        match self.phase {
            Phase::Fading { step } => Some(step),
            Phase::Done => Some(16),
            _ => None,
        }
    }

    pub fn show(&self, frame: &mut agb::display::GraphicsFrame) {
        self.bg.show(frame);
    }
}
