//! A character standing on the battle field, and how it moves between panels.
//!
//! Movement is a warp, not a slide. `BattleObject` keeps the panel it is on at
//! 0x12/0x13 and the panel it is heading to at 0x14/0x15
//! (include/structs/BattleObject.inc:63), so a move is a transition with a
//! target rather than an instant write. The sprite backs that up: animations 4
//! and 3 are a matched pair that dissolves the navi out and materialises it
//! back in, so the panel is committed at the midpoint, hidden by the dissolve.
//!
//! bn6f keeps one `CurAction`, so movement, attacking and flinching are states
//! of a single machine rather than layers that can overlap.

use agb::display::GraphicsFrame;
use agb::display::object::Object;

use crate::field;
use crate::spr;

/// Animation indices in the exported navi sprites. These are a convention
/// shared across navis, not particular to MegaMan: ProtoMan's 0, 3 and 4 are
/// the same poses with the same frame counts. Only a handful of animations set
/// the loop flag, so these are one-shot and re-triggered here.
pub mod anim {
    pub const IDLE: usize = 0;
    pub const FLINCH: usize = 1;
    pub const WARP_IN: usize = 3;
    pub const WARP_OUT: usize = 4;
    /// The buster fire pose (asm31.s:108536 sets animation 0xe).
    pub const FIRE: usize = 14;
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
/// The firing state runs five passes, ending once its frame counter clears 4
/// (asm31.s:108608).
const FIRING_FRAMES: u8 = 5;
/// The flinch timer is set to 0x17 (asm00_2.s:18309).
const FLINCH_FRAMES: u8 = 23;

/// What the actor is doing. bn6f keeps one `CurAction` and movement and attack
/// are mutually exclusive, so all of these are states of one slot.
#[derive(Clone, Copy)]
enum Action {
    Idle,
    /// Dissolving away; `to` is committed as the current panel when this ends.
    Leaving { to: (i32, i32), ticks: u8 },
    /// Materialising on the panel just arrived at.
    Arriving { ticks: u8 },
    /// Standing again but still locked out of another move.
    Recovering { ticks: u8 },
    /// Firing the buster; the shot spawns on the second frame.
    Firing { ticks: u8 },
    /// Reeling from a hit.
    Flinching { ticks: u8 },
}

/// What [`Actor::update`] asks the caller to do this frame.
pub enum Update {
    Nothing,
    /// The second frame of `Firing`: spawn the buster shot in front.
    SpawnShot,
}

pub struct Actor {
    player: spr::Player,
    col: i32,
    row: i32,
    /// Enemies face left, which mirrors the composed frame.
    facing_left: bool,
    action: Action,
}

impl Actor {
    pub fn new(assets: spr::Assets, col: i32, row: i32, facing_left: bool) -> Self {
        Self {
            player: spr::Player::new(assets, anim::IDLE),
            col,
            row,
            facing_left,
            action: Action::Idle,
        }
    }

    /// The panel the actor currently stands on, 1-based. During a warp this is
    /// the panel being left until the move commits at the midpoint.
    pub fn panel(&self) -> (i32, i32) {
        (self.col, self.row)
    }

    /// Panels this actor holds: the one it stands on, plus the one it has
    /// reserved while warping. `object_reservePanel` sets the reserve as the
    /// move begins and clears it at the commit (asm/asm00_2.s:24949), which
    /// keeps the destination from breaking underneath the arrival.
    pub fn occupancy(&self) -> u32 {
        let mut mask = field::panel_bit(self.col, self.row);
        if let Action::Leaving { to, .. } = self.action {
            mask |= field::panel_bit(to.0, to.1);
        }
        mask
    }

    /// Anything but idle holds the one `CurAction` slot, so a warp, a shot and
    /// a flinch all refuse to start over each other.
    fn is_busy(&self) -> bool {
        !matches!(self.action, Action::Idle)
    }

    /// Start warping by one panel. Refused while the action slot is taken or
    /// when the step would leave this actor's half of the field.
    pub fn step(&mut self, dx: i32, dy: i32) -> bool {
        if self.is_busy() {
            return false;
        }
        let (to_col, to_row) = (self.col + dx, self.row + dy);
        let (min_col, max_col) = field::half(self.facing_left);
        if !(min_col..=max_col).contains(&to_col) || !(1..=field::ROWS).contains(&to_row) {
            return false;
        }
        self.action = Action::Leaving {
            to: (to_col, to_row),
            ticks: LEAVING_FRAMES,
        };
        self.player.play(anim::WARP_OUT);
        true
    }

    /// Start firing the buster: animation 14 held for five frames, with the
    /// shot spawned on the second (asm31.s:108536, 108547, 108608). Refused
    /// unless idle, since firing takes the same `CurAction` slot as movement.
    pub fn fire(&mut self) -> bool {
        if !matches!(self.action, Action::Idle) {
            return false;
        }
        self.player.play(anim::FIRE);
        self.action = Action::Firing {
            ticks: FIRING_FRAMES,
        };
        true
    }

    /// Flinch from a hit: animation 1 for 0x17 frames (asm00_2.s:18294,
    /// 18309). Interrupts anything, a warp included -- its reserved panel is
    /// released with the Leaving state.
    pub fn flinch(&mut self) {
        self.player.play(anim::FLINCH);
        self.action = Action::Flinching {
            ticks: FLINCH_FRAMES,
        };
    }

    pub fn update(&mut self) -> Update {
        self.player.update();
        let mut update = Update::Nothing;
        self.action = match self.action {
            Action::Idle => Action::Idle,
            Action::Leaving { to, ticks } if ticks > 1 => Action::Leaving {
                to,
                ticks: ticks - 1,
            },
            Action::Leaving { to, .. } => {
                (self.col, self.row) = to;
                self.player.play(anim::WARP_IN);
                Action::Arriving {
                    ticks: ARRIVING_FRAMES,
                }
            }
            Action::Arriving { ticks } if ticks > 1 => Action::Arriving { ticks: ticks - 1 },
            Action::Arriving { .. } => {
                self.player.play(anim::IDLE);
                Action::Recovering {
                    ticks: RECOVERING_FRAMES,
                }
            }
            Action::Recovering { ticks } if ticks > 1 => {
                Action::Recovering { ticks: ticks - 1 }
            }
            Action::Recovering { .. } => Action::Idle,
            Action::Firing { ticks } if ticks > 1 => {
                // bn6f spawns the shot when its firing counter equals 1, i.e.
                // on the second of the five passes (asm31.s:108547 'cmp r0, #1').
                if ticks == FIRING_FRAMES - 1 {
                    update = Update::SpawnShot;
                }
                Action::Firing { ticks: ticks - 1 }
            }
            Action::Firing { .. } => {
                self.player.play(anim::IDLE);
                Action::Idle
            }
            Action::Flinching { ticks } if ticks > 1 => Action::Flinching { ticks: ticks - 1 },
            Action::Flinching { .. } => {
                self.player.play(anim::IDLE);
                Action::Idle
            }
        };
        update
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
