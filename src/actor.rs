//! A character standing on the battle field, and how it moves between panels.
//!
//! Movement is a warp, not a slide. `BattleObject` keeps the panel it is on at
//! 0x12/0x13 and the panel it is heading to at 0x14/0x15
//! (include/structs/BattleObject.inc:63), so a move is a transition with a
//! target rather than an instant write. The sprite backs that up: animations 4
//! and 3 are a matched pair that dissolves the navi out and materialises it
//! back in, so the panel is committed at the midpoint, hidden by the dissolve.

use agb::display::GraphicsFrame;
use agb::display::object::Object;

use crate::field;
use crate::spr;

/// Animation indices in the exported navi sprites. Only a handful of
/// animations set the loop flag, so these are one-shot and re-triggered here.
pub mod anim {
    pub const IDLE: usize = 0;
    pub const WARP_IN: usize = 3;
    pub const WARP_OUT: usize = 4;
}

enum Movement {
    Still,
    /// Dissolving away; `to` is committed as the current panel when this ends.
    Leaving { to: (i32, i32) },
    /// Materialising on the panel just arrived at.
    Arriving,
}

pub struct Actor {
    player: spr::Player,
    col: i32,
    row: i32,
    /// Enemies face left, which mirrors the composed frame.
    facing_left: bool,
    movement: Movement,
}

impl Actor {
    pub fn new(assets: spr::Assets, col: i32, row: i32, facing_left: bool) -> Self {
        Self {
            player: spr::Player::new(assets, anim::IDLE),
            col,
            row,
            facing_left,
            movement: Movement::Still,
        }
    }

    pub fn is_moving(&self) -> bool {
        !matches!(self.movement, Movement::Still)
    }

    /// Start warping by one panel. Refused while a warp is already running or
    /// when the step would leave this actor's half of the field.
    pub fn step(&mut self, dx: i32, dy: i32) -> bool {
        if self.is_moving() {
            return false;
        }
        let (to_col, to_row) = (self.col + dx, self.row + dy);
        let (min_col, max_col) = field::half(self.facing_left);
        if !(min_col..=max_col).contains(&to_col) || !(1..=field::ROWS).contains(&to_row) {
            return false;
        }
        self.movement = Movement::Leaving {
            to: (to_col, to_row),
        };
        self.player.play(anim::WARP_OUT);
        true
    }

    pub fn update(&mut self) {
        self.player.update();
        if !self.player.finished() {
            return;
        }
        match self.movement {
            Movement::Leaving { to } => {
                (self.col, self.row) = to;
                self.movement = Movement::Arriving;
                self.player.play(anim::WARP_IN);
            }
            Movement::Arriving => {
                self.movement = Movement::Still;
                self.player.play(anim::IDLE);
            }
            Movement::Still => {}
        }
    }

    pub fn show(&self, frame: &mut GraphicsFrame) {
        let (px, py) = field::panel_centre(self.col, self.row);
        for part in self.player.parts() {
            // Offsets are authored facing right, so mirroring reflects the
            // whole composed frame about the actor origin, not each part in
            // place: the part's left edge moves to the opposite side.
            let x = if self.facing_left {
                -part.x - part.width
            } else {
                part.x
            };
            Object::new(part.sprite.clone())
                .set_pos((px + x, py + part.y))
                .set_hflip(part.hflip ^ self.facing_left)
                .set_vflip(part.vflip)
                .show(frame);
        }
    }
}
