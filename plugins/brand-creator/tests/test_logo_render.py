"""logo-sheet, shot and card (the Chromium driver)."""
import json
import struct

import pytest
from helpers import bc, failing, mutate, report

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
    r = bc("logo-sheet", "--min-contrast", "6", project=acme)  # the teal dot is 4.7:1 on the light ground
    assert r.returncode == 1 and "light:16px" in failing(report(acme, "logo-sheet"))


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
