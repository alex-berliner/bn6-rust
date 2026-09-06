//! The state of one battle and the frame logic that runs it: the intro
//! fades the screen in, the fight runs until a side is deleted, and the
//! results window closes with a fade-out. It is all rebuilt for the next
//! battle; the field, HUD and results assets are borrowed.

use agb::display::GraphicsFrame;
use agb::display::Priority;
use agb::display::object::Object;
use agb::display::tiled::RegularBackground;
use agb::fixnum::Num;
use agb::input::{Button, ButtonController};
use alloc::vec::Vec;

use crate::actor::{self, Actor, Update};
use crate::chips::{Chip, Chips};
use crate::custom::{self, Custom, CustomAssets, Offer};
use crate::deck::{Deck, Rng, FOLDER_SIZE};
use crate::field::{self, Field, Panels};
use crate::hud::Hud;
use crate::results::{self, Results};
use crate::shot::Shot;
use crate::{
    CHARGE, COLONEL, CURSOR, DELETE, GUNNER, IMPACT, MEGAMAN, METTAUR, PROTOMAN, SHOTFX, WAVE,
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
// the arm position each frame; this offset stands in for that.
const GLOW_OFFSET: (i32, i32) = (16, -14);
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
const CHIP_CANNON: u16 = 1;
const CHIP_HICANNON: u16 = 2;
const CHIP_AIRSHOT: u16 = 4;
const CHIP_VULCAN: u16 = 5;
const CHIP_MINIBOMB: u16 = 54;
const CHIP_RECOV10: u16 = 154;
const CHIP_RECOV30: u16 = 155;
const CHIP_AREAGRAB: u16 = 163;
const CHIP_INVISIBL: u16 = 177;
const CHIP_BARRIER: u16 = 178;
const SWORD: actor::AttackSpec = actor::AttackSpec {
    windup: None,
    anim: 5,
    frames: 0x15,
    strike_at: 9,
    recover: 5,
};
const THROW: actor::AttackSpec = actor::AttackSpec {
    windup: None,
    anim: 6,
    frames: 0x15,
    strike_at: 9,
    recover: 5,
};
/// Cannon and HiCannon (attack family 0x14, sub_80EBC28): the navi takes
/// animation 8 and the projectile is spawned off the front panel when the
/// frame counter reads 0xf, the pose exiting once it reads 0x1d
/// (asm31.s:109454, 109532, 109549). Both subfamilies are under 4, so the
/// illusions at counter 8 do not apply (asm31.s:109480).
const CANNON: actor::AttackSpec = actor::AttackSpec {
    windup: None,
    anim: 8,
    frames: 0x1d,
    strike_at: 0xf,
    recover: 0,
};
/// Vulcan1 (attack family 0x17, sub_80EBF10): takes animation 0xa as a
/// wind-up, then animation 0xd and fires until its shots are out
/// (sub_80EBF30, sub_80EBF6E; asm31.s:109844, 109887). The three shots are
/// released 0xa frames apart, so they are modelled here as one strike that
/// spawns a staggered volley in chip_strike.
const VULCAN: actor::AttackSpec = actor::AttackSpec {
    windup: Some((0xa, 0x10)),
    anim: 0xd,
    frames: 0x1e,
    strike_at: 1,
    recover: 0,
};
/// AirShot (attack family 0x21, sub_80EC884): takes animation 0x9, plays
/// the gust sound 0xaf and spawns its shot when the frame counter reads 0x5,
/// the pose exiting once it reads 0xa, then a 0xa-frame recovery
/// (sub_80EC8A0, sub_80EC90E; asm31.s:111072, 111094, 111112). The shot it
/// spawns is the same type-3 object as the cannon's (sub_80C4FFE ->
/// t3_0x0_80C4E58), so it is the travelling buster shot at chip power.
const AIRSHOT: actor::AttackSpec = actor::AttackSpec {
    windup: None,
    anim: 0x9,
    frames: 0xa,
    strike_at: 0x5,
    recover: 0xa,
};
/// Recov10 and Recov30 heal their names (byte_80EC870, asm31.s:111044).
const RECOV_HP: [u16; 2] = [10, 30];
/// Invisibl's timer is its first parameter, 0x68 (ChipDataArr.s:5490).
const INVISIBL_FRAMES: u16 = 0x68;
/// Barrier's HP for type 1 is 10 (byte_8020B2C, dat01.s:189).
const BARRIER_HP: u16 = 10;
/// MiniBomb lands three panels ahead, as in every game; its arc and flight
/// time were not traced (the spawn is at the navi's height plus 0x30), so
/// the flight is a stand-in: 40 frames along a parabola 48 pixels high.
const BOMB_RANGE: i32 = 3;
const BOMB_FLIGHT: u8 = 40;
const BOMB_HEIGHT: i32 = 0x30;
/// The blast's animation 0 in sprite 0x26 (the Gunner's impact) runs its
/// five frames; held about as long as that takes.
const BLAST_FRAMES: u8 = 30;

/// A thrown MiniBomb in flight, drawn with the buster shot's sprite for
/// want of the bomb's own, which was not identified.
struct Bomb {
    player: spr::Player,
    from: (i32, i32),
    target: (i32, i32),
    damage: u16,
    ticks: u8,
}

impl Bomb {
    fn position(&self) -> (i32, i32) {
        let (x0, y0) = field::panel_centre(self.from.0, self.from.1);
        let (x1, y1) = field::panel_centre(self.target.0, self.target.1);
        let t = self.ticks as i32;
        let n = BOMB_FLIGHT as i32;
        let lift = BOMB_HEIGHT * 4 * t * (n - t) / (n * n);
        (x0 + (x1 - x0) * t / n, y0 + (y1 - y0) * t / n - lift)
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
    /// The picks from the last chip select, in order (byte_20349C0), and
    /// how many have been used (getCurChipInBattleHand_8010004 reads
    /// hand + 2 + 2 * count; sub_800FC7C advances the count).
    hand: alloc::vec::Vec<Chip>,
    hand_at: usize,
    /// The chip whose attack pose is playing, for its strike.
    chip_in_use: Option<Chip>,
    bombs: Vec<Bomb>,
    panels: Panels,
    bg: RegularBackground,
    megaman: Actor,
    /// Sizes differ between debug and release builds: a debug build fights
    /// the Mettaur alone so the hand and chips can be tried without the
    /// bosses, while the release keeps the game's lineup. Everything here
    /// reads whatever length it is.
    enemies: Vec<Actor>,
    ais: Vec<ai::Ai>,
    gunner_ctl: gunner::Gunner,
    impacts: Vec<gunner::Impact>,
    effects: Vec<(spr::Player, (i32, i32), u8)>,
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
}

/// What a demo build fields: the chip ids to preload straight into the hand
/// (A fires the first at once), and the lone enemy to place so that chip
/// connects on the first press. Enemy-only demos leave the hand empty and
/// just field their navi. None when no demo feature is on.
#[cfg(any(
    feature = "demo-buster",
    feature = "demo-sword",
    feature = "demo-minibomb",
    feature = "demo-cannon",
    feature = "demo-vulcan",
    feature = "demo-airshot",
    feature = "demo-recovery",
    feature = "demo-mettaur",
    feature = "demo-gunner",
    feature = "demo-protoman",
    feature = "demo-colonel",
    feature = "demo-results",
))]
fn demo() -> (alloc::vec::Vec<u16>, i32, Option<(spr::Assets, i32, i32, ai::Style, u16)>) {
    let mut hand = alloc::vec::Vec::new();
    // MegaMan is placed at (3,2) facing right so his front panel is (4,2), the
    // first column of the enemy half: a sword lands there, a cannon/vulcan/
    // airshot shot spawns there and travels on, and LongSwrd reaches it and
    // the panel behind it. WideSwrd sweeps that whole column. MiniBomb lands
    // three ahead of (3,2), so its target sits at (6,2). The target carries a
    // big HP so a chip demo can land several hits without the fight ending;
    // demo-results uses the real 40 so one hit brings the window up.
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
            #[cfg(any(
                feature = "demo-buster",
                feature = "demo-sword",
                feature = "demo-minibomb",
                feature = "demo-cannon",
                feature = "demo-vulcan",
                feature = "demo-airshot",
                feature = "demo-recovery",
                feature = "demo-mettaur",
                feature = "demo-gunner",
                feature = "demo-protoman",
                feature = "demo-colonel",
                feature = "demo-results",
            ))]
            {
                demo()
            }
            #[cfg(not(any(
                feature = "demo-buster",
                feature = "demo-sword",
                feature = "demo-minibomb",
                feature = "demo-cannon",
                feature = "demo-vulcan",
                feature = "demo-airshot",
                feature = "demo-recovery",
                feature = "demo-mettaur",
                feature = "demo-gunner",
                feature = "demo-protoman",
                feature = "demo-colonel",
                feature = "demo-results",
            )))]
            {
                (alloc::vec::Vec::new(), 2, None)
            }
        };
        let megaman = Actor::new(spr::Assets::new(MEGAMAN), demo_col, 2, false, player);
        // Whether a virus dies with the navi's 0x5a-frame blink was not checked.
        // A debug build fights just the Mettaur, to exercise the hand, chips
        // and deletion without the bosses; the release build keeps the game's
        // lineup. A demo build fields its one featured enemy instead.
        let mut enemies: Vec<Actor> = if let Some((assets, col, row, _style, hp)) = demo_enemy {
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
        let effects: Vec<(spr::Player, (i32, i32), u8)> = Vec::new();
        let ais: Vec<ai::Ai> = if let Some((_, _, _, style, _)) = demo_enemy {
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
            bombs: Vec::new(),
            panels,
            bg,
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
        }
    }

    /// Run one frame of battle logic. Returns true once the results window
    /// has been dismissed and its fade-out has completed, so the caller can
    /// start the next battle.
    pub fn update(&mut self, input: &ButtonController, gfx: &Graphics) -> bool {
        // Once either side is deleted the fight is decided: the game goes to
        // its results, which are not built yet, so here the field just holds.
        let over = self.megaman.is_defeated() || self.enemies.iter().all(|e| e.is_defeated());

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
        let paused = over || self.gauge_pause > 0 || self.custom.is_some() || intro;
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
                    .fold(0, |m, e| m | e.occupancy());
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
            // the player and rolls on. Off the field, both are spent.
            let mut spent = !self.shots[i].update();
            if !spent && self.shots[i].just_arrived() {
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

        match self.megaman.update() {
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
                    .push((spr::Player::new(spr::Assets::new(DELETE), 0), at, 90));
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
                let blocked = all_held & !held[i];
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
                        .push((spr::Player::new(spr::Assets::new(DELETE), 0), at, 90));
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

        self.effects.retain_mut(|(p, _, ticks)| {
            p.update();
            *ticks -= 1;
            *ticks > 0
        });
        // A bomb that lands bursts on its panel (sub_80C5DBC's fuse of zero:
        // the blast, setCollisionRegion(1), then sprite 0x26's animation 0).
        let mut landed = Vec::new();
        self.bombs.retain_mut(|b| {
            b.player.update();
            b.ticks += 1;
            if b.ticks >= BOMB_FLIGHT {
                landed.push((b.target, b.damage));
                false
            } else {
                true
            }
        });
        for ((col, row), damage) in landed {
            for enemy in self.enemies.iter_mut().filter(|e| e.is_targetable()) {
                if enemy.panel() == (col, row) {
                    enemy.take_damage(damage);
                }
            }
            self.effects.push((
                spr::Player::new(spr::Assets::new(IMPACT), 0),
                field::panel_centre(col, row),
                BLAST_FRAMES,
            ));
        }

        let occupied = self
            .enemies
            .iter()
            .filter(|e| e.is_targetable())
            .fold(self.megaman.occupancy(), |m, e| m | e.occupancy());
        self.panels.update(occupied);
        for (col, row) in field::panels_in(self.panels.take_dirty()) {
            match self.panels.flashing(col, row) {
                Some(which) => self.field.draw_highlight(&mut self.bg, col, row, which),
                None => {
                    self.field
                        .draw_panel(&mut self.bg, col, row, self.panels.animation(col, row))
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
            CHIP_SWORD | CHIP_WIDESWRD | CHIP_LONGSWRD => {
                self.chip_in_use = Some(chip);
                self.megaman.attack(SWORD);
            }
            CHIP_MINIBOMB => {
                self.chip_in_use = Some(chip);
                self.megaman.attack(THROW);
            }
            CHIP_CANNON | CHIP_HICANNON => {
                self.chip_in_use = Some(chip);
                self.megaman.attack(CANNON);
            }
            CHIP_VULCAN => {
                self.chip_in_use = Some(chip);
                self.megaman.attack(VULCAN);
            }
            CHIP_AIRSHOT => {
                self.chip_in_use = Some(chip);
                self.megaman.attack(AIRSHOT);
            }
            CHIP_RECOV10 => self.megaman.heal(RECOV_HP[0]),
            CHIP_RECOV30 => self.megaman.heal(RECOV_HP[1]),
            CHIP_INVISIBL => self.megaman.set_invisible(INVISIBL_FRAMES),
            CHIP_BARRIER => self.megaman.set_barrier(BARRIER_HP),
            // AreaGrab needs per-panel ownership, which the field does not
            // track yet. The stand-in is nothing.
            CHIP_AREAGRAB => {}
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
            CHIP_SWORD | CHIP_WIDESWRD | CHIP_LONGSWRD => {
                let mut panels: Vec<(i32, i32)> = Vec::new();
                match chip.id {
                    CHIP_WIDESWRD => panels.extend((1..=field::ROWS).map(|r| (col + dx, r))),
                    CHIP_LONGSWRD => panels.extend([(col + dx, row), (col + 2 * dx, row)]),
                    _ => panels.push((col + dx, row)),
                }
                for enemy in self.enemies.iter_mut().filter(|e| e.is_targetable()) {
                    if panels.contains(&enemy.panel()) {
                        enemy.take_damage(chip.power);
                    }
                }
            }
            CHIP_MINIBOMB => {
                let target = ((col + BOMB_RANGE * dx).clamp(1, field::COLS), row);
                self.bombs.push(Bomb {
                    player: spr::Player::new(spr::Assets::new(SHOTFX), 0),
                    from: (col, row),
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
            CHIP_VULCAN => {
                const FAN: [i32; 4] = [0x08, 0x10, 0x18, 0x20];
                let (fc, fr) = self.megaman.front_panel();
                for i in 0..3 {
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
            _ => {
                let (fc, fr) = self.megaman.front_panel();
                self.shots
                    .push(Shot::buster(spr::Assets::new(SHOTFX), fc, fr, dx, chip.power));
            }
        }
    }

    pub fn draw(&mut self, frame: &mut GraphicsFrame) {
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
        for s in &self.shots {
            s.show(frame);
        }
        if !self.megaman.is_defeated() {
            self.megaman.show(frame);
            if self.glow_state != 0 {
                let (px, py) = field::panel_centre(self.megaman.panel().0, self.megaman.panel().1);
                for part in self.glow.parts() {
                    Object::new(part.sprite.clone())
                        .set_priority(Priority::P2)
                        .set_pos((px + GLOW_OFFSET.0 + part.x, py + GLOW_OFFSET.1 + part.y))
                        .set_hflip(part.hflip)
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
            for part in b.player.parts() {
                Object::new(part.sprite.clone())
                    .set_priority(Priority::P2)
                    .set_pos((x + part.x, y + part.y))
                    .set_hflip(part.hflip)
                    .set_vflip(part.vflip)
                    .show(frame);
            }
        }
        for (p, (x, y), _) in &self.effects {
            for part in p.parts() {
                Object::new(part.sprite.clone())
                    .set_priority(Priority::P2)
                    .set_pos((x + part.x, y + part.y))
                    .set_hflip(part.hflip)
                    .set_vflip(part.vflip)
                    .show(frame);
            }
        }

        // The number sits just under the panel the navi stands on, centred on
        // it, which is where the game puts each combatant's gauge.
        for actor in core::iter::once(&self.megaman)
            .chain(self.enemies.iter())
            .filter(|a| a.is_present() && a.hp() > 0 && a.is_targetable())
        {
            let (px, py) = field::panel_centre(actor.panel().0, actor.panel().1);
            let hp = actor.hp();
            self.hud
                .draw_number(frame, hp, px + self.hud.width(hp) / 2, py + 6);
        }
    }
}
