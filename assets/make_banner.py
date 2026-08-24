#!/usr/bin/env python3
"""Generate the README banner (light + dark) as SVG.

Design notes — Swiss / International Typographic Style: monochrome surface,
a single accent, dominant whitespace, asymmetric but balanced composition,
typography as an object (large size jumps).

The mark is narrative, not ornament: a vertical rhythm (sound) turns into a
horizontal one (text) across a single beat. The 90-degree change carries the
whole claim — audio in, transcript out — without an arrow or a fade.

The single accent marks only the output side of that transformation, and is
reused once on the output filename in the command line. Nothing else is
coloured, so the accent means exactly one thing: this is what you get.

Usage:  python3 assets/make_banner.py [name]
"""
from __future__ import annotations

import sys
from pathlib import Path

W, H = 1060, 340
PAD = 80                      # outer breathing room (§ spacing scale, 8px base)
MARK_X = PAD                  # mark occupies the left column
GUTTER = 96                   # mark -> type block, deliberately generous

# Type block: one baseline drives everything below it.
BASE_Y = 152                  # wordmark baseline
TAGLINE_DY = 44
CMD_DY = 96
CAPTION_DY = 138
# The mark centres on the optical middle of the whole type block, not on the
# wordmark — otherwise it reads as floating above the text.
MID_Y = BASE_Y + 34

# --- Layer 1: primitives -> Layer 2: semantic tokens -------------------------
THEMES = {
    "light": {
        "surface": "#fbfbfd",       # off-white, never pure #fff
        "text_primary": "#1d1d1f",  # near-black, never pure #000
        "text_secondary": "#6e6e73",
        "text_tertiary": "#8e8e93",
        "sound": "#c7c7cc",         # the neutral "before" state
        "accent": "#0d9488",        # the only accent: transcribed output
    },
    "dark": {
        "surface": "#0b0b0c",
        "text_primary": "#f5f5f7",
        "text_secondary": "#a1a1a6",
        "text_tertiary": "#7c7c82",
        "sound": "#3a3a3f",
        "accent": "#2dd4bf",        # lifted for contrast on dark
    },
}

# Helvetica first: this is a Swiss-revival composition and Helvetica Neue is
# its canonical face. Falls back to the system UI sans everywhere else.
SANS = ("'Helvetica Neue', -apple-system, BlinkMacSystemFont, Inter, "
        "'Segoe UI', Arial, sans-serif")
MONO = "'SF Mono', Menlo, Consolas, ui-monospace, monospace"

# A speech-like envelope: bursts and gaps, not a symmetric lens.
ENVELOPE = [0.34, 0.52, 0.28, 0.74, 0.55, 0.95, 0.62, 1.00, 0.78, 0.44, 0.86, 0.40]
BAR_W, BAR_GAP = 6, 11
BAR_MAX = 108
BAR_MIN = 16                                # never let a bar read as a dot

# The transcript side gets the same footprint as the sound side, so the mark
# reads as a transformation between two equals rather than a waveform with a
# small icon stuck to it.
LINE_H, LINE_GAP = 6, 16
LINE_LENGTHS = [1.00, 0.82, 0.93, 0.46]   # a paragraph, ragged right
SEAM = 34                                  # the beat where sound becomes text


def mark(t: dict) -> tuple[str, float]:
    """Vertical rhythm (sound) turning into horizontal rhythm (text).

    The transformation is a crisp 90-degree change, not a fade: a fade would
    read as the signal dying out, which is the opposite of the claim.
    Returns (svg fragment, total width).
    """
    out = []
    x = MARK_X
    for amp in ENVELOPE:
        h = max(BAR_MAX * amp, BAR_MIN)
        out.append(
            f'<rect x="{x:.1f}" y="{MID_Y - h / 2:.1f}" width="{BAR_W}" '
            f'height="{h:.1f}" rx="{BAR_W / 2:.1f}" fill="{t["sound"]}"/>'
        )
        x += BAR_W + BAR_GAP
    sound_w = x - BAR_GAP - MARK_X

    x = MARK_X + sound_w + SEAM
    text_w = sound_w                       # deliberate parity with the bars
    block_h = len(LINE_LENGTHS) * LINE_H + (len(LINE_LENGTHS) - 1) * LINE_GAP
    y = MID_Y - block_h / 2
    for frac in LINE_LENGTHS:
        out.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{text_w * frac:.1f}" '
            f'height="{LINE_H}" rx="{LINE_H / 2:.1f}" fill="{t["accent"]}"/>'
        )
        y += LINE_H + LINE_GAP
    return "\n    ".join(out), sound_w + SEAM + text_w


def svg(theme: str, name: str) -> str:
    t = THEMES[theme]
    frag, mark_w = mark(t)
    tx = MARK_X + mark_w + GUTTER
    # Typography as an object: 76 / 18 / 14 / 11.5 is a real hierarchy, not
    # four sizes of the same thing. Display gets negative tracking (-0.03em);
    # the uppercase micro-caption gets generous tracking.
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" role="img" aria-label="{name} — speech to text on your own machine">
  <rect width="{W}" height="{H}" fill="{t['surface']}"/>
  <g>
    {frag}
  </g>
  <text x="{tx}" y="{BASE_Y}" font-family="{SANS}" font-size="76" font-weight="600" letter-spacing="-2.3" fill="{t['text_primary']}">{name}</text>
  <text x="{tx + 2}" y="{BASE_Y + TAGLINE_DY}" font-family="{SANS}" font-size="18" font-weight="400" fill="{t['text_secondary']}">Speech to text on your own machine.</text>
  <text x="{tx + 2}" y="{BASE_Y + CMD_DY}" font-family="{MONO}" font-size="14" fill="{t['text_secondary']}"><tspan fill="{t['text_tertiary']}">$ </tspan>{name} interview.m4a<tspan fill="{t['accent']}"> → transcript.srt</tspan></text>
  <text x="{tx + 2}" y="{BASE_Y + CAPTION_DY}" font-family="{SANS}" font-size="11.5" font-weight="500" letter-spacing="1.4" fill="{t['text_tertiary']}">NO CLOUD · NO API KEYS · 1800+ SITES · MIT</text>
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
