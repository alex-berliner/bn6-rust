#!/usr/bin/env bash
# The one lane for renaming symbols and struct fields inside the disassembly.
#
#   bash tools/rename_lane.sh --dry-run     # apply, rebuild, check the sha1, revert, report
#   bash tools/rename_lane.sh               # the same, but keep and publish it if the sha1 holds
#
# Renaming reference/bn6f is allowed (the user, 2026-09-17: "It just has to produce the same ROM"),
# but it is the one edit that can break the build for everybody, and the submodule is SHARED -- every
# worktree symlinks to this single copy rather than cloning its own. So renames do not go through a
# worker or a worktree. They go through here, serialized against landings, and they are undone
# automatically unless the rebuilt ROM is byte-identical to canon.
#
# What this adds over running tools/field_names.py by hand, which does none of it:
#
#   - the landing lock, so no merge is reading the submodule mid-rewrite;
#   - a refusal unless the submodule is on bn-notes (a detached HEAD silently orphans the commit,
#     which is exactly what happened to 92705e0d on 2026-09-17);
#   - the sha1 gate: `make` ends in `sha1sum -c bn6f.sha1`, and the rebuild takes ~3 seconds, so
#     there is no excuse for an ungated rename;
#   - a full revert on any failure, leaving the submodule exactly as it was;
#   - the publish half: commit on bn-notes, push the fork, move the superproject pointer.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SUB="$ROOT/reference/bn6f"
CANON_SHA1=0676ecd4d58a976af3346caebb44b9b6489ad099

dry=0; msg=""; selftest=""
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) dry=1 ;;
    --self-test) selftest="$2"; dry=1; shift ;;   # sha1 | build -- prove the gate still bites
    --message) msg="$2"; shift ;;
    *) echo "unknown arg $1" >&2; exit 2 ;;
  esac; shift
done
cd "$ROOT"

# Serialized against landings: a merge that reads the submodule while the .inc files are half-rewritten
# would build something that is neither the old tree nor the new one.
exec 9>/tmp/bn-land.lock; flock -w 1800 9 || { echo "could not take the landing lock in 30 min" >&2; exit 1; }

branch="$(git -C "$SUB" rev-parse --abbrev-ref HEAD)"
[ "$branch" = "bn-notes" ] || { echo "submodule is on '$branch', not bn-notes; refusing (git -C $SUB checkout bn-notes)" >&2; exit 1; }
[ -z "$(git -C "$SUB" status --porcelain)" ] || { echo "submodule has uncommitted changes; refusing:" >&2; git -C "$SUB" status --porcelain >&2; exit 1; }

before="$(git -C "$SUB" rev-parse HEAD)"
revert() { git -C "$SUB" checkout -- . 2>/dev/null || true; git -C "$SUB" reset -q --hard "$before"; }

if [ -n "$selftest" ]; then
  # The gate is the only thing standing between a bad rename and a broken disassembly for everyone,
  # so it gets tested rather than trusted. These two edits are not renames; they are the two ways a
  # rename fails: it still assembles but changes the ROM, or it does not assemble at all.
  echo "== SELF TEST ($selftest): injecting a deliberately bad edit instead of a rename"
  case "$selftest" in
    sha1)  printf '\n\t.byte 0x00\n' >> "$SUB/data.s" ;;   # tab: agbasm reads a colonless line start as a label
    build) printf '\n\t.include "definitely_missing_file.inc"\n' >> "$SUB/data.s" ;;
    *) echo "--self-test takes sha1 or build" >&2; exit 2 ;;
  esac
else
  echo "== applying renames (tools/field_names.py)"
  python3 tools/field_names.py apply
fi

if [ -z "$(git -C "$SUB" status --porcelain)" ]; then
  echo "no field changed -- every rename in the table is already applied. Nothing to do."; exit 0
fi
echo; echo "== files touched"; git -C "$SUB" diff --stat | tail -12

echo; echo "== rebuilding (the gate: the ROM must stay byte-identical to canon)"
if ! make -C "$SUB" >/tmp/rename_build.log 2>&1; then
  echo "BUILD FAILED -- reverting. Last lines:" >&2; tail -15 /tmp/rename_build.log >&2
  revert; echo "submodule restored to $(git -C "$SUB" rev-parse --short HEAD)" >&2; exit 1
fi
got="$(sha1sum "$SUB/bn6f.gba" | cut -d' ' -f1)"
if [ "$got" != "$CANON_SHA1" ]; then
  echo "SHA1 MISMATCH -- reverting. built $got, canon $CANON_SHA1" >&2
  revert; echo "submodule restored to $(git -C "$SUB" rev-parse --short HEAD)" >&2; exit 1
fi
echo "sha1 OK: $got -- the rename changed names only, not one byte of the ROM"

if [ "$dry" = 1 ]; then
  echo; echo "== --dry-run: reverting a good rename so you can inspect the diff first"
  revert; echo "submodule restored to $(git -C "$SUB" rev-parse --short HEAD)"; exit 0
fi

echo; echo "== publishing"
[ -n "$msg" ] || msg="D10: rename Unk_<offset> fields where the evidence states the role

Applied by tools/rename_lane.sh: every use moved with the definition, and the rebuilt ROM is
byte-identical to canon ($CANON_SHA1). Old-to-new map and the evidence for each row are in
docs/renames.md."
git -C "$SUB" add -A
git -C "$SUB" commit -q -m "$msg"
git -C "$SUB" push -q fork bn-notes
new="$(git -C "$SUB" rev-parse --short HEAD)"
echo "submodule committed and pushed: $new"

git add reference/bn6f
git commit -q -m "reference/bn6f: field renames ($new), ROM sha1 unchanged

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>"
git push -q origin main
echo "superproject pointer updated and pushed"

echo; echo "== moving this repo's own citations onto the new names"
python3 tools/apply_renames.py --commit 2>&1 | tail -3
