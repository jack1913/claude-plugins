#!/usr/bin/env bash
# Run the whole suite: pytest, node:test and (with --smoke) the Acme end-to-end path and the Quick-tier smoke (no Apple tools, no git).
#
#   BRAND_CREATOR_DATA=<set-up data dir> BRAND_CREATOR_DENYLIST=<denylist.json> tests/run-all.sh [--smoke | --fast]
#
# --fast is the daily run, a minute or two: pytest leaves out every test tests/durations.json measured at a second or more (it says how many),
# node:test runs whole, and there is no smoke. A release runs everything: no --fast, with --smoke.
# BRAND_CREATOR_TEST_FILES="tests/test_a.py tests/test_b.py" runs only those pytest files (the tests a change touches).
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
fast=0
for a in "$@"; do
  case "$a" in --smoke) smoke=1 ;; --fast) fast=1 ;; *) echo "run-all.sh: unknown option '$a' (--smoke, --fast)" >&2; exit 2 ;; esac
done
if [ "$fast" = 1 ] && [ "$smoke" = 1 ]; then echo "run-all.sh: --fast runs no smoke: a release runs the smoke, with every test" >&2; exit 2; fi
[ "$fast" = 1 ] && export BRAND_CREATOR_FAST=1
files=()
if [ -n "${BRAND_CREATOR_TEST_FILES:-}" ]; then
  read -r -a files <<< "$BRAND_CREATOR_TEST_FILES"
  for f in "${files[@]}"; do
    case "$f" in tests/test_*.py) [ -f "$f" ] || { echo "run-all.sh: $f in BRAND_CREATOR_TEST_FILES is not a test file" >&2; exit 2; } ;;
                 *) echo "run-all.sh: $f in BRAND_CREATOR_TEST_FILES is not a test file (tests/test_<name>.py)" >&2; exit 2 ;; esac
  done
fi
parts=","   # the parts asked for, as ",name,name,": spaces around a name and empty items are ignored (tests/docker/verify_log.py reads it the same way)
IFS="," read -r -a items <<< "${BRAND_CREATOR_TEST_PARTS:-pytest,node,smoke}"
for p in ${items[@]+"${items[@]}"}; do
  p="${p//[[:space:]]/}"
  [ -z "$p" ] && continue
  case "$p" in pytest|node|smoke) parts+="$p," ;; *) echo "run-all.sh: unknown part '$p' in BRAND_CREATOR_TEST_PARTS (pytest, node, smoke)" >&2; exit 2 ;; esac
done
# The paid-service fail-safe (tests/conftest.py): unless BRAND_CREATOR_PAID=1, no part of the run sees an OpenRouter key or the
# design-canvas host that generates images with it, so nothing here can spend money by accident.
if [ "${BRAND_CREATOR_PAID:-}" != "1" ]; then
  while IFS= read -r v; do unset "$v"; done < <(compgen -e | grep -E '^(OPENROUTER_|USE_LLM_DESIGN_)' || true)
fi
has() { case "$parts" in *",$1,"*) return 0 ;; *) return 1 ;; esac; }
rc=0
ran=0
if has pytest; then
  # pytest-xdist spreads the tests over worker processes (BRAND_CREATOR_TEST_WORKERS, default auto: one per CPU core; 0 runs them in one process);
  # worksteal moves waiting tests to idle workers, so a block of long tests never ends up queued on one worker
  uv run --no-project --with-requirements tests/requirements.txt python -m pytest ${files[@]+"${files[@]}"} $([ ${#files[@]} = 0 ] && echo tests) -q -n "${BRAND_CREATOR_TEST_WORKERS:-auto}" --dist worksteal || rc=1
  ran=1
fi
if has node; then
  if [ "$fast" = 1 ]; then   # the node:test files under a second a test (tests/tiering.py): the others drive Chromium
    nodefiles=()
    while IFS= read -r f; do [ -n "$f" ] && nodefiles+=("$f"); done < <(python3 tests/tiering.py fast-node-files)   # no mapfile: macOS ships bash 3.2
    all=(tests/node/*.test.mjs)
    skipped=()
    for f in "${all[@]}"; do case " ${nodefiles[*]} " in *" $f "*) ;; *) skipped+=("${f##*/}") ;; esac; done
    echo "FAST TIER: node runs ${#nodefiles[@]} of ${#all[@]} files; not run: ${skipped[*]:-none} (tests/durations.json; a release runs them all)"
    [ ${#nodefiles[@]} = 0 ] || node --test --test-timeout=180000 ${nodefiles[@]+"${nodefiles[@]}"} || rc=1
  else
    node --test --test-timeout=180000 "tests/node/*.test.mjs" || rc=1   # a test still running after 3 minutes is hung: it fails by name
  fi
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
