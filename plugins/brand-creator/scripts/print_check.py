#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.11"
# dependencies = ["pikepdf==10.17.0"]
# ///
"""brand-creator print-check: the physical review of the print PDFs, in mm and pt.

Reads the PDFs `emit print` wrote (every manifest row of emitter print that is a .pdf, or the files named on the command line) and holds them to
rules written in print units. What is read from where, so that no row claims more than it knows:

  from the PDF itself   page count; MediaBox, TrimBox, BleedBox as poppler's `pdfinfo -box` reads them (an oracle independent of the pikepdf that
                        wrote them); fonts (a print PDF has none: the text is outlines); transparency (opacity, soft masks, blend modes, masked images);
                        colour spaces, output intents and the embedded profile; the metadata, XMP and dates; and a 200 dpi raster of the page, to see
                        whether the artwork at the trim carries on into the bleed.
  from the sidecar      <piece>.print.json: what Chromium measured in the render that made the PDF (position and size of every text, logo, image,
                        line and bleed element in mm from the trim corner; font and line sizes in pt). The text is outlined in the file, so it cannot be
                        read from the file any more. The sidecar is bound to the PDF by sha256; it is not proof against someone who edits both.

Rows per piece: bind, pages, page-size, trim-box, bleed-box, bleed-width, bleed:geometry, bleed:ring, safe-zone, line-weight, text-size,
reversed-text, logo-size, transparency, fonts, colour, label:claims, label:icc, dates. Thresholds come from qa/print.json (written by the owner;
unknown keys exit 2) and otherwise from stated defaults, which are proposals: safe zone 3 mm, thinnest line 0.25 pt (0.5 pt light on dark),
smallest reversed text 7 pt, smallest text 5 pt, smallest logo 5 mm high, bleed the region's (printer-specific).

The label rules are the honest-print rules: a file carries "PDF/X-4 candidate (preflight with your printer)" only when it has a CMYK output
intent made from a profile (`--icc FILE` here also checks that the embedded profile is that file), and "RGB proof, not print-ready" when it has
none; any other claim (PDF/X without an intent, "conforms", "compliant", "print-ready") fails. Passing this check does not make a file
print-ready: conformance needs a preflight with your printer's tool, and the printer's own proof is the owner's step.
Exit 0 pass, 1 a rule fails, 3 something could not be read (a missing tool or sidecar). Writes assets/_checks/print-check.json.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))
sys.path.insert(0, str(HERE / "emitters"))
sys.path.insert(0, str(HERE / "printlib"))
import determinism  # noqa: E402
import printpdf as pp  # noqa: E402
from _common import EXIT_CANNOT, EXIT_USAGE, Parser, Report, add_project_arg, confine, fail, find_project, main_guard, rel, scratch_dir  # noqa: E402
from manifest import load_artefacts  # noqa: E402

EPS_MM = 0.01          # rounding in the sidecar (three decimals of a mm)
EDGE_MM = 0.1          # an element whose edge is within this of the trim edge "reaches" the trim there


def fmt(v: float) -> str:
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def short(e: dict) -> str:
    return (e.get("text") or e.get("id") or e.get("tag") or e["kind"])[:30]


def pdfs_to_check(project: Path, named: list[str]) -> list[Path]:
    if named:
        out = []
        for n in named:
            f = confine(project, n, what="PDF")
            if not f.is_file():
                fail(EXIT_USAGE, f"not found: {n}")
            out.append(f)
        return out
    return [project / a["path"] for a in load_artefacts(project) if a.get("emitter") == "print" and a["path"].endswith(".pdf")]


def sidecar_for(pdf: Path) -> Path:
    stem = re.sub(r"\.(rgb-proof|pdfx4-candidate)$", "", pdf.stem)
    return pdf.with_name(stem + ".print.json")


def check_one(project: Path, pdf: Path, cfg: dict, icc_file: Path | None, rep: Report) -> None:
    piece = pdf.stem
    rid = lambda k: f"{piece}:{k}"  # noqa: E731
    pdf_rel = rel(project, pdf)
    side = sidecar_for(pdf)
    rep.inputs.append(pdf)
    sc = None
    if side.is_file():
        rep.inputs.append(side)
        try:
            sc = json.loads(side.read_text(encoding="utf-8"))
        except ValueError:
            sc = None
    if sc is None or sc.get("schema") != 1 or "geometry" not in sc:
        rep.add(rid("bind"), "skipped", "the sidecar says what Chromium measured",
                detail=f"not verified: {rel(project, side)} is missing or not a print sidecar; re-run `brand-creator emit print`")
        sc = None
    else:
        same = sc.get("pdf", {}).get("sha256") == pp.sha256_file(pdf)
        rep.add(rid("bind"), "pass" if same else "fail", "the sidecar belongs to this PDF (sha256)",
                detail="same bytes" if same else f"{pdf_rel} is not the PDF the sidecar was measured for: re-run `brand-creator emit print`")

    # ---- the PDF itself
    boxes = pp.pdfinfo_boxes(pdf)
    info = pp.inspect_pdf(pdf)
    tol = cfg["box_tolerance_mm"]
    rep.add(rid("pages"), "pass" if boxes["pages"] == 1 and info["pages"] == 1 else "fail", "one page", detail=f"{boxes['pages']} page(s)")

    def box_mm(name: str):
        b = boxes.get(name)
        if not b:
            return None
        return [pp.mm(v) for v in b]
    media, trim, bleedbox = box_mm("MediaBox"), box_mm("TrimBox"), box_mm("BleedBox")
    # pdfinfo prints a box that is missing as the MediaBox: a Trim or Bleed box equal to the whole page is "no box set" for our purposes
    if not media or not trim or not bleedbox:
        rep.add(rid("page-size"), "fail", "MediaBox, TrimBox and BleedBox are present", detail="pdfinfo -box did not print all three")
        return
    mw, mh = media[2] - media[0], media[3] - media[1]
    tw, th = trim[2] - trim[0], trim[3] - trim[1]
    bleeds = {"left": trim[0] - media[0], "bottom": trim[1] - media[1], "right": media[2] - trim[2], "top": media[3] - trim[3]}
    bleed = sc["bleed_mm"] if sc else min(bleeds.values())
    if sc:
        etw, eth = sc["trim_mm"]
        ok = abs(tw - etw) <= tol and abs(th - eth) <= tol
        rep.add(rid("trim-box"), "pass" if ok else "fail", "TrimBox is the trim size of the piece",
                detail=f"TrimBox {fmt(tw)} x {fmt(th)} mm, the {sc['region']} table says {fmt(etw)} x {fmt(eth)} mm")
        ew, eh = etw + 2 * bleed, eth + 2 * bleed
        ok = abs(mw - ew) <= tol and abs(mh - eh) <= tol
        rep.add(rid("page-size"), "pass" if ok else "fail", "the page is trim + 2 x bleed",
                detail=f"MediaBox {fmt(mw)} x {fmt(mh)} mm; trim {fmt(etw)} x {fmt(eth)} + 2 x {fmt(bleed)} = {fmt(ew)} x {fmt(eh)} mm")
    else:
        rep.add(rid("page-size"), "skipped", "the page is trim + 2 x bleed", detail="not verified: no sidecar to say what the trim size should be")
    full = all(abs(media[i] - bleedbox[i]) <= tol for i in range(4))
    rep.add(rid("bleed-box"), "pass" if full else "fail", "BleedBox is the whole page (trim + bleed)",
            detail=f"BleedBox {[round(v, 2) for v in bleedbox]} mm, MediaBox {[round(v, 2) for v in media]} mm")
    min_bleed = cfg["min_bleed_mm"] if cfg["min_bleed_mm"] else (sc["bleed_mm"] if sc else None)
    equal = max(bleeds.values()) - min(bleeds.values()) <= tol
    if min_bleed is None:
        rep.add(rid("bleed-width"), "skipped", "the bleed is present and wide enough", detail="not verified: no sidecar and no min_bleed_mm in qa/print.json")
    else:
        ok = min(bleeds.values()) >= min_bleed - tol and equal
        rep.add(rid("bleed-width"), "pass" if ok else "fail", "bleed present on all four sides, at least the stated minimum",
                detail=(f"bleed {', '.join(f'{k} {fmt(v)}' for k, v in bleeds.items())} mm; minimum {fmt(min_bleed)} mm "
                        f"({'qa/print.json' if cfg['min_bleed_mm'] else 'the printer-specific default of the region table'})"
                        + ("" if equal else "; the four sides differ")))

    # ---- the raster ring: does the artwork at the trim go on into the bleed?
    if sc and min(bleeds.values()) > tol:
        ring = pp.ring_stats(pdf, min(bleeds.values()), (tw, th), scratch_dir(project, "print-check") / piece)
        bad = [f"{s}: edge {v['inside']} vs bleed {v['ring']}" for s, v in ring.items() if not v["white_inside"] and v["distance"] > cfg["ring_tolerance"]]
        touched = [s for s, v in ring.items() if not v["white_inside"]]
        if bad:
            rep.add(rid("bleed:ring"), "fail", "artwork that reaches the trim runs on into the bleed",
                    detail="the artwork stops at the trim on " + "; ".join(bad) + " (colour as read at 200 dpi): extend it to the page edge")
        else:
            rep.add(rid("bleed:ring"), "pass", "artwork that reaches the trim runs on into the bleed",
                    detail=(f"carried into the bleed on {', '.join(touched)}; nothing reaches the trim on the other sides" if touched
                            else "no artwork reaches the trim (paper white at every edge), so there is nothing to bleed"))
    else:
        rep.add(rid("bleed:ring"), "skipped" if not sc else "fail", "artwork that reaches the trim runs on into the bleed",
                detail="not verified: no sidecar" if not sc else "there is no bleed to look at")

    # ---- geometry from the sidecar
    els = sc["geometry"]["elements"] if sc else []
    trim_w, trim_h = (sc["trim_mm"] if sc else (tw, th))
    if sc:
        # bleed geometry: an element that reaches a trim edge must run to the page edge
        probs = []
        for e in els:
            if e["kind"] != "bleed":
                continue
            x, y, w, h = e["rect"]
            for side, edge, want, cond in (("left", x, -bleed, x <= EDGE_MM), ("top", y, -bleed, y <= EDGE_MM),
                                           ("right", x + w, trim_w + bleed, x + w >= trim_w - EDGE_MM),
                                           ("bottom", y + h, trim_h + bleed, y + h >= trim_h - EDGE_MM)):
                if cond and abs(edge - want) > EDGE_MM and ((edge > want) if side in ("left", "top") else (edge < want)):
                    probs.append(f"{short(e)} reaches the {side} trim edge but stops at {fmt(edge)} mm; it must run to {fmt(want)} mm")
        rep.add(rid("bleed:geometry"), "fail" if probs else "pass", "art that touches the trim runs to the page edge (data-print-bleed)",
                detail="; ".join(probs[:4]) if probs else f"{sum(1 for e in els if e['kind'] == 'bleed')} bleed element(s), none stops at the trim")
        # safe zone
        safe = cfg["safe_zone_mm"]
        out = []
        for e in els:
            if e["kind"] == "bleed" or e.get("bleed_art"):
                continue
            x, y, w, h = e["rect"]
            gaps = {"left": x, "top": y, "right": trim_w - (x + w), "bottom": trim_h - (y + h)}
            worst = min(gaps, key=gaps.get)
            if gaps[worst] < safe - EPS_MM:
                out.append(f"{e['kind']} '{short(e)}' is {fmt(gaps[worst])} mm from the {worst} trim edge")
        rep.add(rid("safe-zone"), "fail" if out else "pass", f"nothing within {fmt(safe)} mm of the trim",
                detail="; ".join(out[:4]) + (f" (+{len(out) - 4} more)" if len(out) > 4 else "") if out else
                f"{sum(1 for e in els if e['kind'] != 'bleed')} element(s), all at least {fmt(safe)} mm inside the trim")
        # line weights
        lines = [e for e in els if e["kind"] in ("stroke", "border", "rule")]
        thin = [f"{e['kind']} '{short(e)}' is {e['weight_pt']:g} pt" + (" (light on dark)" if e.get("reversed") else "") for e in lines
                if e["weight_pt"] < (cfg["min_line_reversed_pt"] if e.get("reversed") else cfg["min_line_pt"]) - 1e-6]
        rep.add(rid("line-weight"), "fail" if thin else "pass",
                f"no line thinner than {cfg['min_line_pt']:g} pt ({cfg['min_line_reversed_pt']:g} pt light on dark)",
                detail="; ".join(thin[:4]) if thin else f"{len(lines)} line(s) measured, thinnest {min((e['weight_pt'] for e in lines), default=0):g} pt")
        # text sizes
        texts = [e for e in els if e["kind"] == "text"]
        small = [f"'{short(e)}' is {e['font_pt']:g} pt" for e in texts if e["font_pt"] < cfg["min_text_pt"]]
        rep.add(rid("text-size"), "fail" if small else "pass", f"no text smaller than {cfg['min_text_pt']:g} pt",
                detail="; ".join(small[:4]) if small else f"{len(texts)} text run(s), smallest {min((e['font_pt'] for e in texts), default=0):g} pt")
        unv = sc["geometry"].get("unverifiable", [])
        rev = [e for e in texts if e.get("reversed")]
        rsmall = [f"'{short(e)}' is {e['font_pt']:g} pt" for e in rev if e["font_pt"] < cfg["min_reversed_text_pt"]]
        if unv:
            rep.add(rid("reversed-text"), "skipped", f"no light-on-dark text smaller than {cfg['min_reversed_text_pt']:g} pt",
                    detail="not verified: " + "; ".join(u["why"] + f" ('{u['text']}')" for u in unv[:2]))
        else:
            rep.add(rid("reversed-text"), "fail" if rsmall else "pass", f"no light-on-dark text smaller than {cfg['min_reversed_text_pt']:g} pt",
                    detail="; ".join(rsmall[:4]) if rsmall else f"{len(rev)} reversed text run(s), smallest {min((e['font_pt'] for e in rev), default=0):g} pt")
        # logo size
        logos = [e for e in els if e["kind"] in ("svg", "image") and e.get("id") == "logo"]
        if not logos:
            rep.add(rid("logo-size"), "info", f"the logo is at least {cfg['min_logo_mm']:g} mm high", detail='no element marked data-print-id="logo"')
        else:
            low = [f"'{short(e)}' is {fmt(e['rect'][3])} mm high" for e in logos if e["rect"][3] < cfg["min_logo_mm"] - EPS_MM]
            rep.add(rid("logo-size"), "fail" if low else "pass", f"the logo is at least {cfg['min_logo_mm']:g} mm high",
                    detail="; ".join(low) if low else ", ".join(f"{fmt(e['rect'][3])} mm" for e in logos))
    else:
        for k in ("bleed:geometry", "safe-zone", "line-weight", "text-size", "reversed-text", "logo-size"):
            rep.add(rid(k), "skipped", k, detail="not verified: no sidecar (the text is outlined, so only the sidecar knows where it was)")

    # ---- transparency, fonts, colour
    dom = sc["geometry"].get("transparency", []) if sc else []
    tr = info["transparency"] + [f"<{t['tag']}>: {', '.join(t['why'])}" for t in dom]
    rep.add(rid("transparency"), "fail" if tr else "pass", "no transparency (opacity, soft mask, blend mode, shadow, masked image)",
            detail="; ".join(tr[:4]) if tr else "no /ca, /CA, /SMask, blend mode or masked image in the PDF" + ("; none in the page" if sc else ""))
    rep.add(rid("fonts"), "fail" if info["fonts"] else "pass", "text is outlined (the PDF holds no fonts)",
            detail=("fonts still in the file: " + ", ".join(sorted(set(info["fonts"]))[:4])) if info["fonts"] else "no font objects")
    has_intent = bool(info["output_intents"])
    cs = set(info["colour_spaces"])
    if has_intent:
        n4 = all(oi["n"] == 4 for oi in info["output_intents"])
        ok = n4 and "/DeviceRGB" not in cs
        rep.add(rid("colour"), "pass" if ok else "fail", "with an output intent the content is CMYK",
                detail=f"output intent profile N={[oi['n'] for oi in info['output_intents']]}; colour spaces used: {', '.join(sorted(cs)) or 'none'}")
    else:
        ok = not (cs & {"/DeviceCMYK", "/Separation", "/DeviceN", "/ICCBased"})
        rep.add(rid("colour"), "pass" if ok else "fail", "without an output intent the file is RGB (no CMYK or spot colour claimed)",
                detail=f"colour spaces used: {', '.join(sorted(cs)) or 'DeviceRGB operators only'}; RGB proof, spot colours are not produced")

    # ---- the label: honest print, never a conformance claim
    subject = info["info"].get("/Subject", "")
    xmp_desc = (re.findall(r"<dc:description>.*?<rdf:li[^>]*>(.*?)</rdf:li>", info["xmp"], re.S) or [""])[0]
    texts_about = [subject, xmp_desc, info["info"].get("/Keywords", ""), info["info"].get("/Title", "")]
    claims_x = bool(info["gts_version"] or info["xmp_gts_version"] or any("PDF/X" in t for t in texts_about) or pp.SUFFIX_X4 in pdf.name)
    bad_claim = [t for t in texts_about if pp.CLAIM_WORDS.search(pp.NOT_READY.sub("", t))]
    probs = []
    if claims_x and not has_intent:
        probs.append("the file claims PDF/X (Info, XMP, label or file name) but has no output intent made from a CMYK profile: PDF/X-4 needs --icc")
    if bad_claim:
        probs.append(f"claim words in the metadata: {bad_claim[0]!r} (no file of ours says it conforms, is compliant or is print-ready)")
    exact_x4 = subject == pp.LABEL_X4 and pp.SUFFIX_X4 + ".pdf" in pdf.name
    exact_rgb = subject == pp.LABEL_RGB and pp.SUFFIX_RGB + ".pdf" in pdf.name
    if claims_x and has_intent and "candidate" not in subject.lower():
        probs.append(f"PDF/X is named without the word 'candidate' ({subject!r}): the only wording allowed is {pp.LABEL_X4!r}")
    rep.add(rid("label:claims"), "fail" if probs else "pass", "no PDF/X claim without a profile, no conformance or print-ready claim",
            detail="; ".join(probs) if probs else f"the file says {subject!r} and claims nothing more")
    probs = []
    if has_intent and not exact_x4:
        probs.append(f"it has an output intent, so Subject and file name must be the PDF/X-4 candidate label ({subject!r}, {pdf.name})")
    if not has_intent and not exact_rgb:
        probs.append(f"it has no output intent, so Subject and file name must be the RGB proof label ({subject!r}, {pdf.name})")
    if sc and bool(sc.get("icc")) != has_intent:
        probs.append("the sidecar says " + ("an --icc profile was given" if sc.get("icc") else "no --icc profile was given") +
                     f" but the PDF {'has' if has_intent else 'has no'} output intent")
    if sc and sc.get("label") != subject:
        probs.append(f"the sidecar label {sc.get('label')!r} differs from the PDF's Subject {subject!r}")
    if has_intent and icc_file is not None:
        want = pp.sha256_file(icc_file)
        if want not in {oi["profile_sha256"] for oi in info["output_intents"]}:
            probs.append(f"the embedded profile is not {icc_file.name} (sha256 differs)")
    if not has_intent and icc_file is not None:
        probs.append(f"--icc {icc_file.name} was given but the PDF has no output intent")
    rep.add(rid("label:icc"), "fail" if probs else "pass", "the label matches the presence of the user's profile (--icc)",
            detail="; ".join(probs) if probs else (f"profile embedded, label {pp.LABEL_X4!r}" if has_intent else f"no profile, label {pp.LABEL_RGB!r}"))
    dp = determinism.lint_file(pdf)
    rep.add(rid("dates"), "fail" if dp else "pass", "dates and ID are fixed (the same input gives the same bytes)", detail="; ".join(dp))


def main() -> int:
    ap = Parser(prog="brand-creator print-check", description=__doc__, formatter_class=__import__("argparse").RawDescriptionHelpFormatter)
    add_project_arg(ap)
    ap.add_argument("pdf", nargs="*", help="print PDFs inside the project (default: every print PDF in assets/manifest.json)")
    ap.add_argument("--icc", help="the profile you gave `emit print`: the PDF's embedded profile must be this file")
    a = ap.parse_args()
    project = find_project(a.project)
    cfg, cfg_src = pp.load_config(project)
    icc_file = Path(a.icc).expanduser().resolve() if a.icc else None
    if icc_file and not icc_file.is_file():
        fail(EXIT_USAGE, f"--icc not found: {a.icc}")
    files = pdfs_to_check(project, a.pdf)
    rep = Report("print-check", project, [project / pp.CONFIG_FILE], renderer="none (reads PDFs: poppler pdfinfo and pdftoppm, pikepdf)")
    if not files:
        rep.add("print:pdfs", "skipped", "there are print PDFs to check",
                detail="not verified: no print PDF in assets/manifest.json; run `brand-creator emit print`")
    for f in files:
        if not f.is_file():
            rep.add(f"{f.stem}:file", "fail", "the PDF exists", detail=f"{rel(project, f)} is listed but missing")
            continue
        check_one(project, f, cfg, icc_file, rep)
    rep.extra.update({"thresholds": cfg, "thresholds_source": cfg_src, "files": [rel(project, f) for f in files],
                      "note": "passing this check does not make a file print-ready: preflight with your printer's tool and get the printer's proof"})
    return rep.finish(quiet_pass=True)


main_guard(main)
