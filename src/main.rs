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

    // Real navi HP comes from the battle stats table, which is not extracted
    // yet; these stand in so a fight can be played out.
    const ENEMY_HP: u16 = 40;
    // ProtoMan's sword damage is a placeholder too.
    const SWORD_DAMAGE: u16 = 20;
    let mut megaman = Actor::new(
        spr::Assets::new(MEGAMAN),
        2,
        2,
        false,
        1000,
        actor::PLAYER_MERCY_FRAMES,
    );
    let mut enemies = [
        Actor::new(spr::Assets::new(PROTOMAN), 5, 1, true, ENEMY_HP, 0),
        Actor::new(spr::Assets::new(COLONEL), 6, 3, true, ENEMY_HP, 0),
    ];
    // Only ProtoMan acts: his attack animation is verified, Colonel's is not.
    let mut protoman_ai = ai::Ai::new();
    let mut shots: Vec<Shot> = Vec::new();

    loop {
        input.update();

        for (button, dx, dy) in [
            (Button::Right, 1, 0),
            (Button::Left, -1, 0),
            (Button::Down, 0, 1),
            (Button::Up, 0, -1),
        ] {
            if input.is_just_pressed(button) {
                megaman.step(dx, dy);
            }
        }
        // B cracks the panel underfoot. Step off a cracked panel and it gives
        // way, then comes back on its own after ten seconds.
        if input.is_just_pressed(Button::B) {
            let (col, row) = megaman.panel();
            panels.crack(col, row);
        }
        // A fires the buster; the shot is spawned from the attack state.
        if input.is_just_pressed(Button::A) {
            megaman.attack();
        }

        // Shots tick before the actors, so one spawned this frame first moves
        // next frame, as with an object appended to bn6f's running update.
        let mut i = 0;
        while i < shots.len() {
            // A shot on an enemy's panel flinches them and the shot is spent;
            // MegaMan is not hit yet. Shots off the field are spent too.
            let mut spent = !shots[i].update();
            if !spent {
                for enemy in enemies.iter_mut().filter(|e| !e.is_defeated()) {
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

        if matches!(megaman.update(), Update::Strike) {
            // The buster's damage of 2 (sub_801265A: Attack 1, +1 for MegaMan).
            let (col, row) = megaman.front_panel();
            shots.push(Shot::new(
                spr::Assets::new(SHOTFX),
                col,
                row,
                megaman.facing_dx(),
                2,
            ));
        }
        for (i, enemy) in enemies
            .iter_mut()
            .enumerate()
            .filter(|(_, e)| !e.is_defeated())
        {
            if i == 0 {
                protoman_ai.update(enemy, megaman.panel());
            }
            // A sword lands on the panel in front; it hits whoever stands there.
            if matches!(enemy.update(), Update::Strike)
                && !megaman.is_defeated()
                && megaman.panel() == enemy.front_panel()
            {
                megaman.take_damage(SWORD_DAMAGE);
            }
        }

        let occupied = enemies
            .iter()
            .filter(|e| !e.is_defeated())
            .fold(megaman.occupancy(), |m, e| m | e.occupancy());
        panels.update(occupied);
        for (col, row) in field::panels_in(panels.take_dirty()) {
            field.draw_panel(&mut bg, col, row, panels.animation(col, row));
        }

        let mut frame = gfx.frame();
        bg.show(&mut frame);
        for s in &shots {
            s.show(&mut frame);
        }
        megaman.show(&mut frame);
        for enemy in enemies.iter().filter(|e| !e.is_defeated()) {
            enemy.show(&mut frame);
        }

        // The number sits just under the panel the navi stands on, centred on
        // it, which is where the game puts each combatant's gauge.
        for actor in core::iter::once(&megaman).chain(enemies.iter().filter(|e| !e.is_defeated())) {
            let (px, py) = field::panel_centre(actor.panel().0, actor.panel().1);
            let hp = actor.hp();
            hud.draw_number(&mut frame, hp, px + hud.width(hp) / 2, py + 6);
        }
        frame.commit();
    }
}
