#!/usr/bin/env bash
# Publish web/ to the GitHub Pages branch (gh-pages) of this repo's origin.
#
# Builds the current ROMs, copies the site into a worktree of the generated gh-pages branch, refuses
# to publish anything that is not ours (the real ROM, save states, battery saves -- by name AND by
# ROM header/sha1), commits and pushes. gh-pages is a generated branch: nothing else writes to it.
#
# usage: bash tools/publish_site.sh [--no-build]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SITE="/tmp/bn-site"
REAL_SHA1="$(cut -c1-40 "$ROOT/reference/bn6f/bn6f.sha1")"
cd "$ROOT"

if [ "${1:-}" != "--no-build" ]; then
  export CARGO_BUILD_JOBS="${CARGO_BUILD_JOBS:-2}"
  bash tools/build_roms.sh
  bash tools/web_rom.sh
  python3 tools/captures_manifest.py
fi

if [ ! -d "$SITE/.git" ] && [ ! -f "$SITE/.git" ]; then
  if git ls-remote --exit-code --heads origin gh-pages >/dev/null 2>&1; then
    git fetch -q origin gh-pages:gh-pages 2>/dev/null || true
    git worktree add -q "$SITE" gh-pages
  else
    git worktree add -q --detach "$SITE"
    git -C "$SITE" checkout -q --orphan gh-pages
    git -C "$SITE" rm -rq --cached . >/dev/null 2>&1 || true
  fi
fi

# Replace the site contents with web/, minus everything that is not ours.
find "$SITE" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +
rsync -a \
  --exclude 'real-bn6f*' --exclude '*-real.gba' --exclude '*.state' --exclude '*.ss[0-9]' \
  --exclude '*.sav' --exclude '*.srm' \
  "$ROOT/web/" "$SITE/"
touch "$SITE/.nojekyll"

# Hard guard: every ROM published must be one of ours.
bad=0
while IFS= read -r -d '' rom; do
  title="$(dd if="$rom" bs=1 skip=160 count=12 2>/dev/null | tr -d '\0' | sed 's/ *$//')"
  sha="$(sha1sum "$rom" | cut -c1-40)"
  if [ "$sha" = "$REAL_SHA1" ] || [ "$title" = "MEGAMAN6_FXX" ] || [ "$title" != "BN6 RUST" ]; then
    echo "REFUSING: $rom is not a BN6 RUST build (title '$title', sha1 $sha)" >&2; bad=1
  fi
done < <(find "$SITE" -name '*.gba' -print0)
if find "$SITE" \( -name '*.state' -o -name '*.sav' -o -name '*.srm' -o -name 'real-*' \) | grep -q .; then
  echo "REFUSING: a save state, battery save or real-ROM file reached the site dir" >&2; bad=1
fi
[ "$bad" -eq 0 ] || exit 1

cd "$SITE"
git add --all .
if git diff --cached --quiet; then
  echo "site unchanged; nothing to publish"
else
  git commit -q -m "site: $(cat build.txt 2>/dev/null || date -u +%Y-%m-%dT%H:%MZ)"
  git push -q -u origin gh-pages
  echo "published $(git rev-parse --short HEAD) to gh-pages"
fi
