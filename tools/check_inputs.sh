#!/usr/bin/env bash
# Refuse to measure against a changed input: the real and sterile ROMs in /tmp must match the backup
# byte for byte (canon never changes). Called by verify_rows.py and land.sh; run it by hand after any
# tool that touches /tmp. Exit 1 with the mismatching file named.
BACKUP=/home/box/bn-backup; rc=0
for f in bn6f_real.gba bn6f_sterile.gba chipselect.state pausedwithcannon.state; do
  [ -f "$BACKUP/$f" ] || continue
  a=$(sha1sum "/tmp/$f" 2>/dev/null | cut -c1-40); b=$(sha1sum "$BACKUP/$f" | cut -c1-40)
  [ "$a" = "$b" ] || { echo "check_inputs: /tmp/$f differs from the backup (canon changed?) -- bash tools/restore_inputs.sh" >&2; rc=1; }
done
exit $rc
