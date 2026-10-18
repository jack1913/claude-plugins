#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.11"
# dependencies = ["pikepdf==10.17.0"]
# ///
"""brand-creator book-pdf: book.pdf from book.html, honestly labelled.

Chromium prints the book (print media, light scheme by default, A4 or Letter) through `render.mjs pdf`; the result is an RGB document
for reading and review. It is labelled "RGB, not print-ready" in the PDF's Subject and XMP description and on its first page, because it
has no print profile, no bleed and no trim box (print production is a separate, explicit step). The book must lint clean first.
pikepdf sets the metadata; dates and the file ID are fixed, so the same book gives the same bytes on one machine.
Writes book.pdf (or --out, inside the project) and assets/_checks/book-pdf.json.
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "booklib"))
import bookdata  # noqa: E402
import booklint  # noqa: E402
import determinism  # noqa: E402
from _common import (EXIT_CANNOT, EXIT_FAIL, EXIT_USAGE, Parser, Report, add_project_arg, confine, data_dir, fail, find_project,  # noqa: E402
                     main_guard, plugin_root, rel, scratch_dir, sha256_bytes, write_bytes_if_changed)

LABEL = bookdata.PDF_LABEL


def render_raw(project: Path, book_rel: str, out: Path, fmt: str, scheme: str, label_px: float) -> None:
    data_dir()
    cmd = ["node", str(plugin_root() / "scripts" / "render.mjs"), "pdf", book_rel, "--project", str(project), "--out", str(out), "--label", LABEL,
           "--format", fmt, "--scheme", scheme, "--label-px", f"{label_px:g}", "--json"]
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
    except FileNotFoundError:
        fail(EXIT_CANNOT, "node not found on PATH (install Node 22+ and run /brand-creator:setup)")
    if cp.returncode != 0:
        fail(cp.returncode if cp.returncode in (1, 2, 3) else EXIT_CANNOT, cp.stderr.strip() or cp.stdout.strip() or "render.mjs pdf failed")


def finish_pdf(raw: bytes, title: str, edition: int) -> bytes:
    import io
    import pikepdf
    pdf = pikepdf.open(io.BytesIO(raw))
    info = pdf.docinfo
    for k in list(info.keys()):
        del info[k]
    info["/Title"] = pikepdf.String(title)
    info["/Subject"] = pikepdf.String(LABEL)
    info["/Keywords"] = pikepdf.String(f"brand book, edition {edition}, {LABEL}")
    info["/Creator"] = pikepdf.String("brand-creator book-pdf")
    info["/Producer"] = pikepdf.String("brand-creator (Chromium print, pikepdf)")
    info["/CreationDate"] = pikepdf.String(determinism.PDF_FIXED_DATE)
    info["/ModDate"] = pikepdf.String(determinism.PDF_FIXED_DATE)
    with pdf.open_metadata(set_pikepdf_as_editor=False, update_docinfo=False) as meta:
        meta["dc:title"] = title
        meta["dc:description"] = LABEL
        meta["pdf:Keywords"] = f"brand book, edition {edition}, {LABEL}"
        meta["pdf:Producer"] = "brand-creator (Chromium print, pikepdf)"
        meta["xmp:CreatorTool"] = "brand-creator book-pdf"
        meta["xmp:CreateDate"] = determinism.PDF_FIXED_XMP
        meta["xmp:ModifyDate"] = determinism.PDF_FIXED_XMP
        meta["xmp:MetadataDate"] = determinism.PDF_FIXED_XMP
    buf = io.BytesIO()
    pdf.save(buf, static_id=True, object_stream_mode=pikepdf.ObjectStreamMode.disable, compress_streams=True, deterministic_id=False)
    pdf.close()
    return determinism.normalise_pdf(buf.getvalue())


def main() -> int:
    ap = Parser(prog="brand-creator book-pdf", description=__doc__, formatter_class=__import__("argparse").RawDescriptionHelpFormatter)
    add_project_arg(ap)
    ap.add_argument("--out", default="book.pdf", help="output file inside the project (default book.pdf)")
    ap.add_argument("--format", choices=("A4", "Letter"), default="A4", help="page size (default A4)")
    ap.add_argument("--scheme", choices=("light", "dark"), default="light", help="colour scheme of the printout (default light)")
    a = ap.parse_args()
    project = find_project(a.project)
    cfg, _ = bookdata.load_config(project)
    book_rel = cfg["output"]
    book = confine(project, book_rel, what="book")
    if not book.is_file():
        fail(EXIT_USAGE, f"{book_rel} not found; build it first (`brand-creator book`, or write it by hand for an authored-vector brand)")
    out = confine(project, a.out, what="--out")
    view = bookdata.state_view(project)
    doc, _tp = bookdata.tokens(project)
    facts = bookdata.facts(project)
    res = booklint.lint(project, book.read_text(encoding="utf-8"), path=book_rel, view=view, cfg=cfg, tokens_doc=doc, facts_rows=facts,
                        self_consistency=True)
    bad = [r for r in res if r["status"] == "fail"]
    if bad:
        fail(EXIT_FAIL, f"{book_rel} does not lint clean, so it is not exported: " + "; ".join(f"{r['id']}: {r['detail'][:120]}" for r in bad[:3])
             + " (run `brand-creator book-lint --self-consistency`)")
    for tool in ("pdfinfo",):
        if not shutil.which(tool):
            fail(EXIT_CANNOT, f"{tool} not found (poppler); install it (macOS: brew install poppler; Linux: apt install poppler-utils; Windows: scoop install poppler), then re-run. Run: brand-creator prereq --for print")
    rep = Report("book-pdf", project, booklint.lint_inputs(project, book))
    raw = scratch_dir(project, "book-pdf") / "book.raw.pdf"
    render_raw(project, book_rel, raw, a.format, a.scheme, float(cfg["min_label_px"]))
    title = f"{view['name']} brand book, edition {view['edition']}"
    data = finish_pdf(raw.read_bytes(), title, view["edition"])
    changed = write_bytes_if_changed(out, data)

    info = subprocess.run(["pdfinfo", "-box", str(out)], capture_output=True, text=True).stdout
    kv = {m.group(1): m.group(2).strip() for m in re.finditer(r"^([A-Za-z ]+):\s+(.*)$", info, re.M)}
    pages = int(kv.get("Pages", "0") or 0)
    rep.add("pdf:pages", "pass" if pages >= 2 else "fail", "the PDF has pages", detail=f"{pages} page(s), {kv.get('Page size', '?')}")
    rep.add("pdf:label-metadata", "pass" if kv.get("Subject") == LABEL and kv.get("Title") == title else "fail",
            f"the metadata says \"{LABEL}\"", detail=f"Title {kv.get('Title')!r}, Subject {kv.get('Subject')!r}")
    xmp = subprocess.run(["pdfinfo", "-meta", str(out)], capture_output=True, text=True).stdout
    rep.add("pdf:label-xmp", "pass" if LABEL in xmp else "fail", f"the XMP description says \"{LABEL}\"", detail="XMP packet read with pdfinfo -meta")
    if shutil.which("pdftotext"):
        first = subprocess.run(["pdftotext", "-f", "1", "-l", "1", str(out), "-"], capture_output=True, text=True).stdout
        ok = LABEL in " ".join(first.split())
        rep.add("pdf:label-cover", "pass" if ok else "fail", f"the first page says \"{LABEL}\"", detail="text of page 1 read with pdftotext")
    else:
        rep.add("pdf:label-cover", "skipped", f"the first page says \"{LABEL}\"", detail="pdftotext (poppler) is not installed; not verified")
    raw_text = data.decode("latin-1")
    cmyk = bool(re.search(r"/DeviceCMYK|/Separation|/DeviceN", raw_text))
    rep.add("pdf:colour", "fail" if cmyk else "pass", "RGB only: no CMYK, separation or print profile in the file",
            detail="a CMYK or spot colour appeared; this export is an RGB proof" if cmyk else "no /DeviceCMYK, /Separation or /DeviceN; no output intent")
    rep.add("pdf:no-output-intent", "fail" if "/OutputIntents" in raw_text else "pass", "no PDF/X output intent (this is not a print file)", detail="")
    probs = determinism.lint_file(out)
    rep.add("pdf:determinism", "fail" if probs else "pass", "dates and ID are fixed", detail="; ".join(probs))
    rep.add("pdf:print-ready", "info", "not print-ready", detail="RGB, no bleed, no trim box, no profile: a proof for reading and review; print production is a separate step with the printer's proof")
    rep.extra.update({"manifest_view_sha": bookdata.manifest_view_sha(project),
                      "pdf": {"path": rel(project, out), "sha256": sha256_bytes(data), "bytes": len(data), "pages": pages}, "label": LABEL,
                      "format": a.format, "scheme": a.scheme, "written": changed})
    rc = rep.finish(quiet_pass=True)
    print(f"book-pdf: {rel(project, out)} {'written' if changed else 'unchanged'} ({len(data)} bytes, {pages} pages, {a.format}, {LABEL})")
    return rc


main_guard(main)
