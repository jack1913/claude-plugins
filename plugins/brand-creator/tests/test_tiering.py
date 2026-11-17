"""The fast tier and the order of a run: tests/tiering.py, tests/durations.json, `tests/run-all.sh --fast` and BRAND_CREATOR_TEST_FILES."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tiering  # noqa: E402
from helpers import ROOT  # noqa: E402

JUNIT = """<?xml version="1.0" encoding="utf-8"?><testsuites><testsuite name="pytest">
<testcase classname="tests.test_kit" name="test_a" time="2.5"/>
<testcase classname="tests.test_kit" name="test_b" time="0.2"/>
<testcase classname="tests.test_x.TestC" name="test_d[1]" time="1.0"/>
<testcase classname="tests.test_kit" name="test_e" time="3.0"><skipped message="NOT VERIFIED"/></testcase>
</testsuite></testsuites>"""


def test_a_node_id_is_keyed_by_its_file_and_name():
    assert tiering.key_of("tests/test_kit.py::test_a[x]") == "test_kit.py::test_a[x]"
    assert tiering.key_of("test_kit.py::TestA::test_b") == "test_kit.py::TestA::test_b"


def test_durations_from_a_junit_file_keep_the_tests_of_a_second_or_more_that_ran(tmp_path):
    xml = tmp_path / "run.xml"
    xml.write_text(JUNIT, encoding="utf-8")
    assert tiering.durations_from_junit([xml]) == {"test_kit.py::test_a": 2.5, "test_x.py::TestC::test_d[1]": 1.0}   # a skip measured nothing


def test_the_fast_tier_leaves_out_only_the_tests_measured_at_a_second_or_more():
    d = {"test_kit.py::test_a": 2.5}
    assert tiering.is_slow("tests/test_kit.py::test_a", d) and not tiering.is_slow("tests/test_kit.py::test_b", d)   # a test never measured runs


def test_the_committed_durations_name_test_functions_that_exist():
    doc = json.loads((ROOT / "tests" / "durations.json").read_text(encoding="utf-8"))
    assert doc["limit"] == tiering.LIMIT and doc["tests"] and all(v >= tiering.LIMIT for v in doc["tests"].values())
    missing = []
    for key in doc["tests"]:
        file, name = key.split("::")[0], re.sub(r"\[.*$", "", key.split("::")[-1])
        f = ROOT / "tests" / file
        if not f.is_file() or not re.search(rf"^\s*(async )?def {re.escape(name)}\(", f.read_text(encoding="utf-8"), re.M):
            missing.append(key)
    assert not missing, f"tests/durations.json names tests that no longer exist: run tests/tools/durations.py again ({missing[:5]})"


def test_the_fast_tier_deselects_a_slow_test_and_says_so():
    env = {**os.environ, "BRAND_CREATOR_FAST": "1"}
    r = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", "tests/test_finish_chain.py"], cwd=ROOT, capture_output=True, text=True, env=env)
    assert re.search(r"\d+ deselected", r.stdout) and "FAST TIER:" in r.stdout and "were not run" in r.stdout, r.stdout + r.stderr
    assert "test_the_standard_chain_runs_profiles_print_posts_book_and_press_kit_in_order_through_to_check" not in r.stdout


def run_all(*args, **env):
    return subprocess.run(["bash", str(ROOT / "tests" / "run-all.sh"), *args], capture_output=True, text=True, env={**os.environ, **env})


def test_run_all_refuses_fast_with_the_smoke():
    r = run_all("--fast", "--smoke")
    assert r.returncode == 2 and "--fast runs no smoke" in r.stderr, r.stdout + r.stderr


def test_run_all_refuses_a_test_file_that_does_not_exist():
    r = run_all(BRAND_CREATOR_TEST_FILES="tests/test_kit.py tests/test_nope.py", BRAND_CREATOR_TEST_PARTS="pytest")
    assert r.returncode == 2 and "tests/test_nope.py" in r.stderr and "not a test file" in r.stderr, r.stdout + r.stderr


NODE_JUNIT = """<?xml version="1.0" encoding="utf-8"?><testsuites>
<testcase name="a" time="4.0" classname="test" file="x/tests/node/capture.test.mjs"/>
<testcase name="b" time="2.0" classname="test" file="x/tests/node/capture.test.mjs"/>
<testcase name="c" time="0.2" classname="test" file="x/tests/node/common.test.mjs"/>
<testcase name="d" time="0.4" classname="test" file="x/tests/node/common.test.mjs"/>
</testsuites>"""


def test_node_files_from_a_junit_file_are_counted_and_timed(tmp_path):
    xml = tmp_path / "node.xml"
    xml.write_text(NODE_JUNIT, encoding="utf-8")
    assert tiering.node_files_from_junit([xml]) == {"capture.test.mjs": {"tests": 2, "seconds": 6.0}, "common.test.mjs": {"tests": 2, "seconds": 0.6}}


def test_the_fast_tier_runs_the_node_files_under_a_second_a_test_and_any_file_never_measured(tmp_path):
    node = {"capture.test.mjs": {"tests": 2, "seconds": 6.0}, "common.test.mjs": {"tests": 2, "seconds": 0.6}}
    for f in ("capture.test.mjs", "common.test.mjs", "new.test.mjs"):
        (tmp_path / f).write_text("", encoding="utf-8")
    assert tiering.fast_node_files(tmp_path, node) == ["common.test.mjs", "new.test.mjs"]


def test_the_committed_durations_time_every_node_file_and_leave_some_fast():
    doc = json.loads((ROOT / "tests" / "durations.json").read_text(encoding="utf-8"))
    files = sorted(p.name for p in (ROOT / "tests" / "node").glob("*.test.mjs"))
    assert sorted(doc["node"]) == files
    fast = tiering.fast_node_files(ROOT / "tests" / "node", doc["node"])
    assert "workflows.test.mjs" in fast and "capture.test.mjs" not in fast


def test_run_all_fast_runs_only_the_fast_node_files_and_says_so():
    r = run_all("--fast", BRAND_CREATOR_TEST_PARTS="node")
    assert r.returncode == 0, r.stdout + r.stderr
    assert re.search(r"FAST TIER: node runs \d+ of \d+ files", r.stdout) and "capture.test.mjs" in r.stdout, r.stdout


# ---------------------------------------------------------------- the shares of the release run on GitHub (one job each)

@pytest.mark.parametrize("count", [1, 2, 3, 5])
def test_the_shares_hold_every_test_file_once_and_differ_by_no_more_than_the_longest_file(count):
    names = sorted(p.name for p in (ROOT / "tests").glob("test_*.py"))
    durations = tiering.load()
    seconds = tiering.file_seconds(names, durations)
    shares = [tiering.shard(names, durations, i, count) for i in range(1, count + 1)]
    assert sorted(f for share in shares for f in share) == names                                  # every file, in exactly one share
    totals = [sum(seconds[f] for f in share) for share in shares]
    assert max(totals) - min(totals) <= max(seconds.values()), totals
    assert shares == [tiering.shard(names, durations, i, count) for i in range(1, count + 1)]    # the same shares on every machine and run


def test_a_file_never_measured_still_lands_in_a_share_and_a_share_outside_the_count_is_refused():
    assert tiering.shard(["test_new.py", "test_old.py"], {"test_old.py::test_a": 60.0}, 1, 2) == ["test_old.py"]
    assert tiering.shard(["test_new.py", "test_old.py"], {"test_old.py::test_a": 60.0}, 2, 2) == ["test_new.py"]
    for index, count in ((0, 3), (4, 3), (1, 0)):
        with pytest.raises(ValueError, match="whole number from 1 to the count"):
            tiering.shard(["test_a.py"], {}, index, count)


def test_the_shard_command_prints_test_files_run_all_takes_and_refuses_anything_else():
    script = str(ROOT / "tests" / "tiering.py")
    r = subprocess.run([sys.executable, script, "shard", "2", "3"], capture_output=True, text=True)
    files = r.stdout.split()
    assert r.returncode == 0 and files and all(re.fullmatch(r"tests/test_\w+\.py", f) and (ROOT / f).is_file() for f in files), r.stdout
    for bad in (["shard", "4", "3"], ["shard", "0", "3"], ["shard", "a", "3"], ["shard", "1"], ["shards", "1", "3"], []):
        r = subprocess.run([sys.executable, script, *bad], capture_output=True, text=True)
        assert r.returncode == 2 and "usage: tiering.py" in r.stderr and not r.stdout, (bad, r.stdout, r.stderr)
