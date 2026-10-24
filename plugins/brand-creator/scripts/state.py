#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator state: print or query BRAND-STATE.md, record gates, require gates.

  state                          human summary (with the motion decision: the line `brand-creator motion` prints)
  state --json                   everything machine-readable
  state --get tier               one value (dotted keys: gates.G3, fixes_per_area.logo)
  state --set tier=standard      set a frontmatter value (not gates.* or g1s_round; use --record). A list key is written as a real
                                 list: reset_rounds=2,3 (whole numbers from 1), book_chapters=tone,photography
  state --bump fixes_per_area.logo   add 1 to a counter
  state --record G3 "approved r3"    write "<date> <decision>" into gates.G3 (G5 also writes approved_edition = edition: the
                                 brand book shows APPROVED only for the edition G5 approved; G1s also writes g1s_round = the
                                 highest round whose board.html is a style board, r0 included, or removes it when there is none:
                                 board-lint reads it to see that the style pick is newer than the new style board of a full rejection)
  state --require G3             exit 1 with a message naming the gate when it is not recorded
  state --project-auto           like the default, but exit 0 with a message when no project is found (for /status)
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "boardlib"))
from _common import (EXIT_FAIL, EXIT_USAGE, GATE_IDS, CliError, Parser, STATE_FILE, add_project_arg, fail, find_project,  # noqa: E402
                     gate_recorded, latest_round, list_rounds, main_guard, read_state, today, try_find_project,
                     verify_history)
from boardpage import is_style_board, read_page  # noqa: E402
import motionspec  # noqa: E402


# Keys whose values other tools branch on (board_lint, freeze, prereq). A typo here must not pass silently.
ENUMS = {
    "tier": ("quick", "standard", "full"),
    "architecture": ("standalone", "family-member", "product-in-family"),
    "mark_source": ("generated", "authored-vector", "existing"),
    "review_surface": ("auto", "artifact", "local"),
}
PHASE_RE = re.compile(r"P(?:[0-9]|1[0-3])[a-z]?")  # P0..P13, with an optional sub-phase letter such as P1b or P1c
# Keys the template holds as a flow list (`key: [a, b]`): --set writes a real list for them, never a quoted string. A new list key in
# templates/BRAND-STATE.md goes here too (a test reads the template).
LIST_KEYS = ("book_chapters", "reset_rounds")
WORD_RE = re.compile(r"[A-Za-z0-9_.-]+")
KEY_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*(?:\.[A-Za-z0-9_-]+)*")   # a frontmatter key, or a dotted path such as fixes_per_area.lockup


def refuse_g1s_round(key: str) -> None:
    """g1s_round is the highest round whose board is a style board when G1s was recorded; board-lint trusts it, so only `--record G1s` writes it."""
    if key == "g1s_round":
        fail(EXIT_USAGE, "g1s_round is written by --record G1s (the highest round whose board is a style board when the style pick is "
                         "recorded); record the owner's pick with: state --record G1s \"<decision>\"")


def style_board_round(project: Path) -> int | None:
    """The highest round whose rounds/rN/board.html is a style board, as board-lint's style gate counts one (a page that declares
    data-board="style" and its own round, and holds the territories a style board needs), or None. A round folder that was only created or
    copied, or whose style board is not written yet, is not one."""
    for n, path in reversed(list_rounds(project)):
        if is_style_board(read_page(path / "board.html"), n):
            return n
    return None


def check_value(key: str, value: str) -> None:
    if key in ENUMS and value not in ENUMS[key]:
        fail(EXIT_USAGE, f"{key} must be one of {' | '.join(ENUMS[key])}, got {value!r}")
    if key in ("edition", "approved_edition") and not re.fullmatch(r"[1-9][0-9]*", value):
        fail(EXIT_USAGE, f"{key} must be a whole number from 1, got {value!r}")
    if key == "phase" and not PHASE_RE.fullmatch(value):
        fail(EXIT_USAGE, f"phase must be P0 to P13 (a sub-phase letter is allowed, e.g. P1b), got {value!r}")


def list_value(key: str, value: str) -> list:
    """The items of a --set value for a list key: `[2, 3]`, `2,3` or `2`; an empty value or `[]` is the empty list. reset_rounds holds whole
    numbers from 1 (the rounds that follow a full rejection); any other list key holds plain words. Exits 2 on anything else."""
    inner = value.strip()
    if inner.startswith("[") and inner.endswith("]"):
        inner = inner[1:-1].strip()
    items = [x.strip().strip("\"'").strip() for x in inner.split(",")] if inner else []
    if key == "reset_rounds":
        if not all(re.fullmatch(r"[0-9]+", x) and int(x) >= 1 for x in items):
            fail(EXIT_USAGE, f"reset_rounds must be whole numbers from 1, like [2, 3], got {value!r}")
        return [int(x) for x in items]
    if not all(WORD_RE.fullmatch(x) for x in items):
        fail(EXIT_USAGE, f"{key} must be a list of plain words, like [a, b], got {value!r}")
    return items


def motion_decision(project: Path) -> dict:
    """The motion decision as `brand-creator motion` reports it. A summary must always print (the status skill injects it), so a motion/motion.json that cannot
    be read is said in the summary, with the message `motion` gives, and is no exit code here."""
    try:
        return motionspec.decision(project)
    except CliError as e:
        return {"motion": "unreadable", "problem": e.message}


def summary(project: Path) -> dict:
    st = read_state(project)
    d = st.data()
    hist = project / "history"
    latest = latest_round(project)   # 0 is a real round (the style board), so compare with None, never test the number's truth
    return {
        "project": str(project), "state": d, "directions": st.directions(),
        "rounds": [f"r{n}" for n, _ in list_rounds(project)],
        "latest_round": (f"r{latest}" if latest is not None else None),
        "motion": motion_decision(project),
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
    print(f"rounds: {' '.join(s['rounds']) or '-'}   latest: {s['latest_round'] if s['latest_round'] is not None else '-'}")
    m = s["motion"]
    print(f"motion: cannot be read ({m['problem']})" if m["motion"] == "unreadable" else "\n".join(motionspec.status_lines(Path(s["project"]), m)))
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
        k, v = (s.strip() for s in kv.split("=", 1))   # "reset_rounds =2,3" is reset_rounds, so its checks still run
        if not KEY_RE.fullmatch(k):
            fail(EXIT_USAGE, f"--set needs KEY=VALUE with a key of letters, digits, _ and - (dots between parts), got {kv!r}")
        if k.startswith("gates."):
            fail(EXIT_USAGE, "set gates with --record G<n> \"<decision>\" so the date is written too")
        refuse_g1s_round(k)
        if k in LIST_KEYS:
            st.set(k, list_value(k, v))
        else:
            check_value(k, v)
            st.set(k, v)
        changed = True
    for k in a.bump:
        refuse_g1s_round(k)
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
        if g == "G1s":   # which style board the pick came after: board-lint compares it with the style board of a reset round
            n = style_board_round(project)
            if n is not None:
                st.set("g1s_round", n)
                print(f"g1s_round = {n}")
            elif st.remove("g1s_round"):
                print("g1s_round removed (no style board on disk)")
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
