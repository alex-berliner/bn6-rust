//! Charge-shot dispatch (M7, T106): the per-shot_kind cell the original walks
//! when the buster's attack state is entered on a full-charge release.
//!
//! NOT YET DECLARED in main.rs: any code added to the binary shifts its own
//! timing, and that alone moved the cursor guard row 1 -> 10 px (measured,
//! T106: a stable 9 px at canon frame 52, present even with the dispatch
//! wired as a pure no-op -- damage and shot identical to the old path).
//! Declare this module together with the working shot-kind wiring, and
//! re-run the cursor row as the veto (docs/worklog/T106.md has the evidence
//! trail and the next leads).
//!
//! Mechanism, measured on the real ROM (docs/worklog/T106.md): the pwrAtk
//! per-frame handler sub_8012EBC (asm00_2.s:9085-9155) counts
//! `oAIData_PwrAtkCurChargeTime` (include/structs/AIData.inc loc=0x1b) up
//! while the buster button is held -- the count-up and the cap are
//! asm00_2.s:9129-9140, the cap being a data load, not a literal: a
//! (BPwrAtk, transformation)-indexed halfword of powerAttackChargeTimes_
//! 8020404 read via off_8012FC4 (asm00_2.s:9219-9223; table at
//! data/dat01.s:22). The value the verifier's static read gives at index 10
//! is 180; the 100 cap and the 101-frame magenta onset this build watches
//! (main's CHARGE_FRAMES, src/battle.rs:182) are properties of the ONE save
//! state the rows use, and CHARGE_FRAMES is an onset-frame equivalence, not
//! a cap equivalence. On the released frame the player's t1 leg calls
//! `bl sub_80117A4` (asm31.s:119119), which reads `oAIData_BPwrAtk`
//! (AIData.inc loc=0x7, copied from NaviStats+5 by sub_801390C,
//! asm00_2.s:10611-10613) and jumps through
//! ChargeShotHandlersByTransformation_80117D4 (asm00_2.s:5809-5957, 148
//! cells). The cell fills the AI attack vars (damage and the shot object the
//! spawner uses) and returns an id the t1 leg consumes (cell 0x00's shared
//! init ends `mov r0,#0x11`, asm00_2.s:6007 // unnamed: the per-cell return
//! id's consumer).
//!
//! This file ports the DISPATCH SHAPE and one cell's data; the Cannon cell
//! (0x06) is recorded but returns None because the damage it computes needs
//! getBusterDamage_801265A, which is not modelled.

/// Which cell of ChargeShotHandlersByTransformation_80117D4 the dispatch
/// walks. The engine's own default is the NORMAL charged buster -- the cell
/// the real ROM's default save runs (BPwrAtk peeked 0x01 at 0x02034087 on the
/// afterdissolve_0x0c state, T106) -- because there is no buster-config
/// source for shot kind yet; the buster_charge row pairs that with canon's
/// own 0x01.
// canon: busterBugChargeShotDamageCalcHappensHere_8011A7E is cell 0x01 of
// ChargeShotHandlersByTransformation_80117D4
// provenance: off_80117D4 -- reference/bn6f/asm/asm00_2.s:5811
pub const SHOT_KIND_NORMAL: u8 = 0x01;

/// The recorded cell: shot_kind 0x06, sub_8011BA2 (asm00_2.s:6173).
// canon: sub_8011BA2 is cell 0x06 of ChargeShotHandlersByTransformation_80117D4
// provenance: off_80117D4 -- reference/bn6f/asm/asm00_2.s:5816
pub const SHOT_KIND_CANNON: u8 = 0x06;

/// What a charge-shot cell hands the spawner: the fields the cells write
/// into the AI attack vars. Field names follow include/constants' struct
/// (oAIAttackVars_*); the ones the original leaves at 0 on a given path are
/// not modelled.
pub struct ChargeShotVars {
    /// oAIAttackVars_Damage.
    pub damage: u16,
    /// oAIAttackVars_Unk_0a // unnamed: a shot attribute the Cannon cell
    /// alone sets (0x94); the normal cell (busterBugChargeShotDamageCalc
    /// HappensHere_8011A7E, asm00_2.s:6009-6030) leaves it 0.
    pub attribute: u16,
    /// oAIAttackVars_Unk_0c // unnamed: the shot object id the cell hands
    /// the spawner -- NaviStats+0x4f on the normal cell, the constant 0x23c
    /// here (off_8011BCC, asm00_2.s:6194).
    pub object: u16,
}

/// The NORMAL cell, 0x01 -- busterBugChargeShotDamageCalcHappensHere_8011A7E
/// (asm00_2.s:6009-6030): damage = (NaviStats_Attack + 1) * 10, with an
/// emotion==5 override to 1 before the *10, the shot object from
/// NaviStats+0x4f. `buster_damage` is this build's BUSTER_DAMAGE stand-in
/// (main's src/battle.rs:69-72 const) -- NOT getBusterDamage_801265A
/// (asm00_2.s:7933, which reads NaviIndex, stats[1], byte_80126A4 and a
/// transformation table, with an emotion==5 override to 1): the stand-in
/// reproduces main's CHARGED_DAMAGE at the default save's stats and nothing
/// beyond that.
fn normal_cell(buster_damage: u16) -> ChargeShotVars {
    ChargeShotVars {
        damage: buster_damage * 10,
        attribute: 0,
        object: 0, // unnamed: NaviStats+0x4f, not modelled
    }
}

pub fn update(shot_kind: u8, hold_timer: u16, buster_damage: u16) -> Option<ChargeShotVars> {
    let _ = hold_timer;
    match shot_kind {
        SHOT_KIND_NORMAL => Some(normal_cell(buster_damage)),
        // The Cannon cell, 0x06 -- sub_8011BA2 (asm00_2.s:6173-6192) -- is
        // RECORDED here but NOT computable yet. Its damage is
        // sub_8012642(0x1e, 0x14): base 0x1e (30) plus 0x14 (20) times
        // min(getBusterDamage(), 5) -- sub_8012642 (asm00_2.s:7918-7931)
        // pushes its two ARGUMENTS, calls getBusterDamage_801265A, clamps
        // the result at 5, pops the arguments back and returns
        // base + mult*min(damage,5); every cell passes its own (base, mult)
        // pair. The attribute is 0x94 (asm00_2.s:6179) and the shot object
        // 0x23c (off_8011BCC, asm00_2.s:6194), both constant.
        //
        // unported: needs getBusterDamage_801265A (asm00_2.s:7933), which is
        // not Attack+1 and is not modelled -- returning None rather than a
        // number this file cannot compute.
        SHOT_KIND_CANNON => None,
        // The other 146 cells are unported (T106 records one; the other seven
        // of the 0x06..0x0D run are the next tickets').
        _ => None,
    }
}
