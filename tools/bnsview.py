#!/usr/bin/env python3
"""Render an exported BNSP asset (tools/spr_export.py output) to a contact sheet.

usage: bnsview.py <file.bin> <out.png> [--anim N]
"""
import sys, os, struct
from PIL import Image

def view(path, out, anim=0):
    data = open(path, 'rb').read()
    assert data[0:4] == b'BNSP', data[0:4]
    ver, gfx, pal, anim_off, frame_off, oam_off = struct.unpack('<IIIIII', data[4:28])
    # anim table: u32 count, count*(u16 first, u16 count)
    acount = struct.unpack('<I', data[anim_off:anim_off+4])[0]
    first, cnt = struct.unpack('<HH', data[anim_off+4+anim*4:anim_off+8+anim*4])
    # gfx table: u32 count, count*(u32 off, u32 len)
    gcount = struct.unpack('<I', data[gfx:gfx+4])[0]
    gfx_tab = gfx + 4
    # palette: u32 count, count*32 bytes (16 u16 BGR555)
    pcount = struct.unpack('<I', data[pal:pal+4])[0]
    pal0 = pal + 4
    def bgr555(i):
        c = struct.unpack('<H', data[pal0 + i*2: pal0 + i*2 + 2])[0]
        r = (c & 0x1f) * 255 // 31
        g = ((c>>5)&0x1f) * 255 // 31
        b = ((c>>10)&0x1f) * 255 // 31
        return (r, g, b)
    palette = [bgr555(i) for i in range(16)]
    # oam table: u32 count, count*OamRec(u16 tile, i8 x, i8 y, u8 ss, u8 flags)
    ocount = struct.unpack('<I', data[oam_off:oam_off+4])[0]

    def get_tiles(gidx):
        goff, glen = struct.unpack('<II', data[gfx_tab + gidx*8 : gfx_tab + gidx*8 + 8])
        start = gfx + goff
        return data[start:start+glen]

    cells = []
    for fi in range(cnt):
        fo = frame_off + 4 + (first+fi)*10
        gf, pl, oamf, oamc, dur, flags = struct.unpack('<HHHHBB', data[fo:fo+10])
        tiles = get_tiles(gf)
        # render oam entries
        # OBJ dims by (shape, size): ss = shape<<2 | size
        dims = {
            0x0:(8,8),0x1:(16,16),0x2:(32,32),0x3:(64,64),
            0x4:(16,8),0x5:(32,8),0x6:(32,16),0x7:(64,32),
            0x8:(8,16),0x9:(8,32),0xa:(16,32),0xb:(32,64),
        }
        # canvas big enough
        minx=miny=0; maxx=maxy=64
        parts=[]
        for oi in range(oamc):
            o = oam_off + 4 + (oamf+oi)*6
            tile, ox, oy, ss, fl = struct.unpack('<HbbBB', data[o:o+6])
            shape = ss >> 2; size = ss & 3
            key = (shape << 2) | size
            w,h = dims.get(key,(8,8))
            parts.append((tile,ox,oy,w,h,fl))
            minx=min(minx,ox); maxx=max(maxx,ox+w)
            miny=min(miny,oy); maxy=max(maxy,oy+h)
        cw=maxx-minx+4; ch=maxy-miny+4
        im=Image.new('RGB',(cw,ch),(24,24,32))
        for tile,ox,oy,w,h,fl in parts:
            # decode tile: 4bpp, 'w*h/8' tiles, 32 bytes each (2 tiles per 8x8)
            # object spans w x h; tiles stored row-major per object
            rows = h // 8
            cols = w // 8
            tiles_w = cols * rows
            for ty in range(rows):
                for tx in range(cols):
                    t = tile + ty*cols + tx
                    base = t*32
                    for py in range(8):
                        row = tiles[base + py*4 : base + py*4 + 4]
                        for px_ in range(8):
                            nib = (row[px_//2] >> (4*(1-(px_%2)))) & 0xF
                            if nib:
                                col = palette[nib]
                                im.putpixel((ox-minx+2+tx*8+px_, oy-miny+2+ty*8+py), col)
        cells.append(im)
    W=sum(c.width for c in cells); H=max(c.height for c in cells)
    sheet=Image.new('RGB',(W,H),(24,24,32)); x=0
    for c in cells: sheet.paste(c,(x,0)); x+=c.width
    sheet.save(out)
    print(f"{len(cells)} frames -> {out} ({W}x{H})")

if __name__=='__main__':
    args=sys.argv[1:]
    path=args[0]; out=args[1]
    anim=0
    if '--anim' in args: anim=int(args[args.index('--anim')+1])
    view(path,out,anim)
