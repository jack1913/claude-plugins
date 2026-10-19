#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = ["fonttools==4.62.1", "skia-pathops==0.9.2"]
# ///
"""brand-creator outline-glyphs: turn a line of text in a font into SVG paths, so a mark never carries live text.

Pipeline: fontTools instancer pins every variable axis (the ones you pass, the font's default for the rest) ->
skia-pathops removes overlaps (variable fonts draw glyphs as overlapping contours, which show as seams and double
edges in print and with transparency) -> fontTools SVGPathPen writes the outlines. The SVG has one <path> per glyph, no
<text>, no font reference, and carries its metrics as data-* attributes (data-baseline, data-cap-height,
data-x-height, in viewBox units) that `logo-sheet --guides` draws. Check the font's licence first
(`brand-creator fontcheck`): outlines of an OFL font are fine; a font that forbids embedding is not.

Layout is the font's advance widths plus --tracking and manual --pair adjustments (units of the font's em, scaled with
the text). The font's GPOS kerning is NOT applied: set the pairs that matter by eye (AV=-60), the way a logo is kerned.
Writes only inside the project and only when the bytes change.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))
from _common import (EXIT_FAIL, EXIT_USAGE, Parser, add_project_arg, confine, fail, find_project, main_guard, rel,  # noqa: E402
                     write_bytes_if_changed)
from _color import parse_hex  # noqa: E402
from mark_lint import lint_svg_text  # noqa: E402


def fmt(v: float) -> str:
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def parse_axes(items: list[str]) -> dict[str, float]:
    out = {}
    for it in items:
        tag, eq, val = it.partition("=")
        if not eq or len(tag) != 4:
            fail(EXIT_USAGE, f"--axis needs TAG=VALUE with a four-letter tag (wght=700), got {it!r}")
        try:
            out[tag] = float(val)
        except ValueError:
            fail(EXIT_USAGE, f"--axis {it!r}: {val!r} is not a number")
    return out


def parse_pairs(items: list[str]) -> dict[str, float]:
    out = {}
    for it in items:
        pair, eq, val = it.partition("=")
        if not eq or len(pair) != 2:
            fail(EXIT_USAGE, f"--pair needs two characters, =, and a number (AV=-60), got {it!r}")
        try:
            out[pair] = float(val)
        except ValueError:
            fail(EXIT_USAGE, f"--pair {it!r}: {val!r} is not a number")
    return out


def instance(font, axes: dict[str, float]):
    from fontTools.varLib import instancer
    if "fvar" not in font:
        if axes:
            fail(EXIT_USAGE, f"the font is static (no fvar table) but --axis was given: {', '.join(axes)}")
        return font, {}
    have = {a.axisTag: a for a in font["fvar"].axes}
    unknown = sorted(set(axes) - set(have))
    if unknown:
        fail(EXIT_USAGE, f"the font has no axis {', '.join(unknown)}; it has: " + ", ".join(f"{t} ({a.minValue:g}..{a.maxValue:g}, default {a.defaultValue:g})" for t, a in have.items()))
    limits = {}
    for tag, ax in have.items():
        v = axes.get(tag, ax.defaultValue)
        if not ax.minValue <= v <= ax.maxValue:
            fail(EXIT_USAGE, f"--axis {tag}={v:g} is outside the font's range {ax.minValue:g}..{ax.maxValue:g}")
        limits[tag] = v
    return instancer.instantiateVariableFont(font, limits, inplace=False), limits


def main() -> int:
    ap = Parser(prog="brand-creator outline-glyphs", description=__doc__, formatter_class=__import__("argparse").RawDescriptionHelpFormatter)
    add_project_arg(ap)
    ap.add_argument("--font", required=True, help="TTF or OTF file (static or variable); may live outside the project (read only)")
    ap.add_argument("--text", help="the line to outline")
    ap.add_argument("--axis", action="append", default=[], metavar="TAG=VALUE", help="pin a variable axis (repeatable); other axes use the font's default")
    ap.add_argument("--info", action="store_true", help="print the font's name, axes and metrics, then stop")
    ap.add_argument("--em", type=float, default=100.0, help="size of the font's em in the SVG's units (default 100)")
    ap.add_argument("--tracking", type=float, default=0.0, help="extra space after every glyph, in 1/1000 em")
    ap.add_argument("--pair", action="append", default=[], metavar="AB=N", help="manual kerning for a pair, in 1/1000 em (repeatable)")
    ap.add_argument("--padding", type=float, default=0.0, help="space around the ink in SVG units (default 0)")
    ap.add_argument("--keep-overlaps", action="store_true", help="diagnostic: skip overlap removal (shows the seams the default removes)")
    ap.add_argument("--fill", default="#000000", help="#rrggbb fill of the glyphs (default #000000)")
    ap.add_argument("--title", help="accessible name (default: the text)")
    ap.add_argument("--out", default="assets/logo/wordmark.svg", help="SVG inside the project (default assets/logo/wordmark.svg)")
    a = ap.parse_args()
    from fontTools.pens.boundsPen import BoundsPen
    from fontTools.pens.svgPathPen import SVGPathPen
    from fontTools.pens.transformPen import TransformPen
    from fontTools.ttLib import TTFont
    import pathops

    fp = Path(a.font).expanduser()
    if not fp.is_file():
        fail(EXIT_USAGE, f"font not found: {a.font}")
    try:
        font0 = TTFont(str(fp))
    except Exception as e:  # fontTools raises many types for a file that is not a font
        fail(EXIT_USAGE, f"{fp.name} is not a readable font: {e}")
    names = font0["name"]
    family = (names.getDebugName(16) or names.getDebugName(1) or fp.stem)
    if a.info:
        print(f"{family} {names.getDebugName(2) or ''}".strip())
        print(f"unitsPerEm {font0['head'].unitsPerEm}, glyphs {len(font0.getGlyphOrder())}")
        print("axes: " + (", ".join(f"{x.axisTag} {x.minValue:g}..{x.maxValue:g} (default {x.defaultValue:g})" for x in font0["fvar"].axes) if "fvar" in font0 else "none (static font)"))
        return 0
    if not a.text:
        fail(EXIT_USAGE, "--text is required (or use --info)")
    if "\n" in a.text:
        fail(EXIT_USAGE, "one line of text only")
    try:
        parse_hex(a.fill)
    except ValueError as e:
        fail(EXIT_USAGE, f"--fill: {e}")
    if a.em <= 0 or a.padding < 0:
        fail(EXIT_USAGE, "--em must be above 0 and --padding cannot be negative")
    project = find_project(a.project)
    out = confine(project, a.out, what="--out")
    axes = parse_axes(a.axis)
    pairs = parse_pairs(a.pair)
    font, pinned = instance(font0, axes)
    upm = font["head"].unitsPerEm
    s = a.em / upm
    cmap = font.getBestCmap()
    gs = font.getGlyphSet()
    missing = sorted({c for c in a.text if ord(c) not in cmap})
    if missing:
        fail(EXIT_FAIL, f"{fp.name} has no glyph for {', '.join(f'{c!r} (U+{ord(c):04X})' for c in missing)}; "
                        f"pick another font or check coverage with `brand-creator fontcheck`")
    # 1. layout and overlap removal: one pathops path per glyph, positioned in font units
    placed, x = [], 0.0
    for i, ch in enumerate(a.text):
        gname = cmap[ord(ch)]
        path = pathops.Path()
        gs[gname].draw(path.getPen(glyphSet=gs))
        if not a.keep_overlaps:
            path.simplify(fix_winding=True, keep_starting_points=False)
        placed.append((ch, gname, x, path))
        adv = font["hmtx"][gname][0] + a.tracking * upm / 1000
        if i + 1 < len(a.text):
            adv += pairs.get(ch + a.text[i + 1], 0.0) * upm / 1000
        x += adv
    # 2. bounds in SVG space (y down, scaled), then a translation that puts the ink box at the padding
    bp = BoundsPen(None)
    for _ch, _g, gx, path in placed:
        path.draw(TransformPen(bp, (s, 0, 0, -s, gx * s, 0)))
    if bp.bounds is None:
        fail(EXIT_FAIL, "the text has no outlines (only spaces?)")
    x0, y0, x1, y1 = bp.bounds
    tx, ty = a.padding - x0, a.padding - y0
    width, height = (x1 - x0) + 2 * a.padding, (y1 - y0) + 2 * a.padding
    body = []
    for ch, gname, gx, path in placed:
        pen = SVGPathPen(None, ntos=fmt)
        path.draw(TransformPen(pen, (s, 0, 0, -s, gx * s + tx, ty)))
        d = pen.getCommands()
        if d:
            body.append(f'<path data-glyph="{ch if ch not in "&<>\"" else "x" + format(ord(ch), "x")}" d="{d}"/>')
    os2 = font["OS/2"]
    meta = {"data-baseline": fmt(ty)}
    if getattr(os2, "sCapHeight", 0):
        meta["data-cap-height"] = fmt(os2.sCapHeight * s)
    if getattr(os2, "sxHeight", 0):
        meta["data-x-height"] = fmt(os2.sxHeight * s)
    title = (a.title or a.text).replace("&", "&amp;").replace("<", "&lt;").replace('"', "&quot;")
    inst = ",".join(f"{k}={fmt(v)}" for k, v in pinned.items())
    attrs = " ".join(f'{k}="{v}"' for k, v in meta.items())
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {fmt(width)} {fmt(height)}" width="{fmt(width)}" height="{fmt(height)}" '
           f'role="img" aria-label="{title}" {attrs} data-source="{family}{(" " + inst) if inst else ""}">'
           f'<g fill="{a.fill.lower()}">{"".join(body)}</g></svg>\n')
    problems = lint_svg_text(svg)
    if problems:  # cannot happen with this writer; a guard so the promise "no live text" is checked, not assumed
        fail(EXIT_FAIL, f"mark_lint rejects the outlined SVG: {'; '.join(problems)}")
    changed = write_bytes_if_changed(out, svg.encode("utf-8"))
    print(f"{rel(project, out)}: {'written' if changed else 'unchanged'} ({len(a.text)} glyphs from {family}"
          f"{' at ' + inst if inst else ''}; {'overlaps KEPT (diagnostic)' if a.keep_overlaps else 'overlaps removed'}; {fmt(width)} x {fmt(height)} units; no kerning from the font)")
    return 0


main_guard(main)
