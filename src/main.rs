#![no_std]
#![no_main]
#![cfg_attr(test, feature(custom_test_frameworks))]
#![cfg_attr(test, reexport_test_harness_main = "test_main")]
#![cfg_attr(test, test_runner(agb::test_runner::test_runner))]

extern crate alloc;

mod spr;

use agb::display::object::Object;
use agb::input::{Button, ButtonController};

static MEGAMAN: &[u8] = include_bytes!("../assets/megaman.bin");

#[agb::entry]
fn main(mut gba: agb::Gba) -> ! {
    let mut gfx = gba.graphics.get();
    let mut input = ButtonController::new();

    let mut anim = 1usize;
    let mut player = spr::Player::new(spr::Assets::new(MEGAMAN), anim);
    let (x, mut y) = (120, 96);

    loop {
        input.update();

        if input.is_just_pressed(Button::Right) {
            anim = (anim + 1) % player.anim_count();
            player.set_anim(anim);
        }
        if input.is_just_pressed(Button::Left) {
            anim = (anim + player.anim_count() - 1) % player.anim_count();
            player.set_anim(anim);
        }
        if input.is_pressed(Button::Up) {
            y -= 1;
        }
        if input.is_pressed(Button::Down) {
            y += 1;
        }

        player.update();

        let mut frame = gfx.frame();
        for part in player.parts() {
            Object::new(part.sprite.clone())
                .set_pos((x + part.x, y + part.y))
                .set_hflip(part.hflip)
                .set_vflip(part.vflip)
                .show(&mut frame);
        }
        frame.commit();
    }
}
