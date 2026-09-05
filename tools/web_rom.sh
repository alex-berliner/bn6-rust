#!/bin/bash
# Build the release ROM into web/ for tools/serve.py, with the commit it
# came from noted for the page.
set -eu
cd "$(dirname "$0")/.."
cargo build --release
python3 tools/gbafix.py target/thumbv4t-none-eabi/release/bn web/bn6-rust.gba
{ git rev-parse --short HEAD; git diff --quiet || echo "(with uncommitted changes)"; } | tr '\n' ' ' > web/build.txt
echo "web/build.txt: $(cat web/build.txt)"
