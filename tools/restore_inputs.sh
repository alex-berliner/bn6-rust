#!/usr/bin/env bash
# Restore the /tmp working set after a reboot. /tmp is not durable (HANDOFF.md §1); this has
# bitten twice. The irreplaceable inputs live in $BACKUP (and a copy on /media/box/Scyther/bn-backup).
# Everything else is regenerated: the capture tool, the sterile ROM check, the buildable states.
set -euo pipefail
BACKUP="${BACKUP:-/home/box/bn-backup}"
cd "$(dirname "$0")/.."
for f in bn6f_real.gba bn6f_sterile.gba pausedwithcannon.state chipselect.state; do
  [ -f "/tmp/$f" ] || cp "$BACKUP/$f" /tmp/
done
want=$(cut -c1-40 reference/bn6f/bn6f.sha1); got=$(sha1sum /tmp/bn6f_real.gba | cut -c1-40)
[ "$want" = "$got" ] || { echo "real ROM sha1 mismatch: $got"; exit 1; }
[ -x /tmp/mgba_capture ] || gcc tools/mgba_capture.c -o /tmp/mgba_capture -I/usr/include -lmgba -lm
python3 tools/patch_sterile.py /tmp/bn6f_real.gba /tmp/.sterile_check.gba >/dev/null
cmp -s /tmp/.sterile_check.gba /tmp/bn6f_sterile.gba || { echo "sterile ROM differs from patch_sterile.py output"; exit 1; }
rm -f /tmp/.sterile_check.gba
python3 tools/states.py build all
echo "restored: real, sterile, paused, chipselect, mgba_capture, built states"
echo "still missing (lost with /tmp on 2026-09-08, need recipes): battlestart.state noenemy2.state"
