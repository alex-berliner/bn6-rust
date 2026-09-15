#!/usr/bin/env bash
# Land a worker's branch: reproduce its harness lines from a clean checkout (verify_rows), merge with
# --no-ff, remove the worktree, delete the branch, clean the target dir. One command instead of the
# coordinator spending ~15 turns on the same steps.
#
# usage: bash tools/land.sh <branch> <rows,comma,separated> "<merge message>" [--expect ROW=T/W/F/NEG ...] [--no-verify]
#   exits non-zero, merging nothing, if verify_rows fails.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
branch="${1:?branch}"; rows="${2:?rows}"; msg="${3:?merge message}"; shift 3
verify=1; expects=()
while [ $# -gt 0 ]; do
  case "$1" in
    --no-verify) verify=0 ;;
    --expect) expects+=(--expect "$2"); shift ;;
    *) echo "unknown arg $1" >&2; exit 2 ;;
  esac; shift
done
cd "$ROOT"
bash tools/check_inputs.sh || exit 1
# landings are serialized machine-wide: two concurrent merges into the same checkout would corrupt it
exec 9>/tmp/bn-land.lock; flock -w 1800 9 || { echo "could not take the landing lock in 30 min" >&2; exit 1; }
git diff --quiet && git diff --cached --quiet || { echo "main checkout is dirty; refusing" >&2; exit 1; }
sha="$(git rev-parse --short "$branch")"
if [ "$verify" = 0 ] && git diff --name-only "$(git merge-base HEAD "$branch")" "$branch" | grep -qE '^(src/|vendor/|Cargo|build\.rs|assets/)'; then
  echo "--no-verify refused: $branch changes code (src/, vendor/, Cargo, assets); only docs/web/tools landings may skip verify_rows (F38f, 2026-09-15)" >&2; exit 1
fi
if [ "$verify" = 1 ] && [ -f "/tmp/land_verify_$sha.pass" ] && [ -z "$(find "/tmp/land_verify_$sha.pass" -mmin +30)" ] && [ "$(cat "/tmp/land_verify_$sha.pass")" = "$rows" ]; then
  echo "reusing verify_rows PASS for $sha from $(date -r "/tmp/land_verify_$sha.pass" +%H:%M) (rows: $(cat "/tmp/land_verify_$sha.pass"))"
  printf 'verify_rows: PASS (reused, %s)\n' "$(cat "/tmp/land_verify_$sha.pass")" > /tmp/land_verify.txt
elif [ "$verify" = 1 ]; then
  python3 tools/verify_rows.py "$branch" "$rows" "${expects[@]}" | tee /tmp/land_verify.txt
  grep -q '^verify_rows: PASS' /tmp/land_verify.txt || { echo "verify_rows FAILED; not merging" >&2; exit 1; }
fi
name="${branch#wt/}"
printf '%s\n\nverify_rows: %s\n\nCo-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>\n' "$msg" \
  "$( [ "$verify" = 1 ] && grep -E '^  ' /tmp/land_verify.txt | tr -s ' ' | paste -sd';' || echo skipped )" > /tmp/land_msg.txt
git merge --no-ff -q -F /tmp/land_msg.txt "$branch"
[ -d "/tmp/bnwt/$name" ] && git worktree remove --force "/tmp/bnwt/$name" || true
git branch -d "$branch" >/dev/null 2>&1 || git branch -D "$branch" >/dev/null
rm -rf "/tmp/ct_$name" "/tmp/bn-target-$name"
echo "landed $branch as $(git rev-parse --short HEAD)"
