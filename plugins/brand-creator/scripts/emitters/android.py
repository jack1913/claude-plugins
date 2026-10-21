#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator emit android: the adaptive launcher icon, the legacy icons, the Play icon and the feature graphic.

Writes under assets/android/ (override with --out-dir), laid out as an Android module's own paths, and records every file in assets/manifest.json.
  res/mipmap-anydpi-v26/ic_launcher.xml, ic_launcher_round.xml   <adaptive-icon> with a background, a foreground and an explicit monochrome layer
  res/values/ic_launcher_background.xml                          the background layer: the light ground (color.bg) as a colour resource
  res/mipmap-<density>/ic_launcher_foreground.png, ic_launcher_monochrome.png    108 dp layers at mdpi to xxxhdpi, the mark centred and inside the safe zone
  res/mipmap-<density>/ic_launcher.png, ic_launcher_round.png    legacy icons (48 dp) for launchers before API 26: a square and a circle
  play/ic_launcher-playstore.png                                 the Google Play icon: full square, 32-bit, opaque, sRGB chunk
  play/feature-graphic.png                                       the Play feature graphic, 24-bit PNG (no alpha), from templates/card.html (or --template)
Gate: the safe-zone gate. The mark's ink must stay inside the safe zone of the adaptive-icon row (a circle of that diameter, the stricter of the
circle and the square) on every density and on the Play icon; otherwise nothing is written and the emit fails (exit 1). By default the mark is as large
as the logo range allows and still fits; --content-dp sets it by hand and the gate holds you to it. A monochrome layer is always written: a
silhouette of the drawing, or --svg-mono; artwork that cannot be reduced without an authored file fails the emit.
Every size comes from platform-specs.json. A file that serves a row of status U carries the label "UNVERIFIED, recheck". Full tier only.
Needs gate G3 and `brand-creator setup` (the feature graphic is rendered by Chromium). Idempotent.
"""
import math
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "lib"))
import svgtools  # noqa: E402
from _common import EXIT_FAIL, EXIT_USAGE, confine, fail, main_guard, plugin_root  # noqa: E402
from _color import parse_hex  # noqa: E402
from _emit import (CARD_RULE_RADIUS, add_logo_arg, card_art, card_lettering, card_lettering_setup, card_mark_size, fill_template,  # noqa: E402
                   mark_accent, mark_tagline, render_card, rule_radius)
from pxio import png_color_type, png_size, read_png  # noqa: E402
from px_lib import from_png  # noqa: E402
from tierb import INK_TOLERANCE_PX, TierBEmit, ink_far, png_with_srgb  # noqa: E402

LEGACY_CONTENT = 0.6    # share of a legacy icon the mark fills (inside the circle of the round one)
FIT_MARGIN = 0.99       # the automatic size leaves this share of the room the safe zone allows
BYTES_PER_KB = 2 ** 10
STEP_DP = 0.5           # the automatic size is a multiple of this many dp

XML_HEAD = '<?xml version="1.0" encoding="utf-8"?>\n'
ADAPTIVE = (XML_HEAD + '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n'
            '    <background android:drawable="@color/ic_launcher_background"/>\n'
            '    <foreground android:drawable="@mipmap/ic_launcher_foreground"/>\n'
            '    <monochrome android:drawable="@mipmap/ic_launcher_monochrome"/>\n'
            '</adaptive-icon>\n')
COLOUR = XML_HEAD + '<resources>\n    <color name="ic_launcher_background">{hex}</color>\n</resources>\n'


def main() -> int:
    def args(ap) -> None:
        ap.add_argument("--svg-mono", help="authored monochrome SVG for the monochrome layer (default: a black silhouette derived from the drawing)")
        ap.add_argument("--content-dp", type=float, help="the mark's box in dp inside the 108 dp layer (default: the largest in the logo range that fits the safe zone)")
        ap.add_argument("--template", help="card template of the feature graphic (default: templates/card.html in the plugin)")
        add_logo_arg(ap, cards=True)
        ap.add_argument("--tagline", default="", help="one line on the feature graphic (must be a value in FACTS.md)")

    e = TierBEmit.begin("android", __doc__, add_args=args)
    a, rep = e.a, e.rep
    ad, dens = e.sizes("android-adaptive"), e.sizes("android-densities")
    leg, play, feat = e.sizes("android-legacy-launcher"), e.sizes("android-play-icon"), e.sizes("android-feature-graphic")
    layer_dp, safe_dp = ad["layer_dp"], ad["safe_dp"]
    lo, hi = ad["logo_min_dp"], ad["logo_max_dp"]
    base_dpi, dpis = dens["baseline_dpi"], dens["dpi"]
    densities = list(dpis)

    def px(dp: float, density: str) -> int:
        return round(dp * dpis[density] / base_dpi)

    mono_override = None
    if a.svg_mono:
        mf = confine(e.project, a.svg_mono, what="--svg-mono")
        e.add_input(mf)
        mono_override = mf.read_text(encoding="utf-8")
    if a.tagline:
        e.require_fact(a.tagline, what="--tagline")
    if a.content_dp is not None and not (0 < a.content_dp <= hi):
        fail(EXIT_USAGE, f"--content-dp {a.content_dp:g} is outside 0 to {hi} dp (the logo range of the adaptive-icon row is {lo} to {hi} dp)")

    def foreground(n: int, content_dp: float, *, mono: bool = False) -> bytes:
        d = e.drawing(n)
        if mono:
            try:
                art = mono_override if mono_override is not None else svgtools.mono(d.svg)
            except svgtools.SvgError as err:
                fail(EXIT_FAIL, f"the monochrome layer cannot be derived from {d.rel or 'the mark'} ({err}); an adaptive icon ships an explicit monochrome layer: "
                                "pass an authored silhouette with --svg-mono")
        else:
            art = d.svg
        return e.png(svgtools.tile(art, n, n, content=content_dp / layer_dp), n, n)

    # ---- the size of the mark: as large as the logo range allows and the safe zone holds, or what --content-dp says
    top = max(dpis, key=dpis.get)
    n_top = px(layer_dp, top)
    radius_top = safe_dp / 2 * dpis[top] / base_dpi
    far = ink_far(foreground(n_top, hi))
    fit_dp = hi * min(1.0, radius_top / far) if far else float(hi)
    auto_dp = math.floor(fit_dp * FIT_MARGIN / STEP_DP) * STEP_DP
    if a.content_dp is None:
        if auto_dp < lo:
            msg = (f"the mark does not fit the {safe_dp} dp safe zone even at the {lo} dp minimum of the logo range: its ink reaches "
                   f"{far / dpis[top] * base_dpi:.1f} dp from the centre at {hi} dp, which scales to {fit_dp:.1f} dp at the limit. Nothing is written. "
                   "Redraw the mark with a rounder silhouette (the safe zone is a circle), or pass --content-dp lower than the range with the owner's agreement")
            rep.add("check:android safe zone", "fail", f"the mark stays inside the {safe_dp} dp safe zone", detail=msg)
            fail(EXIT_FAIL, msg)
        content_dp = auto_dp
        rep.add("note:content", "info", "the mark's box in the 108 dp layer", detail=f"{content_dp:g} dp (largest in {lo} to {hi} dp that fits the safe zone)")
    else:
        content_dp = a.content_dp
        if content_dp < lo:
            rep.add("note:content", "warn", "the mark is smaller than the logo range", detail=f"--content-dp {content_dp:g} is under {lo} dp, the logo range's minimum")
        else:
            rep.add("note:content", "info", "the mark's box in the 108 dp layer", detail=f"{content_dp:g} dp (--content-dp)")

    # ---- every layer, in memory first: the safe-zone gate runs before anything is written
    files: dict[str, bytes] = {}
    problems: list[str] = []
    for dn in densities:
        n = px(layer_dp, dn)
        limit = safe_dp / 2 * dpis[dn] / base_dpi
        for kind, mono in (("foreground", False), ("monochrome", True)):
            data = foreground(n, content_dp, mono=mono)
            files[f"res/mipmap-{dn}/ic_launcher_{kind}.png"] = data
            far_n = ink_far(data)
            if far_n > limit + INK_TOLERANCE_PX:
                problems.append(f"{kind} at {dn}: ink {far_n / dpis[dn] * base_dpi:.1f} dp from the centre, limit {safe_dp / 2:g} dp")
    if problems:
        msg = (f"the mark is outside the {safe_dp} dp safe zone: " + "; ".join(problems[:4]) + ". Nothing is written. "
               "Lower --content-dp, or leave it out and the largest size that fits is chosen")
        rep.add("check:android safe zone", "fail", f"the mark stays inside the {safe_dp} dp safe zone", detail=msg)
        fail(EXIT_FAIL, msg)
    rep.add("check:android safe zone", "pass", f"the mark stays inside the {safe_dp} dp safe zone (the circle) at every density",
            detail=f"the foreground and monochrome layers at {', '.join(densities)}, content {content_dp:g} dp")

    out = e.out
    ground = e.colour("light", "color.bg")
    for dn in densities:
        n = px(layer_dp, dn)
        for kind in ("foreground", "monochrome"):
            rel = f"res/mipmap-{dn}/ic_launcher_{kind}.png"
            d = e.drawing(n)
            e.slot(f"{out}/{rel}", files[rel], ["android-adaptive", "android-densities"], slot=f"android-adaptive-{kind}", size_px=n, drawing=d,
                   note=f"{kind} layer, {layer_dp} dp at {dn}; the mark in a {content_dp:g} dp box, inside the {safe_dp} dp safe zone"
                        + ("; a silhouette (alpha is what the system themes)" if kind == "monochrome" else "; transparent"))
            got = png_size(files[rel])
            rep.add(f"check:{kind}@{dn} size", "pass" if got == (n, n) else "fail", f"PNG size is {layer_dp} dp at {dn}", detail=f"{got[0]}x{got[1]}, wanted {n}x{n}")

    # background layer (a colour resource) and the adaptive XML (the same document serves the round launcher)
    e.put(f"{out}/res/values/ic_launcher_background.xml", COLOUR.format(hex=ground).encode(), ["android-adaptive"], slot="android-adaptive-background",
          note="the background layer: the light ground colour of the tokens (color.bg)")
    for name in ("ic_launcher", "ic_launcher_round"):
        e.put(f"{out}/res/mipmap-anydpi-v26/{name}.xml", ADAPTIVE.encode(), ["android-adaptive"], slot="android-adaptive-xml",
              note="adaptive icon: background, foreground and monochrome layers")

    # legacy icons: a square and a circle at 48 dp
    for dn in densities:
        n = px(leg["launcher_dp"], dn)
        for shape, name in zip(leg["shapes"], ("ic_launcher", "ic_launcher_round")):
            d = e.drawing(n)
            radius = 0.5 if shape == "round" else 0.0
            data = e.png(svgtools.tile(d.svg, n, n, bg=ground, content=LEGACY_CONTENT, radius=radius), n, n)
            e.slot(f"{out}/res/mipmap-{dn}/{name}.png", data, ["android-legacy-launcher", "android-densities"], slot=f"android-legacy-{shape}", size_px=n,
                   drawing=d, note=f"legacy {shape} launcher icon, {leg['launcher_dp']} dp at {dn}, for launchers before API 26"
                                   + ("; square, no rounded corners" if shape == "square" else ""))

    # Google Play icon: a full square, 32-bit, opaque, sRGB
    pn = play["px"]
    d_p, play_png = e.tile_png(pn, content=content_dp / layer_dp, ground=True, flat=True)
    play_png = png_with_srgb(play_png)
    e.slot(f"{out}/play/ic_launcher-playstore.png", play_png, ["android-play-icon"], slot="google-play-icon", size_px=pn, drawing=d_p,
           note="full square on the light ground (Play applies the corner radius and the shadow), 32-bit PNG, opaque, sRGB chunk")
    _w, _h, ppx = read_png(play_png)
    opaque = all(ppx[i] == 255 for i in range(3, len(ppx), 4))
    kb = len(play_png) / BYTES_PER_KB
    ctype = png_color_type(play_png)
    bits = {2: 3, 6: 4}.get(ctype, 0) * 8   # 8-bit channels: RGB is 24 bits, RGBA 32
    ok = png_size(play_png) == (pn, pn) and bits == play["bits"] and opaque and kb <= play["max_kb"]
    rep.add("check:play icon", "pass" if ok else "fail", "512 square, 32-bit (RGBA), fully opaque, within the size limit",
            detail=f"{png_size(play_png)}, colour type {ctype} ({bits} bits per pixel), opaque {opaque}, {kb:.0f} KB of {play['max_kb']}")
    far_play = ink_far(play_png, ground=parse_hex(ground))
    lim_play = safe_dp / layer_dp * pn / 2
    rep.add("check:play icon safe zone", "pass" if far_play <= lim_play + INK_TOLERANCE_PX else "fail",
            "the mark keeps the adaptive icon's share of the square (inside the 66 of 108 circle)", detail=f"ink {far_play:.0f} px from the centre, limit {lim_play:.0f}")

    # feature graphic: a card from the template, 24-bit PNG
    fw, fh = feat["width"], feat["height"]
    tpl_path = Path(a.template).expanduser().resolve() if a.template else plugin_root() / "templates" / "card.html"
    if not tpl_path.is_file():
        fail(EXIT_USAGE, f"card template not found: {tpl_path}")
    fg = e.colour("light", "color.text")
    template = tpl_path.read_text(encoding="utf-8")
    found, layout = card_lettering_setup(rep, e.project, a, template, tpl_path.name, e.mark_id)
    tagline = mark_tagline(e.project, e.mark, a.tagline, rep.inputs)
    mark_svg = e.drawing(max(fw, fh)).svg
    values = {"width": fw, "height": fh, "bg": ground, "fg": fg, "muted": e.modes["light"].get("color.muted", fg), "accent": mark_accent(e.modes, "light", e.mark, fg),
              "name": e.brand, "tagline": tagline, "layout": layout, "lettering": card_lettering(layout, found[0] if found else None, e.brand, fw, fh),
              "mark": "" if layout == "lockup" else re.sub(r"^\s*<\?xml[^>]*>\s*", "", mark_svg), "mark_size": card_mark_size(mark_svg, fh),
              "rule_radius": rule_radius(CARD_RULE_RADIUS, card_art(layout, mark_svg, found[0] if found else None))}
    src_rel = f"{out}/_build/feature-graphic.html"
    src = confine(e.project, src_rel, what="card source")
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_text(fill_template(template, {k: str(v) for k, v in values.items()}, raw=("mark", "lettering")), encoding="utf-8")
    render_card(e.project, src_rel, fw, fh, f"{out}/_build/feature-graphic.png", "light")
    card_png = confine(e.project, f"{out}/_build/feature-graphic.png", what="card").read_bytes()
    try:
        rgb = from_png(card_png).png_rgb()
    except ValueError as err:
        fail(EXIT_FAIL, f"the feature graphic has transparent pixels ({err}); the template must paint a ground over the whole card")
    e.slot(f"{out}/play/feature-graphic.png", rgb, ["android-feature-graphic"], slot="google-play-feature-graphic", size_px=(fw, fh), drawing=e.drawing(max(fw, fh)),
           resampled_by="PAGE", note="the mark, the name" + (" and one line of real copy" if tagline else "") + " on the light ground, 24-bit PNG with no alpha")
    ok = png_size(rgb) == (fw, fh) and png_color_type(rgb) == 2 and feat["alpha"] is False
    rep.add("check:feature graphic", "pass" if ok else "fail", "1024 x 500 at the spec size, 24-bit (RGB), no alpha channel",
            detail=f"{png_size(rgb)}, colour type {png_color_type(rgb)}")
    rep.extra["content_dp"] = content_dp
    return e.finish()


main_guard(main)
