#!/usr/bin/env python3
"""Generate the README banner (light + dark) as SVG.

A README banner gets about one second of attention, so it answers two
questions in that order: what is this, and why should I care.

Layout rules this file enforces, because breaking them is what made the
earlier versions feel off:

* ONE left edge. Everything stacked — tagline, command, claims — starts at
  PAD. Only the wordmark is indented, because the mark occupies that space
  beside it, which is how a lockup is supposed to read. An earlier version had
  two competing left edges (the mark and rule at 72, the type block at 187)
  and the whole thing looked ragged.
* One vertical rhythm. The mark is centred on the wordmark's cap band, not on
  its bounding box, so the lockup sits level.
* The claims get their own band. They are the reason anyone switches, so they
  are not a footnote in small grey type — they sit in a sunken strip at 22px,
  which also gives the banner a hard bottom edge instead of bleeding into the
  readme content underneath.
* The whole thing is a bordered card. Without a frame it dissolves into the
  page.

The mark is a waveform knocked out of one solid tile. It is one shape, not
several, because thin shapes turn to mush at this size; an earlier attempt
drew a waveform resolving into long rounded horizontal bars, which is the
skeleton-loader idiom and read as "loading" rather than "transcript".

Colour is one accent meaning one thing: this is what you get. It marks the
output filename and the claim bullets, nothing else. The mark stays
monochrome so it does not compete.

Sizes are authored large because GitHub scales the banner down to the readme
column (~900px), so 92px of source lands near 70px on screen.

Usage:  python3 assets/make_banner.py [name]
"""
from __future__ import annotations

import sys
from pathlib import Path

W = 1200
PAD = 64
RADIUS = 16                # card corner

# --- vertical rhythm --------------------------------------------------------
SQ = 80                    # the mark: one solid object
MARK_Y = 56
MARK_CY = MARK_Y + SQ / 2  # 96
NAME_SIZE = 92
NAME_CAP = 66              # cap height of the wordmark at NAME_SIZE
NAME_BASE = int(MARK_CY + NAME_CAP / 2)   # level the cap band with the mark
NAME_X = PAD + SQ + 24

TAGLINE_BASE = 189
CHIP_TOP, CHIP_H, CHIP_W = 219, 46, 530
BAND_TOP, BAND_H = 305, 76
H = BAND_TOP + BAND_H
CLAIMS_BASE = 351          # optically centred in the band

# --- Layer 1 primitives -> Layer 2 semantic tokens --------------------------
THEMES = {
    "light": {
        "surface": "#fbfbfd",        # off-white, never pure #fff
        "surface_sunken": "#eeeff4",  # the command field and the claims band
        "border": "#dcdce2",
        "text_primary": "#1d1d1f",   # near-black, never pure #000
        "text_body": "#3c3c41",
        "text_secondary": "#6e6e73",
        "accent": "#0d9488",         # the only accent: what you get
    },
    "dark": {
        "surface": "#0b0b0c",
        "surface_sunken": "#1a1a1f",
        "border": "#2c2c31",
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

# Ordered by what the objection actually costs the user: privacy, the
# recurring bill, signup friction, reach. x positions are hardcoded with
# ~50px of slack each, because GitHub serves this through <img> with no
# webfont — nothing may depend on measuring text.
CLAIMS = [
    (PAD, "Nothing gets uploaded"),
    (380, "No API keys"),
    (590, "No subscription"),
    (840, "Files or 1800+ sites"),
]

BARS = [0.36, 0.68, 1.00, 0.59, 0.41]
BAR_W, BAR_GAP, INSET = 6, 4, 17


def mark(t: dict) -> str:
    """A waveform knocked out of a solid tile: one object, maximum contrast."""
    out = [f'<rect x="{PAD}" y="{MARK_Y}" width="{SQ}" height="{SQ}" '
           f'rx="20" fill="{t["text_primary"]}"/>']
    inner = SQ - 2 * INSET
    span = len(BARS) * BAR_W + (len(BARS) - 1) * BAR_GAP
    x = PAD + (SQ - span) / 2
    for amp in BARS:
        h = max(inner * amp, BAR_W)
        out.append(
            f'<rect x="{x:g}" y="{MARK_CY - h / 2:g}" width="{BAR_W}" '
            f'height="{h:g}" rx="{BAR_W / 2:g}" fill="{t["surface"]}"/>'
        )
        x += BAR_W + BAR_GAP
    return "\n    ".join(out)


def claims(t: dict) -> str:
    out = []
    for x, label in CLAIMS:
        out.append(
            f'<circle cx="{x + 5}" cy="{CLAIMS_BASE - 7}" r="5" fill="{t["accent"]}"/>'
            f'<text x="{x + 20}" y="{CLAIMS_BASE}" font-family="{SANS}" '
            f'font-size="22" font-weight="600" fill="{t["text_primary"]}">{label}</text>'
        )
    return "\n    ".join(out)


def svg(theme: str, name: str) -> str:
    t = THEMES[theme]
    alt = (f"{name} — {TAGLINE} "
           "Nothing gets uploaded, no API keys, no subscription, "
           "files or 1800+ sites.")
    # Real size jumps: 92 / 28 / 22 / 18. Nothing is set below 18px.
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{alt}">
  <defs>
    <clipPath id="card">
      <rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="{RADIUS}"/>
    </clipPath>
  </defs>
  <g clip-path="url(#card)">
    <rect width="{W}" height="{H}" fill="{t['surface']}"/>
    <rect y="{BAND_TOP}" width="{W}" height="{BAND_H}" fill="{t['surface_sunken']}"/>
    <line x1="0" y1="{BAND_TOP}" x2="{W}" y2="{BAND_TOP}" stroke="{t['border']}" stroke-width="1"/>
    {mark(t)}
    <text x="{NAME_X}" y="{NAME_BASE}" font-family="{SANS}" font-size="{NAME_SIZE}" font-weight="700" letter-spacing="-3.2" fill="{t['text_primary']}">{name}</text>
    <text x="{PAD}" y="{TAGLINE_BASE}" font-family="{SANS}" font-size="28" fill="{t['text_body']}">{TAGLINE}</text>
    <rect x="{PAD}" y="{CHIP_TOP}" width="{CHIP_W}" height="{CHIP_H}" rx="10" fill="{t['surface_sunken']}"/>
    <text x="{PAD + 20}" y="{CHIP_TOP + 30}" font-family="{MONO}" font-size="18" fill="{t['text_body']}"><tspan fill="{t['text_secondary']}">$ </tspan>{name} interview.m4a<tspan fill="{t['accent']}"> → transcript.srt</tspan></text>
    {claims(t)}
  </g>
  <rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="{RADIUS}" fill="none" stroke="{t['border']}" stroke-width="1"/>
</svg>
"""


def main() -> None:
    name = sys.argv[1] if len(sys.argv) > 1 else "offscript"
    out_dir = Path(__file__).resolve().parent
    for theme in THEMES:
        path = out_dir / f"banner-{theme}.svg"
        path.write_text(svg(theme, name))
        print(f"wrote {path}  ({path.stat().st_size} B)")


if __name__ == "__main__":
    main()
