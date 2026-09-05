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

/// Frame counts taken from the move state machine, which runs one step per
/// frame across `sub_80EB088` -> `sub_80EB128` -> `sub_80EB194` ->
/// `sub_80EB1C4` (asm/asm31.s:108036 onwards). The recovery length is
/// per-navi and defaults to 4 (`sub_8010332`, asm/asm00_2.s:3121).
///
/// The timings are the state machine's, not the animations': the dissolve is
/// cut off after three of its four frames when the panel is committed.
const LEAVING_FRAMES: u8 = 3;
const ARRIVING_FRAMES: u8 = 5;
const RECOVERING_FRAMES: u8 = 4;

#[derive(Clone, Copy)]
enum Movement {
    Still,
    /// Dissolving away; `to` is committed as the current panel when this ends.
    Leaving { to: (i32, i32), ticks: u8 },
    /// Materialising on the panel just arrived at.
    Arriving { ticks: u8 },
    /// Standing again but still locked out of another move.
    Recovering { ticks: u8 },
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

    /// The panel the actor currently stands on, 1-based. During a warp this is
    /// the panel being left until the move commits at the midpoint.
    pub fn panel(&self) -> (i32, i32) {
        (self.col, self.row)
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
            ticks: LEAVING_FRAMES,
        };
        self.player.play(anim::WARP_OUT);
        true
    }

    pub fn update(&mut self) {
        self.player.update();
        self.movement = match self.movement {
            Movement::Still => Movement::Still,
            Movement::Leaving { to, ticks } if ticks > 1 => Movement::Leaving {
                to,
                ticks: ticks - 1,
            },
            Movement::Leaving { to, .. } => {
                (self.col, self.row) = to;
                self.player.play(anim::WARP_IN);
                Movement::Arriving {
                    ticks: ARRIVING_FRAMES,
                }
            }
            Movement::Arriving { ticks } if ticks > 1 => Movement::Arriving { ticks: ticks - 1 },
            Movement::Arriving { .. } => {
                self.player.play(anim::IDLE);
                Movement::Recovering {
                    ticks: RECOVERING_FRAMES,
                }
            }
            Movement::Recovering { ticks } if ticks > 1 => {
                Movement::Recovering { ticks: ticks - 1 }
            }
            Movement::Recovering { .. } => Movement::Still,
        };
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
