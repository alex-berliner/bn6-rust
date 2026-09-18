//! Enemy behaviour.
//!
//! These are first passes on fixed timers, not the game's own planners:
//! Colonel's real one (sub_81013AA, asm31.s:153037) picks among five attacks
//! by where the player stands and how both HPs are doing, and ProtoMan's has
//! not been read at all. What each attack itself does is the game's.
//!
//! `Style::Mettaur` is the exception (AUDIT wave 3d ticket): the real
//! Mettaur's own per-frame dispatch is fully traced (reference/bn6f,
//! branch wt/mettaur-ai, the comment on `sub_8109FD6` in asm/asm31.s) and
//! ported as the per-type entry [`objects::MettaurEntry`] (T6,
//! `ForMettaur_8109EF4` with `sub_8109FD6`'s decision table and the
//! wait/hop/attack executors) rather than approximated with a flat timer.
//!
//! THE MACHINE, top to bottom (every address `asm/asm31.s`):
//!
//! - `ForMettaur_8109EF4` (170944-170974) is the per-object `CurAction`
//!   dispatch (13 entries, 0x00..0x0C): 0x00-0x07 are the shared spawn/idle
//!   plumbing every navi uses; 0x08 is `sub_8109FD6`, the Mettaur's OWN
//!   decision loop; 0x09 is a plain "wait N frames" state Unk_00 0x08's
//!   first-ever entry arms (see `MettaurEntry::think`); 0x0A is the HOP
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
//!   what the entry mirrors (see its own doc for the per-state trace).
//!
//! WHAT IS NOT REACHABLE, and how that was checked rather than assumed.
//! `RowCheck` gates on two object-flag tests before the row compare:
//! `OBJECT_FLAGS_IMMOBILIZED` (bit 14, freeze) and `OBJECT_FLAGS_BLIND |
//! OBJECT_FLAGS_CONFUSED` (bits 13/15, divert to `Wander`) --
//! include/structs/CollisionData.inc:16-18. T18 measured both gates' canonical
//! sites in the disassembly and they are exactly here: the bit-14
//! `mov r1,#1; lsl r1,#0xe; tst` gate is asm31.s:171385-171394 and the
//! `=0xa000` BLIND|CONFUSED gate is asm31.s:171395-171397 (per-bit setter/
//! reader walk in docs/inventory/statuses.json). This project has no chip that
//! sets any of the three, so both gates are always false; kept as a named,
//! always-false constant (`BLIND_OR_CONFUSED` in objects.rs) rather than
//! deleted, so `Wander`/`WaitOut` stay real, RNG-consuming code instead of
//! silently vanishing. Checked empirically, not just by grepping for a setter: a
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
use crate::objects::MettaurEntry;

/// Frames between decisions. ProtoMan's planner ticks about every 29 frames
/// and attacks once a counter fed 1-2 per tick reaches 4, so roughly 87
/// frames on average (sub_80FBA24, asm31.s:141641); that average stands in
/// for the counter. The others are placeholders. (Mettaur runs its own
/// entry instead -- see `MettaurEntry`.)
const MOVE_PAUSE: u16 = 29; // provenance: derived -- ProtoMan's planner tick, sub_80FBA24 asm31.s:141641
const ATTACK_PAUSE: u16 = 87; // provenance: derived -- ProtoMan's counter-of-4-at-1..2-per-tick average, sub_80FBA24 asm31.s:141641
const DIVIDE_PAUSE: u16 = 150; // provenance: fitted -- Colonel's real planner (five attacks, HP/position driven) is not reproduced; this is a placeholder pace, not read off its own counter

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
/// worktree's scratch dir, not committed -- docs/provenance.md#7aw / AUDIT pair on real
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
    /// T145: navi ActorType, AIIndex 0x17 (`ForGunner_8113078`'s slot --
    /// identity row `byte_80182C4[3*0x185]` = (0, navi, 0x17), ROM-read).
    /// Measured this ticket: the t1 ActorType fork is latched at spawn, so
    /// the per-frame brain this style services is the same shared think arm
    /// [`Style::Gunner`] services; the fork's live effect is re-keying the
    /// NameID-driven struct reads. Identity data in [`crate::navi`] -- see
    /// its module doc for the flip experiment.
    Navi,
    /// The real Mettaur's own 5-state, RNG-gated decision loop, ported as
    /// the per-type entry [`crate::objects::MettaurEntry`]. A first-version
    /// Mettaur never guards.
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
    /// Only meaningful for `Style::Mettaur`: the ported per-type entry
    /// (`ForMettaur_8109EF4` with its decision table and counters, in
    /// canon's own field layout -- see `MettaurEntry`).
    mettaur: MettaurEntry,
}

impl Ai {
    pub fn new(style: Style) -> Self {
        Self {
            style,
            pause: ATTACK_PAUSE,
            mettaur: MettaurEntry::new(),
        }
    }

    pub fn style(&self) -> &Style {
        &self.style
    }

    /// True while the Mettaur is in one of canon's plain "wait N frames"
    /// states (see `MettaurEntry::is_wait`). The state oracle (TODO R6)
    /// needs this because the entry lives here while the exported CurAction
    /// byte is built in `oracle_fields`.
    pub fn oracle_is_wait(&self) -> bool {
        self.mettaur.is_wait()
    }

    /// `blocked` is the occupancy of every other object, which no move may
    /// land on. `rng` is the battle's own primary generator (FIXTURE.md's
    /// `rng` field, +58), shared across every enemy the way the real ROM's
    /// single `ePrimaryRngSeed` is -- see `Rng`'s own doc. Only
    /// `Style::Mettaur` currently draws from it. The per-type think entry
    /// the dispatcher calls: reached through `objects::enemy_think` (plan
    /// §2.3 step 2, `battle_8108F74` into `RunAIAttack`, asm31.s:169314 /
    /// asm00_2.s:24781); the Mettaur arm is the `off_8109050` behavior entry
    /// `ForMettaur_8109EF4` (asm31.s:170982), ported as `MettaurEntry`
    /// in objects.rs.
    pub fn update(&mut self, me: &mut Actor, target: (i32, i32), blocked: u32, rng: &mut Rng) {
        if matches!(self.style, Style::Mettaur) {
            self.mettaur.think(me, target, blocked, rng);
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
            Style::Gunner | Style::Navi => {}
            Style::Mettaur => unreachable!("handled by the entry above"),
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
