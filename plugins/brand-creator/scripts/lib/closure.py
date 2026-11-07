"""What a round's boards show: the files a freeze keeps, and what cleanup --history leaves in a frozen round.

starting_pages(root)  every board.html, index.html, preview.html and review.html under root, and the *.md directly in root.
static_closure(root, starts)  the files those pages reach through src, href, poster, data-src, xlink:href, srcset, CSS url() and
                      JS import, followed through HTML, CSS, SVG and JS files, only inside root; plus the references that point
                      at no file ("<page>: <ref>"). A script that builds a path is not read here: the browser pass
                      (render.mjs page-requests, browser_closure) sees those.
builders(root)        the scripts that built the round: *.py, *.mjs, *.js, *.sh, never under __pycache__ or node_modules.

Paths are compared after Unicode NFC, so a name decomposed on disk (macOS) is the same file as its precomposed reference.
"""
from __future__ import annotations

import posixpath
import re
import unicodedata
import urllib.parse
from pathlib import Path

START_NAMES = ("board.html", "index.html", "preview.html", "review.html")
FOLLOWED = (".html", ".htm", ".css", ".svg", ".js", ".mjs")
BUILDER_SUFFIXES = (".py", ".mjs", ".js", ".sh")
SKIPPED_DIRS = ("__pycache__", "node_modules")
ATTR = re.compile(r"""\b(?:src|href|poster|data-src|xlink:href)\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.I)
SRCSET = re.compile(r"""\bsrcset\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.I)
CSS_URL = re.compile(r"""url\(\s*(?:"([^"]*)"|'([^']*)'|([^)'"\s]+))\s*\)""", re.I)
JS_IMPORT = re.compile(r"""(?:\bimport\s*(?:[\w*{}\s,]+\s*from\s*)?|\bimport\s*\(\s*)["']([^"']+)["']""")
SCHEME = re.compile(r"^(?:[a-z][a-z0-9+.-]*:|//|#)", re.I)


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def _walk(root: Path):
    for p in sorted(root.rglob("*")):
        if p.is_file() and not any(part in SKIPPED_DIRS for part in p.relative_to(root).parts):
            yield p


def starting_pages(root: Path) -> list[Path]:
    """The pages a frozen round is read through, sorted by their path."""
    starts = [p for p in _walk(root) if p.name in START_NAMES or (p.parent == root and p.suffix.lower() == ".md")]
    return sorted(starts, key=lambda p: nfc(p.relative_to(root).as_posix()))


def builders(root: Path) -> set[Path]:
    """The scripts in the round (they rebuild what the boards show)."""
    return {p for p in _walk(root) if p.suffix.lower() in BUILDER_SUFFIXES}


def references(text: str, suffix: str) -> list[str]:
    """The local references a file of this kind makes, in order, as written (schemes, fragments and queries dropped)."""
    found: list[str] = []
    if suffix in (".html", ".htm", ".svg"):
        found += [a or b for a, b in ATTR.findall(text)]
        for a, b in SRCSET.findall(text):
            found += [part.strip().split()[0] for part in (a or b).split(",") if part.strip()]
    if suffix in (".html", ".htm", ".svg", ".css"):
        found += [a or b or c for a, b, c in CSS_URL.findall(text)]
    if suffix in (".html", ".htm", ".js", ".mjs"):
        found += JS_IMPORT.findall(text)
    out = []
    for ref in found:
        ref = ref.strip()
        if not ref or SCHEME.match(ref):
            continue
        ref = urllib.parse.unquote(ref.split("#", 1)[0].split("?", 1)[0])
        if ref:
            out.append(ref)
    return out


def _index(root: Path) -> dict[str, Path]:
    """Every file under root by its NFC path relative to root."""
    return {nfc(p.relative_to(root).as_posix()): p for p in root.rglob("*") if p.is_file()}


def static_closure(root: Path, starts: list[Path]) -> tuple[set[Path], list[str]]:
    """The files the starting pages reach, followed through HTML, CSS, SVG and JS, inside root; and the references to no file."""
    root = root.resolve()
    index = _index(root)
    kept: set[Path] = set()
    missing: list[str] = []
    todo = [p.resolve() for p in starts]
    while todo:
        p = todo.pop(0)
        if p in kept:
            continue
        kept.add(p)
        suffix = p.suffix.lower()
        if suffix not in FOLLOWED:
            continue
        here = nfc(p.relative_to(root).as_posix())
        for ref in references(p.read_text(encoding="utf-8", errors="replace"), suffix):
            target = posixpath.normpath(posixpath.join(posixpath.dirname(here), ref)) if not ref.startswith("/") else None
            if target is None or target.startswith("../") or target == "..":
                continue  # outside the round: never part of its closure
            hit = index.get(nfc(target))
            if hit is None:
                if f"{here}: {ref}" not in missing:
                    missing.append(f"{here}: {ref}")
            elif hit.resolve() not in kept:
                todo.append(hit.resolve())
    return kept, missing


PAGE_REQUESTS_TIMEOUT_S = 600   # every starting page loaded, settled and walked down once


def browser_closure(root: Path, starts: list[Path]) -> tuple[set[Path], list[str]]:
    """The files the starting pages request when loaded in the plugin's Chromium (render.mjs page-requests): paths a script builds
    included. Second item: the requests that found no file, as "<page>: <path>". Raises CliError(EXIT_CANNOT) when node, the data
    directory or Chromium is missing: the caller decides what that means, never this function."""
    import json
    import os
    import shutil
    import subprocess
    import tempfile
    from _common import EXIT_CANNOT, fail, plugin_root
    data = os.environ.get("BRAND_CREATOR_DATA", "").strip()
    if not data:
        fail(EXIT_CANNOT, "the browser pass needs a set-up data directory (BRAND_CREATOR_DATA): run brand-creator setup")
    node = shutil.which("node")
    if not node:
        fail(EXIT_CANNOT, "the browser pass needs node (Node 22 or newer): run brand-creator prereq, then brand-creator setup")
    root = root.resolve()
    pages = [nfc(p.resolve().relative_to(root).as_posix()) for p in starts if p.suffix.lower() in (".html", ".htm")]
    index = _index(root)
    if not pages:
        return set(), []
    with tempfile.TemporaryDirectory(prefix="bc-page-requests-") as tmp:
        out = Path(tmp) / "requests.json"
        cmd = [node, str(plugin_root() / "scripts" / "render.mjs"), "page-requests", "--root", str(root), "--out", str(out)]
        for p in pages:
            cmd += ["--page", p]
        try:
            cp = subprocess.run(cmd, capture_output=True, timeout=PAGE_REQUESTS_TIMEOUT_S, env={**os.environ, "BRAND_CREATOR_DATA": data})
        except subprocess.TimeoutExpired:
            fail(EXIT_CANNOT, f"the browser pass timed out after {PAGE_REQUESTS_TIMEOUT_S}s")
        if cp.returncode != 0:
            why = cp.stderr.decode("utf-8", "replace").strip().removeprefix("error: ")
            fail(EXIT_CANNOT, f"the browser pass could not run: {why or f'render.mjs page-requests exited {cp.returncode}'}")
        doc = json.loads(out.read_text(encoding="utf-8"))
    seen: set[Path] = set()
    missing: list[str] = []
    for page in pages:
        got = doc["pages"].get(page, {})
        for rel in got.get("requested", []):
            hit = index.get(nfc(rel))
            if hit is not None:
                seen.add(hit.resolve())
        for rel in got.get("missing", []):
            if f"{page}: {rel}" not in missing:
                missing.append(f"{page}: {rel}")
    return seen, missing
