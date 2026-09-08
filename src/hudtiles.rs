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
const BLANK_PAIR: u16 = 10; // provenance: derived -- the exporter's own known asset layout
const CAP_PAIR: u16 = 11; // provenance: derived -- the exporter's own known asset layout
/// Digit slots between the two caps.
const SLOTS: u32 = 4; // provenance: peeked -- read off a live battle's BG3 map
/// The CUSTOM gauge, in the same asset after the HP tiles. Its art is loaded
/// at VRAM tile 0x222 on the real ROM, so the asset index of VRAM tile t is
/// GAUGE_FIRST + (t - 0x22b). The bar is one tile row: an end cap, six body
/// cells, the four-cell L-or-R marker, six more body cells and a mirrored end
/// cap, with the CUSTOM label on the row above it.
const GAUGE_FIRST: u16 = 50; // provenance: peeked -- VRAM tile 0x222 on the real ROM
const CAP_TOP: u16 = GAUGE_FIRST; // provenance: peeked -- VRAM tile offset read off the real ROM
const CAP_BOTTOM: u16 = GAUGE_FIRST + 1; // provenance: peeked -- VRAM tile offset read off the real ROM
const FILLER: u16 = GAUGE_FIRST + 2; // provenance: peeked -- VRAM tile offset read off the real ROM
const CUSTOM_TEXT: u16 = GAUGE_FIRST + 3; // provenance: peeked -- VRAM tile offset read off the real ROM
/// A full bar FLOWS: its body cell steps through four patterns, seven frames
/// each, and its L-or-R marker alternates cyan and orange every eight, both
/// read frame by frame off a live battle's BG3 map (VRAM tiles 0x232, 0x233,
/// 0x234, 0x235 for the body in the order below, 0x236 and 0x23a for the two
/// markers). The map is what animates -- the tile art and the palette bank
/// stay put -- so this is a tile swap, not a palette cycle.
/// NOT VERIFIED: where the cycle starts. One save state cannot say whether
/// the phase runs off the battle's frame counter or off the moment the gauge
/// filled; this build counts from the latter.
// provenance: peeked -- VRAM tile ids read off a live battle's BG3 map.
const BAR_CYCLE: [u16; 4] = [
    GAUGE_FIRST + 9,
    GAUGE_FIRST + 10,
    GAUGE_FIRST + 7,
    GAUGE_FIRST + 8,
];
const BAR_FRAMES: u32 = 7; // provenance: derived -- read off the real ROM's BG3 map frame by frame (each of the 4 flow tiles holds for 7 frames)
const MARKER_FRAMES: u32 = 8; // provenance: derived -- read off the real ROM's BG3 map frame by frame (cyan/orange alternate every 8 frames)
/// The flow runs one frame behind the counter that drives it. Found by
/// aligning a whole battle screen against the real ROM on the BACKDROP's
/// animation -- which leaves every tile but this bar identical, 360 px -- and
/// then sweeping the gauge's own band alone: it matches at -1 and nowhere
/// else, taking the whole 240x160 screen to zero.
/// NOT VERIFIED as a rule. The capture's gauge has been full for an unknown
/// time, so its phase relative to the backdrop is not fixed by anything this
/// save state can show; -1 is what makes this capture match, and its being so
/// small is the only reason to think the two counters are related at all.
const BAR_PHASE: u32 = 1; // provenance: fitted -- matches at -1 and nowhere else against one save state; not verified as a rule (TODO.md A8)
/// The bar runs on its own offset from the marker, and this is a MEASURED
/// number, not a derived one. Matching tiles by hash across a full cycle: the
/// real ROM shows its frame-44 tile on frames 42..48 and this build showed the
/// same tile 9 frames later in aligned time, while the MARKER measured offset
/// 0 -- so the two cannot come off one counter as this code assumed, and no
/// single phase fixes both (9 mod 28 with 0 mod 16 has no solution).
/// What advances the real ROM's bar is still unknown; see TODO A8. Same
/// footing as BUSTER_HIT_DELAY in battle.rs: the value that measures right
/// rather than the value that computes right, and labelled as such.
const BAR_EXTRA: u32 = 9; // provenance: fitted -- measures right, not derived; TODO.md A8: "no single phase fixes both [BAR_EXTRA and MARKER_EXTRA] -- 9 mod 28 with 0 mod 16 has no solution", confirmed again by this ticket's own sterile-HUD test finding the same inconsistency under a different alignment
/// And the marker sits half a blink from where this build put it -- measured
/// the same way, and the residue it removes is exactly the 110 orange pixels
/// the lit marker draws.
const MARKER_EXTRA: u32 = 8; // provenance: fitted -- measures right, not derived; see BAR_EXTRA's own note
/// The partly-filled bar's lit cell. NOT VERIFIED: the gauge is only ever
/// seen full in the capture, so this is the first of the four flow patterns
/// held still.
const BAR: u16 = GAUGE_FIRST + 7; // provenance: fitted -- NOT VERIFIED, the gauge is only ever seen full in the capture (own doc above)
/// The marker is cyan while the gauge is filling and orange once it is full,
/// which is the swap the gauge shows instead of any proportional readout;
/// full, it alternates between the two.
const MARKER_WAITING: u16 = GAUGE_FIRST + 11; // provenance: peeked -- VRAM tile id read off the real ROM
const MARKER_READY: u16 = GAUGE_FIRST + 15; // provenance: peeked -- VRAM tile id read off the real ROM
/// Columns the gauge spans, and how many of them carry bar body.
const GAUGE_COL: u32 = 6; // provenance: peeked -- read off a live battle's BG3 map
const GAUGE_CELLS: u32 = 18; // provenance: peeked -- read off a live battle's BG3 map
const BAR_CELLS: u32 = 12; // provenance: peeked -- read off a live battle's BG3 map
/// The palette bank the gauge draws in on the real ROM.
pub const GAUGE_BANK: u8 = 9; // provenance: peeked -- the real ROM's own choice
/// A blank tile the exporter appends, for clearing cells: tile 0 of this asset
/// is the top half of digit zero and cannot serve as one.
const BLANK_TILE: u16 = 69; // provenance: derived -- the exporter's own known asset layout

/// The palette bank the box draws in. The field uses 0-8 and the results
/// windows 9-11, so this one is free and is the real ROM's own choice.
pub const BANK: u8 = 13; // provenance: peeked -- the real ROM's own choice
/// The entries that bank swaps while the HP figure catches up after a hit.
const HP_FLASH: [(usize, u16); 4] = [(4, 22463), (5, 13087), (6, 4767), (11, 127)]; // provenance: peeked -- read straight out of BG palette RAM on a flashing frame

/// The game's own character code for an ASCII byte, which is also the index of
/// its glyph in the text font (constants/bn6-charmap.tbl). Anything without a
/// code is drawn as a space.
fn char_code(c: u8) -> u16 {
    match c {
        b'0'..=b'9' => 0x01 + (c - b'0') as u16,
        b'A'..=b'Z' => 0x0b + (c - b'A') as u16,
        b'a'..=b'z' => 0x26 + (c - b'a') as u16,
        b'*' => 0x25,
        _ => 0,
    }
}

/// Where the chip name is written, in tile rows, and how wide it can run.
const NAME_ROW: i32 = 18; // provenance: peeked -- measured against the real ROM's own strip
const NAME_COLS: u32 = 12; // provenance: peeked -- measured against the real ROM's own strip
/// The damage figure follows the name in a second digit set carried in this
/// asset, orange rather than white: pair 12 is its zero and it steps by one
/// pair per digit, the same as the HP box's set.
const DAMAGE_ZERO_PAIR: u16 = 12; // provenance: derived -- the exporter's own known asset layout

pub struct HudTiles {
    bg: RegularBackground,
    font: TileSet,
    tiles: TileSet,
    palette: Palette16,
    gauge_palette: Palette16,
    shown: Option<u16>,
    gauge_shown: Option<(u32, u16, bool)>,
    /// Frames the gauge has stood full, which drives the flow animation.
    gauge_tick: u32,
    /// Whether the chip menu is up. The real ROM keeps the HP box on screen
    /// then but redraws it fifteen tile columns over, beside the window and
    /// above the field, and drops the gauge, whose place the window takes.
    menu: bool,
}

impl HudTiles {
    pub fn new(data: &'static [u8], font: &'static [u8]) -> Self {
        assert_eq!(&font[0..4], b"BNTF", "not a BNTF asset");
        let fo = u32::from_le_bytes(font[0x08..0x0c].try_into().unwrap()) as usize;
        let flen = u32::from_le_bytes(font[fo..fo + 4].try_into().unwrap()) as usize;
        let glyphs = &font[fo + 4..fo + 4 + flen];
        assert_eq!(glyphs.as_ptr() as usize % 4, 0, "font must be word aligned");
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
            // SAFETY: alignment asserted above; the exporter emits whole tiles.
            font: unsafe { TileSet::new(glyphs, TileFormat::FourBpp) },
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
            gauge_tick: 0,
            menu: false,
        }
    }

    pub fn palette(&self) -> Palette16 {
        self.palette.clone()
    }

    /// The box's bank with the four entries the real ROM swaps while the HP
    /// figure is catching up after a hit. The TILES do not change -- the same
    /// white digits are drawn -- and entries 4, 5, 6 and 11 go to an orange
    /// ramp, read straight out of BG palette RAM on a flashing frame.
    /// NOT VERIFIED: the heal flash. Nothing in the capture heals the navi, so
    /// this build uses the same ramp for both.
    pub fn flash_palette(&self) -> Palette16 {
        let mut colours = [Rgb15::new(0); 16];
        for (i, slot) in colours.iter_mut().enumerate() {
            *slot = self.palette.colour(i);
        }
        for (i, c) in HP_FLASH {
            colours[i] = Rgb15::new(c);
        }
        Palette16::new(colours)
    }

    pub fn gauge_palette(&self) -> Palette16 {
        self.gauge_palette.clone()
    }

    /// AUDIT pairs 6/14/17: seed the flow counter directly, for a fixture
    /// compared against a save state where the CUSTOM gauge has already
    /// been full (and flowing) for an unknown time -- see TRANSFER.md 7ab,
    /// "two phases in that screen CANNOT be settled by one save state". A
    /// fresh `new()` leaves this at 0, which is right for every fixture
    /// verified against a save state so far (`gauge_tick`'s own doc in
    /// fixture.rs), so this exists as a knob rather than because any current
    /// fixture needs a nonzero seed.
    pub fn seed_gauge(&mut self, tick: u32) {
        self.gauge_tick = tick;
    }

    /// Repaint the CUSTOM label and the bar. `filled` is the gauge's value
    /// over its full value; the marker turns from cyan to orange at one.
    /// NOTE: only the full bar is verified against the real ROM, because the
    /// gauge drains only when the custom window opens and that window
    /// replaces this whole layer, so a draining bar never shows on its own.
    /// The empty body cell is drawn with the label row's filler tile, which is
    /// a guess.
    /// `show` is false once the fight is over: the real ROM drops the whole
    /// gauge -- label, bar and end caps -- the moment the RESULT window comes
    /// up, and keeps only the HP box. Read off /tmp/noenemy2.state, where the
    /// strip beside the HP box is bare backdrop.
    pub fn set_gauge(&mut self, filled: u16, full: u16, show: bool) {
        if self.menu {
            return;
        }
        if !show {
            if self.gauge_shown.is_none() {
                return;
            }
            self.gauge_shown = None;
            for i in 0..GAUGE_CELLS {
                for row in 0..2 {
                    self.bg.set_tile(
                        ((GAUGE_COL + i) as i32, row),
                        &self.tiles,
                        TileSetting::new(BLANK_TILE, TileEffect::new(false, false, BANK)),
                    );
                }
            }
            return;
        }
        let lit = (u32::from(filled) * BAR_CELLS / u32::from(full.max(1))).min(BAR_CELLS);
        let ready = lit >= BAR_CELLS;
        // A full bar flows; anything less stands still, so the animation only
        // runs while it is full and starts over each time it fills.
        if ready {
            self.gauge_tick = self.gauge_tick.wrapping_add(1);
        } else {
            self.gauge_tick = 0;
        }
        let flow = self.gauge_tick.wrapping_sub(BAR_PHASE);
        let (bar, marker) = if ready {
            (
                BAR_CYCLE[(((flow + BAR_EXTRA) / BAR_FRAMES) % BAR_CYCLE.len() as u32) as usize],
                if ((flow + MARKER_EXTRA) / MARKER_FRAMES) % 2 == 0 {
                    MARKER_READY
                } else {
                    MARKER_WAITING
                },
            )
        } else {
            (BAR, MARKER_WAITING)
        };
        if self.gauge_shown == Some((lit, bar, marker == MARKER_READY)) {
            return;
        }
        self.gauge_shown = Some((lit, bar, marker == MARKER_READY));
        let mut body = 0;
        for i in 0..GAUGE_CELLS {
            let col = GAUGE_COL + i;
            let last = i + 1 == GAUGE_CELLS;
            let (top, bottom) = if i == 0 || last {
                (CAP_TOP, CAP_BOTTOM)
            } else if (7..11).contains(&i) {
                (CUSTOM_TEXT + (i as u16 - 7), marker + (i as u16 - 7))
            } else {
                let cell = if body < lit { bar } else { FILLER };
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

    /// Write a chip's name along the bottom, as the real ROM does while a chip
    /// is in use, or clear it. Each glyph is two tiles stacked and its index is
    /// the game's character code.
    pub fn set_name(&mut self, name: Option<(&str, u16)>) {
        // The damage runs straight on from the name, so lay it out first.
        let mut digits = [0u16; 4];
        let mut count = 0;
        if let Some((_, power)) = name {
            if power > 0 {
                let mut left = power;
                while left > 0 && count < digits.len() {
                    digits[count] = left % 10;
                    left /= 10;
                    count += 1;
                }
            }
        }
        let len = name.map_or(0, |(n, _)| n.len());
        for col in 0..NAME_COLS {
            let at = col as usize;
            let code = if at < len {
                name.and_then(|(n, _)| n.as_bytes().get(at).copied()).map(char_code)
            } else if at < len + count {
                None
            } else {
                None
            };
            let digit = if at >= len && at < len + count {
                Some(digits[len + count - 1 - at])
            } else {
                None
            };
            for half in 0..2u16 {
                let (tile, tiles) = match (code, digit) {
                    (Some(c), _) if c != 0 => (c * 2 + half, &self.font),
                    (_, Some(d)) => ((DAMAGE_ZERO_PAIR + d) * 2 + half, &self.tiles),
                    _ => (BLANK_TILE, &self.tiles),
                };
                self.bg.set_tile(
                    (col as i32, NAME_ROW + half as i32),
                    tiles,
                    TileSetting::new(tile, TileEffect::new(false, false, BANK)),
                );
            }
        }
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
        // The right cap is the left one MIRRORED, as the real ROM's map has
        // it: same tile pair with h-flip set.
        self.cell_flipped(base, CAP_PAIR, false);
        self.cell_flipped(base + 1 + SLOTS, CAP_PAIR, true);
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
        self.cell_flipped(col, pair, false);
    }

    fn cell_flipped(&mut self, col: u32, pair: u16, hflip: bool) {
        for half in 0..2u16 {
            self.bg.set_tile(
                (col as i32, half as i32),
                &self.tiles,
                TileSetting::new(pair * 2 + half, TileEffect::new(hflip, false, BANK)),
            );
        }
    }

    /// Returns its background id, so a blend can include this layer -- the
    /// battle's opening whitens EVERY layer, not just the field's.
    pub fn show(&self, frame: &mut GraphicsFrame) -> agb::display::tiled::RegularBackgroundId {
        self.bg.show(frame)
    }
}
