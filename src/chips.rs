//! Battle chip records and card art, read from assets/chips.bin (BNCH,
//! tools/chip_export.py): a subset of ChipDataArr_8021DA8 (data/ChipDataArr.s,
//! layout include/rom_structs/ChipData.inc) with each chip's 16x16 icon
//! (byte_8725894 + id * 0x80), its 7x6-tile card picture and its palette.

use agb::display::tiled::{TileFormat, TileSet};

const MAGIC: &[u8; 4] = b"BNCH";
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
        let count = u32::from_le_bytes(data[8..12].try_into().unwrap()) as usize;
        // v2 appends the behavioural tail after the blobs; the v1 table and
        // blobs are byte-identical, so the tail is found from the file end.
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
