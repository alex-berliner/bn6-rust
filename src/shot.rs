//! Travelling hitboxes that hop one panel at a time: the buster's shot and the
//! Mettaur's shockwave.
//!
//! bn6f models the shot as a temp attack object whose update state decrements
//! `Timer` and moves one panel once it drops below zero, so each hop costs two
//! frames (t3_0x0_80C4E58 -> sub_80C4E7C/sub_80C4F02, asm31.s:27728, 27769).
//! The shockwave is its own object that dwells 0x16 frames on each panel in
//! its first version and keeps going until the panel ahead is invalid
//! (t3_0x16_80C6B40, asm31.s:31354; byte_80C6B00, 31306).

use agb::display::GraphicsFrame;
use agb::display::object::Object;

use crate::field;
use crate::spr;

/// Frames per hop for the buster: the timer is seeded from `Timer2 = 1` on
/// spawn (asm31.s:27728) and one decrement takes it to zero, the next past
/// it, so one panel every two frames.
const BUSTER_HOP: u8 = 2;
/// The shockwave's dwell per panel in its first version (byte_80C6B00).
const WAVE_HOP: u8 = 0x16;

/// The buster shot's graphics live in the effect sprite list: byte_80B8BD4's
/// record selects `SpritePointersList` offset 0xc (`off_8031E00`) slot 2,
/// `sprite_82F569C` (data/SpritePointersList.s:88). The shockwave's are
/// `off_8031FA4` slot 3, `sprite_83536BC`, animation 0 in its first version.
const ANIM: usize = 0;

pub struct Shot {
    pub col: i32,
    pub row: i32,
    /// +1 travelling right, -1 left.
    pub dx: i32,
    ticks: u8,
    interval: u8,
    /// Whether the hitbox keeps going after landing a hit.
    pub piercing: bool,
    /// Fired by the player, so it hits enemies; otherwise it hits the player.
    pub from_player: bool,
    pub damage: u16,
    player: spr::Player,
}

impl Shot {
    pub fn buster(assets: spr::Assets, col: i32, row: i32, dx: i32, damage: u16) -> Self {
        Self::new(assets, col, row, dx, damage, BUSTER_HOP, false, true)
    }

    pub fn shockwave(assets: spr::Assets, col: i32, row: i32, dx: i32, damage: u16) -> Self {
        Self::new(assets, col, row, dx, damage, WAVE_HOP, true, false)
    }

    #[allow(clippy::too_many_arguments)]
    fn new(
        assets: spr::Assets,
        col: i32,
        row: i32,
        dx: i32,
        damage: u16,
        interval: u8,
        piercing: bool,
        from_player: bool,
    ) -> Self {
        Self {
            col,
            row,
            dx,
            ticks: interval,
            interval,
            piercing,
            from_player,
            damage,
            player: spr::Player::new(assets, ANIM),
        }
    }

    /// True on the frame the hitbox arrived on its panel, including the one
    /// it was spawned on, so a dwelling wave hits each panel once.
    pub fn just_arrived(&self) -> bool {
        self.ticks == self.interval
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
            self.ticks = self.interval;
        }
        (1..=field::COLS).contains(&self.col)
    }
}
