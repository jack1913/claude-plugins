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
# bands name grid-mark.svg and mark.svg. The kit folder of a build holds these fifteen files, written out by hand (BRAND_CREATOR_TODAY is 2026-10-17).
import filecmp  # noqa: E402
import hashlib  # noqa: E402
import json  # noqa: E402
import re  # noqa: E402

from helpers import mutate, mutate_json, report  # noqa: E402

KIT_LOGOS = ["grid-mark-dark.svg", "grid-mark-master.png", "grid-mark.svg", "mark-animated.svg", "mark-dark.svg", "mark.svg", "wordmark-dark.svg", "wordmark.svg"]
KIT_FILES = sorted(["SKILL.md", "kit.json", "rules.json", "facts.json", "snippets/logo.html", "brand/assets/tokens/tokens.css", "brand/assets/tokens/tokens.json",
                    *[f"brand/assets/logo/{n}" for n in KIT_LOGOS]])
KIT_REMOVED = "removed-2026-10-17/.claude/skills/acme-brand"
OWNER_FILES = sorted(["EXTENDING.md", "voice.md", "visual.md", "golden-rules.md", "recipes/web-page.md"])   # the owner's files: scaffolded once, not generated, not in KIT_FILES


def kit_of(p):
    return p / ".claude" / "skills" / "acme-brand"


def kit_files(p) -> list[str]:
    """The files of the kit folder that the build generates: the owner's files (OWNER_FILES, scaffolded once) are left out, and `owner_files` lists them."""
    d = kit_of(p)
    return sorted(r for r in (f.relative_to(d).as_posix() for f in d.rglob("*") if f.is_file()) if r not in OWNER_FILES) if d.is_dir() else []


def owner_files(p) -> list[str]:
    d = kit_of(p)
    return sorted(r for r in OWNER_FILES if (d / r).is_file())


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
    assert "would write 15 generated files into .claude/skills/acme-brand/ (version 1.1)" in r.stdout          # the plan goes to stdout, the message to stderr
    r = bc("kit", "build", "--plan", project=acme)
    assert r.returncode == 0 and not (acme / ".claude").exists() and not (acme / "assets" / "_checks" / "kit.json").exists()
    lines = r.stdout.splitlines()
    assert lines[0] == "would write 15 generated files into .claude/skills/acme-brand/ (version 1.1)"
    kinds = [re.fullmatch(r"(generated|scaffold) (\S+) \((\d+) bytes(?:, written once, never overwritten)?\)", ln) for ln in lines[1:]]
    assert all(kinds), [ln for ln, m in zip(lines[1:], kinds) if not m]                      # every line after the first is a generated line or a scaffold line, nothing else
    assert sorted(m.group(2) for m in kinds if m.group(1) == "generated") == KIT_FILES
    assert sorted(m.group(2) for m in kinds if m.group(1) == "scaffold") == OWNER_FILES
    assert all(("written once" in ln) == ln.startswith("scaffold ") for ln in lines[1:])
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
    assert written_row(pack)["detail"] == "15 generated files: 15 written, 0 unchanged, 0 moved to removed-2026-10-17/; version 1.1"
    assert {i["path"] for i in rep["inputs"]} == {"assets/tokens/tokens.css", "assets/tokens/tokens.json", "qa/rules.json", "FACTS.md",
                                                  *[f"assets/logo/{n}" for n in KIT_LOGOS]}


def test_a_second_build_with_nothing_changed_is_byte_identical_and_keeps_the_version(pack):
    assert build(pack).returncode == 0
    first = kit_state(pack)
    r = build(pack)
    assert r.returncode == 0, r.stderr
    assert kit_state(pack) == first                                   # the same bytes, and no file was written again
    assert written_row(pack)["detail"] == "15 generated files: 0 written, 15 unchanged, 0 moved to removed-2026-10-17/; version 1.1"
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
    assert written_row(pack)["detail"] == "15 generated files: 1 written, 14 unchanged, 1 moved to removed-2026-10-17/; version 1.1"
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
    assert (kit_of(pack) / "my-notes.md").is_file() and not (kit_of(pack) / "reference-pages").exists()          # an emptied folder goes ...
    assert sorted(f.name for f in (kit_of(pack) / "snippets").iterdir()) == ["logo.html"]                       # ... one that still holds a generated file stays
    assert written_row(pack)["detail"] == "15 generated files: 2 written, 13 unchanged, 3 moved to removed-2026-10-17/; version 1.2"      # SKILL.md and kit.json: my-notes.md is an owner file, recorded now
    assert sorted(kit_json(pack)["owned"]) == sorted([*OWNER_FILES, "my-notes.md"])


def test_a_finder_ds_store_in_a_generated_folder_is_not_a_foreign_file(pack):
    """macOS puts a `.DS_Store` into a folder the owner opens in Finder. A file named exactly that is ignored in the generated folders: it never stops a build, is never moved,
    and is not in the plan or the report. A file whose name only starts like it is a foreign file as any other."""
    assert build(pack).returncode == 0
    kd = kit_of(pack)
    finder = ["brand/.DS_Store", "brand/assets/logo/.DS_Store", "snippets/.DS_Store", "reference-pages/.DS_Store"]
    for rel in finder:
        (kd / rel).parent.mkdir(parents=True, exist_ok=True)
        (kd / rel).write_bytes(b"\x00\x00\x00\x01Bud1")
    r = bc("kit", "build", "--plan", project=pack)
    assert r.returncode == 0 and "DS_Store" not in r.stdout + r.stderr and r.stdout.splitlines()[0].startswith("would write 15 generated files")
    r = build(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "DS_Store" not in r.stdout + r.stderr and not list(pack.glob("removed-*"))
    assert written_row(pack)["detail"] == "15 generated files: 0 written, 15 unchanged, 0 moved to removed-2026-10-17/; version 1.1"
    assert all((kd / rel).read_bytes() == b"\x00\x00\x00\x01Bud1" for rel in finder)                          # left where Finder put them
    assert not [rel for rel in report(pack, "kit")["outputs"] if "DS_Store" in rel] and not [rel for rel in kit_json(pack)["generated"] if "DS_Store" in rel]
    assert kit_json(pack)["version"] == "1.1"
    (kd / "snippets" / ".DS_Store.bak").write_text("mine\n", encoding="utf-8")
    (kd / "brand" / "assets" / "logo" / "ds_store").write_text("mine\n", encoding="utf-8")                  # not the exact name either
    (kd / "reference-pages" / "old.md").write_text("mine\n", encoding="utf-8")                              # the only foreign file of a folder that Finder also left a file in
    r = build(pack)
    assert r.returncode == 1 and "snippets/.DS_Store.bak (not written by the kit)" in r.stderr and "brand/assets/logo/ds_store (not written by the kit)" in r.stderr
    assert "brand/.DS_Store" not in r.stderr and "snippets/.DS_Store " not in r.stderr
    r = build(pack, "--replace")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "DS_Store.bak" in r.stdout and "brand/.DS_Store" not in r.stdout and (pack / KIT_REMOVED / "snippets/.DS_Store.bak").is_file()
    assert all((kd / rel).is_file() for rel in finder) and not (pack / KIT_REMOVED / "brand" / ".DS_Store").exists()
    assert sorted(f.name for f in (kd / "reference-pages").iterdir()) == [".DS_Store"] and (pack / KIT_REMOVED / "reference-pages" / "old.md").is_file()   # the folder keeps Finder's file: it is not emptied


def test_replace_moves_a_link_in_a_generated_folder_and_never_the_file_it_points_at(pack, tmp_path):
    """A link inside the kit that points at another file (one of the project's, or one beyond it) is a foreign file like any other: `--replace` moves the link itself aside."""
    from helpers import symlink_or_skip
    assert build(pack).returncode == 0
    outside = tmp_path / "outside.txt"
    outside.write_text("outside\n", encoding="utf-8")
    facts = (pack / "FACTS.md").read_bytes()
    symlink_or_skip(kit_of(pack) / "brand" / "notes.md", pack / "FACTS.md")
    symlink_or_skip(kit_of(pack) / "snippets" / "far.txt", outside)
    r = build(pack)
    assert r.returncode == 1 and "brand/notes.md (not written by the kit)" in r.stderr and "snippets/far.txt (not written by the kit)" in r.stderr
    r = build(pack, "--replace")
    assert r.returncode == 0, r.stdout + r.stderr
    assert (pack / "FACTS.md").read_bytes() == facts and outside.read_text(encoding="utf-8") == "outside\n"      # what the links pointed at stays where it was
    assert not (kit_of(pack) / "brand" / "notes.md").is_symlink() and not (kit_of(pack) / "snippets" / "far.txt").is_symlink()
    assert (pack / KIT_REMOVED / "brand" / "notes.md").is_symlink() and (pack / KIT_REMOVED / "snippets" / "far.txt").is_symlink()      # the links are in the backup folder
    assert written_row(pack)["detail"] == "15 generated files: 0 written, 15 unchanged, 2 moved to removed-2026-10-17/; version 1.1"


def test_a_link_to_a_folder_inside_a_generated_folder_is_a_foreign_file_and_is_never_followed(pack):
    """`os.walk` lists a link to a folder with the folders and does not enter it. The kit lists it as the one foreign path it is, and `--replace` moves the link itself: the project folder
    it leads to keeps every file. The same at the path of a file the kit writes, and for a link above planned files, where the files seen through the link are not the kit's to compare or move."""
    from helpers import symlink_or_skip
    assert build(pack).returncode == 0
    kd, assets = kit_of(pack), pack / "assets"
    before = {f.relative_to(pack).as_posix(): file_sha(f) for f in assets.rglob("*") if f.is_file() and "_checks" not in f.parts}
    symlink_or_skip(kd / "brand" / "linked-folder", assets / "logo")
    (kd / "brand/assets/tokens/tokens.css").unlink()
    symlink_or_skip(kd / "brand/assets/tokens/tokens.css", assets / "logo")                              # a folder where a file the kit writes belongs
    r = build(pack)
    assert r.returncode == 1 and "Traceback" not in r.stderr and not list(pack.glob("removed-*"))
    assert "brand/linked-folder (not written by the kit)" in r.stderr and "brand/assets/tokens/tokens.css (not written by the kit)" in r.stderr
    r = build(pack, "--replace")
    assert r.returncode == 0, r.stdout + r.stderr
    assert (pack / KIT_REMOVED / "brand" / "linked-folder").is_symlink() and (pack / KIT_REMOVED / "brand/assets/tokens/tokens.css").is_symlink()
    assert not (kd / "brand" / "linked-folder").exists() and (kd / "brand/assets/tokens/tokens.css").is_file() and not (kd / "brand/assets/tokens/tokens.css").is_symlink()
    assert before == {f.relative_to(pack).as_posix(): file_sha(f) for f in assets.rglob("*") if f.is_file() and "_checks" not in f.parts}      # the project's own files, all there
    assert kit_files(pack) == KIT_FILES and written_row(pack)["detail"] == "15 generated files: 1 written, 14 unchanged, 2 moved to removed-2026-10-17/; version 1.1"
    shutil.rmtree(pack / "removed-2026-10-17")
    stale = {"brand/assets/tokens/stale.txt": "0" * 64}                                                  # recorded by the last build, no longer planned, and seen again through a link:
    (assets / "tokens" / "stale.txt").write_text("mine\n", encoding="utf-8")                              # the project's own file, not the kit's
    mutate_json(pack / "assets" / "_checks" / "kit.json", lambda d: d["outputs"].update(stale))
    shutil.rmtree(kd / "brand" / "assets")
    symlink_or_skip(kd / "brand" / "assets", assets)
    r = build(pack)
    assert r.returncode == 1 and "brand/assets (not written by the kit)" in r.stderr and "stale.txt" not in r.stderr
    r = build(pack, "--replace")
    assert r.returncode == 0, r.stdout + r.stderr
    assert (assets / "tokens" / "stale.txt").read_text(encoding="utf-8") == "mine\n" and (pack / KIT_REMOVED / "brand" / "assets").is_symlink()
    assert not (kd / "brand" / "assets").is_symlink() and kit_files(pack) == KIT_FILES and not (kd / "brand/assets/tokens/stale.txt").exists()


@pytest.mark.parametrize("folder", ["brand", "snippets", "reference-pages"])
def test_a_generated_folder_that_is_a_link_is_a_foreign_file_and_the_folder_it_leads_to_is_never_touched(pack, folder):
    """A generated folder that is itself a link to a folder of the project: the build stops (exit 1, naming the folder), and `--replace` moves the link, never the files of the project
    folder it leads to; the kit then writes a folder of its own."""
    from helpers import symlink_or_skip
    assert build(pack).returncode == 0
    kd, victim = kit_of(pack), pack / "victim"
    if (kd / folder).is_dir():
        shutil.move(str(kd / folder), str(victim))                                                       # the kit's own files, now in a folder of the project
    else:
        victim.mkdir()
    (victim / "owner-notes.md").write_text("mine\n", encoding="utf-8")
    kept = {f.relative_to(victim).as_posix(): file_sha(f) for f in victim.rglob("*") if f.is_file()}
    symlink_or_skip(kd / folder, victim)
    r = build(pack)
    assert r.returncode == 1 and f"{folder} (not written by the kit)" in r.stderr and "Traceback" not in r.stderr and not list(pack.glob("removed-*"))
    r = build(pack, "--replace")
    assert r.returncode == 0, r.stdout + r.stderr
    assert kept == {f.relative_to(victim).as_posix(): file_sha(f) for f in victim.rglob("*") if f.is_file()}        # nothing of the project folder moved, changed or removed
    assert (pack / KIT_REMOVED / folder).is_symlink() and not (kd / folder).is_symlink() and kit_files(pack) == KIT_FILES
    assert not (kd / folder / "owner-notes.md").exists()


@pytest.mark.parametrize("rel", ["brand/assets/tokens/tokens.css", "brand/assets/logo/mark.svg", "snippets/logo.html", "SKILL.md", "rules.json", "facts.json", "kit.json"])
def test_a_link_at_a_path_the_kit_writes_is_a_foreign_file_even_when_it_leads_to_the_bytes_the_last_build_wrote(pack, rel):
    """A link in the kit folder is never read through or written through, not even one that leads to a file holding exactly what the last build recorded (which is no hand edit by the bytes):
    the build stops naming it, and `--replace` moves the link itself, leaving what it pointed at alone; the kit then holds a real file."""
    from helpers import symlink_or_skip
    assert build(pack).returncode == 0
    kd, notes = kit_of(pack), pack / "notes"
    notes.mkdir()
    copy, written = notes / "copy.bin", (kit_of(pack) / rel).read_bytes()
    copy.write_bytes(written)
    (kd / rel).unlink()
    symlink_or_skip(kd / rel, copy)
    r = build(pack)
    assert r.returncode == 1 and "Traceback" not in r.stderr and f"{rel} (not written by the kit)" in r.stderr and not list(pack.glob("removed-*"))
    assert (kd / rel).is_symlink() and copy.read_bytes() == written                          # nothing was written, nothing moved
    r = build(pack, "--replace")
    assert r.returncode == 0, r.stdout + r.stderr
    assert copy.read_bytes() == written                                                      # the file the link pointed at is as it was
    assert (pack / KIT_REMOVED / rel).is_symlink() and (kd / rel).is_file() and not (kd / rel).is_symlink() and kit_files(pack) == KIT_FILES
    assert (kd / rel).read_bytes() == written                                                # the same bytes, in a file of the kit
    assert build(pack).returncode == 0 and not (kd / rel).is_symlink()


@pytest.mark.parametrize("rel, source, change", [
    ("brand/assets/tokens/tokens.css", "assets/tokens/tokens.css", lambda f: f.write_text(f.read_text(encoding="utf-8") + "/* changed */\n", encoding="utf-8")),
    ("facts.json", "FACTS.md", lambda f: mutate(f, "tools are made in batches of 200", "tools are made in batches of 300"))])
def test_a_link_to_the_projects_own_file_or_to_a_backup_copy_is_never_written_through(pack, rel, source, change):
    """Two ways to make the kit write into a project file through a link at a path it writes. A link to the project's own source file; and a link to a backup copy that holds the
    bytes the last build recorded, while the project then changes so that the build has new bytes for that path. Both stop the build, and neither file is touched, with or without `--replace`."""
    from helpers import symlink_or_skip
    assert build(pack).returncode == 0
    kd, notes = kit_of(pack), pack / "notes"
    notes.mkdir()
    own, backup = pack / source, notes / "my-backup"
    recorded = (kd / rel).read_bytes()
    backup.write_bytes(recorded)
    (kd / rel).unlink()
    symlink_or_skip(kd / rel, own)                                                           # (1) a link to the project's own file
    own_before = own.read_bytes()
    r = build(pack)
    assert r.returncode == 1 and f"{rel} (not written by the kit)" in r.stderr and own.read_bytes() == own_before and (kd / rel).is_symlink()
    (kd / rel).unlink()
    symlink_or_skip(kd / rel, backup)                                                        # (2) a link to a backup copy, and the project changes
    change(own)
    changed = own.read_bytes()
    r = build(pack)
    assert r.returncode == 1 and f"{rel} (not written by the kit)" in r.stderr and "Traceback" not in r.stderr
    assert backup.read_bytes() == recorded and (kd / rel).is_symlink() and not list(pack.glob("removed-*"))
    r = build(pack, "--replace")
    assert r.returncode == 0, r.stdout + r.stderr
    assert backup.read_bytes() == recorded and own.read_bytes() == changed                   # the backup keeps the old bytes, the project file is the one it was
    assert (pack / KIT_REMOVED / rel).is_symlink() and (kd / rel).is_file() and not (kd / rel).is_symlink()
    if rel != "facts.json":
        assert (kd / rel).read_bytes() == changed                                            # a real file of the kit now holds the new bytes
    else:
        assert "batches of 300" in (kd / rel).read_text(encoding="utf-8")


def test_a_dangling_link_at_a_path_the_kit_writes_is_a_foreign_file(pack):
    from helpers import symlink_or_skip
    assert build(pack).returncode == 0
    kd = kit_of(pack)
    (kd / "rules.json").unlink()
    symlink_or_skip(kd / "rules.json", pack / "nowhere.json")
    r = build(pack)
    assert r.returncode == 1 and "rules.json (not written by the kit)" in r.stderr and "Traceback" not in r.stderr and not (pack / "nowhere.json").exists()
    assert build(pack, "--replace").returncode == 0 and (kd / "rules.json").is_file() and not (kd / "rules.json").is_symlink() and not (pack / "nowhere.json").exists()


def test_a_kit_json_that_is_a_link_is_no_record_of_the_last_build(pack, tmp_path):
    """With the kit report gone, kit.json stands in for it (`kitlib.previous`), but never through a link: a link that leads out of the project gives neither its version nor its hashes.
    The version behind the link is 1.7, of the kit's own edition, with the content the kit has now: read as a record it would be kept (`next_version`), so only the guard against a
    link in `_kit_json_record` holds the plan at 1.1. A version of another edition (7.7) starts again at 1.1 as a new edition does, with or without the guard."""
    from helpers import symlink_or_skip
    assert build(pack).returncode == 0
    kd, far = kit_of(pack), tmp_path / "far-kit.json"
    far.write_bytes((kd / "kit.json").read_bytes())
    mutate(far, '"version": "1.1"', '"version": "1.7"')
    (kd / "kit.json").unlink()
    symlink_or_skip(kd / "kit.json", far)
    (pack / "assets" / "_checks" / "kit.json").unlink()
    far_before = far.read_bytes()
    r = build(pack, "--plan")
    assert r.returncode == 0 and "version 1.1)" in r.stdout and "1.7" not in r.stdout + r.stderr
    r = build(pack)
    assert r.returncode == 1 and "kit.json (not written by the kit)" in r.stderr and far.read_bytes() == far_before


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
    assert written_row(pack)["detail"].startswith("14 generated files: ") and "1 moved to removed-2026-10-17/" in written_row(pack)["detail"]
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


def test_a_deleted_kit_report_keeps_the_version_and_blames_nobody_for_an_edit(pack):
    """kit.json is the version's only home: with the `kit` report gone, its version and content_sha stand in, and the files the last build wrote are not "edited by hand"."""
    assert build(pack).returncode == 0
    mutate(pack / "FACTS.md", "tools are made in batches of 200", "tools are made in batches of 250")
    assert build(pack).returncode == 0 and kit_json(pack)["version"] == "1.2"            # a version that a fall back to the first build would not give
    report_file = pack / "assets" / "_checks" / "kit.json"
    report_file.unlink()
    first = kit_state(pack)
    r = build(pack)                                                                      # no change in the brand
    assert r.returncode == 0, r.stdout + r.stderr
    assert kit_json(pack)["version"] == "1.2" and kit_state(pack) == first and not list(pack.glob("removed-*"))
    assert report(pack, "kit")["kit_version"] == "1.2" and written_row(pack)["detail"].endswith("0 written, 15 unchanged, 0 moved to removed-2026-10-17/; version 1.2")
    report_file.unlink()
    mutate(pack / "FACTS.md", "tools are made in batches of 250", "tools are made in batches of 300")
    r = build(pack)                                                                      # a change in the brand: the build number goes up by 1
    assert r.returncode == 0, r.stdout + r.stderr
    assert kit_json(pack)["version"] == "1.3" and "Kit version 1.3 (kit.json)." in (kit_of(pack) / "SKILL.md").read_text(encoding="utf-8")
    assert not list(pack.glob("removed-*")) and report(pack, "kit")["kit_version"] == "1.3"


def test_without_a_report_a_kit_json_that_cannot_be_read_gives_no_record(pack):
    """A kit.json that is not a valid kit.json is no record of a build: with no report either, every file counts as the owner's, as before kit.json was read."""
    assert build(pack).returncode == 0
    (pack / "assets" / "_checks" / "kit.json").unlink()
    mutate_json(kit_of(pack) / "kit.json", lambda d: d.__setitem__("flavour", "x"))
    r = build(pack)
    assert r.returncode == 1 and "edited by hand" in r.stderr and "kit.json" in r.stderr and "Traceback" not in r.stderr
    assert build(pack, "--replace").returncode == 0 and kit_json(pack)["version"] == "1.1"


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
             "/* in a product: copy brand/assets/fonts/ into the product's own public or static folder and point each font source below at the path the site serves it from; a built site does not serve .claude/skills/ */\n"
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
    assert r.returncode == 0 and r.stdout.splitlines()[0] == "would write 18 generated files into .claude/skills/acme-brand/ (version 1.1)", r.stdout + r.stderr
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


def set_weight_class(font, value: int) -> None:
    """Store `value` as the OS/2 usWeightClass of a font file, in place."""
    from helpers import fonttools
    r = fonttools("import sys\nfrom fontTools.ttLib import TTFont\nf = TTFont(sys.argv[1])\nf['OS/2'].usWeightClass = int(sys.argv[2])\nf.save(sys.argv[1])\n", str(font), str(value))
    assert r.returncode == 0, r.stderr


def test_a_font_that_stores_an_invalid_weight_class_gets_font_weight_400(pack):
    """OS/2 usWeightClass 0 (or one over 1000) is no weight: fontcheck takes it as 400 and the kit's @font-face never says `font-weight: 0`."""
    with_font(pack, fontcheck=False)
    font = pack / "assets" / "fonts" / TEST_FONT.name
    for stored in (0, 1001, 65535):
        set_weight_class(font, stored)
        r = bc("fontcheck", "--lang", "en", "--no-platform", project=pack)
        assert r.returncode == 0, r.stdout + r.stderr
        r = build(pack)
        assert r.returncode == 0, (stored, r.stdout + r.stderr)
        assert (kit_of(pack) / "snippets" / "fonts.css").read_text(encoding="utf-8") == FONT_FACE, stored
        assert fonts_row(pack)["status"] == "pass"
    set_weight_class(font, 1000)                                                    # the edge of the range is a weight
    assert bc("fontcheck", "--lang", "en", "--no-platform", project=pack).returncode == 0
    assert build(pack).returncode == 0
    assert "  font-weight: 1000;\n" in (kit_of(pack) / "snippets" / "fonts.css").read_text(encoding="utf-8")


def test_a_fontcheck_report_with_a_weight_that_is_no_weight_copies_no_font(pack):
    """A report written before fontcheck took 0 as 400 is still current while the fonts are unchanged: the kit does not take its weight 0 (or 1001, or `true`, or a float) for a weight."""
    with_font(pack)
    path = pack / "assets" / "_checks" / "fontcheck.json"
    row = "licence:assets/fonts/TestFont-subset.ttf"
    for stored in (0, -1, 1001, True, 400.0, "400", None):
        mutate_json(path, lambda d: next(r for r in d["results"] if r["id"] == row).__setitem__("weight", stored))
        r = build(pack)
        assert r.returncode == 0, (stored, r.stdout + r.stderr)
        assert kit_files(pack) == KIT_FILES and not (kit_of(pack) / "snippets" / "fonts.css").exists(), stored
        assert kit_json(pack)["fonts"]["not_copied"] == [{"file": "assets/fonts/TestFont-subset.ttf",
                                                          "reason": "the fontcheck report has no weight or style for it: run `brand-creator fontcheck` again"}], stored
    for stored in (1, 1000):                                                        # the edges are weights
        mutate_json(path, lambda d: next(r for r in d["results"] if r["id"] == row).__setitem__("weight", stored))
        assert build(pack).returncode == 0
        assert f"  font-weight: {stored};\n" in (kit_of(pack) / "snippets" / "fonts.css").read_text(encoding="utf-8")


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
    assert set(kj["sources"]) == {"state_sha", "tokens", "tokens_css", "rules", "facts", "motion", "logos", "fonts", "pages"}
    assert kj["sources"]["fonts"] is None and kj["fonts"] == {"copied": [], "not_copied": []}                  # Acme has no font
    assert kj["sources"]["pages"] is None and kj["reference_pages"] == []                                      # and no site/site.json
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
             (lambda d: d.__setitem__("outputs", {"SKILL.md": 7}), "cannot be compared", "SKILL.md"),
             (lambda d: d.__setitem__("outputs", {"SKILL.md": "not-a-sha"}), "cannot be compared", "SKILL.md"),      # a string that is not 64 hex characters is no sha256 either
             (lambda d: d.__setitem__("outputs", {"SKILL.md": "0" * 63}), "cannot be compared", "SKILL.md"),
             (lambda d: d.__setitem__("outputs", {"SKILL.md": "g" * 64}), "cannot be compared", "SKILL.md"))
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


def test_check_names_the_fonts_among_the_causes_of_a_kit_made_from_another_brand(pack):
    """sources.fonts (the font files, their licence texts and the fontcheck report) moves the kit state too, so the message names the fonts."""
    with_font(pack)
    assert build(pack).returncode == 0
    assert "kit:state" not in check_rows(pack)
    mutate(pack / "assets" / "fonts" / "OFL.txt", "SIL Open Font License", "SIL Open Font License, as shipped")      # a licence text is a source of the fonts, and of nothing else
    row = check_rows(pack)["kit:state"]
    assert row["status"] == "skipped"
    assert row["detail"] == ("not verified: the name, rules, facts, tokens, logos, band drawings, fonts, reference pages, masters or motion spec changed since the kit report; "
                             "run `brand-creator kit build --yes` again")
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
# the fifteen files of a build hold no motion file. The spec is written as test_adapters.py writes it; its tokens (two durations and a curve) are built first.
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
    assert r.returncode == 0 and r.stdout.splitlines()[0] == "would write 18 generated files into .claude/skills/acme-brand/ (version 1.1)", r.stdout + r.stderr
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
    assert written_row(pack)["detail"] == "18 generated files: 18 written, 0 unchanged, 0 moved to removed-2026-10-17/; version 1.1"
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


SECRET = b"<!doctype html><title>SECRET-OUTSIDE</title>"


def link_layout(p, outside, name):
    """The layout of a path that is checked as one file and read as another: `L` is a link to deep/dir, so `L/../<name>` names deep/<name> (a normal file inside the project), but
    the plain path <name> is a link to `outside`, a file beyond the project."""
    from helpers import symlink_or_skip
    (p / "deep" / "dir").mkdir(parents=True)
    (p / "deep" / name).write_bytes(b"<!doctype html><title>inside</title>")
    outside.write_bytes(SECRET)
    symlink_or_skip(p / name, outside)
    symlink_or_skip(p / "L", p / "deep" / "dir")


def nothing_secret_in(p) -> None:
    """No file of the project's .claude/ folder (where the kit goes) holds the outside file's bytes."""
    found = [f for f in (p / ".claude").rglob("*") if f.is_file() and SECRET in f.read_bytes()] if (p / ".claude").exists() else []
    assert found == []


def test_a_proof_page_read_through_a_link_that_leaves_the_project_is_never_copied(pack, tmp_path):
    """The page `L/../E` (L a link to deep/dir, E a link to a file outside the project, deep/E a normal file) must not make the kit read E as if the check had been made on deep/E.
    The kit mirrors the plain path E, so E is what is checked and what is read, and the outside bytes never reach the kit.
    This is the real layout, and it does not tell the fix apart: `confine` takes `..` out of the path before it follows a link, so `L/../E` is E at the very first check and is refused
    with or without the two later checks (the plain path checked again in `_proof_page`, and the page read from the path `confine` returns in `motion_files`). The test below, which
    makes `confine` follow links first, is the one that tells them apart: it fails when both are taken out (either one alone still refuses the page)."""
    moving(pack)
    link_layout(pack, tmp_path / "outside.html", "E")
    mutate_json(pack / "motion" / "proof.json", lambda d: d["cases"][1].__setitem__("page", "L/../E"))
    for args in (("--yes",), ("--plan",)):
        r = bc("kit", "build", *args, project=pack)
        assert r.returncode == 2, (args, r.stdout, r.stderr)
        assert "outside the project" in r.stderr and "demo-page" in r.stderr and "Traceback" not in r.stderr
        assert b"SECRET-OUTSIDE" not in r.stdout.encode() and not (pack / ".claude").exists() and not (pack / "assets" / "_checks" / "kit.json").exists()
    mutate_json(pack / "motion" / "proof.json", lambda d: d["cases"][1].__setitem__("page", "E"))        # the plain path is refused too, whoever names it
    r = build(pack)
    assert r.returncode == 2 and "outside the project" in r.stderr and not (pack / ".claude").exists()
    nothing_secret_in(pack)


def test_a_proof_page_is_read_from_the_path_that_was_checked_whichever_way_a_link_is_resolved(pack, tmp_path, monkeypatch):
    """`confine` takes `..` out of a path before it follows a link, so `L/../E` is E there. If it ever followed links first (as the OS does when it opens the path), `L/../E`
    would pass as deep/E while the kit went on to read the plain path E. The page is checked again as the plain path and read from the checked path, so it cannot."""
    import os
    from pathlib import Path

    import _common
    import kitlib
    moving(pack)
    link_layout(pack, tmp_path / "outside.html", "E")
    mutate_json(pack / "motion" / "proof.json", lambda d: d["cases"][1].__setitem__("page", "L/../E"))

    def links_first(p):
        p, tail = Path(p), []
        while not p.exists() and p != p.parent:
            tail.append(p.name)
            p = p.parent
        return Path(os.path.realpath(p)).joinpath(*reversed(tail))      # no lexical clean-up of `..` first

    monkeypatch.setattr(_common, "_realpath_lenient", links_first)
    assert _common.confine(pack, "L/../E", read=True) == (pack / "deep" / "E").resolve()      # the premise: the raw page is deep/E, inside the project
    with pytest.raises(_common.CliError) as e:
        kitlib.motion_files(pack)
    assert e.value.code == 2 and "outside the project" in e.value.message and "demo-page" in e.value.message


def test_a_band_drawing_read_through_a_link_that_leaves_the_project_is_never_copied(pack, tmp_path):
    """The same layout for a band drawing of qa/rules.json (the drawing is named by its plain path, and that is the file read)."""
    link_layout(pack, tmp_path / "outside.svg", "D.svg")
    rules = {"schema": 1, "bands": [{"name": "small", "max_px": 32, "drawing": "assets/logo/grid-mark.svg"}, {"name": "large", "drawing": "L/../D.svg"}]}
    (pack / "qa" / "rules.json").write_text(json.dumps(rules), encoding="utf-8")
    r = build(pack)
    assert r.returncode == 2 and "outside the project" in r.stderr and "Traceback" not in r.stderr and not (pack / ".claude").exists()
    rules["bands"][1]["drawing"] = "D.svg"                                    # written plainly, it is the same link to the outside, refused the same way
    (pack / "qa" / "rules.json").write_text(json.dumps(rules), encoding="utf-8")
    r = build(pack)
    assert r.returncode == 2 and "outside the project" in r.stderr and not (pack / ".claude").exists()
    nothing_secret_in(pack)


@pytest.mark.parametrize("rel", ["assets/tokens/tokens.css", "assets/tokens/tokens.json", "assets/logo/mark.svg", "assets/fonts/TestFont-subset.ttf", "assets/fonts/OFL.txt",
                                 "motion/motion.json", "motion/SPEC.md"])
def test_every_kind_of_file_the_kit_copies_is_refused_when_it_is_a_link_that_leaves_the_project(pack, tmp_path, rel):
    """The audit of every file the kit copies (the tokens, a logo, a font, its licence text, the motion spec and its hand-off): each is read from the path `confine` checked, so a
    project file that is a link to a file beyond the project is exit 2 for the plan and the build, and nothing is written."""
    from helpers import symlink_or_skip
    if rel.startswith("assets/fonts/"):
        with_font(pack)
    if rel.startswith("motion/"):
        moving(pack)
    far = tmp_path / "far-file"
    far.write_bytes((pack / rel).read_bytes())
    (pack / rel).unlink()
    symlink_or_skip(pack / rel, far)
    for args in (("--yes",), ("--plan",)):
        r = bc("kit", "build", *args, project=pack)
        assert r.returncode == 2, (rel, args, r.stdout, r.stderr)
        assert "outside the project" in r.stderr and "Traceback" not in r.stderr
    assert not kit_of(pack).exists() and not (pack / "assets" / "_checks" / "kit.json").exists()


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


def test_known_rule_ids_refuses_a_site_record_whose_choices_are_not_a_list_and_never_crashes(pack):
    import kitlib
    from _common import CliError
    site = {"schema": 1, "approved": "2026-10-17 (test)", "round": 1, "hero": "a", "pages": [], "choices": [{"id": "c1", "text": "one call to action", "tag": "rule", "source": "DECISIONS.md"}]}
    (pack / "site").mkdir()
    f = pack / "site" / "site.json"
    f.write_text(json.dumps(site), encoding="utf-8")
    assert kitlib.known_rule_ids(pack) == ["site:c1"]
    for bad in (None, "c1", 7, {"c1": {}}, True):
        mutate_json(f, lambda d: d.__setitem__("choices", bad))
        with pytest.raises(CliError) as e:
            kitlib.known_rule_ids(pack)
        assert e.value.code == 2 and "site/site.json" in e.value.message and "choices" in e.value.message, (bad, e.value.message)
    mutate_json(f, lambda d: d.pop("choices"))                                   # no choices at all is a record with none
    assert kitlib.known_rule_ids(pack) == []


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
    assert r.returncode == 0 and r.stdout.splitlines()[0] == "would write 16 generated files into .claude/skills/acme-brand/ (version 1.2)", r.stdout + r.stderr
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


# ---------------------------------------------------------------- snippets/logo.html: the logo in light and dark
# Acme has three marks with a dark twin (grid-mark, mark, wordmark) and one without (mark-animated); grid-mark-master.png is not an SVG. The snippet is written out by hand.
LOGO_HEAD = "<!-- generated by brand-creator: the logo in light and dark, switched as tokens.css switches them; paths are relative to this file -->"
LOGO_NOTE = "<!-- in a product: copy brand/assets/logo/ into the product's own public or static folder and point each image below at the path the site serves it from; a built site does not serve .claude/skills/ -->"
LOGO_STYLE = ("<style>\n"
              "  /* light shows by default; dark shows where tokens.css switches to dark; only display: none is used, so the page keeps the display value it chose */\n"
              '  :root[data-theme="light"] .brand-logo--dark { display: none; }\n'
              '  :root[data-theme="dark"] .brand-logo--light { display: none; }\n'
              "  @media not all and (prefers-color-scheme: dark) {\n"
              '    :root:not([data-theme="dark"]) .brand-logo--dark { display: none; }\n'
              "  }\n"
              "  @media (prefers-color-scheme: dark) {\n"
              '    :root:not([data-theme="light"]) .brand-logo--light { display: none; }\n'
              "  }\n"
              "</style>\n")


def logo_pair(name, alt="Acme"):
    return (f"<!-- {name} -->\n"
            f'<img class="brand-logo brand-logo--light" src="../brand/assets/logo/{name}.svg" alt="{alt}">\n'
            f'<img class="brand-logo brand-logo--dark" src="../brand/assets/logo/{name}-dark.svg" alt="{alt}">\n')


ACME_LOGO_HTML = (LOGO_HEAD + "\n" + LOGO_NOTE + "\n" + LOGO_STYLE + "\n" + logo_pair("grid-mark") + "\n" + logo_pair("mark") + "\n"
                  "<!-- mark-animated -->\n"
                  '<img class="brand-logo" src="../brand/assets/logo/mark-animated.svg" alt="Acme">\n'
                  "\n" + logo_pair("wordmark"))


def test_the_logo_snippet_pairs_each_mark_with_its_dark_twin_and_switches_like_tokens_css(pack):
    r = build(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    snippet = (kit_of(pack) / "snippets" / "logo.html").read_text(encoding="utf-8")
    assert snippet == ACME_LOGO_HTML
    assert '<img class="brand-logo brand-logo--light" src="../brand/assets/logo/mark.svg" alt="Acme">\n' \
           '<img class="brand-logo brand-logo--dark" src="../brand/assets/logo/mark-dark.svg" alt="Acme">\n' in snippet
    css = (kit_of(pack) / "brand" / "assets" / "tokens" / "tokens.css").read_text(encoding="utf-8")
    for selector in (':root[data-theme="dark"]', ':root:not([data-theme="light"])'):              # the two selectors tokens.css switches the dark colours with
        assert selector in snippet and selector in css, selector
    assert "prefers-color-scheme: dark" in snippet and "prefers-color-scheme: dark" in css
    for src in re.findall(r'src="([^"]+)"', snippet):                                              # every path is relative to the snippet and lands on a file of the kit
        assert (kit_of(pack) / "snippets" / src).resolve().is_file(), src
        assert filecmp.cmp(pack / "assets" / "logo" / src.rsplit("/", 1)[1], kit_of(pack) / "snippets" / src, shallow=False)
    assert "snippets/logo.html" in kit_json(pack)["generated"] and file_sha(kit_of(pack) / "snippets" / "logo.html") == kit_json(pack)["generated"]["snippets/logo.html"]
    assert "- `snippets/logo.html`" in (kit_of(pack) / "SKILL.md").read_text(encoding="utf-8")
    assert "snippets/logo.html" in report(pack, "kit")["outputs"]
    first = kit_state(pack)
    assert build(pack).returncode == 0 and kit_state(pack) == first and kit_json(pack)["version"] == "1.1"       # a second build writes nothing


def test_a_mark_without_a_dark_twin_is_shown_in_both_themes(pack):
    assert build(pack).returncode == 0
    snippet = (kit_of(pack) / "snippets" / "logo.html").read_text(encoding="utf-8")
    assert snippet.count('<img class="brand-logo" src="../brand/assets/logo/mark-animated.svg" alt="Acme">\n') == 1
    assert "mark-animated-dark" not in snippet and snippet.count("mark-animated") == 2                                   # its comment and its one image
    hiding = [ln.split("{")[0].strip() for ln in snippet.splitlines() if "{ display: none; }" in ln]
    assert len(hiding) == 4 and all(sel.endswith((".brand-logo--light", ".brand-logo--dark")) for sel in hiding)          # no rule can hide the plain class
    style = snippet.split("<style>")[1].split("</style>")[0]
    assert [b.strip() for b in re.findall(r"\{([^{}]*)\}", style)] == ["display: none;"] * 4                                  # every declaration there is: no size, colour or spacing


def test_a_dark_twin_taken_away_turns_the_pair_into_a_single_image(pack):
    assert build(pack).returncode == 0
    (pack / "assets" / "logo" / "wordmark-dark.svg").unlink()
    assert build(pack).returncode == 0
    snippet = (kit_of(pack) / "snippets" / "logo.html").read_text(encoding="utf-8")
    assert snippet.endswith("<!-- wordmark -->\n" '<img class="brand-logo" src="../brand/assets/logo/wordmark.svg" alt="Acme">\n')
    assert "wordmark-dark" not in snippet and logo_pair("mark") in snippet and kit_json(pack)["version"] == "1.2"


def test_the_logo_snippet_names_the_brand_in_the_alt_and_quotes_what_html_needs_quoted():
    import kitlib
    got = kitlib.logo_html('Acme "Q" & <Co>', ["assets/logo/my mark.svg", "assets/logo/my mark-dark.svg", "assets/logo/b--> x.svg", "assets/logo/z-dark.svg", "assets/logo/m.png"])
    text = got.decode("utf-8")
    assert text.startswith(LOGO_HEAD + "\n" + LOGO_NOTE + "\n<style>\n")
    alt = 'alt="Acme &quot;Q&quot; &amp; &lt;Co&gt;"'
    assert (f'<!-- my mark -->\n<img class="brand-logo brand-logo--light" src="../brand/assets/logo/my%20mark.svg" {alt}>\n'
            f'<img class="brand-logo brand-logo--dark" src="../brand/assets/logo/my%20mark-dark.svg" {alt}>\n') in text
    assert f'<!-- b--&gt; x -->\n<img class="brand-logo" src="../brand/assets/logo/b--%3E%20x.svg" {alt}>\n' in text        # nothing in a name can end the comment or the attribute
    assert text.index("<!-- b--&gt; x -->") < text.index("<!-- my mark -->")                                               # sorted by name
    assert "z-dark" not in text and "m.png" not in text and text.count("<img") == 3                                        # a dark file with no light one, and a PNG, are left out


def test_a_logo_folder_with_nothing_to_show_gets_no_snippet():
    import kitlib
    assert kitlib.logo_html("Acme", []) is None
    assert kitlib.logo_html("Acme", ["assets/logo/mark.png", "assets/logo/mark-dark.svg"]) is None


# ---------------------------------------------------------------- the owner's files: scaffolded once, never overwritten
# EXTENDING.md, voice.md, visual.md, golden-rules.md and recipes/web-page.md come from templates/kit/ when the file is absent. They are the owner's, not generated:
# kit.json lists them under `owned`, and kit_files() (the generated files) leaves them out.

def owned_row(p) -> str:
    return next(r for r in report(p, "kit")["results"] if r["id"] == "kit:owned")["detail"]


def owner_state(p) -> dict:
    return {rel: (file_sha(kit_of(p) / rel), (kit_of(p) / rel).stat().st_mtime_ns) for rel in OWNER_FILES}


def test_the_first_build_scaffolds_the_owner_files_once(pack):
    r = build(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert kit_files(pack) == KIT_FILES and owner_files(pack) == OWNER_FILES
    kd = kit_of(pack)
    ext = (kd / "EXTENDING.md").read_text(encoding="utf-8")
    assert ext.startswith("# Extending the Acme brand kit\n") and "`.claude/skills/acme-brand/`" in ext and "{{" not in ext and "[[fill" not in ext    # complete: no marker left
    for needle in ("`brand-creator kit build --yes`", "`recipes/`", "`[rule: <id>]`", "`[example]`", "/brand-creator:brand-adopt", "`brand-creator kit status --repo <folder>`",
                   "`var(--name)`", "`{dotted.path}`", "Never edit one", "the next build stops on a hand edit"):
        assert needle in ext, needle
    for name, head in (("voice.md", "# Acme voice"), ("visual.md", "# Acme visual"), ("golden-rules.md", "# Acme golden rules")):
        text = (kd / name).read_text(encoding="utf-8")
        assert text.startswith(head + "\n\n") and text.count("[[fill: ") == 1 and "{{" not in text, name
        assert re.search(r"^\[\[fill: [^\[\]]+\]\]$", text, re.M), name                                              # one marker, its note has no square bracket
    assert "[[fill: up to ten rules, each tagged with a rule id from rules.json or as an example]]" in (kd / "golden-rules.md").read_text(encoding="utf-8")
    assert (kd / "recipes" / "web-page.md").read_text(encoding="utf-8").startswith("# Web page\n")
    kj = kit_json(pack)
    assert sorted(kj["owned"]) == OWNER_FILES and all(file_sha(kd / rel) == sha for rel, sha in kj["owned"].items())
    assert not set(OWNER_FILES) & set(kj["generated"]) and not set(OWNER_FILES) & set(report(pack, "kit")["outputs"])    # not generated: check's kit:file never reads them
    assert owned_row(pack) == "5 owner files scaffolded this run, 0 kept as they are"
    skill = (kd / "SKILL.md").read_text(encoding="utf-8")
    assert "Yours to extend; how: `EXTENDING.md`. A build writes each of these once and never overwrites or moves it." in skill
    assert all(f"- `{rel}`" in skill for rel in OWNER_FILES)
    assert skill.index("- `brand/assets/tokens/tokens.css`") < skill.index("Yours to extend") < skill.index("## Colour")
    # a second build has nothing to scaffold: the plan names none, and nothing is touched
    owner_before, kit_before = owner_state(pack), kit_state(pack)
    r = bc("kit", "build", "--plan", project=pack)
    assert r.returncode == 0 and "scaffold " not in r.stdout
    assert build(pack).returncode == 0
    assert owned_row(pack) == "0 owner files scaffolded this run, 5 kept as they are"
    assert owner_state(pack) == owner_before and kit_state(pack) == kit_before and kit_json(pack)["version"] == "1.1"


def test_the_kit_skill_works_beside_the_web_skill_and_the_recipe_arrives_whole(pack):
    """The kit test baseline: the brand skill replaced the owner's web skill, and the page linked brand files inside the kit's own folder. SKILL.md says it works beside the web skill and where
    the files go in a product; the scaffolded recipe is the seven steps, complete (no fill marker, no placeholder left)."""
    assert build(pack).returncode == 0
    kd = kit_of(pack)
    skill = (kd / "SKILL.md").read_text(encoding="utf-8")
    line = ("It works beside your web-design skill, never instead of it: load both when you build a page. A built site does not serve this folder, so copy the files you use from `brand/` "
            "into the product's own public or static folder and link them from there; `recipes/web-page.md` has the steps.")
    assert skill.count(line) == 1 and skill.index("This folder is a brand kit.") < skill.index(line) < skill.index("Generated. Never edit these here")
    recipe = (kd / "recipes" / "web-page.md").read_text(encoding="utf-8")
    assert re.findall(r"(?m)^(\d+)\. ", recipe) == ["1", "2", "3", "4", "5", "6", "7"] and "[[fill" not in recipe and "{{" not in recipe
    assert "into the product's own public or static folder and link them from there" in recipe and "`[data-sample]`" in recipe and "page-check" in recipe


def test_an_owner_file_is_never_overwritten_and_its_change_moves_the_version(pack):
    assert build(pack).returncode == 0
    f = kit_of(pack) / "voice.md"
    first = kit_json(pack)
    mutate(f, "# Acme voice", "# Acme voice, in my words")
    mine = f.read_bytes()
    r = build(pack)
    assert r.returncode == 0, r.stdout + r.stderr                       # an owner edit is no hand edit: the build neither stops nor moves anything
    assert f.read_bytes() == mine and not list(pack.glob("removed-*"))
    kj = kit_json(pack)
    assert kj["version"] == "1.2" and kj["owned"]["voice.md"] == file_sha(f) and kj["owned"]["voice.md"] != first["owned"]["voice.md"]
    assert kj["content_sha"] != first["content_sha"] and kj["generated"] == first["generated"] | {"SKILL.md": kj["generated"]["SKILL.md"]}
    assert "Kit version 1.2 (kit.json)." in (kit_of(pack) / "SKILL.md").read_text(encoding="utf-8")
    assert owned_row(pack) == "0 owner files scaffolded this run, 5 kept as they are"
    assert check_rows(pack)["kit:file"]["status"] == "pass"             # check does not gate an owner's file
    assert build(pack).returncode == 0 and kit_json(pack)["version"] == "1.2"        # the edit is now part of the record: the same content keeps the version
    for n, rel in enumerate(OWNER_FILES, start=3):                      # every owner file counts, a recipe and EXTENDING.md too
        f = kit_of(pack) / rel
        f.write_text(f.read_text(encoding="utf-8") + "\nmine\n", encoding="utf-8")
        assert build(pack).returncode == 0 and kit_json(pack)["version"] == f"1.{n}", rel
        assert f.read_text(encoding="utf-8").endswith("\nmine\n") and kit_json(pack)["owned"][rel] == file_sha(f)


def test_a_deleted_owner_file_is_scaffolded_again(pack):
    assert build(pack).returncode == 0
    kd = kit_of(pack)
    scaffolds = {rel: (kd / rel).read_bytes() for rel in OWNER_FILES}
    (kd / "voice.md").unlink()
    shutil.rmtree(kd / "recipes")
    r = bc("kit", "build", "--plan", project=pack)
    assert r.returncode == 0 and sorted(re.findall(r"^scaffold (\S+) ", r.stdout, re.M)) == ["recipes/web-page.md", "voice.md"] and not (kd / "voice.md").exists()
    assert build(pack).returncode == 0
    assert {rel: (kd / rel).read_bytes() for rel in OWNER_FILES} == scaffolds
    assert owned_row(pack) == "2 owner files scaffolded this run, 3 kept as they are"
    assert kit_json(pack)["version"] == "1.1"                           # the same bytes as before: the content has not changed
    (kd / "visual.md").unlink()
    assert build(pack).returncode == 0 and owned_row(pack) == "1 owner file scaffolded this run, 4 kept as they are"


def test_a_changed_scaffold_leaves_an_owner_file_that_is_already_in_the_kit(pack, plugin_copy):
    r = bc("kit", "build", "--yes", project=pack, plugin=plugin_copy)
    assert r.returncode == 0, r.stdout + r.stderr
    f = kit_of(pack) / "golden-rules.md"
    first = f.read_bytes()
    mutate(plugin_copy / "templates" / "kit" / "golden-rules.md", "The few rules", "Some other words about the rules")
    r = bc("kit", "build", "--yes", project=pack, plugin=plugin_copy)
    assert r.returncode == 0, r.stdout + r.stderr
    assert f.read_bytes() == first and kit_json(pack)["version"] == "1.1" and owned_row(pack) == "0 owner files scaffolded this run, 5 kept as they are"
    f.unlink()                                                          # absent: the scaffold of today is written
    r = bc("kit", "build", "--yes", project=pack, plugin=plugin_copy)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "Some other words about the rules" in f.read_text(encoding="utf-8") and kit_json(pack)["version"] == "1.2"


def test_the_kit_scaffolds_keep_their_placeholder_guard(pack, plugin_copy):
    tpl = plugin_copy / "templates" / "kit" / "voice.md"
    original = mutate(tpl, "# {{brand}} voice", "# {{brand}} voice {{nope}}")
    for args in (("--yes",), ("--plan",)):
        r = bc("kit", "build", *args, project=pack, plugin=plugin_copy)
        assert r.returncode == 2 and "templates/kit/voice.md has placeholders this version does not know: {{nope}}" in r.stderr, (args, r.stdout + r.stderr)
        assert not (pack / ".claude").exists() and not (pack / "assets" / "_checks" / "kit.json").exists()          # nothing is written
    for odd in ("{{Brand}}", "{{ brand }}", "{{no_pe}}", "{{}}"):         # a name the pass would not have matched is refused too, not written into a file that is never overwritten
        tpl.write_text(original.replace("# {{brand}} voice", "# {{brand}} voice " + odd), encoding="utf-8")
        r = bc("kit", "build", "--yes", project=pack, plugin=plugin_copy)
        assert r.returncode == 2 and odd in r.stderr and not (pack / ".claude").exists(), (odd, r.stdout + r.stderr)
    def into_heading(odd: str) -> str:
        return original.replace("# {{brand}} voice", "# {{brand}} voice " + odd, 1)

    for text, said in ((into_heading("{{no\npe}}"), "{{no\\npe}}"),               # a placeholder across lines is a placeholder this version does not know
                       (into_heading("{{brand"), "templates/kit/voice.md has"),    # never closed: it runs to the next }}, so it is refused as one
                       (original + "\n{{brand", "that is no placeholder"),         # never closed, and nothing after it to close it
                       (into_heading("brand}}"), "that is no placeholder")):       # never opened
        tpl.write_text(text, encoding="utf-8")
        for args in (("--yes",), ("--plan",)):
            r = bc("kit", "build", *args, project=pack, plugin=plugin_copy)
            assert r.returncode == 2 and said in r.stderr and "templates/kit/voice.md" in r.stderr, (text, args, r.stdout + r.stderr)
            assert not (pack / ".claude").exists() and not (pack / "assets" / "_checks" / "kit.json").exists(), text              # nothing is written
    tpl.write_text(original, encoding="utf-8")
    r = bc("kit", "build", "--yes", project=pack, plugin=plugin_copy)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (kit_of(pack) / "voice.md").read_text(encoding="utf-8").startswith("# Acme voice\n")
    tpl.unlink()                                                        # a scaffold the plugin lacks is a broken plugin, not a kit to write without it
    (kit_of(pack) / "voice.md").unlink()
    r = bc("kit", "build", "--yes", project=pack, plugin=plugin_copy)
    assert r.returncode == 3 and "templates/kit/voice.md is missing" in r.stderr and not (kit_of(pack) / "voice.md").exists()


def test_the_scaffolds_fill_their_placeholders_in_one_pass(pack):
    assert bc("state", "--set", "name=Acme {{skill}}", project=pack).returncode == 0
    r = build(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    kd = kit_of(pack)
    assert (kd / "voice.md").read_text(encoding="utf-8").startswith("# Acme {{skill}} voice\n")            # the brand's name is written as it is, never read for placeholders again
    ext = (kd / "EXTENDING.md").read_text(encoding="utf-8")
    assert ext.startswith("# Extending the Acme {{skill}} brand kit\n") and "`.claude/skills/acme-brand/`" in ext


def test_something_that_is_no_file_where_an_owner_file_belongs_stops_the_build_and_is_left_alone(pack):
    kd = kit_of(pack)
    (kd / "voice.md").mkdir(parents=True)
    (kd / "voice.md" / "mine.txt").write_text("mine\n", encoding="utf-8")
    for args in ((), ("--replace",)):                                   # --replace moves generated files and links; a folder where an owner's file belongs is never moved
        r = build(pack, *args)
        assert r.returncode == 1 and ".claude/skills/acme-brand/voice.md is not a file" in r.stderr, r.stdout + r.stderr
        assert (kd / "voice.md" / "mine.txt").read_text(encoding="utf-8") == "mine\n" and not (pack / "assets" / "_checks" / "kit.json").exists()
        assert not list(pack.glob("removed-*")) and not (kd / "kit.json").exists()
    shutil.rmtree(kd / "voice.md")
    # the folder an owner file belongs in: a file at `recipes` stops the build before anything is written, and --plan does not promise a scaffold under it
    (kd / "recipes").write_text("mine\n", encoding="utf-8")
    for args in (("--yes",), ("--yes", "--replace"), ("--plan",)):
        r = bc("kit", "build", *args, project=pack)
        assert r.returncode == 1, (args, r.stdout + r.stderr)
        assert ".claude/skills/acme-brand/recipes/web-page.md is not a file" in r.stderr and ".claude/skills/acme-brand/recipes is not a folder" in r.stderr, (args, r.stderr)
        assert "scaffold " not in r.stdout and sorted(f.name for f in kd.iterdir()) == ["recipes"], (args, r.stdout)         # nothing else was written: no SKILL.md, no kit.json
        assert not (pack / "assets" / "_checks" / "kit.json").exists() and not list(pack.glob("removed-*"))
    assert (kd / "recipes").read_text(encoding="utf-8") == "mine\n"                                                          # left as it was
    (kd / "recipes").unlink()                                           # the advice works: move it away, then build again
    r = build(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert kit_json(pack)["version"] == "1.1" and owner_files(pack) == OWNER_FILES and kit_files(pack) == KIT_FILES


def test_a_file_where_an_owner_files_folder_belongs_keeps_the_report_and_the_kit_of_the_last_build(pack):
    assert build(pack).returncode == 0
    kd = kit_of(pack)
    shutil.rmtree(kd / "recipes")
    (kd / "recipes").write_text("mine\n", encoding="utf-8")
    rep_before, kit_before, state_before = (pack / "assets" / "_checks" / "kit.json").read_bytes(), (kd / "kit.json").read_bytes(), kit_state(pack)
    r = build(pack)
    assert r.returncode == 1 and "recipes is not a folder" in r.stderr, r.stdout + r.stderr
    assert (pack / "assets" / "_checks" / "kit.json").read_bytes() == rep_before and (kd / "kit.json").read_bytes() == kit_before and kit_state(pack) == state_before   # the report keeps its outputs and version
    assert report(pack, "kit")["outputs"] and report(pack, "kit")["kit_version"] == "1.1"
    (kd / "recipes").unlink()
    assert build(pack).returncode == 0 and kit_json(pack)["version"] == "1.1" and owner_files(pack) == OWNER_FILES        # no hand edit is left behind: the next build is clean
    assert check_rows(pack)["kit:file"]["status"] == "pass"


def test_kit_json_must_list_the_five_scaffolded_owner_files(pack):
    import kitlib
    from _common import CliError
    assert build(pack).returncode == 0
    assert sorted(kitlib.load(pack)["owned"]) == OWNER_FILES
    f = kit_of(pack) / "kit.json"
    for where, change, needle in (("a path that is no owner file", lambda d: d["owned"].__setitem__("brand/notes.md", "0" * 64), "owned.brand/notes.md: not an owner file"),
                                  ("an owner file left out", lambda d: d["owned"].pop("voice.md"), "owned.voice.md: missing"),
                                  ("a hash that is none", lambda d: d["owned"].__setitem__("voice.md", "x"), "owned.voice.md: must be a sha256"),
                                  ("no owned key", lambda d: d.pop("owned"), "owned: missing"),
                                  ("a list", lambda d: d.__setitem__("owned", []), "owned: must be an object")):
        good = f.read_bytes()
        mutate_json(f, change)
        with pytest.raises(CliError) as e:
            kitlib.load(pack)
        assert e.value.code == 2 and needle in e.value.message, where
        f.write_bytes(good)


# ---------------------------------------------------------------- kit check, part 1: files, links, fill markers, versions, sources, owner files
# `kit check` writes the report kit-check. A fresh kit fails it on the fill markers of the owner's files; every other row of a fresh kit passes. The Acme kit holds eight Markdown, HTML and CSS
# files (SKILL.md, EXTENDING.md, voice.md, visual.md, golden-rules.md, recipes/web-page.md, snippets/logo.html and brand/assets/tokens/tokens.css), and seven relative links, all in
# snippets/logo.html: an <img src> for each of its seven logo images (grid-mark, mark and wordmark with their dark twins, and mark-animated alone).
ALL_PASS = {"kit:files": "pass", "kit:links": "pass", "kit:fill": "pass", "kit:versions": "pass", "kit:plugin": "pass", "kit:sources": "pass", "kit:owned": "pass",
            "kit:tags": "pass", "kit:numbers": "pass"}
FRESH_LINKS = 7
FRESH_FILES = 8
OUTSIDE_KIT = "points outside the kit: it will not resolve in a product repository"


def kit_check(p):
    return bc("kit", "check", project=p)


def check_report_rows(p) -> dict:
    return {r["id"]: r for r in report(p, "kit-check")["results"]}


def statuses(p) -> dict:
    return {i: r["status"] for i, r in check_report_rows(p).items()}


def fill_owned(kit):
    """`mutate` each `[[fill: ...]]` marker of the owner's files into plain text with a tag, as an owner fills them in."""
    for rel in OWNER_FILES:
        f = kit / rel
        for marker in re.findall(r"\[\[fill:[^\]]*\]\]", f.read_text(encoding="utf-8")):
            mutate(f, marker, "Keep it short. [example]")


def filled_kit(p):
    """A kit whose owner files are filled in and recorded by a second build, so that the kit check has nothing to say about them (the owner's edit moved the version to 1.2)."""
    assert build(p).returncode == 0
    fill_owned(kit_of(p))
    r = build(p)
    assert r.returncode == 0, r.stdout + r.stderr
    assert kit_json(p)["version"] == "1.2"


def test_a_fresh_kit_fails_on_its_fill_markers_until_the_owner_files_are_filled(pack):
    assert build(pack).returncode == 0
    r = kit_check(pack)
    assert r.returncode == 1, r.stdout + r.stderr
    assert report(pack, "kit-check")["status"] == "fail" and "[FAIL] kit:fill" in r.stdout
    assert statuses(pack) == {**ALL_PASS, "kit:fill": "fail"}
    assert check_report_rows(pack)["kit:fill"]["detail"].startswith("3 fill marker(s) left: golden-rules.md:5, visual.md:5, voice.md:5;")
    voice = kit_of(pack) / "voice.md"
    marker = re.search(r"\[\[fill:[^\]]*\]\]", voice.read_text(encoding="utf-8")).group(0)
    mutate(voice, marker, "Plain and short. [example]")                      # one filled in: two to go
    assert kit_check(pack).returncode == 1
    assert check_report_rows(pack)["kit:fill"]["detail"].startswith("2 fill marker(s) left: golden-rules.md:5, visual.md:5;")
    fill_owned(kit_of(pack))
    r = kit_check(pack)
    assert r.returncode == 0, r.stdout + r.stderr                             # no fill marker left: a warning about the owner's edits is no failure
    assert report(pack, "kit-check")["status"] == "pass" and statuses(pack) == {**ALL_PASS, "kit:owned": "warn"}
    assert check_report_rows(pack)["kit:owned"]["detail"] == ("voice.md, visual.md, golden-rules.md changed since the last build: "
                                                              "`brand-creator kit build --yes` records it and moves the version on")
    assert build(pack).returncode == 0 and kit_json(pack)["version"] == "1.2"  # the build records the owner's words and moves the version on
    assert kit_check(pack).returncode == 0 and statuses(pack) == ALL_PASS


def test_a_link_that_leaves_the_kit_fails(pack):
    filled_kit(pack)
    assert kit_check(pack).returncode == 0
    assert check_report_rows(pack)["kit:links"]["detail"] == f"{FRESH_LINKS} relative links in {FRESH_FILES} .md, .html and .css files resolve inside the kit"
    visual = kit_of(pack) / "visual.md"
    before = mutate(visual, "Keep it short. [example]", "Keep it short. [example]\n\n[mark](../../../assets/logo/mark.svg)")
    r = kit_check(pack)
    assert r.returncode == 1, r.stdout + r.stderr
    row = check_report_rows(pack)["kit:links"]
    assert row["status"] == "fail"
    assert row["detail"] == (f"1 of {FRESH_LINKS + 1} relative links does not resolve inside the kit: "
                             f"visual.md:7 -> ../../../assets/logo/mark.svg ({OUTSIDE_KIT})")
    assert statuses(pack)["kit:fill"] == "pass" and statuses(pack)["kit:files"] == "pass"
    for link, said in (("/assets/logo/mark.svg", "an absolute path: it will not resolve in a product repository"),
                       ("brand/assets/logo/nope.svg", "no such file in the kit"),
                       ("brand/assets/logo/Mark.svg", "a product repository on Linux tells the letter case apart"),    # the file is mark.svg: found on a Mac, dead on Linux
                       ("brand/assets/logo", "a folder, not a file"),
                       ("brand/assets/logo/mark.svg/more", "no such file in the kit")):
        visual.write_text(before + f"\n[x]({link})\n", encoding="utf-8")
        assert kit_check(pack).returncode == 1, link
        detail = check_report_rows(pack)["kit:links"]["detail"]
        assert f"visual.md:7 -> {link} (" in detail and said in detail, (link, detail)
    ok = ("[a](brand/assets/logo/mark.svg) [b](brand/assets/logo/mark.svg?v=2#top) [c](#top) [d](https://example.com/x.png) [e](mailto:?subject=hello) "
          "[f](data:image/png;base64,AAAA) [g](<brand/assets/logo/wordmark.svg> \"title\") [h](//cdn.example.com/x.css) [i](brand/assets/logo/wordmark%2Ddark.svg)")
    visual.write_text(before + f"\n{ok}\n", encoding="utf-8")                  # relative: a, b, g, i. Not files of the kit: c to f and h
    assert kit_check(pack).returncode == 0
    assert check_report_rows(pack)["kit:links"]["detail"] == f"{FRESH_LINKS + 4} relative links in {FRESH_FILES} .md, .html and .css files resolve inside the kit"


MD_NOTES = """[ok](../brand/assets/logo/mark.svg) and ![image](<../brand/assets/logo/wordmark.svg> "title")
`[code](../gone-in-code.md)`
```
[fenced](../gone-in-a-fence.md)
```
[dead](../brand/assets/gone.md)
[percent](../brand/assets/logo/wordmark%2Ddark.svg)
"""
HTML_NOTES = """<!doctype html>
<html><head>
<!-- <a href="../gone-in-a-comment.html">not a link</a> -->
<link rel="stylesheet" href="../brand/assets/tokens/tokens.css">
<script>var s = '<a href="../gone-in-a-script.html">';</script>
</head><body>
<img src="../brand/assets/logo/mark.svg" srcset="../brand/assets/logo/mark.svg 1x, ../brand/assets/logo/gone-2x.svg 2x" alt="">
<a href="../brand/assets/logo/gone.svg#top">dead</a>
<a href="https://example.com/x">out</a> <a href="mailto:?subject=hello">mail</a> <a href="#top">top</a> <a href="">here</a>
<svg><use xlink:href="../brand/assets/logo/wordmark.svg#w"/></svg>
</body></html>
"""
CSS_NOTES = """/* url(../gone-in-a-comment.png) */
.a { background: url("../brand/assets/logo/mark.svg"); }
.b { background: url(../brand/assets/logo/gone.png); }
.c { background: url( 'data:image/png;base64,AAAA' ) }
.d { background: url(#grad) }
"""


def test_links_are_read_from_markdown_html_and_css_and_only_relative_ones_are_judged(pack):
    filled_kit(pack)
    notes = kit_of(pack) / "notes"                                           # a folder of the owner's own, beside the generated ones
    notes.mkdir()
    (notes / "own.md").write_text(MD_NOTES, encoding="utf-8")
    (notes / "page.html").write_text(HTML_NOTES, encoding="utf-8")
    (notes / "style.css").write_text(CSS_NOTES, encoding="utf-8")
    r = kit_check(pack)
    assert r.returncode == 1, r.stdout + r.stderr
    row = check_report_rows(pack)["kit:links"]
    # own.md: four relative links (the code span and the fenced block are no links), page.html: six, style.css: two, and the seven of the fresh kit
    gone = "(no such file in the kit)"
    assert row["status"] == "fail" and row["detail"] == (
        f"4 of {FRESH_LINKS + 4 + 6 + 2} relative links do not resolve inside the kit: "
        f"notes/own.md:6 -> ../brand/assets/gone.md {gone}, notes/page.html:7 -> ../brand/assets/logo/gone-2x.svg {gone}, "
        f"notes/page.html:8 -> ../brand/assets/logo/gone.svg#top {gone}, notes/style.css:3 -> ../brand/assets/logo/gone.png {gone}")
    for name in ("own.md", "page.html", "style.css"):
        (notes / name).unlink()
    assert kit_check(pack).returncode == 0


@pytest.mark.parametrize("value, urls", [
    ("a.svg 1x,b.svg 2x", ["a.svg", "b.svg"]),                                      # minified: the comma that follows a descriptor ends the candidate
    ("a.svg 1x, b.svg 2x", ["a.svg", "b.svg"]),
    ("a.svg 1x , b.svg 2x", ["a.svg", "b.svg"]),
    ("a.svg 480w,b.svg 960w,c.svg 1440w", ["a.svg", "b.svg", "c.svg"]),
    ("  a.svg\n\t480w ,\n  b.svg 960w  ", ["a.svg", "b.svg"]),                       # any ASCII whitespace, and some before the first and after the last candidate
    ("a.svg, b.svg", ["a.svg", "b.svg"]),                                           # a comma that ends the URL: no descriptor
    ("a.svg,\nb.svg 2x", ["a.svg", "b.svg"]),
    ("a.svg,b.svg 2x", ["a.svg,b.svg"]),                                            # a comma inside a URL, with no whitespace after it, belongs to the URL
    ("data:image/svg+xml,%3Csvg%2F%3E 1x,b.svg 2x", ["data:image/svg+xml,%3Csvg%2F%3E", "b.svg"]),
    ("a.svg 1x,,, b.svg", ["a.svg", "b.svg"]),
    ("a.svg 1x (x, y), b.svg", ["a.svg", "b.svg"]),                                 # a comma inside parentheses is part of the descriptor
    ("a.svg", ["a.svg"]),
    ("", []),
    (" , \n,", []),
])
def test_srcset_urls_are_read_by_the_html_rule(value, urls):
    """The expected URLs are written out by hand from the HTML Standard's "parse a srcset attribute": a URL is the run up to the next ASCII whitespace, one that ends with a comma
    loses its commas and has no descriptor, any other URL is followed by a descriptor that runs to the first comma outside parentheses."""
    import kitlib
    assert [u for _line, u in kitlib.html_links(f'<img srcset="{value}">')] == urls


def test_a_valid_srcset_written_without_spaces_is_no_dead_link(pack):
    """`srcset="a.svg 1x,b.svg 2x"` is valid HTML, and the targets are `a.svg` and `b.svg`, never `1x,b.svg` (a word of the value up to the next white space)."""
    filled_kit(pack)
    notes = kit_of(pack) / "notes"
    notes.mkdir()
    logo = "../brand/assets/logo"
    page = notes / "page.html"
    page.write_text(f"""<img src="{logo}/mark.svg" srcset="{logo}/mark.svg 1x,{logo}/mark-dark.svg 2x" alt="">
<img srcset="{logo}/mark.svg 1x , {logo}/mark-dark.svg 2x" alt="">
<picture><source srcset="{logo}/wordmark.svg 480w,
  {logo}/wordmark-dark.svg 960w"><img src="{logo}/mark.svg" alt=""></picture>
<img srcset="{logo}/mark.svg, {logo}/mark-dark.svg 2x" alt="">
<img srcset="data:image/svg+xml,%3Csvg%2F%3E 1x,{logo}/mark.svg 2x" alt="">
""", encoding="utf-8")                                                                      # eleven relative links; the data: URI is no relative link
    r = kit_check(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert check_report_rows(pack)["kit:links"]["detail"] == f"{FRESH_LINKS + 11} relative links in {FRESH_FILES + 1} .md, .html and .css files resolve inside the kit"
    mutate(page, f"{logo}/mark.svg 1x,{logo}/mark-dark.svg 2x", f"{logo}/mark.svg 1x,{logo}/gone.svg 2x")      # one candidate of the minified form dies
    r = kit_check(pack)
    assert r.returncode == 1, r.stdout + r.stderr
    assert check_report_rows(pack)["kit:links"]["detail"] == (f"1 of {FRESH_LINKS + 11} relative links does not resolve inside the kit: "
                                                              f"notes/page.html:1 -> {logo}/gone.svg (no such file in the kit)")
    mutate(page, f"{logo}/mark.svg 1x,{logo}/gone.svg 2x", f"{logo}/mark.svg 1x,{logo}/mark-dark.svg 2x")
    mutate(page, f"{logo}/wordmark.svg 480w,\n  {logo}/wordmark-dark.svg 960w", f"{logo}/wordmark.svg 480w,\n  {logo}/wordmark-gone.svg 960w")     # and one of the spaced form, on the next line
    r = kit_check(pack)
    assert r.returncode == 1, r.stdout + r.stderr
    assert check_report_rows(pack)["kit:links"]["detail"] == (f"1 of {FRESH_LINKS + 11} relative links does not resolve inside the kit: "
                                                              f"notes/page.html:3 -> {logo}/wordmark-gone.svg (no such file in the kit)")


def test_a_generated_file_edited_or_a_file_added_to_a_generated_folder_fails_kit_check(pack):
    filled_kit(pack)
    assert kit_check(pack).returncode == 0 and statuses(pack) == ALL_PASS
    css = kit_of(pack) / "brand" / "assets" / "tokens" / "tokens.css"
    before = mutate(css, "#4cd7c8", "#4cd7c9")
    assert kit_check(pack).returncode == 1
    assert check_report_rows(pack)["kit:files"]["detail"] == ("1 generated file(s) differ from kit.json: brand/assets/tokens/tokens.css (edited by hand); "
                                                              "change the brand project and run `brand-creator kit build --yes`")
    css.write_text(before, encoding="utf-8")
    assert kit_check(pack).returncode == 0
    stray = kit_of(pack) / "brand" / "notes.txt"
    stray.write_text("mine", encoding="utf-8")                                 # a file of the owner's in a generated folder
    assert kit_check(pack).returncode == 1
    assert check_report_rows(pack)["kit:files"]["detail"] == "1 file(s) in a generated folder are not listed in kit.json: brand/notes.txt; move it to recipes/ or a folder of your own"
    stray.unlink()
    (kit_of(pack) / "notes").mkdir()
    (kit_of(pack) / "notes" / "mine.txt").write_text("mine", encoding="utf-8")      # the owner's own folder is no generated folder
    assert kit_check(pack).returncode == 0
    (kit_of(pack) / "brand" / "assets" / "logo" / "wordmark.svg").unlink()
    assert kit_check(pack).returncode == 1
    assert "brand/assets/logo/wordmark.svg (missing)" in check_report_rows(pack)["kit:files"]["detail"]
    assert build(pack).returncode == 0                                         # the build writes it back
    kj = kit_of(pack) / "kit.json"
    mutate(kj, '"kit": "acme-brand"', '"kit":  "acme-brand"')                  # the same JSON, other bytes: not what the build wrote
    assert kit_check(pack).returncode == 1
    assert check_report_rows(pack)["kit:files"]["detail"] == "kit.json is not the bytes the kit report recorded: it was edited by hand; run `brand-creator kit build --yes`"
    skill = kit_of(pack) / "SKILL.md"
    mutate(skill, "## Never", "## Never\n\n- Do anything.")
    assert kit_check(pack).returncode == 1
    detail = check_report_rows(pack)["kit:files"]["detail"]
    assert "SKILL.md (edited by hand)" in detail and "kit.json is not the bytes the kit report recorded" in detail


def test_the_version_in_skill_md_must_be_the_one_in_kit_json(pack):
    filled_kit(pack)
    assert kit_check(pack).returncode == 0
    skill = kit_of(pack) / "SKILL.md"
    line = "Kit version 1.2 (kit.json)."
    mutate(skill, line, "Kit version 1.3 (kit.json).")
    assert kit_check(pack).returncode == 1
    assert check_report_rows(pack)["kit:versions"]["detail"] == "SKILL.md says version 1.3 (kit.json says 1.2): it must hold `Kit version 1.2 (kit.json).` exactly once"
    assert statuses(pack)["kit:files"] == "fail"                               # the file is no longer the bytes the build wrote either
    mutate(skill, "Kit version 1.3 (kit.json).", f"{line}\n\n{line}")
    assert kit_check(pack).returncode == 1
    assert check_report_rows(pack)["kit:versions"]["detail"] == "SKILL.md holds the version line 2 times (kit.json says 1.2): it must hold `Kit version 1.2 (kit.json).` exactly once"
    mutate(skill, f"{line}\n\n{line}", "A line that states no version.")
    assert kit_check(pack).returncode == 1
    assert check_report_rows(pack)["kit:versions"]["detail"] == "SKILL.md has no version line (kit.json says 1.2): it must hold `Kit version 1.2 (kit.json).` exactly once"
    assert build(pack, "--replace").returncode == 0 and kit_check(pack).returncode == 0     # the build writes SKILL.md back (the edited one is moved aside)
    kj = kit_of(pack) / "kit.json"
    mutate_json(kj, lambda d: d.__setitem__("version", "2.1"))                 # a version of another edition than kit.json's own
    assert kit_check(pack).returncode == 1
    assert "kit.json version 2.1 does not start with its edition 1 (a version is <edition>.<build>)" in check_report_rows(pack)["kit:versions"]["detail"]


def test_a_kit_of_an_older_edition_fails_kit_check(pack):
    filled_kit(pack)
    assert kit_check(pack).returncode == 0
    assert bc("state", "--set", "edition=2", project=pack).returncode == 0
    assert bc("state", "--record", "G5", "approved edition 2 (test)", project=pack).returncode == 0     # the brand is at edition 2 now
    r = kit_check(pack)
    assert r.returncode == 1, r.stdout + r.stderr
    assert check_report_rows(pack)["kit:versions"]["detail"] == "the kit is of edition 1, the brand is at 2: run `brand-creator kit build --yes`"
    assert statuses(pack)["kit:versions"] == "fail"
    assert build(pack).returncode == 0
    r = kit_check(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (kit_json(pack)["edition"], kit_json(pack)["version"]) == ("2", "2.1")


def test_a_brand_change_after_the_build_makes_kit_check_not_verified(pack):
    filled_kit(pack)
    assert kit_check(pack).returncode == 0
    mutate(pack / "FACTS.md", "tools are made in batches of 200", "tools are made in batches of 300")
    r = kit_check(pack)
    assert r.returncode == 3, r.stdout + r.stderr                               # not verified, never a pass
    assert report(pack, "kit-check")["status"] == "not-verified"
    assert statuses(pack) == {**ALL_PASS, "kit:sources": "skipped"}             # the files are the bytes the build wrote; it is the brand that moved on
    assert check_report_rows(pack)["kit:sources"]["detail"] == ("not verified: the brand changed after the kit was built (state_sha, facts); "
                                                                "run `brand-creator kit build --yes`")
    assert build(pack).returncode == 0
    assert kit_check(pack).returncode == 0 and statuses(pack) == ALL_PASS
    shutil.copy(pack / "assets" / "logo" / "wordmark.svg", pack / "assets" / "logo" / "zz-extra.svg")      # a new logo is a source too
    assert kit_check(pack).returncode == 3
    assert check_report_rows(pack)["kit:sources"]["detail"] == "not verified: the brand changed after the kit was built (logos); run `brand-creator kit build --yes`"


def test_check_asks_for_kit_check_once_a_kit_exists(pack):
    assert bc("applied-skill", "--yes", project=pack).returncode == 0           # a plain applied skill first: no kit, so no kit-check
    assert not any(i.startswith(("report:kit", "kit:")) for i in check_rows(pack))
    filled_kit(pack)
    rows = check_rows(pack)
    assert rows["report:kit-check"]["status"] == "skipped"
    assert "no kit-check report" in rows["report:kit-check"]["detail"] and "`brand-creator kit check`" in rows["report:kit-check"]["detail"]
    assert kit_check(pack).returncode == 0
    rows = check_rows(pack)
    assert rows["report:kit-check"]["status"] == "pass" and "kit:checked" not in rows
    voice = kit_of(pack) / "voice.md"
    voice.write_text(voice.read_text(encoding="utf-8").replace("Keep it short. [example]", "Keep it short and plain. [example]"), encoding="utf-8")     # a file the report read changed: it is stale
    rows = check_rows(pack)
    assert rows["report:kit-check"]["status"] == "skipped" and "stale" in rows["report:kit-check"]["detail"] and "voice.md changed" in rows["report:kit-check"]["detail"]
    assert kit_check(pack).returncode == 0 and check_rows(pack)["report:kit-check"]["status"] == "pass"
    visual = kit_of(pack) / "visual.md"
    visual.write_text(visual.read_text(encoding="utf-8") + "\n[[fill: more]]\n", encoding="utf-8")
    assert kit_check(pack).returncode == 1
    rows = check_rows(pack)
    assert rows["report:kit-check"]["status"] == "fail" and "kit:fill" in rows["report:kit-check"]["detail"]       # a failing kit check is a failing check


def test_the_kit_check_report_lists_the_sources_of_the_kit_as_inputs(pack):
    """The kit is made from the brand, so a change of the brand after `kit check` makes its report stale for `check`, not only a change inside the kit."""
    filled_kit(pack)
    assert kit_check(pack).returncode == 0
    inputs = {i["path"] for i in report(pack, "kit-check")["inputs"]}
    for rel in ("FACTS.md", "BRAND-STATE.md", "qa/rules.json", "assets/tokens/tokens.json", "assets/tokens/tokens.css", "assets/logo/mark.svg", "assets/logo/wordmark.svg",
                "assets/_checks/kit.json", ".claude/skills/acme-brand/kit.json", ".claude/skills/acme-brand/voice.md"):
        assert rel in inputs, rel                                                          # the brand's files, the build's report, and the kit's own files
    rows = check_rows(pack)
    assert rows["report:kit-check"]["status"] == "pass" and "kit:checked" not in rows
    mutate(pack / "FACTS.md", "tools are made in batches of 200", "tools are made in batches of 300")
    rows = check_rows(pack)
    assert rows["report:kit-check"]["status"] == "skipped"
    assert "stale" in rows["report:kit-check"]["detail"] and "FACTS.md changed" in rows["report:kit-check"]["detail"]
    assert kit_check(pack).returncode == 3                                                 # read again: the kit no longer matches the brand, so it is not verified
    assert check_rows(pack)["report:kit-check"]["status"] == "skipped"                     # and a report that is not verified is not a pass for check either


def test_a_file_added_to_the_kit_after_kit_check_makes_check_say_not_verified(pack):
    filled_kit(pack)
    assert kit_check(pack).returncode == 0
    assert "kit:checked" not in check_rows(pack)
    notes = kit_of(pack) / "notes"
    notes.mkdir()
    (notes / "new.md").write_text("A page of my own.\n", encoding="utf-8")     # no input of the report that was written: it cannot make the report stale, the tree says so
    rows = check_rows(pack)
    assert rows["report:kit-check"]["status"] == "pass"
    assert rows["kit:checked"]["status"] == "skipped" and "added to the kit, or taken out of it" in rows["kit:checked"]["detail"]
    assert kit_check(pack).returncode == 0
    assert "kit:checked" not in check_rows(pack)
    (notes / "new.md").unlink()                                                # taken out again: the input is gone, so the report is stale
    rows = check_rows(pack)
    assert rows["report:kit-check"]["status"] == "skipped" and "notes/new.md is gone" in rows["report:kit-check"]["detail"]


def test_a_finder_ds_store_in_the_kit_leaves_the_kit_check_current(pack):
    """Finder puts a `.DS_Store` into every folder the owner opens, the top of the kit and `brand/` too, and writes it again whenever the window changes. `kit_paths` leaves a file with
    exactly that name out, as `on_disk` does for the generated folders: it is no input of the `kit-check` report, is not in the kit's tree, and is not read for links or fill markers."""
    filled_kit(pack)
    assert kit_check(pack).returncode == 0
    kd = kit_of(pack)
    finder = [".DS_Store", "brand/.DS_Store", "notes/.DS_Store"]
    (kd / "notes").mkdir()
    for rel in finder:
        (kd / rel).write_text("Finder was here\n[[fill: a note]] [dead](gone.md)\n", encoding="utf-8")       # text, so that a reader that did not skip it would find a marker and a dead link
    rows = check_rows(pack)
    assert rows["report:kit-check"]["status"] == "pass" and "kit:checked" not in rows
    assert kit_check(pack).returncode == 0 and statuses(pack) == ALL_PASS                  # nothing in them is read
    assert not [i["path"] for i in report(pack, "kit-check")["inputs"] if i["path"].endswith(".DS_Store")]
    for rel in finder:                                                                     # Finder writes them again
        mutate(kd / rel, "Finder was here", "Finder was here again")
    rows = check_rows(pack)
    assert rows["report:kit-check"]["status"] == "pass" and "kit:checked" not in rows
    (kd / ".DS_Store").unlink()
    (kd / "brand" / ".DS_Store").unlink()
    (kd / "notes" / ".DS_Store").unlink()
    rows = check_rows(pack)                                                                # and taking them away is no change either
    assert rows["report:kit-check"]["status"] == "pass" and "kit:checked" not in rows
    (kd / ".DS_Store.bak").write_text("mine\n", encoding="utf-8")                          # only the exact name is Finder's: any other name is a file of the kit
    rows = check_rows(pack)
    assert rows["kit:checked"]["status"] == "skipped" and "added to the kit, or taken out of it" in rows["kit:checked"]["detail"]


def test_a_demo_page_whose_files_are_in_the_kit_has_no_dead_link(pack):
    moving(pack)
    demo = pack / "motion" / "demo.html"
    page = demo.read_text(encoding="utf-8")
    assert "</head>" in page and "</main>" in page
    demo.write_text(page.replace("</head>", '<link rel="stylesheet" href="../assets/tokens/tokens.css">\n</head>')
                        .replace("</main>", '<img src="../assets/logo/mark.svg" alt="">\n</main>'), encoding="utf-8")      # the brand's files, where the page finds them from motion/
    filled_kit(pack)
    assert (kit_of(pack) / "brand" / "motion" / "demo.html").is_file()
    r = kit_check(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    # the seven links of snippets/logo.html and the two of the demo page; the Markdown, HTML and CSS files are the eight of a fresh kit, brand/motion/demo.html and brand/motion/SPEC.md
    assert check_report_rows(pack)["kit:links"]["detail"] == f"{FRESH_LINKS + 2} relative links in {FRESH_FILES + 2} .md, .html and .css files resolve inside the kit"
    (pack / "motion" / "helper.js").write_text("// the page's own script\n", encoding="utf-8")        # the project has the file; the kit copies the page and not what it loads
    demo.write_text(demo.read_text(encoding="utf-8").replace("</body>", '<script src="./helper.js"></script>\n</body>'), encoding="utf-8")
    assert build(pack).returncode == 0
    r = kit_check(pack)
    assert r.returncode == 1, r.stdout + r.stderr
    detail = check_report_rows(pack)["kit:links"]["detail"]
    assert detail.startswith(f"1 of {FRESH_LINKS + 3} relative links does not resolve inside the kit: brand/motion/demo.html:") and "-> ./helper.js (no such file in the kit)" in detail


def test_kit_check_without_a_kit_is_a_usage_error_and_writes_no_report(pack):
    r = kit_check(pack)
    assert r.returncode == 2, r.stdout + r.stderr
    assert "no kit in this project: `brand-creator kit build --yes` (opt-in at G5)" in r.stderr
    assert not (pack / "assets" / "_checks" / "kit-check.json").exists() and not (pack / ".claude").exists()


def test_kit_check_without_the_kit_report_cannot_verify_the_files(pack):
    filled_kit(pack)
    (pack / "assets" / "_checks" / "kit.json").unlink()
    r = kit_check(pack)
    assert r.returncode == 3, r.stdout + r.stderr
    assert statuses(pack) == {**ALL_PASS, "kit:files": "skipped"}
    assert check_report_rows(pack)["kit:files"]["detail"] == ("not verified: there is no `kit` report that records what the build wrote; "
                                                              "run `brand-creator kit build --yes`")


def test_kit_check_reads_kit_json_strictly_and_a_kit_json_that_is_a_link_is_refused(pack, tmp_path):
    filled_kit(pack)
    kj = kit_of(pack) / "kit.json"
    good = kj.read_bytes()
    mutate_json(kj, lambda d: d.__setitem__("surprise", 1))
    before = (pack / "assets" / "_checks" / "kit-check.json").exists()
    r = kit_check(pack)
    assert r.returncode == 2 and "surprise: unknown key" in r.stderr and not before
    kj.write_bytes(good)
    outside = tmp_path / "kit.json"
    outside.write_bytes(good)
    kj.unlink()
    kj.symlink_to(outside)
    r = kit_check(pack)
    assert r.returncode == 2 and "is a link, and a link is never read through" in r.stderr and not (pack / "assets" / "_checks" / "kit-check.json").exists()


def test_a_kit_json_that_is_a_link_stops_kit_check_and_check_says_what_holds_of_the_earlier_report(pack, tmp_path):
    """`kit check` stops on a kit.json that is a link before it writes a report, so the report of the earlier run stands. Whether `check` still takes it for current depends on the
    bytes the link leads to: the same bytes leave it current (only `kit:checked` sees that kit.json is a link now), other bytes make it stale."""
    filled_kit(pack)
    assert kit_check(pack).returncode == 0
    kj, outside = kit_of(pack) / "kit.json", tmp_path / "kit.json"
    outside.write_bytes(kj.read_bytes())
    kj.unlink()
    kj.symlink_to(outside)
    earlier = (pack / "assets" / "_checks" / "kit-check.json").read_bytes()
    r = kit_check(pack)
    assert r.returncode == 2 and "is a link, and a link is never read through" in r.stderr
    assert (pack / "assets" / "_checks" / "kit-check.json").read_bytes() == earlier           # no new report
    rows = check_rows(pack)
    assert rows["report:kit-check"]["status"] == "pass"                                     # the bytes are the ones the report read
    assert rows["kit:checked"]["status"] == "skipped" and "added to the kit, or taken out of it" in rows["kit:checked"]["detail"]
    mutate_json(outside, lambda d: d.__setitem__("plugin_version", "0.0.1"))                 # other bytes behind the link
    rows = check_rows(pack)
    assert rows["report:kit-check"]["status"] == "skipped" and "kit.json changed" in rows["report:kit-check"]["detail"]


def test_kit_check_never_reads_through_a_link(pack, tmp_path):
    filled_kit(pack)
    outside = tmp_path / "outside.md"
    outside.write_text("[[fill: from outside]] [gone](../nowhere.md)\n", encoding="utf-8")
    folder = tmp_path / "folder"
    folder.mkdir()
    (folder / "page.md").write_text("[[fill: from a folder]]\n", encoding="utf-8")
    kd = kit_of(pack)
    (kd / "mine.md").symlink_to(outside)                                        # a link to a file, and one to a folder, in the owner's part of the kit: neither is read
    (kd / "mine").symlink_to(folder)
    r = kit_check(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert statuses(pack) == {**ALL_PASS, "kit:owned": "warn"}                  # a link among the owner's files is no file the kit can read: kit:owned says so, and the build refuses it
    assert check_report_rows(pack)["kit:owned"]["detail"].startswith("mine, mine.md is no file the kit can read (a folder, or a link)")
    assert not any(i["path"].endswith(("mine.md", "mine/page.md")) for i in report(pack, "kit-check")["inputs"])
    (kd / "brand" / "assets" / "logo" / "mark.svg").unlink()                    # a link where a generated file belongs is not that file, whatever it points at
    (kd / "brand" / "assets" / "logo" / "mark.svg").symlink_to(pack / "assets" / "logo" / "mark.svg")
    (kd / "brand" / "linked").symlink_to(folder)                                # and a link to a folder in a generated folder is a file nobody listed
    r = kit_check(pack)
    assert r.returncode == 1, r.stdout + r.stderr
    detail = check_report_rows(pack)["kit:files"]["detail"]
    assert "brand/assets/logo/mark.svg (is a link or a folder, not a file)" in detail and "not listed in kit.json: brand/linked;" in detail
    (kd / "visual.md").write_text("[behind](../kit/mine/page.md) [also](mine/page.md) [mine](mine.md)\n", encoding="utf-8")    # a link into a linked folder or file is not a file of the kit
    r = kit_check(pack)
    detail = check_report_rows(pack)["kit:links"]["detail"]
    assert "visual.md:1 -> mine/page.md (behind a link in the kit: a link is never followed)" in detail and "visual.md:1 -> mine.md (is" not in detail
    assert f"visual.md:1 -> ../kit/mine/page.md ({OUTSIDE_KIT})" in detail


def test_the_plugin_version_row_warns_and_never_fails(pack):
    filled_kit(pack)
    kj, rep = kit_of(pack) / "kit.json", pack / "assets" / "_checks" / "kit.json"
    mutate_json(kj, lambda d: d.__setitem__("plugin_version", "0.0.1"))
    mutate_json(rep, lambda d: d["outputs"].__setitem__("kit.json", file_sha(kj)))      # the report records this kit.json as the one the build wrote
    r = kit_check(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    row = check_report_rows(pack)["kit:plugin"]
    assert row["status"] == "warn" and row["detail"].startswith("the kit was built by brand-creator 0.0.1, this is ")
    assert "`brand-creator kit build --yes` records it" in row["detail"] and report(pack, "kit-check")["status"] == "pass"
    assert build(pack).returncode == 0 and kit_json(pack)["plugin_version"] != "0.0.1" and kit_json(pack)["version"] == "1.2"      # recorded; the content did not move
    assert kit_check(pack).returncode == 0 and statuses(pack) == ALL_PASS


def test_a_deleted_or_replaced_owner_file_warns_and_a_marker_in_a_generated_copy_fails(pack):
    filled_kit(pack)
    kd = kit_of(pack)
    (kd / "recipes" / "web-page.md").unlink()
    r = kit_check(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert check_report_rows(pack)["kit:owned"]["status"] == "warn"
    assert check_report_rows(pack)["kit:owned"]["detail"] == "recipes/web-page.md is missing: `brand-creator kit build --yes` writes the scaffold again"
    assert build(pack).returncode == 0 and (kd / "recipes" / "web-page.md").is_file() and kit_check(pack).returncode == 0
    voice = kd / "voice.md"
    voice.unlink()
    voice.mkdir()                                                               # a folder where the file belongs
    assert kit_check(pack).returncode == 0
    assert check_report_rows(pack)["kit:owned"]["detail"] == "voice.md is no file the kit can read (a folder, or a link): move it away yourself, then run `brand-creator kit build --yes`"
    voice.rmdir()
    shutil.copy2(FIXTURES / "FACTS.md", pack / "FACTS.md")
    mutate(pack / "FACTS.md", "tools are made in batches of 200", "tools are made in batches of 200 [[fill: the real number]]")
    assert build(pack).returncode == 0                                          # the brand's own file carries a marker, and the kit holds a copy of what it says
    r = kit_check(pack)
    assert r.returncode == 1 and "facts.json:" in check_report_rows(pack)["kit:fill"]["detail"]


def test_a_kit_json_that_lists_a_path_outside_the_kit_fails_and_the_path_is_never_opened(pack, tmp_path):
    filled_kit(pack)
    secret = tmp_path / "secret.txt"
    secret.write_text("outside the project", encoding="utf-8")
    kj, rep = kit_of(pack) / "kit.json", pack / "assets" / "_checks" / "kit.json"
    for listed in ("../../../../../../../../../../" + str(secret).lstrip("/"), "brand/../../x", "/etc/hosts"):
        mutate_json(kj, lambda d: d["generated"].__setitem__(listed, "0" * 64))
        mutate_json(rep, lambda d: d["outputs"].__setitem__("kit.json", file_sha(kj)))
        r = kit_check(pack)
        assert r.returncode == 1 and "Traceback" not in r.stderr, (listed, r.stdout + r.stderr)
        assert f"{listed} (is no path a kit holds)" in check_report_rows(pack)["kit:files"]["detail"], listed
        mutate_json(kj, lambda d: d["generated"].pop(listed))


# ---------------------------------------------------------------- kit status: is the copy in a product repository current?
# `kit status --repo DIR` reads <DIR>/.claude/skills/acme-brand/ and writes nothing. A repository's copy is made with shutil.copytree of the project's kit folder.
import os  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402

COPY_ORDER = sorted(r for r in KIT_FILES if r != "kit.json") + ["kit.json"]                      # the copy list: the generated files, kit.json last (as the build writes it) ...
OWNER_ORDER = ["EXTENDING.md", "voice.md", "visual.md", "golden-rules.md", "recipes/web-page.md"]   # ... then the owner files the repository lacks
READ_ONLY_LINE = "read only: nothing in the installed kit folders changed while they were read"


def kit_status(p, *repos, extra=(), env=None):
    return bc("kit", "status", *[a for r in repos for a in ("--repo", str(r))], *extra, project=p, env=env)


def installed_of(repo):
    return repo / ".claude" / "skills" / "acme-brand"


def install(p, tmp_path, name="site"):
    """A product repository that holds a byte copy of the project's kit folder."""
    repo = tmp_path / name
    shutil.copytree(kit_of(p), installed_of(repo))
    return repo


def listed(out: str, title: str) -> list[str]:
    """The items under a section of the status text: the lines indented four spaces after the line that starts with `  <title>`."""
    lines = out.splitlines()
    start = next(n for n, ln in enumerate(lines) if ln.startswith(f"  {title}"))
    items = []
    for ln in lines[start + 1:]:
        if not ln.startswith("    "):
            break
        items.append(ln.strip())
    return items


def paths_of(items: list[str]) -> list[str]:
    return [i.split(" (")[0] for i in items]


def tree_of(root) -> list:
    """Every folder, file and link below `root` with its size and modification time: what a read-only run leaves as it was."""
    out = []
    for dirpath, dirs, names in os.walk(root):
        for n in [*dirs, *names]:
            f = os.path.join(dirpath, n)
            st = os.lstat(f)
            out.append((os.path.relpath(f, root), st.st_size, st.st_mtime_ns))
    return sorted(out)


def test_kit_status_says_not_installed_and_lists_what_to_copy(pack, tmp_path):
    assert build(pack).returncode == 0
    repo = tmp_path / "site"
    repo.mkdir()
    (repo / "README.md").write_text("the product", encoding="utf-8")
    project_before, repo_before = tree_of(pack), tree_of(repo)
    r = kit_status(pack, repo)
    assert r.returncode == 1, r.stdout + r.stderr
    lines = r.stdout.splitlines()
    assert lines[0] == "kit acme-brand, version 1.1" and "site: not installed" in lines and lines[-1] == READ_ONLY_LINE
    items = listed(r.stdout, "copy list")
    assert paths_of(items) == COPY_ORDER + OWNER_ORDER                                  # fifteen generated files, kit.json last, then the five owner files
    assert not any("owner file" in i for i in items[:len(COPY_ORDER)]) and all("owner file" in i for i in items[len(COPY_ORDER):])
    assert tree_of(pack) == project_before and tree_of(repo) == repo_before             # nothing written, in the project or in the repository
    assert not list((pack / "assets" / "_checks").glob("*status*"))                      # and no report


def test_kit_status_says_when_the_kit_folder_is_there_but_holds_no_kit(pack, tmp_path):
    assert build(pack).returncode == 0
    repo = tmp_path / "site"
    (installed_of(repo)).mkdir(parents=True)
    (installed_of(repo) / "SKILL.md").write_text("a skill somebody wrote by hand\n", encoding="utf-8")
    r = kit_status(pack, repo)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "site: not installed" in r.stdout.splitlines()
    assert ".claude/skills/acme-brand/ is there but holds no kit.json: it is not a kit, so look at it before you copy over it" in r.stdout
    assert paths_of(listed(r.stdout, "copy list")) == COPY_ORDER + OWNER_ORDER


def test_a_byte_copy_of_the_kit_is_current(pack, tmp_path):
    assert build(pack).returncode == 0
    repo = install(pack, tmp_path)
    r = kit_status(pack, repo)
    assert r.returncode == 0, r.stdout + r.stderr
    lines = r.stdout.splitlines()
    assert "site: current (version 1.1)" in lines and lines[-1] == READ_ONLY_LINE
    assert "copy list" not in r.stdout and "differ" not in r.stdout and "missing" not in r.stdout
    (installed_of(repo) / "brand" / ".DS_Store").write_bytes(b"Finder was here")        # what Finder leaves in a folder it opened is no file of the kit
    assert kit_status(pack, repo).returncode == 0


def test_a_changed_generated_file_in_the_repository_is_not_current_and_owner_changes_are_kept(pack, tmp_path):
    assert build(pack).returncode == 0
    repo = install(pack, tmp_path)
    kd = installed_of(repo)
    mutate(kd / "brand/assets/tokens/tokens.css", "#4cd7c8", "#4cd7c9")                  # a generated file edited in the repository
    (kd / "snippets/logo.html").unlink()                                                  # a generated file that is gone
    (kd / "brand/assets/logo/old-mark.svg").write_text("<svg/>", encoding="utf-8")        # a file of an older kit, which this kit no longer has
    voice = kd / "voice.md"
    voice.write_text(voice.read_text(encoding="utf-8") + "\nOur own words.\n", encoding="utf-8")   # the repository's own voice file
    (kd / "visual.md").unlink()                                                           # an owner file the repository lacks
    r = kit_status(pack, repo)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "site: not current (version 1.1 on both sides, but 1 file differs, 1 file is missing, 1 file is left over from an older kit)" in r.stdout.splitlines()
    assert listed(r.stdout, "generated files that differ") == ["brand/assets/tokens/tokens.css (not the same bytes)"]
    assert listed(r.stdout, "generated files that are missing") == ["snippets/logo.html"]
    assert listed(r.stdout, "left over from an older kit") == ["brand/assets/logo/old-mark.svg"]
    assert listed(r.stdout, "owner files that differ (kept on update)") == ["voice.md"]
    copy = paths_of(listed(r.stdout, "copy list"))
    assert copy == ["brand/assets/tokens/tokens.css", "snippets/logo.html", "visual.md"]        # the generated files that need copying, then the owner file it lacks; voice.md is not in it
    for rel in copy:                                                                       # the copy the list asks for, and the old file taken out
        shutil.copy2(kit_of(pack) / rel, kd / rel)
    r = kit_status(pack, repo)                                                             # the copy is whole now, and only the old file is left: that alone is not current
    assert r.returncode == 1, r.stdout + r.stderr
    assert "site: not current (version 1.1 on both sides, but 1 file is left over from an older kit)" in r.stdout.splitlines()
    assert listed(r.stdout, "left over from an older kit") == ["brand/assets/logo/old-mark.svg"]
    assert not any(ln.startswith("  copy list") for ln in r.stdout.splitlines()) and "generated files that differ" not in r.stdout and "generated files that are missing" not in r.stdout
    (kd / "brand/assets/logo/old-mark.svg").unlink()
    r = kit_status(pack, repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "site: current (version 1.1)" in r.stdout.splitlines() and "copy list" not in r.stdout
    assert listed(r.stdout, "owner files that differ (kept on update)") == ["voice.md"]    # still the repository's own, and current all the same
    assert "Our own words." in voice.read_text(encoding="utf-8")


def test_a_copy_becomes_current_again_after_a_brand_change_removed_a_generated_file(pack, tmp_path):
    """A logo taken out of the project leaves a file in the repository's copy that the new kit does not have. The copy list names the changed files only, so once it is copied the
    two versions are the same and the old file is all that is left: `kit status` says which file it is, that it is not on the copy list, that it goes to removed-<date>/ in the
    repository, and that the versions are the same, not that they differ. The copy is current when the implementer has moved the file there."""
    assert build(pack).returncode == 0
    repo = install(pack, tmp_path)
    kd, gone = installed_of(repo), "brand/assets/logo/wordmark-dark.svg"
    assert kit_status(pack, repo).returncode == 0
    (pack / "assets" / "logo" / "wordmark-dark.svg").unlink()                              # the brand drops a logo file
    assert build(pack).returncode == 0 and kit_json(pack)["version"] == "1.2" and not (kit_of(pack) / gone).exists()
    r = kit_status(pack, repo)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "site: not current (installed version 1.1, project version 1.2)" in r.stdout.splitlines()
    assert listed(r.stdout, "left over from an older kit") == [gone]
    assert ("  left over from an older kit (not in this kit, so not on the copy list; move each to removed-<date>/.claude/skills/acme-brand/ in the repository, "
            "keeping its path; nothing is deleted):") in r.stdout.splitlines()
    copy = paths_of(listed(r.stdout, "copy list"))
    assert gone not in copy and copy == ["SKILL.md", "snippets/logo.html", "kit.json"]            # the files that changed, kit.json last: the old file is not among them
    shown = json.loads(kit_status(pack, repo, extra=("--json",)).stdout)["repos"][0]
    assert shown["left_over"] == [gone] and shown["left_over_to"] == "removed-<date>/.claude/skills/acme-brand/" and shown["copy"] == copy
    for rel in copy:                                                                       # exactly the copy list
        shutil.copy2(kit_of(pack) / rel, kd / rel)
    r = kit_status(pack, repo)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "site: not current (version 1.2 on both sides, but 1 file is left over from an older kit)" in r.stdout.splitlines()     # not "installed 1.2, project 1.2"
    assert "installed version" not in r.stdout and not any(ln.startswith("  copy list") for ln in r.stdout.splitlines())          # nothing left to copy
    assert listed(r.stdout, "left over from an older kit") == [gone]
    moved = repo / "removed-2026-10-17" / ".claude" / "skills" / "acme-brand" / gone         # what the implementer does with it, and says
    moved.parent.mkdir(parents=True)
    shutil.move(str(kd / gone), str(moved))
    r = kit_status(pack, repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "site: current (version 1.2)" in r.stdout.splitlines() and "left over" not in r.stdout
    assert json.loads(kit_status(pack, repo, extra=("--json",)).stdout)["repos"][0]["left_over_to"] is None
    mutate(kd / "brand/assets/tokens/tokens.css", "#4cd7c8", "#4cd7c9")                       # and a file edited in the repository is still caught
    r = kit_status(pack, repo)
    assert r.returncode == 1 and "site: not current (version 1.2 on both sides, but 1 file differs)" in r.stdout.splitlines(), r.stdout + r.stderr


def test_an_older_installed_version_is_not_current_and_names_both_versions(pack, tmp_path):
    assert build(pack).returncode == 0
    repo = install(pack, tmp_path)
    mutate_json(installed_of(repo) / "kit.json", lambda d: d.__setitem__("version", "1.0"))
    r = kit_status(pack, repo)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "site: not current (installed version 1.0, project version 1.1)" in r.stdout.splitlines()
    assert listed(r.stdout, "generated files that differ") == ["kit.json (not the same bytes)"]
    assert paths_of(listed(r.stdout, "copy list")) == ["kit.json"]
    (installed_of(repo) / "kit.json").write_text("not json at all", encoding="utf-8")        # a kit.json that cannot be read has no version to name
    r = kit_status(pack, repo)
    assert r.returncode == 1 and "site: not current (installed version unknown, project version 1.1)" in r.stdout.splitlines()


def test_kit_status_refuses_a_global_skills_folder_the_home_folder_and_the_project(pack, tmp_path):
    assert build(pack).returncode == 0
    home = tmp_path / "home"
    (home / ".claude" / "skills").mkdir(parents=True)
    linked = tmp_path / "linked"                                                          # a repository whose .claude is a link into the global folder
    linked.mkdir()
    (linked / ".claude").symlink_to(home / ".claude")
    uv = lambda *a: subprocess.run(["uv", *a], capture_output=True, text=True, timeout=60).stdout.strip()     # HOME moves, and uv must still find its cache and its Pythons
    env = {"HOME": str(home), "UV_CACHE_DIR": uv("cache", "dir"), "UV_PYTHON_INSTALL_DIR": uv("python", "dir")}
    before = (tree_of(home), tree_of(pack), tree_of(linked))
    for target, needle in ((home, "is your home folder"), (home / ".claude", "is inside ~/.claude"), (home / ".claude" / "skills", "is inside ~/.claude"),
                           (pack, "is the brand project itself or a folder inside it"), (pack / "assets", "is the brand project itself or a folder inside it"),
                           (tmp_path / "nothing-here", "not a folder"), (linked, "~/.claude")):
        r = kit_status(pack, target, env=env)
        assert r.returncode == 2, (target, r.stdout + r.stderr)
        assert needle in r.stderr and not r.stdout, (target, r.stderr)
    assert "the kit goes into one product repository at a time, never into a global skills folder" in kit_status(pack, home, env=env).stderr
    assert "the kit goes into one product repository at a time, never into a global skills folder" in kit_status(pack, home / ".claude" / "skills", env=env).stderr
    ok = tmp_path / "site"                                                                # a folder below the home folder is a repository like any other
    ok.mkdir()
    assert kit_status(pack, ok, env=env).returncode == 1 and (tree_of(home), tree_of(pack), tree_of(linked)) == before
    r = kit_status(pack, ok, tmp_path / "nothing-here", env=env)                           # one bad folder stops the run before anything is read
    assert r.returncode == 2 and not r.stdout


def test_kit_status_reads_and_never_writes_the_repository(pack, tmp_path):
    assert build(pack).returncode == 0
    fresh = tmp_path / "fresh"
    fresh.mkdir()
    (fresh / "package.json").write_text("{}", encoding="utf-8")
    copied = install(pack, tmp_path, "copied")
    stale = install(pack, tmp_path, "stale")
    (installed_of(stale) / "brand/assets/tokens/tokens.css").write_text("edited", encoding="utf-8")
    (installed_of(stale) / "voice.md").unlink()
    project_before, repos_before = tree_of(pack), [tree_of(d) for d in (fresh, copied, stale)]
    for extra in ((), ("--json",)):
        r = kit_status(pack, fresh, copied, stale, extra=extra)
        assert r.returncode == 1 and "Traceback" not in r.stderr, r.stdout + r.stderr
        assert tree_of(pack) == project_before and [tree_of(d) for d in (fresh, copied, stale)] == repos_before
    r = kit_status(pack, fresh, copied, stale)
    assert [ln for ln in r.stdout.splitlines() if ln.startswith(("fresh:", "copied:", "stale:"))] == [
        "fresh: not installed", "copied: current (version 1.1)", "stale: not current (version 1.1 on both sides, but 1 file differs)"]


def test_kit_status_proves_it_read_only_by_the_sizes_and_times_of_the_installed_folder(tmp_path):
    import kitlib
    d = tmp_path / "kit"
    (d / "brand").mkdir(parents=True)
    f = d / "brand" / "a.txt"
    f.write_text("one", encoding="utf-8")
    os.utime(f, ns=(1_000_000_000, 1_000_000_000))
    state = kitlib.folder_state(d)
    assert kitlib.folder_state(d) == state                                                # the same folder, the same proof
    f.write_text("two", encoding="utf-8")                                                 # the same size, another time
    os.utime(f, ns=(2_000_000_000, 2_000_000_000))
    assert kitlib.folder_state(d) != state
    os.utime(f, ns=(1_000_000_000, 1_000_000_000))
    assert kitlib.folder_state(d) == state                                                # the size and the time are what is listed, so the same size and time are the same proof
    f.write_text("three", encoding="utf-8")                                               # another size, the same time
    os.utime(f, ns=(1_000_000_000, 1_000_000_000))
    assert kitlib.folder_state(d) != state
    f.write_text("one", encoding="utf-8")
    os.utime(f, ns=(1_000_000_000, 1_000_000_000))
    (d / "brand" / "b.txt").write_text("", encoding="utf-8")                              # a file added
    assert kitlib.folder_state(d) != state
    (d / "brand" / "b.txt").unlink()
    (d / "brand" / "link").symlink_to(f)                                                  # a link added: listed as the link it is, never followed
    assert kitlib.folder_state(d) != state
    assert kitlib.folder_state(tmp_path / "absent") == kitlib.folder_state(tmp_path / "also-absent")      # a folder that is not there is a state too


def test_kit_status_exits_1_when_the_installed_folder_changes_while_it_is_read(pack, tmp_path):
    assert build(pack).returncode == 0
    repo = install(pack, tmp_path)
    script = ROOT / "scripts" / "kit.py"
    code = ("import runpy, sys\n"
            "script, project, repo = sys.argv[1:4]\n"
            "scripts = script.rsplit('/', 1)[0]\n"
            "sys.path[:0] = [scripts + '/' + d for d in ('lib', 'booklib', 'adaptlib', 'boardlib')]\n"
            "import kitlib\n"
            "real = kitlib.compare\n"
            "def touching(kit, installed):\n"
            "    got = real(kit, installed)\n"
            "    (installed / 'voice.md').write_text('somebody wrote here while the repository was read', encoding='utf-8')\n"
            "    return got\n"
            "kitlib.compare = touching\n"
            "sys.argv = ['kit.py', 'status', '--repo', repo, '--project', project]\n"
            "runpy.run_path(script, run_name='__main__')\n")
    r = subprocess.run([sys.executable, "-c", code, str(script), str(pack), str(repo)], capture_output=True, text=True, timeout=120,
                       env={**os.environ, "BRAND_CREATOR_TODAY": "2026-10-17"})
    assert r.returncode == 1, r.stdout + r.stderr
    assert "site: current (version 1.1)" in r.stdout.splitlines() and READ_ONLY_LINE not in r.stdout
    assert "error: site: the installed kit folder changed while it was read" in r.stderr


def test_kit_status_names_a_repository_by_its_label_and_reads_several_at_once(pack, tmp_path):
    assert build(pack).returncode == 0
    copied = install(pack, tmp_path, "web")
    empty = tmp_path / "app"
    empty.mkdir()
    r = bc("kit", "status", "--repo", f"{copied}=front", "--repo", str(empty), project=pack)
    assert r.returncode == 1, r.stdout + r.stderr
    assert [ln for ln in r.stdout.splitlines() if ln[:1].isalpha() and ": " in ln and not ln.startswith(("kit ", "read only"))] == ["front: current (version 1.1)", "app: not installed"]
    r = bc("kit", "status", "--repo", f"{copied}=front", project=pack)
    assert r.returncode == 0 and "front: current (version 1.1)" in r.stdout.splitlines()


def test_kit_status_without_repo_reads_the_repositories_that_have_a_kit_row(pack, tmp_path):
    assert build(pack).returncode == 0
    r = bc("kit", "status", project=pack)
    assert r.returncode == 2 and "pass --repo" in r.stderr and not r.stdout, r.stdout + r.stderr
    copied, other = install(pack, tmp_path, "site"), tmp_path / "other"
    other.mkdir()
    kit_row = {"n": 1, "category": "kit", "repo": "r1", "file": ".claude/skills/acme-brand/", "lines": [], "find": "kit.json", "change": "Copy the brand kit"}
    (pack / "adoption.json").write_text(json.dumps({
        "schema": 1, "slug": "acme", "repos": [{"id": "r1", "label": "site", "path": "../site"}, {"id": "r2", "label": "other", "path": "../other"}],
        "rows": [{"n": 2, "category": "name", "repo": "r2", "file": "README.md", "lines": [], "find": "Old", "change": "x"}, kit_row]}), encoding="utf-8")
    r = bc("kit", "status", project=pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "site: current (version 1.1)" in r.stdout.splitlines() and "other:" not in r.stdout           # a repository with no kit row is not read
    (pack / "adoption.json").write_text(json.dumps({"schema": 1, "slug": "acme", "repos": [{"id": "r1", "label": "site", "path": "../site"}], "rows": [
        {"n": 1, "category": "name", "repo": "r1", "file": "README.md", "lines": [], "find": "Old", "change": "x"}]}), encoding="utf-8")
    r = bc("kit", "status", project=pack)
    assert r.returncode == 2 and "pass --repo" in r.stderr
    assert copied.is_dir()


def test_kit_status_needs_a_kit_in_the_project_and_never_reads_through_a_link(pack, tmp_path):
    repo = tmp_path / "site"
    repo.mkdir()
    r = kit_status(pack, repo)
    assert r.returncode == 2 and "no kit in this project: `brand-creator kit build --yes` (opt-in at G5)" in r.stderr and not r.stdout
    assert not (pack / ".claude").exists() and not (repo / ".claude").exists()
    assert build(pack).returncode == 0
    elsewhere = tmp_path / "elsewhere"                                                   # a repository whose kit folder is a link to a folder with a kit in it
    shutil.copytree(kit_of(pack), elsewhere)
    (repo / ".claude" / "skills").mkdir(parents=True)
    installed_of(repo).symlink_to(elsewhere)
    r = kit_status(pack, repo)
    assert r.returncode == 2 and "is a link, and a link is never read through" in r.stderr and not r.stdout
    installed_of(repo).unlink()
    shutil.copytree(kit_of(pack), installed_of(repo))
    (installed_of(repo) / "snippets" / "logo.html").unlink()
    (installed_of(repo) / "snippets" / "logo.html").symlink_to(kit_of(pack) / "snippets" / "logo.html")      # a link with the right bytes behind it is no copy of the file
    r = kit_status(pack, repo)
    assert r.returncode == 1 and listed(r.stdout, "generated files that differ") == ["snippets/logo.html (is a link or a folder, not a file)"]
    (installed_of(repo) / "snippets" / "logo.html").unlink()
    shutil.copy2(kit_of(pack) / "snippets" / "logo.html", installed_of(repo) / "snippets" / "logo.html")
    assert kit_status(pack, repo).returncode == 0                                        # the file back as a file: current again
    (installed_of(repo) / "brand" / "elsewhere").symlink_to(elsewhere)                  # a link to a folder in a generated folder is left over, and is not followed
    r = kit_status(pack, repo)
    assert r.returncode == 1, r.stdout + r.stderr
    assert listed(r.stdout, "left over from an older kit") == ["brand/elsewhere"]


def test_kit_status_cannot_judge_a_copy_against_a_kit_that_is_not_whole_in_the_project(pack, tmp_path):
    assert build(pack).returncode == 0
    repo = install(pack, tmp_path)
    mutate(kit_of(pack) / "brand/assets/tokens/tokens.css", "#4cd7c8", "#4cd7c9")         # the project's own kit, edited by hand: kit check says so
    (kit_of(pack) / "snippets/logo.html").unlink()
    r = kit_status(pack, repo)
    assert r.returncode == 3 and not r.stdout, r.stdout + r.stderr
    assert "the kit in the project is not whole, so no copy can be judged against it" in r.stderr
    assert "brand/assets/tokens/tokens.css (edited by hand)" in r.stderr and "snippets/logo.html (missing)" in r.stderr and "brand-creator kit check" in r.stderr


def test_kit_status_json_holds_the_same_facts_as_the_text(pack, tmp_path):
    assert build(pack).returncode == 0
    fresh, stale = tmp_path / "fresh", install(pack, tmp_path, "stale")
    fresh.mkdir()
    kd = installed_of(stale)
    (kd / "brand/assets/tokens/tokens.css").write_text("edited", encoding="utf-8")
    (kd / "snippets/logo.html").unlink()
    (kd / "brand/old.svg").write_text("<svg/>", encoding="utf-8")
    (kd / "voice.md").write_text("mine", encoding="utf-8")
    (kd / "visual.md").unlink()
    r = kit_status(pack, fresh, stale, extra=("--json",))
    assert r.returncode == 1, r.stdout + r.stderr
    doc = json.loads(r.stdout)
    assert [k for k in doc] == ["kit", "version", "repos", "current"] and doc["kit"] == "acme-brand" and doc["version"] == "1.1" and doc["current"] is False
    a, b = doc["repos"]
    assert (a["label"], a["state"], a["installed_version"], a["project_version"]) == ("fresh", "not installed", None, "1.1")
    assert a["copy"] == COPY_ORDER + OWNER_ORDER and a["copy_owner"] == OWNER_ORDER and a["read_only"] is True
    assert (b["label"], b["state"], b["installed_version"], b["project_version"]) == ("stale", "not current", "1.1", "1.1")
    assert b["differ"] == [{"file": "brand/assets/tokens/tokens.css", "why": "not the same bytes"}] and b["missing"] == ["snippets/logo.html"]
    assert b["left_over"] == ["brand/old.svg"] and b["owner_differ"] == [{"file": "voice.md", "why": "not the same bytes"}]
    assert b["left_over_to"] == "removed-<date>/.claude/skills/acme-brand/" and a["left_over_to"] is None      # where the files left over go in the repository; none left over, none said
    assert b["copy"] == ["brand/assets/tokens/tokens.css", "snippets/logo.html", "visual.md"] and b["copy_owner"] == ["visual.md"]
    assert os.path.realpath(b["path"]) == os.path.realpath(stale)
    r = kit_status(pack, install(pack, tmp_path, "same"), extra=("--json",))
    assert r.returncode == 0 and json.loads(r.stdout)["current"] is True


# ---------------------------------------------------------------- the adoption category `kit`: one row per repository, pinned, left alone by a survey
# The target is tests/fixtures/target-repo (a synthetic repository), copied next to the project as `shop`. The expected row is written out by hand.

KIT_ROW_CHANGE = ("Copy the brand kit: every generated file byte for byte and the owner files the repository does not have, by the list "
                  "`brand-creator kit status --repo <path>` prints; it must then say current. Never into a global skills folder.")


def surveyed(p, tmp_path, *labels):
    """The project `p` with each of `labels` surveyed as an empty product repository (a README only), beside the project. -> {label: folder}"""
    repos = {}
    for label in labels:
        repos[label] = tmp_path / label
        repos[label].mkdir()
        (repos[label] / "README.md").write_text("the product\n", encoding="utf-8")
    r = bc("adoption", "survey", *[a for label, d in repos.items() for a in ("--repo", f"{d}={label}")], project=p)
    assert r.returncode == 0, r.stdout + r.stderr
    return repos


def adoption_doc(p) -> dict:
    return json.loads((p / "adoption.json").read_text(encoding="utf-8"))


@pytest.mark.requires_rg
def test_a_kit_row_is_added_for_a_surveyed_repository_and_a_survey_leaves_it_alone(pack, tmp_path):
    assert build(pack).returncode == 0
    shop = tmp_path / "shop"
    shutil.copytree(ROOT / "tests" / "fixtures" / "target-repo", shop)
    survey = ("adoption", "survey", "--repo", f"{shop}=shop", "--old-name", "Oldco")
    assert bc(*survey, project=pack).returncode == 0
    n0 = len(adoption_doc(pack)["rows"])
    assert n0 > 0 and all(r["category"] != "kit" for r in adoption_doc(pack)["rows"])
    r = bc("adoption", "add", "--repo", "shop", "--kit", project=pack)
    assert r.returncode == 0, r.stdout + r.stderr
    doc = adoption_doc(pack)
    assert doc["rows"][-1] == {"n": n0 + 1, "category": "kit", "repo": "r1", "file": ".claude/skills/acme-brand/", "lines": [], "find": "kit.json", "change": KIT_ROW_CHANGE}
    assert doc["nrows"] == n0 + 1 and doc["pins"][str(n0 + 1)] == "r1|kit|.claude/skills/acme-brand/"      # pinned like any row
    md = (pack / "ADOPTION.md").read_text(encoding="utf-8")
    assert f"| {n0 + 1} | to do | Brand kit | shop | `.claude/skills/acme-brand/` | the whole folder | `kit.json` | {KIT_ROW_CHANGE} | <!-- target-repo -->" in md
    assert "Brand kit 1." in md and "match nothing" not in md
    assert bc("adoption", "verify", project=pack).returncode == 0
    assert bc(*survey, project=pack).returncode == 0                                                         # a survey adds no row for a kit and takes none away
    again = adoption_doc(pack)
    assert again["rows"] == doc["rows"] and again["pins"] == doc["pins"] and again["nrows"] == n0 + 1 and str(n0 + 1) not in again["seen"]
    assert "match nothing" not in (pack / "ADOPTION.md").read_text(encoding="utf-8")
    assert bc("adoption", "verify", project=pack).returncode == 0
    mutate_json(pack / "adoption.json", lambda d: d["rows"][-1].update({"file": ".claude/skills/other-brand/"}))
    r = bc("adoption", "verify", project=pack)                                                               # and the pin catches an edit of it
    assert r.returncode == 1 and "pinned" in r.stderr


@pytest.mark.requires_rg
def test_a_kit_row_needs_a_kit_in_the_project_and_is_one_per_repository(pack, tmp_path):
    repos = surveyed(pack, tmp_path, "site", "app")
    before = (pack / "adoption.json").read_bytes()
    r = bc("adoption", "add", "--repo", "site", "--kit", project=pack)
    assert r.returncode == 2 and "no kit in this project" in r.stderr and "kit build --yes" in r.stderr, r.stdout + r.stderr
    assert (pack / "adoption.json").read_bytes() == before
    assert build(pack).returncode == 0
    r = bc("adoption", "add", "--repo", "elsewhere", "--kit", project=pack)
    assert r.returncode == 2 and "not a surveyed repository" in r.stderr and "site, app" in r.stderr
    for flag, value in (("--file", "a"), ("--find", "b"), ("--change", "c"), ("--lines", "3")):               # a kit row says what it is: it takes no words of its own
        r = bc("adoption", "add", "--repo", "site", "--kit", flag, value, project=pack)
        assert r.returncode == 2 and f"{flag}" in r.stderr and "--kit" in r.stderr, (flag, r.stdout + r.stderr)
    assert (pack / "adoption.json").read_bytes() == before
    r = bc("adoption", "add", "--repo", "site", "--file", "a", "--find", "b", project=pack)                  # without --kit the three words are still all needed
    assert r.returncode == 2 and "required: --change" in r.stderr
    assert (pack / "adoption.json").read_bytes() == before
    assert bc("adoption", "add", "--repo", "site", "--kit", project=pack).returncode == 0
    after_one = adoption_doc(pack)
    r = bc("adoption", "add", "--repo", "site", "--kit", project=pack)                                       # one kit row per repository
    assert r.returncode == 2 and "already has a kit row" in r.stderr and "row 1" in r.stderr, r.stdout + r.stderr
    assert adoption_doc(pack) == after_one
    assert bc("adoption", "add", "--repo", "app", "--kit", project=pack).returncode == 0                     # another repository gets its own
    doc = adoption_doc(pack)
    assert [(r["n"], r["category"], r["repo"]) for r in doc["rows"]] == [(1, "kit", "r1"), (2, "kit", "r2")] and doc["nrows"] == 2
    assert doc["pins"] == {"1": "r1|kit|.claude/skills/acme-brand/", "2": "r2|kit|.claude/skills/acme-brand/"}
    assert bc("adoption", "verify", project=pack).returncode == 0
    assert all(not (d / ".claude").exists() for d in repos.values())                                         # no repository was written to


@pytest.mark.requires_rg
def test_a_kit_row_refuses_an_empty_value_of_each_flag_it_does_not_take_lines_included(pack, tmp_path):
    surveyed(pack, tmp_path, "site")
    assert build(pack).returncode == 0
    before = (pack / "adoption.json").read_bytes()
    for flag in ("--file", "--find", "--change", "--lines"):                                                 # an empty value is a value that would be dropped, not "no value"
        r = bc("adoption", "add", "--repo", "site", "--kit", flag, "", project=pack)
        assert r.returncode == 2 and f"argument {flag}: not allowed with argument --kit" in r.stderr, (flag, r.stdout + r.stderr)
    assert (pack / "adoption.json").read_bytes() == before                                                   # nothing was added
    assert bc("adoption", "add", "--repo", "site", "--kit", project=pack).returncode == 0                    # without any of them the row is still added
    assert [r["category"] for r in adoption_doc(pack)["rows"]] == ["kit"]


@pytest.mark.requires_rg
def test_adoption_status_says_whether_each_kit_copy_is_current(pack, tmp_path):
    assert build(pack).returncode == 0
    repos = surveyed(pack, tmp_path, "site", "app", "web")
    status = ("adoption", "status")
    r = bc(*status, project=pack)
    assert r.returncode == 0 and "kit copies" not in r.stdout and "kit" not in json.loads(bc(*status, "--json", project=pack).stdout)   # no kit row: the output is as it was
    for label in repos:
        assert bc("adoption", "add", "--repo", label, "--kit", project=pack).returncode == 0
    shutil.copytree(kit_of(pack), installed_of(repos["site"]))                                               # site: a byte copy
    shutil.copytree(kit_of(pack), installed_of(repos["web"]))                                                # web: a copy with one file changed; app: nothing
    (installed_of(repos["web"]) / "brand/assets/tokens/tokens.css").write_text("edited", encoding="utf-8")
    watched = {"project": (pack, tree_of(pack)), **{label: (d, tree_of(d)) for label, d in repos.items()}}
    r = bc(*status, project=pack)
    assert r.returncode == 0, r.stdout + r.stderr                                                            # a copy that is not current does not fail the status
    lines = r.stdout.splitlines()
    assert lines[:2] == [lines[0], "not done: 1-3"] and lines[0].startswith("not started: 0 of 3 rows done, 0 doing, 3 to do.")      # the counts first
    assert lines[2:] == ["kit copies (read only; `brand-creator kit status` has the copy list):", "  site: current (version 1.1)", "  app: not installed",
                         "  web: not current (version 1.1 on both sides, but 1 file differs)"], lines                        # the same wording as `kit status`: not "installed 1.1, project 1.1"
    for what, (folder, state) in watched.items():
        assert tree_of(folder) == state, f"{what} was written to"                                            # it reads only
    assert not list((pack / "assets" / "_checks").glob("*status*"))
    shown = json.loads(bc(*status, "--json", project=pack).stdout)
    assert list(shown) == ["headline", "counts", "rows", "kit"] and shown["rows"] == 3 and shown["counts"] == {"to do": 3, "doing": 0, "done": 0}
    assert shown["kit"] == [{"label": "site", "state": "current", "installed_version": "1.1", "project_version": "1.1"},
                            {"label": "app", "state": "not installed", "installed_version": None, "project_version": "1.1"},
                            {"label": "web", "state": "not current", "installed_version": "1.1", "project_version": "1.1"}]
    shutil.copy2(kit_of(pack) / "brand/assets/tokens/tokens.css", installed_of(repos["web"]) / "brand/assets/tokens/tokens.css")       # the copy made current
    shutil.copytree(kit_of(pack), installed_of(repos["app"]))
    r = bc(*status, project=pack)
    assert r.returncode == 0 and r.stdout.splitlines()[2:] == ["kit copies (read only; `brand-creator kit status` has the copy list):", "  site: current (version 1.1)",
                                                               "  app: current (version 1.1)", "  web: current (version 1.1)"], r.stdout
    # a copy whose kit.json states another version names both versions; one with a file missing and one left over, on the same version, counts what differs
    mutate_json(installed_of(repos["app"]) / "kit.json", lambda d: d.__setitem__("version", "1.0"))
    (installed_of(repos["web"]) / "snippets/logo.html").unlink()
    (installed_of(repos["web"]) / "brand/old.txt").write_text("a file of an older kit", encoding="utf-8")
    (installed_of(repos["web"]) / "brand/assets/tokens/tokens.css").write_text("edited", encoding="utf-8")
    r = bc(*status, project=pack)
    assert r.returncode == 0 and r.stdout.splitlines()[3:] == ["  site: current (version 1.1)", "  app: not current (installed version 1.0, project version 1.1)",
                                                               "  web: not current (version 1.1 on both sides, but 1 file differs, 1 file is missing, 1 file is left over from an older kit)"], r.stdout
    shown = json.loads(bc(*status, "--json", project=pack).stdout)["kit"]                                    # the JSON keeps its four keys
    assert [list(k) for k in shown] == [["label", "state", "installed_version", "project_version"]] * 3 and [k["installed_version"] for k in shown] == ["1.1", "1.0", "1.1"]
    # a project kit that cannot be read is said, on stderr, and does not fail the status
    (kit_of(pack) / "snippets/logo.html").unlink()
    r = bc(*status, project=pack)
    assert r.returncode == 0 and "kit copies" not in r.stdout, r.stdout + r.stderr
    assert "warning: the kit copies were not read: the kit in the project is not whole" in r.stderr
    shutil.rmtree(kit_of(pack))
    r = bc(*status, "--json", project=pack)
    shown = json.loads(r.stdout)
    assert r.returncode == 0 and "no kit in this project" in r.stderr and "kit" not in shown, r.stdout + r.stderr
    assert shown["kit_unread"].startswith("no kit in this project") and list(shown) == ["headline", "counts", "rows", "kit_unread"]        # and the JSON says it was not read


# ---------------------------------------------------------------- the committed Acme kit the kit-test-hero eval starts from
# evals/_shared/acme-kit/ is a snapshot, so the billed eval needs no build step. tests/tools/regen_eval_kit.py rebuilds it.
EVAL_KIT = ROOT / "evals" / "_shared" / "acme-kit"


def files_of(d) -> list[str]:
    return sorted(f.relative_to(d).as_posix() for f in d.rglob("*") if f.is_file())


def test_the_eval_kit_snapshot_is_what_kit_build_writes_for_acme(pack):
    """The snapshot is the kit of the Acme pack, built, its owner files filled with fill_owned's text, and built again. kit.json holds `plugin_version`, which changes at
    every release, so it is dropped on both sides before the two are compared; every other file is compared byte for byte. When this fails, run tests/tools/regen_eval_kit.py
    (it needs a set-up data directory) and commit the folder."""
    filled_kit(pack)
    built = kit_of(pack)
    assert files_of(EVAL_KIT) == files_of(built), "the files differ: run tests/tools/regen_eval_kit.py"
    assert "kit.json" in files_of(built) and "snippets/logo.html" in files_of(built) and "brand/assets/tokens/tokens.css" in files_of(built)
    for rel in files_of(built):
        if rel == "kit.json":
            continue
        assert (EVAL_KIT / rel).read_bytes() == (built / rel).read_bytes(), f"{rel} differs from what the build writes now: run tests/tools/regen_eval_kit.py"
    snap_json, built_json = (json.loads((d / "kit.json").read_text(encoding="utf-8")) for d in (EVAL_KIT, built))
    assert snap_json.pop("plugin_version") and built_json.pop("plugin_version")                  # both name a version; the version itself is not compared
    assert snap_json == built_json, "kit.json differs (plugin_version apart): run tests/tools/regen_eval_kit.py"
    for rel in OWNER_FILES:                                                                      # the owner files are filled in, not the scaffolds
        assert "[[fill:" not in (EVAL_KIT / rel).read_text(encoding="utf-8"), rel
    for rel in ("voice.md", "visual.md", "golden-rules.md"):
        assert "Keep it short. [example]" in (EVAL_KIT / rel).read_text(encoding="utf-8"), rel


# ---------------------------------------------------------------- kit check, part 2: tags and values
# `kit check` judges the owner's recipes (recipes/**/*.md), golden-rules.md, visual.md and the generated reference-pages/<id>/notes.md in two rows. kit:tags: a bullet (and, in golden-rules.md and
# visual.md, a numbered line) outside a code fence carries `[example]` or a `[rule: <id>]` of a rule the kit knows. kit:numbers: a value (a number with a unit, a ratio, a hex colour, rgb( hsl( oklch()
# has a citation on its own line, code fences included: `[example]`, a known rule id, or a token that exists in the kit's own tokens.css (`var(--name)`) or tokens.json (`{dotted.path}`).
# After `filled_kit` the owner files hold the one line `Keep it short. [example]` at line 5 (golden-rules.md, visual.md, voice.md), and the Acme recipe is 19 lines long, ending
# "The other pages follow the same steps." The tokens Acme builds include --dimension-space-1 (4px), --dimension-space-2 (8px) and --color-bg, and tokens.json names dimension.space-2 and color.bg.
TAG_HINT = "tag each with `[example]` or `[rule: <id>]`, an id of rules.json (a rule of the brand written bare, `page:<id>`, `site:<id>`)"
VALUE_HINT = "cite a token (`var(--name)` of tokens.css, `{dotted.path}` of tokens.json) or a known `[rule: <id>]`, or tag the line `[example]`"
KEPT = "Keep it short. [example]"
CLEAR_SPACE = "the-mark-keeps-its-clear-space"
RECIPE_LAST = "The other pages follow the same steps."
NO_TAGS = "no bullet or numbered line needs a tag"
NO_VALUES = "no value (a number with a unit, a ratio or a colour) needs a citation"


def lack_a_tag(n_bad, n_all, *items):
    return f"{n_bad} of {n_all} line(s) lack a valid tag: {', '.join(items)}; {TAG_HINT}"


def cites_nothing(*items):
    return f"{len(items)} line(s) hold a value with no citation or a token that does not exist: {', '.join(items)}; {VALUE_HINT}"


def test_an_untagged_rule_in_golden_rules_fails_and_a_tagged_one_passes(pack):
    record_rules(pack, "The mark keeps its clear space")
    filled_kit(pack)
    assert kit_check(pack).returncode == 0 and statuses(pack) == ALL_PASS
    assert check_report_rows(pack)["kit:tags"]["detail"] == NO_TAGS
    rules = kit_of(pack) / "golden-rules.md"
    mutate(rules, KEPT, KEPT + "\n\n- Never stretch the mark.\n1. Keep the clear space.\n```\n- inside a fence\n```")
    r = kit_check(pack)
    assert r.returncode == 1, r.stdout + r.stderr
    row = check_report_rows(pack)["kit:tags"]
    assert row["status"] == "fail" and "[FAIL] kit:tags" in r.stdout
    assert row["detail"] == lack_a_tag(2, 2, "golden-rules.md:7 untagged", "golden-rules.md:8 untagged")      # the bullet and the numbered line; the line in the fence is none
    assert statuses(pack) == {**ALL_PASS, "kit:tags": "fail", "kit:owned": "warn"}                             # the lines hold no value, and the owner's edit is only a warning
    mutate(rules, "- Never stretch the mark.", "- Never stretch the mark. [example]")
    assert kit_check(pack).returncode == 1
    assert check_report_rows(pack)["kit:tags"]["detail"] == lack_a_tag(1, 2, "golden-rules.md:8 untagged")
    mutate(rules, "1. Keep the clear space.", f"1. Keep the clear space. [rule: {CLEAR_SPACE}]")
    r = kit_check(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert check_report_rows(pack)["kit:tags"]["detail"] == "2 line(s) carry `[example]` or a rule id the kit knows"
    assert statuses(pack) == {**ALL_PASS, "kit:owned": "warn"}
    assert build(pack).returncode == 0 and kit_check(pack).returncode == 0 and statuses(pack) == ALL_PASS      # the build records the owner's words; the tags stay


def test_which_lines_need_a_tag_and_which_do_not(pack):
    filled_kit(pack)
    rules = kit_of(pack) / "golden-rules.md"
    mutate(rules, KEPT, KEPT + "\n\n* A star bullet.\n   - A nested bullet.\n* * *\n- - -\n---\n**Bold** words.\n-dash-first words.\n2) A numbered line.\n10. Another.\n1.5 is no list.\n"
                              "| - | table |\n> - quoted\n")
    # lines 7 and 8 are bullets (a star, an indented one), 9 to 11 thematic breaks, 12 bold text, 13 no space after the dash, 14 and 15 numbered lines ("2)" and "10."),
    # 16 a decimal, 17 a table row and 18 a quote: only 7, 8, 14 and 15 need a tag
    assert kit_check(pack).returncode == 1
    assert check_report_rows(pack)["kit:tags"]["detail"] == lack_a_tag(
        4, 4, "golden-rules.md:7 untagged", "golden-rules.md:8 untagged", "golden-rules.md:14 untagged", "golden-rules.md:15 untagged")
    for line in ("* A star bullet.", "   - A nested bullet.", "2) A numbered line.", "10. Another."):
        mutate(rules, line, line + " [example]")
    r = kit_check(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert check_report_rows(pack)["kit:tags"]["detail"] == "4 line(s) carry `[example]` or a rule id the kit knows"
    visual = kit_of(pack) / "visual.md"                                       # visual.md is judged like golden-rules.md: a numbered line needs a tag there too
    mutate(visual, KEPT, KEPT + "\n\n1. Tall pictures.\n- Wide pictures. [example]")
    assert kit_check(pack).returncode == 1
    assert check_report_rows(pack)["kit:tags"]["detail"] == lack_a_tag(1, 6, "visual.md:7 untagged")
    mutate(visual, "1. Tall pictures.", "1. Tall pictures. [example]")
    assert kit_check(pack).returncode == 0 and check_report_rows(pack)["kit:tags"]["detail"] == "6 line(s) carry `[example]` or a rule id the kit knows"


def test_a_rule_tag_must_name_a_rule_the_kit_knows(pack):
    record_rules(pack, "The mark keeps its clear space", "Never stretch the mark")                # the ids: the-mark-keeps-its-clear-space and never-stretch-the-mark
    mutate_json(pack / "qa" / "rules.json", lambda d: d.__setitem__("page", {"rules": [
        {"id": "one-mark", "kind": "max-marks-per-view", "max": 1, "g4": "one mark per screen"}]}))                        # page:one-mark
    filled_kit(pack)
    site = {"schema": 1, "approved": "2026-10-17 (test)", "round": 1, "hero": "a", "pages": [],
            "choices": [{"id": "c1", "text": "the footer repeats the contact line", "tag": "rule", "source": "DECISIONS.md"},
                        {"id": "c2", "text": "a calm blue", "tag": "example", "source": ""}]}
    (pack / "site").mkdir()
    (pack / "site" / "site.json").write_text(json.dumps(site), encoding="utf-8")                                           # read at check time: site:c1 is a rule, site:c2 is an example
    rules = kit_of(pack) / "golden-rules.md"
    good = [f"- Keep the clear space. [rule: {CLEAR_SPACE}]", "- Never stretch. [rule: never-stretch-the-mark]", "- One mark. [rule: page:one-mark]",
            "- The footer. [rule: site:c1]", "- Both tags. [example] [rule: page:one-mark]", "-  Spaces inside. [rule:  site:c1 ]"]
    mutate(rules, KEPT, KEPT + "\n\n" + "\n".join(good))                                                                 # lines 7 to 12
    kit_check(pack)
    assert statuses(pack)["kit:tags"] == "pass" and statuses(pack)["kit:numbers"] == "pass"
    assert check_report_rows(pack)["kit:tags"]["detail"] == "6 line(s) carry `[example]` or a rule id the kit knows"
    good_text = rules.read_text(encoding="utf-8")
    for line, said in (("- A calm blue. [rule: site:c2]", "site:c2"),                                                      # a choice tagged example is no rule
                       ("- A typo. [rule: the-mark-keeps-its-clear-spac]", "the-mark-keeps-its-clear-spac"),
                       ("- The case. [rule: Never-Stretch-The-Mark]", "Never-Stretch-The-Mark"),
                       ("- A page rule. [rule: page:nope]", "page:nope"),
                       ("- A choice. [rule: site:c9]", "site:c9"),
                       ("- Empty. [rule: ]", "(empty)"),
                       ("- Beside an example. [example] [rule: nope]", "nope"),
                       ("- Two tags. [rule: never-stretch-the-mark] [rule: nope-either]", "nope-either"),
                       ("1. A numbered line. [rule: page:one-mark, site:c1]", "page:one-mark, site:c1")):                  # one id to a tag
        rules.write_text(good_text + line + "\n", encoding="utf-8")
        assert kit_check(pack).returncode == 1, line
        assert check_report_rows(pack)["kit:tags"]["detail"] == lack_a_tag(1, 7, f"golden-rules.md:13 unknown rule id {said}"), line
    rules.write_text(good_text, encoding="utf-8")
    kit_check(pack)
    assert statuses(pack)["kit:tags"] == "pass"
    (pack / "site" / "site.json").unlink()                                                                                 # without the record, site:c1 is no rule the kit knows
    kit_check(pack)
    assert check_report_rows(pack)["kit:tags"]["detail"] == lack_a_tag(
        2, 6, "golden-rules.md:10 unknown rule id site:c1", "golden-rules.md:12 unknown rule id site:c1")


def test_a_rule_tag_that_names_no_rule_fails_on_any_line_even_one_that_needs_no_tag_and_holds_no_value(pack):
    record_rules(pack, "The mark keeps its clear space")
    filled_kit(pack)
    recipe, golden = kit_of(pack) / "recipes" / "web-page.md", kit_of(pack) / "golden-rules.md"
    kit_check(pack)
    assert statuses(pack) == ALL_PASS
    recipe_was, golden_was = recipe.read_text(encoding="utf-8"), golden.read_text(encoding="utf-8")      # the recipe ends on line 19, golden-rules.md on line 5: the line to try is 21, or 7
    for file, was, last, body, where in ((recipe, recipe_was, RECIPE_LAST, "8. Keep the clear space. [rule: nope]", "recipes/web-page.md:21"),              # a numbered step of a recipe: no tag needed, no value
                                         (golden, golden_was, KEPT, "Keep the clear space. [rule: nope]", "golden-rules.md:7"),                              # a plain sentence: no bullet, no value
                                         (golden, golden_was, KEPT, "## Clear space [rule: nope]", "golden-rules.md:7"),                                    # a heading
                                         (golden, golden_was, KEPT, "> Keep the clear space. [rule: nope]", "golden-rules.md:7"),                           # a quote
                                         (recipe, recipe_was, RECIPE_LAST, "```\nKeep the clear space. [rule: nope]\n```", "recipes/web-page.md:22")):    # a line of a code fence, where no bullet needs a tag
        mutate(file, last, last + "\n\n" + body)
        r = kit_check(pack)
        assert r.returncode == 1, (body, r.stdout + r.stderr)
        assert check_report_rows(pack)["kit:tags"]["status"] == "fail" and "[FAIL] kit:tags" in r.stdout, body
        assert check_report_rows(pack)["kit:tags"]["detail"] == lack_a_tag(1, 1, f"{where} unknown rule id nope"), body
        assert statuses(pack)["kit:numbers"] == "pass", body                                                  # the line holds no value: the value row has nothing to say about it
        mutate(file, "nope", CLEAR_SPACE)                                                                     # the same line with a rule the kit knows
        assert kit_check(pack).returncode == 0, body
        assert check_report_rows(pack)["kit:tags"]["detail"] == "1 line(s) carry `[example]` or a rule id the kit knows", body
        file.write_text(was, encoding="utf-8")
    kit_check(pack)
    assert statuses(pack) == ALL_PASS                                                                         # both files are as the build recorded them again


def test_a_rule_tag_whose_id_is_a_placeholder_in_angle_brackets_shows_the_syntax_and_is_no_citation(pack):
    record_rules(pack, "The mark keeps its clear space")
    filled_kit(pack)
    golden = kit_of(pack) / "golden-rules.md"
    before = mutate(golden, KEPT, KEPT + "\n")                                                                                # line 5 is KEPT; the lines to try follow a blank line 6
    # a placeholder shows the syntax: the tag with `<id>` (or any `<...>`, with a `page:` or `site:` before it) names no id, so it is never judged against the rules the kit knows
    shown = ["- Write a tag as `[rule: <id>]` or `[rule: <rule id>]`. [example]",
             "- A page rule is `[rule: page:<id>]`, a choice of a reference page `[rule: site:<id>]`, any other `[rule: <...>]` and `[rule: <>]`. [example]",
             "Write [rule:<id>] after the line it backs, or [rule:  <the rule's id>  ].",
             "```\n[rule: <id>]\n- [rule: <id>] [example]\n```"]
    golden.write_text(before + "\n" + "\n".join(shown) + "\n", encoding="utf-8")                                              # lines 7 and 8 are bullets; 9 is a sentence; 10 to 13 a fence
    r = kit_check(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert check_report_rows(pack)["kit:tags"]["detail"] == "2 line(s) carry `[example]` or a rule id the kit knows"          # only the two bullets are judged
    assert statuses(pack)["kit:tags"] == "pass" and statuses(pack)["kit:numbers"] == "pass"
    # a real rule next to a placeholder still counts, and an unknown one still fails, on a line of any kind
    golden.write_text(before + f"\n- Mind it. [rule: <id>] [rule: {CLEAR_SPACE}]\n", encoding="utf-8")
    assert kit_check(pack).returncode == 0 and check_report_rows(pack)["kit:tags"]["detail"] == "1 line(s) carry `[example]` or a rule id the kit knows"
    for line, where in (("- Mind it. [rule: <id>] [example] [rule: nope]", 7), ("Write [rule: <id>] or [rule: nope].", 7), ("## Tags [rule: nope] [rule: <id>]", 7),
                        ("```\n[rule: <id>] [rule: nope]\n```", 8), ("- [rule: page:<id> ] [rule: nope]", 7)):
        golden.write_text(before + "\n" + line + "\n", encoding="utf-8")
        assert kit_check(pack).returncode == 1, line
        assert check_report_rows(pack)["kit:tags"]["detail"] == lack_a_tag(1, 1, f"golden-rules.md:{where} unknown rule id nope"), line
    for line in ("[rule: page:]", "[rule: id>]", "[rule: <id>x]", "[rule: x<id>]", "[rule: site:<id>x]", "[rule: <<id>]", "[rule: <a><b>]", "[rule: other:<id>]"):
        golden.write_text(before + "\n" + line + "\n", encoding="utf-8")                                                      # not a placeholder: a whole `<...>`, or `page:` or `site:` and then one
        assert kit_check(pack).returncode == 1, line
        assert "unknown rule id" in check_report_rows(pack)["kit:tags"]["detail"], line
    golden.write_text(before, encoding="utf-8")
    kit_check(pack)
    assert statuses(pack) == ALL_PASS


def test_a_placeholder_tag_is_no_citation_for_a_bullet_or_a_value(pack):
    record_rules(pack, "The mark keeps its clear space")
    filled_kit(pack)
    golden = kit_of(pack) / "golden-rules.md"
    before = mutate(golden, KEPT, KEPT + "\n")
    golden.write_text(before + "\n- Write a tag as `[rule: <id>]`.\n", encoding="utf-8")                                      # a bullet that only shows the syntax still needs its own tag
    r = kit_check(pack)
    assert r.returncode == 1, r.stdout + r.stderr
    assert check_report_rows(pack)["kit:tags"]["detail"] == lack_a_tag(1, 1, "golden-rules.md:7 untagged")
    golden.write_text(before + "\n- Write a tag as `[rule: <id>]`. [example]\n", encoding="utf-8")
    assert kit_check(pack).returncode == 0 and statuses(pack)["kit:tags"] == "pass"
    golden.write_text(before + "\n- Hero padding 48px [rule: <id>]\n", encoding="utf-8")                                       # a value is cited by a rule the kit knows, not by the syntax of one
    assert kit_check(pack).returncode == 1
    assert check_report_rows(pack)["kit:tags"]["detail"] == lack_a_tag(1, 1, "golden-rules.md:7 untagged")
    assert check_report_rows(pack)["kit:numbers"]["detail"] == cites_nothing("golden-rules.md:7 (48px has no citation)")
    golden.write_text(before + "\n```\npadding: 48px; /* [rule: <id>] */\n```\n", encoding="utf-8")
    assert kit_check(pack).returncode == 1
    assert check_report_rows(pack)["kit:numbers"]["detail"] == cites_nothing("golden-rules.md:8 (48px has no citation)")
    assert statuses(pack)["kit:tags"] == "pass"                                                                              # a line of a code fence needs no tag
    golden.write_text(before + "\n```\npadding: 48px; /* [rule: <id>] [example] */\n```\n", encoding="utf-8")
    assert kit_check(pack).returncode == 0 and statuses(pack)["kit:numbers"] == "pass"
    golden.write_text(before + f"\n- Hero padding 48px [rule: <id>] [rule: {CLEAR_SPACE}]\n", encoding="utf-8")                # a real rule beside the syntax cites it
    assert kit_check(pack).returncode == 0 and statuses(pack)["kit:numbers"] == "pass"
    golden.write_text(before + "\nPad it. [rule: <the 48px rule, at 4.5:1>]\n", encoding="utf-8")                           # the words of a tag are no values, those of a placeholder too
    assert kit_check(pack).returncode == 0
    assert check_report_rows(pack)["kit:numbers"]["detail"] == NO_VALUES
    (pack / "site").mkdir()
    (pack / "site" / "site.json").write_text("{not json", encoding="utf-8")                                                  # the ids cannot be read, but a placeholder names none: nothing is left unjudged
    golden.write_text(before + "\n- Write a tag as `[rule: <id>]`. [example]\n", encoding="utf-8")
    kit_check(pack)                                                                                                          # the record is a source of the kit, so the run as a whole is not verified; the tag rows are
    assert statuses(pack)["kit:tags"] == "pass" and statuses(pack)["kit:numbers"] == "pass"
    assert check_report_rows(pack)["kit:tags"]["detail"] == "1 line(s) carry `[example]` or a rule id the kit knows"


def test_a_value_in_a_recipe_needs_a_token_a_rule_or_the_example_tag(pack):
    record_rules(pack, "The mark keeps its clear space")
    filled_kit(pack)
    assert kit_check(pack).returncode == 0 and statuses(pack) == ALL_PASS
    assert check_report_rows(pack)["kit:numbers"]["detail"] == NO_VALUES
    recipe = kit_of(pack) / "recipes" / "web-page.md"
    mutate(recipe, RECIPE_LAST, RECIPE_LAST + "\n\n- Hero padding 48px")                                                      # line 21
    r = kit_check(pack)
    assert r.returncode == 1, r.stdout + r.stderr
    assert check_report_rows(pack)["kit:tags"]["detail"] == lack_a_tag(1, 1, "recipes/web-page.md:21 untagged")
    assert check_report_rows(pack)["kit:numbers"]["detail"] == cites_nothing("recipes/web-page.md:21 (48px has no citation)")
    assert statuses(pack) == {**ALL_PASS, "kit:tags": "fail", "kit:numbers": "fail", "kit:owned": "warn"}
    mutate(recipe, "- Hero padding 48px", "- Hero padding 48px [example]")
    r = kit_check(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert check_report_rows(pack)["kit:numbers"]["detail"] == "1 value(s) on 1 line(s) cite a token, a known rule or `[example]`"
    assert statuses(pack) == {**ALL_PASS, "kit:owned": "warn"}
    mutate(recipe, "48px [example]", f"48px [rule: {CLEAR_SPACE}]")                                                           # a rule of the brand cites the value as well
    assert kit_check(pack).returncode == 0 and statuses(pack) == {**ALL_PASS, "kit:owned": "warn"}
    mutate(recipe, f"48px [rule: {CLEAR_SPACE}]", "48px [rule: page:nope]")                                                   # an id the kit does not know cites nothing
    assert kit_check(pack).returncode == 1
    assert check_report_rows(pack)["kit:tags"]["detail"] == lack_a_tag(1, 1, "recipes/web-page.md:21 unknown rule id page:nope")
    assert check_report_rows(pack)["kit:numbers"]["detail"] == cites_nothing("recipes/web-page.md:21 (48px has no citation; unknown rule id page:nope)")
    mutate(recipe, "- Hero padding 48px [rule: page:nope]", "Hero padding 48px")                                                # a plain line is no bullet, but its value still needs a citation
    assert kit_check(pack).returncode == 1
    assert check_report_rows(pack)["kit:tags"]["detail"] == NO_TAGS
    assert check_report_rows(pack)["kit:numbers"]["detail"] == cites_nothing("recipes/web-page.md:21 (48px has no citation)")
    mutate(recipe, "Hero padding 48px", "Hero padding 48px (var(--dimension-space-2) doubled)")                              # a token cites it
    assert kit_check(pack).returncode == 0 and statuses(pack) == {**ALL_PASS, "kit:owned": "warn"}


def test_a_token_reference_must_exist_in_the_kit_tokens(pack):
    filled_kit(pack)
    recipe = kit_of(pack) / "recipes" / "web-page.md"
    before = mutate(recipe, RECIPE_LAST, RECIPE_LAST + "\n\nA placeholder line.")                                             # the line to try is line 21, after a blank line 20
    for line in ("Pad the hero with 8px: var(--dimension-space-2).", "Pad the hero with 8px: {dimension.space-2}.", "Text on {color.bg} in dark, {modes.dark.color.bg}, 8px.",
                 "Pad the hero with 4px: var( --dimension-space-1 ) and 8px.", "- Pad the hero with 8px: {other.dimension.space-2}. [example]", "A {{placeholder.name}} and ${a.b} and {nothing} are no references.",
                 "```jsx\nexport const Hero = (props) => <h1>{props.title}</h1>;\n```",                                          # a component sample with no value on the line: braces are the language
                 "```css\n.card { --pad: var(--dimension-space-2); padding: var(--pad); }\n```",                                # a custom property of the sample is no token
                 "```css\n.card { color: var(--nope); }\n```",                                                                  # inside a fence a line with no value is not judged, whatever it references
                 "- Show `{props}` or `{{props.title}}` or `${props.title}` in the h1. [example]",                                 # a placeholder in a code span is no reference when it has no dot, or its braces are doubled or follow a dollar
                 "Pad the hero with 8px: {modes.dark.color.bg}, {other.dimension.space-2} and {primitives.color.ink}."):
        recipe.write_text(before + f"\n{line}\n", encoding="utf-8")
        assert kit_check(pack).returncode == 0, (line, check_report_rows(pack)["kit:numbers"]["detail"])
        assert statuses(pack)["kit:numbers"] == "pass", line
    css_gone = "is not declared in brand/assets/tokens/tokens.css"
    json_gone = "is not a path in brand/assets/tokens/tokens.json"
    for line, why in (("Pad the hero with 8px: var(--space-99).", f"8px has no citation; var(--space-99) {css_gone}"),
                      ("Pad the hero with 8px: {dimension.space-99}.", f"8px has no citation; {{dimension.space-99}} {json_gone}"),
                      ("Pad the hero with 8px: var(--dimension-space).", f"8px has no citation; var(--dimension-space) {css_gone}"),
                      ("Pad the hero with 8px: {dimension}.", "8px has no citation"),                                            # one name is no dotted path, so it is no reference
                      ("Use var(--nope) for the hero.", f"var(--nope) {css_gone}"),                                              # outside a code fence a reference is judged on every line: no value on it, still no token
                      ("- Use {color.nope} here. [example]", f"{{color.nope}} {json_gone}"),                                     # and the example tag does not excuse it
                      ("A {color.bg} and {color.nope} and var(--nope) and var(--color-bg).", f"var(--nope) {css_gone}; {{color.nope}} {json_gone}"),   # every one that does not exist is named, the ones that do are not
                      ("- Pad 8px of {color.nope} here. [example]", f"{{color.nope}} {json_gone}"),                             # on a line with a value the example tag does not save a reference that does not exist
                      ("```css\n.card { padding: 8px var(--pad); } /* [example] */\n```", f"var(--pad) {css_gone}"),                 # nor in a code fence: a sample with a value keeps its custom properties on lines of their own
                      ("Pad 8px: var(--dimension-space-2) and var(--space-99).", f"var(--space-99) {css_gone}"),                # one that exists does not excuse one that does not
                      ("Pad 8px [example] var(--nope) {color.bg}.", f"var(--nope) {css_gone}"),
                      ("- Use `{props.title}` in the h1. [example]", f"{{props.title}} {json_gone}"),                           # a {dotted.path} in a code span of prose is a reference too: braces are read wherever no code fence is
                      ("Pad the hero with 8px: {modes.light}.", f"8px has no citation; {{modes.light}} {json_gone}"),            # a group of tokens.json is no token ...
                      ("Pad the hero with 8px: {modes.dark}.", f"8px has no citation; {{modes.dark}} {json_gone}"),
                      ("Pad the hero with 8px: {modes.light.color.bg.hex}.", f"8px has no citation; {{modes.light.color.bg.hex}} {json_gone}"),   # ... nor is a part of one
                      ("Pad the hero with 8px: {modes.light.color.bg.ref}.", f"8px has no citation; {{modes.light.color.bg.ref}} {json_gone}"),
                      ("Pad the hero with 8px: {primitives.nope}.", f"8px has no citation; {{primitives.nope}} {json_gone}")):
        recipe.write_text(before + f"\n{line}\n", encoding="utf-8")
        at = 22 if line.startswith("```") else 21                                                                                # a fence opens on line 21, its sample is line 22
        assert kit_check(pack).returncode == 1, line
        assert check_report_rows(pack)["kit:numbers"]["detail"] == cites_nothing(f"recipes/web-page.md:{at} ({why})"), line
    recipe.write_text(before + "\nPad the hero with 8px: var(--dimension-space-2).\n", encoding="utf-8")
    (kit_of(pack) / "brand" / "assets" / "tokens" / "tokens.css").unlink()                                                   # it is the kit's copy that is read, not the project's
    assert kit_check(pack).returncode == 1
    assert check_report_rows(pack)["kit:numbers"]["detail"] == cites_nothing(
        f"recipes/web-page.md:21 (8px has no citation; var(--dimension-space-2) {css_gone} (that file is missing))")


def test_numbered_steps_need_no_tag_but_their_values_do(pack):
    filled_kit(pack)
    recipe = kit_of(pack) / "recipes" / "web-page.md"
    mutate(recipe, RECIPE_LAST, RECIPE_LAST + "\n\n8. Pad the hero with 48px.\n   1) Then look at it.")                         # lines 21 and 22
    r = kit_check(pack)
    assert r.returncode == 1, r.stdout + r.stderr
    assert check_report_rows(pack)["kit:tags"]["status"] == "pass" and check_report_rows(pack)["kit:tags"]["detail"] == NO_TAGS      # a numbered step of a recipe needs no tag
    assert check_report_rows(pack)["kit:numbers"]["detail"] == cites_nothing("recipes/web-page.md:21 (48px has no citation)")
    mutate(recipe, "8. Pad the hero with 48px.", "8. Pad the hero with 48px, that is var(--dimension-space-2) six times.")
    assert kit_check(pack).returncode == 0 and statuses(pack) == {**ALL_PASS, "kit:owned": "warn"}
    mutate(recipe, "var(--dimension-space-2) six times.", "a lot.")
    assert kit_check(pack).returncode == 1
    assert check_report_rows(pack)["kit:numbers"]["detail"] == cites_nothing("recipes/web-page.md:21 (48px has no citation)")
    mutate(recipe, "a lot.", "a lot. [example]")
    assert kit_check(pack).returncode == 0
    step = "8. Pad the hero with 48px, that is a lot. [example]"                                                              # line 21 as it stands
    for written, value in (("8. Pad the hero 32-48px.", "48px"), ("8. Pad the hero 400-700ms.", "700ms"), ("8. Keep the measure to 60-75ch.", "75ch"), ("8. Pad the hero 1-2rem.", "2rem")):
        mutate(recipe, step, written)                                                                                         # a value written as a range is a value: the last number carries the unit
        step = written
        assert kit_check(pack).returncode == 1, written
        assert check_report_rows(pack)["kit:numbers"]["detail"] == cites_nothing(f"recipes/web-page.md:21 ({value} has no citation)"), written
        assert check_report_rows(pack)["kit:tags"]["detail"] == NO_TAGS
    mutate(recipe, step, step + " [example]")
    assert kit_check(pack).returncode == 0 and statuses(pack) == {**ALL_PASS, "kit:owned": "warn"}
    visual = kit_of(pack) / "visual.md"                                                                                       # in visual.md and golden-rules.md a numbered line needs its tag as well
    mutate(visual, KEPT, KEPT + "\n\n1. Pad the picture with 48px.")
    assert kit_check(pack).returncode == 1
    assert check_report_rows(pack)["kit:tags"]["detail"] == lack_a_tag(1, 1, "visual.md:7 untagged")
    assert check_report_rows(pack)["kit:numbers"]["detail"] == cites_nothing("visual.md:7 (48px has no citation)")
    mutate(visual, "48px.", "48px. [example]")
    assert kit_check(pack).returncode == 0 and statuses(pack) == {**ALL_PASS, "kit:owned": "warn"}


def test_a_value_in_a_code_fence_needs_a_citation_on_its_own_line(pack):
    filled_kit(pack)
    recipe = kit_of(pack) / "recipes" / "web-page.md"
    mutate(recipe, RECIPE_LAST, RECIPE_LAST + "\n\n```css\n.hero { padding: 48px; }\n.hero { margin: var(--dimension-space-2); }\n.hero { gap: 2rem; } /* [example] */\n- keep 3px\n```")
    r = kit_check(pack)                                                                                                       # lines 22 to 25 sit in the fence opened on line 21
    assert r.returncode == 1, r.stdout + r.stderr
    assert check_report_rows(pack)["kit:tags"]["detail"] == NO_TAGS                                                           # a bullet in a fence is no bullet
    assert check_report_rows(pack)["kit:numbers"]["detail"] == cites_nothing("recipes/web-page.md:22 (48px has no citation)", "recipes/web-page.md:25 (3px has no citation)")
    mutate(recipe, ".hero { padding: 48px; }", ".hero { padding: 48px; } /* [example] */")                                  # the tag of another line would not have counted
    mutate(recipe, "- keep 3px", "- keep 3px [example]")
    assert kit_check(pack).returncode == 0 and statuses(pack) == {**ALL_PASS, "kit:owned": "warn"}
    assert check_report_rows(pack)["kit:numbers"]["detail"] == "3 value(s) on 3 line(s) cite a token, a known rule or `[example]`"


def test_every_kind_of_value_is_found_and_names_links_and_tags_are_not_values():
    import kitlib
    found = {"Hero padding 48px": ["48px"], "gap .5rem and 1.5em": [".5rem", "1.5em"], "wait 200ms or 3 s, 100% or 50 %": ["200ms", "3 s", "100%", "50 %"],
             "80vh 100dvh 20svh 10vw 2ch 1fr 45deg 12pt": ["80vh", "100dvh", "20svh", "10vw", "2ch", "1fr", "45deg", "12pt"],
             "contrast 4.5:1 or 16:9": ["4.5:1", "16:9"], "colours #1a2b3c #FFF #abcd #11223344": ["#1a2b3c", "#FFF", "#abcd", "#11223344"],
             "rgb(0 0 0) rgba(0,0,0,.5) hsl(1 2% 3%) oklch(0.5 0.1 200) HSLA(": ["rgb(", "rgba(", "hsl(", "2%", "3%", "oklch(", "HSLA("],
             "margin -8px": ["8px"], "Hero PADDING 48PX": ["48PX"],
             "Hero padding 32-48px": ["48px"], "range 400-700ms": ["700ms"], "1-2rem gap": ["2rem"], "1.5-2em": ["2em"], "line length 60-75ch": ["75ch"],   # a range: the dash follows a number, not a name
             "2em-3em": ["2em", "3em"], "pad 16px-24px": ["16px", "24px"], "1.5rem-2rem": ["1.5rem", "2rem"], "10s-20s": ["10s", "20s"], "50%-75%": ["50%", "75%"],   # a unit on both ends: the dash follows a value
             "Open 9:00 to 17:00": ["9:00", "17:00"]}                                                                                            # a clock time reads as a ratio: the owner tags the line
    for line, values in found.items():
        assert kitlib.find_values(line) == values, line
    for line in ("--space-8px and var(--fs-16px) and fs-16px", "--space-2-8px and var(--space-2-8px)", "x-2rem and my_var-3px", "[rule: page:3s-delay] and [rule: x-2rem]", "[a](brand/x-48px.png) and https://example.com/a#abc123 and &#8212;",
                 "## Heading # 1", "step 2 of 3, 10 seconds, 5th, 22nd", "page:claims and tell:hero-text-budget", "section 2.1 and version 1.2", "a#fff and x1.5rem", "width=\"48\"",
                 "2026-10-30", "4.5 and 1."):
        assert kitlib.find_values(line) == [], line
    assert kitlib.token_refs("var(--a-b) var( --c ) {color.bg} {{brand.name}} ${a.b} {x} {a-b.c-d.9}") == (["--a-b", "--c"], ["color.bg", "a-b.c-d.9"])
    doc = {"$generator": "x", "primitives": {"color.ink": {"hex": "#000000"}}, "other": {"dimension.space-1": "4px"}, "modes": {"light": {"color.bg": {"hex": "#ffffff"}}, "dark": {"color.bg": {}}},
           "motion": {"durations_ms": {"duration.fast": 150}, "curves": {"curve.out": [0, 0, 0.2, 1]}}, "pairs": [], "touching": {"default": 3.0}, "grounds": {"named_by_owner": "", "list": []}}
    assert kitlib.json_token_paths(doc) == {"primitives.color.ink", "color.ink", "other.dimension.space-1", "dimension.space-1", "modes.light.color.bg", "modes.dark.color.bg", "color.bg",   # a token, by its key or by its path from the top
                                            "motion.durations_ms.duration.fast", "motion.curves.curve.out"}                                                                                  # and no group, no part of a token, nothing else of the file
    assert kitlib.json_token_paths({"modes": ["light"], "primitives": 3, "other": None, "motion": {"curves": "x"}}) == set()                                                                  # a file of another shape names no token and never crashes


def test_tags_and_values_are_judged_in_the_owners_markdown_files_golden_rules_visual_and_reference_page_notes_only(pack):
    filled_kit(pack)
    kd = kit_of(pack)
    say = "- Say 48px loudly."
    mutate(kd / "voice.md", KEPT, KEPT + "\n\n" + say)                                                                         # voice.md and EXTENDING.md are not judged for tags and values
    mutate(kd / "EXTENDING.md", "# Extending the Acme brand kit", "# Extending the Acme brand kit\n\n" + say)
    (kd / "notes").mkdir()
    (kd / "notes" / "own.md").write_text(say + "\n", encoding="utf-8")                                                          # any Markdown file of the owner's is judged
    (kd / "recipes" / "deep").mkdir()
    (kd / "recipes" / "deep" / "more.md").write_text("- A deep bullet.\n", encoding="utf-8")                                    # recipes/** : any depth
    (kd / "recipes" / "email.md").write_text("# Email\n\n" + say + "\n1. Write 48px.\n", encoding="utf-8")                      # a numbered step needs no tag, its value a citation
    (kd / "recipes" / "notes.txt").write_text(say + "\n", encoding="utf-8")                                                     # Markdown only
    (kd / "reference-pages" / "start").mkdir(parents=True)
    (kd / "reference-pages" / "start" / "notes.md").write_text("# start\n\n" + say + "\n", encoding="utf-8")                    # the generated notes of a page
    (kd / "reference-pages" / "start" / "other.md").write_text(say + "\n", encoding="utf-8")                                    # notes.md only
    r = kit_check(pack)
    assert r.returncode == 1, r.stdout + r.stderr                                                                             # kit:files fails too: nobody generated these notes
    assert check_report_rows(pack)["kit:tags"]["detail"] == lack_a_tag(
        4, 4, "notes/own.md:1 untagged", "recipes/deep/more.md:1 untagged", "recipes/email.md:3 untagged", "reference-pages/start/notes.md:3 untagged")
    assert check_report_rows(pack)["kit:numbers"]["detail"] == cites_nothing(
        "notes/own.md:1 (48px has no citation)", "recipes/email.md:3 (48px has no citation)", "recipes/email.md:4 (48px has no citation)",
        "reference-pages/start/notes.md:3 (48px has no citation)")


def test_a_rule_tag_on_a_line_that_needs_no_tag_is_not_verified_when_the_rule_ids_cannot_be_read(pack):
    record_rules(pack, "The mark keeps its clear space")
    filled_kit(pack)
    (pack / "site").mkdir()
    (pack / "site" / "site.json").write_text("{not json", encoding="utf-8")
    recipe = kit_of(pack) / "recipes" / "web-page.md"
    mutate(recipe, RECIPE_LAST, RECIPE_LAST + f"\n\n8. Keep the clear space. [rule: {CLEAR_SPACE}]")
    r = kit_check(pack)
    assert r.returncode == 3, r.stdout + r.stderr                                                              # a numbered step needs no tag, but the id it names cannot be judged: never a pass
    tags = check_report_rows(pack)["kit:tags"]
    assert tags["status"] == "skipped" and tags["detail"].startswith("not verified: the rule ids a tag may name cannot be read (") and "site/site.json" in tags["detail"]
    assert statuses(pack)["kit:numbers"] == "pass" and report(pack, "kit-check")["status"] == "not-verified"


def test_tag_rows_are_not_verified_when_the_rule_ids_cannot_be_read(pack):
    record_rules(pack, "The mark keeps its clear space")
    filled_kit(pack)
    (pack / "site").mkdir()
    (pack / "site" / "site.json").write_text("{not json", encoding="utf-8")
    kit_check(pack)                                                                                                           # no line names a rule: the ids are never needed
    assert statuses(pack)["kit:tags"] == "pass" and statuses(pack)["kit:numbers"] == "pass"
    assert any(i["path"].endswith("site/site.json") for i in report(pack, "kit-check")["inputs"])                                # the report goes stale when the site record changes
    golden = kit_of(pack) / "golden-rules.md"
    mutate(golden, KEPT, KEPT + f"\n\n- Keep the clear space. [rule: {CLEAR_SPACE}]")
    kit_check(pack)
    tags = check_report_rows(pack)["kit:tags"]
    assert tags["status"] == "skipped" and tags["detail"].startswith("not verified: the rule ids a tag may name cannot be read (")
    assert "site/site.json" in tags["detail"] and tags["detail"].endswith("); fix it and run `brand-creator kit check` again")
    assert statuses(pack)["kit:numbers"] == "pass"                                                                            # no value on that line
    mutate(golden, f"[rule: {CLEAR_SPACE}]", f"[rule: {CLEAR_SPACE}]\n\nPad 48px [rule: {CLEAR_SPACE}]")
    kit_check(pack)
    assert statuses(pack)["kit:tags"] == "skipped" and statuses(pack)["kit:numbers"] == "skipped"
    assert check_report_rows(pack)["kit:numbers"]["detail"].startswith("not verified: the rule ids a tag may name cannot be read (")
    assert report(pack, "kit-check")["status"] == "not-verified"
    mutate(golden, f"Pad 48px [rule: {CLEAR_SPACE}]", f"Pad 48px [rule: {CLEAR_SPACE}]\n\n- Keep it loud.\n\nPad 8px.")                    # lines 11 and 13: a failure that needs no rule id
    r = kit_check(pack)
    assert r.returncode == 1, r.stdout + r.stderr                                                                             # is not hidden behind the lines that cannot be judged: the owner fixes both at once
    note = "; 1 line(s) that name a rule were not judged, because the rule ids cannot be read ("
    again = "); fix it and run `brand-creator kit check` again"
    tags, numbers = check_report_rows(pack)["kit:tags"], check_report_rows(pack)["kit:numbers"]
    assert tags["status"] == "fail" and numbers["status"] == "fail"
    assert tags["detail"].startswith(lack_a_tag(1, 3, "golden-rules.md:11 untagged") + note.replace("1 line", "2 line")) and "site/site.json" in tags["detail"] and tags["detail"].endswith(again)   # the bullet and the sentence both name a rule
    assert numbers["detail"].startswith(cites_nothing("golden-rules.md:13 (8px has no citation)") + note) and "site/site.json" in numbers["detail"] and numbers["detail"].endswith(again)
    assert report(pack, "kit-check")["status"] == "fail"
    mutate(golden, "\n\n- Keep it loud.\n\nPad 8px.", f"\n\nPad 8px var(--nope) [rule: {CLEAR_SPACE}]")                                 # line 11: a token that does not exist needs no rule id to be found either
    r = kit_check(pack)
    assert r.returncode == 1, r.stdout + r.stderr
    numbers = check_report_rows(pack)["kit:numbers"]
    assert statuses(pack)["kit:tags"] == "skipped" and numbers["status"] == "fail"                                            # the tag on the line stays unjudged
    assert numbers["detail"].startswith(cites_nothing("golden-rules.md:11 (var(--nope) is not declared in brand/assets/tokens/tokens.css)") + "; 2 line(s) that name a rule were not judged, because the rule ids cannot be read (")
    assert "site/site.json" in numbers["detail"] and numbers["detail"].endswith(again)
    mutate(golden, f"\n\nPad 8px var(--nope) [rule: {CLEAR_SPACE}]", "")
    (pack / "site" / "site.json").write_text(json.dumps({"schema": 1, "approved": "2026-10-17 (test)", "round": 1, "hero": "a", "pages": [], "choices": []}), encoding="utf-8")
    kit_check(pack)
    assert statuses(pack)["kit:tags"] == "pass" and statuses(pack)["kit:numbers"] == "pass"


# ---------------------------------------------------------------- reference pages: the approved pages of site/ go into the kit
# tests/fixtures/kit/ is an overlay for the Acme project: one approved page, `start` (site/site.json in the format of `site approve`, its sha256 that of the page), the stylesheet and
# images it loads. Its page-check report and its stills are made by hand (`page_check_report`, `capture_record` of helpers.py), so no browser is needed.
SITE_FIXTURE = ROOT / "tests" / "fixtures" / "kit"
START = "site/start/index.html"
SHOTS = ["1440-light.png", "1440-dark.png", "390-light.png", "390-dark.png", "1440-light-full.png", "capture.json"]
PAGE_KIT = sorted(["brand/site/start/index.html", "brand/site/start/site.css", "brand/site/start/img/pic.svg", *[f"brand/site/start/shots/{n}" for n in SHOTS],
                   "brand/assets/web/base.css", "brand/assets/web/dot.svg", "reference-pages/start/notes.md"])   # what the fixture adds to the fifteen files of a kit
START_NOTES = """# start

Layout: walkthrough (structure only)
Approved: 2026-10-17 approved start; rules c1

Page: [index.html](../../brand/site/start/index.html)
Stills: [1440-light](../../brand/site/start/shots/1440-light.png), [1440-dark](../../brand/site/start/shots/1440-dark.png), [390-light](../../brand/site/start/shots/390-light.png), [390-dark](../../brand/site/start/shots/390-dark.png), [full page](../../brand/site/start/shots/1440-light-full.png)

## Choices

- The stamp appears once per view [rule: site:c1] (decided in the stamp appears once per view)
- Plans sit under the steps [example]
"""
NOTHING_WRITTEN = "nothing was written"


def settle_page(p, pid="start"):
    """The page-check report and the stills `brand-creator page-check` and `brand-creator capture` leave for a page of site/, made by hand."""
    from helpers import capture_record, page_check_report
    page_check_report(p, f"site/{pid}/index.html", "pass")
    capture_record(p, f"site/{pid}/index.html")


def with_site(p, *, settle=True):
    for sub in ("site", "assets"):
        shutil.copytree(SITE_FIXTURE / sub, p / sub, dirs_exist_ok=True)
    if settle:
        settle_page(p)


def edit_page(p, old, new, pid="start"):
    """`mutate` an approved page, record its new sha256 in site/site.json as an approval does, and check and capture it again: a page that was approved again."""
    page = p / "site" / pid / "index.html"
    mutate(page, old, new)
    sha = file_sha(page)
    mutate_json(p / "site" / "site.json", lambda d: next(x for x in d["pages"] if x["id"] == pid).__setitem__("sha256", sha))
    settle_page(p, pid)


def untouched(p):
    """A refusal writes nothing: no kit folder, no `kit` report."""
    assert not (p / ".claude").exists() and not (p / "assets" / "_checks" / "kit.json").exists()


def page_report(p, pid="start"):
    """The path of the page-check report of a page of site/ (assets/_checks/page-check/<file stem>-<hash6>.json: every page file is index.html, so the stem is `index`)."""
    import pagecheck
    return p / "assets" / "_checks" / f"{pagecheck.report_tool(f'site/{pid}/index.html')}.json"


def inputs_hash(doc) -> str:
    h = hashlib.sha256()
    for r in doc["inputs"]:
        h.update(f"{r['path']}\0{r['sha256']}\n".encode())
    return h.hexdigest()


def pages_row(p) -> dict:
    return next(r for r in report(p, "kit")["results"] if r["id"] == "kit:reference-pages")


def pages_pass(*ids) -> dict:
    """The rows of a `kit check` that passes everything, with the one row each reference page of the kit gets."""
    return {**ALL_PASS, **{f"kit:reference-page:{i}": "pass" for i in ids}}


def test_an_approved_reference_page_and_what_it_loads_are_copied_with_notes(pack):
    with_site(pack)
    r = bc("kit", "build", "--plan", project=pack)
    assert r.returncode == 0 and r.stdout.splitlines()[0] == "would write 27 generated files into .claude/skills/acme-brand/ (version 1.1)", r.stdout + r.stderr
    untouched(pack)
    r = build(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert kit_files(pack) == sorted([*KIT_FILES, *PAGE_KIT])
    for rel in PAGE_KIT:                                                                # a byte copy at the project path, under brand/
        if rel.startswith("brand/"):
            assert filecmp.cmp(pack / rel.removeprefix("brand/"), kit_of(pack) / rel, shallow=False), rel
    assert (kit_of(pack) / "reference-pages" / "start" / "notes.md").read_text(encoding="utf-8") == START_NOTES
    assert not (kit_of(pack) / "brand" / "site" / "site.json").exists()                  # the record is not a page: it is not copied
    checked = json.loads(page_report(pack).read_text(encoding="utf-8"))
    capture = json.loads((pack / "site" / "start" / "shots" / "capture.json").read_text(encoding="utf-8"))
    record = {"id": "start", "page": "brand/site/start/index.html", "source_sha": file_sha(pack / START), "page_check_inputs_sha": checked["inputs_sha"],
              "capture_inputs_sha": inputs_hash(capture)}
    assert record["source_sha"] == json.loads((pack / "site" / "site.json").read_text(encoding="utf-8"))["pages"][0]["sha256"]
    assert kit_json(pack)["reference_pages"] == [record]
    loaded = ["assets/tokens/tokens.css", "assets/logo/mark.svg", "assets/web/base.css", "assets/web/dot.svg"]       # outside the page folder: the first two are in the kit anyway
    folder = [rel.removeprefix("brand/") for rel in PAGE_KIT if rel.startswith("brand/site/")]
    assert kit_json(pack)["sources"]["pages"] == motion_hash(pack, ["site/site.json", *folder, *loaded])
    skill = (kit_of(pack) / "SKILL.md").read_text(encoding="utf-8")
    assert all(f"- `{rel}`" in skill for rel in PAGE_KIT)
    row = pages_row(pack)
    assert row["status"] == "pass" and row["detail"] == ("1 approved reference page copied with its stills and the files it loads (start); "
                                                         "notes in reference-pages/<id>/notes.md"), row
    rep = report(pack, "kit")
    assert rep["status"] == "pass" and sorted(rep["outputs"]) == sorted([*KIT_FILES, *PAGE_KIT])
    assert {"site/site.json", START, "site/start/shots/capture.json", "assets/web/base.css", "assets/web/dot.svg", page_report(pack).relative_to(pack).as_posix()} <= {i["path"] for i in rep["inputs"]}
    first = kit_state(pack)
    assert build(pack).returncode == 0 and kit_state(pack) == first and kit_json(pack)["version"] == "1.1"      # a second build writes nothing
    # the kit holds the page whole: every link of the notes and of the copied page resolves inside it, and every tag and value is cited
    fill_owned(kit_of(pack))
    assert build(pack).returncode == 0 and kit_json(pack)["version"] == "1.2"
    r = kit_check(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert statuses(pack) == pages_pass("start")                                                  # and one row for the page it holds
    # the 7 links of snippets/logo.html; 6 in the notes (the page and 5 stills); 5 in the page (3 stylesheets, the mark, the picture; `#plans` and `mailto:` are no relative link); 1 in site.css; 1 in base.css.
    # The files: the 8 of a fresh kit, and the page, site.css, base.css and the notes.
    assert check_report_rows(pack)["kit:links"]["detail"] == f"{FRESH_LINKS + 6 + 5 + 1 + 1} relative links in {FRESH_FILES + 4} .md, .html and .css files resolve inside the kit"


def test_a_project_without_a_site_record_has_an_info_row_and_no_reference_pages(pack):
    assert build(pack).returncode == 0
    row = pages_row(pack)
    assert row["status"] == "info" and row["detail"] == "no approved reference pages"
    assert kit_json(pack)["reference_pages"] == [] and kit_json(pack)["sources"]["pages"] is None
    assert not (kit_of(pack) / "reference-pages").exists() and not list(kit_of(pack).glob("brand/site"))


def test_a_reference_page_without_a_passing_page_check_stops_the_build(pack):
    with_site(pack)
    tool = page_report(pack)
    name = tool.name
    cmd = "run `brand-creator page-check site/start/index.html`"
    # no report at all
    saved = tool.read_bytes()
    tool.unlink()
    for args in (("--yes",), ("--plan",)):
        r = bc("kit", "build", *args, project=pack)
        assert r.returncode == 1, (args, r.stdout, r.stderr)
        assert "site/start/index.html has no page-check report" in r.stderr and cmd in r.stderr and NOTHING_WRITTEN in r.stderr
    untouched(pack)
    # the page is changed so that group 1's own check fails it (a colour that is no token), approved again (the record follows it), and the REAL page-check is run: no report made by hand stands in for it,
    # so the build is judged on the report `page-check` writes (its target, its inputs, its status, its inputs_sha)
    tool.write_bytes(saved)
    edit_page(pack, "<h1>One calm place", '<style>h1 { color: #ff00ff; }</style><h1>One calm place')
    checked = bc("page-check", START, project=pack)
    assert checked.returncode == 1, checked.stdout + checked.stderr
    assert tool.is_file() and json.loads(tool.read_text(encoding="utf-8"))["status"] == "fail"
    r = build(pack)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "site/start/index.html fails its page check (page:colours:" in r.stderr and "; see assets/_checks/page-check/" in r.stderr and name in r.stderr
    assert "approve it again (`brand-creator site approve --replace`)" in r.stderr
    untouched(pack)
    from helpers import page_check_report
    # a report that is no verdict
    page_check_report(pack, START, "not-verified")
    r = build(pack)
    assert r.returncode == 1 and "has a page-check report that gives no verdict (status 'not-verified'; see assets/_checks/page-check/" in r.stderr
    untouched(pack)
    # a report that was current and the page changed after it (the record follows the page, the check does not)
    page_check_report(pack, START, "pass")
    page = pack / "site" / "start" / "index.html"
    mutate(page, "One calm place", "One calmer place")
    mutate_json(pack / "site" / "site.json", lambda d: d["pages"][0].__setitem__("sha256", file_sha(page)))
    r = build(pack)
    assert r.returncode == 1 and "has a page-check report that is stale (site/start/index.html changed)" in r.stderr and cmd in r.stderr, r.stderr
    untouched(pack)
    # a report of another target
    page_check_report(pack, START, "pass")
    mutate_json(page_report(pack), lambda d: d["target"].__setitem__("page", "site/other/index.html"))
    r = build(pack)
    assert r.returncode == 1 and "has a page-check report of another target" in r.stderr and cmd in r.stderr
    untouched(pack)
    # the page is checked and captured again, and passes: the kit goes in
    settle_page(pack)
    r = build(pack)
    assert r.returncode == 0, r.stdout + r.stderr


def test_a_reference_page_without_current_stills_stops_the_build(pack):
    with_site(pack)
    shots = pack / "site" / "start" / "shots"
    cmd = "run `brand-creator capture site/start/index.html`"
    record = (shots / "capture.json").read_bytes()
    (shots / "capture.json").unlink()
    r = build(pack)
    assert r.returncode == 1 and "site/start/index.html has no stills (site/start/shots/capture.json is missing)" in r.stderr and cmd in r.stderr and NOTHING_WRITTEN in r.stderr
    untouched(pack)
    (shots / "capture.json").write_bytes(record)
    mutate_json(shots / "capture.json", lambda d: d["source"].__setitem__("page", "site/other/index.html"))        # the capture of another page
    r = build(pack)
    assert r.returncode == 1 and "has stills that are stale (" in r.stderr and cmd in r.stderr
    untouched(pack)
    from helpers import capture_record
    capture_record(pack, START)
    (shots / "390-dark.png").write_bytes(b"not the still the record lists")
    r = build(pack)
    assert r.returncode == 1 and "has stills that are not the ones capture.json lists" in r.stderr and cmd in r.stderr
    assert "site/start/shots/390-dark.png is not the 390-dark still site/start/shots/capture.json lists (its sha256 differs)" in r.stderr
    untouched(pack)
    capture_record(pack, START)
    mutate(pack / "assets" / "tokens" / "tokens.css", ":root", ":root /* edited */")                                # the tokens changed after the stills were taken: the record is stale
    r = build(pack)
    assert r.returncode == 1 and "has a page-check report that is stale (assets/tokens/tokens.css changed)" in r.stderr and "has stills that are stale (assets/tokens/tokens.css changed" in r.stderr
    untouched(pack)


def test_a_reference_page_that_loads_a_file_outside_the_project_stops_the_build(pack, tmp_path):
    from helpers import symlink_or_skip
    with_site(pack)
    far = tmp_path / "outside.png"
    far.write_bytes(b"SECRET-OUTSIDE")

    def refused(why, *where):
        for args in (("--yes",), ("--plan",)):
            r = bc("kit", "build", *args, project=pack)
            assert r.returncode == 2, (why, args, r.stdout, r.stderr)
            assert "outside the project" in r.stderr and all(w in r.stderr for w in where) and "Traceback" not in r.stderr, (why, r.stderr)
            assert b"SECRET-OUTSIDE" not in r.stdout.encode()
        untouched(pack)
        nothing_secret_in(pack)

    # a name that leaves the project
    edit_page(pack, 'src="img/pic.svg"', 'src="../../../outside.png"')
    refused("a path that climbs out", "site/start/index.html:", "'../../../outside.png' leads outside the project")
    edit_page(pack, 'src="../../../outside.png"', 'src="img/pic.svg"')
    # a file of the project that is a link to a file beyond it, loaded by name
    symlink_or_skip(pack / "assets" / "web" / "far.png", far)
    edit_page(pack, 'src="img/pic.svg"', 'src="../../assets/web/far.png"')
    refused("a link", "site/start/index.html:", "assets/web/far.png")
    edit_page(pack, 'src="../../assets/web/far.png"', 'src="img/pic.svg"')
    # a stylesheet the page loads, and the file that stylesheet loads, one level deeper
    mutate(pack / "assets" / "web" / "base.css", 'url("dot.svg")', 'url("far.png")')
    refused("a link, loaded by a stylesheet", "assets/web/base.css:", "assets/web/far.png")
    mutate(pack / "assets" / "web" / "base.css", 'url("far.png")', 'url("../../../outside.png")')
    refused("a path that climbs out, loaded by a stylesheet", "assets/web/base.css:", "'../../../outside.png' leads outside the project")
    mutate(pack / "assets" / "web" / "base.css", 'url("../../../outside.png")', 'url("dot.svg")')
    (pack / "assets" / "web" / "far.png").unlink()
    # a file in the page folder that is a link to a file beyond the project, and a link to a folder beyond it
    symlink_or_skip(pack / "site" / "start" / "linked.png", far)
    refused("a link in the page folder", "site/start/linked.png")
    (pack / "site" / "start" / "linked.png").unlink()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "x.png").write_bytes(b"SECRET-OUTSIDE")
    symlink_or_skip(pack / "site" / "start" / "folder", elsewhere)
    refused("a link to a folder in the page folder", "site/start/folder")
    (pack / "site" / "start" / "folder").unlink()
    # the page folder itself is a link to a folder beyond the project
    shutil.move(str(pack / "site" / "start"), str(tmp_path / "moved-start"))
    symlink_or_skip(pack / "site" / "start", tmp_path / "moved-start")
    refused("the page folder is a link", "site/start")
    (pack / "site" / "start").unlink()
    shutil.move(str(tmp_path / "moved-start"), str(pack / "site" / "start"))
    # the record itself is a link to a file beyond the project
    shutil.move(str(pack / "site" / "site.json"), str(tmp_path / "record.json"))
    symlink_or_skip(pack / "site" / "site.json", tmp_path / "record.json")
    refused("the record is a link", "site/site.json")
    (pack / "site" / "site.json").unlink()
    shutil.move(str(tmp_path / "record.json"), str(pack / "site" / "site.json"))
    r = build(pack)                                                                                                    # the page as it was: it goes in
    assert r.returncode == 0, r.stdout + r.stderr
    nothing_secret_in(pack)


def test_a_link_in_a_page_folder_that_leaves_the_project_is_not_read_even_to_be_hashed(pack, tmp_path):
    """`check` and `kit check` hash the files the pages are made from. A file of a page folder that is a link to a file beyond the project is none of them: it is not hashed, it does not move the
    sources and it is no input of the report, whatever the file beyond holds (the build refuses it, exit 2, above)."""
    import kitlib
    from helpers import symlink_or_skip
    with_site(pack)
    before = kitlib.pages_source(pack)
    far = tmp_path / "outside.png"
    far.write_bytes(b"ONE")
    symlink_or_skip(pack / "site" / "start" / "linked.png", far)
    assert "site/start/linked.png" not in kitlib.page_sources(pack) and "site/start/linked.png" not in kitlib.page_input_rels(pack)
    assert os.path.realpath(far) not in [os.path.realpath(f) for f in kitlib.input_paths(pack)]
    assert kitlib.pages_source(pack) == before
    far.write_bytes(b"TWO")
    assert kitlib.pages_source(pack) == before                                                                        # what is beyond the project moves nothing
    assert "linked.png" in bc("kit", "build", "--yes", project=pack).stderr                                          # and the build still refuses it
    (pack / "site" / "start" / "linked.png").unlink()
    assert kitlib.pages_source(pack) == before


def test_a_page_that_changes_between_the_record_check_and_the_read_is_not_copied(pack, monkeypatch):
    """`sitedata.validate_site` finds the page as it was approved and the bytes read after it are other bytes: the page changed in between. The race is made by hand: the record check is patched to
    find nothing while the page is no longer the approved one (its report and stills are those of the new bytes). Exit 1, and the page is not copied."""
    import kitlib
    import sitedata
    from _common import CliError
    with_site(pack)
    mutate(pack / "site" / "start" / "index.html", "One calm place", "One calmer place")                              # the record keeps the old sha256
    settle_page(pack)
    assert sitedata.validate_site(pack)                                                                                # as it is, the record check says so
    monkeypatch.setattr(sitedata, "validate_site", lambda project: [])
    with pytest.raises(CliError) as e:
        kitlib.reference_plan(pack, kitlib.font_plan(pack))
    assert e.value.code == 1 and "site/start/index.html changed since it was approved" in e.value.message, e.value.message


def test_a_reference_page_is_read_from_the_path_that_was_checked_whichever_way_a_link_is_resolved(pack, tmp_path):
    """The page loads `assets/web/L/../E`. L is a link to deep/dir and E (beside L) a link to a file beyond the project; deep/E is a file inside it. An operating system that follows L first
    opens deep/E. The kit names the plain path assets/web/E, and that is the path it checks and reads: it is the link to the outside, and nothing outside reaches the kit."""
    from helpers import symlink_or_skip
    with_site(pack)
    (pack / "deep" / "dir").mkdir(parents=True)
    (pack / "deep" / "E").write_bytes(b"inside")
    far = tmp_path / "outside.png"
    far.write_bytes(SECRET)
    symlink_or_skip(pack / "assets" / "web" / "L", pack / "deep" / "dir")
    symlink_or_skip(pack / "assets" / "web" / "E", far)
    edit_page(pack, 'src="img/pic.svg"', 'src="../../assets/web/L/../E"')
    for args in (("--yes",), ("--plan",)):
        r = bc("kit", "build", *args, project=pack)
        assert r.returncode == 2 and "outside the project" in r.stderr and "assets/web/E" in r.stderr and "Traceback" not in r.stderr, (args, r.stdout, r.stderr)
    untouched(pack)
    nothing_secret_in(pack)


def test_a_page_that_loads_a_missing_file_a_folder_or_an_absolute_path_stops_the_build(pack):
    with_site(pack)
    cases = [("a missing file", "img/pic.svg", "img/gone.svg", "leads to site/start/img/gone.svg, which the project does not have"),
             ("a folder", "img/pic.svg", "img/", "leads to site/start/img, a folder, not a file"),
             ("the letter case of the file", "img/pic.svg", "img/PIC.svg", "which the project holds as site/start/img/pic.svg"),
             ("an absolute path", "img/pic.svg", "/img/pic.svg", "is an absolute path, which will not resolve in a product repository"),
             ("a file: address", "img/pic.svg", "file:///img/pic.svg", "is an absolute path")]
    for why, old, new, said in cases:
        edit_page(pack, f'src="{old}"', f'src="{new}"')
        for args in (("--yes",), ("--plan",)):
            r = bc("kit", "build", *args, project=pack)
            assert r.returncode == 1 and said in r.stderr and "site/start/index.html:" in r.stderr and "Traceback" not in r.stderr, (why, args, r.stdout, r.stderr)
        untouched(pack)
        edit_page(pack, f'src="{new}"', f'src="{old}"')
    # what loads nothing from the project is left alone: network addresses, data:, mailto:, tel:, a fragment, a query and an empty href
    edit_page(pack, '<a class="action" href="#plans">', '<a class="action" href="#plans"><img src="https://cdn.example.invalid/x.png" alt=""><img src="data:image/gif;base64,R0lGODlhAQABAAAAACw=" alt="">'
              '<a href="tel:+000">t</a><a href="?x=1">q</a><a href="">e</a><a href="//cdn.example.invalid/y.css">n</a>')
    r = build(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert kit_files(pack) == sorted([*KIT_FILES, *PAGE_KIT])


def test_every_place_a_page_names_a_file_in_is_read_and_the_file_is_copied(pack):
    """src, srcset (with its descriptors), poster, the data of an object, url() in a style attribute and in a style element, and href: each file a page names is copied once, at its project path."""
    with_site(pack)
    extra = {"two.svg": "<svg xmlns='http://www.w3.org/2000/svg'/>", "poster.svg": "<svg xmlns='http://www.w3.org/2000/svg' width='2'/>", "obj.svg": "<svg xmlns='http://www.w3.org/2000/svg' width='3'/>",
             "styled.svg": "<svg xmlns='http://www.w3.org/2000/svg' width='4'/>", "block.svg": "<svg xmlns='http://www.w3.org/2000/svg' width='5'/>", "more.txt": "a text file a link names\n"}
    for name, text in extra.items():
        (pack / "assets" / "web" / name).write_text(text, encoding="utf-8")
    (pack / "site" / "start" / ".DS_Store").write_bytes(b"what Finder leaves")
    edit_page(pack, "<main>", '<style>.s { background: url(../../assets/web/block.svg) }</style>\n<main>')
    edit_page(pack, '<img class="art" src="img/pic.svg" alt="">',
              '<img class="art" src="img/pic.svg" srcset="img/pic.svg 1x, ../../assets/web/two.svg 2x" alt="">\n'
              '<video poster="../../assets/web/poster.svg"></video><object data="../../assets/web/obj.svg"></object>\n'
              '<div style="background: url(\'../../assets/web/styled.svg\')"></div><a href="../../assets/web/more.txt">more</a>')
    r = build(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert kit_files(pack) == sorted([*KIT_FILES, *PAGE_KIT, *[f"brand/assets/web/{n}" for n in extra]])
    for name in extra:
        assert filecmp.cmp(pack / "assets" / "web" / name, kit_of(pack) / "brand" / "assets" / "web" / name, shallow=False)
    assert not (kit_of(pack) / "brand" / "site" / "start" / ".DS_Store").exists()


def test_a_file_two_steps_from_a_pages_stylesheet_is_not_copied_and_kit_check_names_the_link(pack):
    """The steps are counted from a stylesheet the page loads (base.css): what base.css loads, dot.svg and deeper.css, is one step away and is copied; deeper.css is copied but not read, so three.svg, which it loads,
    is two steps away and is not copied."""
    with_site(pack)
    (pack / "assets" / "web" / "deeper.css").write_text(".d { background: url(three.svg); }\n", encoding="utf-8")
    (pack / "assets" / "web" / "three.svg").write_text("<svg xmlns='http://www.w3.org/2000/svg'/>\n", encoding="utf-8")
    mutate(pack / "assets" / "web" / "base.css", ".dot {", '@import "deeper.css";\n.dot {')                                  # base.css loads deeper.css (copied), which loads three.svg (not)
    assert build(pack).returncode == 0
    kit = kit_of(pack)
    assert (kit / "brand" / "assets" / "web" / "deeper.css").is_file() and not (kit / "brand" / "assets" / "web" / "three.svg").exists()
    fill_owned(kit)
    assert build(pack).returncode == 0
    r = kit_check(pack)
    assert r.returncode == 1, r.stdout + r.stderr
    detail = check_report_rows(pack)["kit:links"]["detail"]
    assert detail.startswith("1 of ") and "brand/assets/web/deeper.css:1 -> three.svg (no such file in the kit)" in detail, detail


def test_each_choice_of_a_reference_page_is_tagged_in_its_notes(pack):
    with_site(pack)
    pricing = (pack / "site" / "start" / "index.html").read_text(encoding="utf-8").replace('data-page="start"', 'data-page="pricing"')
    (pack / "site" / "pricing").mkdir()
    (pack / "site" / "pricing" / "index.html").write_text(pricing, encoding="utf-8")
    shutil.copy2(pack / "site" / "start" / "site.css", pack / "site" / "pricing" / "site.css")
    shutil.copytree(pack / "site" / "start" / "img", pack / "site" / "pricing" / "img")
    site = json.loads((pack / "site" / "site.json").read_text(encoding="utf-8"))
    site["pages"].append({"id": "pricing", "path": "site/pricing/index.html", "layout": "own:ledger", "sha256": file_sha(pack / "site" / "pricing" / "index.html")})
    site["choices"] = [
        {"id": "c1", "text": "The stamp appears once per view", "tag": "rule", "source": "the stamp appears once per view", "pages": ["start", "pricing"]},
        {"id": "c2", "text": "Plans sit under the steps", "tag": "example", "source": "", "pages": ["start"]},
        {"id": "c3", "text": "Prices keep two decimals", "tag": "rule", "source": "DECISIONS.md, the pricing page", "pages": ["pricing"]},
        {"id": "c4", "text": "Every page ends with the contact line", "tag": "example", "source": "", },               # no `pages`: it names every page
        {"id": "c5", "text": "The hero image is 640px wide", "tag": "example", "source": "", "pages": ["pricing"]}]
    (pack / "site" / "site.json").write_text(json.dumps(site, indent=2) + "\n", encoding="utf-8")
    settle_page(pack, "pricing")
    r = build(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    notes = lambda pid: (kit_of(pack) / "reference-pages" / pid / "notes.md").read_text(encoding="utf-8")        # noqa: E731
    start, pricing = notes("start"), notes("pricing")
    assert start.split("## Choices\n\n")[1] == ("- The stamp appears once per view [rule: site:c1] (decided in the stamp appears once per view)\n"
                                              "- Plans sit under the steps [example]\n"
                                              "- Every page ends with the contact line [example]\n")
    assert pricing.split("## Choices\n\n")[1] == ("- The stamp appears once per view [rule: site:c1] (decided in the stamp appears once per view)\n"
                                                "- Prices keep two decimals [rule: site:c3] (decided in DECISIONS.md, the pricing page)\n"
                                                "- Every page ends with the contact line [example]\n"
                                                "- The hero image is 640px wide [example]\n")
    assert "Layout: own:ledger (structure only)" in pricing and "Layout: walkthrough (structure only)" in start
    assert [r["id"] for r in kit_json(pack)["reference_pages"]] == ["start", "pricing"]                              # the record's order
    assert "2 approved reference pages copied with their stills" in pages_row(pack)["detail"] and "(start, pricing)" in pages_row(pack)["detail"]
    fill_owned(kit_of(pack))
    assert build(pack).returncode == 0
    r = kit_check(pack)
    assert r.returncode == 0, r.stdout + r.stderr                                                                    # every bullet is tagged with an id the kit knows, and its value is cited
    assert statuses(pack) == pages_pass("start", "pricing")
    # a page with no choice of its own
    site["choices"] = [site["choices"][2]]
    (pack / "site" / "site.json").write_text(json.dumps(site, indent=2) + "\n", encoding="utf-8")
    assert build(pack).returncode == 0
    assert notes("start").endswith("## Choices\n\nThe site round recorded no choice for this page.\n")
    assert kit_check(pack).returncode == 0 and statuses(pack) == pages_pass("start", "pricing")


NASTY = ["The tile is {color.bg} under {props.title} and {{kept.double}} and ${kept.dollar}",
         "Use var(--nope) for the hero, or var( --color-bg ) on the panel",
         "Keep it [example] and [rule: nope] and [rule: the-mark-keeps-its-clear-space] and [[fill: more]] out of the text",
         "See [the page](../../../../etc/shadow) and ![x](missing.png)",
         "Padding 48px, 4.5:1, #1a2b3c, rgb(1 2 3), 100% and 3 em dashes"]


def test_a_choice_text_that_kit_check_would_read_as_a_citation_is_written_so_it_is_not(pack):
    """A choice is the owner's free text. Whatever it holds, the generated notes pass `kit check` as written: a token reference, a tag, a fill marker or a link in a choice is shown
    as the Markdown reader shows it and is not read by the checks (the doubled braces, the numeric references)."""
    with_site(pack)
    record_rules(pack, "The mark keeps its clear space")
    site = json.loads((pack / "site" / "site.json").read_text(encoding="utf-8"))
    site["approved"] = "2026-10-17 approved start with 3 em dashes and {color.bg}; [[fill: x]] [example]"
    site["choices"] = [{"id": f"c{i}", "text": text, "tag": tag, "source": f"decided in [rule: nope] and var(--nope), 48px", "pages": ["start"]}
                       for i, (text, tag) in enumerate(((t, tag) for t in NASTY for tag in ("rule", "example")), 1)]
    (pack / "site" / "site.json").write_text(json.dumps(site, indent=2) + "\n", encoding="utf-8")
    assert build(pack).returncode == 0
    notes = (kit_of(pack) / "reference-pages" / "start" / "notes.md").read_text(encoding="utf-8")
    assert "{{color.bg}} under {{props.title}} and {{kept.double}} and ${kept.dollar}" in notes                  # the doubled braces are the spelling `kit check` leaves alone; one already doubled stays
    assert "var&#40;--nope) for the hero, or var&#40; --color-bg ) on the panel" in notes
    assert "&#91;example] and &#91;rule: nope] and &#91;rule: the-mark-keeps-its-clear-space] and &#91;[fill: more]] out of the text" in notes
    assert "[the page]&#40;../../../../etc/shadow) and ![x]&#40;missing.png)" in notes
    assert "Padding 48px, 4.5:1, #1a2b3c, rgb(1 2 3), 100% and 3 em dashes" in notes                              # a value on a tagged line is cited by the tag, so it stays as written
    assert "Approved: 2026-10-17 approved start with 3 &#101;m dashes and {{color.bg}}; &#91;[fill: x]] &#91;example]" in notes     # the approval has no tag: its value is broken
    fill_owned(kit_of(pack))
    assert build(pack).returncode == 0
    r = kit_check(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert statuses(pack) == pages_pass("start")
    tags = check_report_rows(pack)["kit:tags"]["detail"]
    assert tags.startswith(f"{len(NASTY) * 2} line(s) carry")                                                         # the ten bullets of the notes


def test_a_site_record_that_does_not_validate_stops_the_build(pack):
    with_site(pack)
    site = pack / "site" / "site.json"
    good = site.read_bytes()
    mutate_json(site, lambda d: (d["pages"][0].__setitem__("layout", "no-such-layout"), d["choices"][0].__setitem__("source", ""), d["choices"][1].__setitem__("tag", "maybe"),
                                 d.__setitem__("hero", "")))
    for args in (("--yes",), ("--plan",)):
        r = bc("kit", "build", *args, project=pack)
        assert r.returncode == 1, (args, r.stdout, r.stderr)
        assert "site/site.json does not validate, so no reference page can go into the kit: " in r.stderr
        first = r.stderr.split("into the kit: ")[1]
        assert first.startswith("hero is empty: it names the hero variant the pages were built from; start: the layout 'no-such-layout' is no id of page-layouts.json (one-step, "), first
        assert "; c1: a rule says where it was decided (source is empty)" in first, first
        assert "and 1 more. Fix it" in first and "maybe" not in first, first                                                  # the first three are quoted, the fourth is only counted
    untouched(pack)
    site.write_bytes(good)
    page = pack / "site" / "start" / "index.html"                                                                         # a page edited by hand after it was approved
    mutate(page, "One calm place", "One calmer place")
    r = build(pack)
    assert r.returncode == 1 and "site/start/index.html changed since it was approved" in r.stderr and "site approve --replace" in r.stderr
    untouched(pack)
    mutate(page, "One calmer place", "One calm place")
    site.write_text("{not json", encoding="utf-8")                                                                        # a record that cannot be read
    r = build(pack)
    assert r.returncode == 1 and "site/site.json cannot be read" in r.stderr
    untouched(pack)
    site.write_bytes(good)
    (pack / "site" / "start" / "index.html").unlink()                                                                     # a page that is gone
    r = build(pack)
    assert r.returncode == 1 and "site/start/index.html is missing" in r.stderr
    untouched(pack)


def test_a_reference_page_that_is_changed_is_copied_again_and_the_sources_say_so(pack):
    with_site(pack)
    filled_kit(pack)                                                                                                      # built, the owner's files filled in, built again: version 1.2
    before = kit_json(pack)
    assert kit_check(pack).returncode == 0
    edit_page(pack, "One calm place for your orders", "One calm place for all your orders")
    r = kit_check(pack)                                                                                                     # the kit was built from the page as it was
    assert r.returncode == 3, r.stdout + r.stderr
    assert check_report_rows(pack)["kit:sources"]["status"] == "skipped" and "(pages)" in check_report_rows(pack)["kit:sources"]["detail"]
    state = check_rows(pack)["kit:state"]                                                                                   # and `check` says the same, naming the reference pages
    assert state["status"] == "skipped" and "fonts, reference pages, masters or motion spec changed since the kit report" in state["detail"], state
    assert build(pack).returncode == 0
    after = kit_json(pack)
    assert after["version"] == "1.3" and after["sources"]["pages"] != before["sources"]["pages"]
    assert after["reference_pages"][0]["source_sha"] == file_sha(pack / START) != before["reference_pages"][0]["source_sha"]
    assert "calm place for all your orders" in (kit_of(pack) / "brand" / "site" / "start" / "index.html").read_text(encoding="utf-8")
    assert filecmp.cmp(pack / START, kit_of(pack) / "brand" / START, shallow=False)
    assert kit_check(pack).returncode == 0
    # a file the page loads from outside its folder is a source too
    mutate(pack / "assets" / "web" / "dot.svg", "circle", "ellipse")
    assert kit_check(pack).returncode == 3 and "(pages)" in check_report_rows(pack)["kit:sources"]["detail"]
    assert build(pack).returncode == 0 and kit_json(pack)["version"] == "1.4"
    assert (kit_of(pack) / "brand" / "assets" / "web" / "dot.svg").read_text(encoding="utf-8") == (pack / "assets" / "web" / "dot.svg").read_text(encoding="utf-8")
    # the pages leave the project: their files leave the kit, moved to removed-<date>/ and never deleted
    shutil.rmtree(pack / "site")
    assert build(pack).returncode == 0
    assert kit_files(pack) == KIT_FILES and kit_json(pack)["reference_pages"] == [] and kit_json(pack)["sources"]["pages"] is None
    assert (pack / KIT_REMOVED / "brand" / "site" / "start" / "index.html").is_file() and (pack / KIT_REMOVED / "reference-pages" / "start" / "notes.md").is_file()


def test_a_font_a_page_loads_follows_the_font_rule(pack):
    with_site(pack)
    with_font(pack)
    css = pack / "site" / "start" / "site.css"
    css.write_text(css.read_text(encoding="utf-8") + '@font-face { font-family: "Inter"; src: url("../../assets/fonts/TestFont-subset.ttf") format("truetype"); }\n', encoding="utf-8")
    r = build(pack)                                                                                                   # an OFL font is copied by the font rule, once, with its licence
    assert r.returncode == 0, r.stdout + r.stderr
    assert kit_files(pack) == sorted([*KIT_FILES, *FONT_KIT, *PAGE_KIT])
    assert pages_row(pack)["status"] == "pass"
    fill_owned(kit_of(pack))
    assert build(pack).returncode == 0 and kit_check(pack).returncode == 0
    # a font that is not OFL is listed and not copied, a page that loads it is told so, and the link does not resolve in the kit: `kit check` warns that the font must be supplied under its own licence
    mutate_json(pack / "assets" / "_checks" / "fontcheck.json",
                lambda d: next(x for x in d["results"] if x["id"] == "licence:assets/fonts/TestFont-subset.ttf").__setitem__("recognised", "Apache License"))
    r = build(pack, "--replace")
    assert r.returncode == 0, r.stdout + r.stderr
    assert not (kit_of(pack) / "brand" / "assets" / "fonts" / "TestFont-subset.ttf").exists()
    row = pages_row(pack)
    assert row["status"] == "warn" and "assets/fonts/TestFont-subset.ttf loaded at site/start/site.css:" in row["detail"] and NOT_OFL in row["detail"], row
    assert report(pack, "kit")["status"] == "pass"
    r = kit_check(pack)
    assert r.returncode == 0, r.stdout + r.stderr                                                                     # a warning, never a pass in silence: the font is listed, not missing
    links = check_report_rows(pack)["kit:links"]
    assert links["status"] == "warn" and "-> ../../assets/fonts/TestFont-subset.ttf (brand/assets/fonts/TestFont-subset.ttf: " + NOT_OFL + ")" in links["detail"], links
    assert "the font must be supplied under its own licence" in links["detail"] and "[WARN] kit:links" in r.stdout
    assert statuses(pack) == {**pages_pass("start"), "kit:links": "warn"}


def test_kit_json_must_describe_its_reference_pages(pack):
    import kitlib
    from _common import CliError
    with_site(pack)
    assert build(pack).returncode == 0
    f = kit_of(pack) / "kit.json"
    sha = "a" * 64
    cases = [("no key", lambda d: d.pop("reference_pages"), "reference_pages: missing"),
             ("not a list", lambda d: d.__setitem__("reference_pages", {}), "reference_pages: must be a list"),
             ("an unknown key", lambda d: d["reference_pages"][0].__setitem__("hero", "x"), "reference_pages[0].hero: unknown key"),
             ("a key left out", lambda d: d["reference_pages"][0].pop("capture_inputs_sha"), "reference_pages[0].capture_inputs_sha: missing"),
             ("not a sha", lambda d: d["reference_pages"][0].__setitem__("source_sha", "x"), "reference_pages[0].source_sha: must be a sha256"),
             ("another page path", lambda d: d["reference_pages"][0].__setitem__("page", "brand/site/other/index.html"), "reference_pages[0].page: must be brand/site/<id>/index.html of its id"),
             ("a page listed twice", lambda d: d["reference_pages"].append(dict(d["reference_pages"][0])), "'start' is listed twice"),
             *[(f"the id {pid!r}", lambda d, pid=pid: d["reference_pages"][0].update(id=pid, page=f"brand/site/{pid}/index.html"), "reference_pages[0].id: must be a page id")
               for pid in (".", "..", "Start", "a b", "s", "start/")],                                          # the ids of sitedata.SITE_PAGE_ID only: G3-17 reads site/<id>/ from them
             ("an unknown source", lambda d: d["sources"].__setitem__("pagess", sha), "sources.pagess: unknown key"),
             ("a source left out", lambda d: d["sources"].pop("pages"), "sources.pages: missing")]
    for why, change, said in cases:
        good = f.read_bytes()
        mutate_json(f, change)
        with pytest.raises(CliError) as e:
            kitlib.load(pack)
        assert e.value.code == 2 and said in "\n".join(kitlib.problems(json.loads(f.read_text(encoding="utf-8")))), (why, e.value.message)
        f.write_bytes(good)
    assert kitlib.load(pack)["reference_pages"][0]["id"] == "start"


# ---------------------------------------------------------------- kit check, reference pages: a row for each page the kit holds
# `kit:reference-page:<id>` says whether the kit's copy of a page still stands for the brand. The reports and stills here are made by hand (settle_page); `settle_with_rules` makes a page-check
# report from the rules too (qa/rules.json and the G4 rules of BRAND-STATE.md), as a real `page-check` report is. A real run is the one in test_a_reference_page_without_a_passing_page_check_stops_the_build.
from helpers import capture_record, page_check_report  # noqa: E402

RULES_INPUTS = ("qa/rules.json", "BRAND-STATE.md#g4-rules")
PASS_DETAIL = "site/start/index.html is the page the kit holds, its page check passes, and its report and stills were made from the files the kit was built from"
CHANGED_PAGE = "not verified: the page changed in the project since the kit was built: `brand-creator kit build --yes`"


def page_row(p, pid="start") -> dict:
    return check_report_rows(p)[f"kit:reference-page:{pid}"]


def redo(pid="start") -> str:
    page = f"site/{pid}/index.html"
    return f"run `brand-creator page-check {page}` and `brand-creator capture {page}`, then `brand-creator kit build --yes`"


def tokens_changed(pid="start") -> str:
    return f"not verified: the tokens or rules changed since this page was checked: {redo(pid)}"


def cannot_use(what, why, pid="start") -> str:
    return f"not verified: the {what} of site/{pid}/index.html cannot be used ({why}): {redo(pid)}"


def settle_with_rules(p, pid="start", status="pass"):
    page_check_report(p, f"site/{pid}/index.html", status, also=RULES_INPUTS)
    capture_record(p, f"site/{pid}/index.html")


def test_a_token_change_makes_a_reference_page_not_verified(pack):
    with_site(pack)
    filled_kit(pack)
    r = kit_check(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert statuses(pack) == pages_pass("start") and page_row(pack)["detail"] == PASS_DETAIL
    assert [x["id"] for x in report(pack, "kit-check")["results"]][-1] == "kit:reference-page:start"           # after the rows of the kit itself
    assert {"site/site.json", "site/start/shots/capture.json", page_report(pack).relative_to(pack).as_posix()} <= {i["path"] for i in report(pack, "kit-check")["inputs"]}
    mutate(pack / "assets" / "tokens" / "tokens.css", ":root", ":root /* edited */")                           # the tokens changed after the kit was built and the page was checked
    r = kit_check(pack)
    assert r.returncode == 3, r.stdout + r.stderr
    assert page_row(pack)["status"] == "skipped" and page_row(pack)["detail"] == tokens_changed()
    assert report(pack, "kit-check")["status"] == "not-verified" and "[SKIP] kit:reference-page:start" in r.stdout
    page_check_report(pack, START, "pass")                                                                        # the page is checked again, the stills are not
    assert kit_check(pack).returncode == 3 and page_row(pack)["detail"] == tokens_changed()
    capture_record(pack, START)                                                                                   # and the stills are taken again: the kit still holds the old tokens
    assert kit_check(pack).returncode == 3 and page_row(pack)["detail"] == tokens_changed()
    assert build(pack).returncode == 0 and kit_json(pack)["version"] == "1.3"                                     # build: the kit holds the new tokens and what the page was checked against
    assert kit_json(pack)["reference_pages"][0]["page_check_inputs_sha"] == json.loads(page_report(pack).read_text(encoding="utf-8"))["inputs_sha"]
    r = kit_check(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert statuses(pack) == pages_pass("start")


def test_a_change_of_the_rules_makes_a_reference_page_not_verified(pack):
    assert bc("state", "--record", "G4", "approved (test)", project=pack).returncode == 0                            # a page check reads the G4 rule lines once G4 is recorded
    with_site(pack)
    settle_with_rules(pack)
    filled_kit(pack)
    assert kit_check(pack).returncode == 0 and statuses(pack) == pages_pass("start")
    mutate_json(pack / "qa" / "rules.json", lambda d: d.__setitem__("page", {"rules": [{"id": "one-mark", "kind": "max-marks-per-view", "max": 1, "g4": "one mark per screen"}]}))
    assert kit_check(pack).returncode == 3 and page_row(pack)["detail"] == tokens_changed()                      # the page rules are rules
    settle_with_rules(pack)
    assert kit_check(pack).returncode == 3 and page_row(pack)["detail"] == tokens_changed()                      # checked against the new rules; the kit holds the old ones
    assert build(pack).returncode == 0 and kit_check(pack).returncode == 0 and statuses(pack) == pages_pass("start")
    record_rules(pack, "The mark keeps its clear space")                                                          # a G4 rule recorded after the page was checked
    assert kit_check(pack).returncode == 3 and page_row(pack)["detail"] == tokens_changed()
    settle_with_rules(pack)
    assert build(pack).returncode == 0 and kit_check(pack).returncode == 0 and statuses(pack) == pages_pass("start")


def test_a_reference_page_approved_again_makes_its_kit_copy_not_verified(pack):
    with_site(pack)
    filled_kit(pack)
    assert kit_check(pack).returncode == 0
    site, page = pack / "site" / "site.json", pack / "site" / "start" / "index.html"
    edit_page(pack, "One calm place for your orders", "One calm place for all your orders")                      # approved again: the record follows, and the page is checked and captured again
    r = kit_check(pack)
    assert r.returncode == 3, r.stdout + r.stderr
    assert page_row(pack)["status"] == "skipped" and page_row(pack)["detail"] == CHANGED_PAGE                    # the page, not the tokens: the new report's inputs differ for that reason
    assert build(pack).returncode == 0 and kit_json(pack)["version"] == "1.3"
    assert kit_check(pack).returncode == 0 and statuses(pack) == pages_pass("start")
    mutate(page, "for all your orders", "for just your orders")                                                   # edited and not approved again: the record still holds the sha256 of the build
    assert kit_check(pack).returncode == 3 and page_row(pack)["detail"] == CHANGED_PAGE                          # and its report is stale as well: the page is named first
    mutate(page, "for just your orders", "for all your orders")
    assert kit_check(pack).returncode == 0 and statuses(pack) == pages_pass("start")
    good = site.read_bytes()
    mutate_json(site, lambda d: d["pages"][0].__setitem__("sha256", "0" * 64))                                    # a record that holds another sha256 than the kit was built from
    assert kit_check(pack).returncode == 3 and page_row(pack)["detail"] == CHANGED_PAGE
    site.write_bytes(good)
    mutate_json(site, lambda d: d.__setitem__("pages", []))                                                       # a page the record no longer lists
    assert kit_check(pack).returncode == 3
    assert page_row(pack)["detail"] == "not verified: the page changed in the project since the kit was built (site/site.json no longer lists it): `brand-creator kit build --yes`"
    site.write_bytes(good)
    site.write_text("{not json", encoding="utf-8")                                                                # a record that cannot be read: every page is not verified, naming why
    r = kit_check(pack)
    assert r.returncode == 3, r.stdout + r.stderr
    assert page_row(pack)["status"] == "skipped" and page_row(pack)["detail"].startswith("not verified: the approved pages cannot be read (site/site.json cannot be read (")
    assert page_row(pack)["detail"].endswith(")): `brand-creator kit build --yes` after fixing it") and "Traceback" not in r.stderr
    site.write_bytes(good)
    assert kit_check(pack).returncode == 0 and statuses(pack) == pages_pass("start")


def test_stills_taken_again_make_the_kit_copy_not_verified(pack):
    with_site(pack)
    filled_kit(pack)
    assert kit_check(pack).returncode == 0
    shots, base = pack / "site" / "start" / "shots", pack / "assets" / "web" / "base.css"
    checked = page_report(pack).read_bytes()
    mutate_json(shots / "capture.json", lambda d: d["inputs"].append({"path": "assets/web/base.css", "sha256": file_sha(base)}))   # stills taken again, the browser served one more file
    r = kit_check(pack)
    assert r.returncode == 3, r.stdout + r.stderr
    assert page_row(pack)["status"] == "skipped" and page_row(pack)["detail"] == tokens_changed()
    assert page_report(pack).read_bytes() == checked and json.loads(checked)["inputs_sha"] == kit_json(pack)["reference_pages"][0]["page_check_inputs_sha"]     # the page check is as it was
    assert build(pack).returncode == 0
    capture = json.loads((shots / "capture.json").read_text(encoding="utf-8"))
    assert kit_json(pack)["reference_pages"][0]["capture_inputs_sha"] == inputs_hash(capture) and kit_json(pack)["version"] == "1.3"
    assert kit_check(pack).returncode == 0 and statuses(pack) == pages_pass("start")
    mutate_json(shots / "capture.json", lambda d: d["inputs"][0].__setitem__("sha256", "0" * 64))                    # stills whose record no longer stands for the page
    assert kit_check(pack).returncode == 3 and page_row(pack)["detail"] == tokens_changed()


def test_a_failing_page_check_fails_the_reference_page_row(pack):
    with_site(pack)
    settle_with_rules(pack)
    filled_kit(pack)
    assert kit_check(pack).returncode == 0
    mutate_json(pack / "qa" / "rules.json", lambda d: d.__setitem__("page", {"rules": [{"id": "one-mark", "kind": "max-marks-per-view", "max": 1, "g4": "one mark per screen"}]}))
    settle_with_rules(pack, status="fail")                                                                          # the page is checked against the new rules and fails: current, and failing
    r = kit_check(pack)
    assert r.returncode == 1, r.stdout + r.stderr
    row = page_row(pack)
    assert row["status"] == "fail" and report(pack, "kit-check")["status"] == "fail" and "[FAIL] kit:reference-page:start" in r.stdout
    assert row["detail"].startswith("site/start/index.html fails its page check (page:load:390-light; see assets/_checks/page-check/")
    assert row["detail"].endswith(f"a reference page is a page that passes, so change it, approve it again (`brand-creator site approve --replace`), then {redo()}")
    assert check_report_rows(pack)["kit:sources"]["status"] == "skipped"                                           # the rules changed after the kit was built: a failure still wins the exit code
    mutate_json(pack / "site" / "start" / "shots" / "capture.json", lambda d: d["inputs"][0].__setitem__("sha256", "0" * 64))   # a stale record of the stills does not hide it
    assert kit_check(pack).returncode == 1 and page_row(pack)["status"] == "fail"
    settle_with_rules(pack, status="not-verified")                                                                  # a report that gives no verdict is not a pass, and not a fail
    r = kit_check(pack)
    assert r.returncode == 3, r.stdout + r.stderr
    assert page_row(pack)["status"] == "skipped" and page_row(pack)["detail"].startswith("not verified: the page-check report of site/start/index.html gives no verdict (status 'not-verified'; see assets/_checks/page-check/")
    settle_with_rules(pack)                                                                                         # passes now; the kit still holds the old rules
    assert kit_check(pack).returncode == 3 and page_row(pack)["detail"] == tokens_changed()
    assert build(pack).returncode == 0 and kit_check(pack).returncode == 0 and statuses(pack) == pages_pass("start")


def test_a_failing_report_written_after_the_check_makes_check_ask_for_kit_check_again(pack):
    with_site(pack)
    filled_kit(pack)
    assert kit_check(pack).returncode == 0 and check_rows(pack)["report:kit-check"]["status"] == "pass"
    mutate_json(page_report(pack), lambda d: d.__setitem__("status", "fail"))                                      # the page-check report changed after `kit check` ran
    row = check_rows(pack)["report:kit-check"]
    assert row["status"] == "skipped" and "stale" in row["detail"], row
    r = kit_check(pack)                                                                                             # and the new report is judged by the next `kit check`
    assert r.returncode == 1 and page_row(pack)["status"] == "fail"
    assert check_rows(pack)["report:kit-check"]["status"] == "fail"


def test_a_record_the_row_cannot_use_is_not_verified_and_never_a_pass(pack, tmp_path):
    from helpers import symlink_or_skip
    with_site(pack)
    filled_kit(pack)
    assert kit_check(pack).returncode == 0
    tool = page_report(pack)
    where = tool.relative_to(pack).as_posix()
    shots = pack / "site" / "start" / "shots" / "capture.json"
    good_report, good_shots = tool.read_bytes(), shots.read_bytes()

    def row_is(detail, *, startswith=False):
        r = kit_check(pack)
        assert r.returncode == 3, (detail, r.stdout, r.stderr)
        got = page_row(pack)
        assert got["status"] == "skipped" and (got["detail"].startswith(detail) if startswith else got["detail"] == detail), got
        assert "Traceback" not in r.stderr

    tool.unlink()
    row_is(cannot_use("page-check report", f"{where} is missing"))
    tool.write_text("{not json", encoding="utf-8")
    row_is(cannot_use("page-check report", f"{where} cannot be read"))
    doc = json.loads(good_report)
    doc["target"]["page"] = "site/other/index.html"
    tool.write_text(json.dumps(doc), encoding="utf-8")
    row_is(cannot_use("page-check report", f"{where} is the report of another target"))
    doc = json.loads(good_report)
    doc["inputs"] = [x for x in doc["inputs"] if x["path"] != START]
    tool.write_text(json.dumps(doc), encoding="utf-8")
    row_is(cannot_use("page-check report", f"{where} does not list the page among the files it was made from"))
    tool.write_text(json.dumps({"inputs": "not a list"}), encoding="utf-8")
    row_is(cannot_use("page-check report", f"{where} cannot be read"))
    tool.unlink()
    far = tmp_path / "outside.json"
    far.write_bytes(good_report)
    symlink_or_skip(tool, far)                                                                                      # a link to a report beyond the project is never read through
    row_is("not verified: the page-check report of site/start/index.html cannot be used (", startswith=True)
    assert "outside the project" in page_row(pack)["detail"]
    tool.unlink()
    tool.write_bytes(good_report)
    shots.unlink()
    row_is(cannot_use("stills", "site/start/shots/capture.json is missing"))
    shots.write_text("[]", encoding="utf-8")
    row_is(cannot_use("stills", "site/start/shots/capture.json cannot be read"))
    doc = json.loads(good_shots)
    doc["source"]["page"] = "site/other/index.html"
    shots.write_text(json.dumps(doc), encoding="utf-8")
    row_is(cannot_use("stills", "site/start/shots/capture.json is the capture of another page"))
    doc = json.loads(good_shots)
    doc["inputs"] = [x for x in doc["inputs"] if x["path"] != START]
    shots.write_text(json.dumps(doc), encoding="utf-8")
    row_is(cannot_use("stills", "site/start/shots/capture.json does not list the page among the files it was made from"))
    shots.write_bytes(good_shots)
    assert kit_check(pack).returncode == 0 and statuses(pack) == pages_pass("start")                                # both records back as they were: a pass again
    page = pack / "site" / "start" / "index.html"
    good_page, beyond = page.read_bytes(), tmp_path / "outside.html"
    beyond.write_bytes(good_page)                                                                                   # byte for byte the page the kit holds: a read through the link would pass
    page.unlink()
    symlink_or_skip(page, beyond)                                                                                   # a page that is a link to a file beyond the project is never hashed
    row_is("not verified: the page site/start/index.html cannot be used (", startswith=True)
    assert "outside the project" in page_row(pack)["detail"] and page_row(pack)["detail"].endswith("): `brand-creator kit build --yes` after fixing it")
    page.unlink()
    page.write_bytes(good_page)
    assert kit_check(pack).returncode == 0 and statuses(pack) == pages_pass("start")                                # a plain file again: a pass
    site = pack / "site" / "site.json"
    good_site, record_beyond = site.read_bytes(), tmp_path / "record.json"
    record_beyond.write_bytes(good_site)                                                                            # byte for byte the record the kit was built from: a read through the link would pass
    site.unlink()
    symlink_or_skip(site, record_beyond)                                                                            # a record that is a link to a file beyond the project is never read through
    row_is("not verified: the approved pages cannot be read (", startswith=True)
    assert "outside the project" in page_row(pack)["detail"] and page_row(pack)["detail"].endswith("): `brand-creator kit build --yes` after fixing it")
    site.unlink()
    site.write_bytes(good_site)
    assert kit_check(pack).returncode == 0 and statuses(pack) == pages_pass("start")                                # a plain file again: a pass


def test_each_reference_page_gets_its_own_row_and_a_change_marks_only_its_page(pack):
    with_site(pack)
    text = (pack / "site" / "start" / "index.html").read_text(encoding="utf-8").replace('data-page="start"', 'data-page="pricing"')
    (pack / "site" / "pricing").mkdir()
    (pack / "site" / "pricing" / "index.html").write_text(text, encoding="utf-8")
    shutil.copy2(pack / "site" / "start" / "site.css", pack / "site" / "pricing" / "site.css")
    shutil.copytree(pack / "site" / "start" / "img", pack / "site" / "pricing" / "img")
    site = json.loads((pack / "site" / "site.json").read_text(encoding="utf-8"))
    site["pages"].append({"id": "pricing", "path": "site/pricing/index.html", "layout": "own:ledger", "sha256": file_sha(pack / "site" / "pricing" / "index.html")})
    (pack / "site" / "site.json").write_text(json.dumps(site, indent=2) + "\n", encoding="utf-8")
    settle_page(pack, "pricing")
    filled_kit(pack)
    assert kit_check(pack).returncode == 0
    assert statuses(pack) == pages_pass("start", "pricing")
    assert [x["id"] for x in report(pack, "kit-check")["results"] if x["id"].startswith("kit:reference-page:")] == ["kit:reference-page:start", "kit:reference-page:pricing"]   # kit.json's order
    mutate(pack / "site" / "pricing" / "index.html", "One calm place for your orders", "One calm place for all your orders")
    mutate_json(pack / "site" / "site.json", lambda d: next(x for x in d["pages"] if x["id"] == "pricing").__setitem__("sha256", file_sha(pack / "site" / "pricing" / "index.html")))
    settle_page(pack, "pricing")
    assert kit_check(pack).returncode == 3
    assert statuses(pack) == {**pages_pass("start", "pricing"), "kit:reference-page:pricing": "skipped", "kit:sources": "skipped"}
    assert page_row(pack, "pricing")["detail"] == CHANGED_PAGE
    page_check_report(pack, "site/start/index.html", "fail")                                                         # and a failure of one page is the failure of that page
    assert kit_check(pack).returncode == 1
    assert (page_row(pack)["status"], page_row(pack, "pricing")["status"]) == ("fail", "skipped")


# ---------------------------------------------------------------- fonts a page brings, links to folders, pages that are links leading out (F3-05)
# A font in a page folder, or one a page loads from outside assets/fonts/, goes by the font rule of assets/fonts/ (D6): copied only when the fontcheck report has read it as OFL and an OFL text sits in
# assets/fonts/, otherwise listed in kit.json fonts.not_copied. fontcheck reads assets/fonts/ alone unless `--font` names a font, so these fonts are read with `--font`.
PAGE_FONT = "site/start/fonts/Brought.ttf"
LOADED_FONT = "assets/web/Other.ttf"
CHECK_THEM = ("run `brand-creator fontcheck --font FILE` naming every font the kit holds outside assets/fonts/, this one included (fontcheck always "
              "reads the fonts of assets/fonts/ too, and a run reads only the other fonts it names), then `kit build`")
OFL_LABEL = "SIL Open Font License (OFL)"


def bring_font(p, rel):
    """A copy of the OFL test font at the project path `rel`."""
    f = p / rel
    f.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(TEST_FONT, f)


def put_licence_text(p):
    d = p / "assets" / "fonts"
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy2(OFL_TEXT, d / "OFL.txt")


def read_fonts(p, *rels):
    """fontcheck reads the named fonts, which gives each a `licence:<project path>` row, and reads no other."""
    r = bc("fontcheck", "--lang", "en", "--no-platform", *[a for rel in rels for a in ("--font", str(p / rel))], project=p)
    assert r.returncode == 0, r.stdout + r.stderr
    assert all(f"licence:{rel}" in {x["id"] for x in report(p, "fontcheck")["results"]} for rel in rels)


def copied_font(path):
    return {"file": path, "licence": OFL_LABEL, "licence_files": ["brand/assets/fonts/OFL.txt"]}


def test_a_font_inside_a_page_folder_follows_the_font_rule(pack):
    with_site(pack)
    put_licence_text(pack)
    bring_font(pack, PAGE_FONT)
    # no fontcheck report: the font is listed with a reason that says to check the fonts, and is not copied
    r = build(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert kit_json(pack)["fonts"] == {"copied": [], "not_copied": [{"file": PAGE_FONT, "reason": f"no current fontcheck report: {CHECK_THEM}"}]}
    assert kit_files(pack) == sorted([*KIT_FILES, *PAGE_KIT]) and not (kit_of(pack) / "brand" / PAGE_FONT).exists()
    row = pages_row(pack)
    assert row["status"] == "warn" and f"{PAGE_FONT} sits in the page folder (no current fontcheck report: " in row["detail"], row
    assert report(pack, "kit")["status"] == "pass" and PAGE_FONT in {i["path"] for i in report(pack, "kit")["inputs"]}
    # a current report that has read another font only: this one is a font fontcheck has not read
    with_font(pack)
    r = build(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert kit_json(pack)["fonts"] == {"copied": [copied_font("brand/assets/fonts/TestFont-subset.ttf")],
                                       "not_copied": [{"file": PAGE_FONT, "reason": f"fontcheck has not read it: {CHECK_THEM}"}]}
    assert not (kit_of(pack) / "brand" / PAGE_FONT).exists()
    # fontcheck reads both: the page's font is copied at its project path, with the licence text, and fonts.css keeps the font of assets/fonts/ alone
    read_fonts(pack, "assets/fonts/TestFont-subset.ttf", PAGE_FONT)
    r = build(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert kit_json(pack)["fonts"] == {"copied": [copied_font("brand/assets/fonts/TestFont-subset.ttf"), copied_font(f"brand/{PAGE_FONT}")], "not_copied": []}
    assert kit_files(pack) == sorted([*KIT_FILES, *FONT_KIT, *PAGE_KIT, f"brand/{PAGE_FONT}"])
    assert filecmp.cmp(TEST_FONT, kit_of(pack) / "brand" / PAGE_FONT, shallow=False)
    assert (kit_of(pack) / "snippets" / "fonts.css").read_text(encoding="utf-8") == FONT_FACE
    assert pages_row(pack)["status"] == "pass"
    fill_owned(kit_of(pack))
    assert build(pack).returncode == 0
    assert kit_check(pack).returncode == 0 and statuses(pack) == pages_pass("start")
    # the licence of the page's font is not OFL: it is listed and not copied, and the kit does not keep the copy of the last build
    mutate_json(pack / "assets" / "_checks" / "fontcheck.json",
                lambda d: next(x for x in d["results"] if x["id"] == f"licence:{PAGE_FONT}").__setitem__("recognised", "Apache License"))
    r = build(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert kit_json(pack)["fonts"] == {"copied": [copied_font("brand/assets/fonts/TestFont-subset.ttf")], "not_copied": [{"file": PAGE_FONT, "reason": NOT_OFL}]}
    assert not (kit_of(pack) / "brand" / PAGE_FONT).exists() and (pack / PAGE_FONT).is_file()                           # moved aside from the kit, and the project's own file is as it was
    assert pages_row(pack)["status"] == "warn" and f"{PAGE_FONT} sits in the page folder ({NOT_OFL})" in pages_row(pack)["detail"]
    # a font that changed after fontcheck read it: the report is stale, so no font is copied and the build is not verified (the font of assets/fonts/ has no current report either)
    read_fonts(pack, "assets/fonts/TestFont-subset.ttf", PAGE_FONT)
    with (pack / PAGE_FONT).open("ab") as fh:
        fh.write(b"\0")
    r = build(pack)
    assert r.returncode == 3, r.stdout + r.stderr
    assert kit_json(pack)["fonts"] == {"copied": [], "not_copied": [{"file": "assets/fonts/TestFont-subset.ttf", "reason": NO_FONTCHECK},
                                                                     {"file": PAGE_FONT, "reason": f"no current fontcheck report: {CHECK_THEM}"}]}


def test_a_font_a_page_loads_from_outside_assets_fonts_follows_the_font_rule(pack):
    with_site(pack)
    put_licence_text(pack)
    bring_font(pack, LOADED_FONT)
    css = pack / "site" / "start" / "site.css"
    css.write_text(css.read_text(encoding="utf-8") + '@font-face { font-family: "Other"; src: url("../../assets/web/Other.ttf") format("truetype"); }\n', encoding="utf-8")
    r = build(pack)                                                                                                   # fontcheck has read nothing: the font is listed, not copied
    assert r.returncode == 0, r.stdout + r.stderr
    assert kit_json(pack)["fonts"] == {"copied": [], "not_copied": [{"file": LOADED_FONT, "reason": f"no current fontcheck report: {CHECK_THEM}"}]}
    assert kit_files(pack) == sorted([*KIT_FILES, *PAGE_KIT]) and not (kit_of(pack) / "brand" / LOADED_FONT).exists()
    row = pages_row(pack)
    assert row["status"] == "warn" and f"{LOADED_FONT} loaded at site/start/site.css:" in row["detail"] and "supply it under its own licence" in row["detail"], row
    fill_owned(kit_of(pack))
    assert build(pack).returncode == 0
    r = kit_check(pack)                                                                                               # the link to the font is no broken link, and no silent pass
    assert r.returncode == 0, r.stdout + r.stderr
    links = check_report_rows(pack)["kit:links"]
    assert links["status"] == "warn" and f"-> ../../assets/web/Other.ttf (brand/{LOADED_FONT}: no current fontcheck report: " in links["detail"], links
    assert "the font must be supplied under its own licence" in links["detail"] and "[WARN] kit:links" in r.stdout
    assert statuses(pack) == {**pages_pass("start"), "kit:links": "warn"}
    # fontcheck reads it: OFL by its name table, with the OFL text in assets/fonts/: copied at its project path, and the link resolves
    read_fonts(pack, LOADED_FONT)
    r = build(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert kit_json(pack)["fonts"] == {"copied": [copied_font(f"brand/{LOADED_FONT}")], "not_copied": []}
    assert filecmp.cmp(TEST_FONT, kit_of(pack) / "brand" / LOADED_FONT, shallow=False) and (kit_of(pack) / "brand" / "assets" / "fonts" / "OFL.txt").is_file()
    assert not (kit_of(pack) / "snippets" / "fonts.css").exists()                                                       # no font of assets/fonts/: no snippet
    assert pages_row(pack)["status"] == "pass"
    assert kit_check(pack).returncode == 0 and statuses(pack) == pages_pass("start")
    # not OFL: listed and not copied again, and the link is a warning again
    mutate_json(pack / "assets" / "_checks" / "fontcheck.json",
                lambda d: next(x for x in d["results"] if x["id"] == f"licence:{LOADED_FONT}").__setitem__("recognised", "Apache License"))
    r = build(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert kit_json(pack)["fonts"] == {"copied": [], "not_copied": [{"file": LOADED_FONT, "reason": NOT_OFL}]} and not (kit_of(pack) / "brand" / LOADED_FONT).exists()
    assert kit_check(pack).returncode == 0 and statuses(pack) == {**pages_pass("start"), "kit:links": "warn"}
    # OFL by its name table but the licence text is gone from assets/fonts/: the same reason as for a font of assets/fonts/
    read_fonts(pack, LOADED_FONT)
    ofl = pack / "assets" / "fonts" / "OFL.txt"
    mutate(ofl, "SIL Open Font License", "Some Licence", count=99)
    mutate(ofl, "SIL OPEN FONT LICENSE", "SOME LICENCE", count=99)
    r = build(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert kit_json(pack)["fonts"] == {"copied": [], "not_copied": [{"file": LOADED_FONT, "reason": "OFL by its name table, but no OFL licence text in assets/fonts/: add the font's OFL.txt"}]}


def test_a_link_to_a_font_the_kit_does_not_copy_is_judged_by_its_exact_path_and_a_broken_link_still_fails(pack):
    """The warning is for a font kit.json lists. A link that spells the listed path in another letter case, a link to a font kit.json does not list, and a broken link beside a listed font still fail."""
    with_site(pack)
    put_licence_text(pack)
    bring_font(pack, LOADED_FONT)
    css = pack / "site" / "start" / "site.css"
    css.write_text(css.read_text(encoding="utf-8") + '@font-face { font-family: "Other"; src: url("../../assets/web/Other.ttf") format("truetype"); }\n', encoding="utf-8")
    filled_kit(pack)
    assert kit_check(pack).returncode == 0 and check_report_rows(pack)["kit:links"]["status"] == "warn"
    page = kit_of(pack) / "brand" / "site" / "start" / "site.css"
    other = page.read_text(encoding="utf-8")
    for why, link in (("another letter case", "../../assets/web/other.ttf"), ("an unlisted font", "../../assets/web/Third.ttf"), ("a folder", "../../assets/web/")):
        page.write_text(other + f'@font-face {{ font-family: "X"; src: url("{link}"); }}\n', encoding="utf-8")
        r = kit_check(pack)
        links = check_report_rows(pack)["kit:links"]
        assert links["status"] == "fail" and f"-> {link} (" in links["detail"] and "1 more leads to a font the kit does not copy" in links["detail"], (why, links)
        assert r.returncode == 1, (why, r.stdout)
    page.write_text(other, encoding="utf-8")
    assert kit_check(pack).returncode == 0                                                                           # the kit as it was built: a warning only


def second_page(p, pid="pricing"):
    """A second approved page, a copy of `start` (its record in site/site.json, its page check and stills as `settle_page` makes them)."""
    text = (p / "site" / "start" / "index.html").read_text(encoding="utf-8").replace('data-page="start"', f'data-page="{pid}"')
    (p / "site" / pid).mkdir()
    (p / "site" / pid / "index.html").write_text(text, encoding="utf-8")
    shutil.copy2(p / "site" / "start" / "site.css", p / "site" / pid / "site.css")
    shutil.copytree(p / "site" / "start" / "img", p / "site" / pid / "img")
    site = json.loads((p / "site" / "site.json").read_text(encoding="utf-8"))
    site["pages"].append({"id": pid, "path": f"site/{pid}/index.html", "layout": "own:ledger", "sha256": file_sha(p / "site" / pid / "index.html")})
    (p / "site" / "site.json").write_text(json.dumps(site, indent=2) + "\n", encoding="utf-8")
    settle_page(p, pid)


def test_pages_that_link_to_each_other_by_a_folder_url_go_into_the_kit(pack, tmp_path):
    """`href="../pricing/"` is accepted by `site approve` and is the folder's index.html, as a web server answers it. In the project that file is copied (an approved page is in the kit anyway), and in the kit
    `kit check` accepts a link to a folder that holds an index.html. A folder without one still fails, in the project and in the kit."""
    from helpers import symlink_or_skip
    with_site(pack)
    second_page(pack)
    (pack / "assets" / "web" / "more").mkdir()
    (pack / "assets" / "web" / "more" / "index.html").write_text("<!doctype html><title>More</title>\n", encoding="utf-8")
    edit_page(pack, '<a class="action" href="#plans">', '<a href="../pricing/">Prices</a> <a href="../pricing">Prices again</a> <a href="../../assets/web/more/">More</a> <a href="./">Here</a><a class="action" href="#plans">')
    r = build(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    pricing = ["brand/site/pricing/index.html", "brand/site/pricing/site.css", "brand/site/pricing/img/pic.svg", *[f"brand/site/pricing/shots/{n}" for n in SHOTS], "reference-pages/pricing/notes.md"]
    assert kit_files(pack) == sorted([*KIT_FILES, *PAGE_KIT, *pricing, "brand/assets/web/more/index.html"])           # a folder that is no approved page is copied as its index.html
    assert filecmp.cmp(pack / "assets" / "web" / "more" / "index.html", kit_of(pack) / "brand" / "assets" / "web" / "more" / "index.html", shallow=False)
    fill_owned(kit_of(pack))
    assert build(pack).returncode == 0
    r = kit_check(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert statuses(pack) == pages_pass("start", "pricing")
    # the kit side: a link to a folder in the kit is its index.html when the kit has one there
    recipe = kit_of(pack) / "recipes" / "web-page.md"
    recipe.write_text(recipe.read_text(encoding="utf-8") + "\nSee [the pricing page](../brand/site/pricing/) and [the pricing page again](../brand/site/pricing).\n", encoding="utf-8")
    assert build(pack).returncode == 0                                                                                # the owner's edit is recorded
    assert kit_check(pack).returncode == 0 and statuses(pack) == pages_pass("start", "pricing")
    mutate(recipe, "(../brand/site/pricing)", "(../brand/site/pricing/img/)")                                          # a folder in the kit without an index.html fails
    mutate(recipe, "(../brand/site/pricing/)", "(../brand/assets/logo/)")
    assert build(pack).returncode == 0
    r = kit_check(pack)
    assert r.returncode == 1, r.stdout + r.stderr
    links = check_report_rows(pack)["kit:links"]["detail"]
    assert "recipes/web-page.md:" in links and "-> ../brand/assets/logo/ (a folder, not a file)" in links and "-> ../brand/site/pricing/img/ (a folder, not a file)" in links, links
    # in the project a folder without an index.html stops the build, as it did, and says why
    mutate(recipe, "(../brand/assets/logo/)", "(../brand/site/pricing/)")
    mutate(recipe, "(../brand/site/pricing/img/)", "(../brand/site/pricing/)")
    edit_page(pack, 'href="../pricing/"', 'href="../"')
    for args in (("--yes",), ("--plan",)):
        r = bc("kit", "build", *args, project=pack)
        assert r.returncode == 1 and "leads to site, a folder, not a file: it holds no index.html" in r.stderr and "site/start/index.html:" in r.stderr, (args, r.stdout, r.stderr)
    edit_page(pack, 'href="../"', 'href="../pricing/"')
    assert build(pack).returncode == 0
    # and a folder URL whose index.html is a link leading out of the project is exit 2, never read
    far = tmp_path / "outside-index.html"
    far.write_bytes(SECRET)
    (pack / "assets" / "web" / "more" / "index.html").unlink()
    symlink_or_skip(pack / "assets" / "web" / "more" / "index.html", far)
    r = bc("kit", "build", "--yes", project=pack)
    assert r.returncode == 2 and "outside the project" in r.stderr and "assets/web/more/index.html" in r.stderr, r.stdout + r.stderr
    nothing_secret_in(pack)


@pytest.mark.parametrize("bytes_differ", [False, True], ids=["same-bytes", "other-bytes"])
def test_a_page_folder_or_index_that_is_a_link_leading_out_is_exit_2_whatever_the_bytes(pack, tmp_path, bytes_differ):
    """validate_site hashes each page, through a link too. A page folder or an index.html that is a link leading outside the project is exit 2 before that, so it is never exit 1 because the bytes behind
    the link are not the approved ones."""
    from helpers import symlink_or_skip
    with_site(pack)
    page, folder = pack / "site" / "start" / "index.html", pack / "site" / "start"
    for what in ("index.html", "folder"):
        outside = tmp_path / ("moved-index.html" if what == "index.html" else "moved-start")
        shutil.move(str(page if what == "index.html" else folder), str(outside))
        symlink_or_skip(page if what == "index.html" else folder, outside)
        beyond = outside if what == "index.html" else outside / "index.html"
        if bytes_differ:
            mutate(beyond, "One calm place", "One calmer place")                                                      # not the bytes the record holds
        for args in (("--yes",), ("--plan",)):
            r = bc("kit", "build", *args, project=pack)
            assert r.returncode == 2, (what, args, r.stdout, r.stderr)
            assert "outside the project" in r.stderr and "site/start" in r.stderr and "Traceback" not in r.stderr and "changed since it was approved" not in r.stderr, (what, r.stderr)
        untouched(pack)
        (page if what == "index.html" else folder).unlink()
        if bytes_differ:
            mutate(beyond, "One calmer place", "One calm place")
        shutil.move(str(outside), str(page if what == "index.html" else folder))
    r = build(pack)                                                                                                   # the pages as they were: the kit goes in
    assert r.returncode == 0, r.stdout + r.stderr


# ---------------------------------------------------------------- masters travel with the kit (K-01)
# Everything under assets/masters/ is copied into the kit at its project path (brand/assets/masters/...), byte for byte, listed in kit.json `generated`, and recorded in kit.json
# `sources.masters`. A font in it goes by the font rule of assets/fonts/ (copied only when fontcheck read it as OFL and an OFL text sits in assets/fonts/). A project without the folder
# builds the bytes it always did: no key, no row.
MASTER_PNG = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01master-png\x00\xff"
MASTER_PPTX = b"PK\x03\x04\x14\x00\x00\x00\x08\x00master-pptx\x00\x01\x02"
MASTER_PDF = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF\n\x00"
MASTER_HTML = ('<!doctype html>\n<html><head><link rel="stylesheet" href="ad.css"></head>\n'
               '<body><img src="ad.png" alt=""><img src="../../logo/mark.svg" alt=""></body></html>\n')
MASTER_CSS = '.ad { background: url("ad.png"); }\n'
MASTERS = {"assets/masters/ad/index.html": MASTER_HTML.encode(), "assets/masters/ad/ad.css": MASTER_CSS.encode(), "assets/masters/ad/ad.png": MASTER_PNG,
           "assets/masters/deck/deck.pptx": MASTER_PPTX, "assets/masters/deck/slides.pdf": MASTER_PDF}
MASTERS_KIT = sorted(f"brand/{rel}" for rel in MASTERS)
MASTER_FONT = "assets/masters/fonts/Master.ttf"


def with_masters(p, files=MASTERS):
    for rel, data in files.items():
        f = p / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(data)


def masters_row(p) -> dict:
    return next(r for r in report(p, "kit")["results"] if r["id"] == "kit:masters")


def test_a_master_and_its_picture_are_copied_byte_for_byte_and_listed(pack):
    with_masters(pack)
    r = bc("kit", "build", "--plan", project=pack)
    assert r.returncode == 0 and r.stdout.splitlines()[0] == "would write 20 generated files into .claude/skills/acme-brand/ (version 1.1)", r.stdout + r.stderr
    assert f"generated brand/assets/masters/ad/ad.png ({len(MASTER_PNG)} bytes)" in r.stdout.splitlines()
    assert not (pack / ".claude").exists()
    r = build(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert kit_files(pack) == sorted([*KIT_FILES, *MASTERS_KIT])
    for rel, data in MASTERS.items():
        assert (kit_of(pack) / "brand" / rel).read_bytes() == data, rel                   # byte for byte, the PNG, the PPTX and the PDF too
    kj = kit_json(pack)
    assert set(MASTERS_KIT) <= set(kj["generated"]) and all(file_sha(kit_of(pack) / rel) == sha for rel, sha in kj["generated"].items())
    assert kj["generated"]["brand/assets/masters/ad/ad.png"] == hashlib.sha256(MASTER_PNG).hexdigest()
    expected = hashlib.sha256("".join(f"{rel}\0{hashlib.sha256(MASTERS[rel]).hexdigest()}\n" for rel in sorted(MASTERS)).encode()).hexdigest()
    assert kj["sources"]["masters"] == expected                                          # one sha256 over the sorted pairs `<project path>\0<sha256>\n`, as the other sources are made
    assert kj["fonts"] == {"copied": [], "not_copied": []} and kj["version"] == "1.1"
    skill = (kit_of(pack) / "SKILL.md").read_text(encoding="utf-8")
    assert all(f"- `{rel}`" in skill for rel in MASTERS_KIT)
    rep = report(pack, "kit")
    assert rep["status"] == "pass" and sorted(rep["outputs"]) == sorted([*KIT_FILES, *MASTERS_KIT])
    assert set(MASTERS) <= {i["path"] for i in rep["inputs"]}                            # a changed master makes the `kit` report stale
    assert masters_row(pack)["status"] == "pass"
    assert masters_row(pack)["detail"] == "5 master files copied byte for byte from assets/masters/ to brand/assets/masters/"
    assert written_row(pack)["detail"] == "20 generated files: 20 written, 0 unchanged, 0 moved to removed-2026-10-17/; version 1.1"
    first = kit_state(pack)
    assert build(pack).returncode == 0 and kit_state(pack) == first and kit_json(pack)["version"] == "1.1"       # a second build writes nothing
    mutate(pack / "assets/masters/ad/index.html", "<body>", "<body class=\"changed\">")                       # a deliberate break: one master changes, and its copy, its hash and the version follow
    assert build(pack).returncode == 0
    changed = (pack / "assets/masters/ad/index.html").read_bytes()
    assert (kit_of(pack) / "brand/assets/masters/ad/index.html").read_bytes() == changed and b'class="changed"' in changed
    assert kit_json(pack)["generated"]["brand/assets/masters/ad/index.html"] == hashlib.sha256(changed).hexdigest() and kit_json(pack)["version"] == "1.2"


def test_the_links_in_a_master_html_must_resolve_inside_the_kit(pack):
    with_masters(pack)
    filled_kit(pack)
    r = kit_check(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert statuses(pack) == ALL_PASS                                                    # ad.css, ad.png and ../../logo/mark.svg are all in the kit
    assert check_report_rows(pack)["kit:links"]["detail"] == f"{FRESH_LINKS + 4} relative links in {FRESH_FILES + 2} .md, .html and .css files resolve inside the kit"
    mutate(pack / "assets/masters/ad/index.html", 'src="ad.png"', 'src="missing.png"')   # a master that links to a file the kit does not hold
    mutate(pack / "assets/masters/ad/ad.css", 'url("ad.png")', 'url("../../../../../outside.png")')
    assert build(pack).returncode == 0                                                   # the build copies the masters as they are; `kit check` judges the links
    r = kit_check(pack)
    assert r.returncode == 1, r.stdout + r.stderr
    detail = check_report_rows(pack)["kit:links"]["detail"]
    assert check_report_rows(pack)["kit:links"]["status"] == "fail"
    assert "brand/assets/masters/ad/index.html:3 -> missing.png (no such file in the kit)" in detail
    assert f"brand/assets/masters/ad/ad.css:1 -> ../../../../../outside.png ({OUTSIDE_KIT})" in detail


def test_changing_adding_or_taking_away_a_master_makes_the_kit_stale(pack):
    with_masters(pack)
    filled_kit(pack)
    assert kit_check(pack).returncode == 0 and "kit:state" not in check_rows(pack)
    mutate(pack / "assets/masters/ad/ad.css", ".ad {", ".ad { color: red;")             # a master changed after the build
    r = kit_check(pack)
    assert r.returncode == 3, r.stdout + r.stderr                                        # not verified, never a pass
    assert statuses(pack) == {**ALL_PASS, "kit:sources": "skipped"}
    assert check_report_rows(pack)["kit:sources"]["detail"] == "not verified: the brand changed after the kit was built (masters); run `brand-creator kit build --yes`"
    state = check_rows(pack)["kit:state"]                                                # and check's own row says so too
    assert state["status"] == "skipped" and state["detail"].startswith("not verified: ") and "masters" in state["detail"]
    assert build(pack).returncode == 0
    assert kit_json(pack)["version"] == "1.3" and (kit_of(pack) / "brand/assets/masters/ad/ad.css").read_text(encoding="utf-8") == MASTER_CSS.replace(".ad {", ".ad { color: red;")
    assert kit_check(pack).returncode == 0 and statuses(pack) == ALL_PASS and "kit:state" not in check_rows(pack)
    with (pack / "assets/masters/ad/ad.png").open("ab") as fh:                           # a picture too: the bytes, not the text, are what is recorded
        fh.write(b"\x01")
    assert kit_check(pack).returncode == 3
    assert build(pack).returncode == 0 and kit_json(pack)["version"] == "1.4" and (kit_of(pack) / "brand/assets/masters/ad/ad.png").read_bytes() == MASTER_PNG + b"\x01"
    (pack / "assets/masters/deck/notes.pdf").write_bytes(MASTER_PDF + b"more")          # a master added
    assert kit_check(pack).returncode == 3 and check_report_rows(pack)["kit:sources"]["detail"].endswith("(masters); run `brand-creator kit build --yes`")
    assert build(pack).returncode == 0 and kit_json(pack)["version"] == "1.5" and (kit_of(pack) / "brand/assets/masters/deck/notes.pdf").is_file()
    (pack / "assets/masters/deck/deck.pptx").unlink()                                    # a master taken away: its copy is moved aside, as a logo taken away is
    assert kit_check(pack).returncode == 3
    assert build(pack).returncode == 0 and kit_json(pack)["version"] == "1.6"
    assert not (kit_of(pack) / "brand/assets/masters/deck/deck.pptx").exists()
    assert (pack / "removed-2026-10-17/.claude/skills/acme-brand/brand/assets/masters/deck/deck.pptx").read_bytes() == MASTER_PPTX
    assert "brand/assets/masters/deck/deck.pptx" not in kit_json(pack)["generated"] and kit_check(pack).returncode == 0
    shutil.rmtree(pack / "assets/masters")                                               # the whole folder gone: the key goes with it
    assert build(pack).returncode == 0 and "masters" not in kit_json(pack)["sources"] and kit_json(pack)["version"] == "1.7"
    assert kit_files(pack) == KIT_FILES and kit_check(pack).returncode == 0


def test_a_font_in_the_masters_follows_the_font_rule(pack):
    with_masters(pack)
    put_licence_text(pack)
    bring_font(pack, MASTER_FONT)
    listed_font = f"{MASTER_FONT} sits in the masters folder"
    # no fontcheck report: the font is listed with a reason that says to check the fonts, and is not copied; the rest of the masters are
    r = build(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert kit_json(pack)["fonts"] == {"copied": [], "not_copied": [{"file": MASTER_FONT, "reason": f"no current fontcheck report: {CHECK_THEM}"}]}
    assert kit_files(pack) == sorted([*KIT_FILES, *MASTERS_KIT]) and not (kit_of(pack) / "brand" / MASTER_FONT).exists()
    row = masters_row(pack)
    assert row["status"] == "warn" and listed_font in row["detail"] and "5 master files copied" in row["detail"], row
    assert {MASTER_FONT, "assets/fonts/OFL.txt"} <= {i["path"] for i in report(pack, "kit")["inputs"]}       # the report of fontcheck is an input as soon as there is one
    # a current report that has read another font only: this one is a font fontcheck has not read
    with_font(pack)
    assert build(pack).returncode == 0
    assert kit_json(pack)["fonts"]["not_copied"] == [{"file": MASTER_FONT, "reason": f"fontcheck has not read it: {CHECK_THEM}"}]
    # fontcheck reads both and the licence is OFL with its text in assets/fonts/: copied at its project path, with the licence text
    read_fonts(pack, "assets/fonts/TestFont-subset.ttf", MASTER_FONT)
    r = build(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "assets/_checks/fontcheck.json" in {i["path"] for i in report(pack, "kit")["inputs"]}
    assert kit_json(pack)["fonts"] == {"copied": [copied_font("brand/assets/fonts/TestFont-subset.ttf"), copied_font(f"brand/{MASTER_FONT}")], "not_copied": []}
    assert kit_files(pack) == sorted([*KIT_FILES, *FONT_KIT, *MASTERS_KIT, f"brand/{MASTER_FONT}"])
    assert filecmp.cmp(TEST_FONT, kit_of(pack) / "brand" / MASTER_FONT, shallow=False)
    assert (kit_of(pack) / "snippets" / "fonts.css").read_text(encoding="utf-8") == FONT_FACE      # fonts.css holds the fonts of assets/fonts/ only
    assert masters_row(pack)["status"] == "pass" and masters_row(pack)["detail"] == "6 master files copied byte for byte from assets/masters/ to brand/assets/masters/"
    # not OFL by the report: listed with the reason, not copied, and the kit does not keep the copy of the last build
    mutate_json(pack / "assets" / "_checks" / "fontcheck.json",
                lambda d: next(x for x in d["results"] if x["id"] == f"licence:{MASTER_FONT}").__setitem__("recognised", "Apache License"))
    assert build(pack).returncode == 0
    assert kit_json(pack)["fonts"]["not_copied"] == [{"file": MASTER_FONT, "reason": NOT_OFL}] and not (kit_of(pack) / "brand" / MASTER_FONT).exists()
    assert (pack / MASTER_FONT).is_file()                                                # the project's own font is as it was
    assert masters_row(pack)["status"] == "warn" and f"{listed_font} ({NOT_OFL})" in masters_row(pack)["detail"]
    # OFL by its name table but the licence text is gone from assets/fonts/
    read_fonts(pack, "assets/fonts/TestFont-subset.ttf", MASTER_FONT)
    ofl = pack / "assets" / "fonts" / "OFL.txt"
    mutate(ofl, "SIL Open Font License", "Some Licence", count=99)
    mutate(ofl, "SIL OPEN FONT LICENSE", "SOME LICENCE", count=99)
    assert build(pack).returncode == 0
    assert kit_json(pack)["fonts"]["not_copied"] == [{"file": "assets/fonts/TestFont-subset.ttf", "reason": "OFL by its name table, but no OFL licence text in assets/fonts/: add the font's OFL.txt"},
                                                     {"file": MASTER_FONT, "reason": "OFL by its name table, but no OFL licence text in assets/fonts/: add the font's OFL.txt"}]


def unread_why(ext):
    """The reason kit.json gives for a font file of a format fontcheck cannot read, written out by hand."""
    return (f"a font format fontcheck cannot read ({ext}): only .ttf, .otf, .woff and .woff2 fonts are read, so its licence is unknown and it is not copied; "
            "copy it into a product yourself, under its own licence")


def test_a_font_format_fontcheck_cannot_read_is_never_copied_from_the_masters(pack):
    """A collection (.ttc), an embedded-OpenType (.eot) and the other formats fontcheck cannot read have no licence the font rule could read, so they are held back and listed, like a font the rule refuses."""
    with_masters(pack)
    put_licence_text(pack)
    bring_font(pack, MASTER_FONT)
    collection, embedded = "assets/masters/fonts/Commercial.ttc", "assets/masters/fonts/Commercial.eot"
    (pack / collection).write_bytes(b"ttcf\x00\x01\x00\x00commercial collection")
    (pack / embedded).write_bytes(b"\x00\x00\x00\x00embedded commercial")
    r = build(pack)                                                                      # no fontcheck report: the OFL font is held back too
    assert r.returncode == 0, r.stdout + r.stderr
    assert kit_json(pack)["fonts"] == {"copied": [], "not_copied": [{"file": embedded, "reason": unread_why(".eot")}, {"file": collection, "reason": unread_why(".ttc")},
                                                                   {"file": MASTER_FONT, "reason": f"no current fontcheck report: {CHECK_THEM}"}]}
    assert kit_files(pack) == sorted([*KIT_FILES, *MASTERS_KIT])                         # neither is in the kit, and none is listed as generated
    assert not any("Commercial" in rel for rel in kit_json(pack)["generated"]) and (pack / collection).is_file() and (pack / embedded).is_file()
    row = masters_row(pack)
    assert row["status"] == "warn" and "5 master files copied" in row["detail"], row
    assert f"{collection} sits in the masters folder ({unread_why('.ttc')})" in row["detail"] and f"{embedded} sits in the masters folder ({unread_why('.eot')})" in row["detail"]
    assert {collection, embedded} <= {i["path"] for i in report(pack, "kit")["inputs"]}
    mutate(pack / collection, "commercial", "changed")                                   # a deliberate break: one of them changes, which makes the kit stale as any master does
    kit_check(pack)
    assert check_report_rows(pack)["kit:sources"]["status"] == "skipped" and check_report_rows(pack)["kit:sources"]["detail"].endswith("(masters); run `brand-creator kit build --yes`")
    recorded = kit_json(pack)["sources"]["masters"]
    assert build(pack).returncode == 0 and not (kit_of(pack) / "brand" / collection).exists()
    assert kit_json(pack)["sources"]["masters"] != recorded and kit_json(pack)["version"] == "1.1"      # the sources are recorded again; nothing in the kit changed, so the version stays
    # fontcheck reads the OFL font and it is copied; a format it cannot read stays held back, whatever the report says of the others
    read_fonts(pack, MASTER_FONT)
    assert build(pack).returncode == 0
    assert kit_json(pack)["fonts"] == {"copied": [copied_font(f"brand/{MASTER_FONT}")],
                                       "not_copied": [{"file": embedded, "reason": unread_why(".eot")}, {"file": collection, "reason": unread_why(".ttc")}]}
    assert kit_files(pack) == sorted([*KIT_FILES, *MASTERS_KIT, f"brand/{MASTER_FONT}", "brand/assets/fonts/OFL.txt"])      # the font with the licence text it travels with
    assert masters_row(pack)["status"] == "warn" and "6 master files copied" in masters_row(pack)["detail"]
    # the other formats, in any letter case, in any folder of the masters
    more = {"assets/masters/deck/Face.otc": ".otc", "assets/masters/deck/Mac.dfont": ".dfont", "assets/masters/deck/Print.PFB": ".pfb", "assets/masters/deck/Print.pfm": ".pfm",
            "assets/masters/deck/Print.pfa": ".pfa", "assets/masters/deck/Loud.TTC": ".ttc"}
    for rel in more:
        (pack / rel).write_bytes(b"not a font fontcheck reads")
    assert build(pack).returncode == 0
    listed_files = [f["file"] for f in kit_json(pack)["fonts"]["not_copied"]]
    assert listed_files == sorted([embedded, collection, *more]) and {f["reason"] for f in kit_json(pack)["fonts"]["not_copied"]} == {unread_why(e) for e in (".eot", ".ttc", *more.values())}
    assert kit_files(pack) == sorted([*KIT_FILES, *MASTERS_KIT, f"brand/{MASTER_FONT}", "brand/assets/fonts/OFL.txt"]) and masters_row(pack)["status"] == "warn"
    # a font file only: the folder is still masters, the row says none is copied
    shutil.rmtree(pack / "assets" / "masters")
    (pack / collection).parent.mkdir(parents=True)
    (pack / collection).write_bytes(b"ttcf\x00\x01\x00\x00commercial collection")
    assert build(pack).returncode == 0
    assert kit_json(pack)["fonts"] == {"copied": [], "not_copied": [{"file": collection, "reason": unread_why(".ttc")}]} and kit_files(pack) == KIT_FILES
    assert masters_row(pack)["status"] == "warn" and masters_row(pack)["detail"].startswith("0 master files copied byte for byte")


def test_a_link_to_a_master_font_the_kit_does_not_copy_is_a_warning_in_kit_check(pack):
    put_licence_text(pack)
    bring_font(pack, MASTER_FONT)
    with_masters(pack, {**MASTERS, "assets/masters/ad/ad.css": b'@font-face { font-family: "Master"; src: url("../fonts/Master.ttf") format("truetype"); }\n'})
    filled_kit(pack)                                                                     # no fontcheck report: the font is listed, not copied
    assert kit_json(pack)["fonts"]["not_copied"][0]["file"] == MASTER_FONT
    r = kit_check(pack)
    assert r.returncode == 0, r.stdout + r.stderr                                        # a warning, not a failure, and no silent pass
    links = check_report_rows(pack)["kit:links"]
    assert links["status"] == "warn" and f"brand/assets/masters/ad/ad.css:1 -> ../fonts/Master.ttf (brand/{MASTER_FONT}: no current fontcheck report: " in links["detail"], links
    assert "the font must be supplied under its own licence" in links["detail"]
    assert statuses(pack) == {**ALL_PASS, "kit:links": "warn"}
    read_fonts(pack, MASTER_FONT)                                                        # fontcheck reads it: copied, and the link resolves
    assert build(pack).returncode == 0 and (kit_of(pack) / "brand" / MASTER_FONT).is_file()
    assert kit_check(pack).returncode == 0 and statuses(pack) == ALL_PASS


def test_a_link_to_a_master_font_of_a_format_fontcheck_cannot_read_is_a_warning_in_kit_check(pack):
    embedded = "assets/masters/fonts/Commercial.eot"
    with_masters(pack, {**MASTERS, "assets/masters/ad/ad.css": b'@font-face { font-family: "Commercial"; src: url("../fonts/Commercial.eot"); }\n', embedded: b"embedded commercial"})
    filled_kit(pack)
    assert kit_json(pack)["fonts"]["not_copied"] == [{"file": embedded, "reason": unread_why(".eot")}] and not (kit_of(pack) / "brand" / embedded).exists()
    r = kit_check(pack)
    assert r.returncode == 0, r.stdout + r.stderr                                        # a warning, not a failure, and no silent pass
    links = check_report_rows(pack)["kit:links"]
    assert links["status"] == "warn" and f"brand/assets/masters/ad/ad.css:1 -> ../fonts/Commercial.eot (brand/{embedded}: a font format fontcheck cannot read (.eot)" in links["detail"], links
    assert "the font must be supplied under its own licence" in links["detail"] and statuses(pack) == {**ALL_PASS, "kit:links": "warn"}


def test_a_project_without_the_masters_folder_builds_the_same_bytes_as_before(pack):
    """The eval kit snapshot (evals/_shared/acme-kit/) is the kit of this very Acme project, built before masters existed: a project without assets/masters/ must still build every generated file,
    every source and kit.json's keys exactly as it holds them, with no `masters` key and no `kit:masters` row. A folder that holds no file is no masters either."""
    filled_kit(pack)
    plain = (kit_of(pack) / "kit.json").read_bytes()
    snapshot = json.loads((EVAL_KIT / "kit.json").read_text(encoding="utf-8"))
    got = kit_json(pack)
    assert list(got) == ["schema", "kit", "version", "edition", "plugin_version", "content_sha", "generated", "owned", "fonts", "sources", "reference_pages"]
    assert list(got["sources"]) == ["state_sha", "tokens", "tokens_css", "rules", "facts", "motion", "logos", "fonts", "pages"]
    assert got["generated"] == snapshot["generated"] and got["sources"] == snapshot["sources"] and got["fonts"] == snapshot["fonts"] and got["version"] == snapshot["version"] == "1.2"
    assert not any(r["id"] == "kit:masters" for r in report(pack, "kit")["results"])
    rep_before = report(pack, "kit")
    (pack / "assets" / "masters" / "ad").mkdir(parents=True)                             # a folder with no file in it, and a Finder file
    (pack / "assets" / "masters" / ".DS_Store").write_bytes(b"Finder")
    (pack / "assets" / "masters" / "ad" / ".DS_Store").write_bytes(b"Finder")
    r = bc("kit", "build", "--plan", project=pack)
    assert r.returncode == 0 and r.stdout.splitlines()[0] == "would write 15 generated files into .claude/skills/acme-brand/ (version 1.2)", r.stdout
    assert build(pack).returncode == 0
    assert (kit_of(pack) / "kit.json").read_bytes() == plain and kit_json(pack)["version"] == "1.2"
    assert not any(r["id"] == "kit:masters" for r in report(pack, "kit")["results"]) and report(pack, "kit")["kit_sources_sha"] == rep_before["kit_sources_sha"]
    assert kit_check(pack).returncode == 0 and statuses(pack) == ALL_PASS
    mutate(pack / "FACTS.md", "tools are made in batches of 200", "tools are made in batches of 300")      # the control: a changed fact does move kit.json, so the equality above would have caught a changed key
    assert build(pack).returncode == 0 and (kit_of(pack) / "kit.json").read_bytes() != plain and kit_json(pack)["sources"]["facts"] != snapshot["sources"]["facts"]


def test_a_link_in_the_masters_is_never_followed(pack, tmp_path):
    from helpers import symlink_or_skip
    with_masters(pack)
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"outside the project")
    symlink_or_skip(pack / "assets/masters/ad/leak.png", outside)                        # a file that leads out of the project
    for args in (("--yes",), ("--plan",)):
        r = bc("kit", "build", *args, project=pack)
        assert r.returncode == 2 and "outside the project" in r.stderr and "Traceback" not in r.stderr, (args, r.stdout + r.stderr)
    assert not (pack / ".claude").exists() and outside.read_bytes() == b"outside the project"
    (pack / "assets/masters/ad/leak.png").unlink()
    here = pack / "assets" / "masters" / "ad-again"
    symlink_or_skip(here, pack / "assets/masters/ad")                                    # a link to a folder, even one that stays inside the project, is not copied: the kit copies files
    r = build(pack)
    assert r.returncode == 1 and "assets/masters/ad-again is a link to a folder" in r.stderr and not (pack / ".claude").exists(), r.stdout + r.stderr
    here.unlink()
    real = pack / "assets" / "real-masters"
    shutil.move(str(pack / "assets" / "masters"), str(real))
    symlink_or_skip(pack / "assets" / "masters", real)                                   # the folder itself a link to a folder of the project: exit 1, the kit copies files
    r = build(pack)
    assert r.returncode == 1 and "assets/masters is a link" in r.stderr and not (pack / ".claude").exists(), r.stdout + r.stderr
    (pack / "assets" / "masters").unlink()
    shutil.move(str(real), str(pack / "assets" / "masters"))
    folder = tmp_path / "far-masters"
    shutil.move(str(pack / "assets" / "masters"), str(folder))
    symlink_or_skip(pack / "assets" / "masters", folder)                                 # the masters folder itself is a link leading out
    r = build(pack)
    assert r.returncode == 2 and "outside the project" in r.stderr and not (pack / ".claude").exists(), r.stdout + r.stderr
    (pack / "assets" / "masters").unlink()
    shutil.move(str(folder), str(pack / "assets" / "masters"))
    assert build(pack).returncode == 0 and kit_files(pack) == sorted([*KIT_FILES, *MASTERS_KIT])


def test_a_master_that_is_a_link_to_nothing_stops_the_build_in_the_words_of_a_master_not_a_page(pack):
    from pathlib import Path

    from helpers import symlink_or_skip
    with_masters(pack)
    symlink_or_skip(pack / "assets/masters/ad/gone.png", Path("nowhere.png"))            # a link to nothing, spelled relative to the folder it sits in
    for args in (("--yes",), ("--plan",)):
        r = bc("kit", "build", *args, project=pack)
        assert r.returncode == 1 and "Traceback" not in r.stderr, (args, r.stdout + r.stderr)
        assert ("master file assets/masters/ad/gone.png cannot be read (a link to nothing, a folder, or no plain file): "
                "a master is copied as it is, so put the real file back or take the link out of assets/masters/") in r.stderr, r.stderr
        assert "page" not in r.stderr and "approved" not in r.stderr, r.stderr            # the reference-page sentence ("the page was approved with it") is no word about a master
    assert not (pack / ".claude").exists()


def test_a_master_svg_with_live_text_fails_check_like_any_svg_under_assets(pack):
    """`check` lints every SVG under assets/ as pure vector (mark_lint), the masters folder included: the kit copies the file, and `check` fails the project for it. Pinned as it is today."""
    with_masters(pack, {**MASTERS, "assets/masters/ad/banner.svg": b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><text x="1" y="5">Sale</text></svg>\n'})
    assert build(pack).returncode == 0 and (kit_of(pack) / "brand/assets/masters/ad/banner.svg").is_file()
    row = check_rows(pack)["mark_lint:assets/masters/ad/banner.svg"]
    assert row["status"] == "fail" and "<text> element" in row["detail"], row


def test_a_file_where_the_masters_folder_belongs_stops_the_build(pack):
    (pack / "assets" / "masters").write_text("not a folder\n", encoding="utf-8")
    r = build(pack)
    assert r.returncode == 1 and "assets/masters is not a folder" in r.stderr and not (pack / ".claude").exists(), r.stdout + r.stderr


def test_a_master_that_a_reference_page_loads_is_one_file_in_the_kit(pack):
    """A page of site/ may load a file of assets/masters/: the kit holds one copy of it, at its project path, for the page and for the masters."""
    with_site(pack)
    with_masters(pack, {"assets/masters/ad/ad.png": MASTER_PNG})
    css = pack / "site" / "start" / "site.css"
    css.write_text(css.read_text(encoding="utf-8") + '.ad { background: url("../../assets/masters/ad/ad.png"); }\n', encoding="utf-8")
    settle_page(pack)
    r = build(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert (kit_of(pack) / "brand/assets/masters/ad/ad.png").read_bytes() == MASTER_PNG
    assert kit_files(pack).count("brand/assets/masters/ad/ad.png") == 1 and kit_json(pack)["version"] == "1.1"
    assert kit_json(pack)["sources"]["masters"] and kit_json(pack)["sources"]["pages"]


# ---------------------------------------------------------------- the owner's own files travel (K-02)
# Every file of the kit folder that is no generated file, no kit.json and no Finder `.DS_Store` is an owner file: hashed in kit.json `owned` at the next build (so the version moves when one is
# added, changed or taken away), checked by `kit:owned`, judged by `kit:fill`, `kit:tags` and `kit:numbers` when it is Markdown (voice.md and EXTENDING.md apart, as before), and on the copy list of
# `kit status`: copied into a repository only where the repository has none. A file of another kind travels and is never judged. A link among them is refused like a kit.json that is a link.
EMAIL = "# Email\n\n1. Say who the mail is from.\n- Short subject lines. [example]\n"
EMAIL_KIT = "recipes/email.md"


def owner_listed(p) -> list[str]:
    return sorted(kit_json(p)["owned"])


def test_a_recipe_the_owner_adds_is_hashed_moves_the_version_is_on_the_copy_list_and_is_judged(pack, tmp_path):
    filled_kit(pack)
    repo = install(pack, tmp_path)                                                       # a product repository that holds the kit of version 1.2
    kd = kit_of(pack)
    email = kd / "recipes" / "email.md"
    email.write_text(EMAIL + "[[fill: the sign-off]]\n", encoding="utf-8")
    before = kit_json(pack)
    r = kit_check(pack)                                                                  # judged before the build records it: a fill marker in it fails kit:fill
    assert r.returncode == 1, r.stdout + r.stderr
    assert statuses(pack) == {**ALL_PASS, "kit:fill": "fail", "kit:owned": "warn"}
    assert check_report_rows(pack)["kit:fill"]["detail"].startswith("1 fill marker(s) left: recipes/email.md:5;")
    assert check_report_rows(pack)["kit:owned"]["detail"] == "recipes/email.md was added since the last build: `brand-creator kit build --yes` records it and moves the version on"
    mutate(email, "[[fill: the sign-off]]", "End with the name. [example]")
    r = build(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    kj = kit_json(pack)
    assert sorted(kj["owned"]) == sorted([*OWNER_FILES, EMAIL_KIT]) and kj["owned"][EMAIL_KIT] == file_sha(email)
    assert {k: v for k, v in kj["owned"].items() if k != EMAIL_KIT} == before["owned"]     # the five are as they were
    assert kj["version"] == "1.3" and kj["content_sha"] != before["content_sha"] and "Kit version 1.3 (kit.json)." in (kd / "SKILL.md").read_text(encoding="utf-8")
    assert email.read_text(encoding="utf-8") == EMAIL + "End with the name. [example]\n" and not list(pack.glob("removed-*"))     # never overwritten, never moved
    assert owned_row(pack) == "0 owner files scaffolded this run, 6 kept as they are"
    assert EMAIL_KIT not in kj["generated"] and EMAIL_KIT not in report(pack, "kit")["outputs"]
    assert build(pack).returncode == 0 and kit_json(pack)["version"] == "1.3"             # recorded: the same content keeps the version
    assert kit_check(pack).returncode == 0 and statuses(pack) == ALL_PASS
    assert check_report_rows(pack)["kit:owned"]["detail"] == "the 6 owner files are as the last build recorded them"
    # the copy list: the generated files that changed (SKILL.md carries the version, kit.json last), then the owner file the repository lacks
    r = kit_status(pack, repo)
    assert r.returncode == 1, r.stdout + r.stderr
    items = listed(r.stdout, "copy list")
    assert paths_of(items) == ["SKILL.md", "kit.json", EMAIL_KIT] and items[-1] == f"{EMAIL_KIT} (owner file, the repository has none)"
    res = json.loads(kit_status(pack, repo, extra=("--json",)).stdout)["repos"][0]
    assert res["copy"] == ["SKILL.md", "kit.json", EMAIL_KIT] and res["copy_owner"] == [EMAIL_KIT]
    for rel in ("SKILL.md", "kit.json", EMAIL_KIT):                                       # the copy the list asks for
        (installed_of(repo) / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(kd / rel, installed_of(repo) / rel)
    r = kit_status(pack, repo)
    assert r.returncode == 0 and "site: current (version 1.3)" in r.stdout.splitlines() and "copy list" not in r.stdout
    # D11, unchanged for the file the owner added: where the repository has its own, it is reported and not copied, and the copy is current all the same
    (installed_of(repo) / EMAIL_KIT).write_text("The repository's own email recipe.\n", encoding="utf-8")
    r = kit_status(pack, repo)
    assert r.returncode == 0 and listed(r.stdout, "owner files that differ (kept on update)") == [EMAIL_KIT] and "copy list" not in r.stdout
    assert (installed_of(repo) / EMAIL_KIT).read_text(encoding="utf-8") == "The repository's own email recipe.\n"
    (installed_of(repo) / EMAIL_KIT).unlink()                                             # and where it has none, it is on the list again
    r = kit_status(pack, repo)
    assert r.returncode == 0 and paths_of(listed(r.stdout, "copy list")) == [EMAIL_KIT]


def test_a_page_the_owner_adds_is_never_judged_for_words_but_its_dead_link_fails_kit_links(pack):
    """EXTENDING.md, the changelog and the manual say it so: a file of another kind is not read for fill markers, tags or values, but the links in its .html or .css must lead to a file inside the kit."""
    filled_kit(pack)
    kd = kit_of(pack)
    (kd / "notes").mkdir()
    (kd / "notes" / "page.html").write_text('<a href="missing.html">gone</a> [[fill: x]] 16px\n', encoding="utf-8")
    (kd / "notes" / "style.css").write_text('.a { background: url("gone.png"); }\n', encoding="utf-8")
    assert build(pack).returncode == 0                                                   # the build only records them
    r = kit_check(pack)
    assert r.returncode == 1, r.stdout + r.stderr
    rows = statuses(pack)
    assert rows["kit:links"] == "fail" and {i: s for i, s in rows.items() if i != "kit:links"} == {i: s for i, s in ALL_PASS.items() if i != "kit:links"}    # the words (a marker, a size) are judged by no row
    detail = check_report_rows(pack)["kit:links"]["detail"]
    assert "notes/page.html:1 -> missing.html (no such file in the kit)" in detail and "notes/style.css:1 -> gone.png (no such file in the kit)" in detail, detail


def test_a_file_the_owner_adds_that_is_not_markdown_travels_and_is_never_judged(pack, tmp_path):
    filled_kit(pack)
    kd = kit_of(pack)
    (kd / "notes").mkdir()
    (kd / "notes" / "palette.txt").write_text("[[fill: the swatches]] 16px #ffffff\n", encoding="utf-8")                  # a fill marker, a size and a colour: none is judged
    (kd / "notes" / "page.html").write_text('<a href="../brand/assets/logo/mark.svg">mark</a> [[fill: x]] 16px\n', encoding="utf-8")   # a marker and a size: not judged; its link is, as in any .html of the kit
    (kd / "notes" / "brief.pdf").write_bytes(b"%PDF-1.4\n\x00\x01 binary \xff")
    before = kit_json(pack)
    build_r = build(pack)
    assert build_r.returncode == 0, build_r.stdout + build_r.stderr
    kj = kit_json(pack)
    wanted = ["notes/brief.pdf", "notes/page.html", "notes/palette.txt"]
    assert sorted(kj["owned"]) == sorted([*OWNER_FILES, *wanted]) and all(kj["owned"][r] == file_sha(kd / r) for r in wanted)
    assert kj["version"] == "1.3" and kj["generated"].keys() == before["generated"].keys()
    r = kit_check(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert statuses(pack) == ALL_PASS                                                    # kit:fill, kit:tags and kit:numbers read none of the three
    assert check_report_rows(pack)["kit:links"]["detail"] == f"{FRESH_LINKS + 1} relative links in {FRESH_FILES + 1} .md, .html and .css files resolve inside the kit"      # the .html is read for its links, as any in the kit
    assert check_report_rows(pack)["kit:tags"]["detail"] == "no bullet or numbered line needs a tag" and check_report_rows(pack)["kit:numbers"]["detail"] == NO_VALUES
    assert check_report_rows(pack)["kit:fill"]["detail"] == "no [[fill marker is left"
    # the three travel: a repository with no copy is told to copy the five, then the files of the owner, sorted
    repo = tmp_path / "site"
    repo.mkdir()
    r = kit_status(pack, repo)
    assert paths_of(listed(r.stdout, "copy list")) == COPY_ORDER + OWNER_ORDER + wanted
    assert all(i.endswith("(owner file, the repository has none)") for i in listed(r.stdout, "copy list")[len(COPY_ORDER):])
    # a changed one is a changed owner file: kit:owned warns, the next build records it and moves the version
    mutate(kd / "notes" / "palette.txt", "16px", "17px")
    assert kit_check(pack).returncode == 0 and check_report_rows(pack)["kit:owned"]["detail"].startswith("notes/palette.txt changed since the last build")
    assert build(pack).returncode == 0 and kit_json(pack)["version"] == "1.4" and kit_json(pack)["owned"]["notes/palette.txt"] == file_sha(kd / "notes" / "palette.txt")
    with (kd / "notes" / "brief.pdf").open("ab") as fh:
        fh.write(b"\x02")
    assert build(pack).returncode == 0 and kit_json(pack)["version"] == "1.5" and kit_json(pack)["owned"]["notes/brief.pdf"] == file_sha(kd / "notes" / "brief.pdf")
    # taken away: kit:owned says so, and the next build moves the version and forgets it
    (kd / "notes" / "brief.pdf").unlink()
    assert kit_check(pack).returncode == 0
    assert check_report_rows(pack)["kit:owned"]["detail"] == "notes/brief.pdf was removed since the last build: `brand-creator kit build --yes` records it and moves the version on"
    assert build(pack).returncode == 0
    assert kit_json(pack)["version"] == "1.6" and "notes/brief.pdf" not in kit_json(pack)["owned"] and sorted(kit_json(pack)["owned"]) == sorted([*OWNER_FILES, *wanted[1:]])
    assert not list(pack.glob("removed-*")) and kit_check(pack).returncode == 0 and statuses(pack) == ALL_PASS


def test_a_markdown_file_the_owner_adds_is_judged_like_the_recipes(pack):
    """notes/ideas.md is the owner's own Markdown file: kit:fill, kit:tags and kit:numbers read it, a bullet needs a tag and a value a citation. voice.md and EXTENDING.md are not judged for tags and values."""
    filled_kit(pack)
    kd = kit_of(pack)
    (kd / "notes").mkdir()
    (kd / "notes" / "ideas.md").write_text("# Ideas\n\n- A bullet with no tag.\n- Use 12px. [example]\n- Use 20px.\n1. A numbered step needs none.\n[[fill: more]]\n", encoding="utf-8")
    assert build(pack).returncode == 0
    r = kit_check(pack)
    assert r.returncode == 1, r.stdout + r.stderr
    assert check_report_rows(pack)["kit:fill"]["detail"].startswith("1 fill marker(s) left: notes/ideas.md:7;")
    assert check_report_rows(pack)["kit:tags"]["detail"] == lack_a_tag(2, 3, "notes/ideas.md:3 untagged", "notes/ideas.md:5 untagged")
    assert check_report_rows(pack)["kit:numbers"]["detail"] == cites_nothing("notes/ideas.md:5 (20px has no citation)")
    (kd / "notes" / "ideas.md").write_text("# Ideas\n\n- A bullet. [example]\n- Use 12px. [example]\n- Use 20px. [rule: " + CLEAR_SPACE + "]\n1. A numbered step needs none.\n", encoding="utf-8")
    assert build(pack).returncode == 0
    record_rules(pack, "The mark keeps its clear space")
    assert build(pack).returncode == 0
    r = kit_check(pack)
    assert r.returncode == 0, r.stdout + r.stderr
    assert statuses(pack) == ALL_PASS


def test_a_file_in_a_generated_folder_is_still_foreign_and_never_an_owner_file(pack):
    assert build(pack).returncode == 0
    kd = kit_of(pack)
    (kd / "recipes" / "email.md").write_text(EMAIL, encoding="utf-8")
    foreign = ["brand/notes.md", "snippets/mine.css", "reference-pages/start/mine.md"]
    for rel in foreign:
        (kd / rel).parent.mkdir(parents=True, exist_ok=True)
        (kd / rel).write_text("mine\n", encoding="utf-8")
    mutate(kd / "snippets" / "logo.html", "<img", "<img data-x=\"1\"")                    # a hand edit of a generated file stops the build as well
    kit_before = (kd / "kit.json").read_bytes()
    r = build(pack)
    assert r.returncode == 1, r.stdout + r.stderr
    assert "snippets/logo.html (edited by hand)" in r.stderr
    assert all(f"{rel} (not written by the kit)" in r.stderr for rel in foreign) and (kd / "kit.json").read_bytes() == kit_before and not list(pack.glob("removed-*"))
    r = build(pack, "--replace")                                                         # --replace moves them aside, as it always did; they were never the owner's
    assert r.returncode == 0, r.stdout + r.stderr
    assert all(not (kd / rel).exists() and (pack / "removed-2026-10-17" / ".claude/skills/acme-brand" / rel).read_text(encoding="utf-8") == "mine\n" for rel in foreign)
    assert owner_listed(pack) == sorted([*OWNER_FILES, EMAIL_KIT]) and kit_json(pack)["version"] == "1.2"
    assert (pack / "removed-2026-10-17" / ".claude/skills/acme-brand/snippets/logo.html").read_text(encoding="utf-8").count('data-x="1"') >= 1 and b'data-x' not in (kd / "snippets" / "logo.html").read_bytes()


def test_a_link_among_the_owners_files_is_refused_the_way_a_kit_json_link_is(pack, tmp_path):
    from helpers import symlink_or_skip
    filled_kit(pack)
    kd = kit_of(pack)
    target = pack / "elsewhere.md"                                                       # a file of the project, outside the kit, and a folder of it
    target.write_text("Kept in the project. [[fill: never read]]\n", encoding="utf-8")
    folder = pack / "elsewhere"
    folder.mkdir()
    (folder / "page.md").write_text("- untagged and never read\n", encoding="utf-8")
    symlink_or_skip(kd / "recipes" / "email.md", target)
    symlink_or_skip(kd / "notes", folder)
    kit_before = (kd / "kit.json").read_bytes()
    r = build(pack)
    assert r.returncode == 1 and "notes (a link among your own files: never read through)" in r.stderr and f"{EMAIL_KIT} (a link among your own files: never read through)" in r.stderr, r.stdout + r.stderr
    assert bc("kit", "build", "--plan", project=pack).returncode == 0                      # the plan only says what would be written
    assert (kd / "kit.json").read_bytes() == kit_before and (kd / "recipes" / "email.md").is_symlink() and not list(pack.glob("removed-*"))
    r = kit_check(pack)                                                                  # kit check never reads through it: the files it leads to are not judged, and kit:owned says what it is
    assert r.returncode == 0, r.stdout + r.stderr
    assert statuses(pack) == {**ALL_PASS, "kit:owned": "warn"}
    assert check_report_rows(pack)["kit:owned"]["detail"] == ("notes, recipes/email.md is no file the kit can read (a folder, or a link): "
                                                              "move it away yourself, then run `brand-creator kit build --yes`")
    repo = tmp_path / "site"
    repo.mkdir()
    r = kit_status(pack, repo)                                                           # kit status cannot list what it must not read: the kit is not whole
    assert r.returncode == 3 and "link" in r.stderr and "notes" in r.stderr and EMAIL_KIT in r.stderr, r.stdout + r.stderr
    r = build(pack, "--replace")                                                         # --replace moves the links themselves, never what they point at
    assert r.returncode == 0, r.stdout + r.stderr
    moved = pack / "removed-2026-10-17" / ".claude/skills/acme-brand"
    assert (moved / "notes").is_symlink() and (moved / EMAIL_KIT).is_symlink() and not (kd / "notes").exists() and not (kd / "recipes" / "email.md").exists()
    assert target.read_text(encoding="utf-8").startswith("Kept in the project.") and (folder / "page.md").is_file()
    assert owner_listed(pack) == OWNER_FILES and kit_json(pack)["version"] == "1.2"
    # one of the five as a link to a file of the project: refused too, and --replace puts the scaffold in its place
    voice = kd / "voice.md"
    mine = voice.read_bytes()
    voice.unlink()
    symlink_or_skip(voice, target)
    r = build(pack)
    assert r.returncode == 1 and "voice.md (a link among your own files: never read through)" in r.stderr, r.stdout + r.stderr
    r = build(pack, "--replace")
    assert r.returncode == 0, r.stdout + r.stderr
    assert voice.is_file() and not voice.is_symlink() and voice.read_text(encoding="utf-8").startswith("# Acme voice\n") and mine != voice.read_bytes()
    assert (moved / "voice.md").is_symlink() and target.is_file()                                           # the same removed-<date> folder: it holds no voice.md yet
    # the folder an owner file belongs in is a link to a folder: the same
    shutil.rmtree(kd / "recipes")
    symlink_or_skip(kd / "recipes", folder)
    r = build(pack)
    assert r.returncode == 1 and "recipes (a link among your own files: never read through)" in r.stderr and (folder / "page.md").is_file() and not (folder / "web-page.md").exists(), r.stdout + r.stderr


def test_a_link_among_the_owners_files_is_exit_1_and_replace_moves_it_whatever_it_points_at(pack, tmp_path):
    """The rule of a kit.json that is a link: a link to nothing and a link leading out of the project are refused like one to a file of the project (exit 1, never exit 2), and --replace moves the link
    itself aside in every case, for the five scaffolded files and the folder they belong in as well as for a file of the owner's own. Nothing a link leads to is read, moved or written."""
    from helpers import symlink_or_skip
    filled_kit(pack)
    kd = kit_of(pack)
    outside = tmp_path / "outside.txt"
    outside.write_text("outside the project\n", encoding="utf-8")
    far = tmp_path / "far"
    far.mkdir()
    (far / "x.md").write_text("- never read\n", encoding="utf-8")

    def moved(rel):                                                                       # where --replace put the link itself
        return next(d / ".claude/skills/acme-brand" / rel for d in sorted(pack.glob("removed-*")) if (d / ".claude/skills/acme-brand" / rel).is_symlink())

    def refused(*rels):
        r = build(pack)
        assert r.returncode == 1, r.stdout + r.stderr
        assert all(f"{rel} (a link among your own files: never read through)" in r.stderr for rel in rels) and "outside the project" not in r.stderr and "Traceback" not in r.stderr, r.stderr
        r = bc("kit", "build", "--plan", project=pack)
        assert r.returncode == 0 and "would write" in r.stdout, r.stdout + r.stderr          # the plan only says what would be written
        assert not list(pack.glob("removed-*")) and outside.read_text(encoding="utf-8") == "outside the project\n" and (far / "x.md").is_file()

    # files of the owner's own: to nothing, out of the project (a file and a folder), and --replace clears all three
    (kd / "notes").mkdir()
    symlink_or_skip(kd / "notes" / "out.txt", outside)
    symlink_or_skip(kd / "notes" / "far", far)
    (kd / "notes" / "gone.md").symlink_to("nowhere.md")                                   # a link to nothing, spelled relative to the folder it sits in
    before = (kd / "kit.json").read_bytes()
    refused("notes/gone.md", "notes/out.txt", "notes/far")
    assert (kd / "kit.json").read_bytes() == before
    r = kit_check(pack)                                                                   # kit check never reads through them, and says what they are
    assert r.returncode == 0, r.stdout + r.stderr
    assert check_report_rows(pack)["kit:owned"]["detail"] == ("notes/far, notes/gone.md, notes/out.txt is no file the kit can read (a folder, or a link): "
                                                              "move it away yourself, then run `brand-creator kit build --yes`")
    r = build(pack, "--replace")
    assert r.returncode == 0, r.stdout + r.stderr
    assert all(moved(f"notes/{n}").is_symlink() and not (kd / "notes" / n).exists() and not (kd / "notes" / n).is_symlink() for n in ("gone.md", "out.txt", "far"))
    assert os.readlink(moved("notes/gone.md")) == "nowhere.md" and moved("notes/out.txt").resolve() == outside.resolve() and moved("notes/far").resolve() == far.resolve()
    assert owner_listed(pack) == OWNER_FILES and kit_json(pack)["version"] == "1.2" and kit_check(pack).returncode == 0
    shutil.rmtree(pack / "removed-2026-10-17")
    # one of the five as a link to nothing, and as a link out of the project: the scaffold is written once the link is moved
    for rel, target in (("voice.md", "nowhere.md"), ("golden-rules.md", outside)):
        (kd / rel).unlink()
        if isinstance(target, str):
            (kd / rel).symlink_to(target)
        else:
            symlink_or_skip(kd / rel, target)
        refused(rel)
        r = build(pack, "--replace")
        assert r.returncode == 0, (rel, r.stdout + r.stderr)
        assert (kd / rel).is_file() and not (kd / rel).is_symlink() and (kd / rel).read_text(encoding="utf-8").startswith("# Acme ") and moved(rel).is_symlink(), rel
        shutil.rmtree(pack / "removed-2026-10-17")
        fill_owned(kd)                                                                    # the scaffold has its fill marker again
        assert build(pack).returncode == 0
    # the folder the five belong in: a link to nothing, and a link to a folder outside the project
    for target in ("nowhere", far):
        shutil.rmtree(kd / "recipes")
        if isinstance(target, str):
            (kd / "recipes").symlink_to(target)
        else:
            symlink_or_skip(kd / "recipes", target)
        refused("recipes")
        r = build(pack, "--replace")
        assert r.returncode == 0, r.stdout + r.stderr
        assert (kd / "recipes").is_dir() and not (kd / "recipes").is_symlink() and (kd / "recipes" / "web-page.md").is_file() and moved("recipes").is_symlink()
        assert not (far / "web-page.md").exists() and (far / "x.md").is_file()
        shutil.rmtree(pack / "removed-2026-10-17")
    assert kit_check(pack).returncode == 0
    assert owner_listed(pack) == OWNER_FILES


def test_kit_json_names_its_owner_files_as_plain_paths_of_the_owner_part_of_the_kit(pack):
    import kitlib
    from _common import CliError
    assert build(pack).returncode == 0
    f = kit_of(pack) / "kit.json"
    for where, change, needle in (("a file of the owner in a folder of her own", lambda d: d["owned"].__setitem__("notes/mine.txt", "0" * 64), None),
                                  ("a generated folder", lambda d: d["owned"].__setitem__("brand/assets/x.md", "0" * 64), "owned.brand/assets/x.md: not an owner file"),
                                  ("kit.json itself", lambda d: d["owned"].__setitem__("kit.json", "0" * 64), "owned.kit.json: not an owner file"),
                                  ("a generated file at the top", lambda d: d["owned"].__setitem__("rules.json", "0" * 64), "owned.rules.json: not an owner file"),
                                  ("a path that climbs out", lambda d: d["owned"].__setitem__("../x.md", "0" * 64), "owned.../x.md: not an owner file"),
                                  ("the folder above", lambda d: d["owned"].__setitem__("..", "0" * 64), "owned...: not an owner file"),
                                  ("an absolute path", lambda d: d["owned"].__setitem__("/etc/hosts", "0" * 64), "owned./etc/hosts: not an owner file"),
                                  ("a Finder file", lambda d: d["owned"].__setitem__("notes/.DS_Store", "0" * 64), "owned.notes/.DS_Store: not an owner file"),
                                  ("a hash that is none", lambda d: d["owned"].__setitem__("notes/mine.txt", "x"), "owned.notes/mine.txt: must be a sha256")):
        good = f.read_bytes()
        mutate_json(f, change)
        if needle is None:
            assert "notes/mine.txt" in kitlib.load(pack)["owned"], where
        else:
            with pytest.raises(CliError) as e:
                kitlib.load(pack)
            assert e.value.code == 2 and needle in e.value.message, where
        f.write_bytes(good)
