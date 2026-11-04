"""templates/finish.sh.tpl, the chain's own decisions: which step runs, in which order, with which arguments, what it says, and when it stops. The
filled template runs for real, in a bare project folder, against a stand-in for `brand-creator` that logs every call and answers as each test says,
so each branch takes a fraction of a second instead of a whole chain.

What the tools themselves do lives in their own tests; tests/test_finish_chain.py keeps two real chains end to end (the Standard chain, and a brand that
moves) and the one thing this file assumes of the real CLI: a node tool that wrote its report prints `report: <path>`. tests/mutation_ledger.py
(group finish-chain) breaks the template on purpose and names the test here that must catch each break."""
import json
import os
import re
import subprocess
from pathlib import Path

import pytest
from helpers import ROOT

STUB = r'''#!/usr/bin/env python3
"""A stand-in for brand-creator: it logs each call (without --data <dir>) and answers as STUB_SCENARIO says; any other call succeeds and prints nothing."""
import json, os, sys
from pathlib import Path
argv = sys.argv[1:]
if argv[:1] == ["--data"]:
    argv = argv[2:]
with open(os.environ["STUB_LOG"], "a") as log:
    log.write(json.dumps(argv) + "\n")
scenario = json.loads(Path(os.environ["STUB_SCENARIO"]).read_text())
cmd = argv[0] if argv else ""
answer = scenario.get(" ".join(argv[:2])) or scenario.get(cmd) or {}
if cmd == "state" and argv[1:3] == ["--get", "tier"]:
    print(scenario["tier"])
elif cmd == "state" and argv[1:3] == ["--get", "slug"]:
    if scenario.get("slug_fails"):
        print(scenario["slug_fails"]["err"], file=sys.stderr)
        sys.exit(scenario["slug_fails"]["code"])
    print(scenario["slug"])
elif cmd == "motion" and "--json" in argv and "code" not in answer:
    print(json.dumps(scenario["decision"]))
elif cmd == "check" and not answer:
    print("check: PASS")
for rel in answer.get("write", []):
    Path(rel).parent.mkdir(parents=True, exist_ok=True)
    Path(rel).write_text("{}\n")
if answer.get("out"):
    print(answer["out"])
if answer.get("err"):
    print(answer["err"], file=sys.stderr)
sys.exit(answer.get("code", 0))
'''

ON = {"motion": "on", "signature": "Press"}                     # what `brand-creator motion --json` prints for a brand that moves
OFF = {"motion": "off", "reason": "The brand lives on paper and in a shop window."}
UNDECIDED = {"motion": "undecided"}
STILLS_LINE = "finish.sh: frames could not take the stills (see above); the book keeps the stills of the last run that worked, if any, and check says why"
NOT_DECIDED_LINE = 'motion is not decided: run the motion round, or record nothing moves with `brand-creator motion --off "<the owner\'s reason>"` (check fails motion:decided once G4 is recorded)'
TAG = "a repair guide is in every box"


class Chain:
    """One run of the filled template: its exit code, everything it printed, its steps (`== ...` lines) and the calls it made (argv after --data)."""

    def __init__(self, r: subprocess.CompletedProcess, log: Path, project: Path):
        self.code, self.out, self.project = r.returncode, r.stdout + r.stderr, project
        self.steps = re.findall(r"^== (.+)$", self.out, re.M)
        self.calls = [json.loads(ln) for ln in log.read_text().splitlines()] if log.is_file() else []

    def ran(self, *words: str) -> bool:
        return any(c[:len(words)] == list(words) for c in self.calls)

    def in_order(self, names: list[str]) -> None:
        pos = []
        for n in names:
            hits = [i for i, s in enumerate(self.steps) if s == n or s.startswith(n + " ")]
            assert hits, f"step {n!r} did not run: {self.steps}"
            pos.append(hits[0])
        assert pos == sorted(pos) and len(set(pos)) == len(pos), dict(zip(names, pos))


def chain(tmp_path: Path, *, tier: str = "standard", decision: dict | None = None, proof: str | None = "page", book: bool = True,
          answers: dict | None = None, targets: str = "web", rounds: dict[int, bool] | None = None, files: tuple[str, ...] = (), slug: str = "acme", **env: str) -> Chain:
    """Fill the template (block 2's targets: `targets`; no apple line) into a bare project and run it against the stand-in. `decision` is what `motion --json`
    answers and what motion/motion.json says (the frames step reads the file itself); `proof` writes motion/proof.json with a page case ("page"),
    with a named-state case only ("states"), or not at all (None); `answers` maps a call ("shot", "frames", "emit presskit", ...) to
    {"code": n, "out": text, "err": text, "write": [project files]}. `rounds` maps a round number to whether rounds/r<N>/board.html is there (none: no rounds/ folder).
    `files` are project files to put there (BRAND.md, DESIGN.md, .claude/skills/acme-brand/SKILL.md, .../kit.json); `slug` is what `state --get slug` answers."""
    decision = UNDECIDED if decision is None else decision
    p = tmp_path / "project"
    (p / "tools").mkdir(parents=True)
    (p / "assets").mkdir()
    (p / "assets" / "manifest.json").write_text('{"artefacts": []}\n')
    (p / "motion").mkdir()
    if decision["motion"] in ("on", "off"):
        doc = {"schema": 1, "motion": decision["motion"]}
        doc.update({"signature": {"name": decision["signature"]}} if decision["motion"] == "on" else {"reason": decision["reason"]})
        (p / "motion" / "motion.json").write_text(json.dumps(doc))
    if proof:
        case = {"name": "demo-page", "type": "page", "page": "motion/demo.html"} if proof == "page" else {"name": "dot", "type": "states", "file": "assets/logo/mark-animated.svg"}
        (p / "motion" / "proof.json").write_text(json.dumps({"schema": 1, "cases": [case]}))
    if book:
        (p / "book" / "chapters").mkdir(parents=True)
    for rel in files:
        (p / rel).parent.mkdir(parents=True, exist_ok=True)
        (p / rel).write_text("generated\n")
    for n_, has_board in (rounds or {}).items():
        (p / "rounds" / f"r{n_}").mkdir(parents=True)
        if has_board:
            (p / "rounds" / f"r{n_}" / "board.html").write_text("<html></html>\n")
    tpl = (ROOT / "templates" / "finish.sh.tpl").read_text()
    tpl, n = re.subn(r"^TARGETS=\(.*\)$", f"TARGETS=({targets})", tpl, flags=re.M)
    assert n == 1
    tpl, n = re.subn(r'^\[ "\$\(uname\)" = Darwin \] && TARGETS\+=\(apple\).*$', "", tpl, flags=re.M)
    assert n == 1
    (p / "tools" / "finish.sh").write_text(tpl)
    stub = tmp_path / "stub"
    stub.mkdir()
    (stub / "brand-creator").write_text(STUB)
    (stub / "brand-creator").chmod(0o755)
    scenario, log = tmp_path / "scenario.json", tmp_path / "calls.jsonl"
    scenario.write_text(json.dumps({"tier": tier, "slug": slug, "decision": decision, **(answers or {})}))
    run_env = {k: v for k, v in os.environ.items() if k not in ("BRAND_CREATOR_ROOT", "PRINT_REGION", "POST_FACTS", "FRAMES_ARGS", "TAGLINE", "ADAPTERS_ARGS")}
    run_env.update(PATH=f"{stub}:{os.environ['PATH']}", BRAND_CREATOR_DATA=str(tmp_path / "data"), STUB_SCENARIO=str(scenario), STUB_LOG=str(log), **env)
    r = subprocess.run(["bash", str(p / "tools" / "finish.sh")], capture_output=True, text=True, env=run_env, cwd=tmp_path, timeout=120)
    return Chain(r, log, p)


def report_of(c_path: Path) -> dict:
    """An answer of `shot --motion` that wrote its report: it prints the report's path, as the real one does, and the file is there."""
    return {"out": f"report: {c_path}", "write": [str(c_path)]}


# ---------------------------------------------------------------- the motion step: the decision is always said; a proof that ran is gated by check

def test_a_brand_that_moves_has_its_approved_move_proved_before_the_stills_and_the_book_read_the_report(tmp_path):
    c = chain(tmp_path, decision=ON)
    assert c.code == 0, c.out
    c.in_order(["gates", "motion", "shot --motion motion/proof.json", "frames motion/proof.json --count 25", "book", "book-pdf", "emit presskit"])
    assert "motion is on: signature Press" in c.out and c.ran("shot", "--motion", "motion/proof.json") and c.ran("check")


def test_a_motion_proof_that_fails_does_not_stop_the_chain(tmp_path):
    c = chain(tmp_path, decision=ON, answers={"shot": {"code": 1}})
    assert c.out.count("finish.sh: the motion proof failed (see above); the chain goes on and check fails the report") == 1, c.out
    c.in_order(["shot --motion motion/proof.json", "frames motion/proof.json --count 25", "book", "book-pdf", "emit presskit"])
    assert c.ran("check")                                                                        # check gates the failing report (its own tests)


def test_a_motion_proof_that_is_not_verified_goes_on_because_it_wrote_its_report(tmp_path):
    c = chain(tmp_path, decision=ON, answers={"shot": {"code": 3, **report_of(tmp_path / "project" / "assets/_checks/motion/proof-8f3a0e.json")}})
    assert c.out.count("finish.sh: the motion proof is not verified (see above); the chain goes on and check says why") == 1, c.out
    assert c.out.count("report: ") == 1                                                                         # what the proof printed is shown, its report line too
    assert "shot --motion stopped with exit" not in c.out and "the motion proof failed" not in c.out
    c.in_order(["shot --motion motion/proof.json", "frames motion/proof.json --count 25", "book", "emit presskit"])


def test_the_report_is_found_by_the_path_shot_printed_even_when_it_is_not_named_as_the_chain_types_the_proof(tmp_path):
    """A disk that does not tell letter cases apart names the report after Motion/proof.json: the chain reads the path `shot` printed, not one it guesses."""
    c = chain(tmp_path, decision=ON, answers={"shot": {"code": 3, **report_of(tmp_path / "project" / "assets/_checks/motion/proof-c41d9b.json")}})
    assert c.code == 0 and "is not verified (see above); the chain goes on" in c.out, c.out


@pytest.mark.parametrize("what, answer", [
    ("no report line, though an earlier report is there", {"code": 3, "write": ["assets/_checks/motion/proof-8f3a0e.json"]}),
    ("a report line that names no file", {"code": 3, "out": "report: assets/_checks/motion/proof-gone.json"}),
])
def test_an_exit_3_that_wrote_no_report_stops_the_chain(tmp_path, what, answer):
    c = chain(tmp_path, decision=ON, answers={"shot": answer})
    assert c.code == 3, (what, c.out)
    assert "finish.sh: shot --motion stopped with exit 3 (see above); check has no failing report to gate, so the chain stops here" in c.out and "is not verified (see above)" not in c.out
    assert c.steps[-1] == "shot --motion motion/proof.json" and not c.ran("book") and not c.ran("check"), c.steps


@pytest.mark.parametrize("code", [2, 3])
def test_a_motion_proof_that_stops_with_exit_2_or_3_stops_the_chain_with_that_exit_code(tmp_path, code):
    c = chain(tmp_path, decision=ON, answers={"shot": {"code": code, "err": "stub: shot cannot run"}})
    assert c.code == code, c.out
    assert f"finish.sh: shot --motion stopped with exit {code} (see above); check has no failing report to gate, so the chain stops here" in c.out
    assert c.steps[-1] == "shot --motion motion/proof.json" and not c.ran("frames") and not c.ran("book"), c.steps


def test_a_brand_that_moves_with_no_proof_file_goes_on_and_says_which_file_is_missing(tmp_path):
    c = chain(tmp_path, decision=ON, proof=None)
    assert c.code == 0, c.out
    assert c.out.count("finish.sh: motion/motion.json says the brand moves, but there is no motion/proof.json to prove the approved move: write it, then run `brand-creator shot --motion motion/proof.json`") == 1
    assert "finish.sh: no stills taken: motion/proof.json is missing, cannot be read or has no page case" in c.out
    assert not c.ran("shot") and not c.ran("frames") and c.ran("book") and c.ran("check")
    c.in_order(["gates", "motion", "book", "book-pdf", "emit presskit"])


def test_a_brand_that_does_not_move_says_so_and_takes_no_proof_and_no_stills(tmp_path):
    c = chain(tmp_path, decision=OFF)
    assert c.code == 0, c.out
    assert "nothing moves: The brand lives on paper and in a shop window." in c.out                     # printed, not skipped in silence
    assert "finish.sh: no stills taken: nothing moves (motion/motion.json), so the Motion chapter has nothing to replay" in c.out
    assert not c.ran("shot") and not c.ran("frames")
    c.in_order(["gates", "motion", "book", "book-pdf", "emit presskit"])


def test_a_brand_with_no_decision_on_motion_goes_on_and_says_so(tmp_path):
    c = chain(tmp_path, decision=UNDECIDED)
    assert c.code == 0 and c.out.count(NOT_DECIDED_LINE) == 1, c.out
    assert "finish.sh: no stills taken: motion is not decided, so the Motion chapter has no replay" in c.out
    assert not c.ran("shot") and not c.ran("frames") and c.ran("check")
    c.in_order(["gates", "motion", "book", "book-pdf", "emit presskit"])


def test_a_motion_json_that_is_not_valid_stops_the_chain_at_the_motion_step_with_exit_2(tmp_path):
    c = chain(tmp_path, decision=ON, answers={"motion": {"code": 2, "err": "error: motion/motion.json: cannot be read as JSON"}})
    assert c.code == 2 and "error: motion/motion.json: cannot be read as JSON" in c.out, c.out
    assert c.steps[-1] == "motion" and not c.ran("shot") and not c.ran("book"), c.steps
    assert "motion is not decided" not in c.out and "nothing moves" not in c.out                         # an unreadable answer is not read as "not decided"


def test_the_quick_chain_has_no_motion_step_and_takes_no_stills(tmp_path):
    """Quick decides motion at G4, and only when something moves: no step and no line, even for a brand that moves with a page to take stills of."""
    c = chain(tmp_path, tier="quick", decision=ON)
    assert c.code == 0, c.out
    assert not any(s.startswith(("motion", "shot --motion", "frames")) for s in c.steps) and "book" in c.steps and "book-pdf" in c.steps, c.steps
    assert "nothing moves" not in c.out and "motion is not decided" not in c.out and "motion is on" not in c.out
    assert not c.ran("motion") and not c.ran("shot") and not c.ran("frames")


# ---------------------------------------------------------------- the stills: taken before the book; a page frames cannot step through does not stop the chain

def test_a_page_frames_cannot_step_through_does_not_stop_the_chain(tmp_path):
    c = chain(tmp_path, decision=ON, answers={"frames": {"code": 1, "err": "frames: no seekable motion in demo-page"}})
    assert c.code == 0 and c.out.count(STILLS_LINE) == 1, c.out
    assert c.out.index("frames: no seekable motion in demo-page") < c.out.index(STILLS_LINE)              # the reason `frames` gave is the "see above"
    c.in_order(["gates", "frames motion/proof.json --count 25", "book", "book-pdf", "emit presskit"])     # the book, its PDF and the kit are still built


@pytest.mark.parametrize("code", [2, 3])
def test_any_other_failure_of_frames_stops_the_chain_with_its_exit_code(tmp_path, code):
    c = chain(tmp_path, decision=ON, answers={"frames": {"code": code}})
    assert c.code == code, c.out
    assert f"finish.sh: frames stopped with exit {code} (see above); check has no failing report to gate, so the chain stops here" in c.out and STILLS_LINE not in c.out
    assert c.steps[-1] == "frames motion/proof.json --count 25" and not c.ran("book") and not c.ran("check"), c.steps


def test_frames_args_in_block_2_sets_the_stills_without_editing_the_chain(tmp_path):
    c = chain(tmp_path, decision=ON, FRAMES_ARGS="--count 20")
    assert c.code == 0 and "frames motion/proof.json --count 20" in c.steps, c.out
    assert ["frames", "motion/proof.json", "--count", "20"] in c.calls, c.calls


def test_stills_are_taken_only_of_a_proof_with_a_page_case(tmp_path):
    c = chain(tmp_path, decision=ON, proof="states")
    assert c.code == 0 and not c.ran("frames"), c.calls
    assert "finish.sh: no stills taken: motion/proof.json is missing, cannot be read or has no page case" in c.out


def test_a_book_that_refuses_stops_the_chain_with_its_exit_code_before_its_pdf(tmp_path):
    """For example a motion/motion.json that names a token that is not built: `motion --json` reads the answer alone and goes on, the book refuses."""
    c = chain(tmp_path, decision=ON, answers={"book": {"code": 2, "err": "error: motion/motion.json: no token named motion.nowhere"}})
    assert c.code == 2 and c.steps[-1] == "book" and not c.ran("book-pdf") and not c.ran("check"), (c.steps, c.out)
    assert "error: motion/motion.json: no token named motion.nowhere" in c.out                                 # and its reason is shown


# ---------------------------------------------------------------- the board of the latest round is linted again, so an edit of the facts or the brief is picked up

LINT = "board-lint rounds/r2/board.html"
LINT_REPORT = "assets/_checks/board-lint.json"


def test_the_board_of_the_latest_round_is_linted_again_after_the_press_kit_and_before_staleness_and_check(tmp_path):
    """board-lint lists FACTS.md and brief/BRIEF.md as inputs and `check` wants a current report of the latest round: without this step an edit of either
    turns `check` not verified until board-lint is run by hand. The earlier rounds are not linted; the chain is the same as before apart from this step."""
    c = chain(tmp_path, decision=OFF, rounds={0: True, 1: True, 2: True})
    assert c.code == 0, c.out
    assert c.calls.count(["board-lint", "rounds/r2/board.html"]) == 1 and sum(1 for x in c.calls if x[:1] == ["board-lint"]) == 1, c.calls
    c.in_order(["gates", "book", "book-pdf", "emit presskit", LINT])
    names = [x[0] if x[0] != "emit" else " ".join(x[:2]) for x in c.calls]
    assert names.index("board-lint") < names.index("staleness") < names.index("check") and names.index("emit presskit") < names.index("board-lint"), names


def test_the_latest_round_counts_by_its_number_not_by_its_name(tmp_path):
    c = chain(tmp_path, decision=OFF, rounds={2: True, 10: True, 9: True})
    assert c.code == 0 and [x for x in c.calls if x[:1] == ["board-lint"]] == [["board-lint", "rounds/r10/board.html"]], c.calls


@pytest.mark.parametrize("what, rounds", [("no rounds folder", None), ("a latest round with no board.html", {1: True, 2: False})])
def test_no_board_to_lint_means_no_lint_step(tmp_path, what, rounds):
    """The board `check` looks for is rounds/rN/board.html of the highest N: when it is not there, `check` expects no board-lint report and the chain runs none."""
    c = chain(tmp_path, decision=OFF, rounds=rounds)
    assert c.code == 0 and not c.ran("board-lint") and not any(s.startswith("board-lint") for s in c.steps), (what, c.calls)
    assert c.ran("staleness", "--write") and c.ran("check")


def test_a_board_that_fails_its_lint_does_not_stop_the_chain_check_fails_the_report(tmp_path):
    rep = tmp_path / "project" / LINT_REPORT
    c = chain(tmp_path, decision=OFF, rounds={2: True}, answers={"board-lint": {"code": 1, "out": f"[FAIL] page:unfilled\nreport: {rep}", "write": [str(rep)]}})
    assert c.code == 0, c.out
    assert c.out.count(f"finish.sh: board-lint failed on rounds/r2/board.html (see above); the chain goes on and check fails the report") == 1, c.out
    assert "[FAIL] page:unfilled" in c.out                                                              # the lint's own words are shown
    assert c.ran("staleness", "--write") and c.ran("check") and c.steps[-1] == LINT, (c.steps, c.calls)


def test_a_board_the_lint_could_not_verify_goes_on_because_it_wrote_its_report(tmp_path):
    rep = tmp_path / "project" / LINT_REPORT
    c = chain(tmp_path, decision=OFF, rounds={2: True}, answers={"board-lint": {"code": 3, "out": f"[SKIP] reflex-grounded\nreport: {rep}", "write": [str(rep)]}})
    assert c.code == 0, c.out
    assert c.out.count("finish.sh: board-lint could not verify rounds/r2/board.html (see above); the chain goes on and check says why") == 1, c.out
    assert "[SKIP] reflex-grounded" in c.out and c.ran("staleness", "--write") and c.ran("check")


REFUSED = "page rounds/r2/board.html is outside the project /tmp/project; brand-creator only writes inside the project"   # what the real lint says of a board.html that is a link to a file outside the project (exit 2)


def failed_step(code: int, why: str = REFUSED) -> str:
    return f"finish.sh: step failed: {LINT} stopped with exit {code} and left no report of this board: {why}. The chain goes on, so that check still writes the pack report"


@pytest.mark.parametrize("what, answer, code, why", [
    ("a board it refuses with a usage error (exit 2: a board.html that is a link to a file outside the project)", {"code": 2, "err": f"error: {REFUSED}"}, 2, REFUSED),
    ("an exit 1 that wrote no report", {"code": 1, "out": "report: assets/_checks/board-lint.json"}, 1, "it printed no reason, see above"),
    ("an exit 3 that wrote no report", {"code": 3}, 3, "it printed no reason, see above"),
])
def test_a_board_the_lint_refuses_does_not_stop_the_chain_before_check_and_is_reported_as_a_failed_step(tmp_path, what, answer, code, why):
    """A lint that leaves no report of the latest board (it refuses the board, as with a board.html that is a link to a file outside the project, or it crashes) used to stop the
    chain, so no pack report was written at all. Now the step is reported as failed, with the lint's own message, the chain goes on to staleness and `check` (which says the board is not verified), and it
    ends with a non-zero exit code even if `check` passes: it never passes in silence."""
    c = chain(tmp_path, decision=OFF, rounds={2: True}, answers={"board-lint": answer})
    assert failed_step(code, why) in c.out, (what, c.out)
    assert c.out.count("finish.sh: step failed:") == 1 and c.out.count("finish.sh: check passed, but a step failed") == 1, c.out
    assert why in c.out and c.ran("staleness", "--write") and c.ran("check"), (what, c.calls)
    assert c.code == code, (what, c.code, c.out)                                                      # check passed in the stand-in: the lint's own exit code ends the chain
    assert [x[0] for x in c.calls][-2:] == ["staleness", "check"], c.calls
    assert f"finish.sh: check passed, but a step failed (board-lint {LINT.split()[1]}): the chain ends with exit {code}" in c.out


def test_when_check_fails_too_after_a_refused_board_the_chain_ends_with_the_exit_code_of_check(tmp_path):
    c = chain(tmp_path, decision=OFF, rounds={2: True}, answers={"board-lint": {"code": 2, "err": f"error: {REFUSED}"}, "check": {"code": 1, "out": "check: FAIL report:board-lint"}})
    assert c.code == 1 and "check: FAIL report:board-lint" in c.out and failed_step(2) in c.out, c.out
    assert c.ran("staleness", "--write") and c.ran("check") and "check passed, but a step failed" not in c.out


def test_a_board_that_lints_clean_ends_the_chain_with_the_exit_code_of_check_and_no_failed_step(tmp_path):
    c = chain(tmp_path, decision=OFF, rounds={2: True}, answers={"check": {"code": 3, "out": "check: not verified"}})
    assert c.code == 3 and "step failed" not in c.out and "check passed, but" not in c.out, c.out


# ---------------------------------------------------------------- the brand's generated adapter files are written again after the tokens, before the last lint, staleness and check

ADAPTERS = "--brand-md --design-md --primary accent"
SKILL = ".claude/skills/acme-brand/SKILL.md"
KIT = ".claude/skills/acme-brand/kit.json"
EDITED = "BRAND.md differs from what was last generated: it was edited by hand. Change the sources (tokens, FACTS.md, BRAND-STATE.md) instead, or re-run with --replace to move it to removed-2026-10-17/ and write a new one"


def names(c: Chain) -> list[str]:
    """What the calls asked for, in order: an emit or kit call by its first two words, any other by its command."""
    return [" ".join(x[:2]) if x[0] in ("emit", "kit") else x[0] for x in c.calls]


def failed(cmd: str, code: int, why: str) -> str:
    return f"finish.sh: step failed: {cmd} stopped with exit {code}: {why}. The chain goes on, so that check still writes the pack report"


def test_the_adapter_files_and_the_applied_skill_are_written_again_after_the_tokens_and_the_press_kit_and_before_the_last_lint_staleness_and_check(tmp_path):
    """A token, FACTS.md or BRAND-STATE.md that changed since BRAND.md, DESIGN.md or the applied skill were written leaves `check` with a stale report: the chain writes them again, with the options the
    owner gave `adapters` (ADAPTERS_ARGS of block 2), once everything built from the tokens is done and before `staleness --write` records the pack."""
    c = chain(tmp_path, decision=OFF, rounds={2: True}, files=("BRAND.md", "DESIGN.md", SKILL), ADAPTERS_ARGS=ADAPTERS)
    assert c.code == 0, c.out
    assert c.calls.count(["adapters", "--brand-md", "--design-md", "--primary", "accent"]) == 1 and c.calls.count(["applied-skill", "--yes"]) == 1, c.calls
    assert not c.ran("kit"), c.calls                                                        # no kit.json: the applied skill is the skill
    c.in_order(["tokens", "contrast", "emit web", "gates", "book", "book-pdf", "emit presskit", "adapters --brand-md --design-md --primary accent", "applied-skill --yes", LINT])
    n = names(c)
    assert n.index("tokens") < n.index("contrast") < n.index("emit presskit") < n.index("adapters") < n.index("applied-skill") < n.index("board-lint") < n.index("staleness") < n.index("check"), n


def test_with_a_kit_the_kit_is_built_and_checked_again_and_the_applied_skill_is_left_to_it(tmp_path):
    """The kit's SKILL.md is the kit's to write (`applied-skill` refuses there): the chain builds the kit, and checks it, since a built kit makes the last `kit check` report stale."""
    c = chain(tmp_path, decision=OFF, files=("BRAND.md", SKILL, KIT), ADAPTERS_ARGS="--brand-md")
    assert c.code == 0, c.out
    assert c.calls.count(["kit", "build", "--yes"]) == 1 and c.calls.count(["kit", "check"]) == 1 and not c.ran("applied-skill"), c.calls
    c.in_order(["emit presskit", "adapters --brand-md", "kit build --yes", "kit check"])
    n = names(c)
    assert n.index("adapters") < n.index("kit build") < n.index("kit check") < n.index("staleness") < n.index("check"), n


def test_a_project_with_none_of_them_runs_no_command_and_says_so(tmp_path):
    c = chain(tmp_path, decision=OFF, ADAPTERS_ARGS=ADAPTERS)                               # the option is set, but there is nothing to write again
    assert c.code == 0, c.out
    assert not (c.ran("adapters") or c.ran("applied-skill") or c.ran("kit")), c.calls
    assert "adapters, applied skill, kit: skipped (the project has no BRAND.md, DESIGN.md, applied skill or kit: they are opt-in at G5)" in c.steps
    assert c.ran("staleness", "--write") and c.ran("check")


def test_a_skill_folder_of_another_name_is_not_this_projects_brand_skill(tmp_path):
    c = chain(tmp_path, decision=OFF, files=(".claude/skills/other-brand/SKILL.md", ".claude/skills/other-brand/kit.json"))
    assert c.code == 0 and not c.ran("applied-skill") and not c.ran("kit"), c.calls         # the folder is `.claude/skills/<slug>-brand`, as `check` finds it
    assert any(s.startswith("adapters, applied skill, kit: skipped") for s in c.steps), c.steps


def test_a_slug_that_is_not_set_means_no_skill_folder_and_is_no_failed_step(tmp_path):
    c = chain(tmp_path, decision=OFF, files=(SKILL, KIT), answers={"slug_fails": {"code": 1, "err": "error: slug is not set in BRAND-STATE.md"}})
    assert c.code == 0 and "step failed" not in c.out, c.out                                  # what `state --get` says of a key that is not there: exit 1, "<key> is not set in BRAND-STATE.md"
    assert not c.ran("applied-skill") and not c.ran("kit") and c.ran("check")
    assert any(s.startswith("adapters, applied skill, kit: skipped") for s in c.steps), c.steps


@pytest.mark.parametrize("code, err", [
    (2, "error: BRAND-STATE.md has no frontmatter (first line must be ---)"),
    (3, "error: cannot read BRAND-STATE.md"),
    (1, "error: something else went wrong in state"),
])
def test_a_state_that_cannot_be_read_is_a_failed_step_with_its_message_and_the_chain_still_runs_check(tmp_path, code, err):
    c = chain(tmp_path, decision=OFF, files=(SKILL, KIT), answers={"slug_fails": {"code": code, "err": err}})
    assert failed("state --get slug", code, err.removeprefix("error: ")) in c.out and c.out.count("finish.sh: step failed:") == 1, c.out
    assert not c.ran("applied-skill") and not c.ran("kit") and c.ran("staleness", "--write") and c.calls.count(["check"]) == 1, c.calls    # nothing is guessed about the skill; check still writes the pack report
    assert c.code == code and f"check passed, but a step failed (state --get slug): the chain ends with exit {code}" in c.out, c.out


def test_adapter_files_with_no_options_to_write_them_again_are_left_alone_and_the_line_says_which_variable_to_set(tmp_path):
    c = chain(tmp_path, decision=OFF, files=("BRAND.md", "DESIGN.md", SKILL))
    assert c.code == 0, c.out
    assert not c.ran("adapters"), c.calls
    why = next(s for s in c.steps if s.startswith("adapters: skipped"))
    assert "ADAPTERS_ARGS in block 2 is empty" in why and '"--brand-md --design-md"' in why, why
    assert c.ran("applied-skill", "--yes") and c.ran("staleness", "--write") and c.ran("check")   # the skill has no options of its own: it is written again


def test_an_adapter_file_that_refuses_is_a_failed_step_with_its_message_and_the_chain_goes_on_to_check_and_ends_with_its_exit_code(tmp_path):
    c = chain(tmp_path, decision=OFF, files=("BRAND.md", SKILL), ADAPTERS_ARGS="--brand-md", answers={"adapters": {"code": 1, "err": f"error: {EDITED}"}})
    assert failed("adapters --brand-md", 1, EDITED) in c.out and c.out.count("finish.sh: step failed:") == 1, c.out
    assert c.ran("applied-skill", "--yes") and c.ran("staleness", "--write") and c.ran("check")   # what can still be written is, and check still writes the pack report
    assert [x[0] for x in c.calls][-2:] == ["staleness", "check"]
    assert c.code == 1 and "finish.sh: check passed, but a step failed (adapters --brand-md): the chain ends with exit 1" in c.out, c.out


def test_a_design_file_that_could_not_be_linted_ends_the_chain_with_exit_3_though_check_passed(tmp_path):
    """`adapters` writes both files and exits 3 when @google/design.md is not installed: not verified, never a pass. It prints no `error:` line, so the step says where its reason is."""
    c = chain(tmp_path, decision=OFF, files=("DESIGN.md",), ADAPTERS_ARGS="--design-md", answers={"adapters": {"code": 3, "out": "[SKIP] design-md:lint (DESIGN.md linted by @google/design.md): not verified: the package is not installed"}})
    assert failed("adapters --design-md", 3, "the reason is printed above") in c.out and "[SKIP] design-md:lint" in c.out, c.out
    assert c.code == 3 and c.ran("check") and "check passed, but a step failed (adapters --design-md): the chain ends with exit 3" in c.out, c.out


def test_a_skill_that_refuses_is_a_failed_step_too(tmp_path):
    c = chain(tmp_path, decision=OFF, files=(SKILL,), answers={"applied-skill": {"code": 1, "err": "error: .claude/skills/acme-brand/SKILL.md differs from what was last generated: it was edited by hand"}})
    assert failed("applied-skill --yes", 1, ".claude/skills/acme-brand/SKILL.md differs from what was last generated: it was edited by hand") in c.out, c.out
    assert c.code == 1 and c.ran("check") and "check passed, but a step failed (applied-skill --yes)" in c.out


def test_a_kit_that_refuses_is_a_failed_step_and_is_not_checked_as_if_it_had_been_built(tmp_path):
    c = chain(tmp_path, decision=OFF, files=(SKILL, KIT), answers={"kit build": {"code": 1, "err": "error: 2 files of the kit were edited by hand: brand/assets/tokens/tokens.css"}})
    assert failed("kit build --yes", 1, "2 files of the kit were edited by hand: brand/assets/tokens/tokens.css") in c.out, c.out
    assert not c.ran("kit", "check") and c.ran("staleness", "--write") and c.ran("check")
    assert c.code == 1 and "check passed, but a step failed (kit build --yes)" in c.out


def test_a_kit_check_that_fails_is_a_failed_step_whose_report_is_above(tmp_path):
    c = chain(tmp_path, decision=OFF, files=(SKILL, KIT), answers={"kit check": {"code": 1, "out": "[FAIL] kit:fill (no fill marker is left in the kit): 3 fill marker(s) left"}})
    assert failed("kit check", 1, "the reason is printed above") in c.out and "[FAIL] kit:fill" in c.out, c.out
    assert c.code == 1 and "check passed, but a step failed (kit check)" in c.out


def test_when_check_fails_too_after_a_refused_step_the_chain_ends_with_the_exit_code_of_check(tmp_path):
    c = chain(tmp_path, decision=OFF, files=("BRAND.md",), ADAPTERS_ARGS="--brand-md",
              answers={"adapters": {"code": 1, "err": f"error: {EDITED}"}, "check": {"code": 3, "out": "check: not verified"}})
    assert c.code == 3 and failed("adapters --brand-md", 1, EDITED) in c.out and "check passed, but a step failed" not in c.out, c.out


def test_the_first_of_two_failed_steps_decides_the_exit_code_and_both_are_said(tmp_path):
    c = chain(tmp_path, decision=OFF, files=("BRAND.md", SKILL, KIT), ADAPTERS_ARGS="--brand-md",
              answers={"adapters": {"code": 1, "err": f"error: {EDITED}"}, "kit build": {"code": 2, "err": "error: no --yes"}})
    assert c.out.count("finish.sh: step failed:") == 2 and failed("kit build --yes", 2, "no --yes") in c.out, c.out
    assert c.code == 1 and c.out.count("check passed, but a step failed (adapters --brand-md): the chain ends with exit 1") == 1 and c.calls.count(["check"]) == 1, c.out


def test_a_refused_board_and_a_refused_adapter_file_run_check_once_and_the_chain_does_not_pass(tmp_path):
    c = chain(tmp_path, decision=OFF, rounds={2: True}, files=("BRAND.md",), ADAPTERS_ARGS="--brand-md",
              answers={"board-lint": {"code": 2, "err": f"error: {REFUSED}"}, "adapters": {"code": 1, "err": f"error: {EDITED}"}})
    assert c.out.count("finish.sh: step failed:") == 2 and failed("adapters --brand-md", 1, EDITED) in c.out and failed_step(2) in c.out, c.out
    assert c.calls.count(["check"]) == 1 and c.code == 1, c.out                              # the adapter file is the first failed step of the chain: its exit code ends it, and the later refused board does not hide it
    assert "check passed, but a step failed (adapters --brand-md): the chain ends with exit 1" in c.out and "check passed, but a step failed (board-lint" not in c.out


# ---------------------------------------------------------------- the book, the press kit, print and posts, by tier

def test_without_chapters_the_book_is_skipped_loudly_and_the_press_kit_is_told_it_has_no_book(tmp_path):
    c = chain(tmp_path, decision=UNDECIDED, book=False)
    assert c.code == 0, c.out
    assert "book: skipped (no book/chapters/: start one with brand-creator book --init and fill it)" in c.steps
    assert not c.ran("book") and not c.ran("book-pdf") and ["emit", "presskit", "--no-book"] in c.calls, c.calls
    c.in_order(["emit web", "emit profiles", "gates", "book: skipped", "emit presskit"])


def test_print_is_emitted_only_when_the_owner_opted_in_with_a_region(tmp_path):
    c = chain(tmp_path, decision=OFF)
    assert c.code == 0 and not c.ran("emit", "print") and not c.ran("print-check"), c.calls
    assert not any(s.startswith(("emit print", "print-check")) for s in c.steps), c.steps
    c = chain(tmp_path / "eu", decision=OFF, PRINT_REGION="EU")
    assert c.ran("emit", "print", "--region", "EU") and c.ran("print-check"), c.calls


def test_with_a_book_the_press_kit_holds_it(tmp_path):
    c = chain(tmp_path, decision=OFF)
    assert ["emit", "presskit"] in c.calls and ["emit", "presskit", "--no-book"] not in c.calls, c.calls


@pytest.mark.parametrize("env", [{"PRINT_REGION": "EU"}, {"POST_FACTS": "spare parts"}])
def test_a_value_for_a_step_the_tier_does_not_allow_stops_the_chain_before_any_step(tmp_path, env):
    c = chain(tmp_path, tier="quick", **env)
    assert c.code == 2 and "Standard and Full tier" in c.out and "state --set tier=standard" in c.out, c.out
    assert c.steps == [] and not c.ran("emit")                                                          # not one step ran


def test_the_quick_chain_keeps_its_shape_profiles_but_no_press_kit_no_print(tmp_path):
    c = chain(tmp_path, tier="quick", decision=UNDECIDED)
    assert c.code == 0, c.out
    assert not any(s.startswith(("emit print", "emit presskit", "emit android")) for s in c.steps), c.steps
    assert c.ran("emit", "profiles") and not c.ran("emit", "presskit") and not c.ran("emit", "print")


def test_print_posts_and_a_tagline_reach_each_emitter_as_whole_arguments(tmp_path):
    """Option values with spaces stay one argument, in the emitter's call and in the idempotence run that repeats it."""
    c = chain(tmp_path, decision=OFF, targets="web social", TAGLINE=TAG, PRINT_REGION="EU", IMAGE_BASE_URL="https://img.example.com/brand", POST_FACTS="spare parts;repair guide;batch size")
    assert c.code == 0, c.out
    c.in_order(["tokens", "contrast", "emit web", "emit social", "emit profiles", "emit print", "print-check", "gates", "book", "book-pdf", "emit presskit"])
    assert ["emit", "social", "--tagline", TAG, "--posts", "--post-fact", "spare parts", "--post-fact", "repair guide", "--post-fact", "batch size"] in c.calls, c.calls
    assert ["emit", "print", "--region", "EU", "--tagline", TAG, "--image-base-url", "https://img.example.com/brand"] in c.calls, c.calls
    idem = next(x for x in c.calls if x[0] == "verify-idempotent")
    social = next(x for x in idem if x.startswith("{bc} emit social "))
    assert "--tagline a\\ repair\\ guide\\ is\\ in\\ every\\ box" in social and "--post-fact spare\\ parts" in social, social
