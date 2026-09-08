//! AUDIT pairs 6, 14, 17 / FIXTURE.md: one ROM, any fixture.
//!
//! Today every fixture is a `demo-*` cargo feature that bakes one state into
//! its own build (see Cargo.toml's `demo*` feature list and every
//! `cfg!(feature = "demo...")` site in `main.rs`/`battle.rs`). This module
//! is the runtime alternative: the harness writes a 64-byte descriptor into
//! EWRAM at a fixed address before the ROM boots (and keeps writing it,
//! frame by frame, so it survives whatever the emulator's cheat mechanism
//! does), and `read()` parses it once at startup. `Battle::new` and the
//! per-frame logic in `battle.rs` take everything -- enemies, positions, HP,
//! hand, gauge, flags, backdrop/gauge seeds -- from the descriptor when one
//! is present, and fall back to exactly today's behaviour (`cfg!`-gated demo
//! features, or the plain release build) when it is absent. The `demo-*`
//! features are NOT removed by this: they stay until wave 3 confirms the
//! harness reproduces every check through descriptors instead.
//!
//! Address **0x02000040**, 64 bytes, little-endian -- FIXTURE.md's own
//! contract, mirrored here field for field. Reserved as bytes 64..128 of
//! `main.rs`'s own `BATTLE_MARKER` static, which `gba.ld`'s
//! `.ewram : { *(.ewram .ewram.*); ... }` rule places ahead of `.data`/
//! `.bss`, so the descriptor is never zeroed as `.bss` or overwritten by
//! `.data` init. See `BATTLE_MARKER`'s own doc comment in `main.rs` for why
//! it is ONE array covering both the marker and this descriptor rather than
//! two separate `#[link_section]`'d statics -- the two-statics version was
//! tried first and its relative order silently flipped under
//! `--features demo-hudmatch`, which is exactly the kind of failure this
//! module's reservation must not have.

/// `0x46495854`: the two harness cheats that write it are
/// `--cheat 0x02000040:0x5854 --cheat 0x02000042:0x4649` (FIXTURE.md), which
/// land bytes `54 58 49 46` at 0x40..0x44 -- read back as one little-endian
/// u32 that is this constant.
const MAGIC: u32 = 0x4649_5854;

/// Base address of the descriptor, per FIXTURE.md.
pub const ADDR: usize = 0x0200_0040;

/// bit0: open with the chip window (gate the gauge-pause -> chip-window-open
/// sequence; UNSET reproduces `demo-hudmatch`'s own special case, which
/// freezes a full gauge and never opens the window -- see `read()`'s doc and
/// the descriptor table below).
pub const FLAG_OPEN_WINDOW: u8 = 1 << 0;
/// bit1: blank HUD. UNSET means the real HUD (`HudTiles`) is always drawn
/// with a descriptor -- AUDIT pair 6: the old sterile arena drew NOTHING at
/// all where canon shows the HP box (no stub currently exists in this code
/// to draw a bare "100" either; see the report), which made every chip
/// comparison a box instead of a full screen. SET reproduces
/// `demo-sterile`'s `hud_tiles: None`.
pub const FLAG_BLANK_HUD: u8 = 1 << 1;
/// bit2: blank backdrop. Reproduces `demo-sterile`'s WHOLE non-HUD
/// background, not just the `backdrop` module: `backdrop: None`, the field
/// layer (`self.bg`) replaced with a blank tilemap, and the hand-chip icon
/// object suppressed (`hand_icon_palette: None`) -- exactly the three things
/// `cfg!(feature = "demo-sterile")` already gates. Broader than its name
/// suggests; flagged in the report as worth a name/scope check with
/// FIXTURE.md's author.
pub const FLAG_BLANK_BACKDROP: u8 = 1 << 2;
/// bit3: auto-fire the hand, on the schedule `fire_frame` seeds -- see its
/// own field doc.
pub const FLAG_AUTO_FIRE: u8 = 1 << 3;
/// bit4: skip the white intro. SET reproduces every `demo-*` fixture's own
/// legacy short black ramp (`SCREEN_FADE_FRAMES`'s `demo && !demo-open`
/// branch, `0x10 * 2` = 32 frames); UNSET plays the real 71-frame white hold
/// + 14-frame ramp, which is what `demo-open` and the default release build
/// already do.
pub const FLAG_SKIP_INTRO: u8 = 1 << 4;

/// A fixture descriptor, parsed from the 64 bytes at `ADDR`. Fields and
/// offsets match FIXTURE.md exactly, with additions past byte 48 (FIXTURE.md's
/// own reserved region) -- see `window_pick_count`'s doc for why they live
/// there instead of in the published contract.
#[derive(Clone, Copy)]
pub struct Fixture {
    pub enemies: u8,
    pub enemy_kind: u8,
    pub enemy_col: u8,
    pub enemy_row: u8,
    pub megaman_hp: u16,
    pub megaman_col: u8,
    pub megaman_row: u8,
    pub hand_count: u8,
    pub hand: [u8; 5],
    pub gauge: u8,
    pub flags: u8,
    pub art_entry: u16,
    pub art_timer: u16,
    pub scroll_xq: u16,
    pub scroll_yq: u16,
    /// Seeds `HudTiles`'s own flow counter (`gauge_tick` there) directly, for
    /// a fixture compared against a save state where the CUSTOM gauge has
    /// already been full for an unknown time -- see `hudtiles::HudTiles::
    /// seed_gauge`'s doc and TRANSFER.md 7ab ("two phases... cannot be
    /// settled by one save state"). 0xFFFF ("default" throughout this
    /// contract) leaves `HudTiles::new`'s own fresh value (0), which is
    /// already right for every fixture verified so far -- see the table
    /// below -- so this is a knob to reach for if a future capture's gauge
    /// phase does not land on zero, not one any current row needs to turn.
    pub gauge_tick: u16,
    pub fire_frame: u16,
    /// Was FIXTURE.md's own reserved region before this ticket; +32 is now
    /// published there (see FIXTURE.md). 0 => the kind's own sensible
    /// default (40, `METTAUR_HP`, for kind 0) -- NOTE this is 0, not 0xFFFF,
    /// even though FIXTURE.md's own table entry for this field currently
    /// reads "0xFFFF = the kind's default": the actual code below (unchanged
    /// by this ticket, already verified byte-identical for `demo-field`) has
    /// always treated 0 as the sentinel and a literal 0xFFFF as a real (if
    /// absurdly large) HP value -- `demo-field`'s own Mettaur is pinned at
    /// enemy_hp = 0xffff to survive the capture's per-frame damage. Flagged
    /// in the ticket report as a FIXTURE.md wording bug, not fixed here
    /// (out of scope: this file mirrors the contract, it does not own it).
    pub enemy_hp: u16,
    /// +34 FIXTURE.md: chips the chip WINDOW offers, distinct from `hand`
    /// (the already-picked hand used when the window is closed). 0..5.
    pub deck_count: u8,
    /// +35 FIXTURE.md: chip ids offered, in order, `deck_count` of them live.
    pub deck: [u8; 5],
    /// +40 FIXTURE.md: 0 = battle, 1 = start already at the RESULT window.
    pub start_state: u8,
    /// +41 FIXTURE.md: busting level shown when `start_state` = 1.
    pub result_level: u8,
    /// +42 FIXTURE.md: battle time (in frames) shown when `start_state` = 1.
    pub result_frames: u16,
    /// +44 FIXTURE.md: reward (zenny) shown when `start_state` = 1.
    pub result_zenny: u16,
    /// +46 FIXTURE.md: battle frame to raise ENEMY DELETED on, 0xFFFF =
    /// never forced.
    pub banner_at: u16,
    /// NOT IN FIXTURE.md, offset +48 (the reserved region past this ticket's
    /// own new fields). FIXTURE.md's own words for `deck` are "codes are the
    /// game's own per-id defaults" (`chips::Chip::codes[0]`), which covers 3
    /// of `demo-custmatch`'s 5 real slots (Cannon@0, AirShot@wildcard,
    /// MiniBomb@1 all match their chip's own `codes[0]`) but not the other 2
    /// -- Vulcan1's card is captured at code D (3), whose `codes[0]` is B
    /// (1), and Sword's at code S (18), whose `codes[0]` is H (7); see
    /// `chips.bin`'s own record (checked with a throwaway script reading it
    /// directly: Vulcan1 codes = [1, 3, 18, 26], Sword codes = [7, 11, 18,
    /// 26) -- so the letter this capture shows is `codes[1]`/`codes[2]`, not
    /// the chip's first/default one. Reported rather than silently patched
    /// into FIXTURE.md, same as `enemy_hp` was: a per-slot code override is
    /// needed for byte-identical reproduction and the published contract has
    /// none. 0xFF (per slot) => that slot's own `codes[0]`.
    pub deck_codes: [u8; 5],
    /// NOT IN FIXTURE.md, offset +53. `demo-custmatch`'s own capture already
    /// has ONE offered chip picked (the Cannon, slot 4) with the cursor
    /// resting on OK when the window opens; `demo-cardname` is the identical
    /// window with the cursor on the first slot instead, to show the card's
    /// NAME rather than the OK confirmation message (`custom.rs`'s own
    /// `cfg!(feature = "demo-cardname")` site -- which fixture.rs's own
    /// descriptor table comment WRONGLY claimed had "no cfg site of its own"
    /// before this ticket; see the ticket report). No FIXTURE.md field
    /// starts a window already mid-pick, so this is the same kind of
    /// reserved-region addition as `enemy_hp`/`deck_codes`. 0 => no
    /// pre-pick, `Custom::open`'s own fresh `picks: Vec::new()` /
    /// `cursor_at: 0` stand, which is every fixture but these two.
    pub window_pick_count: u8,
    /// +54: the offered slot index pre-picked when `window_pick_count` > 0.
    pub window_pick_slot: u8,
    /// +55: `cursor_at` to set when `window_pick_count` > 0, in
    /// `custom::Custom`'s own encoding (0..=9 a slot, `custom::OK` = 0xa).
    pub window_cursor: u8,
}

impl Fixture {
    pub fn flag(&self, bit: u8) -> bool {
        self.flags & bit != 0
    }
}

/// The descriptor's actual base address: `crate::fixture_ptr()`, not the
/// literal `ADDR`. Reading through that function's own reference to
/// `BATTLE_MARKER` is what keeps the reservation from being linked away
/// (see that static's doc comment in main.rs) -- an earlier cut of this
/// read a hardcoded literal address instead, which compiled fine but let
/// the linker drop the reservation entirely since nothing referenced it.
/// `debug_assert_eq!` below still checks the two agree, so a future change
/// that moves `BATTLE_MARKER` and breaks FIXTURE.md's contract fails loudly
/// in a debug build rather than silently reading someone else's memory.
fn base() -> usize {
    let p = crate::fixture_ptr() as usize;
    debug_assert_eq!(p, ADDR, "BATTLE_MARKER's fixture half did not land at FIXTURE.md's 0x02000040");
    p
}

unsafe fn r8(off: usize) -> u8 {
    unsafe { core::ptr::read_volatile((base() + off) as *const u8) }
}
unsafe fn r16(off: usize) -> u16 {
    unsafe { core::ptr::read_volatile((base() + off) as *const u16) }
}
unsafe fn r32(off: usize) -> u32 {
    unsafe { core::ptr::read_volatile((base() + off) as *const u32) }
}

/// Read the descriptor at `ADDR`. `None` when the magic is absent, which is
/// the default: every existing capture and every `demo-*` build leaves this
/// region zero, so a plain build with no fixture poked in behaves exactly as
/// it does today (AUDIT pair 17's "when absent, behave exactly as the
/// default build does today").
///
/// Volatile reads throughout: the harness writes this region with per-frame
/// `--cheat addr:val16` pokes rather than once, so nothing here may be
/// hoisted, reordered around, or assumed constant by the optimiser.
pub fn read() -> Option<Fixture> {
    unsafe {
        if r32(0) != MAGIC {
            return None;
        }
        let mut hand = [0u8; 5];
        for (i, h) in hand.iter_mut().enumerate() {
            *h = r8(13 + i);
        }
        let mut deck = [0u8; 5];
        for (i, d) in deck.iter_mut().enumerate() {
            *d = r8(35 + i);
        }
        // NOT IN FIXTURE.md, offset +48: see `deck_codes`'s own doc.
        let mut deck_codes = [0u8; 5];
        for (i, c) in deck_codes.iter_mut().enumerate() {
            *c = r8(48 + i);
        }
        Some(Fixture {
            enemies: r8(4),
            enemy_kind: r8(5),
            enemy_col: r8(6),
            enemy_row: r8(7),
            megaman_hp: r16(8),
            megaman_col: r8(10),
            megaman_row: r8(11),
            hand_count: r8(12),
            hand,
            gauge: r8(18),
            flags: r8(19),
            art_entry: r16(20),
            art_timer: r16(22),
            scroll_xq: r16(24),
            scroll_yq: r16(26),
            gauge_tick: r16(28),
            fire_frame: r16(30),
            enemy_hp: r16(32),
            deck_count: r8(34),
            deck,
            start_state: r8(40),
            result_level: r8(41),
            result_frames: r16(42),
            result_zenny: r16(44),
            banner_at: r16(46),
            deck_codes,
            // NOT IN FIXTURE.md, offsets +53..+55: see `window_pick_count`'s
            // own doc.
            window_pick_count: r8(53),
            window_pick_slot: r8(54),
            window_cursor: r8(55),
        })
    }
}

// ---------------------------------------------------------------------------
// THE DESCRIPTOR TABLE (AUDIT pair 17, ticket step 3).
//
// Every existing `demo-*` fixture's bytes, offset by offset, so a harness
// wanting to reproduce one has the numbers rather than having to re-derive
// them from `battle.rs`'s cfg sites. `art_entry`/`art_timer`/`scroll_xq`/
// `scroll_yq` are 0xFFFF (all four) wherever the demo feature's own
// `prime_backdrop` call is excluded from seeding -- the backdrop keeps
// `Backdrop::new`'s own fresh-battle defaults instead. `enemy_hp` is this
// module's own reserved-region addition (see the field's doc above); every
// other column is a real FIXTURE.md field. `hand` lists only the
// `hand_count` chip ids that matter; the rest of the 5-byte array is 0.
//
// magic is 0x46495854 for every row below; omitted from the table.
//
//                        enemies kind col row  hp  mcol mrow hand(ids)      gauge flags(bin)  art_entry art_timer scroll_xq scroll_yq fire_frame enemy_hp
// demo-hudmatch             1     0    5   3   60    3    2  [1]              1  0b00010000     5         4        424       724        --        0 (40)
// demo-custmatch            1     0    5   3  100    3    2  []               1  0b00010001     0xFFFF  0xFFFF    0xFFFF    0xFFFF      --        0 (40)
// demo-cardname           (same as demo-custmatch in EVERY column above -- `demo-cardname` is a
//                           Cargo feature alias for `demo-custmatch` with no cfg site of its OWN
//                           in battle.rs. It DOES have one in custom.rs though -- the
//                           `cfg!(feature = "demo-cardname")` at the window's cursor_at, which
//                           this comment used to miss entirely before this ticket (see the
//                           WAVE 3 ADDITIONS block below: window_cursor is the one byte where
//                           these two rows actually differ).)
// demo-resultmatch          1     0    5   3   60    3    2  []               0  0b00010001     0xFFFF  0xFFFF    0xFFFF    0xFFFF      --        0 (40)
// demo-open                 3     0    4   1   60    2    2  []               0  0b00000001     0xFFFF  0xFFFF    0xFFFF    0xFFFF      --        0 (40)
// demo-field                1     0    5   2  100    2    2  [1]              0  0b00010001     5         4        424       724        --    0xFFFF
// demo-banner                0    --  --  --  100    2    2  []               0  0b00010111     0xFFFF  0xFFFF    0xFFFF    0xFFFF      --        --
// demo-sterile,demo-cannon,
//   demo-auto                0    --  --  --  100    2    2  [1]              0  0b00011111     0xFFFF  0xFFFF    0xFFFF    0xFFFF      90        --
//
// flags legend: bit0 FLAG_OPEN_WINDOW, bit1 FLAG_BLANK_HUD, bit2
// FLAG_BLANK_BACKDROP, bit3 FLAG_AUTO_FIRE, bit4 FLAG_SKIP_INTRO (written
// low-to-high, so demo-hudmatch's 0b00010000 is "skip intro, nothing else").
//
// demo-open is the ONE row with FLAG_SKIP_INTRO unset: it exists to compare
// the real white-hold-and-ramp opening, so it plays it, exactly like the
// default release build.
//
// demo-hudmatch is the ONE row with FLAG_OPEN_WINDOW unset: its capture
// holds a full gauge and never opens the chip window (battle.rs's own
// `!cfg!(feature = "demo-hudmatch")` guard on the gauge-pause branch, which
// this flag reproduces).
//
// WAVE 3 ADDITIONS (this ticket, AUDIT 6/14/17/FIXTURE.md's own "Fields +32
// onward were added after wave 2" note): deck_count/deck (FIXTURE.md +34/
// +35), start_state/result_level/result_frames/result_zenny (+40/+41/+42/
// +44), banner_at (+46) are now real FIXTURE.md fields, read by `read()`
// above. deck_codes (+48, NOT IN FIXTURE.md) and window_pick_count/
// window_pick_slot/window_cursor (+53/+54/+55, NOT IN FIXTURE.md) are this
// module's own reserved-region additions, same precedent as `enemy_hp`
// before it was published -- see each field's own doc for why the published
// contract does not reach far enough on its own. Every row not listed below
// leaves all of these at their defaults (deck_count 0, start_state 0,
// banner_at 0xFFFF, window_pick_count 0) and is unaffected.
//
// demo-custmatch / demo-cardname: deck_count 5, deck [5, 4, 71, 54, 1]
//   (CHIP_VULCAN, CHIP_AIRSHOT, CHIP_SWORD, CHIP_MINIBOMB, CHIP_CANNON --
//   Vulcan1, AirShot, Sword, MiniBomb, Cannon, in the capture's own slot
//   order), deck_codes [3, 0xFF, 18, 0xFF, 0xFF] (only Vulcan1 and Sword
//   need overriding -- AirShot/MiniBomb/Cannon's captured codes already
//   equal their own `codes[0]`; see `deck_codes`'s own doc for the numbers),
//   window_pick_count 1, window_pick_slot 4 (the Cannon, last of the five
//   offered), window_cursor demo-custmatch=0xa (OK) / demo-cardname=0 (the
//   first slot, the only way to see the card's NAME rather than the OK
//   confirmation message). window_cursor is the ONE byte that actually
//   distinguishes these two rows -- everything else in their descriptor,
//   this addition included, is identical.
// demo-resultmatch: start_state 1, result_level 2, result_frames 1760,
//   result_zenny 100 (RESULTMATCH_TIME/RESULTMATCH_ZENNY/the hardcoded 2 in
//   battle.rs's own demo-resultmatch cfg site, battle.rs:1993).
// demo-banner: banner_at 100 (BANNER_DEMO_AT).
//
// VERIFIED BYTE-IDENTICAL (2026-09-08), ticket step 3: a plain (no `demo-*`
// feature) build with the demo-hudmatch/demo-field/chip-fixture rows above
// poked into RAM (as 16-bit halfword `--cheat`s, two bytes at a time -- see
// the ticket report for the exact command) was captured for 220 frames
// alongside the matching `demo-*` feature build and diffed every frame with
// `tools/chip_compare.py`'s `diff_frames`. All three: ZERO differing pixels
// over 200 CONSECUTIVE frames once clear of the intro's own first ~8
// frames. Within those first frames, 1-2 frames differ by a few thousand
// px at most -- root-caused to a sub-frame boot-timing difference between
// the fixture-driven and cfg-driven code paths in `Battle::new` (the same
// class of "boot length moves with the compiler" sensitivity AUDIT pair 1
// exists to solve by aligning on `BATTLE_MARKER` rather than raw capture
// frame index, not a state/logic defect in this module -- confirmed by a
// control diff against the untouched pre-ticket `demo-hudmatch` build,
// which matches this ticket's `demo-hudmatch` build pixel-for-pixel with no
// fixture involved at all). See the ticket report for the full numbers.
//
// WAVE 3 VERIFICATION (2026-09-08), this ticket's step 2: the same
// methodology, marker-aligned (`--watch 0x02000000:8:<file>`, aligned on the
// first capture frame reading `BATTLE_MAGIC` on EACH side separately, then
// diffed battle-frame-for-battle-frame rather than raw capture index --
// belt-and-braces over wave 2's raw-index diff, and it matters: demo-banner
// MUST be built `--features demo-sterile,demo-banner` together (confirmed
// against tools/build_roms.sh/regress.py, which never build it alone) --
// blanking the backdrop and HUD measurably shortens `Battle::new`'s own
// asset-loading cost, which is why a `demo-banner`-alone build's marker
// landed 7 capture-frames later than the correctly-blanked one before this
// was caught) over 200 battle-frames (10..209):
//   demo-resultmatch: 0 px, 200/200 frames -- BYTE-IDENTICAL.
//   demo-banner:      0 px, 200/200 frames -- BYTE-IDENTICAL.
//   demo-custmatch:   371 px total, 2 of 200 frames nonzero (battle-frames
//     125 and 134; 112 px and 259 px respectively -- 0.0005% of the
//     76,800,000 px compared). NOT byte-identical.
//   demo-cardname:    862 px total, 2 of 200 frames nonzero (the SAME two
//     battle-frames, 125 and 134; 569 px and 293 px). NOT byte-identical.
//
// demo-custmatch/demo-cardname's residual, investigated but NOT fully
// root-caused -- reported honestly per AUDIT pair 11 rather than rounded to
// "close enough": both anomalies sit in the card-picture region (roughly
// x152-207 x y15-40 depending on frame, PICTURE_BANK's content -- the "CHIP
// DATA TRANSMISSION" message card for demo-custmatch, the highlighted
// Vulcan1 card for demo-cardname), are fully deterministic and reproducible
// (a capture diffed against a second capture of the SAME rom is bit-exact),
// are NOT a marker/boot-alignment artifact (both sides' `BATTLE_MAGIC`
// lands on the identical capture frame, delta 0 -- unlike the demo-banner
// build mistake above, which this two would have looked like if it were the
// same class of bug), and PERSIST unchanged when the fixture's `deck`/
// `deck_codes` are dropped to 0 (falling back to the ordinary shuffled
// folder) -- so the cause is not the deck-construction code added by this
// ticket. They are the FIRST fixture-driven chip-window opens any capture
// has ever exercised: every fixture wave 2 verified either never opens the
// window (`demo-hudmatch`, `FLAG_OPEN_WINDOW` unset) or opens it too late to
// reach within a short capture (`demo-open`/`demo-field`, gauge starts
// empty, ~1260 frames to fill) -- so `Custom::open()`/`Custom::update()`'s
// own `pending_palettes` queue (pushed by `draw_card()` during `open()`,
// not drained until the FOLLOWING `update()` call -- see that method's own
// code) was never diffed byte-for-byte against anything before this ticket,
// fixture-driven or not. Worth a closer look with more time than this
// ticket had; see the ticket report.
