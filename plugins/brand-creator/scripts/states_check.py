#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator states-check: a state set (idle, active, paused, error ...) must be told apart without colour.

Small glyphs that carry a state (tray and status icons, badges) are read by people who cannot tell the colours apart,
on screens in greyscale and at a glance. Every pair of states in a set must differ in
  * greyscale: the share of ink pixels (of either image) whose luma differs by more than 16/255 on the set's ground, and
  * silhouette: the share of the union of the two shapes that is not shared (alpha when an image has transparency,
    otherwise the ink against the ground),
each at or above the owner's thresholds (qa/rules.json states.greyscale_min_diff and states.silhouette_min_diff;
proposals 0.10 each, printed with every result). A pair of states that look the same fails.

Sets are declared in qa/states.json (or --states FILE, repeatable). Without --states every `qa/states.*.json` next to it is read too:
`emit tray` writes its own sets to qa/states.tray.json, so the owner's file is never edited by a generator and one report covers all.
  {"schema": 1, "sets": [{"name": "tray-16", "size": 16, "ground": "#808080",
                          "states": {"idle": "assets/tray/idle.svg", "error": "assets/tray/error.png"},
                          "greyscale_min_diff": 0.10, "silhouette_min_diff": 0.10}]}
An SVG state is rasterised at the set's `size` (resvg); PNG states are used as they are and must share one size.
`ground`, `greyscale_min_diff` and `silhouette_min_diff` are optional overrides of the project rules.
"""
import itertools
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))
import imgmeasure as im  # noqa: E402
import qa_rules  # noqa: E402
import svgtools  # noqa: E402
from _color import parse_hex  # noqa: E402
from _common import (EXIT_CANNOT, EXIT_USAGE, Parser, Report, add_project_arg, add_renderer_arg, confine, fail, find_project,  # noqa: E402
                     main_guard, rasterise_svg, rel)
from pxio import read_png  # noqa: E402

STATES_FILE = "qa/states.json"
LABEL = "owner thresholds (qa/rules.json states); proposals until the owner sets them"


def load_sets(f: Path) -> list[dict]:
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        fail(EXIT_USAGE, f"{f.name}: cannot read the state sets ({e})")
    if not isinstance(doc, dict) or doc.get("schema") != 1 or not isinstance(doc.get("sets"), list) or not doc["sets"]:
        fail(EXIT_USAGE, f"{f.name}: needs {{\"schema\": 1, \"sets\": [ ... ]}} with at least one set")
    names = set()
    for i, s in enumerate(doc["sets"]):
        if not (isinstance(s, dict) and isinstance(s.get("name"), str) and isinstance(s.get("states"), dict)):
            fail(EXIT_USAGE, f"{f.name}: sets[{i}] needs a name and a states map of {{state name: file}}")
        if s["name"] in names:
            fail(EXIT_USAGE, f"{f.name}: two sets are called {s['name']!r}")
        names.add(s["name"])
        if len(s["states"]) < 2:
            fail(EXIT_USAGE, f"{f.name}: set {s['name']!r} needs at least two states to compare")
        extra = set(s) - {"name", "size", "ground", "states", "greyscale_min_diff", "silhouette_min_diff"}
        if extra:
            fail(EXIT_USAGE, f"{f.name}: set {s['name']!r} has unknown keys {sorted(extra)}")
        for k in ("greyscale_min_diff", "silhouette_min_diff", "size"):
            v = s.get(k)
            if v is not None and (not isinstance(v, (int, float)) or isinstance(v, bool) or v <= 0):
                fail(EXIT_USAGE, f"{f.name}: set {s['name']!r}: {k} must be a number above 0")
    return doc["sets"]


def load_state(project: Path, path: str, size: int | None, renderer: str):
    p = confine(project, path, what="state image")
    if not p.is_file():
        fail(EXIT_USAGE, f"state image not found: {path}")
    if p.suffix.lower() == ".svg":
        if not size:
            fail(EXIT_USAGE, f"{path} is an SVG: give the set a `size` to rasterise it at")
        return p, read_png(rasterise_svg(svgtools.fit(p.read_text(encoding="utf-8"), size, size), size, size, renderer=renderer))
    if p.suffix.lower() != ".png":
        fail(EXIT_USAGE, f"{path}: states are .png or .svg files")
    try:
        return p, read_png(p.read_bytes())
    except ValueError as e:
        fail(EXIT_CANNOT, f"{path}: cannot read the PNG ({e})")


def silhouette(raster, ground) -> list[bool]:
    w, h, px = raster
    if any(px[i + 3] < 255 for i in range(0, len(px), 4)):
        return im.alpha_mask(raster)
    return im.ink_mask(raster, ground)


def main() -> int:
    ap = Parser(prog="brand-creator states-check", description=__doc__, formatter_class=__import__("argparse").RawDescriptionHelpFormatter)
    add_project_arg(ap)
    add_renderer_arg(ap)
    ap.add_argument("--states", action="append", help=f"state sets file inside the project, repeatable (default {STATES_FILE} plus qa/states.*.json)")
    a = ap.parse_args()
    project = find_project(a.project)
    if a.states:
        files = [confine(project, s, what="--states") for s in a.states]
    else:
        files = ([project / STATES_FILE] if (project / STATES_FILE).is_file() else []) + sorted((project / "qa").glob("states.*.json"))
        files = [confine(project, str(f.relative_to(project)), what="state sets") for f in files] or [confine(project, STATES_FILE, what="state sets")]
    for sf in files:
        if not sf.is_file():
            fail(EXIT_USAGE, f"no state sets: {rel(project, sf)} not found. Declare them as described in `brand-creator states-check --help`")
    rules, rules_src = qa_rules.load(project)
    sets: list[dict] = []
    for sf in files:
        more = load_sets(sf)
        clash = {s["name"] for s in sets} & {s["name"] for s in more}
        if clash:
            fail(EXIT_USAGE, f"{sf.name}: set name(s) {sorted(clash)} are also declared in an earlier state file")
        sets += more
    sf = files[0]
    loaded: list[tuple[dict, dict]] = []
    inputs = files + [project / qa_rules.RULES_FILE]
    for s in sets:
        imgs = {}
        for name, path in s["states"].items():
            p, r = load_state(project, path, s.get("size"), a.renderer)
            imgs[name] = r
            inputs.append(p)
        dims = {r[:2] for r in imgs.values()}
        if len(dims) != 1:
            fail(EXIT_USAGE, f"set {s['name']!r}: the states differ in size ({', '.join(f'{n} {r[0]}x{r[1]}' for n, r in imgs.items())}); "
                             f"every state of a set must be the same size")
        loaded.append((s, imgs))
    rep = Report("states", project, inputs, renderer=f"{a.renderer} (SVG states only)")
    rep.extra = {"sets": [s["name"] for s in sets], "rules_source": rules_src, "states_file": rel(project, sf),
                 "states_files": [rel(project, f) for f in files]}
    for s, imgs in loaded:
        g_min = float(s.get("greyscale_min_diff", rules["states"]["greyscale_min_diff"]))
        s_min = float(s.get("silhouette_min_diff", rules["states"]["silhouette_min_diff"]))
        ground = s.get("ground", rules["states"]["ground"])
        try:
            parse_hex(ground)
        except ValueError as e:
            fail(EXIT_USAGE, f"set {s['name']!r}: ground: {e}")
        sil = {n: silhouette(r, ground) for n, r in imgs.items()}
        for (na, ra), (nb, rb) in itertools.combinations(imgs.items(), 2):
            gd = im.grey_diff_ratio(ra, rb, ground)
            sd = im.diff_ratio(sil[na], sil[nb])
            miss = ([f"greyscale {gd:.2f} < {g_min:g}"] if gd < g_min else []) + ([f"silhouette {sd:.2f} < {s_min:g}"] if sd < s_min else [])
            rep.add(f"states:{s['name']}:{na}|{nb}", "fail" if miss else "pass", LABEL,
                    detail=(f"{na} vs {nb}: " + ("; ".join(miss) + ": these two read as the same state without colour" if miss else
                                                  f"greyscale {gd:.2f} (min {g_min:g}), silhouette {sd:.2f} (min {s_min:g})")),
                    set=s["name"], greyscale_diff=round(gd, 4), silhouette_diff=round(sd, 4),
                    greyscale_min=g_min, silhouette_min=s_min, ground=ground)
    return rep.finish()


main_guard(main)
