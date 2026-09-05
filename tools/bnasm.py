"""Helpers for pulling binary data back out of the bn6f disassembly's .s files.

The disassembly stores ROM data as `.byte` / `.word` / `.hword` directives under
a label, so recovering the original bytes means re-assembling those directives.
"""

import re
import struct

_LABEL = re.compile(r"^([A-Za-z_][A-Za-z_0-9]*)::")
_DIRECTIVE = re.compile(r"^\s*\.(byte|hword|short|word|space)\s+(.*)$")


def _values(text):
    for part in text.split("//")[0].split(","):
        part = part.strip()
        if part:
            yield int(part, 0)


def read_symbol(path, symbol, max_bytes=None, through_labels=False):
    """Return the bytes emitted under `symbol`.

    Stops at the next label unless `through_labels` is set. Some blobs (the
    battle tileset and palette among them) have spurious labels pointing into
    their middle, so reading those requires ignoring label boundaries and
    relying on `max_bytes` to bound the read.
    """
    out = bytearray()
    collecting = False
    with open(path) as f:
        for line in f:
            m = _LABEL.match(line)
            if m:
                if collecting and not through_labels:
                    break
                collecting = collecting or m.group(1) == symbol
                continue
            if not collecting:
                continue
            d = _DIRECTIVE.match(line)
            if not d:
                continue
            kind, rest = d.group(1), d.group(2)
            if kind == "space":
                out += b"\0" * next(_values(rest))
            elif kind == "byte":
                out += bytes(v & 0xFF for v in _values(rest))
            elif kind in ("hword", "short"):
                for v in _values(rest):
                    out += struct.pack("<H", v & 0xFFFF)
            else:
                for v in _values(rest):
                    out += struct.pack("<I", v & 0xFFFFFFFF)
            if max_bytes is not None and len(out) >= max_bytes:
                break
    return bytes(out[:max_bytes]) if max_bytes else bytes(out)


def lz77_decompress(data):
    """GBA BIOS LZ77 (compression type 1). `data` starts at the 4-byte header."""
    assert data[0] == 0x10, f"not LZ77 (header byte {data[0]:#x})"
    size = data[1] | (data[2] << 8) | (data[3] << 16)
    out = bytearray()
    p = 4
    while len(out) < size:
        flags = data[p]
        p += 1
        for bit in range(7, -1, -1):
            if len(out) >= size:
                break
            if flags & (1 << bit):
                block = (data[p] << 8) | data[p + 1]
                p += 2
                count = ((block >> 12) & 0xF) + 3
                disp = (block & 0xFFF) + 1
                start = len(out) - disp
                for i in range(count):
                    out.append(out[start + i])
            else:
                out.append(data[p])
                p += 1
    return bytes(out[:size])


def bgr555(v):
    return ((v & 31) * 255 // 31, ((v >> 5) & 31) * 255 // 31, ((v >> 10) & 31) * 255 // 31)


def decode_tile(tiles, index):
    """Decode one 4bpp 8x8 tile into 8 rows of palette indices."""
    off = index * 32
    rows = []
    for y in range(8):
        row = []
        for b in tiles[off + y * 4: off + y * 4 + 4]:
            row.append(b & 0xF)
            row.append(b >> 4)
        rows.append(row)
    return rows
