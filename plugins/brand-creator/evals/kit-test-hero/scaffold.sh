#!/usr/bin/env bash
# Scaffold for the "kit-test-hero" eval: runs in the empty workspace of one run (`claude plugin eval . --scaffold`). Offline: it copies files only.
set -euo pipefail
. "$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../_shared/fixture.sh"
fx_kit
