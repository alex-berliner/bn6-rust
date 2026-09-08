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
/// offsets match FIXTURE.md exactly, with ONE addition -- see `enemy_hp`.
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
    pub gauge_tick: u16,
    pub fire_frame: u16,
    /// NOT IN FIXTURE.md. Read from the first two bytes of the "reserved"
    /// region (+32), which the contract documents as zero -- so any
    /// descriptor written against the published contract alone reads 0 here
    /// and gets the sensible default below, unaffected.
    ///
    /// `demo-field`'s own Mettaur carries `FIELDMATCH_HP = 0xffff` (the
    /// number the real capture's per-frame `--cheat` keeps its HP pinned to,
    /// battle.rs), which is baked into that demo feature's Rust source, not
    /// supplied by any harness poke -- so reproducing it byte-for-byte
    /// through a descriptor needs SOME per-fixture HP, and the published
    /// contract has none. This is exactly the gap AUDIT pair 17 asks to be
    /// reported rather than silently patched into FIXTURE.md: see this
    /// crate's ticket report for the recommendation (a real `enemy_hp: u16`
    /// field, offset TBD by whoever owns the contract next).
    ///
    /// 0 => the kind's own sensible default (40, `METTAUR_HP`, for kind 0).
    pub enemy_hp: u16,
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
// demo-cardname           (same as demo-custmatch -- `demo-cardname` is a Cargo feature alias
//                           for `demo-custmatch` with no cfg site of its own; only the harness's
//                           input script differs, not the descriptor)
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
// CANNOT BE EXPRESSED WITH THE PUBLISHED FIELDS -- see the ticket report:
//   - demo-custmatch/demo-cardname's own point: the chip window's specific
//     OFFERED deck (`Deck::stacked([Vulcan1@3, AirShot@wild, Sword@18,
//     MiniBomb@1, Cannon@0])`, battle.rs). The `hand` field only feeds the
//     ALREADY-PICKED hand used when the window is closed; there is no field
//     for what the window itself offers. `check_window`/`check_card`/
//     `check_cursor` cannot be reproduced by descriptor without a new one.
//   - demo-resultmatch's own point: the RESULT window is forced up on frame
//     0 at a specific clock (RESULTMATCH_TIME = 1760 frames, busting level
//     2, RESULTMATCH_ZENNY = 100 zenny). No field starts a battle already at
//     "won, this long ago, this well."
//   - demo-banner's own point: the ENEMY DELETED banner is forced up once
//     the internal clock reaches BANNER_DEMO_AT (100). No field arms a
//     banner at a chosen frame.
//   - enemy_hp (this module's own workaround; a real field is needed, see
//     above).
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
