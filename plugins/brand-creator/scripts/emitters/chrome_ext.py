#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator emit chrome-ext: a Chrome extension's icons, store icon and promotional tiles.

Writes under assets/chrome-ext/ (override with --out-dir) and records every file in assets/manifest.json.
  icons/icon-<px>.png                  the manifest icons from the chrome-ext-icons spec row (PNG only: WebP and SVG are not supported); each is drawn by
                                       the size-band rule for its own size. The store-icon size carries the Web Store rule: artwork inside the
                                       store-art box, the rest transparent padding (the file the store shows is this manifest file)
  store/store-icon-<px>.png            the same pixels, as the file the Web Store listing asks for
  store/promo-small-<w>x<h>.png        the small promotional tile (required by the store), from templates/card.html (or --template), opaque
  store/promo-marquee-<w>x<h>.png      the marquee tile (optional in the store), opaque
  manifest.icons.json                  the "icons" object to merge into manifest.json
Gate: the store icon's artwork sits inside the art box with transparent padding on every side. Screenshots show the real product and are not written.
Every size comes from platform-specs.json. A file that serves a row of status U carries the label "UNVERIFIED, recheck". Full tier only.
Needs gate G3 and `brand-creator setup` (the promo tiles are rendered by Chromium). Idempotent.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "lib"))
import svgtools  # noqa: E402
from _common import EXIT_FAIL, EXIT_USAGE, confine, fail, main_guard, plugin_root  # noqa: E402
from _emit import (CARD_RULE_RADIUS, add_logo_arg, card_art, card_lettering, card_lettering_setup, card_mark_size, fill_template,  # noqa: E402
                   mark_accent, mark_tagline, render_card, rule_radius)
from pxio import png_color_type, png_size  # noqa: E402
from px_lib import from_png  # noqa: E402
from tierb import INK_TOLERANCE_PX, TierBEmit, ink_bbox  # noqa: E402


def main() -> int:
    def args(ap) -> None:
        ap.add_argument("--template", help="card template of the promo tiles (default: templates/card.html in the plugin)")
        add_logo_arg(ap, cards=True)
        ap.add_argument("--tagline", default="", help="one line on the promo tiles (must be a value in FACTS.md)")

    e = TierBEmit.begin("chrome-ext", __doc__, add_args=args)
    a, rep, out = e.a, e.rep, e.out
    ic, promo = e.sizes("chrome-ext-icons"), e.sizes("chrome-ext-promo")
    if a.tagline:
        e.require_fact(a.tagline, what="--tagline")
    if [f.lower() for f in ic["formats"]] != ["png"]:
        fail(EXIT_FAIL, f"the chrome-ext-icons row lists formats {ic['formats']}; this emitter writes PNG only")

    store, art = ic["store_icon"], ic["store_art"]
    pad = (store - art) // 2
    icons, store_png = {}, None
    for s in ic["manifest"]:
        d = e.drawing(s)
        svg = svgtools.tile(d.svg, s, s, content=art / s) if s == store else svgtools.fit(d.svg, s, s)
        data = e.png(svg, s, s)
        icons[str(s)] = f"icons/icon-{s}.png"
        e.slot(f"{out}/icons/icon-{s}.png", data, ["chrome-ext-icons"], slot=f"chrome-ext-icon-{s}", size_px=s, drawing=d,
               note=f"manifest icon, {s} px PNG" + (f"; the Web Store rule: {art} px of artwork in {store}, {pad} px of transparent padding per side" if s == store else ""))
        got = png_size(data)
        rep.add(f"check:icon-{s} size", "pass" if got == (s, s) else "fail", "PNG size equals the manifest size", detail=f"{got[0]}x{got[1]}")
        if s == store:
            store_png, store_d = data, d
    if store_png is None:
        fail(EXIT_FAIL, f"the manifest sizes {ic['manifest']} do not include the store icon size {store}")
    box = ink_bbox(store_png)
    ok = box is not None and box[0] >= pad - INK_TOLERANCE_PX and box[1] >= pad - INK_TOLERANCE_PX and \
        box[2] <= store - pad + INK_TOLERANCE_PX and box[3] <= store - pad + INK_TOLERANCE_PX
    rep.add("check:store icon padding", "pass" if ok else "fail", f"the artwork is inside the {art} px box with {pad} px of transparent padding per side",
            detail=f"ink box {box}")
    e.slot(f"{out}/store/store-icon-{store}.png", store_png, ["chrome-ext-icons"], slot="chrome-web-store-icon", size_px=store, drawing=store_d,
           note=f"Web Store icon: {art} px of artwork in {store} px, transparent padding; the same pixels as icons/icon-{store}.png")
    e.put(f"{out}/manifest.icons.json", (json.dumps({"icons": icons}, indent=2) + "\n").encode(), ["chrome-ext-icons"], slot="chrome-ext-manifest-icons",
          note="the icons object for manifest.json, paths relative to the extension root")

    # promo tiles: cards from the template, opaque
    tpl_path = Path(a.template).expanduser().resolve() if a.template else plugin_root() / "templates" / "card.html"
    if not tpl_path.is_file():
        fail(EXIT_USAGE, f"card template not found: {tpl_path}")
    template = tpl_path.read_text(encoding="utf-8")
    found, layout = card_lettering_setup(rep, e.project, a, template, tpl_path.name, e.mark_id)
    tagline = mark_tagline(e.project, e.mark, a.tagline, rep.inputs)
    ground, fg = e.colour("light", "color.bg"), e.colour("light", "color.text")
    for key in ("small", "marquee"):
        w, h = promo[key]["width"], promo[key]["height"]
        d = e.drawing(max(w, h))
        values = {"width": w, "height": h, "bg": ground, "fg": fg, "muted": e.modes["light"].get("color.muted", fg),
                  "accent": mark_accent(e.modes, "light", e.mark, fg), "name": e.brand, "tagline": tagline,
                  "layout": layout, "lettering": card_lettering(layout, found[0] if found else None, e.brand, w, h),
                  "mark": "" if layout == "lockup" else re.sub(r"^\s*<\?xml[^>]*>\s*", "", d.svg), "mark_size": card_mark_size(d.svg, h),
                  "rule_radius": rule_radius(CARD_RULE_RADIUS, card_art(layout, d.svg, found[0] if found else None))}
        src_rel = f"{out}/_build/promo-{key}.html"
        src = confine(e.project, src_rel, what="card source")
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text(fill_template(template, {k: str(v) for k, v in values.items()}, raw=("mark", "lettering")), encoding="utf-8")
        render_card(e.project, src_rel, w, h, f"{out}/_build/promo-{key}.png", "light")
        raw = confine(e.project, f"{out}/_build/promo-{key}.png", what="card").read_bytes()
        try:
            rgb = from_png(raw).png_rgb()
        except ValueError as err:
            fail(EXIT_FAIL, f"the {key} promo tile has transparent pixels ({err}); the template must paint a ground over the whole card")
        e.slot(f"{out}/store/promo-{key}-{w}x{h}.png", rgb, ["chrome-ext-promo"], slot=f"chrome-web-store-promo-{key}", size_px=(w, h), drawing=d,
               resampled_by="PAGE", note=f"{key} promotional tile" + (" (required by the store)" if promo[key].get("required") else " (optional)")
                                         + ": the mark and the name" + (" and one line of real copy" if tagline else "") + ", opaque")
        got = png_size(rgb)
        rep.add(f"check:promo-{key} size", "pass" if got == (w, h) and png_color_type(rgb) == 2 else "fail", "PNG at the spec size, 24-bit (opaque)",
                detail=f"{got[0]}x{got[1]}, colour type {png_color_type(rgb)}")
    rep.add("note:promo alpha", "info", "promo tiles are written opaque",
            detail="the store page was not read for an alpha rule on promo images, so they carry none; screenshots (real product) are not written")
    return e.finish()


main_guard(main)
