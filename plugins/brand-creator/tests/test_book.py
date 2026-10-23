"""The brand book: the Markdown subset, chapter selection, the generated book (structure, computed values, byte identity), the lint
(each rule broken in a scratch copy) and the PDF export. Expected values are worked out by hand or read from the project's own data."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from helpers import ROOT, bc, fill_markers, make_project, install_fixture, mutate, report

import bookdata
import bookmd
import booklint
import htmlscan

setup = pytest.mark.requires_setup
resvg = pytest.mark.requires_resvg


# ---------------------------------------------------------------- the Markdown subset (no tools needed)

class Ctx:
    BLOCK = {"files"}
    INLINE = {"count", "fact"}

    def block(self, n, a, lang):
        return f"<BLOCK {n}>"

    def inline(self, n, a, lang):
        return f"<{n}:{a}>"

    def image(self, p, alt, lang, line):
        return f"<IMG {p} {alt}>"

    def variant(self, kind, group, name, line):
        pass


def md(text: str) -> str:
    return bookmd.convert(text, Ctx(), "en")[1]


def test_markdown_subset_maps_each_construct_to_its_html():
    src = "# Title\n\n## Why\nOne **bold _it_** and `code` and [a](#b).\n\n- one\n- [ ] two\n\n1. a\n2. b\n\n> quoted\n\n{{files}}\n"
    title, html = bookmd.convert(src, Ctx(), "en")
    assert title == "Title"
    assert html.splitlines() == [
        "<h3>Why</h3>",
        '<p>One <strong>bold <em>it</em></strong> and <code>code</code> and <a href="#b">a</a>.</p>',
        '<ul><li>one</li><li class="task" data-task="open">two</li></ul>',
        "<ol><li>a</li><li>b</li></ol>",
        "<blockquote><p>quoted</p></blockquote>",
        "<BLOCK files>"]


def test_markdown_table_and_counts():
    html = md("| a | b |\n|---|---|\n| 1 | {{count:files}} |\n")
    assert html == '<div class="tw"><table><thead><tr><th>a</th><th>b</th></tr></thead><tbody><tr><td>1</td><td><count:files></td></tr></tbody></table></div>'


def test_raw_html_is_escaped_so_a_chapter_cannot_carry_a_script():
    assert md("<script>alert(1)</script>") == "<p>&lt;script&gt;alert(1)&lt;/script&gt;</p>"


@pytest.mark.parametrize("src,needle", [
    ("[[fill: write this]]", "unfilled marker"),
    ("#### deep", "deeper than ###"),
    ("- a\n  - nested", "nested lists"),
    ("| a | b |\n|---|---|\n| 1 |", "table row has 1 cells"),
    ("[x](javascript:void)", "not allowed"),
    ("{{nonsense}}", "unknown block"),
    ("see {{files}} here", "it is a block"),
    ("::: variant g a\nopen forever", "never closed"),
    ("::: variant onlyone", "GROUP NAME"),
    (":::", "closing :::"),
])
def test_markdown_errors_name_the_line_and_the_problem(src, needle):
    with pytest.raises(bookmd.MdError) as e:
        md(src)
    assert needle in str(e.value) and str(e.value).startswith("line ")


# ---------------------------------------------------------------- which chapters appear

def view(tier, arch="standalone", extra=()):
    return {"tier": tier, "architecture": arch, "book_chapters": list(extra)}


def test_quick_is_the_short_guide(tmp_path):
    assert bookdata.chapters_for(tmp_path, view("quick")) == ["idea", "mark", "colour", "files", "changing"]


def test_standard_adds_the_system_chapters_and_the_rules_of_each(tmp_path):
    base = ["idea", "mark", "colour", "type", "use", "files", "proof", "donts", "changing", "history"]
    assert bookdata.chapters_for(tmp_path, view("standard")) == base
    (tmp_path / "motion").mkdir()
    (tmp_path / "motion/proof.json").write_text("{}")
    (tmp_path / "assets/logo").mkdir(parents=True)
    (tmp_path / "assets/logo/wordmark.svg").write_text("<svg/>")
    got = bookdata.chapters_for(tmp_path, view("standard", extra=["tone", "photography"]))
    assert got == ["idea", "mark", "motion", "wordmark", "colour", "type", "tone", "photography", "use", "files", "proof", "donts", "changing", "history"]


def test_family_modes_add_endorsement_and_family_and_full_adds_adoption_and_launch(tmp_path):
    got = bookdata.chapters_for(tmp_path, view("full", "product-in-family"))
    assert "endorsement" in got and "family" in got and got[-3:] == ["launch", "changing", "history"] and "adoption" in got
    assert "endorsement" not in bookdata.chapters_for(tmp_path, view("full", "standalone"))
    assert "adoption" not in bookdata.chapters_for(tmp_path, view("standard", "family-member"))


# ---------------------------------------------------------------- a built book

@pytest.fixture(scope="session")
def built(golden, tmp_path_factory):
    """A standard-tier Acme project with a manifest (emit web), a downscale proof, every chapter filled, and the book built."""
    if shutil.which("resvg") is None:
        pytest.skip("NOT VERIFIED: resvg is not installed")
    p = tmp_path_factory.mktemp("bookproj") / "acme"
    shutil.copytree(golden, p)
    for k, v in (("tier", "standard"), ("content_languages", "en"), ("book_chapters", "tone")):
        assert bc("state", "--set", f"{k}={v}", project=p).returncode == 0
    mutate(p / "BRAND-STATE.md", "- (rule) (...)", "- (rule) the accent is a fill, never text (proposal)")
    for cmd in (("emit", "web"), ("contrast",)):
        r = bc(*cmd, project=p)
        assert r.returncode == 0, r.stdout + r.stderr
    import sys
    ds = [] if sys.platform == "darwin" else ["--renderer=pillow"]
    r = bc("downscale", "--source", "assets/logo/grid-mark-master.png", *ds, project=p)
    assert r.returncode == 0, r.stdout + r.stderr
    r = bc("book", "--init", project=p)
    assert r.returncode == 0, r.stdout + r.stderr
    assert fill_markers(p) > 10
    r = bc("book", project=p)
    assert r.returncode == 0, r.stdout + r.stderr
    return p


@pytest.fixture
def proj(built, tmp_path):
    dst = tmp_path / "acme"
    shutil.copytree(built, dst)
    return dst


def add_fact(proj: Path, label: str, value: str) -> None:
    """Append a row to the FACTS.md table (the template has prose after the table, so the row goes after the last table line)."""
    f = proj / "FACTS.md"
    lines = f.read_text().split("\n")
    last = max(i for i, ln in enumerate(lines) if ln.startswith("|"))
    lines.insert(last + 1, f"| {label} | {value} | owner | 2026-10-17 |")
    f.write_text("\n".join(lines))


def sections(text):
    return [t.attrs["data-chapter"] for t in htmlscan.tags(text) if not t.closing and t.name == "section" and "data-chapter" in t.attrs]


@setup
@resvg
def test_the_book_has_the_chapters_the_tier_and_state_decide_in_registry_order(proj):
    html = (proj / "book.html").read_text()
    # the Acme project has motion/ (the dot press) and a wordmark, and BRAND-STATE opts in to tone
    assert sections(html) == ["idea", "mark", "motion", "wordmark", "colour", "type", "tone", "use", "files", "proof", "donts", "changing", "history"]


@setup
@resvg
def test_the_book_is_self_contained_with_no_script_no_network_and_both_schemes(proj):
    html = (proj / "book.html").read_text()
    assert "<script" not in html and not re.search(r"(?:src|href)=[\"']https?:", html) and "@import" not in html
    assert "prefers-color-scheme:dark" in html and 'name="viewport"' in html and '<html lang="en">' in html
    srcs = [t.attrs["src"] for t in htmlscan.tags(html) if t.name == "img"]
    assert srcs and all(s.startswith("data:") for s in srcs)


@setup
@resvg
def test_counts_and_the_files_table_come_from_the_manifest(proj):
    html = (proj / "book.html").read_text()
    manifest = json.loads((proj / "assets/manifest.json").read_text())["artefacts"]
    counts = {t.attrs["data-count"]: htmlscan.visible_text(html[t.start:htmlscan.element_end(html, t)]) for t in htmlscan.tags(html)
              if not t.closing and "data-count" in t.attrs}
    assert counts["files"] == str(len(manifest)) and int(counts["files"]) > 5
    assert counts["slots"] == str(len({a["slot"] for a in manifest if a.get("slot")}))
    assert counts["colours"] == str(len(json.loads((proj / "assets/tokens/tokens.json").read_text())["primitives"]))
    rows = {t.attrs["data-path"]: t.attrs["data-sha"] for t in htmlscan.tags(html) if not t.closing and "data-path" in t.attrs}
    assert {a["path"] for a in manifest} <= set(rows)
    assert all(rows[a["path"]] == a["sha256"][:8] for a in manifest)
    assert "assets/logo/mark.svg" in rows


@setup
@resvg
def test_the_contrast_table_is_computed_not_copied(proj):
    html = (proj / "book.html").read_text()
    # Acme's text on its background: #0d1b2d on #f9f7ee, worked out independently with the WCAG formula as 16.15:1
    assert "16.15:1" in html and "15.92:1" in html


@setup
@resvg
def test_the_mark_by_size_proof_has_exact_pixel_images(proj):
    html = (proj / "book.html").read_text()
    sizes = {}
    for t in htmlscan.tags(html):
        if t.name == "img" and t.attrs.get("class") == "px" and t.attrs.get("alt", "").endswith("light ground"):
            sizes[int(t.attrs["width"])] = t.attrs["src"]
    assert sorted(sizes) == [16, 20, 32, 48, 64, 128, 180]
    import base64
    import struct
    for s, src in sizes.items():
        png = base64.b64decode(src.split(",", 1)[1])
        assert png[:8] == b"\x89PNG\r\n\x1a\n" and struct.unpack(">II", png[16:24]) == (s, s)
    assert "assets/logo/grid-mark.svg (small)" in html and "assets/logo/mark.svg (large)" in html   # the band rule picked the drawings


@setup
@resvg
def test_rebuild_is_byte_identical_and_verify_agrees(proj):
    before = (proj / "book.html").read_bytes()
    assert bc("book", project=proj).returncode == 0
    assert (proj / "book.html").read_bytes() == before
    assert bc("book", "--verify", project=proj).returncode == 0
    (proj / "book.html").write_bytes(before + b" ")
    r = bc("book", "--verify", project=proj)
    assert r.returncode == 1 and "edited by hand" in r.stdout + r.stderr


@setup
@resvg
def test_the_cover_follows_the_gates_and_the_edition(proj):
    html = (proj / "book.html").read_text()
    cover = next(t for t in htmlscan.tags(html) if "data-cover" in t.attrs)
    assert cover.attrs["data-edition"] == "1" and cover.attrs["data-stamp"] == "pending" and "APPROVED" not in html
    assert bc("state", "--record", "G5", "edition approved (test)", project=proj).returncode == 0
    assert bc("book", project=proj).returncode == 0
    html = (proj / "book.html").read_text()
    cover = next(t for t in htmlscan.tags(html) if "data-cover" in t.attrs)
    assert cover.attrs["data-stamp"] == "approved" and "APPROVED 2026-10-17" in html
    assert bc("state", "--set", "edition=2", project=proj).returncode == 0     # a new edition is not approved by the old G5
    assert bc("book", project=proj).returncode == 0
    html = (proj / "book.html").read_text()
    assert next(t for t in htmlscan.tags(html) if "data-cover" in t.attrs).attrs["data-stamp"] == "pending" and "APPROVED" not in html


def cover_html(proj: Path) -> str:
    html = (proj / "book.html").read_text()
    start = html.index('id="cover"')
    return html[start:html.index("</section>", start)]


def lint_row(proj: Path, rid: str) -> dict:
    return next(x for x in report(proj, "book-lint")["results"] if x["id"] == rid)


@setup
@resvg
def test_the_approval_stamp_follows_the_content_language_and_the_lint_wants_that_word(proj):
    """The stamp word is APPROVED, or the book/book.json labels entry for it in the book's first content language: the lint looks for that word,
    so a Polish book can say its own, and a hand-authored cover follows the same rule. English is never translated."""
    assert bc("state", "--set", "content_languages=pl", project=proj).returncode == 0
    assert bc("state", "--record", "G5", "edition approved (test)", project=proj).returncode == 0
    # no label for the word: it stays English, the book says so, and the lint accepts the English word
    assert bc("book", project=proj).returncode == 0
    assert "APPROVED 2026-10-17" in cover_html(proj)
    assert re.search(r"label\(s\) have no pl translation[^\"]*APPROVED", json.dumps(report(proj, "book")))
    assert bc("book-lint", "--self-consistency", project=proj).returncode == 0
    # the project's own word: the stamp says it, the English one is gone, and the lint wants the project's
    (proj / "book/book.json").write_text(json.dumps({"schema": 1, "labels": {"pl": {"APPROVED": "ZATWIERDZONO"}}}))
    assert bc("book", project=proj).returncode == 0
    assert "ZATWIERDZONO 2026-10-17" in cover_html(proj) and "APPROVED" not in cover_html(proj)
    assert bc("book-lint", "--self-consistency", project=proj).returncode == 0
    assert lint_row(proj, "edition:stamp")["status"] == "pass"
    # a hand-authored cover that kept the English word where the labels say another fails, naming the word it wants
    mutate(proj / "book.html", "ZATWIERDZONO 2026-10-17", "APPROVED 2026-10-17")
    assert bc("book-lint", project=proj).returncode == 1
    row = lint_row(proj, "edition:stamp")
    assert row["status"] == "fail" and "has no ZATWIERDZONO stamp but the edition is approved" in row["detail"] and "labels.pl.APPROVED" in row["detail"]
    mutate(proj / "book.html", "APPROVED 2026-10-17", "ZATWIERDZONO 2026-10-17")
    assert bc("book-lint", project=proj).returncode == 0
    # the lint's word is the first content language's: with pl,en the English chapters do not change the cover
    assert bc("state", "--set", "content_languages=pl,en", project=proj).returncode == 0
    for f in list((proj / "book/chapters").glob("*.md")):
        shutil.copy(f, f.with_name(f.stem + ".pl.md"))
        f.rename(f.with_name(f.stem + ".en.md"))
    assert bc("book", project=proj).returncode == 0 and "ZATWIERDZONO 2026-10-17" in cover_html(proj)
    assert bc("book-lint", project=proj).returncode == 0
    # English is never translated, in the generator and in the lint alike
    assert bc("state", "--set", "content_languages=en", project=proj).returncode == 0
    for f in list((proj / "book/chapters").glob("*.pl.md")):
        f.unlink()
    for f in list((proj / "book/chapters").glob("*.en.md")):
        f.rename(f.with_name(f.name.replace(".en.md", ".md")))
    (proj / "book/book.json").write_text(json.dumps({"schema": 1, "labels": {"en": {"APPROVED": "SIGNED OFF"}}}))
    assert bc("book", project=proj).returncode == 0 and "APPROVED 2026-10-17" in cover_html(proj) and "SIGNED OFF" not in cover_html(proj)
    assert bc("book-lint", project=proj).returncode == 0


def cover_title(proj: Path) -> str:
    return re.search(r"<h1>(.*?)</h1>", cover_html(proj), re.S).group(1)


@setup
@resvg
def test_the_cover_title_is_the_drawn_wordmark_with_its_dark_pair_and_the_name_as_alt(proj):
    """Acme has a wordmark and its dark file: the cover's h1 holds both as images (alt = the name), switched like the cover's marks."""
    import base64
    html = (proj / "book.html").read_text()
    imgs = [t for t in htmlscan.tags(cover_title(proj)) if t.name == "img"]
    assert [(t.attrs["class"], t.attrs["data-mark"], t.attrs["alt"]) for t in imgs] == [("wm sch-l", "wordmark", "Acme"), ("wm sch-d", "wordmark-dark", "Acme")]
    for t, f in zip(imgs, ("wordmark.svg", "wordmark-dark.svg")):
        assert base64.b64decode(t.attrs["src"].split(",", 1)[1]).decode() == (proj / "assets/logo" / f).read_text()
    # Acme's wordmark is 282.17 x 77.82: in the cover's art box (at most 320 wide, 96 tall) it is 320 wide and 320 x 77.82 / 282.17 = 88.25, so 88, tall
    assert [(t.attrs["width"], t.attrs["height"]) for t in imgs] == [("320", "88")] * 2
    assert "<h1>Acme</h1>" not in html and html.count('class="wm') == 2
    assert ".cover .sch-d{display:none}" in html and "@media (prefers-color-scheme:dark){.cover .sch-l{display:none}.cover .sch-d{display:block}}" in html   # dark scheme
    assert "@media print{" in html and ".cover .sch-l{display:block}.cover .sch-d{display:none}" in html                                                       # and print
    r = bc("book-lint", "--self-consistency", project=proj)
    assert r.returncode == 0, r.stdout
    rows = {x["id"]: x["status"] for x in report(proj, "book-lint")["results"]}
    for rid in ("marks:lint", "words:scratch", "words:round", "words:forbidden", "words:status", "images:alt", "edition:stamp", "self:colours", "self:font-size"):
        assert rows[rid] == "pass", (rid, rows[rid])


@setup
@resvg
def test_without_a_wordmark_the_cover_types_the_name_and_without_a_dark_one_it_says_so(proj):
    logo = proj / "assets/logo"
    (logo / "wordmark-dark.svg").rename(proj / "wordmark-dark.svg")
    assert bc("book", project=proj).returncode == 0
    imgs = [t for t in htmlscan.tags(cover_title(proj)) if t.name == "img"]
    assert [t.attrs["class"] for t in imgs] == ["wm"] and "sch-" not in cover_title(proj)       # the light wordmark only: no switch
    assert "wordmark-dark.svg does not exist; the cover shows the light wordmark in dark mode too" in json.dumps(report(proj, "book"))
    assert bc("book-lint", "--self-consistency", project=proj).returncode == 0
    (logo / "wordmark.svg").rename(proj / "wordmark.svg")
    r = bc("book", project=proj)
    assert r.returncode == 0, r.stdout + r.stderr
    assert cover_title(proj) == "Acme" and "<h1>Acme</h1>" in cover_html(proj)                  # no wordmark: the typed name stays
    assert bc("book-lint", "--self-consistency", project=proj).returncode == 0


@setup
@resvg
def test_a_pixel_art_wordmark_on_the_cover_is_set_at_a_whole_number_scale(proj):
    """A wordmark drawn on a 30 x 5 grid (shape-rendering crispEdges): a vector would be fitted to 320 x 53, pixel art takes the whole scale 10, so 300 x 50."""
    for name, ink in (("wordmark", "#0d1b2d"), ("wordmark-dark", "#f0eee7")):
        (proj / f"assets/logo/{name}.svg").write_text(
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 30 5" shape-rendering="crispEdges"><rect x="0" y="0" width="3" height="5" fill="{ink}"/>'
            f'<rect x="4" y="0" width="26" height="1" fill="{ink}"/></svg>')
    assert bc("book", project=proj).returncode == 0
    imgs = [t for t in htmlscan.tags(cover_title(proj)) if t.name == "img"]
    assert [(t.attrs["width"], t.attrs["height"]) for t in imgs] == [("300", "50")] * 2
    assert bc("book-lint", "--self-consistency", project=proj).returncode == 0


@setup
@resvg
def test_a_stamp_label_that_is_empty_or_not_text_is_a_usage_error(proj):
    for bad in ("", "  "):
        (proj / "book/book.json").write_text(json.dumps({"schema": 1, "labels": {"pl": {"APPROVED": bad}}}))
        r = bc("book", project=proj)
        assert r.returncode == 2 and "labels.pl.APPROVED is the cover's approval stamp" in r.stderr, (bad, r.stderr)
    # a labels entry that is not an object of words stops the run with exit 2, never a traceback
    for bad in ({"APPROVED": 7}, {"APPROVED": None}, "ZATWIERDZONO", ["ZATWIERDZONO"]):
        (proj / "book/book.json").write_text(json.dumps({"schema": 1, "labels": {"pl": bad}}))
        assert bc("state", "--set", "content_languages=pl", project=proj).returncode == 0
        for cmd in (("book",), ("book-lint",)):
            r = bc(*cmd, project=proj)
            assert r.returncode == 2 and "labels.pl must be an object of English word to its translation" in r.stderr, (bad, cmd, r.stderr)


@setup
@resvg
def test_the_stamp_word_is_trimmed_and_found_in_the_stamp_not_in_the_other_cover_labels(proj):
    """Spaces around the label do not break the build, and a cover label that shares the stamp word (Approval translated as the same word)
    cannot pass for the stamp while the edition waits for approval."""
    assert bc("state", "--set", "content_languages=pl", project=proj).returncode == 0
    (proj / "book/book.json").write_text(json.dumps({"schema": 1, "labels": {"pl": {"APPROVED": "Akceptacja", "Approval": "Akceptacja"}}}))
    r = bc("book", project=proj)
    assert r.returncode == 0, r.stdout + r.stderr                       # pending: the Approval label says the word, the stamp does not
    assert bc("book-lint", project=proj).returncode == 0 and lint_row(proj, "edition:stamp")["status"] == "pass"
    assert bc("state", "--record", "G5", "edition approved (test)", project=proj).returncode == 0
    (proj / "book/book.json").write_text(json.dumps({"schema": 1, "labels": {"pl": {"APPROVED": " ZATWIERDZONO "}}}))
    r = bc("book", project=proj)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "ZATWIERDZONO 2026-10-17" in cover_html(proj) and bc("book-lint", project=proj).returncode == 0


@setup
@resvg
def test_the_status_line_on_the_cover_is_a_facts_value_or_absent(proj):
    assert "Status" not in (proj / "book.html").read_text().split("</dl>")[0]    # the new project's FACTS.md has no status row
    add_fact(proj, "status", "the online shop is in development")
    assert bc("book", project=proj).returncode == 0
    cover = (proj / "book.html").read_text().split("</dl>")[0]
    assert "the online shop is in development" in cover


@setup
@resvg
def test_book_lint_passes_the_built_book_and_check_gates_it(proj):
    r = bc("book-lint", "--self-consistency", project=proj)
    assert r.returncode == 0, r.stdout
    rows = {x["id"]: x["status"] for x in report(proj, "book-lint")["results"]}
    for rid in ("ids:duplicate", "anchors:broken", "network:refs", "words:scratch", "words:round", "words:forbidden", "words:status", "lang:parity",
                "marks:lint", "chapters:required", "edition:stamp", "counts:data", "counts:typed", "files:accounting", "self:durations",
                "self:font-size", "self:colours"):
        assert rows.get(rid) == "pass", (rid, rows.get(rid))
    bc("check", project=proj)
    ids = {x["id"]: x["status"] for x in report(proj, "check")["results"]}
    assert ids["report:book-lint"] == "pass" and ids["report:book"] == "pass" and ids["book:generated"] == "pass"


@setup
@resvg
def test_check_fails_a_generated_book_edited_by_hand_and_notices_a_state_change(proj):
    mutate(proj / "book.html", '<p class="eyebrow">Brand book</p>', '<p class="eyebrow">Brand book, edited by hand</p>')   # the cover's title is the drawn wordmark: no text to edit
    bc("check", project=proj)
    ids = {x["id"]: x["status"] for x in report(proj, "check")["results"]}
    assert ids["book:generated"] == "fail" and ids["report:book"] == "pass"     # the sources did not change; the output did
    assert bc("book", project=proj).returncode == 0
    assert bc("state", "--record", "G6", "adopted (test)", project=proj).returncode == 0
    bc("check", project=proj)
    ids = {x["id"]: x["status"] for x in report(proj, "check")["results"]}
    assert ids["report:book:state"] == "skipped"       # the cover says "approved" now: rebuild


def cover_adoption(proj: Path) -> str:
    html = (proj / "book.html").read_text()
    m = re.search(r"<dt>Adoption</dt><dd>(.*?)</dd>", html)
    assert m, "the cover has no Adoption row"
    return m.group(1)


def test_the_cover_claims_adoption_only_as_far_as_the_data_back_it(proj):
    assert cover_adoption(proj) == "Adoption not yet approved" and not (proj / "adoption.json").exists()
    assert bc("state", "--record", "G6", "go (test)", project=proj).returncode == 0
    assert bc("book", project=proj).returncode == 0
    assert cover_adoption(proj) == "Adoption approved 2026-10-17"     # the owner's go is not progress: no 'applied'
    assert "Applied to products" not in (proj / "book.html").read_text()
    (proj / "adoption.json").write_text(json.dumps({"rows": [{"n": 1}, {"n": 2}, {"n": 3}], "progress": {"1": "done", "2": "doing"}}))
    assert bc("book", project=proj).returncode == 0
    assert cover_adoption(proj) == "Adoption approved 2026-10-17; 1 of 3 rows done"
    assert bc("book", "--verify", project=proj).returncode == 0
    (proj / "adoption.json").write_text(json.dumps({"rows": [{"n": 1}, {"n": 2}, {"n": 3}], "progress": {"1": "done", "2": "done", "3": "done"}}))
    r = bc("book", "--verify", project=proj)
    assert r.returncode != 0, "a changed row progress must make the built book stale"
    assert bc("book", project=proj).returncode == 0 and cover_adoption(proj).endswith("3 of 3 rows done")


def test_an_adoption_json_that_is_not_an_adoption_record_stops_the_book(proj):
    (proj / "adoption.json").write_text('{"rows": "x"}')
    r = bc("book", project=proj)
    assert r.returncode == 2 and "adoption.json is not an adoption record" in r.stderr


@setup
def test_the_book_keeps_its_16px_side_gutter_on_the_cover_and_the_colophon(proj):
    def gutters():
        r = bc("shot", "book.html", "--out", str(proj.parent / "shots"), "--dsf", "1", project=proj)
        assert r.returncode == 0, r.stdout + r.stderr
        return {x["id"]: (x["gutter_left"], x["gutter_right"]) for x in report(proj, "shot")["results"]}
    g = gutters()
    assert set(g) == {"view:1440-light", "view:1440-dark", "view:390-light", "view:390-dark"}
    for view in ("view:390-light", "view:390-dark"):
        assert g[view][0] >= 16 and g[view][1] >= 16, (view, g[view])
    # mutation: the old rules (padding shorthand on .cover and .colophon override the .wrap gutter) must be caught by the same measurement
    mutate(proj / "book.html", ".cover{padding-top:56px;padding-bottom:40px}", ".cover{padding:56px 0 40px}")
    mutate(proj / "book.html", "padding-top:24px;padding-bottom:48px}", "padding:24px 0 48px;margin:0}")
    g = gutters()
    assert g["view:390-light"][0] == 0, g["view:390-light"]     # the cover text starts at the screen edge


# ---------------------------------------------------------------- the lint: each rule broken in a scratch copy

def build_fails(proj, needle, rule=None):
    r = bc("book", project=proj)
    out = r.stdout + r.stderr
    assert r.returncode == 1, out
    assert needle in out, out
    if rule:
        rows = {x["id"]: x["status"] for x in report(proj, "book")["results"]}
        assert rows[f"lint:{rule}"] == "fail", rows
    return out


@setup
@resvg
def test_a_typed_count_that_disagrees_with_the_data_fails(proj):
    n = len(json.loads((proj / "assets/manifest.json").read_text())["artefacts"])
    mutate(proj / "book/chapters/files.md", "The pack holds", f"There are {n + 40} files here. The pack holds")
    build_fails(proj, f"\"{n + 40} files\" but the data say {n} files", "counts:typed")
    # the same sentence with the right number is allowed (and {{count:files}} is the way to write it)
    mutate(proj / "book/chapters/files.md", f"{n + 40} files", f"{n} files")
    assert bc("book", project=proj).returncode == 0


@setup
@resvg
def test_a_logo_name_that_leaves_the_project_is_refused(proj):
    mutate(proj / "book/chapters/mark.md", "## By size", "{{marks:../../../outside}}\n\n## By size")
    r = bc("book", project=proj)
    assert r.returncode == 2 and "outside the project" in r.stderr, r.stdout + r.stderr


@setup
@resvg
def test_a_round_word_in_chapter_two_fails_but_the_history_chapter_may_use_it(proj):
    mutate(proj / "book/chapters/mark.md", "## By size", "## By size\n\nThis came out of Round 2 and v3.\n")
    build_fails(proj, "'Round 2'", "words:round")
    mutate(proj / "book/chapters/mark.md", "This came out of Round 2 and v3.", "A plain sentence.")
    mutate(proj / "book/chapters/history.md", "## How the system was decided", "## How the system was decided\n\nRound 2 narrowed it; decision 3 closed it.\n")
    assert bc("book", project=proj).returncode == 0


@setup
@resvg
def test_a_network_reference_fails(proj):
    mutate(proj / "book/chapters/use.md", "## In use", "## In use\n\nSee [the site](https://example.com/brand).\n")
    build_fails(proj, "network address in a link", "network:refs")


@setup
@resvg
def test_network_script_and_unembedded_resources_in_the_html_fail_book_lint(proj):
    mutate(proj / "book.html", "<main", '<script src="https://cdn.example.com/x.js"></script><img src="logo.png" alt="x"><main')
    r = bc("book-lint", project=proj)
    assert r.returncode == 1
    detail = next(x["detail"] for x in report(proj, "book-lint")["results"] if x["id"] == "network:refs")
    assert "<script> element" in detail and "is not embedded" in detail


@setup
@resvg
def test_a_status_word_not_in_facts_fails_and_one_in_facts_passes(proj):
    mutate(proj / "book/chapters/idea.md", "## The idea", "## The idea\n\nThe shop is coming soon.\n")
    build_fails(proj, "'coming soon'", "words:status")
    add_fact(proj, "status", "the shop is coming soon")
    assert bc("book", project=proj).returncode == 0


@setup
@resvg
def test_a_motion_duration_outside_the_tokens_fails(proj):
    mutate(proj / "book.html", "</style>", "a{transition:color 900ms}@media (prefers-reduced-motion:reduce){a{transition:none}}</style>")   # switched off under reduced motion, as motion:reduced wants
    r = bc("book-lint", "--self-consistency", project=proj)
    assert r.returncode == 1
    detail = next(x["detail"] for x in report(proj, "book-lint")["results"] if x["id"] == "self:durations")
    assert "900ms" in detail and "150ms" in detail
    mutate(proj / "book.html", "900ms", "150ms")
    assert bc("book-lint", "--self-consistency", project=proj).returncode == 0     # a duration that is a token is fine


@setup
@resvg
def test_durations_named_motion_in_the_starter_tokens_count_as_well(proj):
    """The starter tokens name their durations motion.*, Acme names them duration.*: the self-check reads both."""
    tj = proj / "assets" / "tokens" / "tokens.json"
    doc = json.loads(tj.read_text())
    renamed = {("motion." + k.split(".", 1)[1] if k.startswith("duration.") else k): v for k, v in doc["other"].items()}
    assert renamed != doc["other"]
    doc["other"] = renamed
    tj.write_text(json.dumps(doc, indent=2) + "\n")
    assert bookdata.motion_durations_ms(doc) and not any(k.startswith("duration.") for k in doc["other"])
    mutate(proj / "book.html", "</style>", "a{transition:color 150ms}@media (prefers-reduced-motion:reduce){a{transition:none}}</style>")
    assert bc("book-lint", "--self-consistency", project=proj).returncode == 0
    mutate(proj / "book.html", "150ms", "900ms")
    assert bc("book-lint", "--self-consistency", project=proj).returncode == 1


@setup
@resvg
def test_text_in_a_mark_fails_in_the_source_and_in_the_html(proj):
    mutate(proj / "assets/logo/mark.svg", "</svg>", "<text x='1' y='9'>A</text></svg>")
    out = bc("book", project=proj)
    assert out.returncode == 1 and "<text> element" in out.stdout + out.stderr
    mutate(proj / "assets/logo/mark.svg", "<text x='1' y='9'>A</text>", "")
    assert bc("book", project=proj).returncode == 0
    mutate(proj / "book.html", "<h2>Idea</h2>", '<h2>Idea</h2><svg viewBox="0 0 8 8"><text>A</text></svg>')
    r = bc("book-lint", project=proj)
    assert r.returncode == 1
    assert "<text> element" in next(x["detail"] for x in report(proj, "book-lint")["results"] if x["id"] == "marks:lint")


@setup
@resvg
def test_a_colour_or_font_size_outside_the_rules_fails_the_self_consistency_lint(proj):
    mutate(proj / "book.html", "</style>", "p{color:#123456;font-size:9px}</style>")
    r = bc("book-lint", "--self-consistency", project=proj)
    assert r.returncode == 1
    rows = {x["id"]: x for x in report(proj, "book-lint")["results"]}
    assert rows["self:colours"]["status"] == "fail" and "#123456" in rows["self:colours"]["detail"]
    assert rows["self:font-size"]["status"] == "fail" and "9 px" in rows["self:font-size"]["detail"]


@setup
@resvg
def test_unfilled_markers_unknown_directives_and_missing_chapter_files_fail_the_build(proj):
    mutate(proj / "book/chapters/type.md", "## Tokens", "## Tokens\n\n[[fill: still to write]]\n")
    build_fails(proj, "unfilled marker")
    mutate(proj / "book/chapters/type.md", "[[fill: still to write]]", "Done.")
    shutil.move(proj / "book/chapters/use.md", proj / "use.md.moved")
    build_fails(proj, "chapter use has no content file")


@setup
@resvg
def test_a_forbidden_word_from_the_brief_fails(proj):
    (proj / "research").mkdir(exist_ok=True)
    (proj / "research/cliches.md").write_text("# Clichés\n\n## Forbidden\n\n- lightbulb\n- world-class\n")
    mutate(proj / "book/chapters/idea.md", "## The idea", "## The idea\n\nA world-class lightbulb moment.\n")
    out = build_fails(proj, "'lightbulb'", "words:forbidden")
    assert "'world-class'" in out


@setup
@resvg
def test_a_quoted_fact_must_equal_facts_md(proj):
    add_fact(proj, "batch size", "tools are made in batches of 200")
    mutate(proj / "book/chapters/idea.md", "## The idea", "## The idea\n\nBatches: {{fact:batch size}}.\n")
    assert bc("book", project=proj).returncode == 0
    mutate(proj / "book.html", "tools are made in batches of 200", "tools are made in batches of 300")
    r = bc("book-lint", project=proj)
    assert r.returncode == 1
    assert "FACTS.md says" in next(x["detail"] for x in report(proj, "book-lint")["results"] if x["id"] == "facts:data")
    (proj / "book/chapters/idea.md").write_text((proj / "book/chapters/idea.md").read_text().replace("{{fact:batch size}}", "{{fact:no such row}}"))
    build_fails(proj, "FACTS.md has no row named 'no such row'")


@setup
@resvg
def test_a_file_missing_from_the_files_chapter_fails_the_accounting(proj):
    manifest = json.loads((proj / "assets/manifest.json").read_text())["artefacts"]
    victim = manifest[0]["path"]
    html = (proj / "book.html").read_text()
    tag = next(t for t in htmlscan.tags(html) if not t.closing and t.attrs.get("data-path") == victim)
    end = htmlscan.element_end(html, tag)
    (proj / "book.html").write_text(html[:tag.start] + html[end:])
    assert (proj / "book.html").read_text() != html
    r = bc("book-lint", project=proj)
    assert r.returncode == 1
    assert victim in next(x["detail"] for x in report(proj, "book-lint")["results"] if x["id"] == "files:accounting")


@setup
@resvg
def test_a_missing_chapter_and_leftover_scaffolding_fail_book_lint(proj):
    html = (proj / "book.html").read_text()
    tag = next(t for t in htmlscan.tags(html) if t.name == "section" and t.attrs.get("data-chapter") == "donts")
    end = htmlscan.element_end(html, tag)
    (proj / "book.html").write_text(html[:tag.start] + html[end:])
    assert bc("book-lint", project=proj).returncode == 1
    assert "donts" in next(x["detail"] for x in report(proj, "book-lint")["results"] if x["id"] == "chapters:required")
    (proj / "book.html").write_text(html.replace("<main", '<div data-variant="nav:a"></div><main', 1))
    assert bc("book-lint", project=proj).returncode == 1
    assert "nav:a" in next(x["detail"] for x in report(proj, "book-lint")["results"] if x["id"] == "variants:open")


@setup
@resvg
def test_duplicate_ids_and_broken_anchors_fail(proj):
    mutate(proj / "book.html", '<section class="ch" id="files"', '<section class="ch" id="idea"')
    mutate(proj / "book.html", 'href="#proof"', 'href="#nowhere"')
    assert bc("book-lint", project=proj).returncode == 1
    rows = {x["id"]: x for x in report(proj, "book-lint")["results"]}
    assert rows["ids:duplicate"]["status"] == "fail" and "idea" in rows["ids:duplicate"]["detail"]
    assert rows["anchors:broken"]["status"] == "fail" and "#nowhere" in rows["anchors:broken"]["detail"]


@setup
@resvg
def test_open_variants_need_an_explicit_flag_and_still_fail_the_lint(proj):
    mutate(proj / "book/chapters/idea.md", "## The idea", "## The idea\n\n::: variant nav a\nOption A.\n:::\n\n::: variant nav b\nOption B.\n:::\n")
    build_fails(proj, "an open choice")
    r = bc("book", "--allow-variants", project=proj)
    assert r.returncode == 0 and 'data-variant="nav:a"' in (proj / "book.html").read_text()
    assert bc("book-lint", project=proj).returncode == 1       # the gate does not take the review flag


@setup
@resvg
def test_a_legal_disclosure_from_facts_must_appear_verbatim(proj):
    add_fact(proj, "legal: registration", "Acme Ltd, registered in Exampleland under 000000")
    r = bc("book-lint", project=proj)
    assert r.returncode == 1
    assert "not in the book" in next(x["detail"] for x in report(proj, "book-lint")["results"] if x["id"].startswith("legal:"))
    mutate(proj / "book/chapters/idea.md", "## The idea", "## The idea\n\nAcme Ltd, registered in Exampleland under 000000.\n")
    assert bc("book", project=proj).returncode == 0
    assert bc("book-lint", project=proj).returncode == 0


@setup
@resvg
def test_a_superseded_open_graph_file_is_listed_with_a_note_and_the_book_goes_stale_when_the_marking_changes(proj):
    """emit social keeps the Open Graph file of an earlier card (cached link previews may still use its URL), so its manifest row stays, marked
    superseded: the files chapter lists it with a note instead of as a second current card, and a change of the marking makes the book stale."""
    from helpers import mutate_json
    assert bc("emit", "social", project=proj).returncode == 0
    assert bc("emit", "social", "--name", "Acme Tools", project=proj).returncode == 0      # a new card, a new file name: the first one is kept
    og = [a for a in json.loads((proj / "assets/manifest.json").read_text())["artefacts"] if a["path"].startswith("assets/social/og-")]
    old, new = [a["path"] for a in og if a.get("superseded")], [a["path"] for a in og if not a.get("superseded")]
    assert len(old) == 1 and len(new) == 1
    assert bc("book", project=proj).returncode == 0
    html = (proj / "book.html").read_text()
    rows = {t.attrs["data-path"]: html[t.start:htmlscan.element_end(html, t)] for t in htmlscan.tags(html) if not t.closing and t.name == "tr" and "data-path" in t.attrs}
    note = "superseded, kept for cached link previews"
    assert note in rows[old[0]] and note not in rows[new[0]] and html.count(note) == 1
    assert bc("book-lint", "--self-consistency", project=proj).returncode == 0
    assert report(proj, "book-lint")["status"] == "pass" and {x["id"]: x["status"] for x in report(proj, "book-lint")["results"]}["files:accounting"] == "pass"
    # the marking is part of what the book shows: without it the same book is not verified any more, with it again it is
    bc("check", project=proj)
    assert "report:book:manifest" not in {x["id"] for x in report(proj, "check")["results"]}
    mutate_json(proj / "assets/manifest.json", lambda d: next(a for a in d["artefacts"] if a["path"] == old[0]).pop("superseded"))
    bc("check", project=proj)
    assert {x["id"]: x["status"] for x in report(proj, "check")["results"]}["report:book:manifest"] == "skipped"
    # a manifest with no marked row hashes as it always did (the books of earlier projects stay current)
    rows0 = sorted(({k: a.get(k) for k in ("path", "sha256", "bytes", "emitter", "slot", "size", "band")}
                    for a in bookdata.manifest_rows(proj)), key=lambda r: r["path"])
    import hashlib
    assert bookdata.manifest_view_sha(proj) == hashlib.sha256(json.dumps(rows0, sort_keys=True).encode()).hexdigest()


# ---------------------------------------------------------------- two content languages

@setup
@resvg
def test_two_languages_need_every_chapter_in_both_with_the_same_structure(proj):
    assert bc("state", "--set", "content_languages=pl,en", project=proj).returncode == 0
    build_fails(proj, "no content file book/chapters/idea.pl.md")
    for f in list((proj / "book/chapters").glob("*.md")):
        shutil.copy(f, f.with_name(f.stem + ".pl.md"))
        f.rename(f.with_name(f.stem + ".en.md"))
    r = bc("book", project=proj)
    assert r.returncode == 0, r.stdout + r.stderr
    html = (proj / "book.html").read_text()
    assert '<html lang="pl">' in html and 'lang="en" data-key="idea"' in html and 'lang="pl" data-key="idea"' in html
    assert re.search(r'label\(s\) have no pl translation', json.dumps(report(proj, "book")))     # the labels fall back to English, said out loud
    mutate(proj / "book/chapters/idea.pl.md", "## What stays fixed", "## What stays fixed\n\nAn extra paragraph only in Polish.\n")
    out = build_fails(proj, "idea: en and pl differ in structure", "lang:parity")
    assert "differ in structure at block" in out


@setup
@resvg
def test_content_languages_must_be_set_and_never_default_from_the_chat_language(proj):
    mutate(proj / "BRAND-STATE.md", "content_languages: en", 'content_languages: ""')
    r = bc("book", project=proj)
    assert r.returncode == 2 and "no content language" in r.stderr


@setup
@resvg
def test_an_authored_vector_brand_cannot_build_its_book(proj):
    assert bc("state", "--set", "mark_source=authored-vector", project=proj).returncode == 0
    r = bc("book", project=proj)
    assert r.returncode == 2 and "hand-authored" in r.stderr and "patch" in r.stderr
    assert bc("book-lint", "--self-consistency", project=proj).returncode == 0       # the gate still reads the file


@setup
@resvg
def test_the_fonts_of_the_project_are_embedded_as_data_uris(proj):
    font = ROOT / "tests/fixtures/fonts/TestFont-subset.ttf"
    (proj / "assets/fonts").mkdir(parents=True)
    shutil.copy(font, proj / "assets/fonts/test.ttf")
    (proj / "book/book.json").write_text(json.dumps({"schema": 1, "fonts": [{"family": "Test Face", "file": "assets/fonts/test.ttf", "weight": 400}]}))
    r = bc("book", project=proj)
    assert r.returncode == 0, r.stdout + r.stderr
    html = (proj / "book.html").read_text()
    assert re.search(r'@font-face\{font-family:"Test Face";font-weight:400;font-style:normal;font-display:block;src:url\(data:font/ttf;base64,', html)
    assert "<link" not in html


@setup
@resvg
def test_an_unknown_key_in_book_json_is_exit_2_not_a_silent_default(proj):
    (proj / "book/book.json").write_text(json.dumps({"schema": 1, "min_label": 12}))
    r = bc("book", project=proj)
    assert r.returncode == 2 and "unknown key 'min_label'" in r.stderr


# ---------------------------------------------------------------- the PDF export

@setup
@resvg
@pytest.mark.requires_gs
def test_book_pdf_is_an_rgb_proof_labelled_in_the_metadata_and_on_the_cover(proj):
    r = bc("book-pdf", project=proj)
    assert r.returncode == 0, r.stdout + r.stderr
    pdf = proj / "book.pdf"
    info = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
    assert "Subject:         RGB, not print-ready" in info and "Title:           Acme brand book, edition 1" in info
    pages = int(re.search(r"Pages:\s+(\d+)", info).group(1))
    assert pages >= 5 and "A4" in info
    first = subprocess.run(["pdftotext", "-f", "1", "-l", "1", str(pdf), "-"], capture_output=True, text=True).stdout
    assert "RGB, not print-ready" in " ".join(first.split()) and "brand book" in " ".join(first.split()).lower()   # the name is the drawn wordmark: an image, no text
    # the drawn title prints as vector paths (no text, no raster image), so the guard is on the print CSS: nothing hides the cover's title
    css = (proj / "book.html").read_text().split("<style>", 1)[1].split("</style>", 1)[0]
    printed = css[css.index("@media print"):]
    assert not re.search(r"(\.wm|\.cover\s+h1)[^{}]*\{[^}]*display\s*:\s*none", printed), "the print CSS hides the cover's drawn title"
    assert re.search(r'<h1[^>]*><img class="wm[^"]*"', cover_html(proj))
    data = pdf.read_bytes()
    assert b"/DeviceCMYK" not in data and b"/OutputIntents" not in data and b"/ObjStm" not in data
    rows = {x["id"]: x["status"] for x in report(proj, "book-pdf")["results"]}
    assert rows["pdf:label-metadata"] == rows["pdf:label-xmp"] == rows["pdf:label-cover"] == rows["pdf:colour"] == rows["pdf:determinism"] == "pass"
    assert rows["pdf:print-ready"] == "info"
    # two runs, one machine, the same bytes
    again = bc("book-pdf", project=proj)
    assert again.returncode == 0 and "unchanged" in again.stdout and pdf.read_bytes() == data
    letter = bc("book-pdf", "--format", "Letter", "--out", "book-letter.pdf", project=proj)
    assert letter.returncode == 0
    assert "612 x 792" in subprocess.run(["pdfinfo", str(proj / "book-letter.pdf")], capture_output=True, text=True).stdout


@setup
@resvg
@pytest.mark.requires_gs
def test_book_pdf_refuses_a_book_that_does_not_lint_clean(proj):
    mutate(proj / "book.html", "<main", '<script>1</script><main')
    r = bc("book-pdf", project=proj)
    assert r.returncode == 1 and "does not lint clean" in r.stderr
    assert not (proj / "book.pdf").exists()


PRINT_MARGIN_PT = 14 / 25.4 * 72   # render.mjs prints the book with a 14 mm margin on every side
PX_PER_PT = 96 / 72                # CSS px per point


def pdf_pages(pdf: Path) -> list[str]:
    """The text of every page of a PDF, read with poppler's pdftotext."""
    n = int(re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout).group(1))
    return [subprocess.run(["pdftotext", "-f", str(i), "-l", str(i), str(pdf), "-"], capture_output=True, text=True).stdout for i in range(1, n + 1)]


def room_below(pdf: Path, word: str) -> tuple[int, float]:
    """(its page, CSS px between the word and the bottom of that page's content area) of the word's last line, read with pdftotext -bbox."""
    for i in range(1, len(pdf_pages(pdf)) + 1):
        xml = subprocess.run(["pdftotext", "-bbox", "-f", str(i), "-l", str(i), str(pdf), "-"], capture_output=True, text=True).stdout
        w = re.search(rf'<word xMin="[\d.]+" yMin="[\d.]+" xMax="[\d.]+" yMax="([\d.]+)">{word}</word>', xml)
        if w:
            return i, (float(re.search(r'<page width="[\d.]+" height="([\d.]+)">', xml).group(1)) - PRINT_MARGIN_PT - float(w.group(1))) * PX_PER_PT
    raise AssertionError(f"{word} is on no page of {pdf.name}")


def assert_no_empty_page_when_the_end_is_near_the_page_bottom(proj: Path, html_for, next_title: str) -> None:
    """`html_for(spacer)` is the book with its last block (the word ENDMARKER, on a page that goes on from an earlier one) `spacer` px lower. Print it
    once, work out from that print how far ENDMARKER is above the page's content end, print it again with 30 px left (inside the 48 px of padding and
    the 12 px of margin, or the 40 px of cover padding, that a box ending there needs below its last line) and check: the same number of pages, none
    without text, and the next chapter on the very next page."""
    def printed(spacer: int) -> Path:
        (proj / "book.html").write_text(html_for(spacer))
        r = bc("book-pdf", "--out", f"print-{spacer}.pdf", project=proj)
        assert r.returncode == 0, r.stdout + r.stderr
        return proj / f"print-{spacer}.pdf"
    first = printed(0)
    page, room = room_below(first, "ENDMARKER")
    assert page >= 2, "the last block must be on a page that goes on from an earlier one, or this proves nothing"
    second = printed(max(0, int(room - 30)))
    page2, room2 = room_below(second, "ENDMARKER")
    assert page2 == page and 0 < room2 < 40, (page, page2, room2)       # still on its page, and inside the 40 px the padding below its last line needs
    pages = pdf_pages(second)
    assert len(pages) == len(pdf_pages(first)), "the same book prints one page longer: an empty page came with the padding"
    assert [n + 1 for n, t in enumerate(pages) if not t.strip()] == []
    assert pages[page2].lstrip().startswith(next_title), pages[page2][:80]   # the next chapter starts on the very next page


@setup
@resvg
@pytest.mark.requires_gs
@pytest.mark.requires_pdftotext
def test_no_page_of_the_book_pdf_is_empty_when_a_chapter_ends_at_the_bottom_of_its_last_page(proj):
    """A chapter that goes on from an earlier page and ends within its bottom padding (48 px) and the margin of its last line (12 px) of the page's end
    sent that padding to a page of its own, and the next chapter's page break left that page empty. The first chapter is lengthened to two pages."""
    html0 = (proj / "book.html").read_text()
    end = html0.index("\n</div>\n</section>", html0.index('id="idea"'))
    filler = "<p>Acme sample text for this slot.</p>\n" * 50

    def html_for(spacer: int) -> str:
        return html0[:end] + "\n" + filler + (f'<div style="height:{spacer}px"></div>\n' if spacer else "") + "<p>ENDMARKER</p>" + html0[end:]
    assert_no_empty_page_when_the_end_is_near_the_page_bottom(proj, html_for, "The mark by size")


@setup
@resvg
@pytest.mark.requires_gs
@pytest.mark.requires_pdftotext
def test_no_page_of_the_book_pdf_is_empty_when_the_cover_ends_at_the_bottom_of_its_second_page(proj):
    """The same for the cover (40 px of bottom padding, then the first chapter's page break): its table of contents starts a second page and is moved
    down by its own top padding until its last entry ends 30 px above the page's end."""
    html0 = (proj / "book.html").read_text()
    assert html0.count('<ol class="toc">') == 1

    def html_for(spacer: int) -> str:
        page = html0.replace('<ol class="toc">', f'<ol class="toc" style="break-before:page;padding-top:{spacer}px">')
        return page.replace("</ol>", '<li><a href="#idea" data-n="99">ENDMARKER</a></li></ol>', 1)
    assert_no_empty_page_when_the_end_is_near_the_page_bottom(proj, html_for, "Idea")


# ---------------------------------------------------------------- the press kit contains the book, so the book leaves it out

@setup
@resvg
def test_the_press_kit_is_left_out_of_the_book_and_does_not_make_its_reports_stale(proj):
    from helpers import mutate_json
    r = bc("emit", "presskit", "--no-book", project=proj)
    assert r.returncode == 0, r.stdout + r.stderr
    kit = "assets/presskit/acme-press-kit.zip"
    assert any(a["path"] == kit for a in json.loads((proj / "assets/manifest.json").read_text())["artefacts"])
    r = bc("book", project=proj)                                     # the files chapter now says where the kit is, without its checksum
    assert r.returncode == 0, r.stdout + r.stderr
    html = (proj / "book.html").read_text()
    tags = [t for t in htmlscan.tags(html) if not t.closing and t.attrs.get("data-path") == kit]
    assert len(tags) == 1 and tags[0].name == "p" and "data-sha" not in tags[0].attrs
    assert "its checksum is not stated here" in html

    def check_rows():
        bc("check", project=proj)
        return {x["id"]: x["status"] for x in report(proj, "check")["results"]}
    rows = check_rows()
    assert rows["report:book-lint"] == rows["report:book"] == "pass" and not [k for k in rows if k.startswith("report:") and k.endswith(":manifest")], [k for k in rows if k.startswith("report:") and k.endswith(":manifest")]
    # rebuilding the kit changes the manifest row of the kit, and only that: the book and its reports stay current
    before = (proj / "book.html").read_bytes()
    assert bc("emit", "presskit", "--no-book", "--include", "assets/tokens/tokens.css", project=proj).returncode == 0
    assert bc("emit", "presskit", "--no-book", "--include", "assets/tokens/tokens.json", project=proj).returncode == 0
    rows = check_rows()
    assert rows["report:book-lint"] == rows["report:book"] == "pass" and not [k for k in rows if k.startswith("report:") and k.endswith(":manifest")], [k for k in rows if k.startswith("report:") and k.endswith(":manifest")]
    assert (proj / "book.html").read_bytes() == before
    # a row the book does show changing does make the reports not verified
    def bump(d):
        row = next(a for a in d["artefacts"] if a["emitter"] != "presskit")
        row["bytes"] += 1
    mutate_json(proj / "assets/manifest.json", bump)
    rows = check_rows()
    assert rows["report:book:manifest"] == "skipped" and rows["report:book-lint:manifest"] == "skipped"


# ---------------------------------------------------------------- the motion proof in the book: one report per proof file

def put_motion_report(project: Path, proof: str, rows: list[tuple[str, str]], cases: tuple[str, ...] = ()) -> Path:
    """A proof file and the report `shot --motion` writes for it (assets/_checks/motion/<slug>-<hash6>.json), written by hand; `cases` are the names it records."""
    from _common import motion_report_tool, sha256_file
    f = project / proof
    f.parent.mkdir(parents=True, exist_ok=True)
    if not f.is_file():
        f.write_text('{"schema": 1, "cases": []}\n')
    out = project / "assets" / "_checks" / (motion_report_tool(proof) + ".json")
    out.parent.mkdir(parents=True, exist_ok=True)
    results = [{"id": i, "status": s, "label": "x", "detail": ""} for i, s in rows]
    out.write_text(json.dumps({"tool": motion_report_tool(proof), "version": "0", "inputs_sha": "0" * 64, "inputs": [{"path": proof, "sha256": sha256_file(f)}], "renderer": "x",
                               "results": results, "status": "pass", "proof": proof, "cases": [{"name": n, "type": "page"} for n in cases]}, indent=2) + "\n")
    return out


@setup
@resvg
def test_the_book_shows_each_proofs_motion_report_and_leaves_an_exploration_proof_out(proj):
    from _common import motion_report_tool
    put_motion_report(proj, "motion/proof.json", [("motion:demo-page:cls:normal", "pass"), ("motion:demo-page:whole-pixel", "info"), ("motion:demo-page:edges:360", "fail")], ("demo-page",))
    put_motion_report(proj, "rounds/r2/try.json", [("motion:tryout:marker", "pass")], ("tryout",))        # a try-out: not part of the brand as it stands
    r = bc("book", project=proj)
    assert r.returncode == 0, r.stdout + r.stderr
    html = (proj / "book.html").read_text()
    assert ">cls:normal<" in html and ">edges:360<" in html and "whole-pixel" not in html   # pass, fail and warn rows; info rows are not
    assert "demo-page" not in html and ">marker<" not in html and "tryout" not in html     # a row id holds the case's name: the table shows the check, under the number of the case
    tool = motion_report_tool("motion/proof.json")
    assert f'data-report="{tool}"' in html and f">{tool}<" not in html and motion_report_tool("rounds/r2/try.json") not in html      # the report table lists the report of the proof, not under its name
    assert '<h4 data-proof="motion/proof.json">Motion proof</h4>' in html and "Motion proof:" not in html                              # one report: the plain heading, the path in an attribute
    put_motion_report(proj, "motion/hero.json", [("motion:hero:control", "pass")], ("hero",))          # a second proof of the project: each gets its table, numbered by the order of the paths
    assert bc("book", project=proj).returncode == 0
    html = (proj / "book.html").read_text()
    assert '<h4 data-proof="motion/hero.json">Motion proof 1</h4>' in html and '<h4 data-proof="motion/proof.json">Motion proof 2</h4>' in html and ">control<" in html and "motion:hero" not in html
    assert "motion/proof.json</" not in html and "motion/hero.json</" not in html and ">Motion proof 1<" in html and ">Motion proof 2<" in html     # the paths are not text; the report table names the same two
    (proj / "assets/_checks/motion").rename(proj.parent / "moved-away")                      # no report at all: the table is left out, and the build says so
    r = bc("book", project=proj)
    assert r.returncode == 0 and ">cls:normal<" not in (proj / "book.html").read_text()
    assert "no motion report" in r.stdout + r.stderr
