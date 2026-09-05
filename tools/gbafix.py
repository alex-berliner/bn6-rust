#!/usr/bin/env python3
"""Turn the linked ELF into a bootable .gba: raw binary plus a valid header.

usage: python3 gbafix.py <elf> <out.gba> [title]

The cartridge header needs the Nintendo logo at 0x04 and a complement
checksum at 0xbd (the BIOS refuses the ROM otherwise; emulators are lax).
agb ships agb-gbafix for this, but as a host tool it does not build under
this project's cargo config (build-std for the GBA target), so the logo is
read out of its source and the header written here.
"""

import os
import re
import subprocess
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
GBAFIX_SRC = os.path.join(ROOT, "vendor", "agb", "agb-gbafix", "src", "lib.rs")


def nintendo_logo():
    src = open(GBAFIX_SRC).read()
    m = re.search(r"NINTENDO_LOGO: &\[u8\] = &\[(.*?)\];", src, re.S)
    logo = bytes(int(x, 0) for x in re.findall(r"0x[0-9a-fA-F]+", m.group(1)))
    assert len(logo) == 156
    return logo


def main():
    elf, out = sys.argv[1], sys.argv[2]
    title = (sys.argv[3] if len(sys.argv) > 3 else "BN6 RUST").encode()[:12].ljust(12)
    subprocess.check_call(["arm-none-eabi-objcopy", "-O", "binary", elf, out])
    d = bytearray(open(out, "rb").read())
    d[0x04:0xA0] = nintendo_logo()
    d[0xA0:0xAC] = title
    d[0xAC:0xB0] = b"ABNE"  # game code
    d[0xB0:0xB2] = b"00"  # maker
    d[0xB2] = 0x96  # fixed
    d[0xB3:0xBD] = bytes(10)
    c = 0
    for i in range(0xA0, 0xBD):
        c = (c - d[i]) & 0xFF
    d[0xBD] = (c - 0x19) & 0xFF
    open(out, "wb").write(d)
    print(f"{out}: {len(d)} bytes")


if __name__ == "__main__":
    main()
