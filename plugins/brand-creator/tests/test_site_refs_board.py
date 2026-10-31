"""The website references board (data-board="site-refs"): a round after G4 that shows groups of real sites to learn from (scripts/boardlib/siteboard.py, templates/site-refs-board.html).
Every row of the lint has a deliberate break here. The board is an ordinary round, so these tests need no browser."""
import re
from pathlib import Path

import pytest
from helpers import ROOT, bc, failing, fill_site_refs_board, fill_style_board, install_fixture, make_project, mutate, report

import reflex
import siteboard
from boardpage import group_count, is_site_refs_board, parse_dom

TEMPLATE = ROOT / "templates" / "site-refs-board.html"
CLICHES_TEMPLATE = ROOT / "templates" / "site-cliches.md"
NAMES = ("Ledger", "Atlas", "Quay", "Harbour")
THREE_CLICHES = ("# Acme: site clichés\n\n## Avoid unless argued\n\n"
                 "- a full-width photo with a headline laid over it\n- three equal tiles under the fold\n- a countdown that restarts for every visitor\n")


def board_text(names=NAMES, rnd: int = 2) -> str:
    return fill_site_refs_board(TEMPLATE.read_text(encoding="utf-8"), names, rnd=rnd)


def build(tmp_path, *, tier: str = "standard", g4: bool = True, research: str | None = "online", surfaces: str | None = "site, social", cliches: str | None = THREE_CLICHES,
          board: str | None = "rounds/r2/board.html", names=NAMES, rnd: int = 2) -> Path:
    """A project ready for a website references board: Standard, G3 and G4 recorded, the online-research answer, a brief that lists a site, three site clichés and the board filled in at `board`.
    Each keyword leaves one of those out or changes it (a purpose-built input for a failing case)."""
    p = make_project(tmp_path, tier=tier)
    install_fixture(p, tokens=False, logo=False, qa=False)
    for gate, text in (("G3", "approved r1 (test)"), ("G4", "approved system rules (test)")):
        if gate != "G4" or g4:
            assert bc("state", "--record", gate, text, project=p).returncode == 0
    if research is not None:
        assert bc("state", "--set", f"site_research={research}", project=p).returncode == 0
    if surfaces is not None:
        brief = p / "brief" / "BRIEF.md"
        text = brief.read_text(encoding="utf-8")
        line = "- Required surfaces: (site, app icon, social, print, packaging, ...)"
        assert line in text
        brief.write_text(text.replace(line, f"- Required surfaces: {surfaces}"), encoding="utf-8")
    if cliches is not None:
        (p / "research").mkdir(exist_ok=True)
        (p / "research" / "site-cliches.md").write_text(cliches, encoding="utf-8")
    if board is not None:
        (p / board).parent.mkdir(parents=True, exist_ok=True)
        (p / board).write_text(board_text(names, rnd), encoding="utf-8")
    return p


@pytest.fixture
def proj(tmp_path):
    return build(tmp_path)


def lint(p: Path, page: str = "rounds/r2/board.html", *extra):
    return bc("board-lint", page, *extra, project=p)


def rows(p: Path) -> dict:
    return {r["id"]: r for r in report(p, "board-lint")["results"]}


def detail(p: Path, rid: str) -> str:
    return rows(p)[rid]["detail"]


def failed(p: Path) -> list[str]:
    return failing(report(p, "board-lint"))


# ---------------------------------------------------------------- the template and a finished board

def test_a_filled_site_refs_board_passes(proj):
    r = lint(proj)
    assert r.returncode == 0, r.stdout
    got = rows(proj)
    for rid in ("page:data-board", "page:unfilled", "page:votes", "site-refs:tier", "site-refs:brief", "site-refs:g4", "site-refs:research", "site-refs:cliches-file", "groups:count",
                "section:visitor-job", "section:norm", "section:owner-sites", "section:site-cliches", "section:none-of-these", "section:my-call", "section:questions", "section:reply"):
        assert got[rid]["status"] == "pass", (rid, got[rid])
    assert got["page:data-board"]["detail"] == "site-refs" and "4 found" in got["groups:count"]["detail"]
    assert not [x for x in got if x.startswith(("direction", "map:", "masters", "project:", "motion:"))], "no direction, map, style gate, inventory, kept master or motion row on a references board"


def test_the_template_as_it_is_fails_until_filled(proj):
    for needle in ('data-board="site-refs"', 'data-section="visitor-job"', 'data-section="norm"', 'data-section="owner-sites"', 'data-like="like"', 'data-like="dislike"', 'data-field="why"',
                   'data-section="group"', 'data-field="idea"', 'data-field="references"', 'data-field="shot"', 'data-field="take"', 'data-field="avoid"', 'data-section="site-cliches"',
                   'data-section="none-of-these"', 'data-section="my-call"', 'data-section="questions"', 'data-multi="true"', 'data-section="reply"', "articles for groups two to four"):
        assert needle in TEMPLATE.read_text(encoding="utf-8"), needle
    (proj / "rounds" / "r2" / "board.html").write_text(TEMPLATE.read_text(encoding="utf-8"), encoding="utf-8")
    r = lint(proj)
    assert r.returncode == 1 and "page:unfilled" in failed(proj), r.stdout
    assert rows(proj)["site-refs:g4"]["status"] == "pass"            # the gates are the project's, not the page's


def test_the_template_has_the_frame_of_the_style_board_and_no_network_address(proj):
    text = TEMPLATE.read_text(encoding="utf-8")
    style = (ROOT / "templates" / "style-board.html").read_text(encoding="utf-8")
    for frame in ('<meta name="color-scheme" content="light dark">', ':root[data-theme="dark"]', "--sans:ui-sans-serif,system-ui", 'id="reply-out"', 'id="copy-reply"', "?t=light|dark"):
        assert frame in text and frame in style, frame
    assert not re.search(r"""(?:src|href)\s*=\s*["']?(?:https?:)?//""", text)
    body = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    assert "http://" not in body and "https://" not in re.sub(r"\[\[fill:[^\]]*\]\]", "", body)


def test_the_filled_board_gives_each_group_a_vote_group_of_its_own(proj):
    page = (proj / "rounds" / "r2" / "board.html").read_text(encoding="utf-8")
    for name in NAMES:
        assert f'data-vote="{name}"' in page and f'name="vote-{name}"' in page, name
    assert lint(proj).returncode == 0 and rows(proj)["page:votes"]["status"] == "pass"


def test_the_site_cliches_template_gives_no_items_and_has_no_forbidden_section(tmp_path):
    text = CLICHES_TEMPLATE.read_text(encoding="utf-8")
    assert "## Site clichés seen" in text and "## Avoid unless argued" in text and "## Forbidden" not in text
    (tmp_path / "research").mkdir()
    (tmp_path / "research" / "site-cliches.md").write_text(text, encoding="utf-8")
    assert reflex.cliche_items(tmp_path, rel="research/site-cliches.md") == []
    assert "layout / copy / imagery / interaction" in text


# ---------------------------------------------------------------- site-refs:tier, site-refs:brief, site-refs:g4, site-refs:research

def test_a_site_refs_board_needs_standard_or_full(proj):
    mutate(proj / "BRAND-STATE.md", "tier: standard", "tier: quick")
    r = lint(proj)
    assert r.returncode == 1 and "site-refs:tier" in failed(proj), r.stdout
    assert "the site work is Standard and Full" in detail(proj, "site-refs:tier") and "quick" in detail(proj, "site-refs:tier")


def test_a_site_refs_board_is_allowed_in_the_full_tier(tmp_path):
    p = build(tmp_path, tier="full")
    assert lint(p).returncode == 0, lint(p).stdout
    assert rows(p)["site-refs:tier"]["detail"] == "tier: full"


def test_a_site_refs_board_needs_a_site_in_the_brief(proj):
    mutate(proj / "brief" / "BRIEF.md", "- Required surfaces: site, social", "- Required surfaces: app icon, social")
    r = lint(proj)
    assert r.returncode == 1 and "site-refs:brief" in failed(proj), r.stdout
    why = detail(proj, "site-refs:brief")
    assert "lists a site under Required surfaces" in why and "ask the owner" in why and "app icon, social" in why, why


def test_the_untouched_brief_template_line_is_no_site(tmp_path):
    p = build(tmp_path, surfaces=None)
    assert "(site, app icon, social, print, packaging, ...)" in (p / "brief" / "BRIEF.md").read_text(encoding="utf-8")   # `new` wrote the template line and nobody changed it
    r = lint(p)
    assert r.returncode == 1 and "site-refs:brief" in failed(p), r.stdout
    assert "(site, app icon, social, print, packaging, ...)" in detail(p, "site-refs:brief") and "template" in detail(p, "site-refs:brief")


def test_a_polish_brief_counts_strona_as_a_site(tmp_path):
    p = build(tmp_path, surfaces="strona www, social")
    r = lint(p)
    assert r.returncode == 0, r.stdout
    assert rows(p)["site-refs:brief"]["status"] == "pass" and "strona" in detail(p, "site-refs:brief")


@pytest.mark.parametrize("line, counts", [
    ("site, social", True), ("Website, print", True), ("a web page and packaging", True), ("Landing page", True), ("www", True), ("web-page", True), ("sites", True),
    ("strona internetowa", True), ("stronę, wizytówki", True), ("witryna firmowa", True), ("na witrynie", True), ("strony www", True),
    ("microsite", True), ("strone internetowa", True), ("witryne firmowa", True), ("stronka", True), ("stronką", True),
    ("app icon, social, print", False), ("strong brand, packaging", False), ("sitemap", False), ("(site, app icon, social, print, packaging, ...)", False), ("", False),
])
def test_the_site_word_list_reads_english_and_polish(tmp_path, line, counts):
    (tmp_path / "brief").mkdir()
    (tmp_path / "brief" / "BRIEF.md").write_text(f"# Acme: brief\n\n## Facts\n\n- Offer: loaves\n- Required surfaces: {line}\n- Regulated profession: none\n", encoding="utf-8")
    listed, why = siteboard.brief_lists_site(tmp_path)
    assert listed is counts, (line, why)
    assert "Required surfaces" in why, why


def test_the_surfaces_line_is_found_in_other_shapes_and_a_missing_line_or_file_is_no_site(tmp_path):
    (tmp_path / "brief").mkdir()
    brief = tmp_path / "brief" / "BRIEF.md"
    brief.write_text("# Acme: brief\n\n- **Required surfaces:** Website, print\n", encoding="utf-8")
    assert siteboard.brief_lists_site(tmp_path)[0] is True
    brief.write_text("# Acme: brief\n\n- REQUIRED SURFACES: Site\n", encoding="utf-8")
    assert siteboard.brief_lists_site(tmp_path)[0] is True
    brief.write_text("# Acme: brief\n\nA site would be nice.\n", encoding="utf-8")
    listed, why = siteboard.brief_lists_site(tmp_path)
    assert listed is False and 'no "Required surfaces:" line' in why
    brief.unlink()
    listed, why = siteboard.brief_lists_site(tmp_path)
    assert listed is False and "missing" in why


def test_an_empty_surfaces_line_never_reads_the_next_line(proj):
    brief = proj / "brief" / "BRIEF.md"
    brief.write_text("# Acme: brief\n\n## Facts\n\n- Required surfaces:\n- Regulated profession: none (orders come in through the shop's www form)\n", encoding="utf-8")
    listed, why = siteboard.brief_lists_site(proj)
    assert listed is False and "Required surfaces line is empty" in why, why
    r = lint(proj)
    assert r.returncode == 1 and "site-refs:brief" in failed(proj), r.stdout
    assert "is empty" in detail(proj, "site-refs:brief") and "www" not in detail(proj, "site-refs:brief"), detail(proj, "site-refs:brief")
    brief.write_text("# Acme: brief\n\n- **Required surfaces:**\n\n- Offer: a site for loaves\n", encoding="utf-8")   # the bold label, a blank line, a site word further down
    assert siteboard.brief_lists_site(proj)[0] is False and "is empty" in siteboard.brief_lists_site(proj)[1]


def test_a_site_refs_board_waits_for_g4(tmp_path):
    p = build(tmp_path, g4=False)
    r = lint(p)
    assert r.returncode == 1 and "site-refs:g4" in failed(p), r.stdout
    assert "after the system rules (G4)" in detail(p, "site-refs:g4") and "state --record G4" in detail(p, "site-refs:g4")


def test_a_site_refs_board_waits_for_the_online_research_answer(proj):
    mutate(proj / "BRAND-STATE.md", "site_research: online", "site_research: auto")
    r = lint(proj)
    assert r.returncode == 1 and "site-refs:research" in failed(proj), r.stdout
    assert "state --set site_research=online|links-only|none" in detail(proj, "site-refs:research") and "auto" in detail(proj, "site-refs:research")


@pytest.mark.parametrize("answer", ["online", "links-only", "none"])
def test_each_recorded_answer_to_the_online_research_question_lets_the_board_through(tmp_path, answer):
    p = build(tmp_path, research=answer)
    r = lint(p)
    assert r.returncode == 0, r.stdout
    assert detail(p, "site-refs:research") == f"site_research: {answer}"


def test_a_project_that_never_recorded_the_answer_fails_the_research_row_as_missing(tmp_path):
    p = build(tmp_path, research=None)
    state = (p / "BRAND-STATE.md").read_text(encoding="utf-8")
    (p / "BRAND-STATE.md").write_text("\n".join(ln for ln in state.split("\n") if not ln.startswith("site_research")), encoding="utf-8")
    assert "site_research" not in (p / "BRAND-STATE.md").read_text(encoding="utf-8")
    r = lint(p)
    assert r.returncode == 1 and "site-refs:research" in failed(p), r.stdout
    assert "missing" in detail(p, "site-refs:research")


# ---------------------------------------------------------------- page:data-board, the style gate

@pytest.mark.parametrize("rnd", [0, 1])
def test_a_site_refs_board_is_round_2_or_later(tmp_path, rnd):
    p = build(tmp_path, board=f"rounds/r{rnd}/refs.html", rnd=rnd)
    r = lint(p, f"rounds/r{rnd}/refs.html")
    assert r.returncode == 1 and "page:data-board" in failed(p), r.stdout
    assert "a round of its own from round 2 on" in detail(p, "page:data-board")


def test_a_site_refs_board_is_never_a_reset_round(tmp_path):
    p = build(tmp_path)
    assert bc("state", "--set", "reset_rounds=[2]", project=p).returncode == 0
    r = lint(p)
    assert r.returncode == 1 and "page:data-board" in failed(p), r.stdout
    assert "listed in reset_rounds" in detail(p, "page:data-board") and "a round of its own from round 2 on" in detail(p, "page:data-board")


def test_a_data_board_that_is_none_of_the_kinds_names_site_refs_among_them(proj):
    (proj / "rounds" / "r2" / "board.html").write_text(board_text().replace('data-board="site-refs"', 'data-board="sites"'), encoding="utf-8")
    r = lint(proj)
    assert r.returncode == 1 and "pick|refine|style|motion|site-refs" in detail(proj, "page:data-board")


def test_the_style_gate_never_counts_a_site_refs_board_as_the_rejected_round(tmp_path):
    """r1 pick (rejected), r2 style (reset), r3 a website references board, r4 pick (reset): the rejected round is r1, and the style board of r2 comes after it. If a references board
    counted as a round the owner rejected, the new style board would have to come after r3 and the pick of r4 would fail."""
    proj = build(tmp_path, board="rounds/r3/board.html", rnd=3)
    style = proj / "rounds" / "r2" / "board.html"
    style.parent.mkdir()
    style.write_text(fill_style_board((ROOT / "templates" / "style-board.html").read_text(encoding="utf-8")).replace('data-round="0"', 'data-round="2"'), encoding="utf-8")
    assert bc("state", "--record", "G1s", "picked Ember", project=proj).returncode == 0
    src = (proj / "rounds" / "r1" / "board.html").read_text(encoding="utf-8").replace('data-round="1"', 'data-round="4"')
    src = src.replace('<span class="axis x0">', '<span data-field="failed-round">Round 1 sat in the middle of the category norm.</span><span class="axis x0">', 1)
    extra = ('<section class="block" data-section="what-changed"><h2>What changed</h2><p>New territories after a full rejection.</p></section>\n'
             '<section class="block" data-section="weak-points"><h2>Weak points</h2><p>Untested at 16 px.</p></section>\n'
             '<section class="block" data-section="losers"><h2>Kept as losers</h2><div data-section="loser" data-name="Compass"><p data-field="reason">Round 1 was rejected as a whole.</p></div></section>\n')
    marker = '<section class="block" id="directions">'
    (proj / "rounds" / "r4").mkdir()
    (proj / "rounds" / "r4" / "board.html").write_text(src.replace(marker, extra + marker), encoding="utf-8")
    assert bc("state", "--set", "reset_rounds=[2, 4]", project=proj).returncode == 0
    r = lint(proj, "rounds/r4/board.html")
    assert r.returncode == 0, r.stdout
    gate = rows(proj)["project:style-gate"]
    assert gate["status"] == "pass" and "the rejected round is r1" in gate["detail"], gate


def test_a_website_references_board_is_no_style_board_for_the_style_pick(proj):
    """`state --record G1s` writes g1s_round, the highest round whose board is a style board: a references board is not one."""
    assert bc("state", "--record", "G1s", "picked Ember", project=proj).returncode == 0
    assert bc("state", "--get", "g1s_round", project=proj).returncode == 1                   # no style board on disk: the key is not there


# ---------------------------------------------------------------- the sections, the groups, the clichés

@pytest.mark.parametrize("section", ["visitor-job", "norm", "owner-sites", "site-cliches", "none-of-these", "my-call", "questions", "reply"])
def test_a_site_refs_board_needs_each_section(proj, section):
    mutate(proj / "rounds" / "r2" / "board.html", f'data-section="{section}"', f'data-removed="{section}"')
    r = lint(proj)
    assert r.returncode == 1 and f"section:{section}" in failed(proj), r.stdout


def test_a_section_with_only_its_heading_is_empty_and_fails(proj):
    board = proj / "rounds" / "r2" / "board.html"
    page = board.read_text(encoding="utf-8")
    m = re.search(r'(<section class="block" id="job" data-section="visitor-job">\s*<h2>.*?</h2>).*?(</section>)', page, re.S)
    assert m
    board.write_text(page.replace(m.group(0), m.group(1) + "\n" + m.group(2)), encoding="utf-8")
    r = lint(proj)
    assert r.returncode == 1 and "section:visitor-job" in failed(proj) and "empty" in detail(proj, "section:visitor-job"), r.stdout


def test_the_questions_of_a_references_board_follow_the_rules_of_every_board(proj):
    mutate(proj / "rounds" / "r2" / "board.html", '<li data-option="a" data-recommended="true"><label><input type="radio" name="q2"', '<li data-option="a"><label><input type="radio" name="q2"')
    r = lint(proj)
    assert r.returncode == 1 and "question:2:options" in failed(proj), r.stdout


def test_fewer_than_four_groups_fail(proj):
    board = proj / "rounds" / "r2" / "board.html"
    last = re.findall(r'      <article class="group".*?</article>\n', board.read_text(encoding="utf-8"), re.S)[-1]
    mutate(board, last, "")
    r = lint(proj)
    assert r.returncode == 1 and "groups:count" in failed(proj), r.stdout
    assert "3 found" in detail(proj, "groups:count") and "at least 4" in detail(proj, "groups:count")


def test_a_group_without_a_name_or_content_is_not_counted(proj):
    board = proj / "rounds" / "r2" / "board.html"
    page = board.read_text(encoding="utf-8")
    assert group_count(parse_dom(page)) == 4
    board.write_text(page.replace('data-section="group" data-name="Quay"', 'data-section="group" data-name=""'), encoding="utf-8")
    assert group_count(parse_dom(board.read_text(encoding="utf-8"))) == 3
    r = lint(proj)
    assert r.returncode == 1 and "groups:count" in failed(proj), r.stdout


def test_more_than_six_groups_warn_and_do_not_fail(tmp_path):
    p = build(tmp_path, names=NAMES + ("Mill", "Orchard", "Forge"))
    r = lint(p)
    assert r.returncode == 0, r.stdout
    row = rows(p)["groups:count"]
    assert row["status"] == "warn" and "7 found" in row["detail"] and "6" in row["detail"], row


@pytest.mark.parametrize("count", [4, 5, 6])
def test_four_to_six_groups_pass(tmp_path, count):
    p = build(tmp_path, names=("Ledger", "Atlas", "Quay", "Harbour", "Mill", "Orchard")[:count])
    assert lint(p).returncode == 0
    assert rows(p)["groups:count"]["status"] == "pass"


def test_the_site_cliches_file_needs_three_items(proj):
    mutate(proj / "research" / "site-cliches.md", "- a countdown that restarts for every visitor\n", "")
    r = lint(proj)
    assert r.returncode == 1 and "site-refs:cliches-file" in failed(proj), r.stdout
    assert "2 item(s)" in detail(proj, "site-refs:cliches-file") and "at least 3" in detail(proj, "site-refs:cliches-file")


def test_the_site_cliches_file_is_required_and_the_template_alone_is_not_enough(tmp_path):
    p = build(tmp_path, cliches=None)
    r = lint(p)
    assert r.returncode == 1 and "site-refs:cliches-file" in failed(p) and "templates/site-cliches.md" in detail(p, "site-refs:cliches-file"), r.stdout
    p2 = build(tmp_path / "b", cliches=CLICHES_TEMPLATE.read_text(encoding="utf-8"))
    r = lint(p2)
    assert r.returncode == 1 and "site-refs:cliches-file" in failed(p2) and "0 item(s)" in detail(p2, "site-refs:cliches-file"), r.stdout


def test_the_lint_report_lists_the_brief_and_the_site_cliches_as_inputs(proj):
    assert lint(proj).returncode == 0
    paths = [i["path"] for i in report(proj, "board-lint")["inputs"]]
    assert "brief/BRIEF.md" in paths and "research/site-cliches.md" in paths and "rounds/r2/board.html" in paths, paths


def test_min_directions_is_not_used_on_a_references_board(proj):
    r = lint(proj, "rounds/r2/board.html", "--min-directions", "3")
    assert r.returncode == 0, r.stdout
    assert rows(proj)["directions:count"]["status"] == "info" and "not used" in detail(proj, "directions:count")


# ---------------------------------------------------------------- is_site_refs_board (the page the site round waits for)

def test_a_page_counts_as_a_references_board_when_it_declares_its_round_and_holds_four_groups():
    page = board_text(rnd=2)
    assert is_site_refs_board(parse_dom(page), 2) is True
    assert is_site_refs_board(parse_dom(page), 3) is False                                      # a copy that still declares the round it came from
    assert is_site_refs_board(parse_dom(board_text(NAMES[:3], rnd=2)), 2) is False              # three groups
    assert is_site_refs_board(parse_dom(page.replace('data-board="site-refs"', 'data-board="style"')), 2) is False
    assert is_site_refs_board(None, 2) is False
