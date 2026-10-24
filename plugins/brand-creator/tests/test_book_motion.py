"""The brand book's motion chapter: the motion spec as the chapter shows it (the signature move, the parts, the timeline with every reference as its token and its
value, the tokens with their curves drawn, the rules), the replay built from the stills `frames` wrote (markup, rules, warnings), and the book-lint rows that guard it
(motion:reduced, motion:replay, motion:stills, self:durations), each broken on purpose. The stills here are written by a helper: a flipbook needs pictures, not a
browser. A real browser plays one in tests/node/bookmotion.test.mjs, and the Acme smoke builds one from real stills."""
import base64
import hashlib
import json
import re
import shutil
import zlib
from pathlib import Path

import pytest
from helpers import ROOT, bc, fill_markers, mutate, mutate_json, report
from test_motionspec import off_doc, on_doc

import bookdata
import bookgen
import booklint
import htmlscan
from _common import motion_report_tool, sha256_file
from px_lib import Img

pytestmark = [pytest.mark.requires_setup, pytest.mark.requires_resvg]
SPEC = "motion/motion.json"
CASE = "demo-page"
FRAMES = f"motion/frames/{CASE}"
LENGTH = 400   # the replay's length in ms: not one of the tokens (150, 120, 160, 320, 640), so that a replay's own durations are told from the tokens'
OLDER = "the book shows stills older than motion/frames: run brand-creator book"


# ---------------------------------------------------------------- helpers

def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def frames_report_name(proof: str) -> str:
    """Where `frames` keeps its report of a proof, assets/_checks/<this>.json: the twin of proofReportTool in _common.mjs written out here, so that these tests do not
    use the code they test (a real run of `frames` checks the twin: test_a_case_folder_and_a_report_are_named_as_frames_names_them_and_every_real_replay_lints)."""
    stem = proof.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    return "frames/" + (re.sub(r"[^A-Za-z0-9]+", "-", stem).strip("-").lower() or "proof") + "-" + hashlib.sha256(proof.encode()).hexdigest()[:6]


def page_case(p: Path, case: str, proof: str = "motion/proof.json") -> None:
    """Make `case` a page case of the proof (a copy of the demo's, under another name), when the proof is a file of the project that has a list of cases."""
    f = p / proof
    if not f.is_file():
        return
    doc = json.loads(f.read_text())
    if not isinstance(doc.get("cases"), list) or any(c.get("name") == case and c.get("type") == "page" for c in doc["cases"]):
        return
    demo = next((c for c in json.loads((ROOT / "skills/brand-creator/references/examples/acme/motion/proof.json").read_text())["cases"] if c["type"] == "page"), None)
    doc["cases"] = [c for c in doc["cases"] if c.get("name") != case] + [{**demo, "name": case}]
    f.write_text(json.dumps(doc, indent=2) + "\n")


def write_frames(p: Path, case: str = CASE, proof: str = "motion/proof.json", n: int = 9, length_ms: float = LENGTH, size=(8, 8), scale: int = 2,
                 pcts=None, report_: bool = True, shade: int = 0, vouch=None) -> dict:
    """What `frames` writes for a page case, made by hand: n stills (a square that moves from one to the next), the strip, the reduced still, frames.json and the
    report of the run (its inputs are the proof and the page, so it goes stale when they change). `shade` makes other pictures of the same size. The case is made a
    page case of its proof, and the report vouches for it alone, as the run of `frames --case` does: `vouch` names the cases of a run that took several."""
    page_case(p, case, proof)
    w, h = size
    pcts = pcts if pcts is not None else ([0] if n == 1 else [round(100 * i / (n - 1), 2) for i in range(n)])
    folder = bookdata.case_folder(case)
    d = p / "motion" / "frames" / folder
    d.mkdir(parents=True, exist_ok=True)
    pad = max(2, len(str(len(pcts) - 1)))
    ink = ["#007d71", "#0d1b2d", "#4b596c", "#c03030"][shade % 4]
    stills, files = [], []
    for i, pct in enumerate(pcts):
        img = Img(w * scale, h * scale, "#f9f7ee")
        img.rect(1 + i % (w * scale - 5), 3 + i % 5, 4, 4, ink)
        name = f"{i:0{pad}d}-{pct:g}.png"
        (d / name).write_bytes(img.png())
        stills.append(img)
        files.append({"percent": pct, "ms": round(length_ms * pct) / 100, "file": f"motion/frames/{folder}/{name}", "sha256": sha((d / name).read_bytes())})
    strip = Img(w * scale * len(pcts), h * scale, "#f9f7ee")
    for i, img in enumerate(stills):
        strip.blit(img, i * w * scale, 0)
    (d / "strip.png").write_bytes(strip.png())
    reduced = Img(w * scale, h * scale, "#f9f7ee")
    reduced.rect(2, 2, 4, 4, "#0d1b2d")
    (d / "reduced.png").write_bytes(reduced.png())
    doc = {"schema": 1, "case": case, "proof": proof, "page": "motion/demo.html", "selector": "#mark", "length_ms": length_ms, "scale": scale, "size": [w, h], "frames": files,
           "strip": {"file": f"motion/frames/{folder}/strip.png", "sha256": sha((d / "strip.png").read_bytes())},
           "reduced": {"file": f"motion/frames/{folder}/reduced.png", "sha256": sha((d / "reduced.png").read_bytes())}}
    (d / "frames.json").write_text(json.dumps(doc, indent=2) + "\n")
    if report_:
        tool = frames_report_name(proof)
        out = p / "assets" / "_checks" / f"{tool}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        ins = [f for f in (p / proof, p / "motion/demo.html") if f.is_file()]
        took = vouch if vouch is not None else [case]
        out.write_text(json.dumps({"tool": tool, "version": "0", "inputs_sha": "0" * 64, "inputs": [{"path": f.relative_to(p).as_posix(), "sha256": sha256_file(f)} for f in ins],
                                   "renderer": "x", "results": [{"id": f"frames:{c}", "status": "pass", "label": "x"} for c in took], "status": "pass", "proof": proof,
                                   "cases": [{"name": c} for c in took], "points_pct": pcts}, indent=2) + "\n")
    return doc


def write_spec(p: Path, doc) -> None:
    (p / "motion").mkdir(exist_ok=True)
    (p / SPEC).write_text(doc if isinstance(doc, str) else json.dumps(doc, indent=2) + "\n", encoding="utf-8")


def put_report(p: Path, proof: str, rows: list[tuple[str, str]]) -> None:
    """The report `shot --motion` writes for a proof (assets/_checks/motion/<slug>-<hash6>.json), written by hand."""
    f = p / proof
    f.parent.mkdir(parents=True, exist_ok=True)
    if not f.is_file():
        f.write_text('{"schema": 1, "cases": []}\n')
    out = p / "assets" / "_checks" / (motion_report_tool(proof) + ".json")
    out.parent.mkdir(parents=True, exist_ok=True)
    cases = [{"name": c["name"], "type": c["type"]} for c in json.loads(f.read_text()).get("cases", [])]   # the cases of the proof, as `shot --motion` records them
    out.write_text(json.dumps({"tool": motion_report_tool(proof), "version": "0", "inputs_sha": "0" * 64, "inputs": [{"path": proof, "sha256": sha256_file(f)}], "renderer": "x",
                               "results": [{"id": i, "status": s, "label": "x", "detail": ""} for i, s in rows], "status": "pass", "proof": proof, "cases": cases}, indent=2) + "\n")


def build(p: Path, code: int = 0):
    r = bc("book", project=p)
    assert r.returncode == code, r.stdout + r.stderr
    return r


def html_of(p: Path) -> str:
    return (p / "book.html").read_text()


def motion_warnings(p: Path) -> list[str]:
    return [x["detail"] for x in report(p, "book")["results"] if x["id"] == "book:motion" and x["status"] == "warn"]


def lint(p: Path) -> dict:
    """book-lint --self-consistency; -> {row id: row}."""
    bc("book-lint", "--self-consistency", project=p)
    return {x["id"]: x for x in report(p, "book-lint")["results"]}


def chapter(html: str, cid: str) -> str:
    t = next(t for t in htmlscan.tags(html) if t.name == "section" and t.attrs.get("data-chapter") == cid)
    return html[t.start:htmlscan.element_end(html, t)]


def figure(html: str, case: str = CASE) -> str:
    t = next(t for t in htmlscan.tags(html) if t.name == "figure" and t.attrs.get("data-motion-demo") == case)
    return html[t.start:htmlscan.element_end(html, t)]


def css_of(html: str) -> str:
    return html.split("<style>", 1)[1].split("</style>", 1)[0]


def table_after(sec: str, heading: str, tag: str = "h4") -> list[list[str]]:
    """The cell texts of the rows of every table after the heading (it may carry attributes), up to the next heading."""
    rest = sec[re.search(rf"<{tag}\b[^>]*>{re.escape(heading)}</{tag}>", sec).end():]
    nxt = re.search(r"<h[34]\b", rest)
    rest = rest[:nxt.start()] if nxt else rest
    rows = re.findall(r"<tr\b[^>]*>(.*?)</tr>", rest, re.S)
    return [[htmlscan.visible_text(c, with_attributes=False) for c in re.findall(r"<td\b[^>]*>(.*?)</td>", row, re.S)] for row in rows if "<td" in row]


def keyframes(css: str, name: str) -> list[tuple[float, str]]:
    """The steps of a flipbook's @keyframes: (percent, the x of its object-position)."""
    m = re.search(r"@keyframes " + re.escape(name) + r"\{(.*?)\}\}", css)
    assert m, f"no @keyframes {name}"
    return [(float(a), b) for a, b in re.findall(r"([\d.]+)%\{object-position:(\S+) 0\}", m.group(1) + "}")]


def rule_body(css: str, selector: str) -> str:
    m = re.search(re.escape(selector) + r"\{([^}]*)\}", css)
    assert m, f"no rule for {selector}"
    return m.group(1)


def groups(d: dict) -> None:
    """The motion tokens of a starter: durations (a distance and a duration of another group among them) and three curves."""
    d["motion"] = {"$type": "duration", "quick": {"$value": {"value": 160, "unit": "ms"}}, "base": {"$value": {"value": 320, "unit": "ms"}},
                   "stagger": {"$value": {"value": 120, "unit": "ms"}}, "distance": {"$type": "dimension", "$value": {"value": 8, "unit": "px"}}}
    d["timing"] = {"$type": "duration", "slow": {"$value": {"value": 640, "unit": "ms"}}}
    d["easing"] = {"$type": "cubicBezier", "standard": {"$value": [0.2, 0, 0, 1]}, "enter": {"$value": [0, 0, 0, 1]}, "exit": {"$value": [0.3, 0, 1, 1]}}


@pytest.fixture(scope="session")
def mbase(golden, tmp_path_factory):
    """Acme at the Standard tier in English with motion and easing tokens built and every chapter written: no motion spec, no stills, no book."""
    if shutil.which("resvg") is None:
        pytest.skip("NOT VERIFIED: resvg is not installed")
    p = tmp_path_factory.mktemp("motionbook") / "acme"
    shutil.copytree(golden, p)
    mutate_json(p / "tokens" / "primitives.tokens.json", groups)
    for cmd in (("tokens",), ("state", "--set", "tier=standard"), ("state", "--set", "content_languages=en")):
        r = bc(*cmd, project=p)
        assert r.returncode == 0, r.stdout + r.stderr
    mutate(p / "BRAND-STATE.md", "- (rule) (...)", "- (rule) the accent is a fill, never text (proposal)")
    assert bc("book", "--init", project=p).returncode == 0
    assert fill_markers(p) > 5
    return p


@pytest.fixture
def mp(mbase, tmp_path):
    dst = tmp_path / "acme"
    shutil.copytree(mbase, dst)
    return dst


@pytest.fixture(scope="session")
def mbook(mbase, tmp_path_factory):
    """The book of an Acme that moves: motion.json on, nine stills of the demo page, built."""
    p = tmp_path_factory.mktemp("motionbook2") / "acme"
    shutil.copytree(mbase, p)
    write_spec(p, on_doc())
    write_frames(p)
    build(p)
    return p


@pytest.fixture
def bp(mbook, tmp_path):
    dst = tmp_path / "acme-book"
    shutil.copytree(mbook, dst)
    return dst


# ---------------------------------------------------------------- A: the motion spec as the chapter shows it

def test_the_motion_block_shows_the_signature_parts_timeline_tokens_and_rules_with_every_reference_as_token_and_value(mp):
    doc = on_doc()
    doc["timeline"].append({"part": "dot", "property": "opacity", "start": "{motion.base} + {motion.stagger} * 2", "duration": "{motion.quick}", "easing": "{easing.standard}"})
    write_spec(mp, doc)
    r = build(mp)
    sec = chapter(html_of(mp), "motion")
    assert "<p><strong>Signature move: Settle.</strong> The dot drops onto the grid and settles.</p>" in sec
    assert "<p>Shown in:</p><ul><li>app icon</li><li>empty states</li></ul>" in sec
    assert table_after(sec, "Parts") == [["dot", "The accent dot of the mark."], ["ring-outer", "The outer ring."]]
    # a start is its sum in ms next to the expression, a duration its ms and token, an easing its four numbers and token (motion.stagger 120, base 320, quick 160, fast 150)
    assert table_after(sec, "Timeline") == [
        ["dot", "transform", "120 ms motion.stagger", "320 ms motion.base", "cubic-bezier(0.2, 0, 0, 1) easing.standard", "drops two pixels"],
        ["ring-outer", "opacity", "240 ms motion.stagger × 2", "320 ms motion.base", "cubic-bezier(0, 0, 0, 1) easing.enter", ""],
        ["dot", "transform", "0 ms", "150 ms duration.fast", "cubic-bezier(0.3, 0, 1, 1) easing.exit", ""],
        ["dot", "opacity", "560 ms motion.base + motion.stagger × 2", "160 ms motion.quick", "cubic-bezier(0.2, 0, 0, 1) easing.standard", ""]]
    tokens = table_after(sec, "Motion tokens")
    assert tokens[:5] == [["duration.fast", "150 ms"], ["motion.base", "320 ms"], ["motion.quick", "160 ms"], ["motion.stagger", "120 ms"], ["timing.slow", "640 ms"]]   # by type, not by group
    assert [r[:2] for r in tokens[5:8]] == [["easing.enter", "cubic-bezier(0, 0, 0, 1)"], ["easing.exit", "cubic-bezier(0.3, 0, 1, 1)"], ["easing.standard", "cubic-bezier(0.2, 0, 0, 1)"]]
    assert tokens[8:] == [["motion.distance", "8px"]]                                  # a token of the motion groups that is neither a duration nor a curve stays as the tokens write it
    assert '<h4>Motion rules</h4><ul><li>reduced motion: nothing moves</li><li>nothing loops forever</li></ul>' in sec
    assert not [w for w in motion_warnings(mp) if "motion.json is missing" in w]
    assert any("no motion report; the motion proof table is left out" in w for w in motion_warnings(mp)), r.stdout       # a motion that moves wants its proof
    put_report(mp, "motion/proof.json", [("motion:demo-page:cls:normal", "pass")])
    build(mp)
    sec = chapter(html_of(mp), "motion")
    assert table_after(sec, "Motion proof") == [["Case 2", "cls:normal", "pass"]] and "motion:demo-page" not in sec      # the proof tables stay: the check, under its case's number


def test_each_curve_is_drawn_as_an_svg_with_a_role_an_aria_label_and_no_text(mp):
    write_spec(mp, on_doc())
    build(mp)
    sec = chapter(html_of(mp), "motion")
    svgs = re.findall(r"<svg\b.*?</svg>", sec)
    assert len(svgs) == 3
    labels = [re.search(r'aria-label="([^"]*)"', s).group(1) for s in svgs]
    assert labels == ["easing.enter: cubic-bezier(0, 0, 0, 1)", "easing.exit: cubic-bezier(0.3, 0, 1, 1)", "easing.standard: cubic-bezier(0.2, 0, 0, 1)"]
    assert all('role="img"' in s and "<text" not in s and "<tspan" not in s and s.count("<path") == 1 for s in svgs)      # one path: the curve (the guides are two lines)
    assert bc("book-lint", "--self-consistency", project=mp).returncode == 0       # marks:lint reads every inline <svg>: pure vector, and self:colours: no colour of its own


def curve_points(svg: str) -> tuple[float, list[tuple[float, float]]]:
    """(the height of the drawing, 200 points of its curve in drawing pixels), read back from the path alone."""
    h = float(re.search(r'viewBox="0 0 [\d.]+ ([\d.]+)"', svg).group(1))
    d = re.findall(r'd="(M[^"]*C[^"]*)"', svg)[0]
    x0, y0, x1, y1, x2, y2, x3, y3 = (float(v) for v in re.findall(r"-?[\d.]+", d))
    pts = []
    for i in range(201):
        t = i / 200
        a, b, c, e = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
        pts.append((a * x0 + b * x1 + c * x2 + e * x3, a * y0 + b * y1 + c * y2 + e * y3))
    return h, pts


def test_a_curve_drawing_is_the_same_every_time_and_has_room_for_an_overshoot_above_one_and_below_zero():
    linear = bookgen.curve_svg("easing.linear", [0, 0, 1, 1])
    assert linear == ('<svg class="curve" viewBox="0 0 52 52" width="52" height="52" role="img" aria-label="easing.linear: cubic-bezier(0, 0, 1, 1)">'
                      '<g stroke="currentColor" stroke-opacity=".35" stroke-dasharray="2 3"><line x1="6" y1="46" x2="46" y2="46"/><line x1="6" y1="6" x2="46" y2="6"/></g>'
                      '<path d="M6 46C6 46 46 6 46 6" fill="none" stroke="currentColor" stroke-width="2"/></svg>')
    assert bookgen.curve_svg("easing.linear", [0, 0, 1, 1]) == linear
    for c in ([0.34, 1.56, 0.64, 1], [0.5, -0.6, 0.5, 1], [0.2, 0, 0, 1], [0.7, -1.2, 0.3, 2.4], [0.25, 0.1, 0.25, 1], [0.5, 2, 0.5, 2], [0, 1.5, 1, -0.5]):
        svg = bookgen.curve_svg("easing.x", c)
        h, pts = curve_points(svg)
        assert all(0 <= y <= h for _x, y in pts), (c, h, min(y for _x, y in pts), max(y for _x, y in pts))      # the whole curve is in the picture
        assert not re.search(r"\d[eE][+-]?\d", svg) and "<text" not in svg
    height = lambda c: float(re.search(r'height="([\d.]+)"', bookgen.curve_svg("e", c)).group(1))   # noqa: E731
    assert height([0.2, 0, 0, 1]) == 52 and height([0.34, 1.56, 0.64, 1]) > 52 and height([0.5, -0.6, 0.5, 1]) > 52      # an ease needs 52 px, an overshoot or an anticipation more
    assert "cubic-bezier(0.0000001, 0.3, 0.2, 1)" in bookgen.curve_svg("easing.tiny", [1e-07, 0.3, 0.2, 1])      # plain decimals, as tokens.css prints them


def test_a_curve_and_a_number_print_as_the_adapters_and_the_tokens_print_them():
    import adapt
    for c in ([0.2, 0, 0, 1], [0.34, 1.56, 0.64, 1], [1e-07, 0.3, 0.2, 1], [0, 0, 1, 1], [0.1, 0.30000000000000004, 0.5, 1]):
        assert bookdata.curve_css(c) == adapt.bezier(c)
    assert [bookdata.num_text(v) for v in (0, -0.0, 240, 3.5, 16.666666, 0.0004, 1e6)] == ["0", "0", "240", "3.5", "16.667", "0", "1000000"]
    assert bookdata.num_text(16.666666, 2) == "16.67" and bookdata.num_text(12.5, 2) == "12.5"


def test_motion_off_says_why_nothing_moves_shows_no_demo_even_with_stills_and_does_not_ask_for_a_proof(mp):
    write_spec(mp, off_doc())
    write_frames(mp)
    build(mp)
    sec = chapter(html_of(mp), "motion")
    assert "<p>Nothing moves: The owner wants a still brand: nothing in it needs to move.</p>" in sec
    assert "data-motion-demo" not in html_of(mp) and "motion-demo" not in css_of(html_of(mp)) and "Signature move" not in sec and "<table" not in sec
    ws = motion_warnings(mp)
    assert any("says nothing moves" in w and "demo-page" in w and "left out" in w for w in ws), ws
    assert not [w for w in ws if "no motion report" in w]                           # nothing moves: no proof to wait for
    put_report(mp, "motion/proof.json", [("motion:demo-page:cls:normal", "pass")])  # a proof that exists is shown
    build(mp)
    assert table_after(chapter(html_of(mp), "motion"), "Motion proof") == [["Case 2", "cls:normal", "pass"]]


def test_without_motion_json_the_chapter_keeps_its_token_table_and_the_build_says_what_is_missing(mp):
    r = build(mp)
    sec = chapter(html_of(mp), "motion")
    assert table_after(sec, "The motion", tag="h3") == [["duration.fast", "150ms"], ["easing.enter", "cubic-bezier(0, 0, 0, 1)"], ["easing.exit", "cubic-bezier(0.3, 0, 1, 1)"],
                                                         ["easing.standard", "cubic-bezier(0.2, 0, 0, 1)"], ["motion.base", "320ms"], ["motion.distance", "8px"],
                                                         ["motion.quick", "160ms"], ["motion.stagger", "120ms"]]       # every duration, easing and motion token, as the tokens write it
    assert "Signature move" not in sec and "<svg" not in sec and "data-motion-demo" not in sec
    ws = motion_warnings(mp)
    assert any("motion/motion.json is missing" in w and "no signature move and no timeline" in w for w in ws), ws
    assert any("no stills in motion/frames/" in w and "brand-creator frames motion/proof.json --count 25" in w for w in ws), r.stdout   # an older project is told about the replay too


def test_a_motion_json_that_is_not_valid_stops_the_book_with_exit_2(mp):
    write_spec(mp, {**on_doc(), "colour": "teal"})
    r = bc("book", project=mp)
    assert r.returncode == 2 and "colour: unknown key" in r.stderr and not (mp / "book.html").exists()
    write_spec(mp, "{not json")
    r = bc("book", project=mp)
    assert r.returncode == 2 and "cannot be read as JSON" in r.stderr
    spec = on_doc()
    spec["timeline"][0]["easing"] = "{easing.nope}"
    write_spec(mp, spec)
    r = bc("book", project=mp)
    assert r.returncode == 2 and "easing.nope" in r.stderr and report(mp, "book")["status"] == "fail"      # the run's report says it stopped


def test_the_motion_chapter_appears_once_motion_is_decided_in_motion_json_on_or_off(tmp_path):
    view = {"tier": "standard", "architecture": "standalone", "book_chapters": []}
    assert "motion" not in bookdata.chapters_for(tmp_path, view)
    (tmp_path / "motion").mkdir()
    for doc in (on_doc(), off_doc()):
        (tmp_path / "motion/motion.json").write_text(json.dumps(doc))
        assert "motion" in bookdata.chapters_for(tmp_path, view) and bookdata.has_motion(tmp_path)
    (tmp_path / "motion/motion.json").rename(tmp_path / "motion/moved.json")
    assert not bookdata.has_motion(tmp_path)
    (tmp_path / "motion/SPEC.md").write_text("# spec")
    assert bookdata.has_motion(tmp_path)
    assert "motion" not in bookdata.chapters_for(tmp_path, {**view, "tier": "quick"})        # the Quick book has no motion chapter, whatever the files


OLD_MOTION_CHAPTER = """## What moves

Acme sample text for this slot.

## Timing

{{motion}}

Acme sample text for this slot.

## Reduced motion

Acme sample text for this slot.
"""


def test_a_chapter_file_written_from_the_old_template_gets_the_new_block(mp):
    (mp / "book/chapters/motion.md").write_text(OLD_MOTION_CHAPTER)
    write_spec(mp, on_doc())
    write_frames(mp)
    build(mp)
    sec = chapter(html_of(mp), "motion")
    assert "Signature move: Settle." in sec and "<h4>Timeline</h4>" in sec and 'data-motion-demo="demo-page"' in sec and sec.index("<h3>Timing</h3>") < sec.index("<h4>Timeline</h4>")


def test_the_chapter_template_holds_only_the_owners_prose_around_the_block():
    t = (ROOT / "templates/book/motion.md").read_text()
    assert t.count("{{motion}}") == 1 and "## Timing" not in t and "## What moves" not in t
    assert [h for h in re.findall(r"^## (.*)$", t, re.M)] == ["Why it moves", "The motion", "Reduced motion"]
    assert t.count("[[fill:") == 2 and "for assistive technology" in t.split("## Reduced motion")[1]


# ---------------------------------------------------------------- B: the replay

def test_each_frames_json_of_a_gated_proof_becomes_one_replay_with_the_markup_of_the_contract(mp):
    write_spec(mp, on_doc())
    write_frames(mp, n=9)
    build(mp)
    fig = figure(chapter(html_of(mp), "motion"))
    assert re.match(r"<figure[^>]*>", fig).group(0) == f'<figure class="motion-demo" data-motion-demo="demo-page" data-length-ms="{LENGTH}" data-frames="9">'
    assert re.findall(r"<(input|label|div|span|img|p|figcaption)\b", fig) == ["input", "label", "input", "label", "div", "img", "img", "p", "figcaption"]
    assert '<input type="checkbox" id="bc-replay-demo-page"><label for="bc-replay-demo-page">Replay</label>' in fig
    assert '<input type="checkbox" id="bc-slow-demo-page"><label for="bc-slow-demo-page">4× slower</label>' in fig      # the multiplication sign, not an x
    stage = re.search(r'<div class="motion-stage">(.*?)</div>', fig, re.S).group(1)
    imgs = {t.attrs["class"]: t.attrs for t in htmlscan.tags(fig) if t.name == "img"}
    assert list(imgs) == ["motion-flip", "motion-reduced"] and stage.startswith('<picture><source type="image/png" srcset="data:image/png;base64,') and '</picture><img class="motion-reduced"' in stage
    flip, source = imgs["motion-flip"], next(t.attrs for t in htmlscan.tags(fig) if t.name == "source")
    assert source["srcset"].endswith(" 2x") and "srcset" not in flip                     # the strip once, in the <source>: its density is the stills' scale (2x), so one still is its css size
    assert base64.b64decode(source["srcset"][:-3].split(",", 1)[1]) == (mp / FRAMES / "strip.png").read_bytes()      # the file's exact bytes
    # valid HTML: the <img> has the src the standard asks of it, a 1 x 1 transparent PNG that nothing draws while the <source> matches (a second copy of the strip would double the book)
    assert flip["src"] == bookgen.PIXEL and booklint._png_dims(booklint._data_png(flip["src"])) == (1, 1)
    png = booklint._data_png(flip["src"])
    assert png[25] == 6 and zlib.decompress(png[png.index(b"IDAT") + 4:png.index(b"IEND") - 8]) == b"\x00\x00\x00\x00\x00"      # colour type RGBA, one row: filter 0 and a pixel of four zero bytes
    assert [t.name for t in htmlscan.tags(stage)][:4] == ["picture", "source", "img", "picture"]
    assert imgs["motion-reduced"]["src"].startswith("data:image/png;base64,") and base64.b64decode(imgs["motion-reduced"]["src"].split(",", 1)[1]) == (mp / FRAMES / "reduced.png").read_bytes()
    assert flip["alt"] == "Settle: the mark in motion" and imgs["motion-reduced"]["alt"] == "Settle: the still shown when motion is reduced"
    assert (flip["width"], flip["height"], imgs["motion-reduced"]["width"], imgs["motion-reduced"]["height"]) == ("8", "8", "8", "8")      # one still
    times = re.search(r'<p class="cap motion-times">(.*?)</p>', fig).group(1)
    assert times.startswith("Stills at: 0 % (0 ms), 12.5 % (50 ms), 25 % (100 ms)") and times.endswith("100 % (400 ms)")
    assert fig.rstrip().endswith("</figcaption>\n</figure>") and "<figcaption>Settle: 400 ms, 9 stills, 8 × 8 px</figcaption>" in fig
    assert chapter(html_of(mp), "motion").index('<h4>Replay</h4>') < chapter(html_of(mp), "motion").index("<figure")


def test_the_replay_is_the_strip_stepped_through_by_four_identical_keyframes_that_a_checkbox_chooses_between(bp):
    css = css_of(html_of(bp))
    base = rule_body(css, "#bc-replay-demo-page~.motion-stage .motion-flip")
    assert base == f"animation:bc-flip-demo-page-r0s0 {LENGTH}ms step-end 1 both"                   # over data-length-ms, once, left on the last still, each holding until the next
    assert "data:image" not in css and rule_body(css, ".motion-flip") == "display:block;object-fit:none"      # the picture is the <img>'s: the style sheet holds none, and the img shows one still
    assert rule_body(css, "#bc-replay-demo-page:checked~.motion-stage .motion-flip") == "animation-name:bc-flip-demo-page-r1s0"
    assert rule_body(css, "#bc-slow-demo-page:checked~.motion-stage .motion-flip") == f"animation-name:bc-flip-demo-page-r0s1;animation-duration:{4 * LENGTH}ms"      # 4 x data-length-ms
    assert rule_body(css, "#bc-replay-demo-page:checked~#bc-slow-demo-page:checked~.motion-stage .motion-flip") == "animation-name:bc-flip-demo-page-r1s1"
    names = [f"bc-flip-demo-page-{k}" for k in ("r0s0", "r1s0", "r0s1", "r1s1")]
    frames = [keyframes(css, n) for n in names]
    assert frames[0] == frames[1] == frames[2] == frames[3] and len(set(names)) == 4                # four identical keyframes under four names
    # each still at its percent, held until the next: still i is shown from p_i with object-position -i x 8 px (the first at 0)
    assert frames[0] == [(0.0, "0"), (12.5, "-8px"), (25.0, "-16px"), (37.5, "-24px"), (50.0, "-32px"), (62.5, "-40px"), (75.0, "-48px"), (87.5, "-56px"), (100.0, "-64px")]
    clip = rule_body(css, ".motion-demo input")
    assert "clip:rect(0 0 0 0)" in clip and "position:absolute" in clip and "display:none" not in clip and "visibility:hidden" not in clip
    assert not re.search(r"<input[^>]*\bhidden\b", html_of(bp))
    # reduced motion hides the controls and the flipbook (and stops the animation of every name), shows the still; print shows the flipbook whole, with no animation
    assert "@media screen and (prefers-reduced-motion:reduce){.motion-demo input,.motion-demo label{display:none}.motion-flip{display:none}.motion-reduced{display:block}}" in css      # on a screen only
    assert ("@media print{.motion-demo input,.motion-demo label{display:none}.motion-stage{width:auto;overflow:visible}"
            ".motion-flip{animation:none!important;width:100%;max-width:100%;height:auto;object-fit:fill}.motion-times{display:block}}") in css
    assert ("@media (prefers-reduced-motion:reduce){#bc-replay-demo-page~.motion-stage .motion-flip,#bc-replay-demo-page:checked~.motion-stage .motion-flip,"
            "#bc-slow-demo-page:checked~.motion-stage .motion-flip,#bc-replay-demo-page:checked~#bc-slow-demo-page:checked~.motion-stage .motion-flip{animation:none}}") in css
    assert ".motion-demo{" in css and css.index(".motion-demo{") > css.index(".colophon{")      # added after the book's own rules


def test_the_strip_is_embedded_once_for_each_replay_and_each_language_has_its_own_copy(mp):
    """The flipbook is the strip <img> itself and print shows that same image whole: one copy of the strip per replay, where the flipbook's css background and a
    print-only image made two."""
    write_spec(mp, on_doc())
    write_frames(mp)
    build(mp)
    strip64 = base64.b64encode((mp / FRAMES / "strip.png").read_bytes()).decode()
    html = html_of(mp)
    assert html.count(strip64) == 1 and "motion-strip" not in html and "background-image" not in css_of(html).split(".motion-demo{", 1)[1]
    assert bc("state", "--set", "content_languages=pl,en", project=mp).returncode == 0      # two languages: a chapter of each, a replay in each, and one copy of the strip in each
    for f in list((mp / "book/chapters").glob("*.md")):
        shutil.copy(f, f.with_name(f.stem + ".pl.md"))
        f.rename(f.with_name(f.stem + ".en.md"))
    build(mp)
    assert html_of(mp).count(strip64) == 2


def test_a_book_without_a_replay_has_none_of_its_rules_and_one_with_is_rebuilt_to_the_same_bytes(mp, bp):
    build(mp)
    assert "motion-demo" not in html_of(mp) and "bc-flip" not in html_of(mp) and "motion-stage" not in html_of(mp)
    before = (bp / "book.html").read_bytes()
    assert b"@keyframes bc-flip-demo-page-r0s0" in before
    build(bp)
    assert (bp / "book.html").read_bytes() == before and bc("book", "--verify", project=bp).returncode == 0


def test_stills_in_any_order_or_not_from_0_to_100_make_a_flipbook_that_always_has_a_first_and_a_last_keyframe():
    def steps(pcts):
        return bookgen.BookBuild.flipbook_steps({"size": [8, 8], "frames": [{"percent": p} for p in pcts]})
    assert steps([0, 25, 50, 75, 100]) == [("0", "0"), ("25", "-8px"), ("50", "-16px"), ("75", "-24px"), ("100", "-32px")]
    assert steps([100, 0, 50]) == [("0", "-8px"), ("50", "-16px"), ("100", "0")]           # --at 100,0,50: the strip is in the order given, the animation in time
    assert steps([25, 50, 75]) == [("0", "0"), ("25", "0"), ("50", "-8px"), ("75", "-16px"), ("100", "-16px")]      # nothing at 0 or 100: the first and last still stand in
    assert steps([0, 33.33, 66.67, 100])[1:3] == [("33.33", "-8px"), ("66.67", "-16px")]
    assert steps([0, 50, 50, 100]) == [("0", "0"), ("50", "-16px"), ("100", "-24px")]      # two at one percent: the later one is shown
    assert steps([5]) == [("0", "0"), ("5", "0"), ("100", "0")]


def test_stills_that_do_not_run_from_0_to_100_or_share_a_percent_are_built_and_the_build_says_so(mp):
    write_spec(mp, on_doc())
    write_frames(mp, pcts=[25, 50, 75, 90, 95, 96, 97, 98, 99])
    build(mp)
    assert any("run from 25 % to 99 %" in w and "not on the rest frame" in w for w in motion_warnings(mp))
    css = css_of(html_of(mp))
    assert keyframes(css, "bc-flip-demo-page-r0s0")[0] == (0.0, "0") and keyframes(css, "bc-flip-demo-page-r0s0")[-1][0] == 100.0
    write_frames(mp, pcts=[0, 10, 20, 30, 40, 40, 70, 90, 100])
    build(mp)
    assert any("two stills of demo-page are at the same percent" in w for w in motion_warnings(mp))
    assert not [w for w in motion_warnings(mp) if "run from" in w]


def test_the_stills_of_an_exploration_proof_a_gone_proof_or_a_folder_that_cannot_be_read_are_left_out_and_said(mp):
    write_spec(mp, on_doc())
    write_frames(mp)
    (mp / "rounds/r2").mkdir(parents=True, exist_ok=True)
    (mp / "rounds/r2/try.json").write_text('{"schema": 1, "cases": []}\n')
    write_frames(mp, case="try-out", proof="rounds/r2/try.json")
    write_frames(mp, case="old-hero", proof="motion/gone.json")
    (mp / "motion/frames/broken").mkdir()
    (mp / "motion/frames/broken/frames.json").write_text("{not json")
    (mp / "motion/frames/stray").mkdir()
    (mp / "motion/frames/stray/00-0.png").write_bytes(Img(16, 16, "#ff0000").png())     # stills with no frames.json: a run that was cut short
    write_frames(mp, case="Hero Page")
    shutil.move(str(mp / "motion/frames/Hero-Page"), str(mp / "motion/frames/hero"))      # a folder renamed: the files frames.json lists are not in it
    write_frames(mp, case="Menu")
    mutate_json(mp / "motion/frames/Menu/frames.json", lambda d: d.update(case="Side Menu"))      # a case renamed in frames.json, not in its folder
    build(mp)
    assert re.findall(r'data-motion-demo="([^"]*)"', html_of(mp)) == ["demo-page"]
    ws = " | ".join(motion_warnings(mp))
    assert "motion/frames/try-out/ holds the stills of rounds/r2/try.json, an exploration proof" in ws and "its replay is left out" in ws
    assert "motion/frames/old-hero/ holds the stills of motion/gone.json, a proof that no longer exists" in ws
    assert "motion/frames/broken/frames.json cannot be read as JSON" in ws
    assert "motion/frames/stray/ has no frames.json, so its stills cannot be replayed: run `brand-creator frames <proof>` again, or move the folder to removed-<date>/" in ws
    assert "motion/frames/hero/frames.json: it lists motion/frames/Hero-Page/00-0.png, which is not in motion/frames/hero/" in ws
    assert "motion/frames/Menu/ holds the case 'Side Menu', which belongs in motion/frames/Side-Menu/" in ws


def test_a_missing_strip_leaves_the_replay_out_and_two_cases_that_make_one_id_keep_the_first(mp):
    write_spec(mp, on_doc())
    write_frames(mp)
    write_frames(mp, case="a.b")
    write_frames(mp, case="a-b")                                                        # both make the id part a-b
    write_frames(mp, case="no-strip")
    shutil.move(str(mp / "motion/frames/no-strip/strip.png"), str(mp.parent / "strip.moved"))
    build(mp)
    assert re.findall(r'data-motion-demo="([^"]*)"', html_of(mp)) == ["a-b", "demo-page"]      # folders in name order: a-b before a.b, which is left out
    ws = " | ".join(motion_warnings(mp))
    assert "motion/frames/no-strip/strip.png is listed in motion/frames/no-strip/frames.json and does not exist; the replay of no-strip is left out" in ws
    assert "motion/frames/a.b/ makes the same control ids as motion/frames/a-b/ (a-b); its replay is left out: rename one of the cases" in ws
    assert lint(mp)["ids:duplicate"]["status"] == "pass"


def test_a_replay_of_fewer_than_nine_stills_is_built_and_the_build_names_the_command_that_makes_it_smooth(mp):
    write_spec(mp, on_doc())
    write_frames(mp, n=5)
    build(mp)
    assert 'data-frames="5"' in html_of(mp)
    assert any("the replay of demo-page jumps between 5 stills; `brand-creator frames motion/proof.json --count 25` makes it smooth" in w for w in motion_warnings(mp))
    write_frames(mp, n=9)
    build(mp)
    assert not [w for w in motion_warnings(mp) if "jumps between" in w]                  # nine is smooth enough
    write_frames(mp, n=1)
    build(mp)
    assert any("jumps between 1 still;" in w for w in motion_warnings(mp))


def tamper(p: Path, name: str) -> None:
    """A still edited after `frames` wrote it: another picture under the same name."""
    (p / FRAMES / name).write_bytes(Img(16, 16, "#ff0000").png())


def test_a_still_that_is_not_the_one_frames_json_lists_is_a_warning_that_names_the_command(mp):
    write_spec(mp, on_doc())
    write_frames(mp, n=9)
    build(mp)
    assert not [w for w in motion_warnings(mp) if "frames" in w]                         # a current set of stills says nothing
    tamper(mp, "03-37.5.png")
    build(mp)
    assert any("motion/frames/demo-page/: 03-37.5.png is not the file listed; frames.json and the files disagree: run `brand-creator frames motion/proof.json --count 9`" in w
               for w in motion_warnings(mp)), motion_warnings(mp)
    shutil.move(str(mp / FRAMES / "04-50.png"), str(mp.parent / "still.moved"))          # a still that is gone, and three more that are not the ones listed
    for n in ("00-0.png", "01-12.5.png", "02-25.png"):
        tamper(mp, n)
    build(mp)
    assert any("motion/frames/demo-page/: 00-0.png is not the file listed; 01-12.5.png is not the file listed; 02-25.png is not the file listed; 2 more; "
               "frames.json and the files disagree" in w for w in motion_warnings(mp)), motion_warnings(mp)


def test_a_frames_report_that_is_stale_missing_or_failed_is_a_warning_that_names_the_command(mp):
    write_spec(mp, on_doc())
    write_frames(mp, n=9)
    cmd = "run `brand-creator frames motion/proof.json --case demo-page --count 9`"
    # the page changed since the stills were taken: the report is stale
    mutate(mp / "motion/demo.html", "<title>Acme dot, motion demo</title>", "<title>Acme dot, a demo</title>")
    build(mp)
    assert any("the frames report of motion/proof.json is stale (motion/demo.html changed)" in w and cmd in w for w in motion_warnings(mp)), motion_warnings(mp)
    # no report at all
    shutil.move(str(mp / "assets" / "_checks" / f"{frames_report_name('motion/proof.json')}.json"), str(mp.parent / "report.moved"))
    build(mp)
    assert any("no frames report for motion/proof.json" in w and cmd in w and "stale" not in w for w in motion_warnings(mp)), motion_warnings(mp)
    # the last run failed
    write_frames(mp, n=9)
    mutate_json(mp / "assets" / "_checks" / f"{frames_report_name('motion/proof.json')}.json", lambda d: d["results"][0].update(status="fail"))
    build(mp)
    assert any("the last `frames` run for motion/proof.json did not pass for demo-page" in w and cmd in w for w in motion_warnings(mp)), motion_warnings(mp)
    write_frames(mp, n=9)                                                               # a current, passing report: no warning
    build(mp)
    assert not [w for w in motion_warnings(mp) if "frames" in w]


def test_a_motion_json_that_names_a_token_that_is_not_built_stops_the_book_with_exit_2(mp):
    """`brand-creator motion` reads the answer from the document alone, so the finish chain's motion step goes on; the book looks every duration
    and curve up among the built tokens and refuses one that is not there (exit 2), before it writes anything."""
    doc = {**on_doc(), "parts": [{"id": "dot", "description": "The accent dot of the mark."}],
           "timeline": [{"part": "dot", "property": "transform", "start": "0", "duration": "{motion.nowhere}", "easing": "{easing.standard}"}]}
    write_spec(mp, doc)
    r = build(mp, code=2)
    assert "no token named motion.nowhere" in r.stdout + r.stderr, r.stdout + r.stderr
    assert not (mp / "book.html").exists()


def test_a_frames_run_that_fails_keeps_the_stills_of_the_last_run_that_worked_and_the_book_replays_them(mp):
    """The finish chain says so after a failed `frames` ("the book keeps the stills of the last run that worked"), and the tools make it true: a real run that
    worked, then the page loses its motion and a run fails (exit 1, a failing report) over the earlier stills. They are kept byte for byte, and the book replays
    them, with a warning that they may be older than the page."""
    write_spec(mp, on_doc())
    assert bc("frames", "motion/proof.json", "--count", "9", project=mp).returncode == 0
    folder = mp / "motion" / "frames" / "demo-page"
    before = {f.name: f.read_bytes() for f in folder.iterdir()}
    mutate(mp / "motion/demo.html", "animation: press 320ms steps(2, end) 1 both;", "")         # nothing on the page moves any more
    r = bc("frames", "motion/proof.json", "--count", "9", project=mp)
    assert r.returncode == 1 and "no seekable motion" in r.stdout + r.stderr, r.stdout + r.stderr
    assert {f.name: f.read_bytes() for f in folder.iterdir()} == before
    build(mp)
    assert 'data-motion-demo="demo-page"' in (mp / "book.html").read_text()
    assert any("did not pass for demo-page, so its stills may be older than the page" in w for w in motion_warnings(mp)), motion_warnings(mp)


def test_the_frames_command_in_a_warning_writes_the_same_points_again(mp):
    def cmd(pcts):
        return bookdata.frames_command({"proof": "motion/p.json", "frames": [{"percent": x} for x in pcts]})
    assert cmd([0]) == "brand-creator frames motion/p.json --count 1"
    assert cmd([0, 50, 100]) == "brand-creator frames motion/p.json --count 3"
    assert cmd([0, 25, 50, 75, 100]) == "brand-creator frames motion/p.json --count 5"
    assert cmd([0, 16.67, 33.33, 50, 66.67, 83.33, 100]) == "brand-creator frames motion/p.json --count 7"        # 100 / 6 rounded to 2 places
    assert cmd([0, 10, 30, 60, 100]) == "brand-creator frames motion/p.json --at 0,10,30,60,100"
    assert cmd([100, 0, 50]) == "brand-creator frames motion/p.json --at 100,0,50"
    assert cmd([0, 33.33, 100]) == "brand-creator frames motion/p.json --at 0,33.33,100"
    write_spec(mp, on_doc())                                                            # and the warning carries it
    write_frames(mp, pcts=[0, 10, 30, 60, 100])
    tamper(mp, "02-30.png")
    build(mp)
    assert any("02-30.png is not the file listed" in w and "run `brand-creator frames motion/proof.json --at 0,10,30,60,100`" in w for w in motion_warnings(mp)), motion_warnings(mp)


def test_a_motion_that_is_on_with_no_stills_builds_no_demo_and_warns_with_the_frames_command(mp):
    write_spec(mp, on_doc())
    build(mp)
    assert "data-motion-demo" not in html_of(mp) and "motion-demo" not in css_of(html_of(mp))
    assert any("no stills in motion/frames/" in w and "run `brand-creator frames motion/proof.json --count 25`" in w for w in motion_warnings(mp)), motion_warnings(mp)
    shutil.move(str(mp / "motion/proof.json"), str(mp.parent / "proof.moved"))           # no proof at all: frames cannot run yet, and the warning says what it needs
    build(mp)
    assert any("no stills in motion/frames/" in w and "(it needs the motion proof, motion/proof.json)" in w for w in motion_warnings(mp)), motion_warnings(mp)


def test_a_proof_with_no_page_case_says_so_instead_of_asking_for_stills_and_a_proof_that_cannot_be_read_does_not_hide_the_ask(mp):
    write_spec(mp, on_doc())
    (mp / "motion/proof.json").write_text(json.dumps({"schema": 1, "cases": [c for c in json.loads((mp / "motion/proof.json").read_text())["cases"] if c["type"] == "states"]}))
    r = build(mp)
    assert not [w for w in motion_warnings(mp) if "no stills" in w]
    assert any(x["id"] == "book:motion" and x["status"] == "info" and "has no page case" in x["detail"] for x in report(mp, "book")["results"]), r.stdout
    (mp / "motion/proof.json").write_text("{not json")
    build(mp)
    assert any("no stills in motion/frames/" in w for w in motion_warnings(mp)), motion_warnings(mp)


def test_with_two_languages_every_chapter_has_its_own_replay_with_its_own_ids_and_the_lint_passes(mp):
    write_spec(mp, on_doc())
    write_frames(mp)
    assert bc("state", "--set", "content_languages=pl,en", project=mp).returncode == 0
    for f in list((mp / "book/chapters").glob("*.md")):
        shutil.copy(f, f.with_name(f.stem + ".pl.md"))
        f.rename(f.with_name(f.stem + ".en.md"))
    build(mp)
    html = html_of(mp)
    assert re.findall(r'<input type="checkbox" id="([^"]*)"', html) == ["bc-replay-demo-page-pl", "bc-slow-demo-page-pl", "bc-replay-demo-page-en", "bc-slow-demo-page-en"]
    for lang in ("pl", "en"):
        assert f"bc-flip-demo-page-{lang}-r1s1" in css_of(html) and f'for="bc-slow-demo-page-{lang}"' in html
    rows = lint(mp)
    assert all(rows[r]["status"] == "pass" for r in ("ids:duplicate", "lang:parity", "motion:reduced", "motion:replay", "motion:stills", "self:durations")), \
        {k: (v["status"], v["detail"]) for k, v in rows.items() if v["status"] not in ("pass", "info")}


def test_the_labels_of_the_motion_chapter_are_translated_with_the_book_json_labels_and_the_missing_ones_are_reported(mp):
    write_spec(mp, on_doc())
    write_frames(mp)
    assert bc("state", "--set", "content_languages=pl", project=mp).returncode == 0     # one language: the chapter files keep their names
    build(mp)
    assert any("label(s) have no pl translation" in x["detail"] for x in report(mp, "book")["results"] if x["id"] == "book:labels")      # Polish labels are not written yet
    (mp / "book/book.json").write_text(json.dumps({"schema": 1, "labels": {"pl": {"Replay": "Odtw\u00f3rz", "4\u00d7 slower": "4\u00d7 wolniej", "Signature move": "Ruch znaku",
                                                                               "Shown in": "Gdzie wida\u0107", "the mark in motion": "znak w ruchu", "stills": "klatek",
                                                                               "Stills at": "Klatki w", "Timeline": "Przebieg"}}}))
    build(mp)
    sec = chapter(html_of(mp), "motion")
    assert "<strong>Signature move: Settle.</strong>" not in sec and "<strong>Ruch znaku: Settle.</strong>" in sec and "<p>Gdzie wida\u0107:</p>" in sec and "<h4>Przebieg</h4>" in sec
    fig = figure(html_of(mp))
    assert ">Odtw\u00f3rz</label>" in fig and ">4\u00d7 wolniej</label>" in fig and 'alt="Settle: znak w ruchu"' in fig
    assert "Klatki w: 0 % (0 ms)" in fig and "9 klatek" in fig
    assert "Replay" not in fig and "slower" not in fig


def test_read_frames_says_what_is_wrong_with_a_frames_json_and_never_reads_a_file_outside_its_folder(mp):
    write_frames(mp)
    doc, bad = bookdata.read_frames(mp, CASE)
    assert bad == [] and doc["case"] == CASE
    f = mp / FRAMES / "frames.json"
    good = json.loads(f.read_text())
    for what, edit, needle in (("a schema from the future", lambda d: d.update(schema=2), "schema is 2, this version reads 1"),
                               ("no case", lambda d: d.pop("case"), "case is missing"),
                               ("a length of zero", lambda d: d.update(length_ms=0), "length_ms must be a number above 0"),
                               ("no scale", lambda d: d.pop("scale"), "scale must be a number above 0"),
                               ("a size of one number", lambda d: d.update(size=[8]), "size must be [width, height] in css px"),
                               ("no frames", lambda d: d.update(frames=[]), "frames must be a non-empty list"),
                               ("a percent past 100", lambda d: d["frames"][0].update(percent=101), "frames must be a non-empty list"),
                               ("a sha256 that is not one", lambda d: d["strip"].update(sha256="abc"), "strip must be {file, sha256}"),
                               ("a proof outside the project", lambda d: d.update(proof="../outside.json"), "proof must be a path inside the project"),
                               ("an absolute proof", lambda d: d.update(proof="/etc/hosts"), "proof must be a path inside the project"),
                               ("a file out of its folder", lambda d: d["strip"].update(file="motion/frames/other/strip.png"), "it lists motion/frames/other/strip.png, which is not in motion/frames/demo-page/"),
                               ("a file that leaves the project", lambda d: d["reduced"].update(file="motion/frames/demo-page/../../../x.png"), "which is not in motion/frames/demo-page/")):
        doc = json.loads(json.dumps(good))
        edit(doc)
        f.write_text(json.dumps(doc))
        got, bad = bookdata.read_frames(mp, CASE)
        assert got is None and any(needle in b for b in bad), (what, bad)
    f.write_text("[1]")
    assert bookdata.read_frames(mp, CASE) == (None, [f"{FRAMES}/frames.json is not a JSON object"])
    f.write_text("{nope")
    assert "cannot be read as JSON" in bookdata.read_frames(mp, CASE)[1][0]
    shutil.move(str(f), str(mp.parent / "frames.moved"))
    assert "cannot be read as JSON" in bookdata.read_frames(mp, CASE)[1][0] and CASE not in bookdata.frames_folders(mp)


def test_a_case_folder_and_a_report_are_named_as_frames_names_them_and_every_real_replay_lints(mp):
    """The twins in bookdata (case_folder, case_slug, frames_report_tool) against a real run of `frames` on page cases whose names need them."""
    names = ["Hero Page 2!", "..dots", "a/b", "caf\u00e9", "-lead"]
    page = next(c for c in json.loads((mp / "motion/proof.json").read_text())["cases"] if c["type"] == "page")
    (mp / "motion/Hero Proof.json").write_text(json.dumps({"schema": 1, "cases": [{**page, "name": n} for n in names]}))
    r = bc("frames", "motion/Hero Proof.json", "--count", "2", project=mp)
    assert r.returncode == 0, r.stdout + r.stderr
    assert bookdata.frames_folders(mp) == sorted(bookdata.case_folder(n) for n in names) == ["Hero-Page-2-", "a-b", "caf-", "dots", "lead"]
    assert (mp / "assets/_checks" / f"{frames_report_name('motion/Hero Proof.json')}.json").is_file() and bookdata.frames_report_tool("motion/Hero Proof.json") == frames_report_name("motion/Hero Proof.json")
    assert [bookdata.case_slug(n) for n in names] == ["hero-page-2", "dots", "a-b", "caf", "lead"]
    assert [bookdata.case_slug(n) for n in ("A-B", "--x--", "a.b")] == ["a-b", "x", "a-b"]
    for n in names:
        doc, bad = bookdata.read_frames(mp, bookdata.case_folder(n))
        assert bad == [] and doc["case"] == n and doc["proof"] == "motion/Hero Proof.json"
    write_spec(mp, on_doc())
    build(mp)                                                                           # a real run's stills, its report and its names make replays and no warning
    html = html_of(mp)
    assert re.findall(r'data-motion-demo="([^"]*)"', html) == [bookdata.case_folder(n) and n for n in sorted(names, key=bookdata.case_folder)]
    assert 'id="bc-replay-hero-page-2"' in html and 'id="bc-slow-caf"' in html
    assert not [w for w in motion_warnings(mp) if "frames" in w and "jumps" not in w], motion_warnings(mp)
    rows = lint(mp)
    assert all(rows[r]["status"] == "pass" for r in ("motion:reduced", "motion:replay", "motion:stills", "ids:duplicate", "self:durations")), \
        {k: (v["status"], v["detail"]) for k, v in rows.items() if v["status"] not in ("pass", "info")}


# ---------------------------------------------------------------- C: the book-lint rows

def test_the_built_replay_passes_the_three_motion_rows_and_a_book_without_one_gets_info_rows(bp, mp):
    rows = lint(bp)
    for r in ("motion:reduced", "motion:replay", "motion:stills", "self:durations", "marks:lint", "images:alt", "network:refs", "ids:duplicate"):
        assert rows[r]["status"] == "pass", (r, rows[r])
    assert "demo-page" in rows["motion:replay"]["detail"] and "demo-page" in rows["motion:stills"]["detail"] and "1 motion demo(s)" in rows["motion:reduced"]["detail"]
    assert bc("book-lint", project=bp).returncode == 0                              # the plain lint reads the motion rows as well
    build(mp)
    plain = lint(mp)
    for r in ("motion:reduced", "motion:replay", "motion:stills"):
        assert plain[r]["status"] == "info" and plain[r]["detail"].startswith("no motion demo"), (r, plain[r])        # nothing measured is never a pass


def break_book(p: Path, old: str, new: str, row: str, needle: str, count: int = 1) -> dict:
    """Mutate the book, check that the lint fails on `row` and says `needle`, and return the rows."""
    mutate(p / "book.html", old, new, count)
    assert bc("book-lint", "--self-consistency", project=p).returncode == 1
    rows = {x["id"]: x for x in report(p, "book-lint")["results"]}
    assert rows[row]["status"] == "fail" and needle in rows[row]["detail"], (row, rows[row])
    return rows


def test_motion_reduced_fails_a_rule_that_starts_an_animation_that_nothing_switches_off_under_reduced_motion(bp):
    break_book(bp, "</style>", ".x{animation:bc-flip-demo-page-r0s0 150ms}</style>", "motion:reduced", "'.x' starts the animation bc-flip-demo-page-r0s0")
    mutate(bp / "book.html", "</style>", "@media (prefers-reduced-motion:reduce){.other{animation:none}}</style>")
    assert lint(bp)["motion:reduced"]["status"] == "fail"                                               # a switch-off for another selector is none for this one
    mutate(bp / "book.html", "@media (prefers-reduced-motion:reduce){.other{animation:none}}</style>", "@media (prefers-reduced-motion:reduce){.x{animation:none}}</style>")
    assert lint(bp)["motion:reduced"]["status"] == "pass"
    mutate(bp / "book.html", "</style>", ".y{animation-name:bc-flip-demo-page-r0s0}</style>")           # animation-name alone starts one too
    assert lint(bp)["motion:reduced"]["status"] == "fail"
    mutate(bp / "book.html", "</style>", "@media (prefers-reduced-motion:reduce){.y{animation-name:none}}</style>")
    assert lint(bp)["motion:reduced"]["status"] == "pass"
    mutate(bp / "book.html", "</style>", ".z{animation:none}.w{animation-name:none}</style>")           # none starts nothing
    assert lint(bp)["motion:reduced"]["status"] == "pass"


def test_motion_reduced_fails_a_transition_with_a_duration_that_nothing_switches_off_and_lets_one_of_zero_alone(bp):
    break_book(bp, "</style>", "a{transition:color 150ms}</style>", "motion:reduced", "'a' starts a transition")
    mutate(bp / "book.html", "a{transition:color 150ms}", "a{transition:color 0s}")                      # no duration, no transition
    assert lint(bp)["motion:reduced"]["status"] == "pass"
    mutate(bp / "book.html", "a{transition:color 0s}", "a{transition-duration:150ms}")
    assert lint(bp)["motion:reduced"]["status"] == "fail"
    mutate(bp / "book.html", "a{transition-duration:150ms}", "a{transition:color 150ms,opacity 0s}")   # one of two with a duration is one
    assert lint(bp)["motion:reduced"]["status"] == "fail"
    mutate(bp / "book.html", "</style>", "@media (prefers-reduced-motion:reduce){a{transition:none}}</style>")
    assert lint(bp)["motion:reduced"]["status"] == "pass"
    mutate(bp / "book.html", "a{transition:color 150ms,opacity 0s}@media (prefers-reduced-motion:reduce){a{transition:none}}",
           "a{transition:color 150ms}@media (prefers-reduced-motion:reduce){a{transition-property:none}}")
    assert lint(bp)["motion:reduced"]["status"] == "pass"                                               # transition-property: none switches it off as well


def test_motion_reduced_takes_a_star_rule_only_with_important_a_later_rule_only_and_leaves_alone_what_never_applies_under_reduced_motion(bp):
    mutate(bp / "book.html", "</style>", ".x{animation:bc-flip-demo-page-r0s0 150ms}@media (prefers-reduced-motion:reduce){*{animation:none}}</style>")
    rows = lint(bp)                                                 # a * rule is weaker than any class: it only counts with !important
    assert rows["motion:reduced"]["status"] == "fail" and "(or for * with !important)" in rows["motion:reduced"]["detail"]
    mutate(bp / "book.html", "*{animation:none}", "*,*::before{animation:none!important}")
    assert lint(bp)["motion:reduced"]["status"] == "pass"
    mutate(bp / "book.html", ".x{animation:bc-flip-demo-page-r0s0 150ms}@media (prefers-reduced-motion:reduce){*,*::before{animation:none!important}}",
           "@media (prefers-reduced-motion:reduce){.z{animation:none}}.z{animation:bc-flip-demo-page-r0s0 150ms}")
    rows = lint(bp)                                                 # the switch-off comes before the rule it should override: the rule wins
    assert rows["motion:reduced"]["status"] == "fail" and "'.z' starts" in rows["motion:reduced"]["detail"]
    mutate(bp / "book.html", "@media (prefers-reduced-motion:reduce){.z{animation:none}}.z{animation:bc-flip-demo-page-r0s0 150ms}",
           "@media (prefers-reduced-motion:no-preference){.z{animation:bc-flip-demo-page-r0s0 150ms}}")
    assert lint(bp)["motion:reduced"]["status"] == "pass"           # a rule that only applies when motion is welcome needs no switch
    mutate(bp / "book.html", "@media (prefers-reduced-motion:no-preference){.z{animation:bc-flip-demo-page-r0s0 150ms}}",
           "@media (min-width:900px){.z{animation:bc-flip-demo-page-r0s0 150ms}}")
    assert lint(bp)["motion:reduced"]["status"] == "fail"           # a width condition is no reason not to switch it off
    mutate(bp / "book.html", "@media (min-width:900px){.z{animation:bc-flip-demo-page-r0s0 150ms}}", "")
    mutate(bp / "book.html", '<p class="eyebrow">', '<p style="animation:bc-flip-demo-page-r0s0 150ms" class="eyebrow">')
    rows = lint(bp)                                                 # an inline style cannot be switched off by a media query
    assert rows["motion:reduced"]["status"] == "fail" and "<p style> starts the animation" in rows["motion:reduced"]["detail"]


def test_motion_reduced_fails_a_demo_that_still_shows_its_flipbook_or_hides_its_still_or_leaves_its_controls(bp):
    ok = "{display:none}.motion-flip{display:none}.motion-reduced{display:block}}"
    break_book(bp, ok, "{display:none}.motion-flip{display:block}.motion-reduced{display:block}}", "motion:reduced", "demo-page: the flipbook is shown under reduced motion")
    mutate(bp / "book.html", "{display:none}.motion-flip{display:block}.motion-reduced{display:block}}", "{display:none}.motion-flip{display:none}.motion-reduced{display:none}}")
    rows = lint(bp)
    assert rows["motion:reduced"]["status"] == "fail" and "demo-page: the reduced still is not shown under reduced motion" in rows["motion:reduced"]["detail"]
    mutate(bp / "book.html", "{display:none}.motion-flip{display:none}.motion-reduced{display:none}}", ok)
    assert lint(bp)["motion:reduced"]["status"] == "pass"
    break_book(bp, "@media screen and (prefers-reduced-motion:reduce){.motion-demo input,.motion-demo label{display:none}", "@media screen and (prefers-reduced-motion:reduce){.motion-demo input,.motion-demo label{display:inline-block}",
               "motion:reduced", "is shown under reduced motion, where the flipbook it controls is not")
    mutate(bp / "book.html", "@media screen and (prefers-reduced-motion:reduce){.motion-demo input,.motion-demo label{display:inline-block}", "@media screen and (prefers-reduced-motion:reduce){.motion-demo input,.motion-demo label{display:none}")
    assert lint(bp)["motion:reduced"]["status"] == "pass"
    break_book(bp, '<img class="motion-reduced"', '<img class="motion-redux"', "motion:reduced", "demo-page: no reduced still")
    mutate(bp / "book.html", '<img class="motion-redux"', '<img class="motion-reduced"')
    assert lint(bp)["motion:reduced"]["status"] == "pass"


def test_motion_reduced_fails_a_demo_whose_flipbook_keeps_an_animation_under_reduced_motion(bp):
    ok = "#bc-slow-demo-page:checked~.motion-stage .motion-flip,#bc-replay-demo-page:checked~#bc-slow-demo-page:checked~.motion-stage .motion-flip{animation:none}}"
    rows = break_book(bp, ok, "#bc-slow-demo-page:checked~.motion-stage .motion-flip{animation:none}}", "motion:reduced",
                      "'#bc-replay-demo-page:checked~#bc-slow-demo-page:checked~.motion-stage .motion-flip' starts the animation")
    assert "the flipbook still has an animation under reduced motion" in rows["motion:reduced"]["detail"]
    mutate(bp / "book.html", "#bc-slow-demo-page:checked~.motion-stage .motion-flip{animation:none}}", ok)
    assert lint(bp)["motion:reduced"]["status"] == "pass"


def test_motion_replay_fails_a_checkbox_without_an_id_a_label_or_label_text(bp):
    break_book(bp, '<label for="bc-replay-demo-page">Replay</label>', '<label for="bc-replay-demo-page"></label>', "motion:replay", "the label of #bc-replay-demo-page has no visible text")
    mutate(bp / "book.html", '<label for="bc-replay-demo-page"></label>', '<label for="bc-replay-demo-page"><span></span> </label>')
    assert lint(bp)["motion:replay"]["status"] == "fail"
    mutate(bp / "book.html", '<label for="bc-replay-demo-page"><span></span> </label>', '<label for="bc-replay-demo-page">Replay</label>')
    assert lint(bp)["motion:replay"]["status"] == "pass"
    break_book(bp, '<label for="bc-slow-demo-page">', '<label for="somewhere-else">', "motion:replay", '#bc-slow-demo-page has no <label for="bc-slow-demo-page">')
    mutate(bp / "book.html", '<label for="somewhere-else">', '<label for="bc-slow-demo-page">')
    break_book(bp, '<input type="checkbox" id="bc-slow-demo-page">', '<input type="checkbox" id="slow-demo-page">', "motion:replay", "no checkbox whose id starts with bc-slow-")
    mutate(bp / "book.html", '<input type="checkbox" id="slow-demo-page">', '<input type="checkbox">')
    assert lint(bp)["motion:replay"]["status"] == "fail"
    mutate(bp / "book.html", '<input type="checkbox">', '<input type="checkbox" id="bc-slow-demo-page">')
    break_book(bp, '<input type="checkbox" id="bc-replay-demo-page">', '<input type="text" id="bc-replay-demo-page">', "motion:replay", "no checkbox whose id starts with bc-replay-")


def test_motion_replay_fails_a_checkbox_the_keyboard_cannot_reach_outside_the_reduced_motion_and_print_media(bp):
    for old, new, why in (('<input type="checkbox" id="bc-replay-demo-page">', '<input type="checkbox" id="bc-replay-demo-page" hidden>', "it has the hidden attribute"),
                          ('<input type="checkbox" id="bc-slow-demo-page">', '<input type="checkbox" id="bc-slow-demo-page" tabindex="-1">', "it has a negative tabindex"),
                          ('<input type="checkbox" id="bc-slow-demo-page">', '<input type="checkbox" id="bc-slow-demo-page" disabled>', "it has the disabled attribute"),
                          ('<input type="checkbox" id="bc-replay-demo-page">', '<input type="checkbox" id="bc-replay-demo-page" style="display:none">', "its style says display: none"),
                          ('<input type="checkbox" id="bc-slow-demo-page">', '<input type="checkbox" id="bc-slow-demo-page" style="visibility:hidden">', "its style says visibility: hidden")):
        rows = break_book(bp, old, new, "motion:replay", "is out of the keyboard's reach")
        assert why in rows["motion:replay"]["detail"]
        mutate(bp / "book.html", new, old)
        assert lint(bp)["motion:replay"]["status"] == "pass"
    for rule, why in ((".motion-demo input{display:none}", "a rule says display: none"), ("#bc-slow-demo-page{visibility:hidden}", "a rule says visibility: hidden"),
                      ("input[type=checkbox]{display:none}", "a rule says display: none"), ("@media (max-width:600px){.motion-demo input{display:none}}", "a rule says display: none")):
        rows = break_book(bp, "</style>", rule + "</style>", "motion:replay", "out of the keyboard's reach")
        assert why in rows["motion:replay"]["detail"]
        mutate(bp / "book.html", rule + "</style>", "</style>")
    # in the reduced-motion and print media the controls are not there on purpose
    mutate(bp / "book.html", "</style>", "@media print{input{display:none}}@media (prefers-reduced-motion:reduce){input{visibility:hidden}}</style>")
    assert lint(bp)["motion:replay"]["status"] == "pass"


def test_motion_replay_fails_when_a_checkbox_does_not_start_the_flipbook_again_or_the_slow_one_is_not_four_times_as_long(bp):
    break_book(bp, "#bc-replay-demo-page:checked~.motion-stage .motion-flip{animation-name:bc-flip-demo-page-r1s0}",
               "#bc-replay-demo-page:checked~.motion-stage .motion-flip{animation-name:bc-flip-demo-page-r0s0}", "motion:replay",
               "checking the replay box does not change the flipbook's animation-name (still bc-flip-demo-page-r0s0), so the replay would not start again")
    mutate(bp / "book.html", "#bc-replay-demo-page:checked~.motion-stage .motion-flip{animation-name:bc-flip-demo-page-r0s0}",
           "#bc-replay-demo-page:checked~.motion-stage .motion-flip{animation-name:bc-flip-demo-page-r1s0}")
    assert lint(bp)["motion:replay"]["status"] == "pass"
    break_book(bp, f"#bc-slow-demo-page:checked~.motion-stage .motion-flip{{animation-name:bc-flip-demo-page-r0s1;animation-duration:{4 * LENGTH}ms}}",
               "#bc-slow-demo-page:checked~.motion-stage .motion-flip{animation-name:bc-flip-demo-page-r0s1}", "motion:replay",
               f"the flipbook runs for {LENGTH} ms (replay unchecked, slow checked), not {4 * LENGTH} ms (4 x data-length-ms)")
    mutate(bp / "book.html", "animation-name:bc-flip-demo-page-r0s1}", "animation-name:bc-flip-demo-page-r0s1;animation-duration:2000ms}")
    assert lint(bp)["motion:replay"]["status"] == "fail"
    mutate(bp / "book.html", "animation-name:bc-flip-demo-page-r0s1;animation-duration:2000ms}", f"animation-name:bc-flip-demo-page-r0s1;animation-duration:{4 * LENGTH}ms}}")
    assert lint(bp)["motion:replay"]["status"] == "pass"
    break_book(bp, "#bc-replay-demo-page:checked~#bc-slow-demo-page:checked~.motion-stage .motion-flip{animation-name:bc-flip-demo-page-r1s1}",
               "#bc-replay-demo-page:checked~#bc-slow-demo-page:checked~.motion-stage .motion-flip{animation-name:bc-flip-demo-page-r0s1}", "motion:replay",
               "checking the replay box with the slow box checked does not change the flipbook's animation-name (still bc-flip-demo-page-r0s1)")
    mutate(bp / "book.html", "#bc-replay-demo-page:checked~#bc-slow-demo-page:checked~.motion-stage .motion-flip{animation-name:bc-flip-demo-page-r0s1}",
           "#bc-replay-demo-page:checked~#bc-slow-demo-page:checked~.motion-stage .motion-flip{animation-name:bc-flip-demo-page-r1s1}")
    assert lint(bp)["motion:replay"]["status"] == "pass"
    break_book(bp, f"animation:bc-flip-demo-page-r0s0 {LENGTH}ms step-end 1 both", "animation:bc-flip-demo-page-r0s0 step-end 1 both", "motion:replay",
               f"the flipbook runs for 0 ms (replay unchecked, slow unchecked), not {LENGTH} ms (data-length-ms)")
    mutate(bp / "book.html", "animation:bc-flip-demo-page-r0s0 step-end 1 both", f"animation:bc-flip-demo-page-r0s0 {LENGTH}ms step-end 1 both")
    rows = break_book(bp, f"animation:bc-flip-demo-page-r0s0 {LENGTH}ms step-end 1 both", "animation:none", "motion:replay", "the flipbook has no animation (replay unchecked, slow unchecked)")
    assert rows["motion:replay"]["status"] == "fail"


def test_motion_replay_fails_keyframes_that_are_missing_differ_or_a_flipbook_that_repeats_forever(bp):
    break_book(bp, "@keyframes bc-flip-demo-page-r1s0{", "@keyframes bc-flip-demo-page-zzz{", "motion:replay", "there is no @keyframes bc-flip-demo-page-r1s0")
    mutate(bp / "book.html", "@keyframes bc-flip-demo-page-zzz{", "@keyframes bc-flip-demo-page-r1s0{")
    assert lint(bp)["motion:replay"]["status"] == "pass"
    break_book(bp, "@keyframes bc-flip-demo-page-r1s1{0%{object-position:0 0}", "@keyframes bc-flip-demo-page-r1s1{0%{object-position:-8px 0}", "motion:replay",
               "the @keyframes of bc-flip-demo-page-r0s0, bc-flip-demo-page-r0s1, bc-flip-demo-page-r1s0, bc-flip-demo-page-r1s1 are not the same")
    mutate(bp / "book.html", "@keyframes bc-flip-demo-page-r1s1{0%{object-position:-8px 0}", "@keyframes bc-flip-demo-page-r1s1{0%{object-position:0 0}")
    assert lint(bp)["motion:replay"]["status"] == "pass"
    break_book(bp, f"{LENGTH}ms step-end 1 both", f"{LENGTH}ms step-end infinite both", "motion:replay", "the flipbook repeats forever")
    mutate(bp / "book.html", f"{LENGTH}ms step-end infinite both", f"{LENGTH}ms step-end 1 both")
    assert lint(bp)["motion:replay"]["status"] == "pass"


def test_motion_replay_fails_a_demo_with_no_flipbook_and_one_whose_rules_do_not_reach_it(bp):
    break_book(bp, '<img class="motion-flip"', '<img class="motion-flap"', "motion:replay", "no flipbook (an element with the class motion-flip)")
    mutate(bp / "book.html", '<img class="motion-flap"', '<img class="motion-flip"')
    assert lint(bp)["motion:replay"]["status"] == "pass"
    # the checkboxes after the stage cannot reach it with ~: toggling them would change nothing
    fig = figure(html_of(bp))
    first = '<input type="checkbox" id="bc-replay-demo-page"><label for="bc-replay-demo-page">Replay</label>\n'
    moved = fig.replace(first, "", 1).replace("</figure>", first + "</figure>")
    mutate(bp / "book.html", fig, moved)
    rows = lint(bp)
    assert rows["motion:replay"]["status"] == "fail" and "demo-page: the flipbook has no animation (replay unchecked, slow unchecked)" in rows["motion:replay"]["detail"]


def test_motion_stills_fails_a_picture_that_is_not_the_file_in_motion_frames_a_length_or_count_that_differs_and_a_size_that_does_not_fit(bp):
    html = html_of(bp)
    strip = re.search(r'<source type="image/png" srcset="([^"]*) 2x">', html).group(1)
    reduced = re.search(r'<img class="motion-reduced" src="([^"]*)"', html).group(1)
    rows = break_book(bp, f'srcset="{strip} 2x"', f'srcset="{reduced} 2x"', "motion:stills", "the flipbook picture is not motion/frames/demo-page/strip.png")
    assert OLDER in rows["motion:stills"]["detail"]
    mutate(bp / "book.html", f'srcset="{reduced} 2x"', f'srcset="{strip} 2x"')
    break_book(bp, f'<img class="motion-reduced" src="{reduced}"', f'<img class="motion-reduced" src="{strip}"', "motion:stills", "the reduced picture is not motion/frames/demo-page/reduced.png")
    mutate(bp / "book.html", f'<img class="motion-reduced" src="{strip}"', f'<img class="motion-reduced" src="{reduced}"')
    assert lint(bp)["motion:stills"]["status"] == "pass"
    break_book(bp, f' srcset="{strip} 2x"', "", "motion:stills", "the flipbook picture is not motion/frames/demo-page/strip.png")      # no strip in the <source>: the 1 x 1 stand-in is what the <img> shows
    mutate(bp / "book.html", '<source type="image/png">', f'<source type="image/png" srcset="{strip} 2x">')
    assert lint(bp)["motion:stills"]["status"] == "pass"
    pic = f'<picture><source type="image/png" srcset="{strip} 2x"><img class="motion-flip" src="{bookgen.PIXEL}"'
    break_book(bp, pic, '<picture><img class="motion-flip"', "motion:stills", 'no flipbook picture in the demo (an <img class="motion-flip"> in a <picture> whose <source> has a srcset that is a data: URI)')
    mutate(bp / "book.html", '<picture><img class="motion-flip"', f'<picture><img class="motion-flip" src="{bookgen.PIXEL}" srcset="{strip} 2x"')      # a hand-written book may have the strip on the <img> itself
    assert lint(bp)["motion:stills"]["status"] == "pass"
    mutate(bp / "book.html", f'<picture><img class="motion-flip" src="{bookgen.PIXEL}" srcset="{strip} 2x"', pic)
    assert lint(bp)["motion:stills"]["status"] == "pass"
    break_book(bp, f'<img class="motion-reduced" src="{reduced}"', '<img class="motion-reduced" src="data:image/png;base64,@@@@"', "motion:stills", "the reduced picture is not a base64 data:image/png URI")
    mutate(bp / "book.html", '<img class="motion-reduced" src="data:image/png;base64,@@@@"', f'<img class="motion-reduced" src="{reduced}"')
    rows = break_book(bp, f'data-length-ms="{LENGTH}"', f'data-length-ms="{LENGTH + 1}"', "motion:stills", f"data-length-ms is {LENGTH + 1}, frames.json says {LENGTH}")
    assert OLDER in rows["motion:stills"]["detail"]
    mutate(bp / "book.html", f'data-length-ms="{LENGTH + 1}"', f'data-length-ms="{LENGTH}"')
    break_book(bp, 'data-frames="9"', 'data-frames="8"', "motion:stills", "data-frames is 8, frames.json lists 9")
    mutate(bp / "book.html", 'data-frames="8"', 'data-frames="9"')
    break_book(bp, f'data-length-ms="{LENGTH}"', 'data-length-ms="x"', "motion:stills", "data-length-ms is not a number")
    break_book(bp, 'data-length-ms="x"', 'data-length-ms="0"', "motion:replay", "data-length-ms is not a number above 0")
    mutate(bp / "book.html", 'data-length-ms="0"', f'data-length-ms="{LENGTH}"')
    assert lint(bp)["motion:stills"]["status"] == "pass"
    # the flipbook shows one still of the strip at a time: the strip's density is the stills' scale, the img is one still wide and high, and object-fit is none
    break_book(bp, f'srcset="{strip} 2x"', f'srcset="{strip}"', "motion:stills", "the flipbook picture is drawn at 1x, frames.json says the stills are 2x, so one still would not fill 8 x 8 px: the srcset of its <source> needs the descriptor 2x")
    mutate(bp / "book.html", f'srcset="{strip}"', f'srcset="{strip} 2x"')
    break_book(bp, 'alt="Settle: the mark in motion" width="8"', 'alt="Settle: the mark in motion" width="9"', "motion:stills", "the flipbook is 9 x 8 px, one still of frames.json is 8 x 8 px")
    mutate(bp / "book.html", 'alt="Settle: the mark in motion" width="9"', 'alt="Settle: the mark in motion" width="8"')
    break_book(bp, ".motion-flip{display:block;object-fit:none}", ".motion-flip{display:block;object-fit:fill}", "motion:stills", "the flipbook's object-fit is fill")
    mutate(bp / "book.html", ".motion-flip{display:block;object-fit:fill}", ".motion-flip{display:block;object-fit:none}")
    assert lint(bp)["motion:stills"]["status"] == "pass"


def test_motion_stills_fails_a_book_built_before_the_stills_were_taken_again_and_passes_once_it_is_rebuilt(bp):
    assert lint(bp)["motion:stills"]["status"] == "pass"
    write_frames(bp, shade=1)                                                       # `frames` ran again: the same names, other pictures
    rows = lint(bp)
    assert rows["motion:stills"]["status"] == "fail" and OLDER in rows["motion:stills"]["detail"]
    build(bp)
    assert lint(bp)["motion:stills"]["status"] == "pass"
    write_frames(bp, n=11, shade=1)                                                 # more stills: the count differs
    rows = lint(bp)
    assert rows["motion:stills"]["status"] == "fail" and f"data-frames is 9, frames.json lists 11 ({OLDER})" in rows["motion:stills"]["detail"]
    write_frames(bp, n=9, shade=1, length_ms=500)                                   # the page got slower
    rows = lint(bp)
    assert rows["motion:stills"]["status"] == "fail" and f"data-length-ms is {LENGTH}, frames.json says 500" in rows["motion:stills"]["detail"]
    write_frames(bp, n=9)                                                           # the book as it was built, and the stills as they were (the book is rebuilt below)
    build(bp)
    shutil.move(str(bp / FRAMES / "strip.png"), str(bp / "strip.moved"))            # a file that frames.json lists and that is gone
    rows = lint(bp)
    assert rows["motion:stills"]["status"] == "fail" and f"motion/frames/demo-page/strip.png is gone ({OLDER})" in rows["motion:stills"]["detail"]
    shutil.move(str(bp / "strip.moved"), str(bp / FRAMES / "strip.png"))
    shutil.move(str(bp / FRAMES / "frames.json"), str(bp / "frames.json.moved"))
    rows = lint(bp)
    assert rows["motion:stills"]["status"] == "fail" and "motion/frames/demo-page/frames.json cannot be read" in rows["motion:stills"]["detail"]
    shutil.move(str(bp / "frames.json.moved"), str(bp / FRAMES / "frames.json"))
    mutate_json(bp / FRAMES / "frames.json", lambda d: d.update(case="other"))
    assert "is for the case 'other'" in lint(bp)["motion:stills"]["detail"]


def test_motion_stills_fails_a_picture_whose_sha256_is_not_the_one_frames_json_lists_and_the_build_refuses_it(bp):
    doc = json.loads((bp / FRAMES / "frames.json").read_text())
    before = (bp / "book.html").read_bytes()
    (bp / FRAMES / "strip.png").write_bytes(Img(100, 16, "#123456").png())          # edited after frames.json was written: not the listed sha256, and not 9 stills wide
    r = build(bp, 1)                                                                # the book would embed the edited file: it does not lint clean, so it is not written
    assert "run brand-creator frames, then brand-creator book" in r.stdout and (bp / "book.html").read_bytes() == before
    assert doc["strip"]["sha256"] != sha((bp / FRAMES / "strip.png").read_bytes())
    # a book that embeds the edited file (written by hand): the picture is the file on disk, and not the one frames.json lists
    edited = "data:image/png;base64," + base64.b64encode((bp / FRAMES / "strip.png").read_bytes()).decode()
    old = re.search(r'<source type="image/png" srcset="([^"]*) 2x">', html_of(bp)).group(1)
    rows = break_book(bp, f'srcset="{old} 2x"', f'srcset="{edited} 2x"', "motion:stills",
                      "the flipbook picture is motion/frames/demo-page/strip.png, which is not the file frames.json lists (its sha256 differs): run brand-creator frames, then brand-creator book")
    assert "the flipbook picture is 100x16 px, frames.json says 9 still(s) of 8 x 8 px at 2x: run brand-creator frames again" in rows["motion:stills"]["detail"]      # a size that does not fit stays a warning
    assert bc("book-lint", "--self-consistency", project=bp).returncode == 1        # and it fails the book


def test_the_reports_list_the_spec_and_the_stills_as_inputs_so_check_notices_new_ones(bp):
    assert lint(bp)["motion:stills"]["status"] == "pass"
    inputs = {i["path"] for i in report(bp, "book-lint")["inputs"]}
    assert {f"{FRAMES}/frames.json", f"{FRAMES}/strip.png", f"{FRAMES}/reduced.png"} <= inputs
    built = {i["path"] for i in report(bp, "book")["inputs"]}                             # the book's own report names the spec, the stills and the report of the run that took them
    assert {SPEC, f"{FRAMES}/frames.json", f"{FRAMES}/strip.png", f"{FRAMES}/reduced.png", f"assets/_checks/{frames_report_name('motion/proof.json')}.json"} <= built
    bc("check", project=bp)
    assert {x["id"]: x["status"] for x in report(bp, "check")["results"]}["report:book-lint"] == "pass"
    write_frames(bp, shade=2)                                                       # the stills are new, the book and its reports are not
    bc("check", project=bp)
    rows = {x["id"]: x for x in report(bp, "check")["results"]}
    assert rows["report:book-lint"]["status"] == "skipped" and "changed" in rows["report:book-lint"]["detail"], rows["report:book-lint"]
    assert rows["report:book"]["status"] == "skipped"


def test_check_gates_the_frames_report_of_each_gated_proof_passing_failing_or_stale_and_only_lists_an_exploration_or_gone_proofs(bp):
    tool = frames_report_name("motion/proof.json")
    rf = bp / "assets" / "_checks" / f"{tool}.json"

    def checked(which: str = tool) -> dict:
        bc("check", project=bp)
        return {x["id"]: x for x in report(bp, "check")["results"]}[f"report:{which}"]
    row = checked()
    assert row["status"] == "pass" and row["detail"] == f"{tool} report is current and passing"
    mutate_json(rf, lambda d: d.update(status="fail", results=[{**d["results"][0], "status": "fail"}]))        # the last run of `frames` failed
    row = checked()
    assert row["status"] == "fail" and f"{tool} report is failing (frames:demo-page)" in row["detail"]
    write_frames(bp)                                                                    # a current, passing report again
    assert checked()["status"] == "pass"
    # the page changed since the stills were taken: not verified, and the way out is the run the report records, then the book that replays its stills
    mutate(bp / "motion/demo.html", "<title>Acme dot, motion demo</title>", "<title>Acme dot, a demo</title>")
    row = checked()
    assert row["status"] == "skipped" and row["detail"] == (f"not verified: {tool} report is stale (motion/demo.html changed); "
                                                            "re-run `brand-creator frames motion/proof.json --count 9` and then `brand-creator book`")
    write_frames(bp, pcts=[0, 10, 30, 60, 100])                                         # a run with points that are not evenly spread
    mutate(bp / "motion/demo.html", "<title>Acme dot, a demo</title>", "<title>Acme dot, a demo again</title>")
    assert checked()["detail"].endswith("re-run `brand-creator frames motion/proof.json --at 0,10,30,60,100` and then `brand-creator book`")
    mutate_json(rf, lambda d: d.pop("points_pct"))                                      # a report that does not record its points: the usual number
    assert checked()["detail"].endswith("re-run `brand-creator frames motion/proof.json --count 25` and then `brand-creator book`")
    rf.write_text("{not json")                                                          # a report that cannot be read fails, as any report does
    row = checked()
    assert row["status"] == "fail" and f"assets/_checks/{tool}.json is not valid JSON; re-run `brand-creator frames <proof.json> --count 25` and then `brand-creator book`" in row["detail"]
    # a try-out's report is listed and never gated, and one whose proof is gone is a warning that says where it goes
    (bp / "rounds/r2").mkdir(parents=True, exist_ok=True)
    (bp / "rounds/r2/try.json").write_text('{"schema": 1, "cases": []}\n')
    write_frames(bp, case="try-out", proof="rounds/r2/try.json")
    write_frames(bp, case="old-hero", proof="motion/gone.json")
    tryout, gone = frames_report_name("rounds/r2/try.json"), frames_report_name("motion/gone.json")
    row = checked(tryout)
    assert row["status"] == "info" and "exploration proof, not gated: rounds/r2/try.json is under rounds/" in row["detail"]
    row = checked(gone)
    assert row["status"] == "warn" and f"the proof motion/gone.json no longer exists, so assets/_checks/{gone}.json gates nothing; move it to removed-<date>/" in row["detail"]


def test_check_does_not_take_a_frames_report_for_the_stills_of_a_case_it_did_not_take(bp):
    tool = frames_report_name("motion/proof.json")

    def checked() -> dict:
        bc("check", project=bp)
        return {x["id"]: x for x in report(bp, "check")["results"]}[f"report:{tool}"]
    write_frames(bp, case="second")                                                     # a second page case of the proof ...
    write_frames(bp, vouch=[CASE, "second"])                                            # ... and one run that took both: its report vouches for both
    assert checked()["status"] == "pass"
    write_frames(bp, case="second")                                                     # `frames --case second` ran after the page changed: the report covers that case alone
    row = checked()
    assert row["status"] == "skipped" and row["detail"] == (
        "not verified: the frames report of motion/proof.json does not vouch for the stills of demo-page in motion/frames/ (its last run took second); "
        "re-run `brand-creator frames motion/proof.json --count 9` and then `brand-creator book`")      # the run that takes every case, then the book that replays them
    write_frames(bp, vouch=[CASE, "second"])
    assert checked()["status"] == "pass"
    mutate_json(rf := bp / "assets" / "_checks" / f"{tool}.json", lambda d: d["results"][0].update(status="info"))      # a row that is not a pass vouches for nothing either
    row = checked()
    assert row["status"] == "skipped" and "does not vouch for the stills of demo-page in motion/frames/ (its last run took demo-page, second)" in row["detail"]
    write_frames(bp, vouch=[CASE, "second"])
    # a case the proof no longer has as a page case is not asked for (the build leaves its stills out and says to move them), nor are the stills of another proof
    mutate_json(bp / "motion/proof.json", lambda d: d.update(cases=[c for c in d["cases"] if c["name"] != "second"]))
    write_frames(bp)
    assert checked()["status"] == "pass", rf.read_text()
    (bp / "rounds/r2").mkdir(parents=True, exist_ok=True)
    (bp / "rounds/r2/try.json").write_text('{"schema": 1, "cases": []}\n')
    write_frames(bp, case="try-out", proof="rounds/r2/try.json")
    assert checked()["status"] == "pass"


def test_a_hand_authored_book_with_a_replay_is_read_by_the_same_rows(bp):
    assert bc("state", "--set", "mark_source=authored-vector", project=bp).returncode == 0
    assert bc("book", project=bp).returncode == 2                                       # the generator refuses: the book is the author's
    rows = lint(bp)
    assert all(rows[r]["status"] == "pass" for r in ("motion:reduced", "motion:replay", "motion:stills", "self:durations")), {k: v["detail"] for k, v in rows.items() if v["status"] == "fail"}
    break_book(bp, f'data-length-ms="{LENGTH}"', f'data-length-ms="{LENGTH + 1}"', "motion:stills", "data-length-ms")
    mutate(bp / "book.html", f'data-length-ms="{LENGTH + 1}"', f'data-length-ms="{LENGTH}"')
    assert lint(bp)["motion:stills"]["status"] == "pass"


def test_self_durations_lets_a_replay_use_its_own_length_and_four_times_it_and_nothing_else_may(bp):
    assert lint(bp)["self:durations"]["status"] == "pass"                           # 400ms and 1600ms are not tokens, but they are this replay's
    rows = break_book(bp, "</style>", f"a{{transition:color {LENGTH}ms}}@media (prefers-reduced-motion:reduce){{a{{transition:none}}}}</style>", "self:durations", f"transition: {LENGTH}ms in a")
    assert "is not a duration token" in rows["self:durations"]["detail"]
    mutate(bp / "book.html", f"a{{transition:color {LENGTH}ms}}", "a{transition:color 150ms}")
    assert lint(bp)["self:durations"]["status"] == "pass"                           # a token is fine anywhere
    rows = break_book(bp, f"animation:bc-flip-demo-page-r0s0 {LENGTH}ms step-end 1 both", "animation:bc-flip-demo-page-r0s0 500ms step-end 1 both", "self:durations",
                      "animation: 500ms in #bc-replay-demo-page~")
    assert rows["motion:replay"]["status"] == "fail"
    mutate(bp / "book.html", "animation:bc-flip-demo-page-r0s0 500ms step-end 1 both", f"animation:bc-flip-demo-page-r0s0 {LENGTH}ms step-end 1 both")
    assert lint(bp)["self:durations"]["status"] == "pass"
    break_book(bp, "</style>", f".motion-flip,a{{animation-delay:{LENGTH}ms}}</style>", "self:durations", f"animation-delay: {LENGTH}ms in .motion-flip,a")      # a rule that reaches more than the replay
    mutate(bp / "book.html", f".motion-flip,a{{animation-delay:{LENGTH}ms}}", f"#bc-slow-demo-page:checked~.motion-stage .motion-flip{{animation-delay:{4 * LENGTH}ms}}")
    assert lint(bp)["self:durations"]["status"] == "pass"                           # four times the length is the replay's as well, in any of its rules


def test_a_replay_needs_a_passing_row_for_its_case_in_the_current_frames_report_and_a_case_that_is_still_in_the_proof(mp):
    write_spec(mp, on_doc())
    write_frames(mp, case="second")                                                     # a second page case of the proof
    write_frames(mp, vouch=[CASE, "second"])                                            # one run took both: its report vouches for both
    build(mp)
    assert not [w for w in motion_warnings(mp) if "frames" in w and "jumps" not in w], motion_warnings(mp)
    write_frames(mp, case="second")                                                     # `frames --case second` ran after it: the report is rewritten and covers it alone
    build(mp)
    ws = " | ".join(motion_warnings(mp))
    assert "the frames report of motion/proof.json does not cover demo-page (its last run took second): the stills of demo-page are not known to be current; " in ws
    # a proof of several page cases is run whole: `--case demo-page` would un-vouch second, and following the advice case by case never settles
    assert "run `brand-creator frames motion/proof.json --count 9` (all 2 page cases of motion/proof.json: the report vouches only for the cases of its last run)" in ws
    assert "--case" not in ws
    assert "does not cover second" not in ws and re.findall(r'data-motion-demo="([^"]*)"', html_of(mp)) == ["demo-page", "second"]      # the demo is built, and said to be unvouched
    # a case the proof no longer has as a page case (removed, or made a states case): its stills are left out, and the warning says what to move
    write_frames(mp, vouch=[CASE, "second"])
    for edit in (lambda cs: [c for c in cs if c["name"] != "second"], lambda cs: [{**c, "type": "states"} if c["name"] == "second" else c for c in cs]):
        mutate_json(mp / "motion/proof.json", lambda d: d.update(cases=edit(d["cases"])))
        build(mp)
        assert re.findall(r'data-motion-demo="([^"]*)"', html_of(mp)) == ["demo-page"]
        assert "second is no longer a page case of motion/proof.json: move motion/frames/second/ to removed-<date>/" in " | ".join(motion_warnings(mp))
        write_frames(mp, case="second", vouch=[CASE, "second"])                         # back in the proof
    build(mp)
    assert re.findall(r'data-motion-demo="([^"]*)"', html_of(mp)) == ["demo-page", "second"]


def test_motion_reduced_does_not_take_a_plain_none_for_a_start_marked_important(bp):
    reduce = "@media (prefers-reduced-motion:reduce){%s}"
    rows = break_book(bp, "</style>", ".x{animation:bc-flip-demo-page-r0s0 150ms!important}" + reduce % ".x{animation:none}" + "</style>", "motion:reduced",
                      "'.x' starts the animation bc-flip-demo-page-r0s0 with !important and no later rule in @media (prefers-reduced-motion: reduce) sets animation: none !important for it")
    assert "(or for * with !important)" not in rows["motion:reduced"]["detail"]
    mutate(bp / "book.html", "{.x{animation:none}}", "{.x{animation:none!important}}")
    assert lint(bp)["motion:reduced"]["status"] == "pass"                               # an important stop for an important start
    mutate(bp / "book.html", "{.x{animation:none!important}}", "{*{animation:none!important}}")
    assert lint(bp)["motion:reduced"]["status"] == "fail"                               # a * with !important loses to a class with !important
    mutate(bp / "book.html", "!important}" + reduce % "*{animation:none!important}", "}" + reduce % "*{animation:none!important}")
    assert lint(bp)["motion:reduced"]["status"] == "pass"                               # the start is not important any more: the * wins, as before
    mutate(bp / "book.html", "</style>", ".y{transition:color 150ms!important}" + reduce % ".y{transition:none}" + "</style>")
    rows = lint(bp)
    assert rows["motion:reduced"]["status"] == "fail" and "'.y' starts a transition with !important" in rows["motion:reduced"]["detail"]
    mutate(bp / "book.html", "{.y{transition:none}}", "{.y{transition:none!important}}")
    assert lint(bp)["motion:reduced"]["status"] == "pass"
    mutate(bp / "book.html", ".y{transition:color 150ms!important}" + reduce % ".y{transition:none!important}", "")
    # importance is weighed per longhand: a stop counts when it wins on the longhand that stops the transition (property none, or a duration of 0), whatever the other says
    def case(start: str, stop: str, status: str) -> None:
        mutate(bp / "book.html", "</style>", start + reduce % stop + "</style>")
        assert lint(bp)["motion:reduced"]["status"] == status, (start, stop)
        mutate(bp / "book.html", start + reduce % stop + "</style>", "</style>")
    case(".y{transition-duration:150ms!important;transition-property:color}", ".y{transition:none}", "pass")      # the property is none (both normal, the later wins): no transition runs
    case(".y{transition-property:color!important;transition-duration:150ms}", ".y{transition:none}", "pass")      # the duration is 0 (both normal): none runs
    case(".y{transition-property:color!important;transition-duration:150ms!important}", ".y{transition:none}", "fail")      # a plain none wins on neither
    case(".y{transition-property:color!important;transition-duration:150ms!important}", ".y{transition-duration:0s}", "fail")
    case(".y{transition-property:color!important;transition-duration:150ms!important}", ".y{transition-property:none!important}", "pass")      # an important one wins on its own
    case(".y{transition-property:color!important;transition-duration:150ms!important}", ".y{transition-duration:0s!important}", "pass")
    case(".y{transition-duration:150ms!important}", ".y{transition-property:none}", "pass")      # the start sets no property: nothing to win against
    case(".y{transition-duration:150ms!important;transition-property:color}", "*{transition:none}", "fail")      # a * rule is weaker than a class, so it needs !important
    case(".y{transition-duration:150ms!important;transition-property:color}", "*{transition-property:none!important}", "pass")      # on the property, where the start is not important
    mutate(bp / "book.html", "</style>", ".y{transition-duration:150ms!important;transition-property:color!important}" + reduce % ".y{transition:none}" + "</style>")
    assert "'.y' starts a transition with !important and no later rule" in lint(bp)["motion:reduced"]["detail"]      # the words are for a start that is important on a longhand


def test_a_book_built_before_the_stills_exist_fails_motion_stills_once_they_appear_and_check_notices_them(mp):
    write_spec(mp, on_doc())
    page_case(mp, "later")                                                              # a second page case, with no stills yet
    build(mp)                                                                           # motion on and no stills: the book has no replay, and the build says so
    assert "data-motion-demo" not in html_of(mp) and lint(mp)["motion:stills"]["status"] == "info"
    bc("check", project=mp)
    ids = {x["id"]: x["status"] for x in report(mp, "check")["results"]}
    assert ids["report:book-lint"] == "pass" and ids["report:book"] == "pass" and "report:book-lint:frames" not in ids
    for tool in ("book", "book-lint"):                                                  # reports of a version from before the key, and no stills now: nothing in them to be stale
        f = mp / "assets/_checks" / f"{tool}.json"
        doc = json.loads(f.read_text())
        f.write_text(json.dumps({k: v for k, v in doc.items() if k != "frames_view_sha"}, indent=2) + "\n")
    bc("check", project=mp)
    assert not [x for x in report(mp, "check")["results"] if x["id"].endswith(":frames")]
    build(mp)
    write_frames(mp)                                                                    # `frames` ran afterwards: stills of a case the book shows nothing of
    bc("check", project=mp)
    ids = {x["id"]: x for x in report(mp, "check")["results"]}
    assert ids["report:book-lint:frames"]["status"] == "skipped" and ids["report:book:frames"]["status"] == "skipped"
    assert "stills of a gated proof appeared, went or changed since the book-lint report; re-run `brand-creator book-lint --self-consistency`" in ids["report:book-lint:frames"]["detail"]
    rows = lint(mp)
    assert rows["motion:stills"]["status"] == "fail"
    assert "demo-page: its stills are in motion/frames/demo-page/ and the book has no replay of them: run brand-creator book (the Motion chapter shows the replay through its {{motion}} line)" in rows["motion:stills"]["detail"]
    assert bc("book-lint", "--self-consistency", project=mp).returncode == 1
    build(mp)                                                                           # what the lint asks for
    assert lint(mp)["motion:stills"]["status"] == "pass" and 'data-motion-demo="demo-page"' in html_of(mp)
    bc("check", project=mp)
    ids = {x["id"]: x["status"] for x in report(mp, "check")["results"]}
    assert ids["report:book-lint"] == "pass" and "report:book-lint:frames" not in ids and "report:book:frames" not in ids
    write_frames(mp, case="later")                                                      # one more case of the proof: stills that appeared after this book was built
    bc("check", project=mp)
    assert {x["id"]: x["status"] for x in report(mp, "check")["results"]}["report:book-lint:frames"] == "skipped"


def test_stills_the_build_left_out_and_said_so_and_those_of_a_motion_that_is_off_are_no_failure_of_the_book(mp):
    write_spec(mp, on_doc())
    write_frames(mp)
    write_frames(mp, case="no-strip")
    shutil.move(str(mp / "motion/frames/no-strip/strip.png"), str(mp.parent / "strip.moved"))      # a strip that is gone: the build leaves the case out, and says so
    write_frames(mp, case="rounds-over", proof="motion/proof.json")
    mutate_json(mp / "motion/proof.json", lambda d: d.update(cases=[c for c in d["cases"] if c["name"] != "rounds-over"]))      # a case the proof no longer has
    write_frames(mp, case="a.b")
    write_frames(mp, case="a-b", vouch=["a.b", "a-b"])                                  # two cases that make one id: the second folder is left out
    build(mp)
    assert re.findall(r'data-motion-demo="([^"]*)"', html_of(mp)) == ["a-b", "demo-page"]
    ws = " | ".join(motion_warnings(mp))
    assert "no-strip" in ws and "rounds-over is no longer a page case" in ws and "makes the same control ids" in ws
    rows = lint(mp)
    assert rows["motion:stills"]["status"] in ("pass", "warn") and "no-strip" not in rows["motion:stills"]["detail"] and "rounds-over" not in rows["motion:stills"]["detail"]
    assert bc("book-lint", "--self-consistency", project=mp).returncode == 0           # the book is what the build made of them: nothing is missing from it
    write_spec(mp, off_doc())                                                           # nothing moves: stills are not shown, and the book is not asked for them
    build(mp)
    assert lint(mp)["motion:stills"]["status"] == "info"
    write_spec(mp, on_doc())
    shutil.move(str(mp / "motion/frames/demo-page"), str(mp.parent / "demo.moved"))
    build(mp)
    write_frames(mp)                                                                    # stills appeared for a book that is hand-written: it is told, and `book` cannot help
    assert bc("state", "--set", "mark_source=authored-vector", project=mp).returncode == 0
    rows = lint(mp)
    assert rows["motion:stills"]["status"] == "warn" and "this book is hand-written: add the replay with `brand-creator patch`" in rows["motion:stills"]["detail"]


def test_a_quick_book_has_no_motion_chapter_and_is_not_asked_for_a_replay(mp):
    write_spec(mp, on_doc())
    write_frames(mp)
    assert bc("state", "--set", "tier=quick", project=mp).returncode == 0
    for f in (mp / "book/chapters").glob("*.md"):
        if f.stem not in bookdata.chapters_for(mp, bookdata.state_view(mp)):
            f.rename(mp.parent / f.name)
    build(mp)
    assert "motion" not in [t.attrs["data-chapter"] for t in htmlscan.tags(html_of(mp)) if t.name == "section" and "data-chapter" in t.attrs]
    assert lint(mp)["motion:stills"]["status"] == "info"


def test_the_list_of_stills_carries_the_strip_and_the_reduced_still_so_that_a_picture_that_goes_and_comes_back_is_seen_by_check(bp):
    view = bookdata.state_view(bp)
    entry = bookdata.frames_view(bp, view)[0]
    assert entry["path"] == f"{FRAMES}/frames.json" and entry["sha256"] == sha((bp / FRAMES / "frames.json").read_bytes())
    assert entry["strip"] == sha((bp / FRAMES / "strip.png").read_bytes()) and entry["reduced"] == sha((bp / FRAMES / "reduced.png").read_bytes())
    before = bookdata.frames_view_sha(bp, view)
    for pic in ("strip", "reduced"):
        moved = bp.parent / f"{pic}.moved"
        shutil.move(str(bp / FRAMES / f"{pic}.png"), str(moved))                         # a picture that is gone (frames.json still lists it) ...
        assert bookdata.frames_view(bp, view)[0][pic] == "absent" and bookdata.frames_view_sha(bp, view) != before
        build(bp)                                                                       # ... a book built without it (the build leaves the replay out and says so) ...
        assert "data-motion-demo" not in html_of(bp) and any(f"{pic}.png is listed in {FRAMES}/frames.json and does not exist" in w for w in motion_warnings(bp))
        bc("check", project=bp)
        assert not [x for x in report(bp, "check")["results"] if x["id"].endswith(":frames")]       # the book is what the stills were when it was built
        shutil.move(str(moved), str(bp / FRAMES / f"{pic}.png"))                         # ... and the picture comes back, byte for byte
        assert bookdata.frames_view_sha(bp, view) == before
        bc("check", project=bp)
        ids = {x["id"]: x["status"] for x in report(bp, "check")["results"]}
        assert ids["report:book-lint:frames"] == ids["report:book:frames"] == "skipped", (pic, ids)  # a replay could be shown now: not verified until the book is rebuilt
        build(bp)
        assert 'data-motion-demo="demo-page"' in html_of(bp)
        bc("check", project=bp)
        assert not [x for x in report(bp, "check")["results"] if x["id"].endswith(":frames")]
    (bp / FRAMES / "frames.json").write_text("{not json")                               # a frames.json that cannot be read lists no pictures: they are looked for by their usual names
    now = bookdata.frames_view(bp, view)[0]
    assert now["strip"] == entry["strip"] and now["reduced"] == entry["reduced"] and now["sha256"] != entry["sha256"]


@pytest.mark.parametrize("how", ["a Quick book", "motion off"])
def test_stills_are_no_input_of_a_book_that_shows_none_and_taking_them_does_not_make_its_reports_not_verified(mp, how):
    write_spec(mp, on_doc() if how == "a Quick book" else off_doc())
    if how == "a Quick book":                                                           # no Motion chapter at all
        assert bc("state", "--set", "tier=quick", project=mp).returncode == 0
        for f in (mp / "book/chapters").glob("*.md"):
            if f.stem not in bookdata.chapters_for(mp, bookdata.state_view(mp)):
                f.rename(mp.parent / f.name)
    view = bookdata.state_view(mp)
    assert not bookdata.shows_stills(mp, view)
    build(mp)
    empty = bookdata.frames_view_sha(mp, view)
    ids = lambda: {x["id"]: x["status"] for x in report(mp, "check")["results"]}      # noqa: E731
    bc("check", project=mp)
    assert ids()["report:book"] == ids()["report:book-lint"] == "pass"
    write_frames(mp)                                                                    # `frames` ran afterwards: stills of a gated proof, which this book does not show
    bc("check", project=mp)
    rows = ids()
    assert rows["report:book"] == rows["report:book-lint"] == "pass" and not [k for k in rows if k.endswith(":frames")], rows
    assert bookdata.frames_view(mp, view) == [] and bookdata.frames_inputs(mp, view) == [] and bookdata.frames_view_sha(mp, view) == empty
    bc("book-lint", "--self-consistency", project=mp)                                   # a lint run made with the stills there records none of them either
    for tool in ("book", "book-lint"):
        rep = report(mp, tool)
        assert rep["frames_view_sha"] == empty and not [i["path"] for i in rep["inputs"] if i["path"].startswith(FRAMES) or i["path"] == "motion/proof.json"], tool
    if how == "motion off":                                                             # the Standard book has its Motion chapter, and it says nothing moves
        assert "Nothing moves" in chapter(html_of(mp), "motion")
    assert not [p for p in booklint.lint_inputs(mp, mp / "book.html", view) if "motion/frames" in p.as_posix()]       # book-pdf records the same inputs


def test_motion_replay_walks_the_ancestors_of_the_boxes_and_the_labels_and_wants_the_labels_and_the_flipbook_shown_on_a_screen(bp):
    for old, new, needles in (
            ('<figure class="motion-demo"', '<figure hidden class="motion-demo"', ("#bc-replay-demo-page is out of the keyboard's reach: its ancestor <figure> has the hidden attribute",
                                                                                  "the label of #bc-replay-demo-page is not shown on a screen: its ancestor <figure> has the hidden attribute",
                                                                                  "#bc-slow-demo-page is out of the keyboard's reach: its ancestor <figure> has the hidden attribute",
                                                                                  "the label of #bc-slow-demo-page is not shown on a screen: its ancestor <figure> has the hidden attribute")),
            ('<figure class="motion-demo"', '<figure inert class="motion-demo"', ("#bc-slow-demo-page is out of the keyboard's reach: its ancestor <figure> has the inert attribute",)),
            ('<div class="motion-stage">', '<div class="motion-stage" style="display:none">', ("the flipbook is not shown on a screen: its style says display: none (on its ancestor <div>)",)),
            ('<div class="motion-stage">', '<div class="motion-stage" style="opacity:0">', ("the flipbook is not shown on a screen: its style says opacity: 0 (on its ancestor <div>)",)),
            ('<figure class="motion-demo"', '<figure style="visibility:hidden" class="motion-demo"', ("#bc-replay-demo-page is out of the keyboard's reach: its style says visibility: hidden (on its ancestor <figure>)",))):
        rows = break_book(bp, old, new, "motion:replay", needles[0])
        for n in needles[1:]:
            assert n in rows["motion:replay"]["detail"], (n, rows["motion:replay"]["detail"])
        mutate(bp / "book.html", new, old)
        assert lint(bp)["motion:replay"]["status"] == "pass"
    for rule, needle in ((".motion-demo label{display:none}", "the label of #bc-replay-demo-page is not shown on a screen: a rule says display: none"),
                         (".motion-demo label{opacity:0}", "the label of #bc-replay-demo-page is not shown on a screen: a rule says opacity: 0"),
                         (".motion-stage{display:none}", "the flipbook is not shown on a screen: a rule says display: none (on its ancestor <div>)"),
                         (".motion-flip{visibility:hidden}", "the flipbook is not shown on a screen: a rule says visibility: hidden"),
                         ("#bc-slow-demo-page:checked~.motion-stage{display:none}", "the flipbook is not shown on a screen: a rule says display: none (on its ancestor <div>)")):
        break_book(bp, "</style>", rule + "</style>", "motion:replay", needle)
        mutate(bp / "book.html", rule + "</style>", "</style>")
    # a child that says visibility: visible shows itself in a hidden parent; the media of reduced motion and print are not the book on a screen
    mutate(bp / "book.html", "</style>", ".motion-demo{visibility:hidden}.motion-demo input,.motion-demo label,.motion-stage{visibility:visible}"
           "@media print{.motion-stage{display:none}}@media (prefers-reduced-motion:reduce){.motion-demo{visibility:hidden}}</style>")
    assert lint(bp)["motion:replay"]["status"] == "pass"


def test_a_selector_the_lint_cannot_read_is_named_in_the_rows_that_read_what_it_sets_and_the_row_is_a_warning_not_a_pass(bp):
    rows = lint(bp)
    assert all(rows[r]["status"] == "pass" and "not read" not in rows[r]["detail"] for r in ("motion:reduced", "motion:replay", "motion:stills"))      # the book's own rules are all read
    for rule, sets, who in ((".motion-flip:not(.zz){display:none}", "display", ("motion:reduced", "motion:replay")),
                            (".motion-flip:is(img){animation:none}", "animation", ("motion:reduced", "motion:replay")),
                            (".motion-demo :where(label){visibility:hidden}", "visibility", ("motion:reduced", "motion:replay")),
                            (".motion-stage:has(img){opacity:0}", "opacity", ("motion:reduced", "motion:replay")),
                            (".motion-flip:hover{transition:none}", "transition", ("motion:reduced", "motion:replay")),
                            (".motion-stage :is(.motion-flip){object-fit:fill}", "object-fit", ("motion:stills",)),           # what motion:stills reads: the fit and the size of the flipbook, its limits too
                            (".motion-stage :is(.motion-flip){object-position:0 0}", "object-position", ("motion:replay",)),      # and motion:replay reads its position: the keyframes move it
                            (".motion-flip:where(img){width:9px}", "width", ("motion:stills",)),
                            (".motion-flip:where(img){height:9px}", "height", ("motion:stills",)),
                            (".motion-flip:where(img){max-width:9px}", "max-width", ("motion:stills",)),
                            (".motion-flip:where(img){min-height:9px}", "min-height", ("motion:stills",)),
                            ('.motion-flip[data-x="a" i]{opacity:0}', "opacity", ("motion:reduced", "motion:replay"))):          # the last one cannot be parsed at all
        mutate(bp / "book.html", "</style>", rule + "</style>")
        rows = lint(bp)
        sel = rule.split("{")[0]
        for r in ("motion:reduced", "motion:replay", "motion:stills"):
            if r in who:
                assert rows[r]["status"] == "warn" and f"not read: {sel} (sets {sets})" in rows[r]["detail"], (rule, r, rows[r])
            else:
                assert rows[r]["status"] == "pass" and "not read" not in rows[r]["detail"], (rule, r, rows[r])
        mutate(bp / "book.html", rule + "</style>", "</style>")
    for rule in (".motion-flip:not(.zz){margin:0}", ".zzz:not(.y){display:none}", "@media print{.motion-flip:not(.zz){display:none}}", ".other-thing:has(img){animation:none}",
                 ".motion-flip:where(img){background:var(--bg)}"):      # the flipbook is no background any more: no row reads one
        mutate(bp / "book.html", "</style>", rule + "</style>")        # sets nothing a row reads, or reaches nothing of a demo, or is for print only
        rows = lint(bp)
        assert all(rows[r]["status"] == "pass" and "not read" not in rows[r]["detail"] for r in ("motion:reduced", "motion:replay", "motion:stills")), rule
        mutate(bp / "book.html", rule + "</style>", "</style>")
    mutate(bp / "book.html", "</style>", ".motion-flip:not(.zz){display:none}</style>")
    rows = break_book(bp, "{animation:none}}", "{animation:none}}.motion-flip{animation:foo 150ms}", "motion:reduced", "'.motion-flip' starts the animation foo")        # a failing row keeps failing, and still says what it did not read
    assert "not read: .motion-flip:not(.zz) (sets display)" in rows["motion:reduced"]["detail"]


def test_a_motion_that_is_on_with_only_stills_that_cannot_be_shown_still_warns_with_the_frames_command(mp):
    write_spec(mp, on_doc())
    (mp / "rounds/r2").mkdir(parents=True, exist_ok=True)
    (mp / "rounds/r2/try.json").write_text('{"schema": 1, "cases": []}\n')
    write_frames(mp, case="try-out", proof="rounds/r2/try.json")                        # only a try-out's stills are in motion/frames/
    build(mp)
    assert "data-motion-demo" not in html_of(mp)
    ws = motion_warnings(mp)
    assert any("holds the stills of rounds/r2/try.json, an exploration proof" in w for w in ws), ws
    assert any("none of the stills in motion/frames/ can be shown (see above), so the motion chapter has no replay: run `brand-creator frames motion/proof.json --count 25`" in w for w in ws), ws
    assert not [w for w in ws if w.startswith("no stills in")]                          # the folder is not empty: the warning says what is true
    write_frames(mp)                                                                    # a replay is built: no summary
    build(mp)
    assert not [w for w in motion_warnings(mp) if "no replay" in w]
    write_spec(mp, off_doc())                                                           # nothing moves: no replay is wanted
    build(mp)
    assert not [w for w in motion_warnings(mp) if "no replay" in w]


def test_the_text_of_a_replay_is_named_after_the_signature_move_or_the_mark_in_motion_and_never_after_the_case(mp):
    write_spec(mp, on_doc())
    write_frames(mp, case="hero-v2")                                                    # a working name for a proof: it trips the round and the scratch words if it is printed
    write_frames(mp, case="draft-x", vouch=["hero-v2", "draft-x"])
    put_report(mp, "motion/proof.json", [("motion:dot-press:1x:file=rest", "pass"), ("motion:demo-page:control", "pass"), ("motion:hero-v2:cls:normal", "pass"),
                                         ("motion:hero-v2:edges:360", "warn"), ("motion:draft-x:control", "fail"), ("motion:draft-x:settled", "pass")])      # and `shot --motion` ran: its rows hold the case names
    r = build(mp)                                                                       # the book is written: no word rule fails
    html = html_of(mp)
    assert rows_pass(lint(mp), "words:round", "words:scratch") and "NOT written" not in r.stdout + r.stderr
    proof = table_after(chapter(html, "motion"), "Motion proof")                        # the checks, grouped by case, under the replay's name or the case's number: never the case
    assert proof == [["Case 1", "1x:file=rest", "pass"], ["Case 2", "control", "pass"], ["Settle (2)", "cls:normal", "pass"], ["Settle (2)", "edges:360", "warn"],
                     ["Settle (1)", "control", "fail"], ["Settle (1)", "settled", "pass"]]      # dot-press and demo-page have no replay here; draft-x is the first replay, hero-v2 the second
    assert not [w for w in motion_warnings(mp) if "belong to none" in w]
    for i, case in enumerate(("draft-x", "hero-v2"), 1):                                # folders in name order: draft-x first
        fig = figure(html, case)
        assert f'data-motion-demo="{case}"' in fig and f'id="bc-replay-{case}"' in fig and f'for="bc-slow-{case}"' in fig and f"bc-flip-{case}-r1s1" in css_of(html)     # the id stays in the ids and names
        assert f'alt="Settle ({i}): the mark in motion"' in fig and f'alt="Settle ({i}): the still shown when motion is reduced"' in fig
        assert f"<figcaption>Settle ({i}): 400 ms, 9 stills, 8 × 8 px</figcaption>" in fig
        shown = htmlscan.visible_text(fig)
        assert "hero-v2" not in shown and "draft-x" not in shown
    # one replay: no number. No motion.json: "The mark in motion", and the flipbook's alt is not the phrase twice
    (mp / SPEC).rename(mp.parent / "spec.moved")
    write_frames(mp, case="hero-v2")
    shutil.move(str(mp / "motion/frames/draft-x"), str(mp.parent / "draft.moved"))
    build(mp)
    fig = figure(html_of(mp), "hero-v2")
    assert 'alt="The mark in motion"' in fig and 'alt="The mark in motion: the still shown when motion is reduced"' in fig and "<figcaption>The mark in motion: 400 ms, 9 stills" in fig
    assert "hero-v2" not in htmlscan.visible_text(fig)
    assert [r[0] for r in table_after(chapter(html_of(mp), "motion"), "Motion proof")] == ["Case 1", "Case 2", "The mark in motion", "The mark in motion", "Case 4", "Case 4"]      # the same names in the proof table


def test_a_motion_report_row_that_belongs_to_none_of_its_cases_is_shown_by_its_label_and_said_in_a_warning_never_by_its_id(mp):
    write_spec(mp, on_doc())
    put_report(mp, "motion/proof.json", [("motion:demo-page:control", "pass"), ("motion:hero-v2:cls:normal", "fail")])      # hero-v2 is no case of this proof
    build(mp)
    sec = chapter(html_of(mp), "motion")
    assert table_after(sec, "Motion proof") == [["Case 2", "control", "pass"], ["Case 3", "x", "fail"]]            # by its label (the helper writes "x"), under a case of its own
    assert "hero-v2" not in htmlscan.visible_text(sec)
    assert any("has 1 row(s) that belong to none of its cases (dot-press, demo-page), such as motion:hero-v2:cls:normal" in w and "run `brand-creator shot --motion motion/proof.json` again" in w
               for w in motion_warnings(mp)), motion_warnings(mp)
    mutate_json(mp / "assets/_checks" / f"{motion_report_tool('motion/proof.json')}.json", lambda d: d.pop("cases"))      # a report that lists no case: every row is one of them
    build(mp)
    assert [r[0] for r in table_after(chapter(html_of(mp), "motion"), "Motion proof")] == ["Case 1", "Case 1"]
    assert any("has 2 row(s) that belong to none of its cases (it lists none)" in w for w in motion_warnings(mp)), motion_warnings(mp)


def test_a_proof_file_a_report_or_a_state_with_a_working_name_never_reaches_the_text_of_the_book_only_its_data_attributes(mp):
    write_spec(mp, on_doc())
    (mp / "motion/hero-v2.json").write_text(json.dumps({"schema": 1, "cases": [{"name": "icon", "type": "states", "file": "assets/logo/mark-animated.svg", "static": "assets/logo/mark.svg",
                                                                                 "rest": "rest", "controls": [["rest", "draft-v2"]]}]}))       # a proof file with a working name, and a state called draft-v2
    put_report(mp, "motion/hero-v2.json", [("motion:icon:1x:file=rest", "pass"), ("motion:icon:1x:rest=static", "pass"), ("motion:icon:1x:draft-v2=expected", "pass"),
                                           ("motion:icon:1x:control:rest!=draft-v2", "pass"), ("motion:icon:2x:control:rest!=draft-v2", "pass"), ("motion:icon:2x:state:old-v1", "fail")])
    (mp / "motion/draft-x.json").write_text(json.dumps({"schema": 1, "cases": [{"name": "dot", "type": "page", "page": "motion/demo.html", "selector": "#mark"}]}))     # another, a page case
    put_report(mp, "motion/draft-x.json", [("motion:dot:control", "pass")])
    put_report(mp, "motion/old-v1.json", [("motion:legacy:1x:control:rest!=old-state", "pass"), ("motion:legacy:1x:old-state=expected", "pass")])
    mutate_json(mp / "assets/_checks" / f"{motion_report_tool('motion/old-v1.json')}.json", lambda d: (d.pop("cases"), d["results"][1].update(label="state old-state equals its reference drawing")))      # no case listed: rows by label
    r = build(mp)                                                                       # the book is written: no word rule fails
    html = html_of(mp)
    rows = lint(mp)
    assert "NOT written" not in r.stdout + r.stderr and not [k for k, v in rows.items() if v["status"] == "fail"], {k: v["detail"] for k, v in rows.items() if v["status"] == "fail"}
    shown = htmlscan.visible_text(html)                                                 # all the text a reader (or a word rule) gets, the alt and title attributes too
    reports = [motion_report_tool(x) for x in ("motion/hero-v2.json", "motion/draft-x.json", "motion/old-v1.json")]
    for name in ("hero-v2", "draft-x", "old-v1", "draft-v2", "old-state", *reports):
        assert name not in shown, (name, shown[max(0, shown.index(name) - 60):shown.index(name) + 60])
    sec = chapter(html, "motion")
    # the proofs are numbered in the order of their paths, which are in an attribute
    assert re.findall(r'<h4 data-proof="([^"]*)">(Motion proof \d)</h4>', sec) == [("motion/draft-x.json", "Motion proof 1"), ("motion/hero-v2.json", "Motion proof 2"), ("motion/old-v1.json", "Motion proof 3")]
    assert table_after(sec, "Motion proof 1") == [["Case 1", "control", "pass"]]
    # a state is shown by its place in the case (the control pairs name them first, rest first), the same at 1x and 2x; the check as it is stays in the row's attribute
    assert table_after(sec, "Motion proof 2") == [["Case 1", "1x:file=rest", "pass"], ["Case 1", "1x:rest=static", "pass"], ["Case 1", "1x:state 2=expected", "pass"], ["Case 1", "1x:control:state 1!=state 2", "pass"],
                                                  ["Case 1", "2x:control:state 1!=state 2", "pass"], ["Case 1", "2x:state:state 3", "fail"]]
    assert 'data-check="1x:draft-v2=expected"' in sec and 'data-check="2x:control:rest!=draft-v2"' in sec and 'data-check="2x:state:old-v1"' in sec and 'data-check="1x:file=rest"' not in sec
    assert table_after(sec, "Motion proof 3") == [["Case 1", "x", "pass"], ["Case 1", "state 2 equals its reference drawing", "pass"]]      # a row of no case is its label, with the state by its place
    # the report table names the same proofs; the reports' names are attributes
    found = re.findall(r'<tr data-report="(motion/[^"]*)" data-proof="([^"]*)"><td data-l="Report">([^<]*)</td>', chapter(html, "proof"))
    assert sorted(found) == sorted([(reports[1], "motion/draft-x.json", "Motion proof 1"), (reports[0], "motion/hero-v2.json", "Motion proof 2"), (reports[2], "motion/old-v1.json", "Motion proof 3")])


def rows_pass(rows: dict, *ids: str) -> bool:
    return all(rows[i]["status"] == "pass" for i in ids)


def test_self_durations_gives_the_replay_length_only_to_a_rule_that_reaches_one_demo_and_nothing_else(bp, mp):
    assert lint(bp)["self:durations"]["status"] == "pass"
    rows = break_book(bp, "</style>", f"img{{animation-delay:{LENGTH}ms}}</style>", "self:durations", f"animation-delay: {LENGTH}ms in img")             # touches the demo's images and every other image of the book
    assert "is not a duration token" in rows["self:durations"]["detail"]
    mutate(bp / "book.html", f"img{{animation-delay:{LENGTH}ms}}", f".motion-flip{{animation-delay:{LENGTH}ms}}")
    assert lint(bp)["self:durations"]["status"] == "pass"                               # a selector for this demo's flipbook alone: its length is its own
    mutate(bp / "book.html", f".motion-flip{{animation-delay:{LENGTH}ms}}", f".zzz{{animation-delay:{LENGTH}ms}}")
    assert lint(bp)["self:durations"]["status"] == "fail"                               # a selector that matches nothing keeps the token-only rule
    mutate(bp / "book.html", f".zzz{{animation-delay:{LENGTH}ms}}", f"figure{{animation-delay:{LENGTH}ms}}")
    assert lint(bp)["self:durations"]["status"] == "fail"                               # the figure of the demo, and every other figure
    # two demos of one length: a selector for the flipbook of each reaches both
    write_spec(mp, on_doc())
    write_frames(mp, case="second")
    write_frames(mp, vouch=[CASE, "second"])
    build(mp)
    assert lint(mp)["self:durations"]["status"] == "pass"
    break_book(mp, "</style>", f".motion-flip{{animation-delay:{LENGTH}ms}}</style>", "self:durations", f"animation-delay: {LENGTH}ms in .motion-flip")
    mutate(mp / "book.html", f".motion-flip{{animation-delay:{LENGTH}ms}}", f"#bc-slow-second:checked~.motion-stage .motion-flip{{animation-delay:{4 * LENGTH}ms}}")
    assert lint(mp)["self:durations"]["status"] == "pass"                               # an id of one demo reaches that demo's flipbook only


def test_a_keyframes_with_no_name_is_said_in_motion_replay_and_does_not_crash_the_lint(bp):
    rows = break_book(bp, "</style>", "@keyframes{0%{opacity:0}100%{opacity:1}}</style>", "motion:replay", "a @keyframes with no name")
    r = bc("book-lint", "--self-consistency", project=bp)
    assert "Traceback" not in r.stderr and "IndexError" not in r.stderr and rows["motion:replay"]["status"] == "fail"
    mutate(bp / "book.html", "@keyframes{0%{opacity:0}100%{opacity:1}}", "@keyframes   {0%{opacity:0}}")
    assert "a @keyframes with no name" in lint(bp)["motion:replay"]["detail"]


def test_the_stills_of_an_exploration_proof_are_no_input_of_the_book_or_of_book_lint_and_do_not_change_the_list_of_stills(bp):
    (bp / "rounds/r2").mkdir(parents=True, exist_ok=True)
    (bp / "rounds/r2/try.json").write_text('{"schema": 1, "cases": []}\n')
    view = bookdata.state_view(bp)
    before = bookdata.frames_view_sha(bp, view)
    write_frames(bp, case="try-out", proof="rounds/r2/try.json")
    write_frames(bp, case="old-hero", proof="motion/gone.json")                         # a proof that is gone is not shown either
    write_frames(bp, vouch=[CASE])
    build(bp)
    assert bookdata.frames_view_sha(bp, view) == before
    for tool in ("book", "book-lint"):
        inputs = {i["path"] for i in report(bp, tool)["inputs"]}
        assert not [i for i in inputs if "motion/frames/try-out/" in i or "motion/frames/old-hero/" in i or i == "rounds/r2/try.json"], (tool, sorted(inputs))
        assert {f"{FRAMES}/frames.json", f"{FRAMES}/strip.png", f"{FRAMES}/reduced.png", "motion/proof.json", SPEC} <= inputs, (tool, sorted(inputs))
        assert report(bp, tool)["frames_view_sha"] == before
    bc("check", project=bp)
    assert "report:book-lint:frames" not in {x["id"]: x["status"] for x in report(bp, "check")["results"]}      # new try-out stills: nothing to re-run


def test_motion_replay_reads_the_timing_function_the_iteration_count_and_the_keyframes_against_frames_json(bp):
    once = f"{LENGTH}ms step-end 1 both"
    break_book(bp, once, f"{LENGTH}ms step-end 3 both", "motion:replay", "the flipbook plays 3 times (replay unchecked, slow unchecked); it plays once")
    mutate(bp / "book.html", f"{LENGTH}ms step-end 3 both", f"{LENGTH}ms step-end 1.5 both")
    assert "plays 1.5 times" in lint(bp)["motion:replay"]["detail"]
    mutate(bp / "book.html", f"{LENGTH}ms step-end 1.5 both", once)
    assert lint(bp)["motion:replay"]["status"] == "pass"
    break_book(bp, once, f"{LENGTH}ms linear 1 both", "motion:replay", "the flipbook's timing function is linear (replay unchecked, slow unchecked), not step-end: each still must hold until the next")
    mutate(bp / "book.html", f"{LENGTH}ms linear 1 both", f"{LENGTH}ms 1 both")
    assert "the flipbook's timing function is ease (replay unchecked, slow unchecked), not step-end" in lint(bp)["motion:replay"]["detail"]      # a shorthand without one sets ease
    cur = f"{LENGTH}ms 1 both"
    for ok in ("steps(1, end)", "steps(1,jump-end)", "steps(1)"):                       # the same step, written the other ways
        mutate(bp / "book.html", cur, f"{LENGTH}ms {ok} 1 both")
        cur = f"{LENGTH}ms {ok} 1 both"
        assert lint(bp)["motion:replay"]["status"] == "pass", ok
    mutate(bp / "book.html", cur, once)
    # a longhand after the shorthand counts as much as the shorthand
    break_book(bp, "</style>", "#bc-replay-demo-page~.motion-stage .motion-flip{animation-timing-function:ease-in}</style>", "motion:replay", "the flipbook's timing function is ease-in (replay unchecked, slow unchecked)")
    mutate(bp / "book.html", "#bc-replay-demo-page~.motion-stage .motion-flip{animation-timing-function:ease-in}</style>", "</style>")
    assert lint(bp)["motion:replay"]["status"] == "pass"
    # the keyframes are the stills of frames.json: a percent that moved, a position that is wrong, one that is missing or extra, and a property that changes how a step is held
    kf = lambda x: f"object-position:{x} 0"      # noqa: E731
    rows = break_book(bp, f"12.5%{{{kf('-8px')}}}", f"13%{{{kf('-8px')}}}", "motion:replay", "do not step through the stills of frames.json: no keyframe at 12.5 %, where frames.json has a still", count=4)
    assert rows["motion:replay"]["detail"].count("do not step through") == 1                     # the four names are the same: said once
    mutate(bp / "book.html", f"13%{{{kf('-8px')}}}", f"12.5%{{{kf('-8px')}}}", 4)
    break_book(bp, f"12.5%{{{kf('-8px')}}}", f"12.5%{{{kf('-9px')}}}", "motion:replay", f"at 12.5 % it has `{kf('-9px')}`, frames.json gives `{kf('-8px')}`", count=4)
    mutate(bp / "book.html", f"12.5%{{{kf('-9px')}}}", f"12.5%{{{kf('-8px')}}}", 4)
    break_book(bp, f"12.5%{{{kf('-8px')}}}", f"12.5%{{{kf('-8px')}}}13%{{{kf('-8px')}}}", "motion:replay", "a keyframe at 13 % has no still in frames.json", count=4)
    mutate(bp / "book.html", f"12.5%{{{kf('-8px')}}}13%{{{kf('-8px')}}}", f"12.5%{{{kf('-8px')}}}", 4)
    break_book(bp, f"0%{{{kf('0')}}}", f"0%{{{kf('0')};animation-timing-function:linear}}", "motion:replay", "at 0 % it has `object-position:0 0;animation-timing-function:linear`", count=4)
    mutate(bp / "book.html", f"0%{{{kf('0')};animation-timing-function:linear}}", f"0%{{{kf('0')}}}", 4)
    mutate(bp / "book.html", f"0%{{{kf('0')}}}", f"from{{{kf('0')}}}", 4)                        # from and to are 0% and 100%
    mutate(bp / "book.html", f"100%{{{kf('-64px')}}}", f"to{{{kf('-64px')}}}", 4)
    assert lint(bp)["motion:replay"]["status"] == "pass"
    # the book is older than frames.json: the stills moved, and the keyframes say so
    write_frames(bp, pcts=[0, 10, 20, 30, 40, 50, 60, 70, 100], shade=1)
    assert "do not step through the stills of frames.json" in lint(bp)["motion:replay"]["detail"]


def test_motion_replay_fails_a_flipbook_whose_direction_play_state_fill_mode_or_delay_would_not_play_the_stills_once_in_order(bp):
    once = f"{LENGTH}ms step-end 1 both"
    for new, needle in ((f"{LENGTH}ms step-end 1 reverse both", "the flipbook's direction is reverse (replay unchecked, slow unchecked), not normal"),
                        (f"{LENGTH}ms step-end 1 alternate both", "the flipbook's direction is alternate (replay unchecked, slow unchecked), not normal"),
                        (f"{LENGTH}ms step-end 1 both paused", "the flipbook's play state is paused (replay unchecked, slow unchecked), not running"),
                        (f"{LENGTH}ms step-end 1 forwards", "the flipbook's fill mode is forwards (replay unchecked, slow unchecked), not both"),
                        (f"{LENGTH}ms step-end 1", "the flipbook's fill mode is none (replay unchecked, slow unchecked), not both"),
                        (f"{LENGTH}ms 50ms step-end 1 both", "the flipbook's delay is 50ms (replay unchecked, slow unchecked), not 0")):      # the second time of the shorthand is the delay
        break_book(bp, once, new, "motion:replay", needle)
        mutate(bp / "book.html", new, once)
        assert lint(bp)["motion:replay"]["status"] == "pass"
    base = "#bc-replay-demo-page~.motion-stage .motion-flip"
    for prop, value, needle in (("animation-direction", "reverse", "direction is reverse"), ("animation-play-state", "paused", "play state is paused"),
                                ("animation-fill-mode", "backwards", "fill mode is backwards"), ("animation-delay", "1s", "delay is 1s")):      # a longhand after the shorthand counts as much
        rule = f"{base}{{{prop}:{value}}}"
        break_book(bp, "</style>", rule + "</style>", "motion:replay", needle)
        mutate(bp / "book.html", rule + "</style>", "</style>")
    rule = "#bc-slow-demo-page:checked~.motion-stage .motion-flip{animation-direction:reverse}"                  # one state of the two boxes is enough
    break_book(bp, "</style>", rule + "</style>", "motion:replay", "the flipbook's direction is reverse (replay unchecked, slow checked), not normal")
    mutate(bp / "book.html", rule + "</style>", "</style>")
    assert lint(bp)["motion:replay"]["status"] == "pass"


def test_a_style_attribute_is_weighed_in_the_cascade_over_a_rule_of_its_importance_and_below_an_important_one(bp):
    flip = '<img class="motion-flip"'
    inline = lambda css: f'<img class="motion-flip" style="{css}"'      # noqa: E731
    break_book(bp, flip, inline("animation-timing-function:linear"), "motion:replay", "the flipbook's timing function is linear (replay unchecked, slow unchecked)")      # a style attribute counts
    mutate(bp / "book.html", "</style>", ".motion-flip{animation-timing-function:step-end!important}</style>")
    assert lint(bp)["motion:replay"]["status"] == "pass"                                                         # an !important rule beats an inline declaration that is not important
    mutate(bp / "book.html", inline("animation-timing-function:linear"), inline("animation-timing-function:linear!important"))
    assert "the flipbook's timing function is linear" in lint(bp)["motion:replay"]["detail"]                     # and an important inline one beats it
    mutate(bp / "book.html", inline("animation-timing-function:linear!important"), flip)
    mutate(bp / "book.html", ".motion-flip{animation-timing-function:step-end!important}", "#bc-replay-demo-page~.motion-stage .motion-flip.motion-flip{animation-timing-function:linear}")
    assert "the flipbook's timing function is linear" in lint(bp)["motion:replay"]["detail"]                     # a rule more specific than the one that sets it
    mutate(bp / "book.html", flip, inline("animation-timing-function:step-end"))
    assert lint(bp)["motion:replay"]["status"] == "pass"                                                         # an inline declaration beats a rule of its importance, however specific
    mutate(bp / "book.html", inline("animation-timing-function:step-end"), flip)
    mutate(bp / "book.html", "#bc-replay-demo-page~.motion-stage .motion-flip.motion-flip{animation-timing-function:linear}", "")
    assert lint(bp)["motion:replay"]["status"] == "pass"
    # the other rows read it too: the size and the fit of the flipbook, and whether it is shown
    break_book(bp, flip, inline("width:9px"), "motion:stills", "the flipbook is 9 x 8 px")
    mutate(bp / "book.html", inline("width:9px"), inline("object-fit:fill"))
    assert "the flipbook's object-fit is fill" in lint(bp)["motion:stills"]["detail"]
    mutate(bp / "book.html", inline("object-fit:fill"), flip)
    stage = '<div class="motion-stage"'
    break_book(bp, stage, stage + ' style="display:none"', "motion:replay", "the flipbook is not shown on a screen: its style says display: none (on its ancestor <div>)")
    mutate(bp / "book.html", "</style>", ".motion-stage{display:block!important}</style>")
    assert lint(bp)["motion:replay"]["status"] == "pass"                                                         # an important rule shows what an inline style hides


def test_a_rule_inside_layer_scope_container_or_supports_is_not_applied_and_the_rows_that_read_what_it_sets_name_it(bp):
    base = "#bc-replay-demo-page~.motion-stage .motion-flip"
    for at in ("@layer demo", "@scope (.motion-demo)", "@container (min-width:1px)", "@supports (display:grid)"):
        rule = f"{at}{{{base}{{animation-name:none}}}}"      # applied, it would win by its place: the flipbook would have no animation
        mutate(bp / "book.html", "</style>", rule + "</style>")
        rows = lint(bp)
        for r in ("motion:reduced", "motion:replay"):
            assert rows[r]["status"] == "warn" and f"not read: {base} (sets animation) inside {at}" in rows[r]["detail"], (at, r, rows[r])      # said, not failed and not passed in silence
        assert rows["motion:stills"]["status"] == "pass" and "not read" not in rows["motion:stills"]["detail"]
        mutate(bp / "book.html", rule + "</style>", "</style>")
    for rule in ("@layer demo{.motion-flip{margin:0}}", "@layer demo{.zzz{animation:none}}", "@layer demo{@media print{.motion-flip{display:none}}}"):
        mutate(bp / "book.html", "</style>", rule + "</style>")      # sets nothing a row reads, reaches nothing of a demo, or is for print only
        rows = lint(bp)
        assert all(rows[r]["status"] == "pass" and "not read" not in rows[r]["detail"] for r in ("motion:reduced", "motion:replay", "motion:stills")), rule
        mutate(bp / "book.html", rule + "</style>", "</style>")
    mutate(bp / "book.html", "</style>", "@layer demo{.motion-flip{display:none}}.motion-flip{display:block}</style>")      # in a browser the unlayered rule wins; the lint does not weigh layers
    rows = lint(bp)
    assert rows["motion:replay"]["status"] == "warn" and "not read: .motion-flip (sets display) inside @layer demo" in rows["motion:replay"]["detail"]


def try_css(bp: Path, css: str) -> dict:
    """Append `css` to the book's style, lint, take it out again; -> the rows."""
    mutate(bp / "book.html", "</style>", css + "</style>")
    rows = lint(bp)
    mutate(bp / "book.html", css + "</style>", "</style>")
    return rows


def test_a_stop_inside_layer_scope_container_or_supports_is_not_counted_and_the_row_names_it(bp):
    reduce = "@media (prefers-reduced-motion:reduce){%s}"
    for kind, start, stop in (("animation", ".x{animation:bc-flip-demo-page-r0s0 150ms}", ".x{animation:none}"), ("transition", ".x{transition:color 150ms}", ".x{transition:none}")):
        assert try_css(bp, start + reduce % stop)["motion:reduced"]["status"] == "pass"                  # the stop as it is: it switches the start off
        for at in ("@layer r", "@scope (.motion-demo)", "@container (min-width:1px)", "@supports (display:grid)"):
            for wrapped in (reduce % f"{at}{{{stop}}}", f"{at}{{{reduce % stop}}}"):                       # the at-rule inside the media block, and around it
                row = try_css(bp, start + wrapped)["motion:reduced"]
                assert row["status"] == "fail" and "'.x' starts " in row["detail"], (wrapped, row)       # the stop is not applied by a cascade that does not evaluate it: the gap stays ...
                assert f"not read: .x (sets {kind}) inside {at}" in row["detail"], (wrapped, row)          # ... and the row names the rule
    row = try_css(bp, ".x{animation:bc-flip-demo-page-r0s0 150ms}" + reduce % ".x{animation:none}@layer r{.x{animation:none}}")["motion:reduced"]
    assert row["status"] == "pass" and "not read" not in row["detail"]                                       # a stop that is read leaves the layered one unsaid: nothing is missing


def test_the_css_reader_ends_a_statement_at_rule_at_its_semicolon_and_keeps_a_style_rule_with_nested_rules_whole():
    assert booklint.css_rules('@layer a,b;.x{y:z}@charset "utf-8";@import url("a;b.css") layer(a);.w{v:u}') == [
        ((), "@layer a,b;", "", False), ((), ".x", "y:z", False), ((), '@charset "utf-8";', "", False), ((), '@import url("a;b.css") layer(a);', "", False), ((), ".w", "v:u", False)]
    assert booklint.css_rules("@media print{@layer a;.x{y:z}}@font-face{font-family:x;src:url(a)}") == [(("@media print",), "@layer a;", "", False), (("@media print",), ".x", "y:z", False),
                                                                                                         ((), "@font-face", "font-family:x;src:url(a)", False)]
    assert booklint.css_rules(".a{color:red;&:hover{margin:0}}@media print{.b{@media (x){display:none}}}") == [((), ".a", "color:red;margin:0;", True), (("@media print",), ".b", "display:none;", True)]
    assert booklint.css_blocks("@layer a;.a{b:c}") == [("@layer a;", ""), (".a", "b:c")]


def test_the_rule_after_a_statement_at_rule_is_read_and_a_layer_statement_is_named_in_the_motion_rows(bp):
    for statement in ('@charset "utf-8";', '@import "a.css";', '@import url("a;b.css");', "@layer a,b;", "@layer a;@layer b;", "@namespace svg url(http://www.w3.org/2000/svg);"):
        rows = try_css(bp, statement + ".motion-flip{display:none}")                                         # the rule right after it used to be dropped
        assert rows["motion:replay"]["status"] == "fail" and "the flipbook is not shown on a screen: a rule says display: none" in rows["motion:replay"]["detail"], (statement, rows["motion:replay"])
        assert rows["motion:reduced"]["status"] == ("warn" if "@layer" in statement else "pass"), (statement, rows["motion:reduced"])
    row = try_css(bp, "@media (min-width:1px){@layer a;.motion-flip{display:none}}")["motion:replay"]       # a statement inside a block ends at its semicolon too
    assert row["status"] == "fail" and "a rule says display: none" in row["detail"]
    for statement, named in (("@layer a,b;", ["@layer a,b"]), ("@layer a, b;", ["@layer a,b"]), ("@layer a;@layer b;", ["@layer a", "@layer b"])):      # a layer statement orders the layers: every motion row says it did not read it
        rows = try_css(bp, statement + ".zzz{margin:0}")
        for r in ("motion:reduced", "motion:replay", "motion:stills"):
            assert rows[r]["status"] == "warn" and all(f"not read: {n} (orders the layers of the cascade)" in rows[r]["detail"] for n in named), (statement, r, rows[r])
    for statement in ('@charset "utf-8";', '@import "a.css";'):                                                 # the others change nothing the rows read
        rows = try_css(bp, statement + ".zzz{margin:0}")
        assert all(rows[r]["status"] == "pass" and "not read" not in rows[r]["detail"] for r in ("motion:reduced", "motion:replay", "motion:stills")), statement


def test_motion_reduced_weighs_a_stop_against_the_declaration_that_wins_on_each_longhand_and_the_other_rules_that_can_select_the_element(bp):
    reduce = "@media (prefers-reduced-motion:reduce){%s}"

    def case(css: str, status: str, needle: str = "") -> None:
        row = try_css(bp, css)["motion:reduced"]
        assert row["status"] == status and needle in row["detail"], (css, row)
    # the declaration that wins in the rule is the important one, wherever it stands: a plain stop loses to it on both longhands
    case(".y{transition-property:color!important;transition-duration:150ms!important;transition:color 150ms}" + reduce % ".y{transition:none}", "fail", "'.y' starts a transition with !important")
    case(".y{transition-property:color!important;transition-duration:150ms!important;transition:color 150ms}" + reduce % ".y{transition:none!important}", "pass")
    case(".y{animation-name:bc-flip-demo-page-r0s0!important;animation:none}" + reduce % ".y{animation:none}", "fail", "'.y' starts the animation bc-flip-demo-page-r0s0 with !important")
    case(".y{animation-name:bc-flip-demo-page-r0s0!important;animation:none}" + reduce % ".y{animation:none!important}", "pass")
    case(".y{animation-name:none!important;animation:bc-flip-demo-page-r0s0 150ms}", "pass")                  # an important none is the winner: nothing starts
    # another rule that can select the element outweighs the stop: a more specific one, a refinement, or one that sets the longhand later
    start = ".y{transition-duration:150ms}"
    case(start + "main .y{transition-property:color}" + reduce % ".y{transition-property:none}", "fail",
         "'.y' starts a transition and the transition: none for it in @media (prefers-reduced-motion: reduce) is outweighed by 'main .y'")
    case(start + ".y.on{transition-property:color}" + reduce % ".y{transition-property:none}", "fail", "outweighed by '.y.on'")
    case(start + "div.y{transition-property:color}" + reduce % ".y{transition-property:none}", "fail", "outweighed by 'div.y'")
    case(start + "#a{transition-property:color}" + reduce % ".y{transition-property:none}", "fail", "outweighed by '#a'")
    case(start + ".y{transition-property:color}" + reduce % ".y{transition-property:none}", "pass")           # the same selector, earlier: the stop is the later rule
    case(reduce % ".y{transition-property:none}" + start + ".y{transition-property:color}", "fail", "no later rule")       # the same selector, later: it wins
    case(start + "main .y{transition-property:color}" + reduce % ".y{transition:none}", "pass")              # the stop wins on the duration, where nothing outweighs it
    case(start + "main .y{transition-property:color}" + reduce % ".y{transition-property:none}main .y{transition-property:none}", "pass")      # and the refinement is switched off under its own selector
    case(start + "span.y{transition-property:color}" + reduce % "div.y{transition-property:none}", "fail", "no later rule")                     # a rule for another tag does not meet it
    case(start + "span.y{transition-property:color}" + reduce % ".y{transition-property:none}", "fail", "outweighed by 'span.y'")
    case("a{transition:color 150ms}.btn{transition:background 200ms}" + reduce % "a{transition:none}.btn{transition:none}", "pass")           # two starts, each switched off under its own selector
    case("a{transition:color 150ms}" + "a:hover{transition-property:background}" + reduce % "a{transition-property:none}", "fail", "outweighed by 'a:hover'")


def test_a_start_where_the_cascade_does_not_look_is_weighed_as_if_it_applies_and_named(bp):
    # an !important start inside @supports, @layer or @container still needs an !important stop: Chromium runs the animation under reduced motion otherwise
    reduce = "@media (prefers-reduced-motion:reduce){%s}"
    for at in ("@supports (display:grid)", "@layer demo", "@container (min-width:1px)"):
        row = try_css(bp, at + "{.zz{animation:bc-flip-demo-page-r0s0 320ms!important}}" + reduce % ".zz{animation:none}")["motion:reduced"]
        assert row["status"] == "fail" and "'.zz' starts the animation bc-flip-demo-page-r0s0 with !important" in row["detail"], (at, row)
        assert f"not read: .zz (starts animation) inside {at}" in row["detail"], (at, row)
        row = try_css(bp, at + "{.zz{animation:bc-flip-demo-page-r0s0 320ms!important}}" + reduce % ".zz{animation:none!important}")["motion:reduced"]
        assert row["status"] == "warn" and f"not read: .zz (starts animation) inside {at}" in row["detail"], (at, row)   # switched off, and still named
    row = try_css(bp, "@supports (display:grid){.zz{transition:color 150ms}}" + reduce % ".zz{transition:none}")["motion:reduced"]
    assert row["status"] == "warn" and "not read: .zz (starts transition) inside @supports (display:grid)" in row["detail"], row     # a plain start: a plain stop is enough


def test_a_block_that_holds_nested_rules_is_named_in_the_rows_it_could_affect_and_an_inline_important_with_no_space_is_read(bp):
    for rule, sets in ((".motion-flip{display:none;&:hover{margin:0}}", "display"),                          # the flipbook is hidden in a browser, and the cascade here has not seen it
                       (".motion-flip{margin:0;&:hover{display:none}}", "display"),                          # what the nested rule sets counts as much
                       (".motion-flip{margin:0;.x &{animation:none}}", "animation"),
                       (".motion-flip{margin:0;@media (prefers-reduced-motion:reduce){transition:none}}", "transition")):
        rows = try_css(bp, rule)
        for r in ("motion:reduced", "motion:replay"):
            assert rows[r]["status"] == "warn" and f"not read: .motion-flip (sets {sets}) with nested rules" in rows[r]["detail"], (rule, r, rows[r])
        assert rows["motion:stills"]["status"] == "pass" and "not read" not in rows["motion:stills"]["detail"], rule
    rows = try_css(bp, ".motion-flip{max-width:8px;&:hover{padding:0}}")                                    # it sets what only motion:stills reads
    assert rows["motion:stills"]["status"] == "warn" and "not read: .motion-flip (sets max-width) with nested rules" in rows["motion:stills"]["detail"]
    assert rows["motion:reduced"]["status"] == "pass" and rows["motion:replay"]["status"] == "pass"
    rows = try_css(bp, ".motion-flip{margin:0;&:hover{padding:0}}.zzz{display:none;&:hover{margin:0}}")      # sets nothing a row reads, or reaches nothing of a demo
    assert all(rows[r]["status"] == "pass" and "not read" not in rows[r]["detail"] for r in ("motion:reduced", "motion:replay", "motion:stills"))
    rows = try_css(bp, "@layer demo{.motion-flip{display:none;&:hover{margin:0}}}")                           # inside an at-rule it is both
    assert "not read: .motion-flip (sets display) inside @layer demo with nested rules" in rows["motion:replay"]["detail"]
    # a stop with nested rules is not counted either
    row = try_css(bp, ".x{animation:bc-flip-demo-page-r0s0 150ms}@media (prefers-reduced-motion:reduce){.x{animation:none;&:hover{margin:0}}}")["motion:reduced"]
    assert row["status"] == "fail" and "'.x' starts" in row["detail"] and "not read: .x (sets animation) with nested rules" in row["detail"]
    # an inline style is read the way a rule is: `!important` needs no space before it
    p_ = '<p class="eyebrow">'
    for style in ("transition:color 150ms!important", "transition:color 150ms !important", "animation:bc-flip-demo-page-r0s0 150ms!important", "transition-duration:150ms!important;transition-property:color"):
        mutate(bp / "book.html", p_, f'<p style="{style}" class="eyebrow">')
        row = lint(bp)["motion:reduced"]
        assert row["status"] == "fail" and "<p style> starts " in row["detail"] and "cannot be switched off under reduced motion" in row["detail"], (style, row)
        mutate(bp / "book.html", f'<p style="{style}" class="eyebrow">', p_)
    mutate(bp / "book.html", p_, '<p style="transition:color 0s!important;animation:none!important" class="eyebrow">')
    assert lint(bp)["motion:reduced"]["status"] == "pass"                                                    # a duration of 0 and no animation start nothing


def test_motion_replay_fails_an_important_object_position_and_motion_stills_reads_the_limits_of_the_size_like_the_size(bp):
    flip, inline = ".motion-flip", lambda css: f'<img class="motion-flip" style="{css}"'      # noqa: E731
    row = try_css(bp, f"{flip}{{object-position:0 0!important}}")["motion:replay"]
    assert row["status"] == "fail" and "the flipbook has object-position: 0 0 !important, which the keyframes cannot override, so the replay is frozen" in row["detail"]
    assert try_css(bp, f"{flip}{{object-position:0 0!important}}")["motion:stills"]["status"] == "pass"       # the replay's row, not the stills'
    for css in (f"{flip}{{object-position:0 0}}", f"@media print{{{flip}{{object-position:0 0!important}}}}"):      # the keyframes move a plain declaration; print has no animation
        assert try_css(bp, css)["motion:replay"]["status"] == "pass", css
    break_book(bp, '<img class="motion-flip"', inline("object-position:0 0!important"), "motion:replay", "object-position: 0 0 !important, which the keyframes cannot override")      # an inline one too
    mutate(bp / "book.html", inline("object-position:0 0!important"), '<img class="motion-flip"')
    mutate(bp / "book.html", "</style>", f"{flip}{{object-position:0 0!important}}#bc-replay-demo-page~.motion-stage {flip}{{object-position:5px 0!important}}</style>")
    assert "the replay is frozen" in lint(bp)["motion:replay"]["detail"]                                      # the winner of the two is important as well
    mutate(bp / "book.html", f"{flip}{{object-position:0 0!important}}#bc-replay-demo-page~.motion-stage {flip}{{object-position:5px 0!important}}</style>", "</style>")
    # the size is the width and height held by max- and min-: a size that is not one still's fails motion:stills
    for css, shown in ((f"{flip}{{max-width:4px}}", "4 x 8 px (max-width: 4px)"), (f"{flip}{{max-height:4px}}", "8 x 4 px (max-height: 4px)"),
                       (f"{flip}{{min-width:16px}}", "16 x 8 px (min-width: 16px)"), (f"{flip}{{min-height:9px}}", "8 x 9 px (min-height: 9px)"),
                       (f"{flip}{{max-width:6px;min-width:7px}}", "7 x 8 px (max-width: 6px, min-width: 7px)"),      # a min wins where the two meet
                       (f"{flip}{{width:20px;max-width:4px}}", "4 x 8 px (max-width: 4px)")):
        row = try_css(bp, css)["motion:stills"]
        assert row["status"] == "fail" and f"the flipbook is {shown}, one still of frames.json is 8 x 8 px" in row["detail"], (css, row)
    for css in (f"{flip}{{max-width:8px;min-width:8px;max-height:8px;min-height:8px}}", f"{flip}{{max-width:none;min-width:auto;min-height:0}}", f"{flip}{{max-width:100px;min-width:1px}}"):
        assert try_css(bp, css)["motion:stills"]["status"] == "pass", css                                      # limits that leave the size alone
    row = try_css(bp, f"{flip}{{max-width:100%}}")["motion:stills"]                                           # a limit the lint cannot read as px is said, not skipped
    assert row["status"] == "fail" and "the flipbook's max-width is 100%, which the lint does not read as px: it may show more or less than one still" in row["detail"]
    break_book(bp, '<img class="motion-flip"', inline("max-width:4px"), "motion:stills", "the flipbook is 4 x 8 px (max-width: 4px)")


def test_a_source_a_browser_may_skip_keeps_the_strip_from_being_read_and_fails_motion_replay_and_motion_stills_naming_it(bp):
    plain = '<source type="image/png" srcset='
    for attrs, named in (('type="image/x-nope"', '<source type="image/x-nope">'), ('type="image/webp"', '<source type="image/webp">'),
                         ('type="image/png" media="(min-width:99999px)"', '<source media="(min-width:99999px)" type="image/png">'), ('media="all"', '<source media="all">'),
                         ('type="image/png" media=""', '<source media="" type="image/png">')):
        mutate(bp / "book.html", plain, f"<source {attrs} srcset=")
        rows = lint(bp)
        for r in ("motion:replay", "motion:stills"):
            assert rows[r]["status"] == "fail" and f"the flipbook's {named} may not be the one a browser takes the strip from" in rows[r]["detail"], (attrs, r, rows[r])
        assert "the flipbook picture is not" not in rows["motion:stills"]["detail"] and "no flipbook picture" not in rows["motion:stills"]["detail"], rows["motion:stills"]      # it names the source, not the picture
        mutate(bp / "book.html", f"<source {attrs} srcset=", plain)
        assert lint(bp)["motion:stills"]["status"] == "pass"
    for attrs in ("", 'type="IMAGE/PNG"', 'type=" image/png "'):                                              # the strip's source needs no media and a png type, or no type
        mutate(bp / "book.html", plain, f"<source {attrs} srcset=")
        rows = lint(bp)
        assert rows["motion:replay"]["status"] == "pass" and rows["motion:stills"]["status"] == "pass", (attrs, rows["motion:replay"], rows["motion:stills"])
        mutate(bp / "book.html", f"<source {attrs} srcset=", plain)


# ---------------------------------------------------------------- C: the reading the rows rest on (selectors, @media, the cascade)

PAGE = ('<html><head><style>{css}</style></head><body><figure class="f" id="fig"><input type="checkbox" id="a"><input type="checkbox" id="b"><label for="a">A</label>'
        '<div class="stage"><span class="flip x" data-k="alpha-1" role="img"></span><p><span class="deep"></span></p></div></figure><span class="flip out"></span></body></html>')


def computed(css: str, cls: str, prop: str, *, checked=(), mode: str = "screen"):
    text = PAGE.format(css=css)
    rules, _kf, _uris = booklint.style_rules(text)
    el = next(e for e in booklint._walk(booklint._dom(text)) if cls in e.attrs.get("class", "").split())
    return booklint._cascade(rules, el, prop, checked=frozenset(checked), mode=mode)


def test_the_cascade_the_motion_rows_read_weighs_importance_then_specificity_then_the_later_rule():
    assert computed(".flip{display:none}.flip{display:block}", "flip", "display") == "block"                              # the later of two equal rules
    assert computed(".stage .flip{display:none}.flip{display:block}", "flip", "display") == "none"                       # a more specific rule beats a later one
    assert computed("#fig .flip{display:none}.stage .flip.x{display:block}", "x", "display") == "none"                   # an id beats any number of classes
    assert computed(".stage .flip{display:none}.flip{display:block!important}", "x", "display") == "block"               # !important beats specificity
    assert computed("span{display:none}.out{display:block}", "out", "display") == "block" and computed("span{display:none}", "out", "display") == "none"
    assert computed("*{display:none}", "x", "display") == "none" and computed(".out{display:none}", "x", "display") is None   # a rule for another element says nothing
    assert computed(".flip{display:none;display:block}", "x", "display") == "block"                                       # within one rule the later declaration
    assert computed(".flip{animation:foo 1s}", "x", "animation-name") == "foo" and computed(".flip{animation:foo 1s}", "x", "animation-duration") == "1000ms"
    assert computed(".flip{animation:foo 1s;animation-name:bar}", "x", "animation-name") == "bar"                        # a longhand after the shorthand wins, and the other way round
    assert computed(".flip{animation-name:bar;animation:foo 1s}", "x", "animation-name") == "foo"


def test_the_selectors_the_motion_rows_read_are_type_id_class_attribute_checked_and_the_four_combinators():
    sel = lambda s, cls="x", **kw: computed(f"{s}{{display:none}}", cls, "display", **kw) == "none"   # noqa: E731
    assert sel("span.flip") and sel("div span") and sel("div > span") and sel("figure span") and not sel("figure > span") and sel("figure > div > span")
    assert sel("[data-k]") and sel('[data-k="alpha-1"]') and sel("[data-k^=alpha]") and sel("[data-k$='-1']") and sel("[data-k*=pha]") and not sel('[data-k="alpha"]')
    assert sel("[data-k~=alpha-1]") and sel('[data-k|="alpha"]') and not sel('[data-k|="alph"]') and sel('[role=img]') and not sel("[data-k^=beta]")
    assert sel("#a ~ .stage .x") and sel("label ~ .stage .x") and sel("#b ~ .stage .x") and not sel("#a + .stage .x") and sel("label + .stage .x")             # ~ any earlier sibling, + the one before
    assert sel("#a:checked ~ .stage .x", checked=["a"]) and not sel("#a:checked ~ .stage .x") and not sel("#a:checked ~ .stage .x", checked=["b"])
    assert not sel(".x:hover") and not sel(".x::before") and not sel(".x:not(.y)") and not sel("a b[")                      # a state the page is not in, a pseudo-element, a selector it does not read
    assert sel(".stage .x, .nothing") and sel(".nothing, .stage .x") and sel("div  >  span.flip")
    assert not sel(".nothing") and not sel("span.nothing") and not sel(".flip.nothing") and not sel("#nothing") and not sel("p .x") and not sel("em")      # what an element lacks it is not selected by


def test_the_media_conditions_the_motion_rows_read_are_screen_print_and_reduced_motion():
    css = "@media print{.flip{display:block}}@media (prefers-reduced-motion: reduce){.flip{display:inline}}@media (max-width:600px){.flip{display:flex}}"
    assert computed(css, "x", "display", mode="print") == "flex" and computed(css, "x", "display", mode="reduce") == "flex"
    assert computed("@media print{.flip{display:block}}", "x", "display", mode="print") == "block" and computed("@media print{.flip{display:block}}", "x", "display") is None
    assert computed("@media (prefers-reduced-motion:reduce){.flip{display:inline}}", "x", "display", mode="reduce") == "inline"
    assert computed("@media (prefers-reduced-motion:reduce){.flip{display:inline}}", "x", "display") is None
    assert computed("@media (prefers-reduced-motion:no-preference){.flip{display:inline}}", "x", "display") == "inline"
    assert computed("@media (prefers-reduced-motion:no-preference){.flip{display:inline}}", "x", "display", mode="reduce") is None
    assert computed("@media screen and (prefers-reduced-motion: reduce){.flip{display:inline}}", "x", "display", mode="reduce") == "inline"
    assert computed("@media screen and (prefers-reduced-motion: reduce){.flip{display:inline}}", "x", "display", mode="print") is None
    assert computed("@media print, (prefers-reduced-motion: reduce){.flip{display:inline}}", "x", "display", mode="reduce") == "inline"
    assert computed("@media (min-width:1px){@media print{.flip{display:inline}}}", "x", "display") is None                  # nested: every condition must hold
    for at in ("@supports (display:grid)", "@layer demo", "@scope (.stage)", "@container (min-width:1px)"):
        assert computed(f"{at}{{.flip{{display:grid}}}}", "x", "display") is None                                           # not evaluated, so not applied (booklint._unread names it)
    assert computed("@media (min-width:1px){@layer demo{.flip{display:grid}}}", "x", "display") is None
    assert computed("@font-face{font-family:x}.flip{display:grid}", "x", "display") == "grid"                                 # another at-rule around nothing of the rule changes nothing


def test_the_data_uris_of_the_style_stand_in_the_rules_and_come_back_by_number():
    text = '<style>.a{background-image:url(data:image/png;base64,AAAA)}.b{background:url( "data:image/png;base64,BBBB" )}</style>'
    rules, _kf, uris = booklint.style_rules(text)
    assert uris == ["data:image/png;base64,AAAA", "data:image/png;base64,BBBB"]
    assert [d[1] for r in rules for d in r.decls if d[0] in ("background-image", "background")] == ["url(data:@0)", "url(data:@1)"]
