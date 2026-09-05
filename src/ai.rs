//! Enemy behaviour.
//!
//! ProtoMan's is the one every player knows: warp to the panel facing you and
//! thrust. This is a first pass on fixed timers, not the game's own AI, which
//! has not been read yet.

use crate::actor::Actor;
use crate::field;

/// Frames between decisions. Placeholders until the real AI's pacing is known.
const MOVE_PAUSE: u16 = 40;
const ATTACK_PAUSE: u16 = 90;

pub struct Ai {
    pause: u16,
}

impl Ai {
    pub fn new() -> Self {
        Self {
            pause: ATTACK_PAUSE,
        }
    }

    /// Close on the panel facing `target` one step at a time, row first so the
    /// approach reads as lining up, then attack once there.
    pub fn update(&mut self, me: &mut Actor, target: (i32, i32)) {
        if self.pause > 0 {
            self.pause -= 1;
            return;
        }
        if me.is_busy() {
            return;
        }
        let (col, row) = me.panel();
        let want = (field::half(true).0, target.1);
        if row != want.1 {
            me.step(0, (want.1 - row).signum());
            self.pause = MOVE_PAUSE;
        } else if col != want.0 {
            me.step((want.0 - col).signum(), 0);
            self.pause = MOVE_PAUSE;
        } else {
            me.attack();
            self.pause = ATTACK_PAUSE;
        }
    }
}
