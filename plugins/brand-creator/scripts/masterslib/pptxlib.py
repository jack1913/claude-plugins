"""What a PowerPoint deck holds, read from its XML with no Office app (masters check, masters embed-fonts).

inspect(path) -> {"slide_size": (cx, cy) in EMU, "slides": n, "outside": ["slide 3: <shape name>", ...], "fonts_named": [...],
                  "fonts_embedded": [...], "missing_pictures": ["slide 2: ../media/x.png", ...]}
Raises ValueError when the file is no PPTX (no zip, or no ppt/presentation.xml). A theme font reference (+mj-lt, +mn-lt) is not a font name.
"""
from __future__ import annotations

import posixpath
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

NS = {"p": "http://schemas.openxmlformats.org/presentationml/2006/main", "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
      "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships", "rel": "http://schemas.openxmlformats.org/package/2006/relationships"}
SLIDE = re.compile(r"^ppt/slides/slide(\d+)\.xml$")
FONT_ATTRS = ("latin", "ea", "cs", "sym")


SHAPES = ("sp", "pic", "cxnSp")


def _xfrm(el, path: str):
    x = el.find(path, NS)
    if x is None:
        return None
    off, ext = x.find("a:off", NS), x.find("a:ext", NS)
    if off is None or ext is None:
        return None
    return x, (int(off.get("x")), int(off.get("y")), int(ext.get("cx")), int(ext.get("cy")))


def _boxes(tree, to_slide, sx: float, sy: float):
    """(name, (x, y, w, h) in slide EMU) of every shape, picture, connector and graphic frame (a table, a chart) under `tree`, a shape inside a
    group mapped through the group's transform (a:chOff and a:chExt are the group's own coordinates of its a:off and a:ext)."""
    for el in tree:
        tag = el.tag.rsplit("}", 1)[-1]
        nv = el.find(".//p:cNvPr", NS)
        name = nv.get("name") if nv is not None else "a shape"
        if tag in SHAPES or tag == "graphicFrame":
            got = _xfrm(el, "p:spPr/a:xfrm" if tag in SHAPES else "p:xfrm")
            if got:
                x, y, w, h = got[1]
                (px, py) = to_slide(x, y)
                yield name, (px, py, w * sx, h * sy)
        elif tag == "grpSp":
            got = _xfrm(el, "p:grpSpPr/a:xfrm")
            if not got:
                continue
            xf, (gx, gy, gw, gh) = got
            ch_off, ch_ext = xf.find("a:chOff", NS), xf.find("a:chExt", NS)
            cox, coy = (int(ch_off.get("x")), int(ch_off.get("y"))) if ch_off is not None else (gx, gy)
            cw, chh = (int(ch_ext.get("cx")), int(ch_ext.get("cy"))) if ch_ext is not None else (gw, gh)
            kx, ky = (gw / cw if cw else 1.0), (gh / chh if chh else 1.0)
            ox, oy = to_slide(gx, gy)
            yield from _boxes(el, lambda px, py, ox=ox, oy=oy, cox=cox, coy=coy, kx=kx, ky=ky: (ox + (px - cox) * kx * sx, oy + (py - coy) * ky * sy), sx * kx, sy * ky)


def inspect(path: Path) -> dict:
    try:
        z = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as e:
        raise ValueError(f"not a PowerPoint file (no zip: {e})")
    with z:
        names = set(z.namelist())
        if "ppt/presentation.xml" not in names:
            raise ValueError("not a PowerPoint file (no ppt/presentation.xml)")
        pres = ET.fromstring(z.read("ppt/presentation.xml"))
        sz = pres.find("p:sldSz", NS)
        if sz is None:
            raise ValueError("ppt/presentation.xml names no slide size (p:sldSz)")
        cx, cy = int(sz.get("cx")), int(sz.get("cy"))
        embedded = sorted({f.get("typeface") for f in pres.iterfind("p:embeddedFontLst/p:embeddedFont/p:font", NS) if f.get("typeface")})
        named: set[str] = set()
        outside, missing = [], []
        slides = sorted((int(m.group(1)), n) for n in names if (m := SLIDE.match(n)))
        for k, name in slides:
            root = ET.fromstring(z.read(name))
            tree = root.find("p:cSld/p:spTree", NS)
            if tree is not None:
                for nm, (x, y, w, h) in _boxes(tree, lambda px, py: (px, py), 1.0, 1.0):
                    if x < 0 or y < 0 or x + w > cx or y + h > cy:
                        outside.append(f"slide {k}: {nm}")
            for tag in FONT_ATTRS:
                for el in root.iter(f"{{{NS['a']}}}{tag}"):
                    t = el.get("typeface", "")
                    if t and not t.startswith("+"):
                        named.add(t)
            rels = f"ppt/slides/_rels/slide{k}.xml.rels"
            if rels in names:
                for rel in ET.fromstring(z.read(rels)).iterfind("rel:Relationship", NS):
                    if rel.get("Type", "").endswith("/image") and rel.get("TargetMode") != "External":
                        target = posixpath.normpath(posixpath.join("ppt/slides", rel.get("Target", "")))
                        if target not in names:
                            missing.append(f"slide {k}: {rel.get('Target')}")
    return {"slide_size": (cx, cy), "slides": len(slides), "outside": outside, "fonts_named": sorted(named), "fonts_embedded": embedded, "missing_pictures": missing}
