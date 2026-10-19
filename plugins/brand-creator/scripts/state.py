#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator state: print or query BRAND-STATE.md, record gates, require gates.

  state                          human summary
  state --json                   everything machine-readable
  state --get tier               one value (dotted keys: gates.G3, fixes_per_area.logo)
  state --set tier=standard      set a frontmatter value (not gates.*; use --record)
  state --bump fixes_per_area.logo   add 1 to a counter
  state --record G3 "approved r3"    write "<date> <decision>" into gates.G3 (G5 also writes approved_edition = edition: the
                                 brand book shows APPROVED only for the edition G5 approved)
  state --require G3             exit 1 with a message naming the gate when it is not recorded
  state --project-auto           like the default, but exit 0 with a message when no project is found (for /status)
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from _common import (EXIT_FAIL, EXIT_USAGE, GATE_IDS, Parser, STATE_FILE, add_project_arg, fail, find_project,  # noqa: E402
                     gate_recorded, latest_round, list_rounds, main_guard, read_state, today, try_find_project,
                     verify_history)


# Keys whose values other tools branch on (board_lint, freeze, prereq). A typo here must not pass silently.
ENUMS = {
    "tier": ("quick", "standard", "full"),
    "architecture": ("standalone", "family-member", "product-in-family"),
    "mark_source": ("generated", "authored-vector", "existing"),
    "review_surface": ("auto", "artifact", "local"),
}
PHASE_RE = re.compile(r"P(?:[0-9]|1[0-3])[a-z]?")  # P0..P13, with an optional sub-phase letter such as P1b or P1c


def check_value(key: str, value: str) -> None:
    if key in ENUMS and value not in ENUMS[key]:
        fail(EXIT_USAGE, f"{key} must be one of {' | '.join(ENUMS[key])}, got {value!r}")
    if key in ("edition", "approved_edition") and not re.fullmatch(r"[1-9][0-9]*", value):
        fail(EXIT_USAGE, f"{key} must be a whole number from 1, got {value!r}")
    if key == "phase" and not PHASE_RE.fullmatch(value):
        fail(EXIT_USAGE, f"phase must be P0 to P13 (a sub-phase letter is allowed, e.g. P1b), got {value!r}")


def summary(project: Path) -> dict:
    st = read_state(project)
    d = st.data()
    hist = project / "history"
    return {
        "project": str(project), "state": d, "directions": st.directions(),
        "rounds": [f"r{n}" for n, _ in list_rounds(project)],
        "latest_round": (f"r{latest_round(project)}" if latest_round(project) else None),
        "frozen": sorted(p.name for p in hist.iterdir() if p.is_dir()) if hist.is_dir() else [],
        "history_problems": verify_history(project),
    }


def print_summary(s: dict) -> None:
    d = s["state"]
    gates = d.get("gates", {}) or {}
    print(f"project: {s['project']}")
    print(f"name: {d.get('name', '')} (slug {d.get('slug', '')})")
    print(f"tier: {d.get('tier', '?')}   phase: {d.get('phase', '?')}   architecture: {d.get('architecture', '?')}   "
          f"mark source: {d.get('mark_source', '?')}")
    print(f"renderer: {d.get('renderer', 'resvg')}   review surface: {d.get('review_surface', 'auto')}   "
          f"review url: {d.get('review_url') or '-'}")
    print("gates: " + "  ".join(f"{g} {'recorded' if str(gates.get(g, '')).strip() else '-'}" for g in GATE_IDS))
    for g in GATE_IDS:
        if str(gates.get(g, "")).strip():
            print(f"  {g}: {gates[g]}")
    print(f"rounds: {' '.join(s['rounds']) or '-'}   latest: {s['latest_round'] or '-'}")
    if d.get("fixes_per_area"):
        print("fixes per area: " + ", ".join(f"{k}={v}" for k, v in d["fixes_per_area"].items()))
    if d.get("canonical_direction"):
        print(f"canonical direction: {d['canonical_direction']}")
    if s["directions"]:
        print("directions: " + "; ".join(f"{r.get('name', '?')}{' (' + r['letter'] + ')' if r.get('letter') else ''}"
                                         f" [{r.get('status', '')}]" for r in s["directions"]))
    if s["frozen"]:
        print("frozen: " + ", ".join(s["frozen"]))
    print("history: " + ("intact" if not s["history_problems"] else "PROBLEMS: " + "; ".join(s["history_problems"])))


def main() -> int:
    ap = Parser(prog="brand-creator state", description=__doc__, formatter_class=__import__("argparse").RawDescriptionHelpFormatter)
    add_project_arg(ap)
    ap.add_argument("--project-auto", action="store_true", help="exit 0 with a message when no project is found")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--get", metavar="KEY")
    ap.add_argument("--set", action="append", default=[], metavar="KEY=VALUE")
    ap.add_argument("--bump", action="append", default=[], metavar="KEY")
    ap.add_argument("--record", nargs=2, metavar=("GATE", "DECISION"))
    ap.add_argument("--require", metavar="GATE")
    a = ap.parse_args()

    if a.project_auto and not a.project:
        p = try_find_project()
        if p is None:
            print(f"no brand project found from {Path.cwd()} (no {STATE_FILE} in this folder or above). "
                  f"Start one with /brand-creator:new, or pass --project.")
            return 0
        project = p
    else:
        project = find_project(a.project)

    if a.require:
        g = a.require
        if g not in GATE_IDS:
            fail(EXIT_USAGE, f"unknown gate {g!r}; gates are {', '.join(GATE_IDS)}")
        rec = gate_recorded(project, g)
        if not rec:
            fail(EXIT_FAIL, f"gate {g} is not recorded in {STATE_FILE}. Get the owner's decision, then run: "
                            f"brand-creator state --record {g} \"<decision>\"")
        print(f"{g}: recorded ({rec})")
        return 0

    changed = False
    st = read_state(project)
    for kv in a.set:
        if "=" not in kv:
            fail(EXIT_USAGE, f"--set needs KEY=VALUE, got {kv!r}")
        k, v = kv.split("=", 1)
        if k.startswith("gates."):
            fail(EXIT_USAGE, "set gates with --record G<n> \"<decision>\" so the date is written too")
        check_value(k, v)
        st.set(k, v)
        changed = True
    for k in a.bump:
        cur = st.get(k, "0")
        try:
            n = int(cur or 0) + 1
        except ValueError:
            fail(EXIT_USAGE, f"{k} is {cur!r}, not a number")
        st.set(k, n)
        print(f"{k} = {n}")
        changed = True
    if a.record:
        g, decision = a.record
        if g not in GATE_IDS:
            fail(EXIT_USAGE, f"unknown gate {g!r}; gates are {', '.join(GATE_IDS)}")
        if not decision.strip():
            fail(EXIT_USAGE, "a gate needs a decision text")
        prev = str((st.get("gates", {}) or {}).get(g, "") or "").strip()
        st.set(f"gates.{g}", f"{today()} {decision.strip()}")
        if g == "G5":   # the approval belongs to the edition that was approved, so a later edition is not approved by it
            ed = str(st.get("edition", "") or "").strip()
            if ed:
                st.set("approved_edition", ed)
                print(f"approved_edition = {ed}")
            else:
                print("note: BRAND-STATE.md has no edition; add one (state --set edition=1) so the book can show the approval")
        print(f"recorded {g}: {today()} {decision.strip()}" + (f"   (replaced: {prev})" if prev else ""))
        changed = True
    if changed:
        st.save()
        if not (a.get or a.json):
            return 0

    if a.get:
        v = read_state(project).get(a.get)
        if v is None:
            fail(EXIT_FAIL, f"{a.get} is not set in {STATE_FILE}")
        print(json.dumps(v) if isinstance(v, (dict, list)) else v)
        return 0
    s = summary(project)
    if a.json:
        print(json.dumps(s, indent=2, ensure_ascii=False))
    else:
        print_summary(s)
    return 0


main_guard(main)
