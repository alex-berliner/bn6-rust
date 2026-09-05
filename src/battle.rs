//! The state of one battle and the frame logic that runs it: the intro
//! fades the screen in, the fight runs until a side is deleted, and the
//! results window closes with a fade-out. It is all rebuilt for the next
//! battle; the field, HUD and results assets are borrowed.

use agb::display::GraphicsFrame;
use agb::display::object::Object;
use agb::display::tiled::RegularBackground;
use agb::fixnum::Num;
use agb::input::{Button, ButtonController};
use alloc::vec::Vec;

use crate::actor::{self, Actor, Update};
use crate::custom::{self, Custom, CustomAssets};
use crate::field::{self, Field, Panels};
use crate::hud::Hud;
use crate::results::{self, Results};
use crate::shot::Shot;
use crate::{ai, gunner, spr};
use crate::{
    CHARGE, COLONEL, CURSOR, DELETE, GUNNER, IMPACT, MEGAMAN, METTAUR, PROTOMAN, SHOTFX, WAVE,
};
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
    panels: Panels,
    bg: RegularBackground,
    megaman: Actor,
    enemies: [Actor; 4],
    ais: [ai::Ai; 4],
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

impl<'a> Battle<'a> {
    pub fn new(
        field: &'a Field,
        results: &'a Results,
        hud: &'a Hud,
        custom_assets: &'a CustomAssets,
    ) -> Self {
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
        let megaman = Actor::new(spr::Assets::new(MEGAMAN), 2, 2, false, player);
        // Whether a virus dies with the navi's 0x5a-frame blink was not checked.
        let mut enemies = [
            Actor::new(spr::Assets::new(PROTOMAN), 5, 1, true, enemy(PROTOMAN_HP)),
            Actor::new(spr::Assets::new(COLONEL), 6, 3, true, enemy(COLONEL_HP)),
            Actor::new(spr::Assets::new(METTAUR), 5, 3, true, enemy(METTAUR_HP)),
            Actor::new(spr::Assets::new(GUNNER), 6, 2, true, enemy(gunner::HP)),
        ];
        let gunner_ctl = gunner::Gunner::new();
        let impacts: Vec<gunner::Impact> = Vec::new();
        // The deletion effect, sprite_839CCDC animation 0, spawned at the body
        // when HP reaches zero (spawn_t1_0x0_EffectObject via byte_80E0398 row
        // 3; asm31.s:85229, 85033). An enemy's is given a 0x5a-frame timer.
        let effects: Vec<(spr::Player, (i32, i32), u8)> = Vec::new();
        let ais = [
            ai::Ai::new(ai::Style::Thrust),
            ai::Ai::new(ai::Style::Divide),
            ai::Ai::new(ai::Style::Mettaur),
            ai::Ai::new(ai::Style::Gunner),
        ];
        let intro_fade = SCREEN_FADE_FRAMES;
        let intro_next = 0usize;
        for enemy in enemies.iter_mut() {
            enemy.hide();
        }
        let cross_shape: Option<&[(i32, i32)]> = None;
        let shots: Vec<Shot> = Vec::new();
        let gauge = 0u16;
        let gauge_pause = 0u16;
        let results_delay = RESULTS_DELAY;
        let shown: Option<results::Shown> = None;
        let fade_out = 0u8;
        let clock = 0u32;
        let moves = 0u8;

        Self {
            field,
            results,
            hud,
            custom_assets,
            custom: None,
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
        // chip window, which takes bank 9 while it is up.
        if let Some(window) = self.custom.as_mut() {
            if window.update(input) {
                self.custom = None;
                gfx.set_background_palette(custom::BANK, &self.results.palettes()[0]);
                self.gauge = 0;
            }
        } else if self.gauge_pause > 0 {
            self.gauge_pause -= 1;
            if self.gauge_pause == 0 {
                gfx.set_background_palette(custom::BANK, &self.custom_assets.palette(0));
                self.custom = Some(self.custom_assets.open());
            }
        } else if !over && self.intro_fade == 0 && self.intro_next >= self.enemies.len() {
            self.gauge = (self.gauge + GAUGE_STEP).min(GAUGE_FULL);
            if self.gauge == GAUGE_FULL {
                self.gauge_pause = GAUGE_PAUSE;
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
        // B cracks the panel underfoot. Step off a cracked panel and it gives
        // way, then comes back on its own after ten seconds.
        if input.is_just_pressed(Button::B) {
            let (col, row) = self.megaman.panel();
            self.panels.crack(col, row);
        }
        // A fires on the press; holding it charges, and a release at full
        // charge fires again, harder (sub_8012EBC, asm00_2.s:9059).
        if !paused {
            if input.is_just_pressed(Button::A) {
                self.megaman.attack(actor::BUSTER);
            }
            if input.is_pressed(Button::A) {
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
            Update::Strike { charged } => {
                let (col, row) = self.megaman.front_panel();
                let damage = if charged { CHARGED_DAMAGE } else { BUSTER_DAMAGE };
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
        self.impacts.retain_mut(|imp| match imp.update(&mut self.panels) {
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

        let occupied = self
            .enemies
            .iter()
            .filter(|e| e.is_targetable())
            .fold(self.megaman.occupancy(), |m, e| m | e.occupancy());
        self.panels.update(occupied);
        for (col, row) in field::panels_in(self.panels.take_dirty()) {
            match self.panels.flashing(col, row) {
                Some(which) => self.field.draw_highlight(&mut self.bg, col, row, which),
                None => self
                    .field
                    .draw_panel(&mut self.bg, col, row, self.panels.animation(col, row)),
            }
        }

        false
    }

    /// Draw the frame for the state `update` has just advanced. The caller
    /// commits it.
    pub fn draw(&mut self, frame: &mut GraphicsFrame) {
        let bg_id = self.bg.show(frame);
        // Whichever navi is fading -- the deleted player out, an arriving
        // enemy in -- pixelates and thins over the field; the intro's screen
        // fade darkens everything until the field is revealed.
        let window_id = self.shown.as_ref().map(|window| window.show(frame));
        if let Some(window) = &self.custom {
            window.show(frame);
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
        for (p, (x, y), _) in &self.effects {
            for part in p.parts() {
                Object::new(part.sprite.clone())
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
