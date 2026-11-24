"""Embed fonts in a PowerPoint deck (brand-creator masters embed-fonts), so PowerPoint shows the brand fonts without installing them.

PowerPoint keeps embedded fonts as ppt/fonts/*.fntdata in Embedded OpenType (EOT) form; this writes uncompressed, unobfuscated EOT
(version 0x00020001) around each TTF and lists the fonts in ppt/presentation.xml (p:embeddedFontLst, after p:notesSz). The typeface is the
font's family name (name ID 1, as the slides name it: "Geist", "Geist SemiBold"), the style comes from its subfamily (name ID 2: Regular, Bold,
Italic, Bold Italic). A font whose OS/2 fsType forbids embedding is refused. Keynote and Google Slides ignore embedded fonts.
Ported from the method a client deck proved in PowerPoint (rendered with the fonts not installed). The zip is written with fixed timestamps,
so the same deck and fonts give the same bytes.
"""
from __future__ import annotations

import re
import struct
import zipfile
from io import BytesIO

FIXED_TIME = (1980, 1, 1, 0, 0, 0)
STYLES = {"regular": "regular", "bold": "bold", "italic": "italic", "bold italic": "boldItalic"}
FONT_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/font"


class EmbedError(ValueError):
    pass


def table_offset(data: bytes, tag: bytes) -> int:
    n = struct.unpack(">H", data[4:6])[0]
    for i in range(n):
        rec = data[12 + 16 * i: 28 + 16 * i]
        if rec[:4] == tag:
            return struct.unpack(">I", rec[8:12])[0]
    raise EmbedError(f"the font has no {tag.decode()} table")


def table(data: bytes, tag: bytes) -> bytes:
    n = struct.unpack(">H", data[4:6])[0]
    for i in range(n):
        rec = data[12 + 16 * i: 28 + 16 * i]
        if rec[:4] == tag:
            off, length = struct.unpack(">II", rec[8:16])
            return data[off: off + length]
    raise EmbedError(f"the font has no {tag.decode()} table")


def name(data: bytes, nid: int) -> str:
    t = table(data, b"name")
    count, strings = struct.unpack(">HH", t[2:6])
    for i in range(count):
        pid, eid, _lid, n, length, off = struct.unpack(">HHHHHH", t[6 + 12 * i: 18 + 12 * i])
        if pid == 3 and eid == 1 and n == nid:
            return t[strings + off: strings + off + length].decode("utf-16-be")
    raise EmbedError(f"the font has no Windows name {nid}")


def font_names(ttf: bytes) -> tuple[str, str]:
    """(family as the slides name it, style key of p:embeddedFont: regular, bold, italic or boldItalic)."""
    if ttf[:4] not in (b"\x00\x01\x00\x00", b"true"):
        raise EmbedError("not a TrueType font (a .ttf; a .otf with CFF outlines or a .woff2 is not embedded by PowerPoint)")
    sub = name(ttf, 2).strip().lower()
    if sub not in STYLES:
        raise EmbedError(f"its subfamily is {name(ttf, 2)!r}: PowerPoint embeds Regular, Bold, Italic and Bold Italic of a family "
                         "(a static weight such as SemiBold is its own family, named so in name ID 1)")
    return name(ttf, 1), STYLES[sub]


def eot(ttf: bytes) -> bytes:
    os2, head = table(ttf, b"OS/2"), table(ttf, b"head")
    weight, fstype = struct.unpack(">H", os2[4:6])[0], struct.unpack(">H", os2[8:10])[0]
    if fstype & 0x2:
        raise EmbedError("its licence forbids embedding (OS/2 fsType is restricted)")
    panose = os2[32:42]
    ur = struct.unpack(">IIII", os2[42:58])
    cp = struct.unpack(">II", os2[78:86])
    italic = 1 if struct.unpack(">H", os2[62:64])[0] & 1 else 0
    checksum = struct.unpack(">I", head[8:12])[0]

    def s(v: str) -> bytes:
        b = v.encode("utf-16-le")
        return struct.pack("<H", len(b)) + b

    names = (struct.pack("<H", 0) + s(name(ttf, 1)) + struct.pack("<H", 0) + s(name(ttf, 2)) + struct.pack("<H", 0)
             + s(name(ttf, 5)) + struct.pack("<H", 0) + s(name(ttf, 4)) + struct.pack("<H", 0) + struct.pack("<H", 0))
    body = (struct.pack("<II", 0x00020001, 0) + panose + struct.pack("<BB", 1, italic) + struct.pack("<I", weight)
            + struct.pack("<HH", fstype, 0x504C) + struct.pack("<IIII", *ur) + struct.pack("<II", *cp)
            + struct.pack("<I", checksum) + struct.pack("<IIII", 0, 0, 0, 0) + names)
    total = 8 + len(body) + len(ttf)
    return struct.pack("<II", total, len(ttf)) + body + ttf


def embed(deck: bytes, fonts: list[tuple[str, bytes]]) -> tuple[bytes, list[str]]:
    """The deck with the fonts embedded, and the typefaces it now holds. fonts: (file name for messages, TTF bytes). Raises EmbedError."""
    by_family: dict[str, dict[str, bytes]] = {}
    for fname, data in fonts:
        try:
            family, style = font_names(data)
            blob = eot(data)
        except EmbedError as e:
            raise EmbedError(f"{fname}: {e}")
        if style in by_family.setdefault(family, {}):
            raise EmbedError(f"{fname}: a second {style} of {family}")
        by_family[family][style] = blob
    try:
        src = zipfile.ZipFile(BytesIO(deck))
    except zipfile.BadZipFile as e:
        raise EmbedError(f"not a PowerPoint file ({e})")
    with src:
        files = {i.filename: src.read(i.filename) for i in src.infolist()}
    for need in ("ppt/presentation.xml", "ppt/_rels/presentation.xml.rels", "[Content_Types].xml"):
        if need not in files:
            raise EmbedError(f"not a PowerPoint file (no {need})")
    pres = files["ppt/presentation.xml"].decode("utf-8")
    if "embeddedFontLst" in pres:
        raise EmbedError("the deck has embedded fonts already; rebuild it first, then embed")
    rels = files["ppt/_rels/presentation.xml.rels"].decode("utf-8")
    nid = max([int(x) for x in re.findall(r'Id="rId(\d+)"', rels)] or [0]) + 1
    entries, n = [], 1
    for family in sorted(by_family):
        parts = []
        for style in ("regular", "bold", "italic", "boldItalic"):
            if style not in by_family[family]:
                continue
            part = f"fonts/font{n}.fntdata"
            files["ppt/" + part] = by_family[family][style]
            rels = rels.replace("</Relationships>", f'<Relationship Id="rId{nid}" Type="{FONT_REL}" Target="{part}"/></Relationships>')
            parts.append(f'<p:{style} r:id="rId{nid}"/>')
            nid, n = nid + 1, n + 1
        fam = family.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;")
        entries.append(f'<p:embeddedFont><p:font typeface="{fam}" pitchFamily="2" charset="0"/>{"".join(parts)}</p:embeddedFont>')
    files["ppt/_rels/presentation.xml.rels"] = rels.encode("utf-8")
    m = re.search(r"<p:notesSz[^>]*/>", pres)
    if not m:
        raise EmbedError("ppt/presentation.xml has no p:notesSz, after which the font list goes")
    pres = pres[: m.end()] + f"<p:embeddedFontLst>{''.join(entries)}</p:embeddedFontLst>" + pres[m.end():]
    head = re.search(r"<p:presentation\b[^>]*>", pres).group(0)
    new = re.sub(r'\s(embedTrueTypeFonts|saveSubsetFonts)="[^"]*"', "", head).replace("<p:presentation ", '<p:presentation embedTrueTypeFonts="1" saveSubsetFonts="0" ', 1)
    files["ppt/presentation.xml"] = pres.replace(head, new, 1).encode("utf-8")
    ct = files["[Content_Types].xml"].decode("utf-8")
    if 'Extension="fntdata"' not in ct:
        ct = ct.replace("<Default ", '<Default Extension="fntdata" ContentType="application/x-fontdata"/><Default ', 1)
    files["[Content_Types].xml"] = ct.encode("utf-8")
    out = BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in ["[Content_Types].xml"] + sorted(f for f in files if f != "[Content_Types].xml"):
            info = zipfile.ZipInfo(f, FIXED_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, files[f])
    return out.getvalue(), sorted(by_family)
