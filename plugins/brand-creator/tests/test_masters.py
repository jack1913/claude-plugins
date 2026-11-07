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
