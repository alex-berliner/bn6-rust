#![no_std]
#![no_main]
#![cfg_attr(test, feature(custom_test_frameworks))]
#![cfg_attr(test, reexport_test_harness_main = "test_main")]
#![cfg_attr(test, test_runner(agb::test_runner::test_runner))]

extern crate alloc;

mod actor;
mod ai;
mod field;
mod hud;
mod shot;
mod spr;

use actor::{Actor, Update};
use agb::display::object::Object;
use agb::fixnum::Num;
use agb::input::{Button, ButtonController};
use alloc::vec::Vec;
use shot::Shot;

/// `include_bytes!` gives no alignment guarantee, but the field tile data has
/// to be word aligned before it can be handed to the VRAM manager.
#[repr(C, align(4))]
struct Aligned<T: ?Sized>(T);

static MEGAMAN: &[u8] = &Aligned(*include_bytes!("../assets/megaman.bin")).0;
static PROTOMAN: &[u8] = &Aligned(*include_bytes!("../assets/protoman.bin")).0;
static COLONEL: &[u8] = &Aligned(*include_bytes!("../assets/colonel.bin")).0;
static SHOTFX: &[u8] = &Aligned(*include_bytes!("../assets/shotfx.bin")).0;
static CHARGE: &[u8] = &Aligned(*include_bytes!("../assets/charge.bin")).0;
static DELETE: &[u8] = &Aligned(*include_bytes!("../assets/delete.bin")).0;
static FONT: &[u8] = &Aligned(*include_bytes!("../assets/font.bin")).0;
static FIELD: &[u8] = &Aligned(*include_bytes!("../assets/field.bin")).0;

#[agb::entry]
fn main(mut gba: agb::Gba) -> ! {
    let mut gfx = gba.graphics.get();
    let mut input = ButtonController::new();

    let field = field::Field::new(FIELD);
    let hud = hud::Hud::new(FONT);
    gfx.set_background_palettes(&field.palettes());

    let mut panels = field::Panels::new(field::PANEL_NORMAL);
    let mut bg = field.background(&panels);

    // Boss HP comes from each navi's enemy-definition rows, six bytes per
    // version: an hword whose low twelve bits are HP and top four the
    // element, which the spawner writes to HP and MaxHP (sub_80076A0,
    // asm00_1.s:9155). First version: ProtoMan byte_80FB8BC 0x708
    // (asm31.s:141547), Colonel byte_8101244 0x4b0 (asm31.s:152949).
    const PROTOMAN_HP: u16 = 1800;
    const COLONEL_HP: u16 = 1200;
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
    let mut charge = 0u16;
    // The glow is one persistent effect object on the navi's arm whose
    // animation index is the charge state, 1 charging and 2 full, hidden at 0
    // (chargeShotChargeObject_update_80E0E20, asm31.s:86354). The game tracks
    // the arm position each frame; this offset stands in for that.
    const GLOW_OFFSET: (i32, i32) = (16, -14);
    let mut glow = spr::Player::new(spr::Assets::new(CHARGE), 1);
    let mut glow_state = 0usize;
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
    let mut megaman = Actor::new(spr::Assets::new(MEGAMAN), 2, 2, false, player);
    let mut enemies = [
        Actor::new(spr::Assets::new(PROTOMAN), 5, 1, true, enemy(PROTOMAN_HP)),
        Actor::new(spr::Assets::new(COLONEL), 6, 3, true, enemy(COLONEL_HP)),
    ];
    // The deletion effect, sprite_839CCDC animation 0, spawned at the body
    // when HP reaches zero (spawn_t1_0x0_EffectObject via byte_80E0398 row
    // 3; asm31.s:85229, 85033). An enemy's is given a 0x5a-frame timer.
    let mut effects: Vec<(spr::Player, (i32, i32), u8)> = Vec::new();
    let mut ais = [ai::Ai::new(ai::Style::Thrust), ai::Ai::new(ai::Style::Divide)];
    // The intro: the screen reveals over a 0x10-step fade (SetScreenFade via
    // the intro object, asm31.s:85280), then the enemy navis materialise one
    // at a time from a fade-in list, and only then does the fight state run
    // and lift the pause (sub_8009658 onwards, asm00_1.s:13379; sub_800855E,
    // 11048). The player's navi is simply there. The screen fade's frame
    // count was not read; two frames a step stands in.
    const SCREEN_FADE_FRAMES: u16 = 0x10 * 2;
    let mut intro_fade = SCREEN_FADE_FRAMES;
    let mut intro_next = 0usize;
    for enemy in enemies.iter_mut() {
        enemy.hide();
    }
    let mut cross_shape: Option<&[(i32, i32)]> = None;
    let mut shots: Vec<Shot> = Vec::new();
    // The custom gauge: a u16 at BattleState+0x20 that the fight state adds
    // 0xd to each frame, full at 0x4000 (sub_800855E, asm00_1.s:11100;
    // accessors asm00_2.s:29821-29883). A speed word at +0x22 defaults to
    // 0x20 but nothing reading it was found, so it is not applied. When full
    // the battle pauses for about 60 frames of chimes and then opens chip
    // selection (sub_8008840); that screen is not built, so for now the pause
    // ends with the gauge cleared, as entering it does (asm03_0.s:540).
    const GAUGE_STEP: u16 = 0xd;
    const GAUGE_FULL: u16 = 0x4000;
    const GAUGE_PAUSE: u16 = 60;
    let mut gauge = 0u16;
    let mut gauge_pause = 0u16;

    loop {
        input.update();

        // Once either side is deleted the fight is decided: the game goes to
        // its results, which are not built yet, so here the field just holds.
        let over = megaman.is_defeated() || enemies.iter().all(|e| e.is_defeated());

        // The gauge only runs while the fight does; a full gauge holds
        // everything, including itself, until the chip-select hand-off.
        if gauge_pause > 0 {
            gauge_pause -= 1;
            if gauge_pause == 0 {
                gauge = 0;
            }
        } else if !over && intro_fade == 0 && intro_next >= enemies.len() {
            gauge = (gauge + GAUGE_STEP).min(GAUGE_FULL);
            if gauge == GAUGE_FULL {
                gauge_pause = GAUGE_PAUSE;
            }
        }
        // Bring the field in, then the enemies one by one.
        let intro = if intro_fade > 0 {
            intro_fade -= 1;
            true
        } else if intro_next < enemies.len() {
            if !enemies[intro_next].is_present() {
                enemies[intro_next].appear();
            } else if !enemies[intro_next].is_busy() {
                intro_next += 1;
            }
            true
        } else {
            false
        };
        let paused = over || gauge_pause > 0 || intro;

        for (button, dx, dy) in [
            (Button::Right, 1, 0),
            (Button::Left, -1, 0),
            (Button::Down, 0, 1),
            (Button::Up, 0, -1),
        ] {
            if input.is_just_pressed(button) && !paused {
                megaman.step(dx, dy);
            }
        }
        // B cracks the panel underfoot. Step off a cracked panel and it gives
        // way, then comes back on its own after ten seconds.
        if input.is_just_pressed(Button::B) {
            let (col, row) = megaman.panel();
            panels.crack(col, row);
        }
        // A fires on the press; holding it charges, and a release at full
        // charge fires again, harder (sub_8012EBC, asm00_2.s:9059).
        if !paused {
            if input.is_just_pressed(Button::A) {
                megaman.attack(actor::BUSTER);
            }
            if input.is_pressed(Button::A) {
                charge = charge.saturating_add(1);
            } else {
                if charge >= CHARGE_FRAMES {
                    megaman.attack_charged();
                }
                charge = 0;
            }
        }

        let state = match charge {
            c if c >= CHARGE_FRAMES => 2,
            c if c >= CHARGING_FROM => 1,
            _ => 0,
        };
        if state != glow_state {
            glow_state = state;
            if state != 0 {
                glow.play(state);
            }
        }
        glow.update();

        // Shots tick before the actors, so one spawned this frame first moves
        // next frame, as with an object appended to bn6f's running update.
        let mut i = 0;
        while i < shots.len() {
            // A shot on an enemy's panel flinches them and the shot is spent;
            // MegaMan is not hit yet. Shots off the field are spent too.
            let mut spent = !shots[i].update();
            if !spent {
                for enemy in enemies.iter_mut().filter(|e| e.is_targetable()) {
                    if enemy.panel() == (shots[i].col, shots[i].row) {
                        enemy.take_damage(shots[i].damage);
                        spent = true;
                    }
                }
            }
            if spent {
                shots.swap_remove(i);
            } else {
                i += 1;
            }
        }

        match megaman.update() {
            Update::Strike { charged } => {
                let (col, row) = megaman.front_panel();
                let damage = if charged { CHARGED_DAMAGE } else { BUSTER_DAMAGE };
                shots.push(Shot::new(
                    spr::Assets::new(SHOTFX),
                    col,
                    row,
                    megaman.facing_dx(),
                    damage,
                ));
            }
            Update::Died => {
                let at = field::panel_centre(megaman.panel().0, megaman.panel().1);
                effects.push((spr::Player::new(spr::Assets::new(DELETE), 0), at, 90));
            }
            _ => {}
        }
        for (enemy, ai) in enemies
            .iter_mut()
            .zip(ais.iter_mut())
            .filter(|(e, _)| e.is_present())
        {
            if !paused && !enemy.is_busy() && megaman.is_targetable() {
                // Decided as the attack begins, as the game does, and held for
                // its duration even if the player moves.
                cross_shape = ai::cross_targets(megaman.panel());
                ai.update(enemy, megaman.panel());
            }
            let update = enemy.update();
            // ProtoMan's strike lands on the panel in front and Colonel's
            // slashes on the cross shape or the whole front column
            // (dword_8103B00, asm31.s:158257). Both navis light their targets
            // every eighth frame of the wind-up (asm31.s:142671, 157045);
            // Colonel's overhead slash borrows the same telegraph.
            let targets: Vec<(i32, i32)> = match ai.style() {
                ai::Style::Thrust => alloc::vec![enemy.front_panel()],
                ai::Style::Divide => match cross_shape {
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
                Update::Winding { frame } if frame % 8 == 0 => {
                    for &(col, row) in &targets {
                        if (1..=field::COLS).contains(&col) && (1..=field::ROWS).contains(&row) {
                            panels.highlight(col, row, 0);
                        }
                    }
                }
                Update::Died => {
                    let at = field::panel_centre(enemy.panel().0, enemy.panel().1);
                    effects.push((spr::Player::new(spr::Assets::new(DELETE), 0), at, 90));
                }
                Update::Strike { .. } if megaman.is_targetable() => {
                    if targets.contains(&megaman.panel()) {
                        let damage = match ai.style() {
                            ai::Style::Thrust => SWORD_DAMAGE,
                            ai::Style::Divide if cross_shape.is_some() => CROSS_DAMAGE,
                            ai::Style::Divide => DIVIDE_DAMAGE,
                        };
                        megaman.take_damage(damage);
                    }
                }
                _ => {}
            }
        }

        effects.retain_mut(|(p, _, ticks)| {
            p.update();
            *ticks -= 1;
            *ticks > 0
        });

        let occupied = enemies
            .iter()
            .filter(|e| e.is_targetable())
            .fold(megaman.occupancy(), |m, e| m | e.occupancy());
        panels.update(occupied);
        for (col, row) in field::panels_in(panels.take_dirty()) {
            match panels.flashing(col, row) {
                Some(which) => field.draw_highlight(&mut bg, col, row, which),
                None => field.draw_panel(&mut bg, col, row, panels.animation(col, row)),
            }
        }

        let mut frame = gfx.frame();
        let bg_id = bg.show(&mut frame);
        // Whichever navi is fading -- the deleted player out, an arriving
        // enemy in -- pixelates and thins over the field; the intro's screen
        // fade darkens everything until the field is revealed.
        if intro_fade > 0 {
            let amount = Num::from_raw((intro_fade as u8).div_ceil(2));
            frame
                .blend()
                .darken(amount.min(Num::from_raw(16)))
                .enable_background(bg_id)
                .enable_object();
        } else if let Some((mosaic, alpha)) = core::iter::once(&megaman)
            .chain(enemies.iter())
            .find_map(|a| a.fade())
        {
            frame.mosaic().set_object(mosaic, mosaic);
            frame
                .blend()
                .object_transparency(Num::from_raw(alpha), Num::from_raw(16 - alpha))
                .enable_background(bg_id);
        }
        for s in &shots {
            s.show(&mut frame);
        }
        if !megaman.is_defeated() {
            megaman.show(&mut frame);
            if glow_state != 0 {
                let (px, py) = field::panel_centre(megaman.panel().0, megaman.panel().1);
                for part in glow.parts() {
                    Object::new(part.sprite.clone())
                        .set_pos((px + GLOW_OFFSET.0 + part.x, py + GLOW_OFFSET.1 + part.y))
                        .set_hflip(part.hflip)
                        .set_vflip(part.vflip)
                        .show(&mut frame);
                }
            }
        }
        for enemy in enemies.iter().filter(|e| e.is_present()) {
            enemy.show(&mut frame);
        }
        for (p, (x, y), _) in &effects {
            for part in p.parts() {
                Object::new(part.sprite.clone())
                    .set_pos((x + part.x, y + part.y))
                    .set_hflip(part.hflip)
                    .set_vflip(part.vflip)
                    .show(&mut frame);
            }
        }

        // The number sits just under the panel the navi stands on, centred on
        // it, which is where the game puts each combatant's gauge.
        for actor in core::iter::once(&megaman)
            .chain(enemies.iter())
            .filter(|a| a.is_present() && a.hp() > 0 && a.is_targetable())
        {
            let (px, py) = field::panel_centre(actor.panel().0, actor.panel().1);
            let hp = actor.hp();
            hud.draw_number(&mut frame, hp, px + hud.width(hp) / 2, py + 6);
        }
        frame.commit();
    }
}
