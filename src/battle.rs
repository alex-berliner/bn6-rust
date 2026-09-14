//! The state of one battle and the frame logic that runs it: the intro
//! fades the screen in, the fight runs until a side is deleted, and the
//! results window closes with a fade-out. It is all rebuilt for the next
//! battle; the field, HUD and results assets are borrowed.

use agb::display::GraphicsFrame;
use agb::display::Priority;
use agb::display::AffineMatrix;
use agb::display::{Palette16, Rgb15};
use agb::display::object::{
    AffineMatrixObject, AffineMode, DynamicSprite16, Object, ObjectAffine,
    PaletteVramSingle, Size, SpriteVram,
};
// Unconditional now (AUDIT pairs 6/14/17): a fixture-driven battle can ask
// for a blank arena at runtime (FLAG_BLANK_BACKDROP) in a build that has no
// demo-sterile feature at all, so the blank background's own constructor
// must exist in every build, not just one gated on that cfg.
use agb::display::tiled::{RegularBackgroundSize, TileFormat};
use agb::display::tiled::RegularBackground;
use agb::fixnum::Num;
use agb::input::{Button, ButtonController};
use alloc::vec::Vec;

use crate::actor::{self, Actor, Update};
use crate::banner::{self, Banner};
use crate::chips::{Chip, Chips};
use crate::custom::{self, Custom, CustomAssets, Offer};
use crate::deck::{Deck, Rng, FOLDER_SIZE};
use crate::field::{self, Field, Panels};
use crate::hud::{Counter, Hud};
use crate::results::{self, Results};
use crate::script;
use crate::shot::Shot;
use crate::{
    BARREL_CHARGE, CANNON_ORB, CHARGE, CURSOR, DELETE, GUNNER, IMPACT, MEGAMAN, METTAUR,
    AREAGRAB_ORB, AIRSHOT_BARREL, AQUA_SWORD, BARRIER, BLKBOMB, BOMB_BLAST, ELEC_SWORD, ENERGBOM_BLAST, FIRE_SWORD, HEAL,
    FLSHBOM, LILBOILER, MINIBOMB, POISAREA, POISSEED, VDOLL,
    BUSTER_ARM, BUSTER_FX, BUSTER_HIT,
    SHOTFX, SWORD_ARC, SWORD_SPR, VULCAN_FIREBALL, VULCAN_GUN, WAVE,
};
use crate::{ai, gunner, objects, spr};
use crate::fixture::{self, Fixture};
use agb::display::Graphics;

// The Mettaur's first-version record: HP 0x28, and its shockwave deals
// 10 (MettaurEnemyStruct2_8109BD8, byte_8109F28; asm31.s:170519).
const METTAUR_HP: u16 = 40; // provenance: derived -- MettaurEnemyStruct2_8109BD8, asm31.s:170519
const WAVE_DAMAGE: u16 = 10; // provenance: derived -- byte_8109F28, asm31.s:170519
/// Which of the field's two highlight overlays the shockwave paints its panel
/// with.
const WAVE_HIGHLIGHT: usize = 0;
// MegaMan's own HP does come from the disassembly: byte_80210DD
// (data/dat01.s:295) row 0 gives 50 * 2 = 100, via init_8013B64.
const PLAYER_HP: u16 = 100; // provenance: derived -- byte_80210DD, data/dat01.s:295, via init_8013B64
/// The real win reward, used until the actual roll is implemented (a
/// captured save state's own displayed reward).
const RESULTMATCH_ZENNY: u16 = 100; // provenance: peeked -- the capture's own displayed reward
/// Where the RESULT window's corner badge lands, from OAM entry 0 of a live
/// results screen.
const RESULTS_MARK_AT: (i32, i32) = (37, 21); // provenance: peeked -- OAM entry 0 of a live results screen
// ProtoMan's strike reads byte_80FBFFC, 0x64 in the first version
// (sub_80FBF92, asm31.s:142402, 142437). Colonel's launchers each
// pick a damage row (asm31.s:153414-153526): the cross slash reads
// byte_81017D8 and the overhead slash byte_81017F0 (asm31.s:153623,
// 153629), whose first-version hwords are 80 and 30. The version column
// comes from the AI data's version byte (sub_800FE12, asm00_2.s:2370).
const SWORD_DAMAGE: u16 = 100; // provenance: derived -- byte_80FBFFC, sub_80FBF92, asm31.s:142402/142437
const CROSS_DAMAGE: u16 = 80; // provenance: derived -- byte_81017D8, asm31.s:153623
const DIVIDE_DAMAGE: u16 = 30; // provenance: derived -- byte_81017F0, asm31.s:153629
// Buster damage is Attack + 1 for MegaMan (sub_801265A, asm00_2.s:7908)
// and a charged shot is (Attack + 1) * 10 (asm00_2.s:5988), at Attack 1.
const BUSTER_DAMAGE: u16 = 2; // provenance: derived -- sub_801265A, asm00_2.s:7908
/// The muzzle flash's origin above the front panel's centre, and how long its
/// animation runs (durations 2,1,1,2,1).
const BUSTER_FX_UP: i32 = 26; // provenance: peeked -- measured off the real ROM's OAM
// SOUND_BUSTER_6A (id 0x6A, reference/bn6f/constants/enums/SoundOffsets.inc:50), played the
// instant the fire phase starts by sub_80BCF7A (asm31.s:10516-10528). It is a PSG channel-1
// (square/sweep) blip, not a DirectSound sample: its song header (dat37.s:41516-41519,
// dword_81B82FC) is one track (dat37.s:41513-41515, byte_81B82EC) selecting voicegroup entry 0
// (dat37.s:2755-2756, byte_8156D6C -- type 0x9 = square1, duty 0 = 12.5%, sweep byte 0x1F =
// time 1/decreasing/shift 7, envelope attack 0/decay 1(fastest)/sustain 0/release 0) at key 0x7F
// with the instrument's own base key 0x3C, tempo 0x4B=75 (the docs' own example of "75 = 1
// frame/tick"), for a 7-tick/7-frame gate. The instrument's "hardware time length control" byte
// is 0, i.e. disabled, so nothing hardware-gates the note: only the envelope's own decay ends it.
// Capturing the real ROM's channel 0 (mgba_capture --dump-audio --audio-channel 0, subtracting a
// silent control run to cancel the battle music) shows a clean downward hardware sweep starting
// around 5240 Hz -- an 18-sample period at the measured 96000 Hz capture rate -- decaying in
// volume over about 130-150 ms with no sharp cutoff, exactly matching that reading of the ROM
// data. BUSTER_BLIP_FREQ is that measured onset frequency's register value, not a note-table
// guess.
// provenance: derived -- dat37.s:2755-2756, byte_8156D6C, cross-checked
// against a captured channel-0 sweep reading.
const BUSTER_BLIP_SWEEP: agb::sound::psg::Sweep =
    agb::sound::psg::Sweep { time: 1, decreasing: true, shift: 7 };
/// MEASURED AGAINST THE REAL ROM, not taken from the instrument's own bytes.
/// Capturing channel 0 on both sides and subtracting a run with no shot to
/// cancel the battle music, the real blip is 1376 RMS on the frame it lands
/// and 794 on the next, and gone. A hardware envelope at its FASTEST period
/// still takes fifteen frames to fall from 15 to 0 -- which is what a straight
/// reading of the instrument produces, and it is about five times too long and
/// nearly three times too loud. M4A evidently runs this envelope in software.
/// So the volume is set to match the measured peak (15 * 1376/3768 is about 6)
/// and the note is cut by the hardware LENGTH COUNTER, which the instrument
/// itself does not use -- an approximation of the real envelope's shape rather
/// than a reproduction of its mechanism, and recorded here as one.
// provenance: fitted -- explicitly "an approximation of the real envelope's
// shape rather than a reproduction of its mechanism" (M4A runs the real
// envelope in software, not the hardware envelope this reuses).
const BUSTER_BLIP_ENVELOPE: agb::sound::psg::Envelope =
    agb::sound::psg::Envelope { initial_volume: 6, increasing: false, period: 1 };
/// Frames the blip sounds for. The real one is full on the frame it lands, half
/// on the next, and gone -- and the hardware cannot do that on its own: its
/// FASTEST envelope takes about six frames to fall from volume 6, and the
/// length counter that is supposed to cut a note short does not appear to work
/// at all (a note asking for 1/256 of a second still runs the full six). So the
/// channel is stopped in software after two frames, which is what M4A does
/// anyway -- it runs its envelopes itself rather than leaving them to the APU,
/// which is exactly why its blips are shorter than the hardware's fastest.
const BUSTER_BLIP_FRAMES: u8 = 2; // provenance: fitted -- stopped in software to approximate M4A's own envelope, not a hardware-length-counter value
/// Frames between the buster firing and the blip. The real ROM does not play a
/// sound where it asks for one: `PlaySoundEffect` (asm00_0.s:26) appends a
/// {function, args} record to a 32-entry ring buffer that something else drains
/// (`sound_8000808`, asm00_0.s:380), so the note lands a frame after the frame
/// that asked for it. Measured: the real blip is on the press's seventh frame
/// and this build's, played immediately, was on the sixth.
const BUSTER_BLIP_DELAY: u8 = 1; // provenance: fitted -- measures right (matches the captured onset frame), not computed from a cited mechanism
const BUSTER_BLIP_FREQ: u16 = 2023; // provenance: peeked -- the measured onset frequency's register value, not a note-table guess
// SOUND_HIT_6B (TRANSFER.md 7bb): the enemy's own hit-flash/HP-decrement
// reaction, not the buster's fire -- soloing the harness's channels 4 and 5
// (both FIFOs, its numbering, not the hardware's) and control-subtracting a
// run with no press (residual RMS of press-minus-control, not the coarser
// difference-of-RMS 7bb used) shows nothing above a noise floor of about 130
// through the press's 14th frame, a partial rise on the 15th (856) and the
// sample's own measured 1881-sample/10512Hz body (178.94 ms, ~10.7 frames)
// established by the 16th (3662, rising to a peak of 4074 on the 17th).
// MEASURED, not guessed, and not simply derived: the plain buster's Strike
// (where this and BUSTER_BLIP_DELAY are both set) lands on the press's 6th
// frame, so a naive count from BUSTER_BLIP_DELAY's own confirmed one-frame
// sound-request latency predicts the 15th. What actually lands there is one
// frame later, the 16th -- agb's software mixer double-buffers
// (`MixerBuffer::should_calculate`, sw_mixer.rs), so a channel started in
// `play_sound` is not the buffer the timer/DMA is actively draining until
// the FOLLOWING `Mixer::frame()`, an extra frame of latency this build does
// not control and that was found by building and capturing, not assumed.
// 4, NOT 9. The value was 9 when this was wired, chosen against a frame
// accounting that counted "+k" from a different origin than the `audio` check
// does. Comparing the two residual envelopes on the check's own convention --
// press+k on both sides, the same one `buster` uses to compare the visuals at
// 0 -- the real ROM's onset is at press+10 and 9 put ours at press+16, six
// frames late. Swept: 2 -> 25101, 3 -> 17738, 4 -> 11971, 5 -> 13160,
// 6 -> 16607, 7 -> 22207. A clean minimum, not a plateau.
// Still the delay that measures right rather than the one that computes right:
// agb's mixer double-buffers, so a channel started in `play_sound` is not in
// the buffer the DMA is draining until the following `Mixer::frame()`.
const BUSTER_HIT_DELAY: u8 = 4; // provenance: fitted -- swept to a clean residual-RMS minimum against the captured onset, not derived from a cited mechanism
// F31b: the barrel and the muzzle have no length of their own. canon holds
// both in pointers -- the barrel in oAIData_Unk_68 (sub_80EB562/sub_80EB572,
// asm31.s:108743-108750, spawned on the fire phase's FIRST tick, which is why
// the barrel is in OAM on the pose's first frame) and the muzzle in
// oBattleObject_RelatedObject1Ptr (sub_800FAAC -> sub_80C4FFE,
// asm00_2.s:1903-1916, spawned on the second tick) -- and `sub_80EB502` ends
// the attack by clearing BOTH pointers and calling object_exitAttackState
// (asm31.s:108712-108722). Measured on the real ROM: pose+barrel enter OAM at
// canon 134, the muzzle at 135, and both vanish together at 159, the frame the
// 25-frame pose ends. So each one's lifetime is read from the pose the navi is
// actually holding (actor::Actor::buster_spec), never from a constant of its
// own; the old BUSTER_ARM_FRAMES=18 and BUSTER_FX_FRAMES=7 outlived the pose
// on one side and died inside it on the other.
// The barrel comes with the POSE, not with the button, so its delay IS the
// pose's own lead-in: canon spawns it on the fire phase's first tick, the same
// tick that calls object_setAnimation(0xe) (asm31.s:108614-108625), and it is
// drawn on the pose's first frame.
const BUSTER_ARM_DELAY: u8 = actor::BUSTER_WINDUP; // provenance: derived -- sub_80EB450 tick 0, asm31.s:108614-108625
/// Frames between the chip button going down and the chip being used.
const CHIP_USE_DELAY: u8 = 3; // provenance: peeked -- measured off the real ROM
const CHARGED_DAMAGE: u16 = 20;
// Frames of holding B before a release fires a charged shot: the buster's
// row of powerAttackChargeTimes_8020404 (data/dat01.s) at Charge stat 1.
// Measured rather than read: the real ROM's glow turns magenta on the 101st
// frame of the hold, in a capture whose navi was first moved off the virus's
// row so its shockwave would not bury him at that moment.
const CHARGE_FRAMES: u16 = 101; // provenance: peeked -- measured onset frame in a live capture, not read from the charge-time table directly
// Below this the hold is not yet a charge at all (asm00_2.s:9107). Eleven,
// not ten: the real ROM's sparks first show on the eleventh frame of the
// hold, this build's on the tenth.
const CHARGING_FROM: u16 = 11; // provenance: peeked -- measured onset frame in a live capture
// The glow is one persistent effect object on the navi's arm whose
// animation index is the charge state, 1 charging and 2 full, hidden at 0
// (chargeShotChargeObject_update_80E0E20, asm31.s:86354). The game tracks
// the arm position each frame; a fixed offset stands in for that. It is
// centred on the navi's body and pushed a little toward the front (the
// direction it faces), rather than the old top-right corner offset, so the
// charge reads as gathering at the buster.
const GLOW_FORWARD: i32 = 2; // provenance: fitted -- a stand-in offset for the game's own per-frame tracked arm position, chosen to read as gathering at the buster
/// Which of the glow sprite's three animations each charge state plays.
/// Animations 0 and 1 carry the same OAM offsets and different spark art;
/// 2 is the full-charge set, which draws in the sprite's third palette.
const GLOW_ANIM: [usize; 3] = [0, 0, 2]; // provenance: derived -- chargeShotChargeObject_update_80E0E20, asm31.s:86354
// The intro: the screen holds WHITE, then the field appears whole, then the
// enemies materialise one at a time from a fade-in list, and only then does
// the fight state run and lift the pause (sub_8009658 onwards, asm00_1.s:
// 13379; sub_800855E, 11048). The player's navi is simply there.
//
// MEASURED (2026-09-07), from a save state at a battle's first frame and its
// own line-up under `demo-open`: the screen is 100% WHITE from frame 0 through
// 70 and 0% at 71, with no ramp between -- a HOLD, not a fade -- and then the
// field is simply there. The three viruses follow at 113, 141 and 173.
// This was black and 32 frames, with a note admitting the count had never been
// read. It was the wrong colour and less than half the length.
// The white belongs to the BATTLE and not to the map-to-battle transition:
// the save state's scroll counters (`eBGScrollCBCounters`, zeroed once at
// battle init) read 0x0000 there, so init has just happened, and the screen is
// still white for 71 frames afterwards.
//
// Every fixture that compares against a capture taken MID-BATTLE, where no
// intro is running, has a frame offset calibrated against the 32 this used
// to be; lengthening it to the real 71 moved eight of them at once. The
// intro's length is a fixture artefact for them, exactly as BATTLE START! is.
// provenance: peeked -- `71 + INTRO_RAMP` (below), measured from a save
// state at a battle's first frame, full white through frame 70. The runtime
// formula this used to be a standalone const for is now `Battle::new`'s own
// `intro_fade`, which reads FLAG_SKIP_INTRO from a fixture instead of a
// demo-* feature (the old legacy `0x10 * 2` black-ramp branch, AUDIT pair 17
// prune ticket).
/// Frames the white takes to come off at the end of the hold. Measured: full
/// white through frame 70, then 92, 85, 77, 70, 62, 56, 48 and settled at 86.
const INTRO_RAMP: u16 = 14; // provenance: peeked -- measured against the real ROM's own fade-out readings
// The custom gauge: a u16 at BattleState+0x20 that the fight state adds
// 0xd to each frame, full at 0x4000 (sub_800855E, asm00_1.s:11100;
// accessors asm00_2.s:29821-29883). A speed word at +0x22 defaults to
// 0x20 but nothing reading it was found, so it is not applied. When full
// the battle pauses for about 60 frames of chimes and then opens chip
// selection (sub_8008840), which clears the gauge on entry (asm03_0.s:540).
const GAUGE_STEP: u16 = 0xd; // provenance: derived -- sub_800855E, asm00_1.s:11100
/// The field slides 15 px down while the chip menu is up, at 1.5 px a frame:
/// measured on the real ROM, its top edge runs 72, 74, 75, 77, 78, 80, 81, 83,
/// 84, 86, 87 over ten frames and holds at 87. Kept in half-pixels.
///
/// Canon does not "slide the field" at all: it pans the CAMERA, from inside
/// the chip window's own slide routines. The slide-out (sub_8026BF4,
/// reference/bn6f/asm/asm03_0.s:1037) adds dword_8026CC8 = 0x18000 to
/// Camera+0x34 on each of its ten calls (asm03_0.s:1099-1104, the constant at
/// asm03_0.s:1141-1142) and the slide-in subtracts the same value on each of
/// its own (asm03_0.s:964-969). 0x18000 is 1.5 px in the camera's 16.16, so
/// ten calls ARE the 15 px -- the step and the total are canon's, not a
/// measurement of the picture.
const FIELD_SLIDE: u16 = 30; // provenance: derived -- ten slide calls x 0x18000 (1.5 px in 16.16) on Camera+0x34, asm03_0.s:1099-1104 (kept in half-pixels)
const FIELD_SLIDE_STEP: u16 = 3; // provenance: derived -- one slide call's 0x18000 = 1.5 px, asm03_0.s:1099-1104 (kept in half-pixels)
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
/// LilBolr1/2/3: bomb family, subfamily 3, which routes through sub_80D7A96
/// rather than MiniBomb's sub_80C5DBC -- a fixed target ahead rather than the
/// targeted arc. Its blast is the same object MiniBomb's is, confirmed by the
/// art matching the exported blast asset byte for byte.
/// FlshBom1/2/3 share bomb subfamily 0xe, so one implementation serves all
/// three; their powers are 40, 70 and 100.
const CHIP_FLSHBOM1: u16 = 57;
const CHIP_FLSHBOM2: u16 = 58;
const CHIP_FLSHBOM3: u16 = 59;
const CHIP_LILBOLR1: u16 = 98;
const CHIP_LILBOLR2: u16 = 99;
const CHIP_LILBOLR3: u16 = 100;
const CHIP_MEGENBOM: u16 = 56;
/// PoisSeed, the one of the three seeds whose panels this build already has
/// art for: the field asset carries POISON, and the ROM's panel tilemap has
/// no grass or ice at all.
const CHIP_BUGBOMB: u16 = 67;
const CHIP_GRASSEED: u16 = 68;
const CHIP_ICESEED: u16 = 69;
const CHIP_POISSEED: u16 = 70;
const CHIP_VDOLL: u16 = 150;
/// BugBomb throws a spiked ball and VDoll a small doll, and both LAND AND
/// STAY: the object rests on its panel rather than bursting. BugBomb's ball
/// is the seeds' own sprite in another animation -- animations 4 held and 5
/// thrown, matched by their OAM shapes -- and VDoll has its own,
/// byte_83262C0.spr, whose two animations share their three parts and differ
/// only in a palette flash on spawn.
const BUG_HELD_ANIM: usize = 4; // provenance: peeked -- matched by OAM shapes against the real ROM
const BUG_THROWN_ANIM: usize = 5; // provenance: peeked -- matched by OAM shapes against the real ROM
const VDOLL_ANIM: usize = 1; // provenance: peeked -- matched against the real ROM's OAM
/// VDoll's HELD object is not the doll: it is the seeds' own sprite,
/// animation 0, whose 16x16 part sits thirty left and twenty-eight up of the
/// panel centre -- exactly where the real ROM's OAM puts it.
const VDOLL_HELD_ANIM: usize = 0; // provenance: peeked -- exactly where the real ROM's OAM puts it
/// How long a landed one stands. Nothing removes it in the capture.
const RESTS_FRAMES: u8 = 255; // provenance: fitted -- u8's own max as a "never expires" stand-in; nothing removes the object within any capture
/// BugBomb's ball flies flatter than a bomb, and these are the game's own
/// numbers rather than a sweep's: `tools/throw_dump.py 43` finds the thrown
/// object in EWRAM and reads them out of it. X steps by exactly 0x2C000 a
/// frame, Z starts at 0x300000 -- the shared spawn height -- and the Z
/// velocity starts at 0x26062 and loses 0x2800 a frame, over a timer of 42.
/// The sweep that preceded this landed on 0x25D60 and 0x27C0, which is a
/// point on the ridge where a launch 1282 too weak and a pull 64 too soft
/// cancel over forty frames: it drew the same pixels everywhere except one
/// rounding boundary, which is what the last frame of BugBomb's residue was.
const BUG_VX: i32 = BLKBOMB_VX; // provenance: peeked -- tools/throw_dump.py 43 reads it out of the live thrown object
const BUG_VZ: i32 = 0x26062; // provenance: peeked -- tools/throw_dump.py 43
const BUG_GRAVITY: i32 = 0x2800; // provenance: peeked -- tools/throw_dump.py 43
const BUG_FLIGHT: u8 = 42; // provenance: peeked -- tools/throw_dump.py 43's own timer of 42
/// How high BugBomb's resting ball floats above its panel: sub_80D9E94's
/// landing (loc_80D9EC2, asm31.s:71831) writes Z = 0xa<<0x10 after snapping
/// X/Y to the panel, so the ball sits ten above the ground its shadow stays
/// on. The trajectory's own endpoint is lower and left of that -- the whole
/// of chip-bugbomb's residue -- and the 60-frame fuse and blast that follow
/// (sub_80D9F2C) fall past this row's 70 frames, so the freeze below stands
/// in until a longer row needs them.
const BUG_REST_Z: i32 = 0xa << Q16_SHIFT; // provenance: derived -- sub_80D9E94 loc_80D9EC2 (asm31.s:71831)
/// VDoll's doll rests ON its panel, not above it: sub_80D47C0's landing
/// (loc_80D481E, asm31.s:60568) snaps X/Y to the panel with
/// object_setCoordinatesFromPanels and then writes Z = 0, where BugBomb
/// writes ten. The same landing poisons the panel (object_setPanelType 4).
const VDOLL_REST_Z: i32 = 0; // provenance: derived -- sub_80D47C0 loc_80D481E (asm31.s:60568)
/// VDoll's doll flies far higher and slower than any bomb -- it rises to the
/// top of the screen and hangs there -- so it gets its own launch, gravity and
/// flight, and `tools/throw_dump.py 96` reads all four out of the object while
/// it is in the air. The doll also steps the OTHER WAY ROUND: its update moves
/// it and then applies the pull (t3_0x7a, sub_80D47C0 loc_80D4848,
/// asm31.s:60530), where a bomb applies the pull and then moves.
const VDOLL_VX: i32 = 0x1EEEE; // provenance: peeked -- tools/throw_dump.py 96 reads it out of the live object
const VDOLL_VZ: i32 = 0x2F333; // provenance: peeked -- tools/throw_dump.py 96
const VDOLL_GRAVITY: i32 = 0x2000; // provenance: peeked -- tools/throw_dump.py 96
const VDOLL_FLIGHT: u8 = 60; // provenance: peeked -- tools/throw_dump.py 96
/// Timer2 is decremented BEFORE the branch, so the doll only lands once it
/// reads below zero: one frame after the 0x3c flight updates (sub_80D47C0
/// loc_80D47FA-80D4848, asm31.s:60546-60568). Bomb.flight counts updates
/// before the landing is processed, so it runs one past the timer seed.
const VDOLL_LANDING_LAG: u8 = 1; // provenance: derived -- sub_80D47C0 loc_80D47FA lands only once Timer2 < 0 (asm31.s:60546)
/// Its sprite's animations and palette shift, read off the real ROM's OAM.
/// Every part of both animations carries an OAM palette offset of 9, and the
/// live palette is the sprite's index 12, so the chip's own shift is 3 -- its
/// attack_param_2, the same way BigBomb's 3 picks the red bomb. The offsets
/// count FROM the shifted palette here, as Barr100's bubble does.
const SEED_HELD_ANIM: usize = 8;
const SEED_THROWN_ANIM: usize = 9;
/// The SHEET's palette, which does NOT follow the pod's: PoisSeed and IceSeed
/// share the sprite's index 0 and GrasSeed takes 8. Matched by dumping OBJ
/// bank 1 while each sheet is up and comparing it against the asset's own
/// palettes.
const SHEET_PALETTE_GRAS: usize = 8; // provenance: derived -- dumped OBJ bank 1 palette against the asset's own palettes (see sheet_palette)
const fn sheet_palette(id: u16) -> usize {
    match id {
        CHIP_GRASSEED => SHEET_PALETTE_GRAS,
        _ => 0,
    }
}

/// One palette per seed, and it is the chip's attack_param_2: IceSeed 1,
/// GrasSeed 2, PoisSeed 3. BugBomb shares their sprite and takes 0; VDoll has
/// its own sprite and takes 0 too.
const SEED_PALETTE_ICE: usize = 1; // provenance: derived -- the chip's attack_param_2 (see seed_or_bomb_palette)
const SEED_PALETTE_GRAS: usize = 2; // provenance: derived -- the chip's attack_param_2 (see seed_or_bomb_palette)
const SEED_PALETTE_POIS: usize = 3; // provenance: derived -- the chip's attack_param_2 (see seed_or_bomb_palette)
const fn seed_or_bomb_palette(id: u16, thrown: bool) -> usize {
    match id {
        CHIP_ICESEED => SEED_PALETTE_ICE,
        CHIP_GRASSEED => SEED_PALETTE_GRAS,
        CHIP_POISSEED => SEED_PALETTE_POIS,
        CHIP_BUGBOMB | CHIP_VDOLL => 0,
        _ => bomb_palette(id, thrown),
    }
}
/// The poison sheet's animation and how long it runs, from the sprite's own
/// frame durations.
const POISON_ANIM: usize = 1; // provenance: derived -- the sprite's own frame durations
const POISON_FRAMES: u8 = 16; // provenance: derived -- the sprite's own frame durations
/// Step from the enemy half's first column to its middle column: the sheet's
/// middle column is pushed last so it sorts above both neighbours in the
/// inter-panel overlap zones (canon zone B: R148 over L188).
const SHEET_MID_STEP: i32 = 1; // provenance: derived -- field::half(true) = 4..=6, middle is 5
/// How long each slash arc animation runs, from its frame durations
/// (6+4+3, 6+4+3, 4+3+3).
const SWORD_ARC_FRAMES: [u8; 3] = [13, 13, 10]; // provenance: derived -- the sprite's own frame durations
// Against the real ROM (tools/chip_compare.py 47 demo-sword): the two
// lead-in states take a frame each (sub_80EB79C, sub_80EB84C), so two frames
// of the idle pose lead in; the slash pose is then on screen 27 frames --
// the 0x15 of its timer, the frame that reads the end and only queues the
// exit, the exit frame, and the five of recovery with its last frame held
// -- and the idle is back 29 frames after the press. Every frame of that,
// with the sword object and the arc, diffs to zero against the real ROM.
// provenance: derived -- sub_80EB79C/sub_80EB84C/asm31.s:109141, cross-checked
// pixel-for-pixel against the real ROM (tools/chip_compare.py 47 demo-sword).
const SWORD: actor::AttackSpec = actor::AttackSpec {
    windup: Some((0, 2)),
    anim: 5,
    frames: 0x15 + 1,
    // The timer starts at 0x15 and the hit goes out on the frame it reads
    // 0xc (asm31.s:109141), the tenth of the pose.
    strike_at: 10,
    recover: 5,
    recover_anim: None,
    pose: None,
};
/// StepSwrd holds its recovery pose one frame longer than the other swords.
/// Measured against the real ROM: on the attack's frame 29 the navi is still
/// in the recovery pose (917 non-black pixels at home, 178 of them body
/// colour) and idle on 30, where every other sword is idle on 29. The frame
/// the step spends going home is the likely cause.
// provenance: peeked -- the +1 is measured against the real ROM's own recovery-pose frame count.
const STEP_SWORD: actor::AttackSpec = actor::AttackSpec {
    windup: SWORD.windup,
    anim: SWORD.anim,
    frames: SWORD.frames,
    strike_at: SWORD.strike_at,
    recover: SWORD.recover + 1,
    recover_anim: SWORD.recover_anim,
    pose: None,
};

/// MiniBomb (attack family 0x12, sub_80EB644, asm31.s:108790): animation 6
/// and the held bomb from the first frame, the throw on the frame the
/// counter reads 9 -- the tenth -- and the pose's first state ends at 0x15,
/// but the second state's timer is never re-seeded and counts the same
/// counter back down, so the navi holds animation 6 (whose last frame is
/// the idle pose) until the exit 42 frames in (sub_80EB758, asm31.s:108904).
// provenance: derived -- sub_80EB644/sub_80EB758, asm31.s:108790/108904.
const THROW: actor::AttackSpec = actor::AttackSpec {
    windup: None,
    anim: 6,
    frames: 42,
    strike_at: 10,
    recover: 0,
    recover_anim: None,
    pose: None,
};
/// The cannon pose: the counter runs to 0x1d (sub_80EBC28, asm31.s:109532,
/// 109554), and the frame that reads 0x1d only queues the exit state, which
/// runs the frame after, so the pose is on screen for 0x1e frames -- the real
/// ROM shows the idle again 30 frames after the attack starts (TRANSFER.md).
/// The barrel object lives exactly as long.
const CANNON_FRAMES: u8 = 0x1d + 1; // provenance: derived -- sub_80EBC28, asm31.s:109532/109554
/// Cannon and HiCannon (attack family 0x14, sub_80EBC28): the navi takes
/// animation 8 and the projectile is spawned off the front panel when the
/// frame counter reads 0xf, the pose exiting once it reads 0x1d
/// (asm31.s:109454, 109532, 109549). Both subfamilies are under 4, so the
/// illusions at counter 8 do not apply (asm31.s:109480).
// provenance: derived -- sub_80EBC28, asm31.s:109454/109532/109549, recover/recover_anim peeked (TRANSFER.md).
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
    pose: None,
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
// provenance: derived -- dword_80EBFEC = 0xA050403, asm31.s:109878-109892.
const VULCAN1_SHOTS: u8 = 3; // provenance: derived -- dword_80EBFEC = 0xA050403, asm31.s:109878-109892
const VULCAN2_SHOTS: u8 = 4; // provenance: derived -- dword_80EBFEC = 0xA050403, asm31.s:109878-109892
const VULCAN3_SHOTS: u8 = 5; // provenance: derived -- dword_80EBFEC = 0xA050403, asm31.s:109878-109892
const SUPRVULC_SHOTS: u8 = 10; // provenance: derived -- dword_80EBFEC = 0xA050403, asm31.s:109878-109892
const fn vulcan_shots(id: u16) -> u8 {
    match id {
        CHIP_VULCAN2 => VULCAN2_SHOTS,
        CHIP_VULCAN3 => VULCAN3_SHOTS,
        CHIP_SUPRVULC => SUPRVULC_SHOTS,
        _ => VULCAN1_SHOTS,
    }
}

/// The firing state's length and the recovery that follows, per shot
/// count. Measured on the real ROM: the firing pose's last frame -- recoil
/// plus muzzle flash -- is c21, c35 and c46 for Vulcan1/2/3 (the pose
/// starts at c2), and the gun is on screen 35, 46 and 57 frames, which
/// leaves the recoveries below. The state machine's own tick rate does not
/// map to frames one-for-one, so these are the measurements rather than a
/// formula.
// provenance: peeked -- "the measurements rather than a formula" (the state
// machine's own tick rate does not map to frames one-for-one).
const VULCAN1_TIMING: (u8, u8) = (20, 13); // provenance: peeked -- the firing pose's last frame and gun-on-screen frames, measured on the real ROM (see vulcan_timing)
const VULCAN2_TIMING: (u8, u8) = (34, 10); // provenance: peeked -- the firing pose's last frame and gun-on-screen frames, measured on the real ROM (see vulcan_timing)
const VULCAN3_TIMING: (u8, u8) = (45, 10); // provenance: peeked -- the firing pose's last frame and gun-on-screen frames, measured on the real ROM (see vulcan_timing)
const SUPRVULC_TIMING: (u8, u8) = (100, 10); // provenance: peeked -- flashes run to c101 and the gun is on screen 112 frames, measured on the real ROM (see vulcan_timing)
const fn vulcan_timing(shots: u8) -> (u8, u8) {
    match shots {
        VULCAN2_SHOTS => VULCAN2_TIMING,
        VULCAN3_SHOTS => VULCAN3_TIMING,
        // SuprVulc's ten shots: its flashes run to c101 and the gun is on
        // screen 112 frames, measured the same way.
        SUPRVULC_SHOTS => SUPRVULC_TIMING,
        _ => VULCAN1_TIMING,
    }
}

/// The first state holds animation 0xa for two ticks with the arm gun
/// spawned; the firing state sets animation 0xd (sub_80EBF10,
/// asm31.s:109821).
const VULCAN_WINDUP_ANIM: u8 = 0xa; // provenance: derived -- sub_80EBF10, asm31.s:109821
const VULCAN_WINDUP_TICKS: u8 = 2; // provenance: derived -- sub_80EBF10, asm31.s:109821
const VULCAN_FIRE_ANIM: u8 = 0xd; // provenance: derived -- sub_80EBF10, asm31.s:109821
const fn vulcan(shots: u8) -> actor::AttackSpec {
    let (frames, recover) = vulcan_timing(shots);
    actor::AttackSpec {
        windup: Some((VULCAN_WINDUP_ANIM as usize, VULCAN_WINDUP_TICKS)),
        anim: VULCAN_FIRE_ANIM as usize,
        frames,
        strike_at: 1,
        recover,
        recover_anim: Some(VULCAN_WINDUP_ANIM as usize),
        pose: None,
    }
}
/// The Vulcan gun rides the arm for the whole attack (byte_80B8BD4 row
/// 0xd: effect list 0xC index 0x1d = sprite_83195F0, animation 0, at
/// arm-position row 0xe: +23 forward, 25 up, byte_80188C0[28..30]).
const fn vulcan_gun_frames(shots: u8) -> u8 {
    let (firing, recover) = vulcan_timing(shots);
    VULCAN_WINDUP_TICKS + firing + recover
}
const VULCAN_ARM: (i32, i32) = (23, -25); // provenance: derived -- byte_80B8BD4 row 0xd, byte_80188C0[28..30]
/// SuprVulc's detached muzzle-fire ball. Canon spawns a live 16x16 object
/// (OAM obj0, tile 512, pal 11) that slides in from the left edge and parks
/// above the gun tip for the volley's tail: OAM x 285 +16/frame from gun-age
/// 85 (capture 90), wrapping past 512 to 13/29, pinned at 37 from gun-age
/// 102 (capture 107) through the gun's last frame, y 21 throughout -- all
/// peeked off the sterile-row capture (watch 0x02034b80/0x02034c00/0x07000000;
/// the per-frame shadow-table writer is the strh at ROM 0x0802C4CC inside the
/// strip copier 0x0802C4B6, called from the 5-part sprite builder 0x0802C4E8,
/// fed by a CpuFastSet ROM 0x08731DF4 -> EWRAM 0x02034B30 at capture 88).
/// Spawn is chip-gated (see below): Vulcan1/2/3 guns are gone by gun-ages
/// VULCAN1_TIMING/VULCAN2_TIMING/VULCAN3_TIMING (see vulcan_timing) while
/// SUPRVULC_TIMING's gun lives on, so only SuprVulc can reach these ages --
/// and the age window alone would also fire for a short gun on a longer
/// capture. The chip gate, not the age coincidence, keeps Vulcan1/2/3 clean.
const VULCAN_FIREBALL_X0_AGE: u8 = 85; // provenance: peeked -- OAM obj0 becomes tile-512/pal-11 at capture 90 = gun-age 85
const VULCAN_FIREBALL_X0: i32 = 285; // provenance: peeked -- OAM x at capture 90
const VULCAN_FIREBALL_DX: i32 = 16; // provenance: peeked -- OAM x +16/frame, captures 90-104
const VULCAN_FIREBALL_PARK_AGE: u8 = 102; // provenance: peeked -- OAM x pinned from capture 107 = gun-age 102
const VULCAN_FIREBALL_PARK_X: i32 = 37; // provenance: peeked -- parked OAM x (gun tip)
const VULCAN_FIREBALL_Y: i32 = 21; // provenance: peeked -- OAM y, constant captures 90-129
const VULCAN_FIREBALL_FIRST_VISIBLE: u8 = 99; // provenance: peeked -- x wraps on-screen (509 -> -3) at capture 104 = gun-age 99
const VULCAN_FIREBALL_LAST_VISIBLE: u8 = 112; // provenance: peeked -- still parked past the row's end (capture 117+)
/// Canon's object palette bank 11 on the fireball's frames (dumped off OBJ
/// pal RAM at capture 110): baked as a `&'static` so the sprite takes the
/// static loader path (`PaletteVramSingle::new`) rather than a runtime
/// colour-keyed bank -- the runtime path's extra bank turned the navi gray
/// on every frame of this row (mechanism not traced, see the ticket report).
// provenance: derived -- canon OBJ palette RAM bank 11, dumped at capture 110 (/tmp/f12dump/objpal.bin)
static VULCAN_FIREBALL_PAL: Palette16 = Palette16::new([
    Rgb15::new(0x0000),
    Rgb15::new(0x7fff),
    Rgb15::new(0x5294),
    Rgb15::new(0x163c),
    Rgb15::new(0x1536),
    Rgb15::new(0x7c1f),
    Rgb15::new(0x53be),
    Rgb15::new(0x6b5a),
    Rgb15::new(0x7c1f),
    Rgb15::new(0x14a5),
    Rgb15::new(0x0e5e),
    Rgb15::new(0x013d),
    Rgb15::new(0x175f),
    Rgb15::new(0x1f9f),
    Rgb15::new(0x10df),
    Rgb15::new(0x24d7),
]);
fn vulcan_fireball_x(age: u8) -> i32 {
    if age >= VULCAN_FIREBALL_PARK_AGE {
        VULCAN_FIREBALL_PARK_X
    } else {
        (VULCAN_FIREBALL_X0 + VULCAN_FIREBALL_DX * (age as i32 - VULCAN_FIREBALL_X0_AGE as i32))
            & 0x1FF
    }
}
/// AirShot (attack family 0x21, sub_80EC884): animation 9 and the arm
/// object from the first frame, sound 0xaf; the hit goes out on the frame
/// the counter reads 5 -- the sixth -- as an instant one-panel hitbox one
/// panel ahead (sub_80C4FFE -> t3_0x0_80C4E58: no travelling shot); the
/// first state hands over when the counter reads 10 and the second counts
/// it back down, exiting on the 22nd frame (sub_80EC8A0, sub_80EC90E;
/// asm31.s:111067-111142). So the pose is on screen 21 frames.
// provenance: derived -- sub_80EC8A0/sub_80EC90E, asm31.s:111067-111142.
const AIRSHOT: actor::AttackSpec = actor::AttackSpec {
    windup: None,
    anim: 0x9,
    frames: 21,
    strike_at: 6,
    recover: 0,
    recover_anim: None,
    pose: None,
};
/// The AirShot arm object lives as long as the pose (byte_80B8BD4 row
/// 0x13: effect list 0xC index 0x18 = sprite_83138C4, animation 0 -- the
/// barrel, four frames of muzzle gust, the barrel held -- at arm-position
/// row 0xa: +18 forward, 24 up, byte_80188C0[20..22]).
const AIRSHOT_FRAMES: u8 = 21; // provenance: derived -- sub_80EC8A0/sub_80EC90E, asm31.s:111067-111142
const AIRSHOT_ARM: (i32, i32) = (18, -24); // provenance: derived -- byte_80B8BD4 row 0x13, byte_80188C0[20..22]
/// The Recov chips heal their names; the amounts are byte_80EC870
/// (asm31.s:111044), one per subfamily.
const RECOV_HP: [u16; 9] = [10, 30, 50, 80, 120, 150, 200, 300, 1000]; // provenance: derived -- byte_80EC870, asm31.s:111044
/// The heal effect's animation length, from its frame durations.
const HEAL_FRAMES: u8 = 14; // provenance: derived -- the sprite's own frame durations
/// Invisibl's timer is its first parameter, 0x68 (ChipDataArr.s:5490).
const INVISIBL_FRAMES: u16 = 0x68; // provenance: derived -- ChipDataArr.s:5490
/// Barrier's HP for type 1 is 10 (byte_8020B2C, dat01.s:189).
const BARRIER_HP: u16 = 10; // provenance: derived -- byte_8020B2C, dat01.s:189
/// Barrier, Barr100 and Barr200 are one chip with one handler: family 0x15
/// subfamily 4 (off_802CCB4[4] = sub_80E3B50), whose first attack parameter
/// indexes byte_8020B2C (data/dat01.s:189) for the bubble's HP. Barrier's
/// parameter is 1 -> row 1 = 10, Barr100's is 5 -> 0x64, Barr200's is 7 ->
/// 0xc8. Nothing else about them differs.
/// The bubble is the same object in another colour: Barrier's is teal,
/// Barr100's gold and Barr200's pink, matched colour for colour against the
/// real captures against sprite_832F8C8's thirteen palettes. The asset is
/// exported with all of them for this.
// provenance: peeked -- matched colour for colour against the real captures.
const BARRIER_PALETTE_GOLD: usize = 3; // provenance: peeked -- matched colour for colour against the real captures (see barrier_palette)
const BARRIER_PALETTE_PINK: usize = 6; // provenance: peeked -- matched colour for colour against the real captures (see barrier_palette)
const fn barrier_palette(id: u16) -> usize {
    match id {
        CHIP_BARR100 => BARRIER_PALETTE_GOLD,
        CHIP_BARR200 => BARRIER_PALETTE_PINK,
        _ => 0,
    }
}

// provenance: derived -- byte_8020B2C, data/dat01.s:189.
const BARR100_HP: u16 = 100; // provenance: derived -- byte_8020B2C, data/dat01.s:189
const BARR200_HP: u16 = 200; // provenance: derived -- byte_8020B2C, data/dat01.s:189
const fn barrier_hp(id: u16) -> u16 {
    match id {
        CHIP_BARR100 => BARR100_HP,
        CHIP_BARR200 => BARR200_HP,
        _ => BARRIER_HP,
    }
}
/// Frames from the press to the effect, measured on the real ROM (the
/// bubble object's first, one-frame dot is behind the navi, so it is
/// created a frame before the bubble shows).
const INVISIBL_PRESENTATION: u16 = 128; // provenance: peeked -- measured on the real ROM
const BARRIER_PRESENTATION: u16 = 45; // provenance: peeked -- canon attack entry (CurAction 0x08->0x14) at capture frame 3, bubble's first visible frame at 49 (diff k=44): attack+46; the spawn fires one frame after the countdown hits 0, so 45
/// AreaGrab's own length is the attack's own: the steal orbs below land on
/// its last frame (canon captures 5..81, burst on 81).
const AREAGRAB_PRESENTATION: u16 = 77; // provenance: fitted -- held value pending the orb mechanism, not a measurement
/// AreaGrab's steal orb: the type-3 object 0xf (sub_80C6548 -> t3_0xf_80C6414,
/// asm31.s:30658/30497). sprite_load(0x80,0x0c,0x13) = sprite_830E44C
/// (data/SpritePointersList.s:105), noShadow, CurAnim 0, Z 0x1000000 falling
/// 0x80000 a frame; on landing the panel is stolen, CurAction 4 -> CurAnim 1
/// (SE 0xa2), destroy at anim end (sub_80C64A0/sub_80C6524/sub_80C6536,
/// asm31.s:30560-30650). Chip 163's attack parameter is nonzero, so the
/// sub_80E0754 loop (asm31.s:85522) spawns one orb per row (PanelY 1..3) at
/// the enemy half's edge column, all on the same frame -- the OAM watch
/// shows three 16x32 pairs at x124/140, tile 31, pal 1, falling 8px/frame
/// from captures 62/65/68 and all three bursting (anim 1) on capture 81.
const AREAGRAB_ORB_Z0: i32 = 0x1000000; // provenance: derived -- dword_80C656C, asm31.s:30672
const AREAGRAB_ORB_ZVEL: i32 = 0x80000; // provenance: derived -- dword_80C6568, asm31.s:30670
/// Presentation age the orbs spawn at: canon spawns them on logic 48, 45
/// frames after the chip press (capture 3 -- OAM watch: nothing at the edge
/// column before, culled above, first pair at capture 62) -- and our fire
/// sits 2 frames earlier in this row's locked alignment, so ours spawn at
/// the same age off the chip fire and land on the row's last two frames.
const AREAGRAB_SPAWN_AGE: u16 = 47; // provenance: peeked -- spawn k=43 both sides (OAM trajectory back-extrapolation); ours 47 post-fire, canon 45 post-press
/// The falling / landing-burst animations of sprite_830E44C.
const AREAGRAB_FALL_ANIM: usize = 0; // provenance: derived -- sub_80C6438 sets CurAnim 0, asm31.s:30517
const AREAGRAB_BURST_ANIM: usize = 1; // provenance: derived -- sub_80C6524 sets CurAnim 1, asm31.s:30560
/// Fall palette: the live fall holds anim 0's first frame (object_updateSprite
/// is skipped during the chip timefreeze, so the OAM tile-31/pal-1 pair never
/// changes -- OAM watch, captures 62..80) while the bank it sits in walks the
/// sprite's rows one step per frame (OBJ palette watch). The walk phase is
/// pinned by the row itself: with a constant add of 1 the row reads ~0 every
/// 4th fall frame exactly where orb age % 4 == 2, so the live value there is 1
/// and the cycle is (age + 3) % 4.
const AREAGRAB_ORB_PAL_PHASE: usize = 3; // provenance: peeked -- constant-add-1 probe reads ~0 at orb ages 18, 22, 26, 30 (row k=61, 65, 69, 73)
/// Fall palette cycle length: the live OBJ palette walks the sprite's rows
/// one step per orb age past the spawn frame (OBJ palette watch).
const AREAGRAB_ORB_PALS: usize = 4; // provenance: peeked -- OBJ palette RAM walk, one row per frame
/// Top cull: canon writes no OAM until the pair's top passes -28 (first
/// watch entry), one 8px step inside -32.
const AREAGRAB_ORB_CULL_TOP: i32 = -32; // provenance: peeked -- first orb OAM at y=-28, nothing above (OAM watch)
/// Bottom of the visible screen; the burst sits on its panel, always inside.
const AREAGRAB_ORB_CULL_BOTTOM: i32 = 160; // provenance: derived -- GBA screen height
/// One steal orb in flight: fixed x/y (its panel's centre), Z height in the
/// game's 16.16, age in frames since the shared spawn frame; landed once Z
/// reaches 0, bursting from the next frame.
struct AreagrabOrb {
    player: spr::Player,
    x: i32,
    y: i32,
    z: i32,
    age: u8,
    landed: bool,
    burst: bool,
}

impl AreagrabOrb {
    /// Screen position; the game truncates Y and Z separately (cf. Bomb).
    fn position(&self) -> (i32, i32) {
        (self.x, self.y - (self.z >> Q16_SHIFT))
    }
}
/// The thrown bomb (sub_80C5DBC -> t3_0x8_80C5BB0, asm31.s:29657, 29400):
/// spawned 4 pixels ahead of the navi and 0x30 up, sprite_82F569C
/// animation 1 with a shadow; it flies at 0x2e666 (2.9 px) a frame
/// forward, its vertical speed starting at 0x20666 (2.02 px) a frame and
/// losing 0x2800 (0.156 px) a frame (byte_80C5D58, asm31.s:29609), for a
/// fixed 0x28 frames (asm31.s:29531), which is about three panels.
const BOMB_FLIGHT: u8 = 40; // provenance: derived -- byte_80C5D58, asm31.s:29531/29609, the disassembly's own data table
/// BlkBomb's ball covers the same three panels more slowly: measured against
/// the real ROM, its leading edge moves 70 px over the 27 frames where
/// MiniBomb's moves 74, so the flight is 42 frames rather than 40. The
/// horizontal speed scales down with that and the launch speed up, so the arc
/// still lands flat.
const BLKBOMB_FLIGHT: u8 = 42; // provenance: peeked -- measured against the real ROM's leading-edge pixel movement
/// BlkBomb is thrown flatter and slower than a MiniBomb: the same 0x2800 pull
/// but less of both speeds. Read out of the object by `tools/throw_dump.py 3c`
/// rather than swept -- the sweep that preceded it landed on 0x27C0 and
/// 0x22051, which draws the same pixels because a pull 0x40 too soft and a
/// launch 0x31D too weak cancel over the flight.
const BLKBOMB_GRAVITY: i32 = 0x2800; // provenance: peeked -- read out of the live object by tools/throw_dump.py, not swept
const BLKBOMB_VX: i32 = 0x2C000; // provenance: peeked -- read out of the live object by tools/throw_dump.py
const BLKBOMB_VZ: i32 = 0x2236E; // provenance: peeked -- read out of the live object by tools/throw_dump.py
/// LilBolr lobs its boiler far higher than a bomb: measured on the real ROM
/// the ball rises to y=10, about a hundred pixels above the panel, peaking
/// eleven frames in and landing on the same fortieth frame a bomb does. That
/// needs a faster launch and a stronger pull, solved from those two figures.
/// Where the damage tag sits relative to the projectile's origin, measured
/// off the real ROM's object list.
const DAMAGE_TAG_RIGHT: i32 = 32; // provenance: peeked -- measured off the real ROM's object list
const DAMAGE_TAG_DOWN: i32 = 30; // provenance: peeked -- measured off the real ROM's object list
/// FlshBom's arc is taller than a bomb's and it comes down harder. Solved
/// against the real ROM's ball tracked frame by frame by its four yellow
/// colours over the whole forty-frame flight: it leaves the hand at y48,
/// peaks at y32 held from frame 20 to 24, and is back down at y90 on frame
/// 47. Fitting only the first thirty frames gives a curve that is right at
/// the peak and six pixels low at the end, so the fit has to run to the
/// landing.
///
/// Read out of the object by `tools/throw_dump.py 39`, which also says why the
/// earlier fit had to be "a step behind": FlshBom's ball, like VDoll's doll,
/// MOVES AND THEN FALLS rather than falling and then moving, so a build that
/// applies the pull first needs a launch one whole gravity step higher to draw
/// the same arc. The fit had found 0x2BD00, which is 0x28CCC + 0x3000 to
/// within 0x34. With the order right the launch is the game's own number.
const FLSHBOM_VZ: i32 = 0x28CCC; // provenance: peeked -- read out of the live object by tools/throw_dump.py 39
const FLSHBOM_GRAVITY: i32 = 0x3000; // provenance: peeked -- read out of the live object by tools/throw_dump.py 39
/// The summoned LilBoiler's own HP, which rides under it in the game's object
/// digits. All three LilBolrs show 40 against powers of 100, 140 and 180.
/// Where the chip-in-hand icon's top left sits relative to the navi's panel
/// centre, measured off the real ROM's OAM.
const HAND_ICON_AT: (i32, i32) = (-1, -56); // provenance: peeked -- measured off the real ROM's OAM

/// The icon's OBJECT palette, byte_872CFD4, which the exporter reads: it is
/// not the chip window's icon bank, which is a background palette and differs
/// at two entries.
/// The BNHI asset's header: a 4-byte magic, then a version word, then the
/// sixteen 2-byte BGR555 palette entries at byte 8
/// (tools/hand_icon_export.py's own layout).
const BNHI_MAGIC_LEN: usize = 4; // provenance: derived -- tools/hand_icon_export.py's own BNHI layout
const BNHI_PALETTE_AT: usize = 8; // provenance: derived -- tools/hand_icon_export.py's own BNHI layout
const BNHI_PALETTE_COLOURS: usize = 16; // provenance: derived -- tools/hand_icon_export.py's own BNHI layout
const BGR555_BYTES: usize = 2; // provenance: derived -- one BGR555 palette colour is two bytes
fn hand_icon_palette() -> PaletteVramSingle {
    let data = crate::HAND_ICON;
    assert_eq!(&data[0..BNHI_MAGIC_LEN], b"BNHI", "not a BNHI asset");
    let mut colours = [agb::display::Rgb15::new(0); BNHI_PALETTE_COLOURS];
    for (i, slot) in colours.iter_mut().enumerate() {
        let o = BNHI_PALETTE_AT + i * BGR555_BYTES;
        *slot = agb::display::Rgb15::new(u16::from_le_bytes(data[o..o + BGR555_BYTES].try_into().unwrap()));
    }
    PaletteVramSingle::try_allocate_shared(&agb::display::Palette16::new(colours))
        .expect("hand icon palette should fit in vram")
}
const BOILER_HP: u16 = 40;
/// Where that figure sits relative to the projectile's origin: measured on
/// the real ROM's frames 13, 20 and 30, its two digits span sixteen pixels
/// starting at the projectile's own x and its top is three below.
const BOILER_HP_RIGHT: i32 = 16; // provenance: peeked -- measured on the real ROM's frames 13, 20 and 30
const BOILER_HP_DOWN: i32 = 3; // provenance: peeked -- measured on the real ROM's frames 13, 20 and 30
/// LilBolr's flight is BLKBOMB'S, exactly: `tools/throw_dump.py 62` reads the
/// same 0x2C000 across, 0x2236E up and 0x2800 down out of the boiler that
/// `throw_dump.py 3c` reads out of the bomb. Two sweeps had found two nearby
/// but different answers, which is the sweep's weakness -- a ridge of
/// (vz, gravity) pairs all draw the same pixels, so nothing tells you the two
/// chips share one launcher until you read the numbers.
// provenance: peeked -- tools/throw_dump.py 62 reads the same three values out
// of the live boiler that throw_dump.py 3c reads out of the bomb.
const LILBOLR_VX: i32 = BLKBOMB_VX;
const LILBOLR_VZ: i32 = BLKBOMB_VZ;
const LILBOLR_GRAVITY: i32 = BLKBOMB_GRAVITY;

/// The afterimage's age when it is drawn for the last time. It is spawned
/// during the frame that uses the chip and aged in that same frame, so an age
/// of 1 is the attack's frame 0. Measured against the real ROM: drawn on the
/// attack's frames 1-2, 5-6, 9-10, 13-14 and 17-18, and gone from 19 on.
const STEP_GHOST_LAST: u8 = 19; // provenance: peeked -- measured against the real ROM's drawn frames
/// The panel the navi steps TO gets a second red afterimage of its own from
/// the attack's frame 8, blinking two on and two off through frame 29. Unlike
/// the one left at home this is not a single still: it TRAILS the navi by
/// exactly three frames. Read out of the real ROM's OAM, object for object --
/// on frame 16 the red copy's four sprites have precisely the sizes and
/// positions the navi's had on frame 13, and on frame 17 the same, and on
/// frame 12 those of frame 9. It outlives the step: the navi is home from
/// frame 24 and the copy is still blinking there at 29.
const STEP_GHOST2_FIRST: u8 = 9; // provenance: peeked -- read out of the real ROM's OAM, object for object
const STEP_GHOST2_LAST: u8 = 34; // provenance: peeked -- read out of the real ROM's OAM, object for object
/// The age at which the step's bookkeeping is dropped.
const STEP_STATE_LAST: u8 = 34;
const BOMB_SPAWN_AHEAD: i32 = 4 << 16; // provenance: derived -- sub_80C5DBC, asm31.s:29657
const BOMB_SPAWN_UP: i32 = 0x30 << 16; // provenance: derived -- sub_80C5DBC, asm31.s:29657
const BOMB_VX: i32 = 0x2e666; // provenance: derived -- byte_80C5D58, asm31.s:29609
const BOMB_VZ: i32 = 0x20666; // provenance: derived -- byte_80C5D58, asm31.s:29609
const BOMB_GRAVITY: i32 = 0x2800; // provenance: derived -- byte_80C5D58, asm31.s:29609
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
/// Which animation of the bomb sprite a bomb plays, held and thrown.
/// MiniBomb, BlkBomb and BigBomb use 0 and 1; EnergBom and MegEnBom use 2
/// and 3. Found by pulling the real bomb's tiles out of OBJ VRAM and looking
/// for those exact bytes among the sprite's graphics blobs (see bomb_anim's
/// own doc below).
const BOMB_ANIM_ENER_HELD: usize = 2; // provenance: derived -- the sprite's own graphics blobs (see bomb_anim)
const BOMB_ANIM_ENER_THROWN: usize = 3; // provenance: derived -- animation 3 is a five-frame loop at four frames each, the bomb tumbling (see bomb_anim)
const BOMB_PALETTE_BLK_HELD: usize = 4; // provenance: derived -- byte_80EB738 row 0x2d, asm31.s:108898 (see bomb_palette)
const BOMB_PALETTE_BIG: usize = 3; // provenance: derived -- byte_80C5BA0[3]'s fourth byte, asm31.s:29422 (see bomb_palette)
const BOMB_PALETTE_ENER: usize = 5; // provenance: peeked -- the only one of sprite_82F569C's thirteen palettes holding the real held bomb's grey, brown and orange (see bomb_palette)
const fn bomb_anim(id: u16, thrown: bool) -> usize {
    match (id, thrown) {
        (CHIP_ENERGBOM | CHIP_MEGENBOM, false) => BOMB_ANIM_ENER_HELD,
        (CHIP_ENERGBOM | CHIP_MEGENBOM, true) => BOMB_ANIM_ENER_THROWN,
        (_, true) => 1,
        _ => 0,
    }
}

const fn bomb_palette(id: u16, thrown: bool) -> usize {
    match (id, thrown) {
        (CHIP_BLKBOMB, false) => BOMB_PALETTE_BLK_HELD,
        (CHIP_BIGBOMB, _) => BOMB_PALETTE_BIG,
        // EnergBom and MegEnBom are MiniBomb's own held sprite row in
        // another palette (byte_80EB738 pair 1, asm31.s:108898), and they
        // throw through the same sub_80C5DBC. The exporter's palette order is
        // not the ROM's, so the index is the measured one: the real held bomb
        // is grey with brown and orange, and palette 5 is the only one of
        // sprite_82F569C's thirteen that holds all of those colours. The
        // asset is exported with every palette so that index exists.
        (CHIP_ENERGBOM | CHIP_MEGENBOM, _) => BOMB_PALETTE_ENER,
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
const HELD_BOMB_FRAMES: u8 = THROW.strike_at - 1; // provenance: derived -- byte_80B8BD4 row 4, the real ROM shows it gone on the throw frame
/// The attack frame the flash bomb's ball is raised on.
const HELD_RAISE_AT: u8 = 5; // provenance: peeked -- measured off the real ROM
/// On a solid panel the landing spreads type-4 effect row 0 -- effect list
/// 0x14 index 0, sprite_8399578, animation 0, 22 frames -- from the panel
/// (sub_801BD3C, asm31.s:29569-29589) with sound 0x70.
const BLAST_FRAMES: u8 = 22; // provenance: derived -- sub_801BD3C, asm31.s:29569-29589
/// Frames the t3_0x11 energy explosion draws. Its update (sub_80C6854,
/// asm31.s:31069) pulses the collision region on the init frame and 7 and 14
/// frames later, then sits in phase 4 for a 0x14 Timer -- drawn init through
/// init+33, destroyed the frame after.
const ENERGBOM_BLAST_FRAMES: u8 = 34; // provenance: derived -- sub_80C6854, asm31.s:31069 (see above)

/// A thrown MiniBomb in flight, in the game's 16.16 coordinates.
struct Bomb {
    player: spr::Player,
    x: i32,
    y: i32,
    z: i32,
    vx: i32,
    vz: i32,
    gravity: i32,
    target: (i32, i32),
    damage: u16,
    /// BigBomb's landing spreads over the panel and its eight neighbours:
    /// the region byte dword_80C5D7C[Param1] is 1 for MiniBomb and 0xf for
    /// BigBomb, and 0xf is the nine-panel offset list byte_8019951
    /// (asm31.s:29619, asm00_2.s:20987). Every panel gets the same puff.
    wide: bool,
    ticks: u8,
    flight: u8,
    /// LilBolr shows its damage riding under the projectile; the bombs do not.
    show_damage: bool,
    /// A seed lays its sheet over the enemy's half where it lands instead of
    /// bursting, in the chip's own palette.
    poison: bool,
    seed_palette: usize,
    /// BugBomb and VDoll land and stay: the object rests on its panel.
    rests: bool,
    /// BugBomb's landing snaps the ball onto its panel (sub_80D9E94
    /// loc_80D9EC2) and VDoll's snaps the doll the same way (sub_80D47C0
    /// loc_80D481E, object_setCoordinatesFromPanels); both freeze through
    /// the rows that follow.
    rest_snaps: bool,
    /// Height the resting object floats at: ten above the panel for BugBomb's
    /// ball, on the panel for VDoll's doll.
    rest_z: i32,
    /// VDoll's landing poisons the panel it rests on (object_setPanelType 4,
    /// sub_80D47C0 loc_80D481E).
    rest_poisons: bool,
    /// Whether the object moves and then feels the pull, rather than feeling
    /// it and then moving. A bomb does the pull first (sub_80C5C9C,
    /// asm31.s:29536); VDoll's doll does it last (sub_80D47C0, asm31.s:60530).
    /// It is half a step of difference, which is a pixel wherever the arc is
    /// steep.
    moves_before_falling: bool,
    /// EnergBom and MegEnBom throw Param1 == 2 (measured live: the thrown
    /// object's +0x4 reads 2 for chips 0x37/0x38, 0 for MiniBomb's 0x36),
    /// which routes the landing through sub_80C5D84's Param1 == 2 branch
    /// (sub_80C68B0, asm31.s:29664 -- the t3_0x11 energy explosion) instead
    /// of the single-panel type-4 blast MiniBomb's Param1 == 0 spreads.
    ener: bool,
}

impl Bomb {
    fn step(&mut self) {
        self.x += self.vx;
        if self.moves_before_falling {
            self.z += self.vz;
            self.vz -= self.gravity;
        } else {
            self.vz -= self.gravity;
            self.z += self.vz;
        }
    }

    /// Screen position of the bomb; the game truncates Y and Z separately.
    fn position(&self) -> (i32, i32) {
        (self.x >> Q16_SHIFT, (self.y >> Q16_SHIFT) - (self.z >> Q16_SHIFT))
    }

    /// Where the shadow goes: on the ground under the bomb.
    fn ground(&self) -> (i32, i32) {
        (self.x >> Q16_SHIFT, self.y >> Q16_SHIFT)
    }
}
/// The CHIP-NAME POPUP. A family-0x15 chip puts its name up in the middle of
/// the screen while it presents -- AreaGrab, Invisibl, Barrier, Barr100 and
/// Barr200 are the five in this build, and the family is what picks them out:
/// `attack_family: 0x15` in `data/ChipDataArr.s`, which nothing else carries.
/// Checked the other way too, by dumping OAM on the attack's 40th frame for
/// every one of the scoreboard's 43 chips: exactly those five put objects up.
///
/// Everything below was read out of the real ROM's OAM frame by frame.
/// One 8x16 object per letter, all at y=32, in OBJ palette bank 11, drawn
/// ahead of everything else (they are OAM entries 0 upward). The strip is
/// CENTRED on x=60: eight letters run 28..92 and seven 32..88.
const POPUP_Y: i32 = 32; // provenance: peeked -- read out of the real ROM's OAM frame by frame
const POPUP_CENTRE: i32 = 60; // provenance: peeked -- read out of the real ROM's OAM frame by frame
const POPUP_CELL: i32 = 8; // provenance: peeked -- read out of the real ROM's OAM frame by frame
/// Frames from the chip's use to the popup's first frame. The real ROM puts it
/// up 21 frames after the button and the attack starts 3 frames after it, so
/// it is the attack's 18th frame -- and 19 counted from here, because the
/// presentation is set on the frame before the attack's first.
const POPUP_AT: u16 = 19; // provenance: peeked -- measured against the real ROM
/// The popup's roll-out is the BANNER's, frame for frame: the same 58-entry
/// vertical-scale sequence, read out of OAM for both. `banner::SCALE` holds it.
/// OBJ palette bank 11 while the popup is up, read straight out of palette RAM
/// at 0x5000360. It is the battle text font's own object bank, and it is the
/// same sixteen colours for every one of the five chips.
const POPUP_PALETTE: [u16; 16] = [ // provenance: peeked -- read straight out of palette RAM at 0x5000360
    0x0000, 0x7ffe, 0x14a5, 0x03e0, 0x7bde, 0x7fbc, 0x7f99, 0x6e6f,
    0x61cc, 0x037f, 0x029f, 0x0280, 0x3547, 0x37f6, 0x7bd1, 0x4108,
];

/// The name in flight: one sprite per letter, built once when the chip is
/// used, and a frame counter.
struct NamePopup {
    letters: Vec<SpriteVram>,
    /// Screen x of the leftmost letter, from centring the strip on x=60.
    left: i32,
    t: u16,
}

impl NamePopup {
    fn new(name: &str) -> Self {
        // The RAW half of the battle text font: the asset carries the plain
        // glyphs and then a colour-added copy, and the popup uses the plain
        // ones -- checked byte for byte against the tiles the real ROM leaves
        // at 0x6016E00 for every letter of "Barrier".
        let font = crate::TEXT_FONT;
/// The BNTF font's glyph-table pointer sits 8 bytes into the header
/// (tools/font_export.py's own layout, shared with custom::BNTF_TABLE_OFF);
/// entries are 4-byte words and the popup uses the raw first half of the
/// glyph data.
const BNTF_GLYPH_TABLE_AT: usize = 0x08; // provenance: derived -- tools/font_export.py's own BNTF layout
const BNTF_WORD_LEN: usize = 4; // provenance: derived -- tools/font_export.py's own BNTF layout
const BNTF_RAW_HALF_DIV: usize = 2; // provenance: derived -- the popup uses the raw first half of the glyph data (see NamePopup::new)
        let at = |o: usize| u32::from_le_bytes(font[o..o + BNTF_WORD_LEN].try_into().unwrap()) as usize;
        let fo = at(BNTF_GLYPH_TABLE_AT);
        let raw = &font[fo + BNTF_WORD_LEN..fo + BNTF_WORD_LEN + at(fo) / BNTF_RAW_HALF_DIV];
        let palette = PaletteVramSingle::try_allocate_shared(&agb::display::Palette16::new(
            POPUP_PALETTE.map(agb::display::Rgb15::new),
        ))
        .expect("popup palette should fit in vram");
        let letters: Vec<SpriteVram> = name
            .as_bytes()
            .iter()
            .map(|&c| {
                let g = custom::char_code(c) as usize * GLYPH_BYTES;
                DynamicSprite16::from_bytes(Size::S8x16, &raw[g..g + GLYPH_BYTES])
                    .to_vram(palette.clone())
            })
            .collect();
        let left = POPUP_CENTRE - letters.len() as i32 * POPUP_CELL / 2; // canon: POPUP_CENTRE centring
        Self { letters, left, t: 0 }
    }

    /// Advance a frame; false once the popup has rolled up and gone.
    fn update(&mut self) -> bool {
        self.t += 1;
        self.t < POPUP_AT + banner::SCALE.len() as u16
    }

    fn show(&self, frame: &mut GraphicsFrame) {
        let Some(&scale) = self
            .t
            .checked_sub(POPUP_AT)
            .and_then(|i| banner::SCALE.get(i as usize))
        else {
            return;
        };
        let matrix = AffineMatrixObject::new(AffineMatrix::<Num<i32, 8>> { // canon: 8.8 fixed-point affine entries
            a: Num::from_raw(AFFINE_UNITY),
            b: Num::from_raw(0),
            c: Num::from_raw(0),
            d: Num::from_raw(scale as i32),
            x: Num::from_raw(0),
            y: Num::from_raw(0),
        });
        for (i, letter) in self.letters.iter().enumerate() {
            ObjectAffine::new(letter.clone(), matrix.clone(), AffineMode::Affine)
                .set_priority(Priority::P0)
                .set_pos((self.left + i as i32 * POPUP_CELL, POPUP_Y))
                .show(frame);
        }
    }
}

/// 0x100 is 1.0 in the affine matrix's 8.8 fixed-point entries: the popup
/// keeps the X axis unscaled and scales Y by the banner roll-out.
const AFFINE_UNITY: i32 = 0x100; // provenance: derived -- 8.8 fixed-point 1.0 in the affine matrix
/// Bytes of one 8x16 glyph in the battle text font: two 4bpp tiles.
const GLYPH_BYTES: usize = 64;

const GAUGE_FULL: u16 = 0x4000; // provenance: derived -- sub_800855E, asm00_1.s:11100
const GAUGE_PAUSE: u16 = 60; // provenance: peeked -- "about 60 frames of chimes" measured on the real ROM
// The end sequence as canon's sequencer states it, one count per state
// (F32b, watched on the real ROM on the zero-enemy route -- STERILE +
// PAUSED + DELETE + Start@10 -- and identical on the warp/buster/chip-use
// poke variants: dword_203CA70 0x08->0x0C at capture 47, 0x0C->0x0400000C
// with the HUD teardown at 48 (mask 0x020352C0 0x4497->0x8084), the ENEMY
// DELETED banner's OBJ first differing at 49 and gone by 108 (roll-up
// 99..107; the mask's bit 15 reads 0x8084 at 48..105, 0x0084 from 106),
// the results driver's first slide tick at 154 and its 14th at 167,
// settled at 168, the mark OBJ entering 164..167 -- all from --watch and
// consecutive-frame consec-diffs of --disable-bg/--only-bg-3 captures).
// From the 0x0C frame that is banner at +2, banner down at +59..61,
// first slide at +107, settled at +121, mark at +117. The result_arrival
// route shows the same driver chain mid-flight and tick-identical to ours:
// canon's BG3 slide ticks at result_arrival frames 19..32 read per-tick
// 2786,4307,4956,5049,5403,6408,6887,7220,7574,7874,8402,9860,12817,9003
// px, and ours at 31..44 read the same 14 values in the same order (F34's
// chain holds; the result row reads 0).
// NOT ADOPTED (measured 2026-09-14): arming the banner at over+2, canon's
// own +2, moves field integrated 158950->158954 (worst 5621->5625): the
// only pixel difference anywhere is 12 BG0 px on the show frame (capture
// 121 -- BG palette RAM peeked identical old-vs-new at that frame, so tile
// content; OBJ/BG1/BG2/BG3 all 0 there and every other frame 67..169 is 0).
// The upload/content path that carries a 2-frame banner shift 50+ battles
// forward into the backdrop was not traced, so the banner stays at over+0
// and the RESULT show stays at over+110 -- where field's fixture lands its
// setup (BG3 writes at capture 121/122), first slide (140) and settle
// (154) today. Canon's setup (banner down +59, first slide +107, i.e. a
// 48-frame driver setup against our show-to-slide 18 = SLIDE_HOLD 16 + 2)
// cannot sit at both field's score-locked offset and the three zero-enemy
// rows' subject offsets at once (F38b: warp needs the slide at battle ~72,
// buster at ~122, 50 apart under one schedule), so that setup-duration
// delta stays OPEN with this ticket.
// T7 (2026-09-14): the hand-written `over` flag below is now the table
// (Sequencer: 0x08 the fight, 0x0C/0x10 the end counts, transition edge at
// dissolve expiry) with the same frames and the real word exported to the
// trace. What the table does NOT do: per-state counts and handlers (the
// 94-count plus 16-frame setup factored the 110 composite with the same
// show frame by construction, but regressed field +12 on one frame and was
// reverted -- see RESULTS_DELAY), the entry timing (teardown/banner stay on
// the transition update; canon runs them the update after, moving them
// regressed field +4, measured above), the opening states (0x00/0x04), the
// 0x14/0x18+ edges, and the driver setup (canon slides at 0x0C+107).
/// Frames the closing banner runs: canon's 49..106 mask window (up 49,
/// gone by 108); banner.rs's own SCALE already runs this long.
const BANNER_FRAMES: u16 = 58; // provenance: peeked -- mask bit 15 set at canon 48..105, banner OBJ 49..107, same captures (F32b)
const _: () = assert!(BANNER_FRAMES as usize == banner::SCALE.len());
/// Canon's banner-sequencer states: the low byte of dword_203CA70, which is
/// what sub_800801C dispatches on (asm00_1.s:10422, table off_8008038).
/// 0x00/0x04 run the opening banners, 0x08 is the fight itself (sub_80080D2),
/// 0x0C/0x10 count the end (sub_80081A4 win, sub_800825A lose), 0x14 is
/// sub_80082DC's message count; 0x18-0x24 are the sibling branch that only
/// runs where sub_800A152 returns 7.
const SEQ_08: u32 = 0x08; // provenance: derived -- off_8008038 entry 2 (sub_80080D2, the fight)
const SEQ_0C: u32 = 0x0C; // provenance: derived -- off_8008038 entry 3 (sub_80081A4, the win count)
const SEQ_10: u32 = 0x10; // provenance: derived -- off_8008038 entry 4 (sub_800825A, the lose count)
/// Frames from `over` to the RESULT show: kept at field's landing (show at
/// battle 110 = BG3 setup at capture 121/122, slide 140..153). A fitted
/// composite, not canon's count (canon's setup starts at 0x0C+59 and its
/// first slide lands at +107); the delta is the OPEN setup-duration gap.
/// T7 tried factoring it as the table's own 94-count plus a 16-frame driver
/// setup (94+16 = 110, same show frame by construction) and reverted the
/// factoring on a measured +12 regression (field integrated 158950->158962,
/// one frame, capture 121's y14-30 band; mechanism untraced, not chased
/// further within this ticket): the countdown/show below is byte-for-byte
/// the old sequence, and only the state dispatch above it is the table's.
const RESULTS_DELAY: u16 = 110; // provenance: fitted -- field's measured show frame, unchanged by this ticket
/// Canon's banner sequencer as its state table (T7): `state` is dword_203CA70's
/// low byte (0x08 the fight, 0x0C/0x10 the end counts), dispatched where the
/// old hand-written `over` flag was read. The per-state counts and handlers
/// (94-count, handoff, driver setup) stay the old composite (see RESULTS_DELAY):
/// what the table owns is the state dispatch, the transition edge and the
/// word the trace exports -- the frames are the old ones by construction.
struct Sequencer {
    state: u32,
}
impl Sequencer {
    /// A live fight: canon enters battle reading 0x08 (battle_full's watch:
    /// 0x1c->0x08 at capture 11).
    fn battle() -> Self {
        Self { state: SEQ_08 }
    }
    /// The watched word's low half, which is what the TRC2 block exports:
    /// the state byte (byte 1 reads 0 on both sides).
    fn word_lo(&self) -> u16 {
        self.state as u16
    }
    /// The 0x08 -> end edge: the transition write itself (sub_80080D2's
    /// `str r0,[r5]`), which also clears the entry byte.
    fn transition(&mut self, state: u32) {
        self.state = state;
    }
}
/// Frames from the first chip window closing to BATTLE START!. Measured on the
/// real ROM from a save state at a battle's first frame: the window opens at
/// 165 on its own, is confirmed, closes at 259, and the banner goes up at 289.
const BATTLE_START_AFTER_WINDOW: u16 = 30; // provenance: peeked -- measured on the real ROM
/// Frames from the last combatant going down (the death action's first
/// frame) to the end sequence -- the banner sequencer's RESULT countdown
/// 0x0C. Watched on the real ROM on two routes: PAUSED with the Mettaur's
/// HP forced to 0 and Start@10 (death action at capture frame 12, 0x0C at
/// 47) and a live Cannon kill on the same state (HP 0 at 61, 0x0C at 96).
/// Both give 35: the enemy-object routine at ROM 0x08016676 counts the
/// dissolve (timer +0x20 set 0x1f, one a frame, death entered at 0x0801B290,
/// gone entered at 0x080166A0) and the battle main at 0x0800A09F calls into
/// sub_80081A4, whose instruction at 0x0800811E writes 0x0C to dword_203CA70
/// (teardown follows in the same routine, byte3 init at 0x080081CA). NOTE:
/// F27b's prose calls this gap 47 -- that is the 0x0C CAPTURE frame on the
/// HP-forced route, i.e. 12 paused frames (Start@10 plus the resume) plus
/// these 35 live ones, not an event-locked count from the killing hit.
const DISSOLVE_FRAMES: u8 = 35; // provenance: peeked -- death-action frame to sequencer 0x0C, --watch/--watch-write on 0x0203ca70/0x0203ab68/0x0203ab80, real ROM, two routes, 2026-09-14 (F32)

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
    /// SuprVulc's detached muzzle-fire ball: a prebuilt 16x16 VRAM sprite
    /// (canon's tile-512 art, palette above) plus its age in gun-ages (None
    /// on its spawn frame, then 0, 1, ...).
    vulcan_fireball: Option<(SpriteVram, Option<u8>)>,
    /// AreaGrab's steal orbs in flight (see AREAGRAB_ORB_Z0): spawned together
    /// at AREAGRAB_SPAWN_AGE, falling, bursting and stealing on landing.
    areagrab_orbs: Vec<AreagrabOrb>,
    /// A family-0x15 chip mid-presentation: the game freezes time, dims the
    /// screen and shows the chip's name before the effect lands
    /// (object_timefreezeBegin, object_dimScreen, object_drawChipName;
    /// object.s:95-287). The lengths are measured on the real ROM -- the
    /// bubble appears 46 frames after the attack entry for Barrier (CurAction
    /// 0x08->0x14 at capture frame 3, first bubble pixels at capture 49),
    /// the flicker starts 128 after for Invisibl -- as the banner's own
    /// timing was not traced. The dim itself is not drawn yet.
    presentation: Option<(Chip, u16)>,
    /// The chip name in the middle of the screen while a family-0x15 chip
    /// presents. It outlives the presentation for Barrier (58 frames from the
    /// attack's 18th against the presentation's 77) and is outlived by it for
    /// Invisibl, so it runs on its own clock rather than the presentation's.
    popup: Option<NamePopup>,
    /// The wide ribbon across the middle of the screen -- ENEMY DELETED when
    /// the last enemy goes, MEGAMAN DELETED when the navi does.
    banner: Option<Banner>,
    banner_assets: banner::Assets,
    /// Whether the fight's closing banner has been asked for, so it is asked
    /// for once.
    banner_done: bool,
    /// T8 (docs/coverage/plan-interpreters.md §3): both script interpreters --
    /// the map VM and the chatbox text VM -- with the state each walks from.
    /// Nothing in this build installs a script, so both stop at canon's own
    /// "nothing installed" gates and never fetch; see the hook in `update`.
    scripts: script::Scripts<'a>,
    /// Whether BATTLE START! has been put up, likewise once.
    opened: bool,
    /// Whether the FIRST chip window has closed yet, in every build.
    /// `opened` cannot serve: it is deliberately left false when a fixture
    /// is present so `banner_at` is not armed for fixtures that compare
    /// against mid-battle captures, and the gauge needs the plain fact.
    window_closed: bool,
    /// The window's state machine flips Done on its tenth slide-out call,
    /// but canon's scroll reset and HUD redraw wait a frame: RenderInfo+0x18
    /// still reads 0x78 on slide frame 90 and 0 on blank frame 91, and the
    /// gauge redraw lands on frame 92 (F18c, peeked -- watch 0x0200ac58).
    /// While set, the HUD stays in menu mode so no redraw leaks onto the
    /// blank frame; the next update performs the visible reset instead.
    close_redraw_pending: bool,
    /// Frames until it goes up, counting down from the chip window closing.
    banner_at: u16,
    /// Frames until the buster's blip sounds; see BUSTER_BLIP_DELAY.
    blip_in: u8,
    /// Frames until it is silenced again; see BUSTER_BLIP_FRAMES.
    blip_off: u8,
    /// Frames until the buster's hit sample plays; see BUSTER_HIT_DELAY. No
    /// off-timer needed: unlike the PSG blip, the DirectSound sample is
    /// fire-and-forget and stops itself when it runs out of data.
    hit_in: u8,
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
    step_trail: [((usize, usize), (i32, i32)); STEP_TRAIL_LEN],
    step_trail_sword: [Option<(usize, usize)>; STEP_TRAIL_LEN],
    /// The panel the step went to. The afterimage keeps taking new frames
    /// after the navi has gone home -- frame 24's copy carries the navi's
    /// frame-21 sprite -- but only from frames where the navi was still over
    /// there, so the trail is followed by position, not by a cut-off.
    step_dest: (i32, i32),
    /// The flash bomb's held ball is RAISED partway through the throw, and its
    /// sprite does not encode that -- every frame of it carries the same part
    /// offsets, where MiniBomb's animation moves the bomb itself. Measured on
    /// the real ROM: the ball sits at (37,88) through the attack's frame 4 and
    /// at (51,64) from frame 5. This counts down to that move and carries
    /// where to put it. It applies to the first effect, which for a bomb chip
    /// is the held ball and the only one on the field then.
    held_raise: Option<(u8, (i32, i32))>,
    /// Frames until the sword object is spawned: the two lead-in states
    /// (sub_80EB79C, sub_80EB84C: one frame each) before the slash state
    /// that creates it.
    sword_in: Option<u8>,
    bombs: Vec<Bomb>,
    panels: Panels,
    /// AUDIT wave 3d "bg3-merge": an always-empty background shown first
    /// (except while the RESULT window is up -- see `draw`'s own comment),
    /// purely so `backdrop`/`bg`/`hud_bg` land on hardware BG1/2/3 the way
    /// canon's own (BG0 unused) do, instead of BG0/1/2. A similar filler was
    /// tried and reverted in the wave-3c "zero-layers" ticket, there
    /// measuring a real one-frame boot-length shift from the extra
    /// `RegularBackground::new()` call. This ticket's own version of that
    /// same experiment measured clean instead -- tools/harness.py --only
    /// opening: isolated stayed at 0 with the SAME search offset, both
    /// before and after adding this field -- but boot length moving with
    /// unrelated code (AUDIT pair 1) means that clean result is a property
    /// of THIS commit's own instruction count, not a guarantee; if a future
    /// change ever needs to shave a frame back, this field is the first
    /// thing to revert.
    filler_bg: RegularBackground,
    bg: RegularBackground,
    /// Absent in the sterile arena, which shows neither: building them there
    /// still claimed video memory and starved the barrier bubble's sprite.
    backdrop: Option<crate::backdrop::Backdrop>,
    /// How far the field has slid out of the chip menu's way, in half-pixels.
    field_slide: u16,
    emotion: crate::emotion::Emotion,
    /// Whether canon's battle-HUD element 14 (the emotion window) is still
    /// enabled -- see `Emotion`'s own gate in `draw` for the canon rule and
    /// the measurement.
    hud_live: bool,
    /// Frames until a seed's sheet goes down, counted from the pod landing,
    /// and the palette it takes.
    poison_pending: u8,
    poison_palette: usize,
    /// Frames until EnergBom/MegEnBom's energy explosion starts, counted
    /// from the bomb landing, and the panel it starts on. Canon's spawn runs
    /// in the CurAction-4 handler (sub_80C5D84, asm31.s:29664), a frame after
    /// the Timer-0 landing frame, and the new object draws its first frame
    /// from init -- measured: the ball is gone on canon 53, the ring's first
    /// dot shows on 54. Same one-frame delay shape as poison_pending above.
    ring_pending: u8,
    ring_target: (i32, i32),
    /// The palette for the chip-in-hand icon the game hangs over the navi.
    /// None in the sterile arena, which does not draw the icon: the bank it
    /// would hold is one the longest volley needs. SuprVulc panicked with
    /// "sprite palette should fit in vram" until this was made optional.
    hand_icon_palette: Option<PaletteVramSingle>,
    hud_tiles: Option<crate::hudtiles::HudTiles>,
    /// AUDIT wave 3d "bg3-merge": the ONE hardware background canon shares
    /// between the HUD's HP box, the chip-select window and the RESULT
    /// window (peeked, identical BGxCNT across pausedwithcannon/chipselect/
    /// result_arrival: BG3, priority 1). `Some` exactly when `hud_tiles` is
    /// (created alongside it in `Battle::new`), or lazily the first time
    /// `custom`'s window opens with `hud_tiles` blanked (the isolated
    /// `window`/`card` checks: FLAG_BLANK_HUD with FLAG_OPEN_WINDOW) --
    /// see `open_custom_window`. `hud_tiles` and `custom` each borrow it for
    /// the span of one call, never own it, so both can draw into it in the
    /// same frame; its scroll is 0 whenever `custom` is not driving it
    /// (reset the moment the chip window finishes closing -- canon's own
    /// BG3HOFS does the same, see that reset site's own comment). RESULT
    /// keeps its own, separate background: measured (this ticket) that
    /// canon does NOT scroll BG3 for its slide-in -- RenderInfo's BG0-3
    /// HOFS/VOFS shadows (0x0200ac4c-0x0200ac5b) read a constant 0 across
    /// the whole result_arrival capture (backdrop's own BG1 excepted, which
    /// drifts on its own ambient animation) even while the window visibly
    /// slides in at sub-tile precision, and the HP box's own pixels are
    /// identical between a normal battle frame and a settled RESULT frame
    /// -- so sharing this scroll-driven background would incorrectly drag
    /// the HP box during the chip window's slide (which canon DOES do,
    /// confirmed live: the box visibly moves in lock-step with BG3HOFS
    /// while the chip window opens) while RESULT needs it to stay put.
    /// Canon's real technique for RESULT (not hardware scroll -- likely a
    /// per-frame VRAM tile-bitmap rewrite of the leading edge) is not
    /// identified; reproducing it is future work, not this ticket's
    /// mechanical merge.
    hud_bg: Option<RegularBackground>,
    megaman: Actor,
    /// Sizes differ between debug and release builds: a debug build fights
    /// the Mettaur alone so the hand and chips can be tried without the
    /// bosses, while the release keeps the game's lineup. Everything here
    /// reads whatever length it is.
    enemies: Vec<Actor>,
    ais: Vec<ai::Ai>,
    /// AUDIT wave 3d ticket (mettaur-ai): the battle's own primary generator
    /// (`ai::Rng`, mirroring `ePrimaryRngSeed`) -- a SEPARATE stream from
    /// `deck::Rng` above (`eSecondaryRngSeed`, the folder shuffle's own),
    /// named `primary_rng` rather than `rng` to avoid shadowing the
    /// `deck::Rng` parameter `Battle::new` already takes. Seeded from
    /// FIXTURE.md's `rng` field (+58) and advanced once every battle frame
    /// in `update()`, independent of any enemy's own decisions -- see
    /// `ai::Rng`'s own doc for why (measured: the real ROM's own primary RNG
    /// state advances by exactly one step every rendered frame regardless of
    /// AI branching).
    primary_rng: ai::Rng,
    gunner_ctl: gunner::Gunner,
    impacts: Vec<gunner::Impact>,
    /// Transient sprites: the player, its screen position, frames left, and
    /// whether it is a type-4 effect object -- one the game draws on its
    /// spawn frame with its first animation frame counting from the next
    /// (the sword arc, the heal), unlike the type-1 attack objects (the
    /// cannon barrel, the sword) whose first frame counts from the spawn.
    effects: Vec<(spr::Player, (i32, i32), u8, bool, bool)>,
    shots: Vec<Shot>,
    glow: spr::Player,
    glow_state: usize,
    charge: u16,
    cross_shape: Option<&'static [(i32, i32)]>,
    intro_fade: u16,
    intro_next: usize,
    gauge: u16,
    gauge_pause: u16,
    /// Set when the chip window closes with picks committed: canon's close
    /// routine blanks the chip-name strip and redraws nothing there (F18, see
    /// the window-close site below). Until it is set the strip follows the
    /// front of the hand, which is the behaviour every other row measures.
    name_suppressed: bool,
    /// Frames from `over` to the RESULT show, counting down from RESULTS_DELAY;
    /// the table owns the state, this owns the composite count (see the const).
    results_delay: u16,
    /// Canon's banner sequencer as its state table (T7): the 0x08 fight
    /// state, the 0x0C/0x10 end counts, the handoff. See `Sequencer`.
    seq: Sequencer,
    /// Frames until the end sequence fires once the fight is decided, counting
    /// down from DISSOLVE_FRAMES; None until the last combatant goes down.
    /// The RESOLVE_OVER stand-in (death before frame 0) starts at Some(0).
    dissolve_in: Option<u8>,
    shown: Option<results::Shown>,
    /// The regular-chip mark the RESULT window hangs at its top-left corner,
    /// held only while that window is up.
    results_mark: Option<agb::display::object::SpriteVram>,
    /// Frames until the buster's barrel joins the pose.
    buster_arm_in: u8,
    /// Frames until the pressed chip button uses a chip.
    chip_use_in: u8,
    /// Whether the HP box's bank is currently on its orange ramp, and what
    /// it should be on the next frame.
    hp_flashing: bool,
    hp_flash_next: bool,
    fade_out: u8,
    clock: u32,
    moves: u8,
    /// Countdown to the next automatic chip use, when present, from a
    /// fixture's own FLAG_AUTO_FIRE.
    auto_ticks: u16,
    /// AUDIT pairs 6/14/17: the fixture this battle was built from, if any --
    /// kept so `update`/`draw` can consult its flags too (`skip_intro`,
    /// `open_window_allowed` below), not just `Battle::new`.
    fixture: Option<Fixture>,
}

/// The oracle snapshot's own 40-byte export block (see the layout table on
/// `oracle_snapshot`): this project's own protocol, so the length is chosen,
/// not read.
const ORACLE_SNAPSHOT_LEN: usize = 40; // provenance: chosen -- this project's own oracle protocol (see oracle_snapshot's table)
/// The state-trace export block's own length (see `trace_snapshot`'s
/// table): this project's own protocol, so the length is chosen, not read.
const TRACE_SNAPSHOT_LEN: usize = 64; // provenance: chosen -- this project's own trace protocol (see trace_snapshot's table)
/// The state-trace block's version word (T1): bumped when the layout above
/// changes, so tools/trace.py can refuse a stale ROM's block loudly.
const TRACE_VERSION: u16 = 3; // provenance: chosen -- this project's own trace protocol version (v3: offset-42 exports the sequencer word's low half, T7; was the 0..3 banner-phase mapping)
/// A fixture field left at its default: 0xFFFF means "no seed"
/// (art_entry), "default" (gauge_tick), "unset" (banner_at,
/// result_elapsed) throughout this project's fixture contract.
const FIXTURE_UNSET: u16 = 0xFFFF; // provenance: chosen -- this project's own fixture "default" (see FIXTURE.md and the gauge_tick/art_entry docs)
/// The fixture hand holds five chips, and a deck_codes entry of 0xff
/// means "no override, use the chip's own codes[0]" (see Battle::new).
const HAND_SIZE: usize = 5; // provenance: chosen -- this project's own five-slot fixture hand (see Battle::new)
const DECK_CODE_FOLLOWS_CHIP: u8 = 0xff; // provenance: chosen -- this project's own deck_codes "no override" (see Battle::new)
/// Bits in a Q16 fixed-point position: the speeds this module keeps
/// (BOMB_VX and friends) are 16.16, so shifting by this converts.
const Q16_SHIFT: u32 = 16; // provenance: derived -- the Q16 fixed-point speeds this module keeps (BOMB_VX and friends)
/// The afterimage trail is a ring of four frames so the copy can lag three
/// behind the navi; both copies blink two frames shown and two hidden.
const STEP_TRAIL_LEN: usize = 4; // provenance: derived -- step_trail's own four-frame ring (see its doc)
const STEP_TRAIL_NEXT: usize = 1; // provenance: derived -- one slot round the four-frame ring is three frames back (see below)
const STEP_RING_PERIOD: u8 = 4; // provenance: derived -- step_trail's own four-frame ring (see its doc)
const STEP_BLINK_SHOWN: u8 = 2; // provenance: peeked -- the copies blink two on and two off (see STEP_GHOST2_FIRST)
const STEP_GHOST_FIRST: u8 = 2; // provenance: peeked -- the first drawn age in STEP_GHOST_LAST's measured drawn frames
/// The no-fixture lineup: an empty hand, MegaMan at column 2, row 2, and
/// one Mettaur at (5, 3) (see Battle::new).
const DEMO_COL: i32 = 2; // provenance: chosen -- this build's no-fixture lineup (see Battle::new)
const DEMO_ROW: i32 = 2; // provenance: chosen -- this build's no-fixture lineup (see Battle::new)
const DEMO_ENEMY_COL: i32 = 5; // provenance: chosen -- this build's no-fixture lineup (see Battle::new)
const DEMO_ENEMY_ROW: i32 = 3; // provenance: chosen -- this build's no-fixture lineup (see Battle::new)
/// BambSwrd's blade is the plain sword sprite in palette 2: byte_80B8BD4's
/// row 0x1c (see use_chip's sword match).
const BAMBSWRD_SWORD_PALETTE: usize = 2; // provenance: derived -- byte_80B8BD4 row 0x1c, asm31.s:109348
/// The deletion effect's timer: an enemy's deletion runs 0x5a frames
/// (see Battle::new's effects).
const DELETE_FRAMES: u8 = 90; // provenance: derived -- the enemy's 0x5a-frame deletion timer (see Battle::new's effects)
/// The windup telegraph ticks every 8th winding frame for non-Mettaur styles.
const WINDUP_TELEGRAPH_EVERY: u8 = 8; // provenance: peeked -- measured telegraph cadence
/// The long swords reach two panels ahead (byte_80EBA18's shapes: the panel
/// ahead, the column ahead, two panels ahead -- see the CHIP_ doc above).
const LONG_SWORD_FAR: i32 = 2; // provenance: derived -- byte_80EBA18's shapes (see the CHIP_ doc above)
/// FIELD_SLIDE is kept in half-pixels (see its doc), so halving converts
/// the slide to a screen scroll -- with `div_euclid`, because canon reads its
/// 16.16 camera with an ARITHMETIC shift, i.e. truncating toward -inf. On a
/// scroll that runs negative that is not the same as Rust's `/`: over the ten
/// close frames the pan's progress is floor(3n/2) = 0,1,3,4,6,7,9,10,12,13,15
/// (canon's own top-of-field rows, measured on `windowclose`), where a divide
/// toward zero gives ceil(3n/2) and is a pixel out on every odd step.
const FIELD_SUBPX: u16 = 2; // provenance: derived -- FIELD_SLIDE is kept in half-pixels (see its doc)
/// The results screen fade runs 1-16 and 16 means fully black
/// (results::Shown::update).
const RESULTS_FADE_BLACK: u8 = 16; // provenance: derived -- results::Shown::update: 16 means the screen is fully black
/// The slash arc rides above the front panel's centre; the offset is this
/// build's own, tuned to the panel art.
const SWORD_ARC_UP: i32 = 0x10; // provenance: fitted -- this build's own arc height, tuned to the panel art

impl<'a> Battle<'a> {
    /// AUDIT pairs 6/14/17: whether the intro plays the real 71-frame white
    /// hold + 14-frame ramp (`false`) or the old `demo-*` fixtures' own
    /// legacy 32-frame black ramp (`true`, only ever reachable through a
    /// fixture's own FLAG_SKIP_INTRO now that every `demo-*` feature that
    /// used to drive this at compile time is gone). No fixture: no reason
    /// to skip -- the default build always plays the real intro.
    fn skip_intro(&self) -> bool {
        match self.fixture {
            Some(f) => f.flag(fixture::FLAG_SKIP_INTRO),
            None => false,
        }
    }

    /// Whether the gauge-pause -> chip-window-open sequence is allowed to
    /// run at all. UNSET (via FLAG_OPEN_WINDOW) reproduced the old
    /// `demo-hudmatch` feature's guard, which froze a full gauge and never
    /// opened the window so a long HUD capture never lost the battle screen
    /// to it. No fixture: always allowed.
    fn open_window_allowed(&self) -> bool {
        match self.fixture {
            Some(f) => f.flag(fixture::FLAG_OPEN_WINDOW),
            None => true,
        }
    }

    /// The state oracle's export block (TODO R6): 40 bytes the main loop
    /// writes to EWRAM 0x02000008 every frame (inside the marker array's own
    /// padding -- see main.rs's ORACLE_OFFSET note for why not 0x02000080),
    /// byte-for-byte comparable with canon's own RAM through a `--watch`.
    /// Field map (offsets in the block; canon addresses are the compared
    /// side, watched directly):
    ///
    /// | off | width | field | canon address | source |
    /// |-----|-------|-------|---------------|--------|
    /// |  0  | 4 | "ORCL" magic 0x4f52434c | -- | our own protocol constant (free choice, like BATTLE_MAGIC) |
    /// |  4  | 4 | battle frame counter | -- (canon has no known battle-frame RAM word; alignment is the row's own Align) | `clock`-equivalent count passed in |
    /// |  8  | 4 | primary RNG state | 0x020013f0 `ePrimaryRngSeed` (ewram.s:262) | `ai::Rng::state()` |
    /// | 12  | 2 | MegaMan CurState\|CurAction<<8 | 0x0203a9b8 = eT1BattleObject0+8 (constants/headers/EWRAM.h:54, BattleObject.inc:40-52) | `Actor::oracle_fields` |
    /// | 14  | 1 | MegaMan CurAnim | 0x0203a9c0 (+0x10) | identity, see `oracle_fields` |
    /// | 15  | 1 | MegaMan PanelX | 0x0203a9c2 (+0x12) | `Actor::panel()`, same units as the descriptor's col |
    /// | 16  | 1 | MegaMan PanelY | 0x0203a9c3 (+0x13) | as above |
    /// | 18  | 2 | MegaMan Timer | 0x0203a9d0 (+0x20) | flinch countdown + `post_flinch` shadow |
    /// | 20  | 2 | MegaMan HP | 0x0203a9d4 (+0x24) | `Actor::hp()` |
    /// | 22  | 2 | enemy CurState\|CurAction<<8 | the POPULATED enemy slot -- 0x0203ab60 for the PAUSED-based rows (the ALIVE cheat's own address 0x0203ab84 = +0x24 proves the base), NOT 0x0203aa88, which is an empty slot (HP 0) | `Actor::oracle_fields` + `Ai::oracle_is_wait` |
    /// | 24  | 1 | enemy CurAnim | slot+0x10 | identity |
    /// | 25  | 1 | enemy PanelX | slot+0x12 | `Actor::panel()` |
    /// | 26  | 1 | enemy PanelY | slot+0x13 | as above |
    /// | 28  | 2 | enemy Timer | slot+0x20 | exported 0: canon reads a constant 0x0002 there (measured), nothing dynamic to model -- oracle.py keeps it out of the compared set |
    /// | 30  | 2 | enemy HP | slot+0x24 | `Actor::hp()` (info-only: the PAUSED rows' canon side is poked 0xffff by ALIVE) |
    /// | 32  | 2 | custom gauge | 0x020352a0 = eStruct2035280+0x20 (sub_801DFB8, asm00_2.s:29892-29907) | `self.gauge` (info-only: canon's is full from the old battle, ours ticks from the descriptor) |
    /// | 34  | 6 | zero padding | -- | -- |
    ///
    /// Export-only: nothing in the battle logic reads it back, so it cannot
    /// change behaviour -- the rerun rows prove that. Also nothing may write
    /// over it: 0x02000008..0x02000030 is inside `BATTLE_MARKER`'s own
    /// reservation (bytes 8..48), which nothing else touches -- the first
    /// cut placed it at 0x02000080, which is agb's `SPRITE_LOADER` (nm),
    /// and the two fought every frame.
    pub fn oracle_snapshot(&self, battle_frame: u32) -> [u8; ORACLE_SNAPSHOT_LEN] {
        let mut b = [0u8; ORACLE_SNAPSHOT_LEN];
        b[0..4].copy_from_slice(&crate::ORACLE_MAGIC.to_le_bytes()); // "ORCL", see main.rs's ORACLE_MAGIC (provenance: chosen -- this project's own protocol constant)
        b[4..8].copy_from_slice(&battle_frame.to_le_bytes()); // canon: oracle snapshot layout, see the table above
        b[8..12].copy_from_slice(&self.primary_rng.state().to_le_bytes()); // canon: oracle snapshot layout, see the table above
        let mm = self.megaman.oracle_fields(true, false);
        b[12..14].copy_from_slice(&mm.cur_state_action.to_le_bytes()); // canon: oracle snapshot layout, see the table above
        b[14] = mm.anim; // canon: oracle snapshot layout, see the table above
        b[15] = mm.panel_x; // canon: oracle snapshot layout, see the table above
        b[16] = mm.panel_y; // canon: oracle snapshot layout, see the table above
        b[18..20].copy_from_slice(&mm.timer.to_le_bytes()); // canon: oracle snapshot layout, see the table above
        b[20..22].copy_from_slice(&mm.hp.to_le_bytes()); // canon: oracle snapshot layout, see the table above
        // First enemy. Every oracle row so far has exactly one; the empty
        // slots around it export 0xffff sentinels.
        if let Some(enemy) = self.enemies.first() {
            let ai_wait = self.ais.first().map(|ai| ai.oracle_is_wait()).unwrap_or(false);
            let e = enemy.oracle_fields(false, ai_wait);
            b[22..24].copy_from_slice(&e.cur_state_action.to_le_bytes()); // canon: oracle snapshot layout, see the table above
            b[24] = e.anim; // canon: oracle snapshot layout, see the table above
            b[25] = e.panel_x; // canon: oracle snapshot layout, see the table above
            b[26] = e.panel_y; // canon: oracle snapshot layout, see the table above
            b[28..30].copy_from_slice(&e.timer.to_le_bytes()); // canon: oracle snapshot layout, see the table above
            b[30..32].copy_from_slice(&e.hp.to_le_bytes()); // canon: oracle snapshot layout, see the table above
        } else {
            b[22..24].copy_from_slice(&FIXTURE_UNSET.to_le_bytes()); // canon: oracle snapshot layout, see the table above
            b[30..32].copy_from_slice(&FIXTURE_UNSET.to_le_bytes()); // canon: oracle snapshot layout, see the table above
        }
        b[32..34].copy_from_slice(&self.gauge.to_le_bytes()); // canon: oracle snapshot layout, see the table above
        b
    }

    /// The state-trace export block (T1): 64 bytes at EWRAM 0x02000080
    /// (bytes 128..192 of main.rs's `BATTLE_MARKER`, linker-placed -- `nm`
    /// proves the array owns 0x02000000..0x02000100, so the block can never
    /// overlap agb's `SPRITE_LOADER`/interrupt table the way an absolute
    /// 0x02000080 address did in R6). Versioned (`TRC2`, version 2): the
    /// v1 ORCL block at 0x02000008 is untouched, so oracle.py keeps
    /// reading it byte-identically. Field map (offsets in the block;
    /// canon addresses are the trace's own `--watch` set, tools/trace.py):
    ///
    /// | off | field | canon | source |
    /// |-----|-------|-------|--------|
    /// |  0  | u32 "TRC2" magic | -- | TRACE_MAGIC (own protocol) |
    /// |  4  | u16 version (=2), u16 len (=64) | -- | own protocol |
    /// |  8  | u32 battle frame | -- (canon has no battle-frame word; R6) | same counter as oracle_snapshot |
    /// | 12  | u32 primary RNG | 0x020013f0 ePrimaryRngSeed (ewram.s:262) | primary_rng.state() |
    /// | 16  | u16 MM state\|action<<8 | 0x0203a9b8 (BattleObject+8) | oracle_fields |
    /// | 18  | u8 MM anim, u8 panel_x, u8 panel_y, u8 mercy | +0x10/+0x12/+0x13, mercy [CollisionDataPtr]+0x24 | oracle_fields (+mercy accessor, T1b) |
    /// | 22  | u16 MM timer, u16 MM hp | +0x20/+0x24 | oracle_fields |
    /// | 26  | u16 E1 state\|action<<8, u8 anim, u8 panel_x, u8 panel_y | first populated enemy slot +8... | oracle_fields of enemies.first() |
    /// | 32  | u16 E1 timer (0), u16 E1 hp | slot +0x20/+0x24 | as above (timer unsupported, R6) |
    /// | 36  | u16 E2 state\|action, u16 E3 state\|action | 2nd/3rd slots +8 | 0xFFFF sentinels: one-enemy model, never populated |
    /// | 40  | u16 custom gauge | 0x020352a0 (eStruct2035280+0x20) | self.gauge |
    /// | 42  | u16 sequencer low | 0x0203ca70 dword_203CA70 (ewram.s:3040) | low half of the watched word: the state byte (0x08 fight, 0x0C win count, 0x10 lose; byte 1 reads 0 both sides), judged in tools/trace.py (T7) |
    /// | 44  | u16 HUD element mask | 0x020352c0 (eStruct2035280+0x40) | hud_live ? 0x4497 : 0x0084 (peeked canon encodings of the two states, T1) |
    /// | 46  | u16 backdrop GFX entry, u16 GFX timer | 0x020094c0 eGFXAnimStates (ewram.s:596) | backdrop.trace_state() (0s when backdrop: None) |
    /// | 50  | u32 backdrop x_q, u32 backdrop y_q | 0x02009690 eBGScrollCBCounters (ewram.s:619) | as above (canon holds -8f/-4f there) |
    /// | 58  | u16 field_slide (own camera) | 0x020099b4 Camera Y (eCamera+0x34, Camera.inc:26) | self.field_slide (INFO-only: different mechanisms) |
    /// | 60  | u16 GFX (0), u16 pad | 0x020094c0+4.. | unsupported on our side: 0, never compared |
    ///
    /// Export-only like oracle_snapshot: nothing reads it back, so it
    /// cannot change behaviour (the rerun rows prove that).
    pub fn trace_snapshot(&self, battle_frame: u32) -> [u8; TRACE_SNAPSHOT_LEN] {
        let mut b = [0u8; TRACE_SNAPSHOT_LEN];
        b[0..4].copy_from_slice(&crate::TRACE_MAGIC.to_le_bytes()); // "TRC2", see main.rs's TRACE_MAGIC (provenance: chosen -- this project's own protocol constant)
        b[4..6].copy_from_slice(&TRACE_VERSION.to_le_bytes()); // trace snapshot layout, see the table above
        b[6..8].copy_from_slice(&(TRACE_SNAPSHOT_LEN as u16).to_le_bytes()); // trace snapshot layout, see the table above
        b[8..12].copy_from_slice(&battle_frame.to_le_bytes()); // trace snapshot layout, see the table above
        b[12..16].copy_from_slice(&self.primary_rng.state().to_le_bytes()); // trace snapshot layout, see the table above
        let mm = self.megaman.oracle_fields(true, false);
        b[16..18].copy_from_slice(&mm.cur_state_action.to_le_bytes()); // trace snapshot layout, see the table above
        b[18] = mm.anim; // trace snapshot layout, see the table above
        b[19] = mm.panel_x; // trace snapshot layout, see the table above
        b[20] = mm.panel_y; // trace snapshot layout, see the table above
        b[21] = self.megaman.mercy(); // trace snapshot layout, see the table above (accessor, not OracleFields: keeps the oracle path's struct identical to main, T1b)
        b[22..24].copy_from_slice(&mm.timer.to_le_bytes()); // trace snapshot layout, see the table above
        b[24..26].copy_from_slice(&mm.hp.to_le_bytes()); // trace snapshot layout, see the table above
        if let Some(enemy) = self.enemies.first() {
            let ai_wait = self.ais.first().map(|ai| ai.oracle_is_wait()).unwrap_or(false);
            let e = enemy.oracle_fields(false, ai_wait);
            b[26..28].copy_from_slice(&e.cur_state_action.to_le_bytes()); // trace snapshot layout, see the table above
            b[28] = e.anim; // trace snapshot layout, see the table above
            b[29] = e.panel_x; // trace snapshot layout, see the table above
            b[30] = e.panel_y; // trace snapshot layout, see the table above
            b[32..34].copy_from_slice(&e.timer.to_le_bytes()); // trace snapshot layout, see the table above (always 0: unsupported, R6)
            b[34..36].copy_from_slice(&e.hp.to_le_bytes()); // trace snapshot layout, see the table above
        } else {
            b[26..28].copy_from_slice(&FIXTURE_UNSET.to_le_bytes()); // trace snapshot layout, see the table above
            b[34..36].copy_from_slice(&FIXTURE_UNSET.to_le_bytes()); // trace snapshot layout, see the table above
        }
        // No second/third enemy in this model: sentinels, never compared
        // against canon's live slots (same rule as oracle.py's has_enemy).
        b[36..38].copy_from_slice(&FIXTURE_UNSET.to_le_bytes()); // trace snapshot layout, see the table above
        b[38..40].copy_from_slice(&FIXTURE_UNSET.to_le_bytes()); // trace snapshot layout, see the table above
        b[40..42].copy_from_slice(&self.gauge.to_le_bytes()); // trace snapshot layout, see the table above
        b[42..44].copy_from_slice(&self.seq.word_lo().to_le_bytes()); // trace snapshot layout, see the table above
        let hud_mask: u16 = if self.hud_live { 0x4497 } else { 0x0084 }; // provenance: peeked -- canon's own element mask at 0x020352C0: 0x4497 live battle, 0x0084 past teardown (--watch, F27b/popup note, T1)
        b[44..46].copy_from_slice(&hud_mask.to_le_bytes()); // trace snapshot layout, see the table above
        let (bd_entry, bd_timer, bd_xq, bd_yq) = match &self.backdrop {
            Some(bd) => bd.trace_state(),
            None => (0, 0, 0, 0),
        };
        b[46..48].copy_from_slice(&bd_entry.to_le_bytes()); // trace snapshot layout, see the table above
        b[48..50].copy_from_slice(&bd_timer.to_le_bytes()); // trace snapshot layout, see the table above
        b[50..54].copy_from_slice(&bd_xq.to_le_bytes()); // trace snapshot layout, see the table above
        b[54..58].copy_from_slice(&bd_yq.to_le_bytes()); // trace snapshot layout, see the table above
        b[58..60].copy_from_slice(&self.field_slide.to_le_bytes()); // trace snapshot layout, see the table above
        // +60 GFX word: unsupported on our side (no GFX-anim model) -- 0.
        // +62 pad.
        b
    }

    pub fn new(
        field: &'a Field,
        results: &'a Results,
        hud: &'a Hud,
        custom_assets: &'a CustomAssets,
        chips: &'a Chips,
        rng: &mut Rng,
        fixture: Option<Fixture>,
    ) -> Self {
        // A stand-in folder: the asset's chips over and over, each with its
        // first code, in place of the PET navi's thirty (sub_800A3E4).
        let mut folder = [0u16; FOLDER_SIZE];
        for (i, entry) in folder.iter_mut().enumerate() {
            let chip = chips.get(i % chips.len());
            *entry = Deck::entry(chip.id, chip.codes[0]);
        }
        let mut deck = Deck::new(folder, rng);
        // AUDIT pairs 6/14/17: the chip window fixture offers exactly what
        // the capture's window does, read off the real ROM by matching each
        // slot's four icon tiles against every chip's icon in byte_8725894:
        // Vulcan1 D, AirShot *, Sword S, MiniBomb B and Cannon A, with the
        // Cannon already picked (its icon is the one in the pick stack).
        // A fixture's own `deck_count`/`deck` (FIXTURE.md +34/+35) drive this
        // instead of the hardcoded stack when one is present; `deck_codes`
        // (this module's own reserved-region addition -- see its doc) covers
        // the two slots whose captured code is not the chip's own `codes[0]`
        // default that FIXTURE.md's field alone would give.
        match fixture {
            Some(f) if f.deck_count > 0 => {
                let mut entries = [crate::deck::EMPTY; HAND_SIZE];
                for i in 0..f.deck_count as usize {
                    let id = f.deck[i] as u16;
                    let code = if f.deck_codes[i] != DECK_CODE_FOLLOWS_CHIP {
                        f.deck_codes[i]
                    } else {
                        chips.by_id(id).map(|c| c.codes[0]).unwrap_or(0)
                    };
                    entries[i] = Deck::entry(id, code);
                }
                deck = Deck::stacked(entries);
            }
            Some(_) => {}
            None => {}
        }
        let deck = deck;
        let panels = Panels::new(field::PANEL_NORMAL);
        // AUDIT pairs 6/14/17: FLAG_BLANK_HUD and FLAG_BLANK_BACKDROP,
        // reduced to what the old demo-sterile feature used to mean when
        // there is no fixture, so every site below that used to check that
        // cfg directly keeps reading exactly what it read before.
        // FLAG_BLANK_BACKDROP is broader than its name: it reproduces
        // demo-sterile's WHOLE non-HUD arena (backdrop module, field bg
        // layer and the hand-chip icon object), not just the backdrop --
        // see fixture.rs's own doc on the flag.
        let blank_hud = fixture
            .map(|f| f.flag(fixture::FLAG_BLANK_HUD))
            .unwrap_or(false);
        let blank_backdrop = fixture
            .map(|f| f.flag(fixture::FLAG_BLANK_BACKDROP))
            .unwrap_or(false);
        // The sterile arena draws a plain background so the real ROM's field can
        // be stripped via the harness's --disable-bg (BG layers) and the two
        // captures diff cleanly whole-frame: MegaMan + attack on black on both.
        let bg = if blank_backdrop {
            RegularBackground::new(
                Priority::P3,
                RegularBackgroundSize::Background32x32,
                TileFormat::FourBpp,
            )
        } else {
            field.background(&panels)
        };
        // AUDIT wave 3d "bg3-merge": see `filler_bg`'s own doc.
        let filler_bg = RegularBackground::new(
            Priority::P0,
            RegularBackgroundSize::Background32x32,
            TileFormat::FourBpp,
        );

        let charge = 0u16;
        let glow = spr::Player::new(spr::Assets::new(CHARGE), 1);
        let glow_state = 0usize;
        let player = actor::Profile {
            // Both parity fixtures come from save states where the navi has
            // taken damage, and both capture the HP box, so they carry the
            // capture's own 60 rather than a fresh navi's.
            hp: match fixture {
                Some(f) => f.megaman_hp,
                None => PLAYER_HP,
            },
            mercy: actor::PLAYER_MERCY_FRAMES,
            death_frames: actor::PLAYER_DEATH_FRAMES,
        };
        let enemy = |hp| actor::Profile {
            hp,
            mercy: 0,
            death_frames: actor::ENEMY_DEATH_FRAMES,
        };
        // A fixture takes the hand and column straight from the descriptor;
        // its own enemies are built separately below (see the `enemies`
        // match below). No fixture: an empty hand, MegaMan at column 2 (the
        // default release build's own lineup is built there too).
        let (demo_hand, demo_col): (alloc::vec::Vec<u16>, i32) = match fixture {
            Some(f) => (
                f.hand[..f.hand_count as usize]
                    .iter()
                    .map(|&id| id as u16)
                    .collect(),
                f.megaman_col as i32,
            ),
            None => (alloc::vec::Vec::new(), DEMO_COL),
        };
        let demo_row = fixture.map(|f| f.megaman_row as i32).unwrap_or(DEMO_ROW);
        let megaman = Actor::new(spr::Assets::new(MEGAMAN), demo_col, demo_row, false, player);
        // Whether a virus dies with the navi's 0x5a-frame blink was not checked.
        // A debug build fights just the Mettaur, to exercise the hand, chips
        // and deletion without the bosses; the release build keeps the game's
        // lineup.
        let (mut enemies, ais): (Vec<Actor>, Vec<ai::Ai>) = if let Some(f) = fixture {
            // Kinds are per slot (FIXTURE.md +5, two bits each); the layout
            // is still the diagonal -- (enemy_col, enemy_row), (+1, +1),
            // (+2, +1)... -- which is the only multi-enemy shape any
            // existing fixture needs, and exactly record 6's own shape
            // (T9b's slot probe: Mettaur (5,2) then Gunner (6,3)).
            let mut es = alloc::vec::Vec::new();
            let mut ai_list = alloc::vec::Vec::new();
            for i in 0..f.enemies as i32 {
                // Art, style and the kind's own default HP come from the
                // kind's first-version record (MettaurEnemyStruct2_8109BD8 /
                // GunnerEnemyStruct2_8112B9C).
                let (art, style, default_hp) = match f.kind_of(i as usize) {
                    fixture::KIND_GUNNER => (GUNNER, ai::Style::Gunner, gunner::HP),
                    _ => (METTAUR, ai::Style::Mettaur, METTAUR_HP),
                };
                let hp = if f.enemy_hp == 0 { default_hp } else { f.enemy_hp };
                es.push(Actor::new(
                    spr::Assets::new(art),
                    f.enemy_col as i32 + i,
                    f.enemy_row as i32 + i,
                    true,
                    enemy(hp),
                ));
                ai_list.push(ai::Ai::new(style));
            }
            (es, ai_list)
        } else {
            // ONE METTAUR, in every other build. The four-strong line-up that
            // used to stand here in release builds -- ProtoMan, Colonel, a
            // Mettaur and a Gunner -- kills the navi in about fifteen seconds,
            // which is before the custom gauge has filled even once, so nobody
            // playing the rollup ever reached the chip window.
            (
                alloc::vec![Actor::new(
                    spr::Assets::new(METTAUR),
                    DEMO_ENEMY_COL,
                    DEMO_ENEMY_ROW,
                    true,
                    enemy(METTAUR_HP)
                )],
                alloc::vec![ai::Ai::new(ai::Style::Mettaur)],
            )
        };
        let gunner_ctl = gunner::Gunner::new();
        let impacts: Vec<gunner::Impact> = Vec::new();
        // The deletion effect, sprite_839CCDC animation 0, spawned at the body
        // when HP reaches zero (spawn_t1_0x0_EffectObject via byte_80E0398 row
        // 3; asm31.s:85229, 85033). An enemy's is given a 0x5a-frame timer.
        let effects: Vec<(spr::Player, (i32, i32), u8, bool, bool)> = Vec::new();
        // AUDIT pairs 6/14/17: a fixture's own FLAG_SKIP_INTRO drives this;
        // no fixture means no reason to skip (see `skip_intro`'s own doc).
        // F34b: a fixture starting on the results screen (start_state == 1,
        // canon: FIXTURE.md +40) has no fade left -- canon's RESULT_ARRIVAL
        // capture is 8048 battle frames in (eBGScrollCBCounters fall 8/4 a
        // frame from 0/0 at battle init), long past the battle-opening white
        // hold + ramp (INTRO_HOLD + INTRO_RAMP) this fade reproduces, so the
        // fixture starts settled.
/// The skip-intro fade starts here (the legacy black-ramp branch's own
/// value, see INTRO_RAMP's doc) and the white hold lasts 71 frames
/// (full white through the 71st frame, see INTRO_RAMP's doc).
const INTRO_SKIP_FADE: u16 = 0x10 * 2; // provenance: derived -- the legacy black-ramp branch's own value (see INTRO_RAMP's doc)
const INTRO_HOLD: u16 = 71; // provenance: peeked -- full white through the 71st frame (see INTRO_RAMP's doc)
        let intro_fade: u16 = if fixture.map(|f| f.start_state == 1).unwrap_or(false) {
            0 // canon: no fade left 8048 battle frames in (see the F34b note above)
        } else if fixture
            .map(|f| f.flag(fixture::FLAG_SKIP_INTRO))
            .unwrap_or(false)
        {
            INTRO_SKIP_FADE
        } else {
            INTRO_HOLD + INTRO_RAMP
        };
        let intro_next = 0usize;
        for enemy in enemies.iter_mut() {
            enemy.hide();
        }
        let cross_shape: Option<&[(i32, i32)]> = None;
        let shots: Vec<Shot> = Vec::new();
        // A BATTLE OPENS WITH THE CHIP WINDOW. Measured on the real ROM from a
        // save state at a battle's first frame: the field fades in, the
        // viruses materialise, and the window comes up on its own at frame
        // 165 with nothing pressed. This build used to start the gauge empty
        // in a release build, which is 0x4000 / 0xd = 1260 frames -- twenty-one
        // seconds of an unarmed navi before the first chip. The gauge starts
        // FULL, and the pause that follows it opens the window.
        let gauge = match fixture {
            Some(f) => if f.gauge != 0 { GAUGE_FULL } else { 0 },
            None => GAUGE_FULL,
        };
        let gauge_pause = 0u16;
        let results_delay = RESULTS_DELAY;
        let shown: Option<results::Shown> = None;
        let results_mark: Option<agb::display::object::SpriteVram> = None;
        let buster_arm_in = 0u8;
        let chip_use_in = 0u8;
        let hp_flashing = false;
        let hp_flash_next = false;
        let fade_out = 0u8;
        let clock = 0u32;
        let moves = 0u8;
        // AUDIT pairs 6/14/17: a fixture's own FLAG_AUTO_FIRE seeds this
        // with its `fire_frame` -- see the per-frame firing block in
        // `update` below. No fixture: no auto-fire.
        let auto_ticks: u16 = if let Some(f) = fixture {
            if f.flag(fixture::FLAG_AUTO_FIRE) { f.fire_frame } else { 0 }
        } else {
            0u16
        };
        // `demo_hand` loads straight into the hand, so A fires the first one
        // at once without the chip-select window (a fixture's own `hand`
        // does the same; the default build's is always empty).
        let hand: alloc::vec::Vec<Chip> = demo_hand
            .into_iter()
            .filter_map(|id| chips.by_id(id))
            .collect();
        let mut hud_tiles = if blank_hud {
            None
        } else {
            Some(crate::hudtiles::HudTiles::new(crate::HUD_TILES, crate::TEXT_FONT))
        };
        // AUDIT wave 3d "bg3-merge": the shared BG3 (see `hud_bg`'s own doc).
        // Paired 1:1 with `hud_tiles` above -- `open_custom_window` creates
        // it lazily instead when `hud_tiles` is blanked but the chip window
        // still opens (the isolated `window`/`card` checks).
        let hud_bg = if blank_hud {
            None
        } else {
            Some(RegularBackground::new(
                Priority::P1,
                RegularBackgroundSize::Background32x32,
                TileFormat::FourBpp,
            ))
        };
        // AUDIT pairs 6/14/17: a fixture's own `gauge_tick` (FIXTURE.md +28)
        // seeds the bar's flow phase directly -- see `HudTiles::seed_gauge`'s
        // own doc. 0xFFFF ("default" throughout this contract) leaves the
        // fresh `new()` value above.
        if let (Some(hud), Some(f)) = (hud_tiles.as_mut(), fixture) {
            if f.gauge_tick != FIXTURE_UNSET {
                hud.seed_gauge(f.gauge_tick as u32);
            }
        }

        Self {
            field,
            results,
            hud,
            custom_assets,
            custom: None,
            scripts: script::Scripts::new(),
            chips,
            deck,
            hand,
            hand_at: 0,
            chip_in_use: None,
            sword_in: None,
            held_raise: None,
            step_home: None,
            step_ghost: None,
            step_ghost2: None,
            step_ghost2_key: None,
            step_ghost2_sword: None,
            step_sword_art: None,
            step_trail: [((0, 0), (0, 0)); STEP_TRAIL_LEN],
            step_trail_sword: [None; STEP_TRAIL_LEN],
            step_dest: (0, 0),
            presentation: None,
            popup: None,
            banner: None,
            banner_assets: banner::Assets::new(crate::BANNER),
            banner_done: false,
            opened: false,
            window_closed: false,
            close_redraw_pending: false,
            banner_at: 0,
            blip_in: 0,
            blip_off: 0,
            hit_in: 0,
            bubble: None,
            vulcan_gun: None,
            vulcan_fireball: None,
            areagrab_orbs: Vec::new(),
            bombs: Vec::new(),
            panels,
            filler_bg,
            bg,
            backdrop: if blank_backdrop {
                None
            } else {
                Some(crate::backdrop::Backdrop::new(crate::BACKDROP))
            },
            field_slide: 0,
            poison_pending: 0,
            poison_palette: 0,
            ring_pending: 0,
            ring_target: (0, 0),
            // Objects, not tiles, so it shows in the sterile arena too --
            // which is where it was measured.
            emotion: crate::emotion::Emotion::new(crate::EMOTION),
            // Canon enables the emotion window with the rest of the battle
            // HUD and never re-enables it inside a battle, so this starts
            // set and is only ever cleared (in `update`, on the teardown).
            // A battle with an enemy always has a live HUD in canon; only a
            // zero-enemy arena -- which canon never fields -- has to be told,
            // hence FLAG_HUD_LIVE (see its own doc in fixture.rs).
            hud_live: !enemies.is_empty()
                || fixture.map(|f| f.flag(fixture::FLAG_HUD_LIVE)).unwrap_or(false),
            hand_icon_palette: (!blank_backdrop).then(hand_icon_palette),
            hud_tiles,
            hud_bg,
            hp_shown: core::iter::once(Counter::new(megaman.hp()))
                .chain(enemies.iter().map(|e| Counter::new(e.hp())))
                .collect(),
            megaman,
            enemies,
            ais,
            // AUDIT wave 3d ticket: FIXTURE.md's `rng` (+58), 0 => this
            // project's own default seed (see `ai::DEFAULT_SEED`'s doc).
            primary_rng: ai::Rng::new(match fixture {
                Some(f) if f.rng != 0 => f.rng,
                _ => ai::DEFAULT_SEED,
            }),
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
            name_suppressed: false,
            results_delay,
            dissolve_in: None,
            seq: Sequencer::battle(),
            shown,
            results_mark,
            buster_arm_in,
            chip_use_in,
            hp_flashing,
            hp_flash_next,
            fade_out,
            clock,
            moves,
            auto_ticks,
            fixture,
        }
    }

    /// Ask panel `(c, r)` to show the shockwave's highlight this frame, unless
    /// somebody is standing on it: the capture's wave lights the panel ahead of
    /// the navi and the one behind him and leaves his own dark on the frames it
    /// is passing through him.
    fn light_wave_panel(&mut self, c: i32, r: i32) {
        let taken = self.megaman.is_present() && self.megaman.panel() == (c, r)
            || self
                .enemies
                .iter()
                .any(|e| e.is_present() && e.panel() == (c, r));
        if (1..=field::COLS).contains(&c) && (1..=field::ROWS).contains(&r) && !taken {
            self.panels.highlight(c, r, WAVE_HIGHLIGHT);
        }
    }

    /// The buster's BARREL, a 16x8 object riding the navi's arm for the whole
    /// pose. Its own OAM offsets put it at (+13,-30) from the navi's origin,
    /// which is the panel centre, so it is spawned there and the sprite
    /// places itself. A held object, so no ground shadow.
    fn spawn_buster_arm(&mut self) {
        // NOT pre-ticked: it is spawned at the top of the frame, before the
        // effects tick, so it takes this frame's tick with the rest.
        let arm = spr::Player::new(spr::Assets::new(BUSTER_ARM), 0);
        let (mc, mr) = self.megaman.panel();
        // Its ONE part is the barrel itself, not a ground shadow, so the
        // no-shadow flag must be off or nothing is drawn at all.
        // As long as the pose, and not one frame more: see the comment on
        // BUSTER_ARM_DELAY's neighbours above for canon's two pointers and the
        // object_exitAttackState that clears them.
        let pose = self.megaman.buster_spec().frames;
        self.effects
            .push((arm, field::panel_centre(mc, mr), pose, false, false));
    }

    /// Put the results window up, taking its palette banks back first. The
    /// window draws in banks 9-11 and the CUSTOM gauge holds bank 9 for the
    /// whole fight, so without this the window comes up in the gauge's greens
    /// and yellows instead of its own grey and blue.
    ///
    /// `elapsed` is FIXTURE.md's `result_elapsed` (+56, AUDIT wave 3c item
    /// 2): frames of the slide-in to fast-forward through with no input
    /// before the window is ever drawn, 0 = none (today's only behaviour
    /// for every caller but the fixture path -- see `results::Shown::
    /// fast_forward`'s own doc). Both non-fixture callers below pass 0, so
    /// they are byte-for-byte unaffected by this parameter's addition.
    fn show_results(
        &mut self,
        kind: usize,
        time: u32,
        level: u8,
        zenny: u16,
        elapsed: u32,
        gfx: &Graphics,
    ) {
        for (i, p) in self.results.palettes().iter().enumerate() {
            gfx.set_background_palette(custom::BANK + i as u8, p);
        }
        self.results_mark = Some(self.custom_assets.mark_sprite());
        let mut shown = self.results.show(kind, time, level, 0, zenny);
        shown.fast_forward(elapsed);
        if shown.blit_needed {
            self.results.blit_slide(&mut shown);
        }
        self.shown = Some(shown);
    }

    /// Bring the backdrop's art to the real ROM's state at a battle's first
    /// frame (see `backdrop::Backdrop::prime`). Called once, right after
    /// construction: `Battle::new` has no `Graphics` to draw with, so this
    /// cannot happen there.
    pub fn prime_backdrop(&mut self, gfx: &Graphics) {
        if let Some(backdrop) = self.backdrop.as_mut() {
            // A fixture compared against /tmp/pausedwithcannon.state starts
            // where that state is, not at zero -- see Backdrop::seed. The
            // fixtures that compare against a DIFFERENT state (the battle's
            // own first frame, or a window fixture that covers the backdrop
            // entirely) leave art_entry at its default and get no seed.
            //
            // AUDIT pairs 6/14/17: a fixture carries its own seed in
            // art_entry/art_timer/scroll_xq/scroll_yq, 0xFFFF (in
            // art_entry) meaning "no seed, use Backdrop::new's own fresh-
            // battle defaults". No fixture: no seed either -- the default
            // release build always starts fresh.
            match self.fixture {
                Some(f) if f.art_entry != FIXTURE_UNSET => {
                    backdrop.seed(
                        f.art_entry as usize,
                        f.art_timer,
                        f.scroll_xq as u32,
                        f.scroll_yq as u32,
                    );
                }
                Some(_) => {}
                None => {}
            }
            backdrop.prime(gfx);
        }
    }

    /// Run one frame of battle logic. Returns true once the results window
    /// has been dismissed and its fade-out has completed, so the caller can
    /// start the next battle.
    pub fn update(
        &mut self,
        input: &ButtonController,
        gfx: &Graphics,
        mixer: &mut agb::sound::mixer::Mixer,
    ) -> bool {
        // AUDIT wave 3d ticket: the real ROM's primary RNG (`ePrimaryRngSeed`)
        // advances by exactly one step every rendered battle frame,
        // independent of any enemy's own decisions -- measured (see
        // `ai::Rng`'s own doc), not yet traced to a specific caller. Ticked
        // unconditionally here, before anything else this frame, so an
        // RNG-gated enemy (`MettaurEntry`'s wander arm, currently
        // unreachable -- see ai.rs's own module doc) draws from the same
        // point in the sequence the real ROM would have reached by the time
        // its own equivalent runs.
        self.primary_rng.next();
        // T8 (docs/coverage/plan-interpreters.md §3): canon reaches the two
        // script VMs once per frame before the battle object walk --
        // `RunContinuousMapScript` from the map main loop
        // (reference/bn6f/asm/asm03_1_0.s:1920) and the chatbox text interpreter
        // from its own update (reference/bn6f/asm/chatbox.s:331). Both live in
        // script.rs now; this fixture ROM has no map section and no harness row
        // raises a chatbox, so `eMapScriptState.ContinuousMapScriptPtr` is 0 and
        // `oChatbox_Visible` is 0 and neither loop reads a byte -- which is why
        // the full harness table is the regression test for this hook.
        self.scripts.step_frame(input);
        if self.buster_arm_in > 0 {
            self.buster_arm_in -= 1;
            if self.buster_arm_in == 0 {
                self.spawn_buster_arm();
            }
        }
        if self.backdrop.is_some() {
            self.backdrop.as_mut().unwrap().update(gfx);
        }
        // AUDIT pair 6: the HUD is the real HUD whenever it is not blanked,
        // regardless of the backdrop -- gated on `self.hud_tiles.is_some()`
        // rather than folded into the `backdrop.is_some()` block above (which
        // is what this was before this ticket). Every existing fixture and
        // demo build has always carried FLAG_BLANK_HUD == FLAG_BLANK_BACKDROP
        // (both set or both clear -- see fixture.rs's own descriptor table),
        // so this split changes nothing for any of them; it only matters for
        // a fixture that blanks the backdrop but NOT the HUD (a sterile arena
        // with the real HUD up), which the old single gate never let update
        // at all -- `hud_tiles.as_mut().unwrap()` would have been reached
        // with backdrop still None only by a bug, never by this combination,
        // because nothing built that combination before.
        // NO GAUGE BEFORE THE FIRST CHIP WINDOW HAS CLOSED. A battle opens
        // with that window (7aw), so there is nothing for a gauge to do
        // until it has been through once -- and the real ROM draws none:
        // rendering its HUD strip from a battle's first frame shows the HP
        // box and nothing else at frames 75, 100, 125, 150, 165, 175 and
        // 185, with the window itself up by 200.
        // Only in the builds that actually start at a battle's beginning.
        // Every other demo is calibrated against a capture taken mid-battle,
        // where the gauge is up and belongs there.
        // Computed here, ahead of the `hud_tiles.as_mut()` borrow below,
        // because `skip_intro()` takes `&self` and the borrow checker cannot
        // see that it only reads `self.fixture` -- calling it while `hud`
        // still holds `self.hud_tiles` mutably does not compile.
        // F18c deferred close: the tenth slide-out call flips the window
        // Done, but canon holds scroll 0x78 through that frame (slide 90)
        // and only reads 0 on blank frame 91, redrawing the gauge on 92
        // (RenderInfo+0x18 watch + VRAM dumps on this row's own capture).
        // So the Done frame leaves scroll at 0x78 and arms this; the blank
        // frame performs the visible reset AFTER the HUD has drawn in menu
        // mode, and the redraw lands the frame after that, as on canon.
        let close_blank = self.close_redraw_pending;
        if close_blank {
            // Canon's own BG3HOFS reads 0 here (RenderInfo+0x18 watch,
            // 0x78 at slide 90 -> 0 at blank 91): the slide's last value
            // stays up for the Done frame, not this one. HudTiles' own
            // tile placement assumes an unscrolled background.
            if let Some(bg) = self.hud_bg.as_mut() {
                bg.set_scroll_pos((0, 0));
            }
            for (i, p) in self.results.palettes().iter().enumerate() {
                gfx.set_background_palette(custom::BANK + i as u8, p);
            }
            // The window borrows banks 9-15, and the gauge's is 9, so it
            // goes back last. On the real ROM the window covers this whole
            // layer while it is up, which is why they can share a bank.
            if let Some(hud) = self.hud_tiles.as_ref() {
                gfx.set_background_palette(
                    crate::hudtiles::GAUGE_BANK,
                    &hud.gauge_palette(),
                );
            }
            self.gauge = 0;
            self.close_redraw_pending = false;
        }
        let before_first_window = !self.window_closed && !self.skip_intro();
        // F33b: the CUSTOM gauge is battle-HUD element 4 (mask dword_20352C0,
        // updater sub_801C470 asm00_2.s:26292, draw sub_801C4E4 :26351) and
        // bit 4 is one of the five (0,1,4,10,14) sub_80081A4 ->
        // sub_801BED6(0xE4C53) clears at the RESULT countdown (asm00_1.s:
        // 10617-10621, F27b) -- the same teardown `hud_live` already tracks
        // for element 14. Measured on the zero-enemy rows' canon captures
        // (--watch 0x020352C0:8): the mask reads 0x0084 on every compared
        // frame, so canon draws no gauge there while we drew its frame and
        // label for 1596 px a frame.
        let gauge_up = self.hud_live
            && self.shown.is_none()
            && self.fade_out == 0
            && !before_first_window;
        if let Some(hud) = self.hud_tiles.as_mut() {
            // `hud_bg` is Some whenever `hud_tiles` is (AUDIT wave 3d
            // "bg3-merge": paired 1:1 in `Battle::new`; `open_custom_window`
            // only ever creates `hud_bg` when it was None to begin with,
            // never the reverse), so this is never a fresh-blanked HUD.
            let bg = self.hud_bg.as_mut().unwrap();
            hud.set_menu(bg, self.custom.is_some());
            // F18d: draw the gauge body on the blank frame itself, one
            // logic frame earlier than canon's redraw (canon update 92 -
            // sub_8026BF4's close path in reference/bn6f asm03_0.s:1037
            // clears the window columns per slide call via
            // CopyBackgroundTiles, then a single update writes HP-home +
            // label + 16x0x9222 body + 50B palette, VRAM-dump-verified on
            // this row's own captures: post-91->post-92 = 48 map entries
            // at 0x0600F800 rows 0-1 cols 0-23 + 50 palette bytes, 0 spread).
            // Canon's direct VRAM writes are picture-visible same-frame,
            // but our agb-buffered tile writes land one picture later
            // (this row: update-272's draw showed in picture 273 while
            // update-271's reset showed in 271 -- tile writes lag, palette
            // and register writes do not, same rule as the HP box's own
            // "tile writes land on the next [frame]" comment below).
            // So the blank frame draws the empty body (gauge was just
            // zeroed above; the menu flip already cleared its columns):
            // its tiles appear in the next picture, exactly canon 92's
            // slot, while this picture still shows the Done frame's blank
            // gauge. F18c's skip double-compensated and pushed the body
            // to k=12. The gauge_shown cache makes the redo on the next
            // frame a no-op, so nothing draws twice.
            hud.set_gauge(bg, self.gauge, GAUGE_FULL, gauge_up);
            // The real ROM names the chip that is ABOUT to be used, not the
            // one in flight: measured on a capture where the name stands from
            // the first frame and clears on the frame the chip fires. So it
            // follows the front of the hand.
            // The window covers the name strip while the menu is up, and the
            // real ROM draws no name there then. AUDIT wave 3d "bg3-merge":
            // that strip is now the SAME shared background the window
            // itself draws tiles into. Measured (this ticket,
            // tools/regress.py --only window,card): unconditionally
            // re-blanking it every frame (matching the pre-merge structure
            // byte for byte) measures WORSE than skipping the write while
            // the window is open (32768px vs 8192px over 16 frames) -- the
            // window's own template map is not blank throughout that whole
            // strip, so re-asserting BLANK_TILE there erases real window
            // content the pre-merge code never touched (a separate,
            // lower-priority background of its own back then, so its own
            // blank tiles simply never got seen). Skipping is closer but
            // not yet 0 -- see this ticket's report for where the
            // remaining residue localises.
            if self.custom.is_none() && !self.name_suppressed {
                match self.hand.get(self.hand_at) {
                    // The hand holds the chip itself, so take its name from
                    // that. Indexing the chip table BY ID names the wrong
                    // chip: the table is in the exporter's own order, where
                    // index 1 is HiCannon while chip id 1 is Cannon.
                    Some(chip) => hud.set_name(bg, Some((chip.name(), chip.power))),
                    None => hud.set_name(bg, None),
                }
            }
        }
        if self.backdrop.is_some() {
            // The field slides down out of the window's way and back again:
            // measured on the real ROM at 1.5 px a frame over ten frames to a
            // 15 px offset, held while the menu is up. Left gated on the
            // backdrop (unchanged by this ticket) rather than the HUD: no
            // fixture exercises a chip window with the backdrop blanked and
            // the HUD live within the frame ranges any check covers, so there
            // is nothing to measure this against yet -- flagged in the
            // ticket report rather than guessed at.
            // ...and it pans back WHILE THE WINDOW IS STILL LEAVING, not
            // after it has gone: canon's step lives inside the slide-out
            // itself (see FIELD_SLIDE's doc), one 1.5 px per slide call, so
            // the ten steps and the ten slide frames are the same ten frames.
            // `Custom::is_closing()` is that predicate, asked before
            // `Custom::update` consumes the frame. Waiting for `custom` to
            // become None instead put the whole pan ten frames late (it turns
            // None on the TENTH slide call): windowclose BG3 0 but BG2 266412
            // over k=1..19, canon k=2/4/6/8/10 comparing exactly 0 against our
            // k=12/14/16/18/20 (F29, measured at this row's offset 253).
            let want = if self.custom.as_ref().is_some_and(|w| !w.is_closing()) {
                FIELD_SLIDE
            } else {
                0
            };
            self.field_slide = if self.field_slide < want {
                (self.field_slide + FIELD_SLIDE_STEP).min(want)
            } else {
                self.field_slide.saturating_sub(FIELD_SLIDE_STEP).max(want)
            };
            // NOTE THE PARENTHESES: unary minus binds looser than a method
            // call, so `-x.div_euclid(2)` is `-(x.div_euclid(2))` -- the
            // divide-then-negate that rounds toward zero, i.e. exactly the
            // bug this line exists to fix. Measured with the parentheses
            // missing: BG2 back to 7320-7836 px on k=1,3,5,7,9 (the odd steps
            // only) and 0 on the even ones, our field one pixel high.
            let camera_half_px = -(self.field_slide as i32);
            self.bg
                .set_scroll_pos((0, camera_half_px.div_euclid(FIELD_SUBPX as i32))); // (see FIELD_SUBPX)
        }
        // Once either side is deleted the fight is decided: the game goes to
        // its results, which are not built yet, so here the field just holds.
        // AUDIT pairs 6/14/17: any fixture that fields zero enemies keeps the
        // fight open forever (an empty `enemies` makes `.all()` vacuously
        // true, which would end the fight on frame one) -- a chip-window
        // fixture fields nobody, so the all-enemies-deleted win would fire
        // on its first frame and hold the gauge, which is what opens the
        // window. No fixture: the default release build's own lineup always
        // fields at least one.
        // EXCEPTION (TODO F8, measured): a fixture carrying FLAG_RESOLVE_OVER
        // is an enemy-less arena whose fight is already decided -- the
        // zero-enemy rows' stand-in for the canon side's own deleted-enemy
        // history, which resolves (canon's all-dead advance measured: the
        // banner sequencer enters 0x0C at canon 47 on the field row's own
        // canon capture, and the ENEMY DELETED banner runs canon 49..106).
        // With the bit, the vacuous all-defeated counts, `over` fires on the
        // first battle frame, and the end sequence runs exactly as it would
        // had a real enemy died before frame 0.
        // F32 (2026-09-14): a REAL kill does not end the sequence at the
        // defeat -- `over` used to fire the moment the last enemy read Gone.
        // Canon counts the dissolve first (DISSOLVE_FRAMES, 35, from the
        // death action's first frame) and only then enters 0x0C, so the
        // fight is decided when the last combatant goes DOWN (Dying, HP
        // already 0) and `over` follows 35 frames later. The RESOLVE_OVER
        // stand-in above keeps firing at once: its death is before frame 0,
        // so there is no dissolve left to count.
        let decided = if self.fixture.is_some() {
            let f = self.fixture.unwrap();
            (f.flag(fixture::FLAG_RESOLVE_OVER) || !self.enemies.is_empty())
                && (self.megaman.is_defeated()
                    || self.megaman.is_dying()
                    || self.enemies.iter().all(|e| e.is_defeated() || e.is_dying()))
        } else {
            self.megaman.is_defeated()
                || self.megaman.is_dying()
                || self.enemies.iter().all(|e| e.is_defeated() || e.is_dying())
        };
        if decided && self.dissolve_in.is_none() {
            let instant = self.enemies.is_empty()
                && matches!(self.fixture, Some(f) if f.flag(fixture::FLAG_RESOLVE_OVER));
            // Seed one less than the count, and tick on the latching frame
            // too: this block runs before the take_damage sites below each
            // update, so the latch observes the killing blow a frame late.
            // Together that lands `over` exactly DISSOLVE_FRAMES updates
            // after the blow (OAM-verified: banner OAM first appears 35
            // capture frames after the killing hit reads HP 0, matching
            // canon's death-to-0x0C on both its routes).
            self.dissolve_in = Some(if instant { 0 } else { DISSOLVE_FRAMES - 1 });
        }
        if let Some(n) = self.dissolve_in.as_mut() {
            *n = n.saturating_sub(1);
        }
        // The 0x08 -> end edge of the banner sequencer (sub_80080D2's
        // transition write): the fight is decided when the last combatant
        // goes down and the dissolve runs out -- exactly the old `over`
        // latch, now as the table's own state. Lose when the navi is already
        // down, win otherwise (canon reads the outcome the same way through
        // sub_800A152; the message follows the state).
        if self.dissolve_in == Some(0) && self.seq.state == SEQ_08 {
            self.seq
                .transition(if self.megaman.is_defeated() { SEQ_10 } else { SEQ_0C });
        }
        let over = self.seq.state != SEQ_08;
        // The battle HUD's teardown: canon drops elements 0, 1, 4, 10 and 14
        // together on the frame the end sequence starts, one frame before the
        // banner this same `over` arms below (sub_80081A4's
        // sub_801BED6(0xE4C53), asm00_1.s:10617-10621; measured frame 48
        // against the sequencer's 0x0C at 47). Only the emotion window is
        // modelled here; it is never re-enabled inside a battle.
        if over {
            self.hud_live = false;
        }

        // The gauge only runs while the fight does; a full gauge holds
        // everything, including itself, through the chimes and then the
        // chip window, which takes banks 9-15 while it is up.
        if let Some(window) = self.custom.as_mut() {
            // `hud_bg` exists whenever `custom` does -- opening the window
            // (below) creates it lazily if `hud_tiles` was blanked (AUDIT
            // wave 3d "bg3-merge").
            let bg = self.hud_bg.as_mut().unwrap();
            if window.update(bg, input, gfx) {
                // The picks leave the deck (sub_80293F8) and become the hand.
                self.hand.clear();
                self.hand_at = 0;
                for offer in window.hand() {
                    self.deck.take(offer.deck_index);
                    self.hand.push(offer.chip);
                }
                self.custom = None;
                // Canon's close routine blanks the chip-name strip and leaves
                // it blank: sub_8026BF4 (asm03_0.s:1037, the JumpOffset01
                // 0x04->0x08 slide-out this row's watch names) calls
                // sub_8029D80 (asm03_0.s) = CopyBackgroundTiles of tile 0
                // over the 7x2 name region, and the OK press (custMenuPressOK
                // _8028D3A) committed the picks to the sent-chip data
                // (sub_8029110) rather than to anything the name display
                // follows. Measured (F18): canon shows NOTHING in the strip
                // for the whole 30-frame post-close window while this build
                // redrew the hand-front chip's name there ("Cannon 40", 422
                // px/frame). Suppressed from here on; canon's own re-show
                // trigger (selecting the chip for use mid-battle) is not
                // modelled -- no compared capture reaches it.
                self.name_suppressed = true;
                // F18c: the visible half of closing waits a frame (see the
                // latch above): this frame keeps scroll 0x78 like canon's
                // slide 90, so only arm the blank-frame reset here. The
                // logical half (hand, suppression, banner arming below)
                // still lands on the Done frame.
                self.close_redraw_pending = true;
                // BATTLE START! follows the FIRST chip window, thirty frames
                // after it closes. Measured from a save state at a battle's
                // first frame: window opens 165, closes 259, banner 289.
                // AUDIT pairs 6/14/17: not with a descriptor -- a fixture is
                // by definition testing one scene, not playing the game from
                // a fresh boot, so it never arms this banner regardless of
                // which flags it carries.
                self.window_closed = true;
                if !self.opened && self.fixture.is_none() {
                    self.opened = true;
                    self.banner_at = BATTLE_START_AFTER_WINDOW;
                }
                // F18c: palette restores and the gauge clear ride with the
                // deferred visible reset above, so the blank frame shows
                // neither the window's banks nor a redrawn gauge yet.
                {
                }
            }
        } else if self.gauge_pause > 0 && self.open_window_allowed() {
            // The HUD fixture holds a full gauge to match the capture, which
            // would otherwise open the chip window and never close it -- the
            // demo presses nothing -- leaving no frames of a long capture with
            // the battle screen up.
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
                            .map(|chip| Offer {
                                chip,
                                code: Deck::code(entry),
                                deck_index,
                            })
                    })
                    .collect();
                // AUDIT wave 3d "bg3-merge": the shared HUD/window
                // background, lazily created here for the isolated
                // `window`/`card` checks (FLAG_BLANK_HUD with
                // FLAG_OPEN_WINDOW -- `hud_tiles` is None there, so
                // `Battle::new` never made one).
                let bg = self.hud_bg.get_or_insert_with(|| {
                    RegularBackground::new(
                        Priority::P1,
                        RegularBackgroundSize::Background32x32,
                        TileFormat::FourBpp,
                    )
                });
                self.custom = Some(self.custom_assets.open(bg, &offered, gfx, self.fixture));
                // F37b: the custom screen pauses the fight (canon's
                // PauseBattle/BattlePaused, GameState+0x0A -- F37 watched it
                // read 1 while the window is up), so whatever the enemy held
                // when the window opened is what it holds throughout. A
                // fixture compared against a mid-battle state carries that
                // held pose in the descriptor (peeked enemy_state/enemy_action,
                // see fixture.rs) and takes it here, on the opening frame --
                // not in Battle::new, where it would tick down through the
                // intro and chimes and even fire its strike before the window
                // exists. 0x0b is the attack executor (SWING's own pose,
                // anim 1, both rows' canon_ref); anything else is left alone.
                if let Some(f) = self.fixture {
                    if f.enemy_state != 0 && f.enemy_action == 0x0b {
                        if let Some(enemy) = self.enemies.get_mut(0) {
                            // F37d: canon froze the executor mid-raise, not on
                            // entry. OAM on the row's own canon capture
                            // (frame 15, enemy palette 1) shows all five of
                            // anim 1's frame-4 parts at the mirrored boxes
                            // (164,107,32x16), (172,123,8x16),
                            // (174,127,16x32), (166,131,8x16) and
                            // (163,143,32x8) -- our ROM-exported mettaur.bin
                            // anim 1 frame_in_anim 4 exactly (32x16 at
                            // (-16,-40), 8x16 at (0,-24), mirrored about the
                            // enemy origin; sub_8109DEC sets CurAnim 1 on
                            // entry, asm31.s:170830-170848, and the sprite
                            // updater advances it until BattlePaused freezes
                            // it, asm00_1.s:90-110). Frame 4 is reached after
                            // the durations of frames 0..3 (1+1+1+3) and held
                            // for its own 8, so priming the seeded attack
                            // this many executor ticks lands the frozen sprite
                            // on it. F37b's reverted 9-tick prime is this same
                            // value; it measured worse only because the
                            // actor-Y pan (F37c) had not landed yet.
                            const SWING_PRIME: u8 = 9; // provenance: derived -- sprite-frame durations in the ROM-exported mettaur.bin (1,1,1,3, then 8) + the OAM part-box match above; any count in 7..=14 shows the same frame
                            enemy.attack(actor::SWING);
                            for _ in 0..SWING_PRIME {
                                enemy.update();
                            }
                        }
                    }
                }
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
                // F28/F28b: a full gauge on its own pauses NOTHING in canon.
                // The fight state's own frame (`sub_800855E`, asm00_1.s:11125)
                // opens with `UnpauseBattle` (:11132) and only ever pauses by
                // LEAVING for another state: `sub_800A21C` (asm00_1.s:15203-
                // 15218) answers "is the custom gauge 0x4000, with no time
                // stop and the battle not over", and its caller pairs the
                // answer with `PauseBattle` and battle state 0x14 in one
                // breath (asm00_1.s:11188-11195). `gauge_pause` is this
                // project's model of the chimes BEFORE that transition, so a
                // fixture whose window may not open (FLAG_OPEN_WINDOW clear,
                // `demo-hudmatch`'s own case) has no transition to wait for
                // and must keep running. It did not: the branch below that
                // counts `gauge_pause` down is itself gated on
                // `open_window_allowed()`, so a full gauge re-armed it every
                // frame and froze the whole battle from the frame the gauge
                // filled -- F28 measured tiles/gauge's Mettaur idling in its
                // post-spawn wait for a 470-frame capture because of it.
                if self.gauge == GAUGE_FULL && self.open_window_allowed() {
                    self.gauge_pause = GAUGE_PAUSE;
                }
            }
        }
        // Bring the field in, then the enemies one by one, then say so.
        let intro = if self.intro_fade > 0 {
            self.intro_fade -= 1;
            true
        } else if self.intro_next < self.enemies.len() {
            if !self.enemies[self.intro_next].is_present() {
                self.enemies[self.intro_next].appear();
            } else if !self.enemies[self.intro_next].is_busy() {
                self.intro_next += 1;
                // The last one has finished materialising: BATTLE START!.
                // sub_8008064 (asm00_1.s:10386) raises message 0 here, and
                // THE FIGHT IS PAUSED FOR THE WHOLE OF IT. There is no
                // PauseBattle call inside sub_8008064, which is what an
                // earlier reading of this stopped at -- but one is already in
                // effect: PauseBattle() fires on the first tick of battle
                // state 0 (asm00_1.s:12786) and the only UnpauseBattle()
                // reachable from there is at the top of sub_80080D2
                // (asm00_1.s:10448), the state AFTER this one. And this state
                // is left only when sub_801E754 reports the banner idle, which
                // for a KIND 0 record like BATTLE START!'s has no early-out.
                // So the pause covers the banner's whole 58 frames.
                // The banner does NOT go up here. Measured from a save state at
                // a battle's first frame: the chip window opens at 165 and is
                // confirmed, closes at 259, and BATTLE START! goes up at 289 --
                // thirty frames AFTER the window, not after the intro. See
                // where `banner_at` is armed below.
            }
            true
        } else {
            false
        };
        let presenting = self.presentation.is_some();
        // The opening banner holds the fight, as above. The closing one does
        // not need to: the fight is over by then.
        let opening = self.banner.is_some() && !self.banner_done;
        // F33d: `over` (the 0x0C end sequence, battle main 0x0800A09F ->
        // sub_80081A4, reference/bn6f/asm/asm00_1.s:10617) does NOT pause the
        // fight. Canon keeps simulating inputs/objects/HUD/RESULT after the
        // countdown starts: the banner-sequencer dispatch sub_800801C
        // (asm00_1.s:10422, table off_8008038) runs the 0x0C handler, and
        // only the 0x08 arm refreshes AIData from the joypad mirror
        // (sub_8012DFC, asm00_2.s:8977, called at asm00_1.s:10519-10522) --
        // but the held word persists, so movement still reads it past
        // battle 47 (traced on warp's own canon capture: poke Right@130
        // warps at 132, Down@150 warps at 152; MegaMan's object 0x0203a9b8
        // reads 0x00001004 through both warps, 0x00040804 between), the
        // buster fires (CurAction 0x08->0x11 at canon 132) and chips fire
        // (CurAction 0x08->0x14, object_setAttack2 0x0801169A) -- while our
        // `paused` used to include `over` and froze the scripted subjects.
        // What `over` still drives is unchanged: the HUD teardown
        // (`hud_live = false`, canon's own mask 0x4497->0x8084 at 48 then
        // 0x0084 at 106, watched), the ENEMY DELETED banner arming, and the
        // RESULT countdown/slide (F32's count, F21/F34's driver chain).
        let paused = self.gauge_pause > 0
            || self.custom.is_some()
            || intro
            || opening
            || presenting;
        // ...except the clear-time clock, which keeps the old gate: the
        // traces behind this split cover inputs (held word persists, warps
        // fire), objects (CurAction writes) and HUD/RESULT updates -- nothing
        // says the clock runs past the kill, and it feeds the RESULT time
        // readout, so moving it shifts every post-show frame's digits.
        if !(paused || over) {
            self.clock += 1;
        }
        // AUDIT pairs 6/14/17: `start_state` = 1 (FIXTURE.md +40) puts the
        // window up at once with the descriptor's own readout
        // (`result_level`/`result_frames`/`result_zenny`, +41/+42/+44) --
        // e.g. to compare against /tmp/noenemy2.state -- instead of waiting
        // for a chip press to end the fight normally.
        let fixture_results = self.fixture.filter(|f| f.start_state == 1);
        if self.shown.is_none()
            && self.fade_out == 0
            && let Some(f) = fixture_results
        {
            // result_elapsed: 0xFFFF = settled (results::Shown::SETTLED
            // frames is always enough -- extra fast_forward calls past
            // Phase::Waiting are no-ops), otherwise the field's own
            // frame count.
            let elapsed = if f.result_elapsed == FIXTURE_UNSET { // (see FIXTURE_UNSET)
                results::Shown::SETTLED
            } else {
                f.result_elapsed as u32
            };
            self.show_results(
                results::WIN,
                f.result_frames as u32,
                f.result_level,
                f.result_zenny,
                elapsed,
                gfx,
            );
        }
        if over && self.shown.is_none() && self.fade_out == 0 {
            // The banner the fight ends on, put up once: the real ROM shows it
            // and then brings the RESULT window in behind it.
            if !self.banner_done && self.results_delay <= RESULTS_DELAY {
                self.banner_done = true;
                let message = if self.megaman.is_defeated() {
                    banner::MEGAMAN_DELETED
                } else {
                    banner::ENEMY_DELETED
                };
                self.banner = Some(Banner::new(self.banner_assets, message));
            }
            if self.results_delay > 0 {
                self.results_delay -= 1;
            } else {
                let won = !self.megaman.is_defeated();
                let level = results::busting_level(&results::Tally {
                    time: self.clock,
                    hits_taken: self.megaman.hits_taken(),
                    moves: self.moves,
                });
                let kind = if won { results::WIN } else { results::LOSE };
                self.show_results(kind, self.clock, level, RESULTMATCH_ZENNY, 0, gfx);
            }
        }
        if let Some(window) = self.shown.as_mut() {
            let confirm = input.is_pressed(Button::A) || input.is_pressed(Button::Start);
            // Canon draws the WIN reward only after the first confirm
            // (sub_802C044, asm03_0.s:11959): start the reveal here and
            // draw its content (the tilesets live on `Results`).
            if window.poll_reward_reveal(confirm) {
                self.results.draw_reward(window);
            }
            if let Some(fade) = window.update(confirm) {
                self.fade_out = fade;
                if fade == RESULTS_FADE_BLACK {
                    self.shown = None;
                    self.results_mark = None;
                }
            }
        }
        if matches!(self.shown.as_ref(), Some(w) if w.blit_needed) {
            self.results.blit_slide(self.shown.as_mut().unwrap());
        }
        // The fade-out ends on full black; the next battle's intro fades the
        // field back in from there.
        if self.fade_out == RESULTS_FADE_BLACK {
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
        // button, asm00_2.s:9492). IT FIRES ON THE RELEASE, not the press:
        // hold B on the real ROM and the navi stands in his idle and charges
        // for as long as you hold it, and only shoots when you let go. A tap
        // is a press and a release, which is why tapping still fires at once
        // and why this went unnoticed against a two-frame press.
        if !paused {
            // A uses the next chip of the hand when the navi is free
            // (asm00_2.s:9492-9518: AIData flag 4 when the hand has a chip).
            // ON THE PRESS, two frames later -- NOT on the release, which is
            // what a two-frame press cannot tell apart. Held down for sixty
            // frames on the real ROM, the chip still goes off on the second
            // frame after the press and the icon leaves the navi's hand then;
            // only the BUSTER waits for the button to come up.
            if input.is_just_pressed(Button::A) && self.chip_use_in == 0 {
                self.chip_use_in = CHIP_USE_DELAY;
            }
            if self.chip_use_in > 0 {
                self.chip_use_in -= 1;
                if self.chip_use_in == 0 && !self.megaman.is_busy() && self.hand_at < self.hand.len()
                {
                    let chip = self.hand[self.hand_at];
                    self.hand_at += 1;
                    self.use_chip(chip);
                }
            }
            if input.is_pressed(Button::B) {
                self.charge = self.charge.saturating_add(1);
            } else {
                if self.charge >= CHARGE_FRAMES {
                    self.megaman.attack_charged();
                } else if self.charge > 0 && !self.megaman.is_busy() {
                    let spec = self.megaman.buster_spec();
                    self.megaman.attack(spec);
                    // The barrel comes with the POSE, not with the button:
                    // the real navi stands in his idle first.
                    self.buster_arm_in = BUSTER_ARM_DELAY;
                }
                self.charge = 0;
            }
        }
        // AUDIT pairs 6/14/17: MegaMan fires the hand chips on a repeating
        // timer, so a capture run does not rely on key timing -- a fixture's
        // own FLAG_AUTO_FIRE; its `fire_frame` seeds `auto_ticks` in
        // `Battle::new` and reseeds it here between shots. Waits for the
        // fight to open, a free navi and a chip; the hand is cycled forever
        // (hand_at wraps) and the custom window is never allowed to open, so
        // a capture run keeps shooting the featured chip instead of dropping
        // into a chip select that empties the hand. No fixture: no auto-fire.
        if let Some(f) = self.fixture {
            if f.flag(fixture::FLAG_AUTO_FIRE)
                && !paused
                && self.intro_next >= self.enemies.len()
            {
                self.gauge = 0;
                if self.auto_ticks > 0 {
                    self.auto_ticks -= 1;
                } else if !self.megaman.is_busy() && !self.hand.is_empty() {
                    let chip = self.hand[self.hand_at];
                    self.hand_at = (self.hand_at + 1) % self.hand.len();
                    self.use_chip(chip);
                    self.auto_ticks = f.fire_frame;
                }
            }
        }

        // The charge states index the glow sprite's animation (see GLOW_ANIM):
        // 0 idle, 1 charging, 2 full.
        const CHARGE_STATE_FULL: usize = 2; // provenance: derived -- the glow's animation index is the charge state (see GLOW_ANIM)
        let state = match self.charge {
            c if c >= CHARGE_FRAMES => CHARGE_STATE_FULL,
            c if c >= CHARGING_FROM => 1,
            _ => 0,
        };
        if state != self.glow_state {
            self.glow_state = state;
            if state != 0 {
                self.glow.play(GLOW_ANIM[state]);
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
            // is checked twice, matching canon's own split (F1): BEFORE the
            // shot advances, so the panel it spawns on counts and a
            // point-blank target is hit on the first frame -- and, via
            // `just_hopped()`, on the HOP frame itself, because canon applies
            // the damage in the same frame the wave advances onto the
            // target's panel (watch-write on MegaMan's object: the HP store
            // from applyDamageToPlayer_801ba12, asm00_2.s:24832 ->
            // object_subtractHP at object.s:4685, and the flinch entry
            // object_setAttack0 at asm00_2.s:23606 are all inside canon frame
            // 114, the same frame the wave's light schedule puts the hop
            // in). Checking only before the advance registered the hit a
            // frame late: our wave's hop schedule is pixel-identical to
            // canon's (BG2 pairs at 0), yet the flinch started at k=44
            // against canon's k=43.
            let spawn_arrival = self.shots[i].just_arrived();
            let off_field = !objects::t3_entry(&mut self.shots[i]);
            let mut spent = off_field;
            let arrived = spawn_arrival || self.shots[i].just_hopped();
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
            // A wave that dwelt its way off the field still has its parting
            // light lingering behind it, and/or its last departing segment
            // still playing out at the panel it left (left_panel/left_ticks
            // and departure, both set by the update() call above): the real
            // ROM's segment keeps re-asserting its old panel's highlight
            // every frame until ITS OWN departure finishes
            // (object_highlightCurrentCollisionPanels is called
            // unconditionally each frame from sub_80C6C14, asm31.s:31491-2,
            // regardless of whether the CurAction is "moving" or "dying"), not
            // just while the hitbox is still on the field. Keep the shot alive
            // (hidden, harmless) until both linger out on their own.
            if off_field && self.shots[i].lights_panel && self.shots[i].departing() {
                spent = false;
                self.shots[i].hidden = true;
            }
            if spent {
                self.shots.swap_remove(i);
            } else {
                // A shockwave lights the panel it is standing on, every frame
                // it is there.
                if self.shots[i].lights_panel {
                    let here = (self.shots[i].col, self.shots[i].row);
                    let lit = [Some(here), self.shots[i].left_panel];
                    for (c, r) in lit.into_iter().flatten() {
                        self.light_wave_panel(c, r);
                    }
                }
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
                    Some(CHIP_BAMBSWRD) => (SWORD_SPR, BAMBSWRD_SWORD_PALETTE),
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
                    false,
                ));
            } else {
                self.sword_in = Some(left - 1);
            }
        }
        if let Some(popup) = self.popup.as_mut() {
            if !popup.update() {
                self.popup = None;
            }
        }
        if self.blip_in > 0 {
            self.blip_in -= 1;
            if self.blip_in == 0 {
                agb::sound::psg::Channel1::play(
                    BUSTER_BLIP_SWEEP,
                    agb::sound::psg::Duty::Eighth,
                    BUSTER_BLIP_ENVELOPE,
                    BUSTER_BLIP_FREQ,
                    None,
                );
                self.blip_off = BUSTER_BLIP_FRAMES;
            }
        }
        if self.blip_off > 0 {
            self.blip_off -= 1;
            if self.blip_off == 0 {
                agb::sound::psg::Channel1::stop();
            }
        }
        if self.hit_in > 0 {
            self.hit_in -= 1;
            if self.hit_in == 0 {
                // AT THE TRACK'S OWN VOLUME, not full. The sound's M4A track
                // opens `0xBE 0x70` -- VOL 0x70 = 112 of M4A's 0..127 -- so the
                // real ROM plays this sample at 112/127 of full
                // (data/dat37.s:41543, byte_81B8308, the track the SongHeader
                // for SOUND_HIT_6B points at). Playing it at agb's default 1.0
                // measured 4603 peak residual RMS against the real ROM's 4074,
                // about 13% loud; 4603 * 112/127 = 4060, which is the real
                // figure to within a third of a percent.
                let mut channel = agb::sound::mixer::SoundChannel::new(BUSTER_HIT);
                channel.volume(agb::fixnum::Num::<i16, 8>::new(112) / 127); // canon: 112/127 trims agb's 1.0 to the real peak (see above)
                mixer.play_sound(channel);
            }
        }
        if self.banner_at > 0 {
            self.banner_at -= 1;
            if self.banner_at == 0 {
                self.banner = Some(Banner::new(self.banner_assets, banner::BATTLE_START));
            }
        }
        if let Some(banner) = self.banner.as_mut() {
            if !banner.update() {
                self.banner = None;
            }
        }
        // AUDIT pairs 6/14/17: a fixture's own `banner_at` (FIXTURE.md +46,
        // 0xFFFF = never forced) puts ENEMY DELETED up on a known frame from
        // a descriptor -- e.g. to compare against a capture that deletes the
        // enemy and presses Start at 10 -- so it can be compared with the
        // real ROM's. Note this is NOT the same thing as `self.banner_at` a
        // few lines up, an unrelated existing countdown field for the real
        // BATTLE START banner that a fixture never arms (see the
        // `!self.opened && self.fixture.is_none()` guard above). No fixture:
        // never forced -- the clock STOPS while an opening banner is up, so
        // a bare `clock == target` would stay true every frame and rebuild
        // the banner forever the moment the pause went in.
        let banner_target = self
            .fixture
            .map(|f| f.banner_at)
            .filter(|&v| v != FIXTURE_UNSET)
            .map(|v| v as u32);
        if banner_target == Some(self.clock) && !self.opened {
            self.opened = true;
            self.banner = Some(Banner::new(self.banner_assets, banner::ENEMY_DELETED));
        }
        // AreaGrab's steal orbs fall 0x80000 a frame from 0x1000000 (32 steps,
        // OAM watch: first pair at capture 62, +8px/frame, all three down at
        // capture 80) and land when Z reaches 0 -- the column is stolen on the
        // land frame (still showing the held fall frame), the burst plays from
        // the next frame (sub_80C64A0 land + action 4, sub_80C6524 anim 1 on
        // the frame after), and the orb is dropped when the burst is done
        // (sub_80C6536 end-of-anim destroy).
        let mut areagrab_landed = false;
        for orb in self.areagrab_orbs.iter_mut() {
            if orb.burst {
                orb.player.update();
            } else if orb.landed {
                orb.burst = true;
                orb.player.play(AREAGRAB_BURST_ANIM);
            } else {
                orb.z -= AREAGRAB_ORB_ZVEL;
                if orb.z <= 0 {
                    orb.z = 0;
                    orb.landed = true;
                    areagrab_landed = true;
                }
            }
            // The palette walk never freezes at the burst: the live OBJ
            // palette cycles one sprite row per frame unbroken through the
            // land frame and the burst (OBJ palette RAM watch, canon
            // captures 62..81, period 4), while the sprite frame itself is
            // held by object_updateSpriteTimestop (t3_0xf_80C6414,
            // asm31.s:30497) -- so the age walk runs on burst frames too.
            orb.age += 1;
            orb.player
                .set_palette_add((orb.age as usize + AREAGRAB_ORB_PAL_PHASE) % AREAGRAB_ORB_PALS);
        }
        self.areagrab_orbs
            .retain(|orb| !orb.burst || !orb.player.finished());
        if areagrab_landed {
            let occupied = self
                .enemies
                .iter()
                .filter(|e| e.is_present())
                .fold(0, |m, e| m | e.occupancy());
            for (col, row) in self.panels.steal_column(occupied) {
                self.panels.highlight(col, row, 0);
            }
        }
        if let Some((chip, left)) = self.presentation {
            if left == 0 {
                self.presentation = None;
                match chip.id {
                    CHIP_INVISIBL => self.megaman.set_invisible(INVISIBL_FRAMES),
                    // AreaGrab steals nothing here: each orb stole its panel
                    // as it landed (see the orb update above), so by the time
                    // the presentation ends there is nothing left to take.
                    CHIP_AREAGRAB => {}
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
                // One orb per row at the enemy half's edge column, as the
                // sub_80E0754 loop spawns them (PanelY 1..3).
                if chip.id == CHIP_AREAGRAB
                    && left == AREAGRAB_PRESENTATION - AREAGRAB_SPAWN_AGE
                {
                    for row in 1..=field::ROWS {
                        let (lo, _) = self.panels.half(true, row);
                        let (ox, oy) = field::panel_centre(lo, row);
                        let mut player = spr::Player::frozen_at(
                            spr::Assets::new(AREAGRAB_ORB),
                            AREAGRAB_FALL_ANIM,
                            0,
                        );
                        player.set_palette_add(AREAGRAB_ORB_PAL_PHASE % AREAGRAB_ORB_PALS);
                        self.areagrab_orbs.push(AreagrabOrb {
                            player,
                            x: ox,
                            y: oy,
                            z: AREAGRAB_ORB_Z0,
                            age: 0,
                            landed: false,
                            burst: false,
                        });
                    }
                }
                self.presentation = Some((chip, left - 1));
            }
        }
        if let Some(bubble) = self.bubble.as_mut() {
            bubble.update();
            if self.megaman.barrier() == 0 {
                self.bubble = None;
            }
        }
        let navi_update = objects::t1_player_entry(&mut self.megaman);
        if let Some((gun, _, _)) = self.vulcan_gun.as_mut() {
            match navi_update {
                // The firing state's first frame is also its first shot.
                Update::PoseBegun | Update::Strike { .. } if gun.anim() == 0 => gun.play(1), // unnamed: gun object's firing animation
                Update::Recovering => gun.play(2), // unnamed: gun object's recovery animation
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
                    for (_, pos, _, _, _) in self.effects.iter_mut() {
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
                if charged {
                    self.shots.push(Shot::buster(
                        spr::Assets::new(SHOTFX),
                        col,
                        row,
                        self.megaman.facing_dx(),
                        CHARGED_DAMAGE,
                    ));
                } else {
                    self.blip_in = BUSTER_BLIP_DELAY;
                    self.hit_in = BUSTER_HIT_DELAY;
                    // THE PLAIN BUSTER IS A HITSCAN. Its shot never crosses
                    // the field: OAM on the firing frame has a 32x16 flash
                    // still at the gun while the enemy's HP is already down.
                    // So the row is struck at once and the only object is the
                    // flash, at the FRONT panel's x and BUSTER_FX_UP above the
                    // panel's centre -- (100,82) in the capture, whose navi
                    // stands on the panel centred at (60,108).
                    let (mc, mr) = self.megaman.panel();
                    for enemy in self.enemies.iter_mut().filter(|e| e.is_targetable()) {
                        let (ec, er) = enemy.panel();
                        if er == mr && (ec - mc) * self.megaman.facing_dx() > 0 {
                            enemy.take_damage(BUSTER_DAMAGE);
                            break;
                        }
                    }
                    let (px, py) = field::panel_centre(col, row);
                    // NOT pre-ticked. The effects loop already ticks every
                    // effect on the frame it was pushed, so the extra tick here
                    // ate the first cell of assets/buster_fx.bin's animation
                    // (frame 0, duration 2) down to one frame and ran the whole
                    // muzzle one frame early. canon's cells are 2/1/1/2 and then
                    // the last frame is HELD (flags 0x80) until the attack state
                    // exits -- measured: 8x8 at canon 135-136, 32x16 at 137-138,
                    // 16x8 at 139-140, the last (blank) 8x8 at 141-158.
                    let fx = spr::Player::new(spr::Assets::new(BUSTER_FX), 0);
                    // Spawned one frame into the pose (the fire phase's second
                    // tick), so it outlives the pose's remaining frames.
                    let pose_left = self.megaman.buster_spec().frames.saturating_sub(1);
                    self.effects
                        .push((fx, (px, py - BUSTER_FX_UP), pose_left, false, false));
                }
            }
            Update::Died => {
                let at = field::panel_centre(self.megaman.panel().0, self.megaman.panel().1);
                self.effects
                    .push((spr::Player::new(spr::Assets::new(DELETE), 0), at, DELETE_FRAMES, false, false));
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
        // A freshly spawned shockwave's own panel, applied once the loop below
        // has released its borrow of `self.enemies`. See the strike arm.
        let mut wave_spawn: Option<(i32, i32)> = None;
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
            // F37b: unflagged objects skip their update under BattlePaused
            // (asm00_1.s:90-110), so while the chip window is up the enemy's
            // ticks do not run either -- the seeded pose above holds instead
            // of decaying back to idle. The gate covers the post-close
            // frames too on a fixture capture: canon's BattlePaused reads 1
            // a hundred frames past the close (F37's watch), while this
            // build's `custom` is already None there, so `window_closed`
            // (set once at Done, never reset) extends the freeze past the
            // close. Fixture-scoped: with no fixture the fight resumes after
            // a close as it should. MegaMan keeps ticking: his states
            // already match per oracle and he is occluded on every row this
            // reaches.
            // (Inline rather than a helper: the loop below holds
            // `enemies`/`ais` mutably borrowed, so a &self method would not
            // compile; disjoint field reads do.)
            if self.custom.is_none() && !(self.fixture.is_some() && self.window_closed) {
                objects::enemy_act(enemy);
            }
            continue;
            }
            if !paused && !enemy.is_busy() && self.megaman.is_targetable() {
                let blocked = (all_held & !held[i]) | self.panels.other_half(true);
                // Decided as the attack begins, as the game does, and held for
                // its duration even if the player moves.
                self.cross_shape = ai::cross_targets(self.megaman.panel());
                objects::enemy_think(ai, enemy, self.megaman.panel(), blocked, &mut self.primary_rng);
            }
            // Same freeze as above: the seeded attack pose holds while the
            // window is up and past its close (see the note there).
            // `Nothing` hits no arm of the match below, so a frozen frame
            // spawns no shot, lights no panel, ends no life.
            let update = if self.custom.is_none()
                && !(self.fixture.is_some() && self.window_closed)
            {
                objects::enemy_act(enemy)
            } else {
                Update::Nothing
            };
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
                    if frame % WINDUP_TELEGRAPH_EVERY == 0 && !matches!(ai.style(), ai::Style::Mettaur) =>
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
                        .push((spr::Player::new(spr::Assets::new(DELETE), 0), at, DELETE_FRAMES, false, false));
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
                    // The first hop's light, one frame earlier than the shots
                    // loop would give it. That loop runs EARLIER in this same
                    // frame, before the shot exists, so a freshly spawned
                    // shockwave would not light its panel until the frame
                    // after -- while every LATER hop lights its new panel on
                    // the frame it happens, because the loop reads the column
                    // after `Shot::update` has already advanced it. Only the
                    // spawn carries that extra tick, so only the spawn needs
                    // the nudge. Measured: the real ROM's frame 71 already has
                    // (4,2) lit and ours did not until 72.
                    //
                    // It matches the real ROM's own split between init and
                    // update, which is the reassuring part: `sub_80C6B64`, the
                    // CurState-0 handler that runs on a segment's first tick,
                    // builds the sprite and the collision data but never
                    // highlights (asm31.s:31421-31496), and
                    // `object_highlightCurrentCollisionPanels` is reached only
                    // from `sub_80C6C14`, the CurState-1 handler
                    // (asm31.s:31499-31537, the call at 31524), every tick
                    // from then on. So the real segment's init tick is the one
                    // tick with no highlight -- which is a highlight that
                    // starts as soon as the object exists, not one tick into
                    // its life.
                    wave_spawn = Some((col, row));
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
        // Now that the loop above has released its borrow of `self.enemies`,
        // `light_wave_panel` can take `&mut self` again.
        if let Some((c, r)) = wave_spawn {
            self.light_wave_panel(c, r);
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
        // The fireball ages on its own clock (None = spawned this frame, so
        // the spawn frame ends at age 0 and ages match canon's gun-ages).
        if let Some((_, age)) = self.vulcan_fireball.as_mut() {
            *age = Some(age.map_or(0, |a| a.saturating_add(1)));
        }
        if matches!(self.vulcan_fireball, Some((_, Some(age))) if age > VULCAN_FIREBALL_LAST_VISIBLE)
        {
            self.vulcan_fireball = None;
        }
        for (counter, hp) in self.hp_shown.iter_mut().zip(
            core::iter::once(self.megaman.hp()).chain(self.enemies.iter().map(|e| e.hp())),
        ) {
            counter.update(hp);
        }
        // The HP box AFTER its counter has stepped: the real ROM's first
        // orange frame already shows the lower number, so drawing it before
        // the step flashes the old one.
        if self.hud_tiles.is_some() {
            self.hud_tiles
                .as_mut()
                .unwrap()
                .set_hp(self.hud_bg.as_mut().unwrap(), self.hp_shown[0].shown());
            // ONE FRAME BEHIND the digits. A palette write lands on the frame
            // it is made and the box's tile writes land on the next, so
            // swapping the ramp the moment the counter flashes paints the
            // OLD number orange for a frame.
            let flashing = core::mem::replace(
                &mut self.hp_flash_next,
                self.hp_shown[0].set() != crate::hud::SET_PLAIN,
            );
            if self.hp_flashing != flashing {
                self.hp_flashing = flashing;
                let hud = self.hud_tiles.as_ref().unwrap();
                let p = if flashing { hud.flash_palette() } else { hud.palette() };
                gfx.set_background_palette(crate::hudtiles::BANK, &p);
            }
        }
        if let Some((left, to)) = self.held_raise {
            if left == 0 {
                self.held_raise = None;
                if let Some((_, pos, _, _, _)) = self.effects.first_mut() {
                    *pos = to;
                }
            } else {
                self.held_raise = Some((left - 1, to));
            }
        }
        // The afterimage is spawned on the attack's frame 0 and ages from
        // there; it is gone after frame 18.
        if let Some((_, _, age)) = self.step_ghost.as_mut() {
            *age += 1;
            let age = *age;
            let (mcol, mrow) = self.megaman.panel();
            self.step_trail[age as usize % STEP_TRAIL_LEN] =
                (self.megaman.sprite_key(), field::panel_centre(mcol, mrow));
            if age == STEP_GHOST2_FIRST {
                self.step_dest = field::panel_centre(mcol, mrow);
            }
            self.step_trail_sword[age as usize % STEP_TRAIL_LEN] =
                self.effects.first().map(|(p, _, _, _, _)| p.frame_key());
            // Refreshed on the first frame of each blink pair and held for
            // the second: on frames 16 AND 17 the real copy carries the
            // navi's frame-13 sprite, not 13 and then 14.
            // It stops taking new frames once the navi has gone home: from
            // then on it holds the last pose the navi had on that panel.
            if age >= STEP_GHOST2_FIRST && (age - STEP_GHOST2_FIRST) % STEP_RING_PERIOD == 0 {
                // Three frames back is the next slot round the ring of four,
                // and only while the navi was still on the far panel then.
                let (delayed, was_at) = self.step_trail[(age as usize + STEP_TRAIL_NEXT) % STEP_TRAIL_LEN];
                if self.step_ghost2_key != Some(delayed) && was_at == self.step_dest {
                    let mut ghost =
                        spr::Player::frozen_at(spr::Assets::new(MEGAMAN), delayed.0, delayed.1);
                    ghost.set_red_only(true);
                    let at = self.step_dest;
                    self.step_ghost2 = Some((ghost, at));
                    self.step_ghost2_key = Some(delayed);
                    self.step_ghost2_sword = match (
                        self.step_trail_sword[(age as usize + STEP_TRAIL_NEXT) % STEP_TRAIL_LEN],
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
        self.effects.retain_mut(|(p, _, ticks, _, _)| {
            p.update();
            let alive = *ticks > 0;
            *ticks = ticks.saturating_sub(1);
            alive
        });
        // PoisSeed's sheet, one frame after the pod lands.
        if self.poison_pending > 0 {
            self.poison_pending -= 1;
            if self.poison_pending == 0 {
                let (first, last) = field::half(true);
                // Canon overlap order row by row, read off the real ROM's
                // OAM watch at the sheet stage: each row is one OAM group --
                // back row OAM0-5, middle OAM6-11, front OAM15-20 -- with the
                // middle column's sheet on top throughout (zone B still has
                // R148 over L188). Within a row the outer columns follow the
                // middle as [first, last], except on the back row, which runs
                // [last, first]: OAM0-5 reads c5, c4, c6 while OAM6-11 and
                // OAM15-20 read c5, c6, c4. Effects draw last-pushed-first,
                // so rows go front to back and the middle column stays last.
                // provenance: peeked -- canon OAM watch at the sheet stage.
                let mid = first + SHEET_MID_STEP;
                for r in 1..=field::ROWS {
                    // Back-row outer columns run last-first (peeked: canon
                    // back-row OAM reads c5, c4, c6); other rows first-last.
                    for c in if r == field::ROWS { [last, first, mid] } else { [first, last, mid] } {
                        // NOT in the sterile arena: the real capture's field
                        // layer is stripped, so its poison panels cannot show,
                        // while this build's field would paint them and cost
                        // the comparison 1440 px a frame. The sheet itself is
                        // objects and shows on both sides. `self.backdrop` is
                        // None under exactly the same condition (sterile, or
                        // a fixture's FLAG_BLANK_BACKDROP) so it stands in for
                        // the old cfg! check without a second stored flag.
                        if self.backdrop.is_some() {
                            self.panels.set(c, r, field::PANEL_POISON);
                        }
                        // Spawned a frame after the pod lands and already one
                        // tick in, so its first frame shows for that one frame
                        // only: with either half of that alone the whole sheet
                        // runs a frame early or a frame late.
                        let mut sheet =
                            spr::Player::new(spr::Assets::new(POISAREA), POISON_ANIM);
                        sheet.set_palette_add(self.poison_palette);
                        sheet.update();
                        self.effects.push((
                            sheet,
                            field::panel_centre(c, r),
                            POISON_FRAMES - 1,
                            false,
                            false,
                        ));
                    }
                }
            }
        }
        // EnergBom/MegEnBom's landing bursts nothing -- their Param1 is 2,
        // so the landing's region byte (dword_80C5D7C[2]) is 0 and
        // sub_801BD3C spreads nothing. The t3_0x11 energy explosion
        // (sprite_83B2494, effect list 0x14 index 0x12, animation 0, no
        // shadow, sound 0xBB) starts on the frame after the landing instead.
        if self.ring_pending > 0 {
            self.ring_pending -= 1;
            if self.ring_pending == 0 {
                let (cx, cy) =
                    field::panel_centre(self.ring_target.0, self.ring_target.1);
                // Spawned after this frame's effect tick, so take this
                // frame's tick now, exactly like the blast below.
                let mut ring = spr::Player::new(spr::Assets::new(ENERGBOM_BLAST), 0);
                ring.update();
                self.effects.push((
                    ring,
                    (cx, cy),
                    ENERGBOM_BLAST_FRAMES - 1,
                    false,
                    false,
                ));
            }
        }
        // A bomb that lands bursts on its panel (sub_80C5DBC's fuse of zero:
        // the blast, setCollisionRegion(1), then sprite 0x26's animation 0).
        let mut landed = Vec::new();
        self.bombs.retain_mut(|b| {
            b.player.update();
            b.step();
            b.ticks += 1;
            if b.ticks >= b.flight {
                let mut keep = false;
                if b.rests {
                    if b.rest_snaps {
                        // BugBomb does not stop at the trajectory's endpoint:
                        // the landing snaps X/Y to the target panel and Z to
                        // ten above it (sub_80D9E94 loc_80D9EC2,
                        // asm31.s:71822-71835), and the frozen bomb keeps
                        // drawing through the bomb path, which is what splits
                        // the ball from its ground shadow the way the real
                        // ROM's OAM does. VDoll's doll snaps the same way but
                        // rests ON the panel (sub_80D47C0 loc_80D481E,
                        // asm31.s:60568, Z = 0) and poisons it
                        // (object_setPanelType 4); doll and shadow coincide.
                        let (cx, cy) = field::panel_centre(b.target.0, b.target.1);
                        b.x = cx << Q16_SHIFT;
                        b.y = cy << Q16_SHIFT;
                        b.z = b.rest_z;
                        b.vx = 0;
                        b.vz = 0;
                        b.gravity = 0;
                        b.ticks = 0;
                        b.flight = RESTS_FRAMES;
                        keep = true;
                        // The poison shows on the field layer, which the
                        // sterile arena strips -- same gate as the seeds'
                        // sheets below (self.backdrop is None there).
                        if b.rest_poisons && self.backdrop.is_some() {
                            self.panels.set(b.target.0, b.target.1, field::PANEL_POISON);
                        }
                    } else {
                        // The thrown object is not replaced: it stops where it
                        // lands and keeps its animation.
                        let mut resting = core::mem::replace(
                            &mut b.player,
                            spr::Player::new(spr::Assets::new(MINIBOMB), 0),
                        );
                        resting.update();
                        self.effects.push((
                            resting,
                            b.position(),
                            RESTS_FRAMES,
                            false,
                            false,
                        ));
                    }
                }
                landed.push((
                    b.target,
                    b.damage,
                    b.wide,
                    b.poison.then_some(b.seed_palette),
                    b.rests,
                    b.ener,
                ));
                keep
            } else {
                true
            }
        });
        for ((col, row), damage, wide, poison, rests, ener) in landed {
            // EnergBom and MegEnBom do not burst (see ring_pending): their
            // landing spreads nothing, and the explosion follows a frame
            // later.
            if ener {
                self.ring_pending = 1;
                self.ring_target = (col, row);
                continue;
            }
            // A resting object does not burst: BugBomb's ball and VDoll's
            // doll just stop where they land.
            if rests {
                continue;
            }
            // PoisSeed does not burst: it lays poison over the enemy's whole
            // half, nine panels, each with a pale green sheet that grows out
            // of an ellipse over sixteen frames. Read off the real ROM's OAM
            // at the landing: nine pairs of 32x32 objects, one pair per panel
            // -- a panel is forty wide, so it takes two -- all of them one
            // sprite, byte_830E44C.spr, in the seed's own palette bank. The
            // panels themselves are POISON underneath, which the field asset
            // already carries.
            if let Some(sheet_palette) = poison {
                // The pod is gone for ONE frame before the sheet starts: the
                // real ROM's landing frame shows neither. Measured -- with the
                // sheet spawned the moment the pod goes, its whole animation
                // is a frame early and c48 carries nine ellipses the real ROM
                // does not have.
                self.poison_pending = 1;
                self.poison_palette = sheet_palette;
                continue;
            }
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
                    .push((blast, field::panel_centre(c, r), BLAST_FRAMES - 1, false, false));
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
            CHIP_MINIBOMB | CHIP_BLKBOMB | CHIP_BIGBOMB | CHIP_ENERGBOM | CHIP_MEGENBOM
            | CHIP_LILBOLR1 | CHIP_LILBOLR2 | CHIP_LILBOLR3
            | CHIP_FLSHBOM1 | CHIP_FLSHBOM2 | CHIP_FLSHBOM3
            | CHIP_GRASSEED | CHIP_ICESEED | CHIP_POISSEED
            | CHIP_BUGBOMB | CHIP_VDOLL => {
                self.chip_in_use = Some(chip);
                self.megaman.attack(THROW);
                let (mc, mr) = self.megaman.panel();
                let flash = matches!(
                    chip.id,
                    CHIP_FLSHBOM1 | CHIP_FLSHBOM2 | CHIP_FLSHBOM3
                );
                // The flash bomb is its own sprite, sprite_8391E40, found by
                // taking the held ball's tiles out of OBJ VRAM and searching
                // the data blobs -- it is in no sprite file.
                // PoisSeed lobs a magenta pod: byte_82F569C.spr, found by
                // taking the four tiles of its flying object out of OBJ VRAM
                // and searching all 97 sprite files. Animation 8 is the pod in
                // the hand and 9 the pod in flight -- matched by their OAM
                // shapes against the real ROM's, an 8x8 shadow for the held
                // one and a 16x8 for the thrown. The magenta is palette 12 of
                // the sprite's own block, which carries a palette per seed;
                // index 0 is the blue one IceSeed uses.
                let seed = matches!(chip.id, CHIP_GRASSEED | CHIP_ICESEED | CHIP_POISSEED);
                // BugBomb and VDoll throw and LAND AND STAY rather than
                // bursting or laying a sheet.
                let rests = matches!(chip.id, CHIP_BUGBOMB | CHIP_VDOLL);
                let mut held = if chip.id == CHIP_VDOLL {
                    spr::Player::new(spr::Assets::new(POISSEED), VDOLL_HELD_ANIM)
                } else if chip.id == CHIP_BUGBOMB {
                    spr::Player::new(spr::Assets::new(POISSEED), BUG_HELD_ANIM)
                } else if seed {
                    spr::Player::new(spr::Assets::new(POISSEED), SEED_HELD_ANIM)
                } else if flash {
                    spr::Player::new(spr::Assets::new(FLSHBOM), 0)
                } else {
                    spr::Player::new(spr::Assets::new(MINIBOMB), bomb_anim(chip.id, false))
                };
                if seed || chip.id == CHIP_BUGBOMB {
                    held.set_offsets_follow_shift(true);
                }
                held.set_palette_add(seed_or_bomb_palette(chip.id, false));
                // The flash bomb's sprite carries its own part offsets, which
                // sit 22 right and 10 down of where the bomb sprite's do:
                // measured from the held ball's centre, (37,88) on the real
                // ROM against (59,98) drawn at the panel's origin.
                let at = field::panel_centre(mc, mr);
/// The flash bomb's sprite carries its own part offsets, 22 right and 10
/// down of the bomb sprite's (measured (37,88) on the real ROM against
/// (59,98) drawn at the panel's origin, see below); the raised ball sits 14
/// right and 24 up of that.
const FLASH_AT_DX: i32 = 22; // provenance: peeked -- measured (37,88) on the real ROM against (59,98) at the panel origin (see below)
const FLASH_AT_DY: i32 = 10; // provenance: peeked -- measured (37,88) on the real ROM against (59,98) at the panel origin (see below)
const FLASH_RAISE_DX: i32 = 14; // provenance: peeked -- measured off the real ROM (see below)
const FLASH_RAISE_DY: i32 = 24; // provenance: peeked -- measured off the real ROM (see below)
                let at = if flash { (at.0 - FLASH_AT_DX, at.1 - FLASH_AT_DY) } else { at };
                if flash {
                    self.held_raise = Some((HELD_RAISE_AT, (at.0 + FLASH_RAISE_DX, at.1 - FLASH_RAISE_DY)));
                }
                // The flash bomb's sprite carries a ground shadow as its
                // first part, and the real ROM does not draw it while the ball
                // is held: with the shadow on, this build's ground ellipse
                // runs to x63 on row 110 and starts at x55 on row 105, where
                // the real ROM's stops at x55 and starts at x57 -- its whole
                // ground mark is the navi's own. Drawn at the ball it is a
                // separate 51 px blob at x30-45 y96-100 that the real ROM
                // leaves black.
                self.effects.push((
                    held,
                    at,
                    HELD_BOMB_FRAMES,
                    false,
                    flash || seed,
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
/// The cannon barrel rides 16 forward and 24 up of the navi's panel centre
/// (measured off the real ROM).
const CANNON_BARREL_DX: i32 = 16; // provenance: peeked -- measured off the real ROM
const CANNON_BARREL_DY: i32 = 24; // provenance: peeked -- measured off the real ROM
                self.effects
                    .push((barrel, (mx + CANNON_BARREL_DX, my - CANNON_BARREL_DY), CANNON_FRAMES, false, false));
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
                // Chip-gated, not age-coincidence: the render window
                // ([VULCAN_FIREBALL_FIRST_VISIBLE, VULCAN_FIREBALL_LAST_VISIBLE])
                // alone would also fire for a Vulcan1/2/3 gun on any capture
                // running past VULCAN_FIREBALL_FIRST_VISIBLE, since the fireball
                // ages on its own clock. Canon's tail fire belongs to SuprVulc
                // only -- its gun alone outlives the window (Vulcan1/2/3 guns
                // are gone by VULCAN1_TIMING/VULCAN2_TIMING/VULCAN3_TIMING gun-ages, see vulcan_timing) --
                // so only SuprVulc spawns it.
                if chip.id == CHIP_SUPRVULC {
                    let fireball_tiles = spr::Assets::new(VULCAN_FIREBALL).gfx(0);
                    let fireball = DynamicSprite16::from_bytes(Size::S16x16, fireball_tiles)
                        .to_vram(PaletteVramSingle::new(&VULCAN_FIREBALL_PAL));
                    self.vulcan_fireball = Some((fireball, None));
                }
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
                    false,
                ));
            }
            CHIP_INVISIBL => {
                self.presentation = Some((chip, INVISIBL_PRESENTATION));
                // The name popup is a live-HUD presentation element (canon's builder
                // sub_801E95C, reference/bn6f asm/asm00_2.s:31328, sharing the banner's
                // 0x6016E00 tile region per the NOTE at asm00_2.s:31152): it shows while
                // the battle HUD is up and not past its teardown. The descriptor's
                // FLAG_HUD_LIVE (fixture.rs: canon mask 0x4497 = live vs 0x8084 = torn
                // down) is the only thing that says which canon state sits behind a
                // zero-enemy fixture -- the `popup` row (live) against the 43 chip rows
                // (afterdissolve_0x0c). Measured: zero popup-region pixels over 210
                // sterile-nozero + 150 real-ROM afterdissolve frames, while the popup
                // row's PAUSED-route canon shows it (frames 65..113) -- so draw it only
                // when the flag says live.
                // F12-cursor28 attribution (2026-09-14): this gate adds +22 cursor px
                // (HEAD 154367/914/170 -> 154389/936/170) while a pure-layout 64B
                // used-static pad alongside it moves cursor -28 (154389->154361/909)
                // with no logic change: layout-jitter class (cf. F30's +-21s), not a
                // code-path effect. Kept as-is.
                if self.fixture.map(|f| f.flag(fixture::FLAG_HUD_LIVE)).unwrap_or(false) {
                    self.popup = Some(NamePopup::new(chip.name()));
                }
            }
            CHIP_BARRIER | CHIP_BARR100 | CHIP_BARR200 => {
                self.presentation = Some((chip, BARRIER_PRESENTATION));
                // Same live-HUD gate as CHIP_INVISIBL above: the name popup
                // shows only while the battle HUD is up (canon mask 0x4497
                // live vs 0x8084 torn-down; builder sub_801E95C).
                if self.fixture.map(|f| f.flag(fixture::FLAG_HUD_LIVE)).unwrap_or(false) {
                    self.popup = Some(NamePopup::new(chip.name()));
                }
            }
            // AreaGrab needs per-panel ownership, which the field does not
            // track yet. The stand-in is nothing.
            // AreaGrab takes the enemy's front-most column, a row at a time
            // (sub_80E0754, asm31.s:85444, with the chip's first parameter
            // set); it is a presentation chip, so the fight holds first.
            CHIP_AREAGRAB => {
                self.presentation = Some((chip, AREAGRAB_PRESENTATION));
                // Same live-HUD gate as CHIP_INVISIBL above: the name popup
                // shows only while the battle HUD is up (canon mask 0x4497
                // live vs 0x8084 torn-down; builder sub_801E95C).
                if self.fixture.map(|f| f.flag(fixture::FLAG_HUD_LIVE)).unwrap_or(false) {
                    self.popup = Some(NamePopup::new(chip.name()));
                }
            }
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
                        panels.extend([(col + dx, row), (col + LONG_SWORD_FAR * dx, row)])
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
                    CHIP_LONGSWRD => (1, 0), // canon: byte_80EBAD8 arc row per subfamily (see above)
                    CHIP_SWORD => (2, 0), // canon: byte_80EBAD8 arc row per subfamily (see above)
                    CHIP_WIDEBLDE => (0, 5), // canon: byte_80EBAD8 arc row per subfamily (see above)
                    CHIP_LONGBLDE => (1, 5), // canon: byte_80EBAD8 arc row per subfamily (see above)
                    // Muramasa's row 0x2d: the same animation as LongBlde's
                    // in palette 6.
                    CHIP_MURAMASA => (1, 6), // canon: byte_80EBAD8 arc row per subfamily (see above)
                    _ => (0, 0),
                };
                let (fx, fy) = field::panel_centre(col + dx, row);
                // The elemental swords add their palette: the strike ORs
                // (subfamily - 0xb) into the spawn's Param3, which the
                // effect object adds to the sprite's palette
                // (asm31.s:109198-109206; sub_80E0568, asm31.s:85852).
                let arc_palette = match chip.id {
                    CHIP_FIRESWRD => 1, // canon: subfamily - 0xb ORed into Param3 (see above)
                    CHIP_AQUASWRD => 2, // canon: subfamily - 0xb ORed into Param3 (see above)
                    CHIP_ELECSWRD => 3, // canon: subfamily - 0xb ORed into Param3 (see above)
                    CHIP_BAMBSWRD => 4, // canon: subfamily - 0xb ORed into Param3 (see above)
                    _ => blade_palette,
                };
                let mut arc = spr::Player::new(spr::Assets::new(SWORD_ARC), arc_anim);
                arc.set_palette_add(arc_palette);
                self.effects
                    .push((arc, (fx, fy - SWORD_ARC_UP), SWORD_ARC_FRAMES[arc_anim], true, false));
                for enemy in self.enemies.iter_mut().filter(|e| e.is_targetable()) {
                    if panels.contains(&enemy.panel()) {
                        enemy.take_damage(chip.power);
                    }
                }
            }
            CHIP_MINIBOMB | CHIP_BLKBOMB | CHIP_BIGBOMB | CHIP_ENERGBOM | CHIP_MEGENBOM
            | CHIP_LILBOLR1 | CHIP_LILBOLR2 | CHIP_LILBOLR3
            | CHIP_FLSHBOM1 | CHIP_FLSHBOM2 | CHIP_FLSHBOM3
            | CHIP_GRASSEED | CHIP_ICESEED | CHIP_POISSEED
            | CHIP_BUGBOMB | CHIP_VDOLL => {
                let (mx, my) = field::panel_centre(col, row);
                let lilbolr = matches!(
                    chip.id,
                    CHIP_LILBOLR1 | CHIP_LILBOLR2 | CHIP_LILBOLR3
                );
                let seed = matches!(chip.id, CHIP_GRASSEED | CHIP_ICESEED | CHIP_POISSEED);
                // BugBomb and VDoll throw and LAND AND STAY rather than
                // bursting or laying a sheet.
                let rests = matches!(chip.id, CHIP_BUGBOMB | CHIP_VDOLL);
                // The slash arc rides above the front panel's centre; the offset is this
                // build's own, tuned to the panel art.
                const SWORD_ARC_UP: i32 = 0x10; // provenance: fitted -- this build's own arc height, tuned to the panel art
                // The thrown bomb lands about three panels out (see BOMB_FLIGHT).
                const BOMB_RANGE_PANELS: i32 = 3; // provenance: derived -- the bomb flies about three panels (see BOMB_FLIGHT)
                let target = ((col + BOMB_RANGE_PANELS * dx).clamp(1, field::COLS), row);
                // BlkBomb's thrown ball is its own sprite, not the bomb
                // sprite in another palette: a dark brown ball with a fuse
                // and a ground shadow, three parts in one frame. Identified
                // by taking its tiles out of OBJ VRAM mid-flight and finding
                // those exact bytes in byte_831FA84.spr, the only one of the
                // 97 sprite files that holds them.
                let flash = matches!(
                    chip.id,
                    CHIP_FLSHBOM1 | CHIP_FLSHBOM2 | CHIP_FLSHBOM3
                );
                let mut thrown = if chip.id == CHIP_VDOLL {
                    spr::Player::new(spr::Assets::new(VDOLL), VDOLL_ANIM)
                } else if chip.id == CHIP_BUGBOMB {
                    spr::Player::new(spr::Assets::new(POISSEED), BUG_THROWN_ANIM)
                } else if seed {
                    spr::Player::new(spr::Assets::new(POISSEED), SEED_THROWN_ANIM)
                } else if flash {
                    // The thrown ball is the same sprite as the held one.
                    spr::Player::new(spr::Assets::new(FLSHBOM), 0)
                } else if lilbolr {
                    // The thing LilBolr lobs is the LilBoiler VIRUS, not a
                    // bomb: its tiles are in virusBattleSprite_824EAF4.spr,
                    // which is why it looks nothing like one.
                    spr::Player::new(spr::Assets::new(LILBOILER), 0)
                } else if chip.id == CHIP_BLKBOMB {
                    spr::Player::new(spr::Assets::new(BLKBOMB), 0)
                } else {
                    spr::Player::new(spr::Assets::new(MINIBOMB), bomb_anim(chip.id, true))
                };
                if seed || chip.id == CHIP_BUGBOMB {
                    thrown.set_offsets_follow_shift(true);
                }
                thrown.set_palette_add(seed_or_bomb_palette(chip.id, true));
                self.bombs.push(Bomb {
                    player: thrown,
                    wide: chip.id == CHIP_BIGBOMB,
                    flight: if chip.id == CHIP_VDOLL {
                        VDOLL_FLIGHT + VDOLL_LANDING_LAG
                    } else if chip.id == CHIP_BUGBOMB {
                        BUG_FLIGHT
                    } else if chip.id == CHIP_BLKBOMB {
                        BLKBOMB_FLIGHT
                    } else {
                        BOMB_FLIGHT
                    },
                    gravity: if chip.id == CHIP_VDOLL {
                        VDOLL_GRAVITY
                    } else if chip.id == CHIP_BUGBOMB {
                        BUG_GRAVITY
                    } else if flash {
                        FLSHBOM_GRAVITY
                    } else if lilbolr {
                        LILBOLR_GRAVITY
                    } else if chip.id == CHIP_BLKBOMB {
                        BLKBOMB_GRAVITY
                    } else {
                        BOMB_GRAVITY
                    },
                    show_damage: lilbolr,
                    poison: seed,
                    rests,
                    // Param1 == 2 on the live thrown object for 0x37/0x38
                    // (0 for MiniBomb): the energy blast, not the burst.
                    ener: matches!(chip.id, CHIP_ENERGBOM | CHIP_MEGENBOM),
                    rest_snaps: matches!(chip.id, CHIP_BUGBOMB | CHIP_VDOLL),
                    rest_z: if chip.id == CHIP_VDOLL { VDOLL_REST_Z } else { BUG_REST_Z },
                    rest_poisons: chip.id == CHIP_VDOLL,
                    moves_before_falling: chip.id == CHIP_VDOLL || flash,
                    seed_palette: sheet_palette(chip.id),
                    x: (mx << Q16_SHIFT) + dx * BOMB_SPAWN_AHEAD,
                    y: my << Q16_SHIFT,
                    z: BOMB_SPAWN_UP,
                    vx: if chip.id == CHIP_VDOLL {
                        dx * VDOLL_VX
                    } else if chip.id == CHIP_BUGBOMB {
                        dx * BUG_VX
                    } else if lilbolr {
                        dx * LILBOLR_VX
                    } else if chip.id == CHIP_BLKBOMB {
                        dx * BLKBOMB_VX
                    } else {
                        dx * BOMB_VX
                    },
                    vz: if chip.id == CHIP_VDOLL {
                        VDOLL_VZ
                    } else if chip.id == CHIP_BUGBOMB {
                        BUG_VZ
                    } else if flash {
                        FLSHBOM_VZ
                    } else if lilbolr {
                        LILBOLR_VZ
                    } else if chip.id == CHIP_BLKBOMB {
                        BLKBOMB_VZ
                    } else {
                        BOMB_VZ
                    },
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
                // asm31.s:109878-109892). Each extra shot lengthens the
                // attack by ~11 frames (see vulcan_shots); the delay staggers
                // them 10 frames apart.
                const VULCAN_SHOT_DELAY_STEP: u8 = 0xa; // provenance: peeked -- staggers the stream so each extra shot lengthens the attack ~11 frames (see vulcan_shots)
                for i in 0..vulcan_shots(chip.id) as usize {
                    self.shots.push(Shot::vulcan(
                        spr::Assets::new(SHOTFX),
                        fc,
                        fr,
                        dx,
                        chip.power,
                        FAN[i % FAN.len()],
                        (i as u8) * VULCAN_SHOT_DELAY_STEP,
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
        //
        // AUDIT wave 3d "bg3-merge": call order here is hardware BG index
        // (agb assigns 0, 1, 2... in `.show()` call order each frame) --
        // `filler_bg`, then backdrop, then field, then the shared
        // HUD/window background, landing on hardware BG0 (unused, matching
        // canon's own)/BG1 (backdrop)/BG2 (field)/BG3 (HUD+window+RESULT)
        // exactly where canon's own BGxCNT peeks put them. `filler_bg` is
        // skipped while the RESULT window is up: backdrop + field + hud_bg
        // + `self.shown`'s own background is already 4, agb's hardware cap,
        // and a 5th here panics -- see `filler_bg`'s own doc for why this
        // measured safe to keep everywhere else.
        if self.shown.is_none() {
            self.filler_bg.show(frame);
        }
        let mut backdrop_id = None;
        let mut hud_id = None;
        if let Some(backdrop) = self.backdrop.as_ref() {
            backdrop_id = Some(backdrop.show(frame));
        }
        let bg_id = self.bg.show(frame);
        if let Some(hud_bg) = self.hud_bg.as_ref() {
            hud_id = Some(hud_bg.show(frame));
        }
        // The chip-name popup is OAM entries 0 upward on the real ROM, so it
        // goes in before anything else the fight draws and stands over all of
        // it.
        if let Some(popup) = self.popup.as_ref() {
            popup.show(frame);
        }
        if let Some(banner) = self.banner.as_ref() {
            banner.show(frame);
        }
        // Whichever navi is fading -- the deleted player out, an arriving
        // enemy in -- pixelates and thins over the field; the intro's screen
        // fade darkens everything until the field is revealed.
        let window_id = self.shown.as_ref().map(|window| window.show(frame));
        // The RESULT window's corner badge: the chip window's regular-chip
        // mark, hung as OAM entry 0 at the window's top-left. Read off a live
        // results screen, where it is a 16x16 at (37,21) in OBJ bank 11.
        // ENTRY ANIMATION (TODO F8, measured on the field row's own canon
        // capture): canon's mark does not sit still -- it enters wrapped from
        // the right edge, one frame at attr1 x=509 (a 9-bit coordinate, so
        // the sprite's left 13 pixels draw at x 0..12), then x=13, x=29, and
        // rests at 37 from the next frame on: watch-write on the shadow OAM
        // (dword_3002180) shows x = ([r5+6]*8+13) & 0x1ff with the counter
        // ramping +2/frame and clamping at 3 (the enqueue is sub_802CA5C,
        // asm03_0.s:13225; the ramp lives in the RESULT object's own state
        // machine). The wrapped frame is the slide's own end (j=-2), so the
        // mark rides the slide counter (`results::mark_x_at`), settling at 37
        // with the window, on every path.
        if let Some(mark) = self.results_mark.as_ref() {
            if let Some(window) = self.shown.as_ref() {
                let x = results::mark_x_at(window.slide_x());
                Object::new(mark.clone())
                    .set_priority(Priority::P0)
                    .set_pos((x, RESULTS_MARK_AT.1))
                    .show(frame);
            }
        }
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
            // FULL WHITE, held, not a ramp: the real ROM is 100% white through
            // its 71st frame and 0% on the 72nd. A demo build keeps the old
            // black ramp, so its fixtures' offsets still hold; a fixture's
            // FLAG_SKIP_INTRO reproduces the same choice at runtime.
            if self.skip_intro() {
                let amount = Num::from_raw((self.intro_fade as u8).div_ceil(2)); // canon: INTRO_SKIP_FADE counts half blend steps
                frame
                    .blend()
                    .darken(amount.min(Num::from_raw(16))) // canon: agb full-weight blend (16)
                    .enable_background(bg_id)
                    .enable_object();
            } else {
                // Pure white while the hold lasts, then RAMPED OFF over the
                // last INTRO_RAMP frames. Measured: the real ROM is 100% white
                // through frame 70 and then comes down 92, 85, 77, 70, 62, 56,
                // 48 to its settled level at 86 -- sixteen frames of ramp, not
                // the instant cut this first had.
                let left = self.intro_fade.min(INTRO_RAMP);
                let amount = (16 * left / INTRO_RAMP) as u8; // canon: agb full-weight blend (16)
                let mut blend = frame.blend();
                let mut fade = blend.brighten(Num::from_raw(amount));
                fade.enable_background(bg_id).enable_object();
                // EVERY layer, not just the field's: the backdrop and the HUD
                // are their own backgrounds and stayed coloured underneath,
                // which is why the "white" measured 70 out of 100.
                if let Some(id) = backdrop_id {
                    fade.enable_background(id);
                }
                if let Some(id) = hud_id {
                    fade.enable_background(id);
                }
            }
        } else if let Some((mosaic, alpha)) = core::iter::once(&self.megaman)
            .chain(self.enemies.iter())
            .find_map(|a| a.fade())
        {
            frame.mosaic().set_object(mosaic, mosaic);
            frame
                .blend()
                .object_transparency(Num::from_raw(alpha), Num::from_raw(16 - alpha)) // canon: agb full-weight blend (16)
                .enable_background(bg_id);
        }
        // The emotion window: two objects, (0,18) 32x16 tile 0x3b4 and
        // (32,18) 16x16 tile 0x3bc, palette 12, priority 2 -- exactly the
        // words canon's draw routine sub_801CDEC hardcodes
        // (asm00_2.s:27554-27583). It is battle-HUD ELEMENT 14, dispatched
        // every frame while bit 14 of the element mask dword_20352C0 is set
        // (sub_801BEE0, asm00_2.s:25540-25563; updater sub_801CADC at
        // asm00_2.s:25577, draw at asm00_2.s:25627).
        //
        // TODO F27b (2026-09-13): it does NOT go with the last enemy. Canon
        // clears bit 14 in ONE teardown with the rest of the fight's HUD, on
        // the frame the banner sequencer enters its RESULT countdown 0x0C:
        // sub_80081A4 (asm00_1.s:10617-10621) calls sub_801BED6(0xE4C53),
        // and 0xE4C53 & 0x4497 = 0x4413 -- elements 0, 1, 4, 10 and 14 at
        // once. Measured on the real ROM (PAUSED, enemy HP forced to 0,
        // Start@10): the sequencer dword_203CA70 goes 0x08 -> 0x0C at frame
        // 47, the mask goes 0x4497 -> 0x0084 at frame 48 (--watch-write
        // 0x20352C0:4 names the store: at=0x0801BEDC, lr=0x080081B9), bit 15
        // is set back a moment later by the ENEMY DELETED banner going up
        // (sub_801E792's sub_801BECC(1<<15), asm00_2.s:31055-31112) and the
        // banner runs 49..106. So the window survives the enemy's death and
        // its whole dissolve -- 47 frames of it here -- and goes with the
        // end sequence, one frame before the banner. `over` is this build's
        // same event (it arms that banner on the frame it fires), so the
        // teardown hangs off it in `update`.
        if self.hud_live && self.shown.is_none() && self.fade_out == 0 {
            // Canon's element-14 draw adds the HUD's shared object X
            // displacement (eStruct2035280+0x12) to its two OAM words; see
            // `Emotion::show` and `Custom::hud_obj_x` for the measurement.
            self.emotion
                .show(frame, self.custom.as_ref().map_or(0, |c| c.hud_obj_x()));
        }
        // The chip at the front of the hand hangs over the navi as a 16x16
        // object: read out of a live battle's OAM at (59,52) with the navi on
        // the middle panel of its row, which is that panel's centre one left
        // and fifty-six up. Its four tiles are the chip's own icon. Not drawn
        // while the chip window is up, which covers this half of the screen.
        //
        // NOT IN THE STERILE ARENA. The object belongs to the chip window
        // closing, not to the hand's contents: the real captures poke a chip
        // straight into the hand slot and show no icon at all, so drawing one
        // there costs every chip comparison a constant 256 px.
        // IT GOES WITH THE PRESS, NOT THE RELEASE, and it goes one frame
        // before the chip does. Measured with A HELD for five frames, so the
        // release cannot be involved: the real ROM's icon is present through
        // the press's frame + 1 and gone from + 2, this build's was gone from
        // + 3, and the navi's pose changes on + 4 on BOTH sides. So the attack
        // is aligned and the real ROM simply takes the chip out of the hand a
        // frame before the use fires. `chip_use_in` reads 1 on that frame.
        // (The earlier note here said the real ROM dropped it "on the frame
        // the button comes UP" and that nothing could drop it sooner. The
        // button never came up.)
        if let (None, Some(palette)) = (&self.custom, self.hand_icon_palette.as_ref()) {
            // F33b: canon's queued-chip ICON is battle-HUD element 1
            // (updater sub_801BFF8 asm00_2.s:25655 -> sub_801C002(0), draw
            // sub_801C078 :25729 -> sub_801C082(0), the six slots at
            // dword_20352E0) and is torn down with elements 0/4/10/14 by
            // sub_80081A4 (asm00_1.s:10617-10621); its NAME is element 6
            // (draw sub_801C6EE :26619, no updater) and is NOT. Ours tied
            // both to the hand, so a fixture that carries canon's queued
            // chip in order to draw the name also drew an icon canon had
            // torn down -- measured at exactly 256 px a frame, a 16x16 OBJ.
            // F33b (icon is element 1, torn down with 0/4/10/14) plus F37b:
            // canon's draw-mask bit 1 stays 0 after the OK press commits the
            // picks to the sent-chip data (0x4085 open, 0x4495 after close),
            // so no icon ever comes back for the picked chip -- while this
            // build moved the picks into the hand and drew one. Suppressed
            // once a window has closed (`name_suppressed` rides the same
            // close); rows that never close (buster/chip-use) are untouched.
            if let Some(chip) = self.hand.get(self.hand_at).filter(|_| {
                self.chip_use_in != 1 && self.hud_live && !self.name_suppressed
            }) {
                let (mc, mr) = self.megaman.panel();
                let (px, py) = field::panel_centre(mc, mr);
                let sprite = DynamicSprite16::from_bytes(Size::S16x16, chip.icon_bytes())
                    .to_vram(palette.clone());
                Object::new(sprite)
                    .set_priority(Priority::P2)
                    .set_pos((px + HAND_ICON_AT.0, py + HAND_ICON_AT.1))
                    .show(frame);
            }
        }
        // The summoned boiler's HP figure goes ABOVE the navi. Drawn with the
        // rest of the bomb -- which comes after the actors, so under them --
        // the navi's arm cut the digits on the two frames the figure passes
        // behind him, and the real ROM's is whole there.
        for b in self.bombs.iter().filter(|b| b.show_damage) {
            let (x, y) = b.position();
            // LilBolr carries a figure under the thing it lobs, in the same
            // number objects the HP counters use. Measured on the real ROM:
            // two 32x16 objects at (84,64) and (116,64) on the attack's frame
            // 19, where the boiler's centre is (93,35). It shows with the
            // enemy deleted, so it belongs to the projectile rather than to a
            // hit.
            // It is NOT this chip's damage: it reads 40 for all three
            // LilBolrs, whose powers are 100, 140 and 180. It is the summoned
            // LilBoiler virus's own HP, which fits the thrown object being a
            // virus sprite -- so it is a constant, not b.damage, and drawing
            // b.damage there scored worse (404 px/frame against 352).
            self.hud
                .draw_number(frame, BOILER_HP, x + BOILER_HP_RIGHT, y + BOILER_HP_DOWN);
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
        // SuprVulc's parked muzzle fire, over the gun that shed it.
        if let Some((sprite, Some(age))) = &self.vulcan_fireball {
            if (*age >= VULCAN_FIREBALL_FIRST_VISIBLE
                && *age <= VULCAN_FIREBALL_LAST_VISIBLE)
            {
                Object::new(sprite.clone())
                    .set_priority(Priority::P2)
                    .set_pos((vulcan_fireball_x(*age), VULCAN_FIREBALL_Y))
                    .show(frame);
            }
        }
        // AreaGrab's steal orbs, over the field they are about to take.
        // Culled until the pair's top is inside (canon writes no OAM above).
        // Lowest first: canon's OAM carries the orbs bottom-to-top (OAM watch
        // at captures 66/70/74: y 4/-20, 36/12/-12, 68/44/20), so in the
        // waist overlap where consecutive rings touch, the lower ring wins
        // the same-priority tie. Spawn order is top-down and would show the
        // upper ring instead (row k=60..75, x 134..145).
        let mut areagrab_order: Vec<usize> = (0..self.areagrab_orbs.len()).collect();
        areagrab_order.sort_by_key(|&i| core::cmp::Reverse(self.areagrab_orbs[i].position().1));
        for i in areagrab_order {
            let orb = &self.areagrab_orbs[i];
            let (x, y) = orb.position();
            if y <= AREAGRAB_ORB_CULL_TOP || y >= AREAGRAB_ORB_CULL_BOTTOM {
                continue;
            }
            for part in orb.player.parts().iter().rev() {
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
                && (*age - STEP_GHOST2_FIRST) % STEP_RING_PERIOD < STEP_BLINK_SHOWN
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
            if *age <= STEP_GHOST_LAST && *age >= STEP_GHOST_FIRST && (*age - STEP_GHOST_FIRST) % STEP_RING_PERIOD < STEP_BLINK_SHOWN {
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
        for (p, (x, y), _, _, no_shadow) in self.effects.iter().rev() {
            for (i, part) in p.parts().iter().enumerate().rev() {
                // A sprite's first part is its ground shadow, and a HELD
                // object's is not drawn.
                if *no_shadow && i == 0 {
                    continue;
                }
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
        // THE CHARGE GLOW GOES OVER THE NAVI. The real ROM's OAM has its four
        // 32x32 quadrants at entries 4-7 and the navi's at 8-10, so its sparks
        // cross his body; drawn under him they are cut wherever they would.
        if self.glow_state != 0 && !self.megaman.is_defeated() {
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
        // A seed's pod sorts above the navi, ahead of his body and its
        // own shadow alike: the real ROM's OAM at the pod stage reads pod
        // ball, navi body, seed shadow, navi shadow (chip-poisseed k=9:
        // ball OAM5-6, body OAM7-10, shadow OAM11, navi shadow OAM12; the
        // landing frame reads the same way, ball OAM0-1 over shadow OAM5,
        // so the ball covers the shadow where they overlap). Gated on the
        // seed family: every other thrown object keeps its ball below the
        // navi (chip-minibomb reads 0 that way).
        // provenance: peeked -- bilateral OAM watch at k9-14 and k47.
        for b in &self.bombs {
            if !b.poison {
                continue;
            }
            let (x, y) = b.position();
            for part in b.player.parts().iter().skip(1).rev() {
                Object::new(part.sprite.clone())
                    .set_priority(Priority::P2)
                    .set_pos((x + part.x, y + part.y))
                    .set_hflip(part.hflip)
                    .set_vflip(part.vflip)
                    .show(frame);
            }
        }
        // Every field object rides the chip window's camera pan (see
        // Actor::show): canon holds MegaMan 15 px lower with the window
        // up (F37's OAM watch: y141 open vs y126 closed), and
        // `field_slide` IS that camera in half-pixels. Canon's object draw
        // reads the SIGNED camera with an arithmetic shift (floor,
        // asm00_2.s:25977-25984: asr then neg), so the object offset is the
        // floor of the signed camera -- the BG scroll's own div_euclid
        // form, negated back for objects. Plain truncating halving runs
        // ceil(1.5k) against canon's floor(1.5k) (F37e OAM census), 1 px
        // apart on every odd slide step; this matches canon on all ten.
        // (Parentheses are load-bearing: `-x.div_euclid(2)` parses as
        // `-(x.div_euclid(2))`, the divide-then-negate that rounds the
        // wrong way -- see the scroll site's own note.)
        let cam_dy = -((-(self.field_slide as i32)).div_euclid(FIELD_SUBPX as i32)); // provenance: derived -- canon's asr+neg object-draw shift (asm00_2.s:25977-25984) via FIELD_SLIDE/FIELD_SUBPX
        if !self.megaman.is_defeated() {
            let bubble = self.bubble.as_ref();
            let (mc, mr) = self.megaman.panel();
            let (bx, by) = field::panel_centre(mc, mr);
            // Two pixels forward of the origin on the real ROM.
            const CURSOR_FORWARD_PX: i32 = 2; // provenance: peeked -- two pixels forward of the origin on the real ROM
            let bx = bx + CURSOR_FORWARD_PX * self.megaman.facing_dx();
            self.megaman.show_with_underlay(frame, cam_dy, |frame| {
                // The navi's underlay carries only his bubble here. A thrown
                // object's GROUND SHADOW used to be drawn in this slot too
                // (between his body and his own shadow, entries 14/15 on the
                // real ROM) -- but the real ROM's OAM has the BALL itself at
                // entry 0, ahead of the navi AND its own shadow, so where the
                // two overlap on the landing frame the ball covers the shadow
                // (chip-minibomb k=47: 10 blue px over the shadow's opaque
                // core). Emitted here the shadow took the lower OAM index and
                // covered the ball, so the shadows are drawn after the balls
                // below instead -- they never touch his own shadow (opposite
                // halves of the arena), so that documented order is unchanged
                // where it is visible.
                if let Some(bubble) = bubble {
                    for part in bubble.parts().iter().rev() {
                        Object::new(part.sprite.clone())
                            .set_priority(Priority::P2)
                            .set_pos((bx + part.x, by + part.y + cam_dy))
                            .set_hflip(part.hflip)
                            .set_vflip(part.vflip)
                            .show(frame);
                    }
                }
                // A seed's pod shadow sorts between the navi's body and
                // his own shadow: the real ROM's OAM at the pod stage
                // reads pod ball, navi body, seed shadow, navi shadow
                // (chip-poisseed k=9: ball OAM5-6, body OAM7-10, shadow
                // OAM11, navi shadow OAM12), so the shadow covers his feet
                // where they overlap and his body covers it. Gated on the
                // seed family: every other thrown object keeps its shadow
                // below the navi (chip-minibomb's ball OAM5 and shadow
                // OAM9/10 sort below him). The after-balls loop below
                // draws this shadow a second time, underneath everything:
                // same pixels at the same spot, so it is fully covered
                // here and costs nothing, and it preserves the old picture
                // on the frames the navi himself is not drawn (defeated,
                // blink), where this slot never runs.
                // provenance: peeked -- bilateral OAM watch at k9-14.
                for b in &self.bombs {
                    if !b.poison {
                        continue;
                    }
                    let (gx, gy) = b.ground();
                    if let Some(part) = b.player.parts().first() {
                        Object::new(part.sprite.clone())
                            .set_priority(Priority::P2)
                            .set_pos((gx + part.x, gy + part.y))
                            .set_hflip(part.hflip)
                            .set_vflip(part.vflip)
                            .show(frame);
                    }
                }
            });

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
            // Level with the panel's centre, not six below it: measured
            // against the capture, whose Mettaur's readout occupies rows
            // 112-119 where this build's sat at 118-125.
            // The readout is a field object, so it rides the chip window's
            // own camera pan with everything else on the field: canon holds
            // every field object 15 px lower with the window up (F37's OAM
            // watch on the cursor capture: MegaMan y141 open vs y126 closed,
            // Mettaur and HP box the same 15). `field_slide` IS that camera
            // in half-pixels (see FIELD_SLIDE), so the signed-floor halving
            // below (canon's asr+neg object-draw shift, asm00_2.s:25977-25984)
            // tracks it through the ten slide calls both ways, settled or
            // ramping -- truncating halving runs 1 px apart on odd steps.
            let cam_dy = -((-(self.field_slide as i32)).div_euclid(FIELD_SUBPX as i32)); // provenance: derived -- canon's asr+neg object-draw shift (asm00_2.s:25977-25984) via FIELD_SLIDE/FIELD_SUBPX
            self.hud.draw_number_in(
                frame,
                hp,
                px + self.hud.width(hp) / 2, // unnamed: half the readout width, to centre it
                py + cam_dy,
                counter.set(),
            );
        }
        for enemy in self.enemies.iter().filter(|e| e.is_present()) {
            enemy.show(frame, cam_dy);
        }
        if let Some(cursor) = self.gunner_ctl.cursor() {
            cursor.show(frame);
        }
        for imp in &self.impacts {
            imp.show(frame);
        }
        for b in &self.bombs {
            // Seeds draw their ball above, ahead of the navi block.
            if b.poison {
                continue;
            }
            let (x, y) = b.position();
            // LilBolr carries its damage under the thing it lobs, in the same
            // number objects the HP counters use. Measured on the real ROM:
            // two 32x16 objects at (84,64) and (116,64) on the attack's frame
            // 19, where the boiler's centre is (93,35). It shows with the
            // enemy deleted, so it belongs to the projectile rather than to a
            // hit.
            // The figure the real ROM rides under the boiler is NOT this
            // chip's damage: it reads 40 for all three LilBolrs, whose powers
            // are 100, 140 and 180. It is the summoned LilBoiler virus's own
            // HP, which fits the thrown object being a virus sprite -- so it
            // is a constant, not b.damage, and drawing b.damage there scored
            // worse (404 px/frame against 352).
            // The frame's first part is the shadow (sprite_hasShadow) and it
            // is NOT drawn here: it goes on the ground after the balls, so
            // the ball keeps the lower OAM index and covers the shadow where
            // the two overlap on the landing frame, the way the real ROM's
            // OAM does (ball first, shadow later).
            for part in b.player.parts().iter().skip(1).rev() {
                let (px, py) = (x, y);
                Object::new(part.sprite.clone())
                    .set_priority(Priority::P2)
                    .set_pos((px + part.x, py + part.y))
                    .set_hflip(part.hflip)
                    .set_vflip(part.vflip)
                    .show(frame);
            }
        }
        // A thrown object's GROUND SHADOW, after the balls: the real ROM's
        // OAM carries the ball ahead of the navi and the shadow behind him,
        // so the shadow must sort below the ball (provenance: peeked -- OAM
        // dump of the canon chip-minibomb capture, ball entry 0, shadow
        // entry 4, sub_80C5DBC's object, asm31.s:29657). A seed's shadow
        // is ALSO drawn in the navi's underlay slot above, between his
        // body and his own shadow where the real ROM sorts it; this copy
        // underneath is fully covered there and only shows on the frames
        // he is not drawn.
        for b in &self.bombs {
            let (gx, gy) = b.ground();
            if let Some(part) = b.player.parts().first() {
                Object::new(part.sprite.clone())
                    .set_priority(Priority::P2)
                    .set_pos((gx + part.x, gy + part.y))
                    .set_hflip(part.hflip)
                    .set_vflip(part.vflip)
                    .show(frame);
            }
        }

        // NOT DRAWN: the player's own HP. The real ROM puts it in the tile
        // HP box on BG3 (hudtiles.rs), not in object text -- this build drew
        // both, so a full battle showed the number twice, once in the box and
        // once under it, and the sterile arena showed a number where the real
        // capture has none at all because its BG layers are stripped.
    }
}
