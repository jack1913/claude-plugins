#!/usr/bin/env bash
# Run the whole suite: pytest, node:test and (with --smoke) the Acme end-to-end path and the Quick-tier smoke (no Apple tools, no git).
#
#   BRAND_CREATOR_DATA=<set-up data dir> BRAND_CREATOR_DENYLIST=<denylist.json> tests/run-all.sh [--smoke]
#
# Tests that need the set-up data directory (npm packages, Chromium) or the anonymisation denylist are skipped with a
# loud "NOT VERIFIED" banner when those are missing. A skip is not a pass. BRAND_CREATOR_REQUIRE_ALL=1 (used in CI)
# turns every such skip into a failure.
set -euo pipefail
cd "$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.."
smoke=0
[ "${1:-}" = "--smoke" ] && smoke=1
rc=0
# pytest-xdist spreads the tests over worker processes (BRAND_CREATOR_TEST_WORKERS, default 8; 0 runs them in one process)
uv run --no-project --with-requirements tests/requirements.txt python -m pytest tests -q -n "${BRAND_CREATOR_TEST_WORKERS:-8}" || rc=1
node --test "tests/node/*.test.mjs" || rc=1
if [ "$smoke" = 1 ]; then
  bash tests/smoke/acme.sh || rc=1
  # the Quick tier on a machine without the Apple tools and without git (its own project folder: QUICK_SMOKE_DIR)
  bash tests/smoke/quick.sh || rc=1
fi
exit "$rc"
