"""Measurements of a mark's artwork shared by logo-sheet and board-lint.

ground_contacts: which flat colours of the artwork touch the ground. A pixel drawing (svgtools.pixel_grid) is read cell by cell:
a cell touches the ground along a side it shares with a clear cell or with the edge of the drawing (two cells that meet only at
a corner of a stair step do not touch). Any other drawing is read from a 512 px render as `contrast` finds its touching pairs
(lib/touching.py). Either way a face inside an outline does not touch the ground, and a fill that runs off the drawing's own
edge does.
outline_width: for a pixel drawing (svgtools.pixel_grid), the colour that meets the ground most and how many pixels deep it
runs inward from the ground, the most common depth over every place it meets the ground.
"""
from __future__ import annotations

import json
from pathlib import Path

import svgtools
from _color import parse_hex, wcag_ratio
from _common import EXIT_USAGE, fail, rasterise_svg
from pxio import read_png
from touching import analyse

RASTER, MARGIN = 512, 8
NOT_FLAT = ("linearGradient", "radialGradient", "pattern", "filter", "mask", "image")  # paint that is not a flat fill


def load_json(path: Path, what: str) -> dict:
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        fail(EXIT_USAGE, f"{path.name}: cannot read {what} ({e})")
    if not isinstance(doc, dict):
        fail(EXIT_USAGE, f"{path.name}: {what} must be a JSON object")
    return doc


def load_exceptions(path: Path) -> list[dict]:
    """tokens/exceptions.json: the owner's accepted contrast misses, each with a reason (`contrast` and `logo-sheet` read it)."""
    if not path.is_file():
        return []
    items = load_json(path, "the exceptions register").get("exceptions")
    if not isinstance(items, list):
        fail(EXIT_USAGE, f"{path.name}: needs an \"exceptions\" list")
    out = []
    for i, e in enumerate(items):
        ok = isinstance(e, dict) and all(isinstance(e.get(k), str) and e[k].strip() for k in ("a", "b", "reason"))
        if not ok:
            fail(EXIT_USAGE, f"{path.name}: exceptions[{i}] needs a, b and a non-empty reason (why this miss is accepted)")
        mode = e.get("mode", "*")
        if mode not in ("light", "dark", "*"):
            fail(EXIT_USAGE, f"{path.name}: exceptions[{i}].mode must be light, dark or *, got {mode!r}")
        out.append({"a": e["a"].strip().lower(), "b": e["b"].strip().lower(), "mode": mode, "reason": e["reason"].strip(), "used": False})
    return out


def names_of(tj: dict, mode: str, hexv: str) -> list[str]:
    """Token roles (semantic first, then primitives) whose resolved colour is hexv, plus hexv itself."""
    sem = sorted(k for k, v in tj["modes"][mode].items() if v["hex"].lower() == hexv)
    prim = sorted(k for k, v in tj["primitives"].items() if v["hex"].lower() == hexv)
    return sem + prim + [hexv]


def matches(rule_a: str, rule_b: str, na: list[str], nb: list[str]) -> bool:
    ra, rb = rule_a.lower(), rule_b.lower()
    return (ra in na and rb in nb) or (ra in nb and rb in na)


def ground_target(project: Path) -> tuple[float, str]:
    """The contrast a colour needs against the ground: touching.ground of the built tokens, else 3:1. -> (value, where from)."""
    f = project / "assets" / "tokens" / "tokens.json"
    if f.is_file():
        try:
            v = (json.loads(f.read_text(encoding="utf-8")).get("touching") or {}).get("ground")
            if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0:
                return float(v), "touching.ground in the tokens"
        except ValueError:
            pass
    return 3.0, "the default 3:1"


def edge_strength(png: bytes, ground: str) -> float | None:
    """How strongly a rendered tile stands off its ground at its edge: the highest contrast among the mark's pixels within 2 px of
    a clear pixel or of the tile's border, each composited on the ground. A solid shape reaches its own colour's contrast; a
    hairline that never covers a whole pixel at this size reaches far less. None when the tile has no ink."""
    w, h, px = read_png(png)
    g = parse_hex(ground)
    clear = [[px[(y * w + x) * 4 + 3] == 0 for x in range(w)] for y in range(h)]
    near = [[x < 2 or y < 2 or x >= w - 2 or y >= h - 2 for x in range(w)] for y in range(h)]
    for _ in range(2):   # grow the clear area by one pixel, twice (8-neighbour)
        grown = [row[:] for row in clear]
        for y in range(h):
            for x in range(w):
                if clear[y][x]:
                    for yy in range(max(0, y - 1), min(h, y + 2)):
                        for xx in range(max(0, x - 1), min(w, x + 2)):
                            grown[yy][xx] = True
        clear = grown
    best = None
    for y in range(h):
        for x in range(w):
            i = (y * w + x) * 4
            a = px[i + 3]
            if not a or not (clear[y][x] or near[y][x]):
                continue
            c = tuple((px[i + k] * a + g[k] * (255 - a)) / 255 for k in range(3))
            r = wcag_ratio(c, g)
            best = r if best is None or r > best else best
    return round(best, 2) if best is not None else None


def ground_contacts(svg_text: str, renderer: str = "resvg") -> dict | None:
    """{hex: contact length} of the flat colours that touch the ground (for a pixel drawing, the number of cell sides), or None
    for artwork with non-flat paint (a gradient bands into false flat colours, so its contacts would be wrong rather than merely
    missing)."""
    for el in svgtools.parse(svg_text).iter():
        if el.tag.split("}")[-1] in NOT_FLAT:
            return None
    grid = svgtools.pixel_grid(svg_text)
    if grid:
        cells, n = _cells(svg_text, grid, renderer), grid
        out: dict[str, int] = {}
        for y in range(n):
            for x in range(n):
                c = cells[y][x]
                if c is None:
                    continue
                sides = sum(1 for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                            if not (0 <= x + dx < n and 0 <= y + dy < n) or cells[y + dy][x + dx] is None)
                if sides:
                    out[c] = out.get(c, 0) + sides
        return out
    fitted = svgtools.fit(svg_text, RASTER, RASTER, box=(RASTER - 2 * MARGIN, RASTER - 2 * MARGIN))
    return analyse(rasterise_svg(fitted, RASTER, RASTER, renderer=renderer))["ground"]


def outline_width(svg_text: str, renderer: str = "resvg") -> dict | None:
    """{"grid": N, "colour": hex or None, "width": px or None, "samples": n, "why": None or the reason there is no width} for a
    pixel drawing, None for any other drawing.

    The drawing is rendered at exactly one pixel per grid cell. Every opaque pixel with a transparent neighbour (left, right,
    above or below; the canvas edge is not ground, so a strap that runs off the drawing is not an outline) is a sample: the
    run of its own colour from it inward, away from that neighbour. The outline colour is the colour of most samples, and its
    width the most common run among them that ends at another colour (the smaller on a tie); a run that crosses the whole shape
    to the ground again is a silhouette's thickness, not an outline's."""
    grid = svgtools.pixel_grid(svg_text)
    if not grid:
        return None
    cells = _cells(svg_text, grid, renderer)
    w = h = grid

    def at(x: int, y: int) -> str | None:
        return cells[y][x]

    runs: dict[str, list[int]] = {}
    for y in range(h):
        for x in range(w):
            c = at(x, y)
            if c is None:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if not (0 <= nx < w and 0 <= ny < h) or at(nx, ny) is not None:
                    continue
                n, xx, yy = 0, x, y
                while 0 <= xx < w and 0 <= yy < h and at(xx, yy) == c:
                    n += 1
                    xx, yy = xx - dx, yy - dy
                behind = at(xx, yy) if 0 <= xx < w and 0 <= yy < h else None
                runs.setdefault(c, []).append((n, behind is not None))
    if not runs:
        return {"grid": grid, "colour": None, "width": None, "samples": 0, "why": "no clear cell around the drawing"}
    colour, samples = max(sorted(runs.items()), key=lambda kv: len(kv[1]))   # a tie goes to the lower hex, every run alike
    inner = [n for n, has_behind in samples if has_behind]   # an outline has another colour behind it; a silhouette has none
    if not inner:
        return {"grid": grid, "colour": colour, "width": None, "samples": len(samples),
                "why": f"a silhouette: nothing else lies behind its edge colour {colour}"}
    counts: dict[int, int] = {}
    for n in inner:
        counts[n] = counts.get(n, 0) + 1
    width = min(counts, key=lambda n: (-counts[n], n))
    return {"grid": grid, "colour": colour, "width": width, "samples": len(inner), "why": None}


def _cells(svg_text: str, grid: int, renderer: str) -> list[list[str | None]]:
    """The drawing rendered at one pixel per cell: rows of '#rrggbb', or None for a clear cell."""
    svg, _ = svgtools.place_whole(svg_text, grid)
    w, h, px = read_png(rasterise_svg(svg, grid, grid, renderer=renderer))
    return [[None if px[(y * w + x) * 4 + 3] == 0 else "#%02x%02x%02x" % tuple(px[(y * w + x) * 4:(y * w + x) * 4 + 3])
             for x in range(w)] for y in range(h)]


def tokens_ground(project: Path, mode: str, default: str) -> str:
    """color.bg of the built tokens in `mode`, else `default`."""
    f = project / "assets" / "tokens" / "tokens.json"
    if f.is_file():
        try:
            return json.loads(f.read_text())["modes"][mode]["color.bg"]["hex"]
        except (ValueError, KeyError):
            return default
    return default
