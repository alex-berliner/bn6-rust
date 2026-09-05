#![no_std]
#![no_main]
#![cfg_attr(test, feature(custom_test_frameworks))]
#![cfg_attr(test, reexport_test_harness_main = "test_main")]
#![cfg_attr(test, test_runner(agb::test_runner::test_runner))]

extern crate alloc;

mod actor;
mod field;
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
static FIELD: &[u8] = &Aligned(*include_bytes!("../assets/field.bin")).0;

#[agb::entry]
fn main(mut gba: agb::Gba) -> ! {
    let mut gfx = gba.graphics.get();
    let mut input = ButtonController::new();

    let field = field::Field::new(FIELD);
    gfx.set_background_palettes(&field.palettes());

    let mut panels = field::Panels::new(field::PANEL_NORMAL);
    let mut bg = field.background(&panels);

    // Real navi HP comes from the battle stats table, which is not extracted
    // yet; these stand in so a fight can be played out.
    const ENEMY_HP: u16 = 40;
    let mut megaman = Actor::new(spr::Assets::new(MEGAMAN), 2, 2, false, 1000);
    let mut enemies = [
        Actor::new(spr::Assets::new(PROTOMAN), 5, 1, true, ENEMY_HP),
        Actor::new(spr::Assets::new(COLONEL), 6, 3, true, ENEMY_HP),
    ];
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
        // A fires the buster; the shot is spawned from the firing state.
        if input.is_just_pressed(Button::A) {
            megaman.fire();
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

        if matches!(megaman.update(), Update::SpawnShot) {
            let (col, row) = megaman.panel();
            // MegaMan only faces right for now, so the shot leaves the panel
            // ahead with dx +1 and the buster's damage of 2.
            shots.push(Shot::new(spr::Assets::new(SHOTFX), col + 1, row, 1, 2));
        }
        for enemy in enemies.iter_mut().filter(|e| !e.is_defeated()) {
            enemy.update();
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
        frame.commit();
    }
}
