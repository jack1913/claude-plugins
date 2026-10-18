"""`brand-creator check --cascade "<old value or phrase>"`: every project artefact is searched for the old value, and any current file that
still holds it fails the check.

Searched: every text file of the project (book sources and book.html, README, token sources and built tokens, text assets, templates in the
project, ADOPTION.md, LAUNCH.md, BRAND.md, DESIGN.md, the applied skill under .claude/skills/), PDFs through pdftotext (a PDF whose text is
outlines holds no text to search; the print PDFs say so), and the files named by `tools/cascade.json` ("also": paths, relative to the project, of
documents outside it such as a parent brand's README, read only), by `--also`, and by the `parent_docs` list of the family-check block of
FAMILY.md (relative to FAMILY.md). Skipped on purpose, and said so: history/, decisions/, BRAND-STATE.md, DECISIONS.md (they record what was
decided, old values included), earlier rounds, removed-*/, assets/_checks/ and assets/manifest.json (generated records).

Lines that record what a product repository holds today (ADOPTION.md rows, the rename list of LAUNCH.md, and the `find` fields of adoption.json)
are the adoption work list, not leftovers: they are counted apart and make a warning, never a failure.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import adoptdata as ad
from _common import EXIT_USAGE, fail, rel

TEXT_EXT = {".md", ".html", ".htm", ".css", ".json", ".js", ".mjs", ".txt", ".yml", ".yaml", ".svg", ".xml", ".swift", ".toml", ".sh", ".py", ".tpl",
            ".csv", ".plist", ".ini"}
SKIP_DIRS = {"history", "node_modules", ".git", "_checks", "decisions"}   # `_build/` is searched: its HTML is the only text layer of an image made from a CLI value
SKIP_FILES = {"BRAND-STATE.md", "DECISIONS.md", "manifest.json"}
CONFIG = "tools/cascade.json"
BINARY_EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".ico", ".icns", ".bmp", ".zip", ".woff", ".woff2", ".ttf", ".otf", ".car", ".mp4", ".webm"}


def project_files(project: Path, latest: int | None):
    for p in sorted(project.rglob("*")):
        if not p.is_file() or p.name in SKIP_FILES:
            continue
        parts = p.relative_to(project).parts
        if any(d in SKIP_DIRS or d.startswith("removed") for d in parts[:-1]):
            continue
        if parts[0] == "rounds" and len(parts) > 1 and re.fullmatch(r"r\d+", parts[1]) and int(parts[1][1:]) != latest:
            continue
        yield p


def load_config(project: Path) -> list[str]:
    f = project / CONFIG
    if not f.is_file():
        return []
    try:
        doc = json.loads(f.read_text(encoding="utf-8"))
    except ValueError as e:
        fail(EXIT_USAGE, f"{CONFIG} is not valid JSON: {e}")
    if not isinstance(doc, dict) or set(doc) - {"schema", "also"}:
        fail(EXIT_USAGE, f"{CONFIG}: unknown key(s) {sorted(set(doc) - {'schema', 'also'}) if isinstance(doc, dict) else doc!r} (known: schema, also)")
    if doc.get("schema") != 1:
        fail(EXIT_USAGE, f"{CONFIG}: schema must be 1")
    also = doc.get("also", [])
    if not isinstance(also, list) or not all(isinstance(x, str) and x.strip() for x in also):
        fail(EXIT_USAGE, f"{CONFIG}: `also` must be a list of paths")
    return also


def family_parent_docs(project: Path) -> list[str]:
    """`parent_docs` of the family-check block of FAMILY.md, as paths relative to the project."""
    f = project / "FAMILY.md"
    if not f.is_file():
        return []
    m = re.search(r"```json family-check\n(.*?)```", f.read_text(encoding="utf-8"), re.S)
    if not m:
        return []
    try:
        docs = json.loads(m.group(1)).get("parent_docs", [])
    except ValueError:
        return []   # family-check reports a broken block; the cascade reads only this one key
    if not isinstance(docs, list) or not all(isinstance(x, str) for x in docs):
        fail(EXIT_USAGE, "FAMILY.md: `parent_docs` of the family-check block must be a list of paths (relative to FAMILY.md)")
    return [d for d in docs]


def also_files(project: Path, spec: str, base: Path) -> tuple[list[Path], str | None]:
    """-> (files, problem). A path that does not exist is a problem: a configured document that is gone must not pass silently."""
    p = (base / spec).expanduser()
    if p.is_file():
        return [p], None
    if p.is_dir():
        out = [q for q in sorted(p.rglob("*")) if q.is_file() and q.suffix.lower() in TEXT_EXT
               and not any(d in SKIP_DIRS or d.startswith(".") for d in q.relative_to(p).parts[:-1])]
        return out, None
    return [], f"{spec} (named for the cascade) does not exist"


def pdf_text(f: Path) -> str | None:
    exe = shutil.which("pdftotext")
    if not exe:
        return None
    cp = subprocess.run([exe, "-q", str(f), "-"], capture_output=True, timeout=120)
    return cp.stdout.decode("utf-8", "replace") if cp.returncode == 0 else ""


def adoption_strings(doc, path="adoption.json"):
    """(location, text) pairs of adoption.json without the fields that hold the old values of the product repositories."""
    if isinstance(doc, dict):
        for k, v in doc.items():
            if k in ad.TARGET_KEYS:
                continue
            yield from adoption_strings(v, f"{path}.{k}")
    elif isinstance(doc, list):
        for i, v in enumerate(doc):
            yield from adoption_strings(v, f"{path}[{i}]")
    elif isinstance(doc, str):
        yield path, doc


def run(project: Path, olds: list[str], ignore_case: bool, latest: int | None, also_cli: list[str]) -> list[dict]:
    """Result rows for `Report.add` (keys id, status, label, detail, plus extras)."""
    flags = re.I if ignore_case else 0
    rows: list[dict] = []
    texts: list[tuple[str, str, bool]] = []   # (shown location prefix, text, is_outside)
    files_read: set[str] = set()
    pdfs, outlined, binaries = [], [], 0
    for f in project_files(project, latest):
        r = rel(project, f)
        ext = f.suffix.lower()
        if f.name == ad.FILE and len(f.relative_to(project).parts) == 1:
            try:
                files_read.add(r)
                for loc, t in adoption_strings(json.loads(f.read_text(encoding="utf-8"))):
                    texts.append((loc, t, False))
            except ValueError:
                texts.append((r, f.read_text(encoding="utf-8", errors="replace"), False))
            continue
        if ext in TEXT_EXT:
            files_read.add(r)
            texts.append((r, f.read_text(encoding="utf-8", errors="replace"), False))
        elif ext == ".pdf":
            (outlined if r.startswith("assets/print/") else pdfs).append(f)
        elif ext in BINARY_EXT:
            binaries += 1
    searched_pdfs = 0
    if pdfs:
        if not shutil.which("pdftotext"):
            rows.append({"id": "cascade:pdf", "status": "skipped", "label": "PDFs searched",
                         "detail": f"not verified: {len(pdfs)} PDF(s) in the project and pdftotext (poppler) is not installed; brand-creator prereq --for print"})
        else:
            for f in pdfs:
                t = pdf_text(f)
                texts.append((rel(project, f) + " (pdf text)", t or "", False))
                files_read.add(rel(project, f))
                searched_pdfs += 1
    extra_problems = []
    specs = [(s, project) for s in also_cli] + [(s, project) for s in load_config(project)] + [(s, project / "FAMILY.md") for s in family_parent_docs(project)]
    n_also = 0
    for spec, base in specs:
        basedir = base if base.is_dir() else base.parent
        files, problem = also_files(project, spec, basedir)
        if problem:
            extra_problems.append(problem)
            continue
        for f in files:
            n_also += 1
            texts.append((f"also:{spec}" + ("" if f == (basedir / spec) else "/" + f.relative_to(basedir / spec).as_posix()), f.read_text(encoding="utf-8", errors="replace"), True))
    for pr in extra_problems:
        rows.append({"id": "cascade:also", "status": "fail", "label": "documents named for the cascade exist", "detail": pr})
    note = f"history/, decisions, BRAND-STATE.md, DECISIONS.md, earlier rounds, removed-*/ and generated records (assets/_checks/) are skipped on purpose; the HTML in _build/ folders is searched; {binaries} binary file(s) are not searched"
    if outlined:
        note += f", nor {len(outlined)} print PDF(s) (their text is outlines: the sources are what was searched)"
    rows.append({"id": "cascade:scope", "status": "info", "label": "what the cascade searched and left out", "detail": note + " (an image or a zip is rebuilt from sources that were searched)"})
    for old in olds:
        rx = re.compile(re.escape(old), flags)
        hits, recorded = [], 0
        for loc, text, _outside in texts:
            for i, line in enumerate(text.splitlines(), 1):
                if rx.search(line):
                    if ad.MARK in line:
                        recorded += 1
                    else:
                        hits.append(f"{loc}:{i}" if not loc.startswith("adoption.json") else loc)
        n_files = len(files_read)
        detail = (f"{len(hits)} leftover(s): " + ", ".join(hits[:8]) + (" ..." if len(hits) > 8 else "")) if hits else \
            f"not found in {n_files} current file(s)" + (f", {searched_pdfs} PDF(s) read as text" if searched_pdfs else "") + (f", {n_also} file(s) outside the project" if n_also else "")
        status = "fail" if hits else "pass"
        if recorded and not hits:
            status = "warn"
        if recorded:
            detail += (f"; {recorded} line(s) of ADOPTION.md or LAUNCH.md record what a product repository still holds: that is the adoption work list, "
                       "not a leftover here (`brand-creator adoption survey` refreshes it)")
        rows.append({"id": f"cascade:{old[:40]}", "status": status, "label": "old value no longer appears", "detail": detail, "hits": hits, "recorded": recorded})
    return rows
