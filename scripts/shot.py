#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
shot.py — rasterise an SVG so you can actually look at it.

Design work is not verifiable by reading coordinates. This drives a local
headless Chrome/Edge to screenshot an asset at 1:1, so a change can be judged
by eye instead of assumed. Dev tool only — nothing in the profile depends on it.

Usage:
    python scripts/shot.py assets/hero-dark.svg
    python scripts/shot.py assets/hero-dark.svg --size 1280x400 --out /tmp/h.png
    python scripts/shot.py assets/hero-dark.svg --wait 3000   # mid-animation
"""

import argparse
import os
import subprocess
import sys

CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
]


def find_browser():
    for path in CANDIDATES:
        if os.path.exists(path):
            return path
    raise SystemExit("no Chrome/Edge found — add its path to CANDIDATES")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("svg")
    ap.add_argument("--size", default="1280x400", help="WxH, match the viewBox")
    ap.add_argument("--out", default=None, help="default: alongside the svg")
    ap.add_argument("--wait", type=int, default=1200,
                    help="ms to let the page settle before shooting")
    ap.add_argument("--scale", type=float, default=1.0, help="device scale factor")
    args = ap.parse_args()

    svg = os.path.abspath(args.svg)
    if not os.path.exists(svg):
        raise SystemExit("no such file: " + svg)

    if args.out:
        out = os.path.abspath(args.out)
    else:
        # Keep shots out of assets/ — they are scratch, and .preview/ is
        # already gitignored.
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        shots = os.path.join(root, ".preview")
        if not os.path.isdir(shots):
            os.makedirs(shots)
        out = os.path.join(shots,
                           os.path.splitext(os.path.basename(svg))[0] + ".png")

    width, height = args.size.lower().split("x")
    url = "file:///" + svg.replace("\\", "/").lstrip("/")

    cmd = [
        find_browser(),
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        "--default-background-color=00000000",
        "--force-device-scale-factor={}".format(args.scale),
        "--window-size={},{}".format(width, height),
        "--virtual-time-budget={}".format(args.wait),
        "--screenshot=" + out,
        url,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if not os.path.exists(out):
        sys.stderr.write(proc.stdout[-2000:] + proc.stderr[-2000:])
        raise SystemExit("screenshot failed")

    print("{} -> {} ({} bytes)".format(
        os.path.basename(svg), out, os.path.getsize(out)))


if __name__ == "__main__":
    main()
