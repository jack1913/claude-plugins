#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator emit presskit: a press-kit zip of the logos, lockups, tokens and the book PDF.

  assets/presskit/<slug>-press-kit.zip
    <slug>-press-kit/logos/<file>        every .svg and .png in assets/logo/ (the mark, wordmark, lockups and their dark partners)
    <slug>-press-kit/tokens/tokens.css   the built tokens (assets/tokens/tokens.css and tokens.json)
    <slug>-press-kit/book/book.pdf       the RGB proof of the brand book (`brand-creator book-pdf`); --no-book leaves it out, said in the report
    <slug>-press-kit/README.txt          the file list with sha256 and sizes, and what book.pdf is. It states no usage terms: those are the owner's
    plus any file named with --include (a project path; repeatable)

The zip is deterministic: entries sorted by name, the fixed mtime 1980-01-01 and fixed attributes (determinism.fixed_zip), so the same inputs
give the same bytes and the file is only rewritten when it changes. Every file read is a report input, so editing a logo makes the report
stale. Needs gate G3 (the press gets the approved identity).
"""
import hashlib
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "lib"))
import determinism  # noqa: E402
from _common import EXIT_FAIL, EXIT_USAGE, confine, fail, main_guard, rel  # noqa: E402
from _emit import Emit  # noqa: E402

BOOK_LABEL = b"RGB, not print-ready"
LOGO_SUFFIXES = (".svg", ".png")


def main() -> int:
    def args(ap):
        ap.add_argument("--book", default="book.pdf", help="the book PDF inside the project (default book.pdf)")
        ap.add_argument("--no-book", action="store_true", help="build the kit without the book PDF (said in the report)")
        ap.add_argument("--include", action="append", default=[], metavar="PATH", help="another project file to add under extra/ (repeatable)")

    e = Emit.begin("presskit", __doc__, add_args=args, tiers=("standard", "full"), tier_what="the press kit")
    a, project = e.a, e.project
    root = f"{e.slug}-press-kit"
    entries: dict[str, bytes] = {}
    listing: list[tuple[str, bytes]] = []

    def add(arc: str, f: Path) -> None:
        data = f.read_bytes()
        entries[f"{root}/{arc}"] = data
        listing.append((arc, data))
        e.add_input(f)

    logo_dir = project / "assets" / "logo"
    logos = sorted(p for p in logo_dir.glob("*") if p.is_file() and p.suffix.lower() in LOGO_SUFFIXES) if logo_dir.is_dir() else []
    if not logos:
        fail(EXIT_FAIL, "assets/logo/ holds no .svg or .png logo files: there is nothing to put in a press kit")
    for f in logos:
        add(f"logos/{f.name}", f)
    for name in ("tokens.css", "tokens.json"):
        f = project / "assets" / "tokens" / name
        if not f.is_file():
            fail(EXIT_FAIL, f"assets/tokens/{name} not found; run `brand-creator tokens` first")
        add(f"tokens/{name}", f)
    if a.no_book:
        e.rep.add("note:book", "warn", "no book PDF in the kit", detail="--no-book was given: the kit holds logos and tokens only")
    else:
        bf = confine(project, a.book, what="--book")
        if not bf.is_file():
            fail(EXIT_FAIL, f"{a.book} not found: build the book and its PDF first (`brand-creator book`, `brand-creator book-pdf`), or pass --no-book")
        add("book/book.pdf", bf)
        has_label = BOOK_LABEL in bf.read_bytes()
        e.rep.add("check:book label", "pass" if has_label else "warn", "the book PDF carries its RGB label",
                  detail=f"{a.book} says 'RGB, not print-ready': it is a proof for reading, and the kit's README says so" if has_label
                  else f"{a.book} does not carry the label 'RGB, not print-ready': was it made by `brand-creator book-pdf`?")
    for inc in a.include:
        f = confine(project, inc, what="--include")
        if not f.is_file():
            fail(EXIT_USAGE, f"--include not found: {inc}")
        add(f"extra/{rel(project, f)}", f)

    lines = [f"{e.brand}: press kit", "", "Files (sha256, bytes, path):", ""]
    for arc, data in sorted(listing):
        lines.append(f"{hashlib.sha256(data).hexdigest()}  {len(data):>9}  {arc}")
    lines += ["", "logos/    the artwork: vector SVG (and PNG where the brand has one), light and dark partners where they exist.",
              "tokens/   the brand's colours and other values, as CSS custom properties and JSON."]
    if not a.no_book:
        lines += ["book/     book.pdf is an RGB proof of the brand book, for reading. It is not a print file."]
    lines += ["", "This kit states no terms of use. Ask the owner how the logos may be used.", ""]
    entries[f"{root}/README.txt"] = "\n".join(lines).encode("utf-8")

    data = determinism.fixed_zip(entries)
    rel_zip = f"{e.out}/{e.slug}-press-kit.zip"
    e.put(rel_zip, data, [], slot="press-kit", resampled_by="PAGE", note=f"{len(entries)} files; deterministic zip (sorted entries, fixed mtime)")
    probs = determinism.lint_file(project / rel_zip)
    e.rep.add("check:zip determinism", "fail" if probs else "pass", "entries sorted, fixed mtime", detail="; ".join(probs) or f"{len(entries)} entries")
    e.rep.extra.update({"entries": sorted(entries), "book_included": not a.no_book})
    return e.finish()


main_guard(main)
