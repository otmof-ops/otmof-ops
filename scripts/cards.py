#!/usr/bin/env python3
"""cards.py: the profile's cards, drawn from GitHub's own numbers.

    cards.py --user LOGIN --out DIR [--pin REPO ...]

Writes each card into DIR twice, NAME.svg for GitHub's dark theme and
NAME-light.svg for its light one:

  stats       own public repositories, their stars and version releases,
              followers, and the last 12 months' commits, pull requests and
              issues in public repositories
  languages   the languages of those repositories, by size
  releases    the newest version releases across them
  pin-REPO    one card for each --pin repository

Only public data is counted. The workflow's token sees nothing else; a user
token sees private repositories too and they are left out, but GitHub's
per-repository contribution lists stop at 100 repositories, private ones
included, so the script warns when a list is full. The token comes from
GITHUB_TOKEN (or GH_TOKEN). Standard library only.

Icons: Primer Octicons, MIT License, Copyright (c) 2026 GitHub Inc.
"""
import argparse
import json
import math
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from xml.sax.saxutils import escape

API = "https://api.github.com/graphql"
VERSION = re.compile(r"^v?[0-9]+(\.[0-9]+)+([-+][0-9A-Za-z.-]+)?$")  # releases are version tags, not rolling ones
COLOR = re.compile(r"^#[0-9A-Fa-f]{3,8}$")
ILLEGAL = re.compile("[^\t\n\r -퟿-�\U00010000-\U0010ffff]")  # characters XML cannot hold
FONT = "'Segoe UI', Ubuntu, 'Helvetica Neue', Sans-Serif"
ATTRIBUTION = "<!-- Icons: Primer Octicons, MIT License, Copyright (c) 2026 GitHub Inc. -->"
CONTRIBUTION_LISTS = ("commitContributionsByRepository", "pullRequestContributionsByRepository",
                      "issueContributionsByRepository")

# The ember palette, cig's own orange and the coals behind it, once per GitHub theme.
# "arcs" color the contribution ring: commits, pull requests, issues.
THEMES = {
    "": {"bg": "#0d1117", "edge": "#30363d", "track": "#21262d", "title": "#f97316", "text": "#c9d1d9",
         "muted": "#8b949e", "ember": "#c2410c", "value": "#fdba74", "coal": "#431407",
         "arcs": ("#f97316", "#c2410c", "#fdba74")},
    "-light": {"bg": "#ffffff", "edge": "#d0d7de", "track": "#eaeef2", "title": "#c2410c", "text": "#1f2328",
               "muted": "#59636e", "ember": "#ea580c", "value": "#9a3412", "coal": "#fed7aa",
               "arcs": ("#ea580c", "#9a3412", "#d97706")},
}

ICON = {
    "repo": "M2 2.5A2.5 2.5 0 0 1 4.5 0h8.75a.75.75 0 0 1 .75.75v12.5a.75.75 0 0 1-.75.75h-2.5a.75.75 0 0 1 0-1.5h1.75v-2h-8a1 1 0 0 0-.714 1.7.75.75 0 1 1-1.072 1.05A2.495 2.495 0 0 1 2 11.5Zm10.5-1h-8a1 1 0 0 0-1 1v6.708A2.486 2.486 0 0 1 4.5 9h8ZM5 12.25a.25.25 0 0 1 .25-.25h3.5a.25.25 0 0 1 .25.25v3.25a.25.25 0 0 1-.4.2l-1.45-1.087a.249.249 0 0 0-.3 0L5.4 15.7a.25.25 0 0 1-.4-.2Z",
    "star": "M8 .25a.75.75 0 0 1 .673.418l1.882 3.815 4.21.612a.75.75 0 0 1 .416 1.279l-3.046 2.97.719 4.192a.751.751 0 0 1-1.088.791L8 12.347l-3.766 1.98a.75.75 0 0 1-1.088-.79l.72-4.194L.818 6.374a.75.75 0 0 1 .416-1.28l4.21-.611L7.327.668A.75.75 0 0 1 8 .25Zm0 2.445L6.615 5.5a.75.75 0 0 1-.564.41l-3.097.45 2.24 2.184a.75.75 0 0 1 .216.664l-.528 3.084 2.769-1.456a.75.75 0 0 1 .698 0l2.77 1.456-.53-3.084a.75.75 0 0 1 .216-.664l2.24-2.183-3.096-.45a.75.75 0 0 1-.564-.41L8 2.694Z",
    "fork": "M5 5.372v.878c0 .414.336.75.75.75h4.5a.75.75 0 0 0 .75-.75v-.878a2.25 2.25 0 1 1 1.5 0v.878a2.25 2.25 0 0 1-2.25 2.25h-1.5v2.128a2.251 2.251 0 1 1-1.5 0V8.5h-1.5A2.25 2.25 0 0 1 3.5 6.25v-.878a2.25 2.25 0 1 1 1.5 0ZM5 3.25a.75.75 0 1 0-1.5 0 .75.75 0 0 0 1.5 0Zm6.75.75a.75.75 0 1 0 0-1.5.75.75 0 0 0 0 1.5Zm-3 8.75a.75.75 0 1 0-1.5 0 .75.75 0 0 0 1.5 0Z",
    "tag": "M1 7.775V2.75C1 1.784 1.784 1 2.75 1h5.025c.464 0 .91.184 1.238.513l6.25 6.25a1.75 1.75 0 0 1 0 2.474l-5.026 5.026a1.75 1.75 0 0 1-2.474 0l-6.25-6.25A1.752 1.752 0 0 1 1 7.775Zm1.5 0c0 .066.026.13.073.177l6.25 6.25a.25.25 0 0 0 .354 0l5.025-5.025a.25.25 0 0 0 0-.354l-6.25-6.25a.25.25 0 0 0-.177-.073H2.75a.25.25 0 0 0-.25.25ZM6 5a1 1 0 1 1 0 2 1 1 0 0 1 0-2Z",
    "flame": "M9.533.753V.752c.217 2.385 1.463 3.626 2.653 4.81C13.37 6.74 14.498 7.863 14.498 10c0 3.5-3 6-6.5 6S1.5 13.512 1.5 10c0-1.298.536-2.56 1.425-3.286.376-.308.862 0 1.035.454C4.46 8.487 5.581 8.419 6 8c.282-.282.341-.811-.003-1.5C4.34 3.187 7.035.75 8.77.146c.39-.137.726.194.763.607ZM7.998 14.5c2.832 0 5-1.98 5-4.5 0-1.463-.68-2.19-1.879-3.383l-.036-.037c-1.013-1.008-2.3-2.29-2.834-4.434-.322.256-.63.579-.864.953-.432.696-.621 1.58-.046 2.73.473.947.67 2.284-.278 3.232-.61.61-1.545.84-2.403.633a2.79 2.79 0 0 1-1.436-.874A3.198 3.198 0 0 0 3 10c0 2.53 2.164 4.5 4.998 4.5Z",
}

PROFILE = """
query($login: String!) {
  user(login: $login) {
    followers { totalCount }
    contributionsCollection {
      commitContributionsByRepository(maxRepositories: 100) { repository { isPrivate } contributions { totalCount } }
      pullRequestContributionsByRepository(maxRepositories: 100) { repository { isPrivate } contributions { totalCount } }
      issueContributionsByRepository(maxRepositories: 100) { repository { isPrivate } contributions { totalCount } }
    }
  }
}
"""

REPOS = """
query($login: String!, $after: String) {
  user(login: $login) {
    repositories(first: 50, after: $after, ownerAffiliations: OWNER, privacy: PUBLIC, isFork: false,
                 orderBy: {field: NAME, direction: ASC}) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes {
        name
        description
        stargazerCount
        forkCount
        primaryLanguage { name color }
        releases(first: 100, orderBy: {field: CREATED_AT, direction: DESC}) {
          pageInfo { hasNextPage endCursor }
          nodes { tagName publishedAt isPrerelease isDraft }
        }
        languages(first: 100, orderBy: {field: SIZE, direction: DESC}) {
          edges { size node { name color } }
        }
      }
    }
  }
}
"""

RELEASES = """
query($owner: String!, $name: String!, $after: String) {
  repository(owner: $owner, name: $name) {
    releases(first: 100, after: $after, orderBy: {field: CREATED_AT, direction: DESC}) {
      pageInfo { hasNextPage endCursor }
      nodes { tagName publishedAt isPrerelease isDraft }
    }
  }
}
"""


def query(token, text, variables, tries=3):
    body = json.dumps({"query": text, "variables": variables}).encode()
    for attempt in range(1, tries + 1):
        req = urllib.request.Request(API, data=body, headers={
            "Authorization": "bearer " + token, "Content-Type": "application/json",
            "User-Agent": "profile-cards"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                got = json.load(resp)
        except urllib.error.HTTPError as err:
            if err.code < 500 or attempt == tries:
                sys.exit(f"GitHub answered {err.code} {err.reason}")
        except OSError as err:
            if attempt == tries:
                sys.exit(f"could not reach GitHub: {err}")
        else:
            if got.get("errors"):
                sys.exit("GitHub said: " + json.dumps(got["errors"])[:500])
            return got["data"]
        time.sleep(5 * attempt)
    raise AssertionError("unreachable")


def fetch(token, login):
    """The user, their own public repositories (every page) and each one's every release."""
    user = query(token, PROFILE, {"login": login})["user"]
    if not user:
        sys.exit(f"no GitHub user called {login}")
    for key in CONTRIBUTION_LISTS:
        if len(user["contributionsCollection"][key]) >= 100:
            print(f"warning: {key} holds 100 repositories, GitHub's limit, so its counts may be short",
                  file=sys.stderr)
    user["repos"], after = [], None
    while True:
        page = query(token, REPOS, {"login": login, "after": after})["user"]["repositories"]
        for repo in page["nodes"]:
            releases = repo["releases"]
            while releases["pageInfo"]["hasNextPage"]:
                more = query(token, RELEASES, {"owner": login, "name": repo["name"],
                                               "after": releases["pageInfo"]["endCursor"]})
                more = more["repository"]["releases"]
                releases["nodes"].extend(more["nodes"])
                releases["pageInfo"] = more["pageInfo"]
            user["repos"].append(repo)
        user["repo_count"] = page["totalCount"]
        if not page["pageInfo"]["hasNextPage"]:
            return user
        after = page["pageInfo"]["endCursor"]


def clean(value):
    return ILLEGAL.sub("", value or "")


def text(value):
    return escape(clean(value))


def attr(value):
    return escape(clean(value), {'"': "&quot;"})


def clip(value, limit):
    value = clean(value)
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "…"


def color(value, fallback):
    return value if value and COLOR.match(value) else fallback


def est(value, px):
    """A generous width estimate, wide enough for DejaVu Sans, the usual Linux fallback."""
    return len(value) * px * 0.62


def day(stamp):
    d = datetime.fromisoformat(stamp.replace("Z", "+00:00")) if isinstance(stamp, str) else stamp
    return f"{d.day} {d:%b %Y}"


def public_total(entries):
    return sum(e["contributions"]["totalCount"] for e in entries if not e["repository"]["isPrivate"])


def versions(repo):
    """A repository's published version releases, newest first."""
    return [r for r in repo["releases"]["nodes"]
            if not r["isDraft"] and r["publishedAt"] and VERSION.match(r["tagName"])]


def card(width, height, body, label, p, icons=True):
    """A card: the ground, a hairline edge, an ember line along the top."""
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{attr(label)}">
{ATTRIBUTION if icons else ""}
<title>{text(label)}</title>
<defs>
  <linearGradient id="ember" x1="0" y1="0" x2="1" y2="0">
    <stop offset="0" stop-color="{p['coal']}"/><stop offset="0.55" stop-color="{p['ember']}"/><stop offset="1" stop-color="{p['title']}"/>
  </linearGradient>
  <clipPath id="shape"><rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="10"/></clipPath>
  <style>
    .t {{ font: 600 18px {FONT}; fill: {p['title']}; }}
    .l {{ font: 400 14px {FONT}; fill: {p['text']}; }}
    .v {{ font: 700 14px {FONT}; fill: {p['value']}; }}
    .s {{ font: 400 12px {FONT}; fill: {p['muted']}; }}
    .d {{ font: 400 13px {FONT}; fill: {p['text']}; }}
    .row {{ animation: in 0.5s ease-out backwards; }}
    .spin {{ transform-box: fill-box; transform-origin: center; animation: spin 1.2s ease-out 0.2s backwards; }}
    @keyframes in {{ from {{ opacity: 0; transform: translateX(-6px); }} }}
    @keyframes spin {{ from {{ opacity: 0; transform: rotate(-60deg); }} }}
    @media (prefers-reduced-motion: reduce) {{ .row, .spin {{ animation: none; }} }}
  </style>
</defs>
<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="10" fill="{p['bg']}" stroke="{p['edge']}"/>
<rect x="0" y="0" width="{width}" height="4" fill="url(#ember)" clip-path="url(#shape)"/>
{body}
</svg>
"""


def icon(name, x, y, size, fill):
    return f'<path transform="translate({x} {y}) scale({size / 16})" fill="{fill}" d="{ICON[name]}"/>'


def row(i, delay_step, inner):
    return f'<g class="row" style="animation-delay: {150 + i * delay_step}ms">{inner}</g>'


def arcs(cx, cy, r, stroke, parts, track):
    """A ring: the track, then one arc per part, in proportion, with a hairline gap between."""
    out = [f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{track}" stroke-width="{stroke}"/>']
    total = sum(size for size, _ in parts)
    c = 2 * math.pi * r
    start = 0.0
    drawn = [(size, fill) for size, fill in parts if size > 0]
    for size, fill in drawn:
        length = c * size / total
        gap = 1.5 if len(drawn) > 1 and length > 4 else 0
        out.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{fill}" stroke-width="{stroke}" '
                   f'stroke-dasharray="{length - gap:.2f} {c:.2f}" stroke-dashoffset="{-start:.2f}" '
                   f'transform="rotate(-90 {cx} {cy})"/>')
        start += length
    return out


def stats_card(login, user, p, today):
    repos = user["repos"]
    cc = user["contributionsCollection"]
    commits, prs, issues = (public_total(cc[key]) for key in CONTRIBUTION_LISTS)
    rows = [
        ("Own public repositories", user["repo_count"], p["ember"]),
        ("Stars on them", sum(r["stargazerCount"] for r in repos), p["ember"]),
        ("Releases", sum(len(versions(r)) for r in repos), p["ember"]),
        ("Commits (12 months)", commits, p["arcs"][0]),
        ("Pull requests (12 months)", prs, p["arcs"][1]),
        ("Issues opened (12 months)", issues, p["arcs"][2]),
        ("Followers", user["followers"]["totalCount"], p["ember"]),
    ]
    body = [f'<text x="25" y="38" class="t">{text(clip(login, 22))} · burning since day one</text>']
    for i, (label, value, fill) in enumerate(rows):
        y = 68 + i * 24
        body.append(row(i, 110, f'{icon("flame", 25, y - 13, 14, fill)}'
                                f'<text x="47" y="{y}" class="l">{label}</text>'
                                f'<text x="300" y="{y}" class="v" text-anchor="end">{value:,}</text>'))
    body.append(f'<text x="25" y="238" class="s">public repositories only, updated {today}</text>')
    total = commits + prs + issues
    cx, cy, r = 400, 118, 56
    body.append('<g class="spin">')
    body.extend(arcs(cx, cy, r, 10, list(zip((commits, prs, issues), p["arcs"])), p["track"]))
    body.append('</g>')
    shown = f"{total:,}"
    size = 24 if len(shown) <= 5 else 20 if len(shown) <= 7 else 16
    body.append(f'<text x="{cx}" y="{cy + 2}" class="v" text-anchor="middle" style="font-size: {size}px">{shown}</text>')
    body.append(f'<text x="{cx}" y="{cy + 21}" class="s" text-anchor="middle">contributions</text>')
    body.append(f'<text x="{cx}" y="{cy + r + 26}" class="s" text-anchor="middle">public, last 12 months</text>')
    return card(495, 250, "\n".join(body), f"{clean(login)}'s GitHub stats", p)


def languages_card(user, p, top=6, floor=0.01):
    sizes, colors = {}, {}
    for repo in user["repos"]:
        for edge in repo["languages"]["edges"]:
            name = clean(edge["node"]["name"])
            sizes[name] = sizes.get(name, 0) + edge["size"]
            colors[name] = color(edge["node"]["color"], p["muted"])
    total = sum(sizes.values())
    ranked = sorted(sizes.items(), key=lambda kv: (-kv[1], kv[0]))
    shown = [(n, s) for n, s in ranked[:top] if total and s / total >= floor]
    rest = total - sum(s for _, s in shown)
    if rest:
        shown.append(("Other", rest))
        colors["Other"] = p["muted"]
    height = max(250, 96 + len(shown) * 28)
    cx, cy, r = 92, 64 + (height - 64) / 2, 56
    body = ['<text x="25" y="38" class="t">Languages</text>']
    body.extend(arcs(cx, round(cy, 1), r, 20, [(size, colors[name]) for name, size in shown], p["track"]))
    if shown:
        lead, lead_size = shown[0]
        body.append(f'<text x="{cx}" y="{cy + 2:.1f}" class="v" text-anchor="middle" style="font-size: 18px">'
                    f'{100 * lead_size / total:.1f}%</text>')
        body.append(f'<text x="{cx}" y="{cy + 19:.1f}" class="s" text-anchor="middle">{text(clip(lead, 12))}</text>')
    else:
        body.append(f'<text x="{cx}" y="{cy + 4:.1f}" class="s" text-anchor="middle">no code yet</text>')
    top_y = cy - (len(shown) - 1) * 14
    for i, (name, size) in enumerate(shown):
        y = top_y + i * 28
        body.append(row(i, 90, f'<circle cx="190" cy="{y - 4:.1f}" r="5" fill="{colors[name]}"/>'
                               f'<text x="203" y="{y:.1f}" class="l">{text(clip(name, 13))}</text>'
                               f'<text x="328" y="{y:.1f}" class="s" text-anchor="end">{100 * size / total:.1f}%</text>'))
    return card(350, height, "\n".join(body), "languages in public repositories", p, icons=False)


def releases_card(user, p, top=7):
    found = []
    for repo in user["repos"]:
        for rel in versions(repo):
            found.append((rel["publishedAt"], repo["name"], rel["tagName"], rel["isPrerelease"]))
    found.sort(reverse=True)
    body = ['<text x="25" y="38" class="t">Latest releases</text>']
    for i, (when, repo, tag, pre) in enumerate(found[:top]):
        y = 68 + i * 26
        shown_tag = clip(tag, 16) + (" (pre)" if pre else "")
        room = 320 - est(shown_tag, 14) - 12 - 47  # the name gives way to the tag
        body.append(row(i, 100, f'{icon("tag", 25, y - 13, 14, p["ember"])}'
                                f'<text x="47" y="{y}" class="l">{text(clip(repo, max(6, int(room / (14 * 0.62)))))}</text>'
                                f'<text x="320" y="{y}" class="v" text-anchor="end">{text(shown_tag)}</text>'
                                f'<text x="470" y="{y}" class="s" text-anchor="end">{day(when)}</text>'))
    if not found:
        body.append('<text x="25" y="68" class="s">No releases yet</text>')
    height = 68 + max(len(found[:top]), 1) * 26 + 6
    return card(495, height, "\n".join(body), "latest releases", p)


def wrap(value, width, most=2):
    words = []
    for word in clean(value).split():
        while len(word) > width:
            words.append(word[:width])
            word = word[width:]
        words.append(word)
    lines, line = [], ""
    for word in words:
        if line and len(line) + 1 + len(word) > width:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}" if line else word
    if line:
        lines.append(line)
    if len(lines) > most:
        lines = lines[:most]
        lines[-1] = lines[-1][: width - 1].rstrip() + "…"
    return lines


def pin_card(repo, p):
    stable = next((r for r in versions(repo) if not r["isPrerelease"]), None)
    tag = clip(stable["tagName"], 18) if stable else None
    lang = repo["primaryLanguage"]
    body = [icon("repo", 25, 22, 16, p["muted"]),
            f'<text x="49" y="35" class="t" style="font-size: 16px">{text(clip(repo["name"], 30))}</text>']
    for i, line in enumerate(wrap(repo["description"], 48)):
        body.append(f'<text x="25" y="{62 + i * 18}" class="d">{text(line)}</text>')
    pill = 18 + est(tag, 12) if tag else 0
    room = (375 - pill - 12) if tag else 375
    blocks = []  # left to right; the last ones give way first when the tag needs the room
    if lang:
        name = clip(lang["name"], 16)
        blocks.append((17 + est(name, 12), lambda x, name=name: (
            f'<circle cx="{x + 6:.1f}" cy="104" r="6" fill="{color(lang["color"], p["muted"])}"/>'
            f'<text x="{x + 17:.1f}" y="109" class="s">{text(name)}</text>')))
    for kind, count in (("star", repo["stargazerCount"]), ("fork", repo["forkCount"])):
        shown = f"{count:,}"
        blocks.append((19 + est(shown, 12), lambda x, kind=kind, shown=shown: (
            icon(kind, round(x, 1), 97, 14, p["muted"]) + f'<text x="{x + 19:.1f}" y="109" class="s">{shown}</text>')))
    while blocks and 25 + sum(w for w, _ in blocks) + 16 * (len(blocks) - 1) > room:
        blocks.pop()
    x = 25
    for w, draw in blocks:
        body.append(draw(x))
        x += w + 16
    if tag:
        body.append(f'<rect x="{375 - pill:.1f}" y="93" width="{pill:.1f}" height="22" rx="11" fill="none" stroke="{p["title"]}"/>'
                    f'<text x="{375 - pill / 2:.1f}" y="109" class="v" style="font-size: 12px" text-anchor="middle">'
                    f'{text(tag)}</text>')
    return card(400, 128, "\n".join(body), clean(repo["name"]), p)


def main():
    ap = argparse.ArgumentParser(description="Draw the profile's cards from GitHub's numbers.")
    ap.add_argument("--user", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--pin", action="append", default=[])
    args = ap.parse_args()
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        sys.exit("set GITHUB_TOKEN (or GH_TOKEN)")
    user = fetch(token, args.user)
    by_name = {r["name"]: r for r in user["repos"]}
    missing = [name for name in args.pin if name not in by_name]
    if missing:
        sys.exit(f"not among {args.user}'s own public repositories: {', '.join(missing)}")
    today = day(datetime.now(timezone.utc))
    os.makedirs(args.out, exist_ok=True)
    written = 0
    for suffix, p in THEMES.items():
        files = {"stats": stats_card(args.user, user, p, today), "languages": languages_card(user, p),
                 "releases": releases_card(user, p)}
        for name in args.pin:
            files[f"pin-{name}"] = pin_card(by_name[name], p)
        for name, svg in files.items():
            with open(os.path.join(args.out, f"{name}{suffix}.svg"), "w", encoding="utf-8") as f:
                f.write(svg)
            written += 1
    print(f"{written} cards for {args.user}")


if __name__ == "__main__":
    main()
