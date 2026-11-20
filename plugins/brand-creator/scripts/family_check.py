#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator family-check: a family keeps its shared letters identical and its tiles in proportion.

Family modes only (architecture family-member, product-in-family or family-parent in BRAND-STATE.md); a standalone brand has
nothing to compare and the command says so. It reads the machine-readable block of FAMILY.md (template: templates/FAMILY.md):
  * shared glyphs: every name in glyphs.shared must be equal in the family's source and in this product's source. A glyph is
    cells (row strings, or rows of 0 and 1) or polygons (a list of closed contours, each a list of at least three [x, y]
    numbers, filled even-odd). Cells compare cell for cell; polygons compare point for point (exact) or, for shape, both
    are moved to 0,0, scaled so the longer side of their ink box is 1, filled at POLY_PX px and must not differ in more
    than 1 pixel in 1000. Sources are read, never executed: a .py file is parsed with ast.literal_eval of the named
    assignment, a .json file is parsed as JSON. Reusing a family letter means copying it, never redrawing it.
    A family-parent owns the family's source: glyphs.own is optional there, and without it every shared glyph must be
    defined in the family source.
  * tile share: for each product mark the share of the tile its ink covers and the height of the ink's bounding box,
    which must agree across products within the tolerance (qa/rules.json family.tile_share_tolerance, proposal 0.05).
A source that cannot be read (a sibling repository that is not checked out) makes the check "not verified" (exit 3).
"""
import ast
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))
import qa_rules  # noqa: E402
import svgtools  # noqa: E402
from _common import (EXIT_USAGE, Parser, Report, add_project_arg, add_renderer_arg, fail, find_project, main_guard,  # noqa: E402
                     rasterise_svg, read_state)
from pxio import read_png  # noqa: E402

FAMILY_MODES = ("family-member", "product-in-family", "family-parent")
POLY_PX = 128              # polygon glyphs are filled at this many px on the longer side of their ink box (shape compare)
POLY_TOLERANCE = 1 / 1000  # the share of those pixels that may differ (edge pixels a float rounding can flip)
BLOCK = re.compile(r"```json\s+family-check\s*\n(.*?)\n```", re.S)
EMPTY = set(". _0")
RASTER = 256


class SourceError(Exception):
    pass


def read_block(f: Path) -> dict:
    m = BLOCK.search(f.read_text(encoding="utf-8"))
    if not m:
        fail(EXIT_USAGE, f"{f.name} has no ```json family-check block (template: templates/FAMILY.md)")
    if "[[fill:" in m.group(1):
        fail(EXIT_USAGE, f"{f.name}: the family-check block still has [[fill: ...]] markers")
    try:
        doc = json.loads(m.group(1))
    except ValueError as e:
        fail(EXIT_USAGE, f"{f.name}: the family-check block is not valid JSON ({e})")
    if doc.get("schema") != 1:
        fail(EXIT_USAGE, f"{f.name}: the family-check block needs \"schema\": 1")
    return doc


def read_symbol(base: Path, spec: dict, what: str) -> dict:
    """The glyph map named by spec = {file, symbol}, read without executing anything."""
    if not (isinstance(spec, dict) and isinstance(spec.get("file"), str)):
        fail(EXIT_USAGE, f"glyphs.{what} needs {{\"file\": ..., \"symbol\": ...}}")
    f = (base / spec["file"]).resolve()
    if not f.is_file():
        raise SourceError(f"{what} glyph source not found: {spec['file']} (resolved to {f})")
    sym = spec.get("symbol")
    if f.suffix == ".py":
        if not sym:
            fail(EXIT_USAGE, f"glyphs.{what}: a .py source needs a symbol")
        tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f))
        for node in tree.body:
            targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
            if any(isinstance(t, ast.Name) and t.id == sym for t in targets) and node.value is not None:
                try:
                    val = ast.literal_eval(node.value)
                except ValueError as e:
                    raise SourceError(f"{spec['file']}: {sym} is not a literal ({e}); the check never executes code, so write the glyph cells as a plain literal")
                break
        else:
            raise SourceError(f"{spec['file']}: no top-level assignment to {sym}")
    elif f.suffix == ".json":
        val = json.loads(f.read_text(encoding="utf-8"))
        for part in (sym.split(".") if sym else []):
            if not isinstance(val, dict) or part not in val:
                raise SourceError(f"{spec['file']}: no key {sym}")
            val = val[part]
    else:
        fail(EXIT_USAGE, f"glyphs.{what}: the source must be a .py or .json file, got {f.name}")
    if not isinstance(val, dict):
        raise SourceError(f"{spec['file']}: {sym or 'the document'} must map glyph names to cells")
    return val


def _number(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def glyph_kind(name: str, g, where: str) -> str:
    """cells or polygons; a polygon glyph whose contour is not at least three [x, y] number pairs is exit 2, named."""
    if not (isinstance(g, (list, tuple)) and g and all(isinstance(c, (list, tuple)) for c in g)
            and any(c and isinstance(c[0], (list, tuple)) for c in g)):
        return "cells"
    for i, c in enumerate(g):
        if len(c) < 3 or not all(isinstance(pt, (list, tuple)) and len(pt) == 2 and all(_number(v) for v in pt) for pt in c):
            fail(EXIT_USAGE, f"glyph {name} in {where}: contour {i} must be a list of at least three [x, y] number pairs")
    return "polygons"


def poly_raster(contours) -> list[list[bool]]:
    """The contours moved to 0,0 and scaled so the longer side of their ink box is POLY_PX px, filled even-odd at pixel centres."""
    pts = [(float(x), float(y)) for c in contours for x, y in c]
    x0, y0 = min(p[0] for p in pts), min(p[1] for p in pts)
    side = max(max(p[0] for p in pts) - x0, max(p[1] for p in pts) - y0) or 1.0
    k = POLY_PX / side
    rings = [[((float(x) - x0) * k, (float(y) - y0) * k) for x, y in c] for c in contours]
    w = max(1, round(max(p[0] for r in rings for p in r)))
    h = max(1, round(max(p[1] for r in rings for p in r)))
    grid = []
    for j in range(h):
        yc = j + 0.5
        xs = []
        for r in rings:
            for (ax, ay), (bx, by) in zip(r, r[1:] + r[:1]):
                if (ay <= yc < by) or (by <= yc < ay):
                    xs.append(ax + (yc - ay) * (bx - ax) / (by - ay))
        xs.sort()
        row = [False] * w
        for a, b in zip(xs[0::2], xs[1::2]):
            for i in range(max(0, int(a + 0.5)), min(w, int(b + 0.5))):   # pixel i's centre i+0.5 lies in [a, b)
                row[i] = True
        grid.append(row)
    return grid


def poly_difference(a, b, exact: bool):
    if exact:
        fa = [[(float(x), float(y)) for x, y in c] for c in a]
        fb = [[(float(x), float(y)) for x, y in c] for c in b]
        if len(fa) != len(fb):
            return f"{len(fa)} vs {len(fb)} contours"
        for i, (ca, cb) in enumerate(zip(fa, fb)):
            if len(ca) != len(cb):
                return f"contour {i} has {len(ca)} vs {len(cb)} points"
            for j, (pa, pb) in enumerate(zip(ca, cb)):
                if pa != pb:
                    return f"contour {i}, point {j} differs ({pa[0]:g}, {pa[1]:g} vs {pb[0]:g}, {pb[1]:g})"
        return None
    ra, rb = poly_raster(a), poly_raster(b)
    h, w = max(len(ra), len(rb)), max(len(ra[0]), len(rb[0]))
    cell = (lambda g, y, x: y < len(g) and x < len(g[0]) and g[y][x])
    n = sum(1 for y in range(h) for x in range(w) if cell(ra, y, x) != cell(rb, y, x))
    return f"{n} pixel(s) of {w * h} differ, filled at {POLY_PX} px" if n > POLY_TOLERANCE * w * h else None


def normalise(cells, exact: bool) -> list[list[str]]:
    rows = []
    for r in cells:
        if isinstance(r, str):
            rows.append([c if exact else ("." if c in EMPTY else "#") for c in r])
        else:
            rows.append([("." if not v else "#") if not exact else str(v) for v in r])
    return rows


def first_difference(a: list[list[str]], b: list[list[str]]):
    if len(a) != len(b) or any(len(x) != len(y) for x, y in zip(a, b)):
        return f"size differs: {len(a[0]) if a else 0}x{len(a)} vs {len(b[0]) if b else 0}x{len(b)} cells"
    diff = [(y, x) for y, (ra, rb) in enumerate(zip(a, b)) for x, (ca, cb) in enumerate(zip(ra, rb)) if ca != cb]
    return f"{len(diff)} cell(s) differ, the first at row {diff[0][0]}, column {diff[0][1]}" if diff else None


def tile_measure(path: Path, renderer: str) -> dict:
    if path.suffix.lower() == ".svg":
        text = path.read_text(encoding="utf-8")
        w = h = RASTER
        w, h, px = read_png(rasterise_svg(svgtools.fit(text, w, h), w, h, renderer=renderer))
    elif path.suffix.lower() == ".png":
        w, h, px = read_png(path.read_bytes())
    else:
        fail(EXIT_USAGE, f"{path.name}: tile marks are .svg or .png files")
    counts: dict[tuple, int] = {}  # the ground is the most frequent colour on the image's edge (a mark that fills most of the tile
    for k in range(w * h):         # must not be mistaken for its own ground, which a count over all pixels would do)
        x, y = k % w, k // w
        if x in (0, w - 1) or y in (0, h - 1):
            c = tuple(px[k * 4:k * 4 + 4]) if px[k * 4 + 3] else (0, 0, 0, 0)
            counts[c] = counts.get(c, 0) + 1
    ground = max(counts, key=counts.get)
    xs, ys, n = [], [], 0
    for k in range(w * h):
        c = tuple(px[k * 4:k * 4 + 4]) if px[k * 4 + 3] else (0, 0, 0, 0)
        if sum(abs(c[j] - ground[j]) for j in range(4)) > 48:
            n += 1
            xs.append(k % w)
            ys.append(k // w)
    if not n:
        return {"share": 0.0, "bbox_height": 0.0, "size": [w, h]}
    return {"share": round(n / (w * h), 4), "bbox_height": round((max(ys) - min(ys) + 1) / h, 4),
            "bbox_width": round((max(xs) - min(xs) + 1) / w, 4), "size": [w, h]}


def main() -> int:
    ap = Parser(prog="brand-creator family-check", description=__doc__, formatter_class=__import__("argparse").RawDescriptionHelpFormatter)
    add_project_arg(ap)
    add_renderer_arg(ap)
    ap.add_argument("--family", help="FAMILY.md (default: BRAND-STATE family_file, else FAMILY.md in the project)")
    a = ap.parse_args()
    project = find_project(a.project)
    st = read_state(project).data()
    rep = Report("family", project, [], renderer=f"{a.renderer} (SVG tiles only)")
    arch = str(st.get("architecture", "standalone"))
    if arch not in FAMILY_MODES:
        rep.add("family:applies", "info", "family modes only", detail=f"architecture is {arch}: no family to compare against, nothing was checked")
        return rep.finish()
    fam = Path(a.family) if a.family else Path(str(st.get("family_file") or "FAMILY.md"))
    fam = (fam if fam.is_absolute() else project / fam).resolve()
    if not fam.is_file():
        fail(EXIT_USAGE, f"architecture is {arch} but there is no FAMILY.md ({fam}); copy templates/FAMILY.md, fill it in, or pass --family")
    doc = read_block(fam)
    rules, rules_src = qa_rules.load(project)
    base = fam.parent
    rep.inputs = [fam, project / qa_rules.RULES_FILE]
    rep.extra = {"family": doc.get("family"), "family_file": str(fam.relative_to(project)) if fam.is_relative_to(project) else str(fam),
                 "architecture": arch, "rules_source": rules_src}
    g = doc.get("glyphs")
    if g:
        shared = g.get("shared") or []
        exact = g.get("compare", "shape") == "exact"
        if g.get("compare", "shape") not in ("shape", "exact"):
            fail(EXIT_USAGE, "glyphs.compare must be shape or exact")
        own_given = arch != "family-parent" or g.get("own") is not None   # the parent owns the family source; its own one is optional
        try:
            fam_src = read_symbol(base, g.get("family"), "family")
            own_src = read_symbol(base, g.get("own"), "own") if own_given else None
            rep.inputs += [(base / g["family"]["file"]).resolve()] + ([(base / g["own"]["file"]).resolve()] if own_given else [])
        except SourceError as e:
            rep.add("glyphs:sources", "skipped", "shared glyphs", detail=f"not verified: {e}")
            shared = []
        for name in shared:
            if name not in fam_src or (own_src is not None and name not in own_src):
                where = "the family source" if name not in fam_src else "this product's source"
                rep.add(f"glyph:{name}", "fail", "shared glyph equals the family's", detail=f"{name} is missing from {where}")
                continue
            kf = glyph_kind(name, fam_src[name], g["family"]["file"])
            if own_src is None:
                rep.add(f"glyph:{name}", "pass", "shared glyph is defined in the family source", detail=f"{name}: defined in the family source ({kf})")
                continue
            ko = glyph_kind(name, own_src[name], g["own"]["file"])
            if kf != ko:
                d = f"the family source draws it as {kf}, this product's as {ko}"
            elif kf == "polygons":
                d = poly_difference(fam_src[name], own_src[name], exact)
            else:
                d = first_difference(normalise(fam_src[name], exact), normalise(own_src[name], exact))
            same = "cell-equal" if kf == "cells" else ("point-equal" if exact else "the same shape")
            rep.add(f"glyph:{name}", "fail" if d else "pass", "shared glyph equals the family's",
                    detail=(f"{name}: {d}. Copy the family's glyph; never redraw a shared glyph." if d else f"{name}: {same} as the family source"))
        if not shared and not any(r["id"] == "glyphs:sources" for r in rep.results):
            rep.add("glyphs", "info", "shared glyphs", detail="glyphs.shared is empty: nothing to compare")
    tiles = doc.get("tiles") or []
    if tiles:
        tol = float(doc.get("tile_share_tolerance", rules["family"]["tile_share_tolerance"]))
        got = {}
        for t in tiles:
            if not (isinstance(t, dict) and isinstance(t.get("product"), str) and isinstance(t.get("mark"), str)):
                fail(EXIT_USAGE, "each tiles entry needs a product and a mark")
            f = (base / t["mark"]).resolve()
            if not f.is_file():
                rep.add(f"tile:{t['product']}", "skipped", "tile share", detail=f"not verified: mark not found: {t['mark']}")
                continue
            rep.inputs.append(f)
            got[t["product"]] = tile_measure(f, a.renderer)
            m = got[t["product"]]
            rep.add(f"tile:{t['product']}", "info", "tile share", detail=f"ink covers {m['share']:.1%} of the tile, its box is {m['bbox_height']:.1%} high", **m)
        if len(got) >= 2:
            for key, label in (("share", "ink share of the tile"), ("bbox_height", "height of the ink box")):
                vals = [m[key] for m in got.values()]
                spread = max(vals) - min(vals)
                rep.add(f"tiles:{key}", "pass" if spread <= tol else "fail", f"{label} agrees across products (tolerance {tol:g}, {rules_src if 'tile_share_tolerance' not in doc else 'FAMILY.md'})",
                        detail=f"{', '.join(f'{p} {m[key]:.3f}' for p, m in got.items())}: spread {spread:.3f}" + ("" if spread <= tol else f" exceeds {tol:g}"), spread=round(spread, 4))
        elif not any(r["status"] == "skipped" for r in rep.results):
            rep.add("tiles", "info", "tile share", detail="fewer than two products listed: nothing to compare")
    if not g and not tiles:
        rep.add("family-check", "info", "FAMILY.md block", detail="the block declares neither glyphs nor tiles: nothing to check")
    return rep.finish()


main_guard(main)
