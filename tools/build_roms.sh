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
  # First in the list, right under the two ROMs the page hard-codes. No demo
  # feature at all, so it is the whole game as it actually ships: the release
  # profile, without the debug aids web/bn6-rust.gba is built with (that one
  # starts the gauge full, opens the chip window on L/R and fields a lone
  # Mettaur). This is the one to look at to see every change at once.
  "default rollup Rollup (release build): the whole battle at once -- chip select, the fight, the results, the full enemy line-up"
  "demo-buster buster Buster / charge shot"
  "demo-sword sword Sword / WideSwrd / LongSwrd"
  "demo-minibomb minibomb MiniBomb"
  "demo-cannon cannon Cannon / HiCannon"
  "demo-cannon,demo-sterile,demo-auto cannon-real Cannon on black, auto-fire: matched frame-for-frame to the real ROM"
  "demo-sword,demo-sterile,demo-auto sword-real Sword on black, auto-fire: matched frame-for-frame to the real ROM"
  "demo-wideswrd,demo-sterile,demo-auto wideswrd-real WideSwrd on black, auto-fire: matched frame-for-frame to the real ROM"
  "demo-recovery,demo-sterile,demo-auto recov-real Recov10 on black, auto-fire: matched frame-for-frame to the real ROM"
  "demo-airshot,demo-sterile,demo-auto airshot-real AirShot on black, auto-fire: matched frame-for-frame to the real ROM"
  "demo-minibomb,demo-sterile,demo-auto minibomb-real MiniBomb on black, auto-fire: matched frame-for-frame to the real ROM"
  "demo-vulcan,demo-sterile,demo-auto vulcan-real Vulcan1 on black, auto-fire: matched frame-for-frame to the real ROM"
  "demo-hicannon,demo-sterile,demo-auto hicannon-real HiCannon on black, auto-fire: matched frame-for-frame to the real ROM"
  "demo-mcannon,demo-sterile,demo-auto mcannon-real M-Cannon on black, auto-fire: matched frame-for-frame to the real ROM"
  "demo-longswrd,demo-sterile,demo-auto longswrd-real LongSwrd on black, auto-fire: matched frame-for-frame to the real ROM"
  "demo-recov30,demo-sterile,demo-auto recov30-real Recov30 on black, auto-fire: matched frame-for-frame to the real ROM"
  "demo-invisibl,demo-sterile,demo-auto invisibl-real Invisibl on black, auto-fire: matched frame-for-frame to the real ROM"
  "demo-barrier,demo-sterile,demo-auto barrier-real Barrier on black, auto-fire: matched frame-for-frame to the real ROM"
  "demo-vulcan vulcan Vulcan1 volley"
  "demo-airshot airshot AirShot"
  "demo-recovery recovery Recov / Invisibl / Barrier"
  "demo-mettaur mettaur Mettaur AI"
  "demo-gunner gunner Gunner AI"
  "demo-protoman protoman ProtoMan AI"
  "demo-colonel colonel Colonel AI"
  "demo-poisseed,demo-sterile,demo-auto poisseed-real PoisSeed on black, auto-fire: the pod, its arc and the poison going down, matched to the real ROM"
  "demo-iceseed,demo-sterile,demo-auto iceseed-real IceSeed on black, auto-fire: matched frame-for-frame to the real ROM"
  "demo-grasseed,demo-sterile,demo-auto grasseed-real GrasSeed on black, auto-fire: matched frame-for-frame to the real ROM"
  "demo-bugbomb,demo-sterile,demo-auto bugbomb-real BugBomb on black, auto-fire: matched frame-for-frame to the real ROM"
  "demo-vdoll,demo-sterile,demo-auto vdoll-real VDoll on black, auto-fire: matched frame-for-frame to the real ROM"
  "demo-results results Results screen"
  "demo-hudmatch hudmatch HUD fixture: 60 HP, full gauge, Cannon in hand -- the battle screen matched to the real ROM tile for tile"
  "demo-custmatch custmatch Chip select fixture: the same five chips the real ROM's window offers, matched to it pixel for pixel"
  "demo-cardname cardname Chip select fixture with the cursor on a chip: the preview card -- name, picture, code, element and damage -- matched pixel for pixel"
  "demo-resultmatch resultmatch RESULT window fixture: the capture's own clear time and busting level, matched pixel for pixel"
  "demo-areagrab areagrab AreaGrab: stealing the enemy's front column"
  "demo-vulcan2 vulcan2 Vulcan2 (four shots)"
  "demo-vulcan3 vulcan3 Vulcan3 (five shots)"
  "demo-recov50 recov50 Recov50"
  "demo-fireswrd fireswrd FireSwrd"
  "demo-elecswrd elecswrd ElecSwrd"
  "demo-wideblde wideblde WideBlde"
  "demo-bigbomb bigbomb BigBomb: a nine-panel blast"
  "demo-suprvulc suprvulc SuprVulc (ten shots)"
  "demo-muramasa muramasa Muramasa"
  "demo-suprvulc,demo-sterile,demo-auto suprvulc-real SuprVulc on black, auto-fire: matched frame-for-frame to the real ROM"
  "demo-recov80,demo-sterile,demo-auto recov80-real Recov80 on black, auto-fire: matched frame-for-frame to the real ROM"
  "demo-recov120,demo-sterile,demo-auto recov120-real Recov120 on black, auto-fire: matched frame-for-frame to the real ROM"
  "demo-recov150,demo-sterile,demo-auto recov150-real Recov150 on black, auto-fire: matched frame-for-frame to the real ROM"
  "demo-recov200,demo-sterile,demo-auto recov200-real Recov200 on black, auto-fire: matched frame-for-frame to the real ROM"
  "demo-stepswrd,demo-sterile,demo-auto stepswrd-real StepSwrd on black, auto-fire: 33 of 40 frames match the real ROM exactly"
  "demo-blkbomb,demo-sterile,demo-auto blkbomb-real BlkBomb on black, auto-fire: matched frame-for-frame to the real ROM"
  "demo-lilbolr,demo-sterile,demo-auto lilbolr-real LilBolr1 on black, auto-fire: matched frame-for-frame to the real ROM (the figure under the boiler is its own HP)"
  "demo-energbom,demo-sterile,demo-auto energbom-real EnergBom on black, auto-fire: matched frame-for-frame to the real ROM"
  "demo-megenbom,demo-sterile,demo-auto megenbom-real MegEnBom on black, auto-fire: matched frame-for-frame to the real ROM"
  "demo-barr100,demo-sterile,demo-auto barr100-real Barr100 on black, auto-fire: matched frame-for-frame to the real ROM"
  "demo-barr200,demo-sterile,demo-auto barr200-real Barr200 on black, auto-fire: matched frame-for-frame to the real ROM"
  "demo-bigbomb,demo-sterile,demo-auto bigbomb-real BigBomb on black, auto-fire: matched frame-for-frame to the real ROM"
)

mkdir -p web/roms

# Built in parallel. Sixty-odd `cargo build --release --features X` runs take
# about a quarter of an hour one after another, and they cannot simply be
# backgrounded: cargo locks its target directory, so concurrent invocations
# queue rather than overlap, and worse, they would each overwrite the same
# target/.../bn that the gbafix step reads. Each job therefore gets its OWN
# CARGO_TARGET_DIR under /tmp -- disk for wall clock -- and does its own
# gbafix out of that directory. JOBS defaults to half the cores, because a
# rustc invocation is itself threaded.
JOBS="${JOBS:-$(( $(nproc) / 2 > 1 ? $(nproc) / 2 : 1 ))}"
BUILD_ROOT="${BUILD_ROOT:-/tmp/bn_roms_build}"
mkdir -p "$BUILD_ROOT"

build_one() {
  local slot="$1" feature="$2" file="$3"
  local target="$BUILD_ROOT/$slot"
  echo "building $feature -> web/roms/$file.gba"
  CARGO_TARGET_DIR="$target" cargo build --release --features "$feature" \
    || { echo "FAILED $feature"; return 1; }
  python3 tools/gbafix.py "$target/thumbv4t-none-eabi/release/bn" "web/roms/$file.gba"
}
export -f build_one
export BUILD_ROOT

# One slot per worker, handed out round robin, so a worker reuses its own
# target directory across its jobs and keeps its incremental artifacts.
i=0
for entry in "${ENTRIES[@]}"; do
  read -r feature file label <<< "$entry"
  printf '%s\0%s\0%s\0' "$(( i % JOBS ))" "$feature" "$file"
  i=$(( i + 1 ))
done | xargs -0 -n 3 -P "$JOBS" bash -c 'build_one "$0" "$1" "$2"'

# The manifest is written after the builds, in the order of ENTRIES, so the
# dropdown does not depend on which job finished first.
: > web/roms/manifest.json
printf '[' >> web/roms/manifest.json
first=1
for entry in "${ENTRIES[@]}"; do
  read -r feature file label <<< "$entry"
  if [ ! -f "web/roms/$file.gba" ]; then echo "missing web/roms/$file.gba"; exit 1; fi
  if [ "$first" -eq 0 ]; then printf ',' >> web/roms/manifest.json; fi
  printf '\n  {"feature": "%s", "file": "roms/%s.gba", "label": "%s"}' \
    "$feature" "$file" "$label" >> web/roms/manifest.json
  first=0
done

printf '\n]\n' >> web/roms/manifest.json
echo "wrote web/roms/manifest.json"
