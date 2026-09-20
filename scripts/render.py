#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render.py — pull real GitHub stats and draw them as SVG.

Why hand-rolled instead of github-readme-stats / capsule-render?
Those widgets live on *.vercel.app, which is unreachable from mainland
China, and they rate-limit constantly — which shows up as a broken image.
Everything here is stdlib-only and the output is committed to this repo,
so the cards can never break and the palette matches the profile exactly.

Two deliberate choices:
  * Language split comes from /repos/:owner/:repo/languages (GitHub's own
    linguist analysis), not repo size. Repo size counts package-lock.json
    and friends, which would report a React Native app as 99% JavaScript.
  * Star/follower tiles only appear once they are non-zero. A new account
    showing "0 stars / 0 followers" reads worse than showing nothing, and
    they will surface on their own the day they stop being zero.

Usage:
    python scripts/render.py                 # unauthenticated (60 req/h)
    GITHUB_TOKEN=ghp_xxx python scripts/render.py

Writes: assets/stats.svg, assets/langs.svg
"""

import datetime
import json
import os
import sys
import urllib.error
import urllib.request
from xml.sax.saxutils import escape

USER = os.environ.get("PROFILE_USER", "nanfengjunhuai")
TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
API = "https://api.github.com"

# ── terminal-green theme ────────────────────────────────────────────────
CANVAS = "#0D1117"
PANEL = "#161B22"
WELL = "#0B0F14"
BORDER = "#30363D"
HAIRLINE = "#21262D"
GREEN = "#3FB950"
GREEN_HI = "#7EE787"
TEXT = "#C9D1D9"
MUTED = "#8B949E"
DIM = "#484F58"

FONT = ('ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, '
        '"Liberation Mono", "DejaVu Sans Mono", monospace')

# GitHub linguist colours, so the bar reads as "real" to anyone who knows
LANG_COLORS = {
    "Python": "#3572A5", "JavaScript": "#F1E05A", "TypeScript": "#3178C6",
    "HTML": "#E34C26", "CSS": "#563D7C", "SCSS": "#C6538C", "Less": "#1D365D",
    "C": "#555555", "C++": "#F34B7D", "C#": "#178600", "Java": "#B07219",
    "Shell": "#89E051", "Batchfile": "#C1F12E", "PowerShell": "#012456",
    "Jupyter Notebook": "#DA5B0B", "Markdown": "#083FA1", "TeX": "#3D6117",
    "Go": "#00ADD8", "Rust": "#DEA584", "Ruby": "#701516", "PHP": "#4F5D95",
    "Swift": "#F05138", "Kotlin": "#A97BFF", "Dart": "#00B4AB",
    "Vue": "#41B883", "R": "#198CE7", "MATLAB": "#E16737", "Julia": "#A270BA",
    "Dockerfile": "#384D54", "Makefile": "#427819", "Lua": "#000080",
    "Objective-C": "#438EFF", "Assembly": "#6E4C13", "Perl": "#0298C3",
}
FALLBACK_COLORS = ["#3FB950", "#58A6FF", "#D29922", "#BC8CFF",
                   "#F778BA", "#39C5CF", "#FF7B72"]


def api(path):
    """GET a GitHub API path. Returns parsed JSON, or None on any failure."""
    url = path if path.startswith("http") else API + path
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": USER + "-profile-readme",
    })
    if TOKEN:
        req.add_header("Authorization", "Bearer " + TOKEN)
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 - a dead card beats a dead run
        sys.stderr.write("  ! {} -> {}\n".format(url, exc))
        return None


def graphql(query):
    """POST a GraphQL query. Needs a token; returns None without one."""
    if not TOKEN:
        return None
    req = urllib.request.Request(
        API + "/graphql",
        data=json.dumps({"query": query}).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + TOKEN,
            "Content-Type": "application/json",
            "User-Agent": USER + "-profile-readme",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write("  ! graphql -> {}\n".format(exc))
        return None


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

def card(width, height, title, body, accent=GREEN):
    """A terminal window: title bar, traffic lights, accent rail, body."""
    return """<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" fill="none" role="img" aria-label="{label}">
  <defs>
    <clipPath id="win"><rect x="0" y="0" width="{w}" height="{h}" rx="12"/></clipPath>
    <style>
      .m {{ font-family: {font}; }}
      .lbl {{ font-size: 11.5px; font-weight: 600; letter-spacing: 1.6px; }}
      .val {{ font-size: 32px; font-weight: 700; }}
      .sm  {{ font-size: 11.5px; font-weight: 400; }}
      .ttl {{ font-size: 13px; font-weight: 500; }}
    </style>
  </defs>
  <g clip-path="url(#win)">
    <rect width="{w}" height="{h}" fill="{canvas}"/>
    <rect x="1" y="1" width="{wi}" height="{hi}" rx="11" fill="{well}"/>
    <rect x="0" y="0" width="{w}" height="36" fill="{panel}"/>
    <rect x="0" y="0" width="{w}" height="2" fill="{accent}" opacity="0.85"/>
    <line x1="0" y1="36" x2="{w}" y2="36" stroke="{border}" stroke-width="1"/>
    <circle cx="22" cy="19" r="5.5" fill="#FF5F56"/>
    <circle cx="40" cy="19" r="5.5" fill="#FFBD2E"/>
    <circle cx="58" cy="19" r="5.5" fill="#27C93F"/>
    <text class="m ttl" x="{w2}" y="24" fill="{muted}" text-anchor="middle">{title}</text>
    {body}
  </g>
  <rect x="0.5" y="0.5" width="{wo}" height="{ho}" rx="12" fill="none" stroke="{border}" stroke-width="1"/>
</svg>
""".format(w=width, h=height, wi=width - 2, hi=height - 2, wo=width - 1,
           ho=height - 1, w2=width // 2, label=escape(title), font=FONT,
           canvas=CANVAS, panel=PANEL, well=WELL, border=BORDER,
           muted=MUTED, accent=accent, title=escape(title), body=body)


def tile(x, y, w, h, label, value, sub, value_fill=GREEN_HI):
    return """
  <g>
    <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" fill="{panel}" stroke="{hair}" stroke-width="1"/>
    <rect x="{x}" y="{y}" width="3" height="{h}" rx="1.5" fill="{valf}" opacity="0.7"/>
    <text class="m lbl" x="{tx}" y="{ly}" fill="{muted}">{label}</text>
    <text class="m val" x="{tx}" y="{vy}" fill="{valf}">{value}</text>
    <text class="m sm"  x="{tx}" y="{sy}" fill="{dim}">{sub}</text>
  </g>""".format(x=x, y=y, w=w, h=h, tx=x + 18, ly=y + 26, vy=y + 64,
                 sy=y + 85, label=escape(label), value=escape(value),
                 sub=escape(sub), valf=value_fill, panel=PANEL,
                 hair=HAIRLINE, muted=MUTED, dim=DIM)


def human(n):
    if n >= 1000:
        return "{:.1f}k".format(n / 1000.0).replace(".0k", "k")
    return str(n)


def truncate(text, limit):
    return text if len(text) <= limit else text[:limit - 1] + "…"


# ── card 1: stats ───────────────────────────────────────────────────────

def build_stats(user, repos, langs, contributions):
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

    # Ordered by how much each tile earns its space. Every tile that can read
    # zero is conditional, so a new account never advertises a zero — and
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

    # Tiles stretch to fill the card, so 3 or 4 both look deliberate.
    x0, gap, th, ty = 24, 18, 102, 66
    span = 880 - x0 * 2
    tw = (span - gap * (len(cells) - 1)) / float(len(cells))

    body = ""
    for i, (label, value, sub) in enumerate(cells):
        body += tile(int(round(x0 + i * (tw + gap))), ty, int(round(tw)),
                     th, label, value, sub)

    body += ('\n  <text class="m sm" x="24" y="{}" fill="{}">'
             'auto-generated daily by scripts/render.py</text>'
             ).format(ty + th + 26, DIM)

    return card(880, ty + th + 46, "~/stats", body)


# ── card 2: language distribution ───────────────────────────────────────

def build_langs(langs):
    if not langs:
        return card(880, 150, "~/top-languages",
                    '\n  <text class="m sm" x="24" y="90" fill="{}">'
                    'no language data yet</text>'.format(DIM))

    total = float(sum(langs.values()))
    ranked = sorted(langs.items(), key=lambda kv: kv[1], reverse=True)[:6]

    # Fold the long tail so the bar stays readable and still sums to 100%.
    tail = total - sum(v for _, v in ranked)
    if len(langs) > 6 and tail > 0:
        ranked.append(("Other", tail))

    palette = {n: LANG_COLORS.get(n, FALLBACK_COLORS[i % len(FALLBACK_COLORS)])
               for i, (n, _) in enumerate(ranked)}

    bar_x, bar_y, bar_w, bar_h = 24, 72, 832, 20
    body = '\n  <g>'
    cursor = float(bar_x)
    for i, (name, size) in enumerate(ranked):
        seg = bar_w * size / total
        if i == len(ranked) - 1:
            seg = bar_x + bar_w - cursor   # absorb rounding, end flush
        rx = 5 if len(ranked) == 1 else 0
        body += ('<rect x="{:.2f}" y="{}" width="{:.2f}" height="{}" rx="{}" fill="{}"/>'
                 ).format(cursor, bar_y, max(seg, 0.6), bar_h, rx, palette[name])
        cursor += seg
    body += '</g>'

    body += ('\n  <rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6" '
             'fill="none" stroke="{b}" stroke-width="1"/>'
             ).format(x=bar_x, y=bar_y, w=bar_w, h=bar_h, b=BORDER)

    lx, ly, col_w = 24, 126, 278
    for i, (name, size) in enumerate(ranked):
        cx = lx + (i % 3) * col_w
        cy = ly + (i // 3) * 26
        body += ('''<g>
    <rect x="{cx}" y="{cy0}" width="10" height="10" rx="2.5" fill="{c}"/>
    <text class="m sm" x="{tx}" y="{cy}" fill="{t}">{n}</text>
    <text class="m sm" x="{px}" y="{cy}" fill="{d}" text-anchor="end">{p:.1f}%</text>
  </g>''').format(cx=cx, cy0=cy - 9, cy=cy, tx=cx + 17, px=cx + 246,
                   c=palette[name], t=TEXT, d=MUTED,
                   n=escape(truncate(name, 22)), p=100.0 * size / total)

    rows = (len(ranked) + 2) // 3
    return card(880, ly + rows * 26 + 22, "~/top-languages", body)


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

    cards = (
        ("stats.svg", build_stats(user, repos, langs, contributions)),
        ("langs.svg", build_langs(langs)),
    )
    for filename, svg in cards:
        path = os.path.join(out, filename)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(svg)
        print("  wrote {} ({} bytes)".format(path, len(svg)))

    print("done")


if __name__ == "__main__":
    main()
