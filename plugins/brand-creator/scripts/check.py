#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator check: the gates for the artefacts that exist, nothing more.

  * history/MANIFEST.sha256 is intact (frozen rounds were not touched)
  * mark_lint: every SVG under assets/ is pure vector (no <text>, <tspan>, font-family, @font-face, external href)
  * every artefact listed in assets/manifest.json exists and still has its emitted hash
  * the reports in assets/_checks/ that the existing artefacts call for are present, current (their input hashes still
    match) and passing: tokens, contrast, logo-sheet, board-lint and shot for the latest round, and emit-<target> for each emitter that wrote artefacts;
    with several marks (qa/rules.json marks) logo-sheet/<mark> for each mark and emit-<target>/<mark> for each mark an emitter drew, and every
    drawing a mark's bands name must exist
  * the QA gates an artefact asks for: a manifest row with `qa: ["downscale", ...]` needs a current passing report from
    downscale, states-check, shot --motion, family-check, fontcheck or verify-idempotent; a report that exists is gated too.
    The downscale report must be the one for the row's own master (`downscale_source`); a report on another file does not count.
    shot --motion writes one report per proof file (assets/_checks/motion/<slug>-<hash6>.json): each is gated, except one whose proof sits under
    rounds/, history/ or a removed-*/ folder (an exploration proof: listed, never failing); a report whose proof file is gone is a warning to move it
    to removed-<date>/; a row's motion gate needs one passing gated report. A motion.json of an earlier version is still gated, with a warning.
    `frames` writes one report per proof file as well (assets/_checks/frames/<slug>-<hash6>.json), gated the same way: failing is a failure, stale is
    "not verified" and names `frames <proof> --count N` and then `book` (the book replays the stills the report vouches for), and so is a current one
    that has no passing frames:<case> row for a case of the proof with stills in motion/frames/ (a run of `frames --case` vouches for that case alone)
  * size bands: a slot off the band rule (qa/rules.json) needs an exemption recorded in the manifest
  * staleness: when tools/inputs.json exists, upstream inputs, the plugin version and the emitter code must match it
  * platform-spec rows the pack was built from that are stale or unverified are warned about (specs-due lists them)
  * Tier B packs (android, chrome-ext, msix, profiles, and the watchOS and tvOS files of apple): a file built from an unverified (U) spec row carries the label
    "UNVERIFIED, recheck"; the adaptive icon has its background, foreground and monochrome layers at every density; every MSIX app-list size has its plain,
    unplated and lightunplated files; every avatar and banner of the profile pack is written and its ink still lies inside its safe area
  * the brand book: when book.html exists, a current passing book-lint report made with --self-consistency whose edition, approval and
    facts still match BRAND-STATE.md and FACTS.md, and whose list of the stills of the gated proofs (motion/frames/*/frames.json) is the one
    now on disk; for a generated book also a current `book` report and a book.html that is still the
    bytes `book` wrote (a hand edit fails); a book.pdf report that exists is gated like any other
  * --cascade "<old value or phrase>" (repeatable): no current project artefact may still contain it (text files, PDFs as text, the documents named by
    tools/cascade.json, --also and FAMILY.md parent_docs); lines that record a product repository's old value (ADOPTION.md, LAUNCH.md) warn, they do not fail
  * adoption.json (pins, numbering, accounting) and ADOPTION.md as rendered from it; BRAND.md, DESIGN.md and the applied skill as generated files
  * motion/motion.json, when it exists: valid against its schema, and every duration and curve it names is a built token (a failing row, never a crash)
  * Standard and Full decide motion before G4: once G4 is recorded, motion/motion.json must exist, on or off (motion:decided), and a brand that moves needs a current passing
    report of motion/proof.json, the proof of the approved move (motion:proof; the report of any other proof never counts, a try-out's and the one report of an earlier version included, and a
    current failing one fails the row). A current report that says not-verified is quoted, in its own row and in motion:proof:
    up to three of the rows it could not verify, and what to do about them (motionboard.unverified_why, the words board-lint uses for a variant). From G3 to G4 an undecided motion is an info row. Quick decides it at G4: no row
A check that cannot be established is "not verified" (exit 3), never "pass". A failing gate is exit 1.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "emitters"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "booklib"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "adaptlib"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "boardlib"))
from _common import (Parser, Report, add_project_arg, downscale_report_tool, find_project, gate_recorded, latest_round, main_guard, motion_proof_kind,  # noqa: E402
                     read_state, rel, sha256_file, stale_inputs, verify_history)
from manifest import band_problems, load_artefacts, verify as verify_manifest  # noqa: E402
import qa_rules  # noqa: E402
import tierb  # noqa: E402
from stale import INPUTS_FILE, check_project as check_staleness  # noqa: E402
from mark_lint import lint_svg_file, svg_files_under_assets  # noqa: E402
import bookdata  # noqa: E402
import cascade as cascade_mod  # noqa: E402
import gates as adapt_gates  # noqa: E402
import motionspec  # noqa: E402
import motionboard  # noqa: E402
from _common import EXIT_CANNOT, EXIT_USAGE, CliError, fail  # noqa: E402

APPROVED_PROOF = "motion/proof.json"   # the proof of the approved move: finish.sh proves it, and frames takes the stills the book replays of it
EMITTERS = ("web", "social", "apple", "windows", "linux", "tray", "tauri", "wallet", "developer", "android", "chrome-ext", "msix", "profiles", "print", "presskit")   # each writes assets/_checks/emit-<name>.json
# manifest `qa` value -> (report tool, the command that writes it)
QA_GATES = {
    "downscale": ("downscale", "brand-creator downscale --source <master>"),   # per-source reports: see main()
    "states": ("states", "brand-creator states-check"),
    "motion": ("motion", "brand-creator shot --motion <proof.json>"),   # per-proof reports (assets/_checks/motion/): see main(); a motion.json is the earlier layout
    "family": ("family", "brand-creator family-check"),
    "fonts": ("fontcheck", "brand-creator fontcheck"),
    "idempotent": ("idempotence", "brand-creator verify-idempotent --cmd ..."),
    "print": ("print-check", "brand-creator print-check"),   # print PDFs in the manifest: boxes, bleed, safe zone, label (print_check.py)
}


def report_state(project: Path, tool: str, run_cmd: str, expect_page: str | None = None, expect_source: str | None = None, then: str | None = None):
    """-> (status, detail) for a report on disk: pass | fail | skipped. `then` is a command to run after `run_cmd` (the stills are taken again, then the book is rebuilt)."""
    return read_report_state(project, tool, run_cmd, expect_page, expect_source, then)[:2]


def read_report_state(project: Path, tool: str, run_cmd: str, expect_page: str | None = None, expect_source: str | None = None, then: str | None = None) -> tuple[str, str, dict | None, bool]:
    """-> (status, detail, the report as read or None, whether it is current: its inputs unchanged, and of the page or source asked for), as report_state judges it."""
    again = f"`{run_cmd}`" + (f" and then `{then}`" if then else "")
    f = project / "assets" / "_checks" / f"{tool}.json"
    if not f.is_file():
        return "skipped", f"not verified: no {tool} report; run {again}", None, False
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
    except ValueError:
        return "fail", f"{rel(project, f)} is not valid JSON; re-run {again}", None, False
    stale = stale_inputs(project, doc)
    if expect_page and doc.get("page") != expect_page:
        stale.append(f"the report is for {doc.get('page')}, the latest page is {expect_page}")
    if expect_source and doc.get("source") != expect_source:
        stale.append(f"the report measured {doc.get('source')}, the manifest needs {expect_source}")
    if stale:
        return "skipped", f"not verified: {tool} report is stale ({'; '.join(stale)}); re-run {again}", doc, False
    st = doc.get("status")
    if st == "pass":
        return "pass", f"{tool} report is current and passing", doc, True
    if st == "fail":
        failing = [r["id"] for r in doc.get("results", []) if r.get("status") == "fail"][:4]
        return "fail", f"{tool} report is failing ({', '.join(failing)}); see assets/_checks/{tool}.json", doc, True
    if tool == "motion" or tool.startswith("motion/"):   # a current report of `shot --motion` that is no verdict: it says which rows it could not verify, and what to do, as board-lint says it of a variant
        quoted, how = motionboard.unverified_why(doc, run_cmd)
        return "skipped", f"not verified: {tool} report status is {st!r} ({quoted}): {how}", doc, True
    return "skipped", f"not verified: {tool} report status is {st!r}", doc, True


def gate_proof_reports(project: Path, rep: Report, folder: str, command, vouches=None) -> list[dict]:
    """Gate every report under assets/_checks/<folder>/ (one per proof file) by the proof it names: a proof under rounds/, history/ or a removed-*/ folder is an exploration
    proof (listed, never failing), a report whose proof is gone is a warning, the rest are gated. `command(doc, proof)` -> (the command that writes the report again, the command
    to run after it or None). `vouches(project, doc, proof)` -> why a current, passing report does not stand for all it should (then it is "not verified"), else None.
    -> one record per gated report: its row, the proof it names (None when it names none), the row's status and detail, the report as read and whether it is current."""
    gated: list[dict] = []
    for f in sorted((project / "assets" / "_checks" / folder).glob("*.json")):
        tool = f"{folder}/{f.stem}"
        try:
            doc = json.loads(f.read_text(encoding="utf-8"))
            proof = doc.get("proof")
        except (ValueError, AttributeError):
            doc, proof = None, None   # not readable: report_state fails it, as for any report
        proof = proof if isinstance(proof, str) else None
        kind = motion_proof_kind(project, proof)
        if kind == "gone":
            rep.add(f"report:{tool}", "warn", "gate report", detail=f"the proof {proof} no longer exists, so {rel(project, f)} gates nothing; move it to removed-<date>/")
        elif kind == "exploration":
            rep.add(f"report:{tool}", "info", "gate report", detail=f"exploration proof, not gated: {proof} is under rounds/, history/ or a removed-*/ folder")
        else:
            run_cmd, then = command(doc, proof)
            st, detail, read, current = read_report_state(project, tool, run_cmd, then=then)
            gap = vouches(project, doc, proof) if vouches and st == "pass" else None
            if gap:
                st, detail = "skipped", f"not verified: {gap}; re-run `{run_cmd}`" + (f" and then `{then}`" if then else "")
            rep.add(f"report:{tool}", st, "gate report", detail=detail)
            gated.append({"row": f"report:{tool}", "proof": proof, "status": st, "detail": detail, "doc": read, "current": current})
    return gated


def frames_again(doc: dict | None, proof: str | None) -> tuple[str, str]:
    """The commands that make a stale `frames` report current: the run it records (its points as --count N or --at), then the book, which replays the stills it vouches for."""
    pts = (doc or {}).get("points_pct")
    if proof and isinstance(pts, list) and pts and all(isinstance(p, (int, float)) and not isinstance(p, bool) for p in pts):
        return bookdata.frames_command({"proof": proof, "frames": [{"percent": p} for p in pts]}), "brand-creator book"
    return f"brand-creator frames {proof or '<proof.json>'} --count 25", "brand-creator book"


def frames_unvouched(project: Path, doc: dict | None, proof: str | None) -> str | None:
    """Why a current, passing `frames` report does not vouch for the stills the book replays, else None. One report is kept per proof and every run rewrites it, so after
    `frames --case X` it covers X alone: a case of the proof that has stills in motion/frames/ and no passing frames:<case> row in it replays stills that nothing says are
    the page as it is now (the run that took them may be older than a change to the page)."""
    if not proof or not isinstance(doc, dict):
        return None
    passed = {r.get("id") for r in doc.get("results", []) if isinstance(r, dict) and r.get("status") == "pass"}
    left = [c for c in bookdata.proof_stills(project, proof) if f"frames:{c}" not in passed]
    took = ", ".join(str(c.get("name")) for c in doc.get("cases", []) if isinstance(c, dict)) or "no case"
    return f"the frames report of {proof} does not vouch for the stills of {', '.join(left)} in motion/frames/ (its last run took {took})" if left else None


def motion_decision_rows(project: Path, rep: Report, gated: list[dict]) -> None:
    """Standard and Full decide motion before G4: motion/motion.json, on or off with the owner's reason. Once G4 is recorded it must exist (motion:decided; whether it is valid is the
    motion:spec row), and when it says the brand moves the proof of the approved move, motion/proof.json, must have a current passing report (motion:proof). `gated` are the gated motion
    reports (gate_proof_reports); the one of the approved proof is found by the proof it names, as the same file: a disk that does not tell letter cases apart names it after the proof as it
    spells it (Motion/proof.json), which is not always as it is typed here. The report of any other proof never counts: another proof of the project, one that names no proof, a try-out's (not
    gated) or the one report of an earlier version (not among them). From G3 to G4 an undecided motion is an info row. Quick decides it at G4, and only when something moves: no row."""
    if str(read_state(project).get("tier", "") or "").strip().lower() not in ("standard", "full"):
        return
    spec = project / motionspec.FILE
    label = "motion is decided before G4"
    if not gate_recorded(project, "G4"):
        if gate_recorded(project, "G3") and not spec.is_file():
            rep.add("motion:decided", "info", label, detail=f"not decided yet; due before G4: {motionspec.DECIDE}")
        return
    if not spec.is_file():
        rep.add("motion:decided", "fail", label, detail=f"Standard and Full decide motion before G4: {motionspec.DECIDE}")
        return
    try:
        mode = json.loads(spec.read_text(encoding="utf-8")).get("motion")
    except (OSError, ValueError, AttributeError):
        mode = None   # a file that cannot be read still counts as decided here; motion:spec fails it
    rep.add("motion:decided", "pass", label, detail=f"{motionspec.FILE} exists" + (f" (motion {mode})" if mode in ("on", "off") else ""))
    if mode != "on":
        return
    label = "the approved move has a passing proof"
    approved = project / APPROVED_PROOF
    cmd = f"brand-creator shot --motion {APPROVED_PROOF}"
    if not approved.is_file():
        rep.add("motion:proof", "fail", label, detail=f"{motionspec.FILE} says the brand moves, but there is no proof of the approved move: write {APPROVED_PROOF}")
        return
    mine = [g for g in gated if g["proof"] and (project / g["proof"]).is_file() and (project / g["proof"]).samefile(approved)]
    passing = sorted({g["proof"] for g in mine if g["status"] == "pass"})
    failing = [g for g in mine if g["status"] == "fail"]
    unsure = [g for g in mine if g["status"] == "skipped" and g["current"]]   # current and no verdict: not "run it again" but which rows it could not verify
    if failing:   # the proof ran and failed: a failure, as the report's own row is, never "not verified", and never outvoted by a passing report of the same file under another name
        rep.add("motion:proof", "fail", label, detail=f"the proof of the approved move fails: {failing[0]['detail']}; change the move as its failing rows say, then run `{cmd}`")
    elif passing:
        rep.add("motion:proof", "pass", label, detail=f"met by the report of {', '.join(passing)}")
    elif unsure:
        doc = unsure[0]["doc"]
        quoted, how = motionboard.unverified_why(doc, cmd)
        rep.add("motion:proof", "skipped", label, detail=f"not verified: the motion report of {APPROVED_PROOF} is {doc.get('status')!r}, not a verdict ({quoted}): {how}")
    else:   # no report of it, or a stale one
        rep.add("motion:proof", "skipped", label, detail=f"not verified: run `{cmd}`")


def main() -> int:
    ap = Parser(prog="brand-creator check", description=__doc__, formatter_class=__import__("argparse").RawDescriptionHelpFormatter)
    add_project_arg(ap)
    ap.add_argument("--cascade", action="append", default=[], metavar="OLD", help="old value or phrase that must no longer appear (repeatable)")
    ap.add_argument("--ignore-case", action="store_true", help="case-insensitive cascade search")
    ap.add_argument("--also", action="append", default=[], metavar="PATH", help="a document or folder outside the project to search too (read only; also from tools/cascade.json and FAMILY.md parent_docs)")
    a = ap.parse_args()
    project = find_project(a.project)
    rep = Report("check", project)
    renderer = str(read_state(project).get("renderer", "") or "resvg")
    rep.renderer = renderer

    problems = verify_history(project)
    if (project / "history").is_dir():
        rep.add("history:manifest", "fail" if problems else "pass", "frozen rounds are intact",
                detail="; ".join(problems[:6]) if problems else "history/MANIFEST.sha256 matches")
    else:
        rep.add("history:manifest", "info", "nothing frozen yet")

    svgs = svg_files_under_assets(project)
    for f in svgs:
        bad = lint_svg_file(f)
        rep.add(f"mark_lint:{rel(project, f)}", "fail" if bad else "pass", "pure vector",
                detail="; ".join(bad) if bad else "no text, fonts or external references")
    if not svgs:
        rep.add("mark_lint", "info", "no SVG under assets/ yet")

    arts = load_artefacts(project)
    if arts:
        mprob = verify_manifest(project)
        rep.add("manifest:artefacts", "fail" if mprob else "pass", f"{len(arts)} artefact(s) listed in assets/manifest.json",
                detail="; ".join(mprob[:6]) if mprob else "all present with their emitted hashes")

    tokens = project / "assets" / "tokens" / "tokens.json"
    expectations = []
    if tokens.is_file():
        expectations += [("tokens", "brand-creator tokens", None), ("contrast", "brand-creator contrast", None)]
    rules, _rules_src = qa_rules.load(project)
    for mid, m in rules["marks"].items():
        missing = [b["drawing"] for b in m["bands"] if not (project / b["drawing"]).is_file()]
        rep.add(f"marks:{mid}", "fail" if missing else "pass", "every drawing the mark's bands name exists",
                detail=f"missing: {', '.join(missing)}" if missing else ", ".join(b["drawing"] for b in m["bands"]))
    if any(project.glob("assets/logo/*.svg")):
        if rules["marks"]:   # one logo sheet per mark: a passing sheet of one mark never stands in for another
            expectations += [(f"logo-sheet/{mid}", f"brand-creator logo-sheet --mark {mid}", None) for mid in rules["marks"]]
        else:
            expectations.append(("logo-sheet", "brand-creator logo-sheet", None))
    n = latest_round(project)
    if n is not None and (project / "rounds" / f"r{n}" / "board.html").is_file():
        page = f"rounds/r{n}/board.html"
        expectations += [("board-lint", f"brand-creator board-lint {page}", page), ("shot", f"brand-creator shot {page}", page)]
    book_state_sha = None
    book_view = None
    book_out = None
    try:
        bcfg, _ = bookdata.load_config(project)
        book_out = bcfg["output"]
    except CliError as e:
        rep.add("book:config", "fail", "book/book.json is readable", detail=e.message)
    if book_out and (project / book_out).is_file():
        expectations.append(("book-lint", "brand-creator book-lint --self-consistency", None))
        if str(read_state(project).get("mark_source", "")) != "authored-vector":
            expectations.append(("book", "brand-creator book", None))
        try:
            book_view = bookdata.state_view(project)
            book_state_sha = bookdata.view_sha(book_view, bookdata.facts(project))
        except CliError as e:
            rep.add("book:state", "fail", "BRAND-STATE.md has what the book needs (edition, content_languages, mark_source)", detail=e.message)
    if (project / "assets" / "_checks" / "book-pdf.json").is_file():
        expectations.append(("book-pdf", "brand-creator book-pdf", None))
    expectations += [(t, c, None) for t, c in adapt_gates.expected_reports(project)]
    drawn = {(a_.get("emitter"), a_.get("mark")) for a_ in arts}   # one report per emitter, and per mark when the rows name one
    for em in EMITTERS:
        for mk in sorted({mk for e_, mk in drawn if e_ == em}, key=lambda x: x or ""):
            expectations.append((f"emit-{em}" + (f"/{mk}" if mk else ""), f"brand-creator emit {em}" + (f" --mark {mk}" if mk else ""), None))
    wanted = {k for a_ in arts for k in a_.get("qa", [])}
    unknown = sorted(wanted - set(QA_GATES))
    for k in unknown:
        rep.add(f"qa:{k}", "fail", "known QA gate", detail=f"a manifest row asks for QA gate {k!r}; the known gates are {', '.join(sorted(QA_GATES))}")
    for key, (tool, cmd) in QA_GATES.items():
        if key in ("downscale", "motion"):
            continue   # one report per measured source, one per proof file: handled below
        if key in wanted or (project / "assets" / "_checks" / f"{tool}.json").is_file():
            expectations.append((tool, cmd, None))
    # downscale: a row's qa gate is met only by a passing, current report for ITS master (`downscale_source`), never by a report on another file
    sources: dict[str, list[str]] = {}
    for a_ in arts:
        if "downscale" in a_.get("qa", []):
            sources.setdefault(a_.get("downscale_source") or "", []).append(a_["path"])
    for src, paths in sorted(sources.items()):
        if not src:
            rep.add("qa:downscale", "fail", "a downscale row names its master",
                    detail=f"{', '.join(paths[:3])} ask for the downscale gate but record no downscale_source; re-run the emitter that wrote them")
    for src in sorted(s for s in sources if s):
        tool = downscale_report_tool(src)
        st, detail = report_state(project, tool, f"brand-creator downscale --source {src}", expect_source=src)
        rep.add(f"report:{tool}", st, "downscale gate report for the master", detail=f"{src}: {detail}; serves {len(sources[src])} row(s)")
    for f in sorted((project / "assets" / "_checks" / "downscale").glob("*.json")):
        tool = f"downscale/{f.stem}"
        if tool in {downscale_report_tool(s) for s in sources if s}:
            continue
        try:
            src = json.loads(f.read_text(encoding="utf-8")).get("source")
        except ValueError:
            src = None
        st, detail = report_state(project, tool, f"brand-creator downscale --source {src or '<master>'}")
        rep.add(f"report:{tool}", st, "gate report", detail=detail)
    # motion: one report per proof file. A proof under rounds/, history/ or a removed-*/ folder is an exploration proof (listed, never failing); a
    # report whose proof is gone is a warning (move the report to removed-<date>/); the rest are gated. A row that asks for the gate needs one passing.
    motion_cmd = QA_GATES["motion"][1]
    motion_passing: list[str] = []
    legacy = project / "assets" / "_checks" / "motion.json"
    if legacy.is_file():   # the report of an earlier version: gated as it was, and said to be out of date
        st, detail = report_state(project, "motion", motion_cmd)
        rep.add("report:motion", st, "gate report", detail=detail)
        rep.add("report:motion:legacy", "warn", "motion reports are one per proof file now",
                detail=f"{rel(project, legacy)} is from an earlier version; shot --motion writes assets/_checks/motion/<slug>-<hash6>.json for each proof now: "
                       f"re-run `{motion_cmd}` and move {rel(project, legacy)} to removed-<date>/")
        if st == "pass":
            motion_passing.append("report:motion")
    gated = gate_proof_reports(project, rep, "motion", lambda doc, proof: (f"brand-creator shot --motion {proof or '<proof.json>'}", None))
    motion_passing += [g["row"] for g in gated if g["status"] == "pass"]
    # frames: one report per proof file too (assets/_checks/frames/), gated the same way: the book replays the stills it vouches for, so a stale one is "not verified" until
    # `frames` and then `book` have run again (the motion report being current says nothing about the stills)
    gate_proof_reports(project, rep, "frames", frames_again, frames_unvouched)
    if "motion" in wanted:
        rep.add("qa:motion", "pass" if motion_passing else "skipped", "a manifest row asks for the motion gate",
                detail=f"met by {', '.join(motion_passing)}" if motion_passing else f"not verified: no current passing motion report of a proof of this project; run `{motion_cmd}`")
    cvd_set = any(k == "cvd" or k.startswith("cvd.") for k in rules["_from_file"])   # the project's own colour-vision threshold
    for tool, cmd, page in expectations:
        st, detail = report_state(project, tool, cmd, page)
        rep.add(f"report:{tool}", st, "gate report", detail=detail)
        if tool == "contrast" and st == "pass" and cvd_set:
            doc0 = json.loads((project / "assets" / "_checks" / "contrast.json").read_text(encoding="utf-8"))
            if not any(r.get("section") == "cvd" for r in doc0.get("results", [])):
                rep.add("report:contrast:cvd", "skipped", "the contrast report has the colour-vision rows qa/rules.json asks for",
                        detail="not verified: qa/rules.json sets a colour-vision threshold (cvd) and the contrast report has no colour-vision rows; re-run "
                               "`brand-creator contrast --cvd` (a tools/finish.sh copied before 0.3.5 runs contrast without --cvd: add it there too)")
        if tool in ("book", "book-lint", "book-pdf") and st == "pass":
            doc0 = json.loads((project / "assets" / "_checks" / f"{tool}.json").read_text(encoding="utf-8"))
            if doc0.get("manifest_view_sha") != bookdata.manifest_view_sha(project):
                rep.add(f"report:{tool}:manifest", "skipped", "the book was checked against the current manifest",
                        detail=f"not verified: the files the emitters wrote changed since the {tool} report; re-run `{cmd}`")
        if tool in ("book", "book-lint") and st == "pass":
            doc = json.loads((project / "assets" / "_checks" / f"{tool}.json").read_text(encoding="utf-8"))
            if book_view is not None and bookdata.frames_changed(project, book_view, doc.get("frames_view_sha")):   # (a BRAND-STATE.md the book cannot read is failed above)
                rep.add(f"report:{tool}:frames", "skipped", "the book was checked against the stills now in motion/frames/",
                        detail=f"not verified: stills of a gated proof appeared, went or changed since the {tool} report; re-run `{cmd}`")
            if book_state_sha and doc.get("state_view_sha") != book_state_sha:
                rep.add(f"report:{tool}:state", "skipped", "the book was checked against the current BRAND-STATE.md and FACTS.md",
                        detail=f"not verified: the edition, approval, decided items or facts changed since the {tool} report; re-run `{cmd}`")
            if tool == "book-lint" and not doc.get("self_consistency"):
                rep.add("report:book-lint:self", "skipped", "the book-lint report includes the self-consistency rules",
                        detail="not verified: the report was made without --self-consistency; re-run `brand-creator book-lint --self-consistency`")
            if tool == "book":
                out = doc.get("output", {})
                f = project / out.get("path", "")
                same = f.is_file() and sha256_file(f) == out.get("sha256")
                rep.add("book:generated", "pass" if same else "fail", "book.html is the bytes `book` wrote (generated, never hand-edited)",
                        detail="unchanged since the build" if same else f"{out.get('path')} differs from what `book` wrote: it was edited by hand or by another tool; "
                        "edit book/chapters/*.md and run `brand-creator book`")
    if (project / motionspec.FILE).is_file():   # the machine-readable motion spec: its schema, and each duration and curve it names must be a built token
        try:
            rep.add("motion:spec", "pass", "motion/motion.json is valid", detail=motionspec.summary(motionspec.load(project)))
        except CliError as e:
            unbuilt = e.code == EXIT_CANNOT
            rep.add("motion:spec", "skipped" if unbuilt else "fail", "motion/motion.json is valid", detail=("not verified: " if unbuilt else "") + e.message)
    motion_decision_rows(project, rep, gated)   # the report of an earlier version is in motion_passing (qa:motion), never among these
    adapt_gates.rows(project, rep)
    bprobs = band_problems(project)
    if any("band" in a_ or "layer_bands" in a_ for a_ in arts):
        rep.add("manifest:bands", "fail" if bprobs else "pass", "slots follow the size-band rule (or carry an exemption)",
                detail="; ".join(bprobs[:6]) if bprobs else "every slot's band is the one the picker names, or has a stated exemption")
    for rid_, st_, label_, detail_ in tierb.rows(project):   # Tier B packs: the unverified-row label, the adaptive layers, the MSIX unplated trio
        rep.add(rid_, st_, label_, detail=detail_)
    if (project / INPUTS_FILE).is_file():
        try:
            check_staleness(project, rep)
        except (ValueError, KeyError) as e:
            rep.add("staleness", "fail", "tools/inputs.json is readable", detail=f"{INPUTS_FILE}: {e}")
    mf = project / "assets" / "manifest.json"
    if mf.is_file():
        try:
            stamped = json.loads(mf.read_text(encoding="utf-8")).get("specs", {})
        except ValueError:
            stamped = {}
        for rid, s in sorted(stamped.items()):
            if s.get("stale") or s.get("status") == "U":
                rep.add(f"specs:{rid}", "warn", "platform-spec row the pack was built from",
                        detail=f"row {rid} is {'stale' if s.get('stale') else 'UNVERIFIED (status U)'} (checked {s.get('checked')}); recheck {s.get('source_url')} (brand-creator specs-due)")
    if not expectations:
        rep.add("reports", "info", "no gated artefacts yet", detail="tokens, logo, a round board or emitted assets will each add their gate")

    if a.cascade or a.also:
        if not a.cascade:
            fail(EXIT_USAGE, "--also needs --cascade")
        for r in cascade_mod.run(project, a.cascade, a.ignore_case, n, a.also):
            extra = {k: v for k, v in r.items() if k not in ("id", "status", "label", "detail")}
            rep.add(r["id"], r["status"], r["label"], detail=r["detail"], **extra)
    if renderer.split()[0] != "resvg" or "opted" in renderer:
        print(f"renderer in use: {renderer}")
    return rep.finish()


main_guard(main)
