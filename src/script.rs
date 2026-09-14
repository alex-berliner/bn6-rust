//! The two bytecode VMs of docs/coverage/plan-interpreters.md §3: the map-script
//! interpreter (3.1) and the chatbox text-script interpreter (3.2), each with its
//! dispatch table ported slot for slot.
//!
//! Both are genuine fetch-table-dispatch loops in canon: read the byte at the
//! cursor, scale it by 4 to index a word table, branch to the handler, and keep
//! fetching while the handler returns nonzero
//! (`MapScriptCommandJumptable` + `RunContinuousMapScript`,
//! reference/bn6f/asm/map_script_cutscene.s:3 and :1365-1385;
//! `TextScriptBytecodeJumptable` + `chatbox_interpreteAndDrawDialogChar`,
//! reference/bn6f/asm/chatbox.s:2392 and :373-472). Neither drives battle logic
//! -- chips and enemies run on §2's table dispatch -- but the overworld walk-up
//! in front of every battle runs on the map VM, and every piece of in-game text
//! (chip descriptions, the results screen, all later screens) runs on the text VM.
//!
//! WHAT IS WIRED. `Scripts` is owned by `Battle` and stepped once per frame at
//! the site battle.rs marks, which is where canon's map main loop reaches
//! `RunContinuousMapScript` (reference/bn6f/asm/asm03_1_0.s:1920) and where the
//! chatbox's per-frame update reaches its interpreter (chatbox.s:331). No harness
//! row starts a script -- our battle begins already inside the map, and this
//! fixture ROM has no map section -- so both VMs sit behind canon's own "nothing
//! installed" gates (`RunSecondaryContinuousMapScript`'s null test on
//! `eMapScriptState.SecondaryContinuousMapScriptPtr`, map_script_cutscene.s:1395,
//! and `chatbox_onUpdate`'s test on `oChatbox_Visible`, chatbox.s:280) and never
//! fetch. That makes the port pixel-neutral by construction, which is what §3.4
//! predicted ("what it replaces: nothing in src/ yet"); the full harness table is
//! the regression test for that claim.
//!
//! WHAT IS IMPLEMENTED. Map side: `end`, `jump`, the jump-if family the walk-up
//! stream actually contains (`jump_if_progress_in_range`, `jump_if_flag_set` and
//! `_clear`, the two range forms, `jump_if_mem_equals`), the battle-result gates
//! the post-battle script uses, the event-flag writers, and
//! `run_or_end_secondary_continuous_map_script`. Text side: the character path
//! (the single-byte form and the 0xE4 two-byte form) behind its print-speed
//! countdown, plus `ts_nop`, `ts_end`, `ts_key_wait`, `ts_newline`,
//! `ts_textspeed` and the two deterministic arms of `ts_jump`. Every other opcode
//! is stubbed to a named `Trap` recording canon's own symbol and stopping the
//! walk, rather than a guessed semantic: the row that needs one ports it from its
//! disassembly.
//!
//! Canon's script operands are ABSOLUTE addresses (a jump destination is a full
//! ROM pointer; `jump_if_mem_equals` carries a full RAM pointer), so `Image`
//! resolves an absolute address inside one owned blob and anything outside it is
//! `Trap::PointerOutsideImage` -- never a wrapped read of something else.
//!
//! The operand offsets and command sizes below come from the handlers' own cursor
//! arithmetic, which is the ground truth for the format: opcode 0x02's not-taken
//! arm is `add r7, #7` (map_script_cutscene.s:122) for its 1+1+1+4-byte form, and
//! opcode 0x07's three widths end at `add r7, r7, #11 / #12 / #14` (:298-311).

use agb::input::{Button, ButtonController};

/// `TestEventFlag`'s byte offset of a flag in the bitfield: `lsr r0, #3`
/// (reference/bn6f/asm/asm03_0.s:18525).
const EVENT_FLAG_BYTE_SHIFT: u16 = 3; // provenance: derived -- TestEventFlag, asm03_0.s:18525
/// `TestEventFlag`'s top-bit-first mask: `mov r1, #0x80` then `lsr` by the flag's
/// low 3 bits (asm03_0.s:18534-18536).
const EVENT_FLAG_BIT_MASK: u8 = 0x80; // provenance: derived -- TestEventFlag, asm03_0.s:18534
/// The flag count in the bitfield, from `TestEventFlagRange`'s bound:
/// `mov r1, #0x10; ldrh r0, [r2, #0xe]; mul r0, r1` -- 0x10 halfwords per flag
/// block, 0x100 bits overall (asm03_0.s:18731-18734).
const EVENT_FLAG_BITS: u32 = 0x100; // provenance: derived -- TestEventFlagRange bound, asm03_0.s:18731
/// The "flag number comes from a map-script memory param, not from the script"
/// sentinel: `cmp r4, #0xff` (map_script_cutscene.s:140).
const EVENT_FLAG_FROM_MEMORY: u8 = 0xff; // provenance: derived -- jump_if_flag_set, map_script_cutscene.s:140
/// `set/clear_event_flag_list`'s terminator: the walk stops on a negative signed
/// halfword (`cmp r0, #0; blt .doneSettingFlags`, map_script_cutscene.s:983-985).
const EVENT_FLAG_LIST_END: i16 = 0; // provenance: derived -- set_event_flag_list, map_script_cutscene.s:983
/// `eMapScriptState`'s zero-fill size at install time: `mov r1, #0x14;
/// bl ZeroFillByWord` (map_script_cutscene.s:1339-1341), covering
/// `Unk_00[8]`, the three script pointers and the trailing `Size` word
/// (reference/bn6f/include/structs/MapScriptState.inc:6-12).
const MAP_SCRIPT_STATE_BYTES: usize = 0x14; // provenance: derived -- ZeroFillByWord size, map_script_cutscene.s:1339
/// Stride of the memory-parameter halfwords the flag opcodes read with
/// `ldrh r4, [r5, r4]` off the state base (map_script_cutscene.s:146).
const MAP_SCRIPT_PARAM_STRIDE: u32 = 2; // provenance: derived -- jump_if_flag_set, map_script_cutscene.s:146
/// `MapScriptCmd_jump_if_mem_equals`'s sub-command selector at +1:
/// 0 byte, 1 halfword, 2 word (the `cmp r4, #1` / `cmp r4, #2` chain at
/// map_script_cutscene.s:281-285, named in
/// reference/bn6f/include/bytecode/map_script.inc:96-124).
const MEM_EQUALS_BYTE: u8 = 0; // provenance: derived -- ms_jump_if_byte_equals_subcmd, map_script.inc:96
const MEM_EQUALS_HALFWORD: u8 = 1; // provenance: derived -- ms_jump_if_hword_equals_subcmd, map_script.inc:110
const MEM_EQUALS_WORD: u8 = 2; // provenance: derived -- ms_jump_if_word_equals_subcmd, map_script.inc:124
/// The widths opcode 0x07's not-taken arm advances by, per sub-command:
/// `mov r4, #11` / `#12` / `#14` then `add r7, r7, r4` (map_script_cutscene.s:298-311).
const MEM_EQUALS_SIZES: [u32; 3] = [11, 12, 14]; // provenance: derived -- map_script_cutscene.s:299, 305, 310
/// `run_or_end_secondary_continuous_map_script`'s "end it" argument:
/// `cmp r4, #1` (map_script_cutscene.s:1270).
const SECONDARY_SCRIPT_END: u8 = 1; // provenance: derived -- map_script_cutscene.s:1270
/// How far `MapScriptCommandJumptable`'s own dispatcher will index:
/// `mov r4, #70; mul r4, r0` then `bne` past the call when the scaled index
/// reaches that count (map_script_cutscene.s:1371-1373). The table as
/// disassembled carries 71 words, so slot 0x46 is unreachable.
const MAP_SCRIPT_TABLE_BOUND: u8 = 70; // provenance: derived -- mov r4,#70 in the dispatch, map_script_cutscene.s:1371
/// The first command byte in the text VM: below this a byte is a character, and
/// the table index is `byte - TS_COMMANDS_START` (chatbox.s:391-403, and
/// `TS_COMMANDS_START = 0xE5` in reference/bn6f/include/bytecode/text_script.inc:12).
const TS_COMMANDS_START: u8 = 0xE5; // provenance: derived -- .equiv TS_COMMANDS_START, text_script.inc:12
/// The two-byte character introducer: `cmp r1, #0xe4` selects the arm that reads
/// one more byte and adds 0xE4 back to it (chatbox.s:440-459).
const TS_TWO_BYTE_CHAR: u8 = 0xE4; // provenance: derived -- interpreteAndDrawDialogChar, chatbox.s:440
/// What `chatbox_runScript` starts the per-character countdown at:
/// `mov r0, #2; strb r0, [r5, #oChatbox_TextScriptPrintSpeed]` (chatbox.s:1020-1021).
const TS_DEFAULT_PRINT_SPEED: u8 = 2; // provenance: derived -- chatbox_runScript, chatbox.s:1020
/// `chatbox_runScript`'s zero-fill of the box: `ldr r1, =0x230;
/// bl ZeroFillByWord` (chatbox.s:957-959).
const CHATBOX_STATE_BYTES: usize = 0x230; // provenance: derived -- chatbox_runScript, chatbox.s:958
/// `ts_end`'s nested-script cursor stack, `chatbox + 0x140 + 4 * (depth - 1)`
/// (chatbox.s:2445-2450).
const TEXT_NESTED_STACK_BASE: usize = 0x140; // provenance: derived -- chatbox_E6_end, chatbox.s:2446
const TEXT_NESTED_STACK_STRIDE: usize = 4; // provenance: derived -- `mov r2,#4; mul`, chatbox.s:2447
/// `ts_key_wait`'s "any of the ten buttons" mask when its operand is nonzero:
/// `ldr r1, =0x3ff` (chatbox.s:2538, `dword_8040F68`).
const KEY_WAIT_ANY_MASK: u16 = 0x3ff; // provenance: derived -- chatbox_E7_buttonhalt, chatbox.s:2538
/// Its "A or B on the press edge, else B held" arm: `mov r1, #3` for the edge
/// test, `mov r1, #2` for the held test (chatbox.s:2542-2546).
const KEY_WAIT_AB_MASK: u16 = 0b11; // provenance: derived -- chatbox.s:2542
const KEY_WAIT_B_BIT: u16 = 0b10; // provenance: derived -- chatbox.s:2544
/// `ts_jump`'s selector values at +1: 0 is the weighted-random pick (needs the
/// RNG and a byte table), 1 runs the stored script id, 2 stores byte@2 as the
/// script id and keeps going (`cmp r4, #1` / `#2`, chatbox.s:4202-4209, 4276-4292).
const TS_JUMP_RUN_STORED: u8 = 1; // provenance: derived -- chatbox_F0_jump, chatbox.s:4203
const TS_JUMP_STORE: u8 = 2; // provenance: derived -- chatbox_F0_jump, chatbox.s:4276

// ---------------------------------------------------------------------------
// Pieces both VMs share
// ---------------------------------------------------------------------------

/// One read-only blob at its canon absolute address, so a script operand that
/// carries an address resolves without pretending to own the whole bus.
#[derive(Clone, Copy)]
pub struct Image<'a> {
    /// The canon address of `bytes[0]` -- a ROM blob's `0x08xxxxxx` or a RAM
    /// window's `0x02xxxxxx`.
    pub base: u32,
    pub bytes: &'a [u8],
}

impl<'a> Image<'a> {
    /// The empty image: nothing installed, so every lookup traps.
    pub const EMPTY: Image<'static> = Image {
        base: 0,
        bytes: &[],
    };

    fn index(&self, addr: u32) -> Option<usize> {
        Some(addr.checked_sub(self.base)? as usize)
    }

    pub fn byte(&self, addr: u32) -> Option<u8> {
        self.bytes.get(self.index(addr)?).copied()
    }

    /// Little-endian halfword assembled from bytes, mirroring
    /// `ReadMapScriptHalfword`'s two `ldrb`/`orr` pairs
    /// (map_script_cutscene.s:1444-1456).
    pub fn halfword(&self, addr: u32) -> Option<u16> {
        let lo = self.byte(addr)? as u16;
        Some(lo | ((self.byte(addr + 1)? as u16) << 8))
    }

    /// Little-endian word assembled from bytes, mirroring `ReadMapScriptWord`'s
    /// four `ldrb`/`orr` pairs (map_script_cutscene.s:1476-1501).
    pub fn word(&self, addr: u32) -> Option<u32> {
        let b0 = self.byte(addr)? as u32;
        let b1 = self.byte(addr + 1)? as u32;
        let b2 = self.byte(addr + 2)? as u32;
        let b3 = self.byte(addr + 3)? as u32;
        Some(b0 | (b1 << 8) | (b2 << 16) | (b3 << 24))
    }
}

/// Why a walk stopped when it should not have. Named so a report can say which
/// canon opcode was reached instead of "it broke".
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Trap {
    /// A dispatch-table slot canon itself leaves NULL -- `MapScriptCommand-
    /// Jumptable` slots 0x37 and 0x3f are `.word NULL` (map_script_cutscene.s:59,
    /// :65), so reaching one is a wild cursor, not a missing port.
    NullTableEntry(&'static str, u8),
    /// A slot canon implements and this build does not; the name is canon's.
    Unimplemented(&'static str, u8),
    /// An operand address outside the image the VM holds.
    PointerOutsideImage(u32),
    /// `MapScriptCmd_call_native_function`'s `bx r4` on a script-supplied
    /// address (map_script_cutscene.s:1018-1031): this build has no native table
    /// to call into.
    NativeFunction(u32),
    /// A character was emitted with no tile writer attached. Canon's writer is
    /// the RAM-resident `sub_3006F8C`, called at chatbox.s:443.
    NoDrawTarget,
}

impl Trap {
    /// The trap's kind, for a report line.
    pub fn kind(&self) -> &'static str {
        match self {
            Trap::NullTableEntry(..) => "null table entry",
            Trap::Unimplemented(..) => "unimplemented opcode",
            Trap::PointerOutsideImage(_) => "pointer outside image",
            Trap::NativeFunction(_) => "native function call",
            Trap::NoDrawTarget => "no draw target",
        }
    }

    /// The canon symbol (or `image` / `native` / `draw`) and the opcode or
    /// address that caused the trap.
    pub fn subject(&self) -> (&'static str, u32) {
        match self {
            Trap::NullTableEntry(name, op) | Trap::Unimplemented(name, op) => (*name, *op as u32),
            Trap::PointerOutsideImage(addr) => ("image", *addr),
            Trap::NativeFunction(addr) => ("native", *addr),
            Trap::NoDrawTarget => ("draw", 0),
        }
    }
}

/// One handler's answer to "keep going?". Canon's loop branches on the handler's
/// `r0`: nonzero fetches the next command, zero ends this frame's walk
/// (`bne .mapScriptCommandLoop`, map_script_cutscene.s:1382;
/// `bne loop_803FF56`, chatbox.s:471).
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Step {
    /// The handler returned nonzero -- fetch the next command.
    Again,
    /// The handler returned zero -- this frame's walk is over.
    Stop,
    /// The handler is not ported or a trap fired: the walk stopped here and
    /// `Scripts::trap` says which.
    Trapped,
}

/// The state a map-script walk reads: event flags, the game-progress byte its
/// range test uses, the battle result its post-battle gates test, and the RAM
/// window its pointer operands read through. The offsets are canon's; the values
/// come from whatever the caller has.
pub struct MapWorld<'a> {
    /// `Toolkit->EventFlagsPtr`'s bitfield -- canon's `flags[flag >> 3]` tested
    /// against `0x80 >> (flag & 7)` (asm03_0.s:18521-18538).
    pub event_flags: &'a mut [u8],
    /// `GameState.GameProgress`, the byte opcode 0x02 range-tests
    /// (`ldrb r0, [r0, #oGameState_GameProgress]`, map_script_cutscene.s:107;
    /// reference/bn6f/include/structs/GameState.inc:29).
    pub game_progress: u8,
    /// `eStruct200A008_getBattleResult`'s value -- 0 won, 1 lost, 2 tied, 3 fled
    /// (map_script_cutscene.s:4188, 4198).
    pub battle_result: u8,
    /// The RAM window `jump_if_mem_equals`'s pointer operand reads through.
    /// Canon reads the bus; here an out-of-window pointer traps.
    pub ram: Image<'a>,
}

impl<'a> MapWorld<'a> {
    /// A world with no flags set and no RAM window: what this battle-only ROM
    /// has to offer a script.
    pub fn empty(event_flags: &'a mut [u8]) -> Self {
        Self {
            event_flags,
            game_progress: 0,
            battle_result: 0,
            ram: Image::EMPTY,
        }
    }

    /// `TestEventFlag` (asm03_0.s:18520).
    pub fn test_event_flag(&self, flag: u16) -> bool {
        let bit = flag as u32;
        if bit >= EVENT_FLAG_BITS {
            return false;
        }
        let byte = (bit >> EVENT_FLAG_BYTE_SHIFT as u32) as usize;
        let mask = EVENT_FLAG_BIT_MASK >> (bit & (EVENT_FLAG_BIT_MASK as u32 - 1));
        self.event_flags
            .get(byte)
            .is_some_and(|v| v & mask != 0)
    }

    /// `TestEventFlagRange`: every flag in `[first, first + count)` set -- the
    /// handler counts matches and jumps when the counter reaches the range
    /// (asm03_0.s:18733-18780).
    pub fn test_event_flag_range(&self, first: u16, count: u8) -> bool {
        (0..count).all(|i| self.test_event_flag(first + i as u16))
    }

    /// `SetEventFlag` / `ClearEventFlag`, the same addressing with `orr` /
    /// `bic` on the mask (asm03_0.s:18558-18596).
    fn write_event_flag(&mut self, flag: u16, set: bool) {
        let bit = flag as u32;
        if bit >= EVENT_FLAG_BITS {
            return;
        }
        let byte = (bit >> EVENT_FLAG_BYTE_SHIFT as u32) as usize;
        let mask = EVENT_FLAG_BIT_MASK >> (bit & (EVENT_FLAG_BIT_MASK as u32 - 1));
        if let Some(v) = self.event_flags.get_mut(byte) {
            *v = if set { *v | mask } else { *v & !mask };
        }
    }
}

// ---------------------------------------------------------------------------
// 3.1 The map-script VM
// ---------------------------------------------------------------------------

/// `MapScriptCommandJumptable` (map_script_cutscene.s:3-72, 71 word entries;
/// index = the fetched opcode byte). One variant per slot, in table order, each
/// cited to its handler -- the table has to stay the table even where the
/// handler is not ported, because an unported opcode still has to be named.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum MapCmd {
    /// 0x00 `MapScriptCmd_end` (:79) -- `mov r0, #0`, which ends the walk.
    End,
    /// 0x01 `MapScriptCutsceneCmd_jump` (:88) -- cursor = word at +1.
    Jump,
    /// 0x02 `MapScriptCutsceneCmd_jump_if_progress_in_range` (:103).
    JumpIfProgressInRange,
    /// 0x03 `MapScriptCutsceneCmd_jump_if_flag_set` (:134).
    JumpIfFlagSet,
    /// 0x04 `MapScriptCutsceneCmd_jump_if_flag_range_set` (:167).
    JumpIfFlagRangeSet,
    /// 0x05 `MapScriptCutsceneCmd_jump_if_flag_clear` (:195).
    JumpIfFlagClear,
    /// 0x06 `MapScriptCutsceneCmd_jump_if_flag_range_clear` (:227).
    JumpIfFlagRangeClear,
    /// 0x07 `MapScriptCutsceneCmd_jump_if_mem_equals` (:267), byte/halfword/word
    /// chosen by the sub-command byte at +1.
    JumpIfMemEquals,
    /// 0x08 `MapScriptCutsceneCmd_jump_if_key_item_in_range` (:322).
    JumpIfKeyItemInRange,
    /// 0x09 `MapScriptCutsceneCmd_jump_if_chip_count_in_range` (:356).
    JumpIfChipCountInRange,
    /// 0x0a `MapScriptCutsceneCmd_jump_if_battle_result_equals` (:4191).
    JumpIfBattleResultEquals,
    /// 0x0b `MapScriptCutsceneCmd_jump_if_battle_result_not_equal` (:4214).
    JumpIfBattleResultNotEqual,
    /// 0x0c `MapScriptCutsceneCmd_coordinate_trigger_equals_cmd_8035afa` (:402).
    CoordinateTriggerEquals,
    /// 0x0d `MapScriptCutsceneCmd_coordinate_trigger_not_equal_cmd_8035b44` (:447).
    CoordinateTriggerNotEqual,
    /// 0x0e `MapScriptCmd_jump_if_coord_interaction_value_equals` (:491).
    JumpIfCoordInteractionEquals,
    /// 0x0f `MapScriptCmd_jump_if_coord_interaction_value_not_equal` (:517).
    JumpIfCoordInteractionNotEqual,
    /// 0x10 `MapScriptCutsceneCmd_jump_if_current_navi_equals` (:4237).
    JumpIfCurrentNaviEquals,
    /// 0x11 `MapScriptCutsceneCmd_jump_if_current_navi_not_equal` (:4260).
    JumpIfCurrentNaviNotEqual,
    /// 0x12 `MapScriptCmd_jump_if_player_z_equals` (:542).
    JumpIfPlayerZEquals,
    /// 0x13 `MapScriptCmd_jump_if_player_z_not_equal` (:569).
    JumpIfPlayerZNotEqual,
    /// 0x14 `MapScriptCmd_jump_if_game_state_44_equals` (:596).
    JumpIfGameState44Equals,
    /// 0x15 `MapScriptCmd_jump_if_game_state_44_not_equal` (:621).
    JumpIfGameState44NotEqual,
    /// 0x16 `MapScriptCmd_jump_if_map_group_compare_last_map_group` (:649).
    JumpIfMapGroupEqualsLast,
    /// 0x17 `MapScriptCmd_switch_case_from_navi_stats_4c` (:686).
    SwitchCaseFromNaviStats,
    /// 0x18 `MapScriptCmd_cmd_8035cd6` (:723) -- `byte1 == sub_800B734()`.
    Cmd8035Cd6,
    /// 0x19 `MapScriptCmd_cmd_8035cf8` (:750) -- `byte1 != sub_800B734()`, the
    /// handler `battle_full`'s 14457 profiled instructions display under.
    Cmd8035Cf8,
    /// 0x1a `MapScriptCmd_jump_if_fade_active` (:772).
    JumpIfFadeActive,
    /// 0x1b `MapScriptCmd_jump_if_eStruct200a6a0_initialized` (:791).
    JumpIfStruct200a6a0Initialized,
    /// 0x1c `MapScriptCmd_jump_if_in_pet_menu` (:810).
    JumpIfInPetMenu,
    /// 0x1d `MapScriptCutsceneCmd_set_screen_fade` (:832).
    SetScreenFade,
    /// 0x1e `MapScriptCutsceneCmd_set_enter_map_screen_fade` (:861).
    SetEnterMapScreenFade,
    /// 0x1f `MapScriptCutsceneCmd_set_event_flag` (:881).
    SetEventFlag,
    /// 0x20 `MapScriptCutsceneCmd_clear_event_flag` (:906).
    ClearEventFlag,
    /// 0x21 `MapScriptCutsceneCmd_set_event_flag_range` (:931).
    SetEventFlagRange,
    /// 0x22 `MapScriptCutsceneCmd_clear_event_flag_range` (:952).
    ClearEventFlagRange,
    /// 0x23 `MapScriptCutsceneCmd_set_event_flag_list` (:971).
    SetEventFlagList,
    /// 0x24 `MapScriptCutsceneCmd_clear_event_flag_list` (:994).
    ClearEventFlagList,
    /// 0x25 `MapScriptCmd_call_native_function` (:1018) -- `bx` the word at +1
    /// with the word at +5 as the argument.
    CallNativeFunction,
    /// 0x26 `MapScriptCmd_start_cutscene` (:1037).
    StartCutscene,
    /// 0x27 `MapScriptCutsceneCmd_write_byte` (:1057).
    WriteByte,
    /// 0x28 `MapScriptCutsceneCmd_write_hword` (:1076).
    WriteHalfword,
    /// 0x29 `MapScriptCutsceneCmd_write_word` (:1095).
    WriteWord,
    /// 0x2a `MapScriptCutsceneCmd_write_gamestate_byte` (:1114).
    WriteGameStateByte,
    /// 0x2b `MapScriptCutsceneCmd_write_eStruct2001c04_byte` (:1135).
    WriteStruct2001c04Byte,
    /// 0x2c `MapScriptCutsceneCmd_load_gfx_anim` (:1157).
    LoadGfxAnim,
    /// 0x2d `MapScriptCutsceneCmd_load_gfx_anims` (:1175).
    LoadGfxAnims,
    /// 0x2e `MapScriptCutsceneCmd_load_map_gfx_anims_bg_anim` (:1189).
    LoadMapGfxAnimsBgAnim,
    /// 0x2f `MapScriptCutsceneCmd_terminate_one_or_all_gfx_anims` (:1209).
    TerminateGfxAnims,
    /// 0x30 `MapScriptCutsceneCmd_play_sound` (:5375).
    PlaySound,
    /// 0x31 `MapScriptCutsceneCmd_play_music` (:5390).
    PlayMusic,
    /// 0x32 `MapScriptCutsceneCmd_sound_cmd_80380ea` (:5411).
    SoundCmd80380Ea,
    /// 0x33 `MapScriptCutsceneCmd_sound_cmd_803810e` (:5431).
    SoundCmd803810E,
    /// 0x34 `MapScriptCutsceneCmd_stop_sound` (:5452).
    StopSound,
    /// 0x35 `MapScriptCutsceneCmd_give_or_take_item` (:5466).
    GiveOrTakeItem,
    /// 0x36 `MapScriptCutsceneCmd_do_pet_effect` (:1240).
    DoPetEffect,
    /// 0x37 `.word NULL` (:59).
    NullTable0x37,
    /// 0x38 `MapScriptCutsceneCmd_init_eStruct200a6a0` (:5573).
    InitStruct200a6a0,
    /// 0x39 `MapScriptCutsceneCmd_run_eStruct200a6a0_callback` (:5593).
    RunStruct200a6a0Callback,
    /// 0x3a `MapScriptCmd_run_or_end_secondary_continuous_map_script` (:1266).
    RunOrEndSecondaryScript,
    /// 0x3b `MapScriptCutsceneCmd_init_scenario_effect` (:5681).
    InitScenarioEffect,
    /// 0x3c `MapScriptCutsceneCmd_end_scenario_effect` (:5695).
    EndScenarioEffect,
    /// 0x3d `MapScriptCutsceneCmd_init_minigame_effect` (:5707).
    InitMinigameEffect,
    /// 0x3e `MapScriptCutsceneCmd_end_minigame_effect` (:5721).
    EndMinigameEffect,
    /// 0x3f `.word NULL` (:65).
    NullTable0x3f,
    /// 0x40 `MapScriptCmd_spawn_or_free_objects` (:1303).
    SpawnOrFreeObjects,
    /// 0x41 `MapScriptCutsceneCmd_add_bbs_message_range` (:5735).
    AddBbsMessageRange,
    /// 0x42 `MapScriptCutsceneCmd_add_mail_range` (:5805).
    AddMailRange,
    /// 0x43 `MapScriptCutsceneCmd_cmd_8038346` (:5827).
    Cmd8038346,
    /// 0x44 `MapScriptCutsceneCmd_add_request_range` (:6042).
    AddRequestRange,
    /// 0x45 `MapScriptCutsceneCmd_rush_food_cmd_80384A8` (:6067).
    RushFoodCmd80384A8,
    /// 0x46 `MapScriptCmd_start_on_next_frame` (:1321) -- the 71st slot, past the
    /// `mov r4, #70` bound of the dispatcher, so unreachable (:1371).
    StartOnNextFrame,
}

/// `MapScriptCommandJumptable`, entry for entry (map_script_cutscene.s:4-74).
pub const MAP_SCRIPT_JUMPTABLE: [MapCmd; 71] = [
    MapCmd::End,
    MapCmd::Jump,
    MapCmd::JumpIfProgressInRange,
    MapCmd::JumpIfFlagSet,
    MapCmd::JumpIfFlagRangeSet,
    MapCmd::JumpIfFlagClear,
    MapCmd::JumpIfFlagRangeClear,
    MapCmd::JumpIfMemEquals,
    MapCmd::JumpIfKeyItemInRange,
    MapCmd::JumpIfChipCountInRange,
    MapCmd::JumpIfBattleResultEquals,
    MapCmd::JumpIfBattleResultNotEqual,
    MapCmd::CoordinateTriggerEquals,
    MapCmd::CoordinateTriggerNotEqual,
    MapCmd::JumpIfCoordInteractionEquals,
    MapCmd::JumpIfCoordInteractionNotEqual,
    MapCmd::JumpIfCurrentNaviEquals,
    MapCmd::JumpIfCurrentNaviNotEqual,
    MapCmd::JumpIfPlayerZEquals,
    MapCmd::JumpIfPlayerZNotEqual,
    MapCmd::JumpIfGameState44Equals,
    MapCmd::JumpIfGameState44NotEqual,
    MapCmd::JumpIfMapGroupEqualsLast,
    MapCmd::SwitchCaseFromNaviStats,
    MapCmd::Cmd8035Cd6,
    MapCmd::Cmd8035Cf8,
    MapCmd::JumpIfFadeActive,
    MapCmd::JumpIfStruct200a6a0Initialized,
    MapCmd::JumpIfInPetMenu,
    MapCmd::SetScreenFade,
    MapCmd::SetEnterMapScreenFade,
    MapCmd::SetEventFlag,
    MapCmd::ClearEventFlag,
    MapCmd::SetEventFlagRange,
    MapCmd::ClearEventFlagRange,
    MapCmd::SetEventFlagList,
    MapCmd::ClearEventFlagList,
    MapCmd::CallNativeFunction,
    MapCmd::StartCutscene,
    MapCmd::WriteByte,
    MapCmd::WriteHalfword,
    MapCmd::WriteWord,
    MapCmd::WriteGameStateByte,
    MapCmd::WriteStruct2001c04Byte,
    MapCmd::LoadGfxAnim,
    MapCmd::LoadGfxAnims,
    MapCmd::LoadMapGfxAnimsBgAnim,
    MapCmd::TerminateGfxAnims,
    MapCmd::PlaySound,
    MapCmd::PlayMusic,
    MapCmd::SoundCmd80380Ea,
    MapCmd::SoundCmd803810E,
    MapCmd::StopSound,
    MapCmd::GiveOrTakeItem,
    MapCmd::DoPetEffect,
    MapCmd::NullTable0x37,
    MapCmd::InitStruct200a6a0,
    MapCmd::RunStruct200a6a0Callback,
    MapCmd::RunOrEndSecondaryScript,
    MapCmd::InitScenarioEffect,
    MapCmd::EndScenarioEffect,
    MapCmd::InitMinigameEffect,
    MapCmd::EndMinigameEffect,
    MapCmd::NullTable0x3f,
    MapCmd::SpawnOrFreeObjects,
    MapCmd::AddBbsMessageRange,
    MapCmd::AddMailRange,
    MapCmd::Cmd8038346,
    MapCmd::AddRequestRange,
    MapCmd::RushFoodCmd80384A8,
    MapCmd::StartOnNextFrame,
];

impl MapCmd {
    /// `MapScriptCommandJumptable[opcode]` -- the `lsl r0, #2; ldr r0, [r6, r0]`
    /// of the dispatch loop (map_script_cutscene.s:1376-1379), bounded by the
    /// `mov r4, #70` test (:1371) so slot 0x46 is `None` here exactly as it is
    /// unreachable there.
    pub const fn at(opcode: u8) -> Option<MapCmd> {
        if opcode < MAP_SCRIPT_TABLE_BOUND && (opcode as usize) < MAP_SCRIPT_JUMPTABLE.len() {
            Some(MAP_SCRIPT_JUMPTABLE[opcode as usize])
        } else {
            None
        }
    }

    /// Canon's own symbol for the slot, for trap messages and coverage notes.
    pub const fn symbol(self) -> &'static str {
        match self {
            MapCmd::End => "MapScriptCmd_end",
            MapCmd::Jump => "MapScriptCutsceneCmd_jump",
            MapCmd::JumpIfProgressInRange => "MapScriptCutsceneCmd_jump_if_progress_in_range",
            MapCmd::JumpIfFlagSet => "MapScriptCutsceneCmd_jump_if_flag_set",
            MapCmd::JumpIfFlagRangeSet => "MapScriptCutsceneCmd_jump_if_flag_range_set",
            MapCmd::JumpIfFlagClear => "MapScriptCutsceneCmd_jump_if_flag_clear",
            MapCmd::JumpIfFlagRangeClear => "MapScriptCutsceneCmd_jump_if_flag_range_clear",
            MapCmd::JumpIfMemEquals => "MapScriptCutsceneCmd_jump_if_mem_equals",
            MapCmd::JumpIfKeyItemInRange => "MapScriptCutsceneCmd_jump_if_key_item_in_range",
            MapCmd::JumpIfChipCountInRange => "MapScriptCutsceneCmd_jump_if_chip_count_in_range",
            MapCmd::JumpIfBattleResultEquals => "MapScriptCutsceneCmd_jump_if_battle_result_equals",
            MapCmd::JumpIfBattleResultNotEqual => {
                "MapScriptCutsceneCmd_jump_if_battle_result_not_equal"
            }
            MapCmd::CoordinateTriggerEquals => {
                "MapScriptCutsceneCmd_coordinate_trigger_equals_cmd_8035afa"
            }
            MapCmd::CoordinateTriggerNotEqual => {
                "MapScriptCutsceneCmd_coordinate_trigger_not_equal_cmd_8035b44"
            }
            MapCmd::JumpIfCoordInteractionEquals => {
                "MapScriptCmd_jump_if_coord_interaction_value_equals"
            }
            MapCmd::JumpIfCoordInteractionNotEqual => {
                "MapScriptCmd_jump_if_coord_interaction_value_not_equal"
            }
            MapCmd::JumpIfCurrentNaviEquals => "MapScriptCutsceneCmd_jump_if_current_navi_equals",
            MapCmd::JumpIfCurrentNaviNotEqual => {
                "MapScriptCutsceneCmd_jump_if_current_navi_not_equal"
            }
            MapCmd::JumpIfPlayerZEquals => "MapScriptCmd_jump_if_player_z_equals",
            MapCmd::JumpIfPlayerZNotEqual => "MapScriptCmd_jump_if_player_z_not_equal",
            MapCmd::JumpIfGameState44Equals => "MapScriptCmd_jump_if_game_state_44_equals",
            MapCmd::JumpIfGameState44NotEqual => "MapScriptCmd_jump_if_game_state_44_not_equal",
            MapCmd::JumpIfMapGroupEqualsLast => {
                "MapScriptCmd_jump_if_map_group_compare_last_map_group"
            }
            MapCmd::SwitchCaseFromNaviStats => "MapScriptCmd_switch_case_from_navi_stats_4c",
            MapCmd::Cmd8035Cd6 => "MapScriptCmd_cmd_8035cd6",
            MapCmd::Cmd8035Cf8 => "MapScriptCmd_cmd_8035cf8",
            MapCmd::JumpIfFadeActive => "MapScriptCmd_jump_if_fade_active",
            MapCmd::JumpIfStruct200a6a0Initialized => {
                "MapScriptCmd_jump_if_eStruct200a6a0_initialized"
            }
            MapCmd::JumpIfInPetMenu => "MapScriptCmd_jump_if_in_pet_menu",
            MapCmd::SetScreenFade => "MapScriptCutsceneCmd_set_screen_fade",
            MapCmd::SetEnterMapScreenFade => "MapScriptCutsceneCmd_set_enter_map_screen_fade",
            MapCmd::SetEventFlag => "MapScriptCutsceneCmd_set_event_flag",
            MapCmd::ClearEventFlag => "MapScriptCutsceneCmd_clear_event_flag",
            MapCmd::SetEventFlagRange => "MapScriptCutsceneCmd_set_event_flag_range",
            MapCmd::ClearEventFlagRange => "MapScriptCutsceneCmd_clear_event_flag_range",
            MapCmd::SetEventFlagList => "MapScriptCutsceneCmd_set_event_flag_list",
            MapCmd::ClearEventFlagList => "MapScriptCutsceneCmd_clear_event_flag_list",
            MapCmd::CallNativeFunction => "MapScriptCmd_call_native_function",
            MapCmd::StartCutscene => "MapScriptCmd_start_cutscene",
            MapCmd::WriteByte => "MapScriptCutsceneCmd_write_byte",
            MapCmd::WriteHalfword => "MapScriptCutsceneCmd_write_hword",
            MapCmd::WriteWord => "MapScriptCutsceneCmd_write_word",
            MapCmd::WriteGameStateByte => "MapScriptCutsceneCmd_write_gamestate_byte",
            MapCmd::WriteStruct2001c04Byte => "MapScriptCutsceneCmd_write_eStruct2001c04_byte",
            MapCmd::LoadGfxAnim => "MapScriptCutsceneCmd_load_gfx_anim",
            MapCmd::LoadGfxAnims => "MapScriptCutsceneCmd_load_gfx_anims",
            MapCmd::LoadMapGfxAnimsBgAnim => "MapScriptCutsceneCmd_load_map_gfx_anims_bg_anim",
            MapCmd::TerminateGfxAnims => "MapScriptCutsceneCmd_terminate_one_or_all_gfx_anims",
            MapCmd::PlaySound => "MapScriptCutsceneCmd_play_sound",
            MapCmd::PlayMusic => "MapScriptCutsceneCmd_play_music",
            MapCmd::SoundCmd80380Ea => "MapScriptCutsceneCmd_sound_cmd_80380ea",
            MapCmd::SoundCmd803810E => "MapScriptCutsceneCmd_sound_cmd_803810e",
            MapCmd::StopSound => "MapScriptCutsceneCmd_stop_sound",
            MapCmd::GiveOrTakeItem => "MapScriptCutsceneCmd_give_or_take_item",
            MapCmd::DoPetEffect => "MapScriptCutsceneCmd_do_pet_effect",
            MapCmd::NullTable0x37 => "NULL",
            MapCmd::InitStruct200a6a0 => "MapScriptCutsceneCmd_init_eStruct200a6a0",
            MapCmd::RunStruct200a6a0Callback => "MapScriptCutsceneCmd_run_eStruct200a6a0_callback",
            MapCmd::RunOrEndSecondaryScript => {
                "MapScriptCmd_run_or_end_secondary_continuous_map_script"
            }
            MapCmd::InitScenarioEffect => "MapScriptCutsceneCmd_init_scenario_effect",
            MapCmd::EndScenarioEffect => "MapScriptCutsceneCmd_end_scenario_effect",
            MapCmd::InitMinigameEffect => "MapScriptCutsceneCmd_init_minigame_effect",
            MapCmd::EndMinigameEffect => "MapScriptCutsceneCmd_end_minigame_effect",
            MapCmd::NullTable0x3f => "NULL",
            MapCmd::SpawnOrFreeObjects => "MapScriptCmd_spawn_or_free_objects",
            MapCmd::AddBbsMessageRange => "MapScriptCutsceneCmd_add_bbs_message_range",
            MapCmd::AddMailRange => "MapScriptCutsceneCmd_add_mail_range",
            MapCmd::Cmd8038346 => "MapScriptCutsceneCmd_cmd_8038346",
            MapCmd::AddRequestRange => "MapScriptCutsceneCmd_add_request_range",
            MapCmd::RushFoodCmd80384A8 => "MapScriptCutsceneCmd_rush_food_cmd_80384A8",
            MapCmd::StartOnNextFrame => "MapScriptCmd_start_on_next_frame",
        }
    }
}

/// `eMapScriptState` (0x02011E60, reached through `off_8036090` at
/// map_script_cutscene.s:1415). Held as raw bytes because canon's memory-param
/// halfwords are read off the state base itself -- `ldrh r4, [r5, r4]` (:146) --
/// so a param number aliases whatever field it lands on.
#[derive(Clone, Copy)]
pub struct MapScriptState {
    /// The whole blob, zero-filled the way `MapScriptController_Load` zeroes it
    /// (map_script_cutscene.s:1339-1341).
    pub raw: [u8; MAP_SCRIPT_STATE_BYTES],
}

/// `oMapScriptState_*` field offsets (reference/bn6f/include/structs/
/// MapScriptState.inc:9-12), matching the `str`s in
/// `MapScriptController_LoadDefault` (map_script_cutscene.s:1530-1536).
const ST_ON_INIT: usize = 0x8; // provenance: derived -- oMapScriptState_OnInitMapScriptPtr, MapScriptState.inc:9
const ST_CONTINUOUS: usize = 0xc; // provenance: derived -- oMapScriptState_ContinuousMapScriptPtr, MapScriptState.inc:10
const ST_SECONDARY: usize = 0x10; // provenance: derived -- oMapScriptState_SecondaryContinuousMapScriptPtr, MapScriptState.inc:11

impl MapScriptState {
    pub const fn new() -> Self {
        Self {
            raw: [0; MAP_SCRIPT_STATE_BYTES],
        }
    }

    fn ptr(&self, at: usize) -> u32 {
        u32::from_le_bytes([self.raw[at], self.raw[at + 1], self.raw[at + 2], self.raw[at + 3]])
    }

    fn set_ptr(&mut self, at: usize, value: u32) {
        self.raw[at..at + 4].copy_from_slice(&value.to_le_bytes());
    }

    /// `oMapScriptState_ContinuousMapScriptPtr` -- the pointer canon's watch
    /// reads as dword_2011E6C.
    pub fn continuous(&self) -> u32 {
        self.ptr(ST_CONTINUOUS)
    }

    /// `oMapScriptState_SecondaryContinuousMapScriptPtr`.
    pub fn secondary(&self) -> u32 {
        self.ptr(ST_SECONDARY)
    }

    /// The memory-param flag opcode 0x03/0x05/0x1f/0x20 read when their first
    /// operand is not 0xff (`ldrh r4, [r5, r4]`, map_script_cutscene.s:146).
    fn mem_param_flag(&self, param: u8) -> u16 {
        let at = param as usize;
        let lo = self.raw.get(at).copied().unwrap_or(0) as u16;
        let hi = self
            .raw
            .get(at + MAP_SCRIPT_PARAM_STRIDE as usize)
            .copied()
            .unwrap_or(0) as u16;
        lo | (hi << 8)
    }
}

/// The map-script VM: `RunContinuousMapScript` and its secondary twin
/// (map_script_cutscene.s:1365 / :1389) over one script image.
pub struct MapScriptVm<'a> {
    /// The script's bytes, at their canon address.
    pub code: Image<'a>,
    pub state: MapScriptState,
    /// The trap that last stopped a walk, if any.
    pub trap: Option<Trap>,
    /// Commands dispatched since `install`, for a report line.
    pub commands: u32,
    /// Canon's `r7`: the cursor. Held across the two legs of a frame's walk so
    /// opcode 0x3a can point the secondary leg at a new blob.
    cursor: u32,
}

impl<'a> MapScriptVm<'a> {
    /// A VM with no script installed -- what every harness row runs, since no
    /// row has a map.
    pub const fn new() -> Self {
        Self {
            code: Image::EMPTY,
            state: MapScriptState::new(),
            trap: None,
            commands: 0,
            cursor: 0,
        }
    }

    /// `StoreMapScriptsThenRunOnInitMapScript`'s install step: zero the state,
    /// then store the on-init and continuous pointers (map_script_cutscene.s:
    /// 1338-1344, where `r2 = MapScriptController_LoadDefault(idx)` supplies both).
    pub fn install(&mut self, code: Image<'a>, on_init: u32, continuous: u32) {
        self.code = code;
        self.state = MapScriptState::new();
        self.state.set_ptr(ST_ON_INIT, on_init);
        self.state.set_ptr(ST_CONTINUOUS, continuous);
        self.trap = None;
        self.commands = 0;
        self.cursor = 0;
    }

    /// One frame: the primary walk, then the secondary, which canon runs through
    /// the identical loop behind a null test on its pointer (:1389-1400).
    pub fn step_frame(&mut self, world: &mut MapWorld<'_>) -> Step {
        let mut step = Step::Stop;
        if self.state.continuous() != 0 {
            self.cursor = self.state.continuous();
            step = self.walk(world);
        }
        let secondary = self.state.secondary();
        if step != Step::Trapped && secondary != 0 {
            self.cursor = secondary;
            step = self.walk(world);
        }
        step
    }

    /// The loop body: fetch, index the table, call, repeat while the handler
    /// returns nonzero (`mov r6,#0xc; ldr r6,[r6]; ldrb r0,[r7]; lsl r0,r0,#2;
    /// ldr r0,[r6,r0]; bx r0; bne`, map_script_cutscene.s:1374-1382).
    fn walk(&mut self, world: &mut MapWorld<'_>) -> Step {
        loop {
            let opcode = match self.code.byte(self.cursor) {
                Some(o) => o,
                None => return self.trap(Trap::PointerOutsideImage(self.cursor)),
            };
            let cmd = match MapCmd::at(opcode) {
                Some(c) => c,
                None => {
                    return self.trap(Trap::Unimplemented("MapScriptCommandJumptable", opcode));
                }
            };
            let step = self.dispatch(cmd, opcode, world);
            self.commands = self.commands.wrapping_add(1);
            if step != Step::Again {
                return step;
            }
        }
    }

    /// One handler. Each arm cites the operand offsets it reads and the cursor
    /// advance it makes, both from the handler's own arithmetic.
    fn dispatch(&mut self, cmd: MapCmd, opcode: u8, world: &mut MapWorld<'_>) -> Step {
        match cmd {
            // 0x00 `mov r0, #0` (:81) -- the loop's stop condition, cursor
            // untouched, which is why the state still holds the same pointer next
            // frame.
            MapCmd::End => Step::Stop,
            // 0x01 `ReadMapScriptWord(r6 = 1)` -> r7 (:90-93). Five-byte command.
            MapCmd::Jump => match self.code.word(self.cursor + 1) {
                Some(dest) => self.jump_to(dest),
                None => self.trap(Trap::PointerOutsideImage(self.cursor + 1)),
            },
            // 0x02 byte1@1, byte2@2, destination3@3; taken -> dest, not taken
            // `add r7, #7` (:109-125).
            MapCmd::JumpIfProgressInRange => {
                let lo = match self.operand(1) {
                    Some(v) => v as u8,
                    None => return self.cursor_trap(1),
                };
                let hi = match self.operand(2) {
                    Some(v) => v as u8,
                    None => return self.cursor_trap(2),
                };
                let in_range = lo <= world.game_progress && world.game_progress <= hi;
                self.jump_or_skip(in_range, 3, 7)
            }
            // 0x03 / 0x05: flag from a memory param, or from the halfword at +2
            // when the param byte is 0xff; destination at +4; not taken
            // `add r7, #8` (:134-160, :195-221).
            MapCmd::JumpIfFlagSet | MapCmd::JumpIfFlagClear => {
                let flag = match self.flag_operand() {
                    Ok(f) => f,
                    Err(step) => return step,
                };
                let take = matches!(cmd, MapCmd::JumpIfFlagSet) == world.test_event_flag(flag);
                self.jump_or_skip(take, 4, 8)
            }
            // 0x04 / 0x06: count@1, first flag@2, destination@4, not taken
            // `add r7, #8` (:167-191, :227-251).
            MapCmd::JumpIfFlagRangeSet | MapCmd::JumpIfFlagRangeClear => {
                let count = match self.operand(1) {
                    Some(v) => v as u8,
                    None => return self.cursor_trap(1),
                };
                let first = match self.code.halfword(self.cursor + 2) {
                    Some(v) => v,
                    None => return self.cursor_trap(2),
                };
                let all = world.test_event_flag_range(first, count);
                let take = matches!(cmd, MapCmd::JumpIfFlagRangeSet) == all;
                self.jump_or_skip(take, 4, 8)
            }
            // 0x07 sub-command@1, pointer@2, destination@6, value@10; equal ->
            // dest, else `add r7, r7, #11/#12/#14` (:267-313).
            MapCmd::JumpIfMemEquals => {
                let kind = match self.operand(1) {
                    Some(v) => v as u8,
                    None => return self.cursor_trap(1),
                };
                let ptr = match self.code.word(self.cursor + 2) {
                    Some(v) => v,
                    None => return self.cursor_trap(2),
                };
                let width = match kind {
                    MEM_EQUALS_BYTE => 0,
                    MEM_EQUALS_HALFWORD => 1,
                    MEM_EQUALS_WORD => 2,
                    _ => {
                        return self.trap(Trap::Unimplemented(
                            "MapScriptCmd_jump_if_mem_equals sub-command",
                            kind,
                        ))
                    }
                };
                let dest = match self.code.word(self.cursor + 6) {
                    Some(v) => v,
                    None => return self.cursor_trap(6),
                };
                let want = match width {
                    0 => self.operand(10),
                    1 => self.code.halfword(self.cursor + 10).map(|v| v as u32),
                    _ => self.code.word(self.cursor + 10),
                };
                let got = match width {
                    0 => world.ram.byte(ptr).map(|v| v as u32),
                    1 => world.ram.halfword(ptr).map(|v| v as u32),
                    _ => world.ram.word(ptr),
                };
                match (got, want) {
                    (Some(got), Some(want)) if got == want => self.jump_to(dest),
                    (Some(_), Some(_)) => {
                        self.cursor += MEM_EQUALS_SIZES[width];
                        Step::Again
                    }
                    (_, None) => self.cursor_trap(10),
                    (None, _) => self.trap(Trap::PointerOutsideImage(ptr)),
                }
            }
            // 0x0a / 0x0b: value@1, destination@2, not taken `add r7, #6`
            // (:4191-4212, :4214-4235).
            MapCmd::JumpIfBattleResultEquals | MapCmd::JumpIfBattleResultNotEqual => {
                let want = match self.operand(1) {
                    Some(v) => v as u8,
                    None => return self.cursor_trap(1),
                };
                let take = matches!(cmd, MapCmd::JumpIfBattleResultEquals)
                    == (world.battle_result == want);
                self.jump_or_skip(take, 2, 6)
            }
            // 0x1f / 0x20: the same memory-or-immediate flag selector as 0x03,
            // then Set/ClearEventFlag and `add r7, #4` (:881-904, :906-929).
            MapCmd::SetEventFlag | MapCmd::ClearEventFlag => {
                let flag = match self.flag_operand() {
                    Ok(f) => f,
                    Err(step) => return step,
                };
                world.write_event_flag(flag, matches!(cmd, MapCmd::SetEventFlag));
                self.cursor += 4;
                Step::Again
            }
            // 0x21 / 0x22: count@1, first flag@2, then Set/ClearEventFlagRange
            // and `add r7, #4` (:931-950, :952-966).
            MapCmd::SetEventFlagRange | MapCmd::ClearEventFlagRange => {
                let count = match self.operand(1) {
                    Some(v) => v as u8,
                    None => return self.cursor_trap(1),
                };
                let first = match self.code.halfword(self.cursor + 2) {
                    Some(v) => v,
                    None => return self.cursor_trap(2),
                };
                for i in 0..count {
                    world.write_event_flag(
                        first + i as u16,
                        matches!(cmd, MapCmd::SetEventFlagRange),
                    );
                }
                self.cursor += 4;
                Step::Again
            }
            // 0x23 / 0x24: a -1-terminated halfword list at word@1, walked with
            // `ldrsh` + `add #2` until negative, then `add r7, #5` (:971-992,
            // :994-1016).
            MapCmd::SetEventFlagList | MapCmd::ClearEventFlagList => {
                let set = matches!(cmd, MapCmd::SetEventFlagList);
                let mut at = match self.code.word(self.cursor + 1) {
                    Some(v) => v,
                    None => return self.cursor_trap(1),
                };
                loop {
                    let flag = match world.ram.halfword(at).or_else(|| self.code.halfword(at)) {
                        Some(v) => v as i16,
                        None => return self.trap(Trap::PointerOutsideImage(at)),
                    };
                    if flag < EVENT_FLAG_LIST_END {
                        break;
                    }
                    world.write_event_flag(flag as u16, set);
                    at += MAP_SCRIPT_PARAM_STRIDE;
                }
                self.cursor += 5;
                Step::Again
            }
            // 0x25: `r0 = word@5`, `bx word@1`, then `add r7, #9` (:1018-1031).
            // No native table exists in this build to call.
            MapCmd::CallNativeFunction => match self.code.word(self.cursor + 1) {
                Some(f) => self.trap(Trap::NativeFunction(f)),
                None => self.cursor_trap(1),
            },
            // 0x3a: argument 1 -> secondary pointer = NULL, `add r7, #2`;
            // otherwise secondary = word@2, `add r7, #6` (:1266-1287).
            MapCmd::RunOrEndSecondaryScript => {
                let mode = match self.operand(1) {
                    Some(v) => v as u8,
                    None => return self.cursor_trap(1),
                };
                if mode == SECONDARY_SCRIPT_END {
                    self.state.set_ptr(ST_SECONDARY, 0);
                    self.cursor += 2;
                } else {
                    let ptr = match self.code.word(self.cursor + 2) {
                        Some(v) => v,
                        None => return self.cursor_trap(2),
                    };
                    self.state.set_ptr(ST_SECONDARY, ptr);
                    self.cursor += 6;
                }
                Step::Again
            }
            // Every other slot: named, never guessed.
            other => {
                if matches!(other, MapCmd::NullTable0x37 | MapCmd::NullTable0x3f) {
                    self.trap(Trap::NullTableEntry(other.symbol(), opcode))
                } else {
                    self.trap(Trap::Unimplemented(other.symbol(), opcode))
                }
            }
        }
    }

    /// The 32-bit operand at `cursor + at`, canon's `ReadMapScriptWord` on the
    /// script blob (map_script_cutscene.s:1476).
    fn operand(&self, at: u32) -> Option<u32> {
        self.code.byte(self.cursor + at).map(|v| v as u32)
    }

    /// The flag number opcode 0x03/0x05/0x1f/0x20 work with: the halfword at +2
    /// when the param byte is 0xff, else the state's memory param (:138-149).
    fn flag_operand(&mut self) -> Result<u16, Step> {
        let param = match self.operand(1) {
            Some(v) => v as u8,
            None => return Err(self.cursor_trap(1)),
        };
        if param == EVENT_FLAG_FROM_MEMORY {
            match self.code.halfword(self.cursor + 2) {
                Some(v) => Ok(v),
                None => Err(self.cursor_trap(2)),
            }
        } else {
            Ok(self.state.mem_param_flag(param))
        }
    }

    /// `mov r7, r4` -- the jump arm every conditional handler shares.
    fn jump_to(&mut self, dest: u32) -> Step {
        self.cursor = dest;
        Step::Again
    }

    /// Taken: jump to the word at `cursor + dest_at`. Not taken: `add r7, #size`.
    /// Both return nonzero, so the walk continues (:150-157 and its twins).
    fn jump_or_skip(&mut self, take: bool, dest_at: u32, size: u32) -> Step {
        if take {
            match self.code.word(self.cursor + dest_at) {
                Some(dest) => self.jump_to(dest),
                None => self.cursor_trap(dest_at),
            }
        } else {
            self.cursor += size;
            Step::Again
        }
    }

    fn cursor_trap(&mut self, at: u32) -> Step {
        self.trap(Trap::PointerOutsideImage(self.cursor + at))
    }

    fn trap(&mut self, t: Trap) -> Step {
        self.trap = Some(t);
        Step::Trapped
    }
}

/// The continuous map script `battle_full`'s walk-up actually runs. Canon's live
/// `eMapScriptState.ContinuousMapScriptPtr` reads 0x08072221 from the walk-up's
/// first observed frame to its last --
/// `python3 tools/probe.py watch /tmp/bn6f_real.gba 60 0x02011E60:16
/// --loadstate /tmp/overworld_net.state --start-frame 2040 --ui isolated` (T8)
/// -- and stays there because the loop keeps the cursor in `r7` and never stores
/// it back (map_script_cutscene.s:1365-1385), so every frame re-enters at the
/// saved pointer and stops at `ms_end`.
///
/// The blob below is those bytes, dumped from the ROM at 0x08072218 with the
/// cursor nine bytes in. Decoded with the sizes above: four
/// `ms_jump_if_progress_in_range` gates, then `ms_jump`, more gates,
/// `ms_start_cutscene` (0x26, trapped here) and, past the window, a jump to
/// 0x08072373 -- which is why §3.3 puts the jump-if family first: the walk-up's
/// whole visible behaviour is gates.
pub const MAP_SCRIPT_WALK_UP_BASE: u32 = 0x08072218; // provenance: peeked -- ROM address the walk-up's script stream starts at
/// The cursor inside it: `eMapScriptState+0xc`, watched live (see above).
pub const MAP_SCRIPT_WALK_UP_CURSOR: u32 = 0x08072221; // provenance: peeked -- dword_2011E6C under the walk-up

/// The 42 script bytes at and after 0x08072218, dumped from
/// `/tmp/bn6f_real.gba` for T8.
pub const MAP_SCRIPT_WALK_UP: &[u8] = &[
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0x10, 0x1f, 0x42, 0x22, 0x07, 0x08,
    0x02, 0x20, 0x2f, 0x79, 0x22, 0x07, 0x08, 0x02, 0x50, 0x5f, 0x02, 0x23, 0x07, 0x08, 0x02, 0x60,
    0x8f, 0x24, 0x23, 0x07, 0x08, 0x01, 0x73, 0x23, 0x07, 0x08,
]; // provenance: peeked -- ROM bytes at 0x08072218

/// The walk-up script as an image: its bytes and the address they live at.
pub const fn map_script_walk_up() -> Image<'static> {
    Image {
        base: MAP_SCRIPT_WALK_UP_BASE,
        bytes: MAP_SCRIPT_WALK_UP,
    }
}

// ---------------------------------------------------------------------------
// 3.2 The chatbox text-script VM
// ---------------------------------------------------------------------------

/// The `TextScriptBytecodeJumptable` (chatbox.s:2392-2420, 27 word entries;
/// index = command byte - 0xE5), one variant per slot in table order.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum TextCmd {
    /// 0xE5 `chatbox_E5_nop` (:2425) -- `add r4, #1`, return 2.
    Nop,
    /// 0xE6 `chatbox_E6_end` (:2437) -- pop the nested stack, or close the box.
    End,
    /// 0xE7 `chatbox_E7_buttonhalt` (:2497) -- the arrow, then wait for a press.
    KeyWait,
    /// 0xE8 `chatbox_E8_msgbox` (:2598) -- open/close the box through its own
    /// eight-entry jump table (:2660).
    MsgBox,
    /// 0xE9 `chatbox_E9_newline` (:2836) -- advance the line slot.
    Newline,
    /// 0xEA `chatbox_EA_flag` (:2880).
    Flag,
    /// 0xEB `chatbox_EB_option` (:3028).
    Option,
    /// 0xEC `chatbox_EC_label` (:3074).
    Label,
    /// 0xED `chatbox_ED_select` (:3110).
    Select,
    /// 0xEE `chatbox_EE_pause` (:3347) -- wait N frames, or on a flag.
    Pause,
    /// 0xEF `chatbox_EF_checkflag` (:3448) -- a 52-entry sub-table (:3455).
    CheckFlag,
    /// 0xF0 `chatbox_F0_jump` (:4199) -- the script-selector branch.
    Jump,
    /// 0xF1 `chatbox_F1_textspeed` (:4311).
    TextSpeed,
    /// 0xF2 `chatbox_F2_clearmsgbox` (:4342).
    ClearMsgBox,
    /// 0xF3 `chatbox_F3_control` (:4405).
    Control,
    /// 0xF4 `chatbox_F4_unk` (:4435).
    UnkF4,
    /// 0xF5 `chatbox_F5_mugshot` (:4495).
    Mugshot,
    /// 0xF6 `chatbox_F6_textcolor` (:4608).
    TextColor,
    /// 0xF7 `chatbox_F7_move` (:6057).
    Move,
    /// 0xF8 `chatbox_F8_playeranimation` (:4716).
    PlayerAnimation,
    /// 0xF9 `chatbox_F9_storebyte` (:7129).
    StoreByte,
    /// 0xFA `chatbox_FA_print` (:4847).
    Print,
    /// 0xFB `chatbox_FB_special` (:5398).
    Special,
    /// 0xFC `chatbox_FC_interface` (:5757).
    Interface,
    /// 0xFD `chatbox_FD_sound` (:5252).
    Sound,
    /// 0xFE `chatbox_FE_numberinput` (:6726).
    NumberInput,
    /// 0xFF `chatbox_FF_copytext` (:7176).
    CopyText,
}

/// `TextScriptBytecodeJumptable`, entry for entry (chatbox.s:2393-2419).
pub const TEXT_SCRIPT_JUMPTABLE: [TextCmd; 27] = [
    TextCmd::Nop,
    TextCmd::End,
    TextCmd::KeyWait,
    TextCmd::MsgBox,
    TextCmd::Newline,
    TextCmd::Flag,
    TextCmd::Option,
    TextCmd::Label,
    TextCmd::Select,
    TextCmd::Pause,
    TextCmd::CheckFlag,
    TextCmd::Jump,
    TextCmd::TextSpeed,
    TextCmd::ClearMsgBox,
    TextCmd::Control,
    TextCmd::UnkF4,
    TextCmd::Mugshot,
    TextCmd::TextColor,
    TextCmd::Move,
    TextCmd::PlayerAnimation,
    TextCmd::StoreByte,
    TextCmd::Print,
    TextCmd::Special,
    TextCmd::Interface,
    TextCmd::Sound,
    TextCmd::NumberInput,
    TextCmd::CopyText,
];

impl TextCmd {
    /// `TextScriptBytecodeJumptable[byte - 0xE5]` -- `sub r1, #TS_COMMANDS_START;
    /// lsl r1, #2; ldr r1, [r2, r1]` (chatbox.s:400-403).
    pub const fn at(command: u8) -> Option<TextCmd> {
        let index = command.wrapping_sub(TS_COMMANDS_START) as usize;
        if index < TEXT_SCRIPT_JUMPTABLE.len() {
            Some(TEXT_SCRIPT_JUMPTABLE[index])
        } else {
            None
        }
    }

    /// Canon's symbol for the slot.
    pub const fn symbol(self) -> &'static str {
        match self {
            TextCmd::Nop => "chatbox_E5_nop",
            TextCmd::End => "chatbox_E6_end",
            TextCmd::KeyWait => "chatbox_E7_buttonhalt",
            TextCmd::MsgBox => "chatbox_E8_msgbox",
            TextCmd::Newline => "chatbox_E9_newline",
            TextCmd::Flag => "chatbox_EA_flag",
            TextCmd::Option => "chatbox_EB_option",
            TextCmd::Label => "chatbox_EC_label",
            TextCmd::Select => "chatbox_ED_select",
            TextCmd::Pause => "chatbox_EE_pause",
            TextCmd::CheckFlag => "chatbox_EF_checkflag",
            TextCmd::Jump => "chatbox_F0_jump",
            TextCmd::TextSpeed => "chatbox_F1_textspeed",
            TextCmd::ClearMsgBox => "chatbox_F2_clearmsgbox",
            TextCmd::Control => "chatbox_F3_control",
            TextCmd::UnkF4 => "chatbox_F4_unk",
            TextCmd::Mugshot => "chatbox_F5_mugshot",
            TextCmd::TextColor => "chatbox_F6_textcolor",
            TextCmd::Move => "chatbox_F7_move",
            TextCmd::PlayerAnimation => "chatbox_F8_playeranimation",
            TextCmd::StoreByte => "chatbox_F9_storebyte",
            TextCmd::Print => "chatbox_FA_print",
            TextCmd::Special => "chatbox_FB_special",
            TextCmd::Interface => "chatbox_FC_interface",
            TextCmd::Sound => "chatbox_FD_sound",
            TextCmd::NumberInput => "chatbox_FE_numberinput",
            TextCmd::CopyText => "chatbox_FF_copytext",
        }
    }
}

/// The `Chatbox` fields the text VM touches (reference/bn6f/include/structs/
/// Chatbox.inc). Held as the blob canon zeroes so the offsets are the ones the
/// disassembly names; the box's tile, mugshot and animation state is the next
/// row's business and stays untouched here.
#[derive(Clone, Copy)]
pub struct ChatboxState {
    /// The `ZeroFillByWord(chatbox, 0x230)` blob (chatbox.s:957-959).
    pub raw: [u8; CHATBOX_STATE_BYTES],
}

/// `oChatbox_*` offsets, from Chatbox.inc at the line each cites.
const CB_VISIBLE: usize = 0x0; // provenance: derived -- oChatbox_Visible, Chatbox.inc:13
const CB_SCRIPT_IDX: usize = 0x1; // provenance: derived -- oChatbox_TextScriptIdx, Chatbox.inc:14
const CB_STATE_04: usize = 0x4; // provenance: derived -- oChatbox_TextScriptState_04, Chatbox.inc:17
const CB_NESTED: usize = 0x5; // provenance: derived -- oChatbox_Unk_05, ts_end's stack depth, Chatbox.inc:18
const CB_PRINT_SPEED: usize = 0x8; // provenance: derived -- oChatbox_TextScriptPrintSpeed, Chatbox.inc:21
const CB_CHAR_IN_PRINT: usize = 0x9; // provenance: derived -- oChatbox_CharInPrint, Chatbox.inc:22
const CB_BOX_YX: usize = 0xc; // provenance: derived -- oChatbox_BoxYX, Chatbox.inc:34
const CB_LINE_STATE_0F: usize = 0xf; // provenance: derived -- oChatbox_BoxGfxLoadState_0F, Chatbox.inc:38
const CB_JT_OFFSET: usize = 0x11; // provenance: derived -- oChatbox_JumpTableOffset_11, Chatbox.inc:39
const CB_CURSOR: usize = 0x2c; // provenance: derived -- oChatbox_TextScriptCursorPtr, Chatbox.inc:63
const CB_ARCHIVE: usize = 0x30; // provenance: derived -- oChatbox_TextScriptPtr, Chatbox.inc:64
const CB_SCRIPT: usize = 0x34; // provenance: derived -- oChatbox_CurrTextScriptPtr, Chatbox.inc:65

impl ChatboxState {
    pub const fn new() -> Self {
        Self {
            raw: [0; CHATBOX_STATE_BYTES],
        }
    }

    fn byte_at(&self, at: usize) -> u8 {
        self.raw[at]
    }

    fn set_byte_at(&mut self, at: usize, value: u8) {
        self.raw[at] = value;
    }

    fn halfword_at(&self, at: usize) -> u16 {
        u16::from_le_bytes([self.raw[at], self.raw[at + 1]])
    }

    fn set_halfword_at(&mut self, at: usize, value: u16) {
        self.raw[at..at + 2].copy_from_slice(&value.to_le_bytes());
    }

    fn word_at(&self, at: usize) -> u32 {
        u32::from_le_bytes([self.raw[at], self.raw[at + 1], self.raw[at + 2], self.raw[at + 3]])
    }

    fn set_word_at(&mut self, at: usize, value: u32) {
        self.raw[at..at + 4].copy_from_slice(&value.to_le_bytes());
    }
}

/// What the text VM should do with one drawn character. Canon writes the glyph
/// straight into the box's tile buffer through the RAM-resident `sub_3006F8C`
/// (chatbox.s:441-446); this build draws its text from the hudtiles/results
/// paths, so the VM hands codes back to its caller instead of writing tiles --
/// and with no caller attached, `step_frame` traps rather than drawing a pixel
/// no row asks for.
pub trait DrawTarget {
    /// One character code: the raw script byte, or `0xE4 + second` for the
    /// two-byte form (chatbox.s:450-459 computes that pair).
    fn glyph(&mut self, code: u16);
}

/// The joypad state the text waits test. Canon keeps two copies in the Chatbox
/// (`oChatbox_JoypadHeld` at 0x22, `oChatbox_JoypadUp` at 0x26,
/// Chatbox.inc:23 and :33), refreshed each frame from the button controller.
#[derive(Clone, Copy, Default, PartialEq, Eq, Debug)]
pub struct ChatboxInput {
    /// `oChatbox_JoypadHeld`: the buttons down this frame.
    pub held: u16,
    /// `oChatbox_JoypadUp`: the buttons that went down last frame and are up now,
    /// which is what `ts_key_wait`'s edge test uses (chatbox.s:2542-2543).
    pub up: u16,
}

/// The ten GBA buttons with the bit each occupies in the controller masks, in
/// `agb::input::Button`'s own discriminant order -- bits 0 (A) and 1 (B) are the
/// two `ts_key_wait`'s `0x3ff` / `#3` / `#2` masks are written against
/// (chatbox.s:2538-2546), so the arms implemented here depend only on those.
const JOYPAD_BITS: [(u16, Button); 10] = [
    (0, Button::A),
    (1, Button::B),
    (2, Button::Select),
    (3, Button::Start),
    (4, Button::Right),
    (5, Button::Left),
    (6, Button::Up),
    (7, Button::Down),
    (8, Button::R),
    (9, Button::L),
]; // provenance: derived -- agb::input::Button discriminants (vendor/agb/agb/src/input.rs:59-80)

impl ChatboxInput {
    /// Both masks for this frame, from the controller the battle runs on.
    pub fn from_controller(input: &ButtonController) -> Self {
        let mut held = 0u16;
        let mut up = 0u16;
        for (bit, button) in JOYPAD_BITS {
            if input.is_pressed(button) {
                held |= 1 << bit;
            }
            if input.is_just_pressed(button) {
                up |= 1 << bit;
            }
        }
        Self { held, up }
    }
}

/// The chatbox text-script VM: `chatbox_runScript`'s install
/// (chatbox.s:942-1043) and the per-frame `chatbox_interpreteAndDrawDialogChar`
/// loop (chatbox.s:373-472).
pub struct TextScriptVm<'a> {
    /// The `TextScriptArchive` the cursor points into: the u16 offset table
    /// followed by the scripts, at their canon address.
    pub archive: Image<'a>,
    pub state: ChatboxState,
    /// The trap that last stopped a walk, if any.
    pub trap: Option<Trap>,
    /// Characters drawn since `start`.
    pub glyphs: u32,
    /// Canon's `r4`, written back to `oChatbox_TextScriptCursorPtr` at the end
    /// of every loop iteration (chatbox.s:469).
    cursor: u32,
}

impl<'a> TextScriptVm<'a> {
    /// A VM with no box up: `chatbox_onUpdate`'s own `if (!Visible) return`
    /// stops it (chatbox.s:280-287).
    pub const fn new() -> Self {
        Self {
            archive: Image::EMPTY,
            state: ChatboxState::new(),
            trap: None,
            glyphs: 0,
            cursor: 0,
        }
    }

    /// `chatbox_runScript(archive, script_idx)`: zero the box, resolve the
    /// script's offset through the archive's u16 table, store the cursor, set
    /// `Visible`, and start the print-speed countdown at 2
    /// (chatbox.s:953-1043; the table lookup is :977-981).
    pub fn start(&mut self, archive: Image<'a>, script_idx: u8) {
        self.archive = archive;
        self.state = ChatboxState::new();
        self.trap = None;
        self.glyphs = 0;
        let offset = archive
            .halfword(archive.base + (script_idx as u32) * 2)
            .unwrap_or(0);
        self.cursor = archive.base + offset as u32;
        self.state.set_word_at(CB_CURSOR, self.cursor);
        self.state.set_word_at(CB_ARCHIVE, archive.base);
        self.state.set_word_at(CB_SCRIPT, self.cursor);
        self.state.set_byte_at(CB_SCRIPT_IDX, script_idx);
        self.state.set_byte_at(CB_VISIBLE, 1);
        self.state.set_byte_at(CB_PRINT_SPEED, TS_DEFAULT_PRINT_SPEED);
        // `oChatbox_JumpTableOffset_11` selects the chatbox's per-frame handler:
        // 1 is `chatbox_interpreteAndDrawDialogChar`, 0 the idle one
        // (jt_803FF30, chatbox.s:411-414; set at the head of the interpreter,
        // :375-377).
        const INTERPRETER_SLOT: u8 = 1; // provenance: derived -- jt_803FF30 entry 1, chatbox.s:413
        self.state.set_byte_at(CB_JT_OFFSET, INTERPRETER_SLOT);
    }

    /// Is there a box up? The gate `chatbox_onUpdate` tests first (chatbox.s:280).
    pub fn running(&self) -> bool {
        self.state.byte_at(CB_VISIBLE) != 0
    }

    /// One frame of the interpreter loop.
    pub fn step_frame(&mut self, draw: Option<&mut dyn DrawTarget>) -> Step {
        if !self.running() {
            return Step::Stop;
        }
        self.step_frame_with(draw, ChatboxInput::default())
    }

    /// The loop itself, with the joypad state the waits read. Head: select the
    /// interpreter through `oChatbox_JumpTableOffset_11` (chatbox.s:375-377),
    /// then fetch-test-dispatch while a handler returns nonzero (:390-472).
    pub fn step_frame_with(
        &mut self,
        mut draw: Option<&mut dyn DrawTarget>,
        input: ChatboxInput,
    ) -> Step {
        loop {
            let byte = match self.archive.byte(self.cursor) {
                Some(b) => b,
                None => return self.trap(Trap::PointerOutsideImage(self.cursor)),
            };
            let step = if byte >= TS_COMMANDS_START {
                // The same countdown gates commands: `cmp r2, #0; bgt` on
                // CharInPrint (chatbox.s:396-399).
                let left = self.state.byte_at(CB_CHAR_IN_PRINT);
                if left > 0 {
                    self.state.set_byte_at(CB_CHAR_IN_PRINT, left - 1);
                    self.write_back_cursor();
                    return Step::Stop;
                }
                match TextCmd::at(byte) {
                    Some(cmd) => self.text_dispatch(cmd, byte, &mut draw, input),
                    None => {
                        return self.trap(Trap::Unimplemented("TextScriptBytecodeJumptable", byte))
                    }
                }
            } else {
                self.draw_char(byte, &mut draw)
            };
            self.write_back_cursor();
            if step != Step::Again {
                return step;
            }
        }
    }

    /// `str r4, [r5, #oChatbox_TextScriptCursorPtr]` (chatbox.s:469).
    fn write_back_cursor(&mut self) {
        self.state.set_word_at(CB_CURSOR, self.cursor);
    }

    /// The character arms: the one-byte path (`add r4, #1`, chatbox.s:441-448)
    /// and the 0xE4 two-byte path (`add r4, #2`, :450-459), behind the
    /// `CharInPrint` countdown that refills from `TextScriptPrintSpeed`
    /// (:425-431).
    fn draw_char(&mut self, byte: u8, draw: &mut Option<&mut dyn DrawTarget>) -> Step {
        let left = self.state.byte_at(CB_CHAR_IN_PRINT);
        if left > 0 {
            self.state.set_byte_at(CB_CHAR_IN_PRINT, left - 1);
            return Step::Stop;
        }
        self.state
            .set_byte_at(CB_CHAR_IN_PRINT, self.state.byte_at(CB_PRINT_SPEED));
        let code = if byte == TS_TWO_BYTE_CHAR {
            match self.archive.byte(self.cursor + 1) {
                Some(second) => {
                    self.cursor += 2;
                    TS_TWO_BYTE_CHAR as u16 + second as u16
                }
                None => return self.trap(Trap::PointerOutsideImage(self.cursor + 1)),
            }
        } else {
            self.cursor += 1;
            byte as u16
        };
        self.glyphs = self.glyphs.wrapping_add(1);
        match draw {
            Some(target) => {
                target.glyph(code);
                Step::Again
            }
            None => self.trap(Trap::NoDrawTarget),
        }
    }

    /// One text command. Implemented: `ts_nop`, `ts_end`, `ts_key_wait`,
    /// `ts_newline`, `ts_textspeed` and the two deterministic arms of `ts_jump`;
    /// everything else is a named trap.
    fn text_dispatch(
        &mut self,
        cmd: TextCmd,
        command: u8,
        draw: &mut Option<&mut dyn DrawTarget>,
        input: ChatboxInput,
    ) -> Step {
        match cmd {
            // 0xE5: `add r4, #1; mov r0, #2` (chatbox.s:2425-2430). The 2 tells
            // the loop to skip the per-command bookkeeping call (:405-408).
            TextCmd::Nop => {
                self.cursor += 1;
                Step::Again
            }
            // 0xE6: with a nested script on the stack, restore its cursor and
            // keep going (`ldr r4, [r5, #0x140 + 4*(n-1)]`, :2439-2453);
            // otherwise close the box and return 0 (:2455-2483).
            TextCmd::End => {
                let depth = self.state.byte_at(CB_NESTED);
                if depth != 0 {
                    let slot =
                        TEXT_NESTED_STACK_BASE + (depth as usize - 1) * TEXT_NESTED_STACK_STRIDE;
                    self.cursor = self.state.word_at(slot);
                    self.state.set_byte_at(CB_NESTED, depth - 1);
                    Step::Again
                } else {
                    self.state.set_byte_at(CB_VISIBLE, 0);
                    self.state.set_byte_at(CB_STATE_04, 0);
                    Step::Stop
                }
            }
            // 0xE7: run while the page-out state is set, then wait for the press
            // its operand selects the mask for, and `add r4, #2` past the
            // operand; the handler's own return is 0, which ends the frame
            // either way (:2506-2560).
            TextCmd::KeyWait => {
                let any = self.archive.byte(self.cursor + 1).unwrap_or(0);
                let (edge, held) = if any != 0 {
                    (KEY_WAIT_ANY_MASK, KEY_WAIT_ANY_MASK)
                } else {
                    (KEY_WAIT_AB_MASK, KEY_WAIT_B_BIT)
                };
                let pressed = (input.up & edge) != 0 || (input.held & held) != 0;
                let paging = self.state.byte_at(CB_STATE_04);
                if paging != 0 || !pressed {
                    if paging == 1 {
                        let n = self.state.halfword_at(CB_BOX_YX);
                        self.state.set_halfword_at(CB_BOX_YX, n.wrapping_sub(1));
                    }
                    return Step::Stop;
                }
                self.state.set_byte_at(CB_STATE_04, 0);
                self.state.set_halfword_at(CB_BOX_YX, 0);
                self.cursor += 2;
                Step::Stop
            }
            // 0xE9: `BoxGfxLoadState_0F + 1` and `add r4, #1`, returning 0, so
            // the frame's walk ends here and the line slots advance one per
            // frame (:2836-2874).
            TextCmd::Newline => {
                let line = self.state.byte_at(CB_LINE_STATE_0F) + 1;
                self.state.set_byte_at(CB_LINE_STATE_0F, line);
                self.cursor += 1;
                Step::Stop
            }
            // 0xF1: `TextScriptPrintSpeed = byte@2` (and the +1 copy in the
            // 0x1f3 counter), `add r4, #3`, return 1 -- so printing continues in
            // the same frame (:4311-4338).
            TextCmd::TextSpeed => {
                let speed = self.archive.byte(self.cursor + 2).unwrap_or(0);
                self.state.set_byte_at(CB_PRINT_SPEED, speed);
                self.cursor += 3;
                Step::Again
            }
            // 0xF0 arms 1 and 2: "run the stored script id and stop" and "store
            // byte@2 as the script id", the two arms that need no RNG
            // (:4202-4209, :4276-4292). Arm 0's weighted-random pick and the
            // 0xff terminator stay trapped with the handler's name.
            TextCmd::Jump => {
                let mode = self.archive.byte(self.cursor + 1).unwrap_or(0);
                match mode {
                    TS_JUMP_RUN_STORED => {
                        self.cursor += 2;
                        Step::Stop
                    }
                    TS_JUMP_STORE => {
                        self.cursor += 3;
                        Step::Again
                    }
                    _ => self.trap(Trap::Unimplemented("chatbox_F0_jump", command)),
                }
            }
            other => self.trap(Trap::Unimplemented(other.symbol(), command)),
        }
    }

    fn trap(&mut self, t: Trap) -> Step {
        self.trap = Some(t);
        Step::Trapped
    }
}

// ---------------------------------------------------------------------------
// The pair battle.rs steps
// ---------------------------------------------------------------------------

/// Both interpreters, as the battle frame path sees them. Canon runs the map
/// script from the map main loop (asm03_1_0.s:1920) and the chatbox from its own
/// update (chatbox.s:331); with no map installed and no box up, both stop at
/// their own gates and neither fetches a byte.
pub struct Scripts<'a> {
    pub map: MapScriptVm<'a>,
    pub text: TextScriptVm<'a>,
    /// `Toolkit->EventFlagsPtr`'s bitfield, 0x100 flags (asm03_0.s:18731).
    pub event_flags: [u8; (EVENT_FLAG_BITS as usize) / 8],
}

impl<'a> Scripts<'a> {
    pub const fn new() -> Self {
        Self {
            map: MapScriptVm::new(),
            text: TextScriptVm::new(),
            event_flags: [0; (EVENT_FLAG_BITS as usize) / 8],
        }
    }

    /// One frame of both interpreters. Returns the last step either took, so a
    /// caller that starts a script can see it stop.
    pub fn step_frame(&mut self, input: &ButtonController) -> Step {
        let mut world = MapWorld {
            event_flags: &mut self.event_flags,
            game_progress: 0,
            battle_result: 0,
            ram: Image::EMPTY,
        };
        let map = self.map.step_frame(&mut world);
        if map == Step::Trapped {
            return map;
        }
        let text = self
            .text
            .step_frame_with(None, ChatboxInput::from_controller(input));
        if map != Step::Stop {
            map
        } else {
            text
        }
    }

    /// The first trap either VM hit -- canon's symbol and the opcode or address
    /// behind it, which is what a report line says when a walk stopped early.
    pub fn trap(&self) -> Option<(&'static str, Trap)> {
        if let Some(trap) = self.map.trap {
            Some((trap.subject().0, trap))
        } else {
            self.text.trap.map(|trap| (trap.subject().0, trap))
        }
    }
}

impl<'a> Default for Scripts<'a> {
    fn default() -> Self {
        Self::new()
    }
}
