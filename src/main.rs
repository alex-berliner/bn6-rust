#![no_std]
#![no_main]
#![cfg_attr(test, feature(custom_test_frameworks))]
#![cfg_attr(test, reexport_test_harness_main = "test_main")]
#![cfg_attr(test, test_runner(agb::test_runner::test_runner))]

extern crate alloc;

mod actor;
mod field;
mod spr;

use actor::Actor;
use agb::input::{Button, ButtonController};

/// `include_bytes!` gives no alignment guarantee, but the field tile data has
/// to be word aligned before it can be handed to the VRAM manager.
#[repr(C, align(4))]
struct Aligned<T: ?Sized>(T);

static MEGAMAN: &[u8] = &Aligned(*include_bytes!("../assets/megaman.bin")).0;
static PROTOMAN: &[u8] = &Aligned(*include_bytes!("../assets/protoman.bin")).0;
static FIELD: &[u8] = &Aligned(*include_bytes!("../assets/field.bin")).0;

#[agb::entry]
fn main(mut gba: agb::Gba) -> ! {
    let mut gfx = gba.graphics.get();
    let mut input = ButtonController::new();

    let field = field::Field::new(FIELD);
    gfx.set_background_palettes(&field.palettes());

    // Panels will become per-panel state once battles can crack and break
    // them; for now B walks the whole field through the five types.
    const PANEL_TYPES: [usize; 5] = [
        field::PANEL_NORMAL,
        field::PANEL_CRACKED,
        field::PANEL_BROKEN,
        field::PANEL_HOLE,
        field::PANEL_POISON,
    ];
    let mut panel = 0usize;
    let mut bg = field.background(PANEL_TYPES[panel]);

    let mut megaman = Actor::new(spr::Assets::new(MEGAMAN), 2, 2, false);
    let mut protoman = Actor::new(spr::Assets::new(PROTOMAN), 5, 2, true);

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
        if input.is_just_pressed(Button::B) {
            panel = (panel + 1) % PANEL_TYPES.len();
            bg = field.background(PANEL_TYPES[panel]);
        }

        megaman.update();
        protoman.update();

        let mut frame = gfx.frame();
        bg.show(&mut frame);
        megaman.show(&mut frame);
        protoman.show(&mut frame);
        frame.commit();
    }
}
