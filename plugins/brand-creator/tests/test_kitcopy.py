"""The copy judge (scripts/adaptlib/kitcopy.py): it compares a kit folder with a product repository's copy, standard library only, and the kit ships it as install.py.

Kits here are made by tests/helpers.make_fake_kit, with no brand project behind them; expected values are written out by hand."""
import ast
import json
import sys

import pytest
from helpers import ROOT, make_fake_kit

import _common
import kitcopy
import kitlib

GEN = {"SKILL.md": b"# Acme brand\n", "brand/assets/tokens/tokens.css": b":root{}\n", "snippets/logo.html": b"<img src=x>\n"}


def test_kitcopy_imports_only_the_standard_library():
    tree = ast.parse((ROOT / "scripts" / "adaptlib" / "kitcopy.py").read_text(encoding="utf-8"))
    mods = {a.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    mods |= {n.module.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module and n.level == 0}
    assert mods <= set(sys.stdlib_module_names) | {"__future__"}, mods - set(sys.stdlib_module_names)


def test_the_exit_codes_are_the_plugins():
    assert (kitcopy.EXIT_FAIL, kitcopy.EXIT_USAGE, kitcopy.EXIT_CANNOT) == (_common.EXIT_FAIL, _common.EXIT_USAGE, _common.EXIT_CANNOT)


def test_kitlib_keeps_the_names_it_had():
    for name in ("problems", "is_owner_path", "owner_sorted", "owner_paths", "paths_in", "recorded_path", "compare", "not_current_text", "folder_state",
                 "installed_version", "ROOT_FILES", "OWNED_FILES", "GENERATED_DIRS", "TOP_KEYS", "CURRENT", "NOT_CURRENT", "NOT_INSTALLED", "WHY_MISSING",
                 "WHY_BYTES", "STATUS_SHOWN", "_json_object", "_read_plain", "_plain_file", "_generated_files_in"):
        assert hasattr(kitlib, name), name


def test_a_fake_kit_is_whole_and_a_fresh_repository_gets_every_file(tmp_path):
    kit = tmp_path / "acme-brand"
    make_fake_kit(kit, GEN, {})
    res = kitcopy.compare(kit, tmp_path / "repo" / ".claude" / "skills" / "acme-brand")
    assert res["state"] == kitcopy.NOT_INSTALLED
    assert res["copy_owner"] == ["EXTENDING.md", "voice.md", "visual.md", "golden-rules.md", "recipes/web-page.md"]


def test_a_kit_that_is_not_whole_raises_kit_error_with_exit_3(tmp_path):
    kit = tmp_path / "acme-brand"
    make_fake_kit(kit, GEN, {})
    (kit / "snippets" / "logo.html").write_bytes(b"changed\n")
    with pytest.raises(kitcopy.KitError) as e:
        kitcopy.compare(kit, tmp_path / "repo")
    assert e.value.code == 3 and "not whole" in e.value.message and "snippets/logo.html (edited by hand)" in e.value.message


def test_kitlib_compare_turns_a_kit_error_into_the_plugins_failure(tmp_path):
    kit = tmp_path / "acme-brand"
    make_fake_kit(kit, GEN, {})
    (kit / "snippets" / "logo.html").write_bytes(b"changed\n")
    with pytest.raises(_common.CliError) as e:
        kitlib.compare(kit, tmp_path / "repo")
    assert e.value.code == 3 and "not whole" in e.value.message


def test_refusal_names_the_project_home_and_dot_claude(tmp_path):
    from pathlib import Path
    import os
    project = tmp_path / "brand"
    (project / "sub").mkdir(parents=True)
    home = Path(os.path.realpath(Path.home()))
    assert "brand project itself" in kitcopy.refusal(project, Path(os.path.realpath(project / "sub")))
    assert "home folder" in kitcopy.refusal(project, home)
    assert "inside ~/.claude" in kitcopy.refusal(project, home / ".claude" / "skills")
    assert kitcopy.refusal(project, Path(os.path.realpath(tmp_path)) / "shop") is None


def test_the_page_id_rule_is_sitedatas():
    import sitedata
    assert kitcopy.PAGE_ID.pattern == sitedata.SITE_PAGE_ID.pattern


# ---------------------------------------------------------------- owner files a repository never changed are updated (ADR-0014)

import hashlib  # noqa: E402
import shutil  # noqa: E402


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def installed(tmp_path, kit):
    """A repository's copy of `kit`, byte for byte, as `kit status`'s copy list makes it."""
    dest = tmp_path / "repo" / ".claude" / "skills" / kit.name
    shutil.copytree(kit, dest)
    return dest


def two_versions(tmp_path, v1_owner: dict, v2_owner: dict):
    """The project's kit at version 1.2 (owner files `v2_owner`) and a repository holding version 1.1 (owner files `v1_owner`)."""
    old = tmp_path / "old" / "acme-brand"
    make_fake_kit(old, GEN, v1_owner, version="1.1")
    repo = installed(tmp_path, old)
    kit = tmp_path / "acme-brand"
    make_fake_kit(kit, GEN, v2_owner, version="1.2")
    return kit, repo


def test_owner_state_table():
    p, r = b"new", b"old"
    assert kitcopy.owner_state(None, p, None) == "copy"
    assert kitcopy.owner_state(None, p, sha(r)) == "own"            # recorded as copied, and gone: the repository took it out, and it stays out (0.11.1)
    assert kitcopy.owner_state(p, p, sha(r)) == "same"
    assert kitcopy.owner_state(p, p, None) == "same"
    assert kitcopy.owner_state(r, p, sha(r)) == "update"
    assert kitcopy.owner_state(b"mine", p, sha(r)) == "own"
    assert kitcopy.owner_state(r, p, None) == "own"


def test_an_owner_file_the_repository_never_changed_is_updated(tmp_path):
    kit, repo = two_versions(tmp_path, {"recipes/ad.md": b"v1"}, {"recipes/ad.md": b"v2"})
    res = kitcopy.compare(kit, repo)
    assert res["update_owner"] == ["recipes/ad.md"] and res["owner_differ"] == [] and res["state"] == kitcopy.NOT_CURRENT
    assert res["copy"] == ["recipes/ad.md", "kit.json"]


def test_an_owner_file_the_repository_changed_is_kept_and_reported(tmp_path):
    kit, repo = two_versions(tmp_path, {"recipes/ad.md": b"v1"}, {"recipes/ad.md": b"v2"})
    (repo / "recipes" / "ad.md").write_bytes(b"mine")
    res = kitcopy.compare(kit, repo)
    assert res["update_owner"] == [] and res["owner_differ"] == [("recipes/ad.md", kitcopy.WHY_BYTES)] and "recipes/ad.md" not in res["copy"]


def test_an_owner_file_the_repository_added_is_its_own(tmp_path):
    kit, repo = two_versions(tmp_path, {}, {"recipes/ad.md": b"v2"})
    (repo / "recipes" / "ad.md").write_bytes(b"the repository's own")
    res = kitcopy.compare(kit, repo)
    assert res["update_owner"] == [] and res["owner_differ"] == [("recipes/ad.md", kitcopy.WHY_BYTES)]


def test_an_owner_file_gone_from_the_kit_and_unchanged_is_left_over(tmp_path):
    kit, repo = two_versions(tmp_path, {"recipes/old.md": b"old", "recipes/kept.md": b"kept"}, {})
    (repo / "recipes" / "kept.md").write_bytes(b"changed in the repository")
    res = kitcopy.compare(kit, repo)
    assert res["owner_left_over"] == ["recipes/old.md"] and res["state"] == kitcopy.NOT_CURRENT
    assert "recipes/old.md" not in res["copy"]


@pytest.mark.parametrize("damage", ["broken", "other schema", "link"])
def test_an_unreadable_installed_kit_json_makes_every_differing_owner_file_the_repositorys_own(tmp_path, damage):
    kit, repo = two_versions(tmp_path, {"recipes/ad.md": b"v1"}, {"recipes/ad.md": b"v2"})
    kj = repo / "kit.json"
    if damage == "broken":
        kj.write_text("{", encoding="utf-8")
    elif damage == "other schema":
        doc = json.loads(kj.read_text(encoding="utf-8"))
        kj.write_text(json.dumps({**doc, "schema": 2}), encoding="utf-8")
    else:
        target = tmp_path / "elsewhere.json"
        shutil.move(kj, target)
        kj.symlink_to(target)
    res = kitcopy.compare(kit, repo)
    assert res["update_owner"] == [] and ("recipes/ad.md", kitcopy.WHY_BYTES) in res["owner_differ"] and res["owner_left_over"] == []


def test_kit_json_is_the_last_file_of_every_copy_list(tmp_path):
    kit = tmp_path / "acme-brand"
    make_fake_kit(kit, GEN, {"recipes/ad.md": b"v2"})
    fresh = kitcopy.compare(kit, tmp_path / "fresh" / "acme-brand")
    assert fresh["copy"][-1] == "kit.json" and fresh["copy"].index("recipes/ad.md") < fresh["copy"].index("kit.json")
    kit2, repo = two_versions(tmp_path / "b", {"recipes/ad.md": b"v1", "voice.md": b"v1"}, {"recipes/ad.md": b"v2", "recipes/new.md": b"new"})
    (repo / "voice.md").unlink()                                       # taken out by the repository: its own change, not copied back
    res = kitcopy.compare(kit2, repo)
    assert res["copy"] == ["recipes/new.md", "recipes/ad.md", "kit.json"]
    assert res["copy_owner"] == ["recipes/new.md"] and res["update_owner"] == ["recipes/ad.md"] and ("voice.md", kitcopy.WHY_MISSING) in res["owner_differ"]


def test_a_copy_stopped_before_kit_json_is_finished_by_the_next_run(tmp_path):
    kit, repo = two_versions(tmp_path, {"recipes/ad.md": b"v1"}, {"recipes/ad.md": b"v2", "recipes/new.md": b"new"})
    res = kitcopy.compare(kit, repo)
    for rel in res["copy"][:-1]:                                           # the copy stops just before kit.json
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(kit / rel, repo / rel)
    again = kitcopy.compare(kit, repo)
    assert again["copy"] == ["kit.json"] and again["owner_differ"] == [] and again["update_owner"] == [] and again["state"] == kitcopy.NOT_CURRENT
    shutil.copyfile(kit / "kit.json", repo / "kit.json")
    assert kitcopy.compare(kit, repo)["state"] == kitcopy.CURRENT


# ---------------------------------------------------------------- a second skill for the same brand

import unicodedata  # noqa: E402


def skill(folder, name, description):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "SKILL.md").write_text(f"---\nname: {name}\ndescription: {description}\n---\n\n# x\n", encoding="utf-8")


def test_brand_name_is_read_from_the_kits_heading(tmp_path):
    kit = tmp_path / "lakowo-brand"
    make_fake_kit(kit, {"SKILL.md": "---\nname: lakowo-brand\n---\n\n# Łąkowo brand\n".encode()}, {})
    assert kitcopy.brand_name(kit) == "Łąkowo"
    assert kitcopy.brand_name(tmp_path / "nothing") is None


def test_a_hand_made_skill_naming_the_brand_is_found_even_written_decomposed(tmp_path):
    skills = tmp_path / ".claude" / "skills"
    skill(skills / "lakowo", "lakowo", unicodedata.normalize("NFD", "Applies the Łąkowo brand to anything made for it."))
    skill(skills / "lakowo-brand", "lakowo-brand", "Applies the Łąkowo brand (colours, type).")
    skill(skills / "other", "other", "Writes release notes.")
    assert kitcopy.other_brand_skills(skills, "lakowo-brand", "Łąkowo") == ["lakowo"]


def test_a_link_among_the_skills_and_a_folder_without_skill_md_are_never_read(tmp_path):
    skills = tmp_path / ".claude" / "skills"
    skill(tmp_path / "elsewhere", "lakowo", "Applies the Łąkowo brand.")
    skills.mkdir(parents=True)
    (skills / "linked").symlink_to(tmp_path / "elsewhere")
    (skills / "empty").mkdir()
    assert kitcopy.other_brand_skills(skills, "lakowo-brand", "Łąkowo") == []
    assert kitcopy.other_brand_skills(tmp_path / "no-skills-folder", "lakowo-brand", "Łąkowo") == []


def test_compare_lists_the_other_skill_and_the_status_warns_while_the_copy_stays_current(tmp_path):
    kit = tmp_path / "acme-brand"
    make_fake_kit(kit, GEN, {})
    repo = installed(tmp_path, kit)
    skill(repo.parent / "acme", "acme", "Applies the Acme brand.")
    res = kitcopy.compare(kit, repo)
    assert res["state"] == kitcopy.CURRENT and res["other_skills"] == ["acme"]
    lines = kitcopy.status_lines({**res, "label": "site", "note": None}, ".claude/skills/acme-brand")
    assert "  warning: .claude/skills/acme/ is another skill for Acme: Claude may load either; taking it out is yours" in lines


# ---------------------------------------------------------------- install.py never writes through a link

import subprocess  # noqa: E402

TODAY = "2026-10-17"


def git_repo(tmp_path, name="shop"):
    repo = tmp_path / name
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    return repo


def project_kit(tmp_path, owner=None):
    kit = tmp_path / "brand" / ".claude" / "skills" / "acme-brand"
    make_fake_kit(kit, GEN, owner or {"recipes/ad.md": b"ad"})
    return kit


def outside_untouched(folder) -> str:
    return kitcopy.folder_state(folder)


@pytest.mark.parametrize("where", [".claude", ".claude/skills", ".claude/skills/acme-brand/recipes", ".claude/skills/acme-brand/brand/assets"])
def test_install_refuses_a_link_on_the_way_and_writes_nothing_through_it(tmp_path, where):
    kit = project_kit(tmp_path)
    repo = git_repo(tmp_path)
    if where.startswith(".claude/skills/acme-brand/"):                                       # an installed kit, one of its folders swapped for a link
        assert kitcopy._install(kit, str(repo), True, False, TODAY) == 0
        shutil.rmtree(repo / where)
        make_fake_kit(kit, GEN, {"recipes/ad.md": b"ad", "recipes/email.md": b"email"}, version="1.2")   # a new recipe of the owner's, which the copy writes below recipes/
    outside = tmp_path / "outside"
    outside.mkdir()
    link = repo / where
    link.parent.mkdir(parents=True, exist_ok=True)
    link.symlink_to(outside, target_is_directory=True)
    before = outside_untouched(outside)
    with pytest.raises(kitcopy.KitError) as e:
        kitcopy._install(kit, str(repo), True, False, TODAY)
    assert e.value.code == 2 and "is a link" in e.value.message, e.value.message
    assert outside_untouched(outside) == before and not list(outside.iterdir())


def test_install_refuses_a_removed_folder_that_is_a_link(tmp_path):
    kit = project_kit(tmp_path)
    repo = git_repo(tmp_path)
    assert kitcopy._install(kit, str(repo), True, False, TODAY) == 0
    (repo / ".claude/skills/acme-brand/brand/old.svg").write_text("<svg/>", encoding="utf-8")       # left over: it is moved to removed-<date>/
    outside = tmp_path / "outside"
    outside.mkdir()
    (repo / f"removed-{TODAY}").symlink_to(outside, target_is_directory=True)
    with pytest.raises(kitcopy.KitError) as e:
        kitcopy._install(kit, str(repo), True, False, TODAY)
    assert e.value.code == 2 and "is a link" in e.value.message and not list(outside.iterdir())
    assert (repo / ".claude/skills/acme-brand/brand/old.svg").is_file()                                # nothing moved either


def test_a_planted_temporary_name_is_never_written_through(tmp_path):
    kit = project_kit(tmp_path)
    repo = git_repo(tmp_path)
    assert kitcopy._install(kit, str(repo), True, False, TODAY) == 0
    kd = repo / ".claude" / "skills" / "acme-brand"
    victim = tmp_path / "victim.txt"
    victim.write_text("keep me\n", encoding="utf-8")
    (kd / ".SKILL.md.install-tmp").symlink_to(victim)
    make_fake_kit(kit, {**GEN, "SKILL.md": b"# Acme brand\nversion two\n"}, {"recipes/ad.md": b"ad"}, version="1.2")
    assert kitcopy._install(kit, str(repo), True, False, TODAY) == 0
    assert victim.read_text(encoding="utf-8") == "keep me\n" and (kd / "SKILL.md").read_bytes() == b"# Acme brand\nversion two\n"


# ---------------------------------------------------------------- 0.11.2: the deferred minors of the 0.11.0 review

import os  # noqa: E402
import stat  # noqa: E402


def test_installed_files_get_the_permissions_of_a_new_file_and_keep_an_executable_bit(tmp_path):
    kit = project_kit(tmp_path)
    (kit / "snippets" / "logo.html").chmod(0o755)                                              # an executable file of the kit stays executable
    repo = git_repo(tmp_path)
    old = os.umask(0o022)
    try:
        assert kitcopy._install(kit, str(repo), True, False, TODAY) == 0
    finally:
        os.umask(old)
    kd = repo / ".claude" / "skills" / "acme-brand"
    modes = {p.relative_to(kd).as_posix(): stat.S_IMODE(p.stat().st_mode) for p in kd.rglob("*") if p.is_file()}
    assert modes.pop("snippets/logo.html") == 0o755, modes
    assert modes and set(modes.values()) == {0o644}, modes                                    # never owner-only (mkstemp's 0600): a teammate's checkout reads them


def test_a_move_aside_that_fails_stops_with_a_kit_error_naming_the_file_never_a_traceback(tmp_path, monkeypatch):
    kit = project_kit(tmp_path)
    repo = git_repo(tmp_path)
    assert kitcopy._install(kit, str(repo), True, False, TODAY) == 0
    (repo / ".claude/skills/acme-brand/brand/old.svg").write_text("<svg/>", encoding="utf-8")   # left over: moved aside to removed-<date>/

    def gone(src, dst, *a, **k):                                                                   # another install moved it meanwhile
        raise FileNotFoundError(2, "No such file or directory", src)
    monkeypatch.setattr(shutil, "move", gone)
    with pytest.raises(kitcopy.KitError) as e:
        kitcopy._install(kit, str(repo), True, False, TODAY)
    assert e.value.code == kitcopy.EXIT_FAIL, e.value.message
    assert ".claude/skills/acme-brand/brand/old.svg" in e.value.message and "No such file or directory" in e.value.message, e.value.message
    assert "run it again" in e.value.message, e.value.message


def test_the_brand_is_a_whole_word_in_any_spelling_also_in_a_description_over_several_lines(tmp_path):
    skills = tmp_path / ".claude" / "skills"
    skill(skills / "plain", "plain", "Applies the Lakowo brand to slides.")                            # written without its accents
    (skills / "block").mkdir(parents=True)
    (skills / "block" / "SKILL.md").write_text("---\nname: block\ndescription: >-\n  Applies the house style of\n  ŁĄKOWO to every page.\n---\n\n# x\n",
                                               encoding="utf-8")                                          # a YAML block, in capitals
    (skills / "wrapped").mkdir(parents=True)
    (skills / "wrapped" / "SKILL.md").write_text("---\nname: wrapped\ndescription: Applies the house style\n  of Łąkowo to every page.\n---\n\n# x\n",
                                                 encoding="utf-8")                                        # a plain value that goes on to the next line
    skill(skills / "lakowo-brand", "lakowo-brand", "Applies the Łąkowo brand.")                       # the kit itself
    assert kitcopy.other_brand_skills(skills, "lakowo-brand", "Łąkowo") == ["block", "plain", "wrapped"]
    short = tmp_path / "short" / ".claude" / "skills"
    skill(short / "spacecraft", "spacecraft", "Draws spacecraft and places them.")                       # "ace" inside other words is not the brand
    skill(short / "notes", "ace-notes", "Notes.")                                                         # a whole word of the name is
    skill(short / "body", "body", "Writes copy for Ace.")
    assert kitcopy.other_brand_skills(short, "ace-brand", "Ace") == ["body", "notes"]
