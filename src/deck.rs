//! The battle folder: the thirty chips the chip select window deals from.
//!
//! The game builds it once in the battle intro (sub_800A3E4, asm00_1.s:15355)
//! by copying the PET navi's folder into eBattleFolder as packed halfwords --
//! chip id in the low nine bits, code above (getChipID_802A54E,
//! asm03_0.s:8820) -- and shuffling it with the secondary generator
//! (sub_800A570, asm00_1.s:15568). There is no draw pointer: the window
//! offers the first live entries (sub_8027EE8, asm03_0.s:3510), the picks are
//! blanked to 0xffff at OK (sub_80293F8, asm03_0.s:6413) and the survivors
//! are packed to the front the next time the window opens (sub_802945A,
//! asm03_0.s:6470), so chips passed over come round again and the deck only
//! ever shrinks.
//!
//! The reg chip, tags and the giga re-insertion that the shuffle also does
//! (asm00_1.s:15398-15698) are not reproduced: the folder here has none.

pub const FOLDER_SIZE: usize = 30;
pub const EMPTY: u16 = 0xffff;

/// The secondary RNG (GetRNGSecondary, asm00_0.s:2643): rotate left one,
/// add one, xor the constant.
pub struct Rng(u32);

impl Rng {
    pub fn new(seed: u32) -> Self {
        Self(seed)
    }

    pub fn next(&mut self) -> u32 {
        self.0 = (self.0.rotate_left(1).wrapping_add(1)) ^ 0x873c_a9e5;
        self.0
    }

    /// GetPositiveSignedRNGSecondary: the same step with the sign cleared.
    pub fn positive(&mut self) -> u32 {
        self.next() & 0x7fff_ffff
    }
}

pub struct Deck {
    chips: [u16; FOLDER_SIZE],
}

impl Deck {
    /// Pack a chip and its code letter (0 = A) the way the folder does.
    pub const fn entry(id: u16, code: u8) -> u16 {
        id | (code as u16) << 9
    }

    pub const fn id(entry: u16) -> u16 {
        entry & 0x1ff
    }

    pub const fn code(entry: u16) -> u8 {
        (entry >> 9) as u8
    }

    /// A deck holding exactly these entries in this order, for a fixture that
    /// has to offer the same chips a capture does. Not a shuffle.
    pub fn stacked<const N: usize>(entries: [u16; N]) -> Self {
        let mut chips = [EMPTY; FOLDER_SIZE];
        chips[..N].copy_from_slice(&entries);
        Self { chips }
    }

    /// A folder shuffled as the battle intro does: ShuffleHwordList_SecondaryRNG
    /// (asm00_0.s:1343) swaps two random positions once per entry.
    pub fn new(folder: [u16; FOLDER_SIZE], rng: &mut Rng) -> Self {
        let mut chips = folder;
        let len = chips.len() as u32;
        for _ in 0..len {
            let i = (rng.positive() % len) as usize;
            let j = (rng.positive() % len) as usize;
            chips.swap(i, j);
        }
        Self { chips }
    }

    /// Pack the live chips to the front, as opening the window does.
    pub fn compact(&mut self) {
        let mut next = 0;
        for i in 0..FOLDER_SIZE {
            if self.chips[i] != EMPTY {
                self.chips.swap(i, next);
                next += 1;
            }
        }
    }

    /// The entries the window offers: the first `count` live ones.
    pub fn offer(&self, count: usize) -> &[u16] {
        let live = self.chips.iter().take_while(|&&c| c != EMPTY).count();
        &self.chips[..live.min(count)]
    }

    /// Remove an offered chip by its slot index.
    pub fn take(&mut self, slot: usize) -> u16 {
        core::mem::replace(&mut self.chips[slot], EMPTY)
    }

    pub fn remaining(&self) -> usize {
        self.chips.iter().filter(|&&c| c != EMPTY).count()
    }
}
