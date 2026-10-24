#!/usr/bin/env bash
# Build the Linux image and run the plugin's whole validation inside it (setup, pytest, node:test, the Acme smoke).
#
#   tests/docker/run.sh [--no-build]
#
# The plugin and the repository workflow are mounted read-only and copied inside the container, into the monorepo layout
# (/work/repo/plugins/brand-creator, /work/repo/.github/workflows, /work/repo/.claude-plugin/marketplace.json); nothing the run writes touches this checkout.
# Environment (all optional):
#   BRAND_CREATOR_DOCKER_DATA=<host dir>   keep the data directory (npm packages, Chromium) on the host between runs
#                                          (default: inside the container, so every run tests `brand-creator setup` from scratch)
#   BRAND_CREATOR_DENYLIST=<host file>     the anonymisation denylist (never shipped); mounted read-only so test_anonymisation runs
#   BRAND_CREATOR_TEST_WORKERS=<n>         pytest-xdist workers inside the container (default 4)
#   BRAND_CREATOR_TEST_PARTS=<parts>       run only these parts: pytest, node, smoke, comma-separated (default all; CI runs one per job)
#   BRAND_CREATOR_SUITE_MINUTES=<m>        the deadline of the suite inside the container (default 45): past it the suite is stopped,
#                                          and the log is still verified, so a hung run ends in a failure that says so
#   BRAND_CREATOR_TEST_OUT=<host dir>      the run log and pytest's JUnit file go to a new linux-run.* folder inside it (default: kept in the container only)
#   BRAND_CREATOR_DOCKER_PLATFORM=<p>      for example linux/amd64 (default: the machine's own architecture)
# This script does not set BRAND_CREATOR_REQUIRE_ALL: off macOS some tests are NOT VERIFIED by design (Apple tools), the log verifier
# (tests/docker/verify_log.py) accepts exactly those and fails on any other skip or failure. Exit 0 only when the whole run is OK.
set -euo pipefail

HERE="$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd -P "$HERE/../.." && pwd)"                 # plugins/brand-creator
WORKFLOW="$ROOT/../../.github/workflows/brand-creator.yml"   # tests/test_docker_ci.py reads it from the monorepo root
MARKET="$ROOT/../../.claude-plugin/marketplace.json"         # tests/test_static.py checks the plugin is listed there
[ -f "$MARKET" ] || { echo "run.sh: $MARKET not found (run from the claude-plugins monorepo)" >&2; exit 2; }
[ -f "$WORKFLOW" ] || { echo "run.sh: $WORKFLOW not found: run this from the claude-plugins monorepo (plugins/brand-creator)" >&2; exit 2; }
WORKFLOW="$(cd -P "$(dirname "$WORKFLOW")" && pwd)/brand-creator.yml"
IMAGE="${BRAND_CREATOR_DOCKER_IMAGE:-brand-creator-linux-test:debian13}"

command -v docker >/dev/null || { echo "run.sh: docker is not installed or not on PATH" >&2; exit 3; }
docker info >/dev/null 2>&1 || { echo "run.sh: the docker daemon is not reachable (start Docker Desktop or OrbStack)" >&2; exit 3; }

platform=()
[ -n "${BRAND_CREATOR_DOCKER_PLATFORM:-}" ] && platform=(--platform "$BRAND_CREATOR_DOCKER_PLATFORM")

if [ "${1:-}" != "--no-build" ]; then
  docker build ${platform[@]+"${platform[@]}"} -t "$IMAGE" "$HERE"
fi

# --init: a real PID 1 that passes signals on and reaps orphans; --ipc=host: Chromium needs more shared memory than Docker's default (Playwright's Docker guidance)
args=(--rm --init --ipc=host ${platform[@]+"${platform[@]}"} -v "$ROOT":/src:ro -v "$WORKFLOW":/src-ci/brand-creator.yml:ro -v "$MARKET":/src-ci/marketplace.json:ro
      -e BRAND_CREATOR_TEST_WORKERS="${BRAND_CREATOR_TEST_WORKERS:-4}" -e BRAND_CREATOR_TEST_PARTS="${BRAND_CREATOR_TEST_PARTS:-}"
      -e BRAND_CREATOR_SUITE_MINUTES="${BRAND_CREATOR_SUITE_MINUTES:-45}")
if [ -n "${BRAND_CREATOR_TEST_OUT:-}" ]; then
  mkdir -p "$BRAND_CREATOR_TEST_OUT"
  out="$(mktemp -d "$(cd -P "$BRAND_CREATOR_TEST_OUT" && pwd)/linux-run.XXXXXX")"   # a fresh folder of its own, inside the one given
  chmod a+rwx "$out"   # only it is opened to the container's user (uid 1000), who is not the host's (the CI runner is uid 1001)
  args+=(-v "$out":/out)
  echo "run.sh: the run log and the JUnit file go to $out"
fi
if [ -n "${BRAND_CREATOR_DOCKER_DATA:-}" ]; then
  mkdir -p "$BRAND_CREATOR_DOCKER_DATA"
  args+=(-v "$(cd -P "$BRAND_CREATOR_DOCKER_DATA" && pwd)":/work/data)
fi
if [ -n "${BRAND_CREATOR_DENYLIST:-}" ]; then
  [ -f "$BRAND_CREATOR_DENYLIST" ] || { echo "run.sh: BRAND_CREATOR_DENYLIST is not a file: $BRAND_CREATOR_DENYLIST" >&2; exit 2; }
  args+=(-v "$BRAND_CREATOR_DENYLIST":/run/denylist.json:ro -e BRAND_CREATOR_DENYLIST=/run/denylist.json)
fi
exec docker run "${args[@]}" "$IMAGE" bash /src/tests/docker/in-container.sh
