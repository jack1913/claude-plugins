#!/usr/bin/env python3
"""Score a swift:review report against the verification answer key.

Usage: score.py <key.json> <review.md> --run code|tokened|screenshot

Findings are the report's `- [high|medium|low] ...` lines before `## Not checked`.
A planted violation is detected when a finding's violation and location (the
text before its `— HIG:` part, so never its fix) match the violation's
`must_match` pattern and, for runs with `match_lines`, cite `<file>:<line>`, a
line range, or a `:<line>` continuation after it, within the key's tolerance of
one of its line ranges. A `never` rule matching a finding is a false positive:
`unless` exempts the whole line, while `unless_before` and `unless_after` exempt
one match by the text just before or after it. Exit 0 only when detected >= min
and there are no false positives. Standard library only.
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


LOCATION = re.compile(r"([\w./-]+\.swift)?:(\d+)(?:\s*[-–]\s*(\d+))?")


def claim(line):
    """The violation and location: everything before the finding's HIG part, never its fix."""
    return re.split(r"\s—\s*HIG:", line, maxsplit=1)[0]


def cited_ranges(line, file):
    """Line ranges cited for file, counting `:<line>` continuations after `<file>:<line>`."""
    ranges, current = [], False
    for match in LOCATION.finditer(claim(line)):
        named, start, end = match.groups()
        if named:
            current = named == file or named.endswith("/" + file)
        if current:
            ranges.append((int(start), int(end or start)))
    return ranges


def at_location(line, violation, tolerance):
    for lo, hi in cited_ranges(line, violation["file"]):
        for klo, khi in violation["lines"]:
            if lo <= khi + tolerance and hi >= klo - tolerance:
                return True
    return False


def detects(line, violation, match_lines, tolerance):
    if not re.search(violation["must_match"], claim(line)):
        return False
    return not match_lines or at_location(line, violation, tolerance)


def breaks(line, rule):
    """True when a match of the rule's pattern survives its exemptions."""
    if "unless" in rule and re.search(rule["unless"], line):
        return False
    for match in re.finditer(rule["pattern"], line):
        before, after = line[max(0, match.start() - 30) : match.start()], line[match.end() :]
        if "unless_before" in rule and re.search(rule["unless_before"], before):
            continue
        if "unless_after" in rule and re.search(rule["unless_after"], after):
            continue
        return True
    return False


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
