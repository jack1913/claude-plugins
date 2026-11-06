#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator patch FILE --old TEXT --new TEXT --count N: the one edit path for a hand-authored brand book.

Replaces TEXT in FILE and refuses, writing nothing, unless TEXT occurs exactly N times (a count that is off means the edit was
aimed at something else). On a book file it also writes one line to the `## Edition log` of BRAND-STATE.md, and it refuses to edit
an edition that was approved (G5) unless --new-edition opens the next one, so an approved edition never changes under its stamp.
A generated book is never patched: edit book/chapters/*.md (patch works there) and run `brand-creator book`.
--loose-space lets --old match a no-break space (U+00A0, U+202F) or a longer run of white space where it has a space (the count must still
be exact). --old and --new may come from files (--old-file, --new-file) for multi-line text. Never touches history/ or earlier rounds: which
rounds are earlier is the hook's own rule (guard.round_is_open: the latest round, and rounds/r0/ while G1s is empty).
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "booklib"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bookdata  # noqa: E402
import bookedit  # noqa: E402
from _common import (EXIT_FAIL, EXIT_USAGE, Parser, add_project_arg, confine, fail, find_project, main_guard, read_state,  # noqa: E402
                     rel, write_bytes_if_changed)


def is_book_file(project: Path, f: Path, cfg: dict) -> bool:
    r = f.relative_to(Path(__import__("os").path.realpath(project))).as_posix()
    return r == cfg["output"] or r.startswith("book/")


def main() -> int:
    ap = Parser(prog="brand-creator patch", description=__doc__, formatter_class=__import__("argparse").RawDescriptionHelpFormatter)
    add_project_arg(ap)
    ap.add_argument("file", help="the file to edit (inside the project)")
    ap.add_argument("--old", help="the text to replace")
    ap.add_argument("--new", help="the replacement")
    ap.add_argument("--old-file", help="read the text to replace from a file")
    ap.add_argument("--new-file", help="read the replacement from a file")
    ap.add_argument("--loose-space", action="store_true",
                    help="--old also matches where the book has a no-break space (U+00A0, U+202F) or a longer run of white space in place of a space; still needs exactly --count matches")
    ap.add_argument("--count", type=int, required=True, help="how many times --old must occur (the edit is refused otherwise)")
    ap.add_argument("--note", default="", help="one line for the edition log: why")
    ap.add_argument("--new-edition", action="store_true", help="open the next edition (needed to edit an approved one)")
    a = ap.parse_args()
    project = find_project(a.project)
    if (a.old is None) == (a.old_file is None) or (a.new is None) == (a.new_file is None):
        fail(EXIT_USAGE, "give --old or --old-file, and --new or --new-file (one of each)")
    old = a.old if a.old is not None else Path(a.old_file).read_text(encoding="utf-8")
    new = a.new if a.new is not None else Path(a.new_file).read_text(encoding="utf-8")
    if a.count < 1:
        fail(EXIT_USAGE, "--count must be 1 or more")
    if old == "":
        fail(EXIT_USAGE, "--old is empty")
    if old == new:
        fail(EXIT_USAGE, "--old and --new are the same text; nothing to do")
    f = confine(project, a.file, what="file")
    if not f.is_file():
        fail(EXIT_USAGE, f"{a.file} is not a file in the project")
    r = rel(project, f)
    bookedit.refuse_frozen(project, r)
    try:
        text = f.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        fail(EXIT_USAGE, f"{r} is not UTF-8 text")
    pat = bookedit.loose_pattern(old) if a.loose_space else re.compile(re.escape(old))
    spans = [(m.start(), m.end()) for m in pat.finditer(text)]
    found = len(spans)
    if found != a.count:
        fail(EXIT_FAIL, f"refused: {r} holds the text {found} time(s){' (counting a no-break space or a longer run of white space as a space)' if a.loose_space else ''}, "
                        f"--count says {a.count}; nothing was written. Check the text (a quote, an indent"
                        f"{'' if a.loose_space else ', a no-break space: --loose-space'}) or change --count after reading where it occurs")
    st = read_state(project)
    cfg, _ = bookdata.load_config(project)
    logged = ""
    if is_book_file(project, f, cfg):
        view = bookdata.state_view(project)
        if view["mark_source"] != "authored-vector" and r == cfg["output"]:
            fail(EXIT_FAIL, f"{r} is generated (mark_source {view['mark_source']}) and is never edited by hand: patch book/chapters/*.md, then run `brand-creator book`")
        edition = bookedit.begin_edition(st, view, a.new_edition)
        logged = bookedit.log_line(st, edition, f"patched {r} ({found} replacement{'s' if found != 1 else ''})", a.note)
    new_text = pat.sub(lambda m: new, text)
    write_bytes_if_changed(f, new_text.encode("utf-8"))
    if logged:
        st.save()
    where = ", ".join(str(text.count("\n", 0, s0) + 1) for s0, _e in spans)
    print(f"patched {r}: {found} replacement(s) at line(s) {where}" + (f"\nedition log: {logged}" if logged else "\n(not a book file: no edition log entry)"))
    return 0


main_guard(main)
