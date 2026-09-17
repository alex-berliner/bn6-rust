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
//! Mechanism, measured on the real ROM (docs/worklog/T106.md):
//! the pwrAtk per-frame handler sub_8012EBC (asm00_2.s:9080-9152) counts
//! `oAIData_PwrAtkCurChargeTime` (include/structs/AIData.inc loc=0x1b) up
//! while the buster button is held, capping it at the buster's charge time
//! (DeterminePowerAttackChargeTime, asm00_2.s:9156 -- 100 frames for this
//! save, watched: the counter reads 100 from the 100th held frame). On the
//! released frame the player's t1 leg calls the dispatch (asm31.s:119118,
//! right before object_setAttack1): sub_80117A4 reads `oAIData_BPwrAtk`
//! (AIData.inc loc=0x7, copied from NaviStats+5 by sub_801390C,
//! asm00_2.s:10611-10613) and jumps through
//! ChargeShotHandlersByTransformation_80117D4 (asm00_2.s:5809-5963, 0x94
//! cells). The cell fills the AI attack vars (damage and the shot object the
//! spawner uses) and returns the attack's next id -- 0x27 for the Cannon
//! cell, 0x16 for the normal buster cell, 0x1d for the shared
//! megamanChargeShotBPwrAtk_init // unnamed: the per-cell return id's
//! consumer in the t1 leg.
//!
//! This is a ONE-CELL port: only the Cannon cell (shot_kind 0x06) is
//! implemented; the other cells return `None` and callers keep the plain
//! charged-buster behaviour. The engine has no buster-config source for
//! `BPwrAtk` yet, so the row's canon side pokes the byte (0x02034087, the
//! afterdissolve_0x0c state's player AIData) and this side selects the cell
//! with the constant below -- the pairing the buster_charge row documents.

/// Which cell of ChargeShotHandlersByTransformation_80117D4 the dispatch
/// walks. The engine's own default is the NORMAL charged buster -- the cell
/// the real ROM's default save runs (BPwrAtk peeked 0x01 at 0x02034087 on the
/// afterdissolve_0x0c state, T106) -- because there is no buster-config
/// source for shot kind yet; the buster_charge row pairs that with canon's
/// own 0x01. The ported Cannon arm (0x06) sits in `update` for the follow-up
/// tickets that add the shot-kind channel.
// canon: busterBugChargeShotDamageCalcHappensHere_8011A7E is cell 0x01 of
// ChargeShotHandlersByTransformation_80117D4
// provenance: off_80117D4 -- reference/bn6f/asm/asm00_2.s:5811
pub const SHOT_KIND_NORMAL: u8 = 0x01;

/// The ported cell: shot_kind 0x06, sub_8011BA2 (asm00_2.s:6173).
// canon: sub_8011BA2 is cell 0x06 of ChargeShotHandlersByTransformation_80117D4
// provenance: off_80117D4 -- reference/bn6f/asm/asm00_2.s:5816
pub const SHOT_KIND_CANNON: u8 = 0x06;

/// What a charge-shot cell hands the spawner: the fields sub_8011BA2 writes
/// into the AI attack vars. Field names follow include/constants' struct
/// (oAIAttackVars_*); the ones the original leaves at 0 on this path are not
/// modelled.
pub struct ChargeShotVars {
    /// oAIAttackVars_Damage.
    pub damage: u16,
    /// oAIAttackVars_Unk_0a // unnamed: a shot attribute the Cannon cell
    /// alone sets (0x94); the normal cell (busterBugChargeShotDamageCalc
    /// HappensHere_8011A7E, asm00_2.s:5988-6030) leaves it 0.
    pub attribute: u16,
    /// oAIAttackVars_Unk_0c // unnamed: the shot object id the cell hands
    /// the spawner -- NaviStats+0x4f on the normal cell, the constant 0x23c
    /// here (off_8011BCC, asm00_2.s:6194).
    pub object: u16,
}

/// The Cannon cell, sub_8011BA2 (reference/bn6f/asm/asm00_2.s:6173-6192):
/// damage = getBusterDamage() + 0x14 * min(getBusterDamage(), 5) -- via
/// sub_8012642 (asm00_2.s:7918-7930, r1 = 0x14 = 20, the min cap 5) -- with
/// the shot attribute 0x94 and the shot object 0x23c. `buster_damage` is
/// this build's BUSTER_DAMAGE (the getBusterDamage stand-in, sub_801265A,
/// asm00_2.s:7908: Attack + 1). `hold_timer` is the release-time value of
/// oAIData_PwrAtkCurChargeTime; the cell itself does not read it (the FULL
/// charge gate happened earlier, in the caller), it is carried so the
/// dispatch signature matches the ticket's arm.
pub fn update(shot_kind: u8, hold_timer: u16, buster_damage: u16) -> Option<ChargeShotVars> {
    let _ = hold_timer;
    match shot_kind {
        // The normal charged buster, cell 0x01
        // (busterBugChargeShotDamageCalcHappensHere_8011A7E, asm00_2.s:5988-6030):
        // damage = (Attack + 1) * 10 -- our buster_damage IS Attack + 1
        // (sub_801265A, asm00_2.s:7908) -- attribute 0, the shot object from
        // NaviStats+0x4f (modelled by the caller's plain buster bolt).
        SHOT_KIND_NORMAL => Some(ChargeShotVars {
            damage: buster_damage * 10,
            attribute: 0,
            object: 0, // unnamed: NaviStats+0x4f, not modelled
        }),
        SHOT_KIND_CANNON => {
            // provenance: derived -- sub_8011BA2 asm00_2.s:6175-6177 (0x1e/0x14
            // into sub_8012642) and sub_8012642's mul/add (asm00_2.s:7928-7929)
            const CANNON_CHARGE_MULT: u16 = 0x14;
            const CANNON_CHARGE_CAP: u16 = 5;
            let boost = buster_damage.min(CANNON_CHARGE_CAP);
            Some(ChargeShotVars {
                damage: buster_damage + CANNON_CHARGE_MULT * boost,
                attribute: 0x94,  // provenance: derived -- sub_8011BA2, asm00_2.s:6179
                object: 0x23c,    // provenance: derived -- off_8011BCC, asm00_2.s:6194
            })
        }
        // The other 0x93 cells are unported (T106 ports one; the other seven
        // of the 0x06..0x0D run are the next tickets').
        _ => None,
    }
}
