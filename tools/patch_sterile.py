#!/usr/bin/env python3
"""Patch the canon bn6f ROM for the capture harness.

Three patches: battle_isBattleOver always returns "not over", the ENEMY
DELETED banner is never uploaded, and neither is the chip-name popup.

This is the first half of a sterile real-battle arena: it stops the win/lose
check from concluding the fight, so a battle with the enemy deleted stays live.
The results window is still reached through a separate flow (the enemy-death
-> result animation), so a full arena also needs that path handled.

usage: patch_sterile.py <in.gba> <out.gba>
"""
import sys

def main():
    if len(sys.argv) < 3:
        print("usage: patch_sterile.py <in.gba> <out.gba>")
        return 2
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
    d[banner:banner + 2] = b'\x70\x47'  # bx lr

    # The same OBJ VRAM carries the chip-name popup -- the name of the chip
    # you just used, eight 8x16 objects at (28,32) in OBJ palette 11, with the
    # damage number beside it. sub_801E95C (asm00_2.s:31261) builds it: it
    # looks the chip up (getChip8021DA8), picks the buffer and destination for
    # the local player (sub_801EA5A -> byte_203EDA0 / 0x6016E00), renders the
    # name through renderTextGfx_8045F8C and queues the damage digits through
    # sub_801EA34. Uploading it during the frame that shows it defeats the
    # harness's zeroing exactly as the banner did, and it costs one frame of
    # every chip comparison: 127 px for AreaGrab at the attack's frame 18.
    # Its only caller is sub_801E8CC, which discards the return value.
    popup = 0x0801E95C - base
    if d[popup:popup + 2] != b'\xf0\xb5':
        print(f"warning: expected push at 0x{popup:08x}, got {d[popup:popup+2].hex()}")
    d[popup:popup + 2] = b'\x70\x47'  # bx lr
    with open(sys.argv[2], 'wb') as f:
        f.write(d)
    print(f"patched battle_isBattleOver, the ENEMY DELETED banner and the\n"
          f"chip-name popup: {sys.argv[2]}")

if __name__ == '__main__':
    main()
