#!/usr/bin/env python3
"""Reads the log of `tests/run-all.sh --smoke` made inside the Linux image and decides whether the run is acceptable.

    verify_log.py <log> <run-all exit code>

Acceptable: pytest and node:test have no failure and no error, the whole Acme smoke passed (its line `SMOKE PASSED: Acme at ...`:
the line of one half, `SMOKE PASSED (part ...)`, is not the whole smoke), and every skipped test is a
"NOT VERIFIED" skip whose reason is one of EXPECTED below. A skip that is not on the list is a bug (a test that silently depends on
macOS or on a tool the Linux image should have), so it fails the run. The exact counts and the NOT VERIFIED banner are printed.
BRAND_CREATOR_TEST_PARTS (pytest, node, smoke, comma-separated; default all three) names the parts the run was asked for, as
tests/run-all.sh reads it: each part named must have left its summary, so a part that did not run is a failure, never a pass.
Standard library only.
"""
from __future__ import annotations

import os
import re
import sys
from collections import Counter

# Reason -> why it is expected off macOS. Matched as a prefix of the skip reason after "NOT VERIFIED: ".
EXPECTED = {
    "not macOS": "tests marked requires_macos: Apple tools exist on macOS only",
    "actool is not available": "tests marked requires_actool: Xcode's actool exists on macOS only",
    "the Android SDK (aapt2 and a platform android.jar) is not installed": "tests marked requires_aapt2: the image carries no Android SDK",
    "the claude CLI is not on PATH": "the claude CLI is not installed in the image: it runs `claude plugin validate` (test_static, CI job `validate`) and the free "
                                     "eval-loader check (test_evals and the smoke), which a bare Linux image cannot do",
}
if not os.environ.get("BRAND_CREATOR_DENYLIST"):   # the denylist is the owner's private file: run.sh mounts it when given
    EXPECTED["BRAND_CREATOR_DENYLIST is not set"] = "the anonymisation denylist is never shipped (run.sh mounts it from BRAND_CREATOR_DENYLIST)"
ANSI = re.compile(r"\x1b\[[0-9;]*m")
WHOLE_SMOKE = re.compile(r"^SMOKE PASSED: Acme at ", re.M)   # tests/smoke/acme.sh with every section (ACME_SMOKE_PART unset or all)


PARTS = ("pytest", "node", "smoke")


def main() -> int:
    log, rc = sys.argv[1], int(sys.argv[2])
    parts = [p.strip() for p in (os.environ.get("BRAND_CREATOR_TEST_PARTS") or ",".join(PARTS)).split(",") if p.strip()]   # as tests/run-all.sh reads it
    if not parts or any(p not in PARTS for p in parts):
        print(f"BRAND_CREATOR_TEST_PARTS={os.environ.get('BRAND_CREATOR_TEST_PARTS')!r}: name one or more of {', '.join(PARTS)}", file=sys.stderr)
        return 2
    text = ANSI.sub("", open(log, encoding="utf-8", errors="replace").read())
    lines = text.splitlines()
    problems: list[str] = []

    # ---- pytest
    summary = None
    skips: Counter[str] = Counter()
    if "pytest" in parts:
        summary = next((ln for ln in reversed(lines) if re.search(r"\b\d+ (passed|failed)\b.* in [\d.]+s", ln)), None)
        if summary is None:
            print("no pytest summary line found in the log", file=sys.stderr)
            return 1
        counts = {k: int(n) for n, k in re.findall(r"(\d+) (passed|failed|skipped|deselected|errors?|xfailed|xpassed)", summary)}
        for ln in lines:
            m = re.match(r"SKIPPED \[(\d+)\] (\S+?): (.*)$", ln)
            if m:
                skips[m.group(3).strip()] += int(m.group(1))
        unexpected = {r: n for r, n in skips.items() if not any(r == f"NOT VERIFIED: {e}" or r.startswith(f"NOT VERIFIED: {e}") for e in EXPECTED)}
        if sum(skips.values()) != counts.get("skipped", 0):
            problems.append(f"pytest reports {counts.get('skipped', 0)} skipped but the -rs list names {sum(skips.values())}")
        if unexpected:
            problems.append("unexpected skips (a bug, not an expected NOT VERIFIED): " + "; ".join(f"{n} x {r}" for r, n in unexpected.items()))
        for k in ("failed", "error", "errors"):
            if counts.get(k):
                problems.append(f"pytest: {counts[k]} {k}")

    # ---- node:test (the TAP-ish summary node prints at the end)
    node = {k: int(v) for k, v in re.findall(r"^(?:#|\u2139) (tests|pass|fail|cancelled|skipped|todo) (\d+)$", text, re.M)}   # "# pass 53" (TAP) or "\u2139 pass 53" (spec reporter)
    if "node" in parts:
        if not node:
            problems.append("no node:test summary in the log")
        else:
            if node.get("fail") or node.get("cancelled"):
                problems.append(f"node:test: fail={node.get('fail')} cancelled={node.get('cancelled')}")
            if node.get("skipped") or node.get("todo"):
                problems.append(f"node:test: skipped={node.get('skipped')} todo={node.get('todo')} (nothing in the node suite may be skipped)")

    # ---- smoke
    if "smoke" in parts and not WHOLE_SMOKE.search(text):
        problems.append("the Acme smoke did not print SMOKE PASSED for the whole smoke")
    smoke_nv = [ln.strip() for ln in lines if ln.strip().startswith("NOT VERIFIED:")]
    bad_smoke = [ln for ln in smoke_nv if not any(ln.startswith(f"NOT VERIFIED: {e}") for e in EXPECTED)]
    if bad_smoke:
        problems.append("unexpected NOT VERIFIED lines in the smoke: " + "; ".join(bad_smoke))
    if "SMOKE FAILED" in text:
        problems.append("SMOKE FAILED appears in the log")
    if rc != 0:
        problems.append(f"tests/run-all.sh exited {rc}")

    print("parts  :", ", ".join(parts))
    print("pytest :", summary.strip() if summary else "not asked for")
    print("node   :", (", ".join(f"{k} {v}" for k, v in node.items()) or "no summary") if "node" in parts else "not asked for")
    print("smoke  :", ("SMOKE PASSED" if WHOLE_SMOKE.search(text) else "NOT PASSED") if "smoke" in parts else "not asked for",
          "; NOT VERIFIED lines:", smoke_nv or "none")
    start = next((i for i, ln in enumerate(lines) if "TEST(S) NOT VERIFIED" in ln), None)
    print("NOT VERIFIED banner (verbatim):")
    if start is None:
        print("  (none printed)")
    else:
        for ln in lines[start:start + 3 + len(skips) + 1]:
            print("  " + ln)
    print("skips by reason (pytest -rs):")
    for r, n in sorted(skips.items()):
        print(f"  {n:4d} x {r}")
    print("expected off macOS:")
    for e, why in EXPECTED.items():
        print(f"  - {e}: {why}")
    if problems:
        print("\nLINUX RUN FAILED:", file=sys.stderr)
        for p in problems:
            print("  - " + p, file=sys.stderr)
        return 1
    print(f"\nLINUX RUN OK ({', '.join(parts)}): every skip is an expected NOT VERIFIED; nothing else skipped or failed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
