"""The paid-service fail-safe (tests/conftest.py, tests/run-all.sh): nothing in the default run can spend money on OpenRouter."""
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PROBE = ROOT / "tests" / "paid_probe.py"   # not test_*.py: collected only when named, by the test below


@pytest.mark.costs_money
def test_paid_probe_marked():
    """Only collected with BRAND_CREATOR_PAID=1; it spends nothing itself (the outer tests only collect it)."""


def _pytest(*args, target=None, **env):
    e = {k: v for k, v in os.environ.items() if k not in ("BRAND_CREATOR_PAID", "PYTEST_XDIST_WORKER")}
    e.update(env)
    return subprocess.run([sys.executable, "-m", "pytest", "-p", "no:cacheprovider", "-n", "0", *args, str(target or ROOT / "tests" / "test_paid_guard.py")],
                          cwd=ROOT, capture_output=True, text=True, env=e, timeout=120)


def test_the_default_run_sees_no_key_and_cannot_reach_openrouter():
    r = _pytest("-q", target=PROBE, OPENROUTER_API_KEY="sk-or-fake", USE_LLM_DESIGN_HOST="http://127.0.0.1:1")
    assert r.returncode == 0 and "1 passed" in r.stdout, r.stdout + r.stderr


def test_a_costs_money_test_runs_only_with_brand_creator_paid():
    off = _pytest("--collect-only", "-q", "-m", "costs_money")
    assert "test_paid_probe_marked" not in off.stdout and "deselected" in off.stdout, off.stdout
    on = _pytest("--collect-only", "-q", "-m", "costs_money", BRAND_CREATOR_PAID="1")
    assert "test_paid_probe_marked" in on.stdout, on.stdout


def test_run_all_takes_the_keys_out_of_the_node_and_smoke_parts():
    sh = (ROOT / "tests" / "run-all.sh").read_text()
    guard = sh.index('if [ "${BRAND_CREATOR_PAID:-}" != "1" ]; then')
    assert "OPENROUTER_|USE_LLM_DESIGN_" in sh[guard:guard + 300] and guard < sh.index("if has pytest; then")
