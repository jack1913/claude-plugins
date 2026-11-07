#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator masters: the ads and decks of a brand (a masters round, rounds/rN/masters.json; see scripts/boardlib/mastersdata.py).

  brand-creator masters check [--round N]     render and check every master of the round, write rounds/rN/png/ and the report `masters`

masters check opens each HTML ad and slide at its canvas in the plugin's Chromium, after its fonts load and its animations that end have ended
(the logo reveal), and writes rows: masters:canvas (no element outside the canvas), masters:covered (a text that runs into another text fails; an
element painted over a text warns unless it is inside data-masters-overlay), masters:overlays (info: each overlay), masters:pdf (the deck PDF: one
page per slide, the slides' page size, dates fixed by `brand-creator pdf normalise`), masters:pptx (the PowerPoint file read from its XML: every shape
inside the slide, every font a text names embedded, every picture present) and masters:pptx-render (NOT VERIFIED until the owner opened the deck in
PowerPoint and the answer is in G4m: "PowerPoint: <answer>"). No Office app, LibreOffice or Keynote is driven; Keynote ignores embedded fonts.
Exit 0 pass, 1 a row failed, 2 usage (no masters board), 3 not verified (the PowerPoint answer, or no browser).
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for sub in ("lib", "boardlib", "masterslib"):
    sys.path.insert(0, str(HERE / sub))
from _common import (EXIT_CANNOT, EXIT_FAIL, EXIT_USAGE, Parser, Report, add_project_arg, data_dir, fail, find_project, gate_recorded,  # noqa: E402
                     list_rounds, main_guard, plugin_root, scratch_dir)
from boardpage import page_kind, read_page  # noqa: E402
import determinism  # noqa: E402
import mastersdata  # noqa: E402
import pptxlib  # noqa: E402

MEASURE_TIMEOUT_S = 900
PDF_PAGE = re.compile(rb"/Type\s*/Page(?![s\w])")
PDF_BOX = re.compile(rb"/MediaBox\s*\[\s*([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s+([-\d.]+)\s*\]")
LISTED = 6


def masters_round(project: Path, n: int | None) -> int:
    """The round of the masters board: --round N, else the latest round whose board is a masters board."""
    rounds = list_rounds(project)
    if n is not None:
        d = dict(rounds).get(n)
        if d is None or page_kind(read_page(d / "board.html")) != "masters":
            fail(EXIT_USAGE, f"rounds/r{n}/board.html is not a masters board (data-board=\"masters\")")
        return n
    for k, d in reversed(rounds):
        if page_kind(read_page(d / "board.html")) == "masters":
            return k
    fail(EXIT_USAGE, "there is no masters board in rounds/: a masters round (rounds/rN/board.html with data-board=\"masters\" and its masters.json) comes first")


def listed(items: list[str]) -> str:
    return "; ".join(items[:LISTED]) + (f"; and {len(items) - LISTED} more" if len(items) > LISTED else "")


def measure(project: Path, root: Path, html: list[mastersdata.Entry]) -> dict:
    node = shutil.which("node")
    if not node:
        fail(EXIT_CANNOT, "masters check needs node (Node 22 or newer) and a set-up data directory: run brand-creator prereq, then brand-creator setup")
    data_dir()
    work = scratch_dir(project, "masters")
    req, out = work / "request.json", work / "measures.json"
    out.unlink(missing_ok=True)
    req.write_text(json.dumps({"root": str(root), "png_dir": str(root / "png"),
                               "masters": [{"file": e.file, "width": e.canvas[0], "height": e.canvas[1]} for e in html]}, indent=2), encoding="utf-8")
    try:
        cp = subprocess.run([node, str(plugin_root() / "scripts" / "render.mjs"), "masters-measure", "--request", str(req), "--out", str(out)],
                            capture_output=True, timeout=MEASURE_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        fail(EXIT_CANNOT, f"masters-measure timed out after {MEASURE_TIMEOUT_S}s")
    if cp.returncode != 0:
        fail(EXIT_CANNOT, cp.stderr.decode("utf-8", "replace").strip().removeprefix("error: ") or f"render.mjs masters-measure exited {cp.returncode}")
    return json.loads(out.read_text(encoding="utf-8"))["masters"]


def html_rows(rep: Report, measured: dict) -> None:
    outside = [f"{f}: {', '.join(m['outside'][:4])}" for f, m in measured.items() if m["outside"]]
    rep.add("masters:canvas", "fail" if outside else "pass", "nothing leaves the canvas",
            detail=listed(outside) if outside else f"{len(measured)} master(s): every element inside its canvas")
    collide = [f"{f}: {a} runs into {b}" for f, m in measured.items() for a, b in m["collide"]]
    covered = [f"{f}: {by} is painted over the text of {t}" for f, m in measured.items() for t, by in m["covered"]]
    if collide:
        rep.add("masters:covered", "fail", "no text runs into another or is covered", detail=listed(collide + covered))
    elif covered:
        rep.add("masters:covered", "warn", "no text runs into another or is covered",
                detail=listed(covered) + ". If it is drawn over the text on purpose (a stamp), mark it data-masters-overlay")
    else:
        rep.add("masters:covered", "pass", "no text runs into another or is covered", detail=f"{len(measured)} master(s)")
    overlays = [f"{f}: {', '.join(m['overlays'])}" for f, m in measured.items() if m["overlays"]]
    rep.add("masters:overlays", "info", "drawn over text on purpose (data-masters-overlay)", detail=listed(overlays) if overlays else "none")
    errors = [f"{f}: {x}" for f, m in measured.items() for x in m["errors"] + [f"request to another site: {u}" for u in m["non_local"]] + [f"missing: {u}" for u in m["failed_local"]]]
    if errors:
        rep.add("masters:page-errors", "fail", "each master loads with no error and no request out", detail=listed(errors))


def pdf_rows(rep: Report, root: Path, entry: mastersdata.Entry, slides: list[mastersdata.Entry]) -> None:
    data = (root / entry.file).read_bytes()
    problems = []
    pages = len(PDF_PAGE.findall(data))
    if slides and pages != len(slides):
        problems.append(f"{entry.file} has {pages} page(s) for {len(slides)} slide(s)")
    box = PDF_BOX.search(data)
    if slides and box:
        w, h = float(box.group(3)) - float(box.group(1)), float(box.group(4)) - float(box.group(2))
        cw, ch = slides[0].canvas[0] * 0.75, slides[0].canvas[1] * 0.75
        if abs(w - cw) > 1 or abs(h - ch) > 1:
            problems.append(f"{entry.file}: pages are {w:.0f} x {h:.0f} pt, the slides {cw:.0f} x {ch:.0f} pt ({slides[0].canvas[0]} x {slides[0].canvas[1]} px)")
    if determinism.normalise_pdf(data) != data:
        problems.append(f"{entry.file} carries its own dates or /ID: run brand-creator pdf normalise {entry.file}")
    rep.add("masters:pdf", "fail" if problems else "pass", "the deck PDF", detail="; ".join(problems) if problems else f"{entry.file}: {pages} page(s), normalised")


def pptx_rows(rep: Report, project: Path, root: Path, entry: mastersdata.Entry) -> None:
    try:
        info = pptxlib.inspect(root / entry.file)
    except (ValueError, Exception) as e:   # a broken file is a failed row, never a crash
        rep.add("masters:pptx", "fail", "the PowerPoint file", detail=f"{entry.file}: {e}")
        return
    problems = [f"{x}: outside the slide" for x in info["outside"]]
    unembedded = [f for f in info["fonts_named"] if f not in info["fonts_embedded"]]
    if unembedded:
        problems.append(f"font(s) not embedded: {', '.join(unembedded)} (brand-creator masters embed-fonts {entry.file} --font <file>)")
    problems += [f"{x}: picture missing" for x in info["missing_pictures"]]
    rep.add("masters:pptx", "fail" if problems else "pass", "the PowerPoint file",
            detail=f"{entry.file}: " + (listed(problems) if problems else f"{info['slides']} slide(s), fonts embedded: {', '.join(info['fonts_embedded']) or 'none named'}"))
    g4m = gate_recorded(project, "G4m")
    if "powerpoint" in g4m.lower():
        rep.add("masters:pptx-render", "pass", "the deck renders in PowerPoint (the owner's check)", detail=f"G4m: {g4m}")
    else:
        rep.add("masters:pptx-render", "skipped", "the deck renders in PowerPoint (the owner's check)",
                detail=f"NOT VERIFIED: open {entry.file} in PowerPoint (preferred) and check it shows the brand fonts and nothing overlaps; "
                       f"record the answer with G4m: brand-creator state --record G4m \"<choices>; PowerPoint: <answer>\"")


def cmd_check(project: Path, n: int | None) -> int:
    rnd = masters_round(project, n)
    root = project / "rounds" / f"r{rnd}"
    mf = root / mastersdata.MASTERS_FILE
    m = mastersdata.load_manifest(mf)
    if not mf.is_file() or m.problems:
        fail(EXIT_FAIL, f"rounds/r{rnd}/{mastersdata.MASTERS_FILE}: " + ("does not exist" if not mf.is_file() else "; ".join(m.problems[:5])) + ": run brand-creator board-lint first")
    missing = [e.file for e in m.entries if not (root / e.file).is_file()]
    if missing:
        fail(EXIT_FAIL, f"listed in masters.json but missing in rounds/r{rnd}/: {', '.join(missing[:6])}")
    rep = Report("masters", project, [mf] + [root / e.file for e in m.entries])
    rep.extra = {"round": rnd}
    html = [e for e in m.entries if e.kind in mastersdata.CANVAS_KINDS and e.file.lower().endswith((".html", ".htm"))]
    if html:
        html_rows(rep, measure(project, root, html))
    slides = [e for e in m.entries if e.kind == "slide"]
    for e in m.entries:
        if e.kind == "deck-pdf":
            pdf_rows(rep, root, e, slides)
        elif e.kind == "deck-pptx":
            pptx_rows(rep, project, root, e)
    return rep.finish()


def main() -> int:
    ap = Parser(prog="brand-creator masters", description=__doc__, formatter_class=__import__("argparse").RawDescriptionHelpFormatter)
    subs = ap.add_subparsers(dest="cmd", required=True)
    c = subs.add_parser("check", help="render and check every master of the masters round")
    add_project_arg(c)
    c.add_argument("--round", type=int, help="the masters round (default: the latest masters board)")
    a = ap.parse_args()
    project = find_project(a.project)
    if a.cmd == "check":
        return cmd_check(project, a.round)
    return EXIT_USAGE


main_guard(main)
