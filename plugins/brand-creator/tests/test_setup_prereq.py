"""setup and prereq."""
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest
from helpers import ROOT, bc, data_dir

sys.path.insert(0, str(ROOT / "scripts"))
import prereq  # noqa: E402

MAC = platform.system() == "Darwin"


def bare_path(tmp_path, tools, fake_claude=None) -> dict:
    """A PATH holding only the listed tools (symlinks), optionally with a fake `claude` printing a version."""
    d = tmp_path / "bin"
    d.mkdir()
    for t in tools:
        found = shutil.which(t)
        if found:
            (d / t).symlink_to(found)
    if fake_claude:
        f = d / "claude"
        f.write_text(f"#!/bin/sh\necho '{fake_claude} (Claude Code)'\n")
        f.chmod(f.stat().st_mode | stat.S_IEXEC)
    return {"PATH": str(d)}


BASE = ["python3", "uv", "node", "npm", "bash", "env", "dirname", "readlink", "mkdir", "resvg"]


def run_prereq(args, env):
    return subprocess.run([sys.executable, str(ROOT / "scripts" / "prereq.py"), *args], capture_output=True, text=True,
                          env={**os.environ, **env})


def test_prereq_reports_ok_on_a_complete_machine():
    r = bc("prereq", "--for", "quick")
    assert r.returncode == 0, r.stdout
    assert "OK       python3" in r.stdout and "nothing blocks this scope" in r.stdout


def test_prereq_json_and_unknown_scope():
    r = bc("prereq", "--for", "names", "--json")
    doc = json.loads(r.stdout)
    assert doc["for"] == "names" and {i["id"] for i in doc["items"]} >= {"python3", "uv", "claude", "gh"}
    assert "dig" not in {i["id"] for i in doc["items"]}  # NS lookups use a socket, not dig
    assert all(set(i) == {"id", "status", "version", "blocks", "install", "note"} for i in doc["items"])
    assert bc("prereq", "--for", "bogus").returncode == 2


def test_prereq_missing_tool_says_what_it_blocks_and_how_to_install_it(tmp_path):
    env = bare_path(tmp_path, [t for t in BASE if t != "resvg"], fake_claude="2.1.302")
    r = run_prereq(["--for", "quick"], env)
    assert r.returncode == 3, r.stdout
    assert "MISSING  resvg" in r.stdout and "blocks:  logo sheet" in r.stdout
    assert ("brew install resvg" if MAC else "resvg") in r.stdout
    assert "BLOCKED" in r.stderr and "resvg" in r.stderr


def test_prereq_checks_the_claude_version_against_the_stated_minimum(tmp_path):
    (tmp_path / "a").mkdir()
    r = run_prereq(["--for", "quick"], bare_path(tmp_path / "a", BASE, fake_claude="2.1.200"))
    assert r.returncode == 3 and "below the minimum 2.1.271" in r.stdout
    (tmp_path / "b").mkdir()
    r = run_prereq(["--for", "quick"], bare_path(tmp_path / "b", BASE, fake_claude="2.1.271"))
    assert "OK       claude       2.1.271" in r.stdout


def test_prereq_apple_scope_is_mac_only_without_fallback():
    r = bc("prereq", "--for", "apple", "--json")
    items = {i["id"]: i for i in json.loads(r.stdout)["items"]}
    if MAC:
        assert items["actool"]["status"] in ("OK", "MISSING") and "sdk:watchos" in items
    else:
        assert items["xcode"]["status"] == "MISSING" and "no fallback" in items["xcode"]["blocks"]
        assert r.returncode == 3


def test_prereq_quick_scope_lists_the_downscaler_and_names_the_opt_in_off_macos():
    """The downscale check needs sips (macOS) or an explicit renderer opt-in: prereq says which, and never calls it a blocker."""
    r = bc("prereq", "--for", "quick", "--json")
    items = {i["id"]: i for i in json.loads(r.stdout)["items"]}
    assert "sips" in items
    if MAC:
        assert items["sips"]["status"] == "OK"
    else:
        assert items["sips"]["status"] == "WARN" and "--renderer=resvg|pillow" in items["sips"]["note"]
        assert "opted in" in bc("prereq", "--for", "quick").stdout


def test_prereq_without_sips_warns_and_does_not_block(tmp_path):
    """Hide sips from PATH: the downscale item is a WARN with the opt-in note, and the scope is still not blocked by it."""
    env = bare_path(tmp_path, BASE, fake_claude="2.1.302")
    r = run_prereq(["--for", "quick", "--json", "--data", str(data_dir() or tmp_path)], env)
    items = {i["id"]: i for i in json.loads(r.stdout)["items"]}
    assert items["sips"]["status"] == "WARN" and "downscale check" in items["sips"]["blocks"] + items["sips"]["note"]


def test_prereq_print_scope_names_ghostscript(tmp_path):
    env = bare_path(tmp_path, ["python3", "uv", "bash", "env"], fake_claude="2.1.302")
    r = run_prereq(["--for", "print"], env)
    assert r.returncode == 3 and "MISSING  gs" in r.stdout and "blocks:  print PDFs (outlines the text; a PDF/X-4 candidate with --icc)" in r.stdout


# ---------------------------------------------------------------- setup

def test_setup_plan_shows_downloads_and_sizes_and_changes_nothing(tmp_path):
    d = tmp_path / "data"
    r = bc("setup", "--plan", data=d)
    assert r.returncode == 0, r.stderr
    assert "npm ci" in r.stdout and "MB" in r.stdout and "Chrome Headless Shell" in r.stdout and "Nothing is written under the plugin folder" in r.stdout
    assert not (d / "node_modules").exists() and not (d / "setup.json").exists()


def test_setup_noninteractive_needs_yes(tmp_path):
    d = tmp_path / "data"
    r = bc("setup", data=d)
    assert r.returncode == 2 and "--yes" in r.stderr
    assert not (d / "node_modules").exists()


def test_setup_without_node_names_the_install_command(tmp_path):
    env = bare_path(tmp_path, ["python3", "uv", "bash", "env", "dirname", "mkdir"])
    r = bc("setup", "--yes", data=tmp_path / "data", env=env)
    assert r.returncode == 3 and "MISSING node" in r.stderr and "install:" in r.stderr


def test_bin_requires_a_data_dir_for_everything_but_help_version_prereq(tmp_path):
    env = {k: v for k, v in os.environ.items() if k != "BRAND_CREATOR_DATA"}
    exe = str(ROOT / "bin" / "brand-creator")
    for sub in ("state", "setup", "tokens", "contrast", "check", "new"):
        r = subprocess.run([exe, sub], capture_output=True, text=True, env=env, cwd=tmp_path)
        assert r.returncode == 2 and "--data" in r.stderr, sub
    for sub in ("help", "version"):
        assert subprocess.run([exe, sub], capture_output=True, text=True, env=env).returncode == 0
    assert subprocess.run([exe, "prereq", "--for", "names"], capture_output=True, text=True, env=env).returncode in (0, 3)
    r = subprocess.run([exe, "--data", str(tmp_path / "d"), "nonsense"], capture_output=True, text=True, env=env)
    assert r.returncode == 2 and "unknown subcommand" in r.stderr
    r = subprocess.run([exe, "--data", str(tmp_path / "d"), "names"], capture_output=True, text=True, env=env)
    assert r.returncode == 2 and "required: candidates" in r.stderr  # names now exists; it needs a candidate


def test_bin_resolves_the_plugin_root_through_a_symlink(tmp_path):
    link = tmp_path / "brand-creator"
    link.symlink_to(ROOT / "bin" / "brand-creator")
    r = subprocess.run([str(link), "version"], capture_output=True, text=True)
    assert r.returncode == 0 and r.stdout.strip() == json.loads((ROOT / ".claude-plugin/plugin.json").read_text())["version"]


def test_nothing_is_written_under_the_plugin_root(tmp_path):
    before = sorted(p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*")
                    if p.is_file() and ".git/" not in p.as_posix() and "__pycache__" not in p.parts and ".pytest_cache" not in p.parts)
    bc("prereq", "--for", "quick")
    bc("setup", "--plan", data=tmp_path / "d")
    bc("new", "x", "--root", str(tmp_path), data=tmp_path / "d")
    after = sorted(p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*")
                   if p.is_file() and ".git/" not in p.as_posix() and "__pycache__" not in p.parts and ".pytest_cache" not in p.parts)
    assert before == after


@pytest.mark.requires_setup
def test_installed_playwright_matches_the_pinned_chromium_revision():
    d = data_dir()
    browsers = json.loads((d / "node_modules/playwright-core/browsers.json").read_text())["browsers"]
    rev = next(b["revision"] for b in browsers if b["name"] == "chromium-headless-shell")
    assert rev == prereq.PINNED_CHROMIUM_REVISION
    st = json.loads((d / "setup.json").read_text())
    assert st["chromium_revision"] == rev and Path(st["browsers_path"], f"chromium_headless_shell-{rev}", "INSTALLATION_COMPLETE").is_file()
    r = bc("prereq", "--for", "quick", "--json")
    assert {i["id"]: i["status"] for i in json.loads(r.stdout)["items"]}["chromium"] == "OK"
