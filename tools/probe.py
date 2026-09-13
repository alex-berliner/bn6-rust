#!/usr/bin/env python3
"""The measurements workers kept rewriting as throwaway scripts, as one tool.

  probe.py watch <rom> <frames> ADDR[:LEN] [ADDR[:LEN] ...] [capture options] [--every N] [--from F]
      one row per frame, one hex column per address (LEN 1/2/4 decoded little-endian; other LENs as bytes)
  probe.py peek  <rom> <frame> ADDR[:LEN] ... [capture options]
      the values after that frame (unlike mgba_capture --peek, which reads at load)
  probe.py frame <rom> <frames> --at I[,J,...] --out DIR [capture options]
      PNGs of those frames
  probe.py diff  <dirA> <dirB> [--a-start A] [--b-start B] [--frames N] [--region x0,y0,x1,y1]
      differing pixels per frame between two capture dirs (frame A+k vs B+k), total and worst

capture options (any subcommand that captures): --loadstate F, --loadsave F, --script S, --cheat A:V
(repeatable), --poke A:V (repeatable), --poke-at F:A:V (repeatable), --zero A:L (repeatable),
--raw "extra mgba_capture args". ADDR is hex (0x...). Captures go to a scratch dir and are removed.
"""
import argparse, os, shutil, struct, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import chip_compare as cc  # noqa: E402


def cap_args(a):
    out = []
    if a.loadstate: out += ["--loadstate", a.loadstate]
    if a.loadsave: out += ["--loadsave", a.loadsave]
    if a.script: out += ["--script", a.script]
    for v in a.cheat or []: out += ["--cheat", v]
    for v in a.poke or []: out += ["--poke", v]
    for v in a.poke_at or []: out += ["--poke-at", v]
    for v in a.zero or []: out += ["--zero", v]
    if a.raw: out += a.raw.split()
    return out


def add_cap(p):
    p.add_argument("--loadstate"); p.add_argument("--loadsave"); p.add_argument("--script")
    for f in ("--cheat", "--poke", "--poke-at", "--zero"):
        p.add_argument(f, action="append")
    p.add_argument("--raw")


def parse_addr(s):
    addr, _, ln = s.partition(":")
    return int(addr, 16), int(ln or "2", 0)


def decode(b, ln):
    if ln == 1: return "0x%02x" % b[0]
    if ln == 2: return "0x%04x" % struct.unpack("<H", b)[0]
    if ln == 4: return "0x%08x" % struct.unpack("<I", b)[0]
    return b.hex()


def run_capture(rom, count, extra, watches):
    out = cc.scratch("probe_%d" % os.getpid())
    shutil.rmtree(out, ignore_errors=True)
    files = []
    args = list(extra)
    for addr, ln in watches:
        f = out + "_w_%08x.bin" % addr
        files.append((f, ln))
        args += ["--watch", "0x%08x:%d:%s" % (addr, ln, f)]
    if os.path.exists(out + "_w_dummy"): os.remove(out + "_w_dummy")
    for f, _ in files:
        if os.path.exists(f): os.remove(f)
    subprocess.run([cc.CAPTURE, rom, out, str(count)] + args, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    return out, files


def cmd_watch(a):
    watches = [parse_addr(s) for s in a.addrs]
    out, files = run_capture(a.rom, a.frames, cap_args(a), watches)
    data = [(open(f, "rb").read(), ln) for f, ln in files]
    print("frame " + " ".join("%-12s" % ("0x%08x" % addr) for addr, _ in watches))
    for k in range(a.frm, a.frames, a.every):
        cells = []
        for (buf, ln) in data:
            chunk = buf[k * ln:(k + 1) * ln]
            cells.append("%-12s" % (decode(chunk, ln) if len(chunk) == ln else "-"))
        print("%5d " % k + " ".join(cells))
    shutil.rmtree(out, ignore_errors=True)
    for f, _ in files: os.remove(f)


def cmd_peek(a):
    a.frames, a.frm, a.every = a.frame + 1, a.frame, 1
    cmd_watch(a)


def cmd_frame(a):
    out, _ = run_capture(a.rom, a.frames, cap_args(a), [])
    os.makedirs(a.out, exist_ok=True)
    for i in [int(x) for x in a.at.split(",")]:
        cc.frame(out, i).save(os.path.join(a.out, "frame.%05d.png" % i))
        print("wrote %s/frame.%05d.png" % (a.out, i))
    shutil.rmtree(out, ignore_errors=True)


def cmd_diff(a):
    box = tuple(int(v) for v in a.region.split(",")) if a.region else None
    n = a.frames or (len([f for f in os.listdir(a.dirA) if f.endswith(".rgb")]) - a.a_start)
    total, worst = 0, (0, -1)
    for k in range(n):
        try:
            d = cc.diff_frames(a.dirA, a.a_start + k, a.dirB, a.b_start + k, box)
        except FileNotFoundError:
            break
        total += d
        if d > worst[0]: worst = (d, k)
        print("k=%-4d %d" % (k, d))
    print("total %d worst %d at k=%d over %d frames%s" % (total, worst[0], worst[1], k + 1 if n else 0,
                                                          " region %s" % a.region if box else ""))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("watch"); w.add_argument("rom"); w.add_argument("frames", type=int); w.add_argument("addrs", nargs="+")
    w.add_argument("--every", type=int, default=1); w.add_argument("--from", dest="frm", type=int, default=0); add_cap(w)
    p = sub.add_parser("peek"); p.add_argument("rom"); p.add_argument("frame", type=int); p.add_argument("addrs", nargs="+"); add_cap(p)
    f = sub.add_parser("frame"); f.add_argument("rom"); f.add_argument("frames", type=int); f.add_argument("--at", required=True)
    f.add_argument("--out", required=True); add_cap(f)
    d = sub.add_parser("diff"); d.add_argument("dirA"); d.add_argument("dirB"); d.add_argument("--a-start", type=int, default=0)
    d.add_argument("--b-start", type=int, default=0); d.add_argument("--frames", type=int); d.add_argument("--region")
    a = ap.parse_args()
    {"watch": cmd_watch, "peek": cmd_peek, "frame": cmd_frame, "diff": cmd_diff}[a.cmd](a)


if __name__ == "__main__":
    main()
