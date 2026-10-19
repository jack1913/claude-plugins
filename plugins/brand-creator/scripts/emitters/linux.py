#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator emit linux: hicolor icons, the scalable SVG and an AppStream metainfo stub.

Writes under assets/linux/ (override with --out-dir), laid out as an install tree, and records every file in assets/manifest.json.
  usr/share/icons/hicolor/<s>x<s>/apps/<icon>.png   one PNG per size in the linux-hicolor spec row, each drawn by the band rule
  usr/share/icons/hicolor/scalable/apps/<icon>.svg  the vector drawing for the largest size
  usr/share/metainfo/<app-id>.metainfo.xml          a stub: its text fields come from FACTS.md only (labels below); a field with no
                                                    fact stays empty and is reported, never invented
FACTS.md labels read: "AppStream summary", "AppStream description", "project license" (SPDX), "metadata license" (SPDX), "homepage".
The brand name comes from BRAND-STATE.md. The tray icons are `emit tray`. Needs gate G3. Idempotent.
"""
import html
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "lib"))
import svgtools  # noqa: E402
from _common import main_guard  # noqa: E402
from _emit import Emit  # noqa: E402

FIELD_FACTS = {"summary": "appstream summary", "description": "appstream description", "project_license": "project license",
               "metadata_license": "metadata license"}


def metainfo(e: Emit, app_id: str, icon: str) -> tuple[bytes, list[str]]:
    fx = e.facts()
    missing = []
    vals = {}
    for key, label in FIELD_FACTS.items():
        vals[key] = fx.get(label, "")
        if not vals[key]:
            missing.append(label)
    if not app_id:
        missing.append("--app-id")
    x = html.escape
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             "<!-- Stub written by brand-creator emit linux. An empty element has no confirmed fact in FACTS.md yet: add the fact with its source and re-run. -->",
             '<component type="desktop-application">',
             f"  <id>{x(app_id)}</id>",
             f"  <name>{x(e.brand)}</name>",
             f"  <summary>{x(vals['summary'])}</summary>",
             f"  <metadata_license>{x(vals['metadata_license'])}</metadata_license>",
             f"  <project_license>{x(vals['project_license'])}</project_license>",
             f"  <description><p>{x(vals['description'])}</p></description>",
             f'  <launchable type="desktop-id">{x(app_id)}.desktop</launchable>' if app_id else '  <launchable type="desktop-id"></launchable>',
             f'  <icon type="stock">{x(icon)}</icon>']
    if fx.get("homepage"):
        lines.append(f'  <url type="homepage">{x(fx["homepage"])}</url>')
    lines += ["</component>", ""]
    return "\n".join(lines).encode(), missing


def main() -> int:
    def args(ap):
        ap.add_argument("--icon-name", help="icon file name without extension (default: the project slug)")
        ap.add_argument("--app-id", default="", help="AppStream component id, reverse-DNS (for example org.example.Acme); the metainfo id stays empty without it")

    e = Emit.begin("linux", __doc__, add_args=args)
    hic = e.sizes("linux-hicolor")
    e.sizes("linux-appstream")
    icon = e.a.icon_name or e.slug
    base = f"{e.out}/usr/share/icons/hicolor"
    for s in hic["px"]:
        d = e.drawing(s)
        e.slot(f"{base}/{s}x{s}/apps/{icon}.png", e.png(svgtools.fit(d.svg, s, s), s, s), ["linux-hicolor"], slot=f"hicolor-{s}", size_px=s,
               drawing=d, note="hand size: drawn for this size, the desktop does not shrink it")
    big = max(hic["px"])
    d = e.drawing(big)
    e.slot(f"{base}/{hic['scalable']}/{icon}.svg", d.svg.encode(), ["linux-hicolor"], slot="hicolor-scalable", size_px=big, drawing=d,
           note="vector, the drawing for the largest size")
    data, missing = metainfo(e, e.a.app_id, icon)
    e.put(f"{e.out}/usr/share/metainfo/{e.a.app_id or icon}.metainfo.xml", data, ["linux-appstream"], slot="appstream-metainfo",
          resampled_by="PAGE", note="stub; text fields from FACTS.md only")
    for m in missing:
        e.rep.add(f"metainfo:{m}", "warn", "AppStream field left empty",
                  detail=("pass --app-id" if m == "--app-id" else f"FACTS.md has no row labelled {m!r}") + "; the metainfo is a stub until this is filled")
    if not missing:
        e.rep.add("metainfo:fields", "pass", "every required text field came from FACTS.md or the command line")
    return e.finish()


main_guard(main)
