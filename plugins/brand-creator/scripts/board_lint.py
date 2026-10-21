#!/usr/bin/env -S uv run --script --locked
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""brand-creator board-lint <page.html>: a round page must carry its required sections.

Sections are found by data-section attributes (the vocabulary is documented in scripts/CONTRACT.md, "Board contract").
A section that exists but is empty fails. What is required depends on the round (path rounds/rN/ or --round),
on BRAND-STATE.md (incumbent, reset_rounds, tier, architecture, inventory, gates.G1s, g1s_round) and on the page's data-board kind
(pick: round 1 or a round listed in reset_rounds; refine: the later rounds; style: the style research page of round 0, or of a round
listed in reset_rounds; see scripts/CONTRACT.md).
Exit 1 lists every missing or empty requirement.
On a refine board the kept masters of the round (rounds/rN/<direction>/*.svg, each <name>-dark.svg twin on the dark ground) are also
measured, as warnings only: every flat colour that touches the ground below the target (3:1, or touching.ground of the built tokens),
and, among the pixel drawings of one grid size in one direction, outline widths that differ (marklib/marks.py).
"""
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "boardlib"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "marklib"))
from _common import (EXIT_USAGE, CliError, Parser, Report, add_project_arg, confine, fail, find_project, gate_recorded,  # noqa: E402
                     list_rounds, main_guard, read_state, rel)
import svgtools  # noqa: E402
from boardpage import (MIN_TERRITORIES, PLACEHOLDER, Node, declared_round, is_style_board, page_kind, parse_dom, read_page,  # noqa: E402
                       sections, territory_count)
from _color import parse_hex, wcag_ratio  # noqa: E402
from marks import ground_contacts, ground_target, outline_width, tokens_ground  # noqa: E402

FILL = "[[fill"
# "Option 2", "Style A", "Direction II", "Option #2", "Style-3": a label, not a word name. A label word alone, or followed by a number
# (with or without a separator), or by one letter or a roman numeral after a space, "-" or "#". "Routes", "Looker" and "Moody" are words.
_LABEL_WORDS = "option|direction|variant|style|concept|route|territory|look|mood|idea|version|choice"
_ROMAN = "(?=[ivxlcdm])m{0,3}(?:cm|cd|d?c{0,3})(?:xc|xl|l?x{0,3})(?:ix|iv|v?i{0,3})"
GENERIC_NAME = re.compile(rf"^(?:{_LABEL_WORDS})(?:\d+|[\s#-]+(?:\d+|[^\W\d_]|{_ROMAN}))?$", re.I)
WORD_NAME = re.compile(r"^[^\W\d_]{3,}")
DATA_IMAGE = re.compile(r"^data:image/[a-z0-9.+-]+[;,]", re.I)


def srcset_urls(value: str) -> list[str]:
    """The URLs of an srcset attribute. As in HTML, a URL is a run of characters without white space (so a data: URI keeps its
    comma), and what follows it up to the next comma outside brackets is its descriptor (1x, 640w)."""
    urls: list[str] = []
    i, n = 0, len(value)
    while i < n:
        while i < n and (value[i].isspace() or value[i] == ","):
            i += 1
        j = i
        while j < n and not value[j].isspace():
            j += 1
        url, i = value[i:j], j
        if url.endswith(","):
            url = url.rstrip(",")
        else:
            depth = 0
            while i < n:
                ch = value[i]
                i += 1
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth = max(0, depth - 1)
                elif ch == "," and depth == 0:
                    break
        if url:
            urls.append(url)
    return urls


def style_rearmed(project: Path, rnd: int, reset_rounds: list[int], g1s_round: int | None) -> tuple[bool, str]:
    """After a full rejection the pick board of reset round `rnd` needs a new style board and a style pick recorded after it.
    The rejected round is the highest earlier round whose board is not a style board. The new style board is a style board in a
    round listed in reset_rounds that lies after the rejected round and before `rnd` (the latest one counts); a page that only says
    data-board="style" counts when it declares its own round and holds MIN_TERRITORIES named territories with content, as the style lint
    asks. G1s must have been recorded when that round or a later style board was on disk (g1s_round, written by `state --record G1s`).
    Returns (ok, detail)."""
    pages = {n: read_page(path / "board.html") for n, path in list_rounds(project) if n < rnd}
    last = max((n for n, root in pages.items() if page_kind(root) != "style"), default=-1)
    declared = [n for n, root in pages.items() if page_kind(root) == "style" and n > last and n in reset_rounds]
    styles = [n for n in declared if is_style_board(pages[n], n)]
    rejected = f"the rejected round is r{last}" if last >= 0 else "no earlier pick or refine round was found"

    def not_counted(n: int) -> str:
        said = declared_round(pages[n])
        if said != n:
            return f'r{n} declares data-round="{said}" (a copied page)' if said is not None else f"r{n} declares no data-round"
        return f"r{n} has {territory_count(pages[n])} of the {MIN_TERRITORIES} territories a style board needs"

    if not styles:
        span = f"between r{last} and r{rnd}" if last >= 0 else f"before r{rnd}"
        thin = ", ".join(not_counted(n) for n in sorted(declared))
        return False, ("after a full rejection, show a new style board in a reset round before the next pick board "
                       f"(a page with data-board=\"style\" in a round listed in reset_rounds, {span}; {rejected})"
                       + (f". Not counted as a style board: {thin}" if thin else ""))
    new = max(styles)
    if g1s_round is None or g1s_round < new:
        return False, ("G1s still holds the pick from before the rejection: record the owner's new pick with state --record G1s "
                       f"\"picked <territory>\" (g1s_round is {'missing' if g1s_round is None else g1s_round}; the new style board is "
                       f"r{new}, and the record must come after it)")
    return True, f"the new style board r{new} comes after the rejected round and the pick was recorded after it (g1s_round {g1s_round}; {rejected})"


MASTERS_LABEL = "kept masters before G3 (advice, warnings only)"
SKIP_DIRS = ("drafts", "source", "before")   # before/: the old icons adoption replaces (12-history), not masters


def check_masters(rep: Report, project: Path, rnd: int) -> None:
    """The kept masters of a refine round, measured before the owner approves it (G3): colours that touch the ground under the
    target, and outline widths that differ among the pixel drawings of one grid size in one direction. Warnings only: a strap that
    runs off its drawing on purpose is the owner's call, and the board names it under Weak points."""
    rdir = project / "rounds" / f"r{rnd}"
    dirs = sorted(d for d in rdir.iterdir() if d.is_dir() and d.name not in SKIP_DIRS
                  and not d.name.startswith((".", "removed-"))) if rdir.is_dir() else []
    found = {d: sorted(f for f in d.glob("*.svg") if f.is_file()) for d in dirs}
    found = {d: fs for d, fs in found.items() if fs}
    if not found:
        rep.add("masters", "info", MASTERS_LABEL, detail=f"no SVG masters in rounds/r{rnd}/<direction>/: nothing to measure")
        return
    if not shutil.which("resvg"):
        rep.add("masters", "warn", MASTERS_LABEL, detail="NOT verified: resvg is not installed, so the kept masters were not measured "
                                                         "(run /brand-creator:setup)")
        return
    gl, gd = tokens_ground(project, "light", "#ffffff"), tokens_ground(project, "dark", "#111111")
    target, target_src = ground_target(project)
    unreadable: set = set()

    def measured(fn, art: Path):
        """fn(svg text), or None with a warning when the file cannot be read or drawn (one bad SVG never stops the lint)."""
        try:
            return fn(art.read_text(encoding="utf-8"))
        except (CliError, svgtools.SvgError, OSError, ValueError, UnicodeError) as e:
            if art not in unreadable:
                unreadable.add(art)
                rep.add(f"masters:file:{rel(project, art)}", "warn", MASTERS_LABEL,
                        detail=f"NOT measured: {rel(project, art)} could not be read or drawn ({getattr(e, 'message', None) or e})")
            return None

    for d, files in found.items():
        light = [f for f in files if not f.stem.endswith("-dark")]
        for f in light:
            twin = confine(project, f.with_name(f.stem + "-dark.svg"), what="dark master")
            for art, mode, ground in ((f, "light", gl), (twin if twin.is_file() else f, "dark", gd)):
                rid = f"masters:ground:{rel(project, art)}:{mode}"
                contacts = measured(ground_contacts, art)
                if art in unreadable:
                    continue
                if contacts is None:
                    rep.add(rid, "warn", MASTERS_LABEL, detail=f"NOT verified: {rel(project, art)} uses paint that is not a flat fill")
                    continue
                if not contacts:
                    rep.add(rid, "warn", MASTERS_LABEL, detail=f"NOT verified: no flat colour of {rel(project, art)} meets the {mode} ground in "
                                                               f"a way that can be measured (hairlines, or shapes too thin at 512 px)")
                    continue
                low = sorted(((round(wcag_ratio(parse_hex(hx), parse_hex(ground)), 2), hx) for hx in contacts))
                low = [(r, hx) for r, hx in low if r < target]
                if low:
                    rep.add(rid, "warn", MASTERS_LABEL, ground=ground, below=[{"hex": hx, "ratio": r} for r, hx in low],
                            detail=f"on the {mode} ground {ground}: " + ", ".join(f"{hx} touches it at {r}:1" for r, hx in low)
                                   + f" (target {target:g}:1, {target_src}); give it an edge, or name it under Weak points")
                else:
                    rep.add(rid, "pass", MASTERS_LABEL, ground=ground, detail=f"every colour that touches the {mode} ground {ground} "
                                                                              f"reaches {target:g}:1")
        widths: dict[int, dict[str, int]] = {}
        for f in light:
            ow = measured(outline_width, f)
            if ow and ow["width"]:
                widths.setdefault(ow["grid"], {})[f.name] = ow["width"]
            elif ow:
                rep.add(f"masters:outline:{rel(project, f)}", "info", MASTERS_LABEL, detail=f"no outline width to compare: {ow['why']}")
        for grid, by_file in sorted(widths.items()):
            if len(by_file) < 2:
                continue
            listed = ", ".join(f"{name} {w} px" for name, w in sorted(by_file.items()))
            rid = f"masters:outline:{rel(project, d)}:{grid}"
            if len(set(by_file.values())) > 1:
                rep.add(rid, "warn", MASTERS_LABEL, widths=by_file, detail=f"outline widths differ among the {grid} px grids: {listed}; "
                                                                           f"one family draws one weight")
            else:
                rep.add(rid, "pass", MASTERS_LABEL, widths=by_file, detail=f"one outline width among the {grid} px grids: {listed}")


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
    if a.round is not None and path_round is not None and a.round != path_round:
        fail(EXIT_USAGE, f"--round {a.round} contradicts the page's folder rounds/r{path_round}/: drop --round, or lint the page of round {a.round}")
    page_round = declared_round(root)   # read from the one element that declares both the round and the kind
    rnd = a.round if a.round is not None else (path_round if path_round is not None else page_round)
    if rnd is None:
        fail(EXIT_USAGE, "cannot tell the round: put the page under rounds/rN/, set data-round on <body>, or pass --round N")
    if page_round is None:
        rep.add("page:data-round", "fail", "page declares its round", detail='<body data-round="N"> is missing')
    elif page_round != rnd:
        rep.add("page:data-round", "fail", "page declares its round",
                detail=f'data-round="{page_round}" but this is round {rnd} (a copied page was not updated)')
    else:
        rep.add("page:data-round", "pass", "page declares its round", detail=f"round {rnd}")
    reset_rounds = state.reset_rounds()
    map_round = rnd == 1 or rnd in reset_rounds
    style_round = rnd == 0 or rnd in reset_rounds   # the style research runs before round 1, and again after a full rejection
    kind = page_kind(root)
    if kind not in ("pick", "refine", "style"):
        rep.add("page:data-board", "fail", "page declares its kind", detail='<body data-board="pick|refine|style"> is missing or invalid')
        kind = "pick" if map_round else "refine"
    elif kind == "style" and not style_round:
        rep.add("page:data-board", "fail", "page declares its kind",
                detail=f'a style board is round 0 (rounds/r0/, data-round="0") or a round listed in reset_rounds, not round {rnd}')
    elif kind != "style" and rnd == 0:
        rep.add("page:data-board", "fail", "page declares its kind", detail='round 0 is the style board (data-board="style")')
    elif kind == "pick" and not map_round:
        rep.add("page:data-board", "fail", "page declares its kind",
                detail="a pick board belongs to round 1 or to a round listed in reset_rounds (after a full rejection); later rounds are refine boards")
    elif map_round and kind not in ("pick", "style"):
        rep.add("page:data-board", "fail", "page declares its kind",
                detail=f"round {rnd} must be a pick board (data-board=\"pick\"), or a style board when the style research runs again (reset rounds)")
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

    def check_questions(qs: Node | None) -> None:
        if qs is None:
            return
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

    def check_my_call() -> None:
        mc = need("my-call", True, "the lead's recommendation with an honest critique")
        if mc is not None:
            field(mc, "recommendation", True, "my-call")
            field(mc, "critique", True, "my-call")
            if mc.attrs.get("data-judge") == "ran":
                for f in ("judge-view", "lead-view", "middle-option"):
                    field(mc, f, True, "my-call")

    def check_thumb(im: Node, tid: str) -> None:
        """An optional thumbnail of a reference's real mark (data-field="thumb"): an <img> inlined as a data: image, so the picture
        needs no network, with alt text, in a <figure> with a non-empty <figcaption> (its words are the author's)."""
        src, alt = im.attrs.get("src", "").strip(), im.attrs.get("alt", "").strip()
        problems = []
        if im.tag != "img":
            problems.append(f'data-field="thumb" belongs on an <img>, not on <{im.tag}>')
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
            problems.append("the thumbnail is not inside a <figure>: its <figcaption> names the owner of the mark")
        elif not any((t := c.text().strip()) and not PLACEHOLDER.match(t) for c in fig.walk() if c.tag == "figcaption"):
            problems.append("its <figure> has no non-empty <figcaption>: name the owner of the mark and where the image is from")
        rep.add(tid, "fail" if problems else "pass", "thumbnail is inlined (no network), has alt text and a caption",
                detail="; ".join(problems) if problems else "data: image with alt text and a caption")

    def check_images() -> None:
        """Every <img src> and every srcset (on <img> or <source>) of a style board is an inlined data:image/ URI, so no picture
        needs the network. A thumbnail (data-field="thumb") is held to the same and to more by check_thumb, with a result of its own."""
        problems = []
        for n in root.walk():
            if n.attrs.get("data-field") == "thumb" or n.tag not in ("img", "source"):
                continue
            if n.tag == "img" and not DATA_IMAGE.match(n.attrs.get("src", "").strip()):
                shown = n.attrs.get("src", "").strip()
                problems.append("<img src> " + (f"{shown[:40]!r}" if shown else "is missing"))
            problems += [f"<{n.tag} srcset> {u[:40]!r}" for u in srcset_urls(n.attrs.get("srcset", "")) if not DATA_IMAGE.match(u)]
        rep.add("images:inlined", "fail" if problems else "pass", "every <img src> and srcset is an inlined data:image/ URI (no network)",
                detail=("not inlined: " + "; ".join(problems[:4]) + (f"; and {len(problems) - 4} more" if len(problems) > 4 else "")
                        if problems else "all inlined (or no images outside the thumbnails)"))

    def check_style(rnd: int) -> None:
        """The round 0 style research page (data-board="style"): audience, surfaces, norm, 4+ territories each with 3+ references."""
        need("audience", True, "who sees the mark: the people and what they expect")
        need("surfaces", True, "where the mark is seen")
        need("norm", True, "the category norm: what to avoid")
        terrs = sections(root, "territory")
        counted = territory_count(root)   # named, with content: the same count as the style gate's
        rep.add("territories:count", "pass" if counted >= MIN_TERRITORIES else "fail", "enough style territories",
                detail=f"{counted} found with a name and content, need at least {MIN_TERRITORIES} (and 6 at most is the aim)")
        seen: list[str] = []
        for i, t in enumerate(terrs, 1):
            nm = t.attrs.get("data-name", "").strip()
            label = nm or f"#{i}"
            tid = f"territory:{label}"
            if not WORD_NAME.match(nm) or GENERIC_NAME.match(nm):
                rep.add(f"{tid}:name", "fail", "word name", detail='data-name must be a word of 3+ letters (not "A", "Style 2", "Option B", "Territory 1")')
            elif nm.lower() in seen:
                rep.add(f"{tid}:name", "fail", "word name", detail="duplicate territory name")
            else:
                rep.add(f"{tid}:name", "pass", "word name")
            seen.append(nm.lower())
            field(t, "idea", True, tid)
            refs_nodes = [n for n in t.find_all(data_field="references")]
            good = 0
            for r in refs_nodes:
                for li in (n for n in r.walk() if n.tag == "li"):
                    links = [n for n in li.walk() if n.tag == "a" and re.match(r"https?://\S+", n.attrs.get("href", "").strip())]
                    takes = [n for n in li.find_all(data_field="take") if n.nonempty()]
                    if links and takes:
                        good += 1
            rep.add(f"{tid}:references", "pass" if good >= 3 else "fail", "3+ named references with a link and what to take",
                    detail=(f"{good} reference(s)" if good >= 3 else
                            f"{good} usable reference(s); each <li> in data-field=\"references\" needs an <a href=\"https://...\"> and a non-empty data-field=\"take\" (3 at least)"))
            for k, im in enumerate(t.find_all(data_field="thumb"), 1):
                check_thumb(im, f"{tid}:thumb:{k}")
        inside = {id(n) for t in terrs for n in t.walk()}
        for k, im in enumerate((n for n in root.find_all(data_field="thumb") if id(n) not in inside), 1):
            check_thumb(im, f"thumb:{k}")
        check_images()
        need("none-of-these", True, "the way out: none of these, research again")
        check_my_call()
        qs = need("questions", True, "numbered questions with lettered options, answerable by number from a phone")
        check_questions(qs)
        need("reply", True, "how to answer: a territory name or letter and one sentence")

    if kind == "style":
        check_style(rnd)
        return rep.finish()

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
    check_questions(qs)
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
        if not WORD_NAME.match(nm) or GENERIC_NAME.match(nm):
            rep.add(f"direction:{label}:name", "fail", "word name", detail='data-name must be a word of 3+ letters (not "A", "Option 2", "Direction II")')
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
    check_my_call()

    # ---- project-level: the style research gate (G1s) comes before every pick board. Round 1: a recorded G1s is enough (a pick, "skipped by
    # owner", or an honest "n/a"). The pick board of a reset round (after a full rejection) also needs a new style board in a reset round
    # and a G1s recorded after it, so the pick from before the rejection cannot stand in; a skip is for the first pick board only.
    if kind == "pick":
        g = gate_recorded(project, "G1s")
        reset_pick = rnd >= 2 and rnd in reset_rounds
        raw_round = str(st.get("g1s_round", "") or "").strip()
        g1s_round = int(raw_round) if re.fullmatch(r"\d+", raw_round) else None
        if not g:
            how = ("show the style board (round 0, or a reset round listed in reset_rounds), then record the owner's pick with "
                   "`state --record G1s \"picked <territory>\"` "
                   "(a project already past round 1 records `state --record G1s \"n/a: round 1 drawn before the style step\"`, "
                   "and when the owner skips the research `state --record G1s \"skipped by owner\"`)")
            if reset_pick:
                how += ". After a full rejection the style board is required and a skip or an n/a no longer counts: show a new style board in a reset round, then record the owner's new pick"
            rep.add("project:style-gate", "fail", "style pick (G1s) before a pick board", detail="a pick board waits for the style research: " + how)
        elif reset_pick:
            ok, why = style_rearmed(project, rnd, reset_rounds, g1s_round)
            rep.add("project:style-gate", "pass" if ok else "fail", "style pick (G1s) before a pick board",
                    detail=f"G1s: {g}; {why}" if ok else why)
        else:
            rep.add("project:style-gate", "pass", "style pick (G1s) before a pick board", detail=f"G1s: {g}")

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
    if kind == "refine":
        check_masters(rep, project, rnd)
    return rep.finish()


main_guard(main)
