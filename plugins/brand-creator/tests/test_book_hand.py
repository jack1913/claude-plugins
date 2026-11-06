"""The tools of a hand-authored book: patch --loose-space, `book chapter` (replace, add, remove), `book nbsp --fix`, and the chapter count."""
import re

import pytest
from helpers import bc, make_project

import _common

NB = " "
BOOK = ('<!doctype html>\n<html lang="pl"><body>\n<nav><p>Spis: <span data-count="chapters">2</span> rozdziały</p>\n'
        '<ol><li><a href="#one">Dom i ogród</a></li><li><a href="#two">Dwa</a></li></ol></nav>\n'
        '<section class="ch" id="one" data-chapter="one">\n<p>Mama i tata w domu</p>\n</section>\n'
        '<section class="ch" id="two" data-chapter="two">\n<p>Dom w lesie</p>\n</section>\n</body></html>\n')
FRAG = '<section class="ch" id="two" data-chapter="two">\n<h2>Nowy</h2>\n</section>\n'


@pytest.fixture
def proj(tmp_path):
    p = make_project(tmp_path, tier="standard")
    for kv in ("content_languages=pl", "mark_source=authored-vector"):
        assert bc("state", "--set", kv, project=p).returncode == 0
    (p / "book.html").write_text(BOOK)
    return p


def frag(tmp_path, text=FRAG, name="frag.html"):
    f = tmp_path / name
    f.write_text(text)
    return str(f)


def book(p):
    return (p / "book.html").read_text()


def log(p):
    return [ln for ln in (p / "BRAND-STATE.md").read_text().split("\n") if re.match(r"^- \d{4}-\d{2}-\d{2} edition ", ln)]


# ---------------------------------------------------------------- (b) patch --loose-space

def test_patch_loose_space_matches_a_no_break_space_and_plain_patch_does_not(proj):
    (proj / "book.html").write_text(BOOK.replace("Dom i ogród", f"Dom i{NB}ogród"))
    r = bc("patch", "book.html", "--old", "Dom i ogród", "--new", "Dom", "--count", "1", project=proj)
    assert r.returncode == 1 and "holds the text 0 time(s)" in r.stderr and "--loose-space" in r.stderr
    r = bc("patch", "book.html", "--old", "Dom i ogród", "--new", "Dom", "--count", "1", "--loose-space", project=proj)
    assert r.returncode == 0, r.stderr
    assert ">Dom</a>" in book(proj) and len(log(proj)) == 1


def test_loose_space_takes_the_narrow_no_break_space_and_a_longer_run_and_keeps_the_rest_byte_for_byte(proj):
    src = BOOK.replace("Mama i tata", "Mama i   tata")
    (proj / "book.html").write_text(src)
    r = bc("patch", "book.html", "--old", "Mama i tata w", "--new", "X", "--count", "1", "--loose-space", project=proj)
    assert r.returncode == 0, r.stderr
    assert book(proj) == src.replace("Mama i   tata w", "X")


def test_loose_space_still_refuses_a_match_that_is_not_the_count(proj):
    (proj / "book.html").write_text(BOOK.replace("Dom w lesie", f"Dom{NB}w lesie").replace("Mama i tata w domu", "Dom w domu"))
    before = book(proj)
    r = bc("patch", "book.html", "--old", "Dom w", "--new", "X", "--count", "1", "--loose-space", project=proj)
    assert r.returncode == 1 and "holds the text 2 time(s)" in r.stderr
    assert book(proj) == before and log(proj) == []
    # the loose match does not invent a space where the book has none
    r = bc("patch", "book.html", "--old", "Dom  w", "--new", "X", "--count", "1", "--loose-space", project=proj)
    assert r.returncode == 1 and "holds the text 2 time(s)" in r.stderr
    r = bc("patch", "book.html", "--old", "Domw", "--new", "X", "--count", "1", "--loose-space", project=proj)
    assert r.returncode == 1 and "0 time(s)" in r.stderr


# ---------------------------------------------------------------- (a) book chapter

def test_chapter_replace_swaps_only_that_chapter_and_logs_the_edition(proj, tmp_path):
    r = bc("book", "chapter", "--replace", "two", "--from", frag(tmp_path), "--note", "new two", project=proj)
    assert r.returncode == 0, r.stderr
    assert book(proj) == BOOK.replace('<section class="ch" id="two" data-chapter="two">\n<p>Dom w lesie</p>\n</section>', FRAG.rstrip("\n"))
    assert log(proj) == ["- 2026-10-17 edition 1: replaced chapter two in book.html (chapters 2 -> 2): new two"]
    assert _common.State(proj / "BRAND-STATE.md").get("edition") == "1"


@pytest.mark.parametrize("cid,text,why", [
    ("missing", FRAG.replace("two", "missing"), "no <section data-chapter=\"missing\">"),
    ("two", FRAG.replace('data-chapter="two"', 'data-chapter="three"'), "root must be"),
    ("two", '<section class="ch" id="two">\n</section>', "root must be"),
    ("two", '<div data-chapter="two"></div>', "root must be"),
    ("two", FRAG + "<p>after</p>", "one chapter element and nothing else"),
    ("two", '<section class="ch" id="two" data-chapter="two"><p>x</p>', "not closed"),
])
def test_chapter_replace_refuses_with_exit_2_and_writes_nothing(proj, tmp_path, cid, text, why):
    before, st = book(proj), (proj / "BRAND-STATE.md").read_bytes()
    r = bc("book", "chapter", "--replace", cid, "--from", frag(tmp_path, text), project=proj)
    assert r.returncode == 2 and why in r.stderr, r.stderr
    assert book(proj) == before and (proj / "BRAND-STATE.md").read_bytes() == st


def test_chapter_refuses_a_generated_book(tmp_path):
    p = make_project(tmp_path, tier="standard")
    assert bc("state", "--set", "content_languages=en", project=p).returncode == 0
    (p / "book.html").write_text(BOOK)
    r = bc("book", "chapter", "--replace", "two", "--from", frag(tmp_path), project=p)
    assert r.returncode == 2 and "generated" in r.stderr and book(p) == BOOK


def test_chapter_edit_of_an_approved_edition_needs_a_new_edition(proj, tmp_path):
    assert bc("state", "--record", "G5", "approved", project=proj).returncode == 0
    r = bc("book", "chapter", "--replace", "two", "--from", frag(tmp_path), project=proj)
    assert r.returncode == 1 and "was approved" in r.stderr and book(proj) == BOOK
    r = bc("book", "chapter", "--replace", "two", "--from", frag(tmp_path), "--new-edition", project=proj)
    assert r.returncode == 0, r.stderr
    assert len(log(proj)) == 2 and "opened" in log(proj)[0]


# ---------------------------------------------------------------- (d) the chapter count

def test_adding_a_chapter_recomputes_the_count_and_removing_one_does_too(proj, tmp_path):
    three = FRAG.replace("two", "three")
    r = bc("book", "chapter", "--add", "three", "--from", frag(tmp_path, three), "--after", "one", project=proj)
    assert r.returncode == 0, r.stderr
    b = book(proj)
    assert '<span data-count="chapters">3</span>' in b
    assert [m for m in re.findall(r'data-chapter="(\w+)"', b)] == ["one", "three", "two"]
    r = bc("book", "chapter", "--add", "three", "--from", frag(tmp_path, three), project=proj)
    assert r.returncode == 2 and "already has" in r.stderr
    r = bc("book", "chapter", "--remove", "three", project=proj)
    assert r.returncode == 0, r.stderr
    assert book(proj) == BOOK and "chapters 3 -> 2" in log(proj)[-1]


def test_removing_a_chapter_the_contents_still_links_is_refused(proj):
    r = bc("book", "chapter", "--remove", "two", project=proj)
    assert r.returncode == 2 and "still links to #two" in r.stderr and book(proj) == BOOK
    assert bc("patch", "book.html", "--old", '<li><a href="#two">Dwa</a></li>', "--new", "", "--count", "1", project=proj).returncode == 0
    r = bc("book", "chapter", "--remove", "two", project=proj)
    assert r.returncode == 0, r.stderr
    assert '<span data-count="chapters">1</span>' in book(proj) and 'data-chapter="two"' not in book(proj)


def test_book_lint_fails_a_chapter_count_that_does_not_match(proj):
    import bookdata
    import booklint
    cfg, _ = bookdata.load_config(proj)
    doc = {"primitives": {}, "pairs": [], "modes": {"light": {}}}

    def count_row(text):
        return next(r for r in booklint._count_rules(proj, text, cfg, doc, []) if r["id"] == "counts:data")
    assert count_row(BOOK)["status"] == "pass"
    bad = count_row(BOOK.replace('"chapters">2<', '"chapters">17<'))
    assert bad["status"] == "fail" and "chapters: the book says 17, the data say 2" in bad["detail"]


# ---------------------------------------------------------------- (c) book nbsp

def test_nbsp_fix_is_a_dry_run_until_yes_and_then_writes_the_no_break_spaces_the_lint_warns_on(proj):
    import bookdata
    import booklint
    view = bookdata.state_view(proj)

    def nbsp_row(text):
        return next(r for r in booklint._language_rules(text, view) if r["id"] == "lang:pl:nbsp-single-letter")
    assert nbsp_row(BOOK)["status"] == "warn"
    r = bc("book", "nbsp", "--fix", project=proj)
    assert r.returncode == 0, r.stderr
    assert "dry run" in r.stdout and "line 4" in r.stdout and book(proj) == BOOK and log(proj) == []
    r = bc("book", "nbsp", "--fix", "--yes", "--note", "typography", project=proj)
    assert r.returncode == 0, r.stderr
    b = book(proj)
    assert f"Mama i{NB}tata w{NB}domu" in b and f"Dom i{NB}ogród" in b and f"Dom w{NB}lesie" in b
    assert b.replace(NB, " ") == BOOK, "only spaces changed, nothing else"
    assert log(proj) == ["- 2026-10-17 edition 1: nbsp in book.html (4 spaces made no-break): typography"]
    assert nbsp_row(b)["status"] == "pass"
    r = bc("book", "nbsp", "--fix", "--yes", project=proj)
    assert r.returncode == 0 and "nothing to change" in r.stdout and len(log(proj)) == 1


def test_nbsp_fix_never_touches_a_tag_between_a_one_letter_word_and_the_next(proj):
    src = '<p>Kot i <strong>pies</strong>, dom <em>a</em> las, idź z <a href="#x">nami</a></p>'
    (proj / "book.html").write_text(src)
    r = bc("book", "nbsp", "--fix", "--yes", project=proj)
    assert r.returncode == 0, r.stderr
    b = book(proj)
    assert b != src and b.replace(NB, " ") == src, "every tag kept, only spaces changed"
    assert f"i{NB}<strong>" in b and f"</em>{NB}las" in b and f"z{NB}<a" in b


def test_chapter_replace_refuses_an_id_the_book_has_twice(proj, tmp_path):
    dup = BOOK.replace("</body>", '<section data-chapter="two"><p>again</p></section>\n</body>')
    (proj / "book.html").write_text(dup)
    r = bc("book", "chapter", "--replace", "two", "--from", frag(tmp_path), project=proj)
    assert r.returncode == 2 and "2 chapters" in r.stderr and book(proj) == dup and log(proj) == []


def test_nbsp_fix_needs_fix_and_refuses_a_generated_book_and_an_approved_edition(proj, tmp_path):
    assert bc("book", "nbsp", project=proj).returncode == 2
    assert bc("state", "--record", "G5", "approved", project=proj).returncode == 0
    r = bc("book", "nbsp", "--fix", "--yes", project=proj)
    assert r.returncode == 1 and "was approved" in r.stderr and book(proj) == BOOK
    g = make_project(tmp_path / "g", tier="standard")
    assert bc("state", "--set", "content_languages=pl", project=g).returncode == 0
    (g / "book.html").write_text(BOOK)
    r = bc("book", "nbsp", "--fix", "--yes", project=g)
    assert r.returncode == 2 and "generated" in r.stderr and (g / "book.html").read_text() == BOOK


def test_the_fixer_uses_the_lints_own_rule():
    import inspect

    import booklint
    assert "single_letter_nbsp_pattern(c[\"words\"])" in inspect.getsource(booklint._language_rules)
    assert "single_letter_nbsp_pattern(c[\"words\"])" in inspect.getsource(booklint.nbsp_fixes)


@pytest.mark.parametrize("src", [
    '<p>Polecenie z <code>brand creator kit</code> teraz</p>',
    '<p>Kolor w <script>var a = 1;</script>las</p>',
    '<p>Dom i <svg><title>a b c</title></svg> tata</p>',
    '<p>Dom i <!-- a b c --> tata, w lesie</p>',
    '<p title="x > y">Dom i <b>y</b> z <i>t</i></p>',
    '<p>Kot a   tata i\t<em>x</em></p>',
])
def test_nbsp_fix_writes_only_the_run_after_the_word(proj, src):
    (proj / "book.html").write_text(src)
    r = bc("book", "nbsp", "--fix", "--yes", project=proj)
    assert r.returncode == 0, r.stderr
    b = book(proj)
    assert b != src
    # undoing the no-break spaces gives the source, except a run of spaces directly after the word that collapsed into one
    assert re.sub(r"[ \t]+", " ", b.replace(NB, " ")) == re.sub(r"[ \t]+", " ", src)
    for blk in ("brand creator kit", "var a = 1;", "a b c", 'title="x > y"'):
        assert blk not in src or blk in b, "the content of a code, script, svg, comment or attribute is untouched"


def test_nbsp_dry_run_counts_what_yes_writes(proj):
    (proj / "book.html").write_text('<p>Dom i <code>a b</code> tata, w lesie</p>')
    d = bc("book", "nbsp", "--fix", project=proj)
    assert d.returncode == 0 and "dry run: 2 space(s)" in d.stdout, d.stdout
    assert "y\">" not in d.stdout
    y = bc("book", "nbsp", "--fix", "--yes", project=proj)
    assert "2 space(s) are now" in y.stdout and "(2 spaces made no-break)" in log(proj)[0]


@pytest.mark.parametrize("which", ["chapter", "nbsp"])
def test_book_tools_never_write_a_frozen_file(proj, tmp_path, which):
    (proj / "history").mkdir()
    (proj / "history" / "book.html").write_text(BOOK)
    args = (["chapter", "--replace", "two", "--from", frag(tmp_path)] if which == "chapter" else ["nbsp", "--fix", "--yes"])
    r = bc("book", *args, "--file", "history/book.html", project=proj)
    assert r.returncode == 1 and "frozen" in r.stderr
    assert (proj / "history" / "book.html").read_text() == BOOK and log(proj) == []


@pytest.mark.parametrize("src", [
    '<h2>Część I</h2> <p>Wstęp</p>',
    '<p>dom i</p> <p>las</p>',
    '<ul><li>Wariant A</li> <li>Wariant B</li></ul>',
    '<p>Dom i<br> las</p>',
    '<p>Dom i <br>las</p>',
    '<div data-note="->" class="a b">Tekst</div>',
    '<p title="x > w domu">Tekst</p>',
    '<form><textarea>a b</textarea></form>',
    '<p>Kot i <em> pies</em></p>',
    '<p>Kot i <span></span> pies</p>',
    '<p>Kot i <!-- c --> pies</p>',
])
def test_nbsp_fix_never_writes_between_blocks_in_a_tag_or_in_a_textarea(proj, src):
    (proj / "book.html").write_text(src)
    r = bc("book", "nbsp", "--fix", "--yes", project=proj)
    assert r.returncode == 0, r.stderr
    assert book(proj) == src, "byte for byte: a no-break space between two blocks shows as a gap, and one in an attribute breaks it"


def test_nbsp_fix_collapses_the_run_after_the_word_into_one_no_break_space(proj):
    (proj / "book.html").write_text('<p>Kot a   tata, <em>i</em> las</p>')
    assert bc("book", "nbsp", "--fix", "--yes", project=proj).returncode == 0
    assert book(proj) == f'<p>Kot a{NB}tata, <em>i</em>{NB}las</p>'


def test_nbsp_dry_run_prints_the_plans_count_not_the_lints(proj):
    (proj / "book.html").write_text('<p>Dom i<br>las, w lesie</p>')   # the lint warns on both; the fixer leaves the <br> alone
    d = bc("book", "nbsp", "--fix", project=proj)
    assert d.returncode == 0 and "dry run: 1 space(s)" in d.stdout, d.stdout


def test_a_fragment_with_a_byte_order_mark_is_read(proj, tmp_path):
    f = tmp_path / "bom.html"
    f.write_text("﻿" + '<section data-chapter="two"><h2>Nowy</h2></section>\n', encoding="utf-8")
    r = bc("book", "chapter", "--replace", "two", "--from", str(f), project=proj)
    assert r.returncode == 0, r.stderr
    assert "﻿" not in book(proj) and "Nowy" in book(proj)


# ---------------------------------------------------------------- review round 1

def test_nbsp_fix_writes_one_no_break_space_where_two_languages_nest(proj):
    assert bc("state", "--set", "content_languages=pl,cs", project=proj).returncode == 0
    (proj / "book.html").write_text('<section data-chapter="one" lang="pl"><p>Mama i tata <span lang="cs">a z domu</span></p></section>\n')
    d = bc("book", "nbsp", "--fix", project=proj)
    assert d.returncode == 0 and "dry run: 3 space(s)" in d.stdout, d.stdout
    y = bc("book", "nbsp", "--fix", "--yes", project=proj)
    assert y.returncode == 0, y.stderr
    assert f"a{NB}z{NB}domu" in book(proj) and NB * 2 not in book(proj) and "(3 spaces made no-break)" in log(proj)[0]


def test_loose_space_leaves_the_blank_line_after_an_old_file_that_ends_in_a_newline(proj, tmp_path):
    (proj / "notes.md").write_text("Intro\n\nFirst para.\n\nSecond para.\n")
    old, new = tmp_path / "old.txt", tmp_path / "new.txt"
    old.write_text("First para.\n")
    new.write_text("New para.\n")
    r = bc("patch", "notes.md", "--old-file", str(old), "--new-file", str(new), "--count", "1", "--loose-space", project=proj)
    assert r.returncode == 0, r.stderr
    assert (proj / "notes.md").read_text() == "Intro\n\nNew para.\n\nSecond para.\n"


def test_chapter_remove_refuses_a_link_to_the_sections_own_id_when_it_differs_from_data_chapter(proj):
    (proj / "book.html").write_text(BOOK.replace('id="one" data-chapter="one"', 'id="ch-one" data-chapter="one"').replace('href="#one"', 'href="#ch-one"'))
    before = book(proj)
    r = bc("book", "chapter", "--remove", "one", project=proj)
    assert r.returncode != 0 and "still links to #one or an id inside it (line(s) 4)" in r.stderr, r.stderr
    assert book(proj) == before and log(proj) == []


def test_chapter_remove_refuses_a_link_on_the_sections_own_line_in_a_one_line_book(proj):
    one_line = BOOK.replace('id="one" data-chapter="one"', 'id="ch-one" data-chapter="one"').replace('href="#one"', 'href="#ch-one"').replace("\n", "")
    (proj / "book.html").write_text(one_line)
    r = bc("book", "chapter", "--remove", "one", project=proj)
    assert r.returncode != 0 and "still links to #one or an id inside it (line(s) 1)" in r.stderr, r.stderr
    assert book(proj) == one_line and log(proj) == []
