#!/usr/bin/env python3
"""Patch the canon bn6f ROM so battle_isBattleOver always returns "not over".

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
    with open(sys.argv[2], 'wb') as f:
        f.write(d)
    print(f"patched battle_isBattleOver -> always not-over: {sys.argv[2]}")

if __name__ == '__main__':
    main()
