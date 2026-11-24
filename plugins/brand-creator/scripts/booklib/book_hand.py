"""brand-creator book chapter | nbsp: whole-chapter work and no-break spaces in a hand-authored book (mark_source authored-vector).

  book chapter --replace ID --from FILE        replace the <section data-chapter="ID"> element by the fragment in FILE (its root must be a
                                               <section> with the same data-chapter); the rest of the book stays byte for byte
  book chapter --add ID --from FILE [--after ID]   insert a new chapter after the chapter --after (default: the last one)
  book chapter --remove ID                     remove a chapter; refused while the book still links to #ID (patch the contents first)
  book nbsp --fix [--yes]                      put a no-break space after each one-letter word of the book's languages (the rule book-lint warns
                                               on: scripts/data/languages/<code>.json); a dry run listing the changes unless --yes

Both go through the edition path of `patch`: an approved edition needs --new-edition, and each edit is one line in the Edition log of
BRAND-STATE.md. After a chapter is added or removed the chapter count shown by data-count="chapters" (the contents) is recomputed
here, never typed; book-lint fails a count that does not match. Refuses (exit 2) a book that is generated, an id that is not found
(or already there), and a fragment without the same id. Nothing is written on a refusal.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "booklib"))
import bookdata  # noqa: E402
import bookedit  # noqa: E402
import booklint  # noqa: E402
import htmlscan  # noqa: E402
from _common import (EXIT_USAGE, Parser, add_project_arg, confine, fail, find_project, read_state, rel, write_bytes_if_changed)  # noqa: E402


def _chapters(text: str) -> list[tuple[int, int, str]]:
    try:
        return [(t.start, htmlscan.element_end(text, t), t.attrs["data-chapter"]) for t in htmlscan.tags(text)
                if not t.closing and t.name == "section" and "data-chapter" in t.attrs]
    except ValueError as e:
        fail(EXIT_USAGE, f"the book has a chapter that is not closed: {e}")


def sync_chapter_count(text: str) -> tuple[str, int]:
    """Rewrite what each data-count="chapters" element shows to the number of chapters in `text`. -> (text, how many elements)."""
    n = len(_chapters(text))
    out, done = text, 0
    for t in reversed([t for t in htmlscan.tags(text) if not t.closing and t.attrs.get("data-count") == "chapters"]):
        end = htmlscan.element_end(out, t)
        close = out.rfind("</", t.end, end)
        if t.void or close < 0 or "<" in out[t.end:close]:
            fail(EXIT_USAGE, f"the chapter count at offset {t.start} (data-count=\"chapters\") holds markup; make it a plain number so it can be recomputed")
        out = out[:t.end] + str(n) + out[close:]
        done += 1
    return out, done


def _open(project: Path, a) -> tuple[Path, str, dict, dict]:
    view = bookdata.state_view(project)
    if view["mark_source"] != "authored-vector":
        fail(EXIT_USAGE, f"mark_source is {view['mark_source']}: the book is generated, so it is not edited by hand. Change book/chapters/*.md and run `brand-creator book`")
    cfg, _ = bookdata.load_config(project)
    f = confine(project, a.file or cfg["output"], what="book")
    if not f.is_file():
        fail(EXIT_USAGE, f"book not found: {a.file or cfg['output']}")
    bookedit.refuse_frozen(project, rel(project, f))
    try:
        text = f.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        fail(EXIT_USAGE, f"{rel(project, f)} is not UTF-8 text")
    return f, text, view, cfg


def _commit(project: Path, f: Path, new_text: str, view: dict, new_edition: bool, what: str, note: str) -> str:
    st = read_state(project)
    edition = bookedit.begin_edition(st, view, new_edition)
    line = bookedit.log_line(st, edition, what, note)
    write_bytes_if_changed(f, new_text.encode("utf-8"))
    st.save()
    return line


def _fragment(path: str, cid: str) -> str:
    p = Path(path)
    if not p.is_file():
        fail(EXIT_USAGE, f"--from {path} is not a file")
    try:
        frag = p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        fail(EXIT_USAGE, f"--from {path} is not UTF-8 text")
    frag = frag.removeprefix("\ufeff")   # a byte order mark is not part of the chapter
    tops = [t for t in htmlscan.tags(frag) if not t.closing][:1]
    if not tops or tops[0].name != "section" or tops[0].attrs.get("data-chapter") != cid:
        got = f"data-chapter={tops[0].attrs.get('data-chapter')!r} on <{tops[0].name}>" if tops else "no element"
        fail(EXIT_USAGE, f"the fragment's root must be <section data-chapter=\"{cid}\">; {path} starts with {got}")
    try:
        end = htmlscan.element_end(frag, tops[0])
    except ValueError as e:
        fail(EXIT_USAGE, f"the fragment in {path} is not closed: {e}")
    if tops[0].start != len(frag) - len(frag.lstrip()) or frag[end:].strip():
        fail(EXIT_USAGE, f"{path} must hold one chapter element and nothing else (text, a comment or a second element outside <section data-chapter=\"{cid}\">)")
    return frag[tops[0].start:end]


def chapter(argv: list[str]) -> int:
    ap = Parser(prog="brand-creator book chapter", description=__doc__, formatter_class=__import__("argparse").RawDescriptionHelpFormatter)
    add_project_arg(ap)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--replace", metavar="ID", help="replace this chapter by the fragment in --from")
    g.add_argument("--add", metavar="ID", help="add this chapter, the fragment in --from")
    g.add_argument("--remove", metavar="ID", help="remove this chapter")
    ap.add_argument("--from", dest="src", help="the file holding the chapter fragment (<section data-chapter=ID>...</section>)")
    ap.add_argument("--after", metavar="ID", help="with --add: the chapter it follows (default: the last)")
    ap.add_argument("--file", help="the book (default: `output` in book/book.json, else book.html)")
    ap.add_argument("--note", default="", help="one line for the edition log: why")
    ap.add_argument("--new-edition", action="store_true", help="open the next edition (needed to edit an approved one)")
    a = ap.parse_args(argv)
    project = find_project(a.project)
    cid = a.replace or a.add or a.remove
    if a.remove is None and not a.src:
        fail(EXIT_USAGE, "--replace and --add need --from FILE")
    if a.remove is not None and a.src:
        fail(EXIT_USAGE, "--remove takes no --from")
    if a.after and not a.add:
        fail(EXIT_USAGE, "--after belongs to --add")
    f, text, view, _cfg = _open(project, a)
    r = rel(project, f)
    chs = _chapters(text)
    have = {c: (s, e) for s, e, c in chs}
    if sum(1 for _s, _e, c in chs if c == cid) > 1:
        fail(EXIT_USAGE, f"{r} has {sum(1 for _s, _e, c in chs if c == cid)} chapters with data-chapter=\"{cid}\"; make the ids unique with `brand-creator patch` first")
    if a.add:
        if cid in have:
            fail(EXIT_USAGE, f"{r} already has a chapter {cid!r}; use --replace")
    elif cid not in have:
        fail(EXIT_USAGE, f"{r} has no <section data-chapter=\"{cid}\"> (chapters: {', '.join(c for _s, _e, c in chs) or 'none'})")
    frag = _fragment(a.src, cid) if a.src else ""
    if a.replace:
        s, e = have[cid]
        new_text, verb = text[:s] + frag + text[e:], "replaced"
    elif a.add:
        if a.after and a.after not in have:
            fail(EXIT_USAGE, f"--after {a.after!r}: {r} has no such chapter")
        if not chs:
            fail(EXIT_USAGE, f"{r} has no chapter to put the new one after; add it with `brand-creator patch`")
        at = have[a.after][1] if a.after else chs[-1][1]
        new_text, verb = text[:at] + "\n" + frag + text[at:], "added"
    else:
        s, e = have[cid]
        # links to the chapter's data-chapter value, to its section's own id and to any id inside it
        ids = {cid} | {t.attrs["id"] for t in htmlscan.tags(text[s:e]) if not t.closing and t.attrs.get("id")}
        # by offset, not by line: a link on the section's own line but outside it (a one-line or minified book) still dangles
        hits = [m.start() for i in sorted(ids) for m in re.finditer(rf"""href\s*=\s*["']#{re.escape(i)}["']""", text)]
        links = sorted({text.count("\n", 0, at) + 1 for at in hits if not s <= at < e})
        if links:
            fail(EXIT_USAGE, f"refused: the book still links to #{cid} or an id inside it (line(s) {', '.join(map(str, links))}); take those links out with `brand-creator patch --loose-space` first")
        e2 = e + 1 if text[e:e + 1] == "\n" else e
        new_text, verb = text[:s] + text[e2:], "removed"
    before = len(chs)
    new_text, counted = sync_chapter_count(new_text)
    after = len(_chapters(new_text))
    what = f"{verb} chapter {cid} in {r} (chapters {before} -> {after})"
    line = _commit(project, f, new_text, view, a.new_edition, what, a.note)
    print(f"{verb} chapter {cid} in {r}: {before} -> {after} chapter(s)")
    print(f"chapter count: {counted} element(s) with data-count=\"chapters\" now show {after}" if counted
          else "chapter count: the book has no data-count=\"chapters\" element, nothing to recompute")
    print(f"edition log: {line}")
    if a.add:
        print(f"next: link the chapter from the contents (`brand-creator patch`), then `brand-creator book-lint --self-consistency`")
    return 0


_TAG = re.compile(r"""</?([A-Za-z][\w:-]*)(?:"[^"]*"|'[^']*'|[^>"'])*>""")
_BLOCKS = ("code", "script", "style", "svg", "pre", "table", "textarea")   # never written in or near: the lint blanks most of these whole
# Tags that start or end a block, or break the line. The fixer never steps over one: a no-break space between two blocks (</h2> <p>) is
# no longer collapsible white space and shows as a gap. Any other tag (em, a, span, code, script...) is stepped over.
_BLOCK_LEVEL = {"address", "article", "aside", "blockquote", "body", "br", "caption", "dd", "details", "dialog", "div", "dl", "dt",
                "fieldset", "figcaption", "figure", "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6", "head", "header", "hgroup", "hr",
                "html", "li", "main", "nav", "ol", "option", "p", "pre", "section", "select", "summary", "table", "tbody", "td",
                "textarea", "tfoot", "th", "thead", "title", "tr", "ul"}


def _no_write(text: str) -> list[tuple[int, int]]:
    """Spans of `text` the fixer never writes in: every tag (attribute values that hold '>' included), every comment, and the whole of each
    element in _BLOCKS."""
    spans = [(m.start(), m.end()) for m in re.finditer(r"<!--.*?(?:-->|$)", text, flags=re.S)]
    spans += [(m.start(), m.end()) for m in _TAG.finditer(text)]
    for name in _BLOCKS:
        for m in re.finditer(rf"<{name}\b(?:\"[^\"]*\"|'[^']*'|[^>\"'])*>", text, flags=re.I):
            close = re.compile(rf"</{name}\s*>", re.I).search(text, m.end())
            spans.append((m.start(), close.end() if close else len(text)))
    return spans


def _step(text: str, i: int) -> int:
    """`i` moved past the tags and comments that start there, or -1 when one of them is in _BLOCK_LEVEL."""
    while True:
        if text.startswith("<!--", i):
            e = text.find("-->", i)
            if e < 0:
                return -1
            i = e + 3
            continue
        m = _TAG.match(text, i)
        if not m:
            return i
        if m.group(1).lower() in _BLOCK_LEVEL:
            return -1
        if m.group(1).lower() in _BLOCKS and not m.group(0).startswith("</"):
            return i   # an inline element the fixer never enters (<code>, <svg>, <script>...): it stands where the next word would
        i = m.end()


def nbsp_plan(text: str, view: dict) -> list[tuple[int, int, int, str]]:
    """The edits `book nbsp` makes, as (start, end, line, context) in the real text: text[start:end] is the run of ordinary spaces or tabs
    that follows a one-letter word, and it becomes one no-break space. Found by the lint's own rule (booklint.nbsp_fixes). Left alone: a
    word inside a tag, a comment or an element in _BLOCKS, and a place where a block-level tag (_BLOCK_LEVEL) stands between the word
    and the next one."""
    skip = _no_write(text)
    inside = lambda i: any(x <= i < y for x, y in skip)  # noqa: E731
    out = []
    for s, _e, ln, _ctx in booklint.nbsp_fixes(text, view):
        if s == 0 or inside(s - 1):
            continue
        j = _step(text, s)   # the word may end inside an inline tag (<em>a</em> las)
        if j < 0 or inside(j):
            continue
        k = j
        while k < len(text) and text[k] in " \t":
            k += 1
        n = _step(text, k) if k > j else -1   # what follows the run: the next word, after inline tags only
        if n < 0 or n >= len(text) or text[n] in " \t\r\n":   # a second run after inline tags would show beside the no-break space
            continue
        out.append((j, k, ln, " ".join(text[max(0, s - 24):k + 24].split())))
    return out


def nbsp(argv: list[str]) -> int:
    ap = Parser(prog="brand-creator book nbsp", description=__doc__, formatter_class=__import__("argparse").RawDescriptionHelpFormatter)
    add_project_arg(ap)
    ap.add_argument("--fix", action="store_true", help="find the ordinary spaces after a one-letter word (the book-lint rule); a dry run unless --yes")
    ap.add_argument("--yes", action="store_true", help="write the changes (needs --fix)")
    ap.add_argument("--file", help="the book (default: `output` in book/book.json, else book.html)")
    ap.add_argument("--note", default="", help="one line for the edition log: why")
    ap.add_argument("--new-edition", action="store_true", help="open the next edition (needed to edit an approved one)")
    a = ap.parse_args(argv)
    project = find_project(a.project)
    if not a.fix:
        fail(EXIT_USAGE, "say what to do: `brand-creator book nbsp --fix` lists the spaces to change (add --yes to write them)")
    f, text, view, _cfg = _open(project, a)
    r = rel(project, f)
    plan = nbsp_plan(text, view)
    for _s, _k, ln, ctx in plan:
        print(f"line {ln}: \"{ctx}\"")
    if not plan:
        print(f"{r}: no one-letter word is followed by an ordinary space; nothing to change")
        return 0
    done = len(plan)
    if not a.yes:
        print(f"dry run: {done} space(s) in {r} would become a no-break space; nothing was written. Add --yes to write them")
        return 0
    out, prev = [], 0
    for s, k, _l, _c in plan:
        out += [text[prev:s], "\u00a0"]   # the run of ordinary spaces right after the word becomes one no-break space; nothing else moves
        prev = k
    out.append(text[prev:])
    line = _commit(project, f, "".join(out), view, a.new_edition, f"nbsp in {r} ({done} space{'s' if done != 1 else ''} made no-break)", a.note)
    print(f"wrote {r}: {done} space(s) are now no-break spaces\nedition log: {line}")
    return 0


def main(sub: str, argv: list[str]) -> int:
    return chapter(argv) if sub == "chapter" else nbsp(argv)
