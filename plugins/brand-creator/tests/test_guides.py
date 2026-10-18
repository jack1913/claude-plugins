"""logo-sheet --guides: guide lines over the mark at 512 px, and the measured distance from each horizontal guide to the nearest
ink edge. Marks are outlined with the plugin's own tool, so the data-* metrics it writes are the guides."""
import pytest
from helpers import TEST_FONT, bc, failing, mutate, mutate_json, report

from pxio import read_png

pytestmark = [pytest.mark.requires_setup, pytest.mark.requires_resvg]


@pytest.fixture
def word(acme):
    r = bc("outline-glyphs", "--font", str(TEST_FONT), "--text", "Acme", "--axis", "wght=700", "--fill", "#0d1b2d",
           "--out", "assets/logo/word.svg", project=acme)
    assert r.returncode == 0, r.stderr
    return acme


def guides(proj, *extra, svg="assets/logo/word.svg"):
    bc("logo-sheet", "--guides", "--svg", svg, *extra, project=proj)
    return {r["id"]: r for r in report(proj, "logo-sheet")["results"] if r["id"].startswith(("guide", "guides"))}


def test_the_outlined_wordmarks_own_metrics_sit_on_the_ink_edges(word):
    g = guides(word)
    for k in ("baseline", "cap", "x-height"):
        assert g[f"guide:{k}"]["status"] == "pass", g[f"guide:{k}"]["detail"]
        assert abs(g[f"guide:{k}"]["offset_px"]) <= 1.5
    assert g["guides-image"]["status"] == "info"
    w, h, px = read_png((word / "assets/_checks/logo-guides.png").read_bytes())
    assert (w, h) == (512, 512)
    # the overlay draws the baseline in its own colour (#e0218a): the proof image must contain that colour
    assert any(tuple(px[i:i + 3]) == (0xe0, 0x21, 0x8a) for i in range(0, len(px), 4))
    assert report(word, "logo-sheet")["guides"]["tolerance_px"] == 1.5


def test_a_guide_that_misses_the_ink_fails_with_the_measured_offset(word):
    svg = (word / "assets/logo/word.svg").read_text()
    base = float(svg.split('data-baseline="')[1].split('"')[0])
    g = guides(word, "--baseline", str(base - 4))  # four units above the real baseline: the nearest edge is the baseline itself
    row = g["guide:baseline"]
    assert row["status"] == "fail" and row["offset_px"] > 3 and "off the guide" in row["detail"]
    # cap and x-height default to the baseline minus the font's heights, so they moved with it
    assert sorted(i for i in failing(report(word, "logo-sheet")) if i.startswith("guide")) == ["guide:baseline", "guide:cap", "guide:x-height"]
    g = guides(word, "--baseline", str(base - 4), "--cap-line", str(float(svg.split('data-baseline="')[1].split('"')[0]) - float(svg.split('data-cap-height="')[1].split('"')[0])))
    assert g["guide:cap"]["status"] == "pass" and g["guide:baseline"]["status"] == "fail"  # an explicit cap line stays where it was put


def test_the_tolerance_is_a_project_setting(word):
    mutate_json(word / "qa/rules.json", lambda d: d.setdefault("guides", {}).__setitem__("tolerance_px", 0.05))
    g = guides(word)
    assert any(r["status"] == "fail" for r in g.values() if r["id"].startswith("guide:") and r["id"] != "guide:grid")
    assert report(word, "logo-sheet")["guides"]["tolerance_px"] == 0.05


def test_a_grid_is_drawn_without_judging_anything(acme):
    g = guides(acme, "--grid", "8", svg="assets/logo/grid-mark.svg")
    assert g["guide:grid"]["status"] == "info" and "every 8 unit" in g["guide:grid"]["detail"]
    with_grid = (acme / "assets/_checks/logo-guides.png").read_bytes()
    guides(acme, "--baseline", "9", svg="assets/logo/grid-mark.svg")
    without = (acme / "assets/_checks/logo-guides.png").read_bytes()
    assert with_grid != without  # the grid lines are really in the picture
    wg, hg, pg = read_png(with_grid)
    _, _, pw = read_png(without)
    assert sum(1 for i in range(0, len(pg), 4) if pg[i:i + 3] != pw[i:i + 3]) > 500  # a 10-cell mark at step 8 draws two grid lines each way


def test_nothing_to_draw_is_an_error_not_a_pass(acme):
    r = bc("logo-sheet", "--guides", project=acme)
    assert r.returncode == 2 and "nothing to draw" in r.stderr


def test_the_dark_tile_uses_the_dark_twin_of_the_named_file_never_another_mark(word):
    """--svg wordmark must not borrow mark-dark.svg for the dark tile (the sheet would mix two marks)."""
    bc("logo-sheet", "--svg", "assets/logo/word.svg", project=word)
    assert "same file as light" in report(word, "logo-sheet")["dark_artwork"]
    (word / "assets/logo/word-dark.svg").write_text((word / "assets/logo/word.svg").read_text().replace("#0d1b2d", "#f0eee7"))
    bc("logo-sheet", "--svg", "assets/logo/word.svg", project=word)
    assert report(word, "logo-sheet")["dark_artwork"] == "separate file"
    assert any(i["path"] == "assets/logo/word-dark.svg" for i in report(word, "logo-sheet")["inputs"])
