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

const MAGIC: &[u8; 4] = b"BNCW"; // provenance: derived -- tools/custom_export.py's own BNCW magic
/// The battle text font's own magic, checked the same way as MAGIC.
const FONT_MAGIC: &[u8; 4] = b"BNTF"; // provenance: derived -- tools/font_export.py's own BNTF magic
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
/// The first slot's icon and code cells, then two records per slot.
const SLOT_ICON_BASE: usize = 5; // provenance: derived -- byte_8027B2C's own record order (see the doc comment above)
const SLOT_CODE_BASE: usize = 6; // provenance: derived -- byte_8027B2C's own record order
const SLOT_REGION_STRIDE: usize = 2; // provenance: derived -- one icon record and one code record per slot
const fn region_slot_icon(slot: usize) -> usize {
    SLOT_ICON_BASE + SLOT_REGION_STRIDE * slot
}
const fn region_slot_code(slot: usize) -> usize {
    SLOT_CODE_BASE + SLOT_REGION_STRIDE * slot
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
const TEXT_REGION_COUNT: usize = 4; // provenance: derived -- byte_8027B2C's own record order (name, code, element, damage)
const TEXT_REGIONS: [usize; TEXT_REGION_COUNT] = [REGION_NAME, REGION_CODE, REGION_ELEMENT, REGION_DAMAGE]; // provenance: derived -- byte_8027B2C's own record order
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
/// The font glyph a character starts at (constants/bn6-charmap.tbl):
/// digits, uppercase, lowercase, and the dash; bytes with no glyph read 0.
const CHAR_DIGIT_BASE: u16 = 0x01; // provenance: derived -- constants/bn6-charmap.tbl
const CHAR_UPPER_BASE: u16 = 0x0b; // provenance: derived -- constants/bn6-charmap.tbl
const CHAR_LOWER_BASE: u16 = 0x26; // provenance: derived -- constants/bn6-charmap.tbl
const CHAR_DASH: u16 = 0x40; // provenance: derived -- constants/bn6-charmap.tbl
const CHAR_NONE: u16 = 0; // provenance: derived -- constants/bn6-charmap.tbl (index 0 is blank)
pub fn char_code(c: u8) -> u16 {
    match c {
        b'0'..=b'9' => CHAR_DIGIT_BASE + (c - b'0') as u16,
        b'A'..=b'Z' => CHAR_UPPER_BASE + (c - b'A') as u16,
        b'a'..=b'z' => CHAR_LOWER_BASE + (c - b'a') as u16,
        b'-' => CHAR_DASH,
        _ => CHAR_NONE,
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
/// Pieces of the slot-art section: one empty icon, the 28 code glyphs,
/// the OK box, the stack frame, the regular-chip mark and the message card.
const TILE_BYTES: usize = 32; // provenance: derived -- one 8x8 4bpp tile is 32 bytes
const SLOT_ICON_LEN: usize = 0x80; // provenance: derived -- tools/custom_export.py's own fixed asset layout (four 4bpp tiles)
const CODE_GLYPH_COUNT: usize = 28; // provenance: derived -- tools/custom_export.py's own fixed asset layout (A-Z, '*' and the blank)
const CODE_GLYPH_LEN: usize = 0x40; // provenance: derived -- tools/custom_export.py's own fixed asset layout (two tiles per glyph)
const OK_BOX_LEN: usize = 0x100; // provenance: derived -- tools/custom_export.py's own fixed asset layout (eight tiles)
const MESSAGE_TILES: usize = 42; // provenance: derived -- tools/custom_export.py's own fixed asset layout
const CARD_DIGIT_GLYPHS: usize = 10; // provenance: derived -- tools/custom_export.py's own fixed asset layout (0-9)
const ELEMENT_ICON_LEN: usize = 0x80; // provenance: derived -- tools/custom_export.py's own fixed asset layout (a 16x16 icon is four tiles)
/// Cumulative offsets of each piece inside the slot-art section.
const SLOT_CODE_GLYPHS_AT: usize = SLOT_ICON_LEN; // provenance: derived -- tools/custom_export.py's own fixed asset layout
const SLOT_OK_AT: usize = SLOT_CODE_GLYPHS_AT + CODE_GLYPH_COUNT * CODE_GLYPH_LEN; // provenance: derived -- tools/custom_export.py's own fixed asset layout
const SLOT_STACK_AT: usize = SLOT_OK_AT + OK_BOX_LEN; // provenance: derived -- tools/custom_export.py's own fixed asset layout
const SLOT_MARK_AT: usize = SLOT_STACK_AT + SLOT_ICON_LEN; // provenance: derived -- tools/custom_export.py's own fixed asset layout
const SLOT_MESSAGE_AT: usize = SLOT_MARK_AT + SLOT_ICON_LEN; // provenance: derived -- tools/custom_export.py's own fixed asset layout
const fn card_fonts_at(slot_art: usize) -> usize {
    slot_art + SLOT_MESSAGE_AT + MESSAGE_TILES * TILE_BYTES + PALETTE_VARIANT_BYTES
}
const REGION_OK: usize = 25; // provenance: derived -- byte_8027B2C's own record order
const REGION_STACK: usize = 26; // provenance: derived -- byte_8027B2C's own record order
/// The blank code glyph, dword_86E591C[0x1b] (sub_8028204).
const CODE_NONE: usize = 0x1b; // provenance: derived -- dword_86E591C[0x1b], sub_8028204

/// Byte sizes in the BNCW asset header and sections (tools/custom_export.py's
/// own layout): every section but the map starts with a length word, and the
/// six section pointers sit at these header offsets.
const HDR_WORD_LEN: usize = 4; // provenance: derived -- tools/custom_export.py's own BNCW layout
const HDR_TILES: usize = 0x08; // provenance: derived -- tools/custom_export.py's own BNCW layout
const HDR_MAP: usize = 0x0c; // provenance: derived -- tools/custom_export.py's own BNCW layout
const HDR_PALETTE: usize = 0x10; // provenance: derived -- tools/custom_export.py's own BNCW layout
const HDR_REGIONS: usize = 0x14; // provenance: derived -- tools/custom_export.py's own BNCW layout
const HDR_CURSOR: usize = 0x18; // provenance: derived -- tools/custom_export.py's own BNCW layout
const HDR_SLOT_ART: usize = 0x1c; // provenance: derived -- tools/custom_export.py's own BNCW layout
/// One patch record (byte_8027B2C) is eight bytes: x, y, w, h, bank and the
/// column-major flag, then two unused.
const REGION_RECORD_LEN: usize = 8; // provenance: derived -- byte_8027B2C's own record size
const RF_X: usize = 0; // provenance: derived -- byte_8027B2C's own field order
const RF_Y: usize = 1; // provenance: derived -- byte_8027B2C's own field order
const RF_W: usize = 2; // provenance: derived -- byte_8027B2C's own field order
const RF_H: usize = 3; // provenance: derived -- byte_8027B2C's own field order
const RF_BANK: usize = 4; // provenance: derived -- byte_8027B2C's own field order
const RF_ORDER: usize = 5; // provenance: derived -- byte_8027B2C's own field order
const RECORD_COLUMN_MAJOR: u8 = 1; // provenance: derived -- byte_8027B2C's own flag value
/// The map section stores its w,h words ahead of the u16 entries.
const MAP_HEADER_LEN: usize = 8; // provenance: derived -- tools/custom_export.py's own BNCW layout
const MAP_ENTRY_BYTES: usize = 2; // provenance: derived -- one u16 tilemap entry per cell
/// One 16-colour BGR555 bank; the palette section holds five: three window
/// variants, then the shared icon bank and its dimmed copy.
const PALETTE_VARIANT_BYTES: usize = 32; // provenance: derived -- sixteen BGR555 colours, 2 bytes each
const PALETTE_VARIANTS: usize = 5; // provenance: derived -- tools/custom_export.py's own fixed asset layout
const PAL_ENTRY_BYTES: usize = 2; // provenance: derived -- one BGR555 colour
/// The cursor's blink phases, and the two tiles they take.
const CURSOR_FRAMES: usize = 2; // provenance: derived -- the bracket's two blink phases (see Custom's own doc)
const CURSOR_TILES_LEN: usize = CURSOR_FRAMES * TILE_BYTES; // provenance: derived -- tools/custom_export.py's own fixed asset layout
/// The BNTF font's glyph-table pointer inside its header, and the
/// colour-added copy being the font's second half.
const BNTF_TABLE_OFF: usize = 0x08; // provenance: derived -- tools/font_export.py's own BNTF layout
const FONT_HALVES: usize = 2; // provenance: derived -- tools/font_export.py's own BNTF layout (see new's own comment)
/// BG tilemap entry fields (see set_column).
const TILE_INDEX_MASK: u16 = 0x3ff; // provenance: derived -- GBA BG tilemap bits 0-9 are the tile index
const TILE_HFLIP_BIT: u16 = 0x400; // provenance: derived -- GBA BG tilemap bit 10 flips horizontally
const TILE_VFLIP_BIT: u16 = 0x800; // provenance: derived -- GBA BG tilemap bit 11 flips vertically
const TILE_PALETTE_SHIFT: u32 = 12; // provenance: derived -- GBA BG tilemap bits 12-15 are the palette bank
/// Tile 0 is the blank every column starts and ends as (byte_8026C88).
const FIRST_TILE: u16 = 0; // provenance: derived -- byte_8026C88, sub_8026BF4 (see vacate's doc)
/// One BG tile is 8px; the slide-in stages columns two tiles ahead.
const TILE_PX: i32 = 8; // provenance: derived -- one BG tile is 8x8 pixels
const REVEAL_MARGIN: i32 = 16; // provenance: derived -- sub_8026B04 stages two tiles ahead (see reveal's doc)
/// Scroll positions: fully open is 0, and the layer never scrolls vertically.
const SCROLL_OPEN: i32 = 0; // provenance: derived -- sub_8026B04's slide counter reaches 0 when fully open
const SCROLL_Y: i32 = 0; // provenance: derived -- the window slides horizontally only
/// Picks stack one 2x2 icon per row; the frame alternates two tiles with its
/// own pair for the top two rows, one column either side of the stack.
const STACK_CELL: usize = 2; // provenance: derived -- sub_80281D4 per-row layout, asm03_0.s:3942
const STACK_FRAME_HEAD_ROWS: usize = 2; // provenance: derived -- read off a live menu (see draw_stack_frame's doc)
const STACK_FRAME_HEAD_TILE: u16 = 2; // provenance: derived -- read off a live menu (see draw_stack_frame's doc)
const STACK_FRAME_PAIR: usize = 2; // provenance: derived -- read off a live menu (see draw_stack_frame's doc)
const STACK_FRAME_OFFSET: usize = 1; // provenance: derived -- the frame sits one column either side of the stack
/// The damage row's decimal digits.
const DECIMAL_BASE: u16 = 10; // provenance: derived -- decimal digits, one glyph each
/// The fixture's first pick sets the name rule (sub_8028E4C).
const FIRST_PICK: usize = 0; // provenance: derived -- sub_8028E4C compares against the first pick
/// Cursor-ring ends (dword_802A7CC): slot 0 is first, slot 4 last, then OK.
const FIRST_SLOT: u8 = 0; // provenance: derived -- dword_802A7CC, asm03_0.s:9062
const LAST_SLOT: u8 = 4; // provenance: derived -- dword_802A7CC, asm03_0.s:9062 (OFFERED - 1)
/// Left/right waiting out CURSOR_DELAY (custMenuSomeHandler_8028B74).
const MOVE_RIGHT: i8 = 1; // provenance: derived -- custMenuSomeHandler_8028B74, asm03_0.s:5160
const MOVE_LEFT: i8 = -1; // provenance: derived -- custMenuSomeHandler_8028B74, asm03_0.s:5160
/// Bank 13's colours: the palette section's variant 0.
const PANEL_VARIANT: usize = 0; // provenance: peeked -- variant 0 is the real ROM's bank 13 (see open's comment)
/// Cursor-bracket origins in screen pixels: a slot sits at
/// (8 + 16 * index, 0x68), OK at (0x58, 0x6b), each less 3 per axis
/// (sub_8028894, sub_80288D0, asm03_0.s:4843-4884; see show's doc).
const SLOT_ORIGIN_X: i32 = 8; // provenance: derived -- sub_8028894, asm03_0.s:4843-4884
const SLOT_PITCH_X: i32 = 16; // provenance: derived -- sub_8028894, asm03_0.s:4843-4884
const SLOT_ORIGIN_Y: i32 = 0x68; // provenance: derived -- sub_8028894, asm03_0.s:4843-4884
const BRACKET_INSET: i32 = 3; // provenance: derived -- sub_8028894/sub_80288D0, asm03_0.s:4843-4884
const OK_ORIGIN_X: i32 = 0x58; // provenance: derived -- sub_80288D0, asm03_0.s:4843-4884
const OK_ORIGIN_Y: i32 = 0x6b; // provenance: derived -- sub_80288D0, asm03_0.s:4843-4884

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

/// The blink table's flag bits: 0x10 flips horizontally, 0x20 vertically
/// (see Corner's own doc above).
const BRACKET_HFLIP: u8 = 0x10; // provenance: derived -- byte_80288B0/byte_80288E4 flag word
const BRACKET_VFLIP: u8 = 0x20; // provenance: derived -- byte_80288B0/byte_80288E4 flag word
const BRACKET_NONE: u8 = 0x00; // provenance: derived -- byte_80288B0/byte_80288E4 flag word (no flip bits)
const BRACKET_CORNERS: usize = 4; // provenance: derived -- byte_80288B0 holds four corner words per blink phase
const fn corner(dx: i32, dy: i32, flags: u8) -> Corner {
    Corner {
        dx,
        dy,
        hflip: flags & BRACKET_HFLIP != BRACKET_NONE,
        vflip: flags & BRACKET_VFLIP != BRACKET_NONE,
    }
}

// provenance: derived -- byte_80288B0, asm03_0.s:4860 (see the doc comment above)
const SLOT_BRACKET: [[Corner; BRACKET_CORNERS]; CURSOR_FRAMES] = [
    [
        corner(0, 0, 0), // canon: byte_80288B0 slot-bracket phase 0, top-left
        corner(0xe, 0, BRACKET_HFLIP), // canon: byte_80288B0 slot-bracket phase 0, top-right
        corner(0xe, 0xe, BRACKET_HFLIP | BRACKET_VFLIP), // canon: byte_80288B0 slot-bracket phase 0, bottom-right
        corner(0, 0xe, BRACKET_VFLIP), // canon: byte_80288B0 slot-bracket phase 0, bottom-left
    ],
    [
        corner(1, 1, 0), // canon: byte_80288B0 slot-bracket phase 1, top-left
        corner(0xc, 1, BRACKET_HFLIP), // canon: byte_80288B0 slot-bracket phase 1, top-right
        corner(0xc, 0xc, BRACKET_HFLIP | BRACKET_VFLIP), // canon: byte_80288B0 slot-bracket phase 1, bottom-right
        corner(1, 0xc, BRACKET_VFLIP), // canon: byte_80288B0 slot-bracket phase 1, bottom-left
    ],
];
// provenance: derived -- byte_80288E4, asm03_0.s:4878 (see the doc comment above)
const OK_BRACKET: [[Corner; BRACKET_CORNERS]; CURSOR_FRAMES] = [
    [
        corner(1, 2, 0), // canon: byte_80288E4 OK-bracket phase 0, top-left
        corner(0x16, 2, BRACKET_HFLIP), // canon: byte_80288E4 OK-bracket phase 0, top-right
        corner(0x16, 0x14, BRACKET_HFLIP | BRACKET_VFLIP), // canon: byte_80288E4 OK-bracket phase 0, bottom-right
        corner(1, 0x14, BRACKET_VFLIP), // canon: byte_80288E4 OK-bracket phase 0, bottom-left
    ],
    [
        corner(3, 4, 0), // canon: byte_80288E4 OK-bracket phase 1, top-left
        corner(0x14, 4, BRACKET_HFLIP), // canon: byte_80288E4 OK-bracket phase 1, top-right
        corner(0x14, 0x12, BRACKET_HFLIP | BRACKET_VFLIP), // canon: byte_80288E4 OK-bracket phase 1, bottom-right
        corner(3, 0x12, BRACKET_VFLIP), // canon: byte_80288E4 OK-bracket phase 1, bottom-left
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
    cursor: [SpriteVram; CURSOR_FRAMES],
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
        assert_eq!(&data[..MAGIC.len()], MAGIC, "not a BNCW asset");
        let at = |o: usize| u32::from_le_bytes(data[o..o + HDR_WORD_LEN].try_into().unwrap()) as usize;
        let (t, m, p, r, c, a) = (at(HDR_TILES), at(HDR_MAP), at(HDR_PALETTE), at(HDR_REGIONS), at(HDR_CURSOR), at(HDR_SLOT_ART));
        let len = at(t);
        let tiles = &data[t + HDR_WORD_LEN..t + HDR_WORD_LEN + len];
        let (w, h) = (at(m), at(m + HDR_WORD_LEN));
        assert_eq!((w, h), (MAP_W, MAP_H), "unexpected chip window map size");
        let regions = (0..at(r)) // unnamed: one Region per patch record
            .map(|i| {
                let s = r + HDR_WORD_LEN + i * REGION_RECORD_LEN;
                let e = &data[s..s + REGION_RECORD_LEN];
                Region {
                    x: e[RF_X] as usize,
                    y: e[RF_Y] as usize,
                    w: e[RF_W] as usize,
                    h: e[RF_H] as usize,
                    bank: e[RF_BANK],
                    column_major: e[RF_ORDER] == RECORD_COLUMN_MAJOR,
                }
            })
            .collect();
        let tileset = |bytes: &'static [u8]| {
            assert_eq!(bytes.as_ptr() as usize % HDR_WORD_LEN, 0, "tile data must be word aligned"); // unnamed: a zero remainder means word aligned
            // SAFETY: alignment asserted; the exporter emits whole tiles.
            unsafe { TileSet::new(bytes, TileFormat::FourBpp) }
        };
        Self {
            tiles: tileset(tiles),
            map: &data[m + MAP_HEADER_LEN..m + MAP_HEADER_LEN + w * h * MAP_ENTRY_BYTES],
            // Three variants from the window's own data, then the icon
            // bank and its dimmed copy the exporter appends.
            palette: &data[p..p + PALETTE_VARIANTS * PALETTE_VARIANT_BYTES],
            regions,
            cursor_tiles: &data[c..c + CURSOR_TILES_LEN],
            cursor_palette: read_palette(&data[c + CURSOR_TILES_LEN..c + CURSOR_TILES_LEN + PALETTE_VARIANT_BYTES]),
            cursor_obj_palette: read_palette(&data[c + CURSOR_TILES_LEN + PALETTE_VARIANT_BYTES..c + CURSOR_TILES_LEN + CURSOR_TILES_LEN]),
            regular_mark: &data[a + SLOT_MARK_AT..a + SLOT_MESSAGE_AT],
            message: tileset(&data[a + SLOT_MESSAGE_AT..a + SLOT_MESSAGE_AT + MESSAGE_TILES * TILE_BYTES]),
            message_palette: read_palette(
                &data[a + SLOT_MESSAGE_AT + MESSAGE_TILES * TILE_BYTES
                    ..a + SLOT_MESSAGE_AT + MESSAGE_TILES * TILE_BYTES + PALETTE_VARIANT_BYTES],
            ),
            empty_icon: tileset(&data[a..a + SLOT_ICON_LEN]),
            code_glyphs: tileset(&data[a + SLOT_CODE_GLYPHS_AT..a + SLOT_OK_AT]),
            ok_box: tileset(&data[a + SLOT_OK_AT..a + SLOT_STACK_AT]),
            stack_frame: tileset(
                &data[a + SLOT_STACK_AT..a + SLOT_MARK_AT],
            ),
            card_letters: tileset(&data[card_fonts_at(a)..card_fonts_at(a) + CODE_GLYPH_COUNT * CODE_GLYPH_LEN]),
            card_digits: tileset(
                &data[card_fonts_at(a) + CODE_GLYPH_COUNT * CODE_GLYPH_LEN..card_fonts_at(a) + (CODE_GLYPH_COUNT + CARD_DIGIT_GLYPHS) * CODE_GLYPH_LEN],
            ),
            elements: tileset(
                &data[card_fonts_at(a) + (CODE_GLYPH_COUNT + CARD_DIGIT_GLYPHS) * CODE_GLYPH_LEN..card_fonts_at(a) + (CODE_GLYPH_COUNT + CARD_DIGIT_GLYPHS) * CODE_GLYPH_LEN + ELEMENTS * ELEMENT_ICON_LEN],
            ),
            element_palettes: {
                let o = card_fonts_at(a) + (CODE_GLYPH_COUNT + CARD_DIGIT_GLYPHS) * CODE_GLYPH_LEN + ELEMENTS * ELEMENT_ICON_LEN;
                &data[o..o + ELEMENTS * ELEMENT_PALETTE]
            },
            font: {
                assert_eq!(&font[..FONT_MAGIC.len()], FONT_MAGIC, "not a BNTF asset");
                let fo = u32::from_le_bytes(font[BNTF_TABLE_OFF..BNTF_TABLE_OFF + HDR_WORD_LEN].try_into().unwrap()) as usize;
                let len = u32::from_le_bytes(font[fo..fo + HDR_WORD_LEN].try_into().unwrap()) as usize;
                // The second half is the colour-added copy.
                tileset(&font[fo + HDR_WORD_LEN + len / FONT_HALVES..fo + HDR_WORD_LEN + len])
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
        read_palette(&self.palette[variant * PALETTE_VARIANT_BYTES..variant * PALETTE_VARIANT_BYTES + PALETTE_VARIANT_BYTES])
    }

    /// The shared icon bank carrying this element's own last six entries,
    /// which is what the real ROM has in bank 11 while the card shows it.
    fn icon_palette(&self, element: u8) -> Palette16 {
        let mut bytes = [0u8; PALETTE_VARIANT_BYTES]; // unnamed: zeroed scratch buffer
        let base = SHARED_ICON_VARIANT * PALETTE_VARIANT_BYTES;
        let keep = PALETTE_VARIANT_BYTES - ELEMENT_PALETTE;
        bytes[..keep].copy_from_slice(&self.palette[base..base + keep]);
        let e = (element as usize).min(ELEMENTS - 1) * ELEMENT_PALETTE; // unnamed: clamp to the last element
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
        bg.set_scroll_pos((SLIDE_FROM, SCROLL_Y));
        let palette = PaletteVramSingle::try_allocate_shared(&self.cursor_obj_palette)
            .expect("cursor palette should fit in vram");
        let cursor = [0, 1].map(|i| { // unnamed: the two blink phases
            DynamicSprite16::from_bytes(Size::S8x8, &self.cursor_tiles[i * TILE_BYTES..i * TILE_BYTES + TILE_BYTES])
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
            revealed: 0, // unnamed: no columns drawn yet
            phase: Phase::Opening { x: SLIDE_FROM },
            cursor,
            mark,
            cursor_at: FIRST_SLOT,
            pending_move: 0, // unnamed: no direction waiting
            move_in: 0, // unnamed: no delayed move counting down
            pending_palettes: Vec::new(),
            frames: 0, // unnamed: the open-window frame counter starts here
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
        gfx.set_background_palette(PANEL_BANK, &self.palette(PANEL_VARIANT));
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
            Some(f) if f.window_pick_count > 0 => { // unnamed: the fixture carries picks
                custom.picks.push(f.window_pick_slot as usize);
                custom.cursor_at = f.window_cursor;
            }
            Some(_) => {}
            None => {}
        }
        for slot in 0..OFFERED { // unnamed: every offered slot
            custom.draw_slot(bg, slot);
        }
        for slot in OFFERED..SLOT_CELLS {
            if slot < SLOT_CELLS_SHOWN {
                custom.fill(bg, region_slot_icon(slot), &self.empty_icon, Some(ICON_BANK));
                let r = self.regions[region_slot_code(slot)];
                custom.fill_from(bg, r, &self.code_glyphs, (CODE_NONE * GLYPH_TILES as usize) as u16, r.bank);
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
    let mut colours = [Rgb15::new(0); 16]; // unnamed: overwritten entry by entry below
    for (i, slot) in colours.iter_mut().enumerate() {
        *slot = Rgb15::new(u16::from_le_bytes(
            bytes[i * PAL_ENTRY_BYTES..i * PAL_ENTRY_BYTES + PAL_ENTRY_BYTES].try_into().unwrap(),
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
        while self.revealed < MAP_W && (self.revealed as i32) * TILE_PX + REVEAL_MARGIN >= x {
            self.set_column(bg, self.revealed, true);
            self.revealed += 1; // unnamed: one more column drawn
        }
    }

    /// The slide-out clears the columns the window has vacated with the
    /// blank tile (byte_8026C88; sub_8026BF4). Canon clears them from the
    /// LEFT edge, one column when the new scroll x has bit 2 set and two
    /// when it is clear (sub_8026BF4's `and #4 / lsr #2 / eor #1` bit count --
    /// the slide-in's own count without the eor), which over the ten 0xc
    /// steps is exactly "column c on the first call whose x has carried it
    /// fully off the left edge, (c + 1) * 8 <= x": measured against the real
    /// ROM from /tmp/chipselect.state (Start@50,A@80), +0x44 of eS20364C0
    /// -- its cleared-column counter -- reads 1,3,4,6,7,9,10,12,13,15 across
    /// the ten calls at frames 81..90.
    /// The previous condition here tested the RIGHTMOST column
    /// ((MAP_W - 1) * 8 + 16 = 128, which no x in the slide ever reaches),
    /// so nothing was ever cleared: the whole window map stayed on BG3 and
    /// reappeared at scroll 0 the moment the close finished -- the faded
    /// copy of the window TODO F3 measures staying on the field for the
    /// whole battle.
    fn vacate(&mut self, bg: &mut RegularBackground, x: i32) {
        while self.revealed > 0 && (MAP_W - self.revealed + 1) as i32 * TILE_PX <= x { // unnamed: columns fully past the left edge
            let col = MAP_W - self.revealed;
            self.revealed -= 1; // unnamed: one more column cleared
            self.set_column(bg, col, false);
        }
    }

    fn set_column(&mut self, bg: &mut RegularBackground, col: usize, visible: bool) {
        for row in 0..MAP_H { // unnamed: every map row
            let i = row * MAP_W + col;
            let e = if visible {
                u16::from_le_bytes(self.assets.map[i * MAP_ENTRY_BYTES..i * MAP_ENTRY_BYTES + MAP_ENTRY_BYTES].try_into().unwrap())
            } else {
                FIRST_TILE
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
                    e & TILE_INDEX_MASK,
                    TileEffect::new(e & TILE_HFLIP_BIT != 0, e & TILE_VFLIP_BIT != 0, (e >> TILE_PALETTE_SHIFT) as u8), // unnamed: a clear bit means no flip
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
        self.fill_from(bg, r, tiles, FIRST_TILE, bank.unwrap_or(r.bank));
    }

    fn fill_from(&mut self, bg: &mut RegularBackground, r: Region, tiles: &TileSet, first: u16, bank: u8) {
        for k in 0..r.w * r.h { // unnamed: cells from the first
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
        for dy in 0..r.h { // unnamed: cells from the top
            for dx in 0..r.w { // unnamed: cells from the left
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
        for dy in 0..r.h { // unnamed: cells from the top
            for dx in 0..r.w { // unnamed: cells from the left
                bg.set_tile(
                    ((r.x + dx) as i32, (r.y + dy) as i32),
                    tiles,
                    TileSetting::new(FIRST_TILE, TileEffect::new(false, false, r.bank)),
                );
            }
        }
    }

    /// Repaint every offered slot. A pick changes which of the OTHERS may
    /// still be taken, so they all have to be redrawn, not just the one.
    fn draw_offered(&mut self, bg: &mut RegularBackground) {
        for slot in 0..OFFERED { // unnamed: every offered slot
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
                self.fill_from(bg, r, &assets.code_glyphs, (code * GLYPH_TILES as usize) as u16, r.bank);
            }
            // A PICKED slot keeps its code letter and loses only its icon.
            // Read off the real ROM: its fifth slot shows the empty-cell art
            // with an A still under it, and the chip that A belongs to -- a
            // Cannon, identified from the pick stack's icon -- is the one in
            // the stack.
            Some(offer) => {
                self.fill(bg, region_slot_icon(slot), &assets.empty_icon, Some(ICON_BANK));
                let r = assets.regions[region_slot_code(slot)];
                self.fill_from(bg, r, &assets.code_glyphs, (offer.code as u16) * GLYPH_TILES, r.bank);
            }
            None => {
                self.fill(bg, region_slot_icon(slot), &assets.empty_icon, Some(ICON_BANK));
                let r = assets.regions[region_slot_code(slot)];
                self.fill_from(bg, r, &assets.code_glyphs, (CODE_NONE * GLYPH_TILES as usize) as u16, r.bank);
            }
        }
    }

    /// Paint the card's text regions with its interior tile. A placeholder for
    /// the runtime text renderer; see CARD_INTERIOR_TILE.
    fn fill_card_text_background(&mut self, bg: &mut RegularBackground) {
        for index in TEXT_REGIONS {
            let r = self.assets.regions[index];
            for dy in 0..r.h { // unnamed: cells from the top
                for dx in 0..r.w { // unnamed: cells from the left
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
        for col in 0..r.w { // unnamed: glyph columns from the left
            let g = char_code(bytes.get(col).copied().unwrap_or(b' '));
            for half in 0..r.h { // unnamed: top tile over bottom tile
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
        for col in (0..r.w).rev() { // unnamed: digits right-aligned, from the last cell
            let digit = (n % DECIMAL_BASE) as u16;
            let blank = power == 0 || (n == 0 && col + 1 != r.w); // unnamed: chipless power and leading cells stay interior
            for half in 0..r.h { // unnamed: top tile over bottom tile
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
            n /= DECIMAL_BASE;
        }
    }

    /// Whether a cell belongs to the pick stack's frame columns, which
    /// draw_stack_frame owns. The stored map has the wrong tile there, so the
    /// template must not paint over them as the window slides in.
    fn in_stack_frame(&self, col: usize, row: usize) -> bool {
        let stack = self.assets.regions[REGION_STACK];
        (col == stack.x - STACK_FRAME_OFFSET || col == (stack.x + stack.w) as usize)
            && (stack.y as usize..(stack.y + stack.h) as usize).contains(&row)
    }

    /// The columns either side of the pick stack, alternating the two frame
    /// tiles down each. Read off a live menu: both columns carry the same
    /// pair, in the window's own bank.
    fn draw_stack_frame(&mut self, bg: &mut RegularBackground) {
        let stack = self.assets.regions[REGION_STACK];
        let tiles = &self.assets.stack_frame;
        for row in 0..stack.h { // unnamed: frame cells from the top
            // The right column is the left one MIRRORED: the real ROM's map
            // has the same two tiles there with h-flip set.
            for (col, hflip) in [(stack.x - STACK_FRAME_OFFSET, false), (stack.x + stack.w, true)] {
                bg.set_tile(
                    (col as i32, (stack.y + row) as i32),
                    tiles,
                    // The top two rows have their own pair; the rest
                    // alternate the first two down the column.
                    TileSetting::new(
                        if row < STACK_FRAME_HEAD_ROWS { STACK_FRAME_HEAD_TILE + row as u16 } else { (row % STACK_FRAME_PAIR) as u16 },
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
        for row in 0..HAND_SIZE { // unnamed: one icon per pick row
            let cell = Region {
                x: stack.x,
                y: stack.y + row * STACK_CELL,
                w: STACK_CELL,
                h: STACK_CELL,
                bank: stack.bank,
                column_major: false,
            };
            match self.picks.get(row).and_then(|&slot| self.slots[slot]) {
                Some(offer) => {
                    let icon = offer.chip.icon();
                    self.fill_from(bg, cell, &icon, FIRST_TILE, ICON_BANK);
                }
                None => self.fill_from(bg, cell, &assets.empty_icon, FIRST_TILE, stack.bank),
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
            if self.pictured.is_some() || self.frames == 0 { // unnamed: first frame, or the card showed a chip
                self.pictured = None;
                self.pending_palettes
                    .push((PICTURE_BANK, self.assets.message_palette.clone()));
                let r = self.assets.regions[REGION_PICTURE];
                self.fill_from(bg, r, &self.assets.message, FIRST_TILE, PICTURE_BANK);
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
        self.fill_from(bg, r, &picture, FIRST_TILE, PICTURE_BANK);
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
        let name = picked[FIRST_PICK].chip.name();
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
    /// True on exactly the frames whose [`Custom::update`] will run a
    /// slide-OUT step -- the ten calls canon makes from `sub_8026BF4`
    /// (reference/bn6f/asm/asm03_0.s:1037) while its slide counter climbs
    /// 0xc..0x78.
    ///
    /// Canon pans the battle camera back up FROM INSIDE that routine: every
    /// slide-out call adds `dword_8026CC8` = 0x18000 to the camera's y at
    /// Camera+0x34 (asm03_0.s:1099-1104), and the slide-IN routine subtracts
    /// the same value on each of its own calls (asm03_0.s:964-969). 0x18000
    /// is 1.5 px in the camera's 16.16 fixed point, so ten calls are the
    /// 15-px pan -- and it runs WITH the window, not after it. Callers that
    /// drive the field's scroll need to know the slide is running before
    /// [`Custom::update`] consumes the frame, which is what this answers.
    pub fn is_closing(&self) -> bool {
        matches!(self.phase, Phase::Closing { x } if x < SLIDE_FROM)
    }

    pub fn update(&mut self, bg: &mut RegularBackground, input: &ButtonController, gfx: &Graphics) -> bool {
        // Last frame's card palettes, now that its tiles have landed.
        for (bank, palette) in self.pending_palettes.drain(..) {
            gfx.set_background_palette(bank, &palette);
        }
        self.phase = match self.phase {
            Phase::Opening { x } if x > SCROLL_OPEN => {
                let x = (x - SLIDE_STEP).max(SCROLL_OPEN);
                bg.set_scroll_pos((x, SCROLL_Y));
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
                if x == SCROLL_OPEN { Phase::Open } else { Phase::Opening { x } }
            }
            Phase::Opening { .. } => Phase::Open,
            Phase::Open => {
                self.frames += 1; // unnamed: one frame passes
                self.navigate(bg, input, gfx)
            }
            Phase::Closing { x } if x < SLIDE_FROM => {
                let x = (x + SLIDE_STEP).min(SLIDE_FROM);
                bg.set_scroll_pos((x, SCROLL_Y));
                self.vacate(bg, x);
                // Canon's slide-out advances AND finishes in the same call:
                // sub_8026BF4 (reference/bn6f/asm/asm03_0.s:1037) adds 0xc
                // to the slide counter on entry (asm03_0.s:1060-1062) and,
                // once it reads exactly 0x78, flips JumpOffset01/Unk_02 in
                // that same tenth call (asm03_0.s:1119-1125) -- it never
                // rests a frame at the fully-off-screen position. Returning
                // Closing { x: SLIDE_FROM } here spent one extra frame on
                // the blank window, so the post-close HUD redraw (battle.rs
                // runs it the update after `custom` becomes None) landed a
                // frame late: windowclose BG3 k=10 blank on both sides, k=11
                // canon settled / ours still blank (2447 px, y0..15), k=12
                // settled on both sides (measured this ticket, offset 253).
                if x == SLIDE_FROM {
                    Phase::Done
                } else {
                    Phase::Closing { x }
                }
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
                self.pending_move = MOVE_RIGHT;
                self.move_in = CURSOR_DELAY;
            }
            Tri::Negative => {
                self.pending_move = MOVE_LEFT;
                self.move_in = CURSOR_DELAY;
            }
            Tri::Zero => {}
        }
        if self.move_in > 0 { // unnamed: a delayed move is counting down
            self.move_in -= 1; // unnamed: one frame closer to the move
            if self.move_in == 0 { // unnamed: the delay has run out
                self.cursor_at = if self.pending_move > 0 { // unnamed: the waiting direction is right
                    match self.cursor_at {
                        LAST_SLOT => OK,
                        OK => FIRST_SLOT,
                        i => i + 1, // unnamed: next slot in the ring
                    }
                } else {
                    match self.cursor_at {
                        FIRST_SLOT => OK,
                        OK => LAST_SLOT,
                        i => i - 1, // unnamed: previous slot in the ring
                    }
                };
            }
        }
        if input.is_just_pressed(Button::Start) {
            self.cursor_at = OK;
        }
        if input.is_just_pressed(Button::A) {
            if self.cursor_at == OK {
                return Phase::Closing { x: SCROLL_OPEN };
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
    /// Canon's `eStruct2035280 + 0x12` (0x02035292): the X displacement every
    /// battle-HUD OBJECT element takes while the chip window is up, which is
    /// this window's own slide counter measured from the OPEN position --
    /// `SLIDE_FROM` (0x78) minus the counter this type already keeps, so it
    /// is 0 with the window fully off screen, 0x78 with it fully open, and
    /// canon's 0x0c-a-frame ramp in between, by construction. Verified
    /// against the real ROM with `--watch 0x02035290:8`: 0 -> 0x78 in ten
    /// 0x0c steps at BATTLESTART canon 187..196, and 0x78 -> 0 in ten at
    /// CHIPSELECT + Start@50,A@80 canon 81..90. Read by `emotion.rs`'s draw
    /// (canon's element 14, sub_801CDEC asm00_2.s:27561).
    pub fn hud_obj_x(&self) -> i32 {
        SLIDE_FROM
            - match self.phase {
                Phase::Opening { x } | Phase::Closing { x } => x,
                Phase::Open => SCROLL_OPEN,
                Phase::Done => SLIDE_FROM,
            }
    }

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
        if let Some((_, power)) = self.pictured.filter(|&(_, p)| p > 0) { // unnamed: chips with no attack show no digits
            let r = self.assets.regions[REGION_DAMAGE];
            hud.draw_number(frame, power, ((r.x + r.w) * TILE_PX as usize) as i32, (r.y * TILE_PX as usize) as i32);
        }
        // The origin is the slot's position less 3 in each axis
        // (sub_8028894, sub_80288D0, asm03_0.s:4843-4884: a slot sits at
        // (8 + 16 * index, 0x68), OK at (0x58 + 3, 0x70 - 2)).
        let (x, y, bracket) = if self.cursor_at == OK {
            (OK_ORIGIN_X, OK_ORIGIN_Y, &OK_BRACKET)
        } else {
            (SLOT_ORIGIN_X + SLOT_PITCH_X * self.cursor_at as i32 - BRACKET_INSET, SLOT_ORIGIN_Y - BRACKET_INSET, &SLOT_BRACKET)
        };
        // The counter is bumped at the top of the frame, before anything is
        // drawn, so the first DRAWN frame already reads 1 and every phase flip
        // lands a frame before the real ROM's. Draw from the value the frame
        // started with.
        let phase = (self.frames.saturating_sub(1) >> BLINK_SHIFT) as usize & 1; // unnamed: previous frame's counter, low bit selects the phase
        for c in &bracket[phase] {
            Object::new(self.cursor[phase].clone())
                .set_pos((x + c.dx, y + c.dy))
                .set_hflip(c.hflip)
                .set_vflip(c.vflip)
                .show(frame);
        }
    }
}
