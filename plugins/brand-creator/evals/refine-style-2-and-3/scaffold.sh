#!/usr/bin/env bash
# Scaffold for the "refine-style-2-and-3" eval: runs in the empty workspace of one run (`claude plugin eval . --scaffold`).
set -euo pipefail
. "$(cd -P "$(dirname "${BASH_SOURCE[0]}")" && pwd)/../_shared/fixture.sh"
fx_refine
