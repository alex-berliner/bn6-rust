//! The Gunner virus: a stationary cannon whose cursor walks the row until it
//! finds the player, then a volley of panel-anchored shots.
//!
//! Its AI decides every frame and, in the first version, attacks only when an
//! opponent stands somewhere ahead in its row (sub_8113162, asm32.s:10248).
//! It aims in pose 1 while the cursor travels, fires in pose 2 -- one shot at
//! once and one every ten frames, three in all -- and recovers in pose 3 for
//! 24 frames (sub_8112F4E, sub_8113002, ai_8113038; asm32.s:9958-10102).

use agb::display::GraphicsFrame;
use agb::display::Priority;
use agb::display::object::Object;

use crate::actor::Actor;
use crate::field;
use crate::spr;

/// Gunner first-version stats: HP 0x3c, 10 damage
/// (GunnerEnemyStruct2_8112B9C, asm32.s:9538).
pub const HP: u16 = 60; // provenance: derived -- GunnerEnemyStruct2_8112B9C, asm32.s:9538
pub const DAMAGE: u16 = 10; // provenance: derived -- GunnerEnemyStruct2_8112B9C, asm32.s:9538

const AIM: usize = 1;
const FIRE: usize = 2;
const RECOVER: usize = 3;
const SHOTS: u8 = 3; // provenance: derived -- sub_8112F4E/sub_8113002/ai_8113038, asm32.s:9958-10102
const SHOT_GAP: u8 = 10; // provenance: derived -- sub_8112F4E/sub_8113002/ai_8113038, asm32.s:9958-10102
const RECOVER_FRAMES: u8 = 24; // provenance: derived -- sub_8112F4E/sub_8113002/ai_8113038, asm32.s:9958-10102

/// The lock-on cursor, sprite_8372F34: spawned on the gunner's own panel, it
/// moves at the version's speed, 3 px a frame in the first, and re-checks the
/// panel it is over on every panel's worth of travel; finding an opponent
/// there it locks for 24 frames and hands the panel back
/// (t4_0x30_80E3B70, sub_80E3CC4; asm31.s:92489-92682; byte_81130A8,
/// byte_81130C6).
pub struct Cursor {
    x: i32,
    row: i32,
    dx: i32,
    beat: u8,
    lock: Option<u8>,
    player: spr::Player,
}

const CURSOR_SPEED: i32 = 3; // provenance: derived -- t4_0x30_80E3B70/sub_80E3CC4, asm31.s:92489-92682
/// 0x280000 / 0x30000 frames per panel, rounded down.
const CURSOR_BEAT: u8 = 13; // provenance: derived -- t4_0x30_80E3B70/sub_80E3CC4, asm31.s:92489-92682
const LOCK_FRAMES: u8 = 24; // provenance: derived -- byte_81130A8/byte_81130C6, asm31.s:92489-92682

pub enum CursorState {
    Travelling,
    /// Locked onto this panel and done.
    Locked((i32, i32)),
    /// Ran off the field without finding anyone.
    Lost,
}

impl Cursor {
    pub fn new(assets: spr::Assets, from: (i32, i32), dx: i32) -> Self {
        Self {
            x: field::panel_centre(from.0, from.1).0,
            row: from.1,
            dx,
            beat: CURSOR_BEAT,
            lock: None,
            player: spr::Player::new(assets, 0),
        }
    }

    fn col(&self) -> i32 {
        (self.x + 20).div_euclid(40)
    }

    pub fn update(&mut self, target: (i32, i32)) -> CursorState {
        self.player.update();
        if let Some(dwell) = self.lock {
            if dwell > 1 {
                self.lock = Some(dwell - 1);
                return CursorState::Travelling;
            }
            return CursorState::Locked((self.col(), self.row));
        }
        self.x += CURSOR_SPEED * self.dx;
        self.beat -= 1;
        if self.beat == 0 {
            self.beat = CURSOR_BEAT;
            let col = self.col();
            if !(1..=field::COLS).contains(&col) {
                return CursorState::Lost;
            }
            if (col, self.row) == target {
                self.lock = Some(LOCK_FRAMES);
                self.player.play(1);
            }
        }
        CursorState::Travelling
    }

    pub fn show(&self, frame: &mut GraphicsFrame) {
        let y = field::panel_centre(1, self.row).1;
        for part in self.player.parts().iter().rev() {
            Object::new(part.sprite.clone())
                .set_priority(Priority::P2)
                .set_pos((self.x + part.x, y + part.y))
                .set_hflip(part.hflip)
                .set_vflip(part.vflip)
                .show(frame);
        }
    }
}

/// One shot: anchored to its panel, it warns for ten frames while the panel
/// blinks, then lands with sprite_8372410 and its damage
/// (t3_0xd3_80DFE40, sub_80DFEE8; asm31.s:84400, 84485). The first version
/// does not crack the panel.
pub struct Impact {
    pub col: i32,
    pub row: i32,
    warn: u8,
    player: spr::Player,
}

const WARN_FRAMES: u8 = 10; // provenance: peeked -- measured against the real ROM

impl Impact {
    pub fn new(assets: spr::Assets, at: (i32, i32)) -> Self {
        Self {
            col: at.0,
            row: at.1,
            warn: WARN_FRAMES,
            player: spr::Player::new(assets, 0),
        }
    }

    /// Advance a frame. Returns `Some(true)` on the frame the shot lands, and
    /// `None` once its flash has played out and it should be dropped.
    pub fn update(&mut self, panels: &mut field::Panels) -> Option<bool> {
        if self.warn > 0 {
            // The panel blinks while the shot warns: the impact object
            // highlights it on the frames where its countdown's bit 2 is
            // clear, then decrements -- a 3-on, 4-off pattern from the 0xa
            // seed (t3_0xd3_80DFE40, sub_80DFEE8, asm31.s:84487, 84490).
            if self.warn & 4 == 0 {
                panels.highlight(self.col, self.row, 0);
            }
            self.warn -= 1;
            return Some(self.warn == 0);
        }
        self.player.update();
        if self.player.finished() {
            None
        } else {
            Some(false)
        }
    }

    pub fn show(&self, frame: &mut GraphicsFrame) {
        if self.warn > 0 {
            return;
        }
        let (px, py) = field::panel_centre(self.col, self.row);
        for part in self.player.parts().iter().rev() {
            Object::new(part.sprite.clone())
                .set_priority(Priority::P2)
                .set_pos((px + part.x, py + part.y))
                .set_hflip(part.hflip)
                .set_vflip(part.vflip)
                .show(frame);
        }
    }
}

enum Phase {
    Idle,
    Aiming,
    Firing { left: u8, ticks: u8, at: (i32, i32) },
    Recovering { ticks: u8 },
}

/// The Gunner's own controller, in place of the shared attack machine.
pub struct Gunner {
    phase: Phase,
    cursor: Option<Cursor>,
}

impl Gunner {
    pub fn new() -> Self {
        Self {
            phase: Phase::Idle,
            cursor: None,
        }
    }

    pub fn cursor(&self) -> Option<&Cursor> {
        self.cursor.as_ref()
    }

    /// Run one frame for `me`. New shots are pushed onto `impacts`.
    pub fn update(
        &mut self,
        me: &mut Actor,
        target: (i32, i32),
        cursor_assets: spr::Assets,
        impacts: &mut alloc::vec::Vec<Impact>,
        impact_assets: fn() -> spr::Assets,
    ) {
        self.phase = match self.phase {
            Phase::Idle => {
                if !me.is_busy() && target.1 == me.panel().1 {
                    me.hold(AIM);
                    self.cursor = Some(Cursor::new(cursor_assets, me.panel(), me.facing_dx()));
                    Phase::Aiming
                } else {
                    Phase::Idle
                }
            }
            Phase::Aiming => match self.cursor.as_mut().map(|c| c.update(target)) {
                Some(CursorState::Travelling) => Phase::Aiming,
                Some(CursorState::Locked(at)) => {
                    self.cursor = None;
                    me.hold(FIRE);
                    Phase::Firing {
                        left: SHOTS,
                        ticks: 0,
                        at,
                    }
                }
                _ => {
                    self.cursor = None;
                    me.release();
                    Phase::Idle
                }
            },
            Phase::Firing { left, ticks, at } if ticks > 0 => Phase::Firing {
                left,
                ticks: ticks - 1,
                at,
            },
            Phase::Firing { left, at, .. } if left > 0 => {
                impacts.push(Impact::new(impact_assets(), at));
                Phase::Firing {
                    left: left - 1,
                    ticks: SHOT_GAP,
                    at,
                }
            }
            Phase::Firing { .. } => {
                me.hold(RECOVER);
                Phase::Recovering {
                    ticks: RECOVER_FRAMES,
                }
            }
            Phase::Recovering { ticks } if ticks > 1 => Phase::Recovering { ticks: ticks - 1 },
            Phase::Recovering { .. } => {
                me.release();
                Phase::Idle
            }
        };
    }
}

// =========================================================================
// T9h (2026-09-15): the per-type routine cite + the materialize/animation
// state slots, mirroring `objects::MettaurEntry`'s T6 port.
//
// The dispatch shape canon uses to pick this routine:
//   1. `GetVerActorTyAndAIIdx_80182B4` (reference/bn6f/asm/asm00_2.s:19965-19974)
//      reads `byte_80182C4[3*enemy_idx]` -- the (Version, ActorType, AIIndex)
//      row -- and returns a pointer to it.
//   2. For the Gunner (enemy_idx 0x85, the NameID the poked BattleSettings
//      record 6's slot 1 populates with; see T9b's slot probe and T9c's
//      battle_isBattleOver patch), the row is `(0, ACTOR_TYPE_VIRUS, 0x17)`.
//   3. AIIndex 0x17 routes through `off_8109050` to the CurAction-indexed
//      handler table `ForGunner_8113078` (asm32.s:10123) -- the routine the
//      canon interpreter runs for every frame this Gunner is alive.
//
// The handler table (asm32.s:10123-10142, cited verbatim):
//
//   | index | routine                                       | what canon runs        |
//   |-------|-----------------------------------------------|------------------------|
//   | 0x00  | RunSpawnAnimationMaybe_8016380+1              | spawn animation        |
//   | 0x04  | sub_80165B8+1                                 | spawn arming           |
//   | 0x08  | sub_80165C2+1                                 | idle (freezes if dead) |
//   | 0x0C  | sub_81166AE+1 (sub_80166AE+1)                 | hit reaction           |
//   | 0x10  | sub_81130E4+1                                 | materialize arm 1      |
//   | 0x14  | sub_81130F0+1                                 | materialize arm 2      |
//   | 0x18  | sub_81130FC+1                                 | materialize arm 3      |
//   | 0x1C  | sub_8113108+1                                 | materialize arm 4      |
//   | 0x20  | sub_8113124+1                                 | AI tick arm            |
//   | 0x24  | genericAI_exitAttackStateAfterDelay_81097BA+1| wait/recover           |
//   | 0x28  | sub_8112F4E+1                                 | ATTACK (cursor+impact) |
//   | 0x2C  | sub_8112D9C+1                                 | guard/cleanup          |
//
// Per-state timer arms (cite asm/object.s for the per-state read), from the
// matched `sub_*` routines above:
//
//   | state | timer arm                       | source                          |
//   |-------|---------------------------------|---------------------------------|
//   | 0x0A  | SHOTS = 3 (asm32.s:9958-10102)  | sub_8112F4E / sub_8113002 / ai_8113038 |
//   | 0x0A  | SHOT_GAP = 10                   | sub_8113002 (asm32.s:10066-10070)|
//   | 0x0A  | RECOVER_FRAMES = 24             | ai_8113038 (asm32.s:10087-10117) |
//   | 0x04  | spawn wait (sprite_getFrameParameters bit 0x80) | sub_8112F70 |
//
// The Gunner controller in this file (`Gunner::update`) IS the CurAction
// 0x0A arm in the table above -- the cursor + impact driver that fires
// three panel-anchored shots 10 frames apart, then recovers for 24 frames.
// CurActions 0x00..0x09, 0x0B are routed through the shared `Actor::update`
// / `Ai::update` common path the way `MettaurEntry` routes 0x08..0x0C
// (objects.rs: the cite is the same shape; not re-implemented here).
//
// What this struct models: the per-state fields canon's interpreter holds
// alongside the routine -- `oAIAttackVars_Unk_00` (the CurAction-indexed
// stage), `oAIAttackVars_Unk_01` (the per-state one-shot latch),
// `oAIAttackVars_Unk_10` (the CurAction-0x24 / 0x0A wait counter), and
// `oAIAttackVars_Unk_18` (the CurAction 0x0A initial wait seed). The
// Gunner controller above uses these for its three-shot/recover machine
// (SHOTS / SHOT_GAP / RECOVER_FRAMES). Mirrored one-for-one with
// `MettaurEntry` so future per-state work has the same shape on both arms.
pub struct GunnerEntry {
    /// `oAIAttackVars_Unk_00` (asm32.s:9961): the CurAction-indexed stage
    /// within the current CurAction's arm.
    stage: u8,
    /// `oAIAttackVars_Unk_01` (asm32.s:10060): the per-state one-shot latch
    /// (set on first call, cleared on exit -- `sub_8113002`/`ai_8113038`).
    latch: u8,
    /// `oAIAttackVars_Unk_10` (asm32.s:10066): the CurAction-0x0A wait
    /// counter (10 frames per shot, decremented `bgt`-style).
    wait: u16,
    /// `oAIAttackVars_Unk_18` (asm32.s:10109): the CurAction-0x0A recover
    /// counter (24 frames, decremented `bgt`-style).
    recover: u16,
}

impl GunnerEntry {
    /// Canon starts in CurAction 0x00 with the per-state fields cleared --
    /// `sub_8112F70`/`sub_8113002`/`ai_8113038` all branch on
    /// `oAIAttackVars_Unk_01 == 0` to do their one-shot init (the
    /// first frame in any state sets it to 1).
    pub fn new() -> Self {
        Self {
            stage: 0,   // canon: oAIAttackVars_Unk_00, cleared for a fresh object
            latch: 0,   // canon: oAIAttackVars_Unk_01, cleared for a fresh object
            wait: 0,    // canon: oAIAttackVars_Unk_10, cleared for a fresh object
            recover: 0, // canon: oAIAttackVars_Unk_18, cleared for a fresh object
        }
    }
}
