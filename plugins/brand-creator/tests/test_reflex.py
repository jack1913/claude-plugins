"""The reflex line parser and its helpers (scripts/boardlib/reflex.py): the format of a direction's reflex line, the names it may hit, the grounding words and
the judge's list. Pure functions over text, so these tests need no project, no browser and no setup."""
import sys
import unicodedata

import pytest
from helpers import ROOT

sys.path.insert(0, str(ROOT / "scripts" / "boardlib"))
import reflex  # noqa: E402

COMPASS = "Reflex test: no hits. near miss: device-product-silhouette (it is not a tool outline)"
LANTERN = "hit: type-geometric-rounded-friendly | the rounded face appears only in the wordmark, to echo a lamp for small workshops"
KEYSTONE = "no hits. Near miss: palette-navy-gold-trust (cobalt is not navy and there is no gold)"


def test_the_three_acme_lines_parse():
    compass, lantern, keystone = (reflex.parse(t) for t in (COMPASS, LANTERN, KEYSTONE))
    for p in (compass, lantern, keystone):
        assert p.problems == []
    assert compass.no_hits and not lantern.no_hits and keystone.no_hits
    assert compass.entries == [reflex.Entry("near-miss", "device-product-silhouette", "it is not a tool outline")]
    assert lantern.entries == [reflex.Entry("hit", "type-geometric-rounded-friendly", "the rounded face appears only in the wordmark, to echo a lamp for small workshops")]
    assert keystone.entries == [reflex.Entry("near-miss", "palette-navy-gold-trust", "cobalt is not navy and there is no gold")]
    ids = reflex.ai_default_ids()
    for e in (*compass.entries, *lantern.entries, *keystone.entries):
        assert reflex.known(e.name, ids, []) == "ai-defaults"


def test_the_ids_are_those_of_the_ai_defaults_file():
    ids = reflex.ai_default_ids()
    assert len(ids) == len(set(ids)) and "type-geometric-rounded-friendly" in ids
    assert {"palette-pale-ground-timid-accent", "type-first-answer-display-face", "device-texture-as-identity", "layout-stock-product-page"} <= set(ids)


@pytest.mark.parametrize("text", [
    "Reflex test: one hit, type-geometric-rounded-friendly. Argued: the rounded face appears only in the wordmark.",
    "none of the patterns",
    "",
])
def test_legacy_free_text_gives_a_problem(text):
    p = reflex.parse(text)
    assert not p.no_hits and p.entries == [] and len(p.problems) == 1
    assert ("free text" if text else "empty") in p.problems[0] and "hit: <id> | <argument>" in p.problems[0]


def test_no_hits_followed_by_any_text_is_still_no_hits():
    for text in ("no hits", "No hits.", "Reflex test: no hits, and the board holds none of the stock patterns"):
        p = reflex.parse(text)
        assert p.no_hits and p.entries == [] and p.problems == [], text
    assert not reflex.parse("no hitsy").no_hits   # a word that only starts like it


@pytest.mark.parametrize("text, what", [
    ("hit: x", "has no '|'"),
    ("hit: x |", "empty argument"),
    ("hit: x |   ", "empty argument"),
    ("hit: | because", "no id"),
    ("hit:", "has no '|'"),
])
def test_a_hit_without_an_id_a_bar_or_an_argument_gives_a_problem(text, what):
    p = reflex.parse(text)
    assert len(p.problems) == 1 and what in p.problems[0]
    assert len(reflex.hits(p)) == 1   # a malformed hit is still a hit: it counts, and its problem is reported


def test_no_hits_together_with_a_hit_gives_a_problem():
    p = reflex.parse("no hits. hit: palette-neon-on-black | neon is the shop's sign")
    assert p.no_hits and len(reflex.hits(p)) == 1
    assert len(p.problems) == 1 and "'no hits' together with a hit" in p.problems[0]


def test_text_before_the_first_marker_must_be_empty_or_no_hits():
    p = reflex.parse("two patterns. hit: a | b")
    assert not p.no_hits and any("before the first marker" in x for x in p.problems)
    assert reflex.parse("hit: a | b").problems == []
    assert reflex.parse("No hits (we looked). near miss: a (b)").problems == []


def test_a_near_miss_is_not_in_hits():
    p = reflex.parse("near miss: palette-neon-on-black (the glow is a tray icon) near-miss: type-serif-display-sans-body (no serif) hit: layout-bento-grid | the grid shows tool sizes")
    assert [e.kind for e in p.entries] == ["near-miss", "near-miss", "hit"]
    assert [e.name for e in reflex.hits(p)] == ["layout-bento-grid"]
    assert p.problems == []
    dotted = reflex.parse("No hits. Near miss: device-product-silhouette (it is not a tool outline). Near miss: chef hat.")
    assert [(e.name, e.argument) for e in dotted.entries] == [("device-product-silhouette", "it is not a tool outline"), ("chef hat", "")] and dotted.problems == []
    only = reflex.parse("no hits. near miss: palette-neon-on-black")
    assert reflex.hits(only) == [] and only.entries == [reflex.Entry("near-miss", "palette-neon-on-black", "")] and only.problems == []


def test_markers_are_any_case_and_not_taken_from_inside_a_word_or_a_hyphenated_one():
    p = reflex.parse("REFLEX TEST:   HIT: a | one\n\tHit: b | two NEAR   MISS: c (three)")
    assert [(e.kind, e.name) for e in p.entries] == [("hit", "a"), ("hit", "b"), ("near-miss", "c")] and p.problems == []
    for text in ("white-hit: a | b", "tophit: a | b", "no hits. wholehit: a | b"):
        assert reflex.hits(reflex.parse(text)) == [], text
    # a letter with a diacritic is a letter too
    assert reflex.hits(reflex.parse("żhit: a | b")) == []


def test_the_argument_keeps_a_second_bar_and_the_first_bar_splits():
    e = reflex.parse("hit: a | b | c").entries[0]
    assert (e.name, e.argument) == ("a", "b | c")


def test_norm_drops_one_trailing_parenthetical_and_folds_case_and_space():
    assert reflex.norm("  Wheat-Adjacent   SHAPE (an ear, a sheaf (or two))  ") == "wheat-adjacent shape"
    assert reflex.norm("a (b) (c)") == "a (b)"
    assert reflex.norm("(...)") == "(...)"
    assert reflex.norm("Straße") == reflex.norm("STRASSE")


def test_known_matches_a_cliche_bullet_with_a_trailing_parenthetical():
    cliches = ["wheat-adjacent shape (an ear, a sheaf, chevrons that read as grain)", "chef hat"]
    ids = reflex.ai_default_ids()
    assert reflex.known("wheat-adjacent shape", ids, cliches) == "cliches"
    assert reflex.known("Wheat-adjacent shape (an ear ...)", ids, cliches) == "cliches"
    assert reflex.known("chef hat (as a mark)", ids, cliches) == "cliches"
    assert reflex.known("layout-bento-grid", ids, cliches) == "ai-defaults"
    assert reflex.known("wheat-sheaf", ids, cliches) is None
    assert reflex.known("", ids, cliches) is None and reflex.known("(...)", ids, ["(...)"]) == "cliches"


def test_content_words_keep_polish_letters_and_drop_short_words_digits_and_underscores():
    assert {"łódź", "żółć"} <= reflex.content_words("Łódź i ŻÓŁĆ, a 2026 r. oraz ptak")
    assert reflex.content_words("Łódź żółć") == {"łódź", "żółć"}
    assert reflex.content_words("the tool_box 12345 x-ray ox ab1cd") == {"tool"}
    assert reflex.content_words("") == set()
    # a letter typed as base letter plus accent (decomposed) is not split into short pieces
    decomposed = unicodedata.normalize("NFD", "łódź żółć")
    assert decomposed != "łódź żółć" and reflex.content_words(decomposed) == {"łódź", "żółć"}


def test_ground_words_drop_template_boilerplate_and_keep_a_project_fact(tmp_path):
    facts = (ROOT / "templates" / "FACTS.md").read_text(encoding="utf-8").replace("{{name}}", "Marlow")
    facts = facts.replace("| (example) every product ships with a repair guide | yes | owner, chat on YYYY-MM-DD | YYYY-MM-DD |",
                          "| bake | sourdough is baked in the shop every morning | owner, intake | 2026-10-17 |")
    facts += "| repair | a repair guide ships with every product | owner, intake | 2026-10-17 |\n"   # words of the template's example row are fine in a project row
    facts += "\nDesigners may use sourdough facts here.\n"   # a line of the owner's own that reuses boilerplate words
    (tmp_path / "FACTS.md").write_text(facts, encoding="utf-8")
    (tmp_path / "brief").mkdir()
    brief = (ROOT / "templates" / "BRIEF.md").read_text(encoding="utf-8").replace("{{name}}", "Marlow")
    brief = brief.replace("- Offer: (what is sold or shown, in one sentence)", "- Offer: sourdough loaves and rye bread, sold over the counter")
    (tmp_path / "brief" / "BRIEF.md").write_text(brief, encoding="utf-8")
    words = reflex.ground_words(tmp_path)
    assert {"sourdough", "morning", "loaves", "bread", "counter", "repair", "guide", "ships"} <= words
    assert "marlow" not in words   # the name in the title line is no word of the owner's own
    # template lines left verbatim add nothing; the words of the templates' prose are taken out of the lines that reuse them
    for w in ("copywriters", "claims", "emitters", "designers", "facts", "offer", "audience", "constraints"):
        assert w not in words, w
    # nothing else came from the templates' table rows
    assert "confirmed" not in words and "source" not in words


def test_the_templates_copied_unchanged_add_no_word_not_even_the_name(tmp_path):
    (tmp_path / "brief").mkdir()
    for rel, name in (("FACTS.md", "FACTS.md"), ("brief/BRIEF.md", "BRIEF.md")):
        text = (ROOT / "templates" / name).read_text(encoding="utf-8").replace("{{name}}", "Marlow Loaves")   # what `brand-creator new` writes
        (tmp_path / rel).write_text(text, encoding="utf-8")
    assert reflex.ground_words(tmp_path) == set()
    # only a whole title line is a template line: the same words in a longer line are the owner's own
    (tmp_path / "FACTS.md").write_text("# Marlow Loaves: facts, and sourdough\n", encoding="utf-8")
    assert reflex.ground_words(tmp_path) == {"marlow", "loaves", "sourdough"}


def test_ground_words_of_an_empty_project_are_empty_and_a_polish_fact_is_a_ground_word(tmp_path):
    assert reflex.ground_words(tmp_path) == set()
    (tmp_path / "FACTS.md").write_text("| fact | value | source | confirmed |\n|---|---|---|---|\n| siedziba | warsztat w Łodzi, kolor żółć | właściciel | 2026-10-17 |\n", encoding="utf-8")
    assert {"siedziba", "warsztat", "łodzi", "żółć"} <= reflex.ground_words(tmp_path)


CLICHES = """# Acme: category clichés

## Category

(The category as buyers name it.)

## Avoid unless argued

Visual clichés. A direction may still use one, but its card must argue why.

- wheat-adjacent shape (an ear, a sheaf, chevrons that read as grain)
- (...)
* chef hat <!-- inline note -->
- hand-lettered script
<!-- a multi-line
- comment bullet -->
- wheat-adjacent shape (an ear, a sheaf, chevrons that read as grain)

## Forbidden

- artisan
"""


def test_cliche_items_reads_the_avoid_section_of_the_named_file(tmp_path):
    (tmp_path / "research").mkdir()
    (tmp_path / "research" / "site-cliches.md").write_text(CLICHES, encoding="utf-8")
    items = reflex.cliche_items(tmp_path, rel="research/site-cliches.md")
    assert items == ["wheat-adjacent shape (an ear, a sheaf, chevrons that read as grain)", "chef hat", "hand-lettered script"]
    # the default file is research/cliches.md, and a file that is not there gives an empty list
    assert reflex.cliche_items(tmp_path) == []
    (tmp_path / "research" / "cliches.md").write_text(CLICHES.replace("chef hat", "script wordmark"), encoding="utf-8")
    assert "script wordmark" in reflex.cliche_items(tmp_path) and "chef hat" not in reflex.cliche_items(tmp_path)
    assert reflex.cliche_items(tmp_path, rel="research/other.md") == []


def test_the_cliche_template_gives_no_items(tmp_path):
    (tmp_path / "research").mkdir()
    (tmp_path / "research" / "cliches.md").write_text((ROOT / "templates" / "cliches.md").read_text(encoding="utf-8"), encoding="utf-8")
    assert reflex.cliche_items(tmp_path) == []


@pytest.mark.parametrize("texts, expected", [
    (["none seen"], []),
    (["None seen."], []),
    (["judge saw: none seen"], []),
    (["Judge saw: device-lightbulb-idea; palette-neon-on-black."], ["device-lightbulb-idea", "palette-neon-on-black"]),
    (["seen: chef hat ;  wheat-adjacent shape (an ear)"], ["chef hat", "wheat-adjacent shape (an ear)"]),
    (["layout-bento-grid"], ["layout-bento-grid"]),
    (["  device-lightbulb-idea \n"], ["device-lightbulb-idea"]),
    (["device-lightbulb-idea", "chef hat; with a semicolon", "  "], ["device-lightbulb-idea", "chef hat; with a semicolon"]),
    (["none seen", "layout-bento-grid"], ["layout-bento-grid"]),
    ([""], []),
    ([], []),
])
def test_the_judge_list_comes_from_li_items_or_one_text(texts, expected):
    assert reflex.parse_seen(texts) == expected


@pytest.mark.parametrize("texts, said", [
    (["none seen"], True),
    (["None seen."], True),
    (["judge saw: none seen"], True),
    (["seen: NONE SEEN;"], True),
    (["none seen", "layout-bento-grid"], True),
    (["judge saw:"], False),   # only the label is no answer
    (["seen:  ;"], False),
    ([""], False),
    ([], False),
    (["device-lightbulb-idea; palette-neon-on-black"], False),
    (["not seen yet"], False),
])
def test_only_none_seen_in_so_many_words_is_the_answer_none_seen(texts, said):
    assert reflex.says_none_seen(texts) is said


def test_the_module_is_outside_scripts_lib_and_standard_library_only():
    path = ROOT / "scripts" / "boardlib" / "reflex.py"
    assert path.is_file() and not (ROOT / "scripts" / "lib" / "reflex.py").exists()
    imported = {ln.split()[1].split(".")[0] for ln in path.read_text(encoding="utf-8").splitlines() if ln.startswith(("import ", "from ")) and "__future__" not in ln}
    assert imported and imported <= sys.stdlib_module_names, imported - sys.stdlib_module_names


def rows_of(text, cliches=(), **kw):
    return {suffix: (status, detail) for suffix, status, detail in reflex.line_rows(reflex.parse(text), reflex.ai_default_ids(), list(cliches), **kw)}


def test_line_rows_pass_a_clean_line_and_name_where_each_hit_came_from():
    got = rows_of(LANTERN)
    assert [k for k in got] == ["reflex-format", "reflex-ids", "reflex-count"] and {v[0] for v in got.values()} == {"pass"}
    assert "type-geometric-rounded-friendly (ai-defaults)" in got["reflex-ids"][1]
    assert rows_of("hit: Wheat-adjacent shape | a sheaf", ["wheat-adjacent shape (an ear)"])["reflex-ids"][1].endswith("(cliches)")
    assert rows_of("no hits")["reflex-format"] == ("pass", "no hits") and rows_of("no hits")["reflex-count"][0] == "pass"
    assert set(reflex.LABELS) == {"reflex-format", "reflex-ids", "reflex-count", "reflex-grounded"}
    assert "reflex-grounded" not in got   # no row without a grounding set


def test_line_rows_warn_for_the_format_and_the_ids_and_say_it_is_a_failure_from_the_next_release():
    free = rows_of("one hit, type-geometric-rounded-friendly")
    assert free["reflex-format"][0] == "warn" and "free text" in free["reflex-format"][1] and free["reflex-format"][1].endswith(reflex.NEXT_RELEASE)
    assert reflex.NEXT_RELEASE == "a failure from the next release"
    other = rows_of("two things. hit: a-thing | b")   # text before the marker: the problem does not carry the format, so the row adds it
    assert "'hit: <id> | <argument>' per hit" in other["reflex-format"][1]
    ids = rows_of("hit: wheat-sheaf | a sheaf in the logo", sources="ai-defaults.json (the project has no research/cliches.md)")
    assert ids["reflex-ids"][0] == "warn" and "'wheat-sheaf'" in ids["reflex-ids"][1] and "the project has no research/cliches.md" in ids["reflex-ids"][1]
    assert ids["reflex-ids"][1].endswith(reflex.NEXT_RELEASE) and ids["reflex-count"][0] == "pass"
    nameless = rows_of("hit: | because")   # the missing id is the format row's business
    assert nameless["reflex-format"][0] == "warn" and nameless["reflex-ids"][0] == "pass"


def test_line_rows_fail_two_hits_and_never_count_a_near_miss():
    two = rows_of("hit: palette-neon-on-black | a neon sign. hit: layout-bento-grid | the grid shows tool sizes")
    assert two["reflex-count"][0] == "fail" and "2 hits" in two["reflex-count"][1] and "replace a part before showing it" in two["reflex-count"][1]
    assert two["reflex-format"][0] == "pass" and two["reflex-ids"][0] == "pass"
    one = rows_of("hit: palette-neon-on-black | a neon sign. near miss: layout-bento-grid (the grid is a list)")
    assert one["reflex-count"] == ("pass", "1 hit(s)")
    assert rows_of("hit: a | b. hit: c | d")["reflex-count"][0] == "fail"   # unknown ids still count


def test_line_rows_ground_each_argument_in_the_owners_words():
    ground = {"sourdough", "morning", "saturdays"}
    ok = rows_of("hit: palette-neon-on-black | the sign is lit every Morning, like the sourdough", ground=ground)
    assert list(ok) == ["reflex-format", "reflex-ids", "reflex-count", "reflex-grounded"]
    assert ok["reflex-grounded"] == ("pass", "palette-neon-on-black shares morning, sourdough")   # the shared words, sorted
    bad = rows_of("hit: palette-neon-on-black | a neon sign, because neon is bright", ground=ground)
    status, detail = bad["reflex-grounded"]
    assert status == "warn" and "'palette-neon-on-black'" in detail and "shares no word with FACTS.md or brief/BRIEF.md" in detail
    assert "name the fact, place or craft" in detail and detail.endswith(reflex.NEXT_RELEASE)
    mixed = rows_of("hit: a | the sign is lit every morning. hit: b | a neon sign", ground=ground)   # only the ungrounded hit is named
    assert mixed["reflex-grounded"][0] == "warn" and "'b'" in mixed["reflex-grounded"][1] and "'a'" not in mixed["reflex-grounded"][1]


def test_line_rows_say_not_verified_when_there_is_nothing_to_ground_in_and_skip_a_line_without_an_argued_hit():
    none = rows_of(LANTERN, ground=set())
    status, detail = none["reflex-grounded"]
    assert status == "warn" and detail.startswith("NOT verified") and "checked against nothing" in detail and detail.endswith(reflex.NEXT_RELEASE)
    for text in ("no hits", "no hits. near miss: palette-navy-gold-trust (cobalt is not navy)", "hit: palette-neon-on-black", "hit: palette-neon-on-black |"):
        assert "reflex-grounded" not in rows_of(text, ground={"bread"}), text   # no hit, or a hit with no argument (the format row's business)
        assert "reflex-grounded" not in rows_of(text, ground=set()), text
    assert "reflex-grounded" not in rows_of(LANTERN, ground=None)


def test_line_rows_ground_with_diacritics_and_ignore_words_under_four_letters():
    ground = reflex.content_words("Piekarnia wypieka żytni chleb na zakwasie, łódź i żółć")
    assert rows_of("hit: palette-neon-on-black | neon nad Łódź", ground=ground)["reflex-grounded"] == ("pass", "palette-neon-on-black shares łódź")
    assert rows_of("hit: palette-neon-on-black | neon i żółw, na", ground=ground)["reflex-grounded"][0] == "warn"   # "na" and "i" are under four letters


def test_shared_hit_is_the_name_every_line_hits_and_needs_two_lines():
    p = reflex.parse
    a, b, c = p("hit: Type-Geometric (rounded) | x. hit: other | y"), p("hit: type-geometric | z"), p("no hits. near miss: type-geometric (not here)")
    assert reflex.shared_hit([a, b]) == "type-geometric"
    assert reflex.shared_hit([a, b, c]) is None   # a near miss is no hit
    assert reflex.shared_hit([a]) is None and reflex.shared_hit([]) is None
    assert reflex.shared_hit([p("hit: one | x. hit: two | y"), p("hit: two | z. hit: one | w")]) == "one"   # several shared: the first of the first line
    assert reflex.shared_hit([p("hit: a | x"), p("hit: b | y")]) is None
