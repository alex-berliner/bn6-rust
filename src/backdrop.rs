//! The battle backdrop: the layer the real ROM keeps on BG1 at priority 3,
//! behind the field.
//!
//! A 32x32 tile map of a teal-arc motif on navy, all in one palette bank with
//! no flipped tiles. It scrolls one pixel left every two frames and one pixel
//! up every four, measured against the real ROM as a rigid shift with zero
//! residual, so the offset is kept in quarters of a pixel and advances by two
//! and one each frame.
//!
//! AND ITS ART IS ANIMATED. The map, the palette and the scroll all stand
//! still while the TILE ART underneath cycles: seven complete sets of the
//! layer's 37 tiles, eight frames each, a 56-frame loop -- the little purple
//! glyphs inside the rings. Dumping BG1's char data frame by frame off a live
//! battle shows 36 of the 37 tiles changing while the map's 1024 entries and
//! palette bank 0 never move. A still backdrop differs from the real ROM by
//! about 280 px a frame.
//! NOT VERIFIED: where the loop starts. One save state cannot say what the
//! phase is counted from, so this build counts from the battle's first frame.

use agb::display::tiled::{
    RegularBackground, RegularBackgroundSize, TileEffect, TileFormat, TileSet, TileSetting,
};
use agb::display::{Graphics, GraphicsFrame, Palette16, Priority, Rgb15};

/// Quarter-pixels of scroll per frame, across and down.
const SCROLL_X_Q: u32 = 2;
const SCROLL_Y_Q: u32 = 1;
/// Frames each step of the art animation is held.
const STEP_FRAMES: u32 = 8;
/// Where in a step the loop starts. The scroll advances a pixel every two
/// frames across and every four down, so choosing which frame to compare on
/// can only move the art by four; the other offsets have to be built in.
const ART_PHASE: u32 = 0;

pub struct Backdrop {
    bg: RegularBackground,
    tiles: TileSet,
    /// Steps in the art animation, and how many tiles each holds.
    steps: u16,
    slots: u16,
    /// The step whose art is in vram, and the frame counter driving it.
    step: u16,
    ticks: u32,
    palette: Palette16,
    /// Scroll position in quarters of a pixel, so the half- and quarter-pixel
    /// steps stay exact rather than drifting.
    x_q: u32,
    y_q: u32,
}

impl Backdrop {
    pub fn new(data: &'static [u8]) -> Self {
        assert_eq!(&data[0..4], b"BNBD", "not a BNBD asset");
        let at = |o: usize| u32::from_le_bytes(data[o..o + 4].try_into().unwrap()) as usize;
        let (t, m, p) = (at(0x08), at(0x0c), at(0x10));
        let (steps, slots) = (at(0x14) as u16, at(0x18) as u16);

        let tiles_len = u32::from_le_bytes(data[t..t + 4].try_into().unwrap()) as usize;
        let tiles = &data[t + 4..t + 4 + tiles_len];
        assert_eq!(
            tiles.as_ptr() as usize % 4,
            0,
            "tile data must be word aligned"
        );
        // SAFETY: alignment asserted above, and the length is a whole number
        // of 4bpp tiles by construction of the exporter.
        let tileset = unsafe { TileSet::new(tiles, TileFormat::FourBpp) };

        let mut colours = [Rgb15::new(0); 16];
        for (i, slot) in colours.iter_mut().enumerate() {
            let o = p + i * 2;
            *slot = Rgb15::new(u16::from_le_bytes(data[o..o + 2].try_into().unwrap()));
        }
        let palette = Palette16::new(colours);

        let mut bg = RegularBackground::new(
            Priority::P3,
            RegularBackgroundSize::Background32x32,
            TileFormat::FourBpp,
        );
        for row in 0..32 {
            for col in 0..32 {
                let o = m + (row * 32 + col) * 2;
                let id = u16::from_le_bytes(data[o..o + 2].try_into().unwrap());
                bg.set_tile(
                    (col as i32, row as i32),
                    &tileset,
                    TileSetting::new(id, TileEffect::new(false, false, 0)),
                );
            }
        }

        Self {
            bg,
            tiles: tileset,
            steps,
            slots,
            step: 0,
            ticks: 0,
            palette,
            x_q: 0,
            y_q: 0,
        }
    }

    /// The single background palette bank the backdrop draws in, bank 0 on
    /// the real ROM.
    pub fn palette(&self) -> Palette16 {
        self.palette.clone()
    }

    /// Advance the scroll and the art animation by one frame.
    pub fn update(&mut self, gfx: &Graphics) {
        self.ticks += 1;
        let want = (((self.ticks + ART_PHASE) / STEP_FRAMES) % u32::from(self.steps)) as u16;
        if want != self.step {
            // The map still names the first step's tiles, so those stay the
            // key and only the bytes behind them change: agb keys vram by
            // (tileset, tile index) and replace_tile rewrites the pixels in
            // place, which is what the real ROM does too -- its map never
            // moves.
            for k in 0..self.slots {
                gfx.replace_tile(&self.tiles, k, &self.tiles, want * self.slots + k);
            }
            self.step = want;
        }
        self.x_q = (self.x_q + SCROLL_X_Q) % (256 * 4);
        self.y_q = (self.y_q + SCROLL_Y_Q) % (256 * 4);
        // The motif travels left and up, so the scroll position runs
        // negative: measured on the real ROM, a frame's image is the previous
        // one shifted, and matching the sign the other way scrolls it the
        // wrong way by the right amount.
        self.bg
            .set_scroll_pos((-((self.x_q / 4) as i32), -((self.y_q / 4) as i32)));
    }

    pub fn show(&self, frame: &mut GraphicsFrame) {
        self.bg.show(frame);
    }
}
