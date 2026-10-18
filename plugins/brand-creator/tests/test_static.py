"""Static checks over the shipped files: manifest shape, licences, pins, locks, README, no personal data."""
import json
import os
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

import pytest
from helpers import ROOT

sys.path.insert(0, str(ROOT / "scripts"))
import _common  # noqa: E402
import prereq  # noqa: E402

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".pytest_cache", ".venv"}


def shipped_files():
    for p in sorted(ROOT.rglob("*")):
        rel = p.relative_to(ROOT).parts
        # evals/results/ is the eval runner's local output (gitignored, never shipped): it records the machine's own paths
        if p.is_file() and not any(part in SKIP_DIRS for part in rel) and rel[:2] != ("evals", "results"):
            yield p


def text_files():
    for p in shipped_files():
        try:
            yield p, p.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            continue


# ---------------------------------------------------------------- anonymisation

def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).lower().replace("ł", "l")
    for a, b in (("‘", "'"), ("’", "'"), ("“", '"'), ("”", '"'), ("–", "-"), ("—", "-"), ("‑", "-")):
        s = s.replace(a, b)
    return re.sub(r"\s+", " ", "".join(c for c in s if not unicodedata.combining(c)))


def _hexes(text: str):
    for m in re.finditer(r"(?:#|%23)([0-9a-f]{8}|[0-9a-f]{6}|[0-9a-f]{4}|[0-9a-f]{3})(?![0-9a-z])", text, re.I):
        h = m.group(1).lower()
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h[:3])
        yield "#" + h[:6]
    for m in re.finditer(r"rgba?\(\s*(\d{1,3})\s*[, ]\s*(\d{1,3})\s*[, ]\s*(\d{1,3})", text, re.I):
        yield "#%02x%02x%02x" % tuple(min(255, int(x)) for x in m.groups())


def _scan(deny: dict, files, root: Path) -> list[str]:
    terms = [_fold(t) for t in deny["terms"] if t.strip()]
    allow = [_fold(a) for a in deny.get("allow", [])]
    hexes = {h.lower() for h in deny.get("hex", [])}
    hits = []
    for p in files:
        relp = p.relative_to(root).as_posix()
        folded_path = _fold(relp)
        hits += [f"{relp}: path contains {t!r}" for t in terms if t in folded_path]
        try:
            text = p.read_bytes().decode("utf-8")
        except UnicodeDecodeError:
            continue
        for n, line in enumerate(text.splitlines(), 1):
            f = _fold(line)
            for t in terms:
                i = f.find(t)
                while i >= 0:
                    if not any(a.find(t) >= 0 and f.find(a) <= i < f.find(a) + len(a) for a in allow if a in f):
                        hits.append(f"{relp}:{n}: {t!r}")
                        break
                    i = f.find(t, i + 1)
            for h in _hexes(line):
                if h in hexes:
                    hits.append(f"{relp}:{n}: denylisted colour {h}")
    return hits


def test_anonymisation_scanner_catches_planted_terms(tmp_path):
    """Mutation test for the scanner itself, with a synthetic denylist (nothing real is stored here)."""
    deny = {"terms": ["Zorblax Industries", "dluga fraza"], "hex": ["#123abc"], "allow": ["zorblaxes"]}
    f = tmp_path / "doc.md"
    clean = "Nothing to see. Acme is fictional. Colour #ff00aa.\n"
    f.write_text(clean)
    assert _scan(deny, [f], tmp_path) == []
    for planted in ("We worked for ZORBLAX industries.\n", "Colour #12ABC.\n", "colour #123abc\n", "rgb(18, 58, 188)\n", "Długa Fraza here\n", "color:%23123ABC\n"):
        f.write_text(clean + planted)
        assert f.read_text() != clean
        hits = _scan(deny, [f], tmp_path)
        assert hits or planted == "Colour #12ABC.\n", planted  # #12abc is a different colour than #123abc
    (tmp_path / "zorblax industries.txt").write_text("x")
    assert _scan(deny, [tmp_path / "zorblax industries.txt"], tmp_path)  # file names are scanned too


def test_anonymisation():
    """No client or brand names, real hex values or user quotes in any shipped file. The denylist is NOT shipped:
    point BRAND_CREATOR_DENYLIST at it. Without it this test is skipped with a loud banner."""
    path = os.environ.get("BRAND_CREATOR_DENYLIST", "").strip()
    if not path:
        banner = "NOT VERIFIED: BRAND_CREATOR_DENYLIST is not set, so the anonymisation test did NOT run"
        print("\n" + "!" * len(banner) + "\n" + banner + "\n" + "!" * len(banner), file=sys.stderr)
        import conftest
        conftest.NOT_VERIFIED.append(("tests/test_static.py::test_anonymisation", "BRAND_CREATOR_DENYLIST is not set (anonymisation NOT verified)"))
        if os.environ.get("BRAND_CREATOR_REQUIRE_ALL") == "1":
            pytest.fail(banner)
        pytest.skip(banner)
    deny = json.loads(Path(path).read_text())
    assert deny["terms"] and deny["hex"]
    hits = _scan(deny, list(shipped_files()), ROOT)
    assert hits == [], "anonymisation hits:\n" + "\n".join(hits[:20])


# ---------------------------------------------------------------- no personal data, no network identity

def test_user_agent_is_a_generic_constant_without_an_at_sign():
    assert "@" not in _common.USER_AGENT and re.fullmatch(r"brand-creator/\d+\.\d+\.\d+ \(\+https://[^@\s]+\)", _common.USER_AGENT)
    assert _common.USER_AGENT.split("/")[1].split(" ")[0] == json.loads((ROOT / ".claude-plugin/plugin.json").read_text())["version"]
    for p, text in text_files():
        for m in re.finditer(r"user-agent[\"']?\s*[:=,]\s*[\"']([^\"']+)", text, re.I):
            assert "@" not in m.group(1), f"{p}: User-Agent with @"


def test_no_personal_paths_or_email_addresses_in_shipped_files():
    for p, text in text_files():
        if p.name == "test_static.py":
            continue
        for needle in ("/Users/", "/home/", "C:\\Users", "/private/tmp", "/private/var"):
            assert needle not in text, f"{p.relative_to(ROOT)} contains {needle}"
        # `icon@2x.png` is a retina file name, not an address: a domain part that starts with a scale factor (2x, 3x) is skipped
            assert not re.search(r"[\w.+-]+@(?!\d+x\b)[\w-]+\.[a-z]{2,}", text, re.I), f"{p.relative_to(ROOT)} contains something that looks like an email address"


# ---------------------------------------------------------------- manifest, licence, pins

def test_plugin_json_matches_the_plan():
    d = json.loads((ROOT / ".claude-plugin/plugin.json").read_text())
    assert d["name"] == "brand-creator" and d["displayName"] and d["description"]
    assert d["version"] == "0.1.0" and re.fullmatch(r"\d+\.\d+\.\d+", d["version"])
    assert d["author"] == {"name": "brand-creator contributors"} and d["license"] == "MIT" and d["keywords"]
    assert "homepage" not in d  # a homepage must be a valid URL; none is published yet
    uc = d["userConfig"]
    assert set(uc) == {"projects_root", "review_surface"}
    assert uc["projects_root"]["type"] == "directory" and uc["projects_root"].get("required") in (None, False)
    assert uc["review_surface"]["type"] == "string" and uc["review_surface"]["options"] == ["auto", "artifact", "local"]
    assert uc["review_surface"]["default"] == "auto"
    for k in uc.values():
        assert k["title"] and k["description"]
        assert set(k) <= {"type", "title", "description", "required", "default", "options"}


def test_marketplace_json_has_one_entry_with_a_root_source():
    d = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
    assert len(d["plugins"]) == 1 and d["plugins"][0]["source"] == "./" and d["plugins"][0]["name"] == "brand-creator"
    assert d["owner"]["name"] and d["name"]


def test_license_and_notices():
    lic = (ROOT / "LICENSE").read_text()
    assert lic.startswith("MIT License") and "brand-creator contributors" in lic
    notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text()
    pkg = json.loads((ROOT / "scripts/package.json").read_text())["dependencies"]
    for name, ver in pkg.items():
        assert name in notices and ver in notices, f"{name} {ver} is not listed in THIRD_PARTY_NOTICES.md"
    assert "giginet" in notices.lower() or "icon-composer-validator" in notices  # placeholder for stage 3
    vendor = ROOT / "scripts" / "vendor"
    if vendor.is_dir():
        for f in vendor.rglob("*"):
            if f.is_file():
                assert f.relative_to(ROOT).as_posix() in notices, f"vendored file {f} is not listed in THIRD_PARTY_NOTICES.md"


def test_node_dependencies_are_pinned_exactly_and_locked():
    pkg = json.loads((ROOT / "scripts/package.json").read_text())
    assert pkg["dependencies"]["style-dictionary"] == "5.7.0"
    for name, ver in pkg["dependencies"].items():
        assert re.fullmatch(r"\d+\.\d+\.\d+", ver), f"{name} is not pinned exactly: {ver}"
    lock = json.loads((ROOT / "scripts/package-lock.json").read_text())
    assert lock["packages"][""]["dependencies"] == pkg["dependencies"]
    for name, ver in pkg["dependencies"].items():
        assert lock["packages"][f"node_modules/{name}"]["version"] == ver
    assert int(pkg["engines"]["node"].strip(">=")) >= 22


def test_every_uv_script_has_a_committed_lock_and_pep723_metadata():
    bootstrap = {"setup.py", "prereq.py", "guard.py"}
    for p in sorted((ROOT / "scripts").rglob("*.py")):
        if {"lib", "vendor", "booklib", "printlib", "adaptlib"} & set(p.relative_to(ROOT / "scripts").parts) or p.name in ("specs.py", "manifest.py", "_emit.py", "tierb.py"):
            continue
        text = p.read_text()
        assert "# /// script" in text and "requires-python" in text, p
        if p.name in bootstrap:
            assert not (p.parent / (p.name + ".lock")).exists()
            assert text.startswith("#!/usr/bin/env python3")
        else:
            assert (p.parent / (p.name + ".lock")).is_file(), f"{p.name} has no committed lock (uv lock --script)"
            assert text.startswith("#!/usr/bin/env -S uv run --script --locked"), p
            assert os.access(p, os.X_OK), p


def test_every_uv_script_starts_and_shows_help():
    for p in sorted((ROOT / "scripts").rglob("*.py")):
        if (p.parent / (p.name + ".lock")).is_file():
            r = subprocess.run(["uv", "run", "--script", "--locked", "--quiet", str(p), "--help"], capture_output=True, text=True,
                               env={**os.environ, "BRAND_CREATOR_DATA": "/nonexistent"})
            assert r.returncode == 0 and "usage:" in r.stdout, (p, r.stderr)


def test_executables_and_shebangs():
    assert os.access(ROOT / "bin" / "brand-creator", os.X_OK)
    assert (ROOT / "bin" / "brand-creator").read_text().startswith("#!/usr/bin/env bash")


def test_readme_states_the_minimum_claude_code_version_used_by_prereq():
    readme = (ROOT / "README.md").read_text()
    assert f"**{prereq.MIN_CLAUDE}**" in readme
    rows = re.findall(r"^\| .*? \| (\d+\.\d+\.\d+) \|", readme, re.M)
    runtime = re.search(r"\| Feature \|.*?\n((?:\|.*\n)+)", readme).group(1).splitlines()
    runtime_versions = [m.group(1) for r in runtime if "maintainers only" not in r and (m := re.search(r"\| (\d+\.\d+\.\d+) \|", r))]
    assert prereq.MIN_CLAUDE == max(runtime_versions, key=lambda v: tuple(map(int, v.split("."))))
    assert rows
    for section in ("OS matrix", "first 10 minutes", "/brand-creator:setup", "marketplace add", "Bash(brand-creator *)", "TODO"):
        assert section in readme, section


def test_wording_never_calls_dtcg_a_w3c_standard():
    for p, text in text_files():
        if p.name == "test_static.py":
            continue
        for m in re.finditer(r"(?i)w3c (design tokens|standard)[^\n]{0,60}", text):
            ctx = m.group(0).lower()
            assert "not a w3c standard" in text.lower()[max(0, m.start() - 20):m.end() + 20] or "not" in ctx, f"{p}: {m.group(0)}"


def test_contract_documents_every_data_section_the_lint_requires():
    lint = (ROOT / "scripts/board_lint.py").read_text()
    sections = set(re.findall(r'need\("([a-z-]+)"', lint)) | {"direction", "loser"}
    contract = (ROOT / "scripts/CONTRACT.md").read_text()
    for s in sections:
        assert f"`{s}`" in contract or f'data-section="{s}"' in contract, f"CONTRACT.md does not document data-section {s}"
    for attr in ("data-round", "data-board", "data-name", "data-register", "data-far", "data-direction", "data-letter", "data-field", "data-judge"):
        assert attr in contract, attr


def test_gitignore_covers_generated_files():
    g = (ROOT / ".gitignore").read_text()
    for entry in ("evals/results", "__pycache__", "node_modules"):
        assert entry in g


@pytest.mark.requires_claude
def test_claude_plugin_validate_strict_passes_and_catches_a_broken_manifest(plugin_copy):
    ok = subprocess.run(["claude", "plugin", "validate", str(plugin_copy), "--strict"], capture_output=True, text=True)
    assert ok.returncode == 0 and "Validation passed" in ok.stdout, ok.stdout + ok.stderr
    from helpers import mutate_json
    mutate_json(plugin_copy / ".claude-plugin/plugin.json", lambda d: d["userConfig"]["review_surface"].__setitem__("optionz", 1))
    bad = subprocess.run(["claude", "plugin", "validate", str(plugin_copy), "--strict"], capture_output=True, text=True)
    assert bad.returncode != 0 and "Unrecognized key" in bad.stdout + bad.stderr


def uv_scripts():
    return [p for p in sorted((ROOT / "scripts").rglob("*.py")) if (p.parent / (p.name + ".lock")).is_file()]


def test_script_locks_match_their_inline_metadata():
    """A lock that no longer matches the PEP 723 block would make `uv run --script --locked` fail for users."""
    for p in uv_scripts():
        r = subprocess.run(["uv", "lock", "--script", str(p), "--check"], capture_output=True, text=True)
        assert r.returncode == 0, f"{p.name}: lock is out of date: {r.stderr[-300:]}"


def test_every_python_dependency_is_pinned_exactly_and_listed_in_the_notices():
    notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text().lower()
    seen = {}
    for p in uv_scripts():
        m = re.search(r"# dependencies = \[(.*?)\]", p.read_text())
        assert m, p
        for dep in re.findall(r'"([^"]+)"', m.group(1)):
            assert re.fullmatch(r"[A-Za-z0-9_.-]+==\d+(\.\d+)*", dep), f"{p.name}: {dep} is not pinned with =="
            name, ver = dep.split("==")
            assert seen.setdefault(name, ver) == ver, f"{name} is pinned to two versions"
    assert {"pillow", "fonttools", "brotli", "skia-pathops", "coloraide"} <= set(seen)
    for name, ver in seen.items():
        row = next((l for l in notices.splitlines() if l.startswith("|") and name.replace("-", "") in l.replace("-", "")), None)
        assert row and ver in row, f"{name} {ver} is not listed in THIRD_PARTY_NOTICES.md"
        assert any(w in row for w in ("mit", "bsd", "apache", "mit-cmu", "mpl")), f"no licence on the {name} row"


def test_the_ofl_test_font_is_credited_and_ships_its_licence():
    notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text()
    fonts = ROOT / "tests/fixtures/fonts"
    assert "TestFont-subset.ttf" in notices and "SIL Open Font License" in notices and "Inter" in notices
    assert (fonts / "OFL.txt").read_text().count("SIL OPEN FONT LICENSE Version 1.1") == 1
    readme = (fonts / "README.md").read_text()
    assert "Modification" in readme and "OFL.txt" in readme and "THIRD_PARTY_NOTICES.md" in readme


def test_every_subcommand_in_bin_is_in_the_help_and_the_contract_names_every_report_tool():
    bin_text = (ROOT / "bin/brand-creator").read_text()
    usage = bin_text.split("usage() {")[1].split("EOF\n}")[0]
    dispatch = re.findall(r"^  ([a-z-]+)\)", bin_text.split('case "$sub" in\n  setup)')[1], re.M)
    assert {"downscale", "states-check", "family-check", "fontcheck", "fonts", "outline-glyphs", "snapshot", "verify-idempotent",
            "staleness", "specs-due"} <= set(dispatch)
    for sub in dispatch:
        assert re.search(rf"^\s+{re.escape(sub)}[ |]", usage, re.M) or sub in ("emit", "smoke"), f"{sub} is dispatched but not in the usage text"
    contract = (ROOT / "scripts/CONTRACT.md").read_text()
    for tool in ("downscale", "states", "family", "fontcheck", "motion", "idempotence", "staleness"):
        assert f"`{tool}`" in contract, f"CONTRACT.md does not name the report tool {tool}"
    for key in ("qa/rules.json", "qa/states.json", "qa/idempotence.json", "tools/inputs.json", "distinct", "content_languages", "family-check",
                "Motion proof", "px_lib"):
        assert key in contract, f"CONTRACT.md does not document {key}"


def test_every_install_hint_that_names_brew_also_names_linux():
    """Found by the Linux run: four 'cannot run' messages (book-pdf, print, print-check) told a Linux user only `brew install poppler` or
    `brew install ghostscript`. A message that names the macOS install must name the Linux one in the same sentence (`prereq` has the table)."""
    offenders = []
    for p in sorted((ROOT / "scripts").rglob("*.py")):
        if p.name == "prereq.py" or "vendor" in p.parts:
            continue
        text = p.read_text(encoding="utf-8")
        for m in re.finditer(r"brew install", text):
            if "Linux" not in text[max(0, m.start() - 120):m.end() + 160]:
                offenders.append(f"{p.relative_to(ROOT)}:{text.count(chr(10), 0, m.start()) + 1}")
    assert offenders == [], "macOS-only install hints: " + ", ".join(offenders)
