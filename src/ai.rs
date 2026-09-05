//! Enemy behaviour.
//!
//! These are first passes on fixed timers, not the game's own planners:
//! Colonel's real one (sub_81013AA, asm31.s:153037) picks among five attacks
//! by where the player stands and how both HPs are doing, and ProtoMan's has
//! not been read at all. What each attack itself does is the game's.

use crate::actor::{self, Actor};
use crate::field;

/// Frames between decisions. ProtoMan's planner ticks about every 29 frames
/// and attacks once a counter fed 1-2 per tick reaches 4, so roughly 87
/// frames on average (sub_80FBA24, asm31.s:141641); that average stands in
/// for the counter. The others are placeholders.
const MOVE_PAUSE: u16 = 29;
const ATTACK_PAUSE: u16 = 87;
const DIVIDE_PAUSE: u16 = 150;
/// The Mettaur re-arms its alignment check on a 0x1e counter (asm31.s:171029).
const METTAUR_PAUSE: u16 = 0x1e;

pub enum Style {
    /// Line up with the player, warp to the facing panel, strike the panel
    /// in front -- attack C's chooser lands exactly there (sub_80FCDBA,
    /// asm31.s:144205).
    Thrust,
    /// Stand and slash: the 0xA cross when the player is near the centre of
    /// their side, else the overhead slash on their front column.
    Divide,
    /// Driven by its own controller in `gunner`; nothing to do here.
    Gunner,
    /// Hop a row at a time toward the player's row, then swing the pickaxe
    /// and send a shockwave down the row (sub_810A004, asm31.s:171029;
    /// rule sub_810A21A, 171342). A first-version Mettaur never guards.
    Mettaur,
}

/// The 0xA slash's base panel for the enemy side is (2,2) (dword_8103A04,
/// asm31.s:158121), and one of four offset shapes is laid over it by where
/// the player stands (byte_8103990, asm31.s:158062; lists at
/// asm00_2.s:20990-21025). Which shape the game picks for which position is
/// not fully read, so the first shape covering the player is used, and the
/// last, the 3x3 block without its side centres, when none does.
pub const CROSS_BASE: (i32, i32) = (2, 2);
const CROSS_SHAPES: [&[(i32, i32)]; 4] = [
    &[(0, 0), (1, -1), (-1, 1)],
    &[(0, 0), (-1, -1), (1, 1)],
    &[(0, 0), (-1, -1), (-1, 1)],
    &[(0, 0), (-1, -1), (1, -1), (-1, 1), (1, 1), (0, -1), (0, 1)],
];

/// The panels the cross slash will hit for a player at `target`, or None if
/// the player is out of its reach and the overhead slash should be used.
pub fn cross_targets(target: (i32, i32)) -> Option<&'static [(i32, i32)]> {
    let rel = (target.0 - CROSS_BASE.0, target.1 - CROSS_BASE.1);
    CROSS_SHAPES.iter().copied().find(|s| s.contains(&rel))
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

    /// `blocked` is the occupancy of every other object, which no move may
    /// land on.
    pub fn update(&mut self, me: &mut Actor, target: (i32, i32), blocked: u32) {
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
                    me.step(0, (want.1 - row).signum(), blocked);
                    self.pause = MOVE_PAUSE;
                } else if col != want.0 {
                    me.step((want.0 - col).signum(), 0, blocked);
                    self.pause = MOVE_PAUSE;
                } else {
                    me.attack(actor::THRUST);
                    self.pause = ATTACK_PAUSE;
                }
            }
            Style::Gunner => {}
            Style::Mettaur => {
                let (_, row) = me.panel();
                if row != target.1 {
                    me.hop(0, (target.1 - row).signum(), blocked);
                } else {
                    me.attack(actor::SWING);
                }
                self.pause = METTAUR_PAUSE;
            }
            Style::Divide => {
                let spec = if cross_targets(target).is_some() {
                    actor::CROSS
                } else {
                    actor::DIVIDE
                };
                me.attack(spec);
                self.pause = DIVIDE_PAUSE;
            }
        }
    }
}
