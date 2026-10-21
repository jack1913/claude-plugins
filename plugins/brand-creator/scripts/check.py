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
    The downscale report must be the one for the row's own master (`downscale_source`); a report on another file does not count
  * size bands: a slot off the band rule (qa/rules.json) needs an exemption recorded in the manifest
  * staleness: when tools/inputs.json exists, upstream inputs, the plugin version and the emitter code must match it
  * platform-spec rows the pack was built from that are stale or unverified are warned about (specs-due lists them)
  * Tier B packs (android, chrome-ext, msix, profiles, and the watchOS and tvOS files of apple): a file built from an unverified (U) spec row carries the label
    "UNVERIFIED, recheck"; the adaptive icon has its background, foreground and monochrome layers at every density; every MSIX app-list size has its plain,
    unplated and lightunplated files; every avatar and banner of the profile pack is written and its ink still lies inside its safe area
  * the brand book: when book.html exists, a current passing book-lint report made with --self-consistency whose edition, approval and
    facts still match BRAND-STATE.md and FACTS.md; for a generated book also a current `book` report and a book.html that is still the
    bytes `book` wrote (a hand edit fails); a book.pdf report that exists is gated like any other
  * --cascade "<old value or phrase>" (repeatable): no current project artefact may still contain it (text files, PDFs as text, the documents named by
    tools/cascade.json, --also and FAMILY.md parent_docs); lines that record a product repository's old value (ADOPTION.md, LAUNCH.md) warn, they do not fail
  * adoption.json (pins, numbering, accounting) and ADOPTION.md as rendered from it; BRAND.md, DESIGN.md and the applied skill as generated files
A check that cannot be established is "not verified" (exit 3), never "pass". A failing gate is exit 1.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "emitters"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "booklib"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "adaptlib"))
from _common import (Parser, Report, add_project_arg, downscale_report_tool, find_project, latest_round, main_guard, read_state, rel,  # noqa: E402
                     sha256_file, verify_history)
from manifest import band_problems, load_artefacts, verify as verify_manifest  # noqa: E402
import qa_rules  # noqa: E402
import tierb  # noqa: E402
from stale import INPUTS_FILE, check_project as check_staleness  # noqa: E402
from mark_lint import lint_svg_file, svg_files_under_assets  # noqa: E402
import bookdata  # noqa: E402
import cascade as cascade_mod  # noqa: E402
import gates as adapt_gates  # noqa: E402
from _common import EXIT_USAGE, CliError, fail  # noqa: E402

EMITTERS = ("web", "social", "apple", "windows", "linux", "tray", "tauri", "wallet", "developer", "android", "chrome-ext", "msix", "profiles", "print", "presskit")   # each writes assets/_checks/emit-<name>.json
# manifest `qa` value -> (report tool, the command that writes it)
QA_GATES = {
    "downscale": ("downscale", "brand-creator downscale --source <master>"),   # per-source reports: see main()
    "states": ("states", "brand-creator states-check"),
    "motion": ("motion", "brand-creator shot --motion <proof.json>"),
    "family": ("family", "brand-creator family-check"),
    "fonts": ("fontcheck", "brand-creator fontcheck"),
    "idempotent": ("idempotence", "brand-creator verify-idempotent --cmd ..."),
    "print": ("print-check", "brand-creator print-check"),   # print PDFs in the manifest: boxes, bleed, safe zone, label (print_check.py)
}


def report_state(project: Path, tool: str, run_cmd: str, expect_page: str | None = None, expect_source: str | None = None):
    """-> (status, detail) for a report on disk: pass | fail | skipped."""
    f = project / "assets" / "_checks" / f"{tool}.json"
    if not f.is_file():
        return "skipped", f"not verified: no {tool} report; run `{run_cmd}`"
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
    except ValueError:
        return "fail", f"{rel(project, f)} is not valid JSON; re-run `{run_cmd}`"
    stale = []
    for rec in doc.get("inputs", []):
        p = project / rec["path"]
        if not p.is_file():
            stale.append(f"{rec['path']} is gone")
        elif sha256_file(p) != rec["sha256"]:
            stale.append(f"{rec['path']} changed")
    if expect_page and doc.get("page") != expect_page:
        stale.append(f"the report is for {doc.get('page')}, the latest page is {expect_page}")
    if expect_source and doc.get("source") != expect_source:
        stale.append(f"the report measured {doc.get('source')}, the manifest needs {expect_source}")
    if stale:
        return "skipped", f"not verified: {tool} report is stale ({'; '.join(stale)}); re-run `{run_cmd}`"
    st = doc.get("status")
    if st == "pass":
        return "pass", f"{tool} report is current and passing"
    if st == "fail":
        failing = [r["id"] for r in doc.get("results", []) if r.get("status") == "fail"][:4]
        return "fail", f"{tool} report is failing ({', '.join(failing)}); see assets/_checks/{tool}.json"
    return "skipped", f"not verified: {tool} report status is {st!r}"


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
            book_state_sha = bookdata.view_sha(bookdata.state_view(project), bookdata.facts(project))
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
        if key == "downscale":
            continue   # one report per measured source: handled below
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
    for tool, cmd, page in expectations:
        st, detail = report_state(project, tool, cmd, page)
        rep.add(f"report:{tool}", st, "gate report", detail=detail)
        if tool in ("book", "book-lint", "book-pdf") and st == "pass":
            doc0 = json.loads((project / "assets" / "_checks" / f"{tool}.json").read_text(encoding="utf-8"))
            if doc0.get("manifest_view_sha") != bookdata.manifest_view_sha(project):
                rep.add(f"report:{tool}:manifest", "skipped", "the book was checked against the current manifest",
                        detail=f"not verified: the files the emitters wrote changed since the {tool} report; re-run `{cmd}`")
        if tool in ("book", "book-lint") and st == "pass":
            doc = json.loads((project / "assets" / "_checks" / f"{tool}.json").read_text(encoding="utf-8"))
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
