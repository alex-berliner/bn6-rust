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

    // Enemy HP is still a stand-in. Boss HP flows through RAM staging written
    // somewhere not yet found; the one static table read at spawn
    // (byte_802DD88, asm03_0.s:15867) serves other-navi spawns, and the
    // 1000-1300 boss-looking table dword_802F0A8 (asm03_0.s:18275) is only
    // read by a function nothing calls. Neither names ProtoMan or Colonel.
    const ENEMY_HP: u16 = 40;
    // MegaMan's own HP does come from the disassembly: byte_80210DD
    // (data/dat01.s:295) row 0 gives 50 * 2 = 100, via init_8013B64.
    const PLAYER_HP: u16 = 100;
    // ProtoMan's sword damage is a placeholder too. Colonel's attacks each
    // draw from one of five damage rows (asm31.s:153623, 80/100/50/30/150 in
    // the first version column); which row the overhead slash uses is not
    // mapped, so the first stands in.
    const SWORD_DAMAGE: u16 = 20;
    const DIVIDE_DAMAGE: u16 = 80;
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
    let mut megaman = Actor::new(
        spr::Assets::new(MEGAMAN),
        2,
        2,
        false,
        PLAYER_HP,
        actor::PLAYER_MERCY_FRAMES,
    );
    let mut enemies = [
        Actor::new(spr::Assets::new(PROTOMAN), 5, 1, true, ENEMY_HP, 0),
        Actor::new(spr::Assets::new(COLONEL), 6, 3, true, ENEMY_HP, 0),
    ];
    let mut ais = [ai::Ai::new(ai::Style::Thrust), ai::Ai::new(ai::Style::Divide)];
    let mut shots: Vec<Shot> = Vec::new();

    loop {
        input.update();

        // Once either side is deleted the fight is decided: the game goes to
        // its results, which are not built yet, so here the field just holds.
        let over = megaman.is_defeated() || enemies.iter().all(|e| e.is_defeated());

        for (button, dx, dy) in [
            (Button::Right, 1, 0),
            (Button::Left, -1, 0),
            (Button::Down, 0, 1),
            (Button::Up, 0, -1),
        ] {
            if input.is_just_pressed(button) && !over {
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
        if !over {
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

        if let Update::Strike { charged } = megaman.update() {
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
        for (enemy, ai) in enemies
            .iter_mut()
            .zip(ais.iter_mut())
            .filter(|(e, _)| !e.is_defeated())
        {
            if !over {
                ai.update(enemy, megaman.panel());
            }
            let update = enemy.update();
            // Colonel's 0xA slash lights its target panels every eighth frame
            // of the wind-up (asm31.s:157045-157076); the overhead slash is
            // given the same telegraph on its column so it can be read.
            if let (ai::Style::Divide, Update::Winding { frame }) = (ai.style(), &update) {
                if frame % 8 == 0 {
                    for row in 1..=field::ROWS {
                        panels.highlight(field::half(false).1, row, 0);
                    }
                }
            }
            if !matches!(update, Update::Strike { .. }) || megaman.is_defeated() {
                continue;
            }
            // ProtoMan's thrust lands on the panel in front. Colonel's slash
            // comes down on the whole of the player's front column: rows 1-3
            // of the column dword_8103B00 names for his side (asm31.s:158257).
            match ai.style() {
                ai::Style::Thrust if megaman.panel() == enemy.front_panel() => {
                    megaman.take_damage(SWORD_DAMAGE);
                }
                ai::Style::Divide if megaman.panel().0 == field::half(false).1 => {
                    megaman.take_damage(DIVIDE_DAMAGE);
                }
                _ => {}
            }
        }

        let occupied = enemies
            .iter()
            .filter(|e| !e.is_defeated())
            .fold(megaman.occupancy(), |m, e| m | e.occupancy());
        panels.update(occupied);
        for (col, row) in field::panels_in(panels.take_dirty()) {
            match panels.flashing(col, row) {
                Some(which) => field.draw_highlight(&mut bg, col, row, which),
                None => field.draw_panel(&mut bg, col, row, panels.animation(col, row)),
            }
        }

        let mut frame = gfx.frame();
        bg.show(&mut frame);
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
        for enemy in enemies.iter().filter(|e| !e.is_defeated()) {
            enemy.show(&mut frame);
        }

        // The number sits just under the panel the navi stands on, centred on
        // it, which is where the game puts each combatant's gauge.
        for actor in core::iter::once(&megaman)
            .chain(enemies.iter())
            .filter(|a| !a.is_defeated())
        {
            let (px, py) = field::panel_centre(actor.panel().0, actor.panel().1);
            let hp = actor.hp();
            hud.draw_number(&mut frame, hp, px + hud.width(hp) / 2, py + 6);
        }
        frame.commit();
    }
}
