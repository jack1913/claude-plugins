"""Masters: the ads and decks of a brand (a masters round, masters.json, G4m, masters check and approve, the book block and the kit)."""
from __future__ import annotations

import json
from pathlib import Path

from helpers import bc, failing, make_project, report
import mastersdata

PNG = b"\x89PNG\r\n\x1a\n"
BOARD = ('<!doctype html><html><body data-round="{n}" data-board="masters"><main>'
         '<section data-section="my-call"><p data-field="recommendation">Kalendarz</p><p data-field="critique">Lista is busier</p></section>'
         '<section data-section="questions"><div data-section="question" data-n="1"><p>Which direction?</p>'
         '<span data-option="a" data-recommended="true">Kalendarz</span><span data-option="b">Lista</span></div></section>'
         '<section data-section="reply"><p>Answer 1a or 1b and one sentence.</p></section></main></body></html>\n')


def ad(w: int, h: int, body: str = "<h1>Hello</h1>") -> str:
    return (f'<!doctype html><html><head><meta name="masters-canvas" content="{w}x{h}"><style>html,body{{margin:0;width:{w}px;height:{h}px;overflow:hidden}}'
            f'</style></head><body><main>{body}</main></body></html>\n')


def masters_round(tmp_path: Path, n: int = 5, *, directions=("kalendarz", "lista"), manifest: dict | None = None, g4: bool = True) -> Path:
    p = make_project(tmp_path, tier="standard")
    if g4:
        assert bc("state", "--record", "G4", "rules approved", project=p).returncode == 0
    r = p / "rounds" / f"r{n}"
    r.mkdir(parents=True)
    (r / "board.html").write_text(BOARD.format(n=n))
    entries = []
    for d in directions:
        (r / "reklama").mkdir(exist_ok=True)
        (r / "reklama" / f"{d}-1080x1350.html").write_text(ad(1080, 1350))
        entries.append({"file": f"reklama/{d}-1080x1350.html", "kind": "ad", "canvas": [1080, 1350], "direction": d})
    doc = manifest if manifest is not None else {"entries": entries, "copy_rules": ["no amounts or names in ads"], "builder": "node build.mjs"}
    (r / "masters.json").write_text(json.dumps(doc))
    return p


def lint(p: Path, n: int = 5):
    return bc("board-lint", f"rounds/r{n}/board.html", project=p)


def rows(p: Path) -> dict:
    return {r["id"]: r for r in report(p, "board-lint")["results"]}


# ---------------------------------------------------------------- Task 5: the manifest, the board, G4m

def test_a_manifest_with_a_bad_kind_or_a_missing_canvas_lists_each_problem(tmp_path):
    f = tmp_path / "masters.json"
    f.write_text(json.dumps({"entries": [{"file": "a.html", "kind": "poster"}, {"file": "b.html", "kind": "ad"},
                                         {"file": "c.pdf", "kind": "deck-pdf", "canvas": [1, 1]}, {"kind": "slide", "canvas": [1920, 1080]}]}))
    m = mastersdata.load_manifest(f)
    assert len(m.problems) == 4
    assert any("a.html" in x and "poster" in x for x in m.problems)
    assert any("b.html" in x and "canvas" in x for x in m.problems)
    assert any("c.pdf" in x and "canvas" in x for x in m.problems)
    assert any("entry 4" in x and "file" in x for x in m.problems)


def test_a_sound_manifest_reads_its_entries_rules_and_builder(tmp_path):
    f = tmp_path / "masters.json"
    f.write_text(json.dumps({"entries": [{"file": "reklama/k-1080x1350.html", "kind": "ad", "canvas": [1080, 1350], "direction": "k", "note": "the master"}],
                             "copy_rules": ["no amounts"], "builder": "node build.mjs"}))
    m = mastersdata.load_manifest(f)
    assert m.problems == [] and m.copy_rules == ["no amounts"] and m.builder == "node build.mjs"
    assert m.entries == [mastersdata.Entry("reklama/k-1080x1350.html", "ad", (1080, 1350), "k", "the master")]


def test_a_manifest_that_is_not_json_is_one_problem(tmp_path):
    f = tmp_path / "masters.json"
    f.write_text("{not json")
    assert len(mastersdata.load_manifest(f).problems) == 1


def test_board_lint_passes_a_sound_masters_board(tmp_path):
    p = masters_round(tmp_path)
    r = lint(p)
    assert r.returncode == 0, r.stdout + r.stderr
    got = rows(p)
    for rid in ("masters:gate", "masters:manifest", "masters:files", "masters:canvas-size", "masters:directions"):
        assert got[rid]["status"] == "pass", (rid, got[rid])


def test_board_lint_fails_a_masters_board_whose_file_is_missing(tmp_path):
    p = masters_round(tmp_path)
    (p / "rounds" / "r5" / "reklama" / "lista-1080x1350.html").unlink()
    assert lint(p).returncode == 1
    assert "masters:files" in failing(report(p, "board-lint"))
    assert "reklama/lista-1080x1350.html" in rows(p)["masters:files"]["detail"]


def test_the_canvas_an_ad_declares_must_match_its_manifest_entry(tmp_path):
    p = masters_round(tmp_path)
    (p / "rounds" / "r5" / "reklama" / "lista-1080x1350.html").write_text(ad(1080, 1080))
    assert lint(p).returncode == 1
    assert "masters:canvas-size" in failing(report(p, "board-lint"))


def test_the_first_masters_board_needs_two_directions(tmp_path):
    p = masters_round(tmp_path, directions=("kalendarz",))
    assert lint(p).returncode == 1
    assert "masters:directions" in failing(report(p, "board-lint"))


def test_a_later_masters_board_may_refine_one_direction(tmp_path):
    p = masters_round(tmp_path, n=6, directions=("kalendarz",))
    (p / "rounds" / "r5").mkdir()
    (p / "rounds" / "r5" / "board.html").write_text(BOARD.format(n=5))
    assert lint(p, 6).returncode == 0, rows(p)
    assert rows(p)["masters:directions"]["status"] == "pass"


def test_a_masters_board_needs_g4(tmp_path):
    p = masters_round(tmp_path, g4=False)
    assert lint(p).returncode == 1
    assert "masters:gate" in failing(report(p, "board-lint"))


def test_g4m_is_a_gate_state_can_record(tmp_path):
    p = make_project(tmp_path, tier="standard")
    r = bc("state", "--record", "G4m", "Kalendarz and Lista; PowerPoint: renders", project=p)
    assert r.returncode == 0, r.stderr
    assert bc("state", "--require", "G4m", project=p).returncode == 0


def test_the_masters_board_template_filled_in_passes_board_lint(tmp_path):
    import re
    from helpers import ROOT
    p = masters_round(tmp_path)
    page = (ROOT / "templates" / "masters-board.html").read_text()
    page = page.replace("[[fill: N]]", "5").replace("[[fill: direction one]]", "kalendarz").replace("[[fill: file name]]", "kalendarz-1080x1350")
    page = re.sub(r"\[\[fill:[^\]]*\]\]", "x", page)
    (p / "rounds" / "r5" / "board.html").write_text(page)
    (p / "rounds" / "r5" / "png").mkdir()
    (p / "rounds" / "r5" / "png" / "kalendarz-1080x1350.png").write_bytes(PNG)
    r = lint(p)
    assert r.returncode == 0, failing(report(p, "board-lint"))


# ---------------------------------------------------------------- Task 6: masters check

import zipfile  # noqa: E402

import pytest  # noqa: E402


def check(p: Path, *args: str):
    return bc("masters", "check", *args, project=p)


def mrows(p: Path) -> dict:
    return {r["id"]: r for r in report(p, "masters")["results"]}


def round_with(tmp_path: Path, files: dict[str, str | bytes], entries: list[dict], *, n: int = 5) -> Path:
    p = masters_round(tmp_path, n=n, manifest={"entries": entries, "copy_rules": [], "builder": None})
    for rel, data in files.items():
        f = p / "rounds" / f"r{n}" / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(data.encode() if isinstance(data, str) else data)
    return p


def ad_entry(name: str, w: int = 600, h: int = 400, d: str = "k") -> dict:
    return {"file": f"reklama/{name}.html", "kind": "ad", "canvas": [w, h], "direction": d}


ABS = "position:absolute;font:60px/1 sans-serif;margin:0"


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_clean_ad_passes_and_its_png_is_written(tmp_path):
    p = round_with(tmp_path, {"reklama/a.html": ad(600, 400, f'<p style="{ABS};left:40px;top:40px">Hello</p>')}, [ad_entry("a")])
    r = check(p)
    assert r.returncode == 0, r.stdout + r.stderr
    assert mrows(p)["masters:canvas"]["status"] == "pass" and mrows(p)["masters:covered"]["status"] == "pass"
    png = p / "rounds" / "r5" / "png" / "a.png"
    assert png.read_bytes()[:8] == PNG


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_an_element_outside_the_canvas_fails_masters_canvas(tmp_path):
    body = f'<p style="{ABS};left:40px;top:40px">Hi</p><div id="panel" style="position:absolute;left:500px;top:40px;width:200px;height:50px;background:#000"></div>'
    p = round_with(tmp_path, {"reklama/a.html": ad(600, 400, body)}, [ad_entry("a")])
    assert check(p).returncode == 1
    assert mrows(p)["masters:canvas"]["status"] == "fail" and "#panel" in mrows(p)["masters:canvas"]["detail"]


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_number_running_into_another_fails_masters_covered_and_names_both(tmp_path):
    body = (f'<span id="amount" style="{ABS};left:20px;top:100px">13 205,20 zł</span>'
            f'<span id="three" style="{ABS};left:300px;top:100px">3</span>')
    p = round_with(tmp_path, {"reklama/a.html": ad(600, 400, body)}, [ad_entry("a")])
    assert check(p).returncode == 1
    d = mrows(p)["masters:covered"]
    assert d["status"] == "fail" and "#amount" in d["detail"] and "#three" in d["detail"]


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_an_unmarked_stamp_over_text_warns_naming_both_elements(tmp_path):
    body = (f'<p id="label" style="{ABS};left:40px;top:100px">rozliczony</p>'
            '<div id="stamp" style="position:absolute;left:60px;top:90px;width:120px;height:90px;background:#e33"></div>')
    p = round_with(tmp_path, {"reklama/a.html": ad(600, 400, body)}, [ad_entry("a")])
    assert check(p).returncode == 0
    d = mrows(p)["masters:covered"]
    assert d["status"] == "warn" and "#label" in d["detail"] and "#stamp" in d["detail"] and "data-masters-overlay" in d["detail"]


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_an_overlay_marked_on_purpose_passes_and_is_listed(tmp_path):
    body = (f'<p id="label" style="{ABS};left:40px;top:100px">rozliczony</p>'
            '<div id="stamp" data-masters-overlay style="position:absolute;left:60px;top:90px;width:120px;height:90px;background:#e33"></div>')
    p = round_with(tmp_path, {"reklama/a.html": ad(600, 400, body)}, [ad_entry("a")])
    assert check(p).returncode == 0
    assert mrows(p)["masters:covered"]["status"] == "pass"
    assert mrows(p)["masters:overlays"]["status"] == "info" and "#stamp" in mrows(p)["masters:overlays"]["detail"]


def pdf_bytes(pages: int, w: int = 1440, h: int = 810, date: str = "D:20261107120000Z") -> bytes:
    objs = ["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [" + " ".join(f"{3 + i} 0 R" for i in range(pages)) + f"] /Count {pages} >>"]
    objs += [f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {w} {h}] >>" for _ in range(pages)]
    objs.append(f"<< /Producer (t) /CreationDate ({date}) /ModDate ({date}) >>")
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += f"{i} 0 obj\n{o}\nendobj\n".encode()
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode() + b"".join(f"{o:010d} 00000 n \n".encode() for o in offs)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R /Info {len(objs)} 0 R /ID [<0123456789abcdef0123456789abcdef> <0123456789abcdef0123456789abcdef>] >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return out


def slides(k: int) -> list[dict]:
    return [{"file": f"slajdy/{i}.png", "kind": "image"} for i in range(k)] + [{"file": f"slajdy/s{i}.html", "kind": "slide", "canvas": [1920, 1080], "direction": "k"} for i in range(k)]


def deck(tmp_path: Path, pdf: bytes, k: int = 3) -> Path:
    files = {"prezentacja/deck.pdf": pdf, **{f"slajdy/s{i}.html": ad(1920, 1080, f'<p style="{ABS};left:40px;top:40px">S{i}</p>') for i in range(k)}}
    entries = [{"file": f"slajdy/s{i}.html", "kind": "slide", "canvas": [1920, 1080], "direction": "k"} for i in range(k)] + [{"file": "prezentacja/deck.pdf", "kind": "deck-pdf"}]
    return round_with(tmp_path, files, entries)


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_normalised_deck_pdf_with_one_page_per_slide_passes(tmp_path):
    import determinism
    p = deck(tmp_path, determinism.normalise_pdf(pdf_bytes(3)))
    assert check(p).returncode == 0, mrows(p)
    assert mrows(p)["masters:pdf"]["status"] == "pass"


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_deck_pdf_with_the_wrong_page_count_fails(tmp_path):
    import determinism
    p = deck(tmp_path, determinism.normalise_pdf(pdf_bytes(2)))
    assert check(p).returncode == 1
    assert "2 page" in mrows(p)["masters:pdf"]["detail"] and "3 slide" in mrows(p)["masters:pdf"]["detail"]


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_a_deck_pdf_with_its_own_dates_fails_and_names_pdf_normalise(tmp_path):
    p = deck(tmp_path, pdf_bytes(3))
    assert check(p).returncode == 1
    assert "pdf normalise" in mrows(p)["masters:pdf"]["detail"]


def pptx_bytes(*, shape=(0, 0, 9144000, 5143500), size=(12192000, 6858000), font="Geist", embedded=("Geist",)) -> bytes:
    import io
    x, y, cx, cy = shape
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        emb = "".join(f'<p:embeddedFont><p:font typeface="{t}"/><p:regular r:id="rIdF{i}"/></p:embeddedFont>' for i, t in enumerate(embedded))
        z.writestr("ppt/presentation.xml", '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
                   'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
                   f'<p:sldSz cx="{size[0]}" cy="{size[1]}"/>' + (f"<p:embeddedFontLst>{emb}</p:embeddedFontLst>" if embedded else "") + "</p:presentation>")
        z.writestr("ppt/slides/slide1.xml", '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
                   f'<p:cSld><p:spTree><p:sp><p:nvSpPr><p:cNvPr id="2" name="Title 1"/></p:nvSpPr><p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm></p:spPr>'
                   f'<p:txBody><a:p><a:r><a:rPr><a:latin typeface="{font}"/></a:rPr><a:t>Hi</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>')
    return buf.getvalue()


def pptx_round(tmp_path: Path, data: bytes) -> Path:
    return round_with(tmp_path, {"prezentacja/deck.pptx": data}, [{"file": "prezentacja/deck.pptx", "kind": "deck-pptx"}])


def test_a_sound_pptx_passes_its_structure_and_waits_for_powerpoint(tmp_path):
    p = pptx_round(tmp_path, pptx_bytes())
    r = check(p)
    assert r.returncode == 3, r.stdout + r.stderr                                     # not verified until the owner opened it in PowerPoint
    assert mrows(p)["masters:pptx"]["status"] == "pass"
    assert mrows(p)["masters:pptx-render"]["status"] == "skipped" and "PowerPoint" in mrows(p)["masters:pptx-render"]["detail"]


def test_pptx_render_is_verified_once_the_powerpoint_answer_is_recorded(tmp_path):
    p = pptx_round(tmp_path, pptx_bytes())
    assert bc("state", "--record", "G4m", "Kalendarz; PowerPoint: renders, fonts embedded", project=p).returncode == 0
    assert check(p).returncode == 0
    assert mrows(p)["masters:pptx-render"]["status"] == "pass"


def test_a_pptx_shape_outside_the_slide_fails(tmp_path):
    p = pptx_round(tmp_path, pptx_bytes(shape=(11000000, 0, 2000000, 1000000)))
    assert check(p).returncode == 1
    assert "Title 1" in mrows(p)["masters:pptx"]["detail"] and "outside" in mrows(p)["masters:pptx"]["detail"]


def test_a_pptx_font_that_is_not_embedded_fails(tmp_path):
    p = pptx_round(tmp_path, pptx_bytes(font="Grandstander", embedded=("Geist",)))
    assert check(p).returncode == 1
    assert "Grandstander" in mrows(p)["masters:pptx"]["detail"] and "embed-fonts" in mrows(p)["masters:pptx"]["detail"]


def test_a_pptx_that_is_no_zip_fails(tmp_path):
    p = pptx_round(tmp_path, b"not a zip")
    assert check(p).returncode == 1 and mrows(p)["masters:pptx"]["status"] == "fail"


def test_masters_check_without_a_masters_round_says_so(tmp_path):
    p = make_project(tmp_path, tier="standard")
    r = check(p)
    assert r.returncode == 2 and "masters board" in r.stderr


# ---------------------------------------------------------------- Task 7: pdf normalise, masters embed-fonts, pptxgenjs

FONT = Path(__file__).resolve().parent / "fixtures" / "fonts" / "TestFont-subset.ttf"


def test_pdf_normalise_makes_two_runs_byte_identical(tmp_path):
    import determinism
    f = tmp_path / "deck.pdf"
    raw = pdf_bytes(2)
    f.write_bytes(raw)
    r = bc("pdf", "normalise", str(f))
    assert r.returncode == 0, r.stderr
    once = f.read_bytes()
    assert once == determinism.normalise_pdf(raw) and once != raw
    assert bc("pdf", "normalise", str(f)).returncode == 0 and f.read_bytes() == once
    out = tmp_path / "copy.pdf"
    f.write_bytes(raw)
    assert bc("pdf", "normalise", str(f), "--out", str(out)).returncode == 0
    assert out.read_bytes() == once and f.read_bytes() == raw


def test_pdf_normalise_refuses_a_file_that_is_no_pdf(tmp_path):
    f = tmp_path / "x.pdf"
    f.write_bytes(b"hello")
    r = bc("pdf", "normalise", str(f))
    assert r.returncode == 2 and "not a PDF" in r.stderr


def full_pptx(typeface: str) -> bytes:
    import io
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="xml" ContentType="application/xml"/></Types>')
        z.writestr("ppt/_rels/presentation.xml.rels", '<?xml version="1.0"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide1.xml"/></Relationships>')
        z.writestr("ppt/presentation.xml", '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
                   'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><p:sldSz cx="12192000" cy="6858000"/>'
                   '<p:notesSz cx="6858000" cy="9144000"/></p:presentation>')
        z.writestr("ppt/slides/slide1.xml", '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
                   '<p:cSld><p:spTree><p:sp><p:nvSpPr><p:cNvPr id="2" name="Title 1"/></p:nvSpPr><p:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="100" cy="100"/></a:xfrm></p:spPr>'
                   f'<p:txBody><a:p><a:r><a:rPr><a:latin typeface="{typeface}"/></a:rPr><a:t>Hi</a:t></a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>')
    return buf.getvalue()


def test_embed_fonts_adds_the_font_and_masters_check_sees_it_embedded(tmp_path):
    import fontembed
    import pptxlib
    family, _ = fontembed.font_names(FONT.read_bytes())
    deck = tmp_path / "deck.pptx"
    deck.write_bytes(full_pptx(family))
    assert pptxlib.inspect(deck)["fonts_embedded"] == []
    r = bc("masters", "embed-fonts", str(deck), "--font", str(FONT))
    assert r.returncode == 0, r.stderr
    info = pptxlib.inspect(deck)
    assert info["fonts_embedded"] == [family] and family in info["fonts_named"]
    with zipfile.ZipFile(deck) as z:
        assert "ppt/fonts/font1.fntdata" in z.namelist()
        assert 'Extension="fntdata"' in z.read("[Content_Types].xml").decode()
        assert 'embedTrueTypeFonts="1"' in z.read("ppt/presentation.xml").decode()


def test_embed_fonts_writes_the_same_bytes_every_run(tmp_path):
    import fontembed
    family, _ = fontembed.font_names(FONT.read_bytes())
    a, b = tmp_path / "a.pptx", tmp_path / "b.pptx"
    for d in (a, b):
        d.write_bytes(full_pptx(family))
        assert bc("masters", "embed-fonts", str(d), "--font", str(FONT)).returncode == 0
    assert a.read_bytes() == b.read_bytes()


def test_embed_fonts_refuses_a_restricted_licence_font(tmp_path):
    import struct
    import fontembed
    data = bytearray(FONT.read_bytes())
    off = fontembed.table_offset(bytes(data), b"OS/2")
    struct.pack_into(">H", data, off + 8, 0x0002)
    bad = tmp_path / "Restricted.ttf"
    bad.write_bytes(bytes(data))
    deck = tmp_path / "deck.pptx"
    deck.write_bytes(full_pptx("Whatever"))
    before = deck.read_bytes()
    r = bc("masters", "embed-fonts", str(deck), "--font", str(bad))
    assert r.returncode == 1 and "Restricted.ttf" in r.stderr and "embedding" in r.stderr
    assert deck.read_bytes() == before


def test_embed_fonts_refuses_a_deck_that_has_embedded_fonts_already(tmp_path):
    import fontembed
    family, _ = fontembed.font_names(FONT.read_bytes())
    deck = tmp_path / "deck.pptx"
    deck.write_bytes(full_pptx(family))
    assert bc("masters", "embed-fonts", str(deck), "--font", str(FONT)).returncode == 0
    r = bc("masters", "embed-fonts", str(deck), "--font", str(FONT))
    assert r.returncode == 1 and "already" in r.stderr


def test_setup_installs_pptxgenjs():
    from helpers import ROOT
    pkg = json.loads((ROOT / "scripts" / "package.json").read_text())
    lock = json.loads((ROOT / "scripts" / "package-lock.json").read_text())
    v = pkg["dependencies"]["pptxgenjs"]
    assert v[0].isdigit(), "pinned exactly, as every dependency"
    assert lock["packages"]["node_modules/pptxgenjs"]["version"] == v


# ---------------------------------------------------------------- Task 8: masters approve

STYLED = ad(600, 400, '<p style="position:absolute;left:40px;top:40px;font:40px/1 sans-serif;margin:0">Hi</p>').replace(
    "</head>", '<link rel="stylesheet" href="../wspolne/styl.css"></head>')


def approvable(tmp_path: Path, *, ad_html: str = STYLED, record: bool = True) -> Path:
    files = {"reklama/k-600x400.html": ad_html, "reklama/l-600x400.html": ad_html, "wspolne/styl.css": "body { background: url('tlo.png') }",
             "wspolne/tlo.png": PNG, "build.mjs": "// builds the masters\n", "_lead/scratch.png": PNG}
    entries = [ad_entry("k-600x400", d="k"), ad_entry("l-600x400", d="l")]
    p = round_with(tmp_path, files, entries)
    m = json.loads((p / "rounds" / "r5" / "masters.json").read_text())
    m["copy_rules"], m["builder"] = ["no amounts or names in ads"], "node rounds/r5/build.mjs"
    (p / "rounds" / "r5" / "masters.json").write_text(json.dumps(m))
    if record:
        assert bc("state", "--record", "G4m", "k and l; PowerPoint: no deck", project=p).returncode == 0
    assert lint(p).returncode == 0, rows(p)
    assert check(p).returncode == 0, mrows(p)
    return p


def approve(p: Path, *args: str):
    return bc("masters", "approve", *args, project=p)


def test_approve_needs_g4m(tmp_path):
    p = masters_round(tmp_path)
    r = approve(p)
    assert r.returncode == 1 and "G4m" in r.stderr and "PowerPoint" in r.stderr
    assert not (p / "assets" / "masters").exists()


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_approve_needs_a_current_passing_masters_report(tmp_path):
    p = approvable(tmp_path)
    (p / "rounds" / "r5" / "reklama" / "k-600x400.html").write_text(STYLED.replace("Hi", "Hello"))
    r = approve(p)
    assert r.returncode == 1 and "masters check" in r.stderr and "stale" in r.stderr
    assert not (p / "assets" / "masters").exists()


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_approve_copies_the_masters_and_what_they_reach_and_writes_the_readme(tmp_path):
    p = approvable(tmp_path)
    r = approve(p)
    assert r.returncode == 0, r.stdout + r.stderr
    dest = p / "assets" / "masters"
    got = sorted(f.relative_to(dest).as_posix() for f in dest.rglob("*") if f.is_file())
    assert got == ["README.md", "masters.json", "png/k-600x400.png", "png/l-600x400.png", "reklama/k-600x400.html", "reklama/l-600x400.html",
                   "wspolne/styl.css", "wspolne/tlo.png"]
    assert (dest / "reklama" / "k-600x400.html").read_bytes() == (p / "rounds" / "r5" / "reklama" / "k-600x400.html").read_bytes()
    doc = json.loads((dest / "masters.json").read_text())
    assert doc["round"] == 5 and doc["approved"].endswith("k and l; PowerPoint: no deck") and len(doc["entries"]) == 2
    readme = (dest / "README.md").read_text()
    assert "reklama/k-600x400.html" in readme and "600 × 400" in readme and "no amounts or names in ads" in readme
    assert "node rounds/r5/build.mjs" in readme and "PowerPoint" in readme
    assert approve(p).returncode == 1                                                    # approved masters are there: --replace is needed


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_approve_refuses_a_master_that_reaches_outside_the_round(tmp_path):
    """A master is checked served from its round alone, so a file it loads from outside the round is missing there: masters check fails
    naming it, and approve copies nothing (closure.escapes refuses the same reference should a report ever pass)."""
    outside = STYLED.replace("</head>", '<link rel="stylesheet" href="../../../assets/fonts/fonts.css"></head>')
    p = round_with(tmp_path, {"reklama/k-600x400.html": outside, "reklama/l-600x400.html": STYLED, "wspolne/styl.css": "", "wspolne/tlo.png": PNG},
                   [ad_entry("k-600x400", d="k"), ad_entry("l-600x400", d="l")])
    (p / "assets" / "fonts").mkdir(parents=True)
    (p / "assets" / "fonts" / "fonts.css").write_text("")
    assert bc("state", "--record", "G4m", "k and l", project=p).returncode == 0
    assert lint(p).returncode == 0
    assert check(p).returncode == 1 and "/assets/fonts/fonts.css" in mrows(p)["masters:page-errors"]["detail"]
    r = approve(p)
    assert r.returncode == 1 and "masters check" in r.stderr
    assert not (p / "assets" / "masters").exists()


@pytest.mark.requires_setup
@pytest.mark.requires_node
def test_replaced_masters_go_to_removed(tmp_path):
    p = approvable(tmp_path)
    old = p / "assets" / "masters" / "stare" / "a.html"
    old.parent.mkdir(parents=True)
    old.write_text("old")
    assert approve(p).returncode == 1
    r = approve(p, "--replace")
    assert r.returncode == 0, r.stderr
    assert not (p / "assets" / "masters" / "stare").exists()
    assert (p / "removed-2026-10-17" / "assets-masters" / "stare" / "a.html").read_text() == "old"


# ---------------------------------------------------------------- Task 9: masters older than the site

def chk_rows(p: Path) -> dict:
    bc("check", project=p)
    return {r["id"]: r for r in report(p, "check")["results"]}


def test_masters_older_than_the_site_get_an_info_row(tmp_path):
    p = make_project(tmp_path, tier="standard")
    assert bc("state", "--record", "G4m", "kalendarz", project=p, env={"BRAND_CREATOR_TODAY": "2026-10-25"}).returncode == 0
    assert bc("state", "--record", "G4p", "start, pricing", project=p, env={"BRAND_CREATOR_TODAY": "2026-11-04"}).returncode == 0
    row = chk_rows(p)["masters:behind-site"]
    assert row["status"] == "info" and "approved before the site" in row["detail"] and "2026-10-25" in row["detail"] and "2026-11-04" in row["detail"]


def test_approved_masters_with_no_g4m_and_a_site_get_the_row_too(tmp_path):
    p = make_project(tmp_path, tier="standard")
    (p / "assets" / "masters").mkdir(parents=True)
    (p / "assets" / "masters" / "masters.json").write_text('{"entries": []}')
    assert bc("state", "--record", "G4p", "start", project=p).returncode == 0
    assert chk_rows(p)["masters:behind-site"]["status"] == "info"


def test_no_row_when_the_masters_are_newer_or_there_is_no_site(tmp_path):
    p = make_project(tmp_path, tier="standard")
    assert bc("state", "--record", "G4p", "start", project=p, env={"BRAND_CREATOR_TODAY": "2026-11-04"}).returncode == 0
    assert bc("state", "--record", "G4m", "kalendarz", project=p, env={"BRAND_CREATOR_TODAY": "2026-11-05"}).returncode == 0
    assert "masters:behind-site" not in chk_rows(p)
    q = make_project(tmp_path / "other", tier="standard")
    assert bc("state", "--record", "G4m", "kalendarz", project=q).returncode == 0
    assert "masters:behind-site" not in chk_rows(q)
