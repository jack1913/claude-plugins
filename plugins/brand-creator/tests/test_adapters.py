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
from helpers import FIXTURES, ROOT, bc, data_dir, mutate

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
    return {m.group(1): m.group(2) for ln in block.splitlines() if (m := re.match(r'^  ([a-z-]+): "(#[0-9a-f]{6})"$', ln))}


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
    assert heads == [h for h in CANON if h in heads] and heads[0] == "Overview" and "Colors" in heads and "Components" in heads
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
