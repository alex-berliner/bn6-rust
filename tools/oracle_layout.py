#!/usr/bin/env python3
"""The oracle block's layout, from its one Rust source to the Python readers.

src/battle.rs's `ORACLE_LAYOUT` -- one (name, offset, width) entry per region
of the 40-byte ORCL block at 0x02000008, gaps and padding included -- is the
ONLY place the layout is written (Q4). This script parses that table into
docs/oracle_layout.json (committed), which tools/oracle.py reads its field
offsets from and tools/trace.py its block length from. --check (also run by
tools/harness.py's startup self-check) regenerates the parse and refuses a
stale or diverging JSON, so src/battle.rs is authoritative and a reader can
trust the JSON to agree with it.

usage:
  python3 tools/oracle_layout.py            # regenerate docs/oracle_layout.json
  python3 tools/oracle_layout.py --check    # assert JSON == src table == oracle.py's reader
"""
import json
import os
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC = os.path.join(ROOT, "src", "battle.rs")
JSON_PATH = os.path.join(ROOT, "docs", "oracle_layout.json")

#: One ("name", offset, width) tuple literal from the Rust table.
ENTRY = re.compile(r'\(\s*"([^"]+)"\s*,\s*(\d+)\s*,\s*(\d+)\s*\)')
#: The table itself, with its declared entry count (src/battle.rs's
#: `const ORACLE_LAYOUT: [(&str, usize, usize); N] = [...]`).
TABLE = re.compile(
    r"const ORACLE_LAYOUT:\s*\[\(&str, usize, usize\);\s*(\d+)\]\s*=\s*\[(.*?)\];", re.S)
#: The block length constant next to it (`const ORACLE_SNAPSHOT_LEN: usize = 40`),
#: so the "ends at 40" bound is not a second copy of 40 in this file.
BLOCK_LEN = re.compile(r"const ORACLE_SNAPSHOT_LEN:\s*usize\s*=\s*(\d+)")


def parse_src():
    """(block_len, fields) straight out of src/battle.rs, with the same
    in-offset-order / no-overlap / ends-at-block_len check battle.rs's
    `oracle_layout_tiles` does at compile time -- a bad table fails loudly
    here too instead of becoming a silently-wrong reader."""
    src = open(SRC).read()
    m = TABLE.search(src)
    if not m:
        raise SystemExit("oracle_layout: no ORACLE_LAYOUT table in src/battle.rs")
    declared, body = int(m.group(1)), m.group(2)
    mlen = BLOCK_LEN.search(src)
    if not mlen:
        raise SystemExit("oracle_layout: no ORACLE_SNAPSHOT_LEN in src/battle.rs")
    block_len = int(mlen.group(1))
    fields = [(n, int(o), int(w)) for n, o, w in ENTRY.findall(body)]
    if len(fields) != declared:
        raise SystemExit("oracle_layout: table declares %d entries, body has %d"
                         % (declared, len(fields)))
    cursor = 0
    for name, off, width in fields:
        if off < cursor or off + width > block_len:
            raise SystemExit("oracle_layout: field %r overlaps or runs past the "
                             "%d-byte block" % (name, block_len))
        cursor = off + width
    if cursor != block_len:
        raise SystemExit("oracle_layout: table ends at %d, block is %d bytes "
                         "(gaps and padding must be entries too)" % (cursor, block_len))
    return block_len, fields


def document():
    block_len, fields = parse_src()
    return {
        "generated_from": "src/battle.rs ORACLE_LAYOUT by tools/oracle_layout.py "
                          "-- src/battle.rs is authoritative; harness.py's startup "
                          "self-check (oracle_layout.self_check) refuses a stale copy",
        "block": "ORCL",
        "block_addr": "0x02000008",
        "block_len": block_len,
        "fields": [{"name": n, "offset": o, "width": w} for n, o, w in fields],
    }


def generate():
    with open(JSON_PATH, "w") as f:
        json.dump(document(), f, indent=2)
        f.write("\n")


def load():
    with open(JSON_PATH) as f:
        return json.load(f)


def self_check():
    """tools/harness.py's startup self-check (Q4 step 2): (a) the committed
    docs/oracle_layout.json is exactly what src/battle.rs's table generates
    today, and (b) tools/oracle.py's reader reads the same offsets. Raises
    SystemExit on any disagreement."""
    fresh = document()
    committed = load()
    if fresh["fields"] != committed["fields"] or \
       fresh["block_len"] != committed["block_len"] or \
       fresh["block_addr"] != committed["block_addr"]:
        raise SystemExit(
            "oracle_layout: docs/oracle_layout.json is stale against "
            "src/battle.rs ORACLE_LAYOUT -- regenerate with "
            "python3 tools/oracle_layout.py")
    import oracle  # noqa: E402 (harness.py's sys.path already covers tools/)
    if oracle.ORCL_BLOCK_LEN != fresh["block_len"]:
        raise SystemExit("oracle_layout: tools/oracle.py block length disagrees")
    if int(str(oracle.MM_ORACLE_ADDR), 0) != int(fresh["block_addr"], 0):
        raise SystemExit("oracle_layout: tools/oracle.py block address disagrees")
    for f in fresh["fields"]:
        got = oracle.ORCL_OFFSETS.get(f["name"])
        if got != f["offset"]:
            raise SystemExit(
                "oracle_layout: oracle.py reads %r at %s, table says %d"
                % (f["name"], got, f["offset"]))


def main():
    if "--check" in sys.argv[1:]:
        self_check()
        print("oracle_layout: docs/oracle_layout.json agrees with src/battle.rs "
              "and tools/oracle.py")
    else:
        generate()
        print("oracle_layout: wrote %s" % os.path.relpath(JSON_PATH, ROOT))


if __name__ == "__main__":
    main()
