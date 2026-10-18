#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.11"
# dependencies = ["pikepdf==10.17.0"]
# ///
"""brand-creator emit print: stationery as honest print PDFs, plus an HTML e-mail signature.

Pieces (assets/print/): business-card-front, business-card-back, letterhead, envelope, and email-signature.html with its logo PNGs.
Each PDF is made like this and in no other way: the page is HTML (templates/print/, or --template-dir), exactly trim + 2 x bleed with the crop
marks drawn in the bleed; Chromium prints it (render.mjs pdf, the only Chromium driver) and measures every text, logo and line in the same render;
Ghostscript outlines the text (-dNoOutputFonts); pikepdf sets MediaBox, TrimBox and BleedBox, the metadata and a fixed date and ID.

What the file is called, and what it says about itself, depends on one thing only:
  without --icc   "RGB proof, not print-ready"   (Subject, XMP description, file name <piece>.rgb-proof.pdf)
  with --icc FILE "PDF/X-4 candidate (preflight with your printer)"   (file name <piece>.pdfx4-candidate.pdf). FILE is YOUR printer's CMYK output
                  profile; brand-creator bundles none. Colours are converted through it and written with a PDF/X-4 output intent.
Nothing here can check PDF/X conformance (that needs a preflight tool), so no file says it conforms. Spot colours are not produced.

Sizes come from the print_region table (scripts/emitters/print-regions.json: EU, US, JP): card, paper (A4 or Letter), envelope (DL or #10) and the
default bleed (3 mm, 0.125 in), which is printer-specific: ask the printer and pass --bleed. The region is --region, else the one region the
brief's "Region and language" line names (exit 2 when it names none or several). Text comes from FACTS.md labels only (contact name, contact role,
contact email, contact phone, postal address, website or homepage, legal *); a missing label is left out and reported, never invented. Run
`brand-creator print-check` afterwards: it reads the boxes back and checks the physical rules in mm and pt. Needs gate G3.
"""
import argparse
import html
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "lib"))
sys.path.insert(0, str(HERE.parent / "printlib"))
import printpdf as pp  # noqa: E402
import svgtools  # noqa: E402
from _color import parse_hex, wcag_ratio  # noqa: E402
from _common import EXIT_CANNOT, EXIT_FAIL, EXIT_USAGE, confine, data_dir, fail, main_guard, plugin_root, rel, scratch_dir, sha256_bytes  # noqa: E402
from _emit import Drawing, Emit, add_logo_arg, fill_template  # noqa: E402

RENDER_TIMEOUT_S = 150
PIECES = ("business-card-front", "business-card-back", "letterhead", "envelope")
SIGNATURE = "email-signature"
CONTACT_LABELS = ("contact name", "contact role", "contact email", "contact phone", "postal address", "website")
FONT_SUFFIXES = (".ttf", ".otf", ".woff", ".woff2")
SYSTEM_FONTS = "Arial,Helvetica,sans-serif"
SHA_SHOWN = 9   # hex digits of the profile hash shown in the report


def wcag_ratio_hex(a: str, b: str) -> float:
    return wcag_ratio(parse_hex(a), parse_hex(b))


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def parse_mm(text: str, flag: str) -> tuple[float, float]:
    m = re.fullmatch(r"(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)", text.strip())
    if not m or float(m.group(1)) <= 0 or float(m.group(2)) <= 0:
        fail(EXIT_USAGE, f"{flag} {text!r}: write it as WIDTHxHEIGHT in millimetres (two numbers joined by x)")
    return float(m.group(1)), float(m.group(2))


def num(v: float) -> str:
    return f"{v:.3f}".rstrip("0").rstrip(".")


def render_pdf(project: Path, html_rel: str, size: tuple[float, float], bleed: float, out: Path, measure: Path) -> dict:
    data_dir()
    cmd = ["node", str(plugin_root() / "scripts" / "render.mjs"), "pdf", html_rel, "--project", str(project), "--out", str(out),
           "--size-mm", f"{num(size[0])}x{num(size[1])}", "--bleed-mm", num(bleed), "--measure", str(measure), "--scheme", "light", "--json"]
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=RENDER_TIMEOUT_S)
    except FileNotFoundError:
        fail(EXIT_CANNOT, "node not found on PATH (install Node 22+ and run /brand-creator:setup)")
    if cp.returncode != 0:
        fail(cp.returncode if cp.returncode in (1, 2, 3) else EXIT_CANNOT, cp.stderr.strip() or cp.stdout.strip() or "render.mjs pdf failed")
    return json.loads(cp.stdout.strip().splitlines()[-1])


def clean_svg(svg: str, what: str) -> str:
    svg = re.sub(r"^\s*<\?xml[^>]*>\s*", "", svg)
    try:
        svgtools.viewbox(svgtools.parse(svg))
    except svgtools.SvgError as e:
        fail(EXIT_FAIL, f"{what}: {e}")
    return svg


def main() -> int:
    def args(ap):
        add_logo_arg(ap)
        ap.add_argument("--region", help="print region: EU, US or JP (default: the one the brief's 'Region and language' line names)")
        ap.add_argument("--bleed", help="bleed in mm (default: the region's, stated as printer-specific: ask your printer)")
        ap.add_argument("--icc", help="YOUR printer's CMYK output profile (.icc). With it the PDFs are 'PDF/X-4 candidate (preflight with your "
                                      "printer)'; without it they are 'RGB proof, not print-ready'. brand-creator bundles no profile")
        ap.add_argument("--only", help="comma list of pieces to build: " + ", ".join(PIECES + (SIGNATURE,)) + " (default: all)")
        ap.add_argument("--card-mm", help="business card trim WxH in mm, instead of the region's")
        ap.add_argument("--envelope-mm", help="envelope trim WxH in mm, instead of the region's (a local format)")
        ap.add_argument("--template-dir", help="folder with your copies of the templates (default: templates/print in the plugin)")
        ap.add_argument("--font-file", help="a brand font file inside the project (ttf, otf, woff, woff2); without it the text uses a system font")
        ap.add_argument("--font-family", help="family name for --font-file (default: the file name)")
        ap.add_argument("--tagline", default="", help="a line under the card logo; must be a value in FACTS.md")
        ap.add_argument("--image-base-url", help="absolute https URL where you will host the signature's PNGs (default: a placeholder, warned)")

    e = Emit.begin("print", __doc__, add_args=args, tiers=("standard", "full"), tier_what="print stationery")
    a, project = e.a, e.project
    if a.icc and not Path(a.icc).expanduser().is_file():
        fail(EXIT_USAGE, f"--icc not found: {a.icc}")
    only = [x.strip() for x in a.only.split(",")] if a.only else list(PIECES) + [SIGNATURE]
    bad = [x for x in only if x not in PIECES + (SIGNATURE,)]
    if bad:
        fail(EXIT_USAGE, f"--only: unknown piece {', '.join(bad)} (known: {', '.join(PIECES + (SIGNATURE,))})")
    if a.image_base_url and not re.match(r"^https://[^\s/]+(/\S*)?$", a.image_base_url):
        fail(EXIT_USAGE, "--image-base-url must be an absolute https URL (mail clients load remote images from a host you control)")
    pp.need_gs()

    region, region_src = pp.pick_region(project, a.region)
    row_id = pp.regions()[region]["id"]
    sz = e.sizes(row_id)
    cfg, cfg_src = pp.load_config(project)
    e.add_input(project / pp.CONFIG_FILE)
    bleed = float(a.bleed) if a.bleed else float(sz["bleed_mm"])
    if bleed <= 0:
        fail(EXIT_USAGE, "--bleed must be above 0 (a print page is trim + 2 x bleed)")
    e.rep.add("note:region", "info", f"print region {region}", detail=f"from {region_src}; card, {sz['paper']} paper and {sz['envelope']} envelope from print-regions.json")
    e.rep.add("note:bleed", "info", f"bleed {num(bleed)} mm",
              detail=("--bleed" if a.bleed else f"the {region} default") + ": the bleed is printer-specific, ask your printer for its own template and pass --bleed")
    trims = {"business-card-front": parse_mm(a.card_mm, "--card-mm") if a.card_mm else tuple(sz["business_card_mm"]),
             "letterhead": tuple(sz["paper_mm"]),
             "envelope": parse_mm(a.envelope_mm, "--envelope-mm") if a.envelope_mm else tuple(sz["envelope_mm"])}
    trims["business-card-back"] = trims["business-card-front"]

    icc = None
    if a.icc:
        icc = pp.icc_info(Path(a.icc).expanduser().resolve())
        e.rep.add("note:icc", "info", "user-supplied CMYK profile", detail=f"{icc['description']} (ICC {icc['version']}, {icc['class'].strip()}, sha256 {icc['sha256'][:SHA_SHOWN]}); "
                  "colours are converted through it. brand-creator does not bundle or vouch for it")
    label = pp.LABEL_X4 if icc else pp.LABEL_RGB
    suffix = pp.SUFFIX_X4 if icc else pp.SUFFIX_RGB
    if not icc:
        e.rep.add("note:rgb-proof", "info", pp.LABEL_RGB,
                  detail="no --icc, so no CMYK conversion and no output intent: the PDFs are RGB proofs. Pass your printer's profile with --icc for a PDF/X-4 candidate")

    # ---- inputs: colours, art, facts, font
    paper, ink = (e.colour("light", "color.bg"), e.colour("light", "color.text"))
    muted = e.modes["light"].get("color.muted", ink)
    accent = e.modes["light"].get("color.accent", ink)
    logo_svg, logo_src = e.logo_art()
    logo_svg = clean_svg(logo_svg, logo_src)
    art = Drawing(logo_svg, None if logo_src == "the mark" else logo_src, None)
    logo_dark = clean_svg(e.dark_svg(art), f"dark artwork of {logo_src}")
    e.rep.add("note:logo art", "info", "outlined logo art on the stationery", detail=logo_src)
    facts = e.facts()
    tagline = e.require_fact(a.tagline, what="--tagline") if a.tagline else ""
    if "website" not in facts and "homepage" in facts:   # `homepage` is the label `emit linux` reads: one fact, either label
        facts["website"] = facts["homepage"]
    contact = {k: facts[k] for k in CONTACT_LABELS if k in facts}
    legal = [v for k, v in facts.items() if k.startswith("legal")]
    for k in CONTACT_LABELS:
        if k not in facts:
            e.rep.add(f"note:fact {k}", "warn", "not in FACTS.md", detail=f"the pieces leave out the {k}: add a FACTS.md row labelled '{k}' (owner-confirmed, with a source) and re-run")
    font_face, font_family = "", SYSTEM_FONTS
    if a.font_file:
        ff = confine(project, a.font_file, what="--font-file")
        if ff.suffix.lower() not in FONT_SUFFIXES or not ff.is_file():
            fail(EXIT_USAGE, f"--font-file must be an existing {'/'.join(FONT_SUFFIXES)} file inside the project")
        fam = a.font_family or ff.stem
        font_face = f'@font-face{{font-family:"{fam}";src:url("/{rel(project, ff)}")}}'
        font_family = f'"{fam}",{SYSTEM_FONTS}'
        e.add_input(ff)
        e.rep.add("note:font", "info", "brand font on the stationery", detail=f"{fam} from {rel(project, ff)}; its text is outlined in the PDF (check the licence allows it: fontcheck)")
    else:
        e.rep.add("note:font", "warn", "system font",
                  detail="no --font-file: the text is set in a system sans-serif, so what prints depends on this machine. Pass the brand font for stationery")

    tpl_dir = Path(a.template_dir).expanduser().resolve() if a.template_dir else plugin_root() / "templates" / "print"
    if not tpl_dir.is_dir():
        fail(EXIT_USAGE, f"--template-dir not found: {tpl_dir}")

    def template(name: str) -> str:
        f = tpl_dir / f"{name}.html"
        if not f.is_file():
            fail(EXIT_USAGE, f"template not found: {f}")
        return f.read_text(encoding="utf-8")

    def lines(vals: list[str]) -> str:
        return "".join(f"<div>{esc(v)}</div>" for v in vals)

    def contact_lines() -> list[str]:
        return [contact[k] for k in ("contact email", "contact phone", "website", "postal address") if k in contact]

    scratch = scratch_dir(project, "print")
    lang = str(e.st.get("content_languages") or "").split(",")[0].strip()
    if not lang:
        fail(EXIT_USAGE, "content_languages is not set in BRAND-STATE.md (the language of the brand's own text, for example en or pl); it is never "
                         "defaulted from the chat language. Set it: brand-creator state --set content_languages=en")
    made: dict[str, dict] = {}

    for piece in PIECES:
        if piece not in only:
            e.kept.append(f"{e.out}/{piece}")
            continue
        trim = trims[piece]
        lay = pp.LAYOUT[piece]
        margin = max(lay["margin"], cfg["safe_zone_mm"] + pp.MARGIN_OVER_SAFE_MM)
        page = (trim[0] + 2 * bleed, trim[1] + 2 * bleed)
        if piece == "business-card-back":
            person = contact.get("contact name", "")
            role = contact.get("contact role", "")
            block = ""
            if person:
                block += f'<p class="person">{esc(person)}</p>'
            if role:
                block += f'<p class="role">{esc(role)}</p>'
            if contact_lines():
                block += f'<div class="lines">{lines(contact_lines())}</div>'
            if not block:
                fail(EXIT_FAIL, "business-card-back has nothing to say: FACTS.md has none of the labels contact name, contact role, contact email, "
                                "contact phone, postal address, website. Add the owner-confirmed rows first")
        elif piece == "envelope":
            sender = ([contact["contact name"]] if "contact name" in contact else [e.brand]) + ([contact["postal address"]] if "postal address" in contact else [])
            block = lines(sender)
        else:
            block = lines(([contact["contact name"]] if "contact name" in contact else []) + contact_lines())
        values = {
            "lang": lang, "name": e.brand, "page_w": num(page[0]), "page_h": num(page[1]), "bleed": num(bleed), "trim_w": num(trim[0]),
            "trim_h": num(trim[1]), "safe": num(cfg["safe_zone_mm"]), "margin": num(margin), "paper": paper, "ink": ink, "muted": muted,
            "accent": accent, "font_face": font_face, "font_family": font_family, "marks": pp.crop_marks_svg(page[0], page[1], bleed),
            "logo": logo_svg, "logo_dark": logo_dark, "contact_block": block,
            "tagline_block": f'<p class="tagline">{esc(tagline)}</p>' if tagline else "",
            "legal_block": f'<div class="legal">{lines(legal)}</div>' if legal else "",
            "bar_h": num(bleed + lay.get("bar_extra", 0.0)), "rule_y": num(margin + lay.get("rule_below", 0.0)),
        }
        raw_names = ("font_face", "marks", "logo", "logo_dark", "contact_block", "tagline_block", "legal_block")
        tpl = template(piece)
        src_rel = f"{e.out}/_build/{piece}.html"
        src = confine(project, src_rel, what="print source")
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text(fill_template(tpl, values, raw=raw_names), encoding="utf-8")
        raw_pdf, gs_pdf, meas = scratch / f"{piece}.raw.pdf", scratch / f"{piece}.gs.pdf", scratch / f"{piece}.measure.json"
        render_pdf(project, src_rel, page, bleed, raw_pdf, meas)
        title = f"{e.brand} {piece.replace('-', ' ')}"
        pp.gs_outline(raw_pdf, gs_pdf, icc=icc, title=title, scratch=scratch / f"{piece}-gs")
        pdf_bytes = pp.finish_pdf(gs_pdf.read_bytes(), title=title, label=label, trim_mm=trim, bleed_mm=bleed, pdfx=bool(icc))
        pdf_rel = f"{e.out}/{piece}{suffix}.pdf"
        side_rel = f"{e.out}/{piece}.print.json"
        sidecar = {
            "schema": 1, "piece": piece, "region": region, "region_row": row_id, "label": label,
            "pdf": {"path": pdf_rel, "sha256": sha256_bytes(pdf_bytes), "bytes": len(pdf_bytes)},
            "trim_mm": list(trim), "bleed_mm": bleed, "bleed_source": "--bleed" if a.bleed else f"{region} default (printer-specific)",
            "page_mm": [round(page[0], 3), round(page[1], 3)],
            "icc": {"description": icc["description"], "sha256": icc["sha256"], "colour_space": icc["colour_space"]} if icc else None,
            "template": {"name": f"{piece}.html", "sha256": sha256_bytes(tpl.encode())},
            "font": {"family": font_family, "file": rel(project, ff) if a.font_file else None},
            "measured_by": "Chromium DOM measurement in the same render as the PDF (text is outlined in the file, so it is not in the file)",
            "geometry": json.loads(meas.read_text(encoding="utf-8")),
        }
        side_bytes = (json.dumps(sidecar, indent=1, ensure_ascii=False) + "\n").encode()
        e.put(pdf_rel, pdf_bytes, [row_id], slot=f"print-{piece}", size=f"{num(page[0])}x{num(page[1])}mm", resampled_by="PAGE", note=label, label=label,
              qa=["print"])
        e.put(side_rel, side_bytes, [row_id], slot=f"print-{piece}-geometry", resampled_by="PAGE",
              note="what Chromium measured in the render that made the PDF; print-check reads it")
        made[piece] = {"pdf": pdf_rel, "sidecar": side_rel, "trim_mm": list(trim), "page_mm": [round(page[0], 3), round(page[1], 3)]}

    # ---- the e-mail signature (HTML, not PDF)
    if SIGNATURE not in only:
        e.kept.append(f"{e.out}/{SIGNATURE}/")
    if SIGNATURE in only:
        sg = e.sizes("email-signature")
        em = e.sizes("email-logo")
        ratio = wcag_ratio_hex(ink, paper)
        if ratio < sg["min_contrast"]:
            fail(EXIT_FAIL, f"the signature's text colour {ink} on its ground {paper} is {ratio:.2f}:1, below {sg['min_contrast']}:1 (WCAG 2.2 AA text); "
                            f"fix the tokens color.text and color.bg")
        sig_muted = muted if wcag_ratio_hex(muted, paper) >= sg["min_contrast"] else ink
        if sig_muted != muted:
            e.rep.add("note:signature muted colour", "warn", "color.muted is below the text contrast on the ground", detail="the signature uses color.text for every line")
        base = (a.image_base_url or "https://YOUR-HOST.invalid/brand").rstrip("/")
        if not a.image_base_url:
            e.rep.add("note:signature images", "warn", "image URLs are placeholders",
                      detail=f"the signature points at {base}/: host the PNGs from {e.out}/{SIGNATURE}/ on a host you control and re-run with --image-base-url")
        h1 = em["display_height"]
        vb = svgtools.viewbox(svgtools.parse(logo_svg))
        w1 = round(h1 * vb[2] / vb[3])
        names = {}
        for sc in sg["logo_scales"]:
            w, h = w1 * sc, h1 * sc
            png = e.png(svgtools.tile(logo_svg, w, h, bg=paper, content=1.0), w, h, bg=paper)
            fname = "logo.png" if sc == 1 else f"logo@{sc}x.png"
            names[sc] = fname
            e.put(f"{e.out}/{SIGNATURE}/{fname}", png, ["email-signature", "email-logo"], slot="email-signature-logo", size=f"{w}x{h}", resampled_by="OURS",
                  note=f"shown {h1} px high at 1x, opaque on the brand ground so a dark mode cannot hide it")
        person = ""
        if "contact name" in contact:
            person += f'<div style="font-weight:bold;font-size:14px;line-height:20px;color:{ink}">{esc(contact["contact name"])}</div>'
        if "contact role" in contact:
            person += f'<div style="color:{sig_muted}">{esc(contact["contact role"])}</div>'
        rows = []
        for k, href in (("contact email", "mailto:"), ("contact phone", "tel:"), ("website", "")):
            if k in contact:
                v = contact[k]
                target = href + re.sub(r"[^\d+]", "", v) if href == "tel:" else (href + v if href else v)
                if href == "" and not re.match(r"^https?://", v):
                    target = "https://" + v
                rows.append(f'<a href="{esc(target)}" style="color:{ink};text-decoration:underline">{esc(v)}</a>')
        if "postal address" in contact:
            rows.append(f'<span style="color:{sig_muted}">{esc(contact["postal address"])}</span>')
        values = {"lang": lang, "name": e.brand, "paper": paper, "ink": ink, "accent": accent, "logo_url": f"{base}/{names[1]}",
                  "logo_url_2x": f"{base}/{names[2]}" if 2 in names else f"{base}/{names[1]}", "logo_w": w1, "logo_h": h1,
                  "person_block": person, "lines_block": "<br>".join(rows) if rows else ""}
        if not person and not rows:
            e.rep.add("note:signature text", "warn", "no contact facts", detail="the signature shows the logo only: add contact name, contact role, contact email, contact phone, website rows to FACTS.md")
        sig_html = fill_template(template(SIGNATURE), values, raw=("person_block", "lines_block"))
        e.put(f"{e.out}/{SIGNATURE}/{SIGNATURE}.html", sig_html.encode(), ["email-signature"], slot="email-signature", resampled_by="PAGE",
              note=f"{ratio:.2f}:1 text on its own ground; table layout, inline styles")
        made[SIGNATURE] = {"html": f"{e.out}/{SIGNATURE}/{SIGNATURE}.html"}

    e.rep.extra.update({"region": region, "region_source": region_src, "bleed_mm": bleed, "label": label, "icc": bool(icc), "pieces": made,
                        "thresholds": cfg, "thresholds_source": cfg_src})
    rc = e.finish()
    print(f"emit print: {label}" + ("" if icc else " (no --icc)") + f"; region {region}, bleed {num(bleed)} mm (printer-specific). Next: brand-creator print-check")
    return rc


main_guard(main)
