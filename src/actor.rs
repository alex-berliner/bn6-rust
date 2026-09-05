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
use agb::display::object::{GraphicsMode, Object};

use crate::field;
use crate::spr;

/// Animation indices in the exported navi sprites. These are a convention
/// shared across navis, not particular to MegaMan: ProtoMan's 0, 3 and 4 are
/// the same poses with the same frame counts. Only a handful of animations set
/// the loop flag, so these are one-shot and re-triggered here.
pub mod anim {
    pub const IDLE: usize = 0;
    pub const FLINCH: usize = 1;
    /// The pose held while being deleted (asm00_2.s:17808, 18173).
    pub const DELETED: usize = 2;
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
/// One attack's shape: the pose to hold, for how long, and on which frame of
/// it the hit lands.
#[derive(Clone, Copy)]
pub struct AttackSpec {
    /// A pose held before the strike pose, if the attack has one.
    pub windup: Option<(usize, u8)>,
    pub anim: usize,
    pub frames: u8,
    /// 1-based frame of the pose on which the strike is delivered.
    pub strike_at: u8,
    /// Frames the actor stays busy in its standing pose afterwards.
    pub recover: u8,
}

/// The buster: animation 14 for five passes, ending once its frame counter
/// clears 4, with the shot spawned on the second (asm31.s:108536, 108547,
/// 108608).
pub const BUSTER: AttackSpec = AttackSpec {
    windup: None,
    anim: 14,
    frames: 5,
    strike_at: 2,
    recover: 0,
};
/// Colonel's overhead slash: animation 0xc held for 0x28 frames, the hit
/// spawned when the countdown reads 0x14 (asm31.s:157462, 157464-157479).
pub const DIVIDE: AttackSpec = AttackSpec {
    windup: None,
    anim: 12,
    frames: 40,
    strike_at: 20,
    recover: 0,
};
/// ProtoMan's basic strike, attack A of his AI: animation 0xf held for 16
/// frames while the front panel flashes, then animation 5 for 30 with the
/// hit when the countdown reads 0x14 -- ten frames in -- on the one panel in
/// front, then 20 frames of recovery (sub_80FC226, sub_80FC26A, sub_80FC2DC;
/// asm31.s:142671, 142716; V1 tiers dword_80FBD28, dword_80FBD14).
pub const THRUST: AttackSpec = AttackSpec {
    windup: Some((15, 16)),
    anim: 5,
    frames: 30,
    strike_at: 11,
    recover: 20,
};
/// Colonel's 0xA slash: animation 6 held for 30 frames, then animation 5
/// with the hit on its first frame, held 0x1e, then 24 frames of recovery
/// (asm31.s:157045-157102).
pub const CROSS: AttackSpec = AttackSpec {
    windup: Some((6, 30)),
    anim: 5,
    frames: 30,
    strike_at: 1,
    recover: 24,
};
/// A charged shot first holds its aim for five frames before entering the
/// same fire state (megamanChargeShotAiAttack_80EBE00, asm31.s:109703).
const AIM_FRAMES: u8 = 5;
/// The flinch timer is set to 0x17 (asm00_2.s:18309).
const FLINCH_FRAMES: u8 = 23;
/// After a hit the player flashes and cannot be hit again for 0x78 frames
/// (sub_801A66C, asm00_2.s:22319). Whether enemies get the same grace is not
/// verified, so they are constructed without it.
pub const PLAYER_MERCY_FRAMES: u8 = 120;

/// What an actor starts with and how it dies.
#[derive(Clone, Copy)]
pub struct Profile {
    pub hp: u16,
    /// Post-hit invulnerability, if any.
    pub mercy: u8,
    /// Frames from zero HP to gone. An enemy navi blinks white for 0x5a
    /// frames (sub_8017122, asm00_2.s:17808); the player holds 0x15 then
    /// fades over 0x20 by mosaic and alpha (asm00_2.s:18173-18212), 55 in
    /// all with the two one-frame phases.
    pub death_frames: u8,
}

pub const ENEMY_DEATH_FRAMES: u8 = 92;
pub const PLAYER_DEATH_FRAMES: u8 = 55;
const PLAYER_FADE_FRAMES: u8 = 0x20;
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
    /// Holding an attack's wind-up pose; `next` is the strike pose to follow.
    WindingUp {
        ticks: u8,
        next: AttackSpec,
    },
    /// Attacking; the strike lands when `ticks` counts down to `strike_tick`.
    Attacking {
        ticks: u8,
        strike_tick: u8,
        charged: bool,
        recover: u8,
    },
    /// Reeling from a hit.
    Flinching {
        ticks: u8,
    },
    /// Being deleted: the pose holds while the body flashes, then it is gone.
    Dying {
        ticks: u8,
    },
    Gone,
}

/// What [`Actor::update`] asks the caller to do this frame.
pub enum Update {
    Nothing,
    /// A frame of an attack pose before its strike, counted from 1.
    Winding { frame: u8 },
    /// HP just reached zero: the caller spawns the deletion effect here.
    Died,
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
    death_frames: u8,
    invulnerable: u8,
    flash: u8,
    /// Length of the attack pose in progress, for numbering its frames.
    pose_len: u8,
}

impl Actor {
    pub fn new(assets: spr::Assets, col: i32, row: i32, facing_left: bool, profile: Profile) -> Self {
        Self {
            player: spr::Player::new(assets, anim::IDLE),
            col,
            row,
            facing_left,
            action: Action::Idle,
            hp: profile.hp,
            mercy: profile.mercy,
            death_frames: profile.death_frames,
            invulnerable: 0,
            flash: 0,
            pose_len: 0,
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

    /// Deleted and no longer on the field.
    pub fn is_defeated(&self) -> bool {
        matches!(self.action, Action::Gone)
    }

    /// The player's deletion fade, once it has begun: the mosaic block size
    /// and a 0-16 opacity, both from the phase-3 timer `t` counting 0 to 0x20
    /// -- mosaic `t >> 1`, alpha `0x10 - t` (asm00_2.s:18212).
    pub fn fade(&self) -> Option<(u8, u8)> {
        match self.action {
            Action::Dying { ticks }
                if self.death_frames == PLAYER_DEATH_FRAMES && ticks <= PLAYER_FADE_FRAMES =>
            {
                let t = PLAYER_FADE_FRAMES - ticks;
                Some(((t >> 1).min(15), 0x10u8.saturating_sub(t)))
            }
            _ => None,
        }
    }

    /// Still something that can be hit or aimed at: not dying, not gone.
    pub fn is_targetable(&self) -> bool {
        !matches!(self.action, Action::Dying { .. } | Action::Gone)
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
        if self.hp == 0 {
            // HP zero sets the death flag and the die state takes over the
            // action slot the same frame (asm00_2.s:23769, 23782-23800).
            self.player.play(anim::DELETED);
            self.action = Action::Dying {
                ticks: self.death_frames,
            };
        } else {
            self.flinch();
        }
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

    /// Start an attack. Refused unless idle, since attacking takes the same
    /// `CurAction` slot as movement.
    pub fn attack(&mut self, spec: AttackSpec) -> bool {
        if !matches!(self.action, Action::Idle) {
            return false;
        }
        self.begin(spec, false);
        true
    }

    fn begin(&mut self, spec: AttackSpec, charged: bool) {
        if let Some((anim, frames)) = spec.windup {
            self.player.play(anim);
            self.pose_len = frames;
            self.action = Action::WindingUp {
                ticks: frames,
                next: AttackSpec {
                    windup: None,
                    ..spec
                },
            };
            return;
        }
        self.player.play(spec.anim);
        self.pose_len = spec.frames;
        self.action = Action::Attacking {
            ticks: spec.frames,
            strike_tick: spec.frames + 1 - spec.strike_at,
            charged,
            recover: spec.recover,
        };
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
            if self.flash == 0 && !matches!(self.action, Action::Dying { .. }) {
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
                self.begin(BUSTER, true);
                self.action
            }
            Action::WindingUp { ticks, next } if ticks > 1 => {
                update = Update::Winding {
                    frame: (self.pose_len - ticks) + 1,
                };
                Action::WindingUp {
                    ticks: ticks - 1,
                    next,
                }
            }
            Action::WindingUp { next, .. } => {
                self.begin(next, false);
                self.action
            }
            Action::Attacking {
                ticks,
                strike_tick,
                charged,
                recover,
            } if ticks > 1 => {
                if ticks == strike_tick {
                    update = Update::Strike { charged };
                } else if ticks > strike_tick {
                    // `ticks` counts down from the pose length; the frame just
                    // played is the first once the counter has moved once.
                    update = Update::Winding {
                        frame: (self.pose_len - ticks) + 1,
                    };
                }
                Action::Attacking {
                    ticks: ticks - 1,
                    strike_tick,
                    charged,
                    recover,
                }
            }
            Action::Attacking { recover, .. } => {
                self.player.play(anim::IDLE);
                if recover > 0 {
                    Action::Recovering { ticks: recover }
                } else {
                    Action::Idle
                }
            }
            Action::Flinching { ticks } if ticks > 1 => Action::Flinching { ticks: ticks - 1 },
            Action::Flinching { .. } => {
                self.player.play(anim::IDLE);
                Action::Idle
            }
            Action::Dying { ticks } if ticks == self.death_frames => {
                update = Update::Died;
                Action::Dying { ticks: ticks - 1 }
            }
            Action::Dying { ticks } if ticks > 1 => {
                // The enemy die state forces the white palette on every
                // carry of timer >> 2, two frames in four (asm00_2.s:17808);
                // the player's forces it every frame (asm00_2.s:18212).
                let white = self.death_frames == PLAYER_DEATH_FRAMES || (ticks >> 2) & 1 == 0;
                self.player.set_white(white);
                Action::Dying { ticks: ticks - 1 }
            }
            Action::Dying { .. } => Action::Gone,
            Action::Gone => Action::Gone,
        };
        update
    }

    pub fn show(&self, frame: &mut GraphicsFrame) {
        // While invulnerable the object carries OBJECT_FLAGS_FLASHING
        // (asm00_2.s:23893) and blinks; the game's exact cadence was not
        // traced, so this alternates two frames on, two off, and holds off
        // until the white flash has had its frames on screen.
        if matches!(self.action, Action::Gone) {
            return;
        }
        // The mercy blink stops mattering once the navi is being deleted; the
        // die state's own white/visibility handling takes over.
        let dying = matches!(self.action, Action::Dying { .. });
        if !dying && self.flash == 0 && self.invulnerable > 0 && (self.invulnerable / 2) % 2 == 1 {
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
            let mut object = Object::new(part.sprite.clone());
            object
                .set_pos((px + x, py + part.y))
                .set_hflip(part.hflip ^ self.facing_left)
                .set_vflip(part.vflip);
            if self.fade().is_some() {
                object
                    .set_mosaic(true)
                    .set_graphics_mode(GraphicsMode::AlphaBlending);
            }
            object.show(frame);
        }
    }
}
