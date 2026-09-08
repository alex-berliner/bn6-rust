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
  # 1. The whole game.
  "default rollup Full battle vs one Mettaur: white intro, BATTLE START!, chip select, the fight, ENEMY DELETED, results"

  # 2. The pixel-parity fixtures: each one is compared with the real ROM by
  #    tools/regress.py and each is at zero.
  "demo-hudmatch hudmatch Battle screen fixture: matched to the real ROM tile for tile, 0 of 38400"
  "demo-custmatch custmatch Chip select fixture: the capture's own five chips, matched pixel for pixel"
  "demo-cardname cardname Preview card fixture: name, picture, code, element and damage, pixel for pixel"
  "demo-resultmatch resultmatch RESULT window fixture: the capture's clear time and busting level, pixel for pixel"
  "demo-sterile,demo-banner banner ENEMY DELETED: the banner's whole 58-frame roll-out, matched to the real ROM"

  # 3. Every chip on black against the real ROM, auto-firing, NEWEST FIRST.
  #    The date is when the chip went in. All 43 are at 0.0 px/frame.
  "demo-vdoll,demo-sterile,demo-auto vdoll-real VDoll -- frame-for-frame with the real ROM (Sep 7)"
  "demo-bugbomb,demo-sterile,demo-auto bugbomb-real BugBomb -- frame-for-frame with the real ROM (Sep 7)"
  "demo-iceseed,demo-sterile,demo-auto iceseed-real IceSeed -- frame-for-frame with the real ROM (Sep 7)"
  "demo-grasseed,demo-sterile,demo-auto grasseed-real GrasSeed -- frame-for-frame with the real ROM (Sep 7)"
  "demo-poisseed,demo-sterile,demo-auto poisseed-real PoisSeed -- frame-for-frame with the real ROM (Sep 7)"
  "demo-flshbom,demo-sterile,demo-auto flshbom-real FlshBom -- frame-for-frame with the real ROM (Sep 7)"
  "demo-lilbolr,demo-sterile,demo-auto lilbolr-real LilBolr1 -- frame-for-frame with the real ROM (Sep 7)"
  "demo-recov80,demo-sterile,demo-auto recov80-real Recov80 -- frame-for-frame with the real ROM (Sep 7)"
  "demo-recov200,demo-sterile,demo-auto recov200-real Recov200 -- frame-for-frame with the real ROM (Sep 7)"
  "demo-recov150,demo-sterile,demo-auto recov150-real Recov150 -- frame-for-frame with the real ROM (Sep 7)"
  "demo-recov120,demo-sterile,demo-auto recov120-real Recov120 -- frame-for-frame with the real ROM (Sep 7)"
  "demo-megenbom,demo-sterile,demo-auto megenbom-real MegEnBom -- frame-for-frame with the real ROM (Sep 6)"
  "demo-energbom,demo-sterile,demo-auto energbom-real EnergBom -- frame-for-frame with the real ROM (Sep 6)"
  "demo-barr200,demo-sterile,demo-auto barr200-real Barr200 -- frame-for-frame with the real ROM (Sep 6)"
  "demo-barr100,demo-sterile,demo-auto barr100-real Barr100 -- frame-for-frame with the real ROM (Sep 6)"
  "demo-muramasa,demo-sterile,demo-auto muramasa-real Muramasa -- frame-for-frame with the real ROM (Sep 6)"
  "demo-suprvulc,demo-sterile,demo-auto suprvulc-real SuprVulc -- frame-for-frame with the real ROM (Sep 6)"
  "demo-wideblde,demo-sterile,demo-auto wideblde-real WideBlde -- frame-for-frame with the real ROM (Sep 6)"
  "demo-recov300,demo-sterile,demo-auto recov300-real Recov300 -- frame-for-frame with the real ROM (Sep 6)"
  "demo-longblde,demo-sterile,demo-auto longblde-real LongBlde -- frame-for-frame with the real ROM (Sep 6)"
  "demo-blkbomb,demo-sterile,demo-auto blkbomb-real BlkBomb -- frame-for-frame with the real ROM (Sep 6)"
  "demo-bigbomb,demo-sterile,demo-auto bigbomb-real BigBomb -- frame-for-frame with the real ROM (Sep 6)"
  "demo-fireswrd,demo-sterile,demo-auto fireswrd-real FireSwrd -- frame-for-frame with the real ROM (Sep 6)"
  "demo-elecswrd,demo-sterile,demo-auto elecswrd-real ElecSwrd -- frame-for-frame with the real ROM (Sep 6)"
  "demo-bambswrd,demo-sterile,demo-auto bambswrd-real BambSwrd -- frame-for-frame with the real ROM (Sep 6)"
  "demo-aquaswrd,demo-sterile,demo-auto aquaswrd-real AquaSwrd -- frame-for-frame with the real ROM (Sep 6)"
  "demo-vulcan3,demo-sterile,demo-auto vulcan3-real Vulcan3 -- frame-for-frame with the real ROM (Sep 6)"
  "demo-vulcan2,demo-sterile,demo-auto vulcan2-real Vulcan2 -- frame-for-frame with the real ROM (Sep 6)"
  "demo-recov50,demo-sterile,demo-auto recov50-real Recov50 -- frame-for-frame with the real ROM (Sep 6)"
  "demo-areagrab,demo-sterile,demo-auto areagrab-real AreaGrab -- frame-for-frame with the real ROM (Sep 6)"
  "demo-mcannon,demo-sterile,demo-auto mcannon-real M-Cannon -- frame-for-frame with the real ROM (Sep 6)"
  "demo-recov30,demo-sterile,demo-auto recov30-real Recov30 -- frame-for-frame with the real ROM (Sep 6)"
  "demo-invisibl,demo-sterile,demo-auto invisibl-real Invisibl -- frame-for-frame with the real ROM (Sep 6)"
  "demo-barrier,demo-sterile,demo-auto barrier-real Barrier -- frame-for-frame with the real ROM (Sep 6)"
  "demo-wideswrd,demo-sterile,demo-auto wideswrd-real WideSwrd -- frame-for-frame with the real ROM (Sep 6)"
  "demo-longswrd,demo-sterile,demo-auto longswrd-real LongSwrd -- frame-for-frame with the real ROM (Sep 6)"
  "demo-hicannon,demo-sterile,demo-auto hicannon-real HiCannon -- frame-for-frame with the real ROM (Sep 6)"
  "demo-vulcan,demo-sterile,demo-auto vulcan-real Vulcan1 -- frame-for-frame with the real ROM (Sep 5)"
  "demo-sword,demo-sterile,demo-auto sword-real Sword -- frame-for-frame with the real ROM (Sep 5)"
  "demo-recovery,demo-sterile,demo-auto recovery-real Recov10 -- frame-for-frame with the real ROM (Sep 5)"
  "demo-minibomb,demo-sterile,demo-auto minibomb-real MiniBomb -- frame-for-frame with the real ROM (Sep 5)"
  "demo-cannon,demo-sterile,demo-auto cannon-real Cannon -- frame-for-frame with the real ROM (Sep 5)"
  "demo-airshot,demo-sterile,demo-auto airshot-real AirShot -- frame-for-frame with the real ROM (Sep 5)"
  "demo-stepswrd,demo-sterile,demo-auto stepswrd-real StepSwrd -- 33 of its 40 frames match the real ROM (Sep 6)"

  # 4. One enemy at a time, so its AI can be watched alone.
  "demo-mettaur mettaur Mettaur AI"
  "demo-gunner gunner Gunner AI"
  "demo-protoman protoman ProtoMan AI"
  "demo-colonel colonel Colonel AI"

  # 5. The buster and its charge, which is not a chip.
  "demo-buster buster Buster / charge shot"
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
# JOBS is capped by MEMORY, not by cores. Each rustc is several hundred MB and
# this box has run out of swap with six of them going, which takes the OOM
# killer to whatever else is running. One job per 2 GB of *available* memory,
# never more than a quarter of the cores, at least one.
avail_gb=$(awk '/MemAvailable/ {print int($2/1024/1024)}' /proc/meminfo)
by_mem=$(( avail_gb / 2 )); by_cpu=$(( $(nproc) / 4 ))
JOBS="${JOBS:-$(( by_mem < by_cpu ? by_mem : by_cpu ))}"
[ "$JOBS" -lt 1 ] && JOBS=1
echo "building with $JOBS parallel jobs (${avail_gb}G available, $(nproc) cores)"
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
