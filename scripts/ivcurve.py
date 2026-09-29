#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ivcurve.py — the signal on the hero banner.

The banner plots a forward-biased diode I-V sweep on a LOGARITHMIC current
axis: the amber trace is a measurement, the cyan trace is the model fitted to
it. That pairing is the point of the profile — physics background, math
modeling, and "model vs. measurement" is what the person actually works on. So
the curve is not decorative squiggle; it is a solved device model.

Why semilog, and why two diodes
-------------------------------
On a linear axis a diode is a flat line for 60% of the plot and then a wall.
Half the canvas would be dead space, and a single-diode model sits exactly on
top of the measurement, so "measured vs. fitted" — the whole story — would be
invisible.

Semilog fixes both. It is also the standard way diodes are actually
characterised, because an exponential becomes a straight line. Which then
exposes the real physics worth drawing:

    A real diode conducts by two mechanisms. Diffusion dominates at high
    current (ideality n1 ~ 1.8); recombination dominates at low current
    (n2 ~ 2.4, i.e. a shallower slope). A single-diode fit only captures the
    diffusion term, so it tracks the measurement at high current and
    UNDER-predicts at low current. On a semilog plot that shows up as the
    classic two-slope kink: two lines that converge to the right and split
    into a wedge to the left.

That wedge is a genuine feature of the data, which is why it reads clearly —
unlike instrument noise, which on a log axis is invisible unless it is
implausibly large. Noise is therefore multiplicative (~10%), which is also
what real relative measurement error looks like.

Both curves need I on both sides of the equation once a series resistance is
included, so each sample is solved by bisection:

    I = Is1*(exp((V - I*Rs)/(n1*Vt)) - 1) + Is2*(exp((V - I*Rs)/(n2*Vt)) - 1)

f(I) is monotonically decreasing in I (more current -> less junction voltage
-> less current), so bisection is safe and 200 iterations is far past float
convergence. Seeded, so the banner is byte-identical on every rebuild.
"""

import math
import random

VT = 0.025852      # thermal voltage at 300 K, V

# ── the device: a real two-mechanism diode ──────────────────────────────
# Is1=1e-9 is a leaky power diode, not a small-signal one. A realistic 1e-12
# would put the whole curve below the bottom of the axis.
DEVICE = {
    "is1": 1.0e-9,   # diffusion saturation current, A
    "n1": 1.8,       # diffusion ideality
    "is2": 4.0e-8,   # recombination saturation current, A
    "n2": 2.4,       # recombination ideality — shallower, so it wins at low I
    "rs": 2.5,       # series resistance, ohm
}

# ── the model: a single-diode fit to that device ────────────────────────
# Fitted the way anyone would fit it — against the high-current straight line.
# It never sees the recombination term, which is exactly the point.
FIT = {
    "is1": 1.0e-9,
    "n1": 1.8,
    "rs": 2.5,
}

V_MIN, V_MAX = 0.40, 1.00     # sweep range, volts

# Axis decades, in mA. The measurement enters from the bottom around 0.48 V and
# tops out near 70 mA at the right edge, so three decades is what fills the
# screen — a fourth would strand the top third of the plot empty.
I_FLOOR_MA = 0.1
I_CEIL_MA = 100.0

NOISE_REL = 0.06              # relative measurement scatter


def _solve(v, is1, n1, is2=None, n2=None, rs=0.0):
    """Solve the one- or two-diode equation for I at a given V, by bisection."""
    if v <= 0.0:
        return 0.0

    if is2 is None:
        def excess(i):
            return is1 * (math.exp((v - i * rs) / (n1 * VT)) - 1.0) - i
    else:
        def excess(i):
            u = v - i * rs
            return (is1 * (math.exp(u / (n1 * VT)) - 1.0)
                    + is2 * (math.exp(u / (n2 * VT)) - 1.0) - i)

    lo, hi = 0.0, 10.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if excess(mid) > 0.0:      # this guess draws too little current
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def measured(v):
    """What the instrument recorded: the two-diode device."""
    return _solve(v, DEVICE["is1"], DEVICE["n1"],
                  DEVICE["is2"], DEVICE["n2"], DEVICE["rs"])


def model(v):
    """What the single-diode fit predicts."""
    return _solve(v, FIT["is1"], FIT["n1"], rs=FIT["rs"])


def sample(kind, seed=20260929):
    """Return a list of (volts, milliamps).

    "fit" is densely sampled so it draws as a smooth curve; "raw" is sparsely
    sampled so the individual measurement points stay visible as dots.
    """
    if kind == "fit":
        count, noisy = 200, False
    elif kind == "raw":
        count, noisy = 64, True
    else:
        raise ValueError("kind must be 'fit' or 'raw'")

    rng = random.Random(seed)
    pts = []
    for i in range(count):
        v = V_MIN + (V_MAX - V_MIN) * i / float(count - 1)
        if noisy:
            # Multiplicative: on a log axis an absolute noise floor would be
            # both invisible up top and illegal down bottom (log of a
            # non-positive current).
            i_amp = measured(v) * (1.0 + rng.gauss(0.0, NOISE_REL))
            i_amp = max(i_amp, 1e-12)
        else:
            i_amp = model(v)
        pts.append((v, i_amp * 1000.0))
    return pts


def decades():
    """(floor, ceil, count) of the log axis, in mA."""
    lo = int(round(math.log10(I_FLOOR_MA)))
    hi = int(round(math.log10(I_CEIL_MA)))
    return I_FLOOR_MA, I_CEIL_MA, hi - lo


def decade_labels():
    """Human-readable decade labels in mA: 0.1 1 10 100 1k."""
    _, _, n = decades()
    out = []
    for k in range(n + 1):
        val = I_FLOOR_MA * (10.0 ** k)
        out.append("{:g}k".format(val / 1000.0) if val >= 1000
                   else "{:g}".format(val))
    return out


def ascii_plot(kind="raw", width=64, height=22):
    """Crude terminal plot on the real log scale, for eyeballing without a browser."""
    pts = sample(kind)
    lo, hi, _ = decades()
    llo, lhi = math.log10(lo), math.log10(hi)
    grid = [[" "] * width for _ in range(height)]
    for v, ma in pts:
        if ma <= 0:
            continue
        x = int(round((v - V_MIN) / (V_MAX - V_MIN) * (width - 1)))
        frac = (math.log10(ma) - llo) / (lhi - llo)
        y = height - 1 - int(round(frac * (height - 1)))
        if 0 <= y < height and 0 <= x < width:
            grid[y][x] = "#"
    print("{} — semilog, {}..{} mA over {:.2f}..{:.2f} V".format(
        kind, lo, hi, V_MIN, V_MAX))
    for row in grid:
        print("  |" + "".join(row))
    print("  +" + "-" * width)


if __name__ == "__main__":
    for kind in ("fit", "raw"):
        pts = sample(kind)
        ascii_plot(kind)
        print("  points={}  I({:.2f}V)={:.3g} mA  I({:.2f}V)={:.3g} mA".format(
            len(pts), V_MIN, pts[0][1], V_MAX, pts[-1][1]))

    # The wedge is the whole story — report it so a regression is obvious.
    print("\nmeasured vs model (the wedge should shrink as V rises):")
    for v in (0.45, 0.55, 0.65, 0.75, 0.85, 0.95):
        m, f = measured(v) * 1000.0, model(v) * 1000.0
        gap = math.log10(m / f) if f > 0 else float("inf")
        print("  V={:.2f}  measured={:9.4g} mA  model={:9.4g} mA   "
              "gap={:.2f} decades".format(v, m, f, gap))
    print("\naxis decades: {}".format(" ".join(decade_labels())))
