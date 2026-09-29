#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_stack.py — draw the ~/stack strip.

Replaces skillicons.dev. That service renders each technology as a rounded
square in its own brand colour, which is the single loudest "picked this off a
blog post" signal a profile can carry — nine saturated swatches fighting the
instrument palette. Here every glyph is the same monochrome mark at the same
optical size, and the rail carries the only accent.

Glyph sources
-------------
  * assets/icons/<slug>.svg — real brand paths, pinned from simple-icons
    (CC0 1.0; the marks themselves remain their owners' trademarks). Run
    `python scripts/make_stack.py --fetch` to refresh them.
  * MATLAB has no mark in simple-icons — it was dropped, and no version of the
    package ever carried it. Substituting another product's glyph would be a
    lie, and so would dropping a tool that is actually used, so that slot gets
    a generated isometric surface plot instead. A 3D surface is the motif
    MathWorks is known by anyway, and it belongs in a palette that already
    speaks in plots.

Usage:
    python scripts/make_stack.py             # compose both themes
    python scripts/make_stack.py --fetch     # refresh assets/icons first
"""

import argparse
import math
import os
import sys
import urllib.request
import xml.etree.ElementTree as ET

SVG_NS = "{http://www.w3.org/2000/svg}"

# (slug, label). matplotlib-free; order is roughly "how much of the work".
TOOLS = [
    ("python", "Python"),
    ("javascript", "JavaScript"),
    ("git", "Git"),
    ("github", "GitHub"),
    ("linux", "Linux"),
    ("gnubash", "Bash"),
    ("visualstudiocode", "VS Code"),
    ("latex", "LaTeX"),
    ("matlab", "MATLAB"),
]

# Pinned versions: 13 has the current marks, 12 is the last with VS Code.
ICON_SOURCES = {
    "python": 13, "javascript": 13, "git": 13, "github": 13, "linux": 13,
    "gnubash": 13, "latex": 13, "visualstudiocode": 12,
}

# ── palettes (DESIGN.md §2) ─────────────────────────────────────────────
PALETTES = {
    "dark": {
        "bg": "#0B0E14", "line": "#1C2430",
        "text": "#E6EDF3", "mute": "#5A6675", "accent": "#22D3EE",
    },
    "light": {
        "bg": "#FCFCFD", "line": "#DCE1E8",
        "text": "#0B0E14", "mute": "#6B7684", "accent": "#0E7490",
    },
}

FONT = ('ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, '
        '"Liberation Mono", "DejaVu Sans Mono", monospace')

CARD_W = 880
RAIL_H = 34
GLYPH = 26.0          # target optical size for every mark
GLYPH_Y = 64.0
LABEL_BASELINE = 110.0
CARD_H = 132


def fetch_icons(root):
    """(Re)download the pinned simple-icons files into assets/icons/."""
    out = os.path.join(root, "assets", "icons")
    if not os.path.isdir(out):
        os.makedirs(out)
    for slug, version in sorted(ICON_SOURCES.items()):
        url = ("https://cdn.jsdelivr.net/npm/simple-icons@{}/icons/{}.svg"
               .format(version, slug))
        path = os.path.join(out, slug + ".svg")
        try:
            with urllib.request.urlopen(url, timeout=25) as resp:
                data = resp.read()
            with open(path, "wb") as fh:
                fh.write(data)
            print("  fetched {} ({} bytes)".format(slug, len(data)))
        except Exception as exc:  # noqa: BLE001
            sys.stderr.write("  ! {} -> {}\n".format(url, exc))


def icon_path(root, slug):
    """Pull the path data out of a 24x24 simple-icons file.

    Every one of them is a single <path d="...">, so the geometry lifts out
    cleanly and gets re-emitted at our own scale rather than being nested as a
    sub-<svg>, which keeps the composed file flat and easy to diff.
    """
    path = os.path.join(root, "assets", "icons", slug + ".svg")
    tree = ET.parse(path)
    node = tree.getroot().find(".//" + SVG_NS + "path")
    if node is None:
        raise SystemExit("no <path> in " + path)
    return node.get("d")


def surface_motif(size):
    """An isometric wireframe surface, as a list of inset quadrilateral tiles.

    A saddle height field drawn in isometric projection. Insetting each tile
    toward its own centroid opens hairline gaps so the result reads as a mesh
    rather than a solid blob.

    The grid is deliberately coarse. At 26px a 4x4 mesh turns to mush — the
    gaps fall below a pixel and the tiles bleed into each other — so it is 3x3
    with a wider inset, which still reads as a surface and keeps the gaps open.
    """
    n, gap = 3, 0.17

    def project(i, j):
        u = i / float(n) * 2.0 - 1.0
        v = j / float(n) * 2.0 - 1.0
        z = 0.5 * (u * u - v * v)                  # saddle
        return ((u - v) * 0.866, (u + v) * 0.5 - z)

    grid = {(i, j): project(i, j) for i in range(n + 1) for j in range(n + 1)}

    xs = [p[0] for p in grid.values()]
    ys = [p[1] for p in grid.values()]
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    scale = size / max(w, h)
    ox = -min(xs) * scale + (size - w * scale) / 2.0
    oy = -min(ys) * scale + (size - h * scale) / 2.0

    def place(p):
        return (p[0] * scale + ox, p[1] * scale + oy)

    quads = []
    for i in range(n):
        for j in range(n):
            corners = [place(grid[(i + di, j + dj)])
                       for di, dj in ((0, 0), (1, 0), (1, 1), (0, 1))]
            gx = sum(c[0] for c in corners) / 4.0
            gy = sum(c[1] for c in corners) / 4.0
            shrunk = [(c[0] + (gx - c[0]) * gap, c[1] + (gy - c[1]) * gap)
                      for c in corners]
            quads.append("M" + "L".join("{:.2f},{:.2f}".format(*c) for c in shrunk) + "Z")
    return quads


def build(theme, root):
    p = PALETTES[theme]
    col_w = (CARD_W - 48) / float(len(TOOLS))

    body = []
    for i, (slug, label) in enumerate(TOOLS):
        cx = 24 + col_w * (i + 0.5)
        gx = cx - GLYPH / 2.0
        if slug == "matlab":
            paths = surface_motif(GLYPH)
            body.append('<g transform="translate({:.2f},{:.1f})" fill="{c}" '
                        'fill-opacity="0.8">'.format(gx, GLYPH_Y, c=p["text"]))
            for d in paths:
                body.append('<path d="{}"/>'.format(d))
            body.append('</g>')
        else:
            # 24 -> GLYPH, then position. Non-scaling is fine here: the paths
            # are plain fills with no stroke, so the transform is lossless.
            s = GLYPH / 24.0
            body.append('<g transform="translate({:.2f},{:.1f}) scale({:.5f})" '
                        'fill="{c}" fill-opacity="0.8"><path d="{}"/></g>'
                        .format(gx, GLYPH_Y, s, icon_path(root, slug), c=p["text"]))
        body.append('<text font-size="9.5" x="{:.1f}" y="{:.1f}" fill="{m}" '
                    'text-anchor="middle">{}</text>'
                    .format(cx, LABEL_BASELINE, label, m=p["mute"]))

    return """<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" fill="none" role="img" aria-label="tech stack: {labels}">
  <rect width="{w}" height="{h}" fill="{bg}"/>
  <rect x="0.5" y="0.5" width="{wo}" height="{ho}" fill="none" stroke="{line}" stroke-width="1"/>
  <g font-family='{font}' font-size="11.5" font-weight="600" letter-spacing="1.6">
    <rect x="24" y="11" width="2.5" height="12" fill="{accent}"/>
    <text x="37" y="22" fill="{accent}">SYS.02</text>
    <text x="104" y="22" fill="{mute}">~/stack</text>
    <text x="{note_x}" y="22" fill="{mute}" text-anchor="end">{n} tools</text>
  </g>
  <line x1="24" y1="{rail}" x2="{rail_x}" y2="{rail}" stroke="{line}" stroke-width="1"/>
  <g font-family='{font}'>
{body}
  </g>
</svg>
""".format(w=CARD_W, h=CARD_H, wo=CARD_W - 1, ho=CARD_H - 1,
           labels=", ".join(l for _, l in TOOLS),
           bg=p["bg"], line=p["line"], mute=p["mute"], accent=p["accent"],
           font=FONT, note_x=CARD_W - 24, n=len(TOOLS),
           rail=RAIL_H + 0.5, rail_x=CARD_W - 24,
           body="\n".join("    " + line for line in body))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--theme", choices=("dark", "light", "both"), default="both")
    ap.add_argument("--fetch", action="store_true",
                    help="re-download the pinned simple-icons first")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    root = os.path.dirname(here)

    if args.fetch:
        print("fetching simple-icons ...")
        fetch_icons(root)

    out = args.out or os.path.join(root, "assets")
    themes = ("dark", "light") if args.theme == "both" else (args.theme,)
    for theme in themes:
        svg = build(theme, root)
        path = os.path.join(out, "stack-{}.svg".format(theme))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(svg)
        print("wrote {} ({} bytes)".format(path, len(svg)))


if __name__ == "__main__":
    main()
