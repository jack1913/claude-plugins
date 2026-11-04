#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator inline <page.html> --out <file.html> [--project DIR]: one self-contained copy of a page of the project, to show to someone.

    brand-creator inline tryout/Atlas/index.html --out "$DATA/scratch/tryout/Atlas.html"

The page is read as a browser reads it, from its own folder, and every file it loads goes inside the copy: a stylesheet becomes a <style> element
(its url() and @import inlined in turn, each seen from the stylesheet's own folder), a script becomes an inline <script> (a classic script with
`defer` goes to the end of <body>, where it ran), and an image, a font, the logo, a favicon or a poster becomes a data: URL (src, srcset, poster,
the href of an icon link or of an SVG <image>, url() in a <style>, in a style attribute and in a stylesheet). A <link> that only hints (preload,
prefetch) is dropped. Not read: links (<a href>), form actions, the text of a <script> and a bare string in image-set(). A link to a file of the project
is dead in the copy, and the check that the page asks the network for nothing at run time is page-check's (or `shot`'s), on the page or its copy.
The output is the same bytes for the same inputs.

Nothing is written when any problem stops the page. Exit 0 written. Exit 1: a file the page names does not exist; a kind of file this command does not
inline (video, audio, a manifest, a frame or an embedded page); an @import with a condition, a module that imports another file, a <base href>, an SVG
<use> of another file; a page that is not UTF-8. Exit 2: usage; a page or a file outside the project; a page that loads from another website (an
address with http(s), ftp(s), ws(s) or //, any other scheme but data:, a path starting with /), named by its URL; an --out inside the project but not
under tryout/, not .html or the page itself. Reads only inside the project. Writes only the one --out file, outside the project or under its tryout/ folder; no report.
"""
import base64
import html
import os
import re
import sys
from pathlib import Path
from urllib.parse import unquote

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))
sys.path.insert(0, str(HERE / "booklib"))
sys.path.insert(0, str(HERE / "boardlib"))   # sitedata: the readers of the URLs of a page that `site approve` uses, so the two commands read the same places
import _common  # noqa: E402
import htmlscan  # noqa: E402
import sitedata  # noqa: E402
from _common import EXIT_FAIL, EXIT_USAGE, Parser, add_project_arg, confine, fail, find_project, main_guard, write_bytes_if_changed  # noqa: E402
from bookgen import FONT_MIME, IMG_MIME  # noqa: E402   (what the book embeds: the same types here)

MIME = {**IMG_MIME, **{ext: mime for ext, (mime, _fmt) in FONT_MIME.items()}, ".avif": "image/avif", ".ico": "image/x-icon"}
PAGE_SUFFIXES = (".html", ".htm")
HTML_SUFFIXES = (".html", ".htm", ".xhtml")
CODE_SUFFIXES = {"stylesheet": (".css",), "script": (".js", ".mjs")}   # the only files read as text into the page: no other project file (BRAND-STATE.md, FACTS.md) goes in
HINT_RELS = {"preload", "prefetch", "modulepreload", "preconnect", "dns-prefetch"}   # a hint: dropped when local, refused when it names another website
FILE_RELS = {"icon", "shortcut", "apple-touch-icon", "apple-touch-icon-precomposed", "mask-icon", "apple-touch-startup-image", "manifest"}   # the href is a file the page loads
SCRIPT_DROP = {"src", "integrity", "crossorigin", "defer", "async", "referrerpolicy", "fetchpriority", "blocking"}   # what an inline script has no use for
MODULE_IMPORT = re.compile(r"""(?m)^\s*(?:import|export)\b[^;\n]*?\bfrom\s*["']|^\s*import\s*["']|\bimport\s*\(""")
IMPORT_HEAD = re.compile(r"""@import\s+(?:url\(\s*)?["']?$""", re.I)
IMPORT_TAIL = re.compile(r"""["']?\s*\)?\s*;""")
CHARSET = re.compile(r"""\A\s*@charset\s+["'][^"']*["']\s*;\s*""")
SHOWN = 12            # problems listed in a message before "and N more"
IMPORT_DEPTH = 8      # stylesheets imported inside stylesheets


class Refused(Exception):
    """One URL or file the page cannot go with: the exit code it means, and the sentence."""

    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def attribute_values(t):
    """(lower-case name, the value as written, its quote group, its offset in the text) of each attribute of a tag that has a value."""
    origin = t.start + 1 + len(t.name)
    for m in sitedata._ATTR.finditer(t.attrs_src):
        g = next((x for x in ("dq", "sq", "uq") if m.group(x) is not None), None)
        if g:
            yield m.group("name").lower(), m.group(g), g, origin + m.start(g)


def apply(text: str, edits: list[tuple[int, int, str]]) -> str:
    """`text` with each edit (start, end, new text) applied; the edits do not overlap."""
    for start, end, new in sorted(edits, key=lambda e: (e[0], e[1]), reverse=True):
        text = text[:start] + new + text[end:]
    return text


class Inliner:
    """Reads a page and the files it loads. `problems` holds (exit code, sentence); `files` the project-relative paths read, in the order they were first read."""

    def __init__(self, project: Path):
        self.root = Path(os.path.realpath(project))
        self.problems: list[tuple[int, str]] = []
        self.files: dict[str, bytes] = {}

    def rel(self, p: Path) -> str:
        return p.relative_to(self.root).as_posix()

    def problem(self, label: str, line: int, e: Refused) -> None:
        self.problems.append((e.code, f"{label} line {line}: {e.message}"))

    # ---- files
    def locate(self, url: str, base: Path) -> tuple[Path, str] | None:
        """The file a URL leads to, seen from the folder `base`, and its #fragment; None to leave the URL as written (empty, #fragment, data:)."""
        s = url.strip()
        if not s or s.startswith("#"):
            return None
        shown = sitedata._shown(s)
        scheme = sitedata._SCHEME.match(s)
        if s.startswith("//") or (scheme and scheme.group(1).lower() in sitedata.NETWORK_SCHEMES):
            raise Refused(EXIT_USAGE, f"{shown} is on another website: a page that is shared loads nothing from the network (put the file in the project, or take it out)")
        if scheme:
            if scheme.group(1).lower() == "data":
                return None
            raise Refused(EXIT_USAGE, f"{shown} uses the {scheme.group(1).lower()}: scheme, which a shared page cannot rely on (data: is kept)")
        if s.startswith("/"):
            raise Refused(EXIT_USAGE, f"{shown} starts with / and leads to a place on a web server, not to a file of the project: write the path relative to the page")
        path_part = re.split(r"[?#]", s, maxsplit=1)[0]
        if not path_part:
            return None
        real = Path(os.path.realpath(base / unquote(path_part)))
        if real != self.root and self.root not in real.parents:
            raise Refused(EXIT_USAGE, f"{shown} leads outside the project (or through a link to a place outside it)")
        if any(part.startswith(".") for part in real.relative_to(self.root).parts):
            raise Refused(EXIT_FAIL, f"{shown} leads to {self.rel(real)}, a hidden file or folder, which a shared page does not take")
        if not real.exists():
            raise Refused(EXIT_FAIL, f"{shown} leads to {self.rel(real)}, which does not exist")
        if not real.is_file():
            raise Refused(EXIT_FAIL, f"{shown} leads to {self.rel(real)}, which is a folder")
        return real, ("#" + s.split("#", 1)[1] if "#" in s else "")

    def read(self, p: Path) -> bytes:
        key = self.rel(p)
        if key not in self.files:
            self.files[key] = p.read_bytes()
        return self.files[key]

    def text(self, p: Path) -> str:
        try:
            return self.read(p).decode("utf-8-sig")
        except UnicodeDecodeError:
            raise Refused(EXIT_FAIL, f"{self.rel(p)} is not UTF-8 text, so it cannot be put inside the page")

    def code(self, p: Path, kind: str) -> str:
        """The text of a stylesheet or a script file; any other file is refused, so a page cannot carry a project file into its copy."""
        if p.suffix.lower() not in CODE_SUFFIXES[kind]:
            names = " or ".join(CODE_SUFFIXES[kind])
            raise Refused(EXIT_FAIL, f"{self.rel(p)} is not a {kind}: only a {names} file is put inside the page as a {kind}")
        return self.text(p)

    def data_uri(self, url: str, base: Path, tag: str = "") -> str | None:
        """The data: URL of the file a URL leads to (its fragment kept), or None to leave the URL as written. `tag` is the element it loads for."""
        found = self.locate(url, base)
        if found is None:
            return None
        path, fragment = found
        if tag == "use":
            raise Refused(EXIT_FAIL, f"{self.rel(path)} is the source of an SVG <use>, which a browser does not take from a data: URL: put the symbol in the page")
        if tag in ("iframe", "frame", "embed") and path.suffix.lower() in HTML_SUFFIXES:
            raise Refused(EXIT_FAIL, f"{self.rel(path)} is a page inside the page, which cannot be inlined: put its content in the page")
        mime = MIME.get(path.suffix.lower())
        if mime is None:
            raise Refused(EXIT_FAIL, f"{self.rel(path)}: no type is known for {path.suffix or 'a file with no extension'}; this command inlines images ({', '.join(sorted(MIME))}) and fonts")
        return f"data:{mime};base64," + base64.b64encode(self.read(path)).decode("ascii") + fragment

    # ---- CSS
    def css(self, text: str, base: Path, label: str, first_line: int = 1, stack: tuple[str, ...] | None = None) -> str:
        """CSS text with each url() a data: URL and each @import replaced by the stylesheet it names, seen from its own folder. `stack` is set for a
        stylesheet file (the stylesheets being read, this one last): its @charset goes, and a stylesheet that imports itself is refused."""
        edits: list[tuple[int, int, str]] = []
        for start, end in sorted(sitedata._css_spans(text)):
            line = first_line + text.count("\n", 0, start)
            at = text.rfind("@import", 0, start)
            try:
                if at >= 0 and IMPORT_HEAD.search(text[at:start]):
                    found, tail = self.locate(text[start:end], base), IMPORT_TAIL.match(text, end)
                    if found is None or tail is None:
                        raise Refused(EXIT_FAIL, f"the @import of {sitedata._shown(text[start:end])} cannot be inlined: it has a condition (a media query, layer() or supports()) or is a data: URL")
                    sheet = self.rel(found[0])
                    if sheet in (stack or ()) or len(stack or ()) >= IMPORT_DEPTH:
                        raise Refused(EXIT_FAIL, f"{sheet} imports itself, or sits more than {IMPORT_DEPTH} stylesheets deep")
                    edits.append((at, tail.end(), self.css(self.code(found[0], "stylesheet"), found[0].parent, sheet, 1, (*(stack or ()), sheet))))
                else:
                    new = self.data_uri(text[start:end], base)
                    if new is not None:
                        edits.append((start, end, new))
            except Refused as e:
                self.problem(label, line, e)
        out = apply(text, edits)
        return CHARSET.sub("", out) if stack is not None else out

    # ---- HTML
    def page(self, text: str, base: Path, label: str) -> str:
        edits: list[tuple[int, int, str]] = []
        deferred: list[str] = []
        for t in htmlscan.tags(text):
            if t.closing:
                continue
            line = text.count("\n", 0, t.start) + 1
            a = t.attrs
            try:
                if t.name == "style":
                    close = re.compile(r"</style\s*>", re.I).search(text, t.end)
                    stop = close.start() if close else len(text)
                    edits.append((t.end, stop, self.css(text[t.end:stop], base, label, text.count("\n", 0, t.end) + 1)))
                elif t.name == "base" and a.get("href", "").strip():
                    raise Refused(EXIT_FAIL, "a <base href> changes every path of the page: take it out first")
                elif t.name == "script" and a.get("src", "").strip():
                    close = re.compile(r"</script\s*>", re.I).search(text, t.end)
                    element, moves = self.script(t, a, base)
                    if moves:
                        deferred.append(element)
                    edits.append((t.start, close.end() if close else len(text), "" if moves else element))
                elif t.name == "link":
                    edits += self.link(t, a, base, label, text)
                else:
                    edits += self.attributes(t, base, label, text)
            except Refused as e:
                self.problem(label, line, e)
        if deferred:
            body = text.lower().rfind("</body")
            at = len(text) if body < 0 else body
            edits.append((at, at, "".join(deferred)))
        return apply(text, edits)

    def script(self, t, a: dict, base: Path) -> tuple[str, bool]:
        """(the inline <script> element that takes the place of a <script src>, whether it moves to the end of <body>)."""
        found = self.locate(a["src"], base)
        if found is None:
            raise Refused(EXIT_FAIL, "a <script> whose src is a data: URL cannot be inlined")
        code = self.code(found[0], "script")
        module = a.get("type", "").strip().lower() == "module"
        if module and MODULE_IMPORT.search(code):
            raise Refused(EXIT_FAIL, f"{self.rel(found[0])} is a module that imports another file, which cannot be inlined: put it in one script")
        kept = "".join(" " + m.group(0) for m in sitedata._ATTR.finditer(t.attrs_src) if m.group("name").lower() not in SCRIPT_DROP)
        code = re.sub(r"</(script)", r"<\\/\1", code, flags=re.I).replace("<!--", "<\\!--")     # the text of a script must not end it, or open a comment
        return f"<script{kept}>{code}</script>", "defer" in a and not module

    def link(self, t, a: dict, base: Path, label: str, text: str) -> list[tuple[int, int, str]]:
        """The edit a <link> needs: a <style> element for a stylesheet, nothing for a hint, a data: URL in the href of an icon (a manifest has no type here: refused); none for any other link."""
        rel, href = set(a.get("rel", "").lower().split()), a.get("href", "").strip()
        if not href:
            return []
        if "stylesheet" in rel:
            if "alternate" in rel:
                raise Refused(EXIT_FAIL, "an alternate stylesheet cannot be inlined: it is off until the reader switches to it")
            found = self.locate(href, base)
            if found is None:
                raise Refused(EXIT_FAIL, "a stylesheet whose href is a data: URL cannot be inlined")
            media = f' media="{html.escape(a["media"], quote=True)}"' if a.get("media", "").strip() else ""
            sheet = self.rel(found[0])
            css = self.css(self.code(found[0], "stylesheet"), found[0].parent, sheet, 1, (sheet,))
            css = re.sub(r"</(style)", r"<\\/\1", css, flags=re.I)      # the text of a style must not end it
            return [(t.start, t.end, f"<style{media}>{css}</style>")]
        if rel & HINT_RELS:
            self.locate(href, base)      # a hint that names another website is refused; a local one is only dropped
            return [(t.start, t.end, "")]
        if rel & FILE_RELS:
            return self.attributes(t, base, label, text, only=("href",))
        return []

    def attributes(self, t, base: Path, label: str, text: str, only: tuple[str, ...] = ()) -> list[tuple[int, int, str]]:
        """The edits to the attributes of one tag that load a file: src, poster, the data of an <object>, the href of an SVG <image> or <use>, srcset, a style attribute."""
        edits: list[tuple[int, int, str]] = []
        for name, raw, g, start in attribute_values(t):
            if only and name not in only:
                continue
            line = text.count("\n", 0, start) + 1
            try:
                if name in ("src", "poster") or (name == "data" and t.name == "object") or (name in ("href", "xlink:href") and (t.name in ("image", "feimage", "use") or only)):
                    new = self.data_uri(html.unescape(raw), base, t.name)
                elif name in ("srcset", "imagesrcset"):
                    new, value = None, raw
                    for s, e in sorted(sitedata._srcset_spans(raw), reverse=True):
                        uri = self.data_uri(html.unescape(raw[s:e]), base)
                        if uri is not None:
                            value = new = value[:s] + uri + value[e:]
                elif name == "style":
                    done = self.css(html.unescape(raw), base, label, line)
                    new = None if done == html.unescape(raw) else html.escape(done, quote=True)
                else:
                    continue
            except Refused as e:
                self.problem(label, line, e)
                continue
            if new is not None:
                edits.append((start, start + len(raw), f'"{new}"' if g == "uq" else new))     # a data: URL ends in "=" at times, which an unquoted value cannot hold
        return edits


def inline(project: Path, page: Path) -> tuple[str, list[str]]:
    """-> (the text of the self-contained copy of `page`, the project-relative files it holds). Raises CliError, with every problem listed, when there is one."""
    one = Inliner(project)
    label = one.rel(page)
    try:
        source = page.read_bytes().decode("utf-8-sig")
    except UnicodeDecodeError:
        fail(EXIT_FAIL, f"{label} is not UTF-8 text, so the paths in it cannot be read")
    out = one.page(source, page.parent, label)
    if one.problems:
        listed = "\n".join(f"  - {m}" for _, m in one.problems[:SHOWN]) + (f"\n  - and {len(one.problems) - SHOWN} more" if len(one.problems) > SHOWN else "")
        fail(EXIT_USAGE if any(c == EXIT_USAGE for c, _ in one.problems) else EXIT_FAIL, f"nothing was written: {len(one.problems)} problem(s) stop {label}\n{listed}")
    again = Inliner(project)
    if again.page(out, page.parent, label) != out or again.problems or again.files:      # the copy is read once more: it must name no file to load
        fail(EXIT_FAIL, f"the copy of {label} still names a file to load, so it is not self-contained (a fault in this command, not in the page)")
    return out, list(one.files)


def out_file(project: Path, given: str) -> Path:
    """The file to write: a .html file outside the project, or under its tryout/ folder."""
    root = Path(os.path.realpath(project))
    real = _common._realpath_lenient(Path(given).expanduser())
    if real.suffix.lower() not in PAGE_SUFFIXES:
        fail(EXIT_USAGE, f"--out {given} must be a .html file")
    if real.is_dir():
        fail(EXIT_USAGE, f"--out {given} is a folder: name the file")
    if (real == root or root in real.parents) and Path(os.path.realpath(root / "tryout")) not in real.parents:
        fail(EXIT_USAGE, f"--out {given} must be outside the project, or under tryout/: a copy made for sharing is not a file of the brand")
    return real


def main() -> int:
    ap = Parser(prog="brand-creator inline", description=__doc__, formatter_class=__import__("argparse").RawDescriptionHelpFormatter)
    ap.add_argument("page", help="a page of the project (a try-out: tryout/<Name>/index.html)")
    ap.add_argument("--out", required=True, metavar="FILE.html",
                    help="where the copy goes: outside the project, or under its tryout/ folder (a relative path is read from the folder you run it in)")
    add_project_arg(ap)
    a = ap.parse_args()
    project = find_project(a.project)
    page = confine(project, a.page, what="page", read=True)
    if page.suffix.lower() not in PAGE_SUFFIXES or not page.is_file():
        fail(EXIT_USAGE, f"page {a.page} is not a .html file of the project")
    target = out_file(project, a.out)
    if target == page:
        fail(EXIT_USAGE, f"--out {a.out} is the page itself: the copy would overwrite it")
    text, files = inline(project, page)
    data = text.encode("utf-8")
    write_bytes_if_changed(target, data)
    print(f"wrote {target}: {len(data)} bytes, {len(files)} file(s) inlined" + (f" ({', '.join(files[:SHOWN])}{', ...' if len(files) > SHOWN else ''})" if files else ""))
    return 0


main_guard(main)
