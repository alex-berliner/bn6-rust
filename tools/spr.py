"""Parser for the bn6f `.spr` battle sprite container.

Format derived from asm/sprite.s and asm/asm38.s in the bn6f disassembly
(_sprite_loadAnimationData, _sprite_update, sub_8002818, sub_8002874, sub_80030BA).

Layout
------
All table offsets are relative to BASE = file + 4 (sprite_initialize does `add r0, #4`).

  file[0]        u32   header/magic
  BASE + i*4     u32   animation table: offset to animation i's first frame record
                       The table's length is implied: it ends where the first
                       animation's data begins (BASE + table[0]).

Frame record (20 bytes, animations are contiguous runs of these):
  +0x00  u32  offset to graphics blob   -> {u32 byteSize; tiles[byteSize]}
  +0x04  u32  offset to palette blob    -> {u32 stride=0x20; N*(16*u16 BGR555)}
               palette k lives at BASE + field + 4 + k*32
               Colour 0 is transparent; colour 1 is the near-black outline.
  +0x08  u32  offset to sub-animation T -> S = T + T[0], S[0] = OAM list index
  +0x0c  u32  offset to OAM table O     -> entries = O + O[S[0]*4]
  +0x10  u8   duration in frames
  +0x12  u8   flags: 0x80 = last frame, 0x40 = loop back to start

OAM entry (5 bytes, list terminated by a leading 0xFF):
  +0  u8  first tile index into the frame's graphics blob
  +1  s8  x offset from the object origin
  +2  s8  y offset from the object origin
  +3  u8  bits 0-1 = GBA OBJ size, 0x40 = h-flip, 0x80 = v-flip
  +4  u8  bits 0-1 = GBA OBJ shape (0=square, 1=wide, 2=tall),
          bits 4-7 = palette offset, added to the object's base palette index
          (the engine reads this as `Unk_05 = entry[4] >> 4`)

Tiles are standard GBA 4bpp: 8x8, 32 bytes each, low nibble = left pixel,
laid out in 1D mapping (row-major within each object).
"""

import struct

from bnasm import lz77_decompress

# GBA OBJ dimensions in pixels, indexed [shape][size].
OBJ_DIMS = {
    0: [(8, 8), (16, 16), (32, 32), (64, 64)],
    1: [(16, 8), (32, 8), (32, 16), (64, 32)],
    2: [(8, 16), (8, 32), (16, 32), (32, 64)],
}

BASE = 4


def load_sprite_bytes(path):
    """Read a sprite container, decompressing it if LZ77-wrapped.

    `path` may also be `file.s:symbol` for the containers that are assembled
    inline in a data file rather than shipped under data/sprites/ (the charge
    glow, for one). Plain containers do not record their own length, so the
    read runs generously long; the parser only follows offsets, and the
    exporter only copies what frames reference, so the excess is harmless.

    The comp_*.lz77 files hold this same container, just GBA-LZ77 compressed,
    and decompress to `00` + the 3-byte size + the container (sprite_decompress
    skips the prefix: it stores dest+4 as the sprite pointer). A plain
    container's header can also start with 0x10 (e.g. 0x02010010), so only
    treat the data as compressed when it decodes to that shape.
    """
    if ".s:" in path:
        src, symbol = path.rsplit(":", 1)
        from bnasm import read_symbol
        return read_symbol(src, symbol, max_bytes=0x80000, through_labels=True)
    data = open(path, "rb").read()
    if data[0] == 0x10:
        try:
            dec = lz77_decompress(data)
            if dec[:1] == b"\0" and dec[1:4] == data[1:4]:
                data = dec[4:]
        except IndexError:  # stream is not really LZ77, parse it plain
            pass
    return data


class OamEntry:
    __slots__ = ("tile", "x", "y", "size", "shape", "hflip", "vflip", "pal_offset")

    def __init__(self, tile, x, y, size, shape, hflip, vflip, pal_offset):
        self.tile = tile
        self.x = x
        self.y = y
        self.size = size
        self.shape = shape
        self.hflip = hflip
        self.vflip = vflip
        self.pal_offset = pal_offset

    @property
    def dims(self):
        return OBJ_DIMS[self.shape][self.size]


class Frame:
    def __init__(self, gfx, pal, sub, oam, duration, flags):
        self.gfx = gfx
        self.pal = pal
        self.sub = sub
        self.oam = oam
        self.duration = duration
        self.flags = flags

    @property
    def is_last(self):
        return bool(self.flags & 0x80)

    @property
    def loops(self):
        return bool(self.flags & 0x40)


class Sprite:
    def __init__(self, data):
        self.d = data

    def u32(self, off):
        return struct.unpack_from("<I", self.d, off)[0]

    @property
    def anim_offsets(self):
        # The table runs from BASE up to the first animation's data, so the
        # first entry's value is also the table's byte length.
        count = self.u32(BASE) // 4
        return [self.u32(BASE + i * 4) for i in range(count)]

    def frames(self, anim):
        offs = self.anim_offsets
        start = offs[anim]
        end = offs[anim + 1] if anim + 1 < len(offs) else None
        out = []
        i = 0
        while True:
            o = BASE + start + i * 20
            if end is not None and start + i * 20 >= end:
                break
            f = Frame(
                self.u32(o), self.u32(o + 4), self.u32(o + 8), self.u32(o + 12),
                self.d[o + 0x10], self.d[o + 0x12],
            )
            out.append(f)
            i += 1
            if end is None and f.is_last:
                break
        return out

    def tiles(self, frame):
        g = BASE + frame.gfx
        size = self.u32(g)
        return self.d[g + 4: g + 4 + size]

    def palette(self, frame, index=0):
        p = BASE + frame.pal + 4 + index * 32
        return struct.unpack_from("<16H", self.d, p)

    def oam_entries(self, frame):
        t = BASE + frame.sub
        s = t + self.u32(t)
        idx = self.d[s]
        o = BASE + frame.oam
        cur = o + self.u32(o + idx * 4)
        out = []
        while self.d[cur] != 0xFF:
            tile, x, y, b3, b4 = struct.unpack_from("<BbbBB", self.d, cur)
            out.append(OamEntry(
                tile=tile, x=x, y=y,
                size=b3 & 3, hflip=bool(b3 & 0x40), vflip=bool(b3 & 0x80),
                shape=b4 & 3, pal_offset=b4 >> 4,
            ))
            cur += 5
        return out


def bgr555(v):
    return ((v & 31) * 255 // 31, ((v >> 5) & 31) * 255 // 31, ((v >> 10) & 31) * 255 // 31)


def decode_tile(tiles, index):
    """Return an 8x8 list of rows of palette indices."""
    off = index * 32
    rows = []
    for y in range(8):
        row = []
        for b in tiles[off + y * 4: off + y * 4 + 4]:
            row.append(b & 0xF)
            row.append(b >> 4)
        rows.append(row)
    return rows


def render_frame(spr, frame, pal_index=0, per_entry_palette=False):
    """Composite one frame. Returns (pixels, width, height, origin_x, origin_y)
    where pixels is a dict {(x, y): (r, g, b)}."""
    tiles = spr.tiles(frame)
    entries = spr.oam_entries(frame)
    # sub_8002818 loads one palette per frame, taken from the first OAM entry
    # (Unk_05 = entries[0][4] >> 4). Pass per_entry_palette=True to instead give
    # each OBJ its own bank, which the hardware also allows.
    frame_pal = pal_index + (entries[0].pal_offset if entries else 0)
    px = {}
    for e in entries:
        colors = spr.palette(
            frame, (pal_index + e.pal_offset) if per_entry_palette else frame_pal
        )
        w, h = e.dims
        tw, th = w // 8, h // 8
        for ty in range(th):
            for tx in range(tw):
                t = decode_tile(tiles, e.tile + ty * tw + tx)
                for py in range(8):
                    for pxx in range(8):
                        v = t[py][pxx]
                        if v == 0:
                            continue
                        ox = (w - 1 - (tx * 8 + pxx)) if e.hflip else (tx * 8 + pxx)
                        oy = (h - 1 - (ty * 8 + py)) if e.vflip else (ty * 8 + py)
                        px[(e.x + ox, e.y + oy)] = bgr555(colors[v])
    return px
