#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator masters: the ads and decks of a brand (a masters round, rounds/rN/masters.json; see scripts/boardlib/mastersdata.py).

  brand-creator masters check [--round N]     render and check every master of the round, write rounds/rN/png/ and the report `masters`
  brand-creator masters approve [--round N] [--replace]
                                              after G4m: copy the round's masters, and the files they load, into assets/masters/ with README.md and masters.json
  brand-creator masters embed-fonts <deck.pptx> --font FILE.ttf [--font ...] [--out FILE]
                                              embed TrueType fonts in a PowerPoint deck (PowerPoint shows them without installing them)
  brand-creator pdf normalise <file.pdf> [--out FILE]
                                              fix a PDF's dates and /ID so the same input gives the same bytes (in place by default)

masters check opens each HTML ad and slide at its canvas in the plugin's Chromium, after its fonts load and its animations that end have ended
(the logo reveal), and writes rows: masters:canvas (no element outside the canvas), masters:covered (a text that runs into another text fails; an
element painted over a text warns unless it is inside data-masters-overlay), masters:overlays (info: each overlay), masters:pdf (the deck PDF: one
page per slide, the slides' page size, dates fixed by `brand-creator pdf normalise`), masters:pptx (the PowerPoint file read from its XML: every shape
inside the slide, every font a text names embedded, every picture present) and masters:pptx-render (NOT VERIFIED until the owner opened the deck in
PowerPoint and the answer is in G4m: "PowerPoint: <answer>"). No Office app, LibreOffice or Keynote is driven; Keynote ignores embedded fonts.
Exit 0 pass, 1 a row failed, 2 usage (no masters board), 3 not verified (the PowerPoint answer, or no browser).
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for sub in ("lib", "boardlib", "masterslib"):
    sys.path.insert(0, str(HERE / sub))
from _common import (EXIT_CANNOT, EXIT_FAIL, EXIT_USAGE, Parser, Report, add_project_arg, data_dir, fail, find_project, gate_recorded,  # noqa: E402
                     list_rounds, main_guard, plugin_root, scratch_dir, stale_inputs, today)
import closure  # noqa: E402
from boardpage import page_kind, read_page  # noqa: E402
import determinism  # noqa: E402
import mastersdata  # noqa: E402
import fontembed  # noqa: E402
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


APPROVED_DIR = "assets/masters"
KIND_WORDS = {"ad": "ad", "slide": "slide", "deck-html": "the deck (HTML)", "deck-pdf": "the deck (PDF)", "deck-pptx": "the deck (PowerPoint)", "image": "picture", "font": "font"}


def report_problem(project: Path, tool: str, cmd: str, **match) -> str | None:
    """Why assets/_checks/<tool>.json is not a current, passing report (no file it was made from gone or changed), or None."""
    f = project / "assets" / "_checks" / f"{tool}.json"
    if not f.is_file():
        return f"there is no {tool} report: run {cmd}"
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
        stale = stale_inputs(project, doc)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as e:
        return f"the {tool} report cannot be read ({e}): run {cmd}"
    for k, v in match.items():
        if doc.get(k) != v:
            return f"the {tool} report is for {k} {doc.get(k)!r}, not {v!r}: run {cmd}"
    if stale:
        return f"the {tool} report is stale ({'; '.join(stale[:3])}): run {cmd}"
    if doc.get("status") != "pass":
        return f"the {tool} report is {doc.get('status')!r}, not pass: fix what its rows say, then run {cmd}"
    return None


def readme_text(rnd: int, approved: str, m: mastersdata.Manifest, root: Path) -> str:
    lines = ["# Ads and decks (masters)", "", f"Approved by the owner: {approved} (G4m), from round {rnd} (`rounds/r{rnd}/`). Copied byte for byte by "
             "`brand-creator masters approve`; change a master in a new masters round, get the owner's approval, then approve it again.", "",
             "| File | What | Size |", "| --- | --- | --- |"]
    for e in m.entries:
        size = f"{e.canvas[0]} × {e.canvas[1]}" if e.canvas else "-"
        what = KIND_WORDS[e.kind] + (f", {e.direction}" if e.direction else "") + (f": {e.note}" if e.note else "")
        lines.append(f"| `{e.file}` | {what} | {size} |")
    if m.copy_rules:
        lines += ["", "## Copy rules", ""] + [f"- {r}" for r in m.copy_rules]
    if m.builder:
        lines += ["", "## Rebuild", "", f"`{m.builder}` (from the project root), then `brand-creator masters check --round {rnd}`."]
    if any(e.kind == "deck-pptx" for e in m.entries):
        lines += ["", "## Fonts in the PowerPoint deck", "", "PowerPoint uses the fonts embedded in the deck. Keynote and Google Slides ignore embedded fonts: "
                  "install the font files first."]
    return "\n".join(lines) + "\n"


def cmd_approve(project: Path, n: int | None, replace: bool) -> int:
    approved = gate_recorded(project, "G4m")
    if not approved:
        fail(EXIT_FAIL, "masters approve needs the owner's approval of the masters (G4m) recorded first, with their PowerPoint answer when there is a deck: "
                        "brand-creator state --record G4m \"<the directions approved>; PowerPoint: <their answer>\"")
    rnd = masters_round(project, n)
    root = project / "rounds" / f"r{rnd}"
    board = f"rounds/r{rnd}/board.html"
    for why in (report_problem(project, "board-lint", f"brand-creator board-lint {board}", page=board),
                report_problem(project, "masters", f"brand-creator masters check --round {rnd}", round=rnd)):
        if why:
            fail(EXIT_FAIL, f"masters approve copies checked masters only: {why}")
    m = mastersdata.load_manifest(root / mastersdata.MASTERS_FILE)
    html = [root / e.file for e in m.entries if e.file.lower().endswith((".html", ".htm"))]
    reached, _missing = closure.static_closure(root, html)
    out = closure.escapes(root, reached)
    if out:
        fail(EXIT_FAIL, f"a master loads a file outside the round, which a copy into {APPROVED_DIR}/ would break ({'; '.join(out[:5])}): "
                        "put that file in the round (or its masters) and point to it there, then check and approve again")
    pngs = {root / "png" / (Path(e.file).stem + ".png") for e in m.entries if e.kind in mastersdata.CANVAS_KINDS and e.file.lower().endswith((".html", ".htm"))}
    files = sorted({(root / e.file).resolve() for e in m.entries} | reached | {p.resolve() for p in pngs if p.is_file()}, key=lambda p: p.as_posix())
    dest = project / APPROVED_DIR
    if dest.exists() and any(p.is_file() for p in dest.rglob("*")):
        if not replace:
            fail(EXIT_FAIL, f"{APPROVED_DIR}/ holds approved masters already: run masters approve --replace (it moves them to removed-<date>/assets-masters/ first)")
        base = project / f"removed-{today()}"
        k, to = 1, base / "assets-masters"
        while to.exists():
            k += 1
            to = base / f"assets-masters-{k}"
        to.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(dest), str(to))
        print(f"moved the masters approved before to {to.relative_to(project)}/")
    for f in files:
        d = dest / f.relative_to(root.resolve())
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(f, d)
    doc = {"round": rnd, "approved": approved, "entries": [{k: v for k, v in (("file", e.file), ("kind", e.kind), ("canvas", list(e.canvas) if e.canvas else None),
                                                                              ("direction", e.direction), ("note", e.note)) if v is not None} for e in m.entries],
           "copy_rules": m.copy_rules, "builder": m.builder}
    (dest / mastersdata.MASTERS_FILE).write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (dest / "README.md").write_text(readme_text(rnd, approved, m, root), encoding="utf-8")
    print(f"approved {len(m.entries)} master(s) of round {rnd} into {APPROVED_DIR}/ ({len(files)} file(s), with README.md and masters.json)")
    print("next: brand-creator kit build --yes (the kit carries assets/masters/), and the book's masters block when the book shows them")
    return 0


def cmd_embed(deck: Path, fonts: list[str], out: str | None) -> int:
    if not deck.is_file():
        fail(EXIT_USAGE, f"{deck} not found")
    files = []
    for f in fonts:
        p = Path(f)
        if not p.is_file():
            fail(EXIT_USAGE, f"--font {f}: not found")
        files.append((p.name, p.read_bytes()))
    try:
        data, families = fontembed.embed(deck.read_bytes(), files)
    except fontembed.EmbedError as e:
        fail(EXIT_FAIL, f"nothing was embedded: {e}")
    dest = Path(out) if out else deck
    dest.write_bytes(data)
    print(f"{dest}: {len(files)} font file(s) embedded ({', '.join(families)}); PowerPoint shows them without installing them, Keynote and Google Slides do not")
    return 0


def cmd_pdf_normalise(src: Path, out: str | None) -> int:
    if not src.is_file():
        fail(EXIT_USAGE, f"{src} not found")
    data = src.read_bytes()
    if not data.startswith(b"%PDF-"):
        fail(EXIT_USAGE, f"{src} is not a PDF (it does not start with %PDF-)")
    fixed = determinism.normalise_pdf(data)
    dest = Path(out) if out else src
    if dest != src or fixed != data:
        dest.write_bytes(fixed)
    print(f"{dest}: dates and /ID fixed" + ("" if fixed != data else " (they were already)"))
    return 0


def main() -> int:
    ap = Parser(prog="brand-creator masters", description=__doc__, formatter_class=__import__("argparse").RawDescriptionHelpFormatter)
    subs = ap.add_subparsers(dest="cmd", required=True)
    c = subs.add_parser("check", help="render and check every master of the masters round")
    add_project_arg(c)
    c.add_argument("--round", type=int, help="the masters round (default: the latest masters board)")
    ap_ = subs.add_parser("approve", help="after G4m: copy the round's masters into assets/masters/")
    add_project_arg(ap_)
    ap_.add_argument("--round", type=int, help="the masters round (default: the latest masters board)")
    ap_.add_argument("--replace", action="store_true", help="assets/masters/ holds approved masters: move them to removed-<date>/assets-masters/ first")
    e = subs.add_parser("embed-fonts", help="embed TrueType fonts in a PowerPoint deck")
    e.add_argument("deck")
    e.add_argument("--font", action="append", required=True, metavar="FILE.ttf", help="a font file (repeatable)")
    e.add_argument("--out", help="write here instead of in place")
    p = subs.add_parser("pdf", help="brand-creator pdf normalise <file.pdf>")
    p.add_argument("action", choices=["normalise"])
    p.add_argument("file")
    p.add_argument("--out", help="write here instead of in place")
    a = ap.parse_args()
    if a.cmd == "embed-fonts":
        return cmd_embed(Path(a.deck), a.font, a.out)
    if a.cmd == "pdf":
        return cmd_pdf_normalise(Path(a.file), a.out)
    if a.cmd == "approve":
        return cmd_approve(find_project(a.project), a.round, a.replace)
    return cmd_check(find_project(a.project), a.round)


main_guard(main)
