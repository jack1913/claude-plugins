#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator emit web: favicon, icon.svg, apple-touch, PWA icons, manifest and the <head> snippet.

Writes under assets/web/ (override with --out-dir) and records every file in assets/manifest.json.
  favicon.ico          layers from the spec row, at a stable URL (never fingerprinted); every layer is drawn by the size-band rule
                       (qa/rules.json) for its own size, so the 16 px layer is the hand drawing, not the fine vector shrunk
  icon.svg             the mark; switches to the dark artwork with prefers-color-scheme. One scalable file cannot carry a
                       drawing per size: it is the default mark (the browser shows the .ico layers for the tab only where it prefers them)
  apple-touch-icon.png opaque ground (iOS paints transparency black)
  icons/               PWA any-purpose icons, a separate maskable icon (content inside the safe circle), monochrome; each is
                       drawn by the band rule for its size
  site.webmanifest, head.html
Only files referenced from HTML or the manifest carry a content fingerprint (?v=<8 hex>), and it changes only when the
bytes change. Sizes come from platform-specs.json only. Needs gate G3. Idempotent: a second run writes nothing.
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "lib"))
import svgtools  # noqa: E402
from _color import parse_hex  # noqa: E402
from _common import EXIT_USAGE, confine, fail, main_guard  # noqa: E402
from _emit import Emit, need_colors  # noqa: E402
from pxio import png_size, read_ico_sizes, read_png, write_ico  # noqa: E402

APPLE_TOUCH_CONTENT = 0.7  # share of the touch icon the mark may fill; iOS rounds the corners itself


def v8(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:8]


def main() -> int:
    def args(ap) -> None:
        ap.add_argument("--svg-mono", help="authored monochrome SVG for the PWA monochrome icon (default: a black silhouette derived from the drawing for that size)")
        ap.add_argument("--base-path", default="/", help="URL prefix of the site root in head.html and the manifest (default /)")

    e = Emit.begin("web", __doc__, add_args=args)
    a = e.a
    name = e.brand
    (bg_l,) = need_colors(e.modes, "light", "color.bg")
    (bg_d,) = need_colors(e.modes, "dark", "color.bg")
    base = a.base_path if a.base_path.endswith("/") else a.base_path + "/"
    if not base.startswith("/"):
        fail(EXIT_USAGE, "--base-path must start with /")
    out, rep = e.out, e.rep

    fav, favset, pwa = e.sizes("favicon-search"), e.sizes("favicon-set"), e.sizes("pwa-manifest")
    mono_path = None
    if a.svg_mono:
        mono_path = confine(e.project, a.svg_mono, what="--svg-mono")
        e.add_input(mono_path)
    light, dark = e.light, e.dark

    def put(relpath: str, data: bytes, rows: list[str], **extra) -> None:
        e.put(f"{out}/{relpath}", data, rows, **extra)

    def icon(relpath: str, data: bytes, rows: list[str], size_px: int, d, slot: str, **extra) -> None:
        e.slot(f"{out}/{relpath}", data, rows, slot=slot, size_px=size_px, drawing=d, width=size_px, height=size_px, **extra)

    # favicon.ico: stable URL, layers from the spec, each layer drawn by the band rule for its size
    layers, bands, drawings = [], {}, {}
    for s in favset["ico_layers"]:
        d = e.drawing(s)
        drawings[s] = d
        layers.append(e.png(svgtools.fit(d.svg, s, s), s, s))
        bands[str(s)] = d.band
    ico = write_ico(layers)
    big = max(favset["ico_layers"])
    e.slot(f"{out}/favicon.ico", ico, ["favicon-set", "favicon-search"], slot="favicon-ico", size_px=big, drawing=drawings[big],
           layers=list(favset["ico_layers"]), layer_bands=bands, note="each layer is drawn for its own size by the band rule")
    got = read_ico_sizes(ico)
    want = [(s, s) for s in favset["ico_layers"]]
    rep.add("check:favicon.ico layers", "pass" if got == want else "fail", "layer sizes equal the spec row",
            detail=f"{got} vs {want}")
    if max(favset["ico_layers"]) < fav["recommended_min_px"]:
        rep.add("check:favicon.ico size", "warn", "Google Search recommends more than the largest layer",
                detail=f"largest layer {max(favset['ico_layers'])}px, recommended {fav['recommended_min_px']}px")

    # icon.svg with prefers-color-scheme
    icon_svg = svgtools.combine_scheme(light, dark).encode()
    put("icon.svg", icon_svg, ["favicon-set"], slot="favicon-svg", resampled_by="PAGE", note="one scalable file: the default mark, not a per-size drawing")
    if dark is None:
        rep.add("note:icon.svg", "warn", "no dark artwork", detail="icon.svg has no prefers-color-scheme switch because no --svg-dark was found")

    # apple-touch
    s_apple = favset["apple_touch"]
    d_at = e.drawing(s_apple)
    at = e.png(svgtools.fit(d_at.svg, s_apple, s_apple, box=(s_apple * APPLE_TOUCH_CONTENT, s_apple * APPLE_TOUCH_CONTENT), bg=bg_l), s_apple, s_apple)
    icon("apple-touch-icon.png", at, ["favicon-set"], s_apple, d_at, "apple-touch-icon")
    _w, _h, px = read_png(at)
    rep.add("check:apple-touch opaque", "pass" if all(px[i] == 255 for i in range(3, len(px), 4)) else "fail",
            "no transparency (iOS paints it black)")

    # PWA icons
    icons = []
    for s in pwa["any"]:
        d = e.drawing(s)
        data = e.png(svgtools.fit(d.svg, s, s), s, s)
        icon(f"icons/icon-{s}.png", data, ["pwa-manifest"], s, d, "pwa-icon-any")
        icons.append({"src": f"{base}icons/icon-{s}.png?v={v8(data)}", "sizes": f"{s}x{s}", "type": "image/png", "purpose": "any"})
    s_m, frac = pwa["maskable"], pwa["maskable_safe_radius"]
    d_m = e.drawing(s_m)
    mk = e.png(svgtools.fit_in_circle(d_m.svg, s_m, frac, bg=bg_l), s_m, s_m)
    icon(f"icons/maskable-{s_m}.png", mk, ["pwa-manifest"], s_m, d_m, "pwa-icon-maskable")
    icons.append({"src": f"{base}icons/maskable-{s_m}.png?v={v8(mk)}", "sizes": f"{s_m}x{s_m}", "type": "image/png", "purpose": "maskable"})
    w, h, px = read_png(mk)
    bgc = parse_hex(bg_l)
    cx = cy = (w - 1) / 2
    outside = 0
    for i in range(w * h):
        r, g, b, al = px[i * 4:i * 4 + 4]
        if max(abs(r - bgc[0]), abs(g - bgc[1]), abs(b - bgc[2])) > 8 and ((i % w - cx) ** 2 + (i // w - cy) ** 2) ** 0.5 > frac * w + 1.5:
            outside += 1
    rep.add("check:maskable safe zone", "pass" if outside == 0 else "fail", "content inside the safe circle",
            detail="all mark pixels inside" if outside == 0 else f"{outside} mark pixels outside the {frac:g} radius circle")
    s_mono = pwa["monochrome"]
    d_mono = e.drawing(s_mono)
    try:
        mono_src = mono_path.read_text(encoding="utf-8") if mono_path else svgtools.mono(d_mono.svg)
    except svgtools.SvgError as err:
        rep.add("icons:monochrome", "fail", "monochrome icon", detail=str(err))
        mono_src = None
    if mono_src is not None:
        mn = e.png(svgtools.fit(mono_src, s_mono, s_mono), s_mono, s_mono)
        icon(f"icons/monochrome-{s_mono}.png", mn, ["pwa-manifest"], s_mono, d_mono, "pwa-icon-monochrome")
        icons.append({"src": f"{base}icons/monochrome-{s_mono}.png?v={v8(mn)}", "sizes": f"{s_mono}x{s_mono}", "type": "image/png", "purpose": "monochrome"})
        if not mono_path:
            rep.add("note:monochrome", "warn", "derived silhouette", detail="the monochrome icon is a black silhouette of the drawing for its size; supply --svg-mono when knockouts matter")

    # manifest + head snippet
    manifest = {"name": name, "short_name": name, "icons": icons, "theme_color": bg_l, "background_color": bg_l}
    mbytes = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode()
    put("site.webmanifest", mbytes, ["pwa-manifest"])
    head = "\n".join([
        "<!-- Generated by brand-creator emit web. Paste into <head>. -->",
        f'<link rel="icon" href="{base}favicon.ico" sizes="{favset["ico_html_sizes"]}">',
        f'<link rel="icon" href="{base}icon.svg?v={v8(icon_svg)}" type="image/svg+xml">',
        f'<link rel="apple-touch-icon" href="{base}apple-touch-icon.png?v={v8(at)}">',
        f'<link rel="manifest" href="{base}site.webmanifest?v={v8(mbytes)}">',
        f'<meta name="theme-color" content="{bg_l}" media="(prefers-color-scheme: light)">',
        f'<meta name="theme-color" content="{bg_d}" media="(prefers-color-scheme: dark)">',
        ""]).encode()
    put("head.html", head, ["favicon-set", "pwa-manifest"])
    rep.add("check:favicon.ico stable URL", "pass" if b"favicon.ico?" not in head and f'href="{base}favicon.ico"'.encode() in head else "fail",
            "/favicon.ico is referenced without a fingerprint")

    # dimensions read back from the files on disk
    for ic in icons:
        f = e.project / out / ic["src"].replace(base, "", 1).split("?")[0]
        sw, sh = png_size(f.read_bytes())
        want = int(ic["sizes"].split("x")[0])
        rep.add(f"check:{f.name} size", "pass" if (sw, sh) == (want, want) else "fail", "PNG size equals the manifest", detail=f"{sw}x{sh}")

    return e.finish()


main_guard(main)
