#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator book: build the brand book (generated and existing marks) from data, or scaffold its chapter files.

  book                    build book.html (self-contained: fonts and images inline, no script, no network, light and dark) from the
                          tokens, assets/manifest.json, BRAND-STATE.md, FACTS.md, the contrast and downscale reports and
                          book/chapters/*.md; lint it (book-lint, with --self-consistency); write it only when it lints clean
  book --init             copy the skeleton of every chapter this book needs from templates/book/ into book/chapters/ (never overwrites)
  book --verify           rebuild in memory and compare with the book on disk (a hand edit or a stale book fails)
  book --allow-variants   build with choice scaffolding still open, for a review (book-lint still fails it until `collapse`)

mark_source authored-vector: the book is hand-authored HTML; this command refuses. Edit it with `brand-creator patch` and gate it
with `brand-creator book-lint`. Which chapters appear follows the tier, the architecture and BRAND-STATE.md (scripts/CONTRACT.md,
"Brand book"). The output is byte-identical for the same inputs. Report: assets/_checks/book.json (and book-lint.json).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "booklib"))
import bookdata  # noqa: E402
import bookgen  # noqa: E402
import booklint  # noqa: E402
from _common import (EXIT_FAIL, EXIT_USAGE, Parser, Report, add_project_arg, add_renderer_arg, confine, fail, find_project, main_guard,  # noqa: E402
                     plugin_root, rel, sha256_bytes, write_bytes_if_changed)


def init_chapters(project: Path, build: "bookgen.BookBuild") -> int:
    tpl = plugin_root() / "templates" / "book"
    made = kept = 0
    for cid in build.chapter_ids:
        src = tpl / f"{cid}.md"
        if not src.is_file():
            fail(EXIT_FAIL, f"template missing: {src}")
        for lang in build.langs:
            name = f"{cid}.md" if len(build.langs) == 1 else f"{cid}.{lang}.md"
            dest = confine(project, f"{bookdata.CHAPTER_DIR}/{name}", what="chapter")
            if dest.exists():
                kept += 1
                print(f"kept    {rel(project, dest)} (exists)")
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
            made += 1
            print(f"wrote   {rel(project, dest)}")
    print(f"{made} chapter file(s) written, {kept} kept; chapters for this book: {', '.join(build.chapter_ids)}")
    print("next: fill every [[fill: ...]] marker, then run: brand-creator book")
    return 0


def main() -> int:
    ap = Parser(prog="brand-creator book", description=__doc__, formatter_class=__import__("argparse").RawDescriptionHelpFormatter)
    add_project_arg(ap)
    add_renderer_arg(ap)
    ap.add_argument("--out", help="output file inside the project (default: `output` in book/book.json, else book.html)")
    ap.add_argument("--init", action="store_true", help="write the chapter skeletons this book needs; never overwrites")
    ap.add_argument("--verify", action="store_true", help="rebuild in memory and compare with the book on disk")
    ap.add_argument("--allow-variants", action="store_true", help="build with open choice scaffolding for a review (book-lint still fails it)")
    a = ap.parse_args()
    project = find_project(a.project)
    view = bookdata.state_view(project)
    if view["mark_source"] == "authored-vector":
        fail(EXIT_USAGE, "mark_source is authored-vector: the book is hand-authored HTML, so `brand-creator book` does not build it. Edit it with "
                         "`brand-creator patch book.html --old ... --new ... --count N` and gate it with `brand-creator book-lint --self-consistency`")
    build = bookgen.BookBuild(project, renderer=a.renderer, allow_variants=a.allow_variants)
    if a.init:
        return init_chapters(project, build)
    out_rel = a.out or build.cfg["output"]
    out = confine(project, out_rel, what="--out")
    rep = Report("book", project)
    page = build.build()
    data = page.encode("utf-8")
    rep.inputs = list(build.inputs)
    state_sha = bookdata.view_sha(build.view, build.facts)
    for cid in build.chapter_ids:
        rep.add(f"chapter:{cid}", "pass", "chapter built", detail=f"{len(build.langs)} language(s): {','.join(build.langs)}")
    for id_, detail in build.warnings:
        rep.add(f"book:{id_}", "warn", "a source is missing or stale", detail=detail)
    for id_, detail in build.infos:
        rep.add(f"book:{id_}", "info", "note", detail=detail)
    results = booklint.lint(project, page, path=out_rel, view=build.view, cfg=build.cfg, tokens_doc=build.doc, facts_rows=build.facts,
                            self_consistency=True, allow_variants=a.allow_variants)
    for r in results:
        extra = {k: v for k, v in r.items() if k not in ("id", "status", "label")}
        rep.add(f"lint:{r['id']}", r["status"], r["label"], **extra)
    failing = [r for r in results if r["status"] == "fail"]
    rep.extra.update({"mode": "generated", "output": {"path": out_rel, "sha256": sha256_bytes(data), "bytes": len(data)},
                      "chapters": build.chapter_ids, "languages": build.langs, "state_view_sha": state_sha,
                      "manifest_view_sha": bookdata.manifest_view_sha(project),
                      "written": False})
    if a.verify:
        cur = out.read_bytes() if out.is_file() else None
        same = cur == data
        rep.add("verify", "pass" if same else "fail", "the book on disk is what the sources build",
                detail="byte-identical" if same else ("no book on disk" if cur is None else
                                                      "book.html differs from a rebuild: it was edited by hand or the sources changed since; run `brand-creator book`"))
        return rep.finish(quiet_pass=True)
    if failing:
        rc = rep.finish()
        print("book.html was NOT written: it does not lint clean (the book on disk, if any, is unchanged)", file=sys.stderr)
        return rc or EXIT_FAIL
    changed = write_bytes_if_changed(out, data)
    rep.extra["written"] = changed
    lrep = booklint.write_report(project, out, results, state_view_sha=state_sha, self_consistency=True, book_file=out_rel)
    lrep.finish(quiet_pass=True)
    rc = rep.finish(quiet_pass=True)
    print(f"book: {rel(project, out)} {'written' if changed else 'unchanged'} ({len(data)} bytes, {len(build.chapter_ids)} chapters, {','.join(build.langs)})")
    return rc


main_guard(main)
