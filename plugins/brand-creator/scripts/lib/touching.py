"""Which flat colours of a rasterised mark really touch each other, and which touch the ground (standard library only).

Input is a PNG with a transparent background, rendered by resvg from the SVG. Every pixel is put in one class:

  ground    alpha 0
  blended   partial alpha, or an opaque pixel whose 3x3 neighbourhood is not one colour (an anti-aliased edge)
  solid     an opaque pixel whose 3x3 neighbourhood is one colour: that colour is a flat fill of the artwork

Two classes touch when a pixel of one has a pixel of the other within four pixels in a straight or diagonal line and
only blended pixels lie between them (so the one-pixel anti-aliased seam between two fills counts, a gap of ground
does not). The count of such pixel pairs is the contact length; contacts below MIN_CONTACT are noise and dropped.
Callers fit the mark into the canvas with a margin, so the image border is always ground.
"""
from __future__ import annotations

from pxio import read_png

GROUND = -1
BLENDED = -2
MIN_SOLID_PIXELS = 20   # a colour with fewer interior pixels is an anti-aliasing coincidence, not a fill
MIN_CONTACT = 6         # fewer touching pixel pairs than this is noise
REACH = 4               # interior pixels of two fills are up to 4 apart across a one-pixel anti-aliased seam


def hex_of(key: int) -> str:
    return "#%06x" % key


def analyse(png: bytes) -> dict:
    """-> {"colours": {hex: interior pixel count}, "contacts": {(hex_a, hex_b): n}, "ground": {hex: n}, "size": (w, h)}.

    A pair key is sorted; contacts with the ground are in "ground" (hex -> contact length), not in "contacts"."""
    w, h, px = read_png(png)
    n = w * h
    key = [GROUND] * n
    for i in range(n):
        a = px[4 * i + 3]
        if a == 255:
            key[i] = (px[4 * i] << 16) | (px[4 * i + 1] << 8) | px[4 * i + 2]
        elif a:
            key[i] = BLENDED
    cls = list(key)
    counts: dict[int, int] = {}
    for y in range(1, h - 1):
        row = y * w
        for x in range(1, w - 1):
            i = row + x
            k = key[i]
            if k < 0:
                continue
            if (key[i - 1] == k and key[i + 1] == k and key[i - w] == k and key[i + w] == k
                    and key[i - w - 1] == k and key[i - w + 1] == k and key[i + w - 1] == k and key[i + w + 1] == k):
                counts[k] = counts.get(k, 0) + 1
            else:
                cls[i] = BLENDED
    # opaque border pixels (the caller leaves a margin, so there should be none) are not interior
    for i in list(range(w)) + list(range((h - 1) * w, n)) + list(range(0, n, w)) + list(range(w - 1, n, w)):
        if cls[i] >= 0:
            cls[i] = BLENDED
    keep = {k for k, c in counts.items() if c >= MIN_SOLID_PIXELS}
    for i in range(n):
        if cls[i] >= 0 and cls[i] not in keep:
            cls[i] = BLENDED

    touch: dict[tuple[int, int], int] = {}
    for y in range(h):
        row = y * w
        for x in range(w):
            a = cls[row + x]
            if a == BLENDED:
                continue
            for dx, dy in ((1, 0), (0, 1), (1, 1), (-1, 1)):
                for d in range(1, REACH + 1):
                    xx, yy = x + dx * d, y + dy * d
                    if not (0 <= xx < w and 0 <= yy < h):
                        break
                    b = cls[yy * w + xx]
                    if b == BLENDED:
                        continue
                    if b != a:
                        pair = (a, b) if a < b else (b, a)
                        touch[pair] = touch.get(pair, 0) + 1
                    break
    colours = {hex_of(k): counts[k] for k in sorted(keep)}
    contacts: dict[tuple[str, str], int] = {}
    ground: dict[str, int] = {}
    for (a, b), c in touch.items():
        if c < MIN_CONTACT:
            continue
        if a == GROUND:
            ground[hex_of(b)] = c
        else:
            contacts[(hex_of(a), hex_of(b))] = c
    return {"colours": colours, "contacts": contacts, "ground": ground, "size": (w, h)}
