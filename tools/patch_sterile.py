#!/usr/bin/env python3
"""Patch the canon bn6f ROM for the capture harness.

Four patches: battle_isBattleOver always returns "not over", the ENEMY
DELETED banner is never uploaded, (AUDIT wave 3c "zero-enemy" ticket) the
encounter's enemy is never spawned at all, and (AUDIT wave 3c "inert-enemy"
ticket, --inert-enemy, opt-in) an ALREADY-spawned enemy's own per-frame
handler is stubbed so it never acts, updates its state machine, or (as far
as this session could measure) draws -- see --inert-enemy's own comment
below for why this is a separate opt-in flag rather than always on.

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

usage: patch_sterile.py <in.gba> <out.gba> [--keep-banner]

--keep-banner leaves the ENEMY DELETED banner in, for the one fixture that
wants to compare the banner itself rather than get it out of the way.

CAVEAT, measured (AUDIT wave 3c "zero-enemy" ticket): this patch only stops
FUTURE spawns -- it cannot retroactively remove an enemy already baked into
an existing save state's RAM. Every save state this project has (PAUSED,
CHIPSELECT, BATTLESTART, and everything built from them) was captured AFTER
a real battle's own spawn already ran, so loading any of them on a
third-patched ROM is byte-identical to loading them on the unpatched sterile
ROM (verified: 0 diff pixels over 20 frames from battlestart.state, patched
vs unpatched). A "field starts empty" state needs a save captured from a
real battle-start reached AFTER this patch is applied -- see the ticket
report for how far that got.
"""
import sys

def main():
    if len(sys.argv) < 3:
        print("usage: patch_sterile.py <in.gba> <out.gba> [--keep-banner] [--inert-enemy]")
        return 2
    keep_banner = "--keep-banner" in sys.argv[3:]
    inert_enemy = "--inert-enemy" in sys.argv[3:]
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

    # Third patch (AUDIT wave 3c "zero-enemy" ticket): never spawn the
    # encounter's enemy at all. SpawnBattleObjectUsingBattleEntityConfig_8007368
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
    # CAVEAT, measured (see this file's own docstring and the ticket
    # report): this only stops FUTURE spawns. Every save state this project
    # has was captured from a battle whose spawn already ran on the
    # unpatched ROM, so loading any of them here is byte-identical to
    # loading them on the sterile ROM without this patch -- verified, 0 diff
    # pixels over 20 frames from battlestart.state. A state that actually
    # shows an empty field needs a save captured from a real battle-start
    # reached AFTER this patch, which needs real input from a cold boot
    # (title/intro/overworld -- see the ticket report for how far that got).
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

    with open(sys.argv[2], 'wb') as f:
        f.write(d)
    print("patched battle_isBattleOver%s, enemy spawn%s: %s"
          % ("" if keep_banner else " and the ENEMY DELETED banner",
             " and enemy inertness" if inert_enemy else "", sys.argv[2]))

if __name__ == '__main__':
    main()
