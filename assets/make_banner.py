#!/usr/bin/env python3
"""Generate the README banner (light + dark) as SVG.

A README banner gets about one second of attention, so it has to answer two
questions in that second: what is this, and why should I care. The layout is
therefore typography-led and ordered by exactly that:

  1. the name
  2. what it does, in plain words, large
  3. the objections it removes — the reason anyone switches

Point 3 is the one usually buried in tiny grey type. Here it is the second
loudest element on the canvas, because "nothing gets uploaded" and "no API
keys" are the whole argument, not footnotes.

The mark stays small on purpose — a recognition token, not an illustration.
It is a waveform knocked out of one solid tile, and it is one shape rather
than several because everything thin turns to mush at this size. An earlier
attempt drew a waveform resolving into long rounded horizontal bars: that is
the universal skeleton-loader idiom, so it read as "loading", not "transcript".
A solid tile at maximum contrast still reads when scaled to a favicon.

Colour is one accent and it means one thing: this is what you get. It marks
the output filename in the command and the claims below the rule, nothing
else. The mark itself is monochrome, which keeps it from competing.

Sizes are authored large because GitHub renders the banner scaled down to the
readme column (~900px), so 92px of source becomes roughly 70px on screen.

Usage:  python3 assets/make_banner.py [name]
"""
from __future__ import annotations

import sys
from pathlib import Path

W, H = 1200, 438
PAD = 72

# --- vertical rhythm (8px base) ---------------------------------------------
NAME_BASE = 158           # wordmark baseline
TAGLINE_BASE = 220
CHIP_TOP = 250
CHIP_H = 46
RULE_Y = 338
CLAIMS_BASE = 376

SQ = 80                   # the mark is one solid object, not two thin ones
MARK_CY = 160             # optically centred on the name + tagline group
TYPE_X = PAD + SQ + 32

# --- Layer 1 primitives -> Layer 2 semantic tokens --------------------------
THEMES = {
    "light": {
        "surface": "#fbfbfd",        # off-white, never pure #fff
        "surface_sunken": "#f0f0f4",  # the command field
        "hairline": "#e0e0e6",
        "text_primary": "#1d1d1f",   # near-black, never pure #000
        "text_body": "#3c3c41",
        "text_secondary": "#6e6e73",
        "accent": "#0d9488",         # the only accent: what you get
    },
    "dark": {
        "surface": "#0b0b0c",
        "surface_sunken": "#18181b",
        "hairline": "#2a2a2e",
        "text_primary": "#f5f5f7",
        "text_body": "#d2d2d7",
        "text_secondary": "#98989d",
        "accent": "#2dd4bf",         # lifted for contrast on dark
    },
}

# Helvetica first: this is a Swiss-revival composition and Helvetica Neue is
# its canonical face. Falls back to the system UI sans everywhere else.
SANS = ("'Helvetica Neue', -apple-system, BlinkMacSystemFont, Inter, "
        "'Segoe UI', Arial, sans-serif")
MONO = "'SF Mono', Menlo, Consolas, ui-monospace, monospace"

TAGLINE = "Transcribe any audio or video in 100 languages, on your own machine."

# Ordered by how much the objection actually costs the user: privacy first,
# then the recurring bill and the signup friction, then reach.
# Kept short so the row survives a font substitution without colliding; each
# column has >90px of slack at these x positions.
CLAIMS = [
    (PAD, "Nothing gets uploaded"),
    (390, "No API keys"),
    (600, "No subscription"),
    (850, "Files or 1800+ sites"),
]

# The mark: a waveform knocked out of a solid tile. Two thin shapes at this
# size turn to mush; one solid shape with maximum contrast survives being
# scaled to a favicon.
BARS = [0.36, 0.68, 1.00, 0.59, 0.41]
BAR_W, BAR_GAP = 6, 4
INSET = 17


def mark(t: dict) -> str:
    """A waveform knocked out of a solid tile: one object, maximum contrast."""
    x0, y0 = PAD, MARK_CY - SQ / 2
    out = [f'<rect x="{x0}" y="{y0:.0f}" width="{SQ}" height="{SQ}" '
           f'rx="20" fill="{t["text_primary"]}"/>']
    inner = SQ - 2 * INSET
    span = len(BARS) * BAR_W + (len(BARS) - 1) * BAR_GAP
    x = x0 + (SQ - span) / 2
    for amp in BARS:
        h = max(inner * amp, BAR_W)
        out.append(
            f'<rect x="{x:.1f}" y="{MARK_CY - h / 2:.1f}" width="{BAR_W}" '
            f'height="{h:.1f}" rx="{BAR_W / 2:.1f}" fill="{t["surface"]}"/>'
        )
        x += BAR_W + BAR_GAP
    return "\n    ".join(out)


def claims(t: dict) -> str:
    out = []
    for x, label in CLAIMS:
        out.append(
            f'<circle cx="{x + 4}" cy="{CLAIMS_BASE - 7}" r="4.5" fill="{t["accent"]}"/>'
            f'<text x="{x + 18}" y="{CLAIMS_BASE}" font-family="{SANS}" '
            f'font-size="21" font-weight="500" fill="{t["text_primary"]}">{label}</text>'
        )
    return "\n  ".join(out)


def svg(theme: str, name: str) -> str:
    t = THEMES[theme]
    # Real size jumps, not four sizes of the same thing: 92 / 28 / 21 / 18.
    # Display gets negative tracking; nothing is set below 18px.
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{name} — {TAGLINE} Nothing gets uploaded, no API keys, no subscription, files or 1800+ sites.">
  <rect width="{W}" height="{H}" fill="{t['surface']}"/>
  <g>
    {mark(t)}
  </g>
  <text x="{TYPE_X}" y="{NAME_BASE}" font-family="{SANS}" font-size="92" font-weight="700" letter-spacing="-3.2" fill="{t['text_primary']}">{name}</text>
  <text x="{TYPE_X + 3}" y="{TAGLINE_BASE}" font-family="{SANS}" font-size="28" font-weight="400" fill="{t['text_body']}">{TAGLINE}</text>
  <rect x="{TYPE_X + 3}" y="{CHIP_TOP}" width="530" height="{CHIP_H}" rx="10" fill="{t['surface_sunken']}"/>
  <text x="{TYPE_X + 23}" y="{CHIP_TOP + 30}" font-family="{MONO}" font-size="18" fill="{t['text_body']}"><tspan fill="{t['text_secondary']}">$ </tspan>{name} interview.m4a<tspan fill="{t['accent']}"> → transcript.srt</tspan></text>
  <line x1="{PAD}" y1="{RULE_Y}" x2="{W - PAD}" y2="{RULE_Y}" stroke="{t['hairline']}" stroke-width="1"/>
  {claims(t)}
</svg>
"""


def main() -> None:
    name = sys.argv[1] if len(sys.argv) > 1 else "offscript"
    out_dir = Path(__file__).resolve().parent
    for theme in THEMES:
        path = out_dir / f"banner-{theme}.svg"
        path.write_text(svg(theme, name))
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
