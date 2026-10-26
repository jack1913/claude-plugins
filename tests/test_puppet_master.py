"""Run the puppet-master helper's Node test suite (tests/puppet_master/*.test.mjs).

The helper is a stdlib-only Node script, so its tests are `node:test` files; this
wrapper lets `python3 -m pytest -q` cover them. A missing `node` is a failure, never
a skip: a green run must mean the suite ran.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_node_suite_passes():
    node = shutil.which("node")
    if node is None:
        pytest.fail("node >= 20 is required for tests/puppet_master")
    files = sorted(str(p) for p in (REPO_ROOT / "tests" / "puppet_master").glob("*.test.mjs"))
    assert files, "no tests/puppet_master/*.test.mjs found"
    result = subprocess.run(
        [node, "--test", *files],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == 0, result.stdout + result.stderr
