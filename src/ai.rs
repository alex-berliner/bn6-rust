//! Enemy behaviour.
//!
//! These are first passes on fixed timers, not the game's own planners:
//! Colonel's real one (sub_81013AA, asm31.s:153037) picks among five attacks
//! by where the player stands and how both HPs are doing, and ProtoMan's has
//! not been read at all. What each attack itself does is the game's.
//!
//! `Style::Mettaur` is the exception (AUDIT wave 3d ticket): the real
//! Mettaur's own per-frame dispatch is fully traced now (reference/bn6f,
//! branch wt/mettaur-ai, the comment on `sub_8109FD6` in asm/asm31.s) and
//! reimplemented in [`MettaurState`] below rather than approximated with a
//! flat timer.
//!
//! THE MACHINE, top to bottom (every address `asm/asm31.s`):
//!
//! - `ForMettaur_8109EF4` (170944-170974) is the per-object `CurAction`
//!   dispatch (13 entries, 0x00..0x0C): 0x00-0x07 are the shared spawn/idle
//!   plumbing every navi uses; 0x08 is `sub_8109FD6`, the Mettaur's OWN
//!   decision loop; 0x09 is a plain "wait N frames" state Unk_00 0x08's
//!   first-ever entry arms (see `MettaurState::Spawn`); 0x0A is the HOP
//!   executor (`sub_8109CE6`/`off_8109CF8`, 170650-170757, four raw-byte-
//!   indexed sub-steps: reserve the target panel + spawn a dust effect
//!   [`spawn_t1_0x0_EffectObject`, NOT modelled here] for 3 frames, commit
//!   the panel for 3 more, clear the moving flag and arm the per-version
//!   cooldown `byte_8109F46[Version]` for that many frames, then exit);
//!   0x0B is the ATTACK executor (`sub_8109DD2`/`off_8109DE4`, 170775-
//!   170867: the 0x40-frame swing pose with the shockwave spawned
//!   [`sub_80C6CE4`] when its own countdown reads 0x1b, THEN a separate
//!   0x28 (40) frame recovery, `sub_8109E4A` -- see `actor::SWING`'s own
//!   doc, this recovery was missing entirely before this ticket); 0x0C is
//!   the GUARD executor (`sub_8109E7A`/`off_8109E8C`, 170869-170941, only
//!   ever entered from the decision loop's `Version != 0` "being hit"
//!   branch in `sub_810A004` -- NOT modelled, this project's Mettaur is
//!   always `Version` 0, "a first-version Mettaur never guards").
//! - `sub_8109FD6`'s own 5-state table, `off_8109FF0` (171106-171126), is
//!   what `MettaurState` mirrors: `RowCheck` (`sub_810A004`, 171129-171196),
//!   `AlignHop`/`Wander` (`sub_810A080`/`sub_810A0BA`, 171199-171301, one
//!   table split two ways by `oAIState_Unk_02`), `Decide` (`sub_810A126`,
//!   171304-171376). A 5th state, `sub_810A204` (171426-171439), is reached
//!   only through `Decide`'s own "special chip" branch (`sub_800ED90`'s
//!   equipped-ability gate) -- NOT modelled, see `MettaurState::Decide`'s
//!   own doc.
//!
//! WHAT IS NOT REACHABLE, and how that was checked rather than assumed.
//! `RowCheck` gates on two object-flag tests before the row compare:
//! `OBJECT_FLAGS_IMMOBILIZED` (bit 14, freeze) and `OBJECT_FLAGS_BLIND |
//! OBJECT_FLAGS_CONFUSED` (bits 13/15, divert to `Wander`) --
//! include/structs/CollisionData.inc:16-18. This project has no chip that
//! sets any of the three, so both gates are always false; kept as a named,
//! always-false constant (`BLIND_OR_CONFUSED`) rather than deleted, so
//! `Wander`/`WaitOut` stay real, RNG-consuming code instead of silently
//! vanishing. Checked empirically, not just by grepping for a setter: a
//! `--watch 0x020013f0:4` (ePrimaryRngSeed) capture over 220 frames from
//! /tmp/pausedwithcannon.state, the exact STERILE+PAUSED+ALIVE+Start@10
//! recipe both the `mettaur` and `wave` harness rows use, shows the primary
//! RNG advancing by EXACTLY one step every single rendered frame start to
//! finish (219/219 consecutive transitions match [`Rng::next`]'s own
//! formula bit-for-bit) -- if the Mettaur's own `Wander` roll had fired even
//! once in that window, some frame would show TWO steps instead of one. It
//! never does, in either fixture, over the full window both checks measure
//! from. See [`Rng`]'s own doc for the per-frame advance this confirms and
//! does not (yet) trace to a caller.

use crate::actor::{self, Actor};
use crate::field;

/// Frames between decisions. ProtoMan's planner ticks about every 29 frames
/// and attacks once a counter fed 1-2 per tick reaches 4, so roughly 87
/// frames on average (sub_80FBA24, asm31.s:141641); that average stands in
/// for the counter. The others are placeholders. (Mettaur no longer uses
/// this generic pause -- see `MettaurState`.)
const MOVE_PAUSE: u16 = 29; // provenance: derived -- ProtoMan's planner tick, sub_80FBA24 asm31.s:141641
const ATTACK_PAUSE: u16 = 87; // provenance: derived -- ProtoMan's counter-of-4-at-1..2-per-tick average, sub_80FBA24 asm31.s:141641
const DIVIDE_PAUSE: u16 = 150; // provenance: fitted -- Colonel's real planner (five attacks, HP/position driven) is not reproduced; this is a placeholder pace, not read off its own counter

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
/// takes it to -1. [`Ai::update_mettaur`] counts the same 31 frames; it
/// consumed 30 before F28 (its `ticks == 0` frame fell straight through into
/// `RowCheck` instead of being the waiter's own last frame).
const SPAWN_FRAMES: u16 = 0x1e; // provenance: derived -- sub_810A004, asm31.s:171296-171305

/// This project has no chip that sets `OBJECT_FLAGS_BLIND`,
/// `OBJECT_FLAGS_CONFUSED` or `OBJECT_FLAGS_IMMOBILIZED` yet (grepped every
/// `src/*.rs` chip effect; none exists) -- see the module doc's RNG
/// verification note for the empirical check that this branch never fires
/// in the fixtures this project measures. Named rather than inlined so a
/// future status-effect chip has one place to flip it live.
const BLIND_OR_CONFUSED: bool = false; // provenance: derived -- no chip in this project sets OBJECT_FLAGS_BLIND/CONFUSED/IMMOBILIZED (0xa000/0x4000) yet, include/structs/CollisionData.inc:16-18

/// The primary generator (`GetRNG`/`GetPositiveSignedRNG`,
/// reference/bn6f/asm/asm00_0.s:2610/2626; state `ePrimaryRngSeed`, EWRAM
/// 0x020013f0, ewram.s:262): rotate the 32-bit state left one, add one, xor
/// a fixed constant. This is the SAME rotate-based formula as `deck::Rng`
/// (the SECONDARY generator, `eSecondaryRngSeed`) -- a separate stream with
/// its own state, not shared hardware -- duplicated here rather than
/// imported because this ticket's file ownership (AUDIT wave 3d) is ai.rs/
/// actor.rs/field.rs/spr.rs/shot.rs/emotion.rs/fixture.rs; deck.rs and
/// main.rs (which constructs `deck::Rng`) belong to the parallel agent.
///
/// VERIFIED against the real ROM (this ticket, standalone script in the
/// worktree's scratch dir, not committed -- TRANSFER.md/AUDIT pair on real
/// ROM assets applies): `--watch 0x020013f0:4` over 220 frames from
/// /tmp/pausedwithcannon.state (STERILE+PAUSED+ALIVE, Start@10) gives a
/// sequence where EVERY one of 219 consecutive transitions equals
/// `Rng::next`'s own formula applied to the previous value, bit for bit --
/// zero mismatches. Frame 0 of that same capture reads 0xdd340be4, which is
/// `fixture.rs`'s `rng` value for the `mettaur`/`wave` rows (see its own
/// descriptor-table comment for where that number is used).
///
/// The per-frame advance itself is real but its CALLER was not pinned down:
/// every `bl GetRNG`/`bl GetPositiveSignedRNG` site in asm31.s/asm00_2.s/etc
/// was grepped, and none is an obviously-unconditional once-a-frame tick
/// (most are inside specific effects like `AddRandomVarianceToTwoCoords` or
/// weighted-pick helpers that plainly do not run every frame regardless of
/// state). Reported honestly rather than guessed at, AUDIT pair 15 -- the
/// FORMULA and its per-frame CADENCE are both directly measured facts
/// either way, which is what this project's own `rng` field needs to stay
/// in lockstep with the real ROM.
pub struct Rng(u32);

impl Rng {
    pub fn new(seed: u32) -> Self {
        Self(seed)
    }

    /// The current state, for the state oracle's export block (TODO R6):
    /// canon's `ePrimaryRngSeed` (EWRAM 0x020013f0) is read directly by a
    /// `--watch`, so the export carries ours raw.
    pub fn state(&self) -> u32 {
        self.0
    }

    /// GetRNG: `seed = rotl(seed, 1).wrapping_add(1) ^ 0x873ca9e5`.
    pub fn next(&mut self) -> u32 {
        // provenance: derived -- GetRNG, asm00_0.s:2610-2622 (xor constant rng_80015A0 = 0x873ca9e5)
        self.0 = self.0.rotate_left(1).wrapping_add(1) ^ 0x873c_a9e5;
        self.0
    }

    /// GetPositiveSignedRNG: the same step with the sign bit cleared.
    pub fn positive(&mut self) -> u32 {
        // provenance: derived -- GetPositiveSignedRNG, asm00_0.s:2625-2640 (`lsl r0,r0,#1; lsr r0,r0,#1`)
        self.next() & 0x7fff_ffff
    }
}

/// `SeedRNG`'s own fixed constant (asm00_0.s:2600-2606). Real hardware has
/// no single canonical "battle start" RNG value -- a save file's own
/// accumulated pre-battle RNG state depends on everything played before it
/// -- so this is this project's own chosen default for FIXTURE.md's `rng`
/// field ("+58 ... 0 = our default seed") rather than a ROM fact about battle
/// starts specifically; it is at least the value the ROM itself seeds a
/// fresh RNG stream with.
pub const DEFAULT_SEED: u32 = 0xa338_244f; // provenance: derived -- SeedRNG, asm00_0.s:2600-2606

/// `sub_8109FD6`'s own decision state, `off_8109FF0`'s 5-entry table -- see
/// the module doc for the full trace. `Spawn` is the one CurAction the enum
/// carries that is not one of those five: the CurAction 9 waiter
/// (`sub_8109CBC`) the post-spawn pause runs in, which the real machine
/// reaches by leaving `Unk_00` on state 0 and switching the object's
/// CurAction instead. Its GATE, canon's `oBattleObject_Param4`, is a real
/// separate byte and is modelled as one on [`Ai`] -- folding it into this
/// enum is what cost F28's arming frame.
#[derive(Clone, Copy)]
enum MettaurState {
    /// Real: `oBattleObject_Param4 == 0`'s branch in `sub_810A004`. See
    /// `SPAWN_FRAMES`.
    Spawn(u16),
    /// off_8109FF0[0], `sub_810A004` (asm31.s:171129-171196): compare this
    /// Mettaur's own row against the target's (this project's own
    /// `target.1`, standing in for `sub_80103F8`'s returned object's
    /// `+0x13`) and branch. The two status-flag gates that run first in the
    /// real function are `BLIND_OR_CONFUSED` below (see the module doc).
    RowCheck,
    /// off_8109FF0[1]/off_810A0CC[0], `sub_810A080` (asm31.s:171199-171233):
    /// a hop toward the target's row has been issued (`sub_810A21A`'s own
    /// one-panel-toward-target rule); wait for `Actor` to finish it, then
    /// re-run `RowCheck` (matching `sub_810A080`'s own `loc_810A0B0`, which
    /// always returns to state 0 once the hop's `Unk_1a` "done" flag reads
    /// nonzero -- the "still hopping" half of that branch, `Unk_1a == 0`,
    /// is not reachable in a single-threaded per-frame model like this
    /// one's, since nothing re-enters this arm before `Actor::is_busy`
    /// clears).
    AlignHop,
    /// off_8109FF0[2]/off_810A0CC[0], `sub_810A0D4` (asm31.s:171252-171267):
    /// UNREACHABLE without `BLIND_OR_CONFUSED` -- see the module doc. A
    /// random-direction hop (`sub_810A254`'s own `GetPositiveSignedRNG() &
    /// 1` pick) has been issued or refused by `Actor::hop`; wait for it,
    /// then roll in the `Wander` arm below. This project does not model
    /// `sub_810A254`'s own retry-the-other-direction fallback (the real
    /// table `dword_810A2A4` tries up to 2-3 candidates); a refused hop here
    /// simply does not move, which is unmeasurable while this state cannot
    /// be reached at all.
    Wander,
    /// off_8109FF0[2]/off_810A0CC[1], `sub_810A0EE` (asm31.s:171270-171301):
    /// UNREACHABLE without `BLIND_OR_CONFUSED`. `ticks` counts the 0x32 (50)
    /// frame idle wait a losing roll (14/16, `GetPositiveSignedRNG() & 0xf
    /// >= 2`) arms; a winning roll (2/16) skips straight to `Decide`.
    WaitOut(u16),
    /// off_8109FF0[3], `sub_810A126` (asm31.s:171304-171376): rows equal,
    /// attack. The "special chip" branch (`sub_800ED90`'s own equipped-
    /// ability gate, which would set `Unk_00` to off_8109FF0[4]/
    /// `sub_810A204` instead) is NOT modelled: this project's Mettaur
    /// (`enemy_kind` 0, `AIData.Version` 0, no equippable item) never takes
    /// it in any capture this ticket checked.
    Decide,
}

#[derive(Clone, Copy)]
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
    /// The real Mettaur's own 5-state, RNG-gated decision loop -- see the
    /// module doc and [`MettaurState`]. A first-version Mettaur never
    /// guards.
    Mettaur,
}

/// The 0xA slash's base panel for the enemy side is (2,2) (dword_8103A04,
/// asm31.s:158121), and one of four offset shapes is laid over it by where
/// the player stands (byte_8103990, asm31.s:158062; lists at
/// asm00_2.s:20990-21025). Which shape the game picks for which position is
/// not fully read, so the first shape covering the player is used, and the
/// last, the 3x3 block without its side centres, when none does.
pub const CROSS_BASE: (i32, i32) = (2, 2); // provenance: derived -- dword_8103A04, asm31.s:158121
// provenance: derived -- the four offset shapes themselves are byte_8103990's
// own tables (asm31.s:158062, listed at asm00_2.s:20990-21025); WHICH shape
// the game picks for a given player position is not fully read (see
// `cross_targets`'s own doc below, "fitted": first-match-wins is a stand-in
// for that unread selection rule, not itself derived).
const CROSS_SHAPES: [&[(i32, i32)]; 4] = [
    &[(0, 0), (1, -1), (-1, 1)],
    &[(0, 0), (-1, -1), (1, 1)],
    &[(0, 0), (-1, -1), (-1, 1)],
    &[(0, 0), (-1, -1), (1, -1), (-1, 1), (1, 1), (0, -1), (0, 1)],
];

/// The panels the cross slash will hit for a player at `target`, or None if
/// the player is out of its reach and the overhead slash should be used.
/// provenance: fitted -- the selection rule (first shape covering the
/// player, last shape as fallback) is a stand-in for the game's own unread
/// per-position table; see `CROSS_SHAPES`'s own doc.
pub fn cross_targets(target: (i32, i32)) -> Option<&'static [(i32, i32)]> {
    let rel = (target.0 - CROSS_BASE.0, target.1 - CROSS_BASE.1);
    CROSS_SHAPES.iter().copied().find(|s| s.contains(&rel))
}

pub struct Ai {
    style: Style,
    pause: u16,
    /// Only meaningful for `Style::Mettaur` -- see `MettaurState`.
    mettaur: MettaurState,
    /// canon: `oBattleObject_Param4` -- 0 until the one-time post-spawn wait
    /// has been armed, `SPAWN_FRAMES` for the rest of the battle
    /// (`sub_810A004`, asm31.s:171296-171305, which writes the SAME 0x1e to
    /// Param4 and to the waiter's `oAIAttackVars_Unk_10`). Modelled as its
    /// own field, not folded into `MettaurState`, because canon spends a
    /// whole decision-loop frame ARMING the wait -- `RowCheck` runs, stores
    /// Param4/Unk_10 and calls `object_setAttack0(9)`, and the waiter's
    /// first tick is the NEXT frame. See `update_mettaur`.
    param4: u8,
}

impl Ai {
    pub fn new(style: Style) -> Self {
        Self {
            style,
            pause: ATTACK_PAUSE,
            // canon starts in the decision loop's state 0 with Param4 == 0:
            // the wait is armed BY `RowCheck`'s own first run, it is not the
            // state the object is born in. F28 measured the difference --
            // starting inside the wait skipped canon's arming frame.
            mettaur: MettaurState::RowCheck,
            param4: 0, // canon: oBattleObject_Param4, cleared for a fresh object
        }
    }

    pub fn style(&self) -> &Style {
        &self.style
    }

    /// True while the Mettaur is in one of canon's plain "wait N frames"
    /// states -- the spawn's one-time 0x1e pause (`CurAction` 0x09,
    /// `sub_8109CBC`, asm31.s:170990; armed by `sub_810A004`'s Param4
    /// branch) or a losing wander roll's 0x32 wait (same executor). The
    /// state oracle (TODO R6) needs this because `MettaurState` lives here
    /// while the exported CurAction byte is built in `oracle_fields`.
    pub fn oracle_is_wait(&self) -> bool {
        matches!(
            self.mettaur,
            MettaurState::Spawn(_) | MettaurState::WaitOut(_)
        )
    }

    /// `blocked` is the occupancy of every other object, which no move may
    /// land on. `rng` is the battle's own primary generator (FIXTURE.md's
    /// `rng` field, +58), shared across every enemy the way the real ROM's
    /// single `ePrimaryRngSeed` is -- see `Rng`'s own doc. Only
    /// `Style::Mettaur` currently draws from it. The per-type think entry
    /// the dispatcher calls: reached through `objects::enemy_think` (plan
    /// §2.3 step 2, `battle_8108F74` into `RunAIAttack`, asm31.s:169314 /
    /// asm00_2.s:24781); the Mettaur arm is the `off_8109050` behavior entry
    /// `ForMettaur_8109EF4` (asm31.s:170982), ported as `MettaurState`.
    pub fn update(&mut self, me: &mut Actor, target: (i32, i32), blocked: u32, rng: &mut Rng) {
        if matches!(self.style, Style::Mettaur) {
            self.update_mettaur(me, target, blocked, rng);
            return;
        }
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
            Style::Mettaur => unreachable!("handled by update_mettaur above"),
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

    /// The real Mettaur's own decision loop -- see the module doc and
    /// [`MettaurState`] for the disassembly this mirrors. `MettaurState` is
    /// `Copy`, so this follows `Actor::update`'s own `self.x = match self.x
    /// { .. }` idiom rather than matching a mutable borrow in place.
    fn update_mettaur(&mut self, me: &mut Actor, target: (i32, i32), blocked: u32, rng: &mut Rng) {
        // `sub_8109CBC` (asm31.s:170665-170672), the CurAction 9 waiter:
        // `sub r0,#1; strh; bge locret` -- EVERY frame it runs is a frame of
        // the wait, including the one whose stored value is 0; only the frame
        // that takes the counter to -1 calls `object_exitAttackState`, and
        // the decision loop is back the frame after that. So the arm of 0x1e
        // is 31 frames, and `RowCheck` does NOT share the last of them.
        if let MettaurState::Spawn(ticks) = self.mettaur {
            self.mettaur = if ticks > 0 {
                MettaurState::Spawn(ticks - 1)
            } else {
                MettaurState::RowCheck
            };
            return;
        }
        // Every non-Spawn state below either issues a move/attack that takes
        // the actor's one `CurAction` slot (matching the real machine, which
        // dispatches through the SAME slot: this decision loop only runs
        // again once CurAction has returned to 8) or is itself a pure wait
        // (`WaitOut`) during which the actor is never busy.
        if me.is_busy() {
            return;
        }
        self.mettaur = match self.mettaur {
            MettaurState::Spawn(_) => unreachable!("consumed above"),
            MettaurState::RowCheck => {
                let (_, row) = me.panel();
                if self.param4 == 0 {
                    // `sub_810A004`'s own first branch (asm31.s:171296-171305):
                    // the very first time the decision loop runs for this
                    // object it writes 0x1e to BOTH Param4 and the waiter's
                    // Unk_10 and calls `object_setAttack0(9)`, then returns.
                    // THIS FRAME IS SPENT: the row compare below does not run
                    // on it and the waiter's own first tick is the next frame.
                    self.param4 = SPAWN_FRAMES as u8; // canon: oBattleObject_Param4 = 0x1e
                    MettaurState::Spawn(SPAWN_FRAMES)
                } else if BLIND_OR_CONFUSED {
                    // sub_810A254: GetPositiveSignedRNG() & 1 picks which
                    // neighbour row to try first (asm31.s:171478-171482).
                    let delta = if rng.positive() & 1 == 0 { 1 } else { -1 };
                    me.hop(0, delta, blocked);
                    MettaurState::Wander
                } else if row != target.1 {
                    me.hop(0, (target.1 - row).signum(), blocked);
                    MettaurState::AlignHop
                } else {
                    MettaurState::Decide
                }
            }
            MettaurState::AlignHop => MettaurState::RowCheck,
            MettaurState::Wander => {
                // sub_810A0EE's own roll (asm31.s:171270-171294):
                // GetPositiveSignedRNG() & 0xf, < 2 (2/16) attacks now, else
                // arms the 0x32 (50) frame wait below.
                if rng.positive() & 0xf < 2 {
                    MettaurState::Decide
                } else {
                    MettaurState::WaitOut(0x32)
                }
            }
            MettaurState::WaitOut(ticks) if ticks > 0 => MettaurState::WaitOut(ticks - 1),
            MettaurState::WaitOut(_) => MettaurState::RowCheck,
            MettaurState::Decide => {
                me.attack(actor::SWING);
                MettaurState::RowCheck
            }
        };
    }
}
