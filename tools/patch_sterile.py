#!/usr/bin/env python3
"""Patch the canon bn6f ROM for the capture harness.

Two patches: battle_isBattleOver always returns "not over", and the ENEMY
DELETED banner is never uploaded.

This is the first half of a sterile real-battle arena: it stops the win/lose
check from concluding the fight, so a battle with the enemy deleted stays live.
The results window is still reached through a separate flow (the enemy-death
-> result animation), so a full arena also needs that path handled.

usage: patch_sterile.py <in.gba> <out.gba> [--keep-banner]

--keep-banner leaves the ENEMY DELETED banner in, for the one fixture that
wants to compare the banner itself rather than get it out of the way.
"""
import sys

def main():
    if len(sys.argv) < 3:
        print("usage: patch_sterile.py <in.gba> <out.gba> [--keep-banner]")
        return 2
    keep_banner = "--keep-banner" in sys.argv[3:]
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
    with open(sys.argv[2], 'wb') as f:
        f.write(d)
    print("patched battle_isBattleOver%s: %s"
          % ("" if keep_banner else " and the ENEMY DELETED banner", sys.argv[2]))

if __name__ == '__main__':
    main()
