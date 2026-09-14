//! AUDIT pairs 6, 14, 17 / FIXTURE.md: one ROM, any fixture.
//!
//! Every fixture used to be a `demo-*` cargo feature that baked one state
//! into its own build. This module is the runtime replacement: the harness
//! writes a 64-byte descriptor into EWRAM at a fixed address before the ROM
//! boots (and keeps writing it, frame by frame, so it survives whatever the
//! emulator's cheat mechanism does), and `read()` parses it once at startup.
//! `Battle::new` and the per-frame logic in `battle.rs` take everything --
//! enemies, positions, HP, hand, gauge, flags, backdrop/gauge seeds -- from
//! the descriptor when one is present, and fall back to the plain release
//! build's own behaviour when it is absent. The `demo-*` features and every
//! `cfg!(feature = "demo...")` site that used to gate them in `main.rs`/
//! `battle.rs`/`custom.rs` are gone (AUDIT pair 17 prune ticket, once the
//! harness reproduced every check they covered through descriptors instead)
//! -- the table below is kept as the historical record of what each one's
//! bytes were, since the harness's own descriptors for the ported checks
//! (`opening`/`mettaur`/`cannon`/`cursor` in tools/harness.py) are taken
//! from it verbatim.
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
const MAGIC: u32 = 0x4649_5854; // provenance: derived -- this project's own protocol choice (FIXTURE.md), not a ROM fact; "FIXT" chosen freely, fixed once the harness cheats above were written against it

/// Base address of the descriptor, per FIXTURE.md.
pub const ADDR: usize = 0x0200_0040; // provenance: derived -- this project's own protocol choice (FIXTURE.md): EWRAM's base plus BATTLE_MARKER's own 64-byte reservation (see main.rs's BATTLE_MARKER doc), not a ROM address

/// bit0: open with the chip window (gate the gauge-pause -> chip-window-open
/// sequence; UNSET reproduces `demo-hudmatch`'s own special case, which
/// freezes a full gauge and never opens the window -- see `read()`'s doc and
/// the descriptor table below).
pub const FLAG_OPEN_WINDOW: u8 = 1 << 0; // provenance: derived -- this project's own protocol bit assignment (FIXTURE.md), not a ROM fact
/// bit1: blank HUD. UNSET means the real HUD (`HudTiles`) is always drawn
/// with a descriptor -- AUDIT pair 6: the old sterile arena drew NOTHING at
/// all where canon shows the HP box (no stub currently exists in this code
/// to draw a bare "100" either; see the report), which made every chip
/// comparison a box instead of a full screen. SET reproduces
/// `demo-sterile`'s `hud_tiles: None`.
pub const FLAG_BLANK_HUD: u8 = 1 << 1; // provenance: derived -- this project's own protocol bit assignment (FIXTURE.md), not a ROM fact
/// bit2: blank backdrop. Reproduces the old `demo-sterile` feature's WHOLE
/// non-HUD background, not just the `backdrop` module: `backdrop: None`,
/// the field layer (`self.bg`) replaced with a blank tilemap, and the
/// hand-chip icon object suppressed (`hand_icon_palette: None`) -- exactly
/// the three things that feature used to gate. Broader than its name
/// suggests; flagged in the report as worth a name/scope check with
/// FIXTURE.md's author.
pub const FLAG_BLANK_BACKDROP: u8 = 1 << 2; // provenance: derived -- this project's own protocol bit assignment (FIXTURE.md), not a ROM fact
/// bit3: auto-fire the hand, on the schedule `fire_frame` seeds -- see its
/// own field doc.
pub const FLAG_AUTO_FIRE: u8 = 1 << 3; // provenance: derived -- this project's own protocol bit assignment (FIXTURE.md), not a ROM fact
/// bit4: skip the white intro. SET reproduces every `demo-*` fixture's own
/// legacy short black ramp (`SCREEN_FADE_FRAMES`'s `demo && !demo-open`
/// branch, `0x10 * 2` = 32 frames); UNSET plays the real 71-frame white hold
/// + 14-frame ramp, which is what `demo-open` and the default release build
/// already do.
pub const FLAG_SKIP_INTRO: u8 = 1 << 4; // provenance: derived -- this project's own protocol bit assignment (FIXTURE.md), not a ROM fact
/// bit5: resolve. An enemy-less arena whose fight is already decided: `over`
/// fires on the battle's first frame and the fight runs its whole end
/// sequence (ENEMY DELETED banner, then the RESULT window 110 frames later)
/// exactly as a fixture whose one enemy was killed before frame 0 would.
/// This is the zero-enemy arena rows' stand-in for the canon side's own
/// history, which is a battle whose enemy was deleted and whose all-dead
/// check therefore advances: on the `field` row's own canon capture the
/// banner sequencer enters its RESULT countdown 0x0C at canon frame 47 and
/// the ENEMY DELETED banner runs canon 49..106 -- the real ROM resolves, so
/// the fixture side has to be able to. Without the bit an empty `enemies`
/// still holds the fight open forever (the chip-window fixtures depend on
/// that: see battle.rs's own comment on `over`).
pub const FLAG_RESOLVE_OVER: u8 = 1 << 5; // provenance: peeked -- canon's own deleted-enemy battle resolves (sequencer 0x08->0x0C at canon 47, watched on the field row's own canon capture, 2026-09-12, TODO F8); the bit assignment itself is this project's protocol
/// bit6: the battle HUD is LIVE on this row's canon side at frame 0 -- canon's
/// battle-HUD element mask `dword_20352C0` (eStruct2035280+0x40, dispatched
/// every frame by sub_801BEE0, asm00_2.s:25540-25563) still has element 14,
/// the emotion window (updater sub_801CADC asm00_2.s:25577, draw sub_801CDEC
/// asm00_2.s:25627), enabled. Needed ONLY because a zero-enemy arena has no
/// counterpart in canon (canon never fields an empty enemy list), so nothing
/// in such a fixture says which side of the HUD teardown its canon capture
/// sits on: the `popup` row's canon side is a live battle whose enemy was
/// deleted on a ROM patched never to conclude (mask 0x4497 on all 125 frames,
/// bit14=1), and the 43 chip rows' canon side is `afterdissolve_0x0c`, a
/// battle already past the teardown (mask 0x8084 on all 47 frames, bit14=0) --
/// two different canon states behind byte-identical descriptors. A fixture
/// that fields an enemy needs no bit: canon's HUD is live whenever a battle
/// has one, so `enemies` non-empty implies it (see battle.rs's `hud_live`).
pub const FLAG_HUD_LIVE: u8 = 1 << 6; // provenance: peeked -- canon's own element mask at 0x020352C0 (--watch 0x20352C0:4, F27b): 0x4497 on every frame of the popup row's canon capture, 0x8084 on every frame of the chip rows'; the bit assignment itself is this project's protocol

/// State-trace export enable (T1b): when set, the main loop writes the
/// TRC2 block at 0x02000080 every frame; when clear, no trace store
/// executes on any path, so pixel rows run byte-identical to a build
/// without the export (field integrated back at 158950). Delivered
/// per-frame by the harness's own descriptor cheats like every other
/// flag, so it survives boot; tools/trace.py sets it on recordings only.
/// Bit 7 is the last free bit of the flags byte (bits 0..6 taken above).
/// NOT IN FIXTURE.md: a record-time knob, not battle setup -- pixel-row
/// descriptors leave it clear and never mention it.
/// Read live once per battle via `trace_enabled`, never via `Fixture`:
/// `read()` runs once at startup and the bit is stable after that, while
/// a per-frame re-read would put a load on the timed path every frame.
/// Provenance of the bit assignment is this project's own protocol.
pub const FLAG_TRACE: u8 = 1 << 7; // provenance: derived -- this project's own protocol bit assignment (the last free flags bit; see FLAG_TRACE's doc), not a ROM fact

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
    /// +56 FIXTURE.md (AUDIT wave 3c item 2): when `start_state` = 1, frames
    /// of the RESULT sequence already elapsed at boot. 0 = setup at boot
    /// (the slide itself starts 16 frames later -- `results::SLIDE_HOLD`);
    /// 0xFFFF = settled (the old `demo-resultmatch` picture). See
    /// `results::Shown::fast_forward`.
    pub result_elapsed: u16,
    /// +58 FIXTURE.md (AUDIT wave 3d ticket): the real ROM's primary RNG
    /// state (`ePrimaryRngSeed`, EWRAM 0x020013f0) at the capture's own
    /// frame 0, peeked from the canon state so an RNG-gated enemy takes the
    /// same decisions on both sides -- see `ai::Rng`'s own doc for the
    /// generator this seeds and how the value below was measured. 0 = this
    /// project's own default seed (`ai::DEFAULT_SEED`, `SeedRNG`'s own
    /// constant), not literal zero -- same "0 = sensible default" convention
    /// as `enemy_hp` above.
    pub rng: u32,
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
    /// NOT IN FIXTURE.md, offset +53. The old `demo-custmatch` feature's own
    /// capture already had ONE offered chip picked (the Cannon, slot 4) with
    /// the cursor resting on OK when the window opened; `demo-cardname` was
    /// the identical window with the cursor on the first slot instead, to
    /// show the card's NAME rather than the OK confirmation message (its own
    /// `cfg!(feature = "demo-cardname")` site in `custom.rs`, gone along
    /// with every other `demo-*` cfg site -- AUDIT pair 17 prune ticket; the
    /// two rows now differ only in `window_cursor`, see CUSTMATCH_ROW/
    /// CARDNAME_ROW in tools/harness.py). No FIXTURE.md field
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
    /// NOT IN FIXTURE.md, offset +62: the enemy's `CurState` byte
    /// (`BattleObject` +0x08, `BattleObject.inc:40`), peeked from the canon
    /// capture at the row's own `canon_ref`, for a fixture compared against
    /// a mid-battle state whose virus is frozen mid-attack under the custom
    /// screen's pause (`BattlePaused` reads 1 there, so canon's object skips
    /// its update and holds whatever it held). 0 = no override (this
    /// project's own fight starts every virus in its spawn animation).
    pub enemy_state: u8,
    /// NOT IN FIXTURE.md, offset +63: the enemy's `CurAction` byte (+0x09).
    /// Same sentinel (0 = no override). The animation comes with the action
    /// (`battle.rs` replays the matching `AttackSpec`, whose own `anim` is
    /// what canon's `CurAnim` indexes), not as a third byte there was no
    /// room for.
    pub enemy_action: u8,
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

/// Byte offset of the flags byte inside the descriptor (the same byte
/// `read()` parses as `flags` with its own `r8(19)`): the one address
/// `trace_enabled` reads.
const FLAGS_OFFSET: usize = 19; // provenance: derived -- this project's own descriptor layout (FIXTURE.md +19 flags; the offset read() already reads)

/// Live read of the trace-enable bit (T1b): one volatile byte load of
/// the harness-poked descriptor's flags, called ONCE per battle by main
/// (the descriptor is stable across frames) -- never read via the
/// startup `Fixture`. Clear (every pixel-row descriptor, every boot
/// with no descriptor) means the frame loop takes the off branch and no
/// trace store executes anywhere.
pub fn trace_enabled() -> bool {
    unsafe { r8(FLAGS_OFFSET) & FLAG_TRACE != 0 }
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
            result_elapsed: r16(56),
            rng: r32(58),
            deck_codes,
            // NOT IN FIXTURE.md, offsets +53..+55: see `window_pick_count`'s
            // own doc.
            window_pick_count: r8(53),
            window_pick_slot: r8(54),
            window_cursor: r8(55),
            // NOT IN FIXTURE.md, offsets +62/+63: see `enemy_state`'s doc.
            enemy_state: r8(62),
            enemy_action: r8(63),
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
//   battle.rs's own demo-resultmatch cfg site, battle.rs:1993),
//   result_elapsed 0 (+56, AUDIT wave 3c item 2's own new field -- see its
//   doc above). 0 is the DEFAULT (this row predates the field, and the "0
//   px, 200/200 frames" byte-identical verification below already used it
//   implicitly, since absent/unset always reads back 0 from a
//   zero-initialised descriptor buffer) -- it reproduces exactly what this
//   row always has: the window's slide-in starting fresh on the fixture's
//   own first battle frame, same as `demo-resultmatch`'s own cfg-driven
//   code path (which does not read this field at all and is therefore
//   unaffected by its addition either). `result_elapsed` is for a NEW
//   capability this row does not itself need: landing the capture
//   mid-slide (or pre-settled, 0xFFFF) instead of only at "fresh" or
//   "however far a many-frame capture happened to carry it".
// demo-banner: banner_at 100 (BANNER_DEMO_AT).
//
// AUDIT WAVE 3D ADDITION (this ticket): rng (+58, NEW FIXTURE.md field, see
// `Fixture::rng`'s own doc). tools/harness.py's `mettaur` and `wave` rows
// both compare against the SAME real recipe -- STERILE+PAUSED+ALIVE,
// script "Start@10" (mettaur also passes --disable-bg, wave --disable-obj,
// neither of which can affect CPU-side RNG state) -- so both take the SAME
// peeked value:
//   rng = 0xdd340be4, ePrimaryRngSeed (EWRAM 0x020013f0) read at CAPTURE
//   frame 0, i.e. immediately after `--loadstate /tmp/pausedwithcannon.state`
//   and before the "Start@10" script's own first press -- measured this
//   ticket with `--watch 0x020013f0:4:<file>` on that exact recipe (see
//   `ai::Rng`'s own doc for the full 220-frame verification this value's
//   capture also produced). `mettaur`/`wave` do not draw from this seed
//   today regardless of its value (see `ai.rs`'s own module doc: neither
//   fixture's Mettaur ever reaches an RNG-gated branch), so this number
//   does not move either check's pixel count by itself -- written down here
//   so the tools agent can wire it into `fixture_cheats()`/these two rows
//   without re-deriving it, and so it is ready the day a fixture DOES need
//   it. The harness does not poke this field yet (`fixture_cheats()` is the
//   tools agent's own file, out of this ticket's ownership).
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
// demo-custmatch/demo-cardname's residual (RE-MEASURED, wave 3b's `zero-src`
// ticket, item 1 -- 2026-09-08). Reproduced exactly: 371/862 px on the same
// two frames (125, 134). The wave-3 note above ("both anomalies sit in the
// card-picture region... PICTURE_BANK's content") is WRONG for battle-frame
// 134 and only accidentally right for 125 -- corrected here rather than
// silently overwritten, per AUDIT pair 15 (don't encode a hypothesis as
// settled fact):
//   - PALETTE RAM IS RULED OUT. Watching the full 1024-byte palette region
//     (`--watch 0x05000000:0x400`) frame by frame around both residues finds
//     it BIT-IDENTICAL on every frame checked (118..136) on both sides --
//     the "card-picture PALETTE BANK" theory cannot be the cause, whichever
//     frame.
//   - Battle-frame 125's 112 px IS in the card-picture region (x152-207,
//     y39-40, inside REGION_PICTURE's 56x48 box at (152,9)) -- that part of
//     the old note holds.
//   - Battle-frame 134's 259 px is NOT: its bbox is x56-239, y15-17 -- the
//     picture region's OWN x-range is 152-208, so more than half this box
//     sits outside it, and the diff pattern (flat runs of one solid colour
//     swapped for another across dozens of x, e.g. (41,41,41) vs (0,0,82)
//     for 20+ consecutive pixels) is a tile-content/timing difference, not a
//     palette-index difference -- confirmed by the palette-RAM watch above.
//   - THE ACTUAL MECHANISM, found by watching VRAM (`--watch
//     0x06000000:0x18000`) and the IO register block (`--watch
//     0x04000000:0x60`) frame by frame rather than just pixels: at
//     battle-frame 124 (one frame BEFORE the 125 pixel residue) a single
//     96-byte run of VRAM (0x06005340..0x0600539f, three 4bpp tiles)
//     differs between the two builds; battle-frame 125's own VRAM snapshot
//     is already back to byte-identical. The same IO register block reads a
//     torn, uniform garbage pattern (every register in the block reading
//     the SAME nonsense value, a different one per side) at that exact
//     frame and at battle-frame 133 (one frame before the 134 residue) --
//     nowhere else in 115..145. That pattern -- a VRAM write landing on a
//     different capture-frame between the two builds, self-correcting
//     immediately, with a torn IO-register read at the exact same moment --
//     is the signature of a vblank-boundary race: the two binaries are
//     different code (a `match self.fixture` per relevant frame in the
//     descriptor path vs. a `cfg!`-collapsed no-op in the feature build),
//     so they do not spend the same number of CPU cycles reaching the same
//     point in a frame, and a graphics write that happens to land near a
//     vblank boundary in one binary can cross it in the other.
//   - TESTED, NOT JUST THEORISED: caching `skip_intro()`/
//     `open_window_allowed()` as plain fields computed once in `Battle::new`
//     (removing their `match self.fixture` re-evaluation from `update()`/
//     `show()`'s own per-frame hot path) was tried as the direct fix this
//     mechanism implies. It changed the residue -- proof the mechanism
//     above is real -- but made it WORSE (924/1593 px, not 0), because it
//     just moves the vblank race to a different cycle count, not off the
//     boundary entirely. Reverted; not committed. Chasing cycle-exact parity
//     between a binary with runtime fixture dispatch and one where `cfg!`
//     deletes that dispatch at compile time is not a small fix, and forcing
//     one blind attempt at a time is how AUDIT pair 15 says not to work a
//     ticket -- reported honestly, open, rather than papered over.
//   - Deterministic and reproducible either way (a capture diffed against a
//     second capture of the SAME rom is bit-exact); NOT a marker/boot
//     alignment artifact (both sides' `BATTLE_MAGIC` lands on the identical
//     capture frame, delta 0); PERSISTS unchanged when the fixture's
//     `deck`/`deck_codes` are dropped to 0, so it is not the deck
//     construction this ticket's own predecessor added.
//
// THE DESCRIPTOR PATH AGAINST CANON (this ticket's second half, full screen,
// every frame, /tmp/chipselect.state, regress.py's own `window`/`card`
// recipe -- REAL+CHIPSELECT for `window`, REAL+CHIPSELECT+the same 5x-Left
// cursor-walk script `card`/`cursor` already use for `card`): using this
// module's own `deck`/`deck_codes`/`window_pick_*` fields (CUSTMATCH_ROW
// above plus the reserved-region additions, matching this file's own table)
// rather than the still-`pending_src` deck-less descriptor tools/harness.py
// currently builds:
//   window: lag 182 (searched 150..260 full-screen; the naive full-screen
//     search is a TRAP -- it finds a false minimum at lag 219 because the
//     field/backdrop area right of the window dominates the sum and
//     coincidentally scores lower there; the window's own half, x<112,
//     scores exactly 0 at 182 and nowhere near 0 at 219). At lag 182, x<112
//     (the window itself, the old check's own box) is 0 px over 200
//     CONSECUTIVE battle-frames (55..254), every frame, not just the old
//     check's 16 sampled ones. Full screen at the same lag: 1,296,726 px
//     over the same 200 frames, ALL of it at x>=112 -- confirmed by
//     scanning the right edge (0 up to x=112, climbing from x=113 on).
//   card: lag 86 (same trap avoided the same way -- naive full-screen search
//     finds 91, x<112 is 0 at 86 and 1530 at 91). x<112 is 0 px over 200
//     consecutive battle-frames (147..346, starting once the script's fifth
//     Left press has settled, same reasoning as regress.py's own
//     `check_card`). Full screen at lag 86: 798,796 px over the same 200
//     frames, again entirely at x>=112.
//   LOCALISATION: the x>=112 residue in both is the field/backdrop/HP area
//     the window does not cover, and it is not a defect in the window
//     fixture -- CUSTMATCH_ROW seeds no backdrop phase (art_entry etc. are
//     all 0xFFFF, a fresh `Backdrop::new`), while /tmp/chipselect.state is a
//     save state thousands of frames into a real battle with its own
//     scroll position, its own panel/enemy/HP state, none of which any
//     field of this descriptor asks to reproduce (contrast `FIELD_ROW`,
//     which exists precisely because `field`/`wave` DO need that). The
//     window/card checks were only ever built to prove the WINDOW, and now
//     do, at 0, full screen (of the box that matters) and every frame --
//     reproducing the rest of a real mid-battle screen behind it needs its
//     own fixture fields (backdrop seed + enemy/HP state matching
//     `/tmp/chipselect.state` specifically), out of this ticket's scope.
