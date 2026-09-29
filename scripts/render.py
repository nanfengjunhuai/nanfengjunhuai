#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render.py — pull real GitHub stats and draw them as SVG.

Why hand-rolled instead of github-readme-stats / capsule-render?
Those widgets live on *.vercel.app, which is unreachable from mainland
China, and they rate-limit constantly — which shows up as a broken image.
Everything here is stdlib-only and the output is committed to this repo,
so the cards can never break and the palette matches the profile exactly.

Four deliberate choices:
  * Language split comes from /repos/:owner/:repo/languages (GitHub's own
    linguist analysis), not repo size. Repo size counts package-lock.json
    and friends, which would report a React Native app as 99% JavaScript.
  * Star/follower tiles only appear once they are non-zero. A new account
    showing "0 stars / 0 followers" reads worse than showing nothing, and
    they will surface on their own the day they stop being zero.
  * No boxes around the tiles, and the numbers are NOT accented. Four
    identical rounded rectangles with a bright number in each is the shape
    everyone recognises as a template, and colouring every value reads as
    shouting. Hairline separators and a neutral value tone instead; the
    accent survives as one small tick per column.
  * Both themes are emitted from the same geometry but separate palettes.
    A card is not "dark mode with inverted colours" — see DESIGN.md §2.

Usage:
    python scripts/render.py                 # unauthenticated (60 req/h)
    GITHUB_TOKEN=ghp_xxx python scripts/render.py

Writes: assets/stats-{dark,light}.svg, assets/langs-{dark,light}.svg
"""

import datetime
import json
import os
import sys
import time
import urllib.error
import urllib.request
from xml.sax.saxutils import escape

USER = os.environ.get("PROFILE_USER", "nanfengjunhuai")
TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
API = "https://api.github.com"

# ── palettes (DESIGN.md §2) ─────────────────────────────────────────────
PALETTES = {
    "dark": {
        "bg": "#0B0E14", "well": "#080B10",
        "line": "#1C2430", "grid": "#131A24",
        "text": "#E6EDF3", "dim": "#8B96A5", "mute": "#5A6675",
        "accent": "#22D3EE",
    },
    "light": {
        "bg": "#FCFCFD", "well": "#FFFFFF",
        "line": "#DCE1E8", "grid": "#F0F3F7",
        "text": "#0B0E14", "dim": "#4A5561", "mute": "#6B7684",
        "accent": "#0E7490",
    },
}

# Monochrome ramp for the language bar. Linguist's brand colours (Python blue
# next to JavaScript yellow next to TypeScript blue) turn the card into a
# paint chart and break the instrument language, so separation is carried by
# lightness alone and the legend names each language anyway.
SEG_OPACITY = [1.0, 0.78, 0.62, 0.50, 0.40, 0.32]

FONT = ('ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, '
        '"Liberation Mono", "DejaVu Sans Mono", monospace')

CARD_W = 880
RAIL_H = 34


def _request(url, headers, data=None, attempts=4):
    """GET/POST with retries. Returns parsed JSON, or None once it gives up.

    The retry is not defensive padding. This profile is rendered from a
    mainland-China network, where TLS handshakes to api.github.com are reset
    at random — measured at roughly one failure in six — and a single reset
    used to blank out the whole card. GitHub Actions sees the same thing
    occasionally, so the retry pays off there too.
    """
    last = None
    for attempt in range(attempts):
        req = urllib.request.Request(url, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=25) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last = exc
            # 4xx other than rate limiting will not fix themselves
            if exc.code < 500 and exc.code != 429:
                break
        except Exception as exc:  # noqa: BLE001 - transient network
            last = exc
        if attempt < attempts - 1:
            time.sleep(0.8 * (2 ** attempt))
    sys.stderr.write("  ! {} -> {}\n".format(url, last))
    return None


def api(path):
    """GET a GitHub API path. Returns parsed JSON, or None on any failure."""
    url = path if path.startswith("http") else API + path
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": USER + "-profile-readme",
    }
    if TOKEN:
        headers["Authorization"] = "Bearer " + TOKEN
    return _request(url, headers)


def graphql(query):
    """POST a GraphQL query. Needs a token; returns None without one."""
    if not TOKEN:
        return None
    return _request(
        API + "/graphql",
        {
            "Authorization": "Bearer " + TOKEN,
            "Content-Type": "application/json",
            "User-Agent": USER + "-profile-readme",
        },
        data=json.dumps({"query": query}).encode("utf-8"),
    )


# ── data gathering ──────────────────────────────────────────────────────

def fetch_languages(repos):
    """Real byte counts per language, via linguist. Skips generated files."""
    totals = {}
    for repo in repos[:40]:
        stats = api("/repos/{}/{}/languages".format(USER, repo["name"]))
        if not isinstance(stats, dict):
            continue
        for name, size in stats.items():
            totals[name] = totals.get(name, 0) + size
    return totals


def fetch_contributions():
    """Contributions in the last year. GraphQL first, event log as fallback."""
    data = graphql("""
      query {
        user(login: "%s") {
          contributionsCollection {
            contributionCalendar { totalContributions }
          }
        }
      }""" % USER)
    if data:
        try:
            cal = data["data"]["user"]["contributionsCollection"]
            return cal["contributionCalendar"]["totalContributions"]
        except (KeyError, TypeError):
            pass

    events = api("/users/{}/events/public?per_page=100".format(USER))
    if not isinstance(events, list):
        return None
    count = 0
    for ev in events:
        if ev.get("type") == "PushEvent":
            count += len(ev.get("payload", {}).get("commits", []))
    return count


# ── SVG helpers ─────────────────────────────────────────────────────────

def panel(width, height, sys_id, title, note, body, p):
    """The instrument frame: a status rail, a hairline, then the readout."""
    return """<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" fill="none" role="img" aria-label="{label}">
  <rect width="{w}" height="{h}" fill="{bg}"/>
  <rect x="0.5" y="0.5" width="{wo}" height="{ho}" fill="none" stroke="{line}" stroke-width="1"/>
  <g font-family='{font}' font-size="11.5" font-weight="600" letter-spacing="1.6">
    <rect x="24" y="11" width="2.5" height="12" fill="{accent}"/>
    <text x="37" y="22" fill="{accent}">{sys_id}</text>
    <text x="104" y="22" fill="{mute}">{title}</text>
    <text x="{note_x}" y="22" fill="{mute}" text-anchor="end">{note}</text>
  </g>
  <line x1="24" y1="{rail}" x2="{rail_x}" y2="{rail}" stroke="{line}" stroke-width="1"/>
{body}
</svg>
""".format(w=width, h=height, wo=width - 1, ho=height - 1, label=escape(title),
           bg=p["bg"], line=p["line"], accent=p["accent"], mute=p["mute"],
           font=FONT, sys_id=sys_id, title=escape(title),
           note=escape(note), note_x=width - 24, rail=RAIL_H + 0.5,
           rail_x=width - 24, body=body)


def readout(x, label, value, sub, p, show_tick):
    """One column of the readout: label, value, note. No box.

    The value carries `text`, not `accent`. Accenting all four numbers was the
    thing that made the old card shout; the accent survives as a 1px tick so
    the columns still read as instrument channels.

    The tick sits at the column boundary and the text is indented past it —
    drawing both at the same x ran the rule straight through the first letter
    of every label.
    """
    tick = ('<rect x="{:.1f}" y="60" width="1" height="76" fill="{a}" '
            'fill-opacity="0.55"/>'.format(x, a=p["accent"])) if show_tick else ""
    tx = x + 12
    return """
  <g>
    {tick}
    <text font-family='{font}' font-size="10.5" font-weight="600" letter-spacing="1.5" x="{tx:.1f}" y="76" fill="{mute}">{label}</text>
    <text font-family='{font}' font-size="30" font-weight="700" x="{tx:.1f}" y="114" fill="{text}">{value}</text>
    <text font-family='{font}' font-size="10.5" x="{tx:.1f}" y="134" fill="{mute}">{sub}</text>
  </g>""".format(font=FONT, tick=tick, tx=tx, label=escape(label),
                 value=escape(value), sub=escape(sub),
                 mute=p["mute"], text=p["text"])


def human(n):
    if n >= 1000:
        return "{:.1f}k".format(n / 1000.0).replace(".0k", "k")
    return str(n)


def truncate(text, limit):
    return text if len(text) <= limit else text[:limit - 1] + "…"


# ── card 1: stats ───────────────────────────────────────────────────────

def build_stats(user, repos, langs, contributions, p, theme):
    repos = repos or []
    user = user or {}
    stars = sum(r.get("stargazers_count", 0) for r in repos)
    forks = sum(r.get("forks_count", 0) for r in repos)
    followers = user.get("followers", 0) or 0
    following = user.get("following", 0) or 0

    now = datetime.datetime.now(datetime.timezone.utc)
    created = (user.get("created_at") or "")[:10]
    since = created.replace("-", "/")[:7] if created else "—"
    days = "—"
    if created:
        try:
            born = datetime.datetime.strptime(created, "%Y-%m-%d").replace(
                tzinfo=datetime.timezone.utc)
            days = str((now - born).days)
        except ValueError:
            pass

    last_push, last_repo = "—", "no pushes yet"
    if repos:
        latest = max(repos, key=lambda r: r.get("pushed_at") or "")
        last_repo = truncate(latest.get("name") or "—", 18)
        stamp = (latest.get("pushed_at") or "")[:10]
        if stamp:
            try:
                when = datetime.datetime.strptime(stamp, "%Y-%m-%d").replace(
                    tzinfo=datetime.timezone.utc)
                delta = (now - when).days
                if delta <= 0:
                    last_push = "today"
                elif delta == 1:
                    last_push = "1d ago"
                elif delta < 30:
                    last_push = "{}d ago".format(delta)
                elif delta < 365:
                    last_push = "{}mo ago".format(delta // 30)
                else:
                    last_push = "{}y ago".format(delta // 365)
            except ValueError:
                pass

    top_name, top_pct = "—", 0.0
    if langs:
        total = float(sum(langs.values()))
        top_name = max(langs.items(), key=lambda kv: kv[1])[0]
        top_pct = 100.0 * langs[top_name] / total

    # Ordered by how much each column earns its space. Every column that can
    # read zero is conditional, so a new account never advertises a zero — and
    # each one surfaces on its own the day it stops being zero.
    candidates = [
        ("PUBLIC REPOS", str(len(repos)),
         "{} languages".format(len(langs)) if langs else "no code yet"),
    ]
    if contributions:
        candidates.append(("CONTRIBUTIONS", human(contributions), "last 12 months"))
    if stars:
        candidates.append(("TOTAL STARS", human(stars), "{} forks".format(forks)))
    if followers:
        candidates.append(("FOLLOWERS", str(followers),
                           "following {}".format(following)))
    candidates += [
        ("TOP LANGUAGE", truncate(top_name, 12),
         "{:.0f}% of tracked code".format(top_pct)),
        ("DAYS BUILDING", days, "since {}".format(since)),
        ("LAST PUSH", last_push, last_repo),
    ]
    cells = candidates[:4]

    # Columns stretch to fill the card, so 3 or 4 both look deliberate. Text
    # sits 0px from its column's left edge; the tick marks the boundary.
    x0 = 24
    span = CARD_W - x0 * 2
    cw = span / float(len(cells))
    body = ""
    for i, (label, value, sub) in enumerate(cells):
        body += readout(int(round(x0 + i * cw)), label, value, sub, p,
                        show_tick=(i > 0))

    body += ('\n  <text font-family=\'{f}\' font-size="10.5" x="24" y="162" '
             'fill="{m}">rendered from the GitHub API &#183; refreshed daily '
             'by scripts/render.py</text>'.format(f=FONT, m=p["mute"]))

    return panel(CARD_W, 182, "SYS.03", "~/stats", "live", body, p)


# ── card 2: language distribution ───────────────────────────────────────

def build_langs(langs, p, theme):
    if not langs:
        body = ('\n  <text font-family=\'{f}\' font-size="10.5" x="24" y="80" '
                'fill="{m}">no language data yet</text>'.format(f=FONT, m=p["mute"]))
        return panel(CARD_W, 108, "SYS.04", "~/top-languages", "linguist", body, p)

    total = float(sum(langs.values()))
    ranked = sorted(langs.items(), key=lambda kv: kv[1], reverse=True)[:6]

    # Fold the long tail so the bar stays readable and still sums to 100%.
    tail = total - sum(v for _, v in ranked)
    if len(langs) > 6 and tail > 0:
        ranked.append(("Other", tail))

    bar_x, bar_y, bar_w, bar_h = 24, 62, CARD_W - 48, 22
    segs = []
    cursor = float(bar_x)
    for i, (name, size) in enumerate(ranked):
        seg = bar_w * size / total
        if i == len(ranked) - 1:
            seg = bar_x + bar_w - cursor          # absorb rounding, end flush
        segs.append((cursor, max(seg, 0.5), SEG_OPACITY[i % len(SEG_OPACITY)]))
        cursor += seg

    body = '\n  <g>'
    for i, (sx, sw, opacity) in enumerate(segs):
        body += ('<rect x="{:.2f}" y="{}" width="{:.2f}" height="{}" '
                 'fill="{}" fill-opacity="{}"/>'
                 .format(sx, bar_y, sw, bar_h, p["accent"], opacity))
        # A 1.5px gap between two sub-1% slivers turns the tail of the bar into
        # visual noise, so only separate segments that both have room to spare.
        if i > 0 and sw >= 4 and segs[i - 1][1] >= 4:
            body += ('<rect x="{:.2f}" y="{}" width="1.5" height="{}" fill="{}"/>'
                     .format(sx - 0.75, bar_y, bar_h, p["well"]))
    body += '</g>'
    body += ('\n  <rect x="{x}" y="{y}" width="{w}" height="{h}" fill="none" '
             'stroke="{l}" stroke-width="1"/>'
             .format(x=bar_x, y=bar_y, w=bar_w, h=bar_h, l=p["line"]))

    # legend: three columns, swatch + name + share. The share is right-aligned
    # against a fixed label width rather than the column edge — anchoring it to
    # the column edge left a wide dead gap that made the number look orphaned
    # from the language it belonged to.
    lx, ly, col_w = 24, 112, (CARD_W - 48) / 3
    label_w = 186
    for i, (name, size) in enumerate(ranked):
        cx = lx + (i % 3) * col_w
        cy = ly + (i // 3) * 26
        body += ("""<g font-family='{f}'>
    <rect x="{cx:.1f}" y="{sy:.1f}" width="9" height="9" fill="{a}" fill-opacity="{o}"/>
    <text font-size="11.5" x="{tx:.1f}" y="{cy}" fill="{t}">{n}</text>
    <text font-size="11.5" x="{px:.1f}" y="{cy}" fill="{m}" text-anchor="end">{pct:.1f}%</text>
  </g>""").format(f=FONT, cx=cx, sy=cy - 8.5, a=p["accent"],
                  o=SEG_OPACITY[i % len(SEG_OPACITY)], tx=cx + 17, cy=cy,
                  px=cx + label_w, t=p["text"], m=p["mute"],
                  n=escape(truncate(name, 20)), pct=100.0 * size / total)

    rows = (len(ranked) + 2) // 3
    height = int(ly + (rows - 1) * 26 + 24)
    note = "{} tracked".format(len(langs))
    return panel(CARD_W, height, "SYS.04", "~/top-languages", note, body, p)


# ── main ────────────────────────────────────────────────────────────────

def main():
    here = os.path.dirname(os.path.abspath(__file__))
    out = os.path.join(os.path.dirname(here), "assets")
    if not os.path.isdir(out):
        os.makedirs(out)

    print("fetching {} ...".format(USER))
    user = api("/users/" + USER)
    repos = api("/users/{}/repos?per_page=100&sort=updated".format(USER))
    repos = [r for r in repos if not r.get("fork")] if isinstance(repos, list) else []

    print("  analysed {} public repos".format(len(repos)))
    langs = fetch_languages(repos)
    contributions = fetch_contributions()
    print("  languages: {}".format(", ".join(
        "{}={}".format(k, v) for k, v in sorted(langs.items(),
                                                key=lambda kv: -kv[1])[:5]) or "none"))
    print("  contributions: {}".format(contributions))

    written = []
    for theme, p in PALETTES.items():
        written.append(("stats-{}.svg".format(theme),
                        build_stats(user, repos, langs, contributions, p, theme)))
        written.append(("langs-{}.svg".format(theme),
                        build_langs(langs, p, theme)))

    for filename, svg in written:
        path = os.path.join(out, filename)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(svg)
        print("  wrote {} ({} bytes)".format(path, len(svg)))

    print("done")


if __name__ == "__main__":
    main()
