//! The battle backdrop: the layer the real ROM keeps on BG1 at priority 3,
//! behind the field.
//!
//! A 32x32 tile map of a teal-arc motif on navy, all in one palette bank with
//! no flipped tiles. It scrolls one pixel left every two frames and one pixel
//! up every four, measured against the real ROM as a rigid shift with zero
//! residual, so the offset is kept in quarters of a pixel and advances by two
//! and one each frame.
//!
//! AND ITS ART IS ANIMATED, ON A COMPLETELY SEPARATE CLOCK FROM THE SCROLL.
//! The map, the palette and the scroll all stand still while the TILE ART
//! underneath cycles through seven complete sets of the layer's 37 tiles --
//! the little purple glyphs inside the rings. Dumping BG1's char data frame
//! by frame off a live battle shows 36 of the 37 tiles changing while the
//! map's 1024 entries and palette bank 0 never move. A still backdrop
//! differs from the real ROM by about 280 px a frame.
//!
//! THE MECHANISM (TODO A7). The scroll is `BGScrollCB_BG1Diagonal3to2Scroll`
//! off `eBGScrollCBCounters`, zeroed once at battle init
//! (`sub_8080D90`/`sub_8080DA0`, reference/bn6f/asm/asm00_1.s:8434-8435). The
//! art is a SECOND system entirely -- the same "GFXAnim" engine the overworld
//! maps use for their own animated tiles (`LoadGFXAnim`/`ProcessGFXAnims`,
//! reference/bn6f/asm/asm00_0.s:3510-3697) -- driven by a per-slot countdown
//! `Timer` in `eGFXAnimStates` (0x020094c0,
//! reference/bn6f/include/structs/GFXAnimState.inc) that `ProcessGFXAnims`
//! decrements every frame and, on hitting zero, advances to the next scripted
//! entry and copies its 36 tiles in with `sub_8001C94`. `LoadGFXAnims` IS
//! called at battle init, in the very same routine as the scroll's zero
//! (reference/bn6f/asm/asm21.s:33/37, called from the same `sub_8080DA0`), so
//! it DOES share the scroll's origin -- but the schedule it loads is not a
//! rigid multiple of the scroll's clock, so locking the two together with one
//! shared counter and a constant step length was still wrong.
//!
//! Confirmed for this fixture (three Mettaurs) by peeking
//! `eGFXAnimStates[0]` off `/tmp/battlestart.state`: `Param0` (gfx_src) =
//! 0x08617488 = `dword_8617488`, the same blob `backdrop_export.py` reads,
//! and `Param3` (buffer_index) = 5 -- exactly `off_807FB98`,
//! reference/bn6f/data/dat20.s:140-172 (battle background type 9 in the
//! per-type table at reference/bn6f/asm/asm21.s:389-411). Its schedule is
//! NOT a uniform "8 frames, 7 steps in order": stepped frame by frame from
//! the save state (dumping `eGFXAnimStates[0]` after 0, 1, 2, ... real
//! frames), it opens with nine 4-frame beats alternating two arrangements,
//! one more 4-frame beat on a third, and only THEN settles into a steady
//! 7-step, 8-frame-per-step cycle that repeats for the rest of a 192-frame
//! supercycle before looping back to the opening beats. `STEP_ORDER` and
//! `STEP_HOLD` below are that schedule, read off directly (see their own
//! comment for the exact correspondence to the asset's 7 steps).
//!
//! `tiles` only ever samples deep into a battle (`pausedwithcannon.state` is
//! 7891 frames in), safely inside the steady part, which is why the OLD
//! constant-8-frames-forever model could still land on it exactly while
//! missing the whole opening `demo-open` measures. And at the instant battle
//! init completes -- before this build's first simulated frame -- the real
//! ROM is not at the schedule's very start either: `LoadGFXAnim` performs its
//! first tile copy SYNCHRONOUSLY (using the schedule's first entry), and by
//! the time a save state can even be taken, `ProcessGFXAnims` has already
//! ticked once more (`Timer` reads 3 of a fresh 4, peeked). `Backdrop::prime`
//! reproduces both of those before the first `update()`.

use agb::display::tiled::{
    RegularBackground, RegularBackgroundSize, TileEffect, TileFormat, TileSet, TileSetting,
};
use agb::display::{Graphics, GraphicsFrame, Palette16, Priority, Rgb15};

/// Quarter-pixels of scroll per frame, across and down.
const SCROLL_X_Q: u32 = 2; // provenance: peeked -- measured against the real ROM as a rigid shift, zero residual (see the module doc above)
const SCROLL_Y_Q: u32 = 1; // provenance: peeked -- measured against the real ROM as a rigid shift, zero residual (see the module doc above)

/// The art animation's schedule, read directly off `off_807FB98`
/// (reference/bn6f/data/dat20.s:140-172): one entry per
/// `gfx_anim_data_ptr`, naming which of the asset's 7 steps it shows and how
/// many frames it holds. The asset's own step order (`backdrop_export.py`'s
/// `FRAMES`) was built by matching each of the disassembly's 7 distinct
/// 36-tile tables byte for byte: step 0 is `byte_807FE40`, 1 `byte_807FCD8`,
/// 2 `byte_807FC90`, 3 `byte_807FD20`, 4 `byte_807FD68`, 5 `byte_807FDB0`, 6
/// `byte_807FDF8`. In that numbering the script's 29 entries are steps
/// 2,1,2,1,2,1,2,1,2,3, then 4,5,6,0,1,2,3 repeating -- nine 4-frame beats
/// alternating steps 2 and 1, one 4-frame beat on step 3, then a steady
/// 7-step cycle at 8 frames each -- for 192 frames total before the whole
/// thing loops. Confirmed empirically, not just statically: dumping
/// `eGFXAnimStates[0]` after 0, 1, 2, ... real frames from
/// `/tmp/battlestart.state` walks these exact entries at these exact
/// lengths.
// provenance: derived -- off_807FB98 (reference/bn6f/data/dat20.s:140-172),
// cross-checked empirically by dumping eGFXAnimStates[0] frame by frame off
// /tmp/battlestart.state (see the doc comment above).
const STEP_ORDER: [u16; 29] = [
    2, 1, 2, 1, 2, 1, 2, 1, 2, 3, 4, 5, 6, 0, 1, 2, 3, 4, 5, 6, 0, 1, 2, 3, 4, 5, 6, 0, 1,
];
const STEP_HOLD: [u16; 29] = [
    4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8,
]; // provenance: derived -- same source as STEP_ORDER above

pub struct Backdrop {
    bg: RegularBackground,
    tiles: TileSet,
    slots: u16,
    /// The step whose art is in vram.
    step: u16,
    /// Which entry of `STEP_ORDER`/`STEP_HOLD` is playing, and how many more
    /// frames it has left including this one -- named after the real ROM's
    /// own `GFXAnimState.CommandPos`/`Timer`, which this mirrors frame for
    /// frame rather than deriving from a formula.
    entry: usize,
    timer: u16,
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

        debug_assert!(
            STEP_ORDER.iter().all(|&s| s < steps),
            "STEP_ORDER names a step the asset does not have"
        );

        Self {
            bg,
            tiles: tileset,
            slots,
            // Whatever the tileset's raw upload leaves resident -- step 0 --
            // until `prime` corrects it to what the real ROM actually shows
            // at battle init.
            step: 0,
            entry: 0,
            // STEP_HOLD[0] + 1, not STEP_HOLD[0]. The real ROM's own clock
            // reads entry 0 / Timer 3 at the frame its scroll counters read
            // zero, but this build creates its backdrop two frames into the
            // battle it is being compared with, so it starts two frames
            // further back. MEASURED: with this value `opening` compares 40
            // consecutive frames at exactly 0, and one frame either side of
            // it measures 8102 and 24398. provenance: derived -- the "+1" has
            // a stated mechanism (this build's own two-frame-later backdrop
            // construction), confirmed rather than merely fitted by the
            // 40-frame/8102/24398 sweep above.
            timer: STEP_HOLD[0] + 1,
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

    /// Bring the art to the real ROM's state at a battle's first frame,
    /// before this build's first `update()` call. `LoadGFXAnim` performs its
    /// first tile copy SYNCHRONOUSLY at battle init -- the schedule's entry
    /// 0 -- and by the time a save state can be taken, `ProcessGFXAnims` has
    /// already ticked once more (`Timer` reads 3 of a fresh 4, peeked off
    /// `/tmp/battlestart.state`). Without this the map opens on whichever
    /// step the raw tileset upload happens to leave resident and one frame
    /// later than the real ROM besides.
    /// Start where the CAPTURE is, not at zero.
    ///
    /// A demo fixture is compared against a save state taken thousands of
    /// frames into someone else's battle, and the backdrop's two clocks are
    /// battle-relative -- so a fixture that starts them at zero is comparing
    /// two different moments and can only ever agree by coincidence. That is
    /// exactly what happened: the old, wrong art model had a 56-frame period
    /// which divides the scroll's 896, so it coincided at a fixed frame and
    /// every fixture was quietly calibrated on that coincidence. With the real
    /// 192-frame schedule the coincidence is gone and the fixtures need the
    /// state's own phase instead.
    ///
    /// Peeked out of /tmp/pausedwithcannon.state at load: `eGFXAnimStates[0]`
    /// is on entry 5 with Timer 4 (CommandPos 0x0807FBCC against LoopAddress
    /// 0x0807FBA4, eight bytes an entry), and `eBGScrollCBCounters` reads
    /// -63128 / -31564, which `lsr #4` turns into scroll registers 150 and 75.
    /// The quarter-pixel counters that reproduce those are 424 and 724.
    ///
    /// Same move as `HUDMATCH_HP` carrying the capture's 60 rather than a
    /// fresh navi's 100, and as 7bc's chip-window bracket.
    pub fn seed(&mut self, entry: usize, timer: u16, x_q: u32, y_q: u32) {
        self.entry = entry;
        // Plus the same construction lead `new` builds into its own fresh
        // timer (STEP_HOLD[0] + 1, see above): the seed is applied at
        // construction, one tick before the battle moment the peeked Timer
        // describes, so the peeked value would fire every art step one frame
        // early. Measured: with the bare peeked Timer 4 the `tiles`/`gauge`
        // rows read k=0..6 at 0 and 208 px at k=7 -- our art upload lands
        // where canon's frame-52 upload lands one aligned frame early
        // (watch-write both sides; canon's copy goes through
        // QueueEightWordAlignedGFXTransfer, reference/bn6f/asm/asm00_0.s:3752
        // sub_8001C94) -- and with this +1 it lands on canon's frame.
        // Unseeded battles are untouched (`opening` stays 0).
        self.timer = timer + 1; // provenance: derived -- same construction-lead mechanism as new()'s STEP_HOLD[0] + 1 (build ticks once before the peeked battle moment); tiles k=7 208 -> 0
        self.x_q = x_q;
        self.y_q = y_q;
    }

    /// The state-trace export (T1): the backdrop's GFX-anim position and
    /// scroll phase in one call -- `entry`/`timer` mirror canon's
    /// eGFXAnimStates[0] CommandPos/Timer walk (see the row-note on
    /// F26b's seeds), `x_q`/`y_q` the quarter-pixel scroll phase canon's
    /// eBGScrollCBCounters hold as -8f/-4f (same note). Read-only.
    pub fn trace_state(&self) -> (u16, u16, u32, u32) {
        (self.entry as u16, self.timer, self.x_q, self.y_q)
    }

    /// Draw the step the clocks are already on. It deliberately does NOT set
    /// the timer: `new` establishes it and `seed` may have overridden it, and
    /// an earlier version of this wrote it here and silently discarded every
    /// seeded value.
    pub fn prime(&mut self, gfx: &Graphics) {
        self.show_step(gfx, STEP_ORDER[self.entry]);
    }

    fn show_step(&mut self, gfx: &Graphics, want: u16) {
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
    }

    /// Advance the scroll and the art animation by one frame. The two are
    /// driven by completely separate clocks on the real ROM (see the module
    /// doc) and stay that way here: the scroll is unconditional every frame,
    /// while the art only steps when its own countdown, seeded by `prime`,
    /// reaches zero.
    pub fn update(&mut self, gfx: &Graphics) {
        self.timer -= 1;
        if self.timer == 0 {
            self.entry = (self.entry + 1) % STEP_ORDER.len();
            self.timer = STEP_HOLD[self.entry];
            self.show_step(gfx, STEP_ORDER[self.entry]);
        }

        // The wrap period: canon's own scroll counters (oBGScrollCBCounters,
        // driven by BGScrollCB_BG1Diagonal3to2Scroll at
        // reference/bn6f/asm/asm00_0.s:3305-3321, steps .equiv'd at :3293-3295)
        // run in 1/16-pixel units and turn over after 4096 counts = 256 px,
        // which is the 256-pixel period the notes above the .equiv block
        // record; ours here are quarter-pixel units, so the same period is
        // 256 px * 4. provenance: derived -- canon counter modulus via the
        // asm00_0.s notes; the 4 is this module's quarter-pixel scale (see
        // the module doc).
        const BACKDROP_SCROLL_PERIOD_Q: u32 = 256 * 4; // provenance: derived -- canon's 256-px counter period in quarter-pixel units
        self.x_q = (self.x_q + SCROLL_X_Q) % BACKDROP_SCROLL_PERIOD_Q;
        self.y_q = (self.y_q + SCROLL_Y_Q) % BACKDROP_SCROLL_PERIOD_Q;
        // The motif travels left and up, so the scroll position runs
        // negative: measured on the real ROM, a frame's image is the previous
        // one shifted, and matching the sign the other way scrolls it the
        // wrong way by the right amount.
        // TESTED AND CORRECT (F26b, 2026-09-13 -- the note that stood here
        // said this was an untested difference; it is not a difference at
        // all). canon's `BGScrollCB_BG1Diagonal3to2Scroll`
        // (reference/bn6f/asm/asm00_0.s:3287-3303) does `sub r2,#8` /
        // `lsr r2,r2,#4` / `strh` into RenderInfo Unk_10 (BG1HOFS), and the
        // counter is zeroed at battle init, so at battle frame f it holds
        // -8f and the register gets ((-8f) as u32) >> 4, whose low 9 bits are
        // -ceil(f/2) mod 512. This line computes -((x_q+3)/4) with x_q = 2f,
        // i.e. -ceil(2f/4) = -ceil(f/2): the SAME value, on even and odd
        // frames alike. `lsr` of a negative IS the floor of the signed
        // divide (2^28 higher, which the halfword store and the 9-bit
        // register both discard), and `(q+3)/4` on an unsigned q is a
        // ceiling, so negating it already floors. MEASURED, not argued: with
        // the phase seeded from canon's own counters, BG1 alone (--only-bg 1
        // on both sides) reads 0 on all 40 `windowclose` frames -- 20 of
        // them odd -- and 0 on 169 of `cursor`'s 170 (see that row's note
        // for the one frame, which is canon's mid-frame tile transfer, not
        // this arithmetic). The same y line is `lsr #4` of a counter falling
        // by 4, i.e. -ceil(f/4), which -((y_q+3)/4) with y_q = f reproduces.
        self.bg.set_scroll_pos((
            -(((self.x_q + 3) / 4) as i32),
            -(((self.y_q + 3) / 4) as i32),
        ));
    }

    /// Returns its background id, so a blend can include this layer -- the
    /// battle's opening whitens EVERY layer, not just the field's.
    pub fn show(&self, frame: &mut GraphicsFrame) -> agb::display::tiled::RegularBackgroundId {
        self.bg.show(frame)
    }
}
