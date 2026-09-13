#!/usr/bin/env python3
"""F16 one-off probe: for every row whose fixture has enemies, capture the
row's own canon side with a wide watch over the whole eT1BattleObjects table
(20 slots, stride 0xD8, ewram.s:2972-2992) and report which slot is the
POPULATED enemy at the row's first compared frame (canon_ref). The result
feeds oracle.py's per-row enemy-slot table (provenance: peeked, per row).
Serialized captures -- never two at once."""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chip_compare as cc  # noqa: E402
import harness as H  # noqa: E402

TABLE = 0x0203A9B0  # eT1BattleObject0 (ewram.s:2973)
SLOT = 0xD8         # stride (0x203aa88 - 0x203a9b0)
NSLOTS = 12


def main() -> None:
    for check in H.CHECKS:
        variant = "isolated" if check.ui in ("isolated", "both") else "integrated"
        side = check.canon(variant)
        # enemy presence is a property of the ROW's fixture descriptor, which
        # lives on the RUST side; the canon side reproduces the same scenario
        # via its own state/pokes and carries no descriptor.
        fx = check.rust(variant).fixture or {}
        if not (fx.get("enemies", 0)):
            continue
        out = cc.scratch("f16slot_%s" % check.name)
        watch = "--watch", "%#x:%d:%s" % (TABLE, SLOT * NSLOTS, out)
        if os.path.exists(out):
            os.unlink(out)
        count = check.align.canon_ref + check.frames + 10
        cc.capture(side.resolved_rom(), "f16slotcap_%s" % check.name, count,
                   *side.args(), *watch)
        data = open(out, "rb").read()
        rows = len(data) // (SLOT * NSLOTS)
        print("== %s: canon_ref=%d frames=%d capture rows=%d"
              % (check.name, check.align.canon_ref, check.frames, rows))
        for label, k in (("first compared", check.align.canon_ref),
                         ("last compared", check.align.canon_ref + check.frames - 1)):
            row = data[k * SLOT * NSLOTS:(k + 1) * SLOT * NSLOTS]
            live = []
            for i in range(NSLOTS):
                b = row[i * SLOT:(i + 1) * SLOT]
                state, action = b[8], b[9]
                hp = struct.unpack_from("<H", b, 0x24)[0]
                if state or hp:
                    live.append("slot%d@%#x state=%02x act=%02x hp=%04x"
                                % (i, TABLE + i * SLOT, state, action, hp))
            print("  %s (canon frame %d): %s" % (label, k, "; ".join(live) or "NONE populated"))
        os.system("rm -rf f16slotcap_%s" % check.name)


if __name__ == "__main__":
    main()
