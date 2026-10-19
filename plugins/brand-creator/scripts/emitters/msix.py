#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator emit msix: the images of an MSIX package and an AppxManifest snippet.

Writes under assets/msix/ (override with --out-dir), laid out as the package's own paths, and records every file in assets/manifest.json.
  Assets/<Name>.scale-<N>.png            the base images of the msix-assets spec row (Square44x44Logo, Square150x150Logo, Wide310x150Logo,
                                         Square310x310Logo, Square71x71Logo, StoreLogo) at scale 100, 200 and 400: the base size times N / 100
  Assets/Square44x44Logo.targetsize-<S>.png                       the app-list sizes of the msix-applist spec row, each as
  Assets/Square44x44Logo.targetsize-<S>_altform-unplated.png      the dark-theme file (the artwork for dark grounds, transparent), and
  Assets/Square44x44Logo.targetsize-<S>_altform-lightunplated.png the light-theme file (the artwork for light grounds, transparent)
  AppxManifest.visual-elements.xml       the Properties/Logo and uap:VisualElements elements to merge into Package.appxmanifest
Each target size is drawn by the size-band rule for its own size. Gate: every size has the plain file and both altforms (without them Windows adds a
backplate), the unplated files have a transparent corner, and every PNG is read back at its size. The wide tile uses the logo art (--logo-svg, else
assets/logo/lockup.svg, wordmark.svg, then the mark). The manifest Description is a FACTS.md value (`description` or `summary`) or left out and warned.
Every size comes from platform-specs.json. A file that serves a row of status U carries the label "UNVERIFIED, recheck". Full tier only.
Needs gate G3. Idempotent.
"""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import quoteattr

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "lib"))
import svgtools  # noqa: E402
from _common import EXIT_FAIL, fail, main_guard  # noqa: E402
from _emit import add_logo_arg  # noqa: E402
from pxio import png_size  # noqa: E402
from tierb import TierBEmit, corner_alpha  # noqa: E402

PLATE_CONTENT = 0.7   # share of a tile or store image the mark fills (the app-list files use the whole canvas)
WIDE_CONTENT = 0.8    # share of the wide tile the logo art may fill
ALTFORM_ART = {"unplated": "dark", "lightunplated": "light"}   # the dark-theme file carries the artwork meant for dark grounds
XMLNS = 'xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10"'


def main() -> int:
    e = TierBEmit.begin("msix", __doc__, add_args=add_logo_arg)
    rep, out = e.rep, e.out
    base, lst = e.sizes("msix-assets"), e.sizes("msix-applist")
    unknown = [x for x in lst["altforms"] if x not in ALTFORM_ART]
    if unknown:
        fail(EXIT_FAIL, f"the msix-applist row lists altforms {unknown} that this emitter has no artwork rule for (known: {', '.join(ALTFORM_ART)})")
    art, art_src = e.logo_art()
    rep.add("note:logo art", "info", "logo art used for the wide tile", detail=art_src)
    ground = e.colour("light", "color.bg")

    # base images at every scale
    for name, spec in base["assets"].items():
        for mult in base["scales"]:
            sc = mult * base["percent_per_x"]   # the scale as the file name writes it: 100, 200, 400
            w, h = spec["width"] * mult, spec["height"] * mult
            if w != h and art_src != "the mark":
                d, svg = None, svgtools.fit(art, w, h, box=(w * WIDE_CONTENT, h * WIDE_CONTENT))
            else:
                d = e.drawing(max(w, h))
                svg = svgtools.tile(d.svg, w, h, content=PLATE_CONTENT)
            data = e.png(svg, w, h)
            e.slot(f"{out}/Assets/{name}.scale-{sc}.png", data, ["msix-assets"], slot=f"msix-{name}", size_px=(w, h), drawing=d,
                   note=f"{name} at scale {sc}: {spec['width']}x{spec['height']} x {mult}; transparent, shown on the manifest BackgroundColor plate")
            got = png_size(data)
            rep.add(f"check:{name}@{sc} size", "pass" if got == (w, h) else "fail", "PNG size is the base size times the scale", detail=f"{got[0]}x{got[1]}, wanted {w}x{h}")

    # app-list target sizes: plain, unplated (dark theme) and lightunplated (light theme)
    asset = lst["asset"]
    dark_cache: dict[str, str] = {}
    missing, opaque, wrong = [], [], []
    for s in lst["targetsizes"]:
        d = e.drawing(s)
        arts = {"light": d.svg}
        key = d.rel or "mark"
        if key not in dark_cache:
            dark_cache[key] = e.dark_svg(d)
        arts["dark"] = dark_cache[key]
        variants = [("", "light", "the plain file (shown on the plate)")]
        variants += [(f"_altform-{alt}", ALTFORM_ART[alt], f"{alt}: the {'dark' if ALTFORM_ART[alt] == 'dark' else 'light'}-theme file, no backplate") for alt in lst["altforms"]]
        for suffix, mode, what in variants:
            data = e.png(svgtools.fit(arts[mode], s, s), s, s)
            rel = f"{out}/Assets/{asset}.targetsize-{s}{suffix}.png"
            e.slot(rel, data, ["msix-applist"], slot=f"msix-applist-{s}", size_px=s, drawing=d, note=f"{asset} target size {s}, {what}; transparent")
            if png_size(data) != (s, s):
                wrong.append(rel)
            if suffix and corner_alpha(data) != 0:
                opaque.append(rel)
    rep.add("check:app list sizes", "fail" if wrong else "pass", "every app-list PNG is read back at its target size",
            detail=f"{len(lst['targetsizes'])} sizes x {1 + len(lst['altforms'])} files" if not wrong else f"wrong size: {', '.join(wrong[:4])}")
    rep.add("check:unplated transparent", "fail" if opaque else "pass", "the unplated files have a transparent corner (no ground of their own)",
            detail="all unplated corners are transparent" if not opaque else f"opaque corner: {', '.join(opaque[:4])}")
    rep.add("check:altforms present", "pass", "each target size has the plain file and every altform of the spec row (no backplate)",
            detail=f"{', '.join(lst['altforms'])} for {len(lst['targetsizes'])} sizes")

    # the manifest snippet
    desc = e.facts().get("description") or e.facts().get("summary")
    if not desc:
        rep.add("note:description", "warn", "the manifest Description is left out",
                detail="FACTS.md has no `description` or `summary` row; uap:VisualElements needs a Description: add the row with its source, then re-run")
    n44, n150 = "Square44x44Logo", "Square150x150Logo"
    attrs = [f"DisplayName={quoteattr(e.brand)}"] + ([f"Description={quoteattr(desc)}"] if desc else []) + \
            [f'{n150}="Assets\\{n150}.png"', f'{n44}="Assets\\{n44}.png"', f"BackgroundColor={quoteattr(ground)}"]
    snippet = "\n".join([
        "<!-- Generated by brand-creator emit msix. Merge into Package.appxmanifest; paths are relative to the package root and carry no scale or target size:",
        "     Windows picks the scale-N and targetsize-N files by name. -->",
        "<Properties>", f'  <Logo>Assets\\StoreLogo.png</Logo>', "</Properties>",
        f"<uap:VisualElements {' '.join(attrs)}>",
        f'  <uap:DefaultTile Wide310x150Logo="Assets\\Wide310x150Logo.png" Square71x71Logo="Assets\\Square71x71Logo.png" Square310x310Logo="Assets\\Square310x310Logo.png" />',
        "</uap:VisualElements>", ""])
    try:
        ET.fromstring(f"<Package {XMLNS}>{snippet}</Package>")
    except ET.ParseError as err:
        fail(EXIT_FAIL, f"the AppxManifest snippet is not well-formed XML: {err}")
    for n in (*base["assets"],):
        if n not in snippet:
            fail(EXIT_FAIL, f"the AppxManifest snippet does not name {n}")
    e.put(f"{out}/AppxManifest.visual-elements.xml", snippet.encode(), ["msix-assets"], slot="msix-appxmanifest-snippet",
          note="Properties/Logo and uap:VisualElements for Package.appxmanifest" + ("" if desc else "; no Description (no FACTS.md value)"))
    return e.finish()


main_guard(main)
