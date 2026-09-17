#!/usr/bin/env bash
# Keep the decompiled C in step with what we have learned about the original game. Its field names come from
# the disassembly's own struct macros and its symbol names from the disassembly's labels, so every time those
# improve -- a rename pass, a field that stops being Unk_, a new note that identifies a global -- the C on disk
# is behind until it is re-applied. Re-applying reuses the existing analysis and takes about half a minute, so
# this runs on every launcher tick (every 30 minutes) and does nothing at all when nothing has changed.
#   bash tools/retype_if_stale.sh [--force]
set -uo pipefail
cd "$(dirname "$0")/.."
STAMP="${BN_GHIDRA_PROJECTS:-/home/box/opt/ghidra-projects}/bn6f.work/.bn_inputs_stamp"
[ -d "$(dirname "$STAMP")" ] || { echo "no ghidra project yet; nothing to retype"; exit 0; }
now="$( { git -C reference/bn6f rev-parse HEAD;
          cat reference/bn6f/include/structs/*.inc reference/bn6f/include/rom_structs/*.inc reference/bn6f/include/macros/*.inc 2>/dev/null;
          cat reference/bn6f/docs/renames.md 2>/dev/null; } | sha1sum | cut -c1-40 )"
was="$(cat "$STAMP" 2>/dev/null || echo none)"
if [ "$now" = "$was" ] && [ "${1:-}" != "--force" ]; then exit 0; fi
# never rewrite the C under a running benchmark or replay: a worker reading a file mid-rewrite gets half of it
if pgrep -f 'replay_bench.py|bench_provider.py run' >/dev/null; then echo "retype deferred: a benchmark is running"; exit 0; fi
echo "$(date +%H:%M) the disassembly's types or symbols changed ($was -> $now): re-applying"
if bash tools/ghidra_decompile.sh --retype >/tmp/bn-retype.log 2>&1; then
  echo "$now" > "$STAMP"
  echo "retyped: $(grep -oE '[0-9]+ functions decompiled|[0-9]+ / [0-9]+ declared' /tmp/bn-retype.log | tail -1), $(grep -rl 'unaff_r5' decomp/ 2>/dev/null | wc -l) files still carrying unaff_r5"
else
  echo "retype FAILED; the C on disk is unchanged (see /tmp/bn-retype.log)"; tail -3 /tmp/bn-retype.log
fi
