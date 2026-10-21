"""emit print, print-check, emit presskit and the social posts: honest print (plan review MUST #12), in mm and pt.

Expected values are worked out by hand (1 mm = 72 / 25.4 = 2.8346 pt; a 91 x 61 mm EU card page is 257.95 x 172.91 pt; a US card is exactly
3.5 x 2 in = 252 x 144 pt and its 0.125 in bleed is 9 pt) or read with poppler (`pdfinfo -box`, `pdffonts`, `pdfinfo -meta`), a tool independent of the
pikepdf that writes the boxes. Mutation tests break a scratch copy of a template or of a PDF and assert the mutation applied and the gate now fails.
A PDF/X claim without --icc must fail; with --icc the file is only ever a candidate."""
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from helpers import FIXTURES, ROOT, bc, mutate, report

import determinism
import printpdf as pp
from pxio import png_size

pytestmark = [pytest.mark.requires_setup, pytest.mark.requires_resvg, pytest.mark.requires_gs]

EMAIL = "hello" + chr(64) + "example.com"     # built here: a shipped file never holds an address-shaped string (test_static)
PT_PER_MM = 72 / 25.4   # worked out by hand: 25.4 mm to the inch, 72 pt to the inch
PIECES = ("business-card-front", "business-card-back", "letterhead", "envelope")
RGB = "RGB proof, not print-ready"
X4 = "PDF/X-4 candidate (preflight with your printer)"


def with_contacts(p: Path) -> None:
    """The Acme example's FACTS.md plus the one contact row it cannot hold in a shipped file: the e-mail address."""
    shutil.copy2(FIXTURES / "FACTS.md", p / "FACTS.md")
    with (p / "FACTS.md").open("a") as f:
        f.write(f"| contact email | {EMAIL} | owner, intake | 2026-10-17 |\n")


def pdfinfo_box(pdf: Path) -> dict:
    out = subprocess.run(["pdfinfo", "-box", str(pdf)], capture_output=True, text=True, check=True).stdout
    d = {}
    for ln in out.splitlines():
        m = re.match(r"^(MediaBox|TrimBox|BleedBox):\s+(.*)$", ln)
        if m:
            d[m.group(1)] = [float(v) for v in m.group(2).split()]
        m = re.match(r"^(Subject|Title|Pages):\s+(.*)$", ln)
        if m:
            d[m.group(1)] = m.group(2).strip()
    return d


def size_pt(box):
    return box[2] - box[0], box[3] - box[1]


def fonts(pdf: Path) -> list[str]:
    out = subprocess.run(["pdffonts", str(pdf)], capture_output=True, text=True, check=True).stdout.splitlines()[2:]
    return [ln for ln in out if ln.strip()]


def results(p: Path, tool="print-check") -> dict:
    return {r["id"]: r for r in report(p, tool)["results"]}


def printed_files(p: Path) -> dict[str, Path]:
    d = p / "assets" / "print"
    return {n: next(d.glob(f"{n}.*.pdf")) for n in PIECES}


def gs_cmyk_profile() -> Path:
    """A CMYK profile for the PDF/X-4 path. Ghostscript ships one; brand-creator bundles none, and the test says so if there is none to use."""
    gs = shutil.which("gs")
    # Homebrew: <prefix>/share/ghostscript/<version>/iccprofiles; Debian and Ubuntu: /usr/share/color/icc/ghostscript (iccprofiles links to it)
    for root in (Path(gs).resolve().parents[1] / "share" / "ghostscript", Path(gs).resolve().parents[2] / "share" / "ghostscript",
                 Path(gs).resolve().parents[1] / "share" / "color" / "icc" / "ghostscript"):
        found = sorted(root.rglob("default_cmyk.icc")) if root.is_dir() else []
        if found:
            return found[0]
    msg = "NOT VERIFIED: no CMYK ICC profile found next to Ghostscript to stand in for the user's printer profile"
    if __import__("os").environ.get("BRAND_CREATOR_REQUIRE_ALL") == "1":
        pytest.fail(msg)
    pytest.skip(msg)


@pytest.fixture(scope="session")
def printed(golden, tmp_path_factory):
    """A Standard-tier Acme project with contact facts and the EU print pieces emitted without --icc."""
    p = tmp_path_factory.mktemp("printproj") / "acme"
    shutil.copytree(golden, p)
    with_contacts(p)
    for k, v in (("tier", "standard"), ("content_languages", "en")):
        assert bc("state", "--set", f"{k}={v}", project=p).returncode == 0
    r = bc("emit", "print", "--region", "EU", project=p)
    assert r.returncode == 0, r.stdout + r.stderr
    return p


@pytest.fixture
def proj(printed, tmp_path):
    dst = tmp_path / "acme"
    shutil.copytree(printed, dst)
    return dst


def template_copy(where: Path) -> Path:
    """A scratch copy of templates/print for a test to break with mutate() (which proves the mutation applied)."""
    d = where / "tpl"
    shutil.copytree(ROOT / "templates" / "print", d)
    return d


# ---------------------------------------------------------------- the region table and the pure helpers (no tools)

def test_region_comes_from_the_flag_or_from_exactly_one_region_in_the_brief(tmp_path):
    (tmp_path / "brief").mkdir()
    brief = tmp_path / "brief" / "BRIEF.md"

    def pick(line, flag=None):
        brief.write_text(f"- Region and language: {line}\n")
        return pp.pick_region(tmp_path, flag)[0]
    assert pick("Poland, Polish") == "EU"
    assert pick("the United States, English") == "US"
    assert pick("Japan, Japanese") == "JP"
    assert pick("Germany and Poland") == "EU"          # two countries of one region are one region
    assert pick("Japan, Japanese", "us") == "US"         # the flag wins
    from _common import CliError
    for line in ("one English-speaking market", "Poland and the United States", "(drives top-level domains, trademark offices, print sizes, glyph set)"):
        with pytest.raises(CliError) as e:
            pick(line)
        assert e.value.code == 2 and "Pass --region" in e.value.message


def test_region_table_rows_are_hand_checked_sizes_and_unverified():
    rows = pp.regions()
    assert set(rows) == {"EU", "US", "JP"}
    assert rows["EU"]["sizes"]["business_card_mm"] == [85, 55] and rows["JP"]["sizes"]["business_card_mm"] == [91, 55]
    us = rows["US"]["sizes"]
    assert us["business_card_mm"] == [88.9, 50.8] and us["business_card_in"] == [3.5, 2]    # 3.5 x 25.4 = 88.9, 2 x 25.4 = 50.8
    assert us["paper"] == "Letter" and us["envelope"] == "#10" and abs(us["bleed_mm"] - 0.125 * 25.4) < 1e-9
    assert rows["EU"]["sizes"]["paper"] == "A4" and rows["EU"]["sizes"]["envelope"] == "DL" and rows["EU"]["sizes"]["bleed_mm"] == 3
    assert all(r["status"] == "U" for r in rows.values())     # nobody has read these sizes at a printer or standards page


def test_crop_marks_are_eight_hairlines_in_the_bleed_with_no_opacity():
    svg = pp.crop_marks_svg(91, 61, 3)
    lines = re.findall(r'<line x1="([\d.]+)" y1="([\d.]+)" x2="([\d.]+)" y2="([\d.]+)" stroke="(#[0-9a-f]{6})" stroke-width="([\d.]+)"/>', svg)
    assert len(lines) == 16 and "data-print-mark" in svg and "opacity" not in svg     # 8 marks, each drawn twice (white halo under the black hairline)
    for x1, y1, x2, y2, colour, w in lines:
        x1, y1, x2, y2 = map(float, (x1, y1, x2, y2))
        # every mark lies in the bleed strip, on the extension of a trim edge, and stops 0.5 mm short of the trim corner
        assert 0 <= min(x1, x2) and max(x1, x2) <= 91 and 0 <= min(y1, y2) and max(y1, y2) <= 61
        if x1 == x2:
            assert x1 in (3, 88) and (max(y1, y2) <= 2.5 or min(y1, y2) >= 58.5)
        else:
            assert y1 in (3, 58) and (max(x1, x2) <= 2.5 or min(x1, x2) >= 88.5)
    assert {c for *_, c, _ in lines} == {"#ffffff", "#000000"} and min(float(w) for *_, w in lines) == 0.1
    assert pp.crop_marks_svg(91, 61, 0.4) == ""     # a bleed too small for a mark draws none rather than a mark in the trim


def test_the_config_file_rejects_a_typo_and_a_non_positive_number(tmp_path):
    from _common import CliError
    (tmp_path / "qa").mkdir()
    f = tmp_path / "qa" / "print.json"
    f.write_text('{"schema": 1, "safe_zone": 3}')
    with pytest.raises(CliError) as e:
        pp.load_config(tmp_path)
    assert e.value.code == 2 and "unknown key 'safe_zone'" in e.value.message
    f.write_text('{"schema": 1, "min_line_pt": 0}')
    with pytest.raises(CliError) as e:
        pp.load_config(tmp_path)
    assert e.value.code == 2 and "above 0" in e.value.message
    f.write_text('{"schema": 1, "safe_zone_mm": 5}')
    cfg, src = pp.load_config(tmp_path)
    assert cfg["safe_zone_mm"] == 5.0 and cfg["min_line_pt"] == pp.DEFAULTS["min_line_pt"] and src == "qa/print.json"


def test_an_icc_profile_must_be_cmyk(tmp_path):
    from _common import CliError
    rgb = tmp_path / "rgb.icc"
    head = bytearray(132)
    head[16:20], head[36:40], head[12:16] = b"RGB ", b"acsp", b"mntr"
    rgb.write_bytes(bytes(head))
    with pytest.raises(CliError) as e:
        pp.icc_info(rgb)
    assert e.value.code == 2 and "needs a CMYK output profile" in e.value.message
    notp = tmp_path / "x.icc"
    notp.write_bytes(b"not a profile" * 20)
    with pytest.raises(CliError) as e:
        pp.icc_info(notp)
    assert "no 'acsp' signature" in e.value.message


# ---------------------------------------------------------------- emit print without --icc: an RGB proof

def test_each_pdf_is_exactly_trim_plus_bleed_with_the_boxes_set_and_one_page(printed):
    for piece, (tw, th) in (("business-card-front", (85, 55)), ("business-card-back", (85, 55)), ("letterhead", (210, 297)), ("envelope", (220, 110))):
        b = pdfinfo_box(printed_files(printed)[piece])
        assert b["Pages"] == "1"
        mw, mh = size_pt(b["MediaBox"])
        assert abs(mw - (tw + 6) * PT_PER_MM) < 0.02 and abs(mh - (th + 6) * PT_PER_MM) < 0.02, (piece, mw, mh)       # page = trim + 2 x 3 mm
        tw_, th_ = size_pt(b["TrimBox"])
        assert abs(tw_ - tw * PT_PER_MM) < 0.02 and abs(th_ - th * PT_PER_MM) < 0.02, (piece, tw_, th_)
        assert all(abs(x - y) < 0.01 for x, y in zip(b["BleedBox"], b["MediaBox"]))                                     # BleedBox is the whole page
        inset = [b["TrimBox"][0] - b["MediaBox"][0], b["TrimBox"][1] - b["MediaBox"][1], b["MediaBox"][2] - b["TrimBox"][2], b["MediaBox"][3] - b["TrimBox"][3]]
        assert all(abs(i - 3 * PT_PER_MM) < 0.02 for i in inset), (piece, inset)                                         # 3 mm of bleed on every side


def test_the_text_is_outlined_so_the_pdf_holds_no_fonts(printed):
    for piece, pdf in printed_files(printed).items():
        assert fonts(pdf) == [], (piece, fonts(pdf))
        txt = subprocess.run(["pdftotext", str(pdf), "-"], capture_output=True, text=True).stdout.strip()
        assert txt == "", f"{piece}: text is still live ({txt[:30]!r})"


def test_without_icc_the_label_is_rgb_proof_in_the_metadata_the_xmp_and_the_file_name(printed):
    for piece, pdf in printed_files(printed).items():
        assert pdf.name == f"{piece}.rgb-proof.pdf"
        assert pdfinfo_box(pdf)["Subject"] == RGB
        meta = subprocess.run(["pdfinfo", "-meta", str(pdf)], capture_output=True, text=True).stdout
        assert RGB in meta and "GTS_PDFXVersion" not in meta
        raw = pdf.read_bytes()
        assert b"/OutputIntents" not in raw and b"GTS_PDFX" not in raw and b"PDF/X" not in raw and b"/DeviceCMYK" not in raw
    man = {a["path"]: a for a in json.loads((printed / "assets/manifest.json").read_text())["artefacts"]}
    assert man["assets/print/letterhead.rgb-proof.pdf"]["label"] == RGB and man["assets/print/letterhead.rgb-proof.pdf"]["qa"] == ["print"]


def test_the_pdfs_are_deterministic_and_a_second_emit_writes_nothing(proj):
    before = {n: p.read_bytes() for n, p in printed_files(proj).items()}
    r = bc("emit", "print", "--region", "EU", project=proj)
    assert r.returncode == 0 and "0 written" in r.stdout, r.stdout
    assert {n: p.read_bytes() for n, p in printed_files(proj).items()} == before
    for p in printed_files(proj).values():
        assert determinism.lint_file(p) == []
        assert b"1980" in p.read_bytes() and b"/ObjStm" not in p.read_bytes()


def test_the_sidecar_binds_the_geometry_to_the_pdf_by_hash(printed):
    import hashlib
    for piece, pdf in printed_files(printed).items():
        sc = json.loads((printed / "assets/print" / f"{piece}.print.json").read_text())
        assert sc["pdf"]["sha256"] == hashlib.sha256(pdf.read_bytes()).hexdigest() and sc["icc"] is None and sc["label"] == RGB
        assert sc["region"] == "EU" and sc["bleed_source"].startswith("EU default") and sc["geometry"]["page_mm"] == sc["page_mm"]


# ---------------------------------------------------------------- print-check on the clean set

def test_print_check_passes_the_clean_set_and_names_every_rule_once_per_piece(proj):
    r = bc("print-check", project=proj)
    assert r.returncode == 0, r.stdout + r.stderr
    rep = report(proj, "print-check")
    assert rep["status"] == "pass"
    ids = {x["id"] for x in rep["results"]}
    rules = {"bind", "pages", "page-size", "trim-box", "bleed-box", "bleed-width", "bleed:geometry", "bleed:ring", "safe-zone", "line-weight", "text-size",
             "reversed-text", "logo-size", "transparency", "fonts", "colour", "label:claims", "label:icc", "dates"}
    for piece in PIECES:
        stem = printed_files(proj)[piece].stem
        assert {f"{stem}:{k}" for k in rules} <= ids, (stem, rules - {i.split(':', 1)[1] for i in ids if i.startswith(stem + ":")})
    res = results(proj)
    assert "carried into the bleed" in res["business-card-back.rgb-proof:bleed:ring"]["detail"]          # the dark ground really runs into the bleed
    assert "nothing reaches the trim" in res["envelope.rgb-proof:bleed:ring"]["detail"] or "carried into the bleed" in res["envelope.rgb-proof:bleed:ring"]["detail"]
    assert rep["thresholds"]["safe_zone_mm"] == 3.0 and rep["thresholds_source"].startswith("defaults")
    assert "does not make a file print-ready" in rep["note"]


def test_a_sidecar_for_another_pdf_is_caught(proj):
    side = proj / "assets/print/letterhead.print.json"
    d = json.loads(side.read_text())
    d["pdf"]["sha256"] = "0" * 64
    side.write_text(json.dumps(d))
    r = bc("print-check", project=proj)
    assert r.returncode == 1 and results(proj)["letterhead.rgb-proof:bind"]["status"] == "fail"


# ---------------------------------------------------------------- mutations

def reemit_and_check(p: Path, tpl_dir: Path, only: str) -> dict:
    r = bc("emit", "print", "--region", "EU", "--template-dir", str(tpl_dir), "--only", only, project=p)
    assert r.returncode == 0, r.stdout + r.stderr
    c = bc("print-check", project=p)
    assert c.returncode == 1, c.stdout + c.stderr
    return results(p)


def test_text_inside_the_safe_zone_fails(proj, tmp_path):
    tpl = template_copy(tmp_path)
    mutate(tpl / "business-card-back.html", ".trim{display:flex;flex-direction:column;justify-content:space-between;padding:{{margin}}mm}",
           ".trim{display:flex;flex-direction:column;justify-content:space-between;padding:1mm}")
    res = reemit_and_check(proj, tpl, "business-card-back")
    row = res["business-card-back.rgb-proof:safe-zone"]
    assert row["status"] == "fail" and re.search(r"text 'Sample Person' is 0\.9\d mm from the left trim edge", row["detail"])     # 1 mm of padding, as laid out
    assert res["business-card-front.rgb-proof:safe-zone"]["status"] == "pass"       # the untouched pieces still pass
    assert [r for r in res.values() if r["status"] == "fail" and not r["id"].startswith("business-card-back")] == []


def test_a_missing_bleed_fails_in_the_boxes_the_geometry_and_the_raster(proj, tmp_path):
    tpl = template_copy(tmp_path)
    mutate(tpl / "business-card-back.html", ".ground{background:{{ink}};color:{{paper}}}",
           ".ground{background:{{ink}};color:{{paper}};left:{{bleed}}mm;top:{{bleed}}mm;width:{{trim_w}}mm;height:{{trim_h}}mm}")
    res = reemit_and_check(proj, tpl, "business-card-back")
    geo = res["business-card-back.rgb-proof:bleed:geometry"]
    assert geo["status"] == "fail" and "stops at 0 mm" in geo["detail"] and "must run to -3 mm" in geo["detail"]
    ring = res["business-card-back.rgb-proof:bleed:ring"]
    assert ring["status"] == "fail" and "artwork stops at the trim" in ring["detail"]


def test_a_pdf_without_a_bleed_box_fails_the_box_rows(proj, tmp_path):
    pdf = proj / "assets/print/letterhead.rgb-proof.pdf"
    out = tmp_path / "mut.pdf"
    r = subprocess.run([str(ROOT / "tests/tools/pdfmut.py"), "no-bleedbox", str(pdf), str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert out.read_bytes() != pdf.read_bytes() and pdfinfo_box(out)["BleedBox"] == pdfinfo_box(out)["TrimBox"] != pdfinfo_box(pdf)["BleedBox"]
    shutil.copy2(out, pdf)
    assert bc("print-check", "assets/print/letterhead.rgb-proof.pdf", project=proj).returncode == 1
    res = results(proj)
    assert res["letterhead.rgb-proof:bleed-box"]["status"] == "fail" and "BleedBox" in res["letterhead.rgb-proof:bleed-box"]["detail"]


def test_an_opacity_object_fails_in_the_dom_and_in_the_pdf(proj, tmp_path):
    tpl = template_copy(tmp_path)
    mutate(tpl / "letterhead.html", ".contact{font-size:8pt;line-height:1.45;text-align:right;color:{{muted}}}",
           ".contact{font-size:8pt;line-height:1.45;text-align:right;color:{{muted}};opacity:.5}")
    res = reemit_and_check(proj, tpl, "letterhead")
    row = res["letterhead.rgb-proof:transparency"]
    assert row["status"] == "fail" and "opacity 0.5" in row["detail"]
    assert "ca 0.5" in row["detail"]      # the PDF itself carries it too: found in the file's own graphics state, not only in the page measurement


def test_an_opacity_object_injected_into_the_pdf_alone_is_found(proj, tmp_path):
    pdf = proj / "assets/print/envelope.rgb-proof.pdf"
    out = tmp_path / "mut.pdf"
    r = subprocess.run([str(ROOT / "tests/tools/pdfmut.py"), "opacity", str(pdf), str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert b"/GSmut" in out.read_bytes() and b"/GSmut" not in pdf.read_bytes()
    shutil.copy2(out, pdf)
    assert bc("print-check", "assets/print/envelope.rgb-proof.pdf", project=proj).returncode == 1
    row = results(proj)["envelope.rgb-proof:transparency"]
    assert row["status"] == "fail" and "ca 0.5" in row["detail"]


def test_text_that_is_not_outlined_fails(proj, tmp_path):
    pdf = proj / "assets/print/envelope.rgb-proof.pdf"
    out = tmp_path / "mut.pdf"
    assert subprocess.run([str(ROOT / "tests/tools/pdfmut.py"), "font", str(pdf), str(out)], capture_output=True).returncode == 0
    assert fonts(out) != [] and fonts(pdf) == []
    shutil.copy2(out, pdf)
    assert bc("print-check", "assets/print/envelope.rgb-proof.pdf", project=proj).returncode == 1
    assert results(proj)["envelope.rgb-proof:fonts"]["status"] == "fail"


def test_small_reversed_text_and_a_tiny_logo_fail(proj, tmp_path):
    tpl = template_copy(tmp_path)
    mutate(tpl / "business-card-back.html", ".lines{margin-top:2.4mm;font-size:7.5pt;line-height:1.45}",
           ".lines{margin-top:2.4mm;font-size:5.5pt;line-height:1.45}")
    mutate(tpl / "business-card-back.html", ".logo{width:34%}", ".logo{width:12%}")
    res = reemit_and_check(proj, tpl, "business-card-back")
    stem = "business-card-back.rgb-proof"
    assert res[f"{stem}:reversed-text"]["status"] == "fail" and f"'{EMAIL}' is 5.5 pt" in res[f"{stem}:reversed-text"]["detail"]
    assert res[f"{stem}:logo-size"]["status"] == "fail" and re.search(r"'logo' is 2\.\d+ mm high", res[f"{stem}:logo-size"]["detail"])
    assert res[f"{stem}:text-size"]["status"] == "pass"          # 5.5 pt is above the 5 pt floor for text of any kind


def test_a_hairline_thinner_than_the_minimum_fails_and_a_border_is_never_thinner_than_a_pixel(proj, tmp_path):
    tpl = template_copy(tmp_path)
    mutate(tpl / "letterhead.html", "height:0.5pt;background:{{ink}}",
           "height:0.1pt;background:{{ink}}")
    res = reemit_and_check(proj, tpl, "letterhead")
    row = res["letterhead.rgb-proof:line-weight"]
    assert row["status"] == "fail" and re.search(r"rule '[^']*' is 0\.\d+ pt", row["detail"]) and float(re.search(r"is (0\.\d+) pt", row["detail"]).group(1)) < 0.25
    # Chromium never draws a border thinner than 1 CSS px: a 0.1 pt border measures 0.75 pt, which is what the file holds
    (tmp_path / "b").mkdir()
    tpl2 = template_copy(tmp_path / "b")
    mutate(tpl2 / "business-card-back.html", ".lines{margin-top:2.4mm;",
           ".lines{border-top:0.1pt solid {{paper}};margin-top:2.4mm;")
    assert bc("emit", "print", "--region", "EU", "--template-dir", str(tpl2), "--only", "business-card-back", project=proj).returncode == 0
    sc = json.loads((proj / "assets/print/business-card-back.print.json").read_text())
    border = [e for e in sc["geometry"]["elements"] if e["kind"] == "border"]
    assert border and border[0]["weight_pt"] == 0.75 and border[0]["reversed"] is True


def test_owner_thresholds_from_qa_print_json_replace_the_defaults(proj):
    (proj / "qa").mkdir(exist_ok=True)
    (proj / "qa/print.json").write_text('{"schema": 1, "min_reversed_text_pt": 8}')
    assert bc("print-check", project=proj).returncode == 1
    res = results(proj)
    assert res["business-card-back.rgb-proof:reversed-text"]["status"] == "fail" and "7.5 pt" in res["business-card-back.rgb-proof:reversed-text"]["detail"]
    assert report(proj, "print-check")["thresholds_source"] == "qa/print.json"
    (proj / "qa/print.json").write_text('{"schema": 1, "min_reversed": 8}')
    r = bc("print-check", project=proj)
    assert r.returncode == 2 and "unknown key 'min_reversed'" in r.stderr


def test_a_pdfx_claim_without_icc_fails_print_check(proj, tmp_path):
    pdf = proj / "assets/print/letterhead.rgb-proof.pdf"
    out = tmp_path / "mut.pdf"
    r = subprocess.run([str(ROOT / "tests/tools/pdfmut.py"), "claim-pdfx", str(pdf), str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert pdfinfo_box(out)["Subject"] == X4 and b"/OutputIntents" not in out.read_bytes() and b"GTS_PDFXVersion" in out.read_bytes()
    shutil.copy2(out, pdf)
    assert bc("print-check", "assets/print/letterhead.rgb-proof.pdf", project=proj).returncode == 1
    res = results(proj)
    assert res["letterhead.rgb-proof:label:claims"]["status"] == "fail" and "needs --icc" in res["letterhead.rgb-proof:label:claims"]["detail"]
    assert res["letterhead.rgb-proof:label:icc"]["status"] == "fail" and "no output intent" in res["letterhead.rgb-proof:label:icc"]["detail"]


def test_a_conformance_claim_in_the_label_fails(proj, tmp_path):
    pdf = proj / "assets/print/letterhead.rgb-proof.pdf"
    raw = pdf.read_bytes()
    old = RGB.encode()                                      # the replacement keeps the length, so every xref offset stays valid
    assert old in raw
    new = (b"RGB: print-ready!" + b" " * len(old))[:len(old)]
    assert len(new) == len(old) and new != old
    pdf.write_bytes(raw.replace(old, new))
    assert new in pdf.read_bytes()
    assert bc("print-check", "assets/print/letterhead.rgb-proof.pdf", project=proj).returncode == 1
    row = results(proj)["letterhead.rgb-proof:label:claims"]
    assert row["status"] == "fail" and "claim words in the metadata" in row["detail"]


# ---------------------------------------------------------------- with --icc: a PDF/X-4 candidate, never a conforming file

def test_with_icc_the_pdfs_are_cmyk_pdfx4_candidates_with_an_output_intent(proj):
    icc = gs_cmyk_profile()
    r = bc("emit", "print", "--region", "EU", "--icc", str(icc), project=proj)
    assert r.returncode == 0, r.stdout + r.stderr
    files = printed_files(proj)
    assert all(p.name == f"{n}.pdfx4-candidate.pdf" for n, p in files.items())
    assert not list((proj / "assets/print").glob("*.rgb-proof.pdf"))           # the RGB variants were retired (moved), not left beside them
    assert list(proj.glob("removed-2026-10-17*/assets/print/*.rgb-proof.pdf"))
    for piece, pdf in files.items():
        b = pdfinfo_box(pdf)
        assert b["Subject"] == X4 and fonts(pdf) == []
        mw, mh = size_pt(b["MediaBox"])
        assert abs(mw - ((85 if "card" in piece else {"letterhead": 210, "envelope": 220}[piece]) + 6) * PT_PER_MM) < 0.02
        raw = pdf.read_bytes()
        assert b"/OutputIntents" in raw and b"/GTS_PDFXVersion" in raw and b"/GTS_PDFX" in raw and b"/DeviceRGB" not in raw and b"/ObjStm" not in raw
        assert not re.search(rb"(?i)conform|compliant|certified", raw)
        assert determinism.lint_file(pdf) == []
    c = bc("print-check", "--icc", str(icc), project=proj)
    assert c.returncode == 0, c.stdout + c.stderr
    rows = results(proj)
    assert "profile embedded" in rows["letterhead.pdfx4-candidate:label:icc"]["detail"] and X4 in rows["letterhead.pdfx4-candidate:label:icc"]["detail"]
    assert "output intent profile N=[4]" in rows["letterhead.pdfx4-candidate:colour"]["detail"]
    # a second emit with the same profile writes nothing (the candidate is deterministic too)
    r = bc("emit", "print", "--region", "EU", "--icc", str(icc), project=proj)
    assert "0 written" in r.stdout, r.stdout


def test_print_check_icc_must_be_the_embedded_profile(proj, tmp_path):
    icc = gs_cmyk_profile()
    assert bc("emit", "print", "--region", "EU", "--icc", str(icc), "--only", "letterhead", project=proj).returncode == 0
    other = tmp_path / "other.icc"
    other.write_bytes(icc.read_bytes() + b"\0")
    assert bc("print-check", "assets/print/letterhead.pdfx4-candidate.pdf", "--icc", str(other), project=proj).returncode == 1
    assert "is not other.icc" in results(proj)["letterhead.pdfx4-candidate:label:icc"]["detail"]


def test_an_rgb_profile_is_refused_before_anything_is_written(proj, tmp_path):
    bad = tmp_path / "rgb.icc"
    head = bytearray(132)
    head[16:20], head[36:40] = b"RGB ", b"acsp"
    bad.write_bytes(bytes(head))
    before = {p: p.read_bytes() for p in (proj / "assets/print").glob("*.pdf")}
    r = bc("emit", "print", "--region", "EU", "--icc", str(bad), project=proj)
    assert r.returncode == 2 and "needs a CMYK output profile" in r.stderr
    assert {p: p.read_bytes() for p in (proj / "assets/print").glob("*.pdf")} == before


# ---------------------------------------------------------------- other regions, options and refusals

def test_us_pieces_use_inches_exactly(proj):
    r = bc("emit", "print", "--region", "US", "--only", "business-card-front,letterhead", project=proj)
    assert r.returncode == 0, r.stdout + r.stderr
    card = pdfinfo_box(proj / "assets/print/business-card-front.rgb-proof.pdf")
    assert [round(v, 1) for v in size_pt(card["TrimBox"])] == [252.0, 144.0]            # 3.5 in x 2 in at 72 pt
    assert [round(v, 1) for v in size_pt(card["MediaBox"])] == [270.0, 162.0]           # + 2 x 0.125 in (9 pt each side)
    paper = pdfinfo_box(proj / "assets/print/letterhead.rgb-proof.pdf")
    assert [round(v, 1) for v in size_pt(paper["TrimBox"])] == [612.0, 792.0]           # Letter, 8.5 x 11 in
    assert bc("print-check", "assets/print/business-card-front.rgb-proof.pdf", "assets/print/letterhead.rgb-proof.pdf", project=proj).returncode == 0


def test_the_bleed_is_overridable_and_the_report_states_it_is_the_printers(proj):
    r = bc("emit", "print", "--region", "EU", "--bleed", "5", "--only", "business-card-front", project=proj)
    assert r.returncode == 0, r.stdout
    b = pdfinfo_box(proj / "assets/print/business-card-front.rgb-proof.pdf")
    assert abs(size_pt(b["MediaBox"])[0] - 95 * PT_PER_MM) < 0.02          # 85 + 2 x 5 mm
    rep = report(proj, "emit-print")
    note = next(x for x in rep["results"] if x["id"] == "note:bleed")
    assert "printer-specific" in note["detail"] and "--bleed" in note["detail"] and rep["bleed_mm"] == 5.0
    assert bc("print-check", "assets/print/business-card-front.rgb-proof.pdf", project=proj).returncode == 0


def test_refusals_exit_2_with_a_fix(proj):
    r = bc("emit", "print", project=proj)                               # the Acme brief names no region
    assert r.returncode == 2 and "Pass --region" in r.stderr
    assert bc("emit", "print", "--region", "XX", project=proj).returncode == 2
    assert bc("emit", "print", "--region", "EU", "--only", "poster", project=proj).returncode == 2
    assert bc("emit", "print", "--region", "EU", "--tagline", "an invented claim", project=proj).returncode == 1
    assert bc("emit", "print", "--region", "EU", "--image-base-url", "http://plain.example", "--only", "email-signature", project=proj).returncode == 2
    bc("state", "--set", "tier=quick", project=proj)
    r = bc("emit", "print", "--region", "EU", project=proj)
    assert r.returncode == 2 and "tier" in r.stderr and "state --set tier=standard" in r.stderr
    bc("state", "--set", "tier=standard", project=proj)
    f = proj / "BRAND-STATE.md"
    mutate(f, "content_languages: en", "content_languages:")
    r = bc("emit", "print", "--region", "EU", project=proj)
    assert r.returncode == 2 and "content_languages" in r.stderr


def test_the_card_back_needs_contact_facts_and_invents_none(proj):
    (proj / "FACTS.md").write_text("# Acme: facts\n\n| fact | value | source | confirmed |\n|---|---|---|---|\n| status | the online shop is in development | owner | 2026-10-17 |\n")
    r = bc("emit", "print", "--region", "EU", "--only", "business-card-back", project=proj)
    assert r.returncode == 1 and "nothing to say" in r.stderr
    r = bc("emit", "print", "--region", "EU", "--only", "letterhead,envelope", project=proj)
    assert r.returncode == 0
    warns = [x["id"] for x in report(proj, "emit-print")["results"] if x["id"].startswith("note:fact ") and x["status"] == "warn"]
    assert "note:fact contact email" in warns and "note:fact contact phone" in warns
    text = (proj / "assets/print/_build/letterhead.html").read_text()
    assert EMAIL not in text and "Sample Person" not in text


def test_facts_text_appears_on_the_pieces_and_nothing_else(printed):
    back = re.sub(r"<!--.*?-->", "", (printed / "assets/print/_build/business-card-back.html").read_text(), flags=re.S)
    for v in ("Sample Person", "Founder", EMAIL, "+00 000 000 000", "https://example.com", "1 Example Street, Sampletown"):
        assert v in back
    assert "{{" not in back and "[[fill" not in back
    assert "data-print-id=\"logo\"" in back and "data-print-bleed" in back and "data-print-mark" in back
    assert "opacity" not in back and "box-shadow" not in back and "gradient" not in back


def test_a_brand_font_is_loaded_and_outlined(proj):
    fdir = proj / "assets" / "fonts"
    fdir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "tests/fixtures/fonts/TestFont-subset.ttf", fdir / "TestFont-subset.ttf")
    r = bc("emit", "print", "--region", "EU", "--font-file", "assets/fonts/TestFont-subset.ttf", "--font-family", "Brand Test", "--only", "letterhead", project=proj)
    assert r.returncode == 0, r.stdout + r.stderr
    html = (proj / "assets/print/_build/letterhead.html").read_text()
    assert '@font-face{font-family:\'Brand Test\';src:url("/assets/fonts/TestFont-subset.ttf")}' in html
    # the pieces use it as written: escaped quotes (&quot;) made the rule invalid and Chromium printed in Times. Single quotes keep it
    # valid in a double-quoted style="..." of a copied template too
    assert "font-family:'Brand Test',Arial,Helvetica,sans-serif;" in html and "&quot;" not in html and '"Brand Test"' not in html
    assert fonts(proj / "assets/print/letterhead.rgb-proof.pdf") == []
    rows = {x["id"]: x for x in report(proj, "emit-print")["results"]}
    assert rows["note:font"]["status"] == "info"
    assert bc("emit", "print", "--region", "EU", "--font-file", "assets/fonts/missing.ttf", project=proj).returncode == 2
    r = bc("emit", "print", "--region", "EU", "--font-file", "assets/fonts/TestFont-subset.ttf", "--font-family", 'Brand"}body{x', "--only", "letterhead", project=proj)
    assert r.returncode == 2 and "use letters, digits, spaces" in r.stderr
    # without --font-family the family comes from the file name; a variable font's axis tag is dropped instead of refusing a flag never passed
    shutil.copy2(ROOT / "tests/fixtures/fonts/TestFont-subset.ttf", fdir / "Inter[wght].ttf")
    r = bc("emit", "print", "--region", "EU", "--font-file", "assets/fonts/Inter[wght].ttf", "--only", "letterhead", project=proj)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "font-family:'Inter',Arial" in (proj / "assets/print/_build/letterhead.html").read_text()
    shutil.copy2(ROOT / "tests/fixtures/fonts/TestFont-subset.ttf", fdir / "[wght].ttf")
    r = bc("emit", "print", "--region", "EU", "--font-file", "assets/fonts/[wght].ttf", "--only", "letterhead", project=proj)
    assert r.returncode == 2 and "gives no usable family name: pass --font-family" in r.stderr


# ---------------------------------------------------------------- the e-mail signature

def lum(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def ratio(a, b):
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_the_signature_is_a_table_with_inline_styles_its_own_ground_and_absolute_image_urls(proj):
    html = (proj / "assets/print/email-signature/email-signature.html").read_text()
    body = html.split("<body", 1)[1]
    assert "<table" in body and "<style" not in html.lower() and "<script" not in html.lower() and "class=" not in html and "var(" not in html
    assert 'bgcolor="#f9f7ee"' in html and "background-color:#f9f7ee" in html                      # the Acme paper colour (color.bg #f9f7ee): its own ground
    img = re.search(r'<img src="([^"]+)" srcset="([^"]+)" width="(\d+)" height="(\d+)"', html)
    assert img.group(1).startswith("https://YOUR-HOST.invalid/brand/") and img.group(2).endswith("logo@2x.png 2x")
    assert (img.group(3), img.group(4)) == ("87", "24")               # 24 px high (the email-logo row) x the wordmark's 3.626:1 ratio = 87
    pair = ratio("#0d1b2d", "#f9f7ee")
    assert pair >= 4.5 and f"{pair:.2f}:1" in (proj / "assets/manifest.json").read_text()
    w1 = png_size((proj / "assets/print/email-signature/logo.png").read_bytes())
    w2 = png_size((proj / "assets/print/email-signature/logo@2x.png").read_bytes())
    assert w1 == (87, 24) and w2 == (174, 48)
    rows = {x["id"]: x for x in report(proj, "emit-print")["results"]}
    assert rows["note:signature images"]["status"] == "warn" and "placeholders" in rows["note:signature images"]["label"]


def test_the_signature_takes_the_image_base_url_and_links_only_facts(proj):
    r = bc("emit", "print", "--region", "EU", "--only", "email-signature", "--image-base-url", "https://img.example.com/brand/", project=proj)
    assert r.returncode == 0, r.stdout + r.stderr
    html = (proj / "assets/print/email-signature/email-signature.html").read_text()
    assert 'src="https://img.example.com/brand/logo.png"' in html and "YOUR-HOST" not in html
    assert f'href="mailto:{EMAIL}"' in html and 'href="tel:+00000000000"' in html and 'href="https://example.com"' in html
    assert "Sample Person" in html and "Founder" in html
    rows = {x["id"] for x in report(proj, "emit-print")["results"]}
    assert "note:signature images" not in rows


# ---------------------------------------------------------------- check wires print in only when print artefacts exist

def test_check_gates_print_only_when_print_pdfs_are_in_the_manifest(golden, tmp_path):
    p = tmp_path / "acme"
    shutil.copytree(golden, p)
    bc("check", project=p)
    assert not any(i.startswith("report:print") for i in results(p, "check"))               # no print artefacts, no print gate
    with_contacts(p)
    for k, v in (("tier", "standard"), ("content_languages", "en")):
        bc("state", "--set", f"{k}={v}", project=p)
    assert bc("emit", "print", "--region", "EU", "--only", "letterhead", project=p).returncode == 0
    bc("check", project=p)
    row = results(p, "check")["report:print-check"]
    assert row["status"] == "skipped" and "no print-check report" in row["detail"]
    assert bc("print-check", project=p).returncode == 0
    bc("check", project=p)
    assert results(p, "check")["report:print-check"]["status"] == "pass"
    mutate(p / "assets/print/_build/letterhead.html", "<title>", "<title>x ")      # an input of nothing: the check reads the PDF and the sidecar
    pdf = p / "assets/print/letterhead.rgb-proof.pdf"
    pdf.write_bytes(pdf.read_bytes() + b"\n%edited\n")
    bc("check", project=p)
    st = results(p, "check")
    assert st["report:print-check"]["status"] == "skipped" and "stale" in st["report:print-check"]["detail"]


# ---------------------------------------------------------------- the press kit

def zip_entries(p: Path):
    with zipfile.ZipFile(p) as z:
        return z.infolist(), {i.filename: z.read(i) for i in z.infolist()}


def test_the_press_kit_is_a_deterministic_zip_of_logos_tokens_and_the_book(proj):
    r = bc("emit", "presskit", project=proj)
    assert r.returncode == 1 and "book.pdf not found" in r.stderr                  # no silent kit without the book
    r = bc("emit", "presskit", "--no-book", project=proj)
    assert r.returncode == 0, r.stdout + r.stderr
    z = proj / "assets/presskit/acme-press-kit.zip"
    infos, files = zip_entries(z)
    names = [i.filename for i in infos]
    assert names == sorted(names) and all(i.date_time == (1980, 1, 1, 0, 0, 0) for i in infos)
    logos = sorted(f"acme-press-kit/logos/{p.name}" for p in (proj / "assets/logo").iterdir() if p.suffix in (".svg", ".png"))
    assert [n for n in names if "/logos/" in n] == logos and "acme-press-kit/logos/wordmark.svg" in names
    assert {"acme-press-kit/tokens/tokens.css", "acme-press-kit/tokens/tokens.json", "acme-press-kit/README.txt"} <= set(names)
    assert not any("book" in n for n in names)
    assert files["acme-press-kit/logos/mark.svg"] == (proj / "assets/logo/mark.svg").read_bytes()
    readme = files["acme-press-kit/README.txt"].decode()
    assert "states no terms of use" in readme and "book/" not in readme
    import hashlib
    assert f"{hashlib.sha256(files['acme-press-kit/tokens/tokens.json']).hexdigest()}" in readme
    before = z.read_bytes()
    r = bc("emit", "presskit", "--no-book", project=proj)
    assert "0 written" in r.stdout and z.read_bytes() == before and determinism.lint_file(z) == []
    row = next(a for a in json.loads((proj / "assets/manifest.json").read_text())["artefacts"] if a["path"].endswith("press-kit.zip"))
    assert row["emitter"] == "presskit" and row["slot"] == "press-kit"


def test_the_press_kit_carries_the_labelled_book_pdf_and_follows_the_inputs(proj):
    (proj / "book.pdf").write_bytes(b"%PDF-1.4\n/Subject (RGB, not print-ready)\n%%EOF\n")
    r = bc("emit", "presskit", project=proj)
    assert r.returncode == 0, r.stdout + r.stderr
    _, files = zip_entries(proj / "assets/presskit/acme-press-kit.zip")
    assert files["acme-press-kit/book/book.pdf"] == (proj / "book.pdf").read_bytes()
    assert "book.pdf is an RGB proof of the brand book, for reading. It is not a print file." in files["acme-press-kit/README.txt"].decode()
    row = next(x for x in report(proj, "emit-presskit")["results"] if x["id"] == "check:book label")
    assert row["status"] == "pass"
    z = proj / "assets/presskit/acme-press-kit.zip"
    before = z.read_bytes()
    mutate(proj / "assets/logo/mark.svg", "</svg>", "<!-- changed --></svg>")
    assert bc("emit", "presskit", project=proj).returncode == 0 and z.read_bytes() != before        # a changed logo changes the kit
    (proj / "book.pdf").write_bytes(b"%PDF-1.4\n%%EOF\n")
    assert bc("emit", "presskit", project=proj).returncode == 0
    assert next(x for x in report(proj, "emit-presskit")["results"] if x["id"] == "check:book label")["status"] == "warn"


# ---------------------------------------------------------------- social posts

def post_png(p: Path, name: str) -> tuple[int, int]:
    return png_size((p / "assets/social/posts" / name).read_bytes())


def social(p, *extra):
    return bc("emit", "social", "--posts", "--post-fact", "spare parts", "--post-fact", "repair guide", "--post-fact", "batch size", *extra, project=p)


def test_posts_are_rendered_at_the_spec_rows_from_facts_only(proj):
    r = social(proj)
    assert r.returncode == 0, r.stdout + r.stderr
    names = sorted(x.name for x in (proj / "assets/social/posts").glob("*.png"))
    assert names == [f"carousel-4x5-0{i}.png" for i in range(1, 6)] + ["educational-4x5.png", "post-1x1.png"]      # cover, 3 facts, closing; then the others
    for n in names:
        assert post_png(proj, n) == ((1080, 1080) if n == "post-1x1.png" else (1080, 1350)), n
    html = (proj / "assets/social/_build/posts/carousel-4x5-03.html").read_text()
    assert "a repair guide is in every box" in html and "repair guide" in html and "{{" not in html
    edu = (proj / "assets/social/_build/posts/educational-4x5.html").read_text()
    assert edu.count('<span class="n">') == 3 and "tools are made in batches of 200" in edu
    assert "data-regulated-checklist" not in re.sub(r"<!--.*?-->", "", html, flags=re.S)


def test_posts_need_facts_a_standard_tier_and_take_no_invented_label(proj):
    r = bc("emit", "social", "--posts", project=proj)
    assert r.returncode == 2 and "--post-fact" in r.stderr
    r = bc("emit", "social", "--posts", "--post-fact", "a claim nobody confirmed", project=proj)
    assert r.returncode == 1 and "not a label in FACTS.md" in r.stderr
    bc("state", "--set", "tier=quick", project=proj)
    r = social(proj)
    assert r.returncode == 2 and "tier" in r.stderr
    bc("state", "--set", "tier=standard", project=proj)
    r = bc("emit", "social", "--posts", *sum((["--post-fact", "spare parts"] for _ in range(5)), []), project=proj)
    assert r.returncode == 2 and "at most 4" in r.stderr


def test_a_regulated_profession_puts_the_checklist_on_the_posts(proj):
    f = proj / "brief/BRIEF.md"
    placeholder = next(ln for ln in f.read_text().splitlines() if ln.startswith("- Regulated profession:"))
    assert placeholder.startswith("- Regulated profession: (")
    r = social(proj)                                   # the line is still the template's placeholder: unanswered, said so, no checklist
    assert r.returncode == 0 and next(x for x in report(proj, "emit-social")["results"] if x["id"] == "note:regulated")["status"] == "warn"
    assert not (proj / "assets/social/posts/PRE-PUBLICATION.md").exists()
    mutate(f, placeholder, "- Regulated profession: dentistry, the dental chamber")
    r = social(proj)
    assert r.returncode == 0, r.stdout + r.stderr
    html = (proj / "assets/social/_build/posts/post-1x1.html").read_text()
    assert 'data-regulated-checklist="skills/brand-creator/references/regulated-industries.md#typical-guardrails"' in re.sub(r"<!--.*?-->", "", html, flags=re.S)
    assert 'data-regulated-profession="dentistry, the dental chamber"' in html
    chk = (proj / "assets/social/posts/PRE-PUBLICATION.md").read_text()
    assert "dentistry" in chk and chk.count("- [ ]") == 7 and "Typical guardrails" in chk and "nothing is posted until the owner has ticked every line" in chk
    assert "- educational-4x5.png:" in chk and "spare parts: every tool has a published spare-parts list" in chk
    rows = {x["id"]: x for x in report(proj, "emit-social")["results"]}
    assert rows["note:regulated"]["status"] == "warn" and "pre-publication checklist applies" in rows["note:regulated"]["label"]
    # answering "none" removes the checklist file again (the slot no longer exists: it is retired, not left behind)
    f.write_text(f.read_text().replace("dentistry, the dental chamber", "none"))
    assert social(proj).returncode == 0
    assert not (proj / "assets/social/posts/PRE-PUBLICATION.md").exists() and list(proj.glob("removed-*/assets/social/posts/PRE-PUBLICATION.md"))
    assert "data-regulated-checklist" not in re.sub(r"<!--.*?-->", "", (proj / "assets/social/_build/posts/post-1x1.html").read_text(), flags=re.S)


def test_posts_are_spared_by_a_plain_social_run_and_retired_when_a_slide_goes(proj):
    assert social(proj).returncode == 0
    before = {p.name: p.read_bytes() for p in (proj / "assets/social/posts").glob("*.png")}
    r = bc("emit", "social", project=proj)                                       # no --posts: the posts are not this run's business
    assert r.returncode == 0 and {p.name: p.read_bytes() for p in (proj / "assets/social/posts").glob("*.png")} == before
    assert not any(x["id"].startswith("retired:assets/social/posts") for x in report(proj, "emit-social")["results"])
    r = bc("emit", "social", "--posts", "--post-fact", "spare parts", project=proj)    # one fact: the carousel is three slides, two slides go
    assert r.returncode == 0
    left = sorted(p.name for p in (proj / "assets/social/posts").glob("carousel-*.png"))
    assert left == ["carousel-4x5-01.png", "carousel-4x5-02.png", "carousel-4x5-03.png"]
    assert len(list(proj.glob("removed-2026-10-17*/assets/social/posts/carousel-4x5-0[45].png"))) == 2


def test_social_posts_are_byte_stable_on_a_second_run(proj):
    assert social(proj).returncode == 0
    r = social(proj)
    assert r.returncode == 0 and "0 written" in r.stdout, r.stdout
