"""Determinism rules for generated files, as code: the writers and the linter every emitter and `verify-idempotent` share.

Two runs of a build chain must give byte-identical files (or an allowlisted, explained difference with a substitute
check). The rules, from the plan:

  png     magick with `-define png:exclude-chunks=date,time` (magick_png_args), or Pillow; no tIME chunk, no date text chunk.
  zip     sorted entries, fixed mtime, fixed attributes (fixed_zip); never `zip -r` straight from a folder.
  pdf     /CreationDate, /ModDate and /ID fixed after the PDF is produced (normalise_pdf), so the xref table stays valid.
  car     an Assets.car is a compile gate compared by its `assetutil --info` rendition list, not by bytes.
  chrome  Chromium PNGs are byte-stable only on one machine and font stack: compared on the same machine, never committed
          as a cross-machine oracle.
Standard library only.
"""
from __future__ import annotations

import io
import json
import re
import shutil
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

ZIP_EPOCH = (1980, 1, 1, 0, 0, 0)  # the earliest date a zip can carry
PDF_FIXED_DATE = "D:19800101000000Z"
PDF_FIXED_XMP = "1980-01-01T00:00:00Z"  # the same instant in the ISO form XMP metadata uses (Ghostscript writes dates there only)
OBJSTM_MESSAGE = ("the PDF uses compressed object streams, so its dates and ID cannot be read or fixed in place; "
                  "write it without them (Ghostscript: -dCompatibilityLevel=1.4)")
RULES = [
    {"id": "png-chunks", "rule": "PNG files carry no tIME chunk and no date:* text chunk", "how": "magick_png_args() or px_lib/Pillow"},
    {"id": "zip-order", "rule": "zip entries are sorted by name", "how": "fixed_zip()"},
    {"id": "zip-mtime", "rule": f"zip entries carry the fixed mtime {ZIP_EPOCH}", "how": "fixed_zip()"},
    {"id": "pdf-dates", "rule": f"PDF /CreationDate and /ModDate are {PDF_FIXED_DATE}, XMP dates {PDF_FIXED_XMP}, and /ID is zeroed", "how": "normalise_pdf()"},
    {"id": "car-compare", "rule": "Assets.car is compared by `assetutil --info`, not by bytes", "how": "verify-idempotent substitute assetutil"},
    {"id": "chromium-png", "rule": "Chromium PNGs are byte-stable on one machine and font stack only", "how": "compare on the same machine"},
]


def magick_png_args() -> list[str]:
    """Arguments to put before the output file of an ImageMagick command so no date chunk is written."""
    return ["-define", "png:exclude-chunks=date,time"]


def fixed_zip(entries: dict[str, bytes]) -> bytes:
    """A zip of name -> bytes with sorted entries, a fixed mtime and fixed attributes: the same input gives the same bytes."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name in sorted(entries):
            zi = zipfile.ZipInfo(name, date_time=ZIP_EPOCH)
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.create_system = 3
            zi.external_attr = 0o644 << 16
            z.writestr(zi, entries[name], compresslevel=9)
    return buf.getvalue()


def normalise_pdf(data: bytes) -> bytes:
    """Fix /CreationDate, /ModDate and the /ID strings in place, keeping every byte offset (a date string is overwritten by a
    fixed one padded with spaces to the same length). Best effort for PDFs written by Chromium or Ghostscript; the print
    stage confirms the result with pdfinfo.

    A PDF written with compressed object streams (Ghostscript's default level 1.7) keeps its dates inside a compressed stream,
    where they can be neither seen nor fixed in place: that raises ValueError instead of returning the file unchanged. Write the
    PDF with `-dCompatibilityLevel=1.4` (Ghostscript) or an equivalent that avoids object streams."""
    if re.search(rb"/Type\s*/ObjStm", data):
        raise ValueError(OBJSTM_MESSAGE)
    def fixed(fixed_text: str):
        def date(m: re.Match) -> bytes:
            old = m.group(2)
            new = fixed_text.encode()
            return m.group(1) + (new + b" " * (len(old) - len(new)) if len(old) >= len(new) else new[:len(old)]) + m.group(3)
        return date

    data = re.sub(rb"(/(?:CreationDate|ModDate)\s*\()([^)]*)(\))", fixed(PDF_FIXED_DATE), data)
    data = re.sub(rb"(<xmp:(?:CreateDate|ModifyDate|MetadataDate)>)([^<]*)(</)", fixed(PDF_FIXED_XMP), data)
    return re.sub(rb"(/ID\s*\[\s*)<([0-9A-Fa-f]*)>(\s*)<([0-9A-Fa-f]*)>",
                  lambda m: m.group(1) + b"<" + b"0" * len(m.group(2)) + b">" + m.group(3) + b"<" + b"0" * len(m.group(4)) + b">", data)


def png_chunks(data: bytes) -> list[tuple[str, bytes]]:
    pos, out = 8, []
    while pos + 8 <= len(data):
        n, typ = struct.unpack(">I4s", data[pos:pos + 8])
        out.append((typ.decode("latin-1"), data[pos + 8:pos + 8 + n]))
        pos += 12 + n
    return out


def lint_file(path: Path) -> list[str]:
    """Rule violations in one generated file (empty list = clean)."""
    try:
        data = path.read_bytes()
    except OSError as e:
        return [f"unreadable: {e}"]
    out = []
    suf = path.suffix.lower()
    if suf == ".png" and data[:8] == b"\x89PNG\r\n\x1a\n":
        for typ, body in png_chunks(data):
            if typ == "tIME":
                out.append("PNG has a tIME chunk (png-chunks)")
            elif typ in ("tEXt", "iTXt", "zTXt"):
                key = body.split(b"\0", 1)[0]
                if key.lower().startswith((b"date:", b"create-date", b"modify-date", b"creation time")):
                    out.append(f"PNG has a date text chunk {key.decode('latin-1')!r} (png-chunks)")
    elif suf == ".zip":
        try:
            with zipfile.ZipFile(path) as z:
                infos = z.infolist()
        except zipfile.BadZipFile:
            return ["not a valid zip"]
        names = [i.filename for i in infos]
        if names != sorted(names):
            out.append("zip entries are not sorted (zip-order)")
        bad = sorted({i.filename for i in infos if tuple(i.date_time) != ZIP_EPOCH})
        if bad:
            out.append(f"zip entries with a real mtime, e.g. {bad[0]} (zip-mtime)")
    elif suf == ".pdf":
        if re.search(rb"/Type\s*/ObjStm", data):
            return [OBJSTM_MESSAGE + " (pdf-dates)"]
        for m in re.finditer(rb"/(?:CreationDate|ModDate)\s*\(([^)]*)\)", data):
            if not m.group(1).startswith(PDF_FIXED_DATE.encode()):
                out.append(f"PDF date {m.group(1).decode('latin-1')!r} is not the fixed date (pdf-dates)")
                break
        for m in re.finditer(rb"<xmp:(?:CreateDate|ModifyDate|MetadataDate)>([^<]*)</", data):
            if not m.group(1).startswith(PDF_FIXED_XMP.encode()):
                out.append(f"PDF XMP date {m.group(1).decode('latin-1')!r} is not the fixed date (pdf-dates)")
                break
        m = re.search(rb"/ID\s*\[\s*<([0-9A-Fa-f]*)>", data)
        if m and m.group(1).strip(b"0"):
            out.append("PDF /ID is not zeroed (pdf-dates)")
    return out


# -- Assets.car: the rendition list, not the bytes ------------------------------------------------------------------
# `assetutil --info` lists every rendition of a compiled catalogue. Two compiles of the same input differ in the header
# Timestamp and, per rendition, in the SHA1Digest and in a UUID that actool puts into RenditionName; everything else
# (type, name, idiom, appearance, scale, pixel size, opacity, platform) is stable and is what "the same catalogue" means.
CAR_VOLATILE_KEYS = ("Timestamp", "SHA1Digest", "SHA256Digest", "UUID")
_CAR_UUID = re.compile(r"_[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}(?:-[0-9A-Za-z]+)*(?=\.[A-Za-z0-9]+$|$)")


def car_renditions(path: Path) -> list[dict]:
    """The stable rendition list of a compiled Assets.car (macOS with Xcode only; raises RuntimeError elsewhere)."""
    if sys.platform != "darwin" or not shutil.which("xcrun"):
        raise RuntimeError("assetutil needs macOS with Xcode (xcrun assetutil)")
    cp = subprocess.run(["xcrun", "assetutil", "--info", str(path)], capture_output=True, text=True)
    if cp.returncode != 0:
        raise RuntimeError(f"assetutil failed: {cp.stderr.strip()[:200]}")
    out = []
    for item in json.loads(cp.stdout):
        if not isinstance(item, dict) or ("RenditionName" not in item and "Name" not in item):
            continue
        row = {k: v for k, v in item.items() if k not in CAR_VOLATILE_KEYS}
        if isinstance(row.get("RenditionName"), str):
            row["RenditionName"] = _CAR_UUID.sub("", row["RenditionName"])
        out.append(row)
    return out
