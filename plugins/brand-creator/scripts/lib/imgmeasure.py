"""Pixel measurements shared by the QA checks (downscale, states, family, guides). Standard library only.

Images are (w, h, RGBA bytearray) as returned by pxio.read_png.
"""
from __future__ import annotations

from _color import parse_hex

Raster = tuple  # (w, h, bytearray)


def over(raster: Raster, ground: str | tuple) -> Raster:
    """Composite an RGBA raster over a flat ground colour; the result is fully opaque."""
    w, h, px = raster
    g = parse_hex(ground) if isinstance(ground, str) else tuple(ground[:3])
    out = bytearray(len(px))
    for i in range(0, len(px), 4):
        a = px[i + 3]
        for k in range(3):
            out[i + k] = (px[i + k] * a + g[k] * (255 - a) + 127) // 255
        out[i + 3] = 255
    return w, h, out


def luma(r: int, g: int, b: int) -> float:
    """Rec. 709 luma on the 0..255 scale (greyscale of an sRGB pixel, gamma-encoded as shown on a screen)."""
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def accent_mask(raster: Raster, accent: str | tuple, tolerance: float, ground: str | tuple) -> list[bool]:
    """True for pixels whose colour, composited over the ground, is within `tolerance` (RGB distance) of the accent."""
    w, h, px = over(raster, ground)
    a = parse_hex(accent) if isinstance(accent, str) else tuple(accent[:3])
    t2 = tolerance * tolerance
    return [((px[i] - a[0]) ** 2 + (px[i + 1] - a[1]) ** 2 + (px[i + 2] - a[2]) ** 2) <= t2 for i in range(0, len(px), 4)]


def largest_square(mask: list[bool], w: int, h: int) -> int:
    """Side of the largest all-True axis-aligned square (dynamic programming)."""
    best = 0
    prev = [0] * (w + 1)
    for y in range(h):
        cur = [0] * (w + 1)
        for x in range(w):
            if mask[y * w + x]:
                cur[x + 1] = min(prev[x], prev[x + 1], cur[x]) + 1
                best = max(best, cur[x + 1])
        prev = cur
    return best


def mask_bbox(mask: list[bool], w: int, h: int):
    """(x0, y0, x1, y1) inclusive of the True cells, or None."""
    xs = [i % w for i, v in enumerate(mask) if v]
    ys = [i // w for i, v in enumerate(mask) if v]
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


def alpha_mask(raster: Raster, threshold: int = 128) -> list[bool]:
    w, h, px = raster
    return [px[i + 3] >= threshold for i in range(0, len(px), 4)]


def ink_mask(raster: Raster, ground: str | tuple, tolerance: float = 24) -> list[bool]:
    """True where the pixel is visibly different from the ground (alpha-aware): the mark's ink on that ground."""
    w, h, px = raster
    g = parse_hex(ground) if isinstance(ground, str) else tuple(ground[:3])
    flat = over(raster, g)[2]
    t2 = tolerance * tolerance
    return [((flat[i] - g[0]) ** 2 + (flat[i + 1] - g[1]) ** 2 + (flat[i + 2] - g[2]) ** 2) > t2 for i in range(0, len(flat), 4)]


def diff_ratio(a: list[bool], b: list[bool]) -> float:
    """Pixels where the two masks differ divided by pixels set in either (0 = identical, 1 = disjoint)."""
    if len(a) != len(b):
        raise ValueError("masks differ in size")
    union = sum(1 for x, y in zip(a, b) if x or y)
    if union == 0:
        return 0.0
    return sum(1 for x, y in zip(a, b) if x != y) / union


def grey_diff_ratio(a: Raster, b: Raster, ground: str | tuple, tol: float = 16.0) -> float:
    """Share of the ink pixels of either image (against the ground) whose greyscale differs by more than tol (0..255)."""
    if a[:2] != b[:2]:
        raise ValueError("images differ in size")
    fa, fb = over(a, ground)[2], over(b, ground)[2]
    ia, ib = ink_mask(a, ground), ink_mask(b, ground)
    n = d = 0
    for k in range(a[0] * a[1]):
        if ia[k] or ib[k]:
            n += 1
            if abs(luma(*fa[k * 4:k * 4 + 3]) - luma(*fb[k * 4:k * 4 + 3])) > tol:
                d += 1
    return d / n if n else 0.0
