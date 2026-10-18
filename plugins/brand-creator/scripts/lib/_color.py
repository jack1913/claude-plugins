"""Colour maths shared by contrast.py, logo_sheet.py and the emitters. Standard library only."""
from __future__ import annotations

import re

HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{6})$")


def parse_hex(h: str) -> tuple[int, int, int]:
    h = h.strip()
    if re.fullmatch(r"#[0-9a-fA-F]{3}", h):
        h = "#" + "".join(c * 2 for c in h[1:])
    if not HEX_RE.match(h):
        raise ValueError(f"not a #rrggbb colour: {h!r}")
    return int(h[1:3], 16), int(h[3:5], 16), int(h[5:7], 16)


def to_hex(rgb) -> str:
    return "#%02x%02x%02x" % tuple(int(round(v)) for v in rgb[:3])


def _lin(c: float) -> float:
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(rgb) -> float:
    r, g, b = (_lin(v) for v in rgb[:3])
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def wcag_ratio(a, b) -> float:
    """WCAG 2.x contrast ratio of two (r, g, b) tuples or #rrggbb strings."""
    ra = parse_hex(a) if isinstance(a, str) else a
    rb = parse_hex(b) if isinstance(b, str) else b
    la, lb = luminance(ra), luminance(rb)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)
