#![warn(missing_docs)]
use crate::memory_mapped::MemoryMapped;

const MOSAIC: MemoryMapped<u16> = unsafe { MemoryMapped::new(0x0400_004C) };

/// Control the mosaic effect for the frame.
///
/// The mosaic effect draws a layer in blocks, repeating the top-left pixel of each
/// block over the rest of it, which is the classic pixelated fade. The block size is
/// set once per frame for backgrounds and once for objects; a background opts in
/// through its own settings and an object through
/// [`set_mosaic`](crate::display::object::Object::set_mosaic).
///
/// Sizes are 0 to 15, giving blocks of 1 to 16 pixels.
pub struct Mosaic {
    register: u16,
}

impl Mosaic {
    pub(crate) fn new() -> Self {
        Self { register: 0 }
    }

    /// Set the block size used by backgrounds with mosaic enabled.
    pub fn set_background(&mut self, horizontal: u8, vertical: u8) -> &mut Self {
        assert!(horizontal < 16 && vertical < 16, "mosaic sizes are 0..=15");
        self.register = (self.register & 0xff00) | u16::from(horizontal) | (u16::from(vertical) << 4);

        self
    }

    /// Set the block size used by objects with mosaic enabled.
    pub fn set_object(&mut self, horizontal: u8, vertical: u8) -> &mut Self {
        assert!(horizontal < 16 && vertical < 16, "mosaic sizes are 0..=15");
        self.register =
            (self.register & 0x00ff) | (u16::from(horizontal) << 8) | (u16::from(vertical) << 12);

        self
    }

    pub(crate) fn commit(&self) {
        MOSAIC.set(self.register);
    }
}
