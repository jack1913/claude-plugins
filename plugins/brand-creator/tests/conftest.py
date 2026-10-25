"""pytest configuration: markers, loud banners for tests that could not run, shared fixtures."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import FIXTURES, ROOT, android_sdk, bc, data_dir, install_fixture, make_project, own_data  # noqa: E402

NOT_VERIFIED: list[tuple[str, str]] = []
REQUIRE_ALL = os.environ.get("BRAND_CREATOR_REQUIRE_ALL") == "1"


def pytest_configure(config):
    for m, d in (("requires_setup", "needs `brand-creator setup` (npm packages and Chromium) in BRAND_CREATOR_DATA"),
                 ("requires_resvg", "needs the resvg program on PATH"),
                 ("requires_magick", "needs ImageMagick (magick) on PATH"),
                 ("requires_gs", "needs Ghostscript (gs) and poppler's pdfinfo on PATH"),
                 ("requires_macos", "needs macOS"),
                 ("requires_actool", "needs Xcode's actool"),
                 ("requires_aapt2", "needs the Android SDK: aapt2 from build-tools and a platform's android.jar (ANDROID_HOME or ANDROID_SDK_ROOT)"),
                 ("requires_node", "needs Node 22+"),
                 ("requires_claude", "needs the claude CLI on PATH"),
                 ("requires_rg", "needs ripgrep (rg) on PATH"),
                 ("requires_design_lint", "needs @google/design.md installed in BRAND_CREATOR_DATA by `brand-creator setup`"),
                 ("requires_pdftotext", "needs poppler's pdftotext on PATH"),
                 ("requires_network", "talks to real services; deselected unless BRAND_CREATOR_LIVE=1 (manual live smoke)")):
        config.addinivalue_line("markers", f"{m}: {d}")
    if not config.pluginmanager.hasplugin("timeout"):   # run without tests/requirements.txt: no time limit, and the mark is still known
        config.addinivalue_line("markers", "timeout(seconds): the most a test may run (pytest-timeout, from tests/requirements.txt)")


DEFAULT_TIMEOUT = 300   # seconds a test may run before pytest-timeout stops it as hung; a module that needs longer marks itself (test_finish_chain)


LIVE = os.environ.get("BRAND_CREATOR_LIVE") == "1"
DESELECTED_LIVE: list[str] = []


def pytest_collection_modifyitems(config, items):
    """Every test gets a time limit (DEFAULT_TIMEOUT unless it carries its own), so a hung test fails by name instead of
    holding the whole run until CI kills it. Live-network tests are manual: deselected (not skipped, so REQUIRE_ALL stays
    meaningful) unless BRAND_CREATOR_LIVE=1."""
    if config.pluginmanager.hasplugin("timeout"):
        for it in items:
            if it.get_closest_marker("timeout") is None:
                it.add_marker(pytest.mark.timeout(DEFAULT_TIMEOUT))
    if LIVE:
        return
    keep = []
    for it in items:
        if it.get_closest_marker("requires_network"):
            DESELECTED_LIVE.append(it.nodeid)
        else:
            keep.append(it)
    if DESELECTED_LIVE:
        config.hook.pytest_deselected(items=[i for i in items if i not in keep])
        items[:] = keep


def _missing(item) -> str | None:
    if item.get_closest_marker("requires_setup") and data_dir() is None:
        return "BRAND_CREATOR_DATA is unset or `brand-creator setup` has not been run there"
    if item.get_closest_marker("requires_resvg") and not shutil.which("resvg"):
        return "resvg is not installed"
    if item.get_closest_marker("requires_magick") and not shutil.which("magick"):
        return "ImageMagick (magick) is not installed"
    if item.get_closest_marker("requires_gs") and not (shutil.which("gs") and shutil.which("pdfinfo")):
        return "Ghostscript or pdfinfo is not installed"
    if item.get_closest_marker("requires_node") and not shutil.which("node"):
        return "node is not installed"
    if item.get_closest_marker("requires_rg") and not shutil.which("rg"):
        return "ripgrep (rg) is not installed"
    if item.get_closest_marker("requires_pdftotext") and not shutil.which("pdftotext"):
        return "poppler's pdftotext is not installed"
    if item.get_closest_marker("requires_design_lint") and not (data_dir() and (data_dir() / "node_modules" / "@google" / "design.md" / "package.json").is_file()):
        return "@google/design.md is not installed in the data directory (brand-creator setup --yes)"
    if item.get_closest_marker("requires_claude") and not shutil.which("claude"):
        return "the claude CLI is not on PATH"
    if item.get_closest_marker("requires_macos") and sys.platform != "darwin":
        return "not macOS"
    if item.get_closest_marker("requires_actool") and not (sys.platform == "darwin" and shutil.which("xcrun")):
        return "actool is not available"
    if item.get_closest_marker("requires_aapt2") and android_sdk() is None:
        return "the Android SDK (aapt2 and a platform android.jar) is not installed"
    return None


def pytest_runtest_setup(item):
    why = _missing(item)
    if why:
        if REQUIRE_ALL:
            pytest.fail(f"BRAND_CREATOR_REQUIRE_ALL=1 and a prerequisite is missing: {why}", pytrace=False)
        NOT_VERIFIED.append((item.nodeid, why))
        pytest.skip(f"NOT VERIFIED: {why}")


def pytest_sessionfinish(session):
    """Under pytest-xdist each worker holds its own lists: hand them to the controller so its banner sees every worker."""
    out = getattr(session.config, "workeroutput", None)
    if out is not None:
        out["bc_not_verified"] = NOT_VERIFIED
        out["bc_deselected_live"] = DESELECTED_LIVE


@pytest.hookimpl(optionalhook=True)
def pytest_testnodedown(node, error):
    out = getattr(node, "workeroutput", {})
    NOT_VERIFIED.extend(tuple(x) for x in out.get("bc_not_verified", []))
    # every worker collects the same tests, so the deselected list is the same on each: keep one copy
    for nid in out.get("bc_deselected_live", []):
        if nid not in DESELECTED_LIVE:
            DESELECTED_LIVE.append(nid)


def pytest_terminal_summary(terminalreporter):
    if DESELECTED_LIVE:
        terminalreporter.write_line(f"{len(DESELECTED_LIVE)} live-network test(s) deselected on purpose (manual; run with BRAND_CREATOR_LIVE=1).")
    if NOT_VERIFIED:
        tr = terminalreporter
        tr.write_sep("!", f"{len(NOT_VERIFIED)} TEST(S) NOT VERIFIED (skipped, which is not a pass)", red=True, bold=True)
        reasons = sorted({w for _, w in NOT_VERIFIED})
        for w in reasons:
            tr.write_line(f"  {sum(1 for _, x in NOT_VERIFIED if x == w)} skipped because: {w}")
        tr.write_line("  Set BRAND_CREATOR_DATA to a set-up data directory (brand-creator --data <dir> setup --yes), or set "
                      "BRAND_CREATOR_REQUIRE_ALL=1 to turn these skips into failures.")


@pytest.fixture(scope="session", autouse=True)
def setup_data(tmp_path_factory):
    """The set-up data directory the run was given (BRAND_CREATOR_DATA), or None. The tools never write into it: for the whole session
    BRAND_CREATOR_DATA names a data directory of the run's own (own_data in helpers.py) among pytest's temporary folders, which pytest
    deletes, scratch output included, once three newer runs exist."""
    given = data_dir()
    if given is None:
        yield None
        return
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("BRAND_CREATOR_DATA", str(own_data(given, tmp_path_factory.mktemp("data"))))
        yield given


@pytest.fixture(scope="session")
def golden(tmp_path_factory) -> Path:
    """A fully built Acme project (tokens, mark, board, G3). Tests copy it; nobody edits the golden one."""
    if data_dir() is None:
        pytest.skip("NOT VERIFIED: no set-up data directory")
    tmp = tmp_path_factory.mktemp("golden")
    p = make_project(tmp)
    install_fixture(p)
    assert bc("state", "--record", "G3", "approved r1 (test)", project=p).returncode == 0
    r = bc("tokens", project=p)
    assert r.returncode == 0, r.stdout + r.stderr
    return p


@pytest.fixture
def acme(golden, tmp_path) -> Path:
    dst = tmp_path / "acme"
    shutil.copytree(golden, dst, symlinks=False)
    return dst


@pytest.fixture
def plugin_copy(tmp_path) -> Path:
    """A throwaway copy of the plugin (for tests that must change a plugin file, e.g. platform-specs.json)."""
    dst = tmp_path / "plugin"
    for d in ("bin", "scripts", "templates", ".claude-plugin", "hooks"):
        shutil.copytree(ROOT / d, dst / d, symlinks=True, ignore=shutil.ignore_patterns("__pycache__"))
    return dst
