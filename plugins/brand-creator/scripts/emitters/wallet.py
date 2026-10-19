#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator emit wallet: Apple Wallet pass images and Google Wallet logos.

Writes under assets/wallet/ (override with --out-dir) and records every file in assets/manifest.json.
  apple/icon@2x.png, icon@3x.png          38 x 38 pt, the mark
  apple/logo@..., primaryLogo@..., secondaryLogo@...   the logo art fitted in each box of the apple-wallet spec row (height fixed,
                                          width between its minimum and maximum; narrower art is centred on the minimum width)
  apple/order-logo.png                    300 x 300 px, opaque (order tracking)
  google/logo-<px>.png                    the mark inside the circle-safe area, on the light ground, full bleed (Google masks it to a circle)
  google/wide-logo-<w>x<h>.png            the logo art, transparent, margins on the circle-margin share
Sizes in points are multiplied by the @2x and @3x scales of the spec row. The logo art is --logo-svg, else assets/logo/lockup.svg, else
assets/logo/wordmark.svg, else the mark (every one must be pure vector). The strip, thumbnail, background, artwork and footer images carry
pass content, not the brand mark, and are not written. Needs gate G3. Idempotent.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "lib"))
import svgtools  # noqa: E402
from _common import main_guard  # noqa: E402
from _emit import Emit, add_logo_arg  # noqa: E402
from pxio import png_size, read_png  # noqa: E402

CONTENT = 0.62  # share of an opaque tile the mark fills


def box_for(spec: dict, aspect: float) -> tuple[float, float]:
    """The fitted size in points of art with width/height `aspect` in the box of a spec entry: height fixed, width capped at max_width."""
    h = spec["height"]
    w = h * aspect
    if w > spec["max_width"]:
        w, h = spec["max_width"], spec["max_width"] / aspect
    return w, h


def main() -> int:
    e = Emit.begin("wallet", __doc__, add_args=add_logo_arg)
    aw, gw = e.sizes("apple-wallet"), e.sizes("google-wallet")
    art, art_src = e.logo_art()
    vb = svgtools.viewbox(svgtools.parse(art))
    aspect = vb[2] / vb[3]
    ground = e.colour("light", "color.bg")
    e.rep.add("note:logo art", "info", "logo art used for the wide and pass logos", detail=art_src)
    base = f"{e.out}/apple"

    for sc in aw["scales"]:
        # icon: a square, the mark
        n = aw["icon"]["width"] * sc
        d = e.drawing(n)
        e.slot(f"{base}/icon@{sc}x.png", e.png(svgtools.fit(d.svg, n, n), n, n), ["apple-wallet"], slot="wallet-icon", size_px=n, drawing=d,
               note=f"38 pt at @{sc}x, transparent")
        for key in ("logo", "primaryLogo", "secondaryLogo"):
            spec = aw[key]
            w_pt, h_pt = box_for(spec, aspect)
            w, h = round(w_pt * sc), round(h_pt * sc)
            cw = max(w, spec["min_width"] * sc)
            if art_src == "the mark":
                d = e.drawing(max(cw, h))
                svg = d.svg
            else:
                d, svg = None, art
            png = e.png(svgtools.fit(svg, cw, h, box=(w, h)), cw, h)
            e.slot(f"{base}/{key}@{sc}x.png", png, ["apple-wallet"], slot=f"wallet-{key}", size_px=(cw, h), drawing=d,
                   note=f"{key}: {spec['height']} pt high, @{sc}x; art fitted to {w}x{h} px" + (", centred on the minimum width" if cw > w else ""))
            got = png_size(png)
            e.rep.add(f"check:{key}@{sc}x size", "pass" if got == (cw, h) else "fail", "PNG size equals the point size times the scale",
                      detail=f"{got[0]}x{got[1]}")
    n = aw["order_logo_px"]
    d = e.drawing(n)
    order = e.png(svgtools.tile(d.svg, n, n, bg=ground, content=CONTENT), n, n, bg=ground)
    e.slot(f"{base}/order-logo.png", order, ["apple-wallet"], slot="wallet-order-logo", size_px=n, drawing=d, note="order tracking merchant logo, opaque")
    _w, _h, px = read_png(order)
    e.rep.add("check:order-logo opaque", "pass" if all(px[i] == 255 for i in range(3, len(px), 4)) else "fail", "no transparency")

    # Google Wallet
    n = gw["logo_px"]
    d = e.drawing(n)
    safe = 0.5 - gw["circle_margin"]
    logo = e.png(svgtools.fit_in_circle(d.svg, n, safe, bg=ground), n, n)
    e.slot(f"{e.out}/google/logo-{n}.png", logo, ["google-wallet"], slot="google-wallet-logo", size_px=n, drawing=d,
           note="full bleed on the light ground, mark inside the circle-safe area (Google applies the circle)")
    ww, wh = gw["wide"]["width"], gw["wide"]["height"]
    m = gw["circle_margin"]
    wide = e.png(svgtools.fit(art, ww, wh, box=(ww * (1 - 2 * m), wh * (1 - 2 * m))), ww, wh)
    e.slot(f"{e.out}/google/wide-logo-{ww}x{wh}.png", wide, ["google-wallet"], slot="google-wallet-wide", size_px=(ww, wh),
           note="logo art, transparent", )
    _w, _h, px = read_png(wide)
    e.rep.add("check:wide logo transparent", "pass" if px[3] == 0 else "fail", "the corners are transparent (a transparent PNG is asked for)")
    return e.finish()


main_guard(main)
