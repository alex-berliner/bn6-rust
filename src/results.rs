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

/// Where the window rests, measured against the real ROM by aligning the two
/// windows: 24 px right and 16 px down of what this build had, which is 3
/// TILES and 2 tiles -- the disassembly's 3 is a tile column, not a pixel.
const REST_X: i32 = 24; // provenance: peeked -- aligned against the real ROM's own window (see the doc comment above)
const START_X: i32 = -30; // provenance: derived -- sub_802C34E, asm03_0.s:12353
const SLIDE_STEP: i32 = 2; // provenance: derived -- sub_802C34E, asm03_0.s:12353 ("two pixels a frame")
/// And two tile rows down.
const Y: i32 = 16; // provenance: peeked -- aligned against the real ROM's own window (see the doc comment above)
const DISMISS_FRAMES: u8 = 0x14; // provenance: derived -- sub_802C280, asm03_0.s:12234
/// The clear time is capped at 9'59"99 (dword_802C548).
const TIME_CAP: u32 = 0x95999; // provenance: derived -- dword_802C548
const DIGIT_COLS: [usize; 5] = [20, 19, 17, 16, 14]; // provenance: derived -- sub_802C4E8, asm03_0.s:12558; byte_802C538
/// The reward picture: 7x6 tiles at these window columns and rows, in the
/// fourth palette bank. Read off a live results screen's map.
const REWARD_W: usize = 7; // provenance: peeked -- read off a live results screen's own map
const REWARD_H: usize = 6; // provenance: peeked -- read off a live results screen's own map
const REWARD_TILES: usize = REWARD_W * REWARD_H;
const REWARD_COL: i32 = 14; // provenance: peeked -- read off a live results screen's own map
const REWARD_ROW: i32 = 10; // provenance: peeked -- read off a live results screen's own map
/// The palette bank it draws in, which is the fourth this asset carries: the
/// window's own are 9-11 and the picture's is 12.
const REWARD_BANK: u8 = 12; // provenance: peeked -- read off a live results screen's own map
/// The reward line's row and its last digit column, in window coordinates,
/// and the bank it draws in.
const REWARD_TEXT_ROW: i32 = 12; // provenance: peeked -- read off the capture's own map ("100 z" at rows 12-13)
const REWARD_TEXT_LAST: i32 = 9; // provenance: peeked -- read off the capture's own map, columns 7-9 and 11
const REWARD_TEXT_BANK: u8 = 9; // provenance: peeked -- read off the capture's own map
const ZENNY_GLYPH: u16 = 0xb3; // provenance: peeked -- found by searching all 448 glyphs of the real ROM's own font for the reward line's symbol
/// The GET DATA readout's bottom edge, which the live window and the stored
/// map disagree about: the map's tile there carries a lit top pixel row
/// (colour 9) and the real ROM's cells are flat colour 2, tile 0xc4. The
/// game replaces the run of ten as it draws the reward, so this build does
/// the same, in the same place. Read off the real ROM's own map -- the last
/// 80 pixels of the window, one pixel row of ten cells.
const REWARD_EDGE_ROW: i32 = 14; // provenance: peeked -- read off the real ROM's own map
const REWARD_EDGE_FIRST: i32 = 2; // provenance: peeked -- read off the real ROM's own map
const REWARD_EDGE_LAST: i32 = 11; // provenance: peeked -- read off the real ROM's own map
const REWARD_EDGE_TILE: u16 = 0x0c4; // provenance: peeked -- read off the real ROM's own map
const FONT_TILE: u16 = 0xa0; // provenance: derived -- sub_802C4E8, asm03_0.s:12558
/// The level readout sits at row 6, columns 16-20, its digits right-aligned;
/// level 0xb is the S rank, one glyph at tiles 0xb6/0xb7 in bank 10
/// (sub_802C6EC, asm03_0.s:12830-12888).
const LEVEL_ROW: i32 = 6; // provenance: derived -- sub_802C6EC, asm03_0.s:12830-12888
const LEVEL_COL: i32 = 16; // provenance: derived -- sub_802C6EC, asm03_0.s:12830-12888
const S_TILE: u16 = 0xb6; // provenance: derived -- sub_802C6EC, asm03_0.s:12830-12888
pub const LEVEL_S: u8 = 0xb; // provenance: derived -- sub_802C6EC, asm03_0.s:12830-12888

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
/// provenance: derived (every constant below) -- off_800ADDC/byte_800AE00,
/// sub_800AC20 asm00_1.s:16678-17055.
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
    /// The reward picture in the GET DATA box -- the zenny coin -- and its
    /// own bank. The game draws it into the window's map as a 7x6 image, the
    /// same shape as a chip card's picture.
    reward: TileSet,
    /// The battle text font with 8 added to every nibble, which is what the
    /// game's own text renderer writes here: its copy loop adds a colour word
    /// to each glyph word and this window passes index 8 (sub_3006C18,
    /// asm/asm38.s:2381). Checked against a capture, byte for byte.
    font: TileSet,
}

enum Phase {
    Sliding {
        x: i32,
    },
    Waiting,
    Dismissing {
        ticks: u8,
    },
    /// The screen fade the game runs on dismissal (sub_802C280 ends with a
    /// SetScreenFade of 0x10 steps); one step a frame stands in for its
    /// cadence, which was not read. provenance: the step COUNT (16) is
    /// derived -- sub_802C280's own SetScreenFade call; the RATE (one step a
    /// frame, in `Shown::update` below) is fitted -- the real cadence was
    /// not read.
    Fading {
        step: u8,
    },
    Done,
}

/// A window on screen, driving its own slide, wait and dismissal.
pub struct Shown {
    bg: RegularBackground,
    phase: Phase,
}

impl Results {
    pub fn new(data: &'static [u8], font: &'static [u8]) -> Self {
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
            assert_eq!(
                tiles.as_ptr() as usize % 4,
                0,
                "tile data must be word aligned"
            );
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
            palette: &data[pal..pal + 128],
            // SAFETY: the exporter 4-aligns the blob and emits whole tiles.
            reward: unsafe {
                TileSet::new(&data[pal + 128..pal + 128 + REWARD_TILES * 32], TileFormat::FourBpp)
            },
            font: {
                assert_eq!(&font[0..4], b"BNTF", "not a BNTF asset");
                let fo = u32::from_le_bytes(font[0x08..0x0c].try_into().unwrap()) as usize;
                let len = u32::from_le_bytes(font[fo..fo + 4].try_into().unwrap()) as usize;
                // The second half is the colour-added copy.
                let g = &font[fo + 4 + len / 2..fo + 4 + len];
                assert_eq!(g.as_ptr() as usize % 4, 0, "font must be word aligned");
                // SAFETY: alignment asserted; the exporter emits whole tiles.
                unsafe { TileSet::new(g, TileFormat::FourBpp) }
            },
        }
    }

    /// The three palette banks the windows use, for background banks 9-11.
    pub fn palettes(&self) -> [Palette16; 4] {
        core::array::from_fn(|bank| {
            let mut colours = [Rgb15::new(0); 16];
            for (i, slot) in colours.iter_mut().enumerate() {
                // Banks 9-11 are the window's; the fourth is the reward
                // picture's bank 12, which the exporter appends.
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
    /// The game's own character code for an ASCII byte, which is the glyph's
    /// index in this font (constants/bn6-charmap.tbl).
    fn char_code(c: u8) -> u16 {
        match c {
            b'0'..=b'9' => 0x01 + (c - b'0') as u16,
            b'A'..=b'Z' => 0x0b + (c - b'A') as u16,
            b'a'..=b'z' => 0x26 + (c - b'a') as u16,
            _ => 0,
        }
    }

    pub fn show(&self, variant: usize, time: u32, level: u8, rank: u8, zenny: u16) -> Shown {
        let v = &self.variants[variant];
        let mut bg = RegularBackground::new(
            // AUDIT wave 3c zero-layers (pair 2): was P0. The real ROM
            // draws the RESULT window on the SAME background as the HUD's
            // HP box and the chip-select window -- peeked live,
            // --only-bg 3 on /tmp/result_arrival.state shows both the "60"
            // HP box and the sliding-in window together, and that layer's
            // BGxCNT (0x1f09, reference/bn6f wt/zero-layers's own comment
            // on sub_801DA24) is priority 1, not 0. Matching the priority
            // here (this struct still owns its OWN RegularBackground --
            // see the ticket report on why the harder part, sharing the
            // SAME hardware BG index/tilemap as HudTiles, is not done: the
            // window's own scroll-driven slide-in and HudTiles' always-
            // fixed HP box cannot share one scroll register without the HP
            // box also being made scroll-compensated, which needs more
            // real-ROM measurement than this ticket had room for) costs
            // nothing when the two do not visually overlap (confirmed on
            // the captures above -- the HP box sits above the window, not
            // over it) and removes one more needless mismatch.
            Priority::P1,
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
                    bg.set_tile((col as i32, 4 + dy), &v.tiles, entry(tile | bank << 12));
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
        if variant == WIN {
            // The reward line: the amount right-aligned to the digit column,
            // a blank, then a 'z'. Read off the capture's map, whose "100 z"
            // fills window columns 7-9 and 11 of rows 12-13.
            let mut n = zenny;
            let mut col = REWARD_TEXT_LAST;
            loop {
                let g = Self::char_code(b'0' + (n % 10) as u8);
                for half in 0..2u16 {
                    bg.set_tile(
                        (col, REWARD_TEXT_ROW + half as i32),
                        &self.font,
                        entry(g * 2 + half | (REWARD_TEXT_BANK as u16) << 12),
                    );
                }
                n /= 10;
                col -= 1;
                if n == 0 {
                    break;
                }
            }
            // The symbol after the amount is not a letter: it is glyph 0xb3
            // of the font, found by taking the real ROM's own reward line
            // out of VRAM and searching all 448 glyphs for it.
            let z = ZENNY_GLYPH;
            for half in 0..2u16 {
                bg.set_tile(
                    (REWARD_TEXT_LAST + 2, REWARD_TEXT_ROW + half as i32),
                    &self.font,
                    entry(z * 2 + half | (REWARD_TEXT_BANK as u16) << 12),
                );
            }
            for k in 0..REWARD_TILES {
                bg.set_tile(
                    (REWARD_COL + (k % REWARD_W) as i32, REWARD_ROW + (k / REWARD_W) as i32),
                    &self.reward,
                    TileSetting::new(k as u16, TileEffect::new(false, false, REWARD_BANK)),
                );
            }
            for col in REWARD_EDGE_FIRST..=REWARD_EDGE_LAST {
                bg.set_tile(
                    (col, REWARD_EDGE_ROW),
                    &v.tiles,
                    entry(REWARD_EDGE_TILE | (REWARD_TEXT_BANK as u16) << 12),
                );
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

    /// Draw the window; the id is for including it in the screen fade.
    pub fn show(
        &self,
        frame: &mut agb::display::GraphicsFrame,
    ) -> agb::display::tiled::RegularBackgroundId {
        self.bg.show(frame)
    }

    /// Advance the arriving slide-in by `frames` frames with no input, for
    /// FIXTURE.md's `result_elapsed` (+56): "frames of the RESULT sequence
    /// already elapsed at boot". Just `update(false)` called that many
    /// times -- the exact per-frame motion a real capture would show,
    /// replayed at construction instead of waited out frame by frame, so a
    /// fixture can land the capture on an arbitrary point of the slide
    /// instead of only its two endpoints (AUDIT wave 3c item 2; the
    /// `result` harness row's own note: "MISSING FIELD: something like
    /// 'frames since the RESULT window's own arrival'"). Calls past
    /// `Phase::Waiting` are harmless no-ops (`update`'s own `Phase::Waiting
    /// => Phase::Waiting` arm), so `SETTLED` below only needs to be large
    /// enough, not exact.
    pub fn fast_forward(&mut self, frames: u32) {
        for _ in 0..frames {
            self.update(false);
        }
    }

    /// `frames` for `fast_forward` that is guaranteed to reach
    /// `Phase::Waiting` from a fresh `Results::show` -- FIXTURE.md's
    /// `result_elapsed` = 0xFFFF ("settled", today's demo-resultmatch
    /// picture). Ceiling of `(REST_X - START_X) / SLIDE_STEP` so an
    /// off-by-one never leaves the window a frame short of settled.
    pub const SETTLED: u32 = ((REST_X - START_X + SLIDE_STEP - 1) / SLIDE_STEP) as u32; // provenance: derived -- this file's own slide constants (REST_X, START_X, SLIDE_STEP; sub_802C34E, asm03_0.s:12353), not a separate measurement
}
