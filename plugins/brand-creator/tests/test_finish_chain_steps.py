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
          answers: dict | None = None, targets: str = "web", **env: str) -> Chain:
    """Fill the template (block 2's targets: `targets`; no apple line) into a bare project and run it against the stand-in. `decision` is what `motion --json`
    answers and what motion/motion.json says (the frames step reads the file itself); `proof` writes motion/proof.json with a page case ("page"),
    with a named-state case only ("states"), or not at all (None); `answers` maps a call ("shot", "frames", "emit presskit", ...) to
    {"code": n, "out": text, "err": text, "write": [project files]}."""
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
    scenario.write_text(json.dumps({"tier": tier, "decision": decision, **(answers or {})}))
    run_env = {k: v for k, v in os.environ.items() if k not in ("BRAND_CREATOR_ROOT", "PRINT_REGION", "POST_FACTS", "FRAMES_ARGS", "TAGLINE")}
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
