"""The motion board (data-board="motion"): a round after G3 that tries the signature move as variants, one folder and one card each (scripts/boardlib/motionboard.py,
templates/motion-board.html). Every row of the lint has a deliberate break here. The variants' files are made by hand (a page, a proof, stills and frames.json as `frames`
writes them, the reports `shot --motion` and `frames` write), so these tests need no browser: the real run is the Acme smoke (tests/smoke/acme.sh)."""
import base64
import hashlib
import json
import re
from pathlib import Path

import pytest
from helpers import ROOT, bc, failing, fill_motion_board, fill_style_board, install_fixture, make_project, make_r2_board, mutate, mutate_json, report
from px_lib import Img

TEMPLATE = ROOT / "templates" / "motion-board.html"
NAMES = ("Settle", "Bounce", "Glide")


@pytest.fixture
def proj(tmp_path):
    """Acme at the Standard tier with G3 recorded and its round 1 pick board: the project a motion round starts from."""
    p = make_project(tmp_path, tier="standard")
    install_fixture(p, tokens=False, logo=False, qa=False)
    assert bc("state", "--record", "G3", "approved r1 (test)", project=p).returncode == 0
    return p


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def proof_of(rnd: int, name: str) -> str:
    return f"rounds/r{rnd}/{name}/proof.json"


def report_of(p: Path, rnd: int, name: str) -> Path:
    """Where `shot --motion` keeps its report of a variant's proof."""
    from _common import motion_report_tool
    return p / "assets" / "_checks" / (motion_report_tool(proof_of(rnd, name)) + ".json")


def motion_report(p: Path, proof: str, status: str = "pass", page: str | None = None, loaded: tuple[str, ...] = ()) -> Path:
    """The report `shot --motion` writes for a proof, made by hand: its inputs are the proof, the page and every file the page loaded (`loaded`: a stylesheet, tokens.css, a script)."""
    from _common import motion_report_tool, sha256_file
    f = p / "assets" / "_checks" / (motion_report_tool(proof) + ".json")
    f.parent.mkdir(parents=True, exist_ok=True)
    inputs = [{"path": x, "sha256": sha256_file(p / x)} for x in (proof, page, *loaded) if x and (p / x).is_file()]
    f.write_text(json.dumps({"tool": motion_report_tool(proof), "version": "0", "inputs_sha": "0" * 64, "inputs": inputs, "renderer": "x", "proof": proof, "status": status,
                             "results": [{"id": "motion:case:control", "status": "fail" if status == "fail" else "pass", "label": "control", "detail": "x"}]}, indent=2) + "\n")
    return f


def frames_report_of(p: Path, rnd: int, name: str) -> Path:
    """Where `frames` keeps its report of a variant's proof."""
    from bookdata import frames_report_tool
    return p / "assets" / "_checks" / (frames_report_tool(proof_of(rnd, name)) + ".json")


def frames_report(p: Path, proof: str, name: str, page: str | None = None, status: str = "pass", loaded: tuple[str, ...] = ()) -> Path:
    """The report `frames` writes for a proof, made by hand: its inputs are the proof, the page and every file the page loaded (`loaded`), and the case has its row, `frames:<name>`."""
    from _common import sha256_file
    from bookdata import frames_report_tool
    f = p / "assets" / "_checks" / (frames_report_tool(proof) + ".json")
    f.parent.mkdir(parents=True, exist_ok=True)
    inputs = [{"path": x, "sha256": sha256_file(p / x)} for x in sorted(x for x in (proof, page, *loaded) if x and (p / x).is_file())]
    f.write_text(json.dumps({"tool": frames_report_tool(proof), "version": "0", "inputs_sha": "0" * 64, "inputs": inputs, "renderer": "x", "proof": proof, "cases": [{"name": name}],
                             "points_pct": [0, 100], "engine": "Chromium (Playwright)", "status": status,
                             "results": [{"id": f"frames:{name}", "status": status, "label": "frames of the mark's motion", "detail": "x"}]}, indent=2) + "\n")
    return f


def reports_current(p: Path, rnd: int, name: str, status: str = "pass", loaded: tuple[str, ...] = ()) -> None:
    """The two reports of a variant made again, as `shot --motion` and `frames` make them after a change to its proof or its page: their inputs are the files as they are now."""
    page = f"rounds/r{rnd}/{name}/index.html"
    motion_report(p, proof_of(rnd, name), status, page, loaded)
    frames_report(p, proof_of(rnd, name), name, page, loaded=loaded)


# the rows `shot --motion` writes when it cannot verify something (scripts/render.mjs), as (the end of the row id, its detail)
RAF_ROWS = (("whole-pixel", 'not verified: the mark is also moved by requestAnimationFrame, which cannot be seeked, so what it draws between two frames is not known; a pixel mark '
                            '(the static SVG says shape-rendering="crispEdges"): translation was whole pixels at 33 sample point(s) of 1 animated target(s)'),
            ("edges:360", "not verified: the mark is also moved by requestAnimationFrame, which cannot be seeked, so what it draws between two frames is not known; 33 sample point(s) over 320 ms: "
                          "no part of the mark (1 box(es)) past the left, top or right edge; the page never wider than 360 px, never taller than at rest (200 px)"))
PSEUDO_ROWS = (("whole-pixel", 'not verified: the translation of nudge cannot be read (a percentage on a pseudo-element); a pixel mark (the static SVG says shape-rendering="crispEdges"): '
                               "translation was whole pixels at 33 sample point(s) of 1 animated target(s)"),)      # a CSS animation, no requestAnimationFrame
UNPLACED_ROWS = (("normal:rest=static", "not verified: the still could not be placed exactly over the mark element (#mark): it ended 1.5 css px off, as it does when an ancestor rotates or skews the element"),)


def not_verified(p: Path, name: str, *rows: tuple[str, str]) -> Path:
    """The motion report of a variant as `shot --motion` leaves it when it could not verify something: status not-verified, and a skipped row for each of `rows`."""
    f = report_of(p, 2, name)
    mutate_json(f, lambda d: (d.__setitem__("status", "not-verified"),
                              d["results"].extend({"id": f"motion:{name}:{end}", "status": "skipped", "label": "x", "detail": text} for end, text in rows)))
    return f


def make_variant(p: Path, rnd: int, name: str, status: str = "pass") -> None:
    """rounds/r<rnd>/<name>/: its page, its proof (a page case named after it, its static the approved master), the files `frames` writes (a still, the strip, the reduced still, frames.json
    and the report) and the report of `shot --motion`."""
    d = p / "rounds" / f"r{rnd}" / name
    frames = d / "frames" / name
    frames.mkdir(parents=True)
    master = p / "assets" / "logo" / "mark.svg"   # the approved master every proof compares its rest frame with
    if not master.is_file():
        master.parent.mkdir(parents=True, exist_ok=True)
        master.write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 8"><rect width="8" height="8"/></svg>\n')
    page = f"rounds/r{rnd}/{name}/index.html"
    (p / page).write_text(f'<!doctype html><title>{name}</title><svg id="mark" viewBox="0 0 8 8"><rect width="8" height="8"/></svg>\n')
    proof = proof_of(rnd, name)
    (p / proof).write_text(json.dumps({"schema": 1, "cases": [{"name": name, "type": "page", "page": page, "selector": "#mark", "static": "assets/logo/mark.svg"}]}, indent=2) + "\n")
    hue = "#" + sha(name.encode())[:6]
    files = {"00-0.png": Img(8, 8, hue).png(), "strip.png": Img(24, 8, hue).png(), "reduced.png": Img(8, 8, "#" + sha(name[::-1].encode())[:6]).png()}   # each picture is its own bytes
    for fn, data in files.items():
        (frames / fn).write_bytes(data)
    at = f"rounds/r{rnd}/{name}/frames/{name}"
    (frames / "frames.json").write_text(json.dumps({
        "schema": 1, "case": name, "proof": proof, "page": page, "selector": "#mark", "length_ms": 320, "scale": 2, "size": [8, 8],
        "frames": [{"percent": 0, "ms": 0, "file": f"{at}/00-0.png", "sha256": sha(files["00-0.png"])}],
        "strip": {"file": f"{at}/strip.png", "sha256": sha(files["strip.png"])}, "reduced": {"file": f"{at}/reduced.png", "sha256": sha(files["reduced.png"])}}, indent=2) + "\n")
    motion_report(p, proof, status, page)
    frames_report(p, proof, name, page)


def make_round(p: Path, rnd: int = 2, names=NAMES, *, first: bool = True, statuses: dict | None = None) -> Path:
    """A whole motion round: one folder per variant and rounds/r<rnd>/board.html, the template filled."""
    for n in names:
        make_variant(p, rnd, n, (statuses or {}).get(n, "pass"))
    page = p / "rounds" / f"r{rnd}" / "board.html"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(fill_motion_board(TEMPLATE.read_text(encoding="utf-8"), names, rnd=rnd, first=first, statuses=statuses), encoding="utf-8")
    return page


def lint(p: Path, page: str = "rounds/r2/board.html", *extra):
    return bc("board-lint", page, *extra, project=p)


def rows(p: Path) -> dict:
    return {r["id"]: r for r in report(p, "board-lint")["results"]}


def detail(p: Path, rid: str) -> str:
    return rows(p)[rid]["detail"]


def failed(p: Path) -> list[str]:
    return failing(report(p, "board-lint"))


# ---------------------------------------------------------------- the template and a finished round

def test_the_template_as_it_is_fails_until_filled_and_filled_in_it_is_a_motion_board_that_passes(proj):
    src = TEMPLATE.read_text(encoding="utf-8")
    for needle in ('data-board="motion"', 'data-section="what-changed"', 'data-section="hardest-surface"', 'data-section="weak-points"', 'data-section="my-call"', 'data-section="questions"',
                   'data-section="reply"', "data-motion-variant=", 'data-field="strip"', 'data-field="reduced"', 'data-field="live"', "data-proof=", 'data-field="what-it-is"',
                   'data-field="cost"', 'data-field="degrades-to"', "data-vote=", "@media (prefers-reduced-motion:reduce)", ".variant[hidden]{display:none}",
                   'name="vote-[[fill: Name one]]"'):
        assert needle in src, needle
    assert 'name="vote-one"' not in src                                                      # one name for every card is one radio group for the whole board (tests/node/motionboard.test.mjs: in a browser)
    dest = proj / "rounds" / "r2" / "board.html"
    dest.parent.mkdir()
    dest.write_text(src, encoding="utf-8")
    r = lint(proj)
    assert r.returncode == 1 and "page:unfilled" in failed(proj), r.stdout
    make_round(proj)
    r = lint(proj)
    assert r.returncode == 0, r.stdout
    got = rows(proj)
    for rid in ("page:data-board", "motion:g3", "motion:off", "motion:variants", "motion:files", "motion:proof", "motion:stills", "motion:fields", "section:hardest-surface", "section:my-call",
                "section:questions", "section:reply"):
        assert got[rid]["status"] == "pass", (rid, got[rid])
    assert "Settle, Bounce, Glide" in got["motion:variants"]["detail"] and got["page:data-board"]["detail"] == "motion"
    assert [got[k]["status"] for k in ("section:what-changed", "section:weak-points")] == ["info", "info"]      # not asked of the first motion board


def test_the_template_gives_each_card_a_vote_group_of_its_own_named_after_the_variant(proj):
    """A radio name is one group for the whole page: the card copied from the template names its group after its variant, as shipped (the helper that fills the template renames nothing)."""
    from boardpage import parse_dom
    make_round(proj)
    root = parse_dom((proj / "rounds" / "r2" / "board.html").read_text(encoding="utf-8"))
    groups = {n.attrs["data-vote"]: sorted({r.attrs.get("name") for r in n.walk() if r.tag == "input"}) for n in root.walk() if "data-vote" in n.attrs}
    assert groups == {name: [f"vote-{name}"] for name in NAMES}, groups
    questions = {r.attrs.get("name") for n in root.walk() if n.attrs.get("data-section") == "question" for r in n.walk() if r.tag == "input"}
    assert questions == {"q1"} and not questions & {g for gs in groups.values() for g in gs}


def test_a_motion_board_whose_variants_share_a_vote_group_or_name_it_otherwise_fails_page_votes(proj):
    """The row of every kind of board (tests/test_board_lint.py has the other kinds): a variant copied with the radio name of the one it came from is one vote group with it."""
    make_round(proj)
    page = proj / "rounds" / "r2" / "board.html"
    assert lint(proj).returncode == 0
    assert rows(proj)["page:votes"]["status"] == "pass" and detail(proj, "page:votes") == "3 vote group(s), one per card: vote-Settle, vote-Bounce, vote-Glide"
    before = mutate(page, 'name="vote-Bounce"', 'name="vote-Settle"', count=3)
    r = lint(proj)
    assert r.returncode == 1 and failed(proj) == ["page:votes"], r.stdout                    # nothing else is wrong with the round
    assert 'Settle and Bounce share the radio name "vote-Settle", so they are one vote group' in detail(proj, "page:votes")
    assert 'Bounce: its radios must all be named "vote-Bounce" (found: "vote-Settle")' in detail(proj, "page:votes")
    page.write_text(before)
    mutate(page, 'name="vote-Glide"', 'name="vote-glide"', count=3)                          # the name as written on the card
    r = lint(proj)
    assert r.returncode == 1 and failed(proj) == ["page:votes"] and 'Glide: its radios must all be named "vote-Glide" (found: "vote-glide")' in detail(proj, "page:votes"), r.stdout


@pytest.mark.parametrize("names", [("Settle", "Bounce"), ("Settle", "Bounce", "Glide", "Skate"), ("Settle",)])
def test_the_first_motion_board_shows_exactly_three_variants(proj, names):
    make_round(proj, 2, names)
    r = lint(proj)
    assert r.returncode == 1 and failed(proj) == ["motion:variants"], r.stdout
    assert f"{len(names)} variant card(s) found, the first motion board of a project shows exactly 3" in detail(proj, "motion:variants")


def test_a_motion_board_is_the_first_one_when_no_earlier_round_is_a_motion_board(proj):
    make_r2_board(proj, 2)                                                                   # r2 is a refine board
    make_round(proj, 3, ("Settle", "Bounce", "Glide", "Skate"))
    r = lint(proj, "rounds/r3/board.html")
    assert r.returncode == 1 and failed(proj) == ["motion:variants"] and "4 variant card(s) found" in detail(proj, "motion:variants"), r.stdout
    make_round(proj, 4, ("Settle", "Bounce", "Glide"))                                       # a second motion board with three: fine, though it is not asked to show three
    assert lint(proj, "rounds/r4/board.html").returncode == 1                                # r3 is a motion board now (a failing one, but one): r4 is a later board and needs its sections
    assert {"section:what-changed", "section:weak-points"} <= set(failed(proj)) and "motion:variants" not in failed(proj)


def test_a_later_motion_board_shows_one_or_more_variants_and_needs_what_changed_and_weak_points(proj):
    make_round(proj)                                                                         # r2: the first motion board
    make_round(proj, 3, ("Settle",), first=False)                                            # r3: the refine loop on the picked variant
    r = lint(proj, "rounds/r3/board.html")
    assert r.returncode == 0, r.stdout
    got = rows(proj)
    assert got["motion:variants"]["status"] == "pass" and got["section:what-changed"]["status"] == "pass" and got["section:weak-points"]["status"] == "pass"
    for sid in ("what-changed", "weak-points"):
        page = proj / "rounds" / "r3" / "board.html"
        before = mutate(page, f'data-section="{sid}"', f'data-removed="{sid}"')
        r = lint(proj, "rounds/r3/board.html")
        assert r.returncode == 1 and f"section:{sid}" in failed(proj), (sid, r.stdout)
        page.write_text(before)
    make_round(proj, 4, ("Settle", "Bounce", "Glide", "Skate"), first=False)                # as many as the loop keeps
    assert lint(proj, "rounds/r4/board.html").returncode == 0
    make_round(proj, 5, (), first=False)                                                     # none at all
    r = lint(proj, "rounds/r5/board.html")
    assert r.returncode == 1 and "no variant card found, a later motion board shows 1 or more" in detail(proj, "motion:variants")
    got = rows(proj)
    assert all(got[k]["status"] == "skipped" and "no variant card to look at" in got[k]["detail"] for k in ("motion:files", "motion:proof", "motion:stills", "motion:fields"))


@pytest.mark.parametrize("name, why", [("Variant 2", "a word of 3+ letters"), ("Option B", "a word of 3+ letters"), ("Ab", "a word of 3+ letters"), ("Style", "a word of 3+ letters"),
                                       ("Soft bounce", "the folder rounds/rN/<name>/"), ("Zażółć", "the folder rounds/rN/<name>/"), ("a/b/cde", "a word of 3+ letters")])
def test_a_variant_name_is_a_word_that_is_not_a_label_and_can_be_a_folder_name(proj, name, why):
    make_round(proj)
    mutate(proj / "rounds" / "r2" / "board.html", 'data-motion-variant="Bounce"', f'data-motion-variant="{name}"')
    r = lint(proj)
    assert r.returncode == 1 and "motion:variants" in failed(proj), r.stdout
    assert why in detail(proj, "motion:variants")


def test_two_variants_cannot_share_a_name_even_in_other_letters(proj):
    make_round(proj)
    mutate(proj / "rounds" / "r2" / "board.html", 'data-motion-variant="Bounce"', 'data-motion-variant="settle"')
    assert lint(proj).returncode == 1
    assert "settle: duplicate variant name" in detail(proj, "motion:variants")


@pytest.mark.parametrize("name", ["Stylish", "Routes", "Looker", "Moody"])
def test_a_word_name_that_only_starts_like_a_label_passes(proj, name):
    make_round(proj, 2, ("Settle", "Glide", name))
    assert lint(proj).returncode == 0


# ---------------------------------------------------------------- the gates of the round, and the kind

def test_a_motion_board_before_g3_fails(proj):
    make_round(proj)
    assert lint(proj).returncode == 0
    mutate(proj / "BRAND-STATE.md", "G3: 2026-10-17 approved r1 (test)", 'G3: ""')
    r = lint(proj)
    assert r.returncode == 1 and failed(proj) == ["motion:g3"], r.stdout                    # nothing else is wrong with the round
    assert "a motion round follows the approved design (G3)" in detail(proj, "motion:g3")


def test_a_motion_round_contradicts_a_recorded_nothing_moves(proj):
    make_round(proj)
    (proj / "motion").mkdir()
    spec = proj / "motion" / "motion.json"
    spec.write_text(json.dumps({"schema": 1, "motion": "off", "reason": "The brand has no screen presence."}))
    r = lint(proj)
    assert r.returncode == 1 and failed(proj) == ["motion:off"], r.stdout
    assert "nothing moves is recorded: a motion round contradicts it" in detail(proj, "motion:off") and "The brand has no screen presence." in detail(proj, "motion:off")
    spec.write_text(json.dumps({"schema": 1, "motion": "on", "signature": {"name": "Settle", "description": "The dot settles.", "where": ["app icon"]}}))
    assert lint(proj).returncode == 0 and rows(proj)["motion:off"]["status"] == "pass"       # a brand that moves may try the move again (a later round of the loop)
    spec.unlink()
    assert lint(proj).returncode == 0 and "not decided" in detail(proj, "motion:off")        # not decided: nothing is contradicted


def test_a_motion_json_that_cannot_be_read_is_not_verified_never_a_pass(proj):
    make_round(proj)
    (proj / "motion").mkdir()
    spec = proj / "motion" / "motion.json"
    spec.write_text("{not json")
    r = lint(proj)
    assert r.returncode == 3, r.stdout                                                       # whether nothing moves is recorded cannot be told
    assert rows(proj)["motion:off"]["status"] == "skipped" and "not verified" in detail(proj, "motion:off") and "cannot be read as JSON" in detail(proj, "motion:off")
    spec.write_text("[1]")
    assert lint(proj).returncode == 3 and "must be a JSON object" in detail(proj, "motion:off")
    # a JSON object that `brand-creator motion` and `state` refuse is no answer here either (0.4.0 read "off" with no reason as "nothing moves is recorded"): the same message, never a pass or a fail
    spec.write_text(json.dumps({"schema": 1, "motion": "off"}))
    refused = bc("motion", project=proj)
    assert refused.returncode == 2, refused.stdout
    r = lint(proj)
    assert r.returncode == 3 and rows(proj)["motion:off"]["status"] == "skipped", r.stdout
    assert detail(proj, "motion:off").startswith("not verified: " + refused.stderr.strip().removeprefix("error: ")), (detail(proj, "motion:off"), refused.stderr)


def test_a_motion_json_that_says_on_records_no_nothing_moves_even_when_it_is_not_valid_in_itself(proj):
    """An answer that says the brand moves cannot contradict a motion round, whatever else is wrong with it (0.4.1 made every motion board not verified until an unrelated error was fixed):
    motion:off passes and names the error `brand-creator motion` refuses the file with; `check` fails it in motion:spec."""
    make_round(proj)
    (proj / "motion").mkdir()
    spec = proj / "motion" / "motion.json"
    on = {"schema": 1, "motion": "on", "signature": {"name": "Settle", "description": "The dot settles.", "where": ["app icon"]}}
    for doc in ({"schema": 1, "motion": "on"}, {**on, "colour": "x"}):                          # no signature; an unknown key
        spec.write_text(json.dumps(doc))
        refused = bc("motion", project=proj)
        assert refused.returncode == 2, refused.stdout
        r = lint(proj)
        assert r.returncode == 0 and rows(proj)["motion:off"]["status"] == "pass", (doc, r.stdout)
        assert refused.stderr.strip().removeprefix("error: ") in detail(proj, "motion:off") and "says the brand moves" in detail(proj, "motion:off"), detail(proj, "motion:off")


def test_a_motion_board_is_round_2_or_later_and_is_never_a_reset_round(proj):
    make_round(proj)
    text = (proj / "rounds" / "r2" / "board.html").read_text(encoding="utf-8")
    (proj / "rounds" / "r1" / "board.html").write_text(text.replace('data-round="2"', 'data-round="1"'), encoding="utf-8")
    r = lint(proj, "rounds/r1/board.html")
    assert r.returncode == 1 and "page:data-board" in failed(proj) and "a motion board is round 2 or later" in detail(proj, "page:data-board"), r.stdout
    zero = proj / "rounds" / "r0" / "board.html"
    zero.parent.mkdir()
    zero.write_text(text.replace('data-round="2"', 'data-round="0"'), encoding="utf-8")
    r = lint(proj, "rounds/r0/board.html")
    assert r.returncode == 1 and "page:data-board" in failed(proj) and "a motion board is round 2 or later" in detail(proj, "page:data-board")
    assert bc("state", "--set", "reset_rounds=[2]", project=proj).returncode == 0
    r = lint(proj)
    assert r.returncode == 1 and "round 2 is listed in reset_rounds" in detail(proj, "page:data-board"), r.stdout


@pytest.mark.parametrize("tier", ["quick", "standard", "full"])
def test_a_motion_board_is_allowed_in_any_tier(proj, tier):
    """Standard and Full run a motion round by default; Quick may run one when something moves."""
    assert bc("state", "--set", f"tier={tier}", project=proj).returncode == 0
    make_round(proj)
    r = lint(proj)
    assert r.returncode == 0, r.stdout


def test_an_unknown_kind_is_refused_and_the_message_names_the_four_kinds(proj):
    make_round(proj)
    mutate(proj / "rounds" / "r2" / "board.html", 'data-board="motion"', 'data-board="movement"')
    r = lint(proj)
    assert r.returncode == 1 and "pick|refine|style|motion" in detail(proj, "page:data-board")


# ---------------------------------------------------------------- what every board has, and what a motion board does not need

def test_the_sections_every_board_has_are_required_on_a_motion_board(proj):
    make_round(proj)
    page = proj / "rounds" / "r2" / "board.html"
    for sid in ("hardest-surface", "my-call", "questions", "reply"):
        before = mutate(page, f'data-section="{sid}"', f'data-removed="{sid}"')
        r = lint(proj)
        assert r.returncode == 1 and f"section:{sid}" in failed(proj), (sid, r.stdout)
        page.write_text(before)
    before = mutate(page, 'data-field="critique"', 'data-x="critique"')
    assert lint(proj).returncode == 1 and "my-call:critique" in failed(proj)
    page.write_text(before)
    mutate(page, '<li data-option="a" data-recommended="true">', '<li data-option="a">')    # exactly one recommended option
    assert lint(proj).returncode == 1 and "question:1:options" in failed(proj)


def test_a_motion_board_needs_no_map_no_directions_no_style_gate_no_inventory_and_measures_no_masters(proj):
    assert bc("state", "--set", "tier=full", "--set", "incumbent=the current wordmark", project=proj).returncode == 0   # Full tier with an incumbent: more than a refine board asks
    make_round(proj)
    (proj / "rounds" / "r2" / "Settle" / "mark.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 8"><rect width="8" height="8" fill="#ffffff"/></svg>')   # a master a refine board measures
    r = lint(proj)
    assert r.returncode == 0, r.stdout
    got = rows(proj)
    assert not any(k.startswith(("direction", "masters", "map:", "project:", "section:today", "section:positioning-map", "section:none-of-these", "section:losers", "section:strategy-core")) for k in got), sorted(got)
    r = lint(proj, "rounds/r2/board.html", "--min-directions", "3")
    assert r.returncode == 0 and rows(proj)["directions:count"]["status"] == "info" and "--min-directions is not used" in detail(proj, "directions:count")


def test_the_style_gate_never_counts_a_motion_board_as_the_rejected_round(proj):
    """r1 pick (rejected), r2 style (reset), r3 a motion board, r4 pick (reset): the rejected round is r1, and the style board of r2 comes after it. If a motion board counted as a
    round the owner rejected, the new style board would have to come after r3 and the pick of r4 would fail."""
    style = proj / "rounds" / "r2" / "board.html"
    style.parent.mkdir()
    style.write_text(fill_style_board((ROOT / "templates" / "style-board.html").read_text(encoding="utf-8")).replace('data-round="0"', 'data-round="2"'), encoding="utf-8")
    assert bc("state", "--record", "G1s", "picked Ember", project=proj).returncode == 0
    make_round(proj, 3)
    src = (proj / "rounds" / "r1" / "board.html").read_text(encoding="utf-8").replace('data-round="1"', 'data-round="4"')
    src = src.replace('<span class="axis x0">', '<span data-field="failed-round">Round 1 sat in the middle of the category norm.</span><span class="axis x0">', 1)
    extra = ('<section class="block" data-section="what-changed"><h2>What changed</h2><p>New territories after a full rejection.</p></section>\n'
             '<section class="block" data-section="weak-points"><h2>Weak points</h2><p>Untested at 16 px.</p></section>\n'
             '<section class="block" data-section="losers"><h2>Kept as losers</h2><div data-section="loser" data-name="Compass"><p data-field="reason">Round 1 was rejected as a whole.</p></div></section>\n')
    marker = '<section class="block" id="directions">'
    (proj / "rounds" / "r4").mkdir()
    (proj / "rounds" / "r4" / "board.html").write_text(src.replace(marker, extra + marker), encoding="utf-8")
    assert bc("state", "--set", "reset_rounds=[2, 4]", project=proj).returncode == 0
    r = lint(proj, "rounds/r4/board.html")
    assert r.returncode == 0, r.stdout
    gate = rows(proj)["project:style-gate"]
    assert gate["status"] == "pass" and "the rejected round is r1" in gate["detail"], gate


def test_a_motion_board_is_no_style_board_for_the_style_pick(proj):
    """`state --record G1s` writes g1s_round, the highest round whose board is a style board: a motion board is not one."""
    make_round(proj)
    assert bc("state", "--record", "G1s", "picked Ember", project=proj).returncode == 0
    assert bc("state", "--get", "g1s_round", project=proj).returncode == 1                   # no style board on disk: the key is not there


# ---------------------------------------------------------------- motion:files

def test_a_variant_needs_its_folder_its_page_its_proof_and_its_stills(proj):
    make_round(proj)
    d = proj / "rounds" / "r2" / "Bounce"
    for what, path, why in (("its page", d / "index.html", "Bounce: rounds/r2/Bounce/index.html is missing"),
                            ("its proof", d / "proof.json", "Bounce: rounds/r2/Bounce/proof.json is missing"),
                            ("its strip", d / "frames" / "Bounce" / "strip.png", "Bounce: rounds/r2/Bounce/frames/Bounce/strip.png is missing: run `brand-creator frames rounds/r2/Bounce/proof.json --count 25`"),
                            ("its reduced still", d / "frames" / "Bounce" / "reduced.png", "Bounce: rounds/r2/Bounce/frames/Bounce/reduced.png is missing")):
        moved = path.with_name(path.name + ".moved")
        path.rename(moved)
        r = lint(proj)
        assert r.returncode == 1 and "motion:files" in failed(proj), (what, r.stdout)
        assert why in detail(proj, "motion:files"), (what, detail(proj, "motion:files"))
        moved.rename(path)
    assert lint(proj).returncode == 0
    d.rename(proj / "rounds" / "r2" / "Bounce.moved")
    r = lint(proj)
    assert r.returncode == 1 and "Bounce: rounds/r2/Bounce/ does not exist" in detail(proj, "motion:files")


def test_a_card_and_its_folder_must_be_spelt_alike_letter_case_included(proj):
    """A disk that does not tell letter cases apart (macOS, Windows) opens rounds/r2/Bounce/ for a folder called bounce, so a card Bounce over it passed motion:files there, and `shot --motion` and `frames`, which name
    their reports after the proof as the disk spells it, never made the reports the board then asked for. Where letter cases differ (Linux) the folder Bounce is not there at all. The lint reads the listing of the round's
    folder, so both kinds of disk fail the same row in the same words, and renaming the folder back is the fix on either: the test asserts the same on both."""
    make_round(proj)
    rnd = proj / "rounds" / "r2"
    (rnd / "Bounce").rename(rnd / "bounce")
    listed = [e.name for e in rnd.iterdir()]
    assert "bounce" in listed and "Bounce" not in listed                                      # the listing spells it as renamed, whatever the disk makes of the other spelling
    r = lint(proj)
    assert r.returncode == 1 and "motion:files" in failed(proj), r.stdout
    why = detail(proj, "motion:files")
    assert why.startswith("Bounce: the card and its folder must be spelt alike, letter case included") and "the card says Bounce" in why and "rounds/r2/bounce/" in why, why
    assert "does not exist" not in why, why                                                  # the folder is there, spelt another way: that is what the row says
    (rnd / "bounce").rename(rnd / "Bounce")
    assert lint(proj).returncode == 0


def test_a_proof_needs_a_page_case_named_after_the_variant(proj):
    make_round(proj)
    proof = proj / "rounds" / "r2" / "Bounce" / "proof.json"
    for what, edit, why in (("a case with another name", lambda d: d["cases"][0].__setitem__("name", "Other"), "has no case named Bounce (it has: Other)"),
                            ("a states case", lambda d: d["cases"][0].__setitem__("type", "states"), "is not a page case"),
                            ("no page", lambda d: d["cases"][0].pop("page"), "names no page"),
                            ("no cases", lambda d: d.pop("cases"), "has no list of cases")):
        before = proof.read_text()
        mutate_json(proof, edit)
        reports_current(proj, 2, "Bounce")                                                    # the reports stay current: this test is about the proof
        r = lint(proj)
        assert r.returncode == 1 and why in detail(proj, "motion:files"), (what, detail(proj, "motion:files"))
        proof.write_text(before)
    proof.write_text("{not json")
    assert lint(proj).returncode == 1 and "rounds/r2/Bounce/proof.json cannot be read as JSON" in detail(proj, "motion:files")


def test_a_proof_copied_from_an_earlier_round_that_still_points_there_fails(proj):
    """Round 3 is round 2 copied whole, and the proofs were not fixed: their pages are still the pages of round 2."""
    make_round(proj)
    make_round(proj, 3, first=False)
    proof = proj / "rounds" / "r3" / "Glide" / "proof.json"
    mutate_json(proof, lambda d: d["cases"][0].__setitem__("page", "rounds/r2/Glide/index.html"))
    reports_current(proj, 3, "Glide")                                                        # the reports stay current: this test is about the proof
    r = lint(proj, "rounds/r3/board.html")
    assert r.returncode == 1 and "motion:files" in failed(proj), r.stdout
    assert ("the page case of rounds/r3/Glide/proof.json shows rounds/r2/Glide/index.html, not rounds/r3/Glide/index.html, the page the card links "
            "(a proof copied from an earlier round and not updated: point its page at rounds/r3/Glide/index.html)") in detail(proj, "motion:files")
    mutate_json(proof, lambda d: d["cases"][0].__setitem__("page", "rounds/r3/Glide/../../r2/Glide/index.html"))      # a path that climbs out is the same thing
    assert lint(proj, "rounds/r3/board.html").returncode == 1
    mutate_json(proof, lambda d: d["cases"][0].__setitem__("page", "rounds/r3/Glide/./index.html"))                   # the same page spelled another way is the page
    reports_current(proj, 3, "Glide")
    assert lint(proj, "rounds/r3/board.html").returncode == 0


def test_a_proof_proves_the_page_the_card_links_and_not_another_page_of_the_folder(proj):
    """The owner opens the live link of the card: a proof of a page beside it (a variant's other.html, which exists) proves a move the owner never sees."""
    make_round(proj)
    other = proj / "rounds" / "r2" / "Bounce" / "other.html"
    other.write_text("<!doctype html><title>other</title>\n")
    proof = proj / "rounds" / "r2" / "Bounce" / "proof.json"
    for page in ("rounds/r2/Bounce/other.html", "rounds/r2/Bounce/sub/../other.html", "rounds/r2/Bounce/nowhere.html"):      # one that exists, a path that leads to it, one that does not exist
        mutate_json(proof, lambda d: d["cases"][0].__setitem__("page", page))
        reports_current(proj, 2, "Bounce")                                                                           # the reports stay current: this test is about the proof
        r = lint(proj)
        assert r.returncode == 1 and "motion:files" in failed(proj), (page, r.stdout)
        assert (f"Bounce: the page case of rounds/r2/Bounce/proof.json shows {page}, not rounds/r2/Bounce/index.html, the page the card links") in detail(proj, "motion:files"), page
        mutate_json(proof, lambda d: d["cases"][0].__setitem__("page", "rounds/r2/Bounce/index.html"))
    reports_current(proj, 2, "Bounce")
    assert lint(proj).returncode == 0


def test_a_proof_compares_the_rest_frame_with_an_approved_master_never_with_a_still_of_the_variant(proj):
    make_round(proj)
    proof = proj / "rounds" / "r2" / "Settle" / "proof.json"
    (proj / "rounds" / "r2" / "Settle" / "mine.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 8"><rect width="4" height="4"/></svg>\n')
    (proj / "assets" / "states").mkdir()
    (proj / "assets" / "states" / "dot.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 8 8"><rect width="2" height="2"/></svg>\n')
    not_a_master = "is not an approved master of assets/logo/ (the rest frame is compared with the approved mark, never with a still of the variant's own)"
    for what, value, why in (("a still of its own in the round", "rounds/r2/Settle/mine.svg", f"Settle: the static rounds/r2/Settle/mine.svg of rounds/r2/Settle/proof.json {not_a_master}"),
                             ("a file of the project outside assets/logo/", "assets/states/dot.svg", f"the static assets/states/dot.svg of rounds/r2/Settle/proof.json {not_a_master}"),
                             ("a path that leaves assets/logo/", "assets/logo/../../rounds/r2/Settle/mine.svg", f"the static assets/logo/../../rounds/r2/Settle/mine.svg of rounds/r2/Settle/proof.json {not_a_master}"),
                             ("a master that is not there", "assets/logo/nope.svg", "Settle: the static assets/logo/nope.svg of rounds/r2/Settle/proof.json does not exist"),
                             ("no static", None, "Settle: the page case of rounds/r2/Settle/proof.json names no static (the approved master, for example assets/logo/mark.svg)")):
        before = proof.read_text()
        mutate_json(proof, lambda d: d["cases"][0].pop("static") if value is None else d["cases"][0].__setitem__("static", value))
        reports_current(proj, 2, "Settle")                                                                           # the reports stay current: this test is about the proof
        r = lint(proj)
        assert r.returncode == 1 and "motion:files" in failed(proj), (what, r.stdout)
        assert why in detail(proj, "motion:files"), (what, detail(proj, "motion:files"))
        proof.write_text(before)
    mutate_json(proof, lambda d: d["cases"][0].__setitem__("static", "assets/logo/./mark.svg"))                       # the master, spelled another way
    reports_current(proj, 2, "Settle")
    assert lint(proj).returncode == 0


def test_a_card_links_the_live_page_of_its_variant(proj):
    make_round(proj)
    page = proj / "rounds" / "r2" / "board.html"
    before = mutate(page, '<a data-field="live" href="Glide/index.html">', '<a data-field="live" href="Settle/index.html">')
    r = lint(proj)
    assert r.returncode == 1 and "Glide: the live link 'Settle/index.html' does not lead to rounds/r2/Glide/index.html" in detail(proj, "motion:files")
    page.write_text(before)
    mutate(page, '<a data-field="live" href="Glide/index.html">', '<a data-field="live">')
    r = lint(proj)
    assert r.returncode == 1 and "Glide: the card has no link to the live page" in detail(proj, "motion:files")
    page.write_text(before)
    mutate(page, '<a data-field="live" href="Glide/index.html">', '<a data-field="live" href="Glide/index.html?t=dark#top">')
    assert lint(proj).returncode == 0                                                        # a query or a fragment still leads to the page


# ---------------------------------------------------------------- motion:proof

def test_a_variant_needs_a_current_motion_report(proj):
    make_round(proj)
    cmd = "run `brand-creator shot --motion rounds/r2/Bounce/proof.json`"
    f = report_of(proj, 2, "Bounce")
    moved = f.with_name("bounce.moved")
    f.rename(moved)
    r = lint(proj)
    assert r.returncode == 1 and failed(proj) == ["motion:proof"], r.stdout
    assert f"Bounce: no motion report of rounds/r2/Bounce/proof.json: {cmd}" in detail(proj, "motion:proof")
    moved.rename(f)
    assert lint(proj).returncode == 0
    mutate(proj / "rounds" / "r2" / "Bounce" / "index.html", "<title>Bounce</title>", "<title>Bounce 2</title>")
    r = lint(proj)
    assert r.returncode == 1 and failed(proj) == ["motion:proof", "motion:stills"], r.stdout     # the page changed since the reports were made: the stills were taken of the old one too
    assert "Bounce: the motion report is stale (rounds/r2/Bounce/index.html changed)" in detail(proj, "motion:proof") and cmd in detail(proj, "motion:proof")
    motion_report(proj, proof_of(2, "Bounce"), "pass", "rounds/r2/Bounce/index.html")
    frames_report(proj, proof_of(2, "Bounce"), "Bounce", "rounds/r2/Bounce/index.html")
    assert lint(proj).returncode == 0


def test_a_report_that_is_not_a_verdict_or_not_for_this_proof_or_not_readable_is_not_a_pass(proj):
    make_round(proj)
    f = report_of(proj, 2, "Glide")
    good = f.read_text()
    not_verified(proj, "Glide", *RAF_ROWS)                                                   # a move driven by requestAnimationFrame
    r = lint(proj)
    why = detail(proj, "motion:proof")
    assert r.returncode == 1 and "Glide: the motion report is 'not-verified', not a verdict" in why
    assert "CSS animations, CSS transitions and element.animate() (Web Animations)" in why and "requestAnimationFrame stays not verified however often it runs" in why   # running it again changes nothing
    assert why.endswith("write the move with one of them, then run `brand-creator shot --motion rounds/r2/Glide/proof.json`") and "again" not in why
    f.write_text(good)
    mutate_json(f, lambda d: d.__setitem__("proof", "rounds/r1/Glide/proof.json"))
    r = lint(proj)
    assert r.returncode == 1 and "it is the report of rounds/r1/Glide/proof.json" in detail(proj, "motion:proof")
    f.write_text("{not json")
    r = lint(proj)
    assert r.returncode == 1 and "Glide: the motion report is stale (it cannot be read" in detail(proj, "motion:proof")


def test_a_report_that_is_not_a_verdict_quotes_the_rows_it_could_not_verify_and_gives_the_requestanimationframe_advice_only_when_one_names_it(proj):
    """`shot --motion` writes not-verified rows for CSS animations too: a percentage translate on a pseudo-element, a still that cannot be placed over the mark. Telling the owner to stop using
    requestAnimationFrame for those would send them to rewrite a move that is not driven by it: the row quotes what the report says, and says nothing about requestAnimationFrame."""
    make_round(proj)
    cmd = "`brand-creator shot --motion rounds/r2/Glide/proof.json`"
    f = report_of(proj, 2, "Glide")
    good = f.read_text()
    for what, rows in (("a percentage on a pseudo-element", PSEUDO_ROWS), ("a still that cannot be placed over the mark", UNPLACED_ROWS)):
        f.write_text(good)
        not_verified(proj, "Glide", *rows)
        r = lint(proj)
        why = detail(proj, "motion:proof")
        assert r.returncode == 1 and failed(proj) == ["motion:proof"], (what, r.stdout)
        assert why.startswith("Glide: the motion report is 'not-verified', not a verdict ("), (what, why)
        for end, text in rows:
            assert f"motion:Glide:{end}: {text}" in why, (what, why)                         # the detail of the row, whole
        assert "requestAnimationFrame" not in why and "element.animate()" not in why and "however often" not in why, (what, why)
        assert why.endswith(f"): change the page or the proof as the rows say, then run {cmd}"), (what, why)
    f.write_text(good)
    not_verified(proj, "Glide", *RAF_ROWS)                                                   # the same report of a move that is driven by it
    why = detail(proj, "motion:proof") if lint(proj).returncode == 1 else ""
    assert all(f"motion:Glide:{end}: {text}" in why for end, text in RAF_ROWS) and "requestAnimationFrame stays not verified however often it runs" in why, why
    f.write_text(good)
    not_verified(proj, "Glide", *PSEUDO_ROWS, *RAF_ROWS)                                     # one row that names it is enough: the advice is given, beside the other row
    why = detail(proj, "motion:proof") if lint(proj).returncode == 1 else ""
    assert "the translation of nudge cannot be read" in why and "requestAnimationFrame stays not verified however often it runs" in why, why
    f.write_text(good)
    assert lint(proj).returncode == 0


def test_a_report_that_is_not_a_verdict_shows_three_rows_cuts_a_long_one_and_says_when_it_lists_none(proj):
    make_round(proj)
    f = report_of(proj, 2, "Glide")
    good = f.read_text()
    not_verified(proj, "Glide", *(("row" + str(i), f"not verified: reason {i}") for i in range(1, 5)))
    assert lint(proj).returncode == 1
    why = detail(proj, "motion:proof")
    assert "(motion:Glide:row1: not verified: reason 1 | motion:Glide:row2: not verified: reason 2 | motion:Glide:row3: not verified: reason 3 | and 1 more)" in why and "row4" not in why, why
    f.write_text(good)
    not_verified(proj, "Glide", ("long", "not verified: " + "the translation of wiggle cannot be read " * 20))
    assert lint(proj).returncode == 1
    why = detail(proj, "motion:proof")
    quoted = why[why.index("(motion:Glide:long: ") + 1:why.index("...): ")]
    assert why.count("...") == 1 and 380 < len(quoted) <= 397 and "\n" not in why, (len(quoted), why)   # cut once, on one line
    f.write_text(good)
    mutate_json(f, lambda d: d.__setitem__("status", "not-verified"))                        # a report that says not-verified and lists no row that is
    assert lint(proj).returncode == 1
    why = detail(proj, "motion:proof")
    assert why == ("Glide: the motion report is 'not-verified', not a verdict (it lists no row that is not verified): run `brand-creator shot --motion rounds/r2/Glide/proof.json`"), why
    mutate_json(f, lambda d: d.pop("results"))                                               # no rows at all
    assert lint(proj).returncode == 1 and "(it lists no row that is not verified)" in detail(proj, "motion:proof")
    mutate_json(f, lambda d: d.__setitem__("results", "x"))                                  # rows that are not a list
    assert lint(proj).returncode == 1 and "(it lists no row that is not verified)" in detail(proj, "motion:proof")


def test_the_proof_line_of_a_card_must_equal_the_status_of_its_report_and_have_text(proj):
    make_round(proj, statuses={"Bounce": "fail"})                                            # the report says fail and the card says so: honest, and the board passes
    assert lint(proj).returncode == 0
    page = proj / "rounds" / "r2" / "board.html"
    before = page.read_text()
    assert before.count('<p class="proof" data-proof="fail">') == 1
    page.write_text(before.replace('<p class="proof" data-proof="fail">', '<p class="proof" data-proof="pass">'))
    r = lint(proj)
    assert r.returncode == 1 and 'Bounce: the card says data-proof="pass" and the motion report says fail' in detail(proj, "motion:proof"), r.stdout
    page.write_text(before.replace('<p class="proof" data-proof="fail">', '<p class="proof" data-proof="maybe">'))
    r = lint(proj)
    assert r.returncode == 1 and "Bounce: data-proof must be \"pass\" or \"fail\", got 'maybe'" in detail(proj, "motion:proof")
    page.write_text(re.sub(r'(<p class="proof" data-proof="fail">)[^<]*(</p>)', r"\1\2", before, count=1))
    r = lint(proj)
    assert r.returncode == 1 and "Bounce: the proof line has no text" in detail(proj, "motion:proof")
    page.write_text(before.replace('<p class="proof" data-proof="fail">', '<p class="proof">'))
    r = lint(proj)
    assert r.returncode == 1 and "Bounce: the card needs one proof line" in detail(proj, "motion:proof")


# ---------------------------------------------------------------- motion:stills

def test_the_stills_a_card_shows_are_the_bytes_frames_json_lists(proj):
    make_round(proj)
    strip = proj / "rounds" / "r2" / "Bounce" / "frames" / "Bounce" / "strip.png"
    before = strip.read_bytes()
    strip.write_bytes(Img(24, 8, "#ff0000").png())                                           # the strip was taken again by hand: frames.json lists other bytes
    r = lint(proj)
    assert r.returncode == 1 and "motion:stills" in failed(proj), r.stdout
    assert ("Bounce: rounds/r2/Bounce/frames/Bounce/strip.png is not the strip rounds/r2/Bounce/frames/Bounce/frames.json lists (its sha256 differs)") in detail(proj, "motion:stills")
    strip.write_bytes(before)
    page = proj / "rounds" / "r2" / "board.html"
    saved = mutate(page, 'src="Glide/frames/Glide/reduced.png"', 'src="Settle/frames/Settle/reduced.png"')   # the card shows another variant's picture
    r = lint(proj)
    assert r.returncode == 1 and "Glide: the reduced picture the card shows is not the one rounds/r2/Glide/frames/Glide/frames.json lists" in detail(proj, "motion:stills")
    page.write_text(saved)
    assert lint(proj).returncode == 0


def test_the_stills_must_be_those_frames_took_of_the_page_as_it_is_now(proj):
    """The page of a variant changed after `frames` took its stills. `shot --motion` run again, as the lint asks, makes the motion report current and says nothing about the stills."""
    make_round(proj)
    assert lint(proj).returncode == 0
    mutate(proj / "rounds" / "r2" / "Bounce" / "index.html", "<title>Bounce</title>", "<title>Bounce 2</title>")
    r = lint(proj)
    assert r.returncode == 1 and "motion:proof" in failed(proj)                              # the motion report is stale: the lint says so
    motion_report(proj, proof_of(2, "Bounce"), "pass", "rounds/r2/Bounce/index.html")        # `shot --motion` run again; `frames` was not
    r = lint(proj)
    assert r.returncode == 1 and failed(proj) == ["motion:stills"], r.stdout                 # the strip on the card is still the one of the old page
    assert ("Bounce: the frames report is stale (rounds/r2/Bounce/index.html changed): "
            "run `brand-creator frames rounds/r2/Bounce/proof.json --count 25`") in detail(proj, "motion:stills")
    frames_report(proj, proof_of(2, "Bounce"), "Bounce", "rounds/r2/Bounce/index.html")      # `frames` run again
    assert lint(proj).returncode == 0


def test_a_variant_needs_a_frames_report_that_exists_is_of_its_proof_and_passes_for_its_case(proj):
    make_round(proj)
    cmd = "run `brand-creator frames rounds/r2/Bounce/proof.json --count 25`"
    f = frames_report_of(proj, 2, "Bounce")
    good = f.read_text()
    moved = f.with_name("bounce.moved")
    f.rename(moved)
    r = lint(proj)
    assert r.returncode == 1 and failed(proj) == ["motion:stills"], r.stdout
    assert f"Bounce: no frames report of rounds/r2/Bounce/proof.json: {cmd}" in detail(proj, "motion:stills")
    moved.rename(f)
    assert lint(proj).returncode == 0
    mutate_json(f, lambda d: d.__setitem__("proof", "rounds/r1/Bounce/proof.json"))
    assert lint(proj).returncode == 1 and f"Bounce: the frames report is stale (it is the report of rounds/r1/Bounce/proof.json): {cmd}" in detail(proj, "motion:stills")
    f.write_text(good)
    mutate_json(f, lambda d: d["results"][0].__setitem__("status", "fail"))                  # `frames` found nothing to seek and said so
    r = lint(proj)
    assert r.returncode == 1 and failed(proj) == ["motion:stills"] and f"Bounce: frames:Bounce is fail in the frames report (x): {cmd}" in detail(proj, "motion:stills"), r.stdout
    f.write_text(good)
    mutate_json(f, lambda d: d["results"][0].__setitem__("id", "frames:Other"))              # a run of `frames --case Other`: no word on this case
    assert lint(proj).returncode == 1 and f"Bounce: the frames report has no row for the case Bounce (it has: frames:Other): {cmd}" in detail(proj, "motion:stills")
    f.write_text(good)
    mutate_json(f, lambda d: d.pop("results"))
    assert lint(proj).returncode == 1 and "Bounce: the frames report has no row for the case Bounce (it has: none)" in detail(proj, "motion:stills")
    f.write_text("{not json")
    r = lint(proj)
    assert r.returncode == 1 and "Bounce: the frames report is stale (it cannot be read" in detail(proj, "motion:stills")
    f.write_text(good)
    assert lint(proj).returncode == 0


def test_a_card_shows_a_picture_by_a_relative_path_or_a_data_uri_and_nothing_else(proj):
    make_round(proj)
    page = proj / "rounds" / "r2" / "board.html"
    text = page.read_text()
    plain = 'src="Settle/frames/Settle/strip.png"'
    uri = "data:image/png;base64," + base64.b64encode((proj / "rounds/r2/Settle/frames/Settle/strip.png").read_bytes()).decode()
    page.write_text(text.replace(plain, f'src="{uri}"'))
    assert lint(proj).returncode == 0                                                        # the copy of the page for the review surface: the same bytes, inlined
    page.write_text(text.replace(plain, f'src="{uri[:-8]}AAAAAAAA"'))
    r = lint(proj)
    assert r.returncode == 1 and "Settle: the strip picture the card shows is not the one" in detail(proj, "motion:stills")
    page.write_text(text.replace(plain, 'src="data:image/png;base64,@@@"'))
    assert lint(proj).returncode == 1 and "the strip picture is a data: URI that cannot be decoded" in detail(proj, "motion:stills")
    for src, why in (("https://example.com/strip.png", "a motion board shows the project's own file by a relative path, or a data: URI"), ("//cdn.example.com/s.png", "a relative path"),
                     ("/rounds/r2/Settle/frames/Settle/strip.png", "a relative path"), ("Settle/frames/Settle/nope.png", "does not exist"), ("../../../outside.png", "outside the project"),
                     ("", "has no src")):
        page.write_text(text.replace(plain, f'src="{src}"'))
        r = lint(proj)
        assert r.returncode == 1 and why in detail(proj, "motion:stills"), (src, detail(proj, "motion:stills"))
    page.write_text(text.replace('<img data-field="strip" src="Settle/frames/Settle/strip.png"', '<img src="Settle/frames/Settle/strip.png"'))
    assert lint(proj).returncode == 1 and 'Settle: the card needs one <img data-field="strip">' in detail(proj, "motion:stills")


def test_the_copy_for_the_review_surface_holds_the_pictures_as_data_uris_and_is_linted_with_the_round_flag(proj):
    make_round(proj)
    text = (proj / "rounds" / "r2" / "board.html").read_text()
    inlined = re.sub(r'src="([A-Za-z]+/frames/[A-Za-z]+/(?:strip|reduced)\.png)"',
                     lambda m: 'src="data:image/png;base64,' + base64.b64encode((proj / "rounds" / "r2" / m.group(1)).read_bytes()).decode() + '"', text)
    assert inlined.count("data:image/png;base64,") == 6
    review = proj / "review" / "index.html"
    review.parent.mkdir()
    review.write_text(inlined.replace('href="Glide/index.html"', 'href="../rounds/r2/Glide/index.html"'))      # the live page is where the board's folder is, seen from review/
    r = lint(proj, "review/index.html", "--round", "2")
    assert r.returncode == 0, r.stdout
    assert rows(proj)["motion:stills"]["status"] == "pass" and rows(proj)["motion:files"]["status"] == "pass"
    review.write_text(inlined.replace('data:image/png;base64,', 'data:image/png;base64,AAAA', 1))                # a picture that is not the file frames.json lists
    r = lint(proj, "review/index.html", "--round", "2")
    assert r.returncode == 1 and failed(proj) == ["motion:stills"], r.stdout
    review.write_text(inlined.replace('href="Glide/index.html"', 'href=""'))
    assert lint(proj, "review/index.html", "--round", "2").returncode == 1 and "Glide: the card has no link to the live page" in detail(proj, "motion:files")


def test_frames_json_must_be_the_one_written_for_this_proof_and_variant(proj):
    make_round(proj)
    fj = proj / "rounds" / "r2" / "Glide" / "frames" / "Glide" / "frames.json"
    mutate_json(fj, lambda d: d.__setitem__("proof", "rounds/r1/Glide/proof.json"))          # a folder copied from an earlier round, its stills not taken again
    r = lint(proj)
    assert r.returncode == 1 and ("Glide: rounds/r2/Glide/frames/Glide/frames.json is the stills of rounds/r1/Glide/proof.json (case Glide), not of rounds/r2/Glide/proof.json "
                                  "(a folder copied from an earlier round): run `brand-creator frames rounds/r2/Glide/proof.json --count 25`") in detail(proj, "motion:stills")
    mutate_json(fj, lambda d: d.__setitem__("proof", "rounds/r2/Glide/proof.json"))
    mutate_json(fj, lambda d: d["strip"].__setitem__("sha256", "0" * 64))
    assert lint(proj).returncode == 1 and "is not the strip" in detail(proj, "motion:stills")
    mutate_json(fj, lambda d: d["strip"].pop("sha256"))
    assert lint(proj).returncode == 1 and "lists no strip with a sha256" in detail(proj, "motion:stills")
    fj.write_text("{not json")
    assert lint(proj).returncode == 1 and "rounds/r2/Glide/frames/Glide/frames.json cannot be read" in detail(proj, "motion:stills")
    fj.write_text("[]")
    assert lint(proj).returncode == 1 and "is not a JSON object" in detail(proj, "motion:stills")


# ---------------------------------------------------------------- motion:fields

@pytest.mark.parametrize("fid, label", [("what-it-is", "What it is"), ("cost", "Cost"), ("degrades-to", "Degrades to")])
def test_a_card_says_what_it_is_what_it_costs_and_what_it_degrades_to(proj, fid, label):
    make_round(proj)
    page = proj / "rounds" / "r2" / "board.html"
    text = page.read_text()
    pat = re.compile(rf'(<dd data-field="{fid}">)[^<]*(</dd>)')
    assert pat.search(text)
    page.write_text(pat.sub(r"\1\2", text, count=1))
    r = lint(proj)
    assert r.returncode == 1 and "motion:fields" in failed(proj), r.stdout
    assert f'Settle: {label} is missing or empty (data-field="{fid}" inside the card)' in detail(proj, "motion:fields")
    page.write_text(pat.sub(r"\1TODO\2", text, count=1))
    assert lint(proj).returncode == 1 and "motion:fields" in failed(proj)                    # a placeholder is not text
    page.write_text(pat.sub(r"\1[[fill: say what it is]]\2", text, count=1))
    assert lint(proj).returncode == 1 and {"page:unfilled", "motion:fields"} <= set(failed(proj))
    assert f"Settle: {label} still holds a [[fill: ...]] marker" in detail(proj, "motion:fields")
    page.write_text(text.replace(f'data-field="{fid}"', f'data-x="{fid}"', 1))
    assert lint(proj).returncode == 1 and "motion:fields" in failed(proj)                    # the field is missing


def test_a_field_belongs_to_its_own_card(proj):
    """Cost written on the first card does not stand for the second: the lint reads each card by itself."""
    make_round(proj)
    page = proj / "rounds" / "r2" / "board.html"
    text = page.read_text()
    cut = text.index('data-field="cost"', text.index('<article class="variant" data-motion-variant="Bounce"'))
    page.write_text(text[:cut] + 'data-x="cost"' + text[cut + len('data-field="cost"'):])
    r = lint(proj)
    assert r.returncode == 1 and "Bounce: Cost is missing or empty" in detail(proj, "motion:fields") and "Settle: Cost" not in detail(proj, "motion:fields")


# ---------------------------------------------------------------- the report and `check`

def test_the_lint_report_of_a_motion_board_goes_stale_when_a_variant_file_it_read_changes(proj):
    make_round(proj)
    assert lint(proj).returncode == 0
    inputs = [i["path"] for i in report(proj, "board-lint")["inputs"]]
    for want in ("rounds/r2/board.html", "rounds/r2/Settle/proof.json", "rounds/r2/Settle/index.html", "rounds/r2/Settle/frames/Settle/frames.json", "rounds/r2/Settle/frames/Settle/strip.png",
                 "rounds/r2/Glide/frames/Glide/reduced.png", report_of(proj, 2, "Glide").relative_to(proj).as_posix(), frames_report_of(proj, 2, "Glide").relative_to(proj).as_posix()):
        assert want in inputs, (want, inputs)                                                # the motion and the frames report each card was compared with are among them
    bc("check", project=proj)
    row = lambda: next(x for x in report(proj, "check")["results"] if x["id"] == "report:board-lint")   # noqa: E731
    assert row()["status"] == "pass"
    (proj / "rounds/r2/Glide/frames/Glide/strip.png").write_bytes(Img(24, 8, "#00ff00").png())   # the stills were taken again after the lint
    bc("check", project=proj)
    assert row()["status"] == "skipped" and "rounds/r2/Glide/frames/Glide/strip.png changed" in row()["detail"] and "brand-creator board-lint rounds/r2/board.html" in row()["detail"]


def test_the_lint_report_goes_stale_when_a_file_the_page_of_a_variant_loads_changes(proj):
    """`shot --motion` and `frames` record every file the page loaded (a stylesheet, tokens.css, a script) as inputs of their reports, so the move that lives in one is part of the proof. The lint report lists
    the files those reports were made from too: after a change to one (here the move's stylesheet, 320 ms to 900 ms) the strip on the card is of the old move, and `check` must not call the lint current."""
    make_round(proj)
    css = proj / "rounds/r2/Bounce/move.css"
    css.write_text("#mark{animation:press 320ms steps(2,end) 1 both}\n")
    mutate(proj / "rounds/r2/Bounce/index.html", "<title>Bounce</title>", '<title>Bounce</title><link rel="stylesheet" href="move.css">')
    reports_current(proj, 2, "Bounce", loaded=("rounds/r2/Bounce/move.css",))
    assert lint(proj).returncode == 0
    assert "rounds/r2/Bounce/move.css" in [i["path"] for i in report(proj, "board-lint")["inputs"]]
    row = lambda: next(x for x in report(proj, "check")["results"] if x["id"] == "report:board-lint")   # noqa: E731
    bc("check", project=proj)
    assert row()["status"] == "pass"
    mutate(css, "320ms", "900ms")                                                            # the move changed; the two reports and the lint report were made before
    bc("check", project=proj)
    got = row()
    assert got["status"] == "skipped" and "rounds/r2/Bounce/move.css changed" in got["detail"] and "brand-creator board-lint rounds/r2/board.html" in got["detail"], got
    r = lint(proj)                                                                           # and the lint itself says the reports are of the old move
    assert r.returncode == 1 and failed(proj) == ["motion:proof", "motion:stills"], r.stdout
    assert "Bounce: the motion report is stale (rounds/r2/Bounce/move.css changed)" in detail(proj, "motion:proof")
    reports_current(proj, 2, "Bounce", loaded=("rounds/r2/Bounce/move.css",))                # `shot --motion` and `frames` run again, then the lint
    assert lint(proj).returncode == 0
    bc("check", project=proj)
    assert row()["status"] == "pass"


def test_the_lint_report_of_a_motion_board_goes_stale_when_motion_json_changes(proj):
    """motion:off reads motion/motion.json, so the lint report lists it: an answer changed after the lint (on to off, here) makes `check` ask for the lint again, and that lint finds the
    contradiction. Before 0.4.2 the passing report stayed current and nothing said that the round now contradicts a recorded "nothing moves"."""
    make_round(proj)
    (proj / "motion").mkdir()
    spec = proj / "motion" / "motion.json"
    spec.write_text(json.dumps({"schema": 1, "motion": "on"}))                                  # not valid in itself, but says the brand moves: the lint passes
    assert lint(proj).returncode == 0 and rows(proj)["motion:off"]["status"] == "pass"
    assert "motion/motion.json" in {i["path"] for i in report(proj, "board-lint")["inputs"]}
    spec.write_text(json.dumps({"schema": 1, "motion": "off", "reason": "The brand has no screen presence."}))
    bc("check", project=proj)
    got = next(x for x in report(proj, "check")["results"] if x["id"] == "report:board-lint")
    assert got["status"] == "skipped" and "motion/motion.json changed" in got["detail"], got
    assert lint(proj).returncode == 1 and rows(proj)["motion:off"]["status"] == "fail"


def test_check_wants_the_lint_and_the_shot_of_the_latest_round_when_it_is_a_motion_round(proj):
    make_round(proj)
    assert lint(proj).returncode == 0
    bc("check", project=proj)
    ids = {x["id"]: x for x in report(proj, "check")["results"]}
    assert ids["report:board-lint"]["status"] == "pass"
    assert ids["report:shot"]["status"] == "skipped" and "brand-creator shot rounds/r2/board.html" in ids["report:shot"]["detail"]      # the board is shot last: its report is still to come
