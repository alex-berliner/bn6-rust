#![no_std]
#![no_main]
#![cfg_attr(test, feature(custom_test_frameworks))]
#![cfg_attr(test, reexport_test_harness_main = "test_main")]
#![cfg_attr(test, test_runner(agb::test_runner::test_runner))]

extern crate alloc;

mod field;
mod spr;

use agb::display::object::Object;
use agb::display::GraphicsFrame;
use agb::input::{Button, ButtonController};

/// `include_bytes!` gives no alignment guarantee, but the field tile data has
/// to be word aligned before it can be handed to the VRAM manager.
#[repr(C, align(4))]
struct Aligned<T: ?Sized>(T);

static MEGAMAN: &[u8] = &Aligned(*include_bytes!("../assets/megaman.bin")).0;
static PROTOMAN: &[u8] = &Aligned(*include_bytes!("../assets/protoman.bin")).0;
static FIELD: &[u8] = &Aligned(*include_bytes!("../assets/field.bin")).0;

/// One character on the battle field: an animation player anchored to a panel.
struct Actor {
    player: spr::Player,
    col: i32,
    row: i32,
    facing_left: bool,
}

impl Actor {
    fn new(assets: spr::Assets, anim: usize, col: i32, row: i32, facing_left: bool) -> Self {
        Self {
            player: spr::Player::new(assets, anim),
            col,
            row,
            facing_left,
        }
    }

    fn update(&mut self) {
        self.player.update();
    }

    fn show(&self, frame: &mut GraphicsFrame) {
        let (px, py) = field::panel_centre(self.col, self.row);
        for part in self.player.parts() {
            // Offsets are authored facing right, so mirroring reflects the
            // whole composed frame about the actor origin, not each part in
            // place: the part's left edge moves to the opposite side.
            let x = if self.facing_left {
                -part.x - part.width
            } else {
                part.x
            };
            Object::new(part.sprite.clone())
                .set_pos((px + x, py + part.y))
                .set_hflip(part.hflip ^ self.facing_left)
                .set_vflip(part.vflip)
                .show(frame);
        }
    }
}

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

    let mut anim = 1usize;
    let mut megaman = Actor::new(spr::Assets::new(MEGAMAN), anim, 2, 2, false);
    let mut protoman = Actor::new(spr::Assets::new(PROTOMAN), 1, 5, 2, true);

    loop {
        input.update();

        if input.is_just_pressed(Button::Right) && megaman.col < 6 {
            megaman.col += 1;
        }
        if input.is_just_pressed(Button::Left) && megaman.col > 1 {
            megaman.col -= 1;
        }
        if input.is_just_pressed(Button::Down) && megaman.row < 3 {
            megaman.row += 1;
        }
        if input.is_just_pressed(Button::Up) && megaman.row > 1 {
            megaman.row -= 1;
        }
        if input.is_just_pressed(Button::A) {
            anim = (anim + 1) % megaman.player.anim_count();
            megaman.player.set_anim(anim);
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
