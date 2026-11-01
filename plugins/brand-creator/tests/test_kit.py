"""The brand kit around the applied skill (scripts/adaptlib/kitlib.py, scripts/kit.py) and the applied skill's kit mode.

Expected values are written out by hand from the Acme example (assets/logo/mark.svg is the large drawing, assets/logo/grid-mark.svg the small one;
tokens at assets/tokens/tokens.json), never read from the module under test."""
import shutil

import pytest
from helpers import FIXTURES, ROOT, bc

pytestmark = [pytest.mark.requires_setup, pytest.mark.requires_node]

TEMPLATE = ROOT / "templates" / "applied-skill" / "SKILL.md"


@pytest.fixture
def pack(acme):
    shutil.copy2(FIXTURES / "FACTS.md", acme / "FACTS.md")
    for kv in ("content_languages=en", "edition=1"):
        assert bc("state", "--set", kv, project=acme).returncode == 0
    assert bc("state", "--record", "G5", "approved (test)", project=acme).returncode == 0
    return acme


# ---------------------------------------------------------------- the applied skill builder: kit mode

def test_without_a_kit_the_applied_skill_keeps_its_paths_and_has_no_kit_section(pack):
    r = bc("applied-skill", "--yes", project=pack)
    assert r.returncode == 0, r.stderr
    text = (pack / ".claude" / "skills" / "acme-brand" / "SKILL.md").read_text(encoding="utf-8")
    assert "`../../../assets/tokens/tokens.json`" in text
    assert "- `../../../assets/logo/mark.svg`" in text
    assert "uses `assets/logo/grid-mark.svg`" in text                      # a band line keeps the drawing's project path
    assert "## The kit" not in text and "{{" not in text
    assert "rule.\n\n## Colour" in text                                    # the dropped {{kit}} line leaves one blank line, not two


def test_in_kit_mode_every_path_points_inside_the_kit(pack):
    import adapt
    section = "## The kit\n\nx"
    text = adapt.applied_skill_md(pack, TEMPLATE.read_text(encoding="utf-8"), kit={"prefix": "brand/", "section": section})
    assert "../../../" not in text
    assert "- `brand/assets/logo/mark.svg`" in text
    assert "`brand/assets/tokens/tokens.json`" in text
    assert "uses `brand/assets/logo/grid-mark.svg`" in text and "uses `brand/assets/logo/mark.svg`" in text    # the band lines too
    assert "{{" not in text
    assert 0 < text.index("## The kit") < text.index("## Colour")
    assert "rule.\n\n## The kit\n\nx\n\n## Colour" in text                 # between the "Use this whenever" paragraph and the colour section


def test_kit_mode_changes_only_the_paths_and_the_kit_section(pack):
    """The same builder writes both: with the kit's paths put back and the section taken out, the text is the one without a kit."""
    import adapt
    template = TEMPLATE.read_text(encoding="utf-8")
    plain = adapt.applied_skill_md(pack, template)
    in_kit = adapt.applied_skill_md(pack, template, kit={"prefix": "brand/", "section": "## The kit\n\nx"})
    back = in_kit.replace("## The kit\n\nx\n\n", "").replace("`brand/assets/tokens/", "`../../../assets/tokens/").replace("- `brand/", "- `../../../")
    back = back.replace("uses `brand/", "uses `")
    assert back == plain


def test_a_kit_mode_template_that_has_no_kit_line_still_gets_the_kit_paths(pack):
    """A template with no {{kit}} writes no kit section (as every placeholder a template leaves out writes nothing), and the paths still point into the kit."""
    import adapt
    template = TEMPLATE.read_text(encoding="utf-8").replace("{{kit}}\n\n", "")
    text = adapt.applied_skill_md(pack, template, kit={"prefix": "brand/", "section": "## The kit\n\nx"})
    assert "## The kit" not in text and "`brand/assets/tokens/tokens.json`" in text and "../../../" not in text


def test_kit_mode_writes_braces_in_the_kit_section_as_they_are(pack):
    import adapt
    section = "## The kit\n\nsee {{facts}} and {{tokens}} and {{kit}}"
    text = adapt.applied_skill_md(pack, TEMPLATE.read_text(encoding="utf-8"), kit={"prefix": "brand/", "section": section})
    assert "see {{facts}} and {{tokens}} and {{kit}}" in text


# ---------------------------------------------------------------- kit build: the generated core
# The Acme project has eight logo files (assets/logo/*.svg and *.png), tokens built to assets/tokens/tokens.css and tokens.json, and a qa/rules.json whose
# bands name grid-mark.svg and mark.svg. The kit folder of a build holds these fourteen files, written out by hand (BRAND_CREATOR_TODAY is 2026-10-17).
import filecmp  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402

from helpers import mutate, mutate_json, report  # noqa: E402

KIT_LOGOS = ["grid-mark-dark.svg", "grid-mark-master.png", "grid-mark.svg", "mark-animated.svg", "mark-dark.svg", "mark.svg", "wordmark-dark.svg", "wordmark.svg"]
KIT_FILES = sorted(["SKILL.md", "kit.json", "rules.json", "facts.json", "brand/assets/tokens/tokens.css", "brand/assets/tokens/tokens.json", *[f"brand/assets/logo/{n}" for n in KIT_LOGOS]])
KIT_REMOVED = "removed-2026-10-17/.claude/skills/acme-brand"


def kit_of(p):
    return p / ".claude" / "skills" / "acme-brand"


def kit_files(p) -> list[str]:
    d = kit_of(p)
    return sorted(f.relative_to(d).as_posix() for f in d.rglob("*") if f.is_file()) if d.is_dir() else []


def file_sha(f) -> str:
    return hashlib.sha256(f.read_bytes()).hexdigest()


def build(p, *args):
    return bc("kit", "build", "--yes", *args, project=p)


def written_row(p) -> dict:
    return next(r for r in report(p, "kit")["results"] if r["id"] == "kit:written")


def kit_state(p) -> dict:
    """The bytes and the modification time of every file of the kit folder."""
    return {rel: (file_sha(kit_of(p) / rel), (kit_of(p) / rel).stat().st_mtime_ns) for rel in kit_files(p)}


def test_the_kit_needs_g5_and_yes_and_writes_nothing_without_them(acme):
    assert bc("state", "--set", "approved_edition=1", project=acme).returncode == 0       # an approved edition, so that the edition check cannot stand in for the gate
    r = bc("kit", "build", "--yes", project=acme)
    assert r.returncode == 1 and "The brand kit needs gate G5 recorded" in r.stderr and not (acme / ".claude").exists()
    assert bc("state", "--record", "G5", "approved (test)", project=acme).returncode == 0
    r = bc("kit", "build", project=acme)
    assert r.returncode == 2 and "--yes" in r.stderr and not (acme / ".claude").exists() and not (acme / "assets" / "_checks" / "kit.json").exists()
    assert "would write 14 generated files into .claude/skills/acme-brand/ (version 1.1)" in r.stdout          # the plan goes to stdout, the message to stderr
    r = bc("kit", "build", "--plan", project=acme)
    assert r.returncode == 0 and not (acme / ".claude").exists() and not (acme / "assets" / "_checks" / "kit.json").exists()
    lines = r.stdout.splitlines()
    assert lines[0] == "would write 14 generated files into .claude/skills/acme-brand/ (version 1.1)"
    assert sorted(re.fullmatch(r"generated (\S+) \((\d+) bytes\)", ln).group(1) for ln in lines[1:]) == KIT_FILES
    assert f"generated brand/assets/tokens/tokens.css ({(acme / 'assets/tokens/tokens.css').stat().st_size} bytes)" in lines
    r = bc("kit", "build", "--yes", project=acme)
    assert r.returncode == 0, r.stderr
    assert kit_files(acme) == KIT_FILES


def test_the_kit_core_is_the_applied_skill_with_paths_inside_the_kit(pack):
    r = build(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert kit_files(pack) == KIT_FILES
    skill = (kit_of(pack) / "SKILL.md").read_text(encoding="utf-8")
    paths = re.findall(r"`(brand/[^`]+)`", skill)
    assert {"brand/assets/tokens/tokens.json", "brand/assets/logo/mark.svg", "brand/assets/logo/grid-mark.svg"} <= set(paths)
    for path in paths:
        assert (kit_of(pack) / path).exists(), path
    for name in ("tokens.css", "tokens.json"):
        assert filecmp.cmp(pack / "assets" / "tokens" / name, kit_of(pack) / "brand" / "assets" / "tokens" / name, shallow=False)
    for name in KIT_LOGOS:
        assert filecmp.cmp(pack / "assets" / "logo" / name, kit_of(pack) / "brand" / "assets" / "logo" / name, shallow=False)
    for hexv in ("#f9f7ee", "#0d1b2d", "#007d71", "#0e141d", "#4cd7c8"):
        assert hexv in skill
    assert skill.count("Kit version 1.1 (kit.json).") == 1 and "../../../" not in skill and "{{" not in skill
    assert 0 < skill.index("## The kit") < skill.index("## Colour")
    assert "change the brand project and run `brand-creator kit build --yes` again" in skill
    kj = json.loads((kit_of(pack) / "kit.json").read_text(encoding="utf-8"))
    assert (kj["schema"], kj["kit"], kj["version"], kj["edition"]) == (1, "acme-brand", "1.1", "1")
    assert kj["plugin_version"] == json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())["version"]
    assert sorted(kj["generated"]) == [f for f in KIT_FILES if f != "kit.json"]
    assert all(file_sha(kit_of(pack) / rel) == sha for rel, sha in kj["generated"].items())
    assert re.fullmatch(r"[0-9a-f]{64}", kj["content_sha"])
    rep = report(pack, "kit")
    assert rep["status"] == "pass" and rep["renderer"] == "n/a (generated files)" and rep["outputs"]
    assert rep["kit_version"] == "1.1" and rep["version"] == kj["plugin_version"]          # the report's own `version` stays the plugin's
    assert sorted(rep["outputs"]) == KIT_FILES and all(file_sha(kit_of(pack) / rel) == sha for rel, sha in rep["outputs"].items())
    assert rep["adapter_state_sha"] and rep["kit_sources_sha"]
    assert written_row(pack)["detail"] == "14 generated files: 14 written, 0 unchanged, 0 moved to removed-2026-10-17/; version 1.1"
    assert {i["path"] for i in rep["inputs"]} == {"assets/tokens/tokens.css", "assets/tokens/tokens.json", "qa/rules.json", "FACTS.md",
                                                  *[f"assets/logo/{n}" for n in KIT_LOGOS]}


def test_a_second_build_with_nothing_changed_is_byte_identical_and_keeps_the_version(pack):
    assert build(pack).returncode == 0
    first = kit_state(pack)
    r = build(pack)
    assert r.returncode == 0, r.stderr
    assert kit_state(pack) == first                                   # the same bytes, and no file was written again
    assert written_row(pack)["detail"] == "14 generated files: 0 written, 14 unchanged, 0 moved to removed-2026-10-17/; version 1.1"
    assert json.loads((kit_of(pack) / "kit.json").read_text(encoding="utf-8"))["version"] == "1.1"
    assert not list(pack.glob("removed-*"))


def test_a_changed_token_rebuilds_the_copy_and_adds_one_to_the_build_number(pack):
    assert build(pack).returncode == 0
    before = (kit_of(pack) / "brand/assets/tokens/tokens.css").read_bytes()
    def plum(d):                                                      # a new colour role in both modes, built into the tokens: tokens.css and tokens.json change
        d["color"]["plum"] = {"$value": {"colorSpace": "srgb", "components": [58 / 255, 36 / 255, 72 / 255], "alpha": 1, "hex": "#3a2448"}}
    mutate_json(pack / "tokens" / "primitives.tokens.json", plum)
    for name in ("semantic.light.tokens.json", "semantic.dark.tokens.json"):
        mutate_json(pack / "tokens" / name, lambda d: d["color"].__setitem__("scrim", {"$value": "{color.plum}"}))
    r = bc("tokens", project=pack)
    assert r.returncode == 0, r.stdout + r.stderr
    r = build(pack)
    assert r.returncode == 0, r.stderr
    assert (kit_of(pack) / "brand/assets/tokens/tokens.css").read_bytes() != before
    assert filecmp.cmp(pack / "assets/tokens/tokens.css", kit_of(pack) / "brand/assets/tokens/tokens.css", shallow=False)
    assert filecmp.cmp(pack / "assets/tokens/tokens.json", kit_of(pack) / "brand/assets/tokens/tokens.json", shallow=False)
    assert json.loads((kit_of(pack) / "kit.json").read_text(encoding="utf-8"))["version"] == "1.2"
    assert "Kit version 1.2 (kit.json)." in (kit_of(pack) / "SKILL.md").read_text(encoding="utf-8")
    assert written_row(pack)["detail"].endswith("version 1.2") and report(pack, "kit")["kit_version"] == "1.2"
    assert not list(pack.glob("removed-*"))                           # a change in the project is no hand edit: nothing is moved aside


def test_a_hand_edited_kit_file_stops_the_build_and_replace_moves_it_aside(pack):
    assert build(pack).returncode == 0
    f = kit_of(pack) / "brand/assets/tokens/tokens.css"
    mutate(f, "#f9f7ee", "#f9f7ef")
    before = kit_state(pack)
    r = build(pack)
    assert r.returncode == 1 and "brand/assets/tokens/tokens.css" in r.stderr and "edited by hand" in r.stderr and "--replace" in r.stderr
    assert kit_state(pack) == before and not list(pack.glob("removed-*"))        # nothing written, nothing moved
    r = build(pack, "--replace")
    assert r.returncode == 0, r.stderr
    assert filecmp.cmp(pack / "assets/tokens/tokens.css", f, shallow=False) and "#f9f7ef" not in f.read_text(encoding="utf-8")
    kept = pack / KIT_REMOVED / "brand/assets/tokens/tokens.css"
    assert kept.is_file() and "#f9f7ef" in kept.read_text(encoding="utf-8")
    assert list(pack.glob("removed-*/**/*")) and [p.relative_to(pack).as_posix() for p in pack.glob("removed-*/**/*") if p.is_file()] == [kept.relative_to(pack).as_posix()]
    assert written_row(pack)["detail"] == "14 generated files: 1 written, 13 unchanged, 1 moved to removed-2026-10-17/; version 1.1"
    assert build(pack).returncode == 0                                # and the next build is quiet again


def test_a_hand_edited_kit_json_stops_the_build_too(pack):
    assert build(pack).returncode == 0
    mutate(kit_of(pack) / "kit.json", '"version": "1.1"', '"version": "9.9"')
    r = build(pack)
    assert r.returncode == 1 and "kit.json (edited by hand)" in r.stderr and '"version": "9.9"' in (kit_of(pack) / "kit.json").read_text(encoding="utf-8")
    assert build(pack, "--replace").returncode == 0
    assert json.loads((kit_of(pack) / "kit.json").read_text(encoding="utf-8"))["version"] == "1.1"      # the record of the build, not the edit, decides the version
    assert '"version": "9.9"' in (pack / KIT_REMOVED / "kit.json").read_text(encoding="utf-8")


def test_a_file_put_into_a_generated_folder_stops_the_build(pack):
    assert build(pack).returncode == 0
    for rel in ("brand/assets/notes.md", "snippets/mine.css", "reference-pages/start/extra.md"):
        (kit_of(pack) / rel).parent.mkdir(parents=True, exist_ok=True)
        (kit_of(pack) / rel).write_text("mine\n", encoding="utf-8")
    (kit_of(pack) / "my-notes.md").write_text("not in a generated folder\n", encoding="utf-8")
    r = build(pack)
    assert r.returncode == 1 and "brand/assets/notes.md" in r.stderr and "snippets/mine.css" in r.stderr and "reference-pages/start/extra.md" in r.stderr
    assert "--replace" in r.stderr and (kit_of(pack) / "brand/assets/notes.md").is_file() and not list(pack.glob("removed-*"))
    assert "my-notes.md" not in r.stderr                              # a file outside the generated folders is the owner's: it never stops a build
    r = build(pack, "--replace")
    assert r.returncode == 0, r.stderr
    for rel in ("brand/assets/notes.md", "snippets/mine.css", "reference-pages/start/extra.md"):
        assert not (kit_of(pack) / rel).exists() and (pack / KIT_REMOVED / rel).read_text(encoding="utf-8") == "mine\n"
    assert (kit_of(pack) / "my-notes.md").is_file() and not (kit_of(pack) / "reference-pages").exists() and not (kit_of(pack) / "snippets").exists()   # emptied folders go
    assert written_row(pack)["detail"] == "14 generated files: 0 written, 14 unchanged, 3 moved to removed-2026-10-17/; version 1.1"


def test_a_logo_taken_out_of_the_project_moves_its_kit_copy_to_removed(pack):
    assert build(pack).returncode == 0
    gone = kit_of(pack) / "brand/assets/logo/wordmark-dark.svg"
    bytes_before = gone.read_bytes()
    (pack / "assets" / "logo" / "wordmark-dark.svg").unlink()
    r = build(pack)
    assert r.returncode == 0, r.stderr
    assert "wordmark-dark.svg" in r.stdout and "removed-2026-10-17" in r.stdout          # said, not done quietly
    assert not gone.exists() and (pack / KIT_REMOVED / "brand/assets/logo/wordmark-dark.svg").read_bytes() == bytes_before
    assert kit_files(pack) == [f for f in KIT_FILES if f != "brand/assets/logo/wordmark-dark.svg"]
    assert written_row(pack)["detail"].startswith("13 generated files: ") and "1 moved to removed-2026-10-17/" in written_row(pack)["detail"]
    assert json.loads((kit_of(pack) / "kit.json").read_text(encoding="utf-8"))["version"] == "1.2"


def test_a_new_edition_starts_the_build_number_again(pack):
    assert build(pack).returncode == 0
    assert bc("state", "--set", "name=Acme Tools", project=pack).returncode == 0
    assert build(pack).returncode == 0
    assert json.loads((kit_of(pack) / "kit.json").read_text(encoding="utf-8"))["version"] == "1.2"
    assert bc("state", "--set", "edition=2", project=pack).returncode == 0
    assert bc("state", "--record", "G5", "approved edition 2 (test)", project=pack).returncode == 0     # the kit's edition is the approved one
    r = build(pack)
    assert r.returncode == 0, r.stderr
    kj = json.loads((kit_of(pack) / "kit.json").read_text(encoding="utf-8"))
    assert (kj["edition"], kj["version"]) == ("2", "2.1")
    assert "Kit version 2.1 (kit.json)." in (kit_of(pack) / "SKILL.md").read_text(encoding="utf-8")


def test_the_kit_takes_over_a_skill_file_that_applied_skill_wrote(pack):
    assert bc("applied-skill", "--yes", project=pack).returncode == 0
    assert "## The kit" not in (kit_of(pack) / "SKILL.md").read_text(encoding="utf-8")
    r = build(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    skill = (kit_of(pack) / "SKILL.md").read_text(encoding="utf-8")
    assert "## The kit" in skill and "`brand/assets/tokens/tokens.json`" in skill and "../../../" not in skill
    assert kit_files(pack) == KIT_FILES and not list(pack.glob("removed-*"))        # the earlier skill file was generated, not edited: nothing is moved aside


def test_a_hand_edited_applied_skill_stops_the_first_kit_build(pack):
    assert bc("applied-skill", "--yes", project=pack).returncode == 0
    f = kit_of(pack) / "SKILL.md"
    mutate(f, "## Never", "## Never\n\n- Do anything.")
    r = build(pack)
    assert r.returncode == 1 and "SKILL.md" in r.stderr and "edited by hand" in r.stderr
    assert kit_files(pack) == ["SKILL.md"] and "Do anything" in f.read_text(encoding="utf-8")
    assert not (pack / "assets" / "_checks" / "kit.json").exists()
    r = build(pack, "--replace")
    assert r.returncode == 0, r.stderr
    assert "Do anything" not in f.read_text(encoding="utf-8") and "## The kit" in f.read_text(encoding="utf-8")
    assert "Do anything" in (pack / KIT_REMOVED / "SKILL.md").read_text(encoding="utf-8")


def test_a_build_needs_an_approved_edition(acme):
    assert bc("state", "--record", "G5", "approved (test)", project=acme).returncode == 0
    mutate(acme / "BRAND-STATE.md", "approved_edition: 1", 'approved_edition: ""')
    r = build(acme)
    assert r.returncode == 1 and "G5 is recorded but no edition is approved" in r.stderr and not (acme / ".claude").exists()


def test_a_kit_with_unbuilt_tokens_cannot_be_written(pack):
    (pack / "assets" / "tokens" / "tokens.css").unlink()
    r = build(pack)
    assert r.returncode == 3 and "tokens.css" in r.stderr and "brand-creator tokens" in r.stderr and not (pack / ".claude").exists()
    assert bc("tokens", project=pack).returncode == 0
    (pack / "assets" / "tokens" / "tokens.json").unlink()
    r = build(pack)
    assert r.returncode == 3 and "tokens.json" in r.stderr and "brand-creator tokens" in r.stderr and not (pack / ".claude").exists()


# ---------------------------------------------------------------- fonts: OFL copied with the licence, the others listed
# TEST_FONT is an Inter subset (OFL by its name table; family Inter, weight 400, style normal, read by hand); tests/fixtures/fonts/OFL.txt is the Inter OFL text.
from helpers import TEST_FONT  # noqa: E402

OFL_TEXT = ROOT / "tests" / "fixtures" / "fonts" / "OFL.txt"
FONT_KIT = ["brand/assets/fonts/OFL.txt", "brand/assets/fonts/TestFont-subset.ttf", "snippets/fonts.css"]
NO_FONTCHECK = "no current fontcheck report: run `brand-creator fontcheck`, then `kit build`"
NOT_OFL = "licence: Apache License; only OFL fonts are copied (a default you may change): copy it into a product yourself, under its own licence"
FONT_FACE = ('/* generated by brand-creator from assets/fonts/ and the fontcheck report; paths are relative to this file */\n'
             '\n'
             '@font-face {\n'
             '  font-family: "Inter";\n'
             '  src: url("../brand/assets/fonts/TestFont-subset.ttf") format("truetype");\n'
             '  font-weight: 400;\n'
             '  font-style: normal;\n'
             '}\n')


def with_font(p, *, fontcheck=True, licence=True):
    d = p / "assets" / "fonts"
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy2(TEST_FONT, d / TEST_FONT.name)
    if licence:
        shutil.copy2(OFL_TEXT, d / "OFL.txt")
    if fontcheck:
        r = bc("fontcheck", "--lang", "en", "--no-platform", project=p)
        assert r.returncode == 0, r.stdout + r.stderr


def fonts_row(p) -> dict:
    return next(r for r in report(p, "kit")["results"] if r["id"] == "kit:fonts")


def kit_json(p) -> dict:
    return json.loads((kit_of(p) / "kit.json").read_text(encoding="utf-8"))


def test_an_ofl_font_is_copied_with_its_licence_and_gets_a_font_face(pack):
    with_font(pack)
    r = bc("kit", "build", "--plan", project=pack)
    assert r.returncode == 0 and r.stdout.splitlines()[0] == "would write 17 generated files into .claude/skills/acme-brand/ (version 1.1)", r.stdout + r.stderr
    r = build(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert kit_files(pack) == sorted([*KIT_FILES, *FONT_KIT])
    assert (kit_of(pack) / "snippets" / "fonts.css").read_text(encoding="utf-8") == FONT_FACE
    for name in (TEST_FONT.name, "OFL.txt"):
        assert filecmp.cmp(pack / "assets" / "fonts" / name, kit_of(pack) / "brand" / "assets" / "fonts" / name, shallow=False)
    assert kit_json(pack)["fonts"] == {"copied": [{"file": "brand/assets/fonts/TestFont-subset.ttf", "licence": "SIL Open Font License (OFL)",
                                                   "licence_files": ["brand/assets/fonts/OFL.txt"]}], "not_copied": []}
    assert all(file_sha(kit_of(pack) / rel) == sha for rel, sha in kit_json(pack)["generated"].items()) and set(FONT_KIT) <= set(kit_json(pack)["generated"])
    skill = (kit_of(pack) / "SKILL.md").read_text(encoding="utf-8")
    assert all(f"- `{rel}`" in skill for rel in FONT_KIT)
    row = fonts_row(pack)
    assert row["status"] == "pass" and row["detail"] == "1 font copied with its licence text; snippets/fonts.css written"
    rep = report(pack, "kit")
    assert rep["status"] == "pass" and sorted(rep["outputs"]) == sorted([*KIT_FILES, *FONT_KIT])
    assert {"assets/fonts/TestFont-subset.ttf", "assets/fonts/OFL.txt", "assets/_checks/fontcheck.json"} <= {i["path"] for i in rep["inputs"]}
    assert kit_json(pack)["sources"]["fonts"] and kit_json(pack)["sources"]["fonts"] != kit_json(pack)["sources"]["logos"]
    first = kit_state(pack)
    assert build(pack).returncode == 0 and kit_state(pack) == first               # a second build writes nothing
    assert kit_json(pack)["version"] == "1.1"


def test_a_font_whose_licence_is_not_ofl_is_listed_and_not_copied(pack):
    with_font(pack)
    mutate_json(pack / "assets" / "_checks" / "fontcheck.json",
                lambda d: next(r for r in d["results"] if r["id"] == "licence:assets/fonts/TestFont-subset.ttf").__setitem__("recognised", "Apache License"))
    r = build(pack)
    assert r.returncode == 0, r.stdout + r.stderr                                  # a warning, not a failure
    assert kit_files(pack) == KIT_FILES                                            # no font, no licence text, no fonts.css
    assert kit_json(pack)["fonts"] == {"copied": [], "not_copied": [{"file": "assets/fonts/TestFont-subset.ttf", "reason": NOT_OFL}]}
    row = fonts_row(pack)
    assert row["status"] == "warn" and "assets/fonts/TestFont-subset.ttf" in row["detail"] and NOT_OFL in row["detail"]
    assert report(pack, "kit")["status"] == "pass" and written_row(pack)["status"] == "pass"


def test_without_a_current_fontcheck_report_no_font_is_copied_and_the_kit_is_not_verified(pack):
    with_font(pack, fontcheck=False)
    r = build(pack)
    assert r.returncode == 3, r.stdout + r.stderr
    assert kit_files(pack) == KIT_FILES                                            # the rest is written; no font, no licence text, no fonts.css
    assert kit_json(pack)["fonts"] == {"copied": [], "not_copied": [{"file": "assets/fonts/TestFont-subset.ttf", "reason": NO_FONTCHECK}]}
    rep = report(pack, "kit")
    assert rep["status"] == "not-verified" and written_row(pack)["status"] == "pass"
    assert fonts_row(pack)["status"] == "skipped" and NO_FONTCHECK in fonts_row(pack)["detail"] and fonts_row(pack)["detail"].startswith("not verified: ")
    # a report made before the font changed is no report either
    r = bc("fontcheck", "--lang", "en", "--no-platform", project=pack)
    assert r.returncode == 0, r.stdout + r.stderr
    with (pack / "assets" / "fonts" / TEST_FONT.name).open("ab") as fh:
        fh.write(b"\0")
    r = build(pack)
    assert r.returncode == 3 and kit_files(pack) == KIT_FILES and fonts_row(pack)["status"] == "skipped"
    # and with a current one the font comes in, and the version goes up
    r = bc("fontcheck", "--lang", "en", "--no-platform", project=pack)
    assert r.returncode == 0, r.stdout + r.stderr
    r = build(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert kit_files(pack) == sorted([*KIT_FILES, *FONT_KIT]) and kit_json(pack)["version"] == "1.2"
    assert (kit_of(pack) / "snippets" / "fonts.css").read_text(encoding="utf-8") == FONT_FACE


def test_an_ofl_font_without_its_licence_text_is_not_copied(pack):
    with_font(pack)
    ofl = pack / "assets" / "fonts" / "OFL.txt"
    mutate(ofl, "SIL Open Font License", "Some Licence", count=99)                  # the text names its licence in two spellings
    mutate(ofl, "SIL OPEN FONT LICENSE", "SOME LICENCE", count=99)
    r = build(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert kit_files(pack) == KIT_FILES
    assert kit_json(pack)["fonts"] == {"copied": [], "not_copied": [{"file": "assets/fonts/TestFont-subset.ttf",
                                       "reason": "OFL by its name table, but no OFL licence text in assets/fonts/: add the font's OFL.txt"}]}
    assert fonts_row(pack)["status"] == "warn"
    shutil.copy2(OFL_TEXT, ofl)                                                    # the text comes back: the font is copied, with the text
    r = build(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert kit_files(pack) == sorted([*KIT_FILES, *FONT_KIT]) and fonts_row(pack)["status"] == "pass"


def test_a_font_the_report_cannot_describe_is_listed_and_not_copied(pack):
    with_font(pack)
    path = pack / "assets" / "_checks" / "fontcheck.json"
    row = "licence:assets/fonts/TestFont-subset.ttf"
    mutate_json(path, lambda d: next(r for r in d["results"] if r["id"] == row).pop("family"))      # a report from before fontcheck named the family
    r = build(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert kit_files(pack) == KIT_FILES
    assert kit_json(pack)["fonts"]["not_copied"] == [{"file": "assets/fonts/TestFont-subset.ttf",
                                                      "reason": "the fontcheck report has no family name: run `brand-creator fontcheck` again"}]
    mutate_json(path, lambda d: next(r for r in d["results"] if r["id"] == row).__setitem__("recognised", None))   # the name table says nothing about a licence
    assert build(pack).returncode == 0
    assert kit_json(pack)["fonts"]["not_copied"] == [{"file": "assets/fonts/TestFont-subset.ttf", "reason": "the fontcheck report reads no licence for it"}]
    mutate_json(path, lambda d: d["results"].remove(next(r for r in d["results"] if r["id"] == row)))          # the report never looked at this file
    assert build(pack).returncode == 0
    assert kit_json(pack)["fonts"]["not_copied"] == [{"file": "assets/fonts/TestFont-subset.ttf", "reason": "the fontcheck report reads no licence for it"}]


def test_a_band_drawing_that_is_missing_or_outside_the_project_stops_the_build(pack, tmp_path):
    (pack / "assets" / "logo" / "mark.svg").unlink()
    r = build(pack)
    assert r.returncode == 1 and "names the band drawing assets/logo/mark.svg" in r.stderr and "Traceback" not in r.stderr and not (pack / ".claude").exists()
    shutil.copy2(FIXTURES / "assets" / "logo" / "mark.svg", pack / "assets" / "logo" / "mark.svg")
    (tmp_path / "outside.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>", encoding="utf-8")
    rules = {"schema": 1, "bands": [{"name": "small", "max_px": 32, "drawing": "assets/logo/grid-mark.svg"}, {"name": "large", "drawing": "../outside.svg"}]}
    (pack / "qa" / "rules.json").write_text(json.dumps(rules), encoding="utf-8")
    r = build(pack)
    assert r.returncode == 2 and "outside the project" in r.stderr and not (pack / ".claude").exists()
    rules["bands"][1]["drawing"] = "assets/logo/./mark.svg"
    (pack / "qa" / "rules.json").write_text(json.dumps(rules), encoding="utf-8")
    r = build(pack)
    assert r.returncode == 2 and "assets/logo/mark.svg" in r.stderr and not (pack / ".claude").exists()      # the kit names a drawing by its plain path
    rules["bands"][1]["drawing"] = str(pack / "assets" / "logo" / "mark.svg")
    (pack / "qa" / "rules.json").write_text(json.dumps(rules), encoding="utf-8")
    r = build(pack)
    assert r.returncode == 2 and "('assets/logo/mark.svg')" in r.stderr and not (pack / ".claude").exists()   # an absolute path inside the project is told the plain path, not itself


def test_the_report_records_the_state_and_the_sources_so_that_a_later_check_can_tell_what_changed(pack):
    assert build(pack).returncode == 0
    first = report(pack, "kit")
    kj = json.loads((kit_of(pack) / "kit.json").read_text(encoding="utf-8"))
    assert set(kj["sources"]) == {"state_sha", "tokens", "tokens_css", "rules", "facts", "motion", "logos", "fonts"}
    assert kj["sources"]["fonts"] is None and kj["fonts"] == {"copied": [], "not_copied": []}                  # Acme has no font
    assert kj["sources"]["tokens"] == file_sha(pack / "assets/tokens/tokens.json") and kj["sources"]["tokens_css"] == file_sha(pack / "assets/tokens/tokens.css")
    assert kj["sources"]["rules"] == file_sha(pack / "qa/rules.json") and kj["sources"]["facts"] == file_sha(pack / "FACTS.md")
    assert kj["sources"]["motion"] is None and kj["sources"]["state_sha"] == first["adapter_state_sha"]       # no motion/motion.json in Acme
    with (pack / "FACTS.md").open("a", encoding="utf-8") as fh:
        fh.write("| voice | plain | owner | 2026-10-17 |\n")
    assert build(pack).returncode == 0
    second = report(pack, "kit")
    assert second["kit_sources_sha"] != first["kit_sources_sha"] and second["adapter_state_sha"] != first["adapter_state_sha"]
    assert second["kit_version"] == "1.2"


def test_kit_json_is_read_strictly_and_an_unknown_key_is_refused_naming_it(pack):
    import kitlib
    from _common import CliError
    assert build(pack).returncode == 0
    assert kitlib.exists(pack) and kitlib.load(pack)["version"] == "1.1"
    f = kit_of(pack) / "kit.json"
    for where, change in (("top level", lambda d: d.__setitem__("flavour", "x")), ("sources", lambda d: d["sources"].__setitem__("colour", "x")),
                          ("schema", lambda d: d.__setitem__("schema", 2))):
        good = f.read_bytes()
        mutate_json(f, change)
        with pytest.raises(CliError) as e:
            kitlib.load(pack)
        assert e.value.code == 2, where
        assert {"top level": "flavour", "sources": "colour", "schema": "schema"}[where] in e.value.message
        f.write_bytes(good)
    f.unlink()
    assert not kitlib.exists(pack)


def test_the_version_follows_the_edition_and_the_content_and_nothing_else():
    import kitlib
    assert kitlib.next_version(None, "1", "aa") == "1.1"
    prev = {"version": "1.3", "edition": "1", "content_sha": "aa"}
    assert kitlib.next_version(prev, "1", "aa") == "1.3"             # nothing changed: the same version
    assert kitlib.next_version(prev, "1", "bb") == "1.4"             # the content changed: the build number goes up by 1
    assert kitlib.next_version({"version": "1.9", "edition": "1", "content_sha": "aa"}, "1", "bb") == "1.10"
    assert kitlib.next_version(prev, "2", "aa") == "2.1"             # a new edition starts again
    assert kitlib.next_version(prev, "2", "bb") == "2.1"


def test_the_content_hash_ignores_the_order_the_files_are_listed_in_and_notices_every_byte():
    import kitlib
    a = kitlib.content_sha({"b": "1" * 64, "a": "2" * 64})
    assert a == kitlib.content_sha({"a": "2" * 64, "b": "1" * 64}) and re.fullmatch(r"[0-9a-f]{64}", a)
    assert a != kitlib.content_sha({"a": "2" * 64, "b": "3" * 64}) and a != kitlib.content_sha({"a": "2" * 64, "c": "1" * 64})
    assert a != kitlib.content_sha({"b": "1" * 64, "a": "2" * 64}, {"voice.md": "4" * 64})       # the owner's files count too


# ---------------------------------------------------------------- check gates the kit, and applied-skill hands over to it

def check_rows(p) -> dict:
    """Run `check` and return its rows by id. What the Acme project as a whole lacks decides check's exit code, so these tests read the kit rows, not the code."""
    r = bc("check", project=p)
    assert "Traceback" not in r.stderr, r.stderr
    return {row["id"]: row for row in report(p, "check")["results"]}


def test_check_fails_a_kit_file_edited_after_the_build(pack):
    assert bc("applied-skill", "--yes", project=pack).returncode == 0         # the project had the plain applied skill first; the kit takes its place
    assert build(pack).returncode == 0
    rows = check_rows(pack)
    assert rows["report:kit"]["status"] == "pass" and rows["kit:file"]["status"] == "pass"
    assert "kit:state" not in rows                                            # nothing changed since the build
    assert [i for i in rows if i.startswith("applied-skill:") or i == "report:applied-skill"] == []     # the kit stands in for the skill: its rows are not run
    skill = kit_of(pack) / "SKILL.md"
    before = mutate(skill, "## Never", "## Never\n\n- Do anything.")
    row = check_rows(pack)["kit:file"]
    assert row["status"] == "fail" and "SKILL.md" in row["detail"] and "edited by hand" in row["detail"]
    assert "change the brand project and run `brand-creator kit build --yes`" in row["detail"]
    skill.write_text(before, encoding="utf-8")
    assert check_rows(pack)["kit:file"]["status"] == "pass"
    css = kit_of(pack) / "brand" / "assets" / "tokens" / "tokens.css"          # a copy of the brand's own file counts as much as SKILL.md
    before = mutate(css, "#4cd7c8", "#4cd7c9")
    row = check_rows(pack)["kit:file"]
    assert row["status"] == "fail" and "brand/assets/tokens/tokens.css" in row["detail"] and "SKILL.md" not in row["detail"]
    css.write_text(before, encoding="utf-8")
    (kit_of(pack) / "brand" / "assets" / "logo" / "wordmark.svg").unlink()      # a file taken away is as much a difference as an edit
    row = check_rows(pack)["kit:file"]
    assert row["status"] == "fail" and "brand/assets/logo/wordmark.svg (missing)" in row["detail"]
    assert build(pack).returncode == 0                                         # the build writes it back
    assert check_rows(pack)["kit:file"]["status"] == "pass"
    for rel in KIT_FILES[:6]:                                                  # six files changed (the first six in order; kit.json is not among them): the detail names four and counts the rest
        (kit_of(pack) / rel).write_bytes(b"x")
    detail = check_rows(pack)["kit:file"]["detail"]
    assert all(rel in detail for rel in KIT_FILES[:4]) and KIT_FILES[4] not in detail and KIT_FILES[5] not in detail and "and 2 more" in detail


def test_check_fails_a_kit_report_that_records_nothing_to_compare_and_never_crashes(pack):
    assert build(pack).returncode == 0
    report_file = pack / "assets" / "_checks" / "kit.json"
    good = report_file.read_text(encoding="utf-8")
    cases = ((lambda d: d.pop("outputs"), "records no outputs", ""), (lambda d: d.__setitem__("outputs", {}), "records no outputs", ""),
             (lambda d: d.__setitem__("outputs", ["SKILL.md"]), "records no outputs", ""),
             (lambda d: d.__setitem__("outputs", {"../../x": "0" * 64}), "cannot be compared", "../../x"),     # a record that is no sha256 of a file of the kit is named, never opened
             (lambda d: d.__setitem__("outputs", {"SKILL.md": 7}), "cannot be compared", "SKILL.md"))
    for change, said, named in cases:
        mutate_json(report_file, change)
        row = check_rows(pack)["kit:file"]
        assert row["status"] == "fail" and said in row["detail"] and named in row["detail"] and "brand-creator kit build --yes" in row["detail"], (said, row)
        report_file.write_text(good, encoding="utf-8")
    assert check_rows(pack)["kit:file"]["status"] == "pass"


def test_check_says_not_verified_when_the_brand_changed_after_the_kit(pack):
    assert build(pack).returncode == 0
    assert "kit:state" not in check_rows(pack)
    mutate(pack / "FACTS.md", "tools are made in batches of 200", "tools are made in batches of 300")
    rows = check_rows(pack)
    assert rows["kit:state"]["status"] == "skipped" and "not verified" in rows["kit:state"]["detail"] and "brand-creator kit build --yes" in rows["kit:state"]["detail"]
    assert rows["kit:file"]["status"] == "pass"                                # the files are the bytes the build wrote; it is the brand that moved on
    assert build(pack).returncode == 0
    rows = check_rows(pack)
    assert "kit:state" not in rows and rows["report:kit"]["status"] == "pass" and rows["kit:file"]["status"] == "pass"
    assert bc("state", "--set", "name=Acme Tools", project=pack).returncode == 0          # BRAND-STATE.md is not an input of the report: its view is hashed
    rows = check_rows(pack)
    assert rows["report:kit"]["status"] == "pass" and rows["kit:state"]["status"] == "skipped"
    assert build(pack).returncode == 0
    assert "kit:state" not in check_rows(pack)
    # A new logo changes `kit_sources_sha` and nothing else: the name and FACTS.md are hashed into both shas, and a logo that did not exist when the kit was built is not among
    # the report's recorded inputs, so `report:kit` stays green. `kit:state` is the only row that can say so, and it must look at `kit_sources_sha` too.
    shutil.copy(pack / "assets" / "logo" / "wordmark.svg", pack / "assets" / "logo" / "zz-extra.svg")
    rows = check_rows(pack)
    assert rows["report:kit"]["status"] == "pass" and rows["kit:file"]["status"] == "pass"
    assert rows["kit:state"]["status"] == "skipped" and "not verified" in rows["kit:state"]["detail"]
    assert build(pack).returncode == 0
    assert "kit:state" not in check_rows(pack)


def test_check_does_not_judge_the_brand_against_a_kit_report_that_did_not_pass(pack):
    assert build(pack).returncode == 0
    report_file = pack / "assets" / "_checks" / "kit.json"
    shutil.copy(pack / "assets" / "logo" / "wordmark.svg", pack / "assets" / "logo" / "zz-extra.svg")     # the brand moved on; a logo is no recorded input, so the report row stays as the report says
    assert check_rows(pack)["kit:state"]["status"] == "skipped"                # after a passing report: not verified
    mutate_json(report_file, lambda d: d.__setitem__("status", "fail"))
    rows = check_rows(pack)
    assert rows["report:kit"]["status"] == "fail" and "kit:state" not in rows   # a report that failed is already a failure: there is no "made from" to compare


def test_the_applied_skill_command_hands_over_to_the_kit(pack):
    assert build(pack).returncode == 0
    before = kit_state(pack)
    skill_report = pack / "assets" / "_checks" / "applied-skill.json"
    for args in (("--yes",), ("--yes", "--replace"), ("--plan",), ()):
        r = bc("applied-skill", *args, project=pack)
        assert r.returncode == 2, (args, r.stdout, r.stderr)
        assert "this project's brand skill is a kit (kit.json): run `brand-creator kit build --yes`" in r.stderr, args
        assert not skill_report.exists() and not list(pack.glob("removed-*")) and kit_state(pack) == before, args       # before any write
    (kit_of(pack) / "kit.json").unlink()                                       # without kit.json the folder is a plain applied skill again
    assert bc("applied-skill", "--yes", "--replace", project=pack).returncode == 0
    assert skill_report.is_file()


def test_the_kit_is_searched_by_the_cascade(pack):
    assert build(pack).returncode == 0
    r = bc("check", "--cascade", "#4cd7c8", project=pack)
    assert "Traceback" not in r.stderr
    cas = next(x for x in report(pack, "check")["results"] if x["id"] == "cascade:#4cd7c8")
    kit_hits = [h for h in cas["hits"] if h.startswith(".claude/skills/acme-brand/brand/")]
    assert cas["status"] == "fail" and any(h.startswith(".claude/skills/acme-brand/brand/assets/tokens/tokens.css:") for h in kit_hits), cas["hits"]
    assert any(h.startswith(".claude/skills/acme-brand/SKILL.md:") for h in cas["hits"])


# ---------------------------------------------------------------- motion: the spec, its hand-off text and the demo page
# Acme has motion/demo.html and motion/proof.json (a states case and a page case named demo-page) but no motion/motion.json: the brand has not decided, so
# the fourteen files of a build hold no motion file. The spec is written as test_adapters.py writes it; its tokens (two durations and a curve) are built first.
from test_adapters import add_motion, off_spec, on_spec, put_spec  # noqa: E402

MOTION_KIT = ["brand/motion/SPEC.md", "brand/motion/demo.html", "brand/motion/motion.json"]
SPEC_TEXT = "# Motion spec\n\nThe dot drops onto the grid and settles.\n"


def moving(p, *, spec_md=True):
    """Acme decides that it moves: the duration and curve tokens built, motion/motion.json written, and the hand-off text next to it."""
    add_motion(p)
    put_spec(p, on_spec())
    if spec_md:
        (p / "motion" / "SPEC.md").write_text(SPEC_TEXT, encoding="utf-8")


def motion_hash(p, rels) -> str:
    """sha256 over the (path, sha256 of the file) pairs, sorted by path, as the plan words it: `<path>\\0<sha256>\\n` for each."""
    return hashlib.sha256("".join(f"{r}\0{file_sha(p / r)}\n" for r in sorted(rels)).encode()).hexdigest()


def test_a_brand_that_moves_gets_its_motion_spec_and_demo_page_in_the_kit(pack):
    moving(pack)
    r = bc("kit", "build", "--plan", project=pack)
    assert r.returncode == 0 and r.stdout.splitlines()[0] == "would write 17 generated files into .claude/skills/acme-brand/ (version 1.1)", r.stdout + r.stderr
    r = build(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert kit_files(pack) == sorted([*KIT_FILES, *MOTION_KIT])                    # the proof itself (motion/proof.json) is a test file, not the brand's
    for rel in ("motion/motion.json", "motion/SPEC.md", "motion/demo.html"):
        assert filecmp.cmp(pack / rel, kit_of(pack) / "brand" / rel, shallow=False), rel
    assert (kit_of(pack) / "brand" / "motion" / "SPEC.md").read_text(encoding="utf-8") == SPEC_TEXT
    assert json.loads((kit_of(pack) / "brand/motion/motion.json").read_text(encoding="utf-8"))["signature"]["name"] == " Settle "      # the bytes, not a tidied copy
    assert set(MOTION_KIT) <= set(kit_json(pack)["generated"]) and all(file_sha(kit_of(pack) / rel) == sha for rel, sha in kit_json(pack)["generated"].items())
    skill = (kit_of(pack) / "SKILL.md").read_text(encoding="utf-8")
    assert all(f"- `{rel}`" in skill for rel in MOTION_KIT)
    assert kit_json(pack)["sources"]["motion"] == motion_hash(pack, ["motion/motion.json", "motion/SPEC.md", "motion/demo.html"])
    assert kit_json(pack)["sources"]["motion"] != file_sha(pack / "motion" / "motion.json")
    rep = report(pack, "kit")
    assert rep["status"] == "pass" and sorted(rep["outputs"]) == sorted([*KIT_FILES, *MOTION_KIT])
    assert {"motion/motion.json", "motion/SPEC.md", "motion/demo.html"} <= {i["path"] for i in rep["inputs"]}
    assert written_row(pack)["detail"] == "17 generated files: 17 written, 0 unchanged, 0 moved to removed-2026-10-17/; version 1.1"
    first = kit_state(pack)
    assert build(pack).returncode == 0 and kit_state(pack) == first and kit_json(pack)["version"] == "1.1"       # a second build writes nothing


def test_a_brand_where_nothing_moves_gets_only_its_reason(pack):
    assert build(pack).returncode == 0
    assert kit_files(pack) == KIT_FILES and kit_json(pack)["sources"]["motion"] is None          # nothing decided: no motion file, though Acme has a demo page and a proof
    put_spec(pack, off_spec())
    r = build(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert kit_files(pack) == sorted([*KIT_FILES, "brand/motion/motion.json"])                  # the reason is in the spec; no demo page, no proof, nothing that moves
    assert filecmp.cmp(pack / "motion" / "motion.json", kit_of(pack) / "brand/motion/motion.json", shallow=False)
    assert json.loads((kit_of(pack) / "brand/motion/motion.json").read_text(encoding="utf-8"))["reason"] == off_spec()["reason"]
    assert kit_json(pack)["sources"]["motion"] == motion_hash(pack, ["motion/motion.json"]) and kit_json(pack)["version"] == "1.2"


def test_a_proof_page_outside_the_project_stops_the_build(pack, tmp_path):
    moving(pack)
    (tmp_path / "outside.html").write_text("<!doctype html><title>outside</title>", encoding="utf-8")
    proof = pack / "motion" / "proof.json"
    mutate_json(proof, lambda d: d["cases"][1].__setitem__("page", "../outside.html"))
    r = build(pack)
    assert r.returncode == 2 and "outside the project" in r.stderr and "Traceback" not in r.stderr and not (pack / ".claude").exists()
    mutate_json(proof, lambda d: d["cases"][1].__setitem__("page", "motion/gone.html"))
    r = build(pack)
    assert r.returncode == 1 and "motion/gone.html" in r.stderr and "demo-page" in r.stderr and "Traceback" not in r.stderr and not (pack / ".claude").exists()
    for page in ("./motion/demo.html", "motion/../motion/demo.html", str(pack / "motion" / "demo.html")):     # the same file by other names: one copy, at its plain path
        mutate_json(proof, lambda d: d["cases"][1].__setitem__("page", page))
        r = build(pack)
        assert r.returncode == 0, page + "\n" + r.stdout + r.stderr
        assert kit_files(pack) == sorted([*KIT_FILES, *MOTION_KIT]), page


def test_a_changed_demo_page_rebuilds_its_copy_and_changes_the_motion_source(pack):
    moving(pack)
    assert build(pack).returncode == 0
    before = kit_json(pack)["sources"]["motion"]
    mutate(pack / "motion" / "demo.html", "press 320ms", "press 640ms")
    r = build(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert filecmp.cmp(pack / "motion" / "demo.html", kit_of(pack) / "brand/motion/demo.html", shallow=False) and "press 640ms" in (kit_of(pack) / "brand/motion/demo.html").read_text(encoding="utf-8")
    assert kit_json(pack)["sources"]["motion"] != before and kit_json(pack)["version"] == "1.2" and not list(pack.glob("removed-*"))
    (pack / "motion" / "SPEC.md").unlink()                                                      # the hand-off text taken away: its copy goes to removed-<date>/
    r = build(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "brand/motion/SPEC.md" in r.stdout and (pack / KIT_REMOVED / "brand/motion/SPEC.md").read_text(encoding="utf-8") == SPEC_TEXT
    assert kit_files(pack) == sorted([*KIT_FILES, "brand/motion/demo.html", "brand/motion/motion.json"]) and kit_json(pack)["version"] == "1.3"


def test_a_motion_proof_that_cannot_be_read_stops_the_build_and_none_leaves_only_the_spec(pack):
    moving(pack, spec_md=False)
    (pack / "motion" / "proof.json").unlink()                                                   # no proof: no page to copy, only the spec
    r = build(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert kit_files(pack) == sorted([*KIT_FILES, "brand/motion/motion.json"]) and kit_json(pack)["sources"]["motion"] == motion_hash(pack, ["motion/motion.json"])
    (pack / "motion" / "proof.json").write_text("{", encoding="utf-8")                         # a proof the kit cannot read is not a proof without pages
    r = build(pack)
    assert r.returncode == 2 and "motion/proof.json" in r.stderr and "Traceback" not in r.stderr
    (pack / "motion" / "proof.json").write_text(json.dumps({"schema": 1, "cases": [{"name": "demo-page", "type": "page", "selector": "#mark"}]}), encoding="utf-8")
    r = build(pack)
    assert r.returncode == 2 and "demo-page" in r.stderr and "names no page" in r.stderr
    assert kit_files(pack) == sorted([*KIT_FILES, "brand/motion/motion.json"]) and kit_json(pack)["version"] == "1.1"      # the kit of the first build stands


# ---------------------------------------------------------------- rules.json and facts.json: the rules and the facts as data
# The contrast ratios are worked out by hand from the Acme colours (light: text #0d1b2d, muted #4b596c, accent #007d71 on #f9f7ee; dark: text #f0eee7, muted #a7b2c1,
# accent #4cd7c8 on #0e141d), with the WCAG formula, and rounded to 2 decimals.
ACME_PAIRS = [
    {"fg": "color.text", "bg": "color.bg", "kind": "ui-text", "min": 4.5, "light": 16.15, "dark": 15.92},
    {"fg": "color.muted", "bg": "color.bg", "kind": "ui-text", "min": 4.5, "light": 6.64, "dark": 8.61},
    {"fg": "color.accent", "bg": "color.bg", "kind": "ui-text-large", "min": 3, "light": 4.69, "dark": 10.44},
    {"fg": "color.border", "bg": "color.bg", "kind": "ui-component", "min": 3, "light": 6.64, "dark": 8.61},
    {"fg": "color.mark", "bg": "color.bg", "kind": "brand-rule", "min": 3, "light": 16.15, "dark": 15.92},
    {"fg": "color.accent", "bg": "color.bg", "kind": "brand-rule", "min": 2, "light": 4.69, "dark": 10.44},
]
ACME_BANDS = [{"mark": None, "name": "small", "max_px": 32, "drawing": "brand/assets/logo/grid-mark.svg"},
              {"mark": None, "name": "large", "max_px": None, "drawing": "brand/assets/logo/mark.svg"}]
PLACEHOLDER_RULE = "- (rule) (...)"          # the line the template leaves in BRAND-STATE.md Rules (G4)
CONTACT_VALUES = ("Sample Person", "Founder", "+00 000 000 000", "1 Example Street")


def record_rules(p, *lines):
    """Record G4 "(rule)" lines in BRAND-STATE.md by replacing the template's placeholder bullet."""
    mutate(p / "BRAND-STATE.md", PLACEHOLDER_RULE, "\n".join(f"- (rule) {t}" for t in lines))


def rules_of(p) -> dict:
    return json.loads((kit_of(p) / "rules.json").read_text(encoding="utf-8"))


def facts_of(p) -> dict:
    return json.loads((kit_of(p) / "facts.json").read_text(encoding="utf-8"))


def test_rules_json_lists_the_g4_rules_with_ids_and_the_pairs_with_their_ratios(pack):
    record_rules(pack, "The mark keeps its clear space", "A button says at most three words, always")
    mutate(pack / "brief" / "BRIEF.md", "FORBIDDEN count in every page shot. -->", "FORBIDDEN count in every page shot. -->\n\n- synergy\n- `leverage`")
    r = build(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert kit_files(pack) == KIT_FILES and "rules.json" in KIT_FILES and "facts.json" in KIT_FILES
    expected = {"schema": 1, "edition": "1",
                "g4": [{"id": "the-mark-keeps-its-clear-space", "text": "The mark keeps its clear space"},
                       {"id": "a-button-says-at-most-three", "text": "A button says at most three words, always"}],
                "downscale": {"accent_min_px": 4, "accent_rule_max_size": 32, "from": "qa/rules.json"},
                "bands": ACME_BANDS, "pairs": ACME_PAIRS, "forbidden": ["synergy", "leverage"]}
    text = (kit_of(pack) / "rules.json").read_text(encoding="utf-8")
    assert json.loads(text) == expected
    assert text == json.dumps(expected, indent=2, ensure_ascii=False) + "\n" and "page" not in json.loads(text)      # Acme's qa/rules.json has no page block
    kj = kit_json(pack)
    assert {"rules.json", "facts.json"} <= set(kj["generated"]) and kj["generated"]["rules.json"] == file_sha(kit_of(pack) / "rules.json")
    assert "rules.json" in report(pack, "kit")["outputs"] and "facts.json" in report(pack, "kit")["outputs"]
    skill = (kit_of(pack) / "SKILL.md").read_text(encoding="utf-8")
    assert "- `rules.json`" in skill and "- `facts.json`" in skill                                                    # both are listed in the kit section
    first = kit_state(pack)
    assert build(pack).returncode == 0 and kit_state(pack) == first                                                   # a second build writes nothing


def test_rules_json_says_where_the_size_rule_comes_from_and_names_each_marks_drawings(pack):
    rules = {"schema": 1, "bands": [{"name": "small", "max_px": 32, "drawing": "assets/logo/grid-mark.svg"}, {"name": "large", "drawing": "assets/logo/mark.svg"}]}
    (pack / "qa" / "rules.json").write_text(json.dumps(rules), encoding="utf-8")                         # the project's file sets no downscale number
    assert build(pack).returncode == 0
    assert rules_of(pack)["downscale"] == {"accent_min_px": 4, "accent_rule_max_size": 32, "from": "plugin proposal"}
    assert rules_of(pack)["bands"] == ACME_BANDS
    marks = {"schema": 1, "downscale": {"accent_min_px": 3, "accent_rule_max_size": 24},
             "marks": {"tool-a": {"bands": [{"name": "small", "max_px": 16, "drawing": "assets/logo/grid-mark.svg"}, {"name": "large", "drawing": "assets/logo/mark.svg"}]},
                       "tool-b": {"bands": [{"name": "all", "drawing": "assets/logo/wordmark.svg"}]}}}
    (pack / "qa" / "rules.json").write_text(json.dumps(marks), encoding="utf-8")
    assert build(pack).returncode == 0
    assert rules_of(pack)["downscale"] == {"accent_min_px": 3, "accent_rule_max_size": 24, "from": "qa/rules.json"}
    assert rules_of(pack)["bands"] == [{"mark": "tool-a", "name": "small", "max_px": 16, "drawing": "brand/assets/logo/grid-mark.svg"},
                                       {"mark": "tool-a", "name": "large", "max_px": None, "drawing": "brand/assets/logo/mark.svg"},
                                       {"mark": "tool-b", "name": "all", "max_px": None, "drawing": "brand/assets/logo/wordmark.svg"}]
    for band in rules_of(pack)["bands"]:
        assert (kit_of(pack) / band["drawing"]).is_file()                                                  # every drawing rules.json names is in the kit


def test_a_rule_in_polish_gets_an_ascii_id_and_two_alike_get_a_number(pack):
    record_rules(pack, "Znak zawsze na jasnym tle", "Żółta łata nigdy nie zasłania znaku", "Znak zawsze na jasnym tle",
                 "Mark, always on a light ground, never on a photo", "Mark, always on a light ground, only in the brand colours", "Znak zawsze na jasnym tle")
    assert build(pack).returncode == 0
    assert rules_of(pack)["g4"] == [
        {"id": "znak-zawsze-na-jasnym-tle", "text": "Znak zawsze na jasnym tle"},
        {"id": "zolta-lata-nigdy-nie-zaslania-znaku", "text": "Żółta łata nigdy nie zasłania znaku"},      # ż and ó fold to z and o, ł to l
        {"id": "znak-zawsze-na-jasnym-tle-2", "text": "Znak zawsze na jasnym tle"},
        {"id": "mark-always-on-a-light-ground", "text": "Mark, always on a light ground, never on a photo"},   # only the first six words count ...
        {"id": "mark-always-on-a-light-ground-2", "text": "Mark, always on a light ground, only in the brand colours"},   # ... so these two are alike
        {"id": "znak-zawsze-na-jasnym-tle-3", "text": "Znak zawsze na jasnym tle"}]
    raw = (kit_of(pack) / "rules.json").read_text(encoding="utf-8")
    assert "Żółta łata nigdy nie zasłania znaku" in raw and "\\u" not in raw                                  # the text keeps its own letters


def test_a_rule_id_is_the_ascii_slug_of_its_first_six_words():
    import kitlib
    cases = {"(rule) The mark keeps its clear space": "the-mark-keeps-its-clear-space",
             "The mark keeps its clear space and more words": "the-mark-keeps-its-clear-space",        # no marker needed; the seventh word is not read
             "(RULE)   One   MARK per screen!": "one-mark-per-screen",                                   # marker in any case, white space and punctuation do not count
             "(rule) Don't use the mark’s outline": "dont-use-the-marks-outline",                         # apostrophes join, they do not split
             "(rule) Straße: Größe ≥ 4×4 px": "strasse-grosse-4-4-px",                                    # ß and o with an umlaut fold; a sign between two numbers ends a word
             "(rule) Mark—always on light": "mark-always-on-light",                                        # so does a dash with no space round it
             "(rule) — & —": "rule", "(rule) Знак всегда на светлом фоне": "rule"}                       # no ASCII letter or digit: `rule`
    for line, want in cases.items():
        assert kitlib.rule_id(line) == want, line
    assert kitlib.rule_ids(["(rule) Mark", "(rule) Mark", "(rule) Mark 2", "(rule) Mark"]) == ["mark", "mark-2", "mark-2-2", "mark-3"]    # a number already taken is skipped
    assert kitlib.rule_ids(["(rule) — & —", "(rule) Знак"]) == ["rule", "rule-2"]
    assert kitlib.rule_ids([]) == []


def test_facts_json_holds_the_public_facts_and_never_a_contact_row(pack):
    assert build(pack).returncode == 0
    want = [("spare parts", "every tool has a published spare-parts list"), ("batch size", "tools are made in batches of 200"), ("repair guide", "a repair guide is in every box"),
            ("status", "the online shop is in development"), ("AppStream summary", "Hand tools with a published spare-parts list"),
            ("AppStream description", "Acme makes small-batch hand tools. Every tool has a published spare-parts list and a repair guide in the box."),
            ("project license", "MIT"), ("metadata license", "CC0-1.0"), ("website", "https://example.com")]
    doc = facts_of(pack)
    assert doc == {"schema": 1, "facts": [{"fact": f, "value": v, "source": "owner, intake", "confirmed": "2026-10-17"} for f, v in want]}
    raw = (kit_of(pack) / "facts.json").read_text(encoding="utf-8")
    assert raw == json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    assert not [c for c in CONTACT_VALUES if c in raw] and "contact" not in raw and "postal" not in raw        # the contact name, role, phone and the postal address stay out
    assert not [c for c in CONTACT_VALUES if c in (kit_of(pack) / "rules.json").read_text(encoding="utf-8") + (kit_of(pack) / "SKILL.md").read_text(encoding="utf-8")]
    assert kit_json(pack)["generated"]["facts.json"] == file_sha(kit_of(pack) / "facts.json")


def test_facts_json_of_a_project_without_facts_is_an_empty_list(acme):
    for kv in ("content_languages=en", "edition=1"):
        assert bc("state", "--set", kv, project=acme).returncode == 0
    assert bc("state", "--record", "G5", "approved (test)", project=acme).returncode == 0
    (acme / "FACTS.md").unlink()                                                                               # a project that has not written its facts
    r = build(acme)
    assert r.returncode == 0, r.stdout + r.stderr
    assert facts_of(acme) == {"schema": 1, "facts": []} and (kit_of(acme) / "facts.json").read_text(encoding="utf-8") == '{\n  "schema": 1,\n  "facts": []\n}\n'
    assert rules_of(acme)["g4"] == [] and rules_of(acme)["forbidden"] == []                                    # no recorded rule, no forbidden word: empty lists, never a missing key


def test_the_page_block_of_qa_rules_reaches_rules_json_unchanged(pack):
    block = {"widths": [360, 1280], "display_min_px": 24, "clear_space": 0.3,
             "rules": [{"id": "one-mark", "kind": "max-marks-per-view", "max": 1, "g4": "one mark per screen"},
                       {"id": "short-buttons", "kind": "max-words-per-control", "max": 3, "g4": "a button says at most three words"}]}
    mutate_json(pack / "qa" / "rules.json", lambda d: d.__setitem__("page", block))
    assert build(pack).returncode == 0
    assert rules_of(pack)["page"] == block and list(rules_of(pack)["page"]) == list(block)                     # the same keys in the same order
    only = {"rules": [{"id": "no-eyebrow", "kind": "tell", "tell": "eyebrow", "g4": "no eyebrow over a heading"}]}
    mutate_json(pack / "qa" / "rules.json", lambda d: d.__setitem__("page", only))
    assert build(pack).returncode == 0
    assert rules_of(pack)["page"] == only                                                                      # a block that sets one key is written as it is, with no default added
    assert kit_json(pack)["version"] == "1.2"


def test_a_rule_recorded_after_the_build_rewrites_rules_json_and_is_no_hand_edit(pack):
    record_rules(pack, "The mark keeps its clear space")
    assert build(pack).returncode == 0
    mutate(pack / "BRAND-STATE.md", "- (rule) The mark keeps its clear space", "- (rule) The mark keeps its clear space\n- (rule) Never stretch the mark")
    r = build(pack)
    assert r.returncode == 0, r.stdout + r.stderr                                                              # the old rules.json is the last build's, not somebody's edit
    assert [g["id"] for g in rules_of(pack)["g4"]] == ["the-mark-keeps-its-clear-space", "never-stretch-the-mark"]
    assert kit_json(pack)["version"] == "1.2" and not list(pack.glob("removed-*"))
    mutate(pack / "FACTS.md", "tools are made in batches of 200", "tools are made in batches of 300")          # and the same for facts.json
    assert build(pack).returncode == 0
    assert "tools are made in batches of 300" in (kit_of(pack) / "facts.json").read_text(encoding="utf-8") and kit_json(pack)["version"] == "1.3"
    assert not list(pack.glob("removed-*"))


def test_a_hand_edited_rules_json_or_facts_json_stops_the_build_and_check_fails_it(pack):
    record_rules(pack, "The mark keeps its clear space")
    assert build(pack).returncode == 0
    assert check_rows(pack)["kit:file"]["status"] == "pass"
    for name, old, new in (("rules.json", "The mark keeps its clear space", "The mark may be stretched"), ("facts.json", "MIT", "GPL")):
        f = kit_of(pack) / name
        before = mutate(f, old, new)
        row = check_rows(pack)["kit:file"]
        assert row["status"] == "fail" and name in row["detail"] and "edited by hand" in row["detail"], (name, row)
        r = build(pack)
        assert r.returncode == 1 and f"{name} (edited by hand)" in r.stderr and new in f.read_text(encoding="utf-8"), (name, r.stderr)
        r = build(pack, "--replace")
        assert r.returncode == 0, r.stderr
        assert f.read_text(encoding="utf-8") == before and new in (pack / KIT_REMOVED / name).read_text(encoding="utf-8")      # the plan's bytes are back, the edit is kept aside
        assert check_rows(pack)["kit:file"]["status"] == "pass"


def test_known_rule_ids_are_the_g4_slugs_the_page_rules_and_the_site_rule_choices(pack):
    import kitlib
    from _common import CliError
    record_rules(pack, "The mark keeps its clear space", "Never stretch the mark")
    assert kitlib.known_rule_ids(pack) == ["the-mark-keeps-its-clear-space", "never-stretch-the-mark"]       # no page rules and no site record yet
    assert kitlib.g4_rules(pack) == [{"id": "the-mark-keeps-its-clear-space", "text": "The mark keeps its clear space"},
                                     {"id": "never-stretch-the-mark", "text": "Never stretch the mark"}]
    mutate_json(pack / "qa" / "rules.json", lambda d: d.__setitem__("page", {"rules": [
        {"id": "one-mark", "kind": "max-marks-per-view", "max": 1, "g4": "one mark per screen"},
        {"id": "short-buttons", "kind": "max-words-per-control", "max": 3, "g4": "a button says at most three words"}]}))
    assert kitlib.known_rule_ids(pack) == ["the-mark-keeps-its-clear-space", "never-stretch-the-mark", "page:one-mark", "page:short-buttons"]
    site = {"schema": 1, "approved": "2026-10-17 (test)", "round": 1, "hero": "a", "pages": [],
            "choices": [{"id": "c1", "text": "the footer repeats the contact line", "tag": "rule", "source": "DECISIONS.md"},
                        {"id": "c2", "text": "a calm blue", "tag": "example", "source": ""}, {"id": "c3", "text": "one call to action", "tag": "rule", "source": "DECISIONS.md"}]}
    (pack / "site").mkdir()
    (pack / "site" / "site.json").write_text(json.dumps(site), encoding="utf-8")
    assert kitlib.known_rule_ids(pack) == ["the-mark-keeps-its-clear-space", "never-stretch-the-mark", "page:one-mark", "page:short-buttons", "site:c1", "site:c3"]   # an example is no rule
    (pack / "site" / "site.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(CliError) as e:
        kitlib.known_rule_ids(pack)
    assert e.value.code == 1 and "site/site.json" in e.value.message


# ---------------------------------------------------------------- grounds: the page roles mapped to those of each ground the owner named
# add_grounds (test_adapters) gives Acme the page ground, color.bg, with its five roles: text color.text, action color.accent, on-action color.on-accent, focus
# color.focus and border color.border. Those five are the base variables --color-text, --color-accent, --color-on-accent, --color-focus and --color-border, the names
# tokens.css gives them. Every other ground below is one more entry of the list, with semantic colours of its own built into the tokens.
from test_adapters import add_grounds  # noqa: E402

ON_GROUND = "snippets/on-ground.css"
GROUND_HEAD = ('/* generated by brand-creator from the grounds in assets/tokens/tokens.json; load it after tokens.css; the first ground is the page ground and its '
               'colours are the base variables; put data-ground="<name>" on an element that sits on another ground */')
NAMED = "2026-10-30 text sits on the page colour and on the night panel"
PANEL_RULE = ('[data-ground="panel"] {\n'
              '  background-color: var(--color-panel);\n'
              '  --color-text: var(--color-on-panel);\n'
              '  --color-accent: var(--color-panel-action);\n'
              '  --color-on-accent: var(--color-on-panel-action);\n'
              '  --color-focus: var(--color-panel-focus);\n'
              '  --color-border: var(--color-panel-border);\n'
              '}\n')
DUSK_RULE = ('[data-ground="dusk"] {\n'
             '  background-color: var(--color-dusk);\n'
             '  --color-text: var(--color-on-dusk);\n'
             '  --color-accent: var(--color-dusk-action);\n'
             '  --color-on-accent: var(--color-on-dusk-action);\n'
             '  --color-focus: var(--color-dusk-focus);\n'
             '  --color-border: var(--color-dusk-border);\n'
             '}\n')


def ground_entry(key: str) -> dict:
    """The grounds-list entry of a ground `color.<key>` with roles of its own: color.on-<key>, color.<key>-action, color.on-<key>-action, color.<key>-focus, color.<key>-border."""
    return {"ground": f"color.{key}", "text": f"color.on-{key}", "action": f"color.{key}-action", "on-action": f"color.on-{key}-action", "focus": f"color.{key}-focus",
            "border": f"color.{key}-border"}


def add_ground_tokens(p, key: str, ground: str = "night") -> None:
    """The six semantic colours of ground_entry(key), in light and dark, from Acme's primitives (the ground is `ground`, the rest light text, a bright accent and a mid
    grey). Not built yet: the test builds the tokens once the grounds list is in place."""
    prims = {f"{key}": ground, f"on-{key}": "paper", f"{key}-action": "teal-bright", f"on-{key}-action": "night", f"{key}-focus": "teal-bright", f"{key}-border": "slate"}
    for mode in ("light", "dark"):
        mutate_json(p / "tokens" / f"semantic.{mode}.tokens.json", lambda d: d["color"].update({k: {"$value": "{color." + v + "}"} for k, v in prims.items()}))


def build_tokens(p) -> None:
    r = bc("tokens", project=p)
    assert r.returncode == 0, r.stdout + r.stderr


def grounds_row(p) -> dict | None:
    return next((r for r in report(p, "kit")["results"] if r["id"] == "kit:grounds"), None)


def snippet(p) -> str:
    return (kit_of(p) / ON_GROUND).read_text(encoding="utf-8")


def test_each_named_ground_gets_a_scope_that_maps_the_page_roles_to_its_own(pack):
    add_grounds(pack, named=NAMED)                                                  # one ground, the page ground: it is the base, there is nothing to scope yet
    r = build(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert kit_files(pack) == KIT_FILES and grounds_row(pack)["status"] == "info"
    assert grounds_row(pack)["detail"] == "only the page ground (color.bg) is listed, so there is no other ground to scope: snippets/on-ground.css is not written"
    add_ground_tokens(pack, "panel")
    add_ground_tokens(pack, "dusk", ground="slate")
    mutate_json(pack / "tokens" / "semantic.light.tokens.json",
                lambda d: d["$extensions"]["brand-creator"]["grounds"]["list"].extend([ground_entry("panel"), ground_entry("dusk")]))
    build_tokens(pack)
    assert (json.loads((pack / "assets/tokens/tokens.json").read_text(encoding="utf-8"))["grounds"]["named_by_owner"]) == NAMED
    r = bc("kit", "build", "--plan", project=pack)
    assert r.returncode == 0 and r.stdout.splitlines()[0] == "would write 15 generated files into .claude/skills/acme-brand/ (version 1.2)", r.stdout + r.stderr
    r = build(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert kit_files(pack) == sorted([*KIT_FILES, ON_GROUND])
    assert snippet(pack) == GROUND_HEAD + "\n\n" + PANEL_RULE + "\n" + DUSK_RULE                       # one rule per other ground, in the order they are listed; none for the page ground
    css = (kit_of(pack) / "brand/assets/tokens/tokens.css").read_text(encoding="utf-8")
    used = set(re.findall(r"(--[a-z0-9-]+)", snippet(pack).split("*/", 1)[1]))
    assert used and all(re.search(rf"^\s*{re.escape(v)}:", css, re.M) for v in used), sorted(v for v in used if f"{v}:" not in css)      # every name is one tokens.css declares
    assert {"--color-text", "--color-accent", "--color-on-accent", "--color-focus", "--color-border", "--color-panel", "--color-on-dusk-action"} <= used
    assert ON_GROUND in kit_json(pack)["generated"] and file_sha(kit_of(pack) / ON_GROUND) == kit_json(pack)["generated"][ON_GROUND]
    assert f"- `{ON_GROUND}`" in (kit_of(pack) / "SKILL.md").read_text(encoding="utf-8")
    row = grounds_row(pack)
    assert row["status"] == "pass" and row["detail"] == "2 grounds scoped in snippets/on-ground.css; the page ground is color.bg"
    assert report(pack, "kit")["status"] == "pass" and ON_GROUND in report(pack, "kit")["outputs"]
    assert kit_json(pack)["version"] == "1.2"
    first = kit_state(pack)
    assert build(pack).returncode == 0 and kit_state(pack) == first                    # a second build writes nothing


PAGE_GROUND = {"ground": "color.bg", "text": "color.text", "action": "color.accent", "on-action": "color.on-accent", "focus": "color.focus", "border": "color.border"}


def set_grounds(p, named: str, *others: dict, page: dict | None = None) -> None:
    """The grounds of the semantic light source: the page ground first (`page`, or PAGE_GROUND), then `others`, and `named_by_owner` as given. The tokens are built again."""
    path = p / "tokens" / "semantic.light.tokens.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    doc["$extensions"]["brand-creator"]["grounds"] = {"named_by_owner": named, "list": [dict(page or PAGE_GROUND), *others]}
    path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    build_tokens(p)


def test_grounds_that_are_still_a_proposal_get_no_snippet(pack):
    assert build(pack).returncode == 0
    assert grounds_row(pack) is None and kit_files(pack) == KIT_FILES                  # Acme's tokens list no grounds at all: nothing to say
    add_grounds(pack, named="")                                                        # the starter's proposal: no date, no owner's words
    add_ground_tokens(pack, "panel")
    for named in ("", "a proposal for the page colour", "2026-10-30", "2026-13-45 not a date"):
        set_grounds(pack, named, ground_entry("panel"))
        r = build(pack)
        assert r.returncode == 0, named + r.stdout + r.stderr
        assert kit_files(pack) == KIT_FILES, named                                     # a proposal is not written, however complete it looks
        row = grounds_row(pack)
        assert row["status"] == "info" and row["detail"] == "the grounds are a proposal until the owner names them: snippets/on-ground.css is not written", named
        assert report(pack, "kit")["status"] == "pass"                                 # an info row never fails the build
    set_grounds(pack, NAMED, ground_entry("panel"))                                    # the owner names them: now the snippet appears
    assert build(pack).returncode == 0
    assert snippet(pack) == GROUND_HEAD + "\n\n" + PANEL_RULE and grounds_row(pack)["status"] == "pass"
    set_grounds(pack, "", ground_entry("panel"))                                       # and goes again if the naming is withdrawn: the file is moved to removed-<date>/
    r = build(pack)
    assert r.returncode == 0 and ON_GROUND in r.stdout and not (kit_of(pack) / ON_GROUND).exists()
    assert (pack / KIT_REMOVED / ON_GROUND).read_text(encoding="utf-8") == GROUND_HEAD + "\n\n" + PANEL_RULE


def test_a_ground_with_a_missing_role_is_left_out_and_named(pack):
    add_grounds(pack, named=NAMED)
    add_ground_tokens(pack, "panel")
    add_ground_tokens(pack, "dusk", ground="slate")
    light = pack / "tokens" / "semantic.light.tokens.json"
    both = (ground_entry("panel"), ground_entry("dusk"))
    set_grounds(pack, NAMED, *both)
    # no focus colour for the panel: the kit writes the dusk scope and no half a scope for the panel, and says so
    mutate_json(light, lambda d: d["$extensions"]["brand-creator"]["grounds"]["list"][1].pop("focus"))
    build_tokens(pack)
    r = build(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert snippet(pack) == GROUND_HEAD + "\n\n" + DUSK_RULE and 'data-ground="panel"' not in snippet(pack)
    row = grounds_row(pack)
    assert row["status"] == "warn" and row["detail"] == "1 of 2 other grounds scoped in snippets/on-ground.css; left out: color.panel (the tokens give no focus in light and dark)"
    assert report(pack, "kit")["status"] == "pass"                                      # a warning: the rest of the kit is written
    # a role that names no colour token (`tokens` warns, the role resolves as nothing), and a ground with no text role: no ground is whole any more
    set_grounds(pack, NAMED, *both)
    mutate_json(light, lambda d: d["$extensions"]["brand-creator"]["grounds"]["list"][1].__setitem__("border", "color.nope"))
    mutate_json(light, lambda d: d["$extensions"]["brand-creator"]["grounds"]["list"][2].pop("text"))
    build_tokens(pack)
    r = build(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert ON_GROUND not in kit_files(pack) and not (kit_of(pack) / ON_GROUND).exists()        # no other ground is whole: no snippet, and the one written before moves aside
    assert (pack / KIT_REMOVED / ON_GROUND).read_text(encoding="utf-8") == GROUND_HEAD + "\n\n" + DUSK_RULE
    row = grounds_row(pack)
    assert row["status"] == "warn" and row["detail"] == ("snippets/on-ground.css is not written, every other ground is left out: color.panel (the tokens give no border in light and dark); "
                                                         "color.dusk (the tokens give no text in light and dark)")
    # the page ground itself lacks a role: nothing can be mapped against it, whatever the others hold
    set_grounds(pack, NAMED, *both)
    mutate_json(light, lambda d: d["$extensions"]["brand-creator"]["grounds"]["list"][0].pop("border"))
    build_tokens(pack)
    r = build(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert ON_GROUND not in kit_files(pack)
    row = grounds_row(pack)
    assert row["status"] == "warn" and row["detail"] == ("the page ground (color.bg, the first listed) lacks border in light and dark, so no other ground can be scoped against it: "
                                                         "snippets/on-ground.css is not written")


def test_a_ground_scope_never_points_a_page_variable_at_itself_or_at_one_its_own_rule_sets(pack):
    """The page ground's variables are the ones a scope sets. `--color-border: var(--color-border)` is invalid CSS, so it is not written (the element keeps what it
    inherits). A scope that sets `--color-text` makes every other `var(--color-text)` in the same rule read what the scope set, not the page's colour, so a ground
    that uses a variable its own scope sets is left out and named. A ground whose data-ground name is taken is left out too."""
    add_grounds(pack, named=NAMED)
    for key in ("card", "band", "swap", "panel"):
        add_ground_tokens(pack, key)
    card = {**ground_entry("card"), "focus": "color.focus", "border": "color.border"}              # shares the page's focus ring and border: both stay as the page has them
    band = {**ground_entry("band"), "ground": "color.text", "text": "color.bg"}                       # an inverse band: the page's text colour as its ground
    swap = {**ground_entry("swap"), "text": "color.border", "border": "color.text"}                # two page roles traded
    set_grounds(pack, NAMED, card, band, swap, ground_entry("panel"), ground_entry("panel"))
    r = build(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    card_rule = ('[data-ground="card"] {\n'
                 '  background-color: var(--color-card);\n'
                 '  --color-text: var(--color-on-card);\n'
                 '  --color-accent: var(--color-card-action);\n'
                 '  --color-on-accent: var(--color-on-card-action);\n'
                 '}\n')
    assert snippet(pack) == GROUND_HEAD + "\n\n" + card_rule + "\n" + PANEL_RULE
    assert "--color-focus: var(--color-focus)" not in snippet(pack) and "--color-border: var(--color-border)" not in snippet(pack)
    row = grounds_row(pack)
    clash = "which its own scope sets to something else: give it a token of its own)"
    assert row["status"] == "warn" and row["detail"] == (
        f"2 of 5 other grounds scoped in snippets/on-ground.css; left out: color.text (it uses --color-text, {clash}; "
        f"color.swap (it uses --color-border, --color-text, {clash}; "
        'color.panel (data-ground="panel" is already used by a ground listed before it)')
    # the inverse band gets a colour token of its own for its ground: now it is scoped, with the page's background colour as its text
    mutate_json(pack / "tokens" / "semantic.light.tokens.json", lambda d: d["$extensions"]["brand-creator"]["grounds"]["list"][2].__setitem__("ground", "color.band"))
    build_tokens(pack)
    assert build(pack).returncode == 0
    band_rule = ('[data-ground="band"] {\n'
                 '  background-color: var(--color-band);\n'
                 '  --color-text: var(--color-bg);\n'
                 '  --color-accent: var(--color-band-action);\n'
                 '  --color-on-accent: var(--color-on-band-action);\n'
                 '  --color-focus: var(--color-band-focus);\n'
                 '  --color-border: var(--color-band-border);\n'
                 '}\n')
    assert snippet(pack) == GROUND_HEAD + "\n\n" + card_rule + "\n" + band_rule + "\n" + PANEL_RULE
    assert grounds_row(pack)["detail"].startswith("3 of 5 other grounds scoped in snippets/on-ground.css; left out: color.swap (")


def test_a_page_variable_shared_by_two_roles_is_set_once_or_the_ground_is_left_out(pack):
    """A brand with no focus token writes `focus: color.accent`: the page's action and focus are one variable, `--color-accent`. A rule that sets it twice keeps only the
    later value, so the buttons on the ground would take its focus colour with the check still green. When the ground gives both roles one colour the variable is set
    once; when it gives them two it is left out and named, never written with one of them lost."""
    add_grounds(pack, named=NAMED)
    for key in ("card", "keep", "panel"):
        add_ground_tokens(pack, key)
    page = {**PAGE_GROUND, "focus": "color.accent"}
    card = {**ground_entry("card"), "focus": "color.card-action"}                                   # action and focus agree: --color-accent once
    keep = {**ground_entry("keep"), "action": "color.accent"}                                       # action stays the page's own, focus is another colour: they disagree
    panel = ground_entry("panel")                                                                   # action color.panel-action, focus color.panel-focus: they disagree
    set_grounds(pack, NAMED, card, keep, panel, page=page)
    r = build(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    card_rule = ('[data-ground="card"] {\n'
                 '  background-color: var(--color-card);\n'
                 '  --color-text: var(--color-on-card);\n'
                 '  --color-accent: var(--color-card-action);\n'
                 '  --color-on-accent: var(--color-on-card-action);\n'
                 '  --color-border: var(--color-card-border);\n'
                 '}\n')
    assert snippet(pack) == GROUND_HEAD + "\n\n" + card_rule
    assert snippet(pack).count("--color-accent:") == 1 and 'data-ground="panel"' not in snippet(pack) and 'data-ground="keep"' not in snippet(pack)
    row = grounds_row(pack)
    assert row["status"] == "warn" and row["detail"] == (
        "1 of 3 other grounds scoped in snippets/on-ground.css; left out: "
        "color.keep (the page ground uses --color-accent for action and focus, and this ground gives them different colours (--color-accent and --color-keep-focus): "
        "a scope sets a variable once); "
        "color.panel (the page ground uses --color-accent for action and focus, and this ground gives them different colours (--color-panel-action and --color-panel-focus): "
        "a scope sets a variable once)")
    assert report(pack, "kit")["status"] == "pass"                                                  # a warning: the rest of the kit is written
    # the border is the text colour too: two shared variables. Agreeing on both writes each once, in the order of the roles; the panel disagrees on both and says so twice
    page = {**PAGE_GROUND, "focus": "color.accent", "border": "color.text"}
    card = {**ground_entry("card"), "focus": "color.card-action", "border": "color.on-card"}
    set_grounds(pack, NAMED, card, panel, page=page)
    assert build(pack).returncode == 0
    card_rule = ('[data-ground="card"] {\n'
                 '  background-color: var(--color-card);\n'
                 '  --color-text: var(--color-on-card);\n'
                 '  --color-accent: var(--color-card-action);\n'
                 '  --color-on-accent: var(--color-on-card-action);\n'
                 '}\n')
    assert snippet(pack) == GROUND_HEAD + "\n\n" + card_rule
    assert grounds_row(pack)["detail"] == (
        "1 of 2 other grounds scoped in snippets/on-ground.css; left out: "
        "color.panel (the page ground uses --color-text for text and border, and this ground gives them different colours (--color-on-panel and --color-panel-border): "
        "a scope sets a variable once; "
        "the page ground uses --color-accent for action and focus, and this ground gives them different colours (--color-panel-action and --color-panel-focus): "
        "a scope sets a variable once)")
