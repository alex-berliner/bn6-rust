//! Enemy behaviour.
//!
//! These are first passes on fixed timers, not the game's own planners:
//! Colonel's real one (sub_81013AA, asm31.s:153037) picks among five attacks
//! by where the player stands and how both HPs are doing, and ProtoMan's has
//! not been read at all. What each attack itself does is the game's.

use crate::actor::{self, Actor};
use crate::field;

/// Frames between decisions. Placeholders until the real pacing is known.
const MOVE_PAUSE: u16 = 40;
const ATTACK_PAUSE: u16 = 90;
const DIVIDE_PAUSE: u16 = 150;

pub enum Style {
    /// Line up with the player, warp to the facing panel, thrust.
    Thrust,
    /// Stand and bring the sword down on the player's front column.
    Divide,
}

pub struct Ai {
    style: Style,
    pause: u16,
}

impl Ai {
    pub fn new(style: Style) -> Self {
        Self {
            style,
            pause: ATTACK_PAUSE,
        }
    }

    pub fn style(&self) -> &Style {
        &self.style
    }

    pub fn update(&mut self, me: &mut Actor, target: (i32, i32)) {
        if self.pause > 0 {
            self.pause -= 1;
            return;
        }
        if me.is_busy() {
            return;
        }
        match self.style {
            Style::Thrust => {
                // Row first, so the approach reads as lining up.
                let (col, row) = me.panel();
                let want = (field::half(true).0, target.1);
                if row != want.1 {
                    me.step(0, (want.1 - row).signum());
                    self.pause = MOVE_PAUSE;
                } else if col != want.0 {
                    me.step((want.0 - col).signum(), 0);
                    self.pause = MOVE_PAUSE;
                } else {
                    me.attack(actor::BUSTER);
                    self.pause = ATTACK_PAUSE;
                }
            }
            Style::Divide => {
                me.attack(actor::DIVIDE);
                self.pause = DIVIDE_PAUSE;
            }
        }
    }
}
