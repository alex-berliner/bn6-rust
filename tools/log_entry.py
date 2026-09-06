#!/usr/bin/env python3
"""Add an entry to the web/log screenshot log (the /log.html page).

usage: log_entry.py <screenshot.png> <caption> [--tag label] [--out capture|raw|game]

Copies the screenshot into web/log/ with a timestamped name and appends a
record to web/log/log.json. The /log.html page renders entries reverse
chronologically. Running repeatedly builds a running log.

  - <caption> may be quoted and is rendered under the image.
  --tag   a short label chip (e.g. "cannon", "rust", "real").
  --out   optional subfolder under web/log to group the image.
"""
import argparse
import json
import os
import shutil
import sys
import time

WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "web", "log")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("screenshot")
    ap.add_argument("caption")
    ap.add_argument("--tag", default="")
    ap.add_argument("--out", default="shots")
    args = ap.parse_args()

    os.makedirs(WEB, exist_ok=True)
    sub = os.path.join(WEB, args.out)
    os.makedirs(sub, exist_ok=True)

    ts = int(time.time())
    base = os.path.basename(args.screenshot)
    stem, ext = os.path.splitext(base)
    ext = ext or ".png"
    # Animated GIFs are logged as .gif so the log page plays them; the <img>
    # tag renders both stills and GIFs.
    dest = os.path.join(sub, f"{ts}-{stem}{ext}")
    shutil.copyfile(args.screenshot, dest)

    log_path = os.path.join(WEB, "log.json")
    entries = []
    if os.path.exists(log_path):
        with open(log_path) as f:
            entries = json.load(f)
    entries.append({
        "t": ts,
        "file": f"log/{args.out}/{os.path.basename(dest)}",
        "caption": args.caption,
        "tag": args.tag,
    })
    with open(log_path, "w") as f:
        json.dump(entries, f, indent=2)

    print(f"logged {args.caption} -> {dest} (entry {len(entries)})")


if __name__ == "__main__":
    main()
