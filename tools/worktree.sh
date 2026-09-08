#!/bin/bash
# Set up an isolated git worktree for one agent, so two agents can never build,
# capture or commit over each other.
#
#   tools/worktree.sh mettaur-departure
#
# prints the directory, the branch and the environment to work in. The agent
# works there and commits to its own branch; the coordinator merges back.
#
# Three things this handles that a bare `git worktree add` does not:
#
#   - reference/bn6f is a submodule and a new worktree checks it out EMPTY.
#     Re-cloning it per agent is wasteful and it is only ever read, so it is
#     symlinked to the main checkout's copy. Read it; do not commit in it. The
#     coordinator makes disassembly comments in the main tree.
#   - cargo needs its own target directory per worktree, or the builds serialise
#     on one lock. A build from a fresh one takes about 30 seconds, and the ROM
#     it produces is byte-identical to the main tree's -- verified, so numbers
#     measured in a worktree are directly comparable.
#   - the capture scratch directory is keyed on the checkout path by
#     chip_compare.scratch(), so this needs no argument: it just works out.
set -eu
name="${1:?usage: tools/worktree.sh <name>}"
# The PRIMARY checkout, not whichever worktree this script was run from --
# git-common-dir points at the real .git for every worktree alike.
main="$(cd "$(git -C "$(dirname "$0")/.." rev-parse --git-common-dir)/.." && pwd)"
dir="/tmp/bnwt/$name"
branch="wt/$name"

if [ -e "$dir" ]; then
  echo "$dir already exists -- reusing it" >&2
else
  mkdir -p /tmp/bnwt
  git -C "$main" worktree add -b "$branch" "$dir" HEAD >&2
  rm -rf "$dir/reference/bn6f"
  ln -s "$main/reference/bn6f" "$dir/reference/bn6f"
fi

cat <<EOF
worktree : $dir
branch   : $branch
env      : export CARGO_TARGET_DIR=/tmp/ct_$name
merge    : git -C $main merge --no-ff $branch
cleanup  : git -C $main worktree remove $dir && git -C $main branch -d $branch
EOF
