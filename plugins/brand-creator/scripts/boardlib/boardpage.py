"""How board-lint and `state --record G1s` read a round page, so the two cannot disagree about what a page is. Standard library only.

The page is parsed into a tree of its tags. A repeated attribute counts once, by its first copy, as a browser reads it. The page's own
element is the <body> tag, or the <html> tag when the body declares neither data-round nor data-board; the round and the kind of the page
are both read from that one element, never one from each. A style board counts for the style gate (the pick board of a reset round, and
g1s_round) only when it declares data-board="style" and the round of its own folder, and holds at least MIN_TERRITORIES named territory
sections with content, so a stub page that only says "style", or a copy that still declares the round it came from, unlocks nothing
(scripts/CONTRACT.md, "Board contract"). A website references board counts the same way (is_site_refs_board: data-board="site-refs", its own round and at least
MIN_GROUPS named groups with content). A picture that must show itself without the network, a mark's thumbnail on a style board or a site's screenshot on a references board, is held to one rule
(thumb_problems). This folder is outside scripts/lib/ so that a change here does not make every pack stale.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
MEDIA = {"img", "svg", "canvas", "picture", "video", "object", "iframe"}
SKIP_TEXT = {"script", "style", "template"}
HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
PLACEHOLDER = re.compile(r"^\s*(todo|tbd|\.\.\.|\(\.\.\.\)|lorem ipsum.*)\s*$", re.I)
MIN_TERRITORIES = 4   # a style board shows at least this many style territories (the style lint requires them)
MIN_GROUPS = 4   # a website references board shows at least this many groups of sites (the references lint requires them)
KINDS = ("pick", "refine", "style", "motion", "site-refs", "site", "masters")   # the data-board values; a motion board (a round after G3 that tries the signature move), a website references board (a round after G4) and a site board (a round after G4w) are no pick, style, reset or rejected round
FILL = "[[fill"
# "Option 2", "Style A", "Direction II", "Option #2", "Style-3": a label, not a word name. A label word alone, or followed by a number
# (with or without a separator), or by one letter or a roman numeral after a space, "-" or "#". "Routes", "Looker" and "Moody" are words.
_LABEL_WORDS = "option|direction|variant|style|concept|route|territory|look|mood|idea|version|choice"
_ROMAN = "(?=[ivxlcdm])m{0,3}(?:cm|cd|d?c{0,3})(?:xc|xl|l?x{0,3})(?:ix|iv|v?i{0,3})"
GENERIC_NAME = re.compile(rf"^(?:{_LABEL_WORDS})(?:\d+|[\s#-]+(?:\d+|[^\W\d_]|{_ROMAN}))?$", re.I)
WORD_NAME = re.compile(r"^[^\W\d_]{3,}")
DATA_IMAGE = re.compile(r"^data:image/[a-z0-9.+-]+[;,]", re.I)


class Node:
    def __init__(self, tag, attrs, parent=None):
        self.tag, self.parent, self.children, self.chunks = tag, parent, [], []
        self.attrs: dict[str, str] = {}
        for k, v in attrs:
            self.attrs.setdefault(k, v)   # the first copy of a repeated attribute wins, as in a browser

    def walk(self):
        yield self
        for c in self.children:
            yield from c.walk()

    def text(self, skip_headings: bool = False) -> str:
        if self.tag in SKIP_TEXT or (skip_headings and self.tag in HEADINGS):
            return ""
        out = []
        for chunk in self.chunks:
            out.append(chunk if isinstance(chunk, str) else chunk.text(skip_headings))
        return "".join(out)

    def has_media(self) -> bool:
        return any(n.tag in MEDIA for n in self.walk() if n is not self)

    def nonempty(self) -> bool:
        """Content beyond a heading: text outside h1-h6, or an image/svg/canvas."""
        t = self.text(skip_headings=True).strip()
        return (bool(t) and not PLACEHOLDER.match(t)) or self.has_media()

    def find_all(self, **attr):
        for n in self.walk():
            if all(n.attrs.get(k.replace("_", "-")) == v for k, v in attr.items()):
                yield n


class Dom(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("#root", [])
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        n = Node(tag, [(k, v if v is not None else "") for k, v in attrs], self.cur)
        self.cur.children.append(n)
        self.cur.chunks.append(n)
        if tag not in VOID:
            self.cur = n

    def handle_startendtag(self, tag, attrs):
        n = Node(tag, [(k, v if v is not None else "") for k, v in attrs], self.cur)
        self.cur.children.append(n)
        self.cur.chunks.append(n)

    def handle_endtag(self, tag):
        n = self.cur
        while n is not self.root and n.tag != tag:
            n = n.parent
        if n is not self.root:
            self.cur = n.parent

    def handle_data(self, data):
        self.cur.chunks.append(data)


def parse_dom(text: str) -> Node:
    d = Dom()
    d.feed(text)
    d.close()
    return d.root


def sections(root: Node, sid: str) -> list[Node]:
    return list(root.find_all(data_section=sid))


def read_page(page: Path) -> Node | None:
    """The tree of a page file, or None when the file is missing or unreadable."""
    try:
        return parse_dom(page.read_text(encoding="utf-8", errors="replace"))
    except OSError:
        return None


def page_marker(root: Node) -> Node | None:
    """The element that declares the page's round and kind: the <body> tag, or the <html> tag when the body declares neither data-round
    nor data-board. None when no tag does."""
    for tag in ("body", "html"):
        for n in root.walk():
            if n.tag == tag and ("data-round" in n.attrs or "data-board" in n.attrs):
                return n
    return None


def page_kind(root: Node | None) -> str | None:
    """The data-board value the page declares (read from the same element as its round), or None."""
    marker = page_marker(root) if root is not None else None
    return marker.attrs.get("data-board") if marker is not None else None


def declared_round(root: Node | None) -> int | None:
    """The data-round the page declares as a whole number (read from the same element as its kind), or None."""
    marker = page_marker(root) if root is not None else None
    value = marker.attrs.get("data-round", "") if marker is not None else ""
    return int(value) if re.fullmatch(r"[0-9]+", value) else None


def is_territory(node: Node) -> bool:
    """A territory section that counts: it has a data-name and content beyond its heading."""
    return bool(node.attrs.get("data-name", "").strip()) and node.nonempty()


def territory_count(root: Node) -> int:
    return sum(1 for t in sections(root, "territory") if is_territory(t))


def is_style_board(root: Node | None, folder_round: int) -> bool:
    """Does the page in rounds/r<folder_round>/ count as a style board for the style gate? It declares data-board="style" and that round,
    and holds at least MIN_TERRITORIES territories that count."""
    return (root is not None and page_kind(root) == "style" and declared_round(root) == folder_round
            and territory_count(root) >= MIN_TERRITORIES)


def is_group(node: Node) -> bool:
    """A group of a website references board that counts: it has a data-name and content beyond its heading."""
    return bool(node.attrs.get("data-name", "").strip()) and node.nonempty()


def group_count(root: Node) -> int:
    return sum(1 for g in sections(root, "group") if is_group(g))


def is_site_refs_board(root: Node | None, folder_round: int) -> bool:
    """Does the page in rounds/r<folder_round>/ count as a website references board (for the site round, which waits for one when G4w names a pick)? It declares
    data-board="site-refs" and that round, and holds at least MIN_GROUPS groups that count."""
    return (root is not None and page_kind(root) == "site-refs" and declared_round(root) == folder_round
            and group_count(root) >= MIN_GROUPS)


def thumb_problems(im: Node, field: str = "thumb", subject: str = "the thumbnail", says: str = "the owner of the mark and where the image is from",
                   template_tail: "re.Pattern[str] | None" = None) -> list[str]:
    """What is wrong with a picture that must show itself without the network, as sentences ([] when it is sound): the element is an <img>, its src is an inlined data:image/ URI,
    it has no srcset, it has alt text, and it sits in a <figure> with a non-empty <figcaption> (the words of the caption are the author's). A mark's thumbnail on a style board
    (data-field="thumb": the caption names the owner of the mark) and a site's screenshot on a website references board (data-field="shot": it names whose site it is and when it
    was captured) are held to this one rule. template_tail is words the template itself writes after the author's, which are no caption (a site's screenshot: " · shown for private research"): they are
    dropped before the caption is tested, so a caption that kept only them is empty. The style board does not pass it."""
    src, alt = im.attrs.get("src", "").strip(), im.attrs.get("alt", "").strip()
    problems = []
    if im.tag != "img":
        problems.append(f'data-field="{field}" belongs on an <img>, not on <{im.tag}>')
    if not DATA_IMAGE.match(src):
        problems.append('src must be an inlined data:image/... URI (no network): ' + (f"got {src[:40]!r}" if src else "src is missing"))
    if im.attrs.get("srcset", "").strip():
        problems.append("srcset is not allowed (it would ask the network for another file)")
    if not alt:
        problems.append("alt text is missing or empty")
    fig = im.parent
    while fig is not None and fig.tag != "figure":
        fig = fig.parent
    if fig is None:
        problems.append(f"{subject} is not inside a <figure>: its <figcaption> names {says}")
    elif not any((t := (template_tail.sub("", c.text()) if template_tail is not None else c.text()).strip()) and not PLACEHOLDER.match(t)
                 for c in fig.walk() if c.tag == "figcaption"):
        problems.append(f"its <figure> has no non-empty <figcaption>: name {says}")
    return problems
