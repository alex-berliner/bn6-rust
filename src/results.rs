//! The window shown when a battle ends.
//!
//! sub_802C34E (asm/asm03_0.s:12353) puts up the RESULT window after the
//! last enemy is deleted, or the LOSER window when the player is: a 24x18
//! tilemap in palette bank 9 that is redrawn into the tilemap at column j
//! = -30, +2 columns a frame, until it rests at column j = 3, then waits for A or Start, holds 0x14 more
//! frames and fades the screen out (sub_802C280, asm03_0.s:12234). The clear
//! time is five BCD digits written right to left at row 4, columns 20, 19,
//! 17, 16 and 14 as two-tile-tall glyphs from tile 0xa0, in palette bank
//! 9 + rank (sub_802C4E8, asm03_0.s:12558; byte_802C538).

use agb::display::Priority;
use agb::display::tiled::{
    MappedTile, RegularBackground, RegularBackgroundSize, TileEffect, TileFormat, TileSet, TileSetting,
};
use agb::display::{Palette16, Rgb15};
use alloc::vec::Vec;

const MAGIC: &[u8; 4] = b"BNRS";
pub const WIN: usize = 0;
pub const LOSE: usize = 1;
/// How many window variants the blob carries: RESULT and LOSER.
const VARIANT_N: usize = 2; // provenance: derived -- tools/results_export.py packs len(VARIANTS) = 2, and Results::new asserts the count
/// BNRS blob header offsets (tools/results_export.py's `<4sIII`: MAGIC,
/// version, variant count, palette offset).
const BNRS_COUNT_OFF: usize = 0x08; // provenance: derived -- tools/results_export.py
const BNRS_PAL_OFF: usize = 0x0c; // provenance: derived -- tools/results_export.py
/// Where the first variant starts: past the 16-byte header.
const BNRS_VARIANT_OFF: usize = 0x10; // provenance: derived -- tools/results_export.py
/// A blob u32 field's width in bytes.
const BLOB_U32: usize = 4; // provenance: derived -- tools/results_export.py's struct widths
/// The exporter's alignment: every blob section is padded to a word.
const BLOB_ALIGN: usize = 4; // provenance: derived -- tools/results_export.py pads len(out) % 4, and Results::new asserts word alignment
/// A variant map's own header: the w and h u32s ahead of the u16 cells.
const BNRS_MAP_HEAD: usize = 8; // provenance: derived -- tools/results_export.py's struct.pack("<II", 24, 18)
/// A map cell is one u16 id.
const CELL_BYTES: usize = 2; // provenance: derived -- tools/results_export.py's w*h u16 map
/// A GBA 4bpp tile's bytes.
const TILE_BYTES: usize = 32; // provenance: derived -- GBA 4bpp tile size (tools/results_export.py's FONT_TILE * 32 padding)
/// The palette the blob appends: four banks of sixteen 2-byte colours --
/// the window's banks 9-11 plus the reward picture's bank 12.
const PAL_BANKS: usize = 4; // provenance: derived -- tools/results_export.py appends dword_8732814 (96 B) + dword_8733394 (32 B)
const PAL_COLORS: usize = 16; // provenance: derived -- GBA palette bank size
const PAL_BANK_BYTES: usize = 32; // provenance: derived -- 16 colours of 2 bytes (see above)
const PAL_BYTES: usize = PAL_BANKS * PAL_BANK_BYTES; // provenance: derived -- four banks (see above)
const PAL_ENTRY_BYTES: usize = 2; // provenance: derived -- a GBA palette entry is one u16
/// BNTF blob (tools/text_font_export.py's `<4sII`: MAGIC, version, tiles
/// offset): the glyph-table pointer and the two halves it points at --
/// the raw glyphs, then the same glyphs with 8 added to every nibble.
const FONT_MAGIC: &[u8; 4] = b"BNTF"; // provenance: derived -- tools/text_font_export.py
const BNTF_TABLE_OFF: usize = 0x08; // provenance: derived -- tools/text_font_export.py
const FONT_HALVES: usize = 2; // provenance: derived -- tools/text_font_export.py keeps tiles + colour-shifted copy

/// Where the window rests, measured against the real ROM by aligning the two
/// windows: 24 px right and 16 px down of what this build had, which is 3
/// TILES and 2 tiles -- the disassembly's 3 is a tile column, not a pixel.
const REST_X: i32 = 24; // provenance: peeked -- aligned against the real ROM's own window (see the doc comment above)
/// The slide counter's own units are TILE COLUMNS, not pixels: `sub_802C34E`
/// stores 0xe2 (-30) to `[r5,#6]` and the slide tick `sub_802BE36` adds 2 to
/// that signed byte (`ldrsb`), so the screen x this build keeps is the column
/// times 8. The old 2-px step had read the column step as pixels.
const START_X: i32 = -240; // provenance: derived -- sub_802C34E's 0xe2 (asm03_0.s:12425) times 8
const SLIDE_STEP: i32 = 16; // provenance: derived -- sub_802BE36's +2 columns (asm03_0.s:11670) times 8; the capture's own right edge moves 16 px/frame (47+16k)
/// Frames between setup and the first slide tick: canon holds j=-30 from
/// setup through its frame 15 and ticks during 16..32 (right-edge fit).
const SLIDE_HOLD: u8 = 16; // provenance: peeked -- first slide tick during canon frame 16; which driver timer holds it there was not identified
/// The window's own map size in cells, and the BG map strip the slide
/// rewrite covers: the full 32-cell map width, the window's 18 rows.
const WIN_W: usize = 24; // provenance: derived -- BNRS variant maps are 24x18 cells (Results::new reads w, h)
const WIN_H: usize = 18; // provenance: derived -- BNRS variant maps are 24x18 cells (Results::new reads w, h)
const MAP_W: usize = 32; // provenance: derived -- Background32x32 map width chosen in Results::show
/// Pixels per tile column: `Shown::slide_x` keeps pixels, the map works in
/// columns, so the blit divides by this.
const TILE_PX: i32 = 8; // provenance: derived -- GBA background tile size
/// Where the rewrite block lands in the BG map: top-left, like the old
/// per-tile loop's (col, row) origin.
const MAP_ORIGIN: (i32, i32) = (0, 0); // provenance: derived -- the slide redraw covers map rows 0..18, cols 0..32 from the origin
/// `Shown::cells` tags: which tileset a stored raw map entry belongs to --
/// the window's own tiles, the battle text font, the reward picture. A local
/// encoding, not ROM data.
const CELL_BASE: u8 = 0;
const CELL_FONT: u8 = 1;
const CELL_REWARD: u8 = 2;
/// And two tile rows down.
const Y: i32 = 16; // provenance: peeked -- aligned against the real ROM's own window (see the doc comment above)
const DISMISS_FRAMES: u8 = 0x14; // provenance: derived -- sub_802C280, asm03_0.s:12234
/// The dismissal fade's step count (see `Phase::Fading`).
const FADE_STEPS: u8 = 16; // provenance: derived -- sub_802C280's own SetScreenFade 0x10
/// The clear time is capped at 9'59"99 (dword_802C548).
const TIME_CAP: u32 = 0x95999; // provenance: derived -- dword_802C548
/// The clear time is stored in frames at the GBA's rate; the readout splits
/// it into minutes, seconds and hundredths for the BCD digits below.
const FPS: u32 = 60; // provenance: derived -- GBA frame rate (t.time counts frames)
const CENTIS_PER_SEC: u32 = 100; // provenance: derived -- the readout's hundredths digit (see show)
const SECS_PER_MIN: u32 = 60; // provenance: derived -- sixty seconds to the minute (see show)
const MINUTE_FRAMES: u32 = 3600; // provenance: derived -- 60 fps times 60 s (see above)
/// The readout caps at a single minutes digit (9'59"99 is the cap above).
const TIME_MINUTES_MAX: u32 = 9; // provenance: derived -- single-digit minute readout capped by TIME_CAP
/// The time digits' row: the five BCD digits sit two tiles tall at row 4
/// (module doc; sub_802C4E8).
const TIME_ROW: i32 = 4; // provenance: derived -- sub_802C4E8, asm03_0.s:12558
/// The bank the time digits draw in: palette bank 9, recoloured by rank.
const TIME_BANK: u16 = 9; // provenance: derived -- sub_802C4E8, asm03_0.s:12558
/// The time's record colour rank runs 0-2 (see `show`).
const RANK_MAX: u8 = 2; // provenance: derived -- rank 0-2 recolours the time digits (see show)
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
/// The z glyph's column: past the last digit column, skipping the blank
/// column 10 between the amount (7-9) and the z (11).
const REWARD_Z_COL: i32 = REWARD_TEXT_LAST + 2; // provenance: peeked -- read off the capture's own map ("100 z" at columns 7-9 and 11)
const ZENNY_GLYPH: u16 = 0xb3; // provenance: peeked -- found by searching all 448 glyphs of the real ROM's own font for the reward line's symbol
/// The ten cells at window column 2, row 14 that canon's `sub_802C810`
/// (reference/bn6f/asm/asm03_0.s:13013-13038) owns: it calls
/// `sub_802C4B6(x=2, y=0xe, src, w=0xa, h=1)` with one of two ten-entry
/// tables, `byte_802C834` (asm03_0.s:13029, ten copies of tile 0xc4 with
/// attribute 0x90 = palette bank 9 -- the flat window face) for state 0 and
/// `byte_802C848` (asm03_0.s:13033, tiles 0xba..0xc3 in the same bank -- the
/// "PRESS A BUTTON" prompt) for state 1. The window's own SETUP map is
/// neither: its cells there carry the face's lit top pixel row, which is
/// what shows until the driver reaches its wait state and calls
/// `sub_802C810` for the first time. Measured on this row (F34): canon's
/// window row 14 columns 2-11 read the setup map's lit line through the
/// slide and are rewritten flat from the first wait frame on.
const REWARD_EDGE_ROW: i32 = 14; // provenance: derived -- sub_802C810's r1 = 0xe (asm03_0.s:13018)
const REWARD_EDGE_FIRST: i32 = 2; // provenance: derived -- sub_802C810's r0 = 2 (asm03_0.s:13017)
/// How many cells the run covers -- `sub_802C810`'s `mov r3, #0xa`.
const PROMPT_W: usize = 10; // provenance: derived -- sub_802C810's r3 = 0xa (asm03_0.s:13019)
/// How many runs `sub_802C810` chooses between: the flat face and the prompt (see above).
const PROMPT_STATES: usize = 2; // provenance: derived -- byte_802C834/byte_802C848 (asm03_0.s:13029/13033)
const REWARD_EDGE_LAST: i32 = REWARD_EDGE_FIRST + PROMPT_W as i32 - 1;
const REWARD_EDGE_TILE: u16 = 0x0c4; // provenance: derived -- byte_802C834's tile (asm03_0.s:13029)
/// The prompt's first tile; the ten run consecutively to 0xc3.
const PROMPT_TILE: u16 = 0x0ba; // provenance: derived -- byte_802C848 (asm03_0.s:13033)
/// Canon blinks the prompt on BIT 3 of the game's global frame counter:
/// `sub_802BF0C` (asm03_0.s:11810-11816) loads the halfword at
/// eToolkit+0x24 `CurFramePtr` (ewram.s:583; incremented once a frame by the
/// main loop, asm/main.s:24-28), `and`s 8, shifts it down by 3 and hands the
/// 0/1 to `sub_802C810` -- eight frames on, eight frames off, on a counter
/// that has been running since power-on.
const PROMPT_BLINK_BIT: u32 = 8; // provenance: derived -- sub_802BF0C's `mov r1,#8; and r0,r1` (asm03_0.s:11813-11814)
/// The phase of that counter at this build's own window frame 0. Canon's
/// counter is global and free-running, so it is a PER-ROW seed exactly like
/// the backdrop's `art_entry`/`scroll_xq` -- FIXTURE.md has no field for it
/// yet, so the one value measured lives here: on the `result` row's canon
/// capture (/tmp/result_arrival.state) the counter at 0x0200a210 reads
/// 0x22ef + f at capture frame f, and the map a frame writes is displayed
/// on the next frame (canon renders at the top of its main loop, asm/main.s
/// :15-28), so the state showing on canon frame f is bit 3 of 0x22ee + f;
/// the row's canon_ref is 21, giving 0x2303 + k over the compared frames.
/// It BELONGS IN THE DESCRIPTOR (FIXTURE.md, next to art_entry/scroll_xq):
/// any other fixture aimed at a canon capture of this window will need its
/// own value, and a real battle's is whatever the counter happens to read.
const PROMPT_BLINK_SEED: u32 = 0x2303_u32.wrapping_sub(PROMPT_WINDOW_FRAME_AT_K0); // provenance: peeked -- canon's own eToolkit CurFrame at this row's canon_ref (see above)
/// CONFIRMED by a second pass (F34): watched at 0x0200a210 on this row's own
/// canon capture, the halfword reads 0x22ef at canon frame 0 and +1 every
/// frame after, so bit 3 flips at canon frames 41, 49 and 57; canon's OWN
/// pixels inside the ten cells change one frame later -- 249 px at canon
/// 42, 50 and 58 (k=21, 29, 37 of the compared window) -- and ours change on
/// exactly those frames, with the first `sub_802C810` write (80 px, the
/// setup map's lit line giving way to `byte_802C834`'s flat face) landing on
/// k=14 on both sides.
/// What this window's own `frames` reads at that same moment: the window is
/// created on the fixture's first battle frame, which is the rust capture's
/// marker origin, and the row pairs canon 21+k with rust origin+21+k, so at
/// k=0 `frames` has been ticked 21 times plus this frame's own tick.
const PROMPT_WINDOW_FRAME_AT_K0: u32 = 22; // provenance: peeked -- this row's own alignment (origin+21 <-> canon 21), confirmed by the blink's measured edges (F34)
/// Frames canon spends between the slide's last tick and the first
/// `sub_802C810` call: the wait state is not entered directly. The slide
/// tick hands over with `[r5,#3]` = 0, which is `sub_802BED4`
/// (asm03_0.s:11739-11769) for one frame; it leaves `[r5,#0xb]` = 1 (the
/// `[r5,#0xc]` non-zero path, asm03_0.s:11757-11762) and `[r5,#3]` = 4,
/// which is `sub_802BEFC` (asm03_0.s:11772-11782) for one more frame before
/// it sets `[r5,#3]` = 8 and `sub_802BF0C` starts blinking.
const PROMPT_WAIT_LEAD: u32 = 2; // provenance: derived -- sub_802BED4 one frame + sub_802BEFC's [r5,#0xb]=1 (asm03_0.s:11739-11782)
const FONT_TILE: u16 = 0xa0; // provenance: derived -- sub_802C4E8, asm03_0.s:12558
/// The level readout sits at row 6, columns 16-20, its digits right-aligned;
/// level 0xb is the S rank, one glyph at tiles 0xb6/0xb7 in bank 10
/// (sub_802C6EC, asm03_0.s:12830-12888).
const LEVEL_ROW: i32 = 6; // provenance: derived -- sub_802C6EC, asm03_0.s:12830-12888
const LEVEL_COL: i32 = 16; // provenance: derived -- sub_802C6EC, asm03_0.s:12830-12888
const S_TILE: u16 = 0xb6; // provenance: derived -- sub_802C6EC, asm03_0.s:12830-12888
pub const LEVEL_S: u8 = 0xb; // provenance: derived -- sub_802C6EC, asm03_0.s:12830-12888
/// The level readout's last column: digits end at column 20 (see above).
const LEVEL_LAST_COL: i32 = 20; // provenance: derived -- sub_802C6EC, asm03_0.s:12830-12888
/// The banks the level readout draws in: normal digits in 9, the S glyph in 10.
const LEVEL_BANK: u16 = 9; // provenance: derived -- sub_802C6EC, asm03_0.s:12830-12888
const LEVEL_S_BANK: u16 = 10; // provenance: derived -- sub_802C6EC, asm03_0.s:12830-12888
/// A two-tile-tall glyph's half count: top tile over bottom tile.
const GLYPH_TILES: u16 = 2; // provenance: derived -- two-tile-tall glyphs (module doc; sub_802C4E8)

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
/// The busting-level time gates in seconds and the base each grants, the hit
/// count that still grants its point, and the floors (see `busting_level`).
const BUST_FAST_S: u32 = 5; // provenance: derived -- off_800ADDC/byte_800AE00 (see busting_level)
const BUST_MID_S: u32 = 12; // provenance: derived -- off_800ADDC/byte_800AE00 (see busting_level)
const BUST_SLOW_S: u32 = 36; // provenance: derived -- off_800ADDC/byte_800AE00 (see busting_level)
const BUST_BASE_FAST: i32 = 6; // provenance: derived -- off_800ADDC/byte_800AE00 (see busting_level)
const BUST_BASE_MID: i32 = 5; // provenance: derived -- off_800ADDC/byte_800AE00 (see busting_level)
const BUST_BASE_SLOW: i32 = 4; // provenance: derived -- off_800ADDC/byte_800AE00 (see busting_level)
const BUST_BASE_FLOOR: i32 = 3; // provenance: derived -- off_800ADDC/byte_800AE00 (see busting_level)
const BUST_HIT_CAP: u8 = 4; // provenance: derived -- sub_800AC20: four hits bottoms the bonus (see busting_level)
const BUST_HIT_FLOOR: i32 = -3; // provenance: derived -- sub_800AC20 (see busting_level)
const BUST_MOVE_CAP: u8 = 2; // provenance: derived -- sub_800AC20: moving at most twice grants the point (see busting_level)
const BUST_MOVE_BONUS: i32 = 1; // provenance: derived -- sub_800AC20 (see busting_level)
pub fn busting_level(t: &Tally) -> u8 {
    let seconds = t.time / FPS;
    let base: i32 = if seconds < BUST_FAST_S {
        BUST_BASE_FAST
    } else if seconds < BUST_MID_S {
        BUST_BASE_MID
    } else if seconds < BUST_SLOW_S {
        BUST_BASE_SLOW
    } else {
        BUST_BASE_FLOOR
    };
    let hit = match t.hits_taken {
        x if x < BUST_HIT_CAP => BUST_MOVE_BONUS - x as i32,
        _ => BUST_HIT_FLOOR,
    };
    let moved = if t.moves <= BUST_MOVE_CAP {
        BUST_MOVE_BONUS
    } else {
        0
    };
    (base + hit + moved).clamp(1, LEVEL_S as i32) as u8
}

struct Variant {
    tiles: TileSet,
    map: &'static [u8],
}

pub struct Results {
    variants: [Variant; VARIANT_N],
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
    Sliding { x: i32, hold: u8 },
    Waiting,
    /// The post-confirm reward reveal (WIN only): canon's `sub_802C044`
    /// (reference/bn6f/asm/asm03_0.s:11959) draws the 42 coin tiles one per
    /// frame in PrimaryRNG-shuffled order. This build draws the whole
    /// reward at once when the phase is entered (see `draw_reward`) and
    /// holds the phase for the same 42 frames.
    Revealing {
        left: u8,
    },
    /// The cooldown after the reveal: `sub_802C044` leaves `[r5,#0x0b]` =
    /// 0x1e (asm03_0.s:11764), counted down by `sub_802C0A4`
    /// (asm03_0.s:12010) and ending in the actual grant plus jingle --
    /// confirms are ignored throughout `Revealing` and this phase
    /// (measured: taps 30/60 frames after the first confirm do nothing,
    /// a tap ~90 after dismisses).
    Cooldown {
        ticks: u8,
    },
    /// Waiting for the second confirm, which dismisses.
    RewardWait,
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
    /// The window's own 24x18 cells as raw map entries plus which tileset
    /// each belongs to (`CELL_*`), so the slide can re-blit them at a new
    /// column the way canon's `CopyBackgroundTiles` redraw does.
    cells: [(u8, u16); WIN_W * WIN_H],
    /// The slide rewrite's pre-resolved map words, one per `cells` entry,
    /// plus the pinned VRAM tiles they point at. Rebuilt by
    /// `resolve_cells` whenever `cells` change (show, reward reveal), so
    /// the per-tick blit is one `copy_map_block`, not 576 VRAM-manager
    /// lookups. The guards must stay alive while `words`/`blank` are used.
    guards: Vec<MappedTile>,
    words: [u16; WIN_W * WIN_H],
    /// The off-window fill (variant tile 0), for map columns the window
    /// does not cover; `guards[0]` pins it.
    blank: u16,
    /// Set whenever the slide position moved (or at `show`); the battle
    /// re-blits through `Results::blit_slide` when it sees this.
    pub blit_needed: bool,
    phase: Phase,
    /// WIN vs LOSE (`Results::show`'s `variant`): only WIN ever draws a
    /// reward, so only WIN takes the post-confirm reveal path.
    variant: usize,
    /// The zenny amount to draw when the first confirm lands.
    zenny: u16,
    /// The two ten-cell runs `sub_802C810` chooses between, already resolved
    /// to map words (state 0 = the flat face, state 1 = the prompt), so the
    /// blink is ten `words` stores and a re-blit rather than a re-resolve.
    prompt: [[u16; PROMPT_W]; PROMPT_STATES],
    /// Which run is currently in `words`; `PROMPT_UNWRITTEN` until the
    /// driver's wait state writes one for the first time (canon's setup map
    /// stands until then).
    prompt_state: u8,
    /// Frames since the window went up -- the counterpart of canon's global
    /// frame counter for `PROMPT_BLINK_SEED`.
    frames: u32,
    /// Frames spent in `Phase::Waiting`, so the prompt run waits out
    /// `PROMPT_WAIT_LEAD` the way canon's two intermediate states do.
    wait_frames: u32,
}

/// `Shown::prompt_state` before the wait state has written either run.
const PROMPT_UNWRITTEN: u8 = 0xff;

/// Frames of the post-confirm reward reveal, one tile a frame:
/// `sub_802C044` (reference/bn6f/asm/asm03_0.s:11959) counts `[r5,#0x0b]`
/// from 0 to 0x2a (asm03_0.s:11850) with a blip every 4th frame.
const REVEAL_FRAMES: u8 = 42; // provenance: derived -- sub_802C044's 0x2a loop bound (asm03_0.s:11850)
/// Frames between reveal end and the dismiss-confirm arming: `[r5,#0x0b]`
/// = 0x1e (asm03_0.s:11764), counted down by `sub_802C0A4`
/// (asm03_0.s:12010), ending in the actual grant plus jingle (0x95/0x96).
const COOLDOWN_FRAMES: u8 = 30; // provenance: derived -- the 0x1e `sub_802C044` leaves (asm03_0.s:11764)
/// The RESULT mark's x for a slide position: canon enqueues it as
/// `([r5+6]*8+13) & 0x1ff` (`sub_802CA5C`, asm03_0.s:13225; the old
/// watch-write readings 509/13/29/37 are exactly this formula at
/// j=-2/0/2/3), so it rides the slide counter -- hidden off-screen right
/// while the window is still out, wrapped at j=-2, resting at 37. Passing
/// the possibly-negative value straight to OAM reproduces the masking.
const MARK_DX: i32 = 13; // provenance: derived -- sub_802CA5C's +13 (asm03_0.s:13225)

/// The mark's x for a window slide position `x` (pixels).
pub fn mark_x_at(slide_x: i32) -> i32 {
    slide_x + MARK_DX
}

impl Results {
    pub fn new(data: &'static [u8], font: &'static [u8]) -> Self {
        assert_eq!(&data[0..MAGIC.len()], MAGIC, "not a BNRS asset");
        let u32_at =
            |o: usize| u32::from_le_bytes(data[o..o + BLOB_U32].try_into().unwrap()) as usize;
        let count = u32_at(BNRS_COUNT_OFF);
        assert_eq!(count, VARIANT_N);
        let pal = u32_at(BNRS_PAL_OFF);
        let mut o = BNRS_VARIANT_OFF;
        let mut variant = || {
            o = (o + BLOB_ALIGN - 1) & !(BLOB_ALIGN - 1);
            let len = u32_at(o);
            let tiles = &data[o + BLOB_U32..o + BLOB_U32 + len];
            assert_eq!(
                tiles.as_ptr() as usize % BLOB_ALIGN,
                0,
                "tile data must be word aligned"
            );
            o = (o + BLOB_U32 + len + BLOB_ALIGN - 1) & !(BLOB_ALIGN - 1);
            let (w, h) = (u32_at(o), u32_at(o + BLOB_U32));
            let map = &data[o + BNRS_MAP_HEAD..o + BNRS_MAP_HEAD + w * h * CELL_BYTES];
            o += BNRS_MAP_HEAD + w * h * CELL_BYTES;
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
            palette: &data[pal..pal + PAL_BYTES],
            // SAFETY: the exporter 4-aligns the blob and emits whole tiles.
            reward: unsafe {
                TileSet::new(
                    &data[pal + PAL_BYTES..pal + PAL_BYTES + REWARD_TILES * TILE_BYTES],
                    TileFormat::FourBpp,
                )
            },
            font: {
                assert_eq!(&font[0..FONT_MAGIC.len()], FONT_MAGIC, "not a BNTF asset");
                let fo = u32::from_le_bytes(
                    font[BNTF_TABLE_OFF..BNTF_TABLE_OFF + BLOB_U32]
                        .try_into()
                        .unwrap(),
                ) as usize;
                let len =
                    u32::from_le_bytes(font[fo..fo + BLOB_U32].try_into().unwrap()) as usize;
                // The second half is the colour-added copy.
                let g = &font[fo + BLOB_U32 + len / FONT_HALVES..fo + BLOB_U32 + len];
                assert_eq!(
                    g.as_ptr() as usize % BLOB_ALIGN,
                    0,
                    "font must be word aligned"
                );
                // SAFETY: alignment asserted; the exporter emits whole tiles.
                unsafe { TileSet::new(g, TileFormat::FourBpp) }
            },
        }
    }

    /// The three palette banks the windows use, for background banks 9-11.
    pub fn palettes(&self) -> [Palette16; PAL_BANKS] {
        core::array::from_fn(|bank| {
            let mut colours = [Rgb15::new(0); PAL_COLORS];
            for (i, slot) in colours.iter_mut().enumerate() {
                // Banks 9-11 are the window's; the fourth is the reward
                // picture's bank 12, which the exporter appends.
                let o = bank * PAL_BANK_BYTES + i * PAL_ENTRY_BYTES;
                *slot = Rgb15::new(u16::from_le_bytes(
                    self.palette[o..o + PAL_ENTRY_BYTES].try_into().unwrap(),
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
            b'0'..=b'9' => 0x01 + (c - b'0') as u16, // canon: bn6-charmap.tbl digit base (see above)
            b'A'..=b'Z' => 0x0b + (c - b'A') as u16, // canon: bn6-charmap.tbl uppercase base (see above)
            b'a'..=b'z' => 0x26 + (c - b'a') as u16, // canon: bn6-charmap.tbl lowercase base (see above)
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
        let mut cells = [(CELL_BASE, 0u16); WIN_W * WIN_H];
        for i in 0..WIN_W * WIN_H {
            cells[i] = (
                CELL_BASE,
                u16::from_le_bytes(
                    v.map[i * CELL_BYTES..i * CELL_BYTES + CELL_BYTES]
                        .try_into()
                        .unwrap(),
                ),
            );
        }
        if variant == WIN {
            // Minutes, seconds and hundredths as BCD, least significant first.
            let frames = time.min(u32::MAX / CENTIS_PER_SEC);
            let hundredths = frames % FPS * CENTIS_PER_SEC / FPS;
            let seconds = frames / FPS % SECS_PER_MIN;
            let minutes = (frames / MINUTE_FRAMES).min(TIME_MINUTES_MAX);
            let mut bcd = hundredths % 10 // canon: BCD nibble packing (TIME_CAP is BCD: 9'59"99)
                | (hundredths / 10) << 4 // canon: BCD nibble packing (see above)
                | (seconds % 10) << 8 // canon: BCD nibble packing (see above)
                | (seconds / 10) << 12 // canon: BCD nibble packing (see above)
                | minutes << 16; // canon: BCD nibble packing (see above)
            bcd = bcd.min(TIME_CAP);
            for col in DIGIT_COLS {
                let d = (bcd & 0xf) as u16; // canon: BCD digit mask (see above)
                let top = FONT_TILE + d * GLYPH_TILES;
                let bank = TIME_BANK + rank.min(RANK_MAX) as u16;
                for (dy, tile) in [(0, top), (1, top + 1)] {
                    cells[(TIME_ROW + dy) as usize * WIN_W + col] =
                        (CELL_BASE, tile | bank << MAP_PAL_SHIFT);
                }
                bcd >>= 4; // canon: next BCD digit (see above)
            }
            // The level: S as its one glyph, else decimal digits right-aligned
            // to the readout's last column.
            let mut col = LEVEL_LAST_COL;
            if level >= LEVEL_S {
                for (dy, tile) in [(0, S_TILE), (1, S_TILE + 1)] {
                    cells[(LEVEL_ROW + dy) as usize * WIN_W + col as usize] =
                        (CELL_BASE, tile | LEVEL_S_BANK << MAP_PAL_SHIFT);
                }
            } else {
                let mut n = level.max(1);
                loop {
                    let top = FONT_TILE + (n % 10) as u16 * GLYPH_TILES; // unnamed: decimal digit extraction
                    for (dy, tile) in [(0, top), (1, top + 1)] {
                        cells[(LEVEL_ROW + dy) as usize * WIN_W + col as usize] =
                            (CELL_BASE, tile | LEVEL_BANK << MAP_PAL_SHIFT);
                    }
                    n /= 10; // unnamed: decimal digit extraction
                    if n == 0 {
                        break;
                    }
                    col -= 1;
                }
            }
        }
        // The reward (coin picture, amount line, edge row) is NOT drawn
        // here: canon draws it only after the first confirm -- `sub_802C34E`
        // (reference/bn6f/asm/asm03_0.s:12397) queues the window's static
        // GFX, the slide tick `sub_802BE36` (asm03_0.s:11666) draws only the
        // clear time (`sub_802C4E8`) and level (`sub_802C6EC`), and the
        // reward goes up one tile a frame in `sub_802C044`
        // (asm03_0.s:11959) once `[r5,#1]` reaches 4. See `draw_reward`.
        // Fixed scroll: the slide moves the tilemap cells, never the
        // register -- canon's own BG HOFS/VOFS shadows read a constant 0
        // throughout the arrival capture (battle.rs's bg3-merge comment),
        // because the driver redraws the map at the slide column instead.
        // Fresh cells already render as blank, and j=START_X/8 is fully
        // clipped, so there is nothing to blit until the first tick.
        bg.set_scroll_pos((0, -Y));
        let mut shown = Shown {
            bg,
            cells,
            guards: Vec::new(),
            words: [0; WIN_W * WIN_H],
            blank: 0,
            blit_needed: false,
            phase: Phase::Sliding {
                x: START_X,
                hold: SLIDE_HOLD,
            },
            variant,
            zenny,
            prompt: [[0; PROMPT_W]; PROMPT_STATES],
            prompt_state: PROMPT_UNWRITTEN,
            frames: 0,
            wait_frames: 0,
        };
        self.resolve_cells(&mut shown);
        shown
    }

    /// Draw the WIN reward content (coin picture, amount line, edge row)
    /// onto an already-shown window. Called once, when the first confirm
    /// lands (`Shown::poll_reward_reveal`); a no-op for LOSE, which has no
    /// reward. Canon reveals the 42 tiles progressively over REVEAL_FRAMES
    /// in shuffled order -- this draws them at once; post-confirm frames
    /// are compared by no live row, so the order is a follow-up, not here.
    pub fn draw_reward(&self, shown: &mut Shown) {
        if shown.variant != WIN {
            return;
        }
        let zenny = shown.zenny;
        let cells = &mut shown.cells;
        // The reward line: the amount right-aligned to the digit column,
            // a blank, then a 'z'. Read off the capture's map, whose "100 z"
            // fills window columns 7-9 and 11 of rows 12-13.
            let mut n = zenny;
            let mut col = REWARD_TEXT_LAST;
            loop {
                let g = Self::char_code(b'0' + (n % 10) as u8); // unnamed: decimal digit extraction
                for half in 0..GLYPH_TILES {
                    cells[(REWARD_TEXT_ROW + half as i32) as usize * WIN_W + col as usize] =
                        (CELL_FONT, g * GLYPH_TILES + half | (REWARD_TEXT_BANK as u16) << MAP_PAL_SHIFT);
                }
                n /= 10; // unnamed: decimal digit extraction
                col -= 1;
                if n == 0 {
                    break;
                }
            }
            // The symbol after the amount is not a letter: it is glyph 0xb3
            // of the font, found by taking the real ROM's own reward line
            // out of VRAM and searching all 448 glyphs for it.
            let z = ZENNY_GLYPH;
            for half in 0..GLYPH_TILES {
                cells[(REWARD_TEXT_ROW + half as i32) as usize * WIN_W
                    + REWARD_Z_COL as usize] =
                    (CELL_FONT, z * GLYPH_TILES + half | (REWARD_TEXT_BANK as u16) << MAP_PAL_SHIFT);
            }
            for k in 0..REWARD_TILES {
                cells[(REWARD_ROW + (k / REWARD_W) as i32) as usize * WIN_W
                    + (REWARD_COL + (k % REWARD_W) as i32) as usize] = (CELL_REWARD, k as u16);
            }
            for col in REWARD_EDGE_FIRST..=REWARD_EDGE_LAST {
                cells[REWARD_EDGE_ROW as usize * WIN_W + col as usize] =
                    (CELL_BASE, REWARD_EDGE_TILE | (REWARD_TEXT_BANK as u16) << MAP_PAL_SHIFT);
            }
            shown.blit_needed = true;
            self.resolve_cells(shown);
            self.blit_slide(shown);
    }

    /// Resolve every distinct `(tileset, raw)` pair in `shown.cells` to a
    /// pinned VRAM map word once, so the per-tick slide rewrite is one
    /// `copy_map_block`, not 576 VRAM-manager lookups (F21d: the manager's
    /// lookup cache holds 8 tiles across this window's 3 tilesets, so nearly
    /// every `set_tile` paid the hash path -- ~0.5 frame per blit, missing
    /// vblank every third slide frame). Called whenever `cells` change.
    fn resolve_cells(&self, shown: &mut Shown) {
        let v = &self.variants[shown.variant];
        let tileset = |tag: u8| match tag {
            CELL_FONT => &self.font,
            CELL_REWARD => &self.reward,
            _ => &v.tiles,
        };
        shown.guards.clear();
        // Guard 0 is the off-window blank (variant tile 0), which the
        // blit writes to map columns the window does not cover.
        shown.guards.push(MappedTile::new(&v.tiles, entry(0)));
        shown.blank = shown.guards[0].word();
        let mut distinct: Vec<(u8, u16)> = Vec::new();
        for (i, &(tag, raw)) in shown.cells.iter().enumerate() {
            if tag == CELL_BASE && raw == 0 {
                shown.words[i] = shown.blank;
                continue;
            }
            let found = distinct.iter().position(|&(t, r)| t == tag && r == raw);
            let k = match found {
                Some(k) => k,
                None => {
                    distinct.push((tag, raw));
                    shown
                        .guards
                        .push(MappedTile::new(tileset(tag), entry(raw)));
                    distinct.len() - 1
                }
            };
            // Guard k+1 parallels distinct[k] (guard 0 is the blank).
            shown.words[i] = shown.guards[k + 1].word();
        }
        // `sub_802C810`'s two runs, resolved once so the blink costs ten
        // stores. Appended after the cells so `guards` still pins every word
        // the blit can write.
        for state in 0..PROMPT_STATES {
            for col in 0..PROMPT_W {
                let tile = if state == 0 {
                    REWARD_EDGE_TILE
                } else {
                    PROMPT_TILE + col as u16
                };
                let raw = tile | (REWARD_TEXT_BANK as u16) << MAP_PAL_SHIFT;
                shown.guards.push(MappedTile::new(&v.tiles, entry(raw)));
                shown.prompt[state][col] = shown.guards[shown.guards.len() - 1].word();
            }
        }
        // A re-resolve (the reward draw) rebuilds `words` from `cells`, so
        // put back whichever run the driver has already written.
        if shown.prompt_state != PROMPT_UNWRITTEN {
            let state = shown.prompt_state as usize;
            for col in 0..PROMPT_W {
                shown.words[REWARD_EDGE_ROW as usize * WIN_W
                    + REWARD_EDGE_FIRST as usize
                    + col] = shown.prompt[state][col];
            }
        }
    }

    /// Draw the stored cells into the background at the slide's current
    /// column, clipping off-screen columns. This is this build's version of
    /// the driver's own `CopyBackgroundTiles(j, 2, block 3, ...)` call in
    /// `sub_802BD60` (asm03_0.s:11575): a tilemap redraw every slide tick,
    /// not a scroll. Cells the window does not cover read back as the
    /// fresh-map blank, which is what an untouched cell renders as anyway.
    pub fn blit_slide(&self, shown: &mut Shown) {
        let j = shown.slide_x() / TILE_PX;
        let mut block = [shown.blank; MAP_W * WIN_H];
        for row in 0..WIN_H {
            for col in 0..MAP_W {
                let wc = col as i32 - j;
                if (0..WIN_W as i32).contains(&wc) {
                    block[row * MAP_W + col] = shown.words[row * WIN_W + wc as usize];
                }
            }
        }
        shown.bg.copy_map_block(MAP_ORIGIN, MAP_W, &block);
        shown.blit_needed = false;
    }
}

/// A GBA background map word: the tile id in bits 0-9, the flips in 10-11,
/// the palette bank in 12-15.
const MAP_TILE_MASK: u16 = 0x3ff; // provenance: derived -- GBA background map entry format
const MAP_HFLIP: u16 = 0x400; // provenance: derived -- GBA background map entry format
const MAP_VFLIP: u16 = 0x800; // provenance: derived -- GBA background map entry format
const MAP_PAL_SHIFT: u16 = 12; // provenance: derived -- GBA background map entry format
fn entry(e: u16) -> TileSetting {
    TileSetting::new(
        e & MAP_TILE_MASK,
        TileEffect::new(
            e & MAP_HFLIP != 0,
            e & MAP_VFLIP != 0,
            (e >> MAP_PAL_SHIFT) as u8,
        ),
    )
}

impl Shown {
    /// The window's current slide position in pixels, for the RESULT mark
    /// (`mark_x_at`): the resting position once the slide is over, so post-
    /// slide phases all read the same mark x.
    pub fn slide_x(&self) -> i32 {
        match self.phase {
            Phase::Sliding { x, .. } => x,
            _ => REST_X,
        }
    }

    /// Advance a frame. `confirm` is whether A or Start is down. Returns the
    /// screen fade to apply, 1-16, once the window is being dismissed, and
    /// None before then; 16 means the screen is fully black.
    pub fn update(&mut self, confirm: bool) -> Option<u8> {
        self.phase = match self.phase {
            Phase::Sliding { x, hold } if hold > 0 => Phase::Sliding { x, hold: hold - 1 },
            Phase::Sliding { x, .. } if x < REST_X => {
                let x = (x + SLIDE_STEP).min(REST_X);
                self.blit_needed = true;
                Phase::Sliding { x, hold: 0 }
            }
            Phase::Sliding { .. } => Phase::Waiting,
            // WIN never reaches this arm with confirm held: the battle
            // calls `poll_reward_reveal` first, which moves a waiting WIN
            // window into `Revealing`. LOSE has no reward and dismisses.
            Phase::Waiting if confirm => Phase::Dismissing {
                ticks: DISMISS_FRAMES,
            },
            Phase::Waiting => Phase::Waiting,
            Phase::Revealing { left } if left > 1 => Phase::Revealing { left: left - 1 },
            Phase::Revealing { .. } => Phase::Cooldown {
                ticks: COOLDOWN_FRAMES,
            },
            Phase::Cooldown { ticks } if ticks > 1 => Phase::Cooldown { ticks: ticks - 1 },
            Phase::Cooldown { .. } => Phase::RewardWait,
            Phase::RewardWait if confirm => Phase::Dismissing {
                ticks: DISMISS_FRAMES,
            },
            Phase::RewardWait => Phase::RewardWait,
            Phase::Dismissing { ticks } if ticks > 1 => Phase::Dismissing { ticks: ticks - 1 },
            Phase::Dismissing { .. } => Phase::Fading { step: 1 },
            Phase::Fading { step } if step < FADE_STEPS => Phase::Fading { step: step + 1 },
            Phase::Fading { .. } => Phase::Done,
            Phase::Done => Phase::Done,
        };
        // Canon's wait state, `sub_802BF0C` (asm03_0.s:11787-11822), rewrites
        // the ten cells at (2, 14) EVERY frame with `sub_802C810(bit3 of the
        // global frame counter)` -- and with state 0 on the frame the confirm
        // lands (asm03_0.s:11801). Nothing before the wait state touches them,
        // which is why the setup map's lit line is right until then.
        self.frames = self.frames.wrapping_add(1);
        if matches!(self.phase, Phase::Waiting) {
            self.wait_frames += 1;
            let counter = self.frames.wrapping_add(PROMPT_BLINK_SEED);
            let state = u8::from(counter & PROMPT_BLINK_BIT != 0);
            if self.wait_frames > PROMPT_WAIT_LEAD && state != self.prompt_state {
                self.prompt_state = state;
                for col in 0..PROMPT_W {
                    self.words[REWARD_EDGE_ROW as usize * WIN_W
                        + REWARD_EDGE_FIRST as usize
                        + col] = self.prompt[state as usize][col];
                }
                self.blit_needed = true;
            }
        }
        match self.phase {
            Phase::Fading { step } => Some(step),
            Phase::Done => Some(FADE_STEPS),
            _ => None,
        }
    }

    /// If `confirm` is held while a WIN window waits pre-reward, start the
    /// reveal now and report true so the caller (`Battle::update`, which
    /// owns the tilesets via `Results`) draws the reward content. The
    /// drawing lives on `Results`; the phase lives here. A no-op for LOSE
    /// and for every phase but `Waiting`.
    pub fn poll_reward_reveal(&mut self, confirm: bool) -> bool {
        if confirm && self.variant == WIN && matches!(self.phase, Phase::Waiting) {
            self.phase = Phase::Revealing { left: REVEAL_FRAMES };
            return true;
        }
        false
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
    /// `result_elapsed` = 0xFFFF ("settled"). The setup hold plus the slide
    /// ticks to rest, so an off-by-one never leaves the window short.
    pub const SETTLED: u32 = SLIDE_HOLD as u32
        + ((REST_X - START_X + SLIDE_STEP - 1) / SLIDE_STEP) as u32; // provenance: derived -- this file's own slide constants (REST_X, START_X, SLIDE_STEP, SLIDE_HOLD; sub_802C34E/sub_802BE36, asm03_0.s:12425/11670), not a separate measurement
}
