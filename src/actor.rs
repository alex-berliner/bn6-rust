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
use agb::display::Priority;
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
    /// The Mettaur's hop between rows, its own index 2 (asm31.s:170580).
    pub const HOP: usize = 2;
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
const LEAVING_FRAMES: u8 = 4; // provenance: derived -- sub_80EB088..sub_80EB1C4, asm31.s:108036 onwards
const ARRIVING_FRAMES: u8 = 5; // provenance: derived -- sub_80EB088..sub_80EB1C4, asm31.s:108036 onwards
const RECOVERING_FRAMES: u8 = 4; // provenance: derived -- sub_8010332, asm00_2.s:3121 (per-navi default)
/// The washed-out palette the commit frame is drawn in, and how long it
/// lasts: one frame.
const WARP_PALETTE: usize = 1; // provenance: peeked -- measured against the real ROM
const WARP_PALE_FRAMES: u8 = 1; // provenance: peeked -- measured against the real ROM
/// Frames between the press and the warp starting.
const WARP_DELAY: u8 = 1; // provenance: peeked -- measured against the real ROM
/// A Mettaur's hop is three frames up and three down, landing in its idle
/// pose, then a per-version cooldown of 0x1e frames in the first
/// (sub_8109CE6, asm31.s:170580, 170689; byte_8109F46).
const HOP_FRAMES: u8 = 6; // provenance: derived -- sub_8109CE6, asm31.s:170580
const HOP_COOLDOWN: u8 = 0x1e; // provenance: derived -- byte_8109F46, asm31.s:170689
/// The buster does nothing for two frames after the button is LET GO:
/// measured against a capture whose navi is pixel-identical to its idle
/// through frame 64, with B pressed on 60 and released on 62, and changes on
/// 65.
const BUSTER_WINDUP: u8 = 2; // provenance: peeked -- measured against the real ROM
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
    /// Frames the actor stays busy afterwards.
    pub recover: u8,
    /// The animation played through those frames; `None` keeps the attack
    /// pose's last frame (the real ROM holds the sword's final frame
    /// through its five recovery frames).
    pub recover_anim: Option<usize>,
}

/// The buster: animation 14. The disassembly's "five passes" are passes of
/// the ANIMATION, not game frames -- measured against the real ROM, the pose
/// is held 21 frames and the shot leaves the gun on the eighth, which is
/// where the capture's Mettaur loses its first HP (asm31.s:108536, 108547,
/// 108608).
// provenance: peeked -- measured against the real ROM (asm31.s:108536/108547/108608 cross-checked).
pub const BUSTER: AttackSpec = AttackSpec {
    windup: Some((anim::IDLE, BUSTER_WINDUP)),
    anim: 14,
    frames: 17,
    strike_at: 3,
    recover: 0,
    recover_anim: None,
};
/// Colonel's overhead slash: animation 0xc held for 0x28 frames, the hit
/// spawned when the countdown reads 0x14 (asm31.s:157462, 157464-157479).
// provenance: derived -- asm31.s:157462, 157464-157479.
pub const DIVIDE: AttackSpec = AttackSpec {
    windup: None,
    anim: 12,
    frames: 40,
    strike_at: 20,
    recover: 0,
    recover_anim: None,
};
/// ProtoMan's basic strike, attack A of his AI: animation 0xf held for 16
/// frames while the front panel flashes, then animation 5 for 30 with the
/// hit when the countdown reads 0x14 -- ten frames in -- on the one panel in
/// front, then 20 frames of recovery (sub_80FC226, sub_80FC26A, sub_80FC2DC;
/// asm31.s:142671, 142716; V1 tiers dword_80FBD28, dword_80FBD14).
// provenance: derived -- sub_80FC226/sub_80FC26A/sub_80FC2DC, asm31.s:142671/142716.
pub const THRUST: AttackSpec = AttackSpec {
    windup: Some((15, 16)),
    anim: 5,
    frames: 30,
    strike_at: 11,
    recover: 20,
    recover_anim: Some(anim::IDLE),
};
/// The Mettaur's pickaxe: animation 1 while a 0x40-frame counter runs down,
/// the shockwave spawned at the front panel when it reads 0x1b
/// (sub_8109DEC, asm31.s:170792-170840; sub_80C6CE4, asm31.s:31563), then a
/// SEPARATE 0x28 (40) frame recovery (sub_8109E4A, asm31.s:170843-170867)
/// before the decision machine (sub_8109FD6) is allowed to run again -- the
/// previous cut of this attack had `recover: 0`, which let bn's Mettaur
/// re-attack as soon as the 0x40-frame pose ended, roughly DOUBLE the real
/// cadence (64 frames observed vs. the real 64+40=104) and the dominant
/// driver of the `mettaur`/`wave` residues (AUDIT wave 3d ticket).
// provenance: derived -- sub_8109DEC/sub_8109E4A, asm31.s:170792-170867; sub_80C6CE4, asm31.s:31563.
pub const SWING: AttackSpec = AttackSpec {
    windup: None,
    anim: 1,
    frames: 0x40,
    strike_at: 0x40 - 0x1b + 1,
    recover: 0x28,
    recover_anim: Some(anim::IDLE),
};
/// Colonel's 0xA slash: animation 6 held for 30 frames, then animation 5
/// with the hit on its first frame, held 0x1e, then 24 frames of recovery
/// (asm31.s:157045-157102).
// provenance: derived -- asm31.s:157045-157102.
pub const CROSS: AttackSpec = AttackSpec {
    windup: Some((6, 30)),
    anim: 5,
    frames: 30,
    strike_at: 1,
    recover: 24,
    recover_anim: Some(anim::IDLE),
};
/// A charged shot first holds its aim for five frames before entering the
/// same fire state (megamanChargeShotAiAttack_80EBE00, asm31.s:109703).
const AIM_FRAMES: u8 = 5; // provenance: derived -- megamanChargeShotAiAttack_80EBE00, asm31.s:109703
/// The flinch timer is set to 0x17 (asm00_2.s:18309).
const FLINCH_FRAMES: u8 = 23; // provenance: derived -- asm00_2.s:18309
/// After a hit the player flashes and cannot be hit again for 0x78 frames;
/// the flash timer is seeded to 0x78 in the post-hit invulnerability handler
/// (sub_801A5EE, asm00_2.s:22261) and counts down each frame, holding the
/// OBJECT_FLAGS_FLASHING invisibility until it reaches zero (asm00_2.s:23893).
/// Whether enemies get the same grace is not verified, so they are
/// constructed without it.
pub const PLAYER_MERCY_FRAMES: u8 = 120; // provenance: derived -- sub_801A5EE, asm00_2.s:22261

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

pub const ENEMY_DEATH_FRAMES: u8 = 92; // provenance: derived -- sub_8017122, asm00_2.s:17808
pub const PLAYER_DEATH_FRAMES: u8 = 55; // provenance: derived -- asm00_2.s:18173-18212
const PLAYER_FADE_FRAMES: u8 = 0x20; // provenance: derived -- asm00_2.s:18173-18212
/// An enemy navi fades in over sixteen steps taken every other frame
/// (sub_801641A, asm00_2.s:16099-16137). How each step maps to the mosaic
/// and alpha values was not read; they are stepped linearly here.
const APPEAR_STEPS: u8 = 0x10; // provenance: derived -- sub_801641A, asm00_2.s:16099-16137
const APPEAR_FRAMES: u8 = APPEAR_STEPS * 2; // provenance: derived -- sub_801641A, asm00_2.s:16099-16137
/// A hit forces the sprite white (sprite_forceWhitePalette, asm/sprite.s:1141)
/// and the OAM builder keeps it so until the palette is reassigned
/// (asm38.s:30060BE). Where that happens was not traced, so this length is a
/// stand-in chosen to look right.
const FLASH_FRAMES: u8 = 4; // provenance: fitted -- "a stand-in chosen to look right", not traced

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
    /// Jumping to `to`, committed at the top of the hop.
    Hopping {
        to: (i32, i32),
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
        recover_anim: Option<usize>,
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
    /// Holding a pose for as long as its controller says; the Gunner aims,
    /// fires and recovers on its own timers rather than the attack machine.
    Holding,
    /// Not on the field yet: the intro brings enemies in one at a time.
    Hidden,
    /// Materialising through mosaic and alpha at the start of the battle.
    Appearing {
        ticks: u8,
    },
}

/// What [`Actor::update`] asks the caller to do this frame.
pub enum Update {
    /// A lead-in has ended and the pose begun this frame.
    PoseBegun,
    /// The attack pose has ended and the recovery begun this frame.
    Recovering,
    Nothing,
    /// A frame of an attack pose before its strike, counted from 1.
    Winding {
        frame: u8,
    },
    /// HP just reached zero: the caller spawns the deletion effect here.
    Died,
    /// The second frame of `Attacking`: the caller resolves what the attack
    /// does -- spawn a shot, or hit the panel in front.
    Strike {
        charged: bool,
    },
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
    max_hp: u16,
    invulnerable: u8,
    flash: u8,
    /// Frames left of the warp's pale palette.
    pale: u8,
    /// Frames left of Invisibl: OBJECT_FLAGS_INVIS with FlashingInvisTimer
    /// (sub_8010474, asm00_2.s:3288), during which nothing lands.
    invisible: u16,
    /// A Barrier chip's remaining HP (sub_801A7CC, asm00_2.s:22529): hits
    /// are taken off it, and it breaks at zero (sub_801A802, :22566).
    barrier: u16,
    /// Hits that landed, counted for the busting level: the game bumps its
    /// per-alliance counter 3 on each entry into the flinch state
    /// (asm00_2.s:18308 and its siblings).
    hits_taken: u8,
    /// Length of the attack pose in progress, for numbering its frames.
    pose_len: u8,
    /// State-oracle shadow counters (TODO R6). Written only so the export
    /// block (`oracle_fields`) can name what canon's own +0x20 word reads;
    /// no branch below ever reads them, so they cannot change behaviour.
    /// `post_flinch`: 11 counting down once a flinch has exited -- canon's
    /// MegaMan object reads +0x20 = 0xffff on the first idle frame after a
    /// flinch and then 9..0 over the next ten (PAUSED+Start@10 watch
    /// capture, TODO R6 probe), which no behaviour field tracks.
    post_flinch: u8,
    /// True while a Recovering entered from a Hopping runs: canon keeps the
    /// enemy in CurAction 0x0a (the hop executor, whose own cooldown
    /// `byte_8109F46` the recovery models) through it, while a recovery
    /// entered from an attack stays in 0x0b. Not distinguishable from the
    /// Action alone because both are `Action::Recovering`.
    hop_recovery: bool,
}

/// One actor's state-oracle export, already converted to canon's units and
/// encodings (see `oracle_fields` for every conversion and its source).
pub struct OracleFields {
    /// canon's u16 at BattleObject+0x8: CurState | CurAction << 8
    /// (include/structs/BattleObject.inc:40-52; idle reads 0x0804).
    pub cur_state_action: u16,
    /// canon's CurAnim byte at BattleObject+0x10 (BattleObject.inc:62-66).
    pub anim: u8,
    /// canon's PanelX/PanelY bytes at BattleObject+0x12/0x13
    /// (BattleObject.inc:68-72).
    pub panel_x: u8,
    pub panel_y: u8,
    /// canon's Timer u16 at BattleObject+0x20 (BattleObject.inc:95-99).
    pub timer: u16,
    /// canon's HP u16 at BattleObject+0x24 (BattleObject.inc:101).
    pub hp: u16,
}

impl Actor {
    pub fn new(
        assets: spr::Assets,
        col: i32,
        row: i32,
        facing_left: bool,
        profile: Profile,
    ) -> Self {
        Self {
            player: spr::Player::new(assets, anim::IDLE),
            col,
            row,
            facing_left,
            action: Action::Idle,
            hp: profile.hp,
            max_hp: profile.hp,
            mercy: profile.mercy,
            death_frames: profile.death_frames,
            invulnerable: 0,
            flash: 0,
            pale: 0,
            invisible: 0,
            barrier: 0,
            hits_taken: 0,
            pose_len: 0,
            post_flinch: 0,
            hop_recovery: false,
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
    ///
    /// Also covers the intro's fade-in, run backwards.
    pub fn fade(&self) -> Option<(u8, u8)> {
        match self.action {
            Action::Dying { ticks }
                if self.death_frames == PLAYER_DEATH_FRAMES && ticks <= PLAYER_FADE_FRAMES =>
            {
                let t = PLAYER_FADE_FRAMES - ticks;
                Some(((t >> 1).min(15), 0x10u8.saturating_sub(t)))
            }
            Action::Appearing { ticks } => {
                let step = (APPEAR_FRAMES - ticks) / 2;
                Some((APPEAR_STEPS - 1 - step, step + 1))
            }
            _ => None,
        }
    }

    /// Still something that can be hit or aimed at: on the field, not dying,
    /// not invisible.
    pub fn is_targetable(&self) -> bool {
        self.invisible == 0
            && !matches!(
                self.action,
                Action::Dying { .. } | Action::Gone | Action::Hidden | Action::Appearing { .. }
            )
    }

    /// Recov: object_addHP (sub_800E2FC, object.s:4684), capped at the
    /// starting HP.
    pub fn heal(&mut self, amount: u16) {
        self.hp = (self.hp + amount).min(self.max_hp);
    }

    pub fn set_invisible(&mut self, frames: u16) {
        self.invisible = frames;
    }

    pub fn set_barrier(&mut self, hp: u16) {
        self.barrier = hp;
    }

    pub fn barrier(&self) -> u16 {
        self.barrier
    }

    /// On the field in some form, so drawn and given an HP number.
    pub fn is_present(&self) -> bool {
        !matches!(self.action, Action::Hidden | Action::Gone)
    }

    /// The actor's current animation and frame within it, for rebuilding that
    /// frame later as an afterimage.
    pub fn sprite_key(&self) -> (usize, usize) {
        self.player.frame_key()
    }

    /// Put the navi on a panel at once, as the sword family's step does
    /// (asm31.s:108808-108826: it reserves the panel and sets PanelX/PanelY
    /// rather than running the warp machine).
    pub fn warp_to(&mut self, col: i32, row: i32) {
        self.col = col;
        self.row = row;
    }

    /// Take the navi off the field until the intro brings it in.
    pub fn hide(&mut self) {
        self.action = Action::Hidden;
    }

    /// Start materialising; the navi is idle once the fade is done.
    pub fn appear(&mut self) {
        self.action = Action::Appearing {
            ticks: APPEAR_FRAMES,
        };
    }

    /// Take a hit. bn6f subtracts the damage and enters the flinch state as
    /// separate steps (object_subtractHP at asm00_2.s:23756, flinch at
    /// asm00_2.s:18294), so a killing blow still plays the flinch.
    ///
    /// Returns false when the hit was ignored for landing inside the mercy
    /// window of a previous one.
    pub fn take_damage(&mut self, amount: u16) -> bool {
        if self.invulnerable > 0 || self.invisible > 0 {
            return false;
        }
        if self.barrier > 0 {
            self.barrier = self.barrier.saturating_sub(amount);
            return false;
        }
        self.hp = self.hp.saturating_sub(amount);
        self.hits_taken = self.hits_taken.saturating_add(1);
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

    pub fn hits_taken(&self) -> u8 {
        self.hits_taken
    }

    /// The state-oracle export (TODO R6): this actor's fields converted to
    /// canon's own BattleObject units and encodings, so tools/oracle.py can
    /// compare them byte for byte with a `--watch` of canon's object.
    /// `is_player` picks the player- vs virus-side CurAction map: canon
    /// dispatches them through different jumptables (player
    /// PlayerObjectAIAttackJumptables, asm31.s:107190-107200; virus
    /// ForMettaur_8109EF4, asm31.s:170979-170999), so the same Action
    /// encodes differently. Every conversion's source:
    ///
    /// - CurState byte: canon reads 0x04 (CUR_STATE_UPDATE) on every alive
    ///   object through the PAUSED+Start@10 watch window (TODO R6 probe:
    ///   MegaMan 0x0203a9b0+8 and the Mettaur 0x0203ab60+8, 180 frames).
    /// - CurAction, player: idle 0x08 (measured; traced live asm00_1.s:13117
    ///   and asm31.s:169283), flinch 0x03 (sub_80174FE,
    ///   PlayerObjectAIAttackJumptables[3], asm31.s:107195; measured
    ///   0x0203a9b9 = 0x03 through a shockwave hit), delete 0x02
    ///   (sub_80173F4, [2]). Everything else our model does while the
    ///   player object is under its own AI reads 0x08 in canon (movement
    ///   and aiming live inside playerAI_update_80EA734 [8], not new
    ///   actions) -- so that is what the remaining arms export.
    /// - CurAction, enemy (Mettaur): 0x0a hop executor, 0x0b attack
    ///   executor (swing AND its 0x28 recovery -- canon stays 0x0b across
    ///   both, measured), 0x09 the plain "wait N frames" state
    ///   (`ai::Ai::oracle_is_wait`), 0x00 spawn animation
    ///   (RunSpawnAnimationMaybe_8016380), 0x03 flinch, 0x02 delete, 0x08
    ///   decision loop -- all ForMettaur_8109EF4 entries, asm31.s:170979.
    /// - Timer (+0x20), player: the flinch countdown 0x16..0x00, measured
    ///   (canon 0x0203a9d0 reads 0x16..0 through a 23-frame flinch); our
    ///   `ticks` runs 23..1, so -1. The exit frame's 0xffff and the 9..0
    ///   tail after it are the `post_flinch` shadow (measured 137..147 of
    ///   the same capture; no behaviour field tracks them). fitted -- the
    ///   tail's length 10 and the 0xffff sentinel are read off the capture,
    ///   not derived from a cited instruction.
    /// - Timer, enemy: canon reads a CONSTANT 0x0002 here for the whole
    ///   window (measured); the swing countdown lives outside +0x00..0x2f
    ///   (only +0x9/+0x10/+0x11 change in that range), so there is nothing
    ///   dynamic to model and the export returns 0 -- oracle.py keeps this
    ///   field out of the compared set.
    /// - CurAnim (+0x10): identity -- our `anim` indices ARE the sprites'
    ///   own animation-table indices (actor.rs `pub mod anim`'s doc), which
    ///   is what canon's CurAnim byte indexes (measured 0/1 on both objects
    ///   in the same capture).
    pub fn oracle_fields(&self, is_player: bool, ai_wait: bool) -> OracleFields {
        let cur_action: u8 = match &self.action {
            Action::Flinching { .. } => 0x03,
            Action::Dying { .. } | Action::Gone => 0x02,
            Action::Attacking { .. } => 0x0b,
            // canon keeps the hop executor's own 0x0a through the hop's
            // cooldown recovery (measured: 0x0a for HOP_FRAMES +
            // HOP_COOLDOWN frames, asm31.s:170689) -- but only for the
            // enemy side, whose hops it is.
            Action::Recovering { .. } if !is_player => {
                if self.hop_recovery {
                    0x0a
                } else {
                    0x0b
                }
            }
            Action::Hopping { .. } if !is_player => 0x0a,
            Action::Hidden | Action::Appearing { .. } => 0x00,
            _ if !is_player && ai_wait => 0x09,
            _ => 0x08,
        };
        // The enemy's +0x20 reads a constant 0x0002 through the whole
        // measured window (see the doc above): nothing dynamic to model, so
        // the enemy export always returns 0 and oracle.py keeps this field
        // out of the compared set.
        let timer: u16 = if !is_player {
            0
        } else {
            match &self.action {
                // canon's own flinch handler writes Timer=0x17 on entry and
                // decrements it in the SAME frame (asm00_2.s:18310-18316),
                // so +0x20 reads 0x16=22 on the hit frame -- which is exactly
                // our post-decrement `ticks` (FLINCH_FRAMES=0x17, ticked by
                // this frame's update, F1). No offset either way.
                Action::Flinching { ticks } => (*ticks as u16),
                _
                    if self.post_flinch > 0
                        && matches!(self.action, Action::Idle) =>
                {
                    if self.post_flinch == 11 {
                        // provenance: fitted -- canon's own +0x20 sentinel on the first idle frame after a flinch, read off the PAUSED+Start@10 watch capture
                        0xffff
                    } else {
                        (self.post_flinch - 1) as u16
                    }
                }
                _ => 0,
            }
        };
        OracleFields {
            // canon's u16 at +0x8 is CurState | CurAction << 8 -- idle
            // reads 0x0804, i.e. state in the LOW byte.
            cur_state_action: 0x04u16 | ((cur_action as u16) << 8),
            anim: self.player.anim() as u8,
            panel_x: self.col as u8,
            panel_y: self.row as u8,
            timer,
            hp: self.hp,
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
        if let Action::Leaving { to, .. } | Action::Hopping { to, .. } = self.action {
            mask |= field::panel_bit(to.0, to.1);
        }
        mask
    }

    /// Anything but idle holds the one `CurAction` slot, so a warp, a shot and
    /// a flinch all refuse to start over each other.
    pub fn is_busy(&self) -> bool {
        !matches!(self.action, Action::Idle)
    }

    /// Whether a move to `(col, row)` is allowed: inside this actor's half,
    /// and not a panel another object stands on or has reserved, which the
    /// game's destination filter rejects by the panel's reserve and occupant
    /// flags (byte_8012DD4 via object_getPanelsExceptCurrentFiltered,
    /// asm00_2.s:8933; asm/object.s:2956).
    fn can_move_to(&self, col: i32, row: i32, blocked: u32) -> bool {
        // Which panels belong to this side is in `blocked`: the caller adds
        // the other side's panels, so a stolen column opens up on its own.
        (1..=field::COLS).contains(&col)
            && (1..=field::ROWS).contains(&row)
            && blocked & field::panel_bit(col, row) == 0
    }

    /// Start warping by one panel. Refused while the action slot is taken or
    /// when the step would leave this actor's half of the field or land on a
    /// panel in `blocked`, the other objects' occupancy.
    pub fn step(&mut self, dx: i32, dy: i32, blocked: u32) -> bool {
        if self.is_busy() {
            return false;
        }
        let (to_col, to_row) = (self.col + dx, self.row + dy);
        if !self.can_move_to(to_col, to_row, blocked) {
            return false;
        }
        self.action = Action::Leaving {
            to: (to_col, to_row),
            ticks: LEAVING_FRAMES + WARP_DELAY,
        };
        true
    }

    /// Hop one panel, the way a Mettaur moves. Same refusals as `step`.
    pub fn hop(&mut self, dx: i32, dy: i32, blocked: u32) -> bool {
        if self.is_busy() {
            return false;
        }
        let (to_col, to_row) = (self.col + dx, self.row + dy);
        if !self.can_move_to(to_col, to_row, blocked) {
            return false;
        }
        self.action = Action::Hopping {
            to: (to_col, to_row),
            ticks: HOP_FRAMES,
        };
        self.player.play(anim::HOP);
        true
    }

    /// Take the action slot and hold `anim` until `release`.
    pub fn hold(&mut self, anim: usize) {
        self.player.play(anim);
        self.action = Action::Holding;
    }

    pub fn release(&mut self) {
        if matches!(self.action, Action::Holding) {
            self.player.play(anim::IDLE);
            self.action = Action::Idle;
        }
    }

    /// Start an attack. Refused unless idle, since attacking takes the same
    /// `CurAction` slot as movement.
    pub fn attack(&mut self, spec: AttackSpec) -> bool {
        if !matches!(self.action, Action::Idle) {
            return false;
        }
        // Export-only shadow (TODO R6): any new action after a hop's
        // cooldown means the recovery now belongs to the attack, not the
        // hop -- see `hop_recovery`'s doc.
        self.hop_recovery = false;
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
            recover_anim: spec.recover_anim,
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
        self.hop_recovery = false;
        self.action = Action::Flinching {
            ticks: FLINCH_FRAMES,
        };
    }

    pub fn update(&mut self) -> Update {
        self.invisible = self.invisible.saturating_sub(1);
        self.invulnerable = self.invulnerable.saturating_sub(1);
        // Export-only shadow decrement (TODO R6): see `post_flinch`'s doc.
        self.post_flinch = self.post_flinch.saturating_sub(1);
        if self.pale > 0 {
            self.pale -= 1;
            if self.pale == 0 {
                self.player.set_palette_add(0);
            }
        }
        if self.flash > 0 {
            self.flash -= 1;
            if self.flash == 0 && !matches!(self.action, Action::Dying { .. }) {
                self.player.set_white(false);
            }
        }
        let mut update = Update::Nothing;
        self.action = match self.action {
            Action::Idle => Action::Idle,
            Action::Leaving { to, ticks } if ticks > 1 => {
                if ticks == LEAVING_FRAMES {
                    self.player.play(anim::WARP_OUT);
                }
                Action::Leaving {
                    to,
                    ticks: ticks - 1,
                }
            }
            Action::Leaving { to, .. } => {
                (self.col, self.row) = to;
                self.player.play(anim::WARP_IN);
                // The frame the panel is committed on is drawn in the
                // sprite's SECOND palette, a washed-out copy of the first --
                // not forced white, which is what a hit does. Read off the
                // real ROM: five of that frame's colours are palette 1 of
                // battleSpriteMegaMan.spr word for word, and the frames
                // either side of it are palette 0.
                self.player.set_palette_add(WARP_PALETTE);
                self.pale = WARP_PALE_FRAMES;
                Action::Arriving {
                    ticks: ARRIVING_FRAMES,
                }
            }
            Action::Hopping { to, ticks } if ticks > 1 => {
                if ticks == HOP_FRAMES / 2 + 1 {
                    (self.col, self.row) = to;
                }
                Action::Hopping {
                    to,
                    ticks: ticks - 1,
                }
            }
            Action::Hopping { .. } => {
                self.player.play(anim::IDLE);
                // Export-only shadow (TODO R6): canon keeps the hop
                // executor's CurAction 0x0a through this cooldown.
                self.hop_recovery = true;
                Action::Recovering {
                    ticks: HOP_COOLDOWN,
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
            Action::Recovering { .. } => {
                self.player.play(anim::IDLE);
                self.hop_recovery = false;
                Action::Idle
            }
            Action::Aiming { ticks } if ticks > 1 => Action::Aiming { ticks: ticks - 1 },
            Action::Aiming { .. } => {
                self.begin(BUSTER, true);
                self.action
            }
            // As with the pose: the lead-in is on screen for every tick from
            // its length down to 1, and the pose begins the frame after (the
            // sword's two lead-in states are one frame each, then the slash).
            Action::WindingUp { ticks, next } if ticks > 0 => {
                update = Update::Winding {
                    frame: (self.pose_len - ticks) + 1,
                };
                Action::WindingUp {
                    ticks: ticks - 1,
                    next,
                }
            }
            Action::WindingUp { next, .. } => {
                // The frame that sets the pose is its first: the game's
                // slash state sets the animation and starts its counter in
                // the same tick (sub_80EB862), and the real ROM's sword arc
                // lands a frame earlier than a transition frame would allow
                // (TRANSFER.md 7b). So tick the new pose at once.
                self.begin(next, false);
                match self.action {
                    Action::Attacking {
                        ticks,
                        strike_tick,
                        charged,
                        recover,
                        recover_anim,
                    } => {
                        update = if ticks == strike_tick {
                            Update::Strike { charged }
                        } else {
                            Update::PoseBegun
                        };
                        Action::Attacking {
                            ticks: ticks - 1,
                            strike_tick,
                            charged,
                            recover,
                            recover_anim,
                        }
                    }
                    other => other,
                }
            }
            // The pose is on screen for every tick from `frames` down to 1;
            // the frame after the last is the exit (recovery or idle) --
            // verified against the real ROM for the cannon (0x1e frames of
            // pose, then the recovery pose) and the sword.
            Action::Attacking {
                ticks,
                strike_tick,
                charged,
                recover,
                recover_anim,
            } if ticks > 0 => {
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
                    recover_anim,
                }
            }
            Action::Attacking {
                recover,
                recover_anim,
                ..
            } => {
                if let Some(a) = recover_anim {
                    self.player.play(a);
                } else if recover == 0 {
                    self.player.play(anim::IDLE);
                }
                if recover > 0 {
                    update = Update::Recovering;
                    Action::Recovering { ticks: recover }
                } else {
                    Action::Idle
                }
            }
            Action::Flinching { ticks } if ticks > 0 => Action::Flinching { ticks: ticks - 1 },
            Action::Flinching { .. } => {
                self.player.play(anim::IDLE);
                // Export-only shadow (TODO R6): canon's MegaMan object
                // reads +0x20 = 0xffff on this first idle frame and 9..0
                // over the ten after (PAUSED+Start@10 watch capture).
                // provenance: fitted -- 1 sentinel frame + 10 counted off that capture, not derived from a cited instruction
                self.post_flinch = 11;
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
            Action::Holding => Action::Holding,
            Action::Hidden => Action::Hidden,
            Action::Appearing { ticks } if ticks > 1 => Action::Appearing { ticks: ticks - 1 },
            Action::Appearing { .. } => Action::Idle,
        };
        // The sprite ticks after the state machine, so an animation set this
        // frame -- by an attack begun before the update or by a transition
        // inside it -- is drawn on its first frame this frame and counts
        // from the next, whichever way it was set.
        self.player.update();
        update
    }

    pub fn show(&self, frame: &mut GraphicsFrame) {
        self.show_with_underlay(frame, |_| {});
    }

    /// Draw the navi with `underlay` drawn between its body and its shadow:
    /// the barrier bubble's OAM entries follow the navi's body parts and
    /// precede its shadow on the real ROM, so it covers the shadow and the
    /// body covers it.
    pub fn show_with_underlay(
        &self,
        frame: &mut GraphicsFrame,
        underlay: impl FnOnce(&mut GraphicsFrame),
    ) {
        let mut underlay = Some(underlay);
        // While invulnerable the object carries OBJECT_FLAGS_FLASHING
        // (asm00_2.s:23893) and blinks. The mercy handler's blink reads
        // `FlashingInvisTimer >> 2` and hides the object when the carry bit
        // from that shift is set (asm00_2.s:16796-16806), i.e. the timer's
        // bit 2 toggles the sprite hidden every four frames: four frames
        // visible, four hidden.
        if matches!(self.action, Action::Gone | Action::Hidden) {
            return;
        }
        // The mercy blink stops mattering once the navi is being deleted; the
        // die state's own white/visibility handling takes over.
        let dying = matches!(self.action, Action::Dying { .. });
        if !dying && self.flash == 0 && self.invulnerable > 0 && (self.invulnerable / 4) % 2 == 1 {
            return;
        }
        // Invisibl: the navi is not drawn on the frames where bit 1 of its
        // timer is set -- two hidden, two shown -- (blindVisualHandledHere_8016934,
        // asm00_2.s:16787: `lsr r0, r0, #2; bcc` on FlashingInvisTimer),
        // the timer having been counted down before the draw.
        if self.invisible & 2 != 0 {
            return;
        }
        let (px, py) = field::panel_centre(self.col, self.row);
        // The game fills OAM from the last part of a frame to the first, so
        // the first listed part ends up on top; the shadow is the last part
        // and the body covers it. Against the real ROM the shadow shows 99
        // pixels under the idle navi that way, 146 the other way round.
        // Parts draw last to first, so part 0 -- the shadow -- lands at the
        // bottom; the underlay goes in just above it.
        let parts = self.player.parts();
        for (i, part) in parts.iter().enumerate().rev() {
            if i == 0 {
                if let Some(u) = underlay.take() {
                    u(frame);
                }
            }
            // Offsets are authored facing right, so mirroring reflects the
            // whole composed frame about the actor origin, not each part in
            // place: the part's left edge moves to the opposite side.
            let x = if self.facing_left {
                -part.x - part.width
            } else {
                part.x
            };
            let mut object = Object::new(part.sprite.clone());
            // Every battle sprite is OAM priority 2 (sprite_initialize sets
            // the attribute base 0x800, sprite.s:116); that puts the actors
            // over the field and behind the chip select window on BG3 at
            // priority 1 (sub_801DA24, asm00_2.s:29038: BG3CNT 0x1f09).
            object
                .set_priority(Priority::P2)
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
        if let Some(u) = underlay {
            u(frame);
        }
    }
}
