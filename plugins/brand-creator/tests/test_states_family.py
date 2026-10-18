"""states-check (state sets differ in greyscale and silhouette) and family-check (shared glyphs cell-equal, tile ratios agree).

Images are built with px_lib so every expectation follows from the geometry or from a colour luma worked out by hand."""
import json
import shutil
from pathlib import Path

import pytest
from helpers import ROOT, bc, failing, mutate_json, report

from px_lib import Img

macro = pytest.mark.requires_setup
pytestmark = pytest.mark.requires_resvg


def disc(path: Path, colour, *, ring: bool = False, n: int = 16) -> Path:
    im = Img(n, n)  # transparent ground
    c = (n - 1) / 2
    for y in range(n):
        for x in range(n):
            d = ((x - c) ** 2 + (y - c) ** 2) ** 0.5
            if d <= 6.2 and not (ring and d <= 3.5):
                im.set(x, y, colour)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(im.png())
    return path


def sets(proj, states: dict, **extra):
    (proj / "qa").mkdir(exist_ok=True)
    (proj / "qa/states.json").write_text(json.dumps({"schema": 1, "sets": [{"name": "s", "states": states, **extra}]}))


def res(proj, tool="states"):
    return {r["id"]: r for r in report(proj, tool)["results"]}


# ---------------------------------------------------------------- states-check

def test_the_acme_status_glyphs_differ_in_greyscale_and_silhouette(acme):
    r = bc("states-check", project=acme)
    assert r.returncode == 0, r.stdout
    rows = [x for x in report(acme, "states")["results"]]
    assert [x["id"] for x in rows] == ["states:status-16:idle|active", "states:status-16:idle|error", "states:status-16:active|error"]
    assert all(x["greyscale_diff"] >= 0.10 and x["silhouette_diff"] >= 0.10 and x["greyscale_min"] == 0.10 for x in rows)


def test_two_states_that_are_the_same_picture_fail(acme):
    mutate_json(acme / "qa/states.json", lambda d: d["sets"][0]["states"].__setitem__("dup", "assets/states/idle.png"))
    r = bc("states-check", project=acme)
    assert r.returncode == 1
    row = res(acme)["states:status-16:idle|dup"]
    assert row["status"] == "fail" and row["greyscale_diff"] == 0 and row["silhouette_diff"] == 0
    assert "read as the same state without colour" in row["detail"]
    assert failing(report(acme, "states")) == ["states:status-16:idle|dup"]


def test_colour_alone_does_not_tell_states_apart(acme):
    # orange (200,100,0) and green (0,159,0) have the same Rec. 709 luma: 0.2126*200+0.7152*100 = 114.04 and 0.7152*159 = 113.72
    disc(acme / "assets/s/a.png", (200, 100, 0))
    disc(acme / "assets/s/b.png", (0, 159, 0))
    sets(acme, {"a": "assets/s/a.png", "b": "assets/s/b.png"})
    r = bc("states-check", project=acme)
    assert r.returncode == 1
    row = res(acme)["states:s:a|b"]
    assert row["greyscale_diff"] == 0 and row["silhouette_diff"] == 0
    assert "greyscale 0.00 < 0.1" in row["detail"] and "silhouette 0.00 < 0.1" in row["detail"]


def test_a_different_shape_in_the_same_grey_passes_silhouette_but_fails_greyscale(acme):
    # ink luma 0.7152*179 = 128.0 equals the grey ground (128): the greyscale picture of disc and ring is the same
    disc(acme / "assets/s/disc.png", (0, 179, 0))
    disc(acme / "assets/s/ring.png", (0, 179, 0), ring=True)
    sets(acme, {"disc": "assets/s/disc.png", "ring": "assets/s/ring.png"})
    assert bc("states-check", project=acme).returncode == 1
    row = res(acme)["states:s:disc|ring"]
    assert row["silhouette_diff"] > 0.10 and row["greyscale_diff"] < 0.10
    assert "greyscale" in row["detail"] and "silhouette" not in row["detail"].split(":")[1]


def test_a_darker_disc_of_the_same_shape_passes_greyscale_but_fails_silhouette(acme):
    disc(acme / "assets/s/dark.png", (0, 0, 0))
    disc(acme / "assets/s/light.png", (255, 255, 255))
    sets(acme, {"dark": "assets/s/dark.png", "light": "assets/s/light.png"})
    assert bc("states-check", project=acme).returncode == 1
    row = res(acme)["states:s:dark|light"]
    assert row["greyscale_diff"] == 1.0 and row["silhouette_diff"] == 0  # same shape, opposite brightness
    assert row["status"] == "fail"


def test_thresholds_come_from_the_project_and_a_stricter_one_changes_the_verdict(acme):
    assert bc("states-check", project=acme).returncode == 0
    before = res(acme)["states:status-16:idle|active"]["silhouette_diff"]
    assert before < 0.99
    mutate_json(acme / "qa/rules.json", lambda d: d.setdefault("states", {}).__setitem__("silhouette_min_diff", 0.99))
    r = bc("states-check", project=acme)
    assert r.returncode == 1 and "silhouette 0.43 < 0.99" in res(acme)["states:status-16:idle|active"]["detail"]
    # a set may override the project rule
    mutate_json(acme / "qa/states.json", lambda d: d["sets"][0].__setitem__("silhouette_min_diff", 0.05))
    assert bc("states-check", project=acme).returncode == 0
    assert res(acme)["states:status-16:idle|active"]["silhouette_min"] == 0.05


def test_svg_states_are_rasterised_at_the_sets_size(acme):
    (acme / "assets/s").mkdir(parents=True)
    (acme / "assets/s/sq.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect x="1" y="1" width="8" height="8" fill="#101820"/></svg>')
    (acme / "assets/s/dot.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><circle cx="5" cy="5" r="2" fill="#101820"/></svg>')
    sets(acme, {"sq": "assets/s/sq.svg", "dot": "assets/s/dot.svg"})
    r = bc("states-check", project=acme)
    assert r.returncode == 2 and "give the set a `size`" in r.stderr
    sets(acme, {"sq": "assets/s/sq.svg", "dot": "assets/s/dot.svg"}, size=20)
    assert bc("states-check", project=acme).returncode == 0
    assert res(acme)["states:s:sq|dot"]["silhouette_diff"] > 0.5


def test_bad_state_sets_are_refused(acme, tmp_path):
    disc(acme / "assets/s/a.png", (0, 0, 0))
    disc(acme / "assets/s/big.png", (0, 0, 0), n=20)
    sets(acme, {"a": "assets/s/a.png", "big": "assets/s/big.png"})
    r = bc("states-check", project=acme)
    assert r.returncode == 2 and "differ in size" in r.stderr
    sets(acme, {"a": "assets/s/a.png"})
    assert "at least two states" in bc("states-check", project=acme).stderr
    sets(acme, {"a": "assets/s/a.png", "b": "assets/s/nope.png"})
    assert bc("states-check", project=acme).returncode == 2
    sets(acme, {"a": "assets/s/a.png", "b": "assets/s/a.png"}, colour="x")
    assert "unknown keys" in bc("states-check", project=acme).stderr
    sets(acme, {"a": "assets/s/a.png", "b": "../x.png"})
    assert "outside the project" in bc("states-check", project=acme).stderr
    (acme / "qa/states.json").unlink()
    assert bc("states-check", project=acme).returncode == 2


# ---------------------------------------------------------------- family-check

FAM_K = ["#...#", "#..#.", "###..", "#..#.", "#...#"]
FAM_E = [".###.", "#...#", "#####", "#....", ".####"]


def lit(name, glyphs, extra=""):
    return f"{extra}{name} = {json.dumps(glyphs)}\n"


@pytest.fixture
def fam(acme):
    """A family-member project: family glyphs in a sibling folder, this product's glyphs in tools/, FAMILY.md at the root."""
    assert bc("state", "--set", "architecture=family-member", project=acme).returncode == 0
    sib = acme.parent / "family"
    sib.mkdir()
    (sib / "letters.py").write_text(lit("LETTERS", {"K": FAM_K, "e": FAM_E}))
    (acme / "tools").mkdir(exist_ok=True)
    (acme / "tools/glyphs.py").write_text(lit("GLYPHS", {"K": FAM_K, "e": FAM_E, "x": ["#"]}))
    write_family(acme)
    return acme


def write_family(proj, *, shared=("K", "e"), compare="shape", tiles=None, tol=None, family_file="../family/letters.py", own_file="tools/glyphs.py"):
    block = {"schema": 1, "family": "Test family",
             "glyphs": {"family": {"file": family_file, "symbol": "LETTERS"}, "own": {"file": own_file, "symbol": "GLYPHS"},
                        "shared": list(shared), "compare": compare}}
    if tiles is not None:
        block["tiles"] = tiles
    if tol is not None:
        block["tile_share_tolerance"] = tol
    (proj / "FAMILY.md").write_text("# FAMILY: Test family\n\n```json family-check\n" + json.dumps(block, indent=2) + "\n```\n")


def test_a_standalone_brand_has_nothing_to_compare_and_says_so(acme):
    r = bc("family-check", project=acme)
    assert r.returncode == 0 and "architecture is standalone" in r.stdout
    assert [x["status"] for x in report(acme, "family")["results"]] == ["info"]


def test_shared_glyphs_that_are_cell_equal_pass(fam):
    r = bc("family-check", project=fam)
    assert r.returncode == 0, r.stdout
    assert [x["id"] for x in report(fam, "family")["results"] if x["status"] == "pass"] == ["glyph:K", "glyph:e"]


def test_one_changed_cell_fails_and_names_the_cell(fam):
    mutated = FAM_K[:1] + ["#..##"] + FAM_K[2:]  # row 1, column 4 now filled
    assert mutated != FAM_K
    (fam / "tools/glyphs.py").write_text(lit("GLYPHS", {"K": mutated, "e": FAM_E}))
    r = bc("family-check", project=fam)
    assert r.returncode == 1
    d = res(fam, "family")["glyph:K"]["detail"]
    assert d.startswith("K: 1 cell(s) differ, the first at row 1, column 4") and "never redraw" in d
    assert failing(report(fam, "family")) == ["glyph:K"]


def test_a_missing_or_resized_glyph_fails(fam):
    (fam / "tools/glyphs.py").write_text(lit("GLYPHS", {"K": FAM_K + ["#...#"]}))
    assert bc("family-check", project=fam).returncode == 1
    out = res(fam, "family")
    assert "size differs: 5x6 vs 5x5" in out["glyph:K"]["detail"] or "size differs" in out["glyph:K"]["detail"]
    assert "missing from this product's source" in out["glyph:e"]["detail"]


def test_shape_compare_ignores_the_characters_and_exact_compare_does_not(fam):
    other = [r.replace("#", "X").replace(".", "_") for r in FAM_K]  # the same cells, other characters
    (fam / "tools/glyphs.py").write_text(lit("GLYPHS", {"K": other, "e": FAM_E}))
    assert bc("family-check", project=fam).returncode == 0
    write_family(fam, compare="exact")
    r = bc("family-check", project=fam)
    assert r.returncode == 1 and failing(report(fam, "family")) == ["glyph:K"]


def test_sources_are_read_never_executed(fam, tmp_path):
    marker = tmp_path / "executed.txt"
    (fam.parent / "family/letters.py").write_text(lit("LETTERS", {"K": FAM_K, "e": FAM_E}, extra=f"open({str(marker)!r}, 'w').write('ran')\n"))
    assert bc("family-check", project=fam).returncode == 0
    assert not marker.exists()  # the module-level side effect never ran
    (fam.parent / "family/letters.py").write_text(f"import os\nLETTERS = dict(K={FAM_K!r}, e={FAM_E!r})\nopen({str(marker)!r}, 'w').write('ran')\n")
    r = bc("family-check", project=fam)
    assert r.returncode == 3 and "not a literal" in res(fam, "family")["glyphs:sources"]["detail"]  # not verified, and still nothing ran
    assert not marker.exists()


def test_a_sibling_checkout_that_is_missing_makes_the_check_not_verified(fam):
    (fam.parent / "family/letters.py").rename(fam.parent / "family/letters.moved")
    r = bc("family-check", project=fam)
    assert r.returncode == 3 and "NOT-VERIFIED" in r.stdout
    assert res(fam, "family")["glyphs:sources"]["status"] == "skipped"


def test_json_glyph_sources_work_too(fam):
    (fam.parent / "family/letters.json").write_text(json.dumps({"set": {"K": FAM_K, "e": FAM_E}}))
    block_file = fam / "FAMILY.md"
    write_family(fam, family_file="../family/letters.json")
    t = block_file.read_text().replace('"symbol": "LETTERS"', '"symbol": "set"')
    block_file.write_text(t)
    assert bc("family-check", project=fam).returncode == 0


def square_svg(path: Path, box: int, view: int = 100):
    path.parent.mkdir(parents=True, exist_ok=True)
    off = (view - box) // 2
    path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {view} {view}"><rect x="{off}" y="{off}" width="{box}" height="{box}" fill="#101820"/></svg>')
    return path


def test_tile_shares_are_measured_and_must_agree_across_products(fam):
    square_svg(fam / "assets/logo/a.svg", 50)
    square_svg(fam.parent / "family/b.svg", 50)
    write_family(fam, tiles=[{"product": "this", "mark": "assets/logo/a.svg"}, {"product": "sibling", "mark": "../family/b.svg"}])
    assert bc("family-check", project=fam).returncode == 0
    t = res(fam, "family")
    assert t["tile:this"]["share"] == 0.25 and t["tile:this"]["bbox_height"] == 0.5  # 50 x 50 of 100 x 100, worked out by hand
    assert t["tiles:share"]["status"] == "pass" and t["tiles:bbox_height"]["status"] == "pass"
    square_svg(fam.parent / "family/b.svg", 80)  # share 0.64, height 0.8
    r = bc("family-check", project=fam)
    assert r.returncode == 1
    assert failing(report(fam, "family")) == ["tiles:bbox_height", "tiles:share"] or set(failing(report(fam, "family"))) == {"tiles:share", "tiles:bbox_height"}
    assert abs(res(fam, "family")["tiles:share"]["spread"] - 0.39) < 0.01
    write_family(fam, tiles=[{"product": "this", "mark": "assets/logo/a.svg"}, {"product": "sibling", "mark": "../family/b.svg"}], tol=0.5)
    assert bc("family-check", project=fam).returncode == 0  # the family's own tolerance wins over the proposal


def test_a_missing_tile_mark_is_not_verified(fam):
    square_svg(fam / "assets/logo/a.svg", 50)
    write_family(fam, tiles=[{"product": "this", "mark": "assets/logo/a.svg"}, {"product": "sibling", "mark": "../family/gone.svg"}])
    r = bc("family-check", project=fam)
    assert r.returncode == 3 and res(fam, "family")["tile:sibling"]["status"] == "skipped"


def test_the_unfilled_template_is_refused_and_documents_the_format(fam):
    tpl = (ROOT / "templates/FAMILY.md").read_text()
    (fam / "FAMILY.md").write_text(tpl)
    r = bc("family-check", project=fam)
    assert r.returncode == 2 and "[[fill:" in r.stderr
    for field in ("glyphs.family", "glyphs.shared", "tiles", "tile_share_tolerance", "ast.literal_eval"):
        assert field in tpl, field  # the template documents every field the check reads
    (fam / "FAMILY.md").unlink()
    r = bc("family-check", project=fam)
    assert r.returncode == 2 and "no FAMILY.md" in r.stderr
