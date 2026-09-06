#!/bin/bash
# Build one bespoke demo ROM per battle feature into web/roms/, each loaded
# so the chip fires (and hits) on the first A press, or a single enemy is
# fielded so its AI can be seen alone. Writes web/roms/manifest.json for the
# page's dropdown.
#
# Each entry is "<feature> <filename> <label>". The feature is the cargo
# feature name; the filename is what lands in web/roms/; the label is the
# friendly name shown in the dropdown.
set -eu
cd "$(dirname "$0")/.."

ENTRIES=(
  "demo-buster buster Buster / charge shot"
  "demo-sword sword Sword / WideSwrd / LongSwrd"
  "demo-minibomb minibomb MiniBomb"
  "demo-cannon cannon Cannon / HiCannon"
  "demo-cannon,demo-sterile,demo-auto cannon-real Cannon on black, auto-fire: matched frame-for-frame to the real ROM"
  "demo-sword,demo-sterile,demo-auto sword-real Sword on black, auto-fire: matched frame-for-frame to the real ROM"
  "demo-wideswrd,demo-sterile,demo-auto wideswrd-real WideSwrd on black, auto-fire: matched frame-for-frame to the real ROM"
  "demo-recovery,demo-sterile,demo-auto recov-real Recov10 on black, auto-fire: matched frame-for-frame to the real ROM"
  "demo-vulcan vulcan Vulcan1 volley"
  "demo-airshot airshot AirShot"
  "demo-recovery recovery Recov / Invisibl / Barrier"
  "demo-mettaur mettaur Mettaur AI"
  "demo-gunner gunner Gunner AI"
  "demo-protoman protoman ProtoMan AI"
  "demo-colonel colonel Colonel AI"
  "demo-results results Results screen"
)

mkdir -p web/roms
: > web/roms/manifest.json
printf '[' >> web/roms/manifest.json

first=1
for entry in "${ENTRIES[@]}"; do
  read -r feature file label <<< "$entry"
  echo "building $feature -> web/roms/$file.gba"
  cargo build --release --features "$feature"
  python3 tools/gbafix.py "target/thumbv4t-none-eabi/release/bn" "web/roms/$file.gba"
  if [ "$first" -eq 0 ]; then printf ',' >> web/roms/manifest.json; fi
  printf '\n  {"feature": "%s", "file": "roms/%s.gba", "label": "%s"}' \
    "$feature" "$file" "$label" >> web/roms/manifest.json
  first=0
done

printf '\n]\n' >> web/roms/manifest.json
echo "wrote web/roms/manifest.json"
