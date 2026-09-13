//! The HP box the real ROM draws on BG3, in tiles rather than sprites.
//!
//! Each digit is two tiles stacked and the set steps by two tiles per digit,
//! so digit six is twelve tiles past digit zero. The box is a left cap, four
//! digit slots filled right-aligned with a blank tile in the leading
//! positions, and a right cap, all in one palette bank. Read off a live
//! battle's BG3 map, whose top row is cap, blank, blank, six, zero, cap for an
//! HP of 60.
//!
//! AUDIT wave 3d "bg3-merge" ticket: canon assigns hardware backgrounds
//! BG0 unused, BG1 backdrop (P3), BG2 field panels (P2), BG3 HUD + chip
//! window + RESULT, ONE tilemap (P1) -- peeked, identical across
//! pausedwithcannon/chipselect/result_arrival. Before this ticket agb's
//! `.show()` call order gave `backdrop` 0, `HudTiles` 1, `field` 2,
//! `Custom`/`Results` 3 -- three separate `RegularBackground`s where canon
//! has one, and none at canon's own index. BEFORE measurement
//! (`tools/harness.py`'s `opening`/`CUSTMATCH_ROW`, `--only-bg N` on BOTH
//! sides, full 240x160, no isolation flags):
//!
//! | state (frames) | --only-bg 1 | --only-bg 2 | --only-bg 3 |
//! |---|---|---|---|
//! | opening (40) | 1536000 (38400 px/frame, EVERY frame full-screen: canon's backdrop vs our HudTiles) | 0 (both sides happen to be `field`) | 28160 (704 px/frame: canon's HP box, ours shows nothing -- `custom` is `None`) |
//! | window (16) | 614400 (38400 px/frame, same full mismatch) | 0 (`field` again) | 11264 (704 px/frame: canon's HP box beside its window, ours shows the window alone) |
//!
//! `--only-bg 2` reads 0 only because our `field` already happened to land
//! on hardware index 2 by coincidence of call order, not because the index
//! was chosen to match. `--only-bg 1`/`--only-bg 3` are meaningless as a
//! same-content comparison before this ticket: our index 1 is the HUD, not
//! the backdrop, and our index 3 is the chip window alone (or nothing),
//! never the HUD+window pair canon draws together. See battle.rs's `draw()`
//! and this ticket's own report for the after numbers and the merge itself.

use agb::display::tiled::{RegularBackground, TileEffect, TileFormat, TileSet, TileSetting};
use agb::display::{Palette16, Rgb15};

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
/// Canon order, straight off sub_801C4E4 (asm00_2.s:26372-26373): the bar
/// tile is 0x9232 + ((t div 7) mod 4), i.e. step 0..3 = VRAM 0x232, 0x233,
/// 0x234, 0x235 = asset GAUGE_FIRST+7..+10 -- the rotation the old array had
/// (+9, +10, +7, +8) was absorbed by the (now deleted) fitted BAR_EXTRA.
/// (The old "NOT VERIFIED: where the cycle starts" hedge above is settled by
/// the same routine: the cycle runs off the gauge-full counter t, see below.)
const BAR_CYCLE: [u16; 4] = [
    GAUGE_FIRST + 7,
    GAUGE_FIRST + 8,
    GAUGE_FIRST + 9,
    GAUGE_FIRST + 10,
];
const BAR_FRAMES: u32 = 7; // provenance: derived -- canon's own divisor, `svc 6` (SWI Div) by #7 in sub_801C4E4 (asm00_2.s:26368-26369); matches the BG3 map read frame by frame (each of the 4 flow tiles holds for 7 frames)
/// THE MECHANISM, FOUND IN THE DISASSEMBLY (TODO F6, 2026-09-12 -- this
/// replaces three fitted constants, `BAR_PHASE`/`BAR_EXTRA`/`MARKER_EXTRA`,
/// whose history is summarised at the bottom of this block). Canon draws the
/// flowing gauge in `sub_801C4E4` (asm00_2.s:26351-26423, dispatched from
/// `sub_801BF64`'s per-frame flag table `off_801BF88`, slot 4). With the
/// gauge value (`eStruct2035280+0x20`, word_20352A0) at its 0x4000 cap:
///   - it increments `t` = byte `eStruct2035280+0x00` (0x02035280) by 1 and
///     wraps it at 0x70 = 112 (asm00_2.s:26360-26366);
///   - it draws ALL 16 bar cells (j=7, i=1, width 0x10, block 3) with the
///     ONE tile `0x9232 + ((t div 7) & 3)` (svc 6 = SWI Div, asm00_2.s
///     26367-26379) -- the four flow tiles 0x232..0x235 in direct order;
///   - it draws the 4 marker cells (j=0xd, i=1, width 4) from the table
///     `byte_801C6C0[t & 8]` (asm00_2.s:26380-26388): offset 0 gives
///     0x9236..0x9239 (cyan) and offset 8 gives 0x923a..0x923d (orange), so
///     the marker is ORANGE iff `(t >> 3) & 1` -- no additive phase
///     anywhere, and the marker is the SAME four-tile row per state, not a
///     separate 2-frame blink.
/// Both animations are therefore exact functions of ONE free-running
/// counter, which is the counter this file already models: the zero-src
/// ticket's live measurement (kept below) established that `gauge_tick` --
/// +1 per frame while full, starting at 1 on the first full frame -- IS the
/// real ROM's `t` frame for frame, and the wrap at 112 = lcm(28,16) is why
/// no `(BAR_PHASE, BAR_EXTRA)`-style pair of additive offsets could ever
/// satisfy bar and marker simultaneously under the old formula shapes (the
/// old shapes needed `gt - t = -BAR_EXTRA+1 mod 28` AND `= 9-MARKER_EXTRA
/// mod 16`, which has no solution at the values measured best).
///
/// WHAT REMAINED WAS PURE FIXTURE PHASE (TODO F6): the `tiles`/`gauge` rows
/// compare against PAUSED, whose `t` carries an arbitrary fill history
/// (peeks 98 at load and advances even during the paused frames -- measured:
/// `--watch 0x02035280` over the row's own canon capture reads
/// `t(frame) = 99 + frame`, i.e. the draw inside canon frame c uses
/// `t = 98 + c`), while the fixture-built battle starts `gauge_tick` at 0 at
/// Battle::new. Rather than fit the gap into the formulas, the fixture now
/// seeds it: HUDMATCH carries `gauge_tick=50` (descriptor +28, the field's
/// documented purpose -- "a fixture compared against a save state where the
/// CUSTOM gauge has already been full for an unknown time"), measured off
/// the row's own alignment: the old build's marker flipped at rust frame
/// 440 where canon's flipped at canon frame 46 and its bar at canon 49 --
/// with `gt(u) = u - 7` (first set_gauge at the marker origin 8) that pins
/// `gt(435) = 428` against canon's `t_used(44) = 30`, so the seed making
/// `gt + seed = t_used (mod 112)` at every matched frame is
/// 30 - 428 = -398 = 50 (mod 112). With the seed in, canon's formulas run
/// verbatim on `gauge_tick` and both boundary frames coincide exactly.
///
/// HISTORY OF THE FITTED VALUES THIS REPLACES (kept, compressed): A8's
/// 446-px stripe defect was first zeroed by two MEASURED offsets
/// (`BAR_EXTRA = 9`, `MARKER_EXTRA = 8`) nobody could derive; the zero-src
/// ticket then measured the real counter at 0x02035280 (+1/frame while
/// full, first full frame reads 1, wraps at 112 -- confirmed by
/// construction across a fill-to-full transition and a mid-cycle capture)
/// and derived `BAR_EXTRA=7`/`MARKER_EXTRA=8` from it, but building with 7
/// measured WORSE (538 -> 1258 px) because the fixture's `gauge_tick` is
/// not phase-identical to PAUSED's `t` -- the gap that this seed now
/// supplies. The old 9-frame bar/marker disagreement ("9 mod 28 with 0 mod
/// 16 has no solution") was the same missing-seed problem seen through the
/// old formula shapes, not two clocks.
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

/// AUDIT wave 3d "bg3-merge": no longer owns its own `RegularBackground`.
/// Canon draws the HP box, the chip window and the RESULT window on ONE
/// hardware BG3 (peeked, identical across pausedwithcannon/chipselect/
/// result_arrival) -- see battle.rs's `hud_bg` field, which every method
/// below that used to write `self.bg` now takes as a `&mut RegularBackground`
/// parameter instead.
pub struct HudTiles {
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
    pub fn set_gauge(&mut self, bg: &mut RegularBackground, filled: u16, full: u16, show: bool) {
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
                    bg.set_tile(
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
        // Canon sub_801C4E4 (asm00_2.s:26367-26388): one counter, no phase
        // offsets -- bar tile = BAR_CYCLE[(t div 7) mod 4], marker orange iff
        // (t & 8) != 0. `gauge_tick` IS canon's t frame for frame while full
        // (its doc above), given the fixture seed that matches phases.
        let (bar, marker) = if ready {
            (
                BAR_CYCLE[((self.gauge_tick / BAR_FRAMES) % BAR_CYCLE.len() as u32) as usize],
                if self.gauge_tick & 8 != 0 {
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
            self.gauge_cell(bg, col, 0, top, last);
            self.gauge_cell(bg, col, 1, bottom, last);
        }
    }

    fn gauge_cell(&mut self, bg: &mut RegularBackground, col: u32, row: i32, tile: u16, hflip: bool) {
        bg.set_tile(
            (col as i32, row),
            &self.tiles,
            TileSetting::new(tile, TileEffect::new(hflip, false, GAUGE_BANK)),
        );
    }

    /// Write a chip's name along the bottom, as the real ROM does while a chip
    /// is in use, or clear it. Each glyph is two tiles stacked and its index is
    /// the game's character code.
    pub fn set_name(&mut self, bg: &mut RegularBackground, name: Option<(&str, u16)>) {
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
                bg.set_tile(
                    (col as i32, NAME_ROW + half as i32),
                    tiles,
                    TileSetting::new(tile, TileEffect::new(false, false, BANK)),
                );
            }
        }
    }

    /// Move the box aside for the chip menu, or bring it back.
    pub fn set_menu(&mut self, bg: &mut RegularBackground, menu: bool) {
        if self.menu == menu {
            return;
        }
        self.menu = menu;
        self.shown = None;
        self.gauge_shown = None;
        // AUDIT wave 3d "bg3-merge": columns 0..15 are the chip window's own
        // territory (custom.rs's MAP_W) on the now-shared background, and by
        // the frame this runs (one frame after `self.custom` actually
        // becomes `Some`, since this reads last frame's state -- see the
        // call site's own comment) the window has ALREADY drawn its title
        // and card there. A blanket 0..32 sweep -- correct pre-merge, when
        // this wrote a background of its own that the window never shared
        // -- erases that content instead of the gauge's leftover cells,
        // which is the only thing past column 15 (the aside HP box's own
        // column, see `hp_col`) still needs clearing: cols 15..24 the gauge
        // reached that the window's 15-wide map does not cover. Measured
        // (this ticket): sweeping the full 0..32 here read 32768px over
        // tools/regress.py's window+card (a diagonal backdrop bleed through
        // the card's own picture region, its tiles wiped a frame after
        // `open()` drew them); 15..32 reads 0.
        for col in 15..32 {
            for row in 0..2 {
                bg.set_tile(
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
    pub fn set_hp(&mut self, bg: &mut RegularBackground, hp: u16) {
        if self.shown == Some(hp) {
            return;
        }
        self.shown = Some(hp);
        let base = self.hp_col();
        // The right cap is the left one MIRRORED, as the real ROM's map has
        // it: same tile pair with h-flip set.
        self.cell_flipped(bg, base, CAP_PAIR, false);
        self.cell_flipped(bg, base + 1 + SLOTS, CAP_PAIR, true);
        let mut left = hp;
        for slot in (0..SLOTS).rev() {
            let pair = if left == 0 && slot + 1 != SLOTS {
                BLANK_PAIR
            } else {
                (left % 10) as u16
            };
            left /= 10;
            self.cell(bg, base + 1 + slot, pair);
        }
    }

    /// Paint one two-tile column of the box.
    fn cell(&mut self, bg: &mut RegularBackground, col: u32, pair: u16) {
        self.cell_flipped(bg, col, pair, false);
    }

    fn cell_flipped(&mut self, bg: &mut RegularBackground, col: u32, pair: u16, hflip: bool) {
        for half in 0..2u16 {
            bg.set_tile(
                (col as i32, half as i32),
                &self.tiles,
                TileSetting::new(pair * 2 + half, TileEffect::new(hflip, false, BANK)),
            );
        }
    }

}
