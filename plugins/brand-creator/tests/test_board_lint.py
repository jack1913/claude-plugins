"""board-lint: required sections by data-section, with mutation tests that prove each requirement is enforced."""
import re

import pytest
from helpers import bc, failing, make_project, install_fixture, make_r2_board, mutate, report


@pytest.fixture
def proj(tmp_path):
    p = make_project(tmp_path)
    install_fixture(p, tokens=False, logo=False)
    return p


def lint(p, page="rounds/r1/board.html", *extra):
    return bc("board-lint", page, *extra, project=p)


def test_fixture_round_1_passes(proj):
    r = lint(proj)
    assert r.returncode == 0, r.stdout
    rep = report(proj, "board-lint")
    assert rep["tool"] == "board-lint" and rep["status"] == "pass" and rep["inputs"][0]["path"] == "rounds/r1/board.html"
    assert len(rep["inputs_sha"]) == 64


@pytest.mark.parametrize("section", ["strategy-core", "positioning-map", "hardest-surface", "none-of-these", "my-call", "questions", "reply"])
def test_round_1_missing_section_fails(proj, section):
    board = proj / "rounds" / "r1" / "board.html"
    mutate(board, f'data-section="{section}"', f'data-removed="{section}"')
    r = lint(proj)
    assert r.returncode == 1, r.stdout
    assert f"section:{section}" in failing(report(proj, "board-lint"))


def test_empty_section_fails(proj):
    board = proj / "rounds" / "r1" / "board.html"
    text = board.read_text()
    m = re.search(r'(<section class="block" id="hardest" data-section="hardest-surface">).*?(</section>)', text, re.S)
    assert m
    board.write_text(text.replace(m.group(0), m.group(1) + "\n  \n" + m.group(2)))
    assert board.read_text() != text
    r = lint(proj)
    assert r.returncode == 1 and "empty" in r.stdout
    assert "section:hardest-surface" in failing(report(proj, "board-lint"))


def test_placeholder_section_fails(proj):
    board = proj / "rounds" / "r1" / "board.html"
    text = board.read_text()
    m = re.search(r'(<section class="block" id="weak" data-section="weak-points">\s*<h2>.*?</h2>).*?(</section>)', text, re.S)
    assert m
    board.write_text(text.replace(m.group(0), m.group(1) + "<p>TODO</p>" + m.group(2)))
    assert board.read_text() != text
    assert lint(proj).returncode == 0  # weak points are not required in round 1, so a placeholder there is not a failure
    rep = report(proj, "board-lint")
    m = re.search(r'(<section class="block" id="hardest" data-section="hardest-surface">\s*<h2>.*?</h2>).*?(</section>)', board.read_text(), re.S)
    assert m
    board.write_text(board.read_text().replace(m.group(0), m.group(1) + "<p>TODO</p>" + m.group(2)))
    r = lint(proj)
    assert r.returncode == 1 and "section:hardest-surface" in failing(report(proj, "board-lint")), r.stdout
    assert rep["status"] == "pass"


def test_round_2_page_passes_and_each_required_section_is_enforced(proj):
    page = make_r2_board(proj)
    r = lint(proj, "rounds/r2/board.html")
    assert r.returncode == 0, r.stdout
    for section in ("what-changed", "weak-points", "losers"):
        original = mutate(page, f'data-section="{section}"', f'data-removed="{section}"')
        r = lint(proj, "rounds/r2/board.html")
        assert r.returncode == 1, (section, r.stdout)
        assert f"section:{section}" in failing(report(proj, "board-lint"))
        page.write_text(original)
    assert lint(proj, "rounds/r2/board.html").returncode == 0


def test_round_2_does_not_require_round_1_sections(proj):
    make_r2_board(proj)
    rep_ids = {r["id"]: r["status"] for r in (lint(proj, "rounds/r2/board.html") and report(proj, "board-lint"))["results"]}
    assert rep_ids["section:positioning-map"] == "info" and rep_ids["section:strategy-core"] == "info" and rep_ids["section:none-of-these"] == "info"


def test_loser_without_a_reason_fails(proj):
    page = make_r2_board(proj)
    mutate(page, '<p data-field="reason">Too soft next to the category\'s tool marks.</p>', "<p>Too soft.</p>")
    r = lint(proj, "rounds/r2/board.html")
    assert r.returncode == 1 and "loser:Lantern" in failing(report(proj, "board-lint"))


def test_loser_reason_must_be_one_line(proj):
    page = make_r2_board(proj)
    mutate(page, "Too soft next to the category's tool marks.", "x" * 250)
    assert lint(proj, "rounds/r2/board.html").returncode == 1


def test_today_is_required_only_when_an_incumbent_exists(proj):
    assert lint(proj).returncode == 0
    assert bc("state", "--set", "incumbent=the current wordmark on the website", project=proj).returncode == 0
    r = lint(proj)
    assert r.returncode == 1 and "section:today" in failing(report(proj, "board-lint"))
    board = proj / "rounds" / "r1" / "board.html"
    mutate(board, '<section class="block" id="core" data-section="strategy-core">', '<section data-section="today"><h2>Today</h2><p>The current wordmark.</p></section>\n  <section class="block" id="core" data-section="strategy-core">')
    assert lint(proj).returncode == 0
    # the override flag works without touching the state
    assert bc("state", "--set", "incumbent=none", project=proj).returncode == 0
    assert lint(proj, "rounds/r1/board.html", "--incumbent", "yes").returncode == 0


def test_positioning_map_is_required_again_after_a_full_rejection(proj):
    page = make_r2_board(proj)
    assert lint(proj, "rounds/r2/board.html").returncode == 0
    assert bc("state", "--set", "reset_rounds=[2]", project=proj).returncode == 0
    r = lint(proj, "rounds/r2/board.html")
    assert r.returncode == 1
    ids = failing(report(proj, "board-lint"))
    assert "section:positioning-map" in ids and "page:data-board" in ids  # a reset round is a pick board
    assert page.exists()


def test_every_direction_must_be_on_the_map_and_one_must_be_far(proj):
    board = proj / "rounds" / "r1" / "board.html"
    before = mutate(board, '<span class="dot" data-direction="Keystone"', '<span class="dot" data-x="Keystone"')
    r = lint(proj)
    assert r.returncode == 1 and "map:every-direction" in failing(report(proj, "board-lint"))
    board.write_text(before)
    mutate(board, ' data-far="true"', "")
    r = lint(proj)
    assert r.returncode == 1 and "map:far-from-norm" in failing(report(proj, "board-lint"))


def test_directions_need_word_names_distinct_registers_and_enough_of_them(proj):
    board = proj / "rounds" / "r1" / "board.html"
    before = mutate(board, 'data-name="Compass"', 'data-name="A"')
    assert lint(proj).returncode == 1 and any(i.endswith(":name") for i in failing(report(proj, "board-lint")))
    board.write_text(before)
    before = mutate(board, 'data-register="warm"', 'data-register="calm"')
    assert lint(proj).returncode == 1 and any(i.endswith(":register") for i in failing(report(proj, "board-lint")))
    board.write_text(before)
    mutate(board, '<article class="direction" data-section="direction" data-name="Keystone"', '<article class="direction" data-x="direction" data-name="Keystone"')
    r = lint(proj)
    assert r.returncode == 1 and "directions:count" in failing(report(proj, "board-lint"))


def test_my_call_needs_recommendation_and_critique_and_judge_fields(proj):
    board = proj / "rounds" / "r1" / "board.html"
    before = mutate(board, 'data-field="critique"', 'data-x="critique"')
    assert lint(proj).returncode == 1 and "my-call:critique" in failing(report(proj, "board-lint"))
    board.write_text(before)
    mutate(board, '<section class="block" id="call" data-section="my-call">', '<section class="block" id="call" data-section="my-call" data-judge="ran">')
    r = lint(proj)
    assert r.returncode == 1
    ids = failing(report(proj, "board-lint"))
    assert {"my-call:judge-view", "my-call:lead-view", "my-call:middle-option"} <= set(ids)


def test_page_must_declare_the_matching_round(proj):
    board = proj / "rounds" / "r1" / "board.html"
    mutate(board, 'data-round="1"', 'data-round="2"')
    r = lint(proj)
    assert r.returncode == 1 and "page:data-round" in failing(report(proj, "board-lint"))


def test_inventory_gate_applies_to_full_tier_round_1(proj):
    assert bc("state", "--set", "tier=full", project=proj).returncode == 0
    r = lint(proj)
    assert r.returncode == 1 and "project:inventory" in failing(report(proj, "board-lint"))
    assert bc("state", "--set", "inventory=none (no target repo)", project=proj).returncode == 0
    assert lint(proj).returncode == 0
    assert bc("state", "--set", "inventory=", project=proj).returncode == 0
    (proj / "INVENTORY.md").write_text("# Inventory\n")
    assert lint(proj).returncode == 0
    # product-in-family also needs it
    (proj / "INVENTORY.md").write_text("")
    assert bc("state", "--set", "tier=quick", "--set", "architecture=product-in-family", project=proj).returncode == 0
    (proj / "INVENTORY.md").rename(proj / "INVENTORY.bak")
    assert lint(proj).returncode == 1


def test_usage_errors(proj, tmp_path):
    assert bc("board-lint", "rounds/r1/missing.html", project=proj).returncode == 2
    stray = proj / "loose.html"
    stray.write_text('<body data-round="1" data-board="pick">x</body>')
    assert bc("board-lint", "loose.html", project=proj).returncode in (0, 1)  # the page's own data-round is used
    outside = tmp_path / "outside.html"
    outside.write_text("x")
    assert bc("board-lint", str(outside), project=proj).returncode == 2


# ---------------------------------------------------------------- questions, reflex test, unfilled template markers

def test_questions_must_be_numbered_with_lettered_options(proj):
    board = proj / "rounds" / "r1" / "board.html"
    before = mutate(board, 'data-section="question" data-n="2"', 'data-section="question" data-n="3"')
    r = lint(proj)
    assert r.returncode == 1 and "question:3:number" in failing(report(proj, "board-lint")), r.stdout
    board.write_text(before)
    before = mutate(board, '<li data-option="b"><label><input type="radio" name="q2"', '<li data-option="c"><label><input type="radio" name="q2"')
    r = lint(proj)
    assert r.returncode == 1 and "question:2:options" in failing(report(proj, "board-lint")), r.stdout
    board.write_text(before)
    before = mutate(board, '<li data-option="b"><label><input type="radio" name="q1"', '<li data-option="b" data-recommended="true"><label><input type="radio" name="q1"')
    r = lint(proj)
    assert r.returncode == 1 and "question:1:options" in failing(report(proj, "board-lint")), r.stdout
    board.write_text(before)
    text = board.read_text()
    board.write_text(re.sub(r'data-section="question" data-n="\d"', 'data-x="question"', text))
    assert board.read_text() != text
    r = lint(proj)
    assert r.returncode == 1 and "questions:items" in failing(report(proj, "board-lint")), r.stdout


def test_pick_board_directions_need_a_reflex_result(proj):
    board = proj / "rounds" / "r1" / "board.html"
    mutate(board, '<p class="reflex" data-field="reflex">Reflex test: one hit', '<p class="reflex">Reflex test: one hit')
    r = lint(proj)
    assert r.returncode == 1 and "direction:Lantern:reflex" in failing(report(proj, "board-lint")), r.stdout


def test_refine_board_does_not_need_a_reflex_result(proj):
    page = make_r2_board(proj)
    mutate(page, 'data-field="reflex"', 'data-x="reflex"')
    assert lint(proj, "rounds/r2/board.html").returncode == 0


def test_unfilled_template_markers_fail_in_text_and_attributes_but_not_in_comments(proj):
    board = proj / "rounds" / "r1" / "board.html"
    before = mutate(board, "<h1>Acme: round 1</h1>", "<h1>Acme: round 1</h1><!-- [[fill: a note in a comment]] -->")
    assert lint(proj).returncode == 0
    board.write_text(before)
    before = mutate(board, "<h1>Acme: round 1</h1>", "<h1>Acme: round 1</h1><p>[[fill: lede]]</p>")
    r = lint(proj)
    assert r.returncode == 1 and "page:unfilled" in failing(report(proj, "board-lint")), r.stdout
    board.write_text(before)
    mutate(board, 'data-register="calm"', 'data-register="[[fill: register]]"')
    r = lint(proj)
    assert r.returncode == 1 and "page:unfilled" in failing(report(proj, "board-lint")), r.stdout


@pytest.mark.parametrize("template", ["round-page.html", "board.html", "review/index.html"])
def test_templates_carry_the_contract_and_fail_until_filled(proj, template):
    """A template copied as-is must fail (unfilled markers), and it must already carry every section it needs."""
    from helpers import ROOT
    src = (ROOT / "templates" / template).read_text()
    for sid in ("hardest-surface", "my-call", "questions", "reply", "direction", "weak-points"):
        assert f'data-section="{sid}"' in src, (template, sid)
    for fid in ("idea", "recommendation", "critique"):
        assert f'data-field="{fid}"' in src, (template, fid)
    if template != "board.html":
        for sid in ("strategy-core", "positioning-map", "none-of-these", "what-changed", "losers", "today"):
            assert f'data-section="{sid}"' in src, (template, sid)
    else:
        for sid in ("what-changed", "losers"):
            assert f'data-section="{sid}"' in src, (template, sid)
    dest = proj / "rounds" / "r1" / "board.html"
    dest.write_text(src)
    r = lint(proj)
    assert r.returncode == 1 and "page:unfilled" in failing(report(proj, "board-lint")), r.stdout


# ---------------------------------------------------------------- PF-8 recommended option, PF-2 direction letters

def test_a_question_needs_exactly_one_recommended_option(proj):
    board = proj / "rounds" / "r1" / "board.html"
    before = mutate(board, '<li data-option="a" data-recommended="true"><label><input type="radio" name="q1"',
                    '<li data-option="a"><label><input type="radio" name="q1"')
    r = lint(proj)
    assert r.returncode == 1 and "question:1:options" in failing(report(proj, "board-lint")), r.stdout
    assert "no option is marked" in r.stdout
    board.write_text(before)
    assert lint(proj).returncode == 0


def _with_letters(board):
    text = board.read_text()
    assert "data-letter" not in text  # the shipped example follows the default: word names only
    out = re.sub(r'(<article class="direction" data-section="direction" data-name="[^"]+")', r'\1 data-letter="@@"', text)
    letters = iter("ABCDE")
    while "@@" in out:
        out = out.replace("@@", next(letters), 1)
    assert out != text
    board.write_text(out)
    return text


def test_direction_letter_equal_to_an_option_letter_warns(proj):
    board = proj / "rounds" / "r1" / "board.html"
    _with_letters(board)
    r = lint(proj)
    rows = [x for x in report(proj, "board-lint")["results"] if x["status"] == "warn" and x["id"].endswith(":letters")]
    assert r.returncode == 0 and rows, r.stdout  # a warning, not a failure
    # mutation: a question whose options name the directions is not ambiguous, so the warning goes away for it
    names = re.findall(r'data-section="direction" data-name="([^"]+)"', board.read_text())
    ids_before = {x["id"] for x in rows}
    mutate(board, 'value="a">a. Yes, as written', 'value="a">a. ' + names[0] + ', as written')
    lint(proj)
    after = {x["id"] for x in report(proj, "board-lint")["results"] if x["status"] == "warn" and x["id"].endswith(":letters")}
    assert "question:2:letters" in ids_before and "question:2:letters" not in after


def test_no_letters_no_warning(proj):
    lint(proj)
    assert not [x for x in report(proj, "board-lint")["results"] if x["id"].endswith(":letters")]


def test_round_page_template_leaves_direction_letters_off():
    from helpers import ROOT
    t = (ROOT / "templates" / "round-page.html").read_text(encoding="utf-8")
    live = re.sub(r"<!--.*?-->", "", t, flags=re.S)
    assert 'data-letter="' not in live and 'class="letter">' not in live
    assert "Answer with a direction name, or question number plus option (1a)" in live
    assert not re.search(r'name="q1" value="[a-d]">[a-d]\. ', live)
