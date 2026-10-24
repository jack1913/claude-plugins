#!/usr/bin/env bash
# Run the whole suite: pytest, node:test and (with --smoke) the Acme end-to-end path and the Quick-tier smoke (no Apple tools, no git).
#
#   BRAND_CREATOR_DATA=<set-up data dir> BRAND_CREATOR_DENYLIST=<denylist.json> tests/run-all.sh [--smoke]
#
# Tests that need the set-up data directory (npm packages, Chromium) or the anonymisation denylist are skipped with a
# loud "NOT VERIFIED" banner when those are missing. A skip is not a pass. BRAND_CREATOR_REQUIRE_ALL=1 (used in CI)
# turns every such skip into a failure.
# BRAND_CREATOR_TEST_PARTS=<parts> runs only those parts, a comma-separated list of pytest, node and smoke (default: all
# three; smoke still needs --smoke). CI runs each part in a job of its own. A part name it does not know, or a selection
# that runs nothing, is a usage error (exit 2), never an empty pass.
set -euo pipefail
cd "$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)/.."
smoke=0
[ "${1:-}" = "--smoke" ] && smoke=1
parts=","   # the parts asked for, as ",name,name,": spaces around a name and empty items are ignored (tests/docker/verify_log.py reads it the same way)
IFS="," read -r -a items <<< "${BRAND_CREATOR_TEST_PARTS:-pytest,node,smoke}"
for p in ${items[@]+"${items[@]}"}; do
  p="${p//[[:space:]]/}"
  [ -z "$p" ] && continue
  case "$p" in pytest|node|smoke) parts+="$p," ;; *) echo "run-all.sh: unknown part '$p' in BRAND_CREATOR_TEST_PARTS (pytest, node, smoke)" >&2; exit 2 ;; esac
done
has() { case "$parts" in *",$1,"*) return 0 ;; *) return 1 ;; esac; }
rc=0
ran=0
if has pytest; then
  # pytest-xdist spreads the tests over worker processes (BRAND_CREATOR_TEST_WORKERS, default 8; 0 runs them in one process);
  # worksteal moves waiting tests to idle workers, so a block of long tests never ends up queued on one worker
  uv run --no-project --with-requirements tests/requirements.txt python -m pytest tests -q -n "${BRAND_CREATOR_TEST_WORKERS:-8}" --dist worksteal || rc=1
  ran=1
fi
if has node; then
  node --test --test-timeout=180000 "tests/node/*.test.mjs" || rc=1   # a test still running after 3 minutes is hung: it fails by name
  ran=1
fi
if [ "$smoke" = 1 ] && has smoke; then
  bash tests/smoke/acme.sh || rc=1
  # the Quick tier on a machine without the Apple tools and without git (its own project folder: QUICK_SMOKE_DIR)
  bash tests/smoke/quick.sh || rc=1
  ran=1
fi
if [ "$ran" = 0 ]; then
  echo "run-all.sh: BRAND_CREATOR_TEST_PARTS=${BRAND_CREATOR_TEST_PARTS:-} runs nothing (smoke needs --smoke)" >&2
  exit 2
fi
exit "$rc"
