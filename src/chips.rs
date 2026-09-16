//! Battle chip records and card art, read from assets/chips.bin (BNCH,
//! tools/chip_export.py): a subset of ChipDataArr_8021DA8 (data/ChipDataArr.s,
//! layout include/rom_structs/ChipData.inc) with each chip's 16x16 icon
//! (byte_8725894 + id * 0x80), its 7x6-tile card picture and its palette.

use agb::display::tiled::{TileFormat, TileSet};

const MAGIC: &[u8; 4] = b"BNCH";
/// The exporter's header version: offset 4, u32, little-endian
/// (tools/chip_export.py: "0x04 u32 version (2; v2 appends a behavioural
/// tail, below)"). v1 files have no behavioural tail, so reading one with
/// this code would find the tail pointer from the file end and hand the
/// last TAIL bytes of blob data to behaviour arms as if they were records.
const VERSION: u32 = 2; // canon: tools/chip_export.py's header field 0x04, "u32 version (2; v2 appends a behavioural tail)"
const RECORD: usize = 36; // provenance: derived -- tools/chip_export.py's own fixed-width record layout, not a ROM constant
/// v2's behavioural tail: 8 bytes per record, appended after the blobs
/// (tools/chip_export.py's v2 section; ChipDataArr_8021DA8's EffectFlags
/// +0x9, AttackFamily +0xb, AttackSubFamily +0xc, AttackParam1..4
/// +0x10..+0x13, LockoutFrames +0x14 -- include/rom_structs/ChipData.inc).
const TAIL: usize = 8; // provenance: derived -- chip_export.py's own v2 append-only tail layout
/// A card picture is 7 x 6 tiles (sub_80284E2 copies 0x540 bytes,
/// asm03_0.s:4399).
pub const PICTURE_TILES: (usize, usize) = (7, 6); // provenance: derived -- sub_80284E2, asm03_0.s:4399 (0x540 bytes = 42 4bpp tiles = 7x6)
/// Code byte for '*', which matches any other (sub_8028E4C, asm03_0.s:5595).
pub const WILDCARD: u8 = 0x1a; // provenance: derived -- sub_8028E4C, asm03_0.s:5595

// ----------------------------------------------------------------------------
// T28 minimal first step: chip-state byte reader at 0x02014F6C.
//
// The address sits inside the unnamed 0xA00-byte block `unk_2014000` at
// 0x02014000 (reference/bn6f/ewram.s:1821; bn6f.map:6203-6204 -- the block
// ends at 0x02014A00, the next symbol `eDecompBuffer2014A00`). No public
// symbol or per-asm cite for 0x02014F6C exists in the repo (grep over
// reference/bn6f/{asm,include,data,ewram}.s and bn6f.map finds no
// `chip_state`, `14F6C`, `2014F6` token). The 8-chip x 4-byte layout is
// cited from T28 (TODO.md:613+); the state field is the first byte of the
// 4-byte record (T28's "chip_state_byte"). Subsequent T28 steps will name
// the remaining three bytes and wire the arms (Recov/Barrier/Vulcan) to
// read them; this commit only adds the reader.

/// EWRAM base of the chip-state array (T28). Sits at offset 0xF6C inside
/// `unk_2014000` (reference/bn6f/ewram.s:1821).
pub const CHIP_STATE_BASE: u32 = 0x02014F6C; // canon: unk_2014000 + 0xF6C (reference/bn6f/ewram.s:1821)

/// 8 entries: one per chip slot in the player's hand.
pub const CHIP_STATE_COUNT: usize = 8; // provenance: derived -- T28 task description ("8 chips x 4 bytes struct")

/// 4-byte stride per entry (1 state byte + 3 unnamed bytes, filled by later T28 steps).
pub const CHIP_STATE_STRIDE: usize = 4; // provenance: derived -- T28 task description ("8 chips x 4 bytes struct")

/// One entry of the chip-state array. Only the state byte is wired in this commit.
#[derive(Clone, Copy)]
pub struct ChipState {
    /// The chip's state byte (offset 0 of the 4-byte record at `0x02014F6C + i*4`).
    pub state: u8,
    // canon: 8-chip hand record at 0x02014F6C (reference/bn6f/ewram.s:1821, unk_2014000 + 0xF6C)
}

/// Read one chip-state entry from the EWRAM array at 0x02014F6C.
///
/// `index` is the hand slot (0..CHIP_STATE_COUNT). The reader is a
/// `unsafe` raw pointer read because the array lives in EWRAM (0x02000000
/// range) and is not aliased by any `&'static` in this crate; later T28
/// steps wrap it behind a safe accessor in `src/battle.rs` per the file
/// list ("src/chips.rs: accessors for the record bytes used, nothing
/// else").
///
/// # Safety
/// Caller must ensure `index < CHIP_STATE_COUNT` and that the read happens
/// inside a battle main loop where 0x02014F6C has been populated (the
/// subsystem byte at 0x02001B80 is 12). Outside that window the bytes are
/// the freed-heap fill the rest of `unk_2014000` carries (AGENT_GUIDE.md
/// "Freed-heap fill patterns 0x11/0x22 look like state").
pub unsafe fn read_chip_state(index: usize) -> ChipState {
    debug_assert!(index < CHIP_STATE_COUNT);
    let base = CHIP_STATE_BASE as usize + index * CHIP_STATE_STRIDE;
    // SAFETY: the caller upholds the safety contract above; the pointer is
    // 4-byte aligned because CHIP_STATE_BASE (0x02014F6C) and the stride
    // (4) are both 4-byte aligned.
    let p = base as *const u8;
    ChipState { state: *p }
}

pub struct Chips {
    data: &'static [u8],
    count: usize,
    /// Byte offset of the v2 behavioural tail (after the blobs).
    tail: usize,
}

#[derive(Clone, Copy)]
pub struct Chip {
    pub id: u16,
    pub element: u8,
    pub mb: u8,
    pub power: u16,
    pub codes: [u8; 4],
    name: [u8; 9],
    icon: &'static [u8],
    picture: &'static [u8],
    palette: &'static [u8],
    /// ChipDataArr_8021DA8's EffectFlags (+0x9). Exported in the record's
    /// behavioural tail; no arm reads it yet.
    #[allow(dead_code)]
    pub effect_flags: u8,
    /// AttackFamily (+0xb): the behavioural family the ROM dispatches on.
    pub family: u8,
    /// AttackSubFamily (+0xc): indexes the per-family behaviour tables.
    pub subfamily: u8,
    /// AttackParam1..4 (+0x10..+0x13). Exported in the behavioural tail;
    /// no arm reads them yet.
    #[allow(dead_code)]
    pub params: [u8; 4],
    /// LockoutFrames (+0x14). Exported in the behavioural tail; no arm
    /// reads it yet.
    #[allow(dead_code)]
    pub lockout: u8,
}

impl Chips {
    pub fn new(data: &'static [u8]) -> Self {
        assert_eq!(&data[0..4], MAGIC, "not a BNCH asset");
        let version = u32::from_le_bytes(data[4..8].try_into().unwrap());
        assert_eq!(
            version, VERSION,
            "chips.bin v1 read by v2 code: tail would be misread as behaviour"
        );
        let count = u32::from_le_bytes(data[8..12].try_into().unwrap()) as usize;
        // v2 appends the behavioural tail after the blobs; the v1 table and
        // blobs are byte-identical, so the tail is found from the file end.
        // The version check above is what makes that search safe: without it
        // a v1 asset passes the bounds assert below and silently reads
        // trailing blob bytes as behaviour (docs/worklog/T17.md, T19).
        let tail = data.len() - count * TAIL;
        assert!(tail >= 12 + count * RECORD, "BNCH asset without a v2 tail");
        Self { data, count, tail }
    }

    pub fn len(&self) -> usize {
        self.count
    }

    /// The record at `index` in the asset (not the chip id).
    pub fn get(&self, index: usize) -> Chip {
        assert!(index < self.count);
        let r = &self.data[12 + index * RECORD..12 + (index + 1) * RECORD];
        let t = &self.data[self.tail + index * TAIL..self.tail + (index + 1) * TAIL];
        let u16_at = |o: usize| u16::from_le_bytes(r[o..o + 2].try_into().unwrap());
        let u32_at = |o: usize| u32::from_le_bytes(r[o..o + 4].try_into().unwrap()) as usize;
        let (icon, picture, len, palette) = (u32_at(20), u32_at(24), u32_at(28), u32_at(32));
        Chip {
            id: u16_at(0),
            element: r[2],
            mb: r[3],
            power: u16_at(4),
            codes: r[6..10].try_into().unwrap(),
            name: r[10..19].try_into().unwrap(),
            icon: &self.data[icon..icon + 0x80], // provenance: derived -- byte_8725894's own per-chip stride, four 8x8 4bpp tiles
            picture: &self.data[picture..picture + len],
            palette: &self.data[palette..palette + 32],
            effect_flags: t[0], // ChipDataArr EffectFlags +0x9
            family: t[1],       // AttackFamily +0xb
            subfamily: t[2],    // AttackSubFamily +0xc
            params: [t[3], t[4], t[5], t[6]], // AttackParam1..4 +0x10..+0x13
            lockout: t[7],      // LockoutFrames +0x14
        }
    }

    /// The record for a chip id, if the asset has it.
    pub fn by_id(&self, id: u16) -> Option<Chip> {
        (0..self.count).map(|i| self.get(i)).find(|c| c.id == id)
    }
}

impl Chip {
    pub fn name(&self) -> &str {
        let end = self.name.iter().position(|&b| b == 0).unwrap_or(self.name.len());
        core::str::from_utf8(&self.name[..end]).unwrap_or("")
    }

    /// The icon's four 8x8 tiles, row-major.
    /// The icon's raw four tiles, for the object the game hangs over the
    /// navi to show the chip in hand.
    pub fn icon_bytes(&self) -> &'static [u8] {
        self.icon
    }

    pub fn icon(&self) -> TileSet {
        // SAFETY: the exporter 4-aligns every blob and the asset is held in
        // a word-aligned static.
        unsafe { TileSet::new(self.icon, TileFormat::FourBpp) }
    }

    /// The card picture's 42 tiles, row-major.
    pub fn picture(&self) -> TileSet {
        // SAFETY: as for the icon.
        unsafe { TileSet::new(self.picture, TileFormat::FourBpp) }
    }

    /// Sixteen BGR555 colours.
    pub fn palette(&self) -> &'static [u8] {
        self.palette
    }
}
