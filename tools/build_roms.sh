#!/bin/bash
# Build the one ROM the site lists in its dropdown besides the canon
# reference and the dev-profile build tools/web_rom.sh already publishes:
# the default release build, the full battle (white intro, BATTLE START!,
# chip select, the fight, ENEMY DELETED, results). Writes
# web/roms/manifest.json for the page's dropdown.
#
# Every demo-* cargo feature this used to build one bespoke ROM per (AUDIT
# pair 17 prune ticket) is gone: nothing left on the website but ROMs that
# still get maintained. The manifest format is unchanged -- an array of
# {"file", "label"} objects, each label starting with the pack timestamp
# ("YYYY-MM-DD HH:MM — ...") web/index.html sorts and displays by -- so the
# page needs no change.
set -eu
cd "$(dirname "$0")/.."

mkdir -p web/roms
TARGET_DIR="${CARGO_TARGET_DIR:-target}"
cargo build --release
python3 tools/gbafix.py "$TARGET_DIR/thumbv4t-none-eabi/release/bn" web/roms/rollup.gba

STAMP="$(date '+%Y-%m-%d %H:%M')"
LABEL="$STAMP — Full battle vs one Mettaur: white intro, BATTLE START!, chip select, the fight, ENEMY DELETED, results"
python3 - "$LABEL" <<'EOF'
import json, sys
label = sys.argv[1]
with open("web/roms/manifest.json", "w") as f:
    json.dump([{"file": "roms/rollup.gba", "label": label}], f, indent=2, ensure_ascii=False)
    f.write("\n")
EOF
echo "wrote web/roms/manifest.json"
