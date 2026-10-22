"""adapters (BRAND.md, DESIGN.md) and applied-skill: generated views of the brand, opt-in at G5.

Expected colour values are the hex constants of the Acme example's token sources (tests' fixtures: paper #f9f7ee, ink #0d1b2d, teal #007d71 in light;
night #0e141d and chalk #f0eee7 in dark), written out by hand. The DESIGN.md lint runs the pinned @google/design.md when setup installed it; a stub
package stands in for it where the test is about how its answer is read."""
import json
import os
import re
import shutil
from pathlib import Path

import pytest
from helpers import FIXTURES, ROOT, bc, data_dir, mutate, mutate_json, report

pytestmark = [pytest.mark.requires_setup, pytest.mark.requires_node]
CANON = ["Overview", "Colors", "Typography", "Layout", "Elevation & Depth", "Shapes", "Components", "Do's and Don'ts"]
PINNED = json.loads((ROOT / "scripts" / "package.json").read_text())["dependencies"]["@google/design.md"]
FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)


@pytest.fixture
def pack(acme):
    shutil.copy2(FIXTURES / "FACTS.md", acme / "FACTS.md")
    for kv in ("content_languages=en", "edition=1"):
        assert bc("state", "--set", kv, project=acme).returncode == 0
    assert bc("state", "--record", "G5", "approved (test)", project=acme).returncode == 0
    return acme


def row(p: Path, rid: str, tool="check") -> dict:
    rep = json.loads((p / "assets" / "_checks" / f"{tool}.json").read_text())
    return next(r for r in rep["results"] if r["id"] == rid)


def front(text: str) -> dict:
    return dict(re.match(r"^([a-z]+):\s*(.*?)(?:\s+#.*)?$", ln).groups() for ln in FM_RE.match(text).group(1).splitlines() if re.match(r"^[a-z]+:", ln))


def colours(text: str, section="colors") -> dict:
    block = re.search(rf"^{section}:\n((?:  .*\n)+)", FM_RE.match(text).group(1) + "\n", re.M).group(1)
    return {m.group(1): m.group(2) for ln in block.splitlines() if (m := re.match(r'^  ([a-z-]+): "(#[0-9a-f]{6}(?:[0-9a-f]{2})?)"$', ln))}


def stub_data(tmp_path, answer: dict | None, version=PINNED) -> Path:
    """A data directory whose node_modules is the real one without @google/design.md, or with a stub in its place that prints `answer`."""
    real = data_dir()
    d = tmp_path / "data2"
    (d / "node_modules").mkdir(parents=True)
    for e in (real / "node_modules").iterdir():
        if e.name != "@google":
            (d / "node_modules" / e.name).symlink_to(e)
    if answer is not None:
        pk = d / "node_modules" / "@google" / "design.md"
        pk.mkdir(parents=True)
        (pk / "package.json").write_text(json.dumps({"name": "@google/design.md", "version": version, "bin": {"design.md": "cli.js"}}))
        (pk / "cli.js").write_text(f"console.log({json.dumps(json.dumps(answer))});\n")
    return d


def add_scrim(p: Path) -> None:
    """A see-through role in both modes: a scrim at 56% (#3a2448, alpha byte 0x8f = 143 / 255, the colour of the tokens' own alpha test), built into the tokens."""
    def plum(d):
        d["color"]["plum"] = {"$value": {"colorSpace": "srgb", "components": [58 / 255, 36 / 255, 72 / 255], "alpha": 0.56, "hex": "#3a2448"}}
    mutate_json(p / "tokens" / "primitives.tokens.json", plum)
    for f in ("semantic.light.tokens.json", "semantic.dark.tokens.json"):
        mutate_json(p / "tokens" / f, lambda d: d["color"].__setitem__("scrim", {"$value": "{color.plum}"}))
    r = bc("tokens", project=p)
    assert r.returncode == 0, r.stdout + r.stderr


# ---------------------------------------------------------------- opt-in

def test_the_adapters_need_g5_and_a_flag_and_write_nothing_without_them(acme):
    r = bc("adapters", "--brand-md", "--design-md", project=acme)
    assert r.returncode == 1 and "G5" in r.stderr and not (acme / "BRAND.md").exists() and not (acme / "DESIGN.md").exists()
    assert bc("state", "--record", "G5", "approved (test)", project=acme).returncode == 0
    r = bc("adapters", project=acme)
    assert r.returncode == 2 and "opt-in" in r.stderr and not (acme / "BRAND.md").exists()


def test_each_flag_writes_only_its_file(pack):
    r = bc("adapters", "--brand-md", project=pack)
    assert r.returncode == 0, r.stderr
    assert (pack / "BRAND.md").is_file() and not (pack / "DESIGN.md").exists()


# ---------------------------------------------------------------- BRAND.md

def test_brand_md_has_the_four_layers_and_the_frontmatter_of_the_architecture(pack):
    assert bc("adapters", "--brand-md", project=pack).returncode == 0
    t = (pack / "BRAND.md").read_text()
    fm = front(t)
    assert (fm["type"], fm["architecture"], fm["name"], fm["status"]) == ("master", "independent", '"Acme"', "approved")
    heads = re.findall(r"^## (.+)$", t, re.M)
    assert heads == ["Strategy", "Voice", "Visual", "Governance"]
    assert "every tool has a published spare-parts list" in t and "| light | dark |" in t and "#007d71 | #4cd7c8" in t
    assert "Accessibility commitments" in t and "16.15:1" in t       # ink on paper: (0.0102 + .05) over (.9335 + .05) by hand is 16.15
    for arch, want in (("family-member", ("master", "endorsed")), ("product-in-family", ("product", "endorsed"))):
        assert bc("state", "--set", f"architecture={arch}", project=pack).returncode == 0
        assert bc("adapters", "--brand-md", project=pack).returncode == 0
        fm = front((pack / "BRAND.md").read_text())
        assert (fm["type"], fm["architecture"]) == want
        assert "FAMILY.md" in (pack / "BRAND.md").read_text()
    assert bc("adapters", "--brand-md", "--bm-type", "product", "--bm-architecture", "branded-house", project=pack).returncode == 0
    fm = front((pack / "BRAND.md").read_text())
    assert (fm["type"], fm["architecture"]) == ("product", "branded-house")
    assert bc("adapters", "--brand-md", "--bm-type", "company", project=pack).returncode == 2


def test_a_see_through_role_is_printed_with_its_alpha_wherever_a_role_is_listed(pack):
    """tokens.json carries the alpha of every role. A role under alpha 1 is #rrggbbaa (lower case, the form tokens.css prints) in BRAND.md, DESIGN.md and
    the applied skill; an opaque role stays #rrggbb. The scrim is #3a2448 at 56%: 0.56 x 255 = 142.8, rounded to 143 = 0x8f."""
    add_scrim(pack)
    assert "--color-plum: #3a24488f;" in (pack / "assets/tokens/tokens.css").read_text()
    assert bc("adapters", "--brand-md", "--design-md", "--primary", "accent", project=pack).returncode in (0, 3)
    assert bc("applied-skill", "--yes", project=pack).returncode == 0
    brand, design = (pack / "BRAND.md").read_text(), (pack / "DESIGN.md").read_text()
    skill = (pack / ".claude" / "skills" / "acme-brand" / "SKILL.md").read_text()
    for text in (brand, skill):
        assert "| scrim | #3a24488f | #3a24488f |" in text and "| accent | #007d71 | #4cd7c8 |" in text and "| bg | #f9f7ee | #0e141d |" in text
    c = colours(design)
    assert (c["scrim"], c["scrim-dark"]) == ("#3a24488f", "#3a24488f")
    assert (c["accent"], c["bg"], c["bg-dark"], c["primary"]) == ("#007d71", "#f9f7ee", "#0e141d", "#007d71")
    for text in (brand, design, skill):
        assert not re.search(r"#3a2448(?![0-9a-f])", text), "the scrim must not appear as an opaque colour"


@pytest.mark.requires_design_lint
def test_the_pinned_design_md_format_accepts_an_eight_digit_colour(pack):
    """The format the plugin pins (@google/design.md) lists #RRGGBBAA as a colour; its own lint passes a DESIGN.md that has one."""
    spec = (data_dir() / "node_modules" / "@google" / "design.md" / "dist" / "spec.md").read_text()
    assert "`#RRGGBBAA`" in spec
    add_scrim(pack)
    r = bc("adapters", "--design-md", "--primary", "accent", project=pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "scrim: \"#3a24488f\"" in (pack / "DESIGN.md").read_text()
    assert row(pack, "design-md:lint", "adapters")["status"] == "pass"


def test_brand_md_lists_the_durations_whether_they_are_named_duration_or_motion(pack):
    tj = pack / "assets" / "tokens" / "tokens.json"
    assert bc("adapters", "--brand-md", project=pack).returncode == 0
    motion = (pack / "BRAND.md").read_text().split("### Motion", 1)[1].split("##", 1)[0]
    n = motion.count("- duration.")
    assert n == 1                                                       # Acme has one: duration.fast
    doc = json.loads(tj.read_text())
    doc["other"] = {("motion." + k.split(".", 1)[1] if k.startswith("duration.") else k): v for k, v in doc["other"].items()}
    tj.write_text(json.dumps(doc, indent=2) + "\n")
    assert bc("adapters", "--brand-md", "--replace", project=pack).returncode == 0
    motion = (pack / "BRAND.md").read_text().split("### Motion", 1)[1].split("##", 1)[0]
    assert motion.count("- motion.") == n                               # the starter tokens' names: listed as well


def test_brand_md_invents_no_voice_and_keeps_contact_facts_out(pack):
    assert bc("adapters", "--brand-md", project=pack).returncode == 0
    t = (pack / "BRAND.md").read_text()
    assert "No voice facts are recorded" in t
    for private in ("Sample Person", "+00 000 000 000", "1 Example Street"):
        assert private not in t
    with (pack / "FACTS.md").open("a") as f:
        f.write("| voice | plain and specific, never breathless | owner, intake | 2026-10-17 |\n")
    assert bc("adapters", "--brand-md", project=pack).returncode == 0
    t = (pack / "BRAND.md").read_text()
    assert "plain and specific, never breathless" in t and "No voice facts are recorded" not in t


def test_the_generated_files_are_deterministic(pack):
    assert bc("adapters", "--brand-md", "--design-md", project=pack).returncode in (0, 3)
    a, b = (pack / "BRAND.md").read_bytes(), (pack / "DESIGN.md").read_bytes()
    assert bc("adapters", "--brand-md", "--design-md", project=pack).returncode in (0, 3)
    assert (pack / "BRAND.md").read_bytes() == a and (pack / "DESIGN.md").read_bytes() == b


# ---------------------------------------------------------------- DESIGN.md

def test_design_md_carries_the_token_values_in_the_canonical_order(pack):
    assert bc("adapters", "--design-md", "--primary", "accent", project=pack).returncode in (0, 3)
    t = (pack / "DESIGN.md").read_text()
    c = colours(t)
    assert (c["bg"], c["text"], c["accent"], c["primary"]) == ("#f9f7ee", "#0d1b2d", "#007d71", "#007d71")
    assert (c["bg-dark"], c["text-dark"], c["accent-dark"]) == ("#0e141d", "#f0eee7", "#4cd7c8")
    heads = re.findall(r"^## (.+)$", t, re.M)
    assert [h for h in heads if h != "Motion"] == [h for h in CANON if h in heads] and heads[0] == "Overview" and "Colors" in heads and "Components" in heads
    assert heads.count("Motion") == 1 and heads.index("Motion") == heads.index("Components") + 1      # Acme has a duration: the one prose section the format does not name
    refs = re.findall(r'"\{colors\.([a-z-]+)\}"', t)
    assert refs and all(ref in c for ref in refs)                                  # every reference resolves to a colour the file defines
    assert "version: alpha" in t and "fontFamily" in t and "space-1: 4px" in t
    assert bc("adapters", "--design-md", "--primary", "no-such-role", project=pack).returncode == 2


@pytest.mark.requires_design_lint
def test_design_md_is_linted_by_the_pinned_package_and_passes(pack):
    r = bc("adapters", "--design-md", "--primary", "accent", project=pack)
    assert r.returncode == 0, r.stdout + r.stderr
    lint = row(pack, "design-md:lint", "adapters")
    assert lint["status"] == "pass" and f"@google/design.md {PINNED}" in lint["detail"]
    rep = json.loads((pack / "assets" / "_checks" / "adapters.json").read_text())
    assert rep["design_md_package"] == f"@google/design.md@{PINNED}" and rep["status"] == "pass"
    # without --primary the lint's own `missing-primary` finding shows as a warning, not a failure
    assert bc("adapters", "--design-md", project=pack).returncode == 0
    assert row(pack, "design-md:lint:missing-primary", "adapters")["status"] == "warn"


def test_a_design_md_that_cannot_be_linted_is_not_verified_never_a_pass(pack, tmp_path):
    d = stub_data(tmp_path, None)
    r = bc("adapters", "--design-md", project=pack, data=d)
    assert r.returncode == 3, r.stdout + r.stderr
    assert (pack / "DESIGN.md").is_file()                                           # the file is written; the check is what is missing
    lint = row(pack, "design-md:lint", "adapters")
    assert lint["status"] == "skipped" and "not verified" in lint["detail"] and "setup --yes" in lint["detail"]
    assert json.loads((pack / "assets" / "_checks" / "adapters.json").read_text())["status"] == "not-verified"
    bc("check", project=pack)
    assert row(pack, "report:adapters")["status"] == "skipped"                      # and `check` says so too


def test_the_lint_answer_is_read_errors_and_contrast_findings_fail_other_warnings_warn(pack, tmp_path):
    answer = {"findings": [
        {"severity": "error", "path": "components.x", "message": "Reference {colors.nope} does not resolve to any defined token.", "rule": "broken-ref"},
        {"severity": "warning", "path": "components.y", "message": "textColor on backgroundColor has contrast ratio 3.1:1 (fails WCAG AA).", "rule": "contrast-ratio"},
        {"severity": "warning", "path": "colors.line", "message": "'line' is never referenced.", "rule": "orphaned-tokens"},
        {"severity": "info", "message": "3 colors", "rule": "token-summary"}], "summary": {"errors": 1, "warnings": 2, "infos": 1}}
    r = bc("adapters", "--design-md", project=pack, data=stub_data(tmp_path, answer))
    assert r.returncode == 1
    assert row(pack, "design-md:lint:broken-ref", "adapters")["status"] == "fail"
    assert row(pack, "design-md:lint:contrast-ratio", "adapters")["status"] == "fail"
    assert row(pack, "design-md:lint:orphaned-tokens", "adapters")["status"] == "warn"
    assert row(pack, "design-md:lint", "adapters")["status"] == "fail"
    # a package of another version than the pin is not trusted
    r = bc("adapters", "--design-md", project=pack, data=stub_data(tmp_path / "v", {"findings": [], "summary": {}}, version="0.0.1"))
    assert r.returncode == 3 and "pins" in row(pack, "design-md:lint", "adapters")["detail"]


# ---------------------------------------------------------------- generated files are gated by check

def test_a_hand_edit_of_an_adapter_file_fails_check_and_a_rewrite_needs_replace(pack):
    assert bc("adapters", "--brand-md", "--design-md", project=pack).returncode in (0, 3)
    mutate(pack / "BRAND.md", "## Voice", "## Voice\n\nWe are the friendliest.")
    bc("check", project=pack)
    assert row(pack, "adapters:BRAND.md")["status"] == "fail" and "edited by hand" in row(pack, "adapters:BRAND.md")["detail"]
    r = bc("adapters", "--brand-md", project=pack)
    assert r.returncode == 1 and "edited by hand" in r.stderr and "friendliest" in (pack / "BRAND.md").read_text()
    r = bc("adapters", "--brand-md", "--replace", project=pack)
    assert r.returncode == 0, r.stderr
    assert "friendliest" not in (pack / "BRAND.md").read_text()
    kept = list((pack).glob("removed-*/BRAND.md"))
    assert len(kept) == 1 and "friendliest" in kept[0].read_text()                 # the hand-edited file is kept, never deleted


def test_a_changed_source_makes_the_adapters_not_verified_until_they_are_generated_again(pack):
    assert bc("adapters", "--brand-md", "--design-md", project=pack).returncode in (0, 3)
    bc("check", project=pack)
    assert row(pack, "report:adapters")["status"] in ("pass", "skipped")
    with (pack / "FACTS.md").open("a") as f:
        f.write("| voice | plain | owner | 2026-10-17 |\n")
    bc("check", project=pack)
    assert row(pack, "report:adapters")["status"] == "skipped" and "FACTS.md changed" in row(pack, "report:adapters")["detail"]
    assert bc("adapters", "--brand-md", "--design-md", project=pack).returncode in (0, 3)
    bc("check", project=pack)
    assert row(pack, "adapters:BRAND.md")["status"] == "pass"
    assert bc("state", "--set", "name=Acme Tools", project=pack).returncode == 0          # BRAND-STATE.md is not a report input: its view is hashed
    bc("check", project=pack)
    assert row(pack, "adapters:state")["status"] == "skipped" and "changed since the adapters report" in row(pack, "adapters:state")["detail"]
    assert bc("adapters", "--brand-md", "--design-md", project=pack).returncode in (0, 3)
    assert "Acme Tools" in (pack / "BRAND.md").read_text()


def test_both_files_are_in_the_staleness_record_and_the_cascade_search(pack):
    assert bc("staleness", "--write", project=pack).returncode == 0
    assert bc("adapters", "--brand-md", "--design-md", project=pack).returncode in (0, 3)
    inputs = json.loads((pack / "tools" / "inputs.json").read_text())
    assert "BRAND.md" in inputs["globs"] and "DESIGN.md" in inputs["globs"]
    r = bc("staleness", project=pack)
    assert r.returncode == 1 and "BRAND.md is new since the pack was built" in r.stdout          # the pack predates the adapters
    assert bc("staleness", "--write", project=pack).returncode == 0
    assert bc("staleness", project=pack).returncode == 0
    mutate(pack / "DESIGN.md", "version: alpha", "version: alpha\n# edited")
    r = bc("staleness", project=pack)
    assert r.returncode == 1 and "DESIGN.md changed since the pack was built" in r.stdout
    # the cascade finds an old phrase in the adapter files
    r = bc("check", "--cascade", "published spare-parts list", project=pack)
    cas = row(pack, "cascade:published spare-parts list")
    assert cas["status"] == "fail" and "BRAND.md:" in cas["detail"] and any(h.startswith("BRAND.md:") for h in cas["hits"])


# ---------------------------------------------------------------- applied skill

def test_the_applied_skill_needs_g5_and_yes_and_writes_only_into_the_project(acme):
    r = bc("applied-skill", "--yes", project=acme)
    assert r.returncode == 1 and "G5" in r.stderr and not (acme / ".claude").exists()
    assert bc("state", "--record", "G5", "approved (test)", project=acme).returncode == 0
    r = bc("applied-skill", project=acme)
    assert r.returncode == 2 and "--yes" in r.stderr and not (acme / ".claude").exists()        # prints the plan, writes nothing
    assert "would write .claude/skills/acme-brand/SKILL.md" in r.stdout
    r = bc("applied-skill", "--plan", project=acme)
    assert r.returncode == 0 and not (acme / ".claude").exists()
    r = bc("applied-skill", "--yes", project=acme)
    assert r.returncode == 0, r.stderr
    assert (acme / ".claude" / "skills" / "acme-brand" / "SKILL.md").is_file()
    assert [p.relative_to(acme).as_posix() for p in (acme / ".claude").rglob("*") if p.is_file()] == [".claude/skills/acme-brand/SKILL.md"]


def test_the_applied_skill_is_a_valid_skill_made_of_the_tokens_and_the_facts(pack):
    assert bc("applied-skill", "--yes", project=pack).returncode == 0
    t = (pack / ".claude" / "skills" / "acme-brand" / "SKILL.md").read_text()
    fm = dict(re.match(r"^([a-z-]+):\s*(.*)$", ln).groups() for ln in FM_RE.match(t).group(1).splitlines())
    assert fm["name"] == "acme-brand" and len(fm["description"]) <= 1024 and not re.match(r"(?i)(i|we|you)\b", fm["description"])
    assert set(fm) == {"name", "description"}
    for hexv in ("#f9f7ee", "#0d1b2d", "#007d71", "#0e141d", "#4cd7c8"):
        assert hexv in t
    assert "every tool has a published spare-parts list" in t and "## Never" in t and "Do not stretch" in t
    assert "{{" not in t and "Sample Person" not in t and "+00 000" not in t           # no placeholder left, no contact data
    assert "At 32 px and below the accent must hold a solid 4 x 4 px square" in t
    assert len(t.splitlines()) < 500


def test_a_slug_that_cannot_be_a_skill_name_is_refused(pack):
    bc("state", "--set", "slug=claude-tools", project=pack)
    r = bc("applied-skill", "--yes", project=pack)
    assert r.returncode == 2 and "claude" in r.stderr and not (pack / ".claude").exists()


def test_a_hand_edited_applied_skill_fails_check_and_is_replaced_only_on_request(pack):
    assert bc("applied-skill", "--yes", project=pack).returncode == 0
    f = pack / ".claude" / "skills" / "acme-brand" / "SKILL.md"
    mutate(f, "## Never", "## Never\n\n- Do anything.")
    bc("check", project=pack)
    assert row(pack, "applied-skill:file")["status"] == "fail"
    r = bc("applied-skill", "--yes", project=pack)
    assert r.returncode == 1 and "edited by hand" in r.stderr
    assert bc("applied-skill", "--yes", "--replace", project=pack).returncode == 0
    assert "Do anything" not in f.read_text()
    kept = list(pack.glob("removed-*/.claude/skills/acme-brand/SKILL.md"))
    assert len(kept) == 1 and "Do anything" in kept[0].read_text()
    bc("check", project=pack)
    assert row(pack, "applied-skill:file")["status"] == "pass"


def test_the_applied_skill_is_searched_by_the_cascade(pack):
    assert bc("applied-skill", "--yes", project=pack).returncode == 0
    bc("check", "--cascade", "#4cd7c8", project=pack)
    cas = row(pack, "cascade:#4cd7c8")
    assert cas["status"] == "fail" and any(h.startswith(".claude/skills/acme-brand/SKILL.md:") for h in cas["hits"])


def test_brand_md_mapping_agrees_with_the_architecture_reference():
    """One classification: the adapter's default BRAND.md `type` and `architecture` per mode are the last column of the modes table
    in references/architecture.md, and a family-member is a master brand there and in the intake phase."""
    import ast
    src = (ROOT / "scripts" / "adaptlib" / "adapt.py").read_text(encoding="utf-8")
    bm_map = ast.literal_eval(re.search(r"^BM_MAP = (\{.*\})$", src, re.M).group(1))
    ref = (ROOT / "skills" / "brand-creator" / "references" / "architecture.md").read_text(encoding="utf-8")
    table = {}
    for m in re.finditer(r"^\| `([a-z-]+)` \| ([^|]+) \|.*\| `([a-z-]+)` / `([a-z-]+)` \|$", ref, re.M):
        table[m.group(1)] = (m.group(3), m.group(4))
        assert m.group(3) in m.group(2), f"{m.group(1)}: BRAND.md type {m.group(3)!r} is not the type the table gives ({m.group(2).strip()})"
    assert table == bm_map, (table, bm_map)
    intake = (ROOT / "skills" / "brand-creator" / "references" / "phases" / "00-intake.md").read_text(encoding="utf-8")
    assert re.search(r"^\s*\| family-member \| master\b", intake, re.M)


# ---------------------------------------------------------------- motion: the duration and curve tokens and motion/motion.json

SPEC_FILE = "motion/motion.json"


def add_motion(p: Path, extra=None) -> None:
    """Two more durations, and an easing group with a curve, an alias of it and an overshoot (y above 1), built into the tokens of the project."""
    def groups(d):
        d["motion"] = {"$type": "duration", "base": {"$value": {"value": 320, "unit": "ms"}}, "stagger": {"$value": {"value": 120, "unit": "ms"}}}
        d["easing"] = {"$type": "cubicBezier", "standard": {"$value": [0.2, 0, 0, 1]}, "enter": {"$value": "{easing.standard}"}, "bounce": {"$value": [0.34, 1.56, 0.64, 1]}}
        if extra:
            extra(d)
    mutate_json(p / "tokens" / "primitives.tokens.json", groups)
    r = bc("tokens", project=p)
    assert r.returncode == 0, r.stdout + r.stderr


def on_spec() -> dict:
    return {"schema": 1, "motion": "on",
            "signature": {"name": " Settle ", "description": "The dot drops onto the grid\n  and settles.", "where": ["app icon", "empty\tstates"]},   # words are set on one line
            "parts": [{"id": "dot", "description": "The accent dot of the mark."}],
            "timeline": [{"part": "dot", "property": "transform", "start": "{motion.stagger} * 2", "duration": "{motion.base}", "easing": "{easing.standard}", "note": "drops two pixels"}],
            "rules": ["reduced motion:  nothing moves", "nothing loops forever"]}


def off_spec() -> dict:
    return {"schema": 1, "motion": "off", "reason": "The owner wants a still brand:\nnothing in it needs   to move.", "rules": ["the still is complete"]}


def put_spec(p: Path, doc: dict) -> None:
    (p / "motion").mkdir(exist_ok=True)
    (p / SPEC_FILE).write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def section(text: str, heading: str, until: str = "\n## ") -> str:
    """The body of a heading, up to the next heading of its level or above (the end of the file when there is none)."""
    return text.split(heading + "\n\n", 1)[1].split(until, 1)[0].strip()


def motion_of(p: Path) -> tuple[str, str, str]:
    """The Motion body of BRAND.md, DESIGN.md and the applied skill."""
    skill = (p / ".claude" / "skills" / "acme-brand" / "SKILL.md").read_text()
    return section((p / "BRAND.md").read_text(), "### Motion"), section((p / "DESIGN.md").read_text(), "## Motion"), section(skill, "## Motion")


def maybe_row(p: Path, rid: str, tool="check") -> dict | None:
    rep = json.loads((p / "assets" / "_checks" / f"{tool}.json").read_text())
    return next((r for r in rep["results"] if r["id"] == rid), None)


def generate(p: Path) -> None:
    assert bc("adapters", "--brand-md", "--design-md", "--primary", "accent", "--replace", project=p).returncode in (0, 3)
    assert bc("applied-skill", "--yes", "--replace", project=p).returncode == 0


DURATIONS = ["- duration.fast: 150ms", "- motion.base: 320ms", "- motion.stagger: 120ms"]
CURVES = ["- easing.bounce: cubic-bezier(0.34, 1.56, 0.64, 1)", "- easing.enter: cubic-bezier(0.2, 0, 0, 1)", "- easing.standard: cubic-bezier(0.2, 0, 0, 1)"]


def test_brand_md_lists_the_curves_after_the_durations_with_their_numbers_and_an_alias_as_its_curve(pack):
    add_motion(pack)
    assert bc("adapters", "--brand-md", project=pack).returncode == 0
    body = section((pack / "BRAND.md").read_text(), "### Motion")
    assert body.splitlines() == DURATIONS + CURVES                          # an alias is printed as the numbers it resolves to, not as var(--...)


def test_a_curve_in_the_motion_group_is_listed_as_a_curve_once_and_not_as_a_duration(pack):
    add_motion(pack, lambda d: d["motion"].__setitem__("ease", {"$type": "cubicBezier", "$value": [0.4, 0, 0.2, 1]}))
    assert bc("adapters", "--brand-md", project=pack).returncode == 0
    lines = section((pack / "BRAND.md").read_text(), "### Motion").splitlines()
    assert lines.count("- motion.ease: cubic-bezier(0.4, 0, 0.2, 1)") == 1 and len(lines) == 7
    assert lines[:3] == DURATIONS and lines[-1] == "- motion.ease: cubic-bezier(0.4, 0, 0.2, 1)"      # the durations first, then every curve in name order


def test_curves_numbers_are_plain_decimals_as_tokens_css_writes_them(pack):
    add_motion(pack)
    tj = pack / "assets" / "tokens" / "tokens.json"
    mutate_json(tj, lambda d: d["motion"]["curves"].__setitem__("easing.tiny", [0.0000001, 1.0, 0.5, 2.50]))      # as a JSON reader may hand them over: floats
    assert bc("adapters", "--brand-md", project=pack).returncode == 0
    assert "- easing.tiny: cubic-bezier(0.0000001, 1, 0.5, 2.5)" in (pack / "BRAND.md").read_text()


def test_each_place_the_signature_shows_in_is_a_bullet_of_its_own_even_one_with_a_comma(pack):
    add_motion(pack)
    spec = on_spec()
    spec["signature"]["where"] = ["app icon, at small sizes", "the loading screen"]
    put_spec(pack, spec)
    generate(pack)
    for text in motion_of(pack):
        assert "\nShown in:\n\n- app icon, at small sizes\n- the loading screen\n\nMotion rules:" in text, text


def test_the_motion_spec_reaches_brand_md_design_md_and_the_applied_skill_in_the_same_words(pack):
    add_motion(pack)
    mutate(pack / "BRAND-STATE.md", "- (rule) (...)", "- (rule) the accent is a fill, never text (proposal)")          # a G4 rule: DESIGN.md gets its Do's and Don'ts
    put_spec(pack, on_spec())
    generate(pack)
    brand, design, skill = motion_of(pack)
    want = "\n".join(DURATIONS + CURVES + ["", "Signature move: Settle. The dot drops onto the grid and settles.", "", "Shown in:", "", "- app icon", "- empty states", "",
                                          "Motion rules:", "", "- reduced motion: nothing moves", "- nothing loops forever"])
    assert brand == design == skill == want
    for text in ((pack / "BRAND.md").read_text(), (pack / "DESIGN.md").read_text(), (pack / ".claude" / "skills" / "acme-brand" / "SKILL.md").read_text()):
        assert "drops two pixels" not in text and "ring" not in text                # the parts and the timeline are the hand-off's, not the brand's summary
    skill_text = (pack / ".claude" / "skills" / "acme-brand" / "SKILL.md").read_text()
    assert skill_text.index("\n## Mark\n") < skill_text.index("\n## Motion\n") < skill_text.index("\n## Never\n")
    heads = re.findall(r"^## (.+)$", (pack / "DESIGN.md").read_text(), re.M)
    assert heads[-3:] == ["Components", "Motion", "Do's and Don'ts"]                    # Motion sits before the guardrails, which stay last
    fm = FM_RE.match((pack / "DESIGN.md").read_text()).group(1)
    assert not re.search(r"^(motion|easing|duration)", fm, re.M), "no key of the pinned format is invented for motion"


def test_a_motion_spec_that_says_off_says_why_nothing_moves(pack):
    put_spec(pack, off_spec())
    generate(pack)
    brand, design, skill = motion_of(pack)
    want = "\n".join(DURATIONS[:1] + ["", "Nothing moves: The owner wants a still brand: nothing in it needs to move.", "", "Motion rules:", "", "- the still is complete"])
    assert brand == design == skill == want
    assert "Signature move" not in brand + design + skill
    bare = {"schema": 1, "motion": "off", "reason": "A still brand."}                  # no rules: no rules paragraph
    put_spec(pack, bare)
    generate(pack)
    assert motion_of(pack)[0] == "- duration.fast: 150ms\n\nNothing moves: A still brand."


def test_the_applied_skill_plan_says_it_holds_motion(pack):
    r = bc("applied-skill", "--plan", project=pack)
    assert r.returncode == 0 and "motion (when the tokens or motion/motion.json have any)" in r.stdout


def test_a_spec_with_no_tokens_still_prints_what_it_says(pack):
    mutate_json(pack / "tokens" / "primitives.tokens.json", lambda d: d.pop("duration"))
    assert bc("tokens", project=pack).returncode == 0
    put_spec(pack, off_spec())
    generate(pack)
    assert motion_of(pack)[0].startswith("Nothing moves: The owner wants a still brand")
    assert "### Motion\n\nNothing moves: The owner" in (pack / "BRAND.md").read_text()          # no tokens line, and no blank line in front of the first paragraph
    assert "## Motion\n\nNothing moves: The owner" in (pack / "DESIGN.md").read_text()


def test_without_motion_the_files_are_as_they_were_and_with_durations_they_gain_the_motion_block_and_nothing_else(pack, tmp_path):
    """Acme has one duration. The same project with no duration at all has no Motion anywhere; adding the duration adds exactly the Motion lines."""
    bare = tmp_path / "bare"
    shutil.copytree(pack, bare)
    mutate_json(bare / "tokens" / "primitives.tokens.json", lambda d: d.pop("duration"))
    assert bc("tokens", project=bare).returncode == 0
    generate(pack)
    generate(bare)
    names = {"BRAND.md": "### Motion\n\n- duration.fast: 150ms\n\n", ".claude/skills/acme-brand/SKILL.md": "## Motion\n\n- duration.fast: 150ms\n\n",
             "DESIGN.md": "\n## Motion\n\n- duration.fast: 150ms\n"}      # the last section of a DESIGN.md with no rules: the blank line before it goes with it
    for name, block in names.items():
        with_duration, without = (pack / name).read_text(), (bare / name).read_text()
        assert "Motion" not in without and "{{" not in without, name
        assert block in with_duration and with_duration.count(block) == 1, name
        assert with_duration.replace(block, "") == without, f"{name}: the duration adds its Motion lines and changes nothing else"


def test_a_motion_spec_that_is_not_valid_stops_the_adapters_and_the_applied_skill(pack):
    add_motion(pack)
    doc = on_spec()
    doc["timeline"][0]["easing"] = "{easing.nope}"
    put_spec(pack, doc)
    r = bc("adapters", "--brand-md", "--design-md", project=pack)
    assert r.returncode == 2 and "timeline[0].easing: no token named easing.nope" in r.stderr, r.stdout + r.stderr
    assert not (pack / "BRAND.md").exists() and not (pack / "DESIGN.md").exists()
    assert row(pack, "error", "adapters")["status"] == "fail"
    r = bc("applied-skill", "--yes", project=pack)
    assert r.returncode == 2 and "timeline[0].easing: no token named easing.nope" in r.stderr
    assert not (pack / ".claude").exists()


def test_the_motion_spec_is_a_source_of_the_adapters_and_the_skill(pack):
    """A change to motion/motion.json, its removal, or its first appearance makes the reports not verified until the files are generated again."""
    add_motion(pack)
    put_spec(pack, on_spec())
    generate(pack)
    bc("check", project=pack)
    assert row(pack, "report:adapters")["status"] == "pass" and row(pack, "report:applied-skill")["status"] == "pass"
    assert maybe_row(pack, "adapters:state") is None                              # the row only exists when the sources moved on
    changed = on_spec()
    changed["rules"].append("one more rule")
    put_spec(pack, changed)
    bc("check", project=pack)
    for tool in ("adapters", "applied-skill"):
        r = row(pack, f"report:{tool}")
        assert r["status"] == "skipped" and "motion/motion.json changed" in r["detail"], tool
    for rid in ("adapters:state", "applied-skill:state"):                         # the state hash notices it as well, and says which source it was
        assert row(pack, rid)["status"] == "skipped" and "motion spec" in row(pack, rid)["detail"], rid
    generate(pack)
    bc("check", project=pack)
    assert row(pack, "report:adapters")["status"] == "pass" and row(pack, "adapters:BRAND.md")["status"] == "pass"
    assert "one more rule" in (pack / "BRAND.md").read_text()
    # a spec added after the files were made is not among the report's inputs: the state hash is what notices it
    (pack / SPEC_FILE).rename(pack / "motion" / "motion.json.moved")
    generate(pack)
    bc("check", project=pack)
    assert maybe_row(pack, "adapters:state") is None
    (pack / "motion" / "motion.json.moved").rename(pack / SPEC_FILE)
    bc("check", project=pack)
    assert row(pack, "adapters:state")["status"] == "skipped" and "motion spec" in row(pack, "adapters:state")["detail"]
    assert row(pack, "applied-skill:state")["status"] == "skipped" and "motion spec" in row(pack, "applied-skill:state")["detail"]
    generate(pack)
    bc("check", project=pack)
    assert maybe_row(pack, "adapters:state") is None and maybe_row(pack, "applied-skill:state") is None


@pytest.mark.requires_design_lint
def test_the_pinned_design_md_format_keeps_the_motion_section_and_its_lint_passes(pack):
    add_motion(pack)
    put_spec(pack, on_spec())
    r = bc("adapters", "--design-md", "--primary", "accent", project=pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert row(pack, "design-md:lint", "adapters")["status"] == "pass"
    assert "0 error(s)" in row(pack, "design-md:lint", "adapters")["detail"]
    assert "## Motion" in (pack / "DESIGN.md").read_text()
    spec = (data_dir() / "node_modules" / "@google" / "design.md" / "dist" / "spec.md").read_text()
    assert "Unknown section heading | Preserve; do not error" in spec               # the clause that keeps a prose section the format does not name


def test_the_applied_skill_template_keeps_its_placeholder_guard_and_takes_the_motion_block_wherever_it_is_placed(pack, plugin_copy):
    add_motion(pack)
    put_spec(pack, on_spec())
    tpl = plugin_copy / "templates" / "applied-skill" / "SKILL.md"
    original = tpl.read_text()
    # an unknown placeholder is refused, and nothing is written
    tpl.write_text(original.replace("## Never", "{{nope}}\n\n## Never"))
    r = bc("applied-skill", "--yes", project=pack, plugin=plugin_copy)
    assert r.returncode == 2 and "placeholders this version does not know: {{nope}}" in r.stderr
    assert not (pack / ".claude").exists()
    # {{motion}} that is not followed by a blank line is filled too (the block with its heading, where the template put it), not refused as unknown
    tpl.write_text(original.replace("{{motion}}\n\n", "Motion, if any: {{motion}}!\n\n"))
    r = bc("applied-skill", "--yes", project=pack, plugin=plugin_copy)
    assert r.returncode == 0, r.stderr
    assert re.search(r"Motion, if any: ## Motion\n\n- duration\.fast: 150ms\n[\s\S]*- nothing loops forever!\n", (pack / ".claude" / "skills" / "acme-brand" / "SKILL.md").read_text())
    # a template with no {{motion}} at all writes no motion, as every placeholder a template leaves out writes nothing
    tpl.write_text(original.replace("{{motion}}\n\n", ""))
    assert bc("applied-skill", "--yes", "--replace", project=pack, plugin=plugin_copy).returncode == 0
    assert "Motion" not in (pack / ".claude" / "skills" / "acme-brand" / "SKILL.md").read_text()


def test_a_duration_is_found_by_its_type_and_a_motion_group_token_that_is_no_duration_is_still_listed(pack):
    """tokens.json `motion` says which tokens are durations, so one outside the duration and motion groups is listed; a motion-group token of another type
    (a distance) is listed as tokens.css writes it, as before; a tokens.json built before the motion entry existed still lists its durations by group."""
    def more(d):
        d["timing"] = {"$type": "duration", "slow": {"$value": {"value": 640, "unit": "ms"}}}
        d["motion"]["distance"] = {"$type": "dimension", "$value": {"value": 8, "unit": "px"}}
    add_motion(pack, more)
    assert bc("adapters", "--brand-md", project=pack).returncode == 0
    lines = section((pack / "BRAND.md").read_text(), "### Motion").splitlines()
    assert lines == ["- duration.fast: 150ms", "- motion.base: 320ms", "- motion.distance: 8px", "- motion.stagger: 120ms", "- timing.slow: 640ms"] + CURVES
    mutate_json(pack / "assets" / "tokens" / "tokens.json", lambda d: d.pop("motion"))       # an earlier build: no motion entry, no curves known
    assert bc("adapters", "--brand-md", "--replace", project=pack).returncode == 0
    assert section((pack / "BRAND.md").read_text(), "### Motion").splitlines() == ["- duration.fast: 150ms", "- motion.base: 320ms", "- motion.distance: 8px",
                                                                                   "- motion.stagger: 120ms"]


def test_text_with_braces_in_the_motion_spec_or_the_rules_is_written_as_it_is_and_never_read_as_a_placeholder(pack):
    add_motion(pack)
    mutate(pack / "BRAND-STATE.md", "- (rule) (...)", "- (rule) say {{name}} in full, see {{facts}} (proposal)")   # placeholders filled before and after the text
    doc = on_spec()
    doc["rules"] = ["the dot moves like {{name}} says", "no {{wobble}} ever", "check {{facts}} first"]
    put_spec(pack, doc)
    generate(pack)
    brand, design, skill = motion_of(pack)
    assert brand == design == skill and "- the dot moves like {{name}} says\n- no {{wobble}} ever\n- check {{facts}} first" in skill
    text = (pack / ".claude" / "skills" / "acme-brand" / "SKILL.md").read_text()
    assert "- (rule) say {{name}} in full, see {{facts}} (proposal)" in text and "acme-brand" not in text.split("## Rules", 1)[1].split("\n## ", 1)[0]
