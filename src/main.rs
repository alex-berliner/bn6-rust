#![no_std]
#![no_main]
#![cfg_attr(test, feature(custom_test_frameworks))]
#![cfg_attr(test, reexport_test_harness_main = "test_main")]
#![cfg_attr(test, test_runner(agb::test_runner::test_runner))]

extern crate alloc;

mod actor;
mod ai;
mod backdrop;
mod banner;
mod battle;
mod chips;
mod custom;
mod deck;
mod emotion;
mod field;
mod gunner;
mod hud;
mod hudtiles;
mod results;
mod shot;
mod spr;

use agb::input::ButtonController;
use agb::sound::mixer::Frequency;
use battle::Battle;

/// `include_bytes!` gives no alignment guarantee, but the field tile data has
/// to be word aligned before it can be handed to the VRAM manager.
#[repr(C, align(4))]
struct Aligned<T: ?Sized>(T);

static MEGAMAN: &[u8] = &Aligned(*include_bytes!("../assets/megaman.bin")).0;
static PROTOMAN: &[u8] = &Aligned(*include_bytes!("../assets/protoman.bin")).0;
static COLONEL: &[u8] = &Aligned(*include_bytes!("../assets/colonel.bin")).0;
static SHOTFX: &[u8] = &Aligned(*include_bytes!("../assets/shotfx.bin")).0;
/// The buster's own two objects: the barrel that rides the navi's arm
/// (byte_82F6ECC.spr animation 0) and the muzzle flash it fires
/// (byte_82FE378.spr), both identified by dumping OBJ VRAM on the firing
/// frame and searching every sprite file for those tiles.
static BUSTER_ARM: &[u8] = &Aligned(*include_bytes!("../assets/buster_arm.bin")).0;
static BUSTER_FX: &[u8] = &Aligned(*include_bytes!("../assets/buster_fx.bin")).0;
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
static LILBOILER: &[u8] = &Aligned(*include_bytes!("../assets/lilboiler.bin")).0;
static FLSHBOM: &[u8] = &Aligned(*include_bytes!("../assets/flshbom.bin")).0;
static POISSEED: &[u8] = &Aligned(*include_bytes!("../assets/poisseed.bin")).0;
static POISAREA: &[u8] = &Aligned(*include_bytes!("../assets/poisarea.bin")).0;
static VDOLL: &[u8] = &Aligned(*include_bytes!("../assets/vdoll.bin")).0;
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
static BANNER: &[u8] = &Aligned(*include_bytes!("../assets/banner.bin")).0;
static HUD_TILES: &[u8] = &Aligned(*include_bytes!("../assets/hud_tiles.bin")).0;
static TEXT_FONT: &[u8] = &Aligned(*include_bytes!("../assets/text_font.bin")).0;
static EMOTION: &[u8] = &Aligned(*include_bytes!("../assets/emotion.bin")).0;
static HAND_ICON: &[u8] = &Aligned(*include_bytes!("../assets/hand_icon.bin")).0;
// SOUND_HIT_6B's sample (byte_81597A0, dat37.s): the buster's HIT, not its
// fire -- see TRANSFER.md 7bb. Exported by tools/sample_export.py, 1881
// samples at 10512 Hz, no loop. The mixer frequency below must match exactly
// (agb::include_wav! does no resampling).
static BUSTER_HIT: agb::sound::mixer::SoundData = agb::include_wav!("assets/buster_hit.wav");

/// AUDIT pair 1 / TRANSFER 7bj: the harness used to align a real capture
/// against ours by a frame count from power-on, and our boot length moves
/// with the compiler, so a fixed offset breaks on unrelated edits. This is
/// the fix -- an event the harness can read out of RAM instead of counting
/// frames itself.
///
/// Eight bytes at a fixed EWRAM address, written with volatile stores every
/// frame from the main loop below:
///   +0  u32 magic, little-endian: 0 until the battle has started, then
///       `BATTLE_MAGIC` (0x42415454, "BATT" read big-endian).
///   +4  u32 battle frame counter: 0 on the battle's first frame (the same
///       frame `Battle::new`'s backdrop and gauge begin counting from --
///       for a non-demo build and `demo-open`, the first frame of the white
///       intro; see TRANSFER 7ba), +1 every battle frame after.
///
/// `#[link_section = ".ewram.marker"]` is a dedicated input section that
/// `vendor/agb/agb/src/gba.ld`'s `.ewram : { *(.ewram .ewram.*); ... }` rule
/// places ahead of `.data`/`.bss` -- nothing else in this build uses a
/// `.ewram*` section (agb's own use of `.ewram` is behind `#[cfg(test)]`),
/// so `BATTLE_MARKER` is the sole occupant and lands at EWRAM's base,
/// 0x02000000, independent of how the rest of the binary's statics shuffle
/// around under an unrelated edit or a compiler change. Find it any time
/// with `nm <elf> | grep BATTLE_MARKER`; read it live with
/// `mgba_capture <rom> <out> <N> --dump 0x02000000:8:<file>`.
#[unsafe(no_mangle)]
#[unsafe(link_section = ".ewram.marker")]
pub static mut BATTLE_MARKER: [u32; 2] = [0, 0];

const BATTLE_MAGIC: u32 = 0x4241_5454;

/// Volatile so the write can't be optimised away as dead (nothing in this
/// crate ever reads `BATTLE_MARKER` back) or reordered past a frame's
/// `commit()`.
fn write_battle_marker(magic: u32, frame: u32) {
    unsafe {
        let p = core::ptr::addr_of_mut!(BATTLE_MARKER) as *mut u32;
        core::ptr::write_volatile(p, magic);
        core::ptr::write_volatile(p.add(1), frame);
    }
}

#[agb::entry]
fn main(mut gba: agb::Gba) -> ! {
    let mut gfx = gba.graphics.get();
    let mut input = ButtonController::new();

    let field = field::Field::new(FIELD);
    let hud = hud::Hud::new(FONT);
    let results = results::Results::new(RESULTS, TEXT_FONT);
    let custom_assets = custom::CustomAssets::new(CUSTOM, TEXT_FONT);
    let chips = chips::Chips::new(CHIPS);
    // The folder shuffle's generator; stepped every frame, as the game's
    // secondary RNG is, so each battle deals differently.
    let mut rng = deck::Rng::new(0x2f6b_75a1);
    // The field uses banks 0-8; the results windows live in 9-11.
    let mut palettes = field.palettes();
    // The backdrop draws in bank 0, as it does on the real ROM.
    // The backdrop draws in bank 0, as it does on the real ROM -- but ONLY
    // where it is drawn. The sterile arena shows no backdrop, and handing bank
    // 0 to it there costs the barrier bubble its colours: Barrier goes from
    // 0.8 px/frame to 766. The field itself does not use bank 0, which is why
    // taking it is safe in a full battle.
    if !cfg!(feature = "demo-sterile") {
        palettes[0] = backdrop::Backdrop::new(BACKDROP).palette();
    }
    for (i, p) in results.palettes().into_iter().enumerate() {
        palettes[9 + i] = p;
    }
    // After the results windows, which also want bank 9: the gauge holds it
    // while the fight is up and the chip window borrows it back when it opens.
    // Scoped: these exist only to read their palettes. Held past the block
    // they keep a background and its tiles claimed for the whole program.
    {
        let hud = hudtiles::HudTiles::new(HUD_TILES, TEXT_FONT);
        palettes[hudtiles::BANK as usize] = hud.palette();
        palettes[hudtiles::GAUGE_BANK as usize] = hud.gauge_palette();
    }
    gfx.set_background_palettes(&palettes);

    // 10512 Hz: the mixer's own output rate, chosen to match SOUND_HIT_6B's
    // sample exactly (assets/buster_hit.wav) so agb's include_wav! does no
    // resampling.
    let mut mixer = gba.mixer.mixer(Frequency::Hz10512);

    loop {
        // A battle ends on its fade-out, and the next one's intro fades the
        // field back in from the black, so one follows the other seamlessly.
        let mut battle = Battle::new(&field, &results, &hud, &custom_assets, &chips, &mut rng);
        battle.prime_backdrop(&gfx);
        // Not yet -- this battle's own clocks (backdrop, gauge) start inside
        // the first `battle.update()` call below, not here: `Battle::new`
        // has no `Graphics` to draw with, and `prime_backdrop` only seeds
        // the backdrop's art step (see its doc comment), it does not tick.
        write_battle_marker(0, 0);
        let mut battle_frame: u32 = 0;
        // The very first `commit()` this program ever calls does not
        // actually reach the screen. `VBlank::get()` records the vblank
        // count once, early, inside `gba.graphics.get()` above; by the time
        // this loop's first `commit()` calls `wait_for_vblank()`, all of
        // `main`'s asset loading (into VRAM, well over a frame of DMA and
        // copying) has already let at least one vblank pass, so
        // `wait_for_vblank` (agb's interrupt.rs) sees the count has already
        // moved and returns immediately instead of blocking -- see its
        // `last_waited_number < NUM_VBLANKS` check. That first commit's
        // drawn content is then silently overwritten by the next
        // iteration's before any real vblank displays it.
        //
        // If this counted the first call's tick as frame 0, the marker
        // would report a frame whose drawing is never shown -- a `--dump`
        // right after it never observed anything BUT the SECOND call's
        // value (0 with this guard removed and the second call labelled 1
        // instead: it jumped straight from "not started" to 1, the first
        // call's write invisibly overwritten first). Measured against
        // tools/regress.py's independently-derived `opening` alignment
        // (OPENING_LAGS searched, a unique zero at lag 7 -- +-1 frame off
        // by 63-65k px) the frame genuinely displayed first is the SECOND
        // `battle.update()` call's. So the first call's tick is real
        // (backdrop and gauge do start counting there) but never visible,
        // and is not counted here.
        let mut clocks_visible = false;
        loop {
            input.update();
            rng.next();
            let over = battle.update(&input, &gfx, &mut mixer);
            if clocks_visible {
                write_battle_marker(BATTLE_MAGIC, battle_frame);
                battle_frame += 1;
            }
            clocks_visible = true;
            if over {
                break;
            }
            let mut frame = gfx.frame();
            battle.draw(&mut frame);
            mixer.frame();
            frame.commit();
        }
    }
}
