#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_hero.py — draw the profile hero banner (instrument-panel style).

The banner is an oscilloscope face. A forward-biased diode I-V sweep is plotted
over a log-current graticule: the amber trace is the measurement, the cyan
trace is the single-diode model fitted to it, the fitted parameters are printed
in the corner, and a sweep band travels across the screen.

Strip the animation and the frame is still complete — that is a hard rule,
see DESIGN.md §4. The band brightens what is already there; it never carries
information.

Why a generator instead of a hand-written SVG:
  The dark and light variants must be the *same drawing* with a different
  palette. Two hand-maintained files drift the moment one coordinate is
  nudged, and here the two traces have to agree to the pixel for the
  measurement-vs-model wedge to read at all. So geometry is written once and
  the palette is a parameter.

Usage:
    python scripts/make_hero.py                # both themes
    python scripts/make_hero.py --theme dark
    python scripts/make_hero.py --palette      # dump the colour tables
"""

import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ivcurve  # noqa: E402  (needs the sys.path line above to work)

W, H = 1280, 400

# ── palette ─────────────────────────────────────────────────────────────
# Mirrors DESIGN.md §2. The accents are deliberately NOT the same value in
# both themes: bright cyan #22D3EE on paper white is 1.9:1, i.e. unreadable,
# so the light theme drops to cyan-700 / amber-700 to clear AA.
DARK = {
    "bg": "#0B0E14", "elev": "#10151F", "well": "#080B10",
    "line": "#1C2430", "grid": "#1A2330", "grid_minor": "#131A24",
    "text": "#E6EDF3", "dim": "#8B96A5", "mute": "#5A6675",
    "accent": "#22D3EE", "accent2": "#F59E0B",
    "glow": True, "ambient": "0.18", "vig": 0.95,
}
LIGHT = {
    "bg": "#FCFCFD", "elev": "#F4F6F8", "well": "#FFFFFF",
    "line": "#DCE1E8", "grid": "#E4E9EF", "grid_minor": "#F0F3F7",
    "text": "#0B0E14", "dim": "#4A5561", "mute": "#6B7684",
    "accent": "#0E7490", "accent2": "#B45309",
    "glow": False, "ambient": "0.05", "vig": 0.9,
}

MONO = ('ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, '
        '"Liberation Mono", "DejaVu Sans Mono", monospace')

# ── geometry ────────────────────────────────────────────────────────────
# Everything on an 8px rhythm (DESIGN.md §3). The exceptions are the plot box
# edges, which are derived from the screen rect plus a 16px inner pad.
RAIL_Y = 40          # bottom of the status rail
RULE_Y = 150         # full-width hairline under the wordmark
WM_BASE = 126        # wordmark baseline
WM_SIZE = 64

SCR_X, SCR_Y = 104, 166
SCR_W, SCR_H = 1120, 186
SCR_R, SCR_B = SCR_X + SCR_W, SCR_Y + SCR_H      # 1224, 352
PAD = 16

PX0, PX1 = SCR_X + PAD, SCR_R - PAD              # 120 .. 1208  (V axis)
IY0, IYTOP = SCR_B - PAD, SCR_Y + PAD            # 336 .. 182   (I axis)

V_DIVS = 12          # (1.00 - 0.40) V / 12 = 0.05 V per division
V_LABEL_EVERY = 2    # label every 0.1 V
LOG_MINOR = (2, 5)   # log paper sub-decade lines, the classic 2-and-5 pair

SWEEP_CYCLE = 8.0    # seconds: one full sweep plus a flyback pause
SWEEP_ACTIVE = 0.82  # fraction of the cycle spent travelling


def build(theme):
    p = DARK if theme == "dark" else LIGHT
    dark = theme == "dark"

    pts_fit = ivcurve.sample("fit")
    pts_raw = ivcurve.sample("raw")
    i_floor, i_ceil, n_decades = ivcurve.decades()
    l_floor, l_ceil = math.log10(i_floor), math.log10(i_ceil)

    def vx(v):
        return PX0 + (v - ivcurve.V_MIN) / (ivcurve.V_MAX - ivcurve.V_MIN) * (PX1 - PX0)

    def iy(ma):
        # Log axis, deliberately unclamped at the floor. The pre-knee tail is
        # allowed to run off the bottom edge and be trimmed by the plot
        # clipPath — that is what a real instrument shows. Clamping it to the
        # axis would park it on the bottom line and imply a measurement floor
        # that is not there.
        frac = (math.log10(max(ma, 1e-12)) - l_floor) / (l_ceil - l_floor)
        return IY0 - frac * (IY0 - IYTOP)

    def path(pts):
        return "M" + "L".join("{:.1f},{:.1f}".format(vx(v), iy(ma))
                              for v, ma in pts)

    d_fit, d_raw = path(pts_fit), path(pts_raw)

    v_step_px = (PX1 - PX0) / float(V_DIVS)
    dec_px = (IY0 - IYTOP) / float(n_decades)

    out = []
    add = out.append

    add('<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
        'viewBox="0 0 {w} {h}" fill="none" role="img" '
        'aria-label="nanfeng — physics and optoelectronics, math modeling and '
        'AI agents, drawn as a semilog diode I-V sweep with a fitted model">'
        .format(w=W, h=H))

    # ── defs ────────────────────────────────────────────────────────────
    add('<defs>')
    # Blueprint ruling. Two scales, faded out at the edges by a mask so the
    # grid reads as engineering drawing rather than as a tiled texture.
    add('<pattern id="micro" width="8" height="8" patternUnits="userSpaceOnUse">'
        '<path d="M8 0V8M0 8H8" stroke="{g}" stroke-width="0.5"/></pattern>'
        .format(g=p["grid_minor"]))
    add('<pattern id="major" width="64" height="64" patternUnits="userSpaceOnUse">'
        '<path d="M64 0V64M0 64H64" stroke="{g}" stroke-width="1"/></pattern>'
        .format(g=p["grid_minor"]))
    add('<radialGradient id="vig" cx="0.5" cy="0.42" r="0.78">'
        '<stop offset="0" stop-color="#fff" stop-opacity="{v}"/>'
        '<stop offset="0.55" stop-color="#fff" stop-opacity="{h}"/>'
        '<stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>'
        .format(v=p["vig"], h=p["vig"] * 0.45))
    add('<mask id="vigMask"><rect width="{w}" height="{h}" fill="url(#vig)"/>'
        '</mask>'.format(w=W, h=H))
    add('<radialGradient id="ambient" cx="0.55" cy="0.62" r="0.5">'
        '<stop offset="0" stop-color="{a}" stop-opacity="{o}"/>'
        '<stop offset="1" stop-color="{a}" stop-opacity="0"/></radialGradient>'
        .format(a=p["accent"], o=p["ambient"]))
    add('<linearGradient id="sweepBand" x1="0" y1="0" x2="1" y2="0">'
        '<stop offset="0" stop-color="{a}" stop-opacity="0"/>'
        '<stop offset="0.5" stop-color="{a}" stop-opacity="0.22"/>'
        '<stop offset="1" stop-color="{a}" stop-opacity="0"/></linearGradient>'
        .format(a=p["accent"]))
    add('<clipPath id="screen"><rect x="{x}" y="{y}" width="{w}" height="{h}" '
        'rx="3"/></clipPath>'.format(x=SCR_X, y=SCR_Y, w=SCR_W, h=SCR_H))
    add('<clipPath id="plot"><rect x="{x}" y="{y}" width="{w}" height="{h}"/>'
        '</clipPath>'.format(x=PX0, y=IYTOP, w=PX1 - PX0, h=IY0 - IYTOP))
    if dark:
        add('<filter id="glow" x="-10%" y="-10%" width="120%" height="120%">'
            '<feGaussianBlur stdDeviation="2.4" result="b"/>'
            '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/>'
            '</feMerge></filter>')
    add('</defs>')

    # ── backdrop ────────────────────────────────────────────────────────
    add('<rect width="{w}" height="{h}" fill="{bg}"/>'.format(w=W, h=H, bg=p["bg"]))
    add('<g mask="url(#vigMask)">'
        '<rect width="{w}" height="{h}" fill="url(#micro)"/>'
        '<rect width="{w}" height="{h}" fill="url(#major)"/></g>'.format(w=W, h=H))
    add('<rect width="{w}" height="{h}" fill="url(#ambient)"/>'.format(w=W, h=H))

    # ── status rail ─────────────────────────────────────────────────────
    add('<g font-family=\'{f}\' font-size="11.5" font-weight="600" '
        'letter-spacing="1.6">'.format(f=MONO))
    add('<rect x="56" y="14" width="2.5" height="12" fill="{a}"/>'.format(a=p["accent"]))
    add('<text x="69" y="25.5" fill="{a}">SYS.01</text>'.format(a=p["accent"]))
    add('<text x="136" y="25.5" fill="{m}">nanfeng@github</text>'.format(m=p["mute"]))
    add('<text x="1206" y="25.5" fill="{m}" text-anchor="end">'
        '0.05 V/div&#160;&#160;&#183;&#160;&#160;1 decade/div</text>'
        .format(m=p["mute"]))
    add('</g>')
    add('<line x1="56" y1="{y}" x2="1224" y2="{y}" stroke="{l}" stroke-width="1"/>'
        .format(y=RAIL_Y + 0.5, l=p["line"]))
    add('<circle cx="1222" cy="22" r="3.5" fill="{a}">'
        '<animate attributeName="opacity" values="1;1;0.15;0.15;1" '
        'keyTimes="0;0.42;0.5;0.92;1" dur="1.6s" repeatCount="indefinite"/>'
        '</circle>'.format(a=p["accent"]))

    # ── wordmark + identity ─────────────────────────────────────────────
    add('<text font-family=\'{f}\' font-size="{s}" font-weight="700" '
        'letter-spacing="11.5" x="56" y="{y}" fill="{t}">NANFENG</text>'
        .format(f=MONO, s=WM_SIZE, y=WM_BASE, t=p["text"]))
    add('<g font-family=\'{f}\' text-anchor="end">'.format(f=MONO))
    add('<text font-size="15" x="1224" y="96" fill="{d}">'
        'physics &#183; optoelectronics</text>'.format(d=p["dim"]))
    add('<text font-size="20" font-weight="600" x="1224" y="126" fill="{t}">'
        '<tspan fill="{a}">math modeling</tspan>'
        '<tspan fill="{m}">&#160;&#215;&#160;</tspan>'
        '<tspan fill="{a}">ai agents</tspan></text>'
        .format(t=p["text"], a=p["accent"], m=p["mute"]))
    add('</g>')
    add('<line x1="56" y1="{y}" x2="1224" y2="{y}" stroke="{l}" stroke-width="1"/>'
        .format(y=RULE_Y + 0.5, l=p["line"]))

    # ── screen ──────────────────────────────────────────────────────────
    add('<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="3" fill="{well}" '
        'stroke="{l}" stroke-width="1"/>'
        .format(x=SCR_X + 0.5, y=SCR_Y + 0.5, w=SCR_W - 1, h=SCR_H - 1,
                well=p["well"], l=p["line"]))
    add('<g clip-path="url(#screen)">')

    # graticule — linear volts across, log decades up. The decade lines and
    # the volt rulings carry the `grid` tone; only the 2/5 sub-decade lines
    # below drop to `grid_minor`, so the log paper reads as log paper.
    add('<g stroke="{g}" stroke-width="1">'.format(g=p["grid"]))
    for i in range(1, V_DIVS):
        x = PX0 + i * v_step_px
        add('<line x1="{:.1f}" y1="{y0}" x2="{:.1f}" y2="{y1}"/>'
            .format(x, x, y0=IYTOP, y1=IY0))
    for d in range(1, n_decades):
        y = IY0 - d * dec_px
        add('<line x1="{x0}" y1="{:.1f}" x2="{x1}" y2="{:.1f}"/>'
            .format(y, y, x0=PX0, x1=PX1))
    add('</g>')
    # sub-decade 2/5 lines, fainter — the log-paper look
    add('<g stroke="{g}" stroke-width="1">'.format(g=p["grid_minor"]))
    for d in range(n_decades):
        for sub in LOG_MINOR:
            ma = i_floor * (10.0 ** d) * sub
            if ma >= i_ceil:
                continue
            y = iy(ma)
            add('<line x1="{x0}" y1="{:.1f}" x2="{x1}" y2="{:.1f}"/>'
                .format(y, y, x0=PX0, x1=PX1))
    add('</g>')
    # the two zero axes, a notch brighter than the ruling
    add('<line x1="{x}" y1="{y0}" x2="{x}" y2="{y1}" stroke="{l}" stroke-width="1"/>'
        .format(x=PX0 + 0.5, y0=IYTOP, y1=IY0, l=p["line"]))
    add('<line x1="{x0}" y1="{y}" x2="{x1}" y2="{y}" stroke="{l}" stroke-width="1"/>'
        .format(x0=PX0, x1=PX1, y=IY0 + 0.5, l=p["line"]))

    # ── traces ──────────────────────────────────────────────────────────
    add('<g clip-path="url(#plot)">')
    # measurement: polyline plus sample dots, because a measured sweep is a
    # set of points, not a curve — the dots are what says "data"
    add('<path d="{d}" fill="none" stroke="{c}" stroke-width="1.3" '
        'stroke-opacity="0.75" stroke-linejoin="round"/>'
        .format(d=d_raw, c=p["accent2"]))
    add('<g fill="{c}" fill-opacity="0.9">'.format(c=p["accent2"]))
    for v, ma in pts_raw:
        add('<circle cx="{:.1f}" cy="{:.1f}" r="1.5"/>'.format(vx(v), iy(ma)))
    add('</g>')
    # model: single smooth line, the thing the eye should follow
    glow = ' filter="url(#glow)"' if dark else ''
    add('<path d="{d}" fill="none" stroke="{c}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round"{g}/>'
        .format(d=d_fit, c=p["accent"], g=glow))
    add('</g>')

    # legend + fitted parameters, parked in the dead space above the pre-knee
    # tail of the curve
    add('<g font-family=\'{f}\' font-size="11.5" letter-spacing="0.6">'.format(f=MONO))
    add('<circle cx="128" cy="192" r="3.5" fill="{a}"/>'.format(a=p["accent"]))
    add('<text x="142" y="197" fill="{d}">CH2&#160;&#160;single-diode fit</text>'
        .format(d=p["dim"]))
    add('<circle cx="128" cy="214" r="3.5" fill="{a}"/>'.format(a=p["accent2"]))
    add('<text x="142" y="219" fill="{d}">CH1&#160;&#160;measured</text>'
        .format(d=p["dim"]))
    add('<text x="128" y="246" fill="{m}" font-size="10" letter-spacing="0.9">'
        'fit:&#160;&#160;Is = {isat:.0f} nA&#160;&#160;&#160;n = {n:.2f}'
        '&#160;&#160;&#160;Rs = {rs:.1f} &#937;</text>'
        .format(m=p["mute"], isat=ivcurve.FIT["is1"] * 1e9, n=ivcurve.FIT["n1"],
                rs=ivcurve.FIT["rs"]))
    add('</g>')

    # ── sweep ───────────────────────────────────────────────────────────
    # Brightens what is already drawn; the traces above are full-opacity, so
    # every frame is complete whether or not the band is on screen.
    band_w = 220.0
    add('<rect x="{:.1f}" y="{y}" width="{bw}" height="{h}" fill="url(#sweepBand)">'
        '<animate attributeName="x" dur="{c}s" repeatCount="indefinite" '
        'keyTimes="0;{k};1" values="{v0};{v1};{v1}"/></rect>'
        .format(PX0 - band_w, y=SCR_Y, bw=band_w, h=SCR_H, c=SWEEP_CYCLE,
                k=SWEEP_ACTIVE, v0=PX0 - band_w, v1=PX1))
    fade = min(0.99, SWEEP_ACTIVE + 0.03)
    add('<line y1="{y0}" y2="{y1}" stroke="{a}" stroke-width="1" '
        'stroke-opacity="0.7">'
        '<animate attributeName="x1" dur="{c}s" repeatCount="indefinite" '
        'keyTimes="0;{k};1" values="{v0};{v1};{v1}"/>'
        '<animate attributeName="x2" dur="{c}s" repeatCount="indefinite" '
        'keyTimes="0;{k};1" values="{v0};{v1};{v1}"/>'
        '<animate attributeName="opacity" dur="{c}s" repeatCount="indefinite" '
        'keyTimes="0;{k};{f};1" values="0.75;0.75;0;0"/></line>'
        .format(y0=IYTOP, y1=IY0, a=p["accent"], c=SWEEP_CYCLE, k=SWEEP_ACTIVE,
                v0=PX0, v1=PX1, f=fade))

    # The dot rides keyframes sampled from the model itself rather than
    # animateMotion: animateMotion advances by arc length, so on a curve this
    # steep it would drift out of sync with the cursor line.
    n_dot = 33
    kt, cxs, cys = [], [], []
    for i in range(n_dot):
        t = i / float(n_dot - 1)
        kt.append("{:.4g}".format(t * SWEEP_ACTIVE))
        idx = int(round(t * (len(pts_fit) - 1)))
        cxs.append("{:.1f}".format(vx(pts_fit[idx][0])))
        cys.append("{:.1f}".format(iy(pts_fit[idx][1])))
    add('<circle r="4" fill="{a}">'.format(a=p["accent"]))
    add('<animate attributeName="cx" dur="{c}s" repeatCount="indefinite" '
        'keyTimes="{k}" values="{v}"/>'
        .format(c=SWEEP_CYCLE, k=";".join(kt), v=";".join(cxs)))
    add('<animate attributeName="cy" dur="{c}s" repeatCount="indefinite" '
        'keyTimes="{k}" values="{v}"/>'
        .format(c=SWEEP_CYCLE, k=";".join(kt), v=";".join(cys)))
    add('<animate attributeName="opacity" dur="{c}s" repeatCount="indefinite" '
        'keyTimes="0;{k};{f};1" values="0.95;0.95;0;0"/>'
        .format(c=SWEEP_CYCLE, k=SWEEP_ACTIVE, f=fade))
    add('</circle>')

    add('</g>')  # /screen clip

    # ── axes ────────────────────────────────────────────────────────────
    add('<g font-family=\'{f}\' font-size="10" font-weight="500" '
        'letter-spacing="0.8">'.format(f=MONO))
    add('<text x="96" y="170" fill="{d}" text-anchor="end">I / mA &#183; log</text>'
        .format(d=p["dim"]))
    for i, label in enumerate(ivcurve.decade_labels()):
        y = IY0 - i * dec_px
        add('<text x="96" y="{:.1f}" fill="{m}" text-anchor="end">{}</text>'
            .format(y + 3.5, label, m=p["mute"]))
    add('<text x="56" y="378" fill="{d}">V &#8594;</text>'.format(d=p["dim"]))
    span = ivcurve.V_MAX - ivcurve.V_MIN
    for i in range(0, V_DIVS + 1, V_LABEL_EVERY):
        x = PX0 + i * v_step_px
        add('<text x="{:.1f}" y="378" fill="{m}" text-anchor="middle">'
            '{:.1f}</text>'.format(x, ivcurve.V_MIN + span * i / V_DIVS, m=p["mute"]))
    add('</g>')

    add('</svg>')
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--theme", choices=("dark", "light", "both"), default="both")
    ap.add_argument("--out", default=None, help="output directory")
    ap.add_argument("--palette", action="store_true", help="dump colours and exit")
    args = ap.parse_args()

    if args.palette:
        for name, table in (("dark", DARK), ("light", LIGHT)):
            print(name, " ".join("{}={}".format(k, v) for k, v in sorted(table.items())))
        return

    here = os.path.dirname(os.path.abspath(__file__))
    out = args.out or os.path.join(os.path.dirname(here), "assets")
    if not os.path.isdir(out):
        os.makedirs(out)

    themes = ("dark", "light") if args.theme == "both" else (args.theme,)
    for theme in themes:
        svg = build(theme)
        path = os.path.join(out, "hero-{}.svg".format(theme))
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(svg)
        print("wrote {} ({} bytes)".format(path, len(svg)))


if __name__ == "__main__":
    main()
