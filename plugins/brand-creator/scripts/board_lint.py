#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator board-lint <page.html>: a round page must carry its required sections.

Sections are found by data-section attributes (the vocabulary is documented in scripts/CONTRACT.md, "Board contract").
A section that exists but is empty fails. What is required depends on the round (path rounds/rN/ or --round),
on BRAND-STATE.md (incumbent, reset_rounds, tier, architecture, inventory) and on the page's data-board kind.
Exit 1 lists every missing or empty requirement.
"""
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from _common import (EXIT_USAGE, Parser, Report, add_project_arg, confine, fail, find_project, main_guard,  # noqa: E402
                     read_state, rel)

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
MEDIA = {"img", "svg", "canvas", "picture", "video", "object", "iframe"}
SKIP_TEXT = {"script", "style", "template"}
HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
FILL = "[[fill"
PLACEHOLDER = re.compile(r"^\s*(todo|tbd|\.\.\.|\(\.\.\.\)|lorem ipsum.*)\s*$", re.I)


class Node:
    def __init__(self, tag, attrs, parent=None):
        self.tag, self.attrs, self.parent, self.children, self.chunks = tag, dict(attrs), parent, [], []

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
        self.root = Node("#root", {})
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


def main() -> int:
    ap = Parser(prog="brand-creator board-lint", description=__doc__, formatter_class=__import__("argparse").RawDescriptionHelpFormatter)
    add_project_arg(ap)
    ap.add_argument("page", help="round page (HTML), normally rounds/rN/board.html")
    ap.add_argument("--round", type=int, help="round number (default: from the path rounds/rN/ or the page's data-round)")
    ap.add_argument("--incumbent", choices=("yes", "no"), help="override BRAND-STATE incumbent")
    ap.add_argument("--min-directions", type=int, help="override the minimum number of directions (3 on pick boards, 1 otherwise)")
    a = ap.parse_args()
    project = find_project(a.project)
    page = confine(project, a.page, what="page")
    if not page.is_file():
        fail(EXIT_USAGE, f"page not found: {a.page}")
    root = parse_dom(page.read_text(encoding="utf-8", errors="replace"))
    state = read_state(project)
    st = state.data()
    rep = Report("board-lint", project, [page])
    rep.extra = {"page": rel(project, page)}

    # ---- template markers left unfilled (text and attribute values; HTML comments are ignored)
    unfilled = [c for n in root.walk() for c in n.chunks if isinstance(c, str) and FILL in c]
    unfilled += [v for n in root.walk() for v in n.attrs.values() if v and FILL in v]
    rep.add("page:unfilled", "fail" if unfilled else "pass", "no template markers left",
            detail=(f"{len(unfilled)} '{FILL} ...]]' marker(s) left, first: {unfilled[0].strip()[:80]!r}" if unfilled else "none"))

    # ---- which round and which kind of board
    m = re.search(r"(?:^|/)rounds/r(\d+)/", rel(project, page) + "/") or re.search(r"rounds/r(\d+)/", rel(project, page))
    path_round = int(m.group(1)) if m else None
    body = next((n for n in root.walk() if n.tag in ("body", "html") and "data-round" in n.attrs), None)
    page_round = int(body.attrs["data-round"]) if body and body.attrs["data-round"].isdigit() else None
    rnd = a.round or path_round or page_round
    if rnd is None:
        fail(EXIT_USAGE, "cannot tell the round: put the page under rounds/rN/, set data-round on <body>, or pass --round N")
    if page_round is None:
        rep.add("page:data-round", "fail", "page declares its round", detail='<body data-round="N"> is missing')
    elif page_round != rnd:
        rep.add("page:data-round", "fail", "page declares its round",
                detail=f'data-round="{page_round}" but this is round {rnd} (a copied page was not updated)')
    else:
        rep.add("page:data-round", "pass", "page declares its round", detail=f"round {rnd}")
    reset_rounds = [int(x) for x in (st.get("reset_rounds") or []) if str(x).isdigit()]
    map_round = rnd == 1 or rnd in reset_rounds
    kind = body.attrs.get("data-board") if body else None
    if kind not in ("pick", "refine"):
        rep.add("page:data-board", "fail", "page declares its kind", detail='<body data-board="pick|refine"> is missing or invalid')
        kind = "pick" if map_round else "refine"
    elif map_round and kind != "pick":
        rep.add("page:data-board", "fail", "page declares its kind", detail=f"round {rnd} must be a pick board (data-board=\"pick\")")
    else:
        rep.add("page:data-board", "pass", "page declares its kind", detail=kind)
    incumbent = (a.incumbent == "yes") if a.incumbent else str(st.get("incumbent", "none") or "none").strip().lower() not in ("none", "", "no")

    def need(sid: str, required: bool, why: str) -> Node | None:
        found = sections(root, sid)
        if not required:
            rep.add(f"section:{sid}", "info", "not required here", detail=why)
            return found[0] if found else None
        if not found:
            rep.add(f"section:{sid}", "fail", "required section", detail=f'missing: no element with data-section="{sid}" ({why})')
            return None
        if not any(n.nonempty() for n in found):
            rep.add(f"section:{sid}", "fail", "required section", detail=f'data-section="{sid}" is present but empty or a placeholder')
            return None
        rep.add(f"section:{sid}", "pass", "required section", detail=why)
        return next(n for n in found if n.nonempty())

    def field(parent: Node, fid: str, required: bool, label: str) -> bool:
        fs = [n for n in parent.find_all(data_field=fid)]
        ok = any(n.nonempty() for n in fs)
        if required:
            rep.add(f"{label}:{fid}", "pass" if ok else "fail", "required field",
                    detail="ok" if ok else f'missing or empty: data-field="{fid}" inside data-section="{parent.attrs.get("data-section")}"')
        return ok

    need("what-changed", rnd >= 2, "from round 2: what changed since the review")
    need("today", incumbent, "an incumbent mark or site exists (BRAND-STATE incumbent)")
    pmap = need("positioning-map", map_round, "round 1 and after a full rejection (reset_rounds)")
    need("strategy-core", rnd == 1, "round 1 shows the strategy core for reaction")
    need("hardest-surface", True, "the one surface where the mark is most likely to fail")
    need("weak-points", rnd >= 2, "from round 2: honest weak points")
    losers = need("losers", rnd >= 2, "from round 2: losing candidates stay with a one-line reason")
    if losers is not None:
        items = list(losers.find_all(data_section="loser"))
        if not items:
            rep.add("losers:items", "fail", "each loser carries a reason", detail='no data-section="loser" items inside the losers section')
        for i, it in enumerate(items, 1):
            reasons = [n for n in it.find_all(data_field="reason") if n.nonempty()]
            line = reasons[0].text().strip() if reasons else ""
            if not reasons:
                rep.add(f"loser:{it.attrs.get('data-name') or i}", "fail", "one-line reason", detail='missing data-field="reason"')
            elif len(line) > 200 or "\n" in line.strip():
                rep.add(f"loser:{it.attrs.get('data-name') or i}", "fail", "one-line reason", detail="the reason must be one line (200 characters at most)")
            else:
                rep.add(f"loser:{it.attrs.get('data-name') or i}", "pass", "one-line reason")
    need("none-of-these", kind == "pick", "every pick board carries a None of these option")
    qs = need("questions", True, "numbered questions with lettered options, answerable by number from a phone")
    if qs is not None:
        items = list(qs.find_all(data_section="question"))
        if not items:
            rep.add("questions:items", "fail", "numbered questions", detail='no data-section="question" items inside the questions section')
        for i, q in enumerate(items, 1):
            n = q.attrs.get("data-n", "").strip()
            qid = f"question:{n or i}"
            if n != str(i):
                rep.add(f"{qid}:number", "fail", "numbered in order", detail=f'data-n="{n}" but this is question {i} (number them 1, 2, 3 ...)')
            opts = [o.attrs.get("data-option", "").strip() for o in q.find_all() if "data-option" in o.attrs]
            want = [chr(ord("a") + k) for k in range(len(opts))]
            recommended = [o for o in q.find_all(data_recommended="true")]
            if len(opts) < 2:
                rep.add(f"{qid}:options", "fail", "lettered options", detail=f"{len(opts)} option(s); a question needs at least 2 (data-option=\"a\", \"b\" ...)")
            elif opts != want:
                rep.add(f"{qid}:options", "fail", "lettered options", detail=f"options are {opts}, expected {want}")
            elif len(recommended) != 1:
                rep.add(f"{qid}:options", "fail", "one recommended option",
                        detail=("no option is marked data-recommended (mark the one you would pick)" if not recommended
                                else f"{len(recommended)} options are marked data-recommended; exactly one"))
            else:
                rep.add(f"{qid}:options", "pass", "lettered options", detail=", ".join(opts))
    need("reply", True, "how to answer: a name or letter and one sentence")
    q_items = list(qs.find_all(data_section="question")) if qs is not None else []

    # ---- directions
    dirs = sections(root, "direction")
    min_dirs = a.min_directions or (3 if kind == "pick" else 1)
    rep.add("directions:count", "pass" if len(dirs) >= min_dirs else "fail", "enough directions",
            detail=f"{len(dirs)} found, need at least {min_dirs}")
    names, letters, registers = [], [], []
    for i, d in enumerate(dirs, 1):
        nm = d.attrs.get("data-name", "").strip()
        label = nm or f"#{i}"
        if not re.match(r"^[^\W\d_]{3,}", nm) or re.match(r"^(option|direction|variant|style|concept|route)\s*\d*$", nm, re.I):
            rep.add(f"direction:{label}:name", "fail", "word name", detail='data-name must be a word of 3+ letters (not "A", "Option 2")')
        elif nm.lower() in [x.lower() for x in names]:
            rep.add(f"direction:{label}:name", "fail", "word name", detail="duplicate direction name")
        else:
            rep.add(f"direction:{label}:name", "pass", "word name")
        names.append(nm)
        ltr = d.attrs.get("data-letter", "").strip()
        if ltr:
            if not re.fullmatch(r"[A-Z]", ltr) or ltr in letters:
                rep.add(f"direction:{label}:letter", "fail", "optional letter", detail=f"{ltr!r} must be one unique capital letter")
            letters.append(ltr)
        reg = d.attrs.get("data-register", "").strip()
        if kind == "pick":
            if not reg:
                rep.add(f"direction:{label}:register", "fail", "emotional register", detail="data-register is required on pick boards (one register per direction)")
            elif reg.lower() in [r.lower() for r in registers]:
                rep.add(f"direction:{label}:register", "fail", "emotional register", detail=f"register {reg!r} is used by two directions: three versions of one idea")
            else:
                rep.add(f"direction:{label}:register", "pass", "emotional register", detail=reg)
            registers.append(reg)
        field(d, "idea", True, f"direction:{label}")
        if kind == "pick":
            field(d, "reflex", True, f"direction:{label}")  # reflex test against references/ai-defaults.json
    if letters and q_items:
        # A direction letter that is also an option letter of a question that does not list the directions makes
        # "B" ambiguous in a phone reply ("B" the direction, or option b of question 2).
        lowered = {x.lower() for x in letters}
        for i, q in enumerate(q_items, 1):
            opts = [o for o in q.find_all() if "data-option" in o.attrs]
            text = " ".join(o.text() for o in opts).lower()
            if any(n and n.lower() in text for n in names):
                continue
            clash = sorted(lowered & {o.attrs.get("data-option", "").strip().lower() for o in opts})
            if clash:
                rep.add(f"question:{q.attrs.get('data-n', '').strip() or i}:letters", "warn", "direction letters do not clash with option letters",
                        detail=f"direction letter(s) {', '.join(c.upper() for c in clash)} are also option letters of this question, "
                               f"which does not list the directions: a reply of \"{clash[0]}\" is ambiguous. Drop the direction "
                               f"letters (word names are enough) or name the directions in the options")
    if map_round and pmap is not None:
        far = [d for d in dirs if d.attrs.get("data-far") == "true"]
        rep.add("map:far-from-norm", "pass" if far else "fail", "at least one direction far from the norm",
                detail=f"{len(far)} marked" if far else 'no direction has data-far="true"')
        placed = {n.attrs.get("data-direction", "").strip().lower() for n in pmap.walk() if n.attrs.get("data-direction")}
        absent = [n for n in names if n and n.lower() not in placed]
        rep.add("map:every-direction", "pass" if not absent else "fail", "every direction is placed on the map",
                detail="all placed" if not absent else f'not on the map (data-direction): {", ".join(absent)}')
        if rnd in reset_rounds:
            ok = any(n.nonempty() for n in pmap.find_all(data_field="failed-round"))
            rep.add("map:failed-round", "pass" if ok else "fail", "shows where the failed round sat",
                    detail="ok" if ok else 'data-field="failed-round" is missing or empty inside the map')

    # ---- my call
    mc = need("my-call", True, "the lead's recommendation with an honest critique")
    if mc is not None:
        field(mc, "recommendation", True, "my-call")
        field(mc, "critique", True, "my-call")
        if mc.attrs.get("data-judge") == "ran":
            for f in ("judge-view", "lead-view", "middle-option"):
                field(mc, f, True, "my-call")

    # ---- project-level: inventory before the first board (Full tier / product-in-family)
    if rnd == 1:
        needs_inv = str(st.get("tier", "")).lower() == "full" or str(st.get("architecture", "")).lower() == "product-in-family"
        inv = str(st.get("inventory", "") or "").strip()
        if needs_inv:
            ok = (project / "INVENTORY.md").is_file() or inv.lower().startswith("none")
            rep.add("project:inventory", "pass" if ok else "fail", "inventory before round 1",
                    detail="INVENTORY.md exists or BRAND-STATE records 'inventory: none (no target repo)'" if ok else
                           "round 1 needs INVENTORY.md, or `inventory: none (no target repo)` in BRAND-STATE.md (Full tier / product-in-family)")
        else:
            rep.add("project:inventory", "info", "not required here", detail="only the Full tier and product-in-family need an inventory")
    return rep.finish()


main_guard(main)
