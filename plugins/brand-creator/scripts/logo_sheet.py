#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator logo-sheet: the real-size sheet every mark is judged on, 16 px first.

  * the mark at 16, 20, 32, 64, 128 and 180 px on a light and a dark ground, rasterised 1:1 with resvg
  * the 16 px raster enlarged x4 with nearest-neighbour (what a favicon really looks like)
  * a header mock: the mark at 32 px in a site header strip, light and dark
Each tile is measured: the mark must stay visible and every colour that covers 5 percent or more of the opaque
pixels must reach the brand-rule graphic contrast (default 3:1) against the ground it sits on. These are brand rules,
labelled "brand rule (logos WCAG-exempt)", because WCAG 2.2 exempts logos.
--guides adds the geometry proof: the mark at 512 px with baseline, cap-line, x-height and grid guides drawn over it
(assets/_checks/logo-guides.png) and, for every horizontal guide, the distance in px between the guide and the strongest
ink edge within --window px of it (flat feet and tops measure well; a point does not). Guides come from the flags or from
the data-baseline, data-cap-height and data-x-height attributes that `outline-glyphs` writes; the tolerance is
guides.tolerance_px in qa/rules.json (proposal 1.5 px at 512).
Inputs: --svg (light artwork) and optionally --svg-dark (artwork for the dark ground; the light one is used when
absent, and a dark tile that vanishes is reported). Output: assets/_checks/logo-sheet.png plus the JSON report.
"""
import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
import svgtools  # noqa: E402
from _color import parse_hex, to_hex, wcag_ratio  # noqa: E402
from _common import (EXIT_CANNOT, EXIT_USAGE, Parser, Report, add_project_arg, add_renderer_arg, confine, fail,  # noqa: E402
                     find_project, main_guard, rasterise_svg, rel)
from mark_lint import lint_svg_text  # noqa: E402
import qa_rules  # noqa: E402
from pxio import read_png  # noqa: E402
import xml.etree.ElementTree as ET  # noqa: E402

SIZES = (16, 20, 32, 64, 128, 180)
PAD, GAP = 24, 24
Q = lambda t: f"{{{svgtools.SVG_NS}}}{t}"  # noqa: E731


def measure(png: bytes, ground: str) -> dict:
    w, h, px = read_png(png)
    g = parse_hex(ground)
    xs, ys, opaque = [], [], {}
    total = 0.0
    n_opaque = 0
    for i in range(w * h):
        r, gg, b, a = px[i * 4:i * 4 + 4]
        if a:
            xs.append(i % w)
            ys.append(i // w)
            total += a / 255
        if a >= 230:
            n_opaque += 1
            opaque[(r, gg, b)] = opaque.get((r, gg, b), 0) + 1
    if not xs:
        return {"visible": False, "coverage": 0.0, "bbox": None, "min_ratio": None, "colours": []}
    cols = []
    for rgb, n in sorted(opaque.items(), key=lambda kv: -kv[1]):
        if n / n_opaque >= 0.05:
            cols.append({"hex": to_hex(rgb), "share": round(n / n_opaque, 3), "ratio": round(wcag_ratio(rgb, g), 2)})
    return {"visible": n_opaque > 0, "coverage": round(total / (w * h), 3), "bbox": [min(xs), min(ys), max(xs), max(ys)],
            "min_ratio": min((c["ratio"] for c in cols), default=None), "colours": cols}


def tokens_ground(project: Path, mode: str, default: str) -> str:
    f = project / "assets" / "tokens" / "tokens.json"
    if f.is_file():
        try:
            return json.loads(f.read_text())["modes"][mode]["color.bg"]["hex"]
        except (ValueError, KeyError):
            return default
    return default


GUIDE_RASTER = 512
GUIDE_COLOUR = {"baseline": "#e0218a", "cap": "#1a73e8", "x-height": "#2e9e55", "grid": "#9a9a9a"}


def row_coverage(png: bytes) -> list[int]:
    w, h, px = read_png(png)
    return [sum(1 for x in range(w) if px[(y * w + x) * 4 + 3] >= 128) for y in range(h)]


def strongest_edge(cov: list[int], y: float, window: float) -> tuple[float, int]:
    """-> (boundary position, size of the coverage step) of the strongest row boundary within `window` px of y."""
    best, bstep = None, -1
    for b in range(max(1, int(y - window)), min(len(cov), int(y + window) + 2)):
        step = abs(cov[b] - cov[b - 1])
        if step > bstep or (step == bstep and best is not None and abs(b - y) < abs(best - y)):
            best, bstep = b, step
    return float(best if best is not None else y), max(bstep, 0)


def guides_proof(rep: Report, project: Path, light_txt: str, svg_path: Path, ground: str, a) -> None:
    root = svgtools.parse(light_txt)
    vx, vy, vw, vh = svgtools.viewbox(root)
    attr = lambda k: float(root.get(k)) if root.get(k) not in (None, "") else None  # noqa: E731
    base = a.baseline if a.baseline is not None else attr("data-baseline")
    cap = a.cap_line if a.cap_line is not None else (base - attr("data-cap-height") if base is not None and attr("data-cap-height") else None)
    xl = a.x_line if a.x_line is not None else (base - attr("data-x-height") if base is not None and attr("data-x-height") else None)
    lines = [(n, y) for n, y in (("baseline", base), ("cap", cap), ("x-height", xl)) if y is not None]
    if not lines and not a.grid:
        fail(EXIT_USAGE, "--guides has nothing to draw: pass --baseline/--cap-line/--x-line/--grid (viewBox units), or use a mark outlined "
                         "with `brand-creator outline-glyphs` (it writes data-baseline, data-cap-height and data-x-height)")
    rules, rules_src = qa_rules.load(project)
    tol = float(rules["guides"]["tolerance_px"])
    S = GUIDE_RASTER
    s = min(S / vw, S / vh)
    cw, ch = vw * s, vh * s
    ox, oy = (S - cw) / 2, (S - ch) / 2
    ypx = lambda y: oy + (y - vy) * s  # noqa: E731
    xpx = lambda x: ox + (x - vx) * s  # noqa: E731
    png = rasterise_svg(svgtools.fit(light_txt, S, S), S, S, renderer=a.renderer)
    cov = row_coverage(png)
    rep.extra["guides"] = {"raster_px": S, "tolerance_px": tol, "tolerance_source": rules_src, "window_px": a.window,
                           "units": "mark viewBox units; offsets in px of the 512 px raster"}
    for name, y in lines:
        pos, step = strongest_edge(cov, ypx(y), a.window)
        off = pos - ypx(y)
        ok = abs(off) <= tol and step > 0
        rep.add(f"guide:{name}", "pass" if ok else "fail", f"geometry: the ink edge sits on the {name} guide (tolerance {tol:g} px at {S} px, {rules_src})",
                detail=(f"guide at y={y:g} ({ypx(y):.1f} px); strongest ink edge within {a.window:g} px is at {pos:.1f} px: {off:+.1f} px off"
                        + ("" if ok else "; the edge is off the guide, or there is no ink edge near it (a point or a curve has no flat edge to measure)")),
                guide_y=round(y, 3), edge_px=round(pos, 2), offset_px=round(off, 2), edge_step=step)
    if a.grid:
        rep.add("guide:grid", "info", "grid guides drawn", detail=f"every {a.grid:g} unit(s) of the mark's {vw:g} x {vh:g} viewBox")
    # the proof image: the mark on the ground with the guides over it
    sheet = ET.Element(Q("svg"), {"width": str(S), "height": str(S), "viewBox": f"0 0 {S} {S}"})
    ET.SubElement(sheet, Q("rect"), {"width": str(S), "height": str(S), "fill": ground})
    sheet.append(svgtools.nested(root, ox, oy, cw, ch))
    if a.grid:
        n = 0
        while n * a.grid <= max(vw, vh) + 1e-9:
            for ax in ("v", "h"):
                p = (xpx(vx + n * a.grid) if ax == "v" else ypx(vy + n * a.grid))
                ET.SubElement(sheet, Q("line"), {"x1": f"{p:.2f}" if ax == "v" else "0", "x2": f"{p:.2f}" if ax == "v" else str(S),
                                                 "y1": "0" if ax == "v" else f"{p:.2f}", "y2": str(S) if ax == "v" else f"{p:.2f}",
                                                 "stroke": GUIDE_COLOUR["grid"], "stroke-width": "1", "stroke-opacity": "0.55"})
            n += 1
    for name, y in lines:
        ET.SubElement(sheet, Q("line"), {"x1": "0", "x2": str(S), "y1": f"{ypx(y):.2f}", "y2": f"{ypx(y):.2f}", "stroke": GUIDE_COLOUR[name], "stroke-width": "1"})
        t = ET.SubElement(sheet, Q("text"), {"x": "4", "y": f"{ypx(y) - 3:.2f}", "font-size": "11", "font-family": "sans-serif", "fill": GUIDE_COLOUR[name]})
        t.text = name
    out = confine(project, "assets/_checks/logo-guides.png", what="guides image")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(rasterise_svg(svgtools.dump(sheet), S, S, renderer=a.renderer))
    rep.add("guides-image", "info", "guide overlay", detail=f"{rel(project, out)} ({S}x{S}); read it: every guide should touch an edge")
    rep.extra["guides_image"] = rel(project, out)


def main() -> int:
    ap = Parser(prog="brand-creator logo-sheet", description=__doc__, formatter_class=__import__("argparse").RawDescriptionHelpFormatter)
    add_project_arg(ap)
    add_renderer_arg(ap)
    ap.add_argument("--svg", help="mark SVG for the light ground (default: assets/logo/mark.svg)")
    ap.add_argument("--svg-dark", help="mark SVG for the dark ground (default: <name>-dark.svg next to --svg when it exists, else the light file)")
    ap.add_argument("--ground-light", help="#rrggbb (default: color.bg of the light tokens, else #ffffff)")
    ap.add_argument("--ground-dark", help="#rrggbb (default: color.bg of the dark tokens, else #111111)")
    ap.add_argument("--min-contrast", type=float, default=3.0, help="brand-rule graphic contrast target (default 3)")
    ap.add_argument("--out", help="sheet PNG inside the project (default: assets/_checks/logo-sheet.png)")
    ap.add_argument("--guides", action="store_true", help="geometry proof: guide lines over the mark at 512 px, with the measured distance to the ink")
    ap.add_argument("--baseline", type=float, metavar="Y", help="baseline guide at this y in the mark's viewBox units (default: data-baseline)")
    ap.add_argument("--cap-line", type=float, metavar="Y", help="cap-line guide at this y (default: data-baseline minus data-cap-height)")
    ap.add_argument("--x-line", type=float, metavar="Y", help="x-height guide at this y (default: data-baseline minus data-x-height)")
    ap.add_argument("--grid", type=float, metavar="N", help="grid guides every N viewBox units")
    ap.add_argument("--window", type=float, default=12.0, help="search window in px around a horizontal guide for the ink edge (default 12)")
    a = ap.parse_args()
    project = find_project(a.project)
    svg_path = confine(project, a.svg or "assets/logo/mark.svg", what="--svg")
    if not svg_path.is_file():
        fail(EXIT_USAGE, f"mark SVG not found: {svg_path.relative_to(project)} (pass --svg)")
    # the dark twin of the light file named (mark.svg -> mark-dark.svg, wordmark-outlined.svg -> wordmark-outlined-dark.svg); never another mark
    dark_path = confine(project, a.svg_dark, what="--svg-dark") if a.svg_dark else svg_path.with_name(svg_path.stem + "-dark.svg")
    if a.svg_dark and not dark_path.is_file():
        fail(EXIT_USAGE, f"--svg-dark not found: {a.svg_dark}")
    use_dark = dark_path.is_file()
    light_txt = svg_path.read_text(encoding="utf-8")
    dark_txt = dark_path.read_text(encoding="utf-8") if use_dark else light_txt
    problems = lint_svg_text(light_txt) + (lint_svg_text(dark_txt) if use_dark else [])
    if problems:
        fail(1, f"mark_lint: the mark is not pure vector ({'; '.join(sorted(set(problems)))}); outline text first")
    gl = a.ground_light or tokens_ground(project, "light", "#ffffff")
    gd = a.ground_dark or tokens_ground(project, "dark", "#111111")
    for g in (gl, gd):
        parse_hex(g)
    out = confine(project, a.out or "assets/_checks/logo-sheet.png", what="--out")

    rep = Report("logo-sheet", project, [svg_path] + ([dark_path] if use_dark else []), renderer=a.renderer)
    rep.extra = {"sizes": list(SIZES), "grounds": {"light": gl, "dark": gd}, "sheet": rel(project, out),
                 "dark_artwork": "separate file" if use_dark else "same file as light (no --svg-dark)"}

    # ---- measurements per tile
    for scheme, txt, ground in (("light", light_txt, gl), ("dark", dark_txt, gd)):
        for s in SIZES:
            png = rasterise_svg(svgtools.fit(txt, s, s), s, s, renderer=a.renderer)
            m = measure(png, ground)
            tid = f"{scheme}:{s}px"
            label = "brand rule (logos WCAG-exempt)"
            if not m["visible"]:
                rep.add(tid, "fail", label, detail="the mark is not visible (no opaque pixels)", **m)
            elif m["min_ratio"] is not None and m["min_ratio"] < a.min_contrast:
                worst = min(m["colours"], key=lambda c: c["ratio"])
                rep.add(tid, "fail", label, detail=f"{worst['hex']} on {ground} is {worst['ratio']}:1, target {a.min_contrast:g}:1 "
                                                  f"(dark tiles vanish on dark pages: give the dark ground its own artwork)", **m)
            else:
                rep.add(tid, "pass", label, detail=f"visible, ink coverage {m['coverage']:.0%}, lowest colour contrast {m['min_ratio']}:1", **m)

    if a.guides:
        guides_proof(rep, project, light_txt, svg_path, gl, a)

    # ---- the sheet itself (an SVG assembled from the artwork, rasterised once, 1 px = 1 px)
    pw = PAD * 2 + sum(SIZES) + GAP * (len(SIZES) - 1)
    W, H = pw * 2 + 16, PAD + 180 + PAD + 12 + 64 + PAD + 12 + 56 + PAD + 12
    sheet = ET.Element(Q("svg"), {"width": str(W), "height": str(H), "viewBox": f"0 0 {W} {H}"})
    ET.SubElement(sheet, Q("rect"), {"width": str(W), "height": str(H), "fill": "#808080"})
    for pi, (scheme, txt, ground) in enumerate((("light", light_txt, gl), ("dark", dark_txt, gd))):
        x0 = pi * (pw + 16)
        ET.SubElement(sheet, Q("rect"), {"x": str(x0), "y": "0", "width": str(pw), "height": str(H), "fill": ground})
        label_fill = "#000000" if sum(parse_hex(ground)) > 382 else "#ffffff"
        root = svgtools.parse(txt)
        x = x0 + PAD
        for s in SIZES:
            sheet.append(svgtools.nested(root, x, PAD + 180 - s, s, s))
            t = ET.SubElement(sheet, Q("text"), {"x": str(x), "y": str(PAD + 180 + 14), "font-size": "11", "font-family": "sans-serif", "fill": label_fill})
            t.text = f"{s}"
            x += s + GAP
        # x4 favicon: the real 16 px raster, enlarged with nearest neighbour
        y2 = PAD + 180 + PAD + 12
        png16 = rasterise_svg(svgtools.fit(txt, 16, 16), 16, 16, renderer=a.renderer)
        ET.SubElement(sheet, Q("image"), {"x": str(x0 + PAD), "y": str(y2), "width": "64", "height": "64", "image-rendering": "optimizeSpeed",
                                           "href": "data:image/png;base64," + base64.b64encode(png16).decode()})
        t = ET.SubElement(sheet, Q("text"), {"x": str(x0 + PAD + 80), "y": str(y2 + 36), "font-size": "11", "font-family": "sans-serif", "fill": label_fill})
        t.text = "16 px x4"
        # header mock
        y3 = y2 + 64 + PAD + 12 - 12
        ET.SubElement(sheet, Q("rect"), {"x": str(x0 + PAD), "y": str(y3), "width": str(pw - 2 * PAD), "height": "56", "fill": "none",
                                          "stroke": label_fill, "stroke-opacity": "0.25"})
        sheet.append(svgtools.nested(root, x0 + PAD + 12, y3 + 12, 32, 32))
        for k in range(3):
            ET.SubElement(sheet, Q("rect"), {"x": str(x0 + PAD + 64 + k * 80), "y": str(y3 + 24), "width": "56", "height": "8", "rx": "4",
                                              "fill": label_fill, "fill-opacity": "0.35"})
    sheet_png = rasterise_svg(svgtools.dump(sheet), W, H, renderer=a.renderer)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(sheet_png)
    rep.add("sheet", "info", "logo sheet", detail=f"{rel(project, out)} ({W}x{H}); judge the 16 px tile first", width=W, height=H)
    return rep.finish()


main_guard(main)
