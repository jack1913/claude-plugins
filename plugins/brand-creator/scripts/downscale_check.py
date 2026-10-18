#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow==11.3.0"]
# ///
"""brand-creator downscale: measure what survives when one master is shrunk to the sizes systems really show.

The mark is judged on the pixels an operating system makes, not on the vector at small size. One master (a PNG, or an
SVG that is rasterised once at --master-size) is shrunk to each system size; at each size the accent is measured:
pixel count, bounding box and the largest solid square. Brand rule (default, owner-adjustable in qa/rules.json): at
32 px and below the accent holds a solid 4 x 4 px square, so it does not turn into a 1-2 px smudge.

Method (printed on every report, never a silent fallback):
  macOS          `sips -z` (the real system downscale) is the default.
  --renderer=resvg   rasterises an SVG source at every size (a vector render, not a downscale).
  --renderer=pillow  resamples a PNG source (Lanczos). It cannot read SVG.
  elsewhere      no sips: the run stops (exit 3) unless --renderer is given or BRAND-STATE.md records the opt-in
                 `renderer: resvg (opted in <date>)`; --record-renderer writes that line.
One report per measured source: assets/_checks/downscale/<slug>.json (`check` ties a manifest row's `downscale_source` to it).
Before and after: --previous <older master> measures the same sizes on the earlier round's master; otherwise the earlier report
of the same source is compared when it used the same method, master size, accent and ground (else an info row says so). --png measures files exactly as shipped (for example actool's own output) with no resampling.
"""
import re
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))
sys.path.insert(0, str(HERE / "emitters"))
import imgmeasure as im  # noqa: E402
import qa_rules  # noqa: E402
import specs  # noqa: E402
import svgtools  # noqa: E402
from _color import parse_hex  # noqa: E402
from _common import (EXIT_CANNOT, EXIT_USAGE, Parser, Report, add_project_arg, confine, downscale_report_tool, fail, find_project, main_guard,  # noqa: E402
                     rasterise_svg, read_state, rel, run, scratch_dir, today)
from pxio import png_size, read_png  # noqa: E402

RULE_LABEL = "brand rule (owner-adjustable): the accent keeps a solid square at small sizes"
MASTER_DEFAULT = 1024


def parse_sizes(s: str) -> list[int]:
    try:
        out = sorted({int(x) for x in s.split(",") if x.strip()}, reverse=True)
    except ValueError:
        fail(EXIT_USAGE, f"--sizes must be a comma list of whole numbers, got {s!r}")
    if not out or min(out) < 1:
        fail(EXIT_USAGE, "--sizes needs at least one size of 1 px or more")
    return out


def default_sizes() -> tuple[list[int], list[str]]:
    apple = specs.sizes("downscale-apple")["px"]
    ico = specs.sizes("favicon-set")["ico_layers"]
    return sorted(set(apple) | set(ico), reverse=True), ["downscale-apple", "favicon-set"]


def resolve_method(a, project: Path) -> tuple[str, str]:
    if a.renderer:
        return a.renderer, "explicit --renderer"
    if sys.platform == "darwin" and shutil.which("sips"):
        return "sips", "macOS system downscale, the default"
    recorded = str(read_state(project).get("renderer", "") or "")
    m = re.match(r"^(resvg|pillow) \(opted in (\d{4}-\d{2}-\d{2})\)$", recorded.strip())
    if m:
        return m.group(1), f"opt-in recorded in BRAND-STATE.md on {m.group(2)}"
    fail(EXIT_CANNOT, "there is no system downscaler here (sips exists on macOS only) and no renderer opt-in is recorded. "
                      "Pass --renderer=resvg (SVG source) or --renderer=pillow (PNG source) to opt in explicitly; add "
                      "--record-renderer to write `renderer: <name> (opted in <date>)` into BRAND-STATE.md so later runs "
                      "and `check` know. Nothing was measured.")


def accent_colour(project: Path, a, rules: dict) -> tuple[str, str]:
    """-> (#rrggbb, ground #rrggbb)."""
    import json
    mode = a.mode
    tok = project / "assets" / "tokens" / "tokens.json"
    modes = None
    if tok.is_file():
        try:
            modes = json.loads(tok.read_text(encoding="utf-8"))["modes"][mode]
        except (ValueError, KeyError):
            fail(EXIT_USAGE, f"{rel(project, tok)} is not a brand-creator tokens.json (no modes.{mode})")
    spec = a.accent or rules["downscale"]["accent_colour"]
    if spec.startswith("#"):
        try:
            parse_hex(spec)
        except ValueError as e:
            fail(EXIT_USAGE, str(e))
        acc = spec.lower()
    else:
        if modes is None or spec not in modes:
            fail(EXIT_USAGE, f"accent role {spec} cannot be resolved: build the tokens first (brand-creator tokens), or pass "
                             f"--accent #rrggbb (or set downscale.accent_colour in qa/rules.json)")
        acc = modes[spec]["hex"].lower()
    ground = a.ground or (modes["color.bg"]["hex"].lower() if modes and "color.bg" in modes else ("#ffffff" if mode == "light" else "#111111"))
    try:
        parse_hex(ground)
    except ValueError as e:
        fail(EXIT_USAGE, f"--ground: {e}")
    return acc, ground


def master_png(src: Path, method: str, master_size: int, work: Path, renderer_for_svg: str) -> Path | None:
    """The PNG master the system downscaler reads (rasterising an SVG source once). None for resvg (renders per size)."""
    if src.suffix.lower() == ".png":
        return src
    if src.suffix.lower() != ".svg":
        fail(EXIT_USAGE, f"{src.name}: the source must be a .png or a .svg")
    out = work / f"master-{src.stem}-{master_size}.png"
    out.write_bytes(rasterise_svg(svgtools.fit(src.read_text(encoding="utf-8"), master_size, master_size), master_size, master_size,
                                  renderer=renderer_for_svg))
    return out


def shrink(src: Path, size: int, method: str, work: Path, tag: str, master: Path | None) -> Path:
    out = work / f"{tag}-{size}.png"
    if method == "sips":
        run(["sips", "-z", str(size), str(size), str(master), "--out", str(out)])
    elif method == "pillow":
        from PIL import Image
        with Image.open(master) as img:
            img.convert("RGBA").resize((size, size), Image.LANCZOS).save(out, format="PNG")
    else:  # resvg
        out.write_bytes(rasterise_svg(svgtools.fit(src.read_text(encoding="utf-8"), size, size), size, size, renderer="resvg"))
    return out


def measure_png(path: Path, acc: str, ground: str, tol: float) -> dict:
    try:
        w, h, px = read_png(path.read_bytes())
    except (ValueError, OSError) as e:
        fail(EXIT_CANNOT, f"{path.name}: cannot read the downscaled PNG ({e}); nothing was measured")
    mask = im.accent_mask((w, h, px), acc, tol, ground)
    n = sum(mask)
    bb = im.mask_bbox(mask, w, h)
    return {"size": w if w == h else [w, h], "accent_px": n, "accent_bbox": list(bb) if bb else None,
            "accent_box": f"{bb[2] - bb[0] + 1}x{bb[3] - bb[1] + 1}" if bb else None,
            "accent_square": im.largest_square(mask, w, h),
            "ink_px": sum(im.ink_mask((w, h, px), ground))}


def gate(rep: Report, rid: str, label: str, m: dict, size: int, rule: dict, where: str) -> None:
    need, upto = rule["accent_min_px"], rule["accent_rule_max_size"]
    base = f"accent {m['accent_px']} px, box {m['accent_box'] or 'none'}, largest solid square {m['accent_square']} px"
    if size > upto:
        rep.add(rid, "info", f"{size} px, above the {upto} px rule", detail=f"{base} ({where})", **m)
    elif m["accent_square"] >= need:
        rep.add(rid, "pass", RULE_LABEL, detail=f"{size} px: {base}; needs a {need}x{need} square ({where})", **m)
    elif m["accent_px"] == 0:
        rep.add(rid, "fail", RULE_LABEL, detail=f"{size} px: the accent vanished ({where})", **m)
    else:
        rep.add(rid, "fail", RULE_LABEL, detail=f"{size} px: {base}; needs a {need}x{need} square ({where}). Redraw the accent "
                                                 f"larger or on a coarser grid, or change the rule in qa/rules.json", **m)


def main() -> int:
    ap = Parser(prog="brand-creator downscale", description=__doc__, formatter_class=__import__("argparse").RawDescriptionHelpFormatter)
    add_project_arg(ap)
    ap.add_argument("--source", help="master PNG or SVG inside the project (default: assets/logo/mark.svg)")
    ap.add_argument("--renderer", choices=("resvg", "pillow"), help="explicit non-system method (see above)")
    ap.add_argument("--record-renderer", action="store_true", help="write `renderer: <name> (opted in <date>)` into BRAND-STATE.md")
    ap.add_argument("--sizes", help="comma list of px sizes (default: platform-specs rows downscale-apple and favicon-set)")
    ap.add_argument("--master-size", type=int, default=MASTER_DEFAULT, help="px the SVG source is rasterised to before sips/pillow (default 1024)")
    ap.add_argument("--mode", choices=("light", "dark"), default="light", help="token mode for the accent and ground (default light)")
    ap.add_argument("--accent", help="#rrggbb accent (default: qa/rules.json downscale.accent_colour, a token role resolved in tokens.json)")
    ap.add_argument("--ground", help="#rrggbb ground the master is composited on (default: color.bg of the mode)")
    ap.add_argument("--previous", help="the earlier round's master (PNG or SVG) to measure at the same sizes (before/after)")
    ap.add_argument("--png", action="append", default=[], metavar="FILE", help="measure a PNG exactly as shipped (repeatable; no resampling)")
    a = ap.parse_args()
    project = find_project(a.project)
    rules, rules_src = qa_rules.load(project)
    rule = rules["downscale"]
    # Usage errors (exit 2) come before "this system cannot measure" (exit 3), so the same bad call gives the same answer on macOS and on
    # Linux: a recorded opt-in needs a named renderer, the sizes must parse, the source must be inside the project and exist.
    if a.record_renderer and not a.renderer:
        fail(EXIT_USAGE, "--record-renderer needs an explicit --renderer=resvg|pillow (it records an opt-in to a non-system renderer; "
                         "sips is the default on macOS and needs none)")
    sizes, rows = (parse_sizes(a.sizes), []) if a.sizes else default_sizes()
    src = confine(project, a.source or "assets/logo/mark.svg", what="--source")
    if not src.is_file():
        fail(EXIT_USAGE, f"source not found: {rel(project, src)} (pass --source <master.png|mark.svg>)")
    method, why = resolve_method(a, project)
    label = {"sips": "sips -z", "resvg": "resvg", "pillow": "pillow (Lanczos)"}[method]
    renderer_str = f"{label} ({why})"
    if a.record_renderer:
        st = read_state(project)
        st.set("renderer", f"{a.renderer} (opted in {today()})")
        st.save()
        print(f"recorded in BRAND-STATE.md: renderer: {a.renderer} (opted in {today()})")
    if sys.platform != "darwin" and method == "sips":
        fail(EXIT_CANNOT, "sips is not available on this system")
    if method == "resvg" and src.suffix.lower() != ".svg":
        fail(EXIT_CANNOT, "--renderer=resvg rasterises SVG; a PNG master needs sips (macOS) or --renderer=pillow")
    if method == "pillow" and src.suffix.lower() != ".png":
        fail(EXIT_CANNOT, "--renderer=pillow cannot rasterise SVG (it only resamples PNG input). Pass a PNG master, or use "
                          "--renderer=resvg for an SVG source")
    prev = None
    if a.previous:
        prev = confine(project, a.previous, what="--previous")
        if not prev.is_file():
            fail(EXIT_USAGE, f"--previous not found: {a.previous}")
        if method == "resvg" and prev.suffix.lower() != ".svg" or method == "pillow" and prev.suffix.lower() != ".png":
            fail(EXIT_CANNOT, f"--previous must be a {'.svg' if method == 'resvg' else '.png'} master for --renderer={method}")
    acc, ground = accent_colour(project, a, rules)
    tol = float(rule["accent_tolerance"])
    shipped = [confine(project, p, what="--png") for p in a.png]
    for p in shipped:
        if not p.is_file():
            fail(EXIT_USAGE, f"--png not found: {rel(project, p)}")

    # One report per measured source (assets/_checks/downscale/<slug>.json): `check` matches a manifest row to the report of ITS master.
    tool = downscale_report_tool(rel(project, src))
    # The previous run's numbers (read before the report is overwritten) are comparable only when that run measured the same
    # source with the same method, master size, accent and ground; anything else would report false regressions.
    import json
    last: dict = {}
    why_not = "no earlier report for this source"
    lf = project / "assets" / "_checks" / f"{tool}.json"
    if lf.is_file():
        try:
            doc = json.loads(lf.read_text(encoding="utf-8"))
            now_key = {"source": rel(project, src), "method": method, "master_size": a.master_size}
            diff = [k for k, v in now_key.items() if doc.get(k) != v]
            if (doc.get("accent") or {}).get("hex") != acc or (doc.get("accent") or {}).get("ground") != ground:
                diff.append("accent/ground")
            if diff:
                why_not = f"the earlier report differs in {', '.join(diff)}"
            else:
                last = {r["id"]: r for r in doc.get("results", [])}
        except ValueError:
            why_not = "the earlier report is not readable"

    inputs = [src] + ([prev] if prev else []) + shipped + [project / "assets/tokens/tokens.json", project / qa_rules.RULES_FILE]
    rep = Report(tool, project, inputs, renderer=renderer_str)
    work = scratch_dir(project, "downscale")
    stamped, warns = specs.stamp(rows, today()) if rows else ({}, [])
    rep.extra = {"source": rel(project, src), "method": method, "method_reason": why, "sizes": sizes, "master_size": a.master_size,
                 "accent": {"hex": acc, "mode": a.mode, "ground": ground, "tolerance": tol, "role": a.accent or rule["accent_colour"]},
                 "rule": {"accent_min_px": rule["accent_min_px"], "accent_rule_max_size": rule["accent_rule_max_size"], "source": rules_src},
                 "specs": stamped, "previous": rel(project, prev) if prev else None}
    for i, w in enumerate(warns):
        rep.add(f"spec:{w.split()[2]}:{i}", "warn", "platform spec row", detail=w)
    print(f"method: {renderer_str}; rule from {rules_src}: accent {rule['accent_min_px']}x{rule['accent_min_px']} px at "
          f"{rule['accent_rule_max_size']} px and below")

    if not prev and not last:
        rep.add("compare:none", "info", "before/after", detail=f"no comparable earlier run ({why_not}); pass --previous <older master> to compare")
    master = master_png(src, method, a.master_size, work, "resvg") if method != "resvg" else None
    prev_master = master_png(prev, method, a.master_size, work, "resvg") if prev and method != "resvg" else None
    for size in sizes:
        m = measure_png(shrink(src, size, method, work, "now", master), acc, ground, tol)
        rid = f"downscale:{size}px"
        gate(rep, rid, "", m, size, rule, f"{src.name} via {label}")
        before = None
        if prev:
            before = measure_png(shrink(prev, size, method, work, "prev", prev_master), acc, ground, tol)
            src_of_before = f"--previous {prev.name}"
        elif rid in last and "accent_px" in last[rid]:
            before = {k: last[rid].get(k) for k in ("accent_px", "accent_box", "accent_square")}
            src_of_before = "the previous run's report"
        if before:
            d_px, d_sq = m["accent_px"] - before["accent_px"], m["accent_square"] - before["accent_square"]
            worse = d_sq < 0 and size <= rule["accent_rule_max_size"]
            rep.add(f"compare:{size}px", "warn" if worse else "info", "before/after",
                    detail=f"accent {before['accent_px']} px -> {m['accent_px']} px ({d_px:+d}), solid square {before['accent_square']} -> "
                           f"{m['accent_square']} ({d_sq:+d}) vs {src_of_before}" + ("  REGRESSION at a rule size" if worse else ""),
                    before=before, after={k: m[k] for k in ("accent_px", "accent_box", "accent_square")})
    for p in shipped:
        try:
            w, h = png_size(p.read_bytes())
        except ValueError:
            fail(EXIT_USAGE, f"--png {rel(project, p)} is not a PNG")
        if w != h:
            fail(EXIT_USAGE, f"--png {rel(project, p)} is {w}x{h}; icons are square")
        gate(rep, f"shipped:{rel(project, p)}", "", measure_png(p, acc, ground, tol), w, rule, "as shipped, not resampled")
    return rep.finish()


main_guard(main)
