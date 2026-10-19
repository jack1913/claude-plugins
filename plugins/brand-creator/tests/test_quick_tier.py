"""The Quick tier on a machine without the Apple tools (Stage 7): what tests/smoke/quick.sh proves end to end, as fast unit tests.

Regressions found by the Quick-tier smoke: prereq asked the renderer question twice off macOS and never on a Mac whose PATH lacks sips; prereq
called a broken npm OK; and a refused `emit print` / `emit presskit` left a failing report for a run that never started."""
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest
from helpers import ROOT, bc, make_project

QUESTION = "--renderer=resvg|pillow choice"
SMOKE = ROOT / "tests" / "smoke"
BAKERY = SMOKE / "quick-bakery"


def shim_path(tmp_path: Path, tools: list[str], extra: dict[str, str] | None = None) -> dict:
    """A PATH of symlinks to `tools` only (so no sips, iconutil, xcrun or git), plus scripts named in `extra` (name -> body)."""
    d = tmp_path / "shim"
    d.mkdir()
    for t in tools:
        found = shutil.which(t)
        if found and not (d / t).exists():
            (d / t).symlink_to(found)
    for name, body in (extra or {}).items():
        f = d / name
        f.write_text("#!/bin/sh\n" + body + "\n")
        f.chmod(f.stat().st_mode | stat.S_IEXEC)
    return {"PATH": str(d)}


def prereq(args: list[str], env: dict) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(ROOT / "scripts" / "prereq.py"), *args], capture_output=True, text=True, env={**os.environ, **env})


FAKE_NPM = "echo '10.9.2'"
BASE = ["python3", "uv", "node", "bash", "env", "dirname", "readlink", "mkdir", "resvg"]


def test_prereq_without_sips_asks_the_renderer_question_exactly_once(tmp_path):
    """sips is not on PATH (a Mac with the tool hidden, or Linux): the sips row carries the one question, the scope is not blocked, and the
    closing note does not ask it a second time."""
    assert not shutil.which("sips", path=shim_path(tmp_path, BASE, {"claude": "echo '2.1.302 (Claude Code)'", "npm": FAKE_NPM})["PATH"])
    r = prereq(["--for", "quick"], {"PATH": str(tmp_path / "shim")})
    assert r.returncode == 0, r.stdout + r.stderr
    assert "WARN     sips" in r.stdout and "nothing blocks this scope" in r.stdout
    assert r.stdout.count(QUESTION) == 1, r.stdout
    assert r.stdout.count("opted in") == 1, r.stdout
    for scope in ("standard", "full"):   # the other scopes that carry the downscale check say it once too
        out = prereq(["--for", scope], {"PATH": str(tmp_path / "shim")}).stdout
        assert out.count(QUESTION) <= 1, out


@pytest.mark.requires_macos   # sips ships with macOS; the conftest marker gives the skip the reason the Linux verifier expects
def test_prereq_with_a_system_downscaler_does_not_ask(tmp_path):
    env = shim_path(tmp_path, BASE + ["sips"], {"claude": "echo '2.1.302 (Claude Code)'", "npm": FAKE_NPM})
    out = prereq(["--for", "quick"], env).stdout
    assert "OK       sips" in out and QUESTION not in out, out


def test_prereq_says_a_broken_npm_is_missing_not_ok(tmp_path):
    """`npm --version` that fails (a clobbered shim, a half-removed install) used to read as OK with the error text as its version."""
    env = shim_path(tmp_path, BASE, {"claude": "echo '2.1.302 (Claude Code)'", "npm": "echo 'npm: line 2: /: is a directory' >&2; exit 126"})
    r = prereq(["--for", "quick"], env)
    assert r.returncode == 3, r.stdout
    assert "MISSING  npm" in r.stdout and "did not report a version" in r.stdout and "is a directory" in r.stdout
    assert "BLOCKED" in r.stderr and "npm" in r.stderr


@pytest.mark.parametrize("pack,args", [("print", ["--region", "EU"]), ("presskit", [])])
def test_a_tier_refusal_leaves_no_failing_report(tmp_path, pack, args):
    """The Standard-tier packs refuse in the Quick tier (exit 2, the way up) before any report exists: nothing is written, and the failure of
    a run that never started is not recorded for `check` or a reader to find."""
    p = make_project(tmp_path)
    assert bc("state", "--record", "G3", "approved (test)", project=p).returncode == 0
    r = bc("emit", pack, *args, project=p)
    assert r.returncode == 2, r.stdout + r.stderr
    assert "state --set tier=standard" in r.stderr
    assert not (p / "assets" / "_checks" / f"emit-{pack}.json").exists(), "a refused emit left a report behind"
    assert not (p / "assets" / pack).exists()


def test_the_tier_gate_comes_after_the_g3_gate(tmp_path):
    """Order is unchanged: without G3 the emitters exit 1 first, whatever the tier."""
    p = make_project(tmp_path)
    r = bc("emit", "print", "--region", "EU", project=p)
    assert r.returncode == 1 and "G3" in r.stderr


# ----------------------------------------------------------------- the smoke fixtures and the wiring

def test_run_all_runs_the_quick_smoke_after_the_acme_smoke():
    text = (ROOT / "tests" / "run-all.sh").read_text()
    assert "tests/smoke/acme.sh" in text and "tests/smoke/quick.sh" in text
    assert text.index("tests/smoke/acme.sh") < text.index("tests/smoke/quick.sh")
    assert os.access(SMOKE / "quick.sh", os.X_OK)


def test_quick_smoke_reads_only_files_that_exist():
    import re
    text = (SMOKE / "quick.sh").read_text()
    for rel in set(re.findall(r'"\$FIX[/"]([A-Za-z0-9_./*-]*)', text)):
        if rel and "*" not in rel:
            assert (BAKERY / rel).exists(), rel
    for f in ("brief.md", "facts.md", "board.html", "tools/loaf_mark.py", "tokens/exceptions.json", "tokens/primitives.tokens.json",
              "tokens/semantic.light.tokens.json", "tokens/semantic.dark.tokens.json"):
        assert (BAKERY / f).is_file(), f


def test_the_bakery_board_passes_board_lint(tmp_path):
    """The Quick smoke's first board is a real filled round page: board-lint (Python only, no Chromium) passes it in a Quick project."""
    p = make_project(tmp_path, slug="marlow-lane", name="Marlow Lane Bakery")
    (p / "rounds" / "r1").mkdir(parents=True)
    shutil.copy2(BAKERY / "board.html", p / "rounds" / "r1" / "board.html")
    r = bc("board-lint", "rounds/r1/board.html", project=p)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "board-lint: PASS" in r.stdout


def test_the_bakery_fixtures_are_not_software_and_carry_no_personal_data():
    blob = "\n".join(f.read_text(encoding="utf-8") for f in BAKERY.rglob("*") if f.is_file() and f.suffix in (".md", ".html", ".json", ".py"))
    assert "Marlow Lane Bakery" in blob and "sourdough" in blob.lower()
    home_prefix = "/" + "Users" + "/"   # spelled in two parts: test_static forbids the literal in any shipped file
    for word in ("npm", "pypi", "crates.io", "github.com", home_prefix, "@"):
        assert word not in blob.replace("@media", ""), word
    assert str(Path.home()) not in (SMOKE / "quick.sh").read_text()
