//! The state of one battle and the frame logic that runs it: the intro
//! fades the screen in, the fight runs until a side is deleted, and the
//! results window closes with a fade-out. It is all rebuilt for the next
//! battle; the field, HUD and results assets are borrowed.

use agb::display::GraphicsFrame;
use agb::display::Priority;
use agb::display::object::Object;
use agb::display::tiled::{RegularBackground, RegularBackgroundSize, TileFormat};
use agb::fixnum::Num;
use agb::input::{Button, ButtonController};
use alloc::vec::Vec;

use crate::actor::{self, Actor, Update};
use crate::chips::{Chip, Chips};
use crate::custom::{self, Custom, CustomAssets, Offer};
use crate::deck::{Deck, Rng, FOLDER_SIZE};
use crate::field::{self, Field, Panels};
use crate::hud::{Counter, Hud};
use crate::results::{self, Results};
use crate::shot::Shot;
use crate::{
    BARREL_CHARGE, CANNON_ORB, CHARGE, COLONEL, CURSOR, DELETE, GUNNER, IMPACT, MEGAMAN, METTAUR,
    AIRSHOT_BARREL, AQUA_SWORD, BARRIER, BLKBOMB, BOMB_BLAST, ELEC_SWORD, FIRE_SWORD, HEAL,
    MINIBOMB,
    PROTOMAN, SHOTFX, SWORD_ARC, SWORD_SPR, VULCAN_GUN, WAVE,
};
use crate::{ai, gunner, spr};
use agb::display::Graphics;

// Boss HP comes from each navi's enemy-definition rows, six bytes per
// version: an hword whose low twelve bits are HP and top four the
// element, which the spawner writes to HP and MaxHP (sub_80076A0,
// asm00_1.s:9155). First version: ProtoMan byte_80FB8BC 0x708
// (asm31.s:141547), Colonel byte_8101244 0x4b0 (asm31.s:152949).
const PROTOMAN_HP: u16 = 1800;
const COLONEL_HP: u16 = 1200;
// The Mettaur's first-version record: HP 0x28, and its shockwave deals
// 10 (MettaurEnemyStruct2_8109BD8, byte_8109F28; asm31.s:170519).
const METTAUR_HP: u16 = 40;
const WAVE_DAMAGE: u16 = 10;
/// HP a chip-demo target carries so several hits can land without the fight
/// ending; the real value is 40, but that dies to one sword.
const DEMO_TARGET_HP: u16 = 900;
// MegaMan's own HP does come from the disassembly: byte_80210DD
// (data/dat01.s:295) row 0 gives 50 * 2 = 100, via init_8013B64.
const PLAYER_HP: u16 = 100;
// ProtoMan's strike reads byte_80FBFFC, 0x64 in the first version
// (sub_80FBF92, asm31.s:142402, 142437). Colonel's launchers each
// pick a damage row (asm31.s:153414-153526): the cross slash reads
// byte_81017D8 and the overhead slash byte_81017F0 (asm31.s:153623,
// 153629), whose first-version hwords are 80 and 30. The version column
// comes from the AI data's version byte (sub_800FE12, asm00_2.s:2370).
const SWORD_DAMAGE: u16 = 100;
const CROSS_DAMAGE: u16 = 80;
const DIVIDE_DAMAGE: u16 = 30;
// Buster damage is Attack + 1 for MegaMan (sub_801265A, asm00_2.s:7908)
// and a charged shot is (Attack + 1) * 10 (asm00_2.s:5988), at Attack 1.
const BUSTER_DAMAGE: u16 = 2;
const CHARGED_DAMAGE: u16 = 20;
// Frames of holding A before a release fires a charged shot: the buster's
// row of powerAttackChargeTimes_8020404 (data/dat01.s) at Charge stat 1.
const CHARGE_FRAMES: u16 = 100;
// Below this the hold is not yet a charge at all (asm00_2.s:9107).
const CHARGING_FROM: u16 = 10;
// The glow is one persistent effect object on the navi's arm whose
// animation index is the charge state, 1 charging and 2 full, hidden at 0
// (chargeShotChargeObject_update_80E0E20, asm31.s:86354). The game tracks
// the arm position each frame; a fixed offset stands in for that. It is
// centred on the navi's body and pushed a little toward the front (the
// direction it faces), rather than the old top-right corner offset, so the
// charge reads as gathering at the buster.
const GLOW_FORWARD: i32 = 8;
// The intro: the screen reveals over a 0x10-step fade (SetScreenFade via
// the intro object, asm31.s:85280), then the enemy navis materialise one
// at a time from a fade-in list, and only then does the fight state run
// and lift the pause (sub_8009658 onwards, asm00_1.s:13379; sub_800855E,
// 11048). The player's navi is simply there. The screen fade's frame
// count was not read; two frames a step stands in.
const SCREEN_FADE_FRAMES: u16 = 0x10 * 2;
// The custom gauge: a u16 at BattleState+0x20 that the fight state adds
// 0xd to each frame, full at 0x4000 (sub_800855E, asm00_1.s:11100;
// accessors asm00_2.s:29821-29883). A speed word at +0x22 defaults to
// 0x20 but nothing reading it was found, so it is not applied. When full
// the battle pauses for about 60 frames of chimes and then opens chip
// selection (sub_8008840), which clears the gauge on entry (asm03_0.s:540).
/// Where the player's HP number sits: the right edge and top of the box at
/// the screen's top left, measured off the real ROM. The box frame around
/// it is background art, which is not drawn yet.
const PLAYER_HP_AT: (i32, i32) = (44, 12);
const GAUGE_STEP: u16 = 0xd;
// Chips, by id in ChipDataArr_8021DA8 (data/ChipDataArr.s). The swords
// (attack family 0x13, sub_80EB776, asm31.s:108924) hold animation 5 for
// 0x15 frames with the hit when the timer reads 0xc -- the ninth frame --
// and exit after five more (sub_80EB862, asm31.s:109041, 109407); their
// shapes are the panel ahead, the column ahead, two panels ahead
// (byte_80EBA18). MiniBomb (family 0x12, sub_80EB644, asm31.s:108790)
// throws from animation 6 on the ninth frame of 0x15 and recovers five.
const CHIP_SWORD: u16 = 71;
const CHIP_WIDESWRD: u16 = 72;
const CHIP_LONGSWRD: u16 = 73;
const CHIP_WIDEBLDE: u16 = 74;
const CHIP_LONGBLDE: u16 = 75;
const CHIP_MURAMASA: u16 = 85;
const CHIP_STEPSWRD: u16 = 81;
const CHIP_FIRESWRD: u16 = 76;
const CHIP_AQUASWRD: u16 = 77;
const CHIP_ELECSWRD: u16 = 78;
const CHIP_BAMBSWRD: u16 = 79;
const CHIP_CANNON: u16 = 1;
const CHIP_HICANNON: u16 = 2;
const CHIP_MCANNON: u16 = 3;
const CHIP_AIRSHOT: u16 = 4;
const CHIP_VULCAN: u16 = 5;
const CHIP_VULCAN2: u16 = 6;
const CHIP_VULCAN3: u16 = 7;
const CHIP_SUPRVULC: u16 = 8;
const CHIP_MINIBOMB: u16 = 54;
const CHIP_BLKBOMB: u16 = 60;
const CHIP_BIGBOMB: u16 = 202;
const CHIP_RECOV10: u16 = 154;
const CHIP_RECOV30: u16 = 155;
const CHIP_RECOV50: u16 = 156;
const CHIP_RECOV80: u16 = 157;
const CHIP_RECOV120: u16 = 158;
const CHIP_RECOV150: u16 = 159;
const CHIP_RECOV200: u16 = 160;
const CHIP_RECOV300: u16 = 161;
const CHIP_AREAGRAB: u16 = 163;
const CHIP_INVISIBL: u16 = 177;
const CHIP_BARRIER: u16 = 178;
const CHIP_BARR100: u16 = 179;
const CHIP_BARR200: u16 = 180;
const CHIP_ENERGBOM: u16 = 55;
const CHIP_MEGENBOM: u16 = 56;
/// How long each slash arc animation runs, from its frame durations
/// (6+4+3, 6+4+3, 4+3+3).
const SWORD_ARC_FRAMES: [u8; 3] = [13, 13, 10];
// Against the real ROM (tools/chip_compare.py 47 demo-sword): the two
// lead-in states take a frame each (sub_80EB79C, sub_80EB84C), so two frames
// of the idle pose lead in; the slash pose is then on screen 27 frames --
// the 0x15 of its timer, the frame that reads the end and only queues the
// exit, the exit frame, and the five of recovery with its last frame held
// -- and the idle is back 29 frames after the press. Every frame of that,
// with the sword object and the arc, diffs to zero against the real ROM.
const SWORD: actor::AttackSpec = actor::AttackSpec {
    windup: Some((0, 2)),
    anim: 5,
    frames: 0x15 + 1,
    // The timer starts at 0x15 and the hit goes out on the frame it reads
    // 0xc (asm31.s:109141), the tenth of the pose.
    strike_at: 10,
    recover: 5,
    recover_anim: None,
};
/// StepSwrd holds its recovery pose one frame longer than the other swords.
/// Measured against the real ROM: on the attack's frame 29 the navi is still
/// in the recovery pose (917 non-black pixels at home, 178 of them body
/// colour) and idle on 30, where every other sword is idle on 29. The frame
/// the step spends going home is the likely cause.
const STEP_SWORD: actor::AttackSpec = actor::AttackSpec {
    windup: SWORD.windup,
    anim: SWORD.anim,
    frames: SWORD.frames,
    strike_at: SWORD.strike_at,
    recover: SWORD.recover + 1,
    recover_anim: SWORD.recover_anim,
};

/// MiniBomb (attack family 0x12, sub_80EB644, asm31.s:108790): animation 6
/// and the held bomb from the first frame, the throw on the frame the
/// counter reads 9 -- the tenth -- and the pose's first state ends at 0x15,
/// but the second state's timer is never re-seeded and counts the same
/// counter back down, so the navi holds animation 6 (whose last frame is
/// the idle pose) until the exit 42 frames in (sub_80EB758, asm31.s:108904).
const THROW: actor::AttackSpec = actor::AttackSpec {
    windup: None,
    anim: 6,
    frames: 42,
    strike_at: 10,
    recover: 0,
    recover_anim: None,
};
/// The cannon pose: the counter runs to 0x1d (sub_80EBC28, asm31.s:109532,
/// 109554), and the frame that reads 0x1d only queues the exit state, which
/// runs the frame after, so the pose is on screen for 0x1e frames -- the real
/// ROM shows the idle again 30 frames after the attack starts (TRANSFER.md).
/// The barrel object lives exactly as long.
const CANNON_FRAMES: u8 = 0x1d + 1;
/// Frames between auto-fire chip uses in the demo-auto harness: long enough
/// for an attack's pose and shot to run out before the next one begins.
#[cfg(feature = "demo-auto")]
const AUTO_FIRE_GAP: u16 = 90;
/// Cannon and HiCannon (attack family 0x14, sub_80EBC28): the navi takes
/// animation 8 and the projectile is spawned off the front panel when the
/// frame counter reads 0xf, the pose exiting once it reads 0x1d
/// (asm31.s:109454, 109532, 109549). Both subfamilies are under 4, so the
/// illusions at counter 8 do not apply (asm31.s:109480).
const CANNON: actor::AttackSpec = actor::AttackSpec {
    windup: None,
    anim: 8,
    frames: CANNON_FRAMES,
    strike_at: 0xf,
    // After the pose the real ROM shows three frames of the arm coming
    // down -- animation 15, a single three-frame pose -- before the idle
    // (TRANSFER.md: idle again 33 frames after the attack starts).
    recover: 3,
    recover_anim: Some(15),
};
/// Vulcan1 (attack family 0x17, sub_80EBF10, asm31.s:109821): the first
/// state holds animation 0xa for two ticks with the arm gun spawned; the
/// firing state sets animation 0xd (which loops on its own every five
/// frames -- the recoil rhythm) and fires on its first tick and every 0xa
/// after, three shots (dword_80EBFEC), handing over after the third; the
/// last state sets animation 0xa again for 0xa ticks and exits. Against the
/// real ROM the idle is back 35 frames after the press.
/// Shots per Vulcan, from the subfamily (dword_80EBFEC = 0xA050403:
/// Vulcan1 3, Vulcan2 4, Vulcan3 5; asm31.s:109878-109892). Measured on
/// the real ROM, the muzzle flashes run every 5 frames from c5 and each
/// extra shot lengthens the attack by 11 frames: the gun is on screen 35,
/// 46 and 57 frames for the three chips.
const fn vulcan_shots(id: u16) -> u8 {
    match id {
        CHIP_VULCAN2 => 4,
        CHIP_VULCAN3 => 5,
        CHIP_SUPRVULC => 10,
        _ => 3,
    }
}

/// The firing state's length and the recovery that follows, per shot
/// count. Measured on the real ROM: the firing pose's last frame -- recoil
/// plus muzzle flash -- is c21, c35 and c46 for Vulcan1/2/3 (the pose
/// starts at c2), and the gun is on screen 35, 46 and 57 frames, which
/// leaves the recoveries below. The state machine's own tick rate does not
/// map to frames one-for-one, so these are the measurements rather than a
/// formula.
const fn vulcan_timing(shots: u8) -> (u8, u8) {
    match shots {
        4 => (34, 10),
        5 => (45, 10),
        // SuprVulc's ten shots: its flashes run to c101 and the gun is on
        // screen 112 frames, measured the same way.
        10 => (100, 10),
        _ => (20, 13),
    }
}

const fn vulcan(shots: u8) -> actor::AttackSpec {
    let (frames, recover) = vulcan_timing(shots);
    actor::AttackSpec {
        windup: Some((0xa, 2)),
        anim: 0xd,
        frames,
        strike_at: 1,
        recover,
        recover_anim: Some(0xa),
    }
}
/// The Vulcan gun rides the arm for the whole attack (byte_80B8BD4 row
/// 0xd: effect list 0xC index 0x1d = sprite_83195F0, animation 0, at
/// arm-position row 0xe: +23 forward, 25 up, byte_80188C0[28..30]).
const fn vulcan_gun_frames(shots: u8) -> u8 {
    let (firing, recover) = vulcan_timing(shots);
    2 + firing + recover
}
const VULCAN_ARM: (i32, i32) = (23, -25);
/// AirShot (attack family 0x21, sub_80EC884): animation 9 and the arm
/// object from the first frame, sound 0xaf; the hit goes out on the frame
/// the counter reads 5 -- the sixth -- as an instant one-panel hitbox one
/// panel ahead (sub_80C4FFE -> t3_0x0_80C4E58: no travelling shot); the
/// first state hands over when the counter reads 10 and the second counts
/// it back down, exiting on the 22nd frame (sub_80EC8A0, sub_80EC90E;
/// asm31.s:111067-111142). So the pose is on screen 21 frames.
const AIRSHOT: actor::AttackSpec = actor::AttackSpec {
    windup: None,
    anim: 0x9,
    frames: 21,
    strike_at: 6,
    recover: 0,
    recover_anim: None,
};
/// The AirShot arm object lives as long as the pose (byte_80B8BD4 row
/// 0x13: effect list 0xC index 0x18 = sprite_83138C4, animation 0 -- the
/// barrel, four frames of muzzle gust, the barrel held -- at arm-position
/// row 0xa: +18 forward, 24 up, byte_80188C0[20..22]).
const AIRSHOT_FRAMES: u8 = 21;
const AIRSHOT_ARM: (i32, i32) = (18, -24);
/// The Recov chips heal their names; the amounts are byte_80EC870
/// (asm31.s:111044), one per subfamily.
const RECOV_HP: [u16; 9] = [10, 30, 50, 80, 120, 150, 200, 300, 1000];
/// The heal effect's animation length, from its frame durations.
const HEAL_FRAMES: u8 = 14;
/// Invisibl's timer is its first parameter, 0x68 (ChipDataArr.s:5490).
const INVISIBL_FRAMES: u16 = 0x68;
/// Barrier's HP for type 1 is 10 (byte_8020B2C, dat01.s:189).
const BARRIER_HP: u16 = 10;
/// Barrier, Barr100 and Barr200 are one chip with one handler: family 0x15
/// subfamily 4 (off_802CCB4[4] = sub_80E3B50), whose first attack parameter
/// indexes byte_8020B2C (data/dat01.s:189) for the bubble's HP. Barrier's
/// parameter is 1 -> row 1 = 10, Barr100's is 5 -> 0x64, Barr200's is 7 ->
/// 0xc8. Nothing else about them differs.
/// The bubble is the same object in another colour: Barrier's is teal,
/// Barr100's gold and Barr200's pink, matched colour for colour against the
/// real captures against sprite_832F8C8's thirteen palettes. The asset is
/// exported with all of them for this.
const fn barrier_palette(id: u16) -> usize {
    match id {
        CHIP_BARR100 => 3,
        CHIP_BARR200 => 6,
        _ => 0,
    }
}

const fn barrier_hp(id: u16) -> u16 {
    match id {
        CHIP_BARR100 => 100,
        CHIP_BARR200 => 200,
        _ => BARRIER_HP,
    }
}
/// Frames from the press to the effect, measured on the real ROM (the
/// bubble object's first, one-frame dot is behind the navi, so it is
/// created a frame before the bubble shows).
const INVISIBL_PRESENTATION: u16 = 128;
const BARRIER_PRESENTATION: u16 = 77;
/// AreaGrab is in the same family; its own length is not measured, so
/// Barrier's is used.
const AREAGRAB_PRESENTATION: u16 = BARRIER_PRESENTATION;
/// The thrown bomb (sub_80C5DBC -> t3_0x8_80C5BB0, asm31.s:29657, 29400):
/// spawned 4 pixels ahead of the navi and 0x30 up, sprite_82F569C
/// animation 1 with a shadow; it flies at 0x2e666 (2.9 px) a frame
/// forward, its vertical speed starting at 0x20666 (2.02 px) a frame and
/// losing 0x2800 (0.156 px) a frame (byte_80C5D58, asm31.s:29609), for a
/// fixed 0x28 frames (asm31.s:29531), which is about three panels.
const BOMB_FLIGHT: u8 = 40;
/// BlkBomb's ball covers the same three panels more slowly: measured against
/// the real ROM, its leading edge moves 70 px over the 27 frames where
/// MiniBomb's moves 74, so the flight is 42 frames rather than 40. The
/// horizontal speed scales down with that and the launch speed up, so the arc
/// still lands flat.
const BLKBOMB_FLIGHT: u8 = 42;
const BLKBOMB_VX: i32 = 0x2C000;
const BLKBOMB_VZ: i32 = 0x22051;

/// The afterimage's age when it is drawn for the last time. It is spawned
/// during the frame that uses the chip and aged in that same frame, so an age
/// of 1 is the attack's frame 0. Measured against the real ROM: drawn on the
/// attack's frames 1-2, 5-6, 9-10, 13-14 and 17-18, and gone from 19 on.
const STEP_GHOST_LAST: u8 = 19;
/// The panel the navi steps TO gets a second red afterimage of its own from
/// the attack's frame 8, blinking two on and two off through frame 29. Unlike
/// the one left at home this is not a single still: it TRAILS the navi by
/// exactly three frames. Read out of the real ROM's OAM, object for object --
/// on frame 16 the red copy's four sprites have precisely the sizes and
/// positions the navi's had on frame 13, and on frame 17 the same, and on
/// frame 12 those of frame 9. It outlives the step: the navi is home from
/// frame 24 and the copy is still blinking there at 29.
const STEP_GHOST2_FIRST: u8 = 9;
const STEP_GHOST2_LAST: u8 = 34;
/// The age at which the step's bookkeeping is dropped.
const STEP_STATE_LAST: u8 = 34;
const BOMB_SPAWN_AHEAD: i32 = 4 << 16;
const BOMB_SPAWN_UP: i32 = 0x30 << 16;
const BOMB_VX: i32 = 0x2e666;
const BOMB_VZ: i32 = 0x20666;
const BOMB_GRAVITY: i32 = 0x2800;
/// The bomb's palette. The held object takes byte_80EB738's packed row
/// (asm31.s:108898): MiniBomb and BigBomb row 4, BlkBomb row 0x2d, which
/// is the same sprite with palette 4. The thrown object takes
/// byte_80C5BA0[Param1]'s fourth byte instead (asm31.s:29422): row 0 is
/// palette 0 and row 3 -- BigBomb's, whose first attack parameter is 3 --
/// is palette 3, the red bomb.
/// Which animation of the bomb sprite a bomb plays, held and thrown. MiniBomb,
/// BlkBomb and BigBomb use 0 and 1; EnergBom and MegEnBom use 2 and 3. Found
/// by pulling the real bomb's tiles out of OBJ VRAM and looking for those
/// exact bytes among the sprite's graphics blobs: held, they turn up in the
/// blob animation 2's first frame uses; in flight, in the one animation 3's
/// second frame uses -- and animation 3 is a five-frame loop at four frames
/// each, which is the bomb tumbling, where MiniBomb's animation 1 is a single
/// held frame.
const fn bomb_anim(id: u16, thrown: bool) -> usize {
    match (id, thrown) {
        (CHIP_ENERGBOM | CHIP_MEGENBOM, false) => 2,
        (CHIP_ENERGBOM | CHIP_MEGENBOM, true) => 3,
        (_, true) => 1,
        _ => 0,
    }
}

const fn bomb_palette(id: u16, thrown: bool) -> usize {
    match (id, thrown) {
        (CHIP_BLKBOMB, false) => 4,
        (CHIP_BIGBOMB, _) => 3,
        // EnergBom and MegEnBom are MiniBomb's own held sprite row in
        // another palette (byte_80EB738 pair 1, asm31.s:108898), and they
        // throw through the same sub_80C5DBC. The exporter's palette order is
        // not the ROM's, so the index is the measured one: the real held bomb
        // is grey with brown and orange, and palette 5 is the only one of
        // sprite_82F569C's thirteen that holds all of those colours. The
        // asset is exported with every palette so that index exists.
        (CHIP_ENERGBOM | CHIP_MEGENBOM, _) => 5,
        _ => 0,
    }
}

// BlkBomb (family 0x12 subfamily 6) throws through off_80EB6F8[6] =
// sub_80CD886 (asm31.s:45704) rather than MiniBomb's sub_80C5DBC, and that
// object's sprite resolves to sprite_831EA40 animation 0 by
// byte_80CD8AC[Param1 * 8] (asm31.s:46200). But that sprite is a numbered
// canister, while the real ROM throws a dark brown ball on the same arc as
// MiniBomb with the same ground shadow, so the reading is wrong somewhere.
// Until it is resolved BlkBomb arcs like MiniBomb; only its colours differ
// from the real ROM (its brown is in none of the bomb sprite's palettes).

/// The held bomb rides the navi's origin with no offset (byte_80B8BD4 row
/// 4: effect list 0xC index 2 = sprite_82F569C, animation 0) until the
/// throw, when the attack drops it (the real ROM shows it gone on the
/// throw frame).
const HELD_BOMB_FRAMES: u8 = THROW.strike_at - 1;
/// On a solid panel the landing spreads type-4 effect row 0 -- effect list
/// 0x14 index 0, sprite_8399578, animation 0, 22 frames -- from the panel
/// (sub_801BD3C, asm31.s:29569-29589) with sound 0x70.
const BLAST_FRAMES: u8 = 22;

/// A thrown MiniBomb in flight, in the game's 16.16 coordinates.
struct Bomb {
    player: spr::Player,
    x: i32,
    y: i32,
    z: i32,
    vx: i32,
    vz: i32,
    target: (i32, i32),
    damage: u16,
    /// BigBomb's landing spreads over the panel and its eight neighbours:
    /// the region byte dword_80C5D7C[Param1] is 1 for MiniBomb and 0xf for
    /// BigBomb, and 0xf is the nine-panel offset list byte_8019951
    /// (asm31.s:29619, asm00_2.s:20987). Every panel gets the same puff.
    wide: bool,
    ticks: u8,
    flight: u8,
}

impl Bomb {
    fn step(&mut self) {
        self.x += self.vx;
        self.vz -= BOMB_GRAVITY;
        self.z += self.vz;
    }

    /// Screen position of the bomb; the game truncates Y and Z separately.
    fn position(&self) -> (i32, i32) {
        (self.x >> 16, (self.y >> 16) - (self.z >> 16))
    }

    /// Where the shadow goes: on the ground under the bomb.
    fn ground(&self) -> (i32, i32) {
        (self.x >> 16, self.y >> 16)
    }
}
const GAUGE_FULL: u16 = 0x4000;
const GAUGE_PAUSE: u16 = 60;
// After the last combatant on a side is gone the game's win or loss
// state waits before the window comes up; that wait was not read, and
// 30 frames stand in. The clear time counts from when control opened.
const RESULTS_DELAY: u16 = 30;

/// Everything that belongs to one battle, so a finished battle can be
/// dropped and the next one built from scratch.
pub struct Battle<'a> {
    field: &'a Field,
    results: &'a Results,
    hud: &'a Hud,
    custom_assets: &'a CustomAssets,
    custom: Option<Custom<'a>>,
    chips: &'a Chips,
    deck: Deck,
    /// The HP numbers on screen, which lag the real values: the player's
    /// first, then each enemy's.
    hp_shown: Vec<Counter>,
    /// The picks from the last chip select, in order (byte_20349C0), and
    /// how many have been used (getCurChipInBattleHand_8010004 reads
    /// hand + 2 + 2 * count; sub_800FC7C advances the count).
    hand: alloc::vec::Vec<Chip>,
    hand_at: usize,
    /// The chip whose attack pose is playing, for its strike.
    chip_in_use: Option<Chip>,
    /// The Vulcan gun, driven by the attack's states: animation 0 while the
    /// first state holds, 1 (the firing loop with its muzzle flashes) from
    /// the firing state's first frame, 2 (held) from the last state. The
    /// real ROM's gun follows the navi's states this way; how the game
    /// passes the state to the object was not traced.
    vulcan_gun: Option<(spr::Player, (i32, i32), u8)>,
    /// A family-0x15 chip mid-presentation: the game freezes time, dims the
    /// screen and shows the chip's name before the effect lands
    /// (object_timefreezeBegin, object_dimScreen, object_drawChipName;
    /// object.s:95-287). The lengths are measured on the real ROM -- the
    /// bubble appears 78 frames after the press for Barrier, the flicker
    /// starts 128 after for Invisibl -- as the banner's own timing was not
    /// traced. The dim itself is not drawn yet.
    presentation: Option<(Chip, u16)>,
    /// Barrier's bubble: type-4 object 7 (t4_0x7_80E0AD4, asm31.s:85805;
    /// byte_80E0A14 -> effect list 0xC index 0x3d = sprite_832F8C8),
    /// animation 0 -- a one-frame dot the navi covers, then three frames of
    /// bubble, four times over, looping -- on the navi's origin and under
    /// the navi (its OAM entries follow the navi's), for as long as the
    /// barrier has HP (sub_80E0C74, asm31.s:86011).
    bubble: Option<spr::Player>,
    /// Where StepSwrd's dash started, so the navi can be put back.
    step_home: Option<(i32, i32)>,
    /// The afterimage StepSwrd leaves on the panel it stepped off: the navi's
    /// idle silhouette, its screen position, and its age in frames. Measured
    /// against the real ROM with the enemy hidden rather than deleted -- it is
    /// drawn two frames on and two off, from the attack's frame 1 through its
    /// frame 18, and the navi's own colours are on the enemy's column
    /// throughout. The real object is semi-transparent, which this is not:
    /// under `--disable-bg` mGBA mis-blends it to red-only, so the capture
    /// cannot show what it should look like over a black field (TRANSFER.md
    /// 7l).
    step_ghost: Option<(spr::Player, (i32, i32), u8)>,
    /// The second afterimage, on the panel the navi stepped to, built from
    /// the navi's sprite frame of three frames ago, with the key it was built
    /// from so it is only rebuilt when that frame changes.
    step_ghost2: Option<(spr::Player, (i32, i32))>,
    step_ghost2_key: Option<(usize, usize)>,
    /// The sword's matching red copy: the afterimage takes the attack's own
    /// object with it, so on a blink frame the far panel's blade tip is drawn
    /// in the red bank rather than its own teal and white.
    step_ghost2_sword: Option<(spr::Player, (i32, i32))>,
    /// The sprite the live sword was built from, so its past frame can be
    /// rebuilt, and the navi's and the sword's last four sprite frames, so
    /// the afterimage can lag by three.
    step_sword_art: Option<(&'static [u8], usize)>,
    step_trail: [((usize, usize), (i32, i32)); 4],
    step_trail_sword: [Option<(usize, usize)>; 4],
    /// The panel the step went to. The afterimage keeps taking new frames
    /// after the navi has gone home -- frame 24's copy carries the navi's
    /// frame-21 sprite -- but only from frames where the navi was still over
    /// there, so the trail is followed by position, not by a cut-off.
    step_dest: (i32, i32),
    /// Frames until the sword object is spawned: the two lead-in states
    /// (sub_80EB79C, sub_80EB84C: one frame each) before the slash state
    /// that creates it.
    sword_in: Option<u8>,
    bombs: Vec<Bomb>,
    panels: Panels,
    bg: RegularBackground,
    backdrop: crate::backdrop::Backdrop,
    hud_tiles: crate::hudtiles::HudTiles,
    megaman: Actor,
    /// Sizes differ between debug and release builds: a debug build fights
    /// the Mettaur alone so the hand and chips can be tried without the
    /// bosses, while the release keeps the game's lineup. Everything here
    /// reads whatever length it is.
    enemies: Vec<Actor>,
    ais: Vec<ai::Ai>,
    gunner_ctl: gunner::Gunner,
    impacts: Vec<gunner::Impact>,
    /// Transient sprites: the player, its screen position, frames left, and
    /// whether it is a type-4 effect object -- one the game draws on its
    /// spawn frame with its first animation frame counting from the next
    /// (the sword arc, the heal), unlike the type-1 attack objects (the
    /// cannon barrel, the sword) whose first frame counts from the spawn.
    effects: Vec<(spr::Player, (i32, i32), u8, bool)>,
    shots: Vec<Shot>,
    glow: spr::Player,
    glow_state: usize,
    charge: u16,
    cross_shape: Option<&'static [(i32, i32)]>,
    intro_fade: u16,
    intro_next: usize,
    gauge: u16,
    gauge_pause: u16,
    results_delay: u16,
    shown: Option<results::Shown>,
    fade_out: u8,
    clock: u32,
    moves: u8,
    /// Countdown to the next automatic chip use, for the demo-auto harness.
    auto_ticks: u16,
}

/// What a demo build fields: the chip ids to preload straight into the hand
/// (A fires the first at once), and the lone enemy to place so that chip
/// connects on the first press. Enemy-only demos leave the hand empty and
/// just field their navi. None when no demo feature is on.
#[cfg(feature = "demo")]
fn demo() -> (alloc::vec::Vec<u16>, i32, Option<(spr::Assets, i32, i32, ai::Style, u16)>) {
    let mut hand = alloc::vec::Vec::new();
    // A sterile arena fields MegaMan alone at the same panel the real save
    // state uses (panel (2,2)) so a chip animation can be captured and
    // compared frame-for-frame against the real ROM. The hand holds the chip
    // of whichever chip demo feature is also on, the cannon family when none.
    // This branch must win over the chip demos below, so it is checked first.
    if cfg!(feature = "demo-sterile") {
        if cfg!(feature = "demo-sword") {
            hand.push(CHIP_SWORD);
        } else if cfg!(feature = "demo-wideswrd") {
            hand.push(CHIP_WIDESWRD);
        } else if cfg!(feature = "demo-longswrd") {
            hand.push(CHIP_LONGSWRD);
        } else if cfg!(feature = "demo-hicannon") {
            hand.push(CHIP_HICANNON);
        } else if cfg!(feature = "demo-mcannon") {
            hand.push(CHIP_MCANNON);
        } else if cfg!(feature = "demo-areagrab") {
            hand.push(CHIP_AREAGRAB);
        } else if cfg!(feature = "demo-vulcan2") {
            hand.push(CHIP_VULCAN2);
        } else if cfg!(feature = "demo-vulcan3") {
            hand.push(CHIP_VULCAN3);
        } else if cfg!(feature = "demo-recov50") {
            hand.push(CHIP_RECOV50);
        } else if cfg!(feature = "demo-fireswrd") {
            hand.push(CHIP_FIRESWRD);
        } else if cfg!(feature = "demo-aquaswrd") {
            hand.push(CHIP_AQUASWRD);
        } else if cfg!(feature = "demo-elecswrd") {
            hand.push(CHIP_ELECSWRD);
        } else if cfg!(feature = "demo-bambswrd") {
            hand.push(CHIP_BAMBSWRD);
        } else if cfg!(feature = "demo-blkbomb") {
            hand.push(CHIP_BLKBOMB);
        } else if cfg!(feature = "demo-bigbomb") {
            hand.push(CHIP_BIGBOMB);
        } else if cfg!(feature = "demo-energbom") {
            hand.push(CHIP_ENERGBOM);
        } else if cfg!(feature = "demo-megenbom") {
            hand.push(CHIP_MEGENBOM);
        } else if cfg!(feature = "demo-barr100") {
            hand.push(CHIP_BARR100);
        } else if cfg!(feature = "demo-barr200") {
            hand.push(CHIP_BARR200);
        } else if cfg!(feature = "demo-wideblde") {
            hand.push(CHIP_WIDEBLDE);
        } else if cfg!(feature = "demo-longblde") {
            hand.push(CHIP_LONGBLDE);
        } else if cfg!(feature = "demo-recov300") {
            hand.push(CHIP_RECOV300);
        } else if cfg!(feature = "demo-recov80") {
            hand.push(CHIP_RECOV80);
        } else if cfg!(feature = "demo-recov120") {
            hand.push(CHIP_RECOV120);
        } else if cfg!(feature = "demo-recov150") {
            hand.push(CHIP_RECOV150);
        } else if cfg!(feature = "demo-recov200") {
            hand.push(CHIP_RECOV200);
        } else if cfg!(feature = "demo-suprvulc") {
            hand.push(CHIP_SUPRVULC);
        } else if cfg!(feature = "demo-muramasa") {
            hand.push(CHIP_MURAMASA);
        } else if cfg!(feature = "demo-stepswrd") {
            hand.push(CHIP_STEPSWRD);
        } else if cfg!(feature = "demo-recov30") {
            hand.push(CHIP_RECOV30);
        } else if cfg!(feature = "demo-invisibl") {
            hand.push(CHIP_INVISIBL);
        } else if cfg!(feature = "demo-barrier") {
            hand.push(CHIP_BARRIER);
        } else if cfg!(feature = "demo-minibomb") {
            hand.push(CHIP_MINIBOMB);
        } else if cfg!(feature = "demo-vulcan") {
            hand.push(CHIP_VULCAN);
        } else if cfg!(feature = "demo-airshot") {
            hand.push(CHIP_AIRSHOT);
        } else if cfg!(feature = "demo-recovery") {
            hand.push(CHIP_RECOV10);
        } else {
            hand.push(CHIP_CANNON);
            hand.push(CHIP_HICANNON);
        }
        return (hand, 2, None);
    }
    // MegaMan is placed at (3,2) facing right so his front panel is (4,2), the
    // first column of the enemy half: a sword lands there, a cannon/vulcan/
    // airshot shot spawns there and travels on, and LongSwrd reaches it and
    // the panel behind it. WideSwrd sweeps that whole column. MiniBomb lands
    // three ahead of (3,2), so its target sits at (6,2). The target carries a
    // big HP so a chip demo can land several hits without the fight ending;
    // demo-results uses the real 40 so one hit brings the window up.
    // The real ROM's pausedwithcannon save state, for whole-screen
    // comparisons: MegaMan at (2,2), a Mettaur at (5,2) kept alive.
    if cfg!(feature = "demo-field") {
        return (
            hand,
            2,
            Some((spr::Assets::new(METTAUR), 5, 2, ai::Style::Mettaur, DEMO_TARGET_HP)),
        );
    }
    let megaman_col = 3;
    // Chip demos use a padded-HP target so several hits land without ending
    // the fight; enemy and results demos use the real HP below.
    let hp = DEMO_TARGET_HP;
    if cfg!(feature = "demo-buster") {
        return (hand, megaman_col, Some((spr::Assets::new(METTAUR), 4, 2, ai::Style::Mettaur, hp)));
    }
    if cfg!(feature = "demo-sword") {
        hand.push(CHIP_SWORD);
        return (hand, megaman_col, Some((spr::Assets::new(METTAUR), 4, 2, ai::Style::Mettaur, hp)));
    }
    if cfg!(feature = "demo-minibomb") {
        hand.push(CHIP_MINIBOMB);
        return (hand, megaman_col, Some((spr::Assets::new(METTAUR), 6, 2, ai::Style::Mettaur, hp)));
    }
    if cfg!(feature = "demo-cannon") {
        hand.push(CHIP_CANNON);
        hand.push(CHIP_HICANNON);
        return (hand, megaman_col, Some((spr::Assets::new(METTAUR), 4, 2, ai::Style::Mettaur, hp)));
    }
    // Two grabs, so the boundary moves twice.
    if cfg!(feature = "demo-areagrab") {
        hand.push(CHIP_AREAGRAB);
        hand.push(CHIP_AREAGRAB);
        return (hand, megaman_col, Some((spr::Assets::new(METTAUR), 6, 2, ai::Style::Mettaur, hp)));
    }
    if cfg!(feature = "demo-vulcan") {
        hand.push(CHIP_VULCAN);
        return (hand, megaman_col, Some((spr::Assets::new(METTAUR), 4, 2, ai::Style::Mettaur, hp)));
    }
    if cfg!(feature = "demo-airshot") {
        hand.push(CHIP_AIRSHOT);
        return (hand, megaman_col, Some((spr::Assets::new(METTAUR), 4, 2, ai::Style::Mettaur, hp)));
    }
    if cfg!(feature = "demo-recovery") {
        hand.push(CHIP_RECOV10);
        hand.push(CHIP_RECOV30);
        hand.push(CHIP_INVISIBL);
        hand.push(CHIP_BARRIER);
        return (hand, megaman_col, Some((spr::Assets::new(METTAUR), 6, 2, ai::Style::Mettaur, hp)));
    }
    if cfg!(feature = "demo-mettaur") {
        return (hand, megaman_col, Some((spr::Assets::new(METTAUR), 4, 2, ai::Style::Mettaur, METTAUR_HP)));
    }
    if cfg!(feature = "demo-gunner") {
        return (hand, megaman_col, Some((spr::Assets::new(GUNNER), 6, 2, ai::Style::Gunner, gunner::HP)));
    }
    if cfg!(feature = "demo-protoman") {
        return (hand, megaman_col, Some((spr::Assets::new(PROTOMAN), 6, 2, ai::Style::Thrust, PROTOMAN_HP)));
    }
    if cfg!(feature = "demo-colonel") {
        return (hand, megaman_col, Some((spr::Assets::new(COLONEL), 6, 2, ai::Style::Divide, COLONEL_HP)));
    }
    if cfg!(feature = "demo-results") {
        // A lone Mettaur with a sword in hand: one press deletes it and the
        // RESULT window slides in.
        hand.push(CHIP_SWORD);
        return (hand, megaman_col, Some((spr::Assets::new(METTAUR), 4, 2, ai::Style::Mettaur, METTAUR_HP)));
    }
    (hand, megaman_col, None)
}

impl<'a> Battle<'a> {
    pub fn new(
        field: &'a Field,
        results: &'a Results,
        hud: &'a Hud,
        custom_assets: &'a CustomAssets,
        chips: &'a Chips,
        rng: &mut Rng,
    ) -> Self {
        // A stand-in folder: the asset's chips over and over, each with its
        // first code, in place of the PET navi's thirty (sub_800A3E4).
        let mut folder = [0u16; FOLDER_SIZE];
        for (i, entry) in folder.iter_mut().enumerate() {
            let chip = chips.get(i % chips.len());
            *entry = Deck::entry(chip.id, chip.codes[0]);
        }
        let deck = Deck::new(folder, rng);
        let panels = Panels::new(field::PANEL_NORMAL);
        // The sterile arena draws a plain background so the real ROM's field can
        // be stripped via the harness's --disable-bg (BG layers) and the two
        // captures diff cleanly whole-frame: MegaMan + attack on black on both.
        #[cfg(feature = "demo-sterile")]
        let bg = RegularBackground::new(
            Priority::P3,
            RegularBackgroundSize::Background32x32,
            TileFormat::FourBpp,
        );
        #[cfg(not(feature = "demo-sterile"))]
        let bg = field.background(&panels);

        let charge = 0u16;
        let glow = spr::Player::new(spr::Assets::new(CHARGE), 1);
        let glow_state = 0usize;
        let player = actor::Profile {
            hp: PLAYER_HP,
            mercy: actor::PLAYER_MERCY_FRAMES,
            death_frames: actor::PLAYER_DEATH_FRAMES,
        };
        let enemy = |hp| actor::Profile {
            hp,
            mercy: 0,
            death_frames: actor::ENEMY_DEATH_FRAMES,
        };
        // A demo build also moves MegaMan up to the front of his half so the
        // featured chip reaches the target on the first press.
        let (demo_hand, demo_col, demo_enemy) = {
            #[cfg(feature = "demo")]
            {
                demo()
            }
            #[cfg(not(feature = "demo"))]
            {
                (alloc::vec::Vec::new(), 2, None)
            }
        };
        let megaman = Actor::new(spr::Assets::new(MEGAMAN), demo_col, 2, false, player);
        // Whether a virus dies with the navi's 0x5a-frame blink was not checked.
        // A debug build fights just the Mettaur, to exercise the hand, chips
        // and deletion without the bosses; the release build keeps the game's
        // lineup. A demo build fields its one featured enemy instead. The
        // sterile arena fields nobody.
        let mut enemies: Vec<Actor> = if cfg!(feature = "demo-sterile") {
            alloc::vec::Vec::new()
        } else if let Some((assets, col, row, _style, hp)) = demo_enemy {
            alloc::vec![Actor::new(assets, col, row, true, enemy(hp))]
        } else if cfg!(debug_assertions) {
            alloc::vec![Actor::new(
                spr::Assets::new(METTAUR),
                5,
                3,
                true,
                enemy(METTAUR_HP)
            )]
        } else {
            alloc::vec![
                Actor::new(spr::Assets::new(PROTOMAN), 5, 1, true, enemy(PROTOMAN_HP)),
                Actor::new(spr::Assets::new(COLONEL), 6, 3, true, enemy(COLONEL_HP)),
                Actor::new(spr::Assets::new(METTAUR), 5, 3, true, enemy(METTAUR_HP)),
                Actor::new(spr::Assets::new(GUNNER), 6, 2, true, enemy(gunner::HP)),
            ]
        };
        let gunner_ctl = gunner::Gunner::new();
        let impacts: Vec<gunner::Impact> = Vec::new();
        // The deletion effect, sprite_839CCDC animation 0, spawned at the body
        // when HP reaches zero (spawn_t1_0x0_EffectObject via byte_80E0398 row
        // 3; asm31.s:85229, 85033). An enemy's is given a 0x5a-frame timer.
        let effects: Vec<(spr::Player, (i32, i32), u8, bool)> = Vec::new();
        let ais: Vec<ai::Ai> = if cfg!(feature = "demo-sterile") {
            alloc::vec::Vec::new()
        } else if let Some((_, _, _, style, _)) = demo_enemy {
            alloc::vec![ai::Ai::new(style)]
        } else if cfg!(debug_assertions) {
            alloc::vec![ai::Ai::new(ai::Style::Mettaur)]
        } else {
            alloc::vec![
                ai::Ai::new(ai::Style::Thrust),
                ai::Ai::new(ai::Style::Divide),
                ai::Ai::new(ai::Style::Mettaur),
                ai::Ai::new(ai::Style::Gunner),
            ]
        };
        let intro_fade = SCREEN_FADE_FRAMES;
        let intro_next = 0usize;
        for enemy in enemies.iter_mut() {
            enemy.hide();
        }
        let cross_shape: Option<&[(i32, i32)]> = None;
        let shots: Vec<Shot> = Vec::new();
        // A debug build starts with the gauge full, so the first chip select
        // comes up right after the intro instead of after the counter runs.
        let gauge = if cfg!(debug_assertions) { GAUGE_FULL } else { 0 };
        let gauge_pause = 0u16;
        let results_delay = RESULTS_DELAY;
        let shown: Option<results::Shown> = None;
        let fade_out = 0u8;
        let clock = 0u32;
        let moves = 0u8;
        #[cfg(feature = "demo-auto")]
        let auto_ticks = AUTO_FIRE_GAP;
        #[cfg(not(feature = "demo-auto"))]
        let auto_ticks = 0u16;
        // A demo build loads its chips straight into the hand, so A fires the
        // first one at once without the chip-select window.
        let hand: alloc::vec::Vec<Chip> = demo_hand
            .into_iter()
            .filter_map(|id| chips.by_id(id))
            .collect();

        Self {
            field,
            results,
            hud,
            custom_assets,
            custom: None,
            chips,
            deck,
            hand,
            hand_at: 0,
            chip_in_use: None,
            sword_in: None,
            step_home: None,
            step_ghost: None,
            step_ghost2: None,
            step_ghost2_key: None,
            step_ghost2_sword: None,
            step_sword_art: None,
            step_trail: [((0, 0), (0, 0)); 4],
            step_trail_sword: [None; 4],
            step_dest: (0, 0),
            presentation: None,
            bubble: None,
            vulcan_gun: None,
            bombs: Vec::new(),
            panels,
            bg,
            backdrop: crate::backdrop::Backdrop::new(crate::BACKDROP),
            hud_tiles: crate::hudtiles::HudTiles::new(crate::HUD_TILES),
            hp_shown: core::iter::once(Counter::new(megaman.hp()))
                .chain(enemies.iter().map(|e| Counter::new(e.hp())))
                .collect(),
            megaman,
            enemies,
            ais,
            gunner_ctl,
            impacts,
            effects,
            shots,
            glow,
            glow_state,
            charge,
            cross_shape,
            intro_fade,
            intro_next,
            gauge,
            gauge_pause,
            results_delay,
            shown,
            fade_out,
            clock,
            moves,
            auto_ticks,
        }
    }

    /// Run one frame of battle logic. Returns true once the results window
    /// has been dismissed and its fade-out has completed, so the caller can
    /// start the next battle.
    pub fn update(&mut self, input: &ButtonController, gfx: &Graphics) -> bool {
        #[cfg(not(feature = "demo-sterile"))]
        {
            self.backdrop.update();
            self.hud_tiles.set_hp(self.megaman.hp());
            self.hud_tiles.set_gauge(self.gauge, GAUGE_FULL);
        }
        // Once either side is deleted the fight is decided: the game goes to
        // its results, which are not built yet, so here the field just holds.
        // The sterile arena never concludes: MegaMan is alone, so the
        // all-enemies-deleted win would fire vacuously -- keep the fight open
        // so a chip animation can be captured for as long as needed.
        let over = if cfg!(feature = "demo-sterile") {
            false
        } else {
            self.megaman.is_defeated() || self.enemies.iter().all(|e| e.is_defeated())
        };

        // The gauge only runs while the fight does; a full gauge holds
        // everything, including itself, through the chimes and then the
        // chip window, which takes banks 9-15 while it is up.
        if let Some(window) = self.custom.as_mut() {
            if window.update(input, gfx) {
                // The picks leave the deck (sub_80293F8) and become the hand.
                self.hand.clear();
                self.hand_at = 0;
                for offer in window.hand() {
                    self.deck.take(offer.deck_index);
                    self.hand.push(offer.chip);
                }
                self.custom = None;
                for (i, p) in self.results.palettes().iter().enumerate() {
                    gfx.set_background_palette(custom::BANK + i as u8, p);
                }
                // The window borrows banks 9-15, and the gauge's is 9, so it
                // goes back last. On the real ROM the window covers this whole
                // layer while it is up, which is why they can share a bank.
                gfx.set_background_palette(
                    crate::hudtiles::GAUGE_BANK,
                    &self.hud_tiles.gauge_palette(),
                );
                {
                }
                self.gauge = 0;
            }
        } else if self.gauge_pause > 0 {
            self.gauge_pause -= 1;
            if self.gauge_pause == 0 {
                // The survivors pack to the front and the first five are
                // offered (sub_802945A, sub_8027EE8).
                self.deck.compact();
                let offered: alloc::vec::Vec<Offer> = self
                    .deck
                    .offer(custom::OFFERED)
                    .iter()
                    .enumerate()
                    .filter_map(|(deck_index, &entry)| {
                        self.chips
                            .by_id(Deck::id(entry))
                            .map(|chip| Offer { chip, deck_index })
                    })
                    .collect();
                self.custom = Some(self.custom_assets.open(&offered, gfx));
            }
        } else if !over && self.intro_fade == 0 && self.intro_next >= self.enemies.len() {
            // Debug: L or R opens the chip window at once, without waiting for
            // the gauge to refill (test aid; the game has no such button).
            if cfg!(debug_assertions)
                && (input.is_just_pressed(Button::L) || input.is_just_pressed(Button::R))
            {
                self.gauge_pause = 1;
            } else {
                self.gauge = (self.gauge + GAUGE_STEP).min(GAUGE_FULL);
                if self.gauge == GAUGE_FULL {
                    self.gauge_pause = GAUGE_PAUSE;
                }
            }
        }
        // Bring the field in, then the enemies one by one.
        let intro = if self.intro_fade > 0 {
            self.intro_fade -= 1;
            true
        } else if self.intro_next < self.enemies.len() {
            if !self.enemies[self.intro_next].is_present() {
                self.enemies[self.intro_next].appear();
            } else if !self.enemies[self.intro_next].is_busy() {
                self.intro_next += 1;
            }
            true
        } else {
            false
        };
        let presenting = self.presentation.is_some();
        let paused =
            over || self.gauge_pause > 0 || self.custom.is_some() || intro || presenting;
        if !paused {
            self.clock += 1;
        }
        if over && self.shown.is_none() && self.fade_out == 0 {
            if self.results_delay > 0 {
                self.results_delay -= 1;
            } else {
                let won = !self.megaman.is_defeated();
                let level = results::busting_level(&results::Tally {
                    time: self.clock,
                    hits_taken: self.megaman.hits_taken(),
                    moves: self.moves,
                });
                self.shown = Some(self.results.show(
                    if won { results::WIN } else { results::LOSE },
                    self.clock,
                    level,
                    0,
                ));
            }
        }
        if let Some(window) = self.shown.as_mut() {
            let confirm = input.is_pressed(Button::A) || input.is_pressed(Button::Start);
            if let Some(fade) = window.update(confirm) {
                self.fade_out = fade;
                if fade == 16 {
                    self.shown = None;
                }
            }
        }
        // The fade-out ends on full black; the next battle's intro fades the
        // field back in from there.
        if self.fade_out == 16 {
            return true;
        }

        for (button, dx, dy) in [
            (Button::Right, 1, 0),
            (Button::Left, -1, 0),
            (Button::Down, 0, 1),
            (Button::Up, 0, -1),
        ] {
            if input.is_just_pressed(button) && !paused {
                let blocked = self
                    .enemies
                    .iter()
                    .filter(|e| e.is_present())
                    .fold(self.panels.other_half(false), |m, e| m | e.occupancy());
                if self.megaman.step(dx, dy, blocked) {
                    self.moves = self.moves.saturating_add(1);
                }
            }
        }
        // Select cracks the panel underfoot, a test aid with no counterpart
        // in the game. Step off a cracked panel and it gives way, then comes
        // back on its own after ten seconds.
        if input.is_just_pressed(Button::Select) {
            let (col, row) = self.megaman.panel();
            self.panels.crack(col, row);
        }
        // B is the buster (pwrAtkRelated_readsFromJoypad_8012FC8,
        // asm00_2.s:9332: JOYPAD_B sets the buster flag; A is the chip
        // button, asm00_2.s:9492). It fires on the press; holding it
        // charges, and a release at full charge fires again, harder
        // (sub_8012EBC, asm00_2.s:9059).
        if !paused {
            // A uses the next chip of the hand when the navi is free
            // (asm00_2.s:9492-9518: AIData flag 4 when the hand has a chip).
            if input.is_just_pressed(Button::A)
                && !self.megaman.is_busy()
                && self.hand_at < self.hand.len()
            {
                let chip = self.hand[self.hand_at];
                self.hand_at += 1;
                self.use_chip(chip);
            }
            if input.is_just_pressed(Button::B) && !self.megaman.is_busy() {
                self.megaman.attack(actor::BUSTER);
            }
            if input.is_pressed(Button::B) {
                self.charge = self.charge.saturating_add(1);
            } else {
                if self.charge >= CHARGE_FRAMES {
                    self.megaman.attack_charged();
                }
                self.charge = 0;
            }
        }
        // The demo-auto harness: MegaMan fires the hand chips on a repeating
        // timer, so a capture run does not rely on key timing. It waits for
        // the fight to open, a free navi and a chip, and spaces each use by
        // AUTO_FIRE_GAP so the pose and shot play out between shots. The demo
        // hand is cycled forever (hand_at wraps) and the custom window is never
        // allowed to open, so a capture run keeps shooting the featured chip
        // instead of dropping into a chip select that empties the demo hand.
        #[cfg(feature = "demo-auto")]
        if !paused && self.intro_next >= self.enemies.len() {
            self.gauge = 0;
            if self.auto_ticks > 0 {
                self.auto_ticks -= 1;
            } else if !self.megaman.is_busy() && !self.hand.is_empty() {
                let chip = self.hand[self.hand_at];
                self.hand_at = (self.hand_at + 1) % self.hand.len();
                self.use_chip(chip);
                self.auto_ticks = AUTO_FIRE_GAP;
            }
        }

        let state = match self.charge {
            c if c >= CHARGE_FRAMES => 2,
            c if c >= CHARGING_FROM => 1,
            _ => 0,
        };
        if state != self.glow_state {
            self.glow_state = state;
            if state != 0 {
                self.glow.play(state);
            }
        }
        self.glow.update();

        // Shots tick before the actors, so one spawned this frame first moves
        // next frame, as with an object appended to bn6f's running update.
        let mut i = 0;
        while i < self.shots.len() {
            // A hitbox hits whoever is on the panel it arrives on: the
            // player's shots hit enemies and are spent, an enemy's wave hits
            // the player and rolls on. Off the field, both are spent. Arrival
            // is checked before the shot advances, so the panel it spawns on
            // counts too -- a point-blank target is hit on the first frame.
            let arrived = self.shots[i].just_arrived();
            let mut spent = !self.shots[i].update();
            if !spent && arrived {
                let at = (self.shots[i].col, self.shots[i].row);
                let mut hit = false;
                if self.shots[i].from_player {
                    for enemy in self.enemies.iter_mut().filter(|e| e.is_targetable()) {
                        if enemy.panel() == at {
                            enemy.take_damage(self.shots[i].damage);
                            hit = true;
                        }
                    }
                } else if self.megaman.is_targetable() && self.megaman.panel() == at {
                    self.megaman.take_damage(self.shots[i].damage);
                    hit = true;
                }
                spent = hit && !self.shots[i].piercing;
            }
            if spent {
                self.shots.swap_remove(i);
            } else {
                i += 1;
            }
        }

        // The sword itself is a t1_0x5 object spawned as the slash pose
        // begins (sub_80EB862, asm31.s:109041-109070): byte_80B8BD4 row 3
        // -> effect list off_8031E00[0] = sprite_82EFE48, animation 0 (a
        // spark above the head for eight frames, the blade through the
        // swing, its tip held), riding the navi's origin with no arm
        // offset, alive until the attack state exits; its frames run from
        // the pose's first frame (real ROM: spark c2-9, blade c10-11,
        // 12-13, 14-15, 16-17, 18-19, tip from c20; TRANSFER.md 7b).
        if let Some(left) = self.sword_in {
            if left == 0 {
                self.sword_in = None;
                let (mc, mr) = self.megaman.panel();
                // The sword object is byte_80B8BD4's row for the chip's
                // subfamily (byte_80EBB64, asm31.s:109348): row 3 is
                // sprite_82EFE48 for the plain swords, rows 0x19-0x1b its
                // fire, aqua and elec counterparts, and row 0x1c is
                // sprite_82EFE48 again with palette 2 for BambSwrd.
                let (asset, palette) = match self.chip_in_use.map(|c| c.id) {
                    Some(CHIP_FIRESWRD) => (FIRE_SWORD, 0),
                    Some(CHIP_AQUASWRD) => (AQUA_SWORD, 0),
                    Some(CHIP_ELECSWRD) => (ELEC_SWORD, 0),
                    Some(CHIP_BAMBSWRD) => (SWORD_SPR, 2),
                    _ => (SWORD_SPR, 0),
                };
                let mut sword = spr::Player::new(spr::Assets::new(asset), 0);
                sword.set_palette_add(palette);
                self.step_sword_art = Some((asset, palette));
                self.effects.push((
                    sword,
                    field::panel_centre(mc, mr),
                    // Gone with the attack's exit: off screen the frame the
                    // idle is back.
                    SWORD.frames + SWORD.recover,
                    false,
                ));
            } else {
                self.sword_in = Some(left - 1);
            }
        }
        if let Some((chip, left)) = self.presentation {
            if left == 0 {
                self.presentation = None;
                match chip.id {
                    CHIP_INVISIBL => self.megaman.set_invisible(INVISIBL_FRAMES),
                    CHIP_AREAGRAB => {
                        let occupied = self
                            .enemies
                            .iter()
                            .filter(|e| e.is_present())
                            .fold(0, |m, e| m | e.occupancy());
                        for (col, row) in self.panels.steal_column(occupied) {
                            self.panels.highlight(col, row, 0);
                        }
                    }
                    CHIP_BARRIER | CHIP_BARR100 | CHIP_BARR200 => {
                        self.megaman.set_barrier(barrier_hp(chip.id));
                        let mut bubble = spr::Player::new(spr::Assets::new(BARRIER), 0);
                        bubble.set_offsets_follow_shift(true);
                        bubble.set_palette_add(barrier_palette(chip.id));
                        self.bubble = Some(bubble);
                    }
                    _ => {}
                }
            } else {
                self.presentation = Some((chip, left - 1));
            }
        }
        if let Some(bubble) = self.bubble.as_mut() {
            bubble.update();
            if self.megaman.barrier() == 0 {
                self.bubble = None;
            }
        }
        let navi_update = self.megaman.update();
        if let Some((gun, _, _)) = self.vulcan_gun.as_mut() {
            match navi_update {
                // The firing state's first frame is also its first shot.
                Update::PoseBegun | Update::Strike { .. } if gun.anim() == 0 => gun.play(1),
                Update::Recovering => gun.play(2),
                _ => {}
            }
        }
        match navi_update {
            Update::Recovering if self.step_home.is_some() => {
                // Back where it started once the slash is over: the real ROM
                // has the navi home 24 frames into the attack.
                if let Some((col, row)) = self.step_home.take() {
                    self.megaman.warp_to(col, row);
                    // The sword goes with it. On the real ROM the sword's
                    // last frames are drawn over the HOME panel from frame 24
                    // -- OAM has its blade tip at (41,58) there while the far
                    // panel keeps only the afterimage -- so an attack object
                    // follows the navi rather than staying where it spawned.
                    let home = field::panel_centre(col, row);
                    for (_, pos, _, _) in self.effects.iter_mut() {
                        *pos = home;
                    }
                    // The far panel does keep a sword copy after the return
                    // -- 68 px of one on every blink frame from 24 on -- but
                    // not the frame this holds: keeping this one costs 173 px
                    // a frame instead of 68, so it is dropped until the right
                    // frame is known.
                    self.step_ghost2_sword = None;
                }
            }
            Update::Strike { .. } if self.chip_in_use.is_some() => {
                let chip = self.chip_in_use.take().unwrap();
                self.chip_strike(chip);
            }
            Update::Strike { charged } => {
                let (col, row) = self.megaman.front_panel();
                let damage = if charged {
                    CHARGED_DAMAGE
                } else {
                    BUSTER_DAMAGE
                };
                self.shots.push(Shot::buster(
                    spr::Assets::new(SHOTFX),
                    col,
                    row,
                    self.megaman.facing_dx(),
                    damage,
                ));
            }
            Update::Died => {
                let at = field::panel_centre(self.megaman.panel().0, self.megaman.panel().1);
                self.effects
                    .push((spr::Player::new(spr::Assets::new(DELETE), 0), at, 90, false));
            }
            _ => {}
        }
        // Each enemy may not move onto a panel any other object holds.
        let held: Vec<u32> = self
            .enemies
            .iter()
            .map(|e| if e.is_present() { e.occupancy() } else { 0 })
            .collect();
        let all_held = held.iter().fold(self.megaman.occupancy(), |m, h| m | h);
        for ((i, enemy), ai) in self
            .enemies
            .iter_mut()
            .enumerate()
            .zip(self.ais.iter_mut())
            .filter(|((_, e), _)| e.is_present())
        {
            if matches!(ai.style(), ai::Style::Gunner) {
                if !paused && self.megaman.is_targetable() {
                    self.gunner_ctl.update(
                        enemy,
                        self.megaman.panel(),
                        spr::Assets::new(CURSOR),
                        &mut self.impacts,
                        || spr::Assets::new(IMPACT),
                    );
                }
                enemy.update();
                continue;
            }
            if !paused && !enemy.is_busy() && self.megaman.is_targetable() {
                let blocked = (all_held & !held[i]) | self.panels.other_half(true);
                // Decided as the attack begins, as the game does, and held for
                // its duration even if the player moves.
                self.cross_shape = ai::cross_targets(self.megaman.panel());
                ai.update(enemy, self.megaman.panel(), blocked);
            }
            let update = enemy.update();
            // ProtoMan's strike lands on the panel in front and Colonel's
            // slashes on the cross shape or the whole front column
            // (dword_8103B00, asm31.s:158257). Both navis light their targets
            // every eighth frame of the wind-up (asm31.s:142671, 157045);
            // Colonel's overhead slash borrows the same telegraph.
            let targets: Vec<(i32, i32)> = match ai.style() {
                ai::Style::Thrust | ai::Style::Mettaur | ai::Style::Gunner => {
                    alloc::vec![enemy.front_panel()]
                }
                ai::Style::Divide => match self.cross_shape {
                    Some(shape) => shape
                        .iter()
                        .map(|(dx, dy)| (ai::CROSS_BASE.0 + dx, ai::CROSS_BASE.1 + dy))
                        .collect(),
                    None => (1..=field::ROWS)
                        .map(|row| (field::half(false).1, row))
                        .collect(),
                },
            };
            match update {
                Update::Winding { frame }
                    if frame % 8 == 0 && !matches!(ai.style(), ai::Style::Mettaur) =>
                {
                    for &(col, row) in &targets {
                        if (1..=field::COLS).contains(&col) && (1..=field::ROWS).contains(&row) {
                            self.panels.highlight(col, row, 0);
                        }
                    }
                }
                Update::Died => {
                    let at = field::panel_centre(enemy.panel().0, enemy.panel().1);
                    self.effects
                        .push((spr::Player::new(spr::Assets::new(DELETE), 0), at, 90, false));
                }
                // The Mettaur's strike is a wave set rolling from the front
                // panel; the swords land on their targets at once.
                Update::Strike { .. } if matches!(ai.style(), ai::Style::Mettaur) => {
                    let (col, row) = enemy.front_panel();
                    self.shots.push(Shot::shockwave(
                        spr::Assets::new(WAVE),
                        col,
                        row,
                        enemy.facing_dx(),
                        WAVE_DAMAGE,
                    ));
                }
                Update::Strike { .. } if self.megaman.is_targetable() => {
                    if targets.contains(&self.megaman.panel()) {
                        let damage = match ai.style() {
                            ai::Style::Thrust => SWORD_DAMAGE,
                            ai::Style::Divide if self.cross_shape.is_some() => CROSS_DAMAGE,
                            ai::Style::Divide => DIVIDE_DAMAGE,
                            ai::Style::Mettaur | ai::Style::Gunner => WAVE_DAMAGE,
                        };
                        self.megaman.take_damage(damage);
                    }
                }
                _ => {}
            }
        }

        // The Gunner's shots warn on their panels, then land.
        self.impacts
            .retain_mut(|imp| match imp.update(&mut self.panels) {
                Some(true) => {
                    if self.megaman.is_targetable() && self.megaman.panel() == (imp.col, imp.row) {
                        self.megaman.take_damage(gunner::DAMAGE);
                    }
                    true
                }
                Some(false) => true,
                None => false,
            });

        if let Some((gun, _, ticks)) = self.vulcan_gun.as_mut() {
            gun.update();
            if *ticks == 0 {
                self.vulcan_gun = None;
            } else {
                *ticks -= 1;
            }
        }
        for (counter, hp) in self.hp_shown.iter_mut().zip(
            core::iter::once(self.megaman.hp()).chain(self.enemies.iter().map(|e| e.hp())),
        ) {
            counter.update(hp);
        }
        // The afterimage is spawned on the attack's frame 0 and ages from
        // there; it is gone after frame 18.
        if let Some((_, _, age)) = self.step_ghost.as_mut() {
            *age += 1;
            let age = *age;
            let (mcol, mrow) = self.megaman.panel();
            self.step_trail[age as usize % 4] =
                (self.megaman.sprite_key(), field::panel_centre(mcol, mrow));
            if age == STEP_GHOST2_FIRST {
                self.step_dest = field::panel_centre(mcol, mrow);
            }
            self.step_trail_sword[age as usize % 4] =
                self.effects.first().map(|(p, _, _, _)| p.frame_key());
            // Refreshed on the first frame of each blink pair and held for
            // the second: on frames 16 AND 17 the real copy carries the
            // navi's frame-13 sprite, not 13 and then 14.
            // It stops taking new frames once the navi has gone home: from
            // then on it holds the last pose the navi had on that panel.
            if age >= STEP_GHOST2_FIRST && (age - STEP_GHOST2_FIRST) % 4 == 0 {
                // Three frames back is the next slot round the ring of four,
                // and only while the navi was still on the far panel then.
                let (delayed, was_at) = self.step_trail[(age as usize + 1) % 4];
                if self.step_ghost2_key != Some(delayed) && was_at == self.step_dest {
                    let mut ghost =
                        spr::Player::frozen_at(spr::Assets::new(MEGAMAN), delayed.0, delayed.1);
                    ghost.set_red_only(true);
                    let at = self.step_dest;
                    self.step_ghost2 = Some((ghost, at));
                    self.step_ghost2_key = Some(delayed);
                    self.step_ghost2_sword = match (
                        self.step_trail_sword[(age as usize + 1) % 4],
                        self.step_sword_art,
                    ) {
                        (Some((anim, f)), Some((art, pal))) => {
                            let mut g = spr::Player::frozen_at(spr::Assets::new(art), anim, f);
                            g.set_palette_add(pal);
                            g.set_red_only(true);
                            Some((g, at))
                        }
                        _ => None,
                    };
                }
            }
            if age > STEP_STATE_LAST {
                self.step_ghost = None;
                self.step_ghost2 = None;
                self.step_ghost2_key = None;
                self.step_ghost2_sword = None;
                self.step_sword_art = None;
            }
        }
        // An effect with N frames is drawn for N frames, this one included.
        self.effects.retain_mut(|(p, _, ticks, _)| {
            p.update();
            let alive = *ticks > 0;
            *ticks = ticks.saturating_sub(1);
            alive
        });
        // A bomb that lands bursts on its panel (sub_80C5DBC's fuse of zero:
        // the blast, setCollisionRegion(1), then sprite 0x26's animation 0).
        let mut landed = Vec::new();
        self.bombs.retain_mut(|b| {
            b.player.update();
            b.step();
            b.ticks += 1;
            if b.ticks >= b.flight {
                landed.push((b.target, b.damage, b.wide));
                false
            } else {
                true
            }
        });
        for ((col, row), damage, wide) in landed {
            // The landing panel, and its eight neighbours for BigBomb.
            // The nine puffs overlap, so the order they are pushed decides
            // which seams show. Effects are drawn last-pushed-first, so this
            // list runs back to front. Read straight out of the real ROM's
            // OAM on a blast frame (`--dump 0x7000000:1024`): its nine puffs
            // occupy OAM in the order centre, left, right of the FRONT row,
            // then centre, right, left of the middle row, then centre, right,
            // left of the back row, lowest index on top.
            let spread: &[(i32, i32)] = if wide {
                &[
                    (-1, -1),
                    (1, -1),
                    (0, -1),
                    (-1, 0),
                    (1, 0),
                    (0, 0),
                    (1, 1),
                    (-1, 1),
                    (0, 1),
                ]
            } else {
                &[(0, 0)]
            };
            for (dc, dr) in spread {
                let (c, r) = (col + dc, row + dr);
                if !(1..=field::COLS).contains(&c) || !(1..=field::ROWS).contains(&r) {
                    continue;
                }
                for enemy in self.enemies.iter_mut().filter(|e| e.is_targetable()) {
                    if enemy.panel() == (c, r) {
                        enemy.take_damage(damage);
                    }
                }
                // Spawned after this frame's effect tick, so take this
                // frame's tick now: the blast's first frame then runs its
                // duration from this frame like every other effect.
                let mut blast = spr::Player::new(spr::Assets::new(BOMB_BLAST), 0);
                blast.update();
                self.effects
                    .push((blast, field::panel_centre(c, r), BLAST_FRAMES - 1, false));
            }
        }

        let occupied = self
            .enemies
            .iter()
            .filter(|e| e.is_targetable())
            .fold(self.megaman.occupancy(), |m, e| m | e.occupancy());
        self.panels.update(occupied);
        // The sterile arena draws the same field as the real ROM, so the panels
        // are repainted each frame and cancel in the per-pixel diff.
        for (col, row) in field::panels_in(self.panels.take_dirty()) {
            match self.panels.flashing(col, row) {
                Some(which) => self.field.draw_highlight(&mut self.bg, col, row, which),
                None => {
                    self.field.draw_panel(
                        &mut self.bg,
                        col,
                        row,
                        self.panels.animation(col, row),
                        self.panels.enemy_owned(col, row),
                    )
                }
            }
        }

        false
    }

    /// Draw the frame for the state `update` has just advanced. The caller
    /// commits it.
    /// Start a chip: the attack chips set their pose and strike later; the
    /// rest take effect at once. Ids the fight cannot use yet are consumed
    /// without effect.
    fn use_chip(&mut self, chip: Chip) {
        match chip.id {
            CHIP_SWORD | CHIP_WIDESWRD | CHIP_LONGSWRD | CHIP_WIDEBLDE | CHIP_LONGBLDE
            | CHIP_MURAMASA | CHIP_STEPSWRD | CHIP_FIRESWRD | CHIP_AQUASWRD
            | CHIP_ELECSWRD | CHIP_BAMBSWRD => {
                // StepSwrd's first attack parameter is 1, which sends the
                // sword family's state 0 through sub_8015B00: it reserves a
                // panel across the boundary and moves the navi there before
                // the slash (asm31.s:108790-108826). Against the real ROM the
                // navi's own colours sit on the enemy's front column from the
                // attack's first frame through its 24th, then it is home
                // again, and the slash is pixel-identical. What the home panel
                // holds meanwhile is an afterimage: see step_ghost below.
                if chip.id == CHIP_STEPSWRD {
                    let (col, row) = self.megaman.panel();
                    let dx = self.megaman.facing_dx();
                    let (lo, hi) = self.panels.half(true, row);
                    let step_to = if dx > 0 { lo } else { hi };
                    if !(1..=field::COLS).contains(&step_to) {
                        // Nowhere to step: the slash happens where it stands.
                    } else {
                        self.step_home = Some((col, row));
                        self.megaman.warp_to(step_to, row);
                        let mut ghost =
                            spr::Player::new(spr::Assets::new(MEGAMAN), actor::anim::IDLE);
                        ghost.set_red_only(true);
                        self.step_ghost = Some((ghost, field::panel_centre(col, row), 0));
                    }
                }
                self.chip_in_use = Some(chip);
                self.megaman.attack(if chip.id == CHIP_STEPSWRD { STEP_SWORD } else { SWORD });
                self.sword_in = Some(SWORD.windup.map_or(0, |(_, f)| f));
            }
            CHIP_MINIBOMB | CHIP_BLKBOMB | CHIP_BIGBOMB | CHIP_ENERGBOM | CHIP_MEGENBOM => {
                self.chip_in_use = Some(chip);
                self.megaman.attack(THROW);
                let (mc, mr) = self.megaman.panel();
                let mut held = spr::Player::new(spr::Assets::new(MINIBOMB), bomb_anim(chip.id, false));
                held.set_palette_add(bomb_palette(chip.id, false));
                self.effects.push((
                    held,
                    field::panel_centre(mc, mr),
                    HELD_BOMB_FRAMES,
                    false,
                ));
            }
            CHIP_CANNON | CHIP_HICANNON | CHIP_MCANNON => {
                self.chip_in_use = Some(chip);
                self.megaman.attack(CANNON);
                // The barrel is the t1_0x5 object spawned on the navi's arm
                // as the pose begins (sub_80EBC28 ->
                // spawn_t1_0x5_tempAttackObject_80B8E30, asm31.s:109468),
                // sprite_82F39C0 animation 0: five blank frames, three of
                // white silhouette, the green barrel, the muzzle orb growing
                // over the shot at counter 0xf, the cyan discharge, then the
                // plain barrel until the pose ends at 0x1d. Every frame of
                // that sequence, at those counters, was confirmed against the
                // real ROM's capture (TRANSFER.md), which is also where the
                // anchor comes from: the barrel's box is x 74-96, y 75-90 on
                // the navi at panel (2,2).
                let (mc, mr) = self.megaman.panel();
                let (mx, my) = field::panel_centre(mc, mr);
                let mut barrel = spr::Player::new(spr::Assets::new(BARREL_CHARGE), 0);
                // byte_80B8BD4 rows 0-2: the same barrel with palette 0, 1
                // and 2 for Cannon, HiCannon and M-Cannon.
                barrel.set_palette_add((chip.id - CHIP_CANNON) as usize);
                self.effects
                    .push((barrel, (mx + 16, my - 24), CANNON_FRAMES, false));
            }
            CHIP_VULCAN | CHIP_VULCAN2 | CHIP_VULCAN3 | CHIP_SUPRVULC => {
                self.chip_in_use = Some(chip);
                let shots = vulcan_shots(chip.id);
                self.megaman.attack(vulcan(shots));
                let (mc, mr) = self.megaman.panel();
                let (mx, my) = field::panel_centre(mc, mr);
                let dx = self.megaman.facing_dx();
                self.vulcan_gun = Some((
                    spr::Player::new(spr::Assets::new(VULCAN_GUN), 0),
                    (mx + dx * VULCAN_ARM.0, my + VULCAN_ARM.1),
                    vulcan_gun_frames(shots),
                ));
            }
            CHIP_AIRSHOT => {
                self.chip_in_use = Some(chip);
                self.megaman.attack(AIRSHOT);
                let (mc, mr) = self.megaman.panel();
                let (mx, my) = field::panel_centre(mc, mr);
                let dx = self.megaman.facing_dx();
                self.effects.push((
                    spr::Player::new(spr::Assets::new(AIRSHOT_BARREL), 0),
                    (mx + dx * AIRSHOT_ARM.0, my + AIRSHOT_ARM.1),
                    AIRSHOT_FRAMES,
                    false,
                ));
            }
            CHIP_RECOV10 | CHIP_RECOV30 | CHIP_RECOV50 | CHIP_RECOV80 | CHIP_RECOV120
            | CHIP_RECOV150 | CHIP_RECOV200 | CHIP_RECOV300 => {
                self.megaman
                    .heal(RECOV_HP[(chip.id - CHIP_RECOV10) as usize]);
                // The heal (sub_800E2FC, object.s:4685) adds the HP and
                // spawns type-4 effect row 6 at the navi's coordinates:
                // byte_80E0398 row 6 = effect list 0xC index 0x12, animation
                // 0, gone when the animation ends.
                let (mc, mr) = self.megaman.panel();
                self.effects.push((
                    spr::Player::new(spr::Assets::new(HEAL), 0),
                    field::panel_centre(mc, mr),
                    HEAL_FRAMES,
                    true,
                ));
            }
            CHIP_INVISIBL => self.presentation = Some((chip, INVISIBL_PRESENTATION)),
            CHIP_BARRIER | CHIP_BARR100 | CHIP_BARR200 => {
                self.presentation = Some((chip, BARRIER_PRESENTATION))
            }
            // AreaGrab needs per-panel ownership, which the field does not
            // track yet. The stand-in is nothing.
            // AreaGrab takes the enemy's front-most column, a row at a time
            // (sub_80E0754, asm31.s:85444, with the chip's first parameter
            // set); it is a presentation chip, so the fight holds first.
            CHIP_AREAGRAB => self.presentation = Some((chip, AREAGRAB_PRESENTATION)),
            _ => {
                self.chip_in_use = Some(chip);
                self.megaman.attack(actor::BUSTER);
            }
        }
    }

    /// The chip's hit, on the frame its pose delivers it.
    fn chip_strike(&mut self, chip: Chip) {
        let (col, row) = self.megaman.panel();
        let dx = self.megaman.facing_dx();
        match chip.id {
            CHIP_SWORD | CHIP_WIDESWRD | CHIP_LONGSWRD | CHIP_WIDEBLDE | CHIP_LONGBLDE
            | CHIP_MURAMASA | CHIP_STEPSWRD | CHIP_FIRESWRD | CHIP_AQUASWRD
            | CHIP_ELECSWRD | CHIP_BAMBSWRD => {
                let mut panels: Vec<(i32, i32)> = Vec::new();
                // The hit shape is byte_80EBA18's first byte per subfamily
                // (asm31.s:109246): 1 the panel ahead, 4 the column ahead,
                // 2 two panels ahead; the elemental swords are all 4.
                match chip.id {
                    CHIP_WIDESWRD | CHIP_WIDEBLDE | CHIP_STEPSWRD | CHIP_FIRESWRD
                    | CHIP_AQUASWRD
                    | CHIP_ELECSWRD | CHIP_BAMBSWRD => {
                        panels.extend((1..=field::ROWS).map(|r| (col + dx, r)))
                    }
                    CHIP_LONGSWRD | CHIP_LONGBLDE | CHIP_MURAMASA => {
                        panels.extend([(col + dx, row), (col + 2 * dx, row)])
                    }
                    _ => panels.push((col + dx, row)),
                }
                // With the hit region the strike spawns the slash arc: a
                // type-4 effect object at the front panel's coordinates,
                // 0x10 up, table row byte_80EBAD8[subfamily] of byte_80E0398
                // (asm31.s:109180-109200) -- effect list entry 0x14
                // (sprite_830F144), its animation 2 for Sword, 0 for WideSwrd,
                // 1 for LongSwrd -- gone when the animation ends.
                // The arc's animation is byte_80EBAD8 per subfamily
                // (asm31.s:109264): 0x18 for Sword, 0x16 for WideSwrd and
                // every elemental sword, 0x17 for LongSwrd.
                // byte_80EBAD8's row per subfamily indexes byte_80E0398:
                // rows 0x16/0x17/0x18 are the arc's animations 0/1/2 in
                // palette 0, and the blades' rows 0x19/0x1a are animations
                // 0 and 1 in palette 5 (asm31.s:85787).
                let (arc_anim, blade_palette) = match chip.id {
                    CHIP_LONGSWRD => (1, 0),
                    CHIP_SWORD => (2, 0),
                    CHIP_WIDEBLDE => (0, 5),
                    CHIP_LONGBLDE => (1, 5),
                    // Muramasa's row 0x2d: the same animation as LongBlde's
                    // in palette 6.
                    CHIP_MURAMASA => (1, 6),
                    _ => (0, 0),
                };
                let (fx, fy) = field::panel_centre(col + dx, row);
                // The elemental swords add their palette: the strike ORs
                // (subfamily - 0xb) into the spawn's Param3, which the
                // effect object adds to the sprite's palette
                // (asm31.s:109198-109206; sub_80E0568, asm31.s:85852).
                let arc_palette = match chip.id {
                    CHIP_FIRESWRD => 1,
                    CHIP_AQUASWRD => 2,
                    CHIP_ELECSWRD => 3,
                    CHIP_BAMBSWRD => 4,
                    _ => blade_palette,
                };
                let mut arc = spr::Player::new(spr::Assets::new(SWORD_ARC), arc_anim);
                arc.set_palette_add(arc_palette);
                self.effects
                    .push((arc, (fx, fy - 0x10), SWORD_ARC_FRAMES[arc_anim], true));
                for enemy in self.enemies.iter_mut().filter(|e| e.is_targetable()) {
                    if panels.contains(&enemy.panel()) {
                        enemy.take_damage(chip.power);
                    }
                }
            }
            CHIP_MINIBOMB | CHIP_BLKBOMB | CHIP_BIGBOMB | CHIP_ENERGBOM | CHIP_MEGENBOM => {
                let (mx, my) = field::panel_centre(col, row);
                let target = ((col + 3 * dx).clamp(1, field::COLS), row);
                // BlkBomb's thrown ball is its own sprite, not the bomb
                // sprite in another palette: a dark brown ball with a fuse
                // and a ground shadow, three parts in one frame. Identified
                // by taking its tiles out of OBJ VRAM mid-flight and finding
                // those exact bytes in byte_831FA84.spr, the only one of the
                // 97 sprite files that holds them.
                let mut thrown = if chip.id == CHIP_BLKBOMB {
                    spr::Player::new(spr::Assets::new(BLKBOMB), 0)
                } else {
                    spr::Player::new(spr::Assets::new(MINIBOMB), bomb_anim(chip.id, true))
                };
                thrown.set_palette_add(bomb_palette(chip.id, true));
                self.bombs.push(Bomb {
                    player: thrown,
                    wide: chip.id == CHIP_BIGBOMB,
                    flight: if chip.id == CHIP_BLKBOMB { BLKBOMB_FLIGHT } else { BOMB_FLIGHT },
                    x: (mx << 16) + dx * BOMB_SPAWN_AHEAD,
                    y: my << 16,
                    z: BOMB_SPAWN_UP,
                    vx: if chip.id == CHIP_BLKBOMB { dx * BLKBOMB_VX } else { dx * BOMB_VX },
                    vz: if chip.id == CHIP_BLKBOMB { BLKBOMB_VZ } else { BOMB_VZ },
                    target,
                    damage: chip.power,
                    ticks: 0,
                });
            }
            // Vulcan1: three shots, each fanned a little above or below the
            // row they were aimed at (dword_80EBFF0 = 0x20181008, one byte per
            // shot, chosen by the game's RNG & 3; the three here cycle through
            // them in order) and released 0xa frames apart, the game's fire
            // period (sub_80EBF6E). Each travels one panel a frame through
            // Shot::vulcan (sub_80EBF6E -> spawn_t3_0x12_80C6ADA,
            // t3_0x12_80C6946).
            // AirShot's hitbox lands on the panel ahead at once and shoves
            // what it hits one panel back; the shove is the hop the field
            // already has, its own timing not yet taken from the game.
            CHIP_AIRSHOT => {
                let (fc, fr) = self.megaman.front_panel();
                let blocked = self
                    .enemies
                    .iter()
                    .fold(self.megaman.occupancy(), |m, e| m | e.occupancy())
                    | self.panels.other_half(true);
                for enemy in self.enemies.iter_mut().filter(|e| e.is_targetable()) {
                    if enemy.panel() == (fc, fr) && enemy.take_damage(chip.power) {
                        enemy.hop(dx, 0, blocked);
                    }
                }
            }
            CHIP_VULCAN | CHIP_VULCAN2 | CHIP_VULCAN3 | CHIP_SUPRVULC => {
                const FAN: [i32; 4] = [0x08, 0x10, 0x18, 0x20];
                let (fc, fr) = self.megaman.front_panel();
                // Shots per chip, from the subfamily (dword_80EBFEC =
                // 0xA050403: Vulcan1 3, Vulcan2 4, Vulcan3 5,
                // asm31.s:109878-109892).
                for i in 0..vulcan_shots(chip.id) as usize {
                    self.shots.push(Shot::vulcan(
                        spr::Assets::new(SHOTFX),
                        fc,
                        fr,
                        dx,
                        chip.power,
                        FAN[i % FAN.len()],
                        (i as u8) * 0xa,
                    ));
                }
            }
            // The cannon family's arm barrel: the game spawns a t1_0x5
            // object on the navi's arm that plays this charge animation while
            // the navi holds the pose (sub_80EBC28 -> spawn_t1_0x5,
            // asm31.s:109468; the barrel is effect-list sprite slot 1,
            // byte_82F39C0, anim 0 for the player). It sits at the front of
            // the navi's panel and flashes the orb up to the shot, which the
            // default arm below then fires.
            // The cannon's shot spawns off the front panel at the strike
            // The cannon's shot is the big yellow-outlined white orb
            // (byte_82FE704 anim 0), spawned off the front panel at the strike
            // (counter 0xf, asm31.s:109531). The barrel itself was spawn at
            // the start of the pose in use_chip, so only the shot runs here.
            CHIP_CANNON | CHIP_HICANNON | CHIP_MCANNON => {
                let (fc, fr) = self.megaman.front_panel();
                self.shots
                    .push(Shot::cannon(spr::Assets::new(CANNON_ORB), fc, fr, dx, chip.power));
            }
            _ => {
                let (fc, fr) = self.megaman.front_panel();
                self.shots
                    .push(Shot::buster(spr::Assets::new(SHOTFX), fc, fr, dx, chip.power));
            }
        }
    }

    pub fn draw(&mut self, frame: &mut GraphicsFrame) {
        // The sterile arena leaves the backdrop out for the same reason it
        // draws a plain field: the real ROM's captures strip their BG layers
        // with --disable-bg, so both sides must be MegaMan on black.
        #[cfg(not(feature = "demo-sterile"))]
        self.backdrop.show(frame);
        // The chip window covers the HUD strip on the real ROM and borrows
        // its palette bank, so this layer stands down while it is up.
        #[cfg(not(feature = "demo-sterile"))]
        if self.custom.is_none() {
            self.hud_tiles.show(frame);
        }
        let bg_id = self.bg.show(frame);
        // Whichever navi is fading -- the deleted player out, an arriving
        // enemy in -- pixelates and thins over the field; the intro's screen
        // fade darkens everything until the field is revealed.
        let window_id = self.shown.as_ref().map(|window| window.show(frame));
        if let Some(window) = &self.custom {
            window.show(frame, self.hud);
        }
        if self.fade_out > 0 {
            let mut fade = frame.blend().darken(Num::from_raw(self.fade_out));
            fade.enable_background(bg_id).enable_object();
            // The window fades with everything else rather than vanishing.
            if let Some(id) = window_id {
                fade.enable_background(id);
            }
        } else if self.intro_fade > 0 {
            let amount = Num::from_raw((self.intro_fade as u8).div_ceil(2));
            frame
                .blend()
                .darken(amount.min(Num::from_raw(16)))
                .enable_background(bg_id)
                .enable_object();
        } else if let Some((mosaic, alpha)) = core::iter::once(&self.megaman)
            .chain(self.enemies.iter())
            .find_map(|a| a.fade())
        {
            frame.mosaic().set_object(mosaic, mosaic);
            frame
                .blend()
                .object_transparency(Num::from_raw(alpha), Num::from_raw(16 - alpha))
                .enable_background(bg_id);
        }
        // Attack objects such as the cannon barrel draw over the navi that
        // spawned them (the real ROM shows the barrel covering the arm), and
        // a later one over an earlier one: the sword's arc, spawned at the
        // strike, covers the sword object spawned at the pose's start.
        for (p, (x, y), _) in self.vulcan_gun.iter() {
            for part in p.parts().iter().rev() {
                Object::new(part.sprite.clone())
                    .set_priority(Priority::P2)
                    .set_pos((x + part.x, y + part.y))
                    .set_hflip(part.hflip)
                    .set_vflip(part.vflip)
                    .show(frame);
            }
        }
        // Two frames shown, two hidden, from the attack's frame 8.
        if let (Some((p, (x, y))), Some((_, _, age))) =
            (self.step_ghost2.as_ref(), self.step_ghost.as_ref())
        {
            if (STEP_GHOST2_FIRST..=STEP_GHOST2_LAST).contains(age)
                && (*age - STEP_GHOST2_FIRST) % 4 < 2
            {
                for (q, (qx, qy)) in self
                    .step_ghost2_sword
                    .iter()
                    .map(|(q, at)| (q, *at))
                    .chain(core::iter::once((p, (*x, *y))))
                {
                    for part in q.parts().iter().rev() {
                        Object::new(part.sprite.clone())
                            .set_priority(Priority::P2)
                            .set_pos((qx + part.x, qy + part.y))
                            .set_hflip(part.hflip)
                            .set_vflip(part.vflip)
                            .show(frame);
                    }
                }
            }
        }
        // Two frames shown, two hidden, starting on the attack's frame 1.
        if let Some((p, (x, y), age)) = self.step_ghost.as_ref() {
            if *age <= STEP_GHOST_LAST && *age >= 2 && (*age - 2) % 4 < 2 {
                for part in p.parts().iter().rev() {
                    Object::new(part.sprite.clone())
                        .set_priority(Priority::P2)
                        .set_pos((x + part.x, y + part.y))
                        .set_hflip(part.hflip)
                        .set_vflip(part.vflip)
                        .show(frame);
                }
            }
        }
        for (p, (x, y), _, _) in self.effects.iter().rev() {
            for part in p.parts().iter().rev() {
                Object::new(part.sprite.clone())
                    .set_priority(Priority::P2)
                    .set_pos((x + part.x, y + part.y))
                    .set_hflip(part.hflip)
                    .set_vflip(part.vflip)
                    .show(frame);
            }
        }

        for s in &self.shots {
            s.show(frame);
        }
        if !self.megaman.is_defeated() {
            let bubble = self.bubble.as_ref();
            let (mc, mr) = self.megaman.panel();
            let (bx, by) = field::panel_centre(mc, mr);
            // Two pixels forward of the origin on the real ROM.
            let bx = bx + 2 * self.megaman.facing_dx();
            self.megaman.show_with_underlay(frame, |frame| {
                if let Some(bubble) = bubble {
                    for part in bubble.parts().iter().rev() {
                        Object::new(part.sprite.clone())
                            .set_priority(Priority::P2)
                            .set_pos((bx + part.x, by + part.y))
                            .set_hflip(part.hflip)
                            .set_vflip(part.vflip)
                            .show(frame);
                    }
                }
            });
            if self.glow_state != 0 {
                let (px, py) = field::panel_centre(self.megaman.panel().0, self.megaman.panel().1);
                let dx = self.megaman.facing_dx();
                for part in self.glow.parts().iter().rev() {
                    Object::new(part.sprite.clone())
                        .set_priority(Priority::P2)
                        .set_pos((px + dx * GLOW_FORWARD + part.x, py + part.y))
                        .set_hflip(part.hflip ^ (dx < 0))
                        .set_vflip(part.vflip)
                        .show(frame);
                }
            }
        }
        for enemy in self.enemies.iter().filter(|e| e.is_present()) {
            enemy.show(frame);
        }
        if let Some(cursor) = self.gunner_ctl.cursor() {
            cursor.show(frame);
        }
        for imp in &self.impacts {
            imp.show(frame);
        }
        for b in &self.bombs {
            let (x, y) = b.position();
            let (gx, gy) = b.ground();
            // The frame's first part is the shadow (sprite_hasShadow): it is
            // drawn on the ground, the rest at the bomb's height -- the real
            // ROM keeps the shadow at y 106-111 under the whole arc.
            for (i, part) in b.player.parts().iter().enumerate().rev() {
                let (px, py) = if i == 0 { (gx, gy) } else { (x, y) };
                Object::new(part.sprite.clone())
                    .set_priority(Priority::P2)
                    .set_pos((px + part.x, py + part.y))
                    .set_hflip(part.hflip)
                    .set_vflip(part.vflip)
                    .show(frame);
            }
        }

        // Each enemy's HP sits just under its panel, centred, as the game's
        // object text does; the player's is the box at the top left. Both
        // show the lagging number, which flashes while it catches up.
        for (actor, counter) in self
            .enemies
            .iter()
            .zip(self.hp_shown.iter().skip(1))
            .filter(|(a, _)| a.is_present() && a.hp() > 0 && a.is_targetable())
        {
            let (px, py) = field::panel_centre(actor.panel().0, actor.panel().1);
            let hp = counter.shown();
            self.hud.draw_number_in(
                frame,
                hp,
                px + self.hud.width(hp) / 2,
                py + 6,
                counter.set(),
            );
        }
        if let Some(counter) = self.hp_shown.first() {
            if !self.megaman.is_defeated() {
                let hp = counter.shown();
                self.hud
                    .draw_number_in(frame, hp, PLAYER_HP_AT.0, PLAYER_HP_AT.1, counter.set());
            }
        }
    }
}
