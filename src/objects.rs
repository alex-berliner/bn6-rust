//! The object dispatcher: docs/coverage/plan-interpreters.md section 2.
//!
//! The real game keeps one table of live battle objects and, each frame,
//! dispatches every live object to its per-type entry routine: the T1 table
//! (`T1BattleObjectJumptable`, reference/bn6f/asm/asm00_1.s:1891) and the T3
//! table (`T3BattleObjectJumptable`, asm00_1.s:2087) select the handler, the
//! virus arm runs `battleObject_dispatch_8108F50` (asm31.s:169291) into
//! `battle_8108F74` (asm31.s:169314) and `RunAIAttack` (asm00_2.s:24781),
//! and every object shares the `battle_801B1C4` common path
//! (asm00_2.s:23679). This module ports that table and dispatch shape;
//! section 2.3's per-type entries are our own object types at first
//! (`Actor::update`, `Ai::update`, `Shot::update`), so behaviour is
//! unchanged and the full harness table is the regression test.
//!
//! What routes through here, per frame, in battle.rs's update:
//!
//! - the player (`t1_player_entry`): `t1_0x0_80B81EC`'s player arm
//!   (asm31.s:15) into `playerObject_main_80EA460`.
//! - each enemy, in two legs (`enemy_think`, then `enemy_act`): the
//!   virus/navi arms of `t1_0x0_80B81EC` into
//!   `battleObject_dispatch_8108F50` (virus) and `sub_80F2330` (navi),
//!   both over the shared `battle_801B1C4` core, with the attack-anim
//!   driver `sub_8016E64` (asm00_2.s:17420) as the tail.
//! - each shot (`t3_entry`): the T3 table by shot kind -- `t3_0x0_80C4E58`
//!   (buster/cannon, asm31.s:27691), `t3_0x12` (vulcan seed,
//!   `t3_0x12_80C6946` into `sub_80C6A08`, asm31.s:31212), `t3_0x16_80C6B40`
//!   (shockwave segment, asm31.s:31413).
//!
//! What does NOT route through here (outside the harness-covered entries,
//! left on their direct ticks with the reason at each site):
//!
//! - transient visuals (`Battle::effects`, the vulcan gun/fireball, the
//!   areagrab orbs, bombs, the heal/sword flashes): canon spawns these as
//!   short-lived effect objects through byte_80B8BD4 rows, but ours have no
//!   CurState/CurAction lifecycle -- they are frame-counted sprites, not
//!   dispatched objects.
//! - the Gunner's cursor and impacts (`gunner_ctl`): driven by their own
//!   controller, as `Style::Gunner` is inside `Ai` (an empty arm there).
//!
//! ORDER. Canon iterates one live-object table per frame; battle.rs still
//! ticks shots before actors (the order the hand-written loops always used,
//! which the spawn-frame behaviour in shot.rs's pre-tick and the wave_spawn
//! nudge is calibrated against). Reordering the table walk itself is future
//! work -- this port only names the entries so the walk has one place to
//! change.

use crate::actor::{Actor, Update};
use crate::ai::{Ai, Rng, Style};
use crate::shot::Shot;

/// T3 type of the buster/cannon projectile: `t3_0x0_80C4E58`
/// (reference/bn6f/asm/asm31.s:27691; spawn `sub_80C4E7C`/`sub_80C4F02`).
const T3_BUSTER_CANNON: u8 = 0x0; // provenance: derived -- t3_0x0_80C4E58, asm31.s:27691
/// T3 type of Vulcan's seed shot: `t3_0x12_80C6946` into `sub_80C6A08`
/// (asm31.s:31212).
const T3_VULCAN_SEED: u8 = 0x12; // provenance: derived -- t3_0x12_80C6946, asm31.s:31212
/// T3 type of the shockwave segment: `t3_0x16_80C6B40` (asm31.s:31413).
const T3_SHOCKWAVE: u8 = 0x16; // provenance: derived -- t3_0x16_80C6B40, asm31.s:31413

/// Which T3 table entry a shot ticks through. The discriminant IS the canon
/// T3 type number (the `T3BattleObjectJumptable` index, asm00_1.s:2087), so
/// `t3_entry`'s match reads as the table itself.
#[repr(u8)]
#[derive(Clone, Copy, PartialEq, Eq)]
pub enum T3Kind {
    BusterCannon = T3_BUSTER_CANNON,
    VulcanSeed = T3_VULCAN_SEED,
    Shockwave = T3_SHOCKWAVE,
}

/// Plan §2.3 step 1 -- the common path every battle object shares:
/// `battle_801B1C4` (reference/bn6f/asm/asm00_2.s:23679): pause, collision,
/// HP/death and flag bookkeeping, then the `RunAIAttack` tail (or
/// `sub_8016BFC` in timestop). Ours: `Actor::update` owns the pose, HP,
/// mercy and invulnerability bookkeeping; the pause gate (`paused`, the
/// chip-window freeze) stays at the battle.rs call site, which is the part
/// of the common path this project models outside the object. Timestop has
/// no model yet (plan §1.7 notes), so there is no second tail.
pub fn battle_common_path(actor: &mut Actor) -> Update {
    actor.update()
}

/// Plan §2.3 step 2 (think leg) -- the virus dispatch:
/// `battleObject_dispatch_8108F50` (asm31.s:169291: the `CurState` 3-table
/// `off_8108F68` -- `sub_8016F56` / `battle_8108F74` / `sub_8016C4E` -- then
/// unconditionally the attack-anim driver `sub_8016E64`) into
/// `battle_8108F74` (asm31.s:169314: `AIIndex` into the behavior table
/// `off_8109050` and the attack table `off_81091D0`) into `RunAIAttack`
/// (asm00_2.s:24781: `CurAction < 0x10` takes the per-type table,
/// `>= 0x10` the shared `AIAttackJumptable`, gated by `Unk_1d == 1`).
/// The match below is `t1_0x0_80B81EC`'s own `ActorType` 3-way (asm31.s:15):
/// virus takes the dispatch above, navi takes `sub_80F2330` (unread; it
/// shares the `battle_801B1C4` core, so both arms reach `Ai::update` here),
/// and the player never reaches this leg (see `t1_player_entry`). The
/// Mettaur arm's behavior-table entry is `ForMettaur_8109EF4`
/// (asm31.s:170982), ported as `MettaurState` in ai.rs (plan §2.3 step 4,
/// already landed -- cited, not moved).
pub fn enemy_think(
    ai: &mut Ai,
    me: &mut Actor,
    target: (i32, i32),
    blocked: u32,
    rng: &mut Rng,
) {
    match ai.style() {
        // canon: virus ActorType -> battleObject_dispatch_8108F50.
        Style::Mettaur => {}
        // canon: navi ActorType -> sub_80F2330; same core, same call.
        Style::Thrust | Style::Divide => {}
        // canon: driven by its own controller, never the AI tables; the
        // battle.rs loop `continue`s past this leg for Gunner, so this arm
        // is unreachable through the dispatch (kept total, not deleted).
        Style::Gunner => {}
    }
    ai.update(me, target, blocked, rng);
}

/// Plan §2.3 step 2 (act leg) -- the dispatch tail: the attack-anim driver
/// `sub_8016E64` (asm00_2.s:17420, rank 67 battle_full) over the common
/// path. Every arm of `enemy_think` lands here once its AI tables return.
pub fn enemy_act(enemy: &mut Actor) -> Update {
    battle_common_path(enemy)
}

/// The player arm of `t1_0x0_80B81EC` (asm31.s:15):
/// `playerObject_main_80EA460`. Reached through the same common path; the
/// player's input sampling (`pwrAtkRelated_readsFromJoypad_8012FC8`,
/// asm00_2.s:9332) stays at the battle.rs call site with the other input.
pub fn t1_player_entry(player: &mut Actor) -> Update {
    battle_common_path(player)
}

/// Plan §2.3 step 3 -- the T3 table itself (`T3BattleObjectJumptable`,
/// asm00_1.s:2087), indexed by the shot's kind: `t3_0x0` for the
/// buster/cannon, `t3_0x12` for the vulcan seed, `t3_0x16` for the
/// shockwave. Each entry falls through to `object_updateSprite` after its
/// state routine (asm31.s:27690-27697, same shape at :31413-31421), which
/// is the spawn-frame pre-tick `Shot::new` already takes.
pub fn t3_entry(shot: &mut Shot) -> bool {
    match shot.kind() {
        T3Kind::BusterCannon => t3_0x0_entry(shot),
        T3Kind::VulcanSeed => t3_0x12_entry(shot),
        T3Kind::Shockwave => t3_0x16_entry(shot),
    }
}

/// `t3_0x0_80C4E58` (asm31.s:27691): state 0 `sub_80C4E7C` loads the sprite
/// and animation data (asm31.s:27725-27732); the timer seeded from `Timer2`
/// hops the hitbox one panel per decrement pair (asm31.s:27728, 27769 --
/// `BUSTER_HOP` in shot.rs).
fn t3_0x0_entry(shot: &mut Shot) -> bool {
    shot.update()
}

/// `t3_0x12_80C6946` into `sub_80C6A08` (asm31.s:31212): one panel a frame,
/// stopped by the first thing it hits, no sprite of its own (only the hit
/// spark `sub_80C6A50` shows, :31253 -- `hidden` in shot.rs).
fn t3_0x12_entry(shot: &mut Shot) -> bool {
    shot.update()
}

/// `t3_0x16_80C6B40` (asm31.s:31413): dwell `byte_80C6B00` frames per panel
/// (`WAVE_HOP` in shot.rs), hop by spawning a whole new segment object on
/// the next panel (`sub_80C6CE4`, :31578) while the old one keeps looping
/// until its own last frame (`sub_80C6CBA`, :31552-31567 -- `departure` in
/// shot.rs), travelling until the panel ahead is invalid.
fn t3_0x16_entry(shot: &mut Shot) -> bool {
    shot.update()
}
