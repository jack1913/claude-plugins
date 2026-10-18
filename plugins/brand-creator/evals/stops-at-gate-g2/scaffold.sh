#!/usr/bin/env bash
# Scaffold for the "stops-at-gate-g2" eval: runs in the empty workspace of one run (`claude plugin eval . --scaffold`).
set -euo pipefail
. "$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../_shared/fixture.sh"
fx_r1_shown
