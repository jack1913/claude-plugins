"""logo-sheet, shot and card (the Chromium driver)."""
import json
import struct

import pytest
from helpers import bc, failing, mutate, mutate_json, report

from pxio import png_size

pytestmark = pytest.mark.requires_setup


# ---------------------------------------------------------------- logo sheet

@pytest.mark.requires_resvg
def test_logo_sheet_measures_every_size_on_both_grounds(acme):
    r = bc("logo-sheet", project=acme)
    assert r.returncode == 0, r.stdout
    rep = report(acme, "logo-sheet")
    ids = [x["id"] for x in rep["results"] if x["status"] == "pass"]
    assert ids == [f"{s}:{px}px" for s in ("light", "dark") for px in (16, 20, 32, 64, 128, 180)]
    assert rep["sizes"] == [16, 20, 32, 64, 128, 180]
    sheet = acme / rep["sheet"]
    w, h = png_size(sheet.read_bytes())
    assert (w, h) == (rep["results"][-1]["width"], rep["results"][-1]["height"]) and w > 1000
    assert all(x["label"] == "brand rule (logos WCAG-exempt)" for x in rep["results"] if x["id"][0] in "ld")
    assert rep["grounds"] == {"light": "#f9f7ee", "dark": "#0e141d"}  # taken from the built tokens


@pytest.mark.requires_resvg
def test_a_dark_tile_that_vanishes_fails(acme):
    """The dark mark artwork removed and the dark ground set to the mark's own colour: the mark vanishes."""
    (acme / "assets" / "logo" / "mark-dark.svg").rename(acme / "assets" / "logo" / "mark-dark.bak")
    r = bc("logo-sheet", "--ground-dark", "#0d1b2d", project=acme)
    assert r.returncode == 1, r.stdout
    bad = failing(report(acme, "logo-sheet"))
    assert bad and all(i.startswith("dark:") for i in bad)
    assert not any(i.startswith("light:") for i in bad)


@pytest.mark.requires_resvg
def test_logo_sheet_contrast_target_is_adjustable_and_enforced(acme):
    assert bc("logo-sheet", "--min-contrast", "3", project=acme).returncode == 0
    row = {r["id"]: r for r in report(acme, "logo-sheet")["results"]}["light:64px"]   # the fine vector, past the small band
    navy = row["min_ratio"]                                                          # the triangle is what touches the ground
    assert [c["hex"] for c in row["colours"]] == ["#0d1b2d"] and navy > 10
    r = bc("logo-sheet", "--min-contrast", f"{navy + 0.5:.2f}", project=acme)
    assert r.returncode == 1 and "light:64px" in failing(report(acme, "logo-sheet"))
    assert bc("logo-sheet", "--min-contrast", f"{navy - 0.5:.2f}", project=acme).returncode == 0


LIGHT = "#ffffff"


def _mark(proj, name, body):
    (proj / "assets" / "logo" / name).write_text(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">{body}</svg>')
    return f"assets/logo/{name}"


@pytest.mark.requires_resvg
def test_only_colours_that_touch_the_ground_are_held_to_it(acme):
    """A cream face inside a black outline is 1.15:1 against white but never meets the ground, so it passes; the same cream
    with no outline touches the ground and fails. (The old rule held every colour with 5 % of the ink to the ground.)"""
    framed = _mark(acme, "framed.svg", '<rect x="2" y="2" width="28" height="28" fill="#121212"/><rect x="6" y="6" width="20" height="20" fill="#f2efe6"/>')
    bare = _mark(acme, "bare.svg", '<rect x="2" y="2" width="28" height="28" fill="#121212"/><rect x="6" y="6" width="26" height="20" fill="#f2efe6"/>')
    bc("logo-sheet", "--svg", framed, "--ground-light", LIGHT, project=acme)   # no dark twin: the black frame fails on the dark ground
    rep = report(acme, "logo-sheet")
    assert not [i for i in failing(rep) if i.startswith("light:")], failing(rep)
    rows = {r["id"]: r for r in rep["results"]}
    assert [c["hex"] for c in rows["light:64px"]["colours"]] == ["#121212"]
    r = bc("logo-sheet", "--svg", bare, "--ground-light", LIGHT, project=acme)
    assert r.returncode == 1 and "light:64px" in failing(report(acme, "logo-sheet"))
    worst = {r["id"]: r for r in report(acme, "logo-sheet")["results"]}["light:64px"]
    assert "#f2efe6 touches the light ground" in worst["detail"] and worst["min_ratio"] == 1.15


@pytest.mark.requires_resvg
def test_a_keyline_thinner_than_a_pixel_fails_where_it_blends_into_the_ground(acme):
    """A 0.4-unit black keyline around a cream face (32 viewBox): at 512 px the black meets the ground at 18.73:1, but at 16 px the
    keyline covers a fifth of a pixel, so the tile's edge reaches far less and fails there; at 180 px it is solid and passes."""
    key = _mark(acme, "key.svg", '<rect x="1" y="1" width="30" height="30" fill="#121212"/>'
                                 '<rect x="1.4" y="1.4" width="29.2" height="29.2" fill="#f2efe6"/>')
    bc("logo-sheet", "--svg", key, "--ground-light", LIGHT, project=acme)
    rows = {r["id"]: r for r in report(acme, "logo-sheet")["results"]}
    assert rows["light:16px"]["status"] == "fail" and "edge reaches only" in rows["light:16px"]["detail"]
    assert rows["light:16px"]["edge_ratio"] < 3 and rows["light:16px"]["min_ratio"] > 10   # the colour alone would pass
    assert rows["light:180px"]["status"] == "pass" and rows["light:180px"]["edge_ratio"] > 10


@pytest.mark.requires_resvg
@pytest.mark.parametrize("stroke, colour", [("0.3", "#e5e2d6"), ("0.08", "#121212")])
def test_line_art_never_passes_unmeasured(acme, stroke, colour):
    """Line art: a pale 0.3 stroke (1.21:1 against white) and a 0.08 stroke with no flat colour at 512 px. Each tile either fails, on
    its visibility or its measured edge, or says NOT verified; none passes, as the old rule did ("lowest contrast None:1")."""
    (acme / "assets" / "logo" / "hair.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
                                                      f'<circle cx="32" cy="32" r="20" fill="none" stroke="{colour}" stroke-width="{stroke}"/></svg>')
    bc("logo-sheet", "--svg", "assets/logo/hair.svg", "--ground-light", LIGHT, project=acme)
    rows = {r["id"]: r for r in report(acme, "logo-sheet")["results"] if r["id"].startswith("light:") and r["id"].endswith("px")}
    assert rows and not [i for i, r in rows.items() if r["status"] == "pass"], rows
    for r in rows.values():
        assert (r["status"] == "fail") or (r["status"] == "skipped" and "NOT verified" in r["detail"]), r
    if colour == "#e5e2d6":
        assert rows["light:180px"]["status"] == "fail"             # under a pixel wide even at 180 px: never fully opaque


@pytest.mark.requires_resvg
def test_the_target_comes_from_the_tokens_and_a_ground_exception_excuses_a_colour(acme):
    """No --min-contrast: the target is touching.ground of the built tokens, as for `contrast` and board-lint. A colour that
    tokens/exceptions.json excuses against the ground is a warning that carries the reason, not a failure."""
    assert bc("logo-sheet", project=acme).returncode == 0
    assert report(acme, "logo-sheet")["target"] == {"min": 3.0, "from": "touching.ground in the tokens"}
    mutate_json(acme / "assets" / "tokens" / "tokens.json", lambda d: d["touching"].__setitem__("ground", 30.0))
    assert bc("logo-sheet", project=acme).returncode == 1                      # nothing reaches 30:1
    bare = _mark(acme, "bare.svg", '<rect x="2" y="2" width="28" height="28" fill="#121212"/><rect x="6" y="6" width="26" height="20" fill="#f2efe6"/>')
    why = "the cream band runs off on purpose"
    mutate_json(acme / "tokens" / "exceptions.json", lambda d: d["exceptions"].append({"a": "#f2efe6", "b": "ground", "mode": "light", "reason": why}))
    bc("logo-sheet", "--svg", bare, "--ground-light", LIGHT, "--min-contrast", "3", project=acme)
    row = {r["id"]: r for r in report(acme, "logo-sheet")["results"]}["light:64px"]
    assert row["status"] == "warn" and why in row["detail"] and "excused by tokens/exceptions.json" in row["detail"]


@pytest.mark.requires_resvg
def test_a_band_error_is_recorded_and_a_rules_change_makes_the_report_stale(acme):
    """The rules and the tokens are inputs of the report, so `check` sees a changed band as a stale sheet; and a run that stops on a
    band error writes a failing report instead of leaving the last passing one standing."""
    assert bc("logo-sheet", project=acme).returncode == 0
    mutate_json(acme / "qa" / "rules.json", lambda d: d["bands"][0].__setitem__("note", "a new note"))
    out = bc("check", project=acme).stdout
    assert any("report:logo-sheet" in ln and "qa/rules.json changed" in ln for ln in out.splitlines()), out[-2000:]
    mutate_json(acme / "qa" / "rules.json", lambda d: d["bands"][0].__setitem__("drawing", "assets/logo/missing.svg"))
    assert bc("logo-sheet", project=acme).returncode == 2
    rep = report(acme, "logo-sheet")
    assert rep["status"] == "fail" and "error" in {r["id"] for r in rep["results"]}


@pytest.mark.requires_resvg
def test_a_large_crisp_vector_is_not_taken_for_a_pixel_grid(acme):
    (acme / "assets" / "logo" / "crisp.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" shape-rendering="crispEdges">'
                                                       '<rect x="10" y="10" width="80" height="80" fill="#0d1b2d"/></svg>')
    bc("logo-sheet", "--svg", "assets/logo/crisp.svg", project=acme)
    rows = {r["id"]: r for r in report(acme, "logo-sheet")["results"]}
    assert rows["light:128px"]["placement"]["grid"] is None and not [i for i in rows if i.endswith(":scale")]


@pytest.mark.requires_resvg
def test_a_gradient_mark_is_not_verified_instead_of_passed(acme):
    grad = _mark(acme, "grad.svg", '<defs><linearGradient id="g"><stop offset="0" stop-color="#0d1b2d"/><stop offset="1" stop-color="#007d71"/>'
                                   '</linearGradient></defs><rect x="2" y="2" width="28" height="28" fill="url(#g)"/>')
    bc("logo-sheet", "--svg", grad, project=acme)
    rows = {r["id"]: r for r in report(acme, "logo-sheet")["results"]}
    assert rows["light:64px"]["status"] == "skipped" and "NOT verified" in rows["light:64px"]["detail"]


@pytest.mark.requires_resvg
def test_tiles_follow_the_size_bands_at_whole_number_scales(acme):
    """Acme's bands: the 10 px grid mark up to 32 px, the fine vector above. A pixel drawing is drawn at the largest whole-number
    scale that fits its tile and centred on whole pixels: 10 px at 16 (offset 3), 20 at 20, 30 at 32."""
    assert bc("logo-sheet", project=acme).returncode == 0
    rep = report(acme, "logo-sheet")
    assert rep["bands"]["applied"] is True
    assert {s: f for s, f in rep["bands"]["tiles"].items()} == {"16": "assets/logo/grid-mark.svg", "20": "assets/logo/grid-mark.svg",
                                                                "32": "assets/logo/grid-mark.svg", "64": "assets/logo/mark.svg",
                                                                "128": "assets/logo/mark.svg", "180": "assets/logo/mark.svg"}
    rows = {r["id"]: r for r in rep["results"]}
    assert rows["light:16px"]["placement"] == {"grid": 10, "scale": 1, "offset": 3} and rows["light:16px"]["bbox"][0] >= 3
    assert rows["light:20px"]["placement"] == {"grid": 10, "scale": 2, "offset": 0}
    assert rows["dark:32px"]["placement"] == {"grid": 10, "scale": 3, "offset": 1} and rows["dark:32px"]["drawing"] == "assets/logo/grid-mark.svg"
    assert rows["light:64px"]["placement"]["grid"] is None                         # the vector is fitted, not stepped
    # a mark that is none of the bands' drawings is drawn at every size, and the report says so
    assert bc("logo-sheet", "--svg", "assets/logo/wordmark.svg", project=acme).returncode in (0, 1)
    rep = report(acme, "logo-sheet")
    assert rep["bands"]["applied"] is False and {r["id"] for r in rep["results"]} >= {"bands"}


@pytest.mark.requires_resvg
def test_a_pixel_grid_larger_than_its_tile_is_flagged(acme):
    mutate_json(acme / "qa" / "rules.json", lambda d: d["bands"][0].__setitem__("drawing", "assets/logo/big-grid.svg"))
    (acme / "assets" / "logo" / "big-grid.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" shape-rendering="crispEdges"><path d="M2 2h20v20h-20z" fill="#0d1b2d"/></svg>')
    bc("logo-sheet", project=acme)
    rows = {r["id"]: r for r in report(acme, "logo-sheet")["results"]}
    assert rows["light:16px:scale"]["status"] == "warn" and "larger than the 16 px tile" in rows["light:16px:scale"]["detail"]
    assert rows["light:20px:scale"]["status"] == "warn" and "light:32px:scale" not in rows    # 24 fits 32 once
    assert rows["light:32px"]["placement"] == {"grid": 24, "scale": 1, "offset": 4}


@pytest.mark.requires_resvg
def test_logo_sheet_refuses_marks_with_text_and_guides_without_anything_to_draw(acme):
    svg = acme / "assets" / "logo" / "mark.svg"
    mutate(svg, "<circle", '<text x="1" y="1">A</text><circle')
    r = bc("logo-sheet", project=acme)
    assert r.returncode == 1 and "mark_lint" in r.stderr
    (acme / "assets" / "logo" / "mark.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><path d="M0 0h10v10H0z" fill="#0d1b2d"/></svg>')
    r = bc("logo-sheet", "--guides", project=acme)  # a clean mark with no baseline, cap line or grid to draw
    assert r.returncode == 2 and "nothing to draw" in r.stderr


def test_pillow_renderer_cannot_rasterise_svg(acme):
    r = bc("logo-sheet", "--renderer", "pillow", project=acme)
    assert r.returncode == 3 and "cannot rasterise SVG" in r.stderr


def test_missing_resvg_is_exit_3_with_the_install_command(acme, tmp_path):
    bare = tmp_path / "bare"
    bare.mkdir()
    for tool in ("uv", "node", "python3", "bash", "env", "dirname", "readlink", "mkdir", "cat"):
        from shutil import which
        found = which(tool)
        if found and not (bare / tool).exists():
            (bare / tool).symlink_to(found)
    r = bc("logo-sheet", project=acme, env={"PATH": str(bare)})
    assert r.returncode == 3 and "resvg" in (r.stderr + r.stdout)


# ---------------------------------------------------------------- shots

def page(acme, name, body, head=""):
    f = acme / "rounds" / "r1" / name
    f.write_text(f"<!doctype html><html lang=en><head><meta charset=utf-8><title>t</title>{head}</head><body>{body}</body></html>")
    return f.relative_to(acme).as_posix()


def test_shot_reports_four_views_with_measurements(acme):
    r = bc("shot", "rounds/r1/board.html", project=acme)
    assert r.returncode == 0, r.stdout
    rep = report(acme, "shot")
    assert [x["id"] for x in rep["results"]] == ["view:1440-light", "view:1440-dark", "view:390-light", "view:390-dark"]
    v = rep["results"][0]
    for key in ("height", "overflow", "console_errors", "non_local_requests", "broken_images", "fonts", "scripts", "forbidden_counts", "slices"):
        assert key in v
    assert v["slices"] and all(png_size(open(s, "rb").read())[0] == 2880 for s in rep["results"][0]["slices"])  # dsf 2
    assert png_size(open(rep["results"][2]["slices"][0], "rb").read())[0] == 780
    assert rep["out_dir"].startswith(str(acme.parent)) is False  # shots are written outside the project


def test_shot_slices_stay_under_the_texture_limit(acme):
    page(acme, "tall.html", '<div style="height:20000px;background:linear-gradient(#fff,#000)"></div>')
    r = bc("shot", "rounds/r1/tall.html", project=acme)
    assert r.returncode == 0, r.stdout
    for view in report(acme, "shot")["results"]:
        assert len(view["slices"]) >= 10
        for s in view["slices"]:
            assert png_size(open(s, "rb").read())[1] < 16384
    assert bc("shot", "rounds/r1/tall.html", "--slice", "9000", project=acme).returncode == 2


def test_shot_fails_on_horizontal_overflow(acme):
    rel = page(acme, "wide.html", '<div style="width:2000px;height:20px;background:#000">wide</div>')
    r = bc("shot", rel, project=acme)
    assert r.returncode == 1
    bad = report(acme, "shot")["results"]
    assert all(x["status"] == "fail" and x["overflow"] for x in bad)
    assert "horizontal overflow" in r.stdout


def test_shot_ignores_overflow_inside_a_scrolling_container(acme):
    rel = page(acme, "scroller.html", '<div style="overflow-x:auto;width:300px"><div style="width:2000px;height:20px;background:#000">wide</div></div>')
    assert bc("shot", rel, project=acme).returncode == 0


def test_shot_fails_on_console_errors_and_page_errors(acme):
    rel = page(acme, "err.html", "<p>x</p><script>console.error('boom'); throw new Error('bang')</script>")
    r = bc("shot", rel, project=acme)
    assert r.returncode == 1
    v = report(acme, "shot")["results"][0]
    assert any("boom" in e for e in v["console_errors"]) and any("bang" in e for e in v["console_errors"])
    assert v["scripts"]["total"] == 1


def test_shot_blocks_and_reports_non_local_requests(acme):
    rel = page(acme, "net.html", '<img src="https://example.invalid/x.png" width=10 height=10><link rel=stylesheet href="https://example.invalid/a.css">')
    r = bc("shot", rel, project=acme)
    assert r.returncode == 1
    v = report(acme, "shot")["results"][0]
    assert len(v["non_local_requests"]) == 2 and any("example.invalid/x.png" in u for u in v["non_local_requests"])


def test_shot_reports_broken_and_missing_local_images(acme):
    rel = page(acme, "img.html", '<img src="missing.png" width=10 height=10>')
    r = bc("shot", rel, project=acme)
    assert r.returncode == 1
    v = report(acme, "shot")["results"][0]
    assert v["broken_images"] == ["missing.png"] and any("404" in x for x in v["failed_local_requests"])


def test_shot_accepts_svg_images_without_intrinsic_size(acme):
    rel = page(acme, "svgimg.html", '<img src="../../assets/logo/mark.svg" width=32 height=32><img src="../../assets/logo/mark-dark.svg">')
    r = bc("shot", rel, project=acme)
    assert r.returncode == 0, r.stdout
    assert report(acme, "shot")["results"][0]["broken_images"] == []


def test_shot_counts_forbidden_strings_from_the_project_list(acme):
    brief = acme / "brief" / "BRIEF.md"
    mutate(brief, "## Forbidden\n", "## Forbidden\n\n- synergy\n- `world-class`\n")
    rel = page(acme, "words.html", "<p>Real SYNERGY and more synergy, world-class stuff.</p>")
    r = bc("shot", rel, project=acme)
    assert r.returncode == 1
    v = report(acme, "shot")["results"][0]
    assert v["forbidden_counts"] == {"synergy": 2, "world-class": 1}
    assert report(acme, "shot")["forbidden_terms"] == ["synergy", "world-class"]
    ok = page(acme, "clean.html", "<p>Plain words.</p>")
    assert bc("shot", ok, project=acme).returncode == 0
    ff = acme.parent / "forbidden.txt"
    ff.write_text("plain\n")
    assert bc("shot", ok, "--forbidden-file", str(ff), project=acme).returncode == 1  # an explicit list overrides the project one


def test_shot_dark_scheme_is_really_emulated(acme):
    rel = page(acme, "scheme.html", "<p>x</p>", head="<style>body{background:#fff}@media (prefers-color-scheme:dark){body{background:#000}}</style>")
    r = bc("shot", rel, project=acme)
    assert r.returncode == 0
    rep = report(acme, "shot")
    from pxio import read_png
    light = read_png(open(rep["results"][0]["slices"][0], "rb").read())
    dark = read_png(open(rep["results"][1]["slices"][0], "rb").read())
    assert light[2][:3] == b"\xff\xff\xff" and dark[2][:3] == b"\x00\x00\x00"


def test_shot_motion_needs_a_proof_file_not_a_page(acme):
    r = bc("shot", "rounds/r1/board.html", "--motion", project=acme)
    assert r.returncode == 2, r.stderr
    r = bc("shot", "--motion", "motion/missing.json", project=acme)
    assert r.returncode == 2 and "not found" in r.stderr


def test_shot_out_must_be_outside_the_project(acme):
    r = bc("shot", "rounds/r1/board.html", "--out", str(acme / "shots"), project=acme)
    assert r.returncode == 2 and "outside the project" in r.stderr
    r = bc("shot", "../outside.html", project=acme)
    assert r.returncode == 2


def test_shot_without_setup_names_the_fix(acme, tmp_path):
    r = bc("shot", "rounds/r1/board.html", project=acme, data=tmp_path / "nosetup")
    assert r.returncode == 3 and "setup" in r.stderr


# ---------------------------------------------------------------- cards

def card_html(acme, body="<div style='width:100vw;height:100vh;background:#336699'></div>", name="c.html"):
    f = acme / "assets" / "social" / "_build" / name
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(f"<!doctype html><meta charset=utf-8><style>html,body{{margin:0}}</style>{body}")
    return f.relative_to(acme).as_posix()


def test_card_renders_exact_pixels_and_is_put_on_byte_change(acme):
    rel = card_html(acme)
    r = bc("card", rel, "--width", "300", "--height", "150", "--out", "assets/social/c.png", "--json", project=acme)
    assert r.returncode == 0, r.stderr
    info = json.loads(r.stdout.strip().splitlines()[-1])
    assert info["changed"] is True and (info["width"], info["height"]) == (300, 150)
    png = acme / "assets" / "social" / "c.png"
    assert png_size(png.read_bytes()) == (300, 150)
    m = png.stat().st_mtime_ns
    info = json.loads(bc("card", rel, "--width", "300", "--height", "150", "--out", "assets/social/c.png", "--json", project=acme).stdout.strip().splitlines()[-1])
    assert info["changed"] is False and png.stat().st_mtime_ns == m
    r = bc("card", rel, "--width", "300", "--height", "150", "--dsf", "2", "--out", "assets/social/c2.png", "--json", project=acme)
    assert png_size((acme / "assets" / "social" / "c2.png").read_bytes()) == (600, 300)


def test_card_refuses_network_and_outside_outputs(acme, tmp_path):
    rel = card_html(acme, body='<img src="https://example.invalid/x.png">', name="net.html")
    r = bc("card", rel, "--width", "100", "--height", "100", "--out", "assets/social/n.png", project=acme)
    assert r.returncode == 1 and "not self-contained" in r.stderr
    assert not (acme / "assets" / "social" / "n.png").exists()
    rel = card_html(acme)
    r = bc("card", rel, "--width", "100", "--height", "100", "--out", str(tmp_path / "elsewhere.png"), project=acme)
    assert r.returncode == 2 and "outside the project" in r.stderr
    assert bc("card", rel, "--height", "100", "--out", "assets/x.png", project=acme).returncode == 2
