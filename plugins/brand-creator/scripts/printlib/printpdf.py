"""Print production helpers shared by `emit print` and `print-check`.

Honest print (plan review MUST #12): Chromium prints an RGB page that is exactly trim + 2 x bleed; Ghostscript turns the text into outlines
(`-dNoOutputFonts`); pikepdf sets the boxes and the metadata afterwards. PDF/X-4 is written only when the owner supplies a CMYK output
profile (`--icc`), and even then the file is only a "PDF/X-4 candidate (preflight with your printer)": nothing here can verify conformance.
Without a profile the file is an "RGB proof, not print-ready". The label is in the PDF's Subject, Keywords, XMP description and in the file name.

This folder is not `scripts/lib/`: `staleness` hashes that folder as emitter code, and a change to print must not make every pack stale.
pikepdf (pinned in the scripts that import this module) is imported lazily so that the pure helpers work without it.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "lib"))
sys.path.insert(0, str(HERE.parent / "emitters"))
import determinism  # noqa: E402
import specs  # noqa: E402
from _common import EXIT_CANNOT, EXIT_FAIL, EXIT_USAGE, confine, fail  # noqa: E402

LABEL_RGB = "RGB proof, not print-ready"
LABEL_X4 = "PDF/X-4 candidate (preflight with your printer)"
SUFFIX_RGB = ".rgb-proof"
SUFFIX_X4 = ".pdfx4-candidate"
MM_PER_IN = 25.4
GS_TIMEOUT_S = 120
RING_DPI = 200            # resolution of the bleed-ring raster check

# Template layout, in mm: the inner margin of each piece (always at least the safe zone plus a little), and the height of the accent bar that runs
# off the page. Kept here, not in the emitter, so that the emitter holds no sizes.
LAYOUT = {
    "business-card-front": {"margin": 6.0},
    "business-card-back": {"margin": 6.0},
    "letterhead": {"margin": 20.0, "bar_extra": 6.0, "rule_below": 28.0},
    "envelope": {"margin": 12.0, "bar_extra": 4.0},
}
MARGIN_OVER_SAFE_MM = 2.0   # a margin is never less than the safe zone plus this

# Words no print file of ours may use about itself. A candidate is not a conforming file and nothing here can verify conformance.
CLAIM_WORDS = re.compile(r"\b(conform\w*|compliant|compliance|certified|validated|verified|guaranteed|print[- ]ready)\b", re.I)
NOT_READY = re.compile(r"not print[- ]ready", re.I)

# Thresholds `print-check` holds the artwork to. Defaults are proposals: the printer's own template and the owner's qa/print.json win.
CONFIG_FILE = "qa/print.json"
DEFAULTS = {
    "safe_zone_mm": 3.0,             # text, logos and lines stay this far inside the trim
    "min_line_pt": 0.25,             # thinnest positive line (stroke, border, rule)
    "min_line_reversed_pt": 0.5,     # thinnest line printed light on dark: it fills in
    "min_reversed_text_pt": 7.0,     # smallest light-on-dark text
    "min_text_pt": 5.0,              # smallest text of any kind
    "min_logo_mm": 5.0,              # smallest height of an element marked as a logo (data-print-id); the brand's own minimum belongs in qa/print.json
    "min_bleed_mm": None,            # None: the bleed the region row gives (3 mm, 0.125 in), stated as printer-specific
    "box_tolerance_mm": 0.05,        # boxes and page size, as read back by pdfinfo (two decimals of a point) and rounded by Chromium
    "ring_tolerance": 6,             # bleed ring: colour distance (0..255, per channel max) from the artwork's edge inside the trim
}


def load_config(project: Path) -> tuple[dict, str]:
    """qa/print.json: {"schema": 1, <key>: <number>, ...}. An unknown key or a number at or below 0 exits 2: a typo never falls back to a default."""
    cfg = dict(DEFAULTS)
    f = confine(project, CONFIG_FILE, what="print config")
    if not f.is_file():
        return cfg, "defaults (qa/print.json not present; these numbers are proposals, set them in qa/print.json)"
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
    except ValueError as e:
        fail(EXIT_USAGE, f"{CONFIG_FILE}: not valid JSON ({e})")
    if not isinstance(doc, dict) or doc.get("schema") != 1:
        fail(EXIT_USAGE, f'{CONFIG_FILE}: must be an object with "schema": 1')
    for k, v in doc.items():
        if k == "schema":
            continue
        if k not in DEFAULTS:
            fail(EXIT_USAGE, f"{CONFIG_FILE}: unknown key {k!r} (known: {', '.join(sorted(DEFAULTS))})")
        if isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0:
            fail(EXIT_USAGE, f"{CONFIG_FILE}: {k} must be a number above 0, got {v!r}")
        cfg[k] = float(v)
    return cfg, CONFIG_FILE


# -------------------------------------------------------------------------------------------------------------------- regions
def regions() -> dict[str, dict]:
    """{region code: spec row} from print-regions.json (rows joined to the platform specs as print-<REGION>)."""
    return {r["region"]: dict(r, id=rid) for rid, r in specs.load()["rows"].items() if rid.startswith("print-")}


def pick_region(project: Path, flag: str | None) -> tuple[str, str]:
    """-> (region code, where it came from). `--region` wins; else the 'Region and language' line of brief/BRIEF.md must name exactly one
    region (or a country or alias of one). Nothing is guessed: a brief that names none or several exits 2."""
    table = regions()
    if flag:
        code = flag.upper()
        if code not in table:
            fail(EXIT_USAGE, f"--region {flag}: no such print region (known: {', '.join(sorted(table))})")
        return code, "--region"
    brief = project / "brief" / "BRIEF.md"
    line = ""
    if brief.is_file():
        for ln in brief.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^\s*[-*]\s*Region and language\s*:\s*(.*)$", ln, re.I)
            if m:
                line = m.group(1).strip()
                break
    low = line.lower()
    hits = sorted({code for code, row in table.items() for al in row.get("aliases", [])
                   if re.search(r"(?<![a-z])" + re.escape(al) + r"(?![a-z])", low)})
    if len(hits) == 1:
        return hits[0], f"brief/BRIEF.md ({line[:60]})"
    why = "names no region the print table knows" if not hits else f"names several ({', '.join(hits)})"
    fail(EXIT_USAGE, f"the brief's 'Region and language' line {why}: {line[:80]!r}. Pass --region {'|'.join(sorted(table))} "
                     f"(the region sets card, paper and envelope sizes and the default bleed)")


def sizes_for(region: str) -> dict:
    return regions()[region]["sizes"]


# -------------------------------------------------------------------------------------------------------------------- geometry
def pt(mm: float) -> float:
    return mm * 72.0 / MM_PER_IN


def mm(pts: float) -> float:
    return pts * MM_PER_IN / 72.0


def crop_marks_svg(page_w: float, page_h: float, bleed: float, gap: float = 0.5) -> str:
    """Crop marks inside the bleed strip, drawn by the template (units mm). The page is exactly trim + 2 x bleed, so the marks sit in the bleed:
    each is a hairline on the extension of a trim edge, from the page edge to `gap` short of the trim corner, with a white halo so it shows on
    dark art. They are cut off with the bleed, and `data-print-mark` keeps them out of the geometry checks. No opacity anywhere."""
    if bleed <= gap:
        return ""
    far_x, far_y = page_w - bleed, page_h - bleed
    segs = []
    for x in (bleed, far_x):          # vertical marks, top and bottom strips
        segs.append((x, 0, x, bleed - gap))
        segs.append((x, page_h, x, page_h - bleed + gap))
    for y in (bleed, far_y):          # horizontal marks, left and right strips
        segs.append((0, y, bleed - gap, y))
        segs.append((page_w, y, page_w - bleed + gap, y))
    def lines(width: float, colour: str) -> str:
        return "".join(f'<line x1="{a:g}" y1="{b:g}" x2="{c:g}" y2="{d:g}" stroke="{colour}" stroke-width="{width:g}"/>' for a, b, c, d in segs)
    hair, halo = 0.1, 0.35
    return (f'<svg data-print-mark xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {page_w:g} {page_h:g}" width="{page_w:g}mm" height="{page_h:g}mm" '
            f'style="position:absolute;left:0;top:0">{lines(halo, "#ffffff")}{lines(hair, "#000000")}</svg>')


# -------------------------------------------------------------------------------------------------------------------- ICC
def icc_info(path: Path) -> dict:
    """What the PDF/X-4 candidate needs to know about a user-supplied profile: it must be a CMYK output profile. Nothing is bundled."""
    data = path.read_bytes()
    if len(data) < 132 or data[36:40] != b"acsp":
        fail(EXIT_USAGE, f"--icc {path.name}: not an ICC profile (no 'acsp' signature)")
    space, pcs = data[16:20].decode("latin-1"), data[20:24].decode("latin-1")
    klass = data[12:16].decode("latin-1")
    if space != "CMYK":
        fail(EXIT_USAGE, f"--icc {path.name}: the profile's colour space is {space.strip()!r}; a PDF/X-4 candidate for print needs a CMYK output profile "
                         f"from your printer (for example FOGRA51 or PSO Coated v3, which brand-creator does not bundle)")
    desc = ""
    n = struct.unpack(">I", data[128:132])[0]
    for i in range(min(n, 200)):
        sig, off, size = struct.unpack(">4sII", data[132 + 12 * i:144 + 12 * i])
        if sig == b"desc":
            blob = data[off:off + size]
            if blob[:4] == b"desc":   # v2: ascii count + string
                ln = struct.unpack(">I", blob[8:12])[0]
                desc = blob[12:12 + max(ln - 1, 0)].decode("latin-1", "replace")
            elif blob[:4] == b"mluc" and len(blob) >= 28:   # v4: first record, UTF-16BE
                ln, o = struct.unpack(">II", blob[20:28])
                desc = blob[o:o + ln].decode("utf-16-be", "replace")
            break
    return {"path": str(path), "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data), "colour_space": space, "pcs": pcs,
            "class": klass, "description": desc.strip() or path.name, "version": f"{data[8]}.{data[9] >> 4}"}


# -------------------------------------------------------------------------------------------------------------------- Ghostscript
def need_gs() -> str:
    gs = shutil.which("gs")
    if not gs:
        fail(EXIT_CANNOT, "gs (Ghostscript) not found: it outlines the text of a print PDF. Install it (macOS: brew install ghostscript; Linux: apt install ghostscript; Windows: winget install ArtifexSoftware.GhostScript), "
                          "then re-run. Run: brand-creator prereq --for print")
    return gs


def pdfx_def(title: str, icc: dict) -> str:
    """The PostScript fragment Ghostscript reads to write a PDF/X-4 output intent (written here from the pdfmark reference, not copied from
    Ghostscript's sample). The condition is named after the user's profile; the registry is the ICC's."""
    esc = lambda s: s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")  # noqa: E731
    return "\n".join([
        "% generated by brand-creator emit print: PDF/X-4 candidate",
        f"[ /GTS_PDFXVersion (PDF/X-4) /Title ({esc(title)}) /Trapped /False /DOCINFO pdfmark",
        "[/_objdef {icc_PDFX} /type /stream /OBJ pdfmark",
        "[{icc_PDFX} << /N 4 >> /PUT pdfmark",
        f"[{{icc_PDFX}} ({esc(icc['path'])}) (r) file /PUT pdfmark",
        "[/_objdef {OutputIntent_PDFX} /type /dict /OBJ pdfmark",
        "[{OutputIntent_PDFX} << /Type /OutputIntent /S /GTS_PDFX",
        f"  /OutputCondition ({esc(icc['description'])}) /OutputConditionIdentifier (Custom) /Info ({esc(icc['description'])})",
        "  /RegistryName (http://www.color.org) /DestOutputProfile {icc_PDFX} >> /PUT pdfmark",
        "[{Catalog} << /OutputIntents [ {OutputIntent_PDFX} ] >> /PUT pdfmark", ""])


def gs_outline(src: Path, dst: Path, *, icc: dict | None, title: str, scratch: Path) -> None:
    """Chromium's PDF -> text as outlines (-dNoOutputFonts), written as PDF 1.4 for RGB proofs (no object streams, so dates and ID can be fixed
    in place) and as PDF 1.6 with -dPDFX=4, CMYK conversion through the user's profile and an output intent when `icc` is given."""
    gs = need_gs()
    scratch.mkdir(parents=True, exist_ok=True)
    cmd = [gs, "-q", "-dNOPAUSE", "-dBATCH", "-dSAFER", "-sDEVICE=pdfwrite", "-dNoOutputFonts", "-dAutoRotatePages=/None", f"-sOutputFile={dst}"]
    tail: list[str] = [str(src)]
    if icc:
        deff = scratch / "PDFX_def.ps"
        deff.write_text(pdfx_def(title, icc), encoding="latin-1")
        cmd += [f"--permit-file-read={icc['path']}", "-dPDFX=4", "-dCompatibilityLevel=1.6", "-sColorConversionStrategy=CMYK",
                "-sProcessColorModel=DeviceCMYK", f"-sOutputICCProfile={icc['path']}"]
        tail = [str(deff), str(src)]
    else:
        cmd += ["-dCompatibilityLevel=1.4"]
    cp = subprocess.run(cmd + tail, capture_output=True, text=True, timeout=GS_TIMEOUT_S)
    if cp.returncode != 0 or not dst.is_file():
        fail(EXIT_FAIL, f"Ghostscript failed (exit {cp.returncode}): {(cp.stderr or cp.stdout).strip()[:400]}")


# -------------------------------------------------------------------------------------------------------------------- pikepdf
def _pikepdf():
    try:
        import pikepdf
    except ImportError:
        fail(EXIT_CANNOT, "pikepdf is not importable: run this script through `brand-creator` (uv installs the pinned pikepdf)")
    return pikepdf


def xmp_packet(title: str, label: str, creator: str, *, pdfx: bool, uid: str) -> bytes:
    """A fixed XMP packet: the same input gives the same bytes. The label is the description. PDF/X identification only for a candidate."""
    esc = lambda s: s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")  # noqa: E731
    d = determinism.PDF_FIXED_XMP
    body = (
        '<?xpacket begin="﻿" id="W5M0MpCehiHzreSzNTczkc9d"?>\n<x:xmpmeta xmlns:x="adobe:ns:meta/">\n'
        '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
        f'<rdf:Description rdf:about="" xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:xmp="http://ns.adobe.com/xap/1.0/" '
        f'xmlns:pdf="http://ns.adobe.com/pdf/1.3/" xmlns:xmpMM="http://ns.adobe.com/xap/1.0/mm/" xmlns:pdfxid="http://www.npes.org/pdfx/ns/id/" '
        f'dc:format="application/pdf" xmp:CreatorTool="{esc(creator)}" xmp:CreateDate="{d}" xmp:ModifyDate="{d}" xmp:MetadataDate="{d}" '
        f'pdf:Producer="{esc(creator)}" pdf:Trapped="False" xmpMM:DocumentID="uuid:{uid}" xmpMM:InstanceID="uuid:{uid}" xmpMM:VersionID="1" '
        f'xmpMM:RenditionClass="default"' + (' pdfxid:GTS_PDFXVersion="PDF/X-4"' if pdfx else "") + '>\n'
        f'<dc:title><rdf:Alt><rdf:li xml:lang="x-default">{esc(title)}</rdf:li></rdf:Alt></dc:title>\n'
        f'<dc:description><rdf:Alt><rdf:li xml:lang="x-default">{esc(label)}</rdf:li></rdf:Alt></dc:description>\n'
        '</rdf:Description>\n</rdf:RDF>\n</x:xmpmeta>\n' + " " * 200 + '\n<?xpacket end="w"?>')
    return body.encode("utf-8")


def finish_pdf(raw: bytes, *, title: str, label: str, trim_mm: tuple[float, float], bleed_mm: float, pdfx: bool) -> bytes:
    """Post-processing of the Ghostscript output with pikepdf: exact boxes, fixed metadata, fixed dates and ID, no object streams.

    Chromium rounds the page to its own grid (a card comes out a few hundredths of a millimetre off), so the MediaBox is set to exactly
    trim + 2 x bleed, anchored at the top left where the page content starts; TrimBox is the trim inside it and BleedBox the whole page."""
    import io
    pikepdf = _pikepdf()
    pdf = pikepdf.open(io.BytesIO(raw))
    if len(pdf.pages) != 1:
        fail(EXIT_FAIL, f"the print page came out as {len(pdf.pages)} pages: the artwork overflows the page (a print piece is one page)")
    page = pdf.pages[0]
    mb = [float(v) for v in page.MediaBox]
    top = mb[3]
    w, h = pt(trim_mm[0] + 2 * bleed_mm), pt(trim_mm[1] + 2 * bleed_mm)
    if w > mb[2] - mb[0] + 0.5 or h > mb[3] - mb[1] + 0.5:
        fail(EXIT_FAIL, f"Chromium's page ({mm(mb[2] - mb[0]):.2f} x {mm(mb[3] - mb[1]):.2f} mm) is smaller than trim + 2 x bleed "
                        f"({mm(w):.2f} x {mm(h):.2f} mm)")
    x0, y0 = mb[0], top - h
    full = pikepdf.Array([x0, y0, x0 + w, top])
    b = pt(bleed_mm)
    page.MediaBox = full
    page.CropBox = pikepdf.Array([x0, y0, x0 + w, top])
    page.BleedBox = pikepdf.Array([x0, y0, x0 + w, top])
    page.TrimBox = pikepdf.Array([x0 + b, y0 + b, x0 + w - b, top - b])
    if "/ArtBox" in page:
        del page["/ArtBox"]
    info = pdf.docinfo
    for k in list(info.keys()):
        if not (pdfx and k in ("/GTS_PDFXVersion", "/Trapped")):
            del info[k]
    info["/Title"] = pikepdf.String(title)
    info["/Subject"] = pikepdf.String(label)
    info["/Keywords"] = pikepdf.String(f"print, {label}")
    info["/Creator"] = pikepdf.String("brand-creator emit print")
    info["/Producer"] = pikepdf.String("brand-creator (Chromium print, Ghostscript, pikepdf)")
    info["/CreationDate"] = pikepdf.String(determinism.PDF_FIXED_DATE)
    info["/ModDate"] = pikepdf.String(determinism.PDF_FIXED_DATE)
    if pdfx:
        info["/GTS_PDFXVersion"] = pikepdf.String("PDF/X-4")
        info["/Trapped"] = pikepdf.Name("/False")
    content = b"".join(bytes(p.Contents.read_bytes()) if not isinstance(p.Contents, pikepdf.Array) else b"".join(c.read_bytes() for c in p.Contents)
                       for p in pdf.pages)
    uid = hashlib.sha256(content + title.encode() + label.encode()).hexdigest()
    uid = f"{uid[:8]}-{uid[8:12]}-{uid[12:16]}-{uid[16:20]}-{uid[20:32]}"
    meta = pdf.make_stream(xmp_packet(title, label, "brand-creator emit print", pdfx=pdfx, uid=uid))
    meta["/Type"] = pikepdf.Name("/Metadata")
    meta["/Subtype"] = pikepdf.Name("/XML")
    pdf.Root["/Metadata"] = meta
    buf = io.BytesIO()
    pdf.save(buf, static_id=True, object_stream_mode=pikepdf.ObjectStreamMode.disable, compress_streams=True, deterministic_id=False)
    pdf.close()
    return determinism.normalise_pdf(buf.getvalue())


def inspect_pdf(path: Path) -> dict:
    """What a print PDF says about itself, read with pikepdf: pages, Info and XMP text, claims, output intents (with the profile's bytes),
    fonts, transparency constructs and colour spaces. Used by print-check; it never trusts the sidecar for any of this."""
    pikepdf = _pikepdf()
    pdf = pikepdf.open(path)
    out: dict = {"pages": len(pdf.pages), "info": {}, "xmp": "", "output_intents": [], "fonts": [], "transparency": [], "colour_spaces": set(),
                 "gts_version": None, "xmp_gts_version": None, "images": 0}
    for k, v in pdf.docinfo.items():
        out["info"][str(k)] = str(v)
    out["gts_version"] = out["info"].get("/GTS_PDFXVersion")
    if "/Metadata" in pdf.Root:
        out["xmp"] = bytes(pdf.Root.Metadata.read_bytes()).decode("utf-8", "replace")
        m = re.search(r"GTS_PDFXVersion\s*=\s*\"([^\"]+)\"|<pdfxid:GTS_PDFXVersion>([^<]+)<", out["xmp"])
        out["xmp_gts_version"] = (m.group(1) or m.group(2)) if m else None
    for oi in pdf.Root.get("/OutputIntents", []):
        prof = oi.get("/DestOutputProfile")
        out["output_intents"].append({"subtype": str(oi.get("/S", "")), "condition": str(oi.get("/OutputConditionIdentifier", "")),
                                      "n": int(prof.get("/N", 0)) if prof is not None else None,
                                      "profile_sha256": hashlib.sha256(bytes(prof.read_bytes())).hexdigest() if prof is not None else None})
    seen: set = set()

    def walk(res, where: str) -> None:
        if res is None or not hasattr(res, "get"):
            return
        key = getattr(res, "objgen", None)
        if key and key != (0, 0):
            if key in seen:
                return
            seen.add(key)
        for name, f in (res.get("/Font") or {}).items():
            out["fonts"].append(str(f.get("/BaseFont", name)))
        for name, gs in (res.get("/ExtGState") or {}).items():
            for k in ("/ca", "/CA"):
                if k in gs and float(gs[k]) < 1:
                    out["transparency"].append(f"{where}{name}: {k[1:]} {float(gs[k]):g}")
            sm = gs.get("/SMask")
            if sm is not None and str(sm) != "/None":
                out["transparency"].append(f"{where}{name}: soft mask")
            bm = gs.get("/BM")
            if bm is not None and str(bm) not in ("/Normal", "/Compatible"):
                out["transparency"].append(f"{where}{name}: blend mode {bm}")
        for name, cs in (res.get("/ColorSpace") or {}).items():
            out["colour_spaces"].add(str(cs[0]) if isinstance(cs, pikepdf.Array) else str(cs))
        for name, xo in (res.get("/XObject") or {}).items():
            if str(xo.get("/Subtype")) == "/Image":
                out["images"] += 1
                if "/SMask" in xo or "/Mask" in xo:
                    out["transparency"].append(f"{where}{name}: image with a mask or alpha")
            elif str(xo.get("/Subtype")) == "/Form":
                walk(xo.get("/Resources"), f"{where}{name}/")
        for name, pat in (res.get("/Pattern") or {}).items():
            walk(pat.get("/Resources"), f"{where}{name}/")

    for p in pdf.pages:
        walk(p.get("/Resources"), "")
        stream = b"".join(c.read_bytes() for c in p.Contents) if isinstance(p.Contents, pikepdf.Array) else bytes(p.Contents.read_bytes())
        s = stream.decode("latin-1")
        for op, cs in (("rg", "DeviceRGB"), ("RG", "DeviceRGB"), ("k", "DeviceCMYK"), ("K", "DeviceCMYK")):
            if re.search(r"(?:^|[\s\]])(?:[-+.\d]+\s+){%d}%s(?=\s|$)" % (3 if cs == "DeviceRGB" else 4, op), s):
                out["colour_spaces"].add("/" + cs)
    out["colour_spaces"] = sorted(out["colour_spaces"])
    pdf.close()
    return out


def pdfinfo_boxes(path: Path) -> dict:
    """The boxes as poppler's pdfinfo reads them (pt, two decimals): an oracle independent of the pikepdf that wrote them."""
    if not shutil.which("pdfinfo"):
        fail(EXIT_CANNOT, "pdfinfo (poppler) not found: print-check reads the boxes back with it. Install poppler (macOS: brew install poppler; Linux: apt install poppler-utils; Windows: scoop install poppler). "
                          "Run: brand-creator prereq --for print")
    cp = subprocess.run(["pdfinfo", "-box", str(path)], capture_output=True, text=True, timeout=60)
    if cp.returncode != 0:
        fail(EXIT_FAIL, f"pdfinfo could not read {path.name}: {cp.stderr.strip()[:200]}")
    boxes: dict = {"pages": None}
    for ln in cp.stdout.splitlines():
        m = re.match(r"^(Pages):\s+(\d+)", ln)
        if m:
            boxes["pages"] = int(m.group(2))
        m = re.match(r"^(MediaBox|CropBox|BleedBox|TrimBox|ArtBox):\s+(.*)$", ln)
        if m:
            boxes[m.group(1)] = [float(v) for v in m.group(2).split()]
    return boxes


# -------------------------------------------------------------------------------------------------------------------- raster ring
def _ppm(data: bytes) -> tuple[int, int, bytes]:
    m = re.match(rb"P6\s+(\d+)\s+(\d+)\s+255\s", data)
    if not m:
        raise ValueError("not a binary PPM")
    return int(m.group(1)), int(m.group(2)), data[m.end():]


def ring_stats(path: Path, bleed_mm: float, trim_mm: tuple[float, float], scratch: Path) -> dict:
    """Rasterise the page (poppler, 200 dpi) and compare, side by side, the middle of the bleed strip with a strip 0.5 to 1 mm inside the
    trim. -> {side: {"inside": rgb, "ring": rgb, "distance": max channel difference, "white_inside": bool}}. Medians, so the crop marks
    and any content in the strip do not move the answer."""
    if not shutil.which("pdftoppm"):
        fail(EXIT_CANNOT, "pdftoppm (poppler) not found: print-check rasterises the page to look at the bleed. Install poppler "
                          "(macOS: brew install poppler; Linux: apt install poppler-utils; Windows: scoop install poppler). Run: brand-creator prereq --for print")
    scratch.mkdir(parents=True, exist_ok=True)
    base = scratch / "ring"
    cp = subprocess.run(["pdftoppm", "-r", str(RING_DPI), "-singlefile", "-f", "1", "-l", "1", str(path), str(base)],
                        capture_output=True, text=True, timeout=120)
    ppm = base.with_suffix(".ppm")
    if cp.returncode != 0 or not ppm.is_file():
        fail(EXIT_FAIL, f"pdftoppm could not rasterise {path.name}: {cp.stderr.strip()[:200]}")
    w, h, px = _ppm(ppm.read_bytes())
    k = RING_DPI / MM_PER_IN
    b = bleed_mm * k
    tw, th = trim_mm[0] * k, trim_mm[1] * k

    def median(box: tuple[float, float, float, float]) -> tuple[int, int, int]:
        x0, y0, x1, y1 = (max(0, int(round(v))) for v in box)
        x1, y1 = min(w, max(x1, x0 + 1)), min(h, max(y1, y0 + 1))
        chans: list[list[int]] = [[], [], []]
        step = max(1, ((x1 - x0) * (y1 - y0)) // 4000)
        i = 0
        for y in range(y0, y1):
            row = y * w * 3
            for x in range(x0, x1):
                i += 1
                if i % step:
                    continue
                o = row + x * 3
                for c in range(3):
                    chans[c].append(px[o + c])
        return tuple(sorted(c)[len(c) // 2] for c in chans)  # type: ignore[return-value]

    in0, in1 = 0.5 * k, 1.0 * k
    ring_mid = b / 2
    f0, f1 = 0.2, 0.8   # the middle 60 % of each side
    out = {}
    spans = {"left": (b + in0, b + f0 * th, b + in1, b + f1 * th, ring_mid - b / 4, b + f0 * th, ring_mid + b / 4, b + f1 * th),
             "right": (b + tw - in1, b + f0 * th, b + tw - in0, b + f1 * th, b + tw + ring_mid - b / 4, b + f0 * th, b + tw + ring_mid + b / 4, b + f1 * th),
             "top": (b + f0 * tw, b + in0, b + f1 * tw, b + in1, b + f0 * tw, ring_mid - b / 4, b + f1 * tw, ring_mid + b / 4),
             "bottom": (b + f0 * tw, b + th - in1, b + f1 * tw, b + th - in0, b + f0 * tw, b + th + ring_mid - b / 4, b + f1 * tw, b + th + ring_mid + b / 4)}
    for side, s in spans.items():
        inside, ring = median(s[:4]), median(s[4:])
        out[side] = {"inside": list(inside), "ring": list(ring), "distance": max(abs(a - c) for a, c in zip(inside, ring)),
                     "white_inside": min(inside) >= 250}
    return out


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()
