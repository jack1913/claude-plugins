"""The motion decision: `brand-creator motion` (scripts/motion.py), the line `state` prints, and the rows `check` holds Standard and Full to (motion:decided, motion:proof).

Standard and Full decide motion for every brand before G4: a motion round after G3 (the default), or "nothing moves", recorded once by the owner. motion/motion.json is the one
record (absent: not decided). Quick keeps its own rule: motion is decided at G4 and only when something moves, so it gets no row. These tests need no browser: the gated
motion reports are written by hand, the way tests/test_qa_infra.py writes them."""
import json
from pathlib import Path

import pytest
from helpers import ROOT, bc, failing, make_project, mutate, mutate_json, report

SPEC = "motion/motion.json"
DECIDE = 'run the motion round, or record nothing moves with `brand-creator motion --off "<the owner\'s reason>"`'
ON = {"schema": 1, "motion": "on", "signature": {"name": "Settle", "description": "The dot settles onto the grid.", "where": ["app icon"]}}
OFF = {"schema": 1, "motion": "off", "reason": "The brand has no screen presence."}
ON_TIMELINE = {**ON, "parts": [{"id": "dot", "description": "The accent dot of the mark."}],      # a timeline names a duration and a curve, which are tokens
               "timeline": [{"part": "dot", "property": "transform", "start": "0", "duration": "{motion.base}", "easing": "{easing.standard}"}]}


def project(tmp_path: Path, tier: str = "standard", gates=()) -> Path:
    p = make_project(tmp_path, tier=tier)
    for g in gates:
        assert bc("state", "--record", g, f"recorded for the test ({g})", project=p).returncode == 0
    return p


def write_spec(p: Path, doc) -> Path:
    (p / "motion").mkdir(exist_ok=True)
    f = p / SPEC
    f.write_text(doc if isinstance(doc, str) else json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    return f


def motion(p: Path, *args: str):
    return bc("motion", *args, project=p)


# ---------------------------------------------------------------- brand-creator motion

def test_motion_prints_the_status_line_for_each_answer_and_exits_0(tmp_path):
    p = project(tmp_path, "quick")
    r = motion(p)
    assert (r.returncode, r.stdout) == (0, "motion: not decided\n")
    write_spec(p, OFF)
    r = motion(p)
    assert (r.returncode, r.stdout) == (0, "motion: off (nothing moves: The brand has no screen presence.)\n")
    write_spec(p, ON)
    r = motion(p)
    assert (r.returncode, r.stdout) == (0, "motion: on (signature: Settle)\n")
    write_spec(p, {**OFF, "reason": "Nothing\n  moves,   on purpose."})              # the line is one line whatever the owner typed
    assert motion(p).stdout == "motion: off (nothing moves: Nothing moves, on purpose.)\n"


@pytest.mark.parametrize("tier, gates, due", [("standard", (), False), ("standard", ("G3",), True), ("full", ("G3",), True), ("full", ("G3", "G4"), True),
                                              ("quick", ("G3",), False), ("quick", ("G3", "G4"), False), ("full", ("G1s",), False)])
def test_when_nothing_is_decided_standard_and_full_say_what_is_due_before_g4_once_g3_is_recorded(tmp_path, tier, gates, due):
    p = project(tmp_path, tier, gates)
    r = motion(p)
    assert r.returncode == 0
    want = "motion: not decided\n" + (f"due before G4: {DECIDE}\n" if due else "")
    assert r.stdout == want, (tier, gates, r.stdout)
    for answer in (OFF, ON):                                                          # an answer needs no reminder
        write_spec(p, answer)
        assert "due before G4" not in motion(p).stdout


def test_motion_json_prints_the_decision_as_data(tmp_path):
    p = project(tmp_path, "standard", ("G3",))
    assert json.loads(motion(p, "--json").stdout) == {"motion": "undecided"}
    write_spec(p, OFF)
    assert json.loads(motion(p, "--json").stdout) == {"motion": "off", "reason": "The brand has no screen presence."}
    write_spec(p, ON)
    assert json.loads(motion(p, "--json").stdout) == {"motion": "on", "signature": "Settle"}


def test_a_motion_json_that_is_not_valid_exits_2_with_the_message_of_the_spec_and_is_never_read_as_an_answer(tmp_path):
    p = project(tmp_path)
    f = write_spec(p, {**ON, "schema": 2})
    for args in ((), ("--json",), ("--off", "nothing moves")):
        r = motion(p, *args)
        assert r.returncode == 2 and "motion/motion.json: schema: must be 1" in r.stderr, (args, r.stderr)
        assert r.stdout == ""
    f.write_text("{not json")
    r = motion(p, "--off", "x")
    assert r.returncode == 2 and "motion/motion.json: cannot be read as JSON" in r.stderr
    assert f.read_text() == "{not json"                                              # nothing was written over it


def test_an_answer_that_names_tokens_not_built_yet_is_still_the_answer_and_only_the_spec_row_of_check_says_they_are_missing(tmp_path):
    """The motion round comes before the tokens are built, so a spec can name `{motion.base}` while assets/tokens/ is empty: the answer does not wait for them."""
    p = project(tmp_path, "standard", ("G3",))
    write_spec(p, ON_TIMELINE)
    assert not (p / "assets" / "tokens" / "tokens.json").exists()
    r = motion(p)
    assert (r.returncode, r.stdout, r.stderr) == (0, "motion: on (signature: Settle)\n", "")
    assert json.loads(motion(p, "--json").stdout) == {"motion": "on", "signature": "Settle"}
    before = (p / SPEC).read_bytes()
    r = motion(p, "--off", "nothing moves after all")
    assert r.returncode == 2 and r.stdout == "" and "says the brand moves (signature Settle); turning it off is a rule change" in r.stderr, r.stderr    # the refusal, not a message about tokens
    assert (p / SPEC).read_bytes() == before
    out = bc("state", project=p).stdout
    assert "motion: on (signature: Settle)" in out and "cannot be read" not in out
    assert json.loads(bc("state", "--json", project=p).stdout)["motion"] == {"motion": "on", "signature": "Settle"}
    check(p)
    got = row(p, "motion:spec")                                                              # where the missing tokens are said
    assert got["status"] == "skipped" and got["detail"].startswith("not verified: ") and "brand-creator tokens" in got["detail"], got
    for broken, why in (({**ON_TIMELINE, "schema": 2}, "schema: must be 1"), ({**ON_TIMELINE, "signature": {}}, "signature.name: required")):     # wrong in itself: exit 2 whatever the tokens
        write_spec(p, broken)
        for args in ((), ("--json",), ("--off", "nothing moves")):
            r = motion(p, *args)
            assert r.returncode == 2 and r.stdout == "" and why in r.stderr, (args, r.stdout, r.stderr)
    write_spec(p, {**ON_TIMELINE, "schema": 2, "timeline": [{**ON_TIMELINE["timeline"][0], "easing": "{easing.nowhere}"}]})
    assert "schema: must be 1" in motion(p).stderr and motion(p).returncode == 2


def test_off_records_nothing_moves_in_the_owners_words_and_creates_the_folder(tmp_path):
    p = project(tmp_path, "standard", ("G3",))
    assert not (p / "motion").exists()
    r = motion(p, "--off", "  The brand lives on paper and in a shop window.  ")
    assert r.returncode == 0, r.stderr
    assert r.stdout == "recorded: nothing moves (The brand lives on paper and in a shop window.) in motion/motion.json\n"
    assert json.loads((p / SPEC).read_text(encoding="utf-8")) == {"schema": 1, "motion": "off", "reason": "The brand lives on paper and in a shop window."}
    assert motion(p).stdout == "motion: off (nothing moves: The brand lives on paper and in a shop window.)\n"
    unicode_reason = tmp_path / "u"
    unicode_reason.mkdir()
    q = project(unicode_reason)
    assert motion(q, "--off", "Żadnego ruchu: marka żyje na papierze.").returncode == 0
    assert json.loads((q / SPEC).read_text(encoding="utf-8"))["reason"] == "Żadnego ruchu: marka żyje na papierze."


def test_off_twice_writes_nothing_and_a_different_reason_says_the_recorded_one_stands(tmp_path):
    p = project(tmp_path)
    assert motion(p, "--off", "The brand has no screen presence.").returncode == 0
    f = p / SPEC
    before, stamp = f.read_bytes(), f.stat().st_mtime_ns
    r = motion(p, "--off", "The brand has no screen presence.")
    assert r.returncode == 0 and r.stdout == "already recorded: nothing moves (The brand has no screen presence.)\n"
    r = motion(p, "--off", "Because the owner changed their mind.")
    assert r.returncode == 0
    assert r.stdout.splitlines()[0] == "already recorded: nothing moves (The brand has no screen presence.)"
    assert "the recorded reason stands" in r.stdout and f"changing it is an edit of {SPEC} followed by `brand-creator check --cascade`" in r.stdout
    assert f.read_bytes() == before and f.stat().st_mtime_ns == stamp                  # not rewritten either time


def test_off_is_refused_when_the_spec_says_the_brand_moves(tmp_path):
    p = project(tmp_path)
    write_spec(p, ON)
    before = (p / SPEC).read_bytes()
    r = motion(p, "--off", "nothing moves after all")
    assert r.returncode == 2 and r.stdout == ""
    assert ("motion/motion.json says the brand moves (signature Settle); turning it off is a rule change: edit motion/motion.json and run `brand-creator check --cascade`") in r.stderr
    assert (p / SPEC).read_bytes() == before


@pytest.mark.parametrize("reason", ["", "   ", "\n\t"])
def test_off_needs_a_reason_and_writes_nothing_without_one(tmp_path, reason):
    p = project(tmp_path)
    r = motion(p, "--off", reason)
    assert r.returncode == 2 and "motion/motion.json: reason: must be a non-empty string" in r.stderr and 'motion --off "<the owner\'s reason>"' in r.stderr
    assert not (p / "motion").exists()
    assert motion(project(tmp_path / "again", "quick"), "--off", reason).returncode == 2


def test_a_blank_reason_is_refused_even_when_motion_is_already_off(tmp_path):
    p = project(tmp_path)
    assert motion(p, "--off", "The brand has no screen presence.").returncode == 0
    r = motion(p, "--off", "  ")
    assert r.returncode == 2 and r.stdout == "" and "reason: must be a non-empty string" in r.stderr


def test_off_takes_the_json_flag_only_apart_and_unknown_words_are_usage_errors(tmp_path):
    p = project(tmp_path)
    assert motion(p, "--off", "x", "--json").returncode == 2 and not (p / "motion").exists()
    assert motion(p, "maybe").returncode == 2
    assert motion(p, "--on").returncode == 2                                           # there is no way to say "moves" here: that is the motion round
    assert motion(p, "--off").returncode == 2


def test_the_entry_point_lists_motion_and_runs_it_outside_a_project_only_with_a_project_flag(tmp_path):
    usage = bc("help").stdout
    assert any(ln.startswith("  motion ") and "--off" in ln for ln in usage.splitlines())
    r = bc("motion", cwd=tmp_path)
    assert r.returncode == 2 and "no brand project found" in r.stderr


# ---------------------------------------------------------------- brand-creator state

def test_the_state_summary_prints_the_same_line_so_step_0_sees_the_decision(tmp_path):
    p = project(tmp_path, "standard", ("G3",))
    out = bc("state", project=p).stdout
    assert "motion: not decided\ndue before G4: " + DECIDE in out
    write_spec(p, OFF)
    assert bc("state", project=p).stdout.count("motion: off (nothing moves: The brand has no screen presence.)") == 1
    write_spec(p, ON)
    assert "motion: on (signature: Settle)" in bc("state", project=p).stdout
    assert json.loads(bc("state", "--json", project=p).stdout)["motion"] == {"motion": "on", "signature": "Settle"}
    q = project(tmp_path / "q", "quick")
    assert "motion: not decided\n" in bc("state", project=q).stdout and "due before G4" not in bc("state", project=q).stdout


def test_a_motion_json_the_summary_cannot_read_is_said_there_and_the_summary_still_prints(tmp_path):
    p = project(tmp_path)
    write_spec(p, "{not json")
    r = bc("state", project=p)
    assert r.returncode == 0 and "motion: cannot be read (motion/motion.json: cannot be read as JSON" in r.stdout and "history: intact" in r.stdout
    assert json.loads(bc("state", "--json", project=p).stdout)["motion"]["motion"] == "unreadable"


# ---------------------------------------------------------------- check: motion:decided and motion:proof

def row(p: Path, rid: str) -> dict | None:
    return next((x for x in report(p, "check")["results"] if x["id"] == rid), None)


def check(p: Path):
    return bc("check", project=p)


def gated_report(p: Path, proof: str = "motion/proof.json", status: str = "pass") -> Path:
    """The report `shot --motion` writes for a proof, made by hand (its inputs: the proof file)."""
    from _common import motion_report_tool, sha256_file
    (p / proof).parent.mkdir(parents=True, exist_ok=True)
    if not (p / proof).is_file():
        (p / proof).write_text('{"schema": 1, "cases": []}\n')
    f = p / "assets" / "_checks" / (motion_report_tool(proof) + ".json")
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"tool": motion_report_tool(proof), "version": "0", "inputs_sha": "0" * 64, "inputs": [{"path": proof, "sha256": sha256_file(p / proof)}], "renderer": "x",
                             "proof": proof, "status": status, "results": [{"id": "motion:case:control", "status": "fail" if status == "fail" else "pass", "label": "x", "detail": "x"}]}) + "\n")
    return f


def legacy_report(p: Path, proof: str, status: str = "pass") -> Path:
    """The one report an earlier version wrote, assets/_checks/motion.json, whatever proof it was made of (its inputs: the proof file)."""
    from _common import sha256_file
    (p / proof).parent.mkdir(parents=True, exist_ok=True)
    if not (p / proof).is_file():
        (p / proof).write_text('{"schema": 1, "cases": []}\n')
    f = p / "assets" / "_checks" / "motion.json"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"tool": "motion", "version": "0.3.4", "inputs_sha": "0" * 64, "inputs": [{"path": proof, "sha256": sha256_file(p / proof)}], "renderer": "x",
                             "proof": proof, "status": status, "results": [{"id": "motion:case:control", "status": "fail" if status == "fail" else "pass", "label": "x", "detail": "x"}]}) + "\n")
    return f


@pytest.mark.parametrize("tier", ["standard", "full"])
def test_standard_and_full_fail_check_once_g4_is_recorded_with_no_decision_on_motion(tmp_path, tier):
    p = project(tmp_path, tier, ("G3", "G4"))
    r = check(p)
    got = row(p, "motion:decided")
    assert r.returncode == 1 and got["status"] == "fail", r.stdout
    assert got["detail"] == f"Standard and Full decide motion before G4: {DECIDE}"
    assert "motion:decided" in failing(report(p, "check"))
    assert motion(p, "--off", "The brand has no screen presence.").returncode == 0           # the one way out that needs no round: record that nothing moves
    r = check(p)
    assert r.returncode == 0, r.stdout
    got = row(p, "motion:decided")
    assert got["status"] == "pass" and "motion/motion.json exists (motion off)" in got["detail"]
    assert row(p, "motion:proof") is None                                                    # nothing moves: no proof of a move to ask for


def test_before_g4_an_undecided_motion_is_an_info_row_once_g3_is_recorded_and_no_row_before_it(tmp_path):
    p = project(tmp_path, "standard")
    assert check(p).returncode == 0 and row(p, "motion:decided") is None                      # before G3: no row
    assert bc("state", "--record", "G3", "approved", project=p).returncode == 0
    r = check(p)
    got = row(p, "motion:decided")
    assert r.returncode == 0 and got["status"] == "info" and got["detail"] == f"not decided yet; due before G4: {DECIDE}", r.stdout
    write_spec(p, OFF)
    assert check(p).returncode == 0 and row(p, "motion:decided") is None                      # decided before G4: nothing to remind of


@pytest.mark.parametrize("gates", [(), ("G3",), ("G3", "G4")])
def test_quick_gets_no_motion_row_whatever_it_has_recorded(tmp_path, gates):
    p = project(tmp_path, "quick", gates)
    assert check(p).returncode == 0
    assert row(p, "motion:decided") is None and row(p, "motion:proof") is None
    write_spec(p, ON)                                                                         # Quick decides motion at G4 and only when something moves: a brand that moves needs no proof row
    assert check(p).returncode == 0 and row(p, "motion:decided") is None and row(p, "motion:proof") is None


def test_a_brand_that_moves_needs_a_passing_gated_proof_of_the_approved_move(tmp_path):
    p = project(tmp_path, "standard", ("G3", "G4"))
    write_spec(p, ON)
    r = check(p)
    got = row(p, "motion:proof")
    assert r.returncode == 1 and got["status"] == "fail", r.stdout                           # no motion/proof.json at all
    assert got["detail"] == "motion/motion.json says the brand moves, but there is no proof of the approved move: write motion/proof.json"
    assert row(p, "motion:decided")["status"] == "pass" and "(motion on)" in row(p, "motion:decided")["detail"]
    (p / "motion").mkdir(exist_ok=True)
    (p / "motion" / "proof.json").write_text('{"schema": 1, "cases": []}\n')
    r = check(p)
    got = row(p, "motion:proof")
    assert r.returncode == 3 and got["status"] == "skipped" and got["detail"] == "not verified: run `brand-creator shot --motion motion/proof.json`", r.stdout      # a proof, but no report of it
    f = gated_report(p)
    r = check(p)
    got = row(p, "motion:proof")
    assert r.returncode == 0 and got["status"] == "pass" and got["detail"] == "met by the report of motion/proof.json", r.stdout
    mutate(p / "motion" / "proof.json", '"cases": []', '"cases": [ ]')                       # the proof changed since the report: stale
    r = check(p)
    assert r.returncode == 3 and row(p, "motion:proof")["status"] == "skipped"
    mutate(p / "motion" / "proof.json", '"cases": [ ]', '"cases": []')
    gated_report(p, status="fail")                                                           # the proof ran and failed: its report fails, and so does motion:proof, never "not verified"
    r = check(p)
    got = row(p, "motion:proof")
    assert r.returncode == 1 and got["status"] == "fail", r.stdout
    assert got["detail"].startswith("the proof of the approved move fails: motion/proof-") and "report is failing (motion:case:control)" in got["detail"], got["detail"]
    assert got["detail"].endswith("change the move as its failing rows say, then run `brand-creator shot --motion motion/proof.json`"), got["detail"]
    assert any(x["status"] == "fail" and x["id"].startswith("report:motion/proof-") for x in report(p, "check")["results"])
    assert f.is_file()


# the rows `shot --motion` writes when it cannot verify something (scripts/render.mjs), as (the row's id, its detail): a move driven by requestAnimationFrame, and a CSS animation it cannot read
RAF_ROW = ("motion:demo-page:edges:360", "not verified: the mark is also moved by requestAnimationFrame, which cannot be seeked, so what it draws between two frames is not known; "
                                         "33 sample point(s) over 320 ms: no part of the mark (1 box(es)) past the left, top or right edge; the page never wider than 360 px, never taller than at rest (200 px)")
PSEUDO_ROW = ("motion:demo-page:whole-pixel", "not verified: the translation of nudge cannot be read (a percentage on a pseudo-element); a pixel mark: translation was whole pixels at 33 sample point(s)")
SHOT = "brand-creator shot --motion motion/proof.json"
CSS_WAY_OUT = f"change the page or the proof as the rows say, then run `{SHOT}`"
RAF_WAY_OUT = ("the proof steps through CSS animations, CSS transitions and element.animate() (Web Animations) only, so a move driven by requestAnimationFrame stays not verified however often it runs: "
               f"write the move with one of them, then run `{SHOT}`")


def not_verified(p: Path, *rows: tuple[str, str], proof: str = "motion/proof.json") -> Path:
    """The report of the approved proof as `shot --motion` leaves it when it could not verify something: status not-verified, and a skipped row for each of `rows`."""
    f = gated_report(p, proof)
    mutate_json(f, lambda d: (d.__setitem__("status", "not-verified"), d["results"].extend({"id": i, "status": "skipped", "label": "x", "detail": t} for i, t in rows)))
    return f


def report_row(p: Path, f: Path) -> dict:
    """The row `check` writes for the gated report at `f`."""
    return row(p, "report:" + f.relative_to(p / "assets" / "_checks").with_suffix("").as_posix())


def test_a_current_gated_report_that_is_not_verified_says_which_rows_it_could_not_verify_in_its_own_row_and_in_motion_proof(tmp_path):
    """`check` used to say only `report status is 'not-verified'` and `run it` of a report that is current: nothing said what to change. The two rows quote what the report could not verify,
    as board-lint quotes it for a variant, and the way out with it: the requestAnimationFrame advice only when a row names it."""
    p = project(tmp_path, "standard", ("G3", "G4"))
    write_spec(p, ON)
    f = not_verified(p, PSEUDO_ROW)                                                          # a CSS animation the proof cannot read: nothing to do with requestAnimationFrame
    tool = f.relative_to(p / "assets" / "_checks").with_suffix("").as_posix()
    r = check(p)
    quoted = f"{PSEUDO_ROW[0]}: {PSEUDO_ROW[1]}"
    mp, own = row(p, "motion:proof"), report_row(p, f)
    assert r.returncode == 3 and mp["status"] == "skipped" and own["status"] == "skipped", r.stdout
    assert mp["detail"] == f"not verified: the motion report of motion/proof.json is 'not-verified', not a verdict ({quoted}): {CSS_WAY_OUT}", mp["detail"]
    assert own["detail"] == f"not verified: {tool} report status is 'not-verified' ({quoted}): {CSS_WAY_OUT}", own["detail"]
    assert "requestAnimationFrame" not in mp["detail"] + own["detail"] and "however often" not in mp["detail"] + own["detail"]
    not_verified(p, RAF_ROW)                                                                 # the same report of a move that is driven by it: running it again changes nothing, and it says so
    check(p)
    quoted = f"{RAF_ROW[0]}: {RAF_ROW[1]}"
    assert row(p, "motion:proof")["detail"] == f"not verified: the motion report of motion/proof.json is 'not-verified', not a verdict ({quoted}): {RAF_WAY_OUT}"
    assert report_row(p, f)["detail"] == f"not verified: {tool} report status is 'not-verified' ({quoted}): {RAF_WAY_OUT}"
    not_verified(p, PSEUDO_ROW, RAF_ROW)                                                     # one row that names it is enough: the advice is given, beside the other row
    check(p)
    for got in (row(p, "motion:proof"), report_row(p, f)):
        assert PSEUDO_ROW[1] in got["detail"] and RAF_ROW[1] in got["detail"] and got["detail"].endswith(RAF_WAY_OUT), got["detail"]


def test_check_quotes_three_rows_of_a_report_that_is_not_verified_and_says_when_it_lists_none(tmp_path):
    p = project(tmp_path, "standard", ("G3", "G4"))
    write_spec(p, ON)
    f = not_verified(p, *((f"motion:demo-page:row{i}", f"not verified: reason {i}") for i in range(1, 5)))
    check(p)
    for got in (row(p, "motion:proof"), report_row(p, f)):
        assert ("(motion:demo-page:row1: not verified: reason 1 | motion:demo-page:row2: not verified: reason 2 | motion:demo-page:row3: not verified: reason 3 | and 1 more): "
                + CSS_WAY_OUT) in got["detail"] and "row4" not in got["detail"], got["detail"]
    mutate_json(f, lambda d: d.__setitem__("results", [x for x in d["results"] if x["status"] != "skipped"]))      # a report that says not-verified and lists no row that is not
    check(p)
    assert row(p, "motion:proof")["detail"] == f"not verified: the motion report of motion/proof.json is 'not-verified', not a verdict (it lists no row that is not verified): run `{SHOT}`"
    assert report_row(p, f)["detail"].endswith(f"report status is 'not-verified' (it lists no row that is not verified): run `{SHOT}`")


def test_a_stale_report_is_run_again_and_a_failing_one_fails_motion_proof_and_neither_quotes_a_row(tmp_path):
    """The rows are quoted of a report that is current and no verdict: a stale one is not a report of this proof as it is now (its rows say nothing about it), and a failing one is a
    verdict: motion:proof fails with the report's own row, and asks to change the move, not only to run the proof again (0.4.0 called it not verified)."""
    p = project(tmp_path, "standard", ("G3", "G4"))
    write_spec(p, ON)
    f = not_verified(p, RAF_ROW)
    mutate(p / "motion" / "proof.json", '"cases": []', '"cases": [ ]')                       # the proof changed since the report: stale
    check(p)
    assert row(p, "motion:proof")["detail"] == f"not verified: run `{SHOT}`", row(p, "motion:proof")
    assert "is stale" in report_row(p, f)["detail"] and RAF_ROW[0] not in report_row(p, f)["detail"] + row(p, "motion:proof")["detail"]
    mutate(p / "motion" / "proof.json", '"cases": [ ]', '"cases": []')
    gated_report(p, status="fail")
    r = check(p)
    own, got = report_row(p, f), row(p, "motion:proof")
    assert r.returncode == 1 and own["status"] == "fail" and got["status"] == "fail", r.stdout
    assert got["detail"] == f"the proof of the approved move fails: {own['detail']}; change the move as its failing rows say, then run `{SHOT}`", got["detail"]
    assert RAF_ROW[0] not in got["detail"] and "not verified" not in got["detail"]


def test_the_report_of_a_proof_the_disk_spells_in_another_letter_case_is_found_by_the_proof_it_names(tmp_path):
    """`shot --motion` names its report after the proof as the disk spells it, and records that spelling as its `proof`: a disk that does not tell letter cases apart (macOS) opens motion/proof.json for Motion/proof.json.
    Where letter cases differ (Linux) `motion` is made a second name for the folder, a link, so that both spellings reach the proof there too and the test asserts the same on either kind of disk."""
    p = project(tmp_path, "standard", ("G3", "G4"))
    write_spec(p, ON)
    (p / "motion").rename(p / "Motion")
    if not (p / "motion").exists():                                                          # a disk that tells letter cases apart: motion/ is another folder, so give it the name of this one
        (p / "motion").symlink_to("Motion")
    f = not_verified(p, RAF_ROW, proof="Motion/proof.json")                                  # the report of Motion/proof.json: named and recorded as the disk spells it
    from _common import motion_report_tool
    assert f.name == motion_report_tool("Motion/proof.json").split("/")[1] + ".json" and json.loads(f.read_text())["proof"] == "Motion/proof.json"
    assert (p / "motion/proof.json").samefile(p / "Motion/proof.json")                       # one file, reached by both spellings, on either kind of disk
    r = check(p)
    quoted = f"{RAF_ROW[0]}: {RAF_ROW[1]}"
    assert r.returncode == 3, r.stdout
    assert row(p, "motion:proof")["detail"] == f"not verified: the motion report of motion/proof.json is 'not-verified', not a verdict ({quoted}): {RAF_WAY_OUT}", row(p, "motion:proof")["detail"]
    own = report_row(p, f)
    assert own["status"] == "skipped" and quoted in own["detail"] and own["detail"].endswith(f"write the move with one of them, then run `brand-creator shot --motion Motion/proof.json`"), own["detail"]


def test_check_quotes_with_the_function_of_the_board_lint_and_does_not_copy_it():
    """One wording for two commands: board-lint quotes a variant's report with motionboard.unverified_why and check calls the same function (its own text holds no copy of the advice)."""
    check_py = (ROOT / "scripts" / "check.py").read_text(encoding="utf-8")
    assert check_py.count("motionboard.unverified_why(") == 2 and "stays not verified however often" not in check_py and "| and " not in check_py
    board = (ROOT / "scripts" / "boardlib" / "motionboard.py").read_text(encoding="utf-8")
    assert board.count("unverified_why(") == 2 and board.count("stays not verified however often it runs") == 1       # defined once, used by the board's own row


def test_a_try_out_proof_never_satisfies_the_proof_of_the_approved_move(tmp_path):
    p = project(tmp_path, "full", ("G3", "G4"))
    write_spec(p, ON)
    for where in ("rounds/r2/Settle/proof.json", "history/2026-10-23-approved-motion/proof.json", "removed-2026-10-23/motion/proof.json"):
        gated_report(p, where)                                                               # passing, and of an exploration proof: listed, never counted
    from _common import history_files, sha256_file, write_history_manifest
    write_history_manifest(p / "history", {f.relative_to(p / "history").as_posix(): sha256_file(f) for f in history_files(p / "history")})   # frozen the way `freeze` writes it
    (p / "motion").mkdir(exist_ok=True)
    (p / "motion" / "proof.json").write_text('{"schema": 1, "cases": []}\n')
    r = check(p)
    assert r.returncode == 3 and row(p, "motion:proof")["status"] == "skipped", r.stdout
    assert sum(1 for x in report(p, "check")["results"] if x["status"] == "info" and "exploration proof, not gated" in x.get("detail", "")) == 3
    gated_report(p)                                                                          # the project's own proof passing is what counts
    assert check(p).returncode == 0 and row(p, "motion:proof")["status"] == "pass"


def test_the_report_of_an_earlier_version_never_satisfies_the_proof_of_the_approved_move(tmp_path):
    """assets/_checks/motion.json is one report whatever proof it was made of, so it cannot be told from the proof of the approved move: it is still gated (qa:motion) and said to be old, and never counts here."""
    p = project(tmp_path, "full", ("G3", "G4"))
    write_spec(p, ON)
    (p / "motion").mkdir(exist_ok=True)
    (p / "motion" / "proof.json").write_text('{"schema": 1, "cases": []}\n')
    legacy_report(p, "rounds/r2/Settle/proof.json")                                          # a passing report of a try-out proof, from before there was one report per proof
    r = check(p)
    got = row(p, "motion:proof")
    assert r.returncode == 3 and got["status"] == "skipped" and got["detail"] == "not verified: run `brand-creator shot --motion motion/proof.json`", r.stdout
    assert row(p, "report:motion")["status"] == "pass" and row(p, "report:motion:legacy")["status"] == "warn"      # the old report is still gated, and said to be old
    legacy_report(p, "motion/proof.json")                                                    # even one of the approved proof itself: it is the old layout, run the proof again
    r = check(p)
    assert r.returncode == 3 and row(p, "motion:proof")["status"] == "skipped", r.stdout
    gated_report(p)                                                                          # the report of the proof, in the layout of one report per proof file
    r = check(p)
    assert r.returncode == 0 and row(p, "motion:proof")["status"] == "pass" and row(p, "motion:proof")["detail"] == "met by the report of motion/proof.json", r.stdout


def test_the_report_of_another_proof_of_the_project_never_satisfies_the_proof_of_the_approved_move(tmp_path):
    """0.4.0 passed motion:proof on any passing gated report, so a passing proof of another page met it while motion/proof.json did not exist, and check passed a brand whose approved
    move had no proof at all (finish.sh said check fails it). Only the report of motion/proof.json counts; another proof's is gated in its own row, as before."""
    p = project(tmp_path, "standard", ("G3", "G4"))
    write_spec(p, ON)
    gated_report(p, "site/proof.json")                                                       # another proof of the project, passing
    r = check(p)
    got = row(p, "motion:proof")
    assert r.returncode == 1 and got["status"] == "fail" and got["detail"].endswith("there is no proof of the approved move: write motion/proof.json"), r.stdout
    assert any(x["status"] == "pass" and x["id"].startswith("report:motion/proof-") for x in report(p, "check")["results"])     # its own row passes all the same
    (p / "motion" / "proof.json").write_text('{"schema": 1, "cases": []}\n')
    r = check(p)
    assert r.returncode == 3 and row(p, "motion:proof")["detail"] == f"not verified: run `{SHOT}`", r.stdout     # the approved proof has no report yet: the other one still does not stand in
    gated_report(p, "motion/proof.json")
    assert check(p).returncode == 0
    assert row(p, "motion:proof")["detail"] == "met by the report of motion/proof.json"     # the approved proof alone, never the other one beside it


def test_a_failing_report_of_the_approved_proof_is_never_outvoted_by_a_passing_one_of_the_same_file(tmp_path):
    """Two names can reach motion/proof.json: a disk that does not tell letter cases apart (Motion/proof.json once, motion/proof.json after a rename), or a link. Each name gets its own report, both
    current. A current failure of the approved proof fails motion:proof, whatever another report of the same file says (a link stands in for the second name, the same on every kind of disk)."""
    p = project(tmp_path, "standard", ("G3", "G4"))
    write_spec(p, ON)
    (p / "motion").mkdir(exist_ok=True)
    (p / "motion" / "proof.json").write_text('{"schema": 1, "cases": []}\n')
    (p / "motion" / "alias.json").symlink_to("proof.json")                                   # a second name of the one file
    assert (p / "motion/alias.json").samefile(p / "motion/proof.json")
    gated_report(p, "motion/alias.json")                                                     # passing, under the other name
    f = gated_report(p, status="fail")                                                       # failing, under the name the chain types
    r = check(p)
    got = row(p, "motion:proof")
    assert r.returncode == 1 and got["status"] == "fail", r.stdout
    assert got["detail"] == f"the proof of the approved move fails: {report_row(p, f)['detail']}; change the move as its failing rows say, then run `{SHOT}`", got["detail"]
    gated_report(p)                                                                          # the approved proof passes under both names: met by both
    assert check(p).returncode == 0 and row(p, "motion:proof")["detail"] == "met by the report of motion/alias.json, motion/proof.json"


def test_a_passing_report_that_names_no_proof_never_satisfies_the_proof_of_the_approved_move(tmp_path):
    """A report with no `proof` key cannot say which proof it is of: it is gated all the same, as a proof of the project, in its own row, but it is never taken for the report of motion/proof.json."""
    p = project(tmp_path, "standard", ("G3", "G4"))
    write_spec(p, ON)
    f = gated_report(p, "motion/proof.json")
    mutate_json(f, lambda d: d.pop("proof"))
    r = check(p)
    got = row(p, "motion:proof")
    assert r.returncode == 3 and got["status"] == "skipped" and got["detail"] == f"not verified: run `{SHOT}`", (r.stdout, got)
    assert report_row(p, f)["status"] == "pass"                                              # gated in its own row
    gated_report(p, "motion/proof.json")                                                     # the report as `shot --motion` writes it, naming its proof
    assert check(p).returncode == 0 and row(p, "motion:proof")["detail"] == "met by the report of motion/proof.json"


def test_motion_proof_asks_nothing_before_g4_and_nothing_of_a_brand_that_does_not_move(tmp_path):
    p = project(tmp_path, "standard", ("G3",))
    write_spec(p, ON)
    assert check(p).returncode == 0 and row(p, "motion:proof") is None and row(p, "motion:decided") is None      # G3 only: decided before G4, no row
    assert bc("state", "--record", "G4", "system rules approved", project=p).returncode == 0
    assert row(p, "motion:proof") is None
    assert check(p).returncode == 1 and row(p, "motion:proof")["status"] == "fail"
    write_spec(p, OFF)
    assert check(p).returncode == 0 and row(p, "motion:proof") is None


def test_a_motion_json_that_is_not_valid_is_decided_for_this_row_and_failed_by_the_spec_row(tmp_path):
    p = project(tmp_path, "standard", ("G3", "G4"))
    write_spec(p, "{not json")
    r = check(p)
    assert r.returncode == 1 and row(p, "motion:decided")["status"] == "pass" and row(p, "motion:spec")["status"] == "fail", r.stdout
    assert "motion:decided" not in failing(report(p, "check")) and "motion:spec" in failing(report(p, "check"))


def test_the_contract_and_the_check_docstring_name_the_rows(tmp_path):
    check_py = (ROOT / "scripts" / "check.py").read_text(encoding="utf-8")
    contract = (ROOT / "scripts" / "CONTRACT.md").read_text(encoding="utf-8")
    for needle in ("motion:decided", "motion:proof"):
        assert needle in check_py and needle in contract, needle
