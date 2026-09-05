#![no_std]
#![no_main]
#![cfg_attr(test, feature(custom_test_frameworks))]
#![cfg_attr(test, reexport_test_harness_main = "test_main")]
#![cfg_attr(test, test_runner(agb::test_runner::test_runner))]

extern crate alloc;

mod field;
mod spr;

use agb::display::object::Object;
use agb::input::{Button, ButtonController};

/// `include_bytes!` gives no alignment guarantee, but the field tile data has
/// to be word aligned before it can be handed to the VRAM manager.
#[repr(C, align(4))]
struct Aligned<T: ?Sized>(T);

static MEGAMAN: &[u8] = &Aligned(*include_bytes!("../assets/megaman.bin")).0;
static FIELD: &[u8] = &Aligned(*include_bytes!("../assets/field.bin")).0;

#[agb::entry]
fn main(mut gba: agb::Gba) -> ! {
    let mut gfx = gba.graphics.get();
    let mut input = ButtonController::new();

    let field = field::Field::new(FIELD);
    gfx.set_background_palettes(&field.palettes());
    let bg = field.background(field::PANEL_NORMAL);

    let mut anim = 1usize;
    let mut player = spr::Player::new(spr::Assets::new(MEGAMAN), anim);
    let (mut col, mut row) = (2i32, 2i32);

    loop {
        input.update();

        if input.is_just_pressed(Button::Right) && col < 6 {
            col += 1;
        }
        if input.is_just_pressed(Button::Left) && col > 1 {
            col -= 1;
        }
        if input.is_just_pressed(Button::Down) && row < 3 {
            row += 1;
        }
        if input.is_just_pressed(Button::Up) && row > 1 {
            row -= 1;
        }
        if input.is_just_pressed(Button::A) {
            anim = (anim + 1) % player.anim_count();
            player.set_anim(anim);
        }

        player.update();

        let (px, py) = field::panel_centre(col, row);
        let mut frame = gfx.frame();
        bg.show(&mut frame);
        for part in player.parts() {
            Object::new(part.sprite.clone())
                .set_pos((px + part.x as i32, py + part.y as i32))
                .set_hflip(part.hflip)
                .set_vflip(part.vflip)
                .show(&mut frame);
        }
        frame.commit();
    }
}
