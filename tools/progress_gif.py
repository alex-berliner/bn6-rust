#!/usr/bin/env python3
"""A before/after progress GIF for one harness row: canon on top, then our build at <before>, then our
build at <after>, each on the alignment THAT commit's harness used (so a change of alignment shows as
what it is). Each ref is built in its own clean detached checkout; nothing in the working tree is used.

usage: python3 tools/progress_gif.py <row> <before-ref> [<after-ref>=HEAD] [--ui isolated] [--out FILE]
writes web/captures/<row>-progress.gif and .txt by default.
"""
import argparse, json, os, subprocess, sys
from PIL import Image, ImageDraw

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
W, H, BAR, SCALE, DELAY_MS = 240, 160, 12, 2, 20

DUMP = r'''
import json, sys, os
sys.path.insert(0, "tools")
import harness as h, chip_compare as cc
row, ui, out = sys.argv[1], sys.argv[2], sys.argv[3]
check = next(c for c in h.CHECKS if c.name == row)
res = h.run(check.rust(ui), check.canon(ui), check.frames, check.align)
os.makedirs(out, exist_ok=True)
for k in range(len(res.counts)):
    cc.frame(res.canon_dir, res.canon_ref + k).save("%s/canon_%03d.png" % (out, k))
    cc.frame(res.rust_dir, res.rust_origin + res.rust_offset + k).save("%s/rust_%03d.png" % (out, k))
json.dump({"n": len(res.counts), "total": res.total, "worst": res.worst, "canon_ref": res.canon_ref,
           "rust_offset": res.rust_offset, "counts": list(res.counts)}, open(out + "/meta.json", "w"))
'''


def dump(ref, row, ui, out):
    sha = subprocess.run(["git", "-C", ROOT, "rev-parse", "--short", ref], check=True,
                         capture_output=True, text=True).stdout.strip()
    wt, target = "/tmp/bnwt/progress-%s" % sha, "/tmp/ct_progress"  # persistent: warm rebuilds
    if not os.path.exists(wt):
        subprocess.run(["git", "-C", ROOT, "worktree", "add", "--detach", wt, sha], check=True, capture_output=True)
        subprocess.run(["rm", "-rf", os.path.join(wt, "reference/bn6f")], check=True)
        os.symlink(os.path.join(ROOT, "reference/bn6f"), os.path.join(wt, "reference/bn6f"))
    env = dict(os.environ, CARGO_TARGET_DIR=target, CARGO_BUILD_JOBS=os.environ.get("CARGO_BUILD_JOBS", "2"))
    subprocess.run([sys.executable, "-c", DUMP, row, ui, out], cwd=wt, env=env, check=True,
                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    subprocess.run(["git", "-C", ROOT, "worktree", "remove", "--force", wt], capture_output=True)
    return sha, json.load(open(out + "/meta.json"))


def labelled(im, text):
    panel = Image.new("RGB", (W, H + BAR), (20, 20, 26))
    ImageDraw.Draw(panel).text((3, 1), text, fill=(230, 230, 230))
    panel.paste(im, (0, BAR))
    return panel


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("row"); ap.add_argument("before"); ap.add_argument("after", nargs="?", default="HEAD")
    ap.add_argument("--ui", default="isolated"); ap.add_argument("--out")
    a = ap.parse_args()
    tmp = "/tmp/bn-progress-%s" % a.row
    subprocess.run(["rm", "-rf", tmp])
    bsha, bm = dump(a.before, a.row, a.ui, tmp + "/before")
    asha, am = dump(a.after, a.row, a.ui, tmp + "/after")
    n = min(bm["n"], am["n"])
    frames = []
    for k in range(n):
        top = labelled(Image.open("%s/after/canon_%03d.png" % (tmp, k)), "canon  k=%d" % k)
        b = labelled(Image.open("%s/before/rust_%03d.png" % (tmp, k)),
                     "ours @%s  %d px" % (bsha, bm["counts"][k]))
        c = labelled(Image.open("%s/after/rust_%03d.png" % (tmp, k)),
                     "ours @%s  %d px" % (asha, am["counts"][k]))
        sheet = Image.new("RGB", (W, 3 * (H + BAR) + 6), (70, 70, 80))
        for i, p in enumerate((top, b, c)):
            sheet.paste(p, (0, i * (H + BAR + 3)))
        frames.append(sheet.resize((sheet.width * SCALE, sheet.height * SCALE), Image.NEAREST))
    out = a.out or os.path.join(ROOT, "web/captures", "%s-progress.gif" % a.row)
    frames[0].save(out, save_all=True, append_images=frames[1:], duration=DELAY_MS, loop=0, optimize=True)
    with open(out[:-4] + ".txt", "w") as f:
        f.write("%s (%s), before and after: canon on top; ours at %s (%d px over %d frames, canon %d+k, rust "
                "offset %d); ours at %s (%d px, canon %d+k, rust offset %d). Each build on its own commit's "
                "alignment, from a clean checkout (tools/progress_gif.py).\n" % (
                    a.row, a.ui, bsha, bm["total"], bm["n"], bm["canon_ref"], bm["rust_offset"],
                    asha, am["total"], am["canon_ref"], am["rust_offset"]))
    print("wrote %s (%d frames): before %d px, after %d px" % (out, n, bm["total"], am["total"]))


if __name__ == "__main__":
    main()
