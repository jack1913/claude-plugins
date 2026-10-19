"""mark_lint: a mark, lockup, wordmark or favicon SVG must be pure vector shapes.

Fails on <text>, <tspan>, <textPath>, font-family, @font-face, an external href (anything that is not a '#fragment'
or a data: URI), <script> and <foreignObject>. Outline text first (scripts/outline_glyphs.py in a later stage).
Rule source: GAP S2-P6-t5 / S2-P10-sr1 / S4-19 in the plan.
"""
from __future__ import annotations

import re
from pathlib import Path

_COMMENT = re.compile(r"<!--.*?-->", re.S)
_CDATA = re.compile(r"<!\[CDATA\[(.*?)\]\]>", re.S)
_TAGS = [
    (re.compile(r"<\s*text\b", re.I), "<text> element (outline the glyphs; no live text in marks)"),
    (re.compile(r"<\s*tspan\b", re.I), "<tspan> element"),
    (re.compile(r"<\s*textPath\b", re.I), "<textPath> element"),
    (re.compile(r"font-family\s*[:=]", re.I), "font-family"),
    (re.compile(r"@font-face", re.I), "@font-face"),
    (re.compile(r"<\s*script\b", re.I), "<script> element"),
    (re.compile(r"<\s*foreignObject\b", re.I), "<foreignObject> element"),
]
_HREF = re.compile(r"""(?:xlink:)?href\s*=\s*(["'])(.*?)\1""", re.I | re.S)
_CSS_URL = re.compile(r"url\(\s*(['\"]?)(?!#|data:)([^)'\"]+)\1\s*\)", re.I)
_IMPORT = re.compile(r"@import\b", re.I)


def lint_svg_text(text: str) -> list[str]:
    """Problems found in one SVG document (empty list = clean)."""
    body = _CDATA.sub(lambda m: m.group(1), _COMMENT.sub("", text))
    problems = []
    for rx, msg in _TAGS:
        if rx.search(body):
            problems.append(msg)
    for m in _HREF.finditer(body):
        v = m.group(2).strip()
        if not v.startswith("#") and not v.lower().startswith("data:"):
            problems.append(f"external href {v[:60]!r}")
    for m in _CSS_URL.finditer(body):
        problems.append(f"external url() {m.group(2).strip()[:60]!r}")
    if _IMPORT.search(body):
        problems.append("@import")
    seen, out = set(), []
    for p in problems:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


def lint_svg_file(path: Path) -> list[str]:
    return lint_svg_text(path.read_text(encoding="utf-8", errors="replace"))


def svg_files_under_assets(project: Path) -> list[Path]:
    """Every *.svg under <project>/assets/, skipping folders whose name starts with '_' (reports, scratch)."""
    root = project / "assets"
    if not root.is_dir():
        return []
    return sorted(p for p in root.rglob("*.svg")
                  if not any(part.startswith("_") for part in p.relative_to(root).parts[:-1]))
