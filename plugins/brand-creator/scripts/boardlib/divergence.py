"""Colour divergence between the directions of a pick board, as data: do two directions look alike in colour?

Each direction carries its light-mode colours in its own `style` attribute, as the custom properties `--d-paper`, `--d-ink` and `--d-accent`, each written
`#rgb` or `#rrggbb`. `read_colours` reads them; a direction that does not carry all three as such a value (a template marker, `rgb()`, a missing property)
is not measured. `row` turns the measured directions into the one row board-lint reports, `directions:divergence`: a warning naming each pair of directions
whose paper and ink are both within `PAPER_INK` and whose accents are within `ACCENT` of each other, a pass that names the smallest distance of each colour,
or an info row when fewer than two directions can be measured. The distance is the Euclidean distance of two colours in OKLab (L, a, b with L from 0 to 1;
a just-noticeable difference is about 0.02). The two thresholds are a practice proposal, not a measured rule, and the row says so; it never fails.

Standard library only; no clock, no network, no files. This folder is outside scripts/lib/, so a change here does not make every pack stale.
"""
from __future__ import annotations

import re
from itertools import combinations

PAPER_INK = 0.04   # paper and ink: both within this OKLab distance
ACCENT = 0.06      # accent: within this OKLab distance
PROPERTIES = ("--d-paper", "--d-ink", "--d-accent")   # the order the colours are named in a detail
LABEL = "the directions do not look alike in colour"
PROPOSAL = f"Alike means paper and ink each within {PAPER_INK} and accents within {ACCENT} (OKLab distance); these thresholds are a practice proposal, so the row only warns"

_HEX = re.compile(r"#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})")


def parse_hex(value: str) -> tuple[int, int, int] | None:
    """`#rgb` or `#rrggbb` (white space around it allowed) as (r, g, b) from 0 to 255; None for anything else, `#rrggbbaa` and `rgb()` included."""
    m = _HEX.fullmatch(value.strip())
    if not m:
        return None
    h = m.group(1)
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def read_colours(style: str) -> dict[str, tuple[int, int, int]] | None:
    """The three colours of a `style` attribute, or None when any of them is missing or is not `#rgb` / `#rrggbb`. A property written twice takes its last
    value, as CSS does; a name is exact (`--d-paper-dark` is another property)."""
    declared: dict[str, str] = {}
    for part in style.split(";"):
        name, sep, value = part.partition(":")
        if sep:
            declared[name.strip()] = value.strip()
    out = {}
    for prop in PROPERTIES:
        rgb = parse_hex(declared.get(prop, ""))
        if rgb is None:
            return None
        out[prop] = rgb
    return out


def _linear(c: int) -> float:
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def oklab(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
    """sRGB (0 to 255) to OKLab (Ottosson's matrices): white is (1, 0, 0), black is (0, 0, 0)."""
    r, g, b = (_linear(v) for v in rgb)
    l_ = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    m_ = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    s_ = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return (0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
            1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
            0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_)


def distance(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    """The OKLab distance of two sRGB colours."""
    return sum((x - y) ** 2 for x, y in zip(oklab(a), oklab(b))) ** 0.5


def row(directions: list[tuple[str, str]]) -> tuple[str, str]:
    """The `directions:divergence` row of a pick board as (status, detail). `directions` is one (name, style attribute) per direction, in board order."""
    measured = [(name, colours) for name, style in directions if (colours := read_colours(style))]
    if len(measured) < 2:
        return "info", (f"not measured: {len(measured)} of {len(directions)} direction(s) carry {', '.join(PROPERTIES)} as #rgb or #rrggbb in their style attribute; "
                        f"two are needed to compare them. {PROPOSAL}")
    pairs = []   # (first name, second name, paper, ink, accent distances)
    for (na, ca), (nb, cb) in combinations(measured, 2):
        pairs.append((na, nb, *(distance(ca[p], cb[p]) for p in PROPERTIES)))
    alike = [p for p in pairs if p[2] <= PAPER_INK and p[3] <= PAPER_INK and p[4] <= ACCENT]
    if alike:
        named = "; ".join(f"{a!r} and {b!r} look alike in colour (paper {dp:.3f}, ink {di:.3f}, accent {da:.3f})" for a, b, dp, di, da in alike)
        return "warn", f"{named}. Move the paper, the ink or the accent of one of them away from the other so the owner can tell them apart. {PROPOSAL}"
    smallest = []
    for i, prop in enumerate(PROPERTIES):
        a, b, *d = min(pairs, key=lambda p: p[2 + i])
        smallest.append(f"{prop[4:]} {d[i]:.3f} ({a}, {b})")
    return "pass", f"{len(measured)} directions compared; smallest distance between two of them: {', '.join(smallest)}. {PROPOSAL}"
