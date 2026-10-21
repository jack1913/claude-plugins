"""motion/motion.json: the machine-readable motion spec (scripts/lib/motionspec.py), its schema, its references to the built duration and curve
tokens, and its row in `check`. Every refusal is an exit 2 that names the field path; tokens that are not built are an exit 3."""
import json
import re
import shutil

import pytest
from _common import EXIT_CANNOT, EXIT_USAGE, CliError
from helpers import ROOT, bc, install_fixture, make_project, mutate_json, report
import motionspec

pytestmark = pytest.mark.requires_setup
SPEC = "motion/motion.json"


def on_doc() -> dict:
    return {"schema": 1, "motion": "on",
            "signature": {"name": "Settle", "description": "The dot drops onto the grid and settles.", "where": ["app icon", "empty states"]},
            "parts": [{"id": "dot", "description": "The accent dot of the mark."}, {"id": "ring-outer", "description": "The outer ring."}],
            "timeline": [{"part": "dot", "property": "transform", "start": "{motion.stagger}", "duration": "{motion.base}", "easing": "{easing.standard}", "note": "drops two pixels"},
                         {"part": "ring-outer", "property": "opacity", "start": "{motion.stagger} * 2", "duration": "{motion.base}", "easing": "{easing.enter}"},
                         {"part": "dot", "property": "transform", "start": "0", "duration": "{duration.fast}", "easing": "{easing.exit}"}],
            "rules": ["reduced motion: nothing moves", "nothing loops forever"]}


def off_doc() -> dict:
    return {"schema": 1, "motion": "off", "reason": "The owner wants a still brand: nothing in it needs to move.", "rules": ["the still is complete"]}


def write(p, doc) -> None:
    (p / "motion").mkdir(exist_ok=True)
    (p / SPEC).write_text(doc if isinstance(doc, str) else json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def refusal(p, code=EXIT_USAGE) -> str:
    with pytest.raises(CliError) as e:
        motionspec.load(p)
    assert e.value.code == code, e.value.message
    return e.value.message


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    """Acme with the starter's motion and easing groups, built: the tokens the references of the specs below name."""
    p = make_project(tmp_path_factory.mktemp("motionspec"))
    install_fixture(p, logo=True, board=False)

    def groups(d):
        d["motion"] = {"$type": "duration", "quick": {"$value": {"value": 160, "unit": "ms"}}, "base": {"$value": {"value": 320, "unit": "ms"}}, "stagger": {"$value": {"value": 120, "unit": "ms"}}}
        d["easing"] = {"$type": "cubicBezier", "standard": {"$value": [0.2, 0, 0, 1]}, "enter": {"$value": [0, 0, 0, 1]}, "exit": {"$value": [0.3, 0, 1, 1]}}
    mutate_json(p / "tokens" / "primitives.tokens.json", groups)
    r = bc("tokens", project=p)
    assert r.returncode == 0, r.stdout + r.stderr
    return p


@pytest.fixture
def proj(built, tmp_path):
    dst = tmp_path / "acme"
    shutil.copytree(built, dst, symlinks=False)
    return dst


# ---------------------------------------------------------------- the document

def test_no_file_is_none_and_a_valid_document_comes_back_as_written(proj):
    assert motionspec.load(proj) is None
    for doc in (on_doc(), off_doc()):
        write(proj, doc)
        assert motionspec.load(proj) == doc
    minimal = {"schema": 1, "motion": "on", "signature": {"name": "Settle", "description": "The dot settles.", "where": ["app icon"]}}   # parts, timeline and rules are optional
    write(proj, minimal)
    assert motionspec.load(proj) == minimal
    write(proj, {**off_doc(), "rules": []})
    assert motionspec.load(proj)["rules"] == []


def drop(*path):
    def f(d):
        for k in path[:-1]:
            d = d[k]
        del d[path[-1]]
    return f


def put(*path, value):
    def f(d):
        for k in path[:-1]:
            d = d[k]
        d[path[-1]] = value
    return f


DOCUMENT_REFUSALS = [
    ("no schema", on_doc, drop("schema"), r"schema: required, 1"),
    ("schema 2", on_doc, put("schema", value=2), r"schema: must be 1 .* got 2"),
    ("schema as a string", on_doc, put("schema", value="1"), r'schema: must be 1 .* got "1"'),
    ("schema true", on_doc, put("schema", value=True), r"schema: must be 1 .* got true"),
    ("no motion", on_doc, drop("motion"), r'motion: required, "on" or "off"'),
    ("motion maybe", on_doc, put("motion", value="maybe"), r'motion: must be "on" or "off", got "maybe"'),
    ("motion true", on_doc, put("motion", value=True), r'motion: must be "on" or "off", got true'),
    ("on without a signature", on_doc, drop("signature"), r'signature: required with motion "on"'),
    ("on with a reason", on_doc, put("reason", value="because"), r'reason: only with motion "off"'),
    ("an unknown key at the top", on_doc, put("colour", value="teal"), r"colour: unknown key \(allowed: schema, motion, reason, signature, parts, timeline, rules\)"),
    ("a signature that is a string", on_doc, put("signature", value="Settle"), r"signature: must be an object \{name, description, where\}"),
    ("a signature without a name", on_doc, drop("signature", "name"), r"signature\.name: required, a non-empty string"),
    ("a signature with a blank name", on_doc, put("signature", "name", value="  "), r"signature\.name: required, a non-empty string"),
    ("a signature without a description", on_doc, drop("signature", "description"), r"signature\.description: required, a non-empty string"),
    ("a signature without where", on_doc, drop("signature", "where"), r"signature\.where: required, a non-empty list"),
    ("a signature with an empty where", on_doc, put("signature", "where", value=[]), r"signature\.where: required, a non-empty list"),
    ("a signature where that is a string", on_doc, put("signature", "where", value="icon"), r"signature\.where: required, a non-empty list"),
    ("a signature where with a number in it", on_doc, put("signature", "where", value=["app icon", 3]), r"signature\.where: required, a non-empty list"),
    ("an unknown key in the signature", on_doc, put("signature", "mood", value="calm"), r"signature\.mood: unknown key \(allowed: name, description, where\)"),
    ("parts that is not a list", on_doc, put("parts", value={"dot": "x"}), r"parts: must be a list of \{id, description\}"),
    ("a part that is not an object", on_doc, put("parts", 0, value="dot"), r"parts\[0\]: must be an object \{id, description\}"),
    ("a part id in capitals", on_doc, put("parts", 0, "id", value="Dot"), r'parts\[0\]\.id: must be lower case words joined by hyphens \(a-z, 0-9, -\), got "Dot"'),
    ("a part id with an underscore", on_doc, put("parts", 0, "id", value="ring_outer"), r'parts\[0\]\.id: must be lower case words joined by hyphens .* got "ring_outer"'),
    ("a part id with a double hyphen", on_doc, put("parts", 0, "id", value="ring--outer"), r"parts\[0\]\.id: must be lower case words"),
    ("a part id that is empty", on_doc, put("parts", 0, "id", value=""), r"parts\[0\]\.id: must be lower case words"),
    ("a part id that is a number", on_doc, put("parts", 0, "id", value=3), r"parts\[0\]\.id: must be lower case words .* got 3"),
    ("a part id used twice", on_doc, put("parts", 1, "id", value="dot"), r'parts\[1\]\.id: "dot" is used twice'),
    ("a part without a description", on_doc, drop("parts", 0, "description"), r"parts\[0\]\.description: required, a non-empty string"),
    ("an unknown key in a part", on_doc, put("parts", 1, "selector", value=".dot"), r"parts\[1\]\.selector: unknown key \(allowed: id, description\)"),
    ("timeline that is not a list", on_doc, put("timeline", value="slowly"), r"timeline: must be a list of steps"),
    ("a step that is not an object", on_doc, put("timeline", 1, value="dot"), r"timeline\[1\]: must be an object"),
    ("a step without a part", on_doc, drop("timeline", 0, "part"), r"timeline\[0\]\.part: required, the id of a part"),
    ("a step whose part is not a part", on_doc, put("timeline", 1, "part", value="nope"), r'timeline\[1\]\.part: "nope" is not a part id \(dot, ring-outer\)'),
    ("a step without a property", on_doc, drop("timeline", 0, "property"), r"timeline\[0\]\.property: required, what moves"),
    ("a step without a start", on_doc, drop("timeline", 0, "start"), r'timeline\[0\]\.start: must be "0", a duration reference .* got null'),
    ("a start that is the number 0", on_doc, put("timeline", 2, "start", value=0), r"timeline\[2\]\.start: must be \"0\".* got 0"),
    ("a start in milliseconds", on_doc, put("timeline", 0, "start", value="120ms"), r'timeline\[0\]\.start: must be "0".* got "120ms"'),
    ("a start that is another number", on_doc, put("timeline", 2, "start", value="2"), r'timeline\[2\]\.start: must be "0".* got "2"'),
    ("a start times a word", on_doc, put("timeline", 1, "start", value="{motion.stagger} * x"), r'timeline\[1\]\.start: must be "0".* got "\{motion\.stagger\} \* x"'),
    ("a start times a negative number", on_doc, put("timeline", 1, "start", value="{motion.stagger} * -1"), r"timeline\[1\]\.start: must be \"0\""),
    ("a start plus a number", on_doc, put("timeline", 1, "start", value="{motion.stagger} + 1"), r"timeline\[1\]\.start: must be \"0\""),
    ("a duration that is a literal", on_doc, put("timeline", 0, "duration", value="320ms"), r'timeline\[0\]\.duration: must be a reference to a duration token such as "\{motion\.base\}", got "320ms"'),
    ("a duration times a number", on_doc, put("timeline", 0, "duration", value="{motion.base} * 2"), r"timeline\[0\]\.duration: must be a reference to a duration token"),
    ("a step without a duration", on_doc, drop("timeline", 0, "duration"), r"timeline\[0\]\.duration: must be a reference to a duration token .* got null"),
    ("an easing that is a word", on_doc, put("timeline", 0, "easing", value="ease-out"), r'timeline\[0\]\.easing: must be a reference to a cubicBezier token such as "\{easing\.standard\}", got "ease-out"'),
    ("a step without an easing", on_doc, drop("timeline", 1, "easing"), r"timeline\[1\]\.easing: must be a reference to a cubicBezier token"),
    ("a note that is empty", on_doc, put("timeline", 0, "note", value=""), r"timeline\[0\]\.note: when present, a non-empty string"),
    ("an unknown key in a step", on_doc, put("timeline", 2, "loop", value=True), r"timeline\[2\]\.loop: unknown key \(allowed: part, property, start, duration, easing, note\)"),
    ("rules that is not a list", on_doc, put("rules", value="reduced motion"), r"rules: must be a list of strings"),
    ("a rule that is empty", on_doc, put("rules", 1, value=""), r"rules\[1\]: must be a non-empty string"),
    ("a rule that is a number", on_doc, put("rules", 0, value=5), r"rules\[0\]: must be a non-empty string"),
    ("off without a reason", off_doc, drop("reason"), r'reason: required with motion "off": why nothing moves, in the owner\'s words'),
    ("off with a blank reason", off_doc, put("reason", value=" "), r"reason: must be a non-empty string"),
    ("off with a signature", off_doc, put("signature", value=on_doc()["signature"]), r'signature: not allowed with motion "off" \(nothing moves\)'),
    ("off with parts", off_doc, put("parts", value=[]), r'parts: not allowed with motion "off" \(nothing moves\)'),
    ("off with a timeline", off_doc, put("timeline", value=[]), r'timeline: not allowed with motion "off" \(nothing moves\)'),
]


@pytest.mark.parametrize("what,make,edit,expected", DOCUMENT_REFUSALS, ids=[c[0] for c in DOCUMENT_REFUSALS])
def test_a_document_that_breaks_the_schema_is_exit_2_and_names_the_field_path(proj, what, make, edit, expected):
    doc = make()
    edit(doc)
    write(proj, doc)
    msg = refusal(proj)
    assert msg.startswith("motion/motion.json: ")
    assert re.search(expected, msg), msg


def test_a_file_that_is_not_a_json_object_is_exit_2(proj):
    write(proj, "{not json")
    assert re.search(r"motion/motion\.json: cannot be read as JSON", refusal(proj))
    write(proj, "[1, 2]")
    assert refusal(proj) == "motion/motion.json: the document must be a JSON object"


def test_every_problem_is_listed_in_one_refusal_and_a_long_list_is_cut(proj):
    doc = on_doc()
    doc["schema"] = 2
    doc["signature"]["name"] = ""
    doc["timeline"][0]["easing"] = "ease"
    write(proj, doc)
    msg = refusal(proj)
    assert all(re.search(p, msg) for p in (r"schema: must be 1", r"signature\.name: required", r"timeline\[0\]\.easing: must be a reference"))
    doc = on_doc()
    doc["timeline"] = [{"part": "nope"}] * 4                  # five problems each: part, property, start, duration, easing
    write(proj, doc)
    msg = refusal(proj)
    assert msg.count("is not a part id") == 2 and re.search(r"; and 12 more$", msg), msg      # the first eight are shown, the other twelve are counted


# ---------------------------------------------------------------- the references: they must exist in the built tokens, as the right kind

def test_a_reference_must_name_a_built_token_of_the_right_kind(proj):
    cases = [
        ("a duration that does not exist", ("timeline", 0, "duration"), "{motion.nope}", r"timeline\[0\]\.duration: no token named motion\.nope \(duration tokens: duration\.fast, motion\.base, motion\.quick, motion\.stagger\)"),
        ("a duration that is a curve", ("timeline", 0, "duration"), "{easing.standard}", r"timeline\[0\]\.duration: \{easing\.standard\} is not a duration token \(duration tokens: "),
        ("a duration that is a colour", ("timeline", 0, "duration"), "{color.paper}", r"timeline\[0\]\.duration: \{color\.paper\} is not a duration token"),
        ("a curve that does not exist", ("timeline", 1, "easing"), "{easing.nope}", r"timeline\[1\]\.easing: no token named easing\.nope \(cubicBezier tokens: easing\.enter, easing\.exit, easing\.standard\)"),
        ("a curve that is a duration", ("timeline", 1, "easing"), "{motion.base}", r"timeline\[1\]\.easing: \{motion\.base\} is not a cubicBezier token \(cubicBezier tokens: "),
        ("a start that is a curve", ("timeline", 0, "start"), "{easing.enter}", r"timeline\[0\]\.start: \{easing\.enter\} is not a duration token"),
        ("a start that does not exist", ("timeline", 1, "start"), "{motion.nope} * 2", r"timeline\[1\]\.start: no token named motion\.nope"),
    ]
    for what, path, value, expected in cases:
        doc = on_doc()
        put(*path, value=value)(doc)
        write(proj, doc)
        msg = refusal(proj)
        assert re.search(expected, msg), f"{what}: {msg}"
    for ok in ("0", "{motion.stagger}", "{motion.stagger} * 2", "{motion.stagger}*1.5", "{duration.fast} * 0"):
        doc = on_doc()
        doc["timeline"][0]["start"] = ok
        write(proj, doc)
        assert motionspec.load(proj) == doc, ok


def test_the_references_are_checked_with_the_document_so_one_run_shows_everything(proj):
    doc = on_doc()
    doc["signature"]["name"] = ""
    doc["timeline"][0]["easing"] = "{easing.nope}"
    write(proj, doc)
    msg = refusal(proj)
    assert "signature.name: required" in msg and "timeline[0].easing: no token named easing.nope" in msg


def test_tokens_that_are_not_built_are_exit_3_naming_the_command_and_a_broken_document_is_still_exit_2(proj):
    tj = proj / "assets" / "tokens" / "tokens.json"
    tj.rename(tj.with_name("tokens.json.moved"))
    write(proj, on_doc())
    msg = refusal(proj, EXIT_CANNOT)
    assert "brand-creator tokens" in msg and "motion/motion.json" in msg
    doc = on_doc()
    doc["schema"] = 2
    write(proj, doc)
    assert "schema: must be 1" in refusal(proj)            # exit 2: the document is wrong whether or not the tokens are built
    write(proj, off_doc())                                 # no reference, so nothing to look up
    assert motionspec.load(proj) == off_doc()
    minimal = {"schema": 1, "motion": "on", "signature": on_doc()["signature"]}
    write(proj, minimal)
    assert motionspec.load(proj) == minimal
    tj.with_name("tokens.json.moved").rename(tj)
    tj.write_text("{broken", encoding="utf-8")
    write(proj, on_doc())
    assert "brand-creator tokens" in refusal(proj, EXIT_CANNOT)
    doc = on_doc()
    doc["schema"] = 2
    write(proj, doc)
    msg = refusal(proj)                                    # unreadable tokens do not hide what is wrong with the document itself: still exit 2
    assert "schema: must be 1" in msg and "cannot be read" not in msg
    r = bc("check", project=proj)
    assert row(proj)["status"] == "fail" and "schema: must be 1" in row(proj)["detail"], r.stdout


def test_tokens_built_before_they_had_motion_are_named_in_the_refusal(proj):
    mutate_json(proj / "assets" / "tokens" / "tokens.json", lambda d: d.pop("motion"))
    write(proj, on_doc())
    msg = refusal(proj)
    assert "{motion.stagger} is not a duration token (duration tokens: none; the built tokens have no motion section: run `brand-creator tokens`" in msg


def test_the_summary_says_what_the_document_holds():
    assert motionspec.summary(on_doc()) == "motion on: signature 'Settle', 2 part(s), 3 timeline step(s), 2 rule(s)"
    assert motionspec.summary({"schema": 1, "motion": "on", "signature": on_doc()["signature"]}) == "motion on: signature 'Settle', 0 part(s), 0 timeline step(s), 0 rule(s)"
    assert motionspec.summary({**off_doc(), "reason": "No\nmotion,   by choice."}) == "motion off: No motion, by choice."


# ---------------------------------------------------------------- check

def row(p, rid="motion:spec"):
    return next((r for r in report(p, "check")["results"] if r["id"] == rid), None)


def test_check_has_no_motion_row_without_a_file_and_a_passing_one_with_a_valid_file(proj):
    r = bc("check", project=proj)
    assert "Traceback" not in r.stdout + r.stderr and row(proj, "history:manifest") is not None and row(proj, "error") is None   # the whole run finished
    assert row(proj) is None
    write(proj, on_doc())
    bc("check", project=proj)
    r = row(proj)
    assert r["status"] == "pass" and r["detail"] == "motion on: signature 'Settle', 2 part(s), 3 timeline step(s), 2 rule(s)"
    write(proj, off_doc())
    bc("check", project=proj)
    assert row(proj)["status"] == "pass" and row(proj)["detail"].startswith("motion off: The owner wants a still brand")


def test_check_fails_a_bad_spec_as_a_row_not_a_crash(proj):
    doc = on_doc()
    doc["timeline"][1]["easing"] = "{easing.nope}"
    doc["parts"][0]["id"] = "Dot"
    write(proj, doc)
    r = bc("check", project=proj)
    assert r.returncode == 1 and "Traceback" not in r.stdout + r.stderr, r.stdout + r.stderr
    got = row(proj)
    assert got["status"] == "fail" and "timeline[1].easing: no token named easing.nope" in got["detail"] and "parts[0].id" in got["detail"]
    write(proj, "{not json")
    r = bc("check", project=proj)
    assert r.returncode == 1 and "Traceback" not in r.stdout + r.stderr
    assert row(proj)["status"] == "fail" and "cannot be read as JSON" in row(proj)["detail"]


def test_check_says_not_verified_when_the_tokens_the_spec_names_are_not_built(proj):
    tj = proj / "assets" / "tokens" / "tokens.json"
    tj.rename(tj.with_name("tokens.json.moved"))
    write(proj, on_doc())
    bc("check", project=proj)
    got = row(proj)
    assert got["status"] == "skipped" and got["detail"].startswith("not verified: ") and "brand-creator tokens" in got["detail"]


def test_check_notices_when_the_tokens_lose_a_curve_the_spec_names(proj):
    write(proj, on_doc())
    bc("check", project=proj)
    assert row(proj)["status"] == "pass"
    mutate_json(proj / "tokens" / "primitives.tokens.json", lambda d: d["easing"].pop("enter"))
    assert bc("tokens", project=proj).returncode == 0
    bc("check", project=proj)
    got = row(proj)
    assert got["status"] == "fail" and "timeline[1].easing: no token named easing.enter" in got["detail"]


# ---------------------------------------------------------------- the contract

def test_the_contract_documents_the_motion_spec_and_every_key_the_validator_accepts():
    contract = (ROOT / "scripts" / "CONTRACT.md").read_text(encoding="utf-8")
    assert "### Motion spec" in contract
    section = contract.split("### Motion spec", 1)[1].split("\n### ", 1)[0]
    assert "motion/motion.json" in section and "motionspec.py" in section
    for group in motionspec.KEYS.values():
        for key in group:
            assert f"`{key}`" in section, f"CONTRACT.md does not document the motion.json key {key}"
    for word in ("exit 2", "exit 3", "brand-creator tokens", "unknown key", "lower case"):
        assert word in section, word
    assert "motion/motion.json" in contract.split("## Project file conventions", 1)[1].split("## BRAND-STATE.md frontmatter", 1)[0]
