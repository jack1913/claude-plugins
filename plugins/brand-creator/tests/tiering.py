"""The fast tier, from tests/durations.json: how long each slow test took in the last measured run.

`tests/run-all.sh --fast` (BRAND_CREATOR_FAST=1) leaves out every test measured at LIMIT seconds or more: the daily run, a minute or two. A test
never measured (a new one) always runs. Of the node:test files it runs those under LIMIT seconds a test (`fast_node_files`): the others drive Chromium.
The full run is not reordered by these times: started longest first, the Chromium tests ran together and the run took 14.6 minutes instead of 12.
tests/tools/durations.py writes the file from the JUnit XML of a full run (pytest --junitxml). Standard library only."""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

LIMIT = 1.0                                                   # seconds: a test measured at this or more is a slow test, left out of the fast tier
FILE = Path(__file__).resolve().parent / "durations.json"


def key_of(nodeid: str) -> str:
    """The key of a test in durations.json: its node id from the test file's name on (`test_kit.py::test_a[x]`), so that it does not depend on the folder pytest ran from."""
    return nodeid.rsplit("/", 1)[-1]


def load(path: Path = FILE) -> dict[str, float]:
    """{key: seconds} of the committed file, or {} when there is none (every test then runs, in the order collected)."""
    if not path.is_file():
        return {}
    return {k: float(v) for k, v in json.loads(path.read_text(encoding="utf-8"))["tests"].items()}


def is_slow(nodeid: str, durations: dict[str, float]) -> bool:
    return durations.get(key_of(nodeid), 0.0) >= LIMIT


def durations_from_junit(paths) -> dict[str, float]:
    """{key: seconds, rounded to a tenth} of every test that ran (no skip) for LIMIT seconds or more in the JUnit XML files `paths`; the longest time when a test is in two."""
    out: dict[str, float] = {}
    for p in paths:
        for case in ET.parse(p).getroot().iter("testcase"):
            if case.find("skipped") is not None:
                continue
            seconds = float(case.get("time") or 0)
            parts = (case.get("classname") or "").split(".")
            mod = next((i for i, part in enumerate(parts) if part.startswith("test_")), None)
            if mod is None or seconds < LIMIT:
                continue
            key = "::".join([f"{parts[mod]}.py", *parts[mod + 1:], case.get("name") or ""])
            out[key] = max(out.get(key, 0.0), round(seconds, 1))
    return dict(sorted(out.items()))


def load_node(path: Path = FILE) -> dict[str, dict]:
    """{node test file: {"tests": n, "seconds": s}} of the committed file, or {}."""
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("node", {})


def node_files_from_junit(paths) -> dict[str, dict]:
    """{file name: {"tests": n, "seconds": total, rounded to a tenth}} of every node:test file in the JUnit XML files `paths` (node --test --test-reporter=junit)."""
    out: dict[str, dict] = {}
    for p in paths:
        for case in ET.parse(p).getroot().iter("testcase"):
            f = (case.get("file") or "").rsplit("/", 1)[-1]
            if not f.endswith(".test.mjs"):
                continue
            row = out.setdefault(f, {"tests": 0, "seconds": 0.0})
            row["tests"] += 1
            row["seconds"] += float(case.get("time") or 0)
    return {f: {"tests": r["tests"], "seconds": round(r["seconds"], 1)} for f, r in sorted(out.items())}


def fast_node_files(folder: Path, node: dict[str, dict]) -> list[str]:
    """The node:test files of `folder` the fast tier runs: those measured under LIMIT seconds a test, and any file never measured. Sorted names."""
    def slow(name: str) -> bool:
        row = node.get(name)
        return bool(row) and row["seconds"] / max(row["tests"], 1) >= LIMIT
    return sorted(p.name for p in folder.glob("*.test.mjs") if not slow(p.name))


def file_seconds(files: list[str], durations: dict[str, float]) -> dict[str, float]:
    """{test file name: the seconds its slow tests took in the last measured run, plus one}: a file never measured still counts."""
    out = {f: 1.0 for f in files}
    for key, seconds in durations.items():
        f = key.split("::", 1)[0]
        if f in out:
            out[f] += seconds
    return out


def shard(files: list[str], durations: dict[str, float], index: int, count: int) -> list[str]:
    """Share `index` (1 to `count`) of the test file names `files`, dealt out so that the shares take about as long: the longest file first, each
    to the share with the least time so far. Every file is in exactly one share, and two shares differ by no more than the longest file. Sorted
    names. The release run on GitHub runs one share a job (.github/workflows/brand-creator-release.yml): a job there ends after an hour."""
    if not (isinstance(index, int) and isinstance(count, int) and 1 <= index <= count):
        raise ValueError(f"share {index} of {count}: the share is a whole number from 1 to the count")
    seconds = file_seconds(files, durations)
    shares = [[0.0, []] for _ in range(count)]
    for f in sorted(files, key=lambda f: (-seconds[f], f)):
        least = min(shares, key=lambda share: share[0])
        least[0] += seconds[f]
        least[1].append(f)
    return sorted(shares[index - 1][1])


USAGE = "usage: tiering.py fast-node-files | tiering.py shard <share> <count>"

if __name__ == "__main__":      # `fast-node-files`: the paths tests/run-all.sh --fast gives node --test; `shard 2 3`: the pytest files of share 2 of 3; one a line
    import sys
    here = Path(__file__).resolve().parent
    args = sys.argv[1:]
    if args == ["fast-node-files"]:
        print("\n".join(f"tests/node/{n}" for n in fast_node_files(here / "node", load_node())))
    elif len(args) == 3 and args[0] == "shard" and args[1].isdigit() and args[2].isdigit() and 1 <= int(args[1]) <= int(args[2]):
        names = sorted(p.name for p in here.glob("test_*.py"))
        print("\n".join(f"tests/{n}" for n in shard(names, load(), int(args[1]), int(args[2]))))
    else:
        print(USAGE, file=sys.stderr)
        raise SystemExit(2)
