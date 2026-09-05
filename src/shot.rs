//! The MegaBuster's shot: a hitbox hopping one panel at a time.
//!
//! bn6f models the shot as a temp attack object whose update state decrements
//! `Timer` and moves one panel once it drops below zero, so each hop costs two
//! frames (t3_0x0_80C4E58 -> sub_80C4E7C/sub_80C4F02, asm31.s:27728, 27769).
//! The shot has no sprite yet, so it is invisible; the hit it lands is not.

use agb::display::GraphicsFrame;
use agb::display::object::Object;

use crate::field;
use crate::spr;

/// Frames per hop: the timer is seeded from `Timer2 = 1` on spawn (asm31.s:27728)
/// and one decrement takes it to zero, the next past it, so one panel every
/// two frames.
const HOP_FRAMES: u8 = 2;

/// The shot's graphics live in the effect sprite list: byte_80B8BD4's record
/// selects `SpritePointersList` offset 0xc (`off_8031E00`) slot 2, which is
/// `sprite_82F569C` (data/SpritePointersList.s:88).
const ANIM: usize = 0;

pub struct Shot {
    pub col: i32,
    pub row: i32,
    /// +1 travelling right, -1 left.
    pub dx: i32,
    ticks: u8,
    /// Carried for when hits subtract damage; flinching is all a hit does yet.
    #[allow(dead_code)]
    pub damage: u16,
    player: spr::Player,
}

impl Shot {
    pub fn new(assets: spr::Assets, col: i32, row: i32, dx: i32, damage: u16) -> Self {
        Self {
            col,
            row,
            dx,
            ticks: HOP_FRAMES,
            damage,
            player: spr::Player::new(assets, ANIM),
        }
    }

    pub fn show(&self, frame: &mut GraphicsFrame) {
        let (px, py) = field::panel_centre(self.col, self.row);
        for part in self.player.parts() {
            let x = if self.dx < 0 {
                -part.x - part.width
            } else {
                part.x
            };
            Object::new(part.sprite.clone())
                .set_pos((px + x, py + part.y))
                .set_hflip(part.hflip ^ (self.dx < 0))
                .set_vflip(part.vflip)
                .show(frame);
        }
    }

    /// Advance one frame, hopping a panel whenever the timer runs out. Returns
    /// false once the shot leaves the field (col outside 1..=6) so the caller
    /// drops it; bn6f likewise destroys the shot when its panel goes invalid.
    pub fn update(&mut self) -> bool {
        self.player.update();
        self.ticks -= 1;
        if self.ticks == 0 {
            self.col += self.dx;
            self.ticks = HOP_FRAMES;
        }
        (1..=field::COLS).contains(&self.col)
    }
}
