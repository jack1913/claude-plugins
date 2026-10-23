#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator book-lint [BOOK]: the gate for a brand book, generated or hand-authored.

Checks (each a row in assets/_checks/book-lint.json): duplicate ids and broken anchors; network references, scripts and anything
the book needs at read time that is not inline; scratch words, round language outside the history chapter, the project's FORBIDDEN
words; status words ("coming soon", "launching", "available", "now live" ...) not backed by a FACTS.md value; per-language key
parity for content_languages; mark_lint on every embedded or linked mark SVG; required chapters for the tier; the edition and the
APPROVED stamp against BRAND-STATE.md; computed counts, typed counts and quoted facts against the data; manifest accounting (every
manifest row is in the files chapter); legal disclosures from FACTS.md; leftover choice scaffolding; the motion chapter's replay:
nothing moves under prefers-reduced-motion, the replay starts again from its two checkboxes (which the keyboard reaches) and steps through the
stills of motion/frames/ (rows motion:reduced, motion:replay, motion:stills; info when the book has no replay, a failure when a generated book
has none of stills that exist); a selector the lint cannot evaluate, or a rule inside @layer, @scope, @container or @supports, is named in the row it affects.
--self-consistency adds the book's obedience to its own rules: CSS durations and delays within the motion tokens (a replay may also
use its own length and four times it, in a rule that reaches that replay and nothing else), no font size under the book's minimum label size, every colour one of the brand's tokens.
BOOK defaults to `output` in book/book.json, else book.html. Exit 0 pass, 1 a rule failed, 2 usage, 3 not verified.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "booklib"))
import bookdata  # noqa: E402
import booklint  # noqa: E402
from _common import Parser, add_project_arg, confine, fail, find_project, main_guard, EXIT_USAGE  # noqa: E402


def main() -> int:
    ap = Parser(prog="brand-creator book-lint", description=__doc__, formatter_class=__import__("argparse").RawDescriptionHelpFormatter)
    add_project_arg(ap)
    ap.add_argument("book", nargs="?", help="the book (default: book.html or `output` in book/book.json)")
    ap.add_argument("--self-consistency", action="store_true", help="also check the book against its own motion, size and colour rules")
    ap.add_argument("--allow-variants", action="store_true", help="report open choice scaffolding as a warning (a review build)")
    a = ap.parse_args()
    project = find_project(a.project)
    cfg, _src = bookdata.load_config(project)
    target = a.book or cfg["output"]
    f = confine(project, target, what="book")
    if not f.is_file():
        fail(EXIT_USAGE, f"book not found: {target}")
    view = bookdata.state_view(project)
    doc, _tp = bookdata.tokens(project)
    facts = bookdata.facts(project)
    if f.suffix.lower() not in (".html", ".htm"):
        fail(EXIT_USAGE, f"book-lint reads an HTML book, not {f.suffix or 'a file with no extension'}")
    text = f.read_text(encoding="utf-8")
    results = booklint.lint(project, text, path=target, view=view, cfg=cfg, tokens_doc=doc, facts_rows=facts,
                            self_consistency=a.self_consistency, allow_variants=a.allow_variants)
    rep = booklint.write_report(project, f, results, view=view, state_view_sha=bookdata.view_sha(view, facts), self_consistency=a.self_consistency,
                                book_file=f.relative_to(project.resolve()).as_posix())
    return rep.finish(quiet_pass=True)


main_guard(main)
