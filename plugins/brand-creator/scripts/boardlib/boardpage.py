"""How board-lint and `state --record G1s` read a round page, so the two cannot disagree about what a page is. Standard library only.

The page is parsed into a tree of its tags. A repeated attribute counts once, by its first copy, as a browser reads it. The page's own
element is the <body> tag, or the <html> tag when the body declares neither data-round nor data-board; the round and the kind of the page
are both read from that one element, never one from each. A style board counts for the style gate (the pick board of a reset round, and
g1s_round) only when it declares data-board="style" and the round of its own folder, and holds at least MIN_TERRITORIES named territory
sections with content, so a stub page that only says "style", or a copy that still declares the round it came from, unlocks nothing
(scripts/CONTRACT.md, "Board contract"). This folder is outside scripts/lib/ so that a change here does not make every pack stale.
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
KINDS = ("pick", "refine", "style", "motion")   # the data-board values; a motion board (a round after G3 that tries the signature move) is no pick, style, reset or rejected round
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
