"""board-lint: required sections by data-section, with mutation tests that prove each requirement is enforced."""
import re
import shutil
from pathlib import Path

import pytest
from helpers import ROOT, bc, failing, fill_style_board, make_project, install_fixture, make_r2_board, mutate, report


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


CARD = re.compile(r'      <article class="(?:direction|territory)".*?</article>\n', re.S)   # the one card a board template holds: a direction, or a territory on the style board


@pytest.mark.parametrize("template", ["round-page.html", "style-board.html", "review/index.html"])
def test_each_card_of_a_board_template_has_a_vote_group_of_its_own_named_after_its_direction(template):
    """A radio name is one group for the whole page: with one name for every card (`vote-one`) a vote on the second card unchecks the first. The helpers that fill a template rename nothing, so this
    reads the template as it ships: the radios of the card carry the name of the card's own direction, and three cards made from it are three groups (the motion board's own test is in
    tests/test_motion_board.py; tests/node/boardvotes.test.mjs has the browser decide)."""
    from boardpage import parse_dom
    src = (ROOT / "templates" / template).read_text(encoding="utf-8")
    assert src.count('name="vote-[[fill: Name one]]"') == 3 and "vote-one" not in src, template                  # keep, drop and unsure of the one card, as it ships
    card = CARD.search(src).group(0)
    names = ("Compass", "Lantern", "Keystone")
    page = src.replace(card, "".join(card.replace("[[fill: Name one]]", n) for n in names), 1)
    root = parse_dom(page)
    groups = {n.attrs["data-vote"]: sorted({r.attrs.get("name") for r in n.walk() if r.tag == "input"}) for n in root.walk() if "data-vote" in n.attrs}
    assert groups == {n: [f"vote-{n}"] for n in names}, (template, groups)
    options = {r.attrs.get("name") for n in root.walk() if n.attrs.get("data-section") == "question" for r in n.walk() if r.tag == "input"}
    assert options and not options & {g for gs in groups.values() for g in gs}, (template, options)          # the questions keep their own groups


# ---------------------------------------------------------------- the votes: page:votes, a radio group of its own per card

def make_board(proj: Path, kind: str) -> tuple[str, tuple[str, ...]]:
    """A finished board of a kind that shows cards with a vote: (its page in the project, the names of its cards). Pick: the round 1 board of the Acme example; refine: the board derived from it (one card);
    style: the committed fixture, the style board template filled (the motion board's own tests are in tests/test_motion_board.py)."""
    if kind == "pick":
        return "rounds/r1/board.html", ("Compass", "Lantern", "Keystone")
    if kind == "refine":
        make_r2_board(proj)
        return "rounds/r2/board.html", ("Compass",)
    page = proj / "rounds" / "r0" / "board.html"
    page.parent.mkdir(parents=True)
    page.write_text(STYLE_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    return "rounds/r0/board.html", ("Harbor", "Ember", "Quarry", "Meadow")


def votes(proj: Path) -> dict:
    return next(x for x in report(proj, "board-lint")["results"] if x["id"] == "page:votes")


@pytest.mark.parametrize("kind", ["pick", "refine", "style"])
def test_a_board_whose_cards_each_have_a_vote_group_of_their_own_passes_page_votes(proj, kind):
    page, names = make_board(proj, kind)
    r = lint(proj, page)
    assert r.returncode == 0, r.stdout
    got = votes(proj)
    assert got["status"] == "pass" and got["detail"] == f"{len(names)} vote group(s), one per card: " + ", ".join(f"vote-{n}" for n in names), got


@pytest.mark.parametrize("kind", ["pick", "refine", "style"])
def test_a_card_whose_radios_are_not_named_after_it_fails_page_votes_naming_the_card_and_the_fix(proj, kind):
    """The Acme example once wrote vote-compass for the card Compass, and the templates vote-one for every card: the name is `vote-` and the card's name as written, a group of its own."""
    page, names = make_board(proj, kind)
    board = proj / page
    first = names[0]
    for wrong in ("vote-one", f"vote-{first.lower()}", "vote", f"{first}"):
        before = mutate(board, f'name="vote-{first}"', f'name="{wrong}"', count=3)                  # keep, drop and unsure of the card
        r = lint(proj, page)
        assert r.returncode == 1 and "page:votes" in failing(report(proj, "board-lint")), (wrong, r.stdout)
        got = votes(proj)
        assert got["status"] == "fail" and f'{first}: its radios must all be named "vote-{first}" (found: "{wrong}")' in got["detail"], (wrong, got["detail"])
        assert f'name="vote-{first}" on the card {first}' in got["detail"], got["detail"]            # the fix
        board.write_text(before)
    assert lint(proj, page).returncode == 0
    mutate(board, f'<input type="radio" name="vote-{first}" value="drop">', '<input type="radio" value="drop">')       # one radio with no name at all is no group
    r = lint(proj, page)
    assert r.returncode == 1 and f'{first}: its radios must all be named "vote-{first}" (found: a radio with no name)' in votes(proj)["detail"], votes(proj)["detail"]


@pytest.mark.parametrize("kind", ["pick", "style"])
def test_cards_that_share_a_radio_name_are_one_group_and_fail_page_votes_naming_them(proj, kind):
    """A radio name is one group for the whole page: a card copied with the name of the one it came from (every card of the 0.3.6 templates said vote-one) clears the vote of the other."""
    page, names = make_board(proj, kind)
    board = proj / page
    a, b = names[:2]
    mutate(board, f'name="vote-{b}"', f'name="vote-{a}"', count=3)                                   # the second card was copied and not renamed
    r = lint(proj, page)
    assert r.returncode == 1 and "page:votes" in failing(report(proj, "board-lint")), r.stdout
    why = votes(proj)["detail"]
    assert f'{a} and {b} share the radio name "vote-{a}", so they are one vote group and a vote on one clears the vote on the others' in why, why
    assert f'{b}: its radios must all be named "vote-{b}" (found: "vote-{a}")' in why and f'{a}: its radios' not in why, why
    for n in names[2:]:                                                                              # and every card the same, as the 0.3.6 templates made them
        mutate(board, f'name="vote-{n}"', f'name="vote-{a}"', count=3)
    mutate(board, f'name="vote-{a}"', 'name="vote-one"', count=3 * len(names))
    assert lint(proj, page).returncode == 1
    why = votes(proj)["detail"]
    assert f'{", ".join(names[:-1])} and {names[-1]} share the radio name "vote-one"' in why and f'{a}: its radios must all be named "vote-{a}" (found: "vote-one")' in why, why


def test_two_votes_that_carry_the_same_name_share_a_group_even_when_each_is_named_right(proj):
    """A card copied whole, its name unchanged: both fieldsets say Compass and both name their radios vote-Compass, which is one group."""
    page, names = make_board(proj, "pick")
    board = proj / page
    mutate(board, 'data-vote="Lantern"', 'data-vote="Compass"')
    mutate(board, 'name="vote-Lantern"', 'name="vote-Compass"', count=3)
    r = lint(proj, page)
    assert r.returncode == 1 and "page:votes" in failing(report(proj, "board-lint")), r.stdout
    why = votes(proj)["detail"]
    assert 'Compass (vote #1) and Compass (vote #2) share the radio name "vote-Compass"' in why and "its radios must all be named" not in why, why


def test_a_board_with_no_vote_gets_an_info_row_not_a_failure(proj):
    page, _ = make_board(proj, "pick")
    board = proj / page
    text = board.read_text(encoding="utf-8")
    board.write_text(re.sub(r'<fieldset class="vote" data-vote="[^"]+">.*?</fieldset>', "", text, flags=re.S), encoding="utf-8")
    assert board.read_text(encoding="utf-8") != text and 'data-vote="' not in board.read_text(encoding="utf-8")
    r = lint(proj, page)
    got = votes(proj)
    assert r.returncode == 0 and got["status"] == "info" and got["detail"] == "no vote on this page: a vote (keep / drop / unsure per card) is optional", (r.stdout, got)


def test_the_acme_example_names_the_radios_of_each_card_as_the_card_is_written():
    """The worked example is a finished pick board: its votes pass the row, so the name of each group is `vote-` and the card's name as it stands in data-vote and data-name."""
    from boardpage import parse_dom
    root = parse_dom((ROOT / "skills" / "brand-creator" / "references" / "examples" / "acme" / "rounds" / "r1" / "board.html").read_text(encoding="utf-8"))
    cards = [n.attrs["data-name"] for n in root.walk() if n.attrs.get("data-section") == "direction"]
    groups = {n.attrs["data-vote"]: {r.attrs.get("name") for r in n.walk() if r.tag == "input"} for n in root.walk() if "data-vote" in n.attrs}
    assert cards == ["Compass", "Lantern", "Keystone"] and groups == {c: {f"vote-{c}"} for c in cards}, groups


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


# ---------------------------------------------------------------- style board (round 0) and the G1s requirement

STYLE_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "style-board-filled.html"


@pytest.fixture
def style(proj):
    page = proj / "rounds" / "r0" / "board.html"
    page.parent.mkdir(parents=True)
    page.write_text(STYLE_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
    return page


def test_filled_style_board_passes(proj, style):
    r = lint(proj, "rounds/r0/board.html")
    assert r.returncode == 0, r.stdout
    ids = {x["id"]: x["status"] for x in report(proj, "board-lint")["results"]}
    assert ids["territories:count"] == "pass" and ids["section:audience"] == "pass" and ids["territory:Harbor:references"] == "pass"
    assert ids["page:data-board"] == "pass"


@pytest.mark.parametrize("section", ["audience", "surfaces", "norm", "none-of-these", "my-call", "questions", "reply"])
def test_style_board_missing_section_fails(proj, style, section):
    mutate(style, f'data-section="{section}"', f'data-removed="{section}"')
    r = lint(proj, "rounds/r0/board.html")
    assert r.returncode == 1, r.stdout
    assert f"section:{section}" in failing(report(proj, "board-lint"))


def test_style_board_needs_four_territories(proj, style):
    text = style.read_text()
    style.write_text(text.replace('data-section="territory" data-name="Meadow"', 'data-x="territory" data-name="Meadow"'))
    assert style.read_text() != text
    r = lint(proj, "rounds/r0/board.html")
    assert r.returncode == 1 and "territories:count" in failing(report(proj, "board-lint")), r.stdout


def test_style_territory_needs_an_idea(proj, style):
    text = style.read_text()
    style.write_text(text.replace('data-field="idea"', 'data-x="idea"', 1))
    assert style.read_text() != text
    r = lint(proj, "rounds/r0/board.html")
    assert r.returncode == 1 and "territory:Harbor:idea" in failing(report(proj, "board-lint")), r.stdout


def test_style_territory_needs_three_linked_references_with_a_take(proj, style):
    text = style.read_text()
    style.write_text(text.replace('<a href="https://example.com/reference">', "<a>", 1))  # one reference loses its link
    r = lint(proj, "rounds/r0/board.html")
    assert r.returncode == 1 and "territory:Harbor:references" in failing(report(proj, "board-lint")), r.stdout
    style.write_text(text.replace('data-field="take"', 'data-x="take"', 1))  # one reference loses its "take"
    r = lint(proj, "rounds/r0/board.html")
    assert r.returncode == 1 and "territory:Harbor:references" in failing(report(proj, "board-lint")), r.stdout


def test_style_board_unfilled_marker_and_question_rules(proj, style):
    mutate(style, "<h1>Acme: which look?</h1>", "<h1>Acme: which look?</h1><p>[[fill: lede]]</p>")
    r = lint(proj, "rounds/r0/board.html")
    assert r.returncode == 1 and "page:unfilled" in failing(report(proj, "board-lint")), r.stdout
    style.write_text(STYLE_FIXTURE.read_text(encoding="utf-8"))
    mutate(style, '<li data-option="a" data-recommended="true"><label><input type="radio" name="q2"', '<li data-option="a"><label><input type="radio" name="q2"')
    r = lint(proj, "rounds/r0/board.html")
    assert r.returncode == 1 and "question:2:options" in failing(report(proj, "board-lint")), r.stdout


def test_style_board_must_be_round_zero_and_round_zero_must_be_style(proj, style):
    mutate(style, 'data-round="0" data-board="style"', 'data-round="0" data-board="pick"')
    r = lint(proj, "rounds/r0/board.html")
    assert r.returncode == 1 and "page:data-board" in failing(report(proj, "board-lint")), r.stdout
    style.write_text(STYLE_FIXTURE.read_text(encoding="utf-8"))
    other = proj / "rounds" / "r1" / "board.html"
    other.write_text(style.read_text(encoding="utf-8").replace('data-round="0"', 'data-round="1"'), encoding="utf-8")
    r = lint(proj)
    assert r.returncode == 1 and "page:data-board" in failing(report(proj, "board-lint")), r.stdout


def test_style_board_template_carries_the_vocabulary_and_fails_until_filled(proj):
    src = (ROOT / "templates" / "style-board.html").read_text()
    for sid in ("audience", "surfaces", "norm", "territory", "none-of-these", "my-call", "questions", "reply"):
        assert f'data-section="{sid}"' in src, sid
    for fid in ("idea", "per-item", "references", "take", "thumb", "recommendation", "critique"):
        assert f'data-field="{fid}"' in src, fid
    assert 'data-board="style"' in src and 'data-round="0"' in src
    dest = proj / "rounds" / "r0" / "board.html"
    dest.parent.mkdir(parents=True)
    dest.write_text(src)
    r = lint(proj, "rounds/r0/board.html")
    assert r.returncode == 1 and "page:unfilled" in failing(report(proj, "board-lint")), r.stdout


def test_the_committed_filled_fixture_is_the_template_filled(proj):
    """tests/fixtures/style-board-filled.html is derived from templates/style-board.html: when the template changes, regenerate it
    (Path('tests/fixtures/style-board-filled.html').write_text(helpers.fill_style_board(Path('templates/style-board.html').read_text()))),
    or the lint tests below would run against a page the template no longer makes."""
    template = (ROOT / "templates" / "style-board.html").read_text(encoding="utf-8")
    assert STYLE_FIXTURE.read_text(encoding="utf-8") == fill_style_board(template)


def test_the_template_is_ready_for_thumbnails_multi_pick_and_outlined_swatches():
    src = (ROOT / "templates" / "style-board.html").read_text(encoding="utf-8")
    # an optional thumbnail slot per reference: an inlined image with alt text and a caption that says it is for private research
    assert src.count('<img data-field="thumb" src="[[fill: data:image') == 3
    assert len(re.findall(r"<figcaption>[^<]*shown for private research</figcaption>", src)) == 3
    assert len(re.findall(r'<img data-field="thumb"[^>]* alt="\[\[fill:', src)) == 3
    assert not re.search(r"""<img[^>]*\bsrc="(?:https?:)?//""", src), "a thumbnail is never linked from the net"
    # question 1 is multi-pick: checkboxes, and the reply script lists every ticked style
    q1 = src[src.index('data-n="1"'):src.index('data-n="2"')]
    assert 'data-multi="true"' in q1 and 'type="checkbox" name="q1"' in q1 and 'type="radio"' not in q1
    assert q1.count('type="checkbox"') == 5 and 'class="none-pick"' in q1
    assert 'join(", ")' in src and "none-pick" in src.split("<script>")[1]
    # the other questions stay single-pick
    assert 'type="radio" name="q2"' in src
    # a 1 px outline on every palette swatch
    assert re.search(r"\.mood i\{[^}]*outline:1px solid var\(--outline\)", src) and "--outline:" in src


def _thumbs_in(proj):
    return {x["id"]: x["status"] for x in report(proj, "board-lint")["results"] if ":thumb:" in x["id"] or x["id"].startswith("thumb:")}


def test_a_filled_thumbnail_passes_and_the_slot_is_optional(proj, style):
    assert lint(proj, "rounds/r0/board.html").returncode == 0
    thumbs = _thumbs_in(proj)
    assert len(thumbs) == 12 and set(thumbs.values()) == {"pass"}, thumbs   # 4 territories x 3 references
    text = style.read_text(encoding="utf-8")
    bare = re.sub(r'\s*<figure class="thumb">.*?</figure>', "", text, flags=re.S)
    assert bare != text and "data-field=\"thumb\"" not in bare
    style.write_text(bare, encoding="utf-8")
    assert lint(proj, "rounds/r0/board.html").returncode == 0 and _thumbs_in(proj) == {}


BAD_THUMBS = {   # what is wrong -> an edit of the first thumbnail's <img> tag (the first reference of the first territory, Harbor)
    "a linked image": lambda s: re.sub(r'src="[^"]*"', 'src="https://upload.example.org/mark.png"', s),
    "a link that only mentions data:": lambda s: re.sub(r'src="[^"]*"', 'src="https://upload.example.org/mark.png?x=data:image/png;base64,AAAA"', s),
    "a protocol-relative link": lambda s: re.sub(r'src="[^"]*"', 'src="//upload.example.org/mark.png"', s),
    "a relative file": lambda s: re.sub(r'src="[^"]*"', 'src="research/style-thumbs/mark.png"', s),
    "a data URI that is not an image": lambda s: re.sub(r'src="[^"]*"', 'src="data:text/html;base64,PGI+"', s),
    "no src": lambda s: re.sub(r' src="[^"]*"', "", s),
    "a srcset that asks the network": lambda s: s.replace('<img data-field="thumb"', '<img data-field="thumb" srcset="https://upload.example.org/mark@2x.png 2x"'),
    "no alt text": lambda s: re.sub(r' alt="[^"]*"', "", s),
    "empty alt text": lambda s: re.sub(r' alt="[^"]*"', ' alt=""', s),
    "blank alt text": lambda s: re.sub(r' alt="[^"]*"', ' alt="   "', s),
    "the field on a span": lambda s: s.replace("<img", "<span", 1),
}


@pytest.mark.parametrize("what", sorted(BAD_THUMBS))
def test_a_bad_thumbnail_fails_with_its_territory_and_number(proj, style, what):
    text = style.read_text(encoding="utf-8")
    m = re.search(r'<img data-field="thumb"[^>]*>', text)
    assert m
    edited = BAD_THUMBS[what](m.group(0))
    assert edited != m.group(0), what
    style.write_text(text[:m.start()] + edited + text[m.end():], encoding="utf-8")
    r = lint(proj, "rounds/r0/board.html")
    assert r.returncode == 1, (what, r.stdout)
    bad = [i for i in failing(report(proj, "board-lint")) if ":thumb:" in i]
    assert bad == ["territory:Harbor:thumb:1"], (what, bad)
    assert "thumbnail" in r.stdout


def test_a_thumbnail_outside_the_territories_is_checked_too(proj, style):
    mutate(style, '<section class="block" id="norm" data-section="norm">',
           '<section class="block" id="norm" data-section="norm"><img data-field="thumb" src="https://example.org/norm.png" alt="a norm mark">')
    r = lint(proj, "rounds/r0/board.html")
    assert r.returncode == 1 and "thumb:1" in failing(report(proj, "board-lint")), r.stdout


def _first_thumb_figure(text):
    m = re.search(r'<figure class="thumb">.*?</figure>', text, re.S)
    assert m
    return m


BAD_CAPTIONS = {   # what is wrong -> an edit of the first thumbnail's <figure> (the first reference of the first territory, Harbor)
    "no figure around the image": lambda fig: re.sub(r"</?figure[^>]*>", "", fig),
    "no figcaption": lambda fig: re.sub(r"<figcaption>.*?</figcaption>", "", fig, flags=re.S),
    "an empty figcaption": lambda fig: re.sub(r"<figcaption>.*?</figcaption>", "<figcaption></figcaption>", fig, flags=re.S),
    "a blank figcaption": lambda fig: re.sub(r"<figcaption>.*?</figcaption>", "<figcaption>  \n  </figcaption>", fig, flags=re.S),
    "a placeholder figcaption": lambda fig: re.sub(r"<figcaption>.*?</figcaption>", "<figcaption>TODO</figcaption>", fig, flags=re.S),
    "a figcaption with only an image": lambda fig: re.sub(r"<figcaption>.*?</figcaption>", '<figcaption><img src="data:image/png;base64,AAAA" alt="x"></figcaption>', fig, flags=re.S),
}


@pytest.mark.parametrize("what", sorted(BAD_CAPTIONS))
def test_a_thumbnail_needs_a_figure_with_a_non_empty_caption(proj, style, what):
    text = style.read_text(encoding="utf-8")
    m = _first_thumb_figure(text)
    edited = BAD_CAPTIONS[what](m.group(0))
    assert edited != m.group(0), what
    style.write_text(text[:m.start()] + edited + text[m.end():], encoding="utf-8")
    r = lint(proj, "rounds/r0/board.html")
    assert r.returncode == 1, (what, r.stdout)
    bad = [i for i in failing(report(proj, "board-lint")) if ":thumb:" in i]
    assert bad == ["territory:Harbor:thumb:1"], (what, bad)
    assert "figcaption" in r.stdout, r.stdout


GOOD_CAPTIONS = {   # the words are the author's: any language, no particular phrase
    "Polish, no English words": "Znak: Atelier Harbor · źródło: strona prasowa marki · do prywatnych badań",
    "English without the template phrase": "Harbor Co.: logo from their press page",
    "a caption with markup inside": "<b>Harbor Co.</b> <a href=\"https://example.com/press\">press page</a>",
}


@pytest.mark.parametrize("what", sorted(GOOD_CAPTIONS))
def test_a_caption_in_any_words_passes(proj, style, what):
    text = style.read_text(encoding="utf-8")
    m = _first_thumb_figure(text)
    edited = re.sub(r"<figcaption>.*?</figcaption>", lambda _m: f"<figcaption>{GOOD_CAPTIONS[what]}</figcaption>", m.group(0), flags=re.S)
    assert edited != m.group(0) and "shown for private research" not in edited
    style.write_text(text[:m.start()] + edited + text[m.end():], encoding="utf-8")
    r = lint(proj, "rounds/r0/board.html")
    assert r.returncode == 0, (what, r.stdout)
    assert _thumbs_in(proj)["territory:Harbor:thumb:1"] == "pass"


def _in_norm(img_html):
    return ('<section class="block" id="norm" data-section="norm">', '<section class="block" id="norm" data-section="norm">' + img_html)


BAD_IMAGES = {   # an <img> or <source> that is not a thumbnail -> markup put in the norm section
    "a linked image": '<img src="https://upload.example.org/mark.png" alt="a mark">',
    "a protocol-relative link": '<img src="//upload.example.org/mark.png" alt="a mark">',
    "a relative file": '<img src="research/style-thumbs/mark.png" alt="a mark">',
    "a link that only mentions data:": '<img src="https://upload.example.org/mark.png?x=data:image/png;base64,AAAA" alt="a mark">',
    "a data URI that is not an image": '<img src="data:text/html;base64,PGI+" alt="a mark">',
    "no src": '<img alt="a mark">',
    "an empty src": '<img src="  " alt="a mark">',
    "a linked srcset on an img": '<img src="data:image/png;base64,AAAA" srcset="https://upload.example.org/mark@2x.png 2x" alt="a mark">',
    "a relative srcset on an img": '<img src="data:image/png;base64,AAAA" srcset="mark.png 1x, mark@2x.png 2x" alt="a mark">',
    "a linked srcset on a source": '<picture><source srcset="https://upload.example.org/mark.webp"><img src="data:image/png;base64,AAAA" alt="a mark"></picture>',
    "one bad candidate among inlined ones": '<img src="data:image/png;base64,AAAA" srcset="data:image/png;base64,AAAA 1x, //cdn.example.org/mark@2x.png 2x" alt="a mark">',
    "a bad candidate after a width descriptor": '<picture><source srcset="data:image/png;base64,AAAA 320w, /big.png 960w"><img src="data:image/png;base64,AAAA" alt="a mark"></picture>',
}


@pytest.mark.parametrize("what", sorted(BAD_IMAGES))
def test_any_image_on_a_style_board_must_be_inlined(proj, style, what):
    old, new = _in_norm(BAD_IMAGES[what])
    mutate(style, old, new)
    r = lint(proj, "rounds/r0/board.html")
    assert r.returncode == 1, (what, r.stdout)
    assert "images:inlined" in failing(report(proj, "board-lint")), (what, failing(report(proj, "board-lint")))
    assert [i for i in failing(report(proj, "board-lint")) if ":thumb:" in i] == []   # a plain image has no thumbnail result
    assert "not inlined" in r.stdout


def test_inlined_images_pass_with_or_without_srcset_and_sources(proj, style):
    old, new = _in_norm('<picture><source srcset="data:image/webp;base64,AAAA 1x, data:image/webp;base64,BBBB 2x" type="image/webp">'
                        '<img src="data:image/png;base64,AAAA" srcset="data:image/png;base64,AAAA 1x, data:image/png;base64,BBBB 2x" alt="a mark"></picture>'
                        '<img src="data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27/%3E" alt="a mark">')
    mutate(style, old, new)
    r = lint(proj, "rounds/r0/board.html")
    assert r.returncode == 0, r.stdout
    result = next(x for x in report(proj, "board-lint")["results"] if x["id"] == "images:inlined")
    assert result["status"] == "pass"


REPEATED = {   # a repeated attribute counts by its FIRST copy, as in a browser -> (markup in the norm section, does images:inlined fail?)
    "a linked src first, an inlined one after": ('<img src="https://x.example.org/mark.png" src="data:image/png;base64,AAAA" alt="a mark">', True),
    "an inlined src first, a linked one after": ('<img src="data:image/png;base64,AAAA" src="https://x.example.org/mark.png" alt="a mark">', False),
    "a linked srcset first": ('<img src="data:image/png;base64,AAAA" srcset="https://x.example.org/a.png 2x" srcset="data:image/png;base64,AAAA 2x" alt="a mark">', True),
    "an inlined srcset first": ('<img src="data:image/png;base64,AAAA" srcset="data:image/png;base64,AAAA 2x" srcset="https://x.example.org/a.png 2x" alt="a mark">', False),
}


@pytest.mark.parametrize("what", sorted(REPEATED))
def test_a_repeated_attribute_counts_by_its_first_copy(proj, style, what):
    markup, fails = REPEATED[what]
    old, new = _in_norm(markup)
    mutate(style, old, new)
    r = lint(proj, "rounds/r0/board.html")
    assert (r.returncode == 1) is fails, (what, r.stdout)
    assert ("images:inlined" in failing(report(proj, "board-lint"))) is fails, (what, failing(report(proj, "board-lint")))


def test_a_repeated_section_attribute_counts_by_its_first_copy_too(proj, style):
    mutate(style, '<section class="block" id="norm" data-section="norm">', '<section class="block" id="norm" data-section="elsewhere" data-section="norm">')
    r = lint(proj, "rounds/r0/board.html")
    assert r.returncode == 1 and "section:norm" in failing(report(proj, "board-lint")), r.stdout


def test_a_style_board_without_other_images_passes_the_image_check(proj, style):
    assert lint(proj, "rounds/r0/board.html").returncode == 0
    assert next(x for x in report(proj, "board-lint")["results"] if x["id"] == "images:inlined")["status"] == "pass"


def test_the_image_check_is_for_style_boards_only(proj):
    board = proj / "rounds" / "r1" / "board.html"
    mutate(board, '<section class="block" id="core" data-section="strategy-core">',
           '<section class="block" id="core" data-section="strategy-core"><img src="https://example.org/photo.png" alt="a photo">')
    assert lint(proj).returncode == 0
    assert "images:inlined" not in {x["id"] for x in report(proj, "board-lint")["results"]}


def test_a_thumbnail_with_a_linked_srcset_still_gets_its_own_result_only(proj, style):
    text = style.read_text(encoding="utf-8")
    m = re.search(r'<img data-field="thumb"[^>]*>', text)
    edited = m.group(0).replace('<img data-field="thumb"', '<img data-field="thumb" srcset="https://upload.example.org/mark@2x.png 2x"')
    style.write_text(text[:m.start()] + edited + text[m.end():], encoding="utf-8")
    r = lint(proj, "rounds/r0/board.html")
    assert r.returncode == 1 and failing(report(proj, "board-lint")) == ["territory:Harbor:thumb:1"], r.stdout


LABEL_NAMES = [   # a label word alone, or with a number, one letter or a roman numeral (after a space, "-" or "#", or a number right after)
    "Style 1", "Style 2", "style", "Option 2", "option", "Direction 3", "Variant", "Concept 4", "Route 5", "STYLE 6",
    "Territory 1", "Style A", "Option B", "Look 2", "Mood 3", "Direction II", "Option #2", "Style-3",
    "Territory", "Look", "Mood", "Idea", "Version 2", "Choice C", "Idea #3", "Style - 4", "Option2", "Look iv", "Mood XII", "version  7", "Territory #B",
]
WORD_NAMES = ["Woodcut", "Looker", "Moody", "Stylish", "Optional", "Routes", "Harbour", "Łąka", "Ogród",
              "Styles", "Ideas", "Looks", "Moods", "Choices", "Versions", "Territories", "Ideal", "Lookout", "Mood Indigo", "Look Book"]


@pytest.mark.parametrize("name", LABEL_NAMES)
def test_territory_names_must_not_be_generic_labels(proj, style, name):
    mutate(style, 'data-section="territory" data-name="Meadow"', f'data-section="territory" data-name="{name}"')
    r = lint(proj, "rounds/r0/board.html")
    assert r.returncode == 1, (name, r.stdout)
    assert f"territory:{name}:name" in failing(report(proj, "board-lint")), (name, failing(report(proj, "board-lint")))


@pytest.mark.parametrize("name", WORD_NAMES)
def test_word_names_that_only_start_like_a_label_pass(proj, style, name):
    mutate(style, 'data-section="territory" data-name="Meadow"', f'data-section="territory" data-name="{name}"')
    assert lint(proj, "rounds/r0/board.html").returncode == 0, name


@pytest.mark.parametrize("name", ["Option 2", "Style 1", "Direction"] + LABEL_NAMES[10:])
def test_direction_names_use_the_same_rule(proj, name):
    board = proj / "rounds" / "r1" / "board.html"
    mutate(board, 'data-name="Compass"', f'data-name="{name}"')
    r = lint(proj)
    assert r.returncode == 1 and f"direction:{name}:name" in failing(report(proj, "board-lint")), r.stdout


@pytest.mark.parametrize("name", ["Harbor", "Quarry", "Woodcut", "Looker", "Moody", "Routes"])
def test_direction_word_names_pass(proj, name):
    board = proj / "rounds" / "r1" / "board.html"
    mutate(board, 'data-name="Compass"', f'data-name="{name}"')
    mutate(board, 'data-direction="Compass"', f'data-direction="{name}"')   # every direction stays placed on the map
    r = lint(proj)
    assert r.returncode == 0, (name, r.stdout)


def _make_round_page(proj, n, *, board):
    """rounds/r<n>/board.html from the style fixture (board='style') or round 1's page (board='pick' with a map that shows the failed round)."""
    page = proj / "rounds" / f"r{n}" / "board.html"
    page.parent.mkdir(parents=True, exist_ok=True)
    if board == "style":
        src = STYLE_FIXTURE.read_text(encoding="utf-8").replace('data-round="0"', f'data-round="{n}"')
    else:
        src = (proj / "rounds" / "r1" / "board.html").read_text(encoding="utf-8").replace('data-round="1"', f'data-round="{n}"')
        src = src.replace('<span class="axis x0">', '<span data-field="failed-round">Round 1 sat in the middle of the category norm.</span><span class="axis x0">', 1)
        extra = (
            '<section class="block" data-section="what-changed"><h2>What changed</h2><p>Everything: new territories after a full rejection.</p></section>\n'
            '<section class="block" data-section="weak-points"><h2>Weak points</h2><p>The new territories are untested at 16 px.</p></section>\n'
            '<section class="block" data-section="losers"><h2>Kept as losers</h2>'
            '<div data-section="loser" data-name="Compass"><p data-field="reason">Round 1 was rejected as a whole.</p></div></section>\n')
        marker = '<section class="block" id="directions">'
        assert src.count(marker) == 1
        src = src.replace(marker, extra + marker)
    page.write_text(src, encoding="utf-8")
    return page


def _list_reset(proj, *rounds):
    """reset_rounds is exactly these rounds."""
    assert bc("state", "--set", "reset_rounds=[" + ", ".join(str(n) for n in rounds) + "]", project=proj).returncode == 0


def _g1s_round(proj):
    """The g1s_round that state holds, as a number, or None when the key is not there."""
    r = bc("state", "--get", "g1s_round", project=proj)
    return int(r.stdout.strip()) if r.returncode == 0 else None


def test_a_reset_round_may_hold_a_style_board_but_an_ordinary_round_may_not(proj):
    _make_round_page(proj, 3, board="style")
    r = lint(proj, "rounds/r3/board.html")
    assert r.returncode == 1 and "page:data-board" in failing(report(proj, "board-lint")), r.stdout   # not listed in reset_rounds
    assert "reset_rounds" in r.stdout
    _list_reset(proj, 3)
    r = lint(proj, "rounds/r3/board.html")
    assert r.returncode == 0, r.stdout   # the style research runs again before the new territories
    ids = {x["id"]: x["status"] for x in report(proj, "board-lint")["results"]}
    assert ids["page:data-board"] == "pass" and ids["territories:count"] == "pass" and "section:positioning-map" not in ids
    # it is still a style board: the style rules apply in the reset round
    page = proj / "rounds" / "r3" / "board.html"
    mutate(page, 'data-section="norm"', 'data-removed="norm"')
    assert lint(proj, "rounds/r3/board.html").returncode == 1 and "section:norm" in failing(report(proj, "board-lint"))


def test_a_refine_board_is_still_refused_in_a_reset_round_and_a_style_board_in_round_1_unless_it_is_a_reset_round(proj):
    _make_round_page(proj, 3, board="style")
    _list_reset(proj, 3)
    page = proj / "rounds" / "r3" / "board.html"
    mutate(page, 'data-board="style"', 'data-board="refine"')
    r = lint(proj, "rounds/r3/board.html")
    assert r.returncode == 1 and "page:data-board" in failing(report(proj, "board-lint"))
    assert "style board when the style research runs again" in r.stdout
    one = proj / "rounds" / "r1" / "board.html"
    one.write_text(STYLE_FIXTURE.read_text(encoding="utf-8").replace('data-round="0"', 'data-round="1"'), encoding="utf-8")
    _list_reset(proj)
    r = lint(proj)
    assert r.returncode == 1 and "page:data-board" in failing(report(proj, "board-lint")) and "or a round listed in reset_rounds" in r.stdout


def test_round_0_must_be_a_style_board_whatever_reset_rounds_says(proj, style):
    mutate(style, 'data-board="style"', 'data-board="pick"')
    r = lint(proj, "rounds/r0/board.html")
    assert r.returncode == 1 and "page:data-board" in failing(report(proj, "board-lint")) and "round 0 is the style board" in r.stdout


LATER_PICK = "a pick board belongs to round 1 or to a round listed in reset_rounds (after a full rejection); later rounds are refine boards"


def _kind_detail(proj):
    return next(x for x in report(proj, "board-lint")["results"] if x["id"] == "page:data-board")["detail"]


def test_a_pick_board_in_a_later_round_that_is_not_listed_in_reset_rounds_fails(proj):
    """The lint used to take a pick board in any round, and the re-armed style gate only looked at rounds listed in reset_rounds: a
    pick board in round 2 that nobody listed passed on the old pick. Later rounds are refine boards; a pick board there is a reset."""
    _make_round_page(proj, 2, board="pick")                      # G1s was recorded by the fixture, reset_rounds is empty
    r = lint(proj, "rounds/r2/board.html")
    assert r.returncode == 1, r.stdout
    assert failing(report(proj, "board-lint")) == ["page:data-board"], failing(report(proj, "board-lint"))
    assert _kind_detail(proj) == LATER_PICK and LATER_PICK in r.stdout
    for rnds in ([3], [1], [4, 5]):                              # listing some other round does not help
        _list_reset(proj, *rnds)
        r = lint(proj, "rounds/r2/board.html")
        assert r.returncode == 1 and failing(report(proj, "board-lint")) == ["page:data-board"] and _kind_detail(proj) == LATER_PICK, rnds
    _make_round_page(proj, 5, board="pick")                      # and so on for any later round
    _list_reset(proj, 2)
    r = lint(proj, "rounds/r5/board.html")
    assert r.returncode == 1 and _kind_detail(proj) == LATER_PICK and "page:data-board" in failing(report(proj, "board-lint"))


def test_a_pick_board_in_a_later_round_passes_the_kind_check_once_the_round_is_listed_and_other_kinds_are_unchanged(proj):
    _make_round_page(proj, 2, board="pick")
    _list_reset(proj, 2)
    r = lint(proj, "rounds/r2/board.html")
    assert "page:data-board" not in failing(report(proj, "board-lint")) and _kind_detail(proj) == "pick"
    assert failing(report(proj, "board-lint")) == ["project:style-gate"], r.stdout     # a reset still needs its new style board (the next tests)
    assert lint(proj).returncode == 0 and _kind_detail(proj) == "pick"              # round 1 stays a pick board
    _list_reset(proj)
    make_r2_board(proj, 3)                                                           # a later round is a refine board
    assert lint(proj, "rounds/r3/board.html").returncode == 0 and _kind_detail(proj) == "refine"


def test_a_reset_round_pick_board_waits_for_the_style_gate_like_round_1(proj):
    """r1 pick (rejected), r2 style (reset), the owner's new pick recorded, r3 pick (reset): G1s must be there, as for round 1."""
    _make_round_page(proj, 2, board="style")
    assert bc("state", "--record", "G1s", "picked Ember", project=proj).returncode == 0
    _make_round_page(proj, 3, board="pick")
    _list_reset(proj, 2, 3)
    r = lint(proj, "rounds/r3/board.html")
    assert r.returncode == 0, r.stdout
    _clear_g1s(proj)
    r = lint(proj, "rounds/r3/board.html")
    assert r.returncode == 1 and "project:style-gate" in failing(report(proj, "board-lint")), r.stdout
    assert "reset_rounds" in r.stdout and "n/a: round 1 drawn before the style step" in r.stdout    # today's text is still there ...
    assert "After a full rejection the style board is required and a skip or an n/a no longer counts" in r.stdout   # ... and says a reset takes neither
    assert bc("state", "--record", "G1s", "picked Ember", project=proj).returncode == 0
    assert lint(proj, "rounds/r3/board.html").returncode == 0
    _clear_g1s(proj)
    assert lint(proj, "rounds/r1/board.html").returncode == 1   # round 1 as before
    r = lint(proj, "rounds/r1/board.html")
    assert "n/a: round 1 drawn before the style step" in r.stdout and "skipped by owner" in r.stdout   # round 1 says how to record a skip or an honest n/a
    assert "After a full rejection" not in r.stdout                                                      # and only a reset round gets the sentence about a rejection
    assert "project:style-gate" in {x["id"] for x in report(proj, "board-lint")["results"]}


def test_the_style_board_of_a_reset_round_needs_no_style_gate(proj):
    _make_round_page(proj, 3, board="style")
    _list_reset(proj, 3)
    _clear_g1s(proj)
    r = lint(proj, "rounds/r3/board.html")
    assert r.returncode == 0, r.stdout
    assert "project:style-gate" not in {x["id"] for x in report(proj, "board-lint")["results"]}


def test_a_refine_board_needs_no_style_gate(proj):
    make_r2_board(proj)
    _clear_g1s(proj)
    assert lint(proj, "rounds/r2/board.html").returncode == 0
    assert "project:style-gate" not in {x["id"] for x in report(proj, "board-lint")["results"]}


# ---- after a full rejection the style gate is armed again: a new style board, and a pick recorded after it

REARM_MESSAGE = "after a full rejection, show a new style board in a reset round before the next pick board"
STALE_MESSAGE = "G1s still holds the pick from before the rejection: record the owner's new pick with state --record G1s"


def _gate_result(proj):
    return next(x for x in report(proj, "board-lint")["results"] if x["id"] == "project:style-gate")


def test_a_reset_pick_board_without_a_new_style_board_fails_even_with_g1s_recorded(proj):
    """The old behaviour: G1s holds the first pick, so a pick board in a reset round passed. Now it needs a new style board first."""
    assert _g1s_round(proj) is None                                 # the fixture records G1s while r1, a pick board, is the only round: no style board yet
    _make_round_page(proj, 2, board="pick")
    _list_reset(proj, 2)
    r = lint(proj, "rounds/r2/board.html")
    assert r.returncode == 1 and "project:style-gate" in failing(report(proj, "board-lint")), r.stdout
    assert REARM_MESSAGE in _gate_result(proj)["detail"] and "the rejected round is r1" in _gate_result(proj)["detail"]
    # a second pick board in a row, with no style board anywhere
    _make_round_page(proj, 3, board="pick")
    _list_reset(proj, 2, 3)
    r = lint(proj, "rounds/r3/board.html")
    assert r.returncode == 1 and REARM_MESSAGE in _gate_result(proj)["detail"], r.stdout


def test_a_style_board_that_is_not_listed_in_reset_rounds_does_not_count(proj):
    _make_round_page(proj, 2, board="style")
    assert bc("state", "--record", "G1s", "picked Ember", project=proj).returncode == 0
    _make_round_page(proj, 3, board="pick")
    _list_reset(proj, 3)                                             # r2 holds a style board, but nobody listed it
    r = lint(proj, "rounds/r3/board.html")
    assert r.returncode == 1 and REARM_MESSAGE in _gate_result(proj)["detail"], r.stdout
    _list_reset(proj, 2, 3)
    assert lint(proj, "rounds/r3/board.html").returncode == 0


def _hand_g1s_round(proj, how):
    """g1s_round in BRAND-STATE.md as an old or a damaged state holds it: 'missing' leaves no key, anything else is the key's value."""
    st = proj / "BRAND-STATE.md"
    text = re.sub(r"(?m)^g1s_round:.*\n", "", st.read_text())
    if how != "missing":
        text = text.replace("\ngates:", f"\ng1s_round: {how}\ngates:", 1)
        assert f"\ng1s_round: {how}\n" in text, how
    st.write_text(text)


@pytest.mark.parametrize("how", ["stale", "missing", "abc", '""', "-1"])
def test_a_new_style_board_with_a_g1s_from_before_it_still_fails(proj, how):
    """r1 pick, r2 style, r3 pick; the owner has not picked on r2 yet, so G1s (and g1s_round, when there is one) are still the first pick's."""
    if how == "stale":                                              # the first pick was made on the style board of round 0, before r2 existed
        _make_round_page(proj, 0, board="style")
        assert bc("state", "--record", "G1s", "picked Harbor", project=proj).returncode == 0 and _g1s_round(proj) == 0
    _make_round_page(proj, 2, board="style")
    _make_round_page(proj, 3, board="pick")
    _list_reset(proj, 2, 3)
    if how != "stale":
        _hand_g1s_round(proj, how)
    r = lint(proj, "rounds/r3/board.html")
    assert r.returncode == 1 and "project:style-gate" in failing(report(proj, "board-lint")), r.stdout
    detail = _gate_result(proj)["detail"]
    assert STALE_MESSAGE in detail, detail
    assert f"g1s_round is {0 if how == 'stale' else 'missing'}" in detail and "r2" in detail, detail


def test_a_g1s_recorded_after_the_new_style_board_passes(proj):
    _make_round_page(proj, 2, board="style")
    _list_reset(proj, 2, 3)
    r = bc("state", "--record", "G1s", "picked Ember + Quarry", project=proj)
    assert r.returncode == 0 and "g1s_round = 2" in r.stdout and _g1s_round(proj) == 2       # r2 holds the highest style board
    _make_round_page(proj, 3, board="pick")
    r = lint(proj, "rounds/r3/board.html")
    assert r.returncode == 0, r.stdout
    gate = _gate_result(proj)
    assert gate["status"] == "pass" and "r2" in gate["detail"] and "r1" in gate["detail"] and "g1s_round 2" in gate["detail"]
    # a pick recorded later still counts (g1s_round >= the style board): r3 is a pick board, so the newest style board is still r2
    assert bc("state", "--record", "G1s", "picked Ember + Quarry", project=proj).returncode == 0 and _g1s_round(proj) == 2
    assert lint(proj, "rounds/r3/board.html").returncode == 0


def test_a_pick_recorded_before_the_new_style_board_is_written_does_not_open_the_next_pick_board(proj):
    """Review case E3b. r1 was rejected and r2 is only a copy of it so far (cp -R rounds/r1 rounds/r2); a pick recorded now came before the
    style board that is written next, and g1s_round (the highest round folder, before) took it for one that came after."""
    shutil.copytree(proj / "rounds" / "r1", proj / "rounds" / "r2")
    assert bc("state", "--record", "G1s", "picked Ember (before the board)", project=proj).returncode == 0
    assert _g1s_round(proj) is None                                  # r2 holds no style board yet
    _make_round_page(proj, 2, board="style")
    _make_round_page(proj, 3, board="pick")
    _list_reset(proj, 2, 3)
    r = lint(proj, "rounds/r3/board.html")
    assert r.returncode == 1 and STALE_MESSAGE in _gate_result(proj)["detail"] and "g1s_round is missing" in _gate_result(proj)["detail"], r.stdout
    assert bc("state", "--record", "G1s", "picked Ember", project=proj).returncode == 0 and _g1s_round(proj) == 2     # recorded after the board
    assert lint(proj, "rounds/r3/board.html").returncode == 0


def test_the_gate_reads_the_round_and_the_kind_from_the_same_element(proj):
    """Review case E10. <html data-board="style"> over <body data-round="2" data-board="pick">: board-lint linted r2 as a pick board while the
    gate read the first tag that said data-board, the html tag, and took r2 for the new style board."""
    page = _make_round_page(proj, 2, board="pick")
    mutate(page, '<html lang="en">', '<html lang="en" data-board="style">')
    _make_round_page(proj, 3, board="pick")
    _list_reset(proj, 2, 3)
    assert bc("state", "--record", "G1s", "picked Ember", project=proj).returncode == 0
    assert _g1s_round(proj) is None                                  # r2 is a pick board: no style board anywhere
    r = lint(proj, "rounds/r3/board.html")
    detail = _gate_result(proj)["detail"]
    assert r.returncode == 1 and REARM_MESSAGE in detail and "the rejected round is r2" in detail, r.stdout
    r = lint(proj, "rounds/r2/board.html")                           # and r2 itself is a pick board in a reset round, as its body says
    assert "page:data-board" not in failing(report(proj, "board-lint")) and _kind_detail(proj) == "pick", r.stdout


def test_a_style_board_whose_round_and_kind_sit_on_the_html_tag_still_counts(proj):
    """The page's own element is the body, or the html tag when the body declares neither: both values come from that one tag."""
    page = _make_round_page(proj, 2, board="style")
    mutate(page, '<html lang="en">', '<html lang="en" data-round="2" data-board="style">')
    mutate(page, '<body data-round="2" data-board="style">', "<body>")
    _make_round_page(proj, 3, board="pick")
    _list_reset(proj, 2, 3)
    assert lint(proj, "rounds/r2/board.html").returncode == 0 and _kind_detail(proj) == "style"
    assert bc("state", "--record", "G1s", "picked Ember", project=proj).returncode == 0 and _g1s_round(proj) == 2
    assert lint(proj, "rounds/r3/board.html").returncode == 0


def _thin_style_board(proj, what):
    page = proj / "rounds" / "r2" / "board.html"
    page.parent.mkdir(parents=True, exist_ok=True)
    if what == "a stub that only says style":
        page.write_text('<!doctype html><html><body data-round="2" data-board="style"></body></html>', encoding="utf-8")
        return 0
    if what == "four named but empty territories":                     # review case E1: only named territories with content count
        body = "".join(f'<div data-section="territory" data-name="{n}"><h3>{n}</h3></div>' for n in ("Meadow", "Harbor", "Ember", "Quarry"))
        page.write_text(f'<!doctype html><html><body data-round="2" data-board="style">{body}</body></html>', encoding="utf-8")
        return 0
    page.write_text(STYLE_FIXTURE.read_text(encoding="utf-8").replace('data-round="0"', 'data-round="2"'), encoding="utf-8")
    mutate(page, 'data-section="territory" data-name="Meadow"', 'data-x="territory" data-name="Meadow"')
    return 3


@pytest.mark.parametrize("what", ["a stub that only says style", "four named but empty territories", "a style board one territory short"])
def test_a_style_board_with_too_few_territories_does_not_unlock_the_next_pick_board(proj, what):
    """Review case E9. A page that only says data-board="style" satisfied the gate of the pick board after it, though its own lint fails."""
    shown = _thin_style_board(proj, what)
    _make_round_page(proj, 3, board="pick")
    _list_reset(proj, 2, 3)
    assert bc("state", "--record", "G1s", "picked Ember", project=proj).returncode == 0
    assert _g1s_round(proj) is None                                  # it does not count for g1s_round either
    assert lint(proj, "rounds/r2/board.html").returncode == 1 and "territories:count" in failing(report(proj, "board-lint"))
    r = lint(proj, "rounds/r3/board.html")
    detail = _gate_result(proj)["detail"]
    assert r.returncode == 1 and REARM_MESSAGE in detail, r.stdout
    assert f"r2 has {shown} of the 4 territories a style board needs" in detail and "the rejected round is r1" in detail, detail
    _make_round_page(proj, 2, board="style")                         # four territories are enough
    assert bc("state", "--record", "G1s", "picked Ember", project=proj).returncode == 0 and _g1s_round(proj) == 2
    assert lint(proj, "rounds/r3/board.html").returncode == 0


def test_a_copied_style_board_does_not_count_until_its_page_declares_its_own_round(proj):
    """Review case D1. cp -R rounds/r0 rounds/r2 keeps data-round="0": the copy counted as r2's style board, so a pick recorded on it
    (g1s_round 2) opened the r3 pick board on the first style pick."""
    _make_round_page(proj, 0, board="style")
    shutil.copytree(proj / "rounds" / "r0", proj / "rounds" / "r2")
    _list_reset(proj, 2, 3)
    assert bc("state", "--record", "G1s", "picked Ember", project=proj).returncode == 0
    assert _g1s_round(proj) == 0                                     # the copy in r2 still declares round 0
    _make_round_page(proj, 3, board="pick")
    r = lint(proj, "rounds/r3/board.html")
    detail = _gate_result(proj)["detail"]
    assert r.returncode == 1 and REARM_MESSAGE in detail and 'r2 declares data-round="0" (a copied page)' in detail, r.stdout
    _make_round_page(proj, 2, board="style")                         # the style board written for round 2
    assert bc("state", "--record", "G1s", "picked Ember", project=proj).returncode == 0 and _g1s_round(proj) == 2
    assert lint(proj, "rounds/r3/board.html").returncode == 0


def test_a_round_flag_that_contradicts_the_folder_is_refused(proj):
    """Review case A1. board-lint rounds/r2/board.html --round 1 linted an unlisted r2 pick board as round 1, and it passed."""
    _make_round_page(proj, 2, board="pick")
    r = lint(proj, "rounds/r2/board.html", "--round", "1")
    assert r.returncode == 2 and "--round 1" in r.stderr and "rounds/r2/" in r.stderr, (r.stdout, r.stderr)
    r = lint(proj, "rounds/r2/board.html", "--round", "2")          # the same number as the folder is fine
    assert r.returncode == 1 and _kind_detail(proj) == LATER_PICK, r.stdout


def test_the_round_1_pick_board_keeps_the_old_rule_whatever_g1s_round_says(proj):
    assert lint(proj).returncode == 0
    _hand_g1s_round(proj, "missing")
    assert lint(proj).returncode == 0 and _gate_result(proj)["status"] == "pass"
    _hand_g1s_round(proj, "abc")
    assert lint(proj).returncode == 0 and _gate_result(proj)["status"] == "pass"


def test_two_digit_reset_rounds_work_set_by_state_and_in_an_older_project_that_holds_the_quoted_string(proj):
    """reset_rounds=[10,11] used to be saved as the string "[10,11]" and read one character at a time (1, 0, 1, 1): the style board of
    round 10 was refused as 'not a reset round'. It is a real list now, and an old quoted string still reads as 10 and 11."""
    st = proj / "BRAND-STATE.md"
    _make_round_page(proj, 10, board="style")
    assert bc("state", "--set", "reset_rounds=[10,11]", project=proj).returncode == 0
    assert re.search(r"(?m)^reset_rounds: \[10, 11\]", st.read_text())
    for how in ("a real list", "the old quoted string"):
        if how != "a real list":
            st.write_text(re.sub(r"(?m)^reset_rounds:.*$", 'reset_rounds: "[10,11]"', st.read_text()))
            assert 'reset_rounds: "[10,11]"' in st.read_text()
        r = lint(proj, "rounds/r10/board.html")
        assert r.returncode == 0, (how, r.stdout)                                  # a style board in the reset round 10
        assert bc("state", "--record", "G1s", "picked Ember", project=proj).returncode == 0
        _make_round_page(proj, 11, board="pick")
        r = lint(proj, "rounds/r11/board.html")
        assert r.returncode == 0, (how, r.stdout)                                  # the pick board of the reset round 11
        gate = _gate_result(proj)
        assert gate["status"] == "pass" and "r10" in gate["detail"] and "r1" in gate["detail"], (how, gate)
    st.write_text(re.sub(r"(?m)^reset_rounds:.*$", 'reset_rounds: "[10]"', st.read_text()))
    r = lint(proj, "rounds/r11/board.html")                                       # 11 is no reset round when only 10 is listed
    assert r.returncode == 1 and _kind_detail(proj) == LATER_PICK, r.stdout


def test_two_full_rejections_in_a_row_need_a_style_board_and_a_pick_each(proj):
    """r1 pick, r2 style, r3 pick (rejected), r4 style, r5 pick."""
    _make_round_page(proj, 2, board="style")
    assert bc("state", "--record", "G1s", "picked Ember", project=proj).returncode == 0
    _make_round_page(proj, 3, board="pick")
    _list_reset(proj, 2, 3)
    assert lint(proj, "rounds/r3/board.html").returncode == 0                      # the first reset is complete
    # the owner rejects r3 as a whole: the second reset is a pick board straight away, with the old style board and pick behind it
    _make_round_page(proj, 4, board="pick")
    _list_reset(proj, 2, 3, 4)
    r = lint(proj, "rounds/r4/board.html")
    assert r.returncode == 1 and REARM_MESSAGE in _gate_result(proj)["detail"] and "the rejected round is r3" in _gate_result(proj)["detail"], r.stdout
    # r4 becomes the new style board; r5 is the pick board; the first reset's style board (r2) and pick (g1s_round 2) do not count
    _make_round_page(proj, 4, board="style")
    _make_round_page(proj, 5, board="pick")
    _list_reset(proj, 2, 3, 4, 5)
    assert _g1s_round(proj) == 2
    r = lint(proj, "rounds/r5/board.html")
    assert r.returncode == 1 and STALE_MESSAGE in _gate_result(proj)["detail"] and "r4" in _gate_result(proj)["detail"], r.stdout
    # the owner picks on r4
    assert bc("state", "--record", "G1s", "picked Quarry", project=proj).returncode == 0
    assert _g1s_round(proj) >= 4
    assert lint(proj, "rounds/r5/board.html").returncode == 0
    assert lint(proj, "rounds/r3/board.html").returncode == 0                      # the first reset's pick board still passes
    assert lint(proj, "rounds/r4/board.html").returncode == 0                      # and the second style board needs no gate


def test_with_two_style_boards_in_a_row_the_pick_must_come_after_the_latest_one(proj):
    """r1 pick, r2 style (the owner picks), r3 another style board (research again, redone in a new round), r4 pick: the pick recorded
    on r2 is older than the style board it should follow, so it does not count."""
    _make_round_page(proj, 2, board="style")
    assert bc("state", "--record", "G1s", "picked Ember", project=proj).returncode == 0
    _make_round_page(proj, 3, board="style")
    _make_round_page(proj, 4, board="pick")
    _list_reset(proj, 2, 3, 4)
    r = lint(proj, "rounds/r4/board.html")
    assert r.returncode == 1 and STALE_MESSAGE in _gate_result(proj)["detail"] and "r3" in _gate_result(proj)["detail"], r.stdout
    assert bc("state", "--record", "G1s", "picked Quarry", project=proj).returncode == 0
    assert lint(proj, "rounds/r4/board.html").returncode == 0


def test_a_refine_round_can_be_the_rejected_round(proj):
    """r1 pick, r2 style, r3 pick (a complete reset), r4 a refine board the owner rejects as a whole, r5 pick: the old style board (r2)
    and the pick behind it lie before the rejected round r4, so they do not stand in for a new one."""
    _make_round_page(proj, 2, board="style")
    assert bc("state", "--record", "G1s", "picked Ember", project=proj).returncode == 0
    _make_round_page(proj, 3, board="pick")
    make_r2_board(proj, 4)
    assert 'data-board="refine"' in (proj / "rounds" / "r4" / "board.html").read_text()
    _make_round_page(proj, 5, board="pick")
    _list_reset(proj, 2, 3, 5)
    assert lint(proj, "rounds/r3/board.html").returncode == 0
    r = lint(proj, "rounds/r5/board.html")
    assert r.returncode == 1 and REARM_MESSAGE in _gate_result(proj)["detail"] and "the rejected round is r4" in _gate_result(proj)["detail"], r.stdout
    # a new style board after the refine round, listed, and a pick recorded after it
    _make_round_page(proj, 5, board="style")
    _make_round_page(proj, 6, board="pick")
    _list_reset(proj, 2, 3, 5, 6)
    r = lint(proj, "rounds/r6/board.html")
    assert r.returncode == 1 and STALE_MESSAGE in _gate_result(proj)["detail"] and "r5" in _gate_result(proj)["detail"], r.stdout
    assert bc("state", "--record", "G1s", "picked Meadow", project=proj).returncode == 0
    assert lint(proj, "rounds/r6/board.html").returncode == 0


def test_the_review_page_of_round_0_is_the_style_board_and_passes_the_lint(proj, style):
    """Round 0 has no review template of its own: review/index.html is a copy of the style board, linted with --round 0."""
    review = proj / "review" / "index.html"
    review.parent.mkdir()
    review.write_text(style.read_text(encoding="utf-8"), encoding="utf-8")
    r = lint(proj, "review/index.html", "--round", "0")
    assert r.returncode == 0, r.stdout
    ids = {x["id"]: x["status"] for x in report(proj, "board-lint")["results"]}
    assert ids["page:data-round"] == "pass" and ids["page:data-board"] == "pass" and ids["territories:count"] == "pass"
    assert lint(proj, "review/index.html").returncode == 0   # the page's own data-round="0" is enough
    assert lint(proj, "review/index.html", "--round", "1").returncode == 1   # a stale round number is still caught
    mutate(review, 'data-section="norm"', 'data-removed="norm"')
    assert lint(proj, "review/index.html", "--round", "0").returncode == 1


def _clear_g1s(proj):
    st = proj / "BRAND-STATE.md"
    text = st.read_text()
    out = re.sub(r'(?m)^  G1s:.*$', '  G1s: ""', text)
    assert out != text
    st.write_text(out)


def test_an_older_project_without_a_g1s_key_records_an_honest_na_and_its_board_then_passes(proj):
    """A project made before the style step has no G1s line at all. Its next pick board is refused with the way out in the message;
    `state --record G1s` adds the key, and `state --require G1s` says so before and after."""
    st = proj / "BRAND-STATE.md"
    text = st.read_text()
    older = re.sub(r"(?m)^  G1s:.*\n", "", text)
    assert older != text and not re.search(r"(?m)^\s+G1s:", older)
    st.write_text(older)
    assert bc("state", "--require", "G1s", project=proj).returncode == 1
    r = lint(proj)
    assert r.returncode == 1 and "project:style-gate" in failing(report(proj, "board-lint")), r.stdout
    assert "n/a: round 1 drawn before the style step" in r.stdout and "skipped by owner" in r.stdout
    note = "n/a: round 1 drawn before the style step"
    assert bc("state", "--record", "G1s", note, project=proj).returncode == 0
    assert re.search(r'(?m)^  G1s: "?2026-10-17 n/a: round 1 drawn before the style step"?$', st.read_text())   # the key was added inside the gates map
    r = bc("state", "--require", "G1s", project=proj)
    assert r.returncode == 0 and note in r.stdout
    assert lint(proj).returncode == 0
    ids = {x["id"]: x["status"] for x in report(proj, "board-lint")["results"]}
    assert ids["project:style-gate"] == "pass"


def test_round_1_pick_board_needs_the_style_gate(proj):
    """Recorded or skipped passes; an empty G1s fails; refine boards are not affected."""
    assert lint(proj).returncode == 0
    assert {x["id"]: x["status"] for x in report(proj, "board-lint")["results"]}["project:style-gate"] == "pass"
    _clear_g1s(proj)
    r = lint(proj)
    assert r.returncode == 1 and "project:style-gate" in failing(report(proj, "board-lint")), r.stdout
    assert "G1s" in r.stdout
    assert bc("state", "--record", "G1s", "picked Harbor", project=proj).returncode == 0
    assert lint(proj).returncode == 0
    _clear_g1s(proj)
    make_r2_board(proj)
    assert lint(proj, "rounds/r2/board.html").returncode == 0  # a refine board does not need the style gate


# ---- the kept masters of a refine round, measured before G3 (warnings only)

def _pixel_svg(rows, palette):
    """A pixel drawing from text rows ('.' clear): crisp rects on a square whole-number viewBox."""
    n = len(rows)
    rects = "".join(f'<rect x="{x}" y="{y}" width="1" height="1" fill="{palette[c]}"/>'
                    for y, row in enumerate(rows) for x, c in enumerate(row) if c != ".")
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {n} {n}" shape-rendering="crispEdges">{rects}</svg>'


PAL = {"K": "#121212", "W": "#f2efe6", "C": "#2fb37a"}
def _framed(n, width, *, leak=False):
    """An n x n pixel drawing: a black outline `width` px thick around a cream face, inside a 1 px clear margin. `leak` turns one
    outline pixel on the right edge mint, so the mint meets the ground."""
    rows = []
    for y in range(n):
        row = ""
        for x in range(n):
            if x in (0, n - 1) or y in (0, n - 1):
                row += "."
            elif min(x - 1, y - 1, n - 2 - x, n - 2 - y) < width:
                row += "K"
            else:
                row += "W"
        rows.append(row)
    if leak:
        rows[n // 2] = rows[n // 2][:n - 2] + "C" + rows[n // 2][n - 1:]
    return rows


THICK, THIN, GAP = _framed(16, 2), _framed(16, 1), _framed(16, 1, leak=True)


def _masters(proj, rnd, files):
    d = proj / "rounds" / f"r{rnd}" / "compass"
    d.mkdir(parents=True, exist_ok=True)
    for name, rows in files.items():
        (d / name).write_text(_pixel_svg(rows, PAL), encoding="utf-8")
    return d


def _masters_rows(proj):
    return {r["id"]: r for r in report(proj, "board-lint")["results"] if r["id"].startswith("masters")}


@pytest.mark.requires_resvg
def test_a_refine_board_warns_when_the_outlines_of_its_kept_masters_differ(proj):
    """One family draws one weight: two 16 px grids of a direction with a 2 px and a 1 px outline give a warning before G3
    (a real round was approved with the belt at 2 px and its siblings at 1 px). Warnings never fail the board."""
    make_r2_board(proj)
    _masters(proj, 2, {"belt.svg": THICK, "roller.svg": THIN})
    r = lint(proj, "rounds/r2/board.html")
    assert r.returncode == 0, r.stdout
    row = _masters_rows(proj)["masters:outline:rounds/r2/compass:16"]
    assert row["status"] == "warn" and row["widths"] == {"belt.svg": 2, "roller.svg": 1}
    assert "outline widths differ" in row["detail"] and "belt.svg 2 px, roller.svg 1 px" in row["detail"]
    _masters(proj, 2, {"roller.svg": THICK})                                       # redrawn at 2 px: one weight
    lint(proj, "rounds/r2/board.html")
    assert _masters_rows(proj)["masters:outline:rounds/r2/compass:16"]["status"] == "pass"


@pytest.mark.requires_resvg
def test_a_refine_board_names_each_colour_of_its_kept_masters_that_touches_the_ground_too_softly(proj):
    """A cream face inside a black outline never meets the ground; a mint pixel left on the outline does, at 2.68:1 on white.
    Cells that meet only at a corner do not touch. A -dark twin is measured on the dark ground; without one, the light
    artwork is."""
    make_r2_board(proj)
    _masters(proj, 2, {"framed.svg": THIN, "gap.svg": GAP})
    assert lint(proj, "rounds/r2/board.html").returncode == 0
    rows = _masters_rows(proj)
    assert rows["masters:ground:rounds/r2/compass/framed.svg:light"]["status"] == "pass"
    gap = rows["masters:ground:rounds/r2/compass/gap.svg:light"]
    assert gap["status"] == "warn" and gap["below"] == [{"hex": "#2fb37a", "ratio": 2.68}] and "#2fb37a touches it at 2.68:1" in gap["detail"]
    assert rows["masters:ground:rounds/r2/compass/framed.svg:dark"]["status"] == "warn"   # black on the dark ground, no twin
    ringed = [r.replace(".", "W", 1)[::-1].replace(".", "W", 1)[::-1] if r.strip(".") else r for r in THIN]   # cream ring left and right
    ringed[0] = ringed[-1] = "." + "W" * 14 + "."                                                                # and above and below
    (proj / "rounds" / "r2" / "compass" / "framed-dark.svg").write_text(_pixel_svg(ringed, PAL), encoding="utf-8")
    lint(proj, "rounds/r2/board.html")
    dark = _masters_rows(proj)["masters:ground:rounds/r2/compass/framed-dark.svg:dark"]
    assert dark["status"] == "pass" and dark["ground"] == "#111111"                                             # the twin, on the dark ground


def test_a_refine_round_without_masters_and_a_pick_board_measure_nothing(proj):
    make_r2_board(proj)
    assert lint(proj, "rounds/r2/board.html").returncode == 0
    assert _masters_rows(proj)["masters"]["status"] == "info"
    assert lint(proj).returncode == 0 and not _masters_rows(proj)                   # round 1 is a pick board


@pytest.mark.requires_resvg
def test_cells_that_meet_only_at_a_corner_do_not_touch_and_the_drawings_edge_does(proj):
    """A mint cell whose only clear neighbour is diagonal (an inner corner) does not touch the ground; a cream cell on the edge of a
    drawing with no clear cell at all does, because the drawing's edge meets whatever it is placed on."""
    corner = [list(r) for r in THIN]
    corner[1][1], corner[2][2] = ".", "C"
    bleed = ["K" * 16] + ["K" + "W" * 14 + "K" for _ in range(14)] + ["K" * 16]
    bleed[8] = "W" + bleed[8][1:]
    make_r2_board(proj)
    _masters(proj, 2, {"corner.svg": ["".join(r) for r in corner], "bleed.svg": bleed})
    assert lint(proj, "rounds/r2/board.html").returncode == 0
    rows = _masters_rows(proj)
    assert rows["masters:ground:rounds/r2/compass/corner.svg:light"]["status"] == "pass"
    edge = rows["masters:ground:rounds/r2/compass/bleed.svg:light"]
    assert edge["status"] == "warn" and edge["below"] == [{"hex": "#f2efe6", "ratio": 1.15}]


@pytest.mark.requires_resvg
def test_a_silhouette_has_no_outline_width_and_does_not_count_as_a_different_weight(proj):
    blob = ["." * 16] + ["." * 3 + "K" * 10 + "." * 3 for _ in range(14)] + ["." * 16]
    make_r2_board(proj)
    _masters(proj, 2, {"blob.svg": blob, "framed.svg": THIN})
    lint(proj, "rounds/r2/board.html")
    rows = _masters_rows(proj)
    assert rows["masters:outline:rounds/r2/compass/blob.svg"]["status"] == "info" and "a silhouette" in rows["masters:outline:rounds/r2/compass/blob.svg"]["detail"]
    assert "masters:outline:rounds/r2/compass:16" not in rows                       # one measured width: nothing to compare


@pytest.mark.requires_resvg
def test_an_unreadable_svg_is_a_warning_and_the_before_folder_is_not_measured(proj):
    make_r2_board(proj)
    d = _masters(proj, 2, {"framed.svg": THIN})
    (d / "mockup.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" width="100%"><rect width="10" height="10"/></svg>')
    old = proj / "rounds" / "r2" / "before"
    old.mkdir()
    (old / "old-icon.svg").write_text(_pixel_svg(GAP, PAL))
    r = lint(proj, "rounds/r2/board.html")
    assert r.returncode == 0, r.stdout
    rows = _masters_rows(proj)
    assert rows["masters:file:rounds/r2/compass/mockup.svg"]["status"] == "warn" and "NOT measured" in rows["masters:file:rounds/r2/compass/mockup.svg"]["detail"]
    assert not [i for i in rows if "before/" in i]


def test_without_resvg_the_masters_are_a_warning_not_a_pass(proj, tmp_path):
    from shutil import which
    bare = tmp_path / "bare"
    bare.mkdir()
    for tool in ("uv", "node", "python3", "bash", "env", "dirname", "readlink", "mkdir", "cat"):
        found = which(tool)
        if found and not (bare / tool).exists():
            (bare / tool).symlink_to(found)
    make_r2_board(proj)
    _masters(proj, 2, {"framed.svg": THIN})
    r = bc("board-lint", "rounds/r2/board.html", project=proj, env={"PATH": str(bare)})
    assert r.returncode == 0, r.stdout + r.stderr
    row = _masters_rows(proj)["masters"]
    assert row["status"] == "warn" and "NOT verified: resvg is not installed" in row["detail"]
