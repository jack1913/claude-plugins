---
paths:
  - "maintenance/apicheck/*.py"
  - "maintenance/check-apis.py"
description: "apicheck and check-apis.py import only the Python 3 standard library"
---

# apicheck imports only the standard library

Code in `maintenance/check-apis.py` and `maintenance/apicheck/` imports only the Python 3 standard library (design spec §6: "Python 3 stdlib only").

## The constraint

The repo has no requirements.txt, pyproject.toml or Pipfile, and no gate checks imports. A third-party import passes the tests on a machine that already has the package installed, and fails with ImportError everywhere else. Network code stays on `urllib`, behind `Fetcher`'s `opener=` seam (`maintenance/apicheck/fetch.py:29-34`). The tests inject their fake opener through that seam.

Every import today is standard library or package-relative:

    rg -N --no-filename -o '^\s*(from \S+ import|import \S+)' maintenance/check-apis.py maintenance/apicheck/ | sed 's/^ *//' | sort -u
    -> __future__, dataclasses, pathlib, argparse, hashlib, json, os, re, sys, urllib.error, urllib.parse, urllib.request, plus relative imports (. / .apple / .fetch / .manifest / apicheck.cli)

    fd -H -t f 'requirements.*\.txt|pyproject\.toml|Pipfile|setup\.py|setup\.cfg' . | wc -l   -> 0
