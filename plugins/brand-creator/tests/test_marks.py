"""Several marks in one project (qa/rules.json marks): each mark has its own bands, files, reports and manifest rows; emit social
shows them side by side; check, logo-sheet, contrast and the book follow the marks. The marks here are synthetic, drawn in Acme's own
palette (the plugin's worked test brand): nothing in this file is a real brand."""
import base64
import json
import re
import shutil
from pathlib import Path

import pytest
from helpers import FIXTURES, bc, mutate_json, report

import _emit

INK, TEAL, CHALK, BRIGHT = "#0d1b2d", "#007d71", "#f0eee7", "#4cd7c8"   # Acme's ink, teal, chalk and bright teal


def pixel(w: int, h: int, cells: list[tuple[int, int, int, int, str]]) -> str:
    rects = "".join(f'<rect x="{x}" y="{y}" width="{cw}" height="{ch}" fill="{c}"/>' for x, y, cw, ch, c in cells)
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" shape-rendering="crispEdges">{rects}</svg>'


def ring(n: int, t: int, dot: tuple[int, int], ink: str, accent: str) -> str:
    """A square ring t cells thick on an n grid, with a dot that never touches it."""
    a, b = t, n - 2 * t
    return pixel(n, n, [(a, a, b, t, ink), (a, n - 2 * t, b, t, ink), (a, a + t, t, b - 2 * t, ink), (n - 2 * t, a + t, t, b - 2 * t, ink),
                        (dot[0], dot[0], dot[1], dot[1], accent)])


ALPHA = {"alpha": ring(16, 2, (6, 4), INK, TEAL), "alpha-dark": ring(16, 2, (6, 4), CHALK, BRIGHT),
         "alpha-8": ring(8, 1, (3, 2), INK, TEAL), "alpha-8-dark": ring(8, 1, (3, 2), CHALK, BRIGHT),
         "alpha-wordmark": pixel(20, 5, [(0, 0, 3, 5, INK), (4, 0, 1, 5, INK), (6, 0, 3, 1, INK), (6, 4, 3, 1, INK), (12, 0, 3, 5, INK), (16, 0, 4, 1, INK)]),
         "alpha-wordmark-dark": pixel(20, 5, [(0, 0, 3, 5, CHALK), (4, 0, 1, 5, CHALK), (6, 0, 3, 1, CHALK), (6, 4, 3, 1, CHALK), (12, 0, 3, 5, CHALK),
                                              (16, 0, 4, 1, CHALK)])}
MARKS = {"alpha": {"name": "Alpha", "tagline": "repair guide",
                   "bands": [{"name": "small", "max_px": 16, "drawing": "assets/logo/alpha-8.svg"}, {"name": "large", "drawing": "assets/logo/alpha.svg"}]},
         "beta": {"accent": "color.muted", "bands": [{"name": "all", "drawing": "assets/logo/beta.svg"}]}}


def make_multi(p: Path) -> Path:
    """Acme with two marks instead of one: alpha (pixel art, a small drawing for 16 px and below, a drawn wordmark) and beta (Acme's
    vector mark, one band, no wordmark: its name is typed)."""
    logo = p / "assets/logo"
    for name, svg in ALPHA.items():
        (logo / f"{name}.svg").write_text(svg)
    shutil.copy2(logo / "mark.svg", logo / "beta.svg")
    shutil.copy2(logo / "mark-dark.svg", logo / "beta-dark.svg")

    def to_marks(d):
        d.pop("bands", None)
        d["marks"] = MARKS
    mutate_json(p / "qa/rules.json", to_marks)
    shutil.copy2(FIXTURES / "FACTS.md", p / "FACTS.md")
    return p


@pytest.fixture
def multi(acme) -> Path:
    return make_multi(acme)


def emit(p: Path, *a: str):
    return bc("emit", *a, project=p)


def rows(p: Path) -> list[dict]:
    return json.loads((p / "assets/manifest.json").read_text())["artefacts"]


def page(p: Path, rel: str) -> str:
    return re.sub(r"<!--.*?-->", "", (p / rel).read_text(), flags=re.S)


# ---------------------------------------------------------------- qa/rules.json marks

@pytest.mark.parametrize("marks, needle", [
    ({"Alpha": {"bands": [{"name": "all", "drawing": "assets/logo/alpha.svg"}]}}, "a mark id is lower-case"),
    ({"alpha": {}}, "marks.alpha.bands: every mark names its drawing for each size"),
    ({"alpha": {"bands": [{"name": "all", "drawing": "assets/logo/alpha.svg"}], "colour": "x"}}, "marks.alpha has unknown keys ['colour']"),
    ({"alpha": {"bands": [{"name": "all", "drawing": "assets/logo/alpha.svg"}], "name": 3}}, "marks.alpha.name must be a string"),
    ({"alpha": {"bands": [{"name": "s", "max_px": 16, "drawing": "assets/logo/alpha-8.svg"}]}}, "marks.alpha.bands[0] stops at 16 px"),
])
def test_a_marks_section_that_is_wrong_is_refused_with_the_reason(multi, marks, needle):
    mutate_json(multi / "qa/rules.json", lambda d: d.__setitem__("marks", marks))
    r = emit(multi, "web", "--mark", "alpha")
    assert r.returncode == 2 and needle in r.stderr, r.stderr


def test_the_one_mark_rules_next_to_marks_are_refused(multi):
    mutate_json(multi / "qa/rules.json", lambda d: d.__setitem__("bands", [{"name": "all", "drawing": "assets/logo/mark.svg"}]))
    r = emit(multi, "web", "--mark", "alpha")
    assert r.returncode == 2 and "move the top-level bands and favicon.drawing into the marks" in r.stderr


def test_with_marks_every_run_names_one_and_nothing_is_guessed(multi, acme_copy):
    r = emit(multi, "web")
    assert r.returncode == 2 and "several marks (alpha, beta): pass --mark <id>" in r.stderr
    r = emit(multi, "web", "--mark", "gamma")
    assert r.returncode == 2 and "unknown mark 'gamma'" in r.stderr and "alpha, beta" in r.stderr
    r = emit(multi, "web", "--mark", "alpha", "--svg", "assets/logo/mark.svg")
    assert r.returncode == 2 and "--svg and --svg-dark name one mark's file" in r.stderr
    r = bc("logo-sheet", project=multi)
    assert r.returncode == 2 and "pass --mark <id>" in r.stderr
    r = emit(acme_copy, "web", "--mark", "alpha")
    assert r.returncode == 2 and "this project has one mark" in r.stderr


@pytest.fixture
def acme_copy(golden, tmp_path) -> Path:
    dst = tmp_path / "one-mark"
    shutil.copytree(golden, dst)
    return dst


# ---------------------------------------------------------------- emitters

def test_each_mark_gets_its_own_files_report_rows_and_bands(multi):
    for m in ("alpha", "beta"):
        r = emit(multi, "web", "--mark", m)
        assert r.returncode == 0, r.stdout + r.stderr
        assert report(multi, f"emit-web/{m}")["status"] == "pass"
    web = [a for a in rows(multi) if a["emitter"] == "web"]
    assert {a["mark"] for a in web} == {"alpha", "beta"} and all(a["path"].startswith(f"assets/web/{a['mark']}/") for a in web)
    by = {a["path"]: a for a in web}
    assert by["assets/web/alpha/favicon.ico"]["layer_bands"]["16"] == "small" and by["assets/web/alpha/favicon.ico"]["layer_bands"]["32"] == "large"
    assert by["assets/web/alpha/icon.svg"]["drawing_file"] == "assets/logo/alpha-8.svg"   # the tab size takes alpha's own small drawing
    assert by["assets/web/beta/icon.svg"]["drawing_file"] == "assets/logo/beta.svg"
    assert json.loads((multi / "assets/web/alpha/site.webmanifest").read_text())["name"] == "Alpha"   # the mark's name, not the brand's
    assert not (multi / "assets/web/favicon.ico").exists()
    assert " 0 written" in emit(multi, "web", "--mark", "alpha").stdout   # idempotent per mark


def test_a_run_of_one_mark_never_retires_another_marks_files(multi):
    """alpha written into a folder that holds beta's files: its runs leave beta's rows and files alone."""
    assert emit(multi, "web", "--mark", "beta").returncode == 0
    for _ in range(2):
        assert emit(multi, "web", "--mark", "alpha", "--out-dir", "assets/web").returncode == 0
    beta = [a for a in rows(multi) if a.get("mark") == "beta"]
    assert beta and all((multi / a["path"]).is_file() for a in beta)
    assert not list(multi.glob("removed-*"))


def test_check_ties_each_row_to_its_own_marks_bands(multi):
    assert emit(multi, "web", "--mark", "alpha").returncode == 0

    def lie(d):   # alpha's 16 px layer claims beta's band
        a = next(x for x in d["artefacts"] if x["path"] == "assets/web/alpha/favicon.ico")
        a["layer_bands"]["16"] = "all"
    mutate_json(multi / "assets/manifest.json", lie)
    bc("check", project=multi)
    rep = {x["id"]: x for x in report(multi, "check")["results"]}
    assert rep["manifest:bands"]["status"] == "fail" and "band 'all', which is not defined" in rep["manifest:bands"]["detail"]


def test_check_wants_every_marks_reports_and_drawings(multi):
    assert emit(multi, "web", "--mark", "alpha").returncode == 0
    bc("check", project=multi)
    rep = {x["id"]: x for x in report(multi, "check")["results"]}
    assert rep["marks:alpha"]["status"] == "pass" and rep["report:emit-web/alpha"]["status"] == "pass"
    assert rep["report:logo-sheet/beta"]["status"] == "skipped" and "logo-sheet --mark beta" in rep["report:logo-sheet/beta"]["detail"]
    assert "report:logo-sheet" not in rep and "report:emit-web" not in rep
    (multi / "assets/logo/alpha-8.svg").rename(multi / "alpha-8.svg")
    bc("check", project=multi)
    rep = {x["id"]: x for x in report(multi, "check")["results"]}
    assert rep["marks:alpha"]["status"] == "fail" and "assets/logo/alpha-8.svg" in rep["marks:alpha"]["detail"]


def test_social_shows_every_mark_side_by_side_and_each_mark_on_its_own(multi):
    r = emit(multi, "social", "--repo-images", "yes")
    assert r.returncode == 0, r.stdout + r.stderr
    html = page(multi, "assets/social/_build/github-social.html")
    figs = re.findall(r'<figure><img class="m" alt="([^"]+) mark" width="(\d+)" height="(\d+)"', html)
    assert [f[0] for f in figs] == ["Alpha", "beta"]
    assert int(figs[0][1]) % 16 == 0 and figs[0][1] == figs[0][2]          # pixel art at a whole-number scale of its 16 grid
    caps = re.findall(r"<figcaption>(.*?)</figcaption>", html)
    assert 'class="lettering" alt="Alpha"' in caps[0] and caps[1] == "beta"            # alpha's drawn wordmark; beta's name typed
    assert re.search(r'<div class="head"><img class="lettering" alt="Acme"', html)     # above them, the brand's own drawn wordmark
    res = {x["id"]: x for x in report(multi, "emit-social")["results"]}
    assert res["note:lineup beta"]["status"] == "warn" and "assets/logo/beta-wordmark.svg" in res["note:lineup beta"]["detail"]
    dark = re.search(r'<img class="m" alt="Alpha mark" width="\d+" height="\d+" src="data:image/svg\+xml;base64,([A-Za-z0-9+/=]+)"',
                     page(multi, "assets/social/_build/readme-header-dark.html"))
    assert dark and base64.b64decode(dark.group(1)).decode() == ALPHA["alpha-dark"]   # the dark header takes each mark's dark drawing
    # one mark: its own folder, report and rows, with its wordmark next to it, its tagline and its accent
    r = emit(multi, "social", "--mark", "alpha")
    assert r.returncode == 0, r.stdout + r.stderr
    a = page(multi, "assets/social/alpha/_build/og.html")
    assert '<body class="wordmark">' in a and "a repair guide is in every box" in a
    m = re.search(r'<img class="lettering" alt="Alpha" width="(\d+)" height="(\d+)" src="data:image/svg\+xml;base64,([A-Za-z0-9+/=]+)"', a)
    assert m and int(m.group(1)) % 20 == 0 and int(m.group(2)) % 5 == 0
    assert base64.b64decode(m.group(3)).decode() == ALPHA["alpha-wordmark"]               # alpha's own wordmark, not the brand's
    size = re.search(r"\.mark\{flex:none;height:(\d+)px;aspect-ratio:1\}", a)
    assert size and int(size.group(1)) % 16 == 0
    assert report(multi, "emit-social/alpha")["status"] == "pass"
    r = emit(multi, "social", "--mark", "beta")
    assert r.returncode == 0, r.stdout + r.stderr
    b = page(multi, "assets/social/beta/_build/og.html")
    assert "background:#4b596c" in b and ".mark{flex:none;height:58vh;" in b   # beta's accent is color.muted; a vector mark keeps 58vh
    social = [x for x in rows(multi) if x["emitter"] == "social"]
    assert {x.get("mark") for x in social} == {None, "alpha", "beta"}
    assert all(x["path"].startswith(f"assets/social/{x['mark']}/") for x in social if x.get("mark"))
    assert " 0 written" in emit(multi, "social", "--repo-images", "yes").stdout   # the side-by-side run keeps the marks' rows


def test_a_mark_that_names_a_tagline_or_accent_the_project_does_not_have_stops_the_emit(multi):
    mutate_json(multi / "qa/rules.json", lambda d: d["marks"]["alpha"].__setitem__("tagline", "no such label"))
    r = emit(multi, "social", "--mark", "alpha")
    assert r.returncode == 1 and "its tagline label 'no such label' is not in FACTS.md" in r.stderr
    mutate_json(multi / "qa/rules.json", lambda d: d["marks"]["beta"].__setitem__("accent", "color.nope"))
    r = emit(multi, "social", "--mark", "beta")
    assert r.returncode == 1 and "names the accent color.nope, which the light tokens do not define" in r.stderr


def test_a_post_shows_one_mark(multi):
    assert bc("state", "--set", "tier=standard", project=multi).returncode == 0
    assert bc("state", "--set", "content_languages=en", project=multi).returncode == 0
    r = emit(multi, "social", "--posts", "--post-fact", "repair guide")
    assert r.returncode == 2 and "a post shows one mark: pass --mark <id> with --posts" in r.stderr


# ---------------------------------------------------------------- logo sheet, contrast

def test_the_logo_sheet_runs_per_mark_with_its_own_bands_and_report(multi):
    bc("logo-sheet", "--mark", "alpha", project=multi)
    doc = report(multi, "logo-sheet/alpha")
    tiles = doc["bands"]["tiles"]
    assert tiles["16"] == "assets/logo/alpha-8.svg" and tiles["128"] == "assets/logo/alpha.svg"
    assert (multi / "assets/_checks/logo-sheet/alpha.png").is_file() and not (multi / "assets/_checks/logo-sheet.png").exists()


def test_contrast_checks_the_touching_colours_of_every_mark(multi):
    bc("contrast", project=multi)
    inputs = {i["path"] for i in report(multi, "contrast")["inputs"]}
    for f in ("alpha.svg", "alpha-dark.svg", "alpha-8.svg", "alpha-wordmark.svg", "beta.svg", "beta-dark.svg"):
        assert f"assets/logo/{f}" in inputs, f
    assert "assets/logo/mark.svg" not in inputs and "qa/rules.json" in inputs


# ---------------------------------------------------------------- pixel art is scaled by whole numbers where the plugin picks the size

def test_pixel_art_is_scaled_by_whole_numbers_and_vector_art_keeps_its_box():
    px16 = ALPHA["alpha"]
    vec = (FIXTURES / "assets/logo/mark.svg").read_text()
    assert _emit.fit_art(px16, 100, 100) == (96, 96) and _emit.fit_art(ALPHA["alpha-wordmark"], 100, 23) == (80, 20)
    assert _emit.card_mark_size(px16, 630) == "352px" and _emit.card_mark_size(vec, 630) == "58vh"
    assert _emit.fit_art(vec, 100, 50) == (50, 50)
    assert _emit.whole_px(px16, 10) == 10 and _emit.whole_px(px16, 47) == 32


# ---------------------------------------------------------------- the book

def test_the_book_shows_every_mark_its_sizes_and_one_set_of_misuse_figures(multi):
    """The cover sets every mark side by side, "The mark by size" has a table per mark from its own bands, the misuse figures say they
    stand for every mark, and a name with no file of its own ({{marks:wordmark?}} without assets/logo/wordmark.svg) is looked up per mark."""
    from helpers import mutate
    from test_book import fill_markers
    (multi / "assets/logo/wordmark.svg").rename(multi / "wordmark.svg")
    (multi / "assets/logo/wordmark-dark.svg").rename(multi / "wordmark-dark.svg")
    for k, v in (("tier", "standard"), ("content_languages", "en")):
        assert bc("state", "--set", f"{k}={v}", project=multi).returncode == 0
    mutate(multi / "BRAND-STATE.md", "- (rule) (...)", "- (rule) the accent is a fill, never text (proposal)")
    for cmd in (("emit", "web", "--mark", "alpha"), ("contrast",), ("book", "--init")):
        r = bc(*cmd, project=multi)
        assert r.returncode == 0, (cmd, r.stdout + r.stderr)
    fill_markers(multi)
    r = bc("book", project=multi)
    assert r.returncode == 0, r.stdout + r.stderr
    html = (multi / "book.html").read_text()
    start = html.index('id="cover"')
    cover = html[start:html.index("</section>", start)]
    assert 'data-mark="alpha"' in cover and 'data-mark="beta"' in cover and 'data-mark="alpha-dark"' in cover and 'data-mark="mark"' not in cover
    assert "<h4>Alpha</h4>" in html and "<h4>beta</h4>" in html and "assets/logo/alpha-8.svg (small)" in html
    assert "Shown with one mark; the same applies to every mark." in html
    assert 'data-mark="alpha-wordmark"' in html and 'data-mark="beta-wordmark"' not in html   # beta has none: optional, left out


# ---------------------------------------------------------------- the finish chain

@pytest.mark.requires_resvg
def test_the_finish_chain_runs_each_pack_per_mark_and_the_side_by_side_images_through_to_check(multi, tmp_path):
    """templates/finish.sh.tpl with two marks: each emitter once per mark, emit social once more for every mark side by side, the
    idempotence run over all of them, and check at the end with every mark's reports in place."""
    from test_finish_chain import run, steps
    for cmd in (("logo-sheet", "--mark", "alpha"), ("logo-sheet", "--mark", "beta"), ("board-lint", "rounds/r1/board.html"),
                ("shot", "rounds/r1/board.html")):
        r = bc(*cmd, project=multi)
        assert r.returncode == 0, (cmd, r.stdout + r.stderr)
    tpl = (_emit.plugin_root() / "templates/finish.sh.tpl").read_text()
    tpl, n = re.subn(r"^TARGETS=\(.*\)$", "TARGETS=(web social)", tpl, flags=re.M)
    assert n == 1
    tpl, n = re.subn(r'^\[ "\$\(uname\)" = Darwin \] && TARGETS\+=\(apple\).*$', "", tpl, flags=re.M)
    assert n == 1
    fin = multi / "tools" / "finish.sh"
    fin.parent.mkdir(exist_ok=True)
    fin.write_text(tpl)
    r = run(fin, tmp_path)
    out = r.stdout + r.stderr
    assert r.returncode == 0, out[-3000:]
    ss = steps(out)
    for s in ("emit web --mark alpha", "emit web --mark beta", "emit social --mark alpha", "emit social --mark beta", "emit social"):
        assert s in ss, (s, ss)
    assert "emit web" not in ss                                   # never a run without a mark: it would stop with exit 2
    assert report(multi, "idempotence")["status"] == "pass" and "check: PASS" in out
    cmds = " ".join(report(multi, "idempotence").get("commands", []))
    assert "--mark alpha" in cmds and "--mark beta" in cmds
