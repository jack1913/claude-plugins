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
            for sp in root.iter():
                xfrm = sp.find("p:spPr/a:xfrm", NS) if sp.tag.endswith("}sp") or sp.tag.endswith("}pic") or sp.tag.endswith("}cxnSp") else None
                if xfrm is None:
                    continue
                off, ext = xfrm.find("a:off", NS), xfrm.find("a:ext", NS)
                if off is None or ext is None:
                    continue
                x, y, w, h = int(off.get("x")), int(off.get("y")), int(ext.get("cx")), int(ext.get("cy"))
                if x < 0 or y < 0 or x + w > cx or y + h > cy:
                    nv = sp.find(".//p:cNvPr", NS)
                    outside.append(f"slide {k}: {nv.get('name') if nv is not None else 'a shape'}")
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
