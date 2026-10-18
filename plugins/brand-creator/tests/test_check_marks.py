"""mark_lint and `check`: marks must be vector; history, manifest and reports are verified; cascade finds leftovers."""
import json
import shutil

import pytest
from helpers import bc, failing, make_project, install_fixture, mutate, report

import mark_lint

CLEAN = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><path d="M0 0h10v10z" fill="#123456"/></svg>'

BAD = {
    "text": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><text x="0" y="8">A</text></svg>',
    "tspan": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><g><tspan>A</tspan></g></svg>',
    "textPath": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><textPath href="#p">A</textPath></svg>',
    "font-family attribute": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><g font-family="Inter"/></svg>',
    "font-family css": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><style>g{font-family: serif}</style></svg>',
    "@font-face": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><style>@font-face{font-family:X;src:url(x.woff2)}</style></svg>',
    "external href": '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 10 10"><image xlink:href="https://example.invalid/x.png"/></svg>',
    "relative href": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><use href="other.svg#a"/></svg>',
    "external css url": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect style="fill:url(http://example.invalid/p)"/></svg>',
    "script": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><script>alert(1)</script></svg>',
    "foreignObject": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><foreignObject><p>x</p></foreignObject></svg>',
}


def test_clean_svg_passes_the_lint():
    assert mark_lint.lint_svg_text(CLEAN) == []
    internal = CLEAN.replace("<path", '<defs><path id="a" d="M0 0h1"/></defs><use href="#a"/><path')
    assert mark_lint.lint_svg_text(internal) == []
    assert mark_lint.lint_svg_text(CLEAN.replace("<path", "<!-- <text>commented</text> --><path")) == []


@pytest.mark.parametrize("name", sorted(BAD))
def test_each_forbidden_construct_is_found(name):
    assert BAD[name] != CLEAN
    assert mark_lint.lint_svg_text(BAD[name]), name


@pytest.fixture
def proj(tmp_path):
    p = make_project(tmp_path)
    (p / "assets" / "logo").mkdir(parents=True)
    (p / "assets" / "logo" / "mark.svg").write_text(CLEAN)
    return p


def test_check_passes_the_lint_for_a_clean_mark_but_does_not_call_it_verified(proj):
    r = bc("check", project=proj)
    assert "[PASS] mark_lint:assets/logo/mark.svg" in r.stdout
    # a logo exists, so a logo-sheet report is expected; without it the project is "not verified", never "pass"
    assert r.returncode == 3 and "NOT-VERIFIED" in r.stdout and "report:logo-sheet" in r.stdout


@pytest.mark.parametrize("name", sorted(BAD))
def test_check_fails_when_a_mark_is_not_vector(proj, name):
    mutate(proj / "assets" / "logo" / "mark.svg", CLEAN, BAD[name])
    r = bc("check", project=proj)
    assert r.returncode == 1, r.stdout
    assert "mark_lint:assets/logo/mark.svg" in failing(report(proj, "check"))


def test_text_in_a_favicon_or_lockup_anywhere_under_assets_fails(proj):
    for rel in ("assets/web/icon.svg", "assets/lockup/lockup.svg", "assets/wordmark.svg"):
        f = proj / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(BAD["text"])
    r = bc("check", project=proj)
    assert r.returncode == 1
    assert len([i for i in failing(report(proj, "check")) if i.startswith("mark_lint:")]) == 3


def test_underscore_folders_are_not_linted(proj):
    f = proj / "assets" / "_scratch" / "demo.svg"
    f.parent.mkdir(parents=True)
    f.write_text(BAD["text"])
    r = bc("check", project=proj)
    assert r.returncode == 3 and "demo.svg" not in r.stdout  # linted marks only; the scratch folder is skipped


def test_check_verifies_the_history_manifest(tmp_path):
    p = make_project(tmp_path)
    (p / "rounds" / "r1").mkdir(parents=True)
    (p / "rounds" / "r1" / "notes.html").write_text("<p>approved</p>")
    assert bc("state", "--record", "G3", "ok", project=p).returncode == 0
    assert bc("freeze", "r1", "--name", "first", project=p).returncode == 0
    assert bc("check", project=p).returncode == 0
    frozen = p / "history" / "2026-10-17-first" / "notes.html"
    before = mutate(frozen, "approved", "edited")
    r = bc("check", project=p)
    assert r.returncode == 1 and "modified: history/2026-10-17-first/notes.html" in r.stdout
    frozen.write_text(before)
    assert bc("check", project=p).returncode == 0
    (p / "history" / "2026-10-17-first" / "sneaky.txt").write_text("added outside freeze")
    r = bc("check", project=p)
    assert r.returncode == 1 and "added outside freeze" in r.stdout
    (p / "history" / "2026-10-17-first" / "sneaky.txt").rename(p / "sneaky.bak")
    (frozen).rename(p / "notes.bak")
    r = bc("check", project=p)
    assert r.returncode == 1 and "missing" in r.stdout


def test_cascade_finds_leftover_old_values_and_skips_history(tmp_path):
    p = make_project(tmp_path)
    (p / "rounds" / "r1").mkdir(parents=True)
    (p / "rounds" / "r2").mkdir(parents=True)
    (p / "rounds" / "r1" / "notes.html").write_text("<p>the old threshold 4.5</p>")
    (p / "rounds" / "r2" / "notes.html").write_text("<p>the new threshold 7</p>")
    (p / "README.md").write_text("Threshold is 4.5 here.\n")
    (p / "decisions").mkdir()
    (p / "decisions" / "ADR-0001.md").write_text("we used to say 4.5\n")
    r = bc("check", "--cascade", "4.5", project=p)
    assert r.returncode == 1
    hits = report(p, "check")["results"][-1]["hits"]
    assert hits == ["README.md:1"]  # earlier rounds, decisions and BRAND-STATE are history, not current
    (p / "README.md").write_text("Threshold is 7 here.\n")
    assert bc("check", "--cascade", "4.5", project=p).returncode == 0
    (p / "README.md").write_text("THRESHOLD IS 4.5\n")
    assert bc("check", "--cascade", "threshold is 4.5", project=p).returncode == 0  # case-sensitive by default
    assert bc("check", "--cascade", "threshold is 4.5", "--ignore-case", project=p).returncode == 1


@pytest.mark.requires_setup
def test_check_demands_fresh_passing_reports_for_existing_artefacts(tmp_path):
    p = make_project(tmp_path)
    install_fixture(p)
    assert bc("state", "--record", "G3", "ok", project=p).returncode == 0
    r = bc("check", project=p)
    assert r.returncode == 3 and "report:logo-sheet" in r.stdout and "report:board-lint" in r.stdout  # nothing has run yet
    assert bc("tokens", project=p).returncode == 0
    r = bc("check", project=p)
    assert r.returncode == 3, r.stdout  # tokens built: contrast, logo-sheet, board-lint, shot reports are missing
    assert "not verified: no contrast report" in r.stdout
    for cmd in (["contrast"], ["logo-sheet"], ["board-lint", "rounds/r1/board.html"], ["shot", "rounds/r1/board.html"]):
        assert bc(*cmd, project=p).returncode == 0, cmd
    r = bc("check", project=p)
    assert r.returncode == 0, r.stdout
    rep = report(p, "check")
    assert rep["status"] == "pass"
    # a stale report is not a pass: change the board after its reports were written
    mutate(p / "rounds" / "r1" / "board.html", "Acme: round 1", "Acme: round one")
    r = bc("check", project=p)
    assert r.returncode == 3 and "stale" in r.stdout
    # a failing report is a failed gate
    assert bc("board-lint", "rounds/r1/board.html", project=p).returncode == 0
    assert bc("shot", "rounds/r1/board.html", project=p).returncode == 0
    assert bc("check", project=p).returncode == 0
    mutate(p / "tokens" / "semantic.light.tokens.json", "{color.slate}", "{color.mist}", count=2)
    assert bc("tokens", project=p).returncode == 0
    assert bc("contrast", project=p).returncode == 1
    r = bc("check", project=p)
    assert r.returncode == 1 and "report:contrast" in failing(report(p, "check"))


def test_check_with_nothing_to_gate_says_so(tmp_path):
    p = make_project(tmp_path)
    r = bc("check", project=p)
    assert r.returncode == 0 and "no gated artefacts yet" in r.stdout
