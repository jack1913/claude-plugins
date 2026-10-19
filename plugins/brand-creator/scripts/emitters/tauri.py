#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow==11.3.0"]
# ///
"""brand-creator emit tauri: the icons folder of a Tauri app.

Writes under assets/tauri/ (override with --out-dir), laid out as src-tauri/icons/, and records every file in assets/manifest.json.
  the PNG files of the tauri-icons spec row (file name -> px), each drawn by the band rule
  icon.ico                                           the spec row's layer order (32 first, as Tauri expects), PNG-compressed
  icon.icns                                          the ten macOS sizes of the apple-macos-iconset row, on the padded macOS body
The icon is a rounded tile in the brand's light ground with the mark inside (--content, --radius). SVG is always rasterised with resvg.
--renderer picks the .icns writer: on macOS the default is `iconutil` (the system tool, all ten renditions); `--renderer pillow` writes the
.icns with Pillow instead (no 16 px entry: Pillow's writer has none), and off macOS it is the only way (explicit, recorded in the report);
without it off macOS the emit exits 3. Needs gate G3.
"""
import io
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "lib"))
from _common import EXIT_CANNOT, main_guard, run  # noqa: E402
from _emit import Emit, fail  # noqa: E402
from pxio import png_size, read_ico_sizes, write_ico  # noqa: E402

CONTENT = 0.62   # share of the tile the mark fills
RADIUS = 0.2237  # corner radius as a share of the tile's side (the macOS icon curve, approximated)


def icns_iconutil(pngs: dict[str, bytes]) -> bytes:
    if sys.platform != "darwin" or not shutil.which("iconutil"):
        fail(EXIT_CANNOT, "iconutil is not available (it ships with macOS). Pass --renderer pillow to write the .icns with Pillow "
                          "(explicit opt-in; no 16 px entry), or run on macOS")
    with tempfile.TemporaryDirectory(prefix="bc-iconset-") as td:
        iconset = Path(td) / "icon.iconset"
        iconset.mkdir()
        for name, data in pngs.items():
            (iconset / name).write_bytes(data)
        out = Path(td) / "icon.icns"
        run(["iconutil", "-c", "icns", str(iconset), "-o", str(out)])
        return out.read_bytes()


def icns_pillow(by_px: dict[int, bytes]) -> bytes:
    from PIL import Image
    big = max(by_px)
    im = Image.open(io.BytesIO(by_px[big])).convert("RGBA")
    rest = [Image.open(io.BytesIO(by_px[s])).convert("RGBA") for s in sorted(by_px) if s != big]
    buf = io.BytesIO()
    im.save(buf, format="ICNS", append_images=rest)
    return buf.getvalue()


def main() -> int:
    def args(ap):
        ap.add_argument("--content", type=float, default=CONTENT, help=f"share of the tile the mark fills (default {CONTENT})")
        ap.add_argument("--radius", type=float, default=RADIUS, help=f"tile corner radius as a share of its side (default {RADIUS})")

    e = Emit.begin("tauri", __doc__, add_args=args)
    e.raster_renderer = "resvg"
    pillow = e.a.renderer == "pillow"
    e.rep.renderer = "resvg (SVG); " + ("Pillow (.icns, explicit --renderer pillow)" if pillow else "iconutil (.icns)")
    icons, mac = e.sizes("tauri-icons"), e.sizes("apple-macos-iconset")
    base = f"{e.out}/src-tauri/icons"

    for fname, px in icons["png"].items():
        d, data = e.tile_png(px, content=e.a.content, radius=e.a.radius)
        e.slot(f"{base}/{fname}", data, ["tauri-icons"], slot=f"tauri-{fname}", size_px=px, drawing=d, note="rounded tile, full bleed")
        got = png_size(data)
        e.rep.add(f"check:{fname} size", "pass" if got == (px, px) else "fail", "PNG size equals the spec row", detail=f"{got[0]}x{got[1]}")

    layers, bands = [], {}
    for px in icons["ico_order"]:
        d, data = e.tile_png(px, content=e.a.content, radius=e.a.radius)
        layers.append(data)
        bands[str(px)] = d.band
    ico = write_ico(layers)
    e.put(f"{base}/icon.ico", ico, ["tauri-icons"], slot="tauri-icon.ico", size=f"{max(icons['ico_order'])}x{max(icons['ico_order'])}",
          resampled_by="OURS", note="PNG-in-ICO, the first layer is the one Tauri reads first", layers=list(icons["ico_order"]), layer_bands=bands)
    got = [w for w, _h in read_ico_sizes(ico)]
    e.rep.add("check:icon.ico layer order", "pass" if got == icons["ico_order"] else "fail", "layers in the spec order, 32 first",
              detail=f"{got} vs {icons['ico_order']}")

    body = mac["body_px"] / mac["canvas_px"]
    named, by_px, bands = {}, {}, {}
    for pt in mac["points"]:
        for sc in mac["scales"]:
            n = pt * sc
            if n not in by_px:
                d, data = e.tile_png(n, content=e.a.content, radius=e.a.radius, body=body)
                by_px[n], bands[str(n)] = data, d.band
            named[f"icon_{pt}x{pt}{'@' + str(sc) + 'x' if sc > 1 else ''}.png"] = by_px[n]
    if pillow:
        icns = icns_pillow(by_px)
        note = "Pillow writer (explicit --renderer pillow): no 16 px entry"
    else:
        icns = icns_iconutil(named)
        note = "iconutil: ten renditions"
    e.put(f"{base}/icon.icns", icns, ["tauri-icons", "apple-macos-iconset"], slot="tauri-icon.icns", resampled_by="OURS",
          note=f"{note}; padded body, rounded tile", layer_bands=bands)
    e.rep.add("check:icon.icns", "pass" if icns[:4] == b"icns" and len(icns) == int.from_bytes(icns[4:8], "big") else "fail",
              "an icns container whose length field matches", detail=note)
    return e.finish()


main_guard(main)
