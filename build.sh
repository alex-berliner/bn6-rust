#!/usr/bin/env bash
# Build the ROM: cargo produces an ELF, gbafix.py writes the GBA header and pads it to a cartridge image.
set -eu
cd "$(dirname "$0")"
cargo build --release
python3 tools/gbafix.py "${CARGO_TARGET_DIR:-target}/thumbv4t-none-eabi/release/bn" bn.gba
echo "bn.gba: $(stat -c %s bn.gba) bytes, sha1 $(sha1sum bn.gba | cut -c1-12)"
