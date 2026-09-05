#!/bin/bash
# Build the dev-profile ROM into web/ for tools/serve.py, with the commit it
# came from noted for the page. The debug-profile aids -- the gauge starting
# full, L/R opening the chip window, the Mettaur-only fight -- are gated on
# cfg!(debug_assertions), so the browser build is built the same way the
# debug ROM is rather than with --release.
set -eu
cd "$(dirname "$0")/.."
cargo build
python3 tools/gbafix.py target/thumbv4t-none-eabi/debug/bn web/bn6-rust.gba
{ git rev-parse --short HEAD; git diff --quiet || echo "(with uncommitted changes)"; } | tr '\n' ' ' > web/build.txt
echo "web/build.txt: $(cat web/build.txt)"
