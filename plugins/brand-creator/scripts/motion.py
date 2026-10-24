#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator motion: the motion decision, kept in one file, motion/motion.json.

  motion                  one line and exit 0: "motion: on (signature: <name>)", "motion: off (nothing moves: <reason>)" or "motion: not decided"; in
                          Standard and Full, once G3 is recorded, the last is followed by what is due before G4
  motion --json           the same as data: {"motion": "on" | "off" | "undecided", "signature": <name> (on), "reason": <text> (off)}
  motion --off "<reason>" record that nothing moves, once, in the owner's words: writes {"schema": 1, "motion": "off", "reason": ...} when there is no
                          motion/motion.json. Already off: nothing is written (a different reason says the recorded one stands). On: exit 2, because turning
                          it off is a rule change (edit motion/motion.json, then `check --cascade`)

A motion/motion.json that is not valid is exit 2 with the message of scripts/lib/motionspec.py. The tokens it names are not looked up: whether they are built is the motion:spec row of `check`.
Standard and Full decide motion before G4: the motion round, or `--off`. Quick decides it at G4 and only when something moves.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from _common import EXIT_USAGE, Parser, add_project_arg, confine, fail, find_project, main_guard, write_bytes_if_changed  # noqa: E402
import motionspec  # noqa: E402


def record_off(project: Path, reason: str) -> int:
    new = {"schema": 1, "motion": "off", "reason": reason.strip()}
    bad, _refs = motionspec.check(new)   # the spec's own check decides, before anything else is read or written: a blank reason is its "reason: must be a non-empty string"
    if bad:
        fail(EXIT_USAGE, f"{motionspec.FILE}: " + "; ".join(bad) + ' (motion --off "<the owner\'s reason>": why nothing moves, in the owner\'s words)')
    doc = motionspec.load(project, tokens=False)   # a motion.json that is not valid is exit 2: never written over, never guessed at (its tokens are none of this command's business)
    if doc is not None and doc["motion"] == "on":
        fail(EXIT_USAGE, f"{motionspec.FILE} says the brand moves (signature {doc['signature']['name']}); turning it off is a rule change: edit {motionspec.FILE} "
                         "and run `brand-creator check --cascade` with the old wording as its value, to find what still says it")
    if doc is not None:
        print(f"already recorded: nothing moves ({motionspec.one_line(doc['reason'])})")
        if motionspec.one_line(doc["reason"]) != motionspec.one_line(new["reason"]):
            print(f"the recorded reason stands; changing it is an edit of {motionspec.FILE} followed by `brand-creator check --cascade` with the old wording as its value")
        return 0
    write_bytes_if_changed(confine(project, motionspec.FILE, what="motion spec"), (json.dumps(new, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(f"recorded: nothing moves ({motionspec.one_line(new['reason'])}) in {motionspec.FILE}")
    return 0


def main() -> int:
    ap = Parser(prog="brand-creator motion", description=__doc__, formatter_class=__import__("argparse").RawDescriptionHelpFormatter)
    add_project_arg(ap)
    ap.add_argument("--json", action="store_true", help="print the decision as JSON")
    ap.add_argument("--off", metavar="REASON", help="record that nothing moves, once (the owner's reason)")
    a = ap.parse_args()
    project = find_project(a.project)
    if a.off is not None:
        if a.json:
            fail(EXIT_USAGE, "--json prints the decision; --off records one and says what it did: use one of them")
        return record_off(project, a.off)
    d = motionspec.decision(project)
    print(json.dumps(d, indent=2, ensure_ascii=False) if a.json else "\n".join(motionspec.status_lines(project, d)))
    return 0


main_guard(main)
