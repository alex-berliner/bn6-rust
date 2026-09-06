#!/usr/bin/env python3
"""Build web/captures/manifest.json from the .gif files in web/captures/.

The web/gifs.html gallery reads this to show one card per capture. A capture
file is named <name>.gif; its caption defaults to the name unless an optional
sidecar <name>.txt holds one. Run after dropping a new .gif into web/captures/.

usage: python3 tools/captures_manifest.py
"""
import json
import os
import sys

WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "web", "captures")


def caption_for(name, base):
    txt = os.path.join(WEB, base + ".txt")
    if os.path.exists(txt):
        with open(txt) as f:
            return f.read().strip()
    # Humanise the stub: "cannon" -> "Cannon", "sword-slash" -> "Sword slash".
    return name.replace("-", " ").title()


def main():
    entries = []
    for fn in sorted(os.listdir(WEB)):
        if fn.endswith(".gif"):
            base = fn[:-4]
            entries.append({
                "file": "captures/" + fn,
                "name": base,
                "label": caption_for(base, base),
            })
    out = os.path.join(WEB, "manifest.json")
    with open(out, "w") as f:
        json.dump(entries, f, indent=2)
    print(f"wrote {out} ({len(entries)} captures)")


if __name__ == "__main__":
    main()
