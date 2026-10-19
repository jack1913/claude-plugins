#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pikepdf==10.17.0"]
# ///
"""Test helper: break a print PDF on purpose, in a scratch copy, so print-check can be shown to fail. Used by tests/test_print.py only.

  pdfmut.py claim-pdfx IN OUT      write a PDF/X-4 claim (Info, XMP, Subject) into a file that has no output intent
  pdfmut.py no-bleedbox IN OUT     set BleedBox to the TrimBox (the bleed is gone from the boxes)
  pdfmut.py opacity IN OUT         add an ExtGState with /ca 0.5 to the page resources
  pdfmut.py font IN OUT            add a font resource (text that is not outlined)
Exits 1 with a message when the mutation did not change the file (a mutation that did not apply proves nothing).
"""
import sys

import pikepdf


def main() -> int:
    mode, src, dst = sys.argv[1:4]
    pdf = pikepdf.open(src)
    page = pdf.pages[0]
    before = pdf.docinfo.get("/Subject")
    if mode == "claim-pdfx":
        label = "PDF/X-4 candidate (preflight with your printer)"
        pdf.docinfo["/Subject"] = pikepdf.String(label)
        pdf.docinfo["/GTS_PDFXVersion"] = pikepdf.String("PDF/X-4")
        assert "/OutputIntents" not in pdf.Root, "the source already has an output intent"
    elif mode == "no-bleedbox":
        assert [float(v) for v in page.BleedBox] != [float(v) for v in page.TrimBox]
        page.BleedBox = pikepdf.Array([float(v) for v in page.TrimBox])
    elif mode == "opacity":
        res = page.Resources
        gs = pikepdf.Dictionary(Type=pikepdf.Name.ExtGState, ca=0.5, CA=0.5)
        if "/ExtGState" not in res:
            res.ExtGState = pikepdf.Dictionary()
        res.ExtGState["/GSmut"] = gs
    elif mode == "font":
        if "/Font" not in page.Resources:
            page.Resources.Font = pikepdf.Dictionary()
        page.Resources.Font["/Fmut"] = pdf.make_indirect(pikepdf.Dictionary(Type=pikepdf.Name.Font, Subtype=pikepdf.Name.Type1, BaseFont=pikepdf.Name.Helvetica))
    else:
        print(f"unknown mutation {mode}", file=sys.stderr)
        return 2
    pdf.save(dst, static_id=True, object_stream_mode=pikepdf.ObjectStreamMode.disable)
    after = pikepdf.open(dst)
    if after.docinfo.get("/Subject") == before and mode == "claim-pdfx":
        print("the mutation did not apply", file=sys.stderr)
        return 1
    return 0


sys.exit(main())
