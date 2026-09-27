#!/usr/bin/env python3
"""Score a swift:review report against the verification answer key.

Usage: score.py <key.json> <review.md> --run code|tokened|screenshot

Findings are the report's `- [high|medium|low] ...` lines before `## Not checked`.
A planted violation is detected when a finding matches its `must_match` pattern
and, for runs with `match_lines`, cites `<file>:<line>` (or a line range) within
the key's tolerance of one of its line ranges. A `never` rule matching a finding
is a false positive. Exit 0 only when detected >= min and there are no false
positives. Standard library only.
"""

import argparse
import json
import re
import sys
from pathlib import Path

FINDING = re.compile(r"^\s*- \[(high|medium|low)\]", re.IGNORECASE)
NOT_CHECKED = re.compile(r"^#+\s*Not checked", re.IGNORECASE)


def findings(text):
    out = []
    for line in text.splitlines():
        if NOT_CHECKED.match(line):
            break
        if FINDING.match(line):
            out.append(line.strip())
    return out


def cited_ranges(line, file):
    pattern = re.compile(re.escape(file) + r":(\d+)(?:\s*[-–]\s*(\d+))?")
    return [(int(a), int(b or a)) for a, b in pattern.findall(line)]


def at_location(line, violation, tolerance):
    for lo, hi in cited_ranges(line, violation["file"]):
        for klo, khi in violation["lines"]:
            if lo <= khi + tolerance and hi >= klo - tolerance:
                return True
    return False


def detects(line, violation, match_lines, tolerance):
    if not re.search(violation["must_match"], line):
        return False
    return not match_lines or at_location(line, violation, tolerance)


def breaks(line, rule):
    if not re.search(rule["pattern"], line):
        return False
    return not ("unless" in rule and re.search(rule["unless"], line))


def score(key, text, run_name):
    run = key["runs"][run_name]
    lines = findings(text)
    tolerance = key.get("tolerance", 0)
    detected, used = [], set()
    for vid in run["planted"]:
        v = key["violations"][vid]
        hits = [i for i, line in enumerate(lines) if detects(line, v, run["match_lines"], tolerance)]
        if hits:
            detected.append(vid)
            used.update(hits)
    false_positives = []
    for nid in run["never"]:
        for i, line in enumerate(lines):
            if any(breaks(line, rule) for rule in key["never"][nid]["rules"]):
                false_positives.append(nid)
                used.add(i)
                break
    missed = [vid for vid in run["planted"] if vid not in detected]
    unscored = len(lines) - len(used)
    ok = len(detected) >= run["min"] and not false_positives
    summary = (
        f"detected {len(detected)}/{len(run['planted'])}, missed {missed}, "
        f"false positives {false_positives}, unscored {unscored}"
    )
    return ok, summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("key")
    parser.add_argument("review")
    parser.add_argument("--run", required=True, choices=["code", "tokened", "screenshot"])
    args = parser.parse_args(argv)
    key = json.loads(Path(args.key).read_text())
    ok, summary = score(key, Path(args.review).read_text(), args.run)
    print(summary)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
