#!/usr/bin/env python3
"""numbers.py: draws the profile's two benchmark images.

    numbers.py OUTDIR

Writes headline.svg (four figures) and start-up.svg (the time from start to
exit of `hello`, side by side) into OUTDIR, each twice, NAME.svg for GitHub's
dark theme and NAME-light.svg for its light one.

Every number is copied from cig-script's benchmark paper,
docs/BENCHMARKS-2026-11-15.md: the headline figures from its summary and its
table of time ÷ theirs (row "stage b"), the start-up times from its table
"Every program", row `hello`, each the median of 62 timed runs (31 rounds in
each of two passes).
"""
import os
import sys
from xml.sax.saxutils import escape

PAPER = "cig-script docs/BENCHMARKS-2026-11-15.md"
SANS = "ui-sans-serif, system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif"
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"

HEADLINE = [  # (figure, what it is, over what)
    ("0.82×", "CPython 3.13's time", "21 programs, stage b"),
    ("0.84×", "Node 22's time", "20 programs, stage b"),
    ("0.52×", "cig run's own time", "stage b, faster on all 21"),
    ("3.7 ms", "hello, compiled", "CPython 13.5, Node 27.2"),
]

START_UP = [  # (side, median ms, cig's own)
    ("Lua 5.4", 0.9, False),
    ("Rust", 0.9, False),
    ("LuaJIT 2.1", 1.0, False),
    ("cig, compiled (stage b)", 3.7, True),
    ("cig run", 5.8, True),
    ("CPython 3.13", 13.5, False),
    ("Node 22", 27.2, False),
]

FOOTNOTES = [
    "cig 1.24.0 and cigcompile 0.5.0 as released; one 2018 laptop on battery, 15 Nov 2026.",
    "Lua 5.4.9, LuaJIT 2.1, CPython 3.13.5, Node 22.23.5, Rust 1.100.0.",
    "cig's start-up grows with its run history (cig-script#252).",
    f"Every number: {PAPER}.",
]

# GitHub's dark and light grounds; the orange is cig's own, darkened on white so it can be read.
THEMES = {
    "": {"hot": "#f97316", "hot_from": "#c2410c", "label": "#c9d1d9", "muted": "#8b949e",
         "box": "#3d444d", "bar": "#6e7681"},
    "-light": {"hot": "#c2410c", "hot_from": "#ea580c", "label": "#1f2328", "muted": "#59636e",
               "box": "#d0d7de", "bar": "#8c959f"},
}


def style(t):
    return f"""
    .h {{ font: 700 15px {MONO}; fill: {t['hot']}; }}
    .big {{ font: 700 34px {MONO}; fill: {t['hot']}; }}
    .l {{ font: 400 14px {SANS}; fill: {t['label']}; }}
    .lh {{ font: 700 14px {SANS}; fill: {t['hot']}; }}
    .k {{ font: 400 12px {SANS}; fill: {t['muted']}; }}
    .v {{ font: 400 13px {MONO}; fill: {t['muted']}; }}
    .vh {{ font: 700 13px {MONO}; fill: {t['hot']}; }}
    .box {{ fill: none; stroke: {t['box']}; stroke-width: 1.5; }}
    .hot {{ fill: none; stroke: {t['hot']}; stroke-width: 2; }}
    .bar {{ transform-box: fill-box; transform-origin: left center; animation: grow 0.9s cubic-bezier(0.2, 0.8, 0.2, 1) backwards; }}
    .rise {{ animation: rise 0.6s ease-out backwards; }}
    .val {{ animation: fade 0.4s ease-out backwards; }}
    @keyframes grow {{ from {{ transform: scaleX(0); }} }}
    @keyframes rise {{ from {{ opacity: 0; transform: translateY(8px); }} }}
    @keyframes fade {{ from {{ opacity: 0; }} }}
    @media (prefers-reduced-motion: reduce) {{ .bar, .rise, .val {{ animation: none; }} }}
"""


def svg(width, height, label, title, body, t):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" aria-label="{escape(label, {chr(34): "&quot;"})}">\n'
            f'<title>{escape(title)}</title>\n'
            f'<defs>\n  <linearGradient id="ember" x1="0" y1="0" x2="1" y2="0">'
            f'<stop offset="0" stop-color="{t["hot_from"]}"/><stop offset="1" stop-color="{t["hot"]}"/></linearGradient>\n'
            f'  <style>{style(t)}  </style>\n</defs>\n{body}\n</svg>\n')


def headline(t):
    width, gap, tile_h = 820, 14, 124
    tile_w = (width - 2 - gap * (len(HEADLINE) - 1)) / len(HEADLINE)
    body = []
    for i, (figure, what, over) in enumerate(HEADLINE):
        x = 1 + i * (tile_w + gap)
        mid = x + tile_w / 2
        body.append(f'<g class="rise" style="animation-delay: {150 + i * 150}ms">'
                    f'<rect x="{x:.1f}" y="1" width="{tile_w:.1f}" height="{tile_h}" rx="10" class="{"hot" if i == 0 else "box"}"/>'
                    f'<text x="{mid:.1f}" y="56" class="big" text-anchor="middle">{escape(figure)}</text>'
                    f'<text x="{mid:.1f}" y="84" class="l" text-anchor="middle">{escape(what)}</text>'
                    f'<text x="{mid:.1f}" y="104" class="k" text-anchor="middle">{escape(over)}</text></g>')
    label = "; ".join(f"{figure} {what}, {over}" for figure, what, over in HEADLINE) + f". From {PAPER}."
    return svg(width, tile_h + 2, label, "cig against CPython and Node", "\n".join(body), t)


def start_up(t):
    width, top, step, bar_x, bar_max = 820, 82, 34, 240, 470
    longest = max(ms for _, ms, _ in START_UP)
    foot = top + step * len(START_UP) + 18
    height = foot + 20 * (len(FOOTNOTES) - 1) + 14
    body = ['<text x="20" y="30" class="h">hello, start to exit</text>',
            '<text x="20" y="54" class="k">median of 62 timed runs each, in milliseconds, start-up included; shorter is faster</text>']
    for i, (side, ms, hot) in enumerate(START_UP):
        y = top + i * step
        w = max(bar_max * ms / longest, 3)
        delay = 200 + i * 120
        fill = 'fill="url(#ember)"' if hot else f'fill="{t["bar"]}"'
        body.append(f'<text x="{bar_x - 14}" y="{y + 14}" class="{"lh" if hot else "l"}" text-anchor="end">{escape(side)}</text>'
                    f'<rect class="bar" style="animation-delay: {delay}ms" x="{bar_x}" y="{y}" width="{w:.1f}" height="19" rx="4" {fill}/>'
                    f'<text class="val {"vh" if hot else "v"}" style="animation-delay: {delay + 500}ms" '
                    f'x="{bar_x + w + 10:.1f}" y="{y + 14}">{ms:.1f} ms</text>')
    for i, note in enumerate(FOOTNOTES):
        body.append(f'<text x="20" y="{foot + 20 * i}" class="k">{escape(note)}</text>')
    label = ("hello, from start to exit, median milliseconds: "
             + ", ".join(f"{side} {ms}" for side, ms, _ in START_UP) + f". From {PAPER}.")
    return svg(width, height, label, "hello, start to exit", "\n".join(body), t)


def main():
    if len(sys.argv) != 2:
        sys.exit("usage: numbers.py OUTDIR")
    os.makedirs(sys.argv[1], exist_ok=True)
    for suffix, t in THEMES.items():
        for name, draw in (("headline", headline), ("start-up", start_up)):
            with open(os.path.join(sys.argv[1], f"{name}{suffix}.svg"), "w", encoding="utf-8") as f:
                f.write(draw(t))


if __name__ == "__main__":
    main()
