"""Stage 2b prose and templates: research phase, brand-naming skill, strategy core, regulated industries.

Expected strings are written out by hand (independent oracle); the FORBIDDEN check calls the real parser on a filled
copy of the template, never on the template's own output.
"""
import re
import shutil

from helpers import ROOT
from _common import forbidden_terms
from test_skills import ORCH, REFS, RULE, SKILLS, frontmatter, rules_line

TPL = ROOT / "templates"
NAMING = SKILLS / "brand-naming" / "SKILL.md"
CLAIM_WORDS = re.compile(r"\b(available|free|clear)\b", re.I)


def section(text, heading):
    """Body of a markdown section (up to the next heading of the same or higher level)."""
    m = re.search(rf"^(#+) {re.escape(heading)}\s*$", text, re.M)
    assert m, heading
    rest = text[m.end():]
    nxt = re.search(rf"^#{{1,{len(m.group(1))}}} ", rest, re.M)
    return rest[: nxt.start()] if nxt else rest


def test_brand_naming_frontmatter_is_narrow_and_bilingual():
    fm, body = frontmatter(NAMING)
    assert "disable-model-invocation" not in fm, "brand-naming must be model-invocable"
    assert fm["allowed-tools"] == RULE
    desc = fm["description"]
    assert desc.startswith("Finds a name") and "screening, not clearance" in desc
    assert "not for logos" in desc and "go / go-with-conditions / no" in desc
    for trig in ("wymyśl nazwę", "czy nazwa jest wolna", "is the name X taken"):
        assert trig in fm["when_to_use"], trig
    assert not CLAIM_WORDS.search(desc), "the description must not promise availability"


def test_brand_naming_steps_run_in_the_required_order():
    _, body = frontmatter(NAMING)
    order = ["## Step 1: ask up front", "**Name language**", "**Profile**", "## Step 3: metaphor territories",
             "**Territories first.**", "**Then 40 to 80 candidates**", "## Step 4: distinctiveness class",
             "## Step 5: internal filter", "## Step 6: meaning and sound", "## Step 7: privacy OK",
             "## Step 8: prior-art kill", "## Step 9: screening with brand-creator names", "## Step 10: trademark links",
             "## Step 11: verdict memo", "## Step 12: G1"]
    pos = [body.index(s) for s in order]
    assert pos == sorted(pos), "steps out of order"
    # the privacy question comes before any lookup, and --yes only appears after it
    assert body.index("--plan") > body.index("## Step 7: privacy OK")
    assert body.index("--yes") > body.index("## Step 8: prior-art kill")
    for style in ("invented", "native-language", "descriptive", "metaphor", "compound", "foreign"):
        assert f"| {style} |" in section(body, "Step 3: metaphor territories, then candidates by style"), style
    classes = section(body, "Step 4: distinctiveness class")
    for cls in ("fanciful", "arbitrary", "suggestive", "descriptive", "generic"):
        assert f"| {cls} |" in classes, cls
    assert re.search(r"\| descriptive \|[^\n]*\*\*weak\*\*", classes)
    lang = section(body, "Step 6: meaning and sound in each language")
    assert "English and every audience language" in lang
    assert "gh search repos <name> --sort stars" in section(body, "Step 8: prior-art kill")
    assert 'brand-creator --data "${CLAUDE_PLUGIN_DATA}" names' in body
    assert "templates/names-verdict.md" in body and "Launch TODO" in body
    assert "--record G1" in body


def test_brand_naming_repeats_the_rules_line_verbatim():
    assert rules_line(NAMING.read_text(encoding="utf-8")) == rules_line(ORCH.read_text(encoding="utf-8"))


def test_naming_texts_never_claim_a_name_is_available():
    """Each use of available/free/clear in naming prose must sit in a line that forbids it."""
    files = [NAMING, TPL / "names-verdict.md", REFS / "phases" / "02-naming.md"]
    for f in files:
        for n, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if CLAIM_WORDS.search(line):
                assert re.search(r"\b(never|not)\b(?!-)", line, re.I), f"{f.relative_to(ROOT)}:{n}: {line.strip()}"


def test_names_verdict_template_carries_the_memo_slots():
    t = (TPL / "names-verdict.md").read_text(encoding="utf-8")
    assert t.splitlines()[2].startswith("> **Screening, not clearance.**")
    for slot in ("## Naming brief", "## Territories and styles used", "## Finalists", "## Verdicts", "## Killed, with reasons",
                 "## UNKNOWN and not verified", "## My call", "## Launch TODO (seed for LAUNCH.md)"):
        assert slot in t, slot
    assert "go / go-with-conditions / no" in t and "descriptive (says what it is: **weak**" in t
    todo = section(t, "Launch TODO (seed for LAUNCH.md)")
    assert todo.index("Trademark") < todo.index("Domains"), "trademark comes first in the Launch TODO"
    assert "recheck before buying" in todo and todo.count("- [ ]") >= 5


def test_research_template_slots():
    t = (TPL / "research.md").read_text(encoding="utf-8")
    for slot in ("## Constraints (P1a)", "## Competitive alternatives (status quo first)",
                 "## Competitor lineup (5, reused for distinctiveness checks)", "## Positioning map", "## Only you can confirm",
                 "## Open decisions", "## Sources"):
        assert slot in t, slot
    assert "primary / secondary / UNVERIFIED" in t and "re-fetch result" in t
    assert section(t, "Competitive alternatives (status quo first)").strip().splitlines()[-2].startswith("1. Status quo")


def test_cliches_template_feeds_the_forbidden_list(tmp_path):
    src = TPL / "cliches.md"
    t = src.read_text(encoding="utf-8")
    assert "## Map axes" in t and "## Avoid unless argued" in t
    proj = tmp_path / "p"
    (proj / "research").mkdir(parents=True)
    shutil.copy(src, proj / "research" / "cliches.md")
    assert forbidden_terms(proj) == [], "the empty template must add no FORBIDDEN terms (placeholders leaked)"
    with open(proj / "research" / "cliches.md", "a", encoding="utf-8") as fh:
        fh.write("- trusted partner\n- solutions for every need\n")
    assert forbidden_terms(proj) == ["trusted partner", "solutions for every need"]


def test_inventory_template_slots():
    t = (TPL / "INVENTORY.md").read_text(encoding="utf-8")
    header = next(ln for ln in t.splitlines() if ln.startswith("| ID |"))
    for col in ("ID", "path", "platform rule", "citation (URL, checked, V/R/U)", "resampled by", "state"):
        assert f"| {col} |" in header, col
    for word in ("SYS", "OURS", "PAGE", "EXISTS", "MISSING", "STALE", "inventory: none (no target repo)"):
        assert word in t, word
    assert "## Surprises and conflicts" in t and "## Considered and rejected" in t


def test_research_phase_points_at_its_templates_and_the_lint():
    t = (REFS / "phases" / "01-research.md").read_text(encoding="utf-8")
    for needle in ("templates/research.md", "templates/cliches.md", "templates/INVENTORY.md", "research/research.md",
                   "research/YYYY-MM-DD-<topic>.md", "status quo first", "five-competitor lineup", "before round 1",
                   "project:inventory", "Only you can confirm", "dembrandt"):
        assert needle in t, needle
    for name in ("research.md", "cliches.md", "INVENTORY.md", "names-verdict.md"):
        assert (TPL / name).is_file(), name


def test_strategy_core_fields_match_the_round_page_and_carry_a_guardrails_block():
    core = (REFS / "strategy-core.md").read_text(encoding="utf-8")
    rows = re.findall(r"^\| ([1-7]) \| ([^|]+) \|", section(core, "The fields"), re.M)
    assert [r[0] for r in rows] == list("1234567")
    assert "Drafted by you from research and the brief" in core and "Never collected by interview" in core
    block = section(core, "Guardrails block")
    for line in ("Regulatory:", "Claims:", "Category:", "Family:"):
        assert re.search(rf"^{line}", block, re.M), line
    for page in (TPL / "round-page.html", REFS / "examples" / "acme" / "rounds" / "r1" / "board.html"):
        html = page.read_text(encoding="utf-8")
        sec = re.search(r'data-section="strategy-core".*?</section>', html, re.S).group(0)
        labels = re.findall(r"<dt>([^<]+)</dt>", sec)
        assert labels == ["Category and alternatives", "One target", "Positioning", "Only we", "Proof points",
                          "Not this / This", "Guardrails"], (page, labels)


def test_regulated_industries_method_and_table():
    t = (REFS / "regulated-industries.md").read_text(encoding="utf-8")
    steps = re.findall(r"^([1-7])\. \*\*", section(t, "The method (7 steps)"), re.M)
    assert steps == list("1234567")
    header = next(ln for ln in section(t, "The rules table").splitlines() if ln.startswith("| rule"))
    for col in ("article", "code version or resolution", "primary source (URL)", "date checked", "status"):
        assert col in header, col
    rows = [ln for ln in section(t, "Examples (UNVERIFIED)").splitlines() if ln.startswith("| ") and not ln.startswith("| rule")]
    assert len(rows) >= 3
    for r in rows:
        assert "UNVERIFIED" in r and re.search(r"\| 20\d\d-\d\d-\d\d \|", r), r
    assert "Guardrails block" in t and "does not decide what the law allows" in t
