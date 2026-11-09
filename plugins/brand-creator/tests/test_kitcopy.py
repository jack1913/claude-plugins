"""The copy judge (scripts/adaptlib/kitcopy.py): it compares a kit folder with a product repository's copy, standard library only, and the kit ships it as install.py.

Kits here are made by tests/helpers.make_fake_kit, with no brand project behind them; expected values are written out by hand."""
import ast
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
