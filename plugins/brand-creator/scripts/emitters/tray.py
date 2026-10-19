#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator emit tray: shape-coded state icons for the system tray, then the states-check gate.

Reads tray/tray.json (the project's own config):
  {"schema": 1, "states": {"idle": "assets/tray-src/idle.svg",
                           "active": {"16": "assets/tray-src/active-16.png", "24": "assets/tray-src/active-24.png"},
                           "error": {"light": "assets/tray-src/error-light.svg", "dark": "assets/tray-src/error-dark.svg"}}}
A state's source is a path or a map of master size -> path; an SVG is rasterised exactly at every size, a PNG master is used as it is
at its own size and enlarged by a whole factor (nearest neighbour) for a size it divides: a size with no master that fits is an error,
never a blurry resample. {"light": ..., "dark": ...} gives separate artwork for light and dark taskbars; without it the dark set is
the light set recoloured through the token roles (a colour the tokens do not map is an error). State names are the project's own.
Writes under assets/tray/ (override with --out-dir):
  windows/<light|dark>/<state>-<px>.png   the windows-tray sizes, one set per taskbar theme (light = for a light taskbar)
  linux/<state>-<px>.png                  the linux-tray sizes, one palette (the light artwork; check the target panel)
  macos/<state>Template@2x.png            the apple-menubar-template size: black plus alpha, the glyph centred on the canvas
Then it writes qa/states.tray.json (every size and theme as a state set) and runs `states-check`: two states that look alike in
greyscale or silhouette fail the emit. Needs gate G3.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "lib"))
import svgtools  # noqa: E402
from _color import parse_hex  # noqa: E402
from _common import EXIT_USAGE, confine, data_dir, fail, main_guard, plugin_root, write_bytes_if_changed  # noqa: E402
from _emit import Emit  # noqa: E402
from px_lib import Img, from_png  # noqa: E402

CONFIG = "tray/tray.json"
SETS_FILE = "qa/states.tray.json"
GATE_TIMEOUT_S = 300
MSG_MAX = 250        # characters of a tool's message kept in a report row


def load_config(project: Path) -> dict:
    f = confine(project, CONFIG, what="tray config")
    if not f.is_file():
        fail(EXIT_USAGE, f"no tray config: {CONFIG} not found. Declare the states as described in `brand-creator emit tray --help`")
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
    except ValueError as e:
        fail(EXIT_USAGE, f"{CONFIG} is not valid JSON: {e}")
    states = doc.get("states") if isinstance(doc, dict) else None
    if doc.get("schema") != 1 or not isinstance(states, dict) or len(states) < 2:
        fail(EXIT_USAGE, f"{CONFIG}: needs {{\"schema\": 1, \"states\": {{name: source, ...}}}} with at least two states")
    for name, form in states.items():
        if not (isinstance(name, str) and name.replace("-", "").isalnum() and name[0].isalpha()):
            fail(EXIT_USAGE, f"{CONFIG}: state name {name!r} must be letters, digits and hyphens, starting with a letter")
        if not _form_ok(form) and not (isinstance(form, dict) and set(form) == {"light", "dark"} and all(_form_ok(v) for v in form.values())):
            fail(EXIT_USAGE, f"{CONFIG}: state {name!r}: a source is a path, a map of master size -> path, or {{\"light\": ..., \"dark\": ...}} of those")
    return states


def _form_ok(form) -> bool:
    if isinstance(form, str):
        return bool(form)
    return isinstance(form, dict) and bool(form) and all(k.isdigit() and isinstance(v, str) for k, v in form.items())


def forms(form) -> tuple[object, object | None]:
    """-> (light source, explicit dark source or None)."""
    if isinstance(form, dict) and set(form) == {"light", "dark"}:
        return form["light"], form["dark"]
    return form, None


def resolve(e: Emit, state: str, form, size: int, *, svg_recolour: dict | None = None) -> Img:
    """The state's artwork at exactly size x size px, from its masters (see the module doc)."""
    if isinstance(form, str):
        src = confine(e.project, form, what=f"state {state!r} source")
        if not src.is_file():
            fail(EXIT_USAGE, f"state {state!r}: {form} not found")
        if src not in e.rep.inputs:
            e.rep.inputs.append(src)
        if src.suffix.lower() == ".svg":
            text = src.read_text(encoding="utf-8")
            if svg_recolour is not None:
                try:
                    text = svgtools.recolor(text, svg_recolour)
                except svgtools.SvgError as err:
                    fail(2, f"state {state!r}: {form} cannot be recoloured for a dark taskbar ({err}); give {{\"light\": ..., \"dark\": ...}} sources")
            return from_png(e.png(svgtools.fit(text, size, size), size, size))
        if src.suffix.lower() != ".png":
            fail(EXIT_USAGE, f"state {state!r}: {form} is not a .png or .svg")
        img = from_png(src.read_bytes())
        if img.w != img.h:
            fail(EXIT_USAGE, f"state {state!r}: {form} is {img.w}x{img.h}; masters are square")
        masters = {img.w: img}
        return _scale(state, masters, size, form)
    masters = {}
    for k, path in form.items():
        src = confine(e.project, path, what=f"state {state!r} master {k}")
        if not src.is_file():
            fail(EXIT_USAGE, f"state {state!r}: {path} not found")
        if src not in e.rep.inputs:
            e.rep.inputs.append(src)
        img = from_png(src.read_bytes())
        if img.w != img.h or img.w != int(k):
            fail(EXIT_USAGE, f"state {state!r}: {path} is {img.w}x{img.h} but is listed as the {k} px master")
        masters[int(k)] = img
    return _scale(state, masters, size, ", ".join(form.values()))


def _scale(state: str, masters: dict[int, Img], size: int, what: str) -> Img:
    fits = [n for n in masters if size % n == 0]
    if not fits:
        fail(EXIT_USAGE, f"state {state!r}: no master fits {size} px (masters: {', '.join(map(str, sorted(masters)))} px; a master serves "
                         f"only the sizes it divides). Draw a {size} px master or give an SVG")
    n = max(fits)
    return masters[n] if n == size else masters[n].scaled(size // n)


def recolour(e: Emit, state: str, img: Img) -> Img:
    """Light artwork -> dark taskbar artwork: every opaque colour goes through the tokens' light-to-dark roles, exactly."""
    mapping, clash = e.role_map()
    out = Img(img.w, img.h)
    unmapped: dict[str, int] = {}
    for i in range(0, len(img.p), 4):
        r, g, b, a = img.p[i:i + 4]
        if not a:
            continue
        key = f"#{r:02x}{g:02x}{b:02x}"
        if key in clash or key not in mapping:
            unmapped[key] = unmapped.get(key, 0) + 1
            continue
        out.p[i:i + 4] = bytes((*parse_hex(mapping[key]), a))
    if unmapped:
        fail(2, f"state {state!r}: colours {', '.join(sorted(unmapped))} are not mapped light to dark by the token roles; "
                f"give the state {{\"light\": ..., \"dark\": ...}} sources")
    return out


def template(img: Img, w: int, h: int) -> Img:
    """Black plus alpha on a w x h canvas, the square glyph centred vertically (a macOS template image)."""
    if all(img.p[i] == 255 for i in range(3, len(img.p), 4)):
        fail(2, "a template image needs a transparent background; the state artwork is fully opaque")
    out = Img(w, h)
    oy = (h - img.h) // 2
    for y in range(img.h):
        for x in range(img.w):
            a = img.p[(y * img.w + x) * 4 + 3]
            if a:
                out.set(x, y + oy, (0, 0, 0, a))
    return out


def run_gate(e: Emit) -> None:
    exe = plugin_root() / "bin" / "brand-creator"
    try:
        cp = subprocess.run([str(exe), "--data", str(data_dir()), "states-check", "--project", str(e.project)], capture_output=True,
                            text=True, timeout=GATE_TIMEOUT_S, env=os.environ.copy())
    except subprocess.TimeoutExpired:
        e.rep.add("gate:states-check", "skipped", "states-check could not be run", detail=f"timed out after {GATE_TIMEOUT_S}s")
        return
    lines = [ln for ln in cp.stdout.splitlines() if ln.startswith("[FAIL]")]
    if cp.returncode == 0:
        e.rep.add("gate:states-check", "pass", "every pair of states differs in greyscale and silhouette in every set",
                  detail="assets/_checks/states.json")
    elif cp.returncode == 1:
        e.rep.add("gate:states-check", "fail", "two states read as the same state without colour", detail="; ".join(lines[:4]) or cp.stdout[-MSG_MAX:])
    else:
        e.rep.add("gate:states-check", "skipped", "states-check could not be run", detail=(cp.stderr.strip() or cp.stdout.strip())[-MSG_MAX:])


def main() -> int:
    e = Emit.begin("tray", __doc__)
    states = load_config(e.project)
    e.add_input(e.project / CONFIG)
    win, lin, mac = e.sizes("windows-tray"), e.sizes("linux-tray"), e.sizes("apple-menubar-template")
    ground = {"light": e.colour("light", "color.bg"), "dark": e.colour("dark", "color.bg")}
    sets = []

    def emit_set(setname: str, size: int, gnd: str, files: dict[str, str]) -> None:
        sets.append({"name": setname, "size": size, "ground": gnd, "states": files})

    for mode in ("light", "dark"):
        for s in win["px"]:
            files = {}
            for name, form in states.items():
                light_src, dark_src = forms(form)
                if mode == "light" or dark_src is None:
                    img = resolve(e, name, light_src, s)
                    if mode == "dark":
                        img = recolour(e, name, img)
                else:
                    img = resolve(e, name, dark_src, s)
                rel = f"{e.out}/windows/{mode}/{name}-{s}.png"
                e.slot(rel, img.png(), ["windows-tray"], slot=f"tray-windows-{mode}-{s}", size_px=s, qa=["states"],
                       note=f"{name} for a {mode} taskbar; masters, never a blurry resample")
                files[name] = rel
            emit_set(f"tray-windows-{mode}-{s}", s, ground[mode], files)
    for s in lin["px"]:
        files = {}
        for name, form in states.items():
            img = resolve(e, name, forms(form)[0], s)
            rel = f"{e.out}/linux/{name}-{s}.png"
            e.slot(rel, img.png(), ["linux-tray"], slot=f"tray-linux-{s}", size_px=s, qa=["states"], note=f"{name}, one palette (the light artwork)")
            files[name] = rel
        emit_set(f"tray-linux-{s}", s, ground["light"], files)
    files = {}
    for name, form in states.items():
        img = template(resolve(e, name, forms(form)[0], mac["width"]), mac["width"], mac["height"])
        rel = f"{e.out}/macos/{name}Template@{mac['scale']}x.png"
        e.slot(rel, img.png(), ["apple-menubar-template"], slot="tray-macos-template", size_px=(mac["width"], mac["height"]), qa=["states"],
               note=f"{name}: black plus alpha, template image")
        files[name] = rel
    emit_set("tray-macos-template", mac["width"], "#808080", files)

    doc = {"schema": 1, "generated_by": "brand-creator emit tray", "sets": sets}
    sf = confine(e.project, SETS_FILE, what="state sets")
    sf.parent.mkdir(parents=True, exist_ok=True)
    changed = write_bytes_if_changed(sf, (json.dumps(doc, indent=2) + "\n").encode())
    e.rep.add(f"file:{SETS_FILE}", "pass", "written" if changed else "unchanged", detail=f"{len(sets)} state sets for states-check")
    e.rep.inputs.append(sf)
    e.rep.add("states:names", "info", "state names from tray/tray.json", detail=", ".join(states))
    e.mf.save()
    run_gate(e)
    return e.finish()


main_guard(main)
