"""The closure of a round: what its boards show (scripts/lib/closure.py), for freeze and cleanup --history."""
from __future__ import annotations

import unicodedata
from pathlib import Path

import helpers  # noqa: F401  (puts scripts/lib on sys.path)
import closure


def w(root: Path, rel: str, data: str | bytes = "x") -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data.encode() if isinstance(data, str) else data)
    return p


def rels(root: Path, paths) -> list[str]:
    return sorted(unicodedata.normalize("NFC", p.relative_to(root).as_posix()) for p in paths)


def test_the_closure_follows_html_css_and_svg_references_and_stays_inside_the_round(tmp_path):
    root = tmp_path / "r3"
    w(tmp_path, "outside.png")
    w(root, "board.html", '<link rel="stylesheet" href="style.css"><img src="a.png"><img src="pic.svg"><img src="../outside.png">')
    w(root, "style.css", "body { background: url('bg.png') }")
    w(root, "pic.svg", '<svg xmlns="http://www.w3.org/2000/svg"><image href="inner.png"/></svg>')
    for f in ("a.png", "bg.png", "inner.png", "unused.png"):
        w(root, f)
    kept, missing = closure.static_closure(root, closure.starting_pages(root))
    assert rels(root, kept) == ["a.png", "bg.png", "board.html", "inner.png", "pic.svg", "style.css"]
    assert missing == []


def test_srcset_and_a_js_import_are_followed(tmp_path):
    root = tmp_path / "r3"
    w(root, "d/index.html", '<img srcset="s1.png 1x, s2.png 2x"><script type="module" src="app.mjs"></script>')
    w(root, "d/app.mjs", "import { a } from './lib.mjs';\nconsole.log(a)")
    for f in ("d/s1.png", "d/s2.png", "d/lib.mjs"):
        w(root, f)
    kept, _ = closure.static_closure(root, closure.starting_pages(root))
    assert rels(root, kept) == ["d/app.mjs", "d/index.html", "d/lib.mjs", "d/s1.png", "d/s2.png"]


def test_urls_with_a_scheme_a_query_or_a_fragment_are_handled(tmp_path):
    root = tmp_path / "r3"
    w(root, "board.html", '<a href="https://example.com/x.png">x</a><img src="data:image/png;base64,AAAA"><img src="a.png?v=2#top">'
                          '<img src="with%20space.png"><a href="mailto:a@b.c">m</a><a href="#local">l</a>')
    w(root, "a.png")
    w(root, "with space.png")
    kept, missing = closure.static_closure(root, closure.starting_pages(root))
    assert rels(root, kept) == ["a.png", "board.html", "with space.png"]
    assert missing == []


def test_a_reference_to_no_file_is_listed_not_dropped(tmp_path):
    root = tmp_path / "r3"
    w(root, "board.html", '<img src="gone.png">')
    kept, missing = closure.static_closure(root, closure.starting_pages(root))
    assert rels(root, kept) == ["board.html"]
    assert missing == ["board.html: gone.png"]


def test_a_polish_name_decomposed_on_disk_is_the_same_file(tmp_path):
    root = tmp_path / "r3"
    w(root, unicodedata.normalize("NFD", "ża.png"))
    w(root, "board.html", '<img src="ża.png">')
    kept, missing = closure.static_closure(root, closure.starting_pages(root))
    assert rels(root, kept) == ["board.html", "ża.png"]
    assert missing == []


def test_starting_pages_are_the_board_pages_anywhere_and_the_top_level_notes(tmp_path):
    root = tmp_path / "r3"
    for f in ("board.html", "a/index.html", "a/b/preview.html", "review.html", "NOTES.md", "a/deep.md", "a/other.html"):
        w(root, f)
    assert rels(root, closure.starting_pages(root)) == ["NOTES.md", "a/b/preview.html", "a/index.html", "board.html", "review.html"]


def test_builders_skip_pycache_and_node_modules(tmp_path):
    root = tmp_path / "r3"
    for f in ("build.py", "a/render.mjs", "a/x.js", "go.sh", "__pycache__/build.cpython-313.pyc", "node_modules/p/index.js",
              "a/__pycache__/m.py", "shot.png"):
        w(root, f)
    assert rels(root, closure.builders(root)) == ["a/render.mjs", "a/x.js", "build.py", "go.sh"]
