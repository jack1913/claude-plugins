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
    mutate(proj / "book.html", "<h1>Acme</h1>", "<h1>Acme Corp</h1>")
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
    mutate(proj / "book.html", "</style>", "a{transition:color 900ms}</style>")
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
    mutate(proj / "book.html", "</style>", "a{transition:color 150ms}</style>")
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
    assert "RGB, not print-ready" in " ".join(first.split()) and "Acme" in first
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
