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
//! card's attack power is drawn with the HUD's digit objects over its
//! damage row; the chip name and element the card also carries wait on
//! the game's text font and element icons.
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
    RegularBackground, TileEffect, TileFormat, TileSet, TileSetting,
};
use agb::display::{Graphics, GraphicsFrame, Palette16, Priority, Rgb15};
use agb::input::{Button, ButtonController, Tri};

use crate::chips::{Chip, PICTURE_TILES, WILDCARD};
use crate::hud::Hud;

const MAGIC: &[u8; 4] = b"BNCW";
const MAP_W: usize = 15; // provenance: derived -- byte_86E625C's own 15x20 map (see the module doc above)
const MAP_H: usize = 20; // provenance: derived -- byte_86E625C's own 15x20 map (see the module doc above)
const SLIDE_FROM: i32 = 0x78; // provenance: derived -- sub_8026B04/sub_8026BF4, asm03_0.s:882/1026
const SLIDE_STEP: i32 = 0xc; // provenance: derived -- sub_8026B04/sub_8026BF4, asm03_0.s:882/1026
/// The window's palette bank; the results windows use 9-11 too, so the
/// banks are set on open and the results' restored on close.
pub const BANK: u8 = 9; // provenance: derived -- byte_86E625C's own map, palette bank 9 (see the module doc above)
/// The card picture's bank, holding the highlighted chip's palette.
const PICTURE_BANK: u8 = 10; // provenance: derived -- sub_80284E2, asm03_0.s:4373 (see the module doc above)
/// The panel behind the window's frame, bank 13 on the real ROM. The HUD's
/// own layer stands down while the menu is up, so they can share it.
const PANEL_BANK: u8 = 13; // provenance: peeked -- read off the real ROM with the menu open (see `open()`'s own comment)
/// Banks the slot icons draw in, one per slot. NOTE: the real ROM puts EVERY
/// icon in bank 11 -- read off a live menu, every icon cell in the window's
/// map carries bank 11 -- which means its icons share one 16-colour palette
/// this build does not have; that palette is in neither the window asset nor
/// the chip asset, so the icons here still take one bank each and their own
/// chip's colours. What the list avoids is bank 13, which is the window's
/// panel and the HP box beside it: running 11 through 15 painted the HP box in
/// a chip's colours.
/// The palette every icon and the vertical meter share, variant 3 of the
/// asset's palette section. The real ROM's icons are GREYSCALE, all drawn from
/// this one bank rather than each chip's own colours.
const SHARED_ICON_VARIANT: usize = 3; // provenance: peeked -- read off a live menu by the exporter, like DIM_ICON_VARIANT below
/// A dimmed copy of it, variant 4, which the real ROM keeps in bank 12 and
/// gives to every slot whose chip cannot join the picks made so far
/// (sub_80283C8 maps the slot record's selectable byte through byte_8028470
/// to bank 11 or 12; asm03_0.s:4235-4313). It is not a computed dim of bank
/// 11 -- the per-channel ratios differ entry to entry -- so like bank 11 it
/// is read off a live menu by the exporter.
const DIM_ICON_VARIANT: usize = 4; // provenance: peeked -- read off a live menu by the exporter (see the doc comment above)
const ICON_BANK: u8 = 11; // provenance: peeked -- read off a live menu (every icon cell in the window's map carries bank 11, see BANK's own doc block above)
const DIM_BANK: u8 = 12; // provenance: derived -- sub_80283C8, asm03_0.s:4235-4313
/// Chips offered per window: the base count before Custom parts
/// (sub_802A40C, asm03_0.s:8650).
pub const OFFERED: usize = 5; // provenance: derived -- sub_802A40C, asm03_0.s:8650
/// The window has ten slot cells, two rows of five, and the real ROM draws
/// its empty icon in every one it is not offering -- left alone they stay
/// transparent and the field shows through the window.
const SLOT_CELLS: usize = 10; // provenance: derived -- sub_8027E90/dword_802A7CC, asm03_0.s:3447,9062 (see SLOT_CELLS_SHOWN's own doc below)
/// But only the first EIGHT are ever seen. sub_8027E90 copies the template
/// dword_802A7CC into the twelve per-slot records, and its low bytes give
/// cells 1-8 state 0x0a and cells 9-10 state 0x0b (asm03_0.s:3447, 9062);
/// sub_80283C8 maps 0x0a to the icon bank and lets 0x0b fall through to the
/// window frame's bank 9, where the empty-cell art reads as the panel's own
/// background. The last two only appear in the rare full-custom case where
/// both the draw pile and the capacity reach ten. So the count is fixed, not
/// a function of how many chips are offered.
const SLOT_CELLS_SHOWN: usize = 8; // provenance: derived -- sub_8027E90/dword_802A7CC, asm03_0.s:3447,9062 (see the doc comment above)
/// Picks per window (sub_8028D6C, asm03_0.s:5457).
pub const HAND_SIZE: usize = 5; // provenance: derived -- sub_8028D6C, asm03_0.s:5457

/// The cursor's index for the OK box; 0-4 are the offered slots
/// (S20364C0.inc:14, eS20364C0+7).
const OK: u8 = 0xa; // provenance: derived -- S20364C0.inc:14, eS20364C0+7
/// The bracket swaps tile and shrinks a pixel every 8 frames: `sub_8028820`
/// loads the counter with `ldr r5,[r5,#0x40]` (asm03_0.s:4801) and reduces it
/// with `lsr r5,r5,#3 / and r5,r4` (asm03_0.s:4803-4804), then adds the bit to
/// the base tile 0xb764 (asm03_0.s:4812-4813) -- so neither phase hides the
/// bracket, they are two tiles a pixel apart. The counter is a 32-bit field of
/// the window's own struct at 0x02036500 (`oS20364C0_Extra_Unk_40`,
/// S20364C0.inc:47-58), seeded to 0x78 by the slide-in and counted down by 0xc
/// (asm03_0.s:910-916), then incremented once a frame by state 4
/// (asm03_0.s:1163-1165) and re-zeroed when the selection ends
/// (asm03_0.s:1151-1152). `self.frames` below is that counter.
const BLINK_SHIFT: u32 = 3; // provenance: derived -- asm03_0.s:1163-1165/1151-1152
/// Frames between a direction and the cursor moving. Measured against the
/// real ROM with Left held six frames: its bracket is still on OK for the two
/// frames after the press and on the new slot on the third. Two leaves one
/// frame of the bracket differing and three leaves one frame of the card, so
/// two it is; the last frame of a cursor move is not resolved.
const CURSOR_DELAY: u8 = 2; // provenance: fitted -- two vs. three both leave one frame wrong; not fully resolved

/// Indices into the asset's patch records, in byte_8027B2C's order.
const REGION_PICTURE: usize = 1; // provenance: derived -- byte_8027B2C's own record order (see the doc comment above)
/// The attack power's cells, (6,9) 3x2: digits right-aligned in the row.
const REGION_DAMAGE: usize = 4; // provenance: derived -- byte_8027B2C's own record order
const fn region_slot_icon(slot: usize) -> usize {
    5 + 2 * slot
}
const fn region_slot_code(slot: usize) -> usize {
    6 + 2 * slot
}
/// The card's dark interior tile, which the real ROM uses for the parts of the
/// name and damage rows it is not writing text into (its map has it at the
/// card's inner edge and in the gap beside the damage). The text itself is
/// composed at runtime from a proportional font this build does not have, so
/// those regions are filled with this rather than left transparent -- without
/// it the backdrop shows straight through the card.
const CARD_INTERIOR_TILE: u16 = 0x011; // provenance: peeked -- read off the real ROM's own map (see the doc comment above)
/// A tile of flat colour 1, which in the window frame's bank is the panel's
/// own background. The real ROM fills the two hidden slot cells with it --
/// their VRAM tiles are uniform 0x11 bytes, not the empty-cell art in another
/// bank -- so they read as bare panel.
const PANEL_FLAT_TILE: u16 = 0x03e; // provenance: peeked -- read off the real ROM's own VRAM (see the doc comment above)
/// Where the regular-chip mark's ring lands on screen.
const MARK_AT: (i32, i32) = (95, 4); // provenance: peeked -- read off a live menu's own OAM
/// The card regions that hold text: the chip name, and the element, code and
/// damage row beneath the picture.
const TEXT_REGIONS: [usize; 4] = [0, 2, 3, 4]; // provenance: derived -- byte_8027B2C's own record order
/// The name row: eight glyph columns two tiles tall, written left to right
/// and padded with blanks, which the font draws as flat colour 8 -- the same
/// thing CARD_INTERIOR_TILE is.
const REGION_NAME: usize = 0; // provenance: derived -- byte_8027B2C's own record order
/// How many glyphs of the font one glyph of a name takes: 8x16, top over
/// bottom.
const GLYPH_TILES: u16 = 2; // provenance: derived -- an 8x16 glyph is two stacked 8x8 tiles

/// The game's own character code for an ASCII byte, which is the glyph's index
/// in the battle text font (constants/bn6-charmap.tbl). Shared with the
/// chip-name popup in `battle.rs`, which draws the same font as objects.
pub fn char_code(c: u8) -> u16 {
    match c {
        b'0'..=b'9' => 0x01 + (c - b'0') as u16,
        b'A'..=b'Z' => 0x0b + (c - b'A') as u16,
        b'a'..=b'z' => 0x26 + (c - b'a') as u16,
        b'-' => 0x40,
        _ => 0,
    }
}
/// The element/code/damage row: the code letter, the element icon and the
/// attack power.
const REGION_CODE: usize = 2; // provenance: derived -- byte_8027B2C's own record order
const REGION_ELEMENT: usize = 3; // provenance: derived -- byte_8027B2C's own record order
/// Tiles in one element icon, 16x16 row-major.
const ELEMENT_TILES: u16 = 4; // provenance: derived -- a 16x16 icon is four 8x8 tiles
/// Elements the card has an icon for; 0x0a is null, the last.
const ELEMENTS: usize = 11; // provenance: peeked -- the exporter's own asset, one icon per element plus the null entry
/// Bytes of shared-icon-bank tail each element carries: entries 10 to 15.
const ELEMENT_PALETTE: usize = 12; // provenance: derived -- six BGR555 colours, 2 bytes each (see `element_palettes`'s own doc below)
/// Where the card's three fonts begin inside the asset's slot-art section:
/// after the empty icon, the 28 slot code glyphs, the OK box, the stack
/// frame, the regular-chip mark, and the message card with its palette.
/// provenance: derived -- tools/custom_export.py's own fixed asset layout.
const fn card_fonts_at(slot_art: usize) -> usize {
    slot_art + 0x80 + 28 * 0x40 + 0x200 + 42 * 32 + 32
}
const REGION_OK: usize = 25; // provenance: derived -- byte_8027B2C's own record order
const REGION_STACK: usize = 26; // provenance: derived -- byte_8027B2C's own record order
/// The blank code glyph, dword_86E591C[0x1b] (sub_8028204).
const CODE_NONE: usize = 0x1b; // provenance: derived -- dword_86E591C[0x1b], sub_8028204

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

// provenance: derived -- byte_80288B0, asm03_0.s:4860 (see the doc comment above)
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
// provenance: derived -- byte_80288E4, asm03_0.s:4878 (see the doc comment above)
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
    /// The 32 bytes after the cursor's tiles. Despite sitting in the cursor
    /// section this is the WINDOW's own bank: with the menu open the real ROM
    /// has it in BG bank 9, which is the bank the window's tilemap draws in,
    /// while the three variants in the palette section go to bank 13. The
    /// cursor is an object and takes it from OBJ palette space.
    cursor_palette: Palette16,
    /// The OBJECT palette its sprites draw from, which is NOT the same
    /// palette: `cursor_palette` is the window's background bank 9 word for
    /// word and would paint the bracket's corners yellow where the real ROM's
    /// are orange. Measured against a live menu's OBJ bank 11.
    cursor_obj_palette: Palette16,
    /// The regular-chip mark above the pick stack: a gold ring with a red
    /// disc, four tiles of a 16x16 object.
    regular_mark: &'static [u8],
    /// The "CHIP DATA TRANSMISSION / Sending chip data..." card and its
    /// palette, shown in the picture region whenever the cursor is not on a
    /// chip the window can preview.
    message: TileSet,
    message_palette: Palette16,
    empty_icon: TileSet,
    /// The two tiles that frame the pick stack, alternating down the column
    /// either side of it. The stored map has neither -- the game patches those
    /// cells in when the window opens.
    stack_frame: TileSet,
    code_glyphs: TileSet,
    ok_box: TileSet,
    /// The battle text font with 8 added to every nibble -- the same tiles
    /// the RESULT window's reward line uses, and for the same reason: the
    /// game's text renderer adds a colour word to every glyph word on its way
    /// to VRAM and this window passes index 8 (sub_3006C18, asm/asm38.s:2381).
    /// The card's name row is these glyphs byte for byte.
    font: TileSet,
    /// The card's own three fonts, which -- unlike the name -- are stored
    /// ready-coloured and go to VRAM unchanged: the code letter (A-Z, '*',
    /// blank; ink 0xb), the damage digits (0-9; ink 9) and the element icons,
    /// eleven 16x16 pictures indexed by the chip's element byte.
    card_letters: TileSet,
    card_digits: TileSet,
    elements: TileSet,
    /// Six BGR555 entries per element: the LAST SIX of the shared icon bank.
    /// 10-12 are the icon frame's colours, the same every time; 13-15 are the
    /// element's own, which the real ROM writes as it draws the card. Reading
    /// the bank off one live menu is not enough -- that menu was showing a
    /// null-element card, whose last three entries are zero, so every other
    /// element's icon came out with black where its colour should be.
    element_palettes: &'static [u8],
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
    /// The CODE of this copy, from the folder entry's high bits. A folder
    /// holds copies of the same chip under different codes, and the window
    /// shows the copy's, not the chip's first -- this build used
    /// `chip.codes[0]` and so lettered every copy the same.
    pub code: u8,
    pub deck_index: usize,
}

/// AUDIT wave 3d "bg3-merge": no longer owns its own `RegularBackground`.
/// Canon draws the chip window on the SAME hardware BG3 as the HUD's HP box
/// and the RESULT window (peeked, identical across pausedwithcannon/
/// chipselect/result_arrival) -- see battle.rs's `hud_bg` field, which every
/// method below that used to write `self.bg` now takes as a
/// `&mut RegularBackground` parameter instead.
pub struct Custom<'a> {
    assets: &'a CustomAssets,
    /// Columns drawn so far; the rest of the map is left as tile 0.
    revealed: usize,
    phase: Phase,
    /// The two blink phases of the corner tile.
    cursor: [SpriteVram; 2],
    /// The regular-chip mark, which stands above the pick stack the whole
    /// time the window is up.
    mark: SpriteVram,
    cursor_at: u8,
    /// A direction waiting out CURSOR_DELAY, and the frames left of it.
    pending_move: i8,
    move_in: u8,
    /// Background palettes the card wants, held back ONE FRAME. A palette
    /// lands on the frame it is set and a tilemap write lands on the next, so
    /// setting the new chip's picture palette as the card is redrawn paints
    /// the OLD chip's tiles in the NEW chip's colours for a frame -- 2688
    /// pixels of it, on the frame after every cursor move. The real ROM
    /// changes the whole card on one frame; this build changed the picture's
    /// colours a frame before everything else. Same shape as the HP box's
    /// orange flash (TRANSFER 7aj), same fix.
    pending_palettes: Vec<(u8, Palette16)>,
    /// Counted while the window is open, as eS20364C0+0x40 is.
    frames: u32,
    slots: [Option<Offer>; OFFERED],
    /// Slot indices in pick order (eS20364C0+0x48).
    picks: Vec<usize>,
    /// The chip on the card: its id and attack power.
    pictured: Option<(u16, u16)>,
}

impl CustomAssets {
    pub fn new(data: &'static [u8], font: &'static [u8]) -> Self {
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
            // Three variants from the window's own data, then the icon
            // bank and its dimmed copy the exporter appends.
            palette: &data[p..p + 160],
            regions,
            cursor_tiles: &data[c..c + 64],
            cursor_palette: read_palette(&data[c + 64..c + 96]),
            cursor_obj_palette: read_palette(&data[c + 96..c + 128]),
            regular_mark: &data[a + 0x80 + 28 * 0x40 + 0x180..a + 0x80 + 28 * 0x40 + 0x200],
            message: tileset(&data[a + 0x80 + 28 * 0x40 + 0x200..a + 0x80 + 28 * 0x40 + 0x200 + 42 * 32]),
            message_palette: read_palette(
                &data[a + 0x80 + 28 * 0x40 + 0x200 + 42 * 32
                    ..a + 0x80 + 28 * 0x40 + 0x200 + 42 * 32 + 32],
            ),
            empty_icon: tileset(&data[a..a + 0x80]),
            code_glyphs: tileset(&data[a + 0x80..a + 0x80 + 28 * 0x40]),
            ok_box: tileset(&data[a + 0x80 + 28 * 0x40..a + 0x80 + 28 * 0x40 + 0x100]),
            stack_frame: tileset(
                &data[a + 0x80 + 28 * 0x40 + 0x100..a + 0x80 + 28 * 0x40 + 0x180],
            ),
            card_letters: tileset(&data[card_fonts_at(a)..card_fonts_at(a) + 28 * 0x40]),
            card_digits: tileset(
                &data[card_fonts_at(a) + 28 * 0x40..card_fonts_at(a) + 38 * 0x40],
            ),
            elements: tileset(
                &data[card_fonts_at(a) + 38 * 0x40..card_fonts_at(a) + 38 * 0x40 + 11 * 0x80],
            ),
            element_palettes: {
                let o = card_fonts_at(a) + 38 * 0x40 + 11 * 0x80;
                &data[o..o + ELEMENTS * ELEMENT_PALETTE]
            },
            font: {
                assert_eq!(&font[0..4], b"BNTF", "not a BNTF asset");
                let fo = u32::from_le_bytes(font[0x08..0x0c].try_into().unwrap()) as usize;
                let len = u32::from_le_bytes(font[fo..fo + 4].try_into().unwrap()) as usize;
                // The second half is the colour-added copy.
                tileset(&font[fo + 4 + len / 2..fo + 4 + len])
            },
        }
    }

    /// The regular-chip mark as an object in the palette it shares with the
    /// cursor -- literally shares, since `try_allocate_shared` keys on the
    /// colours and hands both the same bank, which is what the real ROM's OAM
    /// does (both are bank 11).
    /// The RESULT window hangs the SAME one at its top-left corner:
    /// OAM entry 0 of a live results screen is a 16x16 at (37,21), OBJ tile
    /// 0x200 in bank 11, and both the art at that tile and that bank match
    /// this window's byte for byte.
    pub fn mark_sprite(&self) -> SpriteVram {
        let palette = PaletteVramSingle::try_allocate_shared(&self.cursor_obj_palette)
            .expect("cursor palette should fit in vram");
        DynamicSprite16::from_bytes(Size::S16x16, self.regular_mark).to_vram(palette)
    }

    /// One of the window's colour variants, or the two icon banks after them.
    pub fn palette(&self, variant: usize) -> Palette16 {
        read_palette(&self.palette[variant * 32..variant * 32 + 32])
    }

    /// The shared icon bank carrying this element's own last six entries,
    /// which is what the real ROM has in bank 11 while the card shows it.
    fn icon_palette(&self, element: u8) -> Palette16 {
        let mut bytes = [0u8; 32];
        let base = SHARED_ICON_VARIANT * 32;
        let keep = 32 - ELEMENT_PALETTE;
        bytes[..keep].copy_from_slice(&self.palette[base..base + keep]);
        let e = (element as usize).min(ELEMENTS - 1) * ELEMENT_PALETTE;
        bytes[keep..].copy_from_slice(&self.element_palettes[e..e + ELEMENT_PALETTE]);
        read_palette(&bytes)
    }

    /// Open the window over the offered chips, at most one per slot.
    ///
    /// AUDIT pairs 6/14/17: `fixture` is `Battle`'s own `self.fixture`,
    /// threaded through so `demo-custmatch`/`demo-cardname` can be
    /// reproduced by descriptor -- see `fixture::Fixture::window_pick_count`'s
    /// own doc for why this needs fields outside FIXTURE.md's published
    /// contract.
    /// `bg` is the SAME `RegularBackground` the HUD's HP box draws on
    /// (`Battle::hud_bg`, lazily created there if this is the first time
    /// anything has needed it -- AUDIT wave 3d "bg3-merge") -- canon's own
    /// BG3CNT 0x1f09 while the menu runs: priority 1, under the HUD layer
    /// and over the actors (sub_801DA24, asm00_2.s:29038), ONE tilemap
    /// shared with the HP box, not a background of this window's own.
    pub fn open(
        &self,
        bg: &mut RegularBackground,
        offered: &[Offer],
        gfx: &Graphics,
        fixture: Option<crate::fixture::Fixture>,
    ) -> Custom<'_> {
        bg.set_scroll_pos((SLIDE_FROM, 0));
        let palette = PaletteVramSingle::try_allocate_shared(&self.cursor_obj_palette)
            .expect("cursor palette should fit in vram");
        let cursor = [0, 1].map(|i| {
            DynamicSprite16::from_bytes(Size::S8x8, &self.cursor_tiles[i * 32..i * 32 + 32])
                .to_vram(palette.clone())
        });
        // The mark shares the cursor's object palette, as the real ROM's OAM
        // has it: both are bank 11.
        let mark = DynamicSprite16::from_bytes(Size::S16x16, self.regular_mark)
            .to_vram(palette.clone());
        let mut slots = [None; OFFERED];
        for (slot, offer) in slots.iter_mut().zip(offered) {
            *slot = Some(*offer);
        }
        let mut custom = Custom {
            assets: self,
            revealed: 0,
            phase: Phase::Opening { x: SLIDE_FROM },
            cursor,
            mark,
            cursor_at: 0,
            pending_move: 0,
            move_in: 0,
            pending_palettes: Vec::new(),
            frames: 0,
            slots,
            picks: Vec::new(),
            pictured: None,
        };
        // Bank 9 is the window's frame, bank 13 the panel behind it. Read off
        // the real ROM with the menu open: the palette section's variant 0 is
        // the real's bank 13, and the 32 bytes after the cursor tiles are its
        // bank 9. Setting variant 0 into bank 9 is what made the frame render
        // salmon where the real ROM's is grey.
        gfx.set_background_palette(BANK, &self.cursor_palette);
        gfx.set_background_palette(PANEL_BANK, &self.palette(0));
        gfx.set_background_palette(ICON_BANK, &self.palette(SHARED_ICON_VARIANT));
        gfx.set_background_palette(DIM_BANK, &self.palette(DIM_ICON_VARIANT));
        for (i, slot) in custom.slots.iter().enumerate() {
            let _ = (i, slot);
        }
        // The window fixture reproduces the capture's state: its Cannon A is
        // already picked and the cursor sits on OK (demo-cardname: the first
        // slot instead, the only way to see the card's NAME -- with the
        // cursor on OK the real ROM shows its message card instead).
        // AUDIT pairs 6/14/17: `window_pick_count`/`window_pick_slot`/
        // `window_cursor` drive this from the fixture instead when one is
        // present -- see their own doc in fixture.rs for why they are not
        // FIXTURE.md fields.
        match fixture {
            Some(f) if f.window_pick_count > 0 => {
                custom.picks.push(f.window_pick_slot as usize);
                custom.cursor_at = f.window_cursor;
            }
            Some(_) => {}
            None => {}
        }
        for slot in 0..OFFERED {
            custom.draw_slot(bg, slot);
        }
        for slot in OFFERED..SLOT_CELLS {
            if slot < SLOT_CELLS_SHOWN {
                custom.fill(bg, region_slot_icon(slot), &self.empty_icon, Some(ICON_BANK));
                let r = self.regions[region_slot_code(slot)];
                custom.fill_from(bg, r, &self.code_glyphs, (CODE_NONE * 2) as u16, r.bank);
            } else {
                custom.fill_flat(bg, region_slot_icon(slot));
                custom.fill_flat(bg, region_slot_code(slot));
            }
        }
        custom.draw_stack(bg);
        custom.draw_stack_frame(bg);
        custom.fill_card_text_background(bg);
        custom.fill(bg, REGION_OK, &self.ok_box, None);
        custom.draw_card(bg, gfx);
        custom.reveal(bg, SLIDE_FROM);
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
    fn reveal(&mut self, bg: &mut RegularBackground, x: i32) {
        while self.revealed < MAP_W && (self.revealed as i32) * 8 + 16 >= x {
            self.set_column(bg, self.revealed, true);
            self.revealed += 1;
        }
    }

    /// The slide-out clears the columns the window has vacated with the
    /// blank tile (byte_8026C88; sub_8026BF4).
    fn vacate(&mut self, bg: &mut RegularBackground, x: i32) {
        while self.revealed > 0 && ((self.revealed - 1) as i32) * 8 + 16 < x {
            self.revealed -= 1;
            self.set_column(bg, self.revealed, false);
        }
    }

    fn set_column(&mut self, bg: &mut RegularBackground, col: usize, visible: bool) {
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
            if visible && (self.in_region(col, row) || self.in_stack_frame(col, row)) {
                continue;
            }
            bg.set_tile(
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
    fn fill(&mut self, bg: &mut RegularBackground, region: usize, tiles: &TileSet, bank: Option<u8>) {
        let r = self.assets.regions[region];
        self.fill_from(bg, r, tiles, 0, bank.unwrap_or(r.bank));
    }

    fn fill_from(&mut self, bg: &mut RegularBackground, r: Region, tiles: &TileSet, first: u16, bank: u8) {
        for k in 0..r.w * r.h {
            let (dx, dy) = if r.column_major {
                (k / r.h, k % r.h)
            } else {
                (k % r.w, k / r.w)
            };
            bg.set_tile(
                ((r.x + dx) as i32, (r.y + dy) as i32),
                tiles,
                TileSetting::new(first + k as u16, TileEffect::new(false, false, bank)),
            );
        }
    }

    /// Fill a region with the panel's flat background, as the real ROM does
    /// for the slot cells it does not show.
    fn fill_flat(&mut self, bg: &mut RegularBackground, region: usize) {
        let r = self.assets.regions[region];
        for dy in 0..r.h {
            for dx in 0..r.w {
                bg.set_tile(
                    ((r.x + dx) as i32, (r.y + dy) as i32),
                    &self.assets.tiles,
                    TileSetting::new(PANEL_FLAT_TILE, TileEffect::new(false, false, BANK)),
                );
            }
        }
    }

    #[allow(dead_code)] // kept for parity with the real ROM's own patch-record path; unused by any caller yet
    fn blank(&mut self, bg: &mut RegularBackground, region: usize) {
        let r = self.assets.regions[region];
        let tiles = &self.assets.tiles;
        for dy in 0..r.h {
            for dx in 0..r.w {
                bg.set_tile(
                    ((r.x + dx) as i32, (r.y + dy) as i32),
                    tiles,
                    TileSetting::new(0, TileEffect::new(false, false, r.bank)),
                );
            }
        }
    }

    /// Repaint every offered slot. A pick changes which of the OTHERS may
    /// still be taken, so they all have to be redrawn, not just the one.
    fn draw_offered(&mut self, bg: &mut RegularBackground) {
        for slot in 0..OFFERED {
            self.draw_slot(bg, slot);
        }
    }

    /// A slot's icon and code letter: the chip's while it is offered and
    /// unpicked, the empty icon and blank glyph otherwise (sub_8028310).
    fn draw_slot(&mut self, bg: &mut RegularBackground, slot: usize) {
        let assets = self.assets;
        match self.slots[slot] {
            Some(offer) if !self.picks.contains(&slot) => {
                let icon = offer.chip.icon();
                let bank = if self.allowed(slot) { ICON_BANK } else { DIM_BANK };
                self.fill(bg, region_slot_icon(slot), &icon, Some(bank));
                let code = offer.code as usize;
                let r = assets.regions[region_slot_code(slot)];
                self.fill_from(bg, r, &assets.code_glyphs, (code * 2) as u16, r.bank);
            }
            // A PICKED slot keeps its code letter and loses only its icon.
            // Read off the real ROM: its fifth slot shows the empty-cell art
            // with an A still under it, and the chip that A belongs to -- a
            // Cannon, identified from the pick stack's icon -- is the one in
            // the stack.
            Some(offer) => {
                self.fill(bg, region_slot_icon(slot), &assets.empty_icon, Some(ICON_BANK));
                let r = assets.regions[region_slot_code(slot)];
                self.fill_from(bg, r, &assets.code_glyphs, (offer.code as u16) * 2, r.bank);
            }
            None => {
                self.fill(bg, region_slot_icon(slot), &assets.empty_icon, Some(ICON_BANK));
                let r = assets.regions[region_slot_code(slot)];
                self.fill_from(bg, r, &assets.code_glyphs, (CODE_NONE * 2) as u16, r.bank);
            }
        }
    }

    /// Paint the card's text regions with its interior tile. A placeholder for
    /// the runtime text renderer; see CARD_INTERIOR_TILE.
    fn fill_card_text_background(&mut self, bg: &mut RegularBackground) {
        for index in TEXT_REGIONS {
            let r = self.assets.regions[index];
            for dy in 0..r.h {
                for dx in 0..r.w {
                    bg.set_tile(
                        ((r.x + dx) as i32, (r.y + dy) as i32),
                        &self.assets.tiles,
                        TileSetting::new(
                            CARD_INTERIOR_TILE,
                            TileEffect::new(false, false, BANK),
                        ),
                    );
                }
            }
        }
    }

    /// The chip's name along the top of the card, left-aligned in the row's
    /// eight cells and padded with the font's blank -- which is flat colour 8,
    /// the card's own interior, so the row needs no separate background.
    fn draw_card_name(&mut self, bg: &mut RegularBackground, name: &str) {
        let r = self.assets.regions[REGION_NAME];
        let bytes = name.as_bytes();
        for col in 0..r.w {
            let g = char_code(bytes.get(col).copied().unwrap_or(b' '));
            for half in 0..r.h {
                bg.set_tile(
                    ((r.x + col) as i32, (r.y + half) as i32),
                    &self.assets.font,
                    TileSetting::new(
                        g * GLYPH_TILES + half as u16,
                        TileEffect::new(false, false, r.bank),
                    ),
                );
            }
        }
    }

    /// The row under the picture: the copy's code letter, the chip's element
    /// icon, and the attack power right-aligned in the row's three cells with
    /// the rest left as the card's interior. A chip with no attack power
    /// (a Recovery, a Barrier) shows nothing there.
    /// NOT VERIFIED: what the row does for a power of four digits or more --
    /// the widest chip in this build is Muramasa at 1020, which fits.
    fn draw_card_row(&mut self, bg: &mut RegularBackground, code: u8, element: u8, power: u16, gfx: &Graphics) {
        let assets = self.assets;
        self.pending_palettes
            .push((ICON_BANK, assets.icon_palette(element)));
        let r = assets.regions[REGION_CODE];
        self.fill_from(bg, r, &assets.card_letters, code as u16 * GLYPH_TILES, r.bank);
        let r = assets.regions[REGION_ELEMENT];
        self.fill_from(
            bg,
            r,
            &assets.elements,
            element as u16 * ELEMENT_TILES,
            ICON_BANK,
        );
        let r = assets.regions[REGION_DAMAGE];
        let mut n = power;
        for col in (0..r.w).rev() {
            let digit = (n % 10) as u16;
            let blank = power == 0 || (n == 0 && col + 1 != r.w);
            for half in 0..r.h {
                let (tiles, tile) = if blank {
                    (&assets.tiles, CARD_INTERIOR_TILE)
                } else {
                    (&assets.card_digits, digit * GLYPH_TILES + half as u16)
                };
                bg.set_tile(
                    ((r.x + col) as i32, (r.y + half) as i32),
                    tiles,
                    TileSetting::new(tile, TileEffect::new(false, false, r.bank)),
                );
            }
            n /= 10;
        }
    }

    /// Whether a cell belongs to the pick stack's frame columns, which
    /// draw_stack_frame owns. The stored map has the wrong tile there, so the
    /// template must not paint over them as the window slides in.
    fn in_stack_frame(&self, col: usize, row: usize) -> bool {
        let stack = self.assets.regions[REGION_STACK];
        (col == (stack.x - 1) as usize || col == (stack.x + stack.w) as usize)
            && (stack.y as usize..(stack.y + stack.h) as usize).contains(&row)
    }

    /// The columns either side of the pick stack, alternating the two frame
    /// tiles down each. Read off a live menu: both columns carry the same
    /// pair, in the window's own bank.
    fn draw_stack_frame(&mut self, bg: &mut RegularBackground) {
        let stack = self.assets.regions[REGION_STACK];
        let tiles = &self.assets.stack_frame;
        for row in 0..stack.h {
            // The right column is the left one MIRRORED: the real ROM's map
            // has the same two tiles there with h-flip set.
            for (col, hflip) in [(stack.x - 1, false), (stack.x + stack.w, true)] {
                bg.set_tile(
                    (col as i32, (stack.y + row) as i32),
                    tiles,
                    // The top two rows have their own pair; the rest
                    // alternate the first two down the column.
                    TileSetting::new(
                        if row < 2 { 2 + row as u16 } else { (row % 2) as u16 },
                        TileEffect::new(hflip, false, BANK),
                    ),
                );
            }
        }
    }

    /// The picks down the right-hand column, one icon per row, the empty
    /// icon below them (sub_80281D4 per row at open, asm03_0.s:3942).
    fn draw_stack(&mut self, bg: &mut RegularBackground) {
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
            match self.picks.get(row).and_then(|&slot| self.slots[slot]) {
                Some(offer) => {
                    let icon = offer.chip.icon();
                    self.fill_from(bg, cell, &icon, 0, ICON_BANK);
                }
                None => self.fill_from(bg, cell, &assets.empty_icon, 0, stack.bank),
            }
        }
    }

    /// The card shows the chip under the cursor; on OK, or over an empty
    /// or picked slot, it is left as it was (sub_8028476 draws nothing for
    /// the empty slot types, asm03_0.s:4316).
    fn draw_card(&mut self, bg: &mut RegularBackground, gfx: &Graphics) {
        let Some(offer) = self.highlighted() else {
            // No chip to preview -- the cursor is on OK, or over a slot
            // already picked -- so the real ROM puts its "sending chip data"
            // card here instead, in the picture region's own bank.
            if self.pictured.is_some() || self.frames == 0 {
                self.pictured = None;
                self.pending_palettes
                    .push((PICTURE_BANK, self.assets.message_palette.clone()));
                let r = self.assets.regions[REGION_PICTURE];
                self.fill_from(bg, r, &self.assets.message, 0, PICTURE_BANK);
                // The name and the row under the picture go with the card:
                // the real ROM clears both to flat colour 8 when the message
                // is up, which is what the interior tile already is.
                self.fill_card_text_background(bg);
            }
            return;
        };
        if self.pictured.is_some_and(|(id, _)| id == offer.chip.id) {
            return;
        }
        self.pictured = Some((offer.chip.id, offer.chip.power));
        self.pending_palettes
            .push((PICTURE_BANK, read_palette(offer.chip.palette())));
        let picture = offer.chip.picture();
        let r = self.assets.regions[REGION_PICTURE];
        debug_assert_eq!((r.w, r.h), PICTURE_TILES);
        self.fill_from(bg, r, &picture, 0, PICTURE_BANK);
        self.draw_card_name(bg, offer.chip.name());
        self.draw_card_row(bg, offer.code, offer.chip.element, offer.chip.power, gfx);
    }

    /// The chip the card should show. A PICKED slot still previews its chip:
    /// walking the real ROM's cursor onto its picked Cannon puts the Cannon
    /// card up, even though the slot itself shows the empty-cell art. Only OK
    /// and a slot with nothing in it leave the card without a chip.
    fn highlighted(&self) -> Option<Offer> {
        let slot = self.cursor_at as usize;
        if slot < OFFERED {
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
        // Nothing more fits once the hand is full: the real ROM dims every
        // slot then (updateCustomScreen_WhenUnselectingChip_8028EC8's first
        // test, asm03_0.s:5666).
        if self.picks.len() >= HAND_SIZE {
            return false;
        }
        if self.picks.is_empty() {
            return true;
        }
        let picked: Vec<Offer> = self
            .picks
            .iter()
            .filter_map(|&s| self.slots[s])
            .collect();
        let name = picked[0].chip.name();
        if picked.iter().all(|o| o.chip.name() == name) && offer.chip.name() == name {
            return true;
        }
        let mut merged = None;
        for o in &picked {
            let code = o.code;
            if code == WILDCARD {
                continue;
            }
            match merged {
                None => merged = Some(code),
                Some(m) if m == code => {}
                Some(_) => return false,
            }
        }
        let code = offer.code;
        code == WILDCARD || merged.is_none_or(|m| m == code)
    }

    /// Advance a frame. Returns true once the window has slid back out.
    /// `bg` is the SAME shared `RegularBackground` `open()` was given
    /// (`Battle::hud_bg`) -- AUDIT wave 3d "bg3-merge".
    pub fn update(&mut self, bg: &mut RegularBackground, input: &ButtonController, gfx: &Graphics) -> bool {
        // Last frame's card palettes, now that its tiles have landed.
        for (bank, palette) in self.pending_palettes.drain(..) {
            gfx.set_background_palette(bank, &palette);
        }
        self.phase = match self.phase {
            Phase::Opening { x } if x > 0 => {
                let x = (x - SLIDE_STEP).max(0);
                bg.set_scroll_pos((x, 0));
                self.reveal(bg, x);
                // The real ROM's slide-in is state 0 of the window's own state
                // machine (sub_8026B04, asm03_0.s:910-916): it seeds the same
                // 0x78 and subtracts the same 0xc, and on the tenth call --
                // the one where the counter reaches exactly 0 -- it advances
                // to state 4 IN THAT CALL (asm03_0.s:1011-1012). Falling
                // through to a separate arm on the NEXT frame spent an extra
                // frame here, which nothing could see except the bracket: the
                // window is fully revealed either way, but the blink counts
                // from state 4, so it started one frame late. Measured on a
                // static window against /tmp/chipselect.state: 368 px over 32
                // frames at the old timing, 0 at this one.
                if x == 0 { Phase::Open } else { Phase::Opening { x } }
            }
            Phase::Opening { .. } => Phase::Open,
            Phase::Open => {
                self.frames += 1;
                self.navigate(bg, input, gfx)
            }
            Phase::Closing { x } if x < SLIDE_FROM => {
                let x = (x + SLIDE_STEP).min(SLIDE_FROM);
                bg.set_scroll_pos((x, 0));
                self.vacate(bg, x);
                Phase::Closing { x }
            }
            Phase::Closing { .. } => Phase::Done,
            Phase::Done => Phase::Done,
        };
        matches!(self.phase, Phase::Done)
    }

    /// One frame of the open window's input (custMenuSomeHandler_8028B74).
    fn navigate(&mut self, bg: &mut RegularBackground, input: &ButtonController, gfx: &Graphics) -> Phase {
        // THE CURSOR MOVES TWO FRAMES AFTER THE DIRECTION. Measured against
        // the real ROM with Left held six frames: its bracket stays on OK for
        // two of them and this build's had already moved. The same two frames
        // separate every button from what it does here (7ag).
        match input.just_pressed_x_tri() {
            Tri::Positive => {
                self.pending_move = 1;
                self.move_in = CURSOR_DELAY;
            }
            Tri::Negative => {
                self.pending_move = -1;
                self.move_in = CURSOR_DELAY;
            }
            Tri::Zero => {}
        }
        if self.move_in > 0 {
            self.move_in -= 1;
            if self.move_in == 0 {
                self.cursor_at = if self.pending_move > 0 {
                    match self.cursor_at {
                        4 => OK,
                        OK => 0,
                        i => i + 1,
                    }
                } else {
                    match self.cursor_at {
                        0 => OK,
                        OK => 4,
                        i => i - 1,
                    }
                };
            }
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
                self.draw_offered(bg);
                self.draw_stack(bg);
            }
        }
        if input.is_just_pressed(Button::B) {
            if self.picks.pop().is_some() {
                self.draw_offered(bg);
                self.draw_stack(bg);
            }
        }
        self.draw_card(bg, gfx);
        Phase::Open
    }

    /// The picks in order, for the hand.
    pub fn hand(&self) -> impl Iterator<Item = Offer> + '_ {
        self.picks.iter().filter_map(|&slot| self.slots[slot])
    }

    /// Draws this window's OBJECTS only -- the mark, the damage digits and
    /// the cursor bracket. Its tiles live on the shared `Battle::hud_bg`
    /// (AUDIT wave 3d "bg3-merge"), shown once, centrally, in
    /// `Battle::draw()`.
    pub fn show(&self, frame: &mut GraphicsFrame, hud: &Hud) {
        if !matches!(self.phase, Phase::Open) {
            return;
        }
        // The regular-chip mark sits above the pick stack. The real ROM's OAM
        // has it as a 32x32 object at (87,-4) whose only four non-blank tiles
        // are the ring, so the ring itself lands here.
        Object::new(self.mark.clone())
            .set_priority(Priority::P1)
            .set_pos(MARK_AT)
            .show(frame);
        // The card's attack power, in the damage row's cells. The game
        // renders it into those tiles (sub_802869E draws the row); these are
        // the HUD's digit objects at the same place, and the chip name
        // beside it waits on the text font.
        if let Some((_, power)) = self.pictured.filter(|&(_, p)| p > 0) {
            let r = self.assets.regions[REGION_DAMAGE];
            hud.draw_number(frame, power, ((r.x + r.w) * 8) as i32, (r.y * 8) as i32);
        }
        // The origin is the slot's position less 3 in each axis
        // (sub_8028894, sub_80288D0, asm03_0.s:4843-4884: a slot sits at
        // (8 + 16 * index, 0x68), OK at (0x58 + 3, 0x70 - 2)).
        let (x, y, bracket) = if self.cursor_at == OK {
            (0x58, 0x6b, &OK_BRACKET)
        } else {
            (8 + 16 * self.cursor_at as i32 - 3, 0x68 - 3, &SLOT_BRACKET)
        };
        // The counter is bumped at the top of the frame, before anything is
        // drawn, so the first DRAWN frame already reads 1 and every phase flip
        // lands a frame before the real ROM's. Draw from the value the frame
        // started with.
        let phase = (self.frames.saturating_sub(1) >> BLINK_SHIFT) as usize & 1;
        for c in &bracket[phase] {
            Object::new(self.cursor[phase].clone())
                .set_pos((x + c.dx, y + c.dy))
                .set_hflip(c.hflip)
                .set_vflip(c.vflip)
                .show(frame);
        }
    }
}
