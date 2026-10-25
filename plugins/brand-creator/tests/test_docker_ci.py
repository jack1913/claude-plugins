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
    base = {k: v for k, v in os.environ.items() if k != "BRAND_CREATOR_TEST_PARTS"}   # the CI job running these tests sets its own part; these logs are whole runs
    return subprocess.run([sys.executable, str(VERIFY), str(log), str(rc)], capture_output=True, text=True, env={**base, "BRAND_CREATOR_DENYLIST": "x", **(env or {})})


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
    (lambda t: t.replace("SMOKE PASSED: Acme at", "SMOKE PASSED (part finish: the shared build, then tools/finish.sh): Acme at"),
     "did not print SMOKE PASSED for the whole smoke"),                                                           # half a smoke is not the smoke
    (lambda t: t.replace("SMOKE PASSED: Acme at", "QUICK SMOKE PASSED: Acme at"), "did not print SMOKE PASSED for the whole smoke"),
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
    for job in ("linux-suite:", "validate:", "macos-suite:", "brand-creator:"):
        assert re.search(rf"^  {job}$", text, re.M), job
    assert "tests/docker/run.sh" in text                                             # the same entry point a developer uses
    assert "claude plugin validate" in text and "--strict" in text
    validate = text[text.index("\n  validate:\n"):text.index("\n  macos-suite:\n")]
    assert "claude --version" in validate and "available=" not in validate and "if:" not in validate   # no CLI fails the job: the verdict never passes an unvalidated manifest
    assert "requires_macos or requires_actool" in text and text.count("BRAND_CREATOR_REQUIRE_ALL") >= 2
    assert "setup --yes" in text and "acme.sh" in text
    for ln in text.splitlines():
        if not ln.lstrip().startswith("#"):
            assert "plugin eval" not in ln, "CI must not run the billed eval"
    for uses in re.findall(r"uses:\s*(\S+)", text):
        assert re.fullmatch(r"[\w.-]+/[\w.-]+@v\d+", uses), f"{uses}: pin actions by a version tag"
    assert "permissions:\n  contents: read" in text
    assert "working-directory: plugins/brand-creator" in text                         # every job runs in the plugin folder
    assert text.count('"plugins/brand-creator/**"') == 2 and text.count(".github/workflows/brand-creator.yml") == 2   # push and pull_request are path-filtered
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


# ---------------------------------------------------------------- the suite in parts (one CI job each), its deadlines and its time limits

PYTEST_ONLY = GOOD[:GOOD.index("ℹ tests 53")]        # what a pytest-only run prints
NODE_ONLY = GOOD[GOOD.index("ℹ tests 53"):GOOD.index("\n   NOT VERIFIED: the claude CLI")] + "\n"   # what a node-only run prints
SMOKE_ONLY = GOOD[GOOD.index("\n   NOT VERIFIED: the claude CLI"):]                              # what a smoke-only run prints


@pytest.mark.parametrize("parts, text", [("pytest", PYTEST_ONLY), ("node", NODE_ONLY), ("smoke", SMOKE_ONLY), ("pytest,node,smoke", GOOD)])
def test_the_verifier_accepts_the_log_of_each_part_it_was_asked_for(tmp_path, parts, text):
    r = verify(tmp_path, text, env={"BRAND_CREATOR_TEST_PARTS": parts})
    assert r.returncode == 0 and f"LINUX RUN OK ({parts.replace(',', ', ')})" in r.stdout, r.stdout + r.stderr


@pytest.mark.parametrize("parts, text, why", [
    ("pytest,node", PYTEST_ONLY, "no node:test summary"),                 # a part that was asked for and left no summary did not run: a failure
    ("pytest,smoke", PYTEST_ONLY, "did not print SMOKE PASSED"),
    ("node", NODE_ONLY.replace("ℹ fail 0", "ℹ fail 1"), "node:test: fail=1"),
    ("smoke", SMOKE_ONLY.replace("SMOKE PASSED", "SMOKE FAILED"), "did not print SMOKE PASSED"),
])
def test_the_verifier_fails_a_part_that_did_not_run_or_failed(tmp_path, parts, text, why):
    r = verify(tmp_path, text, env={"BRAND_CREATOR_TEST_PARTS": parts})
    assert r.returncode == 1 and why in r.stderr, r.stdout + r.stderr
    r = verify(tmp_path, PYTEST_ONLY, env={"BRAND_CREATOR_TEST_PARTS": "pytest"})   # the positive control: the same verifier passes the pytest part alone
    assert r.returncode == 0, r.stdout + r.stderr


def test_the_verifier_refuses_a_part_it_does_not_know(tmp_path):
    r = verify(tmp_path, GOOD, env={"BRAND_CREATOR_TEST_PARTS": "pytest,unit"})
    assert r.returncode == 2 and "name one or more of pytest, node, smoke" in r.stderr


@pytest.mark.parametrize("parts, args, why", [("unit", [], "unknown part 'unit'"), ("smoke", [], "runs nothing (smoke needs --smoke)")])
def test_run_all_refuses_a_selection_that_names_an_unknown_part_or_runs_nothing(parts, args, why):
    import os
    r = subprocess.run(["bash", str(ROOT / "tests" / "run-all.sh"), *args], capture_output=True, text=True, env={**os.environ, "BRAND_CREATOR_TEST_PARTS": parts})
    assert r.returncode == 2 and why in r.stderr, r.stdout + r.stderr


def test_ci_runs_each_part_in_its_own_job_and_the_verdict_passes_only_when_every_job_did():
    text = ci_text()
    job = text[text.index("  linux-suite:"):text.index("\n  validate:\n")]
    verdict = text[text.index("\n  brand-creator:\n"):]                                        # the check the release-tag ruleset requires
    parts = re.findall(r"- part: (\w+)\n\s+suite-minutes: (\d+)\n\s+job-minutes: (\d+)", job)
    assert sorted(p for p, _, _ in parts) == ["node", "pytest", "smoke"], parts
    for part, suite, jobm in parts:
        assert int(suite) + 10 <= int(jobm), f"{part}: the deadline inside the container must end well before the job's ({suite} vs {jobm} minutes)"
    assert "fail-fast: false" in job and "BRAND_CREATOR_TEST_PARTS: ${{ matrix.part }}" in job and "BRAND_CREATOR_SUITE_MINUTES: ${{ matrix.suite-minutes }}" in job
    assert "if: ${{ !cancelled() }}" in job and "uses: actions/upload-artifact@v" in job        # the log and the JUnit file are kept, a failing run's too
    jobs = re.findall(r"^  ([\w-]+):$", text[text.index("\njobs:\n"):], re.M)
    needs = re.findall(r"^      - ([\w-]+)$", verdict[:verdict.index("\n    if:")], re.M)
    assert sorted(needs) == sorted(j for j in jobs if j != "brand-creator"), (jobs, needs)  # the verdict waits for every other job
    assert "if: ${{ always() }}" in verdict                                                    # and runs even when one failed or was cancelled
    assert "NEEDS: ${{ toJSON(needs) }}" in verdict and """jq -e 'all(.[]; .result == "success")'""" in verdict   # only success passes it: skipped or cancelled is never green


def test_macos_runs_the_apple_tool_tests_and_each_half_of_the_smoke_in_a_job_of_its_own(tmp_path):
    """The Acme smoke took 15 of the macOS job's 22 minutes. Its two halves share the build up to the frozen round, then one runs
    tools/finish.sh and the other every section after it, so they run side by side. That holds because finish.sh works on its own
    copy of the pack, taken before any later section writes into it (names does), and nothing later reads that copy or its logs."""
    import os
    text = ci_text()
    job = text[text.index("  macos-suite:"):text.index("\n  brand-creator:\n")]
    assert re.findall(r"- part: ([\w-]+)", job) == ["pytest", "smoke-finish", "smoke-rest"]
    assert re.findall(r"^ +smoke: (\w+)$", job, re.M) == ["finish", "rest"]
    assert "fail-fast: false" in job and "ACME_SMOKE_PART: ${{ matrix.smoke }}" in job
    assert "if: matrix.part == 'pytest'" in job and "if: matrix.part != 'pytest'" in job       # each job runs its part only
    acme = (ROOT / "tests" / "smoke" / "acme.sh").read_text()
    shared, tail = acme.split('\nif [ "$PART" != rest ]; then\n')
    finish, rest = tail.split('\nfi\nif [ "$PART" = finish ]; then\n')
    code = [ln for ln in shared.splitlines() if ln.strip() and not ln.startswith("#")]
    assert code[-4:] == ['step "freeze the approved round, then check again"', '"${BC[@]}" freeze r1 --name approved-board --project "$P"',
                         'expect_file "$P/history/MANIFEST.sha256"', '"${BC[@]}" check --project "$P"'], code[-4:]  # the shared build ends at the frozen round
    steps = re.findall(r'^step "([^"]+)', finish, re.M)
    assert len(steps) == 1 and steps[0].startswith("tools/finish.sh from the template"), steps                       # one half is that section alone
    assert re.match(r"  printf '\\nSMOKE PASSED \(part finish[^\n]*\n  exit 0\nfi\n", rest)                      # and it ends there
    assert len(re.findall(r'^step "', rest, re.M)) >= 10                                                            # the other half is every later section
    r = subprocess.run(["bash", str(ROOT / "tests" / "smoke" / "acme.sh")], capture_output=True, text=True,
                       env={**os.environ, "BRAND_CREATOR_DATA": str(tmp_path), "ACME_SMOKE_PART": "half"})
    assert r.returncode == 2 and "use all, finish or rest" in r.stderr, r.stdout + r.stderr                       # a part it does not know runs nothing


def test_the_container_stops_a_hung_suite_at_its_deadline_and_still_checks_the_log():
    run = (DOCKER / "run.sh").read_text()
    inside = (DOCKER / "in-container.sh").read_text()
    assert "--init --ipc=host" in run                                                          # a real PID 1 that passes signals on; Chromium's shared memory
    for env in ("BRAND_CREATOR_TEST_PARTS", "BRAND_CREATOR_SUITE_MINUTES"):
        assert f'-e {env}="${{{env}' in run, env
    assert 'timeout --signal=TERM --kill-after=60 "${minutes}m" tests/run-all.sh --smoke' in inside
    assert inside.index("timeout --signal=TERM") < inside.index('python3 tests/docker/verify_log.py "$LOG" "$rc"')   # the verifier runs after the deadline too
    assert "--durations=25" in inside and "--junitxml=/out/pytest-junit.xml" in inside


def test_every_test_has_a_time_limit_and_the_whole_chain_tests_have_a_longer_one(request):
    """pytest-timeout comes from tests/requirements.txt; conftest gives every test DEFAULT_TIMEOUT unless it carries its own, so a hung test fails by name."""
    import conftest
    import test_finish_chain
    assert request.config.pluginmanager.hasplugin("timeout"), "run the tests with tests/requirements.txt (uv run --no-project --with-requirements tests/requirements.txt ...)"
    assert request.node.get_closest_marker("timeout").args == (conftest.DEFAULT_TIMEOUT,) == (300,)
    assert any(m.name == "timeout" and m.args == (1200,) for m in test_finish_chain.pytestmark)
    assert "pytest-timeout==" in (ROOT / "tests" / "requirements.in").read_text()


def test_pytest_hands_waiting_tests_to_idle_workers_everywhere_it_runs_in_parallel():
    """With the default `load` scheduling a block of long tests (test_finish_chain) sat queued on one worker while the others were idle:
    25.7 min on 8 workers; `worksteal` moves waiting tests to idle workers: 11.0 min, the same 1880 tests."""
    assert "--dist worksteal" in (ROOT / "tests" / "run-all.sh").read_text()
    macos = [ln for ln in ci_text().splitlines() if "-m \"requires_macos or requires_actool\"" in ln]
    assert macos and all("--dist worksteal" in ln for ln in macos), macos


def test_the_verifier_tests_ignore_the_part_their_own_ci_job_runs(tmp_path, monkeypatch):
    """The CI job that runs pytest sets BRAND_CREATOR_TEST_PARTS=pytest, and pytest's workers inherit it. The logs these tests write by
    hand are whole runs, so verify() must not pass that on: with it, a failing node:test summary read as a pytest-only run and passed."""
    monkeypatch.setenv("BRAND_CREATOR_TEST_PARTS", "pytest")
    r = verify(tmp_path, GOOD.replace("ℹ fail 0", "ℹ fail 2"))
    assert r.returncode == 1 and "node:test: fail=2" in r.stderr, r.stdout + r.stderr


@pytest.mark.parametrize("parts", ["pytest, node", " node ,pytest", "pytest,,node"])
def test_run_all_and_the_verifier_read_a_list_with_spaces_or_empty_items_the_same_way(tmp_path, parts):
    """Spaces around a name and empty items are ignored by both, so neither silently drops a part the other runs (0.4.2's run-all
    validated 'pytest, node' and then ran pytest alone)."""
    import os
    text = GOOD
    r = verify(tmp_path, text, env={"BRAND_CREATOR_TEST_PARTS": parts})
    assert r.returncode == 0 and ("LINUX RUN OK (pytest, node)" in r.stdout or "LINUX RUN OK (node, pytest)" in r.stdout), r.stdout + r.stderr
    stub = tmp_path / "bin"
    stub.mkdir()
    for tool in ("uv", "node"):
        (stub / tool).write_text(f"#!/bin/sh\necho STUB {tool} ran\n")
        (stub / tool).chmod(0o755)
    r = subprocess.run(["bash", str(ROOT / "tests" / "run-all.sh")], capture_output=True, text=True,
                       env={**os.environ, "PATH": f"{stub}:{os.environ['PATH']}", "BRAND_CREATOR_TEST_PARTS": parts})
    assert r.returncode == 0 and "STUB uv ran" in r.stdout and "STUB node ran" in r.stdout, r.stdout + r.stderr
