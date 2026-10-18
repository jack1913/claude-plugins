"""outline-glyphs: font instance -> overlap removal -> SVG paths. Oracles: resvg's fill rules, the pixel bounds of the render, the
font's own hand-checked axes, mark_lint (no live text)."""
import json
import re
import subprocess

import pytest
from helpers import TEST_FONT, bc, font_variant, make_project

import mark_lint
from pxio import read_png

pytestmark = pytest.mark.requires_resvg


@pytest.fixture
def proj(tmp_path):
    return make_project(tmp_path)


def outline(proj, text, *extra, out="assets/logo/word.svg", font=TEST_FONT):
    r = bc("outline-glyphs", "--font", str(font), "--text", text, "--out", out, *extra, project=proj)
    return r, proj / out


def viewbox(svg: str) -> tuple[float, float]:
    m = re.search(r'viewBox="0 0 ([0-9.]+) ([0-9.]+)"', svg)
    return float(m.group(1)), float(m.group(2))


def render(svg: str, tmp, name="r", width=512):
    f = tmp / f"{name}.svg"
    f.write_text(svg)
    out = tmp / f"{name}.png"
    subprocess.run(["resvg", "-w", str(width), str(f), str(out)], check=True, capture_output=True)
    return read_png(out.read_bytes())


def alpha_bbox(png):
    w, h, px = png
    xs = [i // 4 % w for i in range(0, len(px), 4) if px[i + 3] > 64]
    ys = [i // 4 // w for i in range(0, len(px), 4) if px[i + 3] > 64]
    return min(xs), min(ys), max(xs), max(ys), w, h


def test_info_names_the_font_and_its_axes(proj):
    r = bc("outline-glyphs", "--font", str(TEST_FONT), "--info", project=proj)
    assert r.returncode == 0, r.stderr
    assert "Inter" in r.stdout and "wght 100..900 (default 400)" in r.stdout and "opsz 14..32 (default 14)" in r.stdout
    assert "unitsPerEm 2048" in r.stdout


def test_outlines_have_one_path_per_glyph_and_no_live_text(proj):
    r, f = outline(proj, "Aß Ł", "--axis", "wght=900")
    assert r.returncode == 0, r.stderr
    svg = f.read_text()
    assert svg.count("<path") == 3  # A, ß, Ł: the space has no outline
    assert "<text" not in svg and "font-family" not in svg and "<tspan" not in svg
    assert mark_lint.lint_svg_text(svg) == []
    assert 'role="img"' in svg and 'aria-label="Aß Ł"' in svg and "data-source=\"Inter opsz=14,wght=900\"" in svg
    for k in ("data-baseline", "data-cap-height", "data-x-height"):
        assert re.search(k + r'="[0-9.]+"', svg), k


def test_axes_default_to_the_fonts_defaults_and_change_the_shape(proj):
    _, f = outline(proj, "A")
    default = f.read_text()
    assert 'data-source="Inter opsz=14,wght=400"' in default
    _, f = outline(proj, "A", "--axis", "wght=100")
    thin = f.read_text()
    _, f = outline(proj, "A", "--axis", "wght=900")
    black = f.read_text()
    assert len({re.search(r' d="([^"]+)"', s).group(1) for s in (default, thin, black)}) == 3
    assert viewbox(thin)[0] < viewbox(default)[0] < viewbox(black)[0] + 5  # heavier is wider (thin is narrowest)


def test_overlaps_are_removed_and_the_flag_shows_what_they_were(proj, tmp_path):
    """A variable font draws a glyph as overlapping contours. With nonzero fill that is invisible; with even-odd the overlap
    becomes a hole. After removal the two fill rules must give identical pixels; with --keep-overlaps they must not."""
    def diff(extra):
        _, f = outline(proj, "A", "--axis", "wght=900", *extra)
        svg = f.read_text()
        a = render(svg, tmp_path, "nz")
        b = render(svg.replace('<g fill="#000000">', '<g fill="#000000" fill-rule="evenodd">'), tmp_path, "eo")
        assert svg.replace('<g fill="#000000">', '<g fill="#000000" fill-rule="evenodd">') != svg  # the mutation applied
        return sum(1 for i in range(0, len(a[2]), 4) if a[2][i + 3] != b[2][i + 3])
    assert diff([]) == 0
    assert diff(["--keep-overlaps"]) > 20


def test_the_ink_fills_the_viewbox_and_padding_is_added_around_it(proj, tmp_path):
    _, f = outline(proj, "Ał", "--axis", "wght=700")
    svg = f.read_text()
    x0, y0, x1, y1, w, h = alpha_bbox(render(svg, tmp_path, "tight"))
    assert x0 <= 1 and y0 <= 1 and x1 >= w - 2 and y1 >= h - 2  # no padding: the ink touches all four edges
    _, f = outline(proj, "Ał", "--axis", "wght=700", "--padding", "10")
    padded = f.read_text()
    (tw, th), (pw, ph) = viewbox(svg), viewbox(padded)
    assert abs(pw - (tw + 20)) < 0.05 and abs(ph - (th + 20)) < 0.05
    x0, y0, x1, y1, w, h = alpha_bbox(render(padded, tmp_path, "pad", width=1024))
    assert abs(x0 - 10 * w / pw) < 3 and abs(y0 - 10 * h / ph) < 3


def test_size_tracking_and_manual_pairs_change_the_width_by_the_amount_asked(proj):
    def width(*extra):
        _, f = outline(proj, "AV", *extra)
        return viewbox(f.read_text())[0]
    base = width()
    assert abs(width("--em", "200") - 2 * base) < 0.1  # the em scales the whole line
    assert abs(width("--tracking", "100") - (base + 10)) < 0.05  # 100/1000 em at em 100, one gap
    assert abs(width("--pair", "AV=-60") - (base - 6)) < 0.05
    r, _ = outline(proj, "AV", "--pair", "AVX=3")
    assert r.returncode == 2 and "two characters" in r.stderr


def test_output_is_byte_stable_and_only_written_on_change(proj):
    r1, f = outline(proj, "Łódź", "--axis", "wght=600")
    first = f.read_bytes()
    r2, _ = outline(proj, "Łódź", "--axis", "wght=600")
    assert "written" in r1.stdout and "unchanged" in r2.stdout and f.read_bytes() == first
    r3, _ = outline(proj, "Łódź", "--axis", "wght=650")
    assert "written" in r3.stdout and f.read_bytes() != first


def test_errors_are_explicit(proj, tmp_path):
    r, f = outline(proj, "Č")  # not in the subset
    assert r.returncode == 1 and "U+010C" in r.stderr and not f.exists()
    r, _ = outline(proj, "A", "--axis", "slnt=5")
    assert r.returncode == 2 and "no axis slnt" in r.stderr and "wght" in r.stderr
    r, _ = outline(proj, "A", "--axis", "wght=2000")
    assert r.returncode == 2 and "outside the font's range 100..900" in r.stderr
    r, _ = outline(proj, "A", "--axis", "wght")
    assert r.returncode == 2
    r, _ = outline(proj, "A\nB")
    assert r.returncode == 2 and "one line" in r.stderr
    r, _ = outline(proj, "A", "--fill", "red")
    assert r.returncode == 2
    r, _ = outline(proj, "   ")
    assert r.returncode == 1 and "no outlines" in r.stderr
    r, _ = outline(proj, "A", out="../outside.svg")
    assert r.returncode == 2 and "outside the project" in r.stderr
    r = bc("outline-glyphs", "--font", str(tmp_path / "missing.ttf"), "--text", "A", project=proj)
    assert r.returncode == 2 and "font not found" in r.stderr
    bad = tmp_path / "not-a-font.ttf"
    bad.write_bytes(b"this is not a font")
    r = bc("outline-glyphs", "--font", str(bad), "--text", "A", project=proj)
    assert r.returncode == 2 and "not a readable font" in r.stderr


def test_a_static_font_takes_no_axes_and_has_no_instance_in_its_name(proj, tmp_path):
    static = font_variant(tmp_path / "static.ttf", static=True)
    r, f = outline(proj, "A", font=static)
    assert r.returncode == 0, r.stderr
    assert 'data-source="Inter"' in f.read_text()
    r, _ = outline(proj, "A", "--axis", "wght=700", font=static)
    assert r.returncode == 2 and "static" in r.stderr


def test_the_outlined_wordmark_is_a_valid_mark_for_check_and_guides(proj):
    """The data-* metrics the outliner writes are what `logo-sheet --guides` draws and measures (see test_guides.py)."""
    r, f = outline(proj, "Acme", "--axis", "wght=700", "--fill", "#0d1b2d")
    assert r.returncode == 0
    c = bc("check", project=proj)
    assert "[PASS] mark_lint:assets/logo/word.svg" in c.stdout
    assert json.loads((proj / "assets/_checks/check.json").read_text())["tool"] == "check"
