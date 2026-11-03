"""The website references board (data-board="site-refs"): a round after G4 that shows groups of real sites to learn from (scripts/boardlib/siteboard.py, templates/site-refs-board.html).
Every row of the lint has a deliberate break here. The board is an ordinary round, so these tests need no browser."""
import base64
import hashlib
import json
import re
from pathlib import Path

import pytest
from helpers import (ROOT, STYLE_STAND_IN, STYLE_TINY_PNG, bc, failing, fill_site_refs_board, fill_style_board, install_fixture, make_project, mutate, report,
                     write_site_capture)

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


ADDRESS = "https://example.com/reference"   # the address the filler gives every reference; the picture it inlines in each is STYLE_TINY_PNG


def build(tmp_path, *, tier: str = "standard", g4: bool = True, research: str | None = "online", surfaces: str | None = "site, social", cliches: str | None = THREE_CLICHES,
          board: str | None = "rounds/r2/board.html", names=NAMES, rnd: int = 2, capture: str | None = ADDRESS) -> Path:
    """A project ready for a website references board: Standard, G3 and G4 recorded, the online-research answer, a brief that lists a site, three site clichés, the capture record of the address every
    reference links to (research/site-refs/example/capture.json: the screenshots are its thumbnail) and the board filled in at `board`. Each keyword leaves one of those out or changes it (a purpose-built
    input for a failing case)."""
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
    if capture is not None:
        write_site_capture(p, "example", capture)
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


# ---------------------------------------------------------------- the groups, the references, the screenshots, the sites the owner named

OTHER_PNG = "data:image/png;base64," + base64.b64encode(b"\x89PNG\r\n\x1a\nnot the picture of the capture").decode()
ELSEWHERE = "https://example.org/elsewhere"


def board_path(p: Path) -> Path:
    return p / "rounds" / "r2" / "board.html"


def record_path(p: Path, name: str = "example") -> Path:
    return p / "research" / "site-refs" / name / "capture.json"


def group_change(p: Path, name: str, fn) -> tuple[str, str]:
    """(the article of one group, the article after fn changed it), to hand to mutate(): the change touches that group only, and it must change something."""
    page = board_path(p).read_text(encoding="utf-8")
    m = re.search(rf'      <article class="group" data-section="group" data-name="{re.escape(name)}"[^>]*>.*?</article>\n', page, re.S)
    assert m, name
    after = fn(m.group(0))
    assert after != m.group(0), "the edit did nothing"
    return m.group(0), after


def edit_group(p: Path, name: str, fn) -> None:
    """The same change, applied for a test that is a variation which must pass, not a deliberate break."""
    old, new = group_change(p, name, fn)
    board_path(p).write_text(board_path(p).read_text(encoding="utf-8").replace(old, new, 1), encoding="utf-8")


def swap(old: str, new: str, count: int = 1):
    def fn(block: str) -> str:
        assert old in block, f"{old!r} is not in the group"
        return block.replace(old, new, count)
    return fn


def reference_items(block: str) -> list[str]:
    return re.findall(r'          <li><span class="name">.*?</li>', block, re.S)


def sha(data_uri: str) -> str:
    return hashlib.sha256(base64.b64decode(data_uri.split(",", 1)[1])).hexdigest()


def shot_rows(p: Path) -> dict:
    return {k: v for k, v in rows(p).items() if re.fullmatch(r"group:.+:shot:\d+", k)}


def test_every_group_and_reference_of_a_filled_board_has_a_passing_row(proj):
    r = lint(proj)
    assert r.returncode == 0, r.stdout
    got = rows(proj)
    for name in NAMES:
        for suffix in ("name", "idea", "references", "shot:1", "shot:2", "shot:3"):
            assert got[f"group:{name}:{suffix}"]["status"] == "pass", (name, suffix, got[f"group:{name}:{suffix}"])
        assert f"group:{name}:shot:4" not in got and f"group:{name}:layout" not in got        # one shot row per reference; a layout row only for a group that names one
    assert "thumb-1440.jpg of research/site-refs/example/capture.json, captured 2026-10-17" == got["group:Ledger:shot:1"]["detail"]
    assert got["owner-sites:items"]["status"] == "pass" and "1 liked, 1 disliked" in got["owner-sites:items"]["detail"]
    assert got["images:inlined"]["status"] == "pass"
    assert not [k for k, v in got.items() if v["status"] == "warn"], "a finished board with captured screenshots has no warning"
    assert "research/site-refs/example/capture.json" in [i["path"] for i in report(proj, "board-lint")["inputs"]]


# ---- group:<name>:references

def test_a_group_with_two_references_fails(proj):
    mutate(board_path(proj), *group_change(proj, "Ledger", lambda block: block.replace(reference_items(block)[-1], "", 1)))
    r = lint(proj)
    assert r.returncode == 1, r.stdout
    assert set(failed(proj)) == {"group:Ledger:references"}, failed(proj)
    assert "2 reference(s)" in detail(proj, "group:Ledger:references") and "at least 3" in detail(proj, "group:Ledger:references")
    assert "group:Ledger:shot:3" not in rows(proj) and rows(proj)["group:Atlas:references"]["status"] == "pass"


def test_a_group_with_no_references_list_fails_the_references_row(proj):
    mutate(board_path(proj), *group_change(proj, "Ledger", swap('data-field="references"', 'data-removed="references"')))
    r = lint(proj)
    assert r.returncode == 1 and set(failed(proj)) == {"group:Ledger:references"}, r.stdout
    assert "0 reference(s)" in detail(proj, "group:Ledger:references")


def test_a_reference_without_what_to_avoid_fails(proj):
    mutate(board_path(proj), *group_change(proj, "Ledger", swap('data-field="avoid"', 'data-removed="avoid"')))
    r = lint(proj)
    assert r.returncode == 1 and set(failed(proj)) == {"group:Ledger:references"}, r.stdout
    why = detail(proj, "group:Ledger:references")
    assert "reference 1 (" in why and 'what to avoid (data-field="avoid" missing, empty, or only the label "Avoid:")' in why and "reference 2" not in why, why


@pytest.mark.parametrize("field, label", [("take", "Take"), ("avoid", "Avoid")])
@pytest.mark.parametrize("left", ["{}: ", "{}:", "{} :", "{}: (...)", "<b>{}:</b>", "{}: TODO", "{}", "{}: -", "{} - ", "{}."],
                         ids=["label-and-space", "label", "space-before-colon", "placeholder", "bold-label", "todo", "word-alone", "label-and-dash", "word-and-dash", "word-and-dot"])
def test_a_take_or_an_avoid_that_keeps_only_the_templates_label_fails(proj, field, label, left):
    """The template writes the label inside the field (`Take: [[fill: ...]]`); a board whose marker was deleted and nothing written must not pass for having the label's text."""
    mutate(board_path(proj), *group_change(proj, "Ledger", swap(f'data-field="{field}">{label}: {STYLE_STAND_IN}<', f'data-field="{field}">{left.format(label)}<')))
    r = lint(proj)
    assert r.returncode == 1 and set(failed(proj)) == {"group:Ledger:references"}, (failed(proj), r.stdout)
    why = detail(proj, "group:Ledger:references")
    assert why.startswith("reference 1 (") and f'data-field="{field}" missing, empty, or only the label "{label}:"' in why and "reference 2" not in why, why
    assert rows(proj)["group:Atlas:references"]["status"] == "pass"


@pytest.mark.parametrize("field, label, words", [("take", "Take", "keep the order of the page"), ("avoid", "Avoid", "their colours"), ("take", "Take", "the rhythm of the page, labelled or not")])
def test_a_take_or_an_avoid_with_words_passes_with_the_label_or_without_it(proj, field, label, words):
    edit_group(proj, "Ledger", swap(f'data-field="{field}">{label}: {STYLE_STAND_IN}<', f'data-field="{field}">{words}<'))                      # no label at all
    assert lint(proj).returncode == 0 and rows(proj)["group:Ledger:references"]["status"] == "pass"
    edit_group(proj, "Ledger", swap(f'data-field="{field}">{words}<', f'data-field="{field}">{label} the {words}<'))                            # starts with the word, not the label
    assert lint(proj).returncode == 0 and rows(proj)["group:Ledger:references"]["status"] == "pass"
    edit_group(proj, "Ledger", swap(f'data-field="{field}">{label} the {words}<', f'data-field="{field}">{label}: {words}<'))                   # the label and words
    assert lint(proj).returncode == 0 and rows(proj)["group:Ledger:references"]["status"] == "pass"


@pytest.mark.parametrize("change, said", [
    (swap('data-field="take"', 'data-removed="take"'), "what to take"),
    (swap('<a href="https://example.com/reference">', '<a href="/reference">'), "no link to the site"),
    (swap('data-field="shot"', 'data-removed="shot"'), "no screenshot"),
    (swap('alt="Filled in for the test fixture."', 'alt=""'), "alt text is missing or empty"),
    (lambda block: swap("</figure>", "</div>")(swap('<figure class="shot">', '<div class="shot">')(block)), "is not inside a <figure>"),
], ids=["take", "link", "shot", "alt", "figure"])
def test_each_part_of_a_reference_is_needed(proj, change, said):
    mutate(board_path(proj), *group_change(proj, "Atlas", change))                                # the first reference of the group
    r = lint(proj)
    assert r.returncode == 1 and set(failed(proj)) == {"group:Atlas:references"}, (failed(proj), r.stdout)
    why = detail(proj, "group:Atlas:references")
    assert said in why and why.startswith("reference 1"), why
    assert rows(proj)["group:Ledger:references"]["status"] == "pass"


def test_a_reference_whose_own_link_is_not_http_has_no_link_even_when_its_take_holds_one(proj):
    """The first link of a reference is the site's. A later http link in the take is not a stand-in for it, and a screenshot is never matched to the take's address."""
    other = '<a href="https://example.com/other">their page</a>'
    mutate(board_path(proj), *group_change(proj, "Atlas", lambda block: swap(f'data-field="take">Take: {STYLE_STAND_IN}<', f'data-field="take">Take: {STYLE_STAND_IN} {other}<')(swap('<a href="https://example.com/reference">', '<a href="/reference">')(block))))
    r = lint(proj)
    assert r.returncode == 1 and set(failed(proj)) == {"group:Atlas:references"}, (failed(proj), r.stdout)
    assert "reference 1" in detail(proj, "group:Atlas:references") and "no link to the site" in detail(proj, "group:Atlas:references"), detail(proj, "group:Atlas:references")
    assert "links to no http(s) address" in detail(proj, "group:Atlas:shot:1"), detail(proj, "group:Atlas:shot:1")
    assert "example.com/other" not in detail(proj, "group:Atlas:shot:1")


def test_an_owner_site_whose_own_link_is_not_http_has_no_link_even_when_its_reason_holds_one(proj):
    other = '<a href="https://example.com/other">their page</a>'
    mutate(board_path(proj), '<a href="https://example.com/reference">', '<a href="/reference">')     # the first link on the page is the first site the owner named
    mutate(board_path(proj), f'<span data-field="why">{STYLE_STAND_IN}</span>', f'<span data-field="why">{STYLE_STAND_IN} {other}</span>')
    r = lint(proj)
    assert r.returncode == 1 and failed(proj) == ["owner-sites:items"], r.stdout
    assert "site 1" in detail(proj, "owner-sites:items") and "no http(s) link and no inlined image" in detail(proj, "owner-sites:items")


def test_a_screenshot_without_a_caption_fails(proj):
    mutate(board_path(proj), *group_change(proj, "Atlas", lambda block: re.sub(r"<figcaption>.*?</figcaption>", "<figcaption> </figcaption>", block, count=1, flags=re.S)))
    r = lint(proj)
    assert r.returncode == 1 and set(failed(proj)) == {"group:Atlas:references"}, r.stdout
    assert "no non-empty <figcaption>" in detail(proj, "group:Atlas:references") and "whose site it is and when it was captured" in detail(proj, "group:Atlas:references")


def test_a_caption_that_keeps_only_the_templates_tail_fails(proj):
    """The template ends each caption with ` · shown for private research`; the author's words (whose site, when it was captured) are what must be there."""
    mutate(board_path(proj), *group_change(proj, "Atlas", lambda block: re.sub(r"<figcaption>.*?</figcaption>", "<figcaption> · shown for private research</figcaption>", block, count=1, flags=re.S)))
    r = lint(proj)
    assert r.returncode == 1 and set(failed(proj)) == {"group:Atlas:references"}, r.stdout
    assert "no non-empty <figcaption>" in detail(proj, "group:Atlas:references") and detail(proj, "group:Atlas:references").startswith("reference 1")
    edit_group(proj, "Atlas", lambda block: re.sub(r"<figcaption>.*?</figcaption>", "<figcaption>Example, captured 2026-10-17 · shown for private research</figcaption>", block, count=1, flags=re.S))
    assert lint(proj).returncode == 0 and rows(proj)["group:Atlas:references"]["status"] == "pass"       # the author's words and the tail pass


def test_a_list_inside_a_take_is_part_of_its_reference_and_lends_no_reference_to_a_group(proj):
    def two_references_and_a_list(block: str) -> str:
        return swap(f'data-field="take">Take: {STYLE_STAND_IN}<', 'data-field="take">Take:<ul><li>the order</li><li>the rhythm</li></ul><')(block.replace(reference_items(block)[-1], "", 1))
    mutate(board_path(proj), *group_change(proj, "Ledger", two_references_and_a_list))
    r = lint(proj)
    assert r.returncode == 1 and set(failed(proj)) == {"group:Ledger:references"}, r.stdout            # two references, whatever the list in the first one holds
    assert detail(proj, "group:Ledger:references").startswith("2 reference(s)") and "group:Ledger:shot:3" not in rows(proj)


def test_a_list_inside_a_take_does_not_add_a_reference_to_a_group_of_three(proj):
    edit_group(proj, "Ledger", swap(f'data-field="take">Take: {STYLE_STAND_IN}<', 'data-field="take">Take:<ul><li>the order</li><li>the rhythm</li></ul><'))
    r = lint(proj)
    assert r.returncode == 0, r.stdout
    assert detail(proj, "group:Ledger:references") == "3 reference(s)" and "group:Ledger:shot:4" not in rows(proj) and "group:Ledger:shot:3" in rows(proj)


def test_a_linked_screenshot_fails(proj):
    mutate(board_path(proj), *group_change(proj, "Ledger", swap(f'src="{STYLE_TINY_PNG}"', 'src="https://example.com/shot.png"')))
    r = lint(proj)
    assert r.returncode == 1, r.stdout
    assert set(failed(proj)) == {"group:Ledger:references", "images:inlined"}, failed(proj)          # the picture would ask the network: the reference row and the whole-board row both say so
    assert "inlined data:image/" in detail(proj, "group:Ledger:references") and "reference 1" in detail(proj, "group:Ledger:references")
    row = rows(proj)["group:Ledger:shot:1"]
    assert row["status"] == "warn" and "no bytes to compare" in row["detail"], row                     # and there is nothing to match against a capture


def test_a_srcset_on_a_screenshot_fails(proj):
    mutate(board_path(proj), *group_change(proj, "Ledger", swap(f'src="{STYLE_TINY_PNG}"', f'src="{STYLE_TINY_PNG}" srcset="https://example.com/shot-2x.png 2x"')))
    r = lint(proj)
    assert r.returncode == 1 and "group:Ledger:references" in failed(proj), r.stdout
    assert "srcset is not allowed" in detail(proj, "group:Ledger:references")


def test_a_group_needs_an_idea(proj):
    mutate(board_path(proj), *group_change(proj, "Quay", swap('data-field="idea"', 'data-removed="idea"')))
    r = lint(proj)
    assert r.returncode == 1 and set(failed(proj)) == {"group:Quay:idea"}, r.stdout


# ---- group:<name>:shot:<k>

def test_a_screenshot_not_matched_to_a_capture_warns_and_does_not_fail(proj):
    mutate(record_path(proj), ADDRESS, ELSEWHERE, count=2)                                       # the capture is of another address: the same bytes, a different site
    r = lint(proj)
    assert r.returncode == 0, r.stdout
    shots = shot_rows(proj)
    assert len(shots) == 12 and {v["status"] for v in shots.values()} == {"warn"}, shots
    why = detail(proj, "group:Ledger:shot:2")
    assert f"not matched to a capture of {ADDRESS}" in why, why
    assert f"brand-creator capture --url {ADDRESS} --name <name>" in why and "say in the caption that the owner sent the screenshot" in why, why
    assert f"a capture of {ELSEWHERE}" in why, why                                               # where the picture really came from


def test_a_screenshot_with_no_capture_at_all_warns_and_says_there_is_none(tmp_path):
    p = build(tmp_path, capture=None)
    r = lint(p)
    assert r.returncode == 0, r.stdout
    assert {v["status"] for v in shot_rows(p).values()} == {"warn"} and "there is no research/site-refs/<name>/capture.json" in detail(p, "group:Quay:shot:3")


def test_a_screenshot_that_is_none_of_the_pictures_of_the_capture_of_its_address_warns(proj):
    write_site_capture(proj, "example", ADDRESS, picture=OTHER_PNG)                               # a capture of this address, whose thumbnail is another picture
    r = lint(proj)
    assert r.returncode == 0 and {v["status"] for v in shot_rows(proj).values()} == {"warn"}, r.stdout
    assert "none of its views or thumbnails" in detail(proj, "group:Harbour:shot:1")


def test_a_capture_record_that_cannot_be_read_is_named_in_the_warning(proj):
    (proj / "research" / "site-refs" / "broken").mkdir()
    (proj / "research" / "site-refs" / "broken" / "capture.json").write_text("{not json", encoding="utf-8")
    record_path(proj).unlink()
    r = lint(proj)
    assert r.returncode == 0, r.stdout
    assert "research/site-refs/broken/capture.json" in detail(proj, "group:Ledger:shot:1") and "could not be read" in detail(proj, "group:Ledger:shot:1")


@pytest.mark.parametrize("url, final", [
    (ADDRESS, None), (ADDRESS + "/", None), ("https://EXAMPLE.com/reference", None),            # the address as the browser wrote it: a trailing slash, a host in capitals
    ("https://example.com/", ADDRESS), ("https://example.com/reference#top", None),            # the page the address led on to, and an address with a fragment
])
def test_a_screenshot_matches_the_capture_of_the_address_however_it_is_written(proj, url, final):
    write_site_capture(proj, "example", url, final_url=final)
    r = lint(proj)
    assert r.returncode == 0, r.stdout
    assert {v["status"] for v in shot_rows(proj).values()} == {"pass"}, shot_rows(proj)


@pytest.mark.parametrize("url, want", [
    ("https://example.com:443/reference", "https://example.com/reference"), ("HTTPS://Example.COM:443/", "https://example.com"), ("http://example.com:80/x#top", "http://example.com/x"),
    ("https://example.com:8443/", "https://example.com:8443"), ("http://example.com:443/", "http://example.com:443"), ("https://example.com:80/", "https://example.com:80"),
    ("https://user@localhost:443/", "https://user@localhost"),("https://example.com/reference?a=1#top", "https://example.com/reference?a=1"),
])
def test_an_address_is_compared_without_the_default_port_of_its_scheme_and_with_any_other_port(url, want):
    assert siteboard.same_address(url) == want


def test_a_reference_linked_with_the_default_port_matches_the_capture_the_browser_recorded_without_it(proj):
    edit_group(proj, "Ledger", swap('href="https://example.com/reference"', 'href="https://example.com:443/reference"', 3))
    r = lint(proj)
    assert r.returncode == 0, r.stdout
    assert {rows(proj)[f"group:Ledger:shot:{k}"]["status"] for k in (1, 2, 3)} == {"pass"}
    edit_group(proj, "Ledger", swap(":443/reference", ":8443/reference", 3))                      # another port is another site
    assert lint(proj).returncode == 0 and {rows(proj)[f"group:Ledger:shot:{k}"]["status"] for k in (1, 2, 3)} == {"warn"}


def test_a_screenshot_may_be_a_view_of_the_capture_and_not_only_its_thumbnail(proj):
    doc = json.loads(record_path(proj).read_text(encoding="utf-8"))
    doc["views"][0]["sha256"], doc["thumbs"][0]["sha256"] = sha(STYLE_TINY_PNG), "0" * 64
    record_path(proj).write_text(json.dumps(doc), encoding="utf-8")
    r = lint(proj)
    assert r.returncode == 0 and {v["status"] for v in shot_rows(proj).values()} == {"pass"}, r.stdout
    assert detail(proj, "group:Ledger:shot:1").startswith("1440.png of research/site-refs/example/capture.json")


def test_two_references_to_two_sites_each_match_the_capture_of_their_own_site(tmp_path):
    p = build(tmp_path)
    other = "https://example.net/other"
    write_site_capture(p, "other", other, picture=OTHER_PNG)
    edit_group(p, "Ledger", lambda block: block.replace('href="https://example.com/reference"', f'href="{other}"', 1).replace(STYLE_TINY_PNG, OTHER_PNG, 1))   # the first reference: another site, its picture
    r = lint(p)
    assert r.returncode == 0, r.stdout
    got = rows(p)
    assert got["group:Ledger:shot:1"]["status"] == "pass" and "research/site-refs/other/capture.json" in got["group:Ledger:shot:1"]["detail"], got["group:Ledger:shot:1"]
    assert got["group:Ledger:shot:2"]["status"] == "pass" and "research/site-refs/example/capture.json" in got["group:Ledger:shot:2"]["detail"]
    edit_group(p, "Ledger", swap(OTHER_PNG, STYLE_TINY_PNG))                                     # the first reference shows the other site's address with the first site's picture
    assert lint(p).returncode == 0
    assert rows(p)["group:Ledger:shot:1"]["status"] == "warn" and f"a capture of {ADDRESS}" in detail(p, "group:Ledger:shot:1")


def test_a_new_capture_makes_the_lint_stale(proj):
    assert lint(proj).returncode == 0
    inputs = [i["path"] for i in report(proj, "board-lint")["inputs"]]
    assert "research/site-refs/example/capture.json" in inputs, inputs
    bc("check", project=proj)
    row = lambda: next(x for x in report(proj, "check")["results"] if x["id"] == "report:board-lint")   # noqa: E731
    assert row()["status"] == "pass", row()
    mutate(record_path(proj), '"date": "2026-10-17"', '"date": "2026-10-18"')                    # captured again, a day later: the record the board was compared with changed
    bc("check", project=proj)
    got = row()
    assert got["status"] == "skipped" and "research/site-refs/example/capture.json changed" in got["detail"] and "brand-creator board-lint rounds/r2/board.html" in got["detail"], got


# ---- group:<name>:layout

def test_an_unknown_layout_id_fails_and_own_passes(proj):
    mutate(board_path(proj), *group_change(proj, "Ledger", swap('data-section="group" data-name="Ledger"', 'data-section="group" data-name="Ledger" data-layout="walkthrough"')))
    r = lint(proj)
    assert r.returncode == 0, r.stdout
    assert rows(proj)["group:Ledger:layout"]["status"] == "pass" and rows(proj)["group:Ledger:layout"]["detail"].startswith("walkthrough: "), rows(proj)["group:Ledger:layout"]
    mutate(board_path(proj), 'data-layout="walkthrough"', 'data-layout="nonsense"')
    r = lint(proj)
    assert r.returncode == 1 and set(failed(proj)) == {"group:Ledger:layout"}, r.stdout
    why = detail(proj, "group:Ledger:layout")
    assert "'nonsense'" in why and "walkthrough" in why and "catalogue" in why and "own:<word>" in why, why              # it names the known ids
    mutate(board_path(proj), 'data-layout="nonsense"', 'data-layout="own:ledger-way"')
    r = lint(proj)
    assert r.returncode == 0, r.stdout
    row = rows(proj)["group:Ledger:layout"]
    assert row["status"] == "warn" and "a layout of its own" in row["detail"] and "none of the references fits" in row["detail"], row


@pytest.mark.parametrize("value", ["", "Walkthrough", "own:", "own:Ledger", "own: x", "walkthrough catalogue"])
def test_a_layout_that_is_neither_an_id_nor_own_word_fails(proj, value):
    mutate(board_path(proj), *group_change(proj, "Atlas", swap('data-section="group" data-name="Atlas"', f'data-section="group" data-name="Atlas" data-layout="{value}"')))
    r = lint(proj)
    assert r.returncode == 1 and set(failed(proj)) == {"group:Atlas:layout"}, (failed(proj), r.stdout)


# ---- group:<name>:name

@pytest.mark.parametrize("bad", ["Option 2", "Group 2", "Group B", "Group II", "Cluster 3", "Set A", "Type #4", "Ab", "42", "Layout 3", "Layout B", "Layouts"])
def test_a_generic_group_name_fails(proj, bad):
    mutate(board_path(proj), *group_change(proj, "Ledger", swap('data-section="group" data-name="Ledger"', f'data-section="group" data-name="{bad}"')))
    r = lint(proj)
    assert r.returncode == 1 and set(failed(proj)) == {f"group:{bad}:name"}, (failed(proj), r.stdout)
    assert "word of 3+ letters" in detail(proj, f"group:{bad}:name")


@pytest.mark.parametrize("good", ["Settle", "Groupware", "Typeset", "Clusterfold", "Mill-race", "Layered"])
def test_a_word_that_only_starts_like_a_label_is_a_name(proj, good):
    edit_group(proj, "Ledger", swap('data-section="group" data-name="Ledger"', f'data-section="group" data-name="{good}"'))
    r = lint(proj)
    assert r.returncode == 0, r.stdout
    assert rows(proj)[f"group:{good}:name"]["status"] == "pass"


def test_two_groups_cannot_share_a_name_in_other_letters(proj):
    mutate(board_path(proj), *group_change(proj, "Quay", swap('data-section="group" data-name="Quay"', 'data-section="group" data-name="atlas"')))
    r = lint(proj)
    assert r.returncode == 1 and set(failed(proj)) == {"group:atlas:name"}, r.stdout
    assert detail(proj, "group:atlas:name") == "duplicate group name"
    assert rows(proj)["group:Atlas:name"]["status"] == "pass"                                   # the first of the two is the one that stands


def test_a_group_without_a_name_is_listed_by_its_place(proj):
    mutate(board_path(proj), *group_change(proj, "Harbour", swap('data-section="group" data-name="Harbour"', 'data-section="group" data-name=""')))
    r = lint(proj)
    assert r.returncode == 1 and {"group:#4:name", "groups:count"} <= set(failed(proj)), r.stdout


# ---- owner-sites:items

def test_an_owner_site_needs_like_or_dislike(proj):
    mutate(board_path(proj), '<li data-like="like">', '<li data-like="love">')
    r = lint(proj)
    assert r.returncode == 1 and failed(proj) == ["owner-sites:items"], r.stdout
    assert 'data-like is \'love\', it must be "like" or "dislike"' in detail(proj, "owner-sites:items") and "site 1 (" in detail(proj, "owner-sites:items")


def test_an_owner_site_without_data_like_fails(proj):
    mutate(board_path(proj), '<li data-like="dislike">', "<li>")
    r = lint(proj)
    assert r.returncode == 1 and failed(proj) == ["owner-sites:items"], r.stdout
    assert 'site 2 (' in detail(proj, "owner-sites:items") and 'no data-like ("like" or "dislike")' in detail(proj, "owner-sites:items")


def test_an_owner_site_needs_a_link_or_a_picture_and_a_reason(proj):
    mutate(board_path(proj), '<a href="https://example.com/reference">', '<a href="/reference">')   # the first link on the page is the first site the owner named
    mutate(board_path(proj), '<span data-field="why">', '<span data-removed="why">')                 # the template's own comment also names the field, so the span is what is changed
    r = lint(proj)
    assert r.returncode == 1 and failed(proj) == ["owner-sites:items"], r.stdout
    why = detail(proj, "owner-sites:items")
    assert "no http(s) link and no inlined image" in why and 'no reason (data-field="why" missing or empty' in why, why


def test_a_list_inside_a_reason_is_part_of_its_site_and_not_another_site(proj):
    page = board_path(proj).read_text(encoding="utf-8")
    old = f'<span data-field="why">{STYLE_STAND_IN}</span>'
    assert old in page
    board_path(proj).write_text(page.replace(old, '<div data-field="why"><ul><li>the order</li><li>the tone</li></ul></div>', 1), encoding="utf-8")
    r = lint(proj)
    assert r.returncode == 0, r.stdout
    assert rows(proj)["owner-sites:items"]["status"] == "pass" and "2 site(s): 1 liked, 1 disliked" in detail(proj, "owner-sites:items")


def test_an_owner_site_may_be_a_screenshot_the_owner_sent(proj):
    board = board_path(proj)
    board.write_text(board.read_text(encoding="utf-8").replace('<a href="https://example.com/reference">', f'<figure><img src="{STYLE_TINY_PNG}" alt="The site the owner sent"><figcaption>sent by the owner</figcaption></figure><a>', 1), encoding="utf-8")
    r = lint(proj)
    assert r.returncode == 0, r.stdout
    assert rows(proj)["owner-sites:items"]["status"] == "pass"


def test_an_owner_who_named_no_sites_passes_with_one_line(proj):
    page = board_path(proj).read_text(encoding="utf-8")
    block = re.search(r'    <ul class="owner-sites">.*?</ul>\n', page, re.S).group(0)
    board_path(proj).write_text(page.replace(block, "    <p>You named no sites, so these groups come from the research alone.</p>\n", 1), encoding="utf-8")
    r = lint(proj)
    assert r.returncode == 0, r.stdout
    assert rows(proj)["owner-sites:items"]["status"] == "pass" and "named none" in detail(proj, "owner-sites:items")


def test_an_owner_sites_section_with_no_text_fails_its_section_row_and_adds_no_items_row(proj):
    page = board_path(proj).read_text(encoding="utf-8")
    block = re.search(r'    <ul class="owner-sites">.*?</ul>\n', page, re.S).group(0)
    board_path(proj).write_text(page.replace(block, "", 1), encoding="utf-8")
    r = lint(proj)
    assert r.returncode == 1 and failed(proj) == ["section:owner-sites"], r.stdout
    assert "owner-sites:items" not in rows(proj)


# ---------------------------------------------------------------- is_site_refs_board (the page the site round waits for)

def test_a_page_counts_as_a_references_board_when_it_declares_its_round_and_holds_four_groups():
    page = board_text(rnd=2)
    assert is_site_refs_board(parse_dom(page), 2) is True
    assert is_site_refs_board(parse_dom(page), 3) is False                                      # a copy that still declares the round it came from
    assert is_site_refs_board(parse_dom(board_text(NAMES[:3], rnd=2)), 2) is False              # three groups
    assert is_site_refs_board(parse_dom(page.replace('data-board="site-refs"', 'data-board="style"')), 2) is False
    assert is_site_refs_board(None, 2) is False
