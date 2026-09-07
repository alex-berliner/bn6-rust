//! Battle chip records and card art, read from assets/chips.bin (BNCH,
//! tools/chip_export.py): a subset of ChipDataArr_8021DA8 (data/ChipDataArr.s,
//! layout include/rom_structs/ChipData.inc) with each chip's 16x16 icon
//! (byte_8725894 + id * 0x80), its 7x6-tile card picture and its palette.

use agb::display::tiled::{TileFormat, TileSet};

const MAGIC: &[u8; 4] = b"BNCH";
const RECORD: usize = 36;
/// A card picture is 7 x 6 tiles (sub_80284E2 copies 0x540 bytes,
/// asm03_0.s:4399).
pub const PICTURE_TILES: (usize, usize) = (7, 6);
/// Code byte for '*', which matches any other (sub_8028E4C, asm03_0.s:5595).
pub const WILDCARD: u8 = 0x1a;

pub struct Chips {
    data: &'static [u8],
    count: usize,
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
}

impl Chips {
    pub fn new(data: &'static [u8]) -> Self {
        assert_eq!(&data[0..4], MAGIC, "not a BNCH asset");
        let count = u32::from_le_bytes(data[8..12].try_into().unwrap()) as usize;
        Self { data, count }
    }

    pub fn len(&self) -> usize {
        self.count
    }

    /// The record at `index` in the asset (not the chip id).
    pub fn get(&self, index: usize) -> Chip {
        assert!(index < self.count);
        let r = &self.data[12 + index * RECORD..12 + (index + 1) * RECORD];
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
            icon: &self.data[icon..icon + 0x80],
            picture: &self.data[picture..picture + len],
            palette: &self.data[palette..palette + 32],
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
