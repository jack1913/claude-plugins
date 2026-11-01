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
# bands name grid-mark.svg and mark.svg. The kit folder of a build holds these twelve files, written out by hand (BRAND_CREATOR_TODAY is 2026-10-17).
import filecmp  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402

from helpers import mutate, mutate_json, report  # noqa: E402

KIT_LOGOS = ["grid-mark-dark.svg", "grid-mark-master.png", "grid-mark.svg", "mark-animated.svg", "mark-dark.svg", "mark.svg", "wordmark-dark.svg", "wordmark.svg"]
KIT_FILES = sorted(["SKILL.md", "kit.json", "brand/assets/tokens/tokens.css", "brand/assets/tokens/tokens.json", *[f"brand/assets/logo/{n}" for n in KIT_LOGOS]])
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
    assert "would write 12 generated files into .claude/skills/acme-brand/ (version 1.1)" in r.stdout          # the plan goes to stdout, the message to stderr
    r = bc("kit", "build", "--plan", project=acme)
    assert r.returncode == 0 and not (acme / ".claude").exists() and not (acme / "assets" / "_checks" / "kit.json").exists()
    lines = r.stdout.splitlines()
    assert lines[0] == "would write 12 generated files into .claude/skills/acme-brand/ (version 1.1)"
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
    assert written_row(pack)["detail"] == "12 generated files: 12 written, 0 unchanged, 0 moved to removed-2026-10-17/; version 1.1"
    assert {i["path"] for i in rep["inputs"]} == {"assets/tokens/tokens.css", "assets/tokens/tokens.json", "qa/rules.json", "FACTS.md",
                                                  *[f"assets/logo/{n}" for n in KIT_LOGOS]}


def test_a_second_build_with_nothing_changed_is_byte_identical_and_keeps_the_version(pack):
    assert build(pack).returncode == 0
    first = kit_state(pack)
    r = build(pack)
    assert r.returncode == 0, r.stderr
    assert kit_state(pack) == first                                   # the same bytes, and no file was written again
    assert written_row(pack)["detail"] == "12 generated files: 0 written, 12 unchanged, 0 moved to removed-2026-10-17/; version 1.1"
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
    assert written_row(pack)["detail"] == "12 generated files: 1 written, 11 unchanged, 1 moved to removed-2026-10-17/; version 1.1"
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
    assert written_row(pack)["detail"] == "12 generated files: 0 written, 12 unchanged, 3 moved to removed-2026-10-17/; version 1.1"


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
    assert written_row(pack)["detail"].startswith("11 generated files: ") and "1 moved to removed-2026-10-17/" in written_row(pack)["detail"]
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
    assert r.returncode == 0 and r.stdout.splitlines()[0] == "would write 15 generated files into .claude/skills/acme-brand/ (version 1.1)", r.stdout + r.stderr
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
