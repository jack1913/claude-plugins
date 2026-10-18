#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = ["jsonschema==4.26.0"]
# ///
"""brand-creator emit apple: the Apple icon family (macOS with Xcode only; exit 3 elsewhere, there is no fallback).

Writes under assets/apple/ (override with --out-dir) and records every file in assets/manifest.json.
  AppIcon.icon/                        Icon Composer document: icon.json plus layer SVGs (default, dark and tinted artwork), validated against the
                                       vendored giginet schema and validator (scripts/vendor/giginet-icon-composer) before anything is compiled
  compiled/ios/, macos/, watchos/      actool compiles the .icon once per platform and that is a HARD gate (exit 1 on failure): the fallback PNGs
                                       (ios) and the .icns (macos) ship, with the platform's partial Info.plist and the rendition list of the
                                       compiled Assets.car (compared by `assetutil --info`, never by bytes; the .car itself is not shipped)
  Assets.xcassets/AppIconVision.solidimagestack/   visionOS: a back and a front layer, 1024 px, inside the safe circle, compiled with actool (xros)
  watchos/Assets.xcassets/AppIcon.appiconset/   only when INVENTORY.md or --target lists watchOS: one opaque square at its own spec size, row apple-watchos-appiconset, status U (the system
                                       applies the circular mask), the mark inside the circle (a gate, before anything is written), compiled with actool
                                       for watchos; the size is passed explicitly: ictool exports at the size it is given, never at a default
  tvos/Assets.xcassets/AppIconTV.brandassets/   only when INVENTORY.md or --target lists tvOS: a layered image stack (a back and a front layer at the
                                       tvOS size, 2x), the mark inside the central share of the layer (a gate), compiled with actool for appletvos as a
                                       hard gate. ictool has no tvOS platform, so there is no preview. The App Store icon and the Top Shelf images are not written.
                                       Both packs read a spec row with status U (the margins): their files carry "UNVERIFIED, recheck" in the manifest note
  Assets.xcassets/AppIcon.appiconset/, legacy/AppIcon.icns   only when INVENTORY.md (Deployment targets) or --target shows iOS or macOS below 26:
                                       iOS 1024 light, dark, tinted and the ten macOS sizes; the .icns by iconutil; compiled with actool too
  Assets.xcassets/AccentColor.colorset, Colors.xcassets   the colour sets build_tokens wrote (byte copies)
  Assets.xcassets/MenuBarTemplate.imageset   the menu-bar template, black plus alpha, at the apple-menubar-template size
  marketing/AppStore-1024.png          flattened on the light ground, RGB with no alpha channel
  dmg/background.png, background@2x.png, layout.json   DMG window background (Chromium) and the icon positions it was drawn for
  store/frame-<name>.png, frames.json  App Store screenshot frames (Chromium): the mark, the name, one line of real copy and an empty screenshot area
  _preview/                            only with --previews: ictool renders (iOS, macOS, watchOS), never shipped
The drawing for the app icon is the one the band rule names for the layout size; --master-band picks another (a coarse-grid drawing for a
file the system shrinks) and needs --exemption. Sizes come from platform-specs.json only. Needs gate G3, Xcode (actool, iconutil, assetutil)
and, for the DMG and the frames, `brand-creator setup` (Chromium). Idempotent: a second run writes nothing.
"""
import contextlib
import importlib.util
import io
import json
import math
import plistlib
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "lib"))
import svgtools  # noqa: E402
from _color import parse_hex  # noqa: E402
from _common import EXIT_CANNOT, EXIT_FAIL, EXIT_USAGE, confine, fail, main_guard, plugin_root, run  # noqa: E402
from _emit import Emit, fill_template, render_card, version_below  # noqa: E402
from tierb import FIT_MARGIN, FIT_STEP, INK_TOLERANCE_PX, fit_share, ink_bbox, ink_far, label_note, label_report_row, unverified_rows  # noqa: E402
from determinism import car_renditions  # noqa: E402
from px_lib import Img, from_png  # noqa: E402
from pxio import png_color_type, png_size  # noqa: E402

CONTENT = 0.62        # share of the icon the mark fills (--content-fraction)
RADIUS = 0.2237       # the legacy macOS tile's corner radius as a share of its side
MENUBAR_CONTENT = 0.8  # share of the template canvas the silhouette fills
ACTOOL_TIMEOUT_S = 240
VENDOR = Path("scripts/vendor/giginet-icon-composer")
INFO = {"author": "xcode", "version": 1}
FRAME_UNIT_SHARE = 0.025   # a frame is laid out in units of this share of its shorter side
MSG_MAX = 250             # characters of a tool's message kept in a report row
DMG_APP, DMG_LINK = (0.25, 0.47), (0.75, 0.47)   # centres of the app icon and the Applications alias, as shares of the window


def preflight(a) -> None:
    if sys.platform != "darwin":
        fail(EXIT_CANNOT, "emit apple needs macOS with Xcode (actool, iconutil, assetutil); the .icon pipeline has no fallback on other systems. "
                          "Run it on a Mac; every other emitter works anywhere")
    if not shutil.which("xcrun") or subprocess.run(["xcrun", "--find", "actool"], capture_output=True, text=True).returncode != 0:
        fail(EXIT_CANNOT, "actool not found (no xcrun, or no Xcode selected): install Xcode and run `xcode-select -s <Xcode>`. "
                          "Run: brand-creator prereq --for apple")


def srgb(h: str) -> str:
    r, g, b = parse_hex(h)
    return f"srgb:{r / 255:.5f},{g / 255:.5f},{b / 255:.5f},1.00000"


def dump_json(obj) -> bytes:
    return (json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def validate_icon(pkg: Path) -> tuple[int, str]:
    """Run the vendored validator (schema + the Assets/ cross-check) on a written .icon; -> (exit code, its output)."""
    f = plugin_root() / VENDOR / "validate_icon.py"
    spec = importlib.util.spec_from_file_location("giginet_validate_icon", f)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        rc = mod.main([str(pkg)])
    return rc, buf.getvalue().strip()


class Compiled:
    def __init__(self, files: dict[str, bytes], plist: bytes, renditions: list[dict], warnings: list[str]):
        self.files, self.plist, self.renditions, self.warnings = files, plist, renditions, warnings


def actool(inputs: list[Path], platform: str, target: str, app_icon: str, what: str, device: str | None = None) -> Compiled:
    """Compile with the real toolchain. Any failure is exit 1 with actool's own words: this is a hard gate, never a warning.
    actool reports a catalogue problem (an image stack layer that does not fill the stack) under com.apple.actool.document.errors, with exit 0 and an
    Assets.car written anyway: both keys count as errors."""
    with tempfile.TemporaryDirectory(prefix="bc-actool-") as td:
        out = Path(td) / "out"
        out.mkdir()
        cmd = ["xcrun", "actool", *map(str, inputs), "--compile", str(out), "--platform", platform, "--minimum-deployment-target", target,
               "--app-icon", app_icon, "--output-partial-info-plist", str(out / "partial.plist"), "--output-format", "xml1"]
        if device:
            cmd += ["--target-device", device]
        try:
            cp = subprocess.run(cmd, capture_output=True, timeout=ACTOOL_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            fail(EXIT_FAIL, f"actool timed out after {ACTOOL_TIMEOUT_S}s compiling {what} for {platform}")
        doc = {}
        try:
            doc = plistlib.loads(cp.stdout)
        except Exception:  # noqa: BLE001 - actool prints plain text before the plist on some failures
            pass
        errors = [e.get("description", "") for e in doc.get("com.apple.actool.errors", [])]
        errors += [e.get("message") or e.get("description", "") for e in doc.get("com.apple.actool.document.errors", [])]
        errors = list(dict.fromkeys(errors))
        warns = [e.get("description", "") for e in doc.get("com.apple.actool.warnings", [])]
        warns += [e.get("message") or e.get("description", "") for e in doc.get("com.apple.actool.document.warnings", [])]
        warns = list(dict.fromkeys(warns))
        if cp.returncode != 0 or errors:
            said = (errors[0] if errors else (cp.stderr.decode("utf-8", "replace").strip() or cp.stdout.decode("utf-8", "replace").strip()))
            fail(EXIT_FAIL, f"actool failed compiling {what} for {platform} (exit {cp.returncode}): {said.splitlines()[0][:MSG_MAX] if said else 'no message'}")
        car = out / "Assets.car"
        if not car.is_file():
            fail(EXIT_FAIL, f"actool compiled {what} for {platform} without writing an Assets.car")
        rends = car_renditions(car)
        files = {p.name: p.read_bytes() for p in sorted(out.iterdir()) if p.is_file() and p.name not in ("Assets.car", "partial.plist")}
        plist = (out / "partial.plist").read_bytes() if (out / "partial.plist").is_file() else b""
        return Compiled(files, plist, rends, warns)


def icon_images(rends: list[dict]) -> list[dict]:
    return [r for r in rends if r.get("AssetType") == "Icon Image"]


def main() -> int:
    def args(ap):
        ap.add_argument("--content-fraction", type=float, default=CONTENT, help=f"share of the icon the mark fills (default {CONTENT})")
        ap.add_argument("--visionos-content-fraction", type=float, help="share of the visionOS layer the mark fills (default: --content-fraction; the circular mask "
                                                                        "is smaller than the square, so a mark that fills the square may need a lower value)")
        ap.add_argument("--watchos-content-fraction", type=float, help="share of the watchOS layout size the mark's box fills (default: the largest, up to --content-fraction, "
                                                                       "that keeps the mark inside the circle margin; the gate holds a value you set)")
        ap.add_argument("--tvos-content-fraction", type=float, help="share of the tvOS layer height the mark's box fills (default: the largest, up to --content-fraction, "
                                                                    "that keeps the mark inside the central share of the layer; the gate holds a value you set)")
        ap.add_argument("--master-band", help="band of the drawing used for the app icon (default: the band the layout size picks)")
        ap.add_argument("--exemption", help="one line: why --master-band differs from the picker (recorded in the manifest)")
        ap.add_argument("--app-icon-name", default="AppIcon", help="name of the icon in the compiled catalogue (default AppIcon)")
        ap.add_argument("--target", action="append", default=[], metavar="OS=VERSION", help="minimum OS of the target repo, for example iOS=17.0 (overrides INVENTORY.md)")
        ap.add_argument("--glass", action="store_true", help="leave the Liquid Glass effect on the layers (off by default: a flat brand mark)")
        ap.add_argument("--svg-mono", help="authored monochrome SVG for the menu-bar template (default: a black silhouette derived from the drawing)")
        ap.add_argument("--tagline", default="", help="one line on the App Store frames; must be a value in FACTS.md")
        ap.add_argument("--no-cards", action="store_true", help="do not write the DMG background and the store frames (they need Chromium)")
        ap.add_argument("--previews", action="store_true", help="also render ictool previews into _preview/ (never shipped, not in the manifest)")

    e = Emit.begin("apple", __doc__, add_args=args, preflight=preflight)
    app, ic = e.sizes("apple-app-icon"), e.sizes("apple-icon-composer")
    market, mac, vis, menubar = e.sizes("apple-marketing-icon"), e.sizes("apple-macos-iconset"), e.sizes("apple-visionos-stack"), e.sizes("apple-menubar-template")
    if e.a.exemption and not e.a.master_band:
        fail(EXIT_USAGE, "--exemption needs --master-band")
    tagline = e.require_fact(e.a.tagline, what="--tagline") if e.a.tagline else ""
    name = e.a.app_icon_name
    layout = app["layout_px"]
    content = e.a.content_fraction
    target = f"{ic['min_target']}.0"
    light_bg, dark_bg = e.colour("light", "color.bg"), e.colour("dark", "color.bg")
    base = e.out
    e.check_master_band(layout, e.a.master_band, e.a.exemption)
    master = e.drawing(layout, band=e.a.master_band)
    dark_art = e.dark_svg(master)
    e.rep.add("master:drawing", "info", "drawing used for the app icon", detail=f"{master.rel or 'the mark'} (band {master.band or 'none'})")

    # ---- 0. watchOS and tvOS, only for targets the repo lists: the rasters and their gates come first, so a mark outside the margin writes nothing
    all_targets = e.targets()
    watch_t, tv_t = all_targets.get("watchOS"), all_targets.get("tvOS")
    if watch_t or tv_t:
        wt_safe = e.sizes("apple-watch-tv-safe")
    if watch_t:
        wpx = e.sizes("apple-watchos-appiconset")["appiconset_px"]   # the pre-26 appiconset: its own U row, not the .icon layout canvas (watchos_px)
        w_limit = wt_safe["watchos_safe_circle"] * wpx / 2
        art_w = e.drawing(wpx)
        far_full = ink_far(e.png(svgtools.tile(art_w.svg, wpx, wpx, content=1.0), wpx, wpx))
        if not far_full:
            fail(EXIT_FAIL, f"the drawing {art_w.rel or 'of the mark'} has no ink: nothing to put in the watchOS icon")
        w_auto = e.a.watchos_content_fraction is None
        wc = fit_share(w_limit, far_full, content) if w_auto else e.a.watchos_content_fraction
        if wc <= 0:
            fail(EXIT_FAIL, f"the mark does not fit the watchOS circle margin even at the smallest size (its ink reaches {far_full:.0f} px from the centre at a box of 1.0, "
                            f"the limit is {w_limit:.0f} px). Nothing is written. Redraw the mark with a rounder silhouette")
        d_w, w_raw = e.tile_png(wpx, content=wc, ground=light_bg, flat=True)
        watch_png = from_png(w_raw).png_rgb()
        w_far = ink_far(watch_png, ground=parse_hex(light_bg))
        w_ok = w_far <= w_limit + INK_TOLERANCE_PX
        e.rep.add("check:watchOS circle", "pass" if w_ok else "fail", f"the mark stays inside {wt_safe['watchos_safe_circle']:g} of the watchOS circle",
                  detail=f"farthest ink pixel {w_far:.0f} px from the centre, limit {w_limit:.0f} px, box {wc:g} of the canvas ({'automatic' if w_auto else '--watchos-content-fraction'})"
                         + ("" if w_ok else "; lower --watchos-content-fraction"))
        if not w_ok:
            fail(EXIT_FAIL, f"the mark is outside the watchOS circle margin (ink {w_far:.0f} px from the centre, limit {w_limit:.0f}). Nothing is written. "
                            "Lower --watchos-content-fraction, or leave it out and the largest size that fits is chosen")
    else:
        e.rep.add("watchos", "info", "no watchOS pack", detail="INVENTORY.md lists no watchOS deployment target and no --target watchOS=<version> was given")
    if tv_t:
        tv = e.sizes("apple-tvos-stack")
        tw, th = tv["width"], tv["height"]
        t_half = (wt_safe["tvos_safe_share"] * tw / 2, wt_safe["tvos_safe_share"] * th / 2)
        art_t = e.drawing(max(tw, th))
        bb_full = ink_bbox(e.png(svgtools.tile(art_t.svg, tw, th, content=1.0), tw, th))
        if bb_full is None:
            fail(EXIT_FAIL, f"the drawing {art_t.rel or 'of the mark'} has no ink: nothing to put in the tvOS icon")
        hx, hy = max(tw / 2 - bb_full[0], bb_full[2] - tw / 2), max(th / 2 - bb_full[1], bb_full[3] - th / 2)
        t_auto = e.a.tvos_content_fraction is None
        tc = round(math.floor(min(content, t_half[0] / hx * FIT_MARGIN, t_half[1] / hy * FIT_MARGIN) / FIT_STEP) * FIT_STEP, 2) if t_auto else e.a.tvos_content_fraction
        if tc <= 0:
            fail(EXIT_FAIL, "the mark does not fit the tvOS layer margin even at the smallest size. Nothing is written")
        tv_front = e.png(svgtools.tile(art_t.svg, tw, th, content=tc), tw, th)
        tv_back = Img(tw, th, light_bg).png_rgb()
        bb = ink_bbox(tv_front)
        t_ok = bb is not None and all(abs(v - c0) <= lim + INK_TOLERANCE_PX for v, c0, lim in
                                      ((bb[0], tw / 2, t_half[0]), (bb[2], tw / 2, t_half[0]), (bb[1], th / 2, t_half[1]), (bb[3], th / 2, t_half[1])))
        e.rep.add("check:tvOS safe area", "pass" if t_ok else "fail", f"the mark stays inside the central {wt_safe['tvos_safe_share']:g} of the layer in both directions",
                  detail=f"ink box {bb}, box {tc:g} of the layer height ({'automatic' if t_auto else '--tvos-content-fraction'})" + ("" if t_ok else "; lower --tvos-content-fraction"))
        if not t_ok:
            fail(EXIT_FAIL, f"the mark is outside the tvOS margin (ink box {bb}). Nothing is written. Lower --tvos-content-fraction, or leave it out and the largest size that fits is chosen")
    else:
        e.rep.add("tvos", "info", "no tvOS pack", detail="INVENTORY.md lists no tvOS deployment target and no --target tvOS=<version> was given")

    def slot(rel, data, rows, **kw):
        """A file that is a drawing at a size: slot, size, band and who made the pixels go into the manifest."""
        kw.setdefault("drawing", master)
        kw.setdefault("exemption", e.a.exemption)
        if "downscale" in kw.get("qa", ()):
            kw.setdefault("downscale_source", f"{base}/marketing/AppStore-1024.png")   # the one master the system shrinks into this file
        return e.slot(f"{base}/{rel}", data, rows, **kw)

    def plain(rel, data, rows, *, slot, size=None, **kw):
        """A file that is not a drawing at a size (a document, a colour set, a rendered card): no band is claimed for it."""
        if size:
            kw["size"] = f"{size[0]}x{size[1]}"
        return e.put(f"{base}/{rel}", data, rows, slot=slot, **kw)

    # ---- 1. the .icon document
    try:
        tinted_art = svgtools.greyscale(dark_art)
        src_colours, grey_colours = svgtools.paint_colours(dark_art), svgtools.paint_colours(tinted_art)
    except svgtools.SvgError as err:
        fail(EXIT_FAIL, f"the tinted artwork cannot be derived from the dark drawing ({err})")
    if len(grey_colours) < len(src_colours):
        e.rep.add("tinted:greys", "warn", "two colours of the mark become the same grey in the tinted icon",
                  detail=f"{', '.join(src_colours)} -> {', '.join(grey_colours)}; the tinted icon cannot show the difference")
    layers = {"mark.svg": svgtools.tile(master.svg, layout, layout, content=content),
              "mark-dark.svg": svgtools.tile(dark_art, layout, layout, content=content),
              "mark-tinted.svg": svgtools.tile(tinted_art, layout, layout, content=content)}
    doc = {"fill-specializations": [{"value": {"solid": srgb(light_bg)}}, {"appearance": "dark", "value": {"solid": srgb(dark_bg)}},
                                    {"appearance": "tinted", "value": {"solid": "gray:0.00000,1.00000"}}],
           "groups": [{"layers": [{"glass": bool(e.a.glass), "name": "mark",
                                   "image-name-specializations": [{"value": "mark.svg"}, {"appearance": "dark", "value": "mark-dark.svg"},
                                                                  {"appearance": "tinted", "value": "mark-tinted.svg"}]}],
                       "lighting": "combined", "shadow": {"kind": "neutral", "opacity": 0.5}, "translucency": {"enabled": False, "value": 0.5}}],
           "supported-platforms": {"circles": ["watchOS"], "squares": "shared"}}
    pkg_rel = f"{base}/{name}.icon"
    plain(f"{name}.icon/icon.json", dump_json(doc), ["apple-app-icon", "apple-icon-composer"], slot="apple-icon-document",
          note="Icon Composer document: fill, one group, one layer; dark and tinted specialisations; glass " + ("on" if e.a.glass else "off"))
    for fname, svg in layers.items():
        slot(f"{name}.icon/Assets/{fname}", (svg + "\n").encode(), ["apple-app-icon"], slot="apple-icon-layer", size_px=layout, resampled_by="OURS",
             note={"mark.svg": "default appearance", "mark-dark.svg": "dark appearance", "mark-tinted.svg": "tinted appearance: the dark artwork in greys"}[fname])
    pkg = e.project / pkg_rel
    rc, said = validate_icon(pkg)
    e.rep.add("icon:schema", "pass" if rc == 0 else "fail", "the .icon validates against the vendored giginet schema and asset cross-check",
              detail=said.splitlines()[0] if said else f"exit {rc}")
    if rc != 0:
        e.rep.add("icon:schema:detail", "info", "validator output", detail=said[:600])
        e.mf.save()
        return e.finish()

    # ---- 2. actool per platform: a hard gate
    ios = actool([pkg], ic["actool_platforms"]["ios"], target, name, f"{name}.icon")
    mac_c = actool([pkg], ic["actool_platforms"]["macos"], target, name, f"{name}.icon")
    watch = actool([pkg], ic["actool_platforms"]["watchos"], target, name, f"{name}.icon")
    for tag, c in (("ios", ios), ("macos", mac_c), ("watchos", watch)):
        for w in c.warnings:
            e.rep.add(f"actool:{tag}:warning", "warn", "actool warning", detail=w[:MSG_MAX])
    have = {r.get("Appearance") for r in icon_images(ios.renditions) if r.get("PixelWidth") == layout}
    want = {None, "UIAppearanceDark", "ISAppearanceTintable"}
    e.rep.add("actool:ios", "pass" if want <= have else "fail", "the iOS catalogue holds the default, dark and tintable icon at the layout size",
              detail=f"{len(ios.renditions)} renditions; appearances at {layout} px: {sorted(str(x) for x in have)}")
    sizes_mac = sorted({r["PixelWidth"] for r in icon_images(mac_c.renditions)})
    icns = mac_c.files.get(f"{name}.icns", b"")
    e.rep.add("actool:macos", "pass" if layout in sizes_mac and icns[:4] == b"icns" else "fail",
              "the macOS catalogue holds the layout size and an .icns was written", detail=f"icon sizes {sizes_mac}; {name}.icns {len(icns)} bytes")
    watch_imgs = [r for r in icon_images(watch.renditions) if r.get("Idiom") == "watch"]
    e.rep.add("actool:watchos", "pass" if watch_imgs else "fail", "the watchOS catalogue holds a watch icon image",
              detail=f"{len(watch_imgs)} icon image(s), {sorted({r['PixelWidth'] for r in watch_imgs})} px; the HIG layout size {app['watchos_px']} is "
                     f"only an export size: pass it to ictool explicitly")
    for tag, c in (("ios", ios), ("macos", mac_c), ("watchos", watch)):
        plain(f"compiled/{tag}.renditions.json", dump_json(c.renditions), ["apple-icon-composer"], slot=f"apple-compiled-{tag}",
              resampled_by="SYS", note=f"assetutil --info rendition list of the {tag} Assets.car (the compare unit; the .car itself is not shipped)")
    for fname, data in sorted(ios.files.items()):
        if fname.endswith(".png"):
            px = png_size(data)
            slot(f"compiled/ios/{fname}", data, ["apple-icon-composer"], slot="apple-fallback-png", size_px=px, resampled_by="SYS", qa=["downscale"],
                 note=f"actool fallback for systems before 26 ({px[0]}x{px[1]}); the system shrinks one master")
    plain("compiled/ios/Info-icons.plist", ios.plist, ["apple-icon-composer"], slot="apple-icons-plist", resampled_by="SYS",
          note="CFBundleIcons entries actool wrote for the iOS target")
    slot(f"compiled/macos/{name}.icns", icns, ["apple-icon-composer"], slot="apple-icns", size_px=max(sizes_mac or [layout]), resampled_by="SYS",
         qa=["downscale"], note="actool .icns (up to 256 px with the Tahoe margin); for sizes above, build with the standalone icon behaviour in Xcode")
    with tempfile.TemporaryDirectory(prefix="bc-icns-") as td:
        f = Path(td) / "x.icns"
        f.write_bytes(icns)
        cp = subprocess.run(["iconutil", "-c", "iconset", str(f), "-o", str(Path(td) / "x.iconset")], capture_output=True, text=True)
        n = len(list((Path(td) / "x.iconset").glob("*.png"))) if cp.returncode == 0 else 0
    e.rep.add("check:icns opens", "pass" if n else "fail", "iconutil reads the actool .icns back", detail=f"{n} PNG renditions" if n else cp.stderr.strip()[:200])

    # ---- 3. marketing icon: flattened, no alpha channel
    d_m, m_png = e.tile_png(market["px"], content=content, ground=light_bg, flat=True, band=e.a.master_band)
    img = from_png(m_png)
    flat = img.png_rgb()
    slot("marketing/AppStore-1024.png", flat, ["apple-marketing-icon"], slot="apple-marketing-icon", size_px=market["px"], drawing=d_m, qa=["downscale"],
         note="opaque, RGB, no alpha channel; also the master to run `brand-creator downscale --source` on")
    e.rep.add("check:marketing icon no alpha", "pass" if png_color_type(flat) == 2 and png_size(flat) == (market["px"],) * 2 else "fail",
              "RGB colour type with no alpha channel, at the spec size", detail=f"colour type {png_color_type(flat)}, {png_size(flat)}")

    # ---- 4. visionOS solid image stack
    stack = "Assets.xcassets/AppIconVision.solidimagestack"
    vpx = vis["layer_px"]
    back_png = Img(vpx, vpx, light_bg).png_rgb()   # the back layer is the plain ground; the front layer is the mark alone, with alpha
    vcontent = e.a.visionos_content_fraction or content
    front_png = e.png(svgtools.tile(master.svg, vpx, vpx, content=vcontent), vpx, vpx)
    fimg = from_png(front_png)
    radius = vis["safe_circle"] * vpx / 2
    c0 = vpx / 2
    far = max((((i % vpx + 0.5 - c0) ** 2 + (i // vpx + 0.5 - c0) ** 2) ** 0.5 for i in range(vpx * vpx) if fimg.p[i * 4 + 3]), default=0.0)
    e.rep.add("check:visionOS safe circle", "pass" if far <= radius else "fail", f"the front layer stays inside {vis['safe_circle']:g} of the circular mask",
              detail=f"farthest ink pixel {far:.0f} px from the centre, limit {radius:.0f}" + ("" if far <= radius else "; lower --visionos-content-fraction"))
    for layer, png, rgb in (("Back", back_png, True), ("Front", front_png, False)):
        slot(f"{stack}/{layer}.solidimagestacklayer/Content.imageset/{layer.lower()}.png", png, ["apple-visionos-stack"], slot=f"visionos-{layer.lower()}",
             size_px=vpx, note=f"{layer} layer, {vpx} px, " + ("opaque ground" if rgb else "the mark with alpha"))
        plain(f"{stack}/{layer}.solidimagestacklayer/Content.imageset/Contents.json",
              dump_json({"info": INFO, "images": [{"filename": f"{layer.lower()}.png", "idiom": "vision", "scale": "2x"}]}), ["apple-visionos-stack"],
              slot=f"visionos-{layer.lower()}", note="imageset Contents.json: idiom vision, 2x")
        plain(f"{stack}/{layer}.solidimagestacklayer/Contents.json", dump_json({"info": INFO}), ["apple-visionos-stack"], slot=f"visionos-{layer.lower()}",
              note="layer Contents.json")
    plain(f"{stack}/Contents.json", dump_json({"info": INFO, "layers": [{"filename": "Front.solidimagestacklayer"}, {"filename": "Back.solidimagestacklayer"}]}),
          ["apple-visionos-stack"], slot="visionos-stack", note="front first, then back")

    # ---- 5. colour sets from build_tokens (byte copies) and the accent colour
    tok = e.project / "assets/tokens/Colors.xcassets"
    if not tok.is_dir():
        fail(EXIT_CANNOT, "assets/tokens/Colors.xcassets not found; run `brand-creator tokens` first (the colour sets come from build_tokens)")
    for f in sorted(tok.rglob("*")):
        if f.is_file():
            rel_in = f.relative_to(tok).as_posix()
            plain(f"Colors.xcassets/{rel_in}", f.read_bytes(), ["apple-app-icon"], slot="apple-colorset", note="byte copy of what build_tokens wrote")
    acc = tok / "accent.colorset" / "Contents.json"
    if acc.is_file():
        plain("Assets.xcassets/AccentColor.colorset/Contents.json", acc.read_bytes(), ["apple-app-icon"], slot="apple-accent-colorset",
              note="the accent role under the name Xcode reads as the app's accent colour")
    else:
        e.rep.add("colors:accent", "warn", "no accent colour set", detail="assets/tokens/Colors.xcassets has no accent.colorset; AccentColor was not written")
    plain("Assets.xcassets/Contents.json", dump_json({"info": INFO}), ["apple-app-icon"], slot="apple-catalog", note="catalogue root")

    # ---- 6. menu-bar template: black plus alpha
    try:
        if e.a.svg_mono:
            e.add_input(confine(e.project, e.a.svg_mono, what="--svg-mono"))
        mono_src = (confine(e.project, e.a.svg_mono, what="--svg-mono").read_text(encoding="utf-8") if e.a.svg_mono
                    else svgtools.mono(e.drawing(max(menubar["width"], menubar["height"])).svg))
    except svgtools.SvgError as err:
        fail(EXIT_FAIL, f"the menu-bar template: {err}")
    mw, mh = menubar["width"], menubar["height"]
    mb = e.png(svgtools.tile(mono_src, mw, mh, content=MENUBAR_CONTENT), mw, mh)
    mbi = from_png(mb)
    ink = [mbi.p[i:i + 4] for i in range(0, len(mbi.p), 4) if mbi.p[i + 3]]
    ok = bool(ink) and all(p[0] == p[1] == p[2] == 0 for p in ink) and mbi.p[3] == 0
    e.rep.add("check:menu-bar template", "pass" if ok else "fail", "black plus alpha on a transparent canvas", detail=f"{len(ink)} inked pixels")
    slot(f"Assets.xcassets/MenuBarTemplate.imageset/menubar@{menubar['scale']}x.png", mb, ["apple-menubar-template"], slot="apple-menubar-template",
         size_px=(mw, mh), drawing=None, note="template image, black plus alpha")
    plain("Assets.xcassets/MenuBarTemplate.imageset/Contents.json",
          dump_json({"images": [{"filename": f"menubar@{menubar['scale']}x.png", "idiom": "universal", "scale": f"{menubar['scale']}x"}], "info": INFO,
                     "properties": {"template-rendering-intent": "template"}}), ["apple-menubar-template"], slot="apple-menubar-template",
          note="template rendering intent")

    # ---- 7. legacy sets, only when the target repo supports an OS older than the .icon systems
    targets = e.targets()
    legacy_ios = "iOS" in targets and version_below(targets["iOS"], ic["min_target"])
    legacy_mac = "macOS" in targets and version_below(targets["macOS"], ic["min_target"])
    if not targets:
        e.rep.add("legacy", "info", "no legacy assets", detail="INVENTORY.md lists no deployment targets and no --target was given, so no appiconset or legacy .icns is written")
    elif not (legacy_ios or legacy_mac):
        legacy_scope = {k: v for k, v in targets.items() if k in ("iOS", "macOS")}   # watchOS and tvOS have their own packs (section 8b)
        who = "every target" if len(legacy_scope) == len(targets) else "every iOS and macOS target"
        e.rep.add("legacy", "info", "no legacy assets", detail=(f"{who} is {ic['min_target']} or later ({', '.join(f'{k} {v}' for k, v in legacy_scope.items())})"
                                                              if legacy_scope else "INVENTORY.md lists no iOS or macOS target; watchOS and tvOS have their own packs"))
    app_set = "Assets.xcassets/AppIcon.appiconset"
    if legacy_ios or legacy_mac:
        images = []
        if legacy_ios:
            lp = layout
            _d, light_png = e.tile_png(lp, content=content, ground=light_bg, flat=True, band=e.a.master_band)
            light_rgb = from_png(light_png).png_rgb()
            dark_png = e.png(svgtools.tile(dark_art, lp, lp, content=content), lp, lp)
            tint_png = from_png(e.png(svgtools.tile(tinted_art, lp, lp, bg="#000000", content=content), lp, lp, bg="#000000")).png_rgb()
            for tag, data, appearance in (("light", light_rgb, None), ("dark", dark_png, "dark"), ("tinted", tint_png, "tinted")):
                fn = f"AppIcon-iOS-{tag}-{lp}.png"
                slot(f"{app_set}/{fn}", data, ["apple-app-icon"], slot=f"apple-appiconset-ios-{tag}", size_px=lp, qa=["downscale"],
                     note={"light": "opaque, no alpha", "dark": "transparent ground (the system supplies it)", "tinted": "greyscale on black, opaque"}[tag])
                row = {"filename": fn, "idiom": "universal", "platform": "ios", "size": f"{lp}x{lp}"}
                if appearance:
                    row["appearances"] = [{"appearance": "luminosity", "value": appearance}]
                images.append(row)
        if legacy_mac:
            body = mac["body_px"] / mac["canvas_px"]
            by_px, named = {}, {}
            for pt in mac["points"]:
                for sc in mac["scales"]:
                    n = pt * sc
                    if n not in by_px:
                        d, by_px[n] = e.tile_png(n, content=content, radius=RADIUS, body=body, band=e.a.master_band)
                    fn = f"AppIcon-mac-{pt}x{pt}@{sc}x.png"
                    slot(f"{app_set}/{fn}", by_px[n], ["apple-macos-iconset"], slot="apple-appiconset-mac", size_px=n,
                         note=f"{pt} pt at {sc}x, rounded body, hand size", drawing=d)
                    images.append({"filename": fn, "idiom": "mac", "scale": f"{sc}x", "size": f"{pt}x{pt}"})
                    named[f"icon_{pt}x{pt}{'@' + str(sc) + 'x' if sc > 1 else ''}.png"] = by_px[n]
            with tempfile.TemporaryDirectory(prefix="bc-iconset-") as td:
                iconset = Path(td) / "AppIcon.iconset"
                iconset.mkdir()
                for fn, data in named.items():
                    (iconset / fn).write_bytes(data)
                out = Path(td) / "AppIcon.icns"
                run(["iconutil", "-c", "icns", str(iconset), "-o", str(out)])
                legacy_icns = out.read_bytes()
                back_dir = Path(td) / "back.iconset"
                run(["iconutil", "-c", "iconset", str(out), "-o", str(back_dir)])
                n_back = len(list(back_dir.glob("*.png")))
            want_n = len(mac["points"]) * len(mac["scales"])
            slot("legacy/AppIcon.icns", legacy_icns, ["apple-macos-iconset"], slot="apple-legacy-icns", size_px=max(by_px), resampled_by="OURS", drawing=None,
                 note=f"iconutil, {want_n} renditions")
            e.rep.add("check:legacy icns", "pass" if n_back == want_n else "fail", "iconutil reads every rendition back", detail=f"{n_back} of {want_n}")
        plain(f"{app_set}/Contents.json", dump_json({"images": images, "info": INFO}), ["apple-app-icon"], slot="apple-appiconset",
              note="pairs the iOS fallbacks and the macOS files")
        for key, plat in (("iOS", "iphoneos"), ("macOS", "macosx")):
            if (key == "iOS" and legacy_ios) or (key == "macOS" and legacy_mac):
                with tempfile.TemporaryDirectory(prefix="bc-legacy-") as td:   # the appiconset alone: the other assets are not for this platform
                    cat = Path(td) / "Assets.xcassets"
                    shutil.copytree(e.project / base / app_set, cat / "AppIcon.appiconset")
                    (cat / "Contents.json").write_bytes(dump_json({"info": INFO}))
                    c = actool([cat], plat, targets[key], name, f"{app_set}")
                for w in c.warnings:
                    e.rep.add(f"actool:legacy-{plat}:warning", "warn", "actool warning", detail=w[:MSG_MAX])
                e.rep.add(f"actool:legacy-{plat}", "pass" if icon_images(c.renditions) or any(r.get("AssetType") == "Image" for r in c.renditions) else "fail",
                          f"the {key} appiconset compiles for {key} {targets[key]}", detail=f"{len(c.renditions)} renditions")

    # ---- 8. visionOS compile (the catalogue with the stack, accent and colour sets)
    vc = actool([e.project / base / "Assets.xcassets", e.project / base / "Colors.xcassets"], ic["actool_platforms"]["visionos"], target,
                "AppIconVision", "Assets.xcassets (visionOS stack)")
    for w in vc.warnings:
        e.rep.add("actool:visionos:warning", "warn", "actool warning", detail=w[:MSG_MAX])
    stacks = [r for r in vc.renditions if r.get("AssetType") == "SolidImageStack"]
    imgs = [r for r in vc.renditions if r.get("AssetType") == "Image" and r.get("PixelWidth") == vpx]
    e.rep.add("actool:visionos", "pass" if stacks and len(imgs) >= 2 else "fail", "the solid image stack compiles for visionOS with its layers at the layer size",
              detail=f"{len(stacks)} stack, {len(imgs)} layer images at {vpx} px")
    plain("compiled/visionos.renditions.json", dump_json(vc.renditions), ["apple-visionos-stack"], slot="apple-compiled-visionos",
          resampled_by="SYS", note="assetutil --info rendition list of the visionOS Assets.car")

    # ---- 8b. watchOS and tvOS packs (Tier B: labelled while the margin row is unverified)
    def wt_put(rel, data, rows, *, slot_name, note, size_px=None, drawing=None, **kw):
        """A file of the watchOS or tvOS pack: labelled when a spec row it serves is U, and held by `check` (labelled: true in the manifest)."""
        u = unverified_rows(rows)
        kw.update(note=label_note(rows, note), labelled=True)
        if size_px is None:
            e.put(f"{base}/{rel}", data, rows, slot=slot_name, **kw)
        else:
            e.slot(f"{base}/{rel}", data, rows, slot=slot_name, size_px=size_px, drawing=drawing, exemption=None, **kw)
        label_report_row(e.rep, u)

    if watch_t:
        wrows = ["apple-watch-tv-safe", "apple-watchos-appiconset"]
        wset = f"watchos/Assets.xcassets/{name}.appiconset"
        wfile = f"{name}-watchOS-{wpx}.png"
        wt_put(f"{wset}/{wfile}", watch_png, wrows, slot_name="apple-watchos-icon", size_px=wpx, drawing=d_w, resampled_by="OURS",
               note=f"watchOS icon at {wpx} px (its own spec row, unverified; not the .icon layout size {app['watchos_px']}): an opaque square, the system applies the circular mask; the mark is {wc:g} of the canvas")
        wt_put(f"{wset}/Contents.json", dump_json({"images": [{"filename": wfile, "idiom": "universal", "platform": "watchos", "size": f"{wpx}x{wpx}"}], "info": INFO}), wrows,
               slot_name="apple-watchos-appiconset", note="single-size appiconset for watchOS")
        wt_put("watchos/Assets.xcassets/Contents.json", dump_json({"info": INFO}), wrows, slot_name="apple-catalog", note="watchOS catalogue root")
        wc_out = actool([e.project / base / "watchos/Assets.xcassets"], ic["actool_platforms"]["watchos"], watch_t, name, f"watchos/Assets.xcassets ({name}.appiconset)")
        for w_ in wc_out.warnings:
            e.rep.add("actool:watchos-appiconset:warning", "warn", "actool warning", detail=w_[:MSG_MAX])
        w_imgs = [r for r in icon_images(wc_out.renditions) if r.get("Idiom") == "watch" and r.get("PixelWidth") == wpx]
        e.rep.add("actool:watchos-appiconset", "pass" if w_imgs else "fail", f"the watchOS appiconset compiles for watchOS {watch_t} with an icon image at the appiconset size",
                  detail=f"{len(wc_out.renditions)} renditions; {len(w_imgs)} icon image(s) at {wpx} px")
        wt_put("compiled/watchos-appiconset.renditions.json", dump_json(wc_out.renditions), wrows, slot_name="apple-compiled-watchos-appiconset", resampled_by="SYS",
               note="assetutil --info rendition list of the watchOS appiconset's Assets.car")
        e.rep.add("watchos:icon", "info", "the .icon serves watchOS 26 and later too" if not version_below(watch_t, ic["min_target"]) else "watchOS below 26 uses this appiconset",
                  detail=f"the .icon above lists watchOS as a circle platform; ictool exports it only at the size it is given ({app['watchos_px']} px, passed with --previews)")
    if tv_t:
        trows = ["apple-tvos-stack", "apple-watch-tv-safe"]
        brand = f"tvos/Assets.xcassets/{name}{tv['brandassets_suffix']}.brandassets"
        stk = f"{brand}/{tv['stack']}.imagestack"
        for layer, png in (("Back", tv_back), ("Front", tv_front)):
            wt_put(f"{stk}/{layer}.imagestacklayer/Content.imageset/{layer.lower()}.png", png, trows, slot_name=f"tvos-{layer.lower()}", size_px=(tw, th), drawing=(art_t if layer == "Front" else None),
                   resampled_by="OURS", note=f"{layer} layer, {tw} x {th} px at {tv['scale']}x, " + ("opaque ground" if layer == "Back" else f"the mark with alpha, {tc:g} of the layer height"))
            wt_put(f"{stk}/{layer}.imagestacklayer/Content.imageset/Contents.json",
                   dump_json({"images": [{"filename": f"{layer.lower()}.png", "idiom": "tv", "scale": f"{tv['scale']}x"}], "info": INFO}), trows, slot_name=f"tvos-{layer.lower()}",
                   note="imageset Contents.json: idiom tv")
            wt_put(f"{stk}/{layer}.imagestacklayer/Contents.json", dump_json({"info": INFO}), trows, slot_name=f"tvos-{layer.lower()}", note="layer Contents.json")
        wt_put(f"{stk}/Contents.json", dump_json({"info": INFO, "layers": [{"filename": "Front.imagestacklayer"}, {"filename": "Back.imagestacklayer"}]}), trows,
               slot_name="tvos-stack", note="front first, then back")
        wt_put(f"{brand}/Contents.json", dump_json({"info": INFO, "assets": [{"filename": f"{tv['stack']}.imagestack", "idiom": "tv", "role": "primary-app-icon",
                                                                                "size": f"{tw // tv['scale']}x{th // tv['scale']}"}]}), trows,
               slot_name="tvos-brandassets", note="the app icon asset: one primary stack, no Top Shelf image")
        wt_put("tvos/Assets.xcassets/Contents.json", dump_json({"info": INFO}), trows, slot_name="apple-catalog", note="tvOS catalogue root")
        tv_name = f"{name}{tv['brandassets_suffix']}"
        tc_out = actool([e.project / base / "tvos/Assets.xcassets"], tv["actool_platform"], tv_t, tv_name, f"tvos/Assets.xcassets ({tv_name}.brandassets)", device=tv["actool_device"])
        for w_ in tc_out.warnings:
            e.rep.add("actool:tvos:warning", "warn", "actool warning", detail=w_[:MSG_MAX])
        t_stacks = [r for r in tc_out.renditions if r.get("AssetType") == "ImageStack"]
        t_imgs = [r for r in tc_out.renditions if r.get("AssetType") == "Image" and r.get("PixelWidth") == tw and r.get("PixelHeight") == th and "/" in str(r.get("Name", ""))]
        n_layers = len(t_imgs)
        e.rep.add("actool:tvos", "pass" if t_stacks and tv["layers_min"] <= n_layers <= tv["layers_max"] else "fail",
                  f"the image stack compiles for tvOS {tv_t} with {tv['layers_min']} to {tv['layers_max']} layers at the layer size",
                  detail=f"{len(t_stacks)} stack, {n_layers} layer image(s) at {tw} x {th} px")
        wt_put("compiled/tvos.renditions.json", dump_json(tc_out.renditions), trows, slot_name="apple-compiled-tvos", resampled_by="SYS",
               note="assetutil --info rendition list of the tvOS Assets.car")
        e.rep.add("tvos:other", "info", "not written for tvOS", detail="the App Store icon (a larger stack) and the Top Shelf images: this project has no verified size for them; "
                                                                      "ictool has no tvOS platform, so there is no preview either (open the stack in Xcode)")

    # ---- 9. cards: DMG background and store frames (Chromium)
    if e.a.no_cards:
        e.rep.add("cards", "info", "DMG background and store frames skipped", detail="--no-cards was given")
        e.keep("dmg", "store")   # skipped on purpose, not dropped: cards an earlier run wrote stay
    else:
        bg, fg = light_bg, e.colour("light", "color.text")
        muted = e.modes["light"].get("color.muted", fg)
        accent = e.modes["light"].get("color.accent", fg)
        mark_raw = re.sub(r"^\s*<\?xml[^>]*>\s*", "", master.svg)
        scratch = e.out + "/_build"
        dmg = e.sizes("apple-dmg-background")
        tpl = (plugin_root() / "templates" / "dmg-background.html").read_text(encoding="utf-8")
        for sc in dmg["scales"]:
            w, h = dmg["width"] * sc, dmg["height"] * sc
            html = fill_template(tpl, {"width": w, "height": h, "bg": bg, "fg": fg, "muted": muted, "accent": accent, "name": e.brand, "mark": mark_raw,
                                       "app_fx": DMG_APP[0], "app_fy": DMG_APP[1], "link_fx": DMG_LINK[0], "link_fy": DMG_LINK[1]})
            src = confine(e.project, f"{scratch}/dmg-{sc}x.html", what="card source")
            src.parent.mkdir(parents=True, exist_ok=True)
            src.write_text(html, encoding="utf-8")
            render_card(e.project, f"{scratch}/dmg-{sc}x.html", w, h, f"{scratch}/dmg-{sc}x.png", "light")
            data = (e.project / f"{scratch}/dmg-{sc}x.png").read_bytes()
            got = png_size(data)
            e.rep.add(f"check:dmg {sc}x size", "pass" if got == (w, h) else "fail", "PNG size equals the spec row times the scale", detail=f"{got[0]}x{got[1]}")
            plain(f"dmg/background{'' if sc == 1 else '@' + str(sc) + 'x'}.png", data, ["apple-dmg-background"], slot="apple-dmg-background", size=(w, h),
                  resampled_by="PAGE", note=f"window {dmg['width']}x{dmg['height']} at {sc}x; name, mark and an arrow only")
        layout_doc = {"window": [dmg["width"], dmg["height"]],
                      "app": [round(DMG_APP[0] * dmg["width"]), round(DMG_APP[1] * dmg["height"])],
                      "applications": [round(DMG_LINK[0] * dmg["width"]), round(DMG_LINK[1] * dmg["height"])]}
        plain("dmg/layout.json", dump_json(layout_doc), ["apple-dmg-background"], slot="apple-dmg-layout",
              note="icon centres (px, 1x) the background was drawn for; give them to the DMG builder")
        frames_spec = e.sizes("apple-store-frames")["frames"]
        tpl = (plugin_root() / "templates" / "store-frame.html").read_text(encoding="utf-8")
        frames_doc = {}
        for fr in frames_spec:
            w, h = fr["width"], fr["height"]
            unit = min(w, h) * FRAME_UNIT_SHARE
            landscape = w > h
            head_h = unit * (6 if landscape else 8)
            sx = unit * 2
            slot_y = unit * 2 + head_h + unit
            rect = {"x": round(sx), "y": round(slot_y), "w": round(w - 2 * sx), "h": round(h - slot_y - 2 * unit)}
            html = fill_template(tpl, {"width": w, "height": h, "bg": bg, "fg": fg, "muted": muted, "accent": accent, "name": e.brand, "tagline": tagline,
                                       "mark": mark_raw, "unit": f"{unit:g}", "head_x": round(sx), "head_y": round(unit * 2), "head_h": round(head_h),
                                       "slot_x": rect["x"], "slot_y": rect["y"], "slot_w": rect["w"], "slot_h": rect["h"]})
            src = confine(e.project, f"{scratch}/frame-{fr['name']}.html", what="card source")
            src.write_text(html, encoding="utf-8")
            render_card(e.project, f"{scratch}/frame-{fr['name']}.html", w, h, f"{scratch}/frame-{fr['name']}.png", "light")
            data = (e.project / f"{scratch}/frame-{fr['name']}.png").read_bytes()
            got = png_size(data)
            e.rep.add(f"check:frame {fr['name']} size", "pass" if got == (w, h) else "fail", "PNG size equals the spec row", detail=f"{got[0]}x{got[1]}")
            plain(f"store/frame-{fr['name']}.png", data, ["apple-store-frames"], slot=f"apple-store-frame-{fr['name']}", size=(w, h), resampled_by="PAGE",
                  note="frame only: mark, name" + (", one line of real copy" if tagline else "") + ", empty screenshot area")
            frames_doc[fr["name"]] = {"size": [w, h], "screenshot_area": rect}
        plain("store/frames.json", dump_json(frames_doc), ["apple-store-frames"], slot="apple-store-frames",
              note="where the real screenshot goes in each frame (px)")
        if not tagline:
            e.rep.add("frames:copy", "info", "no line of copy on the frames", detail="--tagline (a FACTS.md value) adds one; nothing is invented")

    # ---- 10. ictool previews (never shipped)
    if e.a.previews:
        xc = subprocess.run(["xcode-select", "-p"], capture_output=True, text=True).stdout.strip()
        ictool = Path(xc).parent / "Applications/Icon Composer.app/Contents/Executables/ictool"
        if not ictool.is_file():
            e.rep.add("previews", "skipped", "ictool not found", detail=f"{ictool}; install Icon Composer with Xcode 26 or later")
        else:
            pdir = confine(e.project, f"{base}/_preview", what="preview folder")
            pdir.mkdir(parents=True, exist_ok=True)
            n = 0
            for plat in ic["ictool_platforms"]:
                px = app["watchos_px"] if plat == "watchOS" else layout
                for rend in ic["renditions"]:
                    out = pdir / f"{plat}-{rend}.png"
                    cp = subprocess.run([str(ictool), str(pkg), "--export-image", "--output-file", str(out), "--platform", plat, "--rendition", rend,
                                         "--width", str(px), "--height", str(px), "--scale", "1"], capture_output=True, text=True)
                    if cp.returncode != 0:
                        e.rep.add(f"preview:{plat}-{rend}", "fail", "ictool renders the .icon", detail=(cp.stderr or cp.stdout).strip()[:200])
                    else:
                        n += 1
            e.rep.add("previews", "info", "ictool previews written (masked by the system shape; not the marketing icon, not shipped)", detail=f"{n} PNG(s) in {base}/_preview/")

    e.rep.add("downscale:run", "info", "run the downscale gate on the master the system shrinks",
              detail=f"brand-creator downscale --source {base}/marketing/AppStore-1024.png   (rows marked qa: downscale need a current passing report)")
    return e.finish()


main_guard(main)
