#!/usr/bin/env python3
"""Patch the canon bn6f ROM for the capture harness.

Six patches: battle_isBattleOver always returns "not over", the ENEMY
DELETED banner is never uploaded, (TODO F5, --hold-banner, opt-in) the
banner sequencer's ENEMY-DELETED completion advance is stubbed so the
battle never leaves the phase in which chips can be fired, (AUDIT wave 3c
"zero-enemy" ticket, --never-spawn, OPT-IN as of the "fresh-state" ticket
-- see its own comment for why) the encounter's enemy is never spawned at
all, (AUDIT wave 3c "inert-enemy" ticket, --inert-enemy, opt-in) an
ALREADY-spawned enemy's own per-frame handler is stubbed so it never acts,
updates its state machine, or (as far as this session could measure)
draws, and (AUDIT wave 3c "fresh-state" ticket, --empty-net-encounter,
opt-in) one specific ROM encounter-table entry's EnemySetup list is
data-patched to terminate right after MegaMan, so THAT ONE encounter
natively spawns no enemies at all -- see its own comment below for why
this succeeds where --never-spawn's code patch crashes.

The first two are the sterile real-battle arena: they stop the win/lose check
from concluding the fight, so a battle with the enemy deleted stays live. The
results window is still reached through a separate flow (the enemy-death ->
result animation), so a full arena also needs that path handled.

The third removes the root cause AUDIT.md pair 3 names directly ("make a game
patch that allows 0 enemies to be on the field, then you don't get any side
effects") instead of deleting a spawned enemy and living with what its death
leaves behind (a dissolving OAM corpse, a portrait-box artifact that only
clears as a side effect of that same death processing -- see
tools/harness.py's ALIGN_CHIP comment and tools/states.py's "chip_ready"
entry for the two rejected workarounds this replaces).

usage: patch_sterile.py <in.gba> <out.gba> [--keep-banner] [--hold-banner]
                                            [--never-spawn]
                                            [--inert-enemy] [--empty-net-encounter]

--keep-banner leaves the ENEMY DELETED banner in, for the one fixture that
wants to compare the banner itself rather than get it out of the way.

--hold-banner (TODO F5, 2026-09-12) is the chip-firing gate fix. MEASURED
(mgba_capture --watch/--watch-write, this ticket): in a battle whose last
enemy is deleted, chips fire ONLY while the generic banner sequencer
(dword_203CA70) sits in its ENEMY DELETED state 0x08 -- the firing A press
reaches MegaMan through sub_800FB54 (asm00_2.s:1994, AIData joypad-flag
gated, asm00_2.s:2006) and works at any frame of that phase -- because it
is 0x08 (sub_80080D2) that refreshes the TWO alliance players' AIData
from the joypad mirror every frame, via sub_8012DFC called twice (once
per alliance player, asm00_1.s:10519-10522), and NOT every object. The
moment the sequencer advances to state 0x0c (the victory countdown,
sub_80081A4, asm00_1.s:10617), input dies -- 0x0c never refreshes
AIData: a press that fires at phase-0x08 frame 40
does NOT fire at frame 120 of the same continuous run, with the FSM
(eBattleState.Index_01, 0x02034881) still in 0x0c and byte_203CA74 still
0. The countdown's own expiry (byte_203CA74=1 written at asm00_1.s:10704,
which sub_800938A consumes and moves the FSM to 0x10; the `cmp r0,#6`
at 0x080093A2 there, asm00_1.s:13137, is IRRELEVANT to the firing gate
-- patching it changed nothing) is a SECOND, later cutoff -- refilling the countdown halfword
0x0203ca78 with a --poke keeps the FSM in 0x0c and byte_203CA74 at 0 and
still does not restore firing. So the previous session's refused-press
symptom ("a state saved past the dissolve refuses every chip press",
harness.py ALIGN_CHIP comment) is canon's own end-of-battle flow, not a
gate bug: past the dissolve the battle is merely waiting out its 94-frame
countdown to the RESULT window, and no unpatched canon battle fires chips
there. The advance out of state 0x08 is sub_80080D2's own turn-end branch:
sub_80080D2 is the sequencer's PLAYER-TURN handler (it calls UnpauseBattle
in its init, asm00_1.s:10521) and every frame asks sub_800A152() -- the
"which alliance still has actors" probe (asm00_1.s:15080) -- advancing to
the RESULT countdown (state 0x0c, sub_80081A4, asm00_1.s:10617) when the
last opponent is gone (sub_800A152 returns 1 AND oBattleState_Unk_3a is
0): `mov r0,#0xC; str r0,[r5]` at loc_8008116
(asm00_1.s:10547-10548, ROM 0x0800811C..0x0800811F, bytes 0C 20 28 60).
TRACED LIVE (--trace-pc 0x0800811C): the hit comes with r0=1 (sub_800A152
returned 1), r1=eBattleState (0x02034880), r5=dword_203CA70, 36 frames
after the enemy's death -- exactly the frame the press at 120 stops
working. (An earlier cut of this patch NOPed the same byte pattern at
0x080083C4 -- sub_800838A's advance, reachable only from sequencer state
0x18 -- and changed nothing: the state still went 0x08 -> 0x0c at frame
47, which is what pinned the real site.) This patch NOPs those 4 bytes
(00 BF 00 BF), so the turn never ends when the last enemy dies.

MEASURED DEAD END (TODO F5 result, Sol-confirmed correction of an earlier
claim here): holding the sequencer in 0x08 FREEZES the corpse dissolve and
the portrait box forever (they complete only as part of the turn-end flow
the NOP removes) and the held battle's FSM dispatcher (sub_8009158) STOPS
after a save/reload -- a state saved under this hold is NOT a clean firing
state, and refilling the countdown halfword 0x0203ca78 does not restore
firing either. The chip-row fixtures cannot use this patch; the remaining
untested route (TODO F5b) is a one-shot poke to MegaMan's AIData pressed
field while the unpatched sequencer sits in 0x0C.

Side effect,
accepted: sub_80080D2's oBattleState_Unk_18 increment (asm00_1.s:10544-46,
immediately before the NOPed store) now runs every frame instead of
once per turn; it is a single wrapping byte whose only other reader is
sub_800AF50 (asm00_1.s:11814), reachable only through the FSM fire path
that byte_203CA74=0 keeps dead while the turn is held. The result
countdown's init (victory music, the 0xe4c53 dispatch) never runs, which
is the point: the battle never starts ending.

CAVEAT, measured (AUDIT wave 3c "zero-enemy" ticket, and confirmed FATAL by
the "fresh-state" ticket): --never-spawn only stops FUTURE spawns -- it
cannot retroactively remove an enemy already baked into an existing save
state's RAM, so every fixture that loads a pre-existing state (PAUSED,
CHIPSELECT, BATTLESTART, and everything built from them) is byte-identical
with or without it (verified: 0 diff pixels over 20 frames from
battlestart.state). For that reason it defaults OFF now (previously always
on): the "fresh-state" ticket walked a real encounter into an ACTUAL fresh
spawn on a --never-spawn ROM and got a hard crash -- see the flag's own
comment. Since no existing fixture depends on it (proven a no-op for all of
them above), turning it off by default changes nothing anyone was relying
on. A "field starts empty" state now goes through --empty-net-encounter
instead (a data patch, not a code stub) -- see its own comment.
"""
import sys

def main():
    if len(sys.argv) < 3:
        print("usage: patch_sterile.py <in.gba> <out.gba> [--keep-banner] [--hold-banner] "
              "[--never-spawn] [--inert-enemy] [--empty-net-encounter]")
        return 2
    keep_banner = "--keep-banner" in sys.argv[3:]
    hold_banner = "--hold-banner" in sys.argv[3:]
    never_spawn = "--never-spawn" in sys.argv[3:]
    inert_enemy = "--inert-enemy" in sys.argv[3:]
    empty_net_encounter = "--empty-net-encounter" in sys.argv[3:]
    with open(sys.argv[1], 'rb') as f:
        d = bytearray(f.read())
    base = 0x08000000
    off = 0x0800A18E - base  # battle_isBattleOver: mov r0,#1; ... -> mov r0,#0; bx lr
    if d[off:off+2] != b'\x01\x20':
        print(f"warning: expected mov r0,#1 at 0x{off:08x}, got {d[off:off+2].hex()}")
    d[off:off+4] = b'\x00\x20\x70\x47'  # mov r0,#0 ; bx lr  (always not-over)

    # And stop the ENEMY DELETED banner being drawn at all. sub_801E838
    # (asm00_2.s:31106) is the routine that uploads its text to OBJ VRAM
    # 0x6016E00 -- five transfers, one per 32x16 object -- and with it gone
    # those objects draw from whatever is in the tiles, which the harness
    # zeroes, so nothing shows. Without this the banner costs every chip
    # comparison exactly 369 px on one frame and "exact" has to mean "equals a
    # floor" rather than zero. Zeroing the tiles alone cannot work: the harness
    # writes before each frame and the game uploads the banner during the very
    # frame that shows it.
    banner = 0x0801E838 - base
    if d[banner:banner + 2] != b'\xf0\xb5':
        print(f"warning: expected push at 0x{banner:08x}, got {d[banner:banner+2].hex()}")
    if not keep_banner:
        d[banner:banner + 2] = b'\x70\x47'  # bx lr

    # Sixth patch (TODO F5), --hold-banner, OPT-IN: hold the banner
    # sequencer in its ENEMY DELETED state 0x08 forever, so the phase in
    # which chips can be fired never ends. See the docstring above for the
    # full measurement trail and the address/bytes justification.
    if hold_banner:
        advance = 0x0800811C - base
        if d[advance:advance + 4] != b'\x0c\x20\x28\x60':
            print(f"warning: expected mov r0,#0xC; str r0,[r5] at 0x{advance + 0x08000000:08x}, "
                  f"got {d[advance:advance + 4].hex()}")
        d[advance:advance + 4] = b'\x00\xbf\x00\xbf'  # nop; nop

    # The chip-name popup that family-0x15 chips put up (AreaGrab, Invisibl,
    # Barrier, Barr100, Barr200) is NOT patched out any more: this build draws
    # it, so it is something to match rather than something to remove. It is
    # built by sub_801E95C (asm00_2.s:31261) -- getChip8021DA8 for the chip,
    # sub_801EA5A for the local player's buffer and destination (byte_203EDA0
    # -> 0x6016E00), renderTextGfx_8045F8C for the name, sub_801EA34 for the
    # damage digits -- and it writes the SAME tiles the banner does, so a
    # comparison that wants to see it has to stop blanking them, which in turn
    # means keeping the enemy alive so no ENEMY DELETED banner is ever asked
    # for. chip_compare.py's --no-banner-zero with --hide-enemy does that.

    # Third patch (AUDIT wave 3c "zero-enemy" ticket), --never-spawn, OPT-IN
    # (flipped from always-on by the "fresh-state" ticket -- see below and
    # the docstring): never spawn the encounter's enemy at all.
    # SpawnBattleObjectUsingBattleEntityConfig_8007368
    # (asm00_1.s:8552, called once per battle from sub_8007358, itself called
    # from 4 near-identical battle-FSM init states -- asm00_1.s:12807/13421/
    # 13908/14317) walks the battle's EnemySetup array and dispatches each
    # entry's type nibble through a table at 0x80073A0 (asm00_1.s:8592):
    # 0x00 spawns MegaMan (spawnMegaMan_80073CC), 0x04 spawns the enemy
    # (spawnEnemy_80073E2, asm00_1.s:8634) via sub_800768C -- the ONLY caller
    # of spawnEnemy_80073E2 in the whole disassembly (grepped), so patching
    # its own entry point rather than the dispatch table (a data patch) is
    # both simpler and exactly as targeted: no EnemySetup entry of type 0x04,
    # for any encounter, ever creates a BattleObject again. The patch is the
    # same shape as the banner patch above -- turn the function into an
    # immediate return: spawnEnemy_80073E2 opens with `push {r5,lr}` (bytes
    # 20 B5); replaced with `bx lr` (70 47). r0's return value (normally the
    # new * BattleObject) is never read by the dispatch loop after the call,
    # so leaving it unset (whatever the type-nibble index computation left in
    # r0) is safe.
    #
    # CAVEAT, measured (see this file's own docstring): this only stops
    # FUTURE spawns. Every save state this project has was captured from a
    # battle whose spawn already ran on the unpatched ROM, so loading any of
    # them here is byte-identical to loading them on the sterile ROM without
    # this patch -- verified, 0 diff pixels over 20 frames from
    # battlestart.state.
    #
    # FATAL, measured (AUDIT wave 3c "fresh-state" ticket): a save is not
    # the only way to reach a fresh spawn. Walking a real forced encounter
    # (TRANSFER 7aw's step-accumulator cheat) into a battle that actually
    # STARTS on a --never-spawn ROM crashes the console to its own cold-boot
    # logo 9-13 frames in, isolated by A/B test to this patch specifically
    # (a control ROM with only the first two patches runs the identical,
    # same-seed encounter cleanly) and to the one-time init path rather than
    # steady-state per-frame logic (a --trace-pc on RunBattleObjectLogic's
    # per-object dispatch call never fires in the crash window). This
    # function's own comment about r0 being unread is still true of the
    # DISPATCH LOOP right after the call -- but sub_800768C, entirely
    # skipped when this patch fires, is what actually calls
    # object_spawnType1 to allocate the BattleObject and (via loc_80076DA)
    # presumably register it; something downstream that assumes as many
    # live actors as EnemySetup specified, not told any fewer were created,
    # is the live hypothesis, not confirmed further (see tools/states.py's
    # "emptyfield_start" entry and reference/bn6f's own comment on this
    # function, wt/fresh-state branch). NOT DEFAULT ANY MORE because of
    # this: --empty-net-encounter (below) gets the same "empty field, battle
    # stays running" result for its one target encounter by patching DATA
    # instead of code, and does not crash.
    if never_spawn:
        spawn = 0x080073E2 - base
        if d[spawn:spawn + 2] != b'\x20\xb5':
            print(f"warning: expected push at 0x{spawn:08x}, got {d[spawn:spawn+2].hex()}")
        d[spawn:spawn + 2] = b'\x70\x47'  # bx lr (never spawn the enemy)

    # Fourth patch (AUDIT wave 3c "inert-enemy" ticket), --inert-enemy, OPT-IN:
    # make an ALREADY-spawned enemy inert instead of chasing a never-spawned
    # one. Traced live (tools/mgba_capture.c's --trace-pc, this ticket): every
    # T1-category battle object (MegaMan, the Mettaur, and whatever else) is
    # dispatched through the SAME shared entry, t1_0x0_80B81EC (asm31.s:4),
    # which reads oBattleObject_AIDataPtr->ActorType and picks one of THREE
    # generic handlers: "virus" -> battleObject_dispatch_8108F50, "navi" ->
    # sub_80F2330, "player" -> playerObject_main_80EA460 (asm31.s:6-23).
    # Confirmed live: PAUSED's Mettaur (r5 == 0x0203ab60 at the dispatch call)
    # reads the SAME table entry (0x080b81ed, t1_0x0_80B81EC's own address)
    # as MegaMan's own object (r5 == 0x0203a9b0) -- t1_0x0_80B81EC is NOT
    # per-object, so patching IT would break MegaMan too. The "virus" branch,
    # battleObject_dispatch_8108F50 (asm31.s:169253), is: patched instead --
    # ONE caller (grepped), and its own body is itself a second dispatch
    # (by oBattleObject_CurState: init/update/destroy) plus an unconditional
    # `bl sub_8016E64` the disassembly's own comment already flags as "enemy
    # attack animations cease playing" if skipped -- i.e. this single function
    # is confirmed (by a prior reverse-engineering pass, not just this one) to
    # be upstream of the enemy's attacks, and by this ticket's own read to be
    # upstream of its state-machine transitions (including whatever notices
    # HP<=0 and starts the death/dissolve sequence that produces the corpse
    # this whole ticket chain is chasing out). Same patch shape as the other
    # three: `push {lr}` (bytes 00 B5) -> `bx lr` (70 47), an immediate
    # return, so CurState never advances and the attack-animation call never
    # runs, for EVERY object of Params->ActorType "virus" (a data-driven
    # field, not tied to Mettaur specifically -- this affects every virus
    # kind, matching the project's existing single-Mettaur-encounter scope
    # without being hard-coded to it).
    #
    # OPT-IN, not always-on: the existing chip scoreboard's --hide-enemy
    # recipe (chip_compare.py) WANTS a live, reactive enemy for chips that
    # need a target (StepSwrd) -- an inert one cannot be hit, take damage, or
    # trigger Full Synchro, which is a real behavioural difference from
    # "immortal but otherwise normal" that --hide-enemy relies on. This flag
    # is for fixtures that want NO enemy behaviour at all (the field/warp/
    # buster/chip-use family, and anything using DELETE_ENEMY as a way to
    # clear the field rather than to fight something), not a replacement for
    # --hide-enemy.
    if inert_enemy:
        virus_dispatch = 0x08108F50 - base
        if d[virus_dispatch:virus_dispatch + 2] != b'\x00\xb5':
            print(f"warning: expected push at 0x{virus_dispatch:08x}, "
                  f"got {d[virus_dispatch:virus_dispatch+2].hex()}")
        d[virus_dispatch:virus_dispatch + 2] = b'\x70\x47'  # bx lr (never update/act)

    # Fifth patch (AUDIT wave 3c "fresh-state" ticket), --empty-net-encounter,
    # OPT-IN: a DATA patch, not a code patch -- "cheat a value, patch a
    # behaviour" applied to the game's own encounter table instead of to
    # SpawnBattleObjectUsingBattleEntityConfig_8007368's caller loop, so the
    # loop itself does exactly what it always does and nothing downstream is
    # left surprised (unlike --never-spawn above, this does not crash).
    #
    # This targets ONE SPECIFIC encounter: the one tools/states.py's
    # "overworld_net" state's own walk (a forced encounter roll, TRANSFER
    # 7aw, held direction cycled Right/Down/Left/Up one per frame from that
    # state) deterministically reaches at frame 93 of the walk, every time
    # (confirmed with a second, differently-phased direction cycle -- same
    # frame, same result). Found by walking the live pointer chain
    # (tools/mgba_capture.c's --dump, not --trace-pc -- no code trace
    # needed): eToolkit (0x020093b0) -> BattleStatePtr (+0x18) ->
    # oBattleState_BattleSettings (BattleState.inc +0x3c) ->
    # oBattleSettings_EnemySetupArrPtr (rom_structs/BattleSettings.inc
    # +0xc) reads 0x080b5306 for this one encounter (confirmed ROM, not a
    # RAM copy -- verified byte-for-byte identical between a live dump at
    # that address and /tmp/bn6f_real.gba's own file bytes at the matching
    # offset, so a data patch here is legitimate and needs no per-frame
    # cheat). Its own EnemySetup array (SpawnBattleObjectUsingBattleEntity-
    # Config_8007368's own format: 4-byte entries, byte0's upper nibble is
    # the dispatch-table index used elsewhere in this file, terminated by
    # any byte0 in 0xF0..0xFF) is, at that address:
    #   +0x00: 00 22 00 00   -- MegaMan, panel byte 0x22
    #   +0x04: 11 35 01 00   -- enemy (Mettaur, enemy_idx 1), panel byte 0x35
    #   +0x08: 11 16 01 00   -- enemy (Mettaur, enemy_idx 1), panel byte 0x16
    #   +0x0c: f0 00 22 00   -- terminator, then the NEXT table entry begins
    # (cross-checked live: this is the SAME 2-Mettaur composition the
    # unpatched control ROM actually shows in its chip-select header,
    # "Mettaur Mettaur", after the identical walk). Patching the byte at
    # +0x04 (ROM 0x080b530a) from 0x11 to 0xf0 makes the dispatch loop hit
    # its own terminator check immediately after spawning MegaMan -- the
    # SAME code path a genuinely-authored "1 navi vs 0 enemies" encounter
    # would take, not a new one. The entry at +0x08 is simply never reached
    # (the loop already stopped), left as-is.
    #
    # OPT-IN: this ROM byte is specific to one table entry among many
    # (asm01.s's own off_8020180/off_8020190/off_80201E4/pt_802029C nested
    # encounter-group tables suggest a great many more exist) -- scoped to
    # exactly the encounter tools/states.py's route needs, not a general
    # "no wild encounters" patch, so it stays off unless asked for.
    #
    # WHY THE WALK TO THIS ENTRY STOPPED REPRODUCING, root-caused this
    # session (AUDIT wave 3c "encounter-roll" ticket) rather than left as
    # the open question the previous session's note left it as: traced live
    # (--trace-pc on sub_80AA4C0's own `bl GetRNG`, ROM 0x080AA51E, and its
    # masked-value/threshold compare, completing by 0x080AA52A) that with
    # the per-frame forced-roll cheat (0x02001c16:2000, 0x02001c18:0)
    # written EVERY frame from load, nothing on this code path perturbs
    # GetRNG's state between one frame's draw and the next, so the roll's
    # outcome -- and, downstream, WHICH EnemySetup table entry a success
    # reaches -- is fixed at load and does not change with more frames or a
    # different held/cycled direction: TRANSFER 7aw's own held-direction
    # orbit trap again, just walked through the forced accumulator instead
    # of through input. On this session's build the very first evaluated
    # frame draws masked value 6 against threshold 12 (row 16, category 5 --
    # matches the documented threshold), 6 < 12, so it ALWAYS succeeds on
    # frame 0, landing on EnemySetupArrPtr 0x080b5398 (a 3-Mettaur
    # composition), never on 0x080b5306.
    #
    # tools/mgba_capture.c gained `--poke-at frame:addr:value` this ticket
    # (a ONE-SHOT write applied immediately before the named frame instead
    # of every frame) as the fix the previous session's note called for --
    # real per-frame play runs untouched up to the named frame, so a swept N
    # samples GetRNG's actual state at frame N rather than repeating frame
    # 0's fixed draw. VERIFIED this restores real frame-to-frame variation
    # (sweeping N in 1-frame steps from overworld_net's own "cycled
    # Right/Down/Left/Up one per frame" script flips between roll success
    # and failure, e.g. N=80..119 succeeds at 80,86,90,94,100,101,102,104,
    # 106,108,109,110,111,112,113,115,119 and fails at every other N in that
    # range), and the successes land on a whole neighbourhood of DISTINCT
    # nearby table entries -- but NOT reliably back on 0x080b5306 itself: a
    # first attempt at patching a differently-reached neighbour instead
    # (0x080b52f9, also MegaMan + 2 Mettaur, reached at N=100) measurably
    # BACKFIRED -- rebuilding the ROM with that byte also terminated moved
    # what N=100 itself selects (0x080b5398 post-patch, not 0x080b52f9),
    # proof that whatever selects an entry for a given roll is sensitive to
    # an EARLIER entry's own encoded length, not just to table position: a
    # patched (shortened) entry is not safe to select-and-later-patch by
    # this route unless it is provably the LAST entry any candidate N's scan
    # passes through. NOT settled further this session (broader N range,
    # -- or the original 7aw-documented walk's exact undocumented phase --
    # was not tried before time ran out); the ONE patch below (0x080b530a,
    # unchanged from the prior session) is left as the sole encounter-table
    # edit, still correct and still the only verified-safe one -- reaching
    # it again is next session's concrete first step, not guessed at here.
    if empty_net_encounter:
        enemy_entry = 0x080b530a - base
        if d[enemy_entry:enemy_entry + 1] != b'\x11':
            print(f"warning: expected enemy entry byte 0x11 at 0x{enemy_entry:08x}, "
                  f"got {d[enemy_entry:enemy_entry+1].hex()}")
        d[enemy_entry] = 0xf0  # terminate the EnemySetup list right after MegaMan

    with open(sys.argv[2], 'wb') as f:
        f.write(d)
    print("patched battle_isBattleOver%s%s, enemy spawn%s%s: %s"
          % ("" if keep_banner else " and the ENEMY DELETED banner",
             " (banner phase held)" if hold_banner else "",
             " (never-spawn)" if never_spawn else "",
             " and enemy inertness" if inert_enemy else "",
             sys.argv[2]))
    if empty_net_encounter:
        print("  and the overworld_net encounter's EnemySetup list (data patch)")

if __name__ == '__main__':
    main()
