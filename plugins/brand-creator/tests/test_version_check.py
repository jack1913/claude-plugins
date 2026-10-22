"""brand-creator version --check: the copy a session runs against the copy Claude Code has installed (installed_plugins.json, next to the cache/
folder that holds the copies). A plugin cache is built in a temporary folder: <plugins>/cache/<marketplace>/brand-creator/<version>/."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "version_check.py"


def cache(tmp_path: Path, *versions: str) -> Path:
    """A plugins folder whose cache holds copies of brand-creator (only plugin.json) at the given versions."""
    plugins = tmp_path / "plugins"
    for v in versions:
        d = plugins / "cache" / "mk" / "brand-creator" / v / ".claude-plugin"
        d.mkdir(parents=True)
        (d / "plugin.json").write_text(json.dumps({"name": "brand-creator", "version": v}))
    return plugins


def record(plugins: Path, *entries: dict) -> None:
    (plugins / "installed_plugins.json").write_text(json.dumps({"version": 2, "plugins": {"brand-creator@mk": list(entries)}}))


def entry(plugins: Path, v: str, scope: str = "user", project: Path | None = None) -> dict:
    e = {"scope": scope, "installPath": str(plugins / "cache" / "mk" / "brand-creator" / v), "version": v}
    if project is not None:
        e["projectPath"] = str(project)
    return e


def check(copy: Path, here: Path):
    r = subprocess.run([sys.executable, str(SCRIPT), str(copy), str(here)], capture_output=True, text=True)
    return r.returncode, r.stdout.strip()


def test_the_installed_copy_passes_and_says_its_scope(tmp_path):
    plugins = cache(tmp_path, "0.3.5")
    record(plugins, entry(plugins, "0.3.5"))
    assert check(plugins / "cache/mk/brand-creator/0.3.5", tmp_path) == (0, "brand-creator 0.3.5: the installed copy (user scope)")


def test_a_session_that_still_runs_the_older_copy_fails_and_says_to_start_a_new_one(tmp_path):
    plugins = cache(tmp_path, "0.3.4", "0.3.5")
    record(plugins, entry(plugins, "0.3.5"))
    code, out = check(plugins / "cache/mk/brand-creator/0.3.4", tmp_path)
    assert code == 1
    assert out.startswith("brand-creator 0.3.4 is running here (") and "the installed copy is 0.3.5 (user scope, " in out
    assert out.endswith(": start a new session, so that the tools and the skills are the installed ones")


def test_a_project_install_counts_in_its_folder_and_below_and_nowhere_else(tmp_path):
    plugins = cache(tmp_path, "0.3.4", "0.3.5")
    proj = tmp_path / "brand"
    (proj / "tools").mkdir(parents=True)
    record(plugins, entry(plugins, "0.3.5", "project", proj))
    assert check(plugins / "cache/mk/brand-creator/0.3.4", proj / "tools")[0] == 1          # below the project: the project's install applies
    code, out = check(plugins / "cache/mk/brand-creator/0.3.4", tmp_path / "elsewhere")
    assert code == 0 and "not checked" in out and "has no install of this plugin that applies to" in out
    record(plugins, entry(plugins, "0.3.5", "project", proj), entry(plugins, "0.3.4"))       # the user install is the running copy: fine anywhere
    assert check(plugins / "cache/mk/brand-creator/0.3.4", tmp_path / "elsewhere")[0] == 0


def test_a_copy_that_is_not_in_a_plugin_cache_or_a_record_that_cannot_be_read_is_not_checked_never_passed_in_silence(tmp_path):
    code, out = check(ROOT, tmp_path)   # this checkout
    assert code == 0 and out.startswith(f"brand-creator {json.loads((ROOT / '.claude-plugin/plugin.json').read_text())['version']}: not checked: ")
    assert "not a copy in a plugin cache (a checkout of the repository?)" in out
    plugins = cache(tmp_path, "0.3.5")
    copy = plugins / "cache/mk/brand-creator/0.3.5"
    assert check(copy, tmp_path) == (0, f"brand-creator 0.3.5: not checked: {(plugins / 'installed_plugins.json').resolve()} cannot be read "
                                        f"(FileNotFoundError: [Errno 2] No such file or directory: '{(plugins / 'installed_plugins.json').resolve()}')")
    (plugins / "installed_plugins.json").write_text("{not json")
    code, out = check(copy, tmp_path)
    assert code == 0 and "not checked: " in out and "cannot be read (JSONDecodeError" in out


def test_the_cli_runs_it_with_the_folder_it_is_run_in_and_refuses_another_argument(tmp_path):
    bc = ROOT / "bin" / "brand-creator"
    r = subprocess.run([str(bc), "version", "--check"], capture_output=True, text=True, cwd=tmp_path)
    assert r.returncode == 0 and "not checked" in r.stdout   # this checkout
    r = subprocess.run([str(bc), "version", "--chek"], capture_output=True, text=True)
    assert r.returncode == 2 and "version takes no argument but --check" in r.stderr
    plugins = cache(tmp_path, "0.3.4")
    copy = plugins / "cache/mk/brand-creator/0.3.4"
    shutil.copytree(ROOT / "bin", copy / "bin"); shutil.copytree(ROOT / "scripts", copy / "scripts", ignore=shutil.ignore_patterns("__pycache__", "node_modules"))
    record(plugins, entry(plugins, "0.3.5"))
    r = subprocess.run([str(copy / "bin" / "brand-creator"), "version", "--check"], capture_output=True, text=True, cwd=tmp_path)
    assert r.returncode == 1 and "start a new session" in r.stdout
