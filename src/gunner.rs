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
