"""The Linux validation (tests/docker) and the CI workflow (.github/workflows/brand-creator.yml at the monorepo root): static checks of the files, and the log verifier on
logs written by hand in the shape pytest, node:test and the smoke print. Nothing here starts Docker."""
import re
import subprocess
import sys
from pathlib import Path

import pytest
from helpers import ROOT

DOCKER = ROOT / "tests" / "docker"
CI = ROOT.parents[1] / ".github" / "workflows" / "brand-creator.yml"   # the monorepo root: GitHub reads only the root .github/


def ci_text() -> str:
    assert CI.is_file(), f"{CI} not found: this plugin's workflow lives at the root of the claude-plugins monorepo (tests/docker/run.sh mirrors that layout in the container)"
    return CI.read_text()
VERIFY = DOCKER / "verify_log.py"
PERSONAL = ("/" + "Users/", "/" + "home/", "/" + "private/")   # written in pieces: test_static scans every shipped file for these


# ---------------------------------------------------------------- the image

def test_dockerfile_pins_every_input_and_ships_no_macos_tool():
    text = (DOCKER / "Dockerfile").read_text()
    for img in re.findall(r"^FROM\s+(\S+)", text, re.M):
        img = re.sub(r"\$\{(\w+)\}", lambda m: re.search(rf"^ARG {m.group(1)}=(\S+)", text, re.M).group(1), img)
        assert ":" in img and not img.endswith(":latest") and "@" not in img.split(":")[0], f"{img}: pin the image by a version tag"
    assert re.search(r"^ARG DEBIAN_TAG=\d+\.\d+-slim$", text, re.M) and re.search(r"^ARG UV_VERSION=\d+\.\d+\.\d+$", text, re.M)
    assert re.search(r"^ARG NODE_VERSION=24\.\d+\.\d+$", text, re.M)                       # Node 24, an exact version
    assert len(re.findall(r"^ARG NODE_SHA256_\w+=[0-9a-f]{64}$", text, re.M)) == 2          # both architectures, checked with sha256sum -c
    assert "sha256sum -c" in text
    for pkg in ("python3", "resvg", "imagemagick", "ghostscript", "poppler-utils", "ripgrep", "potrace", "fontconfig", "fonts-dejavu-core", "libnss3"):
        assert re.search(rf"\b{re.escape(pkg)}\b", text), pkg
    assert "USER bc" in text                                                                # not root
    for tool in ("sips", "iconutil", "actool", "xcrun", "xdg-open"):
        assert not re.search(rf"apt-get install[^\n]*{tool}", text), tool
    for needle in PERSONAL:                                                                 # no personal path in a shipped file
        assert needle not in text


def test_run_scripts_are_valid_bash_and_python():
    for f in ("run.sh", "in-container.sh"):
        assert subprocess.run(["bash", "-n", str(DOCKER / f)]).returncode == 0, f
        assert (DOCKER / f).stat().st_mode & 0o111, f"{f} is not executable"
    compile((DOCKER / "verify_log.py").read_text(), "verify_log.py", "exec")


def test_run_sh_does_not_turn_the_expected_skips_into_failures():
    run = (DOCKER / "run.sh").read_text() + (DOCKER / "in-container.sh").read_text()
    assert "REQUIRE_ALL" in run and "unset BRAND_CREATOR_REQUIRE_ALL" in run   # off macOS the Apple tests are NOT VERIFIED by design: verify_log decides
    assert "verify_log.py" in run and "tests/run-all.sh --smoke" in run and "setup --yes" in run
    assert ":ro" in run                                                         # the checkout is mounted read-only; the run works on a copy


# ---------------------------------------------------------------- the log verifier

GOOD = """\
.............................................                                    [100%]
1 live-network test(s) deselected on purpose (manual; run with BRAND_CREATOR_LIVE=1).
!!!!!!!!!!!! 47 TEST(S) NOT VERIFIED (skipped, which is not a pass) !!!!!!!!!!!!
  45 skipped because: not macOS
  2 skipped because: actool is not available
=========================== short test summary info ============================
SKIPPED [45] tests/conftest.py:85: NOT VERIFIED: not macOS
SKIPPED [2] tests/conftest.py:85: NOT VERIFIED: actool is not available
920 passed, 47 skipped, 1 deselected in 250.00s (0:04:10)
ℹ tests 53
ℹ pass 53
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0

   NOT VERIFIED: the claude CLI is not on PATH; the real eval loader was not run

SMOKE PASSED: Acme at /work/acme-smoke/acme
"""


def verify(tmp_path, text, rc=0, env=None):
    log = tmp_path / "run.log"
    log.write_text(text, encoding="utf-8")
    import os
    return subprocess.run([sys.executable, str(VERIFY), str(log), str(rc)], capture_output=True, text=True, env={**os.environ, "BRAND_CREATOR_DENYLIST": "x", **(env or {})})


def test_the_verifier_accepts_exactly_the_expected_off_macos_skips(tmp_path):
    r = verify(tmp_path, GOOD)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "920 passed, 47 skipped" in r.stdout and "LINUX RUN OK" in r.stdout and "47 TEST(S) NOT VERIFIED" in r.stdout   # the banner is printed verbatim


@pytest.mark.parametrize("mutation, why", [
    (lambda t: t.replace("920 passed, 47 skipped", "919 passed, 1 failed, 47 skipped"), "pytest: 1 failed"),
    (lambda t: t.replace("SKIPPED [2] tests/conftest.py:85: NOT VERIFIED: actool is not available",
                         "SKIPPED [2] tests/conftest.py:85: NOT VERIFIED: ImageMagick (magick) is not installed"), "unexpected skips"),
    (lambda t: t.replace("SKIPPED [2] tests/conftest.py:85: NOT VERIFIED: actool is not available", "SKIPPED [2] tests/x.py:9: some other reason"), "unexpected skips"),
    (lambda t: t.replace("ℹ skipped 0", "ℹ skipped 1"), "node:test: skipped=1"),
    (lambda t: t.replace("ℹ fail 0", "ℹ fail 2"), "node:test: fail=2"),
    (lambda t: t.replace("SMOKE PASSED", "SMOKE FAILED"), "did not print SMOKE PASSED"),
    (lambda t: t.replace("NOT VERIFIED: the claude CLI is not on PATH; the real eval loader was not run", "NOT VERIFIED: fonts are missing"), "unexpected NOT VERIFIED lines in the smoke"),
    (lambda t: t.replace("920 passed, 47 skipped", "920 passed, 48 skipped"), "-rs list names"),   # a skip that was not reported with its reason
])
def test_the_verifier_fails_on_everything_else(tmp_path, mutation, why):
    bad = mutation(GOOD)
    assert bad != GOOD, "the mutation did not apply"
    r = verify(tmp_path, bad)
    assert r.returncode == 1 and why in r.stderr, r.stdout + r.stderr
    assert verify(tmp_path, GOOD, rc=1).returncode == 1   # a non-zero exit of run-all.sh alone is a failure too


def test_the_denylist_skip_is_expected_only_when_no_denylist_was_mounted(tmp_path):
    skip = "SKIPPED [1] tests/test_static.py:105: NOT VERIFIED: BRAND_CREATOR_DENYLIST is not set (anonymisation NOT verified)\n"
    text = GOOD.replace("920 passed, 47 skipped", "919 passed, 48 skipped").replace("=========================== short test summary info ============================\n",
                                                                                "=========================== short test summary info ============================\n" + skip)
    assert skip in text and "48 skipped" in text
    assert verify(tmp_path, text, env={"BRAND_CREATOR_DENYLIST": ""}).returncode == 0   # no denylist given: the skip is expected, and printed
    r = verify(tmp_path, text, env={"BRAND_CREATOR_DENYLIST": "/run/denylist.json"})
    assert r.returncode == 1 and "unexpected skips" in r.stderr   # a mounted denylist must have run the test


# ---------------------------------------------------------------- the workflow

def test_ci_workflow_runs_linux_validate_and_macos_and_never_the_billed_eval():
    text = ci_text()
    for job in ("linux:", "validate:", "macos:"):
        assert re.search(rf"^  {job}$", text, re.M), job
    assert "tests/docker/run.sh" in text                                             # the same entry point a developer uses
    assert "claude plugin validate" in text and "--strict" in text
    assert "SKIPPED" in text and "available=false" in text                           # the documented skip when the CLI cannot be installed
    assert "requires_macos or requires_actool" in text and text.count("BRAND_CREATOR_REQUIRE_ALL") >= 2
    assert "setup --yes" in text and "acme.sh" in text
    for ln in text.splitlines():
        if not ln.lstrip().startswith("#"):
            assert "plugin eval" not in ln, "CI must not run the billed eval"
    for uses in re.findall(r"uses:\s*(\S+)", text):
        assert re.fullmatch(r"[\w.-]+/[\w.-]+@v\d+", uses), f"{uses}: pin actions by a version tag"
    assert "permissions:\n  contents: read" in text
    assert "working-directory: plugins/brand-creator" in text                         # every job runs in the plugin folder
    assert text.count('"plugins/brand-creator/**"') == 2 and text.count(".github/workflows/brand-creator.yml") >= 3   # push and pull_request are path-filtered
    for needle in PERSONAL:
        assert needle not in text


def test_ci_workflow_values_are_valid_yaml():
    """GitHub rejected the first push of the workflow outright ("workflow file issue"): a step name held ': ' unquoted. Every
    single-line `key: value` in the workflow must load as one YAML string, like the skill frontmatter."""
    from test_skills import yaml_plain_scalar_problem
    bad = []
    for n, line in enumerate(ci_text().splitlines(), 1):
        m = re.match(r"^\s*(?:- )?([A-Za-z_][\w-]*):\s+(.+)$", line)
        if m and not line.lstrip().startswith("#") and m.group(2).strip() not in ("|", ">"):
            why = yaml_plain_scalar_problem(m.group(2).strip())
            if why and not m.group(2).strip().startswith("${{"):
                bad.append(f"brand-creator.yml:{n}: {m.group(1)} {why}")
    assert not bad, "\n".join(bad)
