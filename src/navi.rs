//! Enemy navi identity, ported as ROM data (ticket T145).
//!
//! M6's first navi slot is AIIndex 0x17, the second slot the ROM tables
//! name (`ForGunner_8113078`; T134's pick was 0x01, `ForMettaur_8109EF4`).
//! The identity row is measured, not inferred: `byte_80182C4[3*0x185]`
//! reads (version 0, ActorType 1 navi, AIIndex 0x17), so enemy_idx 0x185
//! spawns this slot (GetVerActorTyAndAIIdx_80182B4, asm00_2.s:19965-19974).
//!
//! THE FORK IS LATCHED, NOT PER-FRAME (measured this ticket, canon side).
//! `t1_0x0_80B81EC` (asm31.s:15-35) dispatches on `oAIData_ActorType`
//! (AIData+0x0) into the virus / navi / player arms, but a live flip of the
//! byte -- poke-at of AIData 0x02034280 0x1700 -> 0x1701 (ActorType 0 -> 1,
//! AIIndex 0x17 already there) plus NameID -> 0x0185 on the Gunner object
//! the battlestart_gunner state spawns at capture frame 69 -- holds its
//! values through frame 110, changes nothing else, and does not crash, so
//! the dispatcher is chosen once at spawn. Both per-frame dispatchers are
//! UNBOUNDED CurState-indexed `bx` tables (virus
//! `virusObject_dispatch_8108F50`, asm31.s:169291-169301; navi
//! `naviObject_dispatch_80F2330`, asm31.s:123304-123312); a live-flipped
//! object that kept its virus CurState 4 and really took the navi arm would
//! read the word at 0x080F2358 (mid-instruction bytes of `sub_80F2354`,
//! 0x00847801 shape) and crash. Neither happens: the flip is inert for
//! behaviour and only re-keys the NameID-driven struct reads.
//!
//! The four tables the ticket names are the VIRUS family's consumption set
//! -- think/Struct1/Struct2/act at 0x8109050/0x81090D0/0x8109150/0x81091D0
//! (asm/asm31.s:169448/169513/169578/169643, 32 words each, laid back to
//! back and bounded by off_8109250, NOT 25; the ticket's asm00_2.s cite is
//! a comment-only mention there). A navi ActorType spawn reads the NAVI
//! struct columns instead (enemy_getStruct1/2 pick the table by actor type
//! through off_800F230/off_800F260, asm00_2.s:647-720:
//! `NaviEnemyStruct1Ptrs_80F24D8` / `NaviEnemyStruct2Ptrs_80F253C`), and
//! its CurState-1 leg is `sub_80F2354` over the four 0x80F2xxx tables. Both
//! sets' slot-0x17 rows are ported below; the think/act arms are the shared
//! per-AIIndex arms (the same words serve the Gunner virus, enemy_idx
//! 0x85, whose live AIData in this very scenario reads 0x1700).

/// The four parallel 32-word tables, word-for-word from the ROM this
/// session. Index = AIIndex * 4 (asm31.s:169404-169423, the
/// `battle_8108F74`/`battle_801B1C4` reader pair).
pub const THINK_TABLES: [u32; 32] = [
    // AIThinkTables_8109050, asm31.s:169448-169479. A think word is a
    // pointer to that AI's CurAction-indexed handler table, handed to
    // battle_801B1C4 -- not a routine. Slot 0x01 = ForMettaur_8109EF4
    // (T134's slot), slot 0x17 = ForGunner_8113078 (this ticket's).
    0x08109b74, 0x08109ef4, 0x0810a550, 0x0810a9ec,
    0x0810b2d0, 0x0810bb94, 0x0810c170, 0x0810c6f0,
    0x0810cd60, 0x0810d0f4, 0x0810d554, 0x0810d910,
    0x0810e120, 0x0810e7b0, 0x0810f010, 0x0810f39c,
    0x0810fce0, 0x081104d4, 0x08110dc0, 0x08111330,
    0x08111dc0, 0x081121f0, 0x081129a0, 0x08113078,
    0x081135cc, 0x08113d50, 0x08114710, 0x081154f0,
    0x08115950, 0x08115de0, 0x081163f0, 0x081166b0,
]; // provenance: derived -- ROM read 2026-09-17 (T145), asm31.s:169448
pub const STRUCT1_VIRUS_PTRS: [u32; 32] = [
    // AIEnemyStruct1Ptrs_81090D0, asm31.s:169513-169544. Consumed through
    // enemy_getStruct1 only for ActorType 0 (virus column of
    // off_800F230, asm00_2.s:662-666). Slot 0x17 = GunnerEnemyStruct1_8112B94.
    0x08109a78, 0x08109bd0, 0x0810a2c0, 0x0810a840,
    0x0810ae44, 0x0810b78c, 0x0810becc, 0x0810c35c,
    0x0810c8cc, 0x0810d008, 0x0810d16c, 0x0810d6f8,
    0x0810dd10, 0x0810e3e8, 0x0810ec80, 0x0810f200,
    0x0810f4e4, 0x08110290, 0x08110628, 0x08111130,
    0x0811190c, 0x08111ff8, 0x081126dc, 0x08112b94,
    0x0811323c, 0x08113754, 0x081143c8, 0x081150ac,
    0x08115704, 0x08115bec, 0x081162f8, 0x081165bc,
]; // provenance: derived -- ROM read 2026-09-17 (T145), asm31.s:169513
pub const STRUCT2_VIRUS_PTRS: [u32; 32] = [
    // AIEnemyStruct2Ptrs_8109150, asm31.s:169578-169609. Virus column of
    // off_800F260 (enemy_getStruct2, asm00_2.s:693-720; row = version*6,
    // elem_hp u16 packs element high nibble / figure low 12 bits).
    // Slot 0x17 = GunnerEnemyStruct2_8112B9C.
    0x08109a80, 0x08109bd8, 0x0810a2c8, 0x0810a848,
    0x0810ae4c, 0x0810b794, 0x0810bed4, 0x0810c364,
    0x0810c8d4, 0x0810d010, 0x0810d174, 0x0810d700,
    0x0810dd18, 0x0810e3f0, 0x0810ec88, 0x0810f208,
    0x0810f4ec, 0x08110298, 0x08110630, 0x08111138,
    0x08111914, 0x08112000, 0x081126e4, 0x08112b9c,
    0x08113244, 0x0811375c, 0x081143d0, 0x081150b4,
    0x0811570c, 0x08115bf4, 0x08116300, 0x081165c4,
]; // provenance: derived -- ROM read 2026-09-17 (T145), asm31.s:169578
pub const ACT_HANDLERS: [u32; 32] = [
    // AIActHandlers_81091D0, asm31.s:169643-169674. Act words ARE called
    // (mov lr,pc; bx r0, asm31.s:169417-169421); 0x0810962b = nullsub_13+1.
    0x0810962b, 0x0810962b, 0x0810962b, 0x0810abd1,
    0x0810962b, 0x0810962b, 0x0810962b, 0x0810962b,
    0x0810962b, 0x0810962b, 0x0810962b, 0x0810962b,
    0x0810e2a7, 0x0810e855, 0x0810f091, 0x0810962b,
    0x081100e3, 0x0810962b, 0x0810962b, 0x08111847,
    0x0810962b, 0x0810962b, 0x081129ef, 0x0810962b,
    0x0810962b, 0x0810962b, 0x08115099, 0x0810962b,
    0x081159dd, 0x081162ab, 0x081165a5, 0x0810962b,
]; // provenance: derived -- ROM read 2026-09-17 (T145), asm31.s:169643

/// AIIndex 0x17, the slot this ticket ports (`ForGunner_8113078`,
/// asm31.s:169496; the disassembly's own T12 known-answer names
/// enemy_idx 0x85 -> AIIndex 0x17, asm31.s:169432-169435).
pub const AI_INDEX: u8 = 0x17; // canon: byte_80182C4[3*0x185] = {00,01,17} (ROM read, T145)

/// Slot 0x17's rows in the four ticket tables, named:
/// think = ForGunner_8113078 (asm31.s:169496); Struct1 =
/// GunnerEnemyStruct1_8112B94 (asm31.s:169561); Struct2 =
/// GunnerEnemyStruct2_8112B9C (asm31.s:169626); act = nullsub_13+1
/// (asm31.s:169691).
pub const SLOT: usize = 0x17;

/// The virus-column Struct1 record the pointer above lands on:
/// `04 17 01 00 17 00 00 01`. Field layout per enemy_getStruct1's
/// .equiv block (asm00_2.s:634-645): sprite indices +0/+1, Unk_03/04,
/// Element +5, SecondaryElementWeakness +6, HasShadow +7.
pub const GUNNER_COL_STRUCT1: [u8; 8] = [0x04, 0x17, 0x01, 0x00, 0x17, 0x00, 0x00, 0x01]; // provenance: derived -- GunnerEnemyStruct1_8112B94, ROM read (T145), asm31.s:169561

/// The virus-column Struct2 row 0: elem_hp 0x003c (60 HP, element 0),
/// Unk_02 0, UnkFlags 0x08, elem_damage 0x000a (10). The live Gunner in
/// the battlestart_gunner state carries exactly this: +0x24 reads 0x003c.
pub const GUNNER_COL_STRUCT2_ROW0_HP: u16 = 60; // provenance: derived -- GunnerEnemyStruct2_8112B9C row0 `3c 00 00 08 0a 00`, ROM read (T145), asm31.s:169626

/// The NAVI struct columns a navi ActorType spawn actually reads
/// (enemy_getStruct1/2 actor-type columns off_800F230/off_800F260,
/// asm00_2.s:662-666/700-704): `NaviEnemyStruct1Ptrs_80F24D8[0x17]` =
/// byte_81067FC (asm31.s:123497), `NaviEnemyStruct2Ptrs_80F253C[0x17]` =
/// byte_8106804 (asm31.s:123548).
/// byte_81067FC = `00 0b 01 01 17 00 00 01` (same field layout as above).
pub const NAVI_COL_STRUCT1: [u8; 8] = [0x00, 0x0b, 0x01, 0x01, 0x17, 0x00, 0x00, 0x01]; // provenance: derived -- byte_81067FC, ROM read (T145), asm31.s:123497
/// byte_8106804 row 0 = `84 03 00 03 0a 00`: elem_hp 0x384 & 0xfff = 900,
/// element 0; UnkFlags 3, elem_damage 10. This is the HP a TRUE navi spawn
/// carries; the flip-route scenario (see the module doc) keeps the object's
/// virus-spawn HP 60, which is what the navi-gunner row pins instead.
pub const NAVI_COL_STRUCT2_ROW0_HP: u16 = 900; // provenance: derived -- byte_8106804 row0 `84 03 00 03 0a 00`, ROM read (T145), asm31.s:123548

/// The navi family's CurState legs (`off_80F2348`, asm31.s:123317-123321,
/// consumed UNBOUNDED by naviObject_dispatch_80F2330, asm31.s:123304-123312):
/// 0 = materialize (sub_8016F56, shared with the virus family), 1 = the
/// sub_80F2354 four-table leg, 2 = sub_8016C4E.
pub const CURSTATE_LEGS: [u32; 3] = [0x08016f57, 0x080f2355, 0x08016c4f]; // provenance: derived -- off_80F2348, ROM read (T145), asm31.s:123317-123321

/// Slot 0x17's rows in the four 25-slot navi-family tables sub_80F2354
/// consumes (asm31.s:123326-123361):
/// - 1st call off_80F2410[0x17] = sub_801A9B8+1, a shared hit/damage leg
///   (asm31.s:123421);
/// - 2nd call off_80F2474[0x17] = nullsub_106+1 -- no per-ai pattern
///   routine (asm31.s:123447);
/// - the AI arg off_80F23AC[0x17] = off_81068E8, this navi's own
///   CurAction-indexed AI arm, passed to ai_eventuallyRunsAIAttack_801AF44
///   (asm31.s:123395, call at :123345-123347);
/// - 4th call NaviActHandlers_80F25A0[0x17] = nullsub_106+1 -- no per-ai
///   act routine (asm31.s:123575).
pub const NAVI_HIT_LEG: u32 = 0x0801a9b9; // canon: off_80F2410[0x17] = sub_801A9B8+1, asm31.s:123421
pub const NAVI_PATTERN_LEG: u32 = 0x080f28c1; // unnamed: off_80F2474[0x17] = nullsub_106+1, ROM word read (T145), asm31.s:123447
pub const NAVI_ACT_LEG: u32 = 0x080f28c1; // unnamed: NaviActHandlers_80F25A0[0x17] = nullsub_106+1, ROM word read (T145), asm31.s:123575

/// off_81068E8, the AI arm table (15 entries, CurAction 0x00..0x0E; entry
/// 0x0f would read past it into unrelated data). Entries 0x00..0x07 are the
/// shared generic CurAction arms (0x08016381 = sub_8016380+1, the spawn/idle
/// plumbing ai.rs's module doc describes); 0x08..0x0E are this navi's own
/// executors (0x08106925..0x08107751) -- UNPORTED; our Style::Navi runs the
/// per-frame brain the latched dispatch actually services (the shared think
/// arm), so this table is carried as data for the follow-up that ports it.
pub const AI_ARM: [u32; 15] = [
    0x08016381, 0x08017889, 0x080170c5, 0x080174ff,
    0x080175b9, 0x080178b7, 0x08017689, 0x08017769,
    0x08106925, 0x08106ded, 0x08106ecf, 0x081070a9,
    0x08107185, 0x081073f7, 0x08107751,
]; // provenance: derived -- off_81068E8 = off_80F23AC[0x17], ROM read (T145), asm31.s:123395

/// What the port spawns for this slot. `hp` is the flip-route scenario's
/// measured value (the canon object spawned as a virus and keeps 60);
/// `true_spawn_hp` is byte_8106804's own 900 for the day a true navi spawn
/// exists. Element 0, has_shadow 1 in both struct columns.
pub struct NaviProfile {
    pub ai_index: u8,
    pub hp: u16,
    pub true_spawn_hp: u16,
    pub element: u8,
    pub has_shadow: bool,
}

/// The slot-0x17 profile the fixture spawn builds (battle.rs's KIND_NAVI
/// arm). HP 60: `GUNNER_COL_STRUCT2_ROW0_HP`, the value the row's canon
/// side carries; the navi column's own 900 is kept one field over.
pub fn profile_ai17() -> NaviProfile {
    NaviProfile {
        ai_index: AI_INDEX,
        hp: GUNNER_COL_STRUCT2_ROW0_HP,
        true_spawn_hp: NAVI_COL_STRUCT2_ROW0_HP,
        element: NAVI_COL_STRUCT1[5],
        has_shadow: NAVI_COL_STRUCT1[7] != 0,
    }
}
