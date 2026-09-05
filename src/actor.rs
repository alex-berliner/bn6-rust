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
    /// The navi's attack pose: MegaMan's buster fire (asm31.s:108536 sets
    /// animation 0xe) and ProtoMan's sword thrust are both index 14. Colonel's
    /// is not, so he gets no attack yet.
    pub const ATTACK: usize = 14;
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
/// The buster's firing state runs five passes, ending once its frame counter
/// clears 4 (asm31.s:108608). The sword reuses it; its own timing is not yet
/// taken from the disassembly.
const ATTACK_FRAMES: u8 = 5;
/// A charged shot first holds its aim for five frames before entering the
/// same fire state (megamanChargeShotAiAttack_80EBE00, asm31.s:109703).
const AIM_FRAMES: u8 = 5;
/// The flinch timer is set to 0x17 (asm00_2.s:18309).
const FLINCH_FRAMES: u8 = 23;
/// After a hit the player flashes and cannot be hit again for 0x78 frames
/// (sub_801A66C, asm00_2.s:22319). Whether enemies get the same grace is not
/// verified, so they are constructed without it.
pub const PLAYER_MERCY_FRAMES: u8 = 120;
/// A hit forces the sprite white (sprite_forceWhitePalette, asm/sprite.s:1141)
/// and the OAM builder keeps it so until the palette is reassigned
/// (asm38.s:30060BE). Where that happens was not traced, so this length is a
/// stand-in chosen to look right.
const FLASH_FRAMES: u8 = 4;

/// What the actor is doing. bn6f keeps one `CurAction` and movement and attack
/// are mutually exclusive, so all of these are states of one slot.
#[derive(Clone, Copy)]
enum Action {
    Idle,
    /// Dissolving away; `to` is committed as the current panel when this ends.
    Leaving {
        to: (i32, i32),
        ticks: u8,
    },
    /// Materialising on the panel just arrived at.
    Arriving {
        ticks: u8,
    },
    /// Standing again but still locked out of another move.
    Recovering {
        ticks: u8,
    },
    /// Winding up a charged shot; the pose does not change.
    Aiming {
        ticks: u8,
    },
    /// Attacking; the strike lands on the second frame.
    Attacking {
        ticks: u8,
        charged: bool,
    },
    /// Reeling from a hit.
    Flinching {
        ticks: u8,
    },
}

/// What [`Actor::update`] asks the caller to do this frame.
pub enum Update {
    Nothing,
    /// The second frame of `Attacking`: the caller resolves what the attack
    /// does -- spawn a shot, or hit the panel in front.
    Strike { charged: bool },
}

pub struct Actor {
    player: spr::Player,
    col: i32,
    row: i32,
    /// Enemies face left, which mirrors the composed frame.
    facing_left: bool,
    action: Action,
    hp: u16,
    /// Frames of post-hit invulnerability this actor gets, and how many remain.
    mercy: u8,
    invulnerable: u8,
    flash: u8,
}

impl Actor {
    pub fn new(
        assets: spr::Assets,
        col: i32,
        row: i32,
        facing_left: bool,
        hp: u16,
        mercy: u8,
    ) -> Self {
        Self {
            player: spr::Player::new(assets, anim::IDLE),
            col,
            row,
            facing_left,
            action: Action::Idle,
            hp,
            mercy,
            invulnerable: 0,
            flash: 0,
        }
    }

    /// +1 for a navi facing right, -1 facing left.
    pub fn facing_dx(&self) -> i32 {
        if self.facing_left { -1 } else { 1 }
    }

    /// The panel directly ahead, where a shot spawns or a sword lands.
    pub fn front_panel(&self) -> (i32, i32) {
        (self.col + self.facing_dx(), self.row)
    }

    pub fn hp(&self) -> u16 {
        self.hp
    }

    /// At zero HP bn6f sets the object's death flag and stops running it
    /// (asm00_2.s:23769); here the caller simply drops the actor.
    pub fn is_defeated(&self) -> bool {
        self.hp == 0
    }

    /// Take a hit. bn6f subtracts the damage and enters the flinch state as
    /// separate steps (object_subtractHP at asm00_2.s:23756, flinch at
    /// asm00_2.s:18294), so a killing blow still plays the flinch.
    ///
    /// Returns false when the hit was ignored for landing inside the mercy
    /// window of a previous one.
    pub fn take_damage(&mut self, amount: u16) -> bool {
        if self.invulnerable > 0 {
            return false;
        }
        self.hp = self.hp.saturating_sub(amount);
        self.invulnerable = self.mercy;
        self.flash = FLASH_FRAMES;
        self.player.set_white(true);
        self.flinch();
        true
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
    pub fn is_busy(&self) -> bool {
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

    /// Start an attack: animation 14 held for five frames, with the strike on
    /// the second (asm31.s:108536, 108547, 108608). Refused unless idle, since
    /// attacking takes the same `CurAction` slot as movement.
    pub fn attack(&mut self) -> bool {
        if !matches!(self.action, Action::Idle) {
            return false;
        }
        self.player.play(anim::ATTACK);
        self.action = Action::Attacking {
            ticks: ATTACK_FRAMES,
            charged: false,
        };
        true
    }

    /// Release a full charge: aim for five frames, then fire as normal with
    /// the strike flagged charged so the caller scales the damage.
    pub fn attack_charged(&mut self) -> bool {
        if !matches!(self.action, Action::Idle) {
            return false;
        }
        self.action = Action::Aiming { ticks: AIM_FRAMES };
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
        self.invulnerable = self.invulnerable.saturating_sub(1);
        if self.flash > 0 {
            self.flash -= 1;
            if self.flash == 0 {
                self.player.set_white(false);
            }
        }
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
            Action::Recovering { ticks } if ticks > 1 => Action::Recovering { ticks: ticks - 1 },
            Action::Recovering { .. } => Action::Idle,
            Action::Aiming { ticks } if ticks > 1 => Action::Aiming { ticks: ticks - 1 },
            Action::Aiming { .. } => {
                self.player.play(anim::ATTACK);
                Action::Attacking {
                    ticks: ATTACK_FRAMES,
                    charged: true,
                }
            }
            Action::Attacking { ticks, charged } if ticks > 1 => {
                // bn6f spawns the shot when its firing counter equals 1, i.e.
                // on the second of the five passes (asm31.s:108547 'cmp r0, #1').
                if ticks == ATTACK_FRAMES - 1 {
                    update = Update::Strike { charged };
                }
                Action::Attacking {
                    ticks: ticks - 1,
                    charged,
                }
            }
            Action::Attacking { .. } => {
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
        // While invulnerable the object carries OBJECT_FLAGS_FLASHING
        // (asm00_2.s:23893) and blinks; the game's exact cadence was not
        // traced, so this alternates two frames on, two off, and holds off
        // until the white flash has had its frames on screen.
        if self.flash == 0 && self.invulnerable > 0 && (self.invulnerable / 2) % 2 == 1 {
            return;
        }
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
