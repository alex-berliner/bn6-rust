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

use crate::actor::{self, Actor, Update};
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

// T7q: the MegaMan executor's per-tick gate. Canon runs
// `playerObject_main_80EA460` (`reference/bn6f/asm/asm31.s:107131`) and
// its tail `playerObject_update_80EA484` (asm31.s:107147), which calls
// the per-tick work (input read `sub_8012E74`, AI tick `sub_8013DA0`,
// state-machine dispatch `sub_801AC6C`, attack `ai_eventuallyRunsAIAttack_801AF44`,
// etc). When the sequencer state is in the pre-fight window the
// executor's per-tick work is gated (draw, timer tick, state advance
// all skipped so +0x20 / CurState / CurAction hold their previous
// values for that frame -- the same mechanism T7o PARTIAL [784c8e5]
// observed the SEQ_04 -> SEQ_08 release edge fires AFTER). The gate
// values 0x20/0x24/0x00/0x04 are off_8008038 entries 8/9/0/1,
// respectively `sub_8008452` (window opening), `sub_8008492` (window
// open), `sub_800840C` (post-window settle), `sub_8008064` (the
// banner wait).
const PLAYER_EXECUTOR_GATED_STATE_00: u32 = 0x00; // provenance: derived -- off_8008038 entry 0 (sub_800840C, the post-window settle)
const PLAYER_EXECUTOR_GATED_STATE_04: u32 = 0x04; // provenance: derived -- off_8008038 entry 1 (sub_8008064, the banner wait)
const PLAYER_EXECUTOR_GATED_STATE_20: u32 = 0x20; // provenance: derived -- off_8008038 entry 8 (sub_8008452, the window opening)
const PLAYER_EXECUTOR_GATED_STATE_24: u32 = 0x24; // provenance: derived -- off_8008038 entry 9 (sub_8008492, the window open)

/// True when canon's MegaMan executor (`playerObject_update_80EA484` /
/// `sub_801AC6C`) early-returns because the sequencer is in a pre-fight
/// window. Calling code skips `Actor::update` so the player's per-tick
/// fields (CurState, CurAction, Timer, CurAnim) hold their previous
/// frame's values for the frame.
fn player_executor_gated(seq_state: u32) -> bool {
    matches!(
        seq_state,
        PLAYER_EXECUTOR_GATED_STATE_00
            | PLAYER_EXECUTOR_GATED_STATE_04
            | PLAYER_EXECUTOR_GATED_STATE_20
            | PLAYER_EXECUTOR_GATED_STATE_24
    )
}

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
/// (asm31.s:170982), ported as `MettaurEntry` below (plan §2.3 step 4).
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
        // canon: virus ActorType -> battleObject_dispatch_8108F50. The per-
        // type routine `ForGunner_8113078` (reference/bn6f/asm/asm32.s:10123)
        // is selected through `byte_80182C4[3*enemy_idx]`: the canon
        // interpreter reads the (Version, ActorType, AIIndex) row at
        // `&byte_80182C4[3*enemy_idx]` via `GetVerActorTyAndAIIdx_80182B4`
        // (asm00_2.s:19965-19974) and routes AIIndex 0x17 to
        // `ForGunner_8113078`. The CurAction 0x0A arm of that table is
        // `sub_8112F4E` (asm32.s:9958-10102), ported as
        // `gunner::gunner_update` below -- the per-type routine that
        // advances the Gunner's per-state fields (stage/latch/wait/recover)
        // and returns Update the way `MettaurEntry::think` runs CurAction 8
        // for the Mettaur. Reached through the dispatch (battle.rs's
        // `enemy_think` call) once CurAction reaches 0x0A; for the other
        // CurActions this arm falls through to `ai.update` as before.
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
///
/// T7q: the `seq_state` parameter is the sequencer's current state
/// (battle.rs's `self.seq.state`). When canon's MegaMan executor is in
/// one of the pre-fight window states (SEQ_20/SEQ_24/SEQ_00/SEQ_04)
/// its per-tick work is gated -- draw, timer tick, state advance all
/// skipped (cited at asm31.s:107147 `playerObject_update_80EA484`'s
/// call chain into `sub_801AC6C`/the AI attacks/etc, gated by the
/// off_8008038 entries 8/9/0/1 dispatcher `sub_8009158` in
/// asm00_1.s:12760 which routes SEQ_20/24/00/04 to the window/banner
/// handler arms and does NOT itself call `RunBattleObjectLogic`).
/// Porting the gate here means the per-tick fields stay at their
/// previous-frame values for those frames, matching canon's
/// observed +0x20/CurState/CurAction/CurAnim hold.
pub fn t1_player_entry(player: &mut Actor, seq_state: u32) -> Update {
    if player_executor_gated(seq_state) {
        return Update::Nothing;
    }
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

/// T6 -- the Mettaur's per-type entry: `ForMettaur_8109EF4`
/// (reference/bn6f/asm/asm31.s:170982), the `off_8109050` behavior-table arm
/// for AIIndex 4, with the decision loop it dispatches to (`sub_8109FD6` over
/// `off_8109FF0`) and the executors the loop arms: the CurAction-9 waiter
/// `sub_8109CBC` (asm31.s:170665), the hop executor `sub_8109CE6`
/// (asm31.s:170689), the attack executor `sub_8109DD2` (asm31.s:170814) and
/// the guard executor `sub_8109E7A` (asm31.s:170908, unreachable -- see below).
///
/// Canon's fields, mirrored one for one (member names are the struct-field
/// names in include/structs/AIAttackVars.inc, AIState.inc and
/// BattleObject.inc):
///
/// - `decide` = `oAIState_Unk_00`, the `off_8109FF0` decision-table index.
/// - `decide_sub` = `oAIState_Unk_02`, `sub_810A0BA`'s sub-state (0 = the
///   hop arm `sub_810A0D4`, 4 = the roll/wait arm `sub_810A0EE`).
/// - `latch` = `oAIState_Unk_03`, `sub_810A0EE`'s one-shot latch: 0 rolls
///   this frame, 1 counts `wander_wait` down. Every `RowCheck` exit in
///   `sub_810A004` clears it with the same `strh Unk_02` that clears
///   `decide_sub`, so each blind episode rolls exactly once.
/// - `wander_wait` = `oAIState_Unk_08`, the losing roll's idle counter.
/// - `wait` = `oAIAttackVars_Unk_10`, the CurAction-9 waiter's countdown.
/// - `cur_action`: the object's CurAction as the entry moves it (8 decide,
///   9 wait; the hop/attack executors' 0x0A/0x0B live in `Actor`, below).
/// - `hop_done` = `oAIAttackVars_Unk_1a`, the hop executor's report: 1 on
///   the commit step (`sub_8109DBA`), 0 on the refused-move step
///   (`sub_8109D08`'s `object_canMove` fail). `Actor::hop`'s own
///   accept/refuse IS that check, so it is stored at issue time.
/// - `param4` = `oBattleObject_Param4`, the one-time post-spawn gate.
///
/// What runs where. The decision loop (CurAction 8) only runs once an
/// executor exits back to it, so `think` runs only while `Actor` is idle --
/// the battle loop already gates `enemy_think` on `!is_busy`, and `think`
/// re-checks. Motion itself stays in `Actor`: `hop` is the 0x0A executor's
/// 6 frames plus its `byte_8109F46[0]` cooldown, `SWING` the 0x0B
/// executor's 0x40 swing plus its 0x28 recovery (actor.rs cites both), and
/// the battle loop re-enters `think` once `is_busy` clears -- the same
/// frames canon's executors hand CurAction 8 back on. `sub_810A080`'s
/// arming half (pick the panel via `sub_810A21A`, `object_setAttack0(0xA)`)
/// is folded into the `RowCheck` arm that issues the hop: same frame,
/// same direction, same accept/refuse.
///
/// Unreachable for this project's only Mettaur (Version 0, no equipped
/// item, no status chips) and given no arm below: the guard executor
/// (`sub_810A004`'s `Version != 0` "being hit" branch into CurAction 0x0C)
/// and the `sub_810A204` special state (`sub_810A126`'s `sub_800ED90`
/// equipped-ability gate into Unk_00 0x10). A stray 0x10 in `decide`
/// re-enters `RowCheck` rather than stalling.
pub struct MettaurEntry {
    decide: u8,
    decide_sub: u16,
    latch: u8,
    wander_wait: u16,
    wait: u16,
    cur_action: u8,
    hop_done: u8,
    param4: u8,
}

/// `off_8109FF0[0]`, `sub_810A004` (asm31.s:171129-171196): compare rows,
/// branch to align/wander/decide. The value IS `oAIState_Unk_00`.
const METTAUR_ROW: u8 = 0; // provenance: derived -- off_8109FF0[0], asm31.s:171195
/// `off_8109FF0[1]`, `sub_810A080` (asm31.s:171199-171233): a hop toward the
/// target's row is running; wait for its `Unk_1a` report, then RowCheck or
/// Decide. The value IS `oAIState_Unk_00`.
const METTAUR_ALIGN: u8 = 4; // provenance: derived -- off_8109FF0[1], asm31.s:171197
/// `off_8109FF0[2]`, `sub_810A0BA` (asm31.s:171311-171376): blind/confused
/// wander, in `decide_sub` halves. The value IS `oAIState_Unk_00`.
/// T18 measured the gate that arms this state (the RowCheck
/// `=0xa000` BLIND|CONFUSED tst) at asm31.s:171395-171397, and BLIND's own
/// reader (a hide-sprite `tst` of 0x2000 on `battle_findPlayer`'s result) at
/// asm00_2.s:16861 -- see docs/inventory/statuses.json.
const METTAUR_WANDER: u8 = 8; // provenance: derived -- off_8109FF0[2], asm31.s:171199
/// `off_8109FF0[3]`, `sub_810A126` (asm31.s:171379-171451): rows equal,
/// attack. The value IS `oAIState_Unk_00`.
const METTAUR_DECIDE: u8 = 0x0c; // provenance: derived -- off_8109FF0[3], asm31.s:171201
/// `sub_810A0D4`'s exit writes 4 to `oAIState_Unk_02`, selecting `sub_810A0EE`
/// (asm31.s:171399-171403).
const METTAUR_ROLL_SUB: u16 = 4; // provenance: derived -- sub_810A0D4, asm31.s:171399-171403
/// The decision loop's own CurAction: `sub_8109FD6` runs as CurAction 8
/// (`ForMettaur_8109EF4[8]`, asm31.s:171002).
const METTAUR_ACT_DECIDE: u8 = 8; // provenance: derived -- ForMettaur_8109EF4[8], asm31.s:171002
/// The plain "wait N frames" CurAction the spawn pause runs in
/// (`ForMettaur_8109EF4[9]` = `sub_8109CBC`, asm31.s:171004).
const METTAUR_ACT_WAIT: u8 = 9; // provenance: derived -- ForMettaur_8109EF4[9], asm31.s:171004
/// The one-time pause before a freshly-spawned Mettaur's very first
/// decision: `sub_810A004`'s own `oBattleObject_Param4 == 0` branch arms a
/// flat 0x1e wait (CurAction 9, `sub_8109CBC`) the first time `RowCheck`
/// ever runs, then never again (Param4 is left nonzero).
/// asm31.s:171296-171305.
///
/// THE VALUE IS 0x1e AND THE WAIT IS 31 FRAMES LONG, not 30 (F28,
/// 2026-09-13). `sub_8109CBC` (asm31.s:170665-170672) is
/// `ldrh Unk_10; sub r0,#1; strh; bge locret` -- it returns while the
/// DECREMENTED value is still >= 0, so an arming of 0x1e runs on the frames
/// carrying 30, 29 ... 1, 0 and only exits on the 31st, where the subtract
/// takes it to -1. `think` counts the same 31 frames.
const METTAUR_SPAWN_WAIT: u16 = 0x1e; // provenance: derived -- sub_810A004, asm31.s:171296-171305
/// The idle a losing wander roll arms: `sub_810A0EE` stores 0x32 to
/// `oAIState_Unk_08` (asm31.s:171430-171432), which counts down past zero
/// the same way the waiter does.
const METTAUR_WANDER_WAIT: u16 = 0x32; // provenance: derived -- sub_810A0EE, asm31.s:171430-171432

/// This project has no chip that sets `OBJECT_FLAGS_BLIND`,
/// `OBJECT_FLAGS_CONFUSED` or `OBJECT_FLAGS_IMMOBILIZED` yet (grepped every
/// `src/*.rs` chip effect; none exists) -- see ai.rs's `Rng` doc for the
/// empirical per-frame-cadence check that the RNG-gated wander branch never
/// fires in the fixtures this project measures. Named rather than inlined so
/// a future status-effect chip has one place to flip it live.
const BLIND_OR_CONFUSED: bool = false; // provenance: derived -- no chip in this project sets OBJECT_FLAGS_BLIND/CONFUSED/IMMOBILIZED (0xa000/0x4000) yet, include/structs/CollisionData.inc:16-18

impl MettaurEntry {
    /// Canon starts in the decision loop's state 0 with Param4 == 0: the
    /// wait is armed BY `RowCheck`'s own first run, it is not the state the
    /// object is born in (F28 measured the difference -- starting inside
    /// the wait skipped canon's arming frame).
    pub fn new() -> Self {
        Self {
            decide: METTAUR_ROW, // canon: oAIState_Unk_00, cleared for a fresh object
            decide_sub: 0,
            latch: 0,
            wander_wait: 0,
            wait: 0,
            cur_action: METTAUR_ACT_DECIDE,
            hop_done: 0,
            param4: 0, // canon: oBattleObject_Param4, cleared for a fresh object
        }
    }

    /// True while the Mettaur is in one of canon's plain "wait N frames"
    /// states -- the spawn's one-time 0x1e pause (CurAction 0x09) or a
    /// losing wander roll's 0x32 wait (same countdown inside `sub_810A0EE`).
    /// The state oracle needs this because the entry lives here while the
    /// exported CurAction byte is built in `Actor::oracle_fields`.
    pub fn is_wait(&self) -> bool {
        self.cur_action == METTAUR_ACT_WAIT
            || (self.decide == METTAUR_WANDER && self.latch != 0)
    }

    /// The `off_8109050` Mettaur arm's think leg: `ForMettaur_8109EF4`
    /// through `sub_8109FD6`'s decision table. Reached through
    /// `enemy_think` (plan §2.3 step 2) into `Ai::update`; `blocked` is the
    /// occupancy of every other object, `rng` the battle's primary
    /// generator (FIXTURE.md's `rng` field, +58), shared the way the real
    /// ROM's single `ePrimaryRngSeed` is. Only the unreachable
    /// blind-wander arm draws from it.
    pub fn think(
        &mut self,
        me: &mut Actor,
        target: (i32, i32),
        blocked: u32,
        rng: &mut Rng,
    ) {
        // `sub_8109CBC` (asm31.s:170665-170672), the CurAction 9 waiter:
        // `sub r0,#1; strh; bge locret` -- EVERY frame it runs is a frame of
        // the wait, including the one whose stored value is 0; only the frame
        // that takes the counter to -1 calls `object_exitAttackState`, and
        // the decision loop is back the frame after that.
        if self.cur_action == METTAUR_ACT_WAIT {
            if self.wait > 0 {
                self.wait -= 1;
            } else {
                self.cur_action = METTAUR_ACT_DECIDE;
            }
            return;
        }
        // Every arm below either issues a move/attack that takes the actor's
        // one `CurAction` slot (matching the real machine, which dispatches
        // through the SAME slot: the decision loop only runs again once
        // CurAction has returned to 8) or is itself a pure wait, during
        // which the actor is never busy.
        if me.is_busy() {
            return;
        }
        match self.decide {
            METTAUR_ROW => {
                let (_, row) = me.panel();
                if self.param4 == 0 {
                    // `sub_810A004`'s own first branch (asm31.s:171296-171305):
                    // the very first time the decision loop runs for this
                    // object it writes 0x1e to BOTH Param4 and the waiter's
                    // Unk_10 and calls `object_setAttack0(9)`, then returns.
                    // THIS FRAME IS SPENT: the row compare below does not run
                    // on it and the waiter's own first tick is the next frame.
                    self.param4 = METTAUR_SPAWN_WAIT as u8; // canon: oBattleObject_Param4 = 0x1e
                    self.wait = METTAUR_SPAWN_WAIT; // canon: oAIAttackVars_Unk_10 = 0x1e
                    self.cur_action = METTAUR_ACT_WAIT;
                } else if BLIND_OR_CONFUSED {
                    // `sub_810A254`: GetPositiveSignedRNG() & 1 picks which
                    // neighbour row to try first (asm31.s:171478-171482),
                    // issued here as `sub_810A0D4` would arm it; Unk_02/Unk_03
                    // cleared as `sub_810A004`'s own `strh` does.
                    let delta = if rng.positive() & 1 == 0 { 1 } else { -1 };
                    self.hop_done = me.hop(0, delta, blocked) as u8;
                    self.decide = METTAUR_WANDER;
                    self.decide_sub = 0;
                    self.latch = 0;
                } else if row != target.1 {
                    // `sub_810A080`'s arming half: `sub_810A21A`'s own
                    // one-panel-toward-target rule, issued here.
                    self.hop_done = me.hop(0, (target.1 - row).signum(), blocked) as u8;
                    self.decide = METTAUR_ALIGN;
                } else {
                    self.decide = METTAUR_DECIDE;
                }
            }
            METTAUR_ALIGN => {
                // `sub_810A080`'s wait half (asm31.s:171314-171332):
                // `Unk_1a` nonzero (the hop committed) returns to state 0;
                // zero (the executor refused the move) goes to Decide.
                self.decide = if self.hop_done != 0 {
                    METTAUR_ROW
                } else {
                    METTAUR_DECIDE
                };
            }
            METTAUR_WANDER => {
                // `sub_810A0BA`: `Unk_02 == 0` is `sub_810A0D4` (its hop
                // was issued by the `RowCheck` arm above); the first
                // execution here advances to `sub_810A0EE`'s half.
                if self.decide_sub == 0 {
                    self.decide_sub = METTAUR_ROLL_SUB;
                }
                if self.latch == 0 {
                    // `sub_810A0EE`'s own roll (asm31.s:171405-171429):
                    // GetPositiveSignedRNG() & 0xf, < 2 (2/16) attacks now,
                    // else arms the 0x32 wait below.
                    self.latch = 1;
                    if rng.positive() & 0xf < 2 {
                        self.decide = METTAUR_DECIDE;
                        self.decide_sub = 0;
                    } else {
                        self.wander_wait = METTAUR_WANDER_WAIT;
                    }
                } else if self.wander_wait > 0 {
                    self.wander_wait -= 1;
                } else {
                    self.decide = METTAUR_ROW;
                    self.decide_sub = 0;
                }
            }
            METTAUR_DECIDE => {
                // `sub_810A126`'s normal path (asm31.s:171451-171475): the
                // `sub_800ED90` equipped-ability gate is never taken (no
                // equippable item), so the version tables' tag
                // (`byte_8109F40`) and damage (`byte_8109F28`, Version 0's
                // 10 matching `WAVE_DAMAGE`) ride into `object_setAttack0`
                // (0xb) -- the ATTACK executor, `SWING` in actor.rs with
                // its 0x40 swing and 0x28 recovery.
                me.attack(actor::SWING);
                self.decide = METTAUR_ROW;
                self.decide_sub = 0;
            }
            // `sub_810A204` (Unk_00 0x10): reachable only through `Decide`'s
            // own "special chip" branch, which this entry never takes (see
            // above). Re-enter `RowCheck` rather than stall.
            _ => {
                self.decide = METTAUR_ROW;
                self.decide_sub = 0;
            }
        }
    }
}
