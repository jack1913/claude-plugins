#!/usr/bin/env bash
# Runs INSIDE the Linux image (tests/docker/Dockerfile), started by tests/docker/run.sh. Not meant to be run on a developer machine.
#
# 1. copies the plugin from the read-only mount /src to /work/plugin (no .git, no caches: the copy is what a user would install)
# 2. brand-creator prereq --for full, then `brand-creator setup --yes` into a data directory inside the container (npm ci, Chromium)
# 3. tests/run-all.sh --smoke WITHOUT BRAND_CREATOR_REQUIRE_ALL (pytest, node:test, the Acme smoke on the paths that apply off macOS)
# 4. tests/docker/verify_log.py reads the log: every skip must be an expected one (macOS-only tests), anything else is a failure
set -euo pipefail

SRC=/src
PLUGIN=/work/plugin
DATA="${BRAND_CREATOR_DATA:-/work/data}"
LOG=/work/run-all.log

step() { printf '\n==== %s\n' "$*"; }

step "container"
uname -srm
sed -n 's/^PRETTY_NAME=//p' /etc/os-release
printf 'user %s (uid %s)\n' "$(id -un)" "$(id -u)"
for t in python3 uv node npm resvg magick gs pdfinfo pdftoppm pdftotext rg potrace git; do
  if command -v "$t" >/dev/null; then printf '%-10s %s\n' "$t" "$("$t" --version 2>&1 | head -n 1 || true)"; else printf '%-10s MISSING\n' "$t"; fi
done
for t in sips iconutil actool xcrun xdg-open open; do
  if command -v "$t" >/dev/null; then echo "unexpected: $t exists in the Linux image" >&2; exit 1; fi
done
printf 'fonts      %s families\n' "$(fc-list : family | sort -u | wc -l | tr -d ' ')"

step "copy the plugin"
rm -rf "$PLUGIN"
mkdir -p "$PLUGIN"
tar -C "$SRC" --exclude=./.git --exclude=node_modules --exclude=__pycache__ --exclude=.pytest_cache --exclude=./evals/results -cf - . | tar -C "$PLUGIN" -xf -
cd "$PLUGIN"

step "prereq --for full (Apple tools are expected MISSING off macOS: exit 3 by design)"
set +e
bin/brand-creator --data "$DATA" prereq --for full
rc=$?
set -e
[ "$rc" = 0 ] || [ "$rc" = 3 ] || { echo "prereq exited $rc" >&2; exit 1; }
python3 - "$PLUGIN" "$DATA" <<'PY'
import json, subprocess, sys
r = subprocess.run([sys.argv[1] + "/bin/brand-creator", "--data", sys.argv[2], "prereq", "--for", "full", "--json"], capture_output=True, text=True)
d = json.loads(r.stdout)
missing = sorted(i["id"] for i in d["items"] if i["status"] == "MISSING")
assert d["os"] == "linux", d["os"]
assert missing == ["chromium", "xcode"], f"only chromium (before setup) and xcode may be MISSING on Linux, got {missing}"
print("   ok: MISSING before setup =", missing)
PY

step "setup --yes (npm ci, Chromium headless shell into the data directory, uv environments, browser self-test)"
bin/brand-creator --data "$DATA" setup --yes
python3 - "$PLUGIN" "$DATA" <<'PY'
import json, subprocess, sys
r = subprocess.run([sys.argv[1] + "/bin/brand-creator", "--data", sys.argv[2], "prereq", "--for", "full", "--json"], capture_output=True, text=True)
missing = sorted(i["id"] for i in json.loads(r.stdout)["items"] if i["status"] == "MISSING")
assert missing == ["xcode"], f"after setup only xcode may be MISSING on Linux, got {missing}"
print("   ok: MISSING after setup =", missing)
PY

step "tests/run-all.sh --smoke (no BRAND_CREATOR_REQUIRE_ALL: macOS-only tests must report NOT VERIFIED)"
export BRAND_CREATOR_DATA="$DATA"
export BRAND_CREATOR_TEST_WORKERS="${BRAND_CREATOR_TEST_WORKERS:-4}"
export ACME_SMOKE_DIR=/work/acme-smoke
export PYTEST_ADDOPTS="-rs ${PYTEST_ADDOPTS:-}"
unset BRAND_CREATOR_REQUIRE_ALL
set +e
tests/run-all.sh --smoke 2>&1 | tee "$LOG"
rc=${PIPESTATUS[0]}
set -e
echo "tests/run-all.sh exit code: $rc"

step "verify the log"
python3 tests/docker/verify_log.py "$LOG" "$rc"
