#![no_std]
#![no_main]
#![cfg_attr(test, feature(custom_test_frameworks))]
#![cfg_attr(test, reexport_test_harness_main = "test_main")]
#![cfg_attr(test, test_runner(agb::test_runner::test_runner))]

extern crate alloc;

mod actor;
mod ai;
mod backdrop;
mod battle;
mod chips;
mod custom;
mod deck;
mod field;
mod gunner;
mod hud;
mod hudtiles;
mod results;
mod shot;
mod spr;

use agb::input::ButtonController;
use battle::Battle;

/// `include_bytes!` gives no alignment guarantee, but the field tile data has
/// to be word aligned before it can be handed to the VRAM manager.
#[repr(C, align(4))]
struct Aligned<T: ?Sized>(T);

static MEGAMAN: &[u8] = &Aligned(*include_bytes!("../assets/megaman.bin")).0;
static PROTOMAN: &[u8] = &Aligned(*include_bytes!("../assets/protoman.bin")).0;
static COLONEL: &[u8] = &Aligned(*include_bytes!("../assets/colonel.bin")).0;
static SHOTFX: &[u8] = &Aligned(*include_bytes!("../assets/shotfx.bin")).0;
static BARREL_CHARGE: &[u8] = &Aligned(*include_bytes!("../assets/barrel_charge.bin")).0;
static CANNON_ORB: &[u8] = &Aligned(*include_bytes!("../assets/cannon_orb.bin")).0;
static SWORD_SPR: &[u8] = &Aligned(*include_bytes!("../assets/sword.bin")).0;
static SWORD_ARC: &[u8] = &Aligned(*include_bytes!("../assets/sword_arc.bin")).0;
static FIRE_SWORD: &[u8] = &Aligned(*include_bytes!("../assets/sword_83279C0.bin")).0;
static AQUA_SWORD: &[u8] = &Aligned(*include_bytes!("../assets/sword_8329D28.bin")).0;
static ELEC_SWORD: &[u8] = &Aligned(*include_bytes!("../assets/sword_832C418.bin")).0;
static HEAL: &[u8] = &Aligned(*include_bytes!("../assets/heal.bin")).0;
static AIRSHOT_BARREL: &[u8] = &Aligned(*include_bytes!("../assets/airshot_barrel.bin")).0;
static MINIBOMB: &[u8] = &Aligned(*include_bytes!("../assets/minibomb.bin")).0;
static BLKBOMB: &[u8] = &Aligned(*include_bytes!("../assets/blkbomb.bin")).0;
static BOMB_BLAST: &[u8] = &Aligned(*include_bytes!("../assets/bomb_blast.bin")).0;
static VULCAN_GUN: &[u8] = &Aligned(*include_bytes!("../assets/vulcan_gun.bin")).0;
static BARRIER: &[u8] = &Aligned(*include_bytes!("../assets/barrier.bin")).0;
static CHARGE: &[u8] = &Aligned(*include_bytes!("../assets/charge.bin")).0;
static DELETE: &[u8] = &Aligned(*include_bytes!("../assets/delete.bin")).0;
static METTAUR: &[u8] = &Aligned(*include_bytes!("../assets/mettaur.bin")).0;
static WAVE: &[u8] = &Aligned(*include_bytes!("../assets/wave.bin")).0;
static GUNNER: &[u8] = &Aligned(*include_bytes!("../assets/gunner.bin")).0;
static CURSOR: &[u8] = &Aligned(*include_bytes!("../assets/cursor.bin")).0;
static IMPACT: &[u8] = &Aligned(*include_bytes!("../assets/impact.bin")).0;
static RESULTS: &[u8] = &Aligned(*include_bytes!("../assets/results.bin")).0;
static CHIPS: &[u8] = &Aligned(*include_bytes!("../assets/chips.bin")).0;
static CUSTOM: &[u8] = &Aligned(*include_bytes!("../assets/custom.bin")).0;
static FONT: &[u8] = &Aligned(*include_bytes!("../assets/font.bin")).0;
static FIELD: &[u8] = &Aligned(*include_bytes!("../assets/field.bin")).0;
static BACKDROP: &[u8] = &Aligned(*include_bytes!("../assets/backdrop.bin")).0;
static HUD_TILES: &[u8] = &Aligned(*include_bytes!("../assets/hud_tiles.bin")).0;

#[agb::entry]
fn main(mut gba: agb::Gba) -> ! {
    let mut gfx = gba.graphics.get();
    let mut input = ButtonController::new();

    let field = field::Field::new(FIELD);
    let hud = hud::Hud::new(FONT);
    let results = results::Results::new(RESULTS);
    let custom_assets = custom::CustomAssets::new(CUSTOM);
    let chips = chips::Chips::new(CHIPS);
    // The folder shuffle's generator; stepped every frame, as the game's
    // secondary RNG is, so each battle deals differently.
    let mut rng = deck::Rng::new(0x2f6b_75a1);
    // The field uses banks 0-8; the results windows live in 9-11.
    let mut palettes = field.palettes();
    // The backdrop draws in bank 0, as it does on the real ROM.
    palettes[0] = backdrop::Backdrop::new(BACKDROP).palette();
    for (i, p) in results.palettes().into_iter().enumerate() {
        palettes[9 + i] = p;
    }
    // After the results windows, which also want bank 9: the gauge holds it
    // while the fight is up and the chip window borrows it back when it opens.
    let hud_tiles_palettes = hudtiles::HudTiles::new(HUD_TILES);
    palettes[hudtiles::BANK as usize] = hud_tiles_palettes.palette();
    palettes[hudtiles::GAUGE_BANK as usize] = hud_tiles_palettes.gauge_palette();
    gfx.set_background_palettes(&palettes);

    loop {
        // A battle ends on its fade-out, and the next one's intro fades the
        // field back in from the black, so one follows the other seamlessly.
        let mut battle = Battle::new(&field, &results, &hud, &custom_assets, &chips, &mut rng);
        loop {
            input.update();
            rng.next();
            if battle.update(&input, &gfx) {
                break;
            }
            let mut frame = gfx.frame();
            battle.draw(&mut frame);
            frame.commit();
        }
    }
}
