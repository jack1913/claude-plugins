"""The site board (data-board="site"), hero stage: a round after G4w that shows two or three variants of the site's first screen, one folder and one card each (scripts/boardlib/siteboard.py,
templates/site-board.html). Every row of the lint has a deliberate break here. The variants' pages are made by hand (a page that declares its layout and its id on <body>), and so are the page-check
report and the stills of each (helpers.page_check_report and helpers.capture_record write them in the shape of group 1's tools), so these tests need no browser."""
import base64
import re
import shutil
from pathlib import Path

import pytest
from helpers import (ROOT, bc, capture_record, failing, fill_site_board, fill_site_refs_board, fill_style_board, install_fixture, make_project, mutate, mutate_json, page_check_report,
                     report)

import siteboard
from boardpage import is_site_refs_board, page_kind, parse_dom
from pagecheck import tell_ids

TEMPLATE = ROOT / "templates" / "site-board.html"
REFS_TEMPLATE = ROOT / "templates" / "site-refs-board.html"
NAMES = ("Ledger", "Atlas")
THREE_CLICHES = ("# Acme: site clichés\n\n## Avoid unless argued\n\n"
                 "- a full-width photo with a headline laid over it\n- three equal tiles under the fold\n- a countdown that restarts for every visitor\n")
CARD = re.compile(r'      <article class="variant".*?</article>\n', re.S)


def page_text(name: str, layout: str = "walkthrough", page_id: str = "start") -> str:
    """The home page's first screen of a variant, as the site round makes it: it loads the tokens and declares its layout reference and its id on <body>."""
    return (f'<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><title>{name}</title>'
            f'<link rel="stylesheet" href="../../../assets/tokens/tokens.css"></head>\n<body data-layout="{layout}" data-page="{page_id}"><h1>{name}</h1></body></html>\n')


def settle(p: Path, rnd: int, name: str, status: str = "pass", tells: tuple[str, ...] = ()) -> None:
    """The page-check report and the stills of a variant's page as it is now: what `brand-creator page-check` and `brand-creator capture` leave behind after a change to the page."""
    page = f"rounds/r{rnd}/{name}/index.html"
    page_check_report(p, page, status, tells)
    capture_record(p, page)


def make_variant(p: Path, rnd: int, name: str, layout: str = "walkthrough", page_id: str = "start") -> Path:
    """The folder of a variant: its page, and the page-check report and the stills that belong to the page as written."""
    page = p / "rounds" / f"r{rnd}" / name / "index.html"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(page_text(name, layout, page_id), encoding="utf-8")
    settle(p, rnd, name)
    return page


def board_text(names=NAMES, rnd: int = 2, **kw) -> str:
    return fill_site_board(TEMPLATE.read_text(encoding="utf-8"), names, rnd=rnd, **kw)


def add_round(p: Path, rnd: int, names=NAMES, *, first: bool = True, stage: str = "hero", **kw) -> Path:
    """A site board in round `rnd` with a folder and a page for each variant (a pages board has no variant folders)."""
    if stage == "hero":
        for n in names:
            make_variant(p, rnd, n)
    board = p / "rounds" / f"r{rnd}" / "board.html"
    board.parent.mkdir(parents=True, exist_ok=True)
    board.write_text(board_text(names, rnd, first=first, stage=stage, **kw), encoding="utf-8")
    return board


def add_references_board(p: Path, rnd: int, names=("Ledger", "Atlas", "Quay", "Harbour")) -> Path:
    board = p / "rounds" / f"r{rnd}" / "board.html"
    board.parent.mkdir(parents=True, exist_ok=True)
    board.write_text(fill_site_refs_board(REFS_TEMPLATE.read_text(encoding="utf-8"), names, rnd=rnd), encoding="utf-8")
    return board


def build(tmp_path, *, tier: str = "standard", g4: bool = True, g4w: str | None = "skipped by owner", surfaces: str | None = "site, social", names=NAMES, rnd: int = 2,
          board: bool = True) -> Path:
    """A project ready for a hero board: Standard, G3 and G4 recorded, G4w skipped by the owner, the online-research answer, a brief that lists a site, three site clichés, the tokens' stylesheet and,
    in round `rnd`, a hero board with one folder and one page per variant. Each keyword leaves one of those out or changes it (a purpose-built input for a failing case)."""
    p = make_project(tmp_path, tier=tier)
    install_fixture(p, tokens=False, logo=False, qa=False)
    for gate, text in (("G3", "approved r1 (test)"), ("G4", "approved system rules (test)"), ("G4w", g4w)):
        if text and (gate != "G4" or g4):
            assert bc("state", "--record", gate, text, project=p).returncode == 0
    assert bc("state", "--set", "site_research=online", project=p).returncode == 0
    if surfaces is not None:
        brief = p / "brief" / "BRIEF.md"
        text = brief.read_text(encoding="utf-8")
        line = "- Required surfaces: (site, app icon, social, print, packaging, ...)"
        assert line in text
        brief.write_text(text.replace(line, f"- Required surfaces: {surfaces}"), encoding="utf-8")
    (p / "research").mkdir(exist_ok=True)
    (p / "research" / "site-cliches.md").write_text(THREE_CLICHES, encoding="utf-8")
    (p / "assets" / "tokens").mkdir(parents=True, exist_ok=True)
    (p / "assets" / "tokens" / "tokens.css").write_text(":root{--color-bg:#ffffff;--color-text:#16191d}\n", encoding="utf-8")
    if board:
        add_round(p, rnd, names)
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


def board_of(p: Path, rnd: int = 2) -> Path:
    return p / "rounds" / f"r{rnd}" / "board.html"


# ---------------------------------------------------------------- the template and a finished hero board

def test_a_filled_hero_board_passes(proj):
    r = lint(proj)
    assert r.returncode == 0, r.stdout
    got = rows(proj)
    for rid in ("page:data-board", "page:unfilled", "page:votes", "page:site-stage", "site:tier", "site:brief", "site:g4", "site:g4w", "site:variants", "site:files", "site:layout", "site:fields", "site:check", "site:tells", "site:stills",
                "section:hardest-surface", "section:my-call", "section:questions", "section:reply"):
        assert got[rid]["status"] == "pass", (rid, got[rid])
    assert got["page:data-board"]["detail"] == "site" and got["page:site-stage"]["detail"] == "hero"
    assert "2 variant(s): Ledger, Atlas" in got["site:variants"]["detail"]
    assert not [x for x in got if x.startswith(("direction", "map:", "masters", "project:", "motion:", "site-refs:", "groups:"))], "no direction, map, style gate, inventory, kept master, motion or references row on a site board"
    assert got["section:what-changed"]["status"] == "info" and got["section:weak-points"]["status"] == "info"   # the first hero board of the project needs neither


def test_the_template_as_it_is_fails_until_filled(proj):
    src = TEMPLATE.read_text(encoding="utf-8")
    for needle in ('data-board="site"', 'data-site-stage="hero"', 'data-section="what-changed"', 'data-section="hardest-surface"', 'data-section="weak-points"', 'data-section="my-call"',
                   'data-section="questions"', 'data-section="reply"', "data-site-variant=", 'data-field="still"', 'data-view="1440-light"', 'data-view="1440-dark"', 'data-view="390-light"',
                   'data-view="390-dark"', 'data-field="live"', "data-check=", 'data-field="tells"', 'data-field="reflex"', 'data-field="layout"', "data-layout=", 'data-field="from-refs"',
                   "data-cold=", 'data-field="what-it-is"', 'data-field="cost"', "data-vote=", 'name="vote-[[fill: Name one]]"', 'data-section="choices"', "data-choice=", 'data-tag="rule"',
                   'data-tag="example"', "@media (prefers-reduced-motion:reduce)", ".variant[hidden]{display:none}", "articles for variants two and three"):
        assert needle in src, needle
    board_of(proj).write_text(src, encoding="utf-8")
    r = lint(proj)
    assert r.returncode == 1 and "page:unfilled" in failed(proj), r.stdout
    assert rows(proj)["site:g4"]["status"] == "pass"            # the gates are the project's, not the page's


def test_the_pages_stage_blocks_wait_in_a_comment_and_cost_a_hero_board_nothing(proj):
    """The choices section of the pages stage is in an HTML comment of the template: a filled hero board carries no section of it, and a marker in it is no unfilled marker."""
    page = board_of(proj).read_text(encoding="utf-8")
    assert 'data-section="choices"' not in re.sub(r"<!--.*?-->", "", page, flags=re.S)
    assert 'data-section="choices"' in TEMPLATE.read_text(encoding="utf-8")
    assert lint(proj).returncode == 0 and rows(proj)["page:unfilled"]["status"] == "pass"


def test_the_template_has_the_frame_of_the_motion_board_and_no_network_address():
    text = TEMPLATE.read_text(encoding="utf-8")
    motion = (ROOT / "templates" / "motion-board.html").read_text(encoding="utf-8")
    for frame in ('<meta name="color-scheme" content="light dark">', ':root[data-theme="dark"]', "--sans:ui-sans-serif,system-ui", 'id="reply-out"', 'id="copy-reply"', "?t=light|dark", "?v=Name"):
        assert frame in text and frame in motion, frame
    assert not re.search(r"""(?:src|href)\s*=\s*["']?(?:https?:)?//""", text)
    body = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    assert "http://" not in body and "https://" not in re.sub(r"\[\[fill:[^\]]*\]\]", "", body)


def test_the_filled_board_gives_each_variant_a_vote_group_of_its_own(proj):
    page = board_of(proj).read_text(encoding="utf-8")
    for name in NAMES:
        assert f'data-vote="{name}"' in page and f'name="vote-{name}"' in page, name
    assert lint(proj).returncode == 0 and rows(proj)["page:votes"]["status"] == "pass"


def test_the_four_stills_of_a_card_are_the_four_views_of_capture(proj):
    page = board_of(proj).read_text(encoding="utf-8")
    for name in NAMES:
        for view in ("1440-light", "1440-dark", "390-light", "390-dark"):
            assert f'data-view="{view}" src="{name}/shots/{view}.png"' in page, (name, view)


# ---------------------------------------------------------------- site:tier, site:brief, site:g4

def test_a_site_board_needs_standard_or_full(proj):
    mutate(proj / "BRAND-STATE.md", "tier: standard", "tier: quick")
    r = lint(proj)
    assert r.returncode == 1 and "site:tier" in failed(proj), r.stdout
    assert "Standard and Full" in detail(proj, "site:tier") and "quick" in detail(proj, "site:tier")


def test_a_site_board_is_allowed_in_the_full_tier(tmp_path):
    p = build(tmp_path, tier="full")
    assert lint(p).returncode == 0, lint(p).stdout
    assert detail(p, "site:tier") == "tier: full"


def test_a_site_board_needs_a_site_in_the_brief(proj):
    mutate(proj / "brief" / "BRIEF.md", "- Required surfaces: site, social", "- Required surfaces: app icon, social")
    r = lint(proj)
    assert r.returncode == 1 and "site:brief" in failed(proj), r.stdout
    why = detail(proj, "site:brief")
    assert "lists a site under Required surfaces" in why and "ask the owner" in why and "app icon, social" in why, why


def test_the_untouched_brief_template_line_is_no_site_for_the_site_round(tmp_path):
    p = build(tmp_path, surfaces=None)
    r = lint(p)
    assert r.returncode == 1 and "site:brief" in failed(p), r.stdout
    assert "(site, app icon, social, print, packaging, ...)" in detail(p, "site:brief") and "template" in detail(p, "site:brief")


def test_a_polish_brief_counts_strona_as_a_site_for_the_site_round(tmp_path):
    p = build(tmp_path, surfaces="strona www, social")
    assert lint(p).returncode == 0
    assert rows(p)["site:brief"]["status"] == "pass" and "strona" in detail(p, "site:brief")


def test_a_site_board_waits_for_g4(tmp_path):
    p = build(tmp_path, g4=False)
    r = lint(p)
    assert r.returncode == 1 and "site:g4" in failed(p), r.stdout
    assert "after the system rules (G4)" in detail(p, "site:g4") and "state --record G4" in detail(p, "site:g4")


# ---------------------------------------------------------------- site:g4w

def test_a_site_board_waits_for_g4w(tmp_path):
    p = build(tmp_path, g4w=None)
    r = lint(p)
    assert r.returncode == 1 and "site:g4w" in failed(p), r.stdout
    why = detail(p, "site:g4w")
    assert "G4w" in why and "state --record G4w" in why and "skipped by owner" in why and "/brand-creator:round site-refs" in why, why


def test_a_skip_in_the_owners_words_lets_the_site_board_through(tmp_path):
    p = build(tmp_path, g4w="skipped by owner: I know the sites I want")
    assert lint(p).returncode == 0
    assert rows(p)["site:g4w"]["status"] == "pass" and detail(p, "site:g4w").endswith("skipped by owner: I know the sites I want")


def test_a_picked_g4w_needs_an_earlier_references_board(tmp_path):
    p = build(tmp_path, g4w="picked Ledger; likes none; dislikes none")
    r = lint(p)
    assert r.returncode == 1 and "site:g4w" in failed(p), r.stdout
    assert "G4w names a pick but no website references board came before this round" in detail(p, "site:g4w")


def test_a_picked_g4w_passes_with_a_references_board_in_an_earlier_round(tmp_path):
    p = build(tmp_path, g4w="picked Ledger; likes none; dislikes none", board=False)
    add_references_board(p, 2)
    add_round(p, 3)
    r = lint(p, "rounds/r3/board.html")
    assert r.returncode == 0, r.stdout
    assert detail(p, "site:g4w") == "G4w: 2026-10-17 picked Ledger; likes none; dislikes none; the references board is r2"
    assert "rounds/r2/board.html" in [i["path"] for i in report(p, "board-lint")["inputs"]]   # a change to the references board makes the lint report stale


def test_a_references_board_that_does_not_count_or_comes_later_is_no_pick_to_stand_on(tmp_path):
    p = build(tmp_path, g4w="picked Ledger", board=False)
    add_references_board(p, 2, names=("Ledger", "Atlas", "Quay"))                          # three groups: not a references board
    add_round(p, 3)
    r = lint(p, "rounds/r3/board.html")
    assert r.returncode == 1 and "site:g4w" in failed(p), r.stdout
    add_references_board(p, 2)
    assert is_site_refs_board(parse_dom(board_of(p, 2).read_text(encoding="utf-8")), 2)
    add_references_board(p, 4)                                                              # a references board after this round does not come before it
    assert lint(p, "rounds/r3/board.html").returncode == 0 and detail(p, "site:g4w").endswith("the references board is r2")
    board_of(p, 2).unlink()
    (p / "rounds" / "r2").rmdir()
    r = lint(p, "rounds/r3/board.html")
    assert r.returncode == 1 and "G4w names a pick but no website references board came before this round" in detail(p, "site:g4w"), r.stdout


# ---------------------------------------------------------------- site:variants

def test_the_first_site_board_shows_two_or_three_heroes(tmp_path):
    three = build(tmp_path / "three", names=("Ledger", "Atlas", "Quay"))
    assert lint(three).returncode == 0 and "3 variant(s): Ledger, Atlas, Quay" in detail(three, "site:variants")
    cards = CARD.findall(board_of(three).read_text(encoding="utf-8"))
    assert len(cards) == 3
    mutate(board_of(three), cards[-1], cards[-1] + cards[-1].replace("Quay", "Harbour"))      # a fourth card
    make_variant(three, 2, "Harbour")
    r = lint(three)
    assert r.returncode == 1 and "site:variants" in failed(three), r.stdout
    assert "4 variant card(s) found, the first hero board of a project shows 2 or 3" in detail(three, "site:variants")
    two = build(tmp_path / "two")
    cards = CARD.findall(board_of(two).read_text(encoding="utf-8"))
    mutate(board_of(two), cards[-1], "")                                                      # one card
    r = lint(two)
    assert r.returncode == 1 and "site:variants" in failed(two), r.stdout
    assert "1 variant card(s) found" in detail(two, "site:variants")


def test_a_later_hero_board_shows_one_or_more_heroes_and_needs_what_changed_and_weak_points(tmp_path):
    p = build(tmp_path)                                                                       # r2: the first hero board
    add_round(p, 3, ("Ledger",), first=False)
    r = lint(p, "rounds/r3/board.html")
    assert r.returncode == 0, r.stdout
    got = rows(p)
    assert got["section:what-changed"]["status"] == "pass" and got["section:weak-points"]["status"] == "pass"
    assert detail(p, "site:variants") == "1 variant(s): Ledger"
    mutate(board_of(p, 3), 'data-section="weak-points"', 'data-removed="weak-points"')
    r = lint(p, "rounds/r3/board.html")
    assert r.returncode == 1 and "section:weak-points" in failed(p), r.stdout
    mutate(board_of(p, 3), 'data-section="what-changed"', 'data-removed="what-changed"')
    r = lint(p, "rounds/r3/board.html")
    assert r.returncode == 1 and {"section:what-changed", "section:weak-points"} <= set(failed(p)), r.stdout
    add_round(p, 4, (), first=False)
    r = lint(p, "rounds/r4/board.html")
    assert r.returncode == 1 and "no variant card found, a later hero board shows 1 or more" in detail(p, "site:variants"), r.stdout


@pytest.mark.parametrize("card_name, why", [("Variant 2", "must be a word of 3+ letters"), ("Option B", "must be a word of 3+ letters"), ("A", "must be a word of 3+ letters"),
                                           ("Atlas 2", "letters, digits, - and _ only"), ("Atl/as", "letters, digits, - and _ only")])
def test_a_variant_name_is_a_word_that_is_not_a_label_and_can_be_a_folder_name(proj, card_name, why):
    mutate(board_of(proj), 'data-site-variant="Atlas"', f'data-site-variant="{card_name}"')
    r = lint(proj)
    assert r.returncode == 1 and "site:variants" in failed(proj), r.stdout
    assert why in detail(proj, "site:variants") and card_name in detail(proj, "site:variants")


def test_two_variants_cannot_share_a_name_even_in_other_letters(proj):
    mutate(board_of(proj), 'data-site-variant="Atlas"', 'data-site-variant="ledger"')
    r = lint(proj)
    assert r.returncode == 1 and "site:variants" in failed(proj), r.stdout
    assert "ledger: duplicate variant name" in detail(proj, "site:variants")


# ---------------------------------------------------------------- site:files

def test_a_variant_needs_its_folder_and_its_page(tmp_path):
    p = build(tmp_path)
    (p / "rounds" / "r2" / "Atlas" / "index.html").unlink()
    r = lint(p)
    assert r.returncode == 1 and "site:files" in failed(p), r.stdout
    assert "Atlas: rounds/r2/Atlas/index.html is missing" in detail(p, "site:files")
    shutil.rmtree(p / "rounds" / "r2" / "Atlas")                                              # the stills of `capture` were in shots/
    r = lint(p)
    assert r.returncode == 1 and "Atlas: rounds/r2/Atlas/ does not exist" in detail(p, "site:files"), r.stdout


def test_a_variant_page_must_declare_its_layout_and_page(proj):
    page = proj / "rounds" / "r2" / "Atlas" / "index.html"
    mutate(page, 'data-layout="walkthrough" data-page="start"', 'data-page="start"')
    r = lint(proj)
    assert r.returncode == 1 and {"site:files", "site:layout"} <= set(failed(proj)), r.stdout
    assert "Atlas: the <body> of rounds/r2/Atlas/index.html declares no data-layout" in detail(proj, "site:files")
    assert "Atlas: the page declares no data-layout" in detail(proj, "site:layout")
    mutate(page, '<body data-page="start">', '<body data-layout="walkthrough">')
    r = lint(proj)
    assert r.returncode == 1 and "site:files" in failed(proj) and "Atlas: the <body> of rounds/r2/Atlas/index.html declares no data-page" in detail(proj, "site:files"), r.stdout
    mutate(page, '<body data-layout="walkthrough">', '<body data-layout="walkthrough" data-page="Start Page">')
    r = lint(proj)
    assert r.returncode == 1 and "data-page 'Start Page'" in detail(proj, "site:files") and "is not a page id" in detail(proj, "site:files"), r.stdout
    mutate(page, '<body data-layout="walkthrough" data-page="Start Page">', "<body>")
    assert lint(proj).returncode == 1 and "declares no data-layout" in detail(proj, "site:files") and "declares no data-page" in detail(proj, "site:files")


def test_a_variant_page_without_a_body_tag_fails_the_files_row(proj):
    (proj / "rounds" / "r2" / "Atlas" / "index.html").write_text("<!doctype html><title>Atlas</title><h1>Atlas</h1>\n", encoding="utf-8")
    r = lint(proj)
    assert r.returncode == 1 and "site:files" in failed(proj), r.stdout
    assert "has no <body> tag" in detail(proj, "site:files")


def test_a_card_spelt_unlike_its_folder_fails(proj):
    """A disk that does not tell letter cases apart (macOS, Windows) opens rounds/r2/Atlas/ for a folder called atlas, so a card Atlas over it would pass there. The lint reads the listing of the round's
    folder, so both kinds of disk fail the same row in the same words, and renaming the folder back is the fix on either."""
    rnd = proj / "rounds" / "r2"
    (rnd / "Atlas").rename(rnd / "atlas")
    listed = [e.name for e in rnd.iterdir()]
    assert "atlas" in listed and "Atlas" not in listed
    r = lint(proj)
    assert r.returncode == 1 and "site:files" in failed(proj), r.stdout
    why = detail(proj, "site:files")
    assert why.startswith("Atlas: the card and its folder must be spelt alike, letter case included") and "the card says Atlas" in why and "rounds/r2/atlas/" in why, why
    assert "does not exist" not in why, why
    (rnd / "atlas").rename(rnd / "Atlas")
    assert lint(proj).returncode == 0


def test_the_live_link_of_a_card_leads_to_its_page(proj):
    mutate(board_of(proj), '<a data-field="live" href="Atlas/index.html">', '<a data-field="live" href="Ledger/index.html">')
    r = lint(proj)
    assert r.returncode == 1 and "site:files" in failed(proj), r.stdout
    assert "Atlas: the live link 'Ledger/index.html' does not lead to rounds/r2/Atlas/index.html" in detail(proj, "site:files")
    mutate(board_of(proj), '<a data-field="live" href="Ledger/index.html">', '<a data-field="live" href="">')
    r = lint(proj)
    assert r.returncode == 1 and "the card has no link to the live page" in detail(proj, "site:files"), r.stdout


# ---------------------------------------------------------------- site:layout

def test_an_unknown_layout_fails_and_an_own_layout_warns(proj):
    page = proj / "rounds" / "r2" / "Ledger" / "index.html"
    mutate(page, 'data-layout="walkthrough"', 'data-layout="carousel"')
    mutate(board_of(proj), 'data-field="layout" data-layout="walkthrough"', 'data-field="layout" data-layout="carousel"')
    r = lint(proj)
    assert r.returncode == 1 and "site:layout" in failed(proj), r.stdout
    why = detail(proj, "site:layout")
    assert "Ledger: data-layout 'carousel' is no id of page-layouts.json" in why and "walkthrough" in why and "no own:<word>" in why, why
    mutate(page, 'data-layout="carousel"', 'data-layout="own:ledger"')
    mutate(board_of(proj), 'data-field="layout" data-layout="carousel"', 'data-field="layout" data-layout="own:ledger"')
    settle(proj, 2, "Ledger")                                                                  # the page changed: check it and capture it again
    r = lint(proj)
    assert r.returncode == 0, r.stdout
    assert rows(proj)["site:layout"]["status"] == "warn" and "Ledger: a layout of its own (own:ledger): say on the card why none of the references fit" in detail(proj, "site:layout")


def test_every_layout_reference_of_the_plugin_passes_and_an_own_word_must_be_a_word(proj):
    from sitedata import load_layouts
    page = proj / "rounds" / "r2" / "Ledger" / "index.html"
    previous = "walkthrough"
    for layout in load_layouts():
        mutate(page, f'data-layout="{previous}"', f'data-layout="{layout}"')
        mutate(board_of(proj), f'data-field="layout" data-layout="{previous}"', f'data-field="layout" data-layout="{layout}"')
        previous = layout
        settle(proj, 2, "Ledger")
        assert lint(proj).returncode == 0 and rows(proj)["site:layout"]["status"] == "pass", layout
    mutate(page, f'data-layout="{previous}"', 'data-layout="own:"')
    mutate(board_of(proj), f'data-field="layout" data-layout="{previous}"', 'data-field="layout" data-layout="own:"')
    r = lint(proj)
    assert r.returncode == 1 and "site:layout" in failed(proj), r.stdout


def test_a_card_that_says_another_layout_than_its_page_fails(proj):
    mutate(board_of(proj), 'data-field="layout" data-layout="walkthrough"', 'data-field="layout" data-layout="catalogue"')
    r = lint(proj)
    assert r.returncode == 1 and "site:layout" in failed(proj), r.stdout
    assert "Ledger: the card says data-layout 'catalogue' and the page says 'walkthrough'" in detail(proj, "site:layout")


def test_a_card_without_a_layout_line_fails(proj):
    mutate(board_of(proj), 'data-field="layout" data-layout="walkthrough"', 'data-removed="layout" data-layout="walkthrough"')
    r = lint(proj)
    assert r.returncode == 1 and "site:layout" in failed(proj) and "Ledger: the card has no layout line" in detail(proj, "site:layout"), r.stdout


# ---------------------------------------------------------------- site:fields

@pytest.mark.parametrize("field, label", [("what-it-is", "What it is"), ("cost", "Cost"), ("from-refs", "Takes from")])
def test_a_card_says_what_it_is_what_it_takes_and_what_it_costs(proj, field, label):
    assert lint(proj).returncode == 0
    mutate(board_of(proj), f'data-field="{field}"', f'data-removed="{field}"')
    r = lint(proj)
    assert r.returncode == 1 and "site:fields" in failed(proj), r.stdout
    assert f"Ledger: {label} is missing or empty" in detail(proj, "site:fields")


def test_a_field_belongs_to_its_own_card(proj):
    """Ledger's cost is not Atlas's: a field is read inside its card only."""
    board = board_of(proj)
    cards = CARD.findall(board.read_text(encoding="utf-8"))
    assert len(cards) == 2
    stripped = cards[1].replace('data-field="cost"', 'data-removed="cost"')
    board.write_text(board.read_text(encoding="utf-8").replace(cards[1], stripped), encoding="utf-8")
    r = lint(proj)
    assert r.returncode == 1 and "site:fields" in failed(proj) and "Atlas: Cost is missing or empty" in detail(proj, "site:fields") and "Ledger" not in detail(proj, "site:fields")


# ---------------------------------------------------------------- page:data-board, page:site-stage

@pytest.mark.parametrize("rnd", [0, 1])
def test_a_site_board_is_round_2_or_later(tmp_path, rnd):
    p = build(tmp_path, board=False)
    add_round(p, rnd)
    r = lint(p, f"rounds/r{rnd}/board.html")
    assert r.returncode == 1 and "page:data-board" in failed(p), r.stdout
    assert "a site board is a round of its own from round 2 on" in detail(p, "page:data-board")


def test_a_site_board_is_never_a_reset_round(proj):
    assert bc("state", "--set", "reset_rounds=[2]", project=proj).returncode == 0
    r = lint(proj)
    assert r.returncode == 1 and "page:data-board" in failed(proj), r.stdout
    assert "listed in reset_rounds" in detail(proj, "page:data-board") and "a site board is a round of its own from round 2 on" in detail(proj, "page:data-board")


def test_a_data_board_that_is_none_of_the_kinds_names_site_among_them(proj):
    board_of(proj).write_text(board_text().replace('data-board="site"', 'data-board="sites"'), encoding="utf-8")
    r = lint(proj)
    assert r.returncode == 1 and "pick|refine|style|motion|site-refs|site" in detail(proj, "page:data-board")


def test_a_site_board_without_a_stage_fails(proj):
    mutate(board_of(proj), 'data-board="site" data-site-stage="hero"', 'data-board="site"')
    r = lint(proj)
    assert r.returncode == 1 and "page:site-stage" in failed(proj), r.stdout
    assert 'data-site-stage="hero|pages"' in detail(proj, "page:site-stage") and "missing" in detail(proj, "page:site-stage")
    assert "site:variants" not in rows(proj), "no variant row is read at an unknown stage"
    mutate(board_of(proj), 'data-board="site"', 'data-board="site" data-site-stage="intro"')
    r = lint(proj)
    assert r.returncode == 1 and 'data-site-stage="intro" is not "hero" or "pages"' in detail(proj, "page:site-stage"), r.stdout


def test_the_stage_is_read_from_the_element_that_declares_the_kind(proj):
    """data-site-stage on another element than the one that declares data-board is no stage."""
    mutate(board_of(proj), '<body data-round="2" data-board="site" data-site-stage="hero">', '<body data-round="2" data-board="site"><div data-site-stage="hero"></div>')
    r = lint(proj)
    assert r.returncode == 1 and "page:site-stage" in failed(proj), r.stdout


def test_the_pages_stage_is_not_read_yet_and_the_lint_says_so(tmp_path):
    p = build(tmp_path)
    add_round(p, 3, stage="pages")
    r = lint(p, "rounds/r3/board.html")
    assert r.returncode == 3, r.stdout                                                         # exit 3: not verified, never a pass
    got = rows(p)
    assert got["page:site-stage"]["detail"] == "pages" and got["site:pages-stage"]["status"] == "skipped" and "does not read the pages stage yet" in got["site:pages-stage"]["detail"]
    assert "site:variants" not in got and got["section:what-changed"]["status"] == "info", "the first board of the pages stage needs no What changed, whatever stage came before"


def test_a_board_is_the_first_of_its_own_stage(tmp_path):
    p = build(tmp_path)
    add_round(p, 3, stage="pages")
    assert siteboard.is_first(p, 2, "hero") is True and siteboard.is_first(p, 3, "pages") is True and siteboard.is_first(p, 3, "hero") is False
    add_round(p, 4, ("Ledger",), first=False)
    assert siteboard.is_first(p, 4, "hero") is False and siteboard.is_first(p, 4, "pages") is False
    assert siteboard.stage_of(parse_dom(board_of(p, 3).read_text(encoding="utf-8"))) == "pages" and page_kind(parse_dom(board_of(p, 4).read_text(encoding="utf-8"))) == "site"


# ---------------------------------------------------------------- the style gate, the sections, the inputs

def test_the_style_gate_never_counts_a_site_board_as_the_rejected_round(tmp_path):
    """r1 pick (rejected), r2 style (reset), r3 a site board, r4 pick (reset): the rejected round is r1, and the style board of r2 comes after it. If a site board counted as a round the owner
    rejected, the new style board would have to come after r3 and the pick of r4 would fail."""
    proj = build(tmp_path, board=False)
    style = proj / "rounds" / "r2" / "board.html"
    style.parent.mkdir()
    style.write_text(fill_style_board((ROOT / "templates" / "style-board.html").read_text(encoding="utf-8")).replace('data-round="0"', 'data-round="2"'), encoding="utf-8")
    assert bc("state", "--record", "G1s", "picked Ember", project=proj).returncode == 0
    add_round(proj, 3)
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


def test_a_site_board_is_no_style_board_for_the_style_pick(proj):
    """`state --record G1s` writes g1s_round, the highest round whose board is a style board: a site board is not one."""
    assert bc("state", "--record", "G1s", "picked Ember", project=proj).returncode == 0
    assert bc("state", "--get", "g1s_round", project=proj).returncode == 1                   # no style board on disk: the key is not there


@pytest.mark.parametrize("section", ["hardest-surface", "my-call", "questions", "reply"])
def test_the_sections_every_board_has_are_required_on_a_site_board(proj, section):
    mutate(board_of(proj), f'data-section="{section}"', f'data-removed="{section}"')
    r = lint(proj)
    assert r.returncode == 1 and f"section:{section}" in failed(proj), r.stdout


def test_the_questions_of_a_site_board_follow_the_rules_of_every_board(proj):
    mutate(board_of(proj), '<li data-option="a" data-recommended="true"><label><input type="radio" name="q1"', '<li data-option="a"><label><input type="radio" name="q1"')
    r = lint(proj)
    assert r.returncode == 1 and "question:1:options" in failed(proj), r.stdout


def test_a_site_board_whose_variants_share_a_vote_group_fails_page_votes(proj):
    mutate(board_of(proj), 'name="vote-Atlas"', 'name="vote-Ledger"', count=3)
    r = lint(proj)
    assert r.returncode == 1 and "page:votes" in failed(proj), r.stdout


def test_min_directions_is_not_used_on_a_site_board(proj):
    r = lint(proj, "rounds/r2/board.html", "--min-directions", "3")
    assert r.returncode == 0, r.stdout
    assert rows(proj)["directions:count"]["status"] == "info" and "not used" in detail(proj, "directions:count")


def test_the_lint_report_lists_the_brief_and_each_variant_page_as_inputs_and_goes_stale_with_them(proj):
    from _common import stale_inputs
    assert lint(proj).returncode == 0
    doc = report(proj, "board-lint")
    paths = [i["path"] for i in doc["inputs"]]
    for want in ("brief/BRIEF.md", "rounds/r2/board.html", "rounds/r2/Ledger/index.html", "rounds/r2/Atlas/index.html"):
        assert want in paths, (want, paths)
    assert stale_inputs(proj, doc) == []
    (proj / "rounds" / "r2" / "Atlas" / "index.html").write_text(page_text("Atlas") + "<!-- changed -->\n", encoding="utf-8")
    assert stale_inputs(proj, doc), "a page changed after the lint makes the report stale"


# ---------------------------------------------------------------- site:check, site:tells, site:stills: the proof each variant brings

VIEWS = ("1440-light", "1440-dark", "390-light", "390-dark")


def page_of(name: str, rnd: int = 2) -> str:
    return f"rounds/r{rnd}/{name}/index.html"


def check_report_of(p: Path, name: str, rnd: int = 2) -> Path:
    from pagecheck import report_tool
    return p / "assets" / "_checks" / (report_tool(page_of(name, rnd)) + ".json")


def shots_of(p: Path, name: str, rnd: int = 2) -> Path:
    return p / "rounds" / f"r{rnd}" / name / "shots"


def inline_stills(text: str, p: Path, other: dict | None = None, rnd: int = 2) -> str:
    """The copy of a board published on a review surface: every still by a relative path becomes a data: URI of the same file (of other bytes for the paths in `other`)."""
    def data(m: "re.Match[str]") -> str:
        raw = (other or {}).get(m.group(1)) or (p / "rounds" / f"r{rnd}" / m.group(1)).read_bytes()
        return 'src="data:image/png;base64,' + base64.b64encode(raw).decode() + '"'
    out, n = re.subn(r'src="([A-Za-z0-9_-]+/shots/[0-9a-z-]+\.png)"', data, text)
    assert n >= 4, n
    return out


def test_a_variant_without_a_page_check_report_fails(proj):
    check_report_of(proj, "Atlas").unlink()
    r = lint(proj)
    assert r.returncode == 1 and "site:check" in failed(proj), r.stdout
    why = detail(proj, "site:check")
    assert "Atlas: no page-check report of rounds/r2/Atlas/index.html: run `brand-creator page-check rounds/r2/Atlas/index.html`" in why and "Ledger" not in why, why
    assert rows(proj)["site:tells"]["status"] == "skipped" and "no current page-check verdict to read the tells from for Atlas" in detail(proj, "site:tells")


def test_the_report_of_a_page_is_found_by_the_pages_path(proj):
    from pagecheck import report_tool
    f = check_report_of(proj, "Ledger")
    assert f.is_file() and f.relative_to(proj).as_posix().startswith("assets/_checks/page-check/index-")
    assert f == proj / "assets" / "_checks" / (report_tool("rounds/r2/Ledger/index.html") + ".json")
    assert report_tool("rounds/r2/Ledger/index.html") != report_tool("rounds/r2/Atlas/index.html") != report_tool("rounds/r3/Atlas/index.html")
    assert report(proj, report_tool("rounds/r2/Ledger/index.html"))["target"] == {"kind": "project", "page": "rounds/r2/Ledger/index.html", "from": None, "url": None}


def test_a_page_changed_after_its_page_check_fails(proj):
    mutate(proj / page_of("Atlas"), "<h1>Atlas</h1>", "<h1>Atlas, longer</h1>")
    r = lint(proj)
    assert r.returncode == 1 and {"site:check", "site:stills"} <= set(failed(proj)), r.stdout
    assert "Atlas: the page-check report is stale (rounds/r2/Atlas/index.html changed): run `brand-creator page-check rounds/r2/Atlas/index.html`" in detail(proj, "site:check")
    page_check_report(proj, page_of("Atlas"))                                                  # checked again: the report is current, the stills are not
    r = lint(proj)
    assert r.returncode == 1 and failed(proj) == ["site:stills"], r.stdout
    capture_record(proj, page_of("Atlas"))
    assert lint(proj).returncode == 0


def test_a_changed_tokens_stylesheet_makes_the_check_and_the_stills_stale(proj):
    mutate(proj / "assets" / "tokens" / "tokens.css", "#16191d", "#16191e")
    r = lint(proj)
    assert r.returncode == 1 and {"site:check", "site:stills"} <= set(failed(proj)), r.stdout
    assert "assets/tokens/tokens.css changed" in detail(proj, "site:check") and "assets/tokens/tokens.css changed" in detail(proj, "site:stills")


def test_a_card_that_shows_pass_for_a_failing_check_fails(proj):
    settle(proj, 2, "Atlas", "fail")
    board_of(proj).write_text(board_text(checks={"Atlas": "fail"}), encoding="utf-8")
    mutate(board_of(proj), '<p class="check" data-check="fail">', '<p class="check" data-check="pass">')
    r = lint(proj)
    assert r.returncode == 1 and "site:check" in failed(proj), r.stdout
    assert 'Atlas: the card says data-check="pass" and the page-check report says fail' in detail(proj, "site:check")
    mutate(board_of(proj), '<p class="check" data-check="pass">', '<p class="check" data-check="fail">')    # the first card (Ledger) says fail for a passing check
    r = lint(proj)
    assert r.returncode == 1 and 'Ledger: the card says data-check="fail" and the page-check report says pass' in detail(proj, "site:check"), r.stdout


def test_a_failing_check_shown_as_fail_passes_the_row(proj):
    settle(proj, 2, "Atlas", "fail")
    board_of(proj).write_text(board_text(checks={"Atlas": "fail"}), encoding="utf-8")
    r = lint(proj)
    assert r.returncode == 0, r.stdout
    assert rows(proj)["site:check"]["status"] == "pass"


def test_a_report_that_is_no_verdict_fails_and_says_what_it_could_not_verify(proj):
    settle(proj, 2, "Atlas", "not-verified")
    r = lint(proj)
    assert r.returncode == 1 and "site:check" in failed(proj), r.stdout
    why = detail(proj, "site:check")
    assert "Atlas: the page-check report is 'not-verified', not a verdict" in why and "page:load: not verified: no view was measured" in why and "run `brand-creator page-check rounds/r2/Atlas/index.html`" in why, why
    assert rows(proj)["site:tells"]["status"] == "skipped"


def test_a_check_line_needs_one_status_and_some_text(proj):
    mutate(board_of(proj), '<p class="check" data-check="pass">Filled in for the test fixture.</p>', '<p class="check" data-check="pass"></p>')
    r = lint(proj)
    assert r.returncode == 1 and "Ledger: the check line has no text" in detail(proj, "site:check"), r.stdout
    mutate(board_of(proj), '<p class="check" data-check="pass"></p>', '<p class="check" data-check="maybe">x</p>')
    r = lint(proj)
    assert r.returncode == 1 and "Ledger: data-check must be \"pass\" or \"fail\", got 'maybe'" in detail(proj, "site:check"), r.stdout
    mutate(board_of(proj), '<p class="check" data-check="maybe">x</p>', "")
    r = lint(proj)
    assert r.returncode == 1 and "Ledger: the card needs one check line" in detail(proj, "site:check") and "it has 0" in detail(proj, "site:check"), r.stdout


def test_a_report_of_another_page_is_no_report_of_this_one(proj):
    f = check_report_of(proj, "Atlas")
    mutate_json(f, lambda d: d["target"].__setitem__("page", page_of("Ledger")))
    r = lint(proj)
    assert r.returncode == 1 and "site:check" in failed(proj), r.stdout
    assert "Atlas: the page-check report is stale (it is the report of project rounds/r2/Ledger/index.html, not of the project page rounds/r2/Atlas/index.html)" in detail(proj, "site:check")
    mutate_json(f, lambda d: d.__setitem__("target", {"kind": "url", "page": None, "from": None, "url": "http://localhost:3000/start.html"}))
    r = lint(proj)
    assert r.returncode == 1 and "it is the report of url http://localhost:3000/start.html" in detail(proj, "site:check"), r.stdout


def test_a_report_that_does_not_list_the_page_could_never_go_stale_and_fails(proj):
    mutate_json(check_report_of(proj, "Atlas"), lambda d: d.__setitem__("inputs", [i for i in d["inputs"] if i["path"] != page_of("Atlas")]))
    r = lint(proj)
    assert r.returncode == 1 and "site:check" in failed(proj), r.stdout
    assert "it does not list rounds/r2/Atlas/index.html among the files it was made from, so a change to the page would not show" in detail(proj, "site:check")


def test_every_tell_page_check_found_is_named_on_the_card(proj):
    settle(proj, 2, "Ledger", tells=("eyebrow", "three-equal-tiles"))
    r = lint(proj)
    assert r.returncode == 1 and "site:tells" in failed(proj), r.stdout
    why = detail(proj, "site:tells")
    assert "Ledger: the card does not name eyebrow (" in why and "three-equal-tiles (" in why and "show every tell page-check found, with what you will do about it" in why and "Atlas" not in why, why
    assert "site:check" not in failed(proj), "a tell is a warning of the page, not a failure of the check"
    mutate(board_of(proj), "none found", "eyebrow: moved into the heading; three-equal-tiles: kept, argued in My call")
    assert lint(proj).returncode == 0, lint(proj).stdout
    assert detail(proj, "site:tells") == "2 tell(s) found by page-check, each named on its card"
    mutate(board_of(proj), "three-equal-tiles: kept", "three-equal-tiles-ish: kept")         # an id that is only the start of a longer word is not the id
    r = lint(proj)
    assert r.returncode == 1 and "Ledger: the card does not name three-equal-tiles (" in detail(proj, "site:tells") and "eyebrow (" not in detail(proj, "site:tells"), r.stdout


@pytest.mark.parametrize("tid", tell_ids())
def test_each_tell_of_page_tells_json_is_read_by_its_id(proj, tid):
    settle(proj, 2, "Ledger", tells=(tid,))
    r = lint(proj)
    assert r.returncode == 1 and "site:tells" in failed(proj) and f"does not name {tid} (" in detail(proj, "site:tells"), r.stdout
    mutate(board_of(proj), "none found", f"tell:{tid} will be fixed before the pages")
    assert lint(proj).returncode == 0 and detail(proj, "site:tells") == "1 tell(s) found by page-check, each named on its card"


def test_a_warning_of_the_report_that_is_no_tell_needs_no_mention(proj):
    mutate_json(check_report_of(proj, "Ledger"), lambda d: d["results"].append({"id": "page:pairs:light", "status": "warn", "label": "text on its ground", "detail": "x"}))
    r = lint(proj)
    assert r.returncode == 0, r.stdout
    assert detail(proj, "site:tells") == "page-check found no tell"


def test_a_variant_without_a_capture_record_fails(proj):
    (shots_of(proj, "Atlas") / "capture.json").unlink()
    r = lint(proj)
    assert r.returncode == 1 and failed(proj) == ["site:stills"], r.stdout
    assert "Atlas: no rounds/r2/Atlas/shots/capture.json, so the stills are not those of the page: run `brand-creator capture rounds/r2/Atlas/index.html`" in detail(proj, "site:stills")


def test_stills_must_be_the_captured_bytes(proj):
    still = shots_of(proj, "Ledger") / "390-dark.png"
    still.write_bytes(b"not the picture capture took")
    r = lint(proj)
    assert r.returncode == 1 and failed(proj) == ["site:stills"], r.stdout
    why = detail(proj, "site:stills")
    assert ("Ledger: rounds/r2/Ledger/shots/390-dark.png is not the 390-dark still rounds/r2/Ledger/shots/capture.json lists (its sha256 differs): "
            "run `brand-creator capture rounds/r2/Ledger/index.html`") in why and "Ledger: the 390-dark picture the card shows is not the one" in why and "Atlas" not in why, why
    capture_record(proj, page_of("Ledger"))                                                    # taken again
    assert lint(proj).returncode == 0
    capture = shots_of(proj, "Ledger") / "capture.json"
    mutate_json(capture, lambda d: d["views"][0].__setitem__("sha256", "0" * 64))              # the record lists other bytes than the file and the card have
    r = lint(proj)
    assert r.returncode == 1 and "Ledger: the 1440-light picture the card shows is not the one" in detail(proj, "site:stills"), r.stdout
    mutate_json(capture, lambda d: d["views"][0].__setitem__("sha256", "short"))
    r = lint(proj)
    assert r.returncode == 1 and "Ledger: rounds/r2/Ledger/shots/capture.json lists no 1440-light still with a sha256" in detail(proj, "site:stills"), r.stdout
    mutate_json(capture, lambda d: d["views"].pop(0))
    assert lint(proj).returncode == 1 and "lists no 1440-light still" in detail(proj, "site:stills")


def test_stills_go_stale_when_the_page_changes(proj):
    mutate(proj / page_of("Ledger"), "<h1>Ledger</h1>", "<h1>Ledger again</h1>")
    page_check_report(proj, page_of("Ledger"))                                                 # the check is run again, the capture is not
    r = lint(proj)
    assert r.returncode == 1 and failed(proj) == ["site:stills"], r.stdout
    assert "Ledger: rounds/r2/Ledger/shots/capture.json is stale (rounds/r2/Ledger/index.html changed): run `brand-creator capture rounds/r2/Ledger/index.html`" in detail(proj, "site:stills")


def test_a_capture_of_another_page_fails(proj):
    mutate_json(shots_of(proj, "Atlas") / "capture.json", lambda d: d["source"].__setitem__("page", page_of("Ledger")))
    r = lint(proj)
    assert r.returncode == 1 and failed(proj) == ["site:stills"], r.stdout
    assert "Atlas: rounds/r2/Atlas/shots/capture.json is the capture of rounds/r2/Ledger/index.html, not of rounds/r2/Atlas/index.html (a folder copied from an earlier round)" in detail(proj, "site:stills")
    mutate_json(shots_of(proj, "Atlas") / "capture.json", lambda d: d.__setitem__("source", {"url": "https://example.com/", "final_url": "https://example.com/"}))   # the capture of a real site
    assert lint(proj).returncode == 1 and "is the capture of https://example.com/, not of" in detail(proj, "site:stills")


def test_the_card_shows_exactly_one_still_per_view(proj):
    mutate(board_of(proj), 'data-field="still" data-view="1440-dark"', 'data-field="still" data-view="1440-light"')
    r = lint(proj)
    assert r.returncode == 1 and failed(proj) == ["site:stills"], r.stdout
    why = detail(proj, "site:stills")
    assert 'Ledger: the card needs one <img data-field="still" data-view="1440-light">, it has 2' in why and 'Ledger: the card needs one <img data-field="still" data-view="1440-dark">, it has 0' in why, why
    mutate(board_of(proj), 'data-field="still" data-view="390-dark"', 'data-field="still" data-view="tablet"')
    assert lint(proj).returncode == 1 and "a still of the card has data-view 'tablet', the views are 1440-light, 1440-dark, 390-light, 390-dark" in detail(proj, "site:stills")


@pytest.mark.parametrize("src, why", [("https://example.com/1440-light.png", "a site board shows the project's own file by a relative path, or a data: URI (nothing from the network)"),
                                      ("../../../../outside.png", "which is outside the project"),
                                      ("Ledger/shots/gone.png", "names rounds/r2/Ledger/shots/gone.png, which does not exist"),
                                      ("data:image/png;base64,@@@", "is a data: URI that cannot be decoded")])
def test_a_still_that_is_no_file_of_the_project_is_no_capture(proj, src, why):
    mutate(board_of(proj), 'src="Ledger/shots/1440-light.png"', f'src="{src}"')
    r = lint(proj)
    assert r.returncode == 1 and failed(proj) == ["site:stills"], r.stdout
    assert re.search(r"Ledger: the 1440-light picture (?:is|names) ", detail(proj, "site:stills")) and why in detail(proj, "site:stills")


def test_the_review_copy_may_inline_the_same_stills(proj):
    review = proj / "review" / "index.html"
    review.parent.mkdir()
    review.write_text(inline_stills(board_of(proj).read_text(encoding="utf-8"), proj), encoding="utf-8")
    r = lint(proj, "review/index.html", "--round", "2")
    assert r.returncode == 0, r.stdout
    assert rows(proj)["site:stills"]["status"] == "pass" and rows(proj)["site:check"]["status"] == "pass"


def test_a_review_copy_that_inlines_other_pictures_fails(proj):
    review = proj / "review" / "index.html"
    review.parent.mkdir()
    review.write_text(inline_stills(board_of(proj).read_text(encoding="utf-8"), proj, other={"Atlas/shots/390-light.png": b"another picture"}), encoding="utf-8")
    r = lint(proj, "review/index.html", "--round", "2")
    assert r.returncode == 1 and failed(proj) == ["site:stills"], r.stdout
    assert "Atlas: the 390-light picture the card shows is not the one rounds/r2/Atlas/shots/capture.json lists" in detail(proj, "site:stills")


def test_without_a_variant_card_the_proof_rows_are_not_verified(tmp_path):
    p = build(tmp_path)
    add_round(p, 3, (), first=False)
    r = lint(p, "rounds/r3/board.html")
    assert r.returncode == 1, r.stdout                                                         # site:variants fails: a later hero board shows 1 or more
    got = rows(p)
    for rid in ("site:check", "site:tells", "site:stills"):
        assert got[rid]["status"] == "skipped" and "there is no variant card to look at" in got[rid]["detail"], rid


def test_the_lint_report_lists_the_page_check_reports_the_captures_and_the_stills_as_inputs_and_goes_stale_with_them(proj):
    from _common import stale_inputs
    assert lint(proj).returncode == 0
    doc = report(proj, "board-lint")
    paths = [i["path"] for i in doc["inputs"]]
    for name in NAMES:
        for want in (check_report_of(proj, name).relative_to(proj).as_posix(), f"rounds/r2/{name}/shots/capture.json", *(f"rounds/r2/{name}/shots/{v}.png" for v in VIEWS), "assets/tokens/tokens.css"):
            assert want in paths, (want, paths)
    assert stale_inputs(proj, doc) == []
    still = shots_of(proj, "Atlas") / "390-light.png"
    before = still.read_bytes()
    still.write_bytes(before + b"x")
    assert stale_inputs(proj, doc) == ["rounds/r2/Atlas/shots/390-light.png changed"]
    still.write_bytes(before)
    page_check_report(proj, page_of("Ledger"), "fail")
    assert stale_inputs(proj, doc) == [check_report_of(proj, "Ledger").relative_to(proj).as_posix() + " changed"]
