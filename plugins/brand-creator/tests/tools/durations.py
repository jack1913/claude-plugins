#!/usr/bin/env python3
"""Write tests/durations.json from the JUnit XML of a full run, so that `tests/run-all.sh --fast` knows the slow tests.

    uv run --no-project --with-requirements tests/requirements.txt python -m pytest tests -n auto --dist worksteal --junitxml=<pytest.xml>
    node --test --test-reporter=junit --test-reporter-destination=<node.xml> "tests/node/*.test.mjs"
    python3 tests/tools/durations.py <pytest.xml> <node.xml>

Run it again when tests are added or get slower: a test missing from the file is never left out of the fast tier, so a stale file only makes the fast tier slower."""
from __future__ import annotations

import json
import platform
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tiering  # noqa: E402


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__, file=sys.stderr)
        return 2
    paths = [Path(a) for a in argv]
    tests, node = tiering.durations_from_junit(paths), tiering.node_files_from_junit(paths)
    doc = {"measured": f"{date.today().isoformat()}, {platform.system()} {platform.machine()}", "limit": tiering.LIMIT, "tests": tests, "node": node}
    tiering.FILE.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"durations: {len(tests)} pytest tests of {tiering.LIMIT:g} s or more ({sum(tests.values()) / 60:.1f} minutes), {len(node)} node:test files, written to tests/durations.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
