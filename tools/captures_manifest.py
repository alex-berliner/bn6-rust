#!/usr/bin/env python3
"""Build web/captures/manifest.json from the .gif files in web/captures/.

The web/gifs.html gallery reads this to show one card per capture. A capture
file is named <name>.gif; its caption defaults to the name unless an optional
sidecar <name>.txt holds one. Run after dropping a new .gif into web/captures/.

Order is NEWEST FIRST, so the gallery leads with the most recent work rather
than with whatever happens to start with an "a". "Newest" is the date of the
commit that ADDED the file, read from git, which is stable across checkouts in
a way file mtimes are not -- a fresh clone gives every file the same mtime. A
capture that is not committed yet sorts to the very front, which is where a
just-built comparison belongs while it is being looked at.

usage: python3 tools/captures_manifest.py
"""
import json
import os
import subprocess

WEB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "web", "captures")
REPO = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")


def caption_for(name, base):
    txt = os.path.join(WEB, base + ".txt")
    if os.path.exists(txt):
        with open(txt) as f:
            return f.read().strip()
    # Humanise the stub: "cannon" -> "Cannon", "sword-slash" -> "Sword slash".
    return name.replace("-", " ").title()


def added_dates():
    """filename -> (unix time, YYYY-MM-DD) of the commit that added it.

    `--diff-filter=A` lists only the additions, and git walks history newest
    first, so the first time a name appears is its most recent addition --
    which is the right answer for a capture that was deleted and rebuilt.
    Returns an empty map if git is not available or this is not a checkout;
    the caller then falls back to mtime.
    """
    try:
        out = subprocess.run(
            ["git", "log", "--diff-filter=A", "--format=@%at %ad", "--date=short",
             "--name-only", "--", "web/captures/*.gif"],
            cwd=REPO, capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return {}
    dates, when = {}, None
    for line in out.splitlines():
        if line.startswith("@"):
            stamp, day = line[1:].split(" ", 1)
            when = (int(stamp), day)
        elif line.endswith(".gif") and when is not None:
            dates.setdefault(os.path.basename(line), when)
    return dates


def main():
    dates = added_dates()
    entries = []
    for fn in os.listdir(WEB):
        if not fn.endswith(".gif"):
            continue
        base = fn[:-4]
        # Uncommitted captures sort to the front: float("inf") beats every
        # real commit time, and they get no date badge because they have no
        # committed date to show.
        stamp, day = dates.get(fn, (float("inf"), None))
        entries.append({
            "file": "captures/" + fn,
            "name": base,
            "label": caption_for(base, base),
            "added": day,
            "_sort": stamp,
        })
    # Newest first; ties (a batch committed together) fall back to the name so
    # the order within one day is at least stable between runs.
    entries.sort(key=lambda e: (-e["_sort"], e["name"]))
    for e in entries:
        del e["_sort"]
    out = os.path.join(WEB, "manifest.json")
    with open(out, "w") as f:
        json.dump(entries, f, indent=2)
    print(f"wrote {out} ({len(entries)} captures, newest first)")


if __name__ == "__main__":
    main()
