"""Masters: the ads and decks of a brand, made in a masters round (data-board="masters", a round after G4) and approved at G4m.

A masters round holds masters.json, the manifest every masters tool reads:

    {"entries": [{"file": "reklama/kalendarz-1080x1350.html", "kind": "ad", "canvas": [1080, 1350], "direction": "kalendarz", "note": "..."}, ...],
     "copy_rules": ["no amounts or names in ads", ...], "builder": "node rounds/r5/build.mjs"}

kind is one of KINDS. canvas ([width, height] in CSS px) is required for an ad and a slide, and refused for the others. file is a path inside the
round, written with forward slashes. An HTML master declares its canvas too: <meta name="masters-canvas" content="WxH">.

load_manifest(path) reads it and lists every problem. board_rows(rep, project, rnd, page) adds the masters:* rows of board-lint.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import NamedTuple

MASTERS_FILE = "masters.json"
KINDS = ("ad", "slide", "deck-html", "deck-pdf", "deck-pptx", "image", "font")
CANVAS_KINDS = ("ad", "slide")
CANVAS_META = re.compile(r"""<meta\s+name=["']masters-canvas["']\s+content=["'](\d+)x(\d+)["']""", re.I)


class Entry(NamedTuple):
    file: str
    kind: str
    canvas: tuple[int, int] | None
    direction: str | None
    note: str | None


class Manifest(NamedTuple):
    entries: list[Entry]
    copy_rules: list[str]
    builder: str | None
    problems: list[str]


def load_manifest(path: Path) -> Manifest:
    """The manifest at path, with every problem found (an empty list: sound). A file that cannot be read is one problem."""
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return Manifest([], [], None, [f"{Path(path).name} cannot be read as JSON: {e}"])
    if not isinstance(doc, dict) or not isinstance(doc.get("entries"), list):
        return Manifest([], [], None, [f"{Path(path).name} needs an object with an \"entries\" list"])
    entries, problems = [], []
    for i, e in enumerate(doc["entries"], 1):
        if not isinstance(e, dict) or not isinstance(e.get("file"), str) or not e["file"].strip():
            problems.append(f"entry {i}: no \"file\" (a path inside the round)")
            continue
        f, kind = e["file"].strip(), e.get("kind")
        if f.startswith("/") or ".." in f.split("/") or "\\" in f:
            problems.append(f"{f}: the file must be a path inside the round, with forward slashes")
            continue
        if kind not in KINDS:
            problems.append(f"{f}: kind {kind!r} is not one of {', '.join(KINDS)}")
            continue
        canvas = e.get("canvas")
        if kind in CANVAS_KINDS:
            if not (isinstance(canvas, list) and len(canvas) == 2 and all(isinstance(x, int) and x > 0 for x in canvas)):
                problems.append(f"{f}: an {kind} needs a canvas [width, height] in px")
                continue
            canvas = (canvas[0], canvas[1])
        elif canvas is not None:
            problems.append(f"{f}: a {kind} has no canvas (only an ad and a slide do)")
            continue
        direction = e.get("direction") if isinstance(e.get("direction"), str) and e["direction"].strip() else None
        note = e.get("note") if isinstance(e.get("note"), str) else None
        entries.append(Entry(f, kind, canvas, direction, note))
    stems: dict[str, str] = {}
    for e in entries:   # masters check names each ad's and slide's picture png/<file name>.png, so two of one name would share one picture
        if e.kind in CANVAS_KINDS and e.file.lower().endswith((".html", ".htm")):
            stem = Path(e.file).stem
            if stem in stems:
                problems.append(f"{stems[stem]} and {e.file} share the file name {stem}: their pictures would both be png/{stem}.png; rename one")
            stems.setdefault(stem, e.file)
    rules = [r for r in doc.get("copy_rules", []) if isinstance(r, str) and r.strip()] if isinstance(doc.get("copy_rules"), list) else []
    builder = doc.get("builder") if isinstance(doc.get("builder"), str) and doc["builder"].strip() else None
    return Manifest(entries, rules, builder, problems)


def declared_canvas(html: str) -> tuple[int, int] | None:
    m = CANVAS_META.search(html)
    return (int(m.group(1)), int(m.group(2))) if m else None


def first_masters(project: Path, rnd: int) -> bool:
    """No earlier round holds a masters board."""
    from _common import list_rounds
    from boardpage import page_kind, read_page
    return not any(page_kind(read_page(d / "board.html")) == "masters" for n, d in list_rounds(project) if n < rnd)


def board_rows(rep, project: Path, rnd: int) -> Manifest | None:
    """masters:gate (G4 recorded), masters:manifest, masters:files, masters:canvas-size, masters:directions (two or more on the first masters board)."""
    from _common import gate_recorded
    root = Path(project) / "rounds" / f"r{rnd}"
    if gate_recorded(project, "G4"):
        rep.add("masters:gate", "pass", "a masters round comes after G4", detail="G4 is recorded")
    else:
        rep.add("masters:gate", "fail", "a masters round comes after G4", detail="G4 (the system rules) is not recorded: masters are built from the approved rules")
    mf = root / MASTERS_FILE
    if not mf.is_file():
        rep.add("masters:manifest", "fail", "the round's masters.json", detail=f"rounds/r{rnd}/{MASTERS_FILE} does not exist: it lists every master (file, kind, canvas, direction)")
        return None
    m = load_manifest(mf)
    if m.problems or not m.entries:
        rep.add("masters:manifest", "fail", "the round's masters.json", detail="; ".join(m.problems[:5]) or "no entries")
        return m
    rep.add("masters:manifest", "pass", "the round's masters.json", detail=f"{len(m.entries)} master(s)")
    missing = [e.file for e in m.entries if not (root / e.file).is_file()]
    rep.add("masters:files", "fail" if missing else "pass", "every master listed exists",
            detail=("missing: " + ", ".join(missing[:8])) if missing else f"{len(m.entries)} file(s) present")
    bad = []
    for e in m.entries:
        if e.kind in CANVAS_KINDS and e.file.lower().endswith((".html", ".htm")) and (root / e.file).is_file():
            got = declared_canvas((root / e.file).read_text(encoding="utf-8", errors="replace"))
            if got is None:
                bad.append(f"{e.file}: no <meta name=\"masters-canvas\" content=\"WxH\">")
            elif got != e.canvas:
                bad.append(f"{e.file}: declares {got[0]}x{got[1]}, the manifest says {e.canvas[0]}x{e.canvas[1]}")
    rep.add("masters:canvas-size", "fail" if bad else "pass", "each HTML master declares the canvas its entry names",
            detail="; ".join(bad[:5]) if bad else "match")
    dirs = sorted({e.direction for e in m.entries if e.direction})
    if first_masters(project, rnd) and len(dirs) < 2:
        rep.add("masters:directions", "fail", "the first masters board shows directions",
                detail=f"{len(dirs)} direction(s) ({', '.join(dirs) or 'none'}): the first masters board shows two or three, so the owner picks rather than reacts to one")
    else:
        rep.add("masters:directions", "pass", "the first masters board shows directions", detail=f"{len(dirs)} direction(s): {', '.join(dirs) or 'none named'}")
    return m
